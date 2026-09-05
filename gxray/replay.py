"""A recorded debugger session, and a recorded bisection, played back out of the corpus.

    from gxray import replay

    cc1 = replay.load("cc1")
    print(cc1.transcript("stopping on the pass you care about"))
    cc1.find("pcfun").output          # what the compiler printed, that day, on that machine

    bisect = replay.load_bisect("counters")
    print(bisect.narrow().report())   # run the bisection again over the recorded trials

Why this exists. Everything else in this course is a compiler run the reader can repeat: a
dump, an assembly listing, a configure line. A debugger session is not. It needs a `cc1`
built with `-O0 -g3`, which is a three hundred megabyte binary and forty minutes of build on
a machine that has the memory for it, and it needs a `gdb`, which does not work on
aarch64-darwin at all. So the session is recorded once, with every command and every byte of
output kept, and the reader steps through the recording.

What that costs, said out loud. A recording is a transcript, not an oracle. If GCC renames
`execute_one_pass` the transcript will still show the old name working, and nothing here will
notice. That is the opposite of how the rest of the corpus behaves, and it is why the
session records `Session.gcc` and `Session.host` and why the lesson that reads it also reads
`BP-DEBUGGING`, whose section 2 is regenerated from the pinned tree on every build. The
prose is checked. The transcript is dated.

The bisection is the other half and it is not a transcript. `Bisect` carries every trial the
recorder ran, one per limit, and `narrow` is a real binary search over them. So the reader
watches a bisection converge on a single transformation using arithmetic that runs now, over
outcomes that a compiler produced then.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: Where the recorder puts both files, named after this module.
REPLAYS = Path(__file__).resolve().parent.parent / "corpora" / "replay"

#: What a played back session prints in front of a command, because that is what gdb prints.
PROMPT = "(gdb) "


@dataclass(frozen=True)
class Step:
    """One command that was typed, and everything the debugger printed after it."""

    #: Position in the session, from one. The number the lesson refers to.
    n: int

    #: The heading this step belongs under. A session is a walkthrough, not a log.
    group: str

    #: Exactly what was typed, with no prompt on the front.
    command: str

    #: Every byte gdb wrote between this command and the next one, trailing newline stripped.
    output: str

    #: One sentence on why this command is in the session at all.
    why: str

    @property
    def quiet(self) -> bool:
        """A command that printed nothing, which for `delete` and `set` is the normal case."""
        return not self.output.strip()

    def __str__(self) -> str:
        if self.quiet:
            return f"{PROMPT}{self.command}"
        return f"{PROMPT}{self.command}\n{self.output}"


@dataclass(frozen=True)
class Session:
    """One `gdb` process, from the banner to the kill, as it happened."""

    name: str

    #: The day it was recorded. A transcript has a date the way a photograph does.
    recorded: str

    #: The pinned tree the debugged compiler was built from.
    tag: str
    commit: str

    #: The machine, the gdb, and how the compiler under the debugger was configured. All
    #: three change what the reader would see, so all three are recorded rather than implied.
    host: str
    gdb: str
    configure: str

    #: The binary that was debugged and how big it came out, because the size is the reason
    #: this is a recording.
    binary: str
    bytes: int

    #: The program being compiled, by name and by content, so the reader can read the nine
    #: lines the whole session is about without leaving the notebook.
    program: str
    source: str

    #: The `cc1` command line, exactly as the driver would have run it.
    argv: tuple[str, ...]

    #: What gdb printed before the first command: its own banner, then everything `.gdbinit`
    #: caused. Kept because it is the evidence that the four breakpoints and the skip list in
    #: `BP-DEBUGGING` section 2 are not a reading of the source but a thing that happened.
    startup: str

    #: The same gdb, started once without `set auto-load safe-path /`, refusing to read the
    #: `.gdbinit` that configure wrote. The most common way a first session goes wrong.
    declined: str

    steps: tuple[Step, ...]

    def step(self, n: int) -> Step:
        for one in self.steps:
            if one.n == n:
                return one
        raise KeyError(f"no step {n} in the {self.name} session. It has {len(self.steps)}.")

    def find(self, command: str) -> Step:
        """The first step whose command starts with this text.

        Startswith rather than equality because the interesting commands carry long
        expressions, and a lesson should be able to ask for `pcfun` without quoting one.
        """
        for one in self.steps:
            if one.command.startswith(command):
                return one
        raise KeyError(
            f"nothing in the {self.name} session starts with {command!r}. "
            f"This is a recording, so a command that was not typed has no output."
        )

    @property
    def groups(self) -> tuple[str, ...]:
        """The headings, in the order they occur, each one once."""
        seen: list[str] = []
        for one in self.steps:
            if one.group not in seen:
                seen.append(one.group)
        return tuple(seen)

    def group(self, name: str) -> tuple[Step, ...]:
        got = tuple(one for one in self.steps if one.group == name)
        if not got:
            have = ", ".join(self.groups)
            raise KeyError(f"no group called {name!r} in the {self.name} session. Have: {have}")
        return got

    def transcript(self, group: str | None = None) -> str:
        """The session as it looked on the terminal, all of it or one heading of it."""
        steps = self.group(group) if group else self.steps
        return "\n".join(str(one) for one in steps)

    @property
    def megabytes(self) -> int:
        return round(self.bytes / 1_000_000)

    def __str__(self) -> str:
        return (
            f"{self.gdb} on {self.binary}, {self.megabytes} MB, {len(self.steps)} commands "
            f"in {len(self.groups)} groups, recorded {self.recorded} on {self.host}"
        )


@dataclass(frozen=True)
class Trial:
    """One compilation at one counter limit, and which output it produced."""

    #: The `N` in `-fdbg-cnt=name:N`, which means the closed range 1 to N.
    limit: int

    #: Index into `Bisect.variants`. Two compilations with the same index produced byte
    #: identical assembly, which is the only comparison a bisection makes.
    variant: int

    #: What the counter printed on stderr, which is how GCC tells you a limit was reached.
    stderr: str


@dataclass(frozen=True)
class Probe:
    """One question a bisection asked, and the answer the recording had for it."""

    limit: int
    good: bool

    #: The range still in play after this answer, as a closed interval.
    low: int
    high: int

    def __str__(self) -> str:
        verdict = "matches" if self.good else "differs"
        return f"-fdbg-cnt={{}}:{self.limit:<3} {verdict:<8} {self.low} to {self.high} left"


@dataclass(frozen=True)
class Narrowing:
    """A whole bisection: the probes it made and the number it ended on."""

    counter: str
    probes: tuple[Probe, ...]
    answer: int

    def report(self) -> str:
        lines = [str(p).format(self.counter) for p in self.probes]
        lines.append(f"transformation {self.answer} of the {self.counter} counter is the one")
        return "\n".join(lines)


@dataclass(frozen=True)
class Bisect:
    """Every compilation of one program at every limit of one debug counter."""

    name: str
    recorded: str
    tag: str
    commit: str
    host: str
    compiler: str

    #: The counter that was swept, and the flags every trial was compiled with.
    counter: str
    flags: tuple[str, ...]

    program: str
    source: str

    #: How many times the counter fired with no limit set, read out of `-fdbg-cnt-list`.
    total: int

    #: The distinct assembly outputs, in the order they were first seen. Variant zero is the
    #: unlimited compilation, so `variant == 0` means the limit changed nothing.
    variants: tuple[str, ...]

    trials: tuple[Trial, ...]

    #: The `-fdbg-cnt-list` table after one unlimited compilation, all seventy five rows.
    listing: str

    #: Where the debugger stopped when told to break on the one call that matters, innermost
    #: frame first. This is the answer the bisection is looking for, spelled out.
    culprit: tuple[str, ...]

    def trial(self, limit: int) -> Trial:
        for one in self.trials:
            if one.limit == limit:
                return one
        raise KeyError(
            f"no trial at limit {limit} for the {self.counter} counter. "
            f"The recording covers 0 to {self.trials[-1].limit}."
        )

    def good(self, limit: int) -> bool:
        """Did compiling with this limit produce the same code as compiling with no limit?"""
        return self.trial(limit).variant == 0

    @property
    def first_good(self) -> int:
        """The smallest limit that reproduces the unlimited output.

        Which is the transformation the bisection is hunting: allow this many and the code is
        right, allow one fewer and it is not.
        """
        for one in self.trials:
            if one.variant == 0:
                return one.limit
        raise ValueError(f"no limit reproduced the unlimited output of {self.counter}")

    @property
    def monotone(self) -> bool:
        """Is every limit above the first good one also good?

        A bisection is only valid if the answer is a step, and for a counter that gates one
        kind of transformation it usually is. It does not have to be, and a counter whose
        transformations interact will say false here, which is worth a reader knowing before
        they trust a bisection over four hundred trials they did not run.
        """
        after = [one.variant == 0 for one in self.trials if one.limit >= self.first_good]
        return all(after)

    def narrow(self) -> Narrowing:
        """Binary search the recorded trials the way a person would search real builds.

        This is arithmetic running now over outcomes recorded then. Nothing is compiled, and
        the answer has to come out equal to `first_good`, which is computed by looking at
        every trial rather than at a logarithmic handful of them.
        """
        low, high = 0, self.trials[-1].limit
        probes = []
        while low < high:
            mid = (low + high) // 2
            good = self.good(mid)
            if good:
                high = mid
            else:
                low = mid + 1
            probes.append(Probe(limit=mid, good=good, low=low, high=high))
        return Narrowing(counter=self.counter, probes=tuple(probes), answer=low)

    @property
    def messages(self) -> tuple[str, ...]:
        """The distinct stderr lines the counter produced across the whole sweep."""
        seen: list[str] = []
        for one in self.trials:
            for line in one.stderr.splitlines():
                if line and line not in seen:
                    seen.append(line)
        return tuple(seen)

    def __str__(self) -> str:
        return (
            f"{self.counter} fired {self.total} times on {self.program}, "
            f"{len(self.trials)} trials, {len(self.variants)} distinct outputs, "
            f"the first good limit is {self.first_good}"
        )


def _read(name: str) -> dict:
    path = REPLAYS / f"{name}.json"
    if not path.exists():
        have = ", ".join(sorted(p.stem for p in REPLAYS.glob("*.json"))) or "none"
        raise FileNotFoundError(f"no recording called {name!r} in {REPLAYS}. Have: {have}")
    return json.loads(path.read_text(encoding="utf-8"))


def load(name: str = "cc1") -> Session:
    """Read a recorded debugger session. This is the call a notebook makes."""
    data = _read(name)
    return Session(
        name=name,
        recorded=data["recorded"],
        tag=data["tag"],
        commit=data["commit"],
        host=data["host"],
        gdb=data["gdb"],
        configure=data["configure"],
        binary=data["binary"],
        bytes=data["bytes"],
        program=data["program"],
        source=data["source"],
        argv=tuple(data["argv"]),
        startup=data["startup"],
        declined=data["declined"],
        steps=tuple(
            Step(
                n=n,
                group=row["group"],
                command=row["command"],
                output=row["output"],
                why=row["why"],
            )
            for n, row in enumerate(data["steps"], start=1)
        ),
    )


def load_bisect(name: str = "counters") -> Bisect:
    """Read a recorded debug counter sweep."""
    data = _read(name)
    return Bisect(
        name=name,
        recorded=data["recorded"],
        tag=data["tag"],
        commit=data["commit"],
        host=data["host"],
        compiler=data["compiler"],
        counter=data["counter"],
        flags=tuple(data["flags"]),
        program=data["program"],
        source=data["source"],
        total=data["total"],
        variants=tuple(data["variants"]),
        trials=tuple(
            Trial(limit=row["limit"], variant=row["variant"], stderr=row["stderr"])
            for row in data["trials"]
        ),
        listing=data["listing"],
        culprit=tuple(data["culprit"]),
    )


__all__ = [
    "PROMPT",
    "REPLAYS",
    "Bisect",
    "Narrowing",
    "Probe",
    "Session",
    "Step",
    "Trial",
    "load",
    "load_bisect",
]
