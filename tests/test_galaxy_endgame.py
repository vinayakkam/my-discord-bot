"""After the Void Sentinel: claiming the Ancient Core and its powers."""

import asyncio

import pytest

import galaxy_keeper as gk
from tests.test_galaxy_render import (  # noqa: F401  (fixtures used by name)
    BLOCK, FakeInteraction, UID, _player, assert_clean_grid, assert_fits_discord, click,
    isolated_galaxy, no_wait, rows_of,
)


def _victor(**changes):
    ud = _player(**changes)
    ud["story_state"]["core_retrieved"] = True
    return ud


# ── Binding ───────────────────────────────────────────────────────────────────

def test_core_cannot_be_bound_before_the_sentinel_falls():
    ud = _player()
    assert not gk._bind_core_power(ud, "warp")
    assert ud["core_power"] is None


def test_core_binds_once_and_only_once():
    ud = _victor()
    assert gk._bind_core_power(ud, "warp")
    assert not gk._bind_core_power(ud, "prospector")
    assert ud["core_power"] == "warp"


def test_unknown_power_is_rejected():
    assert not gk._bind_core_power(_victor(), "godmode")


def test_aegis_adds_hull_when_bound():
    ud = _victor(fuel=50, max_fuel=100)
    gk._bind_core_power(ud, "aegis")
    assert ud["max_fuel"] == 100 + gk._AEGIS_HULL_BONUS
    assert ud["fuel"] == 50 + gk._AEGIS_HULL_BONUS


# ── Effects ───────────────────────────────────────────────────────────────────

def _jump_cost(power):
    gk._galaxy.clear()
    ud = _victor(fuel=100, position=[0, 0])
    ud["core_power"] = power
    click(lambda: gk._NavView(UID), "nn", FakeInteraction())
    return 100 - gk._get_user(UID)["fuel"]


def test_warp_lattice_halves_jump_cost(no_wait, monkeypatch):
    monkeypatch.setattr(gk.random, "random", lambda: 0.99)   # no travel event
    normal = _jump_cost(None)
    assert _jump_cost("warp") == max(1, normal // 2)


def _safe_system():
    for x in range(1, 40):
        s = gk.generate_system(x, 7)
        if not s["hazard"] and not s["is_story"]:
            return s
    raise AssertionError("no hazard-free system found")


def _explore_credits(power):
    gk._galaxy.clear()
    ud = _victor(credits=0)
    ud["core_power"] = power
    system = _safe_system()
    ud["position"] = list(system["coords"])
    import random
    random.seed(4)
    it = FakeInteraction()
    click(lambda: gk._ExploreView(UID, system), "explore", it)
    return gk._get_user(UID)["credits"]


def test_prospector_matrix_pays_half_again(no_wait):
    plain = _explore_credits(None)
    rich = _explore_credits("prospector")
    assert rich == plain * 3 // 2


# ── Victory panel and binding animation ───────────────────────────────────────

def test_victory_offers_the_core(no_wait):
    ud = _player(fuel=100, max_fuel=140)
    ud["boss_hp"] = 1
    ud["story_state"]["hints_collected"] = [p["hint"] for p in gk._STORY_PUZZLES]
    it = FakeInteraction()
    click(lambda: gk._BossView(UID), "a1", it)
    final = it.shown[-1][1]
    assert final.title == "🏆 VOID SENTINEL DEFEATED!"
    assert "🔮 Claim the Core" in [f.name for f in final.fields]
    assert_fits_discord(final)


def _claim(key):
    async def go(it):
        view = gk._CoreClaimView(UID)
        await view.choose(it, key)
    it = FakeInteraction()
    asyncio.run(go(it))
    return it


def test_claiming_plays_the_binding_sequence(no_wait):
    _victor()
    it = _claim("prospector")
    hows = [how for how, _ in it.shown]
    assert hows == ["edit"] + ["edit_original"] * len(gk._EXTRACT_STEPS)
    for _, embed in it.shown:
        assert_clean_grid(BLOCK.findall(embed.description)[0])
    assert it.shown[-1][1].title == "💰 Core bound — Prospector Matrix"
    assert gk._get_user(UID)["core_power"] == "prospector"


def test_second_claim_is_refused(no_wait):
    _victor()
    _claim("warp")
    it = _claim("aegis")
    assert [how for how, _ in it.shown] == ["send"]
    assert gk._get_user(UID)["core_power"] == "warp"


@pytest.mark.parametrize("progress", [0.0, 0.35, 0.7, 1.0])
def test_core_art_is_aligned(progress):
    rows = assert_clean_grid(gk._core_art(progress, "aegis" if progress == 1.0 else None))
    assert len(rows[0]) == gk._BOSS_W


def test_core_art_rows_share_one_width():
    assert len({len(r) for r in gk._CORE_ART}) == 1


def test_stats_show_the_bound_power():
    class _Avatar:
        url = "https://cdn.discordapp.com/embed/avatars/0.png"

    class _U:
        display_name = "Tester"
        display_avatar = _Avatar()

    ud = _victor()
    names = [f.name for f in gk._stats_embed(UID, _U()).fields]
    assert "🔮 Core Power" in names
    gk._bind_core_power(ud, "warp")
    field = [f for f in gk._stats_embed(UID, _U()).fields if f.name == "🔮 Core Power"][0]
    assert "Warp Lattice" in field.value
