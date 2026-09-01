"""The T01 boss fight, graded.

Three questions about what the driver would run for four different command lines. Work them
out on paper first, then run this. It says which ones you got right and shows the evidence
for each, so a wrong answer is something you can go and look at rather than a mark.

    python lessons/t01-what-gcc-runs/grade.py
    python lessons/t01-what-gcc-runs/grade.py --steps 1,1,2,3 --shared cc1 --to-as no

Nothing here is hardcoded. Every answer is worked out from the recorded `-###` output, so
re-recording the corpus against a newer compiler cannot leave the grader marking against a
stale answer key. That has to be true or the grader is worse than no grader.
"""

from __future__ import annotations

import argparse
import sys

import gxray

ENTRY = "t01-driver"

#: The four command lines, in the order the lesson lists them.
INVOCATIONS = ["-O2 -E", "-O2 -S", "-O2 -c", "-O2"]


def chains() -> list:
    """The four recorded chains, parsed."""
    backend = gxray.corpus(ENTRY)
    return [backend.chain("", *flags.split()) for flags in INVOCATIONS]


def answers(found: list) -> dict:
    """The three answers, read off the chains rather than written down."""
    every = [set(chain.names) for chain in found]
    shared = sorted(set.intersection(*every)) if every else []
    to_as = [
        arg
        for chain in found
        for step in chain
        if step.name in ("as", "gas")
        for arg in step.argv
        if arg.startswith("-O")
    ]
    return {
        "steps": [len(chain) for chain in found],
        "shared": shared,
        "to_as": to_as,
        "chains": found,
    }


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def numbers(text: str) -> list[int]:
    """`1,1,2,3` as four integers, and anything else as nothing.

    Deliberately forgiving about spaces and deliberately unforgiving about everything else.
    A submission that cannot be read is a wrong answer rather than a crash.
    """
    parts = [part.strip() for part in text.replace(" ", ",").split(",") if part.strip()]
    return [int(part) for part in parts] if all(part.isdigit() for part in parts) else []


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--steps", help="how many programs each of the four runs, as 1,1,2,3")
    parser.add_argument("--shared", help="which program runs in all four")
    parser.add_argument("--to-as", help="does any optimization flag reach the assembler, yes or no")
    args = parser.parse_args(argv)

    key = answers(chains())

    for flags in INVOCATIONS:
        print(f"    gcc {flags} l1.c")

    said_steps = ask("\nHow many programs does each run? as 1,1,2,3:", args.steps)
    said_shared = ask("Which program runs in all four?", args.shared)
    said_to_as = ask("Does any -O flag reach the assembler? yes or no:", args.to_as)

    scored = [
        mark(
            "how many programs each one runs",
            numbers(said_steps) == key["steps"],
            ",".join(str(n) for n in key["steps"]),
            [
                f"gcc {flags:8} runs {', '.join(chain.names)}"
                for flags, chain in zip(INVOCATIONS, key["chains"], strict=True)
            ],
        ),
        mark(
            "which program runs in all four",
            said_shared.lower().strip() in key["shared"],
            " and ".join(key["shared"]) or "none of them",
            [f"in all four: {', '.join(key['shared']) or 'nothing'}"],
        ),
        mark(
            "whether an optimization flag reaches the assembler",
            said_to_as.lower().startswith("y") == bool(key["to_as"]),
            "yes" if key["to_as"] else "no",
            key["to_as"] or ["the assembler is never given a flag starting with -O"],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one worth sitting with is the third. Optimization is a thing that happens")
        print("inside one program, and every other program in the chain is unaware of it.")
        return 0
    print("\nThe raw output is one line away if you want to look at the whole thing:")
    print(f'    print(gxray.corpus("{ENTRY}").chain("", "-O2", "-c").text)')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
