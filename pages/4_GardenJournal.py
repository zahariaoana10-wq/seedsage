"""
4_GardenJournal.py — SeedSage Garden Journal (Final)
Fixed date sorting in export Markdown.
"""

import streamlit as st
import datetime
import base64
import csv
import io
import os
import re
import html
import requests
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Garden Journal", page_icon="📓", layout="wide")

if "user" not in st.session_state or not st.session_state.user:
    st.warning("Please login first.")
    st.switch_page("app.py")

from utils.user_db import init_user_db, save_user
from services.location_service import get_uk_location, get_weather

init_user_db()
user = st.session_state.user
today = datetime.date.today()

if "journal" not in user:
    user["journal"] = []

# ---------- Tag definitions ----------
TAGS = {
    "pest": {"label": "Pest", "color": "#b71c1c", "bg": "#ffebee"},
    "disease": {"label": "Disease", "color": "#e65100", "bg": "#fff3e0"},
    "growth": {"label": "Growth", "color": "#1b5e20", "bg": "#e8f5e9"},
    "harvest": {"label": "Harvest", "color": "#ef6c00", "bg": "#fff8e1"},
    "watering": {"label": "Watering", "color": "#0d47a1", "bg": "#e3f2fd"},
    "weather": {"label": "Weather", "color": "#6a1b9a", "bg": "#f3e5f5"},
    "general": {"label": "General", "color": "#37474f", "bg": "#eceff1"},
}

HEALTH_ICONS = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "💚"}
HEALTH_LABELS = {1: "Critical", 2: "Poor", 3: "Fair", 4: "Good", 5: "Thriving"}

# ---------- Helper functions ----------
def entry_id(entry: dict) -> str:
    return entry.get("timestamp", entry.get("date", ""))

def save_entry(plant, date, note, tags, health, photo_b64=None, weather_ctx=None):
    now = datetime.datetime.now().isoformat()
    user["journal"].append({
        "id": now,
        "plant": plant,
        "date": date.isoformat(),
        "note": note,
        "tags": tags,
        "health": health,
        "photo": photo_b64,
        "timestamp": now,
        "weather_ctx": weather_ctx,
        "ai_insight": None,
        "action_taken": None,
    })
    save_user(user)

def delete_entry(eid: str):
    user["journal"] = [e for e in user["journal"] if entry_id(e) != eid]
    save_user(user)

def persist_insight(eid: str, insight: str):
    for e in user["journal"]:
        if entry_id(e) == eid:
            e["ai_insight"] = insight
            break
    save_user(user)

def mark_action_done(eid: str, action: str):
    for e in user["journal"]:
        if entry_id(e) == eid:
            e["action_taken"] = action
            break
    save_user(user)

def get_ai_insight(plant: str, note: str, tags: list) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "⚠️ API key missing — add OPENROUTER_API_KEY to .env"
    tag_context = f"Tags: {', '.join(tags)}. " if tags else ""
    prompt = f"""You are a UK RHS gardening expert. A gardener noted:
Plant: {plant.capitalize()}
{tag_context}Observation: "{note}"

Give a short, practical response under 80 words covering:
1. Most likely cause
2. Immediate action to take
3. Prevention tip

End with a single action line starting with "Action: " (e.g. "Action: Remove yellowed leaves and apply copper fungicide.")"""
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://seedsage.app",
                "X-Title": "SeedSage Journal",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.6,
            },
            timeout=15,
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ Error: {e}"

@st.cache_data(ttl=1800, show_spinner=False)
def get_wx_context(postcode):
    loc = get_uk_location(postcode)
    if loc:
        wx = get_weather(loc["lat"], loc["lon"])
        if wx:
            return f"{wx['temp']:.1f}°C, {wx['description']}"
    return None

wx_ctx = get_wx_context(user.get("postcode", ""))

# ---------- CSS (unchanged from your polished version) ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;600;700&family=DM+Sans:wght@300;400;500;700&display=swap');

.stApp {
    background: linear-gradient(180deg, #f6f8f3 0%, #f4f7f2 100%);
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3, h4 {
    font-family: 'Lora', serif !important;
}

section[data-testid="stSidebar"] {
    background: white !important;
    border-right: 1px solid #e6ede4;
}

.block-container {
    padding-top: 1.25rem;
    padding-bottom: 2rem;
}

.hero {
    background: linear-gradient(135deg, rgba(46,125,50,0.12), rgba(102,187,106,0.08));
    border: 1px solid #dde8da;
    border-radius: 24px;
    padding: 18px 20px;
    margin-bottom: 1rem;
    box-shadow: 0 8px 24px rgba(0,0,0,0.04);
}

.hero-title {
    color: #2e7d32;
    margin: 0;
}

.hero-sub {
    color: #667;
    margin: 0.35rem 0 0;
}

.kpi-card {
    background: rgba(255,255,255,0.96);
    border: 1px solid #e5ede3;
    border-radius: 18px;
    padding: 16px 18px;
    text-align: center;
    box-shadow: 0 8px 20px rgba(0,0,0,0.05);
    transition: transform .15s ease, box-shadow .15s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 26px rgba(0,0,0,0.08);
}
.kpi-num {
    font-size: 1.9rem;
    font-weight: 700;
    color: #2e7d32;
    line-height: 1;
}
.kpi-lbl {
    font-size: 0.72rem;
    color: #6f7b73;
    margin-top: 4px;
    letter-spacing: .03em;
    text-transform: uppercase;
}

.section-hdr {
    color: #2e7d32;
    font-family: 'Lora', serif;
    font-size: 1.02rem;
    font-weight: 700;
    margin: 1.1rem 0 0.7rem;
}

.journal-card {
    background: rgba(255,255,255,0.98);
    border: 1px solid #e5ede3;
    border-radius: 18px;
    padding: 16px 16px 14px;
    margin-bottom: 14px;
    box-shadow: 0 8px 22px rgba(0,0,0,0.05);
    transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.journal-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 30px rgba(0,0,0,0.08);
    border-color: #d7e6d2;
}
.jcard-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}
.health-badge {
    width: 34px;
    height: 34px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f3f7f1;
    border: 1px solid #e0e9dd;
    font-size: 1rem;
}
.jcard-plant {
    font-size: 1.02rem;
    font-weight: 700;
    color: #1a1a1a;
}
.jcard-date {
    font-size: 0.75rem;
    color: #7d8780;
    margin-left: auto;
}
.jcard-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
}
.jcard-note {
    font-size: 0.92rem;
    color: #2f3431;
    line-height: 1.7;
    margin: 6px 0 8px;
}
.tag-pill {
    display: inline-block;
    font-size: 0.64rem;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 999px;
    letter-spacing: .02em;
    border: 1px solid rgba(0,0,0,0.04);
}
.insight-box {
    background: linear-gradient(135deg, #f2f8f2, #eef7ef);
    border-left: 4px solid #4caf50;
    border-radius: 0 12px 12px 0;
    padding: 12px 13px;
    font-size: 0.86rem;
    color: #205b26;
    margin: 10px 0 8px;
    line-height: 1.55;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
}
.action-done-box {
    background: #edf7ee;
    border: 1px solid #cfe3d0;
    border-radius: 12px;
    padding: 9px 12px;
    font-size: 0.82rem;
    color: #2e7d32;
    margin-top: 6px;
}
.weather-ctx {
    font-size: 0.74rem;
    color: #6f7b73;
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.month-group-hdr {
    font-size: 0.78rem;
    font-weight: 800;
    color: #2e7d32;
    letter-spacing: .08em;
    text-transform: uppercase;
    margin: 1.25rem 0 0.65rem;
    padding-bottom: 5px;
    border-bottom: 2px solid #e8f2e7;
}
.filter-panel, .summary-panel {
    background: rgba(255,255,255,0.92);
    border: 1px solid #e5ede3;
    border-radius: 18px;
    padding: 14px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.04);
}
.tag-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}
.divider-soft {
    border: 0;
    border-top: 1px solid #edf1ea;
    margin: 12px 0;
}
div.stButton > button {
    border-radius: 10px;
    background: white;
    color: #2e7d32;
    border: 1px solid #c8e6c9;
    font-family: 'DM Sans', sans-serif;
    transition: all .15s ease;
}
div.stButton > button:hover {
    background: #2e7d32 !important;
    color: white !important;
    border-color: #2e7d32;
}
.photo-card {
    background: white;
    border: 1px solid #e5ede3;
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 8px 22px rgba(0,0,0,0.05);
}
.photo-meta {
    padding: 10px 12px 12px;
    font-size: 0.75rem;
    color: #6f7b73;
}
</style>
""", unsafe_allow_html=True)

# ---------- Sidebar (filters and export) ----------
with st.sidebar:
    st.markdown("<div style='font-size:1.4rem;font-weight:700;color:#2e7d32;font-family:Lora,serif;'>🌿 SeedSage</div>", unsafe_allow_html=True)
    st.page_link("pages/1_Dashboard.py", label="📊 Dashboard", width='stretch')
    st.page_link("pages/2_Calendar.py", label="🗓️ Calendar", width='stretch')
    st.page_link("pages/3_Companions.py", label="🌻 Companions", width='stretch')
    st.page_link("pages/4_GardenJournal.py", label="📓 Journal", width='stretch')
    st.divider()

    st.markdown("<div class='filter-panel'>", unsafe_allow_html=True)
    st.markdown("**Filter entries**")
    all_plants = ["All Plants"] + sorted({e["plant"] for e in user["journal"]}) if user["journal"] else ["All Plants"]
    f_plant = st.selectbox("Plant", all_plants, key="jf_plant")
    all_tags = ["All Tags"] + list(TAGS.keys())
    f_tag = st.selectbox("Tag", all_tags, key="jf_tag")
    f_search = st.text_input("Search notes", placeholder="e.g. yellow leaves…", key="jf_search")
    st.markdown("**Date range**")
    f_date_from = st.date_input("From", value=today - datetime.timedelta(days=90), key="jf_from")
    f_date_to = st.date_input("To", value=today, key="jf_to")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='filter-panel'>", unsafe_allow_html=True)
    st.markdown("**Export**")
    def export_csv() -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date", "plant", "health", "tags", "note", "action_taken", "weather"])
        for e in user["journal"]:
            w.writerow([
                e.get("date", ""),
                e.get("plant", ""),
                HEALTH_LABELS.get(e.get("health", 3), ""),
                "|".join(e.get("tags", [])),
                e.get("note", "").replace("\n", " "),
                e.get("action_taken", "") or "",
                e.get("weather_ctx", "") or "",
            ])
        return buf.getvalue().encode()

    # FIXED: export_md with safe date sorting
    def export_md() -> str:
        lines = ["# Garden Journal\n"]
        def get_sort_key(entry):
            d = entry.get("date")
            if isinstance(d, datetime.date):
                return d
            if isinstance(d, str):
                try:
                    return datetime.date.fromisoformat(d)
                except:
                    return datetime.date.min
            return datetime.date.min
        for e in sorted(user["journal"], key=get_sort_key, reverse=True):
            lines.append(f"## {e.get('plant', '').capitalize()} — {e.get('date', '')}")
            h = e.get("health", 3)
            lines.append(f"**Health:** {HEALTH_ICONS.get(h, '')} {HEALTH_LABELS.get(h, '')}")
            tags = e.get("tags", [])
            if tags:
                lines.append(f"**Tags:** {', '.join(tags)}")
            lines.append(f"\n{e.get('note', '')}\n")
            if e.get("ai_insight"):
                lines.append(f"> AI Insight: {e['ai_insight']}\n")
            if e.get("action_taken"):
                lines.append(f"✅ Action taken: {e['action_taken']}\n")
            lines.append("---")
        return "\n".join(lines)

    st.download_button("⬇️ CSV", export_csv(), "journal.csv", "text/csv", width='stretch')
    st.download_button("⬇️ Markdown", export_md().encode(), "journal.md", "text/markdown", width='stretch')
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Hero and summary ----------
st.markdown(
    "<div class='hero'><h1 class='hero-title'>📓 Garden Journal</h1><p class='hero-sub'>Record observations, get AI diagnoses, and track every step of the season.</p></div>",
    unsafe_allow_html=True,
)

st.markdown("<div class='summary-panel'>", unsafe_allow_html=True)
cols = st.columns(4)
total = len(user["journal"])
n_plants = len({e["plant"] for e in user["journal"]})
n_insights = sum(1 for e in user["journal"] if e.get("ai_insight"))
n_actions = sum(1 for e in user["journal"] if e.get("action_taken"))
for col, num, lbl in [
    (cols[0], total, "total entries"),
    (cols[1], n_plants, "plants logged"),
    (cols[2], n_insights, "AI insights"),
    (cols[3], n_actions, "actions taken"),
]:
    col.markdown(f"<div class='kpi-card'><div class='kpi-num'>{num}</div><div class='kpi-lbl'>{lbl}</div></div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='margin-top:1rem;'>", unsafe_allow_html=True)
st.markdown("<div class='section-hdr'>Tags</div>", unsafe_allow_html=True)
legend = "".join(
    f"<span class='tag-pill' style='background:{meta['bg']};color:{meta['color']};'>{meta['label']}</span>"
    for meta in TAGS.values()
)
st.markdown(f"<div class='tag-legend'>{legend}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---------- Tabs ----------
tab_diary, tab_new, tab_gallery = st.tabs(["📜 Diary", "✍️ New Entry", "🖼️ Photos"])

# ---------- New Entry tab ----------
with tab_new:
    col_form, col_tip = st.columns([3, 2])
    with col_form:
        plant_options = list(user.get("plants", {}).keys())
        if not plant_options:
            st.info("Add plants on the Dashboard first, then come back to log observations.")
        else:
            with st.form("journal_form", clear_on_submit=True):
                sel_plant = st.selectbox("Plant", plant_options)
                entry_date = st.date_input("Date", today)
                col_h, col_t = st.columns([1, 2])
                with col_h:
                    health = st.select_slider("Plant health", options=[1,2,3,4,5], value=4,
                                              format_func=lambda x: f"{HEALTH_ICONS[x]} {HEALTH_LABELS[x]}")
                with col_t:
                    chosen_tags = st.multiselect("Tags", options=list(TAGS.keys()),
                                                format_func=lambda t: TAGS[t]["label"], default=["general"])
                note = st.text_area("Observation", height=170, placeholder="e.g. White powdery spots on courgette leaves…")
                photo = st.file_uploader("Photo (optional)", type=["jpg", "png", "jpeg"])
                if wx_ctx:
                    st.caption(f"Weather will be saved: {wx_ctx}")
                submitted = st.form_submit_button("💾 Save Entry", width='stretch')
            if submitted:
                if note.strip():
                    photo_b64 = base64.b64encode(photo.read()).decode() if photo else None
                    save_entry(sel_plant, entry_date, note.strip(), chosen_tags, health, photo_b64, wx_ctx)
                    st.success("Entry saved!")
                    st.rerun()
                else:
                    st.warning("Please write an observation note.")
    with col_tip:
        st.markdown("<div class='section-hdr'>What to log</div>", unsafe_allow_html=True)
        for icon_lbl, desc in [
            ("🐛 Pests", "Describe what you see — holes, webbing, insects."),
            ("🍂 Yellowing", "Note which leaves and the pattern."),
            ("🌸 Milestones", "First flower, first fruit, first harvest."),
            ("💧 Watering", "Log if you missed or overwatered."),
            ("🌡️ Weather", "Extreme heat, frost, or heavy rain."),
        ]:
            st.markdown(f"<div style='padding:10px 0;border-bottom:1px solid #eef2ec;'><div style='font-size:0.86rem;font-weight:700;color:#2e7d32;'>{icon_lbl}</div><div style='font-size:0.8rem;color:#5f6a62;'>{desc}</div></div>", unsafe_allow_html=True)

# ---------- Diary tab (with fixed date handling in filtering) ----------
with tab_diary:
    def passes_filters(e):
        if f_plant != "All Plants" and e.get("plant") != f_plant:
            return False
        if f_tag != "All Tags" and f_tag not in e.get("tags", []):
            return False
        if f_search and f_search.lower() not in e.get("note", "").lower():
            return False
        try:
            d_raw = e.get("date", "")
            if isinstance(d_raw, str):
                ed = datetime.date.fromisoformat(d_raw)
            elif isinstance(d_raw, datetime.date):
                ed = d_raw
            else:
                return False
            if not (f_date_from <= ed <= f_date_to):
                return False
        except Exception:
            pass
        return True

    filtered = [e for e in user["journal"] if passes_filters(e)]
    def sort_key(entry):
        d = entry.get("date")
        if isinstance(d, datetime.date):
            return d
        if isinstance(d, str):
            try:
                return datetime.date.fromisoformat(d)
            except:
                return datetime.date.min
        return datetime.date.min

    filtered = sorted(filtered, key=sort_key, reverse=True)

    if not filtered:
        st.markdown(
            "<div style='text-align:center;padding:3rem 0;color:#8a948d;'><div style='font-size:3rem;margin-bottom:0.5rem;'>📓</div><div style='font-size:1.05rem;font-weight:700;color:#5d665f;'>No entries yet</div><div style='font-size:0.86rem;'>Switch to the New Entry tab to log your first observation.</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"{len(filtered)} {'entry' if len(filtered) == 1 else 'entries'} shown")
        current_month = None
        for entry in filtered:
            eid = entry_id(entry)
            e_date = entry.get("date", "")
            try:
                if isinstance(e_date, str):
                    d = datetime.date.fromisoformat(e_date)
                elif isinstance(e_date, datetime.date):
                    d = e_date
                else:
                    continue
                month_key = d.strftime("%B %Y")
            except Exception:
                month_key = "Unknown"

            if month_key != current_month:
                st.markdown(f"<div class='month-group-hdr'>{month_key}</div>", unsafe_allow_html=True)
                current_month = month_key

            health = entry.get("health", 3)
            tags = entry.get("tags", [])
            h_icon = HEALTH_ICONS.get(health, "🟡")
            h_label = HEALTH_LABELS.get(health, "Fair")
            tag_html = "".join(
                f"<span class='tag-pill' style='background:{TAGS[t]['bg']};color:{TAGS[t]['color']};'>{TAGS[t]['label']}</span>"
                for t in tags if t in TAGS
            )
            wx_html = f"<div class='weather-ctx'>🌡️ {entry['weather_ctx']}</div>" if entry.get("weather_ctx") else ""
            action_html = f"<div class='action-done-box'>✅ Action taken: {entry['action_taken']}</div>" if entry.get("action_taken") else ""

            if entry.get("ai_insight"):
                clean_insight = html.escape(re.sub(r"<[^>]+>", "", entry["ai_insight"]))
                clean_insight = clean_insight.replace("\n", "<br>")
                insight_html = f"<div class='insight-box'>🧠 <strong>AI advice:</strong><br>{clean_insight}</div>"
            else:
                insight_html = ""

            st.markdown(f"""
            <div class='journal-card'>
                <div class='jcard-header'>
                    <div class='health-badge'>{h_icon}</div>
                    <div class='jcard-plant'>{entry.get('plant', '').capitalize()}</div>
                    <div style='font-size:0.72rem;color:#7d8780;background:#f4f7f2;border-radius:999px;padding:2px 8px;'>{h_label}</div>
                    <div class='jcard-date'>{e_date if isinstance(e_date, str) else e_date.isoformat()}</div>
                </div>
                <div class='jcard-meta'>{tag_html}</div>
                <div class='jcard-note'>{entry.get('note', '')}</div>
                {wx_html}
                {insight_html}
                {action_html}
            </div>""", unsafe_allow_html=True)

            if entry.get("photo"):
                with st.expander("📷 View photo"):
                    st.image(base64.b64decode(entry["photo"]), use_container_width=True)

            btn_cols = st.columns([2, 2, 2, 1])
            with btn_cols[0]:
                btn_label = "🔄 Re-analyse" if entry.get("ai_insight") else "🧠 AI Insight"
                if st.button(btn_label, key=f"ins_{eid}", width='stretch'):
                    with st.spinner("Analysing…"):
                        insight = get_ai_insight(entry["plant"], entry["note"], entry.get("tags", []))
                    persist_insight(eid, insight)
                    st.rerun()
            with btn_cols[1]:
                if entry.get("ai_insight") and not entry.get("action_taken"):
                    action_line = "Task completed"
                    for line in entry["ai_insight"].split("\n"):
                        if line.strip().startswith("Action:"):
                            action_line = line.replace("Action:", "").strip()
                            break
                    if st.button("✅ Mark done", key=f"done_{eid}", width='stretch'):
                        mark_action_done(eid, action_line)
                        st.rerun()
                elif entry.get("action_taken"):
                    st.markdown("<div style='font-size:0.76rem;color:#2e7d32;padding-top:6px;font-weight:700;'>✅ Done</div>", unsafe_allow_html=True)
            with btn_cols[2]:
                if st.button("✏️ Edit", key=f"edit_{eid}", width='stretch'):
                    st.session_state[f"editing_{eid}"] = True
            with btn_cols[3]:
                if st.button("🗑️", key=f"del_{eid}", width='stretch', help="Delete entry"):
                    st.session_state[f"confirm_del_{eid}"] = True

            if st.session_state.get(f"editing_{eid}"):
                st.markdown("<div class='section-hdr'>Edit note</div>", unsafe_allow_html=True)
                new_note = st.text_area("", value=entry["note"], key=f"note_edit_{eid}", label_visibility="collapsed", height=120)
                c1, c2 = st.columns(2)
                if c1.button("Save", key=f"save_edit_{eid}"):
                    for e in user["journal"]:
                        if entry_id(e) == eid:
                            e["note"] = new_note
                            break
                    save_user(user)
                    del st.session_state[f"editing_{eid}"]
                    st.rerun()
                if c2.button("Cancel", key=f"cancel_edit_{eid}"):
                    del st.session_state[f"editing_{eid}"]
                    st.rerun()

            if st.session_state.get(f"confirm_del_{eid}"):
                st.warning(f"Delete this {entry['plant']} entry from {e_date}?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, delete", key=f"yes_del_{eid}"):
                    delete_entry(eid)
                    for k in [f"confirm_del_{eid}", f"editing_{eid}"]:
                        st.session_state.pop(k, None)
                    st.rerun()
                if c2.button("Cancel", key=f"no_del_{eid}"):
                    del st.session_state[f"confirm_del_{eid}"]
                    st.rerun()

            st.markdown("<hr class='divider-soft'>", unsafe_allow_html=True)

# ---------- Photo gallery tab ----------
with tab_gallery:
    photo_entries = [e for e in user["journal"] if e.get("photo")]
    if not photo_entries:
        st.markdown(
            "<div style='text-align:center;padding:3rem 0;color:#8a948d;'><div style='font-size:3rem;'>🖼️</div><div style='font-size:1.02rem;font-weight:700;color:#5d665f;'>No photos yet</div><div style='font-size:0.86rem;'>Upload a photo when creating a journal entry.</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"{len(photo_entries)} photo(s) in your journal")
        cols = st.columns(3)
        for i, entry in enumerate(sorted(photo_entries, key=lambda x: x.get("date", ""), reverse=True)):
            with cols[i % 3]:
                tags = entry.get("tags", [])
                tag_str = " ".join(
                    f"<span class='tag-pill' style='background:{TAGS[t]['bg']};color:{TAGS[t]['color']};'>{TAGS[t]['label']}</span>"
                    for t in tags if t in TAGS
                )
                health = entry.get("health", 3)
                st.markdown("<div class='photo-card'>", unsafe_allow_html=True)
                st.image(base64.b64decode(entry["photo"]), use_container_width=True)
                st.markdown(
                    f"<div class='photo-meta'><div style='font-weight:700;color:#2f3431;margin-bottom:4px;'>{entry['plant'].capitalize()} — {entry['date']}</div><div>{HEALTH_ICONS.get(health, '🟡')} {HEALTH_LABELS.get(health, 'Fair')}</div><div style='margin-top:6px;'>{tag_str}</div></div>",
                    unsafe_allow_html=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)