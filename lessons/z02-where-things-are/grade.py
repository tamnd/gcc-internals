"""The Z02 boss fight: six things a compiler printed, find where each one came from.

    python lessons/z02-where-things-are/grade.py
    python lessons/z02-where-things-are/grade.py \\
        --says gcc/cfgloop.cc:163,gcc/tree-cfg.cc:1980,...

Every item is real output from a real gcc-16 compiling a five line C file. For four of them
the answer is a file and a line in the pinned tree, written the way a citation is written:

    gcc/cfgloop.cc:163

Two of them also want a year, because a checkout cannot answer them and the history can:

    gcc/tree-cfg.cc:2193:2004

Those two are the point of the exercise. `git grep` tells you where a line is. It does not
tell you when it arrived or what else arrived with it, and the answer to that is often the
explanation you were actually looking for.

    git log -S"Removing basic block" --oneline -- gcc/tree-cfg.cc
    git log --format='%ad %an %s' --date=short -1 <the commit it names>

The vendored checkout in this repository is a shallow clone with one commit in it, so those
commands need a full clone of GCC. The two answers are recorded in the corpus so the grader
can mark you offline, and the lesson says where they came from.

Lines are marked with a little slack. If you point at the `if (dump_file)` two lines above the
`fprintf`, you found it, and arguing about which of the two lines is the answer teaches nobody
anything.
"""

from __future__ import annotations

import argparse
import sys

from gxray import layout

#: How far off a line number can be and still count as found.
SLACK = 3


def parse(given: str) -> tuple[str, int, int]:
    """One answer, as `path`, `line`, `year`, with a year of zero when none was typed."""
    bits = given.strip().split(":")
    if len(bits) not in (2, 3):
        return ("", 0, 0)
    path = bits[0].strip()
    try:
        line = int(bits[1])
        year = int(bits[2]) if len(bits) == 3 else 0
    except ValueError:
        return ("", 0, 0)
    return (path, line, year)


def marks(clue: layout.Clue, given: str) -> tuple[bool, str]:
    """Whether one answer is right, and what to say about it if it is not."""
    path, line, year = parse(given)
    if not path:
        return (False, f"that is not a file and a line. The answer is {clue.answer}.")
    if path.lstrip("./") != clue.path:
        return (False, f"wrong file. It is {clue.path}, and the route is {clue.route}.")
    if abs(line - clue.line) > SLACK:
        return (False, f"right file, wrong place. It is line {clue.line}.")
    if clue.historic:
        if not year:
            return (False, "the file and line are right. This one wants the year as well.")
        if str(year) != clue.date[:4]:
            return (False, f"the line is right and the year is not. It is {clue.date[:4]}.")
    return (True, "")


def ask(n: int, clue: layout.Clue, given: str | None) -> str:
    if given is not None:
        return given.strip()
    name, _, _ = layout.route(clue.route)
    shape = "path:line:year" if clue.historic else "path:line"
    print(f"\n{n}. {clue.dump}")
    print(f"   route: {name}")
    print(f"   answer as {shape}")
    if not sys.stdin.isatty():
        return ""
    return input("   where is it? ").strip()


def said(answer: str) -> list[str]:
    """The answers the reader typed, split on commas or whitespace."""
    return [word.strip() for word in answer.replace(",", " ").split() if word.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--says", help="six answers, comma separated, in the order asked")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    tree = layout.load()
    typed = said(args.says) if args.says else []

    print(f"{tree.tag}, {tree.files} source files, {tree.lines} lines.")
    print(f"{len(tree.hunt)} things a compiler printed. Find where each one came from.")
    print(f"{sum(clue.historic for clue in tree.hunt)} of them want the year too.")

    answers = []
    for n, clue in enumerate(tree.hunt, start=1):
        answers.append(ask(n, clue, typed[n - 1] if n <= len(typed) else None))

    print()
    scored = 0
    for clue, given in zip(tree.hunt, answers, strict=True):
        right, why = marks(clue, given)
        scored += right
        print(f"{'right' if right else 'wrong'}  {clue.dump}")
        print(f"       {clue.answer}   {clue.text}")
        if clue.historic:
            print(f"       {clue.commit}  {clue.date}  {clue.author}  {clue.subject}")
        if not right:
            print(f"       {why}")
            print(f"       {clue.about}")

    print(f"\n{scored} of {len(tree.hunt)}.")
    if scored == len(tree.hunt):
        print("That is the skill. Not knowing where things are, but knowing how to find out")
        print("in under a minute, which is what everybody who works on GCC actually does.")
        print("T01 next, and the compiler proper.")
        return 0
    print("\nThe routes are in the lesson, and you can read the table:")
    print("    from gxray import layout")
    print("    tree = layout.load()")
    print("    print(tree.find('ccp2'))")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
