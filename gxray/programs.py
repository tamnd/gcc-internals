"""The three canonical programs, as strings, so a notebook does not need the filesystem.

Same files as `corpora/programs/`, read from there so the two can never drift apart. A
lesson writes `gxray.L1` and gets the same bytes the corpus was recorded from.
"""

from __future__ import annotations

from pathlib import Path

PROGRAM_DIR = Path(__file__).resolve().parent.parent / "corpora" / "programs"


def _read(name: str) -> str:
    return (PROGRAM_DIR / name).read_text(encoding="utf-8")


L0 = _read("l0.c")
L1 = _read("l1.c")
L2 = _read("l2.c")

ALL = {"L0": L0, "L1": L1, "L2": L2}
