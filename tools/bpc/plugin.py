"""Section 2 of `BP-PLUGIN`, generated from GCC's own list of plugin events.

Two files, read out of the pinned tree every time the blueprint is built:

    gcc/plugin.def      every event, in the order that fixes its enumerator value
    gcc/**/*.cc         every `invoke_plugin_callbacks` call, which is where it fires

The second half is the part worth having. `plugin.def` says an event exists and what the
comment above it claims it means, and it does not say where it fires or what pointer comes
with it. Both of those are the facts a plugin author needs, both live in call sites spread
over eleven files in three directories, and neither is written down anywhere in GCC. A
plugin that registers for `PLUGIN_FINISH_TYPE` and casts the data to the wrong thing gets a
segfault in somebody else's compiler, so the type of the second argument is not a detail.

An event with no call site is not a mistake. Three of the twenty six are pseudo-events,
meaning `register_callback` does the work immediately and no callback is ever stored, and
the table says so rather than leaving a blank row that reads like a gap in the scan.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools.bpc import generator
from tools.bpc.gccsrc import Entry, read
from tools.bpc.gccsrc import parse_def as parse_def_file

PLUGIN_DEF = "gcc/plugin.def"

# The call is written on one line at most sites and split over two at one of them, so the
# scan joins the file and matches across newlines rather than line by line.
CALL = re.compile(
    r"invoke_plugin_callbacks\s*\(\s*(?P<event>PLUGIN_[A-Z_]+)\s*,\s*(?P<data>.*?)\s*\)\s*;",
    re.DOTALL,
)

# Where to look. The front ends fire nearly half the events and none of them are in gcc/
# itself, so a scan of the top directory alone would report most of the table as dead.
SUBDIRS = ("", "c", "c-family", "cp")

# `register_callback` handles these three itself and stores nothing, so they never reach
# `invoke_plugin_callbacks` and `invoke_plugin_callbacks_full` asserts if one arrives.
PSEUDO = {
    "PLUGIN_PASS_MANAGER_SETUP": "`struct register_pass_info *`, at registration",
    "PLUGIN_INFO": "`struct plugin_info *`, at registration",
    "PLUGIN_REGISTER_GGC_ROOTS": "`const struct ggc_root_tab *`, at registration",
}


def events(root: Path) -> list[Entry]:
    return parse_def_file(read(root / "plugin.def"), "DEFEVENT")


def sites(root: Path) -> dict[str, list[tuple[str, int, str]]]:
    """Every place an event is fired: the file, the line, and the data expression.

    Keyed by event name. `plugin.cc` is skipped because the two mentions in it are the
    dispatcher's own switch, not a call.
    """
    found: dict[str, list[tuple[str, int, str]]] = {}
    for sub in SUBDIRS:
        directory = root / sub if sub else root
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.cc")):
            if path.name == "plugin.cc":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "invoke_plugin_callbacks" not in text:
                continue
            for match in CALL.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                where = f"{sub}/{path.name}" if sub else path.name
                data = " ".join(match.group("data").split())
                found.setdefault(match.group("event"), []).append((where, line, data))
    return found


def data_type(expression: str) -> str:
    """What the `void *` handed to a callback actually points at.

    Read off the argument expression rather than guessed. `NULL` means there is no data,
    and a callback that dereferences it on one of those events is reading address zero.
    """
    if expression == "NULL":
        return "none"
    if expression.startswith("&"):
        return f"`{expression[1:]}`, by address"
    return f"`{expression}`"


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


@generator("plugin-events")
def plugin_events(root: Path) -> str:
    every = events(root)
    where = sites(root)

    rows = [
        "| # | Event | Data passed | Fired from |",
        "|---|---|---|---|",
    ]
    for entry in every:
        name = entry.name
        if name in PSEUDO:
            rows.append(f"| {entry.index} | `{name}` | {PSEUDO[name]} | not fired |")
            continue
        found = where.get(name, [])
        if not found:
            rows.append(f"| {entry.index} | `{name}` | unknown | no call site found |")
            continue
        kinds = sorted({data_type(data) for _, _, data in found})
        places = ", ".join(f"`gcc/{f}:{n}`" for f, n, _ in found)
        rows.append(f"| {entry.index} | `{name}` | {' / '.join(kinds)} | {places} |")

    total = len(every)
    fired = sum(1 for e in every if e.name not in PSEUDO and where.get(e.name))
    calls = sum(len(v) for v in where.values())

    summary = (
        f"`gcc/plugin.def` defines **{total} events**. {len(PSEUDO)} of them are "
        f"pseudo-events, handled by `register_callback` at registration time and never "
        f"fired. The remaining {fired} are fired from **{calls} call sites**. The number "
        f"in the first column is the enumerator's value, and it is the index into "
        f"`plugin_callbacks` and `plugin_event_name`, so the order of `plugin.def` is the "
        f"ABI."
    )

    notes = [
        "",
        summary,
        "",
        *rows,
        "",
        "A row saying the data is `none` is a row where the callback is handed a null "
        "pointer. Nothing in the signature says so and nothing checks it.",
    ]
    return "\n".join(notes)


@generator("plugin-event-docs")
def plugin_event_docs(root: Path) -> str:
    """What GCC's own comment above each event says, verbatim.

    Separate from the table above because the comments are the only documentation of intent
    that exists, several of them are one clause long, and reading them next to each other is
    the fastest way to see which events were designed and which were added for one caller.
    """
    rows = ["| Event | What `plugin.def` says |", "|---|---|"]
    for entry in events(root):
        rows.append(f"| `{entry.name}` | {cell(entry.doc) or 'nothing'} |")
    return "\n".join(rows)
