# BP-EXPAND, GIMPLE becomes RTL

**Status:** stub
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** yes
**Generated sections:** none
**Last verified:** 2026-09-02 against `releases/gcc-16.2.0`

This is a stub. It holds the shape of `pass_expand`, the order of the phases inside it, the stack slot partitioning, and what an expander is allowed to fail at. `expand_expr_real_1`, which is the four thousand line switch that turns one tree into RTL, is described by its interface and not its contents. The call sequence and argument passing are out of scope entirely and want their own document, because the ABI lives there. Nothing here can be generated.

## 1. Purpose and scope

Expand is the widest gap in the compiler. On one side is GIMPLE: three address, SSA, target independent, with an unbounded number of named values. On the other is RTL: an instruction list, no SSA, target specific, with pseudo registers that will eventually have to be real ones. Everything about the representation changes at once, in a single pass, and there is no intermediate form.

The thing to understand about expand is that it is not a translation. It is a *search*. For each GIMPLE statement, expand asks the target whether it has an instruction that does this, in this mode, and if the answer is no it asks a different question, and if every question fails it falls back to a library call. Whether `a * b` becomes one instruction, three, or a call to `__mulsi3` is decided here, by looking at tables the machine description generated.

**What this document covers.** The phases of `pass_expand` in order. Out of SSA and partition to pseudo mapping. Local variable layout, including the stack slot sharing that makes two dead variables one slot. How a basic block of GIMPLE becomes a run of insns. The optab query as the mechanism behind the search. The CFG surviving the transition. What properties are provided and destroyed.

**What it does not cover.** `expand_expr_real_1` case by case. Calls, argument setting, and the whole of `calls.cc`, which is where target ABI knowledge concentrates. The prologue and epilogue, which are generated later. `expand_debug_expr` and debug insn generation, which is a parallel pipeline with different rules. Vector and atomic expansion. Anything about RTL as a form, which is BP-RTL.

**Position in the pipeline.** `pass_expand` is the last GIMPLE pass and the first RTL pass, which is the same statement.

**Inputs and outputs as properties.** From `gcc/cfgexpand.cc:6999@releases/gcc-16.2.0`: requires `PROP_ssa | PROP_gimple_leh | PROP_cfg | PROP_gimple_lcx | PROP_gimple_lvec | PROP_gimple_lva`, provides `PROP_rtl`, destroys `PROP_ssa | PROP_gimple`. Five passes in the whole compiler have a nonempty `properties_destroyed`, and the other four each destroy one thing they are named after: `*free_cfg`, `outof_cfglayout`, `loop2_done` and `*clean_state`. Expand is the only one that destroys a representation, and this line is the machine readable way of saying what the previous paragraph said.

## 2. Data structures

### 2.1 The partition map

`rewrite_out_of_ssa` at `gcc/tree-outof-ssa.cc:1499@releases/gcc-16.2.0` fills a `struct ssaexpand`, which holds a `var_map` from SSA names to partitions and, once expand allocates them, a `partition_to_pseudo` array.

Out of SSA is a coalescing problem. Two SSA names that came from the same variable and do not interfere can share one pseudo register, and a PHI becomes nothing at all if all its arguments and its result end up in the same partition. When they cannot be coalesced, the PHI becomes a copy on the incoming edge, which is what `insert_backedge_copies` at `gcc/tree-outof-ssa.cc:1282@releases/gcc-16.2.0` and the edge insertion machinery are there for.

`SA.partition_to_pseudo` at `gcc/cfgexpand.cc:7039@releases/gcc-16.2.0` is the array expand allocates immediately after, one RTL expression per partition. That array is the entire bridge between the two worlds: after it is filled, an SSA name is looked up by partition and comes back as a pseudo.

### 2.2 Stack variables

`class stack_var` at `gcc/cfgexpand.cc:312@releases/gcc-16.2.0` is `decl`, `size`, `alignb`, `representative`, `next` and a `conflicts` bitmap.

The representative and next fields make each partition a linked list with a head, in the union find sense. The conflicts bitmap says which other variables are live at the same time as this one. Two variables in the same partition get the same stack slot.

`size` is documented as changing meaning: it starts as the variable's size and becomes the partition's size once the variable is a representative. That is the kind of field a blueprint exists to warn about.

### 2.3 What a block turns into

There is no new data structure for the output. `expand_gimple_basic_block` at `gcc/cfgexpand.cc:6172@releases/gcc-16.2.0` sets `BB_RTL` on the block and fills in the RTL half of the `il` union described in BP-CFG section 2.1. The same `basic_block` object, with the same index and the same edges, now holds insns instead of statements.

That reuse is why the CFG survives expand rather than being rebuilt, and it is the main practical reason GIMPLE and RTL share a graph at all.

## 3. Algorithms

### 3.1 The pass

`pass_expand::execute` at `gcc/cfgexpand.cc:7028@releases/gcc-16.2.0`, in order.

```text
expand(fun):
    rewrite_out_of_ssa(&SA)                    # SSA names become partitions
    SA.partition_to_pseudo = array of num_partitions

    if debug binds and -ftree-ter:
        avoid_deep_ter_for_debug on every debug bind

    discover_nonconstant_array_refs(forced_stack_vars)
    currently_expanding_to_rtl = 1
    free_dominance_info(CDI_DOMINATORS)        # new blocks are coming
    insn_locations_init()
    emit_note(NOTE_INSN_DELETED)               # an insn that can never be deleted
    targetm.expand_to_rtl_hook()
    crtl->init_stack_alignment()
    resolve_unique_section(...)

    var_ret_seq = expand_used_vars(forced_stack_vars)   # locals get homes
    expand_function_start(current_function_decl)        # parameters arrive

    propagate the RTL of each partition to the SSA names in it
    gimple_register_cfg_hooks -> rtl hooks
    init_block = construct_init_block()

    for bb from init_block->next_bb to EXIT:
        bb = expand_gimple_basic_block(bb, var_ret_seq)

    free_dominance_info(both directions)
    delete_tree_ssa(fun)                       # PROP_ssa is now false
    construct_exit_block()
```

Four moments in that sequence are worth naming.

`free_dominance_info` is called before any expansion, with the comment at `gcc/cfgexpand.cc:7060@releases/gcc-16.2.0` giving the reason: expansion creates basic blocks, because one GIMPLE statement can expand into something with control flow in it. Dominance would go stale, so it is dropped rather than maintained. This is BP-CFG invariant I6 being honoured by the pass with the strongest reason to.

`emit_note (NOTE_INSN_DELETED)` at `gcc/cfgexpand.cc:7086@releases/gcc-16.2.0` is the first insn in the function and exists so that there is always a first insn. Its comment says both reasons: nothing can delete it, and `final` expects it. A great deal of RTL code walks backwards from an insn and would need a null check without it.

`expand_used_vars` runs inside a `start_sequence` and `end_sequence` pair, so the insns it generates go into a detached sequence and are spliced in before the function start note afterwards. Sequences are how RTL code generates instructions it is not sure it wants yet, and this is the first use of the pattern in the pass.

And the block loop runs from `init_block->next_bb` rather than from the first block, because `construct_init_block` at `gcc/cfgexpand.cc:6579@releases/gcc-16.2.0` has already made a block for the entry edge to land in.

### 3.2 Giving locals homes

`expand_used_vars` at `gcc/cfgexpand.cc:2468@releases/gcc-16.2.0` decides, for every local, whether it lives in a pseudo register or on the stack, and for the stack ones where.

```text
expand_used_vars(forced):
    for each local var:
        if it can live in a register: expand_one_var -> gen_reg_rtx
        else: add_stack_var(decl)          # deferred, we want them all first
    build the conflict bitmaps from the liveness we still have
    partition_stack_vars()                 # merge non-conflicting vars
    expand_stack_vars(...)                 # assign an offset per partition
```

`partition_stack_vars` at `gcc/cfgexpand.cc:1240@releases/gcc-16.2.0` sorts by size and alignment with `stack_var_cmp` and then does a quadratic pass merging any two partitions that do not conflict. Quadratic is fine because the number of address taken locals in a function is small, and when it is not, the sort ordering means the big ones get merged first.

This is where two arrays in disjoint scopes end up at the same stack offset. It is also the pass a reader should look at when a function's stack frame is inexplicably large: a conflict that should not be there, usually from a variable being live across more than the programmer thinks, keeps two slots apart.

`expand_stack_vars` at `gcc/cfgexpand.cc:1400@releases/gcc-16.2.0` takes a predicate, and it is called several times with different ones, which is how stack protector ordering puts arrays above scalars.

### 3.3 Expanding a block

`expand_gimple_basic_block` at `gcc/cfgexpand.cc:6172@releases/gcc-16.2.0` walks the statements and dispatches. `expand_gimple_stmt` at `gcc/cfgexpand.cc:4380@releases/gcc-16.2.0` and `expand_gimple_stmt_1` at `gcc/cfgexpand.cc:4214@releases/gcc-16.2.0` are the per statement work, with special cases pulled out: `expand_gimple_cond` at `gcc/cfgexpand.cc:2923@releases/gcc-16.2.0` for conditionals, `expand_gimple_tailcall` at `gcc/cfgexpand.cc:4434@releases/gcc-16.2.0` for tail calls, and `expand_debug_expr` at `gcc/cfgexpand.cc:4822@releases/gcc-16.2.0` for debug binds.

An ordinary assignment goes to `expand_assignment` at `gcc/expr.cc:5988@releases/gcc-16.2.0`, which computes the right hand side with `expand_expr_real` at `gcc/expr.cc:9605@releases/gcc-16.2.0` and stores it with `store_expr` at `gcc/expr.cc:6591@releases/gcc-16.2.0`.

`expand_expr_real_2` at `gcc/expr.cc:9847@releases/gcc-16.2.0` handles the binary and unary operations, and it is where the search described in section 1 happens.

### 3.4 The search

The mechanism is the optab. An optab is a table indexed by machine mode giving the `insn_code` of the pattern that implements an operation in that mode, or `CODE_FOR_nothing`. The tables are generated from the machine description by `genopinit`, so the question "can this target add two 32 bit integers" is answered by an array lookup.

```text
expand_binop(mode, optab, op0, op1, target, unsignedp, methods):
    icode = optab_handler(optab, mode)
    if icode != CODE_FOR_nothing:
        try to generate that insn with these operands
        if the operands do not match the predicates: copy them into registers and retry
        if it works: return the result
    try a wider mode and narrow the result
    try doing it in two halves
    if methods allows: emit a libcall
    return NULL_RTX
```

`expand_binop` at `gcc/optabs.cc:1501@releases/gcc-16.2.0` and `expand_unop` at `gcc/optabs.cc:3249@releases/gcc-16.2.0` are the real ones and have far more fallbacks than that. The important structural fact is the last line: **an expander may fail**, returning null, and the caller has to cope. That is unusual in a compiler back end and it is the reason expand code is written as a cascade of attempts rather than a translation.

`maybe_gen_insn` at `gcc/optabs.cc:8427@releases/gcc-16.2.0` is the "try to generate" step, and `expand_insn` at `gcc/optabs.cc:8514@releases/gcc-16.2.0` is the variant that asserts instead of failing, used where the target has already promised the pattern exists.

*To be written: the mode iteration order, the libcall table, and how `SET`s that no pattern matches survive to be fixed up later.*

## 4. Invariants

**I1.** After expand, no SSA name exists and no GIMPLE statement exists.
Established by: `delete_tree_ssa` near the end of the pass. Checked by: `properties_destroyed` in the pass data, enforced by the pass manager. May be broken by: nobody, since the pass manager checks it.

**I2.** The basic block structure survives. Blocks keep their indices and their edges, and new blocks may be added but existing ones are not renumbered.
Established by: `expand_gimple_basic_block` reusing the block object. Checked by: `rtl_verify_flow_info` afterwards. May be broken by: nobody. This is what lets the RTL passes inherit the profile the GIMPLE passes computed.

**I3.** Every SSA name that reaches expand maps to exactly one partition, and every partition maps to exactly one RTL expression.
Established by: `rewrite_out_of_ssa` and the `partition_to_pseudo` fill. Checked by: nothing directly. May be broken by: a name created after out of SSA ran, which is why the pass checks for that case explicitly in the propagation loop.

**I4.** Two locals assigned the same stack slot are never live at the same time.
Established by: the conflict bitmaps that `partition_stack_vars` reads. Checked by: nothing at compile time. May be broken by: a bug in the liveness that built the bitmaps, and the failure mode is a miscompile that looks like memory corruption.

**I5.** An expander that fails returns null and emits nothing. It does not leave half generated insns behind.
Established by: the sequence discipline, where a speculative attempt runs inside `start_sequence` and the sequence is thrown away on failure. Checked by: nothing. May be broken by: an expander that emits directly instead of into a sequence, which is a real class of back end bug.

**I6.** Dominance information is not available during or after expand.
Established by: `free_dominance_info` at the start and again at the end. Checked by: `dom_info_available_p` returning false. May be broken by: nobody.

*To be written: the invariants about `crtl` initialisation order, and about what may still be a `MEM` after expand.*

## 5. Observable behaviour

`-fdump-rtl-expand` prints the pass. The dump has three parts, and the first two are the interesting ones.

Corpus entry `t05-boss-O2`, GCC 16.2.0 on aarch64-apple-darwin24, `-O2 -g`, function `g`.

The first part is a running commentary, one line per block:

```text
;; Generating RTL for gimple basic block 2
;; Generating RTL for gimple basic block 3
...
Edge 2->6 redirected to 11
Edge 3->5 redirected to 13
```

The redirections are expand creating blocks, which is why dominance was dropped. The GIMPLE function had blocks 2 through 8 and the RTL function has blocks up to 13.

The second part is `try_optimize_cfg`, which runs as part of expand and immediately cleans up what expansion produced:

```text
Merging block 3 into block 2...
Merged blocks 2 and 3.
Redirecting jump 40 from 12 to 13.
Removing jump 60.
```

Two GIMPLE blocks merging into one RTL block is normal. The GIMPLE CFG splits at every point control could go somewhere, and once the conditional has become a compare and a branch, some of those splits are no longer splits.

The third part is the insn list. The first three insns of the function:

```text
(note 1 0 10 NOTE_INSN_DELETED)
(note 10 1 2 2 [bb 2] NOTE_INSN_BASIC_BLOCK)
(insn 2 10 3 2 (set (reg/v:SI 105 [ n ])
        (reg:SI 0 x0 [ n ])) "t05-boss.c":6:1 -1
     (nil))
```

Insn 1 is the undeletable note from section 3.1. Insn 2 is the parameter arriving: hard register `x0`, which is where the aarch64 ABI puts the first integer argument, copied into pseudo 105. Every parameter starts life as a copy out of a hard register, and getting rid of that copy is the register allocator's job, not expand's.

The `-1` before `(nil)` is the insn code, and `-1` means not yet recognised. Compare the branch:

```text
(jump_insn 19 18 20 2 (set (pc)
        (if_then_else (le (reg:CC 66 cc)
                (const_int 0 [0]))
            (label_ref:DI 70)
            (pc))) "t05-boss.c":8:21 discrim 2 59 {aarch64_bcond}
     (int_list:REG_BR_PROB 118111601 (nil))
 -> 70)
```

That one has `59 {aarch64_bcond}`, a real pattern from the aarch64 machine description. Expand knew what instruction it wanted for a conditional branch and generated it directly. For the plain register copies it did not bother, and `pass_rtl_recog` will match them later.

`REG_BR_PROB 118111601` is the branch probability carried over from GIMPLE, scaled to `REG_BR_PROB_BASE`. This is invariant I2 paying off: the profile survived the representation change.

*To be written: `-fdump-rtl-expand-details`, and the stack layout output.*

## 6. Edge cases and error paths

*To be written.* The ones already known to matter:

- An operation with no pattern in any mode, which becomes a libcall, and one with no libcall either, which is an internal compiler error at the point of expansion.
- A statement that expands to control flow, which splits the block it was in and is why new blocks appear.
- Variable length arrays, which need `alloca` and disable most of the stack partitioning.
- A tail call that expand cannot honour, which quietly becomes an ordinary call.
- `TREE_ADDRESSABLE` set temporarily on parameters, at `gcc/cfgexpand.cc:7119@releases/gcc-16.2.0`, so that `expand_function_start` emits copies, and cleared again immediately after. That is a mutation of the tree to communicate with a callee, and it is the kind of thing that only exists because both sides are in the same compilation unit.

## 7. Interactions

Consumes everything the GIMPLE pipeline produced: the CFG, the profile, the SSA form, the alias information. Produces the input to every RTL pass.

`crtl` and `cfun->machine` are initialised here, and the target hook `expand_to_rtl_hook` at `gcc/cfgexpand.cc:7088@releases/gcc-16.2.0` exists so a port can do setup at exactly this moment.

Reads the machine description indirectly, through the optab tables and the generated `gen_*` functions, which is the interaction that makes this pass target dependent.

*To be written: the relationship with `calls.cc`, and with the prologue and epilogue generation that happens much later.*

## 8. Conformance

*To be written.* There is no direct test suite for expand. It is tested by every execution test in the compiler, which is a strong test of correctness and no test at all of quality. `gcc.dg/stack-usage-*` exercises the stack partitioning, and `gcc.target/*` tests exercise particular expanders per target.

## 9. Port notes

This is one of the most target dependent parts of the compiler, and almost none of that dependence is in `cfgexpand.cc`. It arrives through three channels.

The machine description supplies the named patterns. `addsi3`, `movdi`, `cbranchsi4` and the rest are what the optab tables index, and a target that does not define one gets the fallback path instead of the instruction.

The target hooks supply the decisions. Whether a value is passed in a register, how wide a `MODE_INT` promotes to, whether a struct is returned in memory, what alignment the stack needs.

And `expand_function_start` plus `calls.cc` supply the ABI, which is where the largest per target differences live and which this document does not cover.

**What is forced and what is not.** Some translation from a high level IR to a target instruction list is forced. Doing it in one pass is not.

GCC does it in one pass and pays for that in two ways. The pass is enormous, because every decision about instruction selection has to be made with whatever context is available at that moment. And there is no representation between GIMPLE and RTL to optimize, so anything that wants to reason about target instructions has to do it on RTL, which is not in SSA form.

LLVM makes the opposite choice: SelectionDAG is a per block intermediate form that exists only to do instruction selection, and it is optimized before selection and thrown away after. That is more machinery and better selection.

The optab and libcall fallback is the other choice worth naming. Because an expander may fail, GCC can support a target with no multiply instruction without every caller of `expand_binop` knowing about it. The cost is that the failure path is a cascade of attempts, each of which is a place where a target can accidentally get a worse instruction sequence than it deserves, and the only way to find out is to look at the output.
