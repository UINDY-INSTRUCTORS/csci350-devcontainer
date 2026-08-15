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
        start_new_session=True,
    )

    try:
        output, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        # Kill the entire process group to clean up descendants
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            # Process group already dead
            pass
        # Drain remaining output
        output, _ = proc.communicate()
        return TierRun(
            name=name,
            result="timeout",
            duration_s=time.monotonic() - started,
            output=f"{output}\n[level] tier timed out after {timeout_s}s",
        )

    return TierRun(
        name=name,
        result="pass" if proc.returncode == 0 else "fail",
        duration_s=time.monotonic() - started,
        output=output,
    )
