"""T10. The whole map.

Nine lessons, nine slices. This one puts them on one page and asks whether the reader can
draw the thing from memory. There is no new machinery in it. Every widget, parser and drawing
it uses was built for an earlier lesson, and if this lesson needs something new then one of
the nine did not finish its job.

What is new is the program. T01 to T09 all read `l1.c`, four lines and one loop, because a
small program is what you want when you are learning to read a dump. `l1.c` has nothing for
the interprocedural passes to do and nothing for alias analysis to think about, so half the
pipeline runs on it and changes nothing. L2 is the smallest program that gives every phase
work: a struct, a pointer, a struct passed by value, and a static function called twice.

Two recordings. `t10-whole` is L2 at `-O2` with every tree dump, the five RTL dumps that name
a stage, the pass list, and the assembly with `-dp`. `t10-ladder` is the same program with
`-g` and the location carrying dumps, which is what joins a source line to what became of it.
Both are the local compiler, GCC 16.2.0 for aarch64 Darwin.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t10-the-whole-map",
    "t10",
    title="The whole map",
    milestone="M1",
    summary=(
        "One program through the whole compiler, with the pass tape and the IR ladder side "
        "by side, the fourteen stages you would draw from memory and which five of them are "
        "not passes, and one expression traced from the source line to the instruction"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T10. The whole map

{badge}

Nine lessons in. You have watched the {term("driver")} decide which programs to run, seen
{term("GENERIC")} become {term("GIMPLE")}, watched the {term("pass manager")} run a few hundred
passes, met {term("SSA")} and watched it come apart again, seen {term("RTL")} appear, watched
the {term("register allocation", "allocator")} hand out real registers, and read the pass that
writes the file.

Each of those was a slice. This lesson is the whole thing, once, on one program, and the
question it asks is the only one that matters at the end of a part: could you draw this from
memory and be right?

The way to find out is not to read another explanation. It is to put the pipeline in front of
you with the evidence attached, and then answer questions that a confident wrong model gets
wrong. That is what the rest of this page is.

You need a browser. There is no compiler here and no network.

**What you come away with**

- The fourteen stages, in order, and which five of them are not passes at all
- The honest ratio: how many passes ran, and how many of them changed anything
- Being able to read the tape and the ladder together, which is the same run seen two ways
- One expression followed from a source line to the instruction, naming every pass on the way
- Ten questions that catch the models that feel right and are not
""")

lesson.setup()

lesson.md("""
## A program with work in it

`l1.c` was the right program for nine lessons and it is the wrong one for this lesson. Four
lines, one function, one loop, no pointers. There is nothing in it for the interprocedural
passes to do, nothing for alias analysis to be careful about, and no call worth inlining, so a
large part of the pipeline runs over it and correctly changes nothing.

L2 is the smallest program where every phase has something to do.
""")

lesson.code("""
record = gxray.corpus_store.load("t10-whole")

print(f"{record.compiler} for {record.target}")
print(f"recorded {record.recorded} with {' '.join(record.args)}")
print()
print(record.source)
""")

lesson.md("""
Four things in twenty five lines, and each one wakes up a different part of the compiler.

- `struct P` passed by value as `q`, which the middle end would rather not keep in memory
- `pts` as a pointer, which is a question for alias analysis every time it is read
- `dist2` declared `static` and called twice, which is a decision for the inliner
- a loop with a bound the compiler cannot see, which is what the loop passes are for

The function we follow is `nearest`. `dist2` is going to stop existing, and where it goes is
the first interesting thing on the map.

## The fourteen stages

Here is the map, in words. Fourteen stages, in the order a compilation goes through them.

```text
 1  the driver          gcc works out which programs to run
 2  preprocess          includes, macros, line markers
 3  parse               C text becomes GENERIC, a tree
 4  gimplify            GENERIC becomes GIMPLE, three address form
 5  build the CFG       statements become basic blocks and edges
 6  into SSA            every variable becomes a numbered name written once
 7  early optimizers    the cheap cleanups, run per function before anything global
 8  interprocedural     the whole program at once, which is where inlining happens
 9  tree optimizers     the long middle, about two hundred passes on GIMPLE
10  expand              GIMPLE becomes RTL, and SSA comes apart
11  RTL optimizers      combine, scheduling, and the rest of the back end
12  register allocation pseudo registers become hard registers
13  final               the insn chain becomes text
14  assemble            as turns the text into an object file
```

That is the diagram to be able to draw. Before checking whether you can, one thing about the
list is worth pinning down, because it is where most wrong models come from.

Five of those fourteen are not passes. The {term("pass manager")} has never heard of them, they
have no entry in `passes.def`, and `-fdump-passes` will never print them. If your model of GCC
is the pass list, your model is missing the front end and the assembler.
""")

lesson.md(f"""
{claim("nine of the fourteen stages are passes in the list, and five are not")}.
""")

lesson.code("""
from gxray import passes

pipeline = passes.parse(record.pass_texts["-O2"])

STAGES = [
    ("the driver", ""),
    ("preprocess", ""),
    ("parse", ""),
    ("gimplify", ""),
    ("build the CFG", "tree-cfg"),
    ("into SSA", "tree-ssa"),
    ("early optimizers", "tree-early_optimizations"),
    ("interprocedural", "ipa-inline"),
    ("tree optimizers", "tree-optimized"),
    ("expand", "rtl-expand"),
    ("RTL optimizers", "rtl-combine"),
    ("register allocation", "rtl-ira"),
    ("final", "rtl-final"),
    ("assemble", ""),
]

print(f"{'stage':<22}{'a pass?':<10}where it is in the list")
for n, (stage, anchor) in enumerate(STAGES, start=1):
    if not anchor:
        print(f"{n:>2}  {stage:<22}{'no':<10}not a pass, nothing in passes.def")
        continue
    at = [i for i, p in enumerate(pipeline.enabled, start=1) if p.name == anchor]
    print(f"{n:>2}  {stage:<22}{'yes':<10}{anchor} runs {at[0]} of {len(pipeline.enabled)}")

assert sum(1 for _, a in STAGES if a) == 9
""")

lesson.md(f"""
The four at the ends are the ones people forget. The driver is a separate program that runs
other programs, which is T01. Preprocessing and parsing happen inside `cc1` before the pass
manager starts, and the two dumps that show them, `tree-original` and `tree-gimple`, are
written by the front end rather than by a pass. The assembler is not GCC at all.

Gimplification is the interesting one, because it feels like it should be a pass. It is a
recursive walk called once per function on the way in, `gimplify_function_tree` at
{cite("gcc/gimplify.cc:21974@releases/gcc-16.2.0")}, and by the time the first entry in
`passes.def` runs, the function is already GIMPLE. The pass list starts at
{cite("gcc/passes.def:30@releases/gcc-16.2.0")} and the thing it starts with is lowering, not
parsing.

The two entries in that file worth memorising are
{cite("gcc/passes.def:59@releases/gcc-16.2.0")}, which is where the function goes into SSA,
and {cite("gcc/passes.def:460@releases/gcc-16.2.0")}, which is where it becomes RTL. Everything
before the first is not SSA yet, everything after the second is not GIMPLE any more, and those
two lines are the two boundaries the whole middle end is arranged around.

## What actually ran

Now the number that changes how people think about optimizers.
""")

lesson.md(f"""
{claim("281 passes ran on this function and 36 of them changed it")}.
""")

lesson.code("""
from gxray import gimple, tape

# Only the tree dumps hold a function body the GIMPLE parser can read. A `-graph` key is a
# dot file sitting beside a tree dump, and the RTL dumps are a different language.
dumps = {}
for key, text in record.dump_texts.items():
    if not key.startswith("tree-") or key.endswith("-graph"):
        continue
    found = gimple.parse(text).functions.get("nearest")
    if found is not None:
        dumps[key] = found

cells = tape.cells(pipeline, dumps)
counted = {
    "enabled": len(cells),
    "with a dump to measure": len([c for c in cells if c.stats]),
    "changed the function": len([c for c in cells if c.changed]),
    "left it exactly as found": len([c for c in cells if c.changed is False]),
    "no evidence either way": len([c for c in cells if c.changed is None]),
}
for label, n in counted.items():
    print(f"{n:>5}  {label}")
""")

lesson.md("""
Two hundred and eighty one passes are enabled at `-O2`. A hundred and thirty five of them wrote
a dump we can measure. Thirty six changed the function. Ninety eight ran and left it byte for
byte as they found it.

That third number is the one worth sitting with. Two thirds of the passes that we can check did
nothing at all, and that is the normal, healthy case. A pass is a question asked of a function,
and most questions have the answer no. `pass_sincos` looks for a sine and a cosine of the same
angle. There is not one here. It runs, it looks, it says no, and it costs a few microseconds.

The hundred and forty seven with no evidence are a third state and not a gap in the data. Most
passes have no dump at all, so there is nothing to compare on either side of them, and the tape
says so rather than guessing. A drawing that has no place to put "we do not know" ends up
lying, which is why every widget in this book has one.

Here is the tape.
""")

lesson.code("""
from IPython.display import HTML, display

from gxwidgets import PassTape

tape_widget = PassTape(pipeline, dumps=dumps, function="nearest", options=" ".join(record.args))
display(HTML(tape_widget.render()))

# The same conclusion as text, so this cell says something where HTML does not render.
facts = tape_widget.data()
print(f"{len(facts['cells'])} cells on the tape, {len(facts['panels'])} of them with a dump")
for mark, label in [("1", "changed it"), ("0", "left it alone"), ("?", "no evidence")]:
    print(f"  {label:<16}{len([c for c in facts['cells'] if c['changed'] == mark])}")
""")

lesson.md(f"""
Click any cell and the panel underneath says what that pass is, whether it changed anything,
and how many statements, blocks and names were left afterwards. The `changed` filter cuts two
hundred and eighty one down to the thirty six that did something, which is the version of this
picture worth remembering.

Look at where the thirty six are. They are not spread evenly. There is a cluster in the early
optimizers, one enormous event at `einline`, and then a long thin scatter through the tree
passes with a second cluster around the loop optimizer. That shape is the same on almost every
function, and it is why `-O2` is worth roughly what it is worth.

## The ladder, which is the same run seen from the source

The tape is the compiler's view: time on one axis, one cell per pass. The
{term("dump file", "IR ladder")} is the programmer's view: one row per source line, and what
that line turned into at each of four levels.

They are the same compilation. The tape says when, the ladder says what.
""")

lesson.md(f"""
{claim("the ladder for nearest has rows for source lines that are inside dist2")}.
""")

lesson.code("""
from gxray import locs

ladder_record = gxray.corpus_store.load("t10-ladder")
ladder = locs.ladder(
    ladder_record.source,
    generic=ladder_record.dump_texts["tree-original"],
    gimple=ladder_record.dump_texts["tree-optimized"],
    rtl=ladder_record.dump_texts["rtl-expand"],
    asm=ladder_record.asm,
    function="nearest",
)

source = ladder_record.source.splitlines()
print(f"{'line':>5}  {'in':<8}{'generic':>8}{'gimple':>7}{'rtl':>5}{'asm':>5}   source")
for rung in ladder.rungs:
    owner = "dist2" if 5 <= rung.line <= 11 else "nearest"
    counts = "".join(
        f"{len(rung.at(level)):>{w}}" for level, w in zip(locs.LEVELS, (8, 7, 5, 5), strict=True)
    )
    print(f"{rung.line:>5}  {owner:<8}{counts}   {source[rung.line - 1].strip()}")
""")

lesson.md(f"""
Lines 8, 9 and 10 are the body of `dist2`. `dist2` is `static`, it is called twice, and by the
time the optimized dump is written it does not exist. Its statements are in `nearest`, and they
brought their source locations with them, so they show up on the ladder of a function they were
never written inside.

That is what inlining looks like from the source end, and it is the single most useful thing
this lesson has to say about reading a dump. A location in a GIMPLE statement tells you where
the programmer wrote it, not which function it currently lives in.

`ipa_inline` at {cite("gcc/ipa-inline.cc:2822@releases/gcc-16.2.0")} is the pass that decided
it, and it is one of the twenty four {term("middle end", "interprocedural")} passes that look at
the whole translation unit rather than one function at a time. Note that the early inliner had
already done most of the work here, before the IPA phase even started, which is why the tape
shows the big jump at `einline` rather than at `ipa-inline`.

Here is the ladder as a widget. Click a source line, and the four panels show what that line is
at each level.
""")

lesson.code("""
from gxwidgets import IRLadder

ladder_widget = IRLadder(ladder, line=10)
display(HTML(ladder_widget.render()))

shape = ladder_widget.data()
print(f"{len(shape['lines'])} source lines with anything on them")
for level, n in shape["totals"].items():
    print(f"  {locs.LEVEL_NAMES[level]:<10}{n}")
""")

lesson.md("""
## One pass, two dumps

A single dump is data. Two dumps side by side are a transformation, and that is the only shape
in which you can honestly say a pass did something.

The problem with doing it by hand is that diffing two GIMPLE dumps as text marks almost every
line. SSA names get renumbered whenever anything is created or deleted, and branch
probabilities are printed three different ways over the course of a compilation. Neither of
those is the pass. So the comparison is done on the text with the numbers taken off, and the
real lines are what you see.

Start with the pass that makes the point. `release_ssa` shows up on the tape as a pass that
changed the function. Here is what it changed.
""")

lesson.md(f"""
{claim("release_ssa changed twenty three lines and every one of them only moved a number")}.
""")

lesson.code("""
from gxray import diff

order = [p.name for p in pipeline.enabled if p.name in dumps]
before = dumps[order[order.index("tree-release_ssa") - 1]]
after = dumps["tree-release_ssa"]

renumbering = diff.compare(
    before, after, before_name=order[order.index("tree-release_ssa") - 1], after_name="release_ssa"
)
print(renumbering)
print(f"{len(renumbering.renumbered)} of the {len(renumbering.moved)} moved rows only renumbered")
""")

lesson.code("""
from gxwidgets import DumpDiff

display(HTML(DumpDiff(renumbering).render()))
""")

lesson.md(f"""
Twenty three changed lines, twenty three of them renumbering. `release_ssa` at
{cite("gcc/tree-ssanames.cc:983@releases/gcc-16.2.0")} hands unused SSA version numbers back to
a free list so the next pass can reuse them, and reusing them means the survivors get
renumbered. Nothing about the program changed. A diff that called that twenty three changes
would be telling the truth about the text and lying about the compilation.

That is the whole reason this widget normalizes before it compares, and the reason a row where
only the numbers moved is drawn plain rather than coloured.

Now the pass that did something.
""")

lesson.md(f"""
{claim("einline is the pass that put dist2 inside nearest, and it is the largest single change")}.
""")

lesson.code("""
inlining = diff.compare(
    dumps[order[order.index("tree-einline") - 1]],
    dumps["tree-einline"],
    before_name=order[order.index("tree-einline") - 1],
    after_name="einline",
)
print(inlining)
print(f"{len(inlining.renumbered)} of the {len(inlining.moved)} moved rows only renumbered")
print()

biggest = max(
    ((c.name, c.stats["statements"]) for c in cells if c.changed),
    key=lambda pair: pair[1],
)
print(f"the largest function on the tape after any pass: {biggest[0]}, {biggest[1]} statements")
""")

lesson.code("""
display(HTML(DumpDiff(inlining).render()))
""")

lesson.md("""
Twenty statements appear that were not there and none of the moved rows is renumbering. That is
what a transformation looks like next to a bookkeeping pass, and the two sit a few cells apart
on the same tape with nothing to tell them apart until you look.

The other number that cell printed is worth a second. The largest the function ever gets is
fifty eight statements, at `ifcvt`, and the dump at the end of the tree passes has thirty four.
The IR grows before it shrinks, which is the shape of every real optimizer: inline first so
there is something to work with, then spend two hundred passes taking it back apart.

## Following one expression

Here is the exercise the whole lesson is for. Take one expression and follow it all the way
down.

```c
return dx * dx + dy * dy;
```

Line 10 of `l2.c`, inside `dist2`, which is a function that will not exist by the end. Two
multiplies and an add. Follow the multiplies, because a square is easy to find in a dump: it is
the statement that multiplies a name by itself.
""")

lesson.md(f"""
{claim("five tree passes changed the squares, and one of them only renumbered them")}.
""")

lesson.code('''
import re

SQUARE = re.compile(r"= (\\S+) \\* \\1;")


def squares(f):
    """Every statement in this function that multiplies a name by itself."""
    return tuple(
        s.text.strip()
        for b in f.ordered_blocks
        for s in b.stmts
        if not s.is_debug and SQUARE.search(s.text)
    )


seen, trace = None, []
for name in order:
    now = squares(dumps[name])
    if now != seen:
        trace.append((name, now))
        seen = now

for name, now in trace:
    print(f"{name:<26}{len(now)} square(s)")
    for text in now:
        print(f"      {text}")
''')

lesson.md("""
The first row is where we came in: no squares in `nearest` at all, because at that point they
were still inside `dist2`. After that, five events, and every one of them is a different kind
of thing happening.

- **`einline`** puts the squares into `nearest` for the first time. Four of them, not two, and
  the four is the point: the call before the loop and the call inside the loop are two call
  sites, and each one got its own copy of the body.
- **`release_ssa`** changes all four and changes nothing. Same statements, new numbers.
- **`sink1`** has the same four in a different order. Sinking moves a computation down to be
  nearer the place that uses it, so the loop does not pay for it when the branch skips it.
- **`ifcvt`** makes it six. If-conversion writes a branch free copy of the loop body for the
  vectorizer to look at, so for a few passes there are two versions of the loop in the IR.
- **`vect`** puts it back to four. The vectorizer looked, decided this loop was not worth
  vectorizing, and the copy `ifcvt` made went away with it.

A reader who expected a straight line down the pipeline gets two surprises there. Work gets
duplicated on purpose so that a later pass has something to measure, and it gets thrown away
again when the answer is no. The IR is not monotonically improving. It is being tried on.

Then GIMPLE runs out.
""")

lesson.md(f"""
{claim("combine is the pass that turned the multiply and the add into one insn")}.
""")

lesson.code("""
from gxray import rtl

print(f"{'dump':<14}{'insns':>7}{'code':>7}{'mult':>7}{'fused':>7}")
for key in ["rtl-expand", "rtl-combine", "rtl-ira", "rtl-reload", "rtl-final"]:
    f = rtl.parse(record.dump_texts[key], key).only()
    mult = [i for i in f.code if "mult" in str(i.pattern)]
    fused = [i for i in mult if "plus" in str(i.pattern)]
    print(f"{key:<14}{len(f.insns):>7}{len(f.code):>7}{len(mult):>7}{len(fused):>7}")
""")

lesson.md(f"""
Zero fused at `expand`, two after `combine`, and they survive to the end. `combine_instructions`
at {cite("gcc/combine.cc:1123@releases/gcc-16.2.0")} takes two or three insns whose results feed
each other, builds the expression that all of them together compute, and asks the machine
description whether there is a single pattern that matches it. On aarch64 there is, because the
hardware has a multiply-add, and so three insns become two.

That is the last decision anybody makes about this expression. The allocator picks registers for
it, `final` prints it, and the file says so.
""")

lesson.md(f"""
{claim("the fused insn is printed by a pattern called maddsi and the file says which")}.
""")

lesson.code("""
from gxray import asm

listing = asm.parse(record.asm_texts["-O2 -dp"], "t10-whole")
last = dumps["tree-optimized"]
statements = [s for b in last.ordered_blocks for s in b.stmts if not s.is_debug]

print(f"{len(statements)} statements at the end of the tree passes")
print(f"{listing.counts()['total']} lines of assembly, {len(listing.insns)} instructions")
print()
for line in listing.insns:
    if line.pattern in ("mulsi3", "maddsi", "subsi3"):
        print(f"  {line.text.strip().split(';')[0].strip():<26}{line.pattern}")
""")

lesson.md(f"""
`mul` for one square, `madd` for the other square and the add together. Two `sub` instructions
above them, which are `a->x - b->x` and `a->y - b->y` from lines 8 and 9. Four instructions for
the whole of `dist2`, appearing twice because it was inlined twice.

So the trace, end to end, is this:

```text
l2.c:10   return dx * dx + dy * dy;    written inside dist2
einline   the statements move into nearest, twice over
release_ssa  the names are renumbered and nothing else
sink1     one of them moves closer to its use
ifcvt     a second copy appears, for the vectorizer to look at
vect      the vectorizer says no and the copy goes
expand    the mults and the adds are separate insns, none of them fused
combine   a mult and a plus fuse into one insn, twice over
ira, lra  the registers become w3, w4, w7
final     maddsi prints `madd w7, w7, w7, w3`
```

Eleven lines, every one of them checkable from the recording, and none of it is a story about
what compilers generally do.

## The picture

The whole pipeline, drawn, with the fourteen stages and what each one holds, is in
[`diagrams/the-whole-map.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t10-the-whole-map/diagrams/the-whole-map.excalidraw).
Open it at excalidraw.com, delete the labels, and try to put them back. That is the T0 exercise
for this lesson and it is worth doing on paper first.

Two stills from the notebook side, which are the tape and the flow as shapes rather than as
widgets.
""")

lesson.code("""
from IPython.display import SVG

import gxmanim

drawn = gxmanim.mobjects.pass_tape(cells, title="nearest, 281 passes at -O2")
display(SVG(gxmanim.svg.document(drawn)))
print(drawn.describe().splitlines()[0])
print(drawn.caption)
""")

lesson.code("""
from gxray import cfg

graph = cfg.parse(ladder_record.dump_texts["tree-optimized-graph"])["nearest"]
flow = gxmanim.mobjects.cfg_view(graph)
display(SVG(gxmanim.svg.document(flow)))
print(flow.describe().splitlines()[0])
print(flow.caption)
""")

lesson.md("""
## Ten questions

These are not a quiz. Every one of them has a plausible wrong answer that a reader who has done
the first nine lessons will find attractive, and the point of the exercise is to find out which
of those you believe. Commit to an answer before you open the reveal. A prediction you did not
make is not a prediction.
""")

lesson.code("""
from gxwidgets import PredictGate

QUESTIONS = [
    (
        "GCC ran 281 passes on this function at -O2. Roughly how many changed it?",
        [
            ("About a tenth of them", ""),
            (
                "Nearly all of them, that is what the passes are for",
                "Thirty six of the hundred and thirty five we can measure changed anything. A "
                "pass is a question, and most questions have the answer no.",
            ),
            (
                "About half",
                "Still too many. Ninety eight of the measured passes left the function byte for "
                "byte as they found it.",
            ),
        ],
        "Thirty six of two hundred and eighty one, and ninety eight measured passes did nothing.",
    ),
    (
        "dist2 is static and called twice. After inlining, how many copies of `dx * dx` "
        "are in nearest?",
        [
            ("Four", ""),
            (
                "Two, one per call site",
                "Two call sites, but the expression has two squares in it, `dx * dx` and "
                "`dy * dy`. Two call sites times two squares is four.",
            ),
            (
                "One, the inliner would share the body",
                "Inlining is copying. There is no sharing, which is exactly why it costs code "
                "size and why the inliner has a budget.",
            ),
        ],
        "Four. Two call sites, and each copy has both squares in it.",
    ),
    (
        "Which pass turned the multiply and the add into a single madd instruction?",
        [
            ("combine", ""),
            (
                "final, when it printed the assembly",
                "`final` is a printer. By the time it runs, which instruction to use was "
                "decided, and the fused insn is already in the chain.",
            ),
            (
                "the instruction selector during expand",
                "Expand produced the multiplies and the adds as separate insns. None of the "
                "four mults is fused in the expand dump and two of them are in the next one.",
            ),
        ],
        "combine. Zero fused insns in the expand dump, two in the combine dump.",
    ),
    (
        "Ninety eight passes ran and changed nothing. What does that tell you about them?",
        [
            ("Nothing is wrong. Most passes do not apply to most functions", ""),
            (
                "They are wasted work and -O2 would be faster without them",
                "You cannot know a pass does not apply without running it. The looking is the "
                "pass, and it is cheap compared to the transformation it is looking for.",
            ),
            (
                "They are disabled and the list is showing them anyway",
                "Disabled passes are a different thing and the tape shows them separately. "
                "These ran.",
            ),
        ],
        "They ran, looked, and found nothing to do. That is the normal case.",
    ),
    (
        "Source line 8 is inside dist2. Whose IR ladder does it appear on?",
        [
            ("nearest, because the statements were inlined into it", ""),
            (
                "dist2, that is where it was written",
                "By the optimized dump, `dist2` does not exist. Its statements are in "
                "`nearest`, and a statement carries the location it was written at.",
            ),
            (
                "Both, the location is duplicated",
                "There is only one function left. A location says where the programmer wrote "
                "the statement, not which function it currently lives in.",
            ),
        ],
        "nearest. Inlining copies the statements and the statements carry their locations.",
    ),
    (
        "Does the control flow graph still exist after expand?",
        [
            ("Yes. RTL has basic blocks and edges too", ""),
            (
                "No, the CFG is a GIMPLE thing and expand flattens it",
                "The RTL dumps print basic blocks with the same numbering. The CFG survives all "
                "the way to `bbro`, which is a pass that reorders it.",
            ),
            (
                "Only until the register allocator runs",
                "The allocator needs the CFG more than most passes do, because liveness is a "
                "question about paths through the graph.",
            ),
        ],
        "Yes. The insn chain and the CFG coexist for the whole back end.",
    ),
    (
        "q is a struct passed by value. Which pass decided it would live in registers?",
        [
            ("esra, long before RTL existed", ""),
            (
                "The register allocator, that is its job",
                "The allocator hands out registers for pseudos that already exist. By the time "
                "it runs, `q` has been two separate scalars for a hundred and fifty passes.",
            ),
            (
                "expand, when it built the RTL",
                "Expand built pseudos for whatever GIMPLE handed it. What it was handed was "
                "`q$x` and `q$y`, two scalars, because SRA had already taken the struct apart.",
            ),
        ],
        "esra. Scalar replacement of aggregates splits the struct into `q$x` and `q$y`.",
    ),
    (
        "The optimized GIMPLE has 34 statements. Is that roughly the instruction count?",
        [
            ("No, and there is no fixed ratio in either direction", ""),
            (
                "Yes, GIMPLE is three address form so it is close to one to one",
                "Twenty five instructions came out of thirty four statements, and the mapping "
                "is not one to one in either direction. One statement can become several "
                "instructions and several can become one.",
            ),
            (
                "Yes, but with about a third more instructions for the addressing",
                "That is the right instinct for the wrong reason. Here the count went down, "
                "because combine fused insns and some statements were addressing arithmetic "
                "that folded into a load.",
            ),
        ],
        "Thirty four statements, twenty five instructions, and no fixed relationship.",
    ),
    (
        "release_ssa is on the tape as a pass that changed the IR. What did it change?",
        [
            ("Only the SSA version numbers", ""),
            (
                "It deleted dead SSA names, so some statements went",
                "No statement was added or removed. Twenty three lines differ and all twenty "
                "three differ only in their numbers.",
            ),
            (
                "It took the function out of SSA form",
                "Out of SSA happens at expand, two hundred passes later. This pass recycles "
                "version numbers so the next pass can reuse them.",
            ),
        ],
        "Only the numbers. Twenty three changed lines, twenty three of them renumbering.",
    ),
    (
        "If you compile without -g, which of the fourteen stages stops happening?",
        [
            ("None of them", ""),
            (
                "The debug passes, so the pipeline is shorter",
                "There are passes that only do something with `-g`, but they run either way. "
                "What changes is what they emit, not whether the stage is there.",
            ),
            (
                "Nothing changes at all, -g is a linker flag",
                "`-g` changes plenty. It puts a location on every statement, adds debug markers "
                "to the IR, and makes GCC emit several hundred lines of `.debug_info`. It does "
                "not remove a stage.",
            ),
        ],
        "None. `-g` changes what is recorded, not which stages run.",
    ),
]

gates = [
    PredictGate(question, options, answer=answer, id=f"t10-q{n}")
    for n, (question, options, answer) in enumerate(QUESTIONS, start=1)
]
for gate in gates:
    display(HTML(gate.render()))

print(f"{len(gates)} questions. Answers are in each widget behind the reveal.")
""")

lesson.md(f"""
## Where to read more

`BP-PIPELINE` in
[`blueprints/BP-PIPELINE.md`](https://github.com/tamnd/gcc-internals/blob/main/blueprints/BP-PIPELINE.md)
is the reference version of this lesson, and it is the first blueprint in the book to reach
complete. It has all fourteen stages written out with the file and function that implements
each, the two boundaries in `passes.def`, the full `-O2` pass list for GCC 16.2 with the phase
and nesting of every entry, and a table of which dumps exist and which pass writes them.

The pass manager itself is `execute_pass_list` at
{cite("gcc/passes.cc:2777@releases/gcc-16.2.0")}, which is fourteen lines long and is the whole
of what "GCC runs its passes" means.

## Boss fight

Follow `dx * dx + dy * dy` from the source line to the instruction, and name the passes.

Four questions. The first is the long one: every tree pass that changed the statements
computing the expression, in order. The other three are the fusing pass, the machine
description pattern that printed the result, and the count of passes that changed the function
at all.

The grader reads the recording and works the answers out, so there is no answer key anywhere in
the repository. Re-record against a newer compiler and it marks against whatever that compiler
did.

```text
python lessons/t10-the-whole-map/grade.py
```

or `just grade t10-the-whole-map`. It takes the answers on the command line too, so
`--trace einline,release_ssa,sink1,ifcvt,vect --fused combine --pattern maddsi --changed 36` is
a complete submission.

The one to think about is the first. Two of the five are not what a reader means by "touched
it", and working out which two, and why they are on the list anyway, is the point of the
question.

## What to read next

That is M1. Ten lessons, one program each, and the map at the end.

M2 goes back to the beginning and reads the front end properly: the C parser, GENERIC as a data
structure, gimplification as an algorithm rather than an arrow on a diagram, and what a language
front end actually has to provide. M5 is the back end, where T07 to T09 turn into five lessons
on the machine description, the recognizer, scheduling and target hooks.

If you want to keep going in a straight line instead, the two beginner lessons Z01 and Z02 are
the on ramp to all of it, and they assume nothing.
""")

raise SystemExit(lesson.save())
