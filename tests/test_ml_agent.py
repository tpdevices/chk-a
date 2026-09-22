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

import os
from pathlib import Path
import uuid

from chk_a.agents.ml_agent import MLAgent
from chk_a.models.schemas import ConsensusResult, MLConfig
from chk_a.storage.baseline_store import BaselineStore

# Allow tests to use temporary directories under allowed base dir
# SEC-002 compatibility: must be under CHK_A_BASELINE_DIR (/tmp)
BASELINE_TEST_DIR = "/tmp/chk-a-test"
os.environ["CHK_A_BASELINE_DIR"] = BASELINE_TEST_DIR
Path(BASELINE_TEST_DIR).mkdir(parents=True, exist_ok=True)


def _make_temp_path(suffix: str = "baseline.json") -> Path:
    """Create a temp file path within the allowed test directory."""
    return Path(BASELINE_TEST_DIR) / f"test_{uuid.uuid4().hex[:8]}_{suffix}"


def _consensus(fqdn: str, ips: list[str]) -> ConsensusResult:
    return ConsensusResult(fqdn=fqdn, majority_ips=ips, consensus_score=1.0)


def _make_agent(path: Path, **ml_kwargs: object) -> MLAgent:
    cfg = MLConfig(**ml_kwargs)  # type: ignore[arg-type]
    store = BaselineStore(path)
    return MLAgent(cfg, store)


def test_cold_start_returns_zero() -> None:
    path = _make_temp_path()
    agent = _make_agent(path)
    for _ in range(5):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    # 5 < min_samples_before_alert (10) -> not enough data to judge
    assert agent.score("example.com", {"1.2.3.4"}) == 0.0


def test_learned_ip_scores_zero() -> None:
    path = _make_temp_path()
    agent = _make_agent(path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    assert agent.score("example.com", {"1.2.3.4"}) == 0.0


def test_sudden_change_is_anomalous() -> None:
    path = _make_temp_path()
    agent = _make_agent(path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    score = agent.score("example.com", {"9.9.9.9"})
    assert score == 1.0  # no overlap at all


def test_new_ip_partial_anomaly() -> None:
    path = _make_temp_path()
    agent = _make_agent(path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    alone = agent.score("example.com", {"1.2.3.4"})
    with_new = agent.score("example.com", {"1.2.3.4", "5.6.7.8"})
    assert alone == 0.0
    assert with_new > alone
    assert with_new < 1.0


def test_gradual_drift_accepts_new_majority() -> None:
    path = _make_temp_path()
    agent = _make_agent(path)
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


def test_get_baseline_normalized() -> None:
    path = _make_temp_path()
    agent = _make_agent(path)
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    base = agent.get_baseline("example.com")
    assert base == {"1.2.3.4": 1.0}
    # Unknown FQDN -> empty
    assert agent.get_baseline("other.com") == {}


def test_persistence_across_restart() -> None:
    path = _make_temp_path()
    agent = MLAgent(MLConfig(), BaselineStore(path))
    for _ in range(12):
        agent.learn(_consensus("example.com", ["1.2.3.4"]))
    # New agent loads the same store from disk.
    agent2 = MLAgent(MLConfig(), BaselineStore(path))
    assert agent2.get_baseline("example.com") == {"1.2.3.4": 1.0}
    assert agent2.score("example.com", {"1.2.3.4"}) == 0.0


def test_baseline_store_atomic_roundtrip() -> None:
    path = _make_temp_path()
    store = BaselineStore(path)
    store.set_raw("example.com", {"1.2.3.4": 5.0}, 10)
    store.save()
    assert path.exists()
    reloaded = BaselineStore(path)
    raw = reloaded.get_raw("example.com")
    assert raw is not None
    assert raw["counter"] == {"1.2.3.4": 5.0}
    assert raw["sample_count"] == 10
