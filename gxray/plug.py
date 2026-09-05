"""Read what `gxplug` emitted.

The plugin writes one JSON object per line, two per pass: a `pass-start` when the pass
manager is about to run it and a `pass-end` carrying the duration and the state the pass
left behind. `gxplug/README.md` describes the record; this module turns a stream of them
into something a widget can hold.

Why this exists when `gxray.passes` already reads `-fdump-passes`: that tells you which
passes GCC *knows about* and whether they are on. This tells you which ones actually ran,
on which function, in what order, and what changed. At `-O2` on `l1.c` the first is 395
lines and the second is a few hundred events of which most changed nothing, and the gap
between those two numbers is the point of T04.

Nothing here parses text. The plugin emits JSON precisely so that this file does not have
to be a parser, which is the rule in 03-architecture.md about preferring structured output
over scraping a dump.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

# GCC's IR property bits, from `gcc/tree-pass.h`. A record carries `properties` as a plain
# integer because that is what `cfun->curr_properties` is; naming the bits is this side's
# job.
#
# These are duplicated from a GCC header, which is normally how a project goes stale. It is
# safe here only because `test_plug.py` reads `vendor/gcc/gcc/tree-pass.h` at the pinned tag
# and fails if this table and that header disagree, on any bit, in either direction.
PROPERTIES: dict[str, int] = {
    "gimple_any": 1 << 0,
    "gimple_lcf": 1 << 1,
    "gimple_leh": 1 << 2,
    "cfg": 1 << 3,
    "objsz": 1 << 4,
    "ssa": 1 << 5,
    "no_crit_edges": 1 << 6,
    "rtl": 1 << 7,
    "gimple_lomp": 1 << 8,
    "cfglayout": 1 << 9,
    "gimple_lcx": 1 << 10,
    "loops": 1 << 11,
    "gimple_lvec": 1 << 12,
    "gimple_eomp": 1 << 13,
    "gimple_lva": 1 << 14,
    "gimple_opt_math": 1 << 15,
    "gimple_lomp_dev": 1 << 16,
    "rtl_split_insns": 1 << 17,
    "loop_opts_done": 1 << 18,
    "assumptions_done": 1 << 19,
    "gimple_lbitint": 1 << 20,
    "last_full_fold": 1 << 21,
}


def property_names(bits: int | None) -> list[str]:
    """The properties set in `bits`, in bit order.

    An unknown bit is reported as `bit23` rather than dropped. A newer GCC adding a
    property should show up as something a reader can see and ask about, not as silence.
    """
    if bits is None:
        return []
    named = {value: name for name, value in PROPERTIES.items()}
    out = []
    for i in range(bits.bit_length()):
        bit = 1 << i
        if bits & bit:
            out.append(named.get(bit, f"bit{i}"))
    return out


@dataclass(frozen=True)
class Event:
    """One line of the stream."""

    seq: int
    event: str
    pass_name: str | None
    pass_number: int
    function: str | None
    properties: int | None
    statements: int | None
    insns: int | None
    blocks: int | None
    seconds: float | None

    @property
    def property_names(self) -> list[str]:
        return property_names(self.properties)

    @property
    def size(self) -> int | None:
        """Statements before the function becomes RTL, insns after.

        A pass tape wants one number per cell and does not care which side of `expand` it
        is on, but it must not pretend a GIMPLE statement and an RTL insn are the same
        unit. They are not, and the jump at `expand` is real and worth seeing.
        """
        return self.statements if self.statements is not None else self.insns


@dataclass(frozen=True)
class Run:
    """A pass that ran: its start event, its end event, and what happened in between."""

    name: str | None
    number: int
    function: str | None
    start: Event
    end: Event | None

    @property
    def seconds(self) -> float | None:
        return self.end.seconds if self.end else None

    @property
    def changed(self) -> bool:
        """Did anything measurable change?

        Deliberately narrow: this is size and properties, not semantics. A pass that
        rewrote an expression without changing the statement count reports False, and the
        prose has to say so rather than letting a reader infer that most passes do
        nothing. What it is good for is the honest ratio in T04: how many passes ran, and
        how many left a mark you can see from outside.
        """
        if self.end is None:
            return False
        return (
            self.start.statements != self.end.statements
            or self.start.insns != self.end.insns
            or self.start.blocks != self.end.blocks
            or self.start.properties != self.end.properties
        )


@dataclass
class Stream:
    """Every event from one compilation, and the runs assembled out of them."""

    events: list[Event] = field(default_factory=list)

    @property
    def runs(self) -> list[Run]:
        """Pair each `pass-start` with the `pass-end` that follows it.

        The plugin guarantees the two alternate, because it closes the open pass before
        opening another and closes the last one at `PLUGIN_ALL_PASSES_END`. A start with
        no end still becomes a `Run` with `end=None` rather than being dropped: it means
        the compilation died in that pass, which is the single most interesting thing the
        stream can tell you.
        """
        out: list[Run] = []
        open_start: Event | None = None
        for event in self.events:
            if event.event == "pass-start":
                if open_start is not None:
                    out.append(
                        Run(
                            open_start.pass_name,
                            open_start.pass_number,
                            open_start.function,
                            open_start,
                            None,
                        )
                    )
                open_start = event
            elif event.event == "pass-end" and open_start is not None:
                out.append(
                    Run(
                        open_start.pass_name,
                        open_start.pass_number,
                        open_start.function,
                        open_start,
                        event,
                    )
                )
                open_start = None
        if open_start is not None:
            out.append(
                Run(
                    open_start.pass_name,
                    open_start.pass_number,
                    open_start.function,
                    open_start,
                    None,
                )
            )
        return out

    @property
    def functions(self) -> list[str]:
        """Every function named in the stream, in the order it first appears."""
        seen: dict[str, None] = {}
        for event in self.events:
            if event.function is not None:
                seen.setdefault(event.function, None)
        return list(seen)

    def for_function(self, name: str) -> Stream:
        return Stream([e for e in self.events if e.function == name])

    @property
    def seconds(self) -> float:
        return sum(e.seconds for e in self.events if e.seconds is not None)


def _event(record: dict) -> Event:
    """One record to one Event, tolerating fields we do not know about.

    A newer plugin adding a key must not break an older reader, so unknown keys are
    ignored rather than rejected. A missing key is a different matter and raises, because
    that means the two really are out of step.
    """
    try:
        return Event(
            seq=record["seq"],
            event=record["event"],
            pass_name=record["pass"],
            pass_number=record["pass_number"],
            function=record["function"],
            properties=record["properties"],
            statements=record["statements"],
            insns=record["insns"],
            blocks=record["blocks"],
            seconds=record["seconds"],
        )
    except KeyError as exc:
        raise ValueError(f"gxplug record is missing {exc.args[0]}: {record!r}") from exc


def parse_lines(lines: Iterable[str]) -> Iterator[Event]:
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"gxplug line {number} is not JSON: {line!r}") from exc
        yield _event(record)


def parse(text: str) -> Stream:
    return Stream(list(parse_lines(text.splitlines())))


def load(path: str | Path) -> Stream:
    return parse(Path(path).read_text(encoding="utf-8"))
