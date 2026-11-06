"""Tests for the shared game view base, win streaks, and trivia timeouts."""

import types

import discord
import pytest

from olit import storage
from olit.features import gameui


@pytest.fixture(autouse=True)
def isolated_streaks(tmp_path, monkeypatch):
    """Keep tests off the real persistent/streaks.json."""
    monkeypatch.setattr(storage, "STREAKS_FILE", str(tmp_path / "streaks.json"))
    monkeypatch.setattr(storage, "streaks", {})
    yield


def _ctx(author_id=1234):
    """A minimal stand-in for commands.Context."""
    return types.SimpleNamespace(
        author=types.SimpleNamespace(
            id=author_id,
            name="Tester",
            display_name="Tester",
            mention=f"<@{author_id}>",
            display_avatar=types.SimpleNamespace(url="https://example.invalid/a.png"),
        ),
        send=None,
    )


# ── GameView basics ───────────────────────────────────────────────────────────

async def test_game_view_disables_every_child():
    view = gameui.GameView(author_id=1, timeout=5)

    class _B(discord.ui.Button):
        pass

    view.add_item(_B(label="one"))
    view.add_item(_B(label="two"))
    assert all(not c.disabled for c in view.children)

    view.disable_all()
    assert all(c.disabled for c in view.children)


async def test_game_view_timeout_without_a_message_is_safe():
    """on_timeout must not raise when nothing was ever sent."""
    view = gameui.GameView(author_id=1, timeout=5)
    await view.on_timeout()  # no message recorded
    assert view.message is None


async def test_public_view_has_no_author_lock():
    view = gameui.GameView(author_id=None, timeout=5)
    assert view.author_id is None


# ── Streak bonus curve ────────────────────────────────────────────────────────

def test_first_win_earns_no_streak_bonus():
    assert gameui.streak_bonus(1) == 0


def test_streak_bonus_grows_then_caps():
    values = [gameui.streak_bonus(n) for n in range(1, 12)]
    assert values == sorted(values), "bonus must never decrease"
    assert max(values) == 5, "bonus should cap"
    assert values[-1] == values[-2] == 5


def test_streak_bonus_handles_zero_and_negative():
    assert gameui.streak_bonus(0) == 0
    assert gameui.streak_bonus(-3) == 0


# ── Streak persistence ────────────────────────────────────────────────────────

def test_bump_streak_counts_up():
    assert storage.bump_streak("rps", 7) == 1
    assert storage.bump_streak("rps", 7) == 2
    assert storage.get_streak("rps", 7) == 2


def test_reset_streak_returns_the_length_it_had():
    storage.bump_streak("rps", 8)
    storage.bump_streak("rps", 8)
    storage.bump_streak("rps", 8)
    assert storage.reset_streak("rps", 8) == 3
    assert storage.get_streak("rps", 8) == 0


def test_reset_streak_on_a_fresh_player_is_zero():
    assert storage.reset_streak("rps", 999) == 0


def test_streaks_are_per_game():
    storage.bump_streak("rps", 9)
    storage.bump_streak("rps", 9)
    storage.bump_streak("coinflip", 9)
    assert storage.get_streak("rps", 9) == 2
    assert storage.get_streak("coinflip", 9) == 1


def test_streaks_are_per_player():
    storage.bump_streak("rps", 10)
    assert storage.get_streak("rps", 11) == 0


def test_streak_keys_are_strings():
    """JSON object keys are strings; an int key would not survive a reload."""
    storage.bump_streak("rps", 12345)
    assert "12345" in storage.streaks["rps"]
    assert 12345 not in storage.streaks["rps"]


def test_streaks_round_trip_to_disk():
    storage.bump_streak("rps", 55)
    storage.bump_streak("rps", 55)
    assert storage.save_streaks()
    reloaded = storage.load_streaks()
    assert reloaded["rps"]["55"] == 2


def test_load_streaks_ignores_malformed_entries(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text('{"rps": {"1": 3}, "junk": "not a dict"}', encoding="utf-8")
    monkeypatch.setattr(storage, "STREAKS_FILE", str(path))
    loaded = storage.load_streaks()
    assert loaded == {"rps": {"1": 3}}


def test_best_streaks_is_ordered():
    storage.streaks["rps"] = {"1": 2, "2": 9, "3": 5}
    ranked = storage.best_streaks("rps")
    assert [uid for uid, _ in ranked] == ["2", "3", "1"]


def test_best_streaks_on_an_unplayed_game():
    assert storage.best_streaks("nonexistent") == []


# ── RPS and coinflip wiring ───────────────────────────────────────────────────

async def test_rps_and_coinflip_extend_gameview():
    import main

    assert issubclass(main.RPSView, gameui.GameView)
    assert issubclass(main.CoinFlipView, gameui.GameView)


async def test_rps_view_is_locked_to_its_creator():
    import main

    view = main.RPSView(_ctx(4242))
    assert view.author_id == 4242


def test_rps_beats_table_is_a_proper_cycle():
    import main

    assert set(main.RPS_BEATS) == {"rock", "paper", "scissors"}
    # Each move beats exactly one other and loses to exactly one.
    beaten = set(main.RPS_BEATS.values())
    assert beaten == set(main.RPS_BEATS)
    for move, loser in main.RPS_BEATS.items():
        assert main.RPS_BEATS[loser] != move, "that would be a two-way tie"


def test_streak_note_is_quiet_below_two():
    import main

    assert main.streak_note("rps", 777) == ""
    storage.bump_streak("rps", 777)
    assert main.streak_note("rps", 777) == ""


def test_streak_note_appears_from_two_wins():
    import main

    storage.bump_streak("rps", 778)
    storage.bump_streak("rps", 778)
    note = main.streak_note("rps", 778)
    assert "2" in note


# ── Trivia timeout reveals the answer ─────────────────────────────────────────

class _FakeMessage:
    def __init__(self):
        self.embeds = []
        self.edits = []

    async def edit(self, **kwargs):
        self.edits.append(kwargs)
        if kwargs.get("embed") is not None:
            self.embeds = [kwargs["embed"]]


def _answer_view(author_id=1):
    import main

    letter_to_option = {"A": "Mars", "B": "Venus", "C": "Jupiter"}
    question = {"question": "Which planet is the Red Planet?", "answer": "Mars"}
    return main.AnswerButtons(
        _ctx(author_id), "A", 2, letter_to_option, question, "easy"
    )


async def test_trivia_timeout_reveals_the_correct_answer():
    view = _answer_view()
    view.message = _FakeMessage()

    await view.on_timeout()

    assert view.message.edits, "timeout did not edit the question message"
    embed = view.message.embeds[0]
    text = (embed.title or "") + (embed.description or "")
    assert "Mars" in text, "the correct answer was not revealed"
    assert "Time" in embed.title


async def test_trivia_timeout_disables_the_buttons():
    view = _answer_view()
    view.message = _FakeMessage()
    await view.on_timeout()
    assert all(c.disabled for c in view.children)


async def test_trivia_timeout_does_nothing_once_answered():
    """A player who answered must not then see a "time's up" message."""
    view = _answer_view()
    view.message = _FakeMessage()
    view.answered = True

    await view.on_timeout()
    assert view.message.edits == []


async def test_trivia_timeout_without_a_message_is_safe():
    view = _answer_view()
    view.message = None
    await view.on_timeout()  # must not raise


async def test_answer_buttons_are_locked_to_the_player():
    view = _answer_view(author_id=555)
    assert view.author_id == 555


async def test_answer_buttons_renders_one_button_per_option():
    view = _answer_view()
    assert len(view.children) == 3


# ── The other retrofitted views ───────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "RPSView", "CoinFlipView", "GuessView", "TriviaDifficultyView",
    "AnswerButtons", "TriviaPlayAgainView", "MathQuizView",
    "UnscrambleView", "DifficultyView", "MissionView",
])
def test_game_views_all_share_the_base(name):
    """Every game view must inherit the author lock and timeout cleanup."""
    import main

    assert issubclass(getattr(main, name), gameui.GameView), name


def test_election_view_is_deliberately_not_locked():
    """Elections are public: everyone in the server votes on one message."""
    import main

    assert not issubclass(main.ElectionVoteView, gameui.GameView)


async def test_difficulty_view_timeout_edits_its_message():
    """Regression: on_timeout built an embed and discarded it."""
    import main

    view = main.DifficultyView(_ctx())
    view.message = _FakeMessage()
    await view.on_timeout()
    assert view.message.edits, "the dropdown never showed a timeout notice"
    assert "Timeout" in view.message.embeds[0].title


async def test_mission_view_has_no_timeout():
    """A mission should stay playable indefinitely."""
    import main

    view = main.MissionView(1)
    assert view.timeout is None
