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
API_LOGS_FILE = os.path.join(CONFIG_DIR, "api_logs.json")

os.makedirs(CONFIG_DIR, exist_ok=True)

# In-memory storage
guild_commands = {}
automod_config = {}
automod_enabled = {}  # {guild_id: True/False} - tracks if automod is enabled
allowed_users = {}
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
    global guild_commands, automod_config, automod_enabled, allowed_users, api_logs

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
                automod_enabled = json.load(f)
                # Convert string keys to int for consistency
                automod_enabled = {int(k): v for k, v in automod_enabled.items()}
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
        # Convert int keys to strings for JSON
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


def save_api_logs():
    try:
        with open(API_LOGS_FILE, 'w') as f:
            json.dump(api_logs[-1000:], f, indent=2)
    except Exception as e:
        print(f"❌ Error saving API logs: {e}")


def commit_to_github(file_path, content, commit_message):
    """Commit a file to GitHub repository"""
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
            print(f"✅ GitHub commit success: {res['commit']['html_url']}")
            return {'success': True, 'commit_url': res['commit']['html_url']}
        else:
            print(f"❌ GitHub commit failed: {r.status_code}")
            return {'success': False, 'message': r.text}

    except Exception as e:
        print(f"❌ GitHub commit error: {e}")
        return {'success': False, 'message': str(e)}


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


def set_bot_instance(bot):
    """Set bot instance for DM capabilities"""
    global bot_instance
    bot_instance = bot
    print("✅ Bot instance set for API integration")


async def send_welcome_dm_to_owner(guild_id):
    """Send beautiful welcome DM to server owner"""
    if not bot_instance:
        print("⚠️ Bot instance not set, cannot send DM")
        return False

    try:
        import discord

        guild = bot_instance.get_guild(int(guild_id))
        if not guild or not guild.owner:
            print(f"⚠️ Guild {guild_id} or owner not found")
            return False

        embed = discord.Embed(
            title="🎉 Welcome to OLIT Bot!",
            description=f"Thank you for adding OLIT Bot to **{guild.name}**!\n\nYour server is now connected to our API system.",
            color=0x5865F2  # Discord Blurple
        )

        if bot_instance.user.avatar:
            embed.set_thumbnail(url=bot_instance.user.avatar.url)

        embed.add_field(
            name="✨ Quick Setup Complete",
            value="Your server has been automatically configured and is ready to use!",
            inline=False
        )

        embed.add_field(
            name="📋 Custom Commands",
            value="• Create custom commands via the admin panel\n• Commands are instantly available server-wide\n• Edit and remove commands anytime",
            inline=False
        )

        embed.add_field(
            name="🛡️ Auto-Moderation",
            value="• Built-in N-word filter (always active)\n• Add custom banned words via API\n• 24-hour timeout for violations\n• Automatic message deletion",
            inline=False
        )

        embed.add_field(
            name="👥 User Management",
            value="• Configure allowed/exempt users\n• API-based permission system\n• Flexible access control",
            inline=False
        )

        embed.add_field(
            name="🔧 Admin Panel Access",
            value=f"**Server ID:** `{guild_id}`\n\nUse this ID to manage your server in the admin panel.",
            inline=False
        )

        embed.add_field(
            name="📚 Useful Commands",
            value="`!help` - View all commands\n`!api_status` - Check API connection\n`!listcommands` - See custom commands\n`!automod status` - Check automod settings",
            inline=False
        )

        embed.add_field(
            name="🔗 GitHub Integration",
            value="All configuration changes are automatically backed up to GitHub for version control and disaster recovery.",
            inline=False
        )

        embed.set_footer(
            text=f"{guild.name} • OLIT Bot API v2.2",
            icon_url=guild.icon.url if guild.icon else None
        )

        embed.timestamp = datetime.now()

        await guild.owner.send(embed=embed)
        print(f"✅ Welcome DM sent to owner of {guild.name} ({guild_id})")
        return True

    except discord.Forbidden:
        print(f"⚠️ Cannot DM owner of guild {guild_id} - DMs disabled")
        return False
    except Exception as e:
        print(f"❌ Error sending welcome DM: {e}")
        return False


def require_api_key(f):
    """Decorator to require API key authentication"""

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
        'version': '2.3',
        'endpoints': {
            'health': '/',
            'add_command': '/api/add_command [POST]',
            'remove_command': '/api/remove_command [POST]',
            'get_commands': '/api/commands/<guild_id> [GET]',
            'automod': '/api/automod [POST]',
            'automod_status': '/api/automod/<guild_id> [GET]',
            'automod_enabled': '/api/automod_enabled/<guild_id> [GET]',
            'users': '/api/allowed_users [POST]',
            'get_users': '/api/allowed_users/<guild_id> [GET]',
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

        # Check if this is a new guild (not in config)
        is_new_guild = (
                guild_id not in guild_commands and
                guild_id not in automod_config and
                guild_id not in allowed_users
        )

        if guild_id not in guild_commands:
            guild_commands[guild_id] = {}

        guild_commands[guild_id][command] = {
            'response': response,
            'description': description,
            'added_at': datetime.now().isoformat()
        }

        save_guild_commands()

        # Send welcome DM if new guild
        if is_new_guild and bot_instance:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_welcome_dm_to_owner(guild_id))
                loop.close()
            except Exception as e:
                print(f"⚠️ Failed to send welcome DM: {e}")

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

        log_api_request('/api/add_command', 'POST', data, request.remote_addr)

        response_data = {
            'success': True,
            'message': f'Command "{command}" added/updated for guild {guild_id}',
            'command': command,
            'guild_id': guild_id,
            'new_guild_welcome_sent': is_new_guild
        }

        if github_sync_result is not None:
            response_data['github_synced'] = github_sync_result

        return jsonify(response_data)

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
                    commit_to_github(
                        'config/guild_commands.json',
                        guild_commands,
                        f'🗑️ Remove command "{command}" from guild {guild_id}'
                    )
                except Exception as e:
                    print(f"⚠️ GitHub sync failed: {e}")

            log_api_request('/api/remove_command', 'POST', data, request.remote_addr)
            return jsonify({'success': True, 'message': f'Command "{command}" removed'})
        else:
            return jsonify({'success': False, 'error': 'Command not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/commands/<guild_id>', methods=['GET'])
def get_commands_public(guild_id):
    try:
        guild_id = str(guild_id)
        commands = guild_commands.get(guild_id, {})
        return jsonify({
            'success': True,
            'guild_id': guild_id,
            'commands': commands,
            'count': len(commands)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod', methods=['POST'])
@require_api_key
def manage_automod():
    """Add/remove banned words and AUTO-ENABLE automod"""
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

        # Check if this is a new guild
        is_new_guild = (
                guild_id_str not in guild_commands and
                guild_id_str not in automod_config and
                guild_id_str not in allowed_users
        )

        if guild_id_str not in automod_config:
            automod_config[guild_id_str] = []

        if action == 'add':
            if word not in automod_config[guild_id_str]:
                automod_config[guild_id_str].append(word)
                message = f'Word "{word}" added to automod for guild {guild_id_str}'

                # ✨ AUTO-ENABLE AUTOMOD when first word is added
                if guild_id_int not in automod_enabled or not automod_enabled[guild_id_int]:
                    automod_enabled[guild_id_int] = True
                    save_automod_enabled()
                    message += ' | ✅ Auto-moderation ENABLED for this server'
                    print(f"🛡️ Auto-enabled automod for guild {guild_id_int}")
            else:
                message = f'Word "{word}" already in automod list'
        else:
            if word in automod_config[guild_id_str]:
                automod_config[guild_id_str].remove(word)
                message = f'Word "{word}" removed from automod for guild {guild_id_str}'
            else:
                return jsonify({'success': False, 'error': 'Word not found'}), 404

        save_automod_config()

        # Send welcome DM if new guild
        if is_new_guild and bot_instance:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_welcome_dm_to_owner(guild_id_str))
                loop.close()
            except Exception as e:
                print(f"⚠️ Failed to send welcome DM: {e}")

        log_api_request('/api/automod', 'POST', data, request.remote_addr)

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                # Commit both automod config and enabled state
                commit_to_github(
                    'config/automod_config.json',
                    automod_config,
                    f'🛡️ {"Add" if action == "add" else "Remove"} automod word "{word}" for guild {guild_id_str}'
                )

                if action == 'add':
                    enabled_str_keys = {str(k): v for k, v in automod_enabled.items()}
                    commit_to_github(
                        'config/automod_enabled.json',
                        enabled_str_keys,
                        f'🛡️ Auto-enable automod for guild {guild_id_str}'
                    )
            except Exception as e:
                print(f"⚠️ GitHub sync failed: {e}")

        return jsonify({
            'success': True,
            'message': message,
            'guild_id': guild_id_str,
            'word': word,
            'action': action,
            'automod_enabled': automod_enabled.get(guild_id_int, False),
            'new_guild_welcome_sent': is_new_guild
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod/<guild_id>', methods=['GET'])
def get_automod_public(guild_id):
    """Get automod words for a guild"""
    try:
        guild_id = str(guild_id)
        words = automod_config.get(guild_id, [])
        return jsonify({
            'success': True,
            'guild_id': guild_id,
            'words': words,
            'count': len(words)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/automod_enabled/<guild_id>', methods=['GET'])
def get_automod_enabled(guild_id):
    """Check if automod is enabled for a guild"""
    try:
        guild_id_int = int(guild_id)
        enabled = automod_enabled.get(guild_id_int, False)
        return jsonify({
            'success': True,
            'guild_id': str(guild_id),
            'automod_enabled': enabled
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/allowed_users', methods=['POST'])
@require_api_key
def manage_allowed_users():
    """Add/remove allowed users (exempt from automod)"""
    try:
        data = request.json
        guild_id = str(data.get('guild_id'))
        user_id = str(data.get('user_id'))
        action = data.get('action', 'add').lower()

        if not guild_id or not user_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        if action not in ['add', 'remove']:
            return jsonify({'success': False, 'error': 'Action must be "add" or "remove"'}), 400

        # Check if new guild
        is_new_guild = (
                guild_id not in guild_commands and
                guild_id not in automod_config and
                guild_id not in allowed_users
        )

        if guild_id not in allowed_users:
            allowed_users[guild_id] = []

        if action == 'add':
            if user_id not in allowed_users[guild_id]:
                allowed_users[guild_id].append(user_id)
                message = f'User {user_id} added to allowed users (automod exempt) for guild {guild_id}'
            else:
                message = f'User {user_id} already in allowed users list'
        else:
            if user_id in allowed_users[guild_id]:
                allowed_users[guild_id].remove(user_id)
                message = f'User {user_id} removed from allowed users for guild {guild_id}'
            else:
                return jsonify({'success': False, 'error': 'User not found'}), 404

        save_allowed_users()

        # Send welcome DM if new guild
        if is_new_guild and bot_instance:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_welcome_dm_to_owner(guild_id))
                loop.close()
            except Exception as e:
                print(f"⚠️ Failed to send welcome DM: {e}")

        log_api_request('/api/allowed_users', 'POST', data, request.remote_addr)

        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                commit_to_github(
                    'config/allowed_users.json',
                    allowed_users,
                    f'👥 {"Add" if action == "add" else "Remove"} exempt user {user_id} for guild {guild_id}'
                )
            except Exception as e:
                print(f"⚠️ GitHub sync failed: {e}")

        return jsonify({
            'success': True,
            'message': message,
            'guild_id': guild_id,
            'user_id': user_id,
            'action': action,
            'new_guild_welcome_sent': is_new_guild
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/allowed_users/<guild_id>', methods=['GET'])
def get_allowed_users_public(guild_id):
    """Get allowed/exempt users for a guild"""
    try:
        guild_id = str(guild_id)
        users = allowed_users.get(guild_id, [])
        return jsonify({
            'success': True,
            'guild_id': guild_id,
            'users': users,
            'count': len(users)
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
            list(allowed_users.keys())
        ))

        total_commands = sum(len(cmds) for cmds in guild_commands.values())
        total_automod_words = sum(len(words) for words in automod_config.values())
        total_allowed_users = sum(len(users) for users in allowed_users.values())
        automod_enabled_count = sum(1 for enabled in automod_enabled.values() if enabled)

        stats = {
            'total_guilds_configured': total_guilds,
            'total_custom_commands': total_commands,
            'total_automod_words': total_automod_words,
            'total_allowed_users': total_allowed_users,
            'automod_enabled_guilds': automod_enabled_count,
            'api_requests_logged': len(api_logs),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_guild_commands(guild_id):
    return guild_commands.get(str(guild_id), {})


def get_automod_words(guild_id):
    return automod_config.get(str(guild_id), [])


def get_automod_enabled_status(guild_id):
    """Check if automod is enabled for a guild"""
    return automod_enabled.get(int(guild_id), False)


def get_allowed_users_list(guild_id):
    return allowed_users.get(str(guild_id), [])


def run():
    load_all_data()
    print("=" * 50)
    print("🚀 OLIT Discord Bot API Server Starting")
    print("=" * 50)
    print(f"✅ Guilds with commands: {len(guild_commands)}")
    print(f"✅ Guilds with automod: {len(automod_config)}")
    print(f"✅ Guilds with automod enabled: {sum(1 for v in automod_enabled.values() if v)}")
    print(f"✅ Guilds with allowed users: {len(allowed_users)}")
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