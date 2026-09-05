/* Does this compiler find gmp.h without help?

   GCC's own headers include it, so a plugin cannot build without it. On macOS it comes
   from Homebrew and is not on the default include path, and on Linux it is. This file
   exists as a file rather than as a printf inside the Makefile because make treats a
   `#` as the start of a comment even in the middle of a $(shell ...) call, which eats
   the rest of the line and produces an error about an unterminated call. */
#include <gmp.h>

int
main (void)
{
  return 0;
}
