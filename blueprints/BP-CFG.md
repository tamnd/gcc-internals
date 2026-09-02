# BP-CFG, blocks and edges

**Status:** stub
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** no
**Generated sections:** none
**Last verified:** 2026-09-02 against `releases/gcc-16.2.0`

This is a stub. It holds the data structures, the two fixed blocks, how a GIMPLE sequence becomes a graph, and what dominance is computed by and when it is valid. The pass level detail is not here: loop discovery, profile propagation, hot and cold partitioning, and the RTL side of the hooks are named and not specified. Section 2.3 could be generated from `gcc/cfg-flags.def`, which is a `.def` file with exactly the shape `bpc` reads, and that is the obvious first thing to do when this stub is promoted.

## 1. Purpose and scope

A control flow graph is a directed graph whose nodes are straight line runs of instructions and whose edges are the ways control can get from one run to the next. GCC builds one immediately after gimplification and keeps it, in one form or another, until the instructions are written out.

The thing worth understanding first is that there is only one CFG implementation. GIMPLE and RTL do not each have a graph. They share `basic_block_def` and `edge_def`, and the difference between them is one tagged union member inside the block and a table of function pointers that says how to do the operations that need to know what the instructions are. Every pass that only cares about shape works on both without knowing which it is looking at.

**What this document covers.** `basic_block_def`, `edge_def`, `control_flow_graph`. The edge and block flag sets. The two fixed blocks and what they are for. Building the graph from a GIMPLE sequence. Dominance: what computes it, what invalidates it, what `dom_state` means. The hook table as the mechanism that makes one graph serve two IRs. What `verify_flow_info` will and will not catch.

**What it does not cover.** Loops and the loop tree, which are built on top of dominance and are their own subsystem. Profile counts and probabilities beyond naming the fields. Hot and cold partitioning. Exception handling regions, which own a family of edge flags this document lists and does not explain. The RTL specific parts of CFG maintenance, including cfglayout mode. `cleanup_cfg` and the jump threading it enables.

**Position in the pipeline.** Built by `pass_build_cfg` at `gcc/passes.def:41@releases/gcc-16.2.0`, the eleventh pass in `all_lowering_passes`, after control flow and exception handling have been lowered and before SSA. Kept alive through GIMPLE optimization, carried across expand into RTL, and torn down near the end of the RTL pipeline.

**Inputs and outputs as properties.** `pass_build_cfg` requires `PROP_gimple_leh` and provides `PROP_cfg | PROP_loops`, at `gcc/tree-cfg.cc:350@releases/gcc-16.2.0`. Nearly every pass after it lists `PROP_cfg` in `properties_required`, which is the machine readable version of the previous paragraph.

## 2. Data structures

### 2.1 The block

`basic_block_def` at `gcc/basic-block.h:117@releases/gcc-16.2.0`.

| Field | What it holds |
|---|---|
| `preds`, `succs` | vectors of `edge`, the incoming and outgoing edges |
| `aux` | scratch space for whatever pass is running, not garbage collected |
| `loop_father` | the innermost loop containing this block |
| `dom[2]` | two nodes in an ET tree, one for dominance and one for postdominance |
| `prev_bb`, `next_bb` | the block chain, which is a total order and not the same thing as the graph |
| `il` | a union: `gimple_bb_info` or the RTL pair, tagged by `BB_RTL` in `flags` |
| `flags` | see `gcc/cfg-flags.def` |
| `index` | the block number, which is what a dump prints |
| `count` | a `profile_count`, how often this block is expected to run |

Two of those repay attention. `prev_bb` and `next_bb` are a linear order over the blocks that exists alongside the graph and is not derived from it. For RTL it is the layout order, the order the blocks will appear in the output, and getting it wrong produces working code with unnecessary jumps in it. For GIMPLE it is mostly the order the blocks were created in, and passes that want a meaningful order compute one instead.

And `il` is a union with a `STATIC_ASSERT` under it at `gcc/basic-block.h:156@releases/gcc-16.2.0` proving `rtl_bb_info` is at least as big as `gimple_bb_info`. The GIMPLE half is stored inline and the RTL half behind a pointer, and the assert is what stops somebody adding a field to the GIMPLE side and silently growing every basic block in the compiler.

### 2.2 The edge

`edge_def` at `gcc/basic-block.h:26@releases/gcc-16.2.0` is `src`, `dest`, a `gimple_seq` or `rtx_insn *` of instructions queued on the edge, an `aux`, a `goto_locus`, `dest_idx`, `flags` and a `probability`.

`dest_idx` is the edge's own index inside `dest->preds`. It is stored rather than searched for because PHI arguments are positional: argument *i* of a PHI in block B belongs to `B->preds[i]`, so every operation that reorders a block's predecessors has to reorder every PHI in it, and `dest_idx` is what makes that cost proportional to the change rather than to the graph.

`insns` is the mechanism behind `insert_on_edge`. Code that logically belongs on the transition rather than in either endpoint sits there until `commit_edge_insertions` decides whether it can go at the end of the source, the start of the destination, or needs a new block split into the middle.

### 2.3 The flags

`gcc/cfg-flags.def` declares **15** block flags and **18** edge flags, in one file, included twice with different macros, which is the same `.def` trick GIMPLE codes and passes use.

The edge flags that matter to a reader of a dump:

| Flag | Meaning |
|---|---|
| `EDGE_FALLTHRU` | control reaches `dest` without a jump, so `dest` must follow `src` in layout order |
| `EDGE_TRUE_VALUE`, `EDGE_FALSE_VALUE` | the two ways out of a conditional |
| `EDGE_ABNORMAL` | control transfer the CFG cannot fully describe |
| `EDGE_ABNORMAL_CALL`, `EDGE_EH` | the two common reasons for the above |
| `EDGE_FAKE` | not a real transfer, added so an analysis has a connected graph to work on |
| `EDGE_DFS_BACK` | a back edge, computed by `mark_dfs_back_edges`, not maintained |
| `EDGE_IRREDUCIBLE_LOOP` | part of a loop with more than one entry |
| `EDGE_LOOP_EXIT` | leaves a natural loop |
| `EDGE_CROSSING` | crosses the hot and cold partition boundary |
| `EDGE_EXECUTABLE` | reachable, as decided by whatever propagation pass set it |

`EDGE_COMPLEX` at `gcc/basic-block.h:69@releases/gcc-16.2.0` is the union of the abnormal and EH flags, and a great deal of code is written as "if the edge is complex, do not touch it".

`EDGE_DFS_BACK` and `EDGE_EXECUTABLE` are analysis results parked in the graph, not properties of it. They are correct only immediately after the analysis that set them, and nothing prevents a pass from reading a stale one.

### 2.4 The graph itself

`control_flow_graph` at `gcc/cfg.h:38@releases/gcc-16.2.0` hangs off `struct function`. It holds the entry and exit block pointers, a vector indexed by block number, the block and edge counts, the next free block number, a label to block map, the profile status, and for each of the two directions a `dom_state` and a block count.

Every field is spelled `x_something`, and the comment at `gcc/cfg.h:35@releases/gcc-16.2.0` says why: the unprefixed names are already taken by macros that expand to `cfun->cfg->x_whatever`, so the field cannot be called what it is called everywhere else. That is the cost of the `cfun` implicit argument, paid once in this header.

`x_last_basic_block` is the next number to hand out, not the largest one in use. Numbers are not reused, so it grows monotonically and `x_last_basic_block` exceeds `x_n_basic_blocks` in any function that has had a block removed. `compact_blocks` at `gcc/cfg.cc:169@releases/gcc-16.2.0` is the renumbering, and it is called rarely and deliberately, because it invalidates every saved block number in the compiler.

### 2.5 The hooks

`struct cfg_hooks` at `gcc/cfghooks.h:78@releases/gcc-16.2.0` is **33** function pointers and a name. `gimple_cfg_hooks`, `rtl_cfg_hooks` and `cfg_layout_rtl_cfg_hooks` are the three tables. `set_cfg_hooks` installs one, and everything from `split_block` to `duplicate_block` to `verify_flow_info` goes through the installed table.

This is the whole answer to how one CFG serves two IRs. Anything that needs to know what an instruction is goes in the table, and anything that only needs `preds` and `succs` does not.

## 3. Algorithms

### 3.1 Building the graph

`build_gimple_cfg` at `gcc/tree-cfg.cc:182@releases/gcc-16.2.0`, called from `execute_build_cfg` at `gcc/tree-cfg.cc:328@releases/gcc-16.2.0`.

```text
build_gimple_cfg(seq):
    gimple_register_cfg_hooks()    # install the GIMPLE table
    init_empty_tree_cfg()          # entry and exit blocks exist, nothing else
    make_blocks(seq)               # cut the sequence into blocks
    if the function has no blocks: create one empty one
    grow basic_block_info to fit
    cleanup_dead_labels()          # before grouping, or the grouping misses merges
    group_case_labels()            # fewer switch targets means fewer edges
    make_edges()                   # join the blocks up
    assign_discriminators()
    cleanup_dead_labels()          # again, on what the edges left behind
```

The two calls to `cleanup_dead_labels` and the placement of `group_case_labels` before `make_edges` are both there for the same reason, which the comment at `gcc/tree-cfg.cc:206@releases/gcc-16.2.0` states: merging switch cases first means fewer edges get built, rather than getting built and then removed.

`make_blocks` at `gcc/tree-cfg.cc:562@releases/gcc-16.2.0` walks the statement sequence once, starting a new block at any statement that begins one, which is a label, or the statement after one that ends a block, which is a conditional, a goto, a return, a switch or a call that can throw. `make_edges` at `gcc/tree-cfg.cc:924@releases/gcc-16.2.0` then walks the blocks and asks each last statement where it can go, with the per statement work in `make_edges_bb` at `gcc/tree-cfg.cc:810@releases/gcc-16.2.0`.

Nothing about that is surprising, and that is worth saying, because the CFG is one of the few parts of GCC where the textbook algorithm is the algorithm.

### 3.2 Dominance

`calculate_dominance_info` at `gcc/dominance.cc:720@releases/gcc-16.2.0` runs Lengauer and Tarjan, as the file's own header comment at `gcc/dominance.cc:21@releases/gcc-16.2.0` states. The result is stored as an ET tree in `bb->dom[dir]`, not as an array of immediate dominators, which is what makes `dominated_by_p` at `gcc/dominance.cc:1125@releases/gcc-16.2.0` a constant time query and also what makes incremental update possible at all.

`cdi_direction` is `CDI_DOMINATORS` or `CDI_POST_DOMINATORS`, and the two are the same computation on the graph and on the reverse graph. Postdominance needs every block to reach the exit, which is why `connect_infinite_loops_to_exit` at `gcc/cfganal.cc:622@releases/gcc-16.2.0` exists and why it adds `EDGE_FAKE` edges: an infinite loop has no path to the exit and postdominance is undefined without one.

The queries a pass actually uses:

| Call | Answers |
|---|---|
| `get_immediate_dominator (dir, bb)` | the parent in the dominator tree |
| `get_dominated_by (dir, bb)` | the children, as a vector |
| `dominated_by_p (dir, a, b)` | does *b* dominate *a* |
| `nearest_common_dominator (dir, a, b)` | the meet |

`dom_state` at `gcc/dominance.h:31@releases/gcc-16.2.0` is three values. `DOM_NONE` means not computed. `DOM_OK` means computed and the fast query data is usable. `DOM_NO_FAST_QUERY` is the interesting one: the tree is correct but the numbering that makes `dominated_by_p` constant time is not, because an incremental update touched the tree without renumbering it. Queries still work and are slower.

### 3.3 Orders

There is no single canonical order over the blocks, and passes that need one say which.

| Function | Produces |
|---|---|
| `post_order_compute` at `gcc/cfganal.cc:655@releases/gcc-16.2.0` | depth first postorder |
| `pre_and_rev_post_order_compute` at `gcc/cfganal.cc:1075@releases/gcc-16.2.0` | preorder and reverse postorder in one walk |
| `mark_dfs_back_edges` at `gcc/cfganal.cc:62@releases/gcc-16.2.0` | sets `EDGE_DFS_BACK`, returns whether any was found |
| `FOR_EACH_BB_FN` at `gcc/basic-block.h:212@releases/gcc-16.2.0` | the `next_bb` chain, which is not a graph order at all |

Reverse postorder is the one a forward dataflow analysis wants. `FOR_EACH_BB_FN` is the one most code uses, because most code does not care.

*To be written: the dominator tree walk helpers, and how `pass_build_cfg` interacts with the order the gimplifier produced.*

## 4. Invariants

**I1.** ENTRY_BLOCK is 0 and EXIT_BLOCK is 1, both blocks always exist, and no user block has either number.
Established by: `NUM_FIXED_BLOCKS` at `gcc/basic-block.h:265@releases/gcc-16.2.0` and `init_empty_tree_cfg`. Checked by: `verify_flow_info`. May be broken by: nobody. This is why the first real block in every dump is `<bb 2>`.

**I2.** ENTRY has no predecessors and EXIT has no successors.
Established by: the CFG construction. Checked by: `verify_flow_info` at `gcc/cfghooks.cc:105@releases/gcc-16.2.0`. May be broken by: a pass that redirects an edge without checking its endpoints.

**I3.** For every edge *e* in `bb->succs`, *e* appears in `e->dest->preds`, and `e->dest->preds[e->dest_idx]` is *e*.
Established by: `connect_src` and `connect_dest` at `gcc/cfg.cc:215@releases/gcc-16.2.0` being the only two places an edge is attached. Checked by: `verify_flow_info`. May be broken by: code that manipulates the vectors directly, which is why `unchecked_make_edge` at `gcc/cfg.cc:278@releases/gcc-16.2.0` has that name.

**I4.** A PHI in block B has exactly as many arguments as B has predecessors, and argument *i* corresponds to `B->preds[i]`.
Established by: every edge insertion and removal fixing up the PHIs as it goes. Checked by: `verify_ssa`. May be broken by: any CFG change, which is the reason CFG manipulation on SSA is done through helpers rather than by hand.

**I5.** A block with a fallthrough successor is immediately followed by that successor in the `next_bb` chain, once RTL is out of cfglayout mode.
Established by: `cfg_layout_finalize`. Checked by: `rtl_verify_flow_info`. May be broken by: nobody, after that point. Before it, in cfglayout mode, the chain is free and the fallthrough is notional, which is the entire difference between the two modes.

**I6.** Dominance information is either absent or correct. It is never silently stale.
Established by: passes calling `free_dominance_info` before changing the graph in ways they do not want to maintain. Checked by: `verify_dominators` at `gcc/dominance.cc:1165@releases/gcc-16.2.0`, under checking only. May be broken by: a pass that changes the CFG and does not say so. This is the invariant most often gotten wrong in a new pass, and the failure mode is a miscompile rather than a crash.

*To be written: the invariants about profile counts summing across edges, and about `aux` being null at pass boundaries.*

## 5. Observable behaviour

`-fdump-tree-cfg` prints the graph right after it is built. Any later `-fdump-tree-*` prints blocks and their statements, and `-fdump-tree-all-graph` writes a dot file per pass.

Corpus entry `t05-boss-O2` records GCC 16.2.0 on aarch64-apple-darwin24 compiling a loop with a conditional in it at `-O2 -g`. The `tree-ssa` dump for function `g` shows seven blocks, numbered 2 through 8.

| Block | Ends with | Successors |
|---|---|---|
| 2 | `goto <bb 7>` | 7 |
| 3 | `if (flag_9(D) != 0)` | 4 true, 5 false |
| 4 | `goto <bb 6>` | 6 |
| 5 | falls through | 6 |
| 6 | falls through | 7 |
| 7 | `if (k_3 < n_6(D))` | 3 true, 8 false |
| 8 | `return _7` | EXIT |

Four things a reader can read straight off that table. Numbering starts at 2, which is I1 made visible. Block 7 is the loop header: it has the PHIs and it is entered both from block 2 and from block 6, so 6 to 7 is the back edge. Block 6 exists only because two paths merge there, and its PHI has two arguments in the order `(4)` then `(5)`, which is `preds` order and is I4 made visible. And the loop was rotated before this dump: block 2 jumps straight to the test in block 7 rather than falling into the body, which is why the body is blocks 3 through 6 and the test is at the bottom.

*To be written: `-fdump-tree-cfg` raw output as distinct from `tree-ssa`, and the dot output format.*

## 6. Edge cases and error paths

*To be written.* The ones already known to matter:

- A function whose body cannot reach the exit, which is what `connect_infinite_loops_to_exit` and `EDGE_FAKE` are for.
- Abnormal edges, which cannot be split, cannot be redirected, and constrain almost every transformation. `EDGE_COMPLEX` is the test.
- Critical edges, an edge from a block with several successors to a block with several predecessors, which have nowhere to put code and are split by `split_critical_edges` when a pass needs somewhere.
- Irreducible loops, where the dominator tree is still well defined but the loop tree is not, and passes have to check.
- Unreachable blocks, which are legal in the structure and removed by `cleanup_cfg` rather than prevented.

## 7. Interactions

Built by `pass_build_cfg`, consumed by essentially everything after it. SSA construction needs dominance and the dominance frontier. The loop tree is built on dominance and back edges. Expand carries the graph from GIMPLE to RTL rather than rebuilding it. The final passes tear it down.

`cfun->cfg` is per function, which means the CFG follows a function across the inter procedural passes and there is never more than one live at a time in a pass that has not asked for another with `push_cfun`.

*To be written: the relationship with `cleanup_cfg`, and the point in the RTL pipeline where the graph stops being maintained.*

## 8. Conformance

*To be written.* `verify_flow_info` runs under `--enable-checking` after every pass and is the real conformance test. It checks the structural invariants above, and it does not check anything about the instructions in the blocks, which is `verify_gimple` and `verify_rtl_sharing`. The `gcc.dg/torture` suite exercises the CFG indirectly by compiling a lot of code with checking on, and there is no test suite that constructs a CFG directly.

## 9. Port notes

The CFG is target independent and this is one of the few blueprints where that is a real answer rather than a hedge. A port supplies nothing. Targets influence the graph only through what expand generates and through whether the target has conditional execution or delay slots, which changes what the RTL passes do to it, not what it is.

**What is forced and what is not.** A basic block graph is forced by wanting to write dataflow analyses, and every optimizing compiler has one.

Three things GCC chose and did not have to. Sharing one node type between two IRs through a tagged union and a hook table is unusual: LLVM has one IR and so does not need it, and a compiler with two IRs could as easily have two graphs and a converter between them. The saving is real, roughly every shape only pass in the compiler, and the cost is a union and thirty three function pointers.

Storing dominance as an ET tree rather than an immediate dominator array is a bet that incremental updates are common enough to pay for the complexity. `DOM_NO_FAST_QUERY` is the visible seam in that bet.

And the two fixed blocks are pure convenience. Nothing requires an entry node to be a block, and a compiler could use a distinguished null or a separate root list. Making them real blocks means every algorithm that walks the graph gets the boundary for free, at the cost of every algorithm that iterates blocks having to remember to skip them, which is what the split between `FOR_EACH_BB_FN` and `FOR_ALL_BB_FN` at `gcc/basic-block.h:244@releases/gcc-16.2.0` is about.
