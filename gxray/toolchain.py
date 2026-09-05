"""Getting a GCC 16 of your own, and knowing which one you got.

Every lesson before this one borrowed a compiler. Tier 0 borrows Compiler Explorer's or a
recording of one, and Tier 1 borrows whatever the reader's distribution shipped. B01 is
where the reader stops borrowing, and the first thing they need is a straight answer to
"which of these should I do", because there are three and they cost between five minutes
and four hours.

This module is the answer, read out of `containers/matrix.toml` rather than typed into a
lesson. That file is what the CI workflow builds from, what the README table is generated
from, and what the Dockerfile takes its flags from, so a lesson that reads it too cannot
tell the reader to run a configure line nothing has ever run.

    from gxray import toolchain

    toolchain.plan("rel").shell()      # the exact commands, in order
    toolchain.plan("rel").pull()       # or the one command that skips all of them
    toolchain.cheapest()               # what to do if you have five minutes

`tools.matrix` is imported rather than reimplemented. It is the only reader of the matrix
file and B01 is not going to be the second one, because two readers of one file is two
answers to "what does `rel` configure with" the first time somebody edits one of them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from tools.matrix import LOCKFILE, MATRIX, Config, Matrix, MatrixError
from tools.matrix import load as _load

#: What a from source build needs before it will start. Not GCC's own list, which is in the
#: installation manual and is about every host GCC has ever run on. This is the short list
#: that actually stops a reader on a laptop in 2026, and every entry is something this
#: project has watched somebody hit.
PREREQUISITES = (
    ("a C++14 compiler", "stage one is built by it, and GCC forces -std=c++14 on itself"),
    ("gmp, mpfr, mpc", "GCC will not configure without them, and says so clearly"),
    ("isl", "optional, and only the graphite loop passes need it"),
    ("flex, bison", "only if you touch a .l or .y file, which a reader of Part II will"),
    ("gnu make", "bsd make does not build GCC, and on macOS `make` is gnu make already"),
    ("disk", "between one and eight gigabytes depending on the configuration"),
)

#: The three ways to have a GCC 16, cheapest first. The order is the recommendation.
ROUTES = ("pull", "devcontainer", "source")


class ToolchainError(Exception):
    """Something the reader asked for that this project does not have."""


@cache
def matrix(path: Path | None = None) -> Matrix:
    """The build matrix, parsed once. Cached because a notebook calls it in every cell."""
    return _load(path)


@cache
def digests(path: Path | None = None) -> dict[str, str]:
    """Image name to the digest the workflow published, out of `images.lock.json`.

    Empty rather than an error when the file is missing, because a reader who cloned the
    repository has it and a reader who pip installed the package does not, and the second
    of those should still be able to read the configure lines.
    """
    where = path or LOCKFILE
    if not where.is_file():
        return {}
    return json.loads(where.read_text(encoding="utf-8")).get("images", {})


@dataclass(frozen=True)
class Plan:
    """Everything a reader needs to end up with one particular compiler.

    A plan is not a script and deliberately does not run anything. Building GCC takes
    between eighteen minutes and four hours and writes several gigabytes, and a notebook
    cell that starts that because somebody pressed shift and enter is a notebook cell that
    should not exist. `shell()` prints what to run and the reader runs it.
    """

    config: Config
    arch: str
    tag: str
    registry: str
    digest: str = ""

    @property
    def id(self) -> str:
        return self.config.id

    @property
    def image(self) -> str:
        return self.config.image(self.registry, self.arch)

    @property
    def minutes(self) -> int:
        return self.config.minutes

    @property
    def gigabytes(self) -> float:
        return self.config.gigabytes

    def pull(self) -> str:
        """The one command that gets this compiler without building anything.

        By digest when there is one, because a tag is a name somebody can move and a digest
        is not, and the whole point of pulling rather than building is to be sure which
        compiler you got.
        """
        if self.digest:
            name = self.image.rsplit(":", 1)[0]
            return f"docker pull {name}@{self.digest}"
        return f"docker pull {self.image}"

    def configure(self) -> str:
        """The configure line, exactly as the image runs it, shared flags first.

        `CFLAGS` and `CXXFLAGS` go on the configure line rather than on the make line, which
        is what the Dockerfile does and is the part most people get wrong.

        One caveat this cannot express, and BP-BOOTSTRAP invariant I7 can. A bootstrap does
        not use `CFLAGS` for any of its stages. Stage one gets `STAGE1_CFLAGS`, which is
        `-g` from configure, and the rest get `BOOT_CFLAGS`, which defaults to `-g -O2`. So
        the `-O2` below is what `boot` passes and what none of its three stages reads, and a
        reader who wants a differently optimised bootstrap sets `BOOT_CFLAGS` on the make
        line instead.
        """
        if not self.config.from_source:
            raise ToolchainError(f"{self.id} does not build GCC, it wraps one somebody else did")
        settings = [f'CFLAGS="{self.config.cflags}"', f'CXXFLAGS="{self.config.cflags}"']
        return " \\\n    ".join(["../gcc/configure", *self.config.flags, *settings])

    def shell(self) -> str:
        """The whole from source route as text, in the order a reader runs it."""
        if not self.config.from_source:
            return self.pull()
        return "\n".join(
            [
                f"git clone --depth 1 --branch {self.tag} \\",
                "    https://github.com/gcc-mirror/gcc.git gcc",
                "mkdir build && cd build",
                self.configure(),
                f'make {self.config.make} -j"$(nproc)"',
                f"make {self.config.install}",
            ]
        )

    def smoke(self) -> str:
        """The one command that says whether the thing that came out is a compiler."""
        return self.config.smoke

    def cost(self) -> str:
        """What it costs, in the two units a reader is deciding with."""
        return f"{self.minutes} minutes and {self.gigabytes} GB"


def plan(name: str, arch: str = "amd64", path: Path | None = None) -> Plan:
    """The plan for one configuration on one architecture."""
    found = matrix(path)
    config = found[name]
    if arch not in config.arches:
        have = ", ".join(config.arches)
        raise ToolchainError(f"{name} is not built for {arch}, only for {have}")
    return Plan(
        config=config,
        arch=arch,
        tag=found.tag,
        registry=found.registry,
        digest=digests().get(config.image(found.registry, arch), ""),
    )


def plans(arch: str = "amd64", path: Path | None = None) -> list[Plan]:
    """Every configuration built for this architecture, in the order the file declares."""
    return [plan(c.id, arch, path) for c in matrix(path).configs if arch in c.arches]


def names(path: Path | None = None) -> list[str]:
    return [c.id for c in matrix(path).configs]


def cheapest(arch: str = "amd64", path: Path | None = None) -> Plan:
    """The fastest way to a working GCC 16, which is the recommendation for a first read.

    Ties are broken by size rather than by declaration order, so this stays the same answer
    when somebody adds a configuration that happens to take the same number of minutes.
    """
    found = plans(arch, path)
    if not found:
        raise ToolchainError(f"nothing in the matrix is built for {arch}")
    return min(found, key=lambda p: (p.minutes, p.gigabytes, p.id))


def route(minutes: int, arch: str = "amd64", path: Path | None = None) -> list[Plan]:
    """Everything a reader with this much time could have, cheapest first.

    The question B01 opens with is not "how do I build GCC", it is "how much of my evening
    is this", and a reader who has twenty minutes should be shown the two things that fit
    rather than the six that exist.
    """
    fits = [p for p in plans(arch, path) if p.minutes <= minutes]
    return sorted(fits, key=lambda p: (p.minutes, p.gigabytes, p.id))


def table(arch: str = "amd64", path: Path | None = None) -> str:
    """The six configurations as a Markdown table, for a lesson to print."""
    rows = ["| Configuration | What it is for | Minutes | GB |", "|---|---|---|---|"]
    for p in plans(arch, path):
        rows.append(f"| `{p.id}` | {p.config.purpose} | {p.minutes} | {p.gigabytes} |")
    return "\n".join(rows)


def hours(path: Path | None = None) -> float:
    """Machine hours one weekly run of the whole matrix costs."""
    return matrix(path).hours


__all__ = [
    "LOCKFILE",
    "MATRIX",
    "PREREQUISITES",
    "ROUTES",
    "MatrixError",
    "Plan",
    "ToolchainError",
    "cheapest",
    "digests",
    "hours",
    "matrix",
    "names",
    "plan",
    "plans",
    "route",
    "table",
]
