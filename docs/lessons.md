# The lessons

Ninety six lessons in eleven parts. This page is generated from the lessons themselves, so a lesson that exists is on it and a lesson that does not is not.

Every one is a notebook with a Colab badge, so there is nothing to install. Part I runs on the recorded dumps in `corpora/`, which are real output from a real GCC 16.2 and are committed, so a reader with a browser and no compiler sees what the lesson saw. Colab does have a GCC and it is not this one, which is why the setup cell picks a backend that matches and the banner says which one it picked.

| | Lesson | What you come away with | Milestone | Run it |
|---|---|---|---|---|
| T01 | [What does gcc actually run?](https://github.com/tamnd/gcc-internals/blob/main/lessons/t01-what-gcc-runs/t01.ipynb) | That `gcc` compiles nothing and runs the programs that do, how to make it show you the list without running any of it, why `cc1` is not on your PATH, and where the flags you typed actually end up | M1 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t01-what-gcc-runs/t01.ipynb) |
| T05 | [SSA in one lesson](https://github.com/tamnd/gcc-internals/blob/main/lessons/t05-ssa-in-one-lesson/t05.ipynb) | Reading `s_1`, `s_3` and `s_8` as three versions of one variable rather than three variables, what a `PHI` is and where it has to go, what the `(D)` on `n_5(D)` is telling you, and watching SSA get taken apart again on the way to machine code | M0 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tamnd/gcc-internals/blob/main/lessons/t05-ssa-in-one-lesson/t05.ipynb) |

2 of 96 written.
