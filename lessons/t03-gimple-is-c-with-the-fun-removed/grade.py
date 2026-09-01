"""The T03 boss fight, graded.

Hand gimplify the `deeper` function first, on paper, then run this. It says which of the
three you got right and prints the evidence either way, so a wrong answer is something you
can go and look at.

    python lessons/t03-gimple-is-c-with-the-fun-removed/grade.py
    python lessons/t03-gimple-is-c-with-the-fun-removed/grade.py --ops "+,-,*,+,-,*,+" --temps 6

Nothing here is hardcoded. Every answer is computed from the same recorded dump the lesson
reads, so re-recording the corpus against a newer compiler cannot leave the grader marking
against a stale answer key.
"""

from __future__ import annotations

import argparse
import sys

from gxray import corpus_store, gimple

ENTRY = "t03-bench"

#: The function the reader was asked to do by hand. The other six are on the bench so that
#: the third question has somewhere to look.
SUBJECT = "deeper"


def build() -> gimple.GimpleDump:
    """The same parsed dump the lesson builds, from the same recording."""
    record = corpus_store.load(ENTRY)
    return gimple.parse(record.dump_texts["tree-gimple"])


def answers(bench: gimple.GimpleDump) -> dict:
    """The three answers, read off the dump rather than written down."""
    fn = bench.functions[SUBJECT]
    ops = [stmt.operator for stmt in fn.code if stmt.operator]
    temps = {str(stmt.lhs) for stmt in fn.code if str(stmt.lhs).startswith("_")}
    sizes = {name: len(other.code) for name, other in bench.functions.items()}
    biggest = max(sizes.values())
    return {
        "ops": ops,
        "temps": len(temps),
        "most": sorted(name for name, size in sizes.items() if size == biggest),
        "sizes": sizes,
        "code": [stmt.text for stmt in fn.code],
    }


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def sequence(text: str) -> list[str]:
    """`+,-,*` as a list, forgiving about spaces and about a trailing comma."""
    return [part for part in text.replace(" ", ",").split(",") if part]


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
    parser.add_argument("--ops", help="the operators in the order they are computed, as +,-,*")
    parser.add_argument("--temps", help="how many temporaries, not counting the return slot")
    parser.add_argument("--most", help="the bench function with the most GIMPLE statements")
    args = parser.parse_args(argv)

    bench = build()
    key = answers(bench)

    print(f"{bench}\n")

    said_ops = ask(f"In what order does {SUBJECT} compute its operators? as +,-,*:", args.ops)
    said_temps = ask("How many temporaries does it need?", args.temps)
    said_most = ask("Which function on the bench has the most statements?", args.most)

    scored = [
        mark(
            "the order the operators are computed in",
            sequence(said_ops) == key["ops"],
            ",".join(key["ops"]),
            [f"GCC wrote  {line}" for line in key["code"]],
        ),
        mark(
            "how many temporaries",
            number(said_temps) == key["temps"],
            str(key["temps"]),
            ["one per operator except the last, which had the return slot to go in"],
        ),
        mark(
            "the longest function on the bench",
            said_most.strip() in key["most"],
            " or ".join(key["most"]),
            [f"{name:14} {size:>2} statements" for name, size in key["sizes"].items()],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one to sit with is the third. The longest function on the bench is the one")
        print("whose C had no arithmetic in it at all, because a branch costs more statements")
        print("than a multiply does.")
        return 0
    print("\nThe whole bench is one loop away if you want to look at it again:")
    print("    for name, fn in bench.functions.items(): print(name, len(fn.code))")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
