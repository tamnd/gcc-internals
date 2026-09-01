"""The one picture in T03 that is not read off a recorded run.

The lesson shows what GCC did to seven expressions. This draws why it did it, which is one
rule applied over and over: every interior node of the expression tree becomes a statement,
in the order a depth first walk reaches them, and the leaves become nothing because they are
already values. Once you have seen it on one small tree the other six functions are obvious.

    python lessons/t03-gimple-is-c-with-the-fun-removed/diagram.py

It writes `diagrams/one-rule.excalidraw`, which you can open at excalidraw.com and edit. If
you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "one-rule.excalidraw"

#: The tree for `(a + b) * (a - c)`, as label, x, y, and whether it is an interior node.
#: Laid out by hand because four leaves and three operators is not worth a tree layout pass.
NODES = [
    ("*", 250, 60, True),
    ("+", 120, 190, True),
    ("-", 380, 190, True),
    ("a", 50, 320, False),
    ("b", 190, 320, False),
    ("a", 310, 320, False),
    ("c", 450, 320, False),
]

#: Which node is under which, by index into NODES.
EDGES = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]

#: What GCC wrote, in the order it wrote it, and which node each line came from.
STATEMENTS = [("_1 = a + b;", 1), ("_2 = a - c;", 2), ("D.4635 = _1 * _2;", 0)]


def build() -> exdraw.Scene:
    scene = exdraw.Scene("one rule")

    scene.note(
        50,
        0,
        "return (a + b) * (a - c);",
        size=20,
        font=exdraw.CODE,
    )

    boxes = []
    for label, x, y, interior in NODES:
        fill = exdraw.GREEN if interior else exdraw.PLAIN
        boxes.append(scene.box(x, y, 90, 70, label, fill=fill, size=20))

    for parent, child in EDGES:
        scene.arrow(boxes[parent], boxes[child], colour=exdraw.GREY)

    lines = []
    for n, (text, _) in enumerate(STATEMENTS):
        lines.append(scene.box(760, 90 + n * 110, 300, 70, text, fill=exdraw.BLUE))

    for n, (_, node) in enumerate(STATEMENTS):
        scene.arrow(boxes[node], lines[n], "becomes", dashed=True, colour=exdraw.GREEN)

    scene.note(
        50,
        440,
        "The green nodes are the ones with an operator in them. There are three, and GIMPLE\n"
        "has three statements. That is the whole rule.",
        size=17,
    )

    scene.note(
        760,
        20,
        "in this order, depth first, left to right",
        size=16,
        colour=exdraw.GREY,
    )

    scene.note(
        50,
        530,
        "Why the order is the order.\n"
        "\n"
        "A statement can only mention values that already exist, so a node has to be written\n"
        "out after both of its children. That is a post-order walk, and it is why the first\n"
        "line of GIMPLE corresponds to the deepest leftmost operator in the source rather\n"
        "than to the one you read first.\n"
        "\n"
        "The leaves get nothing. a, b and c are already values, and a value needs no\n"
        "statement to compute it. This is the difference the whole representation turns on:\n"
        "GIMPLE allows a value anywhere an operand is wanted, and allows nothing else.",
        size=16,
    )

    scene.note(
        760,
        440,
        "D.4635 is the return slot, which the front\n"
        "end makes for every function. _1 and _2 are\n"
        "the ones gimplification invented, one per\n"
        "interior node it could not leave nested.",
        size=16,
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
