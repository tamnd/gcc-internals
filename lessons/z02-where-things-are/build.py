"""Z02. How to be lost in four and a half million lines, productively.

The second half of getting started. Z01 taught what a line of GCC is made of. This one is
about the other thing that stops people, which is not being able to find the line at all.

The lesson is built around one chain, repeated until it is boring: something a compiler
printed, and the file and line that printed it. Four different routes get you there, and
knowing which one applies is the whole skill. Grepping for a literal works most of the time.
It does not work for a dump file name, because there is no literal. It does not work when the
file in the message was written by GCC's own build and is not in the tree. And it never tells
you when a line arrived, which is often the thing you actually wanted to know.

Everything here comes from `corpora/layout/gcc.json` and `corpora/source/z02.json`, both
written by `record.py` against the pinned tree, so the notebook runs in Colab with no GCC
checkout and no network. The counts are counts, not estimates.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "z02-where-things-are",
    "z02",
    title="How to be lost in four and a half million lines, productively",
    milestone="M1",
    summary=(
        "What every directory in the GCC tree is for, which files are written by the build "
        "rather than by a person, and the four routes from something a compiler printed back "
        "to the line of source that printed it"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# Z02. How to be lost in four and a half million lines, productively

{badge}

You cloned GCC. There are eighty six thousand source files in it and you are looking for one.

The instinct is to read the directory listing top to bottom and try to build a mental model
before touching anything. That takes a week and does not work, because the tree is close to
forty years old and the layout records where things were added rather than what they do.

What works is much smaller. You need to know what four or five directories are, you need to
know which files nobody wrote, and you need one reliable route from something a compiler
printed to the line of source that printed it. Everything else you can look up in ten seconds
once you have those.

This lesson is that. It ends with six things a real gcc-16 printed and the question is the
same one every time: where did this come from.

You need a browser. No compiler, no network, no GCC checkout.

**What you come away with**

- What is in each top level directory, and which one is the compiler
- The four file extensions GCC gave its own meaning, and what each one looks like
- How many ports there are, which is not the number in the directory listing
- How to tell a generated file from a written one before you waste an hour in it
- The chain from a dump file name to the pass, and from the pass to the file
- Six dump excerpts to track down, two of which need the history and not the checkout
""")

lesson.setup()

lesson.md(f"""
## The tree from orbit

Start with what is actually there. The map was recorded by walking the pinned checkout, so
these are counts rather than the numbers people repeat at conferences.

{
    claim(
        "three quarters of the source in the GCC tree is under gcc/, and the rest is libraries "
        "that ship alongside the compiler"
    )
}.
""")

lesson.code("""
import textwrap

from gxray import layout

tree = layout.load()
print(tree)
print()

top = [p for p in tree.places if "/" not in p.path]
print(f"{'directory':<16}{'files':>8}{'lines':>12}   what it is")
for place in top:
    print(f"{place.path:<16}{place.files:>8}{place.lines:>12}   {place.about}")

compiler = tree.place("gcc").lines
print()
print(f"gcc/ is {compiler} of {tree.lines} lines, {100 * compiler // tree.lines} percent")
""")

lesson.md("""
So `gcc/` is the compiler and everything else is a library that ships with it, a preprocessor,
a runtime, or the C++ standard library, which is a large separate project that happens to live
in the same repository. The last row of that table is the top level directories not worth
learning by name, added up, so the total is the real total.

The split is not even close to even, and that is the useful part. If you are reading about
optimization you are reading `gcc/`, and nothing outside it will ever be the answer. The one
outside directory worth knowing by name is `libstdc++-v3`, because a surprising number of
questions that look like compiler questions turn out to be library questions.
""")

lesson.md(f"""
## Inside gcc/

Now the same again, one level down. This is the listing worth actually learning.

{claim("the middle end has no directory of its own and sits loose in gcc/")}.
""")

lesson.code("""
inside = [p for p in tree.places if p.path.startswith("gcc/")]
inside.sort(key=lambda p: -p.lines)

print(f"{'place':<28}{'files':>8}{'lines':>10}   what it is")
for place in inside:
    print(f"{place.path:<28}{place.files:>8}{place.lines:>10}   {place.about}")

loose = tree.place("gcc/*")
print()
print(f"{loose.files} files with no subdirectory, holding {loose.lines} lines")
print("that is the middle end, the driver, the pass manager and the RTL back end")
""")

lesson.md("""
`gcc/*` in that table means the files sitting directly in `gcc/` with no subdirectory of their
own. That is where the interesting part of the compiler is: `passes.def`, `tree-ssa-ccp.cc`,
`combine.cc`, `cfgexpand.cc`, `gimplify.cc`. Nobody ever moved them into a `middle-end/`
directory and at this point nobody is going to.

The front ends did get directories. `gcc/c`, `gcc/cp`, `gcc/fortran`, `gcc/rust` and the rest.
`gcc/config` is every target, which is why it is the largest thing in the tree after the
testsuite. And `gcc/testsuite` has more files in it than everything else put together, which
is a good sign and also the first place to look when you want to know what a feature is
supposed to do.
""")

lesson.md(f"""
## Four and a half million lines

Here is the number in the title, and where it comes from.

{
    claim(
        "the compiler proper is about four and a half million lines, and the tests are seven "
        "tenths of that in fourteen times as many files"
    )
}.
""")

lesson.code("""
tests = tree.place("gcc/testsuite")
whole = tree.place("gcc")
proper = whole.lines - tests.lines
theirs = whole.files - tests.files

print(f"gcc/ altogether        {whole.lines:>10} lines in {whole.files:>6} files")
print(f"gcc/testsuite          {tests.lines:>10} lines in {tests.files:>6} files")
print(f"the compiler itself    {proper:>10} lines in {theirs:>6} files")
print()
print(f"the tests are {100 * tests.lines // proper} percent of the compiler by line count")
print(f"and {tests.files // theirs} times as many files, because a test is a small file")
""")

lesson.md("""
Four and a half million is the honest number for what you might one day read, and it counts
only the parts written in C, in C++, and in GCC's own little languages. The Ada front end is
mostly written in Ada and the Modula-2 front end is mostly written in Modula-2, and counting
those would double the total and tell you nothing, because they are separate compilers that
happen to live here.

Nobody has read four and a half million lines. The people who work on GCC have read a few
tens of thousands of lines, very carefully, in the corner they work in, and they find the rest
the same way you are about to.
""")

lesson.md(f"""
## Four extensions that do not mean what you think

GCC gives its own meaning to four file extensions, and one of them is a trap.

{claim("there is exactly one .pd file in the whole tree and it is match.pd")}.
""")

lesson.code("""
print(f"{'ext':<8}{'count':>7}  {'what it is':<24}notes")
for kind in tree.kinds:
    print(f"{kind.suffix:<8}{kind.count:>7}  {kind.name:<24}{kind.about}")
print()
for kind in tree.kinds:
    print(f"{kind.suffix:<8}{kind.example}")
""")

lesson.md(f"""
`.md` is a {term("machine description")}. It is not markdown, it has been called that since
1988, and `gcc/config/i386/sse.md` is thirty three thousand lines of it. Opening one in a
markdown previewer is a rite of passage.

Here is one pattern out of the aarch64 description, at
{cite("gcc/config/aarch64/aarch64.md:2965@releases/gcc-16.2.0")}.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("z02")
print(f"{len(cuts)} spans, {cuts.lines()} lines, cut from {cuts.tag}")
print()

md = cuts["md"]
print(md.about)
print(f"{md.span}  ({md.citation})")
print()
print(md.numbered())
""")

lesson.md(f"""
The bracketed part at the top is the RTL this pattern matches, and the table at the bottom
says which register classes each operand can be in and what assembly to print for each
combination. You do not need to read it yet. You need to recognize it, so that when a backtrace
lands you in `insn-recog.cc` you know the real source is a file like this one.

`.def` is the other one worth knowing on sight. It is a list, included several times with the
macro defined differently each time, which is how GCC turns one list into an enum, a table of
names, and half a dozen other things without repeating itself. There are
five hundred of them. {cite("gcc/tree.def:295@releases/gcc-16.2.0")} is two entries.
""")

lesson.code("""
for name in ("def", "opt", "pd"):
    span = cuts[name]
    print(f"{span.span}  {span.about}")
    print(span.numbered())
    print()
""")

lesson.md("""
`.opt` is every command line flag, and the build turns it into `options.cc` and `options.h`.
When you want to know what a flag actually sets, this is the file, and it is faster to read
than the manual.

`.pd` is a pattern description and there is one of them: `gcc/match.pd`, twelve thousand lines
of rewrite rules in a small language of its own. Most of what people call constant folding
lives there. The four lines above say that `x + 0`, `x -p 0`, `x - 0`, `x | 0` and `x ^ 0` are
all `x`, for five operators at once.
""")

lesson.md(f"""
## Fifty two directories, forty nine ports

Everybody quotes a number for how many targets GCC supports and everybody quotes a different
one. Count it.

{claim("three directories under gcc/config are not ports and have no machine description")}.
""")

lesson.code("""
print(f"{len(tree.ports) + len(tree.portless)} directories under gcc/config")
print(f"{len(tree.ports)} of them have a .md file, which is what makes a port a port")
print()
for n in range(0, len(tree.ports), 7):
    print("  " + "  ".join(f"{name:<12}" for name in tree.ports[n : n + 7]))
print()
print(f"no machine description: {', '.join(tree.portless)}")
""")

lesson.md(f"""
The three without are operating system support that a real {term("port")} includes rather than
targets in their own right. A Windows build of GCC uses `config/mingw` and `config/i386`
together.

Your machine is one of those forty nine directories, and about eighty percent of anything you
ever want to know about code generation on your machine is in it. The other way into a port is
from the middle end: wherever a pass needs the target's opinion it calls a
{term("target hook")}, and following that call into your port lands you on the exact line that
decided.
""")

lesson.md(f"""
## Nobody wrote this file

GCC's build compiles about thirty small programs and runs them, and they write source code
which is then compiled into the compiler. The result is a {term("generated file")}, which is
why the file in a backtrace is sometimes not in the tree at all, and why a file that is in the
tree is sometimes twenty eight thousand lines of something no human would type.

{claim("the file named in an Applying pattern message does not exist in the source tree")}.
""")

lesson.code("""
print(f"{'program':<24}{'writes':<44}from")
for gen in tree.generators:
    print(f"{gen.program:<24}{gen.writes:<44}{gen.reads}")

print()
for name in ("gimple-match-6.cc", "insn-recog.cc", "options.cc", "tree-cfg.cc"):
    instead = layout.generated(name)
    print(f"{name:<22}{instead or 'checked in, read it directly'}")
""")

lesson.md(f"""
So the rule is: if a file is in your build directory and not in the tree, a program in the
tree wrote it, and the thing you want to read is that program's input. `gimple-match-6.cc` is
one of eleven files that `genmatch` writes out of `match.pd`, split into eleven pieces only so
the build can compile them in parallel.

`genmatch` is worth one look for the shape of it. This is the part that writes the message you
are about to go looking for, at {cite("gcc/genmatch.cc:911@releases/gcc-16.2.0")}.
""")

lesson.code("""
gen = cuts["genmatch"]
print(gen.about)
print(f"{gen.span}  ({gen.citation})")
print()
print(gen.numbered())
""")

lesson.md("""
That is a `fprintf` that prints a `fprintf`. The words `Applying pattern` appear exactly once
in the tree, here, inside a string literal that is being written into a generated file. Grep
for them and this is the only hit, and if you did not know what `genmatch.cc` was you would
have no idea what to do with it.
""")

lesson.md(f"""
## From a dump file name to a source file

This is the chain, and it is the most useful thing in the lesson.

A dump file is called `hunt.c.114t.ccp2`. The `114` is a serial number, the `t` says it is a
GIMPLE dump, and `ccp2` is the pass, second run. There is nothing to grep for, because the
name of the dump file is not written anywhere as a string.

It comes from `pass_data`, which every pass fills in. The comment at
{cite("gcc/tree-pass.h:39@releases/gcc-16.2.0")} documents the whole thing in two lines.
""")

lesson.code("""
data = cuts["pass-data"]
print(f"{data.span}  ({data.citation})")
print(data.numbered({45: "this is the ccp in hunt.c.114t.ccp2"}))
""")

lesson.md(f"""
And the pipeline itself is one file, {cite("gcc/passes.def:80@releases/gcc-16.2.0")}, which is
a list of `NEXT_PASS` lines in the order they run. Here is the neighbourhood of the first run
of ccp, with the pass that makes the `1` in `ccp1`.
""")

lesson.code("""
print(cuts["passes"].numbered({84: "the first of five runs of ccp"}))
print()
print(cuts["make"].numbered({3083: "and this is where it lives"}))
""")

lesson.md(f"""
So the chain is: dump file name, strip the run number, look the name up in `passes.def`, find
the `make_pass_` function, and that file is the pass. GCC does not ship that table, so
`record.py` builds it by pairing every `pass_data` initializer with the `make_pass` function
that hands it over.

{claim("every pass in passes.def resolves to a file and to a dump name")}.
""")

lesson.code("""
named = [p for p in tree.passes if p.dump]
print(f"{len(tree.passes)} passes in passes.def")
print(f"{len(named)} of them resolve to a dump name, and all of them to a file and a line")
print()

for name in ("ccp2", "fre3", "dom2", "loopdone", "reload", "cunrolli"):
    print(f"{name:<12}{tree.find(name)}")

print()
print("a dump name can belong to more than one pass, which is not a mistake:")
for name in ("sra", "modref"):
    for one in tree.passes:
        if one.dump == name:
            print(f"  {one.name:<24}{one.path}:{one.line}")
""")

lesson.md("""
Those pairs are the whole program version of a pass and the per function version, and they
write into the same dump. `sra` is scalar replacement of aggregates, and `ipa-sra` is the same
idea applied across function boundaries, so they share a name and live in different files.

Going the other way is not quite total. Compile something with `-fdump-tree-all -fdump-rtl-all`
and a handful of the dump files you get are not in `passes.def` at all. `original` and `gimple`
come out of the front end before the pass manager starts, `statistics` is the dump machinery
dumping itself, and on aarch64 `early_ra` and `ldp_fusion1` are target passes that the back end
registers at startup rather than listing in the shared pipeline. Those are the exception and
you now know the shape of the exception, which is enough.

Try it the other way round. Pick any dump file in a build directory, take the name after the
number, and `tree.find` it. That is a ten second answer to a question that otherwise involves
guessing at file names.
""")

lesson.md(f"""
## Where a dump message comes from

Most dump text is a plain string in an `fprintf`, so the route is: take the numbers out and
search for the rest. Three examples, all of which you have read in a dump without thinking
about it.

{claim("the Simulating statement line in a ccp dump is not printed by tree-ssa-ccp.cc")}.
""")

lesson.code("""
for name in ("loops", "merge", "simulate"):
    span = cuts[name]
    print(f"{span.span}  ({span.citation})")
    print(f"  {span.about}")
    print(span.numbered())
    print()
""")

lesson.md("""
The third one is the interesting one. `Simulating statement:` shows up in the ccp1 dump, and
it is nowhere in `tree-ssa-ccp.cc`. It is in `tree-ssa-propagate.cc`, which is the engine that
drives ccp, copy propagation and two other passes, and the message is printed by the engine
rather than by any of them.

That happens constantly. The dump is named after the pass, and half of what is in it was
printed by shared code the pass called. If a grep for a message lands you somewhere that looks
unrelated, it usually is not.
""")

lesson.md(f"""
## When the checkout cannot answer

Grep tells you where a line is. It does not tell you when it arrived, who wrote it, what else
came with it, or which bug it was fixing, and those are frequently the questions.

    git log -S"Removing basic block" --oneline -- gcc/tree-cfg.cc
    git blame -L 2190,2196 gcc/tree-cfg.cc
    git log --format='%ad %an %s' --date=short -1 <commit>

`git log -S` searches for commits that added or removed a string, which is the one that finds
things. `git blame` is faster when you already have the line. Neither works in this repository,
because `vendor/gcc` is a shallow clone with one commit in it, so the two answers below were
recorded from a full clone and are in the corpus.

Two more places to know. `MAINTAINERS` at the top of the tree says who owns each part and who
has to approve a patch to it. And commit subjects carry `PR 12345` numbers that go straight
into Bugzilla, where the discussion is usually a better explanation than the commit message.

{claim("Removing basic block arrived with the entire GIMPLE and SSA middle end, in one commit")}.
""")

lesson.code("""
for clue in tree.hunt:
    if not clue.historic:
        continue
    print(f"{clue.dump}")
    print(f"  {clue.answer}   {clue.text}")
    print(f"  {clue.commit}  {clue.date}  {clue.author}")
    print(f"  {clue.subject}")
    print()

print("the seven routes, and what each one is for")
print()
for key, name, command, about in layout.ROUTES:
    print(f"{key:<13}{name}")
    print(f"{'':<13}{command}")
    for line in textwrap.wrap(about, 76):
        print(f"{'':<13}{line}")
    print()
""")

lesson.md("""
The tree-ssa branch merge on 13 May 2004 is the commit that gave GCC a GIMPLE middle end and
SSA form at all. Nearly everything this course is about arrived in it. Finding that out took
one `git log -S` on a string you saw in a dump, which is a good demonstration of why the
history is worth reaching for.

The other one is smaller and as useful. The rule at `match.pd:239` traces back to the
commit that invented `match.pd` in October 2014, which tells you that everything in that file
is newer than the compiler around it.
""")

lesson.md(f"""
## Which files not to open yet

Some files in GCC are large because the thing they describe is large, and some are large
because they have absorbed twenty years of special cases. The second kind will teach you very
little on a first read and will convince you that you cannot do this.

{claim("the largest file under gcc/ is a hand written parser and not generated at all")}.
""")

lesson.code("""
print(f"{'file':<38}{'lines':>8}   why")
for big in tree.biggest:
    print(f"{big.path:<38}{big.lines:>8}   {big.about}")

print()
print("and the short ones, which is where to actually start:")
for one in tree.notable:
    print(f"{one.path:<38}{one.lines:>8}   {one.about}")
""")

lesson.md("""
`combine.cc` and `dwarf2out.cc` are the two to leave alone for a month. Both are correct, both
are important, and neither will make sense until you have context that comes from somewhere
else. `insn-recog.cc` is not in that list because it is not in the tree at all, which you now
know how to notice.

`passes.def` is five hundred lines and is the best afternoon in the compiler. `tree.def` is a
list with a comment on every entry. `tree-ssa-ccp.cc` is a complete optimization pass that
fits in your head. Start there.
""")

lesson.md("""
## The picture

The tree on one sheet, with the routes down the side, is in
[`diagrams/finding-things.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/z02-where-things-are/diagrams/finding-things.excalidraw).
It is meant to sit in a second window while you go digging.

## Six questions

Each of these has an answer that sounds sensible and is wrong about GCC. Commit before you
open the reveal.
""")

lesson.code("""
from gxwidgets import PredictGate

QUESTIONS = [
    (
        "A backtrace points at insn-recog.cc:284091. Where do you look?",
        [
            ("The .md file for the target, because insn-recog.cc is generated from it", ""),
            (
                "gcc/insn-recog.cc, at that line",
                "There is no such file in the tree. genrecog writes it during the build "
                "out of the machine description, so the line number is a line in output.",
            ),
            (
                "gcc/recog.cc, which is the closest name",
                "recog.cc is real and is the recognizer's driver, but the enormous "
                "generated matcher is a different file with a different origin.",
            ),
        ],
        "The target's .md files. The line number belongs to a file the build wrote.",
    ),
    (
        "You want the source for the pass behind a dump called a.c.212t.dom3. Where is it?",
        [
            ("Look up dom in passes.def, then find make_pass_dominator", ""),
            (
                "grep for the string dom3",
                "Nothing in the tree contains dom3. The 3 is the run number, added by the "
                "dump machinery, and the pass is called dom.",
            ),
            (
                "grep for a file called dom3.cc",
                "Dump names and file names are unrelated. The dump name is a string inside "
                "the pass_data initializer and can be anything.",
            ),
        ],
        "Strip the run number, look the name up, and follow it to the make_pass function.",
    ),
    (
        "How many targets does GCC 16 support?",
        [
            (
                "Forty nine, if you count directories under gcc/config with a machine description",
                "",
            ),
            (
                "Fifty two, the number of directories under gcc/config",
                "Three of them are operating system support that a real port includes. "
                "They have no .md file and are not targets on their own.",
            ),
            (
                "Hundreds, because of all the variants",
                "One port covers many variants. The aarch64 port alone covers dozens of "
                "cores, and they are all one directory and one machine description.",
            ),
        ],
        "Forty nine directories have a machine description. The other three are shared bits.",
    ),
    (
        "Where does the middle end live?",
        [
            ("Loose in gcc/, with no directory of its own", ""),
            (
                "gcc/middle-end/",
                "There is no such directory. The front ends got directories and the middle "
                "end never did, which surprises everybody exactly once.",
            ),
            (
                "gcc/tree-ssa/",
                "Also not a directory. The tree-ssa files are named tree-ssa-something.cc "
                "and sit directly in gcc/, which is where the naming convention comes from.",
            ),
        ],
        "Directly in gcc/. About a thousand files with no subdirectory.",
    ),
    (
        "A message in the ccp1 dump is nowhere in tree-ssa-ccp.cc. What happened?",
        [
            ("Shared code the pass calls printed it, and the dump is named after the pass", ""),
            (
                "The dump is misnamed",
                "It is not. A dump file collects everything printed while that pass runs, "
                "wherever in the compiler it was printed from.",
            ),
            (
                "The message is built up from pieces so it never appears as one string",
                "That does happen, and it is worth checking. Here it is one literal, in "
                "tree-ssa-propagate.cc, which is the engine four passes share.",
            ),
        ],
        "Passes call shared code, and shared code prints into whatever dump is open.",
    ),
    (
        "Why would you reach for git log -S over git grep?",
        [
            ("Because you want to know when a line arrived and what came with it", ""),
            (
                "Because it is faster on a large tree",
                "It is much slower. It walks the history and diffs it, and on GCC that "
                "takes a while. You use it for the answer, not for the speed.",
            ),
            (
                "Because git grep misses lines in files that were renamed",
                "git grep searches the checkout, so a renamed file is still searched under "
                "its current name. Renames are a reason to use log with --follow, not -S.",
            ),
        ],
        "It searches the history for a string appearing or disappearing, which grep cannot do.",
    ),
]

gates = [
    PredictGate(question, options, answer=answer, id=f"z02-q{n}")
    for n, (question, options, answer) in enumerate(QUESTIONS, start=1)
]
""")

lesson.code("""
from IPython.display import HTML, display

for gate in gates:
    display(HTML(gate.render()))

print(f"{len(gates)} questions. Answers are in each widget behind the reveal.")
""")

lesson.md("""
## Where to read more

`gcc/doc/gccint.texi` is the internals manual and its first two chapters are a tour of the
tree that is better than anything written about it since. It is also a good demonstration that
the manual exists, which people forget.

`MAINTAINERS` at the top of the tree is a thousand lines and takes five minutes. Reading it
once tells you the shape of the project better than a diagram would.

The gcc-patches archive is public and searchable, and every change in the tree was posted
there first with a rationale attached. When a commit message is one line and unhelpful, the
posting usually is not.

## Boss fight

Six things a real gcc-16 printed, compiling a five line C file. For each one, find the file
and the line that printed it.

    python lessons/z02-where-things-are/grade.py

Four want an answer of the form `gcc/cfgloop.cc:163`. Two want a year on the end as well,
because a checkout cannot answer them and the history can. Line numbers are marked with three
lines of slack either way.

If you have a full clone of GCC handy, do it there with `git grep` and `git log -S` and time
yourself. That is the exercise. The grader is only there to tell you whether you found it.

## What to read next

That is the ramp. You can read a line of GCC and you can find one.

T01 starts the course proper: what actually runs when you type `gcc hello.c`, which is four
programs and not one.
""")

raise SystemExit(lesson.save())
