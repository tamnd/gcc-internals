"""F01. The driver is an interpreter.

The first lesson of Part II, and a deliberate step back before the front end proper. T01
showed what `gcc` runs. This shows the language that decision is written in, which is a real
programming language with conditionals, function calls and a call graph, stored in strings,
printed by `gcc -dumpspecs`, and interpreted by nine hundred lines of C in `gcc/gcc.cc`.

Everything runs out of `corpora/specs/f01.json`, which has two whole spec tables in it and
four pairs of `-###` runs that differ by one text file. The overrides are the part that makes
the lesson stick: a reader who has watched `%{!S:` come off a string and seen `gcc -S` start
running the assembler will never again think of `-S` as a feature.

The reader is expected to have done T01. This lesson does not re-explain `-###`.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "f01-the-spec-language",
    "f01",
    title="The driver is an interpreter",
    milestone="M3",
    summary=(
        "That `gcc -dumpspecs` prints a program, in a language with conditionals and function "
        "calls, which the driver interprets to decide what to run; how to read it; and four "
        "text files that change what your compiler does without patching or rebuilding it"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# F01. The driver is an interpreter

{badge}

T01 ended with a chain of programs and a promise that a {term("spec", "spec string")} decided
it. This lesson is that promise paid.

Here is the thing to hold on to. The {term("driver")} does not contain code that says "if the
user passed `-S`, do not run the assembler". It contains a string, and the string contains
`%{{!S:...}}`, and there is an interpreter that reads that string at run time. The decision
about which programs to run is data. You can print it, you can read it, and with one text file
and no compiler you can change it.

`gcc -dumpspecs` prints the whole program. On the machine this lesson was recorded on it is
fifty six named blocks and under nine thousand characters, all of it in one small language
that nobody documents outside a comment in the driver's own source.

You need a browser. Everything below runs on two recorded spec tables and eight recorded
`-###` runs, so you see what the lesson saw.

**What you come away with**

- Knowing that the driver's behaviour is a program in a string language, and where to print it
- Being able to read a spec: the five families of `%` form, and where an argument ends
- Being able to follow the call graph, which is what turns fifty six strings into a system
- Knowing what a {term("compiler table")} is, and why a file suffix is not the same as a language
- Being able to write a {term("specs file")} that changes what your compiler runs
- Knowing where the interpreter is, so the next surprise is a thing you can go and read
""")

lesson.setup()

lesson.md(f"""
## The program

`gxray.specs` reads `-dumpspecs` output. It is a reader and not a second interpreter: it says
what each form is and what it is for, and it never substitutes anything, because substituting
would need your command line, your target, your filesystem and a temporary directory.

Two tables are recorded. This one is the pinned GCC 16.2.0 on aarch64 macOS.
{claim("gcc -dumpspecs prints tens of named blocks totalling thousands of characters")}.
""")

lesson.code("""
from gxray import specs

rec = specs.load("f01")
table = rec.table("local")

print(f"recorded {rec.recorded}")
print(f"{rec.compiler} for {rec.target}")
print()
print(f"{len(table)} named blocks")
print(f"{sum(len(one) for one in table)} characters of spec language")
""")

lesson.md("""
Now the output itself, the first fourteen lines of it, exactly as the driver printed them.
""")

lesson.code("""
for line in table.text.splitlines()[:14]:
    print(line)
""")

lesson.md(f"""
That is the entire file format. A name between a star and a colon at the start of a line, then
the value on the lines after it until the next name. The value is one string with newlines in
it, and the newlines are part of the language rather than decoration.

The first block, `*asm`, is what gets passed to the assembler. The second, `*asm_debug`, is
empty, and about a third of the table is. An empty spec is not a missing one: it is a hook
this target does not need, and the driver expands it to nothing.

Here are all the names.
""")

lesson.code("""
names = table.names
for start in range(0, len(names), 4):
    print("".join(f"{name:<24}" for name in names[start : start + 4]).rstrip())
""")

lesson.md(f"""
Read down that list and the shape of the toolchain is in it: `cpp_options`, `cc1`,
`cc1_options`, `invoke_as`, `asm_options`, `link`, `lib`, `startfile`, `endfile`. Those are the
stages, and the strings under them are how each stage's command line gets built.

One name is in that grid twice. Nothing complains about that, because a spec table is a list
and not a map: a second definition of a name is appended, and lookups take the last one. Here
both copies are empty so it makes no difference, but the mechanism is the one that matters,
because it is also how a {term("specs file")} replaces a built in spec later in this lesson.
{claim("a name can appear twice in the dump and lookups take the last definition")}.
""")

lesson.code("""
print("defined more than once:", table.duplicates)
print()
for one in table:
    if one.name in table.duplicates:
        print(f"{one.name} defined as {one.value!r}")
print()
print("lookup gives the last:", repr(table["darwin_crt2"].value))
""")

lesson.md(f"""
## Five kinds of thing

A spec is text with `%` forms in it. There are forty five of them in GCC 16, which sounds like
a lot until you see that they fall into five families and you only ever need to recognise which
family you are looking at.
{claim("every percent form in the spec language belongs to one of five families")}.
""")

lesson.code("""
groups = {}
for character, form in specs.FORMS.items():
    groups.setdefault(form.family, []).append("%" + character)

print(f"{'family':<10}{'n':>3}  what it does")
for family, forms in groups.items():
    print(f"{family:<10}{len(forms):>3}  {specs.FAMILIES[family]}")
    print(f"{'':<15}{' '.join(forms)}")
""")

lesson.md(f"""
Plus two compound forms that are not letters at all. `%{{...}}` is a conditional and `%:name()`
is a call to a C function, and between them they are most of what makes a spec hard to read.

Here is the whole table again, counted by what is in it rather than by name.
{claim("conditionals are the second most common thing in a spec table, after plain text")}.
""")

lesson.code("""
from collections import Counter

kinds = Counter()
for one in table:
    kinds.update(one.counts())

for kind, count in kinds.most_common():
    print(f"{kind:<10}{count:>5}  {specs.FAMILIES[kind]}")
""")

lesson.md(f"""
Two hundred and forty nine conditionals. That is the real answer to why the driver's behaviour
is so hard to predict from the outside: it is not a few special cases, it is a table of strings
that is mostly branches.

## Where an argument ends

Before reading a real spec there is one thing to get straight, because getting it wrong is how
a spec turns into line noise. Whitespace is not formatting.
{claim("a space in a spec is an instruction to end the current argument, not punctuation")}.
""")

lesson.code("""
snippet = table["asm_final"].value
print(repr(snippet))
print()
for token in specs.tokenize(snippet):
    shown = str(token)
    print(f"{token.kind:<9}{shown[:30]:<32}{token.about}")
""")

lesson.md(f"""
Three tokens. A conditional that prints a notice and gives up, six characters of whitespace
that end an argument, and a `%<` that deletes a switch from the command line the driver is
building. The driver's own reading of that is at {cite("gcc/gcc.cc:6223@releases/gcc-16.2.0")},
and it is worth knowing that a space is a `case` in a `switch` statement rather than a
separator that gets skipped.

The other half of the problem is that some forms swallow the characters after them. `%|.s` is
one token, not a token and the text `.s`, because `%|` takes a suffix. Reading `%|` and then
wondering what `.s` is doing there is the single most common way to misread a spec.
""")

lesson.code("""
for form in ("|", "g", "e", "<", "W"):
    known = specs.FORMS[form]
    print(f"%{form}   operand: {known.operand:<8}{known.about}")
""")

lesson.md(f"""
## Reading one spec

`invoke_as` is the spec that decides whether the assembler runs. It is four lines of the dump
and it is the spine of this lesson, so here it is one token per line with what each token
means. Nothing is substituted, because nothing can be without a command line.
""")

lesson.code("""
print(table["invoke_as"].value)
print()
print(specs.explain(table["invoke_as"].value))
""")

lesson.md(f"""
Read it from the top. Unless `-fwpa` was given, and then a piece of link time optimization
bookkeeping, and then: **unless `-S` was given**, write the output to a temporary file, pipe it,
and run `as` on it.

That is the whole of `-S`. Not a branch in the driver's C, not a flag the compiler proper knows
about. A negated condition in a string, guarding the part that names the assembler.
{claim("gcc -S stops before the assembler because of a %{!S:...} in the invoke_as spec")}.
""")

lesson.code("""
guard = next(
    token
    for token in specs.walk(table["invoke_as"].value)
    if token.kind == "brace" and token.head == "!S"
)

print("condition:", repr(guard.head), specs.predicate(guard.head))
print("guarding:")
print(specs.explain(guard.body))
""")

lesson.md(f"""
The last section of this lesson takes that guard off and watches what happens.

## The call graph

A spec can run another spec. `%(name)` does it by name, and ten of the letter forms do it by
letter, so `%L` and `%(lib)` are the same edge written two ways. Follow those edges and the
fifty six unrelated strings turn into a graph.

Compiling a C file starts at four specs, which is what the compiler table says to run for a
`.c` file. Everything reachable from there is what your compiler consults to build the command
lines for one `gcc -c hello.c`.
{claim("compiling one C file reaches about a dozen specs, and every name they call is defined")}.
""")

lesson.code("""
roots = ["trad_capable_cpp", "cpp_options", "cc1_options", "invoke_as"]
reached = table.reach(*roots)

print(f"{len(reached)} specs are consulted for one C file:")
for name in reached:
    who = table.callers(name)
    print(f"  {name:<22}{'called by ' + ', '.join(who) if who else 'a starting point'}")

print()
print("names called but never defined:", table.dangling(*roots) or "none")
""")

lesson.md(f"""
No dangling names, which has to be true: a spec that called something undefined would fail on
the first file the compiler was handed, and the check costs nothing to run.

The other direction is more useful in practice. When an argument turns up in a command line and
you want to know who put it there, ask which specs call the one it came from.

## The compiler table

Everything so far has been the spec list. There is a second table, and it is the one that
answers the question the spec list cannot: given a file called `hello.c`, which spec do you
start at?
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("f01")
row = cuts["struct"]

print(f"{row.span}  ({row.citation})")
print(row.about)
print()
print(row.numbered())
""")

lesson.md(f"""
A suffix, a spec, and three flags. The array of these is `default_compilers`, and the row for a
C file is three lines long.
""")

lesson.code("""
print(cuts["c-suffix"].numbered())
""")

lesson.md(f"""
The spec for `.c` is the two character string `@c`. That is not a spec at all, it is the name
of another row, and the indirection is the point: the suffix decides the language, and the
language decides the commands. Change the suffix table and a `.cpp` file compiles as C. Change
the language row and every C file in the world compiles differently.

Here is the `@c` row, which is the real one.
""")

lesson.code("""
print(cuts["c-spec"].numbered())
""")

lesson.md(f"""
That is a C string literal split over thirteen lines with backslashes, which is not a shape
anybody can read. It is the same language as everything above, so it can be put back together
and read the same way.
{claim("the spec that compiles a C file is one string of about five hundred characters")}.
""")

lesson.code("""
at_c = specs.from_c_literal(cuts["c-spec"].text)

print(f"{len(at_c)} characters, {at_c.count(chr(10)) + 1} lines")
print()
print(specs.explain(at_c, depth=1))
""")

lesson.md(f"""
Two top level branches. The first is `%{{E|M|MM:`, which is `-E` and the two dependency
generating flags, and the second is `%{{!E:`, which is everything else. Between them they cover
every way of compiling a C file, and the second one holds nine tenths of the characters.

Nested one level deeper is where the work is.
""")

lesson.code("""
print(specs.explain(at_c, depth=3))
""")

lesson.md(f"""
`%eGNU C no longer supports -traditional without -E` is a diagnostic, written in the spec
language, that a reader will have seen if they ever passed `-traditional` to a C compiler. The
error message you got came out of a string in a table, not out of the compiler.

The names it calls are the roots the call graph section started from.
""")

lesson.code("""
print(specs.Spec("@c", at_c).calls)
""")

lesson.md(f"""
The suffixes and the language rows, counted in the pinned tree when this lesson was recorded.
{claim("the driver knows dozens of file suffixes and five of them are the ones it compiles as C")}.
""")

lesson.code("""
built = rec.builtin

print(f"{len(built.suffixes)} suffixes:")
for start in range(0, len(built.suffixes), 11):
    print("  " + " ".join(f"{s:<6}" for s in built.suffixes[start : start + 11]).rstrip())
print()
print(f"{len(built.languages)} language rows: {', '.join(built.languages)}")
""")

lesson.md(f"""
Most of those suffixes belong to languages this compiler may not even have installed. A `.f90`
row exists whether or not there is a Fortran front end, because the table is compiled into the
driver and the driver is the same program for every language.

The lookup is at {cite("gcc/gcc.cc:9398@releases/gcc-16.2.0")} and it has one property worth
remembering.
""")

lesson.code("""
print(cuts["lookup"].numbered())
""")

lesson.md(f"""
Both loops run backwards. That is not an optimization, it is a policy: rows added later win,
and rows added later are the ones a `-specs=` file added. Hold on to that for the last section.

## The escape hatch

Substitution cannot answer every question. Whether a file exists, whether one version number is
greater than another, what the target's CPU is called: none of that is expressible as text
replacement, so the language has a {term("spec function")}, which is a call into C.
{claim("a spec may call a named C function, and GCC 16 has twenty one of them built in")}.
""")

lesson.code("""
print(f"{len(built.functions)} spec functions:")
for start in range(0, len(built.functions), 3):
    print("  " + "".join(f"{f:<26}" for f in built.functions[start : start + 3]).rstrip())
""")

lesson.md(f"""
The list is at {cite("gcc/gcc.cc:1806@releases/gcc-16.2.0")} and it is a pair per line, a name
and a C function. Which is the exact boundary between what the little language can do and what
it has to ask C for, written down in one place.

It is not the whole list, though, and the last three lines of that array say why.
""")

lesson.code("""
print(cuts["functions"].numbered())
""")

lesson.md(f"""
`EXTRA_SPEC_FUNCTIONS` is a macro a {term("port")} defines, and a port that defines it gets its
own spec functions spliced into the array. So the twenty one are a floor rather than a total,
and both of the compilers recorded here call something that is not in it.
{claim("a target can register spec functions of its own, and both recorded targets do")}.
""")

lesson.code("""
for label in ("local", "elsewhere"):
    one = rec.table(label)
    called = sorted({name for spec in one for name in spec.functions})
    theirs = [name for name in called if name not in built.functions]
    print(f"{label} ({one.target})")
    print(f"  calls {len(called)}: {', '.join(called)}")
    print(f"  not in gcc.cc: {', '.join(theirs) or 'none'}")
""")

lesson.md(f"""
`rewrite_mcpu` is aarch64's, and it exists because `-mcpu=native` has to become a real CPU name
before anything downstream can use it. `local_cpu_detect` is x86's and does the same job. Both
are one line in a port's header file, and both are invisible unless you go looking at the spec
that calls them.

## The one that is not a spec

`-dumpspecs` prints a block called `*link_command`, and it is not in the spec list. It has a
variable of its own, a case of its own in the option handling, and a special case in the code
that reads a specs file.
{claim("link_command is printed by -dumpspecs but is not one of the driver's static specs")}.
""")

lesson.code("""
print("in the dump:      ", "link_command" in table)
print("in static_specs:  ", "link_command" in built.static_specs)
print()
print(cuts["dumpspecs"].numbered())
""")

lesson.md(f"""
The loop prints the spec list, and then one more line prints `link_command` from a variable
called `link_command_spec`. It is worth knowing about for the same reason any special case is:
the day you write a specs file that overrides it and it does not behave like the others, this
is why.

## Two targets, one release

Everything above is one installation. Here is `-dumpspecs` from the same GCC release built for
x86-64 Linux by other people, fetched through Compiler Explorer and recorded.
{claim("two builds of the same GCC release have different spec tables, and neither is wrong")}.
""")

lesson.code("""
elsewhere = rec.table("elsewhere")

print(f"{table.target:<26}{len(table)} blocks")
print(f"{elsewhere.target:<26}{len(elsewhere)} blocks")
print()
print("added on top of the built-in list:")
for label, one in (("local", table), ("elsewhere", elsewhere)):
    print(f"  {label:<12}{', '.join(built.added_by(one))}")
""")

lesson.md(f"""
Forty five of the names are the same everywhere, because they come from `static_specs` in
`gcc/gcc.cc` and every target starts from that list. The rest are the target's own. One of these
compilers added ten Darwin specs about which C runtime object file to link, and the other added
one, and that difference is most of why the two chains in T01 looked so different.

The same spec on both, side by side, is the clearest version of it.
""")

lesson.code("""
for label in ("local", "elsewhere"):
    one = rec.table(label)
    print(f"--- {label}: {one.target} ---")
    print(specs.explain(one["asm"].value, depth=2) or "(empty)")
    print()
""")

lesson.md(f"""
Two strings doing the same job for two instruction sets, in the same language, out of the same
release. Neither of them is a fact about GCC 16. Both are facts about a build of it.

## Changing what your compiler runs

Now the part that turns all of this from trivia into a tool. `-specs=file` reads more spec
definitions and applies them on top of the built-in ones. The format is the one `-dumpspecs`
prints, which means the output of `-dumpspecs` is valid input.

Four experiments follow. Each one is a pair of `-###` runs that differ by exactly one text
file, so whatever moved between them moved because of that file. Nothing was executed:
`-###` prints the chain and stops, which is the only reason it is safe to record one of these
with an assembler that does not exist.

The first one is the smallest useful thing a specs file can do.
{claim("a two line specs file adds an argument to every cc1 the driver runs")}.
""")

lesson.code("""
one = rec["argument"]

print(one.file_text)
print(one.command)
print()
before = set(one.chain_before.named("cc1").argv)
after = set(one.chain_after.named("cc1").argv)
print("cc1 gained:", sorted(after - before) or "nothing")
print("cc1 lost:  ", sorted(before - after) or "nothing")
""")

lesson.md(f"""
The `+` at the start of the value is what makes it an append rather than a replacement. Without
it, `*cc1:` followed by `-fverbose-asm` would replace the whole `cc1` spec with that one flag,
and the driver would try to run a program called `-fverbose-asm`.

Next, the name of the assembler.
{claim("editing one word in one spec makes the driver run a different program for the assembly step")}.
""")

lesson.code("""
one = rec["assembler"]

print(one.command)
print()
print(f"without the file:  {', '.join(one.chain_before.names)}")
print(f"with it:           {', '.join(one.chain_after.names)}")
""")

lesson.md(f"""
The specs file for that one is the local `invoke_as` with the word `as` replaced. That is all.
The assembler's name is not configuration, it is not a variable, it is a word in the middle of
a string, and a text file can change it.

Now the one worth remembering. The `%{{!S:` guard from earlier, deleted.
{claim("deleting the !S guard from invoke_as makes gcc -S run the assembler")}.
""")

lesson.code("""
one = rec["guard"]

print(one.file_text)
print(one.command)
print()
print(f"without the file:  {', '.join(one.chain_before.names)}")
print(f"with it:           {', '.join(one.chain_after.names)}")
""")

lesson.md(f"""
`gcc -S` assembled. The reader asked for assembly and got an object file, because `-S` was
never a feature of the compiler. It is a two character condition inside one string, and the
string is editable.

Note that this specs file was not typed out. It was built by finding the `%{{!S:...}}` token in
the local table with `specs.walk` and removing the wrapper, which is the kind of thing a reader
for the language is for.

Last one, and it uses the compiler table rather than the spec list.
{claim("a specs file whose name has no star adds a row to the compiler table, teaching gcc a new suffix")}.
""")

lesson.code("""
one = rec["suffix"]

print(one.file_text)
print(one.command)
print()
print("without the file:")
print("   ", one.before.strip().splitlines()[-1])
print("with it:")
print("   ", ", ".join(one.chain_after.names))
""")

lesson.md(f"""
A file called `l1.frob` that GCC refused to compile now compiles as C, because two lines of text
added a row to the table that maps suffixes to languages. The code that does it is in
`read_specs`, and it is one `if`.
""")

lesson.code("""
print(cuts["read-specs"].numbered())
""")

lesson.md(f"""
A name that starts with a star sets a spec. A name that does not gets a new row on the end of
`default_compilers`, with the text after it as the row's spec. That is why the lookup runs
backwards: the newest row is the first one tried, so a specs file can override `.c` itself.

The `*link_command` special case is visible in the same span, which is what the earlier section
was about.

## The interpreter

All of the above is one function. `do_spec_1` at {cite("gcc/gcc.cc:6174@releases/gcc-16.2.0")} is
a loop over the characters of a string and a `switch`.
""")

lesson.code("""
print(cuts["interpreter"].numbered())
""")

lesson.md(f"""
That is the whole thing. Nine hundred lines follow, and every one of them is a `case` in that
switch. `gxray.specs` knows about all of them: forty five letters, plus `%{{` and `%:`, and it
was written by reading the case labels in that function.

Which gives a check worth running. If a spec in either recorded table contained a form this
reader had never heard of, it would be reported rather than quietly displayed as text.
{claim("every percent form in both recorded spec tables is one this reader can name")}.
""")

lesson.code("""
for label in ("local", "elsewhere"):
    one = rec.table(label)
    unknown = one.unknown()
    print(f"{label:<12}{len(unknown)} unrecognised forms")
    for name, text in unknown:
        print(f"  {name}: {text}")
""")

lesson.md(f"""
The conditional is the one part with real grammar, and somebody had to write it down before
implementing it, which is the comment above `handle_braces`.
""")

lesson.code("""
print(cuts["braces"].numbered())
""")

lesson.md(f"""
`%{{S:X;T:Y;:D}}` is an if, else if, else, in six characters of punctuation. That is the form
that makes a spec table hard to read at a glance and is worth being able to spell.

And the definition of the whole language is a comment at
{cite("gcc/gcc.cc:473@releases/gcc-16.2.0")}, which is a fair summary of how documented this
corner of GCC is.
""")

lesson.code("""
print(cuts["language"].numbered())
""")

lesson.md(f"""
## Boss fight

No new tools. Three questions, answerable from the recording:

1. `cpp_options` is one of the four specs the compiler table consults for a C file. Which specs
   does it call?
2. Four specs files were tried above. Three of them changed which programs the driver ran, and
   one left the chain alone and changed only an argument. Which three moved the chain?
3. Eleven names in this table are not in the driver's built in `static_specs`, so something
   added them. Ten came from this target. One came from no target at all, and the way to find
   it is that the x86-64 table, which shares almost nothing else with this one, adds it too.
   Which name?

Then check yourself:

```text
python lessons/f01-the-spec-language/grade.py
```

or, from a checkout, `just grade f01-the-spec-language`. It takes answers on the command line
too, so `--calls one,two --changed a,b,c --odd some_name` is a whole submission. Every answer
it marks against is worked out from the recording rather than written down.

## What to read next

F02 is the preprocessor, which is the first program in that chain and the one whose output
`cc1` actually parses.

T01 is the lesson this one grew out of, if you have not done it. It shows the chain; this shows
why the chain is what it is.

B01 builds GCC from source. The `--with-specs` configure option and the `*self_spec` block in
the table above are how a distribution bakes its own defaults into a compiler, and after this
lesson that sentence means something.

If you have a GCC on your machine, the whole lesson runs live. `gcc -dumpspecs > mine.specs`,
then `specs.parse(open("mine.specs").read())` gives you a table of your own, and the four
experiments are four text files and four `-###` runs. Your table will not match this one. That
is the lesson.
""")

raise SystemExit(lesson.save())
