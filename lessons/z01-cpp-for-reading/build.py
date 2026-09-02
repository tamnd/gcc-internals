"""Z01. C++ for people who will only ever read it.

The first lesson in the book and the only one that is not about a compilation. Every other
lesson reads what GCC produced. This one reads what GCC is made of, which is a different
skill and the one that blocks everybody first.

The claim it argues is narrow and worth being narrow about. GCC's C++ is not hard. It is
unfamiliar, which feels the same from the outside and is fixed by a completely different
thing: not by learning more C++, but by learning seventeen constructs that GCC uses everywhere
and almost nobody else uses at all. A reader who knows those seventeen can read any file in the
tree slowly. A reader who knows modern C++ and not those seventeen cannot read any of it.

So the lesson is a vocabulary list with evidence. Every snippet is real, cut from the pinned
tree at `releases/gcc-16.2.0`, committed to `corpora/source/z01.json` and pinned by refcheck
from the other side. Nothing here is a paraphrase and nothing was tidied up for the page.

The T0 exercise is forty lines of `tree-ssa-ccp.cc` with every construct marked, which is the
lesson's real test: not can you define `dyn_cast`, but can you get to the end of a page of GCC
without stopping.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "z01-cpp-for-reading",
    "z01",
    title="C++ for people who will only ever read it",
    milestone="M1",
    summary=(
        "The seventeen constructs that make GCC's source look unreadable, each one in real "
        "code from the pinned tree, and forty lines of a real pass read line by line with "
        "every one of them marked"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# Z01. C++ for people who will only ever read it

{badge}

You opened a file in GCC and it did not look like C++.

```c
if (gassign *assign = dyn_cast <gassign *> (stmt))
  {{
    tree lhs = gimple_assign_lhs (assign);
    if (TREE_CODE (lhs) == SSA_NAME)
      FOR_EACH_IMM_USE_FAST (use_p, iter, lhs)
        ...
```

Five lines, and there is a template that is not a container, a macro that is a loop, a macro
that is a field access, a function that looks like a macro, and a type called `tree` that is
a pointer to a union. None of it is advanced C++. All of it is unfamiliar, and unfamiliar
reads exactly like hard until somebody tells you what it is.

That is the whole of this lesson. Not more C++. Seventeen specific constructs that GCC uses on
almost every page and that you will not have met anywhere else.

Everything here is real. Every snippet was cut out of the pinned GCC 16.2.0 tree by
`record.py`, with the file and the line numbers attached, so you can open any of them on
GitHub and see the same thing. Nothing was simplified for the page.

You need a browser. There is no compiler here, no network, and no GCC checkout.

**What you come away with**

- Why `tree` is one type for four hundred different things, and what that costs to read
- The three casts from `is-a.h`, and which one you can test
- The macros that are loops, and why they are macros
- What `GTY(())` is doing on almost every declaration in the tree
- Forty lines of a real optimization pass, read line by line
- Twelve lines to name, graded, with the marking derived from the source rather than typed
""")

lesson.setup()

lesson.md("""
## The seventeen

Here is the list, up front, so you can see how short it is. The rest of the lesson is these
in real code.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("z01")

print(f"{len(cuts)} snippets, {cuts.lines()} lines, from {len(cuts.files)} files")
print(f"all of it cut from {cuts.tag}")
print()
print(f"{'key':<12}{'construct':<24}what it is")
for key, name, _, about in source.IDIOMS:
    print(f"{key:<12}{name:<24}{about}")
""")

lesson.md(f"""
Seventeen. Not seventeen chapters of a C++ book, seventeen things to recognize. Learning them is
an afternoon and it is the difference between a file you can read and a file you cannot.

{claim("every one of the seventeen constructs appears in the snippets this lesson reads")}.
""")

lesson.code("""
seen = {}
for snippet in cuts:
    for line, keys in source.annotate(snippet).items():
        for key in keys:
            seen.setdefault(key, []).append(f"{snippet.path}:{line}")

print(f"{'key':<12}{'lines':>6}   first one")
for key in source.KEYS:
    where = seen.get(key, [])
    print(f"{key:<12}{len(where):>6}   {where[0] if where else 'nowhere'}")

assert set(seen) == set(source.KEYS), "a construct in the list is in none of the snippets"
""")

lesson.md(f"""
## A tree is a tagged union

The first thing to understand about GCC is that `tree` is one type. Not a base class with four
hundred subclasses. One pointer, to one union, and which arm of the union is live is decided
by a small integer inside it.

{cite("gcc/tree-core.h:2182@releases/gcc-16.2.0")} is that union.
""")

lesson.code("""
union_ = cuts["tree-union"]
print(union_.about)
print(f"{union_.span}  ({union_.citation})")
print()
print(union_.numbered())
""")

lesson.md(f"""
Every arm is a `struct tree_something`, and every arm carries a `GTY ((tag ("TS_SOMETHING")))`.
The tag is not for the compiler. It is for {term("gengtype")}, which reads these annotations
and writes the garbage collector's marking code, and the `desc` at the top says which function
to call to find out which arm is live.

The union has more arms than fit on a page. This is the first fourteen.

{claim("the tag that decides which arm of the union is live is a sixteen bit field")}.
""")

lesson.code("""
base = cuts["tree-base"]
print(base.about)
print(f"{base.span}  ({base.citation})")
print()
print(base.numbered({k: ", ".join(v) for k, v in source.annotate(base).items()}))
""")

lesson.md(f"""
Look at what that costs. `code` is sixteen bits and every one of the sixteen flags after it is
one bit, packed by hand into the first word of every node in the compiler. GCC allocates tens
of millions of these on a large translation unit, so a byte here is megabytes there, and the
{term("garbage collector", "collector")} has to walk all of them.

That packing is why you never touch a field directly. The union is private in practice and the
macros are the API, which is the second construct on the list.

```c
TREE_CODE (t)          // which arm of the union is live
TREE_TYPE (t)          // the type of this expression
DECL_NAME (t)          // the identifier of this declaration
SSA_NAME_DEF_STMT (t)  // the statement that defined this SSA name
```

They are shouty because they are macros, and they are macros because they predate GCC being
C++ and because most of them are defined twice. {cite("gcc/tree.h:438@releases/gcc-16.2.0")} is `TREE_TYPE` in a
checking build:

```c
#define TREE_TYPE(NODE) \\
(CONTAINS_STRUCT_CHECK (NODE, TS_TYPED)->typed.type)
```

and {cite("gcc/tree.h:513@releases/gcc-16.2.0")} is the same macro in a release build:

```c
#define TREE_TYPE(NODE) ((NODE)->typed.type)
```

Same name, same call site, and in one build it dies with a file and a line number when the
node has no type and in the other it reads a field off the wrong arm of the union. The switch
between them is `ENABLE_TREE_CHECKING` at {cite("gcc/tree.h:330@releases/gcc-16.2.0")}, and it is why
everybody who works on GCC uses a {term("checking build")}.

## GIMPLE went the other way

GIMPLE is younger than `tree` and it made the opposite choice: a real base class, real
subclasses, and single inheritance all the way down.
""")

lesson.code("""
head = cuts["gimple-base"]
print(head.about)
print(f"{head.span}  ({head.citation})")
print()
print(head.numbered({k: ", ".join(v) for k, v in source.annotate(head).items()}))
""")

lesson.md(f"""
Same idea as `tree_base` and a different shape: `code` is eight bits here, then flags, and it
is a `struct` with a `GTY` on it rather than a union arm. {cite("gcc/gimple.h:220@releases/gcc-16.2.0")}.

Now the part that surprises people. Here is `gcond`, the class for a conditional jump.
""")

lesson.code("""
sub = cuts["gimple-subclass"]
print(sub.about)
print(f"{sub.span}  ({sub.citation})")
print()
print(sub.numbered())
""")

lesson.md(f"""
No fields. The comment says so. The whole purpose of the class is to be a different type from
`gimple *`, so that a function that only makes sense on a conditional can say so in its
signature and the compiler will hold you to it.

Which raises the question of how you get one, because the thing you have is a `gimple *`.

{claim("a GIMPLE subclass tells is-a.h what it is with a three line function and nothing else")}.
""")

lesson.code("""
helper = cuts["is-a-helper"]
print(helper.about)
print(f"{helper.span}  ({helper.citation})")
print()
print(helper.numbered({k: ", ".join(v) for k, v in source.annotate(helper).items()}))
""")

lesson.md(f"""
That is the entire mechanism. One specialization of `is_a_helper` per statement kind, whose
`test` reads the tag. The doubled `template <>` is not a typo, it is a member specialization
of a class template, which needs one empty list for the class and one for the member. No virtual functions, no RTTI, no `dynamic_cast`. GCC compiles with
`-fno-rtti`, so the language's own downcast is not available, and this is what replaced it.

## The three casts

{cite("gcc/is-a.h:224@releases/gcc-16.2.0")}, and this is the one page of GCC everybody should read early.
""")

lesson.code("""
for name in ("is_a", "as_a", "dyn_cast"):
    cut = cuts[name]
    print(f"### {name}   {cut.about}")
    print(f"{cut.span}  ({cut.citation})")
    print(cut.numbered({k: ", ".join(v) for k, v in source.annotate(cut).items()}))
    print()
""")

lesson.md(f"""
Three functions, ten lines each, and the difference between them is the whole of the idiom.

| | what it does | when it is wrong |
|---|---|---|
| `is_a <T> (p)` | returns true or false | never, it is only a question |
| `as_a <T> (p)` | converts, asserting | undefined in a release build |
| `dyn_cast <T> (p)` | converts, or returns null | never, but you have to check |

The trap is in the middle row. `as_a` calls `gcc_checking_assert`, and a checking assert is
compiled out of a release build. So `as_a <gassign *> (stmt)` on a statement that is not an
assignment is caught immediately in a development build and is silently a wrong pointer in a
release one. When you read GCC and see `as_a`, the author is telling you they already know
what kind of statement it is. When you see `dyn_cast`, they are asking.

{claim("as_a checks with an assert that a release build removes, and dyn_cast checks always")}.
""")

lesson.code("""
inside = {name: source.code_only(cuts[name].lines) for name in ("as_a", "dyn_cast")}

for name, lines in inside.items():
    checks = [text.strip() for text in lines if "assert" in text or "is_a <T>" in text]
    print(f"{name:<10}{len(checks)} check(s)")
    for text in checks:
        print(f"          {text}")

assert any("gcc_checking_assert" in t for t in inside["as_a"])
assert not any("assert" in t for t in inside["dyn_cast"])
""")

lesson.md(f"""
## The macros that are loops

GCC is older than the range based for loop by about twenty years, and it walks the same three
or four structures constantly, so it grew macros that are loops. There are dozens. They all
look the same and once you have seen one you have seen them all.

{cite("gcc/basic-block.h:212@releases/gcc-16.2.0")}.
""")

lesson.code("""
loop = cuts["for-each-bb"]
print(loop.about)
print(f"{loop.span}  ({loop.citation})")
print()
print(loop.numbered({k: ", ".join(v) for k, v in source.annotate(loop).items()}))
""")

lesson.md(f"""
`FOR_EACH_BB_FN (bb, cfun)` expands to a `for` over the block list of `cfun`, which is the
{term("current function")}. It skips the entry and exit blocks, because those are markers
rather than code, and that is a fact about the macro you would never guess from the call.

The other one you will read constantly is the statement iterator, which is a real object
rather than a macro because a statement walk usually wants to delete things as it goes.
""")

lesson.code("""
walk = cuts["ccp-walk"]
print(walk.about)
print(f"{walk.span}  ({walk.citation})")
print()
print(walk.numbered({k: ", ".join(v) for k, v in source.annotate(walk).items()}))
""")

lesson.md(f"""
Two nested walks, blocks then statements, and this shape is most of what a GIMPLE pass does.
`gsi_start_bb`, `gsi_end_p`, `gsi_next`, `gsi_stmt`. Learn those four and you can read the
skeleton of any tree pass in the compiler.

## Why not std::vector

Because the allocator has to be the garbage collector.

{cite("gcc/vec.h:72@releases/gcc-16.2.0")} spells it out, and it is worth reading because the reasoning applies to
every container in the tree.
""")

lesson.code("""
why = cuts["vec-strategies"]
print(why.about)
print(f"{why.span}  ({why.citation})")
print()
print(why.numbered())
""")

lesson.code("""
decl = cuts["vec-declaration"]
print(decl.about)
print(f"{decl.span}  ({decl.citation})")
print()
print(decl.numbered({k: ", ".join(v) for k, v in source.annotate(decl).items()}))
""")

lesson.md(f"""
Three parameters: the element type, the allocation strategy, and the physical layout. The
primary template has an empty body, because every real vector is one of the specializations,
and that is why jumping to the definition of `vec` lands you on nothing.

`hash_map` is the same story.
""")

lesson.code("""
hm = cuts["hash-map"]
print(hm.about)
print(f"{hm.span}  ({hm.citation})")
print()
print(hm.numbered({k: ", ".join(v) for k, v in source.annotate(hm).items()}))
""")

lesson.md(f"""
`GTY((user))` is the interesting part. It tells {term("gengtype")} not to generate the marking
code for this type, because somebody wrote it by hand. When you see `GTY(())` with nothing in
it, gengtype works the type out. When you see arguments, somebody is telling it something it
could not have known.

## The number that might not be a number

{cite("gcc/poly-int.h:374@releases/gcc-16.2.0")}. This is the one that catches people who learned GCC before 2018.
""")

lesson.code("""
poly = cuts["poly-int"]
print(poly.about)
print(f"{poly.span}  ({poly.citation})")
print()
print(poly.numbered({k: ", ".join(v) for k, v in source.annotate(poly).items()}))
""")

lesson.md(f"""
A {term("poly_int")} is a polynomial: a constant term plus coefficients on some indeterminates. It
exists because of scalable vectors. On SVE or RVV a vector register's size is not known when
the compiler runs, so `GET_MODE_SIZE (mode)` cannot return an integer, and it returns one of
these instead.

The consequence shows up in the comparisons. You cannot write `if (a == b)` on two of them,
because the answer might be maybe. So GCC has `known_eq`, `maybe_eq`, `known_lt`, `maybe_lt`
and the rest, and each one says what it does with the uncertain case. When you see
`known_eq (x, y)` the author means "definitely equal", and `maybe_ne (x, y)` means "not
provably equal", and those are different questions with different answers.

On x86 and aarch64 with fixed vectors, every `poly_int` has one coefficient and all of this
compiles to the obvious integer comparison. The cost is only in reading it.

## The four includes

Every `.cc` file in `gcc/` starts the same way and it is not a style preference.
""")

lesson.code("""
inc = cuts["includes"]
print(inc.about)
print(f"{inc.span}  ({inc.citation})")
print()
print(inc.numbered({k: ", ".join(v) for k, v in source.annotate(inc).items()}))
""")

lesson.md(f"""
`config.h` first, always, because it defines the autoconf macros everything else tests.
`system.h` second, because it wraps the host's headers and then poisons a list of functions
GCC refuses to use, so any header included before it can get away with calling `malloc` and
any header after it cannot. `coretypes.h` third, for the forward declarations that let the
rest of the headers refer to each other. A file that needs the target macros puts `tm.h`
fourth, and this one does not, so its fourth include is an ordinary one.

Get the order wrong and the failure is a wall of macro redefinition errors a thousand lines
deep with nothing in it that names the file you edited. That is worth knowing before it
happens to you rather than after.

## Forty lines of a real pass

Everything above is vocabulary. This is the test.

{cite("gcc/tree-ssa-ccp.cc:280@releases/gcc-16.2.0")} is `get_default_value`, from conditional constant propagation.
It is not a simple function and it was not chosen for being one. It is a normal page of GCC.

Read it once with the marks, then scroll up and read it again without them.

{claim("twelve of the forty lines of get_default_value carry a construct, of five kinds")}.
""")

lesson.code("""
read = cuts["ccp-read"]
marks = source.annotate(read)

print(read.about)
print(f"{read.span}  ({read.citation})")
print()
print(read.numbered({k: ", ".join(v) for k, v in marks.items()}))
print()

kinds = sorted({key for keys in marks.values() for key in keys}, key=source.KEYS.index)
print(f"{len(marks)} of {len(read)} lines have a construct on them, {len(kinds)} kinds:")
for key in kinds:
    print(f"  {key:<12}{source.named(key):<24}{source.explain(key)}")
""")

lesson.md("""
Now the same forty lines with nothing marked. This is the version you have to be able to get
through, and the honest test is whether you reach the bottom without stopping.
""")

lesson.code("""
print(read.numbered())
""")

lesson.md(f"""
A few things worth saying about what is in there.

`SSA_NAME_DEF_STMT (var)` is a tree macro that gives you the statement that defined an
{term("SSA")} name. Every SSA name has exactly one, which is the whole point of SSA, and for a
parameter or an uninitialized variable it is a `GIMPLE_NOP`. That is what `gimple_nop_p (stmt)`
on the next line is asking.

{term("wide_int")} and `widest_int` are integers as wide as the target needs. GCC compiles for targets
with 128 bit integers on hosts with 64 bit ones, so a compiler that used `long` for target
arithmetic would be wrong on those targets, and the `wi::` namespace is where the operations
on them live.

`gcc_assert` on line 316 is on in a release build. `gcc_checking_assert`, which `as_a` uses, is
not. Two spellings, two very different things.

And the shape of the function is a lattice: `UNINITIALIZED`, `UNDEFINED`, `CONSTANT`,
`VARYING`. That is CCP and it gets a lesson of its own much later. Here it is only an example
of a page you can now get to the end of.

## Where a dump line comes from

One more, because you have been reading dumps for ten lessons and it is worth seeing the other
side of them.

{cite("gcc/tree-ssa-ccp.cc:566@releases/gcc-16.2.0")}.
""")

lesson.code("""
dmp = cuts["ccp-dump"]
print(dmp.about)
print(f"{dmp.span}  ({dmp.citation})")
print()
print(dmp.numbered({k: ", ".join(v) for k, v in source.annotate(dmp).items()}))
""")

lesson.md(f"""
`dump_file` is null unless somebody asked for a dump, so the guard is not politeness, it is
required. `dump_flags & TDF_DETAILS` is the `-details` modifier you have been typing since
T04. That is where it is read.

And the furniture every pass carries, which you met in T04 from the outside and can now read
from the inside.
""")

lesson.code("""
boiler = cuts["ccp-pass"]
print(boiler.about)
print(f"{boiler.span}  ({boiler.citation})")
print()
print(boiler.numbered({k: ", ".join(v) for k, v in source.annotate(boiler).items()}))
""")

lesson.md(f"""
`"ccp"` on line 3045 is the string that names the dump file. `PROP_cfg | PROP_ssa` is the pass
saying it needs a control flow graph and SSA form before it will run, and the pass manager
checks it. `TODO_update_address_taken` is what it asks to be done afterwards. All of that is
`BP-PIPELINE` section 2, and now you can see where the fields actually live.

## The picture

The seventeen constructs on one sheet, grouped by what they are for, is in
[`diagrams/reading-gcc.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/z01-cpp-for-reading/diagrams/reading-gcc.excalidraw).
Print it and keep it next to you for the first week. That is what it is for.

## Six questions

Every one of these has an answer that sounds right to somebody who knows C++ and is wrong
about GCC. Commit before you open the reveal.
""")

lesson.code("""
from gxwidgets import PredictGate

QUESTIONS = [
    (
        "You have a `gimple *stmt` and you want to know if it is an assignment. Which cast?",
        [
            ("dyn_cast, and check the result for null", ""),
            (
                "as_a, it is the standard one",
                "as_a asserts that it already is one. If you are asking, you do not know, "
                "and in a release build the assert is gone and you get a wrong pointer.",
            ),
            (
                "dynamic_cast, this is C++",
                "GCC compiles with -fno-rtti, so dynamic_cast is not available. is-a.h "
                "exists because of that.",
            ),
        ],
        "dyn_cast. It is the only one of the three that answers the question and converts.",
    ),
    (
        "What does `GTY(())` on a struct do to the code the compiler generates?",
        [
            ("Nothing at all, gengtype reads it and GCC's own compiler ignores it", ""),
            (
                "Adds a header word so the collector can find the type",
                "The tag is in the type, not added by GTY. GTY is a marker that a separate "
                "program reads out of the source text.",
            ),
            (
                "Registers the type with the garbage collector at startup",
                "Nothing happens at run time. gengtype runs during the build and writes a "
                "gtype-desc.cc full of marking functions.",
            ),
        ],
        "Nothing. It is a note to gengtype, which is a separate program that runs at build time.",
    ),
    (
        "Why is `tree` one type rather than a class hierarchy, when `gimple` is a hierarchy?",
        [
            ("Age. tree predates GCC being C++ at all, and it was never converted", ""),
            (
                "Trees are polymorphic and statements are not",
                "It is the other way around if anything. A tree is four hundred different "
                "things behind one pointer, which is more polymorphism, not less.",
            ),
            (
                "Performance, a virtual call per node would be too slow",
                "Neither one has virtual functions. gimple's subclasses have no vtable, "
                "which is why is-a.h has to read the tag by hand.",
            ),
        ],
        "Age. tree is from 1987 and GIMPLE's class hierarchy landed in 2013.",
    ),
    (
        "`GET_MODE_SIZE (mode)` returns a poly_int. Why can it not return an integer?",
        [
            ("Because on SVE and RVV the vector register size is unknown at compile time", ""),
            (
                "Because a mode can be bigger than a host integer",
                "That is what wide_int is for, and it is a different problem. A mode size "
                "fits in a machine word on every target.",
            ),
            (
                "Because sizes are in bits on some targets and bytes on others",
                "Sizes are in bytes everywhere. The uncertainty is about the number, "
                "not the unit it is counted in.",
            ),
        ],
        "Scalable vectors. The size is a polynomial in a number the hardware picks at run time.",
    ),
    (
        'What breaks if you put `#include "tree.h"` before `#include "system.h"`?',
        [
            ("A wall of macro errors, because system.h poisons functions after it runs", ""),
            (
                "Nothing, include order is a style rule",
                "It is enforced by the preprocessor. system.h wraps the host headers and "
                "then poisons a list of functions, so what comes before it and what comes "
                "after it are compiled under different rules.",
            ),
            (
                "A link error, because the symbols come out in the wrong order",
                "It fails at the preprocessing stage, long before anything is linked.",
            ),
        ],
        "It fails to compile, with errors that name none of the lines you touched.",
    ),
    (
        "`FOR_EACH_BB_FN (bb, cfun)` iterates over what, exactly?",
        [
            ("Every block of cfun except the entry and the exit block", ""),
            (
                "Every block of cfun, including entry and exit",
                "Read the macro. It starts at entry->next_bb and stops at exit, so both "
                "markers are outside the loop.",
            ),
            (
                "Every block, in reverse post order",
                "It walks the block list in whatever order the list is in. If you want an "
                "order you ask for one, and there is a different function for that.",
            ),
        ],
        "The real blocks. Entry and exit are markers with no code in them and are skipped.",
    ),
]

gates = [
    PredictGate(question, options, answer=answer, id=f"z01-q{n}")
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

`gcc/is-a.h` has a long comment at the top that is better than anything written about it
since, and it is forty lines. Read it.

`gcc/vec.h` lines 34 to 130 are the design rationale for the container, and they explain more
about how GCC thinks about memory than any document in the tree.

GCC's own internals manual has a chapter on `poly_int` that is genuinely good, which is not
something you can say about every chapter of it.

## Boss fight

Twelve lines of real GCC, and for each one, name the construct.

    python lessons/z01-cpp-for-reading/grade.py

The grader picks the twelve lines out of the extract and works out the answers by reading
them, so there is no answer key anywhere in the repository and re-cutting the snippets against
a newer GCC re-derives the marking. Run it with no arguments and it asks; pass `--says` with
twelve keys separated by commas to answer in one go.

## What to read next

Z02 is the other half of being able to start: what the directories are, which files are
generated, and how to get from a pass name in a dump to the file that implements it.

After that, T01, and the compiler proper.
""")

raise SystemExit(lesson.save())
