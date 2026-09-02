"""The Z01 boss fight, graded.

Twelve lines of real GCC, one at a time, and for each one the question is the same: what is
the construct on this line? Answer with the short key from the table in the lesson, so `cast`
or `loop` or `gty`.

    python lessons/z01-cpp-for-reading/grade.py
    python lessons/z01-cpp-for-reading/grade.py \\
        --says cast,loop,gsi,gty,treemacro,gimple,vec,poly,wide,include,pass,dump

There is no answer key in this repository. The grader loads the same eighteen snippets the
lesson reads, runs `source.annotate` over them, and takes the lines where exactly one
construct was recognized. So the marking is a function of GCC's source: re-cut the snippets
against a newer compiler and the questions and the answers both move with it, and a construct
GCC stops writing stops being asked about.

The one thing that is a choice rather than a derivation is which twelve. The rule is the first
twelve keys in `source.KEYS` that have a line carrying nothing else, which leaves out `hash`
and `assert` because every line of theirs in the extract has a second construct on it as well.
The questions are then sorted by file and line, so the order you see them in is not the order
of the table you learned them from.
"""

from __future__ import annotations

import argparse
import sys

from gxray import source

#: The extract the lesson reads. The same file, so a question cannot be about a line the
#: reader was never shown.
EXTRACT = "z01"

#: How many lines to ask about.
HOW_MANY = 12


def unambiguous(cuts: source.Extract) -> dict[str, tuple[str, int, str]]:
    """The first line in the extract that carries each construct and nothing else.

    A line with two constructs on it is a bad question, because "what is on this line" has
    two right answers and only one of them gets typed. Those lines are still in the lesson,
    they are just not in the exam.
    """
    found: dict[str, tuple[str, int, str]] = {}
    for snippet in cuts:
        for line, keys in sorted(source.annotate(snippet).items()):
            if len(keys) == 1 and keys[0] not in found:
                found[keys[0]] = (snippet.path, line, snippet.at(line).expandtabs(8).rstrip())
    return found


def questions(cuts: source.Extract) -> list[tuple[str, int, str, str]]:
    """The twelve, as `(path, line, text, key)`, in the order they are asked."""
    found = unambiguous(cuts)
    chosen = [key for key in source.KEYS if key in found][:HOW_MANY]
    rows = [(*found[key], key) for key in chosen]
    return sorted(rows, key=lambda row: (row[0], row[1]))


def skipped(cuts: source.Extract) -> list[str]:
    """The constructs no question covers, so the report can say so rather than hide it."""
    asked = {key for *_, key in questions(cuts)}
    return [key for key in source.KEYS if key not in asked]


def ask(path: str, line: int, text: str, given: str | None) -> str:
    if given is not None:
        return given.strip().lower()
    print(f"\n{path}:{line}")
    print(f"    {text.strip()}")
    if not sys.stdin.isatty():
        return ""
    return input("which construct? ").strip().lower()


def said(answer: str) -> list[str]:
    """The keys the reader typed, split on commas or spaces and lowercased."""
    return [w.strip().lower() for w in answer.replace(",", " ").split() if w.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--says", help=f"{HOW_MANY} keys, comma separated, in the order asked")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    cuts = source.load_extract(EXTRACT)
    rows = questions(cuts)
    typed = said(args.says) if args.says else []

    print(f"{EXTRACT}: {len(cuts)} snippets, {cuts.lines()} lines, cut from {cuts.tag}")
    print(f"{len(rows)} lines. Name the construct on each one, by its key from the table.")
    print(f"The keys are: {', '.join(source.KEYS)}")

    answers = []
    for n, (path, line, text, _) in enumerate(rows):
        answers.append(ask(path, line, text, typed[n] if n < len(typed) else None))

    print()
    scored = 0
    for (path, line, text, key), got in zip(rows, answers, strict=True):
        right = got == key
        scored += right
        print(f"{'right' if right else 'wrong'}  {path}:{line}")
        print(f"       {text.strip()}")
        if not right:
            print(f"       that is {key}, {source.named(key)}. {source.explain(key)}")

    left = skipped(cuts)
    print(f"\n{scored} of {len(rows)}.")
    print(f"Not asked about: {', '.join(left)}.")
    if scored == len(rows):
        print("You can read GCC now. Slowly, and with the manual open, which is how")
        print("everybody reads it. The next thing in the way is not the language, it is")
        print("knowing which of four and a half million lines to open, and that is Z02.")
        return 0
    print("\nEverything here is in the extract, and you can see the marking:")
    print("    from gxray import source")
    print("    cuts = source.load_extract('z01')")
    print("    source.annotate(cuts['ccp-read'])")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
