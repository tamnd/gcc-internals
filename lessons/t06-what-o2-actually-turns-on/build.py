"""T06. What -O2 actually turns on.

T04 printed the pass list at five optimization levels and showed that the levels disagree
about which passes are on. This lesson is about where that disagreement comes from, and the
answer is smaller and more boring than people expect: four integers and a table.

Everything here comes from four corpus entries recorded by the script next door. `t06-levels`
holds the optimizer table and the param table at every level plus L1's assembly at every
level, `t06-l0` and `t06-l2` hold the same rebuild for the other two Part I programs, and
`t06-fast` holds one float loop at -O3 and at -Ofast.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t06-what-o2-actually-turns-on",
    "t06",
    title="What -O2 actually turns on",
    milestone="M1",
    summary=(
        "An optimization level is four integers and a table of a hundred and fourteen "
        "entries, why counting the switches that flipped gives the wrong answer, why -Os "
        "and -Oz look identical from outside and are not, and how few of the fifty five "
        "differences between -O1 and -O2 any one function notices"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T06. What -O2 actually turns on

{badge}

T04 left you with a listing where the same 395 passes came back different at every
optimization level, and no explanation of why. This lesson is that explanation.

There is a popular mental model where `-O2` is a named bundle of optimizations, a preset
somebody curated, and `-O3` is the same preset with more in it. The model is wrong in a way
that matters, and by the end of this you will have built `-O2` yourself out of `-O1` and a
list of flags, watched the obvious way of doing it produce worse code than either, and found
out that the function in front of you only cares about four of the fifty five differences.

You need a browser. There is no compiler here and no network.

**What you come away with**

- The four integers an {term("optimization level")} actually is, and where they are set
- How to print the whole flag table yourself, at any level, in one command
- Why reading only the switches that flipped is the mistake this lesson exists to prevent
- What a {term("param")} is and why two levels can run the same passes and still differ
- Why `-Os` and `-Oz` are indistinguishable from outside, and `-Og` is not a weak `-O1`
- Having rebuilt `-O2` out of `-O1` and then cut the list down to what one function needs
""")

lesson.setup()

lesson.md(f"""
## Four integers

Start at the bottom. When GCC has finished reading the command line it walks the options it
was given and works out what optimization level it is at, in
{cite("gcc/opts.cc:735@releases/gcc-16.2.0")}. There is no level object and no preset. There
are four integers on the options structure:

```c
  opts->x_optimize        /* 0, 1, 2 or 3 */
  opts->x_optimize_size   /* 0, 1 for -Os, 2 for -Oz */
  opts->x_optimize_fast   /* 1 for -Ofast */
  opts->x_optimize_debug  /* 1 for -Og */
```

Every spelling of `-O` is a line or two setting those. `-Os` is
{cite("gcc/opts.cc:781@releases/gcc-16.2.0")} and it sets `optimize_size` to 1 and `optimize`
to 2. `-Oz` is {cite("gcc/opts.cc:790@releases/gcc-16.2.0")}, the same thing with
`optimize_size` set to 2. `-Ofast` is {cite("gcc/opts.cc:799@releases/gcc-16.2.0")}, which is
`optimize` 3 and `optimize_fast` 1, and the comment above it says so in four words: `-Ofast`
only adds flags to `-O3`. `-Og` is {cite("gcc/opts.cc:807@releases/gcc-16.2.0")}, `optimize`
1 and `optimize_debug` 1.

Hold on to two of those. `-Os` and `-Oz` differ in one integer and agree in the other three.
`-Og` is not a level of its own at all, it is level 1 with a second flag set.

## The table you can print

The other half of the answer is a table, and unusually for a compiler internal you can print
the whole thing from the command line. `-Q --help=optimizers` lists every option GCC counts
as an optimization and, next to each one, the value it would have if you compiled with the
flags you passed.

```text
gcc-16 -Q --help=optimizers -O2
```

That is the cheapest question in this course. It compiles nothing. The recording has the
answer at all eight levels, so you can ask it eight times without a compiler.
""")

lesson.md(f"""
{claim("at -O2 the optimizer table is 295 lines, of which 244 are switches that are either on or off")}.
""")

lesson.code("""
from gxray import options

record = gxray.corpus_store.load("t06-levels")
levels = options.by_level(record.option_texts)
order = list(levels)

table = levels["-O2"]
print(f"{len(table)} lines in the optimizer table at -O2")
print(f"  {len(table.booleans):>4} switches, printed as [enabled] or [disabled]")
print(f"  {len(table.valued):>4} that take a value, printed as the value")
print(f"  {len(table.params):>4} params, which the table mentions and does not list")
print()
for name in order:
    print(f"{name:>7}  {len(levels[name].enabled):>3} switches on")
""")

lesson.md("""
Read that column of numbers before going on, because it is the shape of the whole lesson.
`-O0` through `-O3` climb. `-Os` and `-Oz` are the same number as each other and lower than
`-O2`. `-Og` is lower than `-O1`. `-Ofast` is the highest.

A column of counts is a bad way to think about this, though, and the next section is why.

## The famous number, and why it is wrong

Ask anyone what `-O2` adds to `-O1` and you get a number of flags. Here is where that number
comes from, and here is the part it leaves out.
""")

lesson.md(f"""
{claim("-O1 to -O2 is 55 differences, of which 48 are switches turning on, none are switches turning off, and 7 are options that took a new value")}.
""")

lesson.code("""
from collections import Counter

changes = options.diff(levels["-O1"], levels["-O2"])
counted = Counter(c.kind for c in changes)

print(f"{len(changes)} differences between -O1 and -O2")
for kind, n in counted.most_common():
    print(f"  {n:>3} {kind}")
print()
print("the seven that are not switches:")
for change in changes:
    if change.kind == "value":
        print(f"  {change}")
""")

lesson.md("""
Those seven are the trap. A tool that answers the question by counting `[disabled]` going to
`[enabled]` reports 48 and is not lying, it is just answering a different question. Two of
those seven turn out to matter more than most of the 48, and you will see exactly which two
before the end of this lesson.

Notice also that nothing goes off. Going up from `-O1` to `-O2` only ever adds. That is true
of `-O0` to `-O1` too, with one exception, and it is not true of any of the other levels, and
that asymmetry is the reason people think of the levels as a slider.

## Where the table comes from

Back into the source, because the table above is printed output and the thing that produced
it is worth seeing.

`default_options_table` is a plain array. Each entry says at which levels one option should
default to on, and it is sorted by level with a comment above each group.

```c
static const struct default_options default_options_table[] =
  {
    /* -O1 and -Og optimizations.  */
    { OPT_LEVELS_1_PLUS, OPT_fbit_tests, NULL, 1 },
    { OPT_LEVELS_1_PLUS, OPT_fcombine_stack_adjustments, NULL, 1 },
```

The first field is the interesting one. It is one of twelve values, and the whole vocabulary
GCC has for saying when an option should be on is those twelve words.
""")

lesson.md(f"""
The enum is at {cite("gcc/common/common-target.h:28@releases/gcc-16.2.0")}, the array is at
{cite("gcc/opts.cc:587@releases/gcc-16.2.0")}, and the code that reads them is
{cite("gcc/opts.cc:471@releases/gcc-16.2.0")}. That function is a switch on the level word,
at {cite("gcc/opts.cc:490@releases/gcc-16.2.0")}, and every case is one line of boolean:

```c
    case OPT_LEVELS_1_PLUS:
      enabled = (level >= 1);
      break;
```

So the answer to what `-O2` turns on is: run down 114 rows, evaluate one boolean per row
against four integers, and set the option if it comes out true. There is no curation and
nothing is bundled. The four words that do most of the work are these.
""")

lesson.md(f"""
{claim("the 114 rows of default_options_table use six of the twelve level words, and ten of the rows are marked speed only")}.
""")

lesson.code("""
import re
from pathlib import Path

# Read the array out of the pinned tree if it is checked out, and fall back to the counts the
# lesson was written against if it is not. The submodule is 1.3 GB and a reader on Colab will
# not have it, which is not a reason for the cell to fail.
source = Path("vendor/gcc/gcc/opts.cc")
FALLBACK = {
    "OPT_LEVELS_2_PLUS": 39,
    "OPT_LEVELS_1_PLUS": 30,
    "OPT_LEVELS_3_PLUS": 18,
    "OPT_LEVELS_1_PLUS_NOT_DEBUG": 14,
    "OPT_LEVELS_2_PLUS_SPEED_ONLY": 10,
    "OPT_LEVELS_FAST": 3,
}

found, speed = Counter(FALLBACK), []
if source.exists():
    body = source.read_text(encoding="utf-8", errors="replace")
    start = body.index("default_options_table[] =")
    table_text = body[start : body.index("\\n  };", start)]
    rows = re.findall(r"\\{\\s*(OPT_LEVELS_\\w+)", table_text)
    # The last row is OPT_LEVELS_NONE, which is the terminator rather than an option. It is
    # dropped here on purpose, because counting it is how you get 115 and then spend an
    # afternoon looking for an option that does not exist.
    found = Counter(word for word in rows if word != "OPT_LEVELS_NONE")
    speed = re.findall(r"OPT_LEVELS_2_PLUS_SPEED_ONLY\\s*,\\s*(\\w+)", table_text)

print(f"{sum(found.values())} rows, using {len(found)} of the twelve level words")
for word, n in found.most_common():
    print(f"  {n:>3}  {word}")
if speed:
    print()
    print("the speed only rows:")
    for name in speed:
        print(f"  {name.removeprefix('OPT_')}")
""")

lesson.md("""
`OPT_LEVELS_2_PLUS_SPEED_ONLY` is the one to look at. It means on at `-O2` and above, but not
when optimizing for size, and there are ten rows of it. Hold that number.

## -Os is not -O2 with the volume down

Now the same diff, pointed at the size levels.
""")

lesson.md(f"""
{claim("-O2 to -Os is 12 differences, of which 7 are switches going off and none are switches coming on, and -Os and -Oz print byte-identical tables")}.
""")

lesson.code("""
for level in ("-Os", "-Og", "-Ofast"):
    changes = options.diff(levels["-O2"], levels[level])
    counted = Counter(c.kind for c in changes)
    print(f"-O2 to {level:<7} {len(changes):>3} differences  {dict(counted)}")

print()
print("what -Os switches off that -O2 has on:")
for change in options.diff(levels["-O2"], levels["-Os"]):
    if change.kind == "off":
        print(f"  {change.name}")

same = record.option_texts["optimizers -Os"] == record.option_texts["optimizers -Oz"]
params_same = record.option_texts["params -Os"] == record.option_texts["params -Oz"]
print()
print(f"-Os and -Oz print the same optimizer table: {same}")
print(f"-Os and -Oz print the same param table:     {params_same}")
""")

lesson.md(f"""
Line those twelve up against the ten speed only rows from the array and nine of the ten show
up. Three of them are alignment options that are two lines in the table, the switch and the
value, and both move, which is how nine rows come out as twelve differences. The tenth row is
`-fschedule-insns`, which is already off at `-O2` on this target, so turning it off again is
not a difference.

Nothing comes on. `-Os` really is `-O2` with things removed, which makes it the one pair in
the whole set where the slider model is nearly right. It is worth knowing that the pass list
disagrees: T04 found one pass, `rtl-hoist`, that is on at `-Os` and off at `-O2`. The flag
that gates it is on at both. A pass gate can look at `optimize_size` directly, and that one
does, which is a second mechanism this table cannot see.

Then there is the other line in that output.

{
    claim(
        "-Os and -Oz differ inside the compiler, where optimize_size is 1 for one and 2 for "
        "the other, and every level word in the table asks whether optimize_size is nonzero "
        "rather than what it is, which is why no printed table can tell the two apart",
        unobservable="optimize_size is a field on the options structure and the only way to "
        "read it is from inside a running compiler. The two lines of source that set it are "
        "cited above and checked against the pinned tree on every push.",
    )
}. Whether `-Oz` does anything at all is then up to individual passes and targets asking
about it themselves, the same way `rtl-hoist` asks. On this recording it does not change L1.

## The other half of a level

Switches are only one of the two things a level sets. The other is a pile of numbers.
""")

lesson.code("""
params = options.by_level(record.option_texts, kind="params")
print(f"{len(params['-O2'])} params at -O2")
print()
for a, b in (("-O1", "-O2"), ("-O2", "-O3"), ("-O2", "-Os")):
    moved = options.diff(params[a], params[b])
    print(f"{a} to {b}: {len(moved)} params move")
    for change in moved:
        print(f"    {change}")
""")

lesson.md(f"""
Five numbers are the entire difference between `-O2` and `-O3` in this table, and four of the
five are inlining limits. `-O3` is mostly `-O2` willing to inline much larger functions. The
first param in the file is at {cite("gcc/params.opt:24@releases/gcc-16.2.0")} and they are all
declared the same way, with a default and a range.

This is why two levels can run exactly the same passes, with exactly the same switches, and
still produce different code. Nothing flipped. A threshold moved.

## -Og is not a weak -O1

`-Og` gets described as optimization that does not hurt debugging, which makes it sound like
a point on the line somewhere below `-O1`. It is not on the line.
""")

lesson.md(f"""
{claim("13 switches on at -O1 are off at -Og, and one switch is on at -Og and off at -O1, so -Og is neither above nor below it")}.
""")

lesson.code("""
both_ways = options.diff(levels["-O1"], levels["-Og"])
off = [c.name for c in both_ways if c.kind == "off"]
on = [c.name for c in both_ways if c.kind == "on"]

print(f"-O1 to -Og: {len(off)} switches off, {len(on)} on")
print()
for name in off:
    print(f"  off  {name}")
for name in on:
    print(f"  on   {name}")
""")

lesson.md(f"""
The thirteen are `OPT_LEVELS_1_PLUS_NOT_DEBUG` rows. There are fourteen of those in the array
and only thirteen turn up here, because `-fdelayed-branch` is off on this target at every
level and turning something off that was already off is not a difference.

The one going the other way is not in the array at all. It is two lines of ordinary C at
{cite("gcc/opts.cc:1234@releases/gcc-16.2.0")}, with a comment that explains itself:

```c
  /* At -O0 or -Og, turn __builtin_unreachable into a trap.  */
  if (!opts->x_optimize || opts->x_optimize_debug)
    SET_OPTION_IF_UNSET (opts, opts_set, flag_unreachable_traps, true);
```

That is the third mechanism in this lesson. The table sets most things, a pass gate can read
the integers directly, and then there is a stretch of hand written code that adjusts whatever
the first two left in an awkward state. Reading the array alone will never tell you about the
third one, and it is where `-funreachable-traps` lives.

`-Og` is a different opinion, not a smaller dose. It is `optimize` 1 with a second integer set
that fourteen rows of the table and several lines of that hand written code check.

## What -Ofast gives up

`-Ofast` is `-O3` plus `optimize_fast`, and the interesting part is not what it adds.
""")

lesson.md(f"""
{claim("-O3 to -Ofast is 11 differences, 5 switches on, 4 off and 2 values, and three of the four it turns off were the ones keeping the floating point arithmetic honest")}.
""")

lesson.code("""
for change in options.diff(levels["-O3"], levels["-Ofast"]):
    print(f"  {change}")
""")

lesson.md("""
`-fmath-errno` off means a math function no longer has to set `errno`, so the compiler may
replace a call with an instruction. `-fsigned-zeros` off means negative zero and positive zero
are now the same number. `-ftrapping-math` off means arithmetic is assumed not to raise. And
`-fassociative-math` on means the compiler may reassociate, which is the big one, because
floating point addition is not associative and reassociating it changes the answer.

The fourth switch going off is `-fsemantic-interposition`, which is not about arithmetic at
all. It is about whether a function in a shared library may be replaced at load time, and
turning it off says no, so the compiler can inline across the boundary.

`-fallow-store-data-races` is on the list too and is also not about arithmetic. It permits the
compiler to introduce a store that the program did not write, which is harmless in a single
threaded program and is a data race in a threaded one.

Here is what that buys and what it costs, on a loop that adds up an array of floats.
""")

lesson.code("""
fast = gxray.corpus_store.load("t06-fast")
print(fast.source)

for flags in ("-O3", "-Ofast"):
    body = fast.asm_texts[flags]
    vector = [line.strip() for line in body.splitlines() if line.strip().startswith("fadd")]
    print(f"{flags:>7}  {len(body.splitlines()):>3} lines   {' | '.join(vector[:3])}")
""")

lesson.md("""
At `-O3` the additions are `fadd s0, s0, s31`, one at a time, in source order, because that
order is part of the answer. At `-Ofast` they are `fadd v3.4s, v3.4s, v30.4s`, four lanes at a
time, followed by a pairwise add to fold the lanes together. The loop got faster and the
result changed. Whether that is a bug depends entirely on what the program is for, which is
why it is not on by default.

`-Ofast` does nothing at all to L1, incidentally. L1 is integer code, and the recording has
its `-O3` and `-Ofast` assembly byte for byte identical. You need floating point in the
program before any of this is visible.

## The picture

Every switch that is not the same at every level, one row per level, filled where the switch
is on. The columns are ordered by the first row that fills them, which is what makes `-O0`
through `-O3` a staircase.

Click a column and the panel says what that one switch is at all eight levels. The buttons
filter to the switches a level is the first to turn on, so the `-O2` button leaves exactly the
48 from the diff above.
""")

lesson.code("""
from IPython.display import HTML, display

from gxwidgets import FlagDiff

widget = FlagDiff(levels)
display(HTML(widget.render()))

# The same numbers as text, so this cell proves something where HTML does not render.
for name in order:
    print(f"{name:>7}  {len(widget.on_at(name)):>3} of the {len(widget.switches)} that vary")
""")

lesson.md("""
Look at the four rows at the top and then at the three at the bottom. `-O0`, `-O1`, `-O2`,
`-O3` fill from the left and never lose a column. `-Os`, `-Og` and `-Ofast` have holes in the
middle of stretches the row above filled solid, and those holes are the whole argument.

Here is the same thing as a still picture, which is what goes in the book.
""")

lesson.code("""
from IPython.display import SVG

import gxmanim

switches = {name: {o.name: bool(o.on) for o in table.booleans} for name, table in levels.items()}
picture = gxmanim.mobjects.flag_ladder(switches, title="Optimizer switches, one row per level")
display(SVG(gxmanim.svg.document(picture)))

print(picture.describe())
""")

lesson.md(f"""
## Rebuilding -O2 by hand

Now the part that makes all of this concrete. Every difference the diff found can be written
as a flag, so `-O1` plus the right list of flags ought to be `-O2` exactly. Let us try it the
obvious way first, with the 48 switches and nothing else.

{claim("-O1 plus all 48 switches produces 86 lines of assembly for L1, which is worse than -O1 at 54 and worse than -O2 at 56, and adding the 7 value changes makes it byte-identical to -O2")}.
""")

lesson.code("""
changes = options.diff(levels["-O1"], levels["-O2"])
switch_flags = [c.as_flag() for c in changes if c.kind == "on"]
value_flags = [c.as_flag() for c in changes if c.kind == "value" and c.as_flag()]

attempts = {
    "-O1 alone": "-O1",
    "-O1 plus the 48 switches": " ".join(["-O1", *switch_flags]),
    "-O1 plus the switches and the values": " ".join(["-O1", *switch_flags, *value_flags]),
    "-O2": "-O2",
}
target = record.asm_texts["-O2"]
for label, flags in attempts.items():
    body = record.asm_texts[flags]
    verdict = "identical to -O2" if body == target else "different"
    print(f"{len(body.splitlines()):>4} lines  {verdict:<17} {label}")
""")

lesson.md("""
Sit with the middle row for a second. Turning on every switch that `-O2` turns on, and nothing
else, produced code half again as long as either level. That is not a rounding error and it is
not a bug in GCC. Three of the seven value changes are the alignment options, and asking for
`-falign-functions` without saying what to align it to gets you the target's maximum rather
than the 32:16 that `-O2` asks for. The switch and the value are two different lines of the
table with two different jobs, and taking one without the other is a request nobody would ever
type on purpose.

This is the entire reason `gxray.options` keeps the value lines instead of reducing everything
to on and off. A lesson built on the flip count would have printed 48, called it the answer,
and been wrong by two lines of assembly in one direction and thirty in the other.

## How few of them matter

Fifty five differences, and the last cell showed you need all of them to get `-O2` exactly.
That is true of L1. It is not true of L1's `f`, which is one small function, and it gets less
true the smaller the function is.

The recorder walks the 55 in the order GCC prints them, drops one, recompiles, and keeps the
drop if the assembly still matches `-O2`. What comes out is a set nothing more can be removed
from. It is not the smallest such set, because a different order would find a different one,
which is why the lesson says irreducible rather than minimal.
""")

lesson.md(f"""
{claim("L0 needs 1 of the 55 flags to match its -O2 output, L1 needs 4, and L2 needs 8")}.
""")

lesson.code("""
def rebuild(entry):
    \"\"\"The recorded rebuild for one program: the flags it needed, and whether they worked.\"\"\"
    stored = gxray.corpus_store.load(entry)
    key = next(k for k in stored.asm_texts if k not in ("-O1", "-O2"))
    flags = key.split()[1:]
    return flags, stored.asm_texts[key] == stored.asm_texts["-O2"]


# L1 lives in the same entry as everything else, which also holds the two long attempts from
# the cell above, so pick the shortest recorded command line that matched.
worked = [k for k in record.asm_texts if k.startswith("-O1 ") and record.asm_texts[k] == target]
l1_key = min(worked, key=len)

runs = {
    "L0": rebuild("t06-l0"),
    "L1": (l1_key.split()[1:], True),
    "L2": rebuild("t06-l2"),
}
for name, (flags, matched) in runs.items():
    print(f"{name}  {len(flags)} of 55, matches -O2: {matched}")
    for flag in flags:
        print(f"      {flag}")
""")

lesson.md(f"""
One flag for L0. Four for L1, and three of the four are the alignment values, which do not
change a single instruction, they change where the instructions sit. The one that changes the
code is `-freorder-blocks-algorithm=stc`, and it is a value, not a switch.

That is the honest answer to what `-O2` did to your function. Almost nothing on the list came
near it. The list has to be that long because it has to be right for every function anyone
compiles, and any given function walks past nearly all of it untouched. This is the same shape
T04 found in the pass tape, arriving from a completely different direction.

## The answer is not portable

One last thing before the boss fight, and it is the reason none of the numbers in this lesson
should be quoted without saying which machine they came from.

The 114 row array is the shared one. Every target gets to add its own on top, and aarch64's is
at {cite("gcc/common/config/aarch64/aarch64-common.cc:48@releases/gcc-16.2.0")}. One of its
rows is {cite("gcc/common/config/aarch64/aarch64-common.cc:62@releases/gcc-16.2.0")}:

```c
    {{ OPT_LEVELS_2_PLUS, OPT_mearly_ra_, NULL, AARCH64_EARLY_RA_ALL }},
```

`-mearly-ra` is an aarch64 option. It is in the diff above, as one of the seven values, and it
would not be in the diff at all on an x86 machine. Re-record this corpus on a different target
and some of these numbers move.
""")

lesson.code("""
target_options = [o for o in levels["-O2"].options.values() if o.target]
print(f"{record.compiler} configured for {record.target}")
print(f"{len(target_options)} of the {len(levels['-O2'])} lines are target options")
print()
for option in target_options[:8]:
    print(f"  {option}")
""")

lesson.md("""
## The picture of the table

The array, the four integers and the twelve words are drawn in
[`diagrams/four-integers.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t06-what-o2-actually-turns-on/diagrams/four-integers.excalidraw).
Open it at excalidraw.com and you can move things around. It shows one option going through
one row of the table and coming out on or off, which is the whole mechanism.

## Boss fight

Build `-O2` out of `-O1` for L1, using as few flags as you can, and get assembly that is
byte-identical to what `-O2` produces.

You have everything you need. The diff cell gives you the 55 candidates, the rebuild cell
shows the two ways of writing them out, and the recording holds the assembly for both. Three
questions:

1. How many flags are in the irreducible set for L1
2. Which one of them is not an alignment option
3. How many lines of assembly `-O1` plus all 48 switches produces, with no value changes

The second question is the one worth thinking about. Three of the four flags in the answer
move code around in memory without changing an instruction. One of them changes the
instructions. Work out which before you look.

Check yourself:

```text
python lessons/t06-what-o2-actually-turns-on/grade.py
```

or `just grade t06-what-o2-actually-turns-on`. It takes the answers on the command line too,
so `--flags 4 --odd-one-out -freorder-blocks-algorithm=stc --switches-only 86` is a complete
submission. Every answer is computed from the same recording the lesson used.

## What to read next

T07 goes down a level, to RTL, which is where the passes T04 counted as `rtl` live and where
the alignment flags in the boss fight actually take effect.

M2 comes back to this table properly. There is a lesson per group of flags, and the question
it keeps asking is the one this lesson only asked once: not what does this flag do, but which
of your functions would notice if you turned it off.
""")

raise SystemExit(lesson.save())
