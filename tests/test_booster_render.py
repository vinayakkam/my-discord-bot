"""Rendering checks for the Mechzilla booster catch field.

The field is shown inside a ``` code block, so the grid only lines up if every
row has the same number of single-width characters. Emoji are double-width in
Discord and used to push rows out of line.
"""

import random
import unicodedata

import pytest

import booster_catch as bc


def _game(**state):
    random.seed(3)
    g = bc.BoosterCatchGame(1, "pilot")
    g.pos_x = g.arm_center = g._last_arm_center = 15.0
    for key, value in state.items():
        setattr(g, key, value)
    if g.pos_y >= bc.CATCH_ZONE_Y and g.state != "over":
        g.catch_window_open = True
        g.state = "catch_zone"
    return g


SCENES = {
    "entry": dict(pos_y=4.0, vel_y=3.8, wind_accel=0.45, anim_frame=3),
    "sonic_boom": dict(pos_y=7.0, vel_y=3.1, anim_frame=10, _sonic_boom_frame=8),
    "burn": dict(pos_y=11.0, vel_y=1.4, engine_on=True, thrust_timer=0.8),
    "burn_near_pad": dict(pos_y=16.0, vel_y=1.0, engine_on=True, thrust_timer=0.8),
    "catch_window": dict(pos_y=15.0, vel_y=0.7, vel_x=0.3),
    "arms_moving": dict(pos_y=9.0, arm_center=19.0),
    "caught": dict(pos_y=16.0, state="over", success=True, catch_window_open=True),
    "crashed": dict(pos_y=19.6, vel_y=3.0, state="over", success=False, pos_x=22.0),
    "wall_left": dict(pos_x=float(bc.WALL_L), pos_y=10.0),
    "wall_right": dict(pos_x=float(bc.WALL_R), pos_y=10.0, arm_center=bc.ARM_CENTER_MAX),
}


@pytest.mark.parametrize("name", sorted(SCENES))
def test_every_row_has_the_same_width(name):
    lines = _game(**SCENES[name]).make_field().split("\n")
    assert len(lines) == bc._CANVAS_H
    assert len({len(line) for line in lines}) == 1


@pytest.mark.parametrize("name", sorted(SCENES))
def test_no_double_width_glyphs(name):
    field = _game(**SCENES[name]).make_field()
    wide = [c for c in field if unicodedata.east_asian_width(c) in ("W", "F")
            or ord(c) >= 0x1F000 or c == "️"]
    assert wide == []


def test_star_field_uses_only_single_width_glyphs():
    for row in bc._make_star_field(1):
        for ch in row:
            assert ch == "" or ch in bc._STAR_CHARS


def test_each_altitude_label_appears_once():
    field = _game(pos_y=2.0).make_field()
    labels = [line[:2].strip() for line in field.split("\n") if line[:2].strip()]
    assert labels == ["15", "10", "6", "3"]


def test_booster_reaches_the_ground_exactly_at_impact():
    g = _game(pos_y=bc.CRASH_Y)
    assert g._booster_top_row() + 3 == bc._GROUND_ROW


def test_engine_burn_draws_a_plume_below_the_engines():
    g = _game(**SCENES["burn"])
    lines = g.make_field().split("\n")
    col = 3 + int(g.pos_x)  # 3 = label width + border
    below = lines[g._booster_top_row() + 4][col]
    assert below == "█"


def test_caught_booster_hangs_in_the_closed_arms():
    g = _game(**SCENES["caught"])
    arm_row = g.make_field().split("\n")[bc._ARM_ROW]
    assert "▐█▌" in arm_row
    assert "┄" not in arm_row


def test_crash_shows_wreckage_not_the_booster():
    field = _game(**SCENES["crashed"]).make_field()
    assert "▀▄▀▄▀▄▀" in field
    assert "▐█▌" not in field


def test_rendering_does_not_change_the_physics_state():
    g = _game(**SCENES["burn"])
    before = (g.pos_x, g.pos_y, g.vel_x, g.vel_y, g.fuel_kg, g.state, g.arm_center)
    g.make_embed("status")
    assert (g.pos_x, g.pos_y, g.vel_x, g.vel_y, g.fuel_kg, g.state, g.arm_center) == before


def test_embed_stays_inside_discords_description_limit():
    for scene in SCENES.values():
        embed = _game(**scene).make_embed("status")
        assert len(embed.description) <= 4096


def test_a_full_descent_renders_every_frame():
    """Run the real physics to impact, rendering each tick like the game loop."""
    random.seed(11)
    g = bc.BoosterCatchGame(1, "pilot")
    ticks = 0
    while g.state != "over" and ticks < 2000:
        g.update_physics(bc.PHYS_DT)
        field = g.make_field()
        assert len({len(line) for line in field.split("\n")}) == 1
        ticks += 1
    assert g.state == "over"
    assert "▀▄▀▄▀▄▀" in g.make_field()
