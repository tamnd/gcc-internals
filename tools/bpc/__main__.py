"""The bpc command line.

    bpc build       regenerate every generated section from the pinned tree
    bpc check       fail if any generated section is stale or a blueprint is malformed
    bpc coverage    the coverage ledger, and fail on anything unclassified
    bpc status      the per blueprint status table
    bpc pages       write the blueprint pages of the site, or --check that they are current
    bpc show ID     print what a single generator would emit, without writing anything

`build`, `check`, `coverage` and `show` need the pinned GCC tree in `vendor/gcc`. `status` and
`pages` read the blueprints and nothing else, which is why the site job can run `pages`.
"""

from __future__ import annotations

import argparse
import sys

from tools.bpc import (
    GCC_ROOT,
    GENERATORS,
    REPO_ROOT,
    BpcError,
    _register_generators,
    build,
    check,
    load,
    pages,
    render,
)
from tools.bpc import coverage as ledger


def require_tree() -> int | None:
    if not (GCC_ROOT / "gimple.def").is_file():
        print(
            f"the pinned GCC tree is not checked out, so nothing can be generated.\n"
            f"  expected it at {GCC_ROOT}\n"
            f"  run: git submodule update --init --depth 1",
            file=sys.stderr,
        )
        return 2
    return None


def cmd_build(args) -> int:
    if (bad := require_tree()) is not None:
        return bad
    changed = build()
    for path in changed:
        print(f"bpc: rewrote {path}")
    if not changed:
        print("bpc: every generated section was already up to date")
    return 0


def cmd_check(args) -> int:
    if (bad := require_tree()) is not None:
        return bad
    problems = check() + ledger.problems()
    for p in problems:
        print(f"bpc: {p}", file=sys.stderr)
    if problems:
        print(f"\n{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(f"bpc: {len(load())} blueprint(s) are well formed and every generated section is current")
    return 0


def cmd_coverage(args) -> int:
    if (bad := require_tree()) is not None:
        return bad
    reports = ledger.report()
    for r in reports:
        print(r.line())
        for item in r.unclassified:
            print(f"  unclassified: {item}")
    unclassified = sum(len(r.unclassified) for r in reports)
    if unclassified:
        print(f"\n{unclassified} item(s) the ledger says nothing about", file=sys.stderr)
        return 1
    return 0


def cmd_status(args) -> int:
    rows = [
        (bp.id, bp.header("Status"), bp.header("Generated sections"), bp.header("Last verified"))
        for bp in load()
    ]
    if not rows:
        print("bpc: no blueprints yet")
        return 0
    width = max(len(r[0]) for r in rows)
    for name, status, generated, verified in rows:
        print(f"{name:<{width}}  {status:<9}  generated {generated:<8}  verified {verified}")
    return 0


def cmd_pages(args) -> int:
    """The site pages for the blueprints. Needs the blueprints and not the GCC tree.

    Kept out of `check` for that reason. `check` reads the pinned tree and cannot run in the
    site job, and a page that is stale should fail in the job that builds the site.
    """
    if args.check:
        problems = pages.check()
        for p in problems:
            print(f"bpc: {p}", file=sys.stderr)
        if problems:
            return 1
        print(f"bpc: the blueprint pages and the site navigation match {len(load())} blueprints")
        return 0
    changed = pages.build()
    for path in changed:
        print(f"bpc: wrote {path.relative_to(REPO_ROOT)}")
    if not changed:
        print("bpc: every blueprint page was already up to date")
    return 0


def cmd_show(args) -> int:
    if (bad := require_tree()) is not None:
        return bad
    print(render(args.id, GCC_ROOT))
    return 0


COMMANDS = {
    "build": cmd_build,
    "check": cmd_check,
    "coverage": cmd_coverage,
    "status": cmd_status,
    "pages": cmd_pages,
    "show": cmd_show,
}


def main(argv: list[str] | None = None) -> int:
    _register_generators()
    p = argparse.ArgumentParser(prog="bpc", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        sp = sub.add_parser(name)
        if name == "show":
            sp.add_argument("id", choices=sorted(GENERATORS))
        if name == "pages":
            sp.add_argument("--check", action="store_true", help="fail instead of writing")
    args = p.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except BpcError as exc:
        print(f"bpc: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
