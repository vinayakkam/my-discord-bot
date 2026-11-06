"""Space trivia questions: a curated set plus a generator built on real data.

The hand-written bank in main.py held 60 questions (20 per difficulty), so
regular players saw repeats almost immediately. Rather than ask anyone to keep
writing questions, this module *generates* them from astronomy data tables:
planet properties, the moon-to-parent mapping, constellations and mission
history.

Every generator produces strictly space-related questions, which is why Open
Trivia DB is not used here -- its "Science & Nature" pool is mostly chemistry,
biology and psychology.

A question is a dict matching the shape main.py already consumes:

    {"question": str, "options": [str, str, str], "answer": str}

Exactly three options, because the answer buttons are labelled A/B/C.

Correctness matters more than volume: `build_bank()` validates every generated
question (answer present in options, no duplicate options, three options) and
drops any that fail, and `tests/test_trivia_bank.py` asserts the same.
"""

import random
from itertools import combinations
from typing import Dict, List, Optional

# ── Source data ───────────────────────────────────────────────────────────────

# name -> properties. `order` is distance rank from the Sun.
PLANETS: Dict[str, dict] = {
    "Mercury": {"order": 1, "moons": 0, "diameter_km": 4879,
                "day_hours": 1408.0, "year_days": 88.0, "rings": False},
    "Venus":   {"order": 2, "moons": 0, "diameter_km": 12104,
                "day_hours": 5832.0, "year_days": 225.0, "rings": False},
    "Earth":   {"order": 3, "moons": 1, "diameter_km": 12756,
                "day_hours": 24.0, "year_days": 365.25, "rings": False},
    "Mars":    {"order": 4, "moons": 2, "diameter_km": 6792,
                "day_hours": 24.7, "year_days": 687.0, "rings": False},
    "Jupiter": {"order": 5, "moons": 95, "diameter_km": 142984,
                "day_hours": 9.9, "year_days": 4333.0, "rings": True},
    "Saturn":  {"order": 6, "moons": 146, "diameter_km": 120536,
                "day_hours": 10.7, "year_days": 10759.0, "rings": True},
    "Uranus":  {"order": 7, "moons": 28, "diameter_km": 51118,
                "day_hours": 17.2, "year_days": 30687.0, "rings": True},
    "Neptune": {"order": 8, "moons": 16, "diameter_km": 49528,
                "day_hours": 16.1, "year_days": 60190.0, "rings": True},
}

ORDINALS = {1: "first", 2: "second", 3: "third", 4: "fourth",
            5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth"}

# parent body -> its moons. Only well-known named moons, so the distractors
# stay recognisable.
MOONS: Dict[str, List[str]] = {
    "Earth": ["the Moon"],
    "Mars": ["Phobos", "Deimos"],
    "Jupiter": ["Io", "Europa", "Ganymede", "Callisto", "Amalthea",
                "Himalia", "Elara", "Metis", "Thebe", "Carme"],
    "Saturn": ["Titan", "Rhea", "Iapetus", "Dione", "Tethys", "Enceladus",
               "Mimas", "Hyperion", "Phoebe", "Janus", "Epimetheus",
               "Prometheus", "Pandora"],
    "Uranus": ["Titania", "Oberon", "Umbriel", "Ariel", "Miranda", "Puck"],
    "Neptune": ["Triton", "Nereid", "Proteus", "Larissa", "Galatea", "Despina"],
    "Pluto": ["Charon", "Nix", "Hydra", "Kerberos", "Styx"],
}

# Space missions: launch year, operator, and target.
MISSIONS: Dict[str, dict] = {
    "Apollo 11": {"year": 1969, "agency": "NASA", "target": "the Moon"},
    "Apollo 13": {"year": 1970, "agency": "NASA", "target": "the Moon"},
    "Voyager 1": {"year": 1977, "agency": "NASA", "target": "the outer planets"},
    "Voyager 2": {"year": 1977, "agency": "NASA", "target": "the outer planets"},
    "Galileo": {"year": 1989, "agency": "NASA", "target": "Jupiter"},
    "Cassini": {"year": 1997, "agency": "NASA", "target": "Saturn"},
    "Spirit": {"year": 2003, "agency": "NASA", "target": "Mars"},
    "Rosetta": {"year": 2004, "agency": "ESA", "target": "a comet"},
    "New Horizons": {"year": 2006, "agency": "NASA", "target": "Pluto"},
    "Juno": {"year": 2011, "agency": "NASA", "target": "Jupiter"},
    "Curiosity": {"year": 2011, "agency": "NASA", "target": "Mars"},
    "Mangalyaan": {"year": 2013, "agency": "ISRO", "target": "Mars"},
    "Hayabusa2": {"year": 2014, "agency": "JAXA", "target": "an asteroid"},
    "OSIRIS-REx": {"year": 2016, "agency": "NASA", "target": "an asteroid"},
    "Parker Solar Probe": {"year": 2018, "agency": "NASA", "target": "the Sun"},
    "InSight": {"year": 2018, "agency": "NASA", "target": "Mars"},
    "Tianwen-1": {"year": 2020, "agency": "CNSA", "target": "Mars"},
    "Perseverance": {"year": 2020, "agency": "NASA", "target": "Mars"},
    "Chandrayaan-3": {"year": 2023, "agency": "ISRO", "target": "the Moon"},
}

AGENCIES = ["NASA", "ESA", "ISRO", "JAXA", "CNSA", "Roscosmos"]

# Brightest stars and the constellation each sits in.
STARS: Dict[str, str] = {
    "Sirius": "Canis Major",
    "Canopus": "Carina",
    "Arcturus": "Boötes",
    "Vega": "Lyra",
    "Capella": "Auriga",
    "Rigel": "Orion",
    "Betelgeuse": "Orion",
    "Procyon": "Canis Minor",
    "Altair": "Aquila",
    "Aldebaran": "Taurus",
    "Antares": "Scorpius",
    "Spica": "Virgo",
    "Pollux": "Gemini",
    "Deneb": "Cygnus",
    "Regulus": "Leo",
    "Polaris": "Ursa Minor",
}

# Launch vehicles and who operates them.
ROCKETS: Dict[str, str] = {
    "Falcon 9": "SpaceX",
    "Falcon Heavy": "SpaceX",
    "Starship": "SpaceX",
    "New Glenn": "Blue Origin",
    "New Shepard": "Blue Origin",
    "Electron": "Rocket Lab",
    "Neutron": "Rocket Lab",
    "Atlas V": "United Launch Alliance",
    "Delta IV Heavy": "United Launch Alliance",
    "Vulcan Centaur": "United Launch Alliance",
    "Ariane 5": "Arianespace",
    "Ariane 6": "Arianespace",
    "PSLV": "ISRO",
    "GSLV Mk III": "ISRO",
    "H-IIA": "JAXA",
    "Long March 5": "CNSA",
    "Soyuz": "Roscosmos",
    "Saturn V": "NASA",
    "Space Launch System": "NASA",
}

# Notable deep-sky objects and what kind of object each is.
DEEP_SKY: Dict[str, str] = {
    "The Orion Nebula": "a nebula",
    "The Crab Nebula": "a supernova remnant",
    "The Ring Nebula": "a planetary nebula",
    "Andromeda": "a galaxy",
    "The Whirlpool": "a galaxy",
    "The Sombrero": "a galaxy",
    "The Pleiades": "an open star cluster",
    "Omega Centauri": "a globular cluster",
    "The Hercules Cluster": "a globular cluster",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_distractors(correct: str, pool: List[str], count: int = 2,
                      rng: Optional[random.Random] = None) -> List[str]:
    """Choose `count` wrong answers from `pool`, never equal to `correct`."""
    rng = rng or random
    candidates = [p for p in pool if p != correct]
    if len(candidates) < count:
        return []
    return rng.sample(candidates, count)


def _make(question: str, answer: str, distractors: List[str],
          rng: Optional[random.Random] = None) -> Optional[dict]:
    """Assemble and shuffle a question, or return None if it is malformed."""
    rng = rng or random
    if not distractors or answer in distractors:
        return None
    options = [answer] + list(distractors)
    if len(set(options)) != len(options):
        return None
    rng.shuffle(options)
    return {"question": question, "options": options, "answer": answer}


# ── Generators ────────────────────────────────────────────────────────────────

def gen_planet_order(rng=None) -> List[dict]:
    """"Which planet is Nth from the Sun?" and the reverse."""
    out = []
    names = list(PLANETS)
    for name, data in PLANETS.items():
        ordinal = ORDINALS[data["order"]]
        out.append(_make(
            f"Which planet is the {ordinal} from the Sun?",
            name, _pick_distractors(name, names, rng=rng), rng))
        out.append(_make(
            f"How far from the Sun is {name}, counting outwards?",
            f"{ordinal.capitalize()}",
            [f"{ORDINALS[o].capitalize()}" for o in
             _pick_distractors(data["order"], list(ORDINALS), rng=rng)], rng))
    return [q for q in out if q]


def gen_planet_moons(rng=None) -> List[dict]:
    """Moon counts, including the two planets with none."""
    out = []
    counts = [str(d["moons"]) for d in PLANETS.values()]
    for name, data in PLANETS.items():
        out.append(_make(
            f"Roughly how many confirmed moons does {name} have?",
            str(data["moons"]),
            _pick_distractors(str(data["moons"]), counts, rng=rng), rng))

    moonless = [n for n, d in PLANETS.items() if d["moons"] == 0]
    withmoons = [n for n, d in PLANETS.items() if d["moons"] > 0]
    for name in moonless:
        out.append(_make(
            "Which of these planets has no moons at all?",
            name, _pick_distractors(name, withmoons, rng=rng), rng))
    return [q for q in out if q]


def gen_planet_superlatives(rng=None) -> List[dict]:
    """Largest, smallest, longest day, longest year, and ring systems."""
    out = []
    names = list(PLANETS)

    biggest = max(PLANETS, key=lambda n: PLANETS[n]["diameter_km"])
    smallest = min(PLANETS, key=lambda n: PLANETS[n]["diameter_km"])
    longest_day = max(PLANETS, key=lambda n: PLANETS[n]["day_hours"])
    shortest_day = min(PLANETS, key=lambda n: PLANETS[n]["day_hours"])
    longest_year = max(PLANETS, key=lambda n: PLANETS[n]["year_days"])
    shortest_year = min(PLANETS, key=lambda n: PLANETS[n]["year_days"])

    for prompt, answer in [
        ("Which is the largest planet in the Solar System?", biggest),
        ("Which is the smallest planet in the Solar System?", smallest),
        ("Which planet has the longest day?", longest_day),
        ("Which planet has the shortest day?", shortest_day),
        ("Which planet takes the longest to orbit the Sun?", longest_year),
        ("Which planet has the shortest year?", shortest_year),
    ]:
        out.append(_make(prompt, answer,
                         _pick_distractors(answer, names, rng=rng), rng))

    ringed = [n for n, d in PLANETS.items() if d["rings"]]
    unringed = [n for n, d in PLANETS.items() if not d["rings"]]
    for name in unringed:
        out.append(_make(
            "Which of these planets has no ring system?",
            name, _pick_distractors(name, ringed, rng=rng), rng))

    # "Which of these three is largest/smallest" comparisons, which add a lot
    # of variety. A head-to-head "A or B?" phrasing cannot work here: the view
    # always renders three buttons, so a two-way question would need a third
    # option that is not one of the two planets named in the prompt.
    rng_local = rng or random
    for triple in _planet_triples(names):
        largest = max(triple, key=lambda n: PLANETS[n]["diameter_km"])
        smallest = min(triple, key=lambda n: PLANETS[n]["diameter_km"])
        listed = ", ".join(triple)
        out.append(_make(
            f"Which of these is the largest: {listed}?",
            largest, [n for n in triple if n != largest], rng_local))
        out.append(_make(
            f"Which of these is the smallest: {listed}?",
            smallest, [n for n in triple if n != smallest], rng_local))
    return [q for q in out if q]


def _planet_triples(names: List[str]) -> List[List[str]]:
    """Distinct groups of three planets, used for comparison questions."""
    return [list(combo) for combo in combinations(sorted(names), 3)]


def gen_moon_parents(rng=None) -> List[dict]:
    """"Which planet does <moon> orbit?" for every listed moon."""
    out = []
    parents = list(MOONS)
    for parent, moons in MOONS.items():
        for moon in moons:
            label = moon if moon.startswith("the ") else moon
            out.append(_make(
                f"Which body does {label} orbit?",
                parent, _pick_distractors(parent, parents, rng=rng), rng))

    # And the reverse: name a moon of a given planet.
    all_moons = [m for ms in MOONS.values() for m in ms]
    for parent, moons in MOONS.items():
        if not moons:
            continue
        answer = moons[0]
        foreign = [m for m in all_moons if m not in moons]
        out.append(_make(
            f"Which of these is a moon of {parent}?",
            answer, _pick_distractors(answer, foreign, rng=rng), rng))
    return [q for q in out if q]


def gen_missions(rng=None) -> List[dict]:
    """Mission operator, target and launch year."""
    out = []
    years = [str(d["year"]) for d in MISSIONS.values()]
    targets = sorted({d["target"] for d in MISSIONS.values()})

    for name, data in MISSIONS.items():
        out.append(_make(
            f"Which agency launched {name}?",
            data["agency"], _pick_distractors(data["agency"], AGENCIES, rng=rng), rng))
        out.append(_make(
            f"What was the destination of {name}?",
            data["target"], _pick_distractors(data["target"], targets, rng=rng), rng))
        out.append(_make(
            f"In which year did {name} launch?",
            str(data["year"]),
            _pick_distractors(str(data["year"]), years, rng=rng), rng))

    # Which mission reached a given target.
    for target in targets:
        matching = [n for n, d in MISSIONS.items() if d["target"] == target]
        nonmatching = [n for n, d in MISSIONS.items() if d["target"] != target]
        answer = matching[0]
        out.append(_make(
            f"Which of these missions was sent to {target}?",
            answer, _pick_distractors(answer, nonmatching, rng=rng), rng))
    return [q for q in out if q]


def gen_stars(rng=None) -> List[dict]:
    """Which constellation hosts a given bright star."""
    out = []
    constellations = sorted(set(STARS.values()))
    for star, constellation in STARS.items():
        out.append(_make(
            f"In which constellation would you find {star}?",
            constellation,
            _pick_distractors(constellation, constellations, rng=rng), rng))

    for constellation in constellations:
        matching = [s for s, c in STARS.items() if c == constellation]
        nonmatching = [s for s, c in STARS.items() if c != constellation]
        answer = matching[0]
        out.append(_make(
            f"Which bright star lies in {constellation}?",
            answer, _pick_distractors(answer, nonmatching, rng=rng), rng))
    return [q for q in out if q]


def gen_rockets(rng=None) -> List[dict]:
    """Who operates a given launch vehicle, and vice versa."""
    out = []
    operators = sorted(set(ROCKETS.values()))
    for rocket, operator in ROCKETS.items():
        out.append(_make(
            f"Which organisation operates the {rocket} rocket?",
            operator, _pick_distractors(operator, operators, rng=rng), rng))

    for operator in operators:
        matching = [r for r, o in ROCKETS.items() if o == operator]
        nonmatching = [r for r, o in ROCKETS.items() if o != operator]
        answer = matching[0]
        out.append(_make(
            f"Which of these rockets is built by {operator}?",
            answer, _pick_distractors(answer, nonmatching, rng=rng), rng))
    return [q for q in out if q]


def gen_deep_sky(rng=None) -> List[dict]:
    """What kind of object a famous deep-sky target is."""
    out = []
    kinds = sorted(set(DEEP_SKY.values()))
    for obj, kind in DEEP_SKY.items():
        out.append(_make(
            f"What kind of object is {obj}?",
            kind, _pick_distractors(kind, kinds, rng=rng), rng))
    return [q for q in out if q]


#: Generators grouped by how hard their output is, which sets the point value.
GENERATORS = {
    "easy": [gen_planet_order, gen_planet_superlatives],
    "medium": [gen_planet_moons, gen_moon_parents, gen_rockets],
    "hard": [gen_missions, gen_stars, gen_deep_sky],
}


# ── Validation and assembly ───────────────────────────────────────────────────

def is_valid(question: dict) -> bool:
    """Whether a question is well formed and answerable.

    A malformed question is worse than a missing one: it either has no correct
    button or two identical ones.
    """
    if not isinstance(question, dict):
        return False
    if set(question) < {"question", "options", "answer"}:
        return False
    options = question.get("options")
    if not isinstance(options, list) or len(options) != 3:
        return False
    if len(set(options)) != 3:
        return False
    if question["answer"] not in options:
        return False
    return bool(str(question.get("question", "")).strip())


def build_bank(curated: Optional[Dict[str, List[dict]]] = None,
               rng: Optional[random.Random] = None) -> Dict[str, List[dict]]:
    """Return {difficulty: [questions]}, curated entries first.

    Generated questions are deduplicated by prompt text and validated, so a
    faulty generator cannot put an unanswerable question in front of a player.
    """
    rng = rng or random
    bank: Dict[str, List[dict]] = {}

    for difficulty, generators in GENERATORS.items():
        seen_prompts = set()
        questions: List[dict] = []

        for question in (curated or {}).get(difficulty, []):
            if is_valid(question) and question["question"] not in seen_prompts:
                seen_prompts.add(question["question"])
                questions.append(question)

        for generator in generators:
            for question in generator(rng):
                if not is_valid(question):
                    continue
                if question["question"] in seen_prompts:
                    continue
                seen_prompts.add(question["question"])
                questions.append(question)

        bank[difficulty] = questions

    return bank


def bank_sizes(bank: Dict[str, List[dict]]) -> Dict[str, int]:
    """Question count per difficulty, for diagnostics and help text."""
    return {difficulty: len(questions) for difficulty, questions in bank.items()}
