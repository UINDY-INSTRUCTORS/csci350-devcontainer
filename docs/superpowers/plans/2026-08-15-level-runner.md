# S3 Level Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `level`, a command that runs an assignment's acceptance tiers in order and writes `assessment.json` recording the E/S/D/U level, so `make level` gives the same answer in a student's Codespace as in CI.

**Architecture:** A small dependency-light Python package baked into the course devcontainer image at `/opt/level`, exposed on `PATH` as `level` — following the `COPY smoke-test.sh /usr/local/bin/smoke-test` pattern already in the Dockerfile. It reads a per-repo `assessment.yml`, shells out to `make test-<tier>` for each tier in order, and applies a pure gating rule to produce a level. The runner knows nothing about JUnit, Racket, or QuickCheck — only Make target names and exit codes.

**Tech Stack:** Python 3.12 (stdlib + PyYAML), GNU Make, Docker/buildx, pytest.

**Spec:** `~/Development/quarto_reports/ai-feedback-system/docs/specs/2026-08-15-csci350-s3-acceptance-testing-design.md` (commits `a842431`, `492b633`)

## Scope: this is plan 1 of 3

The spec covers three separable deliverables. This plan builds only the first, which is working, testable software on its own.

| Plan | Deliverable | Status |
|---|---|---|
| **1 — this plan** | The `level` runner, in the image | — |
| 2 | Tier targets in the assignment templates + the Math Parser property generator | not written |
| 3 | CI workflow: test restoration from template, feedback issue rendering | not written |

Plan 1 is testable end to end without plans 2 or 3: a fixture repo with a hand-written Makefile exercises every path.

## Global Constraints

- **Python 3.12**, as shipped in `mcr.microsoft.com/devcontainers/base:ubuntu-24.04`. No other runtime may be introduced.
- **Dependencies: PyYAML only**, installed via apt as `python3-yaml`. Ubuntu 24.04 is PEP 668 externally-managed, so `pip install` into the system environment is not available without `--break-system-packages`; use apt.
- **The level is data, never an exit code.** `level` exits 0 whenever it successfully writes `assessment.json`, including when the level is U. It exits 1 only on harness error. A student sitting at D must not turn CI red.
- **Levels are exactly `E`, `S`, `D`, `U`.** No other value may appear in `assessment.json`.
- **Tier results are exactly `pass`, `fail`, `timeout`, `skip`.**
- **Determinism:** the runner passes the manifest's `seed` to every tier as the environment variable `LEVEL_SEED`. It never generates a seed itself.
- Image repo is `~/Development/courses/csci350-devcontainer` (currently one commit, `53ea9fb`, clean tree).

## Spec addendum adopted here

The spec's manifest has no timeout field, but §5 requires per-tier timeouts. This plan adds `timeout_s` — a required top-level default with an optional per-tier override:

```yaml
timeout_s: 120
timeouts: {prop: 600}
```

Fold this back into the spec when the plan is accepted.

## File Structure

```
csci350-devcontainer/
  runner/
    pyproject.toml            # pytest config only; the package is not pip-installed
    level/__init__.py
    level/manifest.py         # parse + validate assessment.yml       -> Manifest
    level/grade.py            # pure gating rule                       -> level string
    level/tiers.py            # run one make target under a timeout    -> TierRun
    level/report.py           # assemble + write assessment.json
    level/cli.py              # argv parsing, orchestration, exit codes
    tests/fixtures/passing/   # fixture repo: Makefile + assessment.yml
    tests/test_manifest.py
    tests/test_grade.py
    tests/test_tiers.py
    tests/test_report.py
    tests/test_cli.py
  Dockerfile                  # modify: apt python3-yaml; COPY runner; PATH shim
  smoke-test.sh               # modify: assert `level --version` works
```

Each module has one responsibility and no knowledge of the others' internals. `grade.py` is pure — no filesystem, no subprocess — which is why it is testable first and fastest.

---

### Task 1: Manifest parsing and validation

**Files:**
- Create: `runner/level/__init__.py`, `runner/level/manifest.py`, `runner/pyproject.toml`
- Test: `runner/tests/test_manifest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Manifest` frozen dataclass with fields `standard: str`, `seed: int`, `floor: str`, `tiers: tuple[str, ...]`, `awards: dict[str, str]`, `timeout_s: int`, `timeouts: dict[str, int]`; `load_manifest(path: Path) -> Manifest`; `ManifestError(Exception)`; and `Manifest.timeout_for(tier: str) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# runner/tests/test_manifest.py
import pytest
from pathlib import Path
from level.manifest import load_manifest, ManifestError

GOOD = """
standard: S3
seed: 20260929
floor: U
timeout_s: 120
timeouts: {prop: 600}
tiers:  [smoke, parse, eval, prop]
awards: {smoke: U, parse: D, eval: S, prop: E}
"""

def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "assessment.yml"
    p.write_text(text)
    return p

def test_loads_all_fields(tmp_path):
    m = load_manifest(write(tmp_path, GOOD))
    assert m.standard == "S3"
    assert m.seed == 20260929
    assert m.floor == "U"
    assert m.tiers == ("smoke", "parse", "eval", "prop")
    assert m.awards["prop"] == "E"

def test_timeout_for_uses_override_then_default(tmp_path):
    m = load_manifest(write(tmp_path, GOOD))
    assert m.timeout_for("prop") == 600
    assert m.timeout_for("eval") == 120

def test_rejects_award_for_unknown_tier(tmp_path):
    bad = GOOD.replace("awards: {smoke: U, parse: D, eval: S, prop: E}",
                       "awards: {smoke: U, parse: D, eval: S, prop: E, bogus: E}")
    with pytest.raises(ManifestError, match="bogus"):
        load_manifest(write(tmp_path, bad))

def test_rejects_tier_with_no_award(tmp_path):
    bad = GOOD.replace("awards: {smoke: U, parse: D, eval: S, prop: E}",
                       "awards: {smoke: U, parse: D, eval: S}")
    with pytest.raises(ManifestError, match="prop"):
        load_manifest(write(tmp_path, bad))

def test_rejects_invalid_level_value(tmp_path):
    bad = GOOD.replace("prop: E}", "prop: A}")
    with pytest.raises(ManifestError, match="A"):
        load_manifest(write(tmp_path, bad))

def test_rejects_missing_required_key(tmp_path):
    bad = GOOD.replace("seed: 20260929\n", "")
    with pytest.raises(ManifestError, match="seed"):
        load_manifest(write(tmp_path, bad))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd runner && python3 -m pytest tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'level'`

- [ ] **Step 3: Write minimal implementation**

```python
# runner/level/__init__.py
__version__ = "0.1.0"
```

```python
# runner/level/manifest.py
"""Parse and validate a repo's assessment.yml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

LEVELS = ("E", "S", "D", "U")
REQUIRED = ("standard", "seed", "floor", "tiers", "awards", "timeout_s")


class ManifestError(Exception):
    """The manifest is missing, malformed, or internally inconsistent."""


@dataclass(frozen=True)
class Manifest:
    standard: str
    seed: int
    floor: str
    tiers: tuple[str, ...]
    awards: dict[str, str]
    timeout_s: int
    timeouts: dict[str, int] = field(default_factory=dict)

    def timeout_for(self, tier: str) -> int:
        return self.timeouts.get(tier, self.timeout_s)


def load_manifest(path: Path) -> Manifest:
    try:
        raw = yaml.safe_load(Path(path).read_text())
    except FileNotFoundError as exc:
        raise ManifestError(f"no manifest at {path}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestError(f"{path} must be a YAML mapping")

    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise ManifestError(f"{path} missing required key(s): {', '.join(missing)}")

    tiers = tuple(raw["tiers"])
    awards = dict(raw["awards"])

    unknown = [t for t in awards if t not in tiers]
    if unknown:
        raise ManifestError(f"awards names tier(s) not in tiers: {', '.join(unknown)}")

    unawarded = [t for t in tiers if t not in awards]
    if unawarded:
        raise ManifestError(f"tier(s) with no award: {', '.join(unawarded)}")

    bad = sorted({v for v in [*awards.values(), raw["floor"]] if v not in LEVELS})
    if bad:
        raise ManifestError(f"not a valid level: {', '.join(bad)}")

    return Manifest(
        standard=str(raw["standard"]),
        seed=int(raw["seed"]),
        floor=str(raw["floor"]),
        tiers=tiers,
        awards=awards,
        timeout_s=int(raw["timeout_s"]),
        timeouts={str(k): int(v) for k, v in (raw.get("timeouts") or {}).items()},
    )
```

```toml
# runner/pyproject.toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd runner && python3 -m pytest tests/test_manifest.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add runner/pyproject.toml runner/level/__init__.py runner/level/manifest.py runner/tests/test_manifest.py
git commit -m "feat(level): parse and validate assessment.yml"
```

---

### Task 2: The gating rule

**Files:**
- Create: `runner/level/grade.py`
- Test: `runner/tests/test_grade.py`

**Interfaces:**
- Consumes: `Manifest` from Task 1.
- Produces: `compute_level(manifest: Manifest, results: dict[str, str]) -> str`, where `results` maps tier name to one of `pass`/`fail`/`timeout`/`skip`.

This is the heart of the spec and it is a pure function — no I/O. Getting it right here means the rest is plumbing.

- [ ] **Step 1: Write the failing test**

```python
# runner/tests/test_grade.py
import pytest
from level.manifest import Manifest
from level.grade import compute_level

M = Manifest(
    standard="S3", seed=1, floor="U",
    tiers=("smoke", "parse", "eval", "prop"),
    awards={"smoke": "U", "parse": "D", "eval": "S", "prop": "E"},
    timeout_s=120, timeouts={},
)

def results(**kw):
    base = {t: "pass" for t in M.tiers}
    base.update(kw)
    return base

def test_all_pass_is_top_award():
    assert compute_level(M, results()) == "E"

def test_stops_at_first_failure():
    assert compute_level(M, results(prop="fail")) == "S"
    assert compute_level(M, results(eval="fail", prop="fail")) == "D"

def test_first_tier_failing_gives_floor():
    assert compute_level(M, results(smoke="fail")) == "U"

def test_later_pass_cannot_jump_a_failed_gate():
    # prop passes but eval failed — eval gated, so S3 is D, not E
    assert compute_level(M, results(eval="fail", prop="pass")) == "D"

def test_timeout_counts_as_not_passing():
    assert compute_level(M, results(eval="timeout")) == "D"

def test_skip_counts_as_not_passing():
    assert compute_level(M, results(eval="skip", prop="skip")) == "D"

def test_missing_tier_result_counts_as_not_passing():
    partial = {"smoke": "pass", "parse": "pass"}
    assert compute_level(M, partial) == "D"

def test_rejects_unknown_result_value():
    with pytest.raises(ValueError, match="exploded"):
        compute_level(M, results(eval="exploded"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd runner && python3 -m pytest tests/test_grade.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'level.grade'`

- [ ] **Step 3: Write minimal implementation**

```python
# runner/level/grade.py
"""The gating rule: ordered tier results become a single achievement level."""
from __future__ import annotations

from .manifest import Manifest

RESULTS = ("pass", "fail", "timeout", "skip")


def compute_level(manifest: Manifest, results: dict[str, str]) -> str:
    """Return the level earned by the highest tier such that every tier up to
    and including it passed. A tier that is absent, failed, timed out, or was
    skipped stops the walk — so passing a later tier cannot jump a failed gate.
    """
    for value in results.values():
        if value not in RESULTS:
            raise ValueError(f"not a valid tier result: {value}")

    level = manifest.floor
    for tier in manifest.tiers:
        if results.get(tier) != "pass":
            return level
        level = manifest.awards[tier]
    return level
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd runner && python3 -m pytest tests/test_grade.py -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add runner/level/grade.py runner/tests/test_grade.py
git commit -m "feat(level): add the ordered gating rule"
```

---

### Task 3: Running one tier under a timeout

**Files:**
- Create: `runner/level/tiers.py`
- Test: `runner/tests/test_tiers.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `TierRun` frozen dataclass with fields `name: str`, `result: str`, `duration_s: float`, `output: str`; and `run_tier(name: str, repo: Path, timeout_s: int, seed: int) -> TierRun`.

`run_tier` invokes `make test-<name>` in `repo`, merging stderr into stdout, with `LEVEL_SEED` set in the environment. A non-zero exit is `fail`; exceeding `timeout_s` is `timeout`.

- [ ] **Step 1: Write the failing test**

```python
# runner/tests/test_tiers.py
import shutil
import pytest
from pathlib import Path
from level.tiers import run_tier

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

MAKEFILE = """\
.PHONY: test-ok test-bad test-slow test-seed
test-ok:
\t@echo tier ran
test-bad:
\t@echo boom; exit 3
test-slow:
\t@sleep 5
test-seed:
\t@echo seed=$$LEVEL_SEED
"""

@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "Makefile").write_text(MAKEFILE)
    return tmp_path

def test_zero_exit_is_pass(repo):
    run = run_tier("ok", repo, timeout_s=30, seed=7)
    assert run.result == "pass"
    assert run.name == "ok"
    assert "tier ran" in run.output
    assert run.duration_s >= 0

def test_nonzero_exit_is_fail(repo):
    run = run_tier("bad", repo, timeout_s=30, seed=7)
    assert run.result == "fail"
    assert "boom" in run.output

def test_exceeding_budget_is_timeout(repo):
    run = run_tier("slow", repo, timeout_s=1, seed=7)
    assert run.result == "timeout"
    assert "timed out after 1s" in run.output

def test_seed_is_exported_to_the_tier(repo):
    run = run_tier("seed", repo, timeout_s=30, seed=20260929)
    assert "seed=20260929" in run.output

def test_missing_target_is_fail_not_crash(repo):
    run = run_tier("nosuchtier", repo, timeout_s=30, seed=7)
    assert run.result == "fail"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd runner && python3 -m pytest tests/test_tiers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'level.tiers'`

- [ ] **Step 3: Write minimal implementation**

```python
# runner/level/tiers.py
"""Run a single acceptance tier as a make target, under a wall-clock budget."""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TierRun:
    name: str
    result: str
    duration_s: float
    output: str


def run_tier(name: str, repo: Path, timeout_s: int, seed: int) -> TierRun:
    env = {**os.environ, "LEVEL_SEED": str(seed)}
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["make", f"test-{name}"],
            cwd=str(repo),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.output or ""
        if isinstance(partial, bytes):
            partial = partial.decode(errors="replace")
        return TierRun(
            name=name,
            result="timeout",
            duration_s=time.monotonic() - started,
            output=f"{partial}\n[level] tier timed out after {timeout_s}s",
        )
    return TierRun(
        name=name,
        result="pass" if proc.returncode == 0 else "fail",
        duration_s=time.monotonic() - started,
        output=proc.stdout,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd runner && python3 -m pytest tests/test_tiers.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Commit**

```bash
git add runner/level/tiers.py runner/tests/test_tiers.py
git commit -m "feat(level): run a tier as a make target under a timeout"
```

---

### Task 4: Assembling assessment.json

**Files:**
- Create: `runner/level/report.py`
- Test: `runner/tests/test_report.py`

**Interfaces:**
- Consumes: `Manifest` (Task 1), `compute_level` (Task 2), `TierRun` (Task 3).
- Produces: `build_report(manifest: Manifest, runs: list[TierRun], status: str = "ok") -> dict` and `write_report(report: dict, path: Path) -> None`.

When `status` is `"error"`, `build_report` omits `level` entirely — §5 requires the level be *withheld* on harness failure, not set to U.

- [ ] **Step 1: Write the failing test**

```python
# runner/tests/test_report.py
import json
from pathlib import Path
from level.manifest import Manifest
from level.tiers import TierRun
from level.report import build_report, write_report

M = Manifest(
    standard="S3", seed=20260929, floor="U",
    tiers=("smoke", "parse", "eval", "prop"),
    awards={"smoke": "U", "parse": "D", "eval": "S", "prop": "E"},
    timeout_s=120, timeouts={},
)

RUNS = [
    TierRun("smoke", "pass", 0.4, "ok"),
    TierRun("parse", "pass", 1.2, "ok"),
    TierRun("eval",  "pass", 2.0, "ok"),
    TierRun("prop",  "fail", 3.1, "1 case failed"),
]

def test_reports_level_and_metadata():
    r = build_report(M, RUNS)
    assert r["status"] == "ok"
    assert r["standard"] == "S3"
    assert r["seed"] == 20260929
    assert r["level"] == "S"

def test_reports_every_tier_in_manifest_order():
    r = build_report(M, RUNS)
    assert [t["name"] for t in r["tiers"]] == ["smoke", "parse", "eval", "prop"]
    assert r["tiers"][3]["result"] == "fail"
    assert r["tiers"][3]["output"] == "1 case failed"

def test_error_status_withholds_the_level():
    r = build_report(M, RUNS[:1], status="error")
    assert r["status"] == "error"
    assert "level" not in r

def test_write_report_emits_valid_json(tmp_path: Path):
    out = tmp_path / "assessment.json"
    write_report(build_report(M, RUNS), out)
    assert json.loads(out.read_text())["level"] == "S"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd runner && python3 -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'level.report'`

- [ ] **Step 3: Write minimal implementation**

```python
# runner/level/report.py
"""Assemble and write assessment.json."""
from __future__ import annotations

import json
from pathlib import Path

from .grade import compute_level
from .manifest import Manifest
from .tiers import TierRun


def build_report(manifest: Manifest, runs: list[TierRun], status: str = "ok") -> dict:
    by_name = {r.name: r for r in runs}
    report: dict = {
        "status": status,
        "standard": manifest.standard,
        "seed": manifest.seed,
    }
    if status == "ok":
        report["level"] = compute_level(
            manifest, {name: run.result for name, run in by_name.items()}
        )
    report["tiers"] = [
        {
            "name": name,
            "result": by_name[name].result if name in by_name else "skip",
            "duration_s": round(by_name[name].duration_s, 3) if name in by_name else 0.0,
            "output": by_name[name].output if name in by_name else "",
        }
        for name in manifest.tiers
    ]
    return report


def write_report(report: dict, path: Path) -> None:
    Path(path).write_text(json.dumps(report, indent=2) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd runner && python3 -m pytest tests/test_report.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add runner/level/report.py runner/tests/test_report.py
git commit -m "feat(level): assemble assessment.json, withholding level on error"
```

---

### Task 5: The CLI

**Files:**
- Create: `runner/level/cli.py`, `runner/tests/fixtures/passing/Makefile`, `runner/tests/fixtures/passing/assessment.yml`
- Test: `runner/tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `main(argv: list[str] | None = None) -> int`. Flags: `--repo PATH` (default `.`), `--out PATH` (default `<repo>/assessment.json`), `--version`.

Exit code contract, per Global Constraints: **0 whenever a report is written**, including level U; **1 only on harness error** (missing or invalid manifest). All tiers run even after one fails — the gating happens in `compute_level`, never by stopping early.

- [ ] **Step 1: Write the failing test**

```python
# runner/tests/test_cli.py
import json
import shutil
import pytest
from pathlib import Path
from level.cli import main

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

FIXTURE = Path(__file__).parent / "fixtures" / "passing"

@pytest.fixture
def repo(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE, tmp_path / "repo")
    return tmp_path / "repo"

def test_writes_report_and_exits_zero(repo):
    assert main(["--repo", str(repo)]) == 0
    data = json.loads((repo / "assessment.json").read_text())
    assert data["level"] == "E"
    assert data["status"] == "ok"

def test_runs_every_tier_even_after_a_failure(repo):
    (repo / "FAIL_EVAL").touch()          # fixture Makefile fails test-eval when present
    assert main(["--repo", str(repo)]) == 0
    data = json.loads((repo / "assessment.json").read_text())
    assert data["level"] == "D"
    assert [t["result"] for t in data["tiers"]] == ["pass", "pass", "fail", "pass"]

def test_missing_manifest_is_harness_error(repo):
    (repo / "assessment.yml").unlink()
    assert main(["--repo", str(repo)]) == 1

def test_out_flag_redirects_the_report(repo, tmp_path):
    out = tmp_path / "elsewhere.json"
    assert main(["--repo", str(repo), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["standard"] == "S3"
```

- [ ] **Step 2: Create the fixture repo**

```make
# runner/tests/fixtures/passing/Makefile
.PHONY: test-smoke test-parse test-eval test-prop
test-smoke:
	@echo smoke ok
test-parse:
	@echo parse ok
test-eval:
	@if [ -f FAIL_EVAL ]; then echo eval broke; exit 1; else echo eval ok; fi
test-prop:
	@echo "prop ok seed=$$LEVEL_SEED"
```

```yaml
# runner/tests/fixtures/passing/assessment.yml
standard: S3
seed: 20260929
floor: U
timeout_s: 60
tiers:  [smoke, parse, eval, prop]
awards: {smoke: U, parse: D, eval: S, prop: E}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd runner && python3 -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'level.cli'`

- [ ] **Step 4: Write minimal implementation**

```python
# runner/level/cli.py
"""`level` — run an assignment's acceptance tiers and write assessment.json."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .manifest import ManifestError, load_manifest
from .report import build_report, write_report
from .tiers import run_tier


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="level",
        description="Run acceptance tiers and record the achievement level.",
    )
    parser.add_argument("--repo", default=".", help="assignment repo (default: .)")
    parser.add_argument("--out", default=None, help="output path (default: <repo>/assessment.json)")
    parser.add_argument("--version", action="version", version=f"level {__version__}")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    out = Path(args.out) if args.out else repo / "assessment.json"

    try:
        manifest = load_manifest(repo / "assessment.yml")
    except ManifestError as exc:
        print(f"level: {exc}", file=sys.stderr)
        return 1

    runs = [
        run_tier(tier, repo, manifest.timeout_for(tier), manifest.seed)
        for tier in manifest.tiers
    ]

    report = build_report(manifest, runs)
    write_report(report, out)
    print(f"level: {report['level']}  ({out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd runner && python3 -m pytest -v`
Expected: PASS, 23 tests across all five files

- [ ] **Step 6: Commit**

```bash
git add runner/level/cli.py runner/tests/test_cli.py runner/tests/fixtures
git commit -m "feat(level): add the CLI and its exit-code contract"
```

---

### Task 6: Bake the runner into the image

**Files:**
- Modify: `Dockerfile` (apt package list; new COPY and shim near the existing `COPY smoke-test.sh` at line 129)
- Modify: `smoke-test.sh`
- Test: `smoke-test.sh` is itself the test, run inside the built image.

**Interfaces:**
- Consumes: the `runner/` package from Tasks 1–5.
- Produces: `level` on `PATH` inside `ghcr.io/uindy-instructors/csci350:fa26`, resolving to `/opt/level/level/cli.py`.

- [ ] **Step 1: Add the failing assertion to the smoke test**

Append to `smoke-test.sh`, matching the style of the checks already there:

```bash
echo "--- level runner ---"
level --version || { echo "FAIL: level not on PATH"; exit 1; }
python3 -c "import yaml" || { echo "FAIL: PyYAML missing"; exit 1; }
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker buildx build --load -t csci350:test . && docker run --rm csci350:test smoke-test`
Expected: FAIL with "FAIL: level not on PATH"

- [ ] **Step 3: Add PyYAML to the apt package list**

In the `apt-get install` block (around line 44), add `python3-yaml` to the list, keeping alphabetical order within the existing entries:

```dockerfile
        openjdk-21-jdk \
        pkg-config \
        python3-yaml \
        swi-prolog-nox \
```

Use apt, not pip: Ubuntu 24.04 is PEP 668 externally-managed and `pip install` into the system environment fails without `--break-system-packages`.

- [ ] **Step 4: Copy the runner in and put it on PATH**

Immediately after the existing `COPY smoke-test.sh /usr/local/bin/smoke-test` line, add:

```dockerfile
# The S3 acceptance-tier runner. Lives in the image rather than in each
# assignment repo so CI and the student's Codespace can never disagree about
# what `make level` does. See the vault note CSCI-350-Fall-2026-Plan §3a.
COPY runner/level /opt/level/level
RUN printf '#!/bin/sh\nexec python3 -m level.cli "$@"\n' > /usr/local/bin/level \
    && chmod +x /usr/local/bin/level
ENV PYTHONPATH=/opt/level
```

- [ ] **Step 5: Rebuild and verify the smoke test passes**

Run: `docker buildx build --load -t csci350:test . && docker run --rm csci350:test smoke-test`
Expected: PASS — `level 0.1.0` printed, no FAIL lines

- [ ] **Step 6: Verify end to end against the fixture**

Run:
```bash
docker run --rm -v "$PWD/runner/tests/fixtures/passing:/w" -w /w csci350:test \
  sh -c 'level --repo . && cat assessment.json'
```
Expected: prints `level: E` and a JSON document whose `level` is `E` and whose `prop` tier output contains `seed=20260929`.

- [ ] **Step 7: Commit**

```bash
git add Dockerfile smoke-test.sh
git commit -m "feat(image): ship the level runner and PyYAML"
```

---

## Self-Review

**Spec coverage.** §2 level definitions → Task 2. §2 gating, all-or-nothing, seeding → Tasks 2, 3, 5. §2.1 roll-up across artifacts → *not covered, and correctly so*: that is a gradebook-level rule about combining two assignments' levels, not something a single-repo runner can see. It belongs with the Brightspace import, which §6 puts out of scope. §4.1 Make targets → Task 3 (`make test-<tier>`) and Task 5 (all tiers always run). §4.2 manifest → Task 1. §4.3 output schema → Task 4. §4.4 local parity → Task 6, which is the reason the runner is in the image. §5 build failure → falls out of the smoke tier failing, giving U. §5 timeouts → Task 3. §5 harness error withholds level → Task 4 and Task 5's exit-code contract. §5 test restoration → **plan 3**, since it is a CI concern requiring the template ref.

**Placeholder scan.** No TBD/TODO; every code step carries runnable code; no "similar to Task N".

**Type consistency.** `Manifest` fields are identical in Tasks 1, 2, and 4. `TierRun(name, result, duration_s, output)` is constructed in Task 3 and consumed positionally in Task 4's test in the same order. `compute_level(manifest, results)` has one signature throughout. `run_tier(name, repo, timeout_s, seed)` is called in Task 5 with exactly those four arguments.

**One gap worth naming.** §5 says a per-*test* timeout should stop one hanging case from masking the tests after it. This plan implements only the per-*tier* timeout — a hang inside `test-eval` fails the whole eval tier rather than just that case. Per-test timeouts have to live in the test framework, so they land in plan 2 with the tier targets. The consequence today: a student with one infinite loop sees the whole tier time out rather than one case, which understates what does work. Acceptable for the runner; must be closed before the Math Parser goes out.
