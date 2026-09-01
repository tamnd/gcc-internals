# The claim ledger

Every behavioural claim the lessons make about GCC, and the cell that proves it.

This file is generated. A lesson marks a claim where it makes it, the build works out which cell answers it, and `just claims` fails when one has no answer. The rule is that the evidence is the next code cell and it has to come before the next section heading, because a claim proved three sections later is a claim nobody checked.

A few true things cannot be shown from a notebook at all: what a pass does to memory it has already freed, or the shape of a function a reader would need a debugger on `cc1` to see. Those are marked with the reason, and a lesson is allowed at most 3 of them. The cap is the point. Without it the exception becomes the rule and this goes back to being a book.

Claims about GCC's source rather than its behaviour do not live here. Those carry a `path:line@tag` citation and are checked by `refcheck` against the pinned tree.

12 claims across 2 lessons, 0 of them not observable from a notebook.

## What does gcc actually run?

| Claim | Proved by |
| --- | --- |
| on this target gcc runs one program for -E and for -S, two for -c, and three for a full link | [`t01-10`](t01-what-gcc-runs/t01.ipynb) |
| the driver runs cc1 from an absolute path under libexec, and cc1 is not on the PATH | [`t01-12`](t01-what-gcc-runs/t01.ipynb) |
| the driver hands cc1 many more arguments than the user typed on the command line | [`t01-16`](t01-what-gcc-runs/t01.ipynb) |
| changing -O0 to -O2 changes one flag given to cc1 and nothing at all given to as | [`t01-18`](t01-what-gcc-runs/t01.ipynb) |
| the same source and flags run three programs on one GCC 16.2 build and one on another | [`t01-21`](t01-what-gcc-runs/t01.ipynb) |

## SSA in one lesson

| Claim | Proved by |
| --- | --- |
| the variable s from the source appears in the tree-ssa dump as three separate SSA names | [`t05-10`](t05-ssa-in-one-lesson/t05.ipynb) |
| an SSA name knows the single statement that defines it and the full list of places it is used | [`t05-12`](t05-ssa-in-one-lesson/t05.ipynb) |
| a phi node has exactly one argument per incoming edge, and the arguments are positional | [`t05-18`](t05-ssa-in-one-lesson/t05.ipynb) |
| bb 3 and bb 5 are both immediately dominated by bb 4, not by each other | [`t05-22`](t05-ssa-in-one-lesson/t05.ipynb) |
| the SSA versions in tree-optimized are different from the ones in tree-ssa for the same function | [`t05-26`](t05-ssa-in-one-lesson/t05.ipynb) |
| after optimization the back edge in l1 goes from bb 3 to itself | [`t05-32`](t05-ssa-in-one-lesson/t05.ipynb) |
| every SSA version of s in tree-optimized ends up in the one virtual register that also holds the return value | [`t05-34`](t05-ssa-in-one-lesson/t05.ipynb) |
