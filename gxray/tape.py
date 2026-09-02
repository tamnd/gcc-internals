"""The pipeline with the dumps lined up against it.

One cell per pass that is on, in order, with what the function looked like after it when
there is a dump to look at. This is the model behind the Pass Tape, and it lives here rather
than in the widget because the animation draws the same tape and the two of them agreeing
cannot be left to whoever edits one of them next.

A pass is marked as having changed the IR only when there is a dump on both sides of it.
GCC writes a dump for a pass only when that pass has one and it ran for this function, so
most cells have no evidence either way and say so. That is a third state and not a missing
feature, and every drawing of this data has to have somewhere to put it.
"""

from __future__ import annotations

from dataclasses import dataclass

from gxray.gimple import Function, Stmt
from gxray.passes import Pipeline


@dataclass
class Cell:
    """One pass, and what the IR looked like on the far side of it."""

    index: int
    name: str
    short: str
    phase: str | None
    depth: int
    dump_key: str | None
    changed: bool | None = None
    stats: dict[str, int] | None = None

    @property
    def label(self) -> str:
        counts = ""
        if self.stats:
            # Spelled out rather than formatted with an s on the end, because the first cell
            # on the tape has one basic block and `1 blocks` in a lesson reads as a bug.
            blocks = self.stats["blocks"]
            counts = f", {self.stats['statements']} statements, {blocks} block"
            counts += "" if blocks == 1 else "s"
        state = {
            True: "changed the IR",
            False: "left the IR alone",
            None: "nothing recorded to compare",
        }
        phase = f"{self.phase} pass" if self.phase else "pass"
        return f"{self.index + 1}. {self.name}, {phase}, {state[self.changed]}{counts}"


def fingerprint(f: Function) -> tuple[str, ...]:
    """What counts as the IR being the same, for the purpose of marking a cell.

    Statement text in block order. Not the dump text, which carries the pass name and a
    header full of things that differ between two dumps of an identical function.

    Debug markers are left out. They move whenever a statement moves, so counting them
    would mark almost every pass as having changed something and the tape would be a solid
    block of colour saying nothing.
    """
    return tuple(
        line
        for b in f.ordered_blocks
        for line in [
            f"<bb {b.index}>",
            *[str(p) for p in b.phis],
            *[s.text for s in b.stmts if not s.is_debug],
        ]
    )


def code_in(f: Function) -> list[Stmt]:
    return [s for b in f.ordered_blocks for s in b.stmts if not s.is_debug]


def measure(f: Function) -> dict[str, int]:
    """The three numbers the sparkline under the tape moves: statements, blocks, names."""
    code = code_in(f)
    names = {str(n) for s in code for n in s.operands}
    names |= {str(s.lhs) for s in code if s.lhs is not None}
    names |= {str(p.lhs) for b in f.ordered_blocks for p in b.phis}
    return {
        "statements": len(code),
        "blocks": len(f.blocks),
        "names": len([n for n in names if "_" in n]),
    }


def cells(pipeline: Pipeline, dumps: dict[str, Function] | None = None) -> list[Cell]:
    """Every enabled pass as a cell, with the ones that have a dump measured and compared."""
    dumps = dumps or {}
    out: list[Cell] = []
    previous: tuple[str, ...] | None = None
    for i, p in enumerate(pipeline.enabled):
        cell = Cell(
            index=i,
            name=p.name,
            short=p.short_name,
            phase=p.phase,
            depth=p.depth,
            dump_key=p.dump_key,
        )
        f = dumps.get(p.dump_key or "")
        if f is not None:
            current = fingerprint(f)
            cell.changed = None if previous is None else current != previous
            cell.stats = measure(f)
            previous = current
        out.append(cell)
    return out
