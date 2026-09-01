"""Compositions of the nine primitives, built from what `gxray` parsed.

A mobject takes a model and returns a scene. It does the layout and nothing else. It does
not open files, it does not run GCC, and it does not know whether the scene is going to
become an SVG in a lesson or a frame in a video, which is the whole reason the scene sits
between them.

Four of them here:

    pass_tape   the pipeline, one cell per pass, marked where the IR moved
    ir_ladder   one line of C at four levels, one lane each
    ssa_web     one SSA name from its definition to every use
    phi_node    one PHI, its incoming values, and where each came from
    cfg_view    the control flow graph, with GCC's own edges
    dom_tree    which block has to run before which

`ssa_web` and `phi_node` deliberately draw data flow and not control flow. Blocks are laid
out in index order down the page and the interesting lines are the threads between the
statements. `cfg_view` and `dom_tree` are the ones that draw control flow, and they take a
`gxray.cfg.CFG` rather than a parsed text dump, because the text dump only shows the jumps
and a graph built from it is missing every fallthrough.
"""

from __future__ import annotations

from gxmanim.primitives import GAP, Badge, Block, Card, Cell, Edge, Node, Rung, Thread
from gxmanim.scene import Scene
from gxray.cfg import CFG, ENTRY
from gxray.gimple import Function, Phi, Stmt
from gxray.locs import LEVEL_NAMES, LEVELS, Ladder, strip_locs
from gxray.tape import Cell as TapeCell

# Where the first shape goes. The left margin has to leave room for a def-use thread, which
# bows out to the left of everything it joins.
LEFT = 44
TOP = 12

# How much space between two stacked blocks, and how much between two side by side.
DOWN = 34
ACROSS = 28

# A statement is one line on a card, so long ones get cut. GCC's own text up to here, then
# a marker that says it was cut, because a silently shortened dump is a lie about the dump.
WIDEST = 56


def one_line(text: str, width: int = WIDEST) -> str:
    """The first line of something, short enough to fit on a card.

    RTL insns are several lines and a GIMPLE statement can be long, and a card that grows
    to fit either of them makes every other card in the drawing unreadable.
    """
    head = text.strip().splitlines()[0].strip() if text.strip() else ""
    return head if len(head) <= width else head[: width - 3].rstrip() + "..."


def _is(item, group) -> bool:
    """Membership by identity. Two identical statements are equal and are not the same one."""
    return any(x is item for x in group)


# The pipeline


def pass_tape(cells: list[TapeCell], per_row: int = 96, title: str = "") -> Scene:
    """Every enabled pass as a cell, wrapped into rows.

    The point is not any one pass. It is that at `-O2` almost every pass leaves the function
    exactly as it found it, and a few hundred cells with a handful marked argues that better
    than a paragraph does. The cells with no dump on both sides are drawn as unknown rather
    than as unchanged, because the tape does not know and should not imply that it does.
    """
    moved = [c for c in cells if c.changed]
    blind = [c for c in cells if c.stats is None]
    scene = Scene(
        title=title or f"{len(cells)} passes, {len(moved)} of them changed the IR",
        caption=(
            f"{len(blind)} of the {len(cells)} have no dump on both sides, "
            "so the tape says nothing about them either way."
        ),
    )
    x, y = LEFT, TOP
    for i, c in enumerate(cells):
        if i and i % per_row == 0:
            x, y = LEFT, y + Cell.h + 22
        role = "changed" if c.changed else "unknown" if c.stats is None else "neutral"
        shape = Cell(name=c.name, role=role, id=f"pass-{c.index}", changed=bool(c.changed))
        scene.add(shape, x, y)
        x += Cell.w + 1
    return scene


# The ladder


def ir_ladder(ladder: Ladder, line: int, focus: str = "") -> Scene:
    """One source line, and what each level made of it, one lane per level.

    The lane for a level with nothing in it is still drawn. That is not tidiness, it is the
    most interesting thing the ladder has to say: `return s;` reaches RTL and disappears,
    because the value was already in the return register by then.
    """
    rung = ladder.rung(line)
    counts = rung.counts()
    scene = Scene(
        title=f"{ladder.file} line {line}, at four levels",
        caption=f"{rung.source.strip()} became "
        + ", ".join(f"{counts[lv]} {LEVEL_NAMES[lv]}" for lv in LEVELS),
    )
    source = Card(text=one_line(rung.source), role="focus", id="source")
    scene.add(Rung(name="C source", cards=(source,), id="rung-source"), LEFT, TOP)
    y = TOP + Rung(name="C source", cards=(source,)).h + GAP

    for lv in ladder.levels:
        items = rung.at(lv)
        cards = tuple(
            Card(
                text=one_line(item.text, 40),
                role="focus" if focus and focus in item.text else "neutral",
                id=f"{lv}-{i}",
            )
            for i, item in enumerate(items)
        )
        lane = Rung(
            name=LEVEL_NAMES[lv],
            cards=cards,
            role="neutral" if items else "unknown",
            id=f"rung-{lv}",
        )
        scene.add(lane, LEFT, y)
        y += lane.h + GAP
    return scene


# One name


def ssa_web(fn: Function, name: str) -> Scene:
    """One SSA name, its definition, and a thread to every use.

    Blocks go down the page in index order, which is the order the dump prints them and not
    a claim about control flow. The threads are the drawing. A name defined by a PHI and
    used in two places is three shapes joined by two lines, and that picture is most of what
    static single assignment means.
    """
    web = fn.ssa_web(name)
    definition, uses = web["def"], web["uses"]
    scene = Scene(
        title=f"{name} in {fn.name}, from its definition to every use",
        caption=(
            f"defined by {definition}"
            if definition is not None
            else f"{name} comes in as an argument"
        )
        + f", used {len(uses)} time{'' if len(uses) == 1 else 's'}",
    )

    y = TOP
    def_id = ""
    use_ids: list[str] = []
    for block in fn.ordered_blocks:
        cards = []
        items: list[Phi | Stmt] = [*block.phis, *[s for s in block.stmts if not s.is_debug]]
        for i, item in enumerate(items):
            card_id = f"bb{block.index}-{i}"
            if item is definition:
                role, badges = "focus", (Badge(name, role="focus"),)
                def_id = card_id
            elif _is(item, uses):
                role, badges = "changed", (Badge(name, role="changed"),)
                use_ids.append(card_id)
            else:
                role, badges = "neutral", ()
            cards.append(Card(text=one_line(str(item)), role=role, id=card_id, badges=badges))
        shape = Block(
            index=block.index, cards=tuple(cards), count=block.count, id=f"bb{block.index}"
        )
        scene.add(shape, LEFT, y)
        y += shape.h + DOWN

    if def_id:
        scene.link(*[Thread(src=def_id, dst=u, name=name) for u in use_ids])
    return scene


def phi_node(fn: Function, phi: Phi) -> Scene:
    """One PHI, and where each of its incoming values came from.

    This is the shape that explains SSA, so it gets drawn on its own rather than as part of
    a bigger graph. Each predecessor block sits above with just the statement that defined
    the value it contributes, an edge comes down from it, and the PHI carries one badge per
    argument in the same order the dump prints them.
    """
    scene = Scene(
        title=f"{phi.lhs} in <bb {phi.block}>, one value per way in",
        caption=(
            f"{len(phi.args)} predecessors, so {len(phi.args)} arguments: "
            + ", ".join(f"{v} if control came from <bb {p}>" for v, p in phi.args)
        ),
    )

    x = LEFT
    tops = []
    for value, pred in phi.args:
        block = fn.blocks.get(pred)
        source = _defining_statement(block, value) if block else None
        text, role = _incoming(value, source)
        card = Card(text=text, role=role, id=f"in-{pred}", badges=(Badge(value, role="focus"),))
        shape = Block(index=pred, cards=(card,), id=f"bb{pred}")
        scene.add(shape, x, TOP)
        tops.append(shape)
        x += shape.w + ACROSS

    y = TOP + max(s.h for s in tops) + DOWN
    card = Card(
        text=str(phi),
        role="focus",
        id="phi",
        badges=tuple(Badge(v, role="focus") for v, _ in phi.args),
    )
    scene.add(Block(index=phi.block, cards=(card,), role="focus", id="phi-block"), LEFT, y)
    scene.link(*[Edge(src=f"bb{p}", dst="phi-block", kind="fallthrough") for _, p in phi.args])
    return scene


def _incoming(value: str, source: Stmt | None) -> tuple[str, str]:
    """What to write on the card for one PHI argument, and what role it plays.

    Three cases, and they are genuinely different. The value has a definition in that
    predecessor, so the card shows the statement. It has none, which for the entry block
    usually means the argument came in with the call. Or it is not a name at all, because
    a PHI argument can be a literal, and `# s_9 = PHI <s_5(3), 0(2)>` says the loop starts
    at zero.
    """
    if source is not None:
        return one_line(str(source)), "neutral"
    if "_" not in value:
        return f"{value}, a constant on this edge", "constant"
    return f"{value}, defined before this block", "unknown"


def _defining_statement(block, value: str) -> Stmt | None:
    target = value.split("(")[0].strip()
    for stmt in reversed(block.stmts):
        if stmt.lhs is not None and str(stmt.lhs) == target:
            return stmt
    return None


# Control flow


def _layers(graph: CFG) -> dict[int, int]:
    """How far down the page each block goes, counted in forward edges from ENTRY.

    Back edges are left out of the count on purpose. Including them makes the layer number
    depend on how many times you are willing to go round the loop, which is not a number.
    Reverse postorder guarantees every forward predecessor of a block is placed before the
    block itself, so one pass is enough.
    """
    order = graph.reverse_postorder()
    rank = {b: n for n, b in enumerate(order)}
    layer: dict[int, int] = {}
    for block in order:
        back = [
            e.src
            for e in graph.predecessors(block)
            if e.src in layer and rank.get(e.src, -1) < rank[block]
        ]
        layer[block] = max((layer[p] + 1 for p in back), default=0)
    # Anything ENTRY cannot reach still has to go somewhere, and the bottom is honest about
    # it: nothing above it points at it.
    bottom = max(layer.values(), default=0) + 1
    for block in sorted(graph.blocks):
        layer.setdefault(block, bottom)
    return layer


def cfg_view(graph: CFG, focus: int | None = None, statements: bool = True) -> Scene:
    """The control flow graph, laid out in layers, with the edge kinds GCC recorded.

    These are GCC's own edges out of GCC's own graph dump, so the fallthroughs are here.
    That matters more than it sounds: a block that ends without a `goto` still goes
    somewhere, and a graph drawn by reading gotos out of the text dump would show the loop
    body with no way back into it.

    Blocks in a loop are drawn with the focus role, which is the one distinction worth
    spending a colour on in a control flow drawing.
    """
    layer = _layers(graph)
    rows: dict[int, list[int]] = {}
    for index in graph.indices:
        rows.setdefault(layer[index], []).append(index)

    scene = Scene(
        title=f"{graph.function}, {len(graph.blocks)} blocks and {len(graph.edges)} edges",
        caption=_flow_caption(graph),
    )
    y = TOP
    for depth in sorted(rows):
        shapes = [_cfg_block(graph, i, focus, statements) for i in rows[depth]]
        x = LEFT
        for shape in shapes:
            scene.add(shape, x, y)
            x += shape.w + ACROSS
        y += max(s.h for s in shapes) + DOWN

    scene.link(
        *[Edge(src=f"bb{e.src}", dst=f"bb{e.dst}", kind=e.kind, prob=e.prob) for e in graph.edges]
    )
    return scene


def _cfg_block(graph: CFG, index: int, focus: int | None, statements: bool) -> Block:
    block = graph.blocks[index]
    role = "focus" if index == focus or (focus is None and block.loop) else "neutral"
    # A corpus recorded with `-lineno` has a source location in front of every statement,
    # and in a control flow drawing that is a column of noise in front of the thing the
    # reader came for. The ladder is where locations belong.
    cards = (
        tuple(
            Card(text=one_line(strip_locs(line), 44), role="neutral", id=f"bb{index}-{n}")
            for n, line in enumerate(block.code)
        )
        if statements
        else ()
    )
    return Block(index=index, cards=cards, count=block.count, role=role, id=f"bb{index}")


def _flow_caption(graph: CFG) -> str:
    kinds: dict[str, int] = {}
    for e in graph.edges:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    parts = [f"{n} {kind}" for kind, n in sorted(kinds.items())]
    loops = len(graph.loops)
    tail = f", in {loops} loop{'' if loops == 1 else 's'}" if loops else ""
    return ", ".join(parts) + tail


def dom_tree(graph: CFG) -> Scene:
    """Which block has to have run before a block can run, as a tree.

    A dominates B when every path from ENTRY to B goes through A, and the tree is every
    block hanging off the nearest one that dominates it. It is the shape most of the middle
    end thinks in, because it is the answer to whether a value computed in A is available
    in B, and that is the question every code motion pass is really asking.
    """
    idom = graph.dominators()
    children: dict[int, list[int]] = {}
    for block, parent in sorted(idom.items()):
        children[parent] = [*children.get(parent, []), block]

    def build(index: int) -> Node:
        block = graph.blocks[index]
        return Node(
            text=block.name,
            role="focus" if block.loop else "neutral",
            id=f"dom{index}",
            children=tuple(build(c) for c in children.get(index, [])),
        )

    scene = tree(build(ENTRY))
    deepest = max(graph.depth_of(i) for i in graph.blocks) if graph.blocks else 0
    scene.title = f"{graph.function}, which block has to run before which"
    scene.caption = (
        f"{len(idom) + 1} blocks, {deepest + 1} levels deep. "
        "A block hangs off the nearest block every path to it goes through."
    )
    return scene


# A tree, so the eighth primitive has a caller. Small on purpose: the real tree mobject that
# is still missing is RTXTree, which wants an RTL parser nothing in the toolkit has yet.


def tree(root: Node, gap: int = 18) -> Scene:
    """Any tree of nodes, laid out with children under their parent and edges down.

    The layout is the obvious one: leaves get placed left to right in the order they are
    reached, and a parent is centred over the children it got. Deterministic, and good
    enough for the shallow trees an RTX or a pattern actually makes.
    """
    scene = Scene(title=root.text)
    depth_of: dict[str, int] = {}
    widths: dict[str, float] = {}

    def measure(node: Node, depth: int) -> float:
        depth_of[node.id] = depth
        if not node.children:
            widths[node.id] = node.w
        else:
            widths[node.id] = max(
                node.w,
                sum(measure(c, depth + 1) for c in node.children) + gap * (len(node.children) - 1),
            )
        return widths[node.id]

    def place(node: Node, x: float) -> None:
        span = widths[node.id]
        scene.add(node, x + (span - node.w) / 2, TOP + depth_of[node.id] * (node.h + DOWN))
        child_x = (
            x
            + (span - (sum(widths[c.id] for c in node.children) + gap * (len(node.children) - 1)))
            / 2
        )
        for c in node.children:
            place(c, child_x)
            child_x += widths[c.id] + gap

    for node in root.walk():
        if not node.id:
            raise ValueError(f"every node in a tree needs an id, and {node.text!r} has none")
    measure(root, 0)
    place(root, LEFT)
    scene.link(
        *[
            Edge(src=parent.id, dst=child.id, kind="fallthrough")
            for parent in root.walk()
            for child in parent.children
        ]
    )
    scene.caption = f"{len(root.walk())} nodes, {max(depth_of.values()) + 1} deep"
    return scene


__all__ = [
    "cfg_view",
    "dom_tree",
    "ir_ladder",
    "one_line",
    "pass_tape",
    "phi_node",
    "ssa_web",
    "tree",
]
