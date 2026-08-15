"""`level` — run an assignment's acceptance tiers and write assessment.json."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .manifest import ManifestError, load_manifest
from .report import build_report, write_report
from .tiers import TierRun, run_tier


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

    runs: list[TierRun] = []
    status = "ok"
    for tier in manifest.tiers:
        try:
            runs.append(run_tier(tier, repo, manifest.timeout_for(tier), manifest.seed))
        except Exception as exc:
            # A tier is untrusted student code; anything it does — including
            # producing output that raises far from an OSError (e.g. a
            # UnicodeDecodeError, which is a ValueError) — must still yield a
            # written report with the level withheld, never a bare traceback.
            print(f"level: could not run tier {tier!r}: {exc}", file=sys.stderr)
            status = "error"
            break

    report = build_report(manifest, runs, status=status)

    try:
        write_report(report, out)
    except OSError as exc:
        print(f"level: could not write report to {out}: {exc}", file=sys.stderr)
        return 1

    if status == "error":
        return 1

    print(f"level: {report['level']}  ({out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
