"""The T04 boss fight, graded.

Find the answers in the tape first, then run this. It says which of the three you got right
and prints the evidence either way, so a wrong answer is something you can go and look at.

    python lessons/t04-three-hundred-and-ninety-five-passes/grade.py
    python lessons/t04-three-hundred-and-ninety-five-passes/grade.py --pass ccp1 --changed 25

Nothing here is hardcoded. Every answer is computed from the same recording the lesson reads,
so re-recording the corpus against a newer compiler cannot leave the grader marking against a
stale answer key.
"""

from __future__ import annotations

import argparse
import sys

from gxray import corpus_store, gimple, passes, tape

ENTRY = "t04-tape"

#: The level the tape is built at. The recording holds the pass list at five levels and the
#: dumps at this one, because dumping every pass at five levels is 700 files to answer a
#: question no lesson asks.
LEVEL = "-O2"


def dumps() -> dict[str, gimple.Function]:
    """Every tree dump of the recording that has one function with blocks in it.

    Three of the 140 have no function in them at all, `debug`, `earlydebug` and `statistics`,
    because they print something other than a function body. The GENERIC dump has a body and
    no blocks, and it is not GIMPLE, so it is left out too.
    """
    record = corpus_store.load(ENTRY)
    found = {}
    for key, text in record.dump_texts.items():
        functions = list(gimple.parse(text).functions.values())
        if len(functions) == 1 and functions[0].blocks:
            found[key] = functions[0]
    return found


def build() -> list[tape.Cell]:
    """The same tape the lesson builds, from the same recording."""
    record = corpus_store.load(ENTRY)
    return tape.cells(passes.parse(record.pass_texts[LEVEL]), dumps())


def temporaries(function: gimple.Function) -> set[str]:
    """The names gimplification invented, which are the ones with no variable behind them.

    `s_1` is a version of `s` and belongs to the source. `_6` is not a version of anything,
    it is a slot the compiler needed, and the boss fight is about the last one of those.
    """
    return {str(s.lhs) for s in function.code if s.lhs is not None and str(s.lhs).startswith("_")}


def first_without_temporaries(cells: list[tape.Cell]) -> tuple[tape.Cell | None, list[str]]:
    """The first cell whose dump has no temporary left, and the trail up to it."""
    have = dumps()
    trail, seen = [], False
    for cell in cells:
        if cell.stats is None or cell.dump_key not in have:
            continue
        left = sorted(temporaries(have[cell.dump_key]))
        if left:
            seen = True
            trail.append(f"{cell.index + 1:>4} {cell.name:24} {' '.join(left)}")
        elif seen:
            trail.append(f"{cell.index + 1:>4} {cell.name:24} none left")
            return cell, trail
    return None, trail


def only_at(level: str, other: str) -> list[str]:
    """The passes on at one level and off at another, by short name."""
    record = corpus_store.load(ENTRY)
    off = {p.name for p in passes.parse(record.pass_texts[other]).enabled}
    return sorted(
        p.short_name for p in passes.parse(record.pass_texts[level]).enabled if p.name not in off
    )


def answers(cells: list[tape.Cell]) -> dict:
    """The three answers, read off the recording rather than written down."""
    killer, trail = first_without_temporaries(cells)
    changed = [c for c in cells if c.changed]
    return {
        "pass": killer.short if killer else "",
        "trail": trail,
        "changed": len(changed),
        "changed_names": [c.name for c in changed],
        "only_os": only_at("-Os", "-O2"),
        "levels": {
            level: len(passes.parse(corpus_store.load(ENTRY).pass_texts[level]).enabled)
            for level in ("-O0", "-O1", "-O2", "-O3", "-Os")
        },
    }


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def named(said: str, answer: str) -> bool:
    """A pass answer, forgiving about the phase prefix.

    `ccp1` and `tree-ccp1` are the same pass and the reader may have copied either, since the
    tape shows the long name and the dump file carries the short one.
    """
    return said.strip().removeprefix("tree-").removeprefix("rtl-").removeprefix("ipa-") == answer


def number(text: str) -> int:
    return int(text) if text.strip().isdigit() else -1


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pass", dest="killer", help="the pass that removes the last temporary")
    parser.add_argument("--changed", help="how many passes changed the IR of f")
    parser.add_argument("--only-os", dest="only_os", help="the pass on at -Os and off at -O2")
    args = parser.parse_args(argv)

    cells = build()
    key = answers(cells)

    print(f"{len(cells)} passes on at {LEVEL}, {len([c for c in cells if c.stats])} with a dump\n")

    said_pass = ask("Which pass removes the last temporary?", args.killer)
    said_changed = ask(f"How many of the {len(cells)} changed the IR?", args.changed)
    said_os = ask("Which pass is on at -Os and off at -O2?", args.only_os)

    scored = [
        mark(
            "the pass that removes the last temporary",
            named(said_pass, key["pass"]),
            key["pass"],
            key["trail"][-6:],
        ),
        mark(
            "how many passes changed the IR",
            number(said_changed) == key["changed"],
            str(key["changed"]),
            [", ".join(key["changed_names"][:8]) + ", and so on"],
        ),
        mark(
            "the pass -Os turns on and -O2 does not",
            any(named(said_os, name) for name in key["only_os"]),
            " or ".join(key["only_os"]),
            [f"{level} turns on {count}" for level, count in key["levels"].items()],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one to sit with is the third. Optimization levels are not a slider, they")
        print("are three different opinions about what a good compilation looks like, and -Os")
        print("holds one that -O2 does not.")
        return 0
    print("\nThe trail for the first question is one loop away if you want to look again:")
    print("    for line in answers(build())['trail']: print(line)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
