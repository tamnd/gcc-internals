"""T02. The five faces of one function.

The establishing shot for the whole book. One nine line C function, shown at every level GCC
turns it into, with the source line as the thread running through all of them.

Everything here comes from the `l1-O2` corpus entry, which was recorded with `-g` and the
`lineno` dump modifier. Without those two things there are no locations on the statements and
the ladder cannot be built at all, which is worth knowing before anybody tries to rebuild the
corpus without them.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t02-five-faces",
    "t02",
    title="The five faces of one function",
    milestone="M1",
    summary=(
        "That there are four representations of your code inside GCC and not one, what each "
        "of them is for, how to line them up against the source, and why the line a "
        "statement came from is not always the line its instructions end up on"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T02. The five faces of one function

{badge}

T01 ended at the door of {term("cc1")}. This lesson goes in.

Inside `cc1` your function is never one thing. It is turned into a {term("tree")}, then into
a much flatter kind of tree, then into something that looks like machine code with the
register numbers left blank, then into text an assembler can read. Four representations, one
after another, and the source you wrote makes five.

People find this out slowly and in pieces, usually from an error message that mentions
`_1 = n_3(D) + 1` when they have never written a variable called `_1`. Seeing all five at
once, side by side, on a function short enough to hold in your head, saves a lot of that.

You need a browser. There is no compiler here and no network.

**What you come away with**

- Knowing the names {term("GENERIC")}, {term("GIMPLE")}, {term("RTL")} and assembly, and
  roughly what each one is for
- Being able to point at a line of C and see what it became at each level
- Knowing that the mapping between levels is source locations and nothing else, and where
  that mapping gets thin
- Having seen a statement disappear from one level and reappear on a different line at the
  next, which is the thing that makes debuggers hard
""")

lesson.setup()

lesson.md("""
## One function, recorded four ways

The program is L1, which is the loop this course uses for almost everything. Nine lines, one
loop, one accumulator.

The recording was made with `-O2 -g` and every dump asked for with the `lineno` modifier.
That combination is the whole trick. `-g` makes GCC keep track of where things came from, and
`lineno` makes the dumps print it, so every statement in every dump arrives with a file and a
line stuck to the front of it.
""")

lesson.code("""
backend = gxray.corpus("l1-O2")
print(gxray.banner(backend))
print(gxray.L1)
""")

lesson.md(f"""
Four dumps go into the ladder, one per level. `tree-original` is GENERIC, straight out of the
C front end and before anything has been done to it. `tree-optimized` is GIMPLE at the end of
the tree passes, which is the GIMPLE that becomes RTL. `rtl-expand` is RTL at the moment it
is created. The assembly is what `cc1` finally wrote out.

{claim("every item at every level carries a file and a line, and that is the only field the four levels have in common")}.
""")

lesson.code("""
from gxray import locs

record = gxray.corpus_store.load("l1-O2")
ladder = locs.ladder(
    record.source,
    generic=record.dump_texts["tree-original"],
    gimple=record.dump_texts["tree-optimized"],
    rtl=record.dump_texts["rtl-expand"],
    asm=record.asm,
    function="f",
)

print(ladder, "\\n")
rung = ladder.rung(7)
print("source line 7:", rung.source.strip())
for level in ladder.levels:
    for item in rung.at(level):
        print(f"  {locs.LEVEL_NAMES[level]:9} {item.loc}  {item.text.splitlines()[0]}")
""")

lesson.md("""
One line of C, four items, four different notations, one location on each. Nothing else about
those four items is alike. GENERIC has an assignment expression, GIMPLE has a statement with
an SSA name on the left, RTL has an `insn` with a `plus:SI` in it, and the assembly has an
`add`. The only thing joining them is `l1.c:7:7`.

That is not a simplification for the sake of the lesson. It really is the only join. Nothing
carries a pointer back to the GIMPLE statement it came from, so a debugger, a profiler, a
sanitizer and this ladder are all doing the same thing: reading locations and hoping they
survived.

## One line, four answers

Now the same thing for every line at once. The number in each column is how many items at
that level came from that line of C.
""")

lesson.md(f"""
{claim("the loop header line is the busiest line in the function at all four levels")}.
""")

lesson.code("""
print(f"{'line':>4}  {'GENERIC':>7} {'GIMPLE':>6} {'RTL':>3} {'asm':>3}   source")
for rung in ladder.rungs:
    n = rung.counts()
    print(
        f"{rung.line:>4}  {n['generic']:>7} {n['gimple']:>6} {n['rtl']:>3} {n['asm']:>3}"
        f"   {rung.source.strip()}"
    )
""")

lesson.md("""
Read down the columns and a few things stand out.

The count goes up and down rather than up. GIMPLE has fewer items than GENERIC here, because
the front end's tree for a `for` loop is five nested things and GIMPLE has no loop construct
at all, just a compare and a jump. Then RTL has more than GIMPLE, because one GIMPLE statement
often needs two machine operations. Then the assembly matches RTL almost exactly, because by
that point the hard part is over and the last step is mostly printing.

The `for` line is the busiest at every level, which is fair, since it is three statements
wearing a trenchcoat: an initialisation, a test and an increment.

Line 5 is `int s = 0;`, which is one assignment, and it has two of everything below GENERIC.
That is not double counting. The function has two ways out, one for a loop that ran and one
for a loop that never started, and the zero has to be there on both, so the compiler made two
copies of it. Duplicating code to avoid a branch is such an ordinary thing for an optimizer to
do that it happens here, in a function with one statement in the loop.

And two of the rows are strange. Look at line 8 and line 9.

## Where the return went
""")

lesson.md(f"""
Line 8 is `return s;` and line 9 is the closing brace.
{claim("the return statement has nothing at all at the RTL and assembly levels, and the closing brace has two of each")}.
""")

lesson.code("""
for line in (8, 9):
    rung = ladder.rung(line)
    print(f"line {line}: {rung.source.strip()!r}")
    print(f"  nothing at: {', '.join(rung.empty_levels) or 'no level, it is on all four'}")
    for level in ladder.levels:
        for item in rung.at(level):
            print(f"  {locs.LEVEL_NAMES[level]:9} {item.text.splitlines()[0]}")
    print()
""")

lesson.md("""
The `return` exists at both tree levels and then vanishes. The closing brace, which is not a
statement and does nothing, has two machine instructions on it, and they are both `ret`,
because of the two exits from the paragraph above.

Nothing was lost. What happened is that returning got split in two. Putting the value where
the caller will look for it happens wherever the value was computed, and by the time the tree
passes were done the accumulator was already living in the register the ABI uses for return
values, so there was nothing left to do. Jumping back to the caller is part of the epilogue,
and the epilogue belongs to the whole function rather than to any statement in it, so GCC
files it under the closing brace.

This is worth more than it looks. It is why a breakpoint on a `return` sometimes fires
somewhere surprising, why a profiler will attribute time to a line with no code on it, and why
`-O2` and a debugger together are less pleasant than either alone. The compiler is not
throwing your line numbers away. It is honestly reporting that the code for one line ended up
in two places and the code for another line ended up nowhere.

## The ladder, to look at

The same data as a picture. One line of C, four lanes, and the empty lanes drawn rather than
skipped, because an empty lane is the interesting part.
""")

lesson.code("""
from IPython.display import SVG, display

import gxmanim

picture = gxmanim.mobjects.ir_ladder(ladder, 8)
display(SVG(gxmanim.svg.document(picture)))

# Every drawing in this project can also say what it shows in words, which is what a screen
# reader gets and what a diff of a regenerated drawing is actually readable as.
print(picture.describe())
""")

lesson.md("""
And the same ladder as something you can click, with every line in the function on it. Pick a
line and the four lanes change. It works with the keyboard, and it works with no JavaScript at
all, because the markup is built in Python and the browser only attaches behaviour to it.
""")

lesson.code("""
from IPython.display import HTML

from gxwidgets import IRLadder

# `display` came in with the SVG cell above. This cell needs the cell above it to have run,
# which is true of every cell in every lesson here and worth saying once.

widget = IRLadder(ladder, line=6)
display(HTML(widget.render()))

# The same thing as text, so this cell proves something even where HTML does not render, such
# as in a diff or on a terminal.
print(widget.selected)
""")

lesson.md(f"""
## Why four and not one

The obvious question, having seen four representations of the same nine lines, is why anybody
would want four.

Each one exists because the one before it was the wrong shape for the next job.

{term("GENERIC")} is the shape the language is in. It has to be able to hold anything a front
end can parse, which for C++ includes templates, exceptions and overload sets, so it is big:
{cite("gcc/tree.def:41@releases/gcc-16.2.0")} starts a list of 245 node codes in GCC 16.2, and
that list is shared by every language GCC compiles. You cannot write an optimizer against 245
codes with arbitrary nesting. Nobody has.

{term("GIMPLE")} is the shape optimization is possible in. It is GENERIC with almost everything
taken away: 47 statement codes, from
{cite("gcc/gimple.def:46@releases/gcc-16.2.0")}, no nested expressions, at most one operation
per statement, and control flow as explicit jumps. Every language ends up here and every
target starts from here, which is why one pass written once helps Fortran and D and Ada at the
same time. T03 is about what it cost to get this small.

{term("RTL")} is the shape a machine can be described in. It has 204 expression codes at
{cite("gcc/rtl.def:145@releases/gcc-16.2.0")} and it is deliberately close to hardware: things
have modes, there are registers, and a `set` is a store into somewhere. This is the level where
the target's own description of its instructions can be matched against what you wrote. T07 is
about that.

The assembly is text, and by then all the decisions have been made.

{
    claim(
        "GCC has more GENERIC node codes than RTL expression codes, and roughly five times as many "
        "of either as it has GIMPLE statement codes",
        unobservable="the counts come from GCC's own .def files, and this notebook has no copy of "
        "the source tree. The citations are checked against the pinned tree on every push instead.",
    )
}. That ratio is the argument. The narrow middle is the point of the whole design: it is
where the languages meet the targets, and it is small enough that a pass can be written
without knowing which language or which target it is working for.

## Where the mapping gets thin

The ladder is built from locations, so it is only as good as the locations are, and they are
not perfect.

Some items have no location at all and are dropped. Some have a location that is technically
correct and unhelpful, like the epilogue on the closing brace. A pass that combines two
statements has to pick one of their locations for the result, and it does, and the other one
is gone. At higher optimization levels, inlining gives a statement two locations, one for
where it was written and one for where it was inlined to, and only one of them fits in a
column of a table.

None of this is the ladder being sloppy. It is what location tracking in a real compiler
actually looks like, and the lesson wants you to see the edges rather than a cleaned up
version. Anything in this course that says "line 7 became this" means "GCC says line 7 became
this", which is a slightly weaker statement and the true one.

## The film

The ladder above is one line at four levels, all four printed at once. What it cannot show is
the order the lanes filled up in, which is the whole shape of the pipeline.
[One line of C, growing a lane per level](https://tamnd.github.io/gcc-internals/films/#film-five-faces)
is the same three lines from the same file, drawn a lane at a time as the compiler gets to
them. Seventy two seconds, and it loops, so leave it running while you read the rest.

## Boss fight

Three questions about the table you printed above. Work them out by reading it, not by running
anything.

1. Match each line of C to the number of assembly instructions it owns, as `5=2,6=6,7=1,8=0`
2. Which source line has GIMPLE but nothing at RTL and nothing in the assembly
3. Which source line has RTL and assembly but nothing at either tree level

Then check yourself:

```text
python lessons/t02-five-faces/grade.py
```

or `just grade t02-five-faces`. It takes the answers on the command line too, so
`--asm 5=2,6=6,7=1,8=0 --vanished 8 --appeared 9` is a complete submission. Every answer is
computed from the same recorded dumps the lesson used.

## What to read next

T03 takes the second rung on its own and asks why it is so boring, which turns out to be the
most deliberate design decision in GCC.

T04 is the list of passes that runs between the second rung and the third, all 395 of them.

T05 is SSA, which is why the GIMPLE above says `s_9` and `i_11` instead of `s` and `i`.
""")

raise SystemExit(lesson.save())
