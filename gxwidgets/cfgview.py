"""The control flow graph, drawn from the graph dump rather than from the gotos.

A reader who builds a control flow graph by reading a GIMPLE text dump gets a graph that
looks right and is wrong. A block that falls through to the next one ends without a `goto`,
so nothing in the text says where control went, and the picture comes out with the loop body
hanging off nothing. `gxray.cfg` reads the `.dot` file GCC writes out of its own edge lists
instead, so the fallthroughs, the branch probabilities and the loop nesting are all real.
This widget draws what that parser found and knows nothing about GIMPLE.

The layout is the layering in `CFG.layers`, which is the same one the animation uses, so a
still from a video and a live widget put the blocks in the same places. Every block is a
button, selecting one shows the statements in it and every edge at both ends, and all of
that works on a page with no runtime, because the whole drawing is built here in Python.

Two lanes run down the sides. An edge that skips a layer goes down the right, and an edge
that goes backwards goes up the left, which keeps a long edge from running through the
middle of a block it has nothing to do with.
"""

from __future__ import annotations

from dataclasses import dataclass

from gxmanim.palette import EDGES
from gxray.cfg import CFG, Edge
from gxray.locs import strip_locs
from gxwidgets.base import Widget
from gxwidgets.html import count_of, el, esc, join, legend

PAD = 12
BOX_W = 190
BOX_H = 46
#: ENTRY and EXIT have no code in them, so they get a shorter box and one line of text.
TERM_H = 26
VGAP = 40
COL_GAP = 26
#: How wide one routing lane is. There is one of these per edge that needs to travel.
LANE = 24
#: How far a corner is rounded off. Purely so a right angle does not look like a join.
BEND = 6
#: How far down the gap between two layers the first routing strip sits. The top of a gap is
#: left clear for the letters and percentages on the edges leaving the row above it, because
#: a line through the middle of a label reads as a line through the label.
TRACK = 26

#: The stroke pattern for each of the three line styles the palette names.
DASHES = {"solid": "", "dashed": "5 3", "dotted": "2 3"}


@dataclass(frozen=True)
class Box:
    """Where one block ended up, in the coordinates of the drawing."""

    index: int
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
    def mid(self) -> float:
        return self.y + self.h / 2


def _towards(here: tuple[float, float], there: tuple[float, float], by: float) -> str:
    """A point `by` along the way from one corner to the next, for rounding the corner off."""
    dx, dy = there[0] - here[0], there[1] - here[1]
    span = max(abs(dx), abs(dy))
    step = min(by, span / 2) / span if span else 0
    return f"{here[0] + dx * step:.1f} {here[1] + dy * step:.1f}"


def path(points: list[tuple[float, float]]) -> str:
    """A polyline through the points, with the corners rounded."""
    if len(points) < 3:
        return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
    out = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for n in range(1, len(points) - 1):
        before, here, after = points[n - 1], points[n], points[n + 1]
        out.append(f"L {_towards(here, before, BEND)}")
        out.append(f"Q {here[0]:.1f} {here[1]:.1f} {_towards(here, after, BEND)}")
    out.append(f"L {points[-1][0]:.1f} {points[-1][1]:.1f}")
    return " ".join(out)


def spread(n: int, total: int, span: float, start: float) -> float:
    """Where the nth of `total` things goes along a span, evenly, with a gap at each end."""
    return start + span * (n + 1) / (total + 1)


class CFGView(Widget):
    kind = "cfgview"
    title = "The control flow graph"
    defaults = {"at": ""}

    def __init__(self, graph: CFG, at: str | int = "", **kw: str) -> None:
        self.graph = graph
        self.layer = graph.layers()
        self.idom = graph.dominators()
        self.boxes = self._place()
        self.lane = self._lanes()
        self.ends = self._ports()
        # An edge that leaves the bottom row and goes back up runs along the strip below it,
        # and that strip is outside the box layout, so the drawing has to grow to hold it.
        low = max((y for n in self.lane for _, y in self.points(n)), default=0.0)
        self.height = max(self.height, low + PAD)
        super().__init__(**kw)
        if at != "":
            self.view["at"] = str(at)
        if self.view["at"] not in {str(i) for i in graph.indices}:
            self.view["at"] = str(self.opening)
        self.title = f"{graph.function}, the control flow graph GCC actually had"

    # The model

    @property
    def opening(self) -> int:
        """The block to start on, which is the first one with anything in it.

        ENTRY is first in every graph and has no code, so opening on it would show a reader
        an empty panel and teach them nothing about the function they are looking at.
        """
        for index in self.graph.indices:
            if self.graph.blocks[index].code:
                return index
        return self.graph.indices[0] if self.graph.indices else 0

    def route(self, edge: Edge) -> str:
        """Which of the three ways round the drawing this edge takes.

        This is about the picture rather than about GCC. An edge GCC marked as a back edge
        almost always goes up here as well, but the two can differ, and what decides the
        route is where the two ends ended up on the page.
        """
        if self.layer[edge.dst] <= self.layer[edge.src]:
            return "up"
        return "skip" if self.layer[edge.dst] > self.layer[edge.src] + 1 else "down"

    def arcs(self, index: int) -> list[tuple[str, Edge]]:
        """Every edge touching a block, arriving ones first, in the order they are drawn."""
        return [("in", e) for e in self.graph.predecessors(index)] + [
            ("out", e) for e in self.graph.successors(index)
        ]

    def data(self) -> dict:
        kinds: dict[str, int] = {}
        for e in self.graph.edges:
            kinds[e.kind] = kinds.get(e.kind, 0) + 1
        return {
            "function": self.graph.function,
            "blocks": [
                {
                    "index": i,
                    "statements": len(self.graph.blocks[i].code),
                    "loop": self.graph.blocks[i].loop,
                    "layer": self.layer[i],
                }
                for i in self.graph.indices
            ],
            "kinds": kinds,
            "loops": {str(n): blocks for n, blocks in self.graph.loops.items()},
        }

    # The layout

    def _height(self, index: int) -> float:
        block = self.graph.blocks[index]
        return TERM_H if block.entry or block.exit else BOX_H

    def _lanes(self) -> dict[int, int]:
        """Which side lane each edge that needs one runs in, nearest the boxes first."""
        out: dict[int, int] = {}
        taken = {"up": 0, "skip": 0}
        for n, edge in enumerate(self.graph.edges):
            way = self.route(edge)
            if way != "down":
                out[n] = taken[way]
                taken[way] += 1
        return out

    def _place(self) -> dict[int, Box]:
        """One box per block, laid out in layers, with the side lanes left clear.

        The width of the widest layer sets the width of the drawing, and every other layer is
        centred in it. That keeps a diamond looking like a diamond rather than like a set of
        blocks that all begin at the left margin.
        """
        rows: dict[int, list[int]] = {}
        for index in self.graph.indices:
            rows.setdefault(self.layer[index], []).append(index)
        widths = {d: len(r) * BOX_W + (len(r) - 1) * COL_GAP for d, r in rows.items()}
        inner = max(widths.values(), default=BOX_W)

        ups = sum(1 for e in self.graph.edges if self.route(e) == "up")
        skips = sum(1 for e in self.graph.edges if self.route(e) == "skip")
        self.left = PAD + LANE * ups
        self.width = self.left + inner + LANE * skips + PAD
        self.inner = inner

        boxes: dict[int, Box] = {}
        y = float(PAD)
        for depth in sorted(rows):
            here = rows[depth]
            x = self.left + (inner - widths[depth]) / 2
            for index in here:
                boxes[index] = Box(index, x, y, BOX_W, self._height(index))
                x += BOX_W + COL_GAP
            y += max(self._height(i) for i in here) + VGAP
        self.height = y - VGAP + PAD
        return boxes

    def _lane_x(self, edge: Edge, n: int) -> float:
        lane = self.lane[n]
        if self.route(edge) == "up":
            return self.left - LANE * lane - LANE / 2
        return self.left + self.inner + LANE * lane + LANE / 2

    def _order(self, n: int) -> tuple[int, float, int]:
        """How the edges at one block sort across the side of the box they share.

        Leftmost for the ones going back up the left lane, rightmost for the ones going down
        the right, and the ordinary ones in the middle in the order their far end sits. So
        the port an edge leaves from is on the side it is about to head off to, and two edges
        out of one block do not have to cross each other to get where they are going.
        """
        edge = self.graph.edges[n]
        way = self.route(edge)
        side = -1 if way == "up" else 1 if way == "skip" else 0
        return (side, self.boxes[edge.dst].x, edge.dst)

    def _ports(self) -> dict[int, tuple[tuple[float, float], tuple[float, float]]]:
        """Where every edge leaves and arrives, worked out once so nothing shares a point.

        Every edge leaves the bottom of a block and arrives at the top of one, whichever way
        round the page it goes. A drawing where some edges come out of the side is a drawing
        where a reader has to work out which end is which.

        Edges are keyed by their position in `graph.edges` rather than by their two ends,
        because a switch can have two edges between the same pair of blocks and they still
        need to be drawn apart.
        """
        out: dict[int, list[int]] = {}
        into: dict[int, list[int]] = {}
        for n, edge in enumerate(self.graph.edges):
            out.setdefault(edge.src, []).append(n)
            into.setdefault(edge.dst, []).append(n)
        for block in out:
            out[block].sort(key=self._order)

        # Arriving edges sort by the same side first, then by where they set off from, so the
        # port an edge lands on is under the place it has been travelling from.
        def coming(n: int) -> tuple[int, float]:
            return (self._order(n)[0], self.boxes[self.graph.edges[n].src].x)

        for block in into:
            into[block].sort(key=coming)

        ends: dict[int, tuple[tuple[float, float], tuple[float, float]]] = {}
        for n, edge in enumerate(self.graph.edges):
            src, dst = self.boxes[edge.src], self.boxes[edge.dst]
            leaving, arriving = out[edge.src], into[edge.dst]
            sx = spread(leaving.index(n), len(leaving), src.w, src.x)
            dx = spread(arriving.index(n), len(arriving), dst.w, dst.x)
            ends[n] = ((sx, src.bottom), (dx, dst.y))
        return ends

    def _corridor(self, n: int, below: float, above: float) -> tuple[float, float]:
        """The two clear strips a long edge uses, one under its start and one over its end.

        The gap between two layers has nothing in it, so an edge that has to travel can run
        along one without crossing a block. Edges in different lanes take slightly different
        strips, so two of them going the same way do not sit on top of each other.

        Both strips are measured from the top of the gap they are in rather than from the box
        they touch. Every gap is the same height, so the two work out to the same place in
        their own gap, and neither of them can land on the labels at the top of one.
        """
        step = min(TRACK + self.lane.get(n, 0) * 5, VGAP - 4)
        return below + step, above - VGAP + step

    def points(self, n: int) -> list[tuple[float, float]]:
        """The corners of one edge, from where it leaves to where it arrives."""
        edge = self.graph.edges[n]
        (sx, sy), (dx, dy) = self.ends[n]
        if self.route(edge) == "down":
            if abs(sx - dx) < 0.5:
                return [(sx, sy), (dx, dy)]
            half = (sy + dy) / 2
            return [(sx, sy), (sx, half), (dx, half), (dx, dy)]
        lane = self._lane_x(edge, n)
        leave, arrive = self._corridor(n, sy, dy)
        return [(sx, sy), (sx, leave), (lane, leave), (lane, arrive), (dx, arrive), (dx, dy)]

    # Rendering

    def body(self) -> str:
        return join(
            [
                self._svg(),
                self._note(),
                join([self._panel(i) for i in self.graph.indices]),
                legend(
                    [
                        ("T", "gx-neutral", "the way out of a test when it holds"),
                        ("F", "gx-neutral", "the way out of a test when it does not"),
                        (">>", "gx-neutral", "a doubled arrowhead is the jump back round a loop"),
                        ("|", "gx-changed", "a bar down the left side means it is in a loop"),
                        (">", "gx-focus", "the block the panel below is about"),
                    ]
                ),
                self._text(),
            ]
        )

    def _note(self) -> str:
        return el(
            "p",
            esc(
                "An edge with no letter on it is a fallthrough, and those are real edges even "
                "though nothing in the text dump mentions them. An edge that skips a layer "
                "runs down the right hand lane, and an edge that goes back up runs up the "
                "left hand one, which is what a loop looks like from here. The back edge has "
                "no letter either, because the graph dump records it as the way round the "
                "loop and stops saying which side of the test it came off."
            ),
            class_="gx-note",
        )

    def _svg(self) -> str:
        arcs = [self._arc(n) for n in range(len(self.graph.edges))]
        nodes = [self._node(i) for i in self.graph.indices]
        return el(
            "svg",
            join([self._defs(), *arcs, *nodes]),
            class_="gx-flow",
            viewBox=f"0 0 {self.width:.0f} {self.height:.0f}",
            width=f"{self.width:.0f}",
            height=f"{self.height:.0f}",
            role="group",
            data_select="at",
            aria_label=self.described,
        )

    def _defs(self) -> str:
        """The two arrowheads, named after this widget so two graphs on a page do not clash."""
        single = el(
            "marker",
            el("path", d="M 0 0 L 8 4 L 0 8 z", class_="gx-tip"),
            id=f"{self.id}-tip",
            viewBox="0 0 8 8",
            refX="7",
            refY="4",
            markerWidth="6",
            markerHeight="6",
            orient="auto-start-reverse",
        )
        double = el(
            "marker",
            el("path", d="M 0 0 L 4 4 L 0 8 z M 4 0 L 8 4 L 4 8 z", class_="gx-tip"),
            id=f"{self.id}-tip2",
            viewBox="0 0 8 8",
            refX="7",
            refY="4",
            markerWidth="6",
            markerHeight="6",
            orient="auto-start-reverse",
        )
        return el("defs", join([single, double]))

    def _arc(self, n: int) -> str:
        edge = self.graph.edges[n]
        style = EDGES.get(edge.kind, EDGES["fallthrough"])
        tip = f"{self.id}-tip2" if style["arrow"] == "double" else f"{self.id}-tip"
        line = el(
            "path",
            "",
            class_="gx-arc",
            d=path(self.points(n)),
            data_kind=edge.kind,
            data_stroke=style["stroke"],
            data_width=style["width"],
            stroke_dasharray=DASHES[style["stroke"]] or None,
            marker_end=f"url(#{tip})",
        )
        return join([line, self._arc_label(n)])

    def _arc_label(self, n: int) -> str:
        """The letter and the probability, put where the edge leaves rather than at its middle.

        The middle of a long edge is next to a block it has nothing to do with, and a reader
        following a branch out of a test wants to know which way is which at the fork.
        """
        edge = self.graph.edges[n]
        glyph = EDGES.get(edge.kind, EDGES["fallthrough"])["glyph"]
        # A hundred per cent on every fallthrough is noise. What a reader wants from these
        # numbers is which way GCC thinks the branch usually goes.
        odds = f"{edge.prob * 100:.0f}%" if edge.prob is not None and edge.prob < 1 else ""
        text = " ".join(p for p in (glyph, odds) if p)
        if not text:
            return ""
        (sx, sy), _ = self.ends[n]
        return el(
            "text",
            esc(text),
            class_="gx-arc-label",
            x=f"{sx + 5:.1f}",
            y=f"{sy + 13:.1f}",
        )

    def _node(self, index: int) -> str:
        block, box = self.graph.blocks[index], self.boxes[index]
        parts = [
            el(
                "rect",
                "",
                x=f"{box.x:.1f}",
                y=f"{box.y:.1f}",
                width=f"{box.w:.0f}",
                height=f"{box.h:.0f}",
                rx="4",
            )
        ]
        if block.loop is not None:
            parts.append(
                el(
                    "rect",
                    "",
                    class_="gx-loop",
                    x=f"{box.x:.1f}",
                    y=f"{box.y + 4:.1f}",
                    width="3",
                    height=f"{box.h - 8:.0f}",
                    rx="1.5",
                )
            )
        one_line = block.entry or block.exit
        # The marker for the selected block, drawn on every block and shown on one of them.
        # Which one is a CSS rule on `aria-current`, so clicking moves it without anything
        # here having to run again, and a page with no runtime still marks the right block.
        parts.append(
            el(
                "text",
                "&gt;",
                class_="gx-mark",
                x=f"{box.right - 9:.1f}",
                y=f"{box.mid + 4 if one_line else box.y + 19:.1f}",
                text_anchor="end",
                aria_hidden="true",
            )
        )
        parts.append(
            el(
                "text",
                esc(block.name),
                class_="gx-node-name",
                x=f"{box.x + 12:.1f}",
                y=f"{box.mid + 4 if one_line else box.y + 19:.1f}",
            )
        )
        if not one_line:
            parts.append(
                el(
                    "text",
                    esc(self._subtitle(index)),
                    class_="gx-node-sub",
                    x=f"{box.x + 12:.1f}",
                    y=f"{box.y + 35:.1f}",
                )
            )
        return el(
            "g",
            join(parts),
            class_="gx-node",
            data_cell=str(index),
            data_panel=str(index),
            role="button",
            tabindex=0 if str(index) == self.view["at"] else -1,
            aria_current="true" if str(index) == self.view["at"] else "false",
            aria_label=self._label(index),
        )

    def _subtitle(self, index: int) -> str:
        block = self.graph.blocks[index]
        parts = [count_of(len(block.code), "statement")]
        if block.loop is not None:
            parts.append(f"loop {block.loop}")
        return ", ".join(parts)

    def _label(self, index: int) -> str:
        """What a screen reader hears when it lands on a block."""
        block = self.graph.blocks[index]
        if block.entry or block.exit:
            return f"{block.name}, no code in it"
        outs = count_of(len(self.graph.successors(index)), "way out")
        loop = f", in loop {block.loop}" if block.loop is not None else ""
        return f"{block.name}, {count_of(len(block.code), 'statement')}{loop}, {outs}"

    @property
    def described(self) -> str:
        """What the whole drawing says, in words, for a reader who is not looking at it."""
        graph = self.graph
        loops = len(graph.loops)
        tail = f", and {count_of(loops, 'loop')}" if loops else ", and no loops"
        return (
            f"The control flow graph of {graph.function}: {count_of(len(graph.blocks), 'block')}, "
            f"{count_of(len(graph.edges), 'edge')}{tail}. Every block is a button."
        )

    def _panel(self, index: int) -> str:
        block = self.graph.blocks[index]
        return el(
            "div",
            join([self._facts(index), self._arclist(index), self._code(index)]),
            class_="gx-panel",
            role="tabpanel",
            data_panel=str(index),
            aria_label=f"{block.name}, in full",
            hidden=str(index) != self.view["at"],
        )

    def _facts(self, index: int) -> str:
        block = self.graph.blocks[index]
        facts = [block.name]
        if not (block.entry or block.exit):
            facts.append(count_of(len(block.code), "statement"))
            markers = len(block.lines) - len(block.code)
            if markers:
                facts.append(f"plus {count_of(markers, 'debug marker')}")
        if block.loop is not None:
            facts.append(f"loop {block.loop}, nested {block.depth} deep")
        if index in self.idom:
            facts.append(f"dominated by {self.graph.blocks[self.idom[index]].name}")
        if self.often(index):
            facts.append(self.often(index))
        return el("p", join([el("span", esc(f)) for f in facts]), class_="gx-stat")

    @property
    def base(self) -> int | None:
        """The profile count of the block the function starts in, which is one call.

        GCC's counts are not a number of runs. Without a real profile they come out of the
        branch guesses, scaled so that the entry has a large round number, and the only thing
        worth reading off them is one block against another. Dividing by this one turns them
        into the number a reader actually wants.
        """
        for edge in self.graph.successors(0):
            count = self.graph.blocks[edge.dst].count
            if count:
                return count
        return None

    def often(self, index: int) -> str:
        """How often a block runs per call, said in a way that does not overclaim."""
        count, base = self.graph.blocks[index].count, self.base
        if not count or not base:
            return ""
        share = count / base
        if share < 0.995:
            return f"on about {share * 100:.0f}% of calls"
        return "once per call" if share < 1.5 else f"about {share:.0f} times per call"

    def _arclist(self, index: int) -> str:
        rows = []
        for way, edge in self.arcs(index):
            other = edge.src if way == "in" else edge.dst
            arrow = "from" if way == "in" else "to"
            bits = [edge.kind]
            if edge.back and edge.kind != "back":
                bits.append("and a back edge")
            if edge.prob is not None:
                bits.append(f"{edge.prob * 100:.0f}%")
            rows.append(
                el(
                    "li",
                    join(
                        [
                            esc(f"{way} {arrow} "),
                            el("code", esc(self.graph.blocks[other].name)),
                            esc(", " + ", ".join(bits)),
                        ]
                    ),
                )
            )
        return el("ul", join(rows), class_="gx-arcs")

    def _code(self, index: int) -> str:
        block = self.graph.blocks[index]
        if block.entry or block.exit:
            return el(
                "p",
                esc(
                    f"{block.name} is not a block with code in it. It is where the function "
                    f"starts and stops, and it is in the graph so that every real block has "
                    f"somewhere to come from and somewhere to go."
                ),
                class_="gx-note",
            )
        if not block.code:
            return el(
                "p",
                esc(
                    "This block has no statements in it. GCC keeps an empty block when two "
                    "paths have to stay apart, because a PHI argument is tied to the edge it "
                    "arrived on and two edges cannot arrive on one."
                ),
                class_="gx-note",
            )
        # The locations come off because a recording taken with the lineno modifier puts one
        # in front of every statement, and a column of file names is not what a reader opened
        # a block to look at. The ladder is where locations belong.
        text = "\n".join(strip_locs(line) for line in block.code)
        return el("pre", esc(text), class_="gx-mono")

    def _text(self) -> str:
        """The whole graph as text, for a reader who wants to search it or paste it."""
        lines = []
        for index in self.graph.indices:
            lines.append(self._label(index))
            for way, edge in self.arcs(index):
                other = edge.src if way == "in" else edge.dst
                odds = f"{edge.prob * 100:.0f}%" if edge.prob is not None else ""
                name = self.graph.blocks[other].name
                lines.append(f"  {way:<3} {edge.kind:<12}{odds:>5}  {name}")
        return el(
            "details",
            join(
                [
                    el("summary", "The same graph as text"),
                    el("pre", esc("\n".join(lines)), class_="gx-mono"),
                ]
            ),
        )
