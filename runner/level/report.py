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
