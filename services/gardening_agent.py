"""
services/gardening_agent.py – Direct intent detection + LLM fallback
Handles multiple plants, strips time phrases from plant names.
"""

import os
import re
import asyncio
import logging
import threading
import datetime
from typing import Optional, List, Tuple
from dotenv import load_dotenv

# Suppress logs
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)

import litellm
litellm.suppress_debug_info = True

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openrouter/openai/gpt-4o-mini"
APP_NAME = "seedsage"

# ---------- Date parsing (supports "two weeks ago") ----------
def parse_relative_date(text: str) -> Optional[str]:
    if not text:
        return None
    text = text.lower().strip()
    today = datetime.date.today()
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
    }
    m = re.search(r'last\s+(' + '|'.join(months.keys()) + r')', text)
    if m:
        month = months[m.group(1)]
        year = today.year
        if today.month <= month:
            year -= 1
        return datetime.date(year, month, 15).isoformat()
    m = re.search(r'(?:in\s+)?(' + '|'.join(months.keys()) + r')', text)
    if m:
        month = months[m.group(1)]
        year = today.year
        if today.month > month:
            year += 1
        return datetime.date(year, month, 15).isoformat()
    patterns = [
        (r"(\d+)\s*day[s]?\s*ago", lambda d: today - datetime.timedelta(days=int(d))),
        (r"(\d+)\s*week[s]?\s*ago", lambda d: today - datetime.timedelta(weeks=int(d))),
        (r"(\d+)\s*month[s]?\s*ago", lambda d: today - datetime.timedelta(days=int(d)*30)),
        (r"a week ago", lambda _: today - datetime.timedelta(days=7)),
        (r"two weeks ago", lambda _: today - datetime.timedelta(weeks=2)),
        (r"a day ago", lambda _: today - datetime.timedelta(days=1)),
        (r"a month ago", lambda _: today - datetime.timedelta(days=30)),
        (r"last week", lambda _: today - datetime.timedelta(days=7)),
        (r"yesterday", lambda _: today - datetime.timedelta(days=1)),
    ]
    for pat, fn in patterns:
        m = re.search(pat, text)
        if m:
            if m.groups():
                return fn(m.group(1)).isoformat()
            else:
                return fn(None).isoformat()
    return None

def normalise_plant_name(name: str) -> str:
    if not name:
        return ""
    # First remove any trailing time phrases
    time_phrases = r'\s+(?:a month ago|two weeks ago|2 weeks ago|last week|a week ago|yesterday|today)$'
    name = re.sub(time_phrases, '', name, flags=re.IGNORECASE)
    name = name.lower().strip()
    if name.endswith('ies'):
        name = name[:-3] + 'y'
    elif name.endswith('s') and not name.endswith('ss'):
        name = name[:-1]
    return name

# ---------- Tools ----------
def request_add_plant(plant_name: str, raw_text: str):
    plant_name = normalise_plant_name(plant_name)
    return {
        "action": "add_plant",
        "plant_name": plant_name,
        "planted_date": parse_relative_date(raw_text),
    }

def request_schedule_plan(plant_name: str, raw_text: str):
    plant_name = normalise_plant_name(plant_name)
    return {
        "action": "schedule_plan",
        "plant_name": plant_name,
        "after_date": parse_relative_date(raw_text),
    }

def request_remove_plant(plant_name: str):
    plant_name = normalise_plant_name(plant_name)
    return {"action": "remove_plant", "plant_name": plant_name}

def confirm_remove_plant(plant_name: str):
    return request_remove_plant(plant_name)

def generate_planting_plan(plant_name: str, postcode: str, planted_date: str):
    from utils.llm import generate_plan
    from utils.smart_tasks import generate_task_events
    anchor = None
    if planted_date:
        try:
            anchor = datetime.date.fromisoformat(planted_date)
        except:
            pass
    plant_name = normalise_plant_name(plant_name)
    plan = generate_plan(plant_name, postcode, actual_sow_date=anchor, actual_outdoor_date=anchor)
    sow_date = anchor or datetime.date.today()
    outdoor_date = anchor or datetime.date.today()
    events = generate_task_events(plan.get("tasks", []), outdoor_anchor=outdoor_date, indoor_anchor=sow_date, last_frost_date=None)
    plan["task_events"] = events
    return {
        "action": "schedule_plan",
        "plant_name": plant_name,
        "after_date": planted_date if planted_date else anchor.isoformat() if anchor else None,
    }

def _make_harvest_tool(user_context: dict):
    from services.plant_services import get_plant_guide
    def when_to_harvest(plant_name: str) -> dict:
        plant = normalise_plant_name(plant_name)
        today = datetime.date.today()
        plans = user_context.get("plans", {})
        garden = user_context.get("plants", {})
        return {"message": f"Check your calendar for {plant} harvest tasks. If you have a plan, see 'Harvest' tasks."}
    return when_to_harvest

# ---------- LLM Agent for general Q&A ----------
def build_agent(user_context):
    today = datetime.date.today().isoformat()
    postcode = user_context.get("postcode", "unknown")
    plant_list = ", ".join(user_context.get("plants", {}).keys()) or "none"
    instruction = f"""You are SeedSage, a UK gardening assistant. Answer questions about plant care, watering, fertilising, pests, companion planting, and general gardening advice. Keep answers short, friendly, and practical for the UK climate. Today: {today}. User's plants: {plant_list}. Postcode: {postcode}."""
    return Agent(
        model=LiteLlm(model=MODEL, api_key=OPENROUTER_API_KEY, api_base="https://openrouter.ai/api/v1"),
        name="seedsage_qa_agent",
        instruction=instruction,
        tools=[_make_harvest_tool(user_context)],
    )

# ---------- Async runner for LLM ----------
_loop = None
_loop_lock = threading.Lock()

def _get_or_create_loop():
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            t = threading.Thread(target=_loop.run_forever, daemon=True, name="adk-event-loop")
            t.start()
    return _loop

def _run_coroutine_safe(coro):
    import concurrent.futures
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=60)
    else:
        result_holder = {}
        def run_in_new_loop():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result_holder["value"] = new_loop.run_until_complete(coro)
            except Exception as e:
                result_holder["error"] = e
            finally:
                new_loop.close()
        t = threading.Thread(target=run_in_new_loop, daemon=True)
        t.start()
        t.join(timeout=60)
        if "error" in result_holder:
            raise result_holder["error"]
        if "value" not in result_holder:
            raise TimeoutError("Agent timed out after 60 seconds")
        return result_holder["value"]

async def run_llm_turn(message, user_context, session_id):
    svc = InMemorySessionService()
    agent = build_agent(user_context)
    user_id = user_context.get("name", "user").replace(" ", "_")
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=svc)
    await svc.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    content = genai_types.Content(role="user", parts=[genai_types.Part(text=message)])
    final_response = ""
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if getattr(event, "is_final_response", False) and event.content and event.content.parts:
                if not final_response:
                    final_response = event.content.parts[0].text
    except Exception as e:
        final_response = f"Sorry, I'm having trouble answering that. {str(e)[:200]}"
    if not final_response:
        final_response = "I'm not sure about that. Could you rephrase?"
    return final_response

# ---------- Main run_agent with direct intents (supports multiple plants, strips time) ----------
def run_agent(user_message: str, user_context: dict, session_id: str) -> Tuple[str, List[dict]]:
    msg = user_message.lower()
    actions = []

    # Helper to strip trailing time phrases from a plant name candidate
    def strip_time(name: str) -> str:
        return re.sub(r'\s+(?:a month ago|two weeks ago|last week|a week ago|yesterday|today)$', '', name).strip()

    # ----- REMOVE PLANT (multiple) -----
    if re.search(r'\bremove\s+', msg) or re.search(r'\bdelete\s+', msg):
        match = re.search(r'\b(?:remove|delete)\s+(.+)', msg)
        if match:
            plants_part = match.group(1)
            plant_names = re.split(r',\s*|\s+and\s+', plants_part)
            for raw_plant in plant_names:
                plant = normalise_plant_name(strip_time(raw_plant.strip()))
                if plant:
                    actions.append({"action": "remove_plant", "plant_name": plant})
            if actions:
                plant_list_str = ", ".join([p["plant_name"] for p in actions])
                return f"I've removed {plant_list_str} from your garden.", actions

    # ----- ADD + PLAN (multiple plants) -----
    if re.search(r'(?:planted|add|sowed|sown)\s+.+?\bplan\b', msg):
        match = re.search(r'(?:planted|add|sowed|sown)\s+(.+?)(?:\s+(?:a month ago|two weeks ago|last week|a week ago|yesterday|and create a plan|create a plan|$))', msg)
        if match:
            plants_part = match.group(1)
            # Remove trailing time phrase if still attached
            plants_part = strip_time(plants_part)
            plant_names = re.split(r',\s*|\s+and\s+', plants_part)
            date_val = parse_relative_date(user_message)
            for raw_plant in plant_names:
                plant = normalise_plant_name(raw_plant.strip())
                if plant:
                    actions.append({"action": "add_plant", "plant_name": plant, "planted_date": date_val})
                    actions.append({"action": "schedule_plan", "plant_name": plant, "after_date": date_val})
            if actions:
                added_names = list(set([a['plant_name'] for a in actions if a['action']=='add_plant']))
                return f"I've added {', '.join(added_names)} and will create plans.", actions

    # ----- ADD PLANTS only (multiple) -----
    if re.search(r'\b(?:planted|add|sowed|sown)\s+', msg) and "plan" not in msg:
        match = re.search(r'(?:planted|add|sowed|sown)\s+(.+)', msg)
        if match:
            plants_part = match.group(1)
            plants_part = strip_time(plants_part)
            plant_names = re.split(r',\s*|\s+and\s+', plants_part)
            date_val = parse_relative_date(user_message)
            added = []
            for raw_plant in plant_names:
                plant = normalise_plant_name(raw_plant.strip())
                if plant:
                    actions.append({"action": "add_plant", "plant_name": plant, "planted_date": date_val})
                    added.append(plant)
            if actions:
                return f"I've added {', '.join(added)} to your garden.", actions

    # ----- PLAN only (single plant, already exists) -----
    if re.search(r'\b(?:plan|schedule)\s+for\s+(\w+)', msg) or re.search(r'\bcreate\s+a\s+plan\s+for\s+(\w+)', msg):
        m = re.search(r'(?:plan|schedule|create a plan) for (\w+)', msg)
        if m:
            plant = normalise_plant_name(m.group(1))
            if plant in user_context.get("plants", {}):
                actions.append({"action": "schedule_plan", "plant_name": plant, "after_date": None})
                return f"I'll create a growing plan for {plant}.", actions
            else:
                return f"I don't see {plant} in your garden yet. Please add it first.", []

    # ----- For all other questions → use LLM -----
    try:
        response = _run_coroutine_safe(run_llm_turn(user_message, user_context, session_id))
        return response, []
    except Exception as e:
        return f"⚠️ Agent error: {str(e)[:200]}", []