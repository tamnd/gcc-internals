"""The prediction gate.

Before any output is shown, the reader commits to an answer. Then they run it. Then the
explanation arrives. This is the rule authors most want to skip, because it makes a lesson
longer, and it is also the rule that turns reading into learning.

Compiler material suits it unusually well. Almost everyone who writes C has a confident,
detailed and partly wrong model of what the optimizer does, and surfacing that is most of
the teaching. A gate needs a defensible wrong answer. "Does `-O2` unroll this loop" is a
good gate. "Does the compiler parse this" is not, and the author guidance says so.

The static fallback is a `details` element, so the gate works with no JavaScript: the reader
can answer in their head and open the answer. With JavaScript the reveal stays shut until an
option is chosen, which is the version that actually enforces the rule.

Each wrong option carries its own explanation. A gate that only says "wrong" teaches nothing,
and the reason a reader picked the wrong answer is usually more interesting than the right
one.
"""

from __future__ import annotations

from dataclasses import dataclass

from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join


@dataclass
class Option:
    text: str
    why: str = ""
    correct: bool = False


class GateError(ValueError):
    """A gate that would not teach anything, caught when it is built."""


class PredictGate(Widget):
    kind = "predictgate"
    title = "Predict, then run"
    defaults = {"pick": "", "shown": ""}

    def __init__(
        self,
        question: str,
        options: list[Option] | list[tuple[str, str]] | None = None,
        answer: str = "",
        observe: str = "",
        **kw: str,
    ) -> None:
        self.question = question
        self.options = _options(options or [])
        self.answer = answer
        self.observe = observe
        self._validate()
        super().__init__(**kw)

    def _validate(self) -> None:
        if len(self.options) < 2:
            raise GateError("a gate with one option is a statement, not a question")
        right = [o for o in self.options if o.correct]
        if len(right) != 1:
            raise GateError(f"a gate has exactly one correct option, this one has {len(right)}")
        missing = [o.text for o in self.options if not o.correct and not o.why]
        if missing:
            raise GateError(
                f"these wrong options do not say why they are wrong: {', '.join(missing)}. "
                f"A gate that only says wrong teaches nothing."
            )
        if not self.answer:
            raise GateError("a gate needs an explanation to show after the reader commits")

    @property
    def correct(self) -> int:
        return next(i for i, o in enumerate(self.options) if o.correct)

    def data(self) -> dict:
        return {"correct": self.correct, "why": [o.why for o in self.options]}

    # Rendering

    def body(self) -> str:
        return join([self._form(), self._reveal()])

    def _form(self) -> str:
        picked = self.view["pick"]
        rows = []
        for i, o in enumerate(self.options):
            input_id = f"{self.id}-opt-{i}"
            rows.append(
                el(
                    "label",
                    join(
                        [
                            f'<input type="radio" name="{esc(self.id)}" id="{esc(input_id)}" '
                            f'value="{i}" data-option="{i}"'
                            + (" checked" if picked == str(i) else "")
                            + " />",
                            el("span", esc(o.text)),
                        ],
                        " ",
                    ),
                    for_=input_id,
                )
            )
        return el(
            "fieldset",
            join([el("legend", esc(self.question)), *rows, self._button()]),
        )

    def _button(self) -> str:
        return el(
            "button",
            "Show what actually happens",
            type="button",
            class_="gx-reveal",
            data_reveal=self.id,
            aria_expanded="true" if self.view["shown"] else "false",
            aria_controls=f"{self.id}-verdict",
        )

    def _reveal(self) -> str:
        """The answer. A `details` so it works with nothing running, closed by default."""
        parts = []
        if self.observe:
            parts.append(el("pre", esc(self.observe), class_="gx-mono"))
        parts.append(el("p", esc(self.answer)))
        for i, o in enumerate(self.options):
            if o.why:
                parts.append(
                    el(
                        "p",
                        join(
                            [
                                el("span", esc(o.text), class_="gx-chip gx-removed"),
                                el("span", esc(o.why)),
                            ],
                            " ",
                        ),
                        class_="gx-note",
                        data_why=i,
                    )
                )
        body = el("div", join(parts), id=f"{self.id}-verdict", class_="gx-verdict")
        return el(
            "details",
            join([el("summary", "What actually happens"), body]),
            class_="gx-answer",
            open=bool(self.view["shown"]),
        )


def _options(raw: list[Option] | list[tuple[str, str]]) -> list[Option]:
    """Options as given, or as `(text, why)` pairs where the correct one has an empty why.

    The pair form exists because a gate is written inline in a lesson and the long form is
    four lines of ceremony per option.
    """
    out = []
    for item in raw:
        if isinstance(item, Option):
            out.append(item)
        else:
            text, why = item
            out.append(Option(text=text, why=why, correct=not why))
    return out
