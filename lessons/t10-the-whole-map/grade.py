"""The T10 boss fight, graded.

One expression, `dx * dx + dy * dy` on line 10 of `l2.c`, followed from the source to the
instruction. Four questions: every tree pass that changed the statements computing it, in
order, then the RTL pass that fused the multiply and the add, the machine description pattern
that printed the result, and how many of the enabled passes changed the function at all.

    python lessons/t10-the-whole-map/grade.py
    python lessons/t10-the-whole-map/grade.py \\
        --trace einline,release_ssa,sink1,ifcvt,vect \\
        --fused combine --pattern maddsi --changed 36

Nothing here is written down. The grader loads the recording, finds the statements that
multiply a name by itself, walks the tree dumps looking for the points where that set changes,
counts fused insns across the RTL dumps, and reads the pattern off the annotated assembly.
Re-record against a newer compiler and it marks against whatever that compiler did.

Question one is the one to think about. Two of the passes on the answer are not what anyone
means by touching an expression, and they are on the list because the dumps say so.
"""

from __future__ import annotations

import argparse
import re
import sys

from gxray import asm, corpus_store, gimple, passes, rtl, tape

#: The recording the questions are about. L2 at -O2 with the tree dumps, five RTL dumps and
#: the assembly printed with -dp.
ENTRY = "t10-whole"

#: The function we follow. `dist2` is static and gone by the second dump, so everything
#: interesting happens inside this one.
FUNCTION = "nearest"

#: A statement that multiplies a name by itself, which is how `dx * dx` looks in GIMPLE once
#: the front end has given it a temporary. The back reference is what makes it a square.
SQUARE = re.compile(r"= (\S+) \* \1;")

#: The five RTL dumps that name a stage, in pipeline order. The fusing shows up as the first
#: one of these where a `mult` sits inside a `plus`.
RTL_DUMPS = ("rtl-expand", "rtl-combine", "rtl-ira", "rtl-reload", "rtl-final")


def tree_dumps(record) -> dict[str, gimple.Function]:
    """Every tree dump in the recording that holds a body for our function."""
    found = {}
    for key, text in record.dump_texts.items():
        if not key.startswith("tree-") or key.endswith("-graph"):
            continue
        body = gimple.parse(text).functions.get(FUNCTION)
        if body is not None:
            found[key] = body
    return found


def squares(f: gimple.Function) -> tuple[str, ...]:
    """Every statement in this function that multiplies a name by itself."""
    return tuple(
        s.text.strip()
        for b in f.ordered_blocks
        for s in b.stmts
        if not s.is_debug and SQUARE.search(s.text)
    )


def trace(order: list[str], dumps: dict[str, gimple.Function]) -> list[str]:
    """The dumps where the set of squares is different from the dump before it.

    The first dump is where we came in, so it is a baseline rather than an event. Everything
    after it is a pass that added, removed, renamed or moved one of the statements.
    """
    events, seen = [], None
    for name in order:
        now = squares(dumps[name])
        if seen is not None and now != seen:
            events.append(name.removeprefix("tree-"))
        seen = now
    return events


def fused(record) -> list[tuple[str, int]]:
    """How many insns have a multiply inside an add, at each of the five RTL stages."""
    counts = []
    for key in RTL_DUMPS:
        f = rtl.parse(record.dump_texts[key], key).only()
        pattern = [str(i.pattern) for i in f.code]
        counts.append((key, len([p for p in pattern if "mult" in p and "plus" in p])))
    return counts


def ask(question: str, given: str | None) -> str:
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def names(said: str) -> list[str]:
    """The pass names the reader typed, in order, with the `tree-` prefix forgiven.

    Someone reading the dumps sees `tree-einline` and someone reading the pass list sees
    `einline`. Both are the same pass and this question is not about which file you read.
    """
    words = [w.strip().removeprefix("tree-") for w in said.replace(",", " ").split()]
    return [w for w in words if w]


def number(said: str) -> int | None:
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
    parser.add_argument("--trace", help="the tree passes that changed the squares, in order")
    parser.add_argument("--fused", help="the RTL pass that fused the multiply and the add")
    parser.add_argument("--pattern", help="the machine description pattern that printed it")
    parser.add_argument("--changed", help="how many enabled passes changed the function")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    record = corpus_store.load(ENTRY)
    pipeline = passes.parse(record.pass_texts["-O2"])
    dumps = tree_dumps(record)
    order = [p.name for p in pipeline.enabled if p.name in dumps]
    listing = asm.parse(record.asm_texts["-O2 -dp"], ENTRY)

    print(f"{ENTRY}: {record.compiler} for {record.target}")
    print(f"{FUNCTION}, and one expression in it:")
    print()
    print("    l2.c:10   return dx * dx + dy * dy;")
    print()
    print(f"{len(pipeline.enabled)} passes are enabled, {len(dumps)} of them wrote a tree dump")
    print(f"we can read, and the file has {len(listing.insns)} instructions in it.")
    print()

    said_trace = ask("Which tree passes changed the squares, in order?", args.trace)
    said_fused = ask("Which RTL pass fused the multiply and the add?", args.fused)
    said_pattern = ask("Which pattern printed the fused instruction?", args.pattern)
    said_changed = ask("How many enabled passes changed the function at all?", args.changed)

    events = trace(order, dumps)
    counts = fused(record)
    first = next((key for key, n in counts if n), "nothing")
    pattern = next(
        (line.pattern for line in listing.insns if line.name.startswith("madd")),
        "",
    )
    changed = len([c for c in tape.cells(pipeline, dumps) if c.changed])

    scored = [
        mark(
            "which tree passes changed the squares",
            names(said_trace) == events,
            ", ".join(events),
            [f"{name:<14}{len(squares(dumps['tree-' + name]))} square(s)" for name in events],
        ),
        mark(
            "which RTL pass fused the multiply and the add",
            said_fused.strip().removeprefix("rtl-").lower() == first.removeprefix("rtl-"),
            first.removeprefix("rtl-"),
            [f"{key:<14}{n} fused" for key, n in counts],
        ),
        mark(
            "which pattern printed the fused instruction",
            said_pattern.strip() == pattern,
            pattern,
            [
                f"{' '.join(line.text.split(';')[0].split()):<24}{line.pattern}"
                for line in listing.insns
                if line.pattern in {pattern, "mulsi3"}
            ],
        ),
        mark(
            "how many enabled passes changed the function",
            number(said_changed) == changed,
            str(changed),
            [
                f"{changed} of {len(pipeline.enabled)} enabled passes",
                "the rest either ran and found nothing or wrote no dump to compare",
            ],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 4.")
    if got == 4:
        print("Two of the passes on the first answer are worth arguing about.")
        print("release_ssa changed all four statements and changed nothing about the")
        print("program: it recycles SSA version numbers, so the survivors get renumbered.")
        print("ifcvt made two more copies and vect deleted them again, because the")
        print("vectorizer needs a branch free version of the loop to measure before it can")
        print("decide it is not worth vectorizing. Neither is an optimization of this")
        print("expression, and both are on the list because the dumps say the statements")
        print("are different afterwards. That is what the evidence supports and it is all")
        print("it supports.")
        return 0
    print("\nEverything here is in the recording:")
    print("    from gxray import corpus_store, gimple")
    print("    r = corpus_store.load('t10-whole')")
    print("    gimple.parse(r.dump_texts['tree-einline']).functions['nearest']")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
