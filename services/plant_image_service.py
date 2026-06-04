"""
plant_image_service.py – Emojis from emojidb.org + local fallback.
Supports automatic emoji lookup for any plant name.
"""

import os
import json
import requests
import streamlit as st

# Static local fallback (used when API fails or plant not found)
LOCAL_EMOJIS = {
    "tomato": "🍅", "pepper": "🌶️", "aubergine": "🍆", "courgette": "🥒",
    "cucumber": "🥒", "sweetcorn": "🌽", "lettuce": "🥬", "spinach": "🥬",
    "kale": "🥬", "broccoli": "🥦", "cauliflower": "🥦", "carrot": "🥕",
    "radish": "🫜", "beetroot": "❤️", "potato": "🥔", "onion": "🧅",
    "garlic": "🧄", "pea": "🫛", "bean": "🫘", "basil": "🌿", "mint": "🌿",
    "rosemary": "🌿", "thyme": "🌿", "parsley": "🌿", "coriander": "🌿",
    "dill": "🌿", "sage": "🌿", "oregano": "🌿", "marigold": "🌼",
    "sunflower": "🌻", "nasturtium": "🌸", "strawberry": "🍓",
    "raspberry": "🍓", "blueberry": "🫐", "hyacinth": "🌸", "tulip": "🌷",
    "daffodil": "🌼", "lavender": "💜", "borage": "💙"
}

PLANT_COLOURS = {
    "tomato": "#ef5350", "carrot": "#ffa726", "basil": "#66bb6a",
    "lettuce": "#9ccc65", "cucumber": "#26a69a", "pepper": "#ab47bc",
    "onion": "#ff8a65", "garlic": "#bcaaa4", "potato": "#a1887f",
    "strawberry": "#ef5350", "radish": "#f48fb1", "hyacinth": "#9c27b0",
    "default": "#4caf50"
}

# Cache file path (saved between sessions)
CACHE_FILE = "data/emoji_cache.json"

def _load_cache():
    """Load emoji cache from JSON file."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def _save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def _normalize(name: str) -> str:
    return name.lower().strip().replace(" ", "_")

def get_plant_emoji(plant_name: str) -> str:
    """
    Fetch emoji for plant using:
    1. Session state cache
    2. Persistent cache file
    3. emojidb.org API
    4. Local static fallback
    """
    norm = _normalize(plant_name)

    # 1. Session state cache
    if "emoji_cache" not in st.session_state:
        st.session_state.emoji_cache = {}
    if norm in st.session_state.emoji_cache:
        return st.session_state.emoji_cache[norm]

    # 2. Persistent file cache
    file_cache = _load_cache()
    if norm in file_cache:
        emoji = file_cache[norm]
        st.session_state.emoji_cache[norm] = emoji
        return emoji

    # 3. API call to emojidb.org
    try:
        url = f"https://emojidb.org/api/emoji?search={plant_name}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("results") and len(data["results"]) > 0:
            emoji = data["results"][0].strip()
            # Store in both caches
            st.session_state.emoji_cache[norm] = emoji
            file_cache[norm] = emoji
            _save_cache(file_cache)
            return emoji
    except Exception:
        pass  # fallback to local

    # 4. Local fallback
    emoji = LOCAL_EMOJIS.get(norm, "🌱")
    st.session_state.emoji_cache[norm] = emoji
    file_cache[norm] = emoji
    _save_cache(file_cache)
    return emoji

def get_plant_color(plant_name: str) -> str:
    norm = _normalize(plant_name)
    return PLANT_COLOURS.get(norm, PLANT_COLOURS["default"])