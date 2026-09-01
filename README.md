# gcc-internals

A visual, hands on teardown of GCC 16, taught from zero, and specified precisely enough that you can write a working front end, a working back end and a working optimizer against the specifications alone.

The plan is 96 lessons in eleven parts, 58 blueprints, and three capstone tracks. Nothing exists yet. This repository currently holds the plan, as thirteen milestones and eighteen open questions, and the first code lands with M0.

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

## Blueprints are compiled, not typed

A blueprint has nine sections and no narrative, and the parts of it that are inventories are generated. GCC keeps the facts that have to stay consistent across fifty one targets and twelve front ends in machine readable form, so the list of GIMPLE statement codes comes out of `gcc/gimple.def` and the map from a statement code to the C++ class you may cast it to comes out of the `is_a_helper` specialisations in `gcc/gimple.h`. Nobody transcribes them.

```console
just blueprints        # rebuild every generated section from the pinned tree
just blueprints-check  # fail if what is committed is not what the generator produces
python -m tools.bpc coverage
```

The last one is the honest number. Every GIMPLE code is classified as covered, mentioned, or out of scope with a written reason, the inventory is read from the pinned tree rather than from the ledger, and a code that nothing classifies fails the build. Today it says 47 codes, 11 covered, 12 mentioned, 24 out of scope.

## Status

M0 is underway. See the [milestones](https://github.com/tamnd/gcc-internals/milestones) for the plan and the [open questions](https://github.com/tamnd/gcc-internals/issues?q=is%3Aissue+label%3Akind%2Fopen-question) for what could still change it.

The riskiest one is #1. If Pyodide cannot reach the Compiler Explorer API from a static site, Tier 0 becomes recorded dumps only, and that is a materially worse project. It gets answered in week one.

## Pins

GCC 16.2.0, released 7 August 2026. One site version per GCC major release.

## Licence

Prose, diagrams and animations under CC BY-SA 4.0. Code, tooling and capstone artifacts under GPLv3 or later.
