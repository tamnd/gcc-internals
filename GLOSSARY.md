# Glossary

One definition per term, in one place, so a lesson can use a word without stopping to explain it and without assuming you remember it from forty lessons ago. Lessons link into this file rather than repeating themselves.

The order below is the order you meet these things, not alphabetical, because reading it straight through is a reasonable thing to do. If you are looking one up, the index is next.

This file is generated from `gxray/glossary.py`. Edit that and run `just build-glossary`.

## Index

[GENERIC](#generic) | [GIMPLE](#gimple) | [IRA](#ira) | [LRA](#lra) | [RTL](#rtl) | [RTX](#rtx) | [SSA](#ssa) | [SSA name](#ssa-name) | [allocno](#allocno) | [alternative](#alternative) | [assembler directive](#assembler-directive) | [back end](#back-end) | [basic block](#basic-block) | [bootstrap](#bootstrap) | [bubbling](#bubbling) | [build config](#build-config) | [cc1](#cc1) | [checking build](#checking-build) | [collect2](#collect2) | [constraint](#constraint) | [control flow graph](#control-flow-graph) | [cross compiler](#cross-compiler) | [current function](#current-function) | [default definition](#default-definition) | [define_insn](#define_insn) | [definition](#definition) | [dominance](#dominance) | [driver](#driver) | [dump file](#dump-file) | [edge](#edge) | [expand](#expand) | [final](#final) | [front end](#front-end) | [garbage collector](#garbage-collector) | [gate](#gate) | [generated file](#generated-file) | [gengtype](#gengtype) | [gimplification](#gimplification) | [hard register](#hard-register) | [immediate dominator](#immediate-dominator) | [insn](#insn) | [interference](#interference) | [live range](#live-range) | [loop](#loop) | [machine description](#machine-description) | [machine mode](#machine-mode) | [middle end](#middle-end) | [mode iterator](#mode-iterator) | [optimization level](#optimization-level) | [out of SSA](#out-of-ssa) | [out of tree build](#out-of-tree-build) | [output template](#output-template) | [param](#param) | [pass](#pass) | [pass manager](#pass-manager) | [phi node](#phi-node) | [poly_int](#poly_int) | [port](#port) | [pseudo register](#pseudo-register) | [register allocation](#register-allocation) | [register class](#register-class) | [register pressure](#register-pressure) | [section](#section) | [spec](#spec) | [spill](#spill) | [stage comparison](#stage-comparison) | [stamp file](#stamp-file) | [target hook](#target-hook) | [target triple](#target-triple) | [temporary](#temporary) | [three address form](#three-address-form) | [tree](#tree) | [use](#use) | [wide_int](#wide_int)

## Reading the source

Words you need before you can read a page of GCC, as opposed to a page of GCC's output. Z01 is the lesson, and it is the first one in the book for a reason.

### gengtype

**A program that runs during GCC's build, reads the `GTY` markers out of the source, and writes the garbage collector's marking code.**

This is why `GTY(())` is on almost every declaration in the tree and why it does nothing at run time. GCC's collector has to know the shape of every type it might be asked to mark, and rather than maintain that by hand next to four hundred struct definitions, the build generates it. `gengtype` parses a deliberately small subset of C++, which is the real reason some declarations in GCC are written in an odd way: they are written so that `gengtype` can read them. When you see `GTY((user))` somebody is telling it to keep out because they wrote the marking code themselves.

Also written `GTY`, `gtype-desc.cc`. Taught in Z01. See also [garbage collector](#garbage-collector).

### garbage collector

**GCC collects its own memory, and most of the compiler's data structures are allocated in it.**

A compiler builds enormous graphs with no clear owner, so GCC has a mark and sweep collector and `ggc_alloc` rather than `new`. Two things follow that you will trip over. Containers cannot be the standard library's, because the standard library's allocator is not this one, which is why `vec` and `hash_map` exist. And a pointer the collector cannot see is a pointer to freed memory after the next collection, which is why the `GTY` markers matter and why a root that lives in a local variable has to be registered.

Also written `ggc`, `ggc_alloc`. Taught in Z01. See also [gengtype](#gengtype).

### checking build

**A GCC built with `--enable-checking`, where the accessor macros verify what you claim before they read.**

Dozens of macros in `tree.h` are defined twice, once to check and once not, and a release build gets the second one. `TREE_TYPE` on a node with no type is a clean crash naming the file and line in a checking build and reads a field off the wrong arm of a union in a release build. The same split is why `gcc_assert` and `gcc_checking_assert` are different spellings: the first survives into a release build and the second does not. Anybody working on GCC builds with checking on, and any bug report about a wrong answer will be asked to reproduce with it.

Also written `--enable-checking`, `ENABLE_TREE_CHECKING`. Taught in Z01. See also [tree](#tree). In the source: [`gcc/tree.h:330@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree.h#L330).

### current function

**`cfun`, the function GCC is compiling right now, reachable from anywhere without being passed.**

Almost every pass works on one function at a time, and rather than thread a pointer through every helper in the middle end, GCC keeps it in a global. `FOR_EACH_BB_FN (bb, cfun)` is the shape you will read most often, and the `_FN` suffix on a name means the version that takes the function explicitly, which is the one an interprocedural pass needs. The trap is that `cfun` is null outside a function, so code that runs at the interprocedural level cannot assume it.

Also written `cfun`, `struct function`. Taught in Z01. See also [basic block](#basic-block), [pass](#pass).

### poly_int

**An integer that may not be known until the program runs, written as a constant plus coefficients.**

Scalable vector targets like SVE and RVV do not tell the compiler how wide a vector register is, so sizes and offsets that used to be integers cannot be. A `poly_int` is a small polynomial in indeterminates the hardware picks. The consequence for reading is in the comparisons: `a == b` is not a question you can always answer, so GCC has `known_eq`, `maybe_ne`, `known_lt` and the rest, and each one says what it does with the uncertain case. On a fixed vector target every `poly_int` has one coefficient and it all compiles to the obvious thing.

Also written `poly_int64`, `known_eq`, `maybe_ne`. Taught in Z01. See also [machine mode](#machine-mode). In the source: [`gcc/poly-int.h:374@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/poly-int.h#L374).

### wide_int

**An integer as wide as the target needs, which is not the same as as wide as the host has.**

GCC running on a 64 bit host compiles for targets with 128 bit integers, so constant folding cannot use the host's arithmetic. `wide_int` is a fixed precision integer carrying enough words for the widest type in play, `widest_int` is wider still and used where an intermediate result might not fit, and the operations live in the `wi::` namespace rather than as operators. When you see `wi::to_widest (value)` in a pass, that is a target constant being brought into a form the compiler can do arithmetic on safely.

Also written `widest_int`, `wi::`. Taught in Z01. See also [tree](#tree). In the source: [`gcc/wide-int.h:23@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/wide-int.h#L23).

## Finding things in the tree

Words about the source tree itself rather than about compiling. Z02 is the lesson, and these three are the ones that cost a reader an afternoon if nobody tells them.

### generated file

**A source file that a program in the GCC tree writes during the build, rather than a file anybody wrote.**

A dozen programs under `gcc/` whose names start with `gen` read the machine descriptions, `match.pd`, the `.opt` files and the `GTY` markers, and write C++ into the build directory. `insn-recog.cc` is the biggest of them and can run to hundreds of thousands of lines. The consequence is that a backtrace or a dump line can name a file that is not in the tree at all, and searching for it finds nothing. The route is to work out which generator wrote it and read that generator's input, which is where the change you want to make actually goes. `gxray.layout.generated` will do the lookup for you.

Also written `insn-recog.cc`, `gimple-match-N.cc`, `options.cc`. Taught in Z02. See also [machine description](#machine-description), [gengtype](#gengtype). In the source: [`gcc/genrecog.cc:21@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/genrecog.cc#L21).

### port

**Everything GCC needs in order to emit code for one target, which is one directory under `gcc/config` with a machine description in it.**

The count everybody quotes is the number of directories under `gcc/config`, and it is wrong, because three of those directories are shared operating system support rather than targets. What makes a port a port is a `.md` file. A real port is that machine description plus a `target.cc` full of hooks, a `target.h` of macros, an `.opt` file of target specific flags, and usually a pile of built in function definitions. `gcc/config/aarch64` and `gcc/config/i386` are the two most actively worked on and are both worth a look for how differently two people can solve the same problem.

Also written target, back end for a target. Taught in Z02. See also [machine description](#machine-description), [back end](#back-end), [target hook](#target-hook).

### target hook

**A function pointer the middle end calls when the answer depends on the target, filled in by the port.**

The middle end cannot know whether an unaligned load is cheap or how arguments are passed, so wherever it needs a target's opinion it calls through `targetm`, a big struct of function pointers that every port fills in from `target-def.h`. Reading a port is mostly reading its hooks. The useful habit is the other direction: when a pass does something that looks target specific, find the `targetm.` call in it, then find that hook in the port you care about, and you are looking at the exact line that decided.

Also written `targetm`, `TARGET_*` macro, `target.def`. Taught in Z02. See also [port](#port), [back end](#back-end). In the source: [`gcc/target.h:337@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/target.h#L337).

## Driving the compiler

What actually runs when you type `gcc`, and how to make it show you its work. T01 and T04 are the lessons that cover this ground.

### driver

**The program called `gcc`, which compiles nothing and runs the things that do.**

It reads your command line, works out which language you are in, and then runs a compiler, an assembler and a linker as separate processes. This is worth knowing early because almost every option you pass to `gcc` is really an option for one of those, and `gcc -v` prints the four command lines it built so you can see which. The driver is a few thousand lines of argument shuffling and it is not where the compiler lives.

Also written `gcc`, `gcc.cc`. Taught in T01. See also [cc1](#cc1), [spec](#spec).

### cc1

**The actual C compiler. One process, one translation unit, C in and assembly out.**

Everything this course is about happens inside `cc1`. It is not on your PATH and it is not meant to be run by hand, which is why `gcc -v` is how you find it. There is one of these per language: `cc1plus` for C++, `f951` for Fortran, and so on, all built from the same middle end and back end with a different front end bolted on the front.

Taught in T01. See also [driver](#driver), [spec](#spec), [front end](#front-end). In the source: [`gcc/gcc.cc:1234@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gcc.cc#L1234).

### spec

**A small string language the driver uses to build the command lines it runs.**

A spec is a template full of conditionals like `%{save-temps:...}` that expands into arguments. They are almost unreadable and you will not need to write one, but recognising the syntax stops `gcc -dumpspecs` from looking like line noise, and knowing they exist explains why an option you passed shows up in a completely different form in the `cc1` command line.

Taught in T01. See also [driver](#driver), [cc1](#cc1).

### collect2

**A wrapper the driver runs instead of the linker, which then runs the linker.**

Its job is static constructors. On a target whose linker cannot collect them by itself, `collect2` links once, reads the symbol table looking for constructor and destructor symbols, generates a small C file holding a table of them, compiles it and links again. On a modern target with `.init_array` none of that is needed and it passes almost everything straight through, which is why it looks like a pointless extra process in `-###` output. It is still there because removing a program from the middle of every link on every target is not the kind of change anybody makes casually.

Taught in T01. See also [driver](#driver), [cc1](#cc1). In the source: [`gcc/collect2.cc:25@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/collect2.cc#L25).

### dump file

**A text file GCC writes showing the function after one particular pass.**

Ask for one with `-fdump-tree-ssa` or `-fdump-rtl-expand` and GCC writes the whole function out in that pass's representation. This is the main window this course looks through, and the important thing about it is that it is a rendering rather than the data structure: the dump has no explicit edges, no pointers, and no types unless you ask for them with a modifier. Add `-graph` and you get a `.dot` beside it that does have the edges.

Also written `-fdump-tree-all`. Taught in T01. See also [pass](#pass). In the source: [`gcc/dumpfile.h:522@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/dumpfile.h#L522).

### pass

**One transformation or analysis, run over one function, in a fixed order.**

The whole middle end and back end is a list of these. A pass has a name, a gate that decides whether it runs at all, and an execute function. The list is much longer than people expect and most of what it contains does nothing at `-O0`, which is why the count you get from `-fdump-passes` depends on the optimisation level. Passes are the unit everything else in this course is organised around, because a dump file is named after one.

Taught in T04. See also [dump file](#dump-file), [pass manager](#pass-manager). In the source: [`gcc/tree-pass.h:73@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-pass.h#L73).

### pass manager

**The loop that walks the pass list and runs each pass on each function.**

It is also the thing that opens the dump file, checks the gate, verifies the IR afterwards when checking is on, and keeps track of which analyses are still valid. When a pass appears to have been skipped, the pass manager is where the answer is, and the answer is almost always the gate.

Taught in T04. See also [pass](#pass). In the source: [`gcc/passes.cc:2579@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/passes.cc#L2579).

### gate

**The method a pass answers with yes or no when asked whether it should run.**

It is a virtual function on the pass, so the condition lives with the pass rather than in a table somewhere, and it is asked again for every function. That is why the answer is not a property of your command line: two functions in one file can get different answers from the same gate. `-fdump-passes` prints the answer for one function at one moment, and a gate that depends on how far compilation has got, such as the one guarding the passes that run after register allocation, will print the answer for that moment rather than for the moment the pass is reached.

Taught in T04. See also [pass](#pass), [pass manager](#pass-manager). In the source: [`gcc/tree-pass.h:90@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-pass.h#L90).

### optimization level

**Four integers, and a table that says what each combination of them turns on.**

`-O2` is not a thing the compiler has. What it has is `optimize`, `optimize_size`, `optimize_fast` and `optimize_debug`, and `-O2` is the command line spelling of setting the first to 2 and the rest to 0. A table of a hundred and fourteen entries then says, for each option, which combinations turn it on. `-Os` and `-Oz` both set `optimize` to 2 and differ only in `optimize_size` being 1 or 2, which is why the flag table cannot tell them apart. A target gets its own table on top of the shared one, so the answer is not the same on two machines.

Taught in T06. See also [param](#param), [pass](#pass). In the source: [`gcc/opts.cc:781@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/opts.cc#L781).

### param

**A number the optimizer consults, spelled `--param=name=value`.**

Where a switch says whether to do something, a param says how much. Inlining size limits, unrolling limits, the number of times a loop is peeled. There are three hundred and twenty three of them and the optimization level sets several, so two levels can run exactly the same passes with the same switches and still produce different code because a threshold moved.

Taught in T06. See also [optimization level](#optimization-level). In the source: [`gcc/params.opt:24@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/params.opt#L24).

### front end

**The half of the compiler that knows a language, as opposed to the half that does not.**

A front end parses one language and hands the middle end a function body in GENERIC. Everything after that point is shared, which is the single most important structural fact about GCC: twelve languages, one optimiser, one code generator. It is also why an optimisation bug is almost never a C bug.

Taught in T01. See also [GENERIC](#generic), [middle end](#middle-end).

### middle end

**Everything between the front end and the back end, where the optimisation happens.**

It takes GENERIC in and hands RTL out, and in between it works on GIMPLE in SSA form. The name is a joke that stuck, since a thing with two ends does not have a middle, but it is what everybody calls it and what the source calls it.

Taught in T01. See also [front end](#front-end), [GIMPLE](#gimple), [back end](#back-end).

### back end

**The half that knows a machine, from RTL down to the assembly text.**

It is generated, mostly. A target is described by a `.md` file full of patterns and a `.cc` file full of hooks, and a pile of build time programs turn those into the C that actually runs. This is why grepping for the function that emitted an instruction so often lands you in a file that does not exist in the source tree.

Taught in T01. See also [RTL](#rtl), [middle end](#middle-end).

## The four shapes a function takes

The same function, written down four different ways on its way to assembly. T02, T03 and T07 are the lessons.

### tree

**GCC's universal node type. One tagged union for every kind of thing.**

A `tree` is a pointer to a union with a code on the front telling you which member is live. Types are trees, declarations are trees, constants are trees, and expressions are trees, which is why the accessor macros are shouty and everywhere. It is the oldest data structure in the compiler and reading anything in the front end means being comfortable with it.

Also written `tree_node`. Taught in T02. See also [GENERIC](#generic), [GIMPLE](#gimple). In the source: [`gcc/tree-core.h:2186@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-core.h#L2186).

### GENERIC

**The language independent tree a front end hands over. Still a tree, still nested.**

GENERIC is what the C parser produces: a whole function as one expression tree, with loops and conditionals and function calls nested inside each other exactly the way you wrote them. It is close enough to the source that you can read your program back out of it, which is the point, and far enough from the source that a Fortran front end can produce the same thing.

Taught in T02. See also [tree](#tree), [GIMPLE](#gimple), [gimplification](#gimplification).

### GIMPLE

**A flattened three address form. One operation per statement, no nesting.**

Every expression is broken up until each statement does exactly one thing, with temporaries invented to hold the middle results. This is the representation the entire middle end works on, and the reason for it is that a pass that has to handle arbitrary nesting is a pass nobody can write correctly. What you lose is readability, which is why the dumps look like somebody ran your code through a shredder.

Taught in T02. See also [GENERIC](#generic), [gimplification](#gimplification), [SSA](#ssa), [basic block](#basic-block). In the source: [`gcc/gimple.h:222@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimple.h#L222).

### gimplification

**The pass that turns GENERIC into GIMPLE by flattening the nesting out.**

It walks the tree and, every time it finds an expression that is too complicated to be a statement on its own, it invents a temporary, assigns the sub-expression to it, and puts the assignment before. Everything else about GIMPLE follows from that one move. The function that does it is one of the largest switch statements in the compiler and it is worth looking at once.

Taught in T03. See also [GENERIC](#generic), [GIMPLE](#gimple). In the source: [`gcc/gimplify.cc:20296@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimplify.cc#L20296).

### three address form

**At most one operation per statement, and every operand already a value.**

The name is older than GCC and comes from the shape of the statement: a destination and two sources, three addresses. What it really means is that an operand may be a variable or a constant and may not be another expression, which is one predicate in the source and the entire reason the middle end is writable. A pass reads one operator and two operands and is finished, rather than recursing into a tree of unknown depth.

Also written `is_gimple_val`. Taught in T03. See also [GIMPLE](#gimple), [gimplification](#gimplification), [temporary](#temporary). In the source: [`gcc/gimple-expr.cc:836@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimple-expr.cc#L836).

### temporary

**A variable gimplification invented to hold a value that had nowhere to go.**

Printed as `_1`, `_2` and so on in the dumps, and there is one for every interior node of an expression that had to be flattened. They are not in your source and they are not a sign that anything went wrong. The related name `D.4635` is a different thing: that is the slot a function returns through, made by the front end for every function rather than by gimplification for a particular expression.

Taught in T03. See also [gimplification](#gimplification), [three address form](#three-address-form), [SSA name](#ssa-name). In the source: [`gcc/gimplify.cc:683@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimplify.cc#L683).

### RTL

**Register Transfer Language. Machine operations on unlimited virtual registers.**

RTL is the back end's representation and it is a Lisp-like expression describing what an instruction does to registers and memory, not what the instruction is called. A target matches those expressions against its patterns to pick real instructions. The move from GIMPLE to RTL is the point where the compiler stops being about your program and starts being about a machine.

Also written `rtx`. Taught in T02. See also [expand](#expand), [back end](#back-end). In the source: [`gcc/rtl.h:314@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/rtl.h#L314).

### expand

**The pass that turns GIMPLE into RTL, one statement at a time.**

It is the hinge of the whole compiler and it is not reversible: after expand there is no going back to GIMPLE, so every optimisation that wants to reason about your program rather than about a machine has to have happened already. It is also where the stack frame gets laid out and where a virtual register first appears.

Taught in T07. See also [GIMPLE](#gimple), [RTL](#rtl). In the source: [`gcc/cfgexpand.cc:7015@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/cfgexpand.cc#L7015).

### RTX

**One node of RTL. A code, a machine mode, and some operands.**

Every parenthesis you see in an RTL dump is one of these and they are all the same C struct, which is why the dumps look so uniform. The code says what kind of thing it is, `plus` or `reg` or `set`, and it is one of 203 codes listed in one file. There is no separate type for an instruction and an expression: an insn is an RTX whose code happens to be `insn`.

Also written `rtx`, `rtx_def`. Taught in T07. See also [RTL](#rtl), [machine mode](#machine-mode), [insn](#insn). In the source: [`gcc/rtl.h:319@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/rtl.h#L319).

### machine mode

**The size and kind of a value, written after the colon in a dump.**

`SI` is four bytes of integer, `DI` is eight, `QI` is one, and the letters are historical rather than descriptive. Every RTX carries one, including ones where it means nothing, and the mode is what stops the back end from having to look at a type. `CC` and its variants are the odd ones: they are the mode of a condition code, and what a target keeps in one is up to the target.

Also written `SImode`, `machine_mode`. Taught in T07. See also [RTX](#rtx), [RTL](#rtl). In the source: [`gcc/machmode.def:211@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/machmode.def#L211).

### pseudo register

**A register the compiler invented, numbered from the first free number up.**

Expand pretends the machine has as many registers as it wants and hands them out in order, so the numbers you see in an early dump are a counter and nothing more. The pretence is deliberate: it lets expand pick instructions without also solving register allocation, and it lasts until the allocator runs about twenty passes later. Where the numbering starts is a target's business, which is why the same program starts at 98 on one machine and 134 on another.

Also written `gen_reg_rtx`, virtual register. Taught in T07. See also [RTX](#rtx), [expand](#expand), [hard register](#hard-register), [register allocation](#register-allocation). In the source: [`gcc/emit-rtl.cc:1188@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/emit-rtl.cc#L1188).

### insn

**One entry in the chain of things the function will do, in order.**

After expand a function is a doubly linked list of these rather than a graph of blocks, though the blocks are still recorded on the side. Most entries are not instructions at all: notes, labels and debug entries share the chain, and in a small function they outnumber the real work. The spelling is missing a vowel because it is older than filenames that could hold one.

Also written `rtx_insn`. Taught in T07. See also [RTX](#rtx), [RTL](#rtl), [basic block](#basic-block). In the source: [`gcc/rtl.def:145@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/rtl.def#L145).

## The shape of a function

Blocks, edges and the questions you can ask about them. T05 needs the first four of these, G02 and G03 go deeper.

### basic block

**A run of statements with one way in at the top and one way out at the bottom.**

Nothing branches into the middle of a block and nothing branches out of the middle, so if the first statement runs then all of them run. That guarantee is what makes a block the unit every analysis works in. In a dump they are the things labelled `<bb 3>`, and the two numbered 0 and 1 are the entry and exit blocks, which hold no statements and exist so that every real block has somewhere to come from and go to.

Also written `<bb 3>`. Taught in T05. See also [control flow graph](#control-flow-graph), [edge](#edge). In the source: [`gcc/basic-block.h:117@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/basic-block.h#L117).

### control flow graph

**The blocks of a function plus the edges saying which can follow which.**

The important thing about the CFG is that it is a real data structure with real edges, and the text dump is not it. A fallthrough from one block to the next shows up in the dump as nothing at all, because there is no goto to print, so counting edges by reading a dump gives the wrong answer. Ask for `-graph` and GCC writes the edges out properly.

Also written CFG. Taught in T05. See also [basic block](#basic-block), [edge](#edge), [dominance](#dominance).

### edge

**One possible jump from the end of one block to the start of another.**

Edges carry flags, and the flags are where the interesting cases live: a back edge closes a loop, an abnormal edge is one the compiler cannot reason about normally, an EH edge is the path taken when something throws. A block with two outgoing edges ends in a condition, and which edge is the true one is a flag rather than an ordering.

Taught in T05. See also [basic block](#basic-block), [control flow graph](#control-flow-graph), [loop](#loop).

### dominance

**Block A dominates block B if every path to B goes through A first.**

This is the question the whole middle end keeps asking, because it is how you know a value is available: if the block that defines it dominates the block that uses it, the definition has definitely already run. Entry dominates everything. A block always dominates itself, which sounds like a technicality and matters constantly.

Taught in T05. See also [immediate dominator](#immediate-dominator), [basic block](#basic-block), [SSA](#ssa). In the source: [`gcc/dominance.cc:856@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/dominance.cc#L856).

### immediate dominator

**The closest block that dominates a given block, not counting the block itself.**

Every block except entry has exactly one, which means the dominance relation of a whole function fits in one number per block and the dominator tree is that array read as a tree. GCC computes it lazily and a pass has to ask for it, which is why you see `calculate_dominance_info` at the top of so many passes.

Also written idom, dominator tree. Taught in T05. See also [dominance](#dominance).

### loop

**A back edge and everything that can reach it without leaving.**

GCC finds loops rather than being told about them, which is why a loop written with `goto` and a loop written with `for` end up identical here, and why a `for` loop that the compiler proved runs a fixed number of times may not be a loop by the time you look. Loops nest, and the nesting is a tree with a fake outermost loop at the root standing for the function.

Taught in T05. See also [edge](#edge), [control flow graph](#control-flow-graph). In the source: [`gcc/cfgloop.h:120@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/cfgloop.h#L120).

## SSA

The one idea that makes the middle end tractable, and the vocabulary that comes with it. T05 is the lesson.

### SSA

**Static Single Assignment. Every name is assigned exactly once in the text of the function.**

A variable that was written three times becomes three separate names. That sounds like bookkeeping and it is actually the thing that makes optimisation possible, because once a name has one definition, finding that definition is a pointer dereference rather than a search. Static is the load bearing word: a definition inside a loop runs many times and appears once.

Taught in T05. See also [SSA name](#ssa-name), [phi node](#phi-node), [out of SSA](#out-of-ssa). In the source: [`gcc/tree.def:1035@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree.def#L1035).

### SSA name

**One version of one variable, written `s_4` in a dump.**

The part before the underscore is the variable it came from and the number after it is the version, so `s_4` and `s_7` are the same variable at two different points in the function. Versions are handed out from a single counter and are never reused, so the numbers in a dump are not consecutive and the gaps mean nothing. A name knows the single statement that defines it, and that is the property everything else is built on.

Also written `SSA_NAME`, version. Taught in T05. See also [SSA](#ssa), [definition](#definition), [phi node](#phi-node). In the source: [`gcc/tree-ssanames.cc:351@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-ssanames.cc#L351).

### definition

**The single statement that gives an SSA name its value.**

Every SSA name has exactly one, and going from a name to it is one step. That is the difference between SSA and what came before, where answering the same question meant walking backwards through the CFG and giving up at the first join.

Also written def. Taught in T05. See also [SSA name](#ssa-name), [use](#use).

### use

**Any place an SSA name is read.**

The uses of a name are kept as a list hanging off the name, so going the other way is also one step. A pass that changes a value walks that list to find everything affected, and a name whose use list is empty is dead, which is the entire algorithm behind one of the passes that runs most often.

Also written def-use chain. Taught in T05. See also [definition](#definition), [SSA name](#ssa-name).

### default definition

**The version of a name that was already there when the function started.**

It is written with a `(D)` after it, as in `n_5(D)`, and no statement anywhere defines it. Parameters have one, because their value arrives from the caller. So does a local read before it was ever written, which is the compiler saying out loud that your program has undefined behaviour and it is going to carry on anyway. Seeing a `(D)` on something that is not a parameter is worth a second look.

Also written `(D)`. Taught in T05. See also [SSA name](#ssa-name), [definition](#definition).

### phi node

**A statement at the top of a block that picks a value based on which edge you came in on.**

It exists because SSA needs one name per definition and a join point has two definitions arriving. A phi is not a real instruction and nothing computes it, it is a note saying that this name is whichever of these names the path you took defined. It has exactly one argument per incoming edge and the arguments are positional, which is why deleting an edge means editing every phi in the block.

Also written `PHI`, `gphi`. Taught in T05. See also [SSA name](#ssa-name), [basic block](#basic-block), [out of SSA](#out-of-ssa). In the source: [`gcc/gimple.h:474@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gimple.h#L474).

### out of SSA

**The pass that removes phi nodes by putting real copies on the incoming edges.**

It has to happen because no machine has an instruction that means whichever way you came. Doing it naively costs a copy per phi argument, so the real pass spends most of its effort proving that two SSA names can share one location and dropping the copy. This is the last thing that happens on GIMPLE before expand.

Taught in T05. See also [phi node](#phi-node), [SSA](#ssa), [expand](#expand).

## Registers, and running out of them

What the back end does about the fact that the expander invented more values than the machine has places to put them. T08 is the lesson.

### hard register

**A register the machine actually has, numbered below `FIRST_PSEUDO_REGISTER`.**

The number is an index into a table the target defines, so register 3 means one thing on x86-64 and another on aarch64, and nothing outside the target can turn it into a name. A target has fewer of them available than it has in total, because the stack pointer, usually the frame pointer, and sometimes a platform reserved register are spoken for before the allocator gets a look in.

Also written `FIRST_PSEUDO_REGISTER`. Taught in T08. See also [pseudo register](#pseudo-register), [register class](#register-class), [register allocation](#register-allocation). In the source: [`gcc/config/i386/i386.h:991@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/config/i386/i386.h#L991).

### register class

**A named set of hard registers, because an instruction will not accept an arbitrary register.**

`GENERAL_REGS` is the one integer code lives in. Targets define more, some of them very small, and an instruction that demands a one register class forces the allocator's hand whatever the pressure is. A pressure class is the subset IRA bothers tracking occupancy for, chosen so the tracking stays cheap.

Also written `GENERAL_REGS`, pressure class. Taught in T08. See also [hard register](#hard-register), [register pressure](#register-pressure). In the source: [`gcc/hard-reg-set.h:573@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/hard-reg-set.h#L573).

### register allocation

**Deciding which values get a hard register and which get a stack slot.**

It is the pass that makes the expander's pretence true. Everything before it in the back end may use as many pseudos as it likes, and after it there are no pseudos left. GCC does it in two stages, IRA and then LRA, and it is one of the most expensive things the compiler does, because the second stage is a loop that can make more work for itself.

Taught in T08. See also [IRA](#ira), [LRA](#lra), [spill](#spill), [pseudo register](#pseudo-register).

### allocno

**A pseudo register within one region of the function. The thing IRA actually colours.**

Not the same as a pseudo, and that is the first thing to get straight about an IRA dump. IRA splits a function into regions along the loop tree, and a value live across a loop boundary gets one allocno inside and another outside, which can be given different registers with a copy between them. So thirty pseudos can be sixty two allocnos. The dump writes one as `a58(r159,l0)`: allocno 58, pseudo 159, region 0.

Also written `ira_allocno`. Taught in T08. See also [pseudo register](#pseudo-register), [IRA](#ira), [live range](#live-range). In the source: [`gcc/ira-int.h:274@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/ira-int.h#L274).

### live range

**The stretch of program points where a value has to exist.**

Written `[4..7] [12..40]` in a dump, closed intervals, and a value can have several with gaps between them. Program points are not insn numbers. IRA numbers them by walking the insns and then throws away every point at which nothing was born and nothing died, which typically cuts the numbering by two thirds, so the numbers only mean anything within one dump of one function on one target.

Also written `live_range`. Taught in T08. See also [interference](#interference), [register pressure](#register-pressure), [allocno](#allocno). In the source: [`gcc/ira-int.h:198@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/ira-int.h#L198).

### interference

**Two values are alive at the same point, so they cannot share a register.**

Take every value as a node and put an edge between any two whose live ranges overlap, and you have the interference graph. Allocation is colouring it with as many colours as the target has registers. That problem is NP complete in general, which is why the allocator is a pile of heuristics rather than an algorithm.

Also written conflict, interference graph. Taught in T08. See also [live range](#live-range), [register pressure](#register-pressure), [spill](#spill). In the source: [`gcc/ira-conflicts.cc:570@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/ira-conflicts.cc#L570).

### register pressure

**How many values are alive at the busiest point, counted per register class.**

Printed as `Pressure: GENERAL_REGS=22` in an IRA dump, per region. Pressure above the number of available registers means something has to go to memory. Pressure at or below it does not promise everything fits, because a class constraint or a value that needs a register pair can still fail, but it is the number to look at first and it is the number that decides whether two targets compiling the same source come out the same.

Taught in T08. See also [register class](#register-class), [spill](#spill), [interference](#interference). In the source: [`gcc/ira-color.cc:3654@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/ira-color.cc#L3654).

### spill

**Giving a value a stack slot instead of a register, and loading it back at every use.**

It is what the allocator does when it loses. The cost is not one store, it is a store and then a load at every subsequent use, and if that happens inside a hot loop it is the difference between fast code and slow code. Which value gets picked is a cost model rather than a coin toss: something used once outside a loop is a much better victim than something touched every iteration.

Also written spilling, spilled. Taught in T08. See also [register pressure](#register-pressure), [register allocation](#register-allocation), [LRA](#lra). In the source: [`gcc/lra-spills.cc:659@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/lra-spills.cc#L659).

### IRA

**Integrated Register Allocator. The pass that decides where every value goes.**

It builds the interference graph, colours it, and records the answer, but it does not rewrite a single instruction. Its output is a decision, written to the dump as the `Disposition:` block, and it is the shortest honest answer to what happened to your registers. The pass runs immediately before the one that carries the decision out.

Also written `pass_ira`. Taught in T08. See also [LRA](#lra), [allocno](#allocno), [register allocation](#register-allocation). In the source: [`gcc/ira.cc:6202@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/ira.cc#L6202).

### LRA

**Local Register Allocator. The pass that makes IRA's decision true, and fixes it where it was not.**

It is still called `reload` in the pass list, which is the name of the thing it replaced in 2013, and it does no reloading in the old sense. It loops: satisfy every instruction's operand constraints, which can require inventing a fresh pseudo to hold a reloaded value, which makes the live ranges wrong, so recompute them and reassign, and go round again. That loop is why register allocation is the expensive part of compiling.

Also written `pass_reload`, reload. Taught in T08. See also [IRA](#ira), [spill](#spill), [register allocation](#register-allocation). In the source: [`gcc/lra.cc:2420@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/lra.cc#L2420).

## Becoming text

The last pass in the compiler, the file it writes, and the part of the back end that is a program rather than a table. T09 is the lesson.

### final

**The pass that walks the insn chain one last time and prints each insn as text.**

It is the end of the line. Every pass before it transformed a function into another function, and this one turns it into characters. It is a short pass because almost all of the work is delegated: the pattern that matched the insn back at recognition time knows what to print, and `final` asks it. What `final` itself deals with is everything around the instructions, which is labels, alignment, the function prologue and epilogue markers, debug and unwind information, and the decision about which of those to skip.

Also written `pass_final`. Taught in T09. See also [machine description](#machine-description), [output template](#output-template), [assembler directive](#assembler-directive). In the source: [`gcc/final.cc:4340@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/final.cc#L4340).

### machine description

**The `.md` files that describe a target's instructions to the compiler.**

One directory per target under `gcc/config`, and the `.md` files in it are the largest part of a back end. They are s-expressions with two additions: output templates written in braces can contain C, and names can contain angle bracket placeholders that are expanded at build time. Nothing in them is read at compile time. A dozen generator programs turn them into C during the GCC build, so a pattern is a table entry and a function by the time your compiler runs.

Also written `.md` file, machine description file. Taught in T09. See also [define_insn](#define_insn), [output template](#output-template), [mode iterator](#mode-iterator).

### define_insn

**One pattern: what an insn may look like, what it costs, and what to print for it.**

Four parts. An RTL template that an insn has to match, a condition that has to be true, an output template or the C that produces one, and a list of attributes. Recognition matches an insn against every pattern and records which one won, and `final` prints what that pattern says. A name beginning with a star has no `gen_` function, which means nothing can ask for it by name and only recognition will ever pick it.

Also written pattern, `define_insn_and_split`. Taught in T09. See also [machine description](#machine-description), [output template](#output-template), [alternative](#alternative). In the source: [`gcc/rtl.def:885@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/rtl.def#L885).

### output template

**The string a pattern prints, with `%0` and friends standing in for the operands.**

`add\t%w0, %w1, %w2` is one. `output_asm_insn` walks it, copies the literal characters, and calls the target's operand printer for each `%`. A pattern can have a table of these with one row per alternative, or a single string, or a block of C that returns a string, and the third form is how a pattern picks its text at run time from something only the compiler knows.

Also written `output_asm_insn`. Taught in T09. See also [define_insn](#define_insn), [alternative](#alternative), [constraint](#constraint). In the source: [`gcc/final.cc:3428@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/final.cc#L3428).

### constraint

**A letter saying what an operand has to be for an alternative to be usable.**

`r` is a general register, `m` is memory, `i` is an immediate, and every target adds its own for the shapes its instructions accept. A predicate says what an insn may match, and a constraint says what the register allocator has to arrange before it can be printed. The distinction matters because the allocator reads constraints and nothing else.

Also written operand constraint. Taught in T09. See also [alternative](#alternative), [define_insn](#define_insn), [register allocation](#register-allocation). In the source: [`gcc/genpreds.cc:669@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/genpreds.cc#L669).

### alternative

**One row of a pattern's table: a set of constraints, and the text to print if the operands fit it.**

`add w0, w1, w2` and `add w0, w1, #3` are the same pattern with different alternatives, one taking a register and one taking an immediate. The compiler keeps the chosen row in `which_alternative`, and `-dp` prints it after the pattern name as `/1`. It only prints one when the pattern has more than one row, so a bare pattern name in an annotation is telling you the pattern had no choice to make.

Also written `which_alternative`. Taught in T09. See also [constraint](#constraint), [output template](#output-template), [define_insn](#define_insn). In the source: [`gcc/recog.h:363@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/recog.h#L363).

### mode iterator

**A placeholder in a pattern that makes one written form into several real patterns.**

`*add<mode>3_aarch64` with `GPI` as `[SI DI]` is two patterns, `*addsi3_aarch64` and `*adddi3_aarch64`, expanded when GCC is built. It is why searching a `.md` file for the name an annotation printed usually finds nothing, and why the reader in this project resolves the placeholders before it goes looking.

Also written `define_mode_iterator`, code iterator. Taught in T09. See also [machine description](#machine-description), [define_insn](#define_insn). In the source: [`gcc/read-rtl.cc:1482@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/read-rtl.cc#L1482).

### assembler directive

**A line of assembly that is an instruction to the assembler rather than to the machine.**

Anything starting with a dot. It reserves space, switches section, aligns the location counter, declares a symbol global, or records a size. Most of an assembly file is these: the recorded listing this project uses for T09 is forty six lines of which twelve are instructions. None of them assembles to a byte of code and several of them decide where the bytes go.

Also written pseudo op. Taught in T09. See also [section](#section), [final](#final).

### section

**A named region of the object file, and the thing that decides what a variable costs.**

`.text` is code, `.data` is initialised writable data, `.bss` is data that starts out zero and takes no space in the file, and `.rodata` is read only. Which one a variable lands in is not a style question. `categorize_decl_for_section` decides it from whether the variable is constant, whether its initialiser is all zeros, and whether it needs a relocation, and the answer changes how many bytes the binary is and whether writing to it faults.

Also written `.text`, `.bss`, `.rodata`. Taught in T09. See also [assembler directive](#assembler-directive), [final](#final). In the source: [`gcc/varasm.cc:7368@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/varasm.cc#L7368).

## Building the compiler

Words you need to configure GCC, build it, and read what it tells you afterwards. B01 and B02 are the lessons, and these are the words those two use constantly and that nothing in the tree defines.

### out of tree build

**Running `configure` from an empty directory somewhere else, which is how GCC is meant to be built.**

Nothing stops you running `./configure` inside the source tree, and the first thing it does is scatter object files, generated sources and a `host-<triple>` directory among the checked in ones. GCC does not fully clean up after that, and the top level `configure` refuses to do an out of tree build afterwards from the same source, so the mistake is one you make once and then live with or re-clone. Build in a sibling directory and the source tree stays a source tree, `git status` stays readable, and you can have a checking build and a release build of the same source at the same time.

Also written separate build directory, `srcdir`. Taught in B01. See also [stamp file](#stamp-file), [generated file](#generated-file). In the source: [`configure.ac:222@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/configure.ac#L222).

### target triple

**`cpu-company-system`, the three part name for a machine, and GCC needs up to three of them at once.**

`x86_64-pc-linux-gnu` and `aarch64-apple-darwin24` are triples, and `config.sub` turns whatever you typed into the canonical spelling. The reason there are three of them is that a compiler is a program that runs somewhere and emits code for somewhere else, so `--build` is where it is being compiled, `--host` is where it will run, and `--target` is what it will emit code for. All three the same is a native build. Host and target differing is a cross compiler. All three differing is a Canadian cross, which exists and which you should not attempt first.

Also written configuration name, `--build`, `--host`, `--target`. Taught in B01. See also [cross compiler](#cross-compiler), [port](#port). In the source: [`gcc/doc/install.texi:867@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/doc/install.texi#L867).

### cross compiler

**A GCC whose host and target are different machines, which is one configure flag and a great deal of consequence.**

`--target=riscv64-unknown-elf` and you have a compiler that runs on your laptop and emits RISC-V. What follows is the part people are not ready for. The compiler needs a C library for the target and there is not one on your machine, so either you point it at one or you use a bare metal target that gets away with `newlib`. The programs it produces cannot be run, so the test suite needs a simulator. And the installed binaries are prefixed with the triple, so the thing you type is `riscv64-unknown-elf-gcc` and not `gcc`. For reading a back end that last part is a feature, because the target you are studying is not the one you are typing on.

Also written `--target`, canadian cross. Taught in B01. See also [target triple](#target-triple), [port](#port). In the source: [`configure.ac:213@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/configure.ac#L213).

### stamp file

**An empty file whose only content is its timestamp, standing in for something make cannot depend on directly.**

A build directory is full of files called `s-something` with nothing in them. They exist because a generator program writes several outputs at once and make wants one target per rule, and because GCC writes generated sources through `move-if-change`, which deliberately leaves a file's timestamp alone when its content did not change. The stamp is what records that the generator ran. Deleting one forces a regeneration, and a stale one is the reason a build sometimes ignores an edit you made to a machine description.

Also written `s-` file, `move-if-change`, `$(STAMP)`. Taught in B01. See also [generated file](#generated-file), [out of tree build](#out-of-tree-build). In the source: [`gcc/Makefile.in:2803@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/Makefile.in#L2803).

### bootstrap

**Building GCC three times, each stage compiled by the one before, and comparing the last two.**

Stage one is built by whatever compiler you already have, stage two by stage one, and stage three by stage two. Stages two and three are then compared object file by object file, and they have to be identical, because they are the same source compiled by two compilers that are supposed to be the same compiler. That comparison is the strongest self test GCC has and it catches things nothing else does. It also costs four hours, which is why `--disable-bootstrap` exists and why every configuration in this project except one uses it. B02 is the lesson that takes it apart.

Also written `--enable-bootstrap`, stage comparison, three stage build. Taught in B01. See also [stamp file](#stamp-file), [checking build](#checking-build). In the source: [`Makefile.def:749@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/Makefile.def#L749).

### stage comparison

**The check at the end of a bootstrap: every object file of stage three has to equal stage two's, byte for byte.**

Thirty four lines of shell in `Makefile.tpl`, and the strongest self test GCC has. It walks stage three's object files, skips any stage two does not have, ignores the first sixteen bytes of each, and fails the build if any pair differs. What it proves is that the compiler is a fixed point: compiling its own source with itself does not change it. What it does not prove is that the fixed point is correct, because a bug that behaves the same way every time survives it. It also cannot see six named files, which are excluded on purpose because they legitimately differ.

Also written `make compare`, `.bad_compare`, compare exclusions. Taught in B02. See also [bootstrap](#bootstrap), [build config](#build-config). In the source: [`Makefile.tpl:1824@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/Makefile.tpl#L1824).

### bubbling

**GCC's word for driving the stages as a dependency chain, so a fix only rebuilds the stages after it.**

`stage3-bubble` depends on `stage2-bubble` depends on `stage1-bubble`, so asking for the last one asks for all of them, and make decides what actually needs doing. The point is not the ordering, which a shell script could manage. The point is that after you fix a bug in the compiler and re-run, the stages that are still valid are skipped, which is the difference between a four hour rebuild and a forty minute one. The `-lean` stamp files in the middle are how a stage records that it is still good.

Also written `stageN-bubble`, `-lean`. Taught in B02. See also [bootstrap](#bootstrap), [stamp file](#stamp-file). In the source: [`Makefile.tpl:1797@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/Makefile.tpl#L1797).

### build config

**A makefile fragment in `config/` that changes how the bootstrap stages are built, named on the configure line.**

`--with-build-config=bootstrap-lto` and the stages are built with link time optimisation. There are nineteen of them and they combine, space separated. `bootstrap-debug` is on by default and is the one worth knowing: it compares stage two and stage three a second time with debug info stripped from both, which catches the specific bug where adding `-g` changes the code a compiler generates. `bootstrap-ubsan` and `bootstrap-asan` build the compiler under a sanitizer, are very slow, and find real things.

Also written `--with-build-config`, `config/bootstrap-*.mk`. Taught in B02. See also [stage comparison](#stage-comparison), [bootstrap](#bootstrap). In the source: [`configure.ac:3303@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/configure.ac#L3303).
