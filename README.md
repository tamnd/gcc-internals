# gcc-internals

A visual, hands on teardown of GCC 16, taught from zero, and specified precisely enough that you can write a working front end, a working back end and a working optimizer against the specifications alone.

The plan is 96 lessons in eleven parts, 58 blueprints, and three capstone tracks. Nothing exists yet. This repository currently holds the plan, as thirteen milestones and eighteen open questions, and the first code lands with M0.

## The idea

GCC is the most self documenting large program most engineers will never read. It prints 153 dumps for a four line function, it names all 395 of its passes, it will draw you a control flow graph, and it will tell you why it refused to vectorize your loop. Almost none of that shows up in the material people learn from, which is mostly correct about GCC 4.4 and quietly wrong about everything since.

So the rules are:

- **Observable first.** No claim about GCC's behaviour without a command the reader can run that shows it.
- **Nothing installed.** Every lesson has an experiment that runs in a browser, against the Compiler Explorer API, with a recorded dump corpus as the offline fallback.
- **Cited like a lawyer.** Every claim about the code points at a file, a line and a release tag, and CI fails when the cited line changes.
- **Every lesson ends with a blueprint.** A normative spec of the thing you read about, written so somebody can implement it without ever seeing the lesson.
- **Every part ends with you changing GCC and proving it.**

## Why blueprints, and why three capstones

A specification nobody has implemented from is a wish. The three tracks exist to find out where the blueprints are wrong, and they exercise almost disjoint parts of the set: a real front end for a toy language, a real port for a synthetic RISC target, and six middle end passes checked against GCC and against an SMT solver.

The headline number this project is trying to produce is not a lesson count. It is the number of blueprint bugs the implementations found.

## Status

Pre M0. See the [milestones](https://github.com/tamnd/gcc-internals/milestones) for the plan and the [open questions](https://github.com/tamnd/gcc-internals/issues?q=is%3Aissue+label%3Akind%2Fopen-question) for what could still change it.

The riskiest one is #1. If Pyodide cannot reach the Compiler Explorer API from a static site, Tier 0 becomes recorded dumps only, and that is a materially worse project. It gets answered in week one.

## Pins

GCC 16.2.0, released 7 August 2026. One site version per GCC major release.

## Licence

Prose, diagrams and animations under CC BY-SA 4.0. Code, tooling and capstone artifacts under GPLv3 or later.
