"""
utils/llm.py – Enhanced with fallbacks, retries, and better flower support.
"""

import requests
import json
import os
import datetime
import time
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://seedsage.app",
    "X-Title": "SeedSage",
}
MODEL = "openai/gpt-4o-mini"
MAX_RETRIES = 2
RETRY_DELAY = 1  # seconds

# Local plant name mapping for common misspellings (fallback if API fails)
PLANT_NAME_MAP = {
    "tomatos": "tomato",
    "cucumbers": "cucumber",
    "courgettes": "courgette",
    "aubergines": "aubergine",
    "peppers": "pepper",
    "chillies": "chilli",
    "basils": "basil",
    "carrots": "carrot",
    "onions": "onion",
    "garlics": "garlic",
    "potatoes": "potato",
    "lettuces": "lettuce",
    "hycinths": "hyacinth",
    "tulips": "tulip",
    "daffodils": "daffodil",
}

# Plants that MUST start indoors in UK climate
INDOOR_START_PLANTS = {
    "tomato", "tomatoes", "pepper", "chilli", "chili", "aubergine", "eggplant",
    "basil", "courgette", "cucumber", "sweetcorn", "corn", "celery", "celeriac",
    "leek", "onion", "red onion", "shallot", "cauliflower", "brussels sprout",
    "brussels sprouts", "broccoli", "cabbage", "kale",
}

# Plants that should ONLY go direct outdoors (don't like transplanting)
DIRECT_SOW_ONLY = {
    "carrot", "carrots", "radish", "radishes", "beetroot", "beet",
    "parsnip", "turnip", "pea", "peas", "bean", "beans",
    "broad bean", "broad beans", "spinach", "dill", "coriander",
    "fennel", "nasturtium",
}

def _estimate_last_frost(postcode: str) -> datetime.date:
    today = datetime.date.today()
    year = today.year
    pc = postcode.upper().strip()
    northern = {"EH","G","AB","DD","PH","IV","KW","TD","DG","ML","KY","FK","PA","CA","DL","YO","HG","LS","WF","HD","S","DN","NG","PE","NR","IP"}
    prefix = ''.join(filter(str.isalpha, pc.split()[0]))
    if prefix in northern:
        return datetime.date(year, 4, 30)
    return datetime.date(year, 3, 31)

def _determine_planting_mode(plant: str) -> str:
    p = plant.lower().strip()
    if p in DIRECT_SOW_ONLY:
        return "direct_outdoor"
    if p in INDOOR_START_PLANTS:
        return "indoor_then_out"
    return "indoor_then_out"

def _chat(messages, json_mode=False, retries=MAX_RETRIES):
    """Make API call with retry logic."""
    body = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 1800,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=HEADERS,
                json=body,
                timeout=35,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(RETRY_DELAY)

def correct_plant_name(user_input: str) -> str:
    """Correct plant name using local map and optional API call."""
    user_input = user_input.lower().strip()
    # First check local map
    if user_input in PLANT_NAME_MAP:
        return PLANT_NAME_MAP[user_input]
    # Try API
    try:
        result = _chat([{
            "role": "user",
            "content": (
                f"Identify the common English name of this plant, correcting any typos: '{user_input}'. "
                "Respond with ONLY the corrected lowercase name, nothing else."
            ),
        }])
        return result.lower().strip()
    except Exception:
        # Return as is if API fails
        return user_input

def format_companions(data: dict) -> str:
    companions = "\n".join([f"- {c['plant']}: {c['reason']}" for c in data.get("companions", [])])
    avoid = "\n".join([f"- {c['plant']}: {c['reason']}" for c in data.get("avoid", [])])
    return f"Good companions:\n{companions or 'None'}\n\nAvoid:\n{avoid or 'None'}"

def generate_plan(
    user_input: str,
    postcode: str,
    planting_mode: str = "auto",
    actual_sow_date: datetime.date = None,
    actual_outdoor_date: datetime.date = None,
) -> dict:
    """
    Generate an AI planting plan, with retries and robust fallback.
    """
    from services.location_service import get_uk_location, get_weather
    from services.plant_services import get_botanical_data
    from services.companion_service import get_companions

    today = datetime.date.today()
    raw_plant = user_input.lower().strip()
    plant = correct_plant_name(raw_plant)
    if len(plant) > 30 or (" " not in plant and plant not in raw_plant):
        plant = raw_plant
    last_frost = _estimate_last_frost(postcode)

    if planting_mode == "auto":
        planting_mode = _determine_planting_mode(plant)

    # Recommended dates
    if planting_mode == "indoor_then_out":
        recommended_indoor = last_frost - datetime.timedelta(weeks=7)
        recommended_outdoor = last_frost + datetime.timedelta(days=14)
    else:
        recommended_indoor = None
        recommended_outdoor = last_frost + datetime.timedelta(days=14)

    anchor_indoor = actual_sow_date or recommended_indoor
    anchor_outdoor = actual_outdoor_date or recommended_outdoor or today

    # Context
    location_data = get_uk_location(postcode) or {}
    weather_data = None
    if location_data:
        weather_data = get_weather(location_data["lat"], location_data["lon"])
    plant_data = get_botanical_data(plant) or {
        "sunlight": ["Full Sun"], "watering": "Moderate", "cycle": "Annual"
    }
    companion_data = get_companions(plant)

    mode_desc = {
        "indoor_then_out": f"Start seeds INDOORS around {anchor_indoor.strftime('%d %B') if anchor_indoor else 'Feb/Mar'}, transplant OUTDOORS around {anchor_outdoor.strftime('%d %B')}.",
        "direct_outdoor": f"Sow DIRECTLY OUTDOORS around {anchor_outdoor.strftime('%d %B')}. Do NOT include indoor sowing.",
    }[planting_mode]

    prompt = f"""You are an RHS UK gardening expert.

Plant: {plant}
UK Postcode: {postcode} | Region: {location_data.get('region','UK')}
Planting Mode: {planting_mode} — {mode_desc}
Last estimated frost date: {last_frost.strftime('%d %B')}
Outdoor planting anchor date: {anchor_outdoor.strftime('%d %B %Y')}
Botanical Data: {json.dumps(plant_data)}
Current Weather: {json.dumps(weather_data)}
Companions: {format_companions(companion_data)}

Return STRICT JSON only — no markdown, no explanation:
{{
  "plant_name": "{plant}",
  "planting_mode": "{planting_mode}",
  "indoor_sow_instructions": "string — what to do indoors (null if direct_outdoor)",
  "outdoor_instructions": "string — what to do when planting/sowing outside",
  "care_instructions": "2-3 sentence care summary",
  "companion_advice": "1-2 sentence companion planting advice",
  "timeline": [
    {{"task": "Sow indoors", "start_month": 2, "end_month": 3}},
    {{"task": "Transplant outdoors", "start_month": 4, "end_month": 5}},
    {{"task": "Water regularly", "start_month": 4, "end_month": 9}},
    {{"task": "Harvest", "start_month": 7, "end_month": 10}}
  ],
  "tasks": [
    {{
      "task": "task name",
      "frequency": "daily|every_3_days|weekly|fortnightly|monthly|once",
      "start_offset_days": 0,
      "duration_days": 90,
      "phase": "indoor|outdoor|both",
      "notes": "brief tip"
    }}
  ]
}}

STRICT TASK RULES (must follow exactly):
1. frequency MUST be one of: ["daily","every_3_days","weekly","fortnightly","monthly","once"]
2. start_offset_days: integer, indoor tasks NEGATIVE, outdoor tasks >=0
3. duration_days: positive integer; "once" tasks have duration_days=1
4. phase: "indoor","outdoor","both"
5. REQUIRED TASKS: Sowing, Watering, Fertilising, Pest check, Harvesting. Add Transplanting and Hardening off if indoor_then_out.
6. For ornamental plants (flowers like hyacinth, tulip), produce a simplified plan with watering, fertilising, and harvesting of blooms.
7. Keep tasks practical for UK climate.
"""

    try:
        raw = _chat([{"role": "user", "content": prompt}], json_mode=True)
        plan_data = json.loads(raw)
    except Exception as e:
        # Return minimal plan so dashboard can use its fallback
        return {
            "error": "AI generation failed",
            "details": str(e),
            "plant_name": plant,
            "tasks": [],
            "timeline": [],
            "care_instructions": f"Care for {plant} in UK climate: water regularly, protect from frost.",
            "companion_advice": "Marigolds and nasturtiums are good companions for most plants.",
            "recommended_indoor": recommended_indoor.isoformat() if recommended_indoor else None,
            "recommended_outdoor": recommended_outdoor.isoformat() if recommended_outdoor else None,
            "actual_sow_date": anchor_indoor.isoformat() if anchor_indoor else None,
            "actual_outdoor_date": anchor_outdoor.isoformat(),
            "last_frost": last_frost.isoformat(),
        }

    # Merge dates
    plan_data["plant_name"] = plant
    plan_data["planting_mode"] = planting_mode
    plan_data["recommended_indoor"] = recommended_indoor.isoformat() if recommended_indoor else None
    plan_data["recommended_outdoor"] = recommended_outdoor.isoformat() if recommended_outdoor else None
    plan_data["actual_sow_date"] = anchor_indoor.isoformat() if anchor_indoor else None
    plan_data["actual_outdoor_date"] = anchor_outdoor.isoformat()
    plan_data["last_frost"] = last_frost.isoformat()

    if "tasks" not in plan_data:
        plan_data["tasks"] = []

    return plan_data