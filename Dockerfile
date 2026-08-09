# syntax=docker/dockerfile:1
#
# CSCI-350 Programming Languages — course toolchain image.
#
# One image, every language the course touches, so students never install
# anything and CI runs in a byte-identical environment.
#
#   Java 21 + JUnit .... Wks 1-2 warmup; tokenizer / parser / interpreter projects
#   Racket ............. Wks 8-11  (Scheme path)
#   SBCL ............... Wks 8-11  (Common Lisp path — Paul's inherited HW 02)
#   GHC + HLS .......... Wk 10     (Haskell)
#   SWI-Prolog ......... Wks 12-13 (Prolog)
#   Python 3 ........... general tooling / alternate parser implementation
#
# Both Lisp dialects are installed deliberately: the Scheme-vs-Common-Lisp
# decision is still open, and neither is big enough to be worth blocking on.
# See the vault note CSCI-350-Fall-2026-Plan §4b(e).
#
# Build:  docker buildx build --platform linux/amd64,linux/arm64 -t csci350 .
# Verify: ./smoke-test.sh

ARG BASE=mcr.microsoft.com/devcontainers/base:ubuntu-24.04
FROM ${BASE}

# Set by buildx: "amd64" or "arm64"
ARG TARGETARCH

ARG RACKET_VERSION=9.2
ARG GHC_VERSION=9.6.6
ARG CABAL_VERSION=3.10.3.0
# Last stable on the 1.x line — the line Paul's Jupiter tests target.
# Deliberately NOT 6.x (major renumber, breaking changes) and not Paul's
# own 1.13.0-M3 (a milestone build; no milestones in a course image).
ARG JUNIT_VERSION=1.14.4

ENV DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# 1. System packages
#    Includes GHC's build prerequisites (libgmp, ncurses, numa, zlib) so the
#    ghcup step below doesn't have to discover them the hard way.
#
#    swi-prolog-nox, not swi-prolog: the full metapackage pulls the xpce GUI
#    and with it mesa + a pile of X libraries, all dead weight in a headless
#    container. plunit and the REPL are unaffected.
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        wget \
        unzip \
        zip \
        pkg-config \
        libgmp-dev \
        libncurses-dev \
        libnuma-dev \
        zlib1g-dev \
        openjdk-21-jdk \
        swi-prolog-nox \
        sbcl \
        rlwrap \
        python3 \
        python3-pip \
        python3-venv \
        jq \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-${TARGETARCH}

# Ubuntu 24.04 marks the system Python externally-managed (PEP 668).
# These are course tools, not system libs, so overriding is the pragmatic call.
RUN pip3 install --no-cache-dir --break-system-packages pytest

# ---------------------------------------------------------------------------
# 2. JUnit console standalone
#    Paul's inherited material invokes the standalone jar directly rather than
#    going through Maven/Gradle. Baking it in keeps that workflow and means
#    tests need no network at run time.
# ---------------------------------------------------------------------------
ENV JUNIT_JAR=/opt/junit/junit-platform-console-standalone.jar
RUN mkdir -p /opt/junit && \
    curl -fsSL -o ${JUNIT_JAR} \
      "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/${JUNIT_VERSION}/junit-platform-console-standalone-${JUNIT_VERSION}.jar"

# ---------------------------------------------------------------------------
# 3. Racket  (Scheme path)
#    Official installer. Racket names arches x86_64 / aarch64, buildx says
#    amd64 / arm64 — hence the mapping.
# ---------------------------------------------------------------------------
ENV PATH=/opt/racket/bin:${PATH}
RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) RARCH=x86_64 ;; \
      arm64) RARCH=aarch64 ;; \
      *) echo "unsupported arch: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/racket.sh \
      "https://mirror.racket-lang.org/installers/${RACKET_VERSION}/racket-${RACKET_VERSION}-${RARCH}-linux-buster-cs.sh"; \
    sh /tmp/racket.sh --in-place --dest /opt/racket; \
    rm -f /tmp/racket.sh

# LSP for the Magic Racket VS Code extension.
# Installation scope so every user in the container gets it, not just root.
RUN raco pkg install --auto --scope installation racket-langserver

# ---------------------------------------------------------------------------
# 4. Haskell — GHC, cabal, HLS via ghcup
#    Installed as the non-root `vscode` user because ghcup lives in $HOME.
#    This is by far the largest layer (~2 GB); it is last so edits above it
#    don't force a rebuild.
# ---------------------------------------------------------------------------
USER vscode
ENV BOOTSTRAP_HASKELL_NONINTERACTIVE=1 \
    BOOTSTRAP_HASKELL_INSTALL_HLS=1 \
    BOOTSTRAP_HASKELL_ADJUST_BASHRC=1 \
    BOOTSTRAP_HASKELL_GHC_VERSION=${GHC_VERSION} \
    BOOTSTRAP_HASKELL_CABAL_VERSION=${CABAL_VERSION}
RUN curl -fsSL https://get-ghcup.haskell.org | sh && \
    rm -rf /home/vscode/.ghcup/tmp /home/vscode/.ghcup/cache

ENV PATH=/home/vscode/.ghcup/bin:/home/vscode/.cabal/bin:${PATH}

USER root

# ---------------------------------------------------------------------------
# 5. Smoke test — copied in so the image can verify itself
# ---------------------------------------------------------------------------
COPY smoke-test.sh /usr/local/bin/smoke-test
RUN chmod +x /usr/local/bin/smoke-test

USER vscode
