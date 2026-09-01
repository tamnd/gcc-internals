"""The refcheck command line.

    refcheck check     resolve every citation and compare it with the lockfile
    refcheck update    rebuild the lockfile from the prose
    refcheck list      every citation and where it is written
    refcheck show gcc/passes.cc:855@releases/gcc-16.2.0

Run with no paths, it reads the places prose lives.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.refcheck import (
    GCC_ROOT,
    PINNED_TAG,
    RefError,
    check,
    find_citations,
    pinned_commit,
    resolve,
    scan,
    update,
)

DEFAULT_PATHS = ["lessons", "blueprints", "docs", "gxray", "tools", "README.md", "CONTRIBUTING.md"]


def existing(names: list[str]) -> list[Path]:
    return [Path(n) for n in names if Path(n).exists()]


def require_tree() -> int | None:
    if pinned_commit() is None:
        print(
            f"the pinned GCC tree is not checked out, so nothing can be verified.\n"
            f"  expected it at {GCC_ROOT}\n"
            f"  run: git submodule update --init --depth 1",
            file=sys.stderr,
        )
        return 2
    return None


def cmd_check(args) -> int:
    if (bad := require_tree()) is not None:
        return bad
    paths = existing(args.paths or DEFAULT_PATHS)
    problems = check(paths)
    if problems:
        for p in problems:
            print(f"refcheck: {p}", file=sys.stderr)
        print(f"\n{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(f"refcheck: every citation resolves against {PINNED_TAG}")
    return 0


def cmd_update(args) -> int:
    if (bad := require_tree()) is not None:
        return bad
    paths = existing(args.paths or DEFAULT_PATHS)
    try:
        entries = update(paths)
    except RefError as exc:
        print(f"refcheck: {exc}", file=sys.stderr)
        return 1
    print(f"refcheck: recorded {len(entries)} citation(s)")
    return 0


def cmd_show(args) -> int:
    if (bad := require_tree()) is not None:
        return bad
    found = find_citations(args.citation)
    if not found:
        print(f"{args.citation!r} does not look like a citation", file=sys.stderr)
        return 2
    try:
        r = resolve(found[0])
    except RefError as exc:
        print(f"refcheck: {exc}", file=sys.stderr)
        return 1
    first = max(1, r.citation.line - (len(r.window) - 1) // 2)
    for offset, line in enumerate(r.window):
        n = first + offset
        print(f"{'>' if n == r.citation.line else ' '} {n:>6}  {line}")
    print(f"\nhash {r.digest}")
    return 0


def cmd_list(args) -> int:
    for c in scan(existing(args.paths or DEFAULT_PATHS)):
        print(f"{c.where}: {c.key}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="refcheck", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    for name, fn, helptext in [
        ("check", cmd_check, "verify every citation against the pinned tree"),
        ("update", cmd_update, "rebuild the lockfile"),
        ("list", cmd_list, "print every citation and where it is written"),
    ]:
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("paths", nargs="*")
        sp.set_defaults(fn=fn)

    sp = sub.add_parser("show", help="print the lines a citation points at")
    sp.add_argument("citation")
    sp.set_defaults(fn=cmd_show)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
