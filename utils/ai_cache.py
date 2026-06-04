import json
import hashlib
import os

CACHE_FILE = "data/ai_cache.json"

def load_cache():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def get_ai_cached(plant: str, postcode: str, enrich_func):
    cache = load_cache()
    key = hashlib.md5(f"{plant}_{postcode}".encode()).hexdigest()
    if key in cache:
        return cache[key]
    result = enrich_func(plant, postcode)
    cache[key] = result
    save_cache(cache)
    return result