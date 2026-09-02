# One Dockerfile for every configuration that builds GCC from source.
#
# What makes rel different from chk is a configure flag and a CFLAGS, so five Dockerfiles
# would be five copies of the same forty lines with four characters different, and four of
# them would fall behind. The flags come in as build arguments and `tools.matrix` is what
# knows their values. Run `python -m tools.matrix show chk` to see what a build is handed.
#
# Built natively on both architectures. A cross build under qemu is somewhere between five
# and twenty times slower and boot is already four hours.

FROM ubuntu:24.04 AS base

# Everything GCC's own configure asks for, plus git for the checkout and ccache because a
# no change rebuild should be minutes rather than an hour. DEBIAN_FRONTEND because the
# tzdata postinst otherwise sits waiting for a timezone nobody is there to type.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --no-install-recommends -y \
      build-essential \
      ca-certificates \
      ccache \
      flex \
      bison \
      git \
      libgmp-dev \
      libmpfr-dev \
      libmpc-dev \
      libisl-dev \
      libzstd-dev \
      zlib1g-dev \
      texinfo \
      wget \
      xz-utils \
 && rm -rf /var/lib/apt/lists/*

FROM base AS source

ARG GCC_TAG=releases/gcc-16.2.0
# Shallow, because the matrix wants one tag and the full history is about three gigabytes
# of things no build reads.
RUN git clone --depth 1 --branch "${GCC_TAG}" \
      https://github.com/gcc-mirror/gcc.git /usr/src/gcc

# Anything in patches/ is applied here and nowhere else, so a patched compiler and a stock
# one differ in exactly one place a reviewer can look at. The directory is usually empty
# and the loop is a no-op then, which is the normal case and not a special one.
COPY patches/ /usr/src/patches/
RUN set -eux; \
    for p in /usr/src/patches/*.patch; do \
      [ -e "$p" ] || continue; \
      echo "applying $(basename "$p")"; \
      git -C /usr/src/gcc apply --verbose "$p"; \
    done

FROM source AS build

ARG CONFIGURE_FLAGS
ARG CFLAGS_FOR_GCC="-O2"
ARG MAKE_TARGET="all"
ARG INSTALL_TARGET="install-strip"
ARG CONFIG_ID="rel"

# GCC will not configure in its own source directory and says so, which is the one thing
# every first time builder gets wrong.
WORKDIR /usr/src/build
RUN set -eux; \
    /usr/src/gcc/configure ${CONFIGURE_FLAGS} \
      CFLAGS="${CFLAGS_FOR_GCC}" \
      CXXFLAGS="${CFLAGS_FOR_GCC}" \
      CC="ccache gcc" \
      CXX="ccache g++"; \
    make "${MAKE_TARGET}" -j"$(nproc)"; \
    make "${INSTALL_TARGET}"

FROM base AS final

ARG CONFIG_ID="rel"
ARG GCC_TAG=releases/gcc-16.2.0

COPY --from=build /opt/gcc /opt/gcc
ENV PATH="/opt/gcc/bin:${PATH}"
ENV LD_LIBRARY_PATH="/opt/gcc/lib64:/opt/gcc/lib"

# The build tree is kept for dbg and thrown away for everything else. A debugger needs the
# sources the debug info points at, and dbg is six gigabytes because of exactly this.
COPY --from=build /usr/src/gcc /usr/src/gcc-full
RUN set -eux; \
    if [ "${CONFIG_ID}" = "dbg" ]; then \
      mv /usr/src/gcc-full /usr/src/gcc; \
    else \
      rm -rf /usr/src/gcc-full; \
    fi

# Which compiler this is, readable without running anything. A dump in the corpus says
# which image produced it and this is the other half of that.
LABEL org.opencontainers.image.source="https://github.com/tamnd/gcc-internals"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"
LABEL dev.gcc-internals.config="${CONFIG_ID}"
LABEL dev.gcc-internals.gcc-tag="${GCC_TAG}"

# A build that produced a compiler which cannot compile hello world has failed, and it is
# better to find that out here than in the job that pulled the image. The command comes
# from matrix.toml because a cross compiler has no libc and cannot link.
ARG SMOKE
RUN set -eux; \
    printf 'int main(void){return 0;}\n' > /tmp/t.c; \
    sh -c "${SMOKE}"; \
    rm -f /tmp/t.c /tmp/t /tmp/t.o

CMD ["/bin/sh", "-c", "ls /opt/gcc/bin"]
