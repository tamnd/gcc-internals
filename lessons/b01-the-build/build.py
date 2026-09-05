"""B01. A compiler of your own, in five minutes or four hours.

The first lesson of Part II, and the one where the reader stops borrowing a compiler.

Everything before this ran on somebody else's GCC. Tier 0 runs on recorded dumps or on
Compiler Explorer, and Tier 1 runs on whatever the distribution shipped. Both were fine for
looking at output. Neither is any use for the rest of the course, because you cannot put a
breakpoint in a compiler you do not have and you cannot load a plugin into one built by
somebody who did not enable plugins.

The lesson is organised around a decision rather than around a procedure. There are three
ways to end up with a GCC 16.2 and they cost five minutes, ten minutes and twenty two
minutes to four hours, and the right answer depends entirely on what the reader is going to
do next. Once that is settled, the rest is reading one configure line left to right and
knowing what each flag decided.

Everything the notebook prints comes out of two committed files. `containers/matrix.toml`
is what this project's own images are built from, so a configure line printed here is a
configure line that CI has run this week. `corpora/configure/gcc.json` and
`corpora/source/b01.json` were recorded from the pinned tree by `record.py` next door, so
the counts are counts and the eleven excerpts are the real lines.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "b01-the-build",
    "b01",
    title="A compiler of your own, in five minutes or four hours",
    milestone="M2",
    summary=(
        "The three ways to have a GCC 16 and what each one costs, what the seven flags on a "
        "real configure line actually decided, which four of the fourteen front ends you get "
        "when you ask for none, and the empty file that decides whether your compiler is fast "
        "or careful"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# B01. A compiler of your own, in five minutes or four hours

{badge}

Every lesson so far borrowed a compiler. That stops here, and it stops here because of what
comes next: you cannot set a breakpoint in a compiler you do not have, you cannot load a
plugin into one that was built without plugin support, and you cannot see an internal
consistency check fire in a build that turned them all off.

The instinct at this point is to search for "how to build GCC", find a page with a configure
line on it, paste it, and wait. That works about half the time. When it does not, the error
is four hundred lines into a log and is about a library version, or a directory, or a front
end you did not know you had asked for, and there is nothing in the page you pasted from to
tell you which.

So this lesson is the other order. First, what you are actually choosing between, because
one of the three answers takes five minutes and most readers should take it. Then the
configure line, one flag at a time, with the part of GCC's own configure script that reads
each one. By the end the line is not a spell, it is seven decisions, and you can tell which
one to change.

You need a browser. The building happens on your machine afterwards, in your own time, and
nothing in this notebook starts a build or writes a gigabyte.

**What you come away with**

- The three routes to a GCC 16.2, what each costs in minutes and gigabytes, and which to pick
- The libraries configure will not start without, and the two version thresholds it has for each
- Why you configure from an empty directory, and what happens to a source tree you built in
- A real configure line read left to right, and how many options it did not use
- Which of the fourteen front ends a plain `./configure` builds, and what each one is called
- The empty file that decides whether your compiler checks itself
- What `make` compiles and runs before it compiles any of the compiler
- How to tell whether the thing that came out is the thing you asked for
""")

lesson.setup()

lesson.md(f"""
## Three ways, and you probably want the first

This project builds GCC six different ways, weekly, on two architectures, and publishes the
result. That is a slightly unusual thing for a course to have, and it means the numbers below
are measured rather than guessed: they are what the build actually took on a cold runner.

{
    claim(
        "the cheapest way to a GCC 16 is one docker pull and five minutes, and the most "
        "expensive is a bootstrap at four hours"
    )
}.
""")

lesson.code("""
from gxray import toolchain

print(toolchain.table())
print()
print(f"{toolchain.hours()} machine hours to build all of them once")
""")

lesson.md(f"""
Read the middle column and not the left one. The names are this project's, but the six rows
are the six reasons anybody builds GCC, and yours is one of them.

`rel` is a compiler. It is optimized, it was not bootstrapped, and it is what you want if the
answer to "what am I going to do with it" is "compile things and look at the dumps".

`chk` is the same source with every internal consistency check turned on, which makes it
about three times slower and is the build to have if you are going to change anything. A
{term("checking build")} turns a wrong answer forty passes later into a clean crash naming the
line that broke the invariant.

`dbg` is unoptimized with full debug info, because a debugger attached to a `-O2` compiler
shows you a function whose locals are gone and whose lines run backwards. B03 needs it.

`boot` is the full three stage {term("bootstrap")}. `cross` is a {term("cross compiler")},
which runs here and emits code for a machine you are not sitting at, and it is cheaper than
`rel` because it builds one front end and almost no runtime. `plug` is a distribution's own GCC
with this project's plugin built against it, which is why it costs five minutes and not twenty
two.
""")

lesson.md(f"""
The question that actually decides it is how long you are prepared to wait. Ask it that way.
""")

lesson.code("""
for minutes in (10, 30, 60, 300):
    fits = toolchain.route(minutes)
    names = ", ".join(f"{p.id} ({p.minutes}m)" for p in fits) or "nothing from source"
    print(f"{minutes:>4} minutes  {names}")

print()
best = toolchain.cheapest()
print(f"cheapest: {best.id}, {best.cost()}, {best.config.purpose}")
print()
print(best.pull())
""")

lesson.md(f"""
That last line is the whole of the first route. One command, five minutes, and a GCC 16.2 that
somebody else already built and that CI compiled hello world with before publishing.

Note the `@sha256:` in it. The image is pulled by digest and not by tag, because a tag is a
name somebody can move and a digest is not, and the entire reason to pull rather than build is
being sure which compiler you got.

The second route is the same images with an editor attached. `.devcontainer/devcontainer.json`
in this repository names one of them, and opening the repository in VS Code or in Codespaces
gets you the compiler, this project's tooling and a Jupyter kernel without installing anything
on your own machine. It is the right answer if your build failed and you would rather read the
lessons than debug a build.

The third route is the rest of this lesson.
""")

lesson.md(f"""
## What configure will not start without

Six things, and only three of them are libraries. The list below is not GCC's own, which is in
the installation manual and covers every host GCC has ever run on. This is the short list of
what stops somebody on a laptop.

{
    claim(
        "configure has two version thresholds for each of the three libraries it requires, and "
        "a separate phrase for landing between them"
    )
}.
""")

lesson.code("""
for what, why in toolchain.PREREQUISITES:
    print(f"{what:<20}{why}")

print()

from gxray import configure

build = configure.load()
print(build)
print()
print(f"{'library':<10}{'refuses below':<16}{'happy at':<12}the error says")
for one in build.requires:
    said = f"{one.said}+" + ("  (looser than the check)" if one.rounded else "")
    print(f"{one.library:<10}{one.hard:<16}{one.good:<12}{said}")
""")

lesson.md(f"""
GMP, MPFR and MPC are there because GCC folds constant arithmetic for the target rather than
for the host, so a compiler running on a 64 bit machine has to add two 128 bit numbers exactly
and cannot use the machine's own addition to do it. They are not optional and there is no
configure flag that turns them off.

The two thresholds are worth knowing because of what happens between them. Below the first,
configure refuses. Above the second, it says `yes`. In the gap it prints `buggy but
acceptable`, which is a real string in a real log and does not look like anything you need to
act on.

Here is the check, at {cite("configure.ac:1790@releases/gcc-16.2.0")}. One library, two nested
`AC_TRY_COMPILE` blocks, three possible answers.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("b01")
print(f"{len(cuts)} excerpts, {cuts.lines()} lines, cut from {cuts.tag}")
print()

gmp = cuts["gmp"]
print(gmp.about)
print(f"{gmp.span}  ({gmp.citation})")
print()
print(gmp.numbered({1795: "refuses below this", 1801: "buggy but acceptable below this"}))
""")

lesson.md(f"""
And the message you get when the first one fails, at
{cite("configure.ac:1880@releases/gcc-16.2.0")}, with a comment above it asking somebody to keep
the two in step.
""")

lesson.code("""
print(cuts["message"].numbered())
print()
for one in build.requires:
    if one.rounded:
        print(f"the message says {one.library} {one.said}+ and the code enforces {one.hard}")
""")

lesson.md("""
The comment is doing real work and is worth copying as a habit. A hard coded number in an error
message and the check it describes are two things that have to agree, nothing makes them, and
writing down that they have to is the cheapest thing available.

On a Debian or Ubuntu machine the three libraries are `libgmp-dev libmpfr-dev libmpc-dev`, on
Fedora they are `gmp-devel mpfr-devel libmpc-devel`, and on macOS with Homebrew they are `gmp
mpfr libmpc`. GCC can also build its own copies if you drop the tarballs into the source tree,
which the `contrib/download_prerequisites` script in the tree will do for you, and which is the
right move when your distribution's are too old.
""")

lesson.md(f"""
## Configure from an empty directory

This is the one instruction in the lesson that is not a preference.

Make a directory next to the source tree, stand in it, and run the configure script by its
path. That is an {term("out of tree build")}, and everything downstream is easier for it: the
source tree stays a source tree, `git status` stays readable, you can have a checking build and
a release build of the same source at the same time, and throwing a build away is one `rm -rf`
of a directory you created.

Building inside the source tree is allowed, and that is the trap. It works, and then it leaves
a `host-<triple>` directory and a few thousand object files scattered among the checked in
ones.

{
    claim(
        "the top level configure refuses an out of tree build from a source tree that somebody "
        "has already built in"
    )
}.
""")

lesson.code("""
intree = cuts["intree"]
print(intree.about)
print(f"{intree.span}  ({intree.citation})")
print()
print(intree.numbered({223: "srcdir is not . means out of tree, and this is the remnant"}))
""")

lesson.md(f"""
Read it carefully, because it is the opposite of what people remember. It does not refuse an
in-tree build. It refuses an out of tree build when the source tree it is pointed at has a
`host-<triple>` directory in it, which is what an earlier in-tree build left behind. So the
sequence that hurts is: build in the tree once, decide to do it properly, and discover that the
proper way is now the one that is blocked. The way out is `git clean -xdff` in the source tree,
or another clone.

The layout this lesson assumes from here on is the one the images use.

```text
gcc/          the checkout, at releases/gcc-16.2.0
build/        empty, and where you stand
```
""")

lesson.md(f"""
## One configure line, seven decisions

Here is a real one. This is not an example, it is what `containers/Dockerfile` runs to produce
the `rel` image, read out of the same file the workflow reads.

{
    claim(
        "the rel configuration passes seven flags, out of the hundred and sixty one the two "
        "configure scripts between them offer"
    )
}.
""")

lesson.code("""
plan = toolchain.plan("rel")
print(plan.configure())
print()
print(f"{'where':<16}{'--enable':>10}{'--with':>10}{'total':>8}")
for knob in build.knobs:
    print(f"{knob.where:<16}{knob.enable:>10}{knob.with_:>10}{knob.total:>8}")
print(f"{'':<16}{'':>10}{'':>10}{build.options:>8}")
""")

lesson.md(f"""
Two configure scripts, because there are two. The one you run is at the top of the tree and
configures the whole thing, and it runs a second one inside `gcc/` for the compiler itself,
along with one per library it is going to build. `./configure --help` at the top level shows
you the smaller half of the list, which is the usual reason somebody concludes that an option
they read about does not exist.

Now the seven, in the order they appear.

`--prefix=/opt/gcc` is where `make install` will put it. Use something other than `/usr/local`.
A GCC installed over the system one is a bad afternoon, and a GCC in a directory of its own is
deleted by removing the directory.

`--disable-multilib` says do not also build the 32 bit runtime libraries. On a 64 bit machine
that halves a good deal of the library build time and costs you the ability to compile with
`-m32`, which you were not going to do.

`--disable-nls` turns off translated diagnostics. It is a small speed up and it means the error
messages you are about to read match the ones in every mailing list post about them.

`--disable-libstdcxx-pch` skips precompiling the C++ standard library headers, which is minutes
of build time for a speed up to compiles of C++ that this project does not do.

`--with-system-zlib` uses the zlib your machine has rather than building the copy in the tree.
One less thing to compile.

`--enable-languages=c,c++` is the big one and has its own section below.

`--disable-bootstrap` is the other big one. It says build the compiler once with the compiler I
already have, rather than three times. It is the difference between twenty two minutes and four
hours, and B02 is about what you gave up.
""")

lesson.md(f"""
`CFLAGS` and `CXXFLAGS` go on the configure line and not on the make line. This is the mistake
that is easiest to make and hardest to see: `make CFLAGS=-O0` after configuring rebuilds part of
the tree with one setting and leaves the rest with another, and the result compiles and behaves
oddly.

There is one more thing to know about `CFLAGS`, and it is a real trap in the other direction. A
{term("bootstrap")} does not use it at all. Stage one is built with `STAGE1_CFLAGS` and the rest
with `BOOT_CFLAGS`, which defaults to `-g -O2` regardless of what you asked for. So the `-O2`
below is what `boot` passes and what none of its three stages reads.
""")

lesson.code("""
print(f"{'':<7}{'CFLAGS':<9}{'languages':<11}what makes it different")
for name in toolchain.names():
    one = toolchain.plan(name).config
    if not one.from_source:
        print(f"{name:<7}builds nothing, wraps a distribution compiler")
        continue
    print(f"{name:<7}{one.cflags:<9}{one.languages:<11}{' '.join(one.configure)}")

print()
shared = toolchain.plan("rel").config.common
print(f"all five share {len(shared)} flags: {' '.join(shared)}")
""")

lesson.md("""
That is the whole matrix as differences. Five configurations built from source, one shared
block of five flags, and between one and seven flags each that say what makes them different.
When you are reading somebody else's configure line, this is the useful thing to do to it:
subtract the boilerplate and look at what is left.
""")

lesson.md(f"""
## Which languages, and what they are called

`--enable-languages` is the flag with the largest effect on how long you wait, and the words it
takes are not the directory names and not the program names.

{
    claim(
        "four of GCC's fourteen front ends are built by a configure line that says nothing "
        "about languages"
    )
}.
""")

lesson.code("""
print(f"{'word':<10}{'program':<12}{'directory':<14}{'default':<10}{'target libraries'}")
for one in build.languages:
    state = "yes" if one.default else "opt in"
    row = f"{one.name:<10}{one.compiler or '-':<12}gcc/{one.directory:<10}{state:<10}"
    print(row + ", ".join(one.libs))

print()
defaults = ", ".join(build.default_languages)
print(f"{len(build.languages)} front ends, {len(build.default_languages)} by default: {defaults}")
""")

lesson.md(f"""
Three spellings for one thing, and they do not match. The word is `c++`, the directory is
`gcc/cp`, and the program is `cc1plus`. T01 introduced {term("cc1")} as the thing the
{term("driver")} runs for a C file; that column is the rest of the set, and `crab1` for Rust and
`d21` for D are real names and not typos.

The default is not "all of them" and not "C". It is every front end whose own declaration does
not opt out, which today is four. Nothing keeps a list: the top level configure sources all
fourteen declarations and asks each one.
""")

lesson.code("""
print(cuts["languages"].numbered({2313: "the default when a declaration says nothing"}))
print()
print(cuts["declaration"].about)
print(cuts["declaration"].numbered({30: "so rust is opt in"}))
""")

lesson.md(f"""
Five lines of shell per front end, at {cite("gcc/rust/config-lang.in:27@releases/gcc-16.2.0")}.
The `target_libs` line is where the time goes. Enabling a language does not only build a front
end, it builds that language's runtime for the target, and `libstdc++-v3` alone is a larger
compile than the C front end.

One word is not a choice, at {cite("configure.ac:2407@releases/gcc-16.2.0")}.
""")

lesson.code("""
print(cuts["always"].about)
print(cuts["always"].numbered())
print()
print("so --enable-languages=c++ still builds C, and there is no way to ask for a GCC without it")
""")

lesson.md("""
`c,c++` is the right answer for this course and for almost everybody. Fortran and Objective-C
are on by default and are pure cost if you are not going to use them, which is why every
configuration in this project names its languages rather than accepting the default.

The other three words the flag takes are `all`, which means every front end that opts in by
default plus the ones it can, `default`, which is the same as saying nothing, and a comma
separated list, which is what you want. If you get a language name wrong, configure tells you
so immediately, which is the one part of this that fails fast.
""")

lesson.md(f"""
## The empty file that decides how careful your compiler is

`--enable-checking` is the second flag worth understanding, and its default is not a constant.

{
    claim(
        "an empty file called DEV-PHASE is what makes the default checking level release "
        "rather than yes and extra"
    )
}.
""")

lesson.code("""
check = build.checking
print(f"levels:  {', '.join(check.levels)}")
print(f"flags:   {', '.join(check.flags)}")
print()
print(f"this tree is a release: {check.release}")
print(f"so the default is       {check.default}")
print(f"on a development branch {check.development}")
""")

lesson.code("""
print(cuts["release"].about)
print(cuts["release"].numbered({642: "an empty DEV-PHASE is not the word experimental"}))
""")

lesson.md(f"""
That is the whole mechanism, at {cite("gcc/configure.ac:640@releases/gcc-16.2.0")}. `gcc/DEV-PHASE`
contains the word `experimental` on a development branch and is empty on a release tag. Nothing
else about the source differs. So the same configure line, run against a git checkout of master
and against a release tarball, gives you two compilers with different amounts of self checking
and a large difference in speed, and neither one told you.

The flag itself, and the part people misread.
""")

lesson.code("""
notes = {
    653: "and none of the next six lines runs at all if you passed the flag yourself",
    655: "is_release empty means a development branch, so yes,extra",
    658: "and this is what a release tag gets",
    661: "release is prepended to whatever you passed",
}
print(cuts["default"].numbered(notes))
""")

lesson.md(f"""
Two things in there. The default block is the second argument to `AC_ARG_ENABLE`, which is the
code that runs when you did not pass the flag, and inside it the empty `is_release` is the
development branch and the `else` is the release tag. And the loop reads
`for check in release $ac_checking_flags`, so the word `release` is applied first whatever you
asked for, and `--enable-checking=tree` means `release,tree` and not `tree` alone.

The levels are cumulative in the obvious way and the individual flags are for when you know what
you are chasing. `--enable-checking=all,rtl,extra` is what this project's `chk` image uses,
because a course about internals wants the compiler to complain as early as it can. It is about
three times slower to build and noticeably slower to run, and that is the trade.
""")

lesson.md(f"""
## What make does before it makes the compiler

Now the easy part. Two commands, and the second one takes the time.

```text
make -j"$(nproc)"
make install-strip
```

`-j` matters more here than almost anywhere. GCC's build parallelises well and the difference
between one job and eight is close to the difference between an evening and a coffee. `install-strip`
rather than `install` because the debug info in an installed release compiler is several
gigabytes you will not read.

What happens first is the part worth knowing.

{
    claim(
        "a dozen of the files the compiler is compiled from are written during the build by "
        "programs the build compiles and runs first"
    )
}.
""")

lesson.code("""
from gxray import layout

tree = layout.load()
print(f"{'program':<24}{'writes':<44}from")
for gen in tree.generators:
    print(f"{gen.program:<24}{gen.writes:<44}{gen.reads}")
print()
print(f"{len(tree.generators)} of them here, and the build runs 29, which BP-BUILD lists in full")
""")

lesson.md(f"""
Z02 met these as the reason a backtrace can name a file that is not in the tree. Here they are
the reason the build has a shape. Each one is a small C++ program that is compiled for the
machine doing the building, then run, and what it writes is source that then gets compiled into
the compiler. `insn-recog.cc` for a large target runs to hundreds of thousands of lines and
nobody typed any of it.

The bookkeeping for that is a {term("stamp file")}, at
{cite("gcc/Makefile.in:2803@releases/gcc-16.2.0")}.
""")

lesson.code("""
stamp = cuts["stamp"]
print(stamp.about)
print(f"{stamp.span}  ({stamp.citation})")
print()
notes = {
    2806: "leaves the timestamp alone if the content did not change",
    2807: "so this empty file is what records that the generator ran",
}
print(stamp.numbered(notes))
""")

lesson.md("""
Read the last two lines together. `move-if-change` deliberately does not touch a file whose
content is unchanged, which stops one edit to a machine description from rebuilding every object
that includes the generated header. But then make cannot use that file's timestamp to know the
generator ran, so an empty `s-something` is created to carry it.

This is why a build directory has hundreds of empty files in it, and it is worth knowing for one
practical reason: if you have edited something and the build is ignoring you, deleting the
relevant stamp forces the generator to run again.
""")

lesson.md(f"""
## Is the thing that came out the thing you asked for

Two checks, and neither takes a minute.

The first is that it compiles and runs something. That is the command each of this project's
images runs on itself before it is allowed to be published, which is why a broken build is
caught in the job that produced it rather than three jobs later.
""")

lesson.code("""
for one in toolchain.plans():
    print(f"{one.id:<7}{one.smoke()}")
""")

lesson.md(f"""
The second is that it tells you how it was built. This is the check people skip and then need.

{
    claim(
        "a built GCC carries the configure line it was built with and prints it back when you "
        "run it with -v"
    )
}.
""")

lesson.code("""
version = cuts["version"]
print(version.about)
print(f"{version.span}  ({version.citation})")
print()
print(version.numbered({7736: "this is the line in gcc -v output"}))
print()
print("so on the compiler the rel image ships, that line reads back as:")
print()
print("  Configured with: " + " ".join(toolchain.plan("rel").config.flags))
""")

lesson.md(f"""
`gcc -v` on any GCC prints `Configured with:` followed by the exact arguments its configure was
given. That is how you find out what your distribution did, why their GCC has a flag yours does
not, and whether the compiler you are looking at is the one you built ten minutes ago or the one
in `/usr/bin` that came first in your `PATH`.

It is not only informational. A plugin records the configure line of the compiler it was built
against, and refuses to load into one that does not match, at
{cite("gcc/plugin.cc:1012@releases/gcc-16.2.0")}.
""")

lesson.code("""
print(cuts["plugin"].about)
print(cuts["plugin"].numbered({1021: "and the configure line, compared as a string"}))
""")

lesson.md("""
Five string comparisons, and the last one is the configure line. Two GCCs built from the same
source with different flags will not load each other's plugins, which is strict and is the
reason B05 works at all. It is also the answer to "why does my plugin say version mismatch when
the versions match".

The other three commands worth running once on a new compiler are `gcc -print-search-dirs`,
which says where it will look for `cc1` and the libraries, `gcc -print-prog-name=cc1`, which says
which one it actually found, and `gcc -dumpmachine`, which prints the
{term("target triple")} it was configured for. T01 covered what those mean. On a fresh build they
are how you find out that you are still running the old compiler because `PATH` did not change.
""")

lesson.md(f"""
## When it fails anyway

It will, at some point, and the useful thing is knowing that stopping is allowed.

A GCC build is long enough that a failure at minute forty is genuinely expensive, and the
failures are rarely about GCC. They are about a header your distribution moved, a library
version in the gap, a `make` that is not GNU make, or a disk that ran out. None of that teaches
you anything about compilers.

So the escape hatches are first class here and not an apology.

{
    claim(
        "ten of this project's twelve published images can be pulled by digest, which is a name "
        "nobody can move"
    )
}.
""")

lesson.code("""
locked = toolchain.digests()
print(f"{len(locked)} images published with a recorded digest")
print()
for one in toolchain.plans():
    marker = "digest" if one.digest else "tag only"
    print(f"{one.id:<7}{marker:<10}{one.pull()}")
""")

lesson.md(f"""
Every one of those was built by the same workflow from the same `matrix.toml` the tables above
came from, and every one compiled and ran a program before it was published.

The two without a digest are the bootstrap, which runs weekly and had not run when this was
recorded. That is the honest state of it rather than a placeholder.

The second hatch is the devcontainer. `.devcontainer/devcontainer.json` names the `rel` image by
digest and adds Python and this repository's tooling on top, so opening the repository in VS
Code or in GitHub Codespaces gets you a working compiler and a working kernel without touching
your own machine. If your build failed and you want to get on with the course, take it, and come
back to the build when the failure is interesting rather than in the way.

The third hatch is that most of Part I still works with no compiler at all. The recorded dumps in
`corpora/` are real output from a real GCC 16.2 and are committed.
""")

lesson.md(f"""
## The commands, in order

For a reader who wants the whole thing in one place, this is the `rel` route, generated from the
same file everything else in this lesson read.
""")

lesson.code("""
print(toolchain.plan("rel").shell())
print()
print("# then check it")
print("/opt/gcc/bin/gcc -v")
print("/opt/gcc/bin/gcc -dumpmachine")
""")

lesson.md("""
Expect twenty two minutes on a machine with eight cores and rather longer on two. It writes about
1.2 GB. Nothing in it needs root until `make install`, and if you set `--prefix` to somewhere in
your home directory it does not need root at all.

If you want the checking build instead, which is the one to have if you are going to change
anything, the only difference is one flag and one setting.

```text
--enable-checking=all,rtl,extra    instead of nothing
CFLAGS="-O0 -g"                    instead of -O2
```

That is 47 minutes instead of 22 and 4 GB instead of 1.2, and it is the build the rest of Part II
assumes when it matters.
""")

lesson.md("""
## Where to read more

`gcc/doc/install.texi` in the tree is the installation manual and is the authority for every flag
in this lesson plus two hundred more. It is generated into the page everybody links to, and
reading it in the tree means reading the version that matches your source.

`contrib/download_prerequisites` fetches and unpacks GMP, MPFR, MPC and ISL into the source tree
so configure builds them itself. It is the fastest way out of a library version problem.

`BP-BUILD` and `BP-BOOTSTRAP` in this repository's `blueprints/` are the reference behind this
lesson. They carry the generated tables of every front end declaration, every checking category,
every generator program, and every stage of a bootstrap, each one read out of the pinned tree.

## Boss fight

Eight questions about a configure line and a build, none of which you can answer by pattern
matching on a web page.

    python lessons/b01-the-build/grade.py

Some of them are about this project's matrix, which you have in front of you. Some are about
GCC's own configure script, which you have in the excerpts above. One of them is about your own
machine and the grader will tell you if you are wrong about it.

## What to read next

You have a compiler. B02 is the one you skipped: what `--disable-bootstrap` turned off, why
building GCC three times is a correctness argument and not a ritual, and what the comparison at
the end of it catches.
""")

raise SystemExit(lesson.save())
