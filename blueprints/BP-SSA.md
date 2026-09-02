# BP-SSA, one definition per name

**Status:** stub
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** no
**Generated sections:** none
**Last verified:** 2026-09-02 against `releases/gcc-16.2.0`

This is a stub. It holds the SSA name and the PHI as data structures, the four step construction, what a virtual operand is, and what `verify_ssa` enforces. `update_ssa` and the incremental renamer are described at the level of what they promise and not how they work, which is the largest gap here and the first thing to fill. The out of SSA side is named and left to BP-EXPAND. Nothing in this document can be generated: SSA is code, not a table.

## 1. Purpose and scope

SSA is a naming discipline. Every variable is renamed so that it is assigned exactly once, and wherever two differently named versions of the same original variable meet, a PHI is inserted to pick one based on which edge control came in on.

The payoff is that a use points at its definition directly, so nearly every analysis that would otherwise need a dataflow fixpoint becomes a pointer chase. GCC gets this on GIMPLE and never gets it on RTL, which is most of why the GIMPLE optimizers are where the interesting work happens.

**What this document covers.** The `SSA_NAME` tree node and its fields. The `gphi` statement and its positional arguments. Version numbers, default definitions, and what a name with no `SSA_NAME_VAR` is. Virtual operands and the `.MEM` name. The four step construction in `pass_build_ssa`. The immediate use lists and why they are a cyclic doubly linked list. What `verify_ssa` checks.

**What it does not cover.** How `update_ssa` incrementally renames after a pass has changed the CFG, beyond stating its contract. The pruned and semi pruned variants of PHI placement, beyond naming `prune_unused_phi_nodes`. Alias analysis, which is what makes virtual operands mean anything. Range and pointer info hanging off a name. Any pass that consumes SSA, which is all of them. Out of SSA, which belongs to BP-EXPAND.

**Position in the pipeline.** Built by `pass_build_ssa` at `gcc/passes.def:59@releases/gcc-16.2.0`, inside `pass_build_ssa_passes`, immediately after `pass_fixup_cfg`. Held from there until `rewrite_out_of_ssa` runs as part of expand.

**Inputs and outputs as properties.** Requires `PROP_cfg`. Provides `PROP_ssa`, which is the property nearly every tree optimizer requires.

## 2. Data structures

### 2.1 The name

`tree_ssa_name` at `gcc/tree-core.h:1716@releases/gcc-16.2.0` is a tree node, which means an SSA name is an expression operand and can sit anywhere a `VAR_DECL` could.

| Field | What it holds |
|---|---|
| `var` | the declaration this is a version of, or an `IDENTIFIER_NODE`, or null |
| `def_stmt` | the single statement that defines this name |
| `info` | a union of `ptr_info_def` for pointers and `vrange_storage` for everything else |
| `imm_uses` | the head of the cyclic list of every use of this name |

The version number is not in the struct. `SSA_NAME_VERSION` at `gcc/tree.h:2239@releases/gcc-16.2.0` reads `base.u.version`, reusing a field in the shared tree header, and it is what a dump prints after the underscore. `total_4` is version 4 of the declaration `total`.

`SSA_NAME_VAR` at `gcc/tree.h:2217@releases/gcc-16.2.0` is a macro rather than a field read because `var` has three cases. A real `VAR_DECL` or `PARM_DECL`, in which case this name is a version of a user variable and the dump prints a name. An `IDENTIFIER_NODE`, which keeps the spelling for diagnostics after the declaration itself is gone. Or null, an anonymous name that never corresponded to anything the programmer wrote, which the dump prints as `_7`.

`SSA_NAME_DEF_STMT` at `gcc/tree.h:2235@releases/gcc-16.2.0` is the whole point of the discipline. It is a single pointer and it is always right, which is what "use def chains are free in SSA" means concretely.

### 2.2 The PHI

`gphi` at `gcc/gimple.h:474@releases/gcc-16.2.0` is `capacity`, `nargs`, `result` and a trailing array of `phi_arg_d`.

`phi_arg_d` at `gcc/tree-core.h:1741@releases/gcc-16.2.0` is `imm_use`, `def` and `locus`, in that order, and the comment above it says the order is load bearing: `phi_arg_index_from_use` recovers which argument a use belongs to by pointer arithmetic, and that only works if `imm_use` is first.

Arguments are positional and correspond to `bb->preds` by index. There is no edge pointer in `phi_arg_d`. This is the single most consequential design decision in the whole SSA representation, because it means the PHIs of a block and the predecessor list of that block are one data structure spread across two places, and every CFG edit has to keep them in step.

`capacity` and `nargs` differ because a PHI is reallocated in size classes rather than exactly, so a block that gains a predecessor usually does not need the PHI moved.

### 2.3 Virtual operands

Memory is not in SSA form, because it cannot be: there is no bound on how many locations a store might touch. GCC gets most of the benefit anyway by putting *all* of memory into SSA as a single artificial variable.

`create_vop_var` at `gcc/tree-ssa-operands.cc:230@releases/gcc-16.2.0` builds it: a `VAR_DECL` called `.MEM`, artificial, ignored, and flagged with `VAR_DECL_IS_VIRTUAL_OPERAND`. Every statement that may read memory gets a `vuse` of some version of `.MEM`, and every statement that may write memory gets a `vdef` producing a new one. `gimple_vuse` and `gimple_vdef` at `gcc/gimple.h:2229@releases/gcc-16.2.0` are the accessors.

This gives memory a def use chain in exactly the same shape as a scalar's, so the same walk works on both, and it gives loops of stores the same PHIs that loops of assignments get. What it does not give is precision: two stores to unrelated objects still chain, and disambiguating them is what alias analysis is for. The virtual operand is the skeleton and the alias oracle is the flesh.

### 2.4 Immediate uses

`ssa_use_operand_t` at `gcc/tree-core.h:1704@releases/gcc-16.2.0` is `prev`, `next`, a union of `gimple *` and `tree`, and a `tree *`.

Every use of a name is a node in one cyclic doubly linked list, and the head of that list is the `imm_uses` field inside the name itself. That is what the union is for: the list root points at an SSA name and every other node points at a statement, and the comment at `gcc/tree-core.h:1707@releases/gcc-16.2.0` says exactly this.

Cyclic and doubly linked means removing a use is constant time without knowing the list head, which matters because the common operation is "this statement is going away, unlink all its operands". `FOR_EACH_IMM_USE_FAST` at `gcc/ssa-iterators.h:71@releases/gcc-16.2.0` walks it read only, and `FOR_EACH_IMM_USE_STMT` is the variant that survives the loop body modifying the list, which is the usual case.

Def use chains are free in SSA. Use def chains, the other direction, are this list, and they cost a `ENABLE_GIMPLE_CHECKING` guarded pair of fields and a lot of careful unlinking.

## 3. Algorithms

### 3.1 Construction

`pass_build_ssa::execute` at `gcc/tree-into-ssa.cc:2490@releases/gcc-16.2.0` is four numbered steps, and the numbers are in the source.

```text
build_ssa(fun):
    if optimize: execute_update_addresses_taken()   # more variables become renameable
    init_ssa_operands(fun)
    init_ssa_renamer()
    interesting_blocks = empty set

    # 1, at tree-into-ssa.cc:2517
    calculate_dominance_info(CDI_DOMINATORS)
    compute_dominance_frontiers(dfs)

    # 2, at tree-into-ssa.cc:2521
    mark_def_dom_walker(CDI_DOMINATORS).walk(entry)

    # 3, at tree-into-ssa.cc:2524
    insert_phi_nodes(dfs)

    # 4, at tree-into-ssa.cc:2527
    rewrite_blocks(ENTRY_BLOCK_PTR, REWRITE_ALL)
```

This is Cytron's algorithm, unmodified. Step 1 computes the dominance frontier of every block with `compute_dominance_frontiers` at `gcc/cfganal.cc:1639@releases/gcc-16.2.0`. Step 2 walks the dominator tree recording, for each variable, the set of blocks that define it, with the per statement work in `mark_def_sites` at `gcc/tree-into-ssa.cc:648@releases/gcc-16.2.0`. Step 3 puts a PHI for variable *v* in the iterated dominance frontier of *v*'s definition blocks, computed by `compute_idf` at `gcc/cfganal.cc:1680@releases/gcc-16.2.0`. Step 4 walks the dominator tree again with a stack per variable, replacing each use with the top of stack and each definition with a fresh version.

`prune_unused_phi_nodes` at `gcc/tree-into-ssa.cc:754@releases/gcc-16.2.0` is the refinement Cytron did not have: a PHI whose result is never used is not worth inserting, and dropping it before renaming saves the renaming.

The first line matters more than it looks. `execute_update_addresses_taken` clears `TREE_ADDRESSABLE` on variables whose address was taken in ways that turn out not to need it, and every variable it clears is one more that can be renamed into SSA instead of living in memory behind `.MEM`. It runs only under `optimize`, which is one of the reasons `-O0` GIMPLE looks so different.

### 3.2 Incremental update

`update_ssa` at `gcc/tree-into-ssa.cc:3369@releases/gcc-16.2.0` is what a pass calls after changing the CFG or introducing new definitions of an already renamed variable. Its contract is that the caller registers what it changed, through `mark_sym_for_renaming` and the new and old name maps, and `update_ssa` re-renames the minimum region that could be affected rather than the whole function.

*To be written: the actual algorithm, the difference between `TODO_update_ssa`, `TODO_update_ssa_no_phi`, `TODO_update_ssa_full_phi` and `TODO_update_ssa_only_virtuals`, and what each one costs.*

### 3.3 Names and versions

`make_ssa_name_fn` at `gcc/tree-ssanames.cc:351@releases/gcc-16.2.0` allocates, from a free list if there is one. `release_ssa_name_fn` at `gcc/tree-ssanames.cc:665@releases/gcc-16.2.0` returns a name to the free list, which means **version numbers are reused**, and a name held across a release is a dangling reference to a name that now means something else.

A default definition is a version that has no defining statement because the value existed before the function did: a parameter, or an uninitialized local. `SSA_NAME_IS_DEFAULT_DEF` at `gcc/tree.h:2258@releases/gcc-16.2.0` is the flag, `ssa_default_def` at `gcc/tree-dfa.cc:297@releases/gcc-16.2.0` looks one up. A dump prints them with `(D)`, which is where `flag_9(D)` comes from.

## 4. Invariants

**I1.** Every SSA name has exactly one defining statement, and `SSA_NAME_DEF_STMT` points at it, except for default definitions where it is an empty statement.
Established by: the renamer. Checked by: `verify_ssa` at `gcc/tree-ssa.cc:1038@releases/gcc-16.2.0`. May be broken by: any pass that reuses a name, which is why `copy_ssa_name_fn` exists.

**I2.** A definition dominates every use of it, except for a use in a PHI argument, which must be dominated by the definition along the corresponding edge.
Established by: the renamer, since a stack based rename cannot produce anything else. Checked by: `verify_ssa`. May be broken by: code motion that moves a use above its definition, which is the classic new pass bug and the one `verify_ssa` catches most often.

**I3.** A PHI in block B has exactly `EDGE_COUNT (B->preds)` arguments, and argument *i* is the value arriving on `B->preds[i]`.
Established by: every edge operation fixing up PHIs. Checked by: `verify_ssa`. May be broken by: direct manipulation of `bb->preds`. This is I4 of BP-CFG seen from the other side.

**I4.** Every use of a name appears exactly once in that name's immediate use list, and the list is consistent in both directions.
Established by: `update_stmt` relinking operands whenever a statement changes. Checked by: `verify_ssa` with `check_ssa_operands`. May be broken by: writing through an operand pointer without calling `update_stmt`, which corrupts silently.

**I5.** A statement that may read memory has a `vuse`, and a statement that may write memory has both a `vdef` and a `vuse`.
Established by: `update_stmt` recomputing operands from the statement. Checked by: `verify_ssa`. May be broken by: a pass that changes a statement's memory behaviour and does not say so.

**I6.** Version numbers are unique among live names but are reused after release.
Established by: the free list in `tree-ssanames.cc`. Checked by: nothing, and that is the hazard. A saved version number is only valid as long as the name is.

*To be written: the invariants about abnormal PHIs and `SSA_NAME_OCCURS_IN_ABNORMAL_PHI`, which constrain coalescing and are why some copies survive to the end.*

## 5. Observable behaviour

`-fdump-tree-ssa` prints the function immediately after construction. Every later tree dump is also in SSA form, so the naming shows up everywhere.

Corpus entry `t05-boss-O2`, GCC 16.2.0 on aarch64-apple-darwin24 at `-O2 -g`, function `g`. Reading the `tree-ssa` dump, with the `-g` location prefixes and the `DEBUG` statements taken out so the lines fit:

```text
  <bb 6> :
  # total_1 = PHI <total_11(4), total_10(5)>
  k_12 = k_3 + 1;

  <bb 7> :
  # total_2 = PHI <total_4(2), total_1(6)>
  # k_3 = PHI <k_5(2), k_12(6)>
  if (k_3 < n_6(D))
    goto <bb 3>; [INV]
  else
    goto <bb 8>; [INV]

  <bb 8> :
  _7 = total_2;
  return _7;
```

Five things a reader can take from that and check.

The `_N` suffix is the version, and `total` has versions 1, 2, 4, 10 and 11 in one small function, which is what "assigned exactly once" costs in names and buys in analysis.

`n_6(D)` and `flag_9(D)` carry `(D)` because they are parameters, which are default definitions with no defining statement.

`_7` in block 8 has no variable name because it is anonymous, an `SSA_NAME_VAR` of null, produced by the compiler rather than named by the programmer.

Each PHI argument prints its incoming block in parentheses, which is the dump printing `preds` order rather than anything stored in the argument.

And block 7's PHIs come before its statements, which is not a formatting choice. PHIs are conceptually simultaneous and happen on entry to the block, and the representation keeps them in a separate sequence from the block's statements so that a statement iterator never sees one.

*To be written: `-fdump-tree-ssa-details` and the virtual operand output, which does not appear in this function because it touches no memory.*

## 6. Edge cases and error paths

*To be written.* The ones already known to matter:

- Abnormal edges, whose PHIs cannot be coalesced out and whose names are marked with `SSA_NAME_OCCURS_IN_ABNORMAL_PHI`. This is why `setjmp` and computed gotos cost real code.
- An uninitialized local, which gets a default definition and is exactly what the uninitialized warnings look for.
- A variable whose address is taken, which cannot be renamed and lives behind `.MEM` instead, which is what `execute_update_addresses_taken` tries to reduce.
- Irreducible loops, where PHI placement is still correct because dominance frontiers do not care about reducibility.
- A released name reused with a different type, which the free list makes possible and which is checked only under `ENABLE_GIMPLE_CHECKING`.

## 7. Interactions

Requires the CFG and dominance. Every GIMPLE optimizer consumes it. The alias oracle gives virtual operands their meaning. Out of SSA, in `rewrite_out_of_ssa` at `gcc/tree-outof-ssa.cc:1499@releases/gcc-16.2.0`, is where it ends, and it is part of expand rather than a pass of its own.

`init_ssa_operands` and `fini_ssa_operands` bracket the whole SSA lifetime, and the operand caches they own are per function.

*To be written: the interaction with inlining, which splices two SSA functions together, and with LTO streaming, which has to serialise names and versions.*

## 8. Conformance

*To be written.* `verify_ssa` under `--enable-checking` is the real test, and it is thorough: it checks the definition of every name, the dominance of every use, the PHI argument counts, and optionally the immediate use lists. There is no separate SSA test suite, and the `gcc.dg/tree-ssa` directory tests the optimizers rather than the form.

## 9. Port notes

SSA is target independent and a port supplies nothing. The only target visible consequence is indirect: how many variables can be renamed depends on how many have their address taken, which depends on the ABI, which is why the same source produces a different number of names on different targets.

**What is forced and what is not.** SSA itself is not forced. It is a choice, made in the mid 1990s, that turned out well enough that every serious optimizing compiler written since has made the same one.

Three GCC specific choices worth naming. Positional PHI arguments rather than argument to edge pairs saves a pointer per argument and costs the coupling described in section 2.2. LLVM stores the block in the argument and pays the memory instead, and the result is that LLVM's CFG edits are less delicate.

Putting all of memory in SSA as one `.MEM` name is a real design contribution and not an obvious one. The alternative, which GCC used before 2007, was a set of virtual variables per memory object, and it did not scale: the number of virtual operands per statement grew with the number of objects. One name plus a good alias oracle gives the same precision for a fixed cost per statement.

And keeping SSA on GIMPLE only, never on RTL, is a choice with a visible price. The RTL passes redo dataflow the hard way in `df-core.cc`, and the register allocator works without use def chains. A compiler being written now would put SSA on the low level IR too, and the reason GCC does not is that RTL predates SSA by a decade.
