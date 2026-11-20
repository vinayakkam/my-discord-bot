"""The shared ANSI canvas used to draw ```ansi code blocks."""

import re

from olit import ansi

ESC = re.compile(r"\x1b\[[0-9;]*m")


def test_render_keeps_every_row_the_same_width():
    c = ansi.Canvas(10, 3)
    c.text(0, 0, "AB", ansi.RED)
    c.put(2, 9, "x", ansi.BLUE)
    rows = [ESC.sub("", line) for line in c.render().split("\n")]
    assert rows == ["AB        ", "          ", "         x"]


def test_codes_only_emitted_on_colour_change():
    line = ansi.ansi_line([("a", ansi.RED), ("b", ansi.RED), (" ", None), ("c", ansi.RED),
                           ("d", ansi.BLUE)])
    assert line == "\x1b[0;31mab c\x1b[0;34md"


def test_put_is_clipped_and_only_empty_respects_filled_cells():
    c = ansi.Canvas(3, 1)
    c.put(0, 5, "x")
    c.put(-1, 0, "x")
    c.put(0, 1, "a")
    c.put(0, 1, "b", only_empty=True)
    assert c.get(0, 1) == "a"
    assert c.get(0, 9) == ""


def test_gauge_fills_and_colours_by_level():
    full = ansi.gauge(10, 10, 4)
    low = ansi.gauge(1, 10, 4)
    assert "".join(ch for ch, _ in full) == "████"
    assert full[0][1] == ansi.GREEN_B
    assert "".join(ch for ch, _ in low) == "░░░░"
    assert ansi.gauge(5, 0, 3) == [("░", ansi.GRAY)] * 3


def test_block_wraps_in_an_ansi_fence():
    assert ansi.block("x") == "```ansi\nx\n```"
