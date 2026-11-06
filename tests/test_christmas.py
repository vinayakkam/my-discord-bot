"""Tests for the multi-round Grinch game."""

import asyncio

import discord
import pytest
from discord.ext import commands

from olit import config
from olit.features import christmas


@pytest.fixture(autouse=True)
def isolated_stats(tmp_path, monkeypatch):
    """Keep the real persistent/grinch_stats.json out of the tests."""
    monkeypatch.setattr(christmas, "STATS_FILE", str(tmp_path / "grinch.json"))
    monkeypatch.setattr(christmas, "_stats", {})
    yield


# ── Round construction ────────────────────────────────────────────────────────

def test_round_config_is_consistent():
    """One decoy count per round timer, or zip() would silently drop rounds."""
    assert len(christmas.ROUND_TIMERS) == len(christmas.ROUND_DECOYS)
    assert len(christmas.ROUND_TIMERS) >= 1


def test_timers_shrink_and_decoys_grow():
    """The game is supposed to get harder, not easier."""
    timers = list(christmas.ROUND_TIMERS)
    decoys = list(christmas.ROUND_DECOYS)
    assert timers == sorted(timers, reverse=True)
    assert decoys == sorted(decoys)


def test_enough_decoy_labels_for_the_hardest_round():
    assert len(christmas.DECOY_LABELS) >= max(christmas.ROUND_DECOYS)


async def test_each_round_has_exactly_one_real_button():
    for index, (timeout, decoys) in enumerate(
        zip(christmas.ROUND_TIMERS, christmas.ROUND_DECOYS), start=1
    ):
        view = christmas._RoundView(index, timeout, decoys)
        real = [b for b in view.children if isinstance(b, christmas._RealButton)]
        fake = [b for b in view.children if isinstance(b, christmas._DecoyButton)]
        assert len(real) == 1, f"round {index} has {len(real)} real buttons"
        assert len(fake) == decoys
        assert len(view.children) <= 25, "exceeds Discord's component limit"


async def test_decoy_labels_are_unique_within_a_round():
    view = christmas._RoundView(3, 3.0, max(christmas.ROUND_DECOYS))
    labels = [b.label for b in view.children]
    assert len(labels) == len(set(labels))


async def test_real_button_position_varies():
    """The real button is shuffled, so it must not always sit first."""
    positions = set()
    for _ in range(40):
        view = christmas._RoundView(3, 3.0, 3)
        for i, button in enumerate(view.children):
            if isinstance(button, christmas._RealButton):
                positions.add(i)
    assert len(positions) > 1, "real button never moves"


# ── Scoring ───────────────────────────────────────────────────────────────────

async def test_fast_click_scores_more_than_slow_click():
    fast = christmas._RoundView(1, 5.0, 1)
    slow = christmas._RoundView(1, 5.0, 1)
    slow.started_at -= 5.0  # used the whole timer
    assert christmas.score_round(fast, 1) > christmas.score_round(slow, 1)


async def test_slow_click_still_scores_the_base():
    view = christmas._RoundView(1, 5.0, 1)
    view.started_at -= 5.0
    assert christmas.score_round(view, 1) == christmas.BASE_ROUND_POINTS


async def test_streak_increases_the_score():
    view = christmas._RoundView(1, 5.0, 1)
    one = christmas.score_round(view, 1)
    three = christmas.score_round(view, 3)
    assert three == one + christmas.STREAK_BONUS * 2


async def test_speed_bonus_is_capped():
    view = christmas._RoundView(1, 5.0, 1)
    assert christmas.score_round(view, 1) <= (
        christmas.BASE_ROUND_POINTS + christmas.MAX_SPEED_BONUS
    )


async def test_time_left_fraction_is_bounded():
    view = christmas._RoundView(1, 5.0, 1)
    assert 0.0 <= view.time_left_fraction() <= 1.0
    view.started_at -= 100.0
    assert view.time_left_fraction() == 0.0


# ── Stats bookkeeping ─────────────────────────────────────────────────────────

def test_record_round_win_tracks_personal_best():
    christmas.record_round_win(1, 900, 3)
    assert christmas.get_record(1)["best_ms"] == 900
    christmas.record_round_win(1, 400, 3)
    assert christmas.get_record(1)["best_ms"] == 400
    # A slower time must not overwrite the best.
    christmas.record_round_win(1, 1200, 3)
    assert christmas.get_record(1)["best_ms"] == 400
    assert christmas.get_record(1)["rounds_won"] == 3


def test_record_round_win_accumulates_points():
    christmas.record_round_win(2, 500, 4)
    christmas.record_round_win(2, 500, 6)
    assert christmas.get_record(2)["total_points"] == 10


def test_record_game_finished_credits_only_the_winner():
    christmas.record_game_finished({10, 11}, winner_id=10)
    assert christmas.get_record(10)["games_won"] == 1
    assert christmas.get_record(11)["games_won"] == 0
    # Everyone who took part gets a game played.
    assert christmas.get_record(10)["games_played"] == 1
    assert christmas.get_record(11)["games_played"] == 1


def test_record_game_finished_handles_nobody_winning():
    christmas.record_game_finished({20}, winner_id=None)
    assert christmas.get_record(20)["games_played"] == 1
    assert christmas.get_record(20)["games_won"] == 0


def test_stats_round_trip_to_disk(tmp_path, monkeypatch):
    path = tmp_path / "rt.json"
    monkeypatch.setattr(christmas, "STATS_FILE", str(path))
    monkeypatch.setattr(christmas, "_stats", {})
    christmas.record_round_win(99, 321, 5)
    assert christmas.save_stats()
    reloaded = christmas.load_stats()
    assert reloaded["99"]["best_ms"] == 321


def test_user_ids_are_stored_as_strings():
    """JSON object keys are always strings; mixing types loses records."""
    christmas.record_round_win(12345, 500, 2)
    assert "12345" in christmas._stats
    assert 12345 not in christmas._stats


# ── Embeds ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("decoys", [0, 1, 3])
def test_round_embed_within_limits(decoys):
    embed = christmas.build_round_embed(1, 3, 5.0, decoys)
    assert len(embed) <= 6000
    assert embed.title


def test_final_embed_handles_no_winner():
    embed = christmas.build_final_embed({}, {}, {}, 3)
    assert len(embed) <= 6000
    assert "Grinch" in embed.title


def test_final_embed_ranks_by_rounds_won():
    embed = christmas.build_final_embed(
        {5: 1, 7: 2}, {5: "Ann", 7: "Bob"}, {5: 800, 7: 410}, 3
    )
    # Bob won more rounds, so Bob is named as the overall winner.
    assert "Bob" in embed.description
    board = embed.fields[0].value
    assert board.index("Bob") < board.index("Ann")


def test_leaderboard_handles_empty_stats():
    bot = commands.Bot(command_prefix="!", intents=config.build_intents())
    embed = christmas.build_leaderboard_embed(bot, None)
    assert "Nobody has played" in embed.description


def test_leaderboard_skips_malformed_keys():
    christmas._stats["not-an-id"] = {"games_won": 5, "rounds_won": 5}
    bot = commands.Bot(command_prefix="!", intents=config.build_intents())
    embed = christmas.build_leaderboard_embed(bot, None)
    # Must not raise, and must not list the junk entry.
    assert "not-an-id" not in (embed.description or "")


def test_leaderboard_orders_by_wins_then_rounds():
    christmas._stats.update({
        "1": {"games_won": 1, "rounds_won": 9, "total_points": 1, "games_played": 3},
        "2": {"games_won": 3, "rounds_won": 1, "total_points": 1, "games_played": 3},
    })
    bot = commands.Bot(command_prefix="!", intents=config.build_intents())
    embed = christmas.build_leaderboard_embed(bot, None)
    text = embed.description
    # Player 2 has more game wins, so ranks above player 1.
    assert text.index("User 2") < text.index("User 1")


# ── Registration ──────────────────────────────────────────────────────────────

def test_setup_registers_the_commands():
    bot = commands.Bot(command_prefix="!", intents=config.build_intents())
    christmas.setup(bot)
    for name in ("merrychristmas", "grinchboard", "christmashelp"):
        assert bot.get_command(name) is not None, f"!{name} missing"
    assert bot.get_command("grinchstats") is bot.get_command("grinchboard")
