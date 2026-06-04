"""
utils/smart_tasks.py – Unified gardening task engine
Fixed: generate_insights handles mixed date types (str or date).
"""

import datetime

# =============================================================================
# Task metadata and helpers
# =============================================================================
TASK_CATEGORIES = {
    "watering":      {"icon": "💧", "label": "Watering",       "color": "#42a5f5", "reminder_days": 1},
    "fertilising":   {"icon": "🧪", "label": "Fertilising",    "color": "#ab47bc", "reminder_days": 3},
    "sowing":        {"icon": "🌱", "label": "Sowing",         "color": "#66bb6a", "reminder_days": 7},
    "transplanting": {"icon": "🔄", "label": "Transplanting",  "color": "#26a69a", "reminder_days": 3},
    "harvesting":    {"icon": "🌾", "label": "Harvesting",     "color": "#ffa726", "reminder_days": 1},
    "pruning":       {"icon": "✂️", "label": "Pruning",        "color": "#8d6e63", "reminder_days": 3},
    "pest_check":    {"icon": "🐛", "label": "Pest Check",     "color": "#ef5350", "reminder_days": 3},
    "hardening":     {"icon": "🌤️", "label": "Hardening Off",  "color": "#29b6f6", "reminder_days": 2},
    "general":       {"icon": "📋", "label": "General",        "color": "#607d8b", "reminder_days": 1},
}

CATEGORY_KEYWORDS = {
    "watering":      ["water", "irrigat", "mist", "drip"],
    "fertilising":   ["fertilis", "fertiliz", "feed", "compost", "nutrient", "manure", "liquid feed"],
    "sowing":        ["sow", "seed", "germinate", "propagate", "direct sow"],
    "transplanting": ["transplant", "pot on", "repot", "thin out", "plant out", "move out"],
    "harvesting":    ["harvest", "pick", "collect", "cut", "deadhead"],
    "pruning":       ["prune", "pinch", "trim", "side-shoot", "stake", "train"],
    "pest_check":    ["pest", "disease", "aphid", "slug", "inspect", "spray"],
    "hardening":     ["harden", "acclimat", "cold frame"],
}

def classify_task(task_name: str) -> str:
    task_lower = task_name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in task_lower for k in keywords):
            return category
    return "general"

def generate_reason(category: str) -> str:
    reasons = {
        "watering": "💧 Plants need consistent moisture for healthy growth",
        "fertilising": "🧪 Feeding supports strong growth and higher yields",
        "pest_check": "🐛 Early pest detection prevents major damage",
        "pruning": "✂️ Pruning encourages stronger structure and growth",
        "sowing": "🌱 Correct timing improves germination success",
        "transplanting": "🔄 Proper spacing ensures healthy root development",
        "harvesting": "🌾 Timely harvesting improves yield and flavour",
        "hardening": "🌤️ Gradual exposure prevents transplant shock",
    }
    return reasons.get(category, "📋 Routine garden maintenance")

def generate_task_events(tasks, outdoor_anchor=None, indoor_anchor=None, last_frost_date=None):
    today = datetime.date.today()
    if outdoor_anchor is None and last_frost_date:
        outdoor_anchor = last_frost_date + datetime.timedelta(days=14)
    else:
        if outdoor_anchor is None:
            outdoor_anchor = today
        if indoor_anchor is None:
            indoor_anchor = outdoor_anchor - datetime.timedelta(weeks=7)

    events = []
    for task in tasks:
        name = task.get("task", "Task")
        frequency = task.get("frequency", "weekly")
        offset = task.get("start_offset_days", 0)
        duration = task.get("duration_days", 30)
        phase = task.get("phase", "outdoor")
        notes = task.get("notes", "")

        category = task.get("category") or classify_task(name)
        meta = TASK_CATEGORIES.get(category, TASK_CATEGORIES["general"])

        anchor = indoor_anchor if phase == "indoor" else outdoor_anchor
        start = anchor + datetime.timedelta(days=offset)
        end = start + datetime.timedelta(days=max(0, duration - 1))

        current = start
        while current <= end:
            events.append({
                "id": f"{name}_{current.isoformat()}",
                "title": name,
                "date": current,
                "status": "scheduled",
                "reason": generate_reason(category),
                "category": category,
                "phase": phase,
                "notes": notes,
                "icon": meta["icon"],
                "color": meta["color"],
                "reminder": True,
            })
            if frequency == "daily":
                current += datetime.timedelta(days=1)
            elif frequency == "every_3_days":
                current += datetime.timedelta(days=3)
            elif frequency == "weekly":
                current += datetime.timedelta(days=7)
            elif frequency == "fortnightly":
                current += datetime.timedelta(days=14)
            elif frequency == "monthly":
                current += datetime.timedelta(days=30)
            else:
                break
    events.sort(key=lambda e: e["date"])
    return events

def apply_weather_rules(task_events, forecast):
    if not forecast:
        return task_events
    rain = any("rain" in f.get("description", "").lower() for f in forecast)
    heavy_rain = any("heavy" in f.get("description", "").lower() for f in forecast)
    frost = any(f.get("temp", 99) < 2 for f in forecast)

    adjusted = []
    today = datetime.date.today()
    for ev in task_events:
        ev = dict(ev)
        cat = ev.get("category")
        date = ev.get("date")
        if isinstance(date, str):
            try:
                date = datetime.date.fromisoformat(date)
            except:
                pass
        if cat == "watering" and rain and date <= today + datetime.timedelta(days=1):
            ev["status"] = "skipped"
            ev["reason"] = "☔ Rain expected — watering skipped"
            adjusted.append(ev)
            continue
        if cat == "fertilising" and heavy_rain:
            ev["date"] += datetime.timedelta(days=1)
            ev["status"] = "delayed"
            ev["reason"] = "🌧️ Heavy rain — delayed to prevent nutrient washout"
        if cat in ("sowing", "transplanting") and frost and ev.get("phase") == "outdoor":
            ev["date"] += datetime.timedelta(days=3)
            ev["status"] = "delayed"
            ev["reason"] = "🥶 Frost risk — delayed 3 days"
        adjusted.append(ev)
    return adjusted

def get_upcoming_reminders(plans, days_ahead=7):
    today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=days_ahead)
    reminders = []
    for plant, plan in plans.items():
        for ev in plan.get("task_events", []):
            d_raw = ev.get("date")
            if isinstance(d_raw, str):
                try:
                    d = datetime.date.fromisoformat(d_raw)
                except:
                    continue
            elif isinstance(d_raw, datetime.date):
                d = d_raw
            else:
                continue
            if today <= d <= cutoff and ev.get("status") not in ("skipped", "done"):
                reminders.append({**ev, "plant": plant})
    reminders.sort(key=lambda x: x["date"])
    return reminders

def get_date_ranges(plan):
    today = datetime.date.today()
    year = today.year
    ranges = []
    for item in plan.get("timeline", []):
        sm = item.get("start_month", 1)
        em = item.get("end_month", sm)
        task = item.get("task", "Task")
        try:
            start_year = year if sm >= today.month else year + 1
            end_year = start_year if em >= sm else start_year + 1
            start = datetime.date(start_year, sm, 1)
            if em == 12:
                end = datetime.date(end_year, 12, 31)
            else:
                end = datetime.date(end_year, em + 1, 1) - datetime.timedelta(days=1)
            start_name = start.strftime("%b")
            end_name = end.strftime("%b")
            if start_year == end_year:
                label = f"{start_name}–{end_name}"
            else:
                label = f"{start_name} {start_year} – {end_name} {end_year}"
            ranges.append({"task": task, "start_date": start, "end_date": end, "label": label})
        except:
            continue
    return ranges

# =============================================================================
# NEW FUNCTIONS (growth stage, insights, plan adjustment, missed tasks fix)
# =============================================================================

def get_growth_stage(plant: str, plan: dict) -> str:
    if not plan or not plan.get("actual_outdoor_date"):
        return "unknown"
    planted = datetime.date.fromisoformat(plan["actual_outdoor_date"])
    today = datetime.date.today()
    days = (today - planted).days
    if days < 0:
        return "pre-planting"
    elif days <= 14:
        return "seedling"
    elif days <= 40:
        return "vegetative"
    elif days <= 70:
        return "flowering"
    elif days <= 110:
        return "fruiting"
    else:
        return "harvest"

def get_stage_advice(stage: str) -> str:
    advice = {
        "seedling": "🌱 Keep soil moist and protect from cold.",
        "vegetative": "🌿 Focus on leaf growth — water and feed regularly.",
        "flowering": "🌼 Support flowering with potassium-rich feed.",
        "fruiting": "🍅 Maintain watering consistency for best yield.",
        "harvest": "🌾 Harvest regularly to encourage production.",
    }
    return advice.get(stage, "")

def generate_insights(user: dict) -> list:
    insights = []
    plans = user.get("plans", {})
    journal = user.get("journal", [])
    today = datetime.date.today()

    # Growth stage advice grouped by stage
    stage_plants = {}
    for plant, plan in plans.items():
        stage = get_growth_stage(plant, plan)
        if stage not in ("unknown", "pre-planting"):
            stage_plants.setdefault(stage, []).append(plant.capitalize())

    for stage, plants in stage_plants.items():
        advice = get_stage_advice(stage)
        if advice:
            if len(plants) == 1:
                insights.append(f"{advice} ({plants[0]})")
            else:
                insights.append(f"{advice} ({', '.join(plants)})")

    # Journal insights – handle both string and date objects
    recent_entries = []
    for j in journal:
        d_raw = j.get("date")
        try:
            if isinstance(d_raw, datetime.date):
                d = d_raw
            elif isinstance(d_raw, str):
                d = datetime.date.fromisoformat(d_raw)
            else:
                continue
            if d >= today - datetime.timedelta(days=7):
                recent_entries.append(j)
        except:
            continue
    if len(recent_entries) >= 3:
        insights.append("📝 You're consistently logging activity — great for tracking progress.")
    if not journal:
        insights.append("📓 Start journaling to unlock personalised insights.")

    # Missed tasks — only flag truly overdue (scheduled, not backdated-done)
    overdue_plants = []
    for plant, plan in plans.items():
        for t in plan.get("task_events", []):
            d_raw = t.get("date")
            try:
                if isinstance(d_raw, datetime.date):
                    d = d_raw
                elif isinstance(d_raw, str):
                    d = datetime.date.fromisoformat(d_raw)
                else:
                    continue
                if t.get("status") == "scheduled" and d < today:
                    overdue_plants.append(plant.capitalize())
                    break
            except Exception:
                continue
    if overdue_plants:
        if len(overdue_plants) == 1:
            insights.append(f"⚠️ You have overdue tasks for {overdue_plants[0]} — consider catching up.")
        else:
            insights.append(f"⚠️ You have overdue tasks for {', '.join(overdue_plants)} — consider catching up.")
    return insights

def adjust_plan_for_reality(plan: dict) -> dict:
    if not plan.get("actual_outdoor_date") or not plan.get("recommended_outdoor"):
        return plan
    actual = datetime.date.fromisoformat(plan["actual_outdoor_date"])
    recommended = datetime.date.fromisoformat(plan["recommended_outdoor"])
    delta = (actual - recommended).days
    for task in plan.get("tasks", []):
        task["start_offset_days"] += delta
    return plan

def reschedule_missed_tasks(events):
    """
    For plans generated after the planting date has already passed:
    - Past tasks → mark as done
    - Future tasks → keep as scheduled
    """
    today = datetime.date.today()
    updated = []
    for ev in events:
        ev = dict(ev)
        date = ev.get("date")
        if isinstance(date, str):
            try:
                date = datetime.date.fromisoformat(date)
            except Exception:
                pass
        ev["date"] = date
        if isinstance(date, datetime.date) and date < today:
            ev["status"] = "done"
            ev["reason"] = "✅ Completed (backdated plan)"
        updated.append(ev)
    return updated   # ← only one value