"""Tests for the galaxy riddles and daily contracts."""

from datetime import date

import pytest

from olit.features import galaxy_quests as gq

RIDDLE_KINDS = ("cipher", "math", "sequence", "logic")


def _save(**overrides):
    base = {
        "credits": 150,
        "total_credits_earned": 150,
        "successful_explorations": 0,
        "danger_encounters": 0,
        "resources": {"crystals": 0, "metals": 0, "energy": 0, "dark_matter": 0},
        "discovered": set(),
    }
    base.update(overrides)
    return base


# ── Riddles ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", RIDDLE_KINDS)
def test_riddle_is_solvable_by_its_own_answer(kind):
    riddle = gq.make_riddle(kind, 1, (0, 0))
    assert riddle.prompt.strip()
    assert riddle.answer.strip()
    assert gq.check_answer(riddle, riddle.answer)


@pytest.mark.parametrize("kind", RIDDLE_KINDS)
def test_riddle_rejects_a_wrong_answer(kind):
    riddle = gq.make_riddle(kind, 1, (0, 0))
    assert not gq.check_answer(riddle, "obviously not the answer")
    assert not gq.check_answer(riddle, "")
    assert not gq.check_answer(riddle, None)


@pytest.mark.parametrize("kind", RIDDLE_KINDS)
def test_riddle_is_deterministic_per_player_and_system(kind):
    """Re-opening the panel must not re-roll for an easier riddle."""
    first = gq.make_riddle(kind, 42, (15, 25))
    again = gq.make_riddle(kind, 42, (15, 25))
    assert first == again


@pytest.mark.parametrize("kind", RIDDLE_KINDS)
def test_riddle_differs_between_players(kind):
    a = gq.make_riddle(kind, 1, (15, 25))
    b = gq.make_riddle(kind, 2, (15, 25))
    assert a.prompt != b.prompt or a.answer != b.answer


@pytest.mark.parametrize("kind", RIDDLE_KINDS)
def test_riddle_differs_between_systems(kind):
    a = gq.make_riddle(kind, 1, (15, 25))
    b = gq.make_riddle(kind, 1, (-20, 30))
    assert a.prompt != b.prompt or a.answer != b.answer


def test_unknown_puzzle_type_falls_back_instead_of_crashing():
    riddle = gq.make_riddle("nonsense-type", 1, (0, 0))
    assert gq.check_answer(riddle, riddle.answer)


def test_every_riddle_has_a_hint():
    for kind in RIDDLE_KINDS:
        assert gq.make_riddle(kind, 7, (1, 2)).hint.strip()


def test_cipher_answer_actually_decodes_the_prompt():
    """The shown ciphertext must decode to the stated answer."""
    for uid in range(40):
        riddle = gq.make_riddle("cipher", uid, (1, 1))
        # Pull the ciphertext and shift back out of the prompt.
        import re
        cipher = re.search(r"```\n(\w+)\n```", riddle.prompt).group(1)
        shift = int(re.search(r"\*\*(\d+)\*\* places", riddle.prompt).group(1))
        assert gq._caesar(cipher, -shift).lower() == riddle.answer


def test_sequence_answers_are_numeric():
    for uid in range(30):
        riddle = gq.make_riddle("sequence", uid, (1, 1))
        assert riddle.answer.lstrip("-").isdigit(), riddle.prompt


def test_math_answers_are_numeric():
    for uid in range(30):
        riddle = gq.make_riddle("math", uid, (1, 1))
        assert riddle.answer.lstrip("-").isdigit(), riddle.prompt


@pytest.mark.parametrize("given", [
    "black hole", "Black Hole", "  BLACKHOLE  ", "a black hole",
    "the black hole", "blackhole",
])
def test_answer_matching_is_forgiving(given):
    riddle = gq.Riddle("logic", "?", "black hole", alt_answers=("blackhole",))
    assert gq.check_answer(riddle, given)


def test_answer_matching_still_rejects_near_misses():
    riddle = gq.Riddle("logic", "?", "black hole")
    assert not gq.check_answer(riddle, "white hole")
    assert not gq.check_answer(riddle, "hole")


def test_normalise_strips_accents_and_punctuation():
    assert gq.normalise_answer("Supernová!") == "supernova"



def _set_metric(save, metric, value):
    """Force a metric to `value`, following dotted paths."""
    parts = metric.split(".")
    node = save
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    leaf = parts[-1]
    current = node.get(leaf)
    if isinstance(current, (set, frozenset)):
        node[leaf] = {(i, i) for i in range(value)}
    elif isinstance(current, list):
        node[leaf] = [(i, i) for i in range(value)]
    else:
        node[leaf] = value


def _complete(save, quest):
    """Advance a quest's metric to exactly its target."""
    _set_metric(save, quest["metric"], quest["baseline"] + quest["amount"])


# ── Quests ────────────────────────────────────────────────────────────────────

def test_quests_are_generated():
    quests = gq.generate_quests(_save(), 1, date(2026, 1, 1))
    assert len(quests) == gq.QUESTS_PER_DAY
    for quest in quests:
        assert quest["title"]
        assert quest["amount"] >= 1
        assert quest["claimed"] is False


def test_quests_are_stable_within_a_day():
    a = gq.generate_quests(_save(), 5, date(2026, 1, 1))
    b = gq.generate_quests(_save(), 5, date(2026, 1, 1))
    assert [q["title"] for q in a] == [q["title"] for q in b]


def test_quests_rotate_between_days():
    a = gq.generate_quests(_save(), 5, date(2026, 1, 1))
    b = gq.generate_quests(_save(), 5, date(2026, 1, 2))
    assert [q["title"] for q in a] != [q["title"] for q in b]


def test_quests_differ_between_players():
    a = gq.generate_quests(_save(), 1, date(2026, 1, 1))
    b = gq.generate_quests(_save(), 2, date(2026, 1, 1))
    assert [q["title"] for q in a] != [q["title"] for q in b]


def test_no_duplicate_quests_in_a_set():
    quests = gq.generate_quests(_save(), 9, date(2026, 3, 3))
    keys = [q["key"] for q in quests]
    assert len(keys) == len(set(keys))


def test_baseline_prevents_instantly_complete_quests():
    """A quest must mean "N more", not "N total"."""
    save = _save(resources={"crystals": 500, "metals": 500,
                            "energy": 500, "dark_matter": 500},
                 successful_explorations=500, danger_encounters=500,
                 total_credits_earned=99999,
                 discovered={(i, i) for i in range(50)})
    quests = gq.generate_quests(save, 3, date(2026, 2, 2))
    for quest in quests:
        assert not gq.is_complete(save, quest), quest["title"]


def test_progress_tracks_the_metric():
    save = _save()
    for quest in gq.generate_quests(save, 11, date(2026, 4, 4)):
        fresh = _save()
        quest = dict(quest, baseline=gq.read_metric(fresh, quest["metric"]))
        _complete(fresh, quest)
        done, target = gq.quest_progress(fresh, quest)
        assert done == target, quest["title"]
        assert gq.is_complete(fresh, quest), quest["title"]


def test_progress_is_clamped_to_the_target():
    save = _save()
    for quest in gq.generate_quests(save, 12, date(2026, 4, 4)):
        fresh = _save()
        quest = dict(quest, baseline=gq.read_metric(fresh, quest["metric"]))
        _set_metric(fresh, quest["metric"],
                    quest["baseline"] + quest["amount"] * 10)
        done, target = gq.quest_progress(fresh, quest)
        assert done == target, quest["title"]


def test_claim_awards_credits_and_points():
    save = _save()
    quests = gq.refresh_quests(save, 20, date(2026, 5, 5))
    for quest in quests:
        _complete(save, quest)

    before = save["credits"]
    result = gq.claim_rewards(save, 20)
    assert result["quests"] == len(quests)
    assert save["credits"] == before + result["credits"]
    assert result["points"] > 0


def test_rewards_cannot_be_claimed_twice():
    save = _save()
    quests = gq.refresh_quests(save, 21, date(2026, 5, 5))
    for quest in quests:
        _complete(save, quest)

    first = gq.claim_rewards(save, 21)
    second = gq.claim_rewards(save, 21)
    assert first["quests"] > 0
    assert second == {"quests": 0, "credits": 0, "points": 0}


def test_incomplete_quests_are_not_claimed():
    save = _save()
    gq.refresh_quests(save, 22, date(2026, 5, 5))
    assert gq.claim_rewards(save, 22)["quests"] == 0


def test_refresh_regenerates_on_a_new_day():
    save = _save()
    first = [q["title"] for q in gq.refresh_quests(save, 30, date(2026, 6, 1))]
    same = [q["title"] for q in gq.refresh_quests(save, 30, date(2026, 6, 1))]
    next_day = [q["title"] for q in gq.refresh_quests(save, 30, date(2026, 6, 2))]
    assert first == same
    assert first != next_day


def test_refresh_persists_onto_the_save():
    save = _save()
    gq.refresh_quests(save, 31, date(2026, 6, 1))
    assert "quest_state" in save
    assert save["quest_state"]["day"] == "2026-06-01"


# ── Metric reading ────────────────────────────────────────────────────────────

def test_read_metric_handles_dotted_paths():
    save = _save(resources={"crystals": 7})
    assert gq.read_metric(save, "resources.crystals") == 7


def test_read_metric_counts_collections():
    save = _save(discovered={(0, 0), (1, 1), (2, 2)})
    assert gq.read_metric(save, "discovered") == 3


def test_read_metric_handles_missing_and_malformed_paths():
    assert gq.read_metric(_save(), "nope") == 0
    assert gq.read_metric(_save(), "resources.unobtainium") == 0
    assert gq.read_metric(_save(), "credits.nested.deeper") == 0


def test_every_quest_template_metric_resolves():
    """A typo in a metric path would make a quest permanently impossible."""
    save = _save()
    for template in gq.QUEST_TEMPLATES:
        # Must not raise, and must give a usable integer.
        assert isinstance(gq.read_metric(save, template.metric), int)


def test_progress_bar_renders_at_both_extremes():
    assert gq.progress_bar(0, 10).count("█") == 0
    assert gq.progress_bar(10, 10).count("░") == 0
    assert len(gq.progress_bar(3, 10)) == 12


def test_progress_bar_survives_a_zero_target():
    assert gq.progress_bar(0, 0)
