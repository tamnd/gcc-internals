# BP-CPARSE, the C parser

**Status:** partial
**Applies to:** GCC 16.2.0 (tag `releases/gcc-16.2.0`)
**Target-dependent:** no
**Generated sections:** none
**Last verified:** 2026-09-06 against `releases/gcc-16.2.0`

This document specifies the C front end's parser: the code in `gcc/c/c-parser.cc` and `gcc/c/c-parser.h` that turns the token stream libcpp produced into calls on the tree building interface in `gcc/c/c-decl.cc` and `gcc/c/c-typeck.cc`. The token, the parser state, the four slot lookahead buffer and the identifier classification are specified field by field. Lexing one token, peeking, consuming, the three disambiguations C cannot make without a symbol table, error reporting, fix-it insertion, caret placement and the four recovery routines are specified as algorithms. Semantic analysis, the tree building interface, attributes, OpenMP, OpenACC, Objective-C, transactional memory and the `__RTL` and `__GIMPLE` function body parsers are named and not specified, and each place that stops short says so. Nothing here is generated, because the parser keeps no tables in `.def` files: its grammar is control flow and its keyword set is a C enum. What exists instead is `gxray.cparse`, a reader for recorded diagnostics, with tests that compare its transcription of `get_missing_token_insertion_kind` and of the thirteen `c_parse_error` branches against the pinned tree, so a GCC that grows a case fails the build rather than making a paragraph quietly false.

## 1. Purpose and scope

The C parser is a hand written recursive descent parser. There is no grammar file, no generated table and no parser generator anywhere in the C front end. The file header at `gcc/c/c-parser.h:4@releases/gcc-16.2.0` records that the actions came from an older Bison parser and that the structure was influenced by the C++ parser, and the Bison grammar itself has been gone since GCC 4.1.

The parser's contract with the code above it is one function. `c_parse_file` at `gcc/c/c-parser.cc:31269@releases/gcc-16.2.0` is called once per translation unit by the language hook `c_common_parse_file`, and returns when the token stream is exhausted. Its contract with the code below it is also one function: `c_lex_with_flags` in `gcc/c/c-lex.cc`, which wraps `cpp_get_token` and is called from exactly one place in the parser, `c_lex_one_token` at `gcc/c/c-parser.cc:336@releases/gcc-16.2.0`. Everything the parser will ever know about the program arrives through that one call.

**What this document covers.** The `c_token` and `c_parser` records. The lookahead buffer and the assertions that bound it. How a preprocessing token becomes a parser token, including the symbol table lookup that decides whether an identifier names a type. The three constructs C cannot disambiguate from tokens alone, and how each is resolved. The top level parse loop. How an error is reported, where the caret goes, when a fix-it hint is offered and what offering one does to the caret. The error latch. The four skip routines that implement recovery. The conflict marker recognizer, which is the only thing in the front end that needs a fourth token of lookahead.

**What it does not cover.** Semantic analysis: everything the parser calls in `c_decl.cc`, `c-typeck.cc`, `c-convert.cc` and `c-fold.cc`, which is where declarations become `tree` nodes and where types are checked. The GENERIC the parser builds, which is `BP-GENERIC`. Attribute parsing, both the GNU `__attribute__` syntax and the C23 `[[...]]` syntax, which reaches into `gcc/c-family/c-attribs.cc` and has its own lookahead machinery in `c_parser_check_balanced_raw_token_sequence`. The OpenMP, OpenACC and Objective-C parsers, which between them are more of `c-parser.cc` than C is. Transactional memory. The `__RTL` and `__GIMPLE` body parsers at `gcc/c/c-parser.cc:31308@releases/gcc-16.2.0`, which reopen the source file and parse it again by character. Pragma dispatch beyond the point at which a `CPP_PRAGMA` token interrupts the stream. Precompiled header loading, which happens before the first ordinary token is looked at.

**Position in the pipeline.** Second. Its input is what `BP-CPP` describes and its output is what `BP-GENERIC` describes.

**Inputs and outputs as properties.** None. The `PROP_*` flags describe IR held by the middle end, and the parser produces GENERIC, which predates them. Its input is a token stream and its output is a sequence of calls that leave declarations in the symbol table and function bodies on the statement list.

## 2. Data structures

### 2.1 The token

`c_token` at `gcc/c/c-parser.h:53@releases/gcc-16.2.0`. It is not `cpp_token`. The preprocessor's token is described in section 2.1 of `BP-CPP`, and this is what the front end makes of one after string literal concatenation and after conversion of preprocessing tokens to tokens.

| Field | Type | Meaning |
|---|---|---|
| `type` | `cpp_ttype` in 8 bits | which of the token kinds this is, from libcpp's table |
| `id_kind` | `c_id_kind` in 8 bits | for a `CPP_NAME`, what the symbol table said it was |
| `keyword` | `rid` in 8 bits | for a `CPP_KEYWORD`, which keyword, otherwise `RID_MAX` |
| `pragma_kind` | `pragma_kind` in 8 bits | for a `CPP_PRAGMA`, which pragma, otherwise `PRAGMA_NONE` |
| `location` | `location_t` | a key into the line map, not a line number |
| `value` | `tree` | the payload: an `IDENTIFIER_NODE`, a constant, or `NULL_TREE` |
| `flags` | `unsigned char` | libcpp's token flags, truncated from `unsigned short` |

Two of those fields carry information libcpp did not have. `id_kind` is the answer to a symbol table query, described in section 3.2. `keyword` is set by looking the identifier up in the keyword table, which is why `CPP_KEYWORD` is a parser token type and not a preprocessor one: libcpp has no keywords, only identifiers.

`flags` is one byte here and two in `cpp_token`, so the parser sees the low eight of libcpp's thirteen flags and loses the rest. The comment at `gcc/c/c-parser.cc:1122@releases/gcc-16.2.0` records the consequence: `c_parse_error` is passed a flag word of zero, so a token whose spelling depended on a flag, such as a digraph, is reported by its canonical spelling rather than the one you wrote.

### 2.2 What an identifier turned out to be

`c_id_kind` at `gcc/c/c-parser.h:38@releases/gcc-16.2.0`. Five values, and the first two are the whole of C.

| Value | Meaning |
|---|---|
| `C_ID_ID` | an ordinary identifier |
| `C_ID_TYPENAME` | an identifier declared as a typedef name |
| `C_ID_CLASSNAME` | an Objective-C class name |
| `C_ID_ADDRSPACE` | a target defined address space qualifier |
| `C_ID_NONE` | the token is not an identifier |

`C_ID_ADDRSPACE` is the one place a target influences parsing. The names come from the port's `ADDR_SPACE_KEYWORDS`, and `targetm.addr_space.diagnose_usage` is called at classification time, at `gcc/c/c-parser.cc:392@releases/gcc-16.2.0`. Nothing else in this document is target dependent.

### 2.3 The parser

`c_parser` at `gcc/c/c-parser.cc:191@releases/gcc-16.2.0`. There is one of these per translation unit, in the global `the_parser`, and it is the parser's entire memory of the program. Fields that belong to OpenMP, Objective-C or transactional memory are listed for completeness and are out of scope.

| Field | Type | Meaning |
|---|---|---|
| `tokens` | `c_token *` | the lookahead window, normally `&tokens_buf[0]` |
| `tokens_buf` | `c_token[4]` | the buffer behind it |
| `tokens_avail` | `unsigned` | how many of the window are filled, 0 to 4 |
| `raw_tokens` | `vec<c_token, va_gc> *` | unclassified lookahead, for `[[` in Objective-C |
| `raw_tokens_used` | `unsigned` | how many of those have since been lexed properly |
| `error` | 1 bit | a syntax error is being recovered from |
| `in_pragma` | 1 bit | inside a pragma, so `CPP_PRAGMA_EOL` is not consumed automatically |
| `in_if_block` | 1 bit | parsing the outermost block of an `if` |
| `lex_joined_string` | 1 bit | libcpp should join adjacent string literals, for `#pragma pch_preprocess` |
| `translate_strings_p` | 1 bit | convert string literals to the execution character set |
| `seen_string_literal` | 1 bit | the last thing returned was a string literal |
| `last_token_location` | `location_t` | where the token most recently consumed was |
| `objc_*` | 4 bits total | Objective-C lexical context, out of scope |
| `in_transaction` | 4 bits | transactional memory, out of scope |
| `omp_*`, `in_omp_*` | pointers and a bit | OpenMP, out of scope |

Three of those fields are the subject of most of this document. `tokens_avail` bounds the lookahead. `error` is the latch that stops one mistake becoming a hundred messages. `last_token_location` is the only thing that makes a fix-it hint for a missing token possible, because a hint has to be placed after the token before the one that upset the parser, and by then that token is gone.

The struct is `GTY(())`, so it is garbage collector visible, and `tokens` is `GTY((skip))` because it points into `tokens_buf` rather than owning anything. The parser is collected at the end of the translation unit and not before; `ggc_collect` is called once per external declaration from the top level loop, and the parser survives it.

### 2.4 The lookahead window

The window is not a ring buffer and not a queue. `tokens` is a pointer that normally aims at `tokens_buf[0]`, and consuming a token shuffles the remaining entries down by one, at `gcc/c/c-parser.cc:969@releases/gcc-16.2.0`. When the parser is replaying a pre-lexed token vector, which happens for OpenMP attribute syntax, `tokens` points into that vector instead and consuming advances the pointer, and in that mode `tokens_avail` may exceed 4.

While parsing C, `tokens_avail` is at most 4 and the reachable depth is exactly 4. The comment above the struct says two, and has said two since before the fourth slot was added.

### 2.5 Operator precedence

`c_parser_prec` at `gcc/c/c-parser.h:118@releases/gcc-16.2.0`. Ten levels and a dummy bottom, used by the binary expression parser to run an operator precedence loop rather than eleven mutually recursive functions.

`PREC_NONE`, `PREC_LOGOR`, `PREC_LOGAND`, `PREC_BITOR`, `PREC_BITXOR`, `PREC_BITAND`, `PREC_EQ`, `PREC_REL`, `PREC_SHIFT`, `PREC_ADD`, `PREC_MULT`.

### 2.6 How hard to try when guessing at a type name

`c_lookahead_kind` at `gcc/c/c-parser.h:133@releases/gcc-16.2.0`. Three values, passed down to the predicate in section 3.4.

| Value | Meaning |
|---|---|
| `cla_prefer_type` | an unknown identifier here is a type name |
| `cla_nonabstract_decl` | an unknown identifier is a type name if followed by an identifier or `*` |
| `cla_prefer_id` | never guess |

## 3. Algorithms

### 3.1 The top level

```text
function parse_file (parser: Parser)
    complexity: O(n) in tokens, amortised

    if peek(parser, 1).pragma_kind == PRAGMA_GCC_PCH_PREPROCESS
        parse_pch_preprocess (parser)
    else
        no_more_pch ()

    if peek(parser, 1).type == CPP_EOF
        pedwarn ("ISO C forbids an empty translation unit")
        return

    repeat
        collect_garbage ()
        parse_external_declaration (parser)
    until peek(parser, 1).type == CPP_EOF
```

`c_parser_translation_unit` at `gcc/c/c-parser.cc:2081@releases/gcc-16.2.0`. The obstack save and restore around the body of the loop are omitted: the parser allocates its scratch on `parser_obstack` and frees back to a mark after each external declaration, so the peak scratch is one declaration rather than one file.

The loop has no error handling in it. An external declaration that fails to parse recovers inside `parse_external_declaration`, and the loop cannot tell the difference.

### 3.2 Lexing one token

```text
function lex_one (parser: Parser) -> Token
    complexity: O(1) amortised, plus whatever libcpp does

    t = Token()
    t.type = lex_with_flags (&t.value, &t.location, &t.flags)
    t.id_kind = C_ID_NONE
    t.keyword = RID_MAX
    t.pragma_kind = PRAGMA_NONE

    if t.type == CPP_NAME
        t.id_kind = C_ID_ID
        rid = rid_code (t.value)
        if rid is an address space keyword
            diagnose_address_space_usage (rid, t.location)
            t.id_kind = C_ID_ADDRSPACE
            t.keyword = rid
            return t
        if rid != RID_MAX
            t.type = CPP_KEYWORD
            t.keyword = rid
            return t
        decl = lookup_name (t.value)
        if decl != nothing and code(decl) == TYPE_DECL
            t.id_kind = C_ID_TYPENAME
        else
            t.id_kind = C_ID_ID
    else if t.type == CPP_PRAGMA
        t.pragma_kind = integer_value (t.value)
        t.value = nothing

    return t
```

`c_lex_one_token` at `gcc/c/c-parser.cc:336@releases/gcc-16.2.0`, with the Objective-C context sensitive keyword handling at `gcc/c/c-parser.cc:397@releases/gcc-16.2.0` omitted.

The `lookup_name` call is the lexer hack, and its position in this function is the whole of what makes C hard to parse and the origin of every problem in sections 3.5 and 6.4. The classification is written into the token and the token is then held in the lookahead window, so the answer is the one that was true at the moment the token was first looked at, not the one that is true when the parser gets round to using it.

`lookup_name` is not a hash table probe. It walks the scope chain in `gcc/c/c-decl.cc`, so classification cost is proportional to scope depth, and it has the side effect of marking the binding used for `-Wunused` purposes.

### 3.3 Peeking and consuming

```text
function peek (parser: Parser, n: integer) -> Token
    complexity: O(1)

    assert n > 0
    if parser.tokens_avail >= n
        return parser.tokens[n - 1]
    assert parser.tokens_avail == n - 1
    parser.tokens[n - 1] = lex_one (parser)
    parser.tokens_avail = n
    return parser.tokens[n - 1]

function consume (parser: Parser)
    complexity: O(1)

    assert parser.tokens_avail >= 1
    assert parser.tokens[0].type != CPP_EOF
    parser.last_token_location = parser.tokens[0].location
    if parser.tokens is not &parser.tokens_buf[0]
        parser.tokens = parser.tokens + 1
    else
        for i in 0 .. parser.tokens_avail - 2
            parser.tokens[i] = parser.tokens[i + 1]
    parser.tokens_avail = parser.tokens_avail - 1
    parser.seen_string_literal = false
```

`c_parser_peek_nth_token` at `gcc/c/c-parser.cc:572@releases/gcc-16.2.0` and `c_parser_consume_token` at `gcc/c/c-parser.cc:958@releases/gcc-16.2.0`. `c_parser_peek_token` and `c_parser_peek_2nd_token` are the same function specialised to n of 1 and 2.

Two properties follow from the assertion in `peek`. Lookahead has to be requested in order: asking for the third token without having asked for the second is an internal compiler error, not a longer read. And the parser can never look past the end of the file, because `peek` at 2 asserts that the first token is not `CPP_EOF` and lexing past EOF would otherwise be possible.

`consume` does not refill. The window is filled lazily, one token per peek, so a parser that never peeks past the first token never lexes past it either.

### 3.4 What starts a declaration

C's first ambiguity is that a statement and a declaration may both begin with an identifier. The parser resolves it with a predicate over up to two tokens.

```text
function starts_declaration (parser: Parser, n: integer) -> boolean
    complexity: O(1)

    t = peek (parser, n)
    if t.type == CPP_NAME and peek(parser, n + 1).type == CPP_COLON
        return false                       -- a label
    if t.keyword == RID_STATIC_ASSERT and peek(parser, n + 1).type == CPP_OPEN_PAREN
        return the balanced parenthesis run is followed by a semicolon
    if starts_declspecs (t) or t.keyword == RID_STATIC_ASSERT
        return true
    return starts_typename (parser, cla_nonabstract_decl, n)

function starts_typename (parser: Parser, la: LookaheadKind, n: integer) -> boolean
    complexity: O(1), plus one symbol table walk in the guessing branch

    t = peek (parser, n)
    if t.type == CPP_NAME
        if t.id_kind in {C_ID_TYPENAME, C_ID_ADDRSPACE, C_ID_CLASSNAME}
            return true
    if t.type == CPP_KEYWORD
        return keyword_starts_typename (t.keyword)
    if la == cla_prefer_id
        return false
    if t.type != CPP_NAME or t.id_kind != C_ID_ID
        return false
    if la != cla_prefer_type
        and peek(parser, n + 1).type not in {CPP_NAME, CPP_MULT}
        return false
    return lookup_name (t.value) == nothing
```

`c_parser_next_tokens_start_declaration` at `gcc/c/c-parser.cc:916@releases/gcc-16.2.0` and `c_parser_next_tokens_start_typename` at `gcc/c/c-parser.cc:696@releases/gcc-16.2.0`.

The last three lines are a guess and are labelled as one in the source. An identifier that is not declared at all, followed by another identifier or by a `*`, is treated as a type name that the user got wrong. This is what turns `foo bar;` into `unknown type name 'foo'` rather than into a syntax error, and it is why the two shapes it tests for are exactly the two that a misspelled type would produce.

The static assertion case is the only place in the C parser that reads an unbounded run of tokens ahead. It does so through the raw token vector rather than through the four slot window, which is what `raw_tokens` in section 2.3 is for.

### 3.5 Reclassifying a stale token

```text
function maybe_reclassify (parser: Parser)
    complexity: O(1), plus one symbol table walk

    if peek(parser, 1).type != CPP_NAME
        return
    t = peek (parser, 1)
    if t.id_kind not in {C_ID_ID, C_ID_TYPENAME}
        return
    decl = lookup_name (t.value)
    t.id_kind = C_ID_ID
    if decl != nothing and code(decl) == TYPE_DECL
        t.id_kind = C_ID_TYPENAME
```

`c_parser_maybe_reclassify_token` at `gcc/c/c-parser.cc:2326@releases/gcc-16.2.0`. It is called from five places, all of them the point at which a construct that opened a scope has closed it again: after an `if` statement at `gcc/c/c-parser.cc:8907@releases/gcc-16.2.0`, after a `switch`, after a `while`, after a `for`, and after the declaration list of an old style function definition.

The call is needed because a statement's body can be parsed while the enclosing `for` header's scope is still open, and the token after the body will already have been peeked and classified against that scope. The bug is PR67784 and the comment names it. Note what the function does not do: it does not re-peek, it overwrites `id_kind` in place, and it clears `C_ID_CLASSNAME` and `C_ID_ADDRSPACE` by not being called for them.

### 3.6 Reporting an error

```text
function report_at (parser: Parser, message: string, richloc: RichLocation) -> boolean
    complexity: O(1)

    t = peek (parser, 1)
    if parser.error
        return false
    parser.error = true
    if message == nothing
        return false

    if t.type in {CPP_LSHIFT, CPP_RSHIFT, CPP_EQ_EQ}
        loc = peek_conflict_marker (parser, t.type)
        if loc != nothing
            error_at (loc, "version control conflict marker in file")
            return true

    if parser.seen_string_literal and t.type == CPP_NAME
        header = stdlib_header_for_string_macro (spelling (t.value))
        if header != nothing
            attach_missing_header_hint (richloc, header)

    kind = t.type
    if kind == CPP_KEYWORD
        kind = CPP_NAME
    parse_error (message, kind, t.value, 0, richloc)
    return true

function report (parser: Parser, message: string) -> boolean
    complexity: O(1)

    t = peek (parser, 1)
    if t.type != CPP_EOF
        input_location = t.location
    return report_at (parser, message, RichLocation(input_location))
```

`c_parser_error_richloc` at `gcc/c/c-parser.cc:1073@releases/gcc-16.2.0` and `c_parser_error` at `gcc/c/c-parser.cc:1135@releases/gcc-16.2.0`.

Three things in that are worth stating separately. The latch is the first two lines, and it is checked before anything else, so a second error while `parser.error` is set costs nothing and produces nothing. The keyword collapse near the end means `c_parse_error` never sees `CPP_KEYWORD`, which is why `expected ';' before 'while'` uses the identifier branch of section 3.8 rather than a keyword branch, and there is no keyword branch. And `report` guards the `input_location` update on the token not being `CPP_EOF`, at `gcc/c/c-parser.cc:1009@releases/gcc-16.2.0`, so an error at end of input is reported at wherever the parser last was rather than at a location past the end of the file.

### 3.7 Requiring a token, and the caret swap

```text
function require (parser: Parser, type: TokenType, message: string,
                  matching: Location, type_is_unique: boolean) -> boolean
    complexity: O(1)

    if peek(parser, 1).type == type
        consume (parser)
        return true

    richloc = RichLocation (peek(parser, 1).location)
    if not parser.error and type_is_unique
        maybe_suggest_insertion (richloc, type, parser.last_token_location)
    folded = false
    if matching != unknown
        folded = add_location_if_nearby (richloc, matching)
    if report_at (parser, message, richloc)
        if matching != unknown and not folded
            inform (matching, "to match this %qs", symbol_for (type))
    return false

function maybe_suggest_insertion (richloc: RichLocation, type: TokenType,
                                  prev: Location)
    complexity: O(1)

    kind = insertion_kind (type)
    if kind == impossible
        return
    if kind == before_next
        hint_at = immediately before richloc.primary
    else
        hint_at = immediately after prev
    add_fixit_insert (richloc, hint_at, spelling (type))
    swap (richloc.primary, hint_at)
```

`c_parser_require` at `gcc/c/c-parser.cc:1279@releases/gcc-16.2.0`, `maybe_suggest_missing_token_insertion` at `gcc/c-family/c-common.cc:10049@releases/gcc-16.2.0` and `get_missing_token_insertion_kind` at `gcc/c-family/c-common.cc:9974@releases/gcc-16.2.0`.

`insertion_kind` is a switch over seven token types and a default:

| Token | Where the hint goes |
|---|---|
| `[` | before the token the parser is looking at |
| `(` | before the token the parser is looking at |
| `)` | after the token before it |
| `]` | after the token before it |
| `;` | after the token before it |
| `,` | after the token before it |
| `:` | after the token before it |

Every other token type gets no hint, and the last line of `maybe_suggest_insertion` never runs for it, so the caret stays on the token that upset the parser.

The swap is what puts the caret on the line above the mistake, and GCC's own comment at `gcc/c-family/c-common.cc:10012@releases/gcc-16.2.0` explains it with a diagram. The old primary location is not discarded: it becomes a secondary range on the same diagnostic, which is how an outside observer can tell a swapped diagnostic from an unswapped one without reading the source. Section 5.2 records that.

`type_is_unique` is false when the caller could accept more than one token, which in practice means the message names two, as in `expected ',' or ';'`. Suggesting an insertion when two different tokens would do is not something a fix-it hint can express, so no hint is offered and no swap happens.

### 3.8 Finishing the sentence

`c_parse_error` at `gcc/c-family/c-common.cc:7004@releases/gcc-16.2.0` takes a complaint and a token type and returns a whole sentence. It is shared with the C++ front end. The branch is chosen by the token type alone, and there are thirteen.

| Appended | Selected by |
|---|---|
| ` at end of input` | `CPP_EOF` |
| ` before %s'%c'` | the printable character constant types |
| ` before %s'\x%x'` | the same, when the value does not print |
| ` before user-defined character literal` | the `*_USERDEF` character types |
| ` before user-defined string literal` | the `*_USERDEF` string types |
| ` before string constant` | the string types |
| ` before numeric constant` | `CPP_NUMBER` |
| ` before %qE` | `CPP_NAME` |
| ` before %<#pragma%>` | `CPP_PRAGMA` |
| ` before end of line` | `CPP_PRAGMA_EOL` |
| ` before %<decltype%>` | `CPP_DECLTYPE` |
| ` before %<#embed%>` | `CPP_EMBED` |
| ` before %qs token` | everything else, by a range test |

The last branch is where every punctuation mark in the language lands, which is why the word `token` appears on the end of some of these messages and not others. Nothing about the parser's state contributes: the same complaint before the same token type produces the same sentence wherever it came from.

The printed forms of two branches collide. `%qE` on a one letter identifier and `%s'%c'` on a character constant both produce a single character in single quotes, so a reader who has only the message cannot tell which fired. Section 5.1 records that this is observable and that it is not recoverable from the text.

### 3.9 Recovery

Four routines, and which one a caller picks decides how much of your program is thrown away.

```text
function skip_until_found (parser: Parser, type: TokenType, message: string,
                           matching: Location)
    complexity: O(n) in tokens skipped

    if require (parser, type, message, matching)
        return
    depth = 0
    loop
        t = peek (parser, 1)
        if t.type == type and depth == 0
            consume (parser)
            break
        if t.type == CPP_EOF
            return
        if t.type == CPP_PRAGMA_EOL and parser.in_pragma
            return
        if t.type in {CPP_OPEN_BRACE, CPP_OPEN_PAREN, CPP_OPEN_SQUARE}
            depth = depth + 1
        else if t.type in {CPP_CLOSE_BRACE, CPP_CLOSE_PAREN, CPP_CLOSE_SQUARE}
            if depth == 0
                break
            depth = depth - 1
        consume (parser)
    parser.error = false

function skip_to_end_of_block_or_statement (parser: Parser)
    complexity: O(n) in tokens skipped

    depth = 0
    loop
        t = peek (parser, 1)
        if t.type == CPP_EOF
            return
        if t.type == CPP_PRAGMA_EOL and parser.in_pragma
            return
        if t.type == CPP_SEMICOLON and depth == 0
            consume (parser)
            break
        if t.type == CPP_CLOSE_BRACE and (depth == 0 or depth - 1 == 0)
            consume (parser)
            break
        if t.type == CPP_OPEN_BRACE
            depth = depth + 1
        else if t.type == CPP_CLOSE_BRACE
            depth = depth - 1
        else if t.type == CPP_PRAGMA
            consume the pragma up to and including its CPP_PRAGMA_EOL
            continue
        consume (parser)
    parser.error = false
```

`c_parser_skip_until_found` at `gcc/c/c-parser.cc:1353@releases/gcc-16.2.0` and `c_parser_skip_to_end_of_block_or_statement` at `gcc/c/c-parser.cc:1594@releases/gcc-16.2.0`. The other two are `c_parser_skip_to_end_of_parameter` at `gcc/c/c-parser.cc:1426@releases/gcc-16.2.0`, which stops at a comma or a semicolon at depth zero without consuming it, and `c_parser_skip_to_pragma_eol` at `gcc/c/c-parser.cc:1507@releases/gcc-16.2.0`.

All four clear `parser.error` on the way out, and that is the only way it gets cleared: there are eighteen assignments of `false` to it in the file and every one is a recovery point. Until one of them runs, no further diagnostic can be issued, which is invariant I4.

`skip_until_found` will stop at an unmatched closing bracket without consuming it, so a missing `)` does not eat the rest of the function. `skip_to_end_of_block_or_statement` will not: it consumes the semicolon or brace it stops at, so at least one token of your program is discarded even when the parser had already understood it.

### 3.10 The conflict marker

```text
function peek_conflict_marker (parser: Parser, first: TokenType) -> Location or nothing
    complexity: O(1)

    if peek(parser, 2).type != first
        return nothing
    if peek(parser, 3).type != first
        return nothing
    if peek(parser, 4).type != final_kind (first)
        return nothing
    start = peek(parser, 1).location
    if column (start) != 1
        return nothing
    return make_location (start, start, finish (peek(parser, 4).location))
```

`c_parser_peek_conflict_marker` at `gcc/c/c-parser.cc:1028@releases/gcc-16.2.0`. `final_kind` maps `CPP_LSHIFT` to `CPP_LESS`, `CPP_RSHIFT` to `CPP_GREATER` and `CPP_EQ_EQ` to `CPP_EQ`.

Seven identical characters at the start of a line lex as three two character tokens and one single, which is four tokens, which is the width of the buffer in section 2.4. This is the only caller in the C parser that reaches slot four, and it is not parsing C when it does. The column test is what stops `a << b << c << d` from being reported as a merge conflict.

## 4. Invariants

**I1.** `parser.tokens_avail` is at most 4 while parsing C, and `peek(parser, n)` is called only with `n <= parser.tokens_avail + 1`.
Established by: the callers. Checked by: `gcc_assert` in `c_parser_peek_nth_token` and `c_parser_peek_2nd_token` at `gcc/c/c-parser.cc:560@releases/gcc-16.2.0`, unconditionally, not only under `--enable-checking`. May be broken by: replay from a pre-lexed token vector, where `tokens_avail` may exceed 4 and `tokens` does not point into `tokens_buf`, for the duration of an OpenMP attribute syntax pragma.

**I2.** `parser.tokens[0].type` is never `CPP_EOF` when `consume` is called.
Established by: every caller, which peeks before it consumes. Checked by: `gcc_assert` in `c_parser_consume_token`. May be broken by: nobody. A parser that consumes the end of the file would lex past it, and libcpp returns `CPP_EOF` for ever, so the failure would be a hang rather than a crash if this were not checked.

**I3.** A token's `id_kind` reflects the symbol table as it was when the token was first lexed, not as it is when the token is used.
Established by: `c_lex_one_token`. Checked by: nothing. May be broken by: any scope closing between the peek and the use, which is a real occurrence and the subject of PR67784. Repaired by: `c_parser_maybe_reclassify_token` at the five call sites in section 3.5, and nowhere else, so a construct that closes a scope and does not call it has the bug.

**I4.** At most one diagnostic is issued between an error and the next recovery point.
Established by: the latch in `c_parser_error_richloc`. Checked by: nothing. May be broken by: any code that calls `error_at` directly rather than going through the parser's reporting functions, which the semantic analysis in `c-decl.cc` and `c-typeck.cc` does constantly. The latch covers syntax errors and nothing else.

**I5.** A diagnostic that carries a fix-it hint for a missing token has its primary location at the hint and the token that was actually seen as a secondary location.
Established by: the swap in `maybe_suggest_missing_token_insertion`. Checked by: nothing in the compiler, and by `tests/test_cparse.py::test_the_swapped_diagnostic_keeps_the_place_the_caret_came_from` in this project. May be broken by: nobody. This is the observable form of I5 and section 5.2 states how to see it.

**I6.** `parser.last_token_location` is the location of the most recently consumed token, or `UNKNOWN_LOCATION` before the first.
Established by: `c_parser_consume_token`. Checked by: nothing. May be broken by: `c_parser_consume_pragma` at `gcc/c/c-parser.cc:989@releases/gcc-16.2.0`, which shuffles the window without updating it, so a fix-it hint offered immediately after a pragma is placed relative to the token before the pragma.

## 5. Observable behaviour

Everything in this section is recorded in `corpora/diag/f03.json` and read by `gxray.cparse`. Fifteen programs, twenty two diagnostics. Three of the fifteen were also compiled by an x86-64 Linux GCC of the same release through Compiler Explorer, and their diagnostics agree character for character, which is the evidence for the header line saying this component is not target dependent.

### 5.1 One mistake, thirteen possible sentences

Eight programs in the recording differ only in the token after a missing semicolon, and produce eight different messages. Corpus entries `brace`, `name`, `number`, `string`, `char`, `keyword`, `pragma`, `eof`.

| Entry | What follows | Message |
|---|---|---|
| `brace` | `}` | `expected ';' before '}' token` |
| `name` | `b;` | `expected ',' or ';' before 'b'` |
| `number` | `2;` | `expected ';' before numeric constant` |
| `string` | `"s";` | `expected ';' before string constant` |
| `char` | `'c';` | `expected ';' before 'c'` |
| `keyword` | `while` | `expected ';' before 'while'` |
| `pragma` | `#pragma` | `expected ';' before '#pragma'` |
| `eof` | end of file | `expected ';' at end of input` |

`char` and `keyword` are the same branch of section 3.8 in different disguises: a keyword is reported as `CPP_NAME`, so `'while'` comes from `%qE`. `char` and `name` are two different branches with the same printed form, which is the collision section 3.8 records, and no consumer of the text can separate them.

### 5.2 Where the caret goes

Seven of those eight put the caret at column 23, which is the position the semicolon should have occupied, and carry a fix-it hint inserting `;`. One, `name`, puts it at column 25, which is the token that upset the parser, and carries no hint. The two sets coincide exactly: hinted, moved and column 23 are the same seven entries.

A swapped diagnostic can be recognised without reading GCC's source. Its fix-it hint and its primary location are the same place, and it carries a secondary location somewhere else. `gxray.cparse.Diagnostic.moved` is that test.

### 5.3 Recovery is visible in the error count

Corpus entry `recovery` is a function body with three missing semicolons and produces two errors, of which the second is `expected declaration or statement at end of input` pointing at a closing brace that is not wrong. The first mistake is reported at line 4, the recovery in section 3.9 consumes to the end of the block, and the third mistake is never reached.

### 5.4 Matching brackets are folded into one diagnostic

Corpus entry `paren` is an unclosed `(`, and its first error carries three locations: a caret at the position the `)` should have been, a secondary under the `(` on the line above, and a secondary under the token that upset the parser on the line below. That is `add_location_if_nearby` succeeding. When it fails, because the two are too far apart to draw together, the same information arrives as a separate `to match this '('` note instead.

### 5.5 The conflict marker

Corpus entry `conflict` is a file with git conflict markers in it, and produces three errors reading `version control conflict marker in file`, each with a span seven columns wide starting at column 1. The width is the whole marker, built by `make_location` in section 3.10.

### 5.6 What a diagnostic carries beyond its text

`-fdiagnostics-format=sarif-stderr` prints the structure rather than the prose, and is how the recording was made. GCC 16 accepts `text`, `sarif-file` and `sarif-stderr`, and the JSON format that earlier releases accepted is gone. SARIF message strings use braces for placeholders, so GCC doubles any brace in a message, and `expected ';' before '}' token` arrives with `'}}'` in it. `-fdiagnostics-parseable-fixits` prints the same hints in a one line form intended for an editor.

## 6. Edge cases and error paths

**Empty translation unit.** A file with no tokens at all is a pedwarn, `ISO C forbids an empty translation unit`, at `gcc/c/c-parser.cc:2085@releases/gcc-16.2.0`, and then the parser returns. It is not an error and the compilation succeeds.

**End of input.** `CPP_EOF` is returned for ever once reached. The parser never consumes it, by I2, and never peeks past it, because `c_parser_peek_2nd_token` asserts the first token is not `CPP_EOF`. An error reported at end of input gets its caret from `input_location`, which is not updated for `CPP_EOF`, so the message points at the last real token.

**Peeking out of order.** `peek(parser, 3)` without a preceding `peek(parser, 2)` is `gcc_assert (parser->tokens_avail == n - 1)` failing, which is an internal compiler error with the usual `Please submit a full bug report` text. The assertion is not conditional on `--enable-checking`.

**A token that cannot be classified.** There is no such case. `c_lex_one_token` gives every `CPP_NAME` an `id_kind`, defaulting to `C_ID_ID`, and every other type gets `C_ID_NONE`.

**An unknown identifier where a type belongs.** Section 3.4 guesses, and then `c_parser_declaration_or_fndef` recovers by rewriting the token in place, at `gcc/c/c-parser.cc:2555@releases/gcc-16.2.0`: the token's type becomes `CPP_KEYWORD`, its keyword becomes `RID_VOID` and its value becomes `error_mark_node`. Parsing then continues as though you had written `void`, which gets the pointer types right for the rest of the declaration and produces one error instead of a cascade. Nested function definitions are refused after this recovery, on the grounds that a nested function is not what the user is likely to have meant.

**A pragma in the middle of an expression.** A `CPP_PRAGMA` token can appear anywhere libcpp put one, including places no grammar rule allows. `c_parser_error` reports it through the `%<#pragma%>` branch of section 3.8, and recovery consumes to the `CPP_PRAGMA_EOL`. `parser.in_pragma` stops the recovery routines from running past the end of the pragma into the rest of the statement.

**Conflict markers.** Recognised before the ordinary error path, in `c_parser_error_richloc`, so the message is about the marker rather than about `<<`. Recognition requires all four lookahead slots and a start column of 1, and a marker indented by one space is reported as a shift expression instead.

**A second error before recovery.** Discarded silently by the latch. This is not a rate limit and there is no counter: it is one bit, and the next syntax error after it is set produces nothing at all.

**Errors from semantic analysis.** Not latched. `'x' undeclared` comes from `c-decl.cc` and appears whether or not the parser is recovering, which is why corpus entry `scope-variable` reports an undeclared identifier on a line that the parser read without complaint.

**Allocation failure.** Not handled. The parser allocates on `parser_obstack` and through the garbage collector, and both abort the compiler rather than returning.

**Recursion depth.** Unbounded. Nested parentheses recurse in `c_parser_postfix_expression`, and a sufficiently deeply nested expression exhausts the stack. GCC installs a stack overflow handler that turns this into a diagnostic on hosts that support it, which is out of scope for this document.

## 7. Interactions

**Reads from libcpp.** Through `c_lex_with_flags` in `gcc/c/c-lex.cc`, which is the front end's wrapper over `cpp_get_token`, and which is responsible for string literal concatenation, execution character set translation and turning preprocessing numbers into constants. `BP-CPP` specifies what arrives.

**Reads and writes the symbol table.** `lookup_name` in `gcc/c/c-decl.cc` is called from the lexer, from the type name predicate and from the reclassifier, and its answer is what makes C parseable. Everything the parser builds goes back into the same file through `start_decl`, `finish_decl`, `push_scope`, `pop_scope` and their neighbours.

**Reads the keyword table.** `C_RID_CODE` over the `IDENTIFIER_NODE`, populated by `c_common_init_ts` from `gcc/c-family/c-common.cc`. The parser has no keyword list of its own.

**Calls one target hook.** `targetm.addr_space.diagnose_usage`, during token classification, for a named address space qualifier. It is the only target dependence in the file.

**Shares diagnostics with C++.** `c_parse_error` and `maybe_suggest_missing_token_insertion` are both in `gcc/c-family/c-common.cc` and both are called by the C++ parser too, so a change to either changes both languages' messages.

**Globals it touches.** `the_parser`, the one parser. `input_location`, written by `c_parser_set_source_position_from_token` and read by every diagnostic that does not carry its own location. `parser_obstack`, for scratch. `current_function_decl` and the scope stack, both owned by `c-decl.cc`. `errorcount`, incremented by the diagnostic machinery, and read by the caller of `c_parse_file` to decide whether to proceed. The pseudocode in section 3 passes `parser` explicitly and hides `input_location`; both are globals in the source.

**Ordering.** Nothing runs before it except libcpp initialisation and precompiled header loading. Everything the middle end does runs after, on the GENERIC it produced, which is `BP-GENERIC` and then `BP-GIMPLE`.

## 8. Conformance

**Invariants as assertions.** I1 and I2 are `gcc_assert` calls in the tree and need no test. I3 has no assertion and is tested behaviourally by the PR67784 cases below. I4 and I5 are tested in this project.

**DejaGnu tests.**

| Test | What it pins |
|---|---|
| `gcc/testsuite/gcc.dg/pr67784-1.c` | five ways a scope can close between the peek and the use, all reclassified correctly |
| `gcc/testsuite/gcc.dg/pr67784-2.c` | the same five with the typedef and the variable swapped, all producing `undeclared` |
| `gcc/testsuite/gcc.dg/pr67784-3.c` | the same, with the declaration in an `if` rather than a `for` |
| `gcc/testsuite/gcc.dg/pr67784-4.c` | the same, in a `switch` |
| `gcc/testsuite/gcc.dg/pr67784-5.c` | the same, in a `while` |
| `gcc/testsuite/c-c++-common/conflict-markers-1.c` | all three marker kinds recognised, and the lines between them skipped |
| `gcc/testsuite/c-c++-common/conflict-markers-2.c` through `-11.c` | markers in ten more positions, including ones that must not be recognised |
| `gcc/testsuite/gcc.dg/semicolon-fixits.c` | the fix-it hints for extra and missing semicolons, with their multiline caret output |
| `gcc/testsuite/gcc.dg/parse-error-1.c` through `-3.c` | recovery does not cascade |
| `gcc/testsuite/gcc.dg/parse-decl-after-if.c` | a declaration where the reclassifier has to have run |
| `gcc/testsuite/gcc.dg/parse-decl-after-label.c` | the label case of section 3.4 |
| `gcc/testsuite/gcc.dg/parser-pr28152.c` | keywords reported through the identifier branch of section 3.8 |
| `gcc/testsuite/gcc.dg/fixits.c` | parseable fix-it output |

The conflict marker tests are in `c-c++-common` rather than in `gcc.dg`, which is the testsuite's way of recording that `c_parser_peek_conflict_marker` has a C++ twin with the same behaviour.

**Golden corpus entries.** `corpora/diag/f03.json`, all fifteen. The recorder asserts thirty conditions about them before writing the file, and `tests/test_cparse.py` asserts fifty six about the file afterwards, of which four compare the tables in section 3.7 and section 3.8 with the pinned tree in both directions.

**Registered in Tier 0** as `f03-cparse`, kind `offline`. Offline because the comparators count basic blocks and phi nodes in a tree dump, and none of these programs reaches a tree dump. The online half is the three programs compiled on a second target, cached under `tools/cecache/store`.

## 9. Port notes

**Recursive descent is not forced.** C is not LL(k) for any k, and the four slot buffer is not what makes GCC's parser work; the symbol table lookup during lexing is. Any parsing technique that can consult a symbol table mid parse will do, and several C compilers use generated LALR parsers with the same hack bolted on. What is forced is that something must decide whether an identifier names a type before the construct containing it can be parsed, because `A * b;` and `A (b);` and `(A) * b` are each two different parses and the token stream does not distinguish them.

**Four slots is arbitrary.** Three would parse C. The fourth exists for `c_parser_peek_conflict_marker` and nothing else, and a reimplementation that did not want to recognise merge conflicts would need three. A reimplementation that lexed the whole file up front, which is what GCC's own C++ front end does and what the comment at `gcc/c/c-parser.h:33@releases/gcc-16.2.0` wishes the C front end did, would need none.

**Classifying at lex time is a choice with a cost.** Writing the symbol table's answer into the token means the answer can go stale, which is I3, and GCC pays for that with `c_parser_maybe_reclassify_token` and five call sites that have to be kept in step with the language. Classifying at use time instead costs a symbol table walk per use rather than per token, and removes the bug class. GCC's choice is historical.

**The error latch is a choice.** One bit means the second syntax error in a statement is never seen. Reporting every error and letting the user filter is also defensible and is what some compilers do. What is not defensible is reporting some of them, which is what happens if the flag is cleared in the wrong place, and the eighteen clear sites in `c-parser.cc` are the surface where that can go wrong.

**Caret placement is a choice, and the swap is the interesting half.** Pointing at the token that upset the parser is the obvious behaviour and is what GCC does when it has no repair to suggest. Pointing at where the repair would go is better and is what GCC does when it has one, and the cost is that the two cases look inconsistent to anybody who has not read section 3.7. A reimplementation could do either uniformly. Doing the swap requires keeping the location of the previously consumed token, which is I6 and is one field.

**The unknown type name guess is a choice.** Treating an undeclared identifier followed by another identifier as a misspelled type is a heuristic with no basis in the standard, and it exists so that `foo bar;` gets a useful message. It can be wrong. A reimplementation that omitted it would produce a syntax error instead, which is correct and less helpful.

**Nothing here is target dependent** except `C_ID_ADDRSPACE` and the one hook in section 7. Two targets compiling the same wrong program produce the same diagnostics, which section 5 records as an observation rather than an assertion.
