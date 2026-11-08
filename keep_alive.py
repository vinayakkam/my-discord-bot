from flask import Flask, jsonify, request, render_template_string
from flask import g as flask_g
from flask_cors import CORS
from threading import Thread, Lock
from functools import wraps
import asyncio
from concurrent.futures import TimeoutError as FuturesTimeout
import json
import os
import sys
import subprocess
import hmac
import hashlib
import shutil
import time
from datetime import datetime
import requests
import base64
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ── CORS ──────────────────────────────────────────────────────────────────────
# The dashboard frontend lives in a separate repo on a different origin, so it
# calls these endpoints cross-origin with an X-API-Key header. That is a
# non-simple header, so the browser sends a preflight first -- X-API-Key has to
# be named in Access-Control-Allow-Headers or the real request never goes out.
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        'ALLOWED_ORIGINS',
        'https://olittechnologies.co.in,https://www.olittechnologies.co.in,'
        'http://localhost:8000,http://127.0.0.1:8000',
    ).split(',') if o.strip()
]

CORS(
    app,
    # Named origins rather than "*": the dashboard now sends the visitor's
    # Discord token, and a wildcard would let any page on the web spend that
    # token against this API from the visitor's browser. CORS is not the
    # authorization boundary -- require_guild_access() is -- but there is no
    # reason to invite the request. Override with ALLOWED_ORIGINS if the
    # dashboard is ever served from somewhere else.
    resources={r"/*": {"origins": ALLOWED_ORIGINS}},
    supports_credentials=True,
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    methods=["GET", "POST", "OPTIONS"],
)

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

# How long an API request will wait for the bot's event loop to answer.
BOT_CALL_TIMEOUT = 15

# Reported by /api/public/status and shown on the status page.
SERVICE_VERSION = '3.1'
SERVICE_STARTED_AT = datetime.now()


def run_on_bot_loop(coro_factory, timeout: int = BOT_CALL_TIMEOUT):
    """Run a coroutine on the bot's event loop from this Flask worker thread.

    Flask handlers run in a different thread from the bot. discord.py objects
    (and the aiohttp session underneath them) are bound to the loop the bot was
    started on, so spinning up a fresh loop here and awaiting them fails with
    "attached to a different loop". `run_coroutine_threadsafe` hands the work
    to the correct loop and blocks this thread for the result.

    `coro_factory` must be a zero-argument callable returning a fresh
    coroutine; it is only called once the target loop is confirmed alive.

    Returns (ok, value). On failure `value` is a human-readable reason.
    """
    if bot_instance is None:
        return False, 'Bot not connected to API yet'

    loop = getattr(bot_instance, 'loop', None)
    if loop is None or not loop.is_running():
        return False, 'Bot event loop is not running yet'

    try:
        future = asyncio.run_coroutine_threadsafe(coro_factory(), loop)
        return True, future.result(timeout=timeout)
    except FuturesTimeout:
        return False, f'Bot did not respond within {timeout}s'
    except Exception as exc:
        return False, str(exc)

# ── Public pages ──────────────────────────────────────────────────────────────
# `/` and `/webhook` are the only HTML this service serves, and both are public
# and unauthenticated. They follow the design system of olittechnologies.co.in
# -- Geist, ink-on-paper neutrals, one orange accent, 1px rules, light by
# default and dark from the OS -- with the tokens inlined rather than loaded
# from the website, so the status page still renders if the site or a CDN is
# unreachable.
#
# Nothing guild-specific, user-specific or secret may appear on these pages or
# in the payload behind them. What they show is fixed by PUBLIC_STATUS_FIELDS
# and ENDPOINT_CATALOG below: aggregate totals, uptime, the running commit and
# whether a feature is configured -- never names, IDs, request logs or keys.

SITE_ORIGIN = 'https://olittechnologies.co.in'

# How each endpoint is authorised, and how that is labelled on the status page.
AUTH_LABELS = {
    'public': ('Public', 'No credentials. Safe to call from a browser.'),
    'signature': ('HMAC signed', 'Verified against the GitHub webhook secret.'),
    'discord': ('Discord login', 'Requires a Discord token for a server you manage.'),
}

# Single source of truth for the endpoint list the status page renders, so the
# documentation cannot drift from the routes. (method, path, auth, description)
ENDPOINT_CATALOG = [
    ('Service', [
        ('GET', '/health', 'public', 'Liveness probe. Returns status and server time.'),
        ('GET', '/api/public/status', 'public', 'Aggregate status: uptime, version, bot link, totals.'),
        ('POST', '/webhook', 'signature', 'GitHub push listener. Resets the checkout and restarts.'),
    ]),
    ('Server configuration', [
        ('GET', '/api/config/<guild>', 'discord', 'Full configuration for one server.'),
        ('POST', '/api/add_command', 'discord', 'Create or update a custom command.'),
        ('POST', '/api/remove_command', 'discord', 'Delete a custom command.'),
        ('GET', '/api/commands/<guild>', 'discord', 'List custom commands.'),
    ]),
    ('Moderation', [
        ('POST', '/api/automod', 'discord', 'Add or remove a filtered word.'),
        ('POST', '/api/automod_enable', 'discord', 'Turn the filter on or off.'),
        ('POST', '/api/allowed_users', 'discord', 'Exempt a member from filtering.'),
    ]),
    ('Server data', [
        ('GET', '/api/guilds', 'discord', 'Servers you manage that the bot is in.'),
        ('GET', '/api/channels/<guild>', 'discord', 'Text channels, for the channel picker.'),
        ('POST', '/api/welcome_channel', 'discord', 'Set or clear the welcome channel.'),
        ('GET', '/api/logs', 'discord', 'Recent API requests for one server.'),
    ]),
]

# The shared stylesheet for both pages. A subset of the website's design
# system: only the tokens and components these two pages actually use.
PAGE_CSS = """
:root {
  color-scheme: light;
  --bg-0: #fafaf9; --bg-1: #ffffff; --bg-2: #f4f4f2; --bg-3: #ebebe8;
  --bg-hover: #efefec; --border: #e5e5e1; --border-strong: #d2d2cc;
  --text-1: #111110; --text-2: #50504a; --text-3: #6d6d66;
  --accent: #ea580c; --accent-fg: #c2410c;
  --accent-dim: rgba(234, 88, 12, 0.09); --accent-border: rgba(234, 88, 12, 0.35);
  --ink: #111110; --on-ink: #fafaf9;
  --success: #16a34a; --success-fg: #15803d; --success-dim: rgba(22, 163, 74, 0.1);
  --danger: #dc2626; --danger-fg: #b91c1c; --danger-dim: rgba(220, 38, 38, 0.08);
  --warn: #d97706; --warn-fg: #a16207; --warn-dim: rgba(217, 119, 6, 0.1);
  --header-bg: rgba(250, 250, 249, 0.86);
  --radius-sm: 6px; --radius-md: 8px; --radius-lg: 12px; --radius-full: 999px;
  --font-sans: 'Geist', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace;
  --container: 1120px; --gutter: 24px; --header-h: 60px; --transition: 150ms ease;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg-0: #0c0c0b; --bg-1: #131312; --bg-2: #1a1a18; --bg-3: #232321;
    --bg-hover: #1f1f1d; --border: #262624; --border-strong: #363632;
    --text-1: #ededea; --text-2: #a8a8a0; --text-3: #8a8a82;
    --accent: #f97316; --accent-fg: #fb923c;
    --accent-dim: rgba(249, 115, 22, 0.12); --accent-border: rgba(249, 115, 22, 0.4);
    --ink: #ededea; --on-ink: #0c0c0b;
    --success: #22c55e; --success-fg: #4ade80; --success-dim: rgba(34, 197, 94, 0.12);
    --danger: #ef4444; --danger-fg: #f87171; --danger-dim: rgba(239, 68, 68, 0.12);
    --warn: #f59e0b; --warn-fg: #fbbf24; --warn-dim: rgba(245, 158, 11, 0.12);
    --header-bg: rgba(12, 12, 11, 0.86);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg-0: #0c0c0b; --bg-1: #131312; --bg-2: #1a1a18; --bg-3: #232321;
  --bg-hover: #1f1f1d; --border: #262624; --border-strong: #363632;
  --text-1: #ededea; --text-2: #a8a8a0; --text-3: #8a8a82;
  --accent: #f97316; --accent-fg: #fb923c;
  --accent-dim: rgba(249, 115, 22, 0.12); --accent-border: rgba(249, 115, 22, 0.4);
  --ink: #ededea; --on-ink: #0c0c0b;
  --success: #22c55e; --success-fg: #4ade80; --success-dim: rgba(34, 197, 94, 0.12);
  --danger: #ef4444; --danger-fg: #f87171; --danger-dim: rgba(239, 68, 68, 0.12);
  --warn: #f59e0b; --warn-fg: #fbbf24; --warn-dim: rgba(245, 158, 11, 0.12);
  --header-bg: rgba(12, 12, 11, 0.86);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-sans); font-size: 16px; line-height: 1.6;
  background: var(--bg-0); color: var(--text-1);
  -webkit-font-smoothing: antialiased;
  min-height: 100vh; display: flex; flex-direction: column;
}
a { color: inherit; text-decoration-color: var(--border-strong); text-underline-offset: 3px; }
a:hover { text-decoration-color: currentColor; }
h1 { font-size: clamp(1.9rem, 4vw, 2.6rem); font-weight: 500; letter-spacing: -0.03em; line-height: 1.1; }
h2 { font-size: 1.25rem; font-weight: 500; letter-spacing: -0.02em; }
code, .mono { font-family: var(--font-mono); font-size: 0.875em; }
.container { width: 100%; max-width: var(--container); margin: 0 auto; padding: 0 var(--gutter); }
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}

/* Header and footer, trimmed from the website's shell. */
.site-header {
  position: sticky; top: 0; z-index: 50; height: var(--header-h);
  background: var(--header-bg); backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}
.site-header__inner {
  display: flex; align-items: center; gap: 10px; height: 100%;
  max-width: var(--container); margin: 0 auto; padding: 0 var(--gutter);
}
.brand {
  display: inline-flex; align-items: center; gap: 10px;
  font-weight: 500; letter-spacing: -0.02em; text-decoration: none;
}
.brand img { width: 26px; height: 26px; border-radius: 6px; object-fit: contain; }
.brand small {
  font: 400 0.8rem var(--font-mono); color: var(--text-3);
  padding-left: 10px; border-left: 1px solid var(--border-strong);
}
.site-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.icon-btn {
  display: grid; place-items: center; width: 34px; height: 34px;
  border: 1px solid transparent; border-radius: var(--radius-md);
  background: transparent; color: var(--text-2); cursor: pointer;
  font: inherit; line-height: 1; transition: background var(--transition), color var(--transition);
}
.icon-btn:hover { background: var(--bg-2); color: var(--text-1); }
.site-footer {
  margin-top: auto; border-top: 1px solid var(--border);
  padding: 28px 0; font-size: 0.86rem; color: var(--text-2);
}
.site-footer__inner {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
}
.site-footer a { color: var(--text-2); text-decoration: none; }
.site-footer a:hover { color: var(--text-1); }

/* Page scaffolding */
main { padding: 56px 0 72px; }
.page-head { max-width: 680px; }
.page-head h1 { margin: 18px 0 14px; }
.page-head p { color: var(--text-2); font-size: 1.05rem; }
.section-label {
  display: flex; align-items: center; gap: 10px;
  font: 400 0.74rem var(--font-mono); text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-3);
}
.section-label span { color: var(--accent-fg); }
.section { margin-top: 56px; }
.section > h2 { margin-bottom: 4px; }
.section > p.sub { color: var(--text-2); font-size: 0.94rem; margin-bottom: 20px; }

.badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 2px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border);
  font: 400 0.74rem/1.6 var(--font-mono); color: var(--text-2); background: var(--bg-1);
  white-space: nowrap;
}
.badge-success { color: var(--success-fg); border-color: transparent; background: var(--success-dim); }
.badge-danger { color: var(--danger-fg); border-color: transparent; background: var(--danger-dim); }
.badge-warn { color: var(--warn-fg); border-color: transparent; background: var(--warn-dim); }
.badge-accent { color: var(--accent-fg); border-color: var(--accent-border); background: var(--accent-dim); }
.status-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  flex-shrink: 0; background: var(--text-3);
}
.status-dot.online { background: var(--success); }
.status-dot.connecting { background: var(--warn); animation: pulse 1s ease-in-out infinite; }
.status-dot.offline { background: var(--danger); }
@keyframes pulse { 50% { opacity: 0.35; } }

.card {
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 24px;
}

/* Hairline stat strip, as on the website. */
.stat-strip {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden;
}
.stat-strip > div { background: var(--bg-1); padding: 20px; }
.stat-strip strong {
  display: block; font-size: 1.6rem; font-weight: 500;
  letter-spacing: -0.03em; line-height: 1.25; color: var(--text-1);
}
.stat-strip span {
  font: 400 0.72rem var(--font-mono); color: var(--text-3);
  text-transform: uppercase; letter-spacing: 0.05em;
}

/* Endpoint catalog */
.group + .group { margin-top: 28px; }
.group-name {
  font: 500 0.72rem var(--font-mono); text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-3); margin-bottom: 10px;
}
.ep-list { border-top: 1px solid var(--border); }
.ep {
  display: grid; grid-template-columns: 56px minmax(0, 1.1fr) minmax(0, 1.4fr) auto 32px;
  gap: 14px; align-items: center;
  padding: 13px 4px; border-bottom: 1px solid var(--border);
}
.ep:hover { background: var(--bg-2); }
.method {
  font: 500 0.7rem var(--font-mono); letter-spacing: 0.04em;
  color: var(--text-2); text-align: center;
  padding: 2px 0; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-1);
}
.method.post { color: var(--accent-fg); border-color: var(--accent-border); background: var(--accent-dim); }
.ep-path { font: 500 0.86rem var(--font-mono); overflow-wrap: anywhere; }
.ep-desc { color: var(--text-2); font-size: 0.88rem; }
.copy-btn {
  width: 28px; height: 28px; display: grid; place-items: center;
  border: 1px solid transparent; border-radius: var(--radius-sm);
  background: transparent; color: var(--text-3); cursor: pointer; font: inherit;
  transition: background var(--transition), color var(--transition);
}
.copy-btn:hover { background: var(--bg-3); color: var(--text-1); }
.copy-btn svg { width: 15px; height: 15px; }

/* Key/value rows */
.kv { border-top: 1px solid var(--border); }
.kv > div {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 12px 4px; border-bottom: 1px solid var(--border);
  font-size: 0.9rem; flex-wrap: wrap;
}
.kv dt, .kv .k { color: var(--text-2); }
.kv dd, .kv .v { font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-1); }

.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  height: 36px; padding: 0 14px; border-radius: var(--radius-md);
  font-size: 0.88rem; font-weight: 500; font-family: inherit; line-height: 1;
  cursor: pointer; border: 1px solid transparent; text-decoration: none; white-space: nowrap;
  transition: background var(--transition), border-color var(--transition), opacity var(--transition);
}
.btn-primary { background: var(--ink); color: var(--on-ink); }
.btn-primary:hover { opacity: 0.86; }
.btn-secondary { background: var(--bg-1); color: var(--text-1); border-color: var(--border-strong); }
.btn-secondary:hover { background: var(--bg-2); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.hint { font-size: 0.82rem; color: var(--text-3); }
.note {
  border-left: 2px solid var(--accent-border); background: var(--accent-dim);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: 14px 18px; font-size: 0.9rem; color: var(--text-2);
}
.theme-icon-light { display: none; }
:root[data-theme="dark"] .theme-icon-light { display: block; }
:root[data-theme="dark"] .theme-icon-dark { display: none; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .theme-icon-light { display: block; }
  :root:not([data-theme="light"]) .theme-icon-dark { display: none; }
}

@media (max-width: 760px) {
  main { padding: 36px 0 56px; }
  .ep { grid-template-columns: 52px minmax(0, 1fr) auto; row-gap: 6px; }
  .ep-desc { grid-column: 2 / -1; }
  .copy-btn { display: none; }
}
"""

# Shared <head>, header and footer. `{title}`, `{head}` and `{body}` are filled
# in by _public_page(); Jinja placeholders inside `body` survive untouched
# because this is a plain str.format on the shell only.
PAGE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#fafaf9" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0c0c0b" media="(prefers-color-scheme: dark)">
<link rel="icon" type="image/png" href="SITE/assets/img/logo.png">
<script>try{{var t=localStorage.getItem('theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>{css}</style>
</head>
<body>
<header class="site-header">
  <div class="site-header__inner">
    <a href="SITE/bot/" class="brand"><img src="SITE/assets/img/logo.png" alt="" width="26" height="26">OLIT<small>API</small></a>
    <div class="site-actions">
      <button type="button" class="icon-btn" id="theme-toggle" aria-label="Toggle dark mode">
        <svg class="theme-icon-dark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <svg class="theme-icon-light" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </div>
  </div>
</header>
{body}
<footer class="site-footer">
  <div class="container site-footer__inner">
    <span>OLIT Technologies &middot; <span class="mono">{{{{ domain }}}}</span></span>
    <span><a href="SITE/bot/">Bot</a> &nbsp;&middot;&nbsp; <a href="SITE/bot/dashboard.html">Dashboard</a> &nbsp;&middot;&nbsp; <a href="SITE/privacy.html">Privacy</a></span>
  </div>
</footer>
<script>
// Theme toggle, matching the website: the choice is stored under the same
// localStorage key, though this origin keeps its own copy.
document.getElementById('theme-toggle').addEventListener('click', function () {{
  var root = document.documentElement;
  var dark = root.dataset.theme
    ? root.dataset.theme === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'light' : 'dark';
  try {{ localStorage.setItem('theme', root.dataset.theme); }} catch (e) {{}}
}});
</script>
{scripts}
</body>
</html>
"""


def _public_page(title, body, scripts=''):
    """Compose one public page from the shared shell.

    Only the shell is formatted, so Jinja tags inside `body` reach
    render_template_string untouched.
    """
    return (PAGE_SHELL
            .format(title=title, css=PAGE_CSS, body=body, scripts=scripts)
            .replace('SITE', SITE_ORIGIN))


INDEX_BODY = """
<main class="container">
  <div class="page-head">
    <p class="section-label"><span>01</span>Service status</p>
    <h1>OLIT Bot API</h1>
    <p>The backend behind the OLIT Discord bot and its dashboard. This page is public; every
       endpoint that touches a server's configuration requires a Discord login for that server.</p>
    <div class="actions" style="margin-top:24px">
      <a class="btn btn-primary" href="{{ site }}/bot/dashboard.html">Open dashboard</a>
      <button type="button" class="btn btn-secondary" id="ping-btn">Run health check</button>
      <span class="hint" id="ping-result" aria-live="polite"></span>
    </div>
  </div>

  <div class="section">
    <div class="stat-strip" id="stats">
      <div><strong id="s-state"><span class="status-dot connecting"></span></strong><span>Service</span></div>
      <div><strong id="s-uptime">&mdash;</strong><span>Uptime</span></div>
      <div><strong id="s-gateway">&mdash;</strong><span>Discord gateway</span></div>
      <div><strong id="s-servers">&mdash;</strong><span>Servers</span></div>
      <div><strong id="s-commands">&mdash;</strong><span>Custom commands</span></div>
    </div>
    <p class="hint" style="margin-top:10px" id="refreshed">Loading live status&hellip;</p>
  </div>

  <div class="section">
    <h2>Endpoints</h2>
    <p class="sub">{{ endpoint_count }} routes. Paths shown relative to <code>{{ domain }}</code>.</p>
    {% for group_name, items in endpoints %}
    <div class="group">
      <div class="group-name">{{ group_name }}</div>
      <div class="ep-list">
        {% for method, path, auth, desc in items %}
        <div class="ep">
          <span class="method {{ method|lower }}">{{ method }}</span>
          <span class="ep-path">{{ path }}</span>
          <span class="ep-desc">{{ desc }}</span>
          <span class="badge{{ ' badge-success' if auth == 'public' else ' badge-accent' }}"
                title="{{ auth_labels[auth][1] }}">{{ auth_labels[auth][0] }}</span>
          <button type="button" class="copy-btn" data-copy="https://{{ domain }}{{ path }}"
                  aria-label="Copy URL for {{ path }}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>
          </button>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
  </div>

  <div class="section">
    <h2>Build</h2>
    <p class="sub">What this instance is running.</p>
    <dl class="kv">
      <div><dt>Version</dt><dd>{{ version }}</dd></div>
      <div><dt>Commit</dt><dd id="s-commit">&mdash;</dd></div>
      <div><dt>Branch</dt><dd>{{ branch }}</dd></div>
      <div><dt>Last deploy</dt><dd id="s-deploy">&mdash;</dd></div>
      <div><dt>GitHub config sync</dt><dd>{{ "enabled" if github else "disabled" }}</dd></div>
    </dl>
    <p class="hint" style="margin-top:14px">
      Deploys are triggered by a signed GitHub webhook &mdash; see
      <a href="/webhook">/webhook</a>.
    </p>
  </div>
</main>
"""

INDEX_SCRIPTS = """
<script>
// Everything on this page comes from /api/public/status, which is deliberately
// aggregate-only: no server names, IDs, members or request logs.
var $ = function (id) { return document.getElementById(id); };

function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }

function humanUptime(seconds) {
  if (seconds == null) return '\\u2014';
  var s = Math.floor(seconds);
  var d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  if (d) return d + 'd ' + h + 'h';
  if (h) return h + 'h ' + m + 'm';
  if (m) return m + 'm';
  return s + 's';
}

function setState(ok, text) {
  $('s-state').innerHTML = '<span class="status-dot ' + (ok ? 'online' : 'offline') + '"></span>';
  $('s-state').insertAdjacentText('beforeend', text);
}

function render(data) {
  setState(true, 'Online');
  $('s-uptime').textContent = humanUptime(data.uptime_seconds);

  var g = data.gateway || {};
  $('s-gateway').innerHTML = g.connected
    ? '<span class="status-dot online"></span>' + (g.latency_ms != null ? g.latency_ms + ' ms' : 'linked')
    : '<span class="status-dot offline"></span>offline';

  var t = data.totals || {};
  $('s-servers').textContent = t.servers != null ? t.servers : '\\u2014';
  $('s-commands').textContent = t.custom_commands != null ? t.custom_commands : '\\u2014';

  var v = data.version || {};
  $('s-commit').textContent = v.commit || 'unknown';

  var d = data.last_deploy;
  if (d && d.timestamp) {
    var when = new Date(d.timestamp);
    $('s-deploy').textContent = (isNaN(when) ? d.timestamp : when.toLocaleString()) +
      (d.status && d.status !== 'deployed' ? ' (' + d.status + ')' : '');
  } else {
    $('s-deploy').textContent = 'no deploy recorded';
  }

  $('refreshed').textContent = 'Updated ' + new Date().toLocaleTimeString();
}

function load() {
  fetch('/api/public/status', { headers: { 'Accept': 'application/json' } })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(render)
    .catch(function () {
      setState(false, 'Unreachable');
      $('refreshed').textContent = 'Could not load live status.';
    });
}

load();
setInterval(load, 20000);

// Health check button: shows the round trip of a real request.
$('ping-btn').addEventListener('click', function () {
  var out = $('ping-result');
  out.textContent = 'Checking\\u2026';
  var t0 = performance.now();
  fetch('/health', { headers: { 'Accept': 'application/json' } })
    .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
    .then(function (res) {
      var ms = Math.round(performance.now() - t0);
      out.textContent = res.ok ? 'healthy \\u00b7 ' + ms + ' ms' : 'unhealthy (' + res.j.status + ')';
    })
    .catch(function () { out.textContent = 'health check failed'; });
});

// Copy an endpoint URL. Listens on the container so the markup stays free of
// inline handlers.
document.addEventListener('click', function (e) {
  var btn = e.target.closest('.copy-btn');
  if (!btn) return;
  var done = function () {
    var prev = btn.getAttribute('aria-label');
    btn.setAttribute('aria-label', 'Copied');
    btn.style.color = 'var(--success-fg)';
    setTimeout(function () { btn.setAttribute('aria-label', prev); btn.style.color = ''; }, 1200);
  };
  if (navigator.clipboard) navigator.clipboard.writeText(btn.dataset.copy).then(done, function () {});
});
</script>
"""

INDEX_HTML = _public_page('OLIT Bot API &mdash; Status', INDEX_BODY, INDEX_SCRIPTS)


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

    print("✅ Loaded data for guilds and automod configurations.")


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
    """Write a single file to the repo through the GitHub Contents API.

    This talks to the remote directly and never touches the local checkout, so
    it cannot publish unrelated local commits the way `git push` would.

    `content` may be a dict (serialised as JSON), str or bytes. Returns a
    (ok, detail) pair; callers that do not care may ignore it. Never raises.
    """
    if not GITHUB_TOKEN:
        return False, 'GITHUB_TOKEN is not set'
    try:
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)
        if isinstance(content, str):
            content = content.encode('utf-8')

        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}'
        headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'User-Agent': 'OLIT-Bot-API'}

        # The API needs the current blob SHA to replace an existing file.
        sha = None
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            sha = r.json().get('sha')

        payload = {
            'message': message,
            'content': base64.b64encode(content).decode(),
            'branch': GITHUB_BRANCH,
        }
        if sha:
            payload['sha'] = sha

        put = requests.put(url, headers=headers, json=payload, timeout=30)
        if put.status_code in (200, 201):
            return True, f'{file_path} committed'

        detail = ''
        try:
            detail = put.json().get('message', '')
        except Exception:
            detail = put.text[:120]
        print(f"⚠️  GitHub sync failed for {file_path}: {put.status_code} {detail}")
        return False, f'HTTP {put.status_code}: {detail}'
    except Exception as e:
        print(f"⚠️  GitHub sync error: {e}")
        return False, str(e)


# ── Auto-Deploy & Webhook Security Helper ─────────────────────────────────────
def verify_signature(payload_body, secret, signature_header):
    """Verifies that the webhook payload was sent by GitHub."""
    if not secret or not signature_header:
        return True  # Skip check if secret isn't configured

    hash_object = hmac.new(secret.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


# config/ is tracked in git but rewritten while the bot runs: the dashboard
# commits it through the GitHub Contents API, so the remote is the source of
# truth for it. That left the host's checkout permanently modified, and a plain
# `git pull` refuses to merge over local changes:
#
#     error: Your local changes to the following files would be overwritten by
#     merge: data/galaxy_data.json ... Aborting
#
# `data/` was tracked for the same reason and is not any more -- the galaxy
# saves are runtime state that belongs on the host, like persistent/ -- but
# config/ still is, so the problem stands. A deploy target has no local work
# worth keeping, so a deploy resets to the remote branch instead of merging
# into it. Stale .pyc files that an older commit of this repo used to track are
# cleared the same way.
RUNTIME_STATE_DIRS = ("config", "data")
PRE_DEPLOY_DIR = os.path.join("persistent", "pre_deploy")
LAST_DEPLOY_FILE = os.path.join("persistent", "last_deploy.json")
KEEP_PRE_DEPLOY_SNAPSHOTS = 5


def _run_git(*args, timeout=120):
    """Run one git command and return (ok, combined_output). Never raises."""
    try:
        proc = subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, 'git is not installed on this host'
    except subprocess.TimeoutExpired:
        return False, f"git {' '.join(args)} timed out after {timeout}s"
    except Exception as e:
        return False, str(e)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def git_revision():
    """Short commit, branch and commit date of the running checkout.

    Deliberately omits the commit subject and author: this feeds the public
    status page, which must not disclose anything about the repo's contents.
    """
    ok_sha, sha = _run_git("rev-parse", "--short", "HEAD", timeout=15)
    ok_date, when = _run_git("log", "-1", "--pretty=%cI", timeout=15)
    return {
        'commit': sha if ok_sha else None,
        'branch': GITHUB_BRANCH,
        'committed_at': when if ok_date else None,
    }


def _prune_pre_deploy_snapshots():
    """Keep only the newest few snapshots so the host's disk quota stays small."""
    try:
        snaps = sorted(
            d for d in os.listdir(PRE_DEPLOY_DIR)
            if os.path.isdir(os.path.join(PRE_DEPLOY_DIR, d))
        )
    except OSError:
        return
    for old in snaps[:-KEEP_PRE_DEPLOY_SNAPSHOTS]:
        shutil.rmtree(os.path.join(PRE_DEPLOY_DIR, old), ignore_errors=True)


def _snapshot_runtime_state():
    """Copy the runtime JSON aside before a deploy resets the checkout.

    The reset discards local edits to tracked files. config/ is mirrored to
    GitHub as it changes, so the remote copy is normally identical or newer --
    but a write made after the last mirror would be lost. data/ is untracked
    and nothing mirrors it at all, so a copy here is its only safety net if a
    deploy ever does touch it.

    _restore_runtime_state() puts back anything the reset removed.

    Returns (snapshot_dir, files_copied); snapshot_dir is None on failure.
    """
    target = os.path.join(PRE_DEPLOY_DIR, datetime.now().strftime('%Y%m%d-%H%M%S'))
    copied = 0
    try:
        for name in RUNTIME_STATE_DIRS:
            if not os.path.isdir(name):
                continue
            dest = os.path.join(target, name)
            os.makedirs(dest, exist_ok=True)
            for entry in sorted(os.listdir(name)):
                src = os.path.join(name, entry)
                if entry.endswith('.json') and os.path.isfile(src):
                    shutil.copy2(src, os.path.join(dest, entry))
                    copied += 1
        _prune_pre_deploy_snapshots()
    except OSError as e:
        print(f"⚠️  Could not snapshot runtime state before deploy: {e}")
        return None, copied
    return target, copied


def _restore_runtime_state(snapshot):
    """Put back runtime files that the reset removed from the worktree.

    Resetting onto a commit that no longer tracks a path deletes that path from
    the worktree. `data/` was tracked once, so the first deploy after it was
    untracked would have wiped the host's live galaxy saves -- the files are
    meant to live on the host like `persistent/` does, untracked and
    untouched.

    Only paths git now ignores are restored, so a tracked config file that was
    deliberately deleted upstream stays deleted. Files that survived the reset
    are never overwritten.
    """
    if not snapshot or not os.path.isdir(snapshot):
        return

    restored = 0
    for root, _dirs, files in os.walk(snapshot):
        for name in files:
            saved = os.path.join(root, name)
            # Path relative to the snapshot is the path in the checkout.
            live = os.path.relpath(saved, snapshot)
            if os.path.exists(live):
                continue
            # `git check-ignore` exits 0 only for an ignored path.
            ignored, _out = _run_git("check-ignore", "-q", live, timeout=15)
            if not ignored:
                continue
            try:
                os.makedirs(os.path.dirname(live) or '.', exist_ok=True)
                shutil.copy2(saved, live)
                restored += 1
            except OSError as e:
                print(f"⚠️  Could not restore {live}: {e}")

    if restored:
        print(f"♻️  Restored {restored} untracked runtime file(s) the reset removed")


def _clean_pycache():
    """Delete __pycache__ trees left behind by the previous commit.

    An older commit tracked `__pycache__/*.pyc`, so resetting onto it can
    restore bytecode that shadows the new sources.
    """
    removed = 0
    for root, dirs, _files in os.walk('.'):
        if '.git' in dirs:
            dirs.remove('.git')
        for d in list(dirs):
            if d == '__pycache__':
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                dirs.remove(d)
                removed += 1
    if removed:
        print(f"🧹 Cleared {removed} __pycache__ folder(s)")


def _record_deploy(status, detail=None, commit=None):
    """Persist the outcome of a deploy attempt.

    Written before the process exits, because the restart is how a successful
    deploy ends -- nothing in memory survives to report it.
    """
    try:
        os.makedirs(os.path.dirname(LAST_DEPLOY_FILE), exist_ok=True)
        with open(LAST_DEPLOY_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'status': status,
                'detail': detail,
                'commit': commit,
                'branch': GITHUB_BRANCH,
                'timestamp': datetime.now().isoformat(),
            }, f, indent=2)
    except OSError as e:
        print(f"⚠️  Could not record deploy state: {e}")


def load_last_deploy():
    """Read the last recorded deploy outcome, or None if there is none."""
    try:
        with open(LAST_DEPLOY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def deploy_and_restart():
    """Reset the checkout to the remote branch, then exit so the host restarts us.

    Resets rather than merges -- see RUNTIME_STATE_DIRS above. Never raises:
    this runs on a background thread after the webhook has already replied 200,
    so a traceback here would be invisible. Every failure is printed to the
    console and recorded for the status page instead.
    """
    print("🔄 Webhook deploy: resetting checkout to the remote branch...")

    ok, _ = _run_git("rev-parse", "--is-inside-work-tree", timeout=15)
    if not ok:
        _record_deploy('failed', 'not a git checkout')
        print("❌ Auto-deploy aborted: this directory is not a git checkout")
        return

    snapshot, copied = _snapshot_runtime_state()
    if snapshot and copied:
        print(f"📦 Copied {copied} runtime file(s) to {snapshot}")

    ok, out = _run_git("fetch", "--prune", "origin", GITHUB_BRANCH, timeout=180)
    if not ok:
        _record_deploy('failed', f'git fetch failed: {out[:300]}')
        print(f"❌ Auto-deploy aborted: git fetch failed\n{out}")
        return

    ok, out = _run_git("reset", "--hard", f"origin/{GITHUB_BRANCH}", timeout=120)
    if not ok:
        _record_deploy('failed', f'git reset failed: {out[:300]}')
        print(f"❌ Auto-deploy aborted: git reset failed\n{out}")
        return
    print(f"✅ {out}")

    _restore_runtime_state(snapshot)
    _clean_pycache()

    if os.path.exists("requirements.txt"):
        # Non-fatal: a dependency that fails to build must not strand the bot on
        # the old code, and most hosts reinstall requirements on boot anyway.
        try:
            pip = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                capture_output=True, text=True, timeout=600)
            if pip.returncode != 0:
                print(f"⚠️  pip install reported an error:\n{pip.stderr[-800:]}")
        except Exception as e:
            print(f"⚠️  pip install failed: {e}")

    _record_deploy('deployed', f'reset to origin/{GITHUB_BRANCH}', git_revision().get('commit'))
    print("✅ Deploy complete. Exiting so the host restarts the bot...")
    os._exit(0)


# ── Request logging ───────────────────────────────────────────────────────────
def log_req(endpoint, method, data):
    """Record one API call.

    `guild_id` is stored separately so /api/logs can scope the log to the
    server whose admin is asking; `data` and `ip` stay in the entry but are
    only ever served to the operator key.
    """
    guild_id = None
    if isinstance(data, dict) and data.get('guild_id') not in (None, ''):
        guild_id = str(data['guild_id'])

    api_logs.append({
        'timestamp': datetime.now().isoformat(),
        'endpoint': endpoint,
        'method': method,
        'guild_id': guild_id,
        'data': str(data)[:300],
        'ip': request.remote_addr
    })
    if len(api_logs) % 10 == 0:
        save_api_logs()


# ── Authorization ─────────────────────────────────────────────────────────────
# Authorization happens here, on the backend, because the dashboard is a static
# site: everything it ships is public. The old scheme had the dashboard send a
# shared X-API-Key, which meant the key was readable in
# olittechnologies.co.in/assets/js/api.js and granted whoever found it full
# access to every server's configuration. Several guild GET routes carried no
# check at all.
#
# Now a dashboard request proves who the caller is with their own Discord
# token, and this module asks Discord which servers that person actually
# administers before answering. The API key remains only as an operator
# credential for server-to-server calls; it is never sent to a browser.

DISCORD_API = 'https://discord.com/api/v10'
MANAGE_GUILD = 0x20          # Discord's "Manage Server" permission bit
GUILD_ACCESS_TTL = 300       # seconds a verified token's guild list is reused

# token hash -> (expires_at_monotonic, frozenset of managed guild ids)
_guild_access_cache = {}
_guild_access_lock = Lock()


def _bearer_token():
    """The Discord access token from the Authorization header, if present."""
    header = request.headers.get('Authorization', '')
    if header[:7].lower() == 'bearer ':
        return header[7:].strip() or None
    return None


def _has_admin_key():
    """True when the request carries the operator API key.

    Constant-time compare so a wrong key cannot be recovered by timing.
    """
    key = request.headers.get('X-API-Key')
    if not key or not API_KEY:
        return False
    return hmac.compare_digest(key, API_KEY)


def _prune_access_cache(now):
    """Drop expired entries. Called with the lock held."""
    for key in [k for k, (expires, _ids) in _guild_access_cache.items() if expires <= now]:
        _guild_access_cache.pop(key, None)


def discord_managed_guilds(token):
    """Guild IDs the bearer of `token` owns or has Manage Server on.

    Asks Discord, because the browser's own list cannot be trusted. The result
    is cached for GUILD_ACCESS_TTL against a hash of the token -- the token
    itself is never stored -- so a dashboard session costs one Discord call
    every few minutes rather than one per click.

    Returns (ok, value): a frozenset of string IDs, or a readable error.
    """
    cache_key = hashlib.sha256(token.encode('utf-8')).hexdigest()
    now = time.monotonic()

    with _guild_access_lock:
        hit = _guild_access_cache.get(cache_key)
        if hit and hit[0] > now:
            return True, hit[1]

    try:
        r = requests.get(
            f'{DISCORD_API}/users/@me/guilds',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10,
        )
    except requests.RequestException as e:
        print(f"⚠️  Discord token check failed: {e}")
        return False, 'Could not reach Discord to verify your login'

    if r.status_code == 401:
        return False, 'Your Discord login has expired -- sign in again'
    if r.status_code == 429:
        return False, 'Discord is rate limiting this login, try again shortly'
    if r.status_code != 200:
        return False, f'Discord returned HTTP {r.status_code}'

    try:
        guilds = r.json()
    except ValueError:
        return False, 'Discord returned an unreadable response'
    if not isinstance(guilds, list):
        return False, 'Discord returned an unexpected response'

    managed = set()
    for guild in guilds:
        if not isinstance(guild, dict):
            continue
        try:
            # Discord sends the permission bitfield as a decimal string.
            perms = int(guild.get('permissions') or 0)
        except (TypeError, ValueError):
            perms = 0
        if guild.get('owner') or (perms & MANAGE_GUILD):
            managed.add(str(guild.get('id')))
    managed = frozenset(managed)

    with _guild_access_lock:
        _guild_access_cache[cache_key] = (now + GUILD_ACCESS_TTL, managed)
        _prune_access_cache(now)

    return True, managed


def _authorize():
    """Resolve the caller's authority.

    Returns (ok, managed) where `managed` is None for an operator key (meaning
    every guild) or a frozenset of guild IDs for a Discord login. On failure
    `managed` is an (error_message, status_code) pair.
    """
    if _has_admin_key():
        return True, None

    token = _bearer_token()
    if not token:
        return False, ('Sign in with Discord to manage this server', 401)

    ok, result = discord_managed_guilds(token)
    if not ok:
        return False, (result, 401)
    return True, result


def _requested_guild_id(kwargs):
    """The guild the request is about.

    Looks in the URL rule, then the posted body (JSON or form), then the query
    string -- `/api/logs?guild_id=...` is a GET with no body.
    """
    if kwargs.get('guild_id') is not None:
        return str(kwargs['guild_id'])
    for source in (request.get_json(silent=True), request.form, request.args):
        if not source:
            continue
        guild_id = source.get('guild_id')
        if guild_id not in (None, ''):
            return str(guild_id)
    return None


def require_discord_login(f):
    """Require a verified Discord login (or the operator key), with no guild check.

    The view reads `flask_g.managed_guilds`: a frozenset of guild IDs, or None
    when the caller used the operator key.

    CORS preflights are never seen here: the routes declare explicit methods,
    so Flask answers OPTIONS from the routing layer without invoking the view.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        ok, result = _authorize()
        if not ok:
            message, status = result
            return jsonify({'success': False, 'error': message}), status
        flask_g.managed_guilds = result
        return f(*args, **kwargs)

    return wrapper


def require_guild_access(f):
    """Require that the caller administers the guild this request names.

    The guild comes from the URL (`<guild_id>`) or the posted `guild_id`.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        ok, result = _authorize()
        if not ok:
            message, status = result
            return jsonify({'success': False, 'error': message}), status

        guild_id = _requested_guild_id(kwargs)
        if guild_id is None:
            return jsonify({'success': False, 'error': 'guild_id is required'}), 400

        if result is not None and guild_id not in result:
            # The same answer whether that server does not exist, is not one the
            # bot is in, or simply is not theirs -- so the API cannot be used to
            # discover servers.
            return jsonify({
                'success': False,
                'error': 'You do not have Manage Server permission there',
            }), 403

        flask_g.managed_guilds = result
        flask_g.guild_id = guild_id
        return f(*args, **kwargs)

    return wrapper


def require_admin_key(f):
    """Require the operator API key. For server-to-server calls only.

    Not usable from the dashboard: the key must never be shipped to a browser.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _has_admin_key():
            return jsonify({'success': False, 'error': 'Operator credentials required'}), 401
        return f(*args, **kwargs)

    return wrapper


def _wants_html():
    """True when the caller is a browser rather than an API client.

    Checked against the Accept header, so `curl` and the dashboard keep getting
    JSON from the same routes that render a page for a visitor.
    """
    accept = request.headers.get('Accept', '')
    return 'text/html' in accept and 'application/json' not in accept


def _page_context():
    """Template variables shared by every public page."""
    return {
        'domain': CUSTOM_DOMAIN,
        'site': SITE_ORIGIN,
        'version': SERVICE_VERSION,
        'branch': GITHUB_BRANCH,
        'github': bool(GITHUB_TOKEN),
        'year': datetime.now().year,
    }


# ── Root / Health ─────────────────────────────────────────────────────────────
@app.route('/')
def home():
    if not _wants_html():
        return jsonify({
            'status': 'running',
            'service': 'OLIT Discord Bot API',
            'domain': CUSTOM_DOMAIN,
            'version': SERVICE_VERSION,
        })
    return render_template_string(
        INDEX_HTML,
        endpoints=ENDPOINT_CATALOG,
        endpoint_count=sum(len(items) for _name, items in ENDPOINT_CATALOG),
        auth_labels=AUTH_LABELS,
        **_page_context(),
    )


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/api/public/status')
def public_status():
    """Aggregate service status, with no authentication.

    This is what the status page and the website's bot landing page read, so it
    is restricted to figures that are safe for anyone to see: uptime, the
    running commit, whether the gateway is up, and totals. It must never grow a
    field that names a guild, a user or a channel, exposes request logs, or
    reports whether a particular server is configured -- those belong behind
    require_guild_access().
    """
    gateway = {'connected': False, 'latency_ms': None}
    if bot_instance is not None:
        loop = getattr(bot_instance, 'loop', None)
        gateway['connected'] = bool(loop is not None and loop.is_running()
                                    and not bot_instance.is_closed())
        latency = getattr(bot_instance, 'latency', None)
        # discord.py reports infinity before the first heartbeat lands.
        if isinstance(latency, float) and latency == latency and latency != float('inf'):
            gateway['latency_ms'] = round(latency * 1000)

    return jsonify({
        'success': True,
        'status': 'running',
        'service': 'OLIT Discord Bot API',
        'uptime_seconds': round((datetime.now() - SERVICE_STARTED_AT).total_seconds()),
        'started_at': SERVICE_STARTED_AT.isoformat(),
        'version': dict(git_revision(), service=SERVICE_VERSION),
        'gateway': gateway,
        'totals': {
            # Counts only. `servers` is how many servers have any configuration
            # stored, not which ones.
            'servers': len(set(
                list(guild_commands.keys())
                + list(automod_config.keys())
                + list(allowed_users.keys())
                + [str(k) for k in welcome_channels.keys()]
            )),
            'custom_commands': sum(len(v) for v in guild_commands.values()),
            'filtered_words': sum(len(v) for v in automod_config.values()),
        },
        'features': {
            'github_sync': bool(GITHUB_TOKEN),
            'webhook_signature': bool(GITHUB_SECRET),
        },
        'last_deploy': load_last_deploy(),
        'timestamp': datetime.now().isoformat(),
    })


@app.errorhandler(404)
def not_found_error(error):
    if _wants_html():
        return render_template_string(
            NOT_FOUND_HTML, path=request.path, **_page_context()), 404
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'status': 404,
        'timestamp': datetime.now().isoformat()
    }), 404


WEBHOOK_BODY = """
<main class="container">
  <div class="page-head">
    <p class="section-label"><span>02</span>Deploy listener</p>
    <h1>GitHub webhook</h1>
    <p>This endpoint listens for push events on <code>{{ branch }}</code>. A browser GET only
       renders this page &mdash; deployments are triggered by a signed POST from GitHub.</p>
  </div>

  <div class="section">
    <h2>Configuration</h2>
    <p class="sub">How this instance handles an incoming push.</p>
    <dl class="kv">
      <div><dt>Target branch</dt><dd>{{ branch }}</dd></div>
      <div>
        <dt>Signature verification</dt>
        <dd>
          {% if signed %}<span class="badge badge-success">HMAC SHA-256 enforced</span>
          {% else %}<span class="badge badge-warn">not configured</span>{% endif %}
        </dd>
      </div>
      <div><dt>Strategy</dt><dd>fetch + reset --hard origin/{{ branch }}</dd></div>
      <div><dt>Restart</dt><dd>process exits; the host restarts it</dd></div>
    </dl>
    {% if not signed %}
    <p class="note" style="margin-top:18px">
      Set <code>GITHUB_WEBHOOK_SECRET</code> to the secret configured on the GitHub hook.
      Until then any caller that reaches this URL can trigger a deployment.
    </p>
    {% endif %}
  </div>

  <div class="section">
    <h2>Last deploy</h2>
    <p class="sub">Recorded on disk, so it survives the restart a deploy ends with.</p>
    {% if deploy %}
    <dl class="kv">
      <div>
        <dt>Outcome</dt>
        <dd>
          {% if deploy.status == 'deployed' %}<span class="badge badge-success">deployed</span>
          {% else %}<span class="badge badge-danger">{{ deploy.status }}</span>{% endif %}
        </dd>
      </div>
      <div><dt>When</dt><dd>{{ deploy.timestamp }}</dd></div>
      {% if deploy.commit %}<div><dt>Commit</dt><dd>{{ deploy.commit }}</dd></div>{% endif %}
      {% if deploy.status != 'deployed' and deploy.detail %}
      <div><dt>Detail</dt><dd>{{ deploy.detail }}</dd></div>
      {% endif %}
    </dl>
    {% else %}
    <p class="hint">No deploy has been recorded on this host yet.</p>
    {% endif %}
  </div>

  <div class="section">
    <h2>Why it resets instead of pulling</h2>
    <p class="sub">The failure this replaced.</p>
    <p style="color:var(--text-2);font-size:0.94rem;max-width:720px">
      The bot rewrites its own configuration and save files while it runs, and those files are
      tracked in git so they can be mirrored to GitHub. That left the host's checkout permanently
      modified, and <code>git pull</code> aborted every deploy with
      <em>&ldquo;your local changes would be overwritten by merge&rdquo;</em>. A deploy target has no
      local work worth keeping, so each deploy copies the runtime files aside and resets hard onto
      the remote branch.
    </p>
    <div class="actions" style="margin-top:22px">
      <a class="btn btn-secondary" href="/">Back to status</a>
    </div>
  </div>
</main>
"""

WEBHOOK_HTML = _public_page('GitHub webhook &mdash; OLIT Bot API', WEBHOOK_BODY)


NOT_FOUND_BODY = """
<main class="container">
  <div class="page-head">
    <p class="section-label"><span>404</span>Not found</p>
    <h1>No such endpoint.</h1>
    <p>The path <code>{{ path }}</code> is not served by this API.</p>
    <div class="actions" style="margin-top:26px">
      <a class="btn btn-primary" href="/">See the endpoint list</a>
      <a class="btn btn-secondary" href="{{ site }}/bot/">About the bot</a>
    </div>
  </div>
</main>
"""

NOT_FOUND_HTML = _public_page('Not found &mdash; OLIT Bot API', NOT_FOUND_BODY)

# ── Webhook Auto-Deploy Endpoint ──────────────────────────────────────────────
@app.route('/webhook', methods=['GET', 'POST'])
def github_webhook():
    # If a user visits in a browser, serve the styled interface
    if request.method == 'GET':
        if _wants_html():
            return render_template_string(
                WEBHOOK_HTML,
                signed=bool(GITHUB_SECRET),
                deploy=load_last_deploy(),
                **_page_context(),
            )
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
@require_guild_access
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
@require_guild_access
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
@require_guild_access
def get_commands(guild_id):
    cmds = guild_commands.get(str(guild_id), {})
    return jsonify({'success': True, 'commands': cmds, 'count': len(cmds)})


# ── Automod ───────────────────────────────────────────────────────────────────
@app.route('/api/automod', methods=['POST'])
@require_guild_access
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
@require_guild_access
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
@require_guild_access
def get_automod_status(guild_id):
    return jsonify({'success': True, 'automod_enabled': automod_enabled.get(int(guild_id), False)})


@app.route('/api/automod/<guild_id>', methods=['GET'])
@require_guild_access
def get_automod_words_route(guild_id):
    # Named *_route so it does not collide with the bot-facing
    # get_automod_words() helper defined near the bottom of this file.
    words = automod_config.get(str(guild_id), [])
    return jsonify({'success': True, 'words': words, 'count': len(words)})


# ── Allowed users ─────────────────────────────────────────────────────────────
@app.route('/api/allowed_users', methods=['POST'])
@require_guild_access
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
@require_guild_access
def get_allowed_users(guild_id):
    users = allowed_users.get(str(guild_id), [])
    return jsonify({'success': True, 'users': users, 'count': len(users)})


# ── Welcome channel ───────────────────────────────────────────────────────────
@app.route('/api/guilds', methods=['GET'])
@require_discord_login
def get_guilds():
    """List the guilds the bot is in *that the caller administers*.

    Reads the bot's local guild cache, so it needs the gateway thread. The
    result is filtered against the caller's verified Manage Server list: this
    used to return every server the bot was in to anyone holding the shared
    key, which disclosed the whole customer list.
    """
    try:
        managed = getattr(flask_g, 'managed_guilds', frozenset())

        async def _fetch():
            return [
                {
                    'id': str(guild.id),
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon': str(guild.icon.url) if guild.icon else None,
                }
                for guild in bot_instance.guilds
                # `managed` is None for an operator key, meaning no filtering.
                if managed is None or str(guild.id) in managed
            ]

        ok, result = run_on_bot_loop(_fetch)
        if not ok:
            return jsonify({'success': False, 'error': result}), 503

        result.sort(key=lambda g: g['name'].lower())
        return jsonify({'success': True, 'guilds': result, 'count': len(result)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/channels/<guild_id>', methods=['GET'])
@require_guild_access
def get_channels(guild_id):
    """List the text channels of a guild, for the dashboard's channel picker.

    Needs the gateway, so it goes through run_on_bot_loop(). If the bot has not
    handed itself to this module via set_bot_instance(), this returns 503 --
    which is what made the dashboard's "set welcome channel" picker come up
    empty.
    """
    try:
        async def _fetch():
            # get_guild() reads the local cache; fetch_guild() falls back to the
            # REST API in case the cache is cold.
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
                # Types 0 and 5 are text and announcement channels; welcome
                # messages can only be sent to those.
                if c.type.value in (0, 5)
            ]

        ok, result = run_on_bot_loop(_fetch)
        if not ok:
            return jsonify({'success': False, 'error': result}), 503

        if result is None:
            return jsonify({'success': False, 'error': 'Bot is not in that server'}), 404

        result.sort(key=lambda c: (c.get('parent_id') or '', c.get('position', 0)))

        return jsonify({'success': True, 'channels': result, 'count': len(result)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/welcome_channel', methods=['POST'])
@require_guild_access
def set_welcome_channel():
    """Store the welcome channel for a guild, from the dashboard.

    Accepts a JSON body or a form post: the dashboard has sent both, and the
    old `request.json` access raised a 415 whenever the Content-Type header was
    not exactly application/json, which looked like "saving does nothing".
    """
    try:
        data = request.get_json(silent=True) or request.form or {}

        try:
            guild_id = int(data.get('guild_id', 0))
            channel_id = int(data.get('channel_id', 0))
        except (TypeError, ValueError):
            return jsonify({'success': False,
                            'error': 'guild_id and channel_id must be numeric IDs'}), 400

        if not guild_id:
            return jsonify({'success': False, 'error': 'guild_id is required'}), 400

        # The dashboard's "Remove" button posts channel_id "0" to clear the
        # setting, so 0 is a valid value meaning "delete", not a bad request.
        if channel_id == 0:
            welcome_channels.pop(guild_id, None)
            save_welcome_channels()
            commit_to_github('config/welcome_channels.json',
                             {str(k): str(v) for k, v in welcome_channels.items()},
                             f'👋 Welcome channel cleared for {guild_id}')
            log_req('/api/welcome_channel', 'POST', data)
            return jsonify({'success': True, 'message': 'Welcome channel cleared',
                            'channel_id': None})

        # Keys are ints in memory and stringified on save; see save_welcome_channels().
        welcome_channels[guild_id] = channel_id
        save_welcome_channels()
        commit_to_github('config/welcome_channels.json',
                         {str(k): str(v) for k, v in welcome_channels.items()},
                         f'👋 Welcome channel set for {guild_id}')
        log_req('/api/welcome_channel', 'POST', data)
        return jsonify({'success': True, 'message': 'Welcome channel set', 'channel_id': str(channel_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/welcome_channel/<guild_id>', methods=['GET'])
@require_guild_access
def get_welcome_channel(guild_id):
    ch = welcome_channels.get(int(guild_id))
    return jsonify({'success': True, 'channel_id': str(ch) if ch else None})


# ── Full guild config ─────────────────────────────────────────────────────────
@app.route('/api/config/<guild_id>', methods=['GET'])
@require_guild_access
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
@require_admin_key
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
@require_guild_access
def get_logs():
    """Recent API requests for one server.

    Scoped and redacted. This route used to return the whole global log to any
    caller, including the client IP and the first 300 characters of every
    request body -- one server's admin could read another's traffic. A Discord
    login now sees only entries tagged with their own guild, and only the
    timestamp, endpoint and method; the operator key still sees everything.
    """
    limit = min(request.args.get('limit', 50, type=int), 500)
    managed = getattr(flask_g, 'managed_guilds', frozenset())

    if managed is None:
        # Operator key: the full record, IP and body included.
        return jsonify({'success': True, 'logs': api_logs[-limit:], 'total': len(api_logs)})

    guild_id = getattr(flask_g, 'guild_id', None)
    scoped = [entry for entry in api_logs if entry.get('guild_id') == guild_id]
    return jsonify({
        'success': True,
        'logs': [
            {
                'timestamp': entry.get('timestamp'),
                'endpoint': entry.get('endpoint'),
                'method': entry.get('method'),
            }
            for entry in scoped[-limit:]
        ],
        'total': len(scoped),
    })


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