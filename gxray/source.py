"""Cuttings of GCC's own source, committed so a notebook can read them without the tree.

Every other reader in `gxray` parses something a compiler produced. This one reads the
compiler, which is a different problem and needs a different answer, because the tree is
1.3 GB and a notebook in Colab has none of it.

So the lessons that quote GCC's source quote a committed extract instead. A recorder runs
against `vendor/gcc` at the pinned tag, cuts out the lines a lesson names, and writes them
to `corpora/source/`. The extract carries the path, the line numbers and the tag with every
snippet, so a reader can go and check, and `refcheck` pins the same lines from the other
side. If somebody edits a snippet in the JSON to make a lesson read better, refcheck fails.

    from gxray import source
    cuts = source.load_extract("z01")
    print(cuts.snippet("as_a").text)

The other half of this module is `idioms`, which recognizes the constructs a first time
reader of GCC trips over. It works on the text of a line rather than on a list of answers,
so a lesson that asks what a line does is asking about the line rather than about a key
somebody typed. A construct GCC stops using stops being recognized, which is correct.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: Where the recorders put what they cut, and where a notebook looks for it.
EXTRACTS = Path(__file__).resolve().parent.parent / "corpora" / "source"


@dataclass(frozen=True)
class Snippet:
    """A run of lines from one GCC source file, with where it came from attached."""

    name: str
    path: str
    first: int
    last: int
    lines: tuple[str, ...]
    tag: str
    about: str = ""

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def citation(self) -> str:
        """The citation for the first line, in the form the prose checker expects."""
        return f"{self.path}:{self.first}@{self.tag}"

    def at(self, line: int) -> str:
        """One line by its number in the file, not by its index in the snippet."""
        if not self.first <= line <= self.last:
            raise KeyError(f"{self.path}:{line} is not in {self.name}, which is {self.span}")
        return self.lines[line - self.first]

    @property
    def span(self) -> str:
        return f"{self.path}:{self.first}-{self.last}"

    def numbered(self, mark: dict[int, str] | None = None, tab: int = 8) -> str:
        """The snippet with real file line numbers down the side, and optional margin notes.

        The line numbers have to be the file's own. A reader who counts from one and then
        opens the file on GitHub finds a different line, and the whole point of committing
        the extract was that they could go and look.

        Tabs are expanded here and nowhere else. GCC indents with real tabs at eight columns,
        the stored lines keep them so the hash matches the file, and a notebook that printed
        them raw would show the reader something with the indentation shredded.
        """
        notes = mark or {}
        width = max(len(str(self.last)), 4)
        out = []
        for n, text in enumerate(self.lines, start=self.first):
            note = notes.get(n, "")
            body = f"{n:>{width}}  {text.expandtabs(tab)}".rstrip()
            out.append(body + (f"    <-- {note}" if note else ""))
        return "\n".join(out)

    def __len__(self) -> int:
        return len(self.lines)

    def __str__(self) -> str:
        return f"{self.name} ({self.span}, {len(self)} lines)"


@dataclass(frozen=True)
class Extract:
    """Every snippet one lesson asked for, read back from the committed JSON."""

    tag: str
    snippets: dict[str, Snippet]

    def snippet(self, name: str) -> Snippet:
        if name not in self.snippets:
            have = ", ".join(sorted(self.snippets)) or "none"
            raise KeyError(f"no snippet {name!r} in this extract. Have: {have}")
        return self.snippets[name]

    def __getitem__(self, name: str) -> Snippet:
        return self.snippet(name)

    def __iter__(self):
        return iter(self.snippets.values())

    def __len__(self) -> int:
        return len(self.snippets)

    @property
    def files(self) -> list[str]:
        return sorted({s.path for s in self})

    def lines(self) -> int:
        return sum(len(s) for s in self)


def cut(
    root: Path | str,
    path: str,
    first: int,
    last: int,
    tag: str,
    name: str = "",
    about: str = "",
) -> Snippet:
    """Lines `first` to `last` of one file in a GCC checkout, both ends included.

    Inclusive because that is how everybody says it out loud and how every citation in the
    book is written. An off by one here would make every line number in every lesson wrong
    by one in a way that looks right, so it gets said in the docstring as well as tested.
    """
    whole = (Path(root) / path).read_text(encoding="utf-8", errors="replace").split("\n")
    if last > len(whole):
        raise ValueError(f"{path} has {len(whole)} lines, cannot cut to {last}")
    if first < 1 or first > last:
        raise ValueError(f"{path}:{first}-{last} is not a run of lines")
    return Snippet(
        name=name or path,
        path=path,
        first=first,
        last=last,
        lines=tuple(whole[first - 1 : last]),
        tag=tag,
        about=about,
    )


def extract(root: Path | str, wanted: list[dict], tag: str) -> dict:
    """Cut every snippet a lesson asked for, as the JSON that gets committed."""
    snippets = {}
    for spec in wanted:
        got = cut(root, tag=tag, **spec)
        snippets[got.name] = {
            "path": got.path,
            "first": got.first,
            "last": got.last,
            "about": got.about,
            "lines": list(got.lines),
        }
    return {"tag": tag, "snippets": snippets}


def load_extract(name: str, root: Path | str | None = None) -> Extract:
    """Read a committed extract. This is the call a notebook makes."""
    path = Path(root or EXTRACTS) / f"{name}.json"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in path.parent.glob("*.json"))) or "none"
        raise FileNotFoundError(f"no source extract {name!r}. Have: {available}")
    data = json.loads(path.read_text(encoding="utf-8"))
    tag = data["tag"]
    return Extract(
        tag=tag,
        snippets={
            key: Snippet(
                name=key,
                path=body["path"],
                first=body["first"],
                last=body["last"],
                lines=tuple(body["lines"]),
                tag=tag,
                about=body.get("about", ""),
            )
            for key, body in data["snippets"].items()
        },
    )


#: The constructs a first time reader of GCC trips over. Each is a short key you can type, a
#: name you can read, the pattern that finds it, and one sentence of what it is.
#:
#: Order matters, because the first match is the one a lesson leads with, so the constructs
#: that carry the most meaning come first. A line is allowed to be several of these at once
#: and usually is, and flattening that to one answer is the kind of simplification that
#: leaves a reader stuck on the line after.
IDIOMS: tuple[tuple[str, str, str, str], ...] = (
    (
        "cast",
        "checked downcast",
        r"\b(as_a|dyn_cast|is_a|safe_as_a|safe_dyn_cast|safe_is_a)\s*<",
        "A downcast from is-a.h. as_a asserts, dyn_cast returns null, is_a only asks.",
    ),
    (
        "loop",
        "iterator macro",
        r"\bFOR_(EACH|BB|ALL)_\w+\s*\(",
        "A loop written as a macro, because GCC predates the range for loop by twenty years.",
    ),
    (
        "gsi",
        "statement iterator",
        r"\bgsi_[a-z_]+\s*\(",
        "A cursor into a statement sequence. GIMPLE is a list, so walking it needs one.",
    ),
    (
        "gty",
        "gc marker",
        r"\bGTY\s*\(\(",
        "A note to gengtype, which reads these and writes the code that marks the type.",
    ),
    (
        "treemacro",
        "tree accessor macro",
        r"\b(TREE|DECL|TYPE|POINTER|INTEGER|REAL|SSA_NAME|BLOCK|VAR|CONSTRUCTOR)_[A-Z0-9_]+\s*\(",
        "A macro that reaches into a tree. The union is private and the macros are the API.",
    ),
    (
        "gimple",
        "gimple accessor",
        r"\bgimple_[a-z0-9_]+\s*\(",
        "An accessor on a statement. The same idea as the tree macros, written as functions.",
    ),
    (
        "vec",
        "vector type",
        r"\bvec\s*<|\bauto_vec\b|\bvec_safe_\w+\s*\(|\.safe_(push|grow|splice|insert)\s*\(",
        "GCC's own vector. Not std::vector, because it has to live in the collected heap.",
    ),
    (
        "hash",
        "hash container",
        r"\b(hash_map|hash_set|hash_table)\b",
        "GCC's own hash container, for the same reason as vec: it has to be GC aware.",
    ),
    (
        "poly",
        "poly int",
        r"\bpoly_(int|uint|offset|wide_int)\w*\b|\b(known|maybe)_(eq|ne|lt|le|gt|ge)\s*\(",
        "A size that may not be a constant, because a vector register may not have a size yet.",
    ),
    (
        "wide",
        "wide int",
        r"\b(wide_int|widest_int|offset_int)\b|\bwi::",
        "An integer as wide as the target needs, not as wide as the host happens to be.",
    ),
    (
        "include",
        "mandatory include",
        r'^\s*#\s*include\s+"(config|system|coretypes|tm)\.h"',
        "One of the headers that has to come first, in a fixed order, before anything else.",
    ),
    (
        "pass",
        "pass boilerplate",
        r"\b(opt_pass|pass_data|make_pass_\w+|gcc::context|TODO_\w+|PROP_\w+)\b",
        "The pass manager's furniture. Every pass in passes.def has one of each.",
    ),
    (
        "dump",
        "dump call",
        r"\bdump_(file|flags|printf|enabled_p)\w*\b",
        "Where the text in a dump file comes from. Every dump you have read was one of these.",
    ),
    (
        "assert",
        "assertion",
        r"\bgcc_(assert|checking_assert|unreachable)\s*\(",
        "An internal check. gcc_assert is on in a release build and gcc_checking_assert is not.",
    ),
    (
        "code",
        "tag test",
        r"\bTREE_CODE\s*\(|\bgimple_code\s*\(|\b(code|rcode)\s*==\s*[A-Z][A-Z0-9_]+\b"
        r"|->code\s*==\s*[A-Z]",
        "Asking what kind of node this is. The tag half of the tagged union, read directly.",
    ),
    (
        "template",
        "template",
        r"^\s*template\s*<",
        "A template. GCC uses few of them and the ones it does use are mostly containers.",
    ),
    (
        "bitfield",
        "bitfield",
        r":\s*\d+\s*;",
        "A field packed into part of a word. A tree node is the size it is on purpose.",
    ),
)

_COMPILED = tuple((key, name, re.compile(p), about) for key, name, p, about in IDIOMS)

#: Every short key, in the order a lesson lists them.
KEYS = tuple(key for key, _, _, _ in IDIOMS)


def idioms(line: str) -> list[str]:
    """Every construct in one line of GCC source, by key, in the order `IDIOMS` lists them.

    A line usually has more than one. `FOR_EACH_BB_FN (bb, cfun)` is an iterator macro and
    nothing else, but `if (gimple_code (as_a <gassign *> (s)) == GIMPLE_ASSIGN)` is three
    things at once, and a reader who does not see all three is stuck.
    """
    body = re.sub(r"/\*.*?\*/", " ", line.split("//")[0])
    return [key for key, _, pattern, _ in _COMPILED if pattern.search(body)]


def code_only(lines) -> list[str]:
    """The same lines with the comments blanked out, keeping the line count.

    GCC comments quote the code they are about, so `stmt->code == GIMPLE_COND` appears in a
    comment four lines above the struct that guarantees it. A reader is being asked what the
    code does, and pointing at a sentence about the code is a wrong answer that looks right.
    """
    out, inside = [], False
    for line in lines:
        kept, i = [], 0
        while i < len(line):
            if inside:
                end = line.find("*/", i)
                if end < 0:
                    i = len(line)
                    break
                inside, i = False, end + 2
                continue
            start = line.find("/*", i)
            slashes = line.find("//", i)
            if 0 <= slashes < (start if start >= 0 else len(line)):
                kept.append(line[i:slashes])
                i = len(line)
                break
            if start < 0:
                kept.append(line[i:])
                break
            kept.append(line[i:start])
            inside, i = True, start + 2
        out.append("".join(kept))
    return out


def named(key: str) -> str:
    """The readable name of one construct."""
    for known, name, _, _ in IDIOMS:
        if known == key:
            return name
    raise KeyError(f"no idiom called {key!r}")


def explain(key: str) -> str:
    """One sentence about a construct, for a margin note or a wrong answer."""
    for known, _, _, about in IDIOMS:
        if known == key:
            return about
    raise KeyError(f"no idiom called {key!r}")


def annotate(snippet: Snippet) -> dict[int, list[str]]:
    """Every line of a snippet that has a construct in it, by its number in the file.

    Comments are taken out first, across lines as well as within them, so a construct is
    found where it is written rather than where it is talked about.
    """
    found = {}
    for n, text in enumerate(code_only(snippet.lines), start=snippet.first):
        hit = idioms(text)
        if hit:
            found[n] = hit
    return found
