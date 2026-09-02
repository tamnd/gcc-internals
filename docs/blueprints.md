# The blueprints

A blueprint is a specification and not a lesson. It says what GCC does precisely enough to implement against, with every claim carrying a citation into the pinned tree, and it does not try to teach. The lessons are the way in. These are what you write code against once you are in.

Every one is checked on every push. The citations resolve against `releases/gcc-16.2.0`, and the sections marked as generated are rebuilt from GCC's own `.def` files rather than typed, so a document cannot quietly fall behind the compiler it describes.

Three statuses. A **stub** has all nine sections and says in its header what it does not cover yet, because a lesson needs somewhere to point today and a title with a promise under it is not somewhere. A **partial** has its generated sections landed and prose still to write. A **complete** one is finished.

The pseudocode every algorithm is written in is [NOTATION](blueprints/NOTATION.md), and it is worth five minutes before you reach the first algorithm, because it is not C and reading it as C will mislead you in two places.

| | What it specifies | Status | Generated sections | Target dependent |
|---|---|---|---|---|
| [BP-CFG](blueprints/BP-CFG.md) | blocks and edges | stub | none | no |
| [BP-DRIVER](blueprints/BP-DRIVER.md) | the program that runs the other programs | stub | none | yes |
| [BP-EXPAND](blueprints/BP-EXPAND.md) | GIMPLE becomes RTL | stub | none | yes |
| [BP-FINAL](blueprints/BP-FINAL.md) | turning insns into text | stub | none | yes |
| [BP-GIMPLE](blueprints/BP-GIMPLE.md) | the GIMPLE statement representation | partial | 2 of 9 | no |
| [BP-PIPELINE](blueprints/BP-PIPELINE.md) | the shape of a compilation | complete | none | no |
| [BP-REGALLOC](blueprints/BP-REGALLOC.md) | giving out the machine's registers | stub | none | yes |
| [BP-RTL](blueprints/BP-RTL.md) | the RTL expression representation | stub | none | yes |
| [BP-SSA](blueprints/BP-SSA.md) | one definition per name | stub | none | no |

9 of 58 written: 1 complete, 1 partial, 7 stub.

## What each one is for

### [BP-CFG](blueprints/BP-CFG.md), blocks and edges

This is a stub. It holds the data structures, the two fixed blocks, how a GIMPLE sequence becomes a graph, and what dominance is computed by and when it is valid. The pass level detail is not here: loop discovery, profile propagation, hot and cold partitioning, and the RTL side of the hooks are named and not specified. Section 2.3 could be generated from `gcc/cfg-flags.def`, which is a `.def` file with exactly the shape `bpc` reads, and that is the obvious first thing to do when this stub is promoted.

### [BP-DRIVER](blueprints/BP-DRIVER.md), the program that runs the other programs

This is a stub. It holds what T01 needed and no more, which is the shape of the driver's main loop, the spec language as a grammar, how a file suffix chooses a program, and what a reader of `-###` output is actually looking at. Everything about multilibs, sysroots, offloading, LTO and `collect2` is named and not specified. Section 2 could be generated from `gcc/gcc.cc` in principle, since the spec table is a static array, but the specs a given build actually uses come from the target's `config.gcc` and its headers rather than from the array, so a generator would have to run the driver rather than read the source, and that is a different kind of tool. The header says no generated sections rather than pretending otherwise.

### [BP-EXPAND](blueprints/BP-EXPAND.md), GIMPLE becomes RTL

This is a stub. It holds the shape of `pass_expand`, the order of the phases inside it, the stack slot partitioning, and what an expander is allowed to fail at. `expand_expr_real_1`, which is the four thousand line switch that turns one tree into RTL, is described by its interface and not its contents. The call sequence and argument passing are out of scope entirely and want their own document, because the ABI lives there. Nothing here can be generated.

### [BP-FINAL](blueprints/BP-FINAL.md), turning insns into text

This is a stub. It holds what T09 needed, which is enough of `final` to read an annotated assembly file, find the machine description pattern that emitted any line of it, and say which row of that pattern was used and why. The machine description as a language, the recognizer that decides which pattern matches in the first place, the operand substitution letters each target defines, and the whole of `varasm` past section selection are named here and specified elsewhere.

### [BP-GIMPLE](blueprints/BP-GIMPLE.md), the GIMPLE statement representation

Section 2 is generated from `gcc/gimple.def`, `gcc/gsstruct.def` and `gcc/gimple.h` by `bpc build`. Nothing in it is typed by hand, and `bpc check` fails the build if what is in this file is not what the generator produces from the pinned tree today. Sections 3 to 9 are written by hand and land with the GIMPLE lessons in M4.

### [BP-PIPELINE](blueprints/BP-PIPELINE.md), the shape of a compilation

This document specifies the control flow of one compilation: which components run, in which order, what each one hands the next, and where the pass manager begins and ends. It is the map every other blueprint hangs off. Where another document owns a component, this one states the boundary and the handover and stops.

### [BP-REGALLOC](blueprints/BP-REGALLOC.md), giving out the machine's registers

This is a stub. It holds what T08 needed, which is enough of IRA to read an `.ira` dump and know what every number in it means, plus the names and the order of the things LRA does afterwards. IRA's regional allocation, the cost model in `gcc/ira-costs.cc`, coalescing, and the whole of LRA's constraint satisfaction loop are named here and specified elsewhere, because each of them is longer than this document.

### [BP-RTL](blueprints/BP-RTL.md), the RTL expression representation

This is a stub. It holds what T07 needed and no more, which is the shape of an RTX, the shape of an insn chain, the machine modes, and the register numbering. The algorithms in section 3 are the ones a reader of an `.expand` dump needs in order to know where the text came from, not the ones an implementer of an expander needs, and everything about pattern matching, reload, register allocation and the machine description belongs to blueprints that are not written yet. Section 2 will be generated from `gcc/rtl.def` and `gcc/machmode.def` when the generator exists, which is why the header says no generated sections rather than pretending otherwise.

### [BP-SSA](blueprints/BP-SSA.md), one definition per name

This is a stub. It holds the SSA name and the PHI as data structures, the four step construction, what a virtual operand is, and what `verify_ssa` enforces. `update_ssa` and the incremental renamer are described at the level of what they promise and not how they work, which is the largest gap here and the first thing to fill. The out of SSA side is named and left to BP-EXPAND. Nothing in this document can be generated: SSA is code, not a table.

This page is generated by `python -m tools.bpc pages`. Edit the blueprints rather than editing here.
