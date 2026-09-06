"""The matrix command line.

    matrix jobs --on push     the job list, as JSON, for a workflow matrix
    matrix table              write the table into containers/README.md
    matrix table --check      fail when the README has fallen behind matrix.toml
    matrix show ID            one configuration, expanded, the way the build sees it
    matrix digests --check    fail when the lockfile and the matrix disagree
    matrix record DIR         fold published digests into the lockfile and the devcontainer

None of this needs Docker, a registry, or the pinned GCC tree. It reads one TOML file, so
it runs in any job and on any laptop, which is the reason the matrix is a TOML file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.matrix import (
    DEVCONTAINER,
    LOCKFILE,
    README,
    TRIGGERS,
    MatrixError,
    build,
    load,
    lock_problems,
    record,
    repin,
    table,
)


def cmd_jobs(args) -> int:
    found = load()
    jobs = found.jobs(args.on)
    if args.pretty:
        for job in jobs:
            print(f"{job['id']:<6} {job['arch']:<6} {job['runner']:<16} {job['minutes']:>4} min")
        print(f"\n{len(jobs)} job(s) on a {args.on}")
        return 0
    # GitHub wants `{"include": [...]}` and nothing else, on one line.
    print(json.dumps({"include": jobs}, separators=(",", ":")))
    return 0


def cmd_table(args) -> int:
    found = load()
    if args.check:
        was = README.read_text(encoding="utf-8")
        if table(found) in was:
            print(f"matrix: the table in {README.name} matches {len(found.configs)} configurations")
            return 0
        print(
            f"matrix: the table in containers/{README.name} is not the one matrix.toml"
            " describes. Run: just matrix-table",
            file=sys.stderr,
        )
        return 1
    if build():
        print(f"matrix: rewrote the table in containers/{README.name}")
    else:
        print(f"matrix: the table in containers/{README.name} was already up to date")
    return 0


def cmd_show(args) -> int:
    found = load()
    config = found[args.id]
    print(f"{config.id}, {config.purpose}")
    print(f"\n{config.why}\n")
    print(f"  dockerfile   {config.dockerfile}")
    print(f"  arches       {', '.join(config.arches)}")
    print(f"  built        weekly={config.weekly} on_patches={config.on_patches}")
    print(f"  cost         about {config.minutes} min and {config.gigabytes:g} GB per arch")
    if not config.from_source:
        print("\nThis one does not build GCC. It installs the distribution's and adds the plugin.")
        return 0
    print(f"  make         {config.make}")
    print(f"  install      {config.install}")
    print(f"  cflags       {config.cflags}")
    if config.packages:
        print(f"  packages     {config.packages}")
    print(f"  smoke        {config.smoke}")
    print("\nconfigure")
    for flag in config.flags:
        print(f"  {flag}")
    return 0


def cmd_digests(args) -> int:
    found = load()
    problems = lock_problems(found)
    for problem in problems:
        print(f"matrix: {problem}", file=sys.stderr)
    if problems:
        print(
            f"\n{len(problems)} problem(s). {LOCKFILE.name} is written by the build matrix"
            " workflow, so the fix is usually to run it rather than to edit the file.",
            file=sys.stderr,
        )
        return 1
    print(f"matrix: every image in the matrix is pinned to a digest in {LOCKFILE.name}")
    return 0


def cmd_record(args) -> int:
    """Fold a directory of `image digest` lines into the lockfile. Run by the workflow.

    And then move the devcontainer's pin, because that file names a digest too and is the
    one nothing in CI pulls, so nothing in CI notices when it goes stale until an unrelated
    branch turns red.
    """
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"matrix: there is no {directory} to read digests out of", file=sys.stderr)
        return 2
    have = record(directory)
    print(f"matrix: {LOCKFILE.name} now names {len(have)} image(s)")
    moved = repin(have)
    if moved:
        print(f"matrix: {DEVCONTAINER.name} now pins {moved}")
    else:
        print(f"matrix: {DEVCONTAINER.name} already pins the image it should")
    return 0


COMMANDS = {
    "jobs": cmd_jobs,
    "table": cmd_table,
    "show": cmd_show,
    "digests": cmd_digests,
    "record": cmd_record,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="matrix", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        sp = sub.add_parser(name)
        if name == "jobs":
            sp.add_argument("--on", choices=TRIGGERS, default="weekly")
            sp.add_argument("--pretty", action="store_true", help="for a human, not a workflow")
        if name == "show":
            sp.add_argument("id", choices=[c.id for c in load().configs])
        if name == "record":
            sp.add_argument("directory", help="a directory of `image digest` text files")
        if name in ("table", "digests"):
            sp.add_argument("--check", action="store_true", help="fail instead of writing")
    args = p.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except MatrixError as exc:
        print(f"matrix: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
