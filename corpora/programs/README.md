# The canonical programs

Three programs, used by every lesson in the book. Fixed in M1 and not changed after that, because half the value of a running example is that the reader already knows it by lesson forty.

| File | What it is for |
|---|---|
| `l0.c` | The smallest program that still has something to optimize. Constant folding, and the fact that GCC emits 153 dump files for four lines of C. |
| `l1.c` | A loop with an induction variable and an accumulator. The SSA lessons, the loop lessons and the pass tape all run on this. |
| `l2.c` | Pointers, a struct and a static function worth inlining. Alias analysis, inlining and the interprocedural passes. |

They are formatted in GNU style, the same style GCC's own source uses, so that a reader moving between a lesson program and GCC's source is not also switching brace conventions.
