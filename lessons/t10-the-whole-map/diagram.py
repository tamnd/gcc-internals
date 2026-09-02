"""The whole compiler on one sheet, which is the picture the notebook cannot print.

Every other artefact in T10 is read off a recording. This one is the shape those recordings
have in common, and shape is the thing a table of numbers is worst at. Four rows of stages,
left to right, with what is in the compiler's hands under each one, and the two boundaries in
`passes.def` drawn as boundaries rather than as line numbers.

    python lessons/t10-the-whole-map/diagram.py

It writes `diagrams/the-whole-map.excalidraw`, which you can open at excalidraw.com and edit.
The T0 exercise for this lesson is to delete the fourteen stage labels and put them back, so
open it, select the top row of each box, and see how far you get.

If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "the-whole-map.excalidraw"

#: The four stages before the pass manager exists. None of them is in `passes.def` and none of
#: them will ever appear in `-fdump-passes`, which is the first thing this picture is for.
FRONT = """\
1  the driver          gcc, which runs other programs
2  preprocess          cc1 -E, or cc1 doing it inline
3  parse               C text becomes GENERIC
4  gimplify            GENERIC becomes GIMPLE

   none of these four is a pass
   the pass manager has not started yet"""

#: The tree half. Five stages, all of them passes, and the two boundary lines in `passes.def`
#: that the whole middle end is arranged around.
TREE = """\
 5  build the CFG       tree-cfg
 6  into SSA            tree-ssa
 7  early optimizers    tree-early_optimizations
 8  interprocedural     ipa-inline, 24 ipa passes
 9  tree optimizers     ends at tree-optimized

    passes.def:59   NEXT_PASS (pass_build_ssa)
    passes.def:460  NEXT_PASS (pass_expand)"""

#: The RTL half. Four stages, all passes, and the one that is not GCC.
BACK = """\
10  expand              rtl-expand, and out of SSA
11  RTL optimizers      rtl-combine and the rest
12  register allocation rtl-ira, rtl-reload
13  final               rtl-final, writes the text

14  assemble            as, a different program"""

#: What the compiler is holding at each of the four boundaries. This is the row a reader
#: forgets, because the stage names are easy and the data structures are the point.
HOLDS = """\
after parse       a GENERIC tree, one node per expression
after gimplify    a GIMPLE sequence, three address form
after tree-cfg    basic blocks and edges, statements inside them
after tree-ssa    every name written once, phi nodes at the joins
after expand      an insn chain, RTX trees, and the same CFG
after ira, lra    the same chain with hard registers in it
after final       a text file, and nothing else"""

#: The numbers off the recorded run of `nearest`. They are here so the picture and the notebook
#: cannot drift apart without someone noticing, and because the ratio is the lesson.
COUNTS = """\
nearest, L2 at -O2, GCC 16.2.0 aarch64

  395  passes in the list
  281  enabled at -O2
  135  wrote a dump we can measure
   36  changed the function
   98  ran and changed nothing
  147  no evidence either way

   34  statements at tree-optimized
   25  instructions in the file"""

#: The one expression, all the way down, which is the boss fight drawn.
TRACE = """\
l2.c:10   return dx * dx + dy * dy;

einline      the statements move into nearest, twice
release_ssa  the names are renumbered, nothing else
sink1        one of them moves nearer its use
ifcvt        a second copy appears, for the vectorizer
vect         the vectorizer says no, the copy goes
expand       mults and adds, as separate insns
combine      a mult and a plus fuse, twice
final        maddsi prints  madd w7, w7, w7, w3"""


def build() -> exdraw.Scene:
    scene = exdraw.Scene("the-whole-map")

    scene.note(40, 40, "T10. The whole map", size=28)
    scene.note(
        40,
        90,
        "Fourteen stages. Five of them are not passes, and those five are the ones a pass "
        "list will never tell you about.",
        size=16,
        colour=exdraw.GREY,
    )

    scene.note(40, 160, "1. The fourteen stages, in order", size=18)
    front = scene.box(40, 210, 520, 230, FRONT, fill=exdraw.YELLOW, size=13, font=exdraw.CODE)
    tree = scene.box(620, 210, 600, 250, TREE, fill=exdraw.BLUE, size=13, font=exdraw.CODE)
    back = scene.box(1280, 210, 580, 200, BACK, fill=exdraw.GREEN, size=13, font=exdraw.CODE)
    scene.arrow(front, tree, "the pass manager starts here", colour=exdraw.GREY)
    scene.arrow(back, tree, "", colour=exdraw.GREY)

    scene.note(
        620,
        490,
        "Nine of the fourteen are passes. Stage 14 is a different program, and stages 1 to 4\n"
        "happen before the first line of passes.def runs.",
        size=15,
        colour=exdraw.GREY,
    )

    scene.note(40, 580, "2. What the compiler is holding", size=18)
    holds = scene.box(40, 630, 900, 230, HOLDS, fill=exdraw.PLAIN, size=13, font=exdraw.CODE)
    scene.note(
        40,
        890,
        "The stage names are the easy half. The right hand column is the half people get "
        "wrong, and the one to check\nyourself on: the CFG appears before SSA and outlives "
        "it, and the insn chain and the CFG exist at the same time.",
        size=15,
        colour=exdraw.GREY,
    )

    scene.note(1020, 580, "3. What it cost, on one function", size=18)
    counts = scene.box(1020, 630, 480, 300, COUNTS, fill=exdraw.RED, size=13, font=exdraw.CODE)
    scene.arrow(holds, counts, "", colour=exdraw.GREY)
    scene.note(
        1020,
        960,
        "Thirty six of two hundred and eighty one.\nA pass is a question, and most questions\n"
        "have the answer no.",
        size=15,
        colour=exdraw.GREY,
    )

    scene.note(40, 1020, "4. One expression, from the source line to the instruction", size=18)
    trace = scene.box(40, 1070, 720, 260, TRACE, fill=exdraw.BLUE, size=13, font=exdraw.CODE)
    scene.note(
        820,
        1070,
        "Two of the eight rows are not what anyone means by a pass changing the code.\n"
        "release_ssa only moved the numbers, and ifcvt made a copy that vect threw away.\n"
        "\n"
        "They are on the list because the evidence says so, and working out why they are\n"
        "there is more of the lesson than the six that did real work.",
        size=15,
    )
    scene.note(
        820,
        1230,
        "The IR grows before it shrinks. Fifty eight statements at ifcvt, thirty four at the\n"
        "end. Inline first so there is something to work with, then spend two hundred\n"
        "passes taking it back apart.",
        size=15,
        colour=exdraw.GREY,
    )

    scene.note(40, 1400, "The T0 exercise", size=18)
    scene.note(
        40,
        1450,
        "Delete the fourteen stage names from the three boxes at the top and put them back "
        "from memory. Then do the\nsame with the right hand column of box 2, which is harder "
        "and worth more. If you can do both, you have the map.",
        size=15,
    )
    scene.arrow(trace, holds, "", colour=exdraw.GREY, bend=0.2)

    return scene


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build().document(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
