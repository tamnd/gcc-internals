# Build gxplug against whichever GCC you point it at.
#
# The reader should never have to know about -Wl,-undefined,dynamic_lookup or about where
# Homebrew keeps gmp.h. Both are probed for here. Set GCC to pick a compiler:
#
#     make                    # uses gcc
#     make GCC=gcc-16         # Homebrew, Debian, anything with a -N suffix
#     make check              # builds it, then proves it changes no generated code
#
# The plugin has to be built by the same GCC it will be loaded into. The ABI is sensitive
# to version and to configure options, and plugin_init refuses a mismatch rather than
# crashing later, so a wrong GCC here is a clear error and not a mystery.

GCC ?= gcc
CXX_FOR_PLUGIN ?= $(GCC)

# Where this GCC keeps its plugin headers. Empty means the plugin development package is
# not installed, which is the single most common reason a first attempt fails.
PLUGIN_DIR := $(shell $(GCC) -print-file-name=plugin 2>/dev/null)
PLUGIN_INCLUDE := $(PLUGIN_DIR)/include

UNAME_S := $(shell uname -s)

# GCC itself is built without RTTI, and a plugin that disagrees gets link errors about
# typeinfo that say nothing useful about the cause.
CXXFLAGS ?= -O2 -std=c++17 -fno-rtti -fPIC -Wall -Wextra -Wno-unused-parameter

# Ours, kept separate from CPPFLAGS and placed ahead of it. A developer machine often has
# a CPPFLAGS in the environment pointing at Homebrew LLVM, and an LLVM header found before
# GCC's own is a failure that reads like a compiler bug. Appending to CPPFLAGS would put
# that first; this puts it second and still lets someone add to it deliberately.
GXPLUG_CPPFLAGS := -I$(PLUGIN_INCLUDE)

# gmp.h is included by GCC's own headers and on macOS it lives under the Homebrew prefix,
# which is not on the default include path. Probe rather than hardcode, because the prefix
# differs between Apple silicon and Intel and because Linux does not need this at all.
GMP_PROBE := $(shell $(GCC) $(GXPLUG_CPPFLAGS) -fsyntax-only probe/gmp.c >/dev/null 2>&1 && echo yes || echo no)
ifeq ($(GMP_PROBE),no)
  BREW_PREFIX := $(shell brew --prefix 2>/dev/null)
  ifneq ($(BREW_PREFIX),)
    GXPLUG_CPPFLAGS += -I$(BREW_PREFIX)/include
  endif
endif

# A plugin is C++, and the `gcc` driver knows what to do with a .cc file, so this looks
# like it works right up to the point where it tries to exec a cc1plus that only the g++
# package ships. Asking here turns "No such file or directory" into a sentence that names
# the package.
CXX_PROBE := $(shell echo 'int main(){}' | $(CXX_FOR_PLUGIN) -x c++ -fsyntax-only - >/dev/null 2>&1 && echo yes || echo no)

# Darwin resolves a plugin's undefined symbols out of cc1 at dlopen time, and the linker
# has to be told that is acceptable. ELF platforms do this by default and passing the flag
# there is an error, so it is conditional.
LDFLAGS_PLUGIN :=
ifeq ($(UNAME_S),Darwin)
  LDFLAGS_PLUGIN += -Wl,-undefined,dynamic_lookup
endif

# .so on both platforms, not .dylib. GCC's -fplugin= wants a shared object and Darwin is
# happy to produce one under that name.
PLUGIN := gxplug.so
SRC := src/gxplug.cc

# The five plugins B05 is built on. Two work, one changes the generated code on purpose,
# and two are refused at load time on purpose. They are built with exactly the flags above,
# because a reader's own plugin will be too.
EXAMPLE_SRC := $(wildcard examples/*.cc)
EXAMPLES := $(EXAMPLE_SRC:.cc=.so)

.PHONY: all check probe clean examples examples-check

all: $(PLUGIN)

$(PLUGIN): $(SRC)
	@test -f "$(PLUGIN_INCLUDE)/gcc-plugin.h" || { \
	  echo "gxplug: no plugin headers under $(PLUGIN_INCLUDE)"; \
	  echo "gxplug: install the plugin development package for this compiler"; \
	  echo "gxplug:   Debian/Ubuntu   apt install gcc-16-plugin-dev"; \
	  echo "gxplug:   Fedora          dnf install gcc-plugin-devel"; \
	  echo "gxplug:   Homebrew        already included with the gcc formula"; \
	  exit 1; \
	}
	@test "$(CXX_PROBE)" = yes || { \
	  echo "gxplug: $(CXX_FOR_PLUGIN) cannot compile C++, and a plugin is C++"; \
	  echo "gxplug: install the matching C++ compiler, not another C one"; \
	  echo "gxplug:   Debian/Ubuntu   apt install g++-16"; \
	  echo "gxplug:   Fedora          dnf install gcc-c++"; \
	  exit 1; \
	}
	$(CXX_FOR_PLUGIN) $(GXPLUG_CPPFLAGS) $(CPPFLAGS) $(CXXFLAGS) -shared $(LDFLAGS_PLUGIN) -o $@ $(SRC)

# What the probes decided, for when a build fails somewhere unfamiliar and the first
# question is which compiler and which headers it actually found.
probe:
	@echo "GCC             $(GCC)"
	@echo "version         $$($(GCC) -dumpfullversion 2>/dev/null)"
	@echo "plugin headers  $(PLUGIN_INCLUDE)"
	@echo "gcc-plugin.h    $$(test -f '$(PLUGIN_INCLUDE)/gcc-plugin.h' && echo present || echo MISSING)"
	@echo "uname           $(UNAME_S)"
	@echo "compiles c++    $(CXX_PROBE)"
	@echo "gmp.h on path   $(GMP_PROBE)"
	@echo "CPPFLAGS        $(GXPLUG_CPPFLAGS) $(CPPFLAGS)"
	@echo "link flags      $(LDFLAGS_PLUGIN)"

# The guarantee, checked rather than asserted. Compile something twice, once with the
# plugin and once without, and require the assembly to be identical byte for byte. If this
# ever fails then the plugin is not a passive observer any more and no lesson built on it
# can be trusted.
check: $(PLUGIN)
	@set -e; \
	tmp=$$(mktemp -d); \
	trap 'rm -rf "$$tmp"' EXIT; \
	printf 'int f(int n){int s=0;for(int i=0;i<n;i++)s+=i*i;return s;}\n' > "$$tmp/t.c"; \
	$(GCC) -O2 -S "$$tmp/t.c" -o "$$tmp/without.s"; \
	$(GCC) -O2 -S -fplugin=./$(PLUGIN) -fplugin-arg-gxplug-out="$$tmp/events.ndjson" \
	  "$$tmp/t.c" -o "$$tmp/with.s"; \
	if ! cmp -s "$$tmp/without.s" "$$tmp/with.s"; then \
	  echo "gxplug: FAIL, the plugin changed the generated code"; \
	  diff -u "$$tmp/without.s" "$$tmp/with.s" || true; \
	  exit 1; \
	fi; \
	events=$$(wc -l < "$$tmp/events.ndjson" | tr -d ' '); \
	test "$$events" -gt 0 || { echo "gxplug: FAIL, no events emitted"; exit 1; }; \
	echo "gxplug: assembly identical with and without the plugin, $$events events"

# The examples, built the same way. No header probe here: if the main plugin built, these
# will, and if it did not the reader has already been told which package to install.
examples: $(EXAMPLES)

examples/%.so: examples/%.cc $(PLUGIN)
	$(CXX_FOR_PLUGIN) $(GXPLUG_CPPFLAGS) $(CPPFLAGS) $(CXXFLAGS) -shared $(LDFLAGS_PLUGIN) -o $@ $<

# Each example does what B05 says it does. hello and countpass leave the assembly alone,
# gate changes it, and the two broken ones are refused before they run a line.
#
# The program is an array traversal rather than the accumulator `check` uses, because the
# pass being switched off is ivopts and a loop with no memory reference in it gives ivopts
# nothing to rewrite. The two halves of the gate result are checked separately: how many
# times the pass was refused, which catches a pass name that matched nothing, and whether
# the assembly moved, which catches a pass whose absence makes no difference. They fail for
# different reasons and the messages have to say which.
examples-check: examples
	@set -e; \
	tmp=$$(mktemp -d); \
	trap 'rm -rf "$$tmp"' EXIT; \
	printf 'int f (int *a, int n) { int s = 0; for (int i = 0; i < n; i++) s += a[i]; return s; }\n' > "$$tmp/t.c"; \
	$(GCC) -O2 -S "$$tmp/t.c" -o "$$tmp/plain.s"; \
	for one in hello countpass; do \
	  $(GCC) -O2 -S -fplugin=./examples/$$one.so "$$tmp/t.c" -o "$$tmp/$$one.s" 2>/dev/null; \
	  cmp -s "$$tmp/plain.s" "$$tmp/$$one.s" \
	    || { echo "examples: FAIL, $$one changed the generated code"; exit 1; }; \
	  echo "examples: $$one loaded and changed nothing"; \
	done; \
	$(GCC) -O2 -S -fplugin=./examples/gate.so -fplugin-arg-gate-off=ivopts \
	  "$$tmp/t.c" -o "$$tmp/gate.s" 2>"$$tmp/gate.err"; \
	grep -q 'refused ivopts 0 time' "$$tmp/gate.err" \
	  && { echo "examples: FAIL, no pass called ivopts was ever asked, so nothing was tested"; \
	       cat "$$tmp/gate.err"; exit 1; }; \
	cmp -s "$$tmp/plain.s" "$$tmp/gate.s" \
	  && { echo "examples: FAIL, ivopts was switched off and the assembly did not move"; exit 1; }; \
	echo "examples: gate switched a pass off and the assembly moved"; \
	for one in nolicence wrongver; do \
	  ! $(GCC) -O2 -S -fplugin=./examples/$$one.so "$$tmp/t.c" -o "$$tmp/$$one.s" 2>/dev/null \
	    || { echo "examples: FAIL, $$one was supposed to be refused"; exit 1; }; \
	  echo "examples: $$one was refused, as it should be"; \
	done

clean:
	rm -f $(PLUGIN) $(EXAMPLES)
