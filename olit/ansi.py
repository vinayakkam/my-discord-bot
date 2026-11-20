"""A small character canvas for Discord ```ansi code blocks.

Discord colours text inside an ```ansi block using ANSI escape codes from an
8-colour palette. The grid only lines up if every glyph is single-width, so
callers should stick to ASCII, box drawing and block elements, never emoji.

    canvas = Canvas(20, 3)
    canvas.text(1, 2, "HELLO", YELLOW_B)
    embed.description = block(canvas.render())
"""

from typing import List, Optional, Tuple

# Discord's ANSI palette, as "style;colour" codes. The _B variants are bold.
GRAY, RED, GREEN, YELLOW = "0;30", "0;31", "0;32", "0;33"
BLUE, PINK, CYAN, WHITE = "0;34", "0;35", "0;36", "0;37"
RED_B, GREEN_B, YELLOW_B = "1;31", "1;32", "1;33"
BLUE_B, PINK_B, CYAN_B, WHITE_B = "1;34", "1;35", "1;36", "1;37"


def ansi_line(cells: List[Tuple[str, Optional[str]]]) -> str:
    """Join (char, colour) cells, emitting an escape code only on a change.

    Spaces carry no visible colour, so they never trigger a code. That keeps
    frames small: embed descriptions are capped at 4096 characters and field
    values at 1024.
    """
    parts, current = [], None
    for ch, colour in cells:
        if ch != " " and colour != current:
            parts.append(f"\x1b[{colour or '0'}m")
            current = colour
        parts.append(ch)
    return "".join(parts)


def block(text: str) -> str:
    """Wrap rendered canvas text in an ansi code block."""
    return f"```ansi\n{text}\n```"


class Canvas:
    """A fixed-size grid of (char, colour) cells."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.chars = [[" "] * width for _ in range(height)]
        self.colours: List[List[Optional[str]]] = [[None] * width for _ in range(height)]

    def put(self, row: int, col: int, ch: str, colour: Optional[str] = None,
            only_empty: bool = False) -> None:
        """Set one cell, clipped to the canvas. only_empty skips filled cells."""
        if 0 <= row < self.height and 0 <= col < self.width:
            if only_empty and self.chars[row][col] != " ":
                return
            self.chars[row][col] = ch
            self.colours[row][col] = colour

    def text(self, row: int, col: int, s: str, colour: Optional[str] = None) -> None:
        """Write a string left to right; spaces in it are written too."""
        for i, ch in enumerate(s):
            self.put(row, col + i, ch, colour)

    def get(self, row: int, col: int) -> str:
        return self.chars[row][col] if 0 <= row < self.height and 0 <= col < self.width else ""

    def render(self) -> str:
        """The canvas as ANSI text, one line per row, trailing spaces kept."""
        return "\n".join(
            ansi_line(list(zip(self.chars[r], self.colours[r]))) for r in range(self.height))


def gauge(value: float, maximum: float, width: int,
          colour: Optional[str] = None) -> List[Tuple[str, Optional[str]]]:
    """A filled bar as cells: █ for the filled part, ░ for the rest.

    Without an explicit colour it goes green above 60%, yellow above 30% and
    red below, like a fuel or hull gauge.
    """
    frac = 0.0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    filled = int(round(frac * width))
    if colour is None:
        colour = GREEN_B if frac > 0.6 else YELLOW_B if frac > 0.3 else RED_B
    return [("█", colour)] * filled + [("░", GRAY)] * (width - filled)


def put_cells(canvas: Canvas, row: int, col: int,
              cells: List[Tuple[str, Optional[str]]]) -> None:
    """Write pre-coloured cells (such as a gauge) onto a canvas."""
    for i, (ch, colour) in enumerate(cells):
        canvas.put(row, col + i, ch, colour)
