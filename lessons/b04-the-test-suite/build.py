"""B04. Forty thousand tests, and how to run one of them.

The test suite is the second thing in this course a reader cannot run. `runtest` needs
`expect`, a build tree and a compiler that was built ten minutes ago, and Colab has none of
those. B03 solved that problem by recording a session. This lesson solves it differently,
because the interesting part of the test suite is not what it looks like on a terminal, it is
the rule it applies, and a rule can be modelled.

So `gxray/dejagnu.py` is a model of the deciding part: read the directives out of a C file,
work out the command line, match the compiler's output against what the file said would
appear, and produce the lines that would land in a `.sum`. It is driven by twelve real
compilations of real files out of the pinned tree, recorded through Compiler Explorer by
`record.py` next door, so every verdict in this notebook is a verdict about output a real GCC
16.2 really printed.

The model is honest about being a model and the lesson says so twice: near the top and again
in a section of its own at the end, which lists what it does not implement. `BP-TESTSUITE` is
where the parts that did not fit are written down.

The one idea the lesson is built around is that a GCC test is subtractive. A file with three
`dg-error` directives is not saying that those three messages appear, it is saying that those
three appear and nothing else does. Almost everything that surprises people about this suite
follows from that, and the demonstration is the fifth section: the same file, compiled under
the directory default instead of its own options, keeps all three of its directives passing
and fails anyway, on a struct the author deliberately left legal.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "b04-the-test-suite",
    "b04",
    title="Forty thousand tests, and how to run one of them",
    milestone="M2",
    summary=(
        "The GCC test suite taken apart: what a directive is, why the command line is not "
        "what the file says, the subtractive rule that makes a test fail for output nobody "
        "asked about, the six compilations every torture test costs, how to run one file "
        "without running the other thirty five thousand, and the one question worth asking "
        "of a .sum"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# B04. Forty thousand tests, and how to run one of them

{badge}

B03 stopped the compiler in the middle of a pass and read its memory. This lesson is about
the other way you find out whether the compiler is right, which is to compile thirty five
thousand small programs and check that each one said what it was supposed to say.

Two warnings before anything else, because both change how you should read what follows.

**You cannot run the real thing here, and neither can you on a laptop without a build tree.**
{term("DejaGnu")} needs `expect`, a configured build directory and a compiler built minutes
ago. There is no version of this that works in a notebook.

**So the harness in this lesson is a model.** `gxray.dejagnu` is about six hundred lines of
Python that do the deciding part: read the {term("directive", "directives")} out of a test
file, work out the command line, match the compiler's output against them, and produce the
lines that would go in a `.sum`. It is not the harness. It handles eleven kinds of directive
out of seventy three and there is a section near the end that lists what it leaves out.

What is not a model is the compiler output. Twelve real files out of the pinned tree were
compiled by a real GCC 16.2 and every byte kept, so every verdict below is a verdict about
something a compiler really printed.

**What you come away with**

- How big this thing actually is, counted rather than guessed
- What a directive is, and the four you will meet in almost every file
- Why the command line is not what the file says, and the one directive that adds rather
  than replaces
- Four results out of one compilation, and why the fourth one is the interesting one
- The subtractive rule, demonstrated by breaking a real test in the way rebases break tests
- Why one `dg-note` anywhere in a file changes the meaning of every note in it
- A check that reads a dump instead of a diagnostic, and why a missing dump is not a failure
- Why a directory of four hundred small files costs two thousand four hundred compilations
- How to run one test, which is the thing everybody actually wants
- The race between parallel `runtest` processes, and the two ways it goes wrong silently
- The only question worth asking of a `.sum`, and the answer a summary block cannot give you
""")

lesson.setup()

lesson.md(f"""
## How big it is

Start with the size, because every design decision in this suite is a consequence of it and
because the number people carry around is usually wrong in one direction or the other.

{
    claim(
        "a native x86-64 run of the C test suite walks over thirty five thousand C files, "
        "which is a quarter of the files in the testsuite directory, because the rest belong "
        "to other languages and other architectures"
    )
}.
""")

lesson.code("""
from gxray import dejagnu

corpus = dejagnu.load()
count = corpus.survey

print(corpus.banner)
print()
print(f"{count['files']:>7}  files under gcc/testsuite")
print(f"{count['exp']:>7}  .exp files, one per directory, each a Tcl program")
print(f"{count['total']:>7}  C files a native x86-64 run of the C suite walks over")
print()
for name, many in count["walked"].items():
    print(f"{many:>7}    {name}")
""")

lesson.md(f"""
The `.exp` files are the part that catches people out. A directory of tests is not a list, it
is a Tcl program that decides what to do with the files next to it, and there are five hundred
and fifty of those programs. `gcc.target` alone holds one for every architecture GCC supports
and exactly one of them runs on your machine.

Inside the files, the language is comments.

{
    claim(
        "seventy three kinds of directive are written across the suite, four of them account "
        "for most of the usage, and the model in this lesson handles eleven"
    )
}.
""")

lesson.code("""
census = count["directives"]
print(f"{count['written']:,} directives in {count['scanned']:,} C files, {count['kinds']} kinds")
print()
for name, many in list(census.items())[:10]:
    mark = "modelled" if name in count["handled"] else ""
    print(f"{many:>7}  {name:<30} {mark}")
print()
print(f"{len(count['handled'])} of the {count['kinds']} kinds are modelled in this lesson")
""")

lesson.md(f"""
`dg-final` is top of that list by a distance, and almost all of it is in `gcc.target`, where
the check is nearly always "did the assembler output contain this instruction". That kind of
test is the subject of T09 rather than this lesson, but the count is worth seeing: more than a
third of all the directives in GCC's test suite are looking at generated text rather than at a
diagnostic.

## A test is a C file with comments in it

Here is a real one, whole. Nine lines, and five of them are the test.
""")

lesson.code("""
flex = corpus["flex"]
print(flex.path)
print()
print(flex.text)
""")

lesson.md("""
Four things are being said here.

`{ dg-do compile }` says compile it and stop, do not assemble, link or run it. Most
directories default to `compile` anyway, so this line is usually there for the reader.

`{ dg-options "..." }` says what to compile it with. Hold that thought for the next section,
because it does not mean what it looks like it means.

The three `dg-error` lines each say that an error will appear **on the line the comment is
written on**. That is why they are scattered through the file rather than collected at the
top: the line number is not written anywhere, it is where you put the comment. The second
string is a comment for humans and appears in nothing.

And the fourth struct, `s4`, has no directive at all. That is not an omission. It is the most
important line in the file, and section five is about why.

The model reads them like this.
""")

lesson.code("""
for one in flex.test.directives:
    print(one)

print()
print("dg-do says:      ", flex.test.do_what)
print("dg-options says: ", flex.test.given)
print("expectations:    ")
for want in flex.test.expectations:
    print(f"    line {want.line}: {want.kind} matching {want.pattern!r}")
""")

lesson.md(f"""
## The command line is not what the file says

Three separate things decide what the compiler is handed, and only one of them is in the file
you are reading. This is the single most common way a person misreads a GCC test.

The directory's `.exp` has a default, and here is `gcc.dg`'s.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("b04")
print(f"{len(cuts)} excerpts, {cuts.lines()} lines, cut from {cuts.tag}")
print()
shown = cuts["default"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
print(shown.numbered({25: "every test in this directory, unless it says otherwise"}))
""")

lesson.md(f"""
So a file in `gcc.dg` with no `dg-options` is compiled as C90 with pedantic errors, which is
not a thing anybody writes on purpose and is a thing a great many tests depend on.

Then there is one flag that goes on every compilation in the entire suite whatever anybody
says, at {cite("gcc/testsuite/lib/prune.exp:30@releases/gcc-16.2.0")}.
""")

lesson.code("""
always = cuts["always"]
print(always.about)
print(f"{always.span}  ({always.citation})")
print()
print(always.numbered({30: "prepended, so a test cannot turn it off by setting the variable"}))
""")

lesson.md(f"""
`-fdiagnostics-plain-output` turns off colour, turns off the caret diagram, turns off the
fix-it hints and pins the format of everything else. The suite matches on the text of
diagnostics, so the text has to be stable, and a change to GCC's default output format must
not be allowed to change what forty thousand tests see.

Now the part that surprises people.

{
    claim(
        "dg-options replaces the directory default rather than adding to it, so the flexible "
        "array test is compiled without the -ansi its directory would have given it, and "
        "dg-additional-options is the directive for wanting the other behaviour"
    )
}.
""")

lesson.code("""
print("the directory would have used:  ", " ".join(dejagnu.DEFAULT_CFLAGS))
print("the file asks for:              ", " ".join(flex.test.given))
print("dg-additional-options adds:     ", flex.test.extra or "nothing")
print()
print("so the compiler is handed:")
print("   ", " ".join(flex.test.command()))
print()
print("and that is what it was handed when this was recorded:")
print("   ", " ".join(flex.args))
""")

lesson.md(f"""
`-ansi` is gone. The test asked for C99 and got C99 and nothing else from the directory, and
if it had wanted C99 **and** the directory's pedantic errors it would have had to say
`-pedantic-errors` itself, which is exactly what it does.

Every test that has ever mysteriously started failing after somebody added a flag to a
`dg-options` line has failed for this reason.

## One compilation, four results

Now compile it. This output is recorded, not generated, and it is what GCC 16.2 printed.
""")

lesson.code("""
print(flex.stderr)
""")

lesson.md(f"""
Three diagnostics, three directives, and the lines agree. Feeding both to the model gives the
lines that would land in the `.sum`.

{
    claim(
        "one compilation of a nine line file produces four results, one per dg-error and one "
        "more that no directive in the file asked for"
    )
}.
""")

lesson.code("""
for result in dejagnu.check(flex.test, flex.stderr):
    print(result)
""")

lesson.md(f"""
Four lines, and the fourth is the one to look at. Nothing in the file asked for it. The
harness adds it to every test, and it is the whole reason this suite catches anything.

{term("excess errors", "`(test for excess errors)`")} means: after every expectation has taken
at most one diagnostic, was there anything left over.

## The rule is subtractive

A file with three `dg-error` directives is not saying "these three messages appear". It is
saying "these three appear and nothing else does".

Here is what that buys, demonstrated by breaking the test in the way tests actually get
broken. This is the same file, compiled with the directory default instead of its own
`dg-options`, which is what happens when a rebase eats one line.

{
    claim(
        "under the wrong standard every one of the file's three directives still passes and "
        "the test fails anyway, on the one struct its author deliberately left legal"
    )
}.
""")

lesson.code("""
c90 = corpus["flex-c90"]
print("compiled with:", " ".join(c90.args))
print()
for result in dejagnu.check(c90.test, c90.stderr):
    print(result)
print()
print("what nobody accounted for:")
for line in dejagnu.excess(c90.test, c90.stderr):
    print("   ", line)
""")

lesson.md(f"""
Read the last one. Line 8 is `struct s4 {{ int x; int y[]; }};`, the struct with a named
member before the flexible array, which is legal C99 and is in the file precisely to check
that GCC stays quiet about it. Under C90 it is not legal, GCC says so, and the test fails.

An additive suite would have passed this. All three of the things the file said would happen
happened. The failure is in what else happened, and no directive in the file could have
predicted it, which is the point: the author of a test does not have to enumerate everything
the compiler must not say.

The cost is that pruning becomes load bearing, and the next section is about the one place
where it is subtle.

## Notes are the exception

A diagnostic that no expectation matched is not always an excess error, because a great many
notes are attached to errors that the test does account for, and demanding that a test
enumerate the note under each of its errors would double the size of the suite.

So notes are thrown away. Here is where, at
{cite("gcc/testsuite/lib/prune.exp:61@releases/gcc-16.2.0")}.
""")

lesson.code("""
pruning = cuts["pruning"]
print(pruning.about)
print(f"{pruning.span}  ({pruning.citation})")
print()
print(pruning.numbered({62: "unless something in this file turned the switch off"}))
""")

lesson.md(f"""
And here is the switch, which is the part worth remembering, at
{cite("gcc/testsuite/lib/gcc-dg.exp:1359@releases/gcc-16.2.0")}.
""")

lesson.code("""
notes = cuts["notes"]
print(notes.about)
print(f"{notes.span}  ({notes.citation})")
print()
print(notes.numbered({1363: "one directive, and the whole file changes meaning"}))
""")

lesson.md(f"""
Writing `dg-note` once, anywhere in a file, means every note in that file has to be accounted
for by something. That is a per file switch reached by using a per line directive, and it is
why the comment in the source recommends `dg-message "note: [...]"` when you want to check one
note without signing up for all of them.

Here is a test that depends on it. Two errors, one warning, three directives, and two notes
that nothing mentions.

{
    claim(
        "the assume_aligned test prints five diagnostics, accounts for three of them, and "
        "passes, because the two it ignores are notes and nothing in the file used dg-note"
    )
}.
""")

lesson.code("""
assume = corpus["assume"]
print(assume.path, " ".join(assume.args))
print()
print(assume.stderr)
found, _ = dejagnu.diagnostics(assume.stderr)
print("kinds printed:      ", [one.kind for one in found])
print("directives written: ", len(assume.test.expectations))
print("notes pruned:       ", assume.test.prune_notes)
print()
for result in dejagnu.check(assume.test, assume.stderr):
    print(result)
""")

lesson.md(f"""
Note also what this file does not have: a `dg-options` line. So it is compiled with `-ansi
-pedantic-errors`, as the previous section promised, and that is why it is in this lesson
twice.

## When finding the message is the failure

`dg-bogus` is the inverse directive. It names a message that must not appear on that line, and
it passes by not matching.

{
    claim(
        "dg-bogus passes when the compiler says nothing, and the test it comes from is a "
        "regression test for a note GCC used to print and should not have"
    )
}.
""")

lesson.code("""
bogus = corpus["bogus"]
print(bogus.text)
print("the compiler printed:", repr(bogus.stderr))
print()
for result in dejagnu.check(bogus.test, bogus.stderr):
    print(result)
""")

lesson.md(f"""
`-fopt-info-vec-optimized` asks the vectoriser to report what it did, on a function with
nothing in it. The bug this file records is GCC reporting a vectorisation anyway. It passes
now, and if it ever stops passing the failure will be on the `dg-bogus` line rather than on
excess errors, which is a better error message than "unexpected output".

Notice that `dg-bogus "note"` matches on the word `note`, not on the text of a message. The
model searches the pattern against the diagnostic with its kind still on the front, which is
what makes both that and `dg-message "note: [...]"` work.

## When the check is not a diagnostic

Everything so far has matched against what the compiler said. `dg-final` matches against what
the compiler wrote, which for a middle end test means a {term("dump file")}.

Here is `scan-tree-dump-times`, which is the one you will meet most, at
{cite("gcc/testsuite/lib/scandump.exp:148@releases/gcc-16.2.0")}.
""")

lesson.code("""
scandump = cuts["scandump"]
print(scandump.about)
print(f"{scandump.span}  ({scandump.citation})")
print()
notes = {
    148: "the test name is built here, which is why it is so long in a .sum",
    155: "no dump is UNRESOLVED, not FAIL",
}
print(scandump.numbered(notes))
""")

lesson.md(f"""
That distinction at the bottom matters more than it looks. A missing dump is not a failing
test, it is a test that could not be decided, and `UNRESOLVED` is a separate state that most
people's eyes slide over. A `dg-final` whose `dg-options` lost its `-fdump-tree-...` flag goes
`UNRESOLVED` rather than red.

Here is a real one. A five line function, one dump, and a count.

{
    claim(
        "the fre1 dump of a five line function contains the word Replaced exactly six times, "
        "which is what the test asks for, and the directive names the dump fre1 even though "
        "the flag that produced it was spelled -fdump-tree-fre1-details"
    )
}.
""")

lesson.code("""
fre = corpus["fre"]
print(fre.text)
print("compiled with:  ", " ".join(fre.args))
print("dumps produced: ", list(fre.dumps))
print("the flag        ", "-fdump-tree-fre1-details")
print("writes the dump ", dejagnu.dump_suffix("-fdump-tree-fre1-details"))
print()
for line in fre.dump.splitlines():
    if "Replaced" in line:
        print("   ", line.strip())
print()
for result in dejagnu.scan(fre.test, fre.dumps):
    print(result)
""")

lesson.md("""
Six replacements, from `i = 2; int j = i * 2; int k = i + 2;`. Full redundancy elimination
propagates the constant into both uses, folds both expressions, and then the comparison
becomes a constant too. The test does not care which six, it cares that there are six, and
that is deliberate: a dump scan that checks for one occurrence of a string cannot tell the
difference between the pass working and the pass working once.

And what happens when the dump is not there.
""")

lesson.code("""
for result in dejagnu.scan(fre.test, {}):
    print(result)
""")

lesson.md(f"""
## Six compilations per file

The `torture` directories do something different: they compile the same file once per set of
{term("torture options", "torture options")}. The sets are here, at
{cite("gcc/testsuite/lib/gcc-dg.exp:94@releases/gcc-16.2.0")}.
""")

lesson.code("""
torture = cuts["torture"]
print(torture.about)
print(f"{torture.span}  ({torture.citation})")
print()
print(torture.numbered({98: "spelled out because some ports turn it off at -O3"}))
""")

lesson.md(f"""
Six sets. So `gcc.dg/torture`, which holds about four hundred small files, is two thousand
four hundred compilations, and that arithmetic is most of the answer to why `make check` takes
as long as it does.

Whether a file gets the two loop flags is decided by looking at the text of the file, at
{cite("gcc/testsuite/lib/gcc-dg.exp:738@releases/gcc-16.2.0")}.
""")

lesson.code("""
loops = cuts["loops"]
print(loops.about)
print(f"{loops.span}  ({loops.citation})")
print()
print(loops.numbered({738: "a glob, so format( counts as a loop"}))
""")

lesson.md(f"""
{
    claim(
        "the same file is compiled six times under torture, and a file with no loop in it is "
        "compiled with the same six sets minus the two loop flags, chosen by searching the "
        "text of the file for for or while"
    )
}.
""")

lesson.code("""
one = corpus["torture-0"]
print(one.path)
print(one.text)
print("has a loop:", dejagnu.has_loop(one.text))
print()
for n in range(6):
    each = corpus[f"torture-{n}"]
    verdict = dejagnu.check(each.test, each.stderr)[-1]
    print(f"{verdict.state}  {' '.join(each.args[1:])}")

print()
loopless = corpus["noloop"]
print(f"{loopless.path}, has a loop: {dejagnu.has_loop(loopless.text)}")
for options in dejagnu.torture_list(loopless.text):
    print("   ", options)
""")

lesson.md(f"""
The two flags that went missing are `-funroll-loops` and `-fpeel-loops`, and they went missing
because there is no `for` or `while` in the file. Nobody has ever tightened that search,
because the cost of a false positive is one extra flag on one compilation and the cost of a
false negative is nothing much either.

Six results per file also means six lines per file in the `.sum`, each with the option set in
its name, which is why torture failures are reported as
`FAIL: gcc.dg/torture/x.c -O2 (test for excess errors)` and why the option set is part of the
bug report.

## Running one test out of forty thousand

This is the thing everybody actually wants, and it is one environment variable.

    make check-gcc RUNTESTFLAGS="dg.exp=c99-flex-array-1.c"

The part before the `=` is the `.exp` file, which is to say the directory. The part after is a
glob, and the glob is matched against the file name only.

{
    claim(
        "a RUNTESTFLAGS filter matches the base name of a test and not its path, so a glob "
        "of pr*.c selects files in every directory the named .exp walks"
    )
}.
""")

lesson.code("""
pool = [
    "gcc.dg/c99-flex-array-1.c",
    "gcc.dg/pr87309.c",
    "gcc.dg/pr12345.c",
    "gcc.dg/tree-ssa/ssa-fre-6.c",
    "gcc.dg/torture/pr78517.c",
]
for pattern in ["c99-flex-array-1.c", "pr*.c", "ssa-*", ""]:
    kept = dejagnu.selected(pool, pattern)
    print(f"{pattern or '(no filter)':<22} {len(kept)}  {kept}")
""")

lesson.md("""
Two practical notes that are worth more than the syntax.

The first is that the `.exp` still runs in full. It loads the library, works out the target's
capabilities, and walks the directory, and only then does the filter drop the files you did
not ask for. Running one test out of `gcc.dg` takes a few seconds rather than none.

The second is that `.exp=` names accumulate, so
`RUNTESTFLAGS="dg.exp=pr87309.c tree-ssa.exp=ssa-fre-6.c"` runs two, and a bare
`RUNTESTFLAGS="dg.exp"` runs one directory and nothing else. That last one is the command to
know: it is the difference between five seconds and forty minutes when you are iterating on a
diagnostic.

## The race nobody watches

`make check -j16` does not split the tests between sixteen processes. It starts sixteen
`runtest` processes that all walk the whole list, and they race for the right to run each
batch of ten.
""")

lesson.code("""
race = cuts["race"]
print(race.about)
print(f"{race.span}  ({race.citation})")
print()
print(race.numbered({183: "an assumption, stated, and checked by nothing"}))
""")

lesson.md(f"""
Read line 183 again. Every process must enumerate the tests in the same order. Nothing
verifies that. The marker file for batch 3 is created by whichever process reaches it first,
and every other process takes that as "batch 3 is handled" and moves on, without ever
comparing which ten files it thought batch 3 was.

When the orders agree this works and the allocation is arbitrary, which is fine, because the
tests are independent.

{
    claim(
        "when every process walks the same list every test runs exactly once, and when one "
        "process walks a list that is one file shorter, one test is never run and another "
        "runs twice, and nothing reports either"
    )
}.
""")

lesson.code("""
names = [f"t{n:02d}.c" for n in range(1, 31)]

agreed = dejagnu.race([names, names, names])
print(f"three processes, same order:  sound={agreed.sound}  ran {agreed.counts}")

shorter = [n for n in names if n != "t10.c"]
split = dejagnu.race([names, shorter, names])
print(f"one process missing a file:   sound={split.sound}  ran {split.counts}")
print()
print("never run: ", split.skipped)
print("run twice: ", split.twice)
""")

lesson.md(f"""
The totals are identical. Thirty results either way, ten per process, and a summary block that
says thirty. One file was never compiled and another was compiled twice, and the only visible
trace is a `DUPLICATE` line for the second one, which is a state most people have trained
themselves to ignore.

GCC's own answer to this is five steps left in a comment, which tells you it has happened
before.
""")

lesson.code("""
detect = cuts["detect"]
print(detect.about)
print(f"{detect.span}  ({detect.citation})")
print()
print(detect.numbered({211: "compare the orders by hash, because nothing else will"}))
""")

lesson.md(f"""
An ordering can differ between processes for reasons that have nothing to do with the test
suite: a `glob` returning directory order rather than sorted order, an effective target check
that answers differently under load, a test that writes a file another test then globs. This
is invariant I4 in `BP-TESTSUITE`, and it is the one invariant in that blueprint with no
automated check behind it anywhere in GCC.

## Reading a `.sum`, and the only question worth asking

A run leaves a {term("sum file")} per tool: one line per result, then a summary block. The
lines are what matter and the block is what people read.
""")

lesson.code("""
before = dejagnu.parse_sum(\"\"\"
Running /src/gcc/testsuite/gcc.dg/dg.exp ...
PASS: gcc.dg/a.c (test for excess errors)
PASS: gcc.dg/b.c (test for errors, line 5)
PASS: gcc.dg/b.c (test for excess errors)
FAIL: gcc.dg/c.c (test for excess errors)
PASS: gcc.dg/d.c (test for excess errors)
\t\t=== gcc Summary ===
# of expected passes\t\t4
# of unexpected failures\t1
\"\"\")

after = dejagnu.parse_sum(\"\"\"
Running /src/gcc/testsuite/gcc.dg/dg.exp ...
PASS: gcc.dg/a.c (test for excess errors)
FAIL: gcc.dg/b.c (test for errors, line 5)
PASS: gcc.dg/b.c (test for excess errors)
PASS: gcc.dg/c.c (test for excess errors)
PASS: gcc.dg/e.c (test for excess errors)
\"\"\")

print("before:", dejagnu.summarize(before))
print("after: ", dejagnu.summarize(after))
""")

lesson.md(f"""
Identical. One failure before, one failure after, four passes each way. A summary block that
looks like nothing happened.

{
    claim(
        "two runs whose summary blocks are identical can differ in four separate tests, and "
        "the one that matters most is a test that stopped being run, which no count can show "
        "you because the total was made up again by a different test"
    )
}.
""")

lesson.code("""
for kind, which in dejagnu.regressions(before, after).items():
    print(f"{kind:<8} {len(which)}")
    for name in which:
        print(f"         {name}")
""")

lesson.md(f"""
Four changes. One regression, one fix, one test that appeared and one that vanished.

`gone` is the category to be frightened of. A test in yesterday's file and not in today's has
not failed. It stopped being run, and the usual reason is an
{term("effective target")} check that changed its answer: a feature the configure step no
longer detects, a `dg-skip-if` whose target list you widened, a test moved to a directory
whose `.exp` you are not running. The count went down by one and something else went up by
one, and nothing turned red.

This is why every project that runs GCC's test suite in earnest keeps the previous `.sum` and
compares, and why `contrib/compare_tests` exists in the tree. Comparing summary blocks is not
comparing runs.

## What this model does not do

The honest section, and it is longer than the one in B03 because there is more missing.

`gxray.dejagnu` handles eleven directives. Here is what happens to the rest.
""")

lesson.code("""
made_up = \"\"\"
/* { dg-do run { target int128 } } */
/* { dg-require-effective-target lp64 } */
/* { dg-skip-if "unreliable" { *-*-darwin* } } */
/* { dg-add-options bind_pic_locally } */
/* { dg-error "boom" } */
\"\"\"
test = dejagnu.read_test(made_up, path="gcc.dg/made-up.c")
print(f"{len(test.directives)} directives read, {len(test.unhandled)} not acted on:")
for one in test.unhandled:
    print("   ", one)
print()
print("and dg-do is read, but its target selector is not:", test.do_what)
""")

lesson.md(f"""
They are read, reported, and ignored. A test with any of them is a test whose verdict here may
differ from the real harness's, which is why the model has an `unhandled` property at all
rather than dropping what it does not know.

The larger omissions, in the order they would bite you:

- **Effective targets.** Several hundred of them, and a great many are answered by compiling
  a probe program and seeing whether it worked. That is the mechanism that decides whether a
  test runs at all, and none of it is here.
- **Selectors.** `{{ dg-error "x" "" {{ target lp64 }} }}` and the `xfail` form. Every
  directive can carry one.
- **`prune.exp` in full.** Two hundred lines of regular expressions for output that must not
  count: assembler warnings, linker noise, sanitiser preambles, twenty target specific cases.
  This model implements four patterns and the note switch.
- **Multiline output.** `dg-begin-multiline-output` and its partner, which is how the
  diagnostics with caret diagrams are checked, and which needs the full output rather than the
  line by line reading here.
- **`dg-do run`.** Everything in this lesson stops at `-S`, so nothing was executed, and a
  suite that cannot run a program cannot check what the program printed.
- **Cleanup, timeouts, `dg-line`, precompiled headers, and the parts of `dg-final` that are
  not the three dump scans.**

What the model does do is reach the same verdict as the real harness on the twelve real files
recorded here, and the recorder's `check` function asserts that on every build, so this is a
model that fails rather than rots.

`BP-TESTSUITE` in `blueprints/` is where the rest is written down, including the five
invariants and which of them GCC checks.

## Where to read more

`gcc/doc/sourcebuild.texi` is the reference for the directives, and it is genuinely good.
{cite("gcc/doc/sourcebuild.texi:1033@releases/gcc-16.2.0")} is the directive list and
{cite("gcc/doc/sourcebuild.texi:1491@releases/gcc-16.2.0")} is the effective target list, which
is worth skimming once so that you know the shape of what is available.

`gcc/testsuite/lib/gcc-dg.exp` is the file to read if you read one, and it is under two
thousand lines. `lib/target-supports.exp` is the one nobody reads, at eighteen thousand.

`contrib/compare_tests` and `contrib/test_summary` are the two scripts everybody ends up
using: the first diffs two `.sum` files properly, the second turns a run into the mail message
that gets posted to `gcc-testresults`.

## Boss fight

Nine questions about directives, command lines and `.sum` files.

    python lessons/b04-the-test-suite/grade.py

Two of them hand you a change to a test file and ask what the verdict becomes, which is the
skill this lesson is actually for. The last two are about reading a run rather than reading a
test, and both have an answer most people get wrong in the same direction.

## What to read next

B05 is the last lesson of this milestone, and it is the one that lets you write code that runs
inside the compiler without patching it. A plugin: forty lines of C++, one `-fplugin` flag, a
pass of your own inserted between two of GCC's, and the answer to why the plugin API is not an
API at all.
""")

raise SystemExit(lesson.save())
