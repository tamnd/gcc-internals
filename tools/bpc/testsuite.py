"""Section 2 of `BP-TESTSUITE`, generated from the harness GCC ships in its own tree.

    gcc/testsuite/lib/*.exp     the directives, the scan procedures and the torture options
    gcc/*/Make-lang.in          which languages register a `check-` target and how far it splits
    gcc/testsuite/*/            the directories DejaGnu finds by name

Four lists, and the same argument applies to all four. GCC's `sourcebuild.texi` documents the
directives in prose, in the order somebody thought of them, and documents no version of itself:
a directive added in GCC 15 and a directive removed in GCC 12 read identically in a manual
checked out at the wrong tag. The scan procedures are documented as a family with the variants
described in a sentence rather than listed. The per language parallel split is in a makefile
comment. The torture options are a Tcl list in the middle of `gcc-dg.exp`.

So all four are read out of the pinned tree. The parsing is textual, because the alternative is
running Tcl, and a table that is wrong in a way a reader can check against the file beats a
table that needs an interpreter to produce.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tools.bpc import generator
from tools.bpc.gccsrc import SourceError

LIB = Path("testsuite") / "lib"
TESTS = Path("testsuite")
MAKEFILE = Path("Makefile.in")

# `proc name { params }`, at the start of a line, which is how every proc in the harness is
# written. A continuation line or an indented proc would be missed and there are none.
PROC = re.compile(r"^proc\s+(?P<name>[\w:.<>+-]+)\s*\{(?P<params>[^}]*)\}")

# DejaGnu hands every directive the line number it was written on as the first argument, so a
# directive either takes `args` and digs the line out of it, or names it. Anything else in the
# harness with a `dg-` name is a helper the harness calls itself, not something a test writes.
DIRECTIVE_HEAD = ("args", "linenr")

# The two families whose negation is spelled in the middle of the name rather than at the end.
# Everything else in the harness puts `-not` last, and these two would otherwise each get a
# row of their own, next to the row they are the negation of.
INFIX_NOT = {"scan-not-weak": "scan-weak", "scan-not-hidden": "scan-hidden"}

# Stripped from the end of a scan procedure's name to find the family it belongs to. Order
# matters: `-dem-not` has to come off before `-not` would take half of it.
VARIANTS = ("-dem-not", "-dem", "-times", "-bound", "-not", "-absence")

# What each file's procedures read. The distinction is the whole reason there are eight files
# rather than one: a dump is found by globbing for a suffix and the assembly is a fixed name,
# so the two cannot share an implementation even though they share an interface.
READS = {
    "scanasm.exp": "the assembly, or another file the compiler wrote beside it",
    "scandump.exp": "any dump, named by the suffix given as an argument",
    "scantree.exp": "a GIMPLE dump, from `-fdump-tree-`",
    "scanipa.exp": "an IPA dump, from `-fdump-ipa-`",
    "scanrtl.exp": "an RTL dump, from `-fdump-rtl-`",
    "scanlang.exp": "a front end dump, from `-fdump-lang-`",
    "scanwpaipa.exp": "an LTO dump written by the WPA stage",
    "scanoffloadipa.exp": "an IPA dump from an offload compiler",
    "scanoffloadrtl.exp": "an RTL dump from an offload compiler",
    "scanoffloadtree.exp": "a GIMPLE dump from an offload compiler",
    "scansarif.exp": "the SARIF file, from `-fdiagnostics-format=sarif-file`",
    "gcc-dg.exp": "",
}

# The two families in `gcc-dg.exp`, which is the one file whose scan procedures do not all
# read the same kind of thing. `scan-module` decompresses a Fortran `.mod`, which is a gzip
# stream, and `scan-symbol` reads the symbol table of the linked executable.
READS_BY_BASE = {
    "scan-module": "a Fortran `.mod` file, decompressed",
    "scan-symbol": "the symbol table of the linked executable",
}

TORTURE = re.compile(r"set DG_TORTURE_OPTIONS \[list \\\n(?P<body>.*?)\]", re.DOTALL)
LANG_CHECK = re.compile(r"^lang_checks\s*\+=\s*(?P<targets>.+)$", re.MULTILINE)
LANG_PARALLEL = re.compile(r"^lang_checks_parallelized\s*\+=\s*(?P<targets>.+)$", re.MULTILINE)
PARALLELIZE = re.compile(r"^check_(?P<tool>\S+?)_parallelize\s*=\s*(?P<count>\d+)", re.MULTILINE)


def slurp(path: Path) -> str:
    if not path.is_file():
        raise SourceError(f"{path} is not in the tree")
    return path.read_text(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Proc:
    """One Tcl procedure in the harness, with the comment block written above it."""

    name: str
    params: tuple[str, ...]
    file: str
    line: int
    comment: str

    @property
    def summary(self) -> str:
        """The first sentence of the comment block, or an empty string when there is none.

        Most of the harness is commented and some of it is not, and an empty cell is the
        honest rendering of the second case. Inventing a description for a procedure whose
        author wrote none would put words in the table that are not in the tree.
        """
        stop = self.comment.find(". ")
        return self.comment if stop < 0 else self.comment[: stop + 1]

    @property
    def is_directive(self) -> bool:
        return bool(self.params) and self.params[0] in DIRECTIVE_HEAD


def procs(path: Path) -> list[Proc]:
    """Every top level procedure in one `.exp` file, with the comment above it.

    The comment is the contiguous run of `#` lines above the `proc`, skipping blank lines in
    between, which is the layout the whole harness uses.
    """
    lines = slurp(path).splitlines()
    found: list[Proc] = []
    for n, line in enumerate(lines):
        m = PROC.match(line)
        if m is None:
            continue
        at = n - 1
        while at >= 0 and not lines[at].strip():
            at -= 1
        held: list[str] = []
        while at >= 0 and lines[at].lstrip().startswith("#"):
            held.append(lines[at].lstrip().lstrip("#").strip())
            at -= 1
        held.reverse()
        found.append(
            Proc(
                name=m.group("name"),
                params=tuple(m.group("params").split()),
                file=path.name,
                line=n + 1,
                comment=" ".join(one for one in held if one),
            )
        )
    return found


def harness(root: Path) -> list[Proc]:
    """Every procedure in every `.exp` file the harness is made of, in file order."""
    found: list[Proc] = []
    for path in sorted((root / LIB).glob("*.exp")):
        found += procs(path)
    if not found:
        raise SourceError(f"{root / LIB} has no procedures in it")
    return found


def directives(root: Path) -> list[Proc]:
    """The `dg-` procedures a test file may write, deduplicated by name.

    A name defined in two files is defined twice on purpose: `dg-modules` is one procedure in
    the Algol 68 harness and the same procedure in its torture harness. The first is kept and
    the count says how many names there are rather than how many definitions.
    """
    seen: dict[str, Proc] = {}
    for one in harness(root):
        if one.name.startswith("dg-") and one.is_directive and one.name not in seen:
            seen[one.name] = one
    return sorted(seen.values(), key=lambda p: p.name)


def effective_targets(root: Path) -> int:
    """How many `check_effective_target_` procedures the harness defines."""
    return sum(1 for one in harness(root) if one.name.startswith("check_effective_target_"))


@generator("dg-directives")
def dg_directives(root: Path) -> str:
    every = directives(root)
    requires = [one for one in every if one.name.startswith("dg-require-")]
    silent = [one for one in every if not one.summary]
    files = sorted({one.file for one in every})
    rows = ["| Directive | Defined in | What it does |", "|---|---|---|"]
    for one in every:
        rows.append(f"| `{one.name}` | `{one.file}` | {cell(one.summary)} |")
    summary = (
        f"The harness defines **{len(every)} directives** across {len(files)} files under "
        f"`gcc/testsuite/lib/`. These are GCC's, and they are the smaller half. `dg-do`, "
        f"`dg-options`, `dg-error`, `dg-warning`, `dg-bogus`, `dg-excess-errors` and "
        f"`dg-output` are DejaGnu's, defined in its own `lib/dg.exp`, which is not in this "
        f"tree and is not versioned with it. `dg-final` is in the table because GCC redefines "
        f"DejaGnu's, and a test gets whichever definition was loaded last. A directive is "
        f"recognised here by taking DejaGnu's line number as its first argument, which is "
        f"what separates the {len(every)} below from the procedures the harness calls itself."
    )
    tail = (
        f"{len(requires)} of them are `dg-require-` wrappers, each one a named front end for a "
        f"single `check_effective_target_` procedure. There are "
        f"**{effective_targets(root)} of those** in the harness, and `dg-require-effective-target` "
        f"reaches any of them by name, which is why the wrappers stopped being added and most "
        f"tests written today use the general form. The {len(silent)} empty cells are "
        f"directives whose author wrote no comment above them, and the description column is "
        f"the first sentence of that comment or nothing."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


def family(name: str) -> str:
    """The base procedure a scan variant belongs to."""
    if name in INFIX_NOT:
        return INFIX_NOT[name]
    for suffix in VARIANTS:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


@generator("dg-final-scans")
def dg_final_scans(root: Path) -> str:
    every = [
        one
        for one in harness(root)
        if one.name.startswith("scan-") and one.is_directive and one.file in READS
    ]
    if not every:
        raise SourceError("no scan procedures found, which cannot be right")
    groups: dict[tuple[str, str], list[str]] = {}
    for one in every:
        groups.setdefault((family(one.name), one.file), []).append(one.name)

    rows = ["| Base | Variants | Reads | Defined in |", "|---|---|---|---|"]
    for (base, file), names in sorted(groups.items()):
        extra = {"-not" if n in INFIX_NOT else n[len(base) :] for n in names if n != base}
        shown = ", ".join(f"`{one}`" for one in sorted(extra)) or "none"
        reads = READS_BY_BASE.get(base) or READS[file]
        if not reads:
            raise SourceError(f"{base} is in {file} and nothing here says what it reads")
        rows.append(f"| `{base}` | {shown} | {reads} | `{file}` |")

    summary = (
        f"**{len(every)} scan procedures**, in {len({one.file for one in every})} files, "
        f"grouped here into the {len(groups)} families they actually form. A `dg-final` body "
        f"is a Tcl command, so the first word of it is a procedure name and the table below is "
        f"the list of the ones that read compiler output. The variants are a regular system: "
        f"`-not` asserts absence, `-times` takes a count, `-dem` runs the output through the "
        f"demangler first, and `-bound` takes a comparison and a count."
    )
    tail = (
        "`dg-final` accepts any procedure that is loaded, so this is not a closed set. The "
        "other things a test puts there are the cleanup procedures, `output-exists` and "
        "`output-exists-not`, `object-size`, `dg-function-on-line` and `check-function-bodies`, "
        "which check something other than a pattern in a file."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


@generator("torture-options")
def torture_options(root: Path) -> str:
    text = slurp(root / LIB / "gcc-dg.exp")
    m = TORTURE.search(text)
    if m is None:
        raise SourceError("gcc-dg.exp no longer sets DG_TORTURE_OPTIONS as a literal list")
    sets = [
        one.strip().strip("\\").strip().strip("{}").strip()
        for one in m.group("body").splitlines()
        if one.strip().strip("\\").strip()
    ]
    rows = ["| Option set |", "|---|"] + [f"| `{one}` |" for one in sets]
    summary = (
        f"**{len(sets)} option sets**, and a test run under `gcc-dg-runtest` is compiled and "
        f"checked once for each of them. That is the multiplier on everything else in this "
        f"document: one file in `gcc.dg/torture/` is {len(sets)} compilations, and one "
        f"`dg-final` in it is {len(sets)} scans of {len(sets)} different dumps. `TORTURE_OPTIONS` "
        f"in the environment replaces the list outright and `ADDITIONAL_TORTURE_OPTIONS` "
        f"appends to it, so a run with either set is not comparable with a run without."
    )
    tail = (
        "The `-funroll-loops` in the third set is why the harness greps each test for `for (` "
        "or `while (` before choosing a list. A test with no loop in it is run with a shorter "
        "list, and that decision is made by a regular expression over the source."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


@dataclass(frozen=True)
class Tool:
    """One `--tool` argument to `runtest`, which is one `check-` target."""

    name: str
    parallel: int
    directories: tuple[str, ...]
    exps: int

    @property
    def target(self) -> str:
        return f"check-{self.name}"


def tools(root: Path) -> list[Tool]:
    """Every language's check target, with how far it splits and what it covers."""
    targets: list[str] = []
    parallelized: set[str] = set()
    counts: dict[str, int] = {}
    sources = [root / MAKEFILE] + sorted(root.glob("*/Make-lang.in"))
    for path in sources:
        text = slurp(path)
        for m in LANG_CHECK.finditer(text):
            targets += m.group("targets").split()
        for m in LANG_PARALLEL.finditer(text):
            parallelized.update(m.group("targets").split())
        for m in PARALLELIZE.finditer(text):
            counts[m.group("tool")] = int(m.group("count"))
    if not targets:
        raise SourceError(f"{root / MAKEFILE} and the Make-lang.in files register no checks")

    found = []
    for target in sorted(set(targets)):
        name = target.removeprefix("check-")
        directories = sorted(
            one.name
            for one in (root / TESTS).iterdir()
            if one.is_dir() and (one.name == name or one.name.startswith(f"{name}."))
        )
        exps = sum(len(list((root / TESTS / one).rglob("*.exp"))) for one in directories)
        found.append(
            Tool(
                name=name,
                parallel=counts.get(name, 0) if target in parallelized else 0,
                directories=tuple(directories),
                exps=exps,
            )
        )
    return found


@generator("check-targets")
def check_targets(root: Path) -> str:
    every = tools(root)
    rows = [
        "| Target | `--tool` | Directories | `.exp` files | Parallel slots |",
        "|---|---|---|---|---|",
    ]
    for one in every:
        where = ", ".join(f"`{d}/`" for d in one.directories) or "none in this tree"
        splits = str(one.parallel) if one.parallel else "not parallelized"
        rows.append(f"| `{one.target}` | `{one.name}` | {where} | {one.exps} | {splits} |")
    total = sum(one.exps for one in every)
    summary = (
        f"**{len(every)} check targets**, one for each front end this tree can build plus one "
        f"for each library that ships its own suite, and `make check` runs the ones the tree "
        f"was configured with. Each is a `runtest --tool` invocation. DejaGnu finds the tests "
        f"by name: the directories under `gcc/testsuite/` called the tool name, or the tool "
        f"name and a dot and anything, which is why `gcc.dg`, `gcc.target` and `gcc.c-torture` "
        f"are one target and `g++.dg` is another. The {total} `.exp` files in them are the "
        f"unit of everything: of scheduling, of the `=` filter in `RUNTESTFLAGS`, and of the "
        f"parallel split."
    )
    tail = (
        "The last column is `check_$tool_parallelize`, the point past which splitting that "
        "target stops paying. It is not a job count and the big numbers are not read as "
        "written: the split is capped at `GCC_TEST_PARALLEL_SLOTS` or 128, and it happens at "
        "all only when `make` was given `-j`. The processes that result all walk the same "
        "`.exp` files and race for each batch of ten tests through marker files in a shared "
        "directory, then `contrib/dg-extract-results.sh` merges the sum and log files back "
        "into one."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")
