"""What `./configure` decides, recorded from the pinned tree so a notebook can read it.

`gxray.toolchain` answers "how do I get a GCC 16". This answers the question a reader asks
about thirty seconds later, which is "what did those seven flags on the configure line
actually do, and what were the other hundred and fifty five".

    from gxray import configure

    build = configure.load()
    build.checking.default          # what --enable-checking is when you do not pass it
    build.language("c++").compiler  # cc1plus, which is the program gcc actually runs
    build.requires                  # gmp, mpfr and mpc, with both of their minimums

Everything here was measured by `lessons/b01-the-build/record.py` walking the checkout at
`releases/gcc-16.2.0`. Nothing is typed in except the one sentence of what each thing is
for, and nothing here is a number somebody remembered from a mailing list post.

Two things this deliberately does not do. It does not run configure, because a lesson that
takes four minutes to produce its first output is a lesson nobody finishes. And it does not
know anything about your machine, so a question like "will this build on macOS" is not one
it can answer. What it can tell you is what the script would be deciding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: Where the recorder puts it, and where a notebook looks. Named after this module rather
#: than after the thing it records, the same way `corpora/layout` is named after
#: `gxray.layout`, so it is obvious which reader goes with which directory.
BUILDS = Path(__file__).resolve().parent.parent / "corpora" / "configure"


@dataclass(frozen=True)
class Language:
    """One front end, as its `config-lang.in` declares it.

    A front end is not a directory and it is not a command line word. It is a program with
    a name of its own that the driver runs, and the three spellings do not match: the
    directory is `cp`, the word is `c++`, and the program is `cc1plus`.
    """

    #: What you write in `--enable-languages`.
    name: str

    #: The directory under `gcc/`.
    directory: str

    #: The program the driver runs for a source file in this language.
    compiler: str

    #: Whether a configure line that does not mention languages gets this one.
    default: bool

    #: Whether stage one of a bootstrap can be built with this front end enabled.
    boot: bool

    #: Target libraries that come with it, which is most of what the extra build time is.
    libs: tuple[str, ...] = ()

    def __str__(self) -> str:
        state = "on by default" if self.default else "opt in"
        return f"{self.name:<10}{self.compiler:<12}gcc/{self.directory:<10}{state}"


@dataclass(frozen=True)
class Checking:
    """The `--enable-checking` block: the four levels, the flags, and the default."""

    #: `no`, `release`, `yes` and `all`, in increasing order of paranoia and slowness.
    levels: tuple[str, ...]

    #: The individual checks, each of which can be named on its own.
    flags: tuple[str, ...]

    #: What you get when you do not pass the flag at all, for this tree.
    default: str

    #: What you would get instead if `gcc/DEV-PHASE` said `experimental`, which it does on
    #: every development branch and does not on a release tag.
    development: str

    #: Whether this tree is a release, which is the whole reason the two differ.
    release: bool


@dataclass(frozen=True)
class Requirement:
    """One library configure will not build without, and the two versions it knows about.

    Two, because configure asks twice. Below `hard` it refuses. Between the two it prints
    `buggy but acceptable` and carries on, which is a phrase worth recognising in a log.
    """

    library: str
    hard: str
    good: str

    #: How the error message spells the minimum, which is not always how the code enforces
    #: it. GMP is the one where they differ.
    said: str

    @property
    def rounded(self) -> bool:
        """Whether the message a reader gets is looser than the check they failed."""
        return not self.said.startswith(self.hard)


@dataclass(frozen=True)
class Knobs:
    """How many options one configure script offers, as `configure --help` lists them."""

    where: str
    enable: int
    with_: int

    @property
    def total(self) -> int:
        return self.enable + self.with_


@dataclass(frozen=True)
class Build:
    """Everything recorded about what configuring this tree involves."""

    tag: str
    commit: str
    version: str
    languages: tuple[Language, ...]
    checking: Checking
    requires: tuple[Requirement, ...]
    knobs: tuple[Knobs, ...]

    def language(self, name: str) -> Language:
        """One front end by the word you would write in `--enable-languages`."""
        for one in self.languages:
            if one.name == name:
                return one
        have = ", ".join(one.name for one in self.languages)
        raise KeyError(f"no front end called {name!r}. There are: {have}")

    @property
    def default_languages(self) -> tuple[str, ...]:
        """The front ends a configure line with no `--enable-languages` builds."""
        return tuple(one.name for one in self.languages if one.default)

    @property
    def options(self) -> int:
        """Every knob across every configure script a normal build runs."""
        return sum(k.total for k in self.knobs)

    def __str__(self) -> str:
        return (
            f"GCC {self.version} at {self.tag}, {len(self.languages)} front ends, "
            f"{self.options} configure options"
        )


def load(name: str = "gcc", root: Path | str | None = None) -> Build:
    """Read the committed recording. This is the call a notebook makes."""
    path = Path(root or BUILDS) / f"{name}.json"
    if not path.exists():
        have = ", ".join(sorted(p.stem for p in path.parent.glob("*.json"))) or "none"
        raise FileNotFoundError(f"no build recording called {name!r}. Have: {have}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Build(
        tag=data["tag"],
        commit=data["commit"],
        version=data["version"],
        languages=tuple(
            Language(
                name=row["name"],
                directory=row["directory"],
                compiler=row["compiler"],
                default=row["default"],
                boot=row["boot"],
                libs=tuple(row["libs"]),
            )
            for row in data["languages"]
        ),
        checking=Checking(
            levels=tuple(data["checking"]["levels"]),
            flags=tuple(data["checking"]["flags"]),
            default=data["checking"]["default"],
            development=data["checking"]["development"],
            release=data["checking"]["release"],
        ),
        requires=tuple(Requirement(**row) for row in data["requires"]),
        knobs=tuple(
            Knobs(where=row["where"], enable=row["enable"], with_=row["with"])
            for row in data["knobs"]
        ),
    )


__all__ = [
    "BUILDS",
    "Build",
    "Checking",
    "Knobs",
    "Language",
    "Requirement",
    "load",
]
