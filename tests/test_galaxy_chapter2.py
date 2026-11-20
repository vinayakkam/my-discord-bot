"""Chapter 2, "Echoes of the Core": echo puzzles and the Echo Warden."""

import asyncio

import galaxy_keeper as gk
from olit.features import galaxy_quests
from tests.test_galaxy_render import (  # noqa: F401  (fixtures used by name)
    BLOCK, FakeInteraction, UID, _player, assert_clean_grid, assert_fits_discord, click,
    isolated_galaxy, no_wait, rows_of,
)


def _victor(**changes):
    ud = _player(**changes)
    ud["story_state"]["core_retrieved"] = True
    return ud


def _echo(i=0):
    return gk._ECHO_PUZZLES[i]


# ── World ─────────────────────────────────────────────────────────────────────

def test_echo_and_warden_systems_exist():
    for ps in gk._ECHO_PUZZLES:
        system = gk.generate_system(*ps["coords"])
        assert system["chapter"] == 2 and system["is_story"]
        assert system["hint_reward"] == ps["hint"]
        assert_clean_grid(gk._system_art(system))
    warden = gk.generate_system(*gk._WARDEN_COORDS)
    assert warden["is_warden"] and not warden.get("is_core")
    assert_clean_grid(gk._system_art(warden))


def test_echo_riddles_differ_from_chapter_one():
    """Same puzzle type, different coordinates, so a different riddle."""
    ch1 = {(p["puzzle_type"], galaxy_quests.make_riddle(p["puzzle_type"], UID, p["coords"]).answer)
           for p in gk._STORY_PUZZLES}
    for ps in gk._ECHO_PUZZLES:
        riddle = galaxy_quests.make_riddle(ps["puzzle_type"], UID, ps["coords"])
        assert (ps["puzzle_type"], riddle.answer) not in ch1


def test_old_saves_get_the_chapter_two_story_keys():
    ud = _player()
    del ud["story_state"]["echo_hints"]
    del ud["story_state"]["warden_defeated"]
    ud = gk._get_user(UID)
    assert ud["story_state"]["echo_hints"] == []
    assert ud["story_state"]["warden_defeated"] is False


# ── Echo puzzles ──────────────────────────────────────────────────────────────

def _press_solve(ps):
    system = gk.generate_system(*ps["coords"])
    it = FakeInteraction()
    click(lambda: gk._ExploreView(UID, system), "solve_puzzle", it)
    return it


def test_echo_puzzle_is_locked_until_the_sentinel_falls():
    _player()
    it = _press_solve(_echo())
    assert [how for how, _ in it.shown] == ["send"]


def test_echo_puzzle_opens_the_riddle_after_the_sentinel():
    _victor()
    it = _press_solve(_echo())
    assert [how for how, _ in it.shown] == ["modal"]


def _solve(ps):
    system = gk.generate_system(*ps["coords"])
    riddle = galaxy_quests.make_riddle(ps["puzzle_type"], UID, ps["coords"])

    async def go():
        modal = gk._RiddleModal(UID, system, riddle)
        modal.answer_input._value = riddle.answer
        it = FakeInteraction()
        await modal.on_submit(it)
        return it.shown[-1][1]

    return asyncio.run(go())


def test_echoes_go_to_their_own_list_and_unlock_the_warden():
    ud = _victor()
    before = ud["story_state"]["puzzles_solved"]
    for i, ps in enumerate(gk._ECHO_PUZZLES):
        result = _solve(ps)
        assert result.title == "🧩 Puzzle Solved!"
        progress = [f.value for f in result.fields if f.name == "Progress"][0]
        assert progress == f"{i + 1}/{len(gk._ECHO_PUZZLES)} echoes"
    assert len(ud["story_state"]["echo_hints"]) == len(gk._ECHO_PUZZLES)
    assert ud["story_state"]["hints_collected"] == []
    assert ud["story_state"]["puzzles_solved"] == before
    final = [f for f in result.fields if f.name == "🎯 FINAL MISSION UNLOCKED"][0]
    assert str(gk._WARDEN_COORDS) in final.value


# ── The Echo Warden ───────────────────────────────────────────────────────────

def _press_fight():
    system = gk.generate_system(*gk._WARDEN_COORDS)
    it = FakeInteraction()
    click(lambda: gk._ExploreView(UID, system), "fight_boss", it)
    return it


def test_warden_needs_the_core_and_all_echoes():
    _player()
    assert _press_fight().shown[0][1].title == "🔇 Nothing answers"
    ud = _victor()
    assert _press_fight().shown[0][1].title == "⚔️ Echo Warden — Out of Phase"
    assert ud["boss_hp"] is None


def _ready_for_warden(**changes):
    ud = _victor(**changes)
    ud["story_state"]["echo_hints"] = [p["hint"] for p in gk._ECHO_PUZZLES]
    return ud


def test_warden_fight_starts_with_its_own_scene():
    ud = _ready_for_warden(fuel=200, max_fuel=200)
    it = _press_fight()
    emb = it.shown[0][1]
    assert emb.title == "⚔️ BOSS BATTLE — Echo Warden"
    rows = assert_clean_grid(BLOCK.findall(emb.description)[0])
    assert rows[11].startswith("WARDEN")
    assert ud["boss_id"] == "warden" and ud["boss_hp"] == gk._WARDEN["hp_max"]


def test_each_warden_phase_renders(no_wait):
    ud = _ready_for_warden()
    ud["boss_id"] = "warden"
    for hp in (1600, 900, 300):
        ud["boss_hp"] = hp
        idx = gk._phase_index(hp, "warden")
        rows = assert_clean_grid(gk._boss_art(ud, idx, attack=2, hit_ship=True))
        assert len(rows[0]) == gk._BOSS_W
    assert [gk._phase_index(h, "warden") for h in (1600, 900, 300)] == [0, 1, 2]


def test_killing_the_warden_completes_chapter_two(no_wait):
    ud = _ready_for_warden(fuel=200, max_fuel=200)
    ud["boss_id"] = "warden"
    ud["boss_hp"] = 1
    it = FakeInteraction()
    click(lambda: gk._BossView(UID), "a4", it)
    final = it.shown[-1][1]
    assert final.title == "🏆 ECHO WARDEN SILENCED!"
    art = rows_of(BLOCK.findall(final.description)[0])
    assert art[11].startswith("WARDEN"), "victory art must label the Warden's gauge"
    assert ud["story_state"]["warden_defeated"]
    assert {"Echo Breaker", "Warden's Bane"} <= ud["achievements"]
    assert ud["boss_id"] is None
    assert_fits_discord(final)
    # The Sentinel's state is untouched.
    assert ud["story_state"]["core_retrieved"]


def test_warden_turn_names_the_warden(no_wait):
    ud = _ready_for_warden(fuel=2000, max_fuel=2000)
    ud["boss_id"] = "warden"
    ud["boss_hp"] = 1600
    it = FakeInteraction()
    click(lambda: gk._BossView(UID), "a0", it)
    turn = it.shown[-1][1]
    assert "Warden Retaliates" in [f.name for f in turn.fields]
    assert it.shown[0][1].title == "⚔️ BOSS BATTLE — Echo Warden"
