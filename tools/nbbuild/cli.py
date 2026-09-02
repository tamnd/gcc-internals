"""Running every lesson builder, and collecting what they print.

Each builder is a script rather than a module the collector imports, and that is deliberate.
A lesson is allowed to do whatever it needs at build time, including importing something
heavy or failing outright, and one broken lesson should not take the whole run down in a way
that hides which one it was. Separate processes give that for free, and they also mean the
exit code of a single `python lessons/t05-ssa-in-one-lesson/build.py` is the same thing CI
sees, so an author can debug one lesson without learning a second command.

Exit codes: 0 for success, 1 for a lesson that is wrong, 2 for being asked to do something
that does not make sense.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .claims import render
from .lesson import repository_root

#: The eleven parts of the course, by the letter their lesson ids start with. Sorting the
#: slugs alphabetically would read the beginner ramp last and the back end before the middle
#: end, so the reading order is written down here rather than inferred. It is the order in
#: `05-curriculum.md` and it does not change when a lesson is added.
PARTS = "ZTBFGPDRISX"


def course_order(builder: Path) -> tuple[int, str]:
    """Where one lesson comes in the reading order, from the id its directory starts with."""
    slug = builder.parent.name
    part = PARTS.find(slug[0].upper())
    return (part if part >= 0 else len(PARTS), slug)


def builders(root: Path | None = None) -> list[Path]:
    """Every lesson builder, in the order the lessons are meant to be read.

    Within a part that is alphabetical, because the slugs start with the lesson id and the
    numbers were picked to sort. Across parts it is `PARTS`, because the letters were not.
    """
    root = root or repository_root()
    return sorted((root / "lessons").glob("*/build.py"), key=course_order)


def run(builder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """One builder, from the root of the repository so its relative paths mean something."""
    return subprocess.run(
        [sys.executable, str(builder), *args],
        capture_output=True,
        text=True,
        cwd=builder.parent.parent.parent,
        check=False,
    )


def build(check: bool = False) -> int:
    """Build or check every lesson, and report all the failures rather than the first."""
    found = builders()
    if not found:
        print("no lesson builders found under lessons/")
        return 1

    failed = []
    for builder in found:
        done = run(builder, *(["--check"] if check else []))
        sys.stdout.write(done.stdout)
        if done.returncode != 0:
            failed.append(builder.parent.name)
            sys.stderr.write(done.stderr)

    verb = "checked" if check else "built"
    if failed:
        print(f"\n{len(failed)} of {len(found)} lessons failed: {', '.join(failed)}")
        return 1
    print(f"\n{verb} {len(found)} lessons")
    return 0


INDEX_HEADER = """# The lessons

Ninety six lessons in eleven parts. This page is generated from the lessons themselves, so a lesson that exists is on it and a lesson that does not is not.

Every one is a notebook with a Colab badge, so there is nothing to install. Part I runs on the recorded dumps in `corpora/`, which are real output from a real GCC 16.2 and are committed, so a reader with a browser and no compiler sees what the lesson saw. Colab does have a GCC and it is not this one, which is why the setup cell picks a backend that matches and the banner says which one it picked.

"""


def report(root: Path) -> list[dict] | None:
    """Ask every builder what it claims and what it is about. None if one could not say."""
    entries = []
    for builder in builders(root):
        done = run(builder, "--claims")
        if done.returncode != 0:
            sys.stderr.write(done.stderr)
            print(f"{builder.parent.name} could not report its claims")
            return None
        entries.append(json.loads(done.stdout))
    return entries


def written(path: Path, text: str, check: bool, what: str, rebuild: str) -> int:
    """Write a generated file, or under `--check` fail when what is committed has drifted."""
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            print(f"{what} is out of date, run `{rebuild}`")
            return 1
        print(f"{what} is up to date")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {what}")
    return 0


#: The README carries the same table, spliced into a marked block. Same convention as `bpc`,
#: because a second convention for the same job is one more thing to remember.
BEGIN = "<!-- nbbuild:begin index -->"
END = "<!-- nbbuild:end index -->"


def index(check: bool = False) -> int:
    """Rebuild the course index, in the book and in the README, from the lessons themselves.

    An index kept by hand is an index that is wrong about the third lesson somebody adds in
    a hurry, so the title, the summary and the milestone live in the lesson's `build.py` and
    this reads them back out. Two copies of a table is two chances to be wrong, so there is
    one generator and neither copy is typed.
    """
    root = repository_root()
    entries = report(root)
    if entries is None:
        return 1
    page = written(
        root / "docs" / "lessons.md",
        INDEX_HEADER + table(entries),
        check,
        "docs/lessons.md",
        "just build-lessons",
    )
    readme = root / "README.md"
    return page or written(
        readme,
        splice(readme.read_text(encoding="utf-8"), table(entries)),
        check,
        "the lesson table in README.md",
        "just build-lessons",
    )


def splice(text: str, block: str) -> str:
    """Put the table between the markers in the README, leaving the prose alone."""
    start = text.find(BEGIN)
    stop = text.find(END)
    if start < 0 or stop < start:
        raise RuntimeError(f"README.md needs a {BEGIN} ... {END} block for the lesson table")
    return text[: start + len(BEGIN)] + "\n" + block + text[stop:]


def table(entries: list[dict]) -> str:
    """The index table, the one place its shape is decided."""
    out = [
        "| | Lesson | What you come away with | Milestone | Run it |\n",
        "|---|---|---|---|---|\n",
    ]
    for entry in entries:
        title = entry["title"].split(". ", 1)[-1]
        out.append(
            f"| {entry['id']} | [{title}](https://github.com/tamnd/gcc-internals/blob/main/"
            f"{entry['notebook']}) | {entry['summary']} | {entry['milestone']} | "
            f"{entry['badge']} |\n"
        )
    out.append(f"\n{len(entries)} of 96 written.\n")
    return "".join(out)


def claims(check: bool = False) -> int:
    """Rebuild `lessons/CLAIMS.md` from what the builders report, or check it is current."""
    root = repository_root()
    entries = report(root)
    if entries is None:
        return 1

    return written(
        root / "lessons" / "CLAIMS.md",
        render(entries),
        check,
        "lessons/CLAIMS.md",
        "just build-claims",
    )


def notebooks(root: Path | None = None) -> list[Path]:
    """Every committed lesson notebook, in course order.

    Found by looking rather than by guessing the file name from the directory name, so a
    lesson whose notebook is not named after its slug still gets run.
    """
    root = root or repository_root()
    return sorted((root / "lessons").glob("*/*.ipynb"))


def execute(show: bool = False) -> int:
    """Run every lesson in a real kernel, and optionally print what each cell printed.

    `--show` is not decoration. A cell that raises fails on its own, but a cell that prints
    an empty list where the prose promised four names passes quietly, and reading the
    transcript is the only thing that catches it.
    """
    from .execute import Failed, transcript
    from .execute import execute as run_one

    found = notebooks()
    if not found:
        print("no lesson notebooks found under lessons/")
        return 1

    failed = []
    for path in found:
        try:
            book = run_one(path)
        except Failed as exc:
            failed.append(path.parent.name)
            sys.stderr.write(f"{exc}\n")
            continue
        cells = sum(1 for cell in book.cells if cell.cell_type == "code")
        print(f"{path.parent.name}: {cells} code cells ran")
        if show:
            print()
            print(transcript(book))

    if failed:
        print(f"\n{len(failed)} of {len(found)} lessons failed: {', '.join(failed)}")
        return 1
    print(f"\nran {len(found)} lessons")
    return 0


USAGE = """usage: python -m tools.nbbuild <command>

  build    rebuild every lesson notebook from its build.py, and the index
  check    rebuild them in memory and fail if a committed file has drifted
  claims   rebuild lessons/CLAIMS.md from the claims the lessons marked
  verify   check the ledger is current without writing it
  index    rebuild docs/lessons.md, the course index
  run      execute every lesson in a real kernel, --show to print what it printed
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or len(args) > 2:
        sys.stderr.write(USAGE)
        return 2
    match args:
        case ["build"]:
            return build() or index()
        case ["check"]:
            return build(check=True) or index(check=True)
        case ["claims"]:
            return claims()
        case ["verify"]:
            return claims(check=True)
        case ["index"]:
            return index()
        case ["run"]:
            return execute()
        case ["run", "--show"]:
            return execute(show=True)
        case other:
            sys.stderr.write(f"no such command: {' '.join(other)}\n\n{USAGE}")
            return 2
