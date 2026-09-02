"""`python -m tools.dumpparse`, the command the `dumpparse` job runs.

    python -m tools.dumpparse check     the corpus against the recorded baseline
    python -m tools.dumpparse report     what the parsers made of every dump
    python -m tools.dumpparse worst      the dumps with the most input walked past
    python -m tools.dumpparse record     write the baseline again

`record` is the only one that writes. Run it when you have changed a parser or re-recorded a
corpus entry, look at the diff, and put it in the pull request with the change that caused
it.
"""

from __future__ import annotations

import argparse
import sys

from tools.dumpparse import (
    BASELINE,
    ROOT,
    DumpParseError,
    compare,
    load,
    readings,
    save,
    totals,
)

TICK = "ok"
CROSS = "no"


def _totals_line(found) -> str:
    t = totals(found)
    return (
        f"{t['dumps']} dumps, {t['functions']} functions, {t['items']} statements and insns, "
        f"{t['missed']} unreadable, {t['unread']} pieces of prose walked past"
    )


def cmd_report(args) -> int:
    found = readings()
    width = max(len(r.id) for r in found)
    for r in found:
        if args.all or r.missed or r.unread:
            print(
                f"  {r.id:{width}}  {r.parser:6}  {r.functions:3} fn  {r.items:5} items  "
                f"{r.missed:4} unreadable  {r.unread:5} prose"
            )
    print()
    print(_totals_line(found))
    return 0


def cmd_worst(args) -> int:
    found = sorted(readings(), key=lambda r: (-r.missed, -r.unread))[: args.count]
    width = max(len(r.id) for r in found)
    print("The dumps this book understands least, worst first")
    for r in found:
        print(f"  {r.id:{width}}  {r.missed:4} unreadable  {r.unread:5} prose")
    return 0


def cmd_record(args) -> int:
    found = readings()
    path = save(found)
    print(f"wrote {path.relative_to(ROOT)}")
    print(_totals_line(found))
    print("Look at the diff before you commit it.")
    return 0


def cmd_check(args) -> int:
    print("dumpparse, every dump in the corpus against the recorded baseline")
    found = readings()
    try:
        problems = compare(found, load())
    except DumpParseError as exc:
        print(f"  {CROSS}  {exc}", file=sys.stderr)
        return 2
    for line in problems:
        print(f"  {CROSS}  {line}")
    if problems:
        print(f"\n{len(problems)} differences from {BASELINE.relative_to(ROOT)}")
        print("If every one of them is wanted, run `just dumpparse-record` and commit it.")
        return 1
    print(f"  {TICK}  {_totals_line(found)}")
    if not totals(found)["missed"]:
        print(f"  {TICK}  every statement and every insn in the corpus reads")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.dumpparse", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, help_text in (
        ("check", cmd_check, "the corpus against the recorded baseline"),
        ("report", cmd_report, "what the parsers made of every dump"),
        ("worst", cmd_worst, "the dumps with the most input walked past"),
        ("record", cmd_record, "write the baseline again"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=fn)
        if name == "report":
            p.add_argument("--all", action="store_true", help="including the clean ones")
        if name == "worst":
            p.add_argument("--count", type=int, default=15, help="how many to show")
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
