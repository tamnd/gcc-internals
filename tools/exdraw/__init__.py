"""Excalidraw scenes, written by a script rather than dragged around by hand.

The generated diagrams in this project come from `gxmanim` and are drawn from a real dump,
which is the right way to show data. This is for the other kind of picture: the one that
explains an idea, where there is no dump to draw from and somebody has to decide what goes
where.

Those still should not be hand drawn. A hand drawn `.excalidraw` is a wall of JSON with
random seeds in it, so a one word change to a label produces a diff nobody can read, and two
diagrams drawn a month apart never quite match. A script fixes both: the diff is the line you
changed, and the house style is a default rather than a habit.

The output is a real Excalidraw scene. Open it at excalidraw.com, or in the VS Code plugin,
and you can move things around, which is the point of using the format at all. If you do that
and want to keep it, change the script and regenerate, or the next build undoes your work.

    from tools import exdraw

    scene = exdraw.Scene("what a phi is for")
    top = scene.box(40, 40, 200, 80, "bb 2\\ns_3 = 0", fill=exdraw.BLUE)
    join = scene.box(40, 200, 200, 80, "bb 4\\n# s_1 = PHI <...>", fill=exdraw.YELLOW)
    scene.arrow(top, join, "s is s_3 here")
    Path("phi.excalidraw").write_text(scene.document())
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

#: Excalidraw's own palette. Using the defaults means a diagram somebody opens and edits by
#: hand picks the same colours off the toolbar as the script did.
INK = "#1e1e1e"
GREY = "#868e96"
BLUE = ("#1971c2", "#a5d8ff")
GREEN = ("#2f9e44", "#b2f2bb")
RED = ("#e03131", "#ffc9c9")
YELLOW = ("#f08c00", "#ffec99")
PLAIN = (INK, "transparent")

#: `3` is Excalidraw's code font. Everything here is either an IR fragment or a label on one,
#: so a monospaced font is the honest choice and it makes the width estimate below work.
CODE = 3
HAND = 1

#: How wide a character is, as a fraction of the font size, in the code font. Excalidraw
#: measures text properly when it loads a scene, so this only has to be close enough that
#: nothing overlaps before the first render.
WIDTH = 0.62
LINE = 1.25


def measure(text: str, size: int) -> tuple[float, float]:
    """Roughly how much room a run of text needs, in pixels."""
    lines = text.split("\n")
    return max(len(line) for line in lines) * size * WIDTH, len(lines) * size * LINE


@dataclass
class Element:
    """One thing on the canvas. Wraps the id so callers pass shapes around, not strings."""

    ident: str
    kind: str
    x: float
    y: float
    width: float
    height: float

    @property
    def centre(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.height / 2


@dataclass
class Scene:
    """A canvas being built up. Ids and seeds are counted, never random.

    That is the whole reason this exists. Excalidraw puts a random seed in every element so
    its sketchy rendering differs run to run, which is charming in the app and useless in a
    repository, because it means a regenerated file differs everywhere even when nothing
    changed.
    """

    name: str
    elements: list[dict] = field(default_factory=list)
    _n: int = 0

    def _next(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n:03d}"

    def _base(
        self, ident: str, kind: str, x: float, y: float, w: float, h: float, stroke: str, fill: str
    ) -> dict:
        return {
            "id": ident,
            "type": kind,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "angle": 0,
            "strokeColor": stroke,
            "backgroundColor": fill,
            "fillStyle": "solid",
            "strokeWidth": 2,
            "strokeStyle": "solid",
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "frameId": None,
            "roundness": None,
            "seed": self._n * 7919,
            "version": 1,
            "versionNonce": self._n * 104729,
            "isDeleted": False,
            "boundElements": [],
            "updated": 1,
            "link": None,
            "locked": False,
        }

    def _text(
        self,
        ident: str,
        x: float,
        y: float,
        text: str,
        size: int,
        colour: str,
        container: str | None,
        align: str,
        font: int,
    ) -> dict:
        w, h = measure(text, size)
        element = self._base(ident, "text", x, y, w, h, colour, "transparent")
        element.update(
            {
                "text": text,
                "originalText": text,
                "fontSize": size,
                "fontFamily": font,
                "textAlign": align,
                "verticalAlign": "middle" if container else "top",
                "containerId": container,
                "lineHeight": LINE,
                "autoResize": True,
            }
        )
        return element

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        label: str = "",
        *,
        fill: tuple[str, str] = PLAIN,
        size: int = 16,
        dashed: bool = False,
        font: int = CODE,
    ) -> Element:
        """A rounded rectangle with its label bound inside it.

        Bound rather than placed on top, so dragging the box in the app takes the text with
        it. Somebody will drag it.
        """
        stroke, background = fill
        ident = self._next("box")
        rect = self._base(ident, "rectangle", x, y, w, h, stroke, background)
        rect["roundness"] = {"type": 3}
        if dashed:
            rect["strokeStyle"] = "dashed"
        self.elements.append(rect)
        if label:
            inner = self._next("txt")
            rect["boundElements"] = [{"id": inner, "type": "text"}]
            tw, th = measure(label, size)
            self.elements.append(
                self._text(
                    inner,
                    x + (w - tw) / 2,
                    y + (h - th) / 2,
                    label,
                    size,
                    stroke,
                    ident,
                    "center",
                    font,
                )
            )
        return Element(ident, "rectangle", x, y, w, h)

    def note(
        self, x: float, y: float, text: str, *, size: int = 16, colour: str = INK, font: int = HAND
    ) -> Element:
        """Free text, for a caption or an aside rather than a piece of IR."""
        ident = self._next("txt")
        element = self._text(ident, x, y, text, size, colour, None, "left", font)
        self.elements.append(element)
        return Element(ident, "text", x, y, element["width"], element["height"])

    def arrow(
        self,
        start: Element,
        end: Element,
        label: str = "",
        *,
        dashed: bool = False,
        colour: str = INK,
        bend: float = 0.0,
        size: int = 14,
    ) -> Element:
        """An arrow between two shapes, bound to both so it follows them when they move.

        `bend` pushes the midpoint sideways, which is how the back edge in a loop gets out
        of the way of the forward edges instead of drawing straight through them.
        """
        x1, y1 = start.centre
        x2, y2 = end.centre
        ident = self._next("arr")
        element = self._base(ident, "arrow", x1, y1, x2 - x1, y2 - y1, colour, "transparent")
        points = [[0.0, 0.0], [x2 - x1, y2 - y1]]
        if bend:
            points.insert(1, [(x2 - x1) / 2 + bend, (y2 - y1) / 2])
        element.update(
            {
                "points": points,
                "lastCommittedPoint": None,
                "startBinding": {"elementId": start.ident, "focus": 0, "gap": 4},
                "endBinding": {"elementId": end.ident, "focus": 0, "gap": 4},
                "startArrowhead": None,
                "endArrowhead": "arrow",
                "elbowed": False,
            }
        )
        if dashed:
            element["strokeStyle"] = "dashed"
        self.elements.append(element)
        for shape in (start, end):
            for existing in self.elements:
                if existing["id"] == shape.ident:
                    existing["boundElements"] = [
                        *existing["boundElements"],
                        {"id": ident, "type": "arrow"},
                    ]
        if label:
            inner = self._next("txt")
            element["boundElements"] = [{"id": inner, "type": "text"}]
            tw, th = measure(label, size)
            mid_x = x1 + (x2 - x1) / 2 + (bend / 2)
            mid_y = y1 + (y2 - y1) / 2
            self.elements.append(
                self._text(
                    inner,
                    mid_x - tw / 2,
                    mid_y - th / 2,
                    label,
                    size,
                    colour,
                    ident,
                    "center",
                    HAND,
                )
            )
        return Element(ident, "arrow", min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    def document(self) -> str:
        """The scene as a file. Sorted and indented, so a diff is readable."""
        scene = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://github.com/tamnd/gcc-internals",
            "elements": self.elements,
            "appState": {
                "gridSize": 20,
                "gridModeEnabled": False,
                "viewBackgroundColor": "#ffffff",
            },
            "files": {},
        }
        return json.dumps(scene, indent=2, ensure_ascii=False) + "\n"
