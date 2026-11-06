"""Environment, gateway intents and the hardcoded IDs the bot relies on.

Importing this module reads `.env` exactly once. Nothing here touches the
network or Discord, so it is safe to import from tests.
"""

import os

import discord
from dotenv import load_dotenv

# Read `.env` into the process environment. Safe to call repeatedly.
load_dotenv()

# ── Credentials and target guild ──────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

# `discord.Object` stands in for a Guild when we only know its ID.
GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

# Prefix for all classic (non-slash) commands.
BOT_PREFIX = "!"

# ── People ────────────────────────────────────────────────────────────────────
# Bot owner. Bypasses automod and unlocks the owner-only commands.
MASTER_ID = 814791086114865233

# Same person; used by the `!dev` contact command.
DEV_USER_ID = 814791086114865233

# ── Guilds the slash commands are copied into on startup ──────────────────────
GUILD_IDS = [
    1210475350119813120,
    1411425019434766499,
    1397218218535424090,
    1341485158129205278,
]

GUILDS = [discord.Object(id=guild_id) for guild_id in GUILD_IDS]

# ── Auto-moderation ───────────────────────────────────────────────────────────
# Guilds where automod is always on, regardless of what the dashboard says.
AUTOMOD_ENABLED_GUILDS = {
    1210475350119813120: True,
    1397218218535424090: True,
    1411425019434766499: True,
    1341485158129205278: True,
}

# Users automod never acts on (staff, trusted bots, the owner).
AUTOMOD_EXEMPT_USERS = [
    814791086114865233,
    1085236492571529287,
    948973975353057341,
    1343933090191376446,
    1418946895816167475,
    1414168461172539454,
    827552324389175297,
    1187981682280775733,
]

# Slur variants that are filtered whenever automod is enabled. These are
# matched as substrings, both against the raw lowercased message and against a
# copy with separator characters stripped, so spaced-out spellings still hit.
BUILTIN_NWORD_VARIATIONS = [
    "nigger", "nigga", "n1gger", "n1gga", "nig ger", "nig ga",
    "n-word", "nword", "n word", "nigg3r", "nigg4", "n!gger",
    "!gga", "niqqer", "niqqa", "niggеr", "niggа",
]

# How long automod times a user out for.
AUTOMOD_TIMEOUT_HOURS = 24

# ── Custom emoji reaction triggers, per guild ─────────────────────────────────
# Maps guild ID -> which custom emoji to react with for each inline trigger
# word (`appbcbash`, `appbceq`, `appbaa`, `appsheriff`).
SERVER_EMOJIS = {
    1411425019434766499: {
        # `appbaa` -> BAA emoji
        "aa_emoji": 1412810109083717762,
        # `appbceq` -> BCEQ emoji
        "eq_emoji": 1412810095967994040,
        # `appsheriff` -> Sheriff emoji
        "sheriff_emoji": 1412810083955511326,
        # `appbcbash` reacts with all three of the above, in order.
        "bash_emojis": [
            1412810109083717762,
            1412810095967994040,
            1412810083955511326,
        ],
    },
}


def build_intents() -> discord.Intents:
    """Return the gateway intents the bot needs.

    `message_content` and `members` are privileged and must also be enabled in
    the Discord developer portal, or the bot silently receives empty message
    content and no member events.
    """
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.voice_states = True
    intents.members = True
    intents.emojis = True
    intents.guilds = True
    return intents
