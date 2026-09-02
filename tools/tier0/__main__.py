"""`python -m tools.tier0`, the command CI runs and the one you run before pushing.

    python -m tools.tier0 list         what is registered, and which lessons read it
    python -m tools.tier0 coverage     is every corpus entry and every lesson registered
    python -m tools.tier0 offline      every experiment out of the corpus, no network
    python -m tools.tier0 online       every experiment out of the cache, no network
    python -m tools.tier0 check        both, which is what CI does
    python -m tools.tier0 refresh      the one command allowed to hit the live API
    python -m tools.tier0 prune        delete cache entries nothing asks for

`refresh` is not run by CI and never will be. Run it on a laptop, look at the cache entries
it writes, and put them in the pull request.
"""

from __future__ import annotations

import argparse
import sys

from gxray import corpus_store
from tools.cecache import Cache, OfflineCache
from tools.tier0 import Tier0Error, coverage, load, offline, online, orphans, refresh

TICK = "ok"
CROSS = "no"


def _load(args):
    try:
        return load(args.registry)
    except Tier0Error as exc:
        print("the registry does not make sense:\n", file=sys.stderr)
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc


def cmd_list(args) -> int:
    found = _load(args)
    width = max(len(x.id) for x in found)
    for x in found:
        what = ", ".join(x.dumps) if x.dumps else "no dumps"
        if x.asm:
            what += " and the assembly"
        print(f"{x.id:{width}}  {x.kind:8}  {what}")
        print(f"{'':{width}}  {x.question}")
        print(f"{'':{width}}  read by {', '.join(x.lessons)}")
        print()
    kinds = {k: sum(1 for x in found if x.kind == k) for k in ("recorded", "paired", "offline")}
    print(
        f"{len(found)} experiments: {kinds['recorded']} recorded, "
        f"{kinds['paired']} paired, {kinds['offline']} offline only"
    )
    return 0


def _report(found, run, title: str) -> int:
    print(title)
    width = max(len(x.id) for x in found)
    failed = 0
    for x in found:
        problems = run(x)
        mark = CROSS if problems else TICK
        print(f"  {mark}  {x.id:{width}}  {x.kind}")
        for line in problems:
            print(f"      {line}")
        failed += bool(problems)
    print()
    if failed:
        print(f"{failed} of {len(found)} failed")
    else:
        print(f"all {len(found)} passed")
    return 1 if failed else 0


def cmd_offline(args) -> int:
    return _report(_load(args), offline, "Tier 0, offline, out of the corpus in this repository")


def cmd_online(args) -> int:
    cache = OfflineCache()
    found = _load(args)
    code = _report(
        found,
        lambda x: online(x, cache),
        "Tier 0, online, out of the committed cache and never the network",
    )
    print(f"{cache.hits} cache hits, {cache.misses} misses, {cache.size} entries in the store")
    return code


def cmd_coverage(args) -> int:
    problems = coverage(_load(args))
    print("Tier 0, is every experiment in the book registered here")
    for line in problems:
        print(f"  {CROSS}  {line}")
    if not problems:
        found = _load(args)
        entries = len(corpus_store.entries())
        print(f"  {TICK}  all {entries} corpus entries and every lesson are accounted for")
        print(f"      {len(found)} experiments registered")
    print()
    return 1 if problems else 0


def cmd_check(args) -> int:
    return cmd_coverage(args) or cmd_offline(args) or cmd_online(args)


def cmd_refresh(args) -> int:
    cache = Cache()
    found = _load(args)
    before = cache.size
    for x in found:
        if x.kind == "offline":
            continue
        got = refresh(x, cache)
        if got:
            print(f"{x.id}: fetched {', '.join(got)}")
    added = cache.size - before
    print(f"{added} new cache entries, {cache.size} in the store" if added else "nothing to fetch")
    if added:
        print("Look at what landed under tools/cecache/store and commit it with the change.")
    return 0


def cmd_prune(args) -> int:
    """Delete the cache entries nothing asks for. Prints them first, deletes on --yes.

    Deleting a response means somebody has to fetch it again if it turns out to be wanted,
    so this asks rather than assumes.
    """
    cache = Cache()
    dead = orphans(_load(args))
    if not dead:
        print(f"nothing to prune, all {cache.size} entries are accounted for")
        return 0
    freed = sum(cache.path_for(k).stat().st_size for k in dead)
    for key in dead:
        print(f"  {'deleted' if args.yes else 'would delete'}  {key}")
        if args.yes:
            cache.path_for(key).unlink()
    print(f"\n{len(dead)} entries, {freed // 1024} KB")
    if not args.yes:
        print("Run again with --yes to delete them.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.tier0", description=__doc__)
    parser.add_argument("--registry", default=None, help="a different experiments.toml")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, help_text in (
        ("list", cmd_list, "what is registered"),
        ("coverage", cmd_coverage, "is every corpus entry and every lesson registered"),
        ("offline", cmd_offline, "run every experiment out of the corpus"),
        ("online", cmd_online, "run every experiment out of the cache"),
        ("check", cmd_check, "both, which is what CI does"),
        ("refresh", cmd_refresh, "fetch missing cache entries from the live API"),
        ("prune", cmd_prune, "delete cache entries nothing asks for"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=fn)
        if name == "prune":
            p.add_argument("--yes", action="store_true", help="actually delete them")
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
