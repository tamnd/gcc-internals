"""The three stage bootstrap, and the oracle at the end of it, recorded so it can be run.

`gxray.configure` is what one build decides. This is what happens when the top level decides
to do it three times, and what the comparison between the last two proves.

    from gxray import bootstrap

    boot = bootstrap.load()
    boot.compared                  # the two stages that compare anything, of nine
    boot.stage("3").previous       # 2, which is the compiler that built it
    print(boot.compare().report()) # run the real rule over the recorded object files

The comparison here is not a description of GCC's comparison. It is the same rule, coded
from `Makefile.tpl:1824@releases/gcc-16.2.0` and given the exclusion list read out of
`configure.ac`, run over object files that a real GCC 16.2 really produced. What differs
about them was induced on purpose, one difference per pair, so that a reader can watch the
oracle fire without waiting four hours for a bootstrap to reach it.

What that means, and what it does not. The object files are small, they are not GCC's own,
and they were compiled on whatever machine ran the recorder, which `Bootstrap.host` names.
The rule applied to them is GCC's, down to the sixteen skipped bytes and the six forgiven
patterns. So the mechanism is real and the scale is not, and a reader who wants the scale
has `make bootstrap` and an afternoon.
"""

from __future__ import annotations

import base64
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path

#: Where the recorder puts it, named after this module the same way `corpora/configure` is.
BOOTS = Path(__file__).resolve().parent.parent / "corpora" / "bootstrap"

#: Bytes ignored at the front of every object file, because some object formats put a
#: timestamp there. GCC's number, from the compare rule.
SKIP = 16

#: What `$(objext)` is on every host this course runs on. The exclusion patterns are written
#: with the make variable in them and are matched after it is expanded, which is what make
#: does to them and is the reason `gcc/cc1-checksum.o` matches `gcc/cc*-checksum$(objext)`.
OBJEXT = ".o"


@dataclass(frozen=True)
class Stage:
    """One declared bootstrap stage, from its `bootstrap_stage` block in `Makefile.def`."""

    #: `1`, `2`, `3`, `4`, `profile`, `train`, `feedback`, `autoprofile`, `autofeedback`.
    id: str

    #: The stage whose compiler builds this one, or empty for stage one, which is built by
    #: whatever compiler was already on the machine.
    previous: str

    #: The stage this one is compared against, or empty. Only two stages compare anything.
    compares: str

    #: The `make` target that stops here, or empty for a stage that is only ever passed
    #: through on the way to another one.
    target: str

    #: This stage's own flag assignments, already rendered the way the template writes them.
    cflags: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return f"stage{self.id}"

    @property
    def built_by(self) -> str:
        return f"stage{self.previous}" if self.previous else "the compiler already there"

    def __str__(self) -> str:
        compared = f"compared against stage{self.compares}" if self.compares else "believed"
        return f"{self.name:<18}built by {self.built_by:<28}{compared}"


@dataclass(frozen=True)
class Objects:
    """One pair of object files a comparison would look at, as they were recorded.

    `left` is the earlier stage's and `right` is the later stage's. A pair with no `left` is
    a file that exists in the later stage and not the earlier one, which the real rule skips
    without reporting, and which is recorded here because that silence is worth seeing.
    """

    #: The path the comparison sees, relative to a stage directory. This is what the
    #: exclusion patterns are matched against.
    name: str

    #: One sentence on what was done to make these two differ, or not.
    about: str

    left: bytes | None
    right: bytes

    @property
    def missing(self) -> bool:
        return self.left is None

    def differs_at(self, skip: int = SKIP) -> int:
        """The first byte that differs, counted from the start of the file, or minus one.

        Counted from the start rather than from the skip, because that is the number a
        reader would get from `cmp` and would then go looking for in a hex dump.
        """
        if self.left is None:
            return -1
        a, b = self.left[skip:], self.right[skip:]
        if a == b:
            return -1
        for n, (x, y) in enumerate(zip(a, b, strict=False)):
            if x != y:
                return skip + n
        return skip + min(len(a), len(b))


@dataclass(frozen=True)
class Difference:
    """One object file that was not the same in both stages."""

    name: str

    #: The offset `cmp` would report, counting from the start of the file.
    at: int

    #: The exclusion pattern that forgave it, or empty, in which case it fails the build.
    pattern: str

    @property
    def forgiven(self) -> bool:
        return bool(self.pattern)

    def __str__(self) -> str:
        if self.forgiven:
            return f"warning: {self.name} differs   (forgiven by {self.pattern})"
        return f"{self.name} differs at byte {self.at}"


@dataclass(frozen=True)
class Comparison:
    """What one run of the compare rule found."""

    left: str
    right: str
    skip: int
    forgiven: tuple[str, ...]

    #: Every pair the rule looked at, in the order it looked.
    same: tuple[str, ...]
    differences: tuple[Difference, ...]
    skipped: tuple[str, ...]

    @property
    def checked(self) -> int:
        return len(self.same) + len(self.differences)

    @property
    def bad(self) -> tuple[Difference, ...]:
        """The differences that were not forgiven, which is what stops the build."""
        return tuple(d for d in self.differences if not d.forgiven)

    @property
    def failed(self) -> bool:
        return bool(self.bad)

    def report(self) -> str:
        """What `make` prints, in the order it prints it.

        The warnings come first because they are printed as the rule walks the files, and
        the failure comes last because it is the shell exiting after the loop.
        """
        lines = [f"Comparing stages {self.left} and {self.right}"]
        lines += [str(d) for d in self.differences if d.forgiven]
        if not self.failed:
            lines.append("Comparison successful.")
            return "\n".join(lines)
        lines.append("Bootstrap comparison failure!")
        lines += [d.name for d in self.bad]
        lines.append("make: *** [compare] Error 1")
        return "\n".join(lines)

    def bad_compare(self) -> str:
        """The `.bad_compare` file the failed rule leaves behind, which is the list alone."""
        return "".join(f"{d.name}\n" for d in self.bad)


@dataclass(frozen=True)
class Bootstrap:
    """Everything recorded about building the compiler with itself."""

    tag: str
    commit: str

    #: The machine the object files were compiled on, and by what, because they are the one
    #: part of this recording that is not a property of the GCC sources.
    host: str
    compiler: str

    stages: tuple[Stage, ...]

    #: Host modules rebuilt in every stage, and the ones built once at the end.
    inside: tuple[str, ...]
    outside: tuple[str, ...]

    #: The same split for target libraries, which are compiled by each stage's own compiler
    #: for the target machine. The staged ones are the only generated target code a stage
    #: comparison ever looks at.
    target_inside: tuple[str, ...]
    target_outside: tuple[str, ...]

    #: The object files a comparison is allowed to find different, as written.
    exclusions: tuple[str, ...]

    #: The `config/bootstrap-*.mk` fragments `--with-build-config` takes.
    configs: tuple[str, ...]

    objects: tuple[Objects, ...]

    def stage(self, id: str) -> Stage:
        for one in self.stages:
            if one.id == str(id):
                return one
        have = ", ".join(one.id for one in self.stages)
        raise KeyError(f"no bootstrap stage {id!r}. There are: {have}")

    @property
    def compared(self) -> tuple[Stage, ...]:
        """The stages that compare anything. Every other one is a compiler that is believed."""
        return tuple(one for one in self.stages if one.compares)

    @property
    def default(self) -> tuple[Stage, ...]:
        """The three stages a plain `make bootstrap` runs."""
        return tuple(one for one in self.stages if one.id in ("1", "2", "3"))

    def forgives(self, name: str) -> str:
        """The exclusion pattern that lets this file differ, or empty if none does."""
        for pattern in self.exclusions:
            if fnmatch.fnmatchcase(name, pattern.replace("$(objext)", OBJEXT)):
                return pattern
        return ""

    def compare(self, skip: int = SKIP) -> Comparison:
        """Run the compare rule over the recorded object files.

        This is `Makefile.tpl:1824@releases/gcc-16.2.0` in Python: walk the later stage's
        object files, skip any the earlier stage does not have, compare the rest past the
        first `skip` bytes, and let a file the exclusion list names differ with a warning.
        """
        same, differences, skipped = [], [], []
        for pair in self.objects:
            if pair.missing:
                skipped.append(pair.name)
                continue
            at = pair.differs_at(skip)
            if at < 0:
                same.append(pair.name)
                continue
            differences.append(Difference(pair.name, at, self.forgives(pair.name)))
        two, three = self.compared[0].compares, self.compared[0].id
        return Comparison(
            left=two,
            right=three,
            skip=skip,
            forgiven=self.exclusions,
            same=tuple(same),
            differences=tuple(differences),
            skipped=tuple(skipped),
        )

    def pair(self, name: str) -> Objects:
        for one in self.objects:
            if one.name == name:
                return one
        have = ", ".join(one.name for one in self.objects)
        raise KeyError(f"no recorded object file called {name!r}. There are: {have}")

    def __str__(self) -> str:
        return (
            f"GCC at {self.tag}, {len(self.stages)} stages, {len(self.compared)} of them "
            f"compared, {len(self.exclusions)} files forgiven"
        )


def load(name: str = "gcc", root: Path | str | None = None) -> Bootstrap:
    """Read the committed recording. This is the call a notebook makes."""
    path = Path(root or BOOTS) / f"{name}.json"
    if not path.exists():
        have = ", ".join(sorted(p.stem for p in path.parent.glob("*.json"))) or "none"
        raise FileNotFoundError(f"no bootstrap recording called {name!r}. Have: {have}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Bootstrap(
        tag=data["tag"],
        commit=data["commit"],
        host=data["host"],
        compiler=data["compiler"],
        stages=tuple(
            Stage(
                id=row["id"],
                previous=row["previous"],
                compares=row["compares"],
                target=row["target"],
                cflags=tuple(row["cflags"]),
            )
            for row in data["stages"]
        ),
        inside=tuple(data["inside"]),
        outside=tuple(data["outside"]),
        target_inside=tuple(data["target_inside"]),
        target_outside=tuple(data["target_outside"]),
        exclusions=tuple(data["exclusions"]),
        configs=tuple(data["configs"]),
        objects=tuple(
            Objects(
                name=row["name"],
                about=row["about"],
                left=base64.b64decode(row["left"]) if row["left"] else None,
                right=base64.b64decode(row["right"]),
            )
            for row in data["objects"]
        ),
    )


__all__ = [
    "BOOTS",
    "OBJEXT",
    "SKIP",
    "Bootstrap",
    "Comparison",
    "Difference",
    "Objects",
    "Stage",
    "load",
]
