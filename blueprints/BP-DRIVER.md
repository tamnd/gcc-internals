# BP-DRIVER, the program that runs the other programs

**Status:** partial
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** yes
**Generated sections:** none
**Last verified:** 2026-09-06 against `releases/gcc-16.2.0`

This document specifies the program that decides which other programs a compilation runs. The spec language is specified in full: every `%` form, how a brace construct is read, where an argument ends, and how a specs file overrides a built in string. The driver's main loop, the compiler table, the program search and the observable output are specified. Multilibs, sysroots, offloading, LTO and `collect2` are named and not specified, and each place that stops short says so. Section 2 could be generated from `gcc/gcc.cc` in principle, since the spec table is a static array, but the specs a given build actually uses come from the target's `config.gcc` and its headers rather than from the array, so a generator would have to run the driver rather than read the source, and that is a different kind of tool. What exists instead is `gxray.specs`, a reader for `-dumpspecs` output, with a test that compares its table of forms against the case labels of `do_spec_1` so a GCC that grows a form fails the build rather than printing it as text.

## 1. Purpose and scope

`gcc` is not a compiler. It is a program that reads a command line, decides which other programs have to run and in what order, builds a command line for each of them, and runs them. The compiler is `cc1`, the assembler is `as`, the linker is `ld` behind `collect2`, and none of them are part of the driver.

The interesting property is that the decision is not written in C. It is written in a small string substitution language, the spec language, and the C in `gcc/gcc.cc` is an interpreter for it. That is why the same driver source builds a driver for fifty one targets: the target supplies different strings.

**What this document covers.** The driver's main loop. The spec language: every substitution, the brace constructs, the spec functions, and the order they are evaluated in. How an input file's suffix selects a compiler. How a program name becomes a path. What the driver puts in the environment for the programs it runs. What an outside observer sees, which is `-###`, `-v` and `-dumpspecs`.

**What it does not cover.** Anything any of the programs do once they are running. Multilib selection, which is a subsystem with its own table language. Sysroots and the include path construction, beyond naming `%I`. Offloading and the OpenMP pipeline. LTO, which changes the chain in a way this document does not describe. `collect2`, which is a second driver with its own reasons for existing. `libgcc_s` selection.

**Position in the pipeline.** Before it. Everything else in this book happens inside one of the programs the driver starts.

**Inputs and outputs as properties.** None. The driver never holds IR and the `PROP_*` flags do not exist at this level.

## 2. Data structures

### 2.1 The compiler table

`struct compiler` at `gcc/gcc.cc:1420@releases/gcc-16.2.0` is five fields: a suffix, a spec, an optional replacement for `%C`, whether the compiler can take several source files at once, and whether the source needs preprocessing.

| Field | What it holds |
|---|---|
| `suffix` | the file suffix this entry claims, or `@name` for a named language |
| `spec` | the spec string to run, or `#Language` meaning the language is not built in |
| `cpp_spec` | substituted for `%C` instead of the usual `cpp_spec`, if not null |
| `combinable` | nonzero if the compiler accepts several sources at once |
| `needs_preprocessing` | nonzero if the source has to go through a preprocessor |

`default_compilers` at `gcc/gcc.cc:1453@releases/gcc-16.2.0` is the built-in table. It opens with about forty entries whose spec is a `#` string: `.cc` says `#C++`, `.f90` says `#Fortran`. Those exist so that a driver built without the C++ front end says "C++ compiler not installed on this system" rather than "file not used since linking is not done", which is the error a reader would otherwise get and would not understand.

The C entry is two rows. `{".c", "@c", 0, 0, 1}` at `gcc/gcc.cc:1480@releases/gcc-16.2.0` maps the suffix to a language name, and the `@c` row that follows it holds the spec. That indirection is why `-x c` works on a file called anything at all: `-x` sets the language directly and the suffix lookup is skipped.

### 2.2 The spec list

`struct spec_list` at `gcc/gcc.cc:1716@releases/gcc-16.2.0` is a named string with a pointer to where the string lives and a copy of its default. `static_specs` at `gcc/gcc.cc:1738@releases/gcc-16.2.0` holds **45** of them, which is every spec a `%(name)` reference can resolve to before a specs file adds more. `asm`, `cpp`, `cc1`, `link`, `lib`, `startfile`, `endfile` and `invoke_as` are in there.

A spec is a string and the default value of that string is kept alongside it, which is what makes `-dumpspecs` and a specs file able to override one and put it back.

### 2.3 The spec functions

`static_spec_functions` at `gcc/gcc.cc:1806@releases/gcc-16.2.0` is the escape hatch: **21** named C functions the spec language can call as `%:name(args)`. `if-exists`, `getenv`, `version-compare`, `find-file`, `sanitize` and `dumps` are the ones a reader meets first.

21 is a floor and not a total. The array ends with an `EXTRA_SPEC_FUNCTIONS` splice at `gcc/gcc.cc:1829@releases/gcc-16.2.0`, and a port defines that macro in its target header to add functions of its own. `gcc/config/aarch64/aarch64.h:1537@releases/gcc-16.2.0` is one such definition. Both of the configurations recorded for F01 call at least one function that is not in the built in array: the aarch64 Darwin build calls `rewrite_march` and `rewrite_mcpu`, and the x86-64 Linux build calls `local_cpu_detect`. A tool that checks a spec table against the 21 will report a spec table it cannot read.

Their existence is the honest admission that the spec language is not a programming language and some decisions cannot be expressed in it.

### 2.4 Where the chain actually comes from

`invoke_as` at `gcc/gcc.cc:1339@releases/gcc-16.2.0` is the spec that appends the assembler to a compilation. It is one string, picked at build time from two that differ only in whether the assembler is handed `%|.s` or `%m.s`, and reading it explains the whole shape of what T01 observes:

```text
%{!fwpa*:
   %{fcompare-debug=*|fdump-final-insns=*:%:compare-debug-dump-opt()}
   %{!S:-o %|.s |\n as %(asm_options) %m.s %A }
  }
```

`%{!S:...}` is the whole reason `-S` stops the chain at `cc1`. There is no code anywhere that says "if the user asked for assembly, do not run the assembler". There is a negated brace construct in a string.

That claim is checkable rather than rhetorical. Take the live `invoke_as` out of `gcc -dumpspecs`, remove the `%{!S:` wrapper and keep its body, write the result to a file, and pass `-specs=` that file. `gcc -S` then runs the assembler. F01 records that pair.

### 2.5 A specs file

`read_specs` at `gcc/gcc.cc:2634@releases/gcc-16.2.0` reads the format `-dumpspecs` prints, and a name in it is one of two things.

A name beginning with `*` sets a spec. `set_spec` overwrites, so the definition in the file replaces the built in one, and `+` at the start of the value appends to it instead. The single exception is `*link_command`, which `read_specs` special cases into a variable of its own rather than into the spec list.

A name that does not begin with `*` is a suffix, and the entry is appended to the compiler table as a new row. That is how a specs file teaches the driver a new file extension, and it works because `lookup_compiler` searches backwards, so an appended row beats a built in one.

The consequence worth stating plainly is that both halves of the driver's data are replaceable at run time by a text file, with no compiler and no rebuild.

## 3. Algorithms

### 3.1 The main loop

`driver::main` at `gcc/gcc.cc:8305@releases/gcc-16.2.0` is short enough to read as pseudocode, which is close to what it is.

```text
main(argc, argv):
    set_progname(argv[0])
    expand_at_files(&argc, &argv)          # @file arguments become their contents
    decode_argv(argc, argv)                # the command line becomes switches and infiles
    global_initializations()
    build_multilib_strings()
    set_up_specs()                         # specs files are read here, defaults first
    putenv_COLLECT_AS_OPTIONS(assembler_options)
    putenv_COLLECT_GCC(argv[0])
    maybe_putenv_COLLECT_LTO_WRAPPER()
    maybe_putenv_OFFLOAD_TARGETS()
    handle_unrecognized_options()
    if completion: suggest and return 0
    if not maybe_print_and_exit(): return 0     # -###, --help, -dumpspecs and friends
    if prepare_infiles(): return exit_code      # nothing to compile
    do_spec_on_infiles()                        # one spec run per input file
    maybe_run_linker(argv[0])
    final_actions()
    return exit_code
```

Two things are worth noticing. The specs are fully resolved before any input file is looked at, so a specs file cannot depend on which file is being compiled except through the spec language's own conditionals. And the linker is not part of any file's spec: `maybe_run_linker` at `gcc/gcc.cc:9217@releases/gcc-16.2.0` runs once at the end, after every input has produced an output, which is why `%o` substitutes a list.

### 3.2 Choosing a compiler for a file

`lookup_compiler` at `gcc/gcc.cc:9398@releases/gcc-16.2.0`.

```text
lookup_compiler(name, length, language):
    if language starts with '*': return none          # -x explicitly says "linker input"
    if language is set:
        for cp from last entry down to first:
            if cp.suffix is "@" + language: return cp
        error "language not recognized"; return none
    for cp from last entry down to first:
        if cp.suffix is "-" and name is "-": break
        if len(cp.suffix) < length and name ends with cp.suffix: break
    return cp if found else none
```

Both loops run backwards, and the comment on `compilers` at `gcc/gcc.cc:1445@releases/gcc-16.2.0` says why: if several entries match, the last one wins. A specs file appends, so a user entry beats a built-in one, and that is the entire override mechanism.

The suffix test is `strlen (cp->suffix) < length`, strictly less than. A file named exactly `.c` has no compiler.

### 3.3 Running a spec

`do_spec` at `gcc/gcc.cc:5854@releases/gcc-16.2.0` is the outer call and `do_spec_1` at `gcc/gcc.cc:6163@releases/gcc-16.2.0` is the interpreter. The model is an argument buffer that the spec appends to, plus a list of commands that a `|` or a newline closes off.

```text
do_spec_1(spec, inswitch, soft_matched_part):
    for each character c in spec:
        case c:
            ' ' or '\t':  end the current argument
            '\n':         end the current command; if a program is pending, it joins the list
            '|':          end the current command and pipe it into the next, if -pipe
            '%':          read the next character and dispatch on it
            otherwise:    append c to the current argument
```

The dispatch on `%` is the spec language, and the only description of it anywhere is the comment block that begins at `gcc/gcc.cc:473@releases/gcc-16.2.0`. There are **45** single character forms plus **3** compound ones, and they fall into five families.

Where a form ends matters as much as what it means, so each table says how far past the letter the form reaches. `none` is the letter alone. `suffix` swallows `[.0-9A-Za-z]*` and then an optional literal `%O`, which is why `%|.s` is one form and not a form followed by the text `.s`. `switch` runs to the next space or tab, `line` to the next newline, and `brace` means a balanced `{...}` follows.

### 3.3.1 Forms that substitute text

25 of them, and between them they are every filename, path and suffix the driver knows.

| form | reaches | what it substitutes |
|---|---|---|
| `%%` | none | a literal percent sign |
| `%"` | none | an empty argument, and the end of the one before it |
| `%i` | none | the input file |
| `%b` | none | the input file's base name, without the suffix |
| `%B` | none | the input file's base name, suffix included |
| `%o` | none | every output file so far, which is what the linker is given |
| `%O` | none | the object file suffix for this target |
| `%I` | none | the include options the driver worked out for itself |
| `%s` | none | search for the argument as a library or startup file |
| `%T` | none | search for the argument as a linker script |
| `%D` | none | a `-L` for every directory in `startfile_prefixes` |
| `%P` | none | a runpath option for every directory in `startfile_prefixes` |
| `%M` | none | the multilib os directory |
| `%R` | none | the sysroot, with its suffix |
| `%X` | none | the linker options that `%x` collected |
| `%Y` | none | the assembler options from the command line |
| `%Z` | none | the preprocessor options from the command line |
| `%*` | none | the variable part of the switch this brace matched |
| `%g` | suffix | a temporary file, one per compilation |
| `%u` | suffix | a temporary file, a new one every time |
| `%U` | suffix | the file the last `%u` made, or a new one |
| `%j` | suffix | the bit bucket, or a temporary if there is not one |
| `%\|` | suffix | a temporary file, or a bare `-` when `-pipe` is in effect |
| `%m` | suffix | a temporary file, or nothing at all when `-pipe` is in effect |
| `%.` | suffix | the suffix the next `%*` should use instead of its own |

### 3.3.2 Forms that run another spec

10 of them, and each is a shorthand for one `%(name)`. Both spellings are the same edge in the call graph, and a tool that reads a spec table has to fold them together or it will report `lib` as uncalled on a target whose link spec says `%L`.

| form | runs | form | runs |
|---|---|---|---|
| `%a` | `asm` | `%L` | `lib` |
| `%A` | `asm_final` | `%S` | `startfile` |
| `%C` | `cpp` | `%E` | `endfile` |
| `%G` | `libgcc` | `%1` | `cc1` |
| `%l` | `link` | `%2` | `cc1plus` |

`%(name)` itself is a compound form: the name runs to the closing parenthesis and is looked up in the spec list at run time, so a specs file can add a name and a built in spec can call it.

### 3.3.3 Forms that mark an argument

6 of them. These substitute nothing. They change what the driver does with the argument they are attached to, which is why a reader who is only tracking text comes away thinking they do nothing at all.

| form | reaches | what it does |
|---|---|---|
| `%d` | none | delete the file this argument names, if the compilation works |
| `%w` | none | this argument is the output file, and is what `%o` will find |
| `%V` | none | this compilation produces no output file |
| `%W` | brace | like `%{...}`, but delete the file it names if the run fails |
| `%@` | brace | like `%{...}`, but put the result in a file and pass `@that` |
| `%x` | brace | collect a linker option for `%X` to substitute later |

### 3.3.4 Forms that remove a switch, and forms that stop

`%<S` drops a switch from here on and from what gets passed on. `%>S` drops it from what gets passed on and keeps it here. Both run to the next space or tab, so the switch name is part of the form.

`%eTEXT` prints the rest of the line as an error and abandons this input file. `%nTEXT` prints it as a notice. Both run to the next newline. A reader who has ever seen `GNU C no longer supports -traditional without -E` has read the output of a `%e` in the `@c` spec, which is a diagnostic written in a string in a table rather than in the compiler.

### 3.3.5 Conditionals

`%{...}`, handled by `handle_braces` at `gcc/gcc.cc:7293@releases/gcc-16.2.0`, whose contract is in the comment above it at `gcc/gcc.cc:7288@releases/gcc-16.2.0`. This is the most common form in a real table by a long way, and a table is mostly branches rather than mostly text.

| written | means |
|---|---|
| `%{S}` | pass the switch on, if it was given |
| `%{S*}` | pass on every switch beginning with `S` |
| `%{S:X}` | substitute `X` if `-S` was given |
| `%{!S:X}` | substitute `X` unless `-S` was given |
| `%{S\|T:X}` | substitute `X` if either was given |
| `%{.S:X}` | substitute `X` if the input file's suffix is `.S` |
| `%{,S:X}` | substitute `X` if the spec being used is `S` |
| `%{%:f(a):X}` | substitute `X` if the spec function returns anything |
| `%{S:X;T:Y;:D}` | an n-way choice, last clause the default |

Three things a reader parsing one of these has to get right. The colon that splits the predicate from the body is not the first colon, because the predicate may be a spec function call with a colon of its own. A backslash escapes the next character, which is how `%{std=iso9899\:1999:X}` matches a switch whose name contains a colon. And a semicolon inside a nested brace or inside a function call's parentheses does not start a new clause.

### 3.3.6 Function calls

`%:name(args)`, evaluated by `eval_spec_function` at `gcc/gcc.cc:7046@releases/gcc-16.2.0`. The arguments are processed as a spec first, then split into an argv.

Two details a reader of a real spec will hit. `-O`, `-f`, `-g`, `-m` and `-W` are handled specially inside brace constructs: a later switch of the same kind cancels an earlier one, which is why `-O0 -O2` behaves and `%{O*}` still passes everything. And a `|` at the start of the predicate text means "pipe into the next command, but only if `-pipe` was given", which is the only place in the language where a construct is about process plumbing rather than text.

### 3.4 Finding a program

`find_a_program` at `gcc/gcc.cc:3110@releases/gcc-16.2.0` checks a compiled in default for `as`, `ld`, `dsymutil` and `windres` first, and falls back to `find_a_file` at `gcc/gcc.cc:3059@releases/gcc-16.2.0` searching `exec_prefixes`. `exec_prefixes` is built from `-B`, `GCC_EXEC_PREFIX`, `COMPILER_PATH` and the configured install directory, in that order.

This is why `gcc -print-prog-name=cc1` answers a path outside `PATH` and `gcc -print-prog-name=as` usually answers a path inside it: `cc1` is GCC's own and lives in the libexec directory, and `as` is the system's.

### 3.5 Actually running them

`execute` at `gcc/gcc.cc:3273@releases/gcc-16.2.0` takes the accumulated command list and hands it to `pex`, which is libiberty's process execution layer. Commands separated by `|` become a pipeline in one `pex` object, which is what `-pipe` gets you: no temporary file between `cc1` and `as`.

*To be written: the exit code aggregation, `-wrapper`, and what happens to a signal.*

## 4. Invariants

**I1.** Every input file is looked up in the compiler table exactly once, and a file with no matching entry is passed to the linker unchanged rather than being an error.
Established by: `driver::do_spec_on_infiles` at `gcc/gcc.cc:9070@releases/gcc-16.2.0`. Checked by: nothing. May be broken by: nobody.

**I2.** When several entries in the compiler table match a file, the last one wins.
Established by: the backwards loops in `lookup_compiler`. Checked by: nothing. May be broken by: nobody. This is the mechanism a specs file relies on, so changing the loop direction would silently break every user override rather than failing loudly.

**I3.** A spec string is fully expanded before any process is started for it, and the expansion cannot observe the result of a process it started.
Established by: `do_spec` running `do_spec_2` to completion before calling `execute`. Checked by: nothing. May be broken by: a spec function, which runs during expansion and may look at the filesystem. `%:if-exists` is exactly that, and it is the reason this invariant is stated as a property of processes and not of the world.

**I4.** `%o` substitutes the outputs of the compilations that have already happened, so it is only meaningful in the link spec.
Established by: `outfiles` being filled in as each input is compiled and read once at the end. Checked by: nothing. May be broken by: nobody, and the comment in the language reference saying "%o is for use in the specs for running the linker" is the whole enforcement.

**I5.** The driver holds no intermediate representation at any point.
Established by: the design. Checked by: nothing. May be broken by: nobody. Worth stating because a reader who has heard "GCC" and "the driver" used interchangeably will otherwise look for the optimizer in `gcc.cc`.

**I6.** Every `%(name)` in a spec resolves, because the 45 names of `static_specs` are always defined, empty if the target does not need them.
Established by: `init_spec` at `gcc/gcc.cc:1899@releases/gcc-16.2.0` filling every entry from its default. Checked by: `tests/test_specs.py`, against two recorded targets. May be broken by: a target that removes a name, which is not something the mechanism allows, and a specs file, which can only add. About a third of any real table is empty for this reason, and an empty spec is a hook the target did not need rather than a missing one.

**I7.** A name may be defined more than once in a spec table, and the last definition is the one that resolves.
Established by: `set_spec` overwriting, and a specs file being read after the built in table. Checked by: `tests/test_specs.py`. May be broken by: nobody, and this is the same mechanism as I2 applied to the other half of the data. A reader of `-dumpspecs` output sees both definitions, because the dump walks the list.

*To be written: the invariants about temporary file lifetime, and about what `COLLECT_GCC_OPTIONS` is required to round trip.*

## 5. Observable behaviour

`-###` prints the commands the driver would run, quoted, and runs none of them. `-v` prints them and runs them. `-dumpspecs` prints every spec in the spec list, which is the machine readable version of section 2.2.

Corpus entry `t01-driver` holds five recorded invocations of the same file on the same compiler, differing only in flags. What they show:

| flags | programs run |
|---|---|
| `-O2 -E` | `cc1` |
| `-O2 -S` | `cc1` |
| `-O2 -c` | `cc1`, `as` |
| `-O2` | `cc1`, `as`, `collect2` |
| `-O0 -c` | `cc1`, `as` |

Three facts a reader can take from that table and check. The optimization level does not change the chain, only the arguments to `cc1`, which is the first observable consequence of the driver knowing nothing about optimization. `-E` and `-S` both stop at `cc1`, because the integrated preprocessor means there is no separate `cpp` process to see. And the linker appears as `collect2` rather than `ld`, because `collect2` is what the link spec names.

Corpus entry `t01-driver-ce` holds the same source on a differently configured GCC 16.2.0 through Compiler Explorer. The chain is different, which is the point: the chain is a property of how a compiler was configured and what it targets, not of the version number.

### 5.1 What `-dumpspecs` shows

Corpus entry `f01-specs` holds two whole spec tables of the same release, and four pairs of `-###` runs that differ by one text file.

| | Homebrew aarch64-apple-darwin24 | the Compiler Explorer x86-64 Linux build |
|---|---|---|
| named blocks | 56 | 47 |
| characters | 8783 | 9336 |
| of the 45 built in, missing | none | none |
| added on top | 11 | 2 |

Neither table is a subset of the other and both contain all 45 of `static_specs`, which is the observable form of the claim in section 2.2: the built in list is what a `%(name)` can always resolve to, and everything past it came from the target.

Both tables contain `link_command`, which neither target added. It is the one name `-dumpspecs` prints from a variable rather than from the spec list, at `gcc/gcc.cc:4242@releases/gcc-16.2.0`, so a reader comparing two unrelated targets finds it in both and can conclude it belongs to the driver.

### 5.2 What a specs file changes

Four files, each one pair of `-###` runs that are identical except for `-specs=`.

| file | contents | before | after |
|---|---|---|---|
| `argument` | `*cc1:` then `+ -fverbose-asm` | `cc1` | `cc1`, with `-fverbose-asm` added |
| `assembler` | `*invoke_as:` with `as` renamed | `cc1`, `as` | `cc1`, `my-own-assembler` |
| `guard` | `*invoke_as:` with the `%{!S:` wrapper removed | `cc1` | `cc1`, `as` |
| `suffix` | `.frob:` then `@c` | nothing, and a warning | `cc1`, `as` |

The `argument` file is the `+` form of section 2.5, appending rather than replacing. The `assembler` and `guard` files replace a spec. The `suffix` file adds a compiler table row, and before it the same input is a file the driver has no compiler for and hands to the linker, which is what the "linker input file unused" warning in section 6 is.

*To be written: `-print-search-dirs`, `-print-multi-lib`, and the `COLLECT_*` environment variables as observable output.*

## 6. Edge cases and error paths

*To be written.* The ones already known to matter:

- A file whose suffix matches nothing goes to the linker. This is how `.o` files work, and it is also how a typo in a filename becomes a linker error rather than a driver error. With `-c`, where there is no linker to run, the driver says "linker input file unused because linking not done" and runs nothing at all, which is the `suffix` row of section 5.2 before its specs file is applied.
- A file named exactly `.c`, where the suffix test `strlen (cp->suffix) < length` is false, has no compiler.
- `-` as an input file requires `-E` or `-x`, and the `"-"` entry in the compiler table exists to produce that message.
- A `#Language` entry produces "compiler not installed on this system", which is a driver diagnostic about a front end that was never built, not about anything on the system.
- A spec that ends mid argument, which `do_spec` handles by forcing out the pending command and popping a trailing `|`.

## 7. Interactions

The driver reads the target's configuration through the specs its build compiled in, and reads the environment through `GCC_EXEC_PREFIX`, `COMPILER_PATH`, `LIBRARY_PATH` and `LANG`.

It writes `COLLECT_GCC`, `COLLECT_GCC_OPTIONS`, `COLLECT_AS_OPTIONS` and `COLLECT_LTO_WRAPPER` into the environment of the programs it starts. `collect2` reads `COLLECT_GCC` and `COLLECT_GCC_OPTIONS` to re-invoke the driver for constructor and destructor discovery, which is a driver calling a program that calls the driver, and is the one loop in the toolchain.

Programs started: `cc1` and its siblings, `as`, `collect2`, `lto-wrapper`, and whatever a spec function names.

*To be written: the rest, in particular the sysroot and multilib interaction with `%I` and `%D`.*

## 8. Conformance

*To be written.* `gcc.dg/spec-options.c` and the `gcc.misc-tests/help.exp` family exercise the option handling. There is no test suite for the spec language as a language, which is worth saying out loud: the specs are tested by the fact that the compiler builds and runs, and a change to `handle_braces` that broke an unused construct would not be caught.

This project's own substitute is `tests/test_specs.py`, which is not a conformance suite for GCC and should not be read as one. It checks that the reader in `gxray.specs` agrees with the source: that its table of forms is exactly the case labels of `do_spec_1` minus the whitespace and compound ones, that every letter shorthand names a spec the driver has, and that tokenizing and rejoining every spec of two recorded targets returns the original string.

## 9. Port notes

The driver is target dependent in the only way that matters: the C is shared and the strings are not. A port supplies `ASM_SPEC`, `LINK_SPEC`, `LIB_SPEC`, `STARTFILE_SPEC`, `ENDFILE_SPEC`, `CC1_SPEC` and usually several more through its `config.gcc` fragment and its target header, and those strings are what makes the same `gcc.cc` produce a different chain.

What differs across the two configurations recorded in section 5, both GCC 16.2.0:

| | Homebrew aarch64-apple-darwin24 | the Compiler Explorer x86-64 build |
|---|---|---|
| link step | `collect2` | `collect2` |
| assembler | the system `as` | the binutils `as` in the install tree |
| `-S` chain | `cc1` | `cc1` |
| specs source | compiled in | compiled in |
| named blocks | 56 | 47 |
| names past `static_specs` | 11 | 2 |
| spec functions called | 13, two of them the port's own | 12, one of them the port's own |

The last three rows are the ones that say what porting actually costs here. A port does not write a driver. It writes strings, and the count of strings it has to write is the size of the gap between the built in 45 and what its chain needs. A port that also has to make a decision the language cannot express writes a spec function and splices it in with `EXTRA_SPEC_FUNCTIONS`, which both of the recorded targets did.

**What is forced and what is not.** The split between a driver and a compiler is forced by nothing at all. Clang puts the same logic in a library and calls it in process, and pays for that with a compiler that cannot be replaced without replacing the driver. GCC's choice buys the ability to point `-B` at a different `cc1` and have everything else keep working, which is the single most useful thing about the arrangement when you are developing GCC itself.

The spec language is the clearest case of a historical choice in the whole compiler. Nothing requires the decision procedure to be a string substitution language, and a reimplementation could write it in the host language and lose only the ability to override it with a text file at install time. That ability turns out to matter to distributions and to nobody else, which is worth knowing before deciding to copy the design.

A reimplementation does have to decide one thing GCC decided implicitly: whether the driver knows which switches take arguments. GCC does, and the comment at `gcc/gcc.cc:692@releases/gcc-16.2.0` explains that it has to, because it cannot tell which arguments are input files without knowing which switches consumed the argument after them. That constraint is real and applies to any driver.
