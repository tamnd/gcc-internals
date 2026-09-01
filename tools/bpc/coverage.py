"""The coverage ledger.

GCC has 395 passes at `-O2` and 47 GIMPLE statement codes, and a course cannot teach all of
either. Every course about a large system quietly picks a subset and lets the reader assume
it was the whole thing. This one states the subset as a number.

Every item in every inventory is classified as one of three things:

    covered        a lesson or a blueprint explains it
    mentioned      it is named where it is relevant, without being explained
    out of scope   it is deliberately not covered, with a reason

Nothing may be unclassified, and `bpc coverage` fails when something is. The inventory
itself is read from the pinned tree rather than typed into the ledger, so adding a GIMPLE
code to GCC turns the build red until somebody says what the book does about it. That is
the entire mechanism, and it is worth more than any amount of intending to keep up.

The ledger is rules rather than a line per item, because a rule survives a version bump and
a list does not. A rule matches by prefix, and the first rule that matches an item wins:

    [[inventory.rule]]
    match = "GIMPLE_OMP_*"
    status = "out of scope"
    why = "OpenMP lowering is its own subsystem and its own book."
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from tools.bpc import BLUEPRINTS, GCC_ROOT, BpcError
from tools.bpc.gccsrc import parse_def, read

LEDGER = BLUEPRINTS / "coverage.toml"
STATUSES = ("covered", "mentioned", "out of scope")


@dataclass
class Rule:
    match: str
    status: str
    why: str = ""


@dataclass
class Inventory:
    """One list of things the book could cover, and what it does about each of them."""

    name: str
    what: str
    source: str
    macro: str
    rules: list[Rule] = field(default_factory=list)

    def items(self, root: Path) -> list[str]:
        return [e.name for e in parse_def(read(root / self.source_name), self.macro)]

    @property
    def source_name(self) -> str:
        return self.source.removeprefix("gcc/")

    def classify(self, item: str) -> Rule | None:
        for rule in self.rules:
            if fnmatch.fnmatchcase(item, rule.match):
                return rule
        return None


def load(path: Path | None = None) -> list[Inventory]:
    path = path or LEDGER
    if not path.is_file():
        raise BpcError(f"there is no coverage ledger at {path}")
    body = tomllib.loads(path.read_text(encoding="utf-8"))

    inventories = []
    for name, entry in body.get("inventory", {}).items():
        rules = [
            Rule(match=r["match"], status=r["status"], why=r.get("why", ""))
            for r in entry.get("rule", [])
        ]
        for rule in rules:
            if rule.status not in STATUSES:
                raise BpcError(
                    f"{path}: rule {rule.match!r} has status {rule.status!r}, "
                    f"which is not one of {STATUSES}"
                )
            if rule.status == "out of scope" and not rule.why:
                raise BpcError(
                    f"{path}: rule {rule.match!r} puts something out of scope without saying "
                    f"why. A reason is the only thing that makes an exclusion honest."
                )
        inventories.append(
            Inventory(
                name=name,
                what=entry["what"],
                source=entry["source"],
                macro=entry["macro"],
                rules=rules,
            )
        )
    return inventories


@dataclass
class Report:
    inventory: Inventory
    counts: dict[str, int]
    unclassified: list[str]

    @property
    def total(self) -> int:
        return sum(self.counts.values()) + len(self.unclassified)

    def line(self) -> str:
        parts = ", ".join(f"{self.counts.get(s, 0)} {s}" for s in STATUSES)
        return f"{self.inventory.name}: {self.total} items, {parts}"


def report(root: Path | None = None, path: Path | None = None) -> list[Report]:
    root = root or GCC_ROOT
    out = []
    for inv in load(path):
        counts: dict[str, int] = {}
        unclassified = []
        for item in inv.items(root):
            rule = inv.classify(item)
            if rule is None:
                unclassified.append(item)
            else:
                counts[rule.status] = counts.get(rule.status, 0) + 1
        out.append(Report(inventory=inv, counts=counts, unclassified=unclassified))
    return out


def problems(root: Path | None = None, path: Path | None = None) -> list[str]:
    out = []
    for r in report(root, path):
        for item in r.unclassified:
            out.append(
                f"{r.inventory.name}: {item} is in {r.inventory.source} and the ledger says "
                f"nothing about it. Add a rule to {LEDGER.name} saying covered, mentioned, "
                f"or out of scope with a reason."
            )
    return out
