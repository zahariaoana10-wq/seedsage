import sqlite3
import datetime
import json
import os

DB_PATH = "data/users.db"

def init_user_db():
    """Create the users table if it doesn't exist, with journal column."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT,
            postcode TEXT,
            plants TEXT,
            plans TEXT,
            journal TEXT,
            PRIMARY KEY (username, postcode)
        )
    ''')
    # Add journal column if it doesn't exist (for existing databases)
    try:
        c.execute('ALTER TABLE users ADD COLUMN journal TEXT')
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()

def save_user(user):
    init_user_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    plants_json = json.dumps(user.get("plants", {}), default=str)
    plans_json = json.dumps(user.get("plans", {}), default=str)
    journal_json = json.dumps(user.get("journal", []), default=str)
    c.execute('''
        INSERT OR REPLACE INTO users (username, postcode, plants, plans, journal)
        VALUES (?, ?, ?, ?, ?)
    ''', (user["name"], user["postcode"], plants_json, plans_json, journal_json))
    conn.commit()
    conn.close()

def load_user(name, postcode):
    init_user_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT plants, plans, journal FROM users WHERE username=? AND postcode=?', (name, postcode))
    row = c.fetchone()
    conn.close()
    if row:
        plants = json.loads(row[0])
        plans = json.loads(row[1])
        journal = json.loads(row[2]) if row[2] else []
        # Convert date strings back to date objects for plants
        for p, data in plants.items():
            if "added_on" in data and isinstance(data["added_on"], str):
                data["added_on"] = datetime.date.fromisoformat(data["added_on"])
            if "actual_planted" in data and isinstance(data["actual_planted"], str):
                data["actual_planted"] = datetime.date.fromisoformat(data["actual_planted"])
        # For journal, convert date strings (need to handle)
        for entry in journal:
            if "date" in entry and isinstance(entry["date"], str):
                entry["date"] = datetime.date.fromisoformat(entry["date"])
            if "timestamp" in entry and isinstance(entry["timestamp"], str):
                # keep as string ISO, fine
                pass
        return {"plants": plants, "plans": plans, "journal": journal}
    return None