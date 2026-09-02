"""A page with every widget on it, built from the recorded corpus.

    python -m gxwidgets demo

This is how a widget gets looked at. It needs no compiler, no network and no build step, and
the page it writes is the static fallback with the behaviour module attached, which is
exactly what a lesson page will be. Open it, then open it again with JavaScript turned off,
and the difference should be that the second one does not move.
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

from gxray import corpus_store, gimple, locs, options, passes, regalloc, rtl
from gxwidgets import (
    FlagDiff,
    IRLadder,
    PassTape,
    PredictGate,
    RegAlloc,
    RTXTree,
    SSAWeb,
    TargetCompare,
    script,
)

#: The four back ends T07 puts side by side, in the order the lesson reads them. Two the
#: reader has probably used, then two that make the point, because the point does not land
#: until a machine with no flags register turns up.
TARGETS = {
    "x86-64": "t07-x86-64",
    "aarch64": "t07-aarch64",
    "riscv64": "t07-riscv64",
    "power64le": "t07-power64le",
}

#: The two back ends T08 puts side by side, with the small one first. Fifteen registers
#: against thirty is the whole comparison, and the order is the order the lesson argues in.
PRESSURE = {"x86-64": "t08-x86-64", "aarch64": "t08-aarch64"}

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "l1-O2-passes.txt"

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>gxwidgets</title>
<body style="max-width: 60rem; margin: 2rem auto; padding: 0 1rem;
             font: 15px/1.6 system-ui, sans-serif;">
<h1>gxwidgets</h1>
<p>{banner}</p>
{widgets}
<script type="module">
{script}
attach();
</script>
</body>
</html>
"""


def flagdiff(entry: str = "t06-levels") -> FlagDiff | None:
    """The flag grid, which reads option tables rather than dumps.

    A different corpus entry from everything else on this page, because no one recording
    holds both a pass pipeline and eight printings of the optimizer table. Missing is not an
    error, so that someone who has only run `just corpus` still gets a page.
    """
    try:
        record = corpus_store.load(entry)
    except FileNotFoundError:
        return None
    tables = options.by_level(record.option_texts)
    return FlagDiff(tables) if tables else None


def targetcompare() -> TargetCompare | None:
    """The four back ends, from four Compiler Explorer recordings.

    Four entries rather than one, because one recording is one compiler and the whole widget
    is about four of them. Missing is not an error here either, for the same reason.
    """
    listings, compilers = {}, {}
    for name, entry in TARGETS.items():
        try:
            record = corpus_store.load(entry)
        except FileNotFoundError:
            continue
        listings[name] = rtl.parse(record.dump_texts["rtl-expand"], name).only()
        compilers[name] = record.target
    return TargetCompare(listings, compilers) if listings else None


def pressure() -> RegAlloc | None:
    """The register allocator on five functions, on two targets with different sized files.

    Two entries again, and missing is not an error, so a checkout that has never talked to
    Compiler Explorer still gets a page with the rest of the widgets on it.
    """
    allocations, compilers = {}, {}
    for name, entry in PRESSURE.items():
        try:
            record = corpus_store.load(entry)
        except FileNotFoundError:
            continue
        allocations[name] = regalloc.parse(record.dump_texts["rtl-ira"], name).functions
        compilers[name] = record.target
    return RegAlloc(allocations, compilers) if allocations else None


def build(entry: str = "l1-O2") -> str:
    record = corpus_store.load(entry)
    # Only the tree dumps hold a function body the GIMPLE parser can read. The RTL one is
    # for the ladder, which reads it with a different parser, and a graph key is a dot file
    # sitting beside a tree dump rather than a dump of its own.
    dumps = {
        k: gimple.parse(v).only()
        for k, v in record.dump_texts.items()
        if k.startswith("tree-") and not k.endswith("-graph")
    }
    pipeline = passes.parse(FIXTURE.read_text(encoding="utf-8"))
    f = dumps["tree-ssa"]

    ladder = locs.ladder(
        record.source,
        generic=record.dump_texts.get("tree-original", ""),
        gimple=record.dump_texts.get("tree-optimized", ""),
        rtl=record.dump_texts.get("rtl-expand", ""),
        asm=record.asm,
        function=f.name,
    )

    widgets = [
        PassTape(pipeline, dumps=dumps, function=f.name, options=" ".join(record.args)),
        IRLadder(ladder),
        RTXTree(rtl.parse(record.dump_texts["rtl-expand"], entry).only()),
        SSAWeb(f, name=SSAWeb(f).names[0]),
        PredictGate(
            "This loop runs three times and the trip count is a constant. "
            "How many copies of the body are in the IR after the tree passes?",
            [
                ("Three, the loop is gone", ""),
                (
                    "One, the loop is still a loop",
                    "cunrolli runs early and unrolls a loop whose trip count is small and known, "
                    "so the loop is gone long before the optimized dump.",
                ),
                (
                    "None, the whole thing folds to a constant",
                    "It would if nothing outside used the result, but the sum is returned, so "
                    "the arithmetic has to survive in some form.",
                ),
            ],
            answer="cunrolli peels all three iterations, and what is left is straight line code.",
            observe="\n".join(
                f"  {s.text}" for b in f.ordered_blocks for s in b.stmts if not s.is_debug
            ),
        ),
    ]
    grid = flagdiff()
    if grid is not None:
        widgets.insert(1, grid)
    four = targetcompare()
    if four is not None:
        widgets.append(four)
    two = pressure()
    if two is not None:
        widgets.append(two)

    banner = f"{record.compiler} for {record.target}, recorded {record.recorded}."
    return PAGE.format(
        banner=banner,
        widgets="\n".join(w.render() for w in widgets),
        script=script().replace("</script>", "<\\/script>"),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gxwidgets", description=__doc__)
    ap.add_argument("command", choices=["demo"], help="write a page with every widget on it")
    ap.add_argument("--entry", default="l1-O2", help="which recorded corpus entry to draw")
    ap.add_argument("--out", default="build/widgets.html")
    ap.add_argument("--open", action="store_true", help="open it in a browser afterwards")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(args.entry), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
