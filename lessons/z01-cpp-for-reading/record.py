"""Cut the pieces of GCC's own source that Z01 reads, and commit them.

Every other lesson records what a compiler produced. This one records what the compiler is
made of, which needs the pinned tree in `vendor/gcc` and therefore cannot happen in Colab or
in the notebook. So it happens here, once, and the result goes in `corpora/source/z01.json`.

    python lessons/z01-cpp-for-reading/record.py

The line numbers below are the whole content of this file and they are the thing that rots.
Every one of them is also a citation in the notebook, so `refcheck` pins the same lines from
the other side and a GCC bump that moves any of them fails the build. If that happens, open
the file, find where the construct went, and change the numbers here.

The snippets were chosen so that between them they contain every construct in
`source.IDIOMS` at least once. That is checked by a test rather than by hope.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import source  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "source" / "z01.json"

#: What to cut and why. `about` is the one line the notebook prints above each snippet, so it
#: says what the reader is looking at rather than what the file is called. `cite` is the same
#: `path` and `first` written out again in the one shape `refcheck` recognizes, which is the
#: only reason it exists: refcheck reads `.md` and `.py` files looking for that shape, and
#: without a literal string here nothing would notice these eighteen spans going stale.
#: `main` checks the two spellings agree, so the repetition cannot drift.
WANTED = [
    {
        "name": "tree-union",
        "path": "gcc/tree-core.h",
        "first": 2182,
        "last": 2200,
        "cite": "gcc/tree-core.h:2182@releases/gcc-16.2.0",
        "about": "A tree is a tagged union. This is the union, and the tags are in the GTY.",
    },
    {
        "name": "tree-base",
        "path": "gcc/tree-core.h",
        "first": 1138,
        "last": 1160,
        "cite": "gcc/tree-core.h:1138@releases/gcc-16.2.0",
        "about": "The head of every tree node. One byte of tag and a lot of packed flags.",
    },
    {
        "name": "gimple-base",
        "path": "gcc/gimple.h",
        "first": 220,
        "last": 246,
        "cite": "gcc/gimple.h:220@releases/gcc-16.2.0",
        "about": "The base class every GIMPLE statement inherits from, and its bitfields.",
    },
    {
        "name": "gimple-subclass",
        "path": "gcc/gimple.h",
        "first": 896,
        "last": 905,
        "cite": "gcc/gimple.h:896@releases/gcc-16.2.0",
        "about": "A subclass with no fields at all. Its whole job is to be a different type.",
    },
    {
        "name": "is-a-helper",
        "path": "gcc/gimple.h",
        "first": 976,
        "last": 982,
        "cite": "gcc/gimple.h:976@releases/gcc-16.2.0",
        "about": "How a subclass tells is-a.h what its tag is. One of these per statement kind.",
    },
    {
        "name": "is_a",
        "path": "gcc/is-a.h",
        "first": 224,
        "last": 233,
        "cite": "gcc/is-a.h:224@releases/gcc-16.2.0",
        "about": "is_a asks, and does nothing else.",
    },
    {
        "name": "as_a",
        "path": "gcc/is-a.h",
        "first": 248,
        "last": 257,
        "cite": "gcc/is-a.h:248@releases/gcc-16.2.0",
        "about": "as_a asserts and converts, and the assert is one a release build removes.",
    },
    {
        "name": "dyn_cast",
        "path": "gcc/is-a.h",
        "first": 274,
        "last": 286,
        "cite": "gcc/is-a.h:274@releases/gcc-16.2.0",
        "about": "dyn_cast converts or returns null, which is the one of the three you can test.",
    },
    {
        "name": "for-each-bb",
        "path": "gcc/basic-block.h",
        "first": 208,
        "last": 216,
        "cite": "gcc/basic-block.h:208@releases/gcc-16.2.0",
        "about": "The loop you will read a thousand times, and the macro it is built out of.",
    },
    {
        "name": "vec-strategies",
        "path": "gcc/vec.h",
        "first": 72,
        "last": 89,
        "cite": "gcc/vec.h:72@releases/gcc-16.2.0",
        "about": "Why this is not std::vector: the allocator has to be the garbage collector.",
    },
    {
        "name": "vec-declaration",
        "path": "gcc/vec.h",
        "first": 446,
        "last": 458,
        "cite": "gcc/vec.h:446@releases/gcc-16.2.0",
        "about": "Three template parameters, an empty body, and a range for that works anyway.",
    },
    {
        "name": "hash-map",
        "path": "gcc/hash-map.h",
        "first": 35,
        "last": 45,
        "cite": "gcc/hash-map.h:35@releases/gcc-16.2.0",
        "about": "The same story as vec. GTY((user)) tells gengtype the marking is handwritten.",
    },
    {
        "name": "poly-int",
        "path": "gcc/poly-int.h",
        "first": 374,
        "last": 387,
        "cite": "gcc/poly-int.h:374@releases/gcc-16.2.0",
        "about": "A number that may not be known yet, because a vector may not have a size yet.",
    },
    {
        "name": "includes",
        "path": "gcc/tree-ssa-ccp.cc",
        "first": 121,
        "last": 132,
        "cite": "gcc/tree-ssa-ccp.cc:121@releases/gcc-16.2.0",
        "about": "The first three are mandatory, in that order. Everything after them is ordinary.",
    },
    {
        "name": "ccp-read",
        "path": "gcc/tree-ssa-ccp.cc",
        "first": 280,
        "last": 319,
        "cite": "gcc/tree-ssa-ccp.cc:280@releases/gcc-16.2.0",
        "about": "Forty lines of a real pass. The T0 exercise is to read every one of them.",
    },
    {
        "name": "ccp-walk",
        "path": "gcc/tree-ssa-ccp.cc",
        "first": 900,
        "last": 930,
        "cite": "gcc/tree-ssa-ccp.cc:900@releases/gcc-16.2.0",
        "about": "Walking a function: blocks with one macro, statements inside them with another.",
    },
    {
        "name": "ccp-dump",
        "path": "gcc/tree-ssa-ccp.cc",
        "first": 566,
        "last": 570,
        "cite": "gcc/tree-ssa-ccp.cc:566@releases/gcc-16.2.0",
        "about": "Where a line in a dump file comes from. Guarded, because dumping is usually off.",
    },
    {
        "name": "ccp-pass",
        "path": "gcc/tree-ssa-ccp.cc",
        "first": 3042,
        "last": 3060,
        "cite": "gcc/tree-ssa-ccp.cc:3042@releases/gcc-16.2.0",
        "about": "The furniture. Every pass in passes.def has a pass_data and a class like this.",
    },
]


def main() -> int:
    if not (GCC_ROOT / "gcc" / "tree-core.h").exists():
        print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
        return 1
    specs = []
    for spec in WANTED:
        spec = dict(spec)
        written = spec.pop("cite")
        expected = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if written != expected:
            print(f"{spec['name']}: cite says {written}, the span says {expected}")
            return 1
        specs.append(spec)

    cuts = source.extract(GCC_ROOT, specs, PINNED_TAG)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cuts, indent=1) + "\n", encoding="utf-8")

    got = source.load_extract("z01")
    seen = {key for snippet in got for hits in source.annotate(snippet).values() for key in hits}
    missing = [key for key in source.KEYS if key not in seen]
    print(f"wrote {OUT.relative_to(ROOT)}, {len(got)} snippets, {got.lines()} lines")
    print(f"{len(seen)} of {len(source.KEYS)} constructs appear in them")
    if missing:
        print(f"not covered: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
