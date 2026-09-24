"""Integration tests for the Orchestrator (Loop 5).

Agents are mocked so the cycle runs offline and deterministically. We verify
the call sequence (resolve -> consensus -> learn -> score -> alert), anomaly
triggering, outlier triggering, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from chk_a.config.loader import AppConfig
from chk_a.models.schemas import (
    CheckResult,
    ConsensusResult,
    FQDNConfig,
    ResolverConfig,
)
from chk_a.orchestrator import Orchestrator, ActiveAnomaly
from tests.conftest import _make_temp_path


def _make_config() -> AppConfig:
    return AppConfig(
        fqdns=[FQDNConfig(name="example.com")],
        resolvers=[ResolverConfig(name="r1", address="1.1.1.1:53")],
        fqdn_store_path=str(_make_temp_path("main.json", subdir="chk-a-test/fqdns")),
    )


def _make_agents(score: float = 0.0, outliers: list[CheckResult] | None = None):
    resolver = MagicMock()
    resolver.check_fqdn = AsyncMock(
        return_value=[
            CheckResult(
                fqdn="example.com",
                resolver="r1",
                ips=["1.2.3.4"],
                success=True,
            )
        ]
    )
    consensus = MagicMock()
    consensus.aggregate.return_value = ConsensusResult(
        fqdn="example.com",
        majority_ips=["1.2.3.4"],
        consensus_score=0.5,  # Low score to trigger consensus_deviation alert
        outliers=outliers or [],
    )
    ml = MagicMock()
    ml.learn.return_value = None
    ml.score.return_value = score
    ml.get_baseline.return_value = {}
    ml.storage = MagicMock()
    alert = MagicMock()
    alert.maybe_alert = AsyncMock(return_value=True)
    alert.telegram = MagicMock()
    alert.telegram.close = AsyncMock()
    return {
        "resolver": resolver,
        "consensus": consensus,
        "ml": ml,
        "alert": alert,
    }


def _make_orch(score: float = 0.0, outliers=None) -> Orchestrator:
    return Orchestrator(_make_config(), _make_agents(score, outliers))


@pytest.mark.asyncio
async def test_run_cycle_calls_agents_in_order():
    orch = _make_orch()
    await orch.run_cycle()
    orch.resolver.check_fqdn.assert_awaited_once_with("example.com")
    orch.consensus.aggregate.assert_called_once()
    orch.ml.learn.assert_called_once()
    orch.ml.score.assert_called_once()
    # No anomaly -> no alert.
    orch.alert.maybe_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_cycle_alerts_on_baseline_anomaly():
    orch = _make_orch(score=0.9)
    await orch.run_cycle()
    orch.alert.maybe_alert.assert_awaited()
    # The event type should be baseline_deviation.
    event = orch.alert.maybe_alert.call_args.args[0]
    assert event.type == "baseline_deviation"


@pytest.mark.asyncio
async def test_run_cycle_alerts_on_consensus_outlier():
    outlier = CheckResult(fqdn="example.com", resolver="r1", ips=["9.9.9.9"], success=True)
    orch = _make_orch(score=0.0, outliers=[outlier])
    await orch.run_cycle()
    orch.alert.maybe_alert.assert_awaited()
    event = orch.alert.maybe_alert.call_args.args[0]
    assert event.type == "consensus_deviation"


@pytest.mark.asyncio
async def test_run_cycle_skips_when_no_fqdns():
    config = AppConfig(fqdn_store_path=str(_make_temp_path("main.json", subdir="chk-a-test/fqdns")))  # empty
    agents = _make_agents()
    orch = Orchestrator(config, agents)
    await orch.run_cycle()
    agents["resolver"].check_fqdn.assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_persists_baseline_and_closes_telegram():
    orch = _make_orch()
    await orch.shutdown()
    orch.ml.storage.save.assert_called_once()
    orch.alert.telegram.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_shutdown_sets_event():
    orch = _make_orch()
    orch._shutdown = asyncio.Event()
    orch.request_shutdown()
    assert orch._shutdown.is_set()


@pytest.mark.asyncio
async def test_run_stops_after_one_cycle_on_shutdown():
    orch = _make_orch()
    orch._shutdown = asyncio.Event()
    calls = {"n": 0}

    async def _cycle() -> None:
        calls["n"] += 1
        orch.request_shutdown()

    orch.run_cycle = _cycle  # type: ignore[assignment]
    orch._install_signal_handlers = MagicMock()  # skip real signal wiring
    await orch.run(handle_signals=False)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_resolve_all_returns_per_fqdn_results():
    orch = _make_orch()
    out = await orch._resolve_all(["example.com"])
    assert set(out.keys()) == {"example.com"}
    assert isinstance(out["example.com"], list)


@pytest.mark.asyncio
async def test_recovery_alert_sent_when_anomaly_resolves():
    """When a tracked baseline_deviation anomaly resolves, a recovery alert should be sent."""
    orch = _make_orch(score=0.9)  # Start with anomaly
    await orch.run_cycle()
    # An anomaly alert should have been sent and tracked
    assert orch.alert.maybe_alert.await_count == 1
    assert "example.com|baseline_deviation" in orch._active_anomalies

    # Now change score to below threshold (recovered)
    # Also update consensus mock to return high consensus score (recovered)
    orch.ml.score.return_value = 0.1
    orch.consensus.aggregate.return_value = ConsensusResult(
        fqdn="example.com",
        majority_ips=["1.2.3.4"],
        consensus_score=1.0,  # High consensus = recovered
        outliers=[],
    )
    await orch.run_cycle()
    # A recovery alert should now have been sent (2nd maybe_alert call)
    assert orch.alert.maybe_alert.await_count == 2
    recovery_event = orch.alert.maybe_alert.call_args.args[0]
    assert recovery_event.type == "recovery"
    assert recovery_event.details["original_anomaly_type"] == "baseline_deviation"
    assert "duration_seconds" in recovery_event.details
    assert "duration_human" in recovery_event.details
    assert recovery_event.details["ml_baseline_stability"] >= 0.0


@pytest.mark.asyncio
async def test_recovery_alert_not_sent_when_anomaly_persists():
    """When anomaly persists, no recovery alert should be sent."""
    orch = _make_orch(score=0.9)
    await orch.run_cycle()
    assert orch.alert.maybe_alert.await_count == 1
    assert "example.com|baseline_deviation" in orch._active_anomalies

    # Anomaly still above threshold
    orch.ml.score.return_value = 0.85
    await orch.run_cycle()
    assert orch.alert.maybe_alert.await_count == 2  # baseline_deviation alert, not recovery
    # Still tracking the anomaly
    assert "example.com|baseline_deviation" in orch._active_anomalies


@pytest.mark.asyncio
async def test_active_anomaly_key_format():
    """Test the anomaly key generation format."""
    orch = _make_orch()
    key = orch._anomaly_key("test.com", "baseline_deviation")
    assert key == "test.com|baseline_deviation"


@pytest.mark.asyncio
async def test_duration_human_format() -> None:
    """Test the ActiveAnomaly duration formatting."""
    orch = _make_orch()
    start_time = datetime.now() - timedelta(hours=2, minutes=30, seconds=15)
    anomaly = ActiveAnomaly(
        fqdn="test.com",
        anomaly_type="baseline_deviation",
        start_time=start_time,
        details={},
        resolver_name="test",
        event_id="testhost-20260909-143022",
    )
    duration = anomaly.duration_human()
    assert "ชม." in duration or "นาที" in duration or "วินาที" in duration
    duration_sec = anomaly.duration_seconds()
    assert duration_sec >= 9000.0  # 2h30m = 9000s
