"""The T05 boss fight, graded.

Three questions about a function you have not seen a dump of. Answer them on paper first,
then run this. It tells you which ones you got right and shows the evidence for each, so a
wrong answer is a thing you can go and look at rather than a mark.

    python lessons/t05-ssa-in-one-lesson/grade.py
    python lessons/t05-ssa-in-one-lesson/grade.py --phis 3 --most total --defaults yes

Nothing here is hardcoded. Every answer is computed from the recorded dump, so re-recording
the corpus against a newer GCC cannot leave the grader marking against a stale answer key.
That has to be true or the grader is worse than no grader.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import gxray
from gxray.gimple import ssa_names

ENTRY = "t05-boss-O2"
PROGRAM = Path(__file__).resolve().parent.parent.parent / "corpora" / "programs" / "t05-boss.c"


def dump() -> tuple[object, str]:
    """The recorded `tree-ssa` dump of the boss program, parsed and as text.

    Both, because the parsed function is the way to ask about blocks and phis, and the text
    is the way to ask which names appear. Going through `str(function)` for the second of
    those gives a one line summary and no names at all, silently, which is a trap worth
    only falling into once.
    """
    result = gxray.corpus(ENTRY).compile(PROGRAM.read_text(encoding="utf-8"))
    return result.dump("tree-ssa").only(), result.dump_text("tree-ssa")


def answers(fn, text: str) -> dict:
    """The three answers, worked out from the dump rather than written down."""
    phis = [(block.index, phi) for block in fn.ordered_blocks for phi in block.phis]
    named = [name for name in ssa_names(text) if name.base]
    versions = Counter(name.base for name in named)
    defaults = [name for name in ssa_names(text) if name.default]
    return {
        "phis": len(phis),
        "where": sorted({block for block, _ in phis}),
        "listing": phis,
        "most": versions.most_common(1)[0][0],
        "counts": versions,
        "defaults": defaults,
    }


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phis", help="how many phi nodes the tree-ssa dump has")
    parser.add_argument("--most", help="which variable has the most versions")
    parser.add_argument("--defaults", help="whether any name carries a (D), yes or no")
    args = parser.parse_args(argv)

    fn, text = dump()
    key = answers(fn, text)

    print(PROGRAM.read_text(encoding="utf-8"))

    said_phis = ask("How many phi nodes?", args.phis)
    said_most = ask("Which variable has the most versions?", args.most)
    said_defaults = ask("Any name with a (D)? yes or no:", args.defaults)

    scored = [
        mark(
            "how many phi nodes",
            said_phis.isdigit() and int(said_phis) == key["phis"],
            f"{key['phis']}, in blocks {', '.join(str(b) for b in key['where'])}",
            [f"<bb {block}>  {phi}" for block, phi in key["listing"]],
        ),
        mark(
            "which variable has the most versions",
            said_most.lower().strip() == key["most"],
            key["most"],
            [
                f"{base}: {count} version{'' if count == 1 else 's'}"
                for base, count in sorted(key["counts"].items())
            ],
        ),
        mark(
            "any default definitions",
            said_defaults.lower().startswith("y") == bool(key["defaults"]),
            "yes" if key["defaults"] else "no",
            [f"{name} has no defining statement" for name in key["defaults"]] or ["none"],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The interesting one is the second phi. Two joins, two phis, and the inner one")
        print("feeds the outer one, which is what a nested join looks like in SSA.")
        return 0
    print("\nThe dump is one line away if you want to look at the whole thing:")
    print(f'    print(gxray.corpus("{ENTRY}").compile(source).dump_text("tree-ssa"))')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
