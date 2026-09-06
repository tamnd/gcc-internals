/* wrongver — what a version mismatch looks like, without needing two compilers.

   plugin_default_version_check compares the plugin_gcc_version GCC passes in against the
   one baked into the plugin from plugin-version.h at build time. Normally the second one
   is &gcc_version and the check passes because the plugin was built ten seconds ago by the
   compiler now loading it.

   Here the second one is a fabricated struct, so the check fails the way it would fail if
   this plugin had been built by GCC 15 and dropped into GCC 16. The diagnostic and the exit
   are real; only the mismatch is staged.

   Copyright the gcc-internals authors.
   SPDX-License-Identifier: GPL-3.0-or-later  */

#include "gcc-plugin.h"
#include "config.h"
#include "system.h"
#include "coretypes.h"
#include "diagnostic-core.h"
#include "tree.h"
#include "plugin-version.h"

int plugin_is_GPL_compatible;

/* What the plugin claims it was built by. Every field of this is compared, not only the
   version: two compilers of the same version configured differently have incompatible
   plugin ABIs, which is why configuration_arguments is in the struct at all.  */
static struct plugin_gcc_version built_by
  = { "15.1.0", "20250501", "release", "", "--enable-languages=c,c++" };

int
plugin_init (plugin_name_args * /*info*/, plugin_gcc_version *version)
{
  if (!plugin_default_version_check (version, &built_by))
    {
      error ("wrongver: built against GCC %s, loaded into GCC %s", built_by.basever,
	     version->basever);
      /* Which is a lie, and here is the truth, so that nobody reading this output in a
	 lesson concludes their compiler is broken.  */
      inform (UNKNOWN_LOCATION, "wrongver: really built by GCC %s, the mismatch is staged",
	      gcc_version.basever);
      return 1;
    }
  fprintf (stderr, "wrongver: this line never prints\n");
  return 0;
}
