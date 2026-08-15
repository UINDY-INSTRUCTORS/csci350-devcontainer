import pytest
from level.manifest import Manifest
from level.grade import compute_level

M = Manifest(
    standard="S3", seed=1, floor="U",
    tiers=("smoke", "parse", "eval", "prop"),
    awards={"smoke": "U", "parse": "D", "eval": "S", "prop": "E"},
    timeout_s=120, timeouts={},
)

def results(**kw):
    base = {t: "pass" for t in M.tiers}
    base.update(kw)
    return base

def test_all_pass_is_top_award():
    assert compute_level(M, results()) == "E"

def test_stops_at_first_failure():
    assert compute_level(M, results(prop="fail")) == "S"
    assert compute_level(M, results(eval="fail", prop="fail")) == "D"

def test_first_tier_failing_gives_floor():
    assert compute_level(M, results(smoke="fail")) == "U"

def test_later_pass_cannot_jump_a_failed_gate():
    # prop passes but eval failed — eval gated, so S3 is D, not E
    assert compute_level(M, results(eval="fail", prop="pass")) == "D"

def test_timeout_counts_as_not_passing():
    assert compute_level(M, results(eval="timeout")) == "D"

def test_skip_counts_as_not_passing():
    assert compute_level(M, results(eval="skip", prop="skip")) == "D"

def test_missing_tier_result_counts_as_not_passing():
    partial = {"smoke": "pass", "parse": "pass"}
    assert compute_level(M, partial) == "D"

def test_rejects_unknown_result_value():
    with pytest.raises(ValueError, match="exploded"):
        compute_level(M, results(eval="exploded"))
