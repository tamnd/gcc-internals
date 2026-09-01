"""Lessons are Python files that build notebooks, not notebooks people edit.

A lesson lives in `lessons/<slug>/` with a `build.py` in it, and the `.ipynb` next to it is
generated and committed. Writing one looks like this:

    from tools.nbbuild import Lesson

    lesson = Lesson("t05-ssa-in-one-lesson", "t05")
    cite, term, claim = lesson.cite, lesson.term, lesson.claim

    lesson.md(f"# T05. SSA in one lesson\\n\\n{lesson.badge}")
    lesson.setup()
    lesson.md(f"Every {term('SSA name')} has exactly one definition.")
    lesson.code("import gxray")

    raise SystemExit(lesson.save())

Run it to write the notebook, run it with `--check` to find out whether the committed one
still matches, and run it with `--claims` to print what it asserted. `python -m
tools.nbbuild build` does the first of those for every lesson at once.

There are four reasons the notebook is not the source. A JSON diff for a one word prose
change is unreadable. Cell ids have to be unique and typing them is how they stop being
unique. There is nowhere in a notebook to leave a comment saying why a cell is the way it
is. And a builder can look things up, so a citation goes through the same parser `refcheck`
validates it with and a glossary link fails the build if somebody renamed the term.
"""

from .claims import UNOBSERVABLE_CAP, Claim, TooMany, Unproved
from .lesson import BANNER, SETUP, Lesson, Malformed, repository_root
from .notebook import Cell, document

__all__ = [
    "BANNER",
    "SETUP",
    "UNOBSERVABLE_CAP",
    "Cell",
    "Claim",
    "Lesson",
    "Malformed",
    "TooMany",
    "Unproved",
    "document",
    "repository_root",
]
