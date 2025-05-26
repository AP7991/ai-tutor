from flask import Flask, request, session
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)
app.secret_key = "your_secret_key"  # Required for session storage

client = OpenAI(api_key="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")

@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message", "")

    # Initialize message history
    if "messages" not in session:
        session["messages"] = [
            {"role": "system", "content": (
                "You are an AI math tutor. Always format your response in this structure:\n\n"
                "MATH:\n"
                "1. Step one, no explanation.\n"
                "2. Step two, no explanation.\n"
                "---\n\n"
                "EXPLANATION:\n"
                "1. Explain step one\n"
                "2. Explain step two\n"
                "Always explain as if the user is a beginner. Keep answers focused on the same topic unless explicitly told to change."
            )}
        ]

    session["messages"].append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=session["messages"]
        )
        reply = response.choices[0].message.content

        # Store assistant response in memory
        session["messages"].append({"role": "assistant", "content": reply})
        session.modified = True  # Mark session as changed

        return reply
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/reset', methods=['POST'])
def reset():
    session.pop("messages", None)
    return "Conversation reset", 200

if __name__ == '__main__':
    app.run(port=5000, debug=True)
