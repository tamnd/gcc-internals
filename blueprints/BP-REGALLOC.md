# BP-REGALLOC, giving out the machine's registers

**Status:** stub
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** yes
**Generated sections:** none
**Last verified:** 2026-09-02 against `releases/gcc-16.2.0`

This is a stub. It holds what T08 needed, which is enough of IRA to read an `.ira` dump and know what every number in it means, plus the names and the order of the things LRA does afterwards. IRA's regional allocation, the cost model in `gcc/ira-costs.cc`, coalescing, and the whole of LRA's constraint satisfaction loop are named here and specified elsewhere, because each of them is longer than this document.

Two documents will eventually split out of this one. `BP-IRA` for the allocator and `BP-LRA` for the pass that finishes the job. Until they exist, this is the place that says which is which.

## 1. Purpose and scope

RTL comes out of expansion using pseudo registers, of which there can be any number. The machine has a fixed number of hard registers. Register allocation is the part of the compiler that reconciles those two facts, and the reconciliation is not always possible, so it also decides which values lose.

**What this document covers.** The allocno, which is the thing IRA actually colours. Live ranges and program points. Interference. Register pressure and register classes. The colouring order and what happens when it fails. The disposition, which is the allocator's own record of where every pseudo ended up. The division of labour between IRA and LRA.

**What it does not cover.** The cost model, which decides between two registers that both work and is `gcc/ira-costs.cc` in its entirety. Regional allocation across the loop tree, beyond saying that it exists and why the dump has more allocnos than pseudos. Coalescing and the preference graph. LRA's constraint matching, inheritance, rematerialisation, and elimination. Stack slot layout. All of those are real and all of them are somebody else's section.

**Position in the pipeline.** Two passes, adjacent, in `gcc/passes.def`. `pass_ira` at `gcc/ira.cc:6202@releases/gcc-16.2.0` runs `ira` at `gcc/ira.cc:5663@releases/gcc-16.2.0` and writes the `.ira` dump. `pass_reload` at `gcc/ira.cc:6247@releases/gcc-16.2.0` runs `do_reload` at `gcc/ira.cc:6056@releases/gcc-16.2.0`, which despite the pass name calls LRA, and writes the `.reload` dump. Both are gated on `!targetm.no_register_allocation`, which is false on every target that produces machine code.

**Inputs and outputs as properties.** Neither pass declares a property change. What changes is a fact the property system does not model: before `pass_reload` a function's RTL contains pseudo registers, and after it the function contains only hard registers and memory. Every pass after that point is written on that assumption.

## 2. Data structures

### 2.1 The allocno

`struct ira_allocno` at `gcc/ira-int.h:274@releases/gcc-16.2.0`. An allocno is a pseudo register within one region. That distinction is the single most confusing thing about reading an IRA dump, so it goes first.

IRA divides a function into regions along the loop tree. A pseudo that is live across a loop boundary gets one allocno inside the loop and another outside it, and the two can be given different hard registers, with a copy inserted at the boundary if they differ. So a function with 30 pseudos can have 62 allocnos, and the dump numbers both.

The dump writes an allocno as `a58(r159,l0)`. The `a58` is the allocno number, `r159` is the pseudo it stands for, and `l0` is the region, given as a loop number, with `l0` meaning the whole function. A basic block region prints `b7` instead.

| Field | What it holds |
|---|---|
| `num` | the allocno number, the `a` in the dump |
| `regno` | the pseudo it stands for, the `r` in the dump |
| `loop_tree_node` | the region, the `l` or `b` in the dump |
| `aclass` | the register class it has to be allocated from |
| `hard_regno` | the hard register it got, or `-1` for memory |
| `assigned_p` | whether the allocator has decided yet |
| `objects` | one or two `ira_object`s, two when the value needs two registers |
| `nrefs`, `freq` | how often it is referenced, and how hot those references are |
| `memory_cost` | what it would cost to keep this value in memory |
| `hard_reg_costs` | one cost per allocatable register in the class |

### 2.2 The object and its live ranges

`struct ira_object` at `gcc/ira-int.h:226@releases/gcc-16.2.0`. An allocno has one object for a value that fits in one register and two for a value that needs a pair. Conflicts and live ranges hang off the object rather than the allocno, because half of a register pair can conflict with something the other half does not.

A live range is a closed interval of program points, `[start..finish]`. Program points are numbered by a walk over the insns, and the numbering is per function. The dump prints an allocno's ranges as ` a58(r159): [4..7] [12..40]`, which reads as: this value has to exist from point 4 to point 7 and again from point 12 to point 40, and is dead in between.

The numbering is compressed before colouring. `remove_some_program_points_and_update_live_ranges` at `gcc/ira-lives.cc:1660@releases/gcc-16.2.0` merges runs of points at which nothing is born and nothing dies, because such a point cannot change any answer. The dump reports it:

```text
Compressing live ranges: from 202 to 65 - 32%
```

Two consequences for anybody reading the dump. Point numbers are not insn numbers and never were. And the numbering differs between two targets compiling the same source, so live range bars from two dumps line up within a target and not across two of them.

### 2.3 Conflicts

Two objects conflict if their live ranges overlap, which means they cannot share a register. The conflict relation is stored per object, as a bit vector for small functions and a sorted vector of pointers for large ones, and `build_object_conflicts` at `gcc/ira-conflicts.cc:570@releases/gcc-16.2.0` builds it.

The dump prints one line per allocno:

```text
;; a5(r120,l0) conflicts: a4(r119,l0) a6(r121,l0) a7(r122,l0)
```

Read as a graph, that is the interference graph, and colouring it with as many colours as the target has registers is the allocation problem. The graph is symmetric, so every edge appears twice in the dump.

### 2.4 Register classes and pressure

A register class is a set of hard registers that some instruction requires. `GENERAL_REGS` is the one that matters for integer code. A pressure class is a class IRA tracks occupancy for, chosen by `setup_pressure_classes` at `gcc/ira.cc:786@releases/gcc-16.2.0` so that the set is small and covers what the target actually contends for.

`ira_class_hard_regs_num[cl]`, set up in `setup_class_hard_regs` at `gcc/ira.cc:466@releases/gcc-16.2.0`, is how many registers the class has. It is not the same as how many the allocator can hand out, because the frame pointer, the stack pointer and any platform reserved register are excluded. The number that matters is printed per allocno:

```text
      Allocno a20r135 of GENERAL_REGS(15) has 15 available regs
```

Register pressure at a region is the number of values live at the busiest point in it, per class. `print_loop_title` at `gcc/ira-color.cc:3611@releases/gcc-16.2.0` prints it, with the loop over pressure classes at `gcc/ira-color.cc:3654@releases/gcc-16.2.0`:

```text
    Pressure: GENERAL_REGS=22
```

Pressure above availability is the definition of the problem. Pressure at or below it does not guarantee success, because a class constraint or a register pair can still fail, but for straight integer code on a uniform program it is exact, and section 9 has the measurements.

### 2.5 The disposition

At the end of allocation `ira_print_disposition` at `gcc/ira.cc:698@releases/gcc-16.2.0` writes one entry per allocno, four to a line:

```text
Disposition:
    0:r117 l0     3    1:r118 l0     0    2:r119 l0   mem
```

Each entry is the allocno number, the pseudo, the region, and then either a hard register number or the word `mem`. This is the authoritative record. Everything else in the dump is the allocator narrating its own attempts, and it changes its mind, which section 4 makes precise.

The hard register is a number, not a name. It is an index into the target's register table, and nothing in the `.ira` dump maps it back reliably: the Dataflow summary at the top of the dump names some registers and is printed before allocation, so callee saved registers that only get used later never appear there. To name a register, read the assembly.

## 3. Algorithms

### 3.1 The shape of it

```text
ira(f):
    find register classes and costs for every pseudo   ira-costs.cc
    build the loop tree and the allocnos               ira-build.cc
    compute live ranges                                ira-lives.cc
    compress the program point numbering               ira-lives.cc
    build the conflict graph                           ira-conflicts.cc
    colour                                             ira-color.cc
    flatten the regional allocation back to one map    ira-build.cc
    print the disposition
```

`find_costs_and_classes` at `gcc/ira-costs.cc:1974@releases/gcc-16.2.0`, `ira_build` at `gcc/ira-build.cc:3478@releases/gcc-16.2.0`, `ira_create_allocno_live_ranges` at `gcc/ira-lives.cc:1810@releases/gcc-16.2.0`, `ira_compress_allocno_live_ranges` at `gcc/ira-lives.cc:1833@releases/gcc-16.2.0`, `ira_build_conflicts` at `gcc/ira-conflicts.cc:812@releases/gcc-16.2.0`, `ira_color` entered through `color` at `gcc/ira-color.cc:5246@releases/gcc-16.2.0`, `ira_flattening` at `gcc/ira-build.cc:3134@releases/gcc-16.2.0`.

### 3.2 Colouring

`do_coloring` at `gcc/ira-color.cc:3843@releases/gcc-16.2.0` walks the loop tree and calls `color_allocnos` at `gcc/ira-color.cc:3489@releases/gcc-16.2.0` per region. The colouring itself is Chaitin and Briggs with a priority order, and it is a stack.

```text
push phase:                                            push_allocnos_to_stack
    while any allocno is left in the graph:
        if some allocno has fewer conflicts than there are registers:
            take that one, it is trivially colourable
        else:
            take the one with the worst spill priority
            mark it may_be_spilled
        remove it from the graph and push it

pop phase:                                             pop_allocnos_from_stack
    while the stack is not empty:
        pop an allocno
        if some register in its class is free of every conflicting allocno:
            assign it
        else:
            spill it
```

`push_allocnos_to_stack` at `gcc/ira-color.cc:2950@releases/gcc-16.2.0`, `push_allocno_to_stack` at `gcc/ira-color.cc:2736@releases/gcc-16.2.0`, `pop_allocnos_from_stack` at `gcc/ira-color.cc:2983@releases/gcc-16.2.0`, `assign_hard_reg` at `gcc/ira-color.cc:1971@releases/gcc-16.2.0`.

The order matters and is not arbitrary. `setup_allocno_priorities` at `gcc/ira-color.cc:3098@releases/gcc-16.2.0` and `allocno_spill_priority` at `gcc/ira-color.cc:2567@releases/gcc-16.2.0` rank a candidate by how much it costs to spill it against how much of the graph removing it unblocks, so a value used once outside a loop is a better victim than a value used every iteration.

The dump narrates both phases at `-fira-verbose=5` and above, which is what `-fdump-rtl-ira` gives by default:

```text
      Pushing a20(r135,l0)
      Popping a20(r135,l0)  -- assign reg 12
      Popping a19(r134,l0)  -- spill
```

`Popping` and its verdict are printed at `gcc/ira-color.cc:2994@releases/gcc-16.2.0`, and the assignment at `gcc/ira-color.cc:3011@releases/gcc-16.2.0`.

### 3.3 After colouring, before the dump is written

Two things run after the pop phase and can change any answer it produced. `improve_allocation` at `gcc/ira-color.cc:3217@releases/gcc-16.2.0` looks for a spilled allocno that would be cheaper in a register than the current occupant of some register is, and swaps them. `ira_reassign_conflict_allocnos` at `gcc/ira-color.cc:4072@releases/gcc-16.2.0` retries allocnos whose conflicts have moved.

This is why the disposition and the pop narration disagree. It is not a bug in either and it is not a bug in a reader. Section 4 states it as an invariant.

### 3.4 What LRA does

IRA decides. LRA makes it true. `lra` at `gcc/lra.cc:2420@releases/gcc-16.2.0` is a loop, and the loop is why register allocation is expensive.

```text
lra():
    repeat:
        satisfy the constraints of every insn        lra_constraints
        if nothing changed: stop
        recompute live ranges                        lra_create_live_ranges
        reassign whatever is still unassigned        lra_assign
    then:
        give every remaining pseudo a stack slot     lra_spill
        rewrite every pseudo into a register or a slot
```

`lra_constraints` at `gcc/lra-constraints.cc:5589@releases/gcc-16.2.0`, `lra_create_live_ranges` at `gcc/lra-lives.cc:1516@releases/gcc-16.2.0`, `lra_assign` at `gcc/lra-assigns.cc:1624@releases/gcc-16.2.0` through `assign_by_spills` at `gcc/lra-assigns.cc:1394@releases/gcc-16.2.0` and `spill_for` at `gcc/lra-assigns.cc:943@releases/gcc-16.2.0`, `lra_spill` at `gcc/lra-spills.cc:659@releases/gcc-16.2.0`.

The loop is necessary because satisfying an insn's constraints can require a new pseudo. An instruction that needs its operand in a register, given a value that IRA put in memory, gets a reload: a fresh pseudo, a load into it, and the instruction rewritten to use it. That pseudo is live, so the live ranges are wrong, so anything still unassigned has to be reconsidered, and reconsidering can spill something else, which needs another reload. It terminates because each round has strictly less to fix, and on hard functions it takes several rounds.

`lra_inheritance` at `gcc/lra-constraints.cc:7564@releases/gcc-16.2.0`, driven by `inherit_in_ebb` at `gcc/lra-constraints.cc:7105@releases/gcc-16.2.0`, is the optimisation that keeps this from being catastrophic. A value reloaded into a register stays there for the next use if nothing clobbered it, so a spilled value used three times in a loop body is loaded once, not three times.

## 4. Invariants

**I1.** After `pass_reload`, no insn in the function contains a pseudo register.
Established by: `lra_spill` at `gcc/lra-spills.cc:659@releases/gcc-16.2.0` and the rewrite that follows it. Checked by: every pass after it, implicitly, and by `--enable-checking` builds in `check_rtl`. May be broken by: nobody.

**I2.** Two allocnos whose objects conflict never hold the same hard register at the same time.
Established by: `assign_hard_reg` at `gcc/ira-color.cc:1971@releases/gcc-16.2.0`. Checked by: `check_allocation` in `gcc/ira.cc`, under `--enable-checking`. May be broken by: nobody, and the check exists because the regional flattening in `ira_flattening` is complicated enough that the authors did not want to rely on argument.

**I3.** Every allocno is either assigned a hard register in its class or assigned to memory. There is no third state after colouring finishes.
Established by: `pop_allocnos_from_stack` at `gcc/ira-color.cc:2983@releases/gcc-16.2.0`. Checked by: nothing. May be broken by: nobody.

**I4.** The `Disposition:` block is the outcome. The `Pushing` and `Popping` lines are a trace of one stage and may contradict it.
Established by: `ira_print_disposition` at `gcc/ira.cc:698@releases/gcc-16.2.0` running last. Checked by: nothing, and it needs saying because a reader who trusts the trace will get the wrong answer on any function where `improve_allocation` at `gcc/ira-color.cc:3217@releases/gcc-16.2.0` did anything. Section 9 has a measured instance.

**I5.** A program point number in an `.ira` dump refers to the compressed numbering, not to any insn.
Established by: `remove_some_program_points_and_update_live_ranges` at `gcc/ira-lives.cc:1660@releases/gcc-16.2.0`, which rewrites every range in place. May be broken by: nobody, and it is stated because the ranges printed before compression and the ranges printed after it use the same syntax.

*To be written: the invariants about register pairs and about what `ira_flattening` guarantees across a region boundary.*

## 5. Observable behaviour

`-fdump-rtl-ira` writes the whole of the above: the costs per allocno, the live ranges, the conflict graph, the pressure per region, the colouring trace, the disposition, and a cost total. On the corpus programs in this book it is between 400 KB and 600 KB for five small functions, which is a fair measure of how much the allocator considers.

The cost total, printed by `calculate_allocation_cost` at `gcc/ira.cc:2640@releases/gcc-16.2.0` with the format at `gcc/ira.cc:2677@releases/gcc-16.2.0`:

```text
+++Costs: overall 187732, reg 0, mem 187732, ld 0, st 0, move 0
```

`mem` is what IRA charged itself for the values it could not keep in registers. It is in the same arbitrary units as everything else in the cost model, so the number means nothing on its own and means a great deal compared against the same function on another target.

`-fdump-rtl-reload` writes LRA's output. It is larger again and it does not contain the word `Slot` in the sense old reload used, because LRA words its stack slot assignment differently. For finding out what was spilled, the IRA disposition is shorter and definitive.

Corpus entries: `t08-x86-64` and `t08-aarch64`, recorded through Compiler Explorer at GCC 16.1.0, and `t08-local`, recorded from the Homebrew GCC 16.2.0 on `aarch64-apple-darwin24`. All three hold one dump, `rtl-ira`, at `-O2`, of `corpora/programs/t08-pressure.c`.

*To be written: `-fira-verbose` levels other than the default, `-fira-algorithm`, and what `-fopt-info-rtl` says about spilling.*

## 6. Edge cases and error paths

*To be written.* The ones already known to matter:

A function where pressure is at the limit exactly. Nothing spills if the graph happens to be colourable and something does if it does not, and pressure alone cannot tell you which.

A value that needs a register pair. Its allocno has two objects, and a class with an odd number of free registers can fail to place it while having room for two separate values.

A class with one register in it. Any two values that both need it conflict by construction, and the second one spills no matter what the total pressure is.

`targetm.no_register_allocation`, which is true on targets with no registers to allocate, at which point both passes are skipped and the machine description is expected to have produced code that needs no allocation.

A function that runs out of registers during LRA's loop rather than during IRA. That is the case where IRA's answer was wrong rather than tight, and the compiler recovers by spilling more, which is why the loop exists.

## 7. Interactions

`pass_ira` consumes RTL from every pass before it and produces an annotated function that only `pass_reload` reads. Nothing between them.

`TARGET_CLASS_MAX_NREGS`, `TARGET_HARD_REGNO_MODE_OK` and `TARGET_CAN_CHANGE_MODE_CLASS` decide which registers can hold which values and are consulted constantly. `REG_ALLOC_ORDER` lets a target say which registers to prefer. `TARGET_IRA_CHANGE_PSEUDO_ALLOCNO_CLASS` lets a target override IRA's class choice.

The scheduler interacts with the allocator in both directions and gets neither one it wants. Scheduling before allocation moves independent instructions apart, which raises pressure and causes spills. Scheduling after allocation cannot move much, because the allocator has introduced dependencies that were not in the program. GCC runs a pass on each side and `-fsched-pressure` exists to make the first one care.

*To be written: the full target hook list, and the interaction with `-fcaller-saves`.*

## 8. Conformance

*To be written.* What exists to point at: `gcc.dg/torture/` compiled at every optimisation level catches allocator bugs by miscompiling, which is the only signal a wrong allocation gives. `gcc.target/*/pr*.c` is largely a museum of allocator bugs, one test per fix. The invariants in section 4 restated as assertions, three of which are already assertions in `--enable-checking` builds.

The boss fight in T08 is a conformance test of a kind: predict which of five functions spill on x86-64 at `-O2`, then check against the disposition.

## 9. Port notes

The number of registers a target can hand out is the whole of this section, and it is smaller than the number of registers the target has.

Measured on `corpora/programs/t08-pressure.c`, five functions whose register pressure is fixed by construction at the number of live values plus two. The three configurations are x86-64 at GCC 16.1.0, aarch64 Linux at GCC 16.1.0, and aarch64 Darwin at GCC 16.2.0.

| | x86-64 | aarch64 Linux | aarch64 Darwin |
|---|---|---|---|
| `GENERAL_REGS` size | 15 | 30 | 29 |
| available for allocation | 15 | 30 | 29 |
| `p04`, pressure 6 | 0 spilled | 0 | 0 |
| `p10`, pressure 12 | 0 spilled | 0 | 0 |
| `p14`, pressure 16 | 1 spilled | 0 | 0 |
| `p20`, pressure 22 | 7 spilled | 0 | 0 |
| `p30`, pressure 32 | 17 spilled | 2 | 3 |
| `p30` memory cost | 485260 | 25774 | 44234 |
| allocnos for `p30` | 62 | 61 | 61 |
| `p30` point numbering | 202 to 65 | 170 to 63 | 170 to 63 |

Three things in that table are worth a port's attention.

**Two of those columns are the same instruction set.** aarch64 Linux and aarch64 Darwin differ by one register: Apple reserves `x18` as the platform register, so the allocatable set is `0-17 19-28 30` rather than `0-28 30`. One register fewer, and `p30` spills three values instead of two. Nothing else about the target changed.

**The x86-64 count is not sixteen.** The architecture has sixteen general registers. The stack pointer is not allocatable, which leaves fifteen, and a reader who predicts that a function with sixteen live values fits will be wrong by exactly one, which is what `p14` demonstrates.

**Spilled equals pressure minus available, on this program.** 16 - 15 = 1, 22 - 15 = 7, 32 - 15 = 17, 32 - 30 = 2, 32 - 29 = 3. Every row in the table matches, across three configurations, which is fifteen measurements and no exceptions. It is still not a general rule. It holds because the program is a rotating dependence chain with uniform pressure and one basic block that matters, so the allocator has nothing to trade: every value is live everywhere and costs the same. A program with a hot inner loop and a cold outer one spills by cost rather than by count, and the count can be lower than the arithmetic says, because splitting one long live range in two can make room for both.

**The disagreement between the trace and the disposition, measured.** In `p30` on aarch64 Linux, `a58(r159,l0)` is popped with `assign reg 28` and `a56(r130,l0)` is popped with `-- spill`. The disposition says `r159` is in memory and `r130` is in register 28. `improve_allocation` swapped them between the two printings, which is invariant I4 with a line number attached.

**What is forced and what is not.** That some values end up in memory when there are more of them than there are registers is forced. Which ones is a cost model and could be anything. That the allocator runs twice, as a global allocator and then as a local fixer, is a GCC choice: LLVM makes a different one, greedy allocation with rematerialisation and splitting in a single framework, and gets comparable code out. The two stage split in GCC is historical, since LRA replaced reload in 2013 while keeping reload's position in the pipeline and even its pass name, and the pass being called `reload` in `gcc/ira.cc:6247@releases/gcc-16.2.0` while doing no reloading is the fossil.
