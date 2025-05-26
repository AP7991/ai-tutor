from flask import Flask, Blueprint, request
from flask_cors import CORS
import sqlite3
import requests
import json

app = Flask(__name__)
CORS(app)

API_KEY = "AIzaSyAsSdRNg-BgYCbSwR1TMiG7XvPPkCIdGi0"  # Replace with your actual API key
URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent?key={API_KEY}"
HEADERS = {"Content-Type": "application/json"}

DB_PATH = "chat_history.db"

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
        conn.commit()

def save_message(role, content):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        conn.commit()

def load_history(limit=20):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
    return list(reversed(rows))

init_db()

basic_chat_bp = Blueprint('basic_chat', __name__)

@basic_chat_bp.route('/api/chat-basic', methods=['POST'])
def chat_basic():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return "Error: message is required", 400

    save_message("user", user_message)
    history = load_history(limit=20)
    convo_prompt = "".join(f"{role.upper()}: {text}\n" for role, text in history)

    full_prompt = (
        "You are a helpful conversational assistant. Answer user questions clearly.\n\n"
        f"{convo_prompt}"
        f"USER: {user_message}\n"
    )

    body = {
        "prompt": {
            "messages": [
                {
                    "author": "user",
                    "content": {
                        "text": full_prompt
                    }
                }
            ]
        },
        "temperature": 0.7,
        "maxOutputTokens": 1024
    }

    try:
        r = requests.post(URL, headers=HEADERS, json=body)
        r.raise_for_status()
        ai_text = r.json()["candidates"][0]["content"]["text"].strip()
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response else 'No response content'
        error_msg = f"Request error: {e}\nResponse content: {response_text}"
        print(error_msg)
        return error_msg, 500
    except Exception as e:
        error_msg = f"General error: {e}"
        print(error_msg)
        return error_msg, 500

    save_message("ai", ai_text)
    return ai_text

app.register_blueprint(basic_chat_bp)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
