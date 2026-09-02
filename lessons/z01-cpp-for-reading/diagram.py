"""The seventeen constructs on one sheet, which is the thing to keep next to you for a week.

A notebook is a bad reference. You read it once, top to bottom, and then it is thirty screens
you have to scroll through to find the one line you wanted. This is the same content laid out
so a glance finds the row, grouped by what a construct is for rather than by the order the
lesson happened to meet it in.

    python lessons/z01-cpp-for-reading/diagram.py

It writes `diagrams/reading-gcc.excalidraw`, which you can open at excalidraw.com and edit.
Print it, or keep it in a second window while you read the tree. That is what it is for.

The T0 exercise is at the bottom and it has the same shape as every other one in the course:
cover the right hand column and say what each construct is, then cover the left and name the
construct from its description.

If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "reading-gcc.excalidraw"

#: The two ways GCC says "one of several kinds of thing", which is most of what an
#: intermediate representation has to do. They differ because they were built decades apart.
SHAPES = """\
tree                 one pointer, one union, hundreds of arms
  TREE_CODE (t)      the tag, sixteen bits, says which arm
  GTY ((tag ("...")))  which arm a struct is, for gengtype
  TREE_TYPE (t)      an accessor macro, and the only way in

gimple *             a real base class, real subclasses
  gassign, gcond     subclasses with no fields of their own
  is_a_helper<T>     one per kind, and it reads the tag
  gimple_assign_lhs  an accessor, written as a function"""

#: The three casts. Everybody reads this page once, and then again a month later.
CASTS = """\
is_a <T> (p)       true or false, and nothing else
as_a <T> (p)       convert, gcc_checking_assert first
dyn_cast <T> (p)   convert, or null if it is not one

  the assert in as_a is a CHECKING assert
  and a release build does not have it

  as_a      "I already know what this is"
  dyn_cast  "I am asking"

  there is no dynamic_cast. GCC builds with
  -fno-rtti, which is why is-a.h exists"""

#: The loops. They are all the same idea, so this box is short on purpose.
WALKS = """\
FOR_EACH_BB_FN (bb, cfun)
    every block except entry and exit

gsi_start_bb  gsi_end_p  gsi_next  gsi_stmt
    a cursor into one block's statements

FOR_EACH_SSA_TREE_OPERAND (def, stmt, iter, ...)
    the operands of one statement

cfun is the function being compiled, a global
the _FN suffix means it takes the function
a macro, because GCC predates the range for"""

#: The two places GCC has its own version of something the standard library already has, and
#: the two places a number is not the number you expect. Both for reasons worth knowing.
OWN = """\
vec<T, A, L>       element, allocator, layout
hash_map<K, V>     GTY((user)), marking written by hand

  not std::vector, because the allocator has
  to be ggc_alloc and the collector has to see it

poly_int<N, C>     a size that is not known yet
  known_eq  maybe_ne  known_lt  maybe_lt
  because == can answer maybe on SVE and RVV

wide_int, widest_int  as wide as the TARGET needs
  wi::to_widest, wi::bit_and, the wi:: namespace
  because the host is not the target"""

#: The furniture. None of it is interesting alone and all of it is on every page, so a reader
#: who does not recognize it spends attention here that should go somewhere else.
FURNITURE = """\
#include "config.h"     always first
#include "system.h"     poisons what GCC will not call
#include "coretypes.h"  the forward declarations
#include "tm.h"         only if the file needs the target
    get the order wrong and you get a thousand
    lines of macro errors naming none of your code

const pass_data pass_data_ccp = { ... };
class pass_ccp : public gimple_opt_pass { ... };
    "ccp" in pass_data is the dump file name
    PROP_cfg | PROP_ssa is what it needs first

if (dump_file && (dump_flags & TDF_DETAILS))
    every line you have ever read in a dump

gcc_assert           on in a release build
gcc_checking_assert  off in a release build

ENUM_BITFIELD(tree_code) code : 16;
    a tree node is the size it is on purpose"""

#: The one paragraph that is the lesson, as opposed to the reference material.
POINT = """\
None of this is hard C++.
All of it is unfamiliar C++.

Those two feel the same from
outside, and they are fixed by
completely different things.

More C++ does not help.
This sheet does."""


def build() -> exdraw.Scene:
    scene = exdraw.Scene("reading-gcc")

    scene.note(40, 40, "Z01. Reading GCC", size=28)
    scene.note(
        40,
        90,
        "Seventeen constructs. Every file under gcc/ is made of these and of ordinary C++ "
        "you have already seen.",
        size=16,
        colour=exdraw.GREY,
    )

    scene.note(40, 160, "1. Two ways to say one of several kinds", size=18)
    shapes = scene.box(40, 210, 640, 280, SHAPES, fill=exdraw.BLUE, size=13, font=exdraw.CODE)

    scene.note(740, 160, "2. The three casts", size=18)
    casts = scene.box(740, 210, 560, 300, CASTS, fill=exdraw.RED, size=13, font=exdraw.CODE)
    scene.arrow(shapes, casts, "one tag, three questions", colour=exdraw.GREY)

    scene.note(1360, 160, "3. Walking things", size=18)
    scene.box(1360, 210, 620, 290, WALKS, fill=exdraw.GREEN, size=13, font=exdraw.CODE)

    scene.note(40, 570, "4. Its own containers, and its own numbers", size=18)
    own = scene.box(40, 620, 640, 300, OWN, fill=exdraw.YELLOW, size=13, font=exdraw.CODE)

    scene.note(740, 570, "5. The furniture on every page", size=18)
    furniture = scene.box(
        740, 620, 620, 470, FURNITURE, fill=exdraw.PLAIN, size=13, font=exdraw.CODE
    )
    scene.arrow(own, furniture, "", colour=exdraw.GREY)

    scene.note(1420, 570, "The point", size=18)
    scene.box(1420, 620, 500, 260, POINT, fill=exdraw.BLUE, size=15, font=exdraw.HAND)

    scene.note(
        1420,
        920,
        "The three people get wrong first:\n"
        "\n"
        "  as_a is not the safe one\n"
        "  GTY does nothing at run time\n"
        "  == on a poly_int may not compile",
        size=15,
    )

    scene.note(40, 980, "The T0 exercise", size=18)
    scene.note(
        40,
        1030,
        "Cover the right hand side of each box and say what every construct on the left is "
        "for. Then cover the left and name\nthe construct from its description. Then open a "
        "file under gcc/ at random and read a page. When you stop, the thing\nyou stopped on "
        "is either on this sheet or it is genuinely new, and telling those two apart is the "
        "whole skill.",
        size=15,
    )
    scene.note(
        40,
        1160,
        "Everything here is cut from releases/gcc-16.2.0 and is in corpora/source/z01.json "
        "with the file and line numbers on it.",
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
