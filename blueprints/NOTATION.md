# NOTATION

Every algorithm in every blueprint is written in the same pseudocode. Not C, not C++, not Python, because each of those imports assumptions that are not part of the algorithm. C++ makes you decide about references and ownership before you have said what the algorithm does. Python makes everything a hash table. The dialect here has exactly enough in it to write down what GCC does and nothing spare.

The rule that matters: an implementer reading thirty blueprints reads one dialect thirty times, instead of thirty renderings of somebody's C++. If you find yourself wanting a feature that is not here, the usual answer is that the algorithm is being described at the wrong level.

## Values

Six kinds of value, and nothing else.

```text
integers        0, 1, -3, 2^32
booleans        true, false
symbols         GIMPLE_ASSIGN, VAR_DECL, red
sequences       [a, b, c]        ordered, duplicates allowed
sets            {a, b, c}        unordered, no duplicates
maps            {a: 1, b: 2}     keys to values
records         a named group of named fields
```

There is one more, and it exists because leaving it out is how specifications lie:

```text
nothing         the absence of a value
```

`nothing` is not zero, not the empty sequence and not `false`. GCC spells it `NULL` most of the time and `error_mark_node` some of the time, and where it matters which, the blueprint says so.

## Records

A record is a named group of named fields. This is how a blueprint's section 2 gets used by its section 3.

```text
record Statement
    code       symbol
    operands   sequence of Tree
    location   Location or nothing
```

Field access is a dot. There are no methods, no inheritance and no constructors. A record is data.

```text
s.code
s.operands[0]
```

Writing a field is an assignment, and the reader may take it that anything not assigned is unchanged.

## Assignment and comparison

```text
x = 3                 bind x to 3
s.code = GIMPLE_NOP   write a field
x == y                equal
x != y                not equal
x in S                membership, for sets, sequences and map keys
```

One equals sign binds and two compare, which is the C convention rather than the mathematical one, because most readers of these documents are reading C on the other screen.

## Control

Indentation is structure. There are no braces and no `end` keyword.

```text
if condition
    ...
else if condition
    ...
else
    ...

for each x in S
    ...

while condition
    ...

repeat
    ...
until condition
```

`for each` over a set is unordered, and an algorithm that depends on the order of a set is a bug in the algorithm or a lie in the specification. Where GCC iterates in an order that an outside observer can see, the blueprint says which order and why, because that order is then part of the contract.

```text
for each bb in cfg.blocks in reverse postorder
```

## Functions

```text
function name (arg: Type, arg: Type) -> Type
    ...
    return value
```

A function that can fail says so in its return type and returns the reason, rather than setting a flag somewhere.

```text
function lookup (m: Map, k: Key) -> Value or nothing

function verify (s: Statement) -> ok or error(message)
```

There are no exceptions, no output parameters and no global state. Where GCC uses a global, which it does constantly, the blueprint names it as an explicit argument and section 7 records that it is in fact a global. That is a deliberate friction. A specification that hides the globals is a specification you cannot reimplement from.

## Operations on collections

```text
length(S)              how many
append(S, x)           add to the end of a sequence
S[i]                   index a sequence, from 0
S[i..j]                a slice, i included, j excluded
add(S, x)              add to a set
remove(S, x)           take out of a set
union(A, B)            set union
S = {}                 the empty set
S = []                 the empty sequence
```

Bit sets get their own spelling, because GCC's bitmaps are everywhere in the middle end and their cost model is not the cost model of a hash set.

```text
bitset B over Domain
set(B, i)
clear(B, i)
test(B, i)
```

## Complexity

Every algorithm in a section 3 states its complexity on the line after its signature, in the variables it is written in.

```text
function dominance (cfg: CFG) -> Map
    complexity: O(n * a(n)) in the number of blocks
```

If the complexity in practice differs from the complexity on paper, which for several things in GCC it very much does, say both.

## What is deliberately missing

No pointers, unless the algorithm is about pointers. GCC's IR is a graph of pointers and the pseudocode still says `s.operands[0]`, because whether that is a pointer is a representation question and section 2 already answered it.

No memory management, unless the algorithm is about memory management. `BP-GGC` is about memory management, so `BP-GGC` has allocation in its pseudocode and nothing else does.

No types beyond the six kinds above. A blueprint that needs a type lattice defines the lattice as records in its own section 2.

No inheritance. GCC's C++ statement classes are a narrowing of one representation and section 2 of `BP-GIMPLE` gives the full map, so the pseudocode can say `if s.code == GIMPLE_ASSIGN` and be done.

## A worked example

This is the constant propagation meet operator, written the way a blueprint would write it. The point is that you could implement it in any language from this, and that nothing in it depends on knowing GCC.

```text
record Lattice
    kind   one of {undefined, constant, varying}
    value  integer or nothing
    mask   integer or nothing

function meet (a: Lattice, b: Lattice) -> Lattice
    complexity: O(1)

    if a.kind == undefined
        return b
    if b.kind == undefined
        return a
    if a.kind == varying or b.kind == varying
        return Lattice(varying, nothing, nothing)
    if a.value == b.value
        return a
    return Lattice(varying, nothing, nothing)
```

`undefined` is the top of the lattice and `varying` is the bottom, and meeting anything with the top gives back the other side. That is the whole reason the first two lines are there, and it is the sort of thing a blueprint states in section 4 as an invariant rather than leaving the reader to infer from the code.
