# gcc-internals

A visual, hands on teardown of GCC 16, taught from zero, and specified precisely enough that you can write a working front end, a working back end and a working optimizer against the specifications alone.

**The book is at [tamnd.github.io/gcc-internals](https://tamnd.github.io/gcc-internals/).** The lessons, the films, the glossary and the blueprints are all there, and one page has a live Python notebook in the middle of it that sends your C to a real GCC 16 and shows you the GIMPLE that comes back.

The plan is 96 lessons in eleven parts, 58 blueprints, and three capstone tracks. Twelve lessons and nine blueprints exist so far, and the rest of the repository is the toolkit those lessons are built on plus thirteen milestones and eighteen open questions saying what is still undecided.

## The idea

GCC is the most self documenting large program most engineers will never read. It prints 236 dumps for a six line function, it names all 395 of its passes, it will draw you a control flow graph, and it will tell you why it refused to vectorize your loop. Almost none of that shows up in the material people learn from, which is mostly correct about GCC 4.4 and quietly wrong about everything since.

Both of those numbers are `gcc-16 -O2` on `corpora/programs/l1.c`, and neither was typed in by hand. `python -m gxray dumps -O2` counts the first and `python -m gxray passes --counts -O2` counts the second. A number without its compiler version, its flags and its target is not a fact about GCC, and this repository tries very hard never to print one.

So the rules are:

- **Observable first.** No claim about GCC's behaviour without a command the reader can run that shows it.
- **Nothing installed.** Every lesson has an experiment that runs in a browser, against the Compiler Explorer API, with a recorded dump corpus as the offline fallback.
- **Cited like a lawyer.** Every claim about the code points at a file, a line and a release tag, and CI fails when the cited line changes.
- **Every lesson ends with a blueprint.** A normative spec of the thing you read about, written so somebody can implement it without ever seeing the lesson.
- **Every part ends with you changing GCC and proving it.**

## Why blueprints, and why three capstones

A specification nobody has implemented from is a wish. The three tracks exist to find out where the blueprints are wrong, and they exercise almost disjoint parts of the set: a real front end for a toy language, a real port for a synthetic RISC target, and six middle end passes checked against GCC and against an SMT solver.

The headline number this project is trying to produce is not a lesson count. It is the number of blueprint bugs the implementations found.

## The lessons

Every lesson is a notebook with a Colab badge on it, so there is nothing to install and nothing to build. Part I runs entirely on the recorded dumps in `corpora/`, which are real output from a real GCC 16.2 and are committed, so a reader with a browser and no compiler gets the same output the lesson shows. Colab does have a GCC, but it is several years older than the pinned one, and a lesson that quietly showed you GCC 11's dumps while talking about GCC 16 would be worse than no lesson, so the setup cell picks a backend that matches and the banner says which one it picked and how stale it is, every time.

Nothing in a lesson is typed in by hand. A claim about what GCC does has a cell under it that produces the output, a claim about GCC's own source carries a `path:line@tag` citation that `refcheck` resolves against the pinned tree, and every claim in the course is collected into [CLAIMS.md](lessons/CLAIMS.md) with the cell that proves it.

Vocabulary works the same way. There is one definition per term in [GLOSSARY.md](GLOSSARY.md), which is also [a page in the book](https://tamnd.github.io/gcc-internals/glossary/), and a lesson links into it rather than explaining a word it explained forty lessons ago or assuming you remember one. Each entry says what the word means, then says the thing people reliably get wrong about it, and where a definition rests on something in GCC's source rather than on the literature it carries a citation like everything else here.

Lessons do not invent a fresh example each time either. There are three programs, they are fixed, and they live in `gxray.programs`. `L1` is a loop with an induction variable and an accumulator, eight lines, which is the smallest thing that makes SSA interesting and still small enough to read the whole dump. Meeting a new program and a new subsystem in the same lesson is two jobs, and the one most readers drop is the subsystem.

<!-- nbbuild:begin index -->
| | Lesson | What you come away with | Milestone | Run it |
|---|---|---|---|---|
| Z01 | [C++ for people who will only ever read it](https://github.com/tamnd/gcc-internals/blob/main/lessons/z01-cpp-for-reading/z01.ipynb) | The seventeen constructs that make GCC's source look unreadable, each one in real code from the pinned tree, and forty lines of a real pass read line by line with every one of them marked | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/z01-cpp-for-reading/z01.ipynb) |
| Z02 | [How to be lost in four and a half million lines, productively](https://github.com/tamnd/gcc-internals/blob/main/lessons/z02-where-things-are/z02.ipynb) | What every directory in the GCC tree is for, which files are written by the build rather than by a person, and the four routes from something a compiler printed back to the line of source that printed it | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/z02-where-things-are/z02.ipynb) |
| T01 | [What does gcc actually run?](https://github.com/tamnd/gcc-internals/blob/main/lessons/t01-what-gcc-runs/t01.ipynb) | That `gcc` compiles nothing and runs the programs that do, how to make it show you the list without running any of it, why `cc1` is not on your PATH, and where the flags you typed actually end up | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t01-what-gcc-runs/t01.ipynb) |
| T02 | [The five faces of one function](https://github.com/tamnd/gcc-internals/blob/main/lessons/t02-five-faces/t02.ipynb) | That there are four representations of your code inside GCC and not one, what each of them is for, how to line them up against the source, and why the line a statement came from is not always the line its instructions end up on | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t02-five-faces/t02.ipynb) |
| T03 | [GIMPLE is C with the fun removed](https://github.com/tamnd/gcc-internals/blob/main/lessons/t03-gimple-is-c-with-the-fun-removed/t03.ipynb) | Why the middle IR looks so plain, the one rule that makes it that way, where the temporaries come from and how many of them to expect, and why the two operators that cannot survive the trip are the two that were never really operators | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t03-gimple-is-c-with-the-fun-removed/t03.ipynb) |
| T04 | [Three hundred and ninety-five passes](https://github.com/tamnd/gcc-internals/blob/main/lessons/t04-three-hundred-and-ninety-five-passes/t04.ipynb) | What sits between GIMPLE and assembly, how long the list really is, why the ON and OFF that GCC prints next to each pass is not the same question as whether the pass ran, and what happens to one small function as all of it goes past | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t04-three-hundred-and-ninety-five-passes/t04.ipynb) |
| T05 | [SSA in one lesson](https://github.com/tamnd/gcc-internals/blob/main/lessons/t05-ssa-in-one-lesson/t05.ipynb) | Reading `s_1`, `s_3` and `s_8` as three versions of one variable rather than three variables, what a `PHI` is and where it has to go, what the `(D)` on `n_5(D)` is telling you, and watching SSA get taken apart again on the way to machine code | M0 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t05-ssa-in-one-lesson/t05.ipynb) |
| T06 | [What -O2 actually turns on](https://github.com/tamnd/gcc-internals/blob/main/lessons/t06-what-o2-actually-turns-on/t06.ipynb) | An optimization level is four integers and a table of a hundred and fourteen entries, why counting the switches that flipped gives the wrong answer, why -Os and -Oz look identical from outside and are not, and how few of the fifty five differences between -O1 and -O2 any one function notices | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t06-what-o2-actually-turns-on/t06.ipynb) |
| T07 | [Where GIMPLE becomes RTL](https://github.com/tamnd/gcc-internals/blob/main/lessons/t07-where-gimple-becomes-rtl/t07.ipynb) | The one node type the whole back end is built from, how to read an RTL expression out loud, why most of a function after expand is not instructions, the fiction of unlimited registers, and the same program on four machines disagreeing about every single thing you can measure | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t07-where-gimple-becomes-rtl/t07.ipynb) |
| T08 | [Registers are a lie until they are not](https://github.com/tamnd/gcc-internals/blob/main/lessons/t08-registers-are-a-lie-until-they-are-not/t08.ipynb) | The pass that makes good on the expander's promise, what an allocno is and why it is not a pseudo, live ranges and interference, the one number that decides everything, and the same five functions coming out differently on two machines because one of them has half as many registers | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| T09 | [The last mile](https://github.com/tamnd/gcc-internals/blob/main/lessons/t09-the-last-mile/t09.ipynb) | The pass that writes the assembly file, the annotation that says which machine description pattern emitted each line, why one pattern can emit five different instructions, and the thirty four lines of a forty six line file that are not instructions at all | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t09-the-last-mile/t09.ipynb) |
| T10 | [The whole map](https://github.com/tamnd/gcc-internals/blob/main/lessons/t10-the-whole-map/t10.ipynb) | One program through the whole compiler, with the pass tape and the IR ladder side by side, the fourteen stages you would draw from memory and which five of them are not passes, and one expression traced from the source line to the instruction | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t10-the-whole-map/t10.ipynb) |
| B01 | [A compiler of your own, in five minutes or four hours](https://github.com/tamnd/gcc-internals/blob/main/lessons/b01-the-build/b01.ipynb) | The three ways to have a GCC 16 and what each one costs, what the seven flags on a real configure line actually decided, which four of the fourteen front ends you get when you ask for none, and the empty file that decides whether your compiler is fast or careful | M2 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/b01-the-build/b01.ipynb) |
| B02 | [Building it three times, and the one thing that proves](https://github.com/tamnd/gcc-internals/blob/main/lessons/b02-the-bootstrap/b02.ipynb) | Why a compiler is built three times and compared twice, what that comparison can and cannot catch, the six files it is told to ignore, and a real stage comparison failure induced on purpose so you can see what it looks like before it happens to you | M2 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/b02-the-bootstrap/b02.ipynb) |
| B03 | [A debugger on the compiler, and the counter for when you cannot have one](https://github.com/tamnd/gcc-internals/blob/main/lessons/b03-the-debugger/b03.ipynb) | A real gdb session against a real cc1, recorded command by command: what the compiler's own gdbinit did before you typed anything, how to stop on one pass out of several hundred, how to read a function from a breakpoint, and how to find the exact transformation that broke your code by bisecting a debug counter instead | M2 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/b03-the-debugger/b03.ipynb) |

15 of 96 written.
<!-- nbbuild:end index -->

This table is generated from the lessons, by the same command that builds them, so it cannot list a lesson that does not exist or miss one that does. T05 is the pilot and it is deliberately in the middle of Part I rather than at the start, because everything the course promises has to be true of a hard lesson before it is worth writing the easy ones.

### How a lesson is put together

A lesson is a directory with Python in it, and the notebook is a build artifact:

```text
lessons/t05-ssa-in-one-lesson/
  build.py     the lesson itself, as prose cells and code cells
  t05.ipynb    generated, committed, never edited by hand
  diagram.py   the pictures that explain an idea rather than show a dump
  diagrams/    the Excalidraw scenes it writes
  grade.py     the boss fight, graded against a recorded dump
```

Nobody should have to edit a `.ipynb` by hand and nobody should have to review a diff of one, so `build.py` is ordinary Python that calls `lesson.md(...)` and `lesson.code(...)` in order. The generated notebook is committed as well, because a Colab badge has to point at a real file in the default branch, and CI fails when the two stop matching.

Four things an author gets from the builder, and each of them is a rule rather than a convenience:

- `lesson.cite("gcc/gimple.h:474@releases/gcc-16.2.0")` writes a link to that exact line in the pinned tree. One place in the repository knows the URL format, and `just refcheck` fails when the cited line moves.
- `lesson.term("phi node")` links into the glossary and fails the build if the term is not defined there, which is what stops a lesson from redefining a word the course already owns.
- `lesson.claim("...")` records a claim and requires the next cell to be code, before the next heading. A claim with no evidence under it cannot be committed. Three claims per lesson may be marked unobservable with a written reason, and the fourth is an error rather than a warning.
- `lesson.code(..., differs="...")` marks a cell whose output depends on which GCC produced it, and `varies=` marks one that depends on the reader's own machine. Both print a note above the cell, because the alternative is a reader deciding their setup is broken.

Outputs are never committed, so nothing in the repository proves a cell still runs. Running it is the proof:

| | What it does |
|---|---|
| `just build-lessons` | rebuild every notebook from its `build.py` |
| `just lessons` | fail if a committed notebook has drifted from its builder |
| `just lesson-diagrams` | redraw every Excalidraw scene from its `diagram.py` |
| `just films` | rebuild the six films and the page that lists them |
| `just build-claims` | rebuild the claim ledger |
| `just run-lessons` | execute every lesson top to bottom in a real kernel |
| `just run-lessons --show` | the same, and print what each cell actually printed |
| `just grade t05-ssa-in-one-lesson` | the boss fight |

The `--show` is not decoration. A cell that raises fails on its own, but a cell that prints an empty list where the prose promised four names passes quietly, and that has already happened once here. Reading the transcript is part of changing a lesson, not an optional extra.

The pictures are generated too. Most of them come from `gxmanim` and are drawn from a real dump, so they cannot disagree with the text under them. The other kind is a diagram that explains why something has to be the way it is, where there is no dump to draw from and somebody has to decide what goes where. Those are written with `tools/exdraw` and come out as real `.excalidraw` files you can open and edit, generated rather than hand drawn because Excalidraw puts a random seed in every element and a hand drawn scene has an unreviewable diff.

## Looking at a compiler

The toolkit is `gxray`. It drives GCC, parses what comes back, and answers the same questions whether the compiler is on your machine, on Compiler Explorer, or nowhere at all:

```python
import gxray

gcc = gxray.local("gcc-16")  # a compiler on this machine
gcc = gxray.ce("cg162")  # Compiler Explorer, works from a browser
gcc = gxray.corpus("l1-O2")  # recorded dumps, no network needed

r = gcc.compile(gxray.L1, "-O2", dumps=["tree-ssa"])
f = r.dump("tree-ssa").only()

f.blocks[4].phis  # the PHI nodes in <bb 4>
f.ssa_web("s_1")  # where s_1 comes from and everywhere it goes
```

The same thing from a terminal:

```console
python -m gxray banner
python -m gxray passes --counts -O2
python -m gxray passes --grep vrp -O2
python -m gxray web --name s_1 -O2
```

`just setup` puts the toolkit and the dev tools in a virtualenv, and `just check` runs everything CI runs.

## The recorded compiler and the live one have to agree

Swapping `gxray.corpus` for `gxray.ce` in a lesson's first cell is something several lessons invite you to do, so the two have to give the same answer. Every recorded compilation the book reads is registered in [`tools/tier0/experiments.toml`](tools/tier0/experiments.toml) and checked in both directions on every push.

```console
just tier0-list   # what is registered, and which lessons read it
just tier0        # run all of it, out of the corpus and out of the cache
```

There are three kinds. A **recorded** experiment came from Compiler Explorer in the first place, so the cached response and the corpus entry have to be the same text, byte for byte. A **paired** experiment was recorded against a local compiler, so what has to agree is the shape rather than the text: the functions, the block count, the PHI count, the statement count and the multiset of operators. An **offline** experiment has no online counterpart, and every one of them carries a written reason.

Twenty five experiments are registered today. Nine recorded, ten paired, six offline. The registry knows what the corpus holds and what the lessons directory holds, so a corpus entry added without an experiment fails the build rather than going quietly unchecked.

Two paired experiments compare less than the full set, and both are worth knowing about, because they are the places where the target reaches back into a pass that looks target independent. `ivopts` picks an induction variable by asking the target which addressing modes exist, so x86-64 gets `MEM[(int *)pts + ivtmp * 8]` for the loop in `nearest` and aarch64 increments the pointer instead, one PHI apart. `widening_mul` asks `optab_handler` for a multiply-accumulate, so aarch64 gets a `WIDEN_MULT_PLUS_EXPR` where x86-64 gets a multiply and an add. Neither changes the control flow, so those experiments still compare it, and narrowing a comparison without writing down why is rejected by the registry loader.

CI never touches the live API. The online half reads the responses committed under `tools/cecache/store` through a cache that raises on a miss, so a new experiment without its cache entry fails the build. Fetching is one command, `just ce-refresh`, it runs on a laptop, and what it writes goes in the pull request. Compiler Explorer is free and run by volunteers and this project does not put it in anybody's CI loop.

## How much of a dump this book can actually read

Neither dump parser throws. A GIMPLE statement the classifier does not recognise becomes an `UnparsedStmt` carrying its text, and an RTL list that does not come out as an insn is skipped, because a dump format that shifts by one field should cost one number in one lesson instead of breaking forty at once. That is also a way to be quietly wrong for a year, so the amount tolerated is counted and written down.

```console
just dumpparse         # every dump in the corpus against the baseline
just dumpparse-worst   # the dumps the parsers understand least, worst first
```

Four numbers per dump, in [`tools/dumpparse/baseline.json`](tools/dumpparse/baseline.json). How many functions came out. How many statements and insns came out. How many things the parser should have built and did not. How much input it walked past. Today that is 326 dumps, 380 functions, 19707 statements and insns, nothing unreadable, and 28450 pieces of prose walked past.

The last number is not supposed to be zero and never will be. A dump is mostly prose, and the IRA report alone is nine thousand parenthesised lines of conflict tables and register costs that are not RTL at all. What matters is that it is written down. A change in the dump format that turns real statements into prose moves that number instead of moving nothing, which is exactly the failure a parser that tolerates the unknown is otherwise built to hide.

Re-recording the baseline is `just dumpparse-record`, the diff goes in the pull request next to the change that caused it, and CI re-records it too and fails if the file moves. A number going down is as much a failure as a number going up, because a baseline nobody re-records stops meaning anything.

## Widgets that work with the power off

`gxwidgets` draws what `gxray` parsed. A widget builds its own markup in Python and the browser only attaches behaviour to it, so there is one renderer and the version you see with JavaScript blocked is the same drawing, not a placeholder.

```python
from gxwidgets import IRLadder, PassTape, PredictGate, SSAWeb

SSAWeb(f, name="s_1")  # renders itself in a notebook
SSAWeb(f, name="s_1").render()  # the same thing as standalone HTML
```

`PassTape` is one cell per pass at the chosen optimization level, 281 of them at `-O2`, with the handful that actually changed the IR marked. `IRLadder` takes one line of C and shows what it became at all four levels at once. `SSAWeb` follows one name from its definition to every use. `PredictGate` makes the reader commit to an answer before it shows one. Every role carries a glyph and a border as well as a colour, every drawing says in words what it shows, and the colours come from `gxmanim/palette.py` so a still from an animation matches a live widget.

## One line of C, all the way down

The only thing that survives from your source to the assembly is the source location, so that is what the levels are joined on. `gxray.locs` reads the three spellings GCC uses for it, one in the tree dumps, one in the RTL dumps and one in the `.loc` directives in the assembly, and lines them up per source line:

```python
import gxray
from gxray import locs

r = gxray.corpus("l1-O2").compile(gxray.L1, "-O2", "-g")
lad = locs.ladder(
    r.source,
    generic=r.dump_text("tree-original"),
    gimple=r.dump_text("tree-optimized"),
    rtl=r.dump_text("rtl-expand"),
    asm=r.asm,
    function="f",
)
lad.rung(6).counts()  # {'generic': 5, 'gimple': 4, 'rtl': 6, 'asm': 6}
```

That is the `for` header in `l1.c`, and it is most of the function at every level. Line 8, `return s;`, has one GENERIC statement, one GIMPLE statement and nothing below that at all, because the value was already in the return register and the epilogue got filed under the closing brace on line 9. Reading that off a picture takes a second, and reading it off four dump files takes an afternoon.

## The control flow graph comes from GCC, not from the gotos

A text dump prints the statements in each block and the jumps between them, and a block that falls into the next one has no jump to print. Build a graph by reading gotos and every fallthrough edge is missing, which in `l1.c` is enough to lose the loop. So `gxray.cfg` reads the other dump instead. Ask for `-graph` and GCC writes a `.dot` file beside the text one, straight out of `cfun`'s edge lists, with nothing left out:

```python
import gxray

r = gxray.corpus("l1-O2").compile(gxray.L1, "-O2")
g = r.cfg("tree-optimized")

str(g)  # 'f (5 blocks, 6 edges, 1 loop)'
g.successors(2)  # 2 -> 3 true [89%], 2 -> 4 false [11%]
g.back_edges  # 3 -> 3, the latch
g.dominators()  # {2: 0, 3: 2, 4: 2, 1: 4}
g.loops  # {1: [3]}
```

Blocks 0 and 1 are ENTRY and EXIT, which is true of every function GCC compiles. Edge kinds, probabilities and the loop tree are all in the dot file already, because `gcc/graph.cc` writes the flags out as colours, line styles and nested clusters. Reading it back means reading that mapping backwards, and it is lossy in two places, so `Edge` keeps the weight GCC wrote and a `back` flag rather than pretending a colour is the whole story. The module docstring says exactly where and why.

Drawing the same function at `tree-ssa` and at `tree-optimized` puts the loop rotation on screen. At SSA build time there are six blocks with a separate loop header, and by the end there are five with a single latch that jumps to itself.

## Nine shapes, and that is the whole vocabulary

`gxmanim` is the drawing side. It has exactly nine primitives, and a reader who learns them in lesson one can read every diagram in all 96 lessons without a legend:

| shape | what it means |
| --- | --- |
| card | one GIMPLE tuple or one RTL insn |
| block | a basic block, with its index and count in a header strip |
| edge | control flow, with the kind in the line style |
| badge | an SSA name and its version, or a pseudo register |
| thread | a definition to one of its uses |
| cell | one pass in the pipeline |
| rung | one IR level in the ladder |
| node | an RTX, a GENERIC tree, or a pattern |
| slot | a register, a stack frame, a vector lane, or a bit field |

A visual language with thirty symbols is not a language, it is a lookup table, so adding a tenth means amending the specification in the same change.

Above the shapes sit the mobjects. A mobject takes something `gxray` parsed and returns a `Scene`, which is a list of placed shapes, the links between them, and a sentence saying what the picture shows. It does not draw. The SVG renderer draws, the manim renderer will draw later, and because the meaning lives in the scene rather than in either of them the still in a lesson and the frame in a video cannot disagree.

```python
import gxray
from gxmanim import mobjects, svg

f = gxray.corpus("l1-O2").compile(gxray.L1, "-O2").dump("tree-optimized").only()
scene = mobjects.ssa_web(f, "s_9")

scene.describe()  # what the drawing says, in words
open("web.svg", "w").write(svg.document(scene))
```

`just diagrams` rebuilds every diagram from the recorded dumps and opens a contact sheet with each one and its caption underneath. The renderer has no dependencies, so a diagram is a file CI can regenerate from the dump it came from, and when the pinned compiler moves the pictures move with it.

Some things are not a shape. A control flow graph is a shape and gets a diagram, but the order the SSA renamer walks that graph in is a sequence, and the finished dump does not record it anywhere. Those get a film: a handful of scenes with a running time on each, rendered as one animated SVG that loops. There are six so far, listed on [the films](https://tamnd.github.io/gcc-internals/films/), and `just films` rebuilds them. They are animated SVG rather than video because SVG is text, so a film diffs, regenerates byte for byte, and can be checked by CI against the corpus it was drawn from. Every one of them falls back to a single readable frame when a reader has asked for no motion.

## A live notebook in the middle of a page

The book is MkDocs Material, and a page that wants a runnable experiment says so with one comment:

```markdown
<!-- island: site/notebooks/ce-probe.py -->
```

The build runs that notebook in ordinary CPython, writes the cells into the page as a marimo island with their output already in them, and parks everything the marimo runtime needs in a `<template>`. A script inside a template is inert, so the page costs what the HTML costs and not a byte more. Press the button on it and `island.js` moves the template into the head, which is the moment Pyodide starts coming down. A reader who never presses it never pays for it, and a reader with no JavaScript at all still sees the output the build recorded, because prose output is written into the page as plain HTML alongside the live cell.

Two things happen before the button is pressed, because a cold browser has to download the bundle and then Pyodide while marimo's own parent to worker timeout counts through both, and it loses that race. The page opens a connection to every host the runtime will use as soon as it loads, which carries no payload and hands the timeout back the second it was spending on DNS and TLS. Then the moment the reader's pointer or keyboard reaches the button, before any press, the bundle starts coming down. If it still runs out of time the island says so in a sentence and offers a reload, rather than leaving a status line that says "Starting Python" forever.

The one thing this needs from a notebook is that it knows where it is. `sys.platform == "emscripten"` is true in the browser and nowhere else, so a notebook that wants the network takes the other branch at build time and renders its before state. CI never calls a live API.

[The probe page](https://tamnd.github.io/gcc-internals/probe/) is the first one. It posts your C to Compiler Explorer's GCC 16.2 from your browser and prints the GIMPLE that comes back, which is the whole of open question 1 answered by doing it rather than by arguing about it.

## Blueprints are compiled, not typed

A blueprint has nine sections and no narrative, and the parts of it that are inventories are generated. GCC keeps the facts that have to stay consistent across fifty one targets and twelve front ends in machine readable form, so the list of GIMPLE statement codes comes out of `gcc/gimple.def` and the map from a statement code to the C++ class you may cast it to comes out of the `is_a_helper` specialisations in `gcc/gimple.h`. Nobody transcribes them.

```console
just blueprints        # rebuild every generated section from the pinned tree
just blueprints-check  # fail if what is committed is not what the generator produces
python -m tools.bpc coverage
```

The last one is the honest number. Every GIMPLE code is classified as covered, mentioned, or out of scope with a written reason, the inventory is read from the pinned tree rather than from the ledger, and a code that nothing classifies fails the build. Today it says 47 codes, 11 covered, 12 mentioned, 24 out of scope.

Nine of the fifty eight exist. A stub has all nine sections and says in the header what it does not yet cover, so it is useful to read and honest about its gaps rather than absent.

| Blueprint | Covers | Status |
|---|---|---|
| [BP-PIPELINE](blueprints/BP-PIPELINE.md) | the pass manager, the pass lists, and how a pass is registered and run | complete |
| [BP-GIMPLE](blueprints/BP-GIMPLE.md) | the GIMPLE statement, its codes, its layouts, and the gimplifier | partial |
| [BP-DRIVER](blueprints/BP-DRIVER.md) | the `gcc` program itself, the spec language, and how a suffix picks a compiler | stub |
| [BP-CFG](blueprints/BP-CFG.md) | basic blocks, edges, dominance, and the hook table that serves two IRs | stub |
| [BP-SSA](blueprints/BP-SSA.md) | SSA names, PHIs, virtual operands, and the four step construction | stub |
| [BP-EXPAND](blueprints/BP-EXPAND.md) | out of SSA, stack layout, and the optab search that turns GIMPLE into RTL | stub |
| [BP-RTL](blueprints/BP-RTL.md) | the insn, the pattern, and what recognition means | stub |
| [BP-REGALLOC](blueprints/BP-REGALLOC.md) | IRA and LRA, and what a register class actually constrains | stub |
| [BP-FINAL](blueprints/BP-FINAL.md) | the last pass, and how an insn becomes a line of assembly | stub |

## Six compilers, and only one job that builds them

From Part II onward a reader stops borrowing a compiler and starts owning one, and the lessons need more than one kind. `rel` is the fast one, `chk` has every internal consistency check GCC has turned on, `dbg` is unoptimized with full debug info because a debugger at `-O2` shows you a function whose locals are gone and whose lines run backwards, `boot` is the full three stage bootstrap, `cross` targets riscv64-unknown-elf so the back end lessons have a machine the reader is not sitting at, and `plug` is a distribution's own GCC with the plugin built against it.

All six are described in [`containers/matrix.toml`](containers/matrix.toml) and nowhere else. The workflow asks what to run, the Dockerfile is handed its configure flags, and the table in [`containers/README.md`](containers/README.md) is generated, because configure flags in a Dockerfile plus a job list in a workflow plus times and sizes in a README is three copies of one fact and the second one is stale by the end of the first week.

```console
$ just matrix-show chk
chk, Every internal consistency check GCC has, turned on.
```

The rule underneath it is that no job in this project compiles GCC except the matrix job. A full weekly run is about twelve machine hours across the two architectures and `boot` is eight of them, which is why it is the one configuration that never runs on a push. Everything else pulls an image by digest, so a green run cannot quietly have been testing a compiler nobody published.

`plug` is the row that matters most to a reader, and it is the only one that does not build anything. It installs Debian's `gcc-16`, which is 16.2.0, the same release the citations resolve against, and builds the plugin against that. If the plugin loads only into a compiler we built ourselves then the plugin does not work, and the way to keep that honest is to have one image that never builds one.

## Status

M1 is done and the book publishes at [tamnd.github.io/gcc-internals](https://tamnd.github.io/gcc-internals/) on every merge to main. Twelve lessons, six films, nine blueprints, the glossary, and the live probe page. M0 is still underway. The build matrix exists and the plugin image is verified against Debian's packaged GCC 16.2.0, so what is left of it is the plugin itself and three beginner testers, neither of which is a thing a merge can finish.

See the [milestones](https://github.com/tamnd/gcc-internals/milestones) for the plan and the [open questions](https://github.com/tamnd/gcc-internals/issues?q=is%3Aissue+label%3Akind%2Fopen-question) for what could still change it.

The riskiest one is #1. If Pyodide cannot reach the Compiler Explorer API from a static site, Tier 0 becomes recorded dumps only, and that is a materially worse project. It gets answered in week one.

## Pins

GCC 16.2.0, released 7 August 2026. One site version per GCC major release.

## Licence

Prose, diagrams and animations under CC BY-SA 4.0. Code, tooling and capstone artifacts under GPLv3 or later.
