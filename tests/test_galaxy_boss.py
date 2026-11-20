"""Void Sentinel boss fight: phase selection and the battle scene."""

import pytest

import galaxy_keeper as gk
from tests.test_galaxy_render import (  # noqa: F401  (fixtures used by name)
    BLOCK, FakeInteraction, UID, _player, assert_clean_grid, assert_fits_discord, click,
    isolated_galaxy, no_wait, rows_of,
)

PHASES = gk._SENTINEL["phases"]
HP_MAX = gk._SENTINEL["hp_max"]


@pytest.mark.parametrize("hp, index", [
    (HP_MAX, 0),
    (int(HP_MAX * 0.66), 0),
    (int(HP_MAX * 0.65), 1),
    (int(HP_MAX * 0.31), 1),
    (int(HP_MAX * 0.30), 2),
    (1, 2),
])
def test_phase_follows_remaining_hp(hp, index):
    """Phases 2 and 3 used to be unreachable: phase 1 always won."""
    assert gk._boss_phase(hp) is PHASES[index]


# ── Battle scene art ──────────────────────────────────────────────────────────

def test_every_sprite_is_17_by_7():
    for sprite in gk._SENTINEL_SPRITES + [gk._SENTINEL_DEFEATED]:
        assert len(sprite) == 7
        assert {len(row) for row in sprite} == {17}


def _fighter(hp=HP_MAX, fuel=100):
    ud = _player(fuel=fuel, max_fuel=140)
    ud["boss_hp"] = hp
    ud["story_state"]["hints_collected"] = [p["hint"] for p in gk._STORY_PUZZLES]
    return ud


@pytest.mark.parametrize("phase", [0, 1, 2])
def test_each_phase_scene_is_aligned(phase):
    ud = _fighter()
    rows = assert_clean_grid(gk._boss_art(ud, phase))
    assert len(rows[0]) == gk._BOSS_W
    assert "╱▲╲" in rows[gk._SHIP_ROW]
    assert rows[11].startswith("SENTINEL") and rows[12].startswith("HULL")


@pytest.mark.parametrize("attack", range(len(gk._PLAYER_ATTACKS)))
def test_each_weapon_draws_its_beam(attack):
    ud = _fighter()
    rows = rows_of(gk._boss_art(ud, 0, attack=attack, crit=True))
    beam = gk._ATTACK_BEAMS[attack][0]
    assert all(rows[r][gk._BOSS_CENTRE] == beam for r in range(7, gk._SHIP_ROW))
    assert "CRIT!" in rows[8]


def test_return_fire_shield_victory_and_wreck_frames():
    ud = _fighter()
    hit = rows_of(gk._boss_art(ud, 1, hit_ship=True))
    assert hit[8][gk._BOSS_CENTRE] == "┃"
    shield = rows_of(gk._boss_art(ud, 1, shielded=True))
    assert "╭───╮" in shield[gk._SHIP_ROW - 1]
    won = rows_of(gk._boss_art(ud, 2, defeated=True))
    assert "▒▓█████▓▒" in won[1]
    lost = rows_of(gk._boss_art(ud, 2, hit_ship=True, ship_lost=True))
    assert "x╳x" in lost[gk._SHIP_ROW]


def test_gauges_show_hp_and_hull():
    ud = _fighter(hp=420, fuel=35)
    rows = rows_of(gk._boss_art(ud, 1))
    assert rows[11].rstrip().endswith("420")
    assert rows[12].rstrip().endswith("35")


# ── Turns, animated ───────────────────────────────────────────────────────────

def test_attack_shows_fire_frame_then_the_turn(no_wait):
    _fighter()
    it = FakeInteraction()
    click(lambda: gk._BossView(UID), "a0", it)
    assert [how for how, _ in it.shown] == ["edit", "edit_original"]
    frame, turn = it.shown[0][1], it.shown[1][1]
    assert_clean_grid(BLOCK.findall(frame.description)[0])
    assert turn.title.startswith("⚔️ Turn 1")
    assert_clean_grid(BLOCK.findall(turn.description)[0])
    assert [f.name for f in turn.fields][:1] == ["Your Action"]
    assert_fits_discord(turn)


def test_defend_shows_the_shield(no_wait):
    _fighter(fuel=60)
    it = FakeInteraction()
    click(lambda: gk._BossView(UID), "defend", it)
    frame_rows = rows_of(BLOCK.findall(it.shown[0][1].description)[0])
    assert "╭───╮" in frame_rows[gk._SHIP_ROW - 1]


def test_killing_blow_shows_the_explosion(no_wait):
    _fighter(hp=1)
    it = FakeInteraction()
    click(lambda: gk._BossView(UID), "a1", it)
    final = it.shown[-1][1]
    assert final.title == "🏆 VOID SENTINEL DEFEATED!"
    assert "▒▓█████▓▒" in "\n".join(rows_of(BLOCK.findall(final.description)[0]))
    assert gk._get_user(UID)["story_state"]["core_retrieved"]


def test_losing_shows_the_wreck_with_an_empty_hull(no_wait):
    _fighter(fuel=1)
    it = FakeInteraction()
    click(lambda: gk._BossView(UID), "a2", it)
    final = it.shown[-1][1]
    assert final.title == "💀 SHIP DESTROYED"
    rows = rows_of(BLOCK.findall(final.description)[0])
    assert "x╳x" in rows[gk._SHIP_ROW]
    assert rows[12].rstrip().endswith(" 0")
    assert gk._get_user(UID)["fuel"] == 10        # escape pod reset still happens


def test_opening_screen_has_the_scene():
    import asyncio

    async def build():
        return gk._boss_embed(UID)   # creates a view, which needs a running loop

    _fighter()
    emb, _view = asyncio.run(build())
    assert_clean_grid(BLOCK.findall(emb.description)[0])
    assert [f.name for f in emb.fields] == ["Turn"]
    assert_fits_discord(emb)
