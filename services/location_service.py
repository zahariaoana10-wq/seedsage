import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_uk_location(postcode):
    url = f"https://api.postcodes.io/postcodes/{postcode}"
    res = requests.get(url)

    if res.status_code == 200:
        data = res.json()["result"]
        return {
            "lat": data["latitude"],
            "lon": data["longitude"],
            "region": data["admin_district"]
        }
    return None


def get_weather(lat, lon):
    api_key = os.getenv("OPENWEATHER_API_KEY")

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"

    res = requests.get(url)

    if res.status_code == 200:
        data = res.json()
        return {
            "temp": data["main"]["temp"],
            "description": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"]
        }
    return None


def get_weather_forecast(lat, lon):
    api_key = os.getenv("OPENWEATHER_API_KEY")

    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"

    res = requests.get(url)

    if res.status_code == 200:
        data = res.json()

        forecast = []
        for item in data["list"][:8]:
            forecast.append({
                "temp": item["main"]["temp"],
                "description": item["weather"][0]["description"]
            })

        return forecast

    return []

# services/location_service.py (add this function at the end)

import datetime

# UK postcode regions – estimate last frost date
# Based on Met Office average last frost dates
REGION_LAST_FROST = {
    # South West / South East (mildest)
    "SW": datetime.date(2025, 3, 15),
    "SE": datetime.date(2025, 3, 20),
    "W":  datetime.date(2025, 3, 25),
    "EC": datetime.date(2025, 3, 28),
    "N":  datetime.date(2025, 4, 5),
    "NW": datetime.date(2025, 4, 10),
    "NE": datetime.date(2025, 4, 15),
    "S":  datetime.date(2025, 3, 22),
    "B":  datetime.date(2025, 4, 5),
    "BB": datetime.date(2025, 4, 10),
    "BD": datetime.date(2025, 4, 10),
    "BH": datetime.date(2025, 3, 25),
    "BL": datetime.date(2025, 4, 10),
    "BN": datetime.date(2025, 3, 25),
    "BR": datetime.date(2025, 3, 28),
    "BS": datetime.date(2025, 3, 25),
    "CA": datetime.date(2025, 4, 15),
    "CB": datetime.date(2025, 4, 5),
    "CF": datetime.date(2025, 4, 10),
    "CH": datetime.date(2025, 4, 10),
    "CM": datetime.date(2025, 4, 5),
    "CO": datetime.date(2025, 4, 5),
    "CR": datetime.date(2025, 3, 28),
    "CT": datetime.date(2025, 3, 28),
    "CV": datetime.date(2025, 4, 5),
    "CW": datetime.date(2025, 4, 10),
    "DA": datetime.date(2025, 3, 28),
    "DD": datetime.date(2025, 4, 15),
    "DE": datetime.date(2025, 4, 10),
    "DG": datetime.date(2025, 4, 15),
    "DH": datetime.date(2025, 4, 15),
    "DL": datetime.date(2025, 4, 15),
    "DN": datetime.date(2025, 4, 10),
    "DT": datetime.date(2025, 3, 25),
    "DY": datetime.date(2025, 4, 5),
    "E":  datetime.date(2025, 3, 28),
    "EC": datetime.date(2025, 3, 28),
    "EH": datetime.date(2025, 4, 15),
    "EN": datetime.date(2025, 3, 28),
    "EX": datetime.date(2025, 3, 25),
    "FK": datetime.date(2025, 4, 15),
    "FY": datetime.date(2025, 4, 10),
    "G":  datetime.date(2025, 4, 15),
    "GL": datetime.date(2025, 4, 5),
    "GU": datetime.date(2025, 3, 28),
    "HA": datetime.date(2025, 3, 28),
    "HD": datetime.date(2025, 4, 10),
    "HG": datetime.date(2025, 4, 10),
    "HP": datetime.date(2025, 4, 5),
    "HR": datetime.date(2025, 4, 10),
    "HS": datetime.date(2025, 5, 5),
    "HU": datetime.date(2025, 4, 15),
    "HX": datetime.date(2025, 4, 10),
    "IG": datetime.date(2025, 3, 28),
    "IP": datetime.date(2025, 4, 5),
    "IV": datetime.date(2025, 4, 20),
    "KA": datetime.date(2025, 4, 15),
    "KT": datetime.date(2025, 3, 28),
    "KW": datetime.date(2025, 4, 20),
    "KY": datetime.date(2025, 4, 15),
    "L":  datetime.date(2025, 4, 10),
    "LA": datetime.date(2025, 4, 10),
    "LD": datetime.date(2025, 4, 10),
    "LE": datetime.date(2025, 4, 10),
    "LL": datetime.date(2025, 4, 15),
    "LN": datetime.date(2025, 4, 10),
    "LS": datetime.date(2025, 4, 10),
    "LU": datetime.date(2025, 4, 5),
    "M":  datetime.date(2025, 4, 10),
    "ME": datetime.date(2025, 3, 28),
    "MK": datetime.date(2025, 4, 5),
    "ML": datetime.date(2025, 4, 15),
    "N":  datetime.date(2025, 3, 28),
    "NE": datetime.date(2025, 4, 15),
    "NG": datetime.date(2025, 4, 10),
    "NN": datetime.date(2025, 4, 5),
    "NP": datetime.date(2025, 4, 10),
    "NR": datetime.date(2025, 4, 5),
    "NW": datetime.date(2025, 3, 28),
    "OL": datetime.date(2025, 4, 10),
    "OX": datetime.date(2025, 4, 5),
    "PA": datetime.date(2025, 4, 15),
    "PE": datetime.date(2025, 4, 5),
    "PH": datetime.date(2025, 4, 20),
    "PL": datetime.date(2025, 3, 25),
    "PO": datetime.date(2025, 3, 25),
    "PR": datetime.date(2025, 4, 10),
    "RG": datetime.date(2025, 3, 28),
    "RH": datetime.date(2025, 3, 28),
    "RM": datetime.date(2025, 3, 28),
    "S":  datetime.date(2025, 4, 10),
    "SA": datetime.date(2025, 4, 10),
    "SE": datetime.date(2025, 3, 28),
    "SG": datetime.date(2025, 3, 28),
    "SK": datetime.date(2025, 4, 10),
    "SL": datetime.date(2025, 3, 28),
    "SM": datetime.date(2025, 3, 28),
    "SN": datetime.date(2025, 3, 28),
    "SO": datetime.date(2025, 3, 25),
    "SP": datetime.date(2025, 3, 25),
    "SR": datetime.date(2025, 4, 15),
    "SS": datetime.date(2025, 3, 28),
    "ST": datetime.date(2025, 4, 10),
    "SW": datetime.date(2025, 3, 28),
    "SY": datetime.date(2025, 4, 10),
    "TA": datetime.date(2025, 3, 25),
    "TD": datetime.date(2025, 4, 15),
    "TF": datetime.date(2025, 4, 5),
    "TN": datetime.date(2025, 3, 28),
    "TQ": datetime.date(2025, 3, 25),
    "TR": datetime.date(2025, 3, 20),
    "TS": datetime.date(2025, 4, 15),
    "TW": datetime.date(2025, 3, 28),
    "UB": datetime.date(2025, 3, 28),
    "W":  datetime.date(2025, 3, 28),
    "WA": datetime.date(2025, 4, 10),
    "WC": datetime.date(2025, 3, 28),
    "WD": datetime.date(2025, 3, 28),
    "WF": datetime.date(2025, 4, 10),
    "WN": datetime.date(2025, 4, 10),
    "WR": datetime.date(2025, 4, 5),
    "WS": datetime.date(2025, 4, 5),
    "WV": datetime.date(2025, 4, 5),
    "YO": datetime.date(2025, 4, 15),
    "ZE": datetime.date(2025, 5, 10),
}
DEFAULT_LAST_FROST = datetime.date(2025, 4, 15)

def get_last_frost_date(postcode: str) -> datetime.date:
    """Return estimated last frost date for the given UK postcode."""
    # Extract first part (letters) e.g. "SW1A" -> "SW"
    try:
        prefix = ''.join(filter(str.isalpha, postcode.split()[0].upper()))[:2]
        return REGION_LAST_FROST.get(prefix, DEFAULT_LAST_FROST)
    except:
        return DEFAULT_LAST_FROST