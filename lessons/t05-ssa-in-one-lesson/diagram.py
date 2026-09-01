"""The one picture in T05 that is not drawn from a dump.

Everything else in the lesson is generated from the recorded output of a real compiler, which
is the right way to show what GCC did. This one shows why a phi has to exist at all, and that
is an argument rather than a piece of data, so somebody has to decide what goes where.

    python lessons/t05-ssa-in-one-lesson/diagram.py

It writes `diagrams/phi-at-a-join.excalidraw`, which you can open at excalidraw.com and edit.
If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "phi-at-a-join.excalidraw"


def build() -> exdraw.Scene:
    scene = exdraw.Scene("why a phi has to be there")

    scene.note(
        40,
        20,
        "Two paths reach the top of the loop, each carrying a\n"
        "different value for s. SSA does not allow a name with\n"
        "two definitions, so something has to name both.",
        size=18,
    )

    before = scene.box(60, 150, 260, 90, "<bb 2>\ns_3 = 0;\ni_4 = 0;", fill=exdraw.BLUE)
    body = scene.box(
        520, 150, 260, 90, "<bb 3>\ns_8 = s_1 + i_2;\ni_9 = i_2 + 1;", fill=exdraw.GREEN
    )

    header = scene.box(
        200,
        360,
        440,
        120,
        "<bb 4>\n# s_1 = PHI <s_3(2), s_8(3)>\n# i_2 = PHI <i_4(2), i_9(3)>\nif (i_2 < n_5(D))",
        fill=exdraw.YELLOW,
    )

    after = scene.box(60, 590, 260, 90, "<bb 5>\n_6 = s_1;\nreturn _6;", fill=exdraw.PLAIN)

    scene.arrow(before, header, "s is s_3\non this path")
    scene.arrow(body, header, "s is s_8\non this path")
    scene.arrow(header, body, "round again", bend=200)
    scene.arrow(header, after, "done")

    scene.note(
        60,
        720,
        "The phi is not an instruction. Nothing computes it and no machine has one.\n"
        "It is a note saying which value s_1 stands for on each way in, and the\n"
        "arguments are positional: first one for bb 2, second one for bb 3.\n"
        "Out of SSA deletes it again before any code is generated.",
        size=16,
    )

    scene.note(700, 400, "one argument\nper incoming\nedge", size=16, colour=exdraw.GREY)

    return scene


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build().document(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
