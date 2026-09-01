"""Where a piece of IR came from in the source, at every level GCC prints one.

A compiler course spends most of its time on one representation at a time. The thing that
is genuinely hard to see, and that this module exists to make visible, is that all of them
are the same program. One line of C is a few GENERIC trees, then a few GIMPLE statements,
then a handful of RTL insns, then some instructions, and GCC carries a source location
through all four so that a debugger can walk it back.

That location is the only honest join between the levels. Nothing else survives: the SSA
names are gone by RTL, the pseudo registers are gone by assembly, and matching statements
up by eye is guesswork the moment a pass reorders anything.

Each level spells a location differently, which is the whole reason this file is not three
lines long.

    GENERIC and GIMPLE   [l1.c:6:27 discrim 1] i_9 = i_2 + 1;
    RTL                  (insn 15 14 16 2 (set ...) "l1.c":6:21 discrim 2 -1
    assembly             .loc 1 6 27 is_stmt 1 discriminator 1

The tree dumps print locations only when asked with the `lineno` modifier, RTL prints them
always, and assembly prints them only with `-g`. So a ladder needs a compilation recorded
with both, which is what `just corpus` does.

The discriminator is how GCC tells apart several pieces of code that share a line and
column, which happens constantly in a `for` header. It is kept because dropping it merges
the loop increment into the loop test, and those are the two things a reader is trying to
tell apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

LEVELS = ("generic", "gimple", "rtl", "asm")

LEVEL_NAMES = {
    "generic": "GENERIC",
    "gimple": "GIMPLE",
    "rtl": "RTL",
    "asm": "assembly",
}

# [l1.c:6:27 discrim 1], and the column is missing on a few locations GCC builds by hand.
TREE_LOC = re.compile(
    r"\[(?P<file>[^\[\]:\s]+):(?P<line>\d+)(?::(?P<col>\d+))?(?: discrim (?P<discrim>\d+))?\]"
)
# "l1.c":6:21 discrim 2
RTL_LOC = re.compile(r'"(?P<file>[^"]+)":(?P<line>\d+):(?P<col>\d+)(?: discrim (?P<discrim>\d+))?')
# .loc 1 6 27 is_stmt 1 discriminator 1, where 1 is an index into the .file directives.
ASM_LOC = re.compile(r"^\s*\.loc\s+(?P<file>\d+)\s+(?P<line>\d+)(?:\s+(?P<col>\d+))?(?P<rest>.*)$")
ASM_FILE = re.compile(r'^\s*\.file\s+(?P<index>\d+)\s+"(?P<name>[^"]+)"')
ASM_DISCRIM = re.compile(r"discriminator\s+(\d+)")

# An RTL insn starts in the first column and everything indented under it belongs to it.
RTL_HEAD = re.compile(r"^\((?P<kind>[a-z_]+)\b")


@dataclass(frozen=True, order=True)
class Loc:
    """One source location. Two pieces of IR are on the same rung when these are equal."""

    line: int
    col: int = 0
    discrim: int = 0
    file: str = ""

    def __str__(self) -> str:
        where = f"{self.file}:" if self.file else ""
        tail = f" discrim {self.discrim}" if self.discrim else ""
        return f"{where}{self.line}:{self.col}{tail}"


@dataclass
class Item:
    """One line of one level, and where it says it came from.

    `loc` is the location GCC printed in front of the item. When there is none, it is the
    first location the item mentions anywhere, which is how a PHI whose arguments carry
    locations still lands on a rung instead of falling off the ladder.
    """

    level: str
    text: str
    loc: Loc | None = None
    debug: bool = False

    @property
    def line(self) -> int:
        return self.loc.line if self.loc else 0

    def __str__(self) -> str:
        return self.text


@dataclass
class Rung:
    """One source line, and everything the four levels turned it into."""

    line: int
    source: str
    items: dict[str, list[Item]] = field(default_factory=dict)

    def at(self, level: str) -> list[Item]:
        return self.items.get(level, [])

    def counts(self) -> dict[str, int]:
        return {level: len(self.at(level)) for level in LEVELS}

    @property
    def empty_levels(self) -> list[str]:
        """Levels this line left nothing behind at, which is usually the interesting part."""
        return [level for level in LEVELS if not self.at(level)]

    def __str__(self) -> str:
        counts = ", ".join(f"{n} {LEVEL_NAMES[k]}" for k, n in self.counts().items())
        return f"line {self.line}: {counts}"


@dataclass
class Ladder:
    """Every source line of one function, at four levels."""

    file: str
    rungs: list[Rung] = field(default_factory=list)
    levels: tuple[str, ...] = LEVELS

    def rung(self, line: int) -> Rung:
        for r in self.rungs:
            if r.line == line:
                return r
        have = ", ".join(str(r.line) for r in self.rungs) or "none"
        raise KeyError(f"no rung for source line {line}. Lines with anything on them: {have}")

    @property
    def lines(self) -> list[int]:
        return [r.line for r in self.rungs]

    def __str__(self) -> str:
        return f"{self.file}: {len(self.rungs)} source line(s) across {len(self.levels)} levels"


def locs_in(text: str, style: str = "tree") -> list[Loc]:
    """Every location in a piece of text, in the order it appears."""
    pattern = TREE_LOC if style == "tree" else RTL_LOC
    out = []
    for m in pattern.finditer(text):
        out.append(
            Loc(
                line=int(m.group("line")),
                col=int(m.group("col") or 0),
                discrim=int(m.group("discrim") or 0),
                file=m.group("file"),
            )
        )
    return out


def strip_locs(text: str, style: str = "tree") -> str:
    """The same text with the locations taken out, which is what a reader wants to see.

    The location is already the row the item is sitting on, so printing it again inside the
    statement is noise. A tree statement can carry one in the middle of itself, as in
    `s = [l1.c:7:7] s + i;`, so the gap it leaves behind is closed up too. RTL keeps its
    indentation exactly, because in RTL the indentation is the nesting of the expression.
    """
    if style != "tree":
        # The space in front goes with it, or the insn ends up with a gap in the middle.
        out = re.sub(r"[ \t]*" + RTL_LOC.pattern, "", text)
        return "\n".join(line.rstrip() for line in out.splitlines()).strip()
    out = TREE_LOC.sub("", text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return re.sub(r"\(\s+", "(", out).strip()


LEADING_TREE_LOC = re.compile(r"^(?P<indent>[ \t]*)" + TREE_LOC.pattern + r"[ \t]?")


def take_loc(line: str) -> tuple[Loc | None, str]:
    """Split off the location GCC printed in front of a statement, keeping the indentation.

    The indentation is kept because the GIMPLE parser reads it: a declaration is a line
    indented by exactly two spaces, and a statement that lost its indent along with its
    location would come back as a declaration.
    """
    m = LEADING_TREE_LOC.match(line)
    if not m:
        return None, line
    loc = Loc(
        line=int(m.group("line")),
        col=int(m.group("col") or 0),
        discrim=int(m.group("discrim") or 0),
        file=m.group("file"),
    )
    return loc, m.group("indent") + line[m.end() :]


def tree_items(text: str, level: str, function: str | None = None) -> list[Item]:
    """Statements out of a GENERIC or GIMPLE dump recorded with the `lineno` modifier.

    One item per line that has a location on it. Lines with no location at all are the
    braces, the block headers and the declarations, none of which came from one place in
    the source, so leaving them out is not a loss.
    """
    items: list[Item] = []
    current = None
    for raw in text.splitlines():
        header = re.match(r"^;; Function (?P<pretty>\S+)", raw)
        if header:
            current = header.group("pretty")
            continue
        if function is not None and current is not None and current != function:
            continue
        found = locs_in(raw, "tree")
        if not found:
            continue
        body = strip_locs(raw, "tree")
        if not body:
            continue
        items.append(
            Item(level=level, text=body, loc=found[0], debug=body.lstrip("# ").startswith("DEBUG"))
        )
    return items


def rtl_insns(text: str) -> list[str]:
    """Split an RTL dump into insns. One starts in the first column, and its operands are
    indented under it, so the first column is the only boundary that needs looking for."""
    out: list[str] = []
    current: list[str] | None = None
    for raw in text.splitlines():
        if RTL_HEAD.match(raw):
            if current:
                out.append("\n".join(current).rstrip())
            current = [raw]
        elif current is not None:
            if raw.strip():
                current.append(raw)
            else:
                out.append("\n".join(current).rstrip())
                current = None
    if current:
        out.append("\n".join(current).rstrip())
    return out


def rtl_items(text: str) -> list[Item]:
    """Insns out of an RTL dump, each with the location printed after its pattern.

    A `note` carries no location and is dropped. A `debug_insn` does carry one, and is kept
    but marked, because a ladder that hides them is lying about what is in the dump.
    """
    items = []
    for insn in rtl_insns(text):
        kind = RTL_HEAD.match(insn).group("kind")
        if kind in ("note", "barrier"):
            continue
        found = locs_in(insn, "rtl")
        if not found:
            continue
        items.append(
            Item(
                level="rtl",
                text=strip_locs(insn, "rtl"),
                loc=found[0],
                debug=kind == "debug_insn",
            )
        )
    return items


def asm_items(text: str) -> list[Item]:
    """Instructions out of assembly built with `-g`.

    A `.loc` directive does not label the instruction next to it, it opens a run: every
    instruction after it belongs to that location until the next `.loc`. So this walks the
    file carrying the last one it saw, which is also exactly how a debugger reads it.

    Directives and labels are dropped. They are real output but they are not the thing a
    reader is counting when they ask what one line of C cost.
    """
    files: dict[str, str] = {}
    items: list[Item] = []
    at: Loc | None = None

    for raw in text.splitlines():
        named = ASM_FILE.match(raw)
        if named:
            # GCC writes an absolute path here whenever the source was not in the working
            # directory, and the tree dumps write the bare name, so this keeps the two ends
            # of the ladder talking about the same file.
            files[named.group("index")] = named.group("name").rsplit("/", 1)[-1]
            continue
        loc = ASM_LOC.match(raw)
        if loc:
            discrim = ASM_DISCRIM.search(loc.group("rest") or "")
            at = Loc(
                line=int(loc.group("line")),
                col=int(loc.group("col") or 0),
                discrim=int(discrim.group(1)) if discrim else 0,
                file=files.get(loc.group("file"), loc.group("file")),
            )
            continue
        body = raw.strip()
        if not body or body.startswith((".", "//", "#", ";")) or body.endswith(":"):
            continue
        if at is not None:
            items.append(Item(level="asm", text=body, loc=at))
    return items


def ladder(
    source: str,
    generic: str = "",
    gimple: str = "",
    rtl: str = "",
    asm: str = "",
    function: str | None = None,
    debug: bool = False,
) -> Ladder:
    """Build the ladder from one compilation.

    `debug` keeps the debug markers. They are off by default because there are more of them
    than there is code, and what they are for is building the line table that this module
    is reading, so a ladder full of them is a picture of its own plumbing.
    """
    lines = source.splitlines()
    by_level = {
        "generic": tree_items(generic, "generic", function) if generic else [],
        "gimple": tree_items(gimple, "gimple", function) if gimple else [],
        "rtl": rtl_items(rtl) if rtl else [],
        "asm": asm_items(asm) if asm else [],
    }

    file = ""
    for items in by_level.values():
        for item in items:
            if item.loc and item.loc.file:
                file = item.loc.file
                break
        if file:
            break

    wanted = sorted({i.line for items in by_level.values() for i in items if debug or not i.debug})
    rungs = []
    for line in wanted:
        rung = Rung(line=line, source=lines[line - 1] if 0 < line <= len(lines) else "")
        for level, items in by_level.items():
            rung.items[level] = [i for i in items if i.line == line and (debug or not i.debug)]
        rungs.append(rung)
    return Ladder(file=file, rungs=rungs)
