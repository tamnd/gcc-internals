"""Finding, naming and ordering GCC's dump files.

GCC names a dump file after the input, the position of the pass in the pipeline, the
phase letter, and the pass name:

    l1.c.024t.ssa
    l1.c.273t.optimized
    l1.c.000i.cgraph
    l1.c.216r.expand

The number is the pass's position, the letter is the phase, and everything after the next
dot is the pass name. The number is not stable across GCC versions and nothing should ever
be looked up by it, which is why `DumpFile.key` is the phase and the name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PHASES = {"t": "tree", "r": "rtl", "i": "ipa"}

# l1.c.024t.ssa  ->  base=l1.c index=024 phase=t name=ssa
DUMP_NAME = re.compile(r"^(?P<base>.+?)\.(?P<index>\d{3})(?P<phase>[tri])\.(?P<name>.+)$")

# Every dump of a function body opens with this. It is the only reliable boundary in a
# stream of dumps sent to stderr, which is the only way the browser backend can get them.
FUNCTION_HEADER = re.compile(r"^;; Function (?P<pretty>.+?) \((?P<detail>.*)\)\s*$")


@dataclass(frozen=True)
class DumpFile:
    """One dump file on disk."""

    path: Path
    index: int
    phase: str
    name: str

    @property
    def key(self) -> str:
        """How a lesson refers to this dump. Stable across versions, unlike the index."""
        return f"{self.phase}-{self.name}"

    @property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")

    def __str__(self) -> str:
        return f"{self.index:03d}{self.phase[0]}.{self.name}"


def parse_dump_filename(path: Path | str) -> DumpFile | None:
    """Return a DumpFile, or None if this is not one of GCC's dump files."""
    path = Path(path)
    m = DUMP_NAME.match(path.name)
    if not m:
        return None
    return DumpFile(
        path=path,
        index=int(m.group("index")),
        phase=PHASES[m.group("phase")],
        name=m.group("name"),
    )


def find_dumps(directory: Path | str, base: str | None = None) -> list[DumpFile]:
    """Every dump file in a directory, in the order the passes ran.

    Sorting is by index and then by name, because several passes can share an index.
    """
    directory = Path(directory)
    found = []
    for p in sorted(directory.iterdir()):
        if not p.is_file():
            continue
        d = parse_dump_filename(p)
        if d is None:
            continue
        if base is not None and not p.name.startswith(base + "."):
            continue
        found.append(d)
    return sorted(found, key=lambda d: (d.index, d.name))


def split_stderr_dumps(stderr: str) -> list[str]:
    """Split a stream of dumps sent to `=stderr` into one chunk per function dump.

    GCC writes dumps to separate files when it can, but a browser has no files, so Tier 0
    asks for `-fdump-tree-all=stderr` and gets everything in one stream. There is no
    separator between dumps. There is a `;; Function` header at the top of every dump of a
    function body, and splitting on that recovers the chunks exactly.

    Verified on `l1.c` at `-O1` with Homebrew GCC 16.2.0: the stream contains 109
    `;; Function` headers, and the 109 dump files written by the same compilation contain
    109 between them, in the same order.

    Two caveats a caller has to know about, both of which are why this returns bare chunks
    and not a name to text mapping:

    1. Two dump files at that setting hold no function body at all, so they have no chunk
       here. Chunk N is not dump file N.
    2. Nothing in the stream says which pass produced which chunk. Pairing a chunk with a
       pass name needs a manifest recorded from a run that had filenames, which is what
       `gxray.corpus` ships.
    """
    if not stderr:
        return []
    chunks: list[str] = []
    current: list[str] | None = None
    for line in stderr.splitlines():
        if FUNCTION_HEADER.match(line):
            if current is not None:
                chunks.append("\n".join(current).rstrip() + "\n")
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        chunks.append("\n".join(current).rstrip() + "\n")
    return chunks


def dump_flags(specs: list[str] | tuple[str, ...], to_stderr: bool = False) -> list[str]:
    """Turn ["tree-ssa", "rtl-expand"] into the -fdump- flags that produce them."""
    suffix = "=stderr" if to_stderr else ""
    return [f"-fdump-{spec}{suffix}" for spec in specs]


# What a caller can ask for on top of a dump, from `gcc/dumpfile.cc`. `lineno` is the one
# this project needs, because a source location on every statement is what joins the four
# levels of the IR ladder together.
DUMP_OPTIONS = frozenset({"lineno", "blocks", "details", "slim", "raw", "vops", "uid", "all"})


def split_spec(spec: str) -> tuple[str, tuple[str, ...]]:
    """`tree-ssa-lineno` is the `tree-ssa` dump with `lineno` asked for on top of it.

    The modifier changes what GCC prints, not which dump it is, so it belongs on the flag
    and not in the key. Without this a dump asked for with `-lineno` would be filed under a
    different name from the same dump asked for without it, and a lesson would have to know
    which one the corpus happened to be recorded with.
    """
    parts = spec.split("-")
    options: list[str] = []
    while len(parts) > 2 and parts[-1] in DUMP_OPTIONS:
        options.insert(0, parts.pop())
    return "-".join(parts), tuple(options)
