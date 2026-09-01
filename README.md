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

## Status

M0 is underway. See the [milestones](https://github.com/tamnd/gcc-internals/milestones) for the plan and the [open questions](https://github.com/tamnd/gcc-internals/issues?q=is%3Aissue+label%3Akind%2Fopen-question) for what could still change it.

The riskiest one is #1. If Pyodide cannot reach the Compiler Explorer API from a static site, Tier 0 becomes recorded dumps only, and that is a materially worse project. It gets answered in week one.

## Pins

GCC 16.2.0, released 7 August 2026. One site version per GCC major release.

## Licence

Prose, diagrams and animations under CC BY-SA 4.0. Code, tooling and capstone artifacts under GPLv3 or later.
