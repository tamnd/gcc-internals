"""Every diagram, rebuilt from the recorded corpus.

    python -m gxmanim draw

This is the script the rule points at. Every diagram in this project is generated from a
`gxray` model by something in the repository, so when the pinned compiler moves the pictures
move with it. No hand placed boxes anywhere, because a hand drawn diagram cannot be
re-rendered when the compiler changes and that is precisely how every existing GCC diagram
on the internet ended up describing GCC 4.

    python -m gxmanim draw --index

writes a contact sheet next to the SVGs with each drawing and the words it says underneath,
which is the page to look at when checking whether a picture is worth keeping.
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

from gxmanim import mobjects, svg
from gxmanim.scene import Scene
from gxray import cfg, corpus_store, gimple, locs, passes, tape

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "l1-O2-passes.txt"

SHEET = """<!doctype html>
<html lang="en">
<meta charset="utf-8" />
<title>gxmanim</title>
<body style="max-width: 64rem; margin: 2rem auto; padding: 0 1rem;
             font: 15px/1.6 system-ui, sans-serif;">
<h1>gxmanim</h1>
<p>{banner}</p>
{figures}
</body>
</html>
"""

FIGURE = """<figure style="margin: 2rem 0;">
{svg}
<figcaption style="color: #57606a; font-size: 14px;">{name}. {caption}</figcaption>
</figure>"""


def scenes(entry: str = "l1-O2") -> dict[str, Scene]:
    """Every drawing this project currently knows how to make, from one recorded build."""
    record = corpus_store.load(entry)
    # Graph dumps are dot files sitting under a `tree-` key, so they are skipped here and
    # picked up by name further down.
    dumps = {
        k: gimple.parse(v).only()
        for k, v in record.dump_texts.items()
        if k.startswith("tree-") and not k.endswith("-graph")
    }
    f = dumps["tree-optimized"]
    pipeline = passes.parse(FIXTURE.read_text(encoding="utf-8"))
    ladder = locs.ladder(
        record.source,
        generic=record.dump_texts.get("tree-original", ""),
        gimple=record.dump_texts.get("tree-optimized", ""),
        rtl=record.dump_texts.get("rtl-expand", ""),
        asm=record.asm,
        function=f.name,
    )
    phi = next(p for b in f.ordered_blocks for p in b.phis)
    name = str(phi.lhs)

    out = {
        "pass-tape": mobjects.pass_tape(tape.cells(pipeline, dumps)),
        "ssa-web": mobjects.ssa_web(f, name),
        "phi-node": mobjects.phi_node(f, phi),
    }
    # Both graph dumps, because the pair is the lesson. The loop has a header block of its
    # own when SSA is built and a single latch by the time the optimizers are done with it,
    # and one drawing of either on its own does not say that.
    for key, when in (("tree-ssa", "at ssa"), ("tree-optimized", "at optimized")):
        if f"{key}-graph" in record.dump_texts:
            graph = cfg.parse(record.dump_texts[f"{key}-graph"])[f.name]
            out[f"cfg-{when.replace(' ', '-')}"] = mobjects.cfg_view(graph)
            out[f"dom-tree-{when.replace(' ', '-')}"] = mobjects.dom_tree(graph)
    # One ladder per source line that anything reached, because which line is worth showing
    # depends on the lesson and the interesting one is rarely the first.
    for rung in ladder.rungs:
        out[f"ladder-line-{rung.line}"] = mobjects.ir_ladder(ladder, rung.line)
    return out


def sheet(drawings: dict[str, Scene], banner: str) -> str:
    figures = [
        FIGURE.format(svg=svg.render(s), name=name, caption=svg.esc(s.caption))
        for name, s in drawings.items()
    ]
    return SHEET.format(banner=banner, figures="\n".join(figures))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gxmanim", description=__doc__)
    ap.add_argument("command", choices=["draw"], help="rebuild every diagram")
    ap.add_argument("--entry", default="l1-O2", help="which recorded corpus entry to draw")
    ap.add_argument("--out", default="build/diagrams")
    ap.add_argument("--index", action="store_true", help="also write a contact sheet")
    ap.add_argument("--open", action="store_true", help="open the contact sheet afterwards")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    drawings = scenes(args.entry)
    for name, scene in drawings.items():
        (out / f"{name}.svg").write_text(svg.document(scene), encoding="utf-8")
    print(f"wrote {len(drawings)} diagrams to {out}")

    if args.index or args.open:
        record = corpus_store.load(args.entry)
        page = out / "index.html"
        page.write_text(
            sheet(drawings, f"{record.compiler} for {record.target}, recorded {record.recorded}."),
            encoding="utf-8",
        )
        print(f"wrote {page}")
        if args.open:
            webbrowser.open(page.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
