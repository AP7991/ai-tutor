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
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, content)
        )
        conn.commit()

def load_history(limit=20):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
    return list(reversed(rows))

def get_proficiency():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT topic, sub_topic, score FROM proficiency")
        return {(r[0], r[1]): r[2] for r in cur.fetchall()}

def upsert_proficiency(topic, sub_topic, score):
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

init_db()

def is_clarification(msg):
    msg_lower = msg.lower()
    return bool(re.search(r"explain step \d+", msg_lower) or msg_lower.startswith("why") or "clarify step" in msg_lower)

def build_prompt(user_message, history=None):
    if history:
        convo_prompt = "".join(f"{role.upper()}: {text.strip()}\n" for role, text in history)
    else:
        convo_prompt = ""

    if is_clarification(user_message):
        prompt = (
            "You are an AI math tutor. The user is asking for clarification on one of your previous math steps. "
            "Find the referenced step from the conversation above and explain it in clear, student-friendly language. "
            "Do NOT emit any PROFICIENCY_ASSESSMENT JSON.\n\n"
            f"{convo_prompt}"
            f"USER: {user_message}\n"
        )
    else:
        prompt = (
            "You are an AI math tutor.\n"
            "Return a response strictly formatted as follows:\n\n"
            "MATH:\n"
            "1. First math step\n"
            "2. Second math step\n"
            "...\n\n"
            "---\n\n"
            "EXPLANATION:\n"
            "1. Explanation of First step\n"
            "2. Explanation of Second step\n"
            "...\n\n"
            "Always end with a short question to check understanding. "
            "Always respond even if the student repeats themselves.\n\n"
            f"{convo_prompt}"
            f"USER: {user_message}\n"
        )
    return prompt

def call_gemini(prompt):
    body = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    }
    r = requests.post(URL, headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return "Error: message is required", 400

    save_message("user", user_message)
    history = load_history(limit=20)

    try:
        prompt = build_prompt(user_message, history)
        ai_text = call_gemini(prompt)

        if "I am unable to answer" in ai_text or "Let us return to the original question" in ai_text:
            raise ValueError("Unsatisfactory Gemini response")

    except Exception:
        # Retry without history if the first attempt failed
        try:
            prompt = build_prompt(user_message, history=None)
            ai_text = call_gemini(prompt)
        except Exception as e2:
            return f"Error: {str(e2)}", 500

    save_message("ai", ai_text)

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

    return ai_text

if __name__ == '__main__':
    app.run(port=5000, debug=True)
