"""The control flow graph, read back out of the graph dump GCC writes itself.

Every other parser in this package reads GCC's text dumps. This one does not, and the reason
is worth writing down, because it is the difference between a correct picture and a plausible
one.

A GIMPLE text dump only shows you the jumps. A block that falls through to the next one ends
without a `goto`, so nothing in the text says where control went, and a control flow graph
built by reading gotos out of the dump silently loses every fallthrough edge. That graph looks
fine. It is wrong, and it is wrong in the direction that makes loops disappear.

GCC will hand over the real graph if you ask:

    gcc -O2 -c l1.c -fdump-tree-optimized-graph

which writes `l1.c.273t.optimized.dot` next to the text dump. That file comes straight out of
`cfun`'s edge lists, so the fallthroughs are in it, the loop tree is in it as nested clusters,
and the branch probabilities are in it as labels. This module reads that file.

    >>> from gxray import cfg
    >>> g = cfg.parse(dot_text)["f"]
    >>> sorted(e.kind for e in g.edges)
    ['fallthrough', 'fallthrough', 'false', 'false', 'back', 'true']

What the dot dump cannot tell you, said out loud once here so no caller has to guess.
`gcc/graph.cc` picks a style, a colour and a weight from the edge flags in an if-else chain,
so the mapping back is not quite one to one. A plain black edge and a real `EDGE_FALLTHRU`
differ only by weight, 10 against 100, and `Edge.weight` keeps that. Red means `EDGE_ABNORMAL`
and swallows whatever colour the edge had, so an EH edge and an abnormal call edge arrive here
looking the same. And an edge that is both a fallthrough and a back edge is drawn as a back
edge, because the chain tests `EDGE_DFS_BACK` first. `Edge.back` is there for exactly that
case, since the `setjmp` receiver in a real function has an edge that is abnormal and going
backwards at the same time and a reader needs to know both.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from gxray.locs import take_loc

# `fn_0_basic_block_3 [shape=record,style=filled,fillcolor=lightgrey,label="{...`
NODE = re.compile(r"^\s*fn_(?P<fn>\d+)_basic_block_(?P<bb>\d+)\s*\[(?P<attrs>.*)$")

# `fn_0_basic_block_2:s -> fn_0_basic_block_3:n [style=...,label="[89%]"];`
LINK = re.compile(
    r"^\s*fn_(?P<fn>\d+)_basic_block_(?P<src>\d+):\w+\s*->\s*"
    r"fn_(?P<dfn>\d+)_basic_block_(?P<dst>\d+):\w+\s*\[(?P<attrs>.*?)\];\s*$"
)

FUNCTION = re.compile(r'^\s*subgraph\s+"cluster_(?P<name>[^"]+)"\s*\{')
LOOP = re.compile(r"^\s*subgraph\s+cluster_(?P<fn>\d+)_(?P<loop>\d+)\s*\{")
CLOSE = re.compile(r"^\s*\}\s*$")

HEADER = re.compile(r"^(?:COUNT:(?P<count>\d+))?<bb (?P<index>\d+)>:")
PROBABILITY = re.compile(r"\[(?P<percent>\d+)%\]")

ENTRY = 0
EXIT = 1


def _attributes(text: str) -> dict[str, str]:
    """The `key=value` pairs in a dot attribute list, with quotes stripped.

    Only used on edges, where the values are short and never contain a comma inside quotes.
    Node labels are pulled out by hand instead, because they run over many lines.
    """
    out: dict[str, str] = {}
    for part in text.split(","):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        out[key.strip()] = value.strip().strip('"')
    return out


def unescape(label: str) -> str:
    """A dot record label, back to the text GCC started with.

    GCC escapes every character dot would otherwise read as structure, so a statement comes
    out as `#\\ s_9\\ =\\ PHI\\ \\<s_5(3),\\ 0(2)\\>`. On top of that `\\l` is a line break
    that left justifies, and a backslash at the end of a line continues the string.
    """
    out: list[str] = []
    i = 0
    while i < len(label):
        c = label[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = label[i + 1] if i + 1 < len(label) else ""
        if nxt in ("l", "n", "r"):
            out.append("\n")
        elif nxt != "\n":  # a continued line, so the break itself is not content
            out.append(nxt)
        i += 2
    return "".join(out)


@dataclass(frozen=True)
class Edge:
    """One edge, with the kind recovered from how GCC chose to draw it.

    `kind` is a name from the drawing vocabulary, so a mobject can hand it straight to the
    palette. `weight` and `back` are the two flags the if-else chain in `graph.cc` would
    otherwise lose: an ordinary unconditional edge and a real `EDGE_FALLTHRU` differ only by
    the weight, and an abnormal edge is painted red over whatever it already was.
    """

    src: int
    dst: int
    kind: str = "fallthrough"
    prob: float | None = None
    weight: int = 10
    back: bool = False

    @property
    def fallthrough(self) -> bool:
        """Whether GCC had `EDGE_FALLTHRU` set, which it wrote down as weight 100."""
        return self.weight == 100

    def __str__(self) -> str:
        tail = f" [{self.prob * 100:.0f}%]" if self.prob is not None else ""
        also = " and a back edge" if self.back and self.kind != "back" else ""
        return f"{self.src} -> {self.dst}, {self.kind}{also}{tail}"


def edge_kind(attrs: dict[str, str]) -> str:
    """Which edge flag GCC had, worked back from the style it chose in `graph.cc`.

    The order matters and it is the order in `draw_cfg_node_succ_edges`. Red is tested first
    because it is applied last there and overwrites the colour a kind had already set.
    """
    colour = attrs.get("color", "black")
    style = attrs.get("style", "")
    if colour == "red":
        return "abnormal"
    if colour == "green" and "dotted" in style:
        return "fake"
    if colour == "blue" and "dotted" in style:
        return "back"
    if colour == "forestgreen":
        return "true"
    if colour == "darkorange":
        return "false"
    return "fallthrough"


def is_back(attrs: dict[str, str]) -> bool:
    """Whether GCC had `EDGE_DFS_BACK` set, which survives the red paint that `kind` loses.

    Only two flags make a dotted line, `EDGE_FAKE` and `EDGE_DFS_BACK`, and the fake one is
    the only edge in the whole dump written with weight 0. So dotted and not weightless is
    a back edge, whatever colour it ended up.
    """
    return "dotted" in attrs.get("style", "") and attrs.get("weight") != "0"


@dataclass
class Block:
    """One basic block, as the graph dump prints it.

    `lines` is GCC's own text for the block, so a drawing built from this does not need the
    text dump alongside. ENTRY and EXIT have no lines at all and that is not a parse failure,
    it is what they are.
    """

    index: int
    lines: tuple[str, ...] = ()
    count: int | None = None
    loop: int | None = None
    depth: int = 0

    @property
    def entry(self) -> bool:
        return self.index == ENTRY

    @property
    def exit(self) -> bool:
        return self.index == EXIT

    @property
    def name(self) -> str:
        return "ENTRY" if self.entry else "EXIT" if self.exit else f"<bb {self.index}>"

    @property
    def code(self) -> tuple[str, ...]:
        """The lines minus the debug markers, matching `gimple.Function.code`.

        Compiling with `-g` roughly doubles the line count with `# DEBUG` markers that
        nothing executes. A drawing that shows them makes a four statement block look like
        a ten statement one, so the drawings use this and the honest count uses `lines`.

        The location has to come off before the test, because a dump recorded with both
        `-g` and `-lineno` prints `[l1.c:5:3] # DEBUG BEGIN_STMT;` and a marker hiding
        behind its own source location is still a marker.
        """
        return tuple(line for line in self.lines if not take_loc(line)[1].startswith("# DEBUG"))

    def __str__(self) -> str:
        if self.entry or self.exit:
            return self.name
        inside = f"{len(self.code)} statement{'' if len(self.code) == 1 else 's'}"
        return f"{self.name}, {inside}" + (f", in loop {self.loop}" if self.loop else "")


@dataclass
class CFG:
    """One function's control flow graph, as GCC had it when the dump was written."""

    function: str
    blocks: dict[int, Block] = field(default_factory=dict)
    edges: tuple[Edge, ...] = ()

    @property
    def indices(self) -> list[int]:
        """Every block, ENTRY first, EXIT last, the real ones in index order between them."""
        real = sorted(i for i in self.blocks if i not in (ENTRY, EXIT))
        return (
            [i for i in (ENTRY,) if i in self.blocks]
            + real
            + [i for i in (EXIT,) if i in self.blocks]
        )

    def successors(self, index: int) -> list[Edge]:
        return [e for e in self.edges if e.src == index]

    def predecessors(self, index: int) -> list[Edge]:
        return [e for e in self.edges if e.dst == index]

    @property
    def back_edges(self) -> list[Edge]:
        """Every edge that goes backwards, including the ones drawn as something else."""
        return [e for e in self.edges if e.back]

    @property
    def loops(self) -> dict[int, list[int]]:
        """Loop number to the blocks in it, from the clusters the dump nests them in."""
        out: dict[int, list[int]] = {}
        for i in sorted(self.blocks):
            loop = self.blocks[i].loop
            if loop is not None:
                out.setdefault(loop, []).append(i)
        return out

    def dominators(self) -> dict[int, int]:
        """Every block's immediate dominator, ENTRY excluded because it has none.

        Cooper, Harvey and Kennedy's iterative algorithm, run over reverse postorder. It is
        twenty lines and it is exact, which beats explaining a lattice to a reader who only
        wanted to know why the loop body cannot run before the test.

        Blocks unreachable from ENTRY are left out. Nothing dominates them and giving them a
        parent to make the tree tidy would be a lie about the graph.
        """
        order = self.reverse_postorder()
        rank = {b: n for n, b in enumerate(order)}
        idom: dict[int, int] = {ENTRY: ENTRY}

        def meet(a: int, b: int) -> int:
            while a != b:
                while rank[a] > rank[b]:
                    a = idom[a]
                while rank[b] > rank[a]:
                    b = idom[b]
            return a

        changed = True
        while changed:
            changed = False
            for block in order:
                if block == ENTRY:
                    continue
                done = [e.src for e in self.predecessors(block) if e.src in idom]
                if not done:
                    continue
                new = done[0]
                for other in done[1:]:
                    new = meet(new, other)
                if idom.get(block) != new:
                    idom[block] = new
                    changed = True
        return {b: d for b, d in idom.items() if b != ENTRY}

    def reverse_postorder(self) -> list[int]:
        """Blocks in reverse postorder from ENTRY, which is the order dominators want.

        Successors are walked in index order so the result is the same on every run. An
        iterative walk rather than a recursive one, because a generated function can have
        thousands of blocks and this should not be the thing that hits the recursion limit.
        """
        seen: set[int] = set()
        post: list[int] = []
        stack: list[tuple[int, list[int]]] = []
        if ENTRY in self.blocks:
            stack.append((ENTRY, sorted({e.dst for e in self.successors(ENTRY)})))
            seen.add(ENTRY)
        while stack:
            node, todo = stack[-1]
            if not todo:
                post.append(node)
                stack.pop()
                continue
            nxt = todo.pop(0)
            if nxt in seen:
                continue
            seen.add(nxt)
            stack.append((nxt, sorted({e.dst for e in self.successors(nxt)})))
        return list(reversed(post))

    def layers(self) -> dict[int, int]:
        """How far down the page each block goes, counted in forward edges from ENTRY.

        Back edges are left out of the count on purpose. Including them makes the layer
        number depend on how many times you are willing to go round the loop, which is not a
        number. Reverse postorder guarantees every forward predecessor of a block is placed
        before the block itself, so one pass is enough.

        This is a fact about the graph rather than about any one drawing, which is why it
        lives here: the animation and the widget lay their blocks out the same way, and a
        reader who has seen one recognises the other.
        """
        order = self.reverse_postorder()
        rank = {b: n for n, b in enumerate(order)}
        layer: dict[int, int] = {}
        for block in order:
            above = [
                e.src
                for e in self.predecessors(block)
                if e.src in layer and rank.get(e.src, -1) < rank[block]
            ]
            layer[block] = max((layer[p] + 1 for p in above), default=0)
        # Anything ENTRY cannot reach still has to go somewhere, and the bottom is honest
        # about it: nothing above it points at it.
        bottom = max(layer.values(), default=0) + 1
        for block in sorted(self.blocks):
            layer.setdefault(block, bottom)
        return layer

    def depth_of(self, index: int) -> int:
        """How deep in the dominator tree a block sits, with ENTRY at zero."""
        idom = self.dominators()
        depth = 0
        while index != ENTRY and index in idom:
            index = idom[index]
            depth += 1
        return depth

    def check(self) -> list[str]:
        """Edges pointing at blocks that were never declared. Should always be empty."""
        return [
            f"edge {e} names block {end} and the dump never declared it"
            for e in self.edges
            for end in (e.src, e.dst)
            if end not in self.blocks
        ]

    def __str__(self) -> str:
        loops = len(self.loops)
        tail = f", {loops} loop{'' if loops == 1 else 's'}" if loops else ""
        return f"{self.function} ({len(self.blocks)} blocks, {len(self.edges)} edges{tail})"


def parse(text: str) -> dict[str, CFG]:
    """Every function in one `.dot` graph dump.

    GCC appends to the same file for every function it dumps, so one file can hold several
    graphs. Blocks are attributed to a function by the cluster they were declared in and
    edges by the `fn_N_` prefix on their ends, which is the number the dump uses to keep two
    functions' blocks apart.
    """
    if "digraph" not in text[:200]:
        # A text dump handed to the dot parser produces an empty graph and no complaint,
        # which is a much worse thing to debug than a sentence saying what happened.
        head = text.strip().splitlines()[0][:60] if text.strip() else "an empty string"
        raise ValueError(f"this is not a graph dump. It starts with {head!r}")

    graphs: dict[str, CFG] = {}
    owner: dict[int, str] = {}  # funcdef number to function name
    scopes: list[str] = []  # what each open brace was, innermost last
    loops: list[int] = []  # the loop clusters currently open, outermost first
    function = ""
    pending: list[tuple[int, int, int, dict[str, str]]] = []

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        if m := FUNCTION.match(line):
            function = m.group("name")
            graphs.setdefault(function, CFG(function=function))
            scopes.append("function")
            i += 1
            continue

        if m := LOOP.match(line):
            loops.append(int(m.group("loop")))
            scopes.append("loop")
            i += 1
            continue

        if CLOSE.match(line):
            if scopes and scopes.pop() == "loop" and loops:
                loops.pop()
            i += 1
            continue

        if m := LINK.match(line):
            attrs = _attributes(m.group("attrs"))
            if attrs.get("style") != "invis":  # a layout hint, not an edge in the program
                pending.append(
                    (int(m.group("fn")), int(m.group("src")), int(m.group("dst")), attrs)
                )
            i += 1
            continue

        if m := NODE.match(line):
            body, i = _collect(lines, i, m.group("attrs"))
            index = int(m.group("bb"))
            owner[int(m.group("fn"))] = function
            block = _block(index, body, loops)
            graphs[function].blocks[index] = block
            continue

        i += 1

    for fn, src, dst, attrs in pending:
        name = owner.get(fn, function)
        if name in graphs:
            graphs[name].edges += (
                Edge(
                    src=src,
                    dst=dst,
                    kind=edge_kind(attrs),
                    prob=_probability(attrs.get("label", "")),
                    weight=int(attrs.get("weight", 10)),
                    back=is_back(attrs),
                ),
            )
    return graphs


def _collect(lines: list[str], i: int, first: str) -> tuple[str, int]:
    """A node declaration, which runs until the `"];` that ends it, joined back together."""
    parts = [first]
    while not parts[-1].rstrip().endswith('"];') and i + 1 < len(lines):
        i += 1
        parts.append(lines[i])
    return "\n".join(parts), i + 1


def _block(index: int, body: str, loops: list[int]) -> Block:
    label = body.partition('label="')[2].rpartition('"];')[0]
    text = unescape(label).strip()
    if text in ("ENTRY", "EXIT"):
        return Block(index=index)

    # Record fields are separated by `|`, but GCC puts a whole `if` with both its gotos in
    # one field, so splitting on the newlines inside a field as well is what gets the block
    # back to one statement per line, the way the text dump prints it.
    fields = [f.strip() for f in text.lstrip("{").rstrip("}").split("\n|")]
    count: int | None = None
    if fields and (m := HEADER.match(fields[0].strip())):
        count = int(m.group("count")) if m.group("count") else None
        fields = fields[1:]
    return Block(
        index=index,
        lines=tuple(line.strip() for f in fields for line in f.splitlines() if line.strip()),
        count=count,
        loop=loops[-1] if loops else None,
        depth=len(loops),
    )


def _probability(label: str) -> float | None:
    m = PROBABILITY.search(label)
    return int(m.group("percent")) / 100 if m else None


__all__ = ["CFG", "ENTRY", "EXIT", "Block", "Edge", "edge_kind", "parse"]
