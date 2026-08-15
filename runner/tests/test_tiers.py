import shutil
import pytest
import time
from pathlib import Path
from level.tiers import run_tier

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

MAKEFILE = """\
.PHONY: test-ok test-bad test-slow test-seed test-background test-badbytes
test-ok:
\t@echo tier ran
test-bad:
\t@echo boom; exit 3
test-slow:
\t@sleep 5
test-seed:
\t@echo seed=$$LEVEL_SEED
test-background:
\t@sh -c 'while true; do echo x >> marker.txt; sleep 0.1; done'
test-badbytes:
\t@printf 'before\\377after\\n'
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

def test_non_utf8_output_does_not_crash_the_harness(repo):
    # UnicodeDecodeError subclasses ValueError, not OSError — strict
    # decoding here would raise past cli.py's guard and leave no report
    # written at all. errors="replace" must absorb it.
    run = run_tier("badbytes", repo, timeout_s=30, seed=7)
    assert run.result == "pass"
    assert "before" in run.output
    assert "after" in run.output
    assert "�" in run.output

def test_descendants_are_killed_on_timeout(repo):
    marker_file = repo / "marker.txt"
    run = run_tier("background", repo, timeout_s=0.5, seed=7)
    assert run.result == "timeout"

    # Capture size immediately after timeout
    size_at_timeout = marker_file.stat().st_size if marker_file.exists() else 0

    # Sleep to give any remaining descendants time to write more
    time.sleep(0.5)

    # Verify the file hasn't grown (descendant is dead)
    size_after_sleep = marker_file.stat().st_size if marker_file.exists() else 0
    assert size_after_sleep == size_at_timeout, \
        f"Descendant process still running: {size_at_timeout} -> {size_after_sleep}"
