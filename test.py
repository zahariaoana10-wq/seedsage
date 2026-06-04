# import os
# from dotenv import load_dotenv
# from services.companion_service import get_companions
# from utils.llm import generate_plan

# # Load API keys from your .env file
# load_dotenv()

# def test_services():
#     print("--- 🧪 Starting Foundation Test ---")
    
#     # Test 1: Companion Service
#     test_plant = "tomato"
#     print(f"1. Testing Companion Service for: {test_plant}...")
#     data = get_companions(test_plant)
    
#     if data.get("companions") or data.get("avoid"):
#         print(f"✅ Success: Found {len(data['companions'])} companions for {test_plant}.")
#     else:
#         print("⚠️ Warning: No companions found. Check if your JSON is empty!")

#     # Test 2: LLM Integration
#     print(f"\n2. Testing LLM with GPT-4o-mini...")
#     try:
#         plan = generate_plan(test_plant, "SW1A 1AA")
        
#         # Define 'advice' here so it exists for the print statement below
#         advice = plan.get('companion_advice', 'No advice found')
        
#         if "timeline" in plan:
#             print("✅ Success: LLM generated a plan using your JSON data.")
#             print(f"🤖 AI Advice: {str(advice)[:100]}...")
#         else:
#             print("❌ Failure: LLM responded but format was wrong.")
#     except Exception as e:
#         print(f"❌ Error: {e}")

# if __name__ == "__main__":
#     test_services()

from services.location_service import get_uk_location, get_weather
from services.plant_services import get_botanical_data

# print("--- 🌦️ Testing Weather ---")
# loc = get_uk_location("SW1A 1AA")
# if loc:
#     weather = get_weather(loc['lat'], loc['lon'])
#     print(f"Weather in {loc['region']}: {weather['temp']}°C, {weather['description']}")

print("\n--- 🌿 Testing Perenual ---")
plant = get_botanical_data("Tomato")
if plant:
    print(f"Tomato Needs: {plant['sunlight']} sun and {plant['watering']} watering.")