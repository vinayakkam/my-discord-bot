"""Rendering and landing-burn checks for the Mechzilla booster catch.

The field is shown inside an ```ansi code block, so the grid only lines up if
every row has the same number of single-width characters once the ANSI colour
codes are stripped. Emoji are double-width in Discord and used to push rows
out of line.
"""

import random
import re
import unicodedata

import pytest

import booster_catch as bc

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def visible(field: str) -> list:
    """The field's rows as the player sees them, without colour codes."""
    return [ANSI.sub("", line) for line in field.split("\n")]


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


BURN = dict(engine_on=True, _burn_total=bc.AUTO_BURN_DURATION)

SCENES = {
    "entry": dict(pos_y=4.0, vel_y=3.8, wind_accel=0.45, anim_frame=3),
    "sonic_boom": dict(pos_y=7.0, vel_y=3.1, anim_frame=10, _sonic_boom_frame=8),
    "ignition": dict(pos_y=11.5, vel_y=1.9, thrust_timer=2.4, **BURN),
    "full_thrust": dict(pos_y=12.0, vel_y=1.2, thrust_timer=1.4, **BURN),
    "shutdown": dict(pos_y=12.8, vel_y=0.7, thrust_timer=0.2, **BURN),
    "smoke": dict(pos_y=13.0, anim_frame=13, _burn_end_frame=10),
    "burn_near_pad": dict(pos_y=16.5, vel_y=1.0, thrust_timer=0.8, **BURN),
    "catch_window": dict(pos_y=15.0, vel_y=0.7, vel_x=0.3),
    "arms_moving": dict(pos_y=9.0, arm_center=19.0, anim_frame=1),
    "caught": dict(pos_y=16.0, state="over", success=True, catch_window_open=True),
    "crashed": dict(pos_y=19.6, vel_y=3.0, state="over", success=False, pos_x=22.0),
    "wall_left": dict(pos_x=float(bc.WALL_L), pos_y=10.0),
    "wall_right": dict(pos_x=float(bc.WALL_R), pos_y=10.0, arm_center=bc.ARM_CENTER_MAX),
}


# ── Layout ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(SCENES))
def test_every_row_has_the_same_width(name):
    rows = visible(_game(**SCENES[name]).make_field())
    assert len(rows) == bc._CANVAS_H
    assert len({len(row) for row in rows}) == 1


@pytest.mark.parametrize("name", sorted(SCENES))
def test_no_double_width_glyphs(name):
    text = "".join(visible(_game(**SCENES[name]).make_field()))
    wide = [c for c in text if unicodedata.east_asian_width(c) in ("W", "F")
            or ord(c) >= 0x1F000 or c == "️" or (ord(c) < 32 and c != "\n")]
    assert wide == []


@pytest.mark.parametrize("name", sorted(SCENES))
def test_field_is_coloured_and_fits_the_embed(name):
    g = _game(**SCENES[name])
    field = g.make_field()
    assert ANSI.search(field), "the field should carry ANSI colour codes"
    embed = g.make_embed("status")
    assert embed.description.startswith("```ansi\n")
    assert len(embed.description) <= 4096


def test_star_field_uses_only_single_width_glyphs():
    for row in bc._make_star_field(1):
        for ch in row:
            assert ch == "" or ch in bc._STAR_CHARS


def test_each_altitude_label_appears_once():
    rows = visible(_game(pos_y=2.0).make_field())
    labels = [row[:2].strip() for row in rows if row[:2].strip()]
    assert labels == ["15", "10", "6", "3"]


def test_booster_is_seven_rows_tall_and_five_wide():
    rows = visible(_game(pos_y=5.0).make_field())
    body = [row for row in rows if "███" in row]
    assert len(body) == 5          # dome, fin row and four tank rows share ███
    assert any("╪███╪" in row or "╫███╫" in row for row in rows)


def test_booster_reaches_the_ground_exactly_at_impact():
    g = _game(pos_y=bc.CRASH_Y)
    assert g._booster_top_row() + bc._BOOSTER_H - 1 == bc._GROUND_ROW


# ── Burn animation ────────────────────────────────────────────────────────────

def _below_engines(g, depth):
    rows = visible(g.make_field())
    col = 3 + int(g.pos_x)  # 3 = label width + border
    return rows[g._booster_top_row() + bc._BOOSTER_H - 1 + depth][col]


def test_burn_phases_draw_differently():
    ignition = visible(_game(**SCENES["ignition"]).make_field())
    full = visible(_game(**SCENES["full_thrust"]).make_field())
    shutdown = visible(_game(**SCENES["shutdown"]).make_field())
    assert any("*" in row for row in ignition), "ignition sprays sparks"
    assert sum(row.count("▓") for row in full) > sum(row.count("▓") for row in shutdown)
    assert len({tuple(ignition), tuple(full), tuple(shutdown)}) == 3


def test_full_thrust_plume_is_long():
    g = _game(**SCENES["full_thrust"])
    assert _below_engines(g, 1) == "█"
    assert _below_engines(g, 6) != " "


def test_smoke_lingers_after_cutoff_then_clears():
    smoky = "".join(visible(_game(**SCENES["smoke"]).make_field()))
    clear = "".join(visible(_game(pos_y=13.0, anim_frame=40, _burn_end_frame=10).make_field()))
    assert smoky.count("░") > clear.count("░")


def test_caught_booster_hangs_in_the_closed_arms():
    rows = visible(_game(**SCENES["caught"]).make_field())
    arm_row = rows[bc._ARM_ROW]
    assert "███" in arm_row
    assert "┄" not in arm_row


def test_crash_shows_wreckage_not_the_booster():
    text = "\n".join(visible(_game(**SCENES["crashed"]).make_field()))
    assert "▀▄▀▄▀▄▀" in text
    assert "███" not in text


def test_rendering_does_not_change_the_physics_state():
    g = _game(**SCENES["full_thrust"])
    before = (g.pos_x, g.pos_y, g.vel_x, g.vel_y, g.fuel_kg, g.state, g.arm_center)
    g.make_embed("status")
    assert (g.pos_x, g.pos_y, g.vel_x, g.vel_y, g.fuel_kg, g.state, g.arm_center) == before


# ── Automatic landing burn ────────────────────────────────────────────────────

def _descend(seed, until):
    random.seed(seed)
    g = bc.BoosterCatchGame(1, "pilot")
    ticks = 0
    while g.state != "over" and not until(g) and ticks < 2000:
        g.update_physics(bc.PHYS_DT)
        ticks += 1
    return g


def test_auto_burn_ignites_once_at_its_altitude():
    g = _descend(5, lambda g: g.engine_on)
    assert g.engine_on
    assert g.altitude <= bc.AUTO_BURN_ALT_KM
    assert g.altitude > bc.AUTO_BURN_ALT_KM - 1.0
    assert g._auto_burn_active and g.redraw_requested
    assert any("AUTO LANDING BURN" in line for line in g.timeline)
    assert g.manual_burns == 0, "the auto burn must not count toward the burn penalty"


def test_auto_burn_runs_for_its_full_duration_then_logs_completion():
    g = _descend(5, lambda g: g.engine_on)
    burn_ticks = 0
    while g.engine_on:
        g.update_physics(bc.PHYS_DT)
        burn_ticks += 1
    assert burn_ticks * bc.PHYS_DT >= bc.AUTO_BURN_DURATION - bc.PHYS_DT
    assert not g._auto_burn_active
    assert g._burn_end_frame == g.anim_frame
    assert any("Landing burn complete" in line for line in g.timeline)
    assert sum("AUTO LANDING BURN" in line for line in g.timeline) == 1


def test_auto_burn_is_skipped_without_fuel():
    random.seed(5)
    g = bc.BoosterCatchGame(1, "pilot")
    g.fuel_kg = 0.0
    while g.state != "over":
        g.update_physics(bc.PHYS_DT)
        assert not g.engine_on
    assert any("No fuel left for the landing burn" in line for line in g.timeline)


def test_auto_burn_slows_the_catch_window_speed():
    """Averaged over many descents it lands in the 'good' band, not 'perfect'."""
    speeds = []
    for seed in range(40):
        g = _descend(seed, lambda g: g.catch_window_open)
        speeds.append(g.vel_y)
    mean = sum(speeds) / len(speeds)
    assert bc.PERFECT_VY <= mean < bc.GOOD_VY


def test_manual_thrust_sets_its_own_burn_length():
    g = _game(pos_y=5.0)
    g.action_thrust()
    assert g._burn_total == bc.THRUST_PULSE_DURATION
    assert g.redraw_requested
    assert g.manual_burns == 1


def test_a_full_descent_renders_every_frame():
    """Run the real physics to impact, rendering each tick like the game loop."""
    random.seed(11)
    g = bc.BoosterCatchGame(1, "pilot")
    ticks = 0
    while g.state != "over" and ticks < 2000:
        g.update_physics(bc.PHYS_DT)
        rows = visible(g.make_field())
        assert len({len(row) for row in rows}) == 1
        assert len(g.make_embed("status").description) <= 4096
        ticks += 1
    assert g.state == "over"
    assert "▀▄▀▄▀▄▀" in "\n".join(visible(g.make_field()))


# ── Throttle: burns slow the booster but never make it climb ─────────────────

def test_auto_burn_never_makes_the_booster_climb():
    for seed in range(60):
        random.seed(seed)
        g = bc.BoosterCatchGame(1, "pilot")
        while g.state != "over":
            g.update_physics(bc.PHYS_DT)
            assert g.vel_y > -0.01, f"seed {seed}: booster climbed during descent"


def test_auto_burn_throttles_down_as_it_slows():
    g = _descend(5, lambda g: g.engine_on)
    first = g.throttle
    while g.engine_on:
        g.update_physics(bc.PHYS_DT)
        if g.engine_on:
            last = g.throttle
    assert last < first
    assert abs(g.vel_y - bc.AUTO_BURN_TARGET_VY) < 0.3


def test_mashing_thrust_can_hover_but_never_climb():
    for seed in range(30):
        random.seed(seed)
        g = bc.BoosterCatchGame(1, "pilot")
        while g.state != "over" and (g.fuel_kg > 0 or g.engine_on):
            if g.thrust_timer == 0:
                g.action_thrust()
            g.update_physics(bc.PHYS_DT)
            assert g.vel_y > -0.01


def test_plume_length_follows_the_throttle():
    def flame_cells(throttle):
        g = _game(**SCENES["full_thrust"], throttle=throttle)
        return sum(row.count("▓") + row.count("▒") + row.count("◊")
                   for row in visible(g.make_field()))

    assert flame_cells(1.0) > flame_cells(0.2)


# ── Tower and arms ────────────────────────────────────────────────────────────

def test_tower_stands_clear_of_the_playfield():
    rows = visible(_game(pos_y=8.0).make_field())
    tower_cols = [row[3 + bc._TOWER_COL:3 + bc._TOWER_COL + 3] for row in rows]
    assert "▗▄▖" in tower_cols                 # cap
    assert "▟█▙" == tower_cols[bc._GROUND_ROW]  # base
    assert any(c == "╠═╣" for c in tower_cols)  # floors
    assert "█▓█" == tower_cols[bc._ARM_ROW]     # carriage at arm height


def test_arms_have_catch_pads_either_side_of_the_gap():
    g = _game(pos_y=5.0)
    arm_row = visible(g.make_field())[bc._ARM_ROW]
    left_pad = 3 + int(g.arm_left) + 3
    right_pad = 3 + int(g.arm_right) - 3
    assert arm_row[left_pad] == "█" and arm_row[right_pad] == "█"
    assert set(arm_row[left_pad + 1:right_pad]) == {"─"}   # rear arm through the gap
