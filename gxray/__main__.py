"""The gxray command line, which is mostly here so that a lesson can be checked by hand.

    gxray banner
    gxray passes --program l1 -O2
    gxray passes --program l1 -O2 --grep vrp
    gxray dumps --program l1 -O2
    gxray web --program l1 -O2 --dump tree-ssa --name s_1
    gxray options --against="-O1" -O2

Everything it prints comes from a real compiler run. There are no baked in numbers, which
is the point: when a lesson quotes a figure, this is how a reader checks it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gxray import corpus_store, options, programs
from gxray.build import banner
from gxray.driver import CE_RAW, BackendError, CEBackend, CorpusBackend, LocalBackend

PROGRAMS = {"l0": programs.L0, "l1": programs.L1, "l2": programs.L2}


def pick_backend(args: argparse.Namespace):
    """Turn --backend into a backend. Local unless told otherwise."""
    if args.backend == "ce":
        return CEBackend(args.compiler_id, filters=CE_RAW if args.raw_asm else None)
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


def cmd_chain(args: argparse.Namespace) -> int:
    """What the driver would run, and what it would tell each program."""
    found = pick_backend(args).chain(source_for(args), *args.flags)
    print(f"{found}\n")
    for n, step in enumerate(found, 1):
        print(f"{n}. {step.name}{'  ' + step.role if step.role else ''}")
        if args.full:
            print(f"     {step.program}")
            for arg in step.argv:
                print(f"       {arg}")
    return 0


def cmd_options(args: argparse.Namespace) -> int:
    """The optimizer flag table for these flags, or the difference from another set."""
    backend = pick_backend(args)
    here = backend.options(args.kind, *args.flags)
    if not args.against:
        print(f"{here}\n")
        for option in here.options.values():
            print(f"  {option}")
        return 0
    there = backend.options(args.kind, *args.against.split())
    changes = options.diff(there, here)
    print(f"{args.against} to {' '.join(args.flags)}: {len(changes)} change(s)\n")
    for change in changes:
        print(f"  {change}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    # Almost always local, because the corpus is meant to be the pinned compiler. Compiler
    # Explorer is allowed here for one job: recording what a differently configured GCC 16
    # of the same version does, which is the only way a lesson can compare the two offline.
    backend = pick_backend(args)
    if isinstance(backend, CorpusBackend):
        print("recording from the corpus into the corpus would not tell anybody anything")
        return 2
    if isinstance(backend, LocalBackend) and not backend.available:
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
        chains=[spec.split() for spec in args.chain or []],
        pipelines=[spec.split() for spec in args.pipeline or []],
        tables=[spec.split() for spec in args.table or []],
        assemblies=[spec.split() for spec in args.asm or []],
    )
    path = corpus_store.save(rec)
    counts = [
        (len(rec.pass_texts), "pass list(s)"),
        (len(rec.option_texts), "option table(s)"),
        (len(rec.asm_texts), "assembly listing(s)"),
    ]
    extra = "".join(f", {n} {what}" for n, what in counts if n)
    print(f"wrote {path} ({len(rec.dump_texts)} dumps{extra})")
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
    common.add_argument(
        "--raw-asm",
        action="store_true",
        # Compiler Explorer hides directives, labels and comments by default, which is the
        # right default for a lesson about instructions and the wrong one for a lesson about
        # sections or about the -dp annotations, since those are comments.
        help="ask Compiler Explorer for the assembly unfiltered, directives and all",
    )

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

    sc = sub.add_parser("chain", parents=[common], help="which programs the driver would run")
    sc.add_argument("--full", action="store_true", help="every argument, one per line")

    so = sub.add_parser("options", parents=[common], help="what -Q --help= prints for these flags")
    so.add_argument("--kind", default="optimizers", choices=["optimizers", "params"])
    so.add_argument(
        "--against",
        metavar="FLAGS",
        # Attached, as --against="-O1", because the value starts with a dash.
        help='print only what differs from these flags, as --against="-O1"',
    )

    sr = sub.add_parser("record", parents=[common], help="record a corpus entry from local GCC")
    sr.add_argument(
        "--chain",
        action="append",
        metavar="FLAGS",
        # The value starts with a dash, so it has to arrive attached: --chain="-O2 -c".
        help='also record what -### prints for these flags, repeatable, as --chain="-O2 -c"',
    )
    sr.add_argument(
        "--pipeline",
        action="append",
        metavar="FLAGS",
        # Attached for the same reason --chain is: the value starts with a dash.
        help='also record what -fdump-passes prints for these flags, as --pipeline="-O1"',
    )
    sr.add_argument(
        "--table",
        action="append",
        metavar="KIND FLAGS",
        # A kind and then flags, as --table="optimizers -O2". Nothing is compiled for one.
        help='also record what -Q --help= prints, as --table="optimizers -O2"',
    )
    sr.add_argument(
        "--asm",
        action="append",
        metavar="FLAGS",
        # Attached for the same reason --chain is: the value starts with a dash.
        help='also record the assembly for these flags, as --asm="-O1 -fgcse"',
    )
    return p


COMMANDS = {
    "banner": cmd_banner,
    "passes": cmd_passes,
    "dumps": cmd_dumps,
    "web": cmd_web,
    "chain": cmd_chain,
    "options": cmd_options,
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
