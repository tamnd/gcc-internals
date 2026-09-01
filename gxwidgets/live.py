"""The notebook bridge.

Everything a widget does works without this file. What it adds is the round trip: when the
reader changes the view in the browser, Python hears about it, re-renders, and sends the new
markup back. That matters for the things a static page cannot recompute, and it is why a
notebook is worth having rather than just a nicer looking page.

`anywidget` is the whole dependency, and it is optional. A widget imports fine, renders fine
and tests fine without it, so CI never installs a notebook stack. The import is here rather
than at the top of the package for exactly that reason.
"""

from __future__ import annotations

from pathlib import Path

from gxwidgets.base import Widget

ESM = Path(__file__).parent / "static" / "widget.js"

HINT = (
    "anywidget is not installed, so a widget cannot be shown live in a notebook. "
    "Install it with `pip install anywidget`, or call `widget.render()` for the static "
    "version, which is the same markup with nothing attached to it."
)


def to_anywidget(widget: Widget):
    """Wrap a widget so a notebook can show it."""
    try:
        import anywidget
        import traitlets
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on the environment
        raise ModuleNotFoundError(HINT) from exc

    class Live(anywidget.AnyWidget):
        _esm = ESM
        html = traitlets.Unicode("").tag(sync=True)
        view = traitlets.Dict({}).tag(sync=True)
        data = traitlets.Dict({}).tag(sync=True)

        def __init__(self, inner: Widget) -> None:
            self._inner = inner
            super().__init__(html=inner.render(), view=dict(inner.view), data=inner.data())

        @traitlets.observe("view")
        def _redraw(self, change) -> None:
            wanted = {k: v for k, v in change["new"].items() if k in self._inner.defaults}
            if wanted == self._inner.view:
                return
            self._inner.view.update(wanted)
            self.html = self._inner.render()

    return Live(widget)
