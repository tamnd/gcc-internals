# BP-PIPELINE, the shape of a compilation

**Status:** complete
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** no
**Generated sections:** none
**Last verified:** 2026-09-02 against `releases/gcc-16.2.0`

This document specifies the control flow of one compilation: which components run, in which order, what each one hands the next, and where the pass manager begins and ends. It is the map every other blueprint hangs off. Where another document owns a component, this one states the boundary and the handover and stops.

## 1. Purpose and scope

A GCC compilation is fourteen stages, of which nine are passes and five are not. The five that are not passes are the ones a reader working from `passes.def` will never see, and stating that boundary is the first job of this document.

**What this document covers.** The fourteen stages and their order. The pass manager: the pass object model, the five pass lists, how the tree of passes is built and walked, the gate, the property system, the TODO system, dump file registration and naming, and the command line controls that add, remove or override a pass. The handover between the front end and the pass manager, between GIMPLE and RTL, and between the last pass and the assembler. The interprocedural phase and the five hooks an IPA pass provides. What a reader can observe from outside, and the exact relationship between the pass list and the dump files.

**What it does not cover.** The internals of any individual pass, including the ones named here as stage anchors. The IR formats, which are `BP-GIMPLE` and `BP-RTL`. Register allocation, which is `BP-REGALLOC`. Assembly emission past the point where `final` is entered, which is `BP-FINAL`. LTO, which changes when the pass lists run but not what they contain, and needs a document of its own. Plugins, beyond naming the five callback points the pass manager invokes. The garbage collector, beyond naming the two points where the pass manager offers it a collection opportunity. Offloading and the OpenMP pipeline.

**Position in the pipeline.** This document is the pipeline, so it has no position in it.

**Inputs and outputs as properties.** The compilation starts with no function and no properties. It ends with a text file. Between those, the property word `cfun->curr_properties` is the pass manager's model of what the IR currently is, and section 4 gives the invariants it enforces.

## 2. Data structures

### 2.1 pass_data

`struct pass_data` at `gcc/tree-pass.h:40@releases/gcc-16.2.0`, nine fields, all of them constant for the life of a pass. Every pass in GCC is a static instance of a class that inherits from this.

| Field | Type | What it holds |
|---|---|---|
| `type` | `enum opt_pass_type` | one of `GIMPLE_PASS`, `RTL_PASS`, `SIMPLE_IPA_PASS`, `IPA_PASS` |
| `name` | `const char *` | the short name, which becomes the dump file suffix and the `-fdump` key |
| `optinfo_flags` | `optgroup_flags_t` | which `-fopt-info` group this pass reports under |
| `tv_id` | `timevar_id_t` | the timer this pass is charged to, or `TV_NONE` |
| `properties_required` | `unsigned int` | properties that must hold on entry |
| `properties_provided` | `unsigned int` | properties that hold on exit and did not have to hold on entry |
| `properties_destroyed` | `unsigned int` | properties that do not hold on exit |
| `todo_flags_start` | `unsigned int` | cleanups to run before `execute` |
| `todo_flags_finish` | `unsigned int` | cleanups to run after `execute` |

A `name` beginning with `*` suppresses dump file registration, which is how a pass runs without being nameable on the command line. `register_dump_files` at `gcc/passes.cc:896@releases/gcc-16.2.0` tests the first character.

### 2.2 opt_pass

`class opt_pass : public pass_data` at `gcc/tree-pass.h:73@releases/gcc-16.2.0`. This is `pass_data` plus four virtual functions and three mutable fields.

| Member | Kind | Meaning |
|---|---|---|
| `gate (function *)` | virtual, defaults to `true` | whether this pass and its sub-passes run on this function |
| `execute (function *)` | virtual, defaults to nothing | the pass, returning extra TODO flags to run afterwards |
| `clone ()` | virtual, defaults to an abort | required of any pass listed twice |
| `set_pass_param (unsigned, bool)` | virtual | how a pass listed twice is told which instance it is |
| `sub` | `opt_pass *` | the first of a list of passes run only if this pass ran |
| `next` | `opt_pass *` | the next pass at this level, run whatever this pass did |
| `static_pass_number` | `int` | assigned at pass manager construction, used in dump file names |

The default `execute` does nothing, so a pass whose only content is a `sub` list is legal and common. That is how the pass list expresses grouping.

### 2.3 The four pass types

```text
GIMPLE_PASS       runs on one function, cfun set, IR is GIMPLE
RTL_PASS          runs on one function, cfun set, IR is RTL
SIMPLE_IPA_PASS   runs once, cfun is nothing, sees the whole symbol table
IPA_PASS          runs once, cfun is nothing, and has five extra hooks
```

`execute_one_pass` at `gcc/passes.cc:2579@releases/gcc-16.2.0` asserts the `cfun` half of this on entry, so the distinction is checked rather than documented.

### 2.4 ipa_opt_pass_d

`class ipa_opt_pass_d : public opt_pass` at `gcc/tree-pass.h:141@releases/gcc-16.2.0`. An IPA pass is split in two because LTO writes the analysis to disk and reads it back in a later process.

| Hook | When it runs |
|---|---|
| `generate_summary` | after the bodies are available, to build the pass's per node data |
| `write_summary` | when writing an LTO object, to serialize that data |
| `read_summary` | when reading LTO objects back, to deserialize it |
| `write_optimization_summary` | to serialize the decisions rather than the analysis |
| `read_optimization_summary` | to deserialize them |
| `stmt_fixup` | to turn statement uids back into statements after reading |
| `function_transform` | to apply the decision to one function body, later |
| `variable_transform` | the same, for a variable |

`function_transform` is the field that makes an IPA pass unlike every other pass: the decision is made once for the whole program, and applying it to a function is deferred. `execute_one_pass` pushes the pass onto `node->ipa_transforms_to_apply` for every function with a body, at `gcc/passes.cc:2723@releases/gcc-16.2.0`, and the transform runs when that function is next compiled.

`class simple_ipa_opt_pass` at `gcc/tree-pass.h:197@releases/gcc-16.2.0` has none of that. It has one `execute` and it runs where it sits.

### 2.5 The property word

`cfun->curr_properties`, a bitmask, values at `gcc/tree-pass.h:207@releases/gcc-16.2.0`. Twenty two bits in GCC 16. The ones that describe the shape of the IR rather than one lowering step:

| Property | Meaning | Provided by |
|---|---|---|
| `PROP_gimple_any` | the body is GIMPLE at all | the gimplifier, before any pass |
| `PROP_gimple_lcf` | control flow is lowered, no nested constructs | `pass_lower_cf` |
| `PROP_gimple_leh` | exception handling is lowered | `pass_lower_eh` |
| `PROP_cfg` | the body is basic blocks and edges | `pass_build_cfg` |
| `PROP_ssa` | every name is written once, phi nodes at the joins | `pass_build_ssa` |
| `PROP_rtl` | the body is an insn chain | `pass_expand` |
| `PROP_cfglayout` | the RTL CFG is in layout mode | `pass_into_cfglayout` |
| `PROP_loops` | loop structures are built and must be maintained | `pass_tree_loop_init` |
| `PROP_no_crit_edges` | no edge goes from a multi-successor block to a multi-predecessor one | `pass_split_crit_edges` |

`PROP_gimple` at `gcc/tree-pass.h:235@releases/gcc-16.2.0` is the conjunction of the lowering bits, and is what `execute_one_pass` tests to set `in_gimple_form`.

`PROP_ssa` and `PROP_rtl` are the two that matter most, because they are the two boundaries. `pass_build_ssa` provides `PROP_ssa`. `pass_expand` destroys it and provides `PROP_rtl` in the same pass.

### 2.6 The TODO word

`TODO_*` values at `gcc/tree-pass.h:240@releases/gcc-16.2.0`. A TODO is a cleanup the pass manager performs on the pass's behalf, so that every pass does not reimplement it. The ones an implementer has to model:

| Flag | Effect |
|---|---|
| `TODO_cleanup_cfg` | merge blocks, remove unreachable ones, simplify jumps |
| `TODO_update_ssa` | recompute SSA form for names marked as needing it |
| `TODO_update_ssa_no_phi` | the same, where the pass promises no new phi nodes are needed |
| `TODO_update_ssa_only_virtuals` | the same, for the virtual operands only |
| `TODO_remove_unused_locals` | drop declarations nothing references |
| `TODO_rebuild_cgraph_edges` | recompute the call graph edges out of this function |
| `TODO_rebuild_alias` | recompute the alias information |
| `TODO_update_address_taken` | recompute which variables have their address taken |
| `TODO_df_finish`, `TODO_df_verify` | dataflow bookkeeping, RTL only |
| `TODO_discard_function` | the pass decided this function should not be compiled |
| `TODO_do_not_ggc_collect` | suppress the collection point after this pass |
| `TODO_verify_il` | verify the IR, added by the pass manager and never by a pass |

A pass declares TODOs in `todo_flags_start` and `todo_flags_finish`, and can return more from `execute`. The returned set and the declared set are unioned, at `gcc/passes.cc:2702@releases/gcc-16.2.0`.

`TODO_verify_il` is special: `execute_one_pass` asserts under checking that no pass declares or returns it, then adds it itself to every finish set. A pass cannot opt out of verification.

`TODO_discard_function` is the one TODO that ends the pass rather than following it. Section 3.3 gives the path.

### 2.7 The five pass lists

The pass tree has five roots, all declared in `gcc/passes.def` and all built by the `pass_manager` constructor at `gcc/passes.cc:1577@releases/gcc-16.2.0`.

| List | Declared at | When it runs | Pass types in it |
|---|---|---|---|
| `all_lowering_passes` | `gcc/passes.def:30@releases/gcc-16.2.0` | per function, as soon as the body is finalized | `GIMPLE_PASS` |
| `all_small_ipa_passes` | `gcc/passes.def:49@releases/gcc-16.2.0` | once, after every body is available | `SIMPLE_IPA_PASS`, with GIMPLE sub-lists |
| `all_regular_ipa_passes` | `gcc/passes.def:163@releases/gcc-16.2.0` | once, the real interprocedural phase | `IPA_PASS` |
| `all_late_ipa_passes` | `gcc/passes.def:192@releases/gcc-16.2.0` | once, after the regular IPA passes | `SIMPLE_IPA_PASS` |
| `all_passes` | `gcc/passes.def:199@releases/gcc-16.2.0` | per function, at expansion time | `GIMPLE_PASS` then `RTL_PASS` |

`all_passes` is the long one. It runs the remaining tree passes, then `pass_expand` at `gcc/passes.def:460@releases/gcc-16.2.0`, then every RTL pass, and terminates at `gcc/passes.def:577@releases/gcc-16.2.0`.

The nesting in `passes.def` is expressed by three macros. `NEXT_PASS` appends at the current level. `PUSH_INSERT_PASSES_WITHIN` opens a `sub` list on the pass most recently added. `POP_INSERT_PASSES` closes it. A pass with a `sub` list is a group, and the group's gate controls whether the whole group runs.

### 2.8 The dump file identity of a pass

`register_one_dump_file` at `gcc/passes.cc:833@releases/gcc-16.2.0` derives four strings from a pass, and these are the entire externally visible naming of the pipeline.

```text
prefix       "tree-" for GIMPLE_PASS
             "rtl-"  for RTL_PASS
             "ipa-"  for IPA_PASS and SIMPLE_IPA_PASS

dot_name     "." + name + num          the file suffix on disk
flag_name    prefix + name + num       the -fdump-<flag_name> key
glob_name    prefix + name             the key without the instance number
full_name    prefix + pass->name + num the plugin-visible name
```

`num` is the instance number, empty for the first instance and a decimal count after that, which is why the dumps are `tree-vrp1` and `tree-vrp2` rather than two files with one name. If `pass->name` contains a space, everything up to and including the first space is a disambiguating prefix and is dropped from the dump names but kept in `full_name`.

The prefix is derived from the pass type and nothing else. A reader can therefore read the type of any pass off the name of its dump file, with no lookup.

## 3. Algorithms

### 3.1 The compilation, top to bottom

```text
function compile (files: sequence of Path) -> ok or error
    complexity: O(size of the translation unit), with no bound stated for the passes

    for each file in files
        # Stages 1 to 4. None of these is a pass.
        text = preprocess(file)
        for each declaration in parse(text)
            if declaration is a function with a body
                gimplify(declaration)
                finalize(declaration)        # hand it to the symbol table

        # The symbol table now holds every function and variable.
        analyze_all()                        # cgraph_node::analyze per node
        run(all_lowering_passes) per function
        run(all_small_ipa_passes) once
        run(all_regular_ipa_passes) once
        run(all_late_ipa_passes) once

        for each node in symbol_table in topological order
            # Stages 9 to 13, one function at a time.
            apply(node.ipa_transforms_to_apply)
            run(all_passes) on node

        write_the_rest()                     # variables, sections, debug info

    # Stage 14 is a different program.
    return ok
```

`symbol_table::compile` at `gcc/cgraphunit.cc:2343@releases/gcc-16.2.0` is the middle of that, `ipa_passes` at `gcc/cgraphunit.cc:2231@releases/gcc-16.2.0` runs the three IPA lists, and `expand_all_functions` at `gcc/cgraphunit.cc:1990@releases/gcc-16.2.0` is the per function loop at the end. `compile_file` at `gcc/toplev.cc:449@releases/gcc-16.2.0` is above all of it.

The topological order in the last loop is not decoration. A callee is compiled before its callers where the call graph allows, so that the caller can use what compiling the callee found out.

### 3.2 Walking a pass list

```text
function execute_pass_list (fn: Function, pass: Pass) -> nothing
    complexity: O(number of passes), each one charged separately

    while pass != nothing
        if cfun == nothing
            return                    # a pass discarded the function
        if execute_one_pass(pass) and pass.sub != nothing
            execute_pass_list(fn, pass.sub)
        pass = pass.next

    if cfun != nothing and fn.cfg != nothing
        free_dominance_info(CDI_DOMINATORS)
        free_dominance_info(CDI_POST_DOMINATORS)
```

`execute_pass_list_1` at `gcc/passes.cc:2760@releases/gcc-16.2.0`, with the wrapper at `gcc/passes.cc:2777@releases/gcc-16.2.0`. Fourteen lines, and it is the whole of what "GCC runs its passes" means.

Two things in it are worth stating as rules. A sub-list runs only if its parent ran, and `execute_one_pass` returns whether it ran. The `cfun == nothing` test at the top of each iteration is how `TODO_discard_function` unwinds: the pass that discarded the function did not return, it removed the function, and the walk notices on the next iteration.

Dominance information is freed at the end of every list, unconditionally. A pass that wants dominators computes them.

### 3.3 Running one pass

```text
function execute_one_pass (pass: Pass) -> boolean
    complexity: O(the pass), plus O(function) for verification under checking

    if pass.type in {IPA_PASS, SIMPLE_IPA_PASS}
        assert cfun == nothing
    else
        assert cfun != nothing

    current_pass = pass

    # 1. The gate, and the three things that can override it.
    status = pass.gate(cfun)
    status = override_gate_status(pass, current_function_decl, status)
    status = plugin_override(PLUGIN_OVERRIDE_GATE, status)
    if not status
        return false

    # 2. The __GIMPLE and __RTL entry points skip forward to a named pass.
    if should_skip_pass_p(pass)
        skip_pass(pass)
        return true

    # 3. Bookkeeping the pass does not do itself.
    in_gimple_form = (cfun.curr_properties and PROP_gimple) != 0
    pass_init_dump_file(pass)
    if pass.tv_id != TV_NONE
        timevar_push(pass.tv_id)

    # 4. The declared preconditions.
    execute_todo(pass.todo_flags_start)
    if flag_checking
        for each function f
            verify_curr_properties(f, pass.properties_required)

    # 5. The pass.
    todo_after = pass.execute(cfun)

    # 6. The one early exit.
    if todo_after and TODO_discard_function
        timevar_pop; pass_fini_dump_file(pass)
        free the dominance info; pop_cfun()
        release the body of the function
        return true

    # 7. The property word, then the declared postconditions plus verification.
    for each function f
        update_properties_after_pass(f, pass)
    execute_todo(todo_after or pass.todo_flags_finish or TODO_verify_il)
    verify_interpass_invariants()
    if pass.tv_id != TV_NONE
        timevar_pop(pass.tv_id)

    # 8. An IPA pass defers its body transform to every function with a body.
    if pass.type == IPA_PASS and pass.function_transform != nothing
        for each node with a gimple body and not inlined_to
            append(node.ipa_transforms_to_apply, pass)
    else if dump_file != nothing
        for each function f
            execute_function_dump(f, pass)

    if current_function_decl == nothing
        symtab.process_new_functions()

    pass_fini_dump_file(pass)
    assert not (cfun.curr_properties and PROP_gimple and pass.type == RTL_PASS)
    current_pass = nothing
    if not ((todo_after or pass.todo_flags_finish) and TODO_do_not_ggc_collect)
        ggc_collect()
    return true
```

`gcc/passes.cc:2579@releases/gcc-16.2.0`. The order of steps 4, 5 and 7 is the contract between the pass manager and a pass: preconditions are verified before `execute` and postconditions after, and a pass that breaks a property it did not declare is caught at step 7 of the next pass that requires it rather than at the point of damage.

Step 8 is the only place `else if dump_file` appears, and it has a consequence a reader will notice: an IPA pass with a `function_transform` writes no per function dump at the point it runs, because at that point no function has been transformed.

### 3.4 The gate, and the three ways past it

```text
function gate_of (pass: Pass, fn: Function) -> boolean
    complexity: O(1), plus whatever the pass's own gate does

    status = pass.gate(fn)                        # the pass's own condition
    status = override_gate_status(pass, fn, status)
    status = plugin_override(status)
    return status

function override_gate_status (pass: Pass, fn: Function, status: boolean) -> boolean
    complexity: O(log n) in the number of -fenable and -fdisable options

    explicit = is_pass_explicitly_enabled_or_disabled(pass, fn)
    if explicit == enabled
        return true
    if explicit == disabled
        return false
    return status
```

`override_gate_status` at `gcc/passes.cc:2426@releases/gcc-16.2.0`, the lookup at `gcc/passes.cc:1251@releases/gcc-16.2.0`, and the option parsing at `gcc/passes.cc:1066@releases/gcc-16.2.0`.

`-fenable-<kind>-<pass>` and `-fdisable-<kind>-<pass>` beat the pass's own gate in both directions. Enabling a pass whose own gate said no is legal and will run it, which is the point of the option and also the reason it can produce a compiler that crashes.

### 3.5 The interprocedural list

```text
function execute_ipa_pass_list (pass: Pass) -> nothing
    complexity: O(number of ipa passes * size of the symbol table)

    while pass != nothing
        assert cfun == nothing
        assert pass.type in {IPA_PASS, SIMPLE_IPA_PASS}
        if execute_one_pass(pass) and pass.sub != nothing
            if pass.sub.type == GIMPLE_PASS
                # A GIMPLE sub-list under an IPA pass runs per function,
                # in topological order over the call graph.
                for each function f in call graph topological order
                    execute_pass_list(f, pass.sub)
            else
                execute_ipa_pass_list(pass.sub)
        symtab.process_new_functions()
        pass = pass.next
```

`gcc/passes.cc:3111@releases/gcc-16.2.0`. The GIMPLE sub-list case is how the early optimizers run: they are a per function list nested under an IPA pass, so they see one function at a time while the enclosing pass sees the whole program.

`process_new_functions` after every pass is not optional. An IPA pass can create functions, and a pass list that did not look would compile a body nothing ran the earlier passes on.

### 3.6 Where GIMPLE stops being GIMPLE

`pass_expand` at `gcc/passes.def:460@releases/gcc-16.2.0`, implemented at `gcc/cfgexpand.cc:7028@releases/gcc-16.2.0`. It is an `RTL_PASS` that requires `PROP_ssa`, `PROP_cfg`, `PROP_gimple_leh`, `PROP_gimple_lcx`, `PROP_gimple_lvec` and `PROP_gimple_lva`, destroys `PROP_ssa` and `PROP_gimple`, and provides `PROP_rtl`, all at `gcc/cfgexpand.cc:6999@releases/gcc-16.2.0`.

Two things happen in that one pass and conflating them is the most common wrong model of the back end.

```text
1. Out of SSA.  Every SSA name becomes a pseudo register, and every phi node
   becomes a copy on each incoming edge.  There are no phi nodes in RTL and no
   RTL pass has ever seen one.

2. Expansion.   Every GIMPLE statement becomes one or more RTL insns, chosen
   through the optab tables and the machine description named patterns.
```

The CFG survives. `pass_expand` builds the insn chain inside the existing basic blocks, and the RTL CFG is the same graph with different contents. Every RTL pass up to `pass_free_cfg` has blocks and edges.

### 3.7 The stages that are not passes

Five of the fourteen stages have no entry in `passes.def`, no `pass_data`, no dump file registered by `register_one_dump_file`, and no line in `-fdump-passes`.

| Stage | Where it is | Why it is not a pass |
|---|---|---|
| 1, the driver | `gcc/gcc.cc`, a separate program | it runs `cc1`, it is not inside it |
| 2, preprocess | libcpp, driven by `c_common_parse_file` at `gcc/c-family/c-opts.cc:1419@releases/gcc-16.2.0` | it runs before any function exists |
| 3, parse | `c_parse_file` at `gcc/c/c-parser.cc:31269@releases/gcc-16.2.0` | it produces the thing passes run on |
| 4, gimplify | `gimplify_function_tree` at `gcc/gimplify.cc:21974@releases/gcc-16.2.0` | a recursive walk called once per function on the way in |
| 14, assemble | `as`, a separate program | GCC writes text and stops |

Stages 3 and 4 write dump files anyway. `-fdump-tree-original` and `-fdump-tree-gimple` exist, they are written by the front end and by the gimplifier, and they are the reason a reader can believe the two stages are passes. They are registered through the dump manager directly rather than through `register_one_dump_file`, and no pass owns them.

### 3.8 The fourteen stages, with anchors

| Stage | A pass? | Anchor | What the compiler holds afterwards |
|---|---|---|---|
| 1, the driver | no | `gcc/gcc.cc` | a command line for `cc1` |
| 2, preprocess | no | libcpp | a token stream with line markers |
| 3, parse | no | `c_parse_file` | a GENERIC tree per function |
| 4, gimplify | no | `gimplify_function_tree` | a GIMPLE sequence, three address form |
| 5, build the CFG | yes | `pass_build_cfg`, `build_gimple_cfg` at `gcc/tree-cfg.cc:182@releases/gcc-16.2.0` | basic blocks and edges |
| 6, into SSA | yes | `pass_build_ssa` at `gcc/passes.def:59@releases/gcc-16.2.0` | one definition per name, phi nodes at the joins |
| 7, early optimizers | yes | `pass_early_optimizations`, a GIMPLE sub-list under an IPA pass | the same, cleaned up |
| 8, interprocedural | yes | `all_regular_ipa_passes`, `ipa_inline` at `gcc/ipa-inline.cc:2822@releases/gcc-16.2.0` | decisions recorded, bodies mostly unchanged |
| 9, tree optimizers | yes | `all_passes` up to `pass_expand` | optimized GIMPLE |
| 10, expand | yes | `pass_expand` at `gcc/passes.def:460@releases/gcc-16.2.0` | an insn chain, pseudo registers, the same CFG |
| 11, RTL optimizers | yes | `combine_instructions` at `gcc/combine.cc:1123@releases/gcc-16.2.0` and the rest | fewer, better insns |
| 12, register allocation | yes | `ira` at `gcc/ira.cc:5663@releases/gcc-16.2.0`, `lra` at `gcc/lra.cc:2420@releases/gcc-16.2.0` | hard registers, no pseudos left |
| 13, final | yes | `rest_of_handle_final` at `gcc/final.cc:4259@releases/gcc-16.2.0` | assembly text |
| 14, assemble | no | `as` | an object file |

Stage 7 is a group rather than a single pass, and stages 9, 11 and 12 are ranges. The anchors are the passes a reader can dump to see the boundary, not the whole of the stage.

## 4. Invariants

**I1.** A pass runs only if its gate returns true, and a pass's sub-list runs only if the pass itself ran.
Established by: `execute_pass_list_1` at `gcc/passes.cc:2760@releases/gcc-16.2.0`. Checked by: nothing, it is structural. May be broken by: `-fenable` and `-fdisable`, which change the gate rather than this rule.

**I2.** On entry to a pass, every property in `properties_required` holds.
Established by: whichever earlier pass provided each one. Checked by: `verify_curr_properties` at `gcc/passes.cc:2197@releases/gcc-16.2.0`, under `flag_checking` only. May be broken by: a pass that destroys a property without declaring it, which is a bug and will be caught at the next requirer under checking and nowhere without it.

**I3.** After a pass, `curr_properties` is `(curr_properties or properties_provided) and not properties_destroyed`.
Established by: `update_properties_after_pass`, called from `execute_one_pass` at `gcc/passes.cc:2697@releases/gcc-16.2.0`. Checked by: nothing directly, and I2 depends on it being right.

**I4.** The IR is verified after every pass.
Established by: `execute_one_pass` adding `TODO_verify_il` to the finish set unconditionally, at `gcc/passes.cc:2702@releases/gcc-16.2.0`. Checked by: the `verify_*` functions the TODO dispatches to, under `flag_checking`. May be broken by: nobody. A pass that declares or returns `TODO_verify_il` trips an assertion.

**I5.** An IPA pass runs with `cfun` and `current_function_decl` both nothing, and a GIMPLE or RTL pass runs with both set.
Established by: the callers. Checked by: two `gcc_assert` calls at the top of `execute_one_pass`, unconditionally, not only under checking.

**I6.** No RTL pass sees a body with `PROP_gimple` set.
Established by: `pass_expand` clearing it. Checked by: `gcc_assert` at `gcc/passes.cc:2739@releases/gcc-16.2.0`, after every pass.

**I7.** Dominance information does not survive a pass list.
Established by: `execute_pass_list` freeing both dominance kinds after the walk. Checked by: nothing. A pass that assumes dominators were computed by an earlier pass in a different list is relying on nothing.

**I8.** Every pass whose name does not begin with `*` has a distinct dump flag name.
Established by: `register_one_dump_file` appending the instance number. Checked by: `dump_register`, which rejects a duplicate. May be broken by: nobody, the numbering is derived rather than written.

**I9.** A function reaching stage 14 has no pseudo registers, every insn is recognised, and every operand satisfies its constraints.
Established by: LRA. Checked by: nothing at the boundary. An insn that fails any of the three reaches `get_insn_template` and aborts, which is a crash rather than a diagnostic.

## 5. Observable behaviour

Everything in this section is visible without reading GCC's source, and every claim cross-references a corpus entry.

### 5.1 The pass list

`-fdump-passes` prints every pass in the five lists, with its nesting and whether it is enabled at the current optimization level. It prints the passes and stops, so it needs a source file and produces no object.

For `corpora/programs/l2.c` at `-O2` with GCC 16.2.0, recorded as `t10-whole`: 395 passes in the list, 281 of them enabled.

The output has one line per pass, indented by nesting depth, with the dump flag name. It does not say which passes will change anything, because it has not run them.

### 5.2 The dump files

`-fdump-tree-all`, `-fdump-rtl-all` and `-fdump-ipa-all` write one file per pass that registered a dump. The file name is the source name, a numeric sequence, and the `dot_name` from section 2.8.

The relationship between the pass list and the dumps is not one to one in either direction. A pass whose name begins with `*` registers nothing. A pass that is gated off writes no file. Two dumps, `tree-original` and `tree-gimple`, belong to no pass.

For `t10-whole`, 137 of the tree dumps hold a body for the function under study, against 281 enabled passes. The gap is passes with no dump, which is the majority.

### 5.3 What the passes did

Comparing consecutive dumps of one function gives, for each pass with a dump on both sides, whether that pass changed the IR. For `nearest` in `t10-whole` at `-O2`: 36 passes changed the function, 98 ran and left it byte for byte as they found it, and 147 have no dump on one side or the other and support no statement either way.

The third category is a fact about the instrumentation rather than about the compiler, and a tool that reports two categories is reporting something false.

### 5.4 Timing

`-ftime-report` prints one line per timevar. A pass with `tv_id == TV_NONE` is charged to whatever timer is on the stack, so the report is a partition of the compilation by timevar and not by pass.

### 5.5 Optimization records

`-fopt-info-<group>` prints what passes decided, filtered by the `optinfo_flags` of section 2.1. A pass that sets no group is assigned `OPTGROUP_OTHER` by `register_one_dump_file`, so `-fopt-info-optall` reaches every pass and a narrower group does not.

### 5.6 Complexity that is visible from outside

The pass manager itself is linear in the number of passes. The compilation is not, and the passes that make it not are not in this document. What is in this document and visible: under `flag_checking`, `TODO_verify_il` runs after every one of the 281 enabled passes, and the verification is linear in the function, so a checking build is a constant factor slower in a way that scales with the pass count rather than with the work done.

## 6. Edge cases and error paths

**An empty translation unit.** Every list still runs. The IPA lists run once over an empty symbol table, the per function lists run zero times.

**A function with an empty body.** Gimplification produces an empty sequence, `build_gimple_cfg` produces the two blocks every CFG has, and every pass runs and finds nothing.

**A pass that discards the function.** Returning `TODO_discard_function` from `execute` frees the dominance information, pops `cfun`, and calls `cgraph_node::release_body`. `execute_one_pass` returns true, and the next iteration of `execute_pass_list_1` sees `cfun == nothing` and returns. Any sub-list of the discarding pass does not run.

**An assume function.** The same path, but with `cfun->assume_function` set, the body is kept and `PROP_assumptions_done` is set instead of the body being released, at `gcc/passes.cc:2675@releases/gcc-16.2.0`.

**A pass listed twice.** It must implement `clone`, and the default implementation prints an error and aborts. The two instances get different `static_pass_number` values and therefore different dump files. `set_pass_param` is how the second instance is told it is the second.

**`-fenable` naming a pass that does not exist.** Diagnosed at option processing, in `enable_disable_pass` at `gcc/passes.cc:1066@releases/gcc-16.2.0`.

**`-fenable` on a pass whose preconditions do not hold.** Not diagnosed. The pass runs, `verify_curr_properties` fails under a checking build, and under a release build the behaviour is whatever the pass does with IR it was not written for.

**`__GIMPLE` and `__RTL` functions.** These start the pipeline part way through, by setting `cfun->pass_startwith`. `should_skip_pass_p` at `gcc/passes.cc:2478@releases/gcc-16.2.0` then returns true for every pass until the named one, with five exceptions that run anyway: any pass that destroys `PROP_ssa`, which catches `expand`; any GIMPLE pass that provides a property; anything whose name contains `build_cgraph_edges`, `isel`, `dfinit` or `dfinish`. `skip_pass` at `gcc/passes.cc:2545@releases/gcc-16.2.0` then does by hand the side effects four RTL passes have that later passes depend on, setting `reload_completed`, setting `epilogue_completed`, allocating `INSN_ADDRESSES`, and switching the CFG hooks for `into_cfglayout` and `outof_cfglayout`.

**A plugin inserting a pass.** `register_pass` at `gcc/passes.cc:1480@releases/gcc-16.2.0` takes a reference pass name, an instance number and one of four positions. Inserting renumbers nothing, so a plugin pass gets a `static_pass_number` past the end and a dump file name derived the same way as any other.

**Allocation failure.** Not modelled. GCC's allocator does not return failure.

## 7. Interactions

**The symbol table.** The pass manager does not decide what to compile. `symbol_table::compile` at `gcc/cgraphunit.cc:2343@releases/gcc-16.2.0` decides, and calls the pass lists. Every IPA pass reads the symbol table, and `process_new_functions` is called after every one because they can add to it.

**The call graph order.** `do_per_function_toporder` at `gcc/passes.cc:1748@releases/gcc-16.2.0` is what makes the per function lists run callees before callers. This order is observable, because a pass that reads a callee's summary gets a different answer depending on whether the callee has been compiled.

**Globals the pass manager owns.** `current_pass`, set and cleared around each pass. `cfun` and `current_function_decl`, pushed and popped by the callers. `in_gimple_form`, set from the property word. `reload_completed` and `epilogue_completed`, set by two RTL passes and by `skip_pass`. Section 3 passes all of these as arguments, and none of them is an argument in GCC.

**The garbage collector.** The pass manager offers a collection point after every pass unless `TODO_do_not_ggc_collect` is set, and after a discarded function. Nothing else in the pass manager knows about memory.

**Plugins.** Five callback points: `PLUGIN_OVERRIDE_GATE` and `PLUGIN_PASS_EXECUTION` inside `execute_one_pass`, `PLUGIN_EARLY_GIMPLE_PASSES_START` and `PLUGIN_EARLY_GIMPLE_PASSES_END` around the GIMPLE sub-list of an IPA pass, and `PLUGIN_PASS_MANAGER_SETUP` at construction.

**The dump manager.** `gcc::dump_manager` owns the ids, and `register_one_dump_file` is the only caller that registers a pass dump. The two front end dumps are registered elsewhere and are the reason section 3.7 exists.

**Timevars.** One per pass at most, pushed and popped around everything including the TODOs. A pass with `TV_NONE` is charged to its caller.

**LTO.** Changes when the three IPA lists run relative to the reading and writing of object files, and adds the four serialization hooks of section 2.4 to the sequence. It does not change the contents of any list.

## 8. Conformance

**Golden corpus entries.** `t10-whole` is `corpora/programs/l2.c` at `-O2` with GCC 16.2.0 for aarch64, holding the pass list, every tree dump, five RTL dumps and the annotated assembly. `t10-ladder` is the same program with `-g` and the location carrying dumps. `l1-O2` is the four line program with the same shape of recording, and is the smaller case every claim in section 5 also holds for with different numbers.

**Invariants as assertions.** I5 and I6 are `gcc_assert` in the source and hold in every build. I2 and I4 hold only under `flag_checking`, so an implementation claiming conformance must state which. I1, I3, I7 and I8 are structural and an implementation either has the structure or does not.

**DejaGnu tests.** `gcc/testsuite/gcc.dg/plugin/` exercises pass registration through the four insert positions. `gcc/testsuite/gcc.dg/rtl/` exercises the `__RTL` start-part-way-through path, and every test in it depends on `should_skip_pass_p` and `skip_pass` behaving as section 6 states. `gcc/testsuite/gcc.dg/tree-ssa/` is where a pass proves it did something, by matching its own dump, and each of those tests is an assertion that a named pass writes a named dump.

**The falsifiable claims in section 5.** Each number there is derived from a recording rather than written down, so re-recording against a different compiler and getting a different number is a change in GCC and not a failure of this document. The claim that is invariant across compilers is the shape: most enabled passes have no dump, and most passes with a dump change nothing.

## 9. Port notes

**Forced by the language, not by GCC.** Parsing before gimplification, and a CFG before dataflow. Nothing else in the order is forced by anything except the properties, and the property system is a mechanism for stating an order rather than a reason for one.

**Forced by the properties.** SSA construction before any pass that requires `PROP_ssa`. Out of SSA before RTL, because no RTL pass models phi nodes. Register allocation after every pass that creates pseudos. Everything else in `passes.def` is a choice somebody made and defended with numbers.

**Arbitrary, and an obvious place for a reimplementation to differ.** The order of the tree optimizers. GCC runs 281 passes at `-O2` in one fixed order, and it is one fixed order because a pass manager that searched for an order would be a research project. There is no claim anywhere in GCC that this order is optimal, and the several passes that appear two and three times are the visible evidence that it is not a partial order anybody derived.

**Arbitrary, and worth copying anyway.** The three way distinction between a pass that changed the IR, a pass that did not, and a pass that provides no evidence. GCC does not model this at all, and a reimplementation that does gets an observability property GCC lacks, at the cost of a dump per pass.

**A choice GCC made that costs it.** Properties are a bitmask with a fixed width and no per pass verification of what a pass actually did, only of what it declared. A pass that destroys `PROP_cfg` without saying so is caught at the next requirer, which can be many passes later, and the diagnostic names the wrong pass. A reimplementation that recorded which pass last wrote each property would pay one word per property and get the right name in the message.

**Target dependence.** The header says no, and that is a claim about this document rather than about the compiler. The pass manager, the property system, the TODO system and the five lists are the same on every target. What differs is which passes are in `all_passes` after `pass_expand`, because a target adds machine specific passes through `TARGET_MACHINE_DEPENDENT_REORG` and through `targetm.compute_frame_layout` and friends, and the count of 281 in section 5 is therefore an aarch64 number. The stages of section 3.8 are not.

**What a reimplementation has to decide for itself.** Whether the gate is a virtual function or data. GCC makes it a virtual function, which means a gate can be arbitrarily expensive and can read global state, and several do. Whether dump registration is derived from the pass or written down. GCC derives it, and section 2.8 is the whole of the derivation, which is why the names are predictable. Whether to have four pass types or one with a flag. GCC has four, and the assertions of I5 are the cost of that choice being real rather than advisory.
