import json
from pathlib import Path
from level.manifest import Manifest
from level.tiers import TierRun
from level.report import build_report, write_report

M = Manifest(
    standard="S3", seed=20260929, floor="U",
    tiers=("smoke", "parse", "eval", "prop"),
    awards={"smoke": "U", "parse": "D", "eval": "S", "prop": "E"},
    timeout_s=120, timeouts={},
)

RUNS = [
    TierRun("smoke", "pass", 0.4, "ok"),
    TierRun("parse", "pass", 1.2, "ok"),
    TierRun("eval",  "pass", 2.0, "ok"),
    TierRun("prop",  "fail", 3.1, "1 case failed"),
]

def test_reports_level_and_metadata():
    r = build_report(M, RUNS)
    assert r["status"] == "ok"
    assert r["standard"] == "S3"
    assert r["seed"] == 20260929
    assert r["level"] == "S"

def test_reports_every_tier_in_manifest_order():
    r = build_report(M, RUNS)
    assert [t["name"] for t in r["tiers"]] == ["smoke", "parse", "eval", "prop"]
    assert r["tiers"][3]["result"] == "fail"
    assert r["tiers"][3]["output"] == "1 case failed"

def test_error_status_withholds_the_level():
    r = build_report(M, RUNS[:1], status="error")
    assert r["status"] == "error"
    assert "level" not in r

def test_write_report_emits_valid_json(tmp_path: Path):
    out = tmp_path / "assessment.json"
    write_report(build_report(M, RUNS), out)
    assert json.loads(out.read_text())["level"] == "S"
