# BP-EXAMPLE, the subsystem this describes

**Status:** stub
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** no
**Generated sections:** none
**Last verified:** 2026-09-01 against `releases/gcc-16.2.0`

Copy this file, rename it, and fill it in. The rules are below each heading, and `bpc check` enforces the ones a script can enforce: all nine sections present, a legal status, and a header that names the pinned tag.

A blueprint is what somebody reads while they are implementing something and need to know exactly what GCC does. It has no motivation, no analogies and no narrative, and the rule that makes all the other rules work is that **a blueprint may not reference a lesson**. If an implementer needs a fact, it is in the blueprint, even if a lesson already said it. The lesson can point at the blueprint as much as it likes. The arrow only goes one way.

**Write section 6 before section 3.** Edge cases come from reading tests and bug reports, algorithms come from reading code. Doing the harder research first stops it getting skipped in the last week.

## 1. Purpose and scope

What this component is responsible for, and explicitly what it is not. Where it sits in the pipeline. Its inputs and outputs as IR properties, meaning the `PROP_*` flags it requires, provides and destroys.

The "explicitly what it is not" half is not padding. Most confusion about GCC is somebody attributing a behaviour to the wrong component, and a boundary stated in one sentence saves an afternoon.

## 2. Data structures

Every type this component owns or requires. Field by field: name, type, meaning, valid range, who is allowed to write it, GTY marking and lifetime. Layout where the layout is observable.

Where GCC describes the data in a machine readable file, this section is generated. Put the markers in and let `bpc` fill them:

```text
<!-- bpc:begin some-generator-id -->
<!-- bpc:end some-generator-id -->
```

## 3. Algorithms

The operations, in the pseudocode from `NOTATION.md`. Complete enough to implement from. Complexity stated. Iteration order stated wherever the order is observable from outside.

No prose descriptions of algorithms. The pseudocode is the algorithm. If a paragraph is explaining what the pseudocode does, either the paragraph or the pseudocode is wrong.

## 4. Invariants

Numbered, so that section 8 and the pass documentation can cite them. Each one states what must be true, at which points in the pipeline, who establishes it, who is permitted to break it and until when, and what checks it.

"What checks it" is a specific claim: a `verify_*` function, an assertion under `--enable-checking`, or nothing. An invariant that nothing checks is a landmine, and writing "nothing checks this" is one of the most useful things a blueprint can do.

**I1.** Statement of the invariant.
Established by: who. Checked by: what, or nothing. May be broken by: who, until when.

## 5. Observable behaviour

What an outside observer can see without reading GCC's source: dump text, `-fopt-info` records, diagnostics, the generated code, and complexity that is visible in timing.

Every claim here cross-references a golden corpus entry. Observable behaviour that nobody recorded is a claim rather than an observation, and the corpus is how a reader checks it on their own machine.

## 6. Edge cases and error paths

Empty input. A single element. The maximum size. Recursion and reentrancy. Allocation failure. Malformed IR. Which conditions produce an internal compiler error and what the message says. Interaction with the `-fno-*` flags that turn off things this component needs.

## 7. Interactions

Which other components this reads, writes, invalidates or depends on. Which passes must run before it and which must run after. Which target hooks it consults. Which globals it touches, named honestly, including the ones the pseudocode in section 3 passed as arguments.

## 8. Conformance

The tests that prove an implementation is correct: named DejaGnu tests with their paths, golden corpus entries, the subsets of the torture suite that exercise this, and the invariants from section 4 restated as assertions.

## 9. Port notes

What an independent implementation has to decide for itself. Where GCC's choice is forced and where it is arbitrary. What differs across targets and across build configurations.

The most valuable sentence a blueprint can contain is "GCC does X here, nothing requires X, and a reimplementation may do Y". Telling a forced choice apart from a historical one is the difference between a specification and a transcription.

If the header says this component is target dependent, the table of what differs goes here, and any target specific behaviour mentioned anywhere else in the document is marked inline where it appears. A blueprint that quietly describes x86-64 behaviour as universal is worse than no blueprint at all.
