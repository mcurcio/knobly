"""Draws knobly's pixel-art logo on a grid and writes it as SVG: one <path> per colour, one rectangle per run.

The logo is the word "knobly" with a synth knob, seen from the side, standing in for the "o"; the icon is the same
knob on its own, larger. The SVGs in docs/site/pages/assets/ are this script's output, committed. Change the logo
here, then run `python3 tools/logo.py` from the repository root (standard library only).
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "site" / "pages" / "assets"

INK = "#1c1a2e"  # outlines, and the letters on a light background
CREAM = "#ffe9cc"  # the letters on a dark background
BODY = "#ff8a3d"  # the knob's lit side
SHADE = "#d9541e"  # the knob's shaded side, and the grooves on its lit side
GROOVE = "#a83c12"  # the grooves on its shaded side
TOP = "#ffad5c"  # the knob's flat top
LIGHT = "#ffc27a"  # the top's lit edge
POINTER = "#ffffff"
BASE, BASE_DARK, BASE_LIGHT = "#59528c", "#3b3660", "#8a82c8"  # the disc the knob stands on
LOW, HIGH = "#3ddc84", "#ff3d6e"  # the scale's end marks

Grid = dict[tuple[int, int], str]


def ellipse(grid: Grid, cx: float, cy: float, rx: float, ry: float, colour) -> None:
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                grid[(x, y)] = colour(x)


def knob(cx: float, top: int, rx: float, ry: float, height: int, base_rx: float, base_h: int, marks: bool) -> Grid:
    """A knurled knob seen from slightly above: a flat disc under it, a tall grooved side, a flat top with a pointer
    line, and a dark outline around it all."""
    g: Grid = {}
    bottom = top + height
    # the disc
    ellipse(g, cx, bottom + base_h + 1, base_rx, ry + 1, lambda x: BASE_DARK)
    for y in range(bottom, bottom + base_h + 1):
        for x in range(int(cx - base_rx), int(cx + base_rx) + 1):
            g[(x, y)] = BASE_DARK if x > cx + 2 else BASE
    ellipse(g, cx, bottom, base_rx, ry + 1, lambda x: BASE_LIGHT if x < cx - 3 else BASE)
    if marks:  # the low and high ends of the scale, on the disc's top face
        g[(round(cx - base_rx + 2), bottom - 1)] = LOW
        g[(round(cx + base_rx - 2), bottom - 1)] = HIGH
    # the side, knurled: every other column is a groove
    ellipse(g, cx, bottom - 1, rx, ry, lambda x: SHADE)
    left = int(cx - rx)
    for y in range(top, bottom):
        for x in range(left, int(cx + rx) + 1):
            shaded = x > cx + rx / 3
            groove = (x - left) % 2 == 1
            g[(x, y)] = (GROOVE if shaded else SHADE) if groove else (SHADE if shaded else BODY)
    # the top, and the pointer from its centre to the front-left rim
    ellipse(g, cx, top, rx, ry, lambda x: LIGHT if x < cx - rx / 2 else TOP)
    steps = int(rx)
    for t in range(steps):
        f = t / (steps - 1)
        g[(round(cx - f * rx * 0.6), round(top + f * (ry - 0.5)))] = POINTER
    # the outline
    for x, y in list(g):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            g.setdefault((x + dx, y + dy), INK)
    return g


# A 5x7 lowercase pixel font ("y" has a 2-row descender), drawn at SCALE pixels per cell.
GLYPHS = {
    "k": ["X....", "X....", "X..X.", "X.X..", "XX...", "X.X..", "X..X."],
    "n": [".....", ".....", "XXXX.", "X...X", "X...X", "X...X", "X...X"],
    "b": ["X....", "X....", "XXXX.", "X...X", "X...X", "X...X", "XXXX."],
    "l": ["XX.", ".X.", ".X.", ".X.", ".X.", ".X.", ".XX"],
    "y": [".....", ".....", "X...X", "X...X", "X...X", ".XXXX", "....X", "X...X", ".XXX."],
}
SCALE = 3
KNOB_CELLS = 7  # the knob's slot is wider than a letter's 5 cells


def wordmark(fill: str, shadow: str) -> Grid:
    """The word, each letter with a one-pixel drop shadow, and the knob as its "o"."""
    g: Grid = {}
    x0 = 0
    for ch in "knobly":
        if ch == "o":
            cx = x0 + KNOB_CELLS * SCALE / 2 - 0.5
            g.update(knob(cx, 8, rx=6, ry=2.5, height=8, base_rx=9, base_h=1, marks=False))
            x0 += (KNOB_CELLS + 1) * SCALE
            continue
        rows = GLYPHS[ch]
        for gy, row in enumerate(rows):
            for gx, cell in enumerate(row):
                if cell == "X":
                    for sy in range(SCALE):
                        for sx in range(SCALE):
                            x, y = x0 + gx * SCALE + sx, gy * SCALE + sy
                            g[(x, y)] = fill
                            g.setdefault((x + 1, y + 1), shadow)
        x0 += (len(rows[0]) + 1) * SCALE
    return g


def svg(grid: Grid) -> str:
    """The grid as SVG, trimmed to what is drawn plus a one-pixel margin."""
    x0 = min(x for x, _ in grid) - 1
    y0 = min(y for _, y in grid) - 1
    w = max(x for x, _ in grid) - x0 + 2
    h = max(y for _, y in grid) - y0 + 2
    by_colour: dict[str, list[tuple[int, int]]] = {}
    for (x, y), c in grid.items():
        by_colour.setdefault(c, []).append((x - x0, y - y0))
    paths = []
    for c, pts in by_colour.items():
        pts.sort(key=lambda p: (p[1], p[0]))
        d = []
        i = 0
        while i < len(pts):  # a run along a row becomes one rectangle
            x, y = pts[i]
            j = i
            while j + 1 < len(pts) and pts[j + 1] == (pts[j][0] + 1, y):
                j += 1
            d.append(f"M{x} {y}h{j - i + 1}v1h-{j - i + 1}z")
            i = j + 1
        paths.append(f'<path fill="{c}" d="{"".join(d)}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w * 8}" height="{h * 8}" '
        f'shape-rendering="crispEdges">' + "".join(paths) + "</svg>\n"
    )


def main() -> None:
    (OUT / "icon.svg").write_text(svg(knob(15.5, 9, rx=7, ry=3, height=11, base_rx=12, base_h=2, marks=True)))
    # logo.svg is for light backgrounds, logo-dark.svg for dark ones (the README picks one with <picture>)
    (OUT / "logo.svg").write_text(svg(wordmark(INK, BODY)))
    (OUT / "logo-dark.svg").write_text(svg(wordmark(CREAM, SHADE)))


if __name__ == "__main__":
    main()
