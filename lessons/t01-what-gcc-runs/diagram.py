"""The one picture in T01 that is not read off a recorded run.

The lesson shows the real chain for one compiler on one machine, which is the honest way to
answer the question. This draws the general shape instead: what each program in the chain
eats, what it produces, and which flag stops the driver before the next one starts. That is
a claim about how the driver is organised rather than a fact about a run, so it is drawn by
hand and lives here.

    python lessons/t01-what-gcc-runs/diagram.py

It writes `diagrams/what-gcc-runs.excalidraw`, which you can open at excalidraw.com and edit.
If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "what-gcc-runs.excalidraw"

#: Each program, and the one line about it that belongs on a picture rather than in prose.
STEPS = [
    ("cc1", "C in, assembly text out.\nEvery optimization happens here.", exdraw.GREEN),
    ("as", "assembly text in, one object file out.\nThis is binutils, not GCC.", exdraw.BLUE),
    (
        "collect2",
        "object files in, one executable out.\nA wrapper that runs the linker.",
        exdraw.YELLOW,
    ),
]

#: Where each flag makes the driver stop, as an index into STEPS.
STOPS = [("-E", 0), ("-S", 0), ("-c", 1)]


def build() -> exdraw.Scene:
    scene = exdraw.Scene("what gcc runs")

    scene.note(
        40,
        20,
        "gcc is a driver. It compiles nothing. It reads your command line, builds\n"
        "command lines for the programs below, and runs them in order.",
        size=18,
    )

    driver = scene.box(40, 120, 240, 80, "gcc\nthe driver", fill=exdraw.RED, size=18)

    scene.note(
        320,
        140,
        "-### prints this whole row\nand runs none of it",
        size=16,
        colour=exdraw.GREY,
    )

    boxes = []
    for n, (name, what, colour) in enumerate(STEPS):
        box = scene.box(40 + n * 320, 300, 280, 130, f"{name}\n\n{what}", fill=colour)
        boxes.append(box)
        scene.arrow(driver, box, "runs" if n == 0 else "")

    for one, other in zip(boxes, boxes[1:], strict=False):
        scene.arrow(one, other)

    for label, index in STOPS:
        box = boxes[index]
        stop = scene.box(
            box.x + 200,
            480 + STOPS.index((label, index)) * 70,
            160,
            50,
            label,
            fill=exdraw.PLAIN,
            dashed=True,
        )
        scene.arrow(box, stop, "stop after", dashed=True, colour=exdraw.GREY)

    scene.note(
        40,
        700,
        "Two things people get wrong about this row.\n"
        "\n"
        "The first is that -E, -S and -c are options to the compiler. They are not. They are\n"
        "instructions to the driver about how far along the row to go, and the compiler never\n"
        "sees them.\n"
        "\n"
        "The second is that the row is fixed. It is not. It comes from how this compiler was\n"
        "configured and what it targets, so two GCCs with the same version number can run a\n"
        "different set of programs and neither of them is broken.",
        size=16,
    )

    scene.note(
        40,
        230,
        "one of these per language: cc1plus for C++, f951 for Fortran, d21 for D,\n"
        "all sharing the same middle end and the same back end",
        size=15,
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
