"""The T02 boss fight, graded.

Three questions about where one line of C ends up. Read them off the table in the lesson
first, then run this. It says which ones you got right and prints the evidence either way, so
a wrong answer is something you can go and look at.

    python lessons/t02-five-faces/grade.py
    python lessons/t02-five-faces/grade.py --asm 5=2,6=6,7=1,8=0 --vanished 8 --appeared 9

Nothing here is hardcoded. Every answer is computed from the same recorded dumps the lesson
reads, so re-recording the corpus against a newer compiler cannot leave the grader marking
against a stale answer key.
"""

from __future__ import annotations

import argparse
import sys

from gxray import corpus_store, locs

ENTRY = "l1-O2"

#: The lines the first question asks about. The braces are left out on purpose, because they
#: are the subject of the other two questions and giving them away here would be a shame.
STATEMENTS = [5, 6, 7, 8]


def build() -> locs.Ladder:
    """The same ladder the lesson builds, from the same recording."""
    record = corpus_store.load(ENTRY)
    return locs.ladder(
        record.source,
        generic=record.dump_texts["tree-original"],
        gimple=record.dump_texts["tree-optimized"],
        rtl=record.dump_texts["rtl-expand"],
        asm=record.asm,
        function="f",
    )


def answers(ladder: locs.Ladder) -> dict:
    """The three answers, read off the ladder rather than written down."""
    counts = {rung.line: rung.counts() for rung in ladder.rungs}
    vanished = [line for line, n in counts.items() if n["gimple"] and not n["rtl"] and not n["asm"]]
    appeared = [
        line for line, n in counts.items() if n["rtl"] and not n["generic"] and not n["gimple"]
    ]
    return {
        "asm": {line: counts[line]["asm"] for line in STATEMENTS if line in counts},
        "vanished": vanished,
        "appeared": appeared,
        "counts": counts,
        "ladder": ladder,
    }


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def pairs(text: str) -> dict[int, int]:
    """`5=2,6=6` as a mapping, and anything else as nothing.

    Forgiving about spaces and unforgiving about everything else. A submission that cannot be
    read is a wrong answer rather than a crash.
    """
    found = {}
    for part in text.replace(" ", ",").split(","):
        if not part:
            continue
        line, _, count = part.partition("=")
        if not line.isdigit() or not count.isdigit():
            return {}
        found[int(line)] = int(count)
    return found


def number(text: str) -> int:
    return int(text) if text.strip().isdigit() else -1


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def source_of(ladder: locs.Ladder, line: int) -> str:
    rung = next((r for r in ladder.rungs if r.line == line), None)
    return rung.source.strip() if rung else "no such line"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--asm", help="instructions per line, as 5=2,6=6,7=1,8=0")
    parser.add_argument("--vanished", help="the line with GIMPLE but no RTL and no assembly")
    parser.add_argument("--appeared", help="the line with RTL and assembly but neither tree level")
    args = parser.parse_args(argv)

    ladder = build()
    key = answers(ladder)

    print(f"{ladder}\n")

    said_asm = ask("How many assembly instructions per line? as 5=2,6=6,7=1,8=0:", args.asm)
    said_vanished = ask("Which line has GIMPLE but no RTL and no assembly?", args.vanished)
    said_appeared = ask("Which line has RTL and assembly but neither tree level?", args.appeared)

    scored = [
        mark(
            "which line owns how many instructions",
            pairs(said_asm) == key["asm"],
            ",".join(f"{line}={n}" for line, n in key["asm"].items()),
            [
                f"line {line}  {n:>2} instruction(s)  {source_of(ladder, line)}"
                for line, n in key["asm"].items()
            ],
        ),
        mark(
            "the line that stops at GIMPLE",
            number(said_vanished) in key["vanished"],
            ", ".join(str(line) for line in key["vanished"]) or "no line does that",
            [f"line {line}  {source_of(ladder, line)}" for line in key["vanished"]],
        ),
        mark(
            "the line that only exists below GIMPLE",
            number(said_appeared) in key["appeared"],
            ", ".join(str(line) for line in key["appeared"]) or "no line does that",
            [f"line {line}  {source_of(ladder, line)}" for line in key["appeared"]],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The pair worth sitting with is the last two. The code for the return is on the")
        print("closing brace, and the line that says return has nothing under it at all.")
        return 0
    print("\nThe whole table is one loop away if you want to look at it again:")
    print("    for rung in ladder.rungs: print(rung.line, rung.counts())")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
