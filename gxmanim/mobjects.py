"""Compositions of the nine primitives, built from what `gxray` parsed.

A mobject takes a model and returns a scene. It does the layout and nothing else. It does
not open files, it does not run GCC, and it does not know whether the scene is going to
become an SVG in a lesson or a frame in a video, which is the whole reason the scene sits
between them.

Four of them here:

    pass_tape   the pipeline, one cell per pass, marked where the IR moved
    flag_ladder every optimizer switch at every level, one row per level
    ir_ladder   one line of C at four levels, one lane each
    ssa_web     one SSA name from its definition to every use
    phi_node    one PHI, its incoming values, and where each came from
    cfg_view    the control flow graph, with GCC's own edges
    dom_tree    which block has to run before which
    rtx_tree    one RTL insn's pattern, put back into the tree it was printed from
    spill_map   one lane per target, one cell per pseudo, marked where it spilled
    pressure_ramp  one lane per function, one cell per live value, marked past the end
    asm_tape    one cell per line of the assembly file, coloured by what kind of line it is
    emit_path   one insn, the pattern that emitted it, and the text that came out

`ssa_web` and `phi_node` deliberately draw data flow and not control flow. Blocks are laid
out in index order down the page and the interesting lines are the threads between the
statements. `cfg_view` and `dom_tree` are the ones that draw control flow, and they take a
`gxray.cfg.CFG` rather than a parsed text dump, because the text dump only shows the jumps
and a graph built from it is missing every fallthrough.
"""

from __future__ import annotations

from itertools import count

from gxmanim.primitives import GAP, Badge, Block, Card, Cell, Edge, Node, Rung, Thread
from gxmanim.scene import Scene
from gxray.asm import Line
from gxray.asm import Listing as AsmFile
from gxray.cfg import CFG, ENTRY
from gxray.gimple import Function, Phi, Stmt
from gxray.locs import LEVEL_NAMES, Ladder, strip_locs
from gxray.regalloc import Allocation
from gxray.rtl import Insn, Rtx
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
    than a paragraph does. The cells with nothing to compare are drawn as unknown rather than
    as unchanged, because the tape does not know and should not imply that it does.

    Unknown follows `changed`, which is the tri-state, rather than following whether the cell
    has a dump. Those are nearly the same set and not quite: the first cell with a dump has
    one and still has nothing in front of it to compare against.
    """
    moved = [c for c in cells if c.changed]
    blind = [c for c in cells if c.changed is None]
    scene = Scene(
        title=title or f"{len(cells)} passes, {len(moved)} of them changed the IR",
        caption=(
            f"{len(blind)} of the {len(cells)} have nothing to compare against, "
            "so the tape says nothing about them either way."
        ),
    )
    x, y = LEFT, TOP
    for i, c in enumerate(cells):
        if i and i % per_row == 0:
            x, y = LEFT, y + Cell.h + 22
        role = "changed" if c.changed else "unknown" if c.changed is None else "neutral"
        shape = Cell(name=c.name, role=role, id=f"pass-{c.index}", changed=bool(c.changed))
        scene.add(shape, x, y)
        x += Cell.w + 1
    return scene


# The levels


def flag_ladder(levels: dict[str, dict[str, bool]], title: str = "") -> Scene:
    """One lane per optimization level, one cell per switch, filled where the switch is on.

    `levels` maps a level name to that level's switches. Only the switches that are not
    the same at every level are drawn. A flag that is on everywhere and a flag that is off
    everywhere both say nothing about the difference between two levels, and leaving the
    hundred and thirty odd of them in makes the shape of the picture harder to see rather
    than more honest, so the caption says how many were left out.

    The columns are ordered by the first lane that turns the switch on, which is what makes
    the picture a staircase for `-O0` through `-O3` and makes the lanes that are not on that
    staircase, `-Os` and `-Og` and `-Ofast`, visibly not on it.
    """
    names = sorted({name for switches in levels.values() for name in switches})
    varies = [n for n in names if len({s.get(n) for s in levels.values()}) > 1]
    order = list(levels)
    varies.sort(key=lambda n: (next((i for i, k in enumerate(order) if levels[k].get(n)), 99), n))

    scene = Scene(
        title=title or f"{len(varies)} switches that are not the same at every level",
        caption=(
            f"{len(names) - len(varies)} of the {len(names)} switches are the same at all "
            f"{len(order)} levels and are not drawn."
        ),
    )
    y = TOP
    for level, switches in levels.items():
        cells = tuple(
            Cell(
                name=n,
                role="added" if switches.get(n) else "neutral",
                id=f"{level}{n}",
                state="on" if switches.get(n) else "off",
            )
            for n in varies
        )
        on = sum(1 for n in varies if switches.get(n))
        rung = Rung(
            name=level,
            cards=cells,
            id=f"level{level}",
            summary=f"{on} of these {len(varies)} switches on",
        )
        scene.add(rung, LEFT, y)
        y += rung.h + GAP
    return scene


# The ladder


#: Small numbers as words, because `at 4 levels` in a title reads like a spreadsheet. A
#: ladder normally has all four, and a film builds a partial one a lane at a time.
COUNTED = {1: "one", 2: "two", 3: "three", 4: "four"}


def _how_many_levels(n: int) -> str:
    return f"{COUNTED.get(n, n)} level" + ("" if n == 1 else "s")


def ir_ladder(ladder: Ladder, line: int, focus: str = "") -> Scene:
    """One source line, and what each level made of it, one lane per level.

    The lane for a level with nothing in it is still drawn. That is not tidiness, it is the
    most interesting thing the ladder has to say: `return s;` reaches RTL and disappears,
    because the value was already in the return register by then.

    Which levels get a lane is the ladder's own `levels`, not the four this project usually
    records. A ladder with two of them is a real ladder, either because the recording only
    went that far or because a film is adding the lanes one at a time, and the title and the
    caption both count what is actually there.
    """
    rung = ladder.rung(line)
    counts = rung.counts()
    scene = Scene(
        title=f"{ladder.file} line {line}, at {_how_many_levels(len(ladder.levels))}",
        caption=f"{rung.source.strip()} became "
        + ", ".join(f"{counts[lv]} {LEVEL_NAMES[lv]}" for lv in ladder.levels),
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


def cfg_view(graph: CFG, focus: int | None = None, statements: bool = True) -> Scene:
    """The control flow graph, laid out in layers, with the edge kinds GCC recorded.

    These are GCC's own edges out of GCC's own graph dump, so the fallthroughs are here.
    That matters more than it sounds: a block that ends without a `goto` still goes
    somewhere, and a graph drawn by reading gotos out of the text dump would show the loop
    body with no way back into it.

    Blocks in a loop are drawn with the focus role, which is the one distinction worth
    spending a colour on in a control flow drawing.
    """
    layer = graph.layers()
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


# Trees


def rtx_tree(insn: Insn, width: int = 24) -> Scene:
    """One insn's pattern as a tree, which is what it was before the printer flattened it.

    An RTX prints as an s-expression and reads as a wall of brackets, and the only reason it
    is hard to read is that the printer put a tree on one line. Putting it back is the whole
    drawing. Nothing here interprets anything: the text on a node is the code, its flags and
    its mode exactly as the dump spelled them, and the operands that are not nodes hang off
    their parent as leaves so that a register number is visibly not a node.

    The roles carry the one distinction that matters at expand time. A pseudo is `unknown`,
    because which hard register it ends up in has not been decided and will not be for
    another twenty passes. A hard register and a literal are `constant`, because they are
    already the final answer.
    """
    counter = count()

    def convert(node: Rtx, root: bool = False) -> Node:
        kids = [
            Node(text=one_line(leaf, width), role=_leaf_role(node), id=f"x{next(counter)}")
            for leaf in node.leaves
        ]
        kids += [convert(k) for k in node.children]
        return Node(
            text=one_line(node.head, width),
            role="focus" if root else "neutral",
            id=f"x{next(counter)}",
            children=tuple(kids),
        )

    if insn.pattern is None:
        scene = Scene(title=f"{insn.code} {insn.uid}")
        scene.caption = (
            "This entry has no pattern. It is a marker in the chain, not an instruction."
        )
        return scene

    scene = tree(convert(insn.pattern, root=True))
    scene.title = f"{insn.code} {insn.uid}, opened up"
    leaves = sum(len(n.leaves) for n in insn.pattern.walk())
    matched = (
        f"matched by {insn.name}"
        if insn.name
        else "matched"
        if insn.recognised
        else "no pattern has matched it yet"
    )
    scene.caption = (
        f"{insn.pattern.size} nodes and {leaves} operands that are not nodes, "
        f"{insn.pattern.depth} deep, {matched}. "
        "Every node is a code, a mode and some operands, and nothing else."
    )
    return scene


def _leaf_role(parent: Rtx) -> str:
    """What an operand that is not a node counts as, which depends on what holds it."""
    if parent.code == "reg":
        return "unknown" if parent.pseudo else "constant"
    return "constant" if parent.code.startswith("const") else "neutral"


# Registers


def spill_map(allocations: dict[str, Allocation], title: str = "") -> Scene:
    """One lane per target, one cell per pseudo, filled where the value ended up in memory.

    The picture is a comparison and nothing else. The same function is compiled for two
    machines, the lanes hold the same number of cells because the program is the same, and
    the reader is meant to see that one lane has marks in it and the other does not.

    A pseudo that got a register is `constant`, because the allocator answered and the
    answer is a register. One that did not is `removed`, because the value is gone from the
    register file and every use of it is now a load. Nothing here is `unknown`: by the time
    IRA prints its disposition there is no third state.
    """
    scene = Scene(title=title or "who got a register")
    y = TOP
    for target, alloc in allocations.items():
        pseudos = sorted(alloc.pseudos)
        spilled = set(alloc.spilled)
        cells = tuple(
            Cell(
                name=f"r{p}",
                role="removed" if p in spilled else "constant",
                id=f"{target}-r{p}",
                changed=p in spilled,
                state="in memory" if p in spilled else "in a register",
            )
            for p in pseudos
        )
        rung = Rung(
            name=target,
            cards=cells,
            id=f"target-{target}",
            summary=(
                f"{alloc.peak()} live at the busiest point, {alloc.available()} registers "
                f"to hand out, {len(spilled)} of these {len(pseudos)} pseudos in memory"
            ),
        )
        scene.add(rung, LEFT, y)
        y += rung.h + GAP
    counts = ", ".join(f"{t}: {len(a.spilled)}" for t, a in allocations.items())
    scene.caption = (
        f"Same function, same flags, same compiler version. Values sent to memory, {counts}. "
        "The difference is how many registers the machine has."
    )
    return scene


def pressure_ramp(rows: dict[str, dict[str, Allocation]], target: str) -> Scene:
    """One lane per function, up the pressure ramp, on one target.

    Each lane is one function and each cell is one value alive at the busiest point in it.
    A cell past the number of registers the target can hand out is drawn as removed, so the
    lane where the row first runs off the end of the register file is visible without
    reading a number. That is the whole argument of the lesson in one shape.
    """
    first = next(iter(rows.values()))[target] if rows else None
    limit = first.available() if first is not None else 0
    scene = Scene(title=f"{target}, {limit} registers to hand out")
    y = TOP
    for name, byfn in rows.items():
        alloc = byfn[target]
        cells = tuple(
            Cell(
                name=f"value {i + 1}",
                role="removed" if i >= limit else "constant",
                id=f"{target}-{name}-{i}",
                changed=i >= limit,
                state="past the end of the register file" if i >= limit else "fits",
            )
            for i in range(alloc.peak())
        )
        over = max(0, alloc.over())
        spilled = len(alloc.spilled)
        if over:
            tail = (
                f"{over} more than there are registers, "
                f"{spilled} {'pseudo' if spilled == 1 else 'pseudos'} in memory"
            )
        else:
            tail = f"{limit - alloc.peak()} registers to spare, nothing in memory"
        rung = Rung(
            name=name,
            cards=cells,
            id=f"fn-{name}",
            summary=f"{alloc.peak()} live, {tail}",
        )
        scene.add(rung, LEFT, y)
        y += rung.h + GAP
    scene.caption = (
        "One cell per value alive at the busiest point. Everything past the "
        f"{limit}th cell has nowhere to go, and the lane where that first happens is the "
        "lane where the compiler starts writing to the stack."
    )
    return scene


# Text


#: What each kind of line is drawn as. The same five roles the assembly listing widget uses,
#: so a reader who learned the colours in the notebook does not have to learn them again in
#: the picture. An instruction is `added` because it is the only kind that puts a machine
#: instruction in the object file, and a directive is `constant` because it says something
#: about the file rather than doing anything at run time.
LINE_ROLES = {
    "instruction": "added",
    "directive": "constant",
    "label": "focus",
    "comment": "unknown",
    "blank": "neutral",
}


def asm_tape(listing: AsmFile, per_row: int = 64, title: str = "") -> Scene:
    """One cell per line of the assembly file, coloured by what kind of line it is.

    T07 made the point that a function of four lines of C is thirteen RTL insns. This is the
    same argument one stage later and it comes out the other way round: the file GCC hands
    the assembler is mostly not instructions, and the twelve that are sit in a crowd of
    directives, labels and comments that nobody counts.

    Lines are drawn in file order, wrapped, so the shape of the file survives. The block of
    directives at the top, the run of instructions in the middle and the tail of `.size` and
    `.ident` are all visible as runs of one colour.
    """
    counts = listing.counts()
    scene = Scene(
        title=title or f"{counts['total']} lines, {counts['instruction']} of them instructions",
        caption=(
            f"{counts['directive']} directives, {counts['label']} labels, "
            f"{counts['comment']} comments and {counts['blank']} blank. "
            "Only the instructions become machine code."
        ),
    )
    x, y = LEFT, TOP
    for i, line in enumerate(listing):
        if i and i % per_row == 0:
            x, y = LEFT, y + Cell.h + 22
        state = line.slot if line.slot else line.kind
        shape = Cell(
            name=f"line {line.number}",
            role=LINE_ROLES[line.kind],
            id=f"line-{line.number}",
            changed=line.kind == "instruction",
            state=state,
        )
        scene.add(shape, x, y)
        x += Cell.w + 1
    return scene


def emit_path(line: Line, pattern: dict | None = None) -> Scene:
    """The four steps from one RTL insn to one line of text, drawn as a chain.

    `pattern` is an entry out of `corpora/mdesc/<target>.json`, or None when the extract does
    not have that pattern in it. Without it the chain is three cards rather than four, which
    is honest: the missing card is the one nobody can fill in without the machine description.
    """
    if not line.annotated:
        raise ValueError(f"line {line.number} carries no annotation, so there is no path to draw")

    scene = Scene(title=f"insn {line.uid} becomes one line of assembly")
    cards = [
        Card(
            text=f"insn {line.uid}, cost {line.cost}, {line.length} bytes",
            role="neutral",
            id="insn",
        ),
        Card(text=line.pattern, role="focus", id="pattern"),
    ]
    if pattern is not None:
        rows = pattern.get("alternatives") or []
        row = rows[line.alternative or 0] if rows else None
        if row is not None:
            which = (
                f"alternative {row['index']}: {' , '.join(row['cons'])}"
                if len(rows) > 1
                else f"the only alternative: {' , '.join(row['cons'])}"
            )
            cards.append(Card(text=which, role="changed", id="alternative"))
            cards.append(Card(text=row["template"], role="constant", id="template"))
    cards.append(Card(text=str(line).split("  [")[0], role="added", id="text"))

    y = TOP
    for card in cards:
        scene.add(card, LEFT, y)
        y += card.h + DOWN
    scene.link(
        *[
            Edge(src=a.id, dst=b.id, kind="fallthrough")
            for a, b in zip(cards, cards[1:], strict=False)
        ]
    )
    where = pattern["citation"] if pattern else "the machine description"
    scene.caption = (
        f"Every step is printed somewhere. The first two come off the `-dp` annotation, "
        f"the middle ones are in {where}, and the last one is the file."
    )
    return scene


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
    "asm_tape",
    "cfg_view",
    "dom_tree",
    "emit_path",
    "ir_ladder",
    "one_line",
    "pass_tape",
    "phi_node",
    "pressure_ramp",
    "rtx_tree",
    "spill_map",
    "ssa_web",
    "tree",
]
