"""
services/plant_services.py
Plant data: rich local guide + Perenual API with disk cache.
"""

import os
import json
import requests

CACHE_FILE = "data/perenual_cache.json"

# ---------------------------------------------------------------------------
# Rich local plant guide
# ---------------------------------------------------------------------------
PLANT_GUIDE = {
    "tomato": {
        "botanical": "Solanum lycopersicum",
        "days_to_maturity": 60,
        "sunlight": "Full sun — at least 6-8 hours of direct sun daily.",
        "watering": "Water deeply 2-3 times a week. Keep soil consistently moist but never waterlogged. Use a drip line or water at the base to avoid wetting foliage, which encourages blight.",
        "fertilising": "Feed every 2 weeks with a high-potash (tomato) fertiliser once the first flowers appear. Avoid high-nitrogen feeds after flowering — they promote leaves over fruit.",
        "pruning": "Pinch out side shoots (suckers) that grow between the main stem and branches on cordon varieties. Stop the plant at 4-6 trusses by pinching the growing tip.",
        "pests": {
            "aphids": "Spray with diluted washing-up liquid or introduce ladybirds and lacewings.",
            "blight": "Remove and bin affected leaves immediately. Improve airflow. Apply copper fungicide as a preventative in wet summers.",
            "whitefly": "Use yellow sticky traps; introduce Encarsia formosa in a greenhouse."
        },
        "diseases": {
            "blossom end rot": "Caused by calcium deficiency from irregular watering. Water consistently and add garden lime to the soil.",
            "fusarium wilt": "Remove affected plants. Rotate crops and improve drainage."
        },
        "harvest_tips": "Pick when fully coloured and gives slightly under gentle pressure. Store at room temperature — never in the fridge, which kills flavour.",
        "companions": "Basil, marigold, carrot, parsley. Avoid fennel and brassicas.",
        "uk_notes": "In the UK, grow under glass or in a sheltered south-facing spot. Start indoors in March, transplant after last frost (late May)."
    },
    "cucumber": {
        "botanical": "Cucumis sativus",
        "days_to_maturity": 60,
        "sunlight": "Full sun — 6-8 hours minimum. Thrives in warm, sheltered spots.",
        "watering": "Water generously and consistently — cucumbers are 95% water. Aim for moist but not soggy soil. Irregular watering causes bitter fruit.",
        "fertilising": "Feed weekly with a balanced liquid fertiliser once plants are established. Switch to a high-potash feed when fruits begin to form.",
        "pruning": "Pinch out the growing tip after 6-7 leaves on bush types. For climbing varieties, train up a support and remove side shoots after 2 leaves.",
        "pests": {
            "red spider mite": "Mist foliage regularly to raise humidity. Use predatory mites (Phytoseiulus persimilis) in greenhouses.",
            "cucumber mosaic virus": "Spread by aphids — control aphids promptly. Remove and destroy infected plants."
        },
        "diseases": {
            "powdery mildew": "Improve airflow, avoid overhead watering. Apply a diluted milk spray (1:9 milk:water) as a preventative."
        },
        "harvest_tips": "Harvest when firm and dark green, before they turn yellow. Regular picking encourages more fruit. Cut with a knife rather than pulling.",
        "companions": "Nasturtium, dill, sunflower. Avoid sage and strong aromatic herbs.",
        "uk_notes": "Best grown in a greenhouse or polytunnel in the UK. Outdoor ridge varieties are more cold-tolerant. Sow indoors April-May."
    },
    "carrot": {
        "botanical": "Daucus carota",
        "days_to_maturity": 70,
        "sunlight": "Full sun to partial shade. Tolerates light shade better than most root veg.",
        "watering": "Keep soil consistently moist during germination (can take 2-3 weeks). Once established, water deeply once a week. Avoid overwatering which causes forking.",
        "fertilising": "Avoid high-nitrogen feeds — they cause forked, hairy roots. A low-nitrogen, high-potassium feed applied once mid-season is sufficient.",
        "pruning": "Thin seedlings to 5-8cm apart once they reach 2-3cm tall. Crowded carrots produce small, misshapen roots.",
        "pests": {
            "carrot fly": "Erect a 60cm fine mesh barrier around the bed. Companion plant with leeks, onions, or rosemary to mask the scent.",
            "slugs": "Use copper tape around raised beds or apply nematodes in spring."
        },
        "diseases": {
            "cavity spot": "Caused by calcium deficiency and waterlogging. Improve drainage and lime acidic soils."
        },
        "harvest_tips": "Harvest when the shoulder (top of root) is visible above the soil, usually 1-2cm diameter. Twist off the foliage to store. Leave in the ground over winter in mild areas.",
        "companions": "Leeks, onions, rosemary, lettuce, chives. Avoid dill (attracts carrot fly).",
        "uk_notes": "Sow direct outdoors March-July. Avoid freshly manured soil — causes forking. Raised beds with sandy, stone-free compost give the best results."
    },
    "basil": {
        "botanical": "Ocimum basilicum",
        "days_to_maturity": 30,
        "sunlight": "Full sun — needs 6+ hours. Struggles in cool, cloudy UK summers; a south-facing windowsill or greenhouse is ideal.",
        "watering": "Keep moist but not wet. Water at the base — wet leaves encourage downy mildew. Allow the top centimetre of soil to dry between waterings.",
        "fertilising": "Apply a diluted liquid feed every 3-4 weeks. Avoid overfeeding — it reduces the intensity of the flavour.",
        "pruning": "Pinch out the growing tips regularly to prevent flowering and encourage bushy growth. Once it flowers, leaves become bitter.",
        "pests": {
            "slugs": "Use beer traps or copper tape around pots.",
            "aphids": "Spray with neem oil or soapy water."
        },
        "diseases": {
            "downy mildew": "Improve air circulation, avoid overhead watering, and remove affected leaves promptly."
        },
        "harvest_tips": "Pick leaves from the top down, always leaving at least 2 sets of leaves on each stem. Use fresh — flavour diminishes when cooked. Freeze in olive oil for longer storage.",
        "companions": "Tomato, pepper, oregano. Repels aphids and whitefly near tomatoes.",
        "uk_notes": "Treat as a tender annual in the UK. Sow indoors from April. Bring pots inside when temperatures drop below 10°C."
    },
    "courgette": {
        "botanical": "Cucurbita pepo",
        "days_to_maturity": 55,
        "sunlight": "Full sun — needs warmth and at least 6 hours of sun.",
        "watering": "Water generously at the base, 2-3 times a week. Avoid wetting the crown which causes rot. Mulch around the plant to retain moisture.",
        "fertilising": "Feed weekly with a high-potash liquid fertiliser once the first flowers appear.",
        "pruning": "Remove any yellowing or damaged leaves to improve airflow. No major pruning needed.",
        "pests": {
            "slugs": "Protect young plants with copper tape or nematodes.",
            "vine weevil": "Check roots of pot-grown plants; use nematodes in late summer."
        },
        "diseases": {
            "powdery mildew": "Common in late summer. Improve airflow and apply a milk spray preventatively.",
            "blossom drop": "Usually caused by poor pollination. Hand-pollinate by transferring pollen between male and female flowers with a brush."
        },
        "harvest_tips": "Harvest when 10-15cm long for best flavour and texture. Check plants daily in peak season — they grow fast. Leaving them to grow into marrows reduces further production.",
        "companions": "Nasturtium, marigold, borage. Avoid potatoes.",
        "uk_notes": "Sow indoors in April, transplant after last frost. One or two plants produce abundantly — most families only need 2-3 plants."
    },
    "lettuce": {
        "botanical": "Lactuca sativa",
        "days_to_maturity": 45,
        "sunlight": "Partial shade to full sun. In summer, afternoon shade prevents bolting.",
        "watering": "Keep soil consistently moist. Water little and often. Dry spells cause bolting and bitter leaves.",
        "fertilising": "A nitrogen-rich liquid feed every 2-3 weeks encourages leafy growth.",
        "pruning": "For cut-and-come-again varieties, harvest outer leaves regularly. For hearting types, harvest the whole head.",
        "pests": {
            "slugs": "The main pest. Use nematodes, beer traps, or copper tape.",
            "aphids": "Check under leaves. Spray with soapy water."
        },
        "diseases": {
            "downy mildew": "Improve airflow and avoid overhead watering."
        },
        "harvest_tips": "Harvest in the morning when leaves are crisp. Cut-and-come-again varieties can be harvested multiple times. Harvest hearting types before they bolt.",
        "companions": "Carrot, radish, strawberry, chives. Avoid fennel.",
        "uk_notes": "Sow successionally every 2-3 weeks from March to August for a continuous harvest. Grow under fleece for winter crops."
    },
    "pepper": {
        "botanical": "Capsicum annuum",
        "days_to_maturity": 80,
        "sunlight": "Full sun — 8+ hours. Best grown under glass in the UK.",
        "watering": "Water consistently, keeping soil moist. Reduce watering slightly once fruits begin to colour to concentrate flavour.",
        "fertilising": "Feed weekly with a high-potash tomato fertiliser once flowers appear.",
        "pruning": "Pinch out the growing tip when the plant reaches 20-30cm to encourage branching. Remove the first flower (the 'crown set') to direct energy into the plant structure.",
        "pests": {
            "aphids": "Spray with soapy water or introduce ladybirds.",
            "red spider mite": "Mist foliage to raise humidity. Use predatory mites in greenhouses."
        },
        "diseases": {
            "blossom drop": "Caused by temperature fluctuations or low humidity. Keep temperatures above 15°C and mist flowers."
        },
        "harvest_tips": "Harvest green peppers when firm and full-sized. Leave on the plant to ripen to red, yellow, or orange for sweeter flavour — but this slows further production.",
        "companions": "Basil, carrot, tomato. Avoid fennel.",
        "uk_notes": "Start indoors in February-March. Requires a long warm season — greenhouse or polytunnel strongly recommended in the UK."
    },
    "chilli": {
        "botanical": "Capsicum frutescens",
        "days_to_maturity": 90,
        "sunlight": "Full sun — 8+ hours. Needs warmth; grow under glass in the UK.",
        "watering": "Water moderately. Allow the top of the soil to dry slightly between waterings — slight drought stress increases capsaicin (heat) levels.",
        "fertilising": "Feed weekly with high-potash fertiliser once flowering begins. Avoid high nitrogen which promotes leaves over fruit.",
        "pruning": "Pinch out the growing tip at 20-30cm to encourage bushy growth and more fruit.",
        "pests": {
            "aphids": "Spray with soapy water.",
            "red spider mite": "Raise humidity by misting. Use predatory mites."
        },
        "diseases": {
            "blossom drop": "Caused by cold temperatures or low humidity. Keep above 15°C."
        },
        "harvest_tips": "Harvest green for milder heat, or leave to ripen to red/orange/yellow for more intense flavour and heat. Wear gloves when handling hot varieties.",
        "companions": "Basil, tomato, carrot.",
        "uk_notes": "Start indoors in February. Needs a long season — greenhouse growing is strongly recommended. Overwintered plants produce earlier the following year."
    },
    "pea": {
        "botanical": "Pisum sativum",
        "days_to_maturity": 65,
        "sunlight": "Full sun to partial shade.",
        "watering": "Water well at sowing and when flowers appear. Avoid overwatering between these stages.",
        "fertilising": "Peas fix their own nitrogen — no nitrogen feed needed. A balanced feed at flowering can help pod set.",
        "pruning": "Pinch out growing tips to encourage bushier growth and more pods. Provide support with canes and netting.",
        "pests": {
            "pea moth": "Cover with fine mesh during flowering to prevent egg-laying.",
            "mice": "Protect seeds with wire mesh at sowing."
        },
        "diseases": {
            "powdery mildew": "Common in dry conditions. Water consistently and improve airflow."
        },
        "harvest_tips": "Pick when pods are plump but before they become tough and starchy. Regular picking encourages more pods. Eat or freeze immediately for best sweetness.",
        "companions": "Carrot, radish, mint, turnip. Avoid onions and garlic.",
        "uk_notes": "Sow direct outdoors March-June. Autumn sowings of hardy varieties can overwinter. Provide support — even dwarf varieties benefit from twiggy sticks."
    },
    "bean": {
        "botanical": "Phaseolus vulgaris",
        "days_to_maturity": 60,
        "sunlight": "Full sun — sheltered from strong winds.",
        "watering": "Water well at the base once flowers appear. Irregular watering causes pods to drop.",
        "fertilising": "Beans fix nitrogen — avoid high-nitrogen feeds. A potassium-rich feed at flowering improves pod set.",
        "pruning": "Pinch out growing tips of climbing beans when they reach the top of their support.",
        "pests": {
            "blackfly": "Pinch out growing tips in early summer to remove colonies. Spray with soapy water.",
            "slugs": "Protect young plants with copper tape or nematodes."
        },
        "diseases": {
            "halo blight": "Bacterial disease causing water-soaked spots. Remove affected plants and avoid overhead watering."
        },
        "harvest_tips": "Pick French beans when pods snap cleanly, before seeds swell. Runner beans at 15-20cm. Regular picking is essential — leaving pods to mature stops production.",
        "companions": "Carrot, cucumber, squash, marigold. Avoid onions and fennel.",
        "uk_notes": "Sow indoors April or direct outdoors after last frost (late May). Runner beans need a sturdy support structure — wigwams or a double row of canes."
    },
    "potato": {
        "botanical": "Solanum tuberosum",
        "days_to_maturity": 100,
        "sunlight": "Full sun.",
        "watering": "Water regularly once foliage appears. Increase watering when plants flower — this is when tubers are forming. Inconsistent watering causes hollow or cracked tubers.",
        "fertilising": "Apply a balanced fertiliser at planting. Earth up stems as they grow to increase yield and prevent greening.",
        "pruning": "Earth up (mound soil around stems) every 2-3 weeks as plants grow. This encourages more tubers and protects against frost.",
        "pests": {
            "potato blight": "Spray with copper fungicide preventatively in warm, wet weather. Remove and bin (not compost) affected foliage.",
            "slugs": "Use nematodes in late summer before harvest."
        },
        "diseases": {
            "common scab": "Caused by alkaline soil. Keep soil slightly acidic and water consistently."
        },
        "harvest_tips": "Harvest first earlies when flowers open (June-July). Maincrop potatoes when foliage dies back (August-October). Leave in the ground for 2 weeks after cutting foliage to harden skins.",
        "companions": "Horseradish, beans, marigold. Avoid tomatoes, peppers, and cucumbers (same blight risk).",
        "uk_notes": "Chit seed potatoes in a cool, light place from January. Plant first earlies March-April, maincrops April-May."
    },
    "onion": {
        "botanical": "Allium cepa",
        "days_to_maturity": 100,
        "sunlight": "Full sun.",
        "watering": "Water regularly in dry spells during the growing season. Stop watering once the foliage begins to flop — this helps bulbs ripen.",
        "fertilising": "Apply a balanced fertiliser at planting. Avoid high-nitrogen feeds after midsummer which delay ripening.",
        "pruning": "No pruning needed. Bend over the tops in late summer to speed up ripening if they haven't flopped naturally.",
        "pests": {
            "onion fly": "Cover with fine mesh. Companion plant with carrots.",
            "thrips": "Spray with insecticidal soap in dry weather."
        },
        "diseases": {
            "onion white rot": "Soil-borne fungus — rotate crops and avoid infected soil for 8+ years.",
            "downy mildew": "Improve airflow and avoid overhead watering."
        },
        "harvest_tips": "Harvest when foliage has flopped and turned yellow. Lift carefully and dry in the sun for 2-3 weeks before storing in a cool, dry, airy place.",
        "companions": "Carrot, lettuce, chamomile. Avoid peas and beans.",
        "uk_notes": "Plant sets (small bulbs) March-April for summer harvest. Autumn sets planted September-October for an earlier crop the following year."
    },
    "garlic": {
        "botanical": "Allium sativum",
        "days_to_maturity": 240,
        "sunlight": "Full sun.",
        "watering": "Water sparingly — garlic dislikes waterlogged soil. Water only in prolonged dry spells during spring growth.",
        "fertilising": "Apply a balanced fertiliser in early spring as growth resumes. Avoid feeding after May.",
        "pruning": "Remove flower scapes (curling stems) on hardneck varieties in June — this directs energy into the bulb.",
        "pests": {
            "leek rust": "Orange pustules on leaves. Remove affected leaves. Improve airflow.",
            "onion fly": "Cover with fine mesh."
        },
        "diseases": {
            "white rot": "Avoid planting in infected soil. Rotate crops on a long cycle."
        },
        "harvest_tips": "Harvest when the lower leaves have turned yellow but 3-4 green leaves remain (usually June-July). Dry in a warm, airy place for 3-4 weeks before storing.",
        "companions": "Roses, fruit trees, carrot. Avoid peas and beans.",
        "uk_notes": "Plant individual cloves October-November for the best yields. Softneck varieties store longer; hardneck varieties have more complex flavour."
    },
    "strawberry": {
        "botanical": "Fragaria x ananassa",
        "days_to_maturity": 60,
        "sunlight": "Full sun — at least 6 hours for the best fruit.",
        "watering": "Water regularly, especially during fruiting. Avoid wetting the fruit and crowns — use a drip line or water at the base.",
        "fertilising": "Feed with a high-potash fertiliser every 2 weeks from when flowers appear until fruiting ends. Apply a balanced feed in autumn to build up the plant for next year.",
        "pruning": "After fruiting, cut back old foliage to 10cm. Remove runners unless you want new plants. Replace plants every 3-4 years as yields decline.",
        "pests": {
            "slugs": "Use nematodes or copper tape. Raise pots off the ground.",
            "birds": "Cover with netting as fruits ripen.",
            "vine weevil": "Check roots for white grubs. Apply nematodes in late summer."
        },
        "diseases": {
            "grey mould (botrytis)": "Remove affected fruit immediately. Improve airflow and avoid overhead watering.",
            "powdery mildew": "Apply a milk spray preventatively in dry weather."
        },
        "harvest_tips": "Pick when fully red all over, including the shoulders. Harvest in the morning when cool. Eat within 1-2 days or freeze.",
        "companions": "Borage, lettuce, spinach, thyme. Avoid brassicas and fennel.",
        "uk_notes": "Plant bare-root runners September-October or pot-grown plants in spring. Protect with fleece during late frosts. Grow in raised beds or hanging baskets to improve drainage and deter slugs."
    },
    "hyacinth": {
        "botanical": "Hyacinthus orientalis",
        "days_to_maturity": 90,
        "sunlight": "Full sun to partial shade.",
        "watering": "Water moderately during active growth. Allow to dry out after flowering. Do not overwater — bulbs rot in waterlogged soil.",
        "fertilising": "Apply a balanced bulb fertiliser after flowering to feed the bulb for next year.",
        "pruning": "Deadhead spent flowers but leave the foliage to die back naturally — this feeds the bulb.",
        "pests": {
            "slugs": "Protect emerging shoots with copper tape or grit."
        },
        "diseases": {
            "bulb rot": "Ensure well-drained soil. Plant on a layer of grit."
        },
        "harvest_tips": "Not harvested — grown for flowers. Lift and dry bulbs after foliage dies back if storing.",
        "companions": "Tulips, daffodils, muscari.",
        "uk_notes": "Plant bulbs September-November, 10cm deep. Excellent for forcing indoors — pre-chilled bulbs can be planted in bowls for Christmas flowering."
    },
}

# ---------------------------------------------------------------------------
# Default fallback
# ---------------------------------------------------------------------------
DEFAULT_PLANT_DATA = {
    "sunlight": "Full sun to partial shade",
    "watering": "Water when the top centimetre of soil feels dry.",
    "cycle": "Annual",
    "days_to_maturity": 75,
    "companions": "Marigold, nasturtium (general pest deterrents)",
    "fertilising": "Apply a balanced fertiliser monthly during the growing season.",
    "harvest_tips": "Harvest when produce looks ripe and ready.",
    "pests": {"general": "Check regularly; remove pests by hand or use an organic spray."},
    "diseases": {},
    "uk_notes": "Follow RHS guidelines for UK growing conditions.",
}

# ---------------------------------------------------------------------------
# Disk cache for Perenual API responses
# ---------------------------------------------------------------------------
def _load_perenual_cache() -> dict:
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_perenual_cache(cache: dict):
    os.makedirs("data", exist_ok=True)
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

def _fetch_perenual(plant: str, api_key: str) -> dict:
    """
    Fetch species details from Perenual and return a partial care dict.
    Results are disk-cached so we don't burn through the free quota.
    Returns {} on any error or rate-limit.
    """
    cache = _load_perenual_cache()
    if plant in cache:
        return cache[plant]

    try:
        search = requests.get(
            f"https://perenual.com/api/species-list?key={api_key}&q={plant}",
            timeout=8,
        )
        if search.status_code != 200:
            return {}
        results = search.json().get("data", [])
        if not results:
            return {}

        pid = results[0]["id"]
        det = requests.get(
            f"https://perenual.com/api/species/details/{pid}?key={api_key}",
            timeout=8,
        )
        if det.status_code != 200:
            return {}
        d = det.json()

        partial = {}
        if d.get("sunlight"):
            sl = d["sunlight"]
            partial["sunlight_api"] = ", ".join(sl) if isinstance(sl, list) else str(sl)
        if d.get("watering"):
            partial["watering_api"] = str(d["watering"])
        if d.get("cycle"):
            partial["cycle"] = str(d["cycle"])
        if d.get("maintenance"):
            partial["maintenance"] = str(d["maintenance"])
        if d.get("care_level"):
            partial["care_level"] = str(d["care_level"])
        if d.get("growth_rate"):
            partial["growth_rate"] = str(d["growth_rate"])
        if d.get("harvest_season"):
            partial["harvest_season"] = str(d["harvest_season"])
        if d.get("description"):
            partial["description"] = str(d["description"])[:400]

        cache[plant] = partial
        _save_perenual_cache(cache)
        return partial

    except Exception as e:
        print(f"[Perenual] {plant}: {e}")
        return {}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_botanical_data(plant_name: str) -> dict:
    """
    Returns care data for use in AI plan generation.
    Merges local guide with any available Perenual fields.
    """
    plant = plant_name.lower().strip()
    api_key = os.getenv("PERENUAL_API_KEY")

    base = DEFAULT_PLANT_DATA.copy()
    if plant in PLANT_GUIDE:
        g = PLANT_GUIDE[plant]
        base.update({
            "sunlight": g.get("sunlight", base["sunlight"]),
            "watering": g.get("watering", base["watering"]),
            "cycle": g.get("cycle", base["cycle"]),
            "days_to_maturity": g.get("days_to_maturity", base["days_to_maturity"]),
            "companions": g.get("companions", base["companions"]),
        })

    if api_key:
        api_data = _fetch_perenual(plant, api_key)
        if api_data.get("cycle"):
            base["cycle"] = api_data["cycle"]
        if api_data.get("harvest_season"):
            base["harvest_season"] = api_data["harvest_season"]

    return base


def get_plant_guide(plant_name: str) -> dict:
    """
    Returns the full care guide for dashboard cards.
    Merges the rich local guide with any supplementary Perenual fields.
    """
    plant = plant_name.lower().strip()
    api_key = os.getenv("PERENUAL_API_KEY")

    if plant in PLANT_GUIDE:
        guide = dict(PLANT_GUIDE[plant])
    else:
        guide = {
            "botanical": f"{plant_name.capitalize()} species",
            "days_to_maturity": 75,
            "sunlight": DEFAULT_PLANT_DATA["sunlight"],
            "watering": DEFAULT_PLANT_DATA["watering"],
            "fertilising": DEFAULT_PLANT_DATA["fertilising"],
            "pruning": "Prune as needed to maintain shape and remove dead growth.",
            "pests": DEFAULT_PLANT_DATA["pests"],
            "diseases": DEFAULT_PLANT_DATA["diseases"],
            "harvest_tips": DEFAULT_PLANT_DATA["harvest_tips"],
            "companions": DEFAULT_PLANT_DATA["companions"],
            "uk_notes": DEFAULT_PLANT_DATA["uk_notes"],
        }

    # Supplement with Perenual data where available
    if api_key:
        api_data = _fetch_perenual(plant, api_key)
        if api_data.get("description") and not guide.get("description"):
            guide["description"] = api_data["description"]
        if api_data.get("care_level"):
            guide["care_level"] = api_data["care_level"]
        if api_data.get("maintenance"):
            guide["maintenance"] = api_data["maintenance"]
        if api_data.get("growth_rate"):
            guide["growth_rate"] = api_data["growth_rate"]
        if api_data.get("harvest_season"):
            guide["harvest_season"] = api_data["harvest_season"]

    return guide
