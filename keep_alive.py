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
CORS(app)  # Enable CORS for all routes

# Configuration file paths
CONFIG_DIR = "config"
GUILD_COMMANDS_FILE = os.path.join(CONFIG_DIR, "guild_commands.json")
AUTOMOD_FILE = os.path.join(CONFIG_DIR, "automod_config.json")
ALLOWED_USERS_FILE = os.path.join(CONFIG_DIR, "allowed_users.json")
API_LOGS_FILE = os.path.join(CONFIG_DIR, "api_logs.json")

# Ensure config directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)

# In-memory storage (backed by JSON files)
guild_commands = {}  # {guild_id: {command: {"response": text, "description": desc}}}
automod_config = {}  # {guild_id: [banned_words]}
allowed_users = {}  # {guild_id: [user_ids]}
api_logs = []  # [{timestamp, endpoint, method, data, ip}]

# API Key for authentication (set via environment variable)
API_KEY = os.getenv('API_KEY')

# GitHub Integration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'vinayakkam/my-discord-bot')
GITHUB_BRANCH = os.getenv('GITHUB_BRANCH', 'main')


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def load_all_data():
    """Load all configuration data from JSON files"""
    global guild_commands, automod_config, allowed_users, api_logs

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
        if os.path.exists(ALLOWED_USERS_FILE):
            with open(ALLOWED_USERS_FILE, 'r') as f:
                allowed_users = json.load(f)
                print(f"✅ Loaded {len(allowed_users)} allowed user configs")
    except Exception as e:
        print(f"⚠️ Error loading allowed users: {e}")
        allowed_users = {}

    try:
        if os.path.exists(API_LOGS_FILE):
            with open(API_LOGS_FILE, 'r') as f:
                api_logs = json.load(f)
                api_logs = api_logs[-1000:]
    except Exception as e:
        print(f"⚠️ Error loading API logs: {e}")
        api_logs = []


def save_guild_commands():
    """Save guild commands to JSON file"""
    try:
        with open(GUILD_COMMANDS_FILE, 'w') as f:
            json.dump(guild_commands, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving guild commands: {e}")


def save_automod_config():
    """Save automod configuration to JSON file"""
    try:
        with open(AUTOMOD_FILE, 'w') as f:
            json.dump(automod_config, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving automod config: {e}")


def save_allowed_users():
    """Save allowed users to JSON file"""
    try:
        with open(ALLOWED_USERS_FILE, 'w') as f:
            json.dump(allowed_users, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving allowed users: {e}")


def save_api_logs():
    """Save API logs to JSON file"""
    try:
        with open(API_LOGS_FILE, 'w') as f:
            json.dump(api_logs[-1000:], f, indent=2)
    except Exception as e:
        print(f"❌ Error saving API logs: {e}")


# ============================================
# GITHUB INTEGRATION FUNCTIONS
# ============================================

def commit_to_github(file_path, content, commit_message):
    """Commit a file to GitHub repository"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {
            'success': False,
            'message': 'GitHub integration not configured'
        }

    try:
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)

        api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}'
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        response = requests.get(api_url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json()['sha']

        content_encoded = base64.b64encode(content.encode()).decode()
        data = {
            'message': commit_message,
            'content': content_encoded,
            'branch': GITHUB_BRANCH
        }

        if sha:
            data['sha'] = sha

        response = requests.put(api_url, headers=headers, json=data)

        if response.status_code in [200, 201]:
            result = response.json()
            return {
                'success': True,
                'message': f'Successfully committed to GitHub: {commit_message}',
                'commit_url': result['commit']['html_url'],
                'sha': result['content']['sha']
            }
        else:
            return {
                'success': False,
                'message': f'GitHub API error: {response.status_code} - {response.text}'
            }

    except Exception as e:
        return {
            'success': False,
            'message': f'Error committing to GitHub: {str(e)}'
        }


def log_api_request(endpoint, method, data, ip_address):
    """Log API request for monitoring"""
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


# ============================================
# AUTHENTICATION MIDDLEWARE
# ============================================

def require_api_key(f):
    """Decorator to require API key authentication"""
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key')

        if not provided_key:
            return jsonify({
                'success': False,
                'error': 'Missing API key. Include X-API-Key header.'
            }), 401

        if provided_key != API_KEY:
            return jsonify({
                'success': False,
                'error': 'Invalid API key'
            }), 403

        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


# ============================================
# HEALTH CHECK ROUTES
# ============================================

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'service': 'OLIT Discord Bot API',
        'version': '2.1',
        'endpoints': {
            'health': '/',
            'commands': '/api/add_command',
            'automod': '/api/automod',
            'users': '/api/allowed_users',
            'config': '/api/config/<guild_id>',
            'stats': '/api/stats',
            'logs': '/api/logs'
        }
    })


@app.route('/health')
def health():
    """Alternative health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


# ============================================
# COMMAND MANAGEMENT ROUTES
# ============================================

@app.route('/api/add_command', methods=['POST'])
@require_api_key
def add_command():
    """
    Add or update a custom text command for a guild

    Body: {
        "guild_id": "123456789",
        "command": "welcome",
        "response": "Welcome to our server!",
        "description": "Welcome message" (optional)
    }
    """
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        command = data.get('command', '').lower()
        response = data.get('response')
        description = data.get('description', '')

        # Validation
        if not guild_id or not command or not response:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: guild_id, command, response'
            }), 400

        # Initialize guild commands if not exists
        if guild_id not in guild_commands:
            guild_commands[guild_id] = {}

        # Add/update command
        guild_commands[guild_id][command] = {
            'response': response,
            'description': description,
            'added_at': datetime.now().isoformat()
        }

        # Save to file
        save_guild_commands()

        # Auto-sync to GitHub if configured
        github_sync_result = None
        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                sync_result = commit_to_github(
                    'config/guild_commands.json',
                    guild_commands,
                    f'🤖 Add command "{command}" for guild {guild_id}'
                )
                github_sync_result = sync_result.get('success', False)
            except Exception as e:
                print(f"⚠️ GitHub sync failed: {e}")

        # Log request
        log_api_request('/api/add_command', 'POST', data, request.remote_addr)

        response_data = {
            'success': True,
            'message': f'Command "{command}" added/updated for guild {guild_id}',
            'command': command,
            'guild_id': guild_id
        }

        if github_sync_result is not None:
            response_data['github_synced'] = github_sync_result

        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/remove_command', methods=['POST'])
@require_api_key
def remove_command():
    """
    Remove a custom command from a guild

    Body: {
        "guild_id": "123456789",
        "command": "welcome"
    }
    """
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        command = data.get('command', '').lower()

        if not guild_id or not command:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: guild_id, command'
            }), 400

        if guild_id in guild_commands and command in guild_commands[guild_id]:
            del guild_commands[guild_id][command]
            save_guild_commands()

            # Auto-sync to GitHub
            if GITHUB_TOKEN and GITHUB_REPO:
                try:
                    commit_to_github(
                        'config/guild_commands.json',
                        guild_commands,
                        f'🗑️ Remove command "{command}" from guild {guild_id}'
                    )
                except Exception as e:
                    print(f"⚠️ GitHub sync failed: {e}")

            return jsonify({
                'success': True,
                'message': f'Command "{command}" removed from guild {guild_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Command not found'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# AUTOMOD MANAGEMENT ROUTES
# ============================================

@app.route('/api/automod', methods=['POST'])
@require_api_key
def manage_automod():
    """
    Add or remove banned words for automod

    Body: {
        "guild_id": "123456789",
        "word": "badword",
        "action": "add" | "remove"
    }
    """
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        word = data.get('word', '').lower()
        action = data.get('action', 'add').lower()

        if not guild_id or not word:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: guild_id, word'
            }), 400

        if action not in ['add', 'remove']:
            return jsonify({
                'success': False,
                'error': 'Action must be "add" or "remove"'
            }), 400

        if guild_id not in automod_config:
            automod_config[guild_id] = []

        if action == 'add':
            if word not in automod_config[guild_id]:
                automod_config[guild_id].append(word)
                message = f'Word "{word}" added to automod for guild {guild_id}'
            else:
                message = f'Word "{word}" already in automod list'
        else:
            if word in automod_config[guild_id]:
                automod_config[guild_id].remove(word)
                message = f'Word "{word}" removed from automod for guild {guild_id}'
            else:
                return jsonify({
                    'success': False,
                    'error': 'Word not found in automod list'
                }), 404

        save_automod_config()
        log_api_request('/api/automod', 'POST', data, request.remote_addr)

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                commit_to_github(
                    'config/automod_config.json',
                    automod_config,
                    f'🛡️ {"Add" if action == "add" else "Remove"} automod word "{word}" for guild {guild_id}'
                )
            except Exception as e:
                print(f"⚠️ GitHub sync failed: {e}")

        return jsonify({
            'success': True,
            'message': message,
            'guild_id': guild_id,
            'word': word,
            'action': action
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# USER MANAGEMENT ROUTES
# ============================================

@app.route('/api/allowed_users', methods=['POST'])
@require_api_key
def manage_allowed_users():
    """
    Add or remove allowed users for a guild

    Body: {
        "guild_id": "123456789",
        "user_id": "987654321",
        "action": "add" | "remove"
    }
    """
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        user_id = str(data.get('user_id'))
        action = data.get('action', 'add').lower()

        if not guild_id or not user_id:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: guild_id, user_id'
            }), 400

        if action not in ['add', 'remove']:
            return jsonify({
                'success': False,
                'error': 'Action must be "add" or "remove"'
            }), 400

        if guild_id not in allowed_users:
            allowed_users[guild_id] = []

        if action == 'add':
            if user_id not in allowed_users[guild_id]:
                allowed_users[guild_id].append(user_id)
                message = f'User {user_id} added to allowed users for guild {guild_id}'
            else:
                message = f'User {user_id} already in allowed users list'
        else:
            if user_id in allowed_users[guild_id]:
                allowed_users[guild_id].remove(user_id)
                message = f'User {user_id} removed from allowed users for guild {guild_id}'
            else:
                return jsonify({
                    'success': False,
                    'error': 'User not found in allowed users list'
                }), 404

        save_allowed_users()
        log_api_request('/api/allowed_users', 'POST', data, request.remote_addr)

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                commit_to_github(
                    'config/allowed_users.json',
                    allowed_users,
                    f'👥 {"Add" if action == "add" else "Remove"} user {user_id} for guild {guild_id}'
                )
            except Exception as e:
                print(f"⚠️ GitHub sync failed: {e}")

        return jsonify({
            'success': True,
            'message': message,
            'guild_id': guild_id,
            'user_id': user_id,
            'action': action
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# CONFIGURATION RETRIEVAL ROUTES
# ============================================

@app.route('/api/config/<guild_id>', methods=['GET'])
@require_api_key
def get_config(guild_id):
    """Get all configuration for a specific guild"""
    try:
        guild_id = str(guild_id)

        config = {
            'guild_id': guild_id,
            'commands': guild_commands.get(guild_id, {}),
            'automod_words': automod_config.get(guild_id, []),
            'allowed_users': allowed_users.get(guild_id, []),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'config': config
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/guilds', methods=['GET'])
@require_api_key
def list_guilds():
    """List all configured guilds"""
    try:
        all_guild_ids = set()
        all_guild_ids.update(guild_commands.keys())
        all_guild_ids.update(automod_config.keys())
        all_guild_ids.update(allowed_users.keys())

        guilds_list = []
        for guild_id in all_guild_ids:
            guilds_list.append({
                'guild_id': guild_id,
                'commands_count': len(guild_commands.get(guild_id, {})),
                'automod_words_count': len(automod_config.get(guild_id, [])),
                'allowed_users_count': len(allowed_users.get(guild_id, []))
            })

        return jsonify({
            'success': True,
            'guilds': guilds_list,
            'total': len(guilds_list)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# STATISTICS & MONITORING ROUTES
# ============================================

@app.route('/api/stats', methods=['GET'])
@require_api_key
def get_stats():
    """Get API usage statistics"""
    try:
        total_guilds = len(set(list(guild_commands.keys()) +
                               list(automod_config.keys()) +
                               list(allowed_users.keys())))

        total_commands = sum(len(cmds) for cmds in guild_commands.values())
        total_automod_words = sum(len(words) for words in automod_config.values())
        total_allowed_users = sum(len(users) for users in allowed_users.values())

        stats = {
            'total_guilds_configured': total_guilds,
            'total_custom_commands': total_commands,
            'total_automod_words': total_automod_words,
            'total_allowed_users': total_allowed_users,
            'api_requests_logged': len(api_logs),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/logs', methods=['GET'])
@require_api_key
def get_logs():
    """Get recent API logs"""
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 500)

        recent_logs = api_logs[-limit:]

        return jsonify({
            'success': True,
            'logs': recent_logs,
            'total': len(api_logs)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# UTILITY FUNCTIONS FOR BOT ACCESS
# ============================================

def get_guild_commands(guild_id):
    """Get commands for a guild (called by bot)"""
    return guild_commands.get(str(guild_id), {})


def get_automod_words(guild_id):
    """Get automod words for a guild (called by bot)"""
    return automod_config.get(str(guild_id), [])


def get_allowed_users_list(guild_id):
    """Get allowed users for a guild (called by bot)"""
    return allowed_users.get(str(guild_id), [])


# ============================================
# SERVER INITIALIZATION
# ============================================

def run():
    """Start Flask server"""
    load_all_data()

    print("=" * 50)
    print("🚀 OLIT Discord Bot API Server Starting")
    print("=" * 50)
    print(f"✅ Guilds with commands: {len(guild_commands)}")
    print(f"✅ Guilds with automod: {len(automod_config)}")
    print(f"✅ Guilds with allowed users: {len(allowed_users)}")
    print(f"🔑 API Key configured: {'Yes' if API_KEY else 'No'}")
    print("=" * 50)

    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    """Start Flask server in a separate thread"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("✅ Keep-alive server started on port 8080")