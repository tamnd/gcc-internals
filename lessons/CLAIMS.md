# The claim ledger

Every behavioural claim the lessons make about GCC, and the cell that proves it.

This file is generated. A lesson marks a claim where it makes it, the build works out which cell answers it, and `just claims` fails when one has no answer. The rule is that the evidence is the next code cell and it has to come before the next section heading, because a claim proved three sections later is a claim nobody checked.

A few true things cannot be shown from a notebook at all: what a pass does to memory it has already freed, or the shape of a function a reader would need a debugger on `cc1` to see. Those are marked with the reason, and a lesson is allowed at most 3 of them. The cap is the point. Without it the exception becomes the rule and this goes back to being a book.

Claims about GCC's source rather than its behaviour do not live here. Those carry a `path:line@tag` citation and are checked by `refcheck` against the pinned tree.

83 claims across 12 lessons, 4 of them not observable from a notebook.

## C++ for people who will only ever read it

| Claim | Proved by |
| --- | --- |
| every one of the seventeen constructs appears in the snippets this lesson reads | [`z01-06`](z01-cpp-for-reading/z01.ipynb) |
| the tag that decides which arm of the union is live is a sixteen bit field | [`z01-10`](z01-cpp-for-reading/z01.ipynb) |
| a GIMPLE subclass tells is-a.h what it is with a three line function and nothing else | [`z01-16`](z01-cpp-for-reading/z01.ipynb) |
| as_a checks with an assert that a release build removes, and dyn_cast checks always | [`z01-20`](z01-cpp-for-reading/z01.ipynb) |
| twelve of the forty lines of get_default_value carry a construct, of five kinds | [`z01-35`](z01-cpp-for-reading/z01.ipynb) |

## How to be lost in four and a half million lines, productively

| Claim | Proved by |
| --- | --- |
| three quarters of the source in the GCC tree is under gcc/, and the rest is libraries that ship alongside the compiler | [`z02-04`](z02-where-things-are/z02.ipynb) |
| the middle end has no directory of its own and sits loose in gcc/ | [`z02-07`](z02-where-things-are/z02.ipynb) |
| the compiler proper is about four and a half million lines, and the tests are seven tenths of that in fourteen times as many files | [`z02-10`](z02-where-things-are/z02.ipynb) |
| there is exactly one .pd file in the whole tree and it is match.pd | [`z02-13`](z02-where-things-are/z02.ipynb) |
| three directories under gcc/config are not ports and have no machine description | [`z02-20`](z02-where-things-are/z02.ipynb) |
| the file named in an Applying pattern message does not exist in the source tree | [`z02-23`](z02-where-things-are/z02.ipynb) |
| every pass in passes.def resolves to a file and to a dump name | [`z02-32`](z02-where-things-are/z02.ipynb) |
| the Simulating statement line in a ccp dump is not printed by tree-ssa-ccp.cc | [`z02-35`](z02-where-things-are/z02.ipynb) |
| Removing basic block arrived with the entire GIMPLE and SSA middle end, in one commit | [`z02-38`](z02-where-things-are/z02.ipynb) |
| the largest file under gcc/ is a hand written parser and not generated at all | [`z02-41`](z02-where-things-are/z02.ipynb) |

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

## Where GIMPLE becomes RTL

| Claim | Proved by |
| --- | --- |
| L1 at expand is a chain of 40 entries and only 13 of them are instructions | [`t07-05`](t07-where-gimple-becomes-rtl/t07.ipynb) |
| L1's whole function uses 13 different RTX codes, and 25 of the nodes are registers | [`t07-10`](t07-where-gimple-becomes-rtl/t07.ipynb) |
| insn 21 reads as pseudo 102 becoming pseudo 102 plus pseudo 101 | [`t07-13`](t07-where-gimple-becomes-rtl/t07.ipynb) |
| of the first ten entries in L1 exactly one is an instruction, six are for the debugger and three are markers | [`t07-20`](t07-where-gimple-becomes-rtl/t07.ipynb) |
| L1 uses three pseudo registers, numbered 101 to 103, and two hard ones | [`t07-23`](t07-where-gimple-becomes-rtl/t07.ipynb) |
| SI appears 30 times in L1, CC six times and DI twice | [`t07-26`](t07-where-gimple-becomes-rtl/t07.ipynb) |
| the four targets agree on none of the ten things the table measures | [`t07-29`](t07-where-gimple-becomes-rtl/t07.ipynb) |

## Registers are a lie until they are not

| Claim | Proved by |
| --- | --- |
| the five functions have register pressure 6, 12, 16, 22 and 32, which is N plus two | [`t08-05`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| in p20 half the pseudos have two allocnos, one for the loop and one for outside it | [`t08-08`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| compressing the point numbering throws away about two thirds of the points | [`t08-11`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| in p20 the busiest value conflicts with 39 of the other 41 pseudos | [`t08-14`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| x86-64 hands out 15 registers, and the pressure of p14 is 16, one too many | [`t08-17`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| in p20 on x86-64 seven pseudos are in memory and the rest are in numbered registers | [`t08-20`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| p14 and p20 fit on aarch64 and do not fit on x86-64 | [`t08-23`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| the colouring trace and the final disposition disagree about four allocnos in p30 | [`t08-31`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |
| IRA charges nothing for memory on aarch64 until p30, and a great deal on x86-64 | [`t08-34`](t08-registers-are-a-lie-until-they-are-not/t08.ipynb) |

## The last mile

| Claim | Proved by |
| --- | --- |
| the assembly for a four line function is forty six lines, twelve of them instructions | [`t09-05`](t09-the-last-mile/t09.ipynb) |
| every annotated line names an insn in the final RTL dump, and the two agree | [`t09-08`](t09-the-last-mile/t09.ipynb) |
| five patterns emitted all twelve instructions, and one of them emitted four | [`t09-11`](t09-the-last-mile/t09.ipynb) |
| *addsi3_aarch64 is written *add<mode>3_aarch64 and lives at aarch64.md line 2694 | [`t09-14`](t09-the-last-mile/t09.ipynb) |
| the two movs used different rows, and the rows differ in one constraint letter | [`t09-19`](t09-the-last-mile/t09.ipynb) |
| across all three recordings the slash appears exactly when the pattern has more than one row | [`t09-22`](t09-the-last-mile/t09.ipynb) |
| the same twelve instructions come wrapped in thirty four other lines on Linux and forty four on Darwin | [`t09-25`](t09-the-last-mile/t09.ipynb) |
| nine names land in five different sections and nothing in the C says which | [`t09-28`](t09-the-last-mile/t09.ipynb) |
| wide is four bytes and the section it sits in is aligned to sixty four | [`t09-31`](t09-the-last-mile/t09.ipynb) |

## The whole map

| Claim | Proved by |
| --- | --- |
| nine of the fourteen stages are passes in the list, and five are not | [`t10-07`](t10-the-whole-map/t10.ipynb) |
| 281 passes ran on this function and 36 of them changed it | [`t10-10`](t10-the-whole-map/t10.ipynb) |
| the ladder for nearest has rows for source lines that are inside dist2 | [`t10-15`](t10-the-whole-map/t10.ipynb) |
| release_ssa changed twenty three lines and every one of them only moved a number | [`t10-20`](t10-the-whole-map/t10.ipynb) |
| einline is the pass that put dist2 inside nearest, and it is the largest single change | [`t10-24`](t10-the-whole-map/t10.ipynb) |
| five tree passes changed the squares, and one of them only renumbered them | [`t10-28`](t10-the-whole-map/t10.ipynb) |
| combine is the pass that turned the multiply and the add into one insn | [`t10-31`](t10-the-whole-map/t10.ipynb) |
| the fused insn is printed by a pattern called maddsi and the file says which | [`t10-34`](t10-the-whole-map/t10.ipynb) |
