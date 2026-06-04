"""
1_Dashboard.py — SeedSage Dashboard (Final)
- Search filter removed
- Modal shows next 7 days of tasks only
- Clear conversation button in sidebar
"""

import streamlit as st
import datetime
import uuid
import re
import difflib
from collections import defaultdict

st.set_page_config(page_title="SeedSage | Dashboard", page_icon="🌿", layout="wide")

# ── Auth guard ──────────────────────────────────────────────
if "user" not in st.session_state or not st.session_state.user:
    st.warning("Please login first.")
    st.switch_page("app.py")

# ── Imports ────────────────────────────────────────────────
from utils.user_db import init_user_db, save_user
from utils.llm import generate_plan, _chat
from utils.smart_tasks import (
    generate_task_events, apply_weather_rules,
    TASK_CATEGORIES, get_growth_stage, generate_insights,
    adjust_plan_for_reality, reschedule_missed_tasks
)
from utils.achievements import update_achievements
from services.location_service import get_uk_location, get_weather, get_weather_forecast, get_last_frost_date
from services.plant_image_service import get_plant_emoji, get_plant_color
from services.plant_services import get_plant_guide
from services.gardening_agent import run_agent

# ── Initialise ─────────────────────────────────────────────
init_user_db()
user = st.session_state.user
today = datetime.date.today()
last_frost = get_last_frost_date(user["postcode"])

for k, v in [
    ("task_checked", {}),
    ("dashboard_week_offset", 0),
    ("selected_plant", None),
    ("agent_session_id", f"sess_{uuid.uuid4().hex[:8]}"),
    ("chat_history", []),
]:
    st.session_state.setdefault(k, v)

def save_current_user():
    save_user(st.session_state.user)

def to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    return None

# ── Plant name correction & date extraction ────────────────
KNOWN_PLANTS = [
    "tomato", "basil", "carrot", "lettuce", "cucumber", "pepper", "onion", "garlic",
    "potato", "strawberry", "raspberry", "blueberry", "courgette", "aubergine",
    "chilli", "mint", "rosemary", "thyme", "parsley", "coriander", "dill", "sage",
    "oregano", "marigold", "sunflower", "nasturtium", "borage", "lavender", "hyacinth",
    "tulip", "daffodil", "broccoli", "cauliflower", "cabbage", "kale", "spinach",
    "radish", "beetroot", "turnip", "parsnip", "leek", "shallot", "celery", "fennel"
]

def correct_plant_name(name: str) -> str:
    name = name.lower().strip()
    # Remove trailing time phrases from agent
    time_phrases = r'\s+(?:a month ago|two weeks ago|2 weeks ago|last week|a week ago|yesterday|today)$'
    name = re.sub(time_phrases, '', name)
    if name.endswith("s") and name[:-1] in KNOWN_PLANTS:
        name = name[:-1]
    if name not in KNOWN_PLANTS:
        matches = difflib.get_close_matches(name, KNOWN_PLANTS, n=1, cutoff=0.7)
        if matches:
            name = matches[0]
    return name

def extract_date_from_text(text: str) -> datetime.date | None:
    text = text.lower()
    match = re.search(r"(\d+)\s+day[s]?\s+ago", text)
    if match:
        return today - datetime.timedelta(days=int(match.group(1)))
    match = re.search(r"(\d+)\s+week[s]?\s+ago", text)
    if match:
        return today - datetime.timedelta(weeks=int(match.group(1)))
    match = re.search(r"(\d+)\s+month[s]?\s+ago", text)
    if match:
        return today - datetime.timedelta(days=int(match.group(1)) * 30)
    if "last week" in text:
        return today - datetime.timedelta(days=7)
    if "yesterday" in text:
        return today - datetime.timedelta(days=1)
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(days):
        if f"last {day}" in text:
            diff = (today.weekday() - i) % 7
            if diff == 0:
                diff = 7
            return today - datetime.timedelta(days=diff)
    return None

# ── Weather and forecast ───────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def load_weather():
    loc = get_uk_location(user["postcode"])
    if not loc:
        return None, None
    wx = get_weather(loc["lat"], loc["lon"])
    fc = get_weather_forecast(loc["lat"], loc["lon"])
    return wx, fc

wx, fc = load_weather()

# ── Helper to get plant stage with icon ─────────────────────
STAGE_ICONS = {
    "seedling": "🌱",
    "vegetative": "🌿",
    "flowering": "🌸",
    "fruiting": "🍅",
    "harvest": "🧺",
}

def get_plant_stage(plant_name: str, plan: dict, planted_date: datetime.date, total_days: int) -> tuple[str, str]:
    if plan:
        stage = get_growth_stage(plant_name, plan)
    else:
        days_passed = max(0, (today - planted_date).days)
        if days_passed <= 14:
            stage = "seedling"
        elif days_passed <= 40:
            stage = "vegetative"
        elif days_passed <= 70:
            stage = "flowering"
        elif days_passed <= 110:
            stage = "fruiting"
        else:
            stage = "harvest"
    icon = STAGE_ICONS.get(stage, "☘️")
    return stage, icon

# ── Achievements (update on each load) ─────────────────────
achievements = update_achievements(user)

# ── Auto-fix past tasks on existing plans ─────────────────
_plans_dirty = False
for _p_name, _plan in user.get("plans", {}).items():
    for _ev in _plan.get("task_events", []):
        _d = _ev.get("date")
        if isinstance(_d, str):
            try:
                _d = datetime.date.fromisoformat(_d)
            except Exception:
                continue
        if isinstance(_d, datetime.date) and _d < today and _ev.get("status") in ("scheduled", "rescheduled"):
            _ev["status"] = "done"
            _ev["reason"] = "✅ Completed (backdated plan)"
            _plans_dirty = True
if _plans_dirty:
    save_current_user()

# ── Compute garden statistics ──────────────────────────────
plant_count = len(user["plants"])
planned_count = len(user.get("plans", {}))
due_today_count = sum(
    1 for plan in user.get("plans", {}).values()
    for ev in plan.get("task_events", [])
    if ev.get("status") not in ("done", "skipped")
    and to_date(ev.get("date")) == today
)
completed_tasks = sum(
    1 for plan in user.get("plans", {}).values()
    for ev in plan.get("task_events", [])
    if ev.get("status") == "done"
)

# ── Harvest alerts ─────────────────────────────────────────
harvest_alerts = []
for p_name, p_data in user["plants"].items():
    guide = get_plant_guide(p_name)
    total_days = guide.get("days_to_maturity", 90)
    planted = to_date(p_data.get("actual_planted") or p_data.get("added_on")) or today
    days_left = max(0, total_days - (today - planted).days)
    if 0 <= days_left <= 7:
        harvest_alerts.append(f"🌾 {p_name.capitalize()} ready in {days_left}d")

# ── Dynamic hero subtitle based on weather ─────────────────
weather_desc = wx.get("description", "clear").lower() if wx else "clear"
if "sun" in weather_desc or "clear" in weather_desc:
    hero_subtitle_msg = "Perfect day for planting 🌱"
elif "rain" in weather_desc or "drizzle" in weather_desc:
    hero_subtitle_msg = "Keep an eye on moisture 💧"
else:
    hero_subtitle_msg = "Your garden is growing 🌻"

# ── CSS (unchanged) ─────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap');

:root {{
    --bg: #f5f8f3;
    --card: rgba(255,255,255,0.92);
    --line: #e3eadf;
    --text: #18311d;
    --muted: #6b766d;
    --green: #2e7d32;
    --green2: #66bb6a;
}}

.stApp {{
    background: radial-gradient(circle at top left, rgba(102,187,106,0.10), transparent 28%),
                radial-gradient(circle at top right, rgba(46,125,50,0.08), transparent 26%),
                linear-gradient(180deg, #f8faf6 0%, #f3f7f0 100%);
    font-family: 'DM Sans', sans-serif;
    color: var(--text);
}}

h1,h2,h3,h4 {{ font-family: 'Lora', serif !important; letter-spacing: -0.02em; }}
section[data-testid="stSidebar"] {{ background: rgba(255,255,255,0.92) !important; border-right: 1px solid var(--line); backdrop-filter: blur(10px); }}

.hero {{
    background: linear-gradient(135deg, #2e7d32, #66bb6a);
    border-radius: 24px;
    padding: 26px;
    margin-bottom: 1.5rem;
    color: white;
    box-shadow: 0 18px 40px rgba(0,0,0,0.12);
}}
.hero-title {{ font-size: 2.2rem; font-weight: 700; margin: 0; }}
.hero-subtitle {{ color: rgba(255,255,255,0.85); margin-top: 6px; }}

.stat-card {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 14px;
    text-align: center;
    backdrop-filter: blur(8px);
}}
.stat-label {{ color: var(--muted); font-size: 0.78rem; margin-bottom: 4px; }}
.stat-value {{ font-size: 1.15rem; font-weight: 700; }}

.sec-hdr {{
    color: var(--green); font-family: 'Lora', serif;
    font-size: 1.05rem; font-weight: 700;
    margin: 1rem 0 0.65rem;
    border-bottom: 2px solid #e8f5e9;
    padding-bottom: 5px;
}}

.planter-card {{
    background: var(--card);
    border-radius: 20px;
    border: 1px solid var(--line);
    padding: 14px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.04);
    transition: all 0.22s ease;
    position: relative;
    overflow: hidden;
    animation: fadeIn 0.4s ease;
}}
.planter-card::after {{
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at top, var(--plant-color, #2e7d32), transparent 70%);
    opacity: 0.15;
    pointer-events: none;
}}
.planter-card:hover {{ transform: translateY(-4px); box-shadow: 0 14px 30px rgba(0,0,0,0.08); border-color: #d6e5d0; }}
.planter-emoji {{ font-size: 42px; margin-bottom: 6px; }}
.planter-name {{ font-weight: 700; font-size: 1rem; color: var(--text); }}
.planter-meta {{ font-size: 0.76rem; color: var(--muted); margin-top: 2px; }}
.planter-chip {{
    display: inline-block; margin-top: 8px; padding: 4px 9px;
    border-radius: 999px; background: #edf7ee; color: var(--green);
    font-size: 0.70rem; font-weight: 700;
}}
.planter-progress {{ margin: 10px 0 8px; }}
.prog-track-sm {{
    position: relative; background: #eaf0e7; border-radius: 999px; height: 10px; overflow: hidden;
}}
.prog-track-sm::after, .prog-track-sm::before {{
    content: ''; position: absolute; top: 0; width: 2px; height: 100%;
    background: rgba(255,255,255,0.6); z-index: 1;
}}
.prog-track-sm::after {{ left: 25%; }}
.prog-track-sm::before {{ left: 75%; }}
.prog-fill-sm {{
    height: 10px; border-radius: 999px;
    background: linear-gradient(90deg, #2e7d32, #66bb6a);
    width: 0%;
    animation: fillBar 1.1s ease forwards;
}}
@keyframes fillBar {{ from {{ width: 0%; }} to {{ width: var(--target-width); }} }}

.task-row {{
    background: rgba(255,255,255,0.85);
    border-left: 5px solid var(--green);
    border-radius: 14px;
    padding: 10px 12px;
    margin-bottom: 8px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.03);
    position: relative;
    transition: all 0.16s;
}}
.task-row::before {{
    content: "";
    position: absolute;
    left: 8px;
    top: 14px;
    width: 6px;
    height: 6px;
    background: #2e7d32;
    border-radius: 50%;
    opacity: 0.6;
}}
.task-row:hover {{ transform: translateX(2px); background: rgba(255,255,255,0.95); }}
.small-muted {{ color: var(--muted); font-size: 0.82rem; }}

.sidebar-badge {{
    background: linear-gradient(135deg, #f1f8e9, #e8f5e9);
    padding: 12px; border-radius: 14px; margin-bottom: 12px;
    border: 1px solid var(--line); transition: transform 0.2s;
}}
.sidebar-badge:hover {{ transform: translateY(-2px); }}
.achievement-item {{
    background: rgba(46,125,50,0.08);
    border-radius: 10px;
    padding: 6px 10px;
    margin: 6px 0;
    font-size: 0.72rem;
    color: #2e7d32;
}}
div.stButton > button {{
    border-radius: 8px; background: white; color: #2e7d32;
    border: 1px solid #c8e6c9; transition: all 0.15s;
}}
div.stButton > button:hover {{
    background: #2e7d32 !important; color: white !important;
    transform: scale(0.98);
}}
div.stButton > button:active {{
    transform: scale(0.96);
}}

@media (max-width: 768px) {{
    .hero-title {{ font-size: 1.45rem; }}
    .planter-card {{ min-height: 180px; }}
    .stat-card {{ padding: 12px; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 0.25rem; flex-wrap: wrap; }}
}}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div class='sidebar-badge'><div style='font-weight:800;color:#2e7d32;font-size:1.2rem;'>🌿 SeedSage</div><div style='font-size:0.82rem;color:#667066;'>Smart gardening assistant</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div style='color:#526055;font-size:0.9rem;margin-bottom:0.7rem;'>Hello, {user['name']} 👋</div>", unsafe_allow_html=True)
    st.page_link("pages/1_Dashboard.py", label="📊 Dashboard", width='stretch')
    st.page_link("pages/2_Calendar.py", label="🗓️ Calendar", width='stretch')
    st.page_link("pages/3_Companions.py", label="🌻 Companions", width='stretch')
    st.page_link("pages/4_GardenJournal.py", label="📓 Journal", width='stretch')
    st.divider()

    if wx:
        st.markdown(f"**📍 {user['postcode']}**")
        st.metric("🌡️ Temperature", f"{wx.get('temp', '--')}°C")
        st.metric("💧 Humidity", f"{wx.get('humidity', '--')}%")
        st.caption(wx.get("description", "").capitalize())
        st.caption(f"📅 Last frost: {last_frost.strftime('%d %b')}")
    else:
        st.caption("No weather data")

    # Clear conversation button
    if st.button("🗑️ Clear conversation", width='stretch'):
        st.session_state.chat_history = []
        st.session_state.agent_session_id = f"sess_{uuid.uuid4().hex[:8]}"
        st.success("Conversation cleared!")
        st.rerun()

# ── Header ─────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <div class="hero-title">🌿 Garden Dashboard</div>
    <div class="hero-subtitle">{today.strftime('%A, %d %B %Y')} • {hero_subtitle_msg}</div>
</div>
""", unsafe_allow_html=True)

# ── Summary stats ─────────────────────────────────────────
stats_cols = st.columns(4)
stats_vals = [
    ("🌱 Plants", plant_count),
    ("📋 Planned", planned_count),
    ("📅 Due Today", due_today_count),
    ("❄️ Frost", last_frost.strftime("%d %b") if last_frost else "--"),
]
for col, (label, value) in zip(stats_cols, stats_vals):
    with col:
        st.markdown(f"""
        <div class='stat-card'>
            <div class='stat-label'>{label}</div>
            <div class='stat-value'>{value}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)

# ── Harvest alerts banner ─────────────────────────────────
if harvest_alerts:
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #66bb6a, #81c784);
        color: white;
        padding: 12px 16px;
        border-radius: 16px;
        font-weight: 600;
        margin-bottom: 16px;
    ">
        {' • '.join(harvest_alerts)}
    </div>
    """, unsafe_allow_html=True)

# ── Monthly Advisor button ────────────────────────────────
if st.button("✨ Get Advice for This Month", width='stretch'):
    plant_list = list(user["plants"].keys()) or ["no plants yet"]
    prompt = f"""UK gardening expert. Plants in garden: {', '.join(plant_list)}. Month: {today.strftime('%B')}. Give:
- What to plant
- What to harvest
- 2–3 key actions
Keep it short (max 60 words)."""
    with st.spinner("Asking expert…"):
        advice = _chat([{"role": "user", "content": prompt}])
    st.info(advice)
else:
    st.caption("Click the button above for monthly advice.")

# ── Add Plant (simplified, no search filter) ──────────────
left, right = st.columns([4, 1])
with left:
    new_plant_name = st.text_input("Plant name", label_visibility="collapsed", placeholder="e.g. tomato, basil...")
with right:
    if st.button("Add Plant", width='stretch'):
        if new_plant_name:
            plant = correct_plant_name(new_plant_name)
            if plant not in user["plants"]:
                user["plants"][plant] = {
                    "added_on": today,
                    "actual_planted": today.isoformat(),
                    "milestones": []
                }
                save_current_user()
                st.toast(f"Added {plant.capitalize()} 🌱")
                st.rerun()
            else:
                st.warning("Already in garden.")

# ── My Plants – cards with urgency icons ──────────────────
st.markdown("<div class='sec-hdr'>🌱 My Plants</div>", unsafe_allow_html=True)

if not user["plants"]:
    st.info("Your garden is empty. Add a plant above 🌱")
else:
    # Display all plants (no filter)
    plant_items = list(user["plants"].items())
    rows = [plant_items[i:i + 3] for i in range(0, len(plant_items), 3)]
    for row in rows:
        cols = st.columns(3)
        for idx in range(3):
            with cols[idx]:
                if idx < len(row):
                    p_name, p_data = row[idx]
                    if "added_on" not in p_data:
                        p_data["added_on"] = today
                    if isinstance(p_data["added_on"], str):
                        p_data["added_on"] = datetime.date.fromisoformat(p_data["added_on"])

                    guide = get_plant_guide(p_name)
                    total_days = guide.get("days_to_maturity", 90)
                    planted = to_date(p_data.get("actual_planted") or p_data.get("added_on")) or today
                    days_passed = (today - planted).days
                    progress = min(100, max(0, int((days_passed / total_days) * 100)))
                    days_left = max(0, total_days - days_passed)
                    emoji = get_plant_emoji(p_name)
                    bg_color = get_plant_color(p_name)
                    plan = user["plans"].get(p_name, {})
                    stage_text, stage_icon = get_plant_stage(p_name, plan, planted, total_days)

                    urgency = "🔥" if days_left <= 5 else "⏳" if days_left <= 10 else ""

                    if st.button(f"{emoji} {p_name.capitalize()}", key=f"open_{p_name}", width='stretch'):
                        st.session_state.selected_plant = p_name
                        st.rerun()

                    watering_short = guide.get("watering", "").split(".")[0] + "."

                    st.markdown(f"""
                    <div class="planter-card" style="--plant-color:{bg_color};">
                        <div class="planter-emoji">{emoji}</div>
                        <div class="planter-name">{p_name.capitalize()}</div>
                        <div class="planter-chip">{stage_icon} {stage_text}</div>
                        <div class="planter-meta">{urgency} {days_left} days to harvest</div>
                        <div class="planter-progress">
                            <div class="prog-track-sm">
                                <div class="prog-fill-sm" style="--target-width:{progress}%; background:{bg_color};"></div>
                            </div>
                        </div>
                        <div style="font-size:0.72rem;color:#555;margin-top:6px;">
                            💧 {watering_short}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        if p_name not in user["plans"]:
                            if st.button("Plan", key=f"plan_{p_name}", width='stretch'):
                                with st.spinner(f"Planning {p_name.capitalize()}…"):
                                    plan_data = generate_plan(p_name, user["postcode"])
                                    if "error" not in plan_data:
                                        plan_data = adjust_plan_for_reality(plan_data)
                                        events = generate_task_events(
                                            plan_data.get("tasks", []),
                                            outdoor_anchor=planted,
                                            indoor_anchor=planted - datetime.timedelta(weeks=7),
                                            last_frost_date=last_frost
                                        )
                                        if fc:
                                            events = apply_weather_rules(events, fc)
                                        events = reschedule_missed_tasks(events)
                                        plan_data["task_events"] = events
                                    user["plans"][p_name] = plan_data
                                    save_current_user()
                                    st.success("Plan created!")
                                    st.rerun()
                        else:
                            st.markdown("<div style='text-align:center;font-size:0.75rem;color:#2e7d32;'>✅ Planned</div>", unsafe_allow_html=True)
                    with c2:
                        if st.button("🗑️", key=f"del_{p_name}", width='stretch'):
                            del user["plants"][p_name]
                            user["plans"].pop(p_name, None)
                            if st.session_state.get("selected_plant") == p_name:
                                st.session_state.selected_plant = None
                            save_current_user()
                            st.rerun()
                else:
                    st.empty()

# ── Modal (plant details) – deduplicated tasks, next 7 days only ───
def show_plant_modal(plant_name: str):
    p_data = user["plants"].get(plant_name, {})
    guide = get_plant_guide(plant_name)
    planted = to_date(p_data.get("actual_planted") or p_data.get("added_on")) or today
    total_days = guide.get("days_to_maturity", 90)
    days_passed = max(0, (today - planted).days)
    progress = min(100, max(0, int((days_passed / total_days) * 100)))
    days_left = max(0, total_days - days_passed)
    plan = user["plans"].get(plant_name, {})
    stage_text, stage_icon = get_plant_stage(plant_name, plan, planted, total_days)
    emoji = get_plant_emoji(plant_name)
    bg_color = get_plant_color(plant_name)
    tasks = plan.get("task_events", [])

    # Filter tasks: only those due in the next 7 days (today <= date <= today+7)
    cutoff = today + datetime.timedelta(days=7)
    upcoming_map = {}
    for ev in tasks:
        if ev.get("status") in ("done", "skipped"):
            continue
        d = to_date(ev.get("date"))
        if not d:
            continue
        if d < today or d > cutoff:
            continue
        title = ev.get("title", "Task")
        key = (title, d)
        if key not in upcoming_map:
            upcoming_map[key] = {
                "title": title,
                "date": d,
                "icon": TASK_CATEGORIES.get(ev.get("category", "general"), {}).get("icon", "📋"),
                "category": ev.get("category", "general"),
            }
    upcoming_tasks = sorted(upcoming_map.values(), key=lambda x: x["date"])

    st.markdown(f"### {emoji} {plant_name.capitalize()}")
    st.caption(f"Planted on {planted.strftime('%d %b %Y')} · {stage_icon} {stage_text}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Days to harvest", days_left)
    c2.metric("Progress", f"{progress}%")
    c3.metric("Plan", "Ready" if plant_name in user["plans"] else "Missing")

    st.markdown(f"""
    <div style="margin:8px 0 12px;">
        <div class="prog-track-sm">
            <div class="prog-fill-sm" style="--target-width:{progress}%; background:{bg_color};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("**Care notes**")
    if guide.get("watering"):
        st.markdown(f"💧 **Watering:** {guide['watering']}")
    if guide.get("sunlight"):
        st.markdown(f"☀️ **Sunlight:** {guide['sunlight']}")
    if guide.get("fertilising"):
        st.markdown(f"🌱 **Fertilising:** {guide['fertilising']}")
    if guide.get("pruning"):
        st.markdown(f"✂️ **Pruning:** {guide['pruning']}")
    if guide.get("companions"):
        st.markdown(f"🤝 **Companions:** {guide['companions']}")
    if guide.get("uk_notes"):
        st.info(f"🇬🇧 **UK tip:** {guide['uk_notes']}")

    if upcoming_tasks:
        st.write("**Next tasks (next 7 days)**")
        for ev in upcoming_tasks:
            d_str = ev["date"].strftime("%d %b") if ev["date"] else "Soon"
            st.markdown(f"- {ev['icon']} {ev['title']} · {d_str}")
    else:
        st.caption("No upcoming tasks in the next 7 days.")

    d1, d2 = st.columns(2)
    with d1:
        if plant_name not in user["plans"]:
            if st.button("Generate plan", key=f"modal_plan_{plant_name}", width='stretch'):
                with st.spinner(f"Planning {plant_name.capitalize()}…"):
                    plan_data = generate_plan(plant_name, user["postcode"])
                    if "error" not in plan_data:
                        plan_data = adjust_plan_for_reality(plan_data)
                        events = generate_task_events(
                            plan_data.get("tasks", []),
                            outdoor_anchor=planted,
                            indoor_anchor=planted - datetime.timedelta(weeks=7),
                            last_frost_date=last_frost
                        )
                        if fc:
                            events = apply_weather_rules(events, fc)
                        events = reschedule_missed_tasks(events)
                        plan_data["task_events"] = events
                    user["plans"][plant_name] = plan_data
                    save_current_user()
                    st.toast(f"Plan created for {plant_name.capitalize()} 🌿")
                    st.rerun()
        else:
            st.button("Plan already created", width='stretch', disabled=True)

    with d2:
        if st.button("Close", width='stretch'):
            st.session_state.selected_plant = None
            st.session_state.just_closed_modal = True
            st.rerun()

if st.session_state.selected_plant and st.session_state.selected_plant in user["plants"]:
    @st.dialog(f"{get_plant_emoji(st.session_state.selected_plant)} {st.session_state.selected_plant.capitalize()}")
    def plant_dialog():
        show_plant_modal(st.session_state.selected_plant)
    plant_dialog()

if st.session_state.pop("just_closed_modal", False):
    st.markdown(
        "<script>setTimeout(()=>{const c=document.createElement('div');c.innerHTML='🎉';c.style.cssText='position:fixed;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:999999;font-size:64px;animation:fadeOut 900ms ease forwards;';document.body.appendChild(c);setTimeout(()=>c.remove(),900);}, 0);</script><style>@keyframes fadeOut{0%{opacity:1;transform:translateY(0) scale(1)}100%{opacity:0;transform:translateY(-18px) scale(1.2)}}</style>",
        unsafe_allow_html=True
    )

# ── Ask SeedSage (unchanged) ───────────────────────────────
st.divider()
st.subheader("🤖 Ask SeedSage")

def generate_plan_for_plant(plant_name: str, plant_data: dict) -> bool:
    anchor_str = plant_data.get("actual_planted") or plant_data.get("added_on")
    anchor_date = to_date(anchor_str) or today
    guide = get_plant_guide(plant_name)
    days_to_maturity = guide.get("days_to_maturity", 75)

    try:
        res = generate_plan(plant_name, user["postcode"], actual_sow_date=anchor_date, actual_outdoor_date=anchor_date)
        if "error" in res or not res.get("tasks"):
            raise ValueError
    except Exception:
        res = {"plant_name": plant_name, "tasks": [], "task_events": []}

    tasks = res.get("tasks", [])
    if not tasks:
        return False

    delta = (anchor_date - today).days
    shifted = [{**t, "start_offset_days": t.get("start_offset_days", 0) + delta} for t in tasks]
    events = generate_task_events(
        shifted, outdoor_anchor=anchor_date,
        indoor_anchor=anchor_date - datetime.timedelta(weeks=7),
        last_frost_date=last_frost
    )
    if events and fc:
        events = apply_weather_rules(events, fc)
    events = reschedule_missed_tasks(events)   # now works because function returns a list
    res["task_events"] = events or []
    user["plans"][plant_name] = res
    save_current_user()
    return True

def process_user_message(msg):
    with st.spinner("🌿 SeedSage is thinking..."):
        response, actions = run_agent(msg, user, st.session_state.agent_session_id)

    # Debug print
    print(f"[DEBUG] Actions received: {actions}")

    needs_rerun = False

    for action in actions:
        if action.get("action") == "add_plant":
            plant = correct_plant_name(action.get("plant_name", ""))
            if plant and plant not in user["plants"]:
                planted_date = action.get("planted_date")
                if planted_date:
                    try:
                        planted_date = datetime.date.fromisoformat(planted_date)
                    except:
                        planted_date = today
                else:
                    planted_date = extract_date_from_text(msg) or today
                user["plants"][plant] = {
                    "added_on": planted_date,
                    "actual_planted": planted_date.isoformat(),
                    "milestones": []
                }
                save_current_user()
                st.success(f"✅ Added **{plant.capitalize()}** planted on {planted_date.strftime('%d %b %Y')}!")
                if "plan" in msg.lower():
                    generate_plan_for_plant(plant, user["plants"][plant])
                    st.success(f"📋 Plan created for **{plant.capitalize()}**!")
                needs_rerun = True
            else:
                st.warning(f"Plant '{plant}' already exists or invalid.")

        elif action.get("action") == "schedule_plan":
            plant = correct_plant_name(action.get("plant_name", ""))
            if plant in user["plants"]:
                if plant not in user["plans"]:
                    generate_plan_for_plant(plant, user["plants"][plant])
                    st.success(f"📋 Plan generated for **{plant.capitalize()}**!")
                else:
                    st.info(f"Plan for {plant.capitalize()} already exists.")
            else:
                st.warning(f"Plant '{plant}' not found in your garden. Add it first.")
            needs_rerun = True

        elif action.get("action") == "remove_plant":
            plant = correct_plant_name(action.get("plant_name", ""))
            matched = None
            for existing in user["plants"].keys():
                if existing.lower() == plant or existing.lower() == plant + "s" or plant + "s" == existing.lower():
                    matched = existing
                    break
            if matched:
                del user["plants"][matched]
                user["plans"].pop(matched, None)
                save_current_user()
                st.success(f"🗑️ Removed **{matched.capitalize()}**!")
                needs_rerun = True
            else:
                st.warning(f"Plant '{plant}' not found in your garden.")

    if needs_rerun:
        st.rerun()

    return response

if user["plants"]:
    plant_for_example = st.selectbox(
        "Choose a plant for example questions",
        options=list(user["plants"].keys()),
        index=0,
        key="ex_plant"
    )
else:
    plant_for_example = "tomato"

example_questions = [
    "What are the care requirements for {plant}?",
    "How often should I water {plant}?",
    "When should I plant {plant}?",
    "What are good companion plants for {plant}?",
]

st.markdown("**Try asking:**")
ex_cols = st.columns(len(example_questions))
for i, q_template in enumerate(example_questions):
    filled_q = q_template.replace("{plant}", plant_for_example).replace("{plan}", plant_for_example)
    with ex_cols[i]:
        if st.button(f"💬 {filled_q}", key=f"ex_{i}_{plant_for_example}", width='stretch'):
            st.session_state.pending_example = filled_q
            st.rerun()

if "pending_example" in st.session_state:
    q = st.session_state.pop("pending_example")
    resp = process_user_message(q)
    st.session_state.chat_history.append({"q": q, "a": resp})
    st.rerun()

user_msg = st.chat_input("Ask anything about your garden...")
if user_msg:
    resp = process_user_message(user_msg)
    st.session_state.chat_history.append({"q": user_msg, "a": resp})
    st.rerun()

for chat in st.session_state.get("chat_history", [])[-10:]:
    st.chat_message("user").write(chat["q"])
    st.chat_message("assistant").write(chat["a"])