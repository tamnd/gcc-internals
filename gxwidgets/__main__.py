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

from gxray import corpus_store, gimple, locs, options, passes
from gxwidgets import FlagDiff, IRLadder, PassTape, PredictGate, SSAWeb, script

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
