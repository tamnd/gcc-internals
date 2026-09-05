"""B03. A debugger on the compiler, and the counter you use when you cannot have one.

This lesson has a constraint no other lesson in the course has: its subject cannot be run by
the reader. A debugger session against `cc1` needs a compiler built with `-O0 -g3`, which is
a three hundred megabyte binary out of a six gigabyte build, and it needs a gdb, which does
not exist on macOS at all. Colab has neither. So the session is recorded, once, with every
command and every byte of output kept, and `gxray.replay` plays it back.

That is a real loss and the lesson says so twice: near the top, where a reader decides how
much to trust what they are reading, and again at the end, where the honest limits of a
transcript belong. The mitigation is `record.py` next door, whose `check` function asserts
every behavioural fact this notebook states, so a rename in GCC fails the recording rather
than quietly turning the lesson into a page of error messages.

The second half is not a recording and that is the point of putting it here rather than in a
lesson of its own. `-fdbg-cnt` answers the same question a breakpoint does, and it answers it
without a debugger, so it is the technique a reader on a laptop can actually use. The corpus
carries one compilation per limit and `Bisect.narrow` runs a real binary search over them, so
the reader watches a bisection converge using arithmetic that runs now.

The order is deliberate. What the session already did before you typed anything comes first,
because a reader who does not know that `.gdbinit` set four breakpoints will spend their
first session confused about why the compiler stopped. Then counting, then stopping, then
looking, then the two ways it goes wrong. The counter is last because it is the answer to
"and what if I cannot do any of that", which is the question the whole lesson provokes.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "b03-the-debugger",
    "b03",
    title="A debugger on the compiler, and the counter for when you cannot have one",
    milestone="M2",
    summary=(
        "A real gdb session against a real cc1, recorded command by command: what the "
        "compiler's own gdbinit did before you typed anything, how to stop on one pass out of "
        "several hundred, how to read a function from a breakpoint, and how to find the exact "
        "transformation that broke your code by bisecting a debug counter instead"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# B03. A debugger on the compiler, and the counter for when you cannot have one

{badge}

B02 ended with a compiler you have some reason to trust. This lesson stops it in the middle
of a compilation and looks inside.

There are three ways to find out what a pass did to your code. Read the dump it printed,
which is most of Part I. Turn the pass off partway through and watch for the moment the
symptom appears, which is the second half of this lesson. Or stop the compiler inside the
pass and read the {term("control flow graph")} out of memory, which is the first half and
which needs a debugger.

One warning before anything else, because it changes how you should read the next twenty
cells. **Everything in the first half is a recording.** A real gdb, a real `cc1`, on a real
machine, on a day this notebook records, with every command and every byte of output kept in
`corpora/replay/cc1.json`. It is a recording because the compiler it needs is a six gigabyte
build that produces a three hundred megabyte binary, and because there is no gdb on macOS.
You cannot run this one. You can read every character the debugger printed, which is the next
best thing and is more than a screenshot in a book gives you.

The second half is not a recording. It is fifty real compilations of the same program, one
per limit of a debug counter, and a binary search that runs over them when you run the cell.

**What you come away with**

- Why the program you debug is not the program you ran, and the two ways to fix that
- The four breakpoints, twenty one skip entries and twenty one pretty printers that a GCC
  build tree installs before you type anything
- The one command shape all twenty six shorthands share, and which of them work on a core file
- Three ways to stop on one pass out of several hundred, and which one always works
- What 351 means, and why it is the number for nine lines of C
- Reading a function, a block, a statement and an edge from a breakpoint
- The same function printed either side of one pass, with the transformation visible
- Two commands in the pinned tree that do not do what their names say
- `-fdbg-cnt`, which answers the same question with no debugger at all
- A bisection over fifty compilations that ends on one transformation, named and located
""")

lesson.setup()

lesson.md(f"""
## The compiler you would need

Start with the thing that makes this lesson different, because it is also a fact about GCC
worth having.

{
    claim(
        "a GCC built so a debugger can see into it is the second most expensive configuration "
        "this project builds, and it produces a cc1 of three hundred megabytes"
    )
}.
""")

lesson.code("""
from gxray import replay, toolchain

plan = toolchain.plan("dbg")
print(f"{plan.id}: {plan.cost()}, {plan.config.purpose}")
print()
print(plan.configure())

cc1 = replay.load("cc1")
print()
print(cc1)
""")

lesson.md(f"""
`-O0` because at `-O2` the local variables you want to look at have been optimised away and
the line table runs backwards. `-g3` rather than `-g` because a great deal of what you want to
read in GCC is a macro, and only `-g3` records macro definitions so that a debugger can expand
`TREE_CODE` for you.

The configure line the recording actually used is not quite the one above. It built C only,
which halves the time, and it is recorded next to the session so the difference is visible
rather than implied.
""")

lesson.code("""
print(cc1.configure)
print()
print(f"recorded {cc1.recorded} on {cc1.host}")
print(f"{cc1.gdb}")
print(f"{cc1.binary}, {cc1.bytes:,} bytes")
""")

lesson.md(f"""
Three hundred and thirty two megabytes. An optimised `cc1` is about a tenth of that, and the
difference is almost entirely DWARF. This is the number that makes the session a recording,
and it is worth knowing before you start a `dbg` build on a laptop with a small disk.

## Getting a debugger in front of `cc1`

Now the first thing that goes wrong, which goes wrong for everybody once.

`gcc` is not the compiler. It is a {term("driver")} that works out which programs to run and
runs them, so a breakpoint set on `gcc` stops in a program that does no compiling. What you
want is `cc1`, which lives under `libexec` and which you have probably never invoked by hand.

Two ways to get it. Ask the driver what it would run and then run that yourself, which is
`gcc -###`, or leave the driver in charge and tell it to put a debugger in front of every
subprocess, which is `gcc -wrapper gdb,--args`. The first is what the recording used, because
a command line you can see is a command line you can edit and paste into a bug report.

{
    claim(
        "the command line the driver builds for one C file at -O2 has sixteen arguments on "
        "it, and you typed three of them"
    )
}.
""")

lesson.code("""
print(f"$ gcc -### -O2 -o /dev/null {cc1.program}")
print()
for one in cc1.argv:
    print(f"    {one}")
print()
print(f"{len(cc1.argv)} arguments")
""")

lesson.md(f"""
`-quiet` suppresses the banner, `-dumpbase` and `-dumpbase-ext` decide what the dump files
will be called, `-imultiarch` and `-iprefix` are how the driver tells the compiler where the
headers are, and `-mlittle-endian -mabi=lp64` are the target defaults made explicit. None of
that is optional. A `cc1` run without them behaves differently from the compilation you were
debugging, which is the trap `-###` exists to avoid.

`-###` and not `-v`. Both print the command lines, `-v` also runs them, and the arguments
`-v` prints are unquoted, so a command line with a shell metacharacter in it cannot be pasted
back. The specification for both is {cite("gcc/gcc.cc:3290@releases/gcc-16.2.0")} and
`BP-DRIVER`.

Here is the program. Nine lines, and everything in this lesson happens to it.
""")

lesson.code("""
print(cc1.source)
""")

lesson.md(f"""
## What the compiler's own `.gdbinit` did before you typed anything

A debugger started in a GCC build tree is not a debugger with default settings. It has four
breakpoints, twenty one skip entries, twenty six new commands and twenty one pretty printers,
none of which you asked for, and knowing that is the difference between a first session that
makes sense and one that does not.

The file is written by `configure`, not by `make`, which is why it is not in the source tree
and why `git status` never mentions it.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("b03")
print(f"{len(cuts)} excerpts, {cuts.lines()} lines, cut from {cuts.tag}")
print()
made = cuts["gdbinit"]
print(made.about)
print(f"{made.span}  ({made.citation})")
print()
print(made.numbered({7416: "the commands", 7417: "the Python, which is the printers"}))
""")

lesson.md(f"""
Two consequences, and both of them bite.

The first is that `${{srcdir}}` is an absolute path, fixed at the moment configure ran. A build
tree copied to another machine, or into a container, has a `.gdbinit` pointing at a source
tree that is not there, and gdb reports one error per line and carries on without the hooks.

The second is that the file is per build tree and is never installed. An installed GCC has no
`.gdbinit`, so none of this exists for a compiler you got from your distribution. Everything
in this lesson is for somebody standing in the directory that produced the binary.

A fourth line is added when the compiler was itself built with the address sanitiser, and it
is the reason a file called `gdbasan.in` exists in the tree.
""")

lesson.code("""
asan = cuts["gdbasan"]
print(asan.about)
print(f"{asan.span}  ({asan.citation})")
print()
print(asan.numbered())
""")

lesson.md(f"""
Now what the sourced file does on its way past. The breakpoints are the part that surprises
people, because a compiler that stops on its own is not what a first session expects.
""")

lesson.code("""
stops = cuts["breakpoints"]
print(stops.about)
print(f"{stops.span}  ({stops.citation})")
print()
notes = {
    343: "every failed assertion in GCC goes through this",
    346: "and every ICE through this",
    354: "the comment above says why: abort takes stdio with it",
}
print(stops.numbered(notes))
""")

lesson.md(f"""
`fancy_abort` is what `gcc_assert` calls, `internal_error` is what reports an
{term("SSA", "ICE")}, and the reason `abort` is on the list is written in the comment: if
`abort` runs, `stdio` stops working, and then the printing commands stop working, and you are
stopped in a compiler you can no longer ask anything. So the breakpoint is there to stop it
before it happens.

{
    claim(
        "a debugger started in a GCC build tree has four breakpoints set before the reader "
        "types a single command"
    )
}.
""")

lesson.code("""
print(cc1.startup[-60:].strip())
print()
print(cc1.step(1))
""")

lesson.md(f"""
That is the first command of the recorded session and it is the whole of what `.gdbinit` set
up, read back out of gdb. Note the addresses: two of the four resolved to a source line inside
the compiler and two to a PLT entry, because `exit` and `abort` are in libc.

The skip list is the other half, and it is the one you will be glad of within ten minutes of
using `step`.
""")

lesson.code("""
print(cc1.step(2))
""")

lesson.md(f"""
Twenty one entries, four of them whole headers. Without them a single `step` over a line
containing `TREE_CODE (t)` disappears into an inline accessor in `tree.h` and you spend the
next two minutes pressing `finish`. `INSN_UID`, `NEXT_INSN` and `PATTERN` are on the list for
the same reason on the RTL side.

The third thing is the {term("pretty printer")} set, which is what makes the rest of this
lesson readable at all. It is Python, loaded by that fourth line of `.gdbinit`, and it teaches
gdb how to print GCC's types.

{
    claim(
        "gdb ends up with more pretty printers registered than gdbhooks.py names, because four "
        "of them are registered in a loop"
    )
}.
""")

lesson.code("""
print(cc1.step(3))
""")

lesson.md(f"""
Twenty one, against the seventeen that `gdbhooks.py` registers by name. The extra four are
`scalar_mode`, `scalar_int_mode`, `scalar_float_mode` and `complex_mode`, registered by a loop
whose argument is a loop variable, which is why a table generated from the source undercounts
them and why the recording is worth having. `BP-DEBUGGING` section 2.5 has the named
seventeen and the types each one claims.

## The commands, and the one shape they all have

Twenty six of them, all defined in `gcc/gdbinit.in`, all with names of two or three letters
beginning with `p`. Here is one in full, because they are all this.
""")

lesson.code("""
shape = cuts["pt"]
print(shape.about)
print(f"{shape.span}  ({shape.citation})")
print()
notes = {
    84: "with no argument, use the last value gdb printed",
    85: "and this line is the entire command",
}
print(shape.numbered(notes))
""")

lesson.md(f"""
A command is a `call` into the compiler being debugged. `pt` calls `debug_tree`, `pr` calls
`debug_rtx`, `pgg` calls `debug_gimple_stmt`, and the `debug_*` family exists in GCC for no
other reason. They have no callers inside the compiler at all, which is why a link time
garbage collector would remove every one of them.

That makes sixteen of the twenty six an {term("inferior call")}: gdb sets up a stack frame in
the process being debugged and lets it run. Two things follow. They need a process that is
stopped somewhere a call can succeed, so none of them works on a core file, and a call that
crashes would leave the inferior wedged, which is why `.gdbinit` also sets `unwindonsignal on`.

The other ten read memory and work anywhere, including on a core file. `ptc` is
`TREE_CODE (t)`, `pdn` is `IDENTIFIER_POINTER (DECL_NAME (t))`. `BP-DEBUGGING` section 2.2 has
all twenty six with the function each one calls and the documentation each one carries, and it
is generated from the pinned tree rather than typed.

## When it declines to load any of that

Before the session proper, the failure that costs everybody an afternoon exactly once.

{
    claim(
        "the most common way a first session goes wrong is a warning rather than an error, and "
        "the symptom is that every command in this lesson does not exist"
    )
}.
""")

lesson.code("""
print(cc1.declined)
""")

lesson.md(f"""
That is the same gdb, in the same directory, started once without permission to read the file.
It is a warning. The session continues. Every command above is missing, `pcfun` reports
`Undefined command`, and nothing anywhere says the word `error`.

gdb prints both remedies in the message and they are worth reading rather than pasting. The
narrow one adds this one build tree to the safe path. The wide one turns the protection off
for every directory on the machine, which is a real decision, because auto-loading a
`.gdbinit` from a directory means running whatever is in it. On a current gdb the file to put
either line in is `~/.config/gdb/gdbinit` and not `~/.gdbinit`.

If you are driving gdb from a script rather than by hand, the flag is `-iex` and not `-ex`.
The local `.gdbinit` is read during startup, before any `-ex` runs, so `-ex` sets the safe
path after the decision it was meant to change.

## How often does a pass run

Now the session. The first question is not "how do I stop on `ccp`", it is "how bad is this
going to be", and the way to find out is to count.

{
    claim(
        "compiling nine lines of C at -O2 executes 351 passes, which is why a plain breakpoint "
        "on the pass manager is not usable"
    )
}.
""")

lesson.code("""
print(cc1.transcript("how often a pass runs"))
""")

lesson.md(f"""
Four commands. `break execute_one_pass` puts a breakpoint on the one function every pass goes
through. `ignore $bpnum 1000000` tells gdb to count hits and never stop, which turns a
breakpoint into a counter and is the single most useful thing in this lesson. Then run, and
then read the count back out of `info breakpoints`.

351, for nine lines. A real translation unit multiplies that by the number of functions, so a
file with four hundred functions in it goes through the pass manager somewhere north of a
hundred thousand times. A conditional breakpoint here, where gdb evaluates the condition,
costs a full stop and resume of the inferior on every one of those hits, and that is the
difference between a technique that works and one you abandon after four minutes.

Note also where it stopped: `Breakpoint 3, exit`. The compilation finished and ran into one of
the four breakpoints `.gdbinit` set, which is exactly what those are for.

## Stopping on the pass you care about

Three ways, and they differ in how much has to be true for them to work.

The one that always works is a condition on the pass name at the point where the pass manager
knows which pass it is holding. `pass->name` is a `const char *`, so comparing it with `==`
compares two addresses and is always false. gdb has `$_streq` for this.

{
    claim(
        "a conditional breakpoint on the pass name stops inside the pass manager with the pass "
        "object in hand, and the pass printer names it"
    )
}.
""")

lesson.code("""
print(cc1.transcript("stopping on the pass you care about"))
""")

lesson.md(f"""
Four things in there worth pulling out.

`delete` with no argument deletes every breakpoint, including the four from `.gdbinit`. That
is deliberate here and is worth being deliberate about, because the counting breakpoint would
otherwise still be counting.

`run` with no arguments re-runs with the same arguments, in the same gdb process. The compiler
starts over from nothing, the breakpoints do not, which is how you get from "the symptom is
somewhere in this compilation" to "the symptom is here" without restarting anything.

`<opt_pass* 0xbb47130 "ccp"(42)>` is the {term("pass")} printer at work. The number in
parentheses is the static pass number, which is the one `-fdump-passes` prints and the one
`-fdbg-cnt` has nothing to do with.

And the backtrace is six frames of pass manager and nothing else. `ccp` is inside
`early_optimizations`, which is a pass list, which is inside `opt_local_passes`, which is an
IPA pass being run for one function at a time by `do_per_function_toporder`. That is the whole
shape of {term("pass manager", "the pass manager")} in six lines, and Part I spent a lesson on
it.

The second way to stop is on the pass's own `execute` method, which costs nothing until it
fires and which is what `break-on-pass` does. It has a trap in it and the last section of the
session is about that trap.

The third way is a breakpoint on `pass_init_dump_file`, which happens once per function rather
than once per pass invocation, and is the one to reach for when the question is about one
function rather than one pass.

None of the three stops on a pass that did not run, and the reason is worth reading in the
source, because a breakpoint that never fires looks identical whether the pass is absent or
merely declined.
""")

lesson.code("""
gate = cuts["gate"]
print(gate.about)
print(f"{gate.span}  ({gate.citation})")
print()
notes = {
    2597: "the conditional breakpoint above stops here, before the gate runs",
    2601: "the gate, which is a method on the pass and can say no",
    2620: "and out, with the pass never entered",
}
print(gate.numbered(notes))
""")

lesson.md(f"""
`current_pass = pass` happens first and the {term("gate")} is evaluated second, so a
conditional breakpoint on the line where the name becomes readable stops even for a pass that
is about to decline. That is the useful behaviour: you find out that the pass was reached and
said no, which is a different fact from the pass not being in the pipeline. If your breakpoint
never fires at all, `-fdump-passes` is the thing to check before you conclude the breakpoint
is wrong.

## Looking at the function

You are stopped inside the pass manager, one pass before `ccp` runs. Everything about the
current function is reachable from two globals, `cfun` and `current_function_decl`.

{
    claim(
        "the pretty printers turn every pointer in this section into something readable, and "
        "without them each one of these prints a hexadecimal address"
    )
}.
""")

lesson.code("""
print(cc1.transcript("looking at the function"))
""")

lesson.md(f"""
Read that as four layers.

`cfun->decl` is a {term("tree")}, and the tree printer prints `<function_decl 0x... f>`: the
code, the address, the name. Without the printer it is a `union tree_node *` and gdb prints
the pointer. `ptc` gives you the code alone, which is the one question worth asking about a
tree you do not recognise, and `pdn` gives you the name through two macros without an inferior
call, so both work on a core file.

`pcfun` is the whole function, printed by the compiler itself in the same syntax the dump
files use. This is the command that makes a debugger session worth having, because it means
everything you learned about reading dumps in Part I applies at a breakpoint. The stray `void`
is gdb reporting the return type of the inferior call and is not part of the function.

Then the {term("control flow graph")}. Six blocks, of which two are the entry and exit that
every function has. `x_basic_block_info` is a `vec`, so indexing it needs the dereference and
the printer keeps the result short. The statements in a block are a `gimple_seq` and `pgq`
prints the sequence. The edges are a `vec<edge>` and the edge printer prints `4 -> 3` rather
than a pointer, which is the difference between reading a CFG and decoding one.

## Watching the pass work

Here is the part that pays for the whole setup. You are stopped before `ccp` runs. Let it run,
and print the function again.

{
    claim(
        "the same function printed either side of one pass shows exactly what that pass did, "
        "which for ccp on this program is two assignments and a return value"
    )
}.
""")

lesson.code("""
def printed(step):
    # pcfun is an inferior call, so gdb reports the return type of debug_function as well as
    # the output. It is the word void, and depending on how the two streams flushed it lands
    # before or after the function. It is not part of the function, so take it out.
    return "\\n".join(one for one in step.output.splitlines() if one.strip() != "void").strip()


calls = [one for one in cc1.steps if one.command == "pcfun"]
before, after = printed(calls[0]), printed(calls[-1])

print(cc1.transcript("watching the pass work"))
""")

lesson.md(f"""
`finish` runs to the end of the current frame and prints the return value, which for
`execute_one_pass` is whether the pass ran at all. `true`, so it did.

Now the two functions side by side, which is the same comparison a `-fdump-tree-ccp` would let
you make, except that you did it at a breakpoint on a compilation you were already inside.
""")

lesson.code("""
import difflib

diff = difflib.unified_diff(
    before.splitlines(),
    after.splitlines(),
    "before ccp",
    "after ccp",
    lineterm="",
    n=1,
)
print("\\n".join(diff))
""")

lesson.md(f"""
`s_3 = 0` and `i_4 = 0` are gone, and the {term("phi node", "phi nodes")} that used to read
`PHI <s_3(2), s_8(3)>` now read `PHI <0(2), s_8(3)>`. That is constant propagation, in one
screen, and `_6 = s_1; return _6;` collapsing to `return s_1;` is the copy propagation that
comes with it.

## Two commands that do not do what they say

The session ends on the two things in the pinned tree that will waste your time.

{
    claim(
        "break-on-pass takes a class name rather than a pass name, and given a pass name it "
        "produces a breakpoint that can never fire and says nothing about it"
    )
}.
""")

lesson.code("""
print(cc1.transcript("when it does not do what you meant"))
""")

lesson.md(f"""
`break-on-pass ccp` prints two lines that both read as informational and leaves you with a
pending breakpoint. A pending breakpoint is gdb being helpful about symbols that will arrive
when a shared library loads. This symbol will never arrive. The session runs to the end, the
breakpoint never fires, and the natural conclusion is that the pass did not run.

The name it wants is the class name, `pass_ccp`, and the reason is one line of Python.
""")

lesson.code("""
names, builds = cuts["passnames"], cuts["breakonpass"]
print(names.about)
print(f"{names.span}  ({names.citation})")
print()
print(names.numbered({707: "the first argument of NEXT_PASS, which is a class name"}))
print()
print(builds.about)
print(f"{builds.span}  ({builds.citation})")
print()
print(builds.numbered({754: "the argument goes in with nothing added and nothing checked"}))
""")

lesson.md(f"""
So the completion is right and the documentation is silent. Press tab and gdb offers
`pass_ccp`, because `PassNames` reads `passes.def` off disk and collects the class names out
of it. Type the pass name you have seen in every dump file instead, and it is accepted.

The way to tell the difference after the fact is the word `pending` in `info breakpoints`.

The second one is worse in that nothing can be done about it from where you are standing.
`reload-gdbhooks` is the command for editing `gdbhooks.py` and picking up the change without
restarting the session, and it runs `import imp`, which was removed from Python in 3.12. Any
gdb linked against a current Python cannot run it. The replacement is one line,
`importlib.reload`, and this is in the tree as of 16.2.0.

`kill` at the end is the tidy way out. The compilation is abandoned, nothing is written, and
the gdb process stays alive with all the breakpoints still set.

## The counter, for when you cannot have any of that

Everything above needs a special build of the compiler. Here is the technique that does not,
and it is the one you are more likely to use.

A {term("debug counter")} is a call to `dbg_cnt (name)` sitting in front of a transformation. It
returns true until the counter passes the limit you gave on the command line and false
afterwards, so `-fdbg-cnt=match:20` means "do the first twenty of these and then stop". The
whole mechanism is thirty seven lines.
""")

lesson.code("""
counter = cuts["dbgcnt"]
print(counter.about)
print(f"{counter.span}  ({counter.citation})")
print()
notes = {
    66: "the increment, which is the entire cost when no limit is set",
    68: "no -fdbg-cnt for this counter, so allow everything, forever",
    70: "every range used up, so allow nothing, forever",
    93: "and this is the line printed on stderr when a limit is reached",
}
print(counter.numbered(notes))
""")

lesson.md(f"""
Two properties of that function matter more than the rest.

The count is global and is never reset. It counts calls across every function in the
translation unit, in the order the functions are compiled, so a counter value is a position in
the whole compilation and not a position in a pass or a function. Add a function to the file
and every number moves.

And a counter with no limit costs one increment. That is why seventy five of these calls can
sit in the shipping compiler permanently.

{
    claim(
        "the match counter fires 49 times compiling nine lines of C at -O2, and those 49 "
        "transformations produce exactly two distinct assembly outputs"
    )
}.
""")

lesson.code("""
bisect = replay.load_bisect("counters")
print(bisect)
print()
print(f"compiled by {bisect.compiler} with {' '.join(bisect.flags)}")
print(f"{len(bisect.trials)} compilations, one per limit from 0 to {bisect.total}")
print()
print("\\n".join(bisect.listing.splitlines()[:2]))
for row in bisect.listing.splitlines():
    if row.split()[:1] == [bisect.counter]:
        print(row)
""")

lesson.md(f"""
`match` is the counter in front of GCC's pattern matching folder, which is the busiest counter
there is, and 49 calls for nine lines gives you a sense of how much folding happens in a
compilation you would call trivial. `-fdbg-cnt-list` prints all seventy five with their value
and their ranges, and it is printed by the compiler at the end of the run rather than by the
driver.

Two distinct outputs out of fifty compilations is what makes the next part work. Here is the
whole difference between them.
""")

lesson.code("""
diff = difflib.unified_diff(
    bisect.variants[1].splitlines(),
    bisect.variants[0].splitlines(),
    f"-fdbg-cnt={bisect.counter}:{bisect.first_good - 1}",
    "no limit",
    lineterm="",
    n=2,
)
print("\\n".join(diff))
""")

lesson.md(f"""
One instruction, with its operands the other way round. `cmp w1, w2` against `cmp w2, w1`, in
the loop, and everything else in the file identical. That is what a single missing fold looks
like at the assembly level, and it is a fair model of the real thing: a miscompilation is
usually one transformation, and the hard part is never fixing it, it is finding which one.

## Bisecting it

Which is what the counter is for. You have a compilation that is wrong and a counter you
suspect. Compile with half the transformations allowed. If the output is still wrong the
culprit is in the first half, and if it is right it is in the second. Repeat.

The cell below does exactly that. The compilations happened when the corpus was recorded, one
per limit, and the search runs now.

{
    claim(
        "five probes are enough to find one transformation out of forty nine, and the answer "
        "agrees with sweeping every limit one at a time"
    )
}.
""")

lesson.code("""
narrowed = bisect.narrow()
print(narrowed.report())
print()
print(f"{len(narrowed.probes)} probes, against {len(bisect.trials)} compilations in the sweep")
print(f"the exhaustive answer is {bisect.first_good}, and every limit above it is good: "
      f"{bisect.monotone}")
""")

lesson.md(f"""
Five probes and the answer, out of a fifty compilation sweep, and on a real bug where each
compilation is a build of one file rather than of nine lines that is the difference between an
afternoon and a coffee.

The `monotone` check next to it is not decoration. A bisection is only valid if the answer is
a step: every limit above the culprit good, every limit below it bad. For a counter that gates
one kind of transformation it usually is, and when it is not, a bisection returns a number
that means nothing. `gxray.replay` computes it by looking at every trial, which is a thing you
can do to a recording and cannot do to a real bug.

The counter tells you `-fdbg-cnt=match:43` and `-fdbg-cnt=match:42` differ. It does not tell
you what transformation 43 is. For that you go back to the debugger, break on `dbg_cnt` with a
condition on the count, and read the stack.

{
    claim(
        "the bisected number and a conditional breakpoint together name the transformation, "
        "the file it lives in and the pass that asked for it"
    )
}.
""")

lesson.code("""
for frame in bisect.culprit:
    print(frame)
""")

lesson.md(f"""
Read that from the bottom. `determine_group_iv_cost_cond` in the induction variable optimiser
is costing a candidate. `may_eliminate_iv` asks whether the loop's exit test can be rewritten
in terms of a different variable, and calls `fold_convert_loc` on the bound. That reaches the
generic folder, which reaches `generic_simplify_CONVERT_EXPR` in `generic-match-3.cc`, which
is a generated file: it is the C++ that GCC's `match.pd` pattern language compiles into. And
the first thing it does is ask the counter for permission.

So the answer to "which transformation broke my code" is a specific pattern in `match.pd`,
applied while costing a specific loop optimisation, on line 3783 of a file nobody wrote by
hand. You would not have found that by reading dumps.

## What a recording cannot do

The honest part, and it belongs here rather than in a footnote.

Everything in the first half of this lesson is dated. If GCC renames `execute_one_pass`, the
transcript above still shows the old name working and nothing in this notebook notices. That
is the opposite of how the rest of this course behaves, where a cell that stopped being true
fails the build.

Two things reduce the damage. The recorder next door,
`lessons/b03-the-debugger/record.py`, ends in a `check` function that asserts every
behavioural fact this lesson states: that the hooks loaded, that `pcfun` printed a function,
that the two `pcfun` outputs differ in the statement they should differ in, that
`break-on-pass ccp` is pending and `break-on-pass pass_ccp` is not, that `reload-gdbhooks`
fails on `imp`, and that the sweep is monotone. A recording that has rotted fails to record
rather than producing a lesson full of error messages. And `BP-DEBUGGING` sections 2.2 to 2.6
are regenerated from the pinned tree on every build, so the command list, the printer list and
the counter list are checked even though the session is not.

The second half has no such problem. Those are real compilations and the search over them runs
when you run the cell.

## Where to read more

`BP-DEBUGGING` in this repository's `blueprints/` is the reference this lesson was built from.
It has all twenty six commands with the function each one calls, all seventeen named printers
with the types they claim, all seventy five counters, the three ways to stop on a pass written
out as algorithms, and a section 8 that says in one table how much of this GCC tests, which is
almost none of it.

`gcc/gdbinit.in` and `gcc/gdbhooks.py` are both readable in an afternoon and are the only
documentation any of this has. `help-gcc-hooks` at a gdb prompt prints the list.

`contrib/gcc-git-customization.sh` and the `--param ggc-min-expand=0 --param
ggc-min-heapsize=0` pair are the two other things GCC developers reach for that did not fit
here. The second one collects garbage as often as possible, which turns "this tree was freed
three passes ago and now prints as plausible nonsense" from a rare confusion into a reliable
crash.

## Boss fight

Eight questions about stopping the compiler and about the counter.

    python lessons/b03-the-debugger/grade.py

Two of them are about what you would actually do, given a symptom and no debugger, and those
are the ones worth thinking about rather than looking up.

## What to read next

B04 is the test suite. Forty thousand tests, a language for writing them that is not any
language you know, and how to run one of them without running the other thirty nine thousand
nine hundred and ninety nine.
""")

raise SystemExit(lesson.save())
