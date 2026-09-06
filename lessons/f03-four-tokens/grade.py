"""The F03 boss fight, graded.

Three questions about the recorded parser diagnostics. Work them out on paper first, then run
this. It says which ones you got right and shows the evidence for each, so a wrong answer is
something to go and look at rather than a mark.

    python lessons/f03-four-tokens/grade.py
    python lessons/f03-four-tokens/grade.py --odd name --unsure char,name --deep 3

Nothing here is hardcoded. Every answer is worked out from `corpora/diag/f03.json`, so
re-recording against a newer compiler cannot leave the grader marking against a stale answer
key. That has to be true or the grader is worse than no grader.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from gxray import cparse

#: The eight programs that all leave out the same semicolon. Named rather than derived,
#: because what makes them one family is the mistake they share and no property of the
#: recording says so.
SAME = ("brace", "name", "number", "string", "char", "keyword", "pragma", "eof")


def questions() -> dict:
    """The three answers, read off the recording rather than written down."""
    rec = cparse.load("f03")
    errors = {name: rec[name].errors[0] for name in SAME}
    #: The column seven of the eight agree on, found by counting rather than by naming it,
    #: so a recompile that moves every caret two to the right still grades correctly.
    columns = Counter(one.at.column for one in errors.values())
    usual, _ = columns.most_common(1)[0]
    odd = [name for name, one in errors.items() if one.at.column != usual]
    unsure = sorted(name for name, one in errors.items() if len(one.suffixes) != 1)
    look = rec.lookahead
    return {
        "rec": rec,
        "errors": errors,
        "usual": usual,
        "odd": odd[0] if len(odd) == 1 else "",
        "unsure": unsure,
        "deep": look.depths.get(look.deepest, 0),
        "look": look,
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
    parser.add_argument("--odd", help="the one program whose caret is somewhere else")
    parser.add_argument("--unsure", help="the messages that do not say which branch made them")
    parser.add_argument("--deep", help="how many calls pass a constant 4 to peek_nth_token")
    args = parser.parse_args(argv)

    key = questions()
    errors, look = key["errors"], key["look"]

    print(f"    {len(SAME)} programs, one missing semicolon each")
    print(f"    {len({one.message for one in errors.values()})} different sentences out of them")
    print(f"    {len(cparse.SUFFIXES)} phrases c_parse_error can finish a complaint with")
    print(f"    {look.slots} token slots in the parser")

    where = f"\nSeven carets are at column {key['usual']}. Which program's is not?"
    said_odd = ask(where, args.odd)
    said_unsure = ask("Which messages do not say which branch made them?", args.unsure)
    said_deep = ask("How many calls pass a constant 4 to c_parser_peek_nth_token?", args.deep)

    other = errors[key["odd"]] if key["odd"] else None
    example = next(one for name, one in errors.items() if name != key["odd"])
    scored = [
        mark(
            "the caret that went somewhere else",
            said_odd.strip() == key["odd"],
            key["odd"],
            [
                f"{example.message} has its caret at column {example.at.column}"
                f" and a fix-it inserting {example.fixes[0].insert!r}",
                f"{other.message} has its caret at column {other.at.column} and no fix-it",
                "the message names two possible tokens, so type_is_unique is false and"
                " maybe_suggest_missing_token_insertion is never called",
                "no hint means no swap, so the caret stays on the token that upset the parser"
                " rather than moving to where the repair would go",
            ],
        ),
        mark(
            "the messages that do not say",
            words(said_unsure) == key["unsure"],
            ", ".join(key["unsure"]),
            [f"{name}: {errors[name].message}" for name in key["unsure"]]
            + [
                "both end in one character inside single quotes",
                "one is a character constant and the other is a one letter identifier"
                " quoted back by %qE, and the two branches print the same thing",
                "GCC had the token and knew. A recording of the sentence does not",
            ],
        ),
        mark(
            "how deep the parser ever looks",
            said_deep.strip() == str(key["deep"]),
            str(key["deep"]),
            [
                f"{look.peeks} peeks at one token, {look.seconds} at two",
                ", ".join(f"{n} at a constant {d}" for d, n in sorted(look.depths.items())),
                f"all {key['deep']} of the deepest are in c_parser_peek_conflict_marker",
                "seven '<' characters lex as three CPP_LSHIFT and one CPP_LESS, which is four"
                " tokens, which is the whole buffer",
                "so the fourth slot exists for something that is not C, and C is parsed in three",
            ],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one worth sitting with is the first. Two programs, one mistake, and the")
        print("caret lands in two different places because of whether GCC could name the")
        print("token you left out. The message is not a description of the error. It is a")
        print("readout of how much the parser knew at the moment it gave up.")
        return 0
    print("\nThe whole recording is three lines away if you want to look at it:")
    print("    from gxray import cparse")
    print('    rec = cparse.load("f03")')
    print('    print(rec["brace"].text)')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
