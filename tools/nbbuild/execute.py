"""Running a lesson end to end, which is the only evidence that it works.

Outputs are never committed, so nothing in the repository proves a cell still runs. This is
what proves it. Every lesson is executed top to bottom in a real kernel and the first cell
that raises fails the build, with the traceback and the source of the cell that produced it.

Not raising is a weaker guarantee than it sounds, though. A cell can print an empty list
where the prose promised four names and no exception is involved anywhere, so `transcript`
exists to put what the lesson actually printed in front of a person. Reading that after a
change is the difference between a lesson that runs and a lesson that is right.

It needs `nbclient`, which is in the `lessons` extra rather than in `dev`, because the
toolkit itself has no runtime dependencies and running a notebook is not something a reader
of `gxray` should have to install a kernel for.

Lessons are written so this works with no network and no compiler. A cell that needs either
is a cell that will be flaky in CI and useless to a reader on a train, which is the same
reason Part I runs on recorded dumps.
"""

from __future__ import annotations

from pathlib import Path

#: A lesson that takes longer than this is doing something it should not, most likely
#: reaching for the network. Failing is better than a CI job that hangs for six hours.
TIMEOUT = 300

#: Enough of a long output to see that it is the right shape, without a transcript that
#: nobody scrolls to the end of. Whole outputs are still in the notebook if you want them.
HEAD = 40


class Failed(RuntimeError):
    """A cell raised. Carries the cell's source, because a traceback alone is not enough."""


def execute(path: Path):
    """Execute one notebook in a fresh kernel and hand back the executed copy.

    Nothing is written back to disk. The executed notebook exists only in memory, which
    keeps the committed file free of outputs without needing a stripping step that somebody
    will eventually forget to run.
    """
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    book = nbformat.read(path, as_version=4)
    client = NotebookClient(book, timeout=TIMEOUT, kernel_name="python3", allow_errors=False)
    try:
        client.execute(cwd=str(path.parent.parent.parent))
    except CellExecutionError as exc:
        # nbclient's message includes the traceback but not the code, and the cell number it
        # gives counts markdown cells too, so on its own it is oddly hard to act on.
        raise Failed(f"{path.name}: a cell raised\n\n{exc}") from None
    return book


def run(path: Path) -> int:
    """Execute one notebook and return how many code cells ran."""
    book = execute(path)
    return sum(1 for cell in book.cells if cell.cell_type == "code")


def text_of(output) -> str:
    """What one output looks like as plain text, whatever kind of output it is."""
    match output.get("output_type"):
        case "stream":
            return "".join(output.get("text", ""))
        case "execute_result" | "display_data":
            data = output.get("data", {})
            if "text/plain" in data:
                return "".join(data["text/plain"])
            return f"[{', '.join(sorted(data)) or 'no data'}]"
        case "error":
            return "\n".join(output.get("traceback", [output.get("evalue", "error")]))
        case _:
            return ""


def clip(text: str, lines: int = HEAD) -> str:
    """Long outputs get their head and a note, because a whole dump is not worth reading."""
    got = text.rstrip("\n").split("\n")
    if len(got) <= lines:
        return "\n".join(got)
    return "\n".join(got[:lines] + [f"... {len(got) - lines} more lines"])


def transcript(book, lines: int = HEAD) -> str:
    """Every code cell and what it printed, for a person to read.

    Cells that print nothing are still listed. A cell that was supposed to print something
    and quietly did not is the failure this is here to catch, so leaving it out would defeat
    the purpose.
    """
    out = []
    for cell in book.cells:
        if cell.cell_type != "code":
            continue
        out.append(f"--- {cell.get('id', '?')} " + "-" * 60)
        out.append(clip(cell.source, lines))
        printed = "\n".join(t for t in (text_of(o) for o in cell.outputs) if t)
        out.append("")
        out.append(clip(printed, lines) if printed.strip() else "(no output)")
        out.append("")
    return "\n".join(out)
