"""T07. Where GIMPLE becomes RTL.

T02 showed the five faces of a function and named RTL as the fourth without explaining it.
T05 spent a whole lesson inside SSA, which is a property of the third face. This lesson is
the hinge between them: the pass that reads GIMPLE and writes RTL, what RTL is made of, and
why the same four lines of C come out of it as four different things on four machines.

Everything here comes from recordings. `l1-O2` is the local compiler's `.expand` dump for L1,
which the earlier lessons already use, and `t07-x86-64`, `t07-aarch64`, `t07-riscv64` and
`t07-power64le` are the same program through four back ends on Compiler Explorer.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t07-where-gimple-becomes-rtl",
    "t07",
    title="Where GIMPLE becomes RTL",
    milestone="M1",
    summary=(
        "The one node type the whole back end is built from, how to read an RTL expression "
        "out loud, why most of a function after expand is not instructions, the fiction of "
        "unlimited registers, and the same program on four machines disagreeing about every "
        "single thing you can measure"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T07. Where GIMPLE becomes RTL

{badge}

Everything so far has been about your program. GIMPLE has your variable names in it, near
enough. The control flow graph is the shape of the loop you wrote. SSA is a bookkeeping trick
played on values you can point at in the source.

This lesson is where that stops. {term("expand")} reads the last GIMPLE and writes the first
{term("RTL")}, and RTL is not about your program at all. It is about a machine, and it looks
worse than what came before it, and it is more verbose, and it is full of things that were
not in your code. All three of those are on purpose and this lesson is why.

You need a browser. There is no compiler here and no network.

**What you come away with**

- Being able to read an {term("RTX")} out loud in English, which is most of what people mean
  by knowing RTL
- The one struct the entire back end is built from, and the three things it holds
- Why the chain after expand is mostly not instructions, and what the rest of it is for
- What a {term("machine mode")} is and why `SI` and `DI` are everywhere
- The {term("pseudo register")} fiction, and the twenty passes it has to survive
- Having watched four back ends disagree about a four line program in every measurable way
""")

lesson.setup()

lesson.md(f"""
## Where it happens

There is one pass and it has a name you already know from the pass tape in T04. Its
description is at {cite("gcc/cfgexpand.cc:6999@releases/gcc-16.2.0")} and the class that
implements it is at {cite("gcc/cfgexpand.cc:7015@releases/gcc-16.2.0")}, and the thing to
notice about that second line is what it inherits from:

```c
class pass_expand : public rtl_opt_pass
```

Every pass before it is a `gimple_opt_pass`. This is the first one that is not. The pass runs
once per function, walks the basic blocks in order, and for each GIMPLE statement emits the
RTL that does the same thing on this target. When it is finished there is no GIMPLE left, and
there is no way back. Anything you wanted the compiler to work out about your program had to
have happened before this point.

The dump you want is `-fdump-rtl-expand`, and the recording has it.

```text
gcc-16 -O2 -fdump-rtl-expand l1.c
```

## What comes out

Start by looking at the thing before trying to understand it. Here are the first few entries
of L1's function `f` at the moment expand finished with it.
""")

lesson.md(f"""
{claim("L1 at expand is a chain of 40 entries and only 13 of them are instructions")}.
""")

lesson.code("""
from collections import Counter

from gxray import rtl

record = gxray.corpus_store.load("l1-O2")
listing = rtl.parse(record.dump_texts["rtl-expand"], "l1-O2").only()

print(f"{listing.function} from {record.compiler} on {record.target}")
print(f"{len(listing)} entries in the chain, {len(listing.code)} of them instructions")
print()
for kind, n in Counter(i.code for i in listing).most_common():
    print(f"  {n:>3}  {kind}")
""")

lesson.md("""
Ten `insn`, three `jump_insn`, and twenty seven other things. Two thirds of what expand
produced will never become a single byte of machine code. We will come back to that.

Here is the raw text of the first few, exactly as GCC printed them.
""")

lesson.code("""
for insn in list(listing)[:6]:
    print(insn.raw.rstrip())
    print()
""")

lesson.md(f"""
## Everything is one node

The first thing to know about RTL is the thing that makes it readable, and it is a claim about
the C rather than about the dump. There is one node type. Every parenthesis you saw above is
an instance of the same struct, `rtx_def`, and that struct holds three things:

- a **code**, saying what kind of thing it is, at
  {cite("gcc/rtl.h:319@releases/gcc-16.2.0")}
- a **{term("machine mode")}**, saying how wide the value is
- some **operands**, which are usually more nodes

There is no separate type for an instruction, an expression, a register or a constant. An
{term("insn")} is a node whose code happens to be `insn`, defined at
{cite("gcc/rtl.def:145@releases/gcc-16.2.0")} right next to
{cite("gcc/rtl.def:149@releases/gcc-16.2.0")} and
{cite("gcc/rtl.def:156@releases/gcc-16.2.0")} in the same list as `plus` and `reg`. That is
why a pass can walk any RTL without knowing what it is walking, and it is why the dumps look
so uniform.

The list of codes is one file and it is worth opening once. GCC 16 has 203 of them, plus a
sentinel at the top that means nothing has been decided yet.
""")

lesson.md(f"""
{claim("L1's whole function uses 13 different RTX codes, and 25 of the nodes are registers")}.
""")

lesson.code("""
codes = listing.codes()
print(f"{len(codes)} different RTX codes in the whole function, out of the 203 that exist")
print()
for code, n in codes.items():
    print(f"  {n:>3}  {code}")
""")

lesson.md(f"""
Thirteen. A four line program, and it needed thirteen of the two hundred and three. Most of
the code list is for machines and languages you will never compile for, and the working
vocabulary of everyday RTL is small enough to learn in an afternoon.

## Reading one out loud

Here is the skill this lesson is actually for. Take one expression apart and say what it does
in English, with no jargon in the sentence.

```text
(set (reg/v:SI 102 [ <retval> ])
     (plus:SI (reg/v:SI 102 [ <retval> ])
              (reg/v:SI 101 [ i ])))
```

Outside in. `set` means the second thing becomes the first thing. The first thing is a
register numbered 102 holding four bytes of integer. The second thing is a `plus` of that same
register and register 101. So: register 102 becomes register 102 plus register 101.

That is it. That is the whole expression. Two things get in the way of seeing it the first
time, and neither of them is part of the expression.

The `/v` after `reg` is a printed hint. It means this register came from a variable somebody
wrote, and the macro behind it is
{cite("gcc/rtl.h:1972@releases/gcc-16.2.0")}. Its neighbour
{cite("gcc/rtl.h:1968@releases/gcc-16.2.0")} prints `/i` and means this is the value the
function returns. The `[ <retval> ]` in brackets is also the printer, telling you which
variable the register came from so you can find your way. Delete both and the RTL is
unchanged.

`gxray` has a function that does the reading for you, which is useful for checking yourself
and useless as a substitute for being able to do it.
""")

lesson.md(f"""
{claim("insn 21 reads as pseudo 102 becoming pseudo 102 plus pseudo 101")}.
""")

lesson.code("""
from gxwidgets import english

for uid in [2, 21, 24, 15, 16, 38]:
    insn = listing.at(uid)
    print(f"{insn.code} {insn.uid}")
    print(f"    {insn.pattern}")
    print(f"    {english(insn.pattern)}")
    print()
""")

lesson.md("""
The last one is worth a second look. `(use (reg/i:SI 0 x0))` produces no code at all. It is
there to tell every later pass that the value in `x0` is still wanted when the function
returns, so that nothing helpfully deletes the instruction that put it there. RTL has several
of these and they are not decoration, they are the only thing keeping some correct code alive.

## The widget

The same first ten entries, one click at a time. The left column is the chain, the right panel
opens whichever one you pick into a tree, with a plain English reading at the top and every
node's code, mode and operands underneath. The buttons filter to instructions, to debug
entries, or to the markers.
""")

lesson.code("""
from IPython.display import HTML, display

from gxwidgets import RTXTree
from gxwidgets.rtxtree import KINDS, kind_of

widget = RTXTree(listing)
display(HTML(widget.render()))

# The same breakdown as text, so this cell proves something where HTML does not render.
for kind, gloss in KINDS.items():
    n = len([i for i in widget.shown if kind_of(i) == kind])
    print(f"{n:>3}  {kind:<6}  {gloss}")
""")

lesson.md("""
## The same thing as a picture

The widget is for poking at. This is the still version, which is what goes in the book, and it
draws one insn's pattern as the tree it was before the printer flattened it onto four lines.

The colours carry one distinction and it is the one that matters here. A pseudo register is
drawn as undecided, because which real register it ends up in has not been worked out and will
not be for another twenty passes. A hard register and a literal are drawn as settled, because
they already are.
""")

lesson.code("""
from IPython.display import SVG

import gxmanim

picture = gxmanim.mobjects.rtx_tree(listing.at(21))
display(SVG(gxmanim.svg.document(picture)))

print(picture.describe())
""")

lesson.md(f"""
## Most of it is not instructions

Back to the twenty seven. A function after expand is not a graph of blocks any more. It is a
doubly linked list of entries in the order they will run, and the blocks are recorded on notes
inside that list rather than being the thing you walk.

Three kinds of entry share the chain with the real instructions.

**Notes** mark where a basic block begins and ends, where a loop is, where the function
prologue should go. They are how the control flow graph survives into RTL at all.

**Labels and barriers** are the targets of jumps, and the markers saying that control cannot
fall off the end of this point.

**Debug insns** record where a variable lives at each moment so that a debugger can find `s`
when you stop in the loop. There are fifteen of them in L1, more than there are real
instructions, and every one of them will be deleted before assembly comes out. They exist so
that `-O2 -g` can tell you the truth about a variable that no longer exists.
""")

lesson.md(f"""
{claim("of the first ten entries in L1 exactly one is an instruction, six are for the debugger and three are markers")}.
""")

lesson.code("""
first_ten = list(listing)[:10]
for insn in first_ten:
    where = f"block {insn.bb}" if insn.bb is not None else "no block"
    print(f"{insn.uid:>3}  {kind_of(insn):<6}  {insn.code:<12}  {where}")

print()
for kind in ("code", "debug", "other"):
    print(f"{len([i for i in first_ten if kind_of(i) == kind]):>3}  {kind}")
""")

lesson.md("""
One instruction in the first ten. If you open an `.expand` dump and feel like you are reading
noise, that is because most of it is noise as far as the instructions go, and knowing which
lines to skip is a real part of reading these files.

## The register fiction

Now the part that surprises people. Look at the numbers on the registers above. 101, 102, 103.
""")

lesson.md(f"""
{claim("L1 uses three pseudo registers, numbered 101 to 103, and two hard ones")}.
""")

lesson.code("""
pseudos, hard = listing.registers()
print(f"{len(pseudos)} pseudo registers: {pseudos}")
print(f"{len(hard)} hard registers: {hard}")
print()
for insn in listing.code:
    names = sorted({str(n.register) for n in insn.registers if not n.pseudo})
    if names:
        print(f"{insn.uid:>3}  touches hard register {', '.join(names)}")
""")

lesson.md(f"""
Three pseudos and two hard registers. Register 0 is `x0`, which is where the argument arrives
and where the result has to be when the function returns, so expand had no choice about it.
Register 66 is the condition code, which the machine only has one of, so expand had no choice
about that either. Every other register in the function is one that does not exist.

That is deliberate and it is the single most useful thing to know about expand. The expander
pretends the machine has as many registers as it wants, hands them out in order from the first
free number with {cite("gcc/emit-rtl.cc:1188@releases/gcc-16.2.0")}, and leaves the question
of which real register each one goes in to a pass twenty steps later. It has to work that way.
Choosing instructions and allocating registers are both hard, and doing them at once is much
harder than doing them one after the other.

Where the numbering starts is the target's business. `FIRST_PSEUDO_REGISTER` is however many
real registers the machine has, and then there are six virtual registers on top of that before
the first pseudo, running from {cite("gcc/rtl.h:4091@releases/gcc-16.2.0")} to
{cite("gcc/rtl.h:4146@releases/gcc-16.2.0")}. That is why the same program starts numbering at
98 on one machine and 134 on another, and why a pseudo number is never worth quoting on its
own.

## Machine modes

The other thing on every node is the mode, and it is the letters after the colon. `SI` is four
bytes of integer, `DI` is eight, `QI` is one, `HI` is two. They are declared as a list of
sizes in one file, and {cite("gcc/machmode.def:211@releases/gcc-16.2.0")} is the whole
definition of `SImode`:

```c
INT_MODE (SI, 4);
```

The mode is what stops the back end from having to look at a type. There are no types in RTL.
A 32 bit `int`, a 32 bit `unsigned`, a 32 bit `float` cast to bits, and a pointer on a 32 bit
machine are all the same width, and where the difference matters it is in the operation rather
than in the operand. `plus` and `plus` are the same. Signed and unsigned division are two
different codes.
""")

lesson.md(f"""
{claim("SI appears 30 times in L1, CC six times and DI twice")}.
""")

lesson.code("""
for mode, n in listing.modes().items():
    print(f"  {n:>3}  {mode}")

print()
print("where the modes that are not SI turn up:")
for insn in listing:
    if insn.pattern is None:
        continue
    odd = sorted({n.mode for n in insn.pattern.walk() if n.mode not in ("", "SI")})
    if odd:
        print(f"  {insn.uid:>3}  {', '.join(odd)}")
""")

lesson.md("""
`CC` is the interesting one. It is the mode of a condition code, which is what a compare
writes and a conditional branch reads. Whether the machine has such a thing at all, and where
it lives, is entirely up to the target. Which brings us to the point of the lesson.

## Four back ends

Up to expand this course has been able to say "the compiler" and mean one thing. The front end
is shared. The middle end is shared. Expand is where the target gets a say, and the cheapest
way to see what that means is to run the same four lines of C through four back ends and put
the answers next to each other.

Same source, same flags, same version of GCC.
""")

lesson.md(f"""
{claim("the four targets agree on none of the ten things the table measures")}.
""")

lesson.code("""
from gxwidgets.__main__ import targetcompare

four = targetcompare()
display(HTML(four.render()))

agree = [key for key, same in four.data()["rows"].items() if same]
print(f"{len(four.targets)} targets: {', '.join(four.targets)}")
print(f"{len(agree)} of {len(four.data()['rows'])} rows the same everywhere")
""")

lesson.md("""
Nothing. Ten measurements and not one of them survives a change of machine, on a program with
one loop in it.

Three of the rows are worth stopping on, because each one is a different kind of disagreement.

**Where the condition code lives.** x86-64 has one flags register and names it, and it uses
two different CC modes because it cares which flags the compare set. aarch64 has one flags
register too and one CC mode. PowerPC has eight condition fields, so the compare writes a
pseudo and the allocator picks which field later. RISC-V has no flags register at all.

**Compare and branch.** Three of the four emit two instructions, a compare that writes the
condition code and a branch that reads it. RISC-V emits one, with the comparison inside the
branch, because that is what the instruction set has.

**Does adding destroy anything.** On x86-64 an add sets the flags whether you wanted it to or
not, and RTL has to say so or a later pass will move a compare across it. So x86's add is a
`parallel` holding two things at once: the sum, and a `clobber` announcing that the flags are
now rubbish. The other three add with a plain `set`.
""")

lesson.code("""
def adds(one):
    \"\"\"Every instruction in a listing that has an addition anywhere inside it.\"\"\"
    return [i for i in one.code if i.pattern and any(n.code == "plus" for n in i.pattern.walk())]


for name in four.targets:
    print(name)
    for insn in adds(four.listings[name])[:2]:
        print(f"  {insn.uid:>3}  {str(insn.pattern)[:96]}")
    print()
""")

lesson.md(f"""
## The one that is not the back end

There is a fourth difference in that table and it is not an expand difference at all, which
makes it the most interesting thing here.

Look at power64le. It has a pseudo called `doloop.6` counting down to zero, and nothing in the
C source counts down. No other target has one. If expand were the only place targets differ,
that could not happen, because all four targets were handed the same GIMPLE.

They were not. The middle end asks the target a question, in
{cite("gcc/target.def:4728@releases/gcc-16.2.0")}, and the induction variable pass at
{cite("gcc/tree-ssa-loop-ivopts.cc:8104@releases/gcc-16.2.0")} uses the answer to decide
whether to rewrite the loop into a countdown. Two targets in the whole tree answer yes. So the
GIMPLE that reached expand really was different for PowerPC, three passes earlier, because of
a hook.

The shared middle end is shared in the sense that it is one body of code. It is not shared in
the sense that it does the same thing.

## The picture

One statement across the hinge, one node taken apart, and the chain with its notes, are drawn
in
[`diagrams/one-statement.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t07-where-gimple-becomes-rtl/diagrams/one-statement.excalidraw).
Open it at excalidraw.com and you can move things around.

## Where to read more

`BP-RTL` in
[`blueprints/BP-RTL.md`](https://github.com/tamnd/gcc-internals/blob/main/blueprints/BP-RTL.md)
is the reference version of this lesson. It has the node layout, the format strings that say
what each code's operands are, the register numbering, the printing algorithm, and four
invariants that hold at expand and stop holding later.

## Boss fight

Six RTX expressions, taken from all four recordings, and six English sentences. They are not
in the same order. Match them.

Then two questions the table can answer but only if you can read the expressions.

1. Which target's add has to destroy a register, and how you can tell from the expression
2. Which target has no condition code register, and what it does instead

The one to work at is the fifth sentence. It describes an expression that no other target
produced, about a variable that is not in the source, and the reason is not in the back end.

```text
python lessons/t07-where-gimple-becomes-rtl/grade.py
```

or `just grade t07-where-gimple-becomes-rtl`. It takes the answers on the command line too,
so `--answers A3 B1 C6 D2 E5 F4 --clobbers x86-64 --no-flags riscv64` is a complete
submission. It prints the six sentences first, so run it once to read them before answering.

Here are the six expressions.
""")

lesson.code("""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    "t07grade", pathlib.Path("lessons/t07-where-gimple-becomes-rtl/grade.py")
)
boss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boss)

for letter, entry, uid in boss.EXPRESSIONS:
    insn = boss.expression(entry, uid)
    print(f"{letter}.  {entry}, {insn.code} {insn.uid}")
    for line in str(insn.pattern).splitlines():
        print(f"    {line}")
    print()
""")

lesson.md("""
## What to read next

T08 stays in RTL and comes back to the pretence this lesson set up. Expand handed out pseudo
101, 102 and 103 on the understanding that the machine has as many registers as anybody wants.
It does not. T08 is about the pass that has to make good on that promise with the sixteen or
thirty two registers the machine actually has, and about what happens when there are not
enough.

M3 is the back end properly, and it opens by taking the machine description apart. Everything
in this lesson that came down to "the target decides" is a file you can go and read.
""")

raise SystemExit(lesson.save())
