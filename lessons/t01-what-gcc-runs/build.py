"""T01. What does gcc actually run?

The first lesson of Part I, and the first thing anybody should be told about GCC, which is
that the program called `gcc` is not the compiler.

It runs on recorded `-###` output, because the answer is different on every machine and a
lesson that showed the reader their own answer would have nothing to compare against. Two
recordings are used on purpose: one from the pinned compiler on aarch64 macOS and one from
Compiler Explorer's x86-64 Linux build of the same GCC version. The difference between them
is half the lesson.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t01-what-gcc-runs",
    "t01",
    title="What does gcc actually run?",
    milestone="M1",
    summary=(
        "That `gcc` compiles nothing and runs the programs that do, how to make it show you "
        "the list without running any of it, why `cc1` is not on your PATH, and where the "
        "flags you typed actually end up"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T01. What does `gcc` actually run?

{badge}

You typed `gcc hello.c`. Something happened and a file appeared. This lesson is about the
something.

The short answer is that `gcc` did not compile anything. It read your command line, worked
out what you meant, built command lines for two or three other programs, and ran them. Those
other programs did the work. One of them is the compiler and it is not called `gcc`, it is
not on your PATH, and plenty of people who have used GCC for a decade have never typed its
name.

None of this is hidden. There is a flag that makes the driver print exactly what it would
run and then not run it, and that flag is the whole lesson.

You need a browser. There is no compiler here and no network. Everything below runs on
output recorded from real compilers and committed, so you see what the lesson saw.

**What you come away with**

- Knowing that `gcc` is a {term("driver")} and what a driver is for
- Being able to read `-###` output, which is the first thing to reach for when a build does
  something you did not ask for
- Knowing where {term("cc1")} lives and why it is not on your PATH
- Being able to tell which of your flags went to the compiler, which went to the assembler,
  and which went nowhere
- Knowing why the same command runs a different number of programs on two machines
""")

lesson.setup()

lesson.md("""
## The flag

`-v` makes GCC print each command line before running it. `-###` prints the same thing and
runs nothing at all.

`-###` is the one to learn. It is safe on any command, including one that would overwrite
something you care about, and it quotes its arguments, so what it prints can be pasted or
parsed rather than squinted at. Everything below is `-###` output that was recorded and
committed.
""")

lesson.code("""
backend = gxray.corpus("t01-driver")
print(gxray.banner(backend))
""")

lesson.md("""
The banner is there every time and it is not decoration. A chain of programs is a fact about
one installation of GCC on one machine, and a reader who cannot see which installation is
being shown cannot tell a difference that matters from a difference that does not.

Now the output itself. This is `gcc -### -O2 -c l1.c`, verbatim, with nothing removed.
""")

lesson.code("""
print(backend.chain(gxray.L1, "-O2", "-c").text)
""")

lesson.md("""
It is not pretty and it is not meant to be. Everything the driver says about itself starts
at column zero, and every command it would run starts with exactly one space. That single
space is the entire grammar, and it is all a parser needs.

Read the two indented lines and you have the answer to the question in the title.
""")

lesson.code("""
chain = backend.chain(gxray.L1, "-O2", "-c")

print(chain)
for n, step in enumerate(chain, 1):
    print(f"{n}. {step.name:<10} {step.role}")
""")

shrinks = claim(
    "on this target gcc runs one program for -E and for -S, two for -c, and three for a full link"
)

lesson.md(f"""
Two programs. `cc1` turned your C into assembly text, and `as` turned that text into an
object file. Neither of them is `gcc`.

## The chain changes with the flags

Everybody knows `-c` means "do not link" and `-S` means "stop after the compiler". What is
less obvious is that neither of those is an option to the compiler. They are instructions to
the driver about how far down its list of programs to go, and you can watch the list get
shorter. {shrinks}.
""")

lesson.code("""
for flags in ("-O2 -E", "-O2 -S", "-O2 -c", "-O2"):
    steps = backend.chain(gxray.L1, *flags.split()).names
    print(f"gcc {flags:8} runs  {', '.join(steps)}")
""")

lesson.md(f"""
`-E` and `-S` both run one program and it is the same program, `cc1`, told to stop at a
different point. There has been an integrated preprocessor since the 1990s, so `-E` does not
run a separate `cpp` unless you ask for one with `-no-integrated-cpp`.

The third program in the last line is {term("collect2")}, and it is not the linker. It is a
wrapper that runs the linker. On most modern targets it has almost nothing left to do and
passes everything through, which is exactly why it looks so odd the first time you see it.

The same four lines as a picture, with what each program eats and produces and where each
flag cuts the chain, are in
[`diagrams/what-gcc-runs.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t01-what-gcc-runs/diagrams/what-gcc-runs.excalidraw).
Open it at excalidraw.com and you can move things around. It is the only picture in this
lesson that is not read off a recorded run, because it shows the shape of the chain in
general rather than the chain one compiler happened to run.

## Where cc1 lives

The middle line of that dump was a very long absolute path ending in `cc1`, and that path
answers a question people ask a lot, which is why they cannot find the compiler.
{claim("the driver runs cc1 from an absolute path under libexec, and cc1 is not on the PATH")}.
""")

lesson.code(
    """
import shutil

cc1 = chain.named("cc1")
print("the driver runs:")
print("   ", cc1.program)
print()
print("on your PATH:")
print("   ", shutil.which("cc1") or "not there")
""",
    varies="The path is from the recorded run. Yours is under wherever your GCC was installed.",
)

lesson.md("""
That is deliberate. On a Unix system `libexec` is where you put programs that are meant to
be run by other programs rather than by people. `cc1` takes one translation unit and a pile
of options in a form nobody would want to type, and produces assembly text. It has no
interest in linking, no idea about your other source files, and no useful behaviour if you
run it by hand.

There is one of these per language, built from the same middle end and the same back end
with a different front end on the front: `cc1plus` for C++, `f951` for Fortran, `d21` for D.
That is the most important structural fact about GCC and it is visible right here, in the
name of a program in a directory.

## What the driver tells it
""")

lesson.md(f"""
Now the part that surprises people. You passed one flag.
{claim("the driver hands cc1 many more arguments than the user typed on the command line")}.
""")

lesson.code("""
print("you typed:   gcc -O2 -c l1.c")
print()
print(f"the driver gave cc1 {len(cc1.argv)} arguments:")
for arg in cc1.argv:
    print("   ", arg)
""")

lesson.md(f"""
Exactly one of them is a flag from your command line. The rest are the driver filling in
everything `cc1` needs and has no way to know: where the headers are, which processor to
assume, which ABI, what to call the dump files, where to put the output.

This is why an option you passed can turn up in a different form, or as three options, or
not at all. The translation is done by {term("spec", "spec strings")}, which are templates
full of conditionals, and the one for a C file is in the driver's source at
{cite("gcc/gcc.cc:1493@releases/gcc-16.2.0")}:

```text
%{{!save-temps*:%{{!traditional-cpp:%{{!no-integrated-cpp:
    cc1 %(cpp_unique_options) %(cc1_options)}}}}}}
%{{!fsyntax-only:%(invoke_as)}}
```

The word `cc1` in the middle of that is the whole mechanism. `%{{x:...}}` means "if the
option `x` was given", so the second line reads "unless `-fsyntax-only` was given, also run
the assembler", and that is literally how the driver decides. The table that picks which
spec applies to which file is a few hundred lines above, keyed on the file extension, at
{cite("gcc/gcc.cc:1453@releases/gcc-16.2.0")}, and the assembler line is
{cite("gcc/gcc.cc:1494@releases/gcc-16.2.0")}.

You will never need to write one of these. Recognising the syntax is enough to stop
`gcc -dumpspecs` from looking like line noise.

## Where the optimizer flag goes

Here is a small experiment that makes the division of labour concrete. Compile the same file
at `-O0` and at `-O2`, and compare, argument by argument, what each program was told.
{claim("changing -O0 to -O2 changes one flag given to cc1 and nothing at all given to as")}.
""")

lesson.code("""
at_zero = backend.chain(gxray.L1, "-O0", "-c")
at_two = backend.chain(gxray.L1, "-O2", "-c")

for name in ("cc1", "as"):
    one = set(at_zero.named(name).argv)
    other = set(at_two.named(name).argv)
    # The temporary assembly file has a random name, so it differs on every run and is not
    # a difference about optimization. Anything starting with a dash is a real flag.
    changed = sorted(a for a in one ^ other if a.startswith("-"))
    print(f"{name:>4}: {', '.join(changed) or 'nothing changed'}")
""")

lesson.md("""
That is the shape of the whole toolchain in two lines of output. Optimization happens
entirely inside `cc1`. The assembler is a translator from text to bytes and does not know or
care what produced the text, which is why you cannot make a program faster by passing `-O2`
to `as`, and why `-O2` in the wrong half of a build system is silently useless rather than
an error.

## Two GCCs, same version, different chain
""")

lesson.md(f"""
Everything above is one installation. Here is the same source and the same flags on a
different one: Compiler Explorer's build of GCC 16.2, recorded the same way.
{claim("the same source and flags run three programs on one GCC 16.2 build and one on another")}.
""")

lesson.code("""
elsewhere = gxray.corpus("t01-driver-ce")
print(gxray.banner(elsewhere))
print()

here = backend.chain(gxray.L1, "-O2")
there = elsewhere.chain(gxray.L1, "-O2")

print(f"pinned local build   {here}")
print(f"Compiler Explorer    {there}")
""")

lesson.md("""
Two different things are going on here and it is worth separating them.

The first is the target. One of these is aarch64 macOS and the other is x86-64 Linux, and
the assembler and the linker are different programs with different names and different
arguments. The chain is a property of how a compiler was configured and what it targets, not
of its version number, so two compilers that both say 16.2.0 can differ here and neither of
them is wrong.

The second is that Compiler Explorer is not running the command line you typed. It adds
flags of its own to everything, and the driver's own view of the options shows them.
""")

lesson.code("""
print("options Compiler Explorer's driver saw, for a command line that said -O2:")
for arg in there.named("cc1").options:
    print("   ", arg)
""")

lesson.md("""
`-S` is in there, which is why that chain stops at `cc1`: the site only ever wants assembly,
so it never runs an assembler and never runs a linker. `-masm=intel` is in there too, which
is why assembly on the site looks different from assembly out of your terminal even when
every flag you can see is the same.

This is not a complaint about a very good tool. It is the reason this course records
everything it shows and prints a banner over it. A dump is a fact about a version, a target
and a set of flags, and the flags are not always the ones you typed.

## Boss fight

Four invocations, all on the recorded pinned compiler:

```text
gcc -O2 -E l1.c
gcc -O2 -S l1.c
gcc -O2 -c l1.c
gcc -O2    l1.c
```

Work out, before running anything:

1. How many programs each one runs
2. Which program runs in all four
3. Whether any optimization flag reaches the assembler

Then check yourself:

```text
python lessons/t01-what-gcc-runs/grade.py
```

or, from a checkout, `just grade t01-what-gcc-runs`. It takes the answers on the command
line as well, so `--steps 1,1,2,3 --shared cc1 --to-as no` is a complete submission. Every
answer it marks against is worked out from the recorded output rather than written down, so
re-recording against a newer compiler cannot leave it marking against a stale key.

## What to read next

T02 takes the one program in that chain that matters, `cc1`, and shows the same function in
all five of the forms it passes through inside it.

T04 is the pass list, which is what `cc1` spends its time doing.

B01 builds GCC from source, which is where the difference between the two chains above stops
being trivia and starts being something you choose.

If you have a GCC on your machine and want the live version of this lesson, swap
`gxray.corpus("t01-driver")` in the cells above for `gxray.local("gcc-16")` and every cell
runs against your own compiler. The numbers will differ. That is the lesson.
""")

raise SystemExit(lesson.save())
