"""Two dumps of one function, lined up so that what is left is the transformation.

Reading two dumps side by side by eye does not work past about twenty lines, and the reason
is not the length. Most of what differs between two GIMPLE dumps is not the pass. SSA names
are renumbered whenever anything is created or removed, branch probabilities are reprinted in
a different form once the profile is guessed, and a recording taken with `-g` carries a debug
marker for every statement. A reader who diffs the raw text gets a wall of red and green with
the one line that matters somewhere inside it.

So the lines are normalized before they are compared, and shown unnormalized afterwards. The
normalized text decides which line goes next to which; the real text is what the reader sees.
A line whose normalized text is the same on both sides but whose real text is not gets its
own answer, `renumbered`, because "the numbers in it moved" and "it is a different statement"
are different things and a diff that calls both of them a change is the wall of red again.

What gets compared is `tape.fingerprint`, the same view of a function the Pass Tape uses to
decide whether a pass changed anything. That is deliberate: if the tape says a pass left the
IR alone then the diff either finds nothing or the two disagree, and there is a test for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from gxray.gimple import Function
from gxray.locs import strip_locs
from gxray.tape import fingerprint

#: A profile annotation at the end of a line. GCC prints `[INV]` before the profile is
#: guessed and a percentage or a count afterwards, so the same `goto` is written three
#: different ways over the course of a compilation without the branch ever moving.
PROFILE = re.compile(r"\s*\[(?:INV|\d+(?:\.\d+)?%|(?:local )?count: \d+)\]\s*$")

#: An SSA version number. The name in front of it can be empty, because GCC writes an
#: anonymous temporary as `_6`, and it can have dots in it, because it writes a name the
#: loop optimizer invented as `ivtmp.7_3`. The block numbers in a PHI, `s_3(2)`, are left
#: alone on purpose: a PHI argument arriving from a different block is a real change.
VERSION = re.compile(r"(?<![A-Za-z0-9_.])((?:[A-Za-z.][A-Za-z0-9_.]*)?_)\d+\b")

#: The four things a row of the diff can be. These are palette roles, so the marker and the
#: colour for each of them are already decided and are the same here as everywhere else.
ROLES = ("neutral", "added", "removed", "changed")


def normalize(line: str) -> str:
    """The line with everything that changes for reasons that are not the transformation.

    Source locations, the profile annotation on a branch, and the version number on every
    SSA name. What is left is the shape of the statement, which is the thing worth lining up
    two dumps by.

    This is a claim about the text and not about the meaning. `s_3` and `s_9` normalize to
    the same thing whether the second one is the first one renumbered or a different value
    entirely, and only the reader looking at both real lines can tell which. The wording
    everywhere downstream says the numbers moved, never that the statement is the same.
    """
    return VERSION.sub(r"\1#", PROFILE.sub("", strip_locs(line)))


@dataclass(frozen=True)
class Row:
    """One line of the comparison, on one or both sides."""

    role: str
    before: str = ""
    after: str = ""
    before_line: int | None = None
    after_line: int | None = None

    @property
    def renumbered(self) -> bool:
        """The two sides say the same thing once the numbers come off."""
        return self.role == "changed" and normalize(self.before) == normalize(self.after)

    @property
    def text(self) -> str:
        """The side worth reading, which for anything that survived is the later one."""
        return self.after or self.before

    @property
    def label(self) -> str:
        """What a screen reader hears on this row."""
        if self.role == "added":
            return f"added, {self.after}"
        if self.role == "removed":
            return f"removed, {self.before}"
        if self.role == "changed":
            what = "renumbered" if self.renumbered else "changed"
            return f"{what}, was {self.before}, now {self.after}"
        return f"unchanged, {self.after}"


@dataclass(frozen=True)
class Diff:
    """Two functions, lined up, with a row for every line on either side."""

    rows: tuple[Row, ...]
    before_name: str = "before"
    after_name: str = "after"

    def of(self, role: str) -> list[Row]:
        return [r for r in self.rows if r.role == role]

    @property
    def renumbered(self) -> list[Row]:
        return [r for r in self.rows if r.renumbered]

    @property
    def moved(self) -> list[Row]:
        """Every row the reader has a reason to look at."""
        return [r for r in self.rows if r.role != "neutral"]

    @property
    def counts(self) -> dict[str, int]:
        return {role: len(self.of(role)) for role in ROLES}

    def __bool__(self) -> bool:
        return bool(self.moved)

    def __str__(self) -> str:
        c = self.counts
        return (
            f"{self.before_name} to {self.after_name}: {c['added']} added, "
            f"{c['removed']} removed, {c['changed']} changed"
        )


def pair(before: list[str], after: list[str], at: int, to: int) -> list[Row]:
    """One run of lines that were replaced, laid out two abreast.

    Two lines end up on the same row because they are in the same place in the run, not
    because they are the same statement. Nothing here can tell those apart, and pretending
    otherwise would be the kind of confident wrong answer the whole project is against. What
    makes the row readable is that both real lines are on it, side by side, for the reader to
    judge. When one side of the run is longer, the surplus is what it looks like.
    """
    rows = []
    for n in range(max(len(before), len(after))):
        old = before[n] if n < len(before) else ""
        new = after[n] if n < len(after) else ""
        if not new:
            rows.append(Row("removed", before=old, before_line=at + n))
        elif not old:
            rows.append(Row("added", after=new, after_line=to + n))
        else:
            rows.append(
                Row("changed", before=old, after=new, before_line=at + n, after_line=to + n)
            )
    return rows


def compare(before: Function, after: Function, **names: str) -> Diff:
    """Line the two dumps up.

    The lines are matched on their normalized text and shown as they were written. A pair
    that matched but does not read the same is a change, and `Row.renumbered` is how the
    reader is told which kind.
    """
    old, new = list(fingerprint(before)), list(fingerprint(after))
    keys = ([normalize(line) for line in old], [normalize(line) for line in new])
    rows: list[Row] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, *keys, autojunk=False).get_opcodes():
        if tag == "equal":
            for n in range(i2 - i1):
                a, b = old[i1 + n], new[j1 + n]
                rows.append(
                    Row(
                        role="neutral" if a == b else "changed",
                        before=a,
                        after=b,
                        before_line=i1 + n,
                        after_line=j1 + n,
                    )
                )
        elif tag == "delete":
            rows += [Row("removed", before=old[n], before_line=n) for n in range(i1, i2)]
        elif tag == "insert":
            rows += [Row("added", after=new[n], after_line=n) for n in range(j1, j2)]
        else:
            rows += pair(old[i1:i2], new[j1:j2], i1, j1)
    return Diff(rows=tuple(rows), **names)
