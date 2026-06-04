"""
3_Companions.py — Companion Planting Explorer + AI Garden Layout
"""

from __future__ import annotations

import html
import json
import os
from collections import Counter
from typing import Dict, List, Tuple
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="SeedSage | Companions", page_icon="🌻", layout="wide")

if "user" not in st.session_state or not st.session_state.user:
    st.warning("Please login first.")
    st.switch_page("app.py")

user = st.session_state.user

from services.companion_service import (
    BENEFIT_LABELS,
    enrich_with_ai,
    get_companions,
    get_pairing_info,
)
from services.plant_image_service import get_plant_color, get_plant_emoji
from utils.user_db import save_user

# ── Persistence ──────────────────────────────────────────────
def save_current_user() -> None:
    st.session_state.user = user
    save_user(st.session_state.user)

def persist_layout() -> None:
    draft = st.session_state.layout_draft
    user["garden_layout"] = {
        "rows":      draft["rows"],
        "cols":      draft["cols"],
        "cells":     draft["cells"].copy(),
        "user_cells": draft.get("user_cells", set()),   # which cells the user placed
    }
    save_current_user()

def init_layout_state() -> None:
    saved = user.get("garden_layout", {})
    if "layout_draft" not in st.session_state:
        st.session_state.layout_draft = {
            "rows":      int(saved.get("rows", 6)),
            "cols":      int(saved.get("cols", 6)),
            "cells":     saved.get("cells", {}).copy(),
            "user_cells": set(saved.get("user_cells", [])),
        }
    # pending AI additions (not yet accepted)
    st.session_state.setdefault("ai_additions", {})
    st.session_state.setdefault("ai_add_justification", "")
    st.session_state.setdefault("rejected_ai_cells", set())
    st.session_state.setdefault("full_layout_suggestion", None)
    st.session_state.setdefault("full_layout_justification", "")

def clear_ai_additions() -> None:
    st.session_state.ai_additions = {}
    st.session_state.ai_add_justification = ""
    st.session_state.rejected_ai_cells = set()

# ── Grid helpers ─────────────────────────────────────────────
def orthogonal_neighbors(cell_key: str, rows: int, cols: int) -> List[str]:
    r, c = map(int, cell_key.split(","))
    return [f"{rr},{cc}" for rr, cc in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
            if 0 <= rr < rows and 0 <= cc < cols]

def analyze_adjacent_pairs(cells: Dict[str,str], rows: int, cols: int) -> Tuple[List,List]:
    good, bad, seen = [], [], set()
    for key, pa in cells.items():
        if not pa: continue
        for nb in orthogonal_neighbors(key, rows, cols):
            pb = cells.get(nb,"")
            if not pb or pa == pb: continue
            edge = tuple(sorted((key, nb)))
            if edge in seen: continue
            seen.add(edge)
            rel = get_pairing_info(pa, pb).get("relationship","neutral")
            label = f"{pa} + {pb}"
            if rel == "companion": good.append(label)
            elif rel == "avoid":   bad.append(label)
    return good, bad

def resize_cells(cells: Dict[str,str], old_r, old_c, new_r, new_c) -> Dict[str,str]:
    out = {f"{r},{c}": "" for r in range(new_r) for c in range(new_c)}
    for k, v in cells.items():
        r, c = map(int, k.split(","))
        if 0 <= r < new_r and 0 <= c < new_c:
            out[k] = v
    return out

def detect_conflicts(plants: List[str]):
    conflicts, guilds, seen_c, seen_g = [], [], set(), set()
    for i, a in enumerate(plants):
        for b in plants[i+1:]:
            rel = get_pairing_info(a,b).get("relationship","neutral")
            pair = tuple(sorted((a,b)))
            if rel == "avoid"     and pair not in seen_c: conflicts.append(pair); seen_c.add(pair)
            if rel == "companion" and pair not in seen_g: guilds.append(pair);    seen_g.add(pair)
    return sorted(conflicts), sorted(guilds)

@st.cache_data(ttl=86400, show_spinner=False)
def safe_enrich(plant: str, postcode: str) -> dict:
    try:
        return enrich_with_ai(plant, postcode) or {"companions":[],"avoid":[]}
    except Exception:
        return {"companions":[],"avoid":[]}

# ── AI: fill empty cells around user's layout ────────────────
def ai_fill_around_user(
    current_cells: Dict[str, str],
    user_cell_keys: set,
    n_to_add: int,
    available_plants: List[str],
    rows: int,
    cols: int,
    extra_companions: List[str] = None,  # plants from companion DB not in garden
) -> Tuple[Dict[str,str] | None, str | None, str | None]:
    """
    Asks the AI to choose the best (plant, cell) pairs to fill n_to_add
    empty cells, using companion rules relative to what the user has already placed.

    Returns:
        additions   : Dict[cell_key → plant_name]  — ONLY the new cells
        justification: str
        error       : str | None
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None, None, "OPENROUTER_API_KEY missing from .env"

    empty_cells = [f"{r},{c}" for r in range(rows) for c in range(cols)
                   if not current_cells.get(f"{r},{c}","")]
    if n_to_add > len(empty_cells):
        return None, None, f"Only {len(empty_cells)} empty cells available, but {n_to_add} requested."

    placed_desc = {k: v for k,v in current_cells.items() if v}
    all_plants = list(set(available_plants + (extra_companions or [])))

    prompt = f"""You are an expert companion planting garden designer.

EXISTING LAYOUT (placed by the user, do NOT move these):
{json.dumps(placed_desc, indent=2)}

EMPTY CELLS available (row,col format):
{json.dumps(empty_cells)}

GRID SIZE: {rows} rows × {cols} columns (cells go from 0,0 to {rows-1},{cols-1})

PLANTS you may choose from:
{json.dumps(all_plants)}

TASK:
Choose exactly {n_to_add} of the empty cells and assign the best companion plant to each one.
Rules:
1. Choose plants that are GOOD COMPANIONS to their neighbours in the existing layout.
2. Avoid placing plants that CONFLICT with their neighbours.
3. Do NOT place the same species in adjacent cells (horizontally or vertically).
4. Do NOT move or change any existing user placements.
5. You may repeat a plant species if there are multiple good spots — use your judgement.
6. Fill exactly {n_to_add} cells, no more, no less.

Return ONLY valid JSON (no markdown):
{{
  "additions": {{"row,col": "plant_name", ...}},
  "justification": "under 80 words explaining your choices"
}}"""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://seedsage.app",
                "X-Title": "SeedSage Layout",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role":"user","content": prompt}],
                "max_tokens": 800,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        content = resp.json()["choices"][0]["message"]["content"].strip()
        parsed  = json.loads(content)
        additions = parsed.get("additions", {})
        justification = parsed.get("justification", "AI companion suggestions.")

        # Validate: only empty cells, only valid coords
        validated = {}
        for k, plant in additions.items():
            if k in empty_cells and plant in all_plants:
                validated[k] = plant
        # If AI returned fewer than asked, note it
        if len(validated) < n_to_add:
            justification += f" (Note: {n_to_add - len(validated)} cell(s) could not be filled optimally.)"
        return validated, justification, None

    except Exception as e:
        return None, None, f"AI error: {e}"

# ── AI: full layout suggestion (existing feature) ────────────
def ai_full_layout(
    plant_quantities: Dict[str,int],
    current_cells: Dict[str,str],
    rows: int, cols: int,
) -> Tuple[Dict[str,str] | None, str | None, str | None]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None, None, "OPENROUTER_API_KEY missing."

    total = sum(plant_quantities.values())
    if total > rows * cols:
        return None, None, f"Grid too small ({rows*cols} cells) for {total} plants."

    plants_str = ", ".join(f"{p} ×{q}" for p,q in plant_quantities.items())
    prompt = f"""Companion planting garden layout expert.

Plants with quantities: {plants_str}
Grid: {rows}×{cols} (cells "row,col", 0,0 to {rows-1},{cols-1})

Rules:
- Place EXACTLY the right count of each plant.
- Good companions adjacent where possible.
- Antagonists far apart.
- Never same species in adjacent cells.

Return ONLY JSON:
{{"layout": {{"row,col": "plant_name"}}, "justification": "under 80 words"}}"""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model":"openai/gpt-4o-mini",
                  "messages":[{"role":"user","content":prompt}],
                  "max_tokens":800, "temperature":0.3,
                  "response_format":{"type":"json_object"}},
            timeout=30,
        )
        parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
        raw    = parsed.get("layout", {})
        just   = parsed.get("justification","AI layout.")

        # repair quantities
        desired  = plant_quantities.copy()
        counts   = Counter()
        repaired = {}
        for k, plant in raw.items():
            r2, c2 = map(int, k.split(","))
            if not (0 <= r2 < rows and 0 <= c2 < cols): continue
            if plant not in desired: continue
            if counts[plant] < desired[plant]:
                repaired[k] = plant
                counts[plant] += 1
        # fill missing
        all_cells = [f"{r},{c}" for r in range(rows) for c in range(cols)]
        empty     = [c for c in all_cells if c not in repaired]
        missing   = []
        for plant, qty in desired.items():
            missing.extend([plant] * max(0, qty - counts.get(plant,0)))
        for i, plant in enumerate(missing):
            if i < len(empty): repaired[empty[i]] = plant
        return repaired, just, None
    except Exception as e:
        return None, None, f"AI error: {e}"

# Add this helper at the top of the file (after imports, before build_board_figure)
def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a hex color (#rrggbb or #rgb) to an rgba string."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    if len(hex_color) != 6:
        return f"rgba(0,0,0,{alpha})"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# Then replace the entire build_board_figure function with:
def build_board_figure(
    cells: Dict[str, str],
    rows: int,
    cols: int,
    highlight_cells: Dict[str, str] = None,
    rejected_cells: set = None,
) -> go.Figure:
    highlight_cells = highlight_cells or {}
    rejected_cells = rejected_cells or set()
    xs, ys, texts, colors, sizes, hover, borders = [], [], [], [], [], [], []

    for r in range(rows):
        for c in range(cols):
            key = f"{r},{c}"
            plant = cells.get(key, "") or highlight_cells.get(key, "")
            is_ai = key in highlight_cells and key not in rejected_cells
            is_rejected = key in rejected_cells

            xs.append(c)
            ys.append(rows - 1 - r)

            if plant and not is_rejected:
                texts.append(get_plant_emoji(plant))
                base_color = get_plant_color(plant)
                if is_ai:
                    colors.append(hex_to_rgba(base_color, 0.6))
                else:
                    colors.append(base_color)  # normal hex, no alpha
                sizes.append(56 if not is_ai else 48)
                border = "#ffa726" if is_ai else "#dfe8da"
                hover.append(
                    f"<b>{html.escape(plant.capitalize())}</b><br>"
                    f"{'🤖 AI suggestion' if is_ai else '👤 Your plant'}<br>Cell: {key}"
                )
            else:
                texts.append("·")
                colors.append("#f0f4ee")
                sizes.append(36)
                border = "#e0e8dc"
                hover.append(f"Empty · {key}")
            borders.append(border)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="markers+text",
        text=texts,
        textfont=dict(size=20),
        textposition="middle center",
        hovertext=hover,
        hoverinfo="text",
        marker=dict(
            size=sizes,
            color=colors,
            line=dict(color=borders, width=2),
            symbol="square",
        ),
        showlegend=False,
    ))

    if highlight_cells:
        fig.add_annotation(
            x=0, y=-0.08, xref="paper", yref="paper",
            text="🟧 Orange border = AI suggestion   |   🟩 Green border = Your placement",
            showarrow=False, font=dict(size=11, color="#666"),
            xanchor="left",
        )
    fig.update_layout(
        height=max(320, rows * 80),
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis=dict(visible=False, range=[-0.5, cols - 0.5]),
        yaxis=dict(visible=False, range=[-0.5, rows - 0.5], scaleanchor="x", scaleratio=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
def render_health_banner(cells: Dict[str,str], rows: int, cols: int):
    good, bad = analyze_adjacent_pairs(cells, rows, cols)
    if bad:
        st.warning(f"⚠️ Adjacent conflicts: {', '.join(set(bad[:5]))}"
                   + (f" (+{len(bad)-5} more)" if len(bad) > 5 else ""))
    if good:
        st.success(f"🌿 Good adjacencies: {', '.join(set(good[:5]))}"
                   + (f" (+{len(good)-5} more)" if len(good) > 5 else ""))
    if not good and not bad:
        st.info("No strong companion relationships detected yet. Add more plants!")

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap');

:root {
    --card: rgba(255,255,255,0.92);
    --line: #e3eadf;
    --text: #18311d;
    --muted: #6b766d;
    --green: #2e7d32;
    --green2: #66bb6a;
}

.stApp {
    background: radial-gradient(circle at top left, rgba(102,187,106,0.10), transparent 28%),
                radial-gradient(circle at top right, rgba(46,125,50,0.08), transparent 26%),
                linear-gradient(180deg, #f8faf6 0%, #f3f7f0 100%);
    font-family: 'DM Sans', sans-serif;
    color: var(--text);
}
h1,h2,h3,h4 { font-family:'Lora',serif !important; letter-spacing:-0.02em; }
section[data-testid="stSidebar"] { background:rgba(255,255,255,0.92) !important; border-right:1px solid var(--line); backdrop-filter:blur(10px); }

.hero { background:linear-gradient(135deg,#2e7d32,#66bb6a); border-radius:24px; padding:26px; margin-bottom:1.5rem; color:white; box-shadow:0 18px 40px rgba(0,0,0,0.12); }

.stat-card { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:14px 18px; text-align:center; backdrop-filter:blur(8px); }
.stat-label { color:var(--muted); font-size:0.72rem; }
.stat-value { font-size:1.15rem; font-weight:700; color:var(--green); }

.section-header { color:var(--green); font-family:'Lora',serif; font-size:1.2rem; font-weight:600; margin:1.2rem 0 0.6rem; padding-bottom:6px; border-bottom:2px solid #e8f5e9; }

.sidebar-badge { background:linear-gradient(135deg,#f1f8e9,#e8f5e9); padding:12px; border-radius:14px; margin-bottom:12px; border:1px solid var(--line); }

.companion-card { background:#e8f5e9; border-left:5px solid #4caf50; border-radius:12px; padding:10px 12px; margin-bottom:8px; transition:transform 0.2s,box-shadow 0.2s; }
.companion-card:hover { transform:translateY(-2px); box-shadow:0 6px 16px rgba(0,0,0,0.07); }
.avoid-card { background:#ffebee; border-left:5px solid #ef5350; border-radius:12px; padding:10px 12px; margin-bottom:8px; transition:transform 0.2s; }
.avoid-card:hover { transform:translateY(-2px); }
.badge-good { display:inline-block; color:white; padding:2px 8px; border-radius:999px; font-size:0.65rem; margin-top:6px; }

/* AI addition preview card */
.ai-addition-card { background:var(--card); border:2px dashed #ffa726; border-radius:14px; padding:10px 12px; margin-bottom:6px; display:flex; align-items:center; gap:10px; }
.ai-addition-card .plant-emoji { font-size:1.4rem; }
.ai-addition-card .cell-label { font-size:0.68rem; color:var(--muted); }
.ai-accept-all { background:#e8f5e9; border:1px solid #c8e6c9; border-radius:8px; padding:8px 14px; color:var(--green); font-weight:600; font-size:0.85rem; cursor:pointer; }

.step-badge { display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:var(--green); color:white; font-size:0.75rem; font-weight:700; margin-right:8px; flex-shrink:0; }
.step-row { display:flex; align-items:center; margin-bottom:6px; }
.step-label { font-size:0.88rem; font-weight:600; color:var(--text); }

div.stButton > button { border-radius:8px; background:white; color:var(--green); border:1px solid #c8e6c9; transition:all 0.15s; }
div.stButton > button:hover { background:var(--green) !important; color:white !important; transform:scale(0.98); }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div class='sidebar-badge'><div style='font-weight:800;color:#2e7d32;font-size:1.2rem;'>🌿 SeedSage</div>"
        "<div style='font-size:0.82rem;color:#667066;'>Companion planting explorer</div></div>",
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_Dashboard.py",     label="📊 Dashboard",   use_container_width=True)
    st.page_link("pages/2_Calendar.py",      label="🗓️ Calendar",     use_container_width=True)
    st.page_link("pages/3_Companions.py",    label="🌻 Companions",   use_container_width=True)
    st.page_link("pages/4_GardenJournal.py", label="📓 Journal",      use_container_width=True)
    st.divider()
    st.markdown("**Benefit Key**")
    for _, info in BENEFIT_LABELS.items():
        st.markdown(
            f"<div style='font-size:0.78rem;margin-bottom:3px;'>"
            f"<span style='background:{info['color']};color:white;padding:1px 7px;border-radius:999px;'>"
            f"{info['icon']} {info['label']}</span></div>",
            unsafe_allow_html=True,
        )

# ── HEADER ───────────────────────────────────────────────────
st.markdown(
    "<div class='hero'>"
    "<h1 style='color:#2e7d32;margin:0;'>🌻 Companion Planting Explorer</h1>"
    "<p style='color:#666;margin:0.3rem 0 0;'>Discover which plants help each other, "
    "and design your garden bed with AI companion guidance.</p></div>",
    unsafe_allow_html=True,
)

user_plants_list = sorted(list(user.get("plants", {}).keys()))

if len(user_plants_list) >= 2:
    conflicts, guilds = detect_conflicts(user_plants_list)
    c1,c2,c3 = st.columns(3)
    for col, lbl, val in [
        (c1,"Plants",     len(user_plants_list)),
        (c2,"Good pairs", len(guilds)),
        (c3,"Conflicts",  len(conflicts)),
    ]:
        col.markdown(f"<div class='stat-card'><div class='stat-label'>{lbl}</div>"
                     f"<div class='stat-value'>{val}</div></div>", unsafe_allow_html=True)

# ── TABS ─────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "✅ Good vs Bad Neighbors",
    "📊 Compatibility Matrix",
    "🌱 Garden Layout",
])

# ════════════════════════════════════════════════════════════
# TAB 1 — Good vs Bad Neighbors
# ════════════════════════════════════════════════════════════
with tab1:
    st.markdown("<div class='section-header'>Good Neighbor / Bad Neighbor Labels</div>", unsafe_allow_html=True)
    if not user_plants_list:
        st.info("No plants in your garden yet. Add some on the Dashboard.")
    else:
        for plant in user_plants_list:
            with st.expander(f"{get_plant_emoji(plant)} {plant.capitalize()}"):
                data = get_companions(plant)
                if not data.get("companions") and not data.get("avoid"):
                    data = safe_enrich(plant, user.get("postcode","UK"))
                cols = st.columns(2)
                with cols[0]:
                    st.markdown("##### ✅ Good Neighbors")
                    for c in data.get("companions",[]):
                        b_info = BENEFIT_LABELS.get(c.get("benefit","growth"),
                                                    {"label":"General","icon":"🌿","color":"#4caf50"})
                        st.markdown(f"""<div class='companion-card'>
                            <b>{get_plant_emoji(c['plant'])} {html.escape(c['plant'].capitalize())}</b><br>
                            <span style='font-size:0.82rem;'>{html.escape(c.get('reason',''))}</span><br>
                            <span class='badge-good' style='background:{b_info["color"]};'>{b_info["icon"]} {b_info["label"]}</span>
                        </div>""", unsafe_allow_html=True)
                with cols[1]:
                    st.markdown("##### ❌ Bad Neighbors")
                    for c in data.get("avoid",[]):
                        st.markdown(f"""<div class='avoid-card'>
                            <b>{get_plant_emoji(c['plant'])} {html.escape(c['plant'].capitalize())}</b><br>
                            <span style='font-size:0.82rem;'>{html.escape(c.get('reason',''))}</span>
                        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 2 — Compatibility Matrix
# ════════════════════════════════════════════════════════════
with tab2:
    st.markdown("<div class='section-header'>Garden Compatibility Matrix</div>", unsafe_allow_html=True)
    if len(user_plants_list) < 2:
        st.info("Add at least 2 plants to see the matrix.")
    else:
        st.caption("✅ Good companion &nbsp;&nbsp; ❌ Avoid &nbsp;&nbsp; ⬜ Neutral")
        hcols = st.columns(len(user_plants_list) + 1)
        hcols[0].markdown("")
        for i, plant in enumerate(user_plants_list):
            hcols[i+1].markdown(
                f"<div style='text-align:center;font-weight:700;font-size:0.82rem;'>"
                f"{get_plant_emoji(plant)}<br>{html.escape(plant[:10].capitalize())}</div>",
                unsafe_allow_html=True,
            )
        for pa in user_plants_list:
            rcols = st.columns(len(user_plants_list) + 1)
            rcols[0].markdown(f"**{pa.capitalize()}**")
            for j, pb in enumerate(user_plants_list):
                with rcols[j+1]:
                    if pa == pb:
                        st.markdown("<div style='text-align:center;color:#aaa;'>—</div>", unsafe_allow_html=True)
                    else:
                        rel = get_pairing_info(pa, pb).get("relationship","neutral")
                        icon = "✅" if rel=="companion" else "❌" if rel=="avoid" else "⬜"
                        color = "#2e7d32" if rel=="companion" else "#d32f2f" if rel=="avoid" else "#aaa"
                        st.markdown(f"<div style='text-align:center;font-size:1.1rem;color:{color};font-weight:700;'>{icon}</div>",
                                    unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 3 — Garden Layout (NEW: AI fill around user's plants)
# ════════════════════════════════════════════════════════════
with tab3:
    st.markdown("<div class='section-header'>🌱 Design Your Garden Bed</div>", unsafe_allow_html=True)
    st.markdown(
        "Place your plants in the grid, then tell the AI how many more to add — "
        "it will choose the best **companion plants** to fill the remaining spots based on what you've already planted.",
        unsafe_allow_html=True,
    )

    init_layout_state()
    draft = st.session_state.layout_draft
    rows  = int(draft["rows"])
    cols  = int(draft["cols"])
    cells = dict(draft["cells"])
    user_cell_keys = set(draft.get("user_cells", set()))

    plant_names = sorted(list(user.get("plants",{}).keys()))
    if not plant_names:
        st.warning("No plants added yet. Add plants on the Dashboard first.")
        st.stop()

    # ── STEP 1: Configure grid ────────────────────────────────
    st.markdown("<div class='step-row'><span class='step-badge'>1</span><span class='step-label'>Set up your grid</span></div>",
                unsafe_allow_html=True)

    col_r, col_c, col_clear = st.columns([1,1,2])
    with col_r:
        new_rows = st.number_input("Rows", 2, 12, rows, key="grid_rows")
    with col_c:
        new_cols = st.number_input("Columns", 2, 12, cols, key="grid_cols")
    with col_clear:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("Apply size", use_container_width=True):
            new_cells = resize_cells(cells, rows, cols, new_rows, new_cols)
            st.session_state.layout_draft = {
                "rows": new_rows, "cols": new_cols,
                "cells": new_cells, "user_cells": user_cell_keys,
            }
            persist_layout()
            clear_ai_additions()
            st.rerun()
        if c2.button("Clear all", use_container_width=True):
            st.session_state.layout_draft = {
                "rows": rows, "cols": cols,
                "cells": {f"{r},{c}":"" for r in range(rows) for c in range(cols)},
                "user_cells": set(),
            }
            persist_layout()
            clear_ai_additions()
            st.rerun()

    capacity     = rows * cols
    placed_count = len([v for v in cells.values() if v])
    empty_count  = capacity - placed_count
    st.caption(f"Grid: {rows}×{cols} = {capacity} cells · {placed_count} placed · {empty_count} empty")

    st.divider()

    # ── STEP 2: Place your plants ─────────────────────────────
    st.markdown("<div class='step-row'><span class='step-badge'>2</span><span class='step-label'>Place your plants in the grid</span></div>",
                unsafe_allow_html=True)
    st.caption("Select a plant for each cell, or leave empty. Your placements are shown with a green border.")

    with st.form("layout_editor"):
        new_cells = {}
        plant_opts = ["(empty)"] + plant_names
        for r in range(rows):
            rcols = st.columns(cols)
            for c in range(cols):
                key     = f"{r},{c}"
                current = cells.get(key,"")
                idx     = plant_opts.index(current) if current in plant_opts else 0
                with rcols[c]:
                    # Show emoji above selector for visual feedback
                    emoji = get_plant_emoji(current) if current else "·"
                    st.markdown(f"<div style='text-align:center;font-size:1.3rem;'>{emoji}</div>",
                                unsafe_allow_html=True)
                    sel = st.selectbox(
                        key,
                        options=plant_opts,
                        index=idx,
                        key=f"cell_{r}_{c}",
                        label_visibility="collapsed",
                    )
                    new_cells[key] = "" if sel == "(empty)" else sel

        if st.form_submit_button("💾 Save my layout", use_container_width=True):
            new_user_keys = {k for k,v in new_cells.items() if v}
            st.session_state.layout_draft = {
                "rows": rows, "cols": cols,
                "cells": new_cells,
                "user_cells": new_user_keys,
            }
            persist_layout()
            clear_ai_additions()
            st.success(f"Saved {len(new_user_keys)} plant(s). Now ask the AI to fill the rest!")
            st.rerun()

    st.divider()

    # ── STEP 3: Ask AI to fill around your plants ─────────────
    st.markdown("<div class='step-row'><span class='step-badge'>3</span><span class='step-label'>Let AI fill in the best companion plants</span></div>",
                unsafe_allow_html=True)

    current_empty = [f"{r},{c}" for r in range(rows) for c in range(cols)
                     if not cells.get(f"{r},{c}","")]

    if not current_empty:
        st.success("Your grid is full! Clear some cells to let the AI suggest additions.")
    else:
        col_num, col_plants, col_btn = st.columns([1, 2, 1])

        with col_num:
            n_to_add = st.number_input(
                "How many plants to add?",
                min_value=1,
                max_value=len(current_empty),
                value=min(3, len(current_empty)),
                help=f"Up to {len(current_empty)} empty cells available",
            )

        with col_plants:
            # Option: also suggest plants not in their garden
            use_extra = st.checkbox(
                "Include companion plants not yet in my garden",
                value=True,
                help="AI will also suggest plants from the companion database that would work well here",
            )
            # Build extra companion candidates from DB
            extra_companions = []
            if use_extra and cells:
                placed_plants = list({v for v in cells.values() if v})
                from services.companion_service import get_companions as gc
                seen = set(plant_names)
                for pp in placed_plants:
                    for comp in gc(pp).get("companions", []):
                        name = comp["plant"]
                        if name not in seen:
                            extra_companions.append(name)
                            seen.add(name)
                extra_companions = extra_companions[:12]   # cap at 12 extra options

        with col_btn:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            run_ai = st.button("🤖 AI Fill", use_container_width=True,
                               help="AI will choose the best companion plants for the empty cells")

        # Show what extra companions the AI can use
        if extra_companions:
            extras_str = " · ".join(
                f"{get_plant_emoji(p)} {p.capitalize()}" for p in extra_companions[:8]
            )
            st.caption(f"Extra companions available to AI: {extras_str}"
                       + (f" +{len(extra_companions)-8} more" if len(extra_companions) > 8 else ""))

        if run_ai:
            if not any(cells.values()):
                st.warning("Place at least one plant first (Step 2), then ask AI to fill around it.")
            else:
                with st.spinner(f"Finding the best {n_to_add} companion plant(s)…"):
                    additions, justification, error = ai_fill_around_user(
                        cells, user_cell_keys, n_to_add,
                        plant_names, rows, cols,
                        extra_companions=extra_companions if use_extra else [],
                    )
                if error:
                    st.error(error)
                else:
                    st.session_state.ai_additions         = additions
                    st.session_state.ai_add_justification = justification
                    st.session_state.rejected_ai_cells    = set()
                    st.rerun()

    # ── AI ADDITIONS REVIEW ───────────────────────────────────
    pending = st.session_state.get("ai_additions", {})
    rejected = st.session_state.get("rejected_ai_cells", set())
    pending_active = {k:v for k,v in pending.items() if k not in rejected}

    if pending:
        st.markdown("---")
        st.markdown("### 🤖 AI Suggestions — Review & Accept")
        st.info(f"💬 {st.session_state.get('ai_add_justification','')}")

        # Combined preview: user cells + pending AI additions
        preview_cells = dict(cells)
        for k,v in pending_active.items():
            if k not in preview_cells or not preview_cells[k]:
                preview_cells[k] = v

        # Board with orange borders for AI cells
        st.plotly_chart(
            build_board_figure(cells, rows, cols,
                               highlight_cells=pending_active,
                               rejected_cells=rejected),
            use_container_width=True,
        )

        # Per-addition review cards
        st.markdown(f"**{len(pending_active)} suggestion(s) to review:**")
        for cell_key, plant in sorted(pending.items()):
            if cell_key in rejected:
                continue
            r2, c2   = map(int, cell_key.split(","))
            emoji    = get_plant_emoji(plant)
            color    = get_plant_color(plant)

            # Show what neighbours it's good/bad with
            neighbour_plants = [cells.get(nb,"") for nb in orthogonal_neighbors(cell_key, rows, cols)]
            neighbour_plants = [p for p in neighbour_plants if p]
            good_with = [p for p in neighbour_plants
                         if get_pairing_info(plant,p).get("relationship")=="companion"]
            bad_with  = [p for p in neighbour_plants
                         if get_pairing_info(plant,p).get("relationship")=="avoid"]

            col_card, col_acc, col_rej = st.columns([4, 1, 1])
            with col_card:
                good_str = f"<span style='color:#2e7d32;'>✅ Good with: {', '.join(good_with)}</span>" if good_with else ""
                bad_str  = f"<span style='color:#c62828;'>❌ Conflicts: {', '.join(bad_with)}</span>"  if bad_with  else ""
                new_badge = ""
                if plant not in plant_names:
                    new_badge = "<span style='background:#e3f2fd;color:#1565c0;font-size:0.62rem;padding:1px 6px;border-radius:8px;margin-left:6px;'>new plant</span>"
                st.markdown(
                    f"""<div class='ai-addition-card'>
                        <span class='plant-emoji'>{emoji}</span>
                        <div style='flex:1;'>
                            <div style='font-size:0.9rem;font-weight:700;color:#1a1a1a;'>
                                {plant.capitalize()}{new_badge}
                            </div>
                            <div class='cell-label'>Row {r2}, Col {c2}</div>
                            <div style='font-size:0.75rem;margin-top:3px;'>{good_str} {bad_str}</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with col_acc:
                if st.button("✓ Keep", key=f"keep_{cell_key}", use_container_width=True):
                    # Accept just this one
                    new_plant_entry = {cell_key: plant}
                    merged = dict(cells)
                    merged[cell_key] = plant
                    new_user_keys = set(user_cell_keys) | {cell_key}
                    # Add to garden if new plant
                    if plant not in user.get("plants",{}):
                        import datetime
                        user["plants"][plant] = {
                            "added_on": datetime.date.today(),
                            "actual_planted": datetime.date.today().isoformat(),
                            "milestones": [],
                        }
                    st.session_state.layout_draft = {
                        "rows": rows, "cols": cols,
                        "cells": merged,
                        "user_cells": new_user_keys,
                    }
                    del st.session_state.ai_additions[cell_key]
                    persist_layout()
                    st.rerun()
            with col_rej:
                if st.button("✗ Skip", key=f"rej_{cell_key}", use_container_width=True):
                    st.session_state.rejected_ai_cells.add(cell_key)
                    st.rerun()

        # Accept all / reject all buttons
        st.markdown("")
        ca, cr = st.columns(2)
        if ca.button("✅ Accept all suggestions", use_container_width=True):
            import datetime
            merged = dict(cells)
            for k,v in pending_active.items():
                merged[k] = v
                if v not in user.get("plants",{}):
                    user["plants"][v] = {
                        "added_on": datetime.date.today(),
                        "actual_planted": datetime.date.today().isoformat(),
                        "milestones": [],
                    }
            new_user_keys = set(user_cell_keys) | set(pending_active.keys())
            st.session_state.layout_draft = {
                "rows": rows, "cols": cols,
                "cells": merged,
                "user_cells": new_user_keys,
            }
            clear_ai_additions()
            persist_layout()
            save_current_user()
            st.success(f"Added {len(pending_active)} plant(s) to your garden layout!")
            st.rerun()

        if cr.button("✗ Reject all", use_container_width=True):
            clear_ai_additions()
            st.rerun()

    # ── STEP 4: Full AI replace (existing feature, now optional) ──
    st.divider()
    st.markdown("<div class='step-row'><span class='step-badge'>4</span>"
                "<span class='step-label'>Or: let AI design the entire layout from scratch</span></div>",
                unsafe_allow_html=True)
    st.caption("Set quantities below and AI will arrange everything optimally.")

    qty_cols = st.columns(min(4, max(1, len(plant_names))))
    plant_quantities = {}
    for i, p in enumerate(plant_names):
        with qty_cols[i % 4]:
            plant_quantities[p] = st.number_input(
                p.capitalize(), 0, 20,
                value=1, step=1, key=f"qty_{p}",
            )
    total_q = sum(plant_quantities.values())
    active_quantities = {p:q for p,q in plant_quantities.items() if q > 0}

    if total_q > capacity:
        st.error(f"Too many plants ({total_q}) for grid size ({capacity} cells). Increase grid or reduce quantities.")
    elif total_q > 0:
        if st.button("🤖 AI Full Layout", use_container_width=False):
            with st.spinner("Designing full layout…"):
                suggestion, just, err = ai_full_layout(active_quantities, cells, rows, cols)
            if err:
                st.error(err)
            else:
                # Store in session_state so the preview + Apply button survive the next rerun
                st.session_state.full_layout_suggestion    = suggestion
                st.session_state.full_layout_justification = just
                st.rerun()

    # ── Full layout preview — rendered unconditionally so Apply survives reruns ──
    if st.session_state.get("full_layout_suggestion"):
        suggestion = st.session_state.full_layout_suggestion
        just       = st.session_state.full_layout_justification

        st.markdown("#### ✨ AI Full Layout Suggestion")
        st.info(just)
        st.plotly_chart(
            build_board_figure(suggestion, rows, cols),
            use_container_width=True,
        )
        good2, bad2 = analyze_adjacent_pairs(suggestion, rows, cols)
        if good2: st.success(f"🌿 Good pairs: {', '.join(set(good2[:4]))}")
        if bad2:  st.warning(f"⚠️ Conflicts: {', '.join(set(bad2[:4]))}")

        col_apply, col_discard = st.columns(2)
        if col_apply.button("✅ Apply this full layout", use_container_width=True, key="apply_full"):
            new_user_keys = {k for k, v in suggestion.items() if v}
            st.session_state.layout_draft = {
                "rows": rows, "cols": cols,
                "cells": suggestion,
                "user_cells": new_user_keys,
            }
            persist_layout()
            clear_ai_additions()
            # Clear the pending suggestion
            st.session_state.pop("full_layout_suggestion", None)
            st.session_state.pop("full_layout_justification", None)
            st.success("✅ Full layout applied to your garden!")
            st.rerun()

        if col_discard.button("✗ Discard suggestion", use_container_width=True, key="discard_full"):
            st.session_state.pop("full_layout_suggestion", None)
            st.session_state.pop("full_layout_justification", None)
            st.rerun()

    # ── CURRENT BOARD (always visible at bottom) ──────────────
    st.divider()
    st.markdown("#### 🌿 Your Current Garden Layout")
    current_fig = build_board_figure(cells, rows, cols, highlight_cells={}, rejected_cells=set())
    st.plotly_chart(current_fig, use_container_width=True)
    render_health_banner(cells, rows, cols)