"""Building the markup, and the one stylesheet all four widgets share.

Every widget renders itself to HTML in Python. The browser side does not build any markup,
it attaches behaviour to what is already there. That is what makes the static fallback real
rather than aspirational: the page a reader sees before any runtime starts is the same
markup they get after it, so there is one renderer and it cannot drift from a second one.

The stylesheet is generated from `gxmanim.palette`, so a colour appears in exactly one file
in this repository. Nothing here hard codes a hex value.
"""

from __future__ import annotations

from gxmanim.palette import DARK_PAGE, LIGHT_PAGE, ROLES, css

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def esc(text: object) -> str:
    """Text that is going into an element body or an attribute."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def attrs(values: dict[str, object]) -> str:
    """Attributes, skipping the ones whose value is None or False.

    `True` renders as a bare attribute, which is what `hidden` and `aria-current` want.
    """
    out = []
    for key, value in values.items():
        if value is None or value is False:
            continue
        name = key.rstrip("_").replace("_", "-")
        out.append(name if value is True else f'{name}="{esc(value)}"')
    return (" " + " ".join(out)) if out else ""


def el(name: str, body: str = "", **kw: object) -> str:
    return f"<{name}{attrs(kw)}>{body}</{name}>"


def void(name: str, **kw: object) -> str:
    return f"<{name}{attrs(kw)} />"


def join(parts: list[str], sep: str = "") -> str:
    return sep.join(p for p in parts if p)


def legend(items: list[tuple[str, str, str]]) -> str:
    """The key, as (glyph, css class, what it means).

    A reader who cannot tell the colours apart still gets the glyph, and a reader looking at
    a greyscale printout gets the glyph and the border. Every widget that marks anything has
    to show one of these, and it has to describe what that widget actually drew.
    """
    rows = [
        el(
            "li",
            join(
                [el("span", esc(glyph or "."), class_=f"gx-chip {cls}"), el("span", esc(means))],
                " ",
            ),
        )
        for glyph, cls, means in items
    ]
    return el("ul", join(rows), class_="gx-legend", aria_label="What the markers mean")


def role_legend(roles: list[str | tuple[str, str]]) -> str:
    """The key for a set of palette roles.

    A role's own wording is the default. A widget that uses a role for something more
    specific passes its own, because "what the current paragraph is about" tells a reader
    nothing about the name they are following.
    """
    items = []
    for r in roles:
        name, means = r if isinstance(r, tuple) else (r, ROLES[r].means)
        items.append((ROLES[name].glyph, f"gx-{name}", means))
    return legend(items)


def frame(kind: str, title: str, body: str, state: str = "", id: str = "") -> str:
    """The outer element every widget shares. The browser side looks for `data-gx`.

    `data-id` is what the URL is keyed on, so two tapes on one page keep separate state.
    `data-state` is the view alone, without the id in front of it, because the browser side
    reads it straight into a view object.
    """
    id = id or kind
    head = el("h4", esc(title), class_="gx-title", id=f"{id}-title")
    return el(
        "div",
        join([style(), head, body]),
        class_=f"gx-root gx-{kind}",
        data_gx=kind,
        data_id=id,
        data_state=state,
        role="group",
        aria_labelledby=f"{id}-title",
    )


_STYLE_ONCE = "gx-style"


def style() -> str:
    """The stylesheet, marked so that a page with ten widgets on it still ships it once."""
    return el("style", STYLESHEET, data_gx_style=_STYLE_ONCE)


STYLESHEET = f""":root {{
{css("light")}
}}
@media (prefers-color-scheme: dark) {{
  :root {{
{css("dark")}
  }}
}}
.gx-root {{ font: 13px/1.5 system-ui, sans-serif; color: var(--gx-neutral-ink);
  background: var(--gx-page); border: 1px solid var(--gx-unknown-ink); border-radius: 6px;
  padding: 10px; margin: 1em 0; }}
.gx-root :focus-visible {{ outline: 2px solid var(--gx-focus-ink); outline-offset: 1px; }}
.gx-title {{ margin: 0 0 8px; font-size: 13px; font-weight: 600; }}
.gx-note {{ color: var(--gx-unknown-ink); font-size: 12px; margin: 6px 0 0; }}
.gx-mono {{ font-family: {MONO}; font-size: 12px; white-space: pre; }}

.gx-legend {{ list-style: none; display: flex; flex-wrap: wrap; gap: 4px 14px;
  margin: 8px 0 0; padding: 0; font-size: 12px; color: var(--gx-unknown-ink); }}
.gx-legend li {{ display: flex; gap: 5px; align-items: center; }}
.gx-chip {{ font-family: {MONO}; min-width: 1.3em; text-align: center;
  border-radius: 3px; padding: 0 3px; }}
.gx-added {{ color: var(--gx-added-ink); background: var(--gx-added-fill);
  border: 1px solid currentColor; }}
.gx-removed {{ color: var(--gx-removed-ink); background: var(--gx-removed-fill);
  border: 1px dashed currentColor; }}
.gx-changed {{ color: var(--gx-changed-ink); background: var(--gx-changed-fill);
  border: 3px double currentColor; }}
.gx-focus {{ color: var(--gx-focus-ink); background: var(--gx-focus-fill);
  border: 1px solid currentColor; }}
.gx-constant {{ color: var(--gx-constant-ink); background: var(--gx-constant-fill);
  border: 1px solid currentColor; }}
.gx-unknown {{ color: var(--gx-unknown-ink); background: var(--gx-unknown-fill);
  border: 1px dotted currentColor; }}
.gx-neutral {{ color: var(--gx-neutral-ink); background: var(--gx-neutral-fill);
  border: 1px solid var(--gx-unknown-fill); }}

.gx-tape {{ display: flex; gap: 1px; overflow-x: auto; padding: 2px 0 6px;
  scrollbar-width: thin; }}
.gx-cell {{ flex: 0 0 auto; width: 9px; height: 34px; border: 0; padding: 0;
  background: var(--gx-neutral-fill); border-bottom: 3px solid var(--gx-unknown-fill);
  cursor: pointer; }}
.gx-cell[data-changed="1"] {{ background: var(--gx-changed-fill);
  border-bottom-color: var(--gx-changed-ink); }}
.gx-cell[data-phase="rtl"] {{ border-top: 3px solid var(--gx-constant-ink); }}
.gx-cell[data-phase="ipa"] {{ border-top: 3px solid var(--gx-added-ink); }}
.gx-cell[data-phase="tree"] {{ border-top: 3px solid var(--gx-focus-ink); }}
.gx-cell[aria-current="true"] {{ outline: 2px solid var(--gx-focus-ink); outline-offset: 0;
  background: var(--gx-focus-fill); }}
.gx-panel[hidden] {{ display: none; }}
.gx-panel {{ margin-top: 8px; padding: 8px; background: var(--gx-neutral-fill);
  border-radius: 4px; }}
.gx-stat {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px;
  color: var(--gx-unknown-ink); margin: 0 0 6px; }}

.gx-predictgate fieldset {{ border: 1px solid var(--gx-unknown-ink); border-radius: 4px;
  padding: 8px 12px; margin: 0; }}
.gx-predictgate legend {{ padding: 0 4px; font-weight: 600; }}
.gx-predictgate label {{ display: flex; gap: 8px; align-items: baseline; padding: 4px 0;
  cursor: pointer; }}
.gx-verdict {{ margin-top: 8px; }}
.gx-right {{ color: var(--gx-added-ink); }}
.gx-wrong {{ color: var(--gx-removed-ink); }}

.gx-controls {{ display: flex; flex-wrap: wrap; gap: 4px; margin: 0 0 6px; }}
.gx-controls button {{ font: inherit; font-size: 12px; padding: 1px 8px; cursor: pointer;
  border: 1px solid var(--gx-unknown-fill); border-radius: 999px;
  background: var(--gx-neutral-fill); color: inherit; }}
.gx-controls button[aria-pressed="true"], .gx-controls button[aria-current="true"] {{
  background: var(--gx-focus-fill); color: var(--gx-focus-ink);
  border-color: currentColor; font-weight: 600; }}
.gx-controls button[disabled] {{ opacity: .5; cursor: default; }}
.gx-reveal {{ font: inherit; font-size: 12px; margin-top: 6px; padding: 2px 10px;
  border: 1px solid var(--gx-focus-ink); border-radius: 4px;
  background: var(--gx-focus-fill); color: var(--gx-focus-ink); cursor: pointer; }}
.gx-reveal[disabled] {{ opacity: .55; cursor: not-allowed; }}
.gx-spark {{ color: var(--gx-focus-ink); display: block; }}
.gx-answer[hidden] {{ display: none; }}
.gx-answer summary {{ cursor: pointer; }}

.gx-web {{ max-width: 100%; overflow-x: auto; color: var(--gx-focus-ink); }}
.gx-web text {{ font-family: {MONO}; font-size: 12px; fill: var(--gx-neutral-ink); }}
.gx-web .thread {{ fill: none; stroke: currentColor; stroke-width: 1.2; }}
.gx-web .def {{ fill: currentColor; }}
.gx-web .use {{ fill: none; stroke: currentColor; stroke-width: 1.6; }}
.gx-web .tick {{ fill: currentColor; font-size: 10px; }}
.gx-web .row-header {{ fill: var(--gx-unknown-ink); }}
.gx-web .hit {{ fill: currentColor; font-weight: 700; }}
"""

# The two page colours are exported so a host page can match the widget background without
# reaching into the palette module itself.
PAGE = {"light": LIGHT_PAGE, "dark": DARK_PAGE}
