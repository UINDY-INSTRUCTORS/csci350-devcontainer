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
