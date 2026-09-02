"""The one picture in T06 that is not read off a recorded run.

The lesson prints the tables and diffs them. This draws the machine underneath, which the
diffs cannot show: four integers on one side, one row of `default_options_table` on the other,
and a switch in the middle deciding which way that row goes. Once you have seen a single row
go through it, the rest of the lesson is just that picture a hundred and fourteen times.

    python lessons/t06-what-o2-actually-turns-on/diagram.py

It writes `diagrams/four-integers.excalidraw`, which you can open at excalidraw.com and edit.
If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "four-integers.excalidraw"

#: What each level sets the four to, straight out of the switch in `default_options_optimization`.
#: These are the whole of what the level is by the time the table runs. Everything after this
#: point in the compiler reads these four and never asks which -O you typed.
INTEGERS = """\
           optimize  optimize_size  optimize_debug  optimize_fast
  -O0             0              0               0              0
  -O1             1              0               0              0
  -O2             2              0               0              0
  -O3             3              0               0              0
  -Os             2              1               0              0
  -Oz             2              2               0              0
  -Og             1              0               1              0
  -Ofast          3              0               0              1"""

#: The row being followed, and the test the switch runs for its first word.
ROW = "{ OPT_LEVELS_2_PLUS_SPEED_ONLY,\n    OPT_ftree_loop_vectorize, NULL, 1 }"
TEST = """\
case OPT_LEVELS_2_PLUS_SPEED_ONLY:
  enabled = (level >= 2
             && !size
             && !debug);"""


def build() -> exdraw.Scene:
    scene = exdraw.Scene("four integers")

    scene.note(40, 0, "What an optimization level is", size=20)
    scene.note(
        40,
        40,
        "Four integers, and a table that reads them. There is no list anywhere of what -O2 does.",
        size=16,
        colour=exdraw.GREY,
    )

    scene.note(40, 100, INTEGERS, size=16, font=exdraw.CODE)

    scene.note(
        40,
        340,
        "-Os and -Oz differ in one integer, and the table takes that integer as a\n"
        "yes or no. Both are yes. That is why the two print byte identical tables\n"
        "and are still not the same compiler: the difference is read later, by\n"
        "code that looks at the number rather than at whether it is zero.",
        size=17,
    )

    scene.note(
        820,
        100,
        "The table is 114 rows.\n"
        "\n"
        "Each row is a first word saying when,\n"
        "an option, an argument, and a value.\n"
        "There are 12 words to choose from and\n"
        "GCC 16 uses 6 of them.\n"
        "\n"
        "Every row is read at every level. A\n"
        "level does not pick rows. It hands the\n"
        "switch four integers and the rows sort\n"
        "themselves out.",
        size=17,
    )

    row = scene.box(40, 640, 460, 110, ROW, fill=exdraw.BLUE, size=15, font=exdraw.CODE)
    test = scene.box(600, 625, 400, 140, TEST, fill=exdraw.YELLOW, size=15, font=exdraw.CODE)
    on = scene.box(1100, 540, 340, 90, "on at -O2, -O3, -Ofast", fill=exdraw.GREEN, size=17)
    off = scene.box(1100, 760, 340, 90, "off at -O0, -O1, -Os, -Oz, -Og", fill=exdraw.RED, size=17)

    scene.arrow(row, test, "maybe_default_option", colour=exdraw.GREY)
    scene.arrow(test, on, "true", colour=exdraw.GREEN[0], bend=-0.2)
    scene.arrow(test, off, "false", colour=exdraw.RED[0], bend=0.2)

    scene.note(
        1100,
        660,
        "false does not mean left alone.\n"
        "The same function turns the option\n"
        "off, with the value negated, as long\n"
        "as the row has no argument. So -Os\n"
        "is not -O2 minus a few rows. It is\n"
        "-O2 with those rows arguing the\n"
        "other way.",
        size=16,
    )

    scene.note(
        40,
        900,
        "Where this picture is not the whole story.\n"
        "\n"
        "Two things get past the table. Some options are set by hand in C further down the same\n"
        "file, and -funreachable-traps at opts.cc:1234 is one: it reads optimize and\n"
        "optimize_debug directly and never appears in a row. And a pass can have a gate of its\n"
        "own, so an option being on is not the same as the work happening. Three mechanisms,\n"
        "one of which you can print. The other two you have to go and read.",
        size=17,
    )

    return scene


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build().document(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
