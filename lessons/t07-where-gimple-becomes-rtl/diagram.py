"""The one picture in T07 that is not read off a recorded run.

The lesson prints the chain and opens up single expressions. What it cannot print is the shape
of the thing, because the shape is the reason the dumps look the way they do. One GIMPLE
statement goes into expand and one, two or three RTL insns come out, all of them built from a
single node type that carries a code, a mode and some operands and nothing else. Draw that
node once and the rest of the back end is that node several thousand times.

    python lessons/t07-where-gimple-becomes-rtl/diagram.py

It writes `diagrams/one-statement.excalidraw`, which you can open at excalidraw.com and edit.
If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "one-statement.excalidraw"

#: The statement being followed. It is the accumulate in L1's loop, which is the smallest
#: thing in the program that all four targets disagree about.
GIMPLE = "s_5 = s_9 + i_11;"

#: What that one statement becomes on three of the four targets. Same source, same flags, same
#: version of GCC, and the middle end handed all three the identical GIMPLE.
AARCH64 = """\
(set (reg/v:SI 102 [ <retval> ])
     (plus:SI (reg/v:SI 102 [ <retval> ])
              (reg/v:SI 101 [ i ])))"""
X86 = """\
(parallel [
  (set (reg/v:SI 99) (plus:SI (reg/v:SI 99) (reg/v:SI 98)))
  (clobber (reg:CC 17 flags))])"""
RISCV = """\
(set (reg:DI 138)
     (sign_extend:DI
       (plus:SI (subreg:SI (reg/v:DI 135) 0)
                (subreg:SI (reg/v:DI 134) 0))))"""

#: One node, taken apart. Everything in an RTL dump is this four times a line.
NODE = """\
(plus:SI  (reg/v:SI 102 [ <retval> ])  (reg:SI 101))
 ^^^^ ^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^
 |    |    operand 0                   operand 1
 |    machine mode, 4 bytes of integer
 code, one of 203"""

#: The chain, as it comes out of expand. Every entry is an RTX and only some of them will ever
#: turn into a byte of machine code.
CHAIN = """\
note  1   ->  note  7   ->  insn  2   ->  note  3   ->  debug 9 .. 14
                 |             |
              block 2       the argument arrives"""


def build() -> exdraw.Scene:
    scene = exdraw.Scene("one statement")

    scene.note(40, 0, "One statement, across the hinge", size=20)
    scene.note(
        40,
        40,
        "Everything to the left of expand is about your program. Everything to the right is "
        "about a machine.\nThe same four lines of C reach expand as the same GIMPLE on every "
        "target, and leave as three different things.",
        size=16,
        colour=exdraw.GREY,
    )

    gimple = scene.box(40, 130, 300, 80, GIMPLE, fill=exdraw.GREEN, size=18)
    hinge = scene.box(420, 120, 220, 100, "expand", fill=exdraw.YELLOW, size=20, font=exdraw.HAND)
    scene.note(
        420,
        240,
        "cfgexpand.cc, one\nstatement at a time,\nand not reversible",
        size=15,
        colour=exdraw.GREY,
    )

    arm = scene.box(760, 60, 620, 110, AARCH64, fill=exdraw.BLUE, size=14)
    x86 = scene.box(760, 210, 620, 110, X86, fill=exdraw.BLUE, size=14)
    rv = scene.box(760, 360, 620, 130, RISCV, fill=exdraw.BLUE, size=14)

    scene.arrow(gimple, hinge, colour=exdraw.GREY)
    scene.arrow(hinge, arm, "aarch64", bend=-40)
    scene.arrow(hinge, x86, "x86-64")
    scene.arrow(hinge, rv, "riscv64", bend=40)

    scene.note(
        1420,
        70,
        "one insn.\nthe add is an\nadd and nothing\nelse.",
        size=15,
    )
    scene.note(
        1420,
        220,
        "one insn, two\nthings in it. adding\nwrecks the flags\nand the insn has\nto say so.",
        size=15,
    )
    scene.note(
        1420,
        370,
        "three insns. the\nregisters are 64 bit\nand the arithmetic\nis 32, so the result\n"
        "has to be sign\nextended back.",
        size=15,
    )

    scene.note(40, 560, "What a node is", size=20)
    scene.note(
        40,
        600,
        "There is one struct and every parenthesis above is an instance of it. No separate\n"
        "type for an instruction, an expression or a register. That is why a dump reads\n"
        "uniformly and why a pass can walk anything without knowing what it is walking.",
        size=16,
        colour=exdraw.GREY,
    )
    scene.box(40, 690, 700, 170, NODE, fill=exdraw.PLAIN, size=14)

    scene.note(
        800,
        690,
        "The flags after the slash are printed hints, not\n"
        "part of the expression. /v means this register\n"
        "came from a variable you wrote. /i means it is\n"
        "the value being returned. On a MEM the same two\n"
        "letters mean different things, which is a good\n"
        "reason to look them up rather than guess.\n"
        "\n"
        "The square brackets after a register number are\n"
        "the printer telling you which variable it came\n"
        "from. Delete them and the RTL is unchanged.",
        size=15,
    )

    scene.note(40, 920, "What a function is, after expand", size=20)
    scene.note(
        40,
        960,
        "A doubly linked list, in the order the instructions will run. The blocks are still\n"
        "recorded, on notes in the chain, but they are no longer the thing you walk.",
        size=16,
        colour=exdraw.GREY,
    )
    scene.box(40, 1040, 900, 130, CHAIN, fill=exdraw.PLAIN, size=14)

    scene.note(
        1000,
        1040,
        "In L1 at expand the chain is 40 entries and 13 of them are instructions.\n"
        "The other 27 are notes saying where a block starts, labels, and debug\n"
        "entries recording where a variable lives so a debugger can find it.\n"
        "\n"
        "None of the 27 becomes a byte of machine code. All of them are RTX.",
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
