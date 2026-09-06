"""B05. Sixty lines of C++, and you are inside the compiler.

The last lesson of M2, and the one that turns a reader from somebody who watches GCC into
somebody who runs code inside it. Five plugins, all of them in `gxplug/examples/`, all of
them built and loaded on four different compilers by the `plugin` workflow on every push:

  hello      the contract, in the smallest form that still works
  countpass  a GIMPLE pass of the reader's own, inserted after `ssa`
  gate       the same mechanism used to switch one of GCC's own passes off
  nolicence  refused for a missing symbol
  wrongver   refused by its own version check

None of them can be built in a notebook, which is the constraint that shapes the lesson. A
plugin needs GCC's private headers and the same compiler that will load it, and a Colab
reader has neither. So the sources are in the repository where they can be read line by
line, and `record.py` next door holds eleven real compilations by a real GCC 16.2 with every
byte of output kept.

The idea the lesson is built around is in its last section but decided in its first: the
plugin API is not an API. There is no stable interface, no header that is meant for you, and
a version check that compares the configure line because two builds of the same release have
incompatible layouts. Everything that is hard about writing a plugin follows from that, and
so does the one thing that makes plugins worth having, which is that you are inside, holding
the real IR, with nothing translated.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "b05-the-plugin",
    "b05",
    title="Sixty lines of C++, and you are inside the compiler",
    milestone="M2",
    summary=(
        "GCC's plugin mechanism from the outside in: the three things a plugin has to have, "
        "the three ways it is refused, what an event actually is, a GIMPLE pass of your own "
        "inserted after ssa with its own dump file, switching one of GCC's passes off from "
        "outside and watching the assembly move, and why the thing you are writing against "
        "is not an API"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# B05. Sixty lines of C++, and you are inside the compiler

{badge}

Four lessons of this milestone have been about getting a compiler and finding out what it
did. This one is about putting your own code inside it while it runs.

A {term("plugin")} is a shared object that `cc1` loads at startup. Once it is in, it is in:
it holds the real trees, calls the real functions, sees the real IR between two real passes,
and segfaults the real compiler. There is no sandbox and no translation layer. That is both
the reason plugins are the right tool for a question the dump files cannot answer, and the
reason writing one feels like nothing else in this course.

**You cannot build one here.** A plugin is C++ compiled against GCC's private headers, and it
has to be built by the compiler that will load it. Colab has neither the headers nor a
matching GCC. So this lesson works the way B03 did: the five plugins are in this repository
under `gxplug/examples/`, where every line of them can be read, and everything they printed
was recorded by a real GCC 16.2 and committed.

If you have a compiler from B01 or a container, everything below is four commands away, and
the section before the boss fight says which four.

**What you come away with**

- The three things a plugin must have, and what happens when each one is missing
- Why the version check compares the configure line and not just the version
- What an event actually is, and the three names in the event list that are not events
- A pass of your own, running after `ssa`, in `-fdump-passes`, with its own dump file
- The difference between a pass name and a dump name, which costs everybody an hour once
- Switching one of GCC's passes off from outside, and the assembly moving because of it
- The pass that changes nothing when you switch it off, which is the more useful result
- What `gxplug` is doing, and the honest ratio between passes that run and passes that show
- Why the plugin API is not an API, and what that means for anything you write
""")

lesson.setup()

lesson.md(f"""
## What was recorded, and by what

Everything printed below came out of one recording run on a machine with a real GCC. The
compiler is the same release as the tree every citation in this book points at, so a line
number here and a line number in `vendor/gcc` are the same line.
""")

lesson.code("""
from gxray import plug

session = plug.load_session()

print(session.compiler)
print(session.target)
print(f"recorded {session.recorded}, {len(session.invocations)} compilations")
print()
print(session.probe)
""")

lesson.md(f"""
That probe output is the `Makefile` saying what it found. Three lines of it are the whole
reason `gxplug/Makefile` is ninety lines and not five: where this compiler keeps its plugin
headers, whether `gmp.h` is on the include path, and what the linker needs on this platform.
None of the three is the same on Debian, Fedora, Homebrew and a compiler you built yourself.

## The three things a plugin must have

Here is the smallest one, with its opening comment stripped. Forty lines, and three of them
are not optional.
""")

lesson.code("""
print(plug.body("hello"))
""")

lesson.md(f"""
Those three:

`int plugin_is_GPL_compatible;` is a symbol GCC looks up by name. It is never read. Its
presence is the whole check.

`plugin_init` is the entry point, found by name the same way. It gets the plugin's own
arguments and the compiler's version, and returning non-zero from it stops the compilation.

The version check is the third, and it is the plugin's job rather than GCC's. GCC hands you
its version and expects you to compare it against yours. A plugin that skips the check is a
plugin that loads into anything and does undefined things there.

Everything else is one call to `register_callback` per event you care about. Here is what
that plugin printed, compiling `l2.c`.
""")

lesson.code("""
hello = session["hello"]
print(hello.command)
print()
for line in hello.said:
    print("   ", line)
""")

lesson.md(f"""
Two functions, then the total, and the arguments come through the same way.
""")

lesson.code("""
print(session["hello-arg"].command)
print()
for line in session["hello-arg"].said:
    print("   ", line)
""")

lesson.md(f"""
`-fplugin-arg-hello-who=reader` is parsed by the driver into a key and a value and handed to
`plugin_init` in `info->argv`. The plugin's name in the middle of that flag is the base name
of the shared object, which is how the compiler knows which of several loaded plugins the
argument is for, and which is why renaming your `.so` breaks every command line you wrote.

And the promise all of this rests on:

{
    claim(
        "a plugin that only observes leaves the generated code byte for byte identical, "
        "which is checkable rather than assertable and is checked here for two of the five"
    )
}.
""")

lesson.code("""
plain = session["plain"]
for name in ("hello", "countpass"):
    same = session[name].asm == plain.asm
    print(f"{name:<12} {'identical' if same else 'DIFFERENT'} to the no-plugin assembly")
print()
print(f"{len(plain.asm.splitlines())} lines of assembly, unchanged")
""")

lesson.md(f"""
## The three ways a plugin is refused

All three happen before the plugin runs a line of its own code, or in one case immediately
after, and all three stop the compilation. None of them is a warning.

The first is the licence symbol, at {cite("gcc/plugin.cc:713@releases/gcc-16.2.0")}.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("b05")
print(f"{len(cuts)} excerpts, {cuts.lines()} lines, cut from {cuts.tag}")
print()
shown = cuts["licence"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
print(shown.numbered({714: "looked up by name, never called, never read"}))
""")

lesson.md(f"""
`fatal_error` and not `error`, so the compilation stops there and then. `nolicence.cc` is
`hello.cc` with that one line deleted, and this is what it gets.
""")

lesson.code("""
one = session["nolicence"]
print(f"returncode {one.returncode}")
print()
for line in one.said:
    print("   ", line[:110])
""")

lesson.md(f"""
The plugin's own first line of output is not there, because it never ran.

The second refusal is the version, and it is the one that will happen to you. The check is at
{cite("gcc/plugin.cc:1004@releases/gcc-16.2.0")}, and the interesting part is how much it
compares.
""")

lesson.code("""
shown = cuts["version"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
notes = {
    1013: "the version, which is the field everybody expects",
    1015: "and the datestamp",
    1021: "and the entire configure command line",
}
print(shown.numbered(notes))
""")

lesson.md(f"""
{
    claim(
        "the default version check compares five fields including the full configure "
        "argument string, so two builds of the same GCC release configured differently have "
        "incompatible plugin ABIs and refuse each other's plugins"
    )
}.

That last field is the one that matters. `--enable-checking` changes struct layouts.
`--enable-languages` changes which trees exist. A plugin built against Debian's GCC 16.2 and
loaded into Fedora's GCC 16.2 is loading into a different compiler, and the string comparison
is the only thing standing between that and a crash with no explanation.

`wrongver.cc` claims to have been built by GCC 15.1.0 so the failure can be shown without
needing two compilers installed.
""")

lesson.code("""
one = session["wrongver"]
print(f"returncode {one.returncode}")
print()
for line in one.said:
    print("   ", line)
""")

lesson.md(f"""
Three lines, from three different places. The first is the plugin's own `error` call, the
second is its `inform`, and the third is GCC at
{cite("gcc/plugin.cc:731@releases/gcc-16.2.0")} reacting to a non-zero return.
""")

lesson.code("""
shown = cuts["initcall"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
notes = {
    732: "your plugin_init, and its return value is the whole protocol",
    738: "the handle is leaked on purpose, because unloading mid-compilation is worse",
}
print(shown.numbered(notes))
""")

lesson.md(f"""
The third refusal is the simplest and the most common: the file is not there. That is a
`dlopen` failure and not a driver error, which is why the message is a wall of paths, and
which is why `-fplugin=gxplug.so` without the `./` fails on Linux and works on macOS.
""")

lesson.code("""
print(session["missing"].said[0][:150], "...")
print()
print(cuts["dlopen"].numbered({703: "RTLD_NOW, so a symbol it needs and cannot get fails here"}))
""")

lesson.md(f"""
`RTLD_NOW` is deliberate and the comment says why. Binding every symbol at load time means an
ABI mismatch that got past the version check shows up as a failed `dlopen` rather than as a
crash four hundred passes later.

There is a fourth way to be refused that is nobody's fault but yours, and it is worth a line
because the alternative is worse.
""")

lesson.code("""
print(session["badarg"].command)
print()
for line in session["badarg"].said:
    print("   ", line)
""")

lesson.md(f"""
A mistyped `-fplugin-arg-` name is not a diagnostic GCC can produce, because GCC has no idea
what arguments your plugin takes. It hands over whatever it was given. So a plugin that
ignores what it does not recognize is a plugin where `-fplugin-arg-gxplug-outt=/tmp/x` does
nothing for an hour, and `gxplug` refuses instead.

## What an event actually is

The list of {term("plugin event", "events")} is a file of one-line macro calls at
{cite("gcc/plugin.def:20@releases/gcc-16.2.0")}.
""")

lesson.code("""
shown = cuts["defevent"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
print(shown.numbered({27: "not an event, despite being in the list of events"}))
""")

lesson.md(f"""
Twenty six of these. The order of the file is the ABI, because the enumerator's value is the
index into the callback table, which is why a new event is always added at the end.

Firing one is less than people imagine. It is a linked list walked in registration order, at
{cite("gcc/plugin.cc:582@releases/gcc-16.2.0")}.
""")

lesson.code("""
shown = cuts["dispatch"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
print(shown.numbered({590: "no return value is read, so a callback cannot refuse anything"}))
""")

lesson.md(f"""
Two plugins registered for the same event both run, in the order they were loaded, and
neither can see or stop the other. There is no priority and no veto.

And then the part of the mechanism that is genuinely misleading. Three of the twenty six
names in that list are never fired at all. They are {term("pseudo-event", "pseudo-events")},
acted on the moment you register for them, at
{cite("gcc/plugin.cc:450@releases/gcc-16.2.0")}.

{
    claim(
        "registering a pass is spelled exactly like registering a callback, and is not one: "
        "PLUGIN_PASS_MANAGER_SETUP is handled inside register_callback and never fired, so "
        "the fourth argument is read immediately rather than handed back to you later"
    )
}.
""")

lesson.code("""
shown = cuts["pseudo"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
notes = {
    459: "the callback must be null, because there is nothing to call it from",
    460: "the user data is a register_pass_info, and it is used right here",
}
print(shown.numbered(notes))
""")

lesson.md(f"""
This is the thing to know before writing your first pass, because the code you will copy from
a blog post looks like an event registration and behaves like a function call, and passing a
callback alongside the pass info trips a `gcc_assert` rather than producing a diagnostic.

## A pass of your own

Here is the whole of it. A GIMPLE pass that counts what it sees and changes nothing.
""")

lesson.code("""
print(plug.body("countpass"))
""")

lesson.md(f"""
Three parts.

`pass_data` is what the pass says about itself. The two fields worth stopping on are
`properties_required`, which is `PROP_ssa` here and means the pass manager will refuse to run
this pass anywhere the function is not in SSA form, and `todo_flags_finish`, which is zero and
is a promise. See below.

The class is a `gimple_opt_pass` with a `gate` and an `execute`. A gate returning false is
what `-fdump-passes` prints as `OFF`. `execute` gets the function and returns a
{term("TODO flags", "TODO mask")}.

The registration is four fields, defined at
{cite("gcc/tree-pass.h:328@releases/gcc-16.2.0")}.
""")

lesson.code("""
shown = cuts["info"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
notes = {
    338: "the name of an existing pass, and it has to be the pass name",
    340: "which run of it, where 0 means every run and 1 means the first",
}
print(shown.numbered(notes))
""")

lesson.md(f"""
{term("pass positioning", "Where the pass lands")} is decided by matching that name against
the pass list, at {cite("gcc/passes.cc:1377@releases/gcc-16.2.0")}.
""")

lesson.code("""
shown = cuts["position"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
notes = {
    1393: "the type has to match too, so a GIMPLE pass cannot hang off an RTL one",
    1399: "instance 1 is not pass number 1, it is the one marked as first",
}
print(shown.numbered(notes))
""")

lesson.md(f"""
A reference that matches nothing is a fatal error at registration time, which makes this the
one mistake in the whole area that tells you about itself immediately.

So: does the pass exist? `-fdump-passes` prints the pipeline, and here is where the new one
landed.
""")

lesson.code("""
where = session.pipeline
print(f"{where['total']} passes in the list, and the new one is number {where['index']}")
print()
for line in where["around"]:
    mark = "  <-- yours" if "gxcount" in line else ""
    print(line + mark)
""")

lesson.md(f"""
{
    claim(
        "a pass registered by a plugin is not a special case anywhere downstream: it appears "
        "in -fdump-passes between the two passes it was positioned against, and it gets its "
        "own numbered dump file under its own name, like every other pass"
    )
}.

`tree-gxcount`, sitting between `tree-ssa` and `tree-walloca1`. It also gets
`-fdump-tree-gxcount` and a file called something like `l2.c.376t.gxcount`, with the same
numbering scheme every other dump file uses, because from here down nothing knows or cares
that this pass came from outside.

And it ran.
""")

lesson.code("""
counted = session["countpass"]
print(counted.command)
print()
for line in counted.said:
    print("   ", line)
print()
print("assembly unchanged:", counted.asm == session["plain"].asm)
""")

lesson.md(f"""
Six phi nodes in `nearest`, which is the number T05 spent a lesson on, arrived at from inside
the compiler this time rather than by reading a dump.

The zero this pass returns is the promise mentioned above. A pass that modifies the IR and
returns zero has left the pass manager believing things that are no longer true: the CFG is
clean, SSA is up to date, nothing needs verifying. The compilation then fails somewhere
several passes later, in code that did nothing wrong. It is the most expensive mistake a
first plugin can make and the hardest to attribute, and the reason this one only reads.

## Switching one of GCC's passes off

Every pass has a gate, and one event is handed the address of the answer rather than the
answer, at {cite("gcc/passes.cc:2597@releases/gcc-16.2.0")}.
""")

lesson.code("""
shown = cuts["gatecall"]
print(shown.about)
print(f"{shown.span}  ({shown.citation})")
print()
notes = {
    2597: "which pass is being asked is not in the data, it is in this global",
    2605: "the only event whose data is written rather than read",
}
print(shown.numbered(notes))
""")

lesson.md(f"""
So a plugin can decide, per pass and per function, whether one of GCC's own passes runs. No
flag exists for most of them.
""")

lesson.code("""
print(plug.body("gate"))
""")

lesson.md(f"""
{
    claim(
        "a plugin can switch off one of GCC's own optimization passes for one function at a "
        "time, with no patch and no command line flag, and the generated code changes "
        "because of it"
    )
}.
""")

lesson.code("""
gated = session["gated"]
print(gated.command)
print()
print("   ", gated.said[-1])
print()
diff = session.diff("plain", "gated")
print(f"{len(diff)} lines of unified diff against the same program with nothing switched off")
print()
print("\\n".join(diff[:22]))
""")

lesson.md(f"""
`ivopts` is induction variable optimization: it rewrites a loop's array indexing into pointer
arithmetic the target can address directly. Switching it off leaves the loop correct and
slower, and it moves half the loop head. Fifty six lines of diff on a sixty nine line file.

Now the more useful half of the same experiment.
""")

lesson.code("""
ungated = session["ungated"]
print(ungated.command)
print()
print("   ", ungated.said[-1])
print()
print("assembly changed:", ungated.asm != session["plain"].asm)
""")

lesson.md(f"""
Early inlining was gated twice, refused twice, and the output is byte for byte what it was.
`l2.c` has a static function that clearly wants inlining and it still got inlined, because
`einline` is not the inliner that matters here: the IPA inliner later in the pipeline does the
work, and `einline` exists to make the early passes see through trivial calls.

That result is worth more than the first one. A pass switched off with no visible effect is
the normal case, and the reason is almost always that something else does the same job.

One thing will cost you an hour if nobody says it.

{
    claim(
        "the name in -fdump-tree-cddce1 is not a pass name: it is the pass called cddce plus "
        "the instance number the pass manager gave it, so asking for cddce1 by name matches "
        "nothing at all and reports nothing"
    )
}.
""")

lesson.code("""
print(session["gate-dumpname"].command)
print()
print("   ", session["gate-dumpname"].said[-1])
""")

lesson.md(f"""
Zero refusals, no error, no warning, and a compilation that looks exactly like a successful
experiment. The pass name is `cddce` and the trailing digit is the instance. This is the same
distinction that `ref_pass_instance_number` exists for, seen from the other side, and it is
why the plugin above prints a count rather than trusting that it did something.

## What gxplug is doing

`gxplug` is the plugin this repository ships and every lesson with a pass tape in it is built
on. It is one callback on `PLUGIN_PASS_EXECUTION`, two more on the ends of the run, and a
`PLUGIN_INFO` registration so `--help=plugin` says who it is. It writes one JSON object per
pass rather than printing anything.
""")

lesson.code("""
stream = session.stream
runs = stream.runs
print(f"{len(stream.events)} events, {len(runs)} pass runs, on {stream.functions}")
print(f"{stream.seconds:.4f} seconds of pass time recorded")
print()
for one in runs[:6]:
    print(f"  {one.name:<16} {one.start.size} -> {one.end.size if one.end else None}")
""")

lesson.md(f"""
And the number the pass tape lessons rest on.

{
    claim(
        "most passes that run leave nothing measurable behind: fewer than one in four of the "
        "runs on a nine line program change the statement count, the insn count, the block "
        "count or the property bits"
    )
}.
""")

lesson.code("""
marked = [one for one in runs if one.changed]
print(f"{len(runs)} runs, {len(marked)} left a mark you can see from outside")
print(f"that is {100 * len(marked) // len(runs)}%")
print()
for one in marked[:8]:
    print(
        f"  {one.name:<16} {one.start.size} -> {one.end.size}   blocks "
        f"{one.start.blocks} -> {one.end.blocks}"
    )
""")

lesson.md(f"""
Read that carefully, because it is easy to draw the wrong conclusion from it. `changed` here
means one of four counts moved. A pass that rewrote an expression in place without changing
the number of statements reports `False` and did real work. What the ratio is good for is the
honest version of the sentence people say about GCC having four hundred passes: they do not
all do something to your function, and on a program this small most of them look at it and
leave.

The one place the counts jump is the boundary between the two IRs.
""")

lesson.code("""
where = next(i for i, one in enumerate(runs) if one.name == "expand")
for one in runs[where - 1 : where + 2]:
    end = one.end
    print(f"  {one.name:<12} statements {end.statements}   insns {end.insns}   blocks {end.blocks}")
""")

lesson.md(f"""
Before `expand` the statement count is a number and the insn count is `null`. After it, the
other way round. They are never both set, because a basic block holds either a GIMPLE
sequence or an RTL insn chain in a union, and walking it as the wrong one does not fail a
check: it reads whichever pointer is there and segfaults. Which is what the first version of
`gxplug` did.

## Why the plugin API is not an API

Everything above works. None of it is a promise.

`gcc-plugin.h` is not an interface designed for you. It is a small header that pulls in
GCC's own private headers, and what you are compiling against is the compiler's internals as
they happened to be on the day of that release. There is no stability commitment, no
deprecation cycle, and no list of what is safe to call. `tree.h` changes between releases
because a GCC developer needed it to.

The consequences are concrete and you have seen most of them already:

- The plugin has to be built by the compiler that will load it. Not the same version, the
  same build. {term("plugin ABI", "The check")} compares the configure line.
- No binary plugin can be distributed. Every plugin ships as source and is built on the
  target machine, which is why every distribution has a separate `-plugin-dev` package.
- `-fno-rtti` is not a style choice. GCC is built without RTTI and a plugin that disagrees
  gets link errors about typeinfo that name no cause.
- What arrives with an event is a `void *` whose real type is written in the call site and
  nowhere else. Casting it wrong is a segfault, and `BP-PLUGIN` section 2 is a table of the
  twenty nine call sites for exactly this reason.
- A pass you insert can be moved by a GCC release that reorders the pipeline, and your
  `reference_pass_name` will still match, just somewhere else.

The upgrade story is that there is no upgrade story. A plugin is pinned to a compiler, and
the honest way to maintain one is to test it against each release and fix what broke.

Which is the whole argument for this repository's own design. `gxplug` emits JSON and the
Python side never parses a dump, so the fragile part is sixty lines of C++ in one file that
either compiles against a given GCC or does not, and the four hundred lines that read its
output do not care which compiler produced them.

## Doing this yourself

If you have a compiler with its plugin headers, from B01 or from a container, everything
above is four commands.

```sh
make -C gxplug probe GCC=gcc-16      # what it found, and where
make -C gxplug GCC=gcc-16            # the plugin
make -C gxplug examples GCC=gcc-16   # the five in this lesson
make -C gxplug examples-check GCC=gcc-16
```

The last one is the interesting one. It builds all five, loads each, and asserts that `hello`
and `countpass` leave the assembly identical, that `gate` does not, and that the two broken
ones are refused. The same target runs in CI on Debian, Fedora, Homebrew and a from-source
GCC on every push that touches the directory, which is what stops this lesson from describing
plugins that only work on the machine they were written on.

The prerequisite is the plugin development package, which is a separate install almost
everywhere:

| Channel | What to install |
|---|---|
| Debian | `gcc-16` and `gcc-16-plugin-dev` |
| Fedora | `gcc` and `gcc-plugin-devel` |
| Homebrew | `gcc`, which includes them |
| source | nothing, `make install` puts them under the prefix |

Then point `-fplugin=` at a `.so` and give it a `./` if it is in the current directory.

## Boss fight

Eight questions about loading, events, passes and gates.

    python lessons/b05-the-plugin/grade.py

Three of them are about failures rather than successes, which is where the time goes. The
last one has an answer that is a number, and the number is not the one most people say.

## What to read next

This is the end of M2. You can build GCC, bootstrap it, run it under a debugger, run its test
suite, and load code of your own into it. Everything from here on is about what the compiler
does rather than how to get at it.

M3 is the front end, and it starts before the parser. What the thing you type `gcc` at
actually is and what it runs, the preprocessor, the C parser, GENERIC and the tree
representation everything else is built on, types, the language hooks a front end has to
fill in, and gimplification, which is where a function stops being a tree and starts being
a program.
""")

raise SystemExit(lesson.save())
