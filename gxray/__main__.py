"""The gxray command line, which is mostly here so that a lesson can be checked by hand.

    gxray banner
    gxray passes --program l1 -O2
    gxray passes --program l1 -O2 --grep vrp
    gxray dumps --program l1 -O2
    gxray web --program l1 -O2 --dump tree-ssa --name s_1

Everything it prints comes from a real compiler run. There are no baked in numbers, which
is the point: when a lesson quotes a figure, this is how a reader checks it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gxray import corpus_store, programs
from gxray.build import banner
from gxray.driver import BackendError, CEBackend, CorpusBackend, LocalBackend

PROGRAMS = {"l0": programs.L0, "l1": programs.L1, "l2": programs.L2}


def pick_backend(args: argparse.Namespace):
    """Turn --backend into a backend. Local unless told otherwise."""
    if args.backend == "ce":
        return CEBackend(args.compiler_id)
    if args.backend == "corpus":
        return CorpusBackend(args.entry)
    return LocalBackend(args.gcc)


def source_for(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            return fh.read()
    return PROGRAMS[args.program]


def cmd_banner(args: argparse.Namespace) -> int:
    print(banner(pick_backend(args)))
    return 0


def cmd_passes(args: argparse.Namespace) -> int:
    backend = pick_backend(args)
    if not isinstance(backend, LocalBackend):
        print("passes needs a local compiler, because -fdump-passes has no other route out")
        return 2
    if not backend.available:
        print(f"{backend.gcc} is not on PATH")
        return 2

    pipeline = backend.pipeline(source_for(args), *args.flags)
    counts = pipeline.counts()

    if args.counts:
        for k, v in counts.items():
            print(f"{k:>10}  {v}")
        return 0

    for p in pipeline.all:
        if args.grep and args.grep not in p.name:
            continue
        if args.enabled_only and not p.enabled:
            continue
        state = "on " if p.enabled else "off"
        dump = p.dump_key or "-"
        print(f"{'  ' * p.depth}{p.name:<40} {state}  {dump}")

    print(f"\n{counts['total']} passes, {counts['enabled']} on, {counts['with_dump']} with a dump")
    return 0


def cmd_dumps(args: argparse.Namespace) -> int:
    backend = pick_backend(args)
    result = backend.compile(source_for(args), *args.flags, dumps=args.dump or ["tree-all"])
    if not result.ok:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    for d in result.dump_files or []:
        print(f"{d.index:>4}  {d.phase:<5} {d.name}")
    if not result.dump_files:
        for key in result.dump_keys:
            print(key)

    n = len(result.dump_texts)
    print(f"\n{n} dump(s), {result.unparsed_count} statement(s) the parser did not recognise")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    backend = pick_backend(args)
    result = backend.compile(source_for(args), *args.flags, dumps=[args.dump])
    fn = result.dump(args.dump).only()
    web = fn.ssa_web(args.name)

    print(f"{fn}\n")
    print(f"{web['name']} defined by")
    print(f"  {web['def'] or 'nothing in this function, so it came in from outside'}")
    print(f"\nused by {len(web['uses'])}")
    for use in web["uses"]:
        print(f"  bb {use.block}  {use}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    backend = LocalBackend(args.gcc)
    if not backend.available:
        print(f"{backend.gcc} is not on PATH, and the corpus has to come from the pinned compiler")
        return 2
    # The name the compiler sees ends up printed in front of every statement in a dump
    # recorded with `-lineno`, so it is the program's own name rather than `input.c`.
    rec = corpus_store.record(
        backend,
        args.entry,
        source_for(args),
        *args.flags,
        dumps=args.dump or ["tree-all"],
        filename=Path(args.file).name if args.file else f"{args.program}.c",
    )
    path = corpus_store.save(rec)
    print(f"wrote {path} ({len(rec.dump_texts)} dumps)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--backend", choices=["local", "ce", "corpus"], default="local")
    common.add_argument("--gcc", default="gcc-16", help="which local compiler to drive")
    common.add_argument("--compiler-id", default="cg162", help="Compiler Explorer compiler id")
    common.add_argument("--entry", default="l1-O2", help="corpus entry to read or write")
    common.add_argument("--program", choices=sorted(PROGRAMS), default="l1")
    common.add_argument("--file", help="compile this file instead of a corpus program")
    common.add_argument("--dump", action="append", help="dump to ask for, repeatable")

    p = argparse.ArgumentParser(prog="gxray", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("banner", parents=[common], help="which compiler and backend is in front of you")

    sp = sub.add_parser("passes", parents=[common], help="the pass pipeline for these flags")
    sp.add_argument("--grep", help="only passes whose name contains this")
    sp.add_argument("--enabled-only", action="store_true")
    sp.add_argument("--counts", action="store_true", help="only the numbers")

    sub.add_parser("dumps", parents=[common], help="every dump these flags produce")

    sw = sub.add_parser("web", parents=[common], help="where an SSA name comes from and goes")
    sw.add_argument("--name", required=True, help="an SSA name such as s_1")

    sub.add_parser("record", parents=[common], help="record a corpus entry from local GCC")
    return p


COMMANDS = {
    "banner": cmd_banner,
    "passes": cmd_passes,
    "dumps": cmd_dumps,
    "web": cmd_web,
    "record": cmd_record,
}


def main(argv: list[str] | None = None) -> int:
    # Anything argparse does not recognise is a compiler flag, so `gxray passes -O2 -funroll-loops`
    # works without quoting or a `--` separator. A typo in a gxray option therefore reaches GCC
    # rather than being caught here, and GCC says so loudly, which is a fair trade for being able
    # to paste a flag straight off a lesson page.
    args, rest = build_parser().parse_known_args(argv)
    args.flags = rest or ["-O2"]
    if args.command == "web" and not args.dump:
        args.dump = "tree-ssa"
    elif args.command == "web":
        args.dump = args.dump[0]
    try:
        return COMMANDS[args.command](args)
    except BackendError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
