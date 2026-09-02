"""Pull the machine description patterns T09 reads out of the GCC tree.

The assembly recordings for T09 come from `just corpus-t09`, because they are ordinary
compilations. This is the other half, and it needs a script because it does not compile
anything. It reads `gcc/config/aarch64/aarch64.md` out of the pinned GCC checkout, resolves
the iterators, and writes what it found to `corpora/mdesc/aarch64.json`.

The reason it has to be committed rather than read at notebook time is Colab. A reader
opening T09 in a browser has the repository and no GCC tree, and the tree is 1.3 GB, so the
lesson cannot ask for it. Every extract carries the file, the line and the tag it came from,
so the citation in the notebook is checkable even by a reader who never clones GCC.

Which patterns get extracted is not a guess. The script reads the three assembly recordings,
collects every pattern name `-dp` printed in them, and extracts exactly those. Re-record the
corpus against a different target and this picks up whatever the new listings name.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import asm, corpus_store, mdesc  # noqa: E402

#: The recordings whose annotations decide what is worth extracting.
ENTRIES = ["t09-final", "t09-sections", "t09-local"]

#: Where the pinned GCC checkout is, and the description to start from. Includes are
#: followed from there, which is how the mode iterators in `iterators.md` get read. The
#: path is relative to the root of the checkout rather than to `gcc/`, so that what comes
#: out is already in the shape the rest of the book writes citations in.
TREE = ROOT / "vendor" / "gcc"
START = "gcc/config/aarch64/aarch64.md"

#: The tag the submodule is pinned to. Written into the extract so a stale one is obvious.
TAG = "releases/gcc-16.2.0"


def wanted() -> list[str]:
    """Every pattern named by a `-dp` annotation in the corpus, in first use order."""
    names: list[str] = []
    for entry in ENTRIES:
        for name in asm.parse(corpus_store.load(entry).asm, entry).patterns():
            if name not in names:
                names.append(name)
    return names


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    tree = Path(argv[0]) if argv else TREE
    if not (tree / START).exists():
        print(f"no machine description at {tree / START}")
        print("run `git submodule update --init vendor/gcc` first")
        return 2

    names = wanted()
    machine = mdesc.load(tree, START)
    print(f"{machine}")

    found = mdesc.extract(machine, names, TAG)
    missing = [n for n in names if n not in found["patterns"]]
    for name in missing:
        print(f"  not found: {name}")

    out = mdesc.EXTRACTS / "aarch64.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(found, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(found['patterns'])} of {len(names)} pattern(s)")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
