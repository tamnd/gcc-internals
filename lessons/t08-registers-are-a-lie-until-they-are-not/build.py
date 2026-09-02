"""T08. Registers are a lie until they are not.

T07 ended on a promise the expander makes and cannot keep: help yourself to as many
registers as you like, somebody later will sort it out. This lesson is somebody later.

Everything here comes from recordings of one program, `corpora/programs/t08-pressure.c`,
which holds five functions that keep 4, 10, 14, 20 and 30 values alive at once. `t08-x86-64`
and `t08-aarch64` are Compiler Explorer at GCC 16.1.0 and `t08-local` is the local compiler,
which is aarch64 Darwin and has one register fewer than aarch64 Linux for a reason that
turns out to be worth a paragraph.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t08-registers-are-a-lie-until-they-are-not",
    "t08",
    title="Registers are a lie until they are not",
    milestone="M1",
    summary=(
        "The pass that makes good on the expander's promise, what an allocno is and why it "
        "is not a pseudo, live ranges and interference, the one number that decides "
        "everything, and the same five functions coming out differently on two machines "
        "because one of them has half as many registers"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T08. Registers are a lie until they are not

{badge}

T07 finished with three registers numbered 101, 102 and 103, and the observation that no such
registers exist. The expander invented them. It is allowed to, because it hands the problem
of finding real ones to a pass twenty steps later, and that arrangement is one of the better
ideas in compiler design: choosing instructions and assigning registers are each hard, and
doing both at once is much harder than doing them one after the other.

This lesson is the pass that pays for it. {term("register allocation")} decides which values
live in {term("hard register", "real registers")} and which get written to the stack, and
when it cannot fit everything it decides who loses. That decision is worth watching because
it is the first place in the whole pipeline where the machine you are compiling for changes
the answer rather than just the spelling.

You need a browser. There is no compiler here and no network.

**What you come away with**

- What an {term("allocno")} is, and why an IRA dump has half again as many of them as your
  function has registers in it
- How to read a {term("live range")} and why the numbers in one are not line numbers
- {term("interference", "The interference graph")}, and why colouring it is the whole problem
- {term("register pressure")}, which is the one number that tells you what is going to happen
- Why x86-64 gives you fifteen registers and not sixteen, and what that one costs
- Having watched the same five functions come out fine on one machine and spill on another
""")

lesson.setup()

lesson.md(f"""
## Two passes, adjacent

The pass list has them next to each other and they have unhelpful names.

{term("IRA")} is the first. Its pass description is at
{cite("gcc/ira.cc:6202@releases/gcc-16.2.0")} and it runs the function at
{cite("gcc/ira.cc:5663@releases/gcc-16.2.0")}. It works out where every value should go and
writes the answer down. It does not modify a single instruction.

{term("LRA")} is the second, and in the pass list it is called `reload`, at
{cite("gcc/ira.cc:6247@releases/gcc-16.2.0")}, running
{cite("gcc/ira.cc:6056@releases/gcc-16.2.0")}. That name is a fossil. LRA replaced a pass
called reload in 2013 and inherited its slot, its pass name and its reputation, and it does
no reloading in the old sense. What it does is take IRA's decision and rewrite the function
to match, inventing whatever extra instructions that needs.

We are going to spend almost the whole lesson on the first one, because the first one is
where the interesting decision is made and because its dump is readable.

```text
gcc-16 -O2 -fdump-rtl-ira t08-pressure.c
```

## The program

Five functions, deliberately built so that the number of values alive at once is fixed and
obvious. Each one reads N longs out of an array, then rotates them in a loop so that every
value is used and redefined on every iteration, then returns the sum.

That shape matters. A value that is live across the back edge of a loop has to be in the same
place at the top of the iteration and at the bottom, and because every value is touched every
iteration, no two of them can take turns in one register. There is no clever schedule that
gets out of it. The function needs N places, plus one for the array pointer and one for the
loop counter, and if the machine has fewer than that then something is going to memory.

N goes 4, 10, 14, 20 and 30, and the functions are called `p04`, `p10`, `p14`, `p20`, `p30`.
""")

lesson.md(f"""
{claim("the five functions have register pressure 6, 12, 16, 22 and 32, which is N plus two")}.
""")

lesson.code("""
from gxray import regalloc

record = gxray.corpus_store.load("t08-x86-64")
dump = regalloc.parse(record.dump_texts["rtl-ira"], "t08-x86-64")

print(f"{record.compiler} for {record.target}")
print(f"{len(dump)} functions in the dump")
print()
for alloc in dump:
    print(
        f"  {alloc.function:<5}  pressure {alloc.peak():>3}  "
        f"{len(alloc.pseudos):>3} pseudos  {len(alloc.allocnos):>3} allocnos"
    )
""")

lesson.md(f"""
Two things in that table are already surprising.

The pressure is N plus two, exactly as promised. `p20` keeps twenty two values alive at the
busiest point in the function.

And there are half again as many {term("allocno", "allocnos")} as pseudo registers. That is
the first thing to sort out.

## An allocno is not a pseudo

`struct ira_allocno` at {cite("gcc/ira-int.h:274@releases/gcc-16.2.0")} is the thing IRA
actually colours, and it is a pseudo register within one region of the function.

IRA splits a function up along the loop tree. A value that is live both inside a loop and
outside it gets one allocno for the inside and another for the outside, and the two can be
given different hard registers, with a copy inserted at the boundary if they differ. That is
a real optimisation: a value that is hot inside the loop and cold outside it can have a
register where it matters and give it up where it does not.

Every one of our functions is one loop with values live across it, so every pseudo that
survives the loop gets two allocnos and everything else gets one. In `p20` that is a bit over
half of them, which is where the extra twenty two came from.

The dump writes an allocno as `a58(r159,l0)`. Allocno 58, pseudo 159, region 0, where region
0 means the whole function. A region that is a loop prints its loop number and a region that
is a basic block prints `b` and the block index.
""")

lesson.md(f"""
{claim("in p20 half the pseudos have two allocnos, one for the loop and one for outside it")}.
""")

lesson.code("""
p20 = dump["p20"]
counts = {}
for group in p20.pseudos.values():
    counts[len(group)] = counts.get(len(group), 0) + 1

print(f"{len(p20.pseudos)} pseudos, {len(p20.allocnos)} allocnos")
for n, many in sorted(counts.items()):
    print(f"  {many:>3} pseudos have {n} allocno(s)")

print()
paired = [p for p in p20.pseudos if len(p20.pseudos[p]) == 2]
pseudo = max(paired, key=lambda p: sum(a.live for a in p20.pseudos[p]))
print(f"the longest lived pseudo with two allocnos is r{pseudo}:")
for a in p20.pseudos[pseudo]:
    print(f"  {a}   region {a.level}, alive at {a.live} points, {len(a.conflicts)} conflicts")
""")

lesson.md(f"""
## Live ranges

The second thing on an allocno is when it is alive. `struct live_range` at
{cite("gcc/ira-int.h:198@releases/gcc-16.2.0")} is a closed interval of program points, and
an allocno has a list of them, because a value can be alive, dead, and alive again.

Program points are not insn numbers and they are not line numbers. IRA numbers them by
walking the instructions, roughly two points per insn, and then it throws most of them away.
`remove_some_program_points_and_update_live_ranges` at
{cite("gcc/ira-lives.cc:1660@releases/gcc-16.2.0")} merges every run of points at which
nothing was born and nothing died, because such a point cannot possibly change any answer.
The dump says how much it removed.
""")

lesson.md(f"""
{claim("compressing the point numbering throws away about two thirds of the points")}.
""")

lesson.code("""
for alloc in dump:
    before, after = alloc.compression
    print(
        f"  {alloc.function:<5}  {before:>4} points compressed to {after:>3}  "
        f"({100 * after // before}% left)"
    )

print()
print("p20, the first six allocnos and where they are alive:")
for a in list(p20)[:6]:
    ranges = " ".join(f"[{s}..{e}]" for s, e in a.ranges)
    print(f"  a{a.num:<3} r{a.pseudo:<4} {ranges}")
""")

lesson.md("""
So a range like `[4..40]` means this value has to exist from point 4 to point 40 in a
numbering that only exists inside this dump of this function on this target. Comparing point
numbers between two targets is meaningless, and the widget further down draws the bars per
target for exactly that reason.

What the ranges are for is the next section.

## Interference

Two values that are alive at the same point cannot share a register. That is the entire
definition, and it is what `build_object_conflicts` builds a graph out of.

Draw a node for every value and an edge between any two whose ranges overlap, and allocation
becomes graph colouring: give every node a colour, no two joined nodes the same colour, using
at most as many colours as the machine has registers. That problem is NP complete in general,
which is why the allocator is a large pile of heuristics rather than an algorithm.

Our rotating functions produce about the worst graph you can ask for. The rotated values are
alive from the first load to the final sum, so each of them conflicts with every other one,
and that part of the graph is a clique.
""")

lesson.md(f"""
{claim("in p20 the busiest value conflicts with 39 of the other 41 pseudos")}.
""")

lesson.code("""
graph = p20.graph(level=0)
sizes = sorted({len(peers) for peers in graph.values()})
print(f"{len(graph)} pseudos in region 0")
print(f"conflict counts range from {sizes[0]} to {sizes[-1]}")
print()

busiest = max(graph, key=lambda p: len(graph[p]))
print(f"r{busiest} conflicts with {len(graph[busiest])} other pseudos:")
print("  " + " ".join(f"r{p}" for p in sorted(graph[busiest])))
""")

lesson.md(f"""
Thirty nine out of forty one. Nothing in that set can share a register with anything else in
it, so the number of colours it needs is the number of nodes, and if the machine has fewer
registers than that then no amount of cleverness helps. Exactly one pseudo has no conflicts at
all, r140, which is alive for two points at the very start of the function and dead again
before anything else is loaded.

## The number that decides everything

{term("register pressure")} is how many values are alive at the busiest point, counted per
{term("register class")}. `print_loop_title` at
{cite("gcc/ira-color.cc:3654@releases/gcc-16.2.0")} prints one line per region:

```text
    Pressure: GENERAL_REGS=22
```

Against it goes how many registers the target can actually hand out, which the dump also
prints, once per allocno:

```text
      Allocno a20r135 of GENERAL_REGS(15) has 15 available regs
```

Fifteen. Not sixteen. x86-64 has sixteen general purpose registers and the stack pointer is
one of them, and the stack pointer is not available for holding your variables. Any prediction
that starts from sixteen is going to be off by one, and `p14` is the function that catches it.
""")

lesson.md(f"""
{claim("x86-64 hands out 15 registers, and the pressure of p14 is 16, one too many")}.
""")

lesson.code("""
print(f"{'function':<10}{'pressure':>9}{'available':>11}{'over by':>9}{'in memory':>11}")
for alloc in dump:
    over = max(0, alloc.over())
    print(
        f"{alloc.function:<10}{alloc.peak():>9}{alloc.available():>11}"
        f"{over:>9}{len(alloc.spilled):>11}"
    )
""")

lesson.md(f"""
Look at the last two columns. Every row, the number of pseudos in memory is exactly the
amount by which pressure exceeded supply. Sixteen values and fifteen registers puts one value
in memory. Twenty two puts seven. Thirty two puts seventeen.

Do not learn that as a rule. It is exact here because this program was built to make it exact:
uniform pressure, one loop, every value equally hot, so the allocator has nothing to trade and
no reason to prefer one victim over another. Give it a hot inner loop and a cold outer one and
it will spend a spill in the cold part to save one in the hot part, and the count stops
matching the arithmetic. What survives generally is the direction, not the equality.

## The disposition

Where does the count come from? The end of the dump. `ira_print_disposition` at
{cite("gcc/ira.cc:698@releases/gcc-16.2.0")} writes one entry per allocno, four to a line,
and this is the allocator's own record of what it decided.

```text
Disposition:
    0:r117 l0     3    1:r118 l0     0    2:r119 l0   mem
```

Allocno number, pseudo, region, and then either a hard register number or the word `mem`.
That is the answer. Everything else in the dump is the allocator narrating attempts.

The register is a number and not a name, and there is no honest way to turn it into a name
from this file alone. It is an index into a table only the target has. To find out that
register 3 is `bx`, read the assembly.
""")

lesson.md(f"""
{claim("in p20 on x86-64 seven pseudos are in memory and the rest are in numbered registers")}.
""")

lesson.code("""
print(f"p20: {len(p20.spilled)} pseudos in memory, {len(p20.kept)} in registers")
print()
for pseudo in sorted(p20.pseudos):
    where = ", ".join(a.where for a in p20.pseudos[pseudo])
    mark = "-" if pseudo in set(p20.spilled) else " "
    print(f"  {mark} r{pseudo:<4} {where}")
""")

lesson.md("""
## Two machines

Now the point of the lesson. Same source, same flags, same version of GCC, two back ends.

x86-64 can hand out fifteen general registers. aarch64 can hand out thirty. Everything else
about the comparison is held fixed, so wherever the two answers differ, the difference is the
size of the register file and nothing else.
""")

lesson.md(f"""
{claim("p14 and p20 fit on aarch64 and do not fit on x86-64")}.
""")

lesson.code("""
targets = {"x86-64": "t08-x86-64", "aarch64": "t08-aarch64"}
allocations = {}
for name, entry in targets.items():
    text = gxray.corpus_store.load(entry).dump_texts["rtl-ira"]
    allocations[name] = regalloc.parse(text, name).functions

print(f"{'function':<10}{'pressure':>9}", end="")
for name in targets:
    print(f"{name:>16}", end="")
print()
for fn in ["p04", "p10", "p14", "p20", "p30"]:
    print(f"{fn:<10}{allocations['x86-64'][fn].peak():>9}", end="")
    for name in targets:
        alloc = allocations[name][fn]
        state = "fits" if alloc.fits else f"{len(alloc.spilled)} in memory"
        print(f"{state:>16}", end="")
    print()
""")

lesson.md("""
Three functions out of five come out differently, and one of them, `p20`, is a twenty line
function with no function calls in it.

## The widget

The same thing, one function at a time, with the live ranges drawn. Pick a function along the
top and the two columns are the two targets. Each row is one pseudo, the bar is the points it
is alive at, and the right hand column says where it ended up. The buttons filter down to the
values that got a register or the ones that did not, which on `p30` is the only sensible way
to look at it.

Bars line up within a column and not across two of them, because each target compressed its
own point numbering.
""")

lesson.code("""
from IPython.display import HTML, display

from gxwidgets.__main__ import pressure

widget = pressure()
display(HTML(widget.render()))

# The same conclusion as text, so this cell proves something where HTML does not render.
facts = widget.data()
print(f"{len(facts['targets'])} targets: {', '.join(facts['targets'])}")
for fn in facts["functions"]:
    counts = "  ".join(f"{t}: {n}" for t, n in facts["spilled"][fn].items())
    print(f"  {fn}  {counts}")
print(f"\\nthe targets disagree about {', '.join(facts['diverges'])}")
""")

lesson.md("""
## The same thing as a picture

Two stills. The first is one function on two machines, one cell per pseudo, marked where the
value ended up on the stack. The second is the ramp on one machine, one lane per function and
one cell per value alive at the busiest point, with everything past the fifteenth cell marked
because there is nowhere for it to go.
""")

lesson.code("""
from IPython.display import SVG

import gxmanim

both = gxmanim.mobjects.spill_map({t: allocations[t]["p20"] for t in targets}, title="p20")
display(SVG(gxmanim.svg.document(both)))
print(both.describe())
""")

lesson.code("""
rows = {fn: {t: allocations[t][fn] for t in targets} for fn in ["p04", "p10", "p14", "p20", "p30"]}
ramp = gxmanim.mobjects.pressure_ramp(rows, "x86-64")
display(SVG(gxmanim.svg.document(ramp)))
print(ramp.describe())
""")

lesson.md(f"""
## How the colouring runs, and how it lies to you

Everything so far came off the disposition. The dump also narrates the colouring itself, and
watching it is worth doing once, with one warning attached.

`push_allocnos_to_stack` at {cite("gcc/ira-color.cc:2950@releases/gcc-16.2.0")} takes allocnos
out of the graph one at a time and pushes them. It prefers one with fewer conflicts than there
are registers, because such a node is trivially colourable whatever happens to the rest. When
there is no such node it picks the worst spill candidate, ranked by
`allocno_spill_priority` at {cite("gcc/ira-color.cc:2567@releases/gcc-16.2.0")}, which weighs
what spilling would cost against how much of the graph removing it unblocks.

Then `pop_allocnos_from_stack` at {cite("gcc/ira-color.cc:2983@releases/gcc-16.2.0")} takes
them back off in reverse order and gives each one a free register if there is one left.

```text
      Pushing a20(r135,l0)
      Popping a20(r135,l0)  -- assign reg 12
      Popping a19(r134,l0)  -- spill
```

Here is the warning. Those lines are not the answer.
""")

lesson.md(f"""
{claim("the colouring trace and the final disposition disagree about four allocnos in p30")}.
""")

lesson.code("""
p30 = allocations["aarch64"]["p30"]
told = {step.allocno for step in p30.spill_steps()}
ended = {a.num for a in p30 if a.spilled}

print(f"the trace says {len(told)} allocnos could not be coloured")
print(f"the disposition says {len(ended)} allocnos are in memory")
print()
for num in sorted(told | ended):
    a = p30.allocnos[num]
    trace = "spill" if num in told else "coloured"
    print(f"  a{num:<4} r{a.pseudo:<4}  trace said {trace:<9}  ended up {a.where}")
""")

lesson.md(f"""
Four allocnos, which is two pseudos with two regions each, swapped places between the trace
and the disposition. Pseudo 129 was pushed as a spill candidate and ended up in register 28,
and pseudo 159 was coloured on the way out and ended up on the stack. That is not a bug in
the reader and it is not a bug in GCC. After the pop phase finishes, `improve_allocation` at
{cite("gcc/ira-color.cc:3217@releases/gcc-16.2.0")} goes looking for a spilled value that
would be cheaper in a register than whatever is currently sitting in one, and swaps them.
`ira_reassign_conflict_allocnos` at {cite("gcc/ira-color.cc:4072@releases/gcc-16.2.0")} does
another round of the same idea.

The rule to take away is short. The `Disposition:` block is what happened. Everything above
it is the allocator thinking out loud, and it changes its mind.

## What it cost

IRA prices its own answer, in `calculate_allocation_cost` at
{cite("gcc/ira.cc:2640@releases/gcc-16.2.0")}, and prints the total:

```text
+++Costs: overall 187732, reg 0, mem 187732, ld 0, st 0, move 0
```

The units are frequency weighted and arbitrary. The number is meaningless on its own, means
very little between two different functions, and means a great deal between two targets given
the same function.
""")

lesson.md(f"""
{claim("IRA charges nothing for memory on aarch64 until p30, and a great deal on x86-64")}.
""")

lesson.code("""
print(f"{'function':<10}", end="")
for name in targets:
    print(f"{name:>14}", end="")
print()
for fn in ["p04", "p10", "p14", "p20", "p30"]:
    print(f"{fn:<10}", end="")
    for name in targets:
        print(f"{allocations[name][fn].totals.mem:>14}", end="")
    print()

both_pay = allocations["x86-64"]["p30"].totals.mem, allocations["aarch64"]["p30"].totals.mem
print(
    f"\\np30 is the only function both machines pay for, and x86-64 pays "
    f"{both_pay[0] // both_pay[1]} times as much"
)
""")

lesson.md(f"""
## The third machine, which is the same machine

There is one more recording and it exists because of an accident that turned out to teach
something. `t08-local` is the local compiler, GCC 16.2 on aarch64 Darwin. Same instruction
set as `t08-aarch64`, which is aarch64 Linux.

Apple's calling convention reserves `x18` as a platform register. Nothing else differs. One
register fewer, out of thirty.
""")

lesson.code("""
third = gxray.corpus_store.load("t08-local")
darwin = regalloc.parse(third.dump_texts["rtl-ira"], "darwin").functions

print(f"{third.compiler} for {third.target}")
print()
print(f"{'function':<10}{'linux 30':>12}{'darwin 29':>12}")
for fn in ["p14", "p20", "p30"]:
    linux = allocations["aarch64"][fn]
    apple = darwin[fn]
    print(f"{fn:<10}{len(linux.spilled):>12}{len(apple.spilled):>12}")
""")

lesson.md(f"""
One register, one more value on the stack. That is the cheapest possible demonstration that
the thing being measured really is the size of the register file and not some other property
of the two back ends.

## What LRA does with all this

IRA decided. Nothing has changed yet. Every instruction in the function still refers to
pseudo registers, and something has to rewrite them.

{term("LRA")} at {cite("gcc/lra.cc:2420@releases/gcc-16.2.0")} is a loop, and the loop is the
answer to why register allocation is the slow part of compiling.

```text
repeat:
    satisfy every instruction's operand constraints      lra_constraints
    if nothing changed: stop
    recompute the live ranges                            lra_create_live_ranges
    reassign whatever is still unassigned                lra_assign
then:
    give every remaining pseudo a stack slot             lra_spill
    rewrite every pseudo into a register or a slot
```

Why it has to loop. An instruction that needs its operand in a register, handed a value IRA
put in memory, cannot be left alone. LRA invents a fresh pseudo, emits a load into it, and
rewrites the instruction to use it. That new pseudo is alive, so every live range in the
neighbourhood is now wrong, so anything still unassigned has to be reconsidered, and
reconsidering can spill something else, which needs another load, and round again.

It terminates because each pass has strictly less left to fix. On a function like `p30` it
goes round several times, and each round walks every instruction.

The saving grace is `lra_inheritance` at
{cite("gcc/lra-constraints.cc:7564@releases/gcc-16.2.0")}. A value loaded into a register
stays there for the next use if nothing has clobbered it in between, so a spilled value used
three times in a loop body is loaded once and not three times. Without that, spilling would
cost far more than it does.

## The picture

The supply and demand argument, one function's live ranges, and the two stage split between
IRA and LRA are drawn in
[`diagrams/who-gets-a-register.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t08-registers-are-a-lie-until-they-are-not/diagrams/who-gets-a-register.excalidraw).
Open it at excalidraw.com and you can move things around.

## Where to read more

`BP-REGALLOC` in
[`blueprints/BP-REGALLOC.md`](https://github.com/tamnd/gcc-internals/blob/main/blueprints/BP-REGALLOC.md)
is the reference version of this lesson. It has the allocno layout, the colouring algorithm
written out, five invariants including the one about the trace disagreeing with the
disposition, and the three configuration table with every number in it.

## Boss fight

Predict, before you look. Five functions, x86-64 at `-O2`. Which of them put at least one
value in memory?

Then two questions that need the numbers rather than a guess.

1. How many general registers x86-64 hands the allocator, which is not how many it has
2. How many values `p20` puts in memory on x86-64

The grader checks against the `Disposition:` block of the recorded dump, so it is checking
against the allocator's own record and not against a written down answer.

```text
python lessons/t08-registers-are-a-lie-until-they-are-not/grade.py
```

or `just grade t08-registers-are-a-lie-until-they-are-not`. It takes the answers on the
command line too, so `--spills p14,p20,p30 --available 15 --p20-memory 7` is a complete
submission.

The one to think about before answering is `p14`. Its pressure is sixteen and x86-64 has
sixteen general registers, which makes the tempting answer that it fits exactly.
""")

lesson.md("""
## What to read next

T09 is the last mile. The function now has real registers in it and it is still not text, and
the pass that turns an insn into a line of assembly is one of the few places in GCC where the
machine description is executed rather than matched against.

M3 opens the back end properly, and `BP-REGALLOC` splits into two documents there, because
IRA's cost model and LRA's constraint loop each need more room than one lesson can give them.
""")

raise SystemExit(lesson.save())
