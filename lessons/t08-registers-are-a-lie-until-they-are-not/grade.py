"""The T08 boss fight, graded.

Five functions, x86-64, `-O2`. Predict which of them put at least one value in memory, then
two questions that need the numbers rather than a guess.

    python lessons/t08-registers-are-a-lie-until-they-are-not/grade.py
    python lessons/t08-registers-are-a-lie-until-they-are-not/grade.py \\
        --spills p14,p20,p30 --available 15 --p20-memory 7

Everything the grader marks against is read out of the recorded IRA dump, out of the
`Disposition:` block, which is the allocator's own record of where each value went. There is
no written down answer key here, so re-recording the corpus against a newer compiler cannot
leave the grader marking against something that stopped being true.
"""

from __future__ import annotations

import argparse
import sys

from gxray import corpus_store, regalloc

#: The recording the questions are about, and the one the lesson argues from.
ENTRY = "t08-x86-64"

#: The other target, used only in the closing note. Same source, same flags, twice the
#: registers, and three of the five answers come out differently.
OTHER = "t08-aarch64"

#: The function the second and third questions are about. Twenty lines, no calls, and it is
#: the middle of the ramp: comfortably over on x86-64 and comfortably under on aarch64.
SUBJECT = "p20"


def allocation(entry: str = ENTRY):
    """Every function in one recording, keyed by name."""
    text = corpus_store.load(entry).dump_texts["rtl-ira"]
    return regalloc.parse(text, entry).functions


def spillers(functions) -> list[str]:
    """The functions that put at least one value in memory, in dump order."""
    return [name for name, alloc in functions.items() if not alloc.fits]


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def named(said: str, known: list[str]) -> list[str]:
    """The function names the reader listed, in the order the dump has them.

    Order is imposed rather than taken from the answer, because `p20,p14` and `p14,p20` are
    the same prediction and marking them differently would be marking punctuation.
    """
    words = {w.strip() for w in said.replace(",", " ").split()}
    return [n for n in known if n in words]


def number(said: str) -> int | None:
    """The first whole number in whatever the reader typed, or None if there was not one."""
    for word in said.replace(",", " ").split():
        if word.lstrip("-").isdigit():
            return int(word)
    return None


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spills", help="which functions put a value in memory, comma separated")
    parser.add_argument("--available", help="how many general registers x86-64 hands out")
    parser.add_argument("--p20-memory", dest="memory", help="how many values p20 puts in memory")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    functions = allocation()
    names = list(functions)
    subject = functions[SUBJECT]

    print(f"{len(names)} functions on x86-64 at -O2: {', '.join(names)}")
    print("register pressure, which is how many values are alive at the busiest point:")
    for name, alloc in functions.items():
        print(f"  {name}  {alloc.peak()}")
    print()

    said_spills = ask("Which of them put a value in memory?", args.spills)
    said_available = ask(
        "How many general registers does x86-64 hand the allocator?", args.available
    )
    said_memory = ask(f"How many values does {SUBJECT} put in memory?", args.memory)

    spilling = spillers(functions)
    available = subject.available()
    memory = len(subject.spilled)

    scored = [
        mark(
            "which functions put a value in memory",
            named(said_spills, names) == spilling,
            ", ".join(spilling),
            [
                f"{name}: pressure {functions[name].peak()}, "
                f"{len(functions[name].spilled)} in memory"
                for name in names
            ],
        ),
        mark(
            "how many general registers x86-64 hands the allocator",
            number(said_available) == available,
            str(available),
            [
                "the architecture has sixteen and the stack pointer is one of them, "
                "so the allocator gets fifteen"
            ],
        ),
        mark(
            f"how many values {SUBJECT} puts in memory",
            number(said_memory) == memory,
            str(memory),
            [
                f"pressure {subject.peak()}, {available} registers, "
                f"{subject.peak() - available} more values than places to put them"
            ],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        other = allocation(OTHER)
        fine = [n for n in spilling if other[n].fits]
        differ = [n for n in names if len(other[n].spilled) != len(functions[n].spilled)]
        print(f"The same five functions on aarch64, which hands out {other[SUBJECT].available()}")
        print(
            f"registers rather than {available}, keep everything in registers for "
            f"{', '.join(fine)}."
        )
        print("Nothing about the source changed. The only difference is how many places the")
        print(f"machine has to put a value, and it decides {len(differ)} of these {len(names)}")
        print(f"answers: {', '.join(differ)}.")
        return 0
    print("\nEvery number here is in one block at the end of the dump, which you can read:")
    print("    from gxray import corpus_store, regalloc")
    print("    d = regalloc.parse(corpus_store.load('t08-x86-64').dump_texts['rtl-ira'])")
    print("    d['p20'].spilled")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
