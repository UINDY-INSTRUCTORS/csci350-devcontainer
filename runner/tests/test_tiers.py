import shutil
import pytest
from pathlib import Path
from level.tiers import run_tier

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

MAKEFILE = """\
.PHONY: test-ok test-bad test-slow test-seed
test-ok:
\t@echo tier ran
test-bad:
\t@echo boom; exit 3
test-slow:
\t@sleep 5
test-seed:
\t@echo seed=$$LEVEL_SEED
"""

@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "Makefile").write_text(MAKEFILE)
    return tmp_path

def test_zero_exit_is_pass(repo):
    run = run_tier("ok", repo, timeout_s=30, seed=7)
    assert run.result == "pass"
    assert run.name == "ok"
    assert "tier ran" in run.output
    assert run.duration_s >= 0

def test_nonzero_exit_is_fail(repo):
    run = run_tier("bad", repo, timeout_s=30, seed=7)
    assert run.result == "fail"
    assert "boom" in run.output

def test_exceeding_budget_is_timeout(repo):
    run = run_tier("slow", repo, timeout_s=1, seed=7)
    assert run.result == "timeout"
    assert "timed out after 1s" in run.output

def test_seed_is_exported_to_the_tier(repo):
    run = run_tier("seed", repo, timeout_s=30, seed=20260929)
    assert "seed=20260929" in run.output

def test_missing_target_is_fail_not_crash(repo):
    run = run_tier("nosuchtier", repo, timeout_s=30, seed=7)
    assert run.result == "fail"
