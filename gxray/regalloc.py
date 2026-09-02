"""Turn the IRA dump into an account of who got a register and who did not.

`-fdump-rtl-ira` is the most talkative dump GCC writes and almost none of it is RTL. It is
the allocator narrating a graph colouring, and every stage of the textbook algorithm is in
there under a slightly different name. This reader picks out the six things a lesson needs
and leaves the rest as text.

What the interesting lines look like, from
`gcc-16 -O2 -fdump-rtl-ira -c corpora/programs/t08-pressure.c`:

    a0(r106,l0) costs: GENERAL_REGS:0,0 FP_REGS:1100,14450 MEM:660,9560
     a0(r106): [9..10] [0..6]
    ;; a0(r106,l0) conflicts: a1(r113,l0) a3(r112,l0) a2(r105,l0)
        Pressure: GENERAL_REGS=6
      Allocno a0r106 of GENERAL_REGS(29) has 29 avail. regs  0-17 19-28 30
          Pushing a8(r114,l0)(cost 0)
          Popping a5(r103,l0)  --         assign reg 2
    Disposition:
        5:r103 l0     2    4:r104 l0     4    2:r105 l0     3
    +++Costs: overall -233, reg -233, mem 0, ld 0, st 0, move 0

An allocno is not a pseudo. IRA splits the function into regions, one per loop, and a
pseudo that is live in two regions gets one allocno in each so that it can live in a
register in the hot one and in memory in the cold one. `a9(r103,l1)` and `a5(r103,l0)` are
the same variable at two loop depths. That is why almost everything here is keyed on the
allocno number and why `Allocation.spilled` has to fold back to pseudos before answering.

Three things this reader deliberately does not do.

It does not name hard registers. The dump prints `assign reg 2` and the number is an index
into a table that only the target has, so a name would be a guess. The names are printed by
the assembler output and that is where a lesson should get them.

It does not treat the colouring order as the answer. An allocno can be popped as a spill and
still end up in a register, because a later step swaps it for a cheaper victim. `Disposition`
is what actually happened and `order` is how the algorithm got there. They disagree in
`p30`, which is the most instructive thing in the dump.

It does not read the RTL at the end of each function chunk. That is what `gxray.rtl` is for,
and the allocation is not applied to it yet anyway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FUNCTION = re.compile(r"^;; Function (?P<pretty>.+?) \((?P<detail>.*)\)\s*$")

# a0(r106,l0) costs: GENERAL_REGS:0,0 FP_LO8_REGS:1100,14450 MEM:660,9560
COSTS = re.compile(r"^\s+a(?P<num>\d+)\(r(?P<pseudo>\d+),l(?P<level>\d+)\) costs:(?P<rest>.*)$")
COST_ITEM = re.compile(r"(?P<name>[A-Z][A-Z_0-9]*):(?P<here>-?\d+),(?P<total>-?\d+)")

#  a0(r106): [9..10] [0..6]
RANGES = re.compile(r"^ a(?P<num>\d+)\(r(?P<pseudo>\d+)\):(?P<rest>(?: \[\d+\.\.\d+\])+)\s*$")
ONE_RANGE = re.compile(r"\[(\d+)\.\.(\d+)\]")

# ;; a0(r106,l0) conflicts: a1(r113,l0) a3(r112,l0)
CONFLICTS = re.compile(r"^;; a(?P<num>\d+)\(r\d+,l\d+\) conflicts:(?P<rest>.*)$")
CONFLICT_ITEM = re.compile(r"a(\d+)\(r\d+,l\d+\)")

#     Pressure: GENERAL_REGS=6 FP_REGS=2
PRESSURE = re.compile(r"^\s+Pressure:(?P<rest>(?: [A-Z][A-Z_0-9]*=\d+)+)\s*$")
PRESSURE_ITEM = re.compile(r"([A-Z][A-Z_0-9]*)=(\d+)")

#   Allocno a0r106 of GENERAL_REGS(29) has 29 avail. regs  0-17 19-28 30
CLASS_OF = re.compile(
    r"^\s+Allocno a(?P<num>\d+)r\d+ of (?P<klass>[A-Z][A-Z_0-9]*)"
    r"\((?P<size>\d+)\) has (?P<avail>\d+) avail"
)

#       Pushing a8(r114,l0)(cost 0)
PUSHING = re.compile(r"^\s+Pushing a(?P<num>\d+)\(r\d+,l\d+\)")

#       Popping a5(r103,l0)  --         assign reg 2
#       Popping a56(r130,l0)  -- spill
POPPING = re.compile(r"^\s+Popping a(?P<num>\d+)\(r\d+,l\d+\)\s+--\s+(?P<verdict>.*?)\s*$")
ASSIGNED = re.compile(r"^assign reg (\d+)$")

# Compressing live ranges: from 40 to 11 - 27%
COMPRESSION = re.compile(r"^Compressing live ranges: from (?P<before>\d+) to (?P<after>\d+)")

#     5:r103 l0     2    4:r104 l0     4    0:r106 l0   mem
DISPOSITION = re.compile(r"(?P<num>\d+):r(?P<pseudo>\d+) l(?P<level>\d+)\s+(?P<where>mem|\d+)")

# +++Costs: overall -233, reg -233, mem 0, ld 0, st 0, move 0
TOTALS = re.compile(
    r"^\+\+\+Costs: overall (?P<overall>-?\d+), reg (?P<reg>-?\d+), mem (?P<mem>-?\d+), "
    r"ld (?P<ld>-?\d+), st (?P<st>-?\d+), move (?P<move>-?\d+)"
)

#: What a lesson calls the class of registers a `long` lives in. Every target in the book
#: uses this name for it, because the name comes from `gcc/reginfo.cc` and not from a target.
GENERAL = "GENERAL_REGS"


@dataclass(frozen=True)
class Allocno:
    """One pseudo register in one region of the function.

    `hard` is the register number the allocator settled on, or None for one that ended up in
    memory. It is a number and not a name on purpose: see the module docstring.
    """

    num: int
    pseudo: int
    level: int
    klass: str = ""
    size: int = 0
    avail: int = 0
    mem_cost: int = 0
    ranges: tuple[tuple[int, int], ...] = ()
    conflicts: frozenset[int] = frozenset()
    hard: int | None = None
    placed: bool = False

    @property
    def spilled(self) -> bool:
        """Ended up in memory. False for an allocno the dump never gave a home to."""
        return self.placed and self.hard is None

    @property
    def live(self) -> int:
        """How many program points this allocno is alive for, after range compression."""
        return sum(stop - start + 1 for start, stop in self.ranges)

    @property
    def where(self) -> str:
        if not self.placed:
            return "undecided"
        return "memory" if self.hard is None else f"reg {self.hard}"

    def __str__(self) -> str:
        return f"a{self.num}(r{self.pseudo},l{self.level}) {self.where}"


@dataclass(frozen=True)
class Step:
    """One move of the colouring stack, in the order the dump printed it."""

    action: str
    allocno: int
    verdict: str = ""

    def __str__(self) -> str:
        tail = f" {self.verdict}" if self.verdict else ""
        return f"{self.action} a{self.allocno}{tail}"


@dataclass(frozen=True)
class Totals:
    """What IRA thinks this allocation cost, in its own units.

    The units are frequency weighted instruction counts and they are not comparable across
    functions of different shapes. They are very comparable across two targets given the
    same function, which is the only way this book uses them.
    """

    overall: int = 0
    reg: int = 0
    mem: int = 0
    ld: int = 0
    st: int = 0
    move: int = 0


@dataclass
class Allocation:
    """One function's allocation."""

    function: str = ""
    detail: str = ""
    allocnos: dict[int, Allocno] = field(default_factory=dict)
    pressure: dict[str, int] = field(default_factory=dict)
    sizes: dict[str, int] = field(default_factory=dict)
    order: tuple[Step, ...] = ()
    totals: Totals = field(default_factory=Totals)
    compression: tuple[int, int] | None = None
    text: str = ""

    def __len__(self) -> int:
        return len(self.allocnos)

    def __iter__(self):
        return iter(self.allocnos.values())

    def available(self, klass: str = GENERAL) -> int:
        """How many registers of this class the target has for the allocator to hand out."""
        return self.sizes.get(klass, 0)

    def peak(self, klass: str = GENERAL) -> int:
        """The most values of this class that are alive at any one point in the function."""
        return self.pressure.get(klass, 0)

    def over(self, klass: str = GENERAL) -> int:
        """How far the peak exceeds the supply. Zero or less means it fits."""
        return self.peak(klass) - self.available(klass)

    @property
    def pseudos(self) -> dict[int, list[Allocno]]:
        """Every allocno, gathered back under the pseudo it came from."""
        out: dict[int, list[Allocno]] = {}
        for a in sorted(self.allocnos.values(), key=lambda a: (a.pseudo, a.level)):
            out.setdefault(a.pseudo, []).append(a)
        return out

    @property
    def spilled(self) -> list[int]:
        """Pseudos that ended up in memory anywhere in the function."""
        return sorted(p for p, group in self.pseudos.items() if any(a.spilled for a in group))

    @property
    def kept(self) -> list[int]:
        """Pseudos that got a register everywhere they are live."""
        spilled = set(self.spilled)
        return sorted(p for p in self.pseudos if p not in spilled)

    @property
    def fits(self) -> bool:
        return not self.spilled

    def graph(self, level: int = 0) -> dict[int, set[int]]:
        """The interference graph for one region, keyed on pseudo rather than allocno.

        Region 0 is the whole function. A deeper region is one loop, and its graph is the
        one that decides what happens in the code that runs most.
        """
        here = {a.num: a for a in self.allocnos.values() if a.level == level}
        return {a.pseudo: {here[n].pseudo for n in a.conflicts if n in here} for a in here.values()}

    def spill_steps(self) -> list[Step]:
        """The pops the colourer could not colour. Not the same set as `spilled`."""
        return [s for s in self.order if s.action == "pop" and s.verdict == "spill"]

    def __str__(self) -> str:
        state = "fits" if self.fits else f"{len(self.spilled)} in memory"
        return (
            f"{self.function}: peak {self.peak()} of {self.available()} {GENERAL}, "
            f"{len(self.pseudos)} pseudos, {state}"
        )


@dataclass
class IraDump:
    """Every function in one `-fdump-rtl-ira` dump."""

    name: str = ""
    text: str = ""
    functions: dict[str, Allocation] = field(default_factory=dict)

    def only(self) -> Allocation:
        if len(self.functions) != 1:
            raise ValueError(f"expected one function, found {len(self.functions)}")
        return next(iter(self.functions.values()))

    def __getitem__(self, function: str) -> Allocation:
        return self.functions[function]

    def __len__(self) -> int:
        return len(self.functions)

    def __iter__(self):
        return iter(self.functions.values())

    def __str__(self) -> str:
        return f"{self.name or 'ira'}: {', '.join(self.functions) or 'no functions'}"


def _disposition(text: str) -> dict[int, int | None]:
    """The last Disposition block in a chunk, as allocno to hard register or None.

    The last one and not the first, because IRA prints one per iteration of its spill and
    restore loop and only the final one describes the code that gets generated.
    """
    marks = [m.end() for m in re.finditer(r"^Disposition:\s*$", text, re.MULTILINE)]
    if not marks:
        return {}
    tail = text[marks[-1] :]
    # The block ends at the first line that holds no entry, which is how IRA separates it
    # from whatever it says next. Scanning the whole tail would pick up unrelated numbers.
    out: dict[int, int | None] = {}
    for line in tail.splitlines():
        found = list(DISPOSITION.finditer(line))
        if not found:
            if out:
                break
            continue
        for m in found:
            where = m.group("where")
            out[int(m.group("num"))] = None if where == "mem" else int(where)
    return out


def _one(chunk: str) -> Allocation:
    header = FUNCTION.match(chunk.splitlines()[0]) if chunk.strip() else None
    alloc = Allocation(
        function=header.group("pretty") if header else "",
        detail=header.group("detail") if header else "",
        text=chunk,
    )

    fields: dict[int, dict] = {}

    def slot(num: int) -> dict:
        return fields.setdefault(num, {})

    order: list[Step] = []
    for line in chunk.splitlines():
        m = COSTS.match(line)
        if m:
            here = slot(int(m.group("num")))
            here["pseudo"] = int(m.group("pseudo"))
            here["level"] = int(m.group("level"))
            costs = {c.group("name"): int(c.group("total")) for c in COST_ITEM.finditer(line)}
            here["mem_cost"] = costs.get("MEM", 0)
            continue
        m = RANGES.match(line)
        if m:
            here = slot(int(m.group("num")))
            here["pseudo"] = int(m.group("pseudo"))
            # Last block wins. GCC prints the ranges once as measured and again after
            # compressing them, and the compressed ones are what the conflicts are built on.
            here["ranges"] = tuple((int(a), int(b)) for a, b in ONE_RANGE.findall(m.group("rest")))
            continue
        m = CONFLICTS.match(line)
        if m:
            slot(int(m.group("num")))["conflicts"] = frozenset(
                int(n) for n in CONFLICT_ITEM.findall(m.group("rest"))
            )
            continue
        m = CLASS_OF.match(line)
        if m:
            here = slot(int(m.group("num")))
            here["klass"] = m.group("klass")
            here["size"] = int(m.group("size"))
            here["avail"] = int(m.group("avail"))
            alloc.sizes.setdefault(m.group("klass"), int(m.group("size")))
            continue
        m = PRESSURE.match(line)
        if m:
            for name, value in PRESSURE_ITEM.findall(m.group("rest")):
                # The dump prints one of these per region and the lesson wants the worst.
                alloc.pressure[name] = max(alloc.pressure.get(name, 0), int(value))
            continue
        m = PUSHING.match(line)
        if m:
            order.append(Step("push", int(m.group("num"))))
            continue
        m = POPPING.match(line)
        if m:
            order.append(Step("pop", int(m.group("num")), m.group("verdict")))
            continue
        m = COMPRESSION.match(line)
        if m:
            alloc.compression = (int(m.group("before")), int(m.group("after")))
            continue
        m = TOTALS.match(line)
        if m:
            alloc.totals = Totals(**{k: int(v) for k, v in m.groupdict().items()})

    alloc.order = tuple(order)
    placed = _disposition(chunk)
    for num, here in sorted(fields.items()):
        if "pseudo" not in here:
            continue
        alloc.allocnos[num] = Allocno(
            num=num,
            pseudo=here["pseudo"],
            level=here.get("level", 0),
            klass=here.get("klass", ""),
            size=here.get("size", 0),
            avail=here.get("avail", 0),
            mem_cost=here.get("mem_cost", 0),
            ranges=here.get("ranges", ()),
            conflicts=here.get("conflicts", frozenset()),
            hard=placed.get(num),
            placed=num in placed,
        )
    return alloc


def parse(text: str, name: str = "") -> IraDump:
    """Read an IRA dump. Never raises on unfamiliar content.

    A file with five functions in it produces five chunks and the allocno numbers restart at
    zero in every one, which is why they are split rather than merged.
    """
    dump = IraDump(name=name, text=text)
    marks = [m.start() for m in re.finditer(r"^;; Function ", text, re.MULTILINE)]
    cuts = marks or [0]
    for n, start in enumerate(cuts):
        end = cuts[n + 1] if n + 1 < len(cuts) else len(text)
        one = _one(text[start:end])
        if one.allocnos or one.function:
            dump.functions[one.function or f"function {n}"] = one
    return dump
