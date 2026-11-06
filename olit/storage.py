"""JSON persistence helpers and the shared game score store.

The score store is the one piece of mutable state several feature modules
touch, so it lives here rather than in any single feature. Galaxy RPG progress
is deliberately *separate* and owned by `galaxy_keeper.py`.
"""

import json
import os
from typing import Any, Dict

# Game scores, written by every minigame. Keys are stringified user IDs.
SCORES_FILE = "persistent/scores.json"


def read_json(path: str, default: Any) -> Any:
    """Load JSON from `path`, returning `default` if it is missing or corrupt.

    Never raises: a damaged save file degrades to the default rather than
    taking the whole bot down on startup.
    """
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[STORAGE] Could not read {path}: {exc}")
    return default


def write_json(path: str, data: Any) -> bool:
    """Write `data` to `path` as JSON, creating the parent directory.

    Returns True on success. Never raises, so a failed write cannot kill the
    command that triggered it.
    """
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return True
    except OSError as exc:
        print(f"[STORAGE] Could not write {path}: {exc}")
        return False


def load_scores() -> Dict[str, int]:
    """Read the score table from disk, or return an empty one."""
    data = read_json(SCORES_FILE, {})
    return data if isinstance(data, dict) else {}


# Live score table. Imported by name elsewhere, so always mutate in place --
# rebinding this module global would leave other modules pointing at the old
# dict.
scores: Dict[str, int] = load_scores()


def save_scores() -> bool:
    """Persist the current score table."""
    return write_json(SCORES_FILE, scores)


def add_score(user_id, points: int = 1) -> int:
    """Credit `points` to a user and persist immediately.

    User IDs are normalised to `str` because JSON object keys are always
    strings -- mixing int and str keys here previously caused scores to appear
    to reset after a restart. Returns the user's new total.
    """
    key = str(user_id)
    scores[key] = scores.get(key, 0) + points
    save_scores()
    return scores[key]


def get_score(user_id) -> int:
    """Return a user's current score, 0 if they have never played."""
    return scores.get(str(user_id), 0)


# ── Win streaks ───────────────────────────────────────────────────────────────
# Per-game consecutive-win counters, so a run of wins can pay a bonus. Kept in
# their own file rather than mixed into `scores`, which is a flat point total.

STREAKS_FILE = "persistent/streaks.json"


def load_streaks() -> Dict[str, Dict[str, int]]:
    """Read the streak table: {game: {user_id: current_streak}}."""
    data = read_json(STREAKS_FILE, {})
    if not isinstance(data, dict):
        return {}
    # Drop anything malformed rather than letting it crash a game later.
    return {
        game: {str(uid): int(n) for uid, n in players.items()}
        for game, players in data.items()
        if isinstance(players, dict)
    }


#: Live streak table. Mutate in place; see the note on `scores`.
streaks: Dict[str, Dict[str, int]] = load_streaks()


def save_streaks() -> bool:
    """Persist the current streak table."""
    return write_json(STREAKS_FILE, streaks)


def get_streak(game: str, user_id) -> int:
    """A user's current run of wins in `game`, 0 if none."""
    return streaks.get(game, {}).get(str(user_id), 0)


def bump_streak(game: str, user_id) -> int:
    """Extend a user's winning run and return its new length."""
    key = str(user_id)
    table = streaks.setdefault(game, {})
    table[key] = table.get(key, 0) + 1
    save_streaks()
    return table[key]


def reset_streak(game: str, user_id) -> int:
    """End a user's run. Returns the length it had reached."""
    key = str(user_id)
    table = streaks.setdefault(game, {})
    had = table.pop(key, 0)
    if had:
        save_streaks()
    return had


def best_streaks(game: str, limit: int = 10):
    """Current runs in `game`, longest first, as (user_id, streak) pairs."""
    table = streaks.get(game, {})
    return sorted(table.items(), key=lambda kv: kv[1], reverse=True)[:limit]
