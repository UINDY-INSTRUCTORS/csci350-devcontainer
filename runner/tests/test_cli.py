import json
import shutil
import pytest
from pathlib import Path
from level.cli import main

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

FIXTURE = Path(__file__).parent / "fixtures" / "passing"

@pytest.fixture
def repo(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE, tmp_path / "repo")
    return tmp_path / "repo"

def test_writes_report_and_exits_zero(repo):
    assert main(["--repo", str(repo)]) == 0
    data = json.loads((repo / "assessment.json").read_text())
    assert data["level"] == "E"
    assert data["status"] == "ok"

def test_runs_every_tier_even_after_a_failure(repo):
    (repo / "FAIL_EVAL").touch()          # fixture Makefile fails test-eval when present
    assert main(["--repo", str(repo)]) == 0
    data = json.loads((repo / "assessment.json").read_text())
    assert data["level"] == "D"
    assert [t["result"] for t in data["tiers"]] == ["pass", "pass", "fail", "pass"]

def test_missing_manifest_is_harness_error(repo):
    (repo / "assessment.yml").unlink()
    assert main(["--repo", str(repo)]) == 1

def test_out_flag_redirects_the_report(repo, tmp_path):
    out = tmp_path / "elsewhere.json"
    assert main(["--repo", str(repo), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["standard"] == "S3"

def test_tier_execution_failure_withholds_level(repo, monkeypatch, capsys):
    import level.cli as cli_mod

    def boom(*args, **kwargs):
        raise OSError("make: command not found")

    monkeypatch.setattr(cli_mod, "run_tier", boom)
    assert main(["--repo", str(repo)]) == 1
    data = json.loads((repo / "assessment.json").read_text())
    assert data["status"] == "error"
    assert "level" not in data
    err = capsys.readouterr().err
    assert err.startswith("level:")
    assert "Traceback" not in err

def test_out_directory_missing_is_harness_error(repo, tmp_path, capsys):
    out = tmp_path / "nowhere" / "assessment.json"
    assert main(["--repo", str(repo), "--out", str(out)]) == 1
    assert not out.exists()
    err = capsys.readouterr().err
    assert err.startswith("level:")
    assert str(out) in err
    assert "Traceback" not in err
