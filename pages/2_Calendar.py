"""
2_Calendar.py — SeedSage Calendar (Final)
Fully deduplicated tasks – no per‑plant duplicate events.
Semantic title normalisation merges "Pest check" / "Check for pests", etc.
Due today count shows unique task types, not per‑plant duplicates.
"""

import streamlit as st
import datetime
import calendar as cal_module
from icalendar import Calendar as iCalendar, Event as iCalEvent
from collections import defaultdict

st.set_page_config(page_title="SeedSage | Calendar", page_icon="🗓️", layout="wide")

if "user" not in st.session_state or not st.session_state.user:
    st.warning("Please login first.")
    st.switch_page("app.py")

from utils.user_db import save_user
from utils.smart_tasks import TASK_CATEGORIES, get_date_ranges, classify_task
from services.plant_services import get_plant_guide
from services.location_service import get_weather_forecast, get_uk_location

user = st.session_state.user
today = datetime.date.today()

# ---------- Session state ----------
if "cal_view" not in st.session_state:
    st.session_state.cal_view = "Month"
if "cal_off" not in st.session_state:
    st.session_state.cal_off = 0
if "wk_off" not in st.session_state:
    st.session_state.wk_off = 0
if "done_tasks" not in st.session_state:
    st.session_state.done_tasks = set()

def save_current():
    save_user(st.session_state.user)

def to_date(v):
    if v is None:
        return None
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        try:
            return datetime.date.fromisoformat(v)
        except:
            return None
    return None

def safe_task_key(plant: str, task_id: str) -> str:
    return f"{plant}::{task_id}"

# ---------- Title normalisation (merge synonyms) ----------
TITLE_NORMALISATION = {
    # Pest checks
    "pest check": "Pest check",
    "check for pests": "Pest check",
    "pest inspection": "Pest check",
    # Watering
    "watering": "Watering",
    "water": "Watering",
    "water outdoors": "Watering",
    # Fertilising
    "fertilising": "Fertilising",
    "fertilise": "Fertilising",
    "fertilize": "Fertilising",
    "fertilise outdoors": "Fertilising",
    "fertilizing outdoors": "Fertilising",
    # Sowing
    "sowing": "Sowing",
    "sow": "Sowing",
    # Transplanting
    "transplanting": "Transplanting",
    "transplant": "Transplanting",
    # General
    "harvest": "Harvest",
    "pruning": "Pruning",
    "mulching": "Mulching",
}

def normalise_title(raw_title: str) -> str:
    """Return a canonical title for grouping semantically identical tasks."""
    lower = raw_title.strip().lower()
    return TITLE_NORMALISATION.get(lower, raw_title.strip().capitalize())

# ---------- Duplicate cleanup ----------
def cleanup_duplicate_tasks():
    """Remove duplicate task_events per plant. Keeps first occurrence."""
    changed = False
    for plant_name, plan in user.get("plans", {}).items():
        events = plan.get("task_events", [])
        if not events:
            continue
        seen = set()
        unique_events = []
        for ev in events:
            # Build key based on all meaningful fields (including normalised title)
            norm_title = normalise_title(ev.get("title", "Task"))
            key = (
                ev.get("date"),
                norm_title,
                ev.get("category"),
                ev.get("phase"),
                ev.get("notes", ""),
                ev.get("task_id", "")
            )
            if key not in seen:
                seen.add(key)
                # Optionally store normalised title back? Not needed, keep original.
                unique_events.append(ev)
            else:
                changed = True
        if len(unique_events) != len(events):
            plan["task_events"] = unique_events
    if changed:
        save_current()

def ensure_task_ids():
    changed = False
    for plant_name, plan in user.get("plans", {}).items():
        events = plan.get("task_events", [])
        for idx, ev in enumerate(events):
            if not ev.get("task_id"):
                ev["task_id"] = f"{plant_name}_{idx}_{ev.get('date', '')}_{ev.get('title', 'task')}"
                changed = True
    if changed:
        save_current()

# Run cleanup & ID generation once at startup
cleanup_duplicate_tasks()
ensure_task_ids()

@st.cache_data(ttl=1800, show_spinner=False)
def cached_loc(pc):
    return get_uk_location(pc)

@st.cache_data(ttl=1800, show_spinner=False)
def cached_fc(lat, lon):
    return get_weather_forecast(lat, lon)

loc = cached_loc(user["postcode"]) if user.get("postcode") else None
fc = cached_fc(loc["lat"], loc["lon"]) if loc else []

rain_today = any("rain" in f.get("description", "").lower() for f in fc[:4])
frost_today = any(f.get("temp", 99) < 2 for f in fc[:4])

# ---------- CSS (original theme) ----------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap');
.stApp { background:#f4f7f2; font-family:'DM Sans',sans-serif; }
h1,h2,h3,h4 { font-family:'Lora',serif !important; }
section[data-testid="stSidebar"] { background:white !important; border-right:1px solid #e6ede4; }

.hero {
    background: linear-gradient(135deg, rgba(46,125,50,0.10), rgba(102,187,106,0.08));
    border: 1px solid #e6ede4;
    border-radius: 22px;
    padding: 18px 20px;
    margin-bottom: 1rem;
}

.kpi-card {
    background:white;
    border:1px solid #e6ede4;
    border-radius:12px;
    padding:14px 18px;
    text-align:center;
}
.kpi-num  { font-size:1.8rem; font-weight:700; color:#2e7d32; line-height:1; }
.kpi-lbl  { font-size:0.72rem; color:#888; margin-top:3px; }

.cal-grid-hdr {
    text-align:center;
    font-size:0.7rem;
    font-weight:700;
    color:#888;
    padding:4px 0;
    letter-spacing:.05em;
}
.cal-cell {
    border:1px solid #eef2ec;
    border-radius:8px;
    padding:4px 5px;
    min-height:78px;
    background:white;
    margin:1px;
}
.cal-today {
    border:2px solid #2e7d32 !important;
    background:#f1f8f1 !important;
}
.cal-day-num {
    font-size:0.82rem;
    font-weight:600;
    color:#333;
    display:block;
    margin-bottom:2px;
}
.cal-today .cal-day-num { color:#2e7d32; }

.ev-pill {
    font-size:0.56rem;
    padding:1px 4px;
    border-radius:3px;
    color:white;
    margin-top:2px;
    display:block;
    overflow:hidden;
    white-space:nowrap;
    text-overflow:ellipsis;
}

.week-col {
    border:1px solid #eef2ec;
    border-radius:10px;
    background:white;
    padding:8px 6px;
    min-height:100px;
}
.week-col.today-col {
    border:2px solid #2e7d32;
    background:#f1f8f1;
}
.week-day-hdr {
    font-size:0.7rem;
    color:#888;
    text-align:center;
    margin-bottom:4px;
}
.week-day-num {
    font-size:1.1rem;
    font-weight:700;
    color:#333;
    text-align:center;
}
.today-col .week-day-num { color:#2e7d32; }

.agenda-row {
    display:flex;
    align-items:flex-start;
    gap:10px;
    padding:10px 0;
    border-bottom:1px solid #f0f0f0;
}
.agenda-content { flex:1; }
.agenda-title { font-size:0.88rem; font-weight:600; color:#1a1a1a; }
.agenda-meta  { font-size:0.72rem; color:#888; margin-top:2px; }

.phase-badge {
    display:inline-block;
    font-size:0.6rem;
    padding:1px 6px;
    border-radius:8px;
    color:white;
    margin-left:5px;
}
.phase-indoor  { background:#5c6bc0; }
.phase-outdoor { background:#2e7d32; }

.prog-row { margin:8px 0; }
.prog-label {
    display:flex;
    justify-content:space-between;
    font-size:0.78rem;
    margin-bottom:3px;
}
.prog-track {
    height:8px;
    background:#eef2ec;
    border-radius:10px;
    overflow:hidden;
}
.prog-fill {
    height:8px;
    border-radius:10px;
}

.task-card {
    background:white;
    border:1px solid #e6ede4;
    border-radius:10px;
    padding:10px 12px;
    margin-bottom:6px;
    display:flex;
    align-items:flex-start;
    gap:10px;
}
.task-card.done-card { opacity:0.45; }
.task-icon { font-size:1rem; margin-top:2px; flex-shrink:0; }
.task-title { font-size:0.88rem; font-weight:600; color:#1a1a1a; }
.task-meta  { font-size:0.72rem; color:#888; margin-top:2px; }

.legend-chip {
    display:inline-block;
    padding:2px 8px;
    border-radius:999px;
    font-size:0.68rem;
    margin-right:6px;
    margin-bottom:6px;
    color:white;
}

div.stButton > button {
    border-radius:8px;
    background:white;
    color:#2e7d32;
    border:1px solid #c8e6c9;
    transition: all 0.15s;
}
div.stButton > button:hover {
    background:#2e7d32 !important;
    color:white !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(
        "<div style='font-size:1.4rem;font-weight:700;color:#2e7d32;font-family:Lora,serif;'>🌿 SeedSage</div>",
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_Dashboard.py", label="📊 Dashboard", width='stretch')
    st.page_link("pages/2_Calendar.py", label="🗓️ Calendar", width='stretch')
    st.page_link("pages/3_Companions.py", label="🌻 Companions", width='stretch')
    st.page_link("pages/4_GardenJournal.py", label="📓 Journal", width='stretch')
    st.divider()

    st.markdown("**Filters**")
    plant_opts = ["All Plants"] + sorted(user.get("plans", {}).keys())
    sel_plant = st.selectbox("Plant", plant_opts, key="cal_plant_filter")
    cat_opts = ["All Categories"] + [v["label"] for v in TASK_CATEGORIES.values()]
    sel_cat = st.selectbox("Category", cat_opts, key="cal_cat_filter")

    st.divider()

    def build_ical():
        cal = iCalendar()
        cal.add("prodid", "-//SeedSage//Planting Calendar//EN")
        cal.add("version", "2.0")
        for pn, plan in user.get("plans", {}).items():
            for ev in plan.get("task_events", []):
                d = to_date(ev.get("date"))
                if not d or ev.get("status") in ("done", "skipped"):
                    continue
                ie = iCalEvent()
                title = ev.get("title", "Task")
                ie.add("summary", f"{pn.capitalize()}: {title}")
                ie.add("dtstart", d)
                ie.add("dtend", d + datetime.timedelta(days=1))
                ie.add("description", ev.get("reason", ""))
                ie.add("categories", [ev.get("category", "general")])
                if ev.get("task_id"):
                    ie.add("uid", f"{ev['task_id']}@seedsage")
                cal.add_component(ie)
        return cal.to_ical()

    st.download_button(
        "📅 Export iCal",
        data=build_ical(),
        file_name="seedsage_calendar.ics",
        mime="text/calendar",
        width='stretch',
    )

    st.markdown("**Legend**")
    legend_items = list(TASK_CATEGORIES.values())[:6]
    for item in legend_items:
        st.markdown(
            f"<span class='legend-chip' style='background:{item['color']};'>{item['icon']} {item['label']}</span>",
            unsafe_allow_html=True,
        )

# ---------- Event helpers with deduplication & normalisation ----------
def gather_events(plant_filter="All Plants", cat_filter="All Categories"):
    """Return deduplicated list of events (no duplicate task per plant)."""
    raw_events = []
    for pn, plan in user.get("plans", {}).items():
        if plant_filter != "All Plants" and pn != plant_filter:
            continue
        for idx, ev in enumerate(plan.get("task_events", [])):
            d = to_date(ev.get("date"))
            if not d:
                continue
            cat = ev.get("category", "general")
            cat_info = TASK_CATEGORIES.get(cat, TASK_CATEGORIES["general"])
            if cat_filter != "All Categories" and cat_info["label"] != cat_filter:
                continue
            task_id = ev.get("task_id") or f"{pn}_{idx}_{d.isoformat()}"
            raw_events.append({
                "plant": pn,
                "idx": idx,
                "task_id": task_id,
                "title_raw": ev.get("title", "Task"),
                "title": normalise_title(ev.get("title", "Task")),  # canonical for grouping
                "date": d,
                "status": ev.get("status", "scheduled"),
                "category": cat,
                "phase": ev.get("phase", "outdoor"),
                "notes": ev.get("notes", ""),
                "icon": cat_info["icon"],
                "color": cat_info["color"],
                "label": cat_info["label"],
            })

    # Deduplicate based on (plant, task_id) – strong uniqueness
    unique = {}
    for e in raw_events:
        key = (e["plant"], e["task_id"])
        if key not in unique:
            unique[key] = e
    out = list(unique.values())
    out.sort(key=lambda e: e["date"])
    return out

def is_done_event(e):
    key = safe_task_key(e["plant"], e["task_id"])
    return e["status"] == "done" or key in st.session_state.done_tasks

def mark_done(e):
    key = safe_task_key(e["plant"], e["task_id"])
    st.session_state.done_tasks.add(key)
    if e["plant"] in user.get("plans", {}) and 0 <= e["idx"] < len(user["plans"][e["plant"]].get("task_events", [])):
        user["plans"][e["plant"]]["task_events"][e["idx"]]["status"] = "done"
        save_current()

def reschedule_event(e, new_date):
    if e["plant"] in user.get("plans", {}) and 0 <= e["idx"] < len(user["plans"][e["plant"]].get("task_events", [])):
        user["plans"][e["plant"]]["task_events"][e["idx"]]["date"] = new_date.isoformat()
        save_current()

# Load events with current filters
all_events = gather_events(sel_plant, sel_cat)
active = [e for e in all_events if not is_done_event(e) and e["status"] not in ("done", "skipped")]
future = [e for e in active if e["date"] >= today]
due_today = [e for e in active if e["date"] == today]
overdue = [e for e in active if e["date"] < today]
done_events = [e for e in all_events if is_done_event(e)]

# Unique task types for today (normalised title, across plants)
unique_tasks_today = len({e["title"] for e in due_today})

# ---------- Hero & KPIs ----------
st.markdown(
    "<div class='hero'><h1 style='color:#2e7d32;margin:0;'>🗓️ Garden Calendar</h1><p style='color:#666;margin:0.3rem 0 0;'>Track sowing, transplanting, care tasks, and progress across your garden.</p></div>",
    unsafe_allow_html=True,
)
st.markdown(f"<p style='color:#888;margin-top:0;margin-bottom:1rem;'>{today.strftime('%A, %d %B %Y')}</p>", unsafe_allow_html=True)

if frost_today:
    st.warning("🥶 Frost risk tonight — protect tender plants and delay outdoor sowing.")
elif rain_today:
    st.info("🌧️ Rain expected — outdoor watering tasks can be skipped today.")

k1, k2, k3, k4 = st.columns(4)
next_ev = future[0] if future else None

def kpi(col, num, label, color="#2e7d32"):
    col.markdown(
        f"<div class='kpi-card'><div class='kpi-num' style='color:{color};'>{num}</div><div class='kpi-lbl'>{label}</div></div>",
        unsafe_allow_html=True,
    )

kpi(k1, unique_tasks_today, "task types due today", color="#f57c00" if unique_tasks_today else "#2e7d32")
kpi(k2, len(done_events), "completed ✓", color="#66bb6a")
kpi(k3, len(user.get("plants", {})), "plants")
kpi(k4, next_ev["date"].strftime("%d %b") if next_ev else "—", "next task")

if due_today:
    # Group by normalised title only (ignore phase)
    grouped = defaultdict(lambda: {"plants": set(), "icon": "", "color": ""})
    for e in due_today:
        title = e["title"]
        grouped[title]["plants"].add(e["plant"].capitalize())
        grouped[title]["icon"] = e["icon"]
        grouped[title]["color"] = e["color"]
    
    # Calculate total plant instances (sum of plant counts per title)
    total_plant_instances = sum(len(data["plants"]) for data in grouped.values())
    
    with st.expander(f"📅 {total_plant_instances} plant task(s) due today", expanded=True):
        for title, data in grouped.items():
            plants_str = ", ".join(sorted(data["plants"]))
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{data['icon']} **{title}:** {plants_str}")
            if c2.button("Done ✓", key=f"td_grp_{title.replace(' ', '_')}"):
                # Mark all events with this title as done
                for e in due_today:
                    if e["title"] == title:
                        mark_done(e)
                st.rerun()

st.divider()

top_left, top_right = st.columns([1, 1])
with top_left:
    if st.button("↩️ Today", width='stretch'):
        st.session_state.cal_off = 0
        st.session_state.wk_off = 0
        st.rerun()
with top_right:
    view = st.radio(
        "View",
        ["Month", "Week", "Progress"],
        horizontal=True,
        key="cal_view_radio",
        label_visibility="collapsed",
    )

# ---------- Month View ----------
if view == "Month":
    nav_l, nav_c, nav_r = st.columns([1, 4, 1])
    off = st.session_state.cal_off
    t_m = ((today.month - 1 + off) % 12) + 1
    t_y = today.year + ((today.month - 1 + off) // 12)

    with nav_l:
        if st.button("◀", key="m_prev"):
            st.session_state.cal_off -= 1
            st.rerun()
    with nav_r:
        if st.button("▶", key="m_next"):
            st.session_state.cal_off += 1
            st.rerun()
    with nav_c:
        st.markdown(
            f"<h3 style='text-align:center;margin:4px 0;color:#2e7d32;'>{cal_module.month_name[t_m]} {t_y}</h3>",
            unsafe_allow_html=True,
        )

    hcols = st.columns(7)
    for i, d in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        hcols[i].markdown(f"<div class='cal-grid-hdr'>{d}</div>", unsafe_allow_html=True)

    month_events = {}
    for e in all_events:
        if e["date"].year == t_y and e["date"].month == t_m:
            month_events.setdefault(e["date"].isoformat(), []).append(e)

    for week in cal_module.monthcalendar(t_y, t_m):
        wcols = st.columns(7)
        for i, day in enumerate(week):
            with wcols[i]:
                if day == 0:
                    st.markdown("<div style='min-height:78px;'></div>", unsafe_allow_html=True)
                    continue
                is_td = day == today.day and t_m == today.month and t_y == today.year
                cls = "cal-today" if is_td else ""
                ds = datetime.date(t_y, t_m, day).isoformat()
                day_evs = month_events.get(ds, [])
                # Group by normalised title for pills (optional, but reduces clutter)
                grouped_pills = {}
                for ev in day_evs:
                    key = (ev["title"], ev["phase"])
                    if key not in grouped_pills:
                        grouped_pills[key] = {
                            "icon": ev["icon"],
                            "color": ev["color"],
                            "plants": set(),
                            "phase": ev["phase"]
                        }
                    grouped_pills[key]["plants"].add(ev["plant"][:5].capitalize())
                pills = ""
                for (title, phase), data in list(grouped_pills.items())[:3]:
                    plants_display = ", ".join(sorted(data["plants"]))
                    done_cls = ""  # month view doesn't show done status
                    pills += (
                        f"<span class='ev-pill' style='background:{data['color']};{done_cls}'>"
                        f"{data['icon']} {title[:8]}: {plants_display}</span>"
                    )
                if len(grouped_pills) > 3:
                    pills += f"<span style='font-size:0.55rem;color:#888;'>+{len(grouped_pills)-3}</span>"

                st.markdown(
                    f"<div class='cal-cell {cls}'><span class='cal-day-num'>{day}</span>{pills}</div>",
                    unsafe_allow_html=True,
                )

# ---------- Week View (with normalisation and merging) ----------
elif view == "Week":
    wk_off = st.session_state.wk_off
    wn_l, wn_c, wn_r = st.columns([1, 4, 1])
    with wn_l:
        if st.button("◀", key="w_prev"):
            st.session_state.wk_off = wk_off - 7
            st.rerun()
    with wn_r:
        if st.button("▶", key="w_next"):
            st.session_state.wk_off = wk_off + 7
            st.rerun()

    week_start = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=wk_off)
    week_dates = [week_start + datetime.timedelta(days=i) for i in range(7)]

    with wn_c:
        st.markdown(
            f"<h4 style='text-align:center;margin:4px 0;'>{week_start.strftime('%d %b')} – {week_dates[-1].strftime('%d %b %Y')}</h4>",
            unsafe_allow_html=True,
        )

    week_map = defaultdict(list)
    for e in all_events:
        if week_dates[0] <= e["date"] <= week_dates[-1]:
            week_map[e["date"].isoformat()].append(e)

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    wcols = st.columns(7)
    for i, d in enumerate(week_dates):
        with wcols[i]:
            cls = "today-col" if d == today else ""
            st.markdown(
                f"<div class='week-col {cls}'><div class='week-day-hdr'>{day_names[i]}</div><div class='week-day-num'>{d.day}</div></div>",
                unsafe_allow_html=True,
            )
            tasks_this_day = week_map.get(d.isoformat(), [])
            # Group by normalised title + phase (case-insensitive, synonyms merged)
            groups = {}
            for ev in tasks_this_day:
                norm_title = ev["title"]  # already normalised in gather_events
                phase = ev["phase"]
                key = (norm_title, phase)
                if key not in groups:
                    groups[key] = {
                        "plants": set(),
                        "icon": ev["icon"],
                        "color": ev["color"],
                        "phase": phase,
                    }
                groups[key]["plants"].add(ev["plant"])
            # Display each group as one pill
            for (title, phase), data in groups.items():
                plants_str = ", ".join(sorted([p.capitalize() for p in data["plants"]]))
                phase_cls = "phase-indoor" if phase == "indoor" else "phase-outdoor"
                phase_lbl = "🏠 In" if phase == "indoor" else "🌳 Out"
                st.markdown(
                    f"""
                    <div style='background:{data["color"]}18;border-left:3px solid {data["color"]};
                                border-radius:0 6px 6px 0;padding:4px 6px;margin-top:4px;'>
                        <div style='font-size:0.72rem;font-weight:600;color:#333;'>
                            {data["icon"]} {title}
                        </div>
                        <div style='font-size:0.62rem;color:#777;'>
                            {plants_str}
                            <span class='phase-badge {phase_cls}'>{phase_lbl}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# ---------- Progress View ----------
elif view == "Progress":
    st.markdown("<h4 style='color:#2e7d32;margin-bottom:0.5rem;'>Plant progress to harvest</h4>", unsafe_allow_html=True)
    if not user.get("plans"):
        st.info("No plans yet — generate plans on the Dashboard first.")
    else:
        for plant, plan in user["plans"].items():
            if sel_plant != "All Plants" and plant != sel_plant:
                continue
            guide = get_plant_guide(plant)
            maturity_days = guide.get("days_to_maturity", 75)
            outdoor_str = (
                plan.get("actual_outdoor_date")
                or user.get("plants", {}).get(plant, {}).get("actual_planted")
                or user.get("plants", {}).get(plant, {}).get("added_on")
            )
            planted = to_date(outdoor_str)
            if planted:
                days_grown = max(0, (today - planted).days)
                days_left = max(0, maturity_days - days_grown)
                pct = min(100, int((days_grown / maturity_days) * 100))
                harvest_est = planted + datetime.timedelta(days=maturity_days)
            else:
                days_grown = 0; days_left = maturity_days; pct = 0; harvest_est = None
            planting_mode = plan.get("planting_mode", "direct_outdoor")
            mode_icon = "🏠→🌳" if planting_mode == "indoor_then_out" else "🌳"
            color = "#66bb6a" if pct >= 75 else "#ffa726" if pct >= 40 else "#42a5f5"
            with st.container():
                col_info, col_bar = st.columns([1, 2])
                with col_info:
                    st.markdown(
                        f"""
                        <div style='padding:10px 0;'>
                            <div style='font-size:1rem;font-weight:700;color:#1a1a1a;'>{plant.capitalize()}</div>
                            <div style='font-size:0.72rem;color:#888;margin-top:2px;'>{mode_icon} &nbsp; Day {days_grown} of {maturity_days}</div>
                            <div style='font-size:0.72rem;color:#555;margin-top:1px;'>{'Est. harvest: ' + harvest_est.strftime('%d %b %Y') if harvest_est else 'No planting date set'}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_bar:
                    if planting_mode == "indoor_then_out":
                        indoor_str = plan.get("actual_sow_date") or plan.get("recommended_indoor")
                        indoor_start = to_date(indoor_str)
                        if indoor_start and planted:
                            indoor_days = max(0, (planted - indoor_start).days)
                            total_span = maturity_days + indoor_days
                            in_pct = min(50, int((indoor_days / total_span) * 100))
                            out_pct = max(0, pct - in_pct)
                            bar_html = f"""
                            <div style='display:flex;height:14px;border-radius:7px;overflow:hidden;background:#eef2ec;margin-top:16px;'>
                                <div style='width:{in_pct}%;background:#5c6bc0;'></div>
                                <div style='width:{out_pct}%;background:{color};'></div>
                            </div>
                            <div style='display:flex;font-size:0.62rem;color:#888;margin-top:3px;gap:12px;'>
                                <span><span style='color:#5c6bc0;'>■</span> Indoors</span>
                                <span><span style='color:{color};'>■</span> Outdoors ({pct}%)</span>
                            </div>
                            """
                        else:
                            bar_html = f"<div style='height:14px;border-radius:7px;background:#eef2ec;margin-top:16px;'><div style='width:{pct}%;height:100%;border-radius:7px;background:{color};'></div></div>"
                    else:
                        bar_html = f"<div style='height:14px;border-radius:7px;background:#eef2ec;margin-top:16px;'><div style='width:{pct}%;height:100%;border-radius:7px;background:{color};'></div></div>"
                    st.markdown(
                        bar_html + f"<div style='font-size:0.72rem;color:#888;margin-top:2px;'>{days_left} days to estimated harvest</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown("<hr style='margin:6px 0;border-color:#f0f0f0;'>", unsafe_allow_html=True)

    # Seasonal planting suggestions
    st.markdown(f"<h4 style='color:#2e7d32;margin:1rem 0 0.5rem;'>🌱 What to plant in {today.strftime('%B')}:</h4>", unsafe_allow_html=True)
    seasonal = {
        1: ["Broad beans (indoors)", "Onion sets", "Chilli (indoors on windowsill)"],
        2: ["Tomatoes (indoors)", "Peppers (indoors)", "Lettuce (indoors)"],
        3: ["Peas", "Carrots", "Spinach", "Parsnips", "Onion sets outdoors"],
        4: ["Courgette (indoors)", "Cucumber (indoors)", "Beetroot", "Radish"],
        5: ["Sweetcorn", "French beans", "Runner beans", "Outdoor tomatoes (after frost)"],
        6: ["Basil outdoors", "Turnips", "Kale", "Second peas"],
        7: ["Autumn carrots", "Spring cabbages", "Pak choi", "Lettuce"],
        8: ["Spring onions", "Spinach", "Salad leaves", "Garlic (late Aug)"],
        9: ["Garlic", "Overwintering onions", "Winter lettuce", "Broad beans"],
        10: ["Garlic", "Tulips", "Overwintering spinach"],
        11: ["Garlic (last chance)", "Sweet peas (indoors)"],
        12: ["Planning time! Order seed catalogues"],
    }
    for item in seasonal.get(today.month, ["Check your local conditions"]):
        st.markdown(f"- {item}")