# gxplug

A GCC plugin that watches the pass manager and writes down what it saw.

The text dumps tell you what the IR looked like at a few chosen points. They do not tell you which passes actually ran, in what order, on which function, how long each took, or what the compiler believed about the IR at that moment. `gxplug` emits that as one JSON object per line and changes nothing else.

## The one rule

**`gxplug` never changes what GCC compiles.**

A reader has to be able to add `-fplugin=gxplug.so` to any command in this book and get byte identical code out, plus a stream of events. Nothing here registers a pass, overrides a gate, or modifies a tree. Everything it touches is read only.

That is a promise a document cannot keep, so it is checked instead. `make check` compiles the same program twice, once with the plugin and once without, and compares the assembly byte for byte. The `plugin` workflow runs the same check against four different compilers on every push that touches this directory. If it ever fails then no lesson built on the plugin is trustworthy, and the failure is the most important thing in the repository that day.

## Building it

```sh
make                    # against whatever `gcc` means here
make GCC=gcc-16         # against a specific compiler
make probe              # what the build decided, and where it looked
make check              # build it, then prove it changes no generated code
```

The plugin has to be built by the same GCC that will load it. The plugin ABI depends on the version and on the configure options, and `plugin_init` refuses a mismatch rather than crashing somewhere later, so pointing `GCC` at the wrong compiler gives a clear error instead of a mystery.

The one prerequisite is the plugin headers, which most distributions ship separately from the compiler:

| Channel | What to install |
|---|---|
| Debian | `gcc-16` and `gcc-16-plugin-dev` |
| Fedora | `gcc` and `gcc-plugin-devel` |
| Homebrew | `gcc`, which already includes them |
| source | nothing, `make install` puts them under the prefix |

If `make` cannot find `gcc-plugin.h` it says so and prints that table, because a missing plugin development package is what goes wrong on almost every first attempt.

Two other things differ between those four channels, and both are probed for rather than assumed. On macOS a shared object has to be linked with `-undefined dynamic_lookup`, because its undefined symbols are resolved out of `cc1` at `dlopen` time, and passing that flag on an ELF platform is an error, so it is conditional on `uname`. Also on macOS, `gmp.h` comes from Homebrew and is not on the default include path, so the build compiles `probe/gmp.c` first and adds `$(brew --prefix)/include` only when that fails.

## Running it

```sh
gcc-16 -O2 -S -fplugin=./gxplug.so l1.c -o l1.s
```

With no arguments the stream goes to stderr, so that adding the flag and nothing else shows you something. Standard output is deliberately left alone, because `-S` writes assembly there and the whole point is that it comes out unchanged.

| Argument | What it does |
|---|---|
| `-fplugin-arg-gxplug-out=PATH` | write the stream to a file |
| `-fplugin-arg-gxplug-fd=N` | write it to an already open descriptor |

The second is how a notebook reads the stream without a temporary file. Giving both, or giving an argument that is not one of these, is an error and stops the compilation. A typo in a `-fplugin-arg-` name is otherwise the sort of thing that quietly does nothing for an hour.

## What a record looks like

Two records per pass. A `pass-start` when the pass manager is about to run it, and a `pass-end` carrying the duration and the state the pass left behind.

```json
{"seq":41,"event":"pass-end","pass":"cfg","pass_number":20,"function":"f",
 "properties":84239,"statements":8,"insns":null,"blocks":6,"seconds":0.000065}
```

| Field | Meaning |
|---|---|
| `seq` | position in the stream, so ordering does not depend on timestamps |
| `event` | `pass-start` or `pass-end` |
| `pass` | the pass name, the same one `-fdump-passes` prints |
| `pass_number` | GCC's static pass number, `-1` for a pass that has none |
| `function` | the function being compiled, `null` during an IPA pass |
| `properties` | `cfun->curr_properties`, the IR property bits, as an integer |
| `statements` | GIMPLE statements, or `null` once the function is RTL |
| `insns` | RTL insns, or `null` before `expand` |
| `blocks` | basic blocks, `null` once the CFG has been freed |
| `seconds` | how long the pass took, on `pass-end` only |

A count that does not apply is `null` and not `0`, so a reader can tell "there was nothing to count here" from "counted, and the answer was zero".

`statements` and `insns` are never both set. A basic block holds either a GIMPLE sequence or an RTL insn chain, in a union, and walking it as the wrong one does not fail a check. It reads whichever pointer happens to be there and segfaults, which is what the first version of this plugin did.

## Reading the stream

`gxray.plug` turns a stream into something a widget can hold.

```python
from gxray import plug

stream = plug.load("events.ndjson")
runs = stream.runs
changed = [r for r in runs if r.changed]
print(len(runs), "passes ran,", len(changed), "left a mark")
```

`changed` is deliberately narrow. It means the statement count, the insn count, the block count, or the property bits moved. A pass that rewrote an expression without changing any of those reports `False`, so the prose has to say what the number means rather than let a reader conclude that most passes do nothing. What it is good for is the honest ratio in T04: how many passes ran, and how many left a mark you can see from outside.

A `pass-start` with no matching `pass-end` becomes a run whose `end` is `None`, rather than being dropped. It means the compilation died inside that pass, which is the single most useful thing the stream can tell you.

## Why not read the dumps

`gxray.passes` already parses `-fdump-passes`, and that answers a different question: which passes this compiler knows about, and whether they are switched on. It is a static list. It does not know that `ccp` ran three times, that two of those changed nothing, or that the one expensive pass in the run was somewhere you were not looking.

Nothing in `gxray.plug` parses text, which is the point. The plugin emits JSON precisely so that the reading side does not have to be a parser.
