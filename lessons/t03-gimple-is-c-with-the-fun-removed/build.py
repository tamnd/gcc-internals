"""T03. GIMPLE is C with the fun removed.

The second rung of the T02 ladder, on its own, with a bench of seven one line functions
chosen so that each one breaks a different thing C lets you write.

Everything here comes from the `t03-bench` corpus entry, recorded at -O0 with -g and the
`lineno` modifier. -O0 matters: nothing runs after gimplification, so what the dump shows is
the front end's work and not an optimizer's. The dump is `tree-gimple`, which is the earliest
one there is, taken before the CFG exists.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t03-gimple-is-c-with-the-fun-removed",
    "t03",
    title="GIMPLE is C with the fun removed",
    milestone="M1",
    summary=(
        "Why the middle IR looks so plain, the one rule that makes it that way, where the "
        "temporaries come from and how many of them to expect, and why the two operators "
        "that cannot survive the trip are the two that were never really operators"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T03. GIMPLE is C with the fun removed

{badge}

T02 showed you four representations and gave each of them a paragraph. This lesson takes the
second one and asks the question people actually have about it, which is why it looks so
disappointing.

{term("GIMPLE")} is what you get when someone takes C and removes everything that made
writing it enjoyable. No nested expressions. No `&&`. No `?:`. One operation per line, and a
variable you never declared holding every intermediate result. The first time you read a
`tree-optimized` dump it looks like the compiler has been through your code and made it
worse.

It has, and that is the entire point. This lesson is about what was taken away, what it
bought, and the single rule that explains every bit of it.

You need a browser. There is no compiler here and no network.

**What you come away with**

- The one rule, which is that an operand has to be a value and a value is a variable or a
  constant, and nothing else
- Being able to look at a C expression and say how many GIMPLE statements it will become
  before you run anything
- Knowing where the {term("temporary", "temporaries")} called `_1` and `_2` come from, and
  why `D.4635` is a different kind of name from either of them
- Having watched `&&` and `?:` turn into branches, which is the moment they stop being
  expressions
""")

lesson.setup()

lesson.md("""
## The bench

Seven functions, one expression each, all with the same signature so the only thing that
differs between them is the shape of the expression. They get less reasonable as you go down.

This is not L1. L1 is a loop, and a loop is about control flow, which is T04 and later. Here
there is no loop anywhere, because the subject is what happens to an expression and a loop
would be a second thing to think about.
""")

lesson.code("""
from gxray import gimple

record = gxray.corpus_store.load("t03-bench")
print(record.source)
""")

lesson.md("""
The recording was made with `-O0` and `-fdump-tree-gimple`. Both halves matter.

`-O0` means nothing runs after gimplification, so nothing in the dump is an optimization. If
you take this dump at `-O2` instead, several of these functions come back as one instruction
and you learn nothing about gimplification, because you are looking at the work of two
hundred passes that ran afterwards.

`tree-gimple` is the earliest dump GCC will give you. It is the first moment the function
exists as GIMPLE at all, which is a few microseconds after it stopped being a parse tree.

## Predict first

Before you look at anything. Here is the second function on the bench:

```c
int nested (int a, int b, int c)
{
  return (a + b) * (a - c);
}
```

One line of C, three operators, one return. How many GIMPLE statements does GCC make of it?
Commit to a number, then open the answer.
""")

lesson.code("""
from IPython.display import HTML, display

from gxwidgets import Option, PredictGate

gate = PredictGate(
    "How many GIMPLE statements does `return (a + b) * (a - c);` become?",
    [
        Option(
            "One, it is one statement",
            why="It is one statement in C. GIMPLE counts operations, not semicolons.",
        ),
        Option(
            "Two, the multiply and the return",
            why="Close, but the two additions cannot sit inside the multiply.",
        ),
        Option("Four", correct=True),
        Option(
            "Seven, one per token",
            why="Only operations get a statement. a, b and c are already values.",
        ),
    ],
    answer=(
        "Four. One for each of the three operators, and one for the return. The two "
        "subexpressions have to be computed into somewhere before the multiply can use "
        "them, and that somewhere is a temporary."
    ),
)
display(HTML(gate.render()))
""")

lesson.md("""
## What it actually did

Here is the same function at both levels. GENERIC first, which is the parse tree with the
source structure still in it, then GIMPLE.
""")

lesson.code("""
from gxray import locs

generic = record.dump_texts["tree-original"]
bench = gimple.parse(record.dump_texts["tree-gimple"])


def generic_body(name):
    \"\"\"The code lines of the GENERIC dump belonging to one function, with the locations
    taken off, because at this level there is a location on nearly every node and they come
    to three times the width of the code.\"\"\"
    wanted, out = False, []
    for raw in generic.splitlines():
        if raw.startswith(";; Function "):
            wanted = raw.split()[2] == name
            continue
        line = locs.strip_locs(raw).strip()
        if wanted and line and line not in ("{", "}") and not line.startswith(";;"):
            out.append(line)
    return out


for line in generic_body("nested"):
    print("GENERIC  ", line)
print()
for stmt in bench.functions["nested"].code:
    print("GIMPLE   ", stmt.text)
""")

lesson.md(f"""
GENERIC kept the source. One `return`, with the whole expression nested inside it exactly
where you wrote it, because GENERIC's job is to hold what the front end parsed and nothing
more.

GIMPLE took the tree apart. `_1` and `_2` did not exist a moment ago. `D.4635` did not exist
either, and it is a different kind of thing from the other two: it is the slot the function
returns through, which the front end makes for every function that returns anything, whereas
`_1` and `_2` are the ones gimplification invented on the spot because it had nowhere else to
put a value.

The rule it followed, and it is the only rule, is at
{cite("gcc/gimple-expr.cc:836@releases/gcc-16.2.0")}: an operand has to be a **value**, which
means a variable or a constant. Not an expression. When gimplification finds an expression
where a value is wanted, it makes a temporary, assigns the expression to it, puts that
assignment in front, and uses the temporary instead. That is
{cite("gcc/gimplify.cc:683@releases/gcc-16.2.0")}, and it is about fifty lines long.

Everything else follows. Apply that rule to every operand of every node, from the bottom of
the tree upwards, and a nested expression comes out as a list.

The picture of it, on this exact expression, is in
[`diagrams/one-rule.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t03-gimple-is-c-with-the-fun-removed/diagrams/one-rule.excalidraw).
Open it at excalidraw.com and you can move things around. It is the only picture in this
lesson that is not read off a recorded run, because it is about the rule rather than about
one function.
""")

lesson.md(f"""
Which gives the property the whole middle end is built on.
{claim("no statement anywhere in the gimplified bench has more than one operator on it, and the GENERIC it came from has a line with seven")}.
""")

lesson.code("""
import re

# Operators as the dump prints them, with a space on each side, so the minus sign in a
# negative constant and the star in a pointer type cannot be mistaken for one.
OPERATOR = re.compile(r" (<<|>>|<=|>=|==|!=|&&|\\|\\||[-+*/%&|^<>]) ")

worst_gimple = max(
    len(OPERATOR.findall(stmt.text)) for fn in bench.functions.values() for stmt in fn.code
)
worst_generic = max(
    len(OPERATOR.findall(line)) for name in bench.functions for line in generic_body(name)
)
print("most operators on one line of GENERIC:", worst_generic)
print("most operators on one line of GIMPLE: ", worst_gimple)
""")

lesson.md(f"""
That is {term("three address form")}. At most one operation, at most a couple of operands,
and every operand already a value. A pass that wants to know what a statement does reads one
operator, not a tree of unknown depth.

## How many temporaries to expect

The count is not a mystery and it is not proportional to how long the line is. It is the
number of interior nodes in the expression tree, because that is how many places the rule
fires.

{claim("the bench is seven functions of one line each, and gimplification turns them into between two and eleven statements")}.
""")

lesson.code("""
print(f"{'function':14} {'stmts':>5} {'temps':>5}  operators, in the order GCC emitted them")
for name, fn in bench.functions.items():
    temps = {str(s.lhs) for s in fn.code if str(s.lhs).startswith("_")}
    ops = [s.operator for s in fn.code if s.operator]
    print(f"{name:14} {len(fn.code):>5} {len(temps):>5}  {', '.join(ops) or 'none at all'}")
""")

lesson.md("""
Read `deeper` first, because it is the clean case. Its expression is
`((a + b) * (a - c)) + ((b + c) * (b - a))`, which has seven operators, and it came out as
seven operations plus a return. Six temporaries, one for every operator except the last,
which had somewhere to go already.

The order is worth looking at. `+, -, *, +, -, *, +` is a walk of the tree that visits both
children before their parent, which it has to be: you cannot write a statement that uses a
value that does not exist yet. So the first line of GIMPLE corresponds to the deepest
leftmost operator in the source, not to the one you read first.

`flat` is the only function on the bench where C and GIMPLE agree about what a statement is,
and it agrees because there was only ever one operation in it.

`compound` is the interesting small one. `(a += b) * c` is one C expression doing two things,
a write to `a` and a multiplication using the result, and GIMPLE will not do two things at
once, so it becomes two statements and no temporary at all. The temporary would have been
somewhere to keep the result of the `+`, and there was already somewhere: `a` itself.

## A call is an operation too
""")

lesson.code("""
for stmt in bench.functions["calls"].code:
    print(f"{stmt.kind:8} {stmt.text}")
""")

lesson.md("""
`g (a + b) + h (b + c)` has two calls and three additions in it, and every one of them got
its own line.

The arguments went first, which is the same rule again: an argument is an operand, so it has
to be a value, so `a + b` had to be computed into `_1` before `g` could be handed it. Then
each call landed in its own temporary, because a call is an operation and its result is a
value that has to live somewhere before the outer `+` can add it.

Notice what is not here. There is nothing in the dump about which call happens first. C does
not say, and gimplification does not decide, it just writes them down in an order and the
order it happened to pick is not a promise. If you have ever wondered where the freedom in
unspecified evaluation order physically lives in a compiler, it is here, in a function
choosing which subtree to walk first.

## Where the operators went
""")

lesson.md(f"""
Two of the seven functions came back with almost no operators at all, and they are the two
whose C used `&&` and `?:`.
{claim("neither the && nor the ?: leaves an operator behind, and what stands in for both of them is a condition, some labels, some gotos, and one variable written on two different paths")}.
""")

lesson.code("""
for name in ("shortcircuit", "ternary"):
    fn = bench.functions[name]
    print(f"{name}: {fn.signature}")
    for stmt in fn.code:
        print(f"  {stmt.kind:8} {stmt.text}")
    print()
""")

lesson.md(f"""
`a > 0 && b > 0` became two conditional jumps, three labels, two assignments of a literal,
and one unconditional jump. There is no `&&` and there is not even a `>` left on a right hand
side, because both comparisons went into `if` statements instead.

That is not GIMPLE being awkward. It is GIMPLE being honest. `&&` was never an operator in
the sense `+` is one: it is short circuiting, which means the right operand is only evaluated
sometimes, which means it is a branch. C writes a branch in the middle of an expression and
calls it an operator. The compiler cannot keep pretending, so this is where the pretence
ends. The function that ends it is
{cite("gcc/gimplify.cc:5221@releases/gcc-16.2.0")}, and its name says what it thinks the
construct really was.

`?:` gets the same treatment from {cite("gcc/gimplify.cc:5571@releases/gcc-16.2.0")}, with one
extra thing to arrange: it has a value, and the value comes from one of two paths. The answer
is `iftmp.0` in the first function and the return slot itself in the second, a single
variable written on both sides of the branch and read after they join. Hold on to that shape.
When T05 gets to SSA, a variable written on two paths and read after the join is precisely
the thing a `PHI` exists for, and you are looking at the reason `PHI` had to be invented.

## Why boring is the point

Four things were taken away: nesting, more than one operation per statement, control flow
inside expressions, and any operand that is not a value. What was bought is worth listing,
because every one of these is a thing a real GCC pass does every day.

**A pass can be written.** {cite("gcc/gimple.def:46@releases/gcc-16.2.0")} lists 47 statement
codes and that is the entire language. A pass switches on the code, looks at one operator and
two operands, and is done. Against GENERIC the same pass would have to recurse through
arbitrary nesting and handle 245 node codes, most of which belong to a language it has never
heard of.

**Every value has one name.** `_1` is written in exactly one place. That is not SSA yet, but
it is most of the way there, and it is why the SSA construction pass in T05 has so little to
do: gimplification already gave nearly every intermediate value a name of its own.

**Control flow can be a graph.** Once every branch is a `goto` and a label rather than an
expression, the statements can be cut into blocks at the labels and jumps and joined by
edges. That is the next pass after this dump, and it is why this one has no basic blocks in
it.

**Locations survive.** Every statement here kept the column it came from, which is what T02's
ladder was reading. Flattening an expression into six statements does not lose where they
came from, and that is the only reason a debugger can still find your code afterwards.

{
    claim(
        "one function does nearly all of this, and the switch at the middle of it has over a "
        "hundred cases, one per kind of tree node it might have to take apart",
        unobservable="the shape of gimplify_expr is a fact about the source tree, and this "
        "notebook has no copy of it. The citation is checked against the pinned tree on "
        "every push instead.",
    )
}. It is {cite("gcc/gimplify.cc:20296@releases/gcc-16.2.0")}, it runs for about thirteen
hundred lines, and it is the closest thing GCC has to a definition of what the C family
actually means.

## There are no basic blocks here yet

One last thing about this dump specifically, because it will confuse you later otherwise.
""")

lesson.code("""
fn = bench.functions["shortcircuit"]
print("pre_cfg:", fn.pre_cfg)
print("blocks: ", list(fn.blocks))
print("how it prints:", fn)
""")

lesson.md("""
Every other GIMPLE dump in this course has `<bb 2>` headers in it and a real control flow
graph behind them. This one does not, and it is the only one that does not.

Gimplification and CFG construction are two different passes. The first turns expressions
into statements, which is what you have been reading. The second reads those statements,
notices the labels and the gotos, cuts the list into blocks and works out the edges. Between
them the function is a flat list with jumps in it, which is exactly what you would get if you
wrote assembly by hand, and it is what this dump caught.

That is why the branches above are labels and `goto` rather than edges, and why drawing a
graph of this dump would produce nothing. There is no graph yet. T04 is about the pass list
this one sits at the front of, and the CFG lesson later in M2 is about the pass that comes
next.

## Boss fight

Hand gimplify this, on paper, before running anything:

```c
int deeper (int a, int b, int c)
{
  return ((a + b) * (a - c)) + ((b + c) * (b - a));
}
```

Then answer three things about what you wrote.

1. The operators, in the order your statements compute them, as `+,-,*,+,-,*,+`
2. How many temporaries you needed, counting only the invented ones and not the return slot
3. Which function on the bench GCC gave the most statements to

Check yourself:

```text
python lessons/t03-gimple-is-c-with-the-fun-removed/grade.py
```

or `just grade t03-gimple-is-c-with-the-fun-removed`. It takes the answers on the command
line too, so `--ops "+,-,*,+,-,*,+" --temps 6 --most shortcircuit` is a complete submission.
Keep the quotes around the operators or your shell will try to expand the `*` into a list of
files. Every answer is read off the same recorded dump the lesson used.

If your operator order differs from GCC's, look at whether you went down the left side of the
tree first. GCC did.

## What to read next

T04 is the pass list, all 395 of them, and the first item on it is the one that produced the
dump you have been reading.

T05 is SSA, and it will make more sense now, because you have already seen gimplification do
most of the work and leave exactly one problem behind.

T07 is expand, which does to GIMPLE what gimplification did to GENERIC, one level further
down and with a machine to answer to.
""")

raise SystemExit(lesson.save())
