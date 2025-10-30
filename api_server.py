# api_server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, requests

app = Flask(__name__)
CORS(app)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OWNER = os.getenv("GITHUB_OWNER")
REPO = os.getenv("GITHUB_REPO")
BRANCH = os.getenv("GITHUB_BRANCH", "main")
BOT_FILE = os.getenv("BOT_FILE_PATH", "main.py")
API_KEY = os.getenv("DASHBOARD_KEY")  # optional for security

def github_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

@app.before_request
def check_key():
    if API_KEY and request.headers.get("x-api-key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 403

@app.route("/api/add_command", methods=["POST"])
def add_command():
    data = request.json
    cmd, gif = data.get("command"), data.get("gif")
    if not cmd or not gif:
        return jsonify({"error": "Missing fields"}), 400

    file_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{BOT_FILE}"
    file_resp = requests.get(file_url, headers=github_headers())
    content = file_resp.json()
    import base64
    file_text = base64.b64decode(content["content"]).decode()
    sha = content["sha"]

    new_block = f"""

@bot.command(name="{cmd}")
async def {cmd}(ctx):
    await ctx.send("🎬 {cmd} command triggered!")
    await ctx.send("{gif}")
"""
    updated_text = file_text + new_block
    payload = {
        "message": f"Add GIF command: {cmd}",
        "content": base64.b64encode(updated_text.encode()).decode(),
        "sha": sha,
        "branch": BRANCH
    }
    requests.put(file_url, headers=github_headers(), json=payload)
    return jsonify({"success": True, "command": cmd})

@app.route("/api/automod", methods=["POST"])
def update_automod():
    data = request.json
    new_word = data.get("word")
    file_path = "automod_words.json"
    if not new_word:
        return jsonify({"error": "Missing word"}), 400

    if os.path.exists(file_path):
        words = json.load(open(file_path))
    else:
        words = []

    if new_word not in words:
        words.append(new_word)
        json.dump(words, open(file_path, "w"))
    return jsonify({"success": True, "word": new_word})

@app.route("/api/allowed_users", methods=["POST"])
def update_allowed_users():
    data = request.json
    guild = str(data.get("guild_id"))
    user = str(data.get("user_id"))
    if not guild or not user:
        return jsonify({"error": "Missing guild/user"}), 400

    allowed = {}
    if os.path.exists("allowed_users.json"):
        allowed = json.load(open("allowed_users.json"))

    if guild not in allowed:
        allowed[guild] = []

    if user not in allowed[guild]:
        allowed[guild].append(user)

    json.dump(allowed, open("allowed_users.json", "w"))
    return jsonify({"success": True, "guild_id": guild, "user_id": user})


def run():
    app.run(host='0.0.0.0', port=8080)
