"""How much of the corpus the dump parsers actually understand, written down and watched.

Both parsers in `gxray` are built to tolerate the unknown rather than throw. A GIMPLE
statement the classifier does not recognise becomes an `UnparsedStmt` carrying its text, and
an RTL list that does not come out as an insn is skipped. That is the right behaviour for a
book, because a dump format that shifts by one field should cost one number in one lesson
instead of breaking forty lessons at once. It is also a way to be quietly wrong forever, so
something has to count what got tolerated.

This module is that counter. It reads every dump in the corpus with the parser the dump's
name calls for, and records four numbers per dump.

`functions` is how many functions the parser found. `items` is how many things it built,
statements and PHIs for GIMPLE and insns for RTL. `missed` is how many it should have built
and did not, an `UnparsedStmt` for GIMPLE and a list with an insn code at the front that did
not become an `Insn` for RTL. `unread` is input the parser walked past, a non blank line
that landed nowhere for GIMPLE and a top level list that is not an insn for RTL.

`missed` is the number the milestone asks about and it is zero everywhere today. `unread` is
not zero and is not supposed to be, because a dump is mostly prose. The IRA report alone is
twenty five thousand parenthesised lines of conflict tables. What matters is that both
numbers are recorded and neither moves without somebody looking.

The baseline is committed next to this file. Re-recording it is `just dumpparse-record`, and
the diff goes in a pull request, so a parser change that loses ground has to be argued for
rather than merged by accident.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from gxray import corpus_store, gimple, rtl

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).resolve().parent / "baseline.json"

#: Dump name prefixes and the parser each one wants. A GENERIC dump, a dot file and the
#: debug info dumps all arrive under `tree-`, and the GIMPLE reader is the one that copes
#: with them, so the routing is by prefix and the reader does the rest.
PARSERS = {"rtl-": "rtl"}
DEFAULT_PARSER = "gimple"


class DumpParseError(RuntimeError):
    """Raised when the baseline and the corpus disagree."""


@dataclass(frozen=True)
class Reading:
    """What one parser made of one dump."""

    entry: str
    dump: str
    parser: str
    functions: int
    items: int
    missed: int
    unread: int

    @property
    def id(self) -> str:
        return f"{self.entry}/{self.dump}"

    @property
    def counts(self) -> dict[str, int]:
        return {k: v for k, v in asdict(self).items() if isinstance(v, int)}


def parser_for(dump: str) -> str:
    for prefix, name in PARSERS.items():
        if dump.startswith(prefix):
            return name
    return DEFAULT_PARSER


def read(entry: str, dump: str, text: str) -> Reading:
    """Parse one dump and count what came out."""
    which = parser_for(dump)
    if which == "rtl":
        parsed = rtl.parse(text, dump)
        return Reading(
            entry=entry,
            dump=dump,
            parser=which,
            functions=len(parsed.functions),
            items=sum(len(listing.insns) for listing in parsed.functions.values()),
            missed=len(parsed.missed),
            unread=parsed.unread,
        )

    parsed = gimple.parse(text, dump)
    return Reading(
        entry=entry,
        dump=dump,
        parser=which,
        functions=len(parsed.functions),
        items=sum(
            len(f.stmts) + sum(len(b.phis) for b in f.blocks.values())
            for f in parsed.functions.values()
        ),
        missed=len(parsed.unparsed),
        # A line starting with `;;` is a comment the dump prints for a human and is never a
        # statement, so counting it as input the parser lost track of would bury the lines
        # that really are lost in fourteen hundred that never could have been kept.
        unread=sum(1 for line in parsed.dropped if not line.startswith(";;")),
    )


def readings(entries: list[str] | None = None) -> list[Reading]:
    """Every dump in the corpus, parsed. Around three hundred of them, and it takes seconds."""
    found = []
    for entry in sorted(entries if entries is not None else corpus_store.entries()):
        record = corpus_store.load(entry)
        for dump, text in sorted(record.dump_texts.items()):
            found.append(read(entry, dump, text))
    return found


def totals(found: list[Reading]) -> dict[str, int]:
    keys = ("functions", "items", "missed", "unread")
    out = {"dumps": len(found)}
    out.update({k: sum(r.counts[k] for r in found) for k in keys})
    return out


def snapshot(found: list[Reading]) -> dict:
    return {
        "totals": totals(found),
        "dumps": {r.id: {"parser": r.parser, **r.counts} for r in found},
    }


def save(found: list[Reading], path: Path | None = None) -> Path:
    path = Path(path or BASELINE)
    path.write_text(json.dumps(snapshot(found), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load(path: Path | None = None) -> dict:
    path = Path(path or BASELINE)
    if not path.exists():
        raise DumpParseError(f"no baseline at {path}. Run `just dumpparse-record` and commit it.")
    return json.loads(path.read_text(encoding="utf-8"))


def compare(found: list[Reading], baseline: dict) -> list[str]:
    """What changed since the baseline was recorded, in the order a reader wants it.

    A rise in `missed` comes first and says so plainly, because it is the one failure that
    means the parser has stopped understanding something it used to understand. Everything
    else is a number that moved, which is usually a corpus entry being re-recorded and is
    always something to look at before re-recording the baseline.
    """
    was = baseline.get("dumps", {})
    now = {r.id: r for r in found}
    problems = []

    for key in sorted(set(now) - set(was)):
        problems.append(f"{key} is in the corpus and not in the baseline")
    for key in sorted(set(was) - set(now)):
        problems.append(f"{key} is in the baseline and not in the corpus")

    for key in sorted(set(now) & set(was)):
        reading, before = now[key], was[key]
        if reading.parser != before.get("parser"):
            problems.append(
                f"{key} is read by the {reading.parser} parser now and by the "
                f"{before.get('parser')} parser in the baseline"
            )
        missed = reading.missed - before.get("missed", 0)
        if missed > 0:
            problems.append(
                f"{key} has {reading.missed} things the parser could not read, up from "
                f"{before['missed']}. Something in this dump changed shape."
            )
        for field_name in ("functions", "items", "unread", "missed"):
            new, old = reading.counts[field_name], before.get(field_name)
            if new != old and not (field_name == "missed" and missed > 0):
                problems.append(f"{key} {field_name} is {new} and the baseline says {old}")

    return problems


def check(path: Path | None = None) -> list[str]:
    return compare(readings(), load(path))
