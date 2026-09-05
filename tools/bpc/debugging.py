"""Section 2 of `BP-DEBUGGING`, generated from the three files GCC debugs itself with.

    gcc/gdbinit.in      the commands, the breakpoints and the skip list, installed as .gdbinit
    gcc/gdbhooks.py     the pretty printers, loaded by gdbinit.in
    gcc/dbgcnt.def      every debug counter, which is the non interactive way to bisect a pass

None of the three is documented anywhere a user would look. `gdbinit.in` documents itself, in
the sense that every command has a `document` block next to it, but the file is only ever read
by gdb and the twenty two commands in it appear in no manual. `gdbhooks.py` has a long comment
at the top and no list. `dbgcnt.def` is a list and nothing else.

They are also the three files most likely to be out of date with respect to the compiler, for
the same reason: nothing builds them and nothing tests them. A command that calls a function
which has been renamed fails at the moment somebody needs it, and the failure looks like the
debugger being broken rather than like GCC's own tooling having rotted. So the generator reads
the function each command calls and looks it up in the tree, and a command whose target has
gone gets a row that says so instead of quietly reading like the rest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tools.bpc import generator
from tools.bpc.gccsrc import SourceError, read
from tools.bpc.gccsrc import parse_def as parse_def_file

GDBINIT = "gdbinit.in"
GDBHOOKS = "gdbhooks.py"
DBGCNT = "dbgcnt.def"

# Where a command's target might be defined. The `debug_*` family is spread across the whole
# compiler and two of the commands reach into a front end, so the scan is wide on purpose: a
# row that says a function is missing when it is one directory over is worse than no row.
SUBDIRS = ("", "c", "c-family", "cp", "analyzer", "diagnostics")

# The line every command body starts with, which sets $debug_arg from $arg0 or from the last
# printed value. It carries no information about the command and is dropped from the table.
PREAMBLE = 'eval "set $debug_arg = $%s", $argc ? "arg0" : ""'

CALLS = re.compile(r"^\s*(?:call|output|print)\s+\(?\s*(?P<fn>[A-Za-z_][\w:]*)\s*\(")
# `output (enum tree_code) $x` is a cast and not a call, and the two are the same shape.
NOT_A_FUNCTION = {"enum", "struct", "union", "const", "unsigned", "signed"}
BREAKS = re.compile(r"^\s*(?:b|break)\s+(?P<what>\S+)\s*$")
SETTING = re.compile(r"^\s*set\s+(?P<what>.+?)\s*$")
SKIPPING = re.compile(r"^\s*skip\s+(?P<what>.+?)\s*$")
ALIAS = re.compile(r"^\s*alias\s+(?P<short>\S+)\s*=\s*(?P<long>\S+)\s*$")

PY_COMMAND = re.compile(
    r"class\s+(?P<cls>\w+)\((?:gdb\.Command|gdb\.Parameter)\):\s*\n"
    r'\s*"""(?P<doc>.*?)"""'
    r".*?(?:gdb\.(?:Command|Parameter)\.__init__\(\s*self\s*,|super\([^)]*\)\.__init__\()"
    r"\s*'(?P<name>[^']+)'",
    re.DOTALL,
)

PRINTER_TYPES = re.compile(
    r"pp\.add_printer_for_types\(\s*\[(?P<types>.*?)\]\s*,\s*(?P<name>'[^']*'|\"[^\"]*\")\s*,"
    r"\s*(?P<cls>\w+)",
    re.DOTALL,
)
PRINTER_REGEX = re.compile(
    r"pp\.add_printer_for_regex\(\s*r?(?P<pattern>'[^']*'|\"[^\"]*\")\s*,"
    r"\s*(?P<name>'[^']*'|\"[^\"]*\")\s*,\s*(?P<cls>\w+)",
    re.DOTALL,
)


@dataclass(frozen=True)
class Command:
    """One `define` in `gdbinit.in`, with the `document` block that goes with it."""

    name: str
    body: tuple[str, ...]
    doc: tuple[str, ...]
    line: int

    @property
    def summary(self) -> str:
        """What the command prints, in one line.

        The convention in the file is that the first line of the documentation names the C
        level equivalent and the second says what it prints, so the second line is the one a
        description column wants. Four of the commands do not follow the convention and have
        no `GCC hook:` line, and for those the first line is the description.
        """
        lines = [one for one in self.doc if one.strip() and not one.startswith("See also")]
        if lines and lines[0].startswith("GCC hook:"):
            lines = lines[1:]
        # The blocks are hard wrapped, so a sentence is one to three lines. Stopping on a
        # colon is for the one command whose description is a list rather than a sentence.
        held: list[str] = []
        for line in lines:
            held.append(line.strip())
            if held[-1].endswith((".", ":")):
                break
        return " ".join(held)

    @property
    def hook(self) -> str:
        """The C level equivalent the documentation claims, without the `GCC hook:` label."""
        for line in self.doc:
            if line.startswith("GCC hook:"):
                return line[len("GCC hook:") :].strip()
        return ""

    @property
    def calls(self) -> str:
        """The compiler function the command reaches into, or an empty string.

        Read off the body rather than off the documentation, because a command whose target
        was renamed keeps its old documentation and the body is the half gdb executes.
        """
        for line in self.body:
            m = CALLS.match(line)
            if m is not None and m.group("fn") not in NOT_A_FUNCTION:
                return m.group("fn")
        return ""

    @property
    def breaks(self) -> str:
        """The function the command puts a breakpoint on, for the two that do that."""
        for line in self.body:
            if (m := BREAKS.match(line)) is not None:
                return m.group("what")
        return ""


def commands(root: Path) -> list[Command]:
    """Every `define` block in `gdbinit.in`, in file order, with its documentation."""
    text = read(root / GDBINIT)
    found: list[Command] = []
    docs: dict[str, tuple[str, ...]] = {}
    name: str | None = None
    kind = ""
    at = 0
    held: list[str] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if name is None:
            if line.startswith("define "):
                kind, name, at, held = "define", line[len("define ") :].strip(), n, []
            elif line.startswith("document "):
                kind, name, at, held = "document", line[len("document ") :].strip(), n, []
            continue
        if line.strip() == "end":
            if kind == "define":
                body = tuple(one for one in held if one.strip() and one.strip() != PREAMBLE)
                found.append(Command(name=name, body=body, doc=(), line=at))
            else:
                docs[name] = tuple(held)
            name = None
            continue
        held.append(line)
    if not found:
        raise SourceError(f"{root / GDBINIT} has no `define` blocks in it")
    return [Command(name=c.name, body=c.body, doc=docs.get(c.name, ()), line=c.line) for c in found]


def aliases(root: Path) -> dict[str, str]:
    """The `alias short = long` lines, keyed by the command they are short for."""
    out: dict[str, str] = {}
    for line in read(root / GDBINIT).splitlines():
        if (m := ALIAS.match(line)) is not None:
            out[m.group("long")] = m.group("short")
    return out


def startup(root: Path) -> tuple[list[str], list[str], list[str]]:
    """What the file does outside a `define`: breakpoints, settings, and skips.

    These are the lines that change how the debugger behaves the moment it starts, and they
    are the reason a session against cc1 does not look like a session against any other
    program. Read separately from the commands because a reader has to know about them
    whether or not they ever type one of the shorthands.
    """
    breaks: list[str] = []
    settings: list[str] = []
    skips: list[str] = []
    inside = False
    for line in read(root / GDBINIT).splitlines():
        if line.startswith(("define ", "document ")):
            inside = True
            continue
        if inside:
            inside = line.strip() != "end"
            continue
        if (m := BREAKS.match(line)) is not None:
            breaks.append(m.group("what"))
        elif (m := SETTING.match(line)) is not None:
            settings.append(m.group("what"))
        elif (m := SKIPPING.match(line)) is not None:
            skips.append(m.group("what"))
    return breaks, settings, skips


def defined(root: Path, function: str) -> bool:
    """Whether a name the gdbinit calls is still defined anywhere the scan looks.

    A textual search for the name followed by an open parenthesis at the start of a line,
    which is how GCC writes a definition. Overloads, declarations in headers and calls all
    match too, and that is fine: the question is whether the name still exists at all, and
    a rename is what this is looking for.
    """
    bare = function.rsplit("::", 1)[-1]
    needle = re.compile(rf"^[\w:*& ]*\b{re.escape(bare)}\s*\(", re.MULTILINE)
    for sub in SUBDIRS:
        directory = root / sub if sub else root
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.cc")) + sorted(directory.glob("*.h")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if bare in text and needle.search(text):
                return True
    return False


def counters(root: Path) -> list[str]:
    return [entry.name for entry in parse_def_file(read(root / DBGCNT), "DEBUG_COUNTER")]


@dataclass(frozen=True)
class Printer:
    """One entry in `build_pretty_printer`, which is one type gdb prints GCC's way."""

    name: str
    matches: str
    cls: str


def type_list(raw: str) -> str:
    """The quoted type names out of an `add_printer_for_types` argument.

    The list is hard wrapped over as many as nineteen lines and one of them has a Python
    comment in the middle of it, so anything unquoted is dropped rather than split on.
    """
    names = re.findall(r"'([^']*)'|\"([^\"]*)\"", raw)
    return ", ".join(f"`{a or b}`" for a, b in names)


def printers(root: Path) -> list[Printer]:
    """Every pretty printer registered by `gdbhooks.py`, in registration order.

    The loop at the end of `build_pretty_printer` registers one printer per machine mode
    class with the class name as the printer name, and is not in this list, because its
    argument is a loop variable rather than a literal. The section says so underneath.
    """
    text = read(root / GDBHOOKS)
    found: list[tuple[int, Printer]] = []
    for m in PRINTER_TYPES.finditer(text):
        one = Printer(
            name=m.group("name")[1:-1], matches=type_list(m.group("types")), cls=m.group("cls")
        )
        found.append((m.start(), one))
    for m in PRINTER_REGEX.finditer(text):
        one = Printer(
            name=m.group("name")[1:-1],
            matches=f"anything matching `{m.group('pattern')[1:-1]}`",
            cls=m.group("cls"),
        )
        found.append((m.start(), one))
    if not found:
        raise SourceError(f"{root / GDBHOOKS} registered no pretty printers")
    return [one for _, one in sorted(found, key=lambda pair: pair[0])]


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


def equivalent(root: Path, one: Command) -> tuple[str, str]:
    """The `Equivalent to` cell for a command, and a complaint if the target has gone."""
    if one.breaks:
        target = one.breaks
        gone = "" if defined(root, target) else f"`{one.name}` breaks on `{target}`"
        return f"breakpoint on `{target}`", gone
    if one.calls:
        gone = "" if defined(root, one.calls) else f"`{one.name}` calls `{one.calls}`"
        shown = one.hook or f"{one.calls} ()"
        return f"`{shown}`", gone
    return (f"`{one.hook}`" if one.hook else "gdb alone"), ""


@generator("gdb-commands")
def gdb_commands(root: Path) -> str:
    every = commands(root)
    short = aliases(root)
    rows = [
        "| Command | Alias | Equivalent to | Calls into the compiler | What it prints |",
        "|---|---|---|---|---|",
    ]
    missing: list[str] = []
    for one in every:
        shown, gone = equivalent(root, one)
        if gone:
            missing.append(gone)
            shown += ", **which is not in the tree**"
        alias = f"`{short[one.name]}`" if one.name in short else ""
        into = "yes" if one.calls else "no"
        rows.append(f"| `{one.name}` | {alias} | {shown} | {into} | {cell(one.summary)} |")

    live = sum(1 for one in every if one.calls)
    summary = (
        f"`gcc/gdbinit.in` defines **{len(every)} commands**. The build installs it as "
        f"`.gdbinit` in the `gcc` subdirectory of the build tree, so they exist for a "
        f"debugger started from there and nowhere else. {live} of them work by calling a "
        f"function inside the compiler, which needs a process that is stopped somewhere the "
        f"call can succeed; the rest read memory and work on a core file. The last column is "
        f"the command's own `document` block, which is the only documentation any of them "
        f"has, and the column before it is what that block claims the command is equivalent "
        f"to. Where the claim and the body disagree, the body is what runs."
    )
    tail = ["", "Targets the scan could not find: " + "; ".join(missing) + "."] if missing else []
    return "\n".join(["", summary, "", *rows, *tail])


@generator("gdb-startup")
def gdb_startup(root: Path) -> str:
    breaks, settings, skips = startup(root)
    files = [s.split(" ", 1)[1] for s in skips if s.startswith("file ")]
    functions = [s for s in skips if not s.startswith("file ")]
    lines = [
        "",
        f"Outside the command definitions, the file sets **{len(breaks)} breakpoints**, "
        f"changes **{len(settings)} debugger settings**, and puts **{len(files)} headers and "
        f"{len(functions)} functions** on the skip list. All of it happens at startup, "
        f"before the reader has typed anything.",
        "",
        "| What | Value | Why it is there |",
        "|---|---|---|",
    ]
    for what in breaks:
        lines.append(f"| breakpoint | `{what}` | {_break_reason(what)} |")
    for what in settings:
        lines.append(f"| setting | `set {what}` | {_setting_reason(what)} |")
    lines += [
        "",
        "The skip list is what stops `step` disappearing into an accessor. The headers "
        "skipped whole are "
        + ", ".join(f"`{f}`" for f in files)
        + ", and the named functions are "
        + ", ".join(f"`{f}`" for f in functions)
        + ".",
    ]
    return "\n".join(lines)


REASONS = {
    "fancy_abort": "GCC's own `abort`, which every failed assertion goes through",
    "internal_error": "where an ICE is reported, so the debugger stops with the stack intact",
    "exit": "so a compiler that decided to leave does not take the session with it",
    "abort": "the library one, in case something reached it without going through GCC's",
}

SETTINGS = {
    "pagination off": "so the `skip` output below does not stop for a keypress",
    "unwindonsignal on": "so a `call` that crashes unwinds instead of leaving the process wedged",
    "complaints 0": "so gdb stops reporting symbols it does not understand in this binary",
    "check type off": "so an inferior call can be made without casting an address first",
}


def _break_reason(what: str) -> str:
    return REASONS.get(what, "set by `gdbinit.in`")


def _setting_reason(what: str) -> str:
    return SETTINGS.get(what, "set by `gdbinit.in`")


@generator("gdb-printers")
def gdb_printers(root: Path) -> str:
    every = printers(root)
    rows = ["| Printer | Applies to | Class |", "|---|---|---|"]
    for one in every:
        rows.append(f"| `{one.name}` | {one.matches} | `{one.cls}` |")
    summary = (
        f"`gcc/gdbhooks.py` registers **{len(every)} pretty printers**, and `gdbinit.in` "
        f"loads it. They are what makes `print stmt` produce a GIMPLE statement rather than "
        f"a pointer, and they are the reason a debugger session against cc1 looks nothing "
        f"like one against a program with no hooks installed. A printer is a Python class "
        f"that reads the same fields a human would, so a printer can be wrong in a way the "
        f"compiler is not."
    )
    tail = (
        "A loop after the last of these registers one more printer for each of "
        "`scalar_mode`, `scalar_int_mode`, `scalar_float_mode` and `complex_mode`. It is not "
        "in the table because its arguments are a loop variable, and it is the reason the "
        "count above is lower than the number of types gdb ends up knowing about."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


@dataclass(frozen=True)
class PyCommand:
    """One gdb command or parameter implemented in Python by `gdbhooks.py`."""

    name: str
    cls: str
    doc: str


def py_commands(root: Path) -> list[PyCommand]:
    """The commands `gdbhooks.py` adds, which are the ones `gdbinit.in` does not have.

    A shorthand in `gdbinit.in` is a canned `call`. These are Python, so they can do things
    a canned call cannot: read `passes.def` off disk, complete a pass name, write a dump to
    a file. That is why the interesting three are here rather than there.
    """
    found = []
    for m in PY_COMMAND.finditer(read(root / GDBHOOKS)):
        # The first sentence, which in all four cases is the summary. These docstrings are
        # hard wrapped and the sentence ends mid line, so the cut is on the text and not on
        # a line boundary.
        paragraph = " ".join(m.group("doc").strip().split())
        stop = paragraph.find(". ")
        doc = paragraph if stop < 0 else paragraph[: stop + 1]
        found.append(PyCommand(name=m.group("name"), cls=m.group("cls"), doc=doc))
    if not found:
        raise SourceError(f"{root / GDBHOOKS} defines no gdb commands")
    return found


@generator("gdb-python-commands")
def gdb_python_commands(root: Path) -> str:
    every = py_commands(root)
    rows = ["| Command | Class | What it is for |", "|---|---|---|"]
    for one in every:
        rows.append(f"| `{one.name}` | `{one.cls}` | {cell(one.doc)} |")
    summary = (
        f"`gcc/gdbhooks.py` also defines **{len(every)} commands** of its own, in Python. "
        f"They are separate from the shorthands above because a shorthand is a canned `call` "
        f"and these are programs: one of them reads `passes.def` off disk to complete a pass "
        f"name, and two of them write a dump to a file and open it."
    )
    return "\n".join(["", summary, "", *rows])


@generator("debug-counters")
def debug_counters(root: Path) -> str:
    every = counters(root)
    summary = (
        f"`gcc/dbgcnt.def` declares **{len(every)} debug counters**. Each one is a call to "
        f"`dbg_cnt (name)` somewhere in a pass, which returns true until the counter passes "
        f"the limit given by `-fdbg-cnt=name:limit` and false afterwards. Setting a limit "
        f"turns a pass off partway through, which makes a miscompilation bisectable without "
        f"a debugger: halve the limit until the smallest number that still produces bad code "
        f"is found, and that is the transformation to look at. `-fdbg-cnt-list` prints the "
        f"list from the compiler itself."
    )
    columns = 4
    rows = ["| Counters |", "|---|"]
    for start in range(0, len(every), columns):
        rows.append("| " + ", ".join(f"`{n}`" for n in every[start : start + columns]) + " |")
    return "\n".join(["", summary, "", *rows])
