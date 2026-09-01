"""The prose rules, as code.

Everything here is a rule from the authoring guide that a script can check without
guessing at intent. Rules that need a human stay with the human.

Run it over any markdown file:

    python -m tools.prosecheck lessons/T05/lesson.md

The rules:

1. No em dashes or en dashes. They are the single clearest tell that a paragraph was not
   typed by a person, and a comma or a full stop always works instead.
2. No filler words that shrink the reader. "simply", "just", "obviously", "of course",
   "merely", "trivially". Every one of them is a small insult to whoever finds it hard,
   and in this material somebody will find every single thing hard.
3. No sentence broken across a line. Markdown joins the lines anyway, so a hard wrap
   mid sentence only makes the diff noisier and the source harder to edit.
4. No horizontal rules. A page break in a web page is a decoration that costs a scroll.
5. Every fenced code block declares a language, so the site can highlight it and so a
   reader can tell a shell command from a dump.

Code spans and fenced code blocks are exempt from rules 1 to 3, because `just build` is a
command and a dump excerpt is whatever GCC printed.

A page that has to write a banned word down, which so far means the page listing the rules,
turns the checker off around it and says why:

    <!-- prosecheck: off, this paragraph is quoting the words it bans -->
    ...
    <!-- prosecheck: on -->

The reason is not optional. A suppression with no reason is itself a finding, because the
point of the escape hatch is that the next reader can see whether it was earned.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

DASHES = re.compile(r"[—–]")
FILLER = re.compile(
    r"(?<![\w-])(simply|just|obviously|of course|merely|trivially)(?![\w-])",
    re.IGNORECASE,
)
RULE = re.compile(r"^\s{0,3}([-*_])\s*(?:\1\s*){2,}$")
FENCE = re.compile(r"^\s*(```+|~~~+)\s*(\S*)")
INLINE_CODE = re.compile(r"`[^`]*`")
SUPPRESS = re.compile(r"^\s*<!--\s*prosecheck:\s*(off|on)\s*(.*?)\s*-->\s*$")
SENTENCE_END = re.compile(r"[.!?][\"')\]]?$")
# A line that continues a sentence starts lowercase, or with a word we would never open on.
CONTINUES = re.compile(r"^[a-z(]")


@dataclass
class Finding:
    path: Path
    line: int
    rule: str
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.text}"


def _strip_code(line: str) -> str:
    """Blank out inline code spans so a command in backticks cannot trip a prose rule."""
    return INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)


def check_text(text: str, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    in_fence = False
    fence_marker = ""
    in_front_matter = False
    suppressed = False
    prev_prose = ""
    prev_no = 0

    for i, raw in enumerate(lines, start=1):
        marker = SUPPRESS.match(raw)
        if marker:
            state, reason = marker.group(1), marker.group(2).lstrip(",").strip()
            if state == "off":
                if not reason:
                    findings.append(Finding(path, i, "suppression with no reason", raw.strip()))
                suppressed = True
            else:
                suppressed = False
            prev_prose = ""
            continue
        if suppressed:
            continue

        if i == 1 and raw.strip() == "---":
            in_front_matter = True
            continue
        if in_front_matter:
            if raw.strip() == "---":
                in_front_matter = False
            continue

        fence = FENCE.match(raw)
        if fence:
            marker, lang = fence.group(1), fence.group(2)
            if not in_fence:
                in_fence, fence_marker = True, marker[0] * 3
                if not lang:
                    findings.append(Finding(path, i, "unlabelled code block", raw.strip()))
            elif marker.startswith(fence_marker):
                in_fence = False
            prev_prose = ""
            continue
        if in_fence:
            continue

        if RULE.match(raw):
            findings.append(Finding(path, i, "horizontal rule", raw.strip()))
            prev_prose = ""
            continue

        prose = _strip_code(raw)

        for m in DASHES.finditer(prose):
            findings.append(Finding(path, i, "em or en dash", _context(prose, m.start())))
        for m in FILLER.finditer(prose):
            findings.append(
                Finding(path, i, f"filler word {m.group(1)!r}", _context(prose, m.start()))
            )

        stripped = prose.strip()
        if prev_prose and stripped and CONTINUES.match(stripped):
            findings.append(
                Finding(path, prev_no, "sentence wrapped across lines", prev_prose[-60:].strip())
            )
        # Only plain paragraph text can be a wrapped sentence. Lists, headings, tables and
        # blockquotes are structure, and a table row legitimately starts lowercase.
        is_paragraph = bool(stripped) and not re.match(r"^([#>|]|[-*+]\s|\d+\.\s|\[)", stripped)
        prev_prose = stripped if is_paragraph and not SENTENCE_END.search(stripped) else ""
        prev_no = i

    return findings


def _context(line: str, at: int, width: int = 30) -> str:
    lo, hi = max(0, at - width), min(len(line), at + width)
    return ("..." if lo else "") + line[lo:hi].strip() + ("..." if hi < len(line) else "")


def check_file(path: Path) -> list[Finding]:
    return check_text(path.read_text(encoding="utf-8"), path)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m tools.prosecheck FILE [FILE ...]", file=sys.stderr)
        return 2

    paths: list[Path] = []
    for a in args:
        p = Path(a)
        paths.extend(sorted(p.rglob("*.md")) if p.is_dir() else [p])

    findings = [f for p in paths for f in check_file(p)]
    for f in findings:
        print(f)

    n = len(paths)
    if findings:
        print(f"\n{len(findings)} problem(s) in {n} file(s)", file=sys.stderr)
        return 1
    print(f"prosecheck: {n} file(s) clean")
    return 0
