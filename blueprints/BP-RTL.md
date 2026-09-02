# BP-RTL, the RTL expression representation

**Status:** stub
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** yes
**Generated sections:** none
**Last verified:** 2026-09-02 against `releases/gcc-16.2.0`

This is a stub. It holds what T07 needed and no more, which is the shape of an RTX, the shape of an insn chain, the machine modes, and the register numbering. The algorithms in section 3 are the ones a reader of an `.expand` dump needs in order to know where the text came from, not the ones an implementer of an expander needs, and everything about pattern matching, reload, register allocation and the machine description belongs to blueprints that are not written yet. Section 2 will be generated from `gcc/rtl.def` and `gcc/machmode.def` when the generator exists, which is why the header says no generated sections rather than pretending otherwise.

## 1. Purpose and scope

RTL is the representation the back end optimises and the machine description matches against. GIMPLE ends at expansion, RTL begins there, and everything from that point to the assembly file is written against RTL.

An RTL expression, an RTX, is a node with a code, a machine mode, and a fixed number of operands. The code says what the node is, the mode says how wide the value is, and the operands are other RTXes, integers, strings, or register numbers depending on the code. It is a tree, and the reason it does not look like one is that GCC prints it as an s-expression on as few lines as it can.

**What this document covers.** The node structure, the machine modes, the register numbering, the insn chain, and the format strings that define what an operand slot holds.

**What it does not cover.** Expansion, which is `BP-EXPAND`. The machine description and how a pattern comes to match an insn, which is `BP-MD` and `BP-RECOG`. Register allocation, which is `BP-REGALLOC`. The RTL passes, each of which gets its own. RTL is the noun here and everything that acts on it is elsewhere.

**Position in the pipeline.** RTL exists from `pass_expand` at `gcc/cfgexpand.cc:6999@releases/gcc-16.2.0` to the end of compilation. A function in RTL form has `PROP_rtl` and no longer has `PROP_gimple`, and the pass that makes the change is the only one in the compiler that consumes one and provides the other.

**Inputs and outputs as properties.** RTL is data rather than a pass, so it provides and destroys nothing. The properties belong to the passes.

## 2. Data structures

### 2.1 The node

An RTX is a `struct rtx_def`. The fields that matter to a reader of a dump are the code, the mode, the flag bits, and the operand array.

| Field | What it holds |
|---|---|
| `code` | one of the RTX codes, 16 bits |
| `mode` | one of the machine modes, 8 bits |
| `in_struct`, `volatil`, `unchanging`, `frame_related`, `jump`, `call`, `used`, `return_val` | single bits whose meaning depends on the code |
| `u` | the operand array, whose length and contents come from the format string |

The flag bits are the reason the same slash letter means different things on different codes. `REG_USERVAR_P` at `gcc/rtl.h:1972@releases/gcc-16.2.0` is the `volatil` bit read on a `REG`, and it prints as `/v`. `REG_FUNCTION_VALUE_P` at `gcc/rtl.h:1968@releases/gcc-16.2.0` is the `return_val` bit read on a `REG`, and it prints as `/i`. On a `MEM` those same two bits are `MEM_VOLATILE_P` and something else again. A blueprint that says "/v means a user variable" without saying "on a register" is wrong.

### 2.2 The codes

`gcc/rtl.def` defines **204 codes**, of which the first is `UNKNOWN`, a sentinel, leaving **203 real ones**. Each is one `DEF_RTL_EXPR` line giving the enumerator, the name the printer uses, a format string, and a class.

The format string is the definition of the node's shape. One character per operand slot: `e` an expression, `u` an insn pointer, `i` an integer, `w` a wide integer, `s` a string, `E` a vector of expressions, `B` a basic block, `L` a location, `0` a slot the code uses for something of its own. `INSN` is `"uuBeLie"` at `gcc/rtl.def:145@releases/gcc-16.2.0`, which is previous insn, next insn, basic block, pattern, location, insn code, notes. `JUMP_INSN` is the same with a jump label appended at `gcc/rtl.def:149@releases/gcc-16.2.0`, and `CALL_INSN` is the same with a call argument list appended at `gcc/rtl.def:156@releases/gcc-16.2.0`.

### 2.3 Machine modes

A mode says how wide a value is and what kind of value it is. `gcc/machmode.def` defines the machine independent ones and each target adds its own. The integer modes are a size scale around a four byte word: `QI` is one byte, `HI` two, `SI` four, `DI` eight, `TI` sixteen. `SF` and `DF` are the float modes of the same widths. `VOID` is what a node that is not a value has, and `BLK` is a block of memory of no particular shape.

The condition code modes are the ones that vary most across targets, and section 9 has the table.

### 2.4 Registers

A `REG` holds a register number and nothing else. Numbers below `FIRST_PSEUDO_REGISTER` are hard registers, which are the machine's own and are defined by the target. Numbers at or above it are pseudo registers, which the expander invents freely on the assumption that there are as many as it wants.

Immediately above `FIRST_PSEUDO_REGISTER` sit six virtual registers, `FIRST_VIRTUAL_REGISTER` at `gcc/rtl.h:4091@releases/gcc-16.2.0` through `LAST_VIRTUAL_REGISTER` at `gcc/rtl.h:4146@releases/gcc-16.2.0`, which stand for addresses that are not known until the frame layout is fixed. So the first pseudo a function can be given is `FIRST_PSEUDO_REGISTER + 6`, and that number is different on every target.

### 2.5 The insn chain

A function's RTL is a doubly linked list of insns. An entry is one of `INSN`, `JUMP_INSN`, `CALL_INSN`, `DEBUG_INSN`, `NOTE`, `CODE_LABEL` or `BARRIER`. Only the first three become instructions. `DEBUG_INSN` exists to tell the debugger where a variable is living and compiles to nothing, and the last three are markers.

Every entry has a uid. Uids are unique and are never reused, and they are not contiguous, because passes delete insns and nothing renumbers.

## 3. Algorithms

### 3.1 Printing an RTX

The dump text is produced by walking the format string, so the order of operands in the dump is the order of operands in the struct. `rtx_writer::print_rtx_operand` at `gcc/print-rtl.cc:661@releases/gcc-16.2.0` reads `GET_RTX_FORMAT` and switches on the character.

```text
print(rtx x):
    emit "(" + name(code(x)) + flags(x) + (":" + mode(x) if mode(x) != VOID)
    fmt <- GET_RTX_FORMAT(code(x))
    for i in 0 .. len(fmt) - 1:
        case fmt[i]:
            'e': print(operand(x, i))
            'E': emit "["; for each element: print(element); emit "]"
            'i', 'n', 'w': emit the integer
            's', 'S', 'T': emit the string, quoted
            'u': emit the uid of the insn pointed at, or 0
            'B': emit "[bb " + index + "]"
            'L': emit the source location, quoted
            '0': code specific, and sometimes nothing
    emit ")"
```

Two consequences a reader has to know. A square bracket in a dump is either an `E` slot, which is a real vector of expressions and part of the tree, or a note the printer added for a human, such as the variable name after a register number, and nothing in the syntax distinguishes them. And an insn's tail is positional even though it does not look it: the location, the insn code and the notes are slots four, five and six of `"uuBeLie"`, not free text.

*To be written: `print_rtx` itself, compact mode, and the `-fdump-rtl-*-slim` variants.*

### 3.2 Reading a dump back

*To be written. `gxray/rtl.py` in this repository is a reader that recognises the insn tail by shape rather than by format string, because the corpus has to be readable with no GCC tree present. It is not a reimplementation of anything in GCC and this section should describe GCC's own reader, `read_rtx` in `gcc/read-rtl.cc`, which is a different thing again: it reads machine descriptions, not dumps.*

## 4. Invariants

**I1.** Every RTX operand slot holds the kind of value its format string character says it holds.
Established by: whoever built the node. Checked by: nothing at runtime, though `rtl_check_failed_type1` under `--enable-checking` catches a wrong access rather than a wrong store. May be broken by: nobody.

**I2.** Every insn in a function's chain has a unique uid, and no uid is ever reused within a function.
Established by: `make_insn_raw` and its siblings. Checked by: nothing. May be broken by: nobody.

**I3.** `PREV_INSN` and `NEXT_INSN` are mutual inverses across the whole chain.
Established by: the emit functions in `gcc/emit-rtl.cc`. Checked by: `verify_insn_chain` in `gcc/cfgrtl.cc` under `--enable-checking`. May be broken by: a pass that is mid splice, until it finishes.

**I4.** An insn's `INSN_CODE` is `-1` until `recog` matches it against the machine description, after which it is the number of the matching pattern.
Established by: `recog_memoized`. Checked by: nothing. May be broken by: any pass that changes the pattern, which is required to reset it to `-1`.

*To be written: the invariants about modes, about `SUBREG` validity, and about what may appear inside a `PARALLEL`.*

## 5. Observable behaviour

`-fdump-rtl-expand` writes the chain immediately after expansion, before any RTL pass has run. Every insn in it has `INSN_CODE` of `-1`, which is I4 seen from outside, and almost every register in it is a pseudo.

Corpus entries: `l1-O2` holds the aarch64 dump this book's early lessons read. `t07-x86-64`, `t07-aarch64`, `t07-riscv64` and `t07-power64le` hold the same source at the same flags on four targets, recorded through Compiler Explorer at GCC 16.1.0, which is the newest version that site has built for all four.

What those four show, and what section 9 tabulates: the same four lines of C become 13, 13, 16 and 17 instructions, use 3, 3, 7 and 8 pseudos, and disagree about where a condition code lives.

*To be written: the `-slim` variants, `-fdump-rtl-all`, and what `-fopt-info` says about RTL passes.*

## 6. Edge cases and error paths

*To be written.* The ones already known to matter: a function with no insns at all, which happens for an empty function after everything is deleted; a `PARALLEL` with one element, which is legal and rare; a `SUBREG` of a `SUBREG`, which is not legal and is what `simplify_subreg` exists to prevent; and an insn whose pattern is a bare `USE` or `CLOBBER`, which is not an instruction and still sits in the chain as one.

## 7. Interactions

`pass_expand` at `gcc/cfgexpand.cc:6999@releases/gcc-16.2.0` is the only producer. Everything from there on is a consumer.

Target hooks consulted while RTL is being built are the largest interaction surface in the compiler and this section will need most of a document to itself. The one T07 depends on is `TARGET_PREDICT_DOLOOP_P` at `gcc/target.def:4728@releases/gcc-16.2.0`, which is consulted by `analyze_and_mark_doloop_use` at `gcc/tree-ssa-loop-ivopts.cc:8104@releases/gcc-16.2.0`. That call is in the middle end, not the back end, and it is the reason the optimized GIMPLE for a loop is not always the same on every target.

*To be written: the rest.*

## 8. Conformance

*To be written.* The RTL specific parts of the torture suite, `gcc.dg/rtl/` which lets a test write RTL directly, and the invariants in section 4 restated as assertions.

## 9. Port notes

RTL is target dependent by design. The codes and the format strings are shared, and almost everything a dump actually contains is not.

What differs, from the four recordings in section 5:

| | x86-64 | aarch64 | riscv64 | power64le |
|---|---|---|---|---|
| instructions | 13 | 13 | 16 | 17 |
| pseudos used | 3 | 3 | 7 | 8 |
| lowest pseudo | 98 | 101 | 134 | 117 |
| condition code | `CCNO`, `CCZ`, in a fixed register | `CC`, in a fixed register | none, no flags register | `CC`, in a pseudo |
| compare and branch | two insns | two insns | one insn | two insns |
| adding clobbers something | yes | no | no | no |

The lowest pseudo number is `FIRST_PSEUDO_REGISTER + 6` on each target, which is section 2.4 seen from outside.

Three of those rows are the same fact from three angles, and it is the fact that matters most for a port. x86-64 has one flags register, so an add has to say out loud that it destroys it, which is why the add is a `PARALLEL` with a `CLOBBER` in it. RISC-V has no flags register at all, so a compare and a branch are one instruction and there is no condition code mode in the dump. PowerPC has eight condition fields, so the compare writes a pseudo in `CC` mode and the allocator decides which field later.

**What is forced and what is not.** The format strings are forced, in the sense that the printer and every pass agree on them. The register numbering is not: nothing requires that pseudos be numbered above hard registers, and an implementation that kept two separate spaces would lose nothing except the ability to write `REGNO (x) < FIRST_PSEUDO_REGISTER`, which is a great deal of GCC. Condition codes are the clearest case of a historical choice: GCC models them as a register because the machines it was first written for had one, and a target with no flags register models the absence by having its compare produce a value instead, which works but is visibly a workaround for a model that assumed otherwise.
