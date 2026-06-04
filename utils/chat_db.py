import sqlite3
import datetime
import json

DB_PATH = "data/chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            session_id TEXT,
            user_id TEXT,
            message TEXT,
            response TEXT,
            timestamp TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_conversation(session_id, user_id, user_msg, agent_response):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chat_history (session_id, user_id, message, response, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, user_id, user_msg, agent_response, datetime.datetime.now()))
    conn.commit()
    conn.close()

def get_recent_history(session_id, limit=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT message, response FROM chat_history
        WHERE session_id = ?
        ORDER BY timestamp DESC LIMIT ?
    ''', (session_id, limit))
    rows = c.fetchall()
    conn.close()
    return [{"user": r[0], "assistant": r[1]} for r in reversed(rows)]