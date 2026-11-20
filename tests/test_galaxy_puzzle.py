"""The 🧩 Solve Puzzle form must show the riddle it asks you to solve."""

import asyncio

import galaxy_keeper as gk
from olit.features import galaxy_quests
from tests.test_galaxy_render import (  # noqa: F401  (fixtures used by name)
    FakeInteraction, UID, _player, isolated_galaxy,
)

PUZZLE = gk._STORY_PUZZLES[0]


def _riddle():
    return galaxy_quests.make_riddle(PUZZLE["puzzle_type"], UID, PUZZLE["coords"])


def _modal():
    system = gk.generate_system(*PUZZLE["coords"])

    async def build():
        return gk._RiddleModal(UID, system, _riddle())   # modals need a running loop

    return asyncio.run(build())


def test_form_shows_the_riddle_above_the_answer_box():
    """It used to be an empty answer box; the riddle only came after a miss."""
    components = _modal().to_dict()["components"]
    assert components[0] == {"type": 10, "content": _riddle().prompt}
    assert components[1]["type"] == 18 and components[1]["label"] == "Your answer"
    assert components[1]["component"]["type"] == 4


def _submit(text):
    modal = _modal()
    modal.answer_input._value = text
    it = FakeInteraction()
    asyncio.run(modal.on_submit(it))
    return it.shown[-1][1]


def test_correct_answer_through_the_labelled_box_solves_it():
    _player()
    result = _submit(_riddle().answer)
    assert result.title == "🧩 Puzzle Solved!"
    assert PUZZLE["hint"] in gk._get_user(UID)["story_state"]["hints_collected"]


def test_wrong_answer_repeats_the_riddle():
    _player()
    result = _submit("definitely not it")
    assert result.title == "❌ Incorrect"
    assert _riddle().prompt in result.description
