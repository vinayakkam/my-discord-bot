from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from threading import Thread
import json
import os
import sys
import subprocess
import hmac
import hashlib
from datetime import datetime
import requests
import base64
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# ── Config file paths ────────────────────────────────────────────────────────
CONFIG_DIR = "config"
GUILD_COMMANDS_FILE = os.path.join(CONFIG_DIR, "guild_commands.json")
AUTOMOD_FILE = os.path.join(CONFIG_DIR, "automod_config.json")
AUTOMOD_ENABLED_FILE = os.path.join(CONFIG_DIR, "automod_enabled.json")
ALLOWED_USERS_FILE = os.path.join(CONFIG_DIR, "allowed_users.json")
WELCOME_CHANNELS_FILE = os.path.join(CONFIG_DIR, "welcome_channels.json")
API_LOGS_FILE = os.path.join(CONFIG_DIR, "api_logs.json")

os.makedirs(CONFIG_DIR, exist_ok=True)

# ── In-memory storage ────────────────────────────────────────────────────────
guild_commands = {}
automod_config = {}
automod_enabled = {}
allowed_users = {}
welcome_channels = {}
api_logs = []

# ── Env ──────────────────────────────────────────────────────────────────────
API_KEY = os.getenv('API_KEY', 'Olittech447443456989260909-087')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')  # Secret for HMAC verification
GITHUB_REPO = os.getenv('GITHUB_REPO', 'vinayakkam/my-discord-bot')
GITHUB_BRANCH = os.getenv('GITHUB_BRANCH', 'main')
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '1414168461172539454')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')
CUSTOM_DOMAIN = os.getenv('CUSTOM_DOMAIN', 'api.olittechnologies.co.in')

bot_instance = None

# ── Minimalist Dark Theme Template ────────────────────────────────────────────
INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OLIT Bot Core</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --surface: #111827;
            --surface-hover: #1f2937;
            --border: #1f293d;
            --text-main: #f3f4f6;
            --text-muted: #6b7280;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.15);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.15);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 24px;
            -webkit-font-smoothing: antialiased;
        }

        .card {
            width: 100%;
            max-width: 720px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
            overflow: hidden;
        }

        .header {
            padding: 28px 32px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header h1 {
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-main);
        }

        .header p {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 2px;
        }

        .badge-status {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--success-glow);
            color: var(--success);
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .indicator {
            width: 6px;
            height: 6px;
            background-color: var(--success);
            border-radius: 50%;
            display: inline-block;
        }

        .meta-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            border-bottom: 1px solid var(--border);
        }

        .meta-item {
            padding: 16px 32px;
            border-right: 1px solid var(--border);
        }

        .meta-item:last-child {
            border-right: none;
        }

        .meta-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 600;
        }

        .meta-value {
            font-size: 0.9rem;
            font-weight: 500;
            margin-top: 4px;
            color: var(--text-main);
            font-family: 'JetBrains Mono', monospace;
        }

        .body-content {
            padding: 32px;
        }

        .section-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            font-weight: 700;
            margin-bottom: 16px;
        }

        .endpoints {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .endpoint-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 16px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            transition: border-color 0.15s ease;
        }

        .endpoint-row:hover {
            border-color: #374151;
        }

        .endpoint-left {
            display: flex;
            align-items: center;
            gap: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
        }

        .method {
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 700;
        }

        .method.get { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
        .method.post { background: rgba(168, 85, 247, 0.15); color: #c084fc; }

        .endpoint-desc {
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        .footer {
            padding: 16px 32px;
            background: rgba(0, 0, 0, 0.2);
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <div>
                <h1>OLIT Bot Service API</h1>
                <p>System Management & Integration Layer</p>
            </div>
            <div class="badge-status">
                <span class="indicator"></span> Online
            </div>
        </div>

        <div class="meta-grid">
            <div class="meta-item">
                <div class="meta-label">Domain</div>
                <div class="meta-value">{{ domain }}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">GitHub Auto-Sync</div>
                <div class="meta-value">{{ "Active" if github else "Inactive" }}</div>
            </div>
        </div>

        <div class="body-content">
            <div class="section-title">Core Endpoints</div>
            <div class="endpoints">
                <div class="endpoint-row">
                    <div class="endpoint-left">
                        <span class="method get">GET</span>
                        <span>/health</span>
                    </div>
                    <span class="endpoint-desc">Health Status Verification</span>
                </div>
                <div class="endpoint-row">
                    <div class="endpoint-left">
                        <span class="method post">POST</span>
                        <span>/webhook</span>
                    </div>
                    <span class="endpoint-desc">GitHub Deployment Listener</span>
                </div>
                <div class="endpoint-row">
                    <div class="endpoint-left">
                        <span class="method get">GET</span>
                        <span>/api/stats</span>
                    </div>
                    <span class="endpoint-desc">Service Telemetry</span>
                </div>
                <div class="endpoint-row">
                    <div class="endpoint-left">
                        <span class="method post">POST</span>
                        <span>/api/add_command</span>
                    </div>
                    <span class="endpoint-desc">Custom Command Registration</span>
                </div>
            </div>
        </div>

        <div class="footer">
            <span>OLIT Technologies &copy; {{ year }}</span>
            <span>v3.0.0</span>
        </div>
    </div>
</body>
</html>
"""


# ── Persistence ──────────────────────────────────────────────────────────────
def load_all_data():
    global guild_commands, automod_config, automod_enabled, allowed_users, welcome_channels, api_logs

    def _load(path, default):
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️  Load error {path}: {e}")
        return default

    guild_commands = _load(GUILD_COMMANDS_FILE, {})
    automod_config = _load(AUTOMOD_FILE, {})
    automod_enabled = {int(k): v for k, v in _load(AUTOMOD_ENABLED_FILE, {}).items()}
    allowed_users = _load(ALLOWED_USERS_FILE, {})
    raw_wc = _load(WELCOME_CHANNELS_FILE, {})
    welcome_channels = {int(k): int(v) for k, v in raw_wc.items()}
    api_logs = _load(API_LOGS_FILE, [])[-1000:]

    print(f"✅ Loaded data for guilds and automod configurations.")


def _save(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"❌ Save error {path}: {e}")


def save_guild_commands():   _save(GUILD_COMMANDS_FILE, guild_commands)


def save_automod_config():   _save(AUTOMOD_FILE, automod_config)


def save_automod_enabled():  _save(AUTOMOD_ENABLED_FILE, {str(k): v for k, v in automod_enabled.items()})


def save_allowed_users():    _save(ALLOWED_USERS_FILE, allowed_users)


def save_welcome_channels(): _save(WELCOME_CHANNELS_FILE, {str(k): str(v) for k, v in welcome_channels.items()})


def save_api_logs():
    try:
        with open(API_LOGS_FILE, 'w') as f:
            json.dump(api_logs[-1000:], f, indent=2)
    except Exception as e:
        print(f"❌ Save logs error: {e}")


# ── GitHub sync ───────────────────────────────────────────────────────────────
def commit_to_github(file_path, content, message):
    if not GITHUB_TOKEN:
        return
    try:
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}'
        headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'User-Agent': 'OLIT-Bot-API'}
        sha = None
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            sha = r.json().get('sha')
        payload = {'message': message, 'content': base64.b64encode(content.encode()).decode(), 'branch': GITHUB_BRANCH}
        if sha:
            payload['sha'] = sha
        requests.put(url, headers=headers, json=payload)
    except Exception as e:
        print(f"⚠️  GitHub sync error: {e}")


# ── Auto-Deploy & Webhook Security Helper ─────────────────────────────────────
def verify_signature(payload_body, secret, signature_header):
    """Verifies that the webhook payload was sent by GitHub."""
    if not secret or not signature_header:
        return True  # Skip check if secret isn't configured

    hash_object = hmac.new(secret.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


def deploy_and_restart():
    """Pulls changes from git, installs requirements, and exits process to trigger auto-restart."""
    try:
        print("🔄 Webhook triggered deployment! Pulling latest changes from Git...")
        subprocess.run(["git", "pull", "origin", GITHUB_BRANCH], check=True)

        if os.path.exists("requirements.txt"):
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

        print("✅ Git pull successful. Shutting down process to trigger service restart...")
        os._exit(0)
    except Exception as e:
        print(f"❌ Auto-deploy failed: {e}")


# ── Request logging ───────────────────────────────────────────────────────────
def log_req(endpoint, method, data):
    api_logs.append({
        'timestamp': datetime.now().isoformat(),
        'endpoint': endpoint,
        'method': method,
        'data': str(data)[:300],
        'ip': request.remote_addr
    })
    if len(api_logs) % 10 == 0:
        save_api_logs()


# ── Auth decorator ────────────────────────────────────────────────────────────
def require_api_key(f):
    def wrapper(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if not key:
            return jsonify({'success': False, 'error': 'Missing API key'}), 401
        if key != API_KEY:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 403
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


# ── Root / Health ─────────────────────────────────────────────────────────────
@app.route('/')
def home():
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'status': 'running',
            'service': 'OLIT Discord Bot API',
            'domain': CUSTOM_DOMAIN,
            'version': '3.0',
        })
    return render_template_string(INDEX_HTML, domain=CUSTOM_DOMAIN, github=bool(GITHUB_TOKEN), year=datetime.now().year)


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'status': 404,
        'timestamp': datetime.now().isoformat()
    }), 404


# ── Webhook Auto-Deploy Endpoint ──────────────────────────────────────────────
@app.route('/webhook', methods=['GET', 'POST'])
def github_webhook():
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'message': 'Webhook listener active. Send a POST request from GitHub to trigger deployment.'
        }), 200

    # 1. Check GitHub HMAC signature if secret configured
    signature = request.headers.get('X-Hub-Signature-256')
    if GITHUB_SECRET and not verify_signature(request.data, GITHUB_SECRET, signature):
        return jsonify({'success': False, 'error': 'Invalid webhook signature'}), 401

    # 2. Check Event Type
    event = request.headers.get('X-GitHub-Event', 'push')
    if event == 'ping':
        return jsonify({'success': True, 'message': 'Ping acknowledged'}), 200

    data = request.json or {}
    expected_ref = f"refs/heads/{GITHUB_BRANCH}"

    # Verify branch matches push event target
    if data.get('ref') and data.get('ref') != expected_ref:
        return jsonify({'success': True, 'message': f'Ignored branch {data.get("ref")}'}), 200

    # 3. Trigger auto-deploy background thread
    Thread(target=deploy_and_restart, daemon=True).start()
    log_req('/webhook', 'POST', {'ref': data.get('ref')})

    return jsonify({'success': True, 'message': 'Deployment process initialized.'}), 200


# ── Commands ──────────────────────────────────────────────────────────────────
@app.route('/api/add_command', methods=['POST'])
@require_api_key
def add_command():
    try:
        data = request.json
        guild_id = str(data.get('guild_id', ''))
        command = data.get('command', '').lower().strip()
        response = data.get('response', '').strip()
        description = data.get('description', '')

        if not guild_id or not command or not response:
            return jsonify({'success': False, 'error': 'guild_id, command, and response are required'}), 400

        guild_commands.setdefault(guild_id, {})[command] = {
            'response': response,
            'description': description,
            'added_at': datetime.now().isoformat()
        }
        save_guild_commands()
        commit_to_github('config/guild_commands.json', guild_commands, f'🤖 Add command !{command}')
        log_req('/api/add_command', 'POST', data)
        return jsonify({'success': True, 'message': f'Command "!{command}" added'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/remove_command', methods=['POST'])
@require_api_key
def remove_command():
    try:
        data = request.json
        guild_id = str(data.get('guild_id', ''))
        command = data.get('command', '').lower().strip()

        if guild_id in guild_commands and command in guild_commands[guild_id]:
            del guild_commands[guild_id][command]
            save_guild_commands()
            commit_to_github('config/guild_commands.json', guild_commands, f'🗑️ Remove command !{command}')
            log_req('/api/remove_command', 'POST', data)
            return jsonify({'success': True, 'message': 'Command removed'})
        return jsonify({'success': False, 'error': 'Command not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/commands/<guild_id>', methods=['GET'])
def get_commands(guild_id):
    cmds = guild_commands.get(str(guild_id), {})
    return jsonify({'success': True, 'commands': cmds, 'count': len(cmds)})


# ── Automod ───────────────────────────────────────────────────────────────────
@app.route('/api/automod', methods=['POST'])
@require_api_key
def manage_automod():
    try:
        data = request.json
        guild_id = str(data.get('guild_id', ''))
        word = data.get('word', '').lower().strip()
        action = data.get('action', 'add').lower()

        if not guild_id or not word:
            return jsonify({'success': False, 'error': 'guild_id and word required'}), 400
        if action not in ('add', 'remove'):
            return jsonify({'success': False, 'error': 'action must be add or remove'}), 400

        automod_config.setdefault(guild_id, [])
        guild_id_int = int(guild_id)

        if action == 'add':
            if word not in automod_config[guild_id]:
                automod_config[guild_id].append(word)
            if not automod_enabled.get(guild_id_int):
                automod_enabled[guild_id_int] = True
                save_automod_enabled()
            message = f'"{word}" added to automod'
        else:
            if word in automod_config[guild_id]:
                automod_config[guild_id].remove(word)
                message = f'"{word}" removed from automod'
            else:
                return jsonify({'success': False, 'error': 'Word not found'}), 404

        save_automod_config()
        commit_to_github('config/automod_config.json', automod_config, f'🛡️ Automod: {action} "{word}"')
        log_req('/api/automod', 'POST', data)
        return jsonify(
            {'success': True, 'message': message, 'automod_enabled': automod_enabled.get(guild_id_int, False)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod_enable', methods=['POST'])
@require_api_key
def set_automod_enable():
    try:
        data = request.json
        guild_id = int(data.get('guild_id', 0))
        enabled = bool(data.get('enabled', True))

        automod_enabled[guild_id] = enabled
        save_automod_enabled()
        commit_to_github('config/automod_enabled.json',
                         {str(k): v for k, v in automod_enabled.items()},
                         f'🛡️ Automod {"on" if enabled else "off"} for {guild_id}')
        log_req('/api/automod_enable', 'POST', data)
        return jsonify(
            {'success': True, 'message': f'Automod {"enabled" if enabled else "disabled"}', 'automod_enabled': enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod_enabled/<guild_id>', methods=['GET'])
def get_automod_status(guild_id):
    return jsonify({'success': True, 'automod_enabled': automod_enabled.get(int(guild_id), False)})


@app.route('/api/automod/<guild_id>', methods=['GET'])
def get_automod_words(guild_id):
    words = automod_config.get(str(guild_id), [])
    return jsonify({'success': True, 'words': words, 'count': len(words)})


# ── Allowed users ─────────────────────────────────────────────────────────────
@app.route('/api/allowed_users', methods=['POST'])
@require_api_key
def manage_allowed_users():
    try:
        data = request.json
        guild_id = str(data.get('guild_id', ''))
        user_id = str(data.get('user_id', ''))
        action = data.get('action', 'add').lower()

        if not guild_id or not user_id:
            return jsonify({'success': False, 'error': 'guild_id and user_id required'}), 400

        allowed_users.setdefault(guild_id, [])

        if action == 'add':
            if user_id not in allowed_users[guild_id]:
                allowed_users[guild_id].append(user_id)
            message = f'User {user_id} added to exempt list'
        else:
            if user_id in allowed_users[guild_id]:
                allowed_users[guild_id].remove(user_id)
                message = f'User {user_id} removed from exempt list'
            else:
                return jsonify({'success': False, 'error': 'User not found'}), 404

        save_allowed_users()
        commit_to_github('config/allowed_users.json', allowed_users, f'👥 User {action}: {user_id}')
        log_req('/api/allowed_users', 'POST', data)
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/allowed_users/<guild_id>', methods=['GET'])
def get_allowed_users(guild_id):
    users = allowed_users.get(str(guild_id), [])
    return jsonify({'success': True, 'users': users, 'count': len(users)})


# ── Welcome channel ───────────────────────────────────────────────────────────
@app.route('/api/channels/<guild_id>', methods=['GET'])
@require_api_key
def get_channels(guild_id):
    try:
        if bot_instance is None:
            return jsonify({'success': False, 'error': 'Bot not connected to API yet'}), 503

        import asyncio

        async def _fetch():
            guild = bot_instance.get_guild(int(guild_id))
            if guild is None:
                try:
                    guild = await bot_instance.fetch_guild(int(guild_id))
                except Exception:
                    return None
            channels = await guild.fetch_channels()
            return [
                {
                    'id': str(c.id),
                    'name': c.name,
                    'type': c.type.value,
                    'position': c.position,
                    'parent_id': str(c.category_id) if c.category_id else None,
                    'parent_name': c.category.name if c.category else None,
                }
                for c in channels
                if c.type.value in (0, 5)
            ]

        loop = asyncio.new_event_loop()
        channels = loop.run_until_complete(_fetch())
        loop.close()

        if channels is None:
            return jsonify({'success': False, 'error': 'Bot is not in that server'}), 404

        channels.sort(key=lambda c: (c.get('parent_id') or '', c.get('position', 0)))

        return jsonify({'success': True, 'channels': channels, 'count': len(channels)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/welcome_channel', methods=['POST'])
@require_api_key
def set_welcome_channel():
    try:
        data = request.json
        guild_id = int(data.get('guild_id', 0))
        channel_id = int(data.get('channel_id', 0))

        welcome_channels[guild_id] = channel_id
        save_welcome_channels()
        commit_to_github('config/welcome_channels.json',
                         {str(k): str(v) for k, v in welcome_channels.items()},
                         f'👋 Welcome channel set for {guild_id}')
        log_req('/api/welcome_channel', 'POST', data)
        return jsonify({'success': True, 'message': f'Welcome channel set', 'channel_id': str(channel_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/welcome_channel/<guild_id>', methods=['GET'])
def get_welcome_channel(guild_id):
    ch = welcome_channels.get(int(guild_id))
    return jsonify({'success': True, 'channel_id': str(ch) if ch else None})


# ── Full guild config ─────────────────────────────────────────────────────────
@app.route('/api/config/<guild_id>', methods=['GET'])
@require_api_key
def get_config(guild_id):
    try:
        gid_str = str(guild_id)
        gid_int = int(guild_id)
        return jsonify({'success': True, 'config': {
            'guild_id': gid_str,
            'commands': guild_commands.get(gid_str, {}),
            'automod_words': automod_config.get(gid_str, []),
            'automod_enabled': automod_enabled.get(gid_int, False),
            'allowed_users': allowed_users.get(gid_str, []),
            'welcome_channel': welcome_channels.get(gid_int),
            'timestamp': datetime.now().isoformat(),
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Stats ─────────────────────────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
@require_api_key
def get_stats():
    try:
        total_guilds = len(set(
            list(guild_commands.keys()) +
            list(automod_config.keys()) +
            list(allowed_users.keys()) +
            [str(k) for k in welcome_channels.keys()]
        ))
        return jsonify({'success': True, 'stats': {
            'total_guilds_configured': total_guilds,
            'total_custom_commands': sum(len(v) for v in guild_commands.values()),
            'total_automod_words': sum(len(v) for v in automod_config.values()),
            'total_allowed_users': sum(len(v) for v in allowed_users.values()),
            'automod_enabled_guilds': sum(1 for v in automod_enabled.values() if v),
            'welcome_channels_configured': len(welcome_channels),
            'api_requests_logged': len(api_logs),
            'timestamp': datetime.now().isoformat(),
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Logs ──────────────────────────────────────────────────────────────────────
@app.route('/api/logs', methods=['GET'])
@require_api_key
def get_logs():
    limit = min(request.args.get('limit', 50, type=int), 500)
    return jsonify({'success': True, 'logs': api_logs[-limit:], 'total': len(api_logs)})


# ── Bot helper functions ──────────────────────────────────────────────────────
def get_guild_commands(guild_id):      return guild_commands.get(str(guild_id), {})


def get_automod_words(guild_id):       return automod_config.get(str(guild_id), [])


def get_automod_enabled_status(guild_id): return automod_enabled.get(int(guild_id), False)


def get_allowed_users_list(guild_id):  return allowed_users.get(str(guild_id), [])


def get_welcome_channel_id(guild_id):  return welcome_channels.get(int(guild_id))


def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot


# ── Runner ────────────────────────────────────────────────────────────────────
def run():
    load_all_data()
    print("=" * 50)
    print("🚀 OLIT Discord Bot API v3.0")
    print(f"🌐 Domain: https://{CUSTOM_DOMAIN}")
    print(f"🔗 Webhook: https://{CUSTOM_DOMAIN}/webhook")
    print(f"🔑 API Key: {'set' if API_KEY else 'MISSING'}")
    print(f"🔗 GitHub: {'enabled' if GITHUB_TOKEN else 'disabled'}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5023)


def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
    print("✅ API server started on :5023")


if __name__ == '__main__':
    run()