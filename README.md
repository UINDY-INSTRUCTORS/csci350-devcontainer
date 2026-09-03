# csci350-devcontainer

Course toolchain image for **CSCI-350 Programming Languages** (Fall 2026).

One image with every language the course touches, published to GHCR. Students
open a Codespace and everything is already there; CI runs the identical image.

**Design rationale lives in the vault:** `1. Projects/Classes/CSCI-350-Fall-2026-Plan.md` §4c.

---

## What's in it

| Tool | Used in | Install route |
|---|---|---|
| **Java 21** + JUnit console standalone | Wks 1–2 warmup; tokenizer / parser / interpreter projects | apt + jar to `$JUNIT_JAR` |
| **Racket 9.2** + `racket-langserver` | Wks 8–11, Scheme path | official installer |
| **SBCL** | Wks 8–11, Common Lisp path | apt |
| **GHC 9.6.6** + cabal + HLS | Wk 10, Haskell | ghcup |
| **SWI-Prolog** | Wks 12–13 | apt (`-nox`; the GUI metapackage drags in mesa + X) |
| **Python 3** + pytest | tooling, alternate parser implementation | apt |

**Both Lisp dialects ship deliberately.** The Scheme-vs-Common-Lisp choice
(vault §4b(e)) is still open — Paul Talaga's inherited HW 02 is Common Lisp,
while Sebesta §15.5 is Scheme. Neither runtime is large enough to be worth
blocking the decision on, so the image supports either and the pedagogy call
can be made in August.

---

## Usage

### In an assignment template

Copy `template/devcontainer.json` to `.devcontainer/devcontainer.json` in the
template repo. That's the whole integration — it pulls the published image.

```jsonc
{ "image": "ghcr.io/uindy-instructors/csci350:fa26" }
```

### As the CI runner

The same image backs automated feedback, so "works in my Codespace, fails in
CI" cannot happen for toolchain reasons:

```yaml
jobs:
  analyze:
    runs-on: ubuntu-latest
    container: ghcr.io/uindy-instructors/csci350:fa26
```

### Locally

**Always validate `linux/amd64`** — that is what Codespaces runs. A native arm64
build on an Apple Silicon Mac proves nothing about what students actually get.

```bash
docker buildx build --platform linux/amd64 --load -t csci350 .
docker run --rm --platform linux/amd64 csci350 smoke-test
```

### ⚠️ amd64 cannot be built on Apple Silicon — Racket dies under QEMU

Verified 2026-08-09. An emulated `linux/amd64` build fails at the
`raco pkg install racket-langserver` step:

```
Error: error reading from ~a
("petite")
Aborted                                   exit code 134 (SIGABRT)
```

`petite` is a **Chez Scheme boot file**. Racket CS is built on Chez, whose
code generation and boot-file loading QEMU user-mode emulation does not
handle. The identical step succeeds natively on arm64, and native amd64 is
Racket's most-travelled path, so this is an emulation artifact rather than a
defect in the image.

**Consequence: amd64 must be built on real amd64 hardware.** Options:

1. **GitHub Actions** (recommended) — `ubuntu-latest` runners are native amd64,
   free for public repos, and the publish workflow already smoke-tests what it
   builds. This also exercises the exact path that produces the published image.
2. An Intel Mac / amd64 Linux box, if a local loop is wanted.

Building native arm64 locally is still useful for fast iteration on everything
*except* the Racket layer — just don't mistake it for verification of what
students run.

---

## Publishing

`.github/workflows/publish.yml` builds **linux/amd64** on GitHub's native amd64
runners, pushes to GHCR, and then runs the smoke test against what it just
published — so an image that can't run Racket fails the build rather than
surprising a student.

```bash
gh workflow run "Publish course image" -f tag=fa26
gh run watch
```

### Adding arm64 later

**Do not just add `linux/arm64` to `platforms:`.** GitHub's standard runners are
amd64, so that leg would build under QEMU and hit the same Chez boot-file abort
described above — the identical failure, mirrored.

The correct approach is a matrix over *native* runners, each pushing by digest,
plus a final job that merges them into one manifest list:

```yaml
strategy:
  matrix:
    include:
      - platform: linux/amd64
        runner: ubuntu-latest
      - platform: linux/arm64
        runner: ubuntu-24.04-arm    # native arm64 runner
```
…then `docker buildx imagetools create` to combine the digests.

✅ **Done 2026-09-03** — implemented in `.github/workflows/publish-multiarch.yml`,
after local Apple Silicon development did become a real need: `docker pull` of
`:fa26` on an M-series Mac fails with

    no matching manifest for linux/arm64/v8 in the manifest list entries

That workflow is **manual-only** and defaults to tag `fa26b`, so it cannot
disturb `:fa26`. `publish.yml` is untouched and remains the amd64 path.
Codespaces is amd64, so nothing student-facing depends on the arm64 leg.

**Make the package public** — students are added by `gh rba` as *outside
collaborators*, not org members, so a private package would fail to pull and the
symptom is a Codespace that won't start.

### Tag discipline

Templates pin `:fa26`. Don't rebuild that tag mid-term — it would change the
environment under live assignments. Publish `:fa26b` and bump templates
deliberately instead.

---

## Verifying

`smoke-test.sh` is baked in as `/usr/local/bin/smoke-test`. It doesn't just check
`--version`; it compiles or evaluates a trivial program in each language, because
a half-installed GHC or Racket will still answer `--version` happily.

```
$ docker run --rm csci350 smoke-test
== versions ==
  ok   java             openjdk version "21.0.x"
  ...
== each language actually executes ==
  ok   java run         java ok
  ok   racket run       racket ok
  ...
all 17 checks passed
```

---

## Pinned versions — verify before the first real build

These are `ARG`s at the top of the `Dockerfile`. Three were chosen from
documentation rather than from a completed build, so **the first build is the
verification step**:

All four are **confirmed by a successful arm64 build + smoke test** (2026-08-09).
Resolved versions:

| ARG | Default | Resolved to |
|---|---|---|
| `RACKET_VERSION` | `9.2` | Racket v9.2 [cs] |
| `JUNIT_VERSION` | `1.14.4` | jar present at `$JUNIT_JAR` |
| `GHC_VERSION` | `9.6.6` | GHC 9.6.6, HLS 2.14.0.0 |
| `CABAL_VERSION` | `3.10.3.0` | cabal-install 3.10.3.0 |

Also picked up: OpenJDK 21.0.11, SBCL 2.2.9, SWI-Prolog 9.0.4, Python 3.12.3,
pytest 9.1.1.

**Still to confirm on amd64** — see the QEMU note above; the arm64 pass does not
carry over automatically, though only the Racket layer is actually in doubt.

**On the JUnit pin.** Paul's material ships `1.13.0-M3` — a *milestone* build, which
shouldn't be baked into a course image. Meanwhile the artifact's current release is
**6.1.3**: JUnit renumbered, and 6.x is a major version with breaking changes that
would not run his Jupiter tests unchanged. `1.14.4` is the last stable release on the
1.x line, so his existing test classes work as written and nothing depends on a
milestone. Revisit only if you rewrite the test suites.

The smoke test catches all of these immediately — a bad URL fails the build, a
bad install fails the test.

### HLS on arm64 — resolved

Flagged as a risk before the first build (HLS has historically had thinner
aarch64 coverage). **Not a problem:** ghcup resolves
`haskell-language-server-2.14.0.0-aarch64-linux-deb12` and installs it, so both
arches get full Haskell IDE support.

Kept here as a note because it's the layer most likely to break on a future GHC
bump. If a later arm64 build fails at the ghcup step, the fallback is to drop
`BOOTSTRAP_HASKELL_INSTALL_HLS=1` for arm64 only — GHC itself is unaffected, and
Codespaces (amd64) keeps HLS regardless.

### Size

~4–5 GB, of which **GHC and HLS are roughly half**. If that ever becomes a
problem, the natural split is a `:fa26-noghc` variant for the Java/Lisp/Prolog
weeks, at the cost of maintaining two images. Not worth it unless pull times
actually hurt.
