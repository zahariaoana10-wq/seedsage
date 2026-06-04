# 🌱 SeedSage

**AI-Powered Garden Planning for UK Growers**

SeedSage is a Streamlit web app that helps UK gardeners plan, track, and optimise their growing season. It combines AI-generated planting plans, companion planting guidance, a smart task calendar, and a conversational gardening assistant — all tailored to your UK postcode and local weather.

---

## Features

### 📊 Dashboard
- Add plants to your garden with a planting date
- Progress cards showing days to harvest, growth stage, and a visual progress bar
- Detailed care notes per plant (watering, sunlight, fertilising, pruning, UK tips)
- AI-generated planting plans with task schedules
- Ask SeedSage anything via a built-in chat interface
- Monthly gardening advice based on your plants and current season

### 🗓️ Calendar
- Month, week, agenda, timeline, and progress views
- Tasks grouped by category (watering, sowing, harvesting, etc.)
- "Due today" summary with grouped task view (e.g. _Watering: Tomato, Cucumber_)
- Mark tasks done individually or by group
- Past tasks from backdated plans auto-marked as done
- Export your calendar as an `.ics` file for Google Calendar / Apple Calendar

### 🌻 Companion Planting
- Look up good companions and plants to avoid for any vegetable or herb
- Compatibility matrix for your whole garden
- AI enrichment for plants not in the local database
- Interactive garden layout planner with AI-suggested arrangements
- Conflict detection between adjacent plants

### 🤖 AI Gardening Assistant
- Powered by Google ADK with OpenRouter (GPT-4o-mini by default)
- Personalised harvest timing based on your actual planting dates
- Understands natural language — "I planted tomatoes 3 weeks ago"
- Automatically adds plants and generates plans from conversation
- Tools: companion lookup, plant care data, UK weather, planting calendar

### 📓 Garden Journal
- Log notes, observations, and milestones per plant
- Timestamped entries stored per user

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | [Streamlit](https://streamlit.io) |
| AI Agent | [Google ADK](https://google.github.io/adk-docs/) + [LiteLLM](https://docs.litellm.ai/) |
| LLM | OpenRouter (GPT-4o-mini via OpenRouter API) |
| Plant Data | [Perenual API](https://perenual.com/docs/api) + local guide |
| Weather | [OpenWeatherMap API](https://openweathermap.org/api) |
| Plant Images | [Unsplash](https://unsplash.com/developers) / [Perenual](https://perenual.com) |
| Database | SQLite (via `utils/user_db.py`) |
| Deployment | Runs locally or on [Streamlit Community Cloud](https://streamlit.io/cloud) |

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/zahariaoana10-wq/seedsage.git
cd seedsage
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
PERENUAL_API_KEY=your_perenual_api_key
OPENWEATHER_API_KEY=your_openweathermap_api_key
```

| Key | Where to get it |
|---|---|
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `PERENUAL_API_KEY` | [perenual.com/docs/api](https://perenual.com/docs/api) |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) |

### 4. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser, enter your name and UK postcode to get started.

---

## Project Structure

```
seedsage/
├── app.py                    # Login page & entry point
├── pages/
│   ├── 1_Dashboard.py        # Garden dashboard & AI chat
│   ├── 2_Calendar.py         # Task calendar
│   ├── 3_Companions.py       # Companion planting & layout
│   └── 4_GardenJournal.py   # Garden journal
├── services/
│   ├── companion_service.py  # Companion planting data & AI enrichment
│   ├── gardening_agent.py    # Google ADK agent (OpenRouter)
│   ├── location_service.py   # UK postcode → coordinates, weather
│   ├── plant_image_service.py# Plant emoji & colour lookup
│   └── plant_services.py     # Plant care guide + Perenual API
├── utils/
│   ├── llm.py                # AI plan generation (OpenRouter)
│   ├── smart_tasks.py        # Task scheduling & calendar engine
│   ├── user_db.py            # SQLite user persistence
│   └── achievements.py       # Achievement tracking
├── data/
│   ├── companion_plants.json # Local companion planting database
│   └── uk_planting_guide.json# UK sowing/planting calendar
├── .env                      # API keys (not committed)
├── .gitignore
└── requirements.txt
```

---

## Deployment on Streamlit Community Cloud

1. Push your code to GitHub (already done)
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set the main file to `app.py`
4. Add your API keys under **Settings → Secrets** in the Streamlit dashboard (same format as `.env`)

---

## Notes

- The app is designed for **UK gardeners** — weather, frost dates, and growing advice follow RHS UK standards
- The Perenual free tier has rate limits; plant care data falls back to the built-in local guide when the API is unavailable
- The AI agent uses `openai/gpt-4o-mini` via OpenRouter by default — change `MODEL` in `services/gardening_agent.py` to use any other OpenRouter model
