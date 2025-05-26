from flask import Flask, request
from flask_cors import CORS
import sqlite3
import requests
import os
import json
import re
from datetime import datetime


app = Flask(__name__)
CORS(app)

API_KEY = "AIzaSyAsSdRNg-BgYCbSwR1TMiG7XvPPkCIdGi0"
URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent?key={API_KEY}"
HEADERS = {"Content-Type": "application/json"}

DB_PATH = "chat_history.db"

# --- Database setup -------------------------------------------------------

def init_db():
    """Create the messages and proficiency tables if they don't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proficiency (
                topic TEXT NOT NULL,
                sub_topic TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 5,
                last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (topic, sub_topic)
            )
        """)
        conn.commit()


def save_message(role, content):
    """Insert a new message into the DB."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, content)
        )
        conn.commit()


def load_history(limit=20):
    """Load the last `limit` messages from the DB, oldest first."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
    return list(reversed(rows))


def get_proficiency():
    """Fetch all stored proficiency scores."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT topic, sub_topic, score FROM proficiency")
        return {(r[0], r[1]): r[2] for r in cur.fetchall()}


def upsert_proficiency(topic, sub_topic, score):
    """Insert or update a proficiency score for a topic/sub-topic."""
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO proficiency (topic, sub_topic, score, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(topic, sub_topic) DO UPDATE
              SET score = excluded.score,
                  last_updated = excluded.last_updated
        """, (topic, sub_topic, score, now))
        conn.commit()

# Ensure DB and tables exist on startup
init_db()

# --- Clarification detection ---------------------------------------------

def is_clarification(msg):
    """Return True if the user is asking to clarify a previous step."""
    msg_lower = msg.lower()
    return bool(re.search(r"explain step \d+", msg_lower) or msg_lower.startswith("why") or "clarify step" in msg_lower)

# --- Chat endpoint --------------------------------------------------------

@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return "Error: message is required", 400

    # 1) save the user's message
    save_message("user", user_message)

    # 2) load recent history
    history = load_history(limit=20)
    convo_prompt = "".join(f"{role.upper()}: {text}\n" for role, text in history)

    # 3) optionally fetch current proficiency for use in prompts
    prof = get_proficiency()

    # 4) build the prompt based on whether it's a clarification
    if is_clarification(user_message):
        # Clarification prompt: explain a previous step
        full_prompt = (
            "You are an AI math tutor. The user is asking for clarification on one of your previous math steps. "
            "Find the referenced step from the conversation above and explain it in clear, student-friendly language. "
            "Do NOT emit any PROFICIENCY_ASSESSMENT JSON or repeat the MATH/EXPLANATION template.\n\n"
            f"{convo_prompt}"
            f"USER: {user_message}\n"
        )
    else:
        # Standard problem-solving prompt with proficiency assessment
        full_prompt = (
            "You are an AI math tutor. "
            "First, analyze the user's past messages to infer their competence (1–10) in each topic and sub-topic mentioned. "
            "Return a JSON object labelled \"PROFICIENCY_ASSESSMENT\" mapping topics to sub-topics with scores.\n\n"
            "Then, answer the user's question, tailoring the difficulty exactly to their level.\n\n"
            "Return a response strictly formatted as follows:\n\n"
            "MATH:\n"
            "1. First math step (maths only - in text)\n"
            "2. Second math step (maths only - in text)\n"
            "3. Third math step (maths only - in text) etc.\n\n"
            "---\n\n"
            "EXPLANATION:\n"
            "1. Explanation of First math step (in text)\n"
            "2. Explanation of second math step (in text)\n"
            "etc.\n\n"
            "Always wrap any {text:} items in braces if they appear in MATH. "
            "Always end with a question to check understanding. Make sure your response is short enough and understandable for a year 10 maths student. "
            "Always give an explanation even if the student is repeating themselves. \n\n"
            f"{convo_prompt}"
            f"USER: {user_message}\n\n"
        )

    body = {
        "contents": [
            {"role": "user", "parts": [{"text": full_prompt}]}  
        ]
    }

    # 5) call Gemini
    try:
        r = requests.post(URL, headers=HEADERS, json=body)
        r.raise_for_status()
        ai_text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"Error: {str(e)}", 500

    # 6) save AI reply
    save_message("ai", ai_text)

    # 7) if not clarification, extract & persist proficiency JSON
    if not is_clarification(user_message):
        match = re.search(r'PROFICIENCY_ASSESSMENT\s*:\s*(\{.*?\})', ai_text, re.DOTALL)
        if match:
            try:
                assessment = json.loads(match.group(1))
                for topic, submap in assessment.items():
                    for sub_topic, score in submap.items():
                        s = max(1, min(10, int(score)))
                        upsert_proficiency(topic, sub_topic, s)
            except json.JSONDecodeError:
                pass

    # 8) return raw for front-end parsing
    return ai_text

if __name__ == '__main__':
    app.run(port=5000, debug=True)
