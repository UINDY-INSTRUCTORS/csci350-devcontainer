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
