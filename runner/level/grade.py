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
