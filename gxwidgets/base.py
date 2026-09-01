"""What every widget in this project is.

Three rules, and the base class exists to make all three hard to break.

**A widget consumes a `gxray` model, never raw text.** If a widget parses a dump then the
parser has been written twice and one copy is about to go wrong. Every constructor here
takes something out of `gxray` and the file has no regular expressions in it.

**A widget renders itself in Python.** The markup is built here, the browser attaches
behaviour to it. So the static fallback is not a second implementation that drifts, it is
the same one with nothing plugged in yet, and a lesson is readable before Pyodide starts and
stays readable if it never does.

**A widget is usable without a mouse and without colour vision.** Selection is a real
`button` or a real `input`, the current item carries `aria-current`, panels are associated
with their controls, and every role shows a glyph as well as a fill.

Subclasses provide `kind`, `defaults`, `body()` and `data()`, and get rendering, view state,
URL round tripping and the notebook bridge from here.
"""

from __future__ import annotations

from gxwidgets import state as urlstate
from gxwidgets.html import frame


class Widget:
    """A rendered thing with a small amount of state a reader can change."""

    kind = "widget"
    defaults: dict[str, str] = {}
    title = "Widget"

    def __init__(self, id: str | None = None, **view: str) -> None:
        self.id = id or self.kind
        self.view = dict(self.defaults)
        self.update(**view)

    def update(self, **view: str) -> None:
        """Change the view. A key the widget does not have is a mistake worth hearing about.

        Views that arrive from a URL go through `from_fragment` instead, which drops what it
        does not recognise, because that one comes from a stranger.
        """
        for key, value in view.items():
            if key not in self.defaults:
                known = ", ".join(sorted(self.defaults)) or "none"
                raise KeyError(f"{self.kind} has no view key {key!r}. It has: {known}")
            self.view[key] = str(value)

    def from_fragment(self, text: str) -> None:
        """Apply this widget's slice of a URL fragment, ignoring anything unfamiliar."""
        wanted = urlstate.read(text).get(self.id, {})
        for key, value in wanted.items():
            if key in self.defaults:
                self.view[key] = value

    @property
    def state(self) -> str:
        """The view on its own, which is what goes in `data-state` for the browser side.

        Every key is written, including the empty ones, because this is also how the browser
        learns which keys this widget has and which ones a link is allowed to set.
        """
        return urlstate.encode(self.view, keep_empty=True)

    @property
    def fragment(self) -> str:
        """This widget's view with its id in front, ready to put after a `#`."""
        return urlstate.fragment(self.id, {k: v for k, v in self.view.items() if v})

    def data(self) -> dict:
        """The JSON that the browser side needs. Nothing that is already in the markup."""
        return {}

    def body(self) -> str:
        raise NotImplementedError

    def render(self) -> str:
        """The whole widget, standalone, no runtime needed."""
        return frame(self.kind, self.title, self.body(), state=self.state, id=self.id)

    def _repr_html_(self) -> str:
        return self.render()

    def __str__(self) -> str:
        return f"{self.kind}({self.id})"


def live(widget: Widget):
    """The same widget as an anywidget, for a notebook or a WASM page.

    Kept out of the widget classes so that `import gxwidgets` costs nothing and works in an
    environment with no notebook stack at all, which is most of CI.
    """
    from gxwidgets.live import to_anywidget

    return to_anywidget(widget)
