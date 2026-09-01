"""The pass pipeline, read out of GCC rather than out of a book.

`gcc-16 -fdump-passes` prints every pass it knows about, nested, with whether it is on for
the current options:

       tree-cfg                                            :  ON
       *warn_function_return                               :  ON
       ipa-build_ssa_passes                                :  ON
          tree-fixup_cfg1                                  :  ON
          tree-ssa                                         :  ON

Indentation is nesting. A leading `*` means the pass has no dump file of its own. The
prefix before the first dash is the phase, so `tree-ssa` is a tree pass and `rtl-final` is
an RTL pass, and a name with no such prefix belongs to no phase.

This is the data behind the Pass Tape. On Homebrew GCC 16.2.0 at `-O2` for
`corpora/programs/l1.c` it is 395 lines, which is where the 395 in the prose comes from.
Nothing hand counts it.

Four of those 395 lines do not look like the rest. Two passes have a space in the name,
`rtl-rtl pre` and `rtl-no-opt dfinit`, and two print as `(null)`, which is what GCC shows
for a pass whose name was never set. They are kept rather than skipped, because the count
is quoted in the book and a parser that silently drops the awkward cases is a parser that
quietly makes the book wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A pass name is not an identifier. Two of them contain a space at -O2, `rtl-rtl pre`
# and `rtl-no-opt dfinit`, and two of them are literally `(null)`, which is GCC printing
# a pass that never got a name. So the name is everything up to the trailing colon
# rather than a character class, and `(null)` is kept rather than dropped, because a
# pass tape that quietly loses four cells is worse than one that shows an unnamed pass.
PASS_LINE = re.compile(r"^(?P<indent>\s*)(?P<star>\*?)(?P<name>\S.*?)\s*:\s+(?P<state>ON|OFF)\s*$")
PHASES = ("tree", "rtl", "ipa")
INDENT_STEP = 3


@dataclass
class Pass:
    """One entry in the pass pipeline."""

    name: str
    enabled: bool
    depth: int
    has_dump: bool = True
    children: list[Pass] = field(default_factory=list)

    @property
    def named(self) -> bool:
        """False for the two passes GCC prints as `(null)`."""
        return self.name != "(null)"

    @property
    def phase(self) -> str | None:
        """tree, rtl, ipa, or None for a pass that belongs to no phase."""
        head = self.name.split("-", 1)[0]
        return head if head in PHASES else None

    @property
    def short_name(self) -> str:
        """The name without its phase prefix, which is what the dump file is called.

        A pass name may carry a disambiguating prefix, a space, and then the dump name.
        GCC keeps only the part after the space when it names the dump file, so `rtl pre`
        is dumped as `rtl-pre` and not as `rtl-rtl pre`, and the same for `no-opt dfinit`.
        See `gcc/passes.cc:855@releases/gcc-16.2.0`.
        """
        body = self.name.split("-", 1)[1] if self.phase else self.name
        return body.split(" ", 1)[1] if " " in body else body

    @property
    def dump_key(self) -> str | None:
        """How to ask for this pass's dump, or None if the pass has no dump at all.

        This is the name of a dump, not a promise that a file exists. `-fdump-passes`
        reports whether the gate is open, and a pass whose gate is open can still write
        nothing for a given function. At `-O2` on `l1.c` there is a `tree-ch2` and no
        `tree-ch1`, a `tree-fre1`, `fre3` and `fre5` and no `fre2` or `fre4`. Roughly
        thirty enabled passes produce no file, which is a fact about GCC and not a gap
        in this parser.
        """
        return f"{self.phase}-{self.short_name}" if (self.has_dump and self.phase) else None

    def walk(self):
        """This pass and everything nested inside it, in pipeline order."""
        yield self
        for child in self.children:
            yield from child.walk()

    def __str__(self) -> str:
        return self.name


@dataclass
class Pipeline:
    """Every pass GCC knows about, for one set of options."""

    roots: list[Pass] = field(default_factory=list)

    @property
    def all(self) -> list[Pass]:
        return [p for r in self.roots for p in r.walk()]

    @property
    def enabled(self) -> list[Pass]:
        return [p for p in self.all if p.enabled]

    def by_phase(self, phase: str) -> list[Pass]:
        return [p for p in self.all if p.phase == phase]

    def find(self, name: str) -> Pass | None:
        """Look a pass up by full name, or by short name if that is unambiguous."""
        for p in self.all:
            if p.name == name:
                return p
        matches = [p for p in self.all if p.short_name == name]
        return matches[0] if len(matches) == 1 else None

    def counts(self) -> dict[str, int]:
        """The numbers the prose quotes, so that no lesson has to type one in."""
        return {
            "total": len(self.all),
            "enabled": len(self.enabled),
            "tree": len(self.by_phase("tree")),
            "rtl": len(self.by_phase("rtl")),
            "ipa": len(self.by_phase("ipa")),
            "with_dump": len([p for p in self.all if p.has_dump]),
            "unnamed": len([p for p in self.all if not p.named]),
        }

    def __str__(self) -> str:
        c = self.counts()
        return f"{c['total']} passes, {c['enabled']} on"


def parse(text: str) -> Pipeline:
    """Parse `-fdump-passes` output. Lines that are not pass entries are ignored."""
    pipeline = Pipeline()
    stack: list[Pass] = []

    for raw in text.splitlines():
        m = PASS_LINE.match(raw)
        if not m:
            continue

        depth = len(m.group("indent")) // INDENT_STEP
        node = Pass(
            name=m.group("name"),
            enabled=m.group("state") == "ON",
            depth=depth,
            has_dump=not m.group("star"),
        )

        while stack and stack[-1].depth >= depth:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            pipeline.roots.append(node)
        stack.append(node)

    return pipeline
