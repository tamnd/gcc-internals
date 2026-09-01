# Glossary

One definition per term, in one place, so a lesson can use a word without stopping to explain it and without assuming you remember it from forty lessons ago. Lessons link into this file rather than repeating themselves.

The order below is the order you meet these things, not alphabetical, because reading it straight through is a reasonable thing to do. If you are looking one up, the index is next.

This file is generated from `gxray/glossary.py`. Edit that and run `just build-glossary`.

## Index

[GENERIC](#generic) | [GIMPLE](#gimple) | [RTL](#rtl) | [SSA](#ssa) | [SSA name](#ssa-name) | [back end](#back-end) | [basic block](#basic-block) | [cc1](#cc1) | [control flow graph](#control-flow-graph) | [default definition](#default-definition) | [definition](#definition) | [dominance](#dominance) | [driver](#driver) | [dump file](#dump-file) | [edge](#edge) | [expand](#expand) | [front end](#front-end) | [gimplification](#gimplification) | [immediate dominator](#immediate-dominator) | [loop](#loop) | [middle end](#middle-end) | [out of SSA](#out-of-ssa) | [pass](#pass) | [pass manager](#pass-manager) | [phi node](#phi-node) | [spec](#spec) | [tree](#tree) | [use](#use)

## Driving the compiler

What actually runs when you type `gcc`, and how to make it show you its work. T01 and T04 are the lessons that cover this ground.

### driver

**The program called `gcc`, which compiles nothing and runs the things that do.**

It reads your command line, works out which language you are in, and then runs a compiler, an assembler and a linker as separate processes. This is worth knowing early because almost every option you pass to `gcc` is really an option for one of those, and `gcc -v` prints the four command lines it built so you can see which. The driver is a few thousand lines of argument shuffling and it is not where the compiler lives.

Also written `gcc`, `gcc.cc`. First met in T01. See also [cc1](#cc1), [spec](#spec).

### cc1

**The actual C compiler. One process, one translation unit, C in and assembly out.**

Everything this course is about happens inside `cc1`. It is not on your PATH and it is not meant to be run by hand, which is why `gcc -v` is how you find it. There is one of these per language: `cc1plus` for C++, `f951` for Fortran, and so on, all built from the same middle end and back end with a different front end bolted on the front.

First met in T01. See also [driver](#driver), [spec](#spec), [front end](#front-end). In the source: [`gcc/gcc.cc:1234@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gcc.cc#L1234).

### spec

**A small string language the driver uses to build the command lines it runs.**

A spec is a template full of conditionals like `%{save-temps:...}` that expands into arguments. They are almost unreadable and you will not need to write one, but recognising the syntax stops `gcc -dumpspecs` from looking like line noise, and knowing they exist explains why an option you passed shows up in a completely different form in the `cc1` command line.

First met in T01. See also [driver](#driver), [cc1](#cc1).

### dump file

**A text file GCC writes showing the function after one particular pass.**

Ask for one with `-fdump-tree-ssa` or `-fdump-rtl-expand` and GCC writes the whole function out in that pass's representation. This is the main window this course looks through, and the important thing about it is that it is a rendering rather than the data structure: the dump has no explicit edges, no pointers, and no types unless you ask for them with a modifier. Add `-graph` and you get a `.dot` beside it that does have the edges.

Also written `-fdump-tree-all`. First met in T01. See also [pass](#pass). In the source: [`gcc/dumpfile.h:522@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/dumpfile.h#L522).

### pass

**One transformation or analysis, run over one function, in a fixed order.**

The whole middle end and back end is a list of these. A pass has a name, a gate that decides whether it runs at all, and an execute function. The list is much longer than people expect and most of what it contains does nothing at `-O0`, which is why the count you get from `-fdump-passes` depends on the optimisation level. Passes are the unit everything else in this course is organised around, because a dump file is named after one.

First met in T01. See also [dump file](#dump-file), [pass manager](#pass-manager). In the source: [`gcc/tree-pass.h:73@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-pass.h#L73).

### pass manager

**The loop that walks the pass list and runs each pass on each function.**

It is also the thing that opens the dump file, checks the gate, verifies the IR afterwards when checking is on, and keeps track of which analyses are still valid. When a pass appears to have been skipped, the pass manager is where the answer is, and the answer is almost always the gate.

First met in T04. See also [pass](#pass). In the source: [`gcc/passes.cc:2579@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/passes.cc#L2579).

### front end

**The half of the compiler that knows a language, as opposed to the half that does not.**

A front end parses one language and hands the middle end a function body in GENERIC. Everything after that point is shared, which is the single most important structural fact about GCC: twelve languages, one optimiser, one code generator. It is also why an optimisation bug is almost never a C bug.

First met in T01. See also [GENERIC](#generic), [middle end](#middle-end).

### middle end

**Everything between the front end and the back end, where the optimisation happens.**

It takes GENERIC in and hands RTL out, and in between it works on GIMPLE in SSA form. The name is a joke that stuck, since a thing with two ends does not have a middle, but it is what everybody calls it and what the source calls it.

First met in T01. See also [front end](#front-end), [GIMPLE](#gimple), [back end](#back-end).

### back end

**The half that knows a machine, from RTL down to the assembly text.**

It is generated, mostly. A target is described by a `.md` file full of patterns and a `.cc` file full of hooks, and a pile of build time programs turn those into the C that actually runs. This is why grepping for the function that emitted an instruction so often lands you in a file that does not exist in the source tree.

First met in T01. See also [RTL](#rtl), [middle end](#middle-end).

## The four shapes a function takes

The same function, written down four different ways on its way to assembly. T02, T03 and T07 are the lessons.

### tree

**GCC's universal node type. One tagged union for every kind of thing.**

A `tree` is a pointer to a union with a code on the front telling you which member is live. Types are trees, declarations are trees, constants are trees, and expressions are trees, which is why the accessor macros are shouty and everywhere. It is the oldest data structure in the compiler and reading anything in the front end means being comfortable with it.

Also written `tree_node`. First met in T02. See also [GENERIC](#generic), [GIMPLE](#gimple). In the source: [`gcc/tree-core.h:2186@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-core.h#L2186).

### GENERIC

**The language independent tree a front end hands over. Still a tree, still nested.**

GENERIC is what the C parser produces: a whole function as one expression tree, with loops and conditionals and function calls nested inside each other exactly the way you wrote them. It is close enough to the source that you can read your program back out of it, which is the point, and far enough from the source that a Fortran front end can produce the same thing.

First met in T02. See also [tree](#tree), [GIMPLE](#gimple), [gimplification](#gimplification).

### GIMPLE

**A flattened three address form. One operation per statement, no nesting.**

Every expression is broken up until each statement does exactly one thing, with temporaries invented to hold the middle results. This is the representation the entire middle end works on, and the reason for it is that a pass that has to handle arbitrary nesting is a pass nobody can write correctly. What you lose is readability, which is why the dumps look like somebody ran your code through a shredder.

First met in T03. See also [GENERIC](#generic), [gimplification](#gimplification), [SSA](#ssa), [basic block](#basic-block). In the source: [`gcc/gimple.h:222@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimple.h#L222).

### gimplification

**The pass that turns GENERIC into GIMPLE by flattening the nesting out.**

It walks the tree and, every time it finds an expression that is too complicated to be a statement on its own, it invents a temporary, assigns the sub-expression to it, and puts the assignment before. Everything else about GIMPLE follows from that one move. The function that does it is one of the largest switch statements in the compiler and it is worth looking at once.

First met in T03. See also [GENERIC](#generic), [GIMPLE](#gimple). In the source: [`gcc/gimplify.cc:20296@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimplify.cc#L20296).

### RTL

**Register Transfer Language. Machine operations on unlimited virtual registers.**

RTL is the back end's representation and it is a Lisp-like expression describing what an instruction does to registers and memory, not what the instruction is called. A target matches those expressions against its patterns to pick real instructions. The move from GIMPLE to RTL is the point where the compiler stops being about your program and starts being about a machine.

Also written `rtx`. First met in T07. See also [expand](#expand), [back end](#back-end). In the source: [`gcc/rtl.h:314@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/rtl.h#L314).

### expand

**The pass that turns GIMPLE into RTL, one statement at a time.**

It is the hinge of the whole compiler and it is not reversible: after expand there is no going back to GIMPLE, so every optimisation that wants to reason about your program rather than about a machine has to have happened already. It is also where the stack frame gets laid out and where a virtual register first appears.

First met in T07. See also [GIMPLE](#gimple), [RTL](#rtl). In the source: [`gcc/cfgexpand.cc:7015@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/cfgexpand.cc#L7015).

## The shape of a function

Blocks, edges and the questions you can ask about them. T05 needs the first four of these, G02 and G03 go deeper.

### basic block

**A run of statements with one way in at the top and one way out at the bottom.**

Nothing branches into the middle of a block and nothing branches out of the middle, so if the first statement runs then all of them run. That guarantee is what makes a block the unit every analysis works in. In a dump they are the things labelled `<bb 3>`, and the two numbered 0 and 1 are the entry and exit blocks, which hold no statements and exist so that every real block has somewhere to come from and go to.

Also written `<bb 3>`. First met in T05. See also [control flow graph](#control-flow-graph), [edge](#edge). In the source: [`gcc/basic-block.h:117@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/basic-block.h#L117).

### control flow graph

**The blocks of a function plus the edges saying which can follow which.**

The important thing about the CFG is that it is a real data structure with real edges, and the text dump is not it. A fallthrough from one block to the next shows up in the dump as nothing at all, because there is no goto to print, so counting edges by reading a dump gives the wrong answer. Ask for `-graph` and GCC writes the edges out properly.

Also written CFG. First met in T05. See also [basic block](#basic-block), [edge](#edge), [dominance](#dominance).

### edge

**One possible jump from the end of one block to the start of another.**

Edges carry flags, and the flags are where the interesting cases live: a back edge closes a loop, an abnormal edge is one the compiler cannot reason about normally, an EH edge is the path taken when something throws. A block with two outgoing edges ends in a condition, and which edge is the true one is a flag rather than an ordering.

First met in T05. See also [basic block](#basic-block), [control flow graph](#control-flow-graph), [loop](#loop).

### dominance

**Block A dominates block B if every path to B goes through A first.**

This is the question the whole middle end keeps asking, because it is how you know a value is available: if the block that defines it dominates the block that uses it, the definition has definitely already run. Entry dominates everything. A block always dominates itself, which sounds like a technicality and matters constantly.

First met in T05. See also [immediate dominator](#immediate-dominator), [basic block](#basic-block), [SSA](#ssa). In the source: [`gcc/dominance.cc:856@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/dominance.cc#L856).

### immediate dominator

**The closest block that dominates a given block, not counting the block itself.**

Every block except entry has exactly one, which means the dominance relation of a whole function fits in one number per block and the dominator tree is that array read as a tree. GCC computes it lazily and a pass has to ask for it, which is why you see `calculate_dominance_info` at the top of so many passes.

Also written idom, dominator tree. First met in T05. See also [dominance](#dominance).

### loop

**A back edge and everything that can reach it without leaving.**

GCC finds loops rather than being told about them, which is why a loop written with `goto` and a loop written with `for` end up identical here, and why a `for` loop that the compiler proved runs a fixed number of times may not be a loop by the time you look. Loops nest, and the nesting is a tree with a fake outermost loop at the root standing for the function.

First met in T05. See also [edge](#edge), [control flow graph](#control-flow-graph). In the source: [`gcc/cfgloop.h:120@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/cfgloop.h#L120).

## SSA

The one idea that makes the middle end tractable, and the vocabulary that comes with it. T05 is the lesson.

### SSA

**Static Single Assignment. Every name is assigned exactly once in the text of the function.**

A variable that was written three times becomes three separate names. That sounds like bookkeeping and it is actually the thing that makes optimisation possible, because once a name has one definition, finding that definition is a pointer dereference rather than a search. Static is the load bearing word: a definition inside a loop runs many times, it just appears once.

First met in T05. See also [SSA name](#ssa-name), [phi node](#phi-node), [out of SSA](#out-of-ssa). In the source: [`gcc/tree.def:1035@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree.def#L1035).

### SSA name

**One version of one variable, written `s_4` in a dump.**

The part before the underscore is the variable it came from and the number after it is the version, so `s_4` and `s_7` are the same variable at two different points in the function. Versions are handed out from a single counter and are never reused, so the numbers in a dump are not consecutive and the gaps mean nothing. A name knows the single statement that defines it, and that is the property everything else is built on.

Also written `SSA_NAME`, version. First met in T05. See also [SSA](#ssa), [definition](#definition), [phi node](#phi-node). In the source: [`gcc/tree-ssanames.cc:351@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-ssanames.cc#L351).

### definition

**The single statement that gives an SSA name its value.**

Every SSA name has exactly one, and going from a name to it is one step. That is the difference between SSA and what came before, where answering the same question meant walking backwards through the CFG and giving up at the first join.

Also written def. First met in T05. See also [SSA name](#ssa-name), [use](#use).

### use

**Any place an SSA name is read.**

The uses of a name are kept as a list hanging off the name, so going the other way is also one step. A pass that changes a value walks that list to find everything affected, and a name whose use list is empty is dead, which is the entire algorithm behind one of the passes that runs most often.

Also written def-use chain. First met in T05. See also [definition](#definition), [SSA name](#ssa-name).

### default definition

**The version of a name that was already there when the function started.**

It is written with a `(D)` after it, as in `n_5(D)`, and no statement anywhere defines it. Parameters have one, because their value arrives from the caller. So does a local read before it was ever written, which is the compiler saying out loud that your program has undefined behaviour and it is going to carry on anyway. Seeing a `(D)` on something that is not a parameter is worth a second look.

Also written `(D)`. First met in T05. See also [SSA name](#ssa-name), [definition](#definition).

### phi node

**A statement at the top of a block that picks a value based on which edge you came in on.**

It exists because SSA needs one name per definition and a join point has two definitions arriving. A phi is not a real instruction and nothing computes it, it is a note saying that this name is whichever of these names the path you took defined. It has exactly one argument per incoming edge and the arguments are positional, which is why deleting an edge means editing every phi in the block.

Also written `PHI`, `gphi`. First met in T05. See also [SSA name](#ssa-name), [basic block](#basic-block), [out of SSA](#out-of-ssa). In the source: [`gcc/gimple.h:474@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimple.h#L474).

### out of SSA

**The pass that removes phi nodes by putting real copies on the incoming edges.**

It has to happen because no machine has an instruction that means whichever way you came. Doing it naively costs a copy per phi argument, so the real pass spends most of its effort proving that two SSA names can share one location and dropping the copy. This is the last thing that happens on GIMPLE before expand.

First met in T05. See also [phi node](#phi-node), [SSA](#ssa), [expand](#expand).
