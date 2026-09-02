"""The one picture in T09 that is not read off a recorded run.

The notebook can print the annotation, the pattern, the alternative table and the sections,
because all of those are text somebody can parse. What it cannot print is the shape of the
arrangement: that the machine description sits to one side of the pipeline rather than in it,
that `final` reads it in the opposite direction from every pass before it, and that the file
GCC writes is still three programs away from being something you can run.

    python lessons/t09-the-last-mile/diagram.py

It writes `diagrams/the-last-mile.excalidraw`, which you can open at excalidraw.com and edit.
If you do edit it, change this file too, because the next run overwrites it.
"""

from __future__ import annotations

from pathlib import Path

from tools import exdraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagrams" / "the-last-mile.excalidraw"

#: The annotation, pulled apart. Copied off line 28 of the recorded `t09-final` listing rather
#: than invented, so every field in it is a field a reader will actually see.
ANNOTATION = """\
        add     w0, w0, w1      // 12   [c=4 l=4]  *addsi3_aarch64/1
                                   |      |   |     |               |
                                   |      |   |     |               which row of the table
                                   |      |   |     which define_insn emitted it
                                   |      |   how many bytes it should assemble to
                                   |      what the cost model thought it was worth
                                   the uid of the RTL insn, also in the .final dump"""

#: The insn side of the join, verbatim out of the `.final` dump of the same compilation. The
#: 155 is the insn code, which is the index into the generated insn_data table.
INSN = """\
(insn:TI 12 11 13
  (set (reg/v:SI 0 x0 [orig:102 <retval> ] [102])
       (plus:SI (reg/v:SI 0 x0 [orig:102 <retval> ] [102])
                (reg/v:SI 1 x1 [orig:101 i ] [101])))
  "l1.c":7:7 155 {*addsi3_aarch64})"""

#: The pattern side, cut down to the two rows that matter. The full table has eight rows and
#: the lesson prints all of them.
PATTERN = """\
gcc/config/aarch64/aarch64.md:2694

(define_insn "*add<mode>3_aarch64"
  [(set (match_operand:GPI 0 "register_operand")
        (plus:GPI (match_operand:GPI 1 "register_operand")
                  (match_operand:GPI 2 "aarch64_pluslong_operand")))]
  ""
  {@ [ cons: =0 , %1 , 2 ; attrs: type , arch ]
     [ rk , rk , I ; alu_imm  , * ] add\\t%<w>0, %<w>1, %2
     [ rk , rk , r ; alu_sreg , * ] add\\t%<w>0, %<w>1, %<w>2     <- row 1
     ...six more rows...
  })"""

#: The three shapes an output template can take, which is `get_insn_template` written out.
FORMS = """\
get_insn_template, gcc/final.cc:2024

  SINGLE    one string                  ->  print it
  MULTI     one string per alternative  ->  print output.multi[which_alternative]
  FUNCTION  a C function                ->  call it, print what it returns

  A pattern with a MULTI table is the only one whose annotation gets a slash,
  because n_alternatives > 1 is the condition output_asm_name tests."""

#: What is left after `final` has run, and who deals with each part of it. The point of the
#: panel is that the instructions are the small half.
FILE = """\
l1.s, 46 lines

  12  instructions      the assembler encodes these
  14  directives        the assembler acts on these
   5  labels            the assembler records the addresses
  14  comments          the assembler throws these away
   1  blank             the same"""

#: The three programs after GCC. Deliberately short: each one is somebody else's book.
AFTER = """\
what happens to it next

  as       text  ->  object file    encodes, builds the section and symbol tables,
                                    turns unknown addresses into relocations
  ld       .o    ->  executable     resolves the relocations, lays out the sections
  loader   file  ->  process        maps the sections, sets the permissions

  GCC stops at the first arrow because everything past it is the same for
  every language that can produce an object file."""


def build() -> exdraw.Scene:
    scene = exdraw.Scene("the last mile")

    scene.note(40, 0, "The last mile", size=20)
    scene.note(
        40,
        40,
        "Register allocation was the last pass that decided anything. What is left is an insn "
        "chain full of real\nregisters and a table that says how to print each kind of insn. "
        "This is the printing.",
        size=16,
        colour=exdraw.GREY,
    )

    scene.note(40, 120, "1. One insn, one pattern, one line of text", size=18)
    insn = scene.box(40, 170, 700, 170, INSN, fill=exdraw.BLUE, size=13, font=exdraw.CODE)
    pattern = scene.box(880, 170, 780, 300, PATTERN, fill=exdraw.YELLOW, size=13, font=exdraw.CODE)
    text = scene.box(
        40,
        400,
        700,
        70,
        "        add     w0, w0, w1",
        fill=exdraw.GREEN,
        size=13,
        font=exdraw.CODE,
    )
    scene.arrow(insn, pattern, "insn code 155 picks the pattern", colour=exdraw.GREY)
    scene.arrow(pattern, text, "row 1 of the table is the template", colour=exdraw.GREY, bend=1)
    scene.arrow(insn, text, "final walks the chain", colour=exdraw.GREY)

    scene.note(40, 530, "2. And it tells you it did", size=18)
    scene.box(40, 580, 1200, 210, ANNOTATION, fill=exdraw.PLAIN, size=13, font=exdraw.CODE)
    scene.note(
        1300,
        580,
        "`-dp` is what makes any of this checkable.\n"
        "Without it the assembly is just assembly and\n"
        "the link back to the machine description is\n"
        "something you have to guess at.\n"
        "\n"
        "The uid is the useful field, because the same\n"
        "number is in the .final RTL dump. Everything\n"
        "else in the annotation is a convenience.",
        size=15,
    )

    scene.note(40, 850, "3. The machine description is read the other way round here", size=18)
    scene.note(
        40,
        890,
        "Every pass before this one uses the description to ask does this pattern match my RTL. "
        "`final` uses it to\nask what does this pattern print. Same file, and the second question "
        "is the one that can run C.",
        size=16,
        colour=exdraw.GREY,
    )
    scene.box(40, 970, 900, 200, FORMS, fill=exdraw.YELLOW, size=13, font=exdraw.CODE)
    scene.note(
        1000,
        970,
        "The FUNCTION form is the one worth remembering.\n"
        "`*do_return` decides between `ret` and `retaa` by\n"
        "calling a C function at compile time, which means\n"
        "no pass earlier in the pipeline knows which\n"
        "instruction is going to come out.\n"
        "\n"
        "That is also why it prints no slash. There is no\n"
        "table, so there is no row number to print.",
        size=15,
    )

    scene.note(40, 1230, "4. What comes out, and what it is not", size=18)
    written = scene.box(40, 1280, 620, 200, FILE, fill=exdraw.GREEN, size=13, font=exdraw.CODE)
    after = scene.box(760, 1280, 1080, 220, AFTER, fill=exdraw.RED, size=13, font=exdraw.CODE)
    scene.arrow(written, after, "text, not machine code", colour=exdraw.GREY)

    scene.note(
        40,
        1540,
        "The twelve instructions are the part everybody looks at and they are a quarter of the "
        "file. The other thirty\nfour lines are what makes the object file usable: which section "
        "each thing goes in, how much space it needs,\nwhat it is called, who else may see it, "
        "and how to unwind through it. None of that came from the optimizer.",
        size=15,
        colour=exdraw.GREY,
    )

    return scene


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build().document(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
