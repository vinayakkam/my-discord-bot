"""Riddles and dynamic quests for the galaxy explorer.

Two gaps this fills.

**The puzzles were not puzzles.** Each story system carried a `puzzle_type` of
"cipher", "math", "sequence" or "logic", but the Solve Puzzle button simply
handed over the hint the moment it was clicked. The type was stored and never
read, so there was nothing to solve. `make_riddle()` now produces a real
challenge per type, and `check_answer()` grades it.

**There was nothing to do between story beats.** `daily_quests()` generates a
rotating set of objectives from the player's own save data, so there is always
a concrete goal and a reward attached to it.

Both are deterministic: a riddle is seeded from the player and the system's
coordinates, so re-opening the panel shows the same riddle rather than letting
a player re-roll until they get an easy one. Quests are seeded from the player
and the date, so everyone keeps a stable set for the day.
"""

import hashlib
import random
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

# ── Riddles ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Riddle:
    """One solvable challenge."""

    kind: str
    prompt: str
    answer: str
    hint: str = ""
    alt_answers: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def accepted(self) -> Tuple[str, ...]:
        """Every spelling counted as correct."""
        return (self.answer,) + tuple(self.alt_answers)


# Words used for the cipher puzzles. Space-themed, single words, no spaces.
_CIPHER_WORDS = [
    "NEBULA", "QUASAR", "PULSAR", "COMET", "ECLIPSE", "GRAVITY",
    "ORBIT", "PHOTON", "PLASMA", "SINGULARITY", "ASTEROID", "CORONA",
    "SUPERNOVA", "GALAXY", "METEOR", "APOGEE", "PERIGEE", "PARSEC",
]

# Logic riddles with a one-word answer.
_LOGIC_RIDDLES = [
    ("I have no mass yet I carry energy across the void. I am the fastest "
     "thing there is. What am I?", "photon", ("light", "a photon")),
    ("I pull without touching, bend light itself, and nothing escapes once "
     "past my edge. What am I?", "black hole", ("blackhole", "a black hole")),
    ("I am born when a giant dies, spinning fast and sweeping the dark with "
     "a beam like a lighthouse. What am I?", "pulsar", ("a pulsar", "neutron star")),
    ("I am a river of ice and dust. The closer I come to the fire, the "
     "longer my tail grows. What am I?", "comet", ("a comet",)),
    ("I weigh nothing, cost nothing, and fill everything between the stars. "
     "Astronomers map me by what I hide. What am I?", "dust",
     ("interstellar dust", "cosmic dust")),
    ("Two of us circle a common centre, forever falling toward each other "
     "and forever missing. What are we?", "binary stars",
     ("binary", "a binary star", "binary star system")),
    ("I am the distance light walks in a year, though I am not a measure of "
     "time. What am I?", "light year", ("lightyear", "a light year")),
    ("I shepherd the asteroid belt, scar myself with storms, and my red eye "
     "has watched for centuries. What am I?", "jupiter", ("planet jupiter",)),
    ("I mark the point where a moon is closest to its world. What am I?",
     "perigee", ("the perigee",)),
    ("I am the shadow one world casts upon another. What am I?", "eclipse",
     ("an eclipse", "solar eclipse")),
]

# Sequence puzzles: (description, generator of the terms, the next term).
_SEQUENCE_KINDS = ("arithmetic", "geometric", "squares", "fibonacci", "primes")


def _caesar(text: str, shift: int) -> str:
    """Shift the letters of `text` by `shift`, leaving anything else alone."""
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)


def _make_cipher(rng: random.Random) -> Riddle:
    """A Caesar-shifted space word to decode."""
    word = rng.choice(_CIPHER_WORDS)
    shift = rng.randint(1, 25)
    scrambled = _caesar(word, shift)
    return Riddle(
        kind="cipher",
        prompt=(
            "**Precursor Cipher**\n"
            "The inscription reads:\n"
            f"```\n{scrambled}\n```"
            f"Each letter has been rotated forward by **{shift}** places in the "
            "alphabet. Decode it."
        ),
        answer=word.lower(),
        hint=f"Rotate every letter back {shift} places. "
             f"'{scrambled[0]}' becomes '{word[0]}'.",
    )


def _make_math(rng: random.Random) -> Riddle:
    """Arithmetic dressed as an orbital-mechanics readout."""
    style = rng.choice(("thrust", "transfer", "fuel", "window"))

    if style == "thrust":
        engines = rng.randint(3, 9)
        each = rng.choice((150, 175, 200, 225, 250))
        loss = rng.randint(1, engines - 1)
        answer = (engines - loss) * each
        prompt = (
            "**Thrust Computation**\n"
            f"Your vessel has **{engines}** engines, each producing "
            f"**{each} kN**. **{loss}** have failed.\n"
            "What is the remaining total thrust, in kN?"
        )
        hint = f"({engines} - {loss}) x {each}"
    elif style == "transfer":
        a, b = rng.randint(2, 30), rng.randint(2, 30)
        answer = a * b
        prompt = (
            "**Transfer Window**\n"
            f"A burn lasts **{a}** minutes and must be repeated **{b}** times.\n"
            "How many minutes of burn in total?"
        )
        hint = f"{a} x {b}"
    elif style == "fuel":
        total = rng.randint(400, 900)
        per = rng.choice((5, 8, 10, 12, 15))
        answer = total // per
        prompt = (
            "**Fuel Budget**\n"
            f"You carry **{total}** units of fuel and each jump costs "
            f"**{per}**.\nHow many complete jumps can you make?"
        )
        hint = f"{total} divided by {per}, rounded down"
    else:
        base = rng.randint(20, 60)
        mult = rng.randint(2, 6)
        offset = rng.randint(5, 40)
        answer = base * mult - offset
        prompt = (
            "**Resonance Count**\n"
            f"Three suns pulse every **{base}** seconds. Count **{mult}** "
            f"full cycles, then subtract the **{offset}** second dead band.\n"
            "What is the resonance value?"
        )
        hint = f"{base} x {mult} - {offset}"

    return Riddle(kind="math", prompt=prompt, answer=str(answer), hint=hint)


def _make_sequence(rng: random.Random) -> Riddle:
    """A number sequence with the next term as the answer."""
    kind = rng.choice(_SEQUENCE_KINDS)

    if kind == "arithmetic":
        start, step = rng.randint(2, 20), rng.randint(3, 15)
        terms = [start + step * i for i in range(5)]
        answer = start + step * 5
        hint = f"Each term rises by {step}."
    elif kind == "geometric":
        start, ratio = rng.randint(1, 5), rng.randint(2, 4)
        terms = [start * ratio ** i for i in range(5)]
        answer = start * ratio ** 5
        hint = f"Each term is {ratio} times the one before."
    elif kind == "squares":
        offset = rng.randint(0, 4)
        terms = [(i + 1 + offset) ** 2 for i in range(5)]
        answer = (6 + offset) ** 2
        hint = "These are perfect squares."
    elif kind == "fibonacci":
        a, b = rng.randint(1, 6), rng.randint(1, 6)
        terms = [a, b]
        while len(terms) < 5:
            terms.append(terms[-1] + terms[-2])
        answer = terms[-1] + terms[-2]
        hint = "Each term is the sum of the two before it."
    else:
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
        start = rng.randint(0, 5)
        terms = primes[start:start + 5]
        answer = primes[start + 5]
        hint = "They are consecutive prime numbers."

    shown = ", ".join(str(t) for t in terms)
    return Riddle(
        kind="sequence",
        prompt=(
            "**Resonance Sequence**\n"
            "The ancient computer displays a repeating pattern:\n"
            f"```\n{shown}, ?\n```"
            "What is the next value?"
        ),
        answer=str(answer),
        hint=hint,
    )


def _make_logic(rng: random.Random) -> Riddle:
    """A one-word space riddle."""
    prompt, answer, alts = rng.choice(_LOGIC_RIDDLES)
    return Riddle(
        kind="logic",
        prompt=f"**Precursor Riddle**\n_{prompt}_",
        answer=answer,
        alt_answers=alts,
        hint=f"The answer begins with '{answer[0].upper()}' "
             f"and has {len(answer.replace(' ', ''))} letters.",
    )


_RIDDLE_MAKERS = {
    "cipher": _make_cipher,
    "math": _make_math,
    "sequence": _make_sequence,
    "logic": _make_logic,
}


def _seed_for(*parts) -> int:
    """A stable integer seed from arbitrary values."""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def make_riddle(puzzle_type: str, uid, coords, attempt_salt: int = 0) -> Riddle:
    """Build the riddle for a player at a story system.

    Deterministic in (puzzle_type, uid, coords), so reopening the panel shows
    the same riddle instead of letting a player re-roll for an easier one.
    `attempt_salt` is only for tests that want a different draw.
    """
    maker = _RIDDLE_MAKERS.get(puzzle_type, _make_logic)
    rng = random.Random(_seed_for(puzzle_type, uid, coords, attempt_salt))
    return maker(rng)


def normalise_answer(text: str) -> str:
    """Canonical form for comparing answers.

    Case, accents, surrounding articles, punctuation and internal spacing are
    all ignored, so "A Black Hole" matches "blackhole".
    """
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.strip().lower()

    for article in ("the ", "a ", "an "):
        if text.startswith(article):
            text = text[len(article):]

    return "".join(c for c in text if c.isalnum())


def check_answer(riddle: Riddle, given: str) -> bool:
    """Whether `given` solves `riddle`."""
    candidate = normalise_answer(given)
    if not candidate:
        return False
    return candidate in {normalise_answer(a) for a in riddle.accepted}


# ── Dynamic quests ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class QuestTemplate:
    """A kind of objective, scaled at generation time."""

    key: str
    title: str
    emoji: str
    #: Dotted path into the save data, e.g. "resources.crystals".
    metric: str
    #: (min, max) target increase over the player's current value.
    amount: Tuple[int, int]
    reward_credits: Tuple[int, int]
    reward_points: int


QUEST_TEMPLATES: List[QuestTemplate] = [
    QuestTemplate("explore", "Chart {n} new systems", "\U0001F6F0️",
                  "successful_explorations", (3, 8), (200, 600), 25),
    QuestTemplate("crystals", "Mine {n} crystals", "\U0001F48E",
                  "resources.crystals", (10, 40), (150, 450), 20),
    QuestTemplate("metals", "Refine {n} metals", "⚙️",
                  "resources.metals", (15, 50), (150, 450), 20),
    QuestTemplate("energy", "Collect {n} energy", "⚡",
                  "resources.energy", (10, 35), (150, 450), 20),
    QuestTemplate("dark_matter", "Contain {n} dark matter", "\U0001F311",
                  "resources.dark_matter", (2, 8), (400, 900), 40),
    QuestTemplate("credits", "Earn {n} credits", "\U0001F4B0",
                  "total_credits_earned", (500, 2500), (0, 0), 30),
    QuestTemplate("survive", "Survive {n} hazards", "☠️",
                  "danger_encounters", (2, 5), (300, 700), 35),
    QuestTemplate("discover", "Discover {n} systems", "\U0001F30C",
                  "discovered", (2, 6), (250, 650), 25),
]

#: How many quests a player holds at once.
QUESTS_PER_DAY = 3


def read_metric(save: dict, metric: str) -> int:
    """Read a dotted metric path out of a save dict.

    `discovered` is a set or list of coordinates, so its length is the value.
    """
    node = save
    for part in metric.split("."):
        if not isinstance(node, dict):
            return 0
        node = node.get(part, 0)

    if isinstance(node, (set, list, tuple, dict)):
        return len(node)
    try:
        return int(node)
    except (TypeError, ValueError):
        return 0


def generate_quests(save: dict, uid, on: Optional[date] = None,
                    count: int = QUESTS_PER_DAY) -> List[dict]:
    """Build a player's quest set for a given day.

    Each quest records the player's metric value at assignment, so progress is
    measured as a delta. That makes a quest like "mine 20 crystals" mean twenty
    *more* than you had, rather than being instantly complete because you were
    already carrying thirty.
    """
    on = on or date.today()
    rng = random.Random(_seed_for("quests", uid, on.isoformat()))

    chosen = rng.sample(QUEST_TEMPLATES, k=min(count, len(QUEST_TEMPLATES)))
    quests = []
    for template in chosen:
        amount = rng.randint(*template.amount)
        baseline = read_metric(save, template.metric)
        low, high = template.reward_credits
        quests.append({
            "key": template.key,
            "title": template.title.format(n=amount),
            "emoji": template.emoji,
            "metric": template.metric,
            "amount": amount,
            "baseline": baseline,
            "reward_credits": rng.randint(low, high) if high else 0,
            "reward_points": template.reward_points,
            "claimed": False,
        })
    return quests


def quest_progress(save: dict, quest: dict) -> Tuple[int, int]:
    """Return (done, target) for a quest, clamped to the target."""
    target = max(1, int(quest.get("amount", 1)))
    current = read_metric(save, quest.get("metric", ""))
    done = max(0, current - int(quest.get("baseline", 0)))
    return min(done, target), target


def is_complete(save: dict, quest: dict) -> bool:
    done, target = quest_progress(save, quest)
    return done >= target


def progress_bar(done: int, target: int, width: int = 12) -> str:
    """A compact text progress bar."""
    target = max(1, target)
    filled = int(width * min(1.0, done / target))
    return "█" * filled + "░" * (width - filled)


def refresh_quests(save: dict, uid, on: Optional[date] = None) -> List[dict]:
    """Return the player's quests, regenerating them if the day has rolled.

    Stored on the save under `quests` alongside the day they were issued, so
    unclaimed rewards are not silently lost mid-session.
    """
    on = on or date.today()
    today = on.isoformat()

    store = save.setdefault("quest_state", {})
    if store.get("day") != today:
        store["day"] = today
        store["quests"] = generate_quests(save, uid, on)
    return store["quests"]


def claim_rewards(save: dict, uid) -> Dict[str, int]:
    """Claim every completed, unclaimed quest.

    Returns a summary of what was awarded. Credits are applied to the save
    here; points are returned for the caller to pass to the global scorer.
    """
    quests = save.get("quest_state", {}).get("quests", [])

    credits = points = claimed = 0
    for quest in quests:
        if quest.get("claimed") or not is_complete(save, quest):
            continue
        quest["claimed"] = True
        claimed += 1
        credits += int(quest.get("reward_credits", 0))
        points += int(quest.get("reward_points", 0))

    if credits:
        save["credits"] = save.get("credits", 0) + credits
        save["total_credits_earned"] = (
            save.get("total_credits_earned", 0) + credits
        )

    return {"quests": claimed, "credits": credits, "points": points}
