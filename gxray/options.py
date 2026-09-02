"""The optimizer flag table, read out of GCC rather than out of the manual.

`gcc-16 -Q --help=optimizers -O2` prints every option GCC considers an optimization, and
next to each one the value it would have if you compiled with those flags:

    The following options control optimizations:
      -faggressive-loop-optimizations 	[enabled]
      -falign-functions           		[enabled]
      -falign-functions=          		32:16
      -fallow-store-data-races    		[disabled]
      -fexcess-precision=[fast|standard|16] 	[default]

Three shapes of line hide in there and telling them apart is most of the work. A plain
switch reads `[enabled]` or `[disabled]`. An option that takes a value prints the value,
and the name it prints ends in `=` so it is a different entry from the switch of nearly
the same name. And a few print something that is neither, `[default]` when nothing has set
them, an alias when one option is a spelling of another, or `[available in C++, ObjC++]`
when the option exists but not for the language being compiled.

Only the first shape can be diffed by asking whether it flipped, and a lesson that counts
only the flips is a lesson that misses two of the five things `-O2` does to `-O1`. So the
value lines are kept and compared as text, and `diff` says which kind of change each one
was rather than reducing everything to on and off.

`--help=params` prints in the same format and parses with the same code, which is the
reason `kind` is a field rather than two modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The order to show the levels in. Not alphabetical, not the order the recorder happened to
# run them in, and not one anything in GCC cares about. It puts -O0 to -O3 first because those
# four really are a staircase and reading them in a row is what makes the next four look odd.
LEVELS = ("-O0", "-O1", "-O2", "-O3", "-Os", "-Oz", "-Og", "-Ofast")

# What GCC prints for a switch, as opposed to a value.
ENABLED = "[enabled]"
DISABLED = "[disabled]"

# Where a metavariable starts inside the printed name. `-flifetime-dse=<0,2>` prints the
# range it accepts and `-fira-region=[one|all|mixed]` prints the words it accepts, and in
# both cases the option is called the part in front.
METAS = ("[", "<")


@dataclass(frozen=True)
class Option:
    """One line of the table.

    `name` keeps a trailing `=` when the printed name had one, because `-falign-functions`
    and `-falign-functions=` are two separate lines with two separate values and merging
    them loses the fact that `-O2` sets both.
    """

    name: str
    meta: str = ""
    value: str = ""

    @property
    def boolean(self) -> bool:
        return self.value in (ENABLED, DISABLED)

    @property
    def on(self) -> bool | None:
        """True or False for a switch, None for anything that is not one.

        None rather than False, because `-fexcess-precision=` printing `[default]` is not
        the same fact as a switch being off and code that treats it as one will say `-O2`
        turned something off that `-O2` never touched.
        """
        return None if not self.boolean else self.value == ENABLED

    @property
    def param(self) -> bool:
        return self.name.startswith("--param")

    @property
    def target(self) -> bool:
        """True for a `-m` option, which exists only on the target that printed the table."""
        return self.name.startswith("-m")

    def __str__(self) -> str:
        shown = self.value or "nothing"
        return f"{self.name}{self.meta} is {shown}"


@dataclass
class Table:
    """One printing of one help category at one set of flags."""

    kind: str = ""
    flags: str = ""
    options: dict[str, Option] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.options)

    def __contains__(self, name: str) -> bool:
        return name in self.options

    def __getitem__(self, name: str) -> Option:
        if name not in self.options:
            raise KeyError(f"no option {name!r} in the {self.kind} table for {self.flags!r}")
        return self.options[name]

    @property
    def booleans(self) -> list[Option]:
        return [o for o in self.options.values() if o.boolean]

    @property
    def enabled(self) -> list[Option]:
        return [o for o in self.options.values() if o.on]

    @property
    def valued(self) -> list[Option]:
        """The lines that are neither a switch nor a param. Options that take a value."""
        return [o for o in self.options.values() if not o.boolean and not o.param]

    @property
    def params(self) -> list[Option]:
        return [o for o in self.options.values() if o.param]

    def __str__(self) -> str:
        return f"{self.kind} at {self.flags}: {len(self)} options, {len(self.enabled)} enabled"


def parse(text: str, kind: str = "", flags: str = "") -> Table:
    """Read what `-Q --help=` printed.

    Everything that is not an option line is dropped, which is the banner at the top and
    any blank lines. An option line is recognised by starting with a dash after the
    indent, and nothing else in the output does.
    """
    table = Table(kind=kind, flags=flags)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        parts = stripped.split(None, 1)
        printed = parts[0]
        value = parts[1].strip() if len(parts) > 1 else ""
        cut = min((printed.find(m) for m in METAS if m in printed), default=-1)
        name, meta = (printed[:cut], printed[cut:]) if cut > 0 else (printed, "")
        table.options[name] = Option(name=name, meta=meta, value=value)
    return table


def by_level(texts: dict[str, str], kind: str = "optimizers") -> dict[str, Table]:
    """The recorded `-Q --help` output for one kind of table, parsed, in reading order.

    A recorder keys its output `optimizers -O2`, one entry per level, and a dict of parsed
    tables in `LEVELS` order is what every caller then builds by hand. A level that is not in
    `LEVELS` goes on the end in the order it was recorded, so a recording of something
    unusual is still readable rather than silently dropped.
    """
    parsed = {
        key.split()[1]: parse(text, *key.split())
        for key, text in texts.items()
        if key.startswith(f"{kind} ")
    }
    order = [lv for lv in LEVELS if lv in parsed] + [lv for lv in parsed if lv not in LEVELS]
    return {lv: parsed[lv] for lv in order}


@dataclass(frozen=True)
class Change:
    """One option that is not the same in two tables."""

    name: str
    before: str | None
    after: str | None

    @property
    def kind(self) -> str:
        """on, off, value, added or dropped.

        added and dropped are for an option that is in one table and not the other, which
        happens when the two tables came from different targets or different compilers and
        never happens between two optimization levels of one compiler.
        """
        if self.before is None:
            return "added"
        if self.after is None:
            return "dropped"
        if self.after == ENABLED:
            return "on"
        if self.after == DISABLED:
            return "off"
        return "value"

    def as_flag(self) -> str | None:
        """The command line flag that asks for the `after` side of this change.

        None when there is no way to write it. That happens for a value that GCC printed
        as `[default]` or as nothing, which is what an option looks like when no level has
        set it, and there is no spelling for putting an option back to that. So a change
        can be undone going up the levels and not always coming back down, which is worth
        knowing before you try to rebuild `-Os` out of `-O2`.
        """
        if self.kind == "on":
            return self.name
        if self.kind == "off":
            return f"-fno-{self.name[2:]}" if self.name.startswith("-f") else None
        if self.kind == "value":
            usable = self.after and not self.after.startswith("[")
            return f"{self.name}{self.after}" if usable and self.name.endswith("=") else None
        return None

    def __str__(self) -> str:
        words = {
            "on": f"{self.name} turned on",
            "off": f"{self.name} turned off",
            "value": (
                f"{self.name} went from {self.before or 'nothing'} to {self.after or 'nothing'}"
            ),
            "added": f"{self.name} exists here and did not before",
            "dropped": f"{self.name} is gone",
        }
        return words[self.kind]


def diff(before: Table, after: Table) -> list[Change]:
    """Every option the two tables disagree about, in the order GCC printed them.

    A switch going from `[disabled]` to `[enabled]` and an option going from `simple` to
    `stc` are both here, and `Change.kind` tells them apart. Reporting only the switches
    is the mistake this function exists to make hard.
    """
    out = []
    for name, option in after.options.items():
        old = before.options.get(name)
        if old is None:
            out.append(Change(name, None, option.value))
        elif old.value != option.value:
            out.append(Change(name, old.value, option.value))
    for name, option in before.options.items():
        if name not in after.options:
            out.append(Change(name, option.value, None))
    return out


def flips(before: Table, after: Table, on: bool = True) -> list[str]:
    """Just the switches that flipped, which is the number everyone quotes.

    Kept separate from `diff` and named for what it leaves out, so that a caller reaching
    for the famous number has to look at the word `flips` while doing it.
    """
    want = ENABLED if on else DISABLED
    return [c.name for c in diff(before, after) if c.after == want]
