"""Record what GCC's C parser says about fifteen small programs, and the code that says it.

    python lessons/f03-four-tokens/record.py
    python lessons/f03-four-tokens/record.py --check

Three kinds of evidence go into `corpora/diag/f03.json`:

  cases       fifteen programs through `-fsyntax-only`, each one recorded twice, as the text
              a person reads and as the SARIF a machine can assert against. Three of them go
              through an x86-64 Linux compiler as well, because a parser is the one part of
              GCC that has no target and the cheapest way to say so is to show it
  grammar     every `c_parser_*` function defined in `gcc/c/c-parser.cc`, counted out of the
              pinned tree, which is how the lesson can say what fraction of the C parser is
              about C
  lookahead   every call to the three peeking helpers, and the constant each deep one passes,
              which is the only honest way to answer how far ahead the parser can see

Nothing here links, assembles or optimizes. `-fsyntax-only` stops after the front end, which
is the entire subject, and it is also what makes it safe to record a file with a version
control conflict marker in it.

The x86-64 half goes through the Compiler Explorer API and is cached in
`tools/cecache/store`, so this is a live request once and a file lookup afterwards.

`--check` re-asserts every fact the notebook states, against what is already committed and
without running a compiler, which is what the test suite calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import cparse, source  # noqa: E402
from gxray.driver import CEBackend  # noqa: E402
from tools.cecache import Cache  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "diag" / "f03.json"
CUTS = ROOT / "corpora" / "source" / "f03.json"

#: The local compiler, the same Homebrew GCC 16.2.0 that F01 and F02 recorded.
GCC = os.environ.get("GXRAY_GCC", "gcc-16")

#: The other one. Same release, x86-64 Linux, reached through Compiler Explorer.
CE_COMPILER = "cg162"

#: The one filename every recorded program is compiled under, so that a message from here
#: and a message from a machine on another continent differ in what they say and not in what
#: the file was called on the day.
NAME = "p.c"

#: The eight programs that make the same mistake. Every one of them leaves out one semicolon
#: after `return 1`, and every one of them gets a different sentence, because the sentence is
#: finished by `c_parse_error` according to the type of the token the parser is looking at.
#: Seven put the caret in the same place and one does not, which is the section.
SAME_MISTAKE: tuple[tuple[str, str, str], ...] = (
    ("brace", "the next token is a close brace", "int f(void) { return 1 }\n"),
    ("name", "the next token is an identifier", "int f(void) { int a = 1 b; }\n"),
    ("number", "the next token is a number", "int f(void) { return 1 2; }\n"),
    ("string", "the next token is a string", 'int f(void) { return 1 "x"; }\n'),
    ("char", "the next token is a character constant", "int f(void) { return 1 'c'; }\n"),
    ("keyword", "the next token is a keyword", "int f(void) { return 1 while (0); }\n"),
    (
        "pragma",
        "the next token is a pragma, which is one token",
        "int f(void) { return 1\n#pragma GCC unroll 2\n; }\n",
    ),
    ("eof", "there is no next token", "int f(void) { return 1\n"),
)

#: The rest of the programs. Each is a whole file, the flags it needs, and whether the same
#: file is worth sending to the other target.
PROGRAMS: tuple[tuple[str, str, str, tuple[str, ...], bool], ...] = (
    (
        "meaning-typedef",
        "A is a type, so line 3 declares b",
        "typedef int A;\nint b;\nvoid f(void) { A * b; }\n",
        ("-Wall", "-Wshadow"),
        True,
    ),
    (
        "meaning-variable",
        "A is a variable, so the same line 3 multiplies",
        "int A;\nint b;\nvoid f(void) { A * b; }\n",
        ("-Wall", "-Wshadow"),
        True,
    ),
    (
        "scope-typedef",
        "T is a type at file scope and a variable inside a for header that has closed",
        "typedef int T;\nvoid f(void)\n{\n  for (int T;;)\n    if (1)\n      ;\n  T *x;\n}\n",
        ("-Wall",),
        False,
    ),
    (
        "scope-variable",
        "The same program with the two declarations of T swapped over",
        "int T;\nvoid f(void)\n{\n  for (typedef int T;;)\n    if (1)\n      ;\n  T *x;\n}\n",
        ("-Wall",),
        False,
    ),
    (
        "recovery",
        "Three missing semicolons, and not three errors",
        "void f(void)\n{\n  int a = 1\n  int b = 2\n  int c = 3\n}\n",
        (),
        False,
    ),
    (
        "paren",
        "A bracket that never closes, and the second place the message points",
        "void g(void);\nvoid f(int x)\n{\n  if (x\n    g();\n}\n",
        (),
        False,
    ),
    (
        "conflict",
        "The deepest the C parser ever looks ahead, and what it looks for",
        "int f(void)\n{\n<<<<<<< HEAD\n  return 1;\n=======\n  return 2;\n>>>>>>> other\n}\n",
        (),
        False,
    ),
)

#: Where each span comes from. `first` and `last` are inclusive lines in the pinned tree and
#: `cite` is asserted against `first`, so a span that moves cannot keep a citation pointing
#: at code that is no longer there.
SPANS: tuple[dict, ...] = (
    {
        "name": "intermediates",
        "path": "gcc/c/c-parser.h",
        "first": 26,
        "last": 35,
        "about": "What sits between libcpp and the parser, and the wish at the end of it",
        "cite": "gcc/c/c-parser.h:26@releases/gcc-16.2.0",
    },
    {
        "name": "slots",
        "path": "gcc/c/c-parser.cc",
        "first": 188,
        "last": 198,
        "about": "The parser's entire memory of your file, and the comment that undercounts it",
        "cite": "gcc/c/c-parser.cc:188@releases/gcc-16.2.0",
    },
    {
        "name": "handover",
        "path": "gcc/c/c-parser.cc",
        "first": 332,
        "last": 349,
        "about": "The one call. Everything the parser will ever know arrives through it",
        "cite": "gcc/c/c-parser.cc:332@releases/gcc-16.2.0",
    },
    {
        "name": "lookup",
        "path": "gcc/c/c-parser.cc",
        "first": 467,
        "last": 491,
        "about": "The symbol table decides what an identifier is, while it is being lexed",
        "cite": "gcc/c/c-parser.cc:467@releases/gcc-16.2.0",
    },
    {
        "name": "conflict",
        "path": "gcc/c/c-parser.cc",
        "first": 1016,
        "last": 1054,
        "about": "The only thing in C that needs a fourth token of lookahead",
        "cite": "gcc/c/c-parser.cc:1016@releases/gcc-16.2.0",
    },
    {
        "name": "position",
        "path": "gcc/c/c-parser.cc",
        "first": 1006,
        "last": 1014,
        "about": "The guard that decides where an at-end-of-input message puts its caret",
        "cite": "gcc/c/c-parser.cc:1006@releases/gcc-16.2.0",
    },
    {
        "name": "latch",
        "path": "gcc/c/c-parser.cc",
        "first": 1072,
        "last": 1094,
        "about": "Two lines, and the reason three mistakes are not three errors",
        "cite": "gcc/c/c-parser.cc:1072@releases/gcc-16.2.0",
    },
    {
        "name": "report",
        "path": "gcc/c/c-parser.cc",
        "first": 1130,
        "last": 1141,
        "about": "The other way to report, which puts the caret on the token it can see",
        "cite": "gcc/c/c-parser.cc:1130@releases/gcc-16.2.0",
    },
    {
        "name": "require",
        "path": "gcc/c/c-parser.cc",
        "first": 1278,
        "last": 1318,
        "about": "Where the caret goes when GCC knows which token you left out",
        "cite": "gcc/c/c-parser.cc:1278@releases/gcc-16.2.0",
    },
    {
        "name": "loop",
        "path": "gcc/c/c-parser.cc",
        "first": 2065,
        "last": 2099,
        "about": "The whole of the C parser's top level, which is six lines",
        "cite": "gcc/c/c-parser.cc:2065@releases/gcc-16.2.0",
    },
    {
        "name": "reclassify",
        "path": "gcc/c/c-parser.cc",
        "first": 2321,
        "last": 2341,
        "about": "The patch-up a bug report bought, and the scope it puts right",
        "cite": "gcc/c/c-parser.cc:2321@releases/gcc-16.2.0",
    },
    {
        "name": "suffixes",
        "path": "gcc/c-family/c-common.cc",
        "first": 7000,
        "last": 7013,
        "about": "Where a parser's complaint becomes a sentence, and the first branch of it",
        "cite": "gcc/c-family/c-common.cc:7000@releases/gcc-16.2.0",
    },
    {
        "name": "insertion",
        "path": "gcc/c-family/c-common.cc",
        "first": 9973,
        "last": 9997,
        "about": "The seven tokens GCC will offer to write for you, and which side they go",
        "cite": "gcc/c-family/c-common.cc:9973@releases/gcc-16.2.0",
    },
    {
        "name": "swap",
        "path": "gcc/c-family/c-common.cc",
        "first": 9999,
        "last": 10046,
        "about": "GCC explaining, in a comment with a diagram, why the caret is on the line above",
        "cite": "gcc/c-family/c-common.cc:9999@releases/gcc-16.2.0",
    },
)

#: The GCC test cases the two scope programs are cut down from, named so that a reader who
#: wants the other four variants knows where they are.
SCOPE_TESTS = ("gcc/testsuite/gcc.dg/pr67784-1.c", "gcc/testsuite/gcc.dg/pr67784-2.c")


class Watched(Cache):
    """The ordinary cache, keeping a note of which entries went through it.

    `tools.tier0.orphans` insists the registry accounts for the store exactly, and it works
    that out from an experiment's corpus entry. This lesson's requests are not corpus
    entries, so the list has to come from here instead.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self.used: list[str] = []

    def fetch(self, key: str, send) -> dict:
        self.used.append(key)
        return super().fetch(key, send)


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)


def rename(text: str, was: str) -> str:
    """Call every file `p.c`, wherever it was compiled.

    Compiler Explorer names the file it was handed after its own conventions, and a local
    run names it after a temporary directory. Neither is a fact about parsing, and leaving
    them in would make two recordings of one program look like a disagreement.
    """
    return re.sub(rf"^{re.escape(was)}(?=[:\s])", NAME, text, flags=re.MULTILINE)


def compile_here(work: Path, text: str, *args: str) -> tuple[str, str]:
    """One program through the front end, kept twice.

    The plain run and the SARIF run are two invocations of the same compiler on the same
    file with one flag different, which is the only way to have the sentence a person reads
    and the structure a test can assert against without one of them being reconstructed.
    """
    (work / NAME).write_text(text, encoding="utf-8")
    plain = run([GCC, "-fsyntax-only", *args, NAME], work)
    machine = run([GCC, "-fsyntax-only", "-fdiagnostics-format=sarif-stderr", *args, NAME], work)
    if not machine.stderr.strip():
        raise SystemExit(f"{GCC} printed no SARIF for:\n{text}")
    return plain.stderr, machine.stderr


def elsewhere(back: CEBackend, text: str, *args: str) -> str:
    """The same program through the x86-64 Linux compiler, made comparable with the local one.

    Two things have to come off. Compiler Explorer names the file `<source>`, and it runs
    the compiler attached to something it believes is a terminal, so every diagnostic comes
    back wrapped in colour escapes. Asking for no colour is not enough on its own, because
    which of the two `-fdiagnostics-color` flags wins depends on the order the service
    assembles a command line in, which is not this lesson's business to depend on.
    """
    result = back.compile(text, "-fsyntax-only", "-fdiagnostics-color=never", *args)
    return rename(cparse.plain(result.stderr), "<source>")


def grammar() -> dict:
    """Every `c_parser_*` function defined in the pinned tree, by name.

    Definitions and not declarations, which is what anchoring the pattern to the start of a
    line buys: GCC's C sources put a function's return type on its own line, so a name in
    column one is a definition and a name anywhere else is a call or a prototype.
    """
    text = (GCC_ROOT / "gcc" / "c" / "c-parser.cc").read_text(encoding="utf-8", errors="replace")
    found = re.findall(r"^(c_parser_\w+) \(", text, flags=re.MULTILINE)
    return {"functions": sorted(set(found))}


def lookahead() -> dict:
    """How far past the current token the parser is able to look, counted rather than recalled.

    `depths` counts only the calls that pass a constant. The handful that pass a variable are
    left out on purpose and the notebook says why: they are reached with a small constant from
    their callers, or they are parsing OpenMP out of a vector of tokens that was lexed in one
    go and is not in the four slots at all.
    """
    text = (GCC_ROOT / "gcc" / "c" / "c-parser.cc").read_text(encoding="utf-8", errors="replace")
    depths: dict[int, int] = {}
    for n in re.findall(r"c_parser_peek_nth_token \(parser, (\d+)\)", text):
        depths[int(n)] = depths.get(int(n), 0) + 1
    slots = re.search(r"c_token tokens_buf\[(\d+)\]", text)
    if slots is None:
        raise SystemExit("no tokens_buf in c-parser.cc, so the lookahead cannot be counted")
    return {
        "peeks": len(re.findall(r"c_parser_peek_token \(", text)),
        "seconds": len(re.findall(r"c_parser_peek_2nd_token \(", text)),
        "depths": {str(k): v for k, v in sorted(depths.items())},
        "slots": int(slots.group(1)),
    }


def one_case(work: Path, back: CEBackend, name: str, about: str, text: str, args, share) -> dict:
    plain, machine = compile_here(work, text, *args)
    found = cparse.parse_sarif(machine)
    entry = {
        "about": about,
        "flags": list(args),
        "source": text,
        "text": rename(plain, NAME),
        "diagnostics": [cparse.stored(one) for one in found],
    }
    if share:
        entry["elsewhere"] = elsewhere(back, text, *args)
    return entry


def record() -> dict:
    version = run([GCC, "--version"], ROOT).stdout.splitlines()[0]
    target = run([GCC, "-dumpmachine"], ROOT).stdout.strip()
    watched = Watched()
    back = CEBackend(CE_COMPILER, cache=watched)
    back.version()

    with tempfile.TemporaryDirectory(prefix="f03-") as tmp:
        work = Path(tmp)
        cases: dict[str, dict] = {}
        for name, about, text in SAME_MISTAKE:
            share = name == "brace"
            cases[name] = one_case(work, back, name, about, text, (), share)
        for name, about, text, args, share in PROGRAMS:
            cases[name] = one_case(work, back, name, about, text, args, share)

        return {
            "recorded": date.today().isoformat(),
            "tag": PINNED_TAG,
            "compiler": version,
            "target": target,
            # Which Compiler Explorer entries this recording stands for, written by the code
            # that made the requests rather than kept by hand next to it.
            "cache": sorted(set(watched.used)),
            "cases": cases,
            "grammar": grammar(),
            "lookahead": lookahead(),
        }


def spans() -> dict:
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(GCC_ROOT, wanted, PINNED_TAG)


def check(rec: cparse.Recording) -> list[str]:
    """Every fact the notebook states about the recording, asserted here instead of in prose.

    These are statements about GCC 16.2.0 and not about C. That is what this function is
    for: the paragraph next door cannot notice it has gone stale.
    """
    wrong: list[str] = []

    def want(condition: bool, saying: str) -> None:
        if not condition:
            wrong.append(saying)

    #: The eight programs that make one mistake, which is the spine.
    names = [name for name, _, _ in SAME_MISTAKE]
    said = [rec.case(name).errors[0].message for name in names if rec.case(name).errors]
    want(
        len(said) == len(names),
        f"{len(said)} of the {len(names)} same-mistake programs produced an error, not all",
    )
    want(
        len(set(said)) == len(names),
        f"the {len(names)} programs produced {len(set(said))} distinct sentences, not"
        " one each, and the section is that the sentence is chosen by the next token",
    )
    for name in names:
        first = rec.case(name).errors[0]
        want(
            first.suffixes != [],
            f"{name} says {first.message!r}, which matches no branch of c_parse_error",
        )
    unsure = sorted(name for name in names if rec.case(name).errors[0].suffix is None)
    want(
        unsure == ["char", "name"],
        f"the programs whose message does not say which branch made it are {unsure}, and the"
        " section says the two that end in one quoted character, because a one-letter"
        " identifier and a character constant print the same",
    )
    want(
        rec.case("keyword").errors[0].message.endswith("'while'"),
        "a keyword is no longer reported the way an identifier is, and the section says the"
        " parser hands c_parse_error CPP_NAME when it is looking at a keyword",
    )
    want(
        rec.case("eof").errors[0].message.endswith(" at end of input"),
        "running out of file no longer says so, and the section shows the branch that does",
    )

    #: Seven of the eight put the caret in the same place, because seven go through
    #: `c_parser_require` and one goes through `c_parser_error`.
    columns = {name: rec.case(name).errors[0].at for name in names}
    moved = [name for name in names if columns[name].line == 1 and columns[name].column == 23]
    want(
        sorted(moved) == sorted(set(names) - {"name"}),
        f"the programs whose caret landed just after the 1 are {sorted(moved)}, and the"
        " section says it is every one except the two-token complaint",
    )
    want(
        columns["name"].column == 25,
        f"the two-token complaint now points at column {columns['name'].column}, and the"
        " section says 25, which is where the offending token is",
    )
    hinted = sorted(name for name in names if rec.case(name).errors[0].fixes)
    want(
        hinted == sorted(set(names) - {"name"}),
        f"the programs GCC offered to repair are {hinted}, and the section says every one"
        " except the two-token complaint, which is the same one whose caret did not move,"
        " because moving the caret and offering the repair are the same piece of code",
    )

    #: The brace program in detail, which is the one everybody has seen.
    brace = rec.case("brace").errors[0]
    want(
        brace.message == "expected ';' before '}' token",
        f"the brace program now says {brace.message!r}",
    )
    want(len(brace.fixes) == 1, f"the brace program carries {len(brace.fixes)} fix-its, not 1")
    want(
        brace.fixes and brace.fixes[0].insert == ";",
        "the fix-it for a missing semicolon no longer inserts a semicolon",
    )
    want(
        brace.fixes and brace.fixes[0].at.column == brace.at.column,
        "the caret and the fix-it are no longer in the same place, and the section says the"
        " caret was moved to the fix-it",
    )
    want(
        brace.related != () and brace.related[0].column == 24,
        f"the brace the message names is recorded at {list(brace.related)}, and the section"
        " says column 24, which is not where the caret is",
    )
    want(brace.moved, "the brace program no longer points at two places, which is the section")
    want(
        rec.case("brace").agrees,
        "the two targets no longer say the same thing about a missing semicolon, which"
        " would mean the parser has a target after all",
    )

    #: The pair that differ by one word.
    typedef, variable = rec.case("meaning-typedef"), rec.case("meaning-variable")
    want(
        typedef.line(3) == variable.line(3) == "void f(void) { A * b; }",
        "the two meaning programs no longer share line 3, which is the whole comparison",
    )
    want(
        typedef.source.split("\n")[0] != variable.source.split("\n")[0],
        "the two meaning programs no longer differ on line 1",
    )
    want(
        [one.message for one in typedef.warnings]
        == [
            "declaration of 'b' shadows a global declaration",
            "unused variable 'b'",
        ],
        f"the typedef program now says {[one.message for one in typedef.warnings]}, and the"
        " section says GCC calls line 3 a declaration",
    )
    want(
        [one.message for one in variable.warnings] == ["statement with no effect"],
        f"the variable program now says {[one.message for one in variable.warnings]}, and"
        " the section says GCC calls the same line an expression",
    )
    want(
        typedef.agrees and variable.agrees,
        "the two targets no longer agree about what A * b means, which cannot be right",
    )

    #: The pair GCC needed a bug report to get right.
    want(
        rec.case("scope-typedef").errors == [],
        f"the scope program that should compile now says"
        f" {[str(one) for one in rec.case('scope-typedef').errors]}",
    )
    want(
        "unused variable 'x'" in [one.message for one in rec.case("scope-typedef").warnings],
        "the scope program that compiles no longer declares x, and the section says T *x is"
        " a declaration there because T is the file scope typedef again by then",
    )
    undeclared = rec.case("scope-variable").errors
    want(
        undeclared != [] and "'x' undeclared" in undeclared[0].message,
        f"the scope program that should not compile now says"
        f" {[str(one) for one in undeclared]}, and the section says x is undeclared because"
        " T *x is a multiplication",
    )

    #: Recovery, which is why you fix the first error and recompile.
    recovery = rec.case("recovery")
    want(
        len(recovery.errors) == 2,
        f"three missing semicolons now produce {len(recovery.errors)} errors, and the"
        " section says two",
    )
    want(
        recovery.errors[-1].message.endswith(" at end of input"),
        f"the second error is now {recovery.errors[-1].message!r}, and the section says the"
        " parser skipped to the end of the block and ran out of file looking for it",
    )
    want(
        recovery.errors[-1].at.line == 6,
        f"the at-end-of-input message is now drawn at line {recovery.errors[-1].at.line},"
        " and the section says line 6, because a message about running out of file is put"
        " wherever the parser last was and there is no end of file to point at",
    )

    #: The matching bracket, which is the other thing a rich location carries.
    paren = rec.case("paren")
    want(
        paren.errors != [] and paren.errors[0].message == "expected ')' before 'g'",
        f"the paren program now says {[str(one) for one in paren.errors]}",
    )
    want(
        paren.errors and len(paren.errors[0].related) == 2,
        f"the missing bracket now points at {len(paren.errors[0].related) if paren.errors else 0}"
        " other places, and the section says two: the token it was looking at and the"
        " bracket it wanted to match",
    )
    want(
        paren.errors and sorted(one.line for one in paren.errors[0].related) == [4, 5],
        f"the other two places are now on lines"
        f" {sorted(one.line for one in paren.errors[0].related) if paren.errors else []},"
        " and the section says the open bracket on line 4 and the token on line 5",
    )

    #: The deepest lookahead in the parser, and the only thing that needs it.
    conflict = rec.case("conflict")
    want(
        len(conflict.errors) == 3,
        f"the conflict marker program now produces {len(conflict.errors)} errors, not 3",
    )
    want(
        all(one.message == "version control conflict marker in file" for one in conflict.errors),
        f"the conflict program now says {[one.message for one in conflict.errors]}",
    )
    want(
        all(one.at.column == 1 and one.at.width == 7 for one in conflict.errors),
        f"the conflict markers are now {[one.at.width for one in conflict.errors]} columns"
        " wide, and the section says seven, starting in column one",
    )

    #: The size of the thing, which is the closing section.
    parts = rec.grammar.dialects
    want(
        len(rec.grammar) == 298,
        f"c-parser.cc now defines {len(rec.grammar)} parser functions, not 298",
    )
    want(
        len(parts["C"]) == 113,
        f"{len(parts['C'])} of them are for C, and the section says 113",
    )
    want(
        len(parts["OpenMP"]) > len(parts["C"]),
        f"OpenMP now has {len(parts['OpenMP'])} functions against C's {len(parts['C'])}, and"
        " the section says the file has more code for OpenMP than for C",
    )
    for name in ("c_parser_translation_unit", "c_parser_peek_conflict_marker", "c_parser_require"):
        want(name in rec.grammar.functions, f"{name} is no longer defined in c-parser.cc")

    #: How far it can see.
    look = rec.lookahead
    want(look.slots == 4, f"the token buffer now has {look.slots} slots, not 4")
    want(look.deepest == 4, f"the deepest constant peek is now {look.deepest}, not 4")
    want(
        look.peeks > 7 * look.seconds,
        f"the parser peeks at the next token {look.peeks} times and at the one after it"
        f" {look.seconds} times, and the section says the second is rare",
    )
    want(
        look.depths.get(4, 0) == 3,
        f"there are now {look.depths.get(4, 0)} calls that ask for a fourth token, not 3",
    )
    return wrong


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="assert against what is already there")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.check:
        if shutil.which(GCC) is None:
            print(f"no {GCC} on PATH. Set GXRAY_GCC, or read B01 and build one.")
            return 1
        if not (GCC_ROOT / "gcc" / "c" / "c-parser.cc").is_file():
            print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
            return 1
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(record(), indent=1) + "\n", encoding="utf-8")
        CUTS.parent.mkdir(parents=True, exist_ok=True)
        CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    rec = cparse.load("f03")
    shown = source.load_extract("f03")
    wrong = check(rec)
    for line in wrong:
        print(f"  {line}")
    verb = "checked" if args.check else "wrote"
    said = sum(len(one.diagnostics) for one in rec)
    print(
        f"{verb} {OUT.relative_to(ROOT)}, {len(rec)} programs, {said} diagnostics, "
        f"{len(rec.grammar)} parser functions, recorded {rec.recorded}"
    )
    print(f"{verb} {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
