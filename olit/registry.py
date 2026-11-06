"""The command catalog that drives the help system.

This is the single source of truth for help text. The old help command had the
whole listing hardcoded inside embed literals, which drifted badly out of date
-- it advertised "35+ commands" and "15+ games" while the bot actually
registers more than eighty commands, and it omitted every galaxy, booster,
pixel-art and space-news command.

tests/test_help.py asserts that every command actually registered on the bot
appears here, so this file cannot silently fall behind again.

Each entry is a Cmd:
    name    primary invocation, without the "!" prefix
    desc    one-line description
    usage   argument signature shown to users, if any
    admin   True if it needs elevated permissions
    hidden  True for owner/debug commands, omitted from the public listing
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Cmd:
    """One documented bot command."""

    name: str
    desc: str
    usage: str = ""
    admin: bool = False
    hidden: bool = False
    aliases: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def signature(self) -> str:
        """How the command is typed in chat, e.g. "!timeout <member> <duration>"."""
        return f"!{self.name} {self.usage}".strip()


@dataclass(frozen=True)
class Category:
    """A help page: a titled group of commands."""

    key: str
    title: str
    emoji: str
    blurb: str
    commands: List[Cmd]

    def visible(self, include_hidden: bool = False) -> List[Cmd]:
        """The commands to render for this page."""
        return [c for c in self.commands if include_hidden or not c.hidden]


# ── Categories ────────────────────────────────────────────────────────────────

GAMES = Category(
    key="games", title="Games & Minigames", emoji="\U0001F3AE",
    blurb="Every game awards points that feed the server leaderboard.",
    commands=[
        Cmd("trivia", "Space trivia with an easy/medium/hard difficulty picker"),
        Cmd("mathquiz", "Solve a randomly generated arithmetic problem"),
        Cmd("unscramble", "Unscramble a space-themed word against the clock"),
        Cmd("guess", "Guess the secret number with hot/cold hints"),
        Cmd("rps", "Rock paper scissors against the bot"),
        Cmd("coinflip", "Call heads or tails"),
        Cmd("dice", "Roll a die and optionally bet on the result",
            usage="[guess] [sides]"),
        Cmd("catchbooster", "Catch Booster 16 with the Mechzilla arms",
            aliases=("booster", "mechzilla", "catch16")),
        Cmd("catchhelp", "Controls and flight physics for the booster game",
            aliases=("boosterhelp",)),
        Cmd("merrychristmas", "Start the 3-round Grinch reaction game"),
        Cmd("grinchboard", "All-time Grinch rankings, or one player's record",
            usage="[user]", aliases=("grinchstats",)),
        Cmd("christmashelp", "How the Christmas event works"),
    ],
)

SPACE = Category(
    key="space", title="Space & Mission Simulators", emoji="\U0001F680",
    blurb="Launch simulations, vehicle design and live spaceflight news.",
    commands=[
        Cmd("starship", "Interactive launch-success predictor"),
        Cmd("predict", "Run a full six-stage test campaign on a vehicle",
            usage="[ship name]"),
        Cmd("mission", "Command a mission: launch, refuel and research"),
        Cmd("rocketdesign", "Design a rocket and have it scored"),
        Cmd("spacenow", "Latest spaceflight news and launch updates"),
        Cmd("spacestatus", "Status of the space news feed"),
        Cmd("spacetoggle", "Turn the space news feed on or off", admin=True),
        Cmd("spacediag", "Diagnose the space news feed", admin=True),
        Cmd("spacedebug", "Verbose space feed debug output", hidden=True),
    ],
)

GALAXY = Category(
    key="galaxy", title="Galaxy Exploration RPG", emoji="\U0001F30C",
    blurb="A persistent exploration RPG: travel, scan, upgrade and fight.",
    commands=[
        Cmd("galaxy", "Open your galaxy map and travel between systems"),
        Cmd("gscan", "Scan the current system for resources and phenomena"),
        Cmd("gstats", "Your ship, rank, credits and resources"),
        Cmd("shipyard", "Buy and upgrade ship modules"),
        Cmd("story", "Follow the main story and puzzle chain"),
        Cmd("teleport", "Warp to specific coordinates (needs a warp core)",
            usage="<x> <y>"),
        Cmd("gleaderboard", "Top galaxy explorers"),
        Cmd("worldinfo", "Information about the generated galaxy"),
        Cmd("galaxyhelp", "Full galaxy command reference"),
        Cmd("galaxyadmin", "Galaxy admin tools", admin=True, hidden=True),
        Cmd("forcebackup", "Force a galaxy save backup", admin=True, hidden=True),
    ],
)

FUN = Category(
    key="fun", title="Fun & Reactions", emoji="\U0001F3AD",
    blurb="GIFs, catchphrases and custom emoji reactions.",
    commands=[
        Cmd("pixelart", "Turn an attached image into pixel art",
            aliases=("pixel", "pixelfy", "retroart")),
        Cmd("hello", "Say hello"),
        Cmd("catch", "Catchphrase"),
        Cmd("vent", "Catchphrase"),
        Cmd("behero", "Catchphrase"),
        Cmd("bigboom", "Big explosion GIF"),
        Cmd("mediumboom", "Medium explosion GIF"),
        Cmd("smallboom", "Small explosion GIF"),
        Cmd("hugeboom", "Huge explosion GIF"),
        Cmd("destructivecryo", "Cryo failure GIF"),
        Cmd("lightsaber", "Lightsaber GIF"),
        Cmd("lonely", "Lonely GIF"),
        Cmd("rafshocked", "Shocked reaction GIF"),
        Cmd("wish", "Wish GIF"),
        Cmd("dev", "Contact the bot developer"),
    ],
)

STATS = Category(
    key="stats", title="Scores & Leaderboards", emoji="\U0001F4CA",
    blurb="Track your points and see where you rank.",
    commands=[
        Cmd("stats", "Your full personal gaming report"),
        Cmd("leaderboard", "Server leaderboard, with leader role assignment"),
        Cmd("games", "Browse every game the bot offers"),
        Cmd("ping", "Bot latency"),
        Cmd("guildid", "Show this server's ID"),
        Cmd("rolemapping", "Map leader roles to servers", admin=True,
            usage="[action] [server_id] [role_id]"),
    ],
)

MODERATION = Category(
    key="moderation", title="Moderation", emoji="\U0001F6E1️",
    blurb="Each action requires the matching Discord permission.",
    commands=[
        Cmd("timeout", "Time a member out",
            usage="<member> <duration> [reason]", admin=True),
        Cmd("untimeout", "Remove a timeout", usage="<member> [reason]", admin=True),
        Cmd("warn", "Warn a member", usage="<member> [reason]", admin=True),
        Cmd("kick", "Kick a member", usage="<member> [reason]", admin=True),
        Cmd("ban", "Ban a member", usage="<member> [reason]", admin=True),
        Cmd("purge", "Bulk delete messages", usage="<amount> [member]", admin=True),
        Cmd("slowmode", "Set channel slowmode", usage="[seconds]", admin=True),
        Cmd("modhelp", "Moderation command reference"),
    ],
)

AUTOMOD = Category(
    key="automod", title="Auto-Moderation", emoji="\U0001F6AB",
    blurb="Word filters, per-guild toggles and exemptions.",
    commands=[
        Cmd("automod", "Manage automod for a server",
            usage="[action] [server_id]", admin=True),
        Cmd("enableautomod", "Turn automod on for this server", admin=True),
        Cmd("listfilters", "List active word filters", admin=True),
        Cmd("testfilter", "Check whether a word would be filtered",
            usage="<word>", admin=True),
    ],
)

WELCOME = Category(
    key="welcome", title="Welcome Messages", emoji="\U0001F44B",
    blurb="Greet new members automatically.",
    commands=[
        Cmd("setwelcome", "Set the welcome channel", usage="<channel>", admin=True),
        Cmd("welcomeinfo", "Show the current welcome configuration"),
        Cmd("testwelcome", "Preview the welcome message", admin=True),
    ],
)

ELECTIONS = Category(
    key="elections", title="Elections", emoji="\U0001F5F3️",
    blurb="Run timed votes with buttons and automatic role handover.",
    commands=[
        Cmd("elections", "Start a custom election",
            usage="<hours> <title> [logo_url] <candidates...>", admin=True),
        Cmd("BAAelections", "Start a BAA election",
            usage="[hours] <candidates...>", admin=True),
        Cmd("HSelections", "Start a Head Sheriff election",
            usage="[hours] <candidates...>", admin=True),
        Cmd("endelections", "End an election early",
            usage="<message_id>", admin=True),
        Cmd("listelections", "List running elections"),
        Cmd("winhistory", "A user's election win history", usage="[user]"),
        Cmd("clearwins", "Clear a user's win streak",
            usage="<user> <election_type>", admin=True),
        Cmd("electionhelp", "Full election command reference"),
    ],
)

ADMIN = Category(
    key="admin", title="Owner & API Tools", emoji="\U0001F451",
    blurb="Dashboard sync, GitHub integration and diagnostics.",
    commands=[
        Cmd("listcommands", "List this server's custom dashboard commands"),
        Cmd("reloadcommands", "Reload custom commands from the API", admin=True),
        Cmd("testcommand", "Test a custom command", usage="<name>", admin=True),
        Cmd("apistatus", "Dashboard API connection status", admin=True),
        Cmd("api_status", "Detailed API status", admin=True, hidden=True),
        Cmd("api_reload", "Force an API data reload", admin=True, hidden=True),
        Cmd("api_commands", "Dump API-provided commands", admin=True, hidden=True),
        Cmd("command_stats", "Command usage statistics", admin=True, hidden=True),
        Cmd("github_status", "GitHub sync status", admin=True, hidden=True),
        Cmd("github_sync", "Push config to GitHub", admin=True, hidden=True),
        Cmd("github_info", "GitHub repository info", admin=True, hidden=True),
        Cmd("restricted_command", "Allow-listed users only", hidden=True),
        Cmd("sync", "Resync slash commands", admin=True, hidden=True),
        Cmd("clearguild", "Clear guild slash commands", admin=True, hidden=True),
    ],
)

HELP_META = Category(
    key="help", title="Help & Info", emoji="❓",
    blurb="You are here.",
    commands=[
        Cmd("help", "This menu", usage="[category]", aliases=("olithelp",)),
        Cmd("about", "About the bot"),
        Cmd("commands", "Flat list of every command"),
    ],
)

# Order matters: this is the order the help pages appear in.
CATEGORIES: List[Category] = [
    GAMES, SPACE, GALAXY, FUN, STATS,
    MODERATION, AUTOMOD, WELCOME, ELECTIONS, ADMIN, HELP_META,
]

CATEGORIES_BY_KEY: Dict[str, Category] = {c.key: c for c in CATEGORIES}

# Alternative spellings users might type for "!help <something>".
ALIASES: Dict[str, str] = {
    "game": "games", "gaming": "games", "play": "games", "minigames": "games",
    "rocket": "space", "launch": "space", "missions": "space",
    "rpg": "galaxy", "explore": "galaxy", "exploration": "galaxy",
    "entertainment": "fun", "meme": "fun", "gifs": "fun", "reactions": "fun",
    "score": "stats", "scores": "stats", "leaderboards": "stats",
    "mod": "moderation", "mods": "moderation",
    "filter": "automod", "filters": "automod",
    "greeting": "welcome", "greetings": "welcome",
    "election": "elections", "vote": "elections", "voting": "elections",
    "owner": "admin", "api": "admin", "master": "admin",
    "administration": "admin", "utility": "admin", "util": "admin",
    "tools": "admin", "management": "admin",
}


def resolve_category(raw: Optional[str]) -> Optional[Category]:
    """Map user input to a Category, or None if it matches nothing.

    Accepts the canonical key or any alias, ignoring case and surrounding
    whitespace.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    key = ALIASES.get(key, key)
    return CATEGORIES_BY_KEY.get(key)


def all_commands(include_hidden: bool = False) -> List[Cmd]:
    """Every catalogued command, flattened across categories."""
    return [
        cmd
        for category in CATEGORIES
        for cmd in category.commands
        if include_hidden or not cmd.hidden
    ]


def catalogued_names(include_hidden: bool = True) -> set:
    """Every catalogued name and alias, used by the help coverage test."""
    names = set()
    for cmd in all_commands(include_hidden=include_hidden):
        names.add(cmd.name)
        names.update(cmd.aliases)
    return names


def command_count(include_hidden: bool = False) -> int:
    """Number of documented commands, computed rather than hardcoded."""
    return len(all_commands(include_hidden=include_hidden))
