"""The F01 boss fight, graded.

Three questions about the recorded spec tables and the four specs files. Work them out on
paper first, then run this. It says which ones you got right and shows the evidence for each,
so a wrong answer is something to go and look at rather than a mark.

    python lessons/f01-the-spec-language/grade.py
    python lessons/f01-the-spec-language/grade.py --calls one,two --changed a,b,c --odd name

Nothing here is hardcoded. Every answer is worked out from `corpora/specs/f01.json`, so
re-recording against a newer compiler cannot leave the grader marking against a stale answer
key. That has to be true or the grader is worse than no grader.
"""

from __future__ import annotations

import argparse
import sys

from gxray import specs

#: The spec the first question asks about. One of the four the compiler table starts at for a
#: C file, and the one whose call list is short enough to hold in your head.
SUBJECT = "cpp_options"


def questions() -> dict:
    """The three answers, read off the recording rather than written down."""
    rec = specs.load("f01")
    table = rec.table("local")
    moved = rec.overrides.items()
    changed = [name for name, one in moved if one.programs()[0] != one.programs()[1]]
    added = rec.builtin.added_by(table)
    #: The name in the dump that no target added, worked out rather than named. Two targets
    #: that share nothing else add it, which is the evidence that neither of them did: it is
    #: printed from a variable of its own by the `-dumpspecs` case itself.
    elsewhere = rec.builtin.added_by(rec.table("elsewhere"))
    both = [name for name in added if name in elsewhere]
    return {
        "calls": table[SUBJECT].calls,
        "callers": table.callers(SUBJECT),
        "changed": sorted(changed),
        "added": added,
        "both": both,
        "elsewhere": elsewhere,
        "odd": both[0] if len(both) == 1 else "",
        "rec": rec,
        "table": table,
    }


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def words(text: str) -> list[str]:
    """`a, b c` as three names, in any order and with any punctuation between them."""
    parts = [part.strip() for part in text.replace(",", " ").split() if part.strip()]
    return sorted(parts)


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calls", help=f"which specs {SUBJECT} calls, as a comma separated list")
    parser.add_argument("--changed", help="which specs files changed which programs ran")
    parser.add_argument("--odd", help="the name in the dump that no target added")
    args = parser.parse_args(argv)

    key = questions()
    table = key["table"]

    print(f"    {len(table)} blocks recorded from {table.target}")
    print(f"    four specs files: {', '.join(sorted(key['rec'].overrides))}")

    said_calls = ask(f"\nWhich specs does {SUBJECT} call?", args.calls)
    said_changed = ask("Which specs files changed which programs ran?", args.changed)
    said_odd = ask("Which added name was added by no target?", args.odd)

    scored = [
        mark(
            f"what {SUBJECT} calls",
            words(said_calls) == sorted(key["calls"]),
            ", ".join(key["calls"]),
            [
                f"{SUBJECT} calls {', '.join(key['calls'])}",
                f"and is called by {', '.join(key['callers']) or 'nothing in the spec list'}",
                "which is the point: the compiler table starts at it, not another spec",
            ],
        ),
        mark(
            "which specs files moved the chain",
            words(said_changed) == key["changed"],
            ", ".join(key["changed"]),
            [
                f"{name:<11}{', '.join(one.programs()[0]) or 'nothing'}"
                f"  ->  {', '.join(one.programs()[1]) or 'nothing'}"
                for name, one in sorted(key["rec"].overrides.items())
            ],
        ),
        mark(
            "the name no target added",
            said_odd.strip().lstrip("*") == key["odd"],
            key["odd"],
            [
                f"aarch64 adds: {', '.join(key['added'])}",
                f"x86-64 adds: {', '.join(key['elsewhere'])}",
                f"the only name in both lists is {key['odd']}, so neither target added it",
                "it is printed from a variable of its own by the -dumpspecs case",
            ],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one worth sitting with is the second. Three text files, no compiler, no")
        print("rebuild, and the driver ran different programs. That is what it means for the")
        print("decision to be data rather than code.")
        return 0
    print("\nThe whole recording is two lines away if you want to look at it:")
    print("    from gxray import specs")
    print('    print(specs.load("f01").table("local").text)')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
