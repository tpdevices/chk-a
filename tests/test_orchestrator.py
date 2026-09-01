"""Integration tests for the Orchestrator (Loop 5).

Agents are mocked so the cycle runs offline and deterministically. We verify
the call sequence (resolve -> consensus -> learn -> score -> alert), anomaly
triggering, outlier triggering, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from chk_a.config.loader import AppConfig
from chk_a.models.schemas import (
    CheckResult,
    ConsensusResult,
    FQDNConfig,
    ResolverConfig,
)
from chk_a.orchestrator import Orchestrator


def _make_config() -> AppConfig:
    return AppConfig(
        fqdns=[FQDNConfig(name="example.com")],
        resolvers=[ResolverConfig(name="r1", address="1.1.1.1:53")],
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
        consensus_score=1.0,
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
    config = AppConfig()  # empty
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
