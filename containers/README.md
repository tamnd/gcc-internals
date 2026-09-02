# The build matrix

Six ways to build GCC 16.2.0, on two architectures, published to a registry and pulled by digest.

The rule that shapes all of this: **no job in this project compiles GCC except the matrix job.** Building GCC takes between twenty five minutes and five hours depending on the configuration, and a course whose test suite rebuilds a compiler is a course nobody can contribute to. Everything else names an image by its digest in `images.lock.json`, so a green run cannot quietly have been testing a compiler nobody published, and a pull request that wants a different compiler has to say so in a file a reviewer can see.

<!-- matrix table start -->

| Config | What it is | Build | Size | Arches | Built |
|---|---|---|---|---|---|
| `rel` | The fast development loop. Optimized, no bootstrap, and the one most jobs want. | 25 min | 1.2 GB | amd64, arm64 | weekly and on a patch change |
| `chk` | Every internal consistency check GCC has, turned on. | 45 min | 4 GB | amd64, arm64 | weekly and on a patch change |
| `dbg` | Unoptimized with full debug info, for the lessons that step through GCC in gdb. | 50 min | 6 GB | amd64, arm64 | weekly and on a patch change |
| `boot` | The full three stage bootstrap, with the stage two against stage three comparison. | 240 min | 8 GB | amd64, arm64 | weekly |
| `cross` | A riscv64-elf cross compiler with newlib, for the back end lessons. | 35 min | 1.5 GB | amd64, arm64 | weekly and on a patch change |
| `plug` | A stock distribution GCC with gxplug built against it, and nothing compiled from source. | 5 min | 1.7 GB | amd64, arm64 | weekly and on a patch change |

6 configurations, `rel`, `chk`, `dbg`, `boot`, `cross`, `plug`, on 2 architectures. One full weekly run is about 13.3 machine hours.

<!-- matrix table end -->

## Where the configurations live

In `matrix.toml`, and nowhere else. The workflow asks `tools.matrix` which jobs to run, the Dockerfile is handed its configure flags as build arguments, and the table above is generated. Configure flags in a Dockerfile plus a job list in a workflow plus times and sizes in a README is three copies of one fact, and the second copy goes stale in the first week.

Adding a configuration is adding a table to `matrix.toml` and running `just matrix-table`. If you edited something else instead, CI says so.

To see what a build is actually handed:

```console
$ python -m tools.matrix show chk
chk, Every internal consistency check GCC has, turned on.
...
```

## Two Dockerfiles, not six

`Dockerfile` builds GCC from source and covers five of the six. What makes `rel` different from `chk` is a configure flag and a `CFLAGS`, so five files would be five copies of the same forty lines with four characters different, and four of them would fall behind.

`Dockerfile.plug` is the exception, and it is the row that matters most to a reader. It installs a distribution's own GCC 16 and builds the plugin against it. If the plugin loads only into a compiler we built ourselves then the plugin does not work, and the way to keep that honest is to have one image that never builds one.

It is Debian unstable, because as of September 2026 that is where a packaged GCC 16 actually is, at exactly the 16.2.0 this project is pinned to. Ubuntu 24.04 has GCC 13, and 26.04 has not caught up. A reader on an LTS either uses this image or builds from source, which is the honest answer to open question 4 rather than a wish.

## Building one yourself

You do not need to. The images are published and everything pulls them. But the whole point of B01 is that a reader can, so it has to work:

```console
$ python -m tools.matrix show rel
$ docker build -f containers/Dockerfile \
    --build-arg CONFIGURE_FLAGS="$(python -m tools.matrix show rel | sed -n '/^configure/,$p' | tail -n +2 | xargs)" \
    --build-arg CFLAGS_FOR_GCC="-O2" \
    --build-arg MAKE_TARGET=all \
    --build-arg INSTALL_TARGET=install-strip \
    --build-arg CONFIG_ID=rel \
    --build-arg SMOKE="gcc -O2 /tmp/t.c -o /tmp/t && /tmp/t" \
    -t gcc-internals/rel .
```

That is a mouthful on purpose. The workflow reads the same values out of `matrix.toml` and does not type any of them, and so should you, once B01 ships `just image rel`.

## Patches

Anything in `patches/` is applied to the source tree inside the image and nowhere else, so a patched compiler and a stock one differ in exactly one place a reviewer can look at. The directory is usually empty and the loop that applies them is a no-op then. A change under `patches/` triggers a rebuild of every configuration marked as building on a push, which is every configuration except `boot`.

## What the images cost

Twenty two gigabytes per architecture if you kept all six, which is why the retention policy is the last four weekly builds plus every image a released version of the site refers to. `dbg` is six gigabytes on its own, because it keeps the GCC source tree in the image: a debugger needs the sources its debug info points at, and B03 is unteachable without them.

## The lockfile

`images.lock.json` maps every image the matrix builds to the digest of the last successful build of it. The matrix workflow writes it, and `python -m tools.matrix digests --check` fails when it and `matrix.toml` disagree.

The dangerous direction is an entry for an image the matrix no longer builds. A digest in a registry outlives the workflow that pushed it, so that entry keeps resolving and a job goes on pulling a compiler that nothing rebuilds, forever, silently.

Right now the file is empty, because the matrix has not published a full run yet. `digests --check` therefore reports all twelve images as missing, which is true, and it runs inside the matrix workflow rather than in the ordinary CI for exactly that reason. It moves into CI as a blocking check the day the first full run finishes, and that is issue #61.
