"""The one picture in T08 that is not read off a recorded run.

The lesson prints the pressure table, the live ranges, the conflicts and the disposition. What
it cannot print is why any of that is necessary, because that is an argument about supply and
demand rather than a number in a dump. Three panels: what the expander hands over and what the
machine actually has, one function's live ranges drawn on a time axis, and the two stage split
between IRA and LRA with the thing each stage is allowed to change.

    python lessons/t08-registers-are-a-lie-until-they-are-not/diagram.py

It writes `diagrams/who-gets-a-register.excalidraw`, which you can open at excalidraw.com and
edit. If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "who-gets-a-register.excalidraw"

#: What the expander produced for p20 and what x86-64 has to put it in. Both numbers are
#: measured, the first from the pseudo count in the ira dump and the second from the
#: allocator's own idea of how many of GENERAL_REGS it may hand out.
DEMAND = """\
p20, after expand

  22 values alive at the busiest point
  42 pseudo registers over the whole function

  a pseudo is a number. there is no limit
  on how many the expander invents."""

SUPPLY = """\
x86-64

  16 general registers in the architecture
  -1 the stack pointer, which is spoken for
  ----
  15 the allocator may hand out"""

#: Four of p20's live ranges, on the compressed point numbering IRA actually uses. Copied off
#: the recorded x86-64 dump rather than drawn by eye: the bars are the `ranges` on each
#: allocno and the colon is where the second region begins. r134 is the longest lived value
#: and keeps a register, r141 is short and keeps one, r116 and r160 are the ones that lose.
RANGES = """\
                0    5    10   15   20   25   30   35   40
                |    |    |    |    |    |    |    |    |
  r134 reg 2        =======================================:=
  r141 reg 43                                       ==
  r116 memory                                         =====:=
  r160 memory                                          ====:=
                                                           ^
                                           the second region starts here"""

#: The two stages and what each is allowed to touch. The point of the panel is that only one
#: of them can change the instructions.
IRA = """\
IRA, gcc/ira.cc

  build allocnos from pseudos
  compute live ranges
  build the conflict graph
  colour it, spilling when it must
  write Disposition:

  changes: which register a pseudo lives in
  does not change: the insns"""

LRA = """\
LRA, gcc/lra.cc, pass named reload

  for each insn:
    does it satisfy its constraints?
    if not, insert a load or a store
    or copy to a register that fits
  repeat until nothing changed

  changes: the insns
  does not change: IRA's answer, mostly"""


def build() -> exdraw.Scene:
    scene = exdraw.Scene("who gets a register")

    scene.note(40, 0, "Who gets a register", size=20)
    scene.note(
        40,
        40,
        "Everything before this point in the compiler could pretend the machine had as many "
        "places to put a value as\nthe program needed. This is where that stops being true, "
        "and it stops being true for one boring reason.",
        size=16,
        colour=exdraw.GREY,
    )

    scene.note(40, 120, "1. Supply and demand", size=18)
    demand = scene.box(40, 160, 480, 190, DEMAND, fill=exdraw.GREEN, size=14)
    supply = scene.box(700, 190, 480, 130, SUPPLY, fill=exdraw.BLUE, size=14)
    scene.arrow(demand, supply, "22 into 15", colour=exdraw.GREY)
    scene.note(
        1240,
        190,
        "Seven values have nowhere to go, so seven\n"
        "of them get an address on the stack instead\n"
        "of a register. That is spilling, and it is not\n"
        "a bug or a failure. It is the only answer\n"
        "available once the counting comes out that\n"
        "way.\n"
        "\n"
        "Same source on aarch64, which hands out 30,\n"
        "and nothing spills at all.",
        size=15,
    )

    scene.note(40, 420, "2. Why the counting is per point and not per function", size=18)
    scene.note(
        40,
        460,
        "Two values only compete if they are both alive at the same instant. A function with a "
        "hundred variables in it\nneeds two registers if only two of them are ever live "
        "together. The unit is the live range, not the variable.",
        size=16,
        colour=exdraw.GREY,
    )
    scene.box(40, 540, 900, 230, RANGES, fill=exdraw.PLAIN, size=14)
    scene.note(
        1000,
        540,
        "A live range is a set of program points, and IRA\n"
        "compresses the point numbering first, so the numbers\n"
        "in a real dump are not source line numbers and not\n"
        "insn numbers. For p20 it compresses 142 points down\n"
        "to 45.\n"
        "\n"
        "Two ranges that touch anywhere conflict. The busiest\n"
        "value in p20 conflicts with 39 of the other 41\n"
        "pseudos, so that part of the graph is a clique and no\n"
        "clever colouring gets out of it.\n"
        "\n"
        "Exactly one pseudo has no conflicts at all. It is\n"
        "alive for two points at the top of the function and\n"
        "dead before the next load happens.",
        size=15,
    )

    scene.note(40, 840, "3. Two passes, and only one of them can rewrite code", size=18)
    scene.note(
        40,
        880,
        "GCC does this twice. IRA decides, then LRA makes the decision legal, and they are "
        "separate passes with a\nhandful of others in between. The second one is still called "
        "reload in the pass list even though reload was\ndeleted in 2013.",
        size=16,
        colour=exdraw.GREY,
    )
    ira = scene.box(40, 980, 520, 240, IRA, fill=exdraw.YELLOW, size=14)
    lra = scene.box(740, 980, 560, 240, LRA, fill=exdraw.RED, size=14)
    scene.arrow(ira, lra, "a disposition", colour=exdraw.GREY)

    scene.note(
        1360,
        980,
        "IRA answers a question about a graph. LRA answers\n"
        "a question about an instruction set, and the second\n"
        "one is why an allocator that looks correct on paper\n"
        "still needs a fixup pass after it.\n"
        "\n"
        "The Pushing and Popping lines in the dump are a\n"
        "trace of one stage of colouring, not the outcome.\n"
        "For p30 they disagree with the Disposition: block\n"
        "about four allocnos. The Disposition: block is the\n"
        "one to read.",
        size=15,
    )

    return scene


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build().document(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
