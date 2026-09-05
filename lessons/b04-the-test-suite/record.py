"""Compile twelve real GCC test files with a real GCC 16.2 and keep every byte.

    python lessons/b04-the-test-suite/record.py
    python lessons/b04-the-test-suite/record.py --check

The test suite cannot be run in a notebook. `runtest` needs `expect`, a build tree and a
compiler that was built ten minutes ago, and a reader has none of those. What a reader can
have is the part that decides: the directives in a test file, the diagnostics the compiler
printed, and the rule that turns one into a verdict about the other. That part needs a real
compilation of a real test file, and Compiler Explorer will do a real compilation of a real
test file for free.

So this recorder takes files out of the pinned tree, works out the command line the harness
would use for each one, compiles them through `gxray.ce("cg162")`, and writes the whole lot
to `corpora/testsuite/b04.json`. The notebook then reaches the same verdicts the real harness
reaches, on the same files, from the same output, with no compiler in sight.

Two things are recorded that a passing test suite would not bother with. `flex-c90` is the
flexible array test compiled with the wrong standard, which is what happens when a test loses
its `dg-options` line, and it fails for excess errors on the one struct the author left valid
on purpose. The six `torture-*` entries are one file compiled six times, which is what
`gcc-dg-runtest` does to every file in `gcc.dg/torture` and is why that directory of four
hundred small files takes as long as it does.

`--check` re-runs the assertions against what is already on disk without compiling anything,
which is what the test suite of this repository calls.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import dejagnu, source  # noqa: E402
from gxray.driver import CEBackend  # noqa: E402
from tools.cecache import Cache  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "testsuite" / "b04.json"
CUTS = ROOT / "corpora" / "source" / "b04.json"
SUITE = GCC_ROOT / "gcc" / "testsuite"

#: The Compiler Explorer compiler id for the pinned release. The same one every other lesson
#: uses, so a reader who has run any of them has this cached already.
COMPILER = "cg162"

#: The files, and which directory's defaults they are compiled under. `default` is what the
#: `.exp` passes when the test has no `dg-options`, which is not the same in the two
#: directories and is the source of more confusion than any other thing in this file.
FILES: tuple[dict, ...] = (
    {
        "name": "flex",
        "path": "gcc.dg/c99-flex-array-1.c",
        "default": dejagnu.DEFAULT_CFLAGS,
        "why": "Three errors, and a fourth struct that is legal and must stay quiet",
    },
    {
        "name": "assume",
        "path": "gcc.dg/attr-assume_aligned-2.c",
        "default": dejagnu.DEFAULT_CFLAGS,
        "why": "Two errors and a warning, and no dg-options, so the directory default applies",
    },
    {
        "name": "fre",
        "path": "gcc.dg/tree-ssa/ssa-fre-6.c",
        "default": (),
        "dump": "tree-fre1-details",
        "why": "A dg-final that counts a string in a dump rather than reading a diagnostic",
    },
    {
        "name": "bogus",
        "path": "gcc.dg/pr87309.c",
        "default": (),
        "why": "A dg-bogus, where finding the message is the failure",
    },
    {
        "name": "noloop",
        "path": "gcc.dg/torture/pr78517.c",
        "default": (),
        "extra": ("-O2",),
        "why": "A torture test with no loop in it, so its option list is the shorter one",
    },
)

#: The same file six times, once per torture option set. `gcc.dg/torture/dg-torture.exp`
#: passes an empty default, so the option set is the whole of the optimisation flags.
TORTURED = "gcc.dg/torture/pr122599-1.c"

#: The directories a native x86-64 `make check-gcc` actually walks. `gcc.target` holds a
#: hundred and six `.exp` files, one per architecture, and exactly one of them runs here.
WALKED = (
    "gcc.dg",
    "gcc.c-torture",
    "gcc.target/i386",
    "c-c++-common",
    "gcc.misc-tests",
    "gcc.test-framework",
)

#: A directive in a test file. Loose on purpose: this is a census of what the suite writes,
#: not a parser, and the point of the count is how many kinds there are to fail to handle.
DIRECTIVE = re.compile(r"\{\s*(dg-[a-z0-9-]+)")

#: The spans of the real harness the lesson prints, in order. A reader on Colab has no GCC
#: tree, so every line of Tcl the notebook shows has to be cut out here and committed.
SPANS: tuple[dict, ...] = (
    {
        "name": "default",
        "path": "gcc/testsuite/gcc.dg/dg.exp",
        "first": 22,
        "last": 33,
        "about": "Every test in gcc.dg is compiled with these two flags unless it says otherwise",
        "cite": "gcc/testsuite/gcc.dg/dg.exp:22@releases/gcc-16.2.0",
    },
    {
        "name": "always",
        "path": "gcc/testsuite/lib/prune.exp",
        "first": 22,
        "last": 30,
        "about": "And with this one whatever it says, because the output format is not negotiable",
        "cite": "gcc/testsuite/lib/prune.exp:22@releases/gcc-16.2.0",
    },
    {
        "name": "torture",
        "path": "gcc/testsuite/lib/gcc-dg.exp",
        "first": 84,
        "last": 100,
        "about": "The six option sets, and why -finline-functions is spelled out next to -O3",
        "cite": "gcc/testsuite/lib/gcc-dg.exp:84@releases/gcc-16.2.0",
    },
    {
        "name": "loops",
        "path": "gcc/testsuite/lib/gcc-dg.exp",
        "first": 736,
        "last": 752,
        "about": "Whether a file gets the loop flags is decided by looking for `for` in the text",
        "cite": "gcc/testsuite/lib/gcc-dg.exp:736@releases/gcc-16.2.0",
    },
    {
        "name": "notes",
        "path": "gcc/testsuite/lib/gcc-dg.exp",
        "first": 1343,
        "last": 1366,
        "about": "One dg-note anywhere in a file makes every note in that file count",
        "cite": "gcc/testsuite/lib/gcc-dg.exp:1343@releases/gcc-16.2.0",
    },
    {
        "name": "pruning",
        "path": "gcc/testsuite/lib/prune.exp",
        "first": 56,
        "last": 69,
        "about": "And this is where the notes go when they do not count",
        "cite": "gcc/testsuite/lib/prune.exp:56@releases/gcc-16.2.0",
    },
    {
        "name": "scandump",
        "path": "gcc/testsuite/lib/scandump.exp",
        "first": 142,
        "last": 157,
        "about": "A dg-final builds its own test name, and a missing dump is UNRESOLVED not FAIL",
        "cite": "gcc/testsuite/lib/scandump.exp:142@releases/gcc-16.2.0",
    },
    {
        "name": "race",
        "path": "gcc/testsuite/lib/gcc-defs.exp",
        "first": 180,
        "last": 197,
        "about": "How the suite splits across processes, and what it assumes while doing it",
        "cite": "gcc/testsuite/lib/gcc-defs.exp:180@releases/gcc-16.2.0",
    },
    {
        "name": "detect",
        "path": "gcc/testsuite/lib/gcc-defs.exp",
        "first": 199,
        "last": 213,
        "about": "Five steps, left in the source, for the day the assumption is wrong",
        "cite": "gcc/testsuite/lib/gcc-defs.exp:199@releases/gcc-16.2.0",
    },
)


class Failed(RuntimeError):
    """A compilation that did not do what the lesson says it does."""


class Watched(Cache):
    """The ordinary cache, keeping a note of which entries went through it.

    `tools.tier0.orphans` insists that the registry accounts for the store exactly, and it
    works out what a normal experiment asked for from its corpus entry. This one sends twelve
    requests that are not one corpus entry, so the list has to come from here, and a list
    written by the code that made the requests cannot fall out of step with them.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self.used: list[str] = []

    def fetch(self, key: str, send) -> dict:
        self.used.append(key)
        return super().fetch(key, send)


def pinned_commit() -> str:
    done = subprocess.run(
        ["git", "-C", str(GCC_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def read(path: str) -> str:
    target = SUITE / path
    if not target.is_file():
        raise SystemExit(f"no {target}. Run `just gcc-src` first.")
    return target.read_text(encoding="utf-8")


def one(back, name: str, path: str, text: str, args: list[str], dump: str = "") -> dict:
    """Compile one file the way the harness would, and keep the whole result.

    `-S` is not in the argument list because Compiler Explorer adds it. That is a difference
    from the real harness for `dg-do run` tests and for nothing else, and none of the files
    here are `dg-do run`.
    """
    result = back.compile(text, *args, dumps=[dump] if dump else None, filename="input.c")
    stderr, dumped = result.stderr, ""
    if dump:
        # This backend has no files, so the dump comes back on stderr and stderr is the dump.
        # The real harness has both at once, so the two are separated here rather than in the
        # notebook, and a diagnostic hiding in that stream would be a diagnostic thrown away.
        # `-details` is a modifier and not part of the name, so the key is `tree-fre1`.
        dumped = result.dump_text(result.dump_keys[0])
        buried, _ = dejagnu.diagnostics(stderr)
        if buried:
            raise Failed(f"{name} printed a real diagnostic into its dump stream: {buried[0].raw}")
        stderr = ""
    print(f"  {name:<14} rc={result.returncode:<3} {' '.join(args)}")
    return {
        "path": f"gcc/testsuite/{path}",
        "text": text,
        "args": args,
        "returncode": result.returncode,
        "stderr": stderr,
        "dump": dumped,
    }


def spans() -> dict:
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(GCC_ROOT, wanted, PINNED_TAG)


def survey() -> dict:
    """Count the suite, because a reader on Colab has nothing to count.

    Two numbers matter. `walked` is how many C files a native x86-64 run enumerates, which is
    the honest version of "forty thousand tests" and is a fraction of the hundred thousand
    files in the directory. `directives` is how many kinds of directive exist, against which
    the eleven this lesson models can be measured.
    """
    counts: Counter[str] = Counter()
    scanned = 0
    for path in SUITE.rglob("*.c"):
        scanned += 1
        for found in DIRECTIVE.finditer(path.read_text(encoding="utf-8", errors="replace")):
            counts[found.group(1)] += 1

    walked = {name: sum(1 for _ in (SUITE / name).rglob("*.c")) for name in WALKED}
    return {
        "files": sum(1 for path in SUITE.rglob("*") if path.is_file()),
        "exp": sum(1 for _ in SUITE.rglob("*.exp")),
        "scanned": scanned,
        "walked": walked,
        "total": sum(walked.values()),
        "kinds": len(counts),
        "written": sum(counts.values()),
        "directives": dict(counts.most_common()),
        "handled": sorted(dejagnu.KNOWN),
    }


def record() -> dict:
    """Every compilation, in one dictionary, ready to be written out."""
    watched = Watched()
    back = CEBackend(COMPILER, cache=watched)
    tests: dict[str, dict] = {}

    for spec in FILES:
        text = read(spec["path"])
        test = dejagnu.read_test(text, path=spec["path"])
        args = test.command(default=spec["default"]) + list(spec.get("extra", ()))
        tests[spec["name"]] = one(
            back, spec["name"], spec["path"], text, args, spec.get("dump", "")
        )

    # The same file, with the directive line taken out. Not a test in GCC's tree and not
    # pretending to be one: it is what the test above becomes when a rebase eats one line.
    flex = read(FILES[0]["path"])
    stripped = dejagnu.read_test(flex, path=FILES[0]["path"])
    tests["flex-c90"] = one(
        back,
        "flex-c90",
        FILES[0]["path"],
        flex,
        [*dejagnu.ALWAYS, *dejagnu.DEFAULT_CFLAGS],
    )
    if stripped.given == list(dejagnu.DEFAULT_CFLAGS):
        raise Failed("flex-c90 is the same command line as flex, so it demonstrates nothing")

    tortured = read(TORTURED)
    for n, opts in enumerate(dejagnu.torture_list(tortured)):
        tests[f"torture-{n}"] = one(
            back,
            f"torture-{n}",
            TORTURED,
            tortured,
            [*dejagnu.ALWAYS, *opts.split()],
        )

    return {
        "recorded": date.today().isoformat(),
        "tag": PINNED_TAG,
        "commit": pinned_commit(),
        "compiler": back.version(),
        "target": back.target(),
        "cache": sorted(set(watched.used)),
        "survey": survey(),
        "tests": tests,
    }


def check(corpus: dejagnu.Corpus) -> list[str]:
    """Every behavioural fact the notebook states, asserted here instead of in prose.

    A recording is dated, not verified, so this is the only place a change in GCC can be
    caught. All of it is stated the way the notebook states it, and a line that fails here is
    a paragraph that has gone wrong next door.
    """
    wrong: list[str] = []

    def want(condition: bool, saying: str) -> None:
        if not condition:
            wrong.append(saying)

    flex = corpus["flex"]
    results = dejagnu.check(flex.test, flex.stderr)
    want(flex.returncode == 1, f"the flexible array test compiled, rc {flex.returncode}")
    want(len(results) == 4, f"the flexible array test produced {len(results)} results, not 4")
    want(
        all(r.state == "PASS" for r in results),
        f"the flexible array test does not pass: {results}",
    )
    want(
        [e.line for e in flex.test.expectations] == [5, 6, 7],
        "the three dg-error directives are no longer on lines 5, 6 and 7",
    )

    c90 = corpus["flex-c90"]
    left = dejagnu.excess(c90.test, c90.stderr)
    want(bool(left), "the same test under -ansi produces nothing extra, so nothing is shown")
    want(
        any(":8:" in line for line in left),
        f"nothing extra lands on line 8, the struct that is meant to be legal: {left}",
    )
    want(
        dejagnu.check(c90.test, c90.stderr)[-1].state == "FAIL",
        "the wrong standard no longer fails for excess errors",
    )

    assume = corpus["assume"]
    kinds = [d.kind for d in dejagnu.diagnostics(assume.stderr)[0]]
    want(
        kinds == ["error", "note", "error", "note", "warning"],
        f"assume_aligned prints {kinds}, and the two notes are the point of the entry",
    )
    want(assume.test.prune_notes, "attr-assume_aligned-2.c has grown a dg-note")
    want(
        assume.test.given == [] and assume.args[1:3] == ("-ansi", "-pedantic-errors"),
        "the assume_aligned test is no longer the one with no dg-options",
    )
    want(
        all(r.state == "PASS" for r in dejagnu.check(assume.test, assume.stderr)),
        "the assume_aligned test does not pass",
    )

    fre = corpus["fre"]
    replaced = fre.dump.count("Replaced ")
    want(replaced == 6, f"fre1 replaced {replaced} times, not 6")
    want(
        fre.test.finals == ['scan-tree-dump-times "Replaced " 6 "fre1"'],
        f"the dg-final is now {fre.test.finals}",
    )
    want(list(fre.dumps) == ["fre1"], f"the dump is named {list(fre.dumps)}, not fre1")
    want(
        [r.state for r in dejagnu.scan(fre.test, fre.dumps)] == ["PASS"],
        f"the fre1 scan does not pass: {dejagnu.scan(fre.test, fre.dumps)}",
    )
    want(
        all(r.state == "PASS" for r in dejagnu.check(fre.test, fre.stderr)),
        "the fre test printed a diagnostic as well as a dump",
    )

    bogus = corpus["bogus"]
    want(bogus.test.expectations[0].bogus, "pr87309 no longer has a dg-bogus in it")
    want(
        all(r.state == "PASS" for r in dejagnu.check(bogus.test, bogus.stderr)),
        f"pr87309 has come back: {bogus.stderr}",
    )

    torture = [corpus[f"torture-{n}"] for n in range(6)]
    want(len(dejagnu.torture_list(torture[0].text)) == 6, "the torture list is not six long")
    want(
        dejagnu.has_loop(torture[0].text) and not dejagnu.has_loop(corpus["noloop"].text),
        "the two torture files no longer differ in whether they have a loop",
    )
    want(
        all(t.returncode == 0 and not t.stderr.strip() for t in torture),
        "one of the six torture compilations said something",
    )
    want(
        corpus["noloop"].returncode == 0 and not corpus["noloop"].stderr.strip(),
        "the loopless torture test said something",
    )

    count = corpus.survey
    want(bool(count), "the recording has no survey in it, so the first section has no numbers")
    want(
        30_000 < count.get("total", 0) < 50_000,
        f"a native run now walks {count.get('total')} C files, and the lesson says forty thousand",
    )
    want(
        count.get("kinds", 0) > len(count.get("handled", ())),
        "the model now claims to handle every kind of directive there is, which it does not",
    )
    want(
        count.get("directives", {}).get("dg-final", 0)
        > count.get("directives", {}).get("dg-do", 0),
        "dg-final is no longer the most written directive, which the lesson leans on",
    )
    return wrong


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="assert against what is already there")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.check:
        if not SUITE.is_dir():
            print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
            return 1
        body = record()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
        CUTS.parent.mkdir(parents=True, exist_ok=True)
        CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    corpus = dejagnu.load()
    shown = source.load_extract("b04")
    wrong = check(corpus)
    for line in wrong:
        print(f"  {line}")
    print(f"{'wrote' if not args.check else 'checked'} {OUT.relative_to(ROOT)}, {corpus.banner}")
    print(
        f"{'wrote' if not args.check else 'checked'} {CUTS.relative_to(ROOT)}, "
        f"{len(shown)} spans, {shown.lines()} lines"
    )
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
