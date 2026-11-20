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
