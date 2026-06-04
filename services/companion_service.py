"""
services/companion_service.py

Loads companion planting data from multiple sources:
- Hardcoded UK knowledge base (BUILTIN_DATA)
- Local CSV (data/companion.csv)
- Scraped UK gardening sites (First Tunnels, Soil Association, Thrive)
- AI enrichment (OpenRouter) with cache

All data is merged with priority: builtin > CSV > scraped > AI.
Scraped data is cached for 7 days to avoid repeated requests.
"""

import os
import json
import re
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CSV_PATH = os.path.join(BASE_DIR, "data", "companion.csv")
SCRAPE_CACHE_PATH = os.path.join(BASE_DIR, "data", "companion_scrape_cache.json")
SCRAPE_REFRESH_DAYS = 7

# ---------------------------------------------------------------------------
# Benefit categories with display info (same as original)
# ---------------------------------------------------------------------------
BENEFIT_LABELS = {
    "pest_control": {"label": "Pest Control", "icon": "🐛", "color": "#ef5350"},
    "nitrogen": {"label": "Nitrogen Fixing", "icon": "🌿", "color": "#66bb6a"},
    "pollination": {"label": "Pollination", "icon": "🐝", "color": "#ffa726"},
    "soil": {"label": "Soil Health", "icon": "🌱", "color": "#8d6e63"},
    "moisture": {"label": "Moisture", "icon": "💧", "color": "#42a5f5"},
    "space": {"label": "Space Use", "icon": "📐", "color": "#ab47bc"},
    "structure": {"label": "Structure", "icon": "🌻", "color": "#26a69a"},
    "growth": {"label": "Growth Boost", "icon": "⬆️", "color": "#2e7d32"},
}

# ---------------------------------------------------------------------------
# Extended built‑in knowledge base (covers the most common UK veg garden plants)
# ---------------------------------------------------------------------------
BUILTIN_DATA = {
    "tomato": {
        "companions": [
            {"plant": "basil", "reason": "Repels aphids and whitefly; improves tomato flavour", "benefit": "pest_control"},
            {"plant": "carrot", "reason": "Loosens soil around tomato roots", "benefit": "soil"},
            {"plant": "marigold", "reason": "Deters nematodes and whitefly with strong scent", "benefit": "pest_control"},
            {"plant": "parsley", "reason": "Attracts predatory insects that eat tomato pests", "benefit": "pest_control"},
            {"plant": "borage", "reason": "Repels tomato hornworm; attracts pollinators", "benefit": "pollination"},
            {"plant": "lettuce", "reason": "Grows happily in tomato shade; maximises space", "benefit": "space"},
        ],
        "avoid": [
            {"plant": "fennel", "reason": "Inhibits tomato growth with allelopathic chemicals"},
            {"plant": "brassica", "reason": "Compete for nutrients; attract similar pests"},
            {"plant": "corn", "reason": "Both attract similar pests including aphids"},
        ]
    },
    "basil": {
        "companions": [
            {"plant": "tomato", "reason": "Classic pairing — repels pests, improves flavour", "benefit": "pest_control"},
            {"plant": "pepper", "reason": "Mutual pest deterrence; basil repels aphids", "benefit": "pest_control"},
            {"plant": "oregano", "reason": "Compatible growth habits; both Mediterranean herbs", "benefit": "growth"},
            {"plant": "asparagus", "reason": "Basil repels asparagus beetles", "benefit": "pest_control"},
        ],
        "avoid": [
            {"plant": "sage", "reason": "Sage inhibits basil growth when planted too close"},
            {"plant": "thyme", "reason": "Different moisture requirements cause competition"},
        ]
    },
    "carrot": {
        "companions": [
            {"plant": "leek", "reason": "Leeks deter carrot fly; carrots deter leek moth — perfect swap", "benefit": "pest_control"},
            {"plant": "rosemary", "reason": "Strong scent confuses carrot fly", "benefit": "pest_control"},
            {"plant": "onion", "reason": "Onion scent masks carrots from carrot fly", "benefit": "pest_control"},
            {"plant": "tomato", "reason": "Tomato roots break up soil for carrots", "benefit": "soil"},
            {"plant": "lettuce", "reason": "Shade from lettuce keeps carrot soil moist", "benefit": "moisture"},
        ],
        "avoid": [
            {"plant": "dill", "reason": "Cross-pollinates with carrots; reduces seed quality"},
            {"plant": "parsnip", "reason": "Compete for identical nutrients and space"},
        ]
    },
    "lettuce": {
        "companions": [
            {"plant": "carrot", "reason": "Carrots loosen soil; lettuce shades to retain moisture", "benefit": "soil"},
            {"plant": "radish", "reason": "Radish matures fast; acts as a sacrificial crop for slugs", "benefit": "pest_control"},
            {"plant": "strawberry", "reason": "Mutual ground cover; lettuce shades strawberry roots", "benefit": "moisture"},
            {"plant": "chives", "reason": "Chives deter aphids which attack lettuce", "benefit": "pest_control"},
            {"plant": "mint", "reason": "Repels slugs and aphids near lettuce", "benefit": "pest_control"},
        ],
        "avoid": [
            {"plant": "celery", "reason": "Celery inhibits lettuce germination"},
            {"plant": "parsley", "reason": "Parsley stunts lettuce growth"},
        ]
    },
    "courgette": {
        "companions": [
            {"plant": "sweetcorn", "reason": "Three Sisters classic — corn provides support structure", "benefit": "structure"},
            {"plant": "bean", "reason": "Three Sisters — beans fix nitrogen courgette needs", "benefit": "nitrogen"},
            {"plant": "nasturtium", "reason": "Attracts aphids away from courgette as trap crop", "benefit": "pest_control"},
            {"plant": "borage", "reason": "Deters pests; attracts pollinators for better fruiting", "benefit": "pollination"},
            {"plant": "marigold", "reason": "Strong scent deters whitefly and squash bugs", "benefit": "pest_control"},
        ],
        "avoid": [
            {"plant": "potato", "reason": "Both are heavy feeders competing for potassium"},
            {"plant": "fennel", "reason": "Fennel inhibits most vegetables including courgette"},
        ]
    },
    "bean": {
        "companions": [
            {"plant": "sweetcorn", "reason": "Beans fix nitrogen; corn provides climbing structure", "benefit": "nitrogen"},
            {"plant": "courgette", "reason": "Three Sisters companion; nitrogen benefit", "benefit": "nitrogen"},
            {"plant": "carrot", "reason": "Beans fix nitrogen that benefits carrots", "benefit": "nitrogen"},
            {"plant": "cucumber", "reason": "Similar growth conditions; beans fix shared nitrogen", "benefit": "nitrogen"},
        ],
        "avoid": [
            {"plant": "onion", "reason": "Onion family stunts bean growth significantly"},
            {"plant": "fennel", "reason": "Allelopathic chemicals in fennel inhibit beans"},
            {"plant": "garlic", "reason": "Garlic inhibits bean nitrogen fixation"},
        ]
    },
    "cucumber": {
        "companions": [
            {"plant": "bean", "reason": "Beans fix nitrogen; cucumbers are heavy feeders", "benefit": "nitrogen"},
            {"plant": "corn", "reason": "Corn provides shade and windbreak for cucumbers", "benefit": "structure"},
            {"plant": "nasturtium", "reason": "Trap crop for aphids; keeps cucumbers clean", "benefit": "pest_control"},
            {"plant": "sunflower", "reason": "Provides shade; cucumbers climb sunflower stems", "benefit": "structure"},
            {"plant": "radish", "reason": "Deters cucumber beetles", "benefit": "pest_control"},
        ],
        "avoid": [
            {"plant": "potato", "reason": "Both susceptible to blight; increases disease risk"},
            {"plant": "aromatic herbs", "reason": "Strong herb scents can inhibit cucumber growth"},
        ]
    },
    "pepper": {
        "companions": [
            {"plant": "basil", "reason": "Repels aphids and spider mites from peppers", "benefit": "pest_control"},
            {"plant": "carrot", "reason": "Carrots aerate soil around pepper roots", "benefit": "soil"},
            {"plant": "tomato", "reason": "Similar growing conditions; mutual pest deterrence", "benefit": "pest_control"},
            {"plant": "marigold", "reason": "Deters nematodes in soil that attack pepper roots", "benefit": "pest_control"},
        ],
        "avoid": [
            {"plant": "fennel", "reason": "Fennel inhibits pepper growth"},
            {"plant": "brassica", "reason": "Different nutrient needs cause competition"},
        ]
    },
    "onion": {
        "companions": [
            {"plant": "carrot", "reason": "Classic pairing — mutual pest deterrence (carrot fly vs onion fly)", "benefit": "pest_control"},
            {"plant": "lettuce", "reason": "Onion scent deters lettuce pests", "benefit": "pest_control"},
            {"plant": "tomato", "reason": "Onions deter many tomato pests", "benefit": "pest_control"},
            {"plant": "chamomile", "reason": "Improves onion growth and flavour", "benefit": "growth"},
        ],
        "avoid": [
            {"plant": "bean", "reason": "Onions stunt bean growth significantly"},
            {"plant": "pea", "reason": "Alliums inhibit pea growth"},
            {"plant": "asparagus", "reason": "Competition; alliums inhibit asparagus"},
        ]
    },
    "pea": {
        "companions": [
            {"plant": "carrot", "reason": "Peas fix nitrogen; carrots benefit from it", "benefit": "nitrogen"},
            {"plant": "turnip", "reason": "Peas improve soil nitrogen for turnips", "benefit": "nitrogen"},
            {"plant": "radish", "reason": "Radish deters aphids that attack peas", "benefit": "pest_control"},
            {"plant": "mint", "reason": "Repels pea moth and aphids", "benefit": "pest_control"},
            {"plant": "lettuce", "reason": "Grows in pea shade; peas fix nitrogen", "benefit": "nitrogen"},
        ],
        "avoid": [
            {"plant": "onion", "reason": "Alliums inhibit pea growth and nitrogen fixation"},
            {"plant": "garlic", "reason": "Stunts pea growth"},
        ]
    },
    "marigold": {
        "companions": [
            {"plant": "tomato", "reason": "Deters whitefly and nematodes", "benefit": "pest_control"},
            {"plant": "cucumber", "reason": "General pest deterrent in the vegetable garden", "benefit": "pest_control"},
            {"plant": "potato", "reason": "Deters Colorado beetle and nematodes", "benefit": "pest_control"},
            {"plant": "bean", "reason": "Repels Mexican bean beetle", "benefit": "pest_control"},
        ],
        "avoid": []
    },
    "mint": {
        "companions": [
            {"plant": "tomato", "reason": "Repels aphids and spider mites", "benefit": "pest_control"},
            {"plant": "pea", "reason": "Deters pea moth", "benefit": "pest_control"},
            {"plant": "lettuce", "reason": "Slug and aphid deterrent near lettuce", "benefit": "pest_control"},
            {"plant": "brassica", "reason": "Repels cabbage white butterfly", "benefit": "pest_control"},
        ],
        "avoid": [
            {"plant": "parsley", "reason": "Mint's aggressive spreading overwhelms parsley"},
        ]
    },
    "rosemary": {
        "companions": [
            {"plant": "carrot", "reason": "Scent deters carrot fly", "benefit": "pest_control"},
            {"plant": "bean", "reason": "Repels bean beetles", "benefit": "pest_control"},
            {"plant": "brassica", "reason": "Deters cabbage moth with strong scent", "benefit": "pest_control"},
            {"plant": "sage", "reason": "Compatible Mediterranean herbs; mutual benefit", "benefit": "growth"},
        ],
        "avoid": [
            {"plant": "cucumber", "reason": "Strong rosemary scent inhibits cucumber"},
            {"plant": "potato", "reason": "Different water needs; competition for resources"},
        ]
    },
    "potato": {
        "companions": [
            {"plant": "bean", "reason": "Beans fix nitrogen; potatoes benefit", "benefit": "nitrogen"},
            {"plant": "horseradish", "reason": "Repels Colorado beetle; improves disease resistance", "benefit": "pest_control"},
            {"plant": "marigold", "reason": "Deters Colorado beetle and nematodes", "benefit": "pest_control"},
        ],
        "avoid": [
            {"plant": "tomato", "reason": "Both in nightshade family; spread blight to each other"},
            {"plant": "cucumber", "reason": "Both susceptible to similar diseases"},
            {"plant": "fennel", "reason": "Fennel inhibits potato growth"},
            {"plant": "sunflower", "reason": "Sunflowers inhibit potato growth"},
        ]
    }
}
# ---------------------------------------------------------------------------
# CSV loading (unchanged logic)
# ---------------------------------------------------------------------------
def _load_csv_data() -> dict:
    if not os.path.exists(CSV_PATH):
        return {}
    try:
        df = pd.read_csv(CSV_PATH)
        df["Plant_A"] = df["Plant_A"].str.lower().str.strip()
        df["Plant_B"] = df["Plant_B"].str.lower().str.strip()
        df["Relationship"] = df["Relationship"].str.lower().str.strip()
        df["Reason"] = df["Reason"].str.strip()
        df["Reason"] = df["Reason"].str.split("[").str[0].str.strip()
        df = df.drop_duplicates()
        csv_data = {}
        for _, row in df.iterrows():
            plant_a = row["Plant_A"]
            plant_b = row["Plant_B"]
            rel = row["Relationship"]
            reason = row["Reason"]
            for plant, partner in [(plant_a, plant_b), (plant_b, plant_a)]:
                if plant not in csv_data:
                    csv_data[plant] = {"companions": [], "avoid": []}
                entry = {"plant": partner, "reason": reason}
                if rel == "companion":
                    entry["benefit"] = "growth"
                    if entry not in csv_data[plant]["companions"]:
                        csv_data[plant]["companions"].append(entry)
                elif rel == "avoid":
                    if entry not in csv_data[plant]["avoid"]:
                        csv_data[plant]["avoid"].append(entry)
        return csv_data
    except Exception as e:
        print(f"CSV load error: {e}")
        return {}

# ---------------------------------------------------------------------------
# External scraping (UK sources)
# ---------------------------------------------------------------------------
def _clean_companion_text(raw_text: str) -> list[str]:
    """Extract plant names from RHS‑style prose."""
    fillers = [
        'suggested as a companion for', 'thrive when planted near',
        'keep them away from', 'plant with', 'avoid planting near'
    ]
    cleaned = raw_text.lower()
    for f in fillers:
        cleaned = cleaned.replace(f, ',')
    # Split on common delimiters
    parts = re.split(r'[;,\n]', cleaned)
    plants = []
    for p in parts:
        p = p.strip().strip('.').strip()
        if len(p) > 2 and not p.startswith(('and', 'or', 'the', 'a', 'an')):
            plants.append(p)
    return plants

def scrape_first_tunnels() -> list[dict]:
    """Scrape First Tunnels UK companion chart (HTML table)."""
    url = "https://www.firsttunnels.co.uk/companion-planting-chart"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Look for a table with class or id – adjust as needed
        table = soup.find('table')
        if not table:
            return []
        data = []
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                plant = cells[0].get_text().strip().lower()
                companions_raw = cells[1].get_text().strip()
                plants_list = _clean_companion_text(companions_raw)
                data.append({
                    "plant": plant,
                    "companions": [{"plant": p, "reason": "UK companion planting guide", "benefit": "growth"} for p in plants_list if p],
                    "avoid": []
                })
        return data
    except Exception as e:
        print(f"First Tunnels scrape error: {e}")
        return []

def scrape_soil_association() -> list[dict]:
    """Scrape Soil Association PDF summary (via web page)."""
    # Soil Association doesn't have a simple table, but we can scrape their 'companion planting' blog
    url = "https://www.soilassociation.org/companion-planting"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Find headers with plant names and following paragraphs
        data = []
        for header in soup.find_all(['h2', 'h3']):
            plant = header.get_text().strip().lower()
            if any(word in plant for word in ['companion', 'planting', 'guide']):
                continue
            # Get next sibling paragraph
            para = header.find_next_sibling('p')
            if para:
                text = para.get_text().lower()
                if 'plant with' in text or 'companion' in text:
                    plants = _clean_companion_text(text)
                    data.append({
                        "plant": plant,
                        "companions": [{"plant": p, "reason": "Soil Association organic recommendation", "benefit": "pest_control"} for p in plants if p],
                        "avoid": []
                    })
        return data
    except Exception as e:
        print(f"Soil Association scrape error: {e}")
        return []

def scrape_thrive() -> list[dict]:
    """Scrape Thrive.org.uk companion gardening pages."""
    url = "https://www.thrive.org.uk/companion-planting"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Thrive often uses lists
        data = []
        for ul in soup.find_all('ul'):
            prev = ul.find_previous_sibling(['h2', 'h3', 'p'])
            if prev and prev.get_text():
                context = prev.get_text().lower()
                plant_match = re.search(r'(\w+)\s+companions', context)
                if plant_match:
                    plant = plant_match.group(1)
                    items = ul.find_all('li')
                    companions = [li.get_text().strip().lower() for li in items]
                    data.append({
                        "plant": plant,
                        "companions": [{"plant": p, "reason": "Thrive gardening guide", "benefit": "growth"} for p in companions if p],
                        "avoid": []
                    })
        return data
    except Exception as e:
        print(f"Thrive scrape error: {e}")
        return []

def _get_scraped_data() -> dict:
    """Load scraped data from cache or perform fresh scrape."""
    # Check cache
    if os.path.exists(SCRAPE_CACHE_PATH):
        with open(SCRAPE_CACHE_PATH, 'r') as f:
            cache = json.load(f)
        last_update = datetime.fromisoformat(cache.get("last_update", "1970-01-01"))
        if datetime.now() - last_update < timedelta(days=SCRAPE_REFRESH_DAYS):
            # Convert cache back to data dict
            scraped = {}
            for item in cache.get("data", []):
                plant = item["plant"]
                scraped[plant] = {
                    "companions": item["companions"],
                    "avoid": item["avoid"]
                }
            return scraped

    # Scrape all sources
    all_scraped = {}
    sources = [scrape_first_tunnels, scrape_soil_association, scrape_thrive]
    for source in sources:
        for entry in source():
            plant = entry["plant"]
            if plant not in all_scraped:
                all_scraped[plant] = {"companions": [], "avoid": []}
            # Avoid duplicates
            for c in entry["companions"]:
                if c not in all_scraped[plant]["companions"]:
                    all_scraped[plant]["companions"].append(c)
            for a in entry["avoid"]:
                if a not in all_scraped[plant]["avoid"]:
                    all_scraped[plant]["avoid"].append(a)

    # Save to cache
    cache_data = {
        "last_update": datetime.now().isoformat(),
        "data": [{"plant": k, "companions": v["companions"], "avoid": v["avoid"]} for k, v in all_scraped.items()]
    }
    os.makedirs(os.path.dirname(SCRAPE_CACHE_PATH), exist_ok=True)
    with open(SCRAPE_CACHE_PATH, 'w') as f:
        json.dump(cache_data, f, indent=2)

    return all_scraped

# ---------------------------------------------------------------------------
# Merge all layers (builtin -> CSV -> scraped)
# ---------------------------------------------------------------------------
_CSV_DATA = _load_csv_data()
_SCRAPED_DATA = _get_scraped_data()   # load from cache (or scrape fresh)

def _merge_all() -> dict:
    """Merge builtin (primary), CSV (secondary), scraped (tertiary)."""
    merged = {k: {"companions": list(v["companions"]), "avoid": list(v["avoid"])}
              for k, v in BUILTIN_DATA.items()}
    # Add CSV entries, but do not override builtin
    for plant, data in _CSV_DATA.items():
        if plant not in merged:
            merged[plant] = {"companions": [], "avoid": []}
        existing_companions = {c["plant"] for c in merged[plant]["companions"]}
        for c in data["companions"]:
            if c["plant"] not in existing_companions:
                merged[plant]["companions"].append(c)
        existing_avoids = {c["plant"] for c in merged[plant]["avoid"]}
        for a in data["avoid"]:
            if a["plant"] not in existing_avoids:
                merged[plant]["avoid"].append(a)
    # Add scraped entries (lowest priority)
    for plant, data in _SCRAPED_DATA.items():
        if plant not in merged:
            merged[plant] = {"companions": [], "avoid": []}
        existing_companions = {c["plant"] for c in merged[plant]["companions"]}
        for c in data["companions"]:
            if c["plant"] not in existing_companions:
                merged[plant]["companions"].append(c)
        existing_avoids = {c["plant"] for c in merged[plant]["avoid"]}
        for a in data["avoid"]:
            if a["plant"] not in existing_avoids:
                merged[plant]["avoid"].append(a)
    return merged

ALL_DATA = _merge_all()

# ---------------------------------------------------------------------------
# Public API (same as original)
# ---------------------------------------------------------------------------
def get_companions(plant: str) -> dict:
    plant = plant.lower().strip()
    return ALL_DATA.get(plant, {"companions": [], "avoid": []})

def get_all_plants() -> list[str]:
    return sorted(ALL_DATA.keys())

def get_pairing_info(plant_a: str, plant_b: str) -> dict:
    plant_a = plant_a.lower().strip()
    plant_b = plant_b.lower().strip()
    data_a = ALL_DATA.get(plant_a, {})
    data_b = ALL_DATA.get(plant_b, {})
    for c in data_a.get("companions", []):
        if c["plant"] == plant_b:
            return {"relationship": "companion", "reason": c.get("reason", "Good companions"), "benefit": c.get("benefit", "growth")}
    for c in data_a.get("avoid", []):
        if c["plant"] == plant_b:
            return {"relationship": "avoid", "reason": c.get("reason", "Poor companions")}
    for c in data_b.get("companions", []):
        if c["plant"] == plant_a:
            return {"relationship": "companion", "reason": c.get("reason", "Good companions"), "benefit": c.get("benefit", "growth")}
    for c in data_b.get("avoid", []):
        if c["plant"] == plant_a:
            return {"relationship": "avoid", "reason": c.get("reason", "Poor companions")}
    return {"relationship": "neutral", "reason": "No known interaction"}

# ---------------------------------------------------------------------------
# AI enrichment (unchanged - uses existing utils.ai_cache)
# ---------------------------------------------------------------------------
def _enrich_with_ai_impl(plant: str, postcode: str) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"companions": [], "avoid": []}
    prompt = f"""You are an RHS UK gardening expert.
For the plant "{plant}" grown in the UK, provide companion planting data.

Return STRICT JSON only:
{{
  "companions": [
    {{"plant": "plant name", "reason": "brief reason", "benefit": "pest_control|nitrogen|pollination|soil|moisture|space|structure|growth"}}
  ],
  "avoid": [
    {{"plant": "plant name", "reason": "brief reason"}}
  ]
}}

Include 4-6 companions and 2-3 avoids. Use common UK vegetable/herb names."""
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://seedsage.app",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            },
            timeout=20
        )
        data = resp.json()["choices"][0]["message"]["content"]
        result = json.loads(data)
        return result
    except Exception as e:
        print(f"AI enrichment error: {e}")
        return {"companions": [], "avoid": []}

def enrich_with_ai(plant: str, postcode: str) -> dict:
    from utils.ai_cache import get_ai_cached
    return get_ai_cached(plant, postcode, _enrich_with_ai_impl)