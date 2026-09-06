"""F02. The preprocessor is not a text editor.

The second lesson of Part II, and the first one about a phase of the compiler proper. F01
showed the driver deciding which programs to run. This is the first of those programs.

The lesson has one idea and spends twenty sections earning it: `gcc -E` reads tokens, works
on tokens, and prints tokens, and printing them is lossy. The single most convincing piece of
evidence is a space. `a+EMPTY+b` comes out as `a+ +b`, and there is no input file anywhere
with that space in it. Text substitution cannot produce a character that is in none of its
inputs, so whatever the preprocessor is doing, it is not text substitution.

Everything runs out of `corpora/cpp/f02.json`: five macro tables, six expansions, thirty
eight probed token pairs and four include traces, half of them recorded on x86-64 Linux
through Compiler Explorer. The source spans are in `corpora/source/f02.json`, so a reader who
cloned shallow and has no `vendor/gcc` sees the same libcpp code as everybody else.

The reader is expected to have done T01 and F01. This lesson does not re-explain the chain.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "f02-tokens-not-text",
    "f02",
    title="The preprocessor is not a text editor",
    milestone="M3",
    summary=(
        "That the preprocessor lexes your file into tokens before it does anything else, and "
        "that its printed output is a rendering of those tokens rather than the tokens "
        "themselves; the space GCC inserts that is in no input file; the four hundred macros "
        "you did not write; and why one #include of stdio.h opens thirty eight files"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# F02. The preprocessor is not a text editor

{badge}

Almost everybody carries the same model of the C {term("preprocessor")}: it is a text editor
that runs before the compiler. It pastes headers in, it replaces macro names with their
bodies, and what comes out is a bigger text file.

That model is wrong in a way you can measure in one line. This lesson measures it, and then
spends the rest of its length on what the right model buys you.

Here is the measurement, which will not make sense yet and is the whole lesson in three lines.

```text
#define EMPTY
a+EMPTY+b
```

comes out as `a+ +b`. There is a space in that output. There is no space in the input. There
is no space in `EMPTY`, because `EMPTY` is defined to nothing at all. No amount of substituting
text into text produces a character that is in none of the text.

You need a browser. Everything below runs on a recording, so you see what the lesson saw, on
two targets at once.

**What you come away with**

- Knowing that the preprocessor works in {term("token", "tokens")} and that its output is a
  rendering of them, not the thing itself
- Being able to read a {term("line marker")}, including the digits after the filename
- Knowing why `#define CAT(a, b) a ## b` cannot make `++` out of two `+` macros
- Knowing what {term("blue paint")} is and why `#define foo foo + 1` does not hang
- Being able to say how many macros your compiler defines before it reads a line, and what
  moves that number
- Knowing what an {term("include guard")} has to look like for GCC to skip the file
- Knowing where libcpp is, so the next surprise is a thing you can go and read
""")

lesson.setup()

lesson.md(f"""
## The table you did not write

Start somewhere unarguable. This is a file with one comment in it, compiled with no flags, and
the list of macros that were defined before the compiler read the comment.
{claim("a C compiler defines hundreds of macros before it reads a line of your program")}.
""")

lesson.code("""
from gxray import cpp

rec = cpp.load("f02")
local = rec.macros("local")

print(f"recorded {rec.recorded}")
print(f"{rec.compiler} for {rec.target}")
print()
print(local)
print(f"{len(local.function_like)} of them take arguments")
print(f"{len(local.empty)} are defined to nothing, which is not the same as not defined")
""")

lesson.md("""
Four hundred and forty three. Here are four families of them, with one member of each written
out, so that the range of what is in there is visible.
""")

lesson.code("""
for prefix, one in (
    ("__STDC", "__STDC_VERSION__"),
    ("__SIZEOF", "__SIZEOF_INT__"),
    ("__GCC_ATOMIC", "__GCC_ATOMIC_INT_LOCK_FREE"),
    ("__FLT_", "__FLT_MAX__"),
):
    names = local.starting(prefix)
    print(f"{prefix + '*':<16}{len(names):>3} of them, such as {local[one]}")
""")

lesson.md(f"""
Those are four different kinds of promise. `__STDC_VERSION__` is the language standard.
`__SIZEOF_INT__` is the machine. `__GCC_ATOMIC_INT_LOCK_FREE` is what the hardware can do
without a library call. `__FLT_MAX__` is a number nobody can write down from memory, which is
the point: `float.h` is mostly a file of `#define FLT_MAX __FLT_MAX__` lines, forwarding to
values the compiler computed.

## The same release, twice

The recording has a second table in it, from the same GCC 16.2.0 built for x86-64 Linux by
other people. Not a different version. The same release.
{claim("two builds of one GCC release define different numbers of macros, and neither is wrong")}.
""")

lesson.code("""
elsewhere = rec.macros("elsewhere")

print(f"{local.target:<28}{len(local)} macros")
print(f"{elsewhere.target:<28}{len(elsewhere)} macros")
print()
print(f"{len(local.shared(elsewhere))} names are on both")
print(f"{len(local.only_in(elsewhere))} are only here")
print(f"{len(elsewhere.only_in(local))} are only there")
""")

lesson.md("""
The names that exist on one side and not the other are the ones `#ifdef` can see, and they are
the easy half. Here they are.
""")

lesson.code("""
for label, names in (("here", local.only_in(elsewhere)), ("there", elsewhere.only_in(local))):
    print(f"--- only {label} ({len(names)}) ---")
    for start in range(0, min(len(names), 24), 3):
        print("  " + "".join(f"{n:<30}" for n in names[start : start + 3]).rstrip())
    print()
""")

lesson.md(f"""
The hard half is the other set: names that are defined on both, to different values. Those are
invisible to `#ifdef` and visible only to arithmetic, which is where portability bugs live.
{claim("the same C type is a different width on two builds of one compiler release")}.
""")

lesson.code("""
differ = local.differing(elsewhere)
print(f"{len(differ)} names are defined on both to different values. Some of them:")
print()
for name in (
    "__SIZEOF_LONG_DOUBLE__",
    "__LDBL_MANT_DIG__",
    "__INT_FAST16_TYPE__",
    "__WINT_TYPE__",
    "__USER_LABEL_PREFIX__",
):
    print(f"  {name:<26}{local[name].body!r:<26}{elsewhere[name].body!r}")
""")

lesson.md("""
A `long double` is eight bytes here and sixteen bytes there, with fifty three bits of mantissa
against sixty four. `int_fast16_t` is a `short` here and a `long` there, which is four times
the width. `wint_t` is signed here and unsigned there, so the same comparison against `-1` is
true on one machine and false on the other. And `__USER_LABEL_PREFIX__` is an underscore here
and nothing there, which is why a symbol name in inline assembly is not portable.

Same C, same standard, same compiler release. Every one of those is a fact about a machine
that got written into a macro before your file was read.

## What moves the table

Flags change it, and not the flags a reader expects. Start with the one everybody reaches for.
""")

lesson.code("""
optimized = rec.macros("optimized")

print(f"no flags   {len(local)} macros")
print(f"-O2        {len(optimized)} macros")
print()
print("-O2 adds:   ", optimized.only_in(local))
print("-O2 removes:", local.only_in(optimized))
""")

lesson.md(f"""
One added and one removed, so the count is identical and the table is not. If you were
comparing two compilers by counting their macros you would have concluded that `-O2` does
nothing, which is a good reminder that a count is not a comparison.

Now the flag that names a language standard.
{claim("asking for -std=c23 does not change __STDC_VERSION__, because it was already C23")}.
""")

lesson.code("""
c23 = rec.macros("c23")

print("-std=c23 adds:   ", c23.only_in(local))
print("-std=c23 removes:", local.only_in(c23))
print("-std=c23 changes:", c23.differing(local) or "nothing")
print()
print(f"__STDC_VERSION__ without the flag: {local['__STDC_VERSION__'].body}")
print(f"__STDC_VERSION__ with it:          {c23['__STDC_VERSION__'].body}")
""")

lesson.md("""
The version number does not move, because GCC 16's default is already C23. What the flag
actually does is add `__STRICT_ANSI__`, which turns the GNU extensions off. `-std=c23` is a
request to stop doing something, and every header on the system reads that macro to decide
whether it is allowed to declare `strdup`.

Last one, for contrast, because it is the flag that moves the most.
""")

lesson.code("""
fast = rec.macros("fast")

print("-ffast-math adds:", ", ".join(fast.only_in(local)))
print()
for name in fast.differing(local):
    print(f"  {name:<26}{local[name].body:<8}->  {fast[name].body}")
""")

lesson.md("""
`__FAST_MATH__` is how `math.h` finds out. `__GCC_IEC_559` dropping from 2 to 0 is the compiler
writing down, in a macro, that its floating point is no longer IEEE conformant. That is not a
diagnostic and it is not a warning; it is a number in a table that a header can read.

## The list that is not the list

Here is a question the table above cannot answer. Where is `__FILE__`?
""")

lesson.code("""
print("__FILE__ in the dump of every macro:", "__FILE__" in local)
print("__LINE__ in the dump of every macro:", "__LINE__" in local)
""")

lesson.md(f"""
Not there. Nor `__LINE__`, nor `__COUNTER__`, nor `__has_include`. `-dM` prints the
preprocessor's hash table, and these are not in it, because they are not macros with bodies.
They are C functions with a name registered in front of them.
{claim("almost every macro libcpp builds in is missing from a dump of every macro")}.
""")

lesson.code("""
built = rec.builtin
missing = built.missing_from(local)

print(f"{len(built.array)} macros have a C function behind them:")
for start in range(0, len(built.array), 4):
    print("  " + "".join(f"{n:<22}" for n in built.array[start : start + 4]).rstrip())
print()
print(f"{len(missing)} of them are missing from -dM output.")
print(f"the one that is not: {[n for n in built.array if n not in missing]}")
""")

lesson.md("""
`__STDC__` is the exception, and it is the exception for a boring and satisfying reason: it is
in the array of C functions and it is also defined the ordinary way, with a value, so the hash
table has an entry to print. Every other name on that list would need the compiler to run a
function to answer, and `-dM` has nothing to print.

Here is the array, in the tree, with the macro that builds each row.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("f02")
row = cuts["builtins"]

print(f"{row.span}  ({row.citation})")
print(row.about)
print()
print(row.numbered())
""")

lesson.md(f"""
`B` is name and function. `C` is a name with an alias, `X` is one that warns when you use it.
The four `__has_*` entries are the ones a reader is most likely to have used this year, and
they are the clearest case: `__has_include(<stdio.h>)` cannot be a text substitution, because
answering it means searching the include path.

And the code that decides what `-dM` prints is one loop with one condition in it.
""")

lesson.code("""
print(cuts["dump"].numbered())
""")

lesson.md(f"""
`cpp_user_macro_p`. A node that is a built-in function is skipped, which is the whole answer.

## A space that is in no input file

Now the measurement from the top of the lesson.

Three lines of C, put through `gcc -E -P`. The `-P` turns the line markers off so that what
comes back is the expansion and nothing else. Read the input, predict the output, then run it.
{claim("preprocessed output can contain a space that is in none of the input files")}.
""")

lesson.code("""
spacing = rec.expansion("spacing")

print(spacing.source)
print("becomes")
print()
for was, now in spacing.pairs():
    print(f"  {was:<14}->   {now}")
""")

lesson.md(f"""
Line one is the one that matters. `a+EMPTY+b` has no space in it. `EMPTY` is defined to
nothing. And the output is `a+ +b`.

Do the substitution by hand, the way the wrong model says it happens, and compare.
{claim("what gcc printed differs from text substitution by exactly one space character")}.
""")

lesson.code("""
was, now = spacing.pairs()[0]
naive = was.replace("EMPTY", "")

print(f"the input:                {was!r}")
print(f"text substitution gives:  {naive!r}")
print(f"gcc -E -P gives:          {now!r}")
print()
print(f"difference: {cpp.inserted_spaces(naive, now)} space, and nothing else at all")
""")

lesson.md("""
If the preprocessor were substituting text, the output would be `a++b`, and `a++b` is a
different program: it is `a++` followed by `b`, which does not parse, and if it did parse it
would increment something. The preprocessor knows that, because it is not holding text. It is
holding a `+` token and another `+` token, and it knows that printing them adjacent would
produce a `++` token, and it will not do that.

Line two is the same fact from the other side. `a PLUS +b` has one space in the input and two
in the output. Line three, `a+ +b`, already had the space and comes out unchanged, which is
what says the rule is about the tokens and not about the line.

## The token

Here is the thing being held.
""")

lesson.code("""
print(cuts["token"].numbered())
""")

lesson.md(f"""
Thirty two bytes. A source location, a type from a list of about a hundred, a flag word, and
a union with the spelling in it.

`PREV_WHITE` is the flag to know. Whitespace is not a character in a buffer somewhere: it is a
bit on the token that comes after it. That is why a macro expanding to nothing can leave a
space behind, and why the question "was there a space here" is a thing the preprocessor can
answer at all.

The type list has one entry in it that surprises people.
""")

lesson.code("""
print(cuts["padding"].numbered())
""")

lesson.md(f"""
`CPP_PADDING` is a token that is not a token. It is what a macro expansion leaves at its edges
so that the printer can work out the spacing afterwards, and it is why the sentence "an empty
macro expands to nothing" is not quite true. It expands to padding.

## Which pairs, exactly

A rule that fires on every pair would be a printer that likes spaces. The interesting question
is which pairs, and the answer is a switch statement.
""")

lesson.code("""
print(cuts["avoid-paste"].numbered())
""")

lesson.md(f"""
One `case` per left-hand token type, and the body of each says which right-hand tokens are a
problem. `case CPP_DIV: return c == '/' || c == '*';` with the comment `/* Comments. */` is the
one to read twice: two divisions printed together would open a comment and eat the rest of the
line.

`gxray.cpp` carries at least one witness pair for every one of those labels, and a test
compares the set of labels the table covers against the switch in the pinned tree, so a GCC
that grows a new case fails the build rather than quietly making the next paragraph false.
{claim("the pairs that get a space are the pairs that would otherwise lex as one token")}.
""")

lesson.code("""
labels = {one.case for one in cpp.PASTES}
print(f"{len(cpp.PASTES)} witness pairs, covering {len(labels)} of the case labels:")
print()
for one in cpp.PASTES:
    print(f"  {one.left:>4} {one.right:<6}glued: {one.glued:<8}{one.about}")
""")

lesson.md(f"""
Each of those was actually run. The file that runs them is thirty eight lines of
`ID(left)ID(right)`, where `ID(x)` is `x`, because wrapping each side in a macro call is the
only way to get two tokens adjacent in a source file with no whitespace character anywhere
between them.
{claim("every pair the table names came back separated, and nine control pairs came back glued")}.
""")

lesson.code("""
print(f"{len(rec.probes)} pairs probed")
print(f"{len(rec.spaced)} came out with a space, {len(rec.unspaced)} came out glued")
print()
for one in rec.probes:
    mark = "space" if one.spaced else ""
    print(f"  {one.glued:<8}->  {one.output.strip():<10}{mark:<7}{one.case}")
""")

lesson.md("""
The bottom nine are the control. `+-`, `x+`, `*&`, `][`, `;;`, `&|`, `!!`, `~x`, `1]`: every one
of them is two tokens that stay two tokens when printed together, and every one of them came
back untouched. The rule is not a habit of the printer.

Which is the whole argument, stated as plainly as it can be. The preprocessor inserted a
character into its output, and it chose which pairs to insert it between by asking what the
tokens were. Text does not have types. Tokens do.

## The printer

The code that decides is short enough to read.
""")

lesson.code("""
print(cuts["spacing"].numbered())
""")

lesson.md(f"""
Three reasons for a space, and the comment above the third admits what it is doing: "Subtle. Do
not put a space before a `(` if ...". The first two are the token's own `PREV_WHITE` bit and the
padding left behind by a macro. The third is `cpp_avoid_paste`.

## The other kind of pasting

There is exactly one thing in the language that makes two tokens into one, and it is worth
seeing right after the section on the thing that prevents it.
{claim("the paste operator joins tokens before they are rescanned, so its arguments are not expanded")}.
""")

lesson.code("""
paste = rec.expansion("paste")

print(paste.source)
print("becomes")
print()
for was, now in paste.pairs():
    print(f"  {was:<20}->   {now}")
""")

lesson.md(f"""
`CAT(a, b)` gives `ab`, which is what everybody expects. `CAT(PLUS, PLUS)` gives `PLUSPLUS`,
which is not. `PLUS` is a macro defined to `+`, and a text editor would have substituted it and
then joined, giving `++`.

The rule is that an argument used as an operand of `##` is not macro-expanded first. So `PLUS`
and `PLUS` are joined as they are written, into the single identifier `PLUSPLUS`, which is then
looked up as a macro, is not one, and is printed. This is {term("token pasting")}, and both
halves of the name are now in the lesson: the operator that does it on purpose and the space
that prevents it happening by accident.

The same rule bites in a more familiar place.
""")

lesson.code("""
prescan = rec.expansion("prescan")

print(prescan.source)
print("becomes")
print()
for was, now in prescan.pairs():
    print(f"  {was:<20}->   {now}")
""")

lesson.md("""
`STR(PLUS)` gives `"PLUS"`. That is the two-macro dance every C programmer eventually copies out
of somebody else's header without knowing why: `#` also refuses to expand its operand, so you
need an outer macro whose only job is to force the argument through one round of expansion
before the inner one stringifies it. `XSTR(PLUS)` gives `"+"`.

## Blue paint

Two more expansions, and then the include path.
{claim("a macro cannot expand inside its own expansion, which is what stops the obvious infinite loop")}.
""")

lesson.code("""
paint = rec.expansion("paint")

print(paint.source)
print("becomes")
print()
for was, now in paint.pairs():
    print(f"  {was:<6}->   {now}")
""")

lesson.md(f"""
`#define foo foo + 1` terminates. So does `#define A B` with `#define B A`, which needs the
same rule applied one level out.

The mechanism has a name, from a comp.std.c thread in the 1980s: the identifier is painted
blue, and a blue identifier is never expanded again, even if it later turns up somewhere the
macro is not being expanded. In libcpp it is two flags, and here is the first.
""")

lesson.code("""
print(cuts["paint"].numbered())
""")

lesson.md(f"""
`NODE_DISABLED` while the expansion is in progress, and `NO_EXPAND` stamped onto any token that
came out with the macro's own name on it. The second is the permanent one, and it is why the
result is a property of the token rather than of the moment.

One more, because it catches people who are sure they know how macros work.
""")

lesson.code("""
invocation = rec.expansion("invocation")

print(invocation.source)
print("becomes")
print()
for was, now in invocation.pairs():
    print(f"  {was:<6}->   {now}")
""")

lesson.md("""
`f` on its own is not an invocation of `f`, so it is left alone. A function-like macro expands
only when the next token is an open bracket, which is what lets a header define a macro with the
same name as a function and still let you take the function's address. `f (2)` with a space
does expand, because the rule is about the next token and a space is not one.

## Where the text actually comes from

Turn the line markers back on. Everything so far used `-P`, which suppresses them. Here is the
same kind of file without it.
""")

lesson.code("""
markers = rec.expansion("markers")

print(markers.source)
print("becomes")
print()
print(markers.output)
""")

lesson.md(f"""
Those `#` lines are {term("line marker", "line markers")}. They are not comments, they are not
directives, and they are the mechanism by which an error inside a header points at the header:
the preprocessor destroyed the line numbering by pasting files together, and these hand it
back.
{claim("preprocessed output carries the line and file of every piece of text in it")}.
""")

lesson.code("""
for one in cpp.markers(markers.output):
    print(f"  {one}")
""")

lesson.md(f"""
The digits after the filename are flags, and knowing them turns a wall of noise into four
facts. GCC documents them in exactly one place in the tree.
""")

lesson.code("""
print(cuts["marker-flags"].numbered())
""")

lesson.md(f"""
Flag 3 is the one worth carrying around. A file marked as a system header has its warnings
suppressed, which is why moving a piece of code into `/usr/include` silences a warning about it,
and why `-Wsystem-headers` exists.

The code that prints the line is eleven lines.
""")

lesson.code("""
print(cuts["markers"].numbered())
""")

lesson.md(f"""
The 1 and the 2 come in as `special_flags`, a string the caller passes. The 3 and the 4 are
worked out here from `in_system_header_at`. Which is a small thing, and it explains why a marker
can say `1 3 4` but never `4 1`: the two halves are printed by different code.

## Thirty eight files

One `#include <stdio.h>`. `-H` prints every file that gets opened, one dot per level.
{claim("one include of stdio.h opens dozens of files, several levels deep")}.
""")

lesson.code("""
here = rec.headers("local")

print(here.about)
print(f"{len(here)} files opened, {len(here.files)} of them distinct, {here.depth} levels deep")
print()
print(here.tree(18))
print("  ...")
""")

lesson.md(f"""
That is what a {term("translation unit")} is. Not the file you wrote: the file you wrote with
everything it dragged in, which for a program whose body is one `puts` call is thirty eight
files and some tens of thousands of lines.

The same two lines somewhere else.
""")

lesson.code("""
there = rec.headers("elsewhere")

print(f"{local.target:<28}{len(here.files):>4} distinct files")
print(f"{elsewhere.target:<28}{len(there.files):>4} distinct files")
print()
print(there.tree(12))
print("  ...")
print()
print("files in common:", set(here.files) & set(there.files) or "none at all")
""")

lesson.md("""
Not one file in common. Same standard header, same release, same two lines of C, and the two
trees share nothing, because one of them is an Apple SDK and the other is glibc. Every
portability question about headers is downstream of that picture.

## Reading a header twice

The second `#include <stdio.h>` in that file cost nothing, and it is worth knowing exactly what
"nothing" means. Four headers, differing by one line each, included twice apiece.
""")

lesson.code("""
for name, text in sorted(rec.headers_source.items()):
    print(f"--- {name}")
    for line in text.rstrip().split(chr(10)):
        print(f"    {line}")
""")

lesson.md(f"""
`clean.h` is the ordinary idiom. `untidy.h` has a comment after the `#endif`. `stray.h` has one
declaration after the `#endif`. `bare.h` has no guard at all. Predict which ones get opened
twice before running the next cell.
{claim("an include guard is recognised only if the guard is the whole file, in tokens")}.
""")

lesson.code("""
guards = rec.headers("guards")

print(guards.text)
print(f"opened twice: {', '.join(guards.opened_twice)}")
""")

lesson.md(f"""
`untidy.h` was read once, and `stray.h` was read twice. The difference between them is a
comment and a declaration in the same position, which is the difference between something that
is a token and something that is not. The optimization needs the file's entire token stream to
be one conditional, and comments are gone before anything counts tokens.

The condition itself is two lines.
""")

lesson.code("""
print(cuts["guard"].numbered())
""")

lesson.md(f"""
`file->cmacro` is the name of the guard macro, remembered from the first read. If it is still
defined, the file is not opened. Note what that means for `#pragma once`: it is a different
mechanism with the same effect, and GCC supports both, but the guard version is the one that
works when the same header arrives through two different paths with two different `stat`
results.

`-H` will also volunteer advice about this, and the advice has a condition on it that catches
everybody.
{claim("GCC suggests an include guard only for a file it read exactly once")}.
""")

lesson.code("""
once = rec.headers("once")

print("--- each header included twice")
print(f"    suggestions: {list(guards.guards_wanted) or 'none'}")
print()
print("--- each header included once")
print(f"    suggestions: {[p.rsplit('/', 1)[-1] for p in once.guards_wanted]}")
""")

lesson.md(f"""
The run where two headers were read twice suggested nothing. The run where every header was
read once named the two that have no usable guard.

That is not a bug, and the reason is one line of the condition.
""")

lesson.code("""
print(cuts["advice"].numbered())
""")

lesson.md(f"""
`file->stack_count == 1`. GCC only advises about files it read exactly once, on the theory that
a file it read twice has already cost you the time and does not need a hint. Which means the
suggestion arrives for the header you have not yet had trouble with, and never for the one you
have. Worth knowing before you go looking for it in a build that is slow because of exactly
this problem.

## Two targets, one set of rules

One last comparison, and it is the one that says where the line is. The macro tables of these
two compilers share almost nothing. Every expansion above was recorded on both, and the
question is whether any of them came out differently.
{claim("two targets that share almost no macros expand every one of these files identically")}.
""")

lesson.code("""
for name in ("spacing", "prescan", "paste", "paint", "invocation"):
    one = rec.expansion(name)
    print(f"{name:<12}{'same' if one.agrees else 'DIFFERENT'}   {one.about}")
""")

lesson.md("""
Identical, all of them. Which is the shape of the whole subject: the vocabulary is the target's
and the grammar is the language's. `__SIZEOF_LONG_DOUBLE__` is a fact about a machine.
`a+EMPTY+b` becoming `a+ +b` is a fact about C, and it will be the same on a compiler for a
processor that does not exist yet.

## Boss fight

No new tools. Three questions, answerable from the recording:

1. Thirty eight pairs of tokens were put next to each other with no whitespace between them.
   How many came out of the preprocessor with a space in?
2. Four headers were each included twice. Which of them were actually opened twice?
3. Twenty macros are built into libcpp with a C function behind them, and a dump of every
   macro prints exactly one of them. Which one, and why that one?

Then check yourself:

```text
python lessons/f02-tokens-not-text/grade.py
```

or, from a checkout, `just grade f02-tokens-not-text`. It takes answers on the command line
too, so `--spaces 29 --twice a.h,b.h --odd SOME_MACRO` is a whole submission. Every answer it
marks against is worked out from the recording rather than written down.

## What to read next

F03 is the C parser, which is the program that reads the tokens this lesson has been printing.
The handover between them is one function call, and knowing that the parser never sees a
character of your file explains a great deal about GCC's error messages.

F01 is the lesson before this one, if you have not done it. It shows how `cc1` gets run at all.

If you have a GCC on your machine, every measurement here is one command. `gcc -dM -E - </dev/null | wc -l`
is your table. `echo 'a+EMPTY+b' | gcc -E -P -DEMPTY= -` is the space. `echo '#include <stdio.h>' | gcc -H -E - >/dev/null`
is your include tree, and it will not match this one. That is the lesson.
""")

raise SystemExit(lesson.save())
