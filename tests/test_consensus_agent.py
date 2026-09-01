"""Tests for the Consensus Agent (Loop 2).

Follows the Loop 2 spec in ``md/loop_engineering_prompt.md``:

  * weighted majority vote  (weight = cfg.weight * health.success_rate)
  * consensus_score = 1 - normalized_shannon_entropy(weight distribution)
  * outliers = results whose IPs are not in the majority AND weight < 0.2*total
  * reputation EMA of agreement (alpha = 0.05)

Scenarios required by the spec: 3-1 split, 2-2 split, all-different, single.
"""

from __future__ import annotations

import math

import pytest

from chk_a.agents.consensus_agent import ConsensusAgent
from chk_a.agents.resolver_agent import ResolverHealth
from chk_a.models.schemas import CheckResult, ResolverConfig


# -- helpers ---------------------------------------------------------------
def make_resolvers(names, weights=None):
    weights = weights or [1.0] * len(names)
    return [
        ResolverConfig(name=n, address="127.0.0.1:53", weight=w) for n, w in zip(names, weights)
    ]


def make_health(names, success_rate=1.0):
    return {n: ResolverHealth(success_rate=success_rate) for n in names}


def ok(resolver, ips):
    return CheckResult(fqdn="example.com", resolver=resolver, ips=ips, success=True)


def fail(resolver, error="NXDOMAIN"):
    return CheckResult(fqdn="example.com", resolver=resolver, success=False, error=error)


def agent_for(names, weights=None, success_rate=1.0):
    resolvers = make_resolvers(names, weights)
    health = make_health(names, success_rate)
    return ConsensusAgent(resolvers=resolvers, health=health)


# -- entropy helper (mirrors implementation) -------------------------------
def expected_normalized_entropy(weights):
    total = sum(weights)
    if total <= 0.0 or len(weights) <= 1:
        return 0.0
    entropy = 0.0
    for w in weights:
        if w <= 0.0:
            continue
        p = w / total
        entropy -= p * math.log2(p)
    return min(1.0, entropy / math.log2(len(weights)))


# -- tests -----------------------------------------------------------------
def test_single_resolver_full_consensus():
    a = agent_for(["r1"])
    res = a.aggregate("example.com", [ok("r1", ["5.5.5.5"])])
    assert res.majority_ips == ["5.5.5.5"]
    assert res.consensus_score == 1.0  # single value -> entropy 0
    assert res.outliers == []
    assert res.resolver_reputation["r1"] == 1.0


def test_three_one_split_majority_no_outlier_equal_weights():
    # 3-1 split with EQUAL weights: the minority carries 25% (> 20% of total)
    # so per spec it is NOT an outlier (outlier needs weight < 0.2*total).
    a = agent_for(["r1", "r2", "r3", "r4"])
    results = [
        ok("r1", ["1.2.3.4"]),
        ok("r2", ["1.2.3.4"]),
        ok("r3", ["1.2.3.4"]),
        ok("r4", ["9.9.9.9"]),
    ]
    res = a.aggregate("example.com", results)
    assert res.majority_ips == ["1.2.3.4"]
    # IP weights: 1.2.3.4=3.0, 9.9.9.9=1.0, total=4.0
    # entropy([3,1]) normalized = 0.8113 -> score ~0.1887
    expected_score = round(1.0 - expected_normalized_entropy([3.0, 1.0]), 4)
    assert res.consensus_score == pytest.approx(expected_score)
    assert res.outliers == []  # minority weight 1.0 is not < 0.2*4.0 = 0.8
    # r4 disagreed -> reputation decays toward 0 (alpha 0.05)
    assert res.resolver_reputation["r4"] == pytest.approx(1.0 - 0.05)
    assert res.resolver_reputation["r1"] == 1.0


def test_low_weight_disagreeing_resolver_is_outlier():
    # r4 carries very little weight and disagrees -> flagged as outlier.
    # r1,r2,r3 weight 1.0 agree on X; r4 weight 0.1 disagrees on Y.
    # total = 3.1; 0.2*total = 0.62; r4 weight 0.1 < 0.62 -> outlier.
    a = agent_for(["r1", "r2", "r3", "r4"], weights=[1.0, 1.0, 1.0, 0.1])
    results = [
        ok("r1", ["1.2.3.4"]),
        ok("r2", ["1.2.3.4"]),
        ok("r3", ["1.2.3.4"]),
        ok("r4", ["9.9.9.9"]),
    ]
    res = a.aggregate("example.com", results)
    assert res.majority_ips == ["1.2.3.4"]
    assert len(res.outliers) == 1
    assert res.outliers[0].resolver == "r4"


def test_two_two_split_no_majority_no_outlier():
    a = agent_for(["r1", "r2", "r3", "r4"])
    results = [
        ok("r1", ["1.1.1.1"]),
        ok("r2", ["1.1.1.1"]),
        ok("r3", ["2.2.2.2"]),
        ok("r4", ["2.2.2.2"]),
    ]
    res = a.aggregate("example.com", results)
    # each side = 0.5 weight < 0.6 threshold -> no majority
    assert res.majority_ips == []
    # equal split -> max entropy -> score 0
    assert res.consensus_score == pytest.approx(0.0)
    # both sides carry 0.5*total >= 0.2*total -> not outliers
    assert res.outliers == []


def test_all_different_no_majority():
    a = agent_for(["r1", "r2", "r3", "r4"])
    results = [
        ok("r1", ["1.1.1.1"]),
        ok("r2", ["2.2.2.2"]),
        ok("r3", ["3.3.3.3"]),
        ok("r4", ["4.4.4.4"]),
    ]
    res = a.aggregate("example.com", results)
    assert res.majority_ips == []
    assert res.consensus_score == pytest.approx(0.0)
    assert res.outliers == []


def test_weighted_vote_respects_config_weight():
    # r1 has weight 3, others weight 1 -> r1 alone can reach majority
    a = agent_for(["r1", "r2", "r3"], weights=[3.0, 1.0, 1.0])
    results = [
        ok("r1", ["1.1.1.1"]),
        ok("r2", ["2.2.2.2"]),
        ok("r3", ["3.3.3.3"]),
    ]
    res = a.aggregate("example.com", results)
    # r1 weight 3.0 / total 5.0 = 0.6 >= 0.6 -> majority
    assert res.majority_ips == ["1.1.1.1"]


def test_health_lowers_effective_weight():
    # r1 healthy, r2 flaky (success_rate 0.1) -> r2 contributes little weight
    resolvers = make_resolvers(["r1", "r2", "r3"])
    health = {
        "r1": ResolverHealth(success_rate=1.0),
        "r2": ResolverHealth(success_rate=0.1),
        "r3": ResolverHealth(success_rate=1.0),
    }
    a = ConsensusAgent(resolvers=resolvers, health=health)
    results = [
        ok("r1", ["1.1.1.1"]),
        ok("r2", ["9.9.9.9"]),
        ok("r3", ["1.1.1.1"]),
    ]
    res = a.aggregate("example.com", results)
    # r1+r3 weight = 1.0+1.0 = 2.0; r2 weight = 0.1; total 2.1
    # 1.1.1.1 = 2.0/2.1 = 0.952 >= 0.6 -> majority
    assert res.majority_ips == ["1.1.1.1"]


def test_failed_results_excluded_from_vote():
    a = agent_for(["r1", "r2", "r3"])
    results = [
        ok("r1", ["1.1.1.1"]),
        fail("r2"),
        ok("r3", ["1.1.1.1"]),
    ]
    res = a.aggregate("example.com", results)
    assert res.majority_ips == ["1.1.1.1"]
    # r2 failed -> not in reputation agreement
    assert res.resolver_reputation["r2"] == pytest.approx(1.0 - 0.05)


def test_all_failed_yields_empty_consensus():
    a = agent_for(["r1", "r2"])
    results = [fail("r1"), fail("r2")]
    res = a.aggregate("example.com", results)
    assert res.majority_ips == []
    assert res.consensus_score == 0.0
    assert res.outliers == []


def test_min_consensus_threshold_override():
    a = agent_for(["r1", "r2", "r3", "r4"])
    results = [
        ok("r1", ["1.1.1.1"]),
        ok("r2", ["1.1.1.1"]),
        ok("r3", ["2.2.2.2"]),
        ok("r4", ["2.2.2.2"]),
    ]
    # raise threshold to 0.8 -> 2/4 = 0.5 still below -> no majority
    res = a.aggregate("example.com", results, min_consensus=0.8)
    assert res.majority_ips == []
    # lower threshold to 0.4 -> 0.5 >= 0.4 -> majority
    res2 = a.aggregate("example.com", results, min_consensus=0.4)
    assert set(res2.majority_ips) == {"1.1.1.1", "2.2.2.2"}


def test_reputation_ema_accumulates_over_calls():
    a = agent_for(["r1", "r2"])
    # call 1: r2 disagrees
    a.aggregate(
        "example.com",
        [ok("r1", ["1.1.1.1"]), ok("r2", ["9.9.9.9"])],
    )
    rep_after_1 = a.reputation["r2"]
    # call 2: r2 agrees
    a.aggregate(
        "example.com",
        [ok("r1", ["1.1.1.1"]), ok("r2", ["1.1.1.1"])],
    )
    rep_after_2 = a.reputation["r2"]
    # after disagree then agree: 1.0 -> 0.95 -> 0.95*0.95 + 0.05*1 = 0.9525
    assert rep_after_1 == pytest.approx(0.95)
    assert rep_after_2 == pytest.approx(0.9525)


def test_normalized_entropy_helper():
    # single value -> 0
    assert ConsensusAgent._normalized_entropy([1.0]) == 0.0
    # equal split of two -> 1.0
    assert ConsensusAgent._normalized_entropy([1.0, 1.0]) == pytest.approx(1.0)
    # equal split of four -> 1.0
    assert ConsensusAgent._normalized_entropy([1.0, 1.0, 1.0, 1.0]) == pytest.approx(1.0)
    # skewed -> between 0 and 1
    e = ConsensusAgent._normalized_entropy([3.0, 1.0])
    assert 0.0 < e < 1.0
