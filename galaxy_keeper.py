import discord
from discord import ui
from discord.ext import commands, tasks
import json, os, random, asyncio, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

# ─── FILE PATHS ────────────────────────────────────────────────────
_DATA_DIR   = "data"
GALAXY_FILE = f"{_DATA_DIR}/galaxy_data.json"
WORLD_FILE  = f"{_DATA_DIR}/world_data.json"
SCORES_FILE = f"{_DATA_DIR}/galaxy_scores.json"

GITHUB_REPO_DIR = "."      # Change to absolute path if your repo root differs
GITHUB_BRANCH   = "main"   # or "master"

# ─── MODULE-LEVEL REFS (injected by setup_galaxy) ──────────────────
_bot:       commands.Bot | None = None
_add_score: Callable | None     = None
_MASTER_ID: int                 = 0


def setup_galaxy(bot: commands.Bot, add_score_fn: Callable, master_id: int):
    """
    Call once from on_ready in main.py:
        setup_galaxy(bot, add_score, MASTER_ID)
    """
    global _bot, _add_score, _MASTER_ID
    _bot       = bot
    _add_score = add_score_fn
    _MASTER_ID = master_id
    _load_all()
    _register_commands(bot)
    print(f"[GALAXY KEEPER] Ready — {len(_galaxy)} players · {len(_world)} sectors")


# ─── DATA LAYER ────────────────────────────────────────────────────

def _ensure_dir():
    Path(_DATA_DIR).mkdir(parents=True, exist_ok=True)

def _load_json(path: str) -> dict:
    _ensure_dir()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def _save_json(path: str, data: dict):
    _ensure_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=_serial)

def _serial(obj):
    if isinstance(obj, (set, frozenset)): return list(obj)
    if isinstance(obj, tuple):            return list(obj)
    raise TypeError(f"Not serialisable: {type(obj)}")

_galaxy: dict = {}
_world:  dict = {}

def _load_all():
    global _galaxy, _world
    raw = _load_json(GALAXY_FILE)
    for d in raw.values():
        if "discovered"   in d: d["discovered"]   = set(tuple(c) for c in d["discovered"])
        if "achievements" in d: d["achievements"]  = set(d["achievements"])
    _galaxy = raw
    _world  = _load_json(WORLD_FILE)

def _save_all():
    _save_json(GALAXY_FILE, _galaxy)
    _save_json(WORLD_FILE,  _world)

def _save_user(_uid: int):
    _save_json(GALAXY_FILE, _galaxy)


# ─── WORLD / BIOME GENERATION ─────────────────────────────────────

_BIOMES = [
    ("Void Expanse",     "Deep empty space riddled with dark matter.",         0x0a0a1a, "rare"),
    ("Nebula Nursery",   "Glowing clouds birthing new stars.",                 0x1a0a2e, "common"),
    ("Ancient Ruins",    "Shattered remnants of a precursor civilisation.",    0x2e1a0a, "uncommon"),
    ("Rift Zone",        "Space-time is thin here. Reality flickers.",         0x0a2e2e, "rare"),
    ("Trading Corridor", "Dense with merchant convoys and space stations.",    0x0a1a0a, "common"),
    ("Graveyard Sector", "Hundreds of derelict ships from a forgotten war.",   0x1a1a0a, "uncommon"),
    ("Crystal Expanse",  "Every asteroid glitters with raw crystal.",          0x0a1a2e, "rare"),
    ("Stellar Nursery",  "Young stars and protoplanetary discs everywhere.",   0x2e0a0a, "common"),
]

_STAR_TYPES = [
    ("Red Dwarf",     0.40, 1.0,  "🔴"),
    ("Yellow Star",   0.30, 1.2,  "🟡"),
    ("Blue Giant",    0.12, 1.8,  "🔵"),
    ("White Dwarf",   0.07, 0.8,  "⚪"),
    ("Binary System", 0.05, 2.0,  "✨"),
    ("Neutron Star",  0.03, 2.5,  "💫"),
    ("Pulsar",        0.02, 3.0,  "🌀"),
    ("Quasar",        0.008,5.0,  "🌟"),
    ("Black Hole",    0.002,8.0,  "🕳️"),
]

_PLANET_TYPES = [
    ("Rocky World",   0.30, 15,  "🌍"),
    ("Gas Giant",     0.22, 30,  "🪐"),
    ("Ocean World",   0.15, 75,  "🌊"),
    ("Desert World",  0.10, 35,  "🏜️"),
    ("Ice World",     0.08, 40,  "❄️"),
    ("Volcanic World",0.06, 50,  "🌋"),
    ("Crystal World", 0.04, 200, "💎"),
    ("Toxic World",   0.03, 25,  "☢️"),
    ("Rogue World",   0.01, 180, "🌑"),
    ("Hollow World",  0.005,500, "🟤"),
]

_PHENOMENA = {
    "common":    [("Asteroid Field",20), ("Comet Trail",25), ("Space Station",60),  ("Nebula Fragment",55)],
    "uncommon":  [("Crystal Formation",120),("Magnetic Storm",90),("Ion Stream",80),("Derelict Ship",150)],
    "rare":      [("Ancient Ruins",300), ("Alien Artifact",500),("Temporal Rift",400),("Energy Cascade",350)],
    "epic":      [("Black Hole",600),    ("Wormhole",750),    ("Supernova Remnant",550),("Dark Matter Cloud",700)],
    "legendary": [("Dyson Sphere",1500), ("Ancient Gateway",2000),("Cosmic String",1800),("Progenitor Core",2500)],
}

_HAZARDS = [
    "Solar Flares","Radiation Storm","Gravitational Shear",
    "Pirate Ambush","Unstable Wormhole","Void Tendrils",
    "Antimatter Leak","EMP Field","Space Kraken Spore",
]

def get_sector_biome(sx: int, sy: int) -> dict:
    key = f"{sx},{sy}"
    if key not in _world:
        random.seed(hash((sx, sy, "biome")) & 0xFFFFFFFF)
        b = random.choice(_BIOMES)
        _world[key] = {"name":b[0],"desc":b[1],"color":b[2],"rarity":b[3]}
        _save_json(WORLD_FILE, _world)
    return _world[key]

def generate_system(x: int, y: int) -> dict:
    for ps in _STORY_PUZZLES:
        if (x, y) == ps["coords"]:
            return _make_puzzle_system(x, y, ps)
    if (x, y) == _CORE_COORDS:
        return _make_core_system(x, y)

    random.seed(hash((x, y)) & 0xFFFFFFFF)

    # Star
    r = random.random(); c = 0
    star, star_mult, star_emoji = _STAR_TYPES[-1][0], _STAR_TYPES[-1][2], _STAR_TYPES[-1][3]
    for name, w, mult, emoji in _STAR_TYPES:
        c += w
        if r <= c:
            star, star_mult, star_emoji = name, mult, emoji
            break

    biome = get_sector_biome(x // 50, y // 50)

    n_planets = random.randint(1, 9)
    if "Giant" in star or "Binary" in star:
        n_planets += random.randint(0, 4)

    planets = []
    for i in range(n_planets):
        ptype, _, pts, emoji = random.choices(_PLANET_TYPES, weights=[p[1] for p in _PLANET_TYPES])[0]
        planets.append({
            "name": f"{ptype} {chr(65+i)}", "type": ptype, "emoji": emoji, "base_pts": pts,
            "size": random.choice(["Tiny","Small","Medium","Large","Massive","Colossal"]),
            "moons": random.randint(0, 7),
            "atmosphere": random.choice(["None","Thin","Dense","Toxic","Corrosive","Breathable"]),
            "temperature": random.randint(-273, 1500),
            "gravity": round(random.uniform(0.05, 4.0), 2),
            "resources": random.choice(["None","Minerals","Crystals","Energy","Rare Metals","Dark Matter"]),
        })

    phenomena = []
    rolls = {"common":0.5,"uncommon":0.25,"rare":0.10,"epic":0.04,"legendary":0.005}
    if biome["rarity"] == "rare":
        rolls = {k: min(1.0, v*2) for k, v in rolls.items()}
    for tier, chance in rolls.items():
        if random.random() < chance:
            name, pts = random.choice(_PHENOMENA[tier])
            phenomena.append({"name": name, "tier": tier, "pts": pts})

    hazard = random.choice(_HAZARDS) if random.random() < 0.18 else None
    danger_choices = ["Safe","Low Risk","Moderate","Dangerous","Extreme","Lethal"]
    danger_weights = [0.30, 0.25, 0.20, 0.12, 0.08, 0.05]

    return {
        "coords": (x,y), "star": star, "star_emoji": star_emoji, "star_mult": star_mult,
        "biome": biome["name"], "biome_desc": biome["desc"], "biome_color": biome["color"],
        "planets": planets, "phenomena": phenomena, "hazard": hazard,
        "asteroids": random.randint(0,5), "nebula": random.random() < 0.25,
        "danger": random.choices(danger_choices, weights=danger_weights)[0],
        "trade_val": random.randint(0,800) if random.random() < 0.2 else 0,
        "is_story": False,
    }

def _make_puzzle_system(x, y, ps):
    return {
        "coords":(x,y),"star":"Ancient Binary","star_emoji":"⭐⭐","star_mult":2.0,
        "biome":"Ancient Ruins","biome_desc":"This system hums with precursor energy.","biome_color":0x2e1a0a,
        "planets":[{"name":"Puzzle Keeper","type":"Ancient Ruins","emoji":"🏛️","base_pts":250,
                    "size":"Large","moons":0,"atmosphere":"Energy Field","temperature":-200,
                    "gravity":1.0,"resources":"Crystals"}],
        "phenomena":[{"name":"Ancient Computer Core","tier":"rare","pts":300},
                     {"name":"Cryptic Inscriptions","tier":"uncommon","pts":120}],
        "hazard":"Security Protocols","asteroids":0,"nebula":False,
        "danger":"Dangerous","trade_val":0,"is_story":True,
        "puzzle_type":ps["puzzle_type"],"hint_reward":ps["hint"],"puzzle_coords":ps["coords"],
    }

def _make_core_system(x, y):
    return {
        "coords":(x,y),"star":"Dying Supergiant","star_emoji":"💥","star_mult":5.0,
        "biome":"Rift Zone","biome_desc":"The air crackles with impossible energy.","biome_color":0x0a2e2e,
        "planets":[{"name":"Core Vault","type":"Fortress World","emoji":"🔒","base_pts":1000,
                    "size":"Colossal","moons":12,"atmosphere":"Energy Field","temperature":0,
                    "gravity":10.0,"resources":"Pure Energy"}],
        "phenomena":[{"name":"Power Core Signature","tier":"legendary","pts":2000},
                     {"name":"Void Sentinel Presence","tier":"epic","pts":800}],
        "hazard":"Guardian Defenses","asteroids":0,"nebula":True,
        "danger":"Lethal","trade_val":0,"is_story":True,"is_core":True,
    }

# ─── PULSE-3 ACTIVE STORYLINE ──────────────────────────────────────

_STORY_PUZZLES = [
    {"coords":(15,  25),"puzzle_type":"cipher",  "hint":"The Sentinel sleeps in the shadow of two dying suns — sector deep-negative."},
    {"coords":(-20, 30),"puzzle_type":"math",    "hint":"Where three suns dance, the Core pulses. Count the resonance."},
    {"coords":(35, -15),"puzzle_type":"sequence","hint":"Follow the void between worlds — antimatter trail leads southwest."},
    {"coords":(-25,-40),"puzzle_type":"logic",   "hint":"Coordinates locked: (-78, 42). The Void Sentinel awaits."},
]
_CORE_COORDS = (-78, 42)

_PULSE3_EVENTS = [
    {"title":"📡 Pulse-3 Signal Detected",
     "desc":"An automated distress signal of unknown origin pulses across the sector in threes.", "trigger":0},
    {"title":"👁️ Precursor Sighting",
     "desc":"Translucent alien vessels have been spotted watching explorer ships. Puzzle systems are now active.", "trigger":5},
    {"title":"⚠️ The Void Awakens",
     "desc":"Dark matter readings spike galaxy-wide. The Core Vault coordinates have leaked. The Sentinel stirs.", "trigger":15},
    {"title":"🔴 SENTINEL RAGE — Galaxy-Wide Alert",
     "desc":"The Void Sentinel has fully awakened. Only a commander with all four hints can challenge it at (-78, 42).", "trigger":30},
]

def _pulse3_event(ud: dict) -> dict:
    n  = ud.get("successful_explorations", 0)
    ev = _PULSE3_EVENTS[0]
    for e in _PULSE3_EVENTS:
        if n >= e["trigger"] or len(ud.get("story_state",{}).get("hints_collected",[])) > 0:
            ev = e
    return ev

# ─── USER DATA ─────────────────────────────────────────────────────

_SHIP_UPGRADES = {
    "fuel_tank":       {"cost":400,  "max":5, "desc":"Increases max fuel capacity by 20"},
    "fuel_efficiency": {"cost":500,  "max":5, "desc":"Reduces fuel cost per jump"},
    "scanner_boost":   {"cost":750,  "max":3, "desc":"Reveals rarer phenomena during scans"},
    "cargo_hold":      {"cost":1000, "max":4, "desc":"Increases resource storage"},
    "shield_matrix":   {"cost":1200, "max":3, "desc":"Reduces boss damage (-8 per level)"},
    "warp_core":       {"cost":2000, "max":2, "desc":"Unlocks long-range coordinate jumps"},
    "battle_systems":  {"cost":1500, "max":3, "desc":"Boosts attack damage (+15 per level)"},
}

_RANKS = [
    (0,"Cadet"),(10,"Ensign"),(25,"Lieutenant"),(50,"Commander"),
    (100,"Captain"),(200,"Commodore"),(500,"Admiral"),(999,"Grand Admiral"),
]

def _get_rank(n: int) -> str:
    r = "Cadet"
    for thresh, name in _RANKS:
        if n >= thresh: r = name
    return r

def _default_user(uid: int) -> dict:
    return {
        "uid": uid, "position": [0,0], "fuel": 100, "max_fuel": 100,
        "credits": 150, "discovered": set(), "rare_finds": [], "achievements": set(),
        "resources": {"crystals":0,"metals":0,"energy":0,"dark_matter":0},
        "upgrades": {k:0 for k in _SHIP_UPGRADES},
        "story_state": {"puzzles_solved":0,"hints_collected":[],"core_retrieved":False},
        "successful_explorations": 0, "danger_encounters": 0, "total_credits_earned": 150,
        "boss_hp": None, "boss_turns": 0,
    }

def _get_user(uid: int) -> dict:
    key = str(uid)
    if key not in _galaxy:
        _galaxy[key] = _default_user(uid)
        _save_user(uid)
    d = _galaxy[key]
    if isinstance(d.get("discovered"), list):
        d["discovered"]   = set(tuple(c) for c in d["discovered"])
    if isinstance(d.get("achievements"), list):
        d["achievements"] = set(d["achievements"])
    # Back-fill any missing keys from newer schema
    for k, v in _default_user(uid).items():
        if k not in d:
            d[k] = v
    return d

# ─── ACHIEVEMENTS ──────────────────────────────────────────────────

_ACHIEVEMENTS = [
    ("First Steps",         lambda ud: len(ud["discovered"]) >= 1),
    ("Scout",               lambda ud: len(ud["discovered"]) >= 10),
    ("Veteran Explorer",    lambda ud: len(ud["discovered"]) >= 50),
    ("Master Cartographer", lambda ud: len(ud["discovered"]) >= 100),
    ("Phenomenon Hunter",   lambda ud: len(ud["rare_finds"]) >= 5),
    ("Legendary Seeker",    lambda ud: len(ud["rare_finds"]) >= 20),
    ("Brave Heart",         lambda ud: ud["danger_encounters"] >= 10),
    ("Resource Baron",      lambda ud: sum(ud["resources"].values()) >= 200),
    ("Space Millionaire",   lambda ud: ud["total_credits_earned"] >= 10000),
    ("Puzzle Master",       lambda ud: ud["story_state"]["puzzles_solved"] >= 4),
    ("Void Slayer",         lambda ud: ud["story_state"]["core_retrieved"]),
    ("Ancient Wisdom",      lambda ud: len(ud["story_state"]["hints_collected"]) >= 4),
]

def _check_achievements(ud: dict) -> list:
    new = []
    for name, cond in _ACHIEVEMENTS:
        if name not in ud["achievements"]:
            try:
                if cond(ud):
                    ud["achievements"].add(name)
                    new.append(name)
            except Exception:
                pass
    return new

# ─── REWARD CALCULATION ────────────────────────────────────────────

def _calc_rewards(system: dict, ud: dict):
    pts = 0; credits = 0
    resources = {"crystals":0,"metals":0,"energy":0,"dark_matter":0}
    discoveries = []
    danger_mult = {"Safe":1.0,"Low Risk":1.1,"Moderate":1.3,"Dangerous":1.6,"Extreme":2.2,"Lethal":3.5}
    mult = danger_mult.get(system["danger"],1.0) * system.get("star_mult",1.0)
    tier_icons = {"common":"🔸","uncommon":"💠","rare":"💎","epic":"✨","legendary":"🌟"}

    for p in system["planets"]:
        p_pts = int(p["base_pts"] * mult)
        pts  += p_pts
        discoveries.append(f"{p['emoji']} {p['name']} (+{p_pts})")
        if p["resources"] == "Crystals":      resources["crystals"]    += random.randint(2,8)
        elif p["resources"] == "Rare Metals": resources["metals"]      += random.randint(3,12)
        elif p["resources"] == "Energy":      resources["energy"]      += random.randint(1,6)
        elif p["resources"] == "Dark Matter": resources["dark_matter"] += random.randint(1,3)

    for ph in system["phenomena"]:
        ph_pts = int(ph["pts"] * mult)
        pts   += ph_pts
        discoveries.append(f"{tier_icons[ph['tier']]} {ph['name']} (+{ph_pts})")
        if ph["tier"] in ("rare","epic","legendary"):
            ud["rare_finds"].append(ph["name"])

    if system.get("asteroids",0) > 0:
        belt_pts = system["asteroids"] * int(20*mult)
        pts += belt_pts
        resources["metals"] += system["asteroids"] * random.randint(3,8)
        discoveries.append(f"☄️ {system['asteroids']} Asteroid Fields (+{belt_pts})")

    if system.get("nebula"):
        neb_pts = int(100*mult)
        pts += neb_pts
        resources["energy"] += random.randint(3,8)
        discoveries.append(f"🌌 Nebula (+{neb_pts})")

    bonus = int(pts * 0.20)
    pts  += bonus
    discoveries.append(f"🏆 First Discovery Bonus (+{bonus})")
    credits = pts // 2
    return pts, credits, resources, discoveries

# ─── HP BAR ────────────────────────────────────────────────────────

def _hp_bar(cur: int, max_: int, length: int = 20) -> str:
    if max_ <= 0: return "░" * length
    filled = int((cur/max_)*length)
    bar = "█"*filled + "░"*(length-filled)
    pct = int((cur/max_)*100)
    dot = "🟩" if pct>60 else ("🟨" if pct>30 else "🟥")
    return f"{dot} `[{bar}]` {cur}/{max_} ({pct}%)"

# ─── BOSS DATA ─────────────────────────────────────────────────────

_SENTINEL = {
    "hp_max": 1000,
    "phases": [
        {
            "threshold": 1.0, "name": "Dormant Phase",
            "desc": "The Sentinel scans your vessel with cold, ancient intelligence.",
            "color": 0x440055,
            "art": "  ◈━━━━━━━━━━◈\n  ║  ◉     ◉  ║\n  ║  ╔═════╗  ║\n  ◈  ║  Ω  ║  ◈\n  ║  ╚═════╝  ║\n  ◈━━━━━━━━━━◈",
            "attacks": [
                ("Void Pulse",     60, "Antimatter tendrils lash out!"),
                ("Gravity Crush",  45, "Space warps around your hull!"),
                ("Sensor Scramble",20, "Your instruments go dark!"),
            ],
        },
        {
            "threshold": 0.65, "name": "Rage Phase — Shields Cracking",
            "desc": "Eyes blaze crimson. Ancient weapon systems come online.",
            "color": 0x880022,
            "art": "  ◈▓▓▓▓▓▓▓▓▓▓◈\n  ║  ◎     ◎  ║\n  ║  ╔═══════╗  ║\n  ◈  ║ ΩΩΩ╬ΩΩ ║  ◈\n  ║  ╚═══════╝  ║\n  ◈▓▓▓▓▓▓▓▓▓▓◈",
            "attacks": [
                ("Plasma Barrage",  90,  "A wall of superheated plasma!"),
                ("Void Rift",       75,  "Reality tears around you!"),
                ("Core Beam",      110,  "A focused beam from the Core!"),
                ("Shield Devour",   50,  "Your shields are being eaten!"),
            ],
        },
        {
            "threshold": 0.30, "name": "⚠️ FINAL FORM — Core Unleashed",
            "desc": "The Core Vault cracks open. Pure ancient power floods the Sentinel.",
            "color": 0xff0000,
            "art": "  ◈████████████◈\n  ║  ◉̶     ◉̶  ║\n  ║  ╔═════════╗ ║\n  ◈  ║ ΩΩ∞ΩΩΩ ║  ◈\n  ║  ╚═════════╝ ║\n  ◈████████████◈",
            "attacks": [
                ("Annihilation Wave",150, "TOTAL ANNIHILATION! Your hull buckles!"),
                ("Time Fracture",   100, "Time stutters — you age a decade!"),
                ("Reality Collapse",130, "Space itself attacks!"),
                ("Void Absorption",  80, "The Sentinel absorbs your attack!"),
                ("Omega Strike",    200, "THE SENTINEL UNLEASHES EVERYTHING!"),
            ],
        },
    ],
    "phase2_msg": "⚡ **PHASE 2 TRANSITION!** Ancient protocols activate — power tripled!",
    "phase3_msg": "💀 **FINAL FORM UNLOCKED!** The Core cracks open. Ancient energy floods in!",
    "low_hp_msg": "😤 At critical HP, the Sentinel begins consuming surrounding stars for energy!",
}

_PLAYER_ATTACKS = [
    {"name":"Plasma Cannon",   "dmg":(40,80),  "crit":0.15, "emoji":"🔫"},
    {"name":"Missile Barrage", "dmg":(60,110), "crit":0.10, "emoji":"🚀"},
    {"name":"Ion Beam",        "dmg":(50,90),  "crit":0.20, "emoji":"⚡"},
    {"name":"Void Lance",      "dmg":(80,150), "crit":0.08, "emoji":"🌑"},
    {"name":"Quantum Strike",  "dmg":(30,200), "crit":0.35, "emoji":"💥"},
]

def _boss_phase(hp: int) -> dict:
    ratio = hp / _SENTINEL["hp_max"]
    result = _SENTINEL["phases"][0]
    for ph in reversed(_SENTINEL["phases"]):
        if ratio <= ph["threshold"]:
            result = ph
    return result

# ─── EMBEDS ────────────────────────────────────────────────────────

def _map_embed(uid: int) -> discord.Embed:
    ud    = _get_user(uid)
    pos   = ud["position"]
    biome = get_sector_biome(pos[0]//50, pos[1]//50)
    rank  = _get_rank(ud["successful_explorations"])

    emb = discord.Embed(
        title=f"🌌 Galaxy Map — {biome['name']}",
        description=f"_{biome['desc']}_\n**{rank}** · Position `({pos[0]}, {pos[1]})`",
        color=biome["color"],
    )

    MAP_SIZE = 11; half = MAP_SIZE // 2
    rows = []
    for y in range(pos[1]+half, pos[1]-half-1, -1):
        row = ""
        for x in range(pos[0]-half, pos[0]+half+1):
            coord = (x, y)
            if coord == tuple(pos):
                row += "🚀"
            elif coord in ud["discovered"]:
                sys = generate_system(x, y)
                tiers = [p["tier"] for p in sys.get("phenomena",[])]
                if "legendary" in tiers:  row += "🌟"
                elif "epic" in tiers:     row += "🌀"
                elif sys.get("is_story"): row += "🏛️"
                else:                     row += "✅"
            else:
                row += ["⭐","✦","⋆","✧"][abs(hash((x,y)))%4]
            row += " "
        rows.append(row)

    emb.add_field(name="📍 Sector View", value=f"```\n{chr(10).join(rows)}\n```", inline=False)

    fuel_pct = ud["fuel"] / ud["max_fuel"]
    fuel_bar = "█"*int(fuel_pct*10) + "░"*(10-int(fuel_pct*10))
    emb.add_field(name="⛽ Fuel",    value=f"{ud['fuel']}/{ud['max_fuel']}\n`{fuel_bar}`", inline=True)
    emb.add_field(name="💰 Credits", value=f"{ud['credits']:,}", inline=True)
    emb.add_field(name="🗺️ Systems", value=f"{len(ud['discovered'])} explored", inline=True)

    res = ud["resources"]
    emb.add_field(name="📦 Cargo",
                  value=f"💎 {res['crystals']}  ⚙️ {res['metals']}  ⚡ {res['energy']}  🌑 {res['dark_matter']}",
                  inline=False)

    ev = _pulse3_event(ud)
    emb.add_field(name=ev["title"], value=ev["desc"], inline=False)
    emb.set_footer(text="Navigate with buttons • 🔭 Scan • 📊 Stats")
    return emb

def _scan_embed(system: dict, uid: int) -> discord.Embed:
    x, y = system["coords"]
    emb  = discord.Embed(
        title=f"{system['star_emoji']} Deep Scan — {system['star']}",
        description=f"**Biome:** {system['biome']} · `({x}, {y})`\n_{system.get('biome_desc','')}_",
        color=system.get("biome_color", 0x1a1a2e),
    )
    danger_dot = {"Safe":"🟢","Low Risk":"🟡","Moderate":"🟠","Dangerous":"🔴","Extreme":"🟣","Lethal":"⚫"}
    emb.add_field(name="⚠️ Threat", value=f"{danger_dot.get(system['danger'],'⚪')} **{system['danger']}**", inline=True)

    if system.get("planets"):
        pl = "\n".join(f"{p['emoji']} **{p['name']}** — {p['size']}, {p['resources']}"
                       for p in system["planets"][:5])
        if len(system["planets"]) > 5: pl += f"\n… and {len(system['planets'])-5} more"
        emb.add_field(name=f"🪐 Planets ({len(system['planets'])})", value=pl, inline=False)

    if system.get("phenomena"):
        ti  = {"common":"🔸","uncommon":"💠","rare":"💎","epic":"✨","legendary":"🌟"}
        ph  = "\n".join(f"{ti[p['tier']]} **{p['name']}** (+{p['pts']} pts)" for p in system["phenomena"])
        emb.add_field(name="🔭 Phenomena", value=ph, inline=False)

    if system.get("hazard"):
        emb.add_field(name="🚨 Hazard", value=f"⚠️ **{system['hazard']}**", inline=False)

    if system.get("is_story"):
        if system.get("is_core"):
            emb.add_field(name="💀 BOSS SYSTEM",
                          value="The Void Sentinel lurks here. Collect all 4 hints before engaging.", inline=False)
        else:
            emb.add_field(name="🧩 Puzzle System",
                          value=f"Type: **{system.get('puzzle_type','').upper()}**", inline=False)

    emb.set_footer(text="Use buttons: ⚡ Explore  🧩 Solve Puzzle  ⚔️ Fight Boss")
    return emb

def _stats_embed(uid: int, user) -> discord.Embed:
    ud  = _get_user(uid)
    emb = discord.Embed(
        title=f"🌌 Commander: {user.display_name}",
        description=f"**Rank:** {_get_rank(ud['successful_explorations'])}",
        color=0x9932cc,
    )
    emb.set_thumbnail(url=user.display_avatar.url)
    emb.add_field(name="📍 Position",  value=f"`({ud['position'][0]}, {ud['position'][1]})`", inline=True)
    emb.add_field(name="💰 Credits",   value=f"{ud['credits']:,}", inline=True)
    emb.add_field(name="⛽ Fuel",      value=f"{ud['fuel']}/{ud['max_fuel']}", inline=True)
    emb.add_field(name="🗺️ Explored", value=f"{len(ud['discovered'])} systems", inline=True)
    emb.add_field(name="✅ Missions",  value=str(ud["successful_explorations"]), inline=True)
    emb.add_field(name="⚠️ Hazards",  value=str(ud["danger_encounters"]), inline=True)
    res = ud["resources"]
    emb.add_field(name="📦 Cargo",
                  value=f"💎 {res['crystals']}  ⚙️ {res['metals']}  ⚡ {res['energy']}  🌑 {res['dark_matter']}",
                  inline=False)
    upg = [f"🔧 {k.replace('_',' ').title()}: Lv {v}" for k,v in ud["upgrades"].items() if v > 0]
    if upg: emb.add_field(name="⚡ Upgrades", value="\n".join(upg), inline=False)
    if ud.get("achievements"):
        emb.add_field(name="🏅 Achievements",
                      value="\n".join(f"⭐ {a}" for a in list(ud["achievements"])[:10]),
                      inline=False)
    ss = ud["story_state"]
    emb.add_field(name="📖 Story",
                  value=f"Puzzles: {ss['puzzles_solved']}/4 | Core: {'✅' if ss['core_retrieved'] else '❌'}",
                  inline=False)
    return emb

# ─── NAV VIEW ──────────────────────────────────────────────────────

class _NavView(ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=300)
        self.uid = uid

    async def _move(self, interaction: discord.Interaction, dx: int, dy: int):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ This isn't your ship!", ephemeral=True)
        ud   = _get_user(self.uid)
        eff  = ud["upgrades"]["fuel_efficiency"]
        cost = max(2, 8 - eff)
        if ud["fuel"] < cost:
            return await interaction.response.send_message(f"❌ Need {cost} fuel, have {ud['fuel']}.", ephemeral=True)
        ud["position"][0] += dx
        ud["position"][1] += dy
        ud["fuel"] -= cost
        _save_user(self.uid)
        if random.random() < 0.10:
            ev_emb = _travel_event(ud)
            _save_user(self.uid)
            await interaction.response.edit_message(embed=_map_embed(self.uid), view=self)
            await interaction.followup.send(embed=ev_emb, ephemeral=True)
        else:
            await interaction.response.edit_message(embed=_map_embed(self.uid), view=self)

    @ui.button(label="↖", style=discord.ButtonStyle.secondary, row=0)
    async def nw(self, i, b): await self._move(i, -1,  1)
    @ui.button(label="⬆", style=discord.ButtonStyle.primary,   row=0)
    async def nn(self, i, b): await self._move(i,  0,  1)
    @ui.button(label="↗", style=discord.ButtonStyle.secondary, row=0)
    async def ne(self, i, b): await self._move(i,  1,  1)

    @ui.button(label="🔭 Scan", style=discord.ButtonStyle.success, row=0)
    async def scan(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your ship!", ephemeral=True)
        ud  = _get_user(self.uid)
        pos = ud["position"]
        sys = generate_system(pos[0], pos[1])
        await interaction.response.send_message(
            embed=_scan_embed(sys, self.uid),
            view=_ExploreView(self.uid, sys),
            ephemeral=True,
        )

    @ui.button(label="⬅", style=discord.ButtonStyle.primary,   row=1)
    async def ww(self, i, b): await self._move(i, -1,  0)

    @ui.button(label="🏠 Base", style=discord.ButtonStyle.success, row=1)
    async def home(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your ship!", ephemeral=True)
        ud = _get_user(self.uid)
        ud["position"] = [0, 0]
        ud["fuel"]     = ud["max_fuel"]
        _save_user(self.uid)
        await interaction.response.edit_message(embed=_map_embed(self.uid), view=self)

    @ui.button(label="➡", style=discord.ButtonStyle.primary,   row=1)
    async def ee(self, i, b): await self._move(i,  1,  0)

    @ui.button(label="↙", style=discord.ButtonStyle.secondary, row=2)
    async def sw(self, i, b): await self._move(i, -1, -1)
    @ui.button(label="⬇", style=discord.ButtonStyle.primary,   row=2)
    async def ss(self, i, b): await self._move(i,  0, -1)
    @ui.button(label="↘", style=discord.ButtonStyle.secondary, row=2)
    async def se(self, i, b): await self._move(i,  1, -1)

    @ui.button(label="⛽ Refuel", style=discord.ButtonStyle.danger, row=2)
    async def refuel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your ship!", ephemeral=True)
        ud     = _get_user(self.uid)
        needed = ud["max_fuel"] - ud["fuel"]
        cost   = needed * 2
        if ud["credits"] < cost:
            return await interaction.response.send_message(f"❌ Need {cost} credits, have {ud['credits']}.", ephemeral=True)
        ud["credits"] -= cost
        ud["fuel"]     = ud["max_fuel"]
        _save_user(self.uid)
        await interaction.response.send_message(f"⛽ Refuelled! Cost: {cost} credits.", ephemeral=True, delete_after=5)
        await interaction.edit_original_response(embed=_map_embed(self.uid), view=self)

    @ui.button(label="📊 Stats", style=discord.ButtonStyle.success, row=2)
    async def stats(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your ship!", ephemeral=True)
        await interaction.response.send_message(
            embed=_stats_embed(self.uid, interaction.user), ephemeral=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

def _travel_event(ud: dict) -> discord.Embed:
    events = [
        ("☄️ Comet Strike!",  "metals",      random.randint(5, 15)),
        ("⚡ Energy Surge!",   "energy",      random.randint(3, 10)),
        ("💎 Crystal Drift!", "crystals",    random.randint(2, 8)),
        ("🌑 Dark Matter!",   "dark_matter", random.randint(1, 4)),
        ("💰 Salvage!",       "credits",     random.randint(10, 50)),
        ("🏴‍☠️ Pirates!",      "credits",     -random.randint(5, 25)),
        ("⛽ Fuel Leak!",     "fuel",        -random.randint(3, 8)),
    ]
    label, resource, amt = random.choice(events)
    emb = discord.Embed(title=f"🌌 Travel Event — {label}", color=0x9932cc)
    if resource == "credits":
        ud["credits"] = max(0, ud["credits"] + amt)
        emb.description = f"{'+' if amt>0 else ''}{amt} credits"
    elif resource == "fuel":
        ud["fuel"] = max(0, ud["fuel"] + amt)
        emb.description = f"{'+' if amt>0 else ''}{amt} fuel"
    else:
        ud["resources"][resource] = ud["resources"].get(resource, 0) + amt
        emb.description = f"+{amt} {resource.replace('_',' ').title()}"
    return emb

# ─── EXPLORE VIEW ─────────────────────────────────────────────────

class _ExploreView(ui.View):
    def __init__(self, uid: int, system: dict):
        super().__init__(timeout=180)
        self.uid    = uid
        self.system = system
        if not system.get("is_story"):
            self.remove_item(self.solve_puzzle)
            self.remove_item(self.fight_boss)
        elif system.get("is_core"):
            self.remove_item(self.solve_puzzle)
        else:
            self.remove_item(self.fight_boss)

    @ui.button(label="⚡ Explore System", style=discord.ButtonStyle.success, row=0)
    async def explore(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not yours!", ephemeral=True)
        ud    = _get_user(self.uid)
        coord = tuple(ud["position"])
        if coord in ud["discovered"]:
            return await interaction.response.send_message("⚠️ Already catalogued.", ephemeral=True)

        if self.system.get("hazard") and random.random() < 0.3:
            shield = ud["upgrades"]["shield_matrix"]
            if random.random() > (0.5 + shield*0.15):
                fuel_loss = random.randint(8, 20)
                ud["fuel"] = max(0, ud["fuel"] - fuel_loss)
                ud["danger_encounters"] += 1
                _save_user(self.uid)
                emb = discord.Embed(title="💥 Hazard!",
                                    description=f"**{self.system['hazard']}** — lost {fuel_loss} fuel. Aborted.",
                                    color=0xff0000)
                return await interaction.response.edit_message(embed=emb, view=None)

        pts, credits, resources, discoveries = _calc_rewards(self.system, ud)
        ud["discovered"].add(coord)
        ud["successful_explorations"] += 1
        ud["credits"] += credits
        ud["total_credits_earned"] += credits
        for k, v in resources.items():
            ud["resources"][k] = ud["resources"].get(k, 0) + v
        new_ach = _check_achievements(ud)
        _save_user(self.uid)
        if _add_score: _add_score(self.uid, pts)

        # Also update galaxy scores file directly
        gs = _load_json(SCORES_FILE)
        gs[str(self.uid)] = gs.get(str(self.uid), 0) + pts
        _save_json(SCORES_FILE, gs)

        emb = discord.Embed(
            title="🎉 Exploration Complete!",
            description=f"**{self.system['star']}** at `{coord}` catalogued",
            color=0x00ff41,
        )
        emb.add_field(name="📊 Results",
                      value=f"🏆 {pts:,} pts\n💰 {credits:,} credits\n🌍 {len(self.system['planets'])} worlds",
                      inline=True)
        res_txt = "\n".join(f"+{v} {k.replace('_',' ').title()}" for k,v in resources.items() if v>0) or "None"
        emb.add_field(name="📦 Resources", value=res_txt, inline=True)
        disc_txt = "\n".join(discoveries[:8])
        if len(discoveries) > 8: disc_txt += f"\n…+{len(discoveries)-8} more"
        emb.add_field(name="🔬 Discoveries", value=disc_txt, inline=False)
        if new_ach:
            emb.add_field(name="🏅 New Achievements",
                          value="\n".join(f"⭐ {a}" for a in new_ach), inline=False)
        emb.set_footer(text=f"Total: {len(ud['discovered'])} systems | Rank: {_get_rank(ud['successful_explorations'])}")
        await interaction.response.edit_message(embed=emb, view=None)

    @ui.button(label="🧩 Solve Puzzle", style=discord.ButtonStyle.primary, row=1)
    async def solve_puzzle(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not yours!", ephemeral=True)
        ud   = _get_user(self.uid)
        ss   = ud["story_state"]
        hint = self.system.get("hint_reward", "")
        if hint in ss["hints_collected"]:
            return await interaction.response.send_message("❌ Already solved.", ephemeral=True)
        ss["puzzles_solved"] += 1
        ss["hints_collected"].append(hint)
        if _add_score: _add_score(self.uid, 100)
        _save_user(self.uid)
        emb = discord.Embed(title="🧩 Puzzle Solved!",
                            description=f"**Hint acquired:**\n> _{hint}_", color=0x00ff88)
        emb.add_field(name="Progress", value=f"{len(ss['hints_collected'])}/4 hints", inline=True)
        emb.add_field(name="Reward",   value="+100 points", inline=True)
        if len(ss["hints_collected"]) >= 4:
            emb.add_field(name="🎯 FINAL MISSION UNLOCKED",
                          value="Navigate to `(-78, 42)` and fight the Void Sentinel!", inline=False)
        await interaction.response.edit_message(embed=emb, view=None)

    @ui.button(label="⚔️ Fight Boss", style=discord.ButtonStyle.danger, row=1)
    async def fight_boss(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not yours!", ephemeral=True)
        ud = _get_user(self.uid)
        ss = ud["story_state"]
        if ss.get("core_retrieved"):
            emb = discord.Embed(title="✅ Already Complete",
                                description="You already defeated the Void Sentinel!", color=0x00ff00)
            return await interaction.response.send_message(embed=emb, ephemeral=True)
        if len(ss["hints_collected"]) < 4:
            missing = 4 - len(ss["hints_collected"])
            emb = discord.Embed(title="⚔️ Void Sentinel — Invulnerable",
                                description=f"Collect **{missing} more hint(s)** first.",
                                color=0x880000)
            for ps in _STORY_PUZZLES:
                solved = ps["hint"] in ss["hints_collected"]
                emb.add_field(name=f"{'✅' if solved else '❌'} {ps['puzzle_type'].title()} Puzzle",
                              value=f"Coords: `{ps['coords']}`", inline=True)
            return await interaction.response.send_message(embed=emb, ephemeral=True)
        ud["boss_hp"]    = _SENTINEL["hp_max"]
        ud["boss_turns"] = 0
        _save_user(self.uid)
        emb, view = _boss_embed(self.uid)
        await interaction.response.edit_message(embed=emb, view=view)

# ─── BOSS FIGHT ────────────────────────────────────────────────────

def _boss_embed(uid: int):
    ud    = _get_user(uid)
    hp    = ud["boss_hp"]
    phase = _boss_phase(hp)
    emb   = discord.Embed(
        title="⚔️ BOSS BATTLE — Void Sentinel",
        description=f"_Ancient Guardian of the Core_\n\n**{phase['name']}**\n{phase['desc']}",
        color=phase["color"],
    )
    emb.add_field(name="👾 Sentinel HP", value=_hp_bar(hp, _SENTINEL["hp_max"]),      inline=False)
    emb.add_field(name="Visual",         value=f"```\n{phase['art']}\n```",            inline=False)
    emb.add_field(name="🚀 Your Ship",   value=_hp_bar(ud["fuel"], ud["max_fuel"]),   inline=False)
    emb.add_field(name="Turn",           value=str(ud["boss_turns"]+1),               inline=True)
    emb.set_footer(text="Choose your attack!")
    return emb, _BossView(uid)

class _BossView(ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=120)
        self.uid = uid

    @ui.button(label="🔫 Plasma Cannon",   style=discord.ButtonStyle.danger,    row=0)
    async def a0(self, i, b): await self._atk(i, 0)
    @ui.button(label="🚀 Missile Barrage", style=discord.ButtonStyle.danger,    row=0)
    async def a1(self, i, b): await self._atk(i, 1)
    @ui.button(label="⚡ Ion Beam",        style=discord.ButtonStyle.primary,   row=0)
    async def a2(self, i, b): await self._atk(i, 2)
    @ui.button(label="🌑 Void Lance",      style=discord.ButtonStyle.secondary, row=1)
    async def a3(self, i, b): await self._atk(i, 3)
    @ui.button(label="💥 Quantum Strike",  style=discord.ButtonStyle.secondary, row=1)
    async def a4(self, i, b): await self._atk(i, 4)

    @ui.button(label="🛡️ Defend", style=discord.ButtonStyle.success, row=1)
    async def defend(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your fight!", ephemeral=True)
        ud      = _get_user(self.uid)
        recover = random.randint(5,15) + ud["upgrades"]["shield_matrix"]*3
        ud["fuel"] = min(ud["max_fuel"], ud["fuel"] + recover)
        emb, view = await self._retaliate(ud, f"🛡️ Defended — recovered {recover} fuel.", None)
        await interaction.response.edit_message(embed=emb, view=view)

    async def _atk(self, interaction: discord.Interaction, idx: int):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌ Not your fight!", ephemeral=True)
        ud   = _get_user(self.uid)
        atk  = _PLAYER_ATTACKS[idx]
        base = random.randint(*atk["dmg"])
        bonus= ud["upgrades"]["battle_systems"] * 15
        crit = random.random() < atk["crit"]
        dmg  = int((base + bonus) * (2.0 if crit else 1.0))
        ud["boss_hp"] -= dmg
        player_txt = f"{atk['emoji']} **{atk['name']}** dealt **{dmg}**!" + (" ⭐ **CRIT!**" if crit else "")

        # Phase transition
        old_ratio = (ud["boss_hp"]+dmg) / _SENTINEL["hp_max"]
        new_ratio = max(0, ud["boss_hp"]) / _SENTINEL["hp_max"]
        phase_msg = None
        if old_ratio > 0.65 >= new_ratio:  phase_msg = _SENTINEL["phase2_msg"]
        elif old_ratio > 0.30 >= new_ratio: phase_msg = _SENTINEL["phase3_msg"]

        emb, view = await self._retaliate(ud, player_txt, phase_msg)
        await interaction.response.edit_message(embed=emb, view=view)

    async def _retaliate(self, ud: dict, player_txt: str, phase_msg):
        uid = self.uid

        # Victory
        if ud["boss_hp"] <= 0:
            ud["boss_hp"]   = None
            ud["boss_turns"]= 0
            ud["story_state"]["core_retrieved"] = True
            ud["credits"] += 2000
            ud["resources"]["crystals"]     = ud["resources"].get("crystals",0)    + 100
            ud["resources"]["energy"]       = ud["resources"].get("energy",0)      + 200
            ud["resources"]["dark_matter"]  = ud["resources"].get("dark_matter",0) + 20
            ud["achievements"].add("Void Slayer")
            ud["achievements"].add("Core Retriever")
            ud["achievements"].add("Ancient Wisdom")
            _save_user(uid)
            if _add_score: _add_score(uid, 1000)
            gs = _load_json(SCORES_FILE)
            gs[str(uid)] = gs.get(str(uid), 0) + 1000
            _save_json(SCORES_FILE, gs)
            emb = discord.Embed(
                title="🏆 VOID SENTINEL DEFEATED!",
                description=(
                    "**THE CORE VAULT IS OPEN.**\n\n"
                    "The ancient guardian collapses. The Ancient Core pulses in your grasp.\n\n"
                    "_Your name will echo across the galaxy._"
                ),
                color=0xffd700,
            )
            emb.add_field(name="🎁 Rewards",
                          value="🏆 +1,000 pts  💰 +2,000 credits  💎 +100 crystals  ⚡ +200 energy  🌑 +20 dark matter",
                          inline=False)
            emb.add_field(name="🏅 Achievements",
                          value="⭐ Void Slayer  ⭐ Core Retriever  ⭐ Ancient Wisdom", inline=False)
            return emb, None

        # Boss attacks
        phase   = _boss_phase(ud["boss_hp"])
        b_name, b_dmg_base, b_flavour = random.choice(phase["attacks"])
        shield  = ud["upgrades"]["shield_matrix"]
        actual  = max(5, b_dmg_base - shield*8 - random.randint(0,15))
        ud["fuel"] = max(0, ud["fuel"] - actual)
        ud["boss_turns"] += 1

        # Death
        if ud["fuel"] <= 0:
            ud["boss_hp"]   = None
            ud["boss_turns"]= 0
            ud["fuel"]      = 10
            _save_user(uid)
            emb = discord.Embed(
                title="💀 SHIP DESTROYED",
                description=(
                    f"**{b_name}** dealt {actual} damage — your hull gave way.\n\n"
                    "Escape pod jettisons. Respawned at base.\n"
                    "**Tip: Upgrade shield_matrix and battle_systems before retrying!**"
                ),
                color=0xff0000,
            )
            return emb, None

        _save_user(uid)
        emb = discord.Embed(title=f"⚔️ Turn {ud['boss_turns']} — {phase['name']}", color=phase["color"])
        emb.add_field(name="Your Action",        value=player_txt,                            inline=False)
        if phase_msg:
            emb.add_field(name="⚡ Phase Shift!", value=phase_msg,                             inline=False)
        emb.add_field(name="Sentinel Retaliates",
                      value=f"💀 **{b_name}** — {b_flavour}\nDealt **{actual}** damage!",    inline=False)
        emb.add_field(name="👾 Sentinel HP",     value=_hp_bar(ud["boss_hp"],_SENTINEL["hp_max"]),inline=False)
        emb.add_field(name="🚀 Your HP",         value=_hp_bar(ud["fuel"], ud["max_fuel"]),    inline=False)
        if ud["boss_hp"] < _SENTINEL["hp_max"] * 0.15:
            emb.add_field(name="😤 Taunt", value=_SENTINEL["low_hp_msg"], inline=False)
        emb.add_field(name="Visual", value=f"```\n{phase['art']}\n```", inline=False)
        return emb, _BossView(uid)

# ─── SHIPYARD VIEW ─────────────────────────────────────────────────

class _ShipyardView(ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=300)
        self.uid  = uid
        self.page = 0
        self.keys = list(_SHIP_UPGRADES.keys())

    def _embed(self) -> discord.Embed:
        ud   = _get_user(self.uid)
        key  = self.keys[self.page]
        inf  = _SHIP_UPGRADES[key]
        lv   = ud["upgrades"][key]
        cost = inf["cost"]*(lv+1) if lv < inf["max"] else None
        emb  = discord.Embed(title="🛸 Deep Space Shipyard",
                              description=f"Credits available: **{ud['credits']:,}**", color=0x4169e1)
        emb.add_field(name=key.replace("_"," ").title(),
                      value=f"_{inf['desc']}_\nLevel: **{lv}/{inf['max']}**", inline=False)
        emb.add_field(name="Next Cost", value=f"{cost:,} cr" if cost else "**MAXED OUT**", inline=True)
        emb.set_footer(text=f"Upgrade {self.page+1}/{len(self.keys)}")
        return emb

    @ui.button(label="⬅", style=discord.ButtonStyle.secondary)
    async def prev(self, i, b):
        if i.user.id != self.uid: return await i.response.send_message("❌", ephemeral=True)
        self.page = (self.page-1) % len(self.keys)
        await i.response.edit_message(embed=self._embed(), view=self)

    @ui.button(label="🔧 Buy Upgrade", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("❌", ephemeral=True)
        ud  = _get_user(self.uid)
        key = self.keys[self.page]
        inf = _SHIP_UPGRADES[key]
        lv  = ud["upgrades"][key]
        if lv >= inf["max"]:
            return await interaction.response.send_message("Already maxed!", ephemeral=True)
        cost = inf["cost"]*(lv+1)
        if ud["credits"] < cost:
            return await interaction.response.send_message(f"Need {cost:,} cr.", ephemeral=True)
        ud["credits"] -= cost
        ud["upgrades"][key] += 1
        if key == "fuel_tank":
            ud["max_fuel"] += 20
            ud["fuel"] = min(ud["fuel"]+20, ud["max_fuel"])
        _save_user(self.uid)
        await interaction.response.send_message(
            f"✅ **{key.replace('_',' ').title()}** upgraded to Lv {ud['upgrades'][key]}!", ephemeral=True)
        await interaction.edit_original_response(embed=self._embed(), view=self)

    @ui.button(label="➡", style=discord.ButtonStyle.secondary)
    async def nxt(self, i, b):
        if i.user.id != self.uid: return await i.response.send_message("❌", ephemeral=True)
        self.page = (self.page+1) % len(self.keys)
        await i.response.edit_message(embed=self._embed(), view=self)

# ─── GITHUB AUTO-BACKUP ────────────────────────────────────────────

def _git_push(message: str) -> str:
    try:
        repo = str(Path(GITHUB_REPO_DIR).resolve())
        outputs = []
        for cmd in [
            f'cd "{repo}" && git add data/',
            f'cd "{repo}" && git commit -m "{message}" --allow-empty',
            f'cd "{repo}" && git push origin {GITHUB_BRANCH}',
        ]:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            outputs.append(r.stdout.strip() or r.stderr.strip())
        return "\n".join(outputs)
    except Exception as e:
        return f"Git error: {e}"

@tasks.loop(hours=24)
async def daily_galaxy_backup():
    """Auto-commit galaxy data to GitHub every 24 hours.
    Start from on_ready:  daily_galaxy_backup.start()
    """
    _save_all()
    ts     = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    result = _git_push(f"🤖 Galaxy auto-backup [{ts}]")
    print(f"[GALAXY BACKUP] {ts}\n{result}")

@daily_galaxy_backup.before_loop
async def _before_backup():
    if _bot: await _bot.wait_until_ready()
    now = datetime.utcnow()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    await asyncio.sleep((nxt - now).total_seconds())

# ─── COMMAND REGISTRATION ──────────────────────────────────────────

def _register_commands(bot: commands.Bot):
    """Registers all galaxy commands onto main.py's bot instance."""

    @bot.command(name="galaxy", aliases=["explore","space","g"])
    async def cmd_galaxy(ctx):
        """Open the galaxy explorer."""
        uid  = ctx.author.id
        emb  = _map_embed(uid)
        view = _NavView(uid)
        await ctx.send(embed=emb, view=view)
        ud = _get_user(uid)
        if len(ud["discovered"]) == 0:
            welcome = discord.Embed(
                title="🌟 Welcome, Explorer!",
                description=(
                    "You've been assigned an exploration vessel. Discover star systems, "
                    "solve ancient puzzles, and defeat the **Void Sentinel**."
                ),
                color=0x00ffff,
            )
            welcome.add_field(name="🚀 Controls",
                              value="Arrows = navigate · 🔭 Scan = analyse system · ⚡ Explore = earn rewards",
                              inline=False)
            await ctx.send(embed=welcome, delete_after=30)

    @bot.command(name="gscan", aliases=["probe","gsys"])
    async def cmd_scan(ctx):
        """Scan the current star system."""
        ud  = _get_user(ctx.author.id)
        pos = ud["position"]
        sys = generate_system(pos[0], pos[1])
        await ctx.send(embed=_scan_embed(sys, ctx.author.id),
                       view=_ExploreView(ctx.author.id, sys))

    @bot.command(name="gstats", aliases=["gprofile","gme","galaxystats"])
    async def cmd_stats(ctx):
        """Show your commander profile."""
        await ctx.send(embed=_stats_embed(ctx.author.id, ctx.author))

    @bot.command(name="shipyard", aliases=["gupgrade","gshop","upgrade","shop"])
    async def cmd_shipyard(ctx):
        """Open the ship upgrade shop."""
        view = _ShipyardView(ctx.author.id)
        await ctx.send(embed=view._embed(), view=view)

    @bot.command(name="story", aliases=["pulse","gmissions","galaxyinfo","gstory"])
    async def cmd_story(ctx):
        """View Pulse-3 storyline progress."""
        uid = ctx.author.id
        if uid == _MASTER_ID:
            # Master overview
            emb = discord.Embed(title="🌌 All Players — Story Progress", color=0x9932cc)
            if not _galaxy:
                emb.description = "No players yet."
                return await ctx.send(embed=emb)
            active = 0; done = 0
            for uid_str, ud in _galaxy.items():
                ss    = ud.get("story_state", {})
                hints = len(ss.get("hints_collected", []))
                core  = ss.get("core_retrieved", False)
                if hints > 0 or core:
                    active += 1
                    try:    user = await bot.fetch_user(int(uid_str)); name = user.display_name
                    except: name = f"User {uid_str}"
                    pos_   = ud.get("position", [0,0])
                    emb.add_field(
                        name=f"👤 {name}",
                        value=f"**Status:** {'✅ Complete' if core else f'🧩 {hints}/4'}\n**Pos:** `({pos_[0]}, {pos_[1]})`",
                        inline=True,
                    )
                    if core: done += 1
            emb.add_field(name="📊 Summary",
                          value=f"Active: {active} | Done: {done} | In progress: {active-done}",
                          inline=False)
        else:
            ud = _get_user(uid)
            ss = ud["story_state"]
            emb = discord.Embed(title="📖 Pulse-3 Storyline Progress", color=0x9932cc)
            emb.set_thumbnail(url=ctx.author.display_avatar.url)
            emb.add_field(name="🧩 Puzzles", value=f"{ss['puzzles_solved']}/4", inline=True)
            emb.add_field(name="⚔️ Core",   value="Retrieved ✅" if ss["core_retrieved"] else "Not yet ❌", inline=True)
            emb.add_field(name="📍 Position",value=f"`({ud['position'][0]}, {ud['position'][1]})`", inline=True)
            for ps in _STORY_PUZZLES:
                solved = ps["hint"] in ss["hints_collected"]
                emb.add_field(
                    name=f"{'✅' if solved else '❌'} {ps['puzzle_type'].title()} Puzzle",
                    value=f"Coords: `{ps['coords']}`" + (f"\n> _{ps['hint']}_" if solved else ""),
                    inline=False,
                )
            if ss["hints_collected"] and not ss["core_retrieved"]:
                emb.add_field(name="📜 Hints",
                              value="\n".join(f"• {h}" for h in ss["hints_collected"]),
                              inline=False)
            if len(ss["hints_collected"]) >= 4 and not ss["core_retrieved"]:
                emb.add_field(name="🎯 Next Step",
                              value="Navigate to `(-78, 42)` → Scan → Fight Boss", inline=False)
            elif ss["core_retrieved"]:
                emb.add_field(name="🏆", value="Storyline complete! The Core powers your base.", inline=False)
            ev = _pulse3_event(ud)
            emb.add_field(name=ev["title"], value=ev["desc"], inline=False)
        await ctx.send(embed=emb)

    @bot.command(name="gleaderboard", aliases=["gtop","glb","grankings","galacticleaderboard"])
    async def cmd_lb(ctx):
        """Galaxy exploration leaderboard."""
        gs = _load_json(SCORES_FILE)
        if not gs:
            return await ctx.send("No galaxy scores yet!")
        sorted_s = sorted(gs.items(), key=lambda x: x[1], reverse=True)[:10]
        emb = discord.Embed(title="🏆 Galaxy Explorer Leaderboard", color=0xffd700)
        medals = ["🥇","🥈","🥉"] + ["🏅"]*7
        lines  = []
        for i, (uid_str, score) in enumerate(sorted_s):
            try:    user = bot.get_user(int(uid_str)) or await bot.fetch_user(int(uid_str)); name = user.display_name
            except: name = f"Explorer #{uid_str}"
            lines.append(f"{medals[i]} **{name}** — {score:,} pts")
        emb.description = "\n".join(lines)
        await ctx.send(embed=emb)

    @bot.command(name="worldinfo", aliases=["gbiome","gsector"])
    async def cmd_world(ctx):
        """Info about your current sector biome."""
        ud    = _get_user(ctx.author.id)
        pos   = ud["position"]
        biome = get_sector_biome(pos[0]//50, pos[1]//50)
        emb   = discord.Embed(
            title=f"🌍 Sector {pos[0]//50}.{pos[1]//50} — {biome['name']}",
            description=biome["desc"], color=biome["color"],
        )
        emb.add_field(name="Rarity",   value=biome["rarity"].title(), inline=True)
        emb.add_field(name="Position", value=f"`({pos[0]}, {pos[1]})`", inline=True)
        await ctx.send(embed=emb)

    @bot.command(name="teleport", aliases=["tp","goto"])
    async def cmd_teleport(ctx, location: str = None, x: int = None, y: int = None, member: discord.Member = None):
        """Master-only teleport command."""
        if ctx.author.id != _MASTER_ID:
            return await ctx.send("❌ Master only.")
        target_uid = member.id if member else ctx.author.id
        ud = _get_user(target_uid)
        presets = {
            "puzzle1":(15,25),"puzzle2":(-20,30),"puzzle3":(35,-15),
            "puzzle4":(-25,-40),"boss":(-78,42),"home":(0,0),"base":(0,0),
        }
        if location == "coords" and x is not None and y is not None:
            dest = (x, y)
        elif location and location.lower() in presets:
            dest = presets[location.lower()]
        else:
            emb = discord.Embed(title="🌌 Teleport Help", color=0x9932cc)
            emb.add_field(name="Presets",
                          value="\n".join(f"`!tp {k}` → {v}" for k,v in presets.items()), inline=False)
            emb.add_field(name="Custom",  value="`!teleport coords X Y [@user]`", inline=False)
            return await ctx.send(embed=emb)

        old = ud["position"].copy()
        ud["position"] = list(dest)
        ud["fuel"]     = ud["max_fuel"]
        _save_user(target_uid)
        who = member.mention if member else "You"

        emb = discord.Embed(title="✨ Teleportation Complete", color=0x00ff41,
                            timestamp=ctx.message.created_at)
        target_user = member or ctx.author
        emb.set_thumbnail(url=target_user.display_avatar.url)
        emb.add_field(name="📊 Details",
                      value=f"**Target:** {target_user.mention}\n**From:** `({old[0]}, {old[1]})`\n**To:** `{dest}`\n**Fuel:** Restored",
                      inline=False)
        if dest == (-78, 42):
            emb.add_field(name="⚠️ Boss Warning",
                          value="Ensure you have all 4 hints before engaging the Void Sentinel!", inline=False)
        ss    = ud.get("story_state", {})
        hints = len(ss.get("hints_collected", []))
        if hints > 0:
            emb.add_field(name="📜 Story", value=f"Hints: {hints}/4 | Core: {'✅' if ss.get('core_retrieved') else '❌'}", inline=True)
        await ctx.send(embed=emb)
        if member and member.id != ctx.author.id:
            try:
                dm = discord.Embed(title="✨ You've been teleported!",
                                   description=f"Sent to `{dest}`. Fuel fully restored.", color=0x00ff41)
                await member.send(embed=dm)
            except discord.Forbidden:
                await ctx.send(f"⚠️ Couldn't DM {member.mention}")

    @bot.command(name="galaxyadmin")
    @commands.is_owner()
    async def cmd_admin(ctx):
        total   = len(_galaxy)
        systems = sum(len(d.get("discovered",[])) for d in _galaxy.values())
        await ctx.send(f"🌌 Galaxy: **{total}** players · **{systems}** systems · **{len(_world)}** sectors")

    @bot.command(name="forcebackup")
    @commands.is_owner()
    async def cmd_forcebackup(ctx):
        _save_all()
        result = _git_push("Manual backup via !forcebackup")
        await ctx.send(f"```\n{result}\n```")

    @bot.command(name="galaxyhelp", aliases=["ghelp"])
    async def cmd_ghelp(ctx):
        """Galaxy Keeper command list."""
        emb = discord.Embed(title="🌌 Galaxy Keeper — Commands", color=0x1a1a2e)
        emb.add_field(name="🚀 Exploration",
                      value="`!galaxy` — Open map\n`!gscan` — Scan system\n`!worldinfo` — Biome info",
                      inline=False)
        emb.add_field(name="📊 Profile",
                      value="`!gstats` — Commander profile\n`!story` — Pulse-3 progress\n`!gleaderboard` — Top explorers",
                      inline=False)
        emb.add_field(name="🔧 Upgrades", value="`!shipyard` — Ship upgrade shop", inline=False)
        emb.add_field(name="⚔️ Boss Fight",
                      value="1. Solve 4 puzzles at `(15,25)` `(-20,30)` `(35,-15)` `(-25,-40)`\n"
                            "2. Travel to `(-78, 42)`\n3. Scan → Fight Boss",
                      inline=False)
        await ctx.send(embed=emb)