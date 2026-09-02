"""Record everything T06 reads.

A recipe in the justfile would normally do this, and for the other lessons it does. This
one is a script because half of what gets recorded is not a fixed command line. The lesson
asks how few of the flags between `-O1` and `-O2` a given function actually notices, and
answering that means diffing two tables, turning every difference into a flag, and then
compiling fifty odd times to find out which of them can be dropped. None of that fits on a
line of a makefile and all of it has to be reproducible, so it lives here.

Four entries come out:

    t06-levels   the optimizer table and the param table at every level, plus L1's
                 assembly at every level and for each step of the rebuild
    t06-l0       L0's assembly at -O1, at -O2, and with the flags L0 turns out to need
    t06-l2       the same for L2
    t06-fast     one float loop at -O3 and at -Ofast, which is what -Ofast costs

The irreducible sets are found by walking GCC's own print order and dropping one flag at a
time, keeping the drop when the assembly still matches. That finds a set nothing can be
removed from. It does not find the smallest such set, and a different order would find a
different one, so the lesson says irreducible rather than minimal.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import corpus_store, driver, options  # noqa: E402

# Every level worth printing a table for. -Oz is here because it is the one pair in the
# list that the table cannot tell apart from its neighbour, which is a fact about the
# table rather than about the two levels, and the lesson needs both to show it.
LEVELS = ["-O0", "-O1", "-O2", "-O3", "-Os", "-Oz", "-Og", "-Ofast"]

# Params are printed at fewer levels. The table is three hundred and twenty three lines
# and it only moves between -O1, -O2, -O3 and -Os, so recording the other four would add
# ninety kilobytes to the repository to say nothing four times.
PARAM_LEVELS = ["-O1", "-O2", "-O3", "-Os", "-Oz"]

PROGRAMS = {
    "l0": ROOT / "corpora/programs/l0.c",
    "l1": ROOT / "corpora/programs/l1.c",
    "l2": ROOT / "corpora/programs/l2.c",
    "fast": ROOT / "corpora/programs/t06-fast.c",
}


def rebuild_flags(gcc: driver.LocalBackend) -> tuple[list[str], list[str]]:
    """The flags that spell out the difference between `-O1` and `-O2`, in two piles.

    Switches first, then options that took a new value, because the whole point of the
    exercise is that a reader who only reads the switches gets it wrong and has to be able
    to see the second pile arriving separately.
    """
    one = gcc.options("optimizers", "-O1")
    two = gcc.options("optimizers", "-O2")
    switches, values = [], []
    for change in options.diff(one, two):
        flag = change.as_flag()
        if flag is None:
            continue
        (switches if change.kind == "on" else values).append(flag)
    return switches, values


def irreducible(gcc: driver.LocalBackend, source: str, flags: list[str], target: str) -> list[str]:
    """The flags that cannot be dropped without the assembly changing.

    Dropped in the order they were given, which is GCC's own print order, so the answer is
    the same on every machine that runs this.
    """
    keep = list(flags)
    for flag in list(flags):
        trial = [f for f in keep if f != flag]
        if gcc.compile(source, "-O1", *trial).asm == target:
            keep = trial
    return keep


def write(gcc, entry: str, program: str, asm_flags: list[list[str]], **rest) -> None:
    source = PROGRAMS[program].read_text(encoding="utf-8")
    record = corpus_store.record(
        gcc,
        entry,
        source,
        "-O2",
        dumps=["tree-optimized"],
        filename=PROGRAMS[program].name,
        assemblies=asm_flags,
        **rest,
    )
    record.recorded = date.today().isoformat()
    path = corpus_store.save(record)
    print(f"wrote {path}: {len(record.asm_texts)} listings, {len(record.option_texts)} tables")


def main(argv: list[str] | None = None) -> int:
    which = (argv if argv is not None else sys.argv[1:] or ["gcc-16"])[0]
    gcc = driver.local(which)
    if not gcc.available:
        print(f"{which} is not on PATH, and the corpus has to come from the pinned compiler")
        return 2

    switches, values = rebuild_flags(gcc)
    print(f"-O1 to -O2 is {len(switches)} switches and {len(values)} new values")

    steps = {
        "l0": [],
        "l1": [
            ["-O1", *switches],
            ["-O1", *switches, *values],
        ],
        "l2": [],
    }
    for program in ("l0", "l1", "l2"):
        source = PROGRAMS[program].read_text(encoding="utf-8")
        target = gcc.compile(source, "-O2").asm
        needed = irreducible(gcc, source, [*switches, *values], target)
        print(f"{program} needs {len(needed)}: {' '.join(needed)}")
        steps[program].append(["-O1", *needed])

    write(
        gcc,
        "t06-levels",
        "l1",
        [[level] for level in LEVELS] + steps["l1"],
        tables=[["optimizers", level] for level in LEVELS]
        + [["params", level] for level in PARAM_LEVELS],
    )
    write(gcc, "t06-l0", "l0", [["-O1"], ["-O2"], *steps["l0"]])
    write(gcc, "t06-l2", "l2", [["-O1"], ["-O2"], *steps["l2"]])
    write(gcc, "t06-fast", "fast", [["-O2"], ["-O3"], ["-Ofast"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
