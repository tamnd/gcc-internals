# BP-CPP, the preprocessor

**Status:** partial
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** yes
**Generated sections:** none
**Last verified:** 2026-09-06 against `releases/gcc-16.2.0`

This document specifies libcpp, the library that turns a source file into a stream of preprocessing tokens, and the client in `gcc/c-family/c-ppoutput.cc` that prints that stream when you ask for `-E`. The token, the token type table, the hash node and the macro are specified field by field. Lexing, macro expansion, argument prescan, stringification, pasting, the disabling rule, the multiple include optimization and the spacing rule the printer applies are specified as algorithms. Traditional mode, modules and header units, precompiled headers, `#embed`, character set conversion and the `#if` expression evaluator are named and not specified, and each place that stops short says so. Nothing here is generated, because libcpp keeps its tables in C macros rather than in `.def` files a script could read without a C parser. What exists instead is `gxray.cpp`, a reader for recorded preprocessor output, with tests that compare its table of paste-avoiding pairs against the case labels of `cpp_avoid_paste` in the pinned tree, so a GCC that grows a pair fails the build rather than making a paragraph quietly false.

## 1. Purpose and scope

The preprocessor is not a program. It is a library, libcpp, linked into `cc1` and into every other C family front end, and `gcc -E` does not start a separate process: it runs the same `cc1` with a flag that makes it stop after preprocessing and print. A reader who goes looking for a `cpp` binary in the chain will not find one, which is what T01 observes from the outside and this document explains from the inside.

The library's contract with its client is one function. `cpp_get_token` at `libcpp/macro.cc:3265@releases/gcc-16.2.0` returns the next preprocessing token, and everything else libcpp does happens behind it: opening files, expanding macros, evaluating conditionals, skipping dead branches, and maintaining the line map that says where each token came from. The client either builds a parse tree from those tokens, which is what `cc1` does, or prints them, which is what `-E` does.

**What this document covers.** The token and its flags. The token type table. How a file becomes tokens. How a macro is defined, invoked, expanded, prescanned, stringified and pasted, and why an expansion cannot recurse. The include stack, the multiple include optimization, and `#pragma once`. The line map far enough to explain a line marker. The `-E` printer, including the rule that decides where a space goes.

**What it does not cover.** Traditional mode, which is a second preprocessor in `libcpp/traditional.cc` with its own lexer and its own macro expander, reached with `-traditional-cpp`. C++ modules and header units. Precompiled headers. `#embed`, which is new in C23 and large. Character set conversion, universal character names and the input charset machinery. The `#if` expression evaluator in `libcpp/expr.cc`, except for the one thing it contributes to the include guard state machine. Assertions, the `#assert` family, which GCC marks deprecated in its own directive table. Deferred pragmas, beyond noting where they interrupt the token stream.

**Position in the pipeline.** First. Every other document in this book describes something that happens to tokens this one produced.

**Inputs and outputs as properties.** None. The `PROP_*` flags describe IR held by the middle end, and libcpp holds none. Its input is a file and its output is a token stream.

## 2. Data structures

### 2.1 The token

`cpp_token` at `libcpp/include/cpplib.h:265@releases/gcc-16.2.0`, and its own comment at `libcpp/include/cpplib.h:261@releases/gcc-16.2.0` says it occupies 32 bytes on a 64-bit host.

| Field | Type | Meaning |
|---|---|---|
| `src_loc` | `location_t` | a key into the line map, not a line number |
| `type` | `cpp_ttype` in 8 bits | which of the 90 kinds of token this is |
| `flags` | `unsigned short` | the 13 flags below |
| `val` | union | the payload, discriminated by `type` |

The union has six members and the discriminator is a function, `cpp_token_val_index` at `libcpp/include/cpplib.h:297@releases/gcc-16.2.0`, rather than a field. An identifier carries a `cpp_hashnode *`, a number or string carries a `cpp_string`, a macro argument carries an index, a deferred pragma carries a cookie, and a padding token carries a pointer to the token whose whitespace it is standing in for.

There are 13 flags, at `libcpp/include/cpplib.h:199@releases/gcc-16.2.0`, and they are the part a reader of preprocessed output needs, because three of them are the whole reason the output looks the way it does.

| Flag | Bit | Meaning |
|---|---|---|
| `PREV_WHITE` | 0 | there was whitespace before this token in the file |
| `DIGRAPH` | 1 | it was written as a digraph, so `%:` rather than `#` |
| `STRINGIFY_ARG` | 2 | a macro parameter with `#` in front of it |
| `PASTE_LEFT` | 3 | this token is the left operand of a `##` |
| `NAMED_OP` | 4 | a C++ named operator, so `and` rather than `&&` |
| `PREV_FALLTHROUGH` | 5 | preceded by a fallthrough comment |
| `DECIMAL_INT` | 6 | a decimal integer, and set by the front end rather than by libcpp |
| `PURE_ZERO` | 7 | a single `0` digit, and aliased twice as `COLON_SCOPE` and `NO_DOT_COLON` |
| `SP_DIGRAPH` | 8 | the `#` or `##` in a definition was a digraph |
| `SP_PREV_WHITE` | 9 | whitespace before a `##` in a definition |
| `NO_EXPAND` | 10 | never macro expand this token, whatever the table says |
| `PRAGMA_OP` | 11 | came from `_Pragma` |
| `BOL` | 12 | first token on a line |

Two of those thirteen bits are not libcpp's. `DECIMAL_INT` is set in `gcc/c-family/c-lex.cc`, and `PURE_ZERO` is read by the C++ front end, which is what it means for a token to be a shared structure rather than a private one.

`PREV_WHITE` is one bit and it is the only record of the spacing in the original file. A token does not know how many spaces were in front of it, or whether they were tabs, or whether there was a comment there. The printer reconstructs a plausible spacing from this bit and from the rules in section 3.8, and the reconstruction is not the input.

### 2.2 The token types

`TTYPE_TABLE` at `libcpp/include/cpplib.h:54@releases/gcc-16.2.0` is one C macro with **90** entries, expanded three times in the whole compiler: into `enum cpp_ttype` at `libcpp/include/cpplib.h:161@releases/gcc-16.2.0`, into the spelling table `token_spellings` at `libcpp/lex.cc:46@releases/gcc-16.2.0`, and into a table of names for the C++ parser's own debug printer at `gcc/cp/parser.cc:1677@releases/gcc-16.2.0`. **56** entries are punctuation, written `OP(name, spelling)`, and **34** are everything else, written `TK(name, category)`.

The order is load bearing and the comment above the table at `libcpp/include/cpplib.h:43@releases/gcc-16.2.0` says so. Four names are positions rather than types:

| Name | Equals | Why it exists |
|---|---|---|
| `CPP_LAST_EQ` | `CPP_LSHIFT` | everything at or below it can be followed by `=` to make another token |
| `CPP_FIRST_DIGRAPH` | `CPP_HASH` | the digraph spellings are a contiguous run starting here |
| `CPP_LAST_PUNCTUATOR` | `CPP_ATSIGN` | above this, a token has a payload rather than a fixed spelling |
| `CPP_LAST_CPP_OP` | `CPP_LESS_EQ` | above this, a token cannot appear in a `#if` expression |

Every type has a spelling category, from `enum spell_type` at `libcpp/lex.cc:27@releases/gcc-16.2.0`: `SPELL_OPERATOR` for a fixed string, `SPELL_IDENT` for a hash node's name, `SPELL_LITERAL` for a stored string, and `SPELL_NONE` for the types that cannot be printed at all. The category is what `cpp_output_token` at `libcpp/lex.cc:4637@releases/gcc-16.2.0` switches on.

### 2.3 The padding token

`CPP_PADDING` at `libcpp/include/cpplib.h:157@releases/gcc-16.2.0` is the last entry in the table and the only one that is not a preprocessing token in the language's sense. It carries no text. It exists so that the token stream can say "there was a macro boundary here" at a point where the language says nothing happened, and its `val.source` points at the token whose `PREV_WHITE` should be consulted.

A macro that expands to nothing does not expand to nothing. It expands to a padding token, produced by `padding_token` at `libcpp/macro.cc:2454@releases/gcc-16.2.0`, and the printer's response to that padding is the space in section 5.3 that appears in no input file.

### 2.4 The hash node

`cpp_hashnode` at `libcpp/include/cpplib.h:1069@releases/gcc-16.2.0` is one identifier, interned. Every occurrence of a name anywhere in the translation unit points at the same node, which is why testing whether a name is a macro is a pointer comparison rather than a string comparison.

| Field | Bits | Meaning |
|---|---|---|
| `ident` | | the interned string, from libiberty's hash table |
| `is_directive` | 1 | this name is a directive name |
| `directive_index` | 7 | which one, or a `NODE_OPERATOR` code |
| `rid_code` | 8 | the front end's keyword code, unused by libcpp |
| `flags` | 9 | the `NODE_*` flags |
| `type` | 2 | `enum node_type` |
| `deferred` | 32 | a cookie for lazily defined macros |
| `value` | | a union discriminated by `type` |

`enum node_type` at `libcpp/include/cpplib.h:1015@releases/gcc-16.2.0` has four values, and the interesting one is that a macro is not a separate kind of object. `NT_VOID` is an ordinary identifier, `NT_USER_MACRO` has a `cpp_macro *` in `value`, `NT_BUILTIN_MACRO` has a `cpp_builtin_type` in `value` and no body at all, and `NT_MACRO_ARG` is what a parameter name becomes while its own definition is being read.

Of the nine `NODE_*` flags at `libcpp/include/cpplib.h:1004@releases/gcc-16.2.0`, one is an algorithm rather than a property. `NODE_DISABLED` at `libcpp/include/cpplib.h:1008@releases/gcc-16.2.0` is set on a macro while its own expansion is being rescanned, and section 3.6 is the whole story.

### 2.5 The macro

`cpp_macro` at `libcpp/include/cpplib.h:930@releases/gcc-16.2.0` is a header with the replacement list as a trailing array, so one allocation holds a definition.

| Field | Meaning |
|---|---|
| `parm.params` | the parameter names, as hash nodes, or the assertion chain |
| `line` | where it was defined, for the "defined here" note |
| `count` | how many tokens are in the body |
| `paramc` | how many parameters |
| `lazy` | the value is supplied by the client on first use |
| `kind` | ISO, traditional or assertion, in 2 bits |
| `fun_like` | whether an invocation needs a bracket |
| `variadic` | whether the last parameter is `...` |
| `syshdr` | defined in a system header, which suppresses warnings |
| `used` | expanded or tested at least once, for `-Wunused-macros` |
| `extra_tokens` | trailing `CPP_PASTE` tokens are present for redefinition checking |
| `imported_p` | came from a C++20 header unit |
| `exp.tokens` | the replacement list, `count` of them |

`fun_like` is the field behind the rule most people learn by accident: a function-like macro named without a following `(` is not an invocation and is left alone. Section 3.3 is where that is decided.

### 2.6 The built-in macros

`builtin_array` at `libcpp/init.cc:449@releases/gcc-16.2.0` holds **20** names whose value is computed by a C function rather than stored as tokens, and `enum cpp_builtin_type` at `libcpp/include/cpplib.h:1026@releases/gcc-16.2.0` holds the **19** codes they map to, two names sharing `BT_HAS_ATTRIBUTE`.

```text
__TIMESTAMP__   __TIME__          __DATE__            __FILE__
__FILE_NAME__   __BASE_FILE__     __LINE__            __INCLUDE_LEVEL__
__COUNTER__     __has_attribute   __has_c_attribute   __has_cpp_attribute
__has_builtin   __has_include     __has_include_next  __has_embed
__has_feature   __has_extension   _Pragma             __STDC__
```

None of these has a body, so none of them can be printed by a dump of the macro table, and section 5.2 records that 19 of the 20 are absent from `-dM` output. The exception is `__STDC__`, and the reason is one line: `cpp_init_builtins` at `libcpp/init.cc:589@releases/gcc-16.2.0` installs the array through `cpp_init_special_builtins` at `libcpp/init.cc:539@releases/gcc-16.2.0` and then, at `libcpp/init.cc:596@releases/gcc-16.2.0`, defines `__STDC__` a second time the ordinary way, with a value. The ordinary definition is what the dump can see.

The other names in the table a reader will find with `-dM` come from two places that are not libcpp at all. `cpp_init_builtins` goes on to define the language version macros the ordinary way too, `__cplusplus` at `libcpp/init.cc:606@releases/gcc-16.2.0` and `__STDC_VERSION__` at `libcpp/init.cc:639@releases/gcc-16.2.0`, one arm of a chain of `else if` on the selected standard. Everything about the machine, which is most of the table, is defined by the front end and the target through `c_cpp_builtins` in `gcc/c-family/c-cppbuiltin.cc` and the target's `TARGET_CPU_CPP_BUILTINS` hook. That split is why the count in section 5.1 is a fact about a target rather than about a compiler version.

### 2.7 The file

`_cpp_file` at `libcpp/files.cc:54@releases/gcc-16.2.0` is a file the preprocessor has looked at, whether or not it read it. Three fields carry the whole include story.

| Field | Meaning |
|---|---|
| `cmacro` | the macro whose being defined means this file need not be read again |
| `once_only` | `#pragma once` or `#import`, so it is never read again regardless |
| `stack_count` | how many times this file has been pushed on the buffer stack |

`cmacro` at `libcpp/files.cc:80@releases/gcc-16.2.0` is `nothing` until the file has been read to the end at least once, because working out the guard requires reading the file. The first inclusion of a guarded header therefore costs a full read and a full lex. The saving is on the second and later inclusions, and section 5.5 measures it.

### 2.8 The directives

`DIRECTIVE_TABLE` at `libcpp/directives.cc:151@releases/gcc-16.2.0` holds **22** directives, each with a handler, an origin and a set of flags, and expands into a prototype list, an enum and an array. The origin is one of `KANDR`, `STDC89`, `STDC23` or `EXTENSION`, which is how `-pedantic` knows what to complain about.

Two of the flags matter outside `directives.cc`. `IF_COND` marks four directives, and it is misnamed: three of them open a conditional, `#ifdef`, `#ifndef` and `#if`, and the fourth is `#define`. What the flag really means is that this directive will look after the include guard state itself, and section 3.7 says what that state is. `#define` carries it because `do_define` reads `mi_valid` at `libcpp/directives.cc:700@releases/gcc-16.2.0` before clearing it at `libcpp/directives.cc:720@releases/gcc-16.2.0`, and what it reads it for is the check behind `-Wheader-guard`. `EXPAND` marks the directives whose line is macro expanded before it is read, which is `#include`, `#if`, `#elif`, `#line`, `#include_next`, `#import` and `#embed`, and is why `#include HEADER` works and `#ifdef FOO` does not expand `FOO`.

## 3. Algorithms

### 3.1 From bytes to a line of tokens

`_cpp_clean_line` at `libcpp/lex.cc:877@releases/gcc-16.2.0` runs first on every logical line. It removes trailing whitespace, joins lines ending in a backslash, and normalizes the line ending, recording each thing it did as a note. `_cpp_process_line_notes` at `libcpp/lex.cc:1082@releases/gcc-16.2.0` replays those notes later so that a diagnostic can point at the column in the file the user wrote rather than the column in the line libcpp made.

This is where translation phases 1 to 3 of the C standard happen, and libcpp does not run them as separate passes over the whole file. Trigraph replacement, line splicing and comment removal all happen a line at a time as the lexer needs them, which is observable: a `\` at the end of a line inside a `//` comment continues the comment, because splicing happened before the comment was recognized.

`_cpp_lex_direct` at `libcpp/lex.cc:3888@releases/gcc-16.2.0` produces one token. `_cpp_lex_token` at `libcpp/lex.cc:3725@releases/gcc-16.2.0` wraps it and is the one the rest of the library calls, because it is the layer that handles directives, skipped conditional branches and the end of a file.

```text
_cpp_lex_token(pfile):
    loop
        token = _cpp_lex_direct(pfile)
        if token.flags has BOL and token is '#' and not in a directive
            if _cpp_handle_directive(pfile, indented)
                continue                       # the directive consumed the line
        if in a directive or a deferred pragma
            break                              # never skip inside one
        pfile.mi_valid = false                 # a token outside a directive kills the guard
        if not skipping or token is CPP_EOF
            break
    return token
```

The assignment at `libcpp/lex.cc:3796@releases/gcc-16.2.0` is one line of the include guard state machine and is placed here rather than in `directives.cc` because this is the only place that sees a token which is not part of a directive.

### 3.2 Getting a token

`cpp_get_token_1` at `libcpp/macro.cc:3006@releases/gcc-16.2.0` is the loop everything above libcpp turns. Its state is a stack of contexts: the base context is the file, and each macro under expansion pushes a context holding the tokens it has yet to hand out.

```text
cpp_get_token_1(pfile) -> Token
    complexity: O(1) amortized, unbounded in the worst case for one call

    loop
        context = pfile.context
        if context is the base context
            result = _cpp_lex_token(pfile)
        else if context has tokens left
            result = next token from context
            if result.flags has PASTE_LEFT
                paste_all_tokens(pfile, result)          # section 3.5
                return padding_token(pfile, result)
        else
            pop the context
            return the avoid_paste token                 # a padding token

        if result.type != CPP_NAME
            break
        node = result.val.node
        if node.type == NT_VOID or result.flags has NO_EXPAND
            break
        if node.flags has NODE_DISABLED
            result = a copy of result with NO_EXPAND set # section 3.6
            break
        if pfile.state.prevent_expansion
            break
        if enter_macro_context(pfile, node, result)      # section 3.3
            return padding_token(pfile, result)
    return result
```

One call can do an unbounded amount of work, because entering a macro context may collect arguments, which reads more tokens, which may open a file. The complexity worth stating is the other one: the total work over a translation unit is linear in the number of tokens produced, and a macro whose expansion is quadratic is quadratic because it produces quadratically many tokens, not because any step here is superlinear.

Two of the returns hand back a padding token rather than the thing the caller asked for. That is the mechanism by which a macro boundary survives into the output.

The block above leaves out three things the real loop does, all of them in the same place, between recognizing a name and expanding it. A macro the client promised to supply later is fetched through `cpp_get_deferred_macro` at `libcpp/macro.cc:3066@releases/gcc-16.2.0`, which is how a C++ module's macros arrive. A macro flagged `NODE_CONDITIONAL` asks the client whether to expand it at all, at `libcpp/macro.cc:3097@releases/gcc-16.2.0`. And inside a directive every one of the returns above becomes a `continue` instead, because a directive line has no room for padding. None of the three changes what happens to an ordinary macro in an ordinary C file, which is what sections 5.3 and 5.4 record.

### 3.3 Entering a macro

`enter_macro_context` at `libcpp/macro.cc:1527@releases/gcc-16.2.0` decides whether this occurrence of a macro name is an invocation, and if it is, builds the replacement list and pushes it as a context.

```text
enter_macro_context(pfile, node, result) -> 0, 1 or 2
    complexity: O(body + total argument length), plus prescanning each argument

    pfile.mi_valid = false                      # a macro invalidates the guard

    if node is a user macro
        macro = node.value.macro
        if macro.fun_like
            args = funlike_invocation_p(pfile, node)
            if args is nothing
                return 0                        # the name, alone, is not an invocation
            if macro.paramc > 0
                replace_args(pfile, node, macro, args)   # pushes the context itself
        node.flags = node.flags or NODE_DISABLED         # section 3.6
        if macro.paramc == 0
            push macro.exp.tokens as a context
        if any deferred pragma turned up in an argument
            push those tokens as a further context
            return 2
        return 1

    return builtin_macro(pfile, node, ...)      # computes a value and pushes it
```

`funlike_invocation_p` at `libcpp/macro.cc:1463@releases/gcc-16.2.0` reads forward past any number of padding tokens, and if what it finds is not `(` it puts the token back with `_cpp_backup_tokens` at `libcpp/macro.cc:3379@releases/gcc-16.2.0` and reports no invocation. Reading forward is the reason a function-like macro at the very end of a file does not hang: the lookahead hits `CPP_EOF` and backs up.

`collect_args` at `libcpp/macro.cc:1249@releases/gcc-16.2.0` reads the arguments, counting bracket depth and treating a comma at depth zero as a separator. A comma inside a nested `(...)` is part of an argument, and a comma inside `[...]` or `{...}` is not, which is why a macro invoked with a compound literal or a template argument list needs extra brackets. It also checks the argument count, calling `_cpp_arguments_ok` at `libcpp/macro.cc:1431@releases/gcc-16.2.0` before it returns, so a wrong count reaches `enter_macro_context` as an empty answer indistinguishable from a name with no bracket after it, and the name is printed as itself.

### 3.4 Prescan and stringification

`replace_args` at `libcpp/macro.cc:1987@releases/gcc-16.2.0` builds the replacement list, and the order it does two things in is the answer to the most common macro question there is.

```text
replace_args(pfile, node, macro, args) -> sequence of Token
    complexity: O(body + total expanded argument length)

    for each parameter i used in the body
        if the body uses #i
            args[i].stringified = stringify_arg(pfile, args[i].raw)
        if the body uses i without # or ## next to it
            args[i].expanded = expand_arg(pfile, args[i])   # the prescan
        # if the body only uses i next to # or ##, neither is computed

    for each token t in the body
        if t is a macro argument
            append the stringified, expanded or raw form, as the body demands
        else
            append t
```

`expand_arg` at `libcpp/macro.cc:2768@releases/gcc-16.2.0` is the prescan: an argument is fully macro expanded before it is substituted, unless the parameter it is bound to is an operand of `#` or `##`. `stringify_arg` at `libcpp/macro.cc:931@releases/gcc-16.2.0` uses the raw form, spelling each token and separating them by one space where `PREV_WHITE` says there was whitespace.

That exception is why `#define STR(x) #x` gives the parameter's spelling and the two step `#define XSTR(x) STR(x)` gives its expansion. In `XSTR(PLUS)` the parameter of `XSTR` is not next to a `#`, so it is prescanned to `+`, and `STR` then stringifies the token it was handed. Section 5.4 records both.

### 3.5 Pasting

`paste_all_tokens` at `libcpp/macro.cc:1098@releases/gcc-16.2.0` handles a run of `##` operators left to right, and `paste_tokens` at `libcpp/macro.cc:1029@releases/gcc-16.2.0` does one paste. The implementation is the specification here, because it is not what most people picture.

```text
paste_tokens(pfile, plhs, rhs) -> ok or error
    complexity: O(length of the two spellings)

    buf = spell(plhs) followed by spell(rhs), then a newline
    if plhs is '/' and rhs is not '='
        insert a space between them                # or the buffer opens a comment
    push buf as a buffer and lex one token from it
    if the buffer is not exhausted
        the paste failed
        clear PASTE_LEFT on the left token and put both back
        error "pasting X and Y does not give a valid preprocessing token"
    return the lexed token
```

Pasting is spelling the two tokens, running the lexer over the result, and requiring that the lexer consume all of it. That is why `##` cannot make `++` out of two macros that each expand to `+`: the operands of `##` are not prescanned, so the two tokens being pasted are the identifiers `PLUS` and `PLUS`, and the lexer reads `PLUSPLUS` as one identifier. The paste succeeds and produces the wrong thing, which is worse than failing. Section 5.4 records it.

The failure message is at `libcpp/macro.cc:1076@releases/gcc-16.2.0` and is an error rather than a warning for every language except assembler.

### 3.6 Why an expansion does not recurse

The standard says a macro name found while rescanning its own replacement list is not expanded, and that thereafter it is never expanded again anywhere, even by a later scan. GCC implements that in two flags.

```text
on entering a macro context:      node.flags |= NODE_DISABLED
on leaving it (_cpp_pop_context): node.flags &= ~NODE_DISABLED
on meeting a disabled name:       hand back a copy with NO_EXPAND set
```

The first is at `libcpp/macro.cc:1590@releases/gcc-16.2.0` and the third is in `cpp_get_token_1` at `libcpp/macro.cc:3129@releases/gcc-16.2.0`, which allocates a temporary token with `_cpp_temp_token` at `libcpp/lex.cc:3460@releases/gcc-16.2.0` rather than modifying the one in the macro body, because the body is shared by every invocation.

`NODE_DISABLED` alone would not be enough. It is cleared when the context pops, so a name that survived into the output while disabled would be expandable again by the time somebody rescanned it. `NO_EXPAND` is on the token rather than on the node, so it travels with the token forever. The two together are what the standard calls painting the identifier blue.

The consequence a reader can check: `#define foo foo + 1` terminates and produces `foo + 1`, and a pair of macros that name each other produces one of the two names unchanged. Section 5.4 records both.

### 3.7 The multiple include optimization

A header wrapped in `#ifndef GUARD / #define GUARD / ... / #endif` is skipped on its second inclusion without being opened. Getting that right requires proving that the conditional wraps the entire file, and libcpp proves it with three variables and four assignments rather than with a scan.

```text
state:  mi_valid   is the file still a candidate
        mi_cmacro  the controlling macro, once one is known

on stacking a file            mi_valid = true,  mi_cmacro = nothing
in _cpp_handle_directive      if the directive does not have IF_COND: mi_valid = false
in push_conditional           ifs.mi_cmacro = cmacro if (mi_valid and mi_cmacro == nothing)
                                            else nothing
in do_define                  mi_valid = false        # after reading it, for -Wheader-guard
in _cpp_lex_token             mi_valid = false        # any token outside a directive
in enter_macro_context        mi_valid = false        # any macro invocation
in do_else and do_elif        ifs.mi_cmacro = nothing  # a guard has no else branch
in do_endif                   if this is the outermost #if and ifs.mi_cmacro is set
                                  mi_valid = true, mi_cmacro = ifs.mi_cmacro
in _cpp_pop_file_buffer       if mi_valid: file.cmacro = mi_cmacro
                              mi_valid = false        # for the file that included this one
```

Nine places touch two variables, and nothing anywhere scans the file. The clearing in `_cpp_handle_directive` is at `libcpp/directives.cc:504@releases/gcc-16.2.0`, the two in `do_else` and `do_elif` are at `libcpp/directives.cc:2670@releases/gcc-16.2.0` and `libcpp/directives.cc:2771@releases/gcc-16.2.0`, and the test in `push_conditional` at `libcpp/directives.cc:2843@releases/gcc-16.2.0` carries a comment saying it is effectively a test for top of file, and that is the trick: `mi_valid` starts true and is cleared by the first token or directive that is not the opening conditional, so if it is still true when a conditional opens, nothing preceded that conditional. The assignment in `do_endif` at `libcpp/directives.cc:2807@releases/gcc-16.2.0` sets it back, and the assignment in `_cpp_lex_token` clears it again the moment a token appears after the `#endif`. Whatever survives to `_cpp_pop_file_buffer` at `libcpp/files.cc:2326@releases/gcc-16.2.0` is a guard that covered the whole file.

The check that uses it is in `is_known_idempotent_file` at `libcpp/files.cc:840@releases/gcc-16.2.0`, three lines at `libcpp/files.cc:858@releases/gcc-16.2.0`: if the file has a `cmacro` and that macro is defined, do not stack the file.

This is why one declaration after the `#endif` costs the optimization and a comment does not. A comment produces no token. Section 5.5 measures both.

`#pragma once` reaches the same result by a different and more expensive road. `has_unique_contents` at `libcpp/files.cc:880@releases/gcc-16.2.0` compares the newly read file against every once-only file already seen whose size and modification time match, byte for byte, so that the same header reached through two different paths is recognized. That is a read and a `memcmp` per candidate, where the guard is a pointer test.

### 3.8 Printing, and where the space comes from

`preprocess_file` at `gcc/c-family/c-ppoutput.cc:89@releases/gcc-16.2.0` is the `-E` client. It calls `cpp_get_token` in a loop in `scan_translation_unit` at `gcc/c-family/c-ppoutput.cc:400@releases/gcc-16.2.0` and hands each token to `token_streamer::stream` at `gcc/c-family/c-ppoutput.cc:218@releases/gcc-16.2.0`, which is where the output's shape is decided.

```text
stream(pfile, token, loc)
    if token.type == CPP_PADDING
        avoid_paste = true
        remember the token this padding stands for
        return                                  # nothing is printed for padding

    if avoid_paste
        if the line changed:  emit a line marker and a space
        else if the remembered token had PREV_WHITE
             or cpp_avoid_paste(pfile, previous printed token, token)
             or this is the first token and it is '#'
            print one space
    else if token.flags has PREV_WHITE and token is not a pragma
        print one space

    avoid_paste = false
    print the token
```

Two independent reasons to print a space, and the first one is not in any input file. When a macro expansion ends, `cpp_get_token_1` hands back a padding token, `avoid_paste` becomes true, and the printer then asks `cpp_avoid_paste` at `libcpp/lex.cc:4728@releases/gcc-16.2.0` whether printing the next token against the previous one would change what the pair lexes as. If it would, a space goes in.

`cpp_avoid_paste` is a switch on the left token's type with the right token's first character in hand. It opens with a range test, `(int) a <= (int) CPP_LAST_EQ && c == '='`, which is the ordering constraint of section 2.2 being spent, and then has **22** case labels in **17** arms, `CPP_PRAGMA` sharing its answer with `CPP_NAME` and the five string types sharing one between them. Its own comment at `libcpp/lex.cc:4723@releases/gcc-16.2.0` says the function is conservative and will occasionally advise a space where none is needed.

Line markers are the other half of the printer. `maybe_print_line_1` at `gcc/c-family/c-ppoutput.cc:541@releases/gcc-16.2.0` decides between printing newlines and printing a marker:

```text
maybe_print_line_1(loc, stream) -> was a marker printed
    if the previous line had output on it, end it
    if line markers are wanted
       and the target line is ahead of the current line by less than 8
       and the file has not changed
        print that many newlines
        return false
    print_line_1(loc, "", stream)
    return true
```

Eight is a literal in the source at `gcc/c-family/c-ppoutput.cc:557@releases/gcc-16.2.0`. It is the point where a run of blank lines costs more bytes than a marker.

`print_line_1` at `gcc/c-family/c-ppoutput.cc:592@releases/gcc-16.2.0` writes the marker itself, quoting the filename, and appends the system header flags:

```text
# LINE "FILE" [FLAGS]
```

The flags after the filename are documented at `gcc/doc/cpp.texi:4072@releases/gcc-16.2.0`: `1` entering a file, `2` returning to one, `3` a system header, `4` an implicit `extern "C"` block. `1` and `2` are passed in by the caller. `3` and `4` are computed here from `in_system_header_at`, at `gcc/c-family/c-ppoutput.cc:621@releases/gcc-16.2.0`, and are the reason a marker for a header in `/usr/include` carries a `3` that the header itself never asked for.

`-P` is one variable, `flag_no_line_commands`, tested at `gcc/c-family/c-ppoutput.cc:555@releases/gcc-16.2.0` and again at `gcc/c-family/c-ppoutput.cc:601@releases/gcc-16.2.0`. With it set, no marker is printed and the output loses the only record of which file each line came from.

## 4. Invariants

**I1.** A token's `src_loc` is a key into the line map and is meaningless without it. Nothing in libcpp compares two locations numerically for anything but ordering within one map.
Established by: `linemap_add` at `libcpp/line-map.cc:570@releases/gcc-16.2.0` allocating keys in increasing order. Checked by: nothing. May be broken by: nobody. Worth stating because a `location_t` is an integer and printing it looks like it should mean something.

**I2.** Every identifier token in the translation unit points at the same `cpp_hashnode` for that spelling.
Established by: the interning hash table. Checked by: nothing. May be broken by: nobody. This is what makes `NODE_DISABLED` a workable mechanism: setting a flag on one node disables a name everywhere at once, which is what the standard asks for.

**I3.** A macro is disabled for exactly the interval during which its own replacement list is being rescanned, and a name that escapes that interval unexpanded is unexpandable forever.
Established by: `NODE_DISABLED` set at `libcpp/macro.cc:1590@releases/gcc-16.2.0` and cleared in `_cpp_pop_context` at `libcpp/macro.cc:2856@releases/gcc-16.2.0`, and `NO_EXPAND` set at `libcpp/macro.cc:3131@releases/gcc-16.2.0`. Checked by: nothing. May be broken by: nobody. Both halves are required, and section 3.6 says why one is not enough.

**I4.** The operands of `#` and `##` are never macro expanded, and every other use of a parameter is fully macro expanded before substitution.
Established by: `replace_args` at `libcpp/macro.cc:1987@releases/gcc-16.2.0` computing the expanded form only for parameters that need it. Checked by: nothing. May be broken by: nobody. This is the invariant the two step stringify idiom exists to work around.

**I5.** A file with a controlling macro is not opened again while that macro is defined, and `cmacro` is set only for a conditional that covered the whole file.
Established by: the state machine of section 3.7. Checked by: nothing, and there is no assertion anywhere that a file skipped this way would in fact have produced no tokens. May be broken by: `#undef` of the guard macro, which makes the file readable again and is a supported thing to do.

**I6.** `cpp_avoid_paste` may return true when no space is needed, and may not return false when one is.
Established by: the comment at `libcpp/lex.cc:4723@releases/gcc-16.2.0` stating the first half, and by the switch covering every left-hand type that can begin a longer token. Checked by: `tests/test_cpp.py`, which compares the case labels in the pinned tree against a table of witness pairs and fails when GCC grows a case. May be broken by: a new token type added without a case, which is the failure the test exists to catch.

**I7.** The printed output of `-E` is not the input with substitutions applied, and no property of it may be relied on beyond lexing to the same token sequence.
Established by: sections 3.8 and 2.1, and by `PREV_WHITE` being one bit. Checked by: nothing. May be broken by: nobody. Stated because build systems do rely on it, and a change to the spacing rules is not a bug in GCC.

**I8.** Padding tokens are visible to the client of `cpp_get_token` and are not preprocessing tokens.
Established by: `cpp_get_token_1` returning them at three points in section 3.2. Checked by: nothing. May be broken by: nobody. A client that forgets them, as `funlike_invocation_p` must not, will read the token after a macro expansion as the token immediately after the macro name.

**I9.** A directive is recognized only if the `#` is the first token on a logical line, and a `#` produced by a macro expansion never begins one.
Established by: the `BOL` flag test in `_cpp_lex_token` and the check in `_cpp_handle_directive` at `libcpp/directives.cc:454@releases/gcc-16.2.0`. Checked by: nothing. May be broken by: nobody. The comment at `libcpp/directives.cc:507@releases/gcc-16.2.0` calls the code that enforces the second half a kluge and gives `#define HASH #` as the case it exists for.

*To be written: the invariants about buffer lifetime, and about what a client may hold across a call to `cpp_get_token`.*

## 5. Observable behaviour

Corpus entry `f02`, in `corpora/cpp/f02.json`, holds five macro tables, six expansions, thirty eight probed token pairs and four include traces, recorded on two configurations of GCC 16.2.0: a Homebrew build for `aarch64-apple-darwin24` and the Compiler Explorer build for `x86_64-linux-gnu`. The source spans it cites are in `corpora/source/f02.json`.

### 5.1 The macro table before a line is read

The program is one comment. The flag is `-dM -E`.

| | aarch64-apple-darwin24 | x86_64-linux-gnu |
|---|---|---|
| macros defined | 443 | 408 |
| function-like | 15 | |
| defined to nothing | 3 | |
| names on both | 373 | 373 |
| names on one only | 70 | 35 |
| names on both, different values | 50 | 50 |

Neither is a subset of the other, and 50 names are defined on both sides to different text, which is the set `#ifdef` cannot see. `__SIZEOF_LONG_DOUBLE__` is 8 against 16, `__INT_FAST16_TYPE__` is `short int` against `long int`, `__WINT_TYPE__` is `int` against `unsigned int`, and `__USER_LABEL_PREFIX__` is `_` against empty.

What moves the count is not what a reader expects.

| flags | effect on the table |
|---|---|
| `-O2` | adds `__OPTIMIZE__`, removes `__NO_INLINE__`, count unchanged |
| `-std=c23` | adds `__STRICT_ANSI__`, changes no value at all |
| `-ffast-math` | adds 7 names, changes 3, including `__GCC_IEC_559` from 2 to 0 |

The `-std=c23` row is the one worth reading twice. The default for this compiler is `gnu23`, so the flag people reach for to select the language version selects a version that was already in force, and the only observable change is that the GNU extensions stop being advertised.

### 5.2 What a dump of every macro leaves out

19 of the 20 names in `builtin_array` do not appear in `-dM` output. `__STDC__` does, for the reason in section 2.6. `__FILE__` and `__LINE__` are absent from a dump that claims to print every macro, and are defined.

### 5.3 A space that is in no input file

```text
#define EMPTY
a+EMPTY+b
```

`gcc -E -P` prints `a+ +b`. Text substitution gives `a++b`. The difference is one space and nothing else, and it is there because the empty expansion left a padding token and `cpp_avoid_paste` was asked whether `+` may be printed against `+`.

38 pairs of tokens were probed by putting them next to each other with nothing between them and preprocessing the result. 29 came back separated by a space. The 9 that did not are `+-`, `x+`, `*&`, `][`, `;;`, `&|`, `!!`, `~x` and `1]`, none of which lexes as a single token. The rule fires on the pairs that would change meaning and on no others.

### 5.4 Expansion

| program | output |
|---|---|
| `CAT(a, b)` with `#define CAT(x, y) x ## y` | `ab` |
| `CAT(PLUS, PLUS)` with `#define PLUS +` | `PLUSPLUS` |
| `STR(PLUS)` with `#define STR(x) #x` | `"PLUS"` |
| `XSTR(PLUS)` with `#define XSTR(x) STR(x)` | `"+"` |
| `foo` with `#define foo foo + 1` | `foo + 1` |
| `A` with `#define A B` and `#define B A` | `A` |
| `f(1)` with `#define f(x) [x]` | `[1]` |
| `f` with the same | `f` |
| `f (2)` with the same | `[2]` |

Every one of these is the same on both targets, which is what makes them facts about the language rather than about a machine.

### 5.5 Include guards

Four headers, each included twice, differing by one line.

| header | after the `#endif` | opens |
|---|---|---|
| `clean.h` | nothing | 1 |
| `untidy.h` | a comment | 1 |
| `stray.h` | one declaration | 2 |
| `bare.h` | no guard at all | 2 |

The comment costs nothing because it produces no token. The declaration costs the optimization, and `stray.h` is read, lexed and skipped a second time for one `typedef`.

`-H` prints no guard advice for any of these four, which looks like a broken experiment and is the specification. `report_missing_guard` at `libcpp/files.cc:2203@releases/gcc-16.2.0` reports a file only when `file->stack_count == 1`, at `libcpp/files.cc:2217@releases/gcc-16.2.0`, so the advice arrives for a file that has not yet cost anything and never for the one that has. The same four headers included once each do produce the report, naming `bare.h` and `stray.h`.

### 5.6 Line markers

Four lines of C, two of them `#include`, preprocessed with markers left in, which is the default.

```text
# 0 "markers.c"
# 0 "<built-in>"
# 0 "<command-line>"
# 1 "markers.c"
# 1 "clean.h" 1


int clean_thing;
# 2 "markers.c" 2
int before;
# 1 "stray.h" 1
```

Four markers before a byte of the program, naming three files, two of which are not files. The two blank lines after entering `clean.h` are the guard's `#ifndef` and `#define`, printed as newlines rather than as a marker because the gap is under 8 lines, which is the rule of section 3.8 in the output. The `1` after a filename is entering, the `2` is returning, and `# 4 "markers.c" 2` after `stray.h` is the return jumping over two lines that produced nothing.

### 5.7 What one include costs

Two lines of C, `#include <stdio.h>` and a `puts` call.

| | aarch64-apple-darwin24 | x86_64-linux-gnu |
|---|---|---|
| files opened | 42 | 31 |
| distinct files | 38 | 25 |
| deepest nesting | 6 | 6 |
| files in common | 0 | 0 |

Not one path appears on both sides. The header is the same header in the standard's sense and shares no file with itself across two machines.

*To be written: `-dD`, `-dU` and `-dI` as observable output, and what `-fdirectives-only` changes.*

## 6. Edge cases and error paths

- **A function-like macro name with no following bracket.** Not an invocation. The name is printed as itself. The lookahead in `funlike_invocation_p` backs up whatever it read, including through a newline, so a macro name at the end of one line and a bracket at the start of the next is an invocation.
- **A paste that does not lex.** `paste_tokens` reports `pasting X and Y does not give a valid preprocessing token` at `libcpp/macro.cc:1076@releases/gcc-16.2.0`, clears `PASTE_LEFT`, and emits both operands separately. This is an error for every language except `CLK_ASM`.
- **A paste that lexes as the wrong thing.** No diagnostic, because from the lexer's point of view nothing went wrong. Section 5.4's `PLUSPLUS` is this case.
- **Wrong argument count.** `macro %qs requires %u arguments, but only %u given` at `libcpp/macro.cc:1219@releases/gcc-16.2.0`, or `macro %qs passed %u arguments, but takes just %u` at `libcpp/macro.cc:1224@releases/gcc-16.2.0`, each followed by a note pointing at the definition.
- **An unterminated argument list.** `unterminated argument list invoking macro %qs` at `libcpp/macro.cc:1423@releases/gcc-16.2.0`, raised when the collector reaches the end of the file with brackets open.
- **`#` not followed by a parameter, in a function-like macro.** `libcpp/macro.cc:3812@releases/gcc-16.2.0`. In an object-like macro `#` is an ordinary token.
- **`##` at either end of a replacement list.** `libcpp/macro.cc:3696@releases/gcc-16.2.0`, and a separate message for `__VA_OPT__` at `libcpp/macro.cc:94@releases/gcc-16.2.0`.
- **Include recursion.** The depth limit is 200, set in `cpp_create_reader` at `libcpp/init.cc:235@releases/gcc-16.2.0` and enforced at `libcpp/directives.cc:947@releases/gcc-16.2.0`. The message names `-fmax-include-depth`.
- **A header reached by two different paths.** With `#pragma once`, recognized by comparing contents, at the cost described in section 3.7. With an include guard, recognized because the guard macro is defined, at no cost. Without either, read twice.
- **A guard macro that is undefined between inclusions.** The file is read again. This is supported and is how a header meant to be included several times with different macros set is written.
- **A guard whose `#ifndef` and `#define` name different macros.** `do_define` records the mismatch at `libcpp/directives.cc:715@releases/gcc-16.2.0` and `_cpp_pop_file_buffer` warns at `libcpp/files.cc:2337@releases/gcc-16.2.0`, `header guard X followed by #define of a different macro`, but only under `-Wheader-guard` and only when the front end's spelling corrector says the two names are close enough to be a typo. Without the warning the header still works and is read every time, which is the failure this exists to catch.
- **An `#if` whose expression cannot be evaluated.** Out of scope for this document, and in `libcpp/expr.cc`. The one thing it contributes here is that a `#if defined(X)` at the top of a file can be a controlling macro, recorded through `mi_ind_cmacro` at `libcpp/expr.cc:1243@releases/gcc-16.2.0`.

*To be written: what happens when a file disappears between the `stat` and the `open`, and the behaviour of a directive inside a macro argument list.*

## 7. Interactions

libcpp is called by every C family front end and by nothing else in GCC. The client supplies a `cpp_callbacks` at `libcpp/include/cpplib.h:783@releases/gcc-16.2.0`, which is how the preprocessor tells the front end about a `#define`, an `#include`, a line change or a pragma without knowing what a front end is. The `-E` printer is a client that implements those callbacks by printing, at `gcc/c-family/c-ppoutput.cc:704@releases/gcc-16.2.0` and after.

The line map is shared. libcpp owns `line_table` and every `location_t` in the compiler, including ones attached to GIMPLE statements thousands of passes later, is a key into the same structure this document's tokens use. `trace_include` at `libcpp/line-map.cc:1592@releases/gcc-16.2.0`, which is what `-H` prints, lives there rather than in `files.cc` for that reason.

The macro table is written by three parties: libcpp for the built-ins of section 2.6, `gcc/c-family/c-cppbuiltin.cc` for the language and machine macros, and the target through `TARGET_CPU_CPP_BUILTINS`. Section 5.1's count is the sum, and only the first of the three is in this document.

Options reach libcpp as a `cpp_options` at `libcpp/include/cpplib.h:359@releases/gcc-16.2.0`, filled in by the front end from the command line. The ones that change the algorithms here rather than the diagnostics are `lang`, which selects the standard and therefore the token types that exist, `traditional`, which selects a different preprocessor entirely, and `max_include_depth`.

*To be written: the PCH interaction, and what `-fdirectives-only` does to the lexer.*

## 8. Conformance

GCC's own tests for the preprocessor are in `gcc/testsuite/gcc.dg/cpp`, which is several hundred files, and in `libcpp`'s share of `gcc/testsuite/gcc.dg/`. The subsets that bear on this document are the `macro` family for sections 3.3 to 3.6, `mi*.c` for the multiple include optimization of section 3.7, and `avoidpaste1.c` and `avoidpaste2.c` for the spacing rule of section 3.8, which are the only tests anywhere that assert what `-E` output looks like rather than what it means.

This project's own check is `tests/test_cpp.py`, which is not a conformance suite for GCC. It checks that the reader in `gxray.cpp` agrees with the source: that its table of paste-avoiding pairs covers exactly the 22 case labels of `cpp_avoid_paste` in the pinned tree, minus the six about pragmas and user-defined literal suffixes that a `-E` of a C file cannot produce, plus the range test before the switch, which is a reason without a label, that the range test is still written the way the reader assumes, that the advice condition of section 5.5 is still `file->stack_count == 1`, and that every line marker flag the reader names is one `gcc/doc/cpp.texi` documents.

*To be written: the invariants of section 4 restated as assertions, and which of them the recorded corpus can check.*

## 9. Port notes

The preprocessor's algorithms are target independent and its output is not. Nothing in sections 3.1 to 3.8 asks the target anything. Everything in section 5.1 is the target answering.

| | aarch64-apple-darwin24 | x86_64-linux-gnu |
|---|---|---|
| macros before the first line | 443 | 408 |
| files opened by one `#include <stdio.h>` | 42 | 31 |
| distinct files | 38 | 25 |
| files in common with the other column | 0 | 0 |
| expansion results that differ | 0 of 6 | 0 of 6 |

The last row is the one that says where the boundary is. Two compilers that share no header file and disagree about 50 macro values agree exactly on what `#define foo foo + 1` does, because that is the language and the rest is the machine.

**What is forced and what is not.** The token stream interface is forced by the standard, which defines translation in terms of preprocessing tokens rather than text, and any implementation that works in text will get section 5.3 wrong. The one bit of whitespace in `PREV_WHITE` is not forced: an implementation that wanted `-E` output to round trip could keep a column and reproduce the original spacing, at the cost of a wider token. GCC's choice makes the token small and makes the output a rendering, and I7 is the consequence.

Interning every identifier is not forced either, but `NODE_DISABLED` depends on it. An implementation that compared macro names by string would need the disabled set to live somewhere else, and the obvious somewhere else is a set on the expansion stack, which turns section 3.6 from two flag assignments into a search.

The multiple include optimization is entirely optional and entirely worth it. An implementation may read a guarded header a hundred times and get the same answer, slowly. What is not optional, if the optimization is implemented, is the exactness of the condition: a file with one token after its `#endif` must be read again, and section 5.5 is what that looks like when it works.

The 8 in section 3.8's line marker rule and the 200 include depth are both arbitrary. Nothing else in this document is a number a reimplementation gets to choose.
