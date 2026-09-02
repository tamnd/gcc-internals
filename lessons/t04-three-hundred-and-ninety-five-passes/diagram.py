"""The one picture in T04 that is not read off a recorded run.

The lesson counts the passes and shows what they did. This draws the shape they are held in,
which is the part a nested listing hides: the pass list is a tree with two pointers, and only
one of the two cares what the gate said. Once you have seen that, the fact that `-O0` is a
single boolean rather than a list of exceptions stops being surprising.

    python lessons/t04-three-hundred-and-ninety-five-passes/diagram.py

It writes `diagrams/gated-subtree.excalidraw`, which you can open at excalidraw.com and edit.
If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "gated-subtree.excalidraw"

#: The spine, which is a `next` chain at the top level. Label, and whether it is on at -O0.
SPINE = [
    ("tree-cfg", True),
    ("ipa-opt_local_passes", True),
    ("all_optimizations", False),
    ("rtl-expand", True),
    ("rest_of_compilation", True),
]

#: What hangs off all_optimizations by its `sub` pointer, and how many there are in total.
INSIDE = ["tree-ccp1", "tree-fre1", "tree-dom2", "tree-pre"]
INSIDE_TOTAL = 122

TOP = 120
STEP = 110


def build() -> exdraw.Scene:
    scene = exdraw.Scene("gated subtree")

    scene.note(40, 0, "The pass list, at -O0", size=20)
    scene.note(
        40,
        40,
        "Green is a gate that said yes. Red is one that said no.",
        size=16,
        colour=exdraw.GREY,
    )

    spine = []
    for n, (label, on) in enumerate(SPINE):
        fill = exdraw.GREEN if on else exdraw.RED
        spine.append(scene.box(40, TOP + n * STEP, 320, 70, label, fill=fill, size=18))

    for n in range(len(SPINE) - 1):
        scene.arrow(spine[n], spine[n + 1], "next", colour=exdraw.GREY)

    inside = []
    for n, label in enumerate(INSIDE):
        inside.append(
            scene.box(520, TOP + 2 * STEP + n * 90, 260, 60, label, fill=exdraw.PLAIN, size=17)
        )

    scene.arrow(spine[2], inside[0], "sub", dashed=True, colour=exdraw.RED)
    for n in range(len(INSIDE) - 1):
        scene.arrow(inside[n], inside[n + 1], colour=exdraw.GREY)

    scene.note(
        520,
        TOP + 2 * STEP + len(INSIDE) * 90,
        f"and {INSIDE_TOTAL - len(INSIDE)} more, none of which run",
        size=17,
        colour=exdraw.GREY,
    )

    scene.note(
        840,
        TOP,
        "next is followed whatever the gate said.\n"
        "sub is only followed when the gate said yes.\n"
        "\n"
        "So a container with a gate is a switch for\n"
        "everything hanging off it, and the four\n"
        "boxes on the left of it still run at -O0.",
        size=17,
    )

    scene.note(
        840,
        TOP + 250,
        "The gate on all_optimizations is one line:\n"
        "\n"
        "    return optimize >= 1 && !optimize_debug;\n"
        "\n"
        "That line is the whole of what -O0 means to\n"
        "the middle end. There is no list of things\n"
        "-O0 skips kept anywhere, because there does\n"
        "not need to be one.",
        size=17,
        font=exdraw.CODE,
    )

    scene.note(
        40,
        TOP + len(SPINE) * STEP + 20,
        "What the listing does not show.\n"
        "\n"
        "-fdump-passes asks every pass its own gate and prints the answer, so a pass inside a\n"
        "closed container prints ON and never runs. At -O2 that is 60 of the 281 that printed\n"
        "ON, and none of them wrote a dump. The listing is a map of what each pass would say\n"
        "if asked right now. It is not a record of what ran.",
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
