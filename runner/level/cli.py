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
