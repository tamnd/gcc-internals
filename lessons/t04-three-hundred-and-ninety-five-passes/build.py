"""T04. Three hundred and ninety-five passes.

The first sight of the whole pipeline, on the program every lesson in Part I uses.

Everything here comes from the `t04-tape` corpus entry. That recording holds two things: the
pass list as `-fdump-passes` prints it at five optimization levels, and every tree dump of L1
at -O2, which is 140 files. The pass list gives the cells of the tape and the dumps fill them
in, and the whole lesson is about how few of the cells turn out to have anything in them.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t04-three-hundred-and-ninety-five-passes",
    "t04",
    title="Three hundred and ninety-five passes",
    milestone="M1",
    summary=(
        "What sits between GIMPLE and assembly, how long the list really is, why the ON and "
        "OFF that GCC prints next to each pass is not the same question as whether the pass "
        "ran, and what happens to one small function as all of it goes past"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T04. Three hundred and ninety-five passes

{badge}

T02 showed you four representations of one function and T03 showed you how the second one is
built. This lesson is about the distance between the second and the fourth, which is where
almost all of GCC is.

The honest answer to what happens between GIMPLE and assembly is a list, and the list is
longer than anyone expects. Every {term("pass")} on it gets handed your function, gets to
look at it, and gets to change it. Most of them do not. That last sentence is the actual
subject here, because it is the thing that makes the pipeline understandable instead of
terrifying.

You need a browser. There is no compiler here and no network.

**What you come away with**

- The real size of the pipeline, and how to print it yourself
- What a pass is as a piece of code, which is smaller than it sounds
- Why the passes are nested, and what a container turning off does to everything under it
- Three separate reasons the word ON next to a pass does not mean the pass ran
- Having watched all 281 of them go past one small function and seen how few left a mark
""")

lesson.setup()

lesson.md("""
## The list

`-fdump-passes` prints every pass GCC knows about, nested, with ON or OFF next to each one.
It prints to standard error and it compiles nothing useful, so it is the cheapest question
you can ask a compiler.

```text
gcc-16 -O2 -fdump-passes -c l1.c
```

The recording has the answer at five optimization levels, so the whole lesson can talk about
how the list moves without you needing a compiler to hand.
""")

lesson.md(f"""
{claim("GCC 16.2 knows about 395 passes, and 281 of them printed ON for L1 at -O2")}.
""")

lesson.code("""
from gxray import passes

record = gxray.corpus_store.load("t04-tape")
pipeline = passes.parse(record.pass_texts["-O2"])

print(pipeline)
print()
for label, count in pipeline.counts().items():
    print(f"{label:>10}  {count}")
""")

lesson.md("""
`with_dump` is the number of passes that have a dump file of their own. The other 31 print a
star in front of their name in the listing and write nothing, which usually means the pass is
a container rather than a transformation.

`unnamed` is two passes that GCC prints as `(null)`, because the name was never set. They are
kept in the count rather than quietly dropped. A parser that tidies away the awkward cases is
a parser that makes the book wrong by two.

## Predict first

Before you look at anything else. That function is eight lines of C with one loop in it. Of
the 281 passes that are on at -O2, how many actually change it?
""")

lesson.code("""
from IPython.display import HTML, display

from gxwidgets import Option, PredictGate

gate = PredictGate(
    "How many of the 281 passes change the IR of an eight line function?",
    [
        Option(
            "Nearly all of them, that is what optimization is",
            why="Almost every pass looks and finds nothing to do. Looking is most of the job.",
        ),
        Option(
            "About half",
            why="Still far too many. Most of the list is analysis, and analysis that finds "
            "nothing changes nothing.",
        ),
        Option("About 25", correct=True),
        Option(
            "None, it is too small to optimize",
            why="It gets optimized properly. It takes very few passes to do it.",
        ),
    ],
    answer=(
        "About 25, and you will count the exact number later in this lesson. The pipeline is "
        "not 281 transformations in a row. It is mostly analysis, mostly looking for a shape "
        "that is not there, and moving on."
    ),
)
display(HTML(gate.render()))
""")

lesson.md(f"""
## What a pass is

Smaller than the word suggests. A pass is an object with a name, a
{term("gate")} that answers whether it should run, and an execute function that does the
work. That is the whole interface, and it is at
{cite("gcc/tree-pass.h:73@releases/gcc-16.2.0")}.

The name matters more than it looks like it should, because
{cite("gcc/tree-pass.h:44@releases/gcc-16.2.0")} says the name is a fragment of the dump file
name, and that if it starts with a star there is no dump. So the name is both the identity of
the pass and the only handle you have on it from the command line. When you write
`-fdump-tree-ccp1`, `ccp1` is that field.

Two more fields decide the shape of everything else:

```c
  /* A list of sub-passes to run, dependent on gate predicate.  */
  opt_pass *sub;

  /* Next in the list of passes to run, independent of gate predicate.  */
  opt_pass *next;
```

That is {cite("gcc/tree-pass.h:103@releases/gcc-16.2.0")}, and the two comments are the
important part. `next` runs whatever this pass's gate said. `sub` does not. Read
{cite("gcc/passes.cc:2769@releases/gcc-16.2.0")} and you can see it in two lines: run the
pass, and only if it returned true, recurse into its sub list. That loop, walking `next` and
recursing into `sub`, is the {term("pass manager")} doing the part of its job you can see
from a dump. Opening the dump, asking the gate and rechecking the IR afterwards all happen
one call down, in `execute_one_pass`.

So the pass list is a tree, not a list, and a pass with a gate can switch off a whole subtree.
""")

lesson.md(f"""
{claim("the pipeline is nested four deep, and two containers hold more than half of it between them")}.
""")

lesson.code("""
from collections import Counter

depths = Counter(p.depth for p in pipeline.all)
print("passes at each nesting depth:", dict(sorted(depths.items())))
print()

containers = sorted(pipeline.all, key=lambda p: -len(list(p.walk())))[:4]
for p in containers:
    inside = len(list(p.walk())) - 1
    print(f"{p.name:26} holds {inside:>3} passes, gate says {'ON' if p.enabled else 'OFF'}")
""")

lesson.md(f"""
`all_optimizations` is the one to remember. Its gate is one line at
{cite("gcc/passes.cc:567@releases/gcc-16.2.0")}:

```c
    return optimize >= 1 && !optimize_debug;
```

That is the difference between `-O0` and `-O1`, and 122 passes hang off it. There is no list
of things `-O0` skips maintained anywhere. There is one boolean, and a subtree.

## Three phases and a leftover

A pass name has a prefix, and the prefix says which representation the pass works on. `tree`
means GIMPLE, which is a historical name and not a mistake: GIMPLE is built out of tree nodes
and the dump flags were named before anybody called it GIMPLE. `rtl` means the low level
representation T07 gets to. `ipa` means the pass looks at more than one function at a time,
which is a different job again, because it runs when there is no current function at all.

A name with none of those prefixes belongs to no phase. Those are mostly containers and
warnings.
""")

lesson.code("""
for phase in ("tree", "rtl", "ipa"):
    on = [p for p in pipeline.by_phase(phase) if p.enabled]
    print(f"{phase:>5}  {len(pipeline.by_phase(phase)):>3} known, {len(on):>3} on at -O2")
none = [p for p in pipeline.all if p.phase is None]
print(f"{'none':>5}  {len(none):>3} known, {len([p for p in none if p.enabled]):>3} on at -O2")

print()
print("the four names that are not shaped like the others:")
for p in pipeline.all:
    if not p.named or " " in p.name:
        print(f"  {p.name!r:24} dump key {p.dump_key!r}")
""")

lesson.md("""
`rtl-rtl pre` is not a typo. A pass may carry a disambiguating prefix, a space, and then the
dump name, and GCC keeps only the part after the space when it names the dump file. So that
pass is dumped as `rtl-pre`. Two passes have no name at all and print as `(null)`.

Four awkward entries out of 395 is a low rate for a compiler, but the awkward ones are exactly
where a tidy parser goes wrong, and the count in the title of this lesson depends on getting
them right.

## ON and OFF

Now the interesting part of the listing, which is that the same 395 lines come back different
at every optimization level.
""")

lesson.md(f"""
{claim("-O3 turns on eight passes that -O2 does not, and -Os turns on one that -O2 does not, so the levels are not a slider")}.
""")

lesson.code("""
levels = {name: passes.parse(text) for name, text in record.pass_texts.items()}
order = ["-O0", "-O1", "-O2", "-O3", "-Os"]

print(f"{'level':>6}  {'on':>4}  {'tree':>5} {'rtl':>4} {'ipa':>4}")
for name in order:
    counts = Counter(p.phase for p in levels[name].enabled)
    print(
        f"{name:>6}  {len(levels[name].enabled):>4}  "
        f"{counts['tree']:>5} {counts['rtl']:>4} {counts['ipa']:>4}"
    )


def only_in(a, b):
    \"\"\"The passes on at a and off at b, which is the question a difference of counts hides.\"\"\"
    off = {p.name for p in levels[b].enabled}
    return sorted(p.name for p in levels[a].enabled if p.name not in off)


print()
print("on at -O3, off at -O2:", ", ".join(only_in("-O3", "-O2")))
print("on at -Os, off at -O2:", ", ".join(only_in("-Os", "-O2")))
print("on at -O2, off at -Os:", ", ".join(only_in("-O2", "-Os")))
""")

lesson.md("""
Read the last two lines together. `-Os` is not `-O2` with some passes taken away. It drops the
eight that make code bigger, vectorization and the loop transformations that go with it, and
it turns on `rtl-hoist`, which `-O2` leaves off because hoisting common code out of branches
costs time and saves space.

The levels are three different opinions about what a good compilation looks like, and the
counts hide that. A reader who only ever sees 281 against 274 concludes that `-Os` is a
slightly weaker `-O2`, which is the wrong idea to walk away with.

## ON does not mean it ran

This is the part of the listing people trust too much, and there are three separate reasons
not to.

**The gate is asked per function.** It takes a function as its argument. Two functions in one
file can get different answers, and the listing is one function's answers.

**A pass under a closed container never runs.** `sub` is gated, remember. If
`all_optimizations` says OFF, all 122 passes inside it are skipped, and the listing still
prints ON next to any of them whose own gate happens to say yes.
""")

lesson.md(f"""
{claim("60 of the 281 passes that printed ON at -O2 sit under a container that printed OFF, and not one of them left a dump behind")}.
""")

lesson.code("""
def under_a_closed_gate(pipeline):
    \"\"\"Passes that printed ON somewhere inside a container that printed OFF.\"\"\"
    found = []

    def walk(node, closed):
        if node.enabled and closed:
            found.append(node)
        for kid in node.children:
            walk(kid, closed or not node.enabled)

    for root in pipeline.roots:
        walk(root, False)
    return found


for name in order:
    shut = under_a_closed_gate(levels[name])
    top = levels[name].find("all_optimizations")
    print(
        f"{name:>6}  {len(levels[name].enabled):>4} printed ON, {len(shut):>3} of them shut in, "
        f"all_optimizations says {'ON' if top.enabled else 'OFF'}"
    )

shut = under_a_closed_gate(pipeline)
trees = [p for p in shut if p.phase == "tree"]
wrote = [p.name for p in trees if p.dump_key in record.dump_texts]
print()
print(f"at -O2, {len(trees)} of the {len(shut)} are tree passes, so a dump would be in here")
print("of those, the ones that produced a dump anyway:", wrote)
""")

lesson.md(f"""
The last line is the evidence. Every one of those passes said ON, every one of them would have
written a file if it had run, and the recording has 140 tree dumps in it and none of theirs.

**A gate can be asked too early.** This is the one that catches people. `-fdump-passes` is
printed near the start of compilation, and it works by calling each pass's own gate right
then, at {cite("gcc/passes.cc:963@releases/gcc-16.2.0")}. That is the same call
{cite("gcc/passes.cc:2578@releases/gcc-16.2.0")} makes later when it really runs the pass, so
for most passes the answer is the same. For a gate that depends on how far compilation has
got, it is not.

{
    claim(
        "the container holding the 29 passes that run after register allocation prints OFF "
        "at every optimization level, because its gate returns reload_completed and register "
        "allocation has not happened at the moment the listing is printed",
        unobservable="the recording holds tree dumps and the passes in question are RTL "
        "passes, so there is nothing in this notebook that could show them running. The "
        "citation is checked against the pinned tree on every push instead.",
    )
}. The gate is at {cite("gcc/passes.cc:687@releases/gcc-16.2.0")} and it is two lines long.

So the listing answers the question what would each pass say if asked right now, which is
close to but not the same as which passes will run. Keep it as a map, not as a receipt.

## The tape

Which brings us to the thing that is a receipt. A dump file only exists because a pass
actually ran and wrote it, so the dumps are evidence in a way the listing is not.

The tape is one cell per pass that is on, in pipeline order, with the dump for that pass
attached when there is one. A cell is marked as having changed the IR only when there is a
dump on both sides of it to compare. That is a third state, not a gap: most cells have no
evidence either way and say so.
""")

lesson.md(f"""
{claim("281 cells, 135 of them have a dump, 25 changed the IR of f, 109 left it exactly as they found it, and 147 cannot say")}.
""")

lesson.code("""
from gxray import gimple, tape


def parsed_dumps(record):
    \"\"\"Every dump in the recording that holds one function with basic blocks in it.

    Three of the 140 hold no function at all, because `debug`, `earlydebug` and `statistics`
    print something other than a function body. The GENERIC dump has a body and no blocks in
    it, and it is not GIMPLE, so it does not belong on a GIMPLE tape either.
    \"\"\"
    found = {}
    for key, text in record.dump_texts.items():
        functions = list(gimple.parse(text).functions.values())
        if len(functions) == 1 and functions[0].blocks:
            found[key] = functions[0]
    return found


dumps = parsed_dumps(record)
cells = tape.cells(pipeline, dumps)

print(f"{len(record.dump_texts)} dumps recorded, {len(dumps)} of them a function with blocks")
print(f"{len(cells)} cells, {len([c for c in cells if c.stats])} with a dump attached")
print()
print("changed the IR:      ", len([c for c in cells if c.changed is True]))
print("left the IR alone:   ", len([c for c in cells if c.changed is False]))
print("no evidence to say:  ", len([c for c in cells if c.changed is None]))
""")

lesson.md("""
109 passes ran, wrote a dump, and left the statements exactly as they found them. That is the
shape of the pipeline. Optimization is mostly a very long sequence of passes deciding that the
thing they are looking for is not here.

Two things about how that comparison is made, because both of them change the number.

What is compared is the statement text in block order, not the dump file. A dump carries a
header with the pass name in it, so two dumps of an identical function are never identical
files, and comparing the files would mark all 135 as changed.

Debug markers are left out of the comparison. The recording was made with `-g`, which puts a
`# DEBUG` line at every statement boundary, and those move whenever anything near them moves.
Counting them would mark almost every pass as having changed something and the tape would be
a solid block of colour saying nothing.

## The tape, to click on

Every cell, in order. Pick one and the IR at that point appears above it. The filter buttons
narrow it to the cells that changed something, or to one phase.
""")

lesson.code("""
from gxwidgets import PassTape

widget = PassTape(pipeline, dumps, function="f", options="-O2")
display(HTML(widget.render()))

# The same thing as text, so this cell proves something even where HTML does not render, such
# as in a diff or on a terminal.
print(widget.selected.label)
""")

lesson.md("""
Scroll the strip rather than reading it. The argument the widget is making is visual and it is
about density: a few hundred cells with a couple of dozen marked.

Here is the same data as a still picture, which is what goes in the book and what the
animation for this lesson draws from.
""")

lesson.code("""
from IPython.display import SVG

import gxmanim

picture = gxmanim.mobjects.pass_tape(cells, per_row=48)
display(SVG(gxmanim.svg.document(picture)))

print(picture.describe())
""")

lesson.md("""
The caption says 147 have nothing to compare against, which is the same 147 the cell above
counted, and it is one more than the number of cells with no dump. 146 of the 281 have no dump
at all. The extra one is `tree-omplower`, which has a dump and is the first one that does, so
there is nothing in front of it to compare it with. It gets counted with the cells the tape
cannot speak for rather than with the ones that changed nothing, because it genuinely does not
know, and that is the rule the whole drawing is built on.

## What the 25 actually did

Names first, then numbers. Three of the columns move: how many statements the function has,
how many basic blocks, and how many SSA names.
""")

lesson.code("""
print(f"{'':>4} {'pass':26} {'stmts':>5} {'blocks':>6} {'names':>5}   what moved")
previous = None
for cell in cells:
    if cell.stats is None:
        continue
    if cell.changed:
        moved = []
        for field in ("statements", "blocks", "names"):
            delta = cell.stats[field] - previous[field]
            if delta:
                moved.append(f"{field} {delta:+d}")
        print(
            f"{cell.index + 1:>4} {cell.name:26} "
            f"{cell.stats['statements']:>5} {cell.stats['blocks']:>6} {cell.stats['names']:>5}"
            f"   {', '.join(moved) or 'same counts, different code'}"
        )
    previous = cell.stats
""")

lesson.md("""
A few things worth noticing in that table.

`tree-cfg` is where the basic blocks appear, which is the pass T03 said was coming next. Before
it the function is a flat list and the block count is one. `tree-ssa` is where the SSA names
appear, all eight of them at once, and T05 is about that pass.

Then the block count oscillates for the rest of the run. Three blocks, five, seven, back to
three. That is not noise. The loop optimizer adds a preheader and a latch before it can work,
several passes run with those in place, and a cleanup takes them away again. A pass that
appears to have removed two blocks has usually removed two empty blocks that another pass
added for its own convenience.

The last row is `tree-optimized`, which is not a pass that optimizes anything. It is the pass
that dumps the final GIMPLE, and its cell is marked as changed because the cleanup before it
took the scaffolding back out.

## The picture of the tree

The nesting is the part that is hard to see in a listing, because indentation three spaces at
a time does not look like a tree. There is a drawing of it in
[`diagrams/gated-subtree.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t04-three-hundred-and-ninety-five-passes/diagrams/gated-subtree.excalidraw).
Open it at excalidraw.com and you can move things around. It shows the two pointers, `next`
and `sub`, and what a closed gate does to everything hanging off one of them.

## Boss fight

At the end of `tree-ssa` the function has a temporary in it called `_6`, left over from
gimplification. It is gone by the end. Find out where it went, and answer three things.

1. The pass whose dump is the first one with no `_N` temporary left in it
2. How many of the passes on at -O2 changed the IR of `f`
3. The one pass that is on at `-Os` and off at `-O2`

The first one is the real question and there is a way to do it that is not scrolling. Filter
the tape to the changing passes, look at the ones between `tree-ssa` and the middle of the
run, and check the dumps on each side of each candidate. You want the pass where `_6` is in
the dump before it and not in the dump after it.

Check yourself:

```text
python lessons/t04-three-hundred-and-ninety-five-passes/grade.py
```

or `just grade t04-three-hundred-and-ninety-five-passes`. It takes the answers on the command
line too, so `--pass ccp1 --changed 25 --only-os hoist` is a complete submission, and it
accepts the long name with the phase on the front as well. Every answer is read off the same
recording the lesson used.

## What to read next

T05 is SSA, which is the pass at cell 13 of the tape, the one where eight names appear at
once. It is the pilot lesson of the whole course and it is already written.

T06 goes after the ON and OFF in this listing and asks where it comes from. The answer is
four integers and a table of a hundred and fourteen entries, and it is why `-Os` and `-O2`
disagree about nine passes rather than one being weaker than the other.

M4 goes back through this list properly, a lesson per group of passes, with the tape as the
map. This lesson is the map. That one is the territory.
""")

raise SystemExit(lesson.save())
