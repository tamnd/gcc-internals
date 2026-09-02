"""A scene, as an SVG.

This is the renderer that has no dependencies, so a diagram in a lesson is a file in the
repository that CI can rebuild from the dump it came out of. The rule it exists to serve is
that every diagram is generated from a `gxray` model by a script in the repo. No hand placed
boxes, because a hand drawn diagram cannot be re-rendered when the compiler changes, and
that is exactly the failure mode of every GCC diagram currently on the internet.

The manim renderer comes later and reads the same scenes. Keeping the meaning in the scene
and out of both renderers is what makes a still from a video and a live widget agree.

Two things this file is careful about. Semantics are never carried by colour alone, so a
role is drawn as a border style and a glyph as well as a fill, and an edge kind is a dash
pattern and a letter rather than a hue. And the SVG says what it is: `role="img"`, a
`<title>` and a `<desc>` built from the scene, so a screen reader gets the picture and not
the word "image".
"""

from __future__ import annotations

from gxmanim.palette import ROLES, Role
from gxmanim.primitives import (
    CHAR,
    PAD,
    STRIP,
    Badge,
    Block,
    Box,
    Card,
    Cell,
    Edge,
    Node,
    Point,
    Rung,
    Slot,
    Thread,
    glyph_room,
)
from gxmanim.scene import Scene

FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

# How a border style becomes a dash pattern. `double` is not a dash pattern at all, it is a
# second rectangle inset by two, which is handled where rectangles are drawn.
DASHES = {"solid": "", "dashed": "6 4", "dotted": "2 3", "double": ""}

# How an edge kind becomes a line. Weight is doubled for a branch, because a branch is the
# thing a reader is looking for and the two arms have to stand out from the fallthrough.
WEIGHTS = {"thin": 1.25, "thick": 2.5}


def esc(text: str) -> str:
    """XML escaping. Dump text is full of angle brackets, so this is not optional."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _attrs(**kw) -> str:
    parts = []
    for k, v in kw.items():
        if v is None or v == "":
            continue
        parts.append(f'{k.replace("_", "-")}="{esc(v)}"')
    return " ".join(parts)


def _tag(name: str, body: str = "", **kw) -> str:
    attrs = _attrs(**kw)
    head = f"<{name}{' ' + attrs if attrs else ''}"
    return f"{head}>{body}</{name}>" if body else f"{head}/>"


def _text(x: float, y: float, s: str, fill: str, size: int = 13, **kw) -> str:
    """Monospace, baseline placed from the top of the line so boxes line up with text."""
    return _tag(
        "text",
        esc(s),
        x=f"{x:g}",
        y=f"{y:g}",
        fill=fill,
        font_family=FONT,
        font_size=str(size),
        **kw,
    )


def _rect(box: Box, r: Role, radius: float = 4, fill: str | None = None) -> str:
    """A rectangle carrying a role, which means a fill, an ink border and a border style."""
    swatch = r.light
    common = dict(
        x=f"{box.x:g}",
        y=f"{box.y:g}",
        width=f"{box.w:g}",
        height=f"{box.h:g}",
        rx=f"{radius:g}",
        stroke=swatch.ink,
        stroke_width="1.25",
        stroke_dasharray=DASHES[r.border],
    )
    out = _tag("rect", fill=fill or swatch.fill, **common)
    if r.border == "double":
        inner = Box(box.x + 3, box.y + 3, box.w - 6, box.h - 6)
        out += _tag(
            "rect",
            fill="none",
            x=f"{inner.x:g}",
            y=f"{inner.y:g}",
            width=f"{inner.w:g}",
            height=f"{inner.h:g}",
            rx=f"{max(radius - 2, 0):g}",
            stroke=swatch.ink,
            stroke_width="1",
        )
    return out


def _glyph(box: Box, r: Role) -> str:
    """The role's glyph, in the top right corner. The channel that survives greyscale."""
    if not r.glyph:
        return ""
    return _text(box.right - PAD, box.y + 13, r.glyph, r.light.ink, size=11, text_anchor="end")


class Renderer:
    """Draws one scene. Made fresh per render, so nothing carries over between drawings."""

    def __init__(self, scene: Scene) -> None:
        problems = scene.check()
        if problems:
            raise ValueError("this scene cannot be drawn:\n  " + "\n  ".join(problems))
        self.scene = scene
        self.boxes = scene.boxes()

    def render(self, described: bool = False) -> str:
        """The scene as one `<svg>` element.

        With `described` the title and the description go inside it, which is what a `.svg`
        written to disk needs. Inline in a page the surrounding markup usually carries the
        description instead, and having it twice makes a screen reader read it twice.
        """
        bounds = self.scene.bounds()
        body = []
        if described:
            body.append(_tag("title", esc(self.scene.title)))
            body.append(_tag("desc", esc(self.scene.describe())))
        body.append(self._defs())
        for placed in self.scene.placed:
            body.append(self._shape(placed.shape, placed.box, placed.at))
        for link in self.scene.links:
            body.append(self._edge(link) if isinstance(link, Edge) else self._thread(link))
        return _tag(
            "svg",
            "".join(body),
            xmlns="http://www.w3.org/2000/svg",
            viewBox=f"0 0 {bounds.w:g} {bounds.h:g}",
            width=f"{bounds.w:g}",
            height=f"{bounds.h:g}",
            role="img",
            aria_label=self.scene.title,
        )

    # Shapes

    def _shape(self, shape, box: Box, at: Point) -> str:
        if isinstance(shape, Card):
            return self._card(shape, box)
        if isinstance(shape, Block):
            return self._block(shape, box, at)
        if isinstance(shape, Rung):
            return self._rung(shape, box, at)
        if isinstance(shape, Cell):
            return self._cell(shape, box)
        if isinstance(shape, Node):
            return self._node(shape, box)
        if isinstance(shape, Slot):
            return self._slot(shape, box, at)
        if isinstance(shape, Badge):
            return self._badge(shape, box)
        raise TypeError(f"nothing here knows how to draw a {type(shape).__name__}")

    def _card(self, card: Card, box: Box) -> str:
        r = ROLES[card.role]
        out = _rect(box, r) + _glyph(box, r)
        y = box.y + PAD + 15
        out += _text(box.x + PAD, y, card.text, r.light.ink)
        if card.struck:
            mid = y - 4
            out += _tag(
                "line",
                x1=f"{box.x + PAD:g}",
                y1=f"{mid:g}",
                x2=f"{box.x + PAD + len(card.text) * CHAR:g}",
                y2=f"{mid:g}",
                stroke=r.light.ink,
                stroke_width="1.25",
            )
        for badge, bbox in card.badge_boxes(Point(box.x, box.y)):
            out += self._badge(badge, bbox)
        return out

    def _badge(self, badge: Badge, box: Box) -> str:
        r = ROLES[badge.role]
        out = _rect(box, r, radius=8, fill=r.light.fill)
        return out + _text(box.x + 5, box.y + 12, badge.text, r.light.ink, size=11)

    def _block(self, block: Block, box: Box, at: Point) -> str:
        r = ROLES[block.role]
        out = _rect(box, r, radius=6, fill="none")
        strip = Box(box.x, box.y, box.w, STRIP)
        out += _rect(strip, r, radius=6)
        out += _text(box.x + PAD, box.y + 13, block.label, r.light.ink, size=12)
        if block.note:
            out += _text(
                box.right - PAD, box.y + 13, block.note, r.light.ink, size=11, text_anchor="end"
            )
        for card, cbox in block.card_boxes(at):
            out += self._card(card, cbox)
        return out

    def _rung(self, rung: Rung, box: Box, at: Point) -> str:
        r = ROLES[rung.role]
        lane = Box(box.x, box.y, box.w, box.h)
        out = _rect(lane, r, radius=4, fill="none")
        # The label sits against the first row rather than in the middle, because a lane
        # that wrapped is three rows tall and a name floating in the middle of it reads as
        # if it belonged to the row it happens to be next to.
        first = box.y + 22
        out += _text(box.x + PAD, first, rung.name, r.light.ink, size=12)
        if not rung.cards:
            out += _text(
                box.x + rung.label_w,
                first,
                "nothing here",
                ROLES["unknown"].light.ink,
                size=12,
            )
        for card, cbox in rung.card_boxes(at):
            # A lane holds statement cards in the IR ladder and tape cells in the flag
            # ladder, and the two are drawn by different methods, so ask the shape.
            out += self._cell(card, cbox) if isinstance(card, Cell) else self._card(card, cbox)
        return out

    def _cell(self, cell: Cell, box: Box) -> str:
        r = ROLES[cell.role]
        out = _rect(box, r, radius=1)
        if cell.marked:
            # A tick above the cell, so a changing pass is findable without reading colour.
            out += _text(box.cx, box.y - 3, "|", r.light.ink, size=11, text_anchor="middle")
        return out

    def _node(self, node: Node, box: Box) -> str:
        r = ROLES[node.role]
        out = _rect(box, r, radius=10) + _glyph(box, r)
        # Centred on the text column rather than on the box, since the glyph took a corner.
        middle = box.x + (box.w - glyph_room(node.role)) / 2
        return out + _text(middle, box.y + 17, node.text, r.light.ink, text_anchor="middle")

    def _slot(self, slot: Slot, box: Box, at: Point) -> str:
        r = ROLES[slot.role]
        out = _text(box.x, box.cy + 4, slot.name, r.light.ink, size=12)
        for label, n, pbox in slot.part_boxes(at):
            out += _rect(pbox, r, radius=0)
            if pbox.w >= len(label) * CHAR + 8:
                out += _text(
                    pbox.cx, pbox.y + 16, label, r.light.ink, size=11, text_anchor="middle"
                )
            out += _text(
                pbox.cx, pbox.bottom + 12, str(n), r.light.ink, size=10, text_anchor="middle"
            )
        return out

    # Links

    def _defs(self) -> str:
        ink = ROLES["neutral"].light.ink
        head = _tag(
            "marker",
            _tag("path", d="M0,0 L6,3 L0,6 z", fill=ink),
            id="gx-arrow",
            markerWidth="7",
            markerHeight="7",
            refX="6",
            refY="3",
            orient="auto",
        )
        double = _tag(
            "marker",
            _tag("path", d="M0,0 L6,3 L0,6 z", fill=ink)
            + _tag("path", d="M5,0 L11,3 L5,6 z", fill=ink),
            id="gx-arrow-2",
            markerWidth="12",
            markerHeight="7",
            refX="11",
            refY="3",
            orient="auto",
        )
        return _tag("defs", head + double)

    def _clear(self, edge: Edge, a: Box, b: Box) -> bool:
        """Whether a straight line from `a` down to `b` misses everything else in the scene.

        Only top level shapes are looked at, by id, since a card inside a block is already
        covered by the block. The line is the segment between the two centre columns, so a
        box counts as in the way when it sits between them vertically and overlaps that
        column horizontally.
        """
        top, bottom = a.bottom, b.y
        for other in self.scene.placed:
            box = other.box
            if getattr(other.shape, "id", "") in (edge.src, edge.dst):
                continue
            vertical = box.bottom > top and box.y < bottom
            horizontal = box.x - 8 < max(a.cx, b.cx) and box.right + 8 > min(a.cx, b.cx)
            if vertical and horizontal:
                return False
        return True

    def _edge(self, edge: Edge) -> str:
        a, b = self.boxes[edge.src], self.boxes[edge.dst]
        style = edge.style
        ink = ROLES["neutral"].light.ink
        loop = edge.src == edge.dst
        start, end = (a.foot, b.top) if a.cy <= b.cy and not loop else (a.rightward, b.rightward)
        if loop:
            # A block that jumps to itself. Drawn as a loop off the right hand side, because
            # the straight version is a line from the bottom of the box to the top of the
            # same box, which goes through everything in it.
            bow = a.right + 34
            path = (
                f"M{start.x:g},{start.y - 10:g} C{bow:g},{start.y - 24:g} "
                f"{bow:g},{start.y + 24:g} {end.x:g},{end.y + 10:g}"
            )
        elif a.cy <= b.cy and self._clear(edge, a, b):
            path = f"M{start.x:g},{start.y:g} L{end.x:g},{end.y:g}"
        elif a.cy <= b.cy:
            # A forward edge that skips a layer. Straight down would run it through whatever
            # sits in between, and an arrow crossing a block looks like it enters the block.
            # It leaves and arrives on the left, since the right hand side is where the back
            # edges go and two curves in the same channel are worse than none.
            start, end = a.left, b.left
            bow = max(min(a.x, b.x) - 30, 4)
            path = (
                f"M{start.x:g},{start.y:g} C{bow:g},{start.y:g} "
                f"{bow:g},{end.y:g} {end.x:g},{end.y:g}"
            )
        else:
            # A back edge leaves and re-enters on the right and bows out, so it never lies
            # on top of the forward edges between the same two blocks.
            bow = max(a.right, b.right) + 34
            path = (
                f"M{start.x:g},{start.y:g} C{bow:g},{start.y:g} "
                f"{bow:g},{end.y:g} {end.x:g},{end.y:g}"
            )
        out = _tag(
            "path",
            d=path,
            fill="none",
            stroke=ink,
            stroke_width=f"{WEIGHTS[style['width']] * (1 + (edge.prob or 0)):g}",
            stroke_dasharray=DASHES[style["stroke"]],
            marker_end="url(#gx-arrow-2)" if style["arrow"] == "double" else "url(#gx-arrow)",
        )
        parts = [p for p in (edge.glyph, f"{edge.prob:.0%}" if edge.prob is not None else "") if p]
        if parts:
            out += _text(start.x + 6, start.y + 14, " ".join(parts), ink, size=11)
        return out

    def _thread(self, thread: Thread) -> str:
        a, b = self.boxes[thread.src], self.boxes[thread.dst]
        r = ROLES[thread.role]
        # Out of the left side of the definition and into the left side of the use, bowed
        # away from the blocks so it reads as data flow rather than as another arrow.
        bow = min(a.x, b.x) - 30
        path = (
            f"M{a.left.x:g},{a.left.y:g} "
            f"C{bow:g},{a.left.y:g} {bow:g},{b.left.y:g} {b.left.x:g},{b.left.y:g}"
        )
        out = _tag(
            "path",
            d=path,
            fill="none",
            stroke=r.light.ink,
            stroke_width="1",
            stroke_dasharray="1 2",
            marker_end="url(#gx-arrow)",
        )
        if thread.name:
            out += _text(bow + 4, (a.cy + b.cy) / 2, thread.name, r.light.ink, size=11)
        return out


def render(scene: Scene) -> str:
    """One scene, as an SVG fragment to drop into a page."""
    return Renderer(scene).render()


def document(scene: Scene) -> str:
    """One scene, as a standalone `.svg` file with its title and description in it."""
    return Renderer(scene).render(described=True)
