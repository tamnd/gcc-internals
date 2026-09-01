"""View state, and how it goes in and out of a URL.

Every widget can be linked to. A reader who finds something worth pointing at should be able
to send "the pass tape, scrubbed to forwprop2, with `s_1` selected" rather than "the pass
tape, then scroll right a bit". So the part of a widget's state that a reader can change is
kept apart from the data it is showing, and that part goes in the fragment:

    #passtape=at:forwprop2,sel:s_1,only:changed

The fragment is meant to be read by a person, which rules out base64 and rules out JSON. It
is `key:value` pairs separated by commas, and the four characters that would be ambiguous
are percent encoded. Keys and values are short on purpose.

Two widgets on one page get one fragment each, separated by a semicolon, keyed by widget id.
"""

from __future__ import annotations

from urllib.parse import quote, unquote

SAFE = "".join(c for c in "abcdefghijklmnopqrstuvwxyz0123456789_.-*+ ")
RESERVED = ",;:#%"


def encode_value(value: str) -> str:
    return quote(value, safe=SAFE + "ABCDEFGHIJKLMNOPQRSTUVWXYZ()<>[]")


def encode(view: dict[str, str], keep_empty: bool = False) -> str:
    """A view as the body of a fragment. Empty values are left out rather than written.

    `keep_empty` writes them anyway, as a bare `key:`. That form is for the `data-state`
    attribute rather than for a URL, because it is the only way the browser side learns
    which keys a widget has, and a widget whose reveal has not been opened yet still needs
    to be told about `shown` when a link asks for it.
    """
    items = sorted(view.items())
    parts = [f"{k}:{encode_value(v)}" for k, v in items if keep_empty or v not in ("", None)]
    return ",".join(parts)


def decode(body: str) -> dict[str, str]:
    """The other direction. Anything that is not a `key:value` pair is skipped.

    A fragment arrives from the address bar, which means it arrives from a stranger, so a
    malformed one produces a widget in its default state rather than an exception.
    """
    out: dict[str, str] = {}
    for part in body.split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip()
        if key:
            out[key] = unquote(value)
    return out


def fragment(id: str, view: dict[str, str]) -> str:
    """The whole fragment for one widget, ready to put after a `#`."""
    body = encode(view)
    return f"{id}={body}" if body else ""


def read(text: str) -> dict[str, dict[str, str]]:
    """Every widget's view out of one fragment string, with or without the leading `#`."""
    out: dict[str, dict[str, str]] = {}
    for chunk in text.lstrip("#").split(";"):
        if "=" not in chunk:
            continue
        id, body = chunk.split("=", 1)
        id = id.strip()
        if id:
            out[id] = decode(body)
    return out
