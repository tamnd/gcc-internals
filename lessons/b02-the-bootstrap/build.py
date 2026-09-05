"""B02. Building it three times, and the one thing that proves.

B01 ended with `--disable-bootstrap` and a promise. This is the promise.

The lesson has a problem the other lessons in Part II do not. Its subject takes four hours to
run once, produces tens of thousands of object files, and the interesting outcome is the one
that almost never happens. A notebook cannot wait for it, and a lesson that only described it
would be a lesson about a thing the reader has to take on faith, which is the opposite of
what this course is for.

So the oracle is brought here instead. `gxray.bootstrap.compare` is GCC's compare rule,
re-implemented from `Makefile.tpl:1824` and handed the exclusion list read out of
`configure.ac`, and `record.py` next door compiled six pairs of real object files with a real
GCC 16.2, inducing one outcome per pair on purpose. Six pairs instead of thirty thousand, so
the scale is a lie and the mechanism is not, and the notebook says so where it matters.

The order is the argument first and the machinery second. Why three and not two is a real
piece of reasoning and most descriptions of a bootstrap skip it, which is why people come
away thinking it is a ritual. Once that is settled, the renaming, the sixteen bytes and the
six forgiven patterns are all consequences of it rather than trivia.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "b02-the-bootstrap",
    "b02",
    title="Building it three times, and the one thing that proves",
    milestone="M2",
    summary=(
        "Why a compiler is built three times and compared twice, what that comparison can and "
        "cannot catch, the six files it is told to ignore, and a real stage comparison failure "
        "induced on purpose so you can see what it looks like before it happens to you"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# B02. Building it three times, and the one thing that proves

{badge}

B01 put `--disable-bootstrap` on the configure line and said it was the difference between
twenty two minutes and four hours. That is true and it is not the interesting part. The
interesting part is what the four hours buy, because it is not three copies of the same work.

A compiler is a program that is compiled by a compiler. That is a circle, and the circle is
load bearing: every bug in the compiler that built yours is a bug that could be sitting in
yours, silently, in generated code that no test compiles. You cannot test your way out of
this with a test suite, because a test suite runs the compiler and a miscompiled compiler
runs.

What GCC does instead is build itself three times and compare the last two, and if they are
not byte for byte identical it stops. That check is the {term("stage comparison")}, and this
lesson is about why it works, exactly how much it proves, and the considerable list of things
it does not.

You need a browser. Nothing here starts a build. The object files you are going to compare
were compiled by a real GCC 16.2 before this notebook was written, and the rule that compares
them is GCC's own rule, so the comparison you watch is a real one over a small pile.

**What you come away with**

- The fixed point argument, which is why three and not two, in about a paragraph
- Nine declared stages, and the two of them that check anything
- Which twenty five of GCC's fifty four host modules are rebuilt every single stage
- Why every stage builds in a directory called `gcc`, demonstrated by breaking it
- The compare rule read line by line, then run, over object files that really differ
- The six files a bootstrap is told to ignore, and what each hole is big enough to hide
- What a `Bootstrap comparison failure!` actually looks like and what to do about it
- The four hour price, and the two cheaper things to run instead
""")

lesson.setup()

lesson.md(f"""
## Why three, and not two

Start with the smallest version of the problem. You have a compiler, call it *old*, and some
source, call it *S*. You compile *S* with *old* and get a compiler, call it *A*.

Is *A* correct? You have no idea. *A* is *S* as understood by *old*. If *old* miscompiles one
function in *S*, then *A* is a compiler with a bug in it that is not in *S* and never will be,
and no amount of reading *S* will find it.

So compile *S* again, this time with *A*, and call the result *B*. Now *B* is *S* as
understood by *A*. This is better in a way that is easy to say and easy to miss: *B* was
produced by the compiler you are trying to ship rather than by whatever was lying around.
Compile once more with *B* and you get *C*, which is *S* as understood by *B*.

Here is the step everything rests on. *B* and *C* are both *S*, compiled by *A* and by *B*
respectively. And *A* and *B* are the same source. So if *A* and *B* really are the same
compiler, then *B* and *C* must be the same program, byte for byte. Compare them. If they
differ, then *A* and *B* disagreed about how to compile something, which means the compiler
built by *old* and the compiler built by itself are not the same compiler, which means one of
them is wrong.

That is why two is not enough. You cannot compare *A* with *B* usefully, because *A* was built
by a different compiler and would legitimately differ: different inlining, different register
allocation, a different version of the standard library. *B* and *C* are the first pair that
have no legitimate excuse to differ.

What it proves is precisely this and no more: the compiler has reached a fixed point. Feeding
its own source through it again does not change it. What it does not prove is that the fixed
point is the right one. A compiler that consistently gets something wrong, and gets it wrong
the same way when compiling itself, sails through. Ken Thompson wrote the famous paper about
deliberately arranging exactly that, and the comparison does not catch it. It catches
inconsistency, not incorrectness, and those are different words on purpose.
""")

lesson.md(f"""
## Nine stages, two of which check anything

The three stage story above is the one everybody tells. The tree declares rather more than
three, and it is worth seeing the whole list once, because two of the extra ones are things
you may actually want to run.

{
    claim(
        "GCC declares nine bootstrap stages and exactly two of them compare their output "
        "against anything"
    )
}.
""")

lesson.code("""
from gxray import bootstrap

boot = bootstrap.load()
print(boot)
print()
for one in boot.stages:
    print(f"  {one}")
""")

lesson.md(f"""
The right hand column is the whole point. Six of those nine compilers are built, used to build
something else, and never checked against anything. `stageprofile` and `stagetrain` exist to
produce profile data, `stagefeedback` is the compiler built using it, and the same three again
with `auto` in front use hardware sampling instead of instrumentation. They are how a
distribution ships a GCC that is ten to twenty percent faster than a plain one, and none of
them is compared to anything, because a profiled compiler is deliberately not the same program
as an unprofiled one.

Only `stage3` and `stage4` compare, and `stage4` is not built by default. So the entire
correctness argument of a normal `make bootstrap` rests on one comparison, between stage two
and stage three, at the end of the third build.

Each stage is also built with different flags, which is the other reason the stages are not
three copies of one job.
""")

lesson.code("""
for one in boot.default:
    print(f"stage{one.id}, built by {one.built_by}")
    for flag in one.cflags or ("(nothing of its own)",):
        print(f"    {flag}")
    print()
""")

lesson.md(f"""
Read those three blocks as a strategy rather than as settings.

Stage one is built with `stage1_cflags`, which is `-g` and no optimisation at all, and with
`--disable-libstdcxx-pch`. It is built by a compiler you do not control and it is thrown away,
so the only thing that matters about it is that it appears quickly. It is correspondingly slow
to run, which is why the first stage feels fast and the second feels slow.

Stage two turns internal checking *off* with `-fno-checking`. That looks backwards until you
remember that stage two's job is to build stage three, and a {term("checking build")} would
make that take twice as long while checking a compiler that is about to be discarded anyway.

Stage three turns it back on with `-fchecking=1`. This is the compiler you keep.

Here is the sharp edge in that. Stage two and stage three are built with *different flags*,
and stage three is compared against stage two. Those flags are the flags each stage's compiler
was built with, not the flags it compiles the next stage with, so the comparison is still
comparing like with like. It is a distinction worth holding onto for a minute, because it is
exactly the sort of thing that goes wrong when you start passing your own `CFLAGS` to a
bootstrap and B01 warned you not to.

You can see where a later stage gets its compiler from, at
{cite("Makefile.tpl:278@releases/gcc-16.2.0")}.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("b02")
print(f"{len(cuts)} excerpts, {cuts.lines()} lines, cut from {cuts.tag}")
print()
exports = cuts["exports"]
print(exports.about)
print(f"{exports.span}  ({exports.citation})")
print()
print(exports.numbered({281: "prev-gcc, which is a directory that gets renamed into existence"}))
""")

lesson.md(f"""
`prev-gcc` is a name, not a stage. Whatever the previous stage was, it is renamed to `prev-gcc`
before this stage starts and renamed back afterwards, so the makefile can refer to "the
compiler that came before" without knowing which one that is. Hold that thought; section four
is entirely about why the renaming exists.

## What actually gets rebuilt

Not everything. A GCC source tree contains a great deal that is not the compiler, and building
`dejagnu` three times would be four hours well wasted.

{
    claim(
        "fewer than half of GCC's host modules are inside the bootstrap loop, and the ones that "
        "are include the libraries the compiler links against"
    )
}.
""")

lesson.code("""
inside, outside = boot.inside, boot.outside
total = len(inside) + len(outside)
print(f"{len(inside)} rebuilt every stage, {len(outside)} built once, {total} host modules")
print()
for n in range(0, len(inside), 5):
    print("  " + "  ".join(f"{name:<24}" for name in inside[n : n + 5]))
print()
print("built once, outside the loop:")
for n in range(0, len(outside), 5):
    print("  " + "  ".join(f"{name:<24}" for name in outside[n : n + 5]))
""")

lesson.md(f"""
The first list is the answer to "what is the compiler". `gcc` is the obvious one, `libcpp` is
the preprocessor, `libiberty` is the portability layer, `gmp` `mpfr` `mpc` and `isl` are the
arithmetic libraries B01 made you install, and `bfd` `gas` `ld` and friends are there because a
combined tree can build binutils too. Every one of those is code that ends up inside `cc1` or
is linked against it, so a bug in any of them is a bug in the compiler, so they go round the
loop.

The second list is tools. `gdb`, `dejagnu`, `expect`, `flex`, `bison`, `texinfo`. They are built
with the compiler you already had, once, and nobody compares them, because they are not the
thing under test.

There is a third category that is in neither list and matters more than either.
""")

lesson.code("""
staged, once = boot.target_inside, boot.target_outside
print(f"{len(staged)} target libraries staged, {len(once)} built once")
print()
print("  staged: " + ", ".join(staged))
print()
print("  once:   " + ", ".join(once))
""")

lesson.md(f"""
Target libraries are not host modules. They are compiled by *this stage's* compiler, for the
target machine, which is a different thing from being compiled by the compiler that is doing the
building. Nine of them are staged, which means they are rebuilt every stage and their object
files are compared.

That is the only generated *target* code the comparison ever sees, and `libgcc` is the important
one on the list. `libgcc` is what implements 64 bit division on a 32 bit machine, what unwinds
an exception, and what runs before `main`. It is compiled by the compiler under test, three
times, and the last two have to agree.

## The renaming, and why

Now the mechanical detail that turns out not to be a detail at all.

Each stage builds in a directory named after itself, `stage1-gcc`, `stage2-gcc`, `stage3-gcc`.
Except that it does not, quite. Read GCC's own comment on the subject, at
{cite("Makefile.tpl:1747@releases/gcc-16.2.0")}.
""")

lesson.code("""
why = cuts["why"]
print(why.about)
print(f"{why.span}  ({why.citation})")
print()
notes = {1750: "this is the whole reason", 1754: "naked names, because scripts assume it"}
print(why.numbered(notes))
""")

lesson.md(f"""
"The 'compare' process will fail (on debugging information) if any directory names are
different." That single parenthesis is the entire section.

Compile the same source file twice with `-g`, once in a directory called `stage2-gcc` and once
in a directory called `stage3-gcc`, and the two object files are not identical. Nothing about
the code differs. What differs is a string: GCC records the directory it was invoked in, in the
debug information, as `DW_AT_comp_dir`, because a debugger needs to resolve relative paths later.
Two directories, two strings, two different object files, and a comparison that fails on every
single file for a reason that has nothing to do with compilers.

You do not have to take that on faith. Here it is, done on purpose.

{
    claim(
        "the same source compiled by the same compiler with the same flags produces different "
        "object files if the directory is named differently"
    )
}.
""")

lesson.code("""
pair = boot.pair("gcc/gimplify.o")
print(pair.about)
print(f"recorded from {boot.compiler} on {boot.host}")
print()
print(f"stage2 copy: {len(pair.left):,} bytes")
print(f"stage3 copy: {len(pair.right):,} bytes   same size, so it is not extra content")
print()
at = pair.differs_at()
print(f"first differing byte: {at}")
print(f"  stage2: {pair.left[at - 40 : at + 10]!r}")
print(f"  stage3: {pair.right[at - 40 : at + 10]!r}")
""")

lesson.md(f"""
There it is, in plain ASCII inside the object file, a couple of kilobytes in. The two files are
the same length and agree on every byte up to the directory name.

So the fix is the renaming. Before a stage runs, its build directory is renamed from
`stage3-gcc` to `gcc`, and the previous stage's is renamed from `stage2-gcc` to `prev-gcc`.
Every stage therefore compiles in a directory called `gcc`, records that string, and produces
object files that can be compared. Afterwards they are renamed back so they can coexist. Here is
the rule that does it, at {cite("Makefile.tpl:1767@releases/gcc-16.2.0")}.
""")

lesson.code("""
start = cuts["start"]
print(start.about)
print(f"{start.span}  ({start.citation})")
print()
notes = {
    1776: "this stage becomes plain gcc",
    1777: "and the one before becomes prev-gcc",
}
print(start.numbered(notes))
""")

lesson.md(f"""
`mv`, not a symbolic link, and the comment above says why: symlinks to directories are not
reliable everywhere. So a bootstrap spends a noticeable amount of its life renaming
twenty five directories back and forth, twice per stage, and if you interrupt a bootstrap at the
wrong moment you can find a `gcc` directory that make thinks is a stage and you think is a
mistake. `make distclean` and start again.

The other thing worth knowing about how the stages are driven is the word GCC uses for it.
""")

lesson.code("""
bubble = cuts["bubble"]
print(bubble.about)
print(f"{bubble.span}  ({bubble.citation})")
print()
print(bubble.numbered({1801: "each stage depends on the previous one bubbling first"}))
""")

lesson.md(f"""
{term("bubbling")} is why a bootstrap is a dependency graph and not a shell script. `stage3-bubble`
depends on `stage2-bubble`, which depends on `stage1-bubble`, so asking for stage three asks
for the whole chain. The `-lean` checks in the middle are the part that makes it useful: if you
fix a bug in the compiler and re-run, the stages that are still valid are skipped and only the
affected ones are remade. That is what "bubble a bug fix through all the stages" in the comment
means, and it is the difference between a four hour rebuild and a forty minute one.

## The rule itself

Thirty four lines of shell, embedded in a makefile template, and it is the entire oracle. Read
it once slowly, at {cite("Makefile.tpl:1824@releases/gcc-16.2.0")}.
""")

lesson.code("""
rule = cuts["compare"]
print(rule.about)
print(f"{rule.span}  ({rule.citation})")
print()
notes = {
    1835: "every .o in the later stage, and only .o",
    1839: "a file the earlier stage does not have is skipped, silently",
    1840: "the comparison itself, expanded from do_compare",
    1843: "the exclusion list, pasted in by configure",
    1846: "anything else goes in .bad_compare and fails the build",
}
print(rule.numbered(notes))
""")

lesson.md(f"""
Five things in there are worth naming.

It only looks at `*$(objext)`, which is `.o`. Not the executables, not the libraries, not the
generated sources. Just object files.

It iterates over the *later* stage's files and skips anything the earlier stage does not have,
at line 1839. A file that appeared in stage three and does not exist in stage two is not a
failure, it is silence. That is a real hole and we will look at it in a moment.

The comparison is `$(do-compare)`, which is not `cmp` directly but whatever configure worked
out `cmp` can do on this machine. And whatever it is, it ignores the first sixteen bytes, at
{cite("config/acx.m4:468@releases/gcc-16.2.0")}.
""")

lesson.code("""
skip = cuts["skip"]
print(skip.about)
print(f"{skip.span}  ({skip.citation})")
print()
print(skip.numbered({478: "the fallback, which is two temporary files and a cmp"}))
print()
print(f"gxray.bootstrap uses the same number: SKIP = {bootstrap.SKIP}")
""")

lesson.md(f"""
Sixteen bytes, because some object file formats put a timestamp in the header and a compiler
that records when it ran would otherwise never compare equal to itself. On ELF it is not
strictly needed and it does no harm. Note also the shape of that autoconf test: it does not ask
what `cmp` this is, it asks `cmp` to do the thing and sees whether the answer is right, which is
the correct way to write a feature test and is worth stealing.

Now run it. This is `gxray.bootstrap.compare`, which is the loop above written in Python with
the same sixteen bytes and the same exclusion list, over six pairs of object files that a real
GCC 16.2 really produced.
""")

lesson.code("""
result = boot.compare()
print(f"{'pair':<40}{'bytes':>8}  what was done to it")
for one in boot.objects:
    size = "absent" if one.missing else f"{len(one.right):,}"
    print(f"{one.name:<40}{size:>8}  {one.about}")
print()
print(f"looked at {result.checked}, skipped {len(result.skipped)}, identical {len(result.same)}")
""")

lesson.md(f"""
Six pairs, not thirty thousand, and that number is the one honest limitation of this section. A
real comparison walks every object file in the tree and takes several minutes on its own. What
these six are is one of each thing that can happen, induced deliberately, so that the rule has
something to say about each branch.

{
    claim(
        "the compare rule says nothing at all about a file that exists in the later stage and "
        "not in the earlier one"
    )
}.
""")

lesson.code("""
gone = boot.pair("gcc/rust/rust-lang.o")
print(f"{gone.name}: left={gone.left}, right={len(gone.right):,} bytes")
print(f"missing from the earlier stage: {gone.missing}")
print()
print(f"the rule skipped: {', '.join(result.skipped)}")
print(f"named in the report: {gone.name in result.report()}")
""")

lesson.md("""
That is `if test ! -f $$f1; then continue; fi` and it is not paranoia to care about it. A front
end that is built in stage three and was not built in stage two produces exactly this, and so
does a stage two directory that got partially cleaned. The comparison passes, and the thing it
passed on is a file it never looked at.

## The six it is told to ignore

Now the part that is genuinely uncomfortable. Some object files cannot compare equal, for
reasons that are real, so the build is given a list of files it is allowed to find different.
Each entry on that list is a hole in the oracle.
""")

lesson.code("""
patterns = cuts["exclusions"]
print(patterns.about)
print(f"{patterns.span}  ({patterns.citation})")
print()
print(patterns.numbered({4405: "shell case syntax, and | separates alternatives"}))
print()
for one in boot.exclusions:
    print(f"  {one}")
""")

lesson.md(f"""
Take them one at a time, because they are not all the same kind of thing.

`gcc/cc*-checksum$(objext)` is the honest one. Each compiler binary contains a checksum of the
object files it was linked from, which is how a plugin knows it is loading into the compiler it
was built against. That checksum is a function of the stage, so it *must* differ, and forgiving
it costs nothing because the thing it summarises is compared directly.

`gcc/ada/*tools/*` is Ada's build tools, which are built in a way that does not reproduce.

The three `gm2` entries are Modula-2, and one of them is the interesting one. `M2Version`
records the date of the build. A bootstrap that crosses midnight would fail on it. So it is
forgiven, and so is anything else in that file.

`gcc/cobol/parse$(objext)` is a generated parser whose output depends on the version of `bison`
used, which is not the same in each stage.

{
    claim(
        "a forgiven difference is still found, and the rule can say exactly which pattern "
        "forgave it"
    )
}.
""")

lesson.code("""
for one in ("gcc/cc1-checksum.o", "gcc/m2/gm2-compiler-boot/M2Version.o"):
    pair = boot.pair(one)
    print(f"{one}")
    print(f"  {pair.about}")
    print(f"  differs at byte {pair.differs_at()}, forgiven by {boot.forgives(one)}")
print()
print("and a file that is not on the list:")
print(f"  gcc/expr.o -> {boot.forgives('gcc/expr.o')!r}")
print(f"  gcc/ada/gnattools/gnatmake.o -> {boot.forgives('gcc/ada/gnattools/gnatmake.o')!r}")
""")

lesson.md(f"""
Two details in that last pair of lines. The patterns are written with `$(objext)` in them
because make expands it before the shell sees it, so the thing actually matched is
`gcc/cc*-checksum.o`. And the wildcard crosses directory separators, because this is a shell
`case` and not a glob, which is why `gcc/ada/*tools/*` catches `gcc/ada/gnattools/gnatmake.o`.

The uncomfortable part is what a hole is big enough to hide. Anything the compiler gets wrong
that only shows up in `gcc/cobol/parse.o` will never be caught by this comparison, forever.
Nobody thinks that is likely. Nobody has checked either.

## What a failure looks like

Here is the thing this lesson exists to show you. Two of those six pairs differ for reasons
that are not on the forgiven list, one of them because the source was compiled at a different
optimisation level, which is what a compiler that miscompiles itself actually produces.

{
    claim(
        "one unforgiven difference is enough to fail the comparison, and what it prints does "
        "not say what differed or where"
    )
}.
""")

lesson.code("""
print(result.report())
""")

lesson.md(f"""
That is the output, and on a real bootstrap the only thing different about it is that the list
at the bottom is drawn from thirty thousand files rather than five. `Comparing stages 2 and 3`,
some warnings you were told to expect, and then four lines that mean four hours have produced
nothing you can ship.

Note what is not in it: any indication of *what* differs, or where, or why. The rule ran `cmp`
with its output redirected to `/dev/null` and kept only the exit status. All you get is a list
of names, in a file.
""")

lesson.code("""
print("$ cat .bad_compare")
print(result.bad_compare(), end="")
print()
print(f"{len(result.bad)} unforgiven, out of {result.checked} compared")
for one in result.bad:
    pair = boot.pair(one.name)
    print(f"  {one.name:<20}differs at byte {one.at:<8}{pair.about}")
""")

lesson.md("""
Now look at the two byte offsets, because they are the first diagnostic you have and they say
different things.

`gcc/fold-const.o` differs early, in the first hundred bytes or so. That is inside the code, and
it means the two compilers generated different instructions for the same source. This is the
real thing. Something is wrong with one of the two compilers.

`gcc/gimplify.o` differs late, past a kilobyte in, and the bytes around it were readable ASCII.
That is a path or a string in the debug information, and it almost always means something about
the build environment leaked in rather than something about the compiler. A build done in two
differently named directories, a `__FILE__` with an absolute path in it, an embedded timestamp.

So the first thing to do with a real `.bad_compare` is not to panic and not to file a bug. It is
`cmp -l` on the pair to find the offset, and then `objdump -d` on both if the offset is in the
text section or `readelf --debug-dump` if it is not. If it is code, you have found something. If
it is a string, you have found a reproducibility problem, which is a real bug but a different
one, and the GCC bug database has plenty of both.

The other thing to know is that a failed comparison leaves everything in place. Both stage
directories are still there, renamed back to `stage2-gcc` and `stage3-gcc`, and both compilers
still work. You can run them, diff their `-v` output, and compile the offending file by hand
with each of them.
""")

lesson.md(f"""
## What it costs, and the two cheaper things

Four hours is the number B01 gave and this project's own matrix is where it came from.

{
    claim(
        "the bootstrap is the most expensive configuration this project builds, by a factor of "
        "five over the next one"
    )
}.
""")

lesson.code("""
from gxray import toolchain

print(toolchain.table())
print()
one = toolchain.plan("boot")
print(f"{one.id}: {one.cost()}, {one.config.purpose}")
print()
print(one.configure())
""")

lesson.md(f"""
`--enable-bootstrap` and `--enable-checking=release`, and note that there is no `CFLAGS` on that
line. B01 explained why: a bootstrap ignores yours and uses `BOOT_CFLAGS`, which is `-g -O2`.

You do not have to run the whole thing, and there are two useful ways to run less of it.

The first is a stage target. Each stage that has one can be asked for by name, and stopping
early is a legitimate thing to do.
""")

lesson.code("""
for one in boot.stages:
    if not one.target:
        continue
    checks = f"compares it against stage{one.compares}" if one.compares else "nothing compared"
    print(f"  make {one.target:<24}stops after stage{one.id}, {checks}")
""")

lesson.md(f"""
`make bootstrap2` builds two stages and stops. It costs about two thirds of a full bootstrap and
proves nothing at all, because nothing is compared, but it does answer the question "can the
compiler I just built compile GCC", which is a much better smoke test than compiling hello
world and is the reason the target exists.

`make bootstrap4` builds a fourth stage and compares it against the third. Stage three and stage
four are both built by compilers that are byte identical, so a difference between them is not a
compiler bug, it is non-determinism in the compiler: something reading a hash table in memory
address order, or a temporary filename leaking into output. It is how you chase reproducibility
bugs and is otherwise a waste of an hour.

The second way to run less is to run something else entirely. There are nineteen of what GCC
calls a {term("build config")} in `config/`, each one a makefile fragment that changes how the
stages are built, and `--with-build-config=` takes them by name.
""")

lesson.code("""
print(f"{len(boot.configs)} fragments in config/")
print()
for n in range(0, len(boot.configs), 3):
    print("  " + "".join(f"{name:<38}" for name in boot.configs[n : n + 3]).rstrip())
""")

lesson.md("""
Three of those are worth knowing by name.

`bootstrap-debug` is the one that is on by default and that most people have never heard of. It
compares stage two and stage three *twice*: once normally, and once with `-g` stripped from both,
using `contrib/compare-debug`. The point is to catch a specific and nasty class of bug, where
adding `-g` to a compilation changes the code the compiler generates. It should not, debug info is
supposed to be inert, and when it is not the result is a program that behaves differently under a
debugger. `bootstrap-debug-lean` and `bootstrap-debug-big` are the same idea with different
tradeoffs between disk and time.

`bootstrap-lto` builds the stages with link time optimisation, which is both a way to get a faster
compiler and a very thorough test of LTO itself, since the thing being LTO'd is a few million lines
of C++.

`bootstrap-ubsan` and `bootstrap-asan` build the stages under the undefined behaviour and address
sanitizers. A compiler with an out of bounds read in it will usually still produce correct output,
right up until it does not, and this is how those get found. They are slow and they find things.

You combine them with commas: `--with-build-config="bootstrap-debug bootstrap-lto"`.
""")

lesson.md(f"""
## What the comparison does not cover

Worth collecting in one place, because the list is longer than people expect and every item on
it is a real thing that has happened.

It does not cover files that exist in the later stage only, which the rule skips in silence.

It does not cover the six forgiven patterns.

It does not cover anything that is not an object file. Not the linked executables, not the
libraries, not the generated sources, not the installed tree.

It does not cover a bug that is stable. A compiler that miscompiles the same construct the same
way every time will produce a stage three identical to stage two and pass, which is the fixed
point argument's known limit and the whole subject of Thompson's paper.

It does not cover anything about the *target* code beyond what happens to be in `libgcc` and the
target libraries, which are compared. Your compiler could emit wrong code for a construct that
GCC's own source does not contain, and the bootstrap has nothing to say.

And it does not run at all unless you asked for it. `--disable-bootstrap` is what B01 used and
what five of this project's six configurations use, because the four hours is real.

{
    claim(
        "a native build bootstraps by default and a cross build does not, and neither of those "
        "is a flag you passed"
    )
}.
""")

lesson.code("""
wanted = cuts["wanted"]
print(wanted.about)
print(f"{wanted.span}  ({wanted.citation})")
print()
notes = {
    1554: "a compiler, host and target are this machine, and you said nothing",
    1557: "you said nothing and any of that was not true",
}
print(wanted.numbered(notes))
""")

lesson.md(f"""
`yes:$build:$build:default` is the case that turns it on: there is a compiler, the host and the
target are the build machine, and you did not say. Everything else defaults to off, which is why
a {term("cross compiler")} does not bootstrap and could not sensibly try, since stage two would
have to run on the target.

Note the warning above it as well. `--enable-bootstrap` on a cross build is allowed, with a
`trying to bootstrap a cross compiler` warning, because occasionally somebody has a reason.

## Where to read more

`BP-BOOTSTRAP` in this repository's `blueprints/` is the reference this lesson was built from.
It carries the full stage table, the module lists, the flag assignments per stage and seven
invariants stated precisely, each one read out of the pinned tree rather than typed.

`Makefile.tpl` and `Makefile.def` at the top of the GCC tree are where all of this lives.
`Makefile.in` is generated from them by `autogen` and is what you will actually be reading in a
build directory, which is worth knowing before you go looking for `[+ FOR bootstrap-stage +]` in
a file that has already had it expanded.

`contrib/compare-debug` is the script `bootstrap-debug` uses, and it is fifty readable lines that
show how you strip debug info from two object files in order to compare the rest.

## Boss fight

Eight questions about stages, comparisons and what they prove.

    python lessons/b02-the-bootstrap/grade.py

Two of them are about the fixed point argument and are the ones worth thinking about rather
than looking up.

## What to read next

You have a compiler and you know how much you should trust it. B03 puts a breakpoint in it: a
debugger attached to `cc1`, the six commands worth knowing, and how to stop on the pass you care
about in a program with four thousand functions in it.
""")

raise SystemExit(lesson.save())
