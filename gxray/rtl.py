"""Turn an RTL dump into a tree a widget can draw.

RTL prints as s-expressions, so unlike GIMPLE it does not need a statement classifier. It
needs a reader, and then an honest account of the parts that are not s-expressions at all.

What an insn looks like, from `gcc-16 -O2 -fdump-rtl-expand -c corpora/programs/l1.c`:

    (insn 21 20 22 5 (set (reg/v:SI 102 [ <retval> ])
            (plus:SI (reg/v:SI 102 [ <retval> ])
                (reg/v:SI 101 [ i ]))) "l1.c":7:7 -1
         (nil))

The outer list is the insn, and only the fifth item of it is RTL in the sense the manual
means. `insn 21 20 22 5` is a doubly linked list node: the code, this insn's uid, the
previous uid, the next uid, and the basic block it sits in. After the pattern comes the
source location, an integer that is the machine description pattern this insn matched or
`-1` for one that has not been matched yet, sometimes the name of that pattern in braces,
then the register notes, and for a jump an arrow to the label it goes to.

All of that is positional, and the position is written down. Every RTX code in `rtl.def`
carries a format string, and `INSN` is `"uuBeLie"`: previous insn, next insn, basic block,
pattern, location, insn code, notes. The printer walks that string, so the order the dump
uses is the order the struct uses.

This reader does not walk it, because it does not have it. The format strings live in the
GCC tree and the whole point of the corpus is to work with no GCC tree present, so the tail
is recognised by shape instead: a quoted string is a location, `{...}` is a pattern name,
`->` is a jump target, an integer before the notes is the pattern number. Anything it does
not recognise is kept in `extra` rather than dropped, and `Insn.raw` is always the text it
came from, so nothing this file fails to understand is lost.

The rest of the dump is prose. `expand` prints its progress through the basic blocks, and
`try_optimize_cfg` narrates every block it merges, all before the insns start. That part is
worth reading and is not worth parsing, so `parse` keeps it as `Listing.preamble`.

Three things about RTL that this model makes visible, and that the lessons lean on:

A register is a number. `(reg:SI 103)` is pseudo 103 and `(reg:SI 0 x0)` is hard register 0,
which on this target is called `x0`. The dividing line is `FIRST_PSEUDO_REGISTER`, which is a
per target constant, so `Rtx.pseudo` asks whether the register printed a name rather than
comparing against a number this file would have to know.

Every value carries a machine mode. `SI` is four bytes, `DI` is eight, `CC` is a condition
code. The mode is on the node, not on the register, which is why the same pseudo can appear
in two modes and why `Rtx.mode` is a field rather than a property of a register table.

An insn is a linked list node. `prev` and `next` are uids, not indices, and the uids are not
contiguous because passes delete insns and never renumber. Reading the chain rather than the
printed order is the only way to know what the compiler thinks the order is, so `Listing`
offers both and `chain()` says when they disagree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Codes that print as an insn but are not one. A note is a marker, a barrier says control
#: cannot fall through here, a code_label is a jump target, and a debug_insn exists only to
#: keep the debugger informed and is not compiled into anything.
NOT_CODE = frozenset({"note", "barrier", "code_label", "debug_insn"})

#: The insn codes that carry a pattern the machine description has to match.
REAL = frozenset({"insn", "jump_insn", "call_insn"})

#: `-1` in the pattern slot means this insn has not been matched against the machine
#: description yet, which is true of everything the expander produces.
UNRECOGNISED = -1

_TOKEN = re.compile(
    r"""
    (?P<open>\()
  | (?P<close>\))
  | (?P<vecopen>\[)
  | (?P<vecclose>\])
  | (?P<string>"[^"]*"(?::\d+)*)    # "l1.c":7:7
  | (?P<brace>\{[^}]*\})            # {aarch64_bcond}
  | (?P<arrow>->)
  | (?P<symbol>[^\s()\[\]"{}]+)
    """,
    re.VERBOSE,
)

#: A bracket in an RTL dump is one of two unrelated things, and the dump does not say which.
#: `(parallel [ (set ...) (clobber ...) ])` is a vector of expressions, which is a real part of
#: the tree. `(reg:SI 103 [ n ])` is a note the printer adds so a human can tell which variable
#: a pseudo came from, and it is not RTL at all. The only difference is what comes next, so
#: that is what gets looked at.
VECTOR = "vector"

#: `reg/v:SI`, `plus:SI`, `const_int`, `int_list:REG_BR_PROB`. The flags are single letters
#: GCC prints for a bit it set on the node, `v` for a user variable and `i` for one that is
#: incoming or returned, and they are worth keeping because a reader will ask what they are.
_HEAD = re.compile(r"^(?P<code>[a-z_0-9]+)(?P<flags>(?:/[a-zA-Z])*)(?::(?P<mode>[A-Za-z0-9_]+))?$")

#: Where the insns begin. Everything before it is the expander talking to itself.
MARKER = ";; Full RTL generated for this function:"

FUNCTION = re.compile(r"^;; Function (?P<pretty>.+?) \((?P<detail>.*)\)\s*$")


@dataclass(frozen=True)
class Rtx:
    """One node of an RTL expression.

    `operands` holds a mix of nodes and strings, because RTL does. `(reg:SI 103 [ n ])` has
    a node for a code and two operands that are not nodes at all, a register number and the
    name of the variable it came from. Keeping them as strings is closer to the truth than
    inventing a wrapper for each.
    """

    code: str
    mode: str = ""
    flags: tuple[str, ...] = ()
    operands: tuple[Rtx | str, ...] = ()

    @property
    def children(self) -> tuple[Rtx, ...]:
        return tuple(o for o in self.operands if isinstance(o, Rtx))

    @property
    def leaves(self) -> tuple[str, ...]:
        return tuple(o for o in self.operands if isinstance(o, str))

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def register(self) -> int | None:
        """The register number, for a node that is a register."""
        if self.code != "reg" or not self.leaves:
            return None
        return int(self.leaves[0]) if self.leaves[0].lstrip("-").isdigit() else None

    @property
    def pseudo(self) -> bool:
        """Whether this is one of the infinitely many registers the expander pretends it has.

        GCC prints a hard register as its number and then its name, `(reg:SI 0 x0)`, and a
        pseudo as a number on its own. So the question is answered by what got printed rather
        than by a cutoff this file would have to keep per target.
        """
        if self.register is None:
            return False
        rest = [x for x in self.leaves[1:] if not x.startswith("[")]
        return not rest

    @property
    def value(self) -> int | None:
        """The integer, for a node that is a constant."""
        if self.code != "const_int" or not self.leaves:
            return None
        return int(self.leaves[0]) if self.leaves[0].lstrip("-").isdigit() else None

    def walk(self):
        yield self
        for kid in self.children:
            yield from kid.walk()

    @property
    def depth(self) -> int:
        return 1 + max((kid.depth for kid in self.children), default=0)

    @property
    def size(self) -> int:
        return sum(1 for _ in self.walk())

    @property
    def head(self) -> str:
        """The code with its flags and mode back on, the way the dump prints it."""
        return (
            self.code
            + "".join(f"/{f}" for f in self.flags)
            + (f":{self.mode}" if self.mode else "")
        )

    def __str__(self) -> str:
        inside = " ".join(str(o) for o in self.operands)
        if self.code == VECTOR:
            return f"[{inside}]"
        return f"({' '.join([self.head, inside]).strip()})"


@dataclass(frozen=True)
class Insn:
    """One entry in the printed instruction chain, whether or not it becomes code."""

    code: str
    uid: int
    prev: int
    next: int
    bb: int | None = None
    pattern: Rtx | None = None
    notes: Rtx | None = None
    loc: str = ""
    icode: int | None = None
    name: str = ""
    target: int | None = None
    extra: tuple[str, ...] = ()
    raw: str = ""

    @property
    def is_code(self) -> bool:
        """Whether this turns into machine instructions.

        A dump of a small function is mostly not code. Notes and debug insns outnumber the
        real ones about two to one at expand time, and a reader who counts lines and thinks
        they have counted instructions is going to be surprised later.
        """
        return self.code not in NOT_CODE

    @property
    def is_debug(self) -> bool:
        return self.code == "debug_insn"

    @property
    def recognised(self) -> bool:
        """Whether a machine description pattern has claimed this insn yet."""
        return self.icode is not None and self.icode != UNRECOGNISED

    @property
    def sets(self) -> Rtx | None:
        """The destination, for an insn that is a plain assignment."""
        if self.pattern is None or self.pattern.code != "set":
            return None
        first = self.pattern.operands[0] if self.pattern.operands else None
        return first if isinstance(first, Rtx) else None

    @property
    def registers(self) -> tuple[Rtx, ...]:
        if self.pattern is None:
            return ()
        return tuple(n for n in self.pattern.walk() if n.code == "reg")

    def __str__(self) -> str:
        return f"({self.code} {self.uid} {self.prev} {self.next}" + (
            f" {self.pattern})" if self.pattern else ")"
        )


@dataclass
class Listing:
    """One function's worth of RTL, plus everything the dump said before it."""

    function: str = ""
    detail: str = ""
    preamble: str = ""
    insns: list[Insn] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.insns)

    def __iter__(self):
        return iter(self.insns)

    @property
    def code(self) -> list[Insn]:
        return [i for i in self.insns if i.is_code and not i.is_debug]

    @property
    def blocks(self) -> list[int]:
        seen = []
        for insn in self.insns:
            if insn.bb is not None and insn.bb not in seen:
                seen.append(insn.bb)
        return seen

    def at(self, uid: int) -> Insn | None:
        return next((i for i in self.insns if i.uid == uid), None)

    def chain(self) -> list[Insn]:
        """The insns in the order `next` says they are in, starting from the first printed.

        Normally this is the printed order, and a dump where it is not is a dump worth
        looking at twice. Following the chain also stops at the first broken link rather than
        looping, so a mangled dump gives a short answer instead of hanging.
        """
        walk, seen = [], set()
        current = self.insns[0] if self.insns else None
        while current is not None and current.uid not in seen:
            seen.add(current.uid)
            walk.append(current)
            current = self.at(current.next) if current.next else None
        return walk

    def modes(self) -> dict[str, int]:
        """Every machine mode in the function, and how often it appears."""
        counted: dict[str, int] = {}
        for insn in self.insns:
            for node in insn.pattern.walk() if insn.pattern else ():
                if node.mode:
                    counted[node.mode] = counted.get(node.mode, 0) + 1
        return dict(sorted(counted.items(), key=lambda kv: (-kv[1], kv[0])))

    def codes(self) -> dict[str, int]:
        """Every RTX code in the function, and how often it appears."""
        counted: dict[str, int] = {}
        for insn in self.insns:
            for node in insn.pattern.walk() if insn.pattern else ():
                counted[node.code] = counted.get(node.code, 0) + 1
        return dict(sorted(counted.items(), key=lambda kv: (-kv[1], kv[0])))

    def registers(self) -> tuple[list[int], list[int]]:
        """The pseudos and the hard registers this function mentions, each sorted and unique."""
        pseudo, hard = set(), set()
        for insn in self.insns:
            for node in insn.registers:
                if node.register is None:
                    continue
                (pseudo if node.pseudo else hard).add(node.register)
        return sorted(pseudo), sorted(hard)

    def __str__(self) -> str:
        return f"{self.function}: {len(self.insns)} insns, {len(self.code)} of them code"


def _annotation(text: str, start: int) -> int | None:
    """Where the annotation opening at `start` ends, or None if this bracket starts a vector.

    Nested, because a memory reference prints its GIMPLE address inside the annotation and
    that has brackets of its own: `[0 MEM[(int *)_1]+0 S4 A32]` is one annotation, not two.
    """
    if text[start + 1 :].lstrip().startswith("("):
        return None
    depth = 0
    for n in range(start, len(text)):
        if text[n] == "[":
            depth += 1
        elif text[n] == "]":
            depth -= 1
            if depth == 0:
                return n + 1
    return None


def tokenize(text: str) -> list[str]:
    """The dump as tokens, with each annotation kept whole and exactly as it was printed."""
    tokens: list[str] = []
    skip = 0
    for m in _TOKEN.finditer(text):
        if m.start() < skip:
            continue
        if m.lastgroup == "vecopen":
            end = _annotation(text, m.start())
            if end is not None:
                tokens.append(text[m.start() : end])
                skip = end
                continue
        tokens.append(m.group(0))
    return tokens


def _head(token: str) -> tuple[str, tuple[str, ...], str]:
    found = _HEAD.match(token)
    if not found:
        return token, (), ""
    flags = tuple(f for f in found.group("flags").split("/") if f)
    return found.group("code"), flags, found.group("mode") or ""


def _sexp(tokens: list[str], i: int) -> tuple[Rtx | str, int]:
    """One s-expression starting at `tokens[i]`, and where it ended.

    Written as a loop over an index rather than with recursion on a stream, because the only
    thing that varies is how deep the nesting goes and an expand dump of a big function nests
    further than a reader would guess.
    """
    if tokens[i] == "[":
        i += 1
        items: list[Rtx | str] = []
        while i < len(tokens) and tokens[i] != "]":
            item, i = _sexp(tokens, i)
            items.append(item)
        return Rtx(code=VECTOR, operands=tuple(items)), i + 1
    if tokens[i] != "(":
        return tokens[i], i + 1
    i += 1
    if i >= len(tokens) or tokens[i] == ")":
        return Rtx(code="nil"), min(i + 1, len(tokens))

    code, flags, mode = _head(tokens[i])
    operands: list[Rtx | str] = []
    i += 1
    while i < len(tokens) and tokens[i] != ")":
        item, i = _sexp(tokens, i)
        operands.append(item)
    return Rtx(code=code, mode=mode, flags=flags, operands=tuple(operands)), i + 1


def _is_int(token: str) -> bool:
    return token.lstrip("-").isdigit()


def _insn(items: list[Rtx | str], raw: str) -> Insn | None:
    """One parsed insn list, read positionally at the front and by shape at the back.

    The front four are documented by the printer and can be trusted. `bb` is there when the
    fifth item is a number, which is how a note outside any block tells itself apart from an
    insn inside one.
    """
    head = [x for x in items[:5] if isinstance(x, str)]
    if len(head) < 4 or not all(_is_int(x) for x in head[1:4]):
        return None

    code = head[0]
    uid, prev, nxt = (int(x) for x in head[1:4])
    bb = int(head[4]) if len(head) > 4 and _is_int(head[4]) else None
    rest = items[4 + (bb is not None) :]

    nodes = [x for x in rest if isinstance(x, Rtx)]
    real = [n for n in nodes if n.code != "nil"]
    pattern = real[0] if real and code not in ("code_label", "barrier") else None
    notes = nodes[-1] if nodes and nodes[-1] is not pattern else None

    loc, name, icode, target = "", "", None, None
    words = [x for x in rest if isinstance(x, str)]
    extra = []
    for n, word in enumerate(words):
        if word.startswith('"'):
            loc = word.replace('"', "")
        elif word.startswith("{"):
            name = word.strip("{}")
            icode = int(words[n - 1]) if n and _is_int(words[n - 1]) else icode
        elif word == "->":
            target = int(words[n + 1]) if n + 1 < len(words) and _is_int(words[n + 1]) else None
        elif _is_int(word):
            pass
        else:
            extra.append(word)

    if icode is None:
        numbers = [w for w in words if _is_int(w)]
        # The pattern number is the last bare integer before the notes, and a jump target is
        # the only other one, so drop it before looking.
        if target is not None and numbers and int(numbers[-1]) == target:
            numbers = numbers[:-1]
        icode = int(numbers[-1]) if numbers and code in REAL else None

    return Insn(
        code=code,
        uid=uid,
        prev=prev,
        next=nxt,
        bb=bb,
        pattern=pattern,
        notes=notes,
        loc=loc,
        icode=icode,
        name=name,
        target=target,
        extra=tuple(extra),
        raw=raw.strip(),
    )


def _split(body: str) -> list[str]:
    """The dump text cut into one string per insn, by counting parentheses.

    A quoted filename can hold a parenthesis, so the counter skips strings. Anything outside
    a top level list is dropped, which is how the blank lines between insns disappear.
    """
    chunks, depth, start, quoted = [], 0, None, False
    for n, char in enumerate(body):
        if quoted:
            quoted = char != '"'
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            if depth == 0:
                start = n
            depth += 1
        elif char == ")" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                chunks.append(body[start : n + 1])
    return chunks


def _one(text: str, name: str = "") -> Listing:
    """One function's section of a dump, from its banner to the next one."""
    listing = Listing(function=name)
    for line in text.splitlines():
        found = FUNCTION.match(line)
        if found:
            listing.function = found.group("pretty")
            listing.detail = found.group("detail")
            break

    before, marker, after = text.partition(MARKER)
    listing.preamble = (before if marker else "").strip()
    body = after if marker else text

    for chunk in _split(body):
        parsed, _ = _sexp(tokenize(chunk), 0)
        if not isinstance(parsed, Rtx):
            continue
        insn = _insn([parsed.head, *parsed.operands], chunk)
        if insn is not None:
            listing.insns.append(insn)
    return listing


@dataclass
class RtlDump:
    """One parsed dump, which may hold several functions."""

    functions: dict[str, Listing] = field(default_factory=dict)
    text: str = ""
    name: str = ""

    def only(self) -> Listing:
        """The single function in this dump, for the common case of a one function file."""
        if len(self.functions) != 1:
            raise ValueError(f"expected one function, found {len(self.functions)}")
        return next(iter(self.functions.values()))

    def __getitem__(self, name: str) -> Listing:
        return self.functions[name]

    def __len__(self) -> int:
        return len(self.functions)

    def __iter__(self):
        return iter(self.functions.values())

    def __str__(self) -> str:
        return f"{self.name or 'dump'}: {', '.join(self.functions) or 'no functions'}"


def parse(text: str, name: str = "") -> RtlDump:
    """Read an RTL dump. Never raises on unfamiliar content.

    Anything the reader cannot make an insn out of is skipped rather than raised on, for the
    same reason the GIMPLE parser keeps an `UnparsedStmt`: a dump format that shifts by one
    field should cost one number in one lesson, not forty lessons at once.

    A dump holds one section per function, and a file with seven functions in it produces
    seven banners and seven instruction chains. The uids restart at 1 in each, which is why
    they are split here rather than concatenated into one long chain.
    """
    dump = RtlDump(text=text, name=name)
    marks = [m.start() for m in re.finditer(r"^;; Function ", text, re.MULTILINE)]
    cuts = marks or [0]
    for n, start in enumerate(cuts):
        end = cuts[n + 1] if n + 1 < len(cuts) else len(text)
        listing = _one(text[start:end], name if not marks else "")
        if listing.insns or listing.function:
            dump.functions[listing.function or f"function {n}"] = listing
    return dump
