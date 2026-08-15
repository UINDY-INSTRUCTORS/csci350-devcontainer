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
    # Verify all tiers present in manifest order, with real and synthesized entries
    assert len(r["tiers"]) == 4
    assert [t["name"] for t in r["tiers"]] == ["smoke", "parse", "eval", "prop"]
    # Real entry for smoke (passed in RUNS[:1])
    assert r["tiers"][0]["result"] == "pass"
    assert r["tiers"][0]["duration_s"] == 0.4
    assert r["tiers"][0]["output"] == "ok"
    # Synthesized skip entries for parse, eval, prop (not in RUNS[:1])
    assert r["tiers"][1]["result"] == "skip"
    assert r["tiers"][1]["duration_s"] == 0.0
    assert r["tiers"][1]["output"] == ""
    assert r["tiers"][2]["result"] == "skip"
    assert r["tiers"][2]["duration_s"] == 0.0
    assert r["tiers"][2]["output"] == ""
    assert r["tiers"][3]["result"] == "skip"
    assert r["tiers"][3]["duration_s"] == 0.0
    assert r["tiers"][3]["output"] == ""

def test_write_report_emits_valid_json(tmp_path: Path):
    out = tmp_path / "assessment.json"
    write_report(build_report(M, RUNS), out)
    assert json.loads(out.read_text())["level"] == "S"
