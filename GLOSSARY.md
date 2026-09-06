# Glossary

One definition per term, in one place, so a lesson can use a word without stopping to explain it and without assuming you remember it from forty lessons ago. Lessons link into this file rather than repeating themselves.

The order below is the order you meet these things, not alphabetical, because reading it straight through is a reasonable thing to do. If you are looking one up, the index is next.

This file is generated from `gxray/glossary.py`. Edit that and run `just build-glossary`.

## Index

[DejaGnu](#dejagnu) | [GENERIC](#generic) | [GIMPLE](#gimple) | [IRA](#ira) | [LRA](#lra) | [RTL](#rtl) | [RTX](#rtx) | [SSA](#ssa) | [SSA name](#ssa-name) | [TODO flags](#todo-flags) | [allocno](#allocno) | [alternative](#alternative) | [assembler directive](#assembler-directive) | [back end](#back-end) | [basic block](#basic-block) | [blue paint](#blue-paint) | [bootstrap](#bootstrap) | [bubbling](#bubbling) | [build config](#build-config) | [cc1](#cc1) | [checking build](#checking-build) | [collect2](#collect2) | [compiler table](#compiler-table) | [constraint](#constraint) | [control flow graph](#control-flow-graph) | [cross compiler](#cross-compiler) | [current function](#current-function) | [debug counter](#debug-counter) | [default definition](#default-definition) | [define_insn](#define_insn) | [definition](#definition) | [diagnostic](#diagnostic) | [directive](#directive) | [dominance](#dominance) | [driver](#driver) | [dump file](#dump-file) | [edge](#edge) | [effective target](#effective-target) | [error recovery](#error-recovery) | [excess errors](#excess-errors) | [expand](#expand) | [final](#final) | [fix-it hint](#fix-it-hint) | [front end](#front-end) | [garbage collector](#garbage-collector) | [gate](#gate) | [generated file](#generated-file) | [gengtype](#gengtype) | [gimplification](#gimplification) | [hard register](#hard-register) | [immediate dominator](#immediate-dominator) | [include guard](#include-guard) | [inferior call](#inferior-call) | [insn](#insn) | [interference](#interference) | [line marker](#line-marker) | [live range](#live-range) | [lookahead](#lookahead) | [loop](#loop) | [machine description](#machine-description) | [machine mode](#machine-mode) | [middle end](#middle-end) | [mode iterator](#mode-iterator) | [optimization level](#optimization-level) | [out of SSA](#out-of-ssa) | [out of tree build](#out-of-tree-build) | [output template](#output-template) | [param](#param) | [parser](#parser) | [pass](#pass) | [pass manager](#pass-manager) | [pass positioning](#pass-positioning) | [phi node](#phi-node) | [plugin](#plugin) | [plugin ABI](#plugin-abi) | [plugin event](#plugin-event) | [poly_int](#poly_int) | [port](#port) | [preprocessor](#preprocessor) | [pretty printer](#pretty-printer) | [pseudo register](#pseudo-register) | [pseudo-event](#pseudo-event) | [register allocation](#register-allocation) | [register class](#register-class) | [register pressure](#register-pressure) | [section](#section) | [spec](#spec) | [spec function](#spec-function) | [specs file](#specs-file) | [spill](#spill) | [stage comparison](#stage-comparison) | [stamp file](#stamp-file) | [sum file](#sum-file) | [target hook](#target-hook) | [target triple](#target-triple) | [temporary](#temporary) | [three address form](#three-address-form) | [token](#token) | [token pasting](#token-pasting) | [torture options](#torture-options) | [translation unit](#translation-unit) | [tree](#tree) | [typedef name](#typedef-name) | [use](#use) | [wide_int](#wide_int)

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

What actually runs when you type `gcc`, and how to make it show you its work. T01, T04 and F01 are the lessons that cover this ground.

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

A spec is a template full of conditionals like `%{save-temps:...}` that expands into arguments. `gcc -dumpspecs` prints all of them, which is the driver printing its own program: the decision about which programs to run is written in this language and not in C, and the C in `gcc/gcc.cc` is an interpreter for it. Recognising the syntax stops that output looking like line noise, and it explains why an option you passed shows up in a completely different form in the `cc1` command line.

Also written spec string, `-dumpspecs`. Taught in F01. See also [driver](#driver), [cc1](#cc1), [spec function](#spec-function), [specs file](#specs-file), [compiler table](#compiler-table). In the source: [`gcc/gcc.cc:473@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gcc.cc#L473).

### spec function

**A named C function a spec may call when substitution alone cannot answer the question.**

Written `%:name(arguments)` inside a spec. There are twenty-one of them in GCC 16 and they are the language's escape hatch: `if-exists` cannot be expressed as a substitution because it has to look at the filesystem, and `version-compare` has to compare numbers. Each one is a row in `static_spec_functions` pairing a name with a C function, so the list is the exact boundary between what the little language can do and what it has to ask C for.

Also written `%:`. Taught in F01. See also [spec](#spec), [driver](#driver). In the source: [`gcc/gcc.cc:1814@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gcc.cc#L1814).

### compiler table

**The driver's list of file suffixes, and which spec compiles each one.**

Not the spec list. This is a separate array, `default_compilers`, where each row is a suffix like `.c` and the spec to run for it, and it is what turns a file name into a language. Most rows point at a second row named `@c` or `@c-header`, so the suffix decides the language and the language decides the commands. It is searched backwards, which is what lets a `-specs=` file add a row that wins over the built-in one, and adding a row is how a specs file teaches the driver a file extension it has never heard of.

Also written `default_compilers`. Taught in F01. See also [spec](#spec), [driver](#driver), [specs file](#specs-file). In the source: [`gcc/gcc.cc:1458@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gcc.cc#L1458).

### specs file

**A text file of spec definitions the driver reads with -specs=, overwriting its own.**

The format is the one `-dumpspecs` prints: a name between a star and a colon, then the spec on the lines below it. A name that is already defined is replaced, a `+` at the start of the value appends to what is there instead, and a name that does not begin with a star adds a row to the compiler table. This is the supported way to change what the driver runs without patching or rebuilding it, and it is how GCC's own `-static-libgcc` handling and several distributions' hardening defaults are shipped.

Also written `-specs=`, `read_specs`. Taught in F01. See also [spec](#spec), [driver](#driver), [compiler table](#compiler-table). In the source: [`gcc/gcc.cc:2634@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gcc.cc#L2634).

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

## Before the parser

The first program in the chain, and the one whose output every other lesson quietly assumes. F02 is the lesson.

### preprocessor

**The phase that runs before the parser, and the only one that works in tokens without types.**

It is not a separate program in a normal compilation. `cc1` contains libcpp and calls it for each token, so `gcc -E` is the same code with the output printed instead of parsed. The thing worth unlearning is that it edits text. It lexes your file into tokens, works on tokens, and prints tokens back out, and the printing step has to insert whitespace that was in no input file to stop two of them lexing as one. Everything people find surprising about macros follows from that.

Also written libcpp, `cpp`, `-E`. Taught in F02. See also [token](#token), [translation unit](#translation-unit), [cc1](#cc1). In the source: [`libcpp/init.cc:589@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libcpp/init.cc#L589).

### token

**One lexical unit, with a type, a location and some flags. What the preprocessor deals in.**

A `cpp_token` is thirty two bytes on a 64-bit host: a location, a type from a list of about a hundred, a flag word, and a union holding the spelling. `PREV_WHITE` in those flags is the one to know, because it is where the space before a token lives; the space is a property of the token after it rather than a character in a buffer. A macro expanding to nothing can therefore still leave a space behind, and two tokens that arrive next to each other can still be printed apart.

Also written `cpp_token`, `PREV_WHITE`. Taught in F02. See also [preprocessor](#preprocessor), [token pasting](#token-pasting). In the source: [`libcpp/include/cpplib.h:261@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libcpp/include/cpplib.h#L261).

### translation unit

**One source file with every #include pasted in and every macro expanded. What the parser sees.**

It is the unit C is defined in terms of, and it is much larger than the file you wrote. One `#include <stdio.h>` opens dozens of files, so a hundred line program is routinely tens of thousands of lines by the time the parser starts. This is the reason a compiler feels slow on small files, the reason a macro defined in one header can break a declaration in another, and the reason `gcc -E` is the first thing to run when a build error names a line you cannot find.

Also written TU. Taught in F02. See also [preprocessor](#preprocessor), [include guard](#include-guard).

### line marker

**A `# 42 "file.h" 2 3 4` line in preprocessed output, saying where the following text came from.**

Not a comment and not a directive. It is how the preprocessor hands the parser back the line numbers it destroyed by pasting files together, which is what makes an error inside a header point at the header. The digits after the filename are flags: 1 means entering a file, 2 means returning to one, 3 means a system header where warnings are suppressed, and 4 means the contents are to be wrapped in `extern "C"`. Flag 3 is the reason a warning in your code disappears when you move the same code into `/usr/include`.

Also written `#line`, linemarker. Taught in F02. See also [preprocessor](#preprocessor), [translation unit](#translation-unit). In the source: [`gcc/c-family/c-ppoutput.cc:618@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/c-family/c-ppoutput.cc#L618).

### include guard

**The `#ifndef NAME / #define NAME / #endif` wrapper that stops a header being read twice.**

The interesting part is not the idiom, it is that libcpp recognises it. When a file's entire token stream is one conditional controlled by a macro, the file is remembered along with that macro's name, and the next `#include` of it is skipped without opening the file at all. The recognition is exact: one declaration after the `#endif` and the optimization is off, though a comment there costs nothing, because the check is over tokens and a comment is not one.

Also written multiple inclusion guard, `cmacro`, `#pragma once`. Taught in F02. See also [preprocessor](#preprocessor), [translation unit](#translation-unit). In the source: [`libcpp/files.cc:858@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libcpp/files.cc#L858).

### token pasting

**Two things that mean opposite things: the `##` operator, and the accident it is named after.**

`a ## b` is the operator, and it makes two tokens into one before the result is scanned for macros, which is why `CAT(PLUS, PLUS)` gives you the identifier `PLUSPLUS` and not `++`. The accident is what `cpp_avoid_paste` exists to prevent: when the preprocessor prints two adjacent tokens that would lex back as one, it puts a space between them that was in no input file. Both are the same fact seen from two sides, which is that the preprocessor's output is tokens and its printed form is a lossy rendering of them.

Also written `##`, `cpp_avoid_paste`. Taught in F02. See also [token](#token), [preprocessor](#preprocessor). In the source: [`libcpp/lex.cc:4728@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libcpp/lex.cc#L4728).

### blue paint

**The mark that stops a macro expanding inside its own expansion, so `#define foo foo + 1` terminates.**

While a macro is being expanded, its name is disabled; any occurrence of it in the result is flagged `NO_EXPAND` and stays that way forever, even if it is later passed somewhere the macro is not being expanded. The standard's rule and libcpp's implementation are the reason `#define A B` and `#define B A` produce `A` rather than a hang. The name is from a 1980s comp.std.c thread about painting the identifier blue so it cannot be expanded again, and the source uses it.

Also written `NO_EXPAND`, painted blue, self-reference. Taught in F02. See also [preprocessor](#preprocessor), [token](#token). In the source: [`libcpp/macro.cc:1590@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libcpp/macro.cc#L1590).

## In the parser

The program that reads C, and the four token slots everything surprising about it comes out of. F03 is the lesson.

### parser

**The recursive descent code that turns a token stream into trees. It can see four tokens.**

GCC's C parser is written by hand rather than generated, and all of its memory of your program is a `c_parser` struct: four token slots, a few flags, and the symbol table it shares with the rest of the front end. There is no dump flag for it, because it has no output of its own to print. What it produces is GENERIC, and what you can watch it do is complain. Nearly everything surprising about a C error message follows from the size of that buffer and from the fact that the symbol table has to answer a question before the parse can continue.

Also written `c_parser`, recursive descent, `cc1`. Taught in F03. See also [lookahead](#lookahead), [typedef name](#typedef-name), [GENERIC](#generic). In the source: [`gcc/c/c-parser.cc:191@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/c/c-parser.cc#L191).

### lookahead

**How far ahead the parser can look before deciding what it is reading. In C, four tokens.**

`c_parser_peek_token` gives the next one, `c_parser_peek_2nd_token` the one after it, and `c_parser_peek_nth_token` reaches as far as the fourth. The buffer behind all three is `c_token tokens_buf[4]` and nothing widens it. Most of the peeking in the C parser is one token deep, and the deepest constant peek in the whole file is there to recognise a version control conflict marker, which is not a C construct at all. When a grammar needs to see further than four, the parser does not get more; it commits, and then recovers.

Also written peek, `tokens_buf`, LL(k). Taught in F03. See also [parser](#parser), [token](#token), [error recovery](#error-recovery). In the source: [`gcc/c/c-parser.cc:572@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/c/c-parser.cc#L572).

### typedef name

**An identifier that names a type, and the reason C cannot be parsed without a symbol table.**

`A * b;` declares `b` as a pointer if `A` is a typedef name and multiplies two variables if it is not, and no amount of looking at tokens will tell you which. The parser asks the symbol table instead, and the answer is written into the token as `CPP_KEYWORD` or `CPP_NAME` the first time that token is looked at. That moment can come too early: a token peeked while one scope was open and used after it closed is carrying a stale answer, which is what `c_parser_maybe_reclassify_token` exists to undo.

Also written lexer hack, `CPP_KEYWORD`, `c_parser_maybe_reclassify_token`. Taught in F03. See also [parser](#parser), [token](#token), [lookahead](#lookahead). In the source: [`gcc/c/c-parser.cc:2326@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/c/c-parser.cc#L2326).

### diagnostic

**One complaint, with a message, a severity, a place, and often a suggested repair.**

A diagnostic is not a line of text. It is a structure with a primary location, any number of secondary ones, and any number of fix-it hints, and the text on your terminal is one rendering of it. `-fdiagnostics-format=sarif-stderr` is another, and it is the one to reach for when you want to read the structure rather than the prose. For the parser the message is finished by `c_parse_error`, which chooses one of thirteen endings from the type of the token the parser is looking at, which is why one missing semicolon can produce eight different sentences depending on what comes after it.

Also written `-fdiagnostics-format`, SARIF, `c_parse_error`. Taught in F03. See also [fix-it hint](#fix-it-hint), [parser](#parser), [pretty printer](#pretty-printer). In the source: [`gcc/c-family/c-common.cc:7004@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/c-family/c-common.cc#L7004).

### fix-it hint

**A machine applicable edit hung off a diagnostic, saying insert or delete or replace this text here.**

GCC does not suggest a repair for every mistake. For a missing token it suggests one only for the seven token types `get_missing_token_insertion_kind` knows, and the hint is what decides where the caret goes: two of the seven are inserted before the token that upset the parser and five after the token before it, and in the second case the caret moves back to the end of that previous token. That is why an error about a semicolon points at the line above the one you were reading. `-fdiagnostics-parseable-fixits` prints the hints in a form an editor can apply.

Also written `fixit_hint`, `rich_location`, `-fdiagnostics-parseable-fixits`. Taught in F03. See also [diagnostic](#diagnostic), [parser](#parser). In the source: [`libcpp/include/rich-location.h:620@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/libcpp/include/rich-location.h#L620).

### error recovery

**What the parser does after an error so that it can carry on and find the next one.**

A parser that stopped at the first mistake would make you compile a file once per typo, so after complaining it throws tokens away until it reaches one it can start again from, usually a semicolon or a closing brace at the right nesting depth. This is why three missing semicolons can come out as two errors rather than three, and why an error near the end of a file is sometimes a consequence of one near the top rather than a mistake of its own. The habit to build is to fix the first error and compile again.

Also written resynchronise, `c_parser_skip_until_found`. Taught in F03. See also [parser](#parser), [diagnostic](#diagnostic), [lookahead](#lookahead). In the source: [`gcc/c/c-parser.cc:1353@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/c/c-parser.cc#L1353).

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

Words you need to configure GCC, build it, run it under a debugger, and read what it tells you afterwards. B01, B02 and B03 are the lessons, and these are the words those three use constantly and that nothing in the tree defines.

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

### debug counter

**A counter inside a pass that makes its transformations refusable one at a time, so a bad one can be bisected.**

`dbg_cnt (ccp)` returns true the first N times it is called and false afterwards, where N comes from `-fdbg-cnt=ccp:N`, and the pass is written to skip the transformation when it returns false. Seventy five of them exist, listed in `dbgcnt.def` and printed by `-fdbg-cnt-list`. The point is bisection: if a program is miscompiled with a pass on and correct with it off, halving N repeatedly finds the smallest limit that still produces bad code, and that number is one specific transformation rather than a pass with four thousand of them. The count is over the whole compilation, not per function, so the number is only meaningful for the exact command line that produced it.

Also written `-fdbg-cnt`, `-fdbg-cnt-list`, `dbgcnt.def`. Taught in B03. See also [pass](#pass), [gate](#gate). In the source: [`gcc/dbgcnt.cc:63@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/dbgcnt.cc#L63).

### pretty printer

**A Python class in `gdbhooks.py` that teaches gdb to print one of GCC's types as something readable.**

Without them, `print stmt` in a debugger attached to `cc1` prints a pointer, and `print cfun->decl` prints a tagged union with forty members. With them, the first prints the GIMPLE statement and the second prints `<function_decl 0x... f>`. Seventeen are registered by name and a loop adds four more, and `gdbinit.in` loads the module that does it. A printer reads the same fields a human would read, in Python, without calling into the compiler, which is why one works on a core dump and why one can be wrong in a way the compiler is not.

Also written `gdbhooks.py`, `info pretty-printer`. Taught in B03. See also [tree](#tree), [current function](#current-function). In the source: [`gcc/gdbhooks.py:619@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gdbhooks.py#L619).

### inferior call

**Making the debugged program run one of its own functions, on demand, from the debugger prompt.**

Most of GCC's twenty six gdb shorthands are one of these. `pt` is `call debug_tree ($arg0)`, so printing a tree means running GCC's own printing code inside the stopped compiler and letting it write to stderr. That is what makes the output identical to a dump file, and it is also the reason the trick has teeth: the call needs a live process with a working stack, it can allocate, and if the function it runs hits an assertion the debugger stops inside a call it made itself and says so. `set unwindonsignal on`, which `gdbinit.in` sets, is what stops that leaving the process wedged.

Also written `call`, `pt`, `pcfun`. Taught in B03. See also [pretty printer](#pretty-printer), [cc1](#cc1). In the source: [`gcc/gdbinit.in:83@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/gdbinit.in#L83).

## Testing the compiler

Words you need to read a GCC test, work out what command line it will be compiled with, and tell a real regression from a test that quietly stopped running. B04 is the lesson.

### DejaGnu

**The Tcl and expect framework GCC's test suite is written in, and the reason a test is a C file with comments in it.**

`make check` runs `runtest`, which is DejaGnu, which loads a `.exp` file per directory and hands it a list of files. The `.exp` is a Tcl program, so a directory of tests is a program that decides how to compile them rather than a list of cases. What GCC adds on top is `lib/gcc-dg.exp` and its neighbours, about six thousand lines that turn `{ dg-error "..." }` comments into verdicts. Nothing here is a library you can call: the harness needs `expect`, a build tree and a compiler that was built minutes ago, which is why it is the one part of GCC that a reader cannot try out casually.

Also written `runtest`, `.exp` file, `make check`. Taught in B04. See also [directive](#directive), [excess errors](#excess-errors). In the source: [`gcc/doc/sourcebuild.texi:919@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/doc/sourcebuild.texi#L919).

### directive

**A `{ dg-something ... }` in a comment, which is the whole language a GCC test is written in.**

`{ dg-do compile }` says what to do with the file, `{ dg-options "-O2" }` says what to compile it with, and `{ dg-error "expected" }` says a message will appear on the line the comment is written on. Seventy three kinds exist and a normal test uses three or four. Two of them cause more confusion than the rest together: `dg-options` replaces the directory's default flags rather than adding to them, and `dg-additional-options` is the one that adds. A directive the harness does not know is not an error, it is a comment, so a typo in a directive name is a test that silently checks nothing.

Also written `dg-error`, `dg-options`, `dg-do`. Taught in B04. See also [DejaGnu](#dejagnu), [effective target](#effective-target). In the source: [`gcc/doc/sourcebuild.texi:1033@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/doc/sourcebuild.texi#L1033).

### excess errors

**The rule that makes a test fail for output nobody asked about, which is what stops a test from only checking what it mentions.**

Every diagnostic the compiler printed is matched against the file's expectations, each one satisfying at most one, and whatever is left over is pruned and then reported as excess errors. That is what makes a GCC test subtractive rather than additive: a file with three `dg-error` directives is not saying "these three appear", it is saying "these three and nothing else". It is also why a test can pass every one of its own directives and still fail, and why the excess errors line is the one to read first in a failure.

Also written `prune_gcc_output`, `dg-excess-errors`. Taught in B04. See also [directive](#directive), [sum file](#sum-file). In the source: [`gcc/testsuite/lib/prune.exp:32@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/testsuite/lib/prune.exp#L32).

### torture options

**Six sets of optimisation flags, and a torture test is the same file compiled once with each of them.**

`DG_TORTURE_OPTIONS` is `-O0`, `-O1`, `-O2`, a long `-O3` line, `-O3 -g` and `-Os`, and `gcc-dg-runtest` walks a directory once per set. So `gcc.dg/torture` holding four hundred files means two thousand four hundred compilations, which is why that directory costs what it does. Whether a file gets the two loop flags is decided by looking for the text `for` or `while` in it, with a glob loose enough that `format(` counts, and nobody has tightened it because the cost of a false positive is one extra flag.

Also written `DG_TORTURE_OPTIONS`, `gcc-dg-runtest`, `-funroll-loops`. Taught in B04. See also [optimization level](#optimization-level), [DejaGnu](#dejagnu). In the source: [`gcc/testsuite/lib/gcc-dg.exp:94@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/testsuite/lib/gcc-dg.exp#L94).

### effective target

**A named question about the machine, asked before a test runs, that decides whether it runs at all.**

`{ dg-require-effective-target lp64 }` means skip this file unless pointers are sixty four bits. Several hundred of these are defined in `target-supports.exp`, and a great many are answered by compiling a small program and seeing whether it worked, so the answer depends on the compiler under test rather than on a table. This is the mechanism behind the most common surprise in a `.sum`: a test that passed yesterday and is absent today has usually not been broken, it has stopped being applicable, and a summary block cannot tell you that, because the total went down by one and something else made it up again.

Also written `dg-require-effective-target`, `target-supports.exp`, `dg-skip-if`. Taught in B04. See also [directive](#directive), [sum file](#sum-file). In the source: [`gcc/doc/sourcebuild.texi:1491@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/doc/sourcebuild.texi#L1491).

### sum file

**The one line per result summary a test run leaves behind, and the only thing worth comparing between two runs.**

A line is a state and a name, `PASS: gcc.dg/pr1234.c (test for excess errors)`, and one test file produces several of them. Five of the thirteen states make a run red and the other eight are information, and `XFAIL` in particular means a known failure that failed as expected. The right way to read one is against a previous one: a `PASS` that became a `FAIL` is a regression, and a name that is in the old file and not the new one is a test that stopped being run, which the summary block at the bottom cannot show you and which is the more dangerous of the two.

Also written `.sum`, `.log`, `XFAIL`. Taught in B04. See also [excess errors](#excess-errors), [effective target](#effective-target).

## Extending the compiler

Words you need to load code of your own into GCC, put a pass where you want it, and understand why the thing you are writing against is not an API. B05 is the lesson.

### plugin

**A shared object loaded into `cc1` at startup, which registers functions to be called at named points during a compilation.**

`-fplugin=./thing.so` and the compiler proper `dlopen`s it with `RTLD_NOW`, looks for a symbol called `plugin_is_GPL_compatible` by name, and calls `plugin_init`. Everything a plugin can do follows from being inside the same process: it sees the real IR, calls the real functions, and crashes the real compiler. There are three ways it can be refused, all of them before it runs a line of its own code, and all three stop the compilation rather than warning and carrying on. It is the only supported way to observe or change what GCC does without patching GCC.

Also written `-fplugin=`, `plugin_init`, `-fplugin-arg-`. Taught in B05. See also [plugin event](#plugin-event), [plugin ABI](#plugin-abi). In the source: [`gcc/plugin.cc:699@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/plugin.cc#L699).

### plugin event

**A named point in a compilation where GCC calls whatever a plugin registered for it.**

`gcc/plugin.def` is a file of twenty six one-line macro calls, and the order of that file is the ABI, because the enumerator's value is the index into the callback table. Twenty three of them are fired, from twenty nine places, and what arrives with each one is a `void *` whose real type is written in the call site and nowhere else. Firing an event is a walk down a linked list of callbacks in registration order, with no return value read, so a plugin cannot refuse an event or stop another plugin from seeing it.

Also written `DEFEVENT`, `register_callback`, `invoke_plugin_callbacks`. Taught in B05. See also [plugin](#plugin), [pseudo-event](#pseudo-event). In the source: [`gcc/plugin.def:20@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/plugin.def#L20).

### pseudo-event

**One of the three names in the event list that is never fired, and is instead acted on at the moment you register for it.**

`PLUGIN_PASS_MANAGER_SETUP`, `PLUGIN_INFO` and `PLUGIN_REGISTER_GGC_ROOTS` are handled inside `register_callback` itself: it asserts the callback is null and uses the user data argument straight away. So registering a pass is spelled the same way as registering a callback and does something else entirely, which is the single most confusing thing about the mechanism, and the reason a plugin that passes a function pointer alongside a `register_pass_info` gets an assertion failure rather than a diagnostic.

Also written `PLUGIN_PASS_MANAGER_SETUP`, `register_callback`. Taught in B05. See also [plugin event](#plugin-event), [pass positioning](#pass-positioning). In the source: [`gcc/plugin.cc:458@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/plugin.cc#L458).

### pass positioning

**The four fields that say where in the pipeline a plugin's pass goes: which pass to hang it on, which run of that pass, and before, after or instead of.**

`struct register_pass_info` holds the new pass, a `reference_pass_name`, a `ref_pass_instance_number` where zero means every instance and one means the first, and a `pos_op` of `PASS_POS_INSERT_AFTER`, `PASS_POS_INSERT_BEFORE` or `PASS_POS_REPLACE`. The name to give is the pass name and not the dump name: `-fdump-tree-cddce1` is the pass called `cddce` on its first instance, and a reference to `cddce1` matches nothing. A reference that matches nothing is a fatal error at registration, which is the one mistake in this area that tells you about itself.

Also written `register_pass_info`, `PASS_POS_INSERT_AFTER`, `position_pass`. Taught in B05. See also [pass](#pass), [pseudo-event](#pseudo-event). In the source: [`gcc/tree-pass.h:328@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-pass.h#L328).

### plugin ABI

**The unwritten contract between a plugin and the compiler that loads it, which is every private header GCC has and every option it was configured with.**

`plugin_default_version_check` compares five fields, not one: the base version, the datestamp, the development phase, the revision and the whole configuration argument string. Two compilers of the same version built with different `--enable` flags have incompatible plugin ABIs, because those flags change struct layouts. That is why a plugin has to be built by the compiler that will load it, why the check is the plugin's own job rather than the compiler's, and why there is no such thing as shipping a binary plugin.

Also written `plugin_default_version_check`, `plugin-version.h`, `gcc_version`. Taught in B05. See also [plugin](#plugin), [build config](#build-config). In the source: [`gcc/plugin.cc:1013@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/plugin.cc#L1013).

### TODO flags

**What a pass tells the pass manager to do after it has run, returned as a bit mask from `execute`.**

`TODO_cleanup_cfg`, `TODO_update_ssa`, `TODO_verify_all` and their neighbours. A pass that changed nothing returns zero. A pass that modified the IR and returned zero has left the compiler believing things that are no longer true, and the failure shows up several passes later in code that did nothing wrong, which is the most expensive mistake a first plugin can make. There is a second set, `todo_flags_start`, that runs before the pass instead, and `TODO_mark_first_instance` in it is how the pass manager knows which run of a repeated pass is the first.

Also written `todo_flags_finish`, `TODO_update_ssa`, `pass_data`. Taught in B05. See also [pass](#pass), [pass positioning](#pass-positioning). In the source: [`gcc/tree-pass.h:238@releases/gcc-16.2.0`](https://github.com/gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/tree-pass.h#L238).
