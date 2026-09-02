"""The build matrix, as data rather than as YAML nobody can read.

Six configurations of GCC on two architectures. The whole thing lives in
`containers/matrix.toml`, and this module is what turns that file into the three things
that need it: the job list the workflow runs, the build arguments the Dockerfile takes, and
the table in `containers/README.md`.

The point of holding it in one file is that the alternative was tried by everyone and it
does not work. Configure flags in a Dockerfile, the job list in a workflow, and the times
and sizes in a README are three copies of one fact, and the second one goes stale the first
week and stays stale. Here the workflow asks this module what to run, the Dockerfile is
handed the flags, and `matrix table --check` fails the build when the README disagrees.

The other rule this enforces is the expensive one. No job in this project compiles GCC
except the matrix job. Everything else names an image by digest out of
`containers/images.lock.json`, so a pull request that wants a different compiler has to say
so in a file a reviewer can see, and a green CI run cannot quietly have been testing a
compiler nobody published.

    matrix jobs --on push        the job list, as JSON, for a workflow matrix
    matrix table                 the README table
    matrix table --check         fail when the README has fallen behind this file
    matrix show ID               one configuration, expanded, the way the build sees it
    matrix digests --check       fail when the lockfile names an image the matrix does not
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTAINERS = REPO_ROOT / "containers"
MATRIX = CONTAINERS / "matrix.toml"
LOCKFILE = CONTAINERS / "images.lock.json"
README = CONTAINERS / "README.md"

ARCHES = ("amd64", "arm64")
TRIGGERS = ("push", "weekly")

# The table in containers/README.md, between these two markers. Generated, so a hand edit
# to it is a hand edit that the next `just matrix-table` throws away, and saying so in the
# file itself is cheaper than explaining it afterwards.
TABLE_START = "<!-- matrix table start -->"
TABLE_END = "<!-- matrix table end -->"


class MatrixError(Exception):
    """The matrix file says something that cannot be true."""


@dataclass(frozen=True)
class Config:
    """One way of building GCC.

    `configure` here is only the flags that make this configuration what it is. The shared
    ones live in `[common]` and arrive through `flags`, so reading a table tells you what
    is different about it rather than what every build has.
    """

    id: str
    purpose: str
    why: str
    make: str
    install: str
    smoke: str
    cflags: str
    languages: str
    minutes: int
    gigabytes: float
    arches: tuple[str, ...]
    weekly: bool
    on_patches: bool
    configure: tuple[str, ...] = ()
    common: tuple[str, ...] = ()

    @property
    def from_source(self) -> bool:
        """Whether this builds a compiler or wraps one somebody else built.

        Only `plug` does the second, and it is the row that matters most, because a plugin
        that only loads into a compiler we built ourselves is a plugin that does not work.
        """
        return bool(self.make)

    @property
    def flags(self) -> list[str]:
        """Every configure flag, shared ones first, in the order the build passes them."""
        if not self.from_source:
            return []
        return [*self.common, f"--enable-languages={self.languages}", *self.configure]

    @property
    def dockerfile(self) -> str:
        return "Dockerfile" if self.from_source else "Dockerfile.plug"

    def image(self, registry: str, arch: str) -> str:
        return f"{registry}/{self.id}:{arch}"

    def runs_on(self, trigger: str) -> bool:
        if trigger == "weekly":
            return self.weekly
        if trigger == "push":
            return self.on_patches
        raise MatrixError(f"there is no {trigger!r} trigger, only {' and '.join(TRIGGERS)}")


@dataclass
class Matrix:
    tag: str
    registry: str
    configs: list[Config] = field(default_factory=list)

    def __getitem__(self, name: str) -> Config:
        for config in self.configs:
            if config.id == name:
                return config
        known = ", ".join(c.id for c in self.configs)
        raise MatrixError(f"there is no {name!r} configuration. There is {known}")

    def jobs(self, trigger: str) -> list[dict[str, object]]:
        """One entry per configuration per architecture, which is what a workflow wants.

        A workflow matrix cannot express "this configuration on these architectures", so
        the cross product is done here where it can be tested, rather than in YAML where
        it cannot.
        """
        found: list[dict[str, object]] = []
        for config in self.configs:
            if not config.runs_on(trigger):
                continue
            for arch in config.arches:
                found.append(
                    {
                        "id": config.id,
                        "arch": arch,
                        "runner": runner(arch),
                        "dockerfile": config.dockerfile,
                        "image": config.image(self.registry, arch),
                        "flags": " ".join(config.flags),
                        "cflags": config.cflags,
                        "make": config.make,
                        "install": config.install,
                        "smoke": config.smoke,
                        "minutes": config.minutes,
                    }
                )
        return found

    @property
    def hours(self) -> float:
        """What one weekly run costs in machine hours, which is the number worth watching."""
        total = sum(c.minutes * len(c.arches) for c in self.configs if c.weekly)
        return round(total / 60, 1)


def runner(arch: str) -> str:
    """Which GitHub runner builds a given architecture.

    Native both ways. A cross build under qemu is somewhere between five and twenty times
    slower, and `boot` is already four hours.
    """
    if arch == "amd64":
        return "ubuntu-24.04"
    if arch == "arm64":
        return "ubuntu-24.04-arm"
    raise MatrixError(f"there is no {arch!r} runner, only {' and '.join(ARCHES)}")


def load(path: Path | None = None) -> Matrix:
    raw = tomllib.loads((path or MATRIX).read_text(encoding="utf-8"))
    shared = raw.get("common", {})
    common = tuple(shared.get("configure", ()))
    found = Matrix(tag=raw["tag"], registry=raw["registry"])
    for entry in raw.get("config", []):
        found.configs.append(
            Config(
                id=entry["id"],
                purpose=entry["purpose"],
                why=entry["why"],
                make=entry["make"],
                install=entry.get("install", shared.get("install", "")),
                smoke=entry.get("smoke", shared.get("smoke", "")),
                cflags=entry["cflags"],
                languages=entry.get("languages", shared.get("languages", "c")),
                minutes=entry["minutes"],
                gigabytes=entry["gigabytes"],
                arches=tuple(entry["arches"]),
                weekly=entry["weekly"],
                on_patches=entry["on_patches"],
                configure=tuple(entry.get("configure", ())),
                common=common if entry["make"] else (),
            )
        )
    problems = validate(found)
    if problems:
        raise MatrixError("; ".join(problems))
    return found


def validate(found: Matrix) -> list[str]:
    """Everything about the file that could be wrong without looking wrong."""
    problems = []
    seen: set[str] = set()
    for config in found.configs:
        if config.id in seen:
            problems.append(f"{config.id} is in here twice")
        seen.add(config.id)
        for arch in config.arches:
            if arch not in ARCHES:
                problems.append(f"{config.id} wants {arch}, and there are only {ARCHES}")
        if not config.arches:
            problems.append(f"{config.id} builds for no architecture at all")
        if config.on_patches and not config.weekly:
            # Not a rule of the world, a rule of this project: an image built only on a
            # patch change goes stale the moment nobody touches patches for a month, and
            # then the day somebody needs it, it is two GCC point releases behind.
            problems.append(f"{config.id} is built on a push but never on a schedule")
        if config.from_source and not config.cflags:
            problems.append(f"{config.id} builds GCC and says nothing about optimization")
        if config.from_source and not config.install:
            problems.append(f"{config.id} builds GCC and never installs it")
        if config.from_source and not config.smoke:
            # A compiler that came out of a four hour build and cannot compile anything is
            # a thing to discover in the build and not two jobs later.
            problems.append(f"{config.id} builds GCC and never checks that it works")
    return problems


def row(config: Config) -> str:
    when = "weekly and on a patch change" if config.on_patches else "weekly"
    size = f"{config.gigabytes:g} GB"
    return (
        f"| `{config.id}` | {config.purpose} | {config.minutes} min | {size} | "
        f"{', '.join(config.arches)} | {when} |"
    )


def table(found: Matrix) -> str:
    head = "| Config | What it is | Build | Size | Arches | Built |\n|---|---|---|---|---|---|\n"
    rows = "\n".join(row(c) for c in found.configs)
    every = ", ".join(f"`{c.id}`" for c in found.configs)
    return (
        f"{head}{rows}\n\n"
        f"{len(found.configs)} configurations, {every}, on {len(ARCHES)} architectures. "
        f"One full weekly run is about {found.hours} machine hours.\n"
    )


def rewrite(text: str, block: str) -> str:
    """Swap what is between the markers, and complain if they are not both there."""
    start = text.find(TABLE_START)
    end = text.find(TABLE_END)
    if start == -1 or end == -1 or end < start:
        raise MatrixError(f"{README.name} has lost its {TABLE_START} and {TABLE_END} markers")
    return text[: start + len(TABLE_START)] + "\n\n" + block + "\n" + text[end:]


def build(path: Path | None = None) -> bool:
    """Write the table into the README. True when that changed something."""
    target = path or README
    was = target.read_text(encoding="utf-8")
    now = rewrite(was, table(load()))
    if now == was:
        return False
    target.write_text(now, encoding="utf-8")
    return True


def digests(path: Path | None = None) -> dict[str, str]:
    target = path or LOCKFILE
    if not target.is_file():
        return {}
    return json.loads(target.read_text(encoding="utf-8")).get("images", {})


def lock_problems(found: Matrix, locked: dict[str, str] | None = None) -> list[str]:
    """Does the lockfile name the images this matrix produces, and nothing else.

    An entry for an image the matrix no longer builds is the dangerous one. It keeps
    resolving, because a digest in a registry outlives the workflow that pushed it, so a
    job goes on quietly pulling a compiler that nothing rebuilds.
    """
    have = digests() if locked is None else locked
    want = {c.image(found.registry, arch) for c in found.configs for arch in c.arches}
    extra = sorted(set(have) - want)
    missing = sorted(want - set(have))
    problems = [f"{n} is in the lockfile and not in the matrix" for n in extra]
    problems += [f"{n} is in the matrix and not in the lockfile" for n in missing]
    for name, digest in sorted(have.items()):
        if not digest.startswith("sha256:") or len(digest) != len("sha256:") + 64:
            problems.append(f"{name} is pinned to {digest!r}, which is not a digest")
    return problems


def record(directory: Path, path: Path | None = None) -> dict[str, str]:
    """Fold a directory of `image digest` lines into the lockfile, and write it.

    A merge and not a replacement. A run that rebuilt one configuration by hand must not
    delete the eleven entries it knows nothing about, which is the obvious way to write
    this and is wrong the first time somebody uses `workflow_dispatch`.
    """
    target = path or LOCKFILE
    have = dict(digests(target))
    for line in sorted(directory.glob("*.txt")):
        for row_text in line.read_text(encoding="utf-8").splitlines():
            if not row_text.strip():
                continue
            image, _, digest = row_text.partition(" ")
            if not digest.strip():
                raise MatrixError(f"{line.name} has a line with no digest on it: {row_text!r}")
            have[image] = digest.strip()
    body = {
        "comment": (
            "Written by the build matrix workflow. Every image the project uses is pulled"
            " by the digest in here, so that a job cannot silently be testing a compiler"
            " nobody published. Run: python -m tools.matrix digests --check"
        ),
        "images": dict(sorted(have.items())),
    }
    target.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return have


__all__ = [
    "Config",
    "Matrix",
    "MatrixError",
    "build",
    "digests",
    "load",
    "lock_problems",
    "record",
    "row",
    "runner",
    "table",
    "validate",
]
