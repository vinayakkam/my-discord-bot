from flask import Flask, jsonify, request
from flask_cors import CORS
from threading import Thread
import json
import os
from datetime import datetime
import requests
import base64
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ── CORS: allow the dashboard origin ────────────────────────────────────────
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# ── Config file paths ────────────────────────────────────────────────────────
CONFIG_DIR             = "config"
GUILD_COMMANDS_FILE    = os.path.join(CONFIG_DIR, "guild_commands.json")
AUTOMOD_FILE           = os.path.join(CONFIG_DIR, "automod_config.json")
AUTOMOD_ENABLED_FILE   = os.path.join(CONFIG_DIR, "automod_enabled.json")
ALLOWED_USERS_FILE     = os.path.join(CONFIG_DIR, "allowed_users.json")
WELCOME_CHANNELS_FILE  = os.path.join(CONFIG_DIR, "welcome_channels.json")
API_LOGS_FILE          = os.path.join(CONFIG_DIR, "api_logs.json")

os.makedirs(CONFIG_DIR, exist_ok=True)

# ── In-memory storage ────────────────────────────────────────────────────────
guild_commands  = {}
automod_config  = {}
automod_enabled = {}
allowed_users   = {}
welcome_channels = {}
api_logs        = []

# ── Env ──────────────────────────────────────────────────────────────────────
API_KEY            = os.getenv('API_KEY', 'Olittech447443456989260909-087')
GITHUB_TOKEN       = os.getenv('GITHUB_TOKEN')
GITHUB_REPO        = os.getenv('GITHUB_REPO', 'vinayakkam/my-discord-bot')
GITHUB_BRANCH      = os.getenv('GITHUB_BRANCH', 'main')
DISCORD_CLIENT_ID  = os.getenv('DISCORD_CLIENT_ID', '1414168461172539454')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')

bot_instance = None


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

    guild_commands   = _load(GUILD_COMMANDS_FILE, {})
    automod_config   = _load(AUTOMOD_FILE, {})
    automod_enabled  = {int(k): v for k, v in _load(AUTOMOD_ENABLED_FILE, {}).items()}
    allowed_users    = _load(ALLOWED_USERS_FILE, {})
    raw_wc           = _load(WELCOME_CHANNELS_FILE, {})
    welcome_channels = {int(k): int(v) for k, v in raw_wc.items()}
    api_logs         = _load(API_LOGS_FILE, [])[-1000:]

    print(f"✅ Loaded: {len(guild_commands)} guilds, {len(automod_config)} automod, "
          f"{len(welcome_channels)} welcome channels")


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
        url     = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}'
        headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'User-Agent': 'OLIT-Bot-API'}
        sha     = None
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            sha = r.json().get('sha')
        payload = {'message': message, 'content': base64.b64encode(content.encode()).decode(), 'branch': GITHUB_BRANCH}
        if sha:
            payload['sha'] = sha
        requests.put(url, headers=headers, json=payload)
    except Exception as e:
        print(f"⚠️  GitHub sync: {e}")


# ── Request logging ───────────────────────────────────────────────────────────
def log_req(endpoint, method, data):
    api_logs.append({
        'timestamp': datetime.now().isoformat(),
        'endpoint':  endpoint,
        'method':    method,
        'data':      str(data)[:300],
        'ip':        request.remote_addr
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
    return jsonify({
        'status':  'running',
        'service': 'OLIT Discord Bot API',
        'version': '3.0',
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


# ── Commands ──────────────────────────────────────────────────────────────────
@app.route('/api/add_command', methods=['POST'])
@require_api_key
def add_command():
    try:
        data        = request.json
        guild_id    = str(data.get('guild_id', ''))
        command     = data.get('command', '').lower().strip()
        response    = data.get('response', '').strip()
        description = data.get('description', '')

        if not guild_id or not command or not response:
            return jsonify({'success': False, 'error': 'guild_id, command, and response are required'}), 400

        guild_commands.setdefault(guild_id, {})[command] = {
            'response':    response,
            'description': description,
            'added_at':    datetime.now().isoformat()
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
        data     = request.json
        guild_id = str(data.get('guild_id', ''))
        command  = data.get('command', '').lower().strip()

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
        data     = request.json
        guild_id = str(data.get('guild_id', ''))
        word     = data.get('word', '').lower().strip()
        action   = data.get('action', 'add').lower()

        if not guild_id or not word:
            return jsonify({'success': False, 'error': 'guild_id and word required'}), 400
        if action not in ('add', 'remove'):
            return jsonify({'success': False, 'error': 'action must be add or remove'}), 400

        automod_config.setdefault(guild_id, [])
        guild_id_int = int(guild_id)

        if action == 'add':
            if word not in automod_config[guild_id]:
                automod_config[guild_id].append(word)
            # auto-enable on first word
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
        return jsonify({'success': True, 'message': message, 'automod_enabled': automod_enabled.get(guild_id_int, False)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod_enable', methods=['POST'])
@require_api_key
def set_automod_enable():
    try:
        data     = request.json
        guild_id = int(data.get('guild_id', 0))
        enabled  = bool(data.get('enabled', True))

        automod_enabled[guild_id] = enabled
        save_automod_enabled()
        commit_to_github('config/automod_enabled.json',
                         {str(k): v for k, v in automod_enabled.items()},
                         f'🛡️ Automod {"on" if enabled else "off"} for {guild_id}')
        log_req('/api/automod_enable', 'POST', data)
        return jsonify({'success': True, 'message': f'Automod {"enabled" if enabled else "disabled"}', 'automod_enabled': enabled})
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
        data     = request.json
        guild_id = str(data.get('guild_id', ''))
        user_id  = str(data.get('user_id', ''))
        action   = data.get('action', 'add').lower()

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
    """Return text channels for a guild using the bot instance."""
    try:
        if bot_instance is None:
            return jsonify({'success': False, 'error': 'Bot not connected to API yet'}), 503

        import asyncio

        async def _fetch():
            guild = bot_instance.get_guild(int(guild_id))
            if guild is None:
                # Try fetching if not in cache
                try:
                    guild = await bot_instance.fetch_guild(int(guild_id))
                except Exception:
                    return None
            channels = await guild.fetch_channels()
            return [
                {
                    'id':        str(c.id),
                    'name':      c.name,
                    'type':      c.type.value,
                    'position':  c.position,
                    'parent_id': str(c.category_id) if c.category_id else None,
                    'parent_name': c.category.name if c.category else None,
                }
                for c in channels
                if c.type.value in (0, 5)   # text + announcement
            ]

        # Run async from sync Flask context
        loop = asyncio.new_event_loop()
        channels = loop.run_until_complete(_fetch())
        loop.close()

        if channels is None:
            return jsonify({'success': False, 'error': 'Bot is not in that server'}), 404

        # Sort: by category position then channel position
        channels.sort(key=lambda c: (c.get('parent_id') or '', c.get('position', 0)))

        return jsonify({'success': True, 'channels': channels, 'count': len(channels)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@require_api_key
def set_welcome_channel():
    try:
        data       = request.json
        guild_id   = int(data.get('guild_id', 0))
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
            'guild_id':       gid_str,
            'commands':       guild_commands.get(gid_str, {}),
            'automod_words':  automod_config.get(gid_str, []),
            'automod_enabled': automod_enabled.get(gid_int, False),
            'allowed_users':  allowed_users.get(gid_str, []),
            'welcome_channel': welcome_channels.get(gid_int),
            'timestamp':      datetime.now().isoformat(),
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
            'total_custom_commands':   sum(len(v) for v in guild_commands.values()),
            'total_automod_words':     sum(len(v) for v in automod_config.values()),
            'total_allowed_users':     sum(len(v) for v in allowed_users.values()),
            'automod_enabled_guilds':  sum(1 for v in automod_enabled.values() if v),
            'welcome_channels_configured': len(welcome_channels),
            'api_requests_logged':     len(api_logs),
            'timestamp':               datetime.now().isoformat(),
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Logs ──────────────────────────────────────────────────────────────────────
@app.route('/api/logs', methods=['GET'])
@require_api_key
def get_logs():
    limit = min(request.args.get('limit', 50, type=int), 500)
    return jsonify({'success': True, 'logs': api_logs[-limit:], 'total': len(api_logs)})


# ── Bot helper functions (called from main.py) ────────────────────────────────
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