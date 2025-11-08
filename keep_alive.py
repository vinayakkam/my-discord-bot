from flask import Flask, jsonify, request
from flask_cors import CORS
from threading import Thread
import json
import os
from datetime import datetime
import requests
import base64
from dotenv import load_dotenv
import asyncio

load_dotenv()
app = Flask(__name__)
CORS(app)

# Configuration file paths
CONFIG_DIR = "config"
GUILD_COMMANDS_FILE = os.path.join(CONFIG_DIR, "guild_commands.json")
AUTOMOD_FILE = os.path.join(CONFIG_DIR, "automod_config.json")
AUTOMOD_ENABLED_FILE = os.path.join(CONFIG_DIR, "automod_enabled.json")
ALLOWED_USERS_FILE = os.path.join(CONFIG_DIR, "allowed_users.json")
WELCOME_CHANNELS_FILE = os.path.join(CONFIG_DIR, "welcome_channels.json")
API_LOGS_FILE = os.path.join(CONFIG_DIR, "api_logs.json")

os.makedirs(CONFIG_DIR, exist_ok=True)

# In-memory storage
guild_commands = {}
automod_config = {}
automod_enabled = {}
allowed_users = {}
welcome_channels = {}  # {guild_id: channel_id}
api_logs = []

# API Key
API_KEY = os.getenv('API_KEY')

# GitHub Integration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'vinayakkam/my-discord-bot')
GITHUB_BRANCH = os.getenv('GITHUB_BRANCH', 'main')

# Bot instance reference (set by main.py)
bot_instance = None


def load_all_data():
    """Load all configuration data from JSON files"""
    global guild_commands, automod_config, automod_enabled, allowed_users, welcome_channels, api_logs

    try:
        if os.path.exists(GUILD_COMMANDS_FILE):
            with open(GUILD_COMMANDS_FILE, 'r') as f:
                guild_commands = json.load(f)
                print(f"✅ Loaded {len(guild_commands)} guild command configs")
    except Exception as e:
        print(f"⚠️ Error loading guild commands: {e}")
        guild_commands = {}

    try:
        if os.path.exists(AUTOMOD_FILE):
            with open(AUTOMOD_FILE, 'r') as f:
                automod_config = json.load(f)
                print(f"✅ Loaded {len(automod_config)} automod configs")
    except Exception as e:
        print(f"⚠️ Error loading automod config: {e}")
        automod_config = {}

    try:
        if os.path.exists(AUTOMOD_ENABLED_FILE):
            with open(AUTOMOD_ENABLED_FILE, 'r') as f:
                data = json.load(f)
                automod_enabled = {int(k): v for k, v in data.items()}
                print(f"✅ Loaded {len(automod_enabled)} automod enabled states")
    except Exception as e:
        print(f"⚠️ Error loading automod enabled: {e}")
        automod_enabled = {}

    try:
        if os.path.exists(ALLOWED_USERS_FILE):
            with open(ALLOWED_USERS_FILE, 'r') as f:
                allowed_users = json.load(f)
                print(f"✅ Loaded {len(allowed_users)} allowed user configs")
    except Exception as e:
        print(f"⚠️ Error loading allowed users: {e}")
        allowed_users = {}

    try:
        if os.path.exists(WELCOME_CHANNELS_FILE):
            with open(WELCOME_CHANNELS_FILE, 'r') as f:
                data = json.load(f)
                welcome_channels = {int(k): int(v) for k, v in data.items()}
                print(f"✅ Loaded {len(welcome_channels)} welcome channel configs")
    except Exception as e:
        print(f"⚠️ Error loading welcome channels: {e}")
        welcome_channels = {}

    try:
        if os.path.exists(API_LOGS_FILE):
            with open(API_LOGS_FILE, 'r') as f:
                api_logs = json.load(f)
                api_logs = api_logs[-1000:]
    except Exception as e:
        print(f"⚠️ Error loading API logs: {e}")
        api_logs = []


def save_guild_commands():
    try:
        with open(GUILD_COMMANDS_FILE, 'w') as f:
            json.dump(guild_commands, f, indent=2)
        print(f"💾 Saved guild commands")
    except Exception as e:
        print(f"❌ Error saving guild commands: {e}")


def save_automod_config():
    try:
        with open(AUTOMOD_FILE, 'w') as f:
            json.dump(automod_config, f, indent=2)
        print(f"💾 Saved automod config")
    except Exception as e:
        print(f"❌ Error saving automod config: {e}")


def save_automod_enabled():
    try:
        enabled_str_keys = {str(k): v for k, v in automod_enabled.items()}
        with open(AUTOMOD_ENABLED_FILE, 'w') as f:
            json.dump(enabled_str_keys, f, indent=2)
        print(f"💾 Saved automod enabled states")
    except Exception as e:
        print(f"❌ Error saving automod enabled: {e}")


def save_allowed_users():
    try:
        with open(ALLOWED_USERS_FILE, 'w') as f:
            json.dump(allowed_users, f, indent=2)
        print(f"💾 Saved allowed users")
    except Exception as e:
        print(f"❌ Error saving allowed users: {e}")


def save_welcome_channels():
    try:
        channels_str_keys = {str(k): str(v) for k, v in welcome_channels.items()}
        with open(WELCOME_CHANNELS_FILE, 'w') as f:
            json.dump(channels_str_keys, f, indent=2)
        print(f"💾 Saved welcome channels")
    except Exception as e:
        print(f"❌ Error saving welcome channels: {e}")


def save_api_logs():
    try:
        with open(API_LOGS_FILE, 'w') as f:
            json.dump(api_logs[-1000:], f, indent=2)
    except Exception as e:
        print(f"❌ Error saving API logs: {e}")


def commit_to_github(file_path, content, commit_message):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {'success': False, 'message': 'GitHub integration not configured'}

    try:
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)

        api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}'
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'OLIT-Bot-API'
        }

        r = requests.get(api_url, headers=headers)
        sha = r.json().get('sha') if r.status_code == 200 else None

        payload = {
            'message': commit_message,
            'content': base64.b64encode(content.encode()).decode(),
            'branch': GITHUB_BRANCH
        }
        if sha:
            payload['sha'] = sha

        r = requests.put(api_url, headers=headers, json=payload)

        if r.status_code in [200, 201]:
            res = r.json()
            print(f"✅ GitHub commit success")
            return {'success': True, 'commit_url': res['commit']['html_url']}
        else:
            print(f"❌ GitHub commit failed: {r.status_code}")
            return {'success': False, 'message': r.text}

    except Exception as e:
        print(f"❌ GitHub commit error: {e}")
        return {'success': False, 'message': str(e)}


def log_api_request(endpoint, method, data, ip_address):
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'endpoint': endpoint,
        'method': method,
        'data': str(data)[:500],
        'ip': ip_address
    }
    api_logs.append(log_entry)
    if len(api_logs) % 10 == 0:
        save_api_logs()


def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot
    print("✅ Bot instance set for API integration")


def require_api_key(f):
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key')
        if not provided_key:
            return jsonify({'success': False, 'error': 'Missing API key'}), 401
        if provided_key != API_KEY:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'service': 'OLIT Discord Bot API',
        'version': '2.4',
        'endpoints': {
            'health': '/',
            'commands': '/api/commands/<guild_id> [GET]',
            'automod': '/api/automod [POST/GET]',
            'automod_enable': '/api/automod_enable [POST]',
            'users': '/api/allowed_users [POST/GET]',
            'welcome': '/api/welcome_channel [POST/GET]',
            'config': '/api/config/<guild_id> [GET]',
            'stats': '/api/stats [GET]'
        }
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/api/add_command', methods=['POST'])
@require_api_key
def add_command():
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        command = data.get('command', '').lower()
        response = data.get('response')
        description = data.get('description', '')

        if not guild_id or not command or not response:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        if guild_id not in guild_commands:
            guild_commands[guild_id] = {}

        guild_commands[guild_id][command] = {
            'response': response,
            'description': description,
            'added_at': datetime.now().isoformat()
        }

        save_guild_commands()

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                commit_to_github(
                    'config/guild_commands.json',
                    guild_commands,
                    f'🤖 Add command "{command}" for guild {guild_id}'
                )
            except Exception as e:
                print(f"⚠️ GitHub sync failed: {e}")

        log_api_request('/api/add_command', 'POST', data, request.remote_addr)

        return jsonify({
            'success': True,
            'message': f'Command "{command}" added/updated',
            'command': command,
            'guild_id': guild_id
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/remove_command', methods=['POST'])
@require_api_key
def remove_command():
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        command = data.get('command', '').lower()

        if not guild_id or not command:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        if guild_id in guild_commands and command in guild_commands[guild_id]:
            del guild_commands[guild_id][command]
            save_guild_commands()

            if GITHUB_TOKEN and GITHUB_REPO:
                try:
                    commit_to_github('config/guild_commands.json', guild_commands, f'🗑️ Remove command "{command}"')
                except:
                    pass

            log_api_request('/api/remove_command', 'POST', data, request.remote_addr)
            return jsonify({'success': True, 'message': f'Command removed'})
        else:
            return jsonify({'success': False, 'error': 'Command not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/commands/<guild_id>', methods=['GET'])
def get_commands_public(guild_id):
    try:
        commands = guild_commands.get(str(guild_id), {})
        return jsonify({'success': True, 'guild_id': str(guild_id), 'commands': commands, 'count': len(commands)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod', methods=['POST'])
@require_api_key
def manage_automod():
    try:
        data = request.json
        guild_id_str = str(data.get('guild_id'))
        guild_id_int = int(guild_id_str)
        word = data.get('word', '').lower()
        action = data.get('action', 'add').lower()

        if not guild_id_str or not word:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        if action not in ['add', 'remove']:
            return jsonify({'success': False, 'error': 'Action must be "add" or "remove"'}), 400

        if guild_id_str not in automod_config:
            automod_config[guild_id_str] = []

        if action == 'add':
            if word not in automod_config[guild_id_str]:
                automod_config[guild_id_str].append(word)
                message = f'Word "{word}" added to automod'

                # Auto-enable automod
                if guild_id_int not in automod_enabled or not automod_enabled[guild_id_int]:
                    automod_enabled[guild_id_int] = True
                    save_automod_enabled()
                    message += ' | ✅ Automod ENABLED'
            else:
                message = f'Word already in automod list'
        else:
            if word in automod_config[guild_id_str]:
                automod_config[guild_id_str].remove(word)
                message = f'Word removed from automod'
            else:
                return jsonify({'success': False, 'error': 'Word not found'}), 404

        save_automod_config()
        log_api_request('/api/automod', 'POST', data, request.remote_addr)

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                commit_to_github('config/automod_config.json', automod_config, f'🛡️ Automod update')
                if action == 'add':
                    enabled_str = {str(k): v for k, v in automod_enabled.items()}
                    commit_to_github('config/automod_enabled.json', enabled_str, f'🛡️ Auto-enable automod')
            except:
                pass

        return jsonify({
            'success': True,
            'message': message,
            'automod_enabled': automod_enabled.get(guild_id_int, False)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod/<guild_id>', methods=['GET'])
def get_automod_public(guild_id):
    try:
        words = automod_config.get(str(guild_id), [])
        return jsonify({'success': True, 'guild_id': str(guild_id), 'words': words, 'count': len(words)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod_enable', methods=['POST'])
@require_api_key
def set_automod_enable():
    """Enable or disable automod for a guild"""
    try:
        data = request.json
        guild_id = int(data.get('guild_id'))
        enabled = data.get('enabled', True)

        automod_enabled[guild_id] = enabled
        save_automod_enabled()

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                enabled_str = {str(k): v for k, v in automod_enabled.items()}
                commit_to_github('config/automod_enabled.json', enabled_str, f'🛡️ {"Enable" if enabled else "Disable"} automod')
            except:
                pass

        log_api_request('/api/automod_enable', 'POST', data, request.remote_addr)

        return jsonify({
            'success': True,
            'message': f'Automod {"enabled" if enabled else "disabled"}',
            'automod_enabled': enabled
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod_enabled/<guild_id>', methods=['GET'])
def get_automod_enabled(guild_id):
    try:
        enabled = automod_enabled.get(int(guild_id), False)
        return jsonify({'success': True, 'guild_id': str(guild_id), 'automod_enabled': enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/allowed_users', methods=['POST'])
@require_api_key
def manage_allowed_users():
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        user_id = str(data.get('user_id'))
        action = data.get('action', 'add').lower()

        if not guild_id or not user_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        if action not in ['add', 'remove']:
            return jsonify({'success': False, 'error': 'Action must be "add" or "remove"'}), 400

        if guild_id not in allowed_users:
            allowed_users[guild_id] = []

        if action == 'add':
            if user_id not in allowed_users[guild_id]:
                allowed_users[guild_id].append(user_id)
                message = f'User {user_id} added to exempt list'
            else:
                message = f'User already in exempt list'
        else:
            if user_id in allowed_users[guild_id]:
                allowed_users[guild_id].remove(user_id)
                message = f'User {user_id} removed from exempt list'
            else:
                return jsonify({'success': False, 'error': 'User not found'}), 404

        save_allowed_users()
        log_api_request('/api/allowed_users', 'POST', data, request.remote_addr)

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                commit_to_github('config/allowed_users.json', allowed_users, f'👥 User management')
            except:
                pass

        return jsonify({'success': True, 'message': message})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/allowed_users/<guild_id>', methods=['GET'])
def get_allowed_users_public(guild_id):
    try:
        users = allowed_users.get(str(guild_id), [])
        return jsonify({'success': True, 'guild_id': str(guild_id), 'users': users, 'count': len(users)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/welcome_channel', methods=['POST'])
@require_api_key
def set_welcome_channel():
    """Set welcome channel for a guild"""
    try:
        data = request.json
        guild_id = int(data.get('guild_id'))
        channel_id = int(data.get('channel_id'))

        welcome_channels[guild_id] = channel_id
        save_welcome_channels()

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                channels_str = {str(k): str(v) for k, v in welcome_channels.items()}
                commit_to_github('config/welcome_channels.json', channels_str, f'👋 Set welcome channel')
            except:
                pass

        log_api_request('/api/welcome_channel', 'POST', data, request.remote_addr)

        return jsonify({
            'success': True,
            'message': f'Welcome channel set to {channel_id}',
            'guild_id': str(guild_id),
            'channel_id': str(channel_id)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/welcome_channel/<guild_id>', methods=['GET'])
def get_welcome_channel(guild_id):
    try:
        channel_id = welcome_channels.get(int(guild_id))
        return jsonify({
            'success': True,
            'guild_id': str(guild_id),
            'channel_id': str(channel_id) if channel_id else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/<guild_id>', methods=['GET'])
@require_api_key
def get_config(guild_id):
    try:
        guild_id_str = str(guild_id)
        guild_id_int = int(guild_id)

        config = {
            'guild_id': guild_id_str,
            'commands': guild_commands.get(guild_id_str, {}),
            'automod_words': automod_config.get(guild_id_str, []),
            'automod_enabled': automod_enabled.get(guild_id_int, False),
            'allowed_users': allowed_users.get(guild_id_str, []),
            'welcome_channel': welcome_channels.get(guild_id_int),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify({'success': True, 'config': config})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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

        stats = {
            'total_guilds_configured': total_guilds,
            'total_custom_commands': sum(len(cmds) for cmds in guild_commands.values()),
            'total_automod_words': sum(len(words) for words in automod_config.values()),
            'total_allowed_users': sum(len(users) for users in allowed_users.values()),
            'automod_enabled_guilds': sum(1 for enabled in automod_enabled.values() if enabled),
            'welcome_channels_configured': len(welcome_channels),
            'api_requests_logged': len(api_logs),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/logs', methods=['GET'])
@require_api_key
def get_logs():
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 500)
        recent_logs = api_logs[-limit:]
        return jsonify({'success': True, 'logs': recent_logs, 'total': len(api_logs)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_guild_commands(guild_id):
    return guild_commands.get(str(guild_id), {})


def get_automod_words(guild_id):
    return automod_config.get(str(guild_id), [])


def get_automod_enabled_status(guild_id):
    return automod_enabled.get(int(guild_id), False)


def get_allowed_users_list(guild_id):
    return allowed_users.get(str(guild_id), [])


def get_welcome_channel_id(guild_id):
    return welcome_channels.get(int(guild_id))


def run():
    load_all_data()
    print("=" * 50)
    print("🚀 OLIT Discord Bot API Server Starting")
    print("=" * 50)
    print(f"✅ Guilds with commands: {len(guild_commands)}")
    print(f"✅ Guilds with automod: {len(automod_config)}")
    print(f"✅ Guilds with automod enabled: {sum(1 for v in automod_enabled.values() if v)}")
    print(f"✅ Guilds with allowed users: {len(allowed_users)}")
    print(f"✅ Welcome channels configured: {len(welcome_channels)}")
    print(f"🔑 API Key configured: {'Yes' if API_KEY else 'No'}")
    print(f"🔗 GitHub sync: {'Enabled' if GITHUB_TOKEN and GITHUB_REPO else 'Disabled'}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("✅ Keep-alive server started on port 8080")


if __name__ == '__main__':
    run()