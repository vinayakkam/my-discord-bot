"""Tests for the generated space trivia bank.

A malformed generated question is worse than a missing one: it either has no
correct button or two identical ones. These tests check every question the
generators can produce, not a sample.
"""

import random
import re

import pytest

from olit.features import trivia_bank as tb

ALL_GENERATORS = [
    gen for gens in tb.GENERATORS.values() for gen in gens
]


@pytest.fixture
def bank():
    return tb.build_bank(rng=random.Random(1234))


# ── Structural validity ───────────────────────────────────────────────────────

@pytest.mark.parametrize("generator", ALL_GENERATORS,
                         ids=lambda g: g.__name__)
def test_generator_output_is_all_valid(generator):
    questions = generator(random.Random(99))
    assert questions, f"{generator.__name__} produced nothing"
    for question in questions:
        assert tb.is_valid(question), f"invalid: {question}"


@pytest.mark.parametrize("generator", ALL_GENERATORS,
                         ids=lambda g: g.__name__)
def test_answer_is_never_also_a_distractor(generator):
    """The answer must appear exactly once among the options."""
    for question in generator(random.Random(5)):
        assert question["options"].count(question["answer"]) == 1


def test_every_question_has_three_distinct_options(bank):
    for difficulty, questions in bank.items():
        for question in questions:
            assert len(question["options"]) == 3, question
            assert len(set(question["options"])) == 3, question


def test_answer_is_always_among_the_options(bank):
    for questions in bank.values():
        for question in questions:
            assert question["answer"] in question["options"], question


def test_no_duplicate_prompts_within_a_difficulty(bank):
    for difficulty, questions in bank.items():
        prompts = [q["question"] for q in questions]
        duplicates = {p for p in prompts if prompts.count(p) > 1}
        assert not duplicates, f"{difficulty}: {duplicates}"


# ── Volume ────────────────────────────────────────────────────────────────────

def test_bank_is_much_larger_than_the_curated_seed(bank):
    """The whole point: 60 hand-written questions was too few."""
    total = sum(tb.bank_sizes(bank).values())
    assert total > 200, f"only {total} questions generated"


def test_every_difficulty_has_plenty(bank):
    for difficulty, count in tb.bank_sizes(bank).items():
        assert count >= 40, f"{difficulty} has only {count}"


def test_curated_questions_are_kept(bank):
    curated = {
        "easy": [{"question": "Unique seed question?",
                  "options": ["A", "B", "C"], "answer": "A"}],
    }
    built = tb.build_bank(curated=curated, rng=random.Random(1))
    prompts = [q["question"] for q in built["easy"]]
    assert "Unique seed question?" in prompts


def test_invalid_curated_questions_are_dropped():
    curated = {
        "easy": [
            {"question": "No answer in options?",
             "options": ["A", "B", "C"], "answer": "D"},
            {"question": "Too few options?", "options": ["A"], "answer": "A"},
            {"question": "Duplicate options?",
             "options": ["A", "A", "B"], "answer": "A"},
        ],
    }
    built = tb.build_bank(curated=curated, rng=random.Random(1))
    prompts = [q["question"] for q in built["easy"]]
    for bad in ("No answer in options?", "Too few options?",
                "Duplicate options?"):
        assert bad not in prompts


# ── Factual correctness of the generated content ──────────────────────────────

def test_comparison_options_match_the_planets_named(bank):
    """A "largest of X, Y, Z" question must offer exactly X, Y and Z.

    An earlier version drew distractors from all planets, so the prompt named
    one trio while the buttons showed different planets entirely.
    """
    pattern = re.compile(r"the (largest|smallest): (.+)\?$")
    checked = 0
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            named = [n.strip() for n in match.group(2).split(",")]
            assert sorted(named) == sorted(question["options"]), question
            checked += 1
    assert checked > 0, "no comparison questions found to check"


def test_comparison_answers_are_actually_correct(bank):
    pattern = re.compile(r"the (largest|smallest): (.+)\?$")
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            named = [n.strip() for n in match.group(2).split(",")]
            key = lambda n: tb.PLANETS[n]["diameter_km"]
            expected = (max(named, key=key) if match.group(1) == "largest"
                        else min(named, key=key))
            assert question["answer"] == expected, question


def test_moon_parent_answers_are_correct(bank):
    pattern = re.compile(r"Which body does (.+) orbit\?")
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            moon = match.group(1)
            expected = next(p for p, moons in tb.MOONS.items() if moon in moons)
            assert question["answer"] == expected, question


def test_mission_agency_answers_are_correct(bank):
    pattern = re.compile(r"Which agency launched (.+)\?")
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            mission = match.group(1)
            assert question["answer"] == tb.MISSIONS[mission]["agency"], question


def test_mission_year_answers_are_correct(bank):
    pattern = re.compile(r"In which year did (.+) launch\?")
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            mission = match.group(1)
            assert question["answer"] == str(tb.MISSIONS[mission]["year"]), question


def test_star_constellation_answers_are_correct(bank):
    pattern = re.compile(r"In which constellation would you find (.+)\?")
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            assert question["answer"] == tb.STARS[match.group(1)], question


def test_rocket_operator_answers_are_correct(bank):
    pattern = re.compile(r"Which organisation operates the (.+) rocket\?")
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            assert question["answer"] == tb.ROCKETS[match.group(1)], question


def test_planet_order_answers_are_correct(bank):
    pattern = re.compile(r"Which planet is the (\w+) from the Sun\?")
    reverse = {v: k for k, v in tb.ORDINALS.items()}
    for questions in bank.values():
        for question in questions:
            match = pattern.search(question["question"])
            if not match:
                continue
            order = reverse[match.group(1)]
            expected = next(n for n, d in tb.PLANETS.items()
                            if d["order"] == order)
            assert question["answer"] == expected, question


def test_moonless_planet_questions_only_offer_planets_with_moons(bank):
    for questions in bank.values():
        for question in questions:
            if "has no moons at all" not in question["question"]:
                continue
            assert tb.PLANETS[question["answer"]]["moons"] == 0
            for option in question["options"]:
                if option != question["answer"]:
                    assert tb.PLANETS[option]["moons"] > 0, question


def test_ringless_planet_questions_only_offer_ringed_distractors(bank):
    for questions in bank.values():
        for question in questions:
            if "has no ring system" not in question["question"]:
                continue
            assert tb.PLANETS[question["answer"]]["rings"] is False
            for option in question["options"]:
                if option != question["answer"]:
                    assert tb.PLANETS[option]["rings"] is True, question


# ── Source data sanity ────────────────────────────────────────────────────────

def test_planet_orders_are_one_to_eight():
    orders = sorted(d["order"] for d in tb.PLANETS.values())
    assert orders == list(range(1, 9))


def test_no_moon_is_listed_under_two_parents():
    seen = {}
    for parent, moons in tb.MOONS.items():
        for moon in moons:
            assert moon not in seen, f"{moon} under {seen[moon]} and {parent}"
            seen[moon] = parent


def test_every_mission_agency_is_a_known_agency():
    for name, data in tb.MISSIONS.items():
        assert data["agency"] in tb.AGENCIES, f"{name}: {data['agency']}"


def test_is_valid_rejects_malformed_input():
    assert not tb.is_valid(None)
    assert not tb.is_valid({})
    assert not tb.is_valid({"question": "q", "options": ["a", "b"], "answer": "a"})
    assert not tb.is_valid({"question": "q", "options": ["a", "b", "c"],
                            "answer": "z"})
    assert not tb.is_valid({"question": "", "options": ["a", "b", "c"],
                            "answer": "a"})
    assert tb.is_valid({"question": "q", "options": ["a", "b", "c"],
                        "answer": "a"})
