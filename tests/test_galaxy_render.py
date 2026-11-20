"""Rendering checks for the galaxy explorer's ```ansi screens.

The art lives in code blocks, so every row must be the same width once the
colour codes are stripped, and no glyph may be double-width (emoji are, which
is what made the old emoji map drift).
"""

import re
import unicodedata

import pytest

import galaxy_keeper as gk

ESC = re.compile(r"\x1b\[[0-9;]*m")
BLOCK = re.compile(r"```ansi\n(.*?)\n```", re.S)
UID = 777


@pytest.fixture(autouse=True)
def isolated_galaxy(tmp_path, monkeypatch):
    """Point every galaxy save file at a temp dir and start from no players."""
    monkeypatch.setattr(gk, "_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(gk, "GALAXY_FILE", str(tmp_path / "galaxy.json"))
    monkeypatch.setattr(gk, "WORLD_FILE", str(tmp_path / "world.json"))
    monkeypatch.setattr(gk, "SCORES_FILE", str(tmp_path / "scores.json"))
    monkeypatch.setattr(gk, "_galaxy", {})
    monkeypatch.setattr(gk, "_world", {})
    monkeypatch.setattr(gk, "_add_score", None)


def rows_of(art: str) -> list:
    return [ESC.sub("", line) for line in art.split("\n")]


def assert_clean_grid(art: str) -> list:
    rows = rows_of(art)
    assert len({len(r) for r in rows}) == 1, "rows differ in width"
    wide = [c for r in rows for c in r
            if unicodedata.east_asian_width(c) in ("W", "F") or ord(c) >= 0x1F000]
    assert wide == [], f"double-width glyphs: {wide}"
    return rows


def ansi_blocks(embed) -> list:
    text = (embed.description or "") + "".join(f.value for f in embed.fields)
    return BLOCK.findall(text)


def assert_fits_discord(embed):
    assert len(embed.description or "") <= 4096
    assert all(len(f.value) <= 1024 for f in embed.fields)
    assert len(embed) <= 6000


def _player(**changes):
    ud = gk._get_user(UID)
    ud.update(changes)
    return ud


# ── Map ───────────────────────────────────────────────────────────────────────

def test_map_is_an_aligned_coloured_grid():
    ud = _player(position=[3, -4])
    ud["discovered"].update({(4, -4), (3, -3)})
    rows = assert_clean_grid(gk._map_art(ud))
    assert len(rows[0]) == gk._MAP_W
    assert rows[0].startswith("╭") and rows[0].endswith("╮")


def test_ship_sits_in_the_centre_cell():
    ud = _player(position=[10, 10])
    rows = rows_of(gk._map_art(ud))
    half = gk._MAP_SIZE // 2
    centre_row = rows[1 + half]
    col = 1 + half * gk._MAP_CELL
    assert centre_row[col:col + 3] == "[▲]"


def test_explored_systems_and_base_are_marked():
    ud = _player(position=[1, 0])
    ud["discovered"].add((2, 0))
    rows = rows_of(gk._map_art(ud))
    half = gk._MAP_SIZE // 2
    row = rows[1 + half]
    east = 1 + (half + 1) * gk._MAP_CELL + 1
    west = 1 + (half - 1) * gk._MAP_CELL + 1
    assert row[east] in "■@✶Ω"
    assert row[west] == "⌂"           # (0, 0) is home base


def test_map_hud_shows_fuel_credits_and_systems():
    ud = _player(fuel=30, max_fuel=120, credits=12345)
    text = "\n".join(rows_of(gk._map_art(ud)))
    assert "30/120" in text and "12,345" in text and "SYS 0" in text


def test_map_embed_fits_discord_limits():
    _player(position=[0, 0])
    emb = gk._map_embed(UID)
    assert ansi_blocks(emb)
    assert_fits_discord(emb)


# ── Fake interaction for driving button callbacks ─────────────────────────────

class FakeInteraction:
    """Records every embed a callback shows, in order, without Discord."""

    class _User:
        id = UID
        display_name = "Tester"

    def __init__(self):
        self.user = self._User()
        self.shown = []        # (how, embed) in the order the player sees them
        outer = self

        class _Response:
            async def edit_message(self, embed=None, **kw):
                outer.shown.append(("edit", embed))

            async def send_message(self, content=None, embed=None, **kw):
                outer.shown.append(("send", embed))

            async def send_modal(self, modal):
                outer.shown.append(("modal", None))

        class _Followup:
            async def send(self, content=None, embed=None, **kw):
                outer.shown.append(("followup", embed))

        self.response = _Response()
        self.followup = _Followup()

    async def edit_original_response(self, embed=None, **kw):
        self.shown.append(("edit_original", embed))


@pytest.fixture
def no_wait(monkeypatch):
    """Animations sleep between frames; skip the waiting in tests."""
    async def instant(_seconds):
        return None
    monkeypatch.setattr(gk.asyncio, "sleep", instant)


def click(make_view, button: str, interaction) -> None:
    """Build the view inside an event loop (discord.py requires one) and
    press one of its buttons."""
    import asyncio

    async def go():
        await getattr(make_view(), button).callback(interaction)

    asyncio.run(go())


# ── Warp ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dx, dy", sorted(gk._WARP_SHAPES))
def test_warp_frame_is_aligned_in_every_direction(dx, dy):
    ud = _player(position=[dx * 5, dy * 5])
    rows = assert_clean_grid(gk._warp_art(ud, dx, dy))
    ship = gk._WARP_SHAPES[(dx, dy)][0]
    assert ship in rows[1 + gk._MAP_SIZE // 2]


def test_moving_shows_the_warp_then_the_map(no_wait, monkeypatch):
    _player(position=[0, 0], fuel=50)
    monkeypatch.setattr(gk.random, "random", lambda: 0.99)   # no travel event
    it = FakeInteraction()
    click(lambda: gk._NavView(UID), "nn", it)
    assert [how for how, _ in it.shown] == ["edit", "edit_original"]
    assert it.shown[0][1].title.startswith("🌌 Warping")
    assert it.shown[1][1].title.startswith("🌌 Galaxy Map")
    assert gk._get_user(UID)["position"] == [0, 1]


def test_travel_event_still_arrives_after_the_map(no_wait, monkeypatch):
    _player(position=[0, 0], fuel=50)
    monkeypatch.setattr(gk.random, "random", lambda: 0.01)   # force an event
    it = FakeInteraction()
    click(lambda: gk._NavView(UID), "ee", it)
    assert [how for how, _ in it.shown] == ["edit", "edit_original", "followup"]
    assert it.shown[2][1].title.startswith("🌌 Travel Event")


def test_move_without_fuel_does_not_warp(no_wait):
    _player(position=[0, 0], fuel=0)
    it = FakeInteraction()
    click(lambda: gk._NavView(UID), "nn", it)
    assert [how for how, _ in it.shown] == ["send"]
    assert gk._get_user(UID)["position"] == [0, 0]


# ── Scan ──────────────────────────────────────────────────────────────────────

def _systems():
    """A spread of real generated systems plus the two story specials."""
    found = [gk.generate_system(x, y) for x in range(-6, 7, 3) for y in range(-6, 7, 3)]
    found.append(gk.generate_system(*gk._STORY_PUZZLES[0]["coords"]))
    found.append(gk.generate_system(*gk._CORE_COORDS))
    return found


@pytest.mark.parametrize("reveal", [0.0, 0.34, 0.67, 1.0])
def test_system_diagram_is_aligned_at_every_scan_step(reveal):
    for system in _systems():
        rows = assert_clean_grid(gk._system_art(system, reveal))
        assert len(rows[0]) == gk._SYS_W


def test_every_star_type_has_a_sprite():
    names = {s[0] for s in gk._STAR_TYPES} | {"Ancient Binary", "Dying Supergiant"}
    assert names <= set(gk._STAR_ART)


def test_full_scan_shows_every_planet_and_the_threat():
    system = max(_systems(), key=lambda s: len(s["planets"]))
    rows = rows_of(gk._system_art(system))
    orbit = rows[1][6:]          # skip the star sprite
    glyphs = sum(orbit.count(g) for g in "•●O♦○Ω■")
    assert glyphs == len(system["planets"])
    assert system["danger"].upper()[:12] in rows[4]


def test_partial_scan_masks_planets_and_threat():
    system = max(_systems(), key=lambda s: len(s["planets"]))
    rows = rows_of(gk._system_art(system, 0.34))
    assert "?" in rows[1]
    assert system["danger"].upper() not in rows[4]
    assert "34%" in rows[6]


def test_scan_button_sweeps_then_shows_the_scan(no_wait):
    _player(position=[4, 4])
    it = FakeInteraction()
    click(lambda: gk._NavView(UID), "scan", it)
    hows = [how for how, _ in it.shown]
    assert hows == ["send"] + ["edit_original"] * len(gk._SCAN_STEPS)
    assert all(e.title.startswith("📡 Deep Scan in progress") for _, e in it.shown[:-1])
    assert "Deep Scan —" in it.shown[-1][1].title
    for _, embed in it.shown:
        assert_fits_discord(embed)


# ── Explore ───────────────────────────────────────────────────────────────────

def _safe_system():
    for x in range(1, 40):
        s = gk.generate_system(x, 3)
        if not s["hazard"] and not s["is_story"]:
            return s
    raise AssertionError("no hazard-free system found")


def _hazard_system():
    for x in range(1, 80):
        s = gk.generate_system(x, 5)
        if s["hazard"] and not s["is_story"]:
            return s
    raise AssertionError("no hazard system found")


def test_explore_shows_probes_then_the_report(no_wait):
    system = _safe_system()
    _player(position=list(system["coords"]))
    it = FakeInteraction()
    click(lambda: gk._ExploreView(UID, system), "explore", it)
    assert [how for how, _ in it.shown] == ["edit", "edit_original"]
    probes, result = it.shown[0][1], it.shown[1][1]
    assert probes.title.startswith("🛰️ Probes deployed")
    assert result.title == "🎉 Exploration Complete!"
    report = BLOCK.findall(result.description)[0]
    rows = assert_clean_grid(report)
    assert "COMPLETE" in rows[0] and "PTS" in rows[1]
    assert tuple(system["coords"]) in gk._get_user(UID)["discovered"]
    for _, embed in it.shown:
        assert_fits_discord(embed)


def test_hazard_shows_probes_then_the_alert(no_wait, monkeypatch):
    system = _hazard_system()
    _player(position=list(system["coords"]), fuel=80)
    # First roll < 0.3 triggers the hazard check; the second must beat the shield.
    rolls = iter([0.1, 0.99])
    monkeypatch.setattr(gk.random, "random", lambda: next(rolls))
    it = FakeInteraction()
    click(lambda: gk._ExploreView(UID, system), "explore", it)
    assert [how for how, _ in it.shown] == ["edit", "edit_original"]
    alert = it.shown[1][1]
    assert alert.title == "💥 Hazard!"
    rows = assert_clean_grid(BLOCK.findall(alert.description)[0])
    assert "ABORTED" in rows[1]
    assert tuple(system["coords"]) not in gk._get_user(UID)["discovered"]


def test_report_art_fits_big_numbers():
    art = gk._report_art(123456, 61728, {"crystals": 99, "metals": 999, "energy": 99,
                                         "dark_matter": 9}, 13)
    rows = assert_clean_grid(art)
    assert len(rows[0]) == gk._SYS_W


# ── Shipyard and profile ──────────────────────────────────────────────────────

def test_shipyard_lists_every_upgrade_with_pips_and_costs():
    ud = _player(credits=600)
    ud["upgrades"]["fuel_tank"] = 5            # maxed
    ud["upgrades"]["fuel_efficiency"] = 1
    rows = assert_clean_grid(gk._shipyard_art(ud, "fuel_efficiency"))
    body = rows[2:]
    assert len(body) == len(gk._SHIP_UPGRADES)
    assert body[0].startswith("  FUEL TANK") and body[0].endswith("MAX")
    assert body[1].startswith("► FUEL EFFICIENCY")
    assert "■□□□□" in body[1] and body[1].endswith("1,000")


def test_shipyard_cost_colour_shows_what_you_can_afford():
    ud = _player(credits=450)
    art = gk._shipyard_art(ud, "fuel_tank")
    lines = art.split("\n")
    assert "\x1b[0;33m400" in lines[2]          # fuel tank 400: affordable, yellow
    assert "\x1b[0;31m500" in lines[3]          # efficiency 500: too dear, red


@pytest.mark.parametrize("done", [0, 9, 26, 999, 5000])
def test_profile_panel_is_aligned_at_every_rank(done):
    ud = _player(successful_explorations=done)
    ud["resources"] = {"crystals": 12345, "metals": 67890, "energy": 1234, "dark_matter": 567}
    rows = assert_clean_grid(gk._profile_art(ud))
    assert rows[1].startswith("RANK")
    if done >= gk._RANKS[-1][0]:
        assert "MAX RANK" in rows[1]
    assert "CRYSTAL 12345" in "\n".join(rows) and "DARK 567" in "\n".join(rows)


def test_profile_story_pips_follow_hints():
    ud = _player()
    ud["story_state"]["hints_collected"] = [p["hint"] for p in gk._STORY_PUZZLES[:2]]
    row = rows_of(gk._profile_art(ud))[2]
    assert row[7:14] == "■ ■ □ □"[:7]
    assert "SEALED" in row


def test_shipyard_and_stats_embeds_fit_discord():
    import asyncio

    class _Avatar:
        url = "https://cdn.discordapp.com/embed/avatars/0.png"

    class _U:
        display_name = "Tester"
        display_avatar = _Avatar()

    _player(credits=99999)

    async def build():
        return gk._ShipyardView(UID)._embed()   # views need a running loop

    for emb in (asyncio.run(build()), gk._stats_embed(UID, _U())):
        assert_clean_grid(BLOCK.findall(emb.description)[0])
        assert_fits_discord(emb)
