"""The Core-powered base: modules, production, collecting and the panel."""

import asyncio

import pytest

import galaxy_keeper as gk
from tests.test_galaxy_render import (  # noqa: F401  (fixtures used by name)
    BLOCK, FakeInteraction, UID, _player, assert_clean_grid, assert_fits_discord,
    isolated_galaxy, rows_of,
)

HOUR = 3600.0
T0 = 1_000_000.0


def _owner(**changes):
    ud = _player(**{"credits": 1_000_000, **changes})
    ud["story_state"]["core_retrieved"] = True
    ud["resources"] = {"crystals": 500, "metals": 500, "energy": 500, "dark_matter": 0}
    return ud


# ── Rules ─────────────────────────────────────────────────────────────────────

def test_base_is_locked_without_the_core():
    ud = _player(credits=1_000_000)
    ok, message = gk._base_upgrade(ud, "reactor", T0)
    assert not ok and "Core" in message
    assert ud["base"]["reactor"] == 0


def test_upgrade_charges_credits_and_resource_scaled_by_level():
    ud = _owner()
    gk._base_upgrade(ud, "reactor", T0)
    assert ud["credits"] == 1_000_000 - 2000 and ud["resources"]["energy"] == 480
    gk._base_upgrade(ud, "reactor", T0)
    assert ud["credits"] == 1_000_000 - 2000 - 4000 and ud["resources"]["energy"] == 440
    assert ud["base"]["reactor"] == 2


def test_upgrade_refused_when_short_or_maxed():
    ud = _owner(credits=100)
    ok, message = gk._base_upgrade(ud, "refinery", T0)
    assert not ok and "Need" in message
    ud = _owner()
    for _ in range(gk._BASE_MODULES["hangar"]["max"]):
        assert gk._base_upgrade(ud, "hangar", T0)[0]
    ok, message = gk._base_upgrade(ud, "hangar", T0)
    assert not ok and "max level" in message


def test_hangar_adds_hull():
    ud = _owner(fuel=50, max_fuel=100)
    gk._base_upgrade(ud, "hangar", T0)
    assert ud["max_fuel"] == 100 + gk._HANGAR_HULL and ud["fuel"] == 50 + gk._HANGAR_HULL


def test_production_accrues_and_caps():
    ud = _owner()
    gk._base_upgrade(ud, "reactor", T0)
    gk._base_upgrade(ud, "refinery", T0)
    assert gk._base_pending(ud, T0 + 2 * HOUR) == {"credits": 80, "crystals": 2, "metals": 4}
    capped = gk._base_pending(ud, T0 + 100 * HOUR)
    assert capped["credits"] == 40 * gk._BASE_CAP_HOURS


def test_collect_banks_output_and_restarts_the_clock():
    ud = _owner()
    gk._base_upgrade(ud, "reactor", T0)
    credits = ud["credits"]
    got = gk._base_collect(ud, T0 + 3 * HOUR)
    assert got["credits"] == 120 and ud["credits"] == credits + 120
    assert gk._base_pending(ud, T0 + 3 * HOUR)["credits"] == 0


def test_upgrading_banks_output_at_the_old_rate_first():
    ud = _owner()
    gk._base_upgrade(ud, "reactor", T0)
    credits = ud["credits"]
    gk._base_upgrade(ud, "reactor", T0 + 5 * HOUR)       # level 2 costs 4,000
    assert ud["credits"] == credits + 5 * 40 - 4000


def test_nothing_accrues_before_the_first_module():
    ud = _owner()
    assert gk._base_pending(ud, T0 + 50 * HOUR) == {"credits": 0, "crystals": 0, "metals": 0}


def test_old_saves_get_a_base():
    ud = _player()
    del ud["base"]
    assert gk._get_user(UID)["base"]["reactor"] == 0


# ── Panel ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("levels", [(0, 0, 0), (1, 0, 0), (5, 3, 3), (2, 1, 0)])
def test_base_art_is_aligned_at_any_build(levels):
    ud = _owner()
    ud["base"].update(reactor=levels[0], refinery=levels[1], hangar=levels[2], last_collect=T0)
    rows = assert_clean_grid(gk._base_art(ud, T0 + HOUR))
    assert len(rows[0]) == gk._PANEL_W
    assert "CORE" in rows[1] and "HANGAR" in rows[6]


def test_power_lines_light_up_for_built_modules():
    ud = _owner()
    dark = rows_of(gk._base_art(ud, T0))[2]
    ud["base"]["reactor"] = 1
    lit = rows_of(gk._base_art(ud, T0))[2]
    assert dark[10:14] == "────" and lit[10:14] == "════"


def _press(make, *args):
    async def go():
        view = gk._BaseView(UID)
        it = FakeInteraction()
        await make(view)(it, *args)
        return it
    return asyncio.run(go())


def test_upgrade_button_refreshes_the_panel():
    _owner()
    it = _press(lambda v: v.upgrade, "reactor")
    emb = it.shown[0][1]
    assert it.shown[0][0] == "edit"
    assert "upgraded to level 1" in emb.fields[-1].value
    assert_clean_grid(BLOCK.findall(emb.description)[0])
    assert_fits_discord(emb)


def test_collect_button_reports_what_it_banked():
    ud = _owner()
    gk._base_upgrade(ud, "reactor", gk._now_ts() - 2 * HOUR)
    it = _press(lambda v: v.collect)
    assert "Collected **80** credits" in it.shown[0][1].fields[-1].value
