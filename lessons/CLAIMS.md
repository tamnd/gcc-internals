# The claim ledger

Every behavioural claim the lessons make about GCC, and the cell that proves it.

This file is generated. A lesson marks a claim where it makes it, the build works out which cell answers it, and `just claims` fails when one has no answer. The rule is that the evidence is the next code cell and it has to come before the next section heading, because a claim proved three sections later is a claim nobody checked.

A few true things cannot be shown from a notebook at all: what a pass does to memory it has already freed, or the shape of a function a reader would need a debugger on `cc1` to see. Those are marked with the reason, and a lesson is allowed at most 3 of them. The cap is the point. Without it the exception becomes the rule and this goes back to being a book.

Claims about GCC's source rather than its behaviour do not live here. Those carry a `path:line@tag` citation and are checked by `refcheck` against the pinned tree.

35 claims across 6 lessons, 4 of them not observable from a notebook.

## What does gcc actually run?

| Claim | Proved by |
| --- | --- |
| on this target gcc runs one program for -E and for -S, two for -c, and three for a full link | [`t01-10`](t01-what-gcc-runs/t01.ipynb) |
| the driver runs cc1 from an absolute path under libexec, and cc1 is not on the PATH | [`t01-12`](t01-what-gcc-runs/t01.ipynb) |
| the driver hands cc1 many more arguments than the user typed on the command line | [`t01-16`](t01-what-gcc-runs/t01.ipynb) |
| changing -O0 to -O2 changes one flag given to cc1 and nothing at all given to as | [`t01-18`](t01-what-gcc-runs/t01.ipynb) |
| the same source and flags run three programs on one GCC 16.2 build and one on another | [`t01-21`](t01-what-gcc-runs/t01.ipynb) |

## The five faces of one function

| Claim | Proved by |
| --- | --- |
| every item at every level carries a file and a line, and that is the only field the four levels have in common | [`t02-06`](t02-five-faces/t02.ipynb) |
| the loop header line is the busiest line in the function at all four levels | [`t02-09`](t02-five-faces/t02.ipynb) |
| the return statement has nothing at all at the RTL and assembly levels, and the closing brace has two of each | [`t02-12`](t02-five-faces/t02.ipynb) |
| GCC has more GENERIC node codes than RTL expression codes, and roughly five times as many of either as it has GIMPLE statement codes | not observable from a notebook: the counts come from GCC's own .def files, and this notebook has no copy of the source tree. The citations are checked against the pinned tree on every push instead. |

## GIMPLE is C with the fun removed

| Claim | Proved by |
| --- | --- |
| no statement anywhere in the gimplified bench has more than one operator on it, and the GENERIC it came from has a line with seven | [`t03-11`](t03-gimple-is-c-with-the-fun-removed/t03.ipynb) |
| the bench is seven functions of one line each, and gimplification turns them into between two and eleven statements | [`t03-13`](t03-gimple-is-c-with-the-fun-removed/t03.ipynb) |
| neither the && nor the ?: leaves an operator behind, and what stands in for both of them is a condition, some labels, some gotos, and one variable written on two different paths | [`t03-18`](t03-gimple-is-c-with-the-fun-removed/t03.ipynb) |
| one function does nearly all of this, and the switch at the middle of it has over a hundred cases, one per kind of tree node it might have to take apart | not observable from a notebook: the shape of gimplify_expr is a fact about the source tree, and this notebook has no copy of it. The citation is checked against the pinned tree on every push instead. |

## Three hundred and ninety-five passes

| Claim | Proved by |
| --- | --- |
| GCC 16.2 knows about 395 passes, and 281 of them printed ON for L1 at -O2 | [`t04-05`](t04-three-hundred-and-ninety-five-passes/t04.ipynb) |
| the pipeline is nested four deep, and two containers hold more than half of it between them | [`t04-10`](t04-three-hundred-and-ninety-five-passes/t04.ipynb) |
| -O3 turns on eight passes that -O2 does not, and -Os turns on one that -O2 does not, so the levels are not a slider | [`t04-15`](t04-three-hundred-and-ninety-five-passes/t04.ipynb) |
| 60 of the 281 passes that printed ON at -O2 sit under a container that printed OFF, and not one of them left a dump behind | [`t04-18`](t04-three-hundred-and-ninety-five-passes/t04.ipynb) |
| the container holding the 29 passes that run after register allocation prints OFF at every optimization level, because its gate returns reload_completed and register allocation has not happened at the moment the listing is printed | not observable from a notebook: the recording holds tree dumps and the passes in question are RTL passes, so there is nothing in this notebook that could show them running. The citation is checked against the pinned tree on every push instead. |
| 281 cells, 135 of them have a dump, 25 changed the IR of f, 109 left it exactly as they found it, and 147 cannot say | [`t04-21`](t04-three-hundred-and-ninety-five-passes/t04.ipynb) |

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

## What -O2 actually turns on

| Claim | Proved by |
| --- | --- |
| at -O2 the optimizer table is 295 lines, of which 244 are switches that are either on or off | [`t06-05`](t06-what-o2-actually-turns-on/t06.ipynb) |
| -O1 to -O2 is 55 differences, of which 48 are switches turning on, none are switches turning off, and 7 are options that took a new value | [`t06-08`](t06-what-o2-actually-turns-on/t06.ipynb) |
| the 114 rows of default_options_table use six of the twelve level words, and ten of the rows are marked speed only | [`t06-12`](t06-what-o2-actually-turns-on/t06.ipynb) |
| -O2 to -Os is 12 differences, of which 7 are switches going off and none are switches coming on, and -Os and -Oz print byte-identical tables | [`t06-15`](t06-what-o2-actually-turns-on/t06.ipynb) |
| -Os and -Oz differ inside the compiler, where optimize_size is 1 for one and 2 for the other, and every level word in the table asks whether optimize_size is nonzero rather than what it is, which is why no printed table can tell the two apart | not observable from a notebook: optimize_size is a field on the options structure and the only way to read it is from inside a running compiler. The two lines of source that set it are cited above and checked against the pinned tree on every push. |
| 13 switches on at -O1 are off at -Og, and one switch is on at -Og and off at -O1, so -Og is neither above nor below it | [`t06-20`](t06-what-o2-actually-turns-on/t06.ipynb) |
| -O3 to -Ofast is 11 differences, 5 switches on, 4 off and 2 values, and three of the four it turns off were the ones keeping the floating point arithmetic honest | [`t06-23`](t06-what-o2-actually-turns-on/t06.ipynb) |
| -O1 plus all 48 switches produces 86 lines of assembly for L1, which is worse than -O1 at 54 and worse than -O2 at 56, and adding the 7 value changes makes it byte-identical to -O2 | [`t06-31`](t06-what-o2-actually-turns-on/t06.ipynb) |
| L0 needs 1 of the 55 flags to match its -O2 output, L1 needs 4, and L2 needs 8 | [`t06-34`](t06-what-o2-actually-turns-on/t06.ipynb) |
