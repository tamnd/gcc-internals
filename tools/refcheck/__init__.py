"""Citations that cannot rot without somebody noticing.

Every factual claim about GCC's code carries a citation:

    gcc/tree-ssa-ccp.cc:1183@releases/gcc-16.2.0

`refcheck` resolves all of them against the pinned tree in `vendor/gcc` and verifies a hash
of the cited line and the lines around it. A changed hash is a build failure and a human
has to look.

This is not bureaucracy. It buys three things:

1. The project can bump GCC versions. Without it, a version bump means rereading every
   claim in the book by hand, which means the bump never happens and the material joins
   the pile of writing that is accurate about GCC 4.4.
2. It catches the ordinary and embarrassing error of citing the line above the one you
   meant, at the moment you write it rather than in a reader's bug report.
3. It makes "I read this in the source" checkable by a stranger.

The hashes live in `citations.lock.json`, which is committed. Adding a citation means
running `refcheck update` and committing the new lines, so a citation entering the book is
visible in a diff. That is the same rule as the Compiler Explorer cache and for the same
reason.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GCC_ROOT = REPO_ROOT / "vendor" / "gcc"
LOCKFILE = REPO_ROOT / "citations.lock.json"
PINNED_TAG = "releases/gcc-16.2.0"

# gcc/tree-ssa-ccp.cc:1183@releases/gcc-16.2.0
CITATION = re.compile(
    r"(?P<path>[A-Za-z0-9_][A-Za-z0-9_./+-]*\.[A-Za-z][A-Za-z0-9+]*)"
    r":(?P<line>\d+)"
    r"@(?P<tag>[A-Za-z0-9_./-]+)"
)

# How much of the file goes into the hash: the cited line, plus this many lines either
# side. Two is a deliberate choice. A wider window fails the build for edits that have
# nothing to do with the claim, and a check that cries wolf gets switched off. A narrower
# window misses the off by one, which is the error this is mostly here to catch.
CONTEXT = 2

# Files that do not exist until GCC is built. A citation into one of these is meaningless,
# because the line numbers depend on the build, so it is rejected with an explanation
# rather than reported as a missing file.
GENERATED = {
    "gimple-match.cc": "gcc/match.pd",
    "gimple-match-exports.cc": "gcc/match.pd",
    "generic-match.cc": "gcc/match.pd",
    "insn-recog.cc": "the .md file for the target",
    "insn-emit.cc": "the .md file for the target",
    "insn-output.cc": "the .md file for the target",
    "insn-attrtab.cc": "the .md file for the target",
    "insn-opinit.cc": "the .md file for the target",
    "insn-modes.cc": "the modes.def file for the target",
    "options.cc": "the .opt file that declares the option",
    "options.h": "the .opt file that declares the option",
    "tm.h": "the target's config headers",
    "gtype-desc.cc": "the type declaration that gengtype read",
}


class RefError(RuntimeError):
    """Something wrong with a citation, phrased so the author can fix it."""


@dataclass(frozen=True)
class Citation:
    """One citation, and where in the prose it was written."""

    path: str
    line: int
    tag: str
    source: Path | None = None
    source_line: int = 0

    @property
    def key(self) -> str:
        return f"{self.path}:{self.line}@{self.tag}"

    @property
    def where(self) -> str:
        if self.source is None:
            return "somewhere"
        return f"{self.source}:{self.source_line}"

    def __str__(self) -> str:
        return self.key


@dataclass
class Resolved:
    """A citation that was found in the tree, with the text it points at."""

    citation: Citation
    text: str
    window: list[str]
    digest: str


def find_citations(text: str, source: Path | None = None) -> list[Citation]:
    """Every citation in a piece of prose."""
    found = []
    for n, line in enumerate(text.splitlines(), start=1):
        for m in CITATION.finditer(line):
            found.append(
                Citation(
                    path=m.group("path"),
                    line=int(m.group("line")),
                    tag=m.group("tag"),
                    source=source,
                    source_line=n,
                )
            )
    return found


def scan(paths: list[Path]) -> list[Citation]:
    """Every citation in a set of files and directories."""
    found: list[Citation] = []
    for p in paths:
        files = sorted(p.rglob("*.md")) + sorted(p.rglob("*.py")) if p.is_dir() else [p]
        for f in files:
            if GCC_ROOT in f.parents:
                continue
            found += find_citations(f.read_text(encoding="utf-8", errors="replace"), source=f)
    return found


def digest_of(window: list[str]) -> str:
    """A hash of the cited window. Whitespace at the end of a line is not meaningful."""
    body = "\n".join(line.rstrip() for line in window)
    return hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()[:16]


def resolve(citation: Citation, root: Path | None = None) -> Resolved:
    """Look a citation up in the pinned tree. Raises RefError with a readable reason."""
    root = root or GCC_ROOT
    name = Path(citation.path).name

    if name in GENERATED:
        raise RefError(
            f"{citation.key} at {citation.where} points into {name}, which does not exist "
            f"until GCC is built. Its line numbers are not stable and mean nothing to a "
            f"reader. Cite {GENERATED[name]} instead and name {name} in the prose."
        )

    if citation.tag != PINNED_TAG:
        raise RefError(
            f"{citation.key} at {citation.where} cites {citation.tag} but the tree is "
            f"pinned at {PINNED_TAG}. One tag per site version, so this is either a typo "
            f"or the pin needs to move first."
        )

    target = root / citation.path
    if not target.is_file():
        raise RefError(
            f"{citation.key} at {citation.where} points at a file that is not in the tree. "
            f"Looked in {target}. If the submodule is not checked out, run "
            f"`git submodule update --init --depth 1`."
        )

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    if not 1 <= citation.line <= len(lines):
        raise RefError(
            f"{citation.key} at {citation.where} points at line {citation.line}, but "
            f"{citation.path} has {len(lines)} lines."
        )

    lo = max(0, citation.line - 1 - CONTEXT)
    hi = min(len(lines), citation.line + CONTEXT)
    window = lines[lo:hi]
    return Resolved(
        citation=citation,
        text=lines[citation.line - 1],
        window=window,
        digest=digest_of(window),
    )


def load_lock(path: Path | None = None) -> dict[str, dict]:
    path = path or LOCKFILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("citations", {})


def save_lock(entries: dict[str, dict], path: Path | None = None) -> Path:
    path = path or LOCKFILE
    body = {
        "comment": (
            "Generated by `refcheck update`. Each entry is a hash of the cited line and "
            "two lines either side, in the pinned GCC tree. A changed hash means the code "
            "moved and a human has to reread the claim."
        ),
        "pinned": PINNED_TAG,
        "context_lines": CONTEXT,
        "citations": dict(sorted(entries.items())),
    }
    path.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    return path


def pinned_commit(root: Path | None = None) -> str | None:
    """The commit the submodule is actually checked out at, or None if it is not there."""
    root = root or GCC_ROOT
    if not (root / "gcc").is_dir():
        return None
    out = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip() or None


def check(paths: list[Path], root: Path | None = None, lock: Path | None = None) -> list[str]:
    """Resolve every citation and compare it with the lockfile. Returns the problems."""
    problems: list[str] = []
    recorded = load_lock(lock)
    seen: set[str] = set()

    for citation in scan(paths):
        seen.add(citation.key)
        try:
            found = resolve(citation, root=root)
        except RefError as exc:
            problems.append(str(exc))
            continue

        was = recorded.get(citation.key)
        if was is None:
            problems.append(
                f"{citation.key} at {citation.where} is not in the lockfile. "
                f"Run `refcheck update` and commit the result, so a new citation shows up "
                f"in the diff."
            )
        elif was["hash"] != found.digest:
            problems.append(
                f"{citation.key} at {citation.where} no longer matches what was recorded.\n"
                f"    recorded: {was['text'].strip()}\n"
                f"    now:      {found.text.strip()}\n"
                f"    The code moved. Reread the claim, then run `refcheck update`."
            )

    for stale in sorted(set(recorded) - seen):
        problems.append(f"{stale} is in the lockfile but no longer cited. Run `refcheck update`.")

    return problems


def update(paths: list[Path], root: Path | None = None, lock: Path | None = None) -> dict:
    """Rebuild the lockfile from the prose. Raises on a citation that cannot be resolved."""
    entries: dict[str, dict] = {}
    for citation in scan(paths):
        found = resolve(citation, root=root)
        entries[citation.key] = {"hash": found.digest, "text": found.text.rstrip()}
    save_lock(entries, path=lock)
    return entries
