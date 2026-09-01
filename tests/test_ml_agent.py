"""Tests for the ML / Baseline Agent (Loop 3).

Follows the Loop 3 spec in ``md/loop_engineering_prompt.md``:

  * per-FQDN decayed IP counter (exponential decay, default 0.05)
  * learn(consensus) reinforces majority IPs and persists atomically
  * score(fqdn, observed_ips) = 1 - total-variation overlap with baseline
  * cold start returns 0.0 until min_samples_before_alert reached
  * get_baseline returns normalized probabilities

Scenarios required by the spec: gradual drift, sudden change, new IP, cold start.
"""

from __future__ import annotations

from pathlib import Path

from chk_a.agents.ml_agent import MLAgent
from chk_a.models.schemas import ConsensusResult, MLConfig
from chk_a.storage.baseline_store import BaselineStore


def _consensus(fqdn: str, ips: list[str]) -> ConsensusResult:
    return ConsensusResult(fqdn=fqdn, majority_ips=ips, consensus_score=1.0)


def _make_agent(tmp_path: Path, **ml_kwargs: object) -> MLAgent:
    cfg = MLConfig(**ml_kwargs)  # type: ignore[arg-type]
    store = BaselineStore(tmp_path / "baseline.json")
    return MLAgent(cfg, store)


def test_cold_start_returns_zero(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    for _ in range(5):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    # 5 < min_samples_before_alert (10) -> not enough data to judge
    assert agent.score("example.com", {"1.2.3.4"}) == 0.0


def test_learned_ip_scores_zero(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    assert agent.score("example.com", {"1.2.3.4"}) == 0.0


def test_sudden_change_is_anomalous(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    score = agent.score("example.com", {"9.9.9.9"})
    assert score == 1.0  # no overlap at all


def test_new_ip_partial_anomaly(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    alone = agent.score("example.com", {"1.2.3.4"})
    with_new = agent.score("example.com", {"1.2.3.4", "5.6.7.8"})
    assert alone == 0.0
    assert with_new > alone
    assert with_new < 1.0


def test_gradual_drift_accepts_new_majority(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    for _ in range(15):
        agent.learn(_consensus("example.com", ["9.9.9.9"]))
    score_old = agent.score("example.com", {"1.2.3.4"})
    score_new = agent.score("example.com", {"9.9.9.9"})
    # The new majority is now accepted (below threshold); the drifted-away IP is
    # more anomalous than the accepted one.
    assert score_new < agent.config.anomaly_threshold
    assert score_old > score_new


def test_get_baseline_normalized(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    base = agent.get_baseline("example.com")
    assert base == {"1.2.3.4": 1.0}
    # Unknown FQDN -> empty
    assert agent.get_baseline("other.com") == {}


def test_persistence_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    agent = MLAgent(MLConfig(), BaselineStore(path))
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    # New agent loads the same store from disk.
    agent2 = MLAgent(MLConfig(), BaselineStore(path))
    assert agent2.get_baseline("example.com") == {"1.2.3.4": 1.0}
    assert agent2.score("example.com", {"1.2.3.4"}) == 0.0


def test_baseline_store_atomic_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    store = BaselineStore(path)
    store.set_raw("example.com", {"1.2.3.4": 5.0}, 10)
    store.save()
    assert path.exists()
    reloaded = BaselineStore(path)
    raw = reloaded.get_raw("example.com")
    assert raw is not None
    assert raw["counter"] == {"1.2.3.4": 5.0}
    assert raw["sample_count"] == 10
