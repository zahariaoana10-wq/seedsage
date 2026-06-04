import datetime

def update_achievements(user):
    """Calculate achievements and store in user['achievements']."""
    achievements = []
    # Plant count
    plant_count = len(user.get("plants", {}))
    if plant_count >= 3:
        achievements.append("🌱 Green Thumb – 3 plants growing")
    if plant_count >= 6:
        achievements.append("🌿 Plant Parent – 6 plants growing")
    if plant_count >= 10:
        achievements.append("🌳 Gardener Extraordinaire – 10 plants")
    
    # Plans
    plan_count = len(user.get("plans", {}))
    if plan_count >= 3:
        achievements.append("📋 Planner – 3 plants planned")
    
    # Journal entries
    journal_count = len(user.get("journal", []))
    if journal_count >= 5:
        achievements.append("📓 Storyteller – 5 journal entries")
    if journal_count >= 10:
        achievements.append("📖 Garden Diarist – 10 entries")
    
    # Completed tasks (from plans)
    completed_tasks = sum(
        1 for plan in user.get("plans", {}).values()
        for ev in plan.get("task_events", [])
        if ev.get("status") == "done"
    )
    if completed_tasks >= 10:
        achievements.append("✅ Task Master – 10 completed tasks")
    if completed_tasks >= 25:
        achievements.append("⚡ Green Thumb – 25 tasks done")
    
    # Companion pairs used (not fully implemented, but placeholder)
    # For now, just add a dummy if any companion pairing exists in garden layout
    layout = user.get("garden_layout", {}).get("cells", {})
    used_plants = [p for p in layout.values() if p]
    if len(used_plants) >= 3:
        achievements.append("🌻 Companion Planner – Plants placed with companions")
    
    user["achievements"] = list(set(achievements))  # remove duplicates
    return user["achievements"]