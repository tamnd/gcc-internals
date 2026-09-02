"""One insn, opened up.

RTL is the first thing in the pipeline that looks like it was written for a machine rather
than for a person, and the reaction to a first `.expand` dump is reliably the same: what is
this Lisp-looking thing. The answer is that it is a tree, printed the way trees have been
printed since 1958, and that every node in it says three things and only three: what it is,
how wide it is, and what it is made of.

So this widget takes the printed form apart and puts each of those three in its own column.
The middle column is the machine mode, which is the field a reader new to RTL skips and then
spends an hour confused by. The right hand column is a sentence.

The sentence is the point. `(set (pc) (if_then_else (le (reg:CC 66 cc) (const_int 0))
(label_ref 45) (pc)))` reads as "the program counter becomes label 45 if the condition
register is less than or equal to 0, otherwise the program counter", and a reader who has
seen ten of those stops needing the widget. That is the intended outcome. `english` below
handles about twenty five codes out of the two hundred and three in `rtl.def` and falls back
to naming the code for the rest, which is honest: it is a reading aid, not a decompiler.
"""

from __future__ import annotations

from gxray.rtl import UNRECOGNISED, VECTOR, Insn, Listing, Rtx
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, legend

#: How many insns to open up. Ten is the whole of a small function's prologue and first
#: block, which is enough to meet a note, a debug insn and three real ones.
LIMIT = 10

#: What a machine mode is, in bytes and in words. The letters are a size scale with a
#: four-byte word in the middle: Q is a quarter of it, H a half, S the whole thing, D twice,
#: T four times. GCC's own manual writes "Tetra Integer (?)" for the fourth one, question
#: mark included, so nobody is certain where the naming ran out either.
MODES = {
    "BI": (0, "one bit, for a predicate register"),
    "QI": (1, "quarter integer, one byte"),
    "HI": (2, "half integer, two bytes"),
    "SI": (4, "single integer, four bytes"),
    "DI": (8, "double integer, eight bytes"),
    "TI": (16, "tetra integer, sixteen bytes"),
    "OI": (32, "octa integer, thirty two bytes"),
    "XI": (64, "hexadeca integer, sixty four bytes"),
    "HF": (2, "half float"),
    "SF": (4, "single float, a C float"),
    "DF": (8, "double float, a C double"),
    "TF": (16, "tetra float"),
    "VOID": (0, "no mode, which is what a node that is not a value has"),
    "BLK": (0, "a block of memory of no particular shape"),
}

#: What an RTX code means. Twenty five of two hundred and three, chosen because these are
#: the ones a four line loop produces on four different targets.
CODES = {
    "set": "put the right hand side into the left hand side",
    "reg": "a register",
    "const_int": "a literal integer",
    "const_double": "a literal floating point number",
    "pc": "the program counter, so assigning to it is a jump",
    "label_ref": "the address of a label",
    "symbol_ref": "the address of a named thing",
    "mem": "the memory at this address",
    "subreg": "part of a wider register",
    "plus": "add",
    "minus": "subtract",
    "mult": "multiply",
    "neg": "negate",
    "and": "bitwise and",
    "ior": "bitwise or",
    "xor": "bitwise exclusive or",
    "not": "bitwise not",
    "ashift": "shift left",
    "ashiftrt": "shift right, keeping the sign",
    "lshiftrt": "shift right, filling with zeros",
    "sign_extend": "widen, copying the sign bit",
    "zero_extend": "widen, filling with zeros",
    "compare": "compare, and leave the answer in a condition register",
    "if_then_else": "one of two values, chosen by the first",
    "parallel": "all of these happen in one instruction",
    "vector": "a list of expressions, which the dump prints in square brackets",
    "clobber": "this gets destroyed, do not keep anything in it",
    "use": "this value is still needed at this point",
    "call": "call this, with this much argument space",
    "return": "return from the function",
    "debug_marker": "nothing runs here, it marks a source position for the debugger",
    "var_location": "where a source variable is living at this point",
    "unspec": "something only the target knows how to describe",
    "unspec_volatile": "the same, and it may not be moved or deleted",
    "scratch": "a register the pattern needs and nobody else can see",
    "nil": "nothing",
}

#: The comparison codes, spelled out. They are their own group because they read as verbs
#: and everything else reads as a noun.
TESTS = {
    "eq": "is equal to",
    "ne": "is not equal to",
    "lt": "is less than",
    "le": "is less than or equal to",
    "gt": "is greater than",
    "ge": "is greater than or equal to",
    "ltu": "is below, unsigned",
    "leu": "is below or equal to, unsigned",
    "gtu": "is above, unsigned",
    "geu": "is above or equal to, unsigned",
}

#: The single letter flags GCC prints after a code, and what the bit is called when it is on
#: a register. The same bit means something else on a `mem` or a `subreg`, which is worth
#: knowing and is why these say "on a register".
FLAGS = {
    "v": "a register the user declared",
    "i": "the register the function returns in",
    "u": "known not to change",
    "s": "a value already widened to fill the register",
    "f": "part of the frame setup",
    "j": "known to be a jump",
    "c": "part of a call",
}

#: What a note or a barrier is, for the ones a first dump contains.
KINDS = {"code": "becomes an instruction", "debug": "for the debugger", "other": "a marker"}


def kind_of(insn: Insn) -> str:
    if insn.is_debug:
        return "debug"
    return "code" if insn.is_code else "other"


def register_name(node: Rtx) -> str:
    """A register, said out loud. The bracket after the number is the variable it holds."""
    if node.register is None:
        return "a register"
    named = [x for x in node.leaves[1:] if not x.startswith("[")]
    holds = [x.strip("[] ") for x in node.leaves[1:] if x.startswith("[")]
    what = f"pseudo {node.register}" if node.pseudo else f"register {named[0]}"
    return f"{what}, holding {holds[0]}" if holds and holds[0] else what


def english(node: Rtx | str) -> str:
    """One RTX expression as a sentence.

    Recursive, and deliberately literal. A smoother sentence would hide the shape, and the
    shape is what the reader is here to learn.
    """
    if isinstance(node, str):
        return node.strip("[] ") or node
    kids = node.children
    code = node.code

    if code == "reg":
        return register_name(node)
    if code == "const_int":
        return str(node.value) if node.value is not None else "a constant"
    if code == "pc":
        return "the program counter"
    if code == "label_ref":
        return f"label {node.leaves[0]}" if node.leaves else "a label"
    if code == "symbol_ref":
        return f"the address of {english(node.leaves[0])}" if node.leaves else "an address"
    if code in TESTS and len(kids) == 2:
        return f"{english(kids[0])} {TESTS[code]} {english(kids[1])}"
    if code == "set" and len(kids) == 2:
        return f"{english(kids[0])} becomes {english(kids[1])}"
    if code == "plus" and len(kids) == 2:
        return f"{english(kids[0])} plus {english(kids[1])}"
    if code == "minus" and len(kids) == 2:
        return f"{english(kids[0])} minus {english(kids[1])}"
    if code == "mult" and len(kids) == 2:
        return f"{english(kids[0])} times {english(kids[1])}"
    if code == "compare" and len(kids) == 2:
        return f"the result of comparing {english(kids[0])} with {english(kids[1])}"
    if code == "if_then_else" and len(kids) == 3:
        return f"{english(kids[1])} if {english(kids[0])}, otherwise {english(kids[2])}"
    if code == "sign_extend" and kids:
        return f"{english(kids[0])} widened, keeping its sign"
    if code == "zero_extend" and kids:
        return f"{english(kids[0])} widened, filling with zeros"
    if code == "subreg" and kids:
        return f"part of {english(kids[0])}"
    if code == "mem" and kids:
        return f"the memory at {english(kids[0])}"
    if code == "clobber" and kids:
        return f"{english(kids[0])} gets destroyed"
    if code == "use" and kids:
        return f"{english(kids[0])} is still needed here"
    if code == VECTOR:
        return "; ".join(english(k) for k in kids) if kids else "an empty list"
    if code == "parallel" and kids:
        return "all at once: " + "; ".join(english(k) for k in kids)
    if code == "debug_marker":
        return "a source position for the debugger, and nothing else"
    if code == "var_location" and kids:
        where = english(kids[0])
        name = node.leaves[0] if node.leaves else "a variable"
        return f"{name} is living in {where} from here on"
    if not kids:
        return CODES.get(code, code)
    return f"{CODES.get(code, code)}: " + ", ".join(english(k) for k in kids)


def mode_note(mode: str) -> str:
    """What a mode is, including the condition code modes, which are not in the table."""
    if not mode:
        return ""
    if mode in MODES:
        return MODES[mode][1]
    if mode.startswith("CC"):
        tail = mode[2:]
        which = f", the {tail} part of it" if tail else ""
        return f"a condition code{which}, not a value you can add to anything"
    return "a mode this widget has no note for"


def one_line(node: Rtx | str, width: int = 62) -> str:
    text = str(node)
    return text if len(text) <= width else text[: width - 1] + "…"


class RTXTree(Widget):
    kind = "rtxtree"
    title = "One insn, opened up"
    defaults = {"at": "", "kind": "all"}

    def __init__(self, listing: Listing, limit: int = LIMIT, **kw: str) -> None:
        self.listing = listing
        self.insns = listing.insns[:limit]
        self.limit = limit
        super().__init__(**kw)
        if not self.view["at"] and self.insns:
            self.view["at"] = str((self.shown or self.insns)[0].uid)

    @property
    def shown(self) -> list[Insn]:
        if self.view["kind"] == "all":
            return self.insns
        return [i for i in self.insns if kind_of(i) == self.view["kind"]]

    @property
    def selected(self) -> Insn | None:
        wanted = self.view["at"]
        for insn in self.insns:
            if str(insn.uid) == wanted:
                return insn
        return self.shown[0] if self.shown else None

    def data(self) -> dict:
        return {
            "insns": [{"uid": i.uid, "kind": kind_of(i)} for i in self.insns],
            "total": len(self.listing),
        }

    # Rendering

    def body(self) -> str:
        if not self.insns:
            return el("p", "Nothing to open up. This listing has no insns in it.")
        return join(
            [
                self._summary(),
                self._controls(),
                self._list(),
                join([self._panel(i) for i in self.insns]),
                self._legend(),
                self._noscript(),
            ]
        )

    def _summary(self) -> str:
        code = len([i for i in self.insns if kind_of(i) == "code"])
        parts = [
            f"{self.listing.function}, first {len(self.insns)} of {len(self.listing)} entries",
            f"{code} of those become instructions",
            f"{len(self.listing.code)} in the whole function",
        ]
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _controls(self) -> str:
        buttons = [
            el(
                "button",
                esc(value),
                type="button",
                data_filter="kind",
                data_value=value,
                aria_pressed="true" if self.view["kind"] == value else "false",
            )
            for value in ("all", "code", "debug", "other")
        ]
        return el(
            "div",
            join(buttons, " "),
            class_="gx-controls",
            role="group",
            aria_label="Which entries to show",
        )

    def _list(self) -> str:
        at = self.selected
        rows = [
            el(
                "button",
                join(
                    [
                        el("span", str(i.uid), class_="gx-rung-no"),
                        el("code", esc(i.code), class_="gx-insn-code"),
                        el(
                            "code",
                            esc(one_line(i.pattern) if i.pattern else ""),
                            class_="gx-insn-p",
                        ),
                    ]
                ),
                type="button",
                class_="gx-insn",
                role="tab",
                data_cell=str(i.uid),
                data_panel=str(i.uid),
                data_kind=kind_of(i),
                aria_current="true" if at is not None and i.uid == at.uid else None,
                tabindex=0 if at is not None and i.uid == at.uid else -1,
                aria_label=self._label(i),
            )
            for i in self.shown
        ]
        if not rows:
            return el("p", "No entry matches this filter.", class_="gx-note")
        return el(
            "div",
            join(rows),
            class_="gx-insns",
            role="tablist",
            data_select="at",
            aria_label="Insns in chain order",
        )

    def _label(self, insn: Insn) -> str:
        return f"{insn.code} {insn.uid}, {KINDS[kind_of(insn)]}. {self._reading(insn)}"

    @staticmethod
    def _reading(insn: Insn) -> str:
        return english(insn.pattern) if insn.pattern else "No pattern."

    def _panel(self, insn: Insn) -> str:
        at = self.selected
        blocks = [self._header(insn), self._reading_line(insn)]
        if insn.pattern is not None:
            blocks.append(self._tree(insn.pattern))
        else:
            blocks.append(
                el(
                    "p",
                    esc(
                        "No pattern. This entry is a marker in the chain rather than something "
                        "that becomes an instruction."
                    ),
                    class_="gx-note",
                )
            )
        blocks.append(el("pre", esc(insn.raw), class_="gx-mono"))
        return el(
            "div",
            join(blocks),
            class_="gx-panel",
            role="tabpanel",
            data_panel=str(insn.uid),
            hidden=not (at is not None and at.uid == insn.uid),
        )

    def _header(self, insn: Insn) -> str:
        """The four numbers in front of the pattern, named, because nothing else names them."""
        facts = [
            (insn.code, "what kind of entry this is"),
            (str(insn.uid), "its uid, which never gets reused"),
            (str(insn.prev), "the uid before it"),
            (str(insn.next), "the uid after it, 0 for the last one"),
            (str(insn.bb) if insn.bb is not None else "none", "the block it is in"),
            (insn.loc or "none", "where in the source it came from"),
            (self._icode(insn), "the machine description pattern"),
        ]
        rows = [el("li", join([el("code", esc(v)), el("span", esc(w))], " ")) for v, w in facts]
        return el("ul", join(rows), class_="gx-facts", aria_label="The insn header, field by field")

    @staticmethod
    def _icode(insn: Insn) -> str:
        if insn.icode is None:
            return "none"
        if insn.icode == UNRECOGNISED:
            return "-1, nothing has matched it yet"
        return f"{insn.icode}, {insn.name}" if insn.name else str(insn.icode)

    def _reading_line(self, insn: Insn) -> str:
        return el("p", esc(self._reading(insn)), class_="gx-reading")

    def _tree(self, node: Rtx, depth: int = 0) -> str:
        """The pattern as a nested list, one row per node, three columns each."""
        head = el(
            "div",
            join(
                [
                    el("code", esc(node.head), class_="gx-rtx-head"),
                    el("span", esc(mode_note(node.mode)), class_="gx-rtx-mode"),
                    el("span", esc(CODES.get(node.code, "")), class_="gx-rtx-what"),
                ]
            ),
            class_="gx-rtx-row",
        )
        items = [el("li", self._leaf(node, text)) for text in node.leaves]
        items += [el("li", self._tree(kid, depth + 1)) for kid in node.children]
        inner = el("ul", join(items), class_="gx-rtx-kids") if items else ""
        flags = join(
            [
                el("span", esc(f"/{f} {FLAGS[f]}"), class_="gx-rtx-flag")
                for f in node.flags
                if f in FLAGS
            ],
            " ",
        )
        return join([head, el("p", flags, class_="gx-rtx-flags") if flags else "", inner])

    @staticmethod
    def _leaf(parent: Rtx, text: str) -> str:
        note = ""
        if parent.code == "reg" and text.isdigit():
            note = "a number the target chose" if not parent.pseudo else "invented by the expander"
        return el(
            "div",
            join([el("code", esc(text), class_="gx-rtx-leaf"), el("span", esc(note))], " "),
            class_="gx-rtx-row",
        )

    def _legend(self) -> str:
        return join(
            [
                legend(
                    [
                        ("(", "gx-neutral", "a node, which has a code, a mode and operands"),
                        ("1", "gx-constant", "a leaf, which is a number or a name and not a node"),
                    ]
                ),
                el(
                    "p",
                    esc(
                        "The reading is generated from the tree and covers the codes a small "
                        "function produces. A code it has no wording for is named and left "
                        "alone, which happens more often the further down the pipeline you go."
                    ),
                    class_="gx-note",
                ),
            ]
        )

    def _noscript(self) -> str:
        lines = [self._label(i) for i in self.insns]
        return el(
            "noscript",
            el(
                "details",
                join(
                    [
                        el("summary", "Every insn read out"),
                        el("pre", esc("\n".join(lines)), class_="gx-mono"),
                    ]
                ),
            ),
        )
