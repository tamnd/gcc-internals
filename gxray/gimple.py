"""Turn a GIMPLE dump into something a widget can draw.

The rule from the architecture spec is to parse into a model rather than into strings, and
to tolerate the unknown rather than throw. A statement form the parser does not recognise
becomes an `UnparsedStmt` carrying its text, and the widget renders it verbatim with a
marker. A parser that throws on an unfamiliar line breaks forty lessons on the day GCC
adds a statement kind.

Drift is caught by counting `UnparsedStmt` across the whole corpus in CI and failing when
the count goes up, not by being strict here.

What a tree dump looks like, from
`gcc-16 -O2 -fdump-tree-ssa -c corpora/programs/l1.c -o /dev/null`:

    ;; Function f (f, funcdef_no=0, decl_uid=4594, cgraph_uid=1, symbol_order=0)

    int f (int n)
    {
      int i;
      int s;
      int _6;

      <bb 2> :
      s_3 = 0;
      i_4 = 0;
      goto <bb 4>; [INV]

      <bb 4> [local count: 118111600]:
      # s_1 = PHI <s_3(2), s_8(3)>
      if (i_2 < n_5(D))
        goto <bb 3>; [INV]
      else
        goto <bb 5>; [INV]
    }
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from gxray.locs import Loc, strip_locs, take_loc

# s_3, i_9, _6, and n_5(D) for a name with no definition in this function, which for a
# parameter means the value it came in with.
SSA_NAME = re.compile(r"\b(?P<base>[A-Za-z_][A-Za-z_0-9]*)?_(?P<version>\d+)(?P<default>\(D\))?")

FUNCTION_HEADER = re.compile(r"^;; Function (?P<pretty>.+?) \((?P<detail>.*)\)\s*$")
BLOCK_HEADER = re.compile(r"^\s*<bb (?P<index>\d+)>\s*(?P<attrs>\[[^\]]*\])?\s*:\s*$")
PHI = re.compile(r"^\s*#\s*(?P<lhs>\S+)\s*=\s*PHI\s*<(?P<args>.*)>\s*$")
PHI_ARG = re.compile(r"(?P<value>[^,()]+)\((?P<pred>\d+)\)")
LOCAL_COUNT = re.compile(r"local count:\s*(?P<count>\d+)")
DECL = re.compile(r"^\s{2}(?P<type>[A-Za-z_][\w \[\]*<>:.]*?)\s+(?P<name>[\w.$]+);\s*$")
SIGNATURE = re.compile(r"^(?P<sig>[A-Za-z_].*\(.*\))\s*$")


@dataclass(frozen=True)
class SsaName:
    """One SSA name. `n_5(D)` is `SsaName("n", 5, default=True)`."""

    base: str
    version: int
    default: bool = False

    def __str__(self) -> str:
        return f"{self.base}_{self.version}" + ("(D)" if self.default else "")


def ssa_names(text: str) -> tuple[SsaName, ...]:
    """Every SSA name mentioned in a piece of dump text, in order, without duplicates."""
    seen: dict[str, SsaName] = {}
    for m in SSA_NAME.finditer(text):
        n = SsaName(m.group("base") or "", int(m.group("version")), bool(m.group("default")))
        seen.setdefault(str(n), n)
    return tuple(seen.values())


@dataclass
class Stmt:
    """One GIMPLE statement.

    `loc` is where in the source it came from, and it is only there when the dump was asked
    for with the `lineno` modifier. `text` never contains the location, so a statement
    prints the same either way and a lesson can quote it without knowing how it was made.
    """

    text: str
    block: int
    kind: str = "other"
    lhs: SsaName | str | None = None
    rhs: str | None = None
    operands: tuple[SsaName, ...] = ()
    loc: Loc | None = None

    @property
    def is_unparsed(self) -> bool:
        return False

    @property
    def is_debug(self) -> bool:
        """A debug marker or a variable location note, which `-g` adds and nothing runs.

        They are real lines in the dump, so the parser keeps them, but they are not code
        and counting them as statements makes a function look twice the size it is.
        """
        return self.kind == "debug"

    def __str__(self) -> str:
        return self.text


@dataclass
class UnparsedStmt(Stmt):
    """A statement this parser does not recognise.

    Not an error. The text is kept verbatim and the widget shows it with a marker. CI
    counts these across the corpus and fails when the count rises, so a new statement form
    shows up as one build failure with a diff rather than as forty broken lessons.
    """

    def __post_init__(self) -> None:
        self.kind = "unparsed"

    @property
    def is_unparsed(self) -> bool:
        return True


@dataclass
class Phi:
    """A PHI node: one incoming value per predecessor block."""

    lhs: SsaName
    args: tuple[tuple[str, int], ...]
    text: str
    block: int
    loc: Loc | None = None

    @property
    def is_debug(self) -> bool:
        return False

    def __str__(self) -> str:
        inner = ", ".join(f"{v}({p})" for v, p in self.args)
        return f"# {self.lhs} = PHI <{inner}>"


@dataclass
class Block:
    """One basic block."""

    index: int
    phis: list[Phi] = field(default_factory=list)
    stmts: list[Stmt] = field(default_factory=list)
    count: int | None = None
    attrs: str = ""

    @property
    def successors(self) -> tuple[int, ...]:
        """Blocks this one can branch to, read off its gotos.

        Fallthrough is not in the dump text, so this is what the block says, not the whole
        truth about the CFG. The real edges come from the Graphviz dump, which is what
        `gxray.cfg` will read when it lands.
        """
        out: list[int] = []
        for s in self.stmts:
            for m in re.finditer(r"goto <bb (\d+)>", s.text):
                bb = int(m.group(1))
                if bb not in out:
                    out.append(bb)
        return tuple(out)

    def __str__(self) -> str:
        return f"<bb {self.index}>"


@dataclass
class Function:
    """One function in one dump."""

    name: str
    header: str = ""
    signature: str = ""
    decls: list[tuple[str, str]] = field(default_factory=list)
    blocks: dict[int, Block] = field(default_factory=dict)

    @property
    def stmts(self) -> list[Stmt]:
        """Every statement in the dump, debug markers included, because they are in it."""
        return [s for b in self.ordered_blocks for s in b.stmts]

    @property
    def code(self) -> list[Stmt]:
        """The statements that do something. What a reader means by how big a function is.

        Compiling with `-g` adds a `# DEBUG` line for every statement boundary and every
        variable that moves, so `stmts` on a `-g` dump is roughly double `code` and the
        difference is entirely bookkeeping for the debugger.
        """
        return [s for s in self.stmts if not s.is_debug]

    @property
    def ordered_blocks(self) -> list[Block]:
        return [self.blocks[i] for i in sorted(self.blocks)]

    @property
    def unparsed(self) -> list[Stmt]:
        return [s for s in self.stmts if s.is_unparsed]

    def ssa_web(self, name: str) -> dict[str, object]:
        """Where an SSA name is defined and everywhere it is used.

        This is the data behind the SSAWeb widget. `def` is None for a name with no
        definition in this function, which for a parameter means the value it came in with.

        Debug statements are not uses. `# DEBUG s => s_3` says where a debugger can find
        `s`, it does not read the value, and listing it alongside the real uses would make
        a name look busier than it is.
        """
        target = name.split("(")[0]
        definition: Stmt | Phi | None = None
        uses: list[Stmt | Phi] = []

        for block in self.ordered_blocks:
            for phi in block.phis:
                if str(phi.lhs) == target:
                    definition = phi
                elif any(v.strip().split("(")[0] == target for v, _ in phi.args):
                    uses.append(phi)
            for stmt in block.stmts:
                if stmt.is_debug:
                    continue
                if stmt.lhs is not None and str(stmt.lhs) == target:
                    definition = stmt
                elif any(str(o).split("(")[0] == target for o in stmt.operands):
                    uses.append(stmt)

        return {"name": target, "def": definition, "uses": uses}

    def __str__(self) -> str:
        return f"{self.name} ({len(self.blocks)} blocks, {len(self.code)} statements)"


@dataclass
class GimpleDump:
    """One parsed dump, which may hold several functions."""

    functions: dict[str, Function] = field(default_factory=dict)
    text: str = ""
    name: str = ""

    @property
    def unparsed(self) -> list[Stmt]:
        return [s for f in self.functions.values() for s in f.unparsed]

    def only(self) -> Function:
        """The single function in this dump, for the common case of a one function file."""
        if len(self.functions) != 1:
            raise ValueError(f"expected one function, found {len(self.functions)}")
        return next(iter(self.functions.values()))

    def __str__(self) -> str:
        return f"{self.name or 'dump'}: {', '.join(self.functions) or 'no functions'}"


def _classify(body: str, block: int, loc: Loc | None = None) -> Stmt:
    """Work out what kind of statement this is. Anything unfamiliar comes back unparsed."""
    text = body.strip()
    ops = ssa_names(text)

    if text.startswith("# DEBUG"):
        return Stmt(kind="debug", text=text, block=block, loc=loc, operands=ops)
    if text.startswith("if ("):
        return Stmt(
            kind="cond", text=text, block=block, loc=loc, rhs=text[3:].strip(), operands=ops
        )
    if text.startswith("else"):
        return Stmt(kind="else", text=text, block=block, loc=loc)
    if text.startswith("goto "):
        return Stmt(kind="goto", text=text, block=block, loc=loc, operands=ops)
    if text.startswith("return"):
        return Stmt(kind="return", text=text, block=block, loc=loc, operands=ops)
    if re.match(r"^<[\w.]+>:", text) or re.match(r"^[\w.]+:$", text):
        return Stmt(kind="label", text=text, block=block, loc=loc)

    # An assignment, which is most of GIMPLE. The left hand side is everything before the
    # first `=` that is not part of `==`, `<=`, `>=` or `!=`.
    m = re.match(r"^(?P<lhs>[^=<>!]+?)\s*=\s*(?P<rhs>.+?);?$", text)
    if m:
        lhs_text = m.group("lhs").strip()
        rhs = m.group("rhs").strip().rstrip(";")
        lhs_names = ssa_names(lhs_text)
        lhs: SsaName | str = lhs_names[0] if lhs_names else lhs_text
        kind = "call" if re.search(r"\w+\s*\(", rhs) else "assign"
        return Stmt(
            kind=kind,
            text=text,
            block=block,
            loc=loc,
            lhs=lhs,
            rhs=rhs,
            operands=ssa_names(rhs),
        )

    if re.match(r"^[\w.]+\s*\(.*\);?$", text):
        return Stmt(kind="call", text=text, block=block, loc=loc, rhs=text, operands=ops)

    return UnparsedStmt(text=text, block=block, loc=loc, operands=ops)


def parse(text: str, name: str = "") -> GimpleDump:
    """Parse a GIMPLE dump. Never raises on unfamiliar content."""
    dump = GimpleDump(text=text, name=name)
    current: Function | None = None
    block: Block | None = None
    in_body = False

    for source_line in text.splitlines():
        # A dump made with the `lineno` modifier prints where every statement came from,
        # in front of it and sometimes in the middle of it. The location goes on the
        # statement rather than into its text, so a statement reads the same whether or
        # not the dump was made that way.
        loc, raw = take_loc(source_line.rstrip())
        line = raw.rstrip()

        header = FUNCTION_HEADER.match(line)
        if header:
            pretty = header.group("pretty")
            current = Function(name=pretty.split()[0], header=line)
            dump.functions[current.name] = current
            block, in_body = None, False
            continue

        if current is None or not line.strip():
            continue

        if line.strip() == "{":
            in_body = True
            continue
        if line.strip() == "}":
            in_body, block = False, None
            continue

        if not in_body:
            sig = SIGNATURE.match(line)
            if sig and not current.signature and "(" in line:
                current.signature = sig.group("sig")
            continue

        bb = BLOCK_HEADER.match(line)
        if bb:
            attrs = bb.group("attrs") or ""
            count = LOCAL_COUNT.search(attrs)
            block = Block(
                index=int(bb.group("index")),
                count=int(count.group("count")) if count else None,
                attrs=attrs,
            )
            current.blocks[block.index] = block
            continue

        decl = DECL.match(raw)
        if decl and block is None:
            current.decls.append((decl.group("type").strip(), decl.group("name")))
            continue

        if block is None:
            # Noise between the header and the first block, such as the "Removing basic
            # block 5" lines the optimized dump prints. Not a statement, so not unparsed.
            continue

        # A PHI carries a location on each argument rather than one for the whole node,
        # since each incoming value was written somewhere different. Those go with the
        # rest of the text, and the ladder reads them off the dump itself.
        clean = strip_locs(line) if "[" in line else line.strip()

        phi = PHI.match(clean)
        if phi:
            lhs = ssa_names(phi.group("lhs"))
            args = tuple(
                (m.group("value").strip(), int(m.group("pred")))
                for m in PHI_ARG.finditer(phi.group("args"))
            )
            block.phis.append(
                Phi(
                    lhs=lhs[0] if lhs else SsaName(phi.group("lhs"), -1),
                    args=args,
                    text=clean,
                    block=block.index,
                    loc=loc,
                )
            )
            continue

        block.stmts.append(_classify(clean, block.index, loc))

    return dump
