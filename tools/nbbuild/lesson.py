"""Writing a lesson notebook as a Python file instead of as JSON.

The `.ipynb` format is JSON with the prose stored as lists of strings with the newlines left
on. It is fine for a machine and hostile to a human: the diff for changing one word is
unreadable, ids have to be unique and are easy to duplicate by hand, and there is nowhere to
put a comment explaining why a cell is the way it is.

So the source of truth for every lesson is a `build.py` next to it, and the notebook is
generated. That buys four things. Prose lives in a triple quoted string where it can be read
and reviewed. Citations go through the same parser `refcheck` validates them with, so a
malformed one fails at build time rather than at review time. Glossary links are looked up,
so a lesson cannot ship a link to a definition somebody renamed. And cell ids are counted
out rather than typed, which removes the whole class of mistake.

The generated notebook is committed, because a reader clicking a Colab badge must not need a
build step. `nbbuild check` re-runs every builder and fails if the committed file has
drifted, which is what stops the two from disagreeing.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from gxray.glossary import link as glossary_link
from tools.refcheck import url as citation_url

from .claims import Claim, as_json, resolve
from .notebook import Cell, document

#: Colab reads notebooks straight out of GitHub, so a badge has to name the branch as well
#: as the path. Anything else quietly opens an older copy of the lesson.
REPOSITORY = "https://github.com/tamnd/gcc-internals"
COLAB = "https://colab.research.google.com/github/tamnd/gcc-internals/blob/main"
BADGE_IMAGE = "https://colab.research.google.com/assets/colab-badge.svg"

#: Punctuation the project does not use, written as escapes because these characters are
#: almost indistinguishable from a hyphen in a diff, which is exactly how they get in.
BANNED = (("—", "em dash"), ("–", "en dash"))

#: How a version note reads to somebody running the lesson. Short, and directly under the
#: cell rather than at the end of the section, because a reader comparing what they got
#: against what the lesson says is looking right there.
VERSION_NOTE = "> **Version note.** {text}"

#: The one that goes on almost every cell in Part I, hoisted here so that changing what the
#: lessons say about Colab is one edit rather than ninety six.
BANNER = (
    "Colab has a GCC, but it is not GCC 16, so the dumps you get from it will not match "
    "the ones printed here. The setup cell picks a backend that does match."
)

#: The first code cell of every lesson. It is the same in all of them on purpose, because a
#: reader who has run one lesson should be able to skip it in the next without reading it,
#: and because the day this needs fixing it needs fixing everywhere.
#:
#: Cloning rather than `pip install` is not laziness. The recorded dumps that Tier 0 runs on
#: live in `corpora/` at the top of the repository rather than inside the `gxray` package,
#: so an install from git would give a reader the code and none of the data.
SETUP = """\
# Setup. Safe to run twice, and does nothing at all if you already have the repository.
#
# Colab starts with none of this project's files and a GCC that is several years older than
# the one the lessons were written against. This cell fixes the first problem by cloning,
# and works around the second by having gxray fall back to recorded dumps or to Compiler
# Explorer, both of which are really GCC 16.
import os
import subprocess
import sys

REPO = "https://github.com/tamnd/gcc-internals"

if "google.colab" in sys.modules:
    if not os.path.isdir("gcc-internals"):
        subprocess.run(["git", "clone", "--depth", "1", "-q", REPO], check=True)
    if os.path.basename(os.getcwd()) != "gcc-internals":
        os.chdir("gcc-internals")
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

import gxray

print("gxray", gxray.__version__, "on python", sys.version.split()[0])
"""


def repository_root(start: Path | None = None) -> Path:
    """The top of the checkout, found by looking for the workspace pyproject.

    A builder gets run from wherever the author happens to be standing, and writing the
    notebook next to the current directory rather than next to the lesson is a mistake that
    is annoying to notice and trivial to prevent.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "lessons").exists():
            return candidate
    raise RuntimeError(f"cannot find the repository root from {here}")


class Malformed(ValueError):
    """Raised for a cell that would produce a notebook nobody wants to read."""


@dataclass
class Lesson:
    """One lesson under construction.

    `slug` is the directory name and `stem` is the file name and the id prefix, so T05 lives
    at `lessons/t05-ssa-in-one-lesson/t05.ipynb` with cells `t05-01` upwards.

    `title`, `milestone` and `summary` are here rather than in a table somewhere because the
    course index is generated from them. An index maintained by hand is an index that is
    wrong about the third lesson somebody adds in a hurry.
    """

    slug: str
    stem: str
    title: str = ""
    milestone: str = ""
    summary: str = ""
    root: Path = field(default_factory=repository_root)
    cells: list[Cell] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return self.root / "lessons" / self.slug / f"{self.stem}.ipynb"

    @property
    def relative(self) -> str:
        return f"lessons/{self.slug}/{self.stem}.ipynb"

    @property
    def badge(self) -> str:
        """The Colab badge for this lesson, built from its own path.

        Copying the previous lesson and forgetting to change the link is the easiest mistake
        in the project. Generating the badge from the path the notebook is about to be
        written to means it cannot happen at all.
        """
        return f"[![Open In Colab]({BADGE_IMAGE})]({COLAB}/{self.relative})"

    def cite(self, citation: str) -> str:
        """A citation as a markdown link, labelled with the whole citation.

        The label is the full `path:line@tag` rather than a friendly name on purpose. A
        reader skimming for the file and line should not have to hover over anything, and
        `refcheck` scans the built notebook, so a citation that stopped resolving fails the
        build here exactly as it would in a page.
        """
        return f"[`{citation}`]({citation_url(citation)})"

    def term(self, name: str, text: str = "") -> str:
        """A word linked into the glossary, so a lesson can use it without defining it.

        `text` is there for when the sentence wants a different form of the word, as in
        `term("phi node", "the phi at the top of bb 3")`. Asking for a term that does not
        exist raises at build time, which is the point.
        """
        return glossary_link(name, text)

    def claim(self, text: str, *, unobservable: str = "") -> str:
        """Mark a sentence as a behavioural claim, and get the sentence back unchanged.

        Returning the text is what keeps this out of the reader's way. The prose reads the
        same either way and nothing appears in the notebook, so marking a claim costs the
        author nothing at the point of writing and buys the build the ability to check it.

        The claim registers against the cell that is about to be added, which is why it works
        inside an f-string: by the time `md` runs, the claim already knows where it is. Its
        evidence is the next code cell, and `resolve` refuses a claim whose next code cell is
        on the far side of a section heading.

        `unobservable` is for the claims that are true and cannot be shown from a notebook,
        and it takes the reason rather than a flag, because why not is the part a reader and
        a later author both want. There is a cap on how many a lesson may have.
        """
        self.claims.append(Claim(text.strip(), len(self.cells), unobservable))
        return text

    def _forbid(self, text: str) -> None:
        """One of the project's writing rules, checked here rather than in review.

        Both characters are invisible in a diff and neither has ever been caught by a human.
        """
        for character, name in BANNED:
            if character in text:
                raise Malformed(f"cell {len(self.cells) + 1} contains an {name}")

    def _add(self, kind: str, text: str) -> None:
        body = text.strip("\n")
        if not body.strip():
            raise Malformed(f"cell {len(self.cells) + 1} is empty")
        self.cells.append(Cell(kind, f"{self.stem}-{len(self.cells) + 1:02d}", body))

    def md(self, text: str) -> None:
        """A prose cell."""
        self._forbid(text)
        self._add("markdown", text)

    def code(self, text: str, *, differs: str = "", varies: str = "", quiet: bool = False) -> None:
        """A code cell, with no outputs and no execution count.

        Outputs are never committed. The only proof a cell works is CI executing it, and a
        stored output is a screenshot that goes stale without telling anybody.

        `differs` is for a cell whose output depends on which GCC produced it. The lessons
        are written against the pinned 16.2 and a reader may be on Compiler Explorer, on a
        recorded dump, or on whatever their distribution ships, and a handful of cells will
        show them something that is true of none of those unless somebody says so.

        `varies` is the other kind of note, for a cell whose output depends on the reader's
        machine rather than on the version: which target GCC was configured for, how the
        distribution patched it, how much memory the pass had. It reads the same to a reader
        and it means something different, which is why it is a separate word.

        `quiet` turns the visible note off, for the lessons where one paragraph near the top
        already explains a difference that then shows up in a dozen cells. Repeating it under
        every one of them would train the reader to skip the notes, which is the opposite of
        what they are for.
        """
        if differs and varies:
            raise Malformed(f"cell {len(self.cells) + 1} is both differs and varies")
        note = differs or varies
        if note:
            # Checked before either cell is added, so a rejected note does not leave half of
            # itself behind in a lesson somebody is building interactively.
            self._forbid(note)
        self._add("code", text)
        if note and not quiet:
            self.md(VERSION_NOTE.format(text=note))

    def setup(self) -> None:
        """The standard first code cell. Every lesson calls this and none of them writes it."""
        self._add("code", SETUP)

    def document(self) -> str:
        """The finished notebook as the exact text that belongs on disk."""
        return document(self.cells)

    def save(self, argv: list[str] | None = None) -> int:
        """Write the notebook, or with `--check` report whether it is already correct.

        Both modes are the same function so that the thing CI verifies is the thing an author
        runs, rather than a second implementation that agrees with it most of the time.
        """
        arguments = sys.argv[1:] if argv is None else argv
        # Resolved before anything else, including under `--check`, so a claim that lost its
        # evidence fails the build rather than waiting for somebody to run `--claims`.
        found = resolve(self.claims, self.cells)
        if "--claims" in arguments:
            about = {
                "id": self.stem.upper(),
                "slug": self.slug,
                "milestone": self.milestone,
                "summary": self.summary,
                "badge": self.badge,
            }
            if self.title:
                about["title"] = self.title
            print(json.dumps(as_json(found, self.cells, self.relative, about), indent=1))
            return 0
        text = self.document()
        if "--check" in arguments:
            if not self.path.exists():
                print(f"{self.relative} has not been built")
                return 1
            if self.path.read_text(encoding="utf-8") != text:
                print(f"{self.relative} does not match its builder, run `just build-lessons`")
                return 1
            print(f"{self.relative} is up to date")
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")
        print(f"wrote {self.relative}, {len(self.cells)} cells")
        return 0
