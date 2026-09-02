"""T05. SSA in one lesson.

The pilot. Everything the course promises has to be true of this one first: a reader with a
browser and no compiler can run it, every claim in it has a cell under it, every statement
about GCC's source has a citation that resolves, and it can be finished in an evening.

It runs entirely on the recorded dumps in `corpora/`, which are real output from a real GCC
16.2 and are checked into the repository. There is no network in it and no compiler, which
is the only way a first lesson can be reliable.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t05-ssa-in-one-lesson",
    "t05",
    title="SSA in one lesson",
    milestone="M0",
    summary=(
        "Reading `s_1`, `s_3` and `s_8` as three versions of one variable rather than three "
        "variables, what a `PHI` is and where it has to go, what the `(D)` on `n_5(D)` is "
        "telling you, and watching SSA get taken apart again on the way to machine code"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T05. SSA in one lesson

{badge}

{term("SSA", "Static Single Assignment")} is the idea the whole middle end of GCC is built
on, and it is usually explained backwards. You get a definition, then a page about dominance
frontiers, then an algorithm, and somewhere in there the reason anybody bothered goes
missing.

This lesson does it the other way round. We take one eight line C function, look at what GCC
actually turned it into, and read the answer off the page. By the end you will be able to
open any GIMPLE dump and know what every name in it means, why the odd looking `PHI` lines
are there, and what they cost.

You need a browser. There is no compiler here and no network. Everything below runs on dumps
that a real GCC 16.2 produced, recorded and committed, so you get the same output as the
lesson does.

**What you come away with**

- Reading `s_1`, `s_3`, `s_8` as three versions of one variable rather than three variables
- Knowing what a `PHI` is, where it has to go, and why
- Knowing what the `(D)` means when you see `n_5(D)`
- Being able to answer "where does this value come from" in one step instead of by searching
- Seeing SSA get taken apart again on the way to machine code
""")

lesson.setup()

lesson.md("""
## The program

One loop, one accumulator, one counter. Small enough to hold in your head and big enough
that SSA has something to do.
""")

lesson.code("""
print(gxray.L1)
""")

lesson.md("""
We are going to look at it through a recorded backend rather than a live compiler. The
banner says so, in as many words, every time. That matters: a lesson that quietly shows you
somebody else's output while implying it is yours is worse than no lesson.
""")

lesson.code("""
backend = gxray.corpus("l1-O2")
print(gxray.banner(backend))

result = backend.compile(gxray.L1)
print("dumps available:", ", ".join(result.dump_keys))
""")

lesson.md(f"""
`tree-ssa` is the one we want. It is the dump taken just after GCC has put the function into
SSA form and before any optimisation has run on it, so it is as close as you get to a plain
translation of your program into the middle end's language.

## One variable, three names

Here is the whole function as GCC sees it at that point. Read it once before reading anything
below it. The `# DEBUG` lines are bookkeeping for a debugger and you can ignore them, the
bracketed things are source locations, and the rest is
{term("GIMPLE")}.
""")

lesson.code("""
print(result.dump_text("tree-ssa"))
""")

lesson.md(f"""
The variable you wrote as `s` is not in there. What is in there is `s_3`, `s_1` and `s_8`.

That is the whole of SSA in one observation. {
    claim("the variable s from the source appears in the tree-ssa dump as three separate SSA names")
}, one for each place a value gets put into it: the initial zero, the value at the top of
the loop, and the value after the addition. Same for `i`, which becomes `i_4`, `i_2` and
`i_9`.
""")

lesson.code("""
from gxray.gimple import ssa_names

f = result.dump("tree-ssa").only()
everything = ssa_names(result.dump_text("tree-ssa"))

for base in ("s", "i", "n"):
    versions = [str(n) for n in everything if n.base == base]
    print(f"{base:>2} appears as {', '.join(versions)}")

# One name has no variable in front of the underscore at all.
print(" _ appears as", ", ".join(str(n) for n in everything if not n.base))
""")

lesson.md(f"""
The number after the underscore is the {term("SSA name", "version")}. It is worth being
precise about what "single assignment" means here, because the obvious reading is wrong:
`s_8 = s_1 + i_2` sits inside a loop and runs many times. The rule is not that a name gets a
value once while the program runs. It is that a name is written in exactly one place in the
text of the function. Static, as in static analysis, not as in unchanging.

The versions are handed out from one counter for the whole function, which is why they are
not consecutive per variable and why the numbers do not follow the order things happen in.
`s_1` is the phi at the top of the loop and `s_3` is the zero assigned before the loop even
starts, so the lower number is the later definition. There is no information in the gaps and
none in the order. Do not read anything into either.

The one that is only `_6` is a compiler temporary. It has a version like everything else and
no variable in front of the underscore, because there was no variable in your source for it
to belong to. Gimplification invented it to hold the value of `s` on the way to the `return`,
and after SSA it is a name like any other.

## Why anybody bothered

Here is the payoff, and it is worth being concrete about it because it is easy to miss.

Ask a question about the program: where does the value in `s_1` come from, and who uses it?
Before SSA that question meant walking backwards through the {term("control flow graph")}
looking for writes to `s`, giving up wherever two paths join, and doing the same thing
forwards for the uses. With SSA, {
    claim(
        "an SSA name knows the single statement that defines it and the full list of places it is used"
    )
}, so both directions are a lookup.
""")

lesson.code("""
web = f.ssa_web("s_1")

print("name:      ", web["name"])
print("defined by:", web["def"])
print("used by:")
for use in web["uses"]:
    print("           ", use)
""")

lesson.md(f"""
One {term("definition")}, two {term("use", "uses")}, no searching. Every optimisation in the
middle end is built on being able to do that, and most of them are not much more than doing
it repeatedly.

Here is the same thing as a picture. The diagram is drawn from the dump you just printed, not
from an illustration somebody made once and forgot to update.
""")

lesson.code("""
from IPython.display import SVG, display

import gxmanim

picture = gxmanim.mobjects.ssa_web(f, "s_1")
display(SVG(gxmanim.svg.document(picture)))

# Every diagram in this project can also say what it shows in words, which is what a screen
# reader gets and what the tests check against.
print(picture.describe())
""")

lesson.md(f"""
## The problem at a join

Now the part that makes SSA interesting rather than just tidy.

Look at `<bb 4>`. The `bb` stands for {term("basic block")}, and two of them can reach this
one: `<bb 2>`, falling in from the code before the loop, and `<bb 3>`, coming
round from the bottom of the loop body. So when control arrives at the top of `<bb 4>`, the
current value of `s` is either `s_3` or `s_8`, depending on which way you came.

SSA does not allow that. A name has one definition. Two definitions arriving at one place is
exactly the thing the rule forbids, and it happens at every join in every program with a
branch in it, so this is not a corner case, it is the case.

The answer is the {term("phi node")}.
""")

lesson.code("""
for block in f.ordered_blocks:
    for phi in block.phis:
        print(f"<bb {block.index}>  {phi}")
""")

lesson.md(f"""
Read `# s_1 = PHI <s_3(2), s_8(3)>` as: `s_1` is `s_3` if you got here from block 2, and
`s_8` if you got here from block 3.

Three things about it are worth stating plainly, because all three trip people up.

It is not an instruction. Nothing computes a phi and no machine has one. It is a note in the
IR saying which value this name stands for on each path, and it will be gone before any code
is generated.

{claim("a phi node has exactly one argument per incoming edge, and the arguments are positional")},
matched up with the predecessors in order. That is why deleting an {term("edge")} into a
block means editing every phi in that block, and why a pass that rearranges control flow has
to touch phis it otherwise has nothing to do with.

And all the phis in a block happen at once, conceptually, before any other statement in the
block. That matters when two phis refer to each other, which happens after some loop
transformations.

If you want the same thing as a hand drawn picture rather than as a dump, there is one in
[`diagrams/phi-at-a-join.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t05-ssa-in-one-lesson/diagrams/phi-at-a-join.excalidraw).
Open it at excalidraw.com and you can move the blocks around. It is the only picture in this
lesson that is not drawn from the dump, because it shows why a phi has to be there, and that
is an argument rather than a piece of data.
""")

lesson.code("""
graph = result.cfg("tree-ssa")

for block in f.ordered_blocks:
    if not block.phis:
        continue
    incoming = [edge.src for edge in graph.predecessors(block.index)]
    print(f"<bb {block.index}> has predecessors {incoming}")
    for phi in block.phis:
        print(f"    {phi.lhs} takes", ", ".join(f"{v} from bb {p}" for v, p in phi.args))
""")

lesson.md(f"""
The arguments line up with the predecessors, one for one. If they did not, the dump would be
malformed and GCC built with `--enable-checking` would have refused it.

## Where a phi has to go

A phi is not free, so GCC does not put one at every join for every variable. It puts one
exactly where a name would otherwise have two live definitions arriving, and working out
where that is is a question about {term("dominance")}.

The rule for reading a dump is simpler than the algorithm for producing it. A definition is
usable at a point if the block holding the definition dominates that point, meaning every
path that gets there goes through the definition first. Where that fails, you need a phi.

The cell below prints each block's {term("immediate dominator")}, which is the closest block
every path has to go through on the way in.
""")

lesson.code("""
dominators = graph.dominators()

print(graph)
for block, idom in sorted(dominators.items()):
    print(f"    bb {block:>2} is immediately dominated by bb {idom}")
""")

lesson.md(f"""
`<bb 4>` is dominated by `<bb 2>` and not by `<bb 3>`, which is the formal version of "you
can get to the top of the loop without having gone round it". So `s_8`, defined in `<bb 3>`,
is not available at the top of `<bb 4>` on every path, and a phi is the only way to name the
value that is.

Notice that {claim("bb 3 and bb 5 are both immediately dominated by bb 4, not by each other")},
even though `<bb 5>` comes after `<bb 3>` in the dump. Dump order is not execution order and
it is not dominance order. It is roughly the order the blocks were created in, and reading
anything else into it will mislead you.

Here is the dominator tree drawn out.
""")

lesson.code("""
tree = gxmanim.mobjects.dom_tree(graph)
display(SVG(gxmanim.svg.document(tree)))

print(tree.describe())
""")

lesson.md(f"""
## The names with a (D) on them

One name in the dump has no definition anywhere: `n_5(D)`.
""")

lesson.code("""
condition = [s for b in f.ordered_blocks for s in b.stmts if s.text.startswith("if ")]
print(condition[0].text)
print()
for name in ssa_names(condition[0].text):
    print(f"{str(name):>8}  default definition: {name.default}")
""")

lesson.md(f"""
That is a {term("default definition")}. The `(D)` means the value was already there when the
function was entered, so there is no statement to point at. Parameters always have one,
because their value came from the caller.

The interesting case is the other one. A local variable read before it is written also gets a
`(D)` name, and that is GCC telling you, in the IR, that your program has undefined behaviour
and it is going to compile it anyway. If you ever see a `(D)` on something that is not a
parameter, stop and look at it.

## Versions are not addresses

Here is a mistake that is easy to make once you are comfortable reading dumps: treating a
version number as if it identified a value across the whole compilation.

It does not. {
    claim(
        "the SSA versions in tree-optimized are different from the ones in tree-ssa for the same function"
    )
}, because passes delete names, create names, and never reuse a number. A dump is a snapshot
and the numbering in it is only meaningful within that snapshot.
""")

lesson.code("""
optimized = result.dump("tree-optimized").only()

before = sorted(str(n) for n in ssa_names(result.dump_text("tree-ssa")))
after = sorted(str(n) for n in ssa_names(result.dump_text("tree-optimized")))

print("tree-ssa      ", ", ".join(before))
print("tree-optimized", ", ".join(after))
print()
print("names in both:", ", ".join(sorted(set(before) & set(after))) or "none")
""")

lesson.md("""
Not one survives. Same function, same variables, same loop, and there is no overlap at all.

## What SSA bought

Now look at the same function after the middle end has finished with it. This is
`tree-optimized`, the last GIMPLE dump before the compiler starts thinking about a machine.
""")

lesson.code("""
print(result.dump_text("tree-optimized"))
""")

lesson.md(f"""
Three things happened, and each one is something SSA made cheap.

The loop got a guard. The condition `n_3(D) > 0` is now in `<bb 2>`, before the loop, and the
loop itself ends with `n_3(D) != i_6`. GCC proved the loop runs zero or more times, hoisted
the zero check out, and turned the remaining test into a comparison that a machine does in
one instruction. Doing that safely means knowing exactly which values the condition depends
on, which is a question about definitions.

There is a phi in the exit block that was not there before. `# s_10 = PHI <s_5(3), 0(2)>` in
`<bb 4>` exists precisely because the loop can now be skipped, so the returned value is
either the accumulated `s_5` or the literal zero. The new control flow created a new join and
the join needed a phi. Notice also that one of the arguments is a constant rather than a
name, which is allowed and is common.

And the block count went down.
""")

lesson.code("""
for key in ("tree-ssa", "tree-optimized"):
    g = result.cfg(key)
    print(f"{key:>16}  {g}")
    print(f"{'':>16}  loops {g.loops}, back edges {[str(e) for e in g.back_edges]}")
""")

lesson.md(f"""
The loop went from a header at `<bb 4>` with the body at `<bb 3>` to a single block branching
to itself. That is loop rotation, and it is worth noticing that
{claim("after optimization the back edge in l1 goes from bb 3 to itself")}, which is what a
one block {term("loop")} looks like in a CFG.
""")

lesson.code("""
optimized_graph = result.cfg("tree-optimized")
rotated = gxmanim.mobjects.cfg_view(optimized_graph)
display(SVG(gxmanim.svg.document(rotated)))

print(rotated.describe())
""")

lesson.md(f"""
## Taking it apart again

SSA is a fiction that has to end, because no machine has an instruction meaning "whichever
value the path you took produced". The pass that removes phi nodes is called
{term("out of SSA")}, and the naive version of it puts a copy on each incoming edge: at the
end of `<bb 2>` do `s = 0`, at the end of `<bb 3>` do `s = s_5`, and then `<bb 4>` can just
read `s`.

That would cost a register move per phi argument, which is a lot to pay for a bookkeeping
device. So the real pass spends most of its effort proving that the names involved never need
to be alive at the same time, and when it can prove that, they share one location and the
copy disappears.

You can see the result. In the RTL dump,
{
    claim(
        "every SSA version of s in tree-optimized ends up in the one virtual register that also "
        "holds the return value"
    )
}.
""")

lesson.code("""
import re

rtl = result.dump_text("rtl-expand")
registers = sorted(set(re.findall(r"reg/v:SI (\\d+) \\[ (\\w+|<retval>) \\]", rtl)))

print("virtual registers holding a named value:")
for number, name in registers:
    print(f"    reg {number}  <- {name}")

# The debug notes are the compiler saying where each variable from your source ended up.
print("\\nwhat the debug notes say:")
for variable, number in sorted(set(re.findall(r"var_location:SI (\\w+) \\(reg/v:SI (\\d+)", rtl))):
    print(f"    {variable} is in reg {number}")
""")

lesson.md(f"""
There is no register called `s`, and that is the interesting part. `s_9`, `s_5` and `s_10`
all became register 102, which is labelled `<retval>` because it is also where the return
value goes. Coalescing proved that `s` and the returned value never need to be alive at the
same time, so it gave them one place instead of two, and the copy at the end of the function
disappeared along with the phis. The debug notes are how you tell, since a `var_location` is
the compiler recording which register a variable from your source landed in.

`i_11` and `i_6` went the same way, into register 101. Six SSA names in `tree-optimized`,
three registers coming out of expand, and no copies between any of them.

That is the whole arc: split every variable into one name per definition so the middle end
can reason about it, then put it back together again before anybody has to allocate a real
register.

## What the source says

The three claims this lesson makes about GCC's own code, rather than about what it produced:

The `SSA_NAME` tree code is declared in the same file as every other tree code, with a
comment saying exactly what this lesson has been showing:
{cite("gcc/tree.def:1035@releases/gcc-16.2.0")}.

A phi is a `gphi`, which is a subclass of the base GIMPLE statement rather than a separate
kind of thing, at {cite("gcc/gimple.h:474@releases/gcc-16.2.0")}. That is why the code that
walks statements can walk phis too.

And the dominance query that the whole placement argument rests on is one function,
{cite("gcc/dominance.cc:856@releases/gcc-16.2.0")}, which returns a block and is the thing
passes call thousands of times.

## Boss fight

Here is a different function. Work out, on paper, before running anything:

1. How many phi nodes will its `tree-ssa` dump have, and in which blocks
2. Which variable will have the most versions
3. Whether any name will carry a `(D)`

Then check yourself. There is a grader in this lesson's directory that will tell you which
parts you got right.

```c
int g (int n, int flag)
{{
  int total = 0;
  for (int k = 0; k < n; k++)
    {{
      if (flag)
        total += k;
      else
        total -= k;
    }}
  return total;
}}
```

The answer needs a compiler, which this lesson deliberately does not have, so it lives in
`lessons/t05-ssa-in-one-lesson/grade.py` and runs against a recorded dump of exactly this
program. Run `just grade t05-ssa-in-one-lesson` from a checkout.

## What to read next

T02 goes back a step and shows the same function in all five representations at once, which
is the fastest way to stop being surprised by a dump you have not seen before.

G03 is dominance properly: the algorithm, why GCC computes it lazily, and the dominance
frontier, which is the thing that actually decides where phis go rather than the informal
rule used above.

G05 is out of SSA in detail, including the case where coalescing fails and you get the copies
after all.

If you would rather poke at this one for longer, change `gxray.corpus` to
`gxray.ce` in the setup and every cell in this lesson will run against a live GCC 16 on
Compiler Explorer, with your own program in place of `gxray.L1`.
""")

raise SystemExit(lesson.save())
