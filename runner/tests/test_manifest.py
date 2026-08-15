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

def test_rejects_seed_not_integer(tmp_path):
    bad = GOOD.replace("seed: 20260929", "seed: not_a_number")
    with pytest.raises(ManifestError, match="seed"):
        load_manifest(write(tmp_path, bad))

def test_rejects_timeout_s_not_integer(tmp_path):
    bad = GOOD.replace("timeout_s: 120", "timeout_s: invalid")
    with pytest.raises(ManifestError, match="timeout_s"):
        load_manifest(write(tmp_path, bad))

def test_rejects_tiers_not_list(tmp_path):
    bad = GOOD.replace("tiers:  [smoke, parse, eval, prop]", "tiers: smoke")
    with pytest.raises(ManifestError, match="tiers"):
        load_manifest(write(tmp_path, bad))

def test_rejects_awards_not_mapping(tmp_path):
    bad = GOOD.replace("awards: {smoke: U, parse: D, eval: S, prop: E}", "awards: [U, D, S, E]")
    with pytest.raises(ManifestError, match="awards"):
        load_manifest(write(tmp_path, bad))

def test_rejects_timeout_value_not_integer(tmp_path):
    bad = GOOD.replace("timeouts: {prop: 600}", "timeouts: {prop: not_a_number}")
    with pytest.raises(ManifestError, match="timeouts"):
        load_manifest(write(tmp_path, bad))
