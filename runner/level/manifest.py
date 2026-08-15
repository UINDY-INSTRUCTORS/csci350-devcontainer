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

    try:
        if not isinstance(raw["tiers"], list):
            raise TypeError(f"tiers must be a list, got {type(raw['tiers']).__name__}")
        tiers = tuple(raw["tiers"])
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"tiers: {exc}") from exc

    if not tiers:
        # An empty tiers list loads cleanly, compute_level falls straight
        # through to `floor`, and every student silently gets the floor
        # award (e.g. U) with a green exit — the exact spurious-failure
        # mode this design exists to prevent, arriving via a typo.
        raise ManifestError("tiers must not be empty")

    try:
        if not isinstance(raw["awards"], dict):
            raise TypeError(f"awards must be a mapping, got {type(raw['awards']).__name__}")
        awards = dict(raw["awards"])
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"awards: {exc}") from exc

    unknown = sorted({str(t) for t in awards if t not in tiers})
    if unknown:
        raise ManifestError(f"awards names tier(s) not in tiers: {', '.join(unknown)}")

    unawarded = sorted({str(t) for t in tiers if t not in awards})
    if unawarded:
        raise ManifestError(f"tier(s) with no award: {', '.join(unawarded)}")

    bad = sorted({str(v) for v in [*awards.values(), raw["floor"]] if v not in LEVELS})
    if bad:
        raise ManifestError(f"not a valid level: {', '.join(bad)}")

    try:
        seed = int(raw["seed"])
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"seed must be an integer: {exc}") from exc

    try:
        timeout_s = int(raw["timeout_s"])
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"timeout_s must be an integer: {exc}") from exc

    timeouts_dict = raw.get("timeouts") or {}
    if not isinstance(timeouts_dict, dict):
        raise ManifestError(
            f"timeouts must be a mapping, got {type(timeouts_dict).__name__}"
        )
    timeouts = {}
    for k, v in timeouts_dict.items():
        try:
            timeouts[str(k)] = int(v)
        except (TypeError, ValueError) as exc:
            raise ManifestError(f"timeouts[{k!r}] must be an integer: {exc}") from exc

    return Manifest(
        standard=str(raw["standard"]),
        seed=seed,
        floor=str(raw["floor"]),
        tiers=tiers,
        awards=awards,
        timeout_s=timeout_s,
        timeouts=timeouts,
    )
