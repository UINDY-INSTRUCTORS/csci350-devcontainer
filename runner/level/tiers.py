"""Run a single acceptance tier as a make target, under a wall-clock budget."""
from __future__ import annotations

import os
import signal
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


# A tier is untrusted student code (e.g. a left-recursive parser looping on
# printf inside its timeout budget). communicate() accumulates everything
# a tier prints into memory, and it all lands in assessment.json, so the
# per-tier timeout bounds time but not bytes on its own — cap output size
# too. Keep the first half (build header) and the last half (where
# diagnostics usually are) with a clear elision marker between them.
OUTPUT_CAP = 64 * 1024
OUTPUT_HALF = OUTPUT_CAP // 2
TRUNCATION_MARKER = "\n\n... [level: output truncated, {omitted} chars omitted] ...\n\n"


def _truncate(output: str) -> str:
    if len(output) <= OUTPUT_CAP:
        return output
    omitted = len(output) - OUTPUT_CAP
    marker = TRUNCATION_MARKER.format(omitted=omitted)
    return output[:OUTPUT_HALF] + marker + output[-OUTPUT_HALF:]


def run_tier(name: str, repo: Path, timeout_s: int, seed: int) -> TierRun:
    env = {**os.environ, "LEVEL_SEED": str(seed)}
    started = time.monotonic()

    proc = subprocess.Popen(
        ["make", f"test-{name}"],
        cwd=str(repo),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        start_new_session=True,
    )

    try:
        output, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        # Kill the entire process group to clean up descendants
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            # Process group already dead (ProcessLookupError is a subclass
            # of OSError, so a single except covers it)
            pass
        # Drain remaining output
        output, _ = proc.communicate()
        return TierRun(
            name=name,
            result="timeout",
            duration_s=time.monotonic() - started,
            output=f"{_truncate(output)}\n[level] tier timed out after {timeout_s}s",
        )

    return TierRun(
        name=name,
        result="pass" if proc.returncode == 0 else "fail",
        duration_s=time.monotonic() - started,
        output=_truncate(output),
    )
