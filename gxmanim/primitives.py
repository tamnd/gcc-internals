"""The nine shapes everything in this project is drawn with.

The visual system spec fixes nine primitives and says that introducing a tenth means
amending the spec in the same pull request. That is deliberate friction. A visual language
with thirty symbols is not a language, and the whole point is that by lesson forty a reader
recognises a shape before they read its label.

    1 statement card    one GIMPLE tuple or one RTL insn
    2 block             a basic block, with a header strip carrying index and count
    3 edge              control flow, with the kind in the line style and a glyph
    4 name badge        an SSA name and its version, or a pseudo register
    5 def-use thread    a definition to one of its uses, drawn unlike an edge on purpose
    6 tape cell         one pass in the pipeline
    7 rung              one IR level in the ladder
    8 tree node         an RTX, a GENERIC tree, a match.pd pattern
    9 slot              a register, a stack frame, a vector lane, a bit field

Nothing here knows how to draw itself. A shape carries its content, its role and the size
it wants, and `gxmanim.svg` turns a scene full of them into a picture. That split is what
lets the same scene render to an SVG in a lesson today and to a manim frame later without
either renderer being the place the meaning lives.

Sizes are whole numbers of characters and lines, so a drawing built from a dump lines up
with the dump text, and two scenes built from the same input come out identical. There is no
randomness anywhere in this package and no floating point beyond halving a width.
"""

from __future__ import annotations

from dataclasses import dataclass

from gxmanim.palette import EDGES, ROLES

# One monospace character and one line of them, at the size the widgets use.
CHAR = 8
LINE = 22
PAD = 6

# The header strip on a block, and the gap between two stacked cards.
STRIP = 18
GAP = 4


def _check_role(role: str) -> str:
    if role not in ROLES:
        raise KeyError(f"{role!r} is not a role. The seven are: {', '.join(ROLES)}")
    return role


def text_width(text: str) -> int:
    """How wide a run of monospace text is. Every box in this module is sized from this."""
    return len(text) * CHAR


def glyph_room(role: str) -> int:
    """Space in the top right corner for the role's glyph, which is a real column.

    A role that carries a glyph has to have somewhere to put it. Without this the glyph
    lands on top of the last character of the statement, which is exactly the case where
    both channels are needed at once.
    """
    return 14 if ROLES[role].glyph else 0


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Box:
    """Where something ended up. Produced by a scene, never written by hand."""

    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def top(self) -> Point:
        return Point(self.cx, self.y)

    @property
    def foot(self) -> Point:
        return Point(self.cx, self.bottom)

    @property
    def left(self) -> Point:
        return Point(self.x, self.cy)

    @property
    def rightward(self) -> Point:
        return Point(self.right, self.cy)


# Primitive 4, first because a card can carry one.


@dataclass(frozen=True)
class Badge:
    """A name badge: an SSA name with its version, or a pseudo register.

    Small, attached to something else, and never on its own. A badge is how a reader tells
    `s_1` from `s_3` at a glance without reading the statement it sits on.
    """

    text: str
    role: str = "neutral"
    id: str = ""

    kind = "badge"

    def __post_init__(self) -> None:
        _check_role(self.role)

    @property
    def w(self) -> int:
        return text_width(self.text) + 10

    @property
    def h(self) -> int:
        return 16

    def describe(self) -> str:
        return self.text


# Primitive 1.


@dataclass(frozen=True)
class Card:
    """A statement card: one GIMPLE tuple, or one RTL insn.

    The body is monospace and is GCC's own text, never a paraphrase of it. A reader who
    learns invented names cannot then read a real dump, so the card says `s_8 = s_1 + i_4;`
    and the prose next to it does the explaining.
    """

    text: str
    role: str = "neutral"
    id: str = ""
    badges: tuple[Badge, ...] = ()
    struck: bool = False

    kind = "card"

    def __post_init__(self) -> None:
        _check_role(self.role)

    @property
    def w(self) -> int:
        body = text_width(self.text) + 2 * PAD + glyph_room(self.role)
        badges = sum(b.w + GAP for b in self.badges) + 2 * PAD
        return max(body, badges, 40)

    @property
    def h(self) -> int:
        return LINE + 2 * PAD + (self.badges[0].h + GAP if self.badges else 0)

    def badge_boxes(self, at: Point) -> list[tuple[Badge, Box]]:
        """Where each badge sits, given where the card sits."""
        out = []
        x = at.x + PAD
        y = at.y + LINE + PAD
        for b in self.badges:
            out.append((b, Box(x, y, b.w, b.h)))
            x += b.w + GAP
        return out

    def describe(self) -> str:
        role = ROLES[self.role]
        mark = f" ({role.means})" if self.role != "neutral" else ""
        names = f", tagged {', '.join(b.text for b in self.badges)}" if self.badges else ""
        gone = ", struck through" if self.struck else ""
        return f"{self.text}{mark}{names}{gone}"


# Primitive 2.


@dataclass(frozen=True)
class Block:
    """A basic block: cards in a rectangle, under a header strip.

    The strip carries what GCC calls the block, `<bb 4>`, and its profile count when the
    dump had one. Blocks are the unit a reader learns to count, so the header is always
    there even when the block is empty.
    """

    index: int
    cards: tuple[Card, ...] = ()
    count: int | None = None
    role: str = "neutral"
    id: str = ""

    kind = "block"

    def __post_init__(self) -> None:
        _check_role(self.role)

    @property
    def label(self) -> str:
        return f"<bb {self.index}>"

    @property
    def note(self) -> str:
        return f"count {self.count}" if self.count is not None else ""

    @property
    def w(self) -> int:
        widest = max([c.w for c in self.cards] + [text_width(self.label + " " + self.note) + 8])
        return widest + 2 * PAD

    @property
    def h(self) -> int:
        inner = sum(c.h for c in self.cards) + GAP * max(len(self.cards) - 1, 0)
        return STRIP + PAD + inner + PAD

    def card_boxes(self, at: Point) -> list[tuple[Card, Box]]:
        out = []
        y = at.y + STRIP + PAD
        for c in self.cards:
            out.append((c, Box(at.x + PAD, y, self.w - 2 * PAD, c.h)))
            y += c.h + GAP
        return out

    def describe(self) -> str:
        head = f"{self.label}{', ' + self.note if self.note else ''}"
        if not self.cards:
            return f"{head}, empty"
        body = "; ".join(c.describe() for c in self.cards)
        return f"{head}, holding {len(self.cards)}: {body}"


# Primitive 6.


@dataclass(frozen=True)
class Cell:
    """A tape cell: one pass in the pipeline.

    Narrow on purpose. There are 281 of them at `-O2` and the shape has to say so, because
    the fact that the pipeline is mostly no-ops for any one function is itself the lesson.
    """

    name: str
    role: str = "neutral"
    id: str = ""
    changed: bool = False

    kind = "cell"

    def __post_init__(self) -> None:
        _check_role(self.role)

    w = 6
    h = 34

    def describe(self) -> str:
        return f"{self.name}, {'changed the IR' if self.changed else 'changed nothing'}"


# Primitive 7.


@dataclass(frozen=True)
class Rung:
    """A rung: one IR level in the ladder, as a horizontal lane.

    The lane is the level and what sits in it is what that level made of one line of C.
    Empty lanes are drawn rather than skipped, because a level with nothing in it is the
    most interesting thing the ladder has to say.
    """

    name: str
    cards: tuple[Card, ...] = ()
    role: str = "neutral"
    id: str = ""

    kind = "rung"

    def __post_init__(self) -> None:
        _check_role(self.role)

    # The label column, fixed so every rung's cards start at the same x, and how wide the
    # lane is allowed to get before it wraps. Six RTL insns on one line is normal, and a
    # lane two thousand pixels wide is a picture nobody scrolls to the end of.
    label_w = 96
    max_w = 700

    def rows(self) -> list[list[Card]]:
        """The cards, wrapped. One row is what fits between the label column and `max_w`."""
        out: list[list[Card]] = [[]]
        used = 0.0
        for c in self.cards:
            if out[-1] and used + c.w + GAP > self.max_w - self.label_w:
                out.append([])
                used = 0
            out[-1].append(c)
            used += c.w + GAP
        return out

    @property
    def w(self) -> int:
        if not self.cards:
            return self.label_w + 120
        widest = max(sum(c.w + GAP for c in row) for row in self.rows())
        return self.label_w + widest + PAD

    @property
    def h(self) -> int:
        rows = self.rows()
        tall = max([c.h for c in self.cards] + [LINE + 2 * PAD])
        return tall * len(rows) + GAP * (len(rows) - 1)

    def card_boxes(self, at: Point) -> list[tuple[Card, Box]]:
        out = []
        tall = max([c.h for c in self.cards] + [LINE + 2 * PAD])
        y = at.y
        for row in self.rows():
            x = at.x + self.label_w
            for c in row:
                out.append((c, Box(x, y + (tall - c.h) / 2, c.w, c.h)))
                x += c.w + GAP
            y += tall + GAP
        return out

    def describe(self) -> str:
        if not self.cards:
            return f"{self.name}, nothing"
        return f"{self.name}, {len(self.cards)}: " + "; ".join(c.describe() for c in self.cards)


# Primitive 8.


@dataclass(frozen=True)
class Node:
    """A tree node: an RTX, a GENERIC tree, or a pattern.

    Children go below, and the layout that places them is the mobject's business rather
    than the node's. A node knows its own text and nothing about the tree it is in.
    """

    text: str
    role: str = "neutral"
    id: str = ""
    children: tuple[Node, ...] = ()

    kind = "node"

    def __post_init__(self) -> None:
        _check_role(self.role)

    @property
    def w(self) -> int:
        return text_width(self.text) + 2 * PAD + 6 + glyph_room(self.role)

    @property
    def h(self) -> int:
        return LINE + PAD

    def walk(self) -> list[Node]:
        """This node and every node under it, parents before children."""
        out = [self]
        for c in self.children:
            out.extend(c.walk())
        return out

    def describe(self) -> str:
        if not self.children:
            return self.text
        return f"{self.text} over {', '.join(c.text for c in self.children)}"


# Primitive 9.


@dataclass(frozen=True)
class Slot:
    """A slot: a fixed width bar, subdivided.

    A register, a stack frame, a vector lane, a bit field. The parts are `(label, width)`
    in whatever unit the drawing is about, bytes for a frame and lanes for a vector, and
    the bar is scaled so the whole thing is one width however many units that is.
    """

    name: str
    parts: tuple[tuple[str, int], ...] = ()
    role: str = "neutral"
    id: str = ""

    kind = "slot"

    def __post_init__(self) -> None:
        _check_role(self.role)

    label_w = 96
    bar_w = 320

    @property
    def units(self) -> int:
        return sum(n for _, n in self.parts)

    @property
    def w(self) -> int:
        return self.label_w + self.bar_w

    @property
    def h(self) -> int:
        return LINE + PAD

    def part_boxes(self, at: Point) -> list[tuple[str, int, Box]]:
        """Where each part sits. Widths are proportional, so the bar always fills."""
        out = []
        x = at.x + self.label_w
        total = self.units or 1
        for label, n in self.parts:
            w = self.bar_w * n / total
            out.append((label, n, Box(x, at.y, w, self.h)))
            x += w
        return out

    def describe(self) -> str:
        if not self.parts:
            return f"{self.name}, empty"
        parts = ", ".join(f"{label} takes {n}" for label, n in self.parts)
        return f"{self.name}, {self.units} across {len(self.parts)}: {parts}"


# Primitives 3 and 5. Both join two things, and they are drawn differently on purpose.


@dataclass(frozen=True)
class Edge:
    """Control flow, from one placed shape to another.

    The kind is in the line style and in a glyph, never in the colour, because an edge is
    a thin line and colour on a thin line is the least readable channel there is. The
    probability off GCC's own profile is drawn as weight and also printed as a number.
    """

    src: str
    dst: str
    kind: str = "fallthrough"
    prob: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in EDGES:
            raise KeyError(f"{self.kind!r} is not an edge kind. Have: {', '.join(EDGES)}")

    @property
    def style(self) -> dict[str, str]:
        return EDGES[self.kind]

    @property
    def glyph(self) -> str:
        return self.style["glyph"]

    def describe(self) -> str:
        odds = f", {self.prob:.0%} of the time" if self.prob is not None else ""
        return f"{self.src} to {self.dst}, {self.kind}{odds}"


@dataclass(frozen=True)
class Thread:
    """A def-use thread: a definition to one of its uses.

    Curved and thin, and deliberately unlike an edge. Control flow and data flow are two
    different questions about the same drawing, and a reader who cannot tell the two lines
    apart is reading one picture as if it were another.
    """

    src: str
    dst: str
    name: str = ""
    role: str = "focus"

    def __post_init__(self) -> None:
        _check_role(self.role)

    def describe(self) -> str:
        what = f"{self.name} " if self.name else ""
        return f"{what}from {self.src} to {self.dst}"


# Every shape a scene can hold, so a renderer can be checked against the whole set.
SHAPES = (Card, Block, Badge, Cell, Rung, Node, Slot)
LINKS = (Edge, Thread)

PRIMITIVES: dict[str, str] = {
    "card": "one GIMPLE tuple or one RTL insn",
    "block": "a basic block, with its index and count in a header strip",
    "edge": "control flow, with the kind in the line style",
    "badge": "an SSA name and its version, or a pseudo register",
    "thread": "a definition to one of its uses",
    "cell": "one pass in the pipeline",
    "rung": "one IR level in the ladder",
    "node": "an RTX, a GENERIC tree, or a pattern",
    "slot": "a register, a stack frame, a vector lane, or a bit field",
}


@dataclass(frozen=True)
class Placed:
    """A shape and where it ended up. Mobjects make these, renderers read them."""

    shape: object
    at: Point

    @property
    def box(self) -> Box:
        return Box(self.at.x, self.at.y, self.shape.w, self.shape.h)
