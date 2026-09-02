"""The tree and the routes on one sheet, for the window next to the one you are digging in.

    python lessons/z02-where-things-are/diagram.py

It writes `diagrams/finding-things.excalidraw`, which opens at excalidraw.com and edits.

The notebook explains why each of these is true. This is the part you need again three weeks
later, when you have forgotten the explanation and only want the answer: which directory, what
that extension means, and which of the routes gets you from what the compiler printed to the
line that printed it.

Every number here is from `corpora/layout/gcc.json` at releases/gcc-16.2.0, so if the counts
in the notebook move, run `just corpus-z02` and then this, and both will move together.

If you do edit the drawing, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import layout  # noqa: E402
from tools import exdraw  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "finding-things.excalidraw"

#: The four extensions, which is the single highest value thing on the sheet, because getting
#: one of them wrong costs an hour and getting all four right costs a glance.
KINDS = """\
.cc  .h     ordinary C++, and the accessor macros
.def        an X macro list, included several times
              with the macro defined differently
.md         a machine description. NOT markdown.
              Lisp like patterns for one target
.opt        one command line flag per stanza
.pd         exactly one file: gcc/match.pd"""

#: The generated files. Every one of these is a real name a reader has been sent to by a
#: backtrace, and none of them is in the tree.
NOBODY = """\
in the build dir, not in the tree, read instead:

gimple-match-N.cc      gcc/match.pd
generic-match-N.cc     gcc/match.pd
insn-recog.cc          the target's .md files
insn-emit.cc           the target's .md files
insn-output.cc         the target's .md files
insn-attrtab.cc        the target's .md files
insn-flags.h           the target's .md files
insn-modes.cc          the target's modes.def
options.cc  options.h  the .opt that declares it
gtype-desc.cc          the GTY marker gengtype read
tree-check.h           gcc/tree.def
tm.h                   the target's config headers

the giveaway: a five digit line number in a
file nobody would have written by hand"""

#: The chain. This is the one thing in the lesson that is a procedure rather than a fact.
CHAIN = """\
     hunt.c.114t.ccp2
              |
   strip the run number -> ccp
              |
   grep pass_ccp gcc/passes.def
     tells you WHERE it runs
              |
   grep make_pass_ccp
     tells you WHAT FILE it is
              |
     gcc/tree-ssa-ccp.cc

or skip all of it in a notebook:

  tree.find("ccp2")"""

#: The point, in the voice the rest of the course uses when it stops explaining and says the
#: thing outright.
POINT = """\
Nobody knows where anything is.

The people who look like they do
are running one of five routes,
in under a minute, and then
reading the answer.

Pick the route from the shape of
what you are looking at. That is
the entire trick."""


def opening(about: str) -> str:
    """The first sentence of a place's description, without cutting `stddef.h` in half."""
    head, _, _ = about.partition(". ")
    return head.rstrip(".")


def sizes() -> tuple[str, str]:
    """The two count boxes, filled in from the recorded map rather than typed.

    The inside table drops anything under two thousand lines. Those directories are real and
    the notebook lists them, but a sheet you glance at wants the twenty that come up rather
    than the thirty that exist.
    """
    tree = layout.load()
    tests = tree.place("gcc/testsuite")
    whole = tree.place("gcc")
    proper = whole.lines - tests.lines

    top = "\n".join(
        f"{place.path:<14}{place.lines // 1000:>6}k   {opening(place.about)}"
        for place in tree.places
        if "/" not in place.path
    )
    small = sum(1 for p in tree.places if p.path.startswith("gcc/") and p.lines < 2000)
    inside = "\n".join(
        f"{place.path:<16}{place.lines // 1000:>6}k   {opening(place.about)}"
        for place in sorted(tree.places, key=lambda p: -p.lines)
        if place.path.startswith("gcc/") and place.lines >= 2000
    )
    inside += f"\n\nand {small} more under two thousand lines, in the notebook"
    header = (
        f"{tree.files} source files, {tree.lines // 1000000}.{tree.lines // 100000 % 10}M lines\n"
        f"the compiler without its tests is {proper // 1000}k of that\n"
    )
    return (header + "\n" + top, inside)


def routes() -> str:
    """The five routes worth having on paper, in the order to try them."""
    lines = []
    for key in ("grep", "passes", "generated", "history", "blame"):
        name, command, _ = layout.route(key)
        lines.append(f"{name}\n    {command}\n")
    return "\n".join(lines).rstrip()


def build() -> exdraw.Scene:
    scene = exdraw.Scene("finding-things")
    top, inside = sizes()

    scene.note(40, 40, "Z02. Finding things in GCC", size=28)
    scene.note(
        40,
        90,
        "The tree, and the five routes from something the compiler printed to the line that "
        "printed it.",
        size=16,
        colour=exdraw.GREY,
    )

    scene.note(40, 160, "1. The top level", size=18)
    scene.box(40, 210, 700, 340, top, fill=exdraw.BLUE, size=12, font=exdraw.CODE)

    scene.note(800, 160, "2. Inside gcc/, which is the only one that matters", size=18)
    scene.box(800, 210, 780, 620, inside, fill=exdraw.PLAIN, size=11, font=exdraw.CODE)

    scene.note(40, 590, "3. Four extensions that are not what they look like", size=18)
    kinds = scene.box(40, 640, 700, 240, KINDS, fill=exdraw.GREEN, size=13, font=exdraw.CODE)

    scene.note(1640, 160, "4. Nobody wrote this file", size=18)
    nobody = scene.box(1640, 210, 640, 460, NOBODY, fill=exdraw.RED, size=12, font=exdraw.CODE)
    scene.arrow(kinds, nobody, ".md in, .cc out", colour=exdraw.GREY, bend=0.2)

    scene.note(40, 930, "5. The routes, in the order to try them", size=18)
    scene.box(40, 980, 700, 400, routes(), fill=exdraw.YELLOW, size=12, font=exdraw.CODE)

    scene.note(800, 880, "6. From a dump file name to the source", size=18)
    scene.box(800, 930, 560, 450, CHAIN, fill=exdraw.BLUE, size=13, font=exdraw.CODE)

    scene.note(1420, 880, "The point", size=18)
    scene.box(1420, 930, 480, 280, POINT, fill=exdraw.PLAIN, size=15, font=exdraw.HAND)

    scene.note(
        1640,
        700,
        "Three things people get wrong first:\n"
        "\n"
        "  gcc/config has 52 directories\n"
        "  and 49 of them are ports\n"
        "\n"
        "  Simulating statement is printed by\n"
        "  tree-ssa-propagate.cc, not by the\n"
        "  pass whose dump it lands in\n"
        "\n"
        "  git grep never answers when, and\n"
        "  when is often the real question",
        size=14,
    )

    scene.note(1420, 1240, "The Z02 exercise", size=18)
    scene.note(
        1420,
        1290,
        "Six things a real gcc-16 printed, find where each came from:\n"
        "    python lessons/z02-where-things-are/grade.py\n"
        "Two of them cannot be answered from a checkout at all.",
        size=14,
    )
    scene.note(
        40,
        1430,
        "Counts from corpora/layout/gcc.json at releases/gcc-16.2.0, recorded by walking the "
        "tree. Run just corpus-z02 to redo them.",
        size=14,
        colour=exdraw.GREY,
    )

    return scene


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build().document(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
