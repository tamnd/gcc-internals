/* hello — the smallest plugin that is still a plugin.

   Forty lines, three of which are the whole of the plugin contract: a symbol that says the
   licence is compatible, an entry point called plugin_init, and a version check that GCC
   does not perform for you.

   Everything else here is one callback. PLUGIN_PRE_GENERICIZE fires once per function
   definition, just after the front end has finished with it and before it is handed to the
   middle end, so counting them counts the functions in the translation unit. PLUGIN_FINISH
   fires once, at the very end, which is where the total gets printed.

     gcc-16 -O2 -S -fplugin=./examples/hello.so t.c -o t.s
     gcc-16 -O2 -S -fplugin=./examples/hello.so -fplugin-arg-hello-who=reader t.c -o t.s

   Copyright the gcc-internals authors.
   SPDX-License-Identifier: GPL-3.0-or-later  */

#include "gcc-plugin.h"
#include "config.h"
#include "system.h"
#include "coretypes.h"
#include "tree.h"
#include "plugin-version.h"

/* GCC checks for this symbol by name before it calls anything, and a plugin without it is
   refused with a diagnostic about the licence. It is never read, only found.  */
int plugin_is_GPL_compatible;

static int functions = 0;
static const char *who = "world";

static void
on_function (void *gcc_data, void * /*user_data*/)
{
  tree fndecl = (tree) gcc_data;
  functions++;
  fprintf (stderr, "hello: %s\n", IDENTIFIER_POINTER (DECL_NAME (fndecl)));
}

static void
on_finish (void * /*gcc_data*/, void * /*user_data*/)
{
  fprintf (stderr, "hello, %s: %d function(s) in this unit\n", who, functions);
}

int
plugin_init (plugin_name_args *info, plugin_gcc_version *version)
{
  /* Not a formality. The plugin is compiled against GCC's private headers, so a plugin
     built for one compiler and loaded into another is undefined behaviour. Returning
     non-zero here stops the compilation with a diagnostic instead.  */
  if (!plugin_default_version_check (version, &gcc_version))
    return 1;

  for (int i = 0; i < info->argc; i++)
    if (strcmp (info->argv[i].key, "who") == 0)
      who = info->argv[i].value;

  register_callback (info->base_name, PLUGIN_PRE_GENERICIZE, on_function, nullptr);
  register_callback (info->base_name, PLUGIN_FINISH, on_finish, nullptr);
  return 0;
}
