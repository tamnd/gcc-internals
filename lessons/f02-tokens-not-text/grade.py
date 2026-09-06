"""The F02 boss fight, graded.

Three questions about the recorded preprocessor output. Work them out on paper first, then
run this. It says which ones you got right and shows the evidence for each, so a wrong answer
is something to go and look at rather than a mark.

    python lessons/f02-tokens-not-text/grade.py
    python lessons/f02-tokens-not-text/grade.py --spaces 29 --twice a,b --odd NAME

Nothing here is hardcoded. Every answer is worked out from `corpora/cpp/f02.json`, so
re-recording against a newer compiler cannot leave the grader marking against a stale answer
key. That has to be true or the grader is worse than no grader.
"""

from __future__ import annotations

import argparse
import sys

from gxray import cpp


def questions() -> dict:
    """The three answers, read off the recording rather than written down."""
    rec = cpp.load("f02")
    table = rec.macros("local")
    missing = rec.builtin.missing_from(table)
    #: The built-in that a dump of every macro does print. Worked out by subtraction rather
    #: than named, because the interesting thing is that there is exactly one.
    printed = [name for name in rec.builtin.array if name not in missing]
    return {
        "rec": rec,
        "spaces": len(rec.spaced),
        "unspaced": rec.unspaced,
        "twice": [one.rsplit("/", 1)[-1] for one in rec.headers("guards").opened_twice],
        "missing": missing,
        "printed": printed,
        "odd": printed[0] if len(printed) == 1 else "",
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
    return sorted(part.strip() for part in text.replace(",", " ").split() if part.strip())


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spaces", help="how many of the probed pairs got a space between them")
    parser.add_argument("--twice", help="which of the four headers were opened twice")
    parser.add_argument("--odd", help="the built-in macro that -dM does print")
    args = parser.parse_args(argv)

    key = questions()
    rec = key["rec"]
    probed = len(rec.probes)

    print(f"    {len(rec.macros('local'))} macros before a line of your program is read")
    print(f"    {probed} pairs of tokens put next to each other with nothing between them")
    print(f"    {len(rec.builtin.array)} macros libcpp defines with a C function behind them")

    said_spaces = ask(f"\nOf the {probed} pairs, how many came out with a space in?", args.spaces)
    said_twice = ask("Which of the four headers were opened twice?", args.twice)
    said_odd = ask("Which built-in macro does -dM print?", args.odd)

    scored = [
        mark(
            "how many pairs were separated",
            said_spaces.strip() == str(key["spaces"]),
            str(key["spaces"]),
            [
                f"{key['spaces']} of {probed} got a space, and {len(key['unspaced'])} did not",
                "  ".join(f"{one.glued}" for one in key["unspaced"][:6]) + " came out unchanged",
                "so it is not a habit of the printer. It fires on the pairs that would lex"
                " as one token and on no others",
            ],
        ),
        mark(
            "which headers were read twice",
            words(said_twice) == sorted(key["twice"]),
            ", ".join(sorted(key["twice"])),
            [
                "bare.h has no guard at all, which is the easy half",
                "stray.h has a guard, and one declaration after the #endif",
                "untidy.h has a guard and a comment after the #endif, and is read once",
                "the optimization needs the guard to be the whole file, in tokens",
            ],
        ),
        mark(
            "the built-in that gets printed",
            said_odd.strip() == key["odd"],
            key["odd"],
            [
                f"{len(key['missing'])} of the {len(rec.builtin.array)} are missing from -dM",
                f"the one that is not is {key['odd']}",
                "because it is the only one of them cpp_init_builtins also defines the"
                " ordinary way, with a value it can write into the hash table",
                "the others are C functions, and there is nothing to print",
            ],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one worth sitting with is the first. A space appeared in the output that is")
        print("in no input file, and it appeared because of what the two things beside it are.")
        print("Text does not have that property. Tokens do.")
        return 0
    print("\nThe whole recording is two lines away if you want to look at it:")
    print("    from gxray import cpp")
    print('    print(cpp.load("f02").headers("guards").text)')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
