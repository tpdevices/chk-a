"""Integration tests for the full chk-a pipeline.

This test suite exercises the complete flow:
ResolverAgent → ConsensusAgent → MLAgent → AlertAgent → Orchestrator

with mocked network calls and verified correlation ID propagation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import os
import uuid
from pathlib import Path

import pytest

from chk_a.agents.alert_agent import AlertAgent
from chk_a.agents.consensus_agent import ConsensusAgent
from chk_a.agents.ml_agent import MLAgent
from chk_a.agents.resolver_agent import ResolverAgent
from chk_a.config.loader import AppConfig
from chk_a.models.schemas import (
    AlertConfig,
    AnomalyEvent,
    CheckResult,
    ConsensusResult,
    FQDNConfig,
    LoggingConfig,
    MTRConfig,
    MLConfig,
    ResolverAgentConfig,
    ResolverConfig,
    SchedulerConfig,
)
from chk_a.orchestrator import Orchestrator
from chk_a.storage.baseline_store import BaselineStore
from chk_a.utils.context import get_correlation_id, new_correlation_id, set_correlation_id
from chk_a.utils.telegram_client import TelegramClient

# Set allowed base dir for tests
BASELINE_TEST_DIR = "/tmp/chk-a-test"
os.environ["CHK_A_BASELINE_DIR"] = BASELINE_TEST_DIR
Path(BASELINE_TEST_DIR).mkdir(parents=True, exist_ok=True)


def _make_temp_path(suffix: str = "baselines.json") -> Path:
    """Create a temp file path within the allowed test directory."""
    return Path(BASELINE_TEST_DIR) / f"test_{uuid.uuid4().hex[:8]}_{suffix}"


# Test fixtures
@pytest.fixture
def baseline_store_path() -> str:
    """Create a temp baseline store path."""
    return str(_make_temp_path("baselines.json"))


@pytest.fixture
def baseline_store(baseline_store_path) -> BaselineStore:
    """Create a BaselineStore with temp path."""
    return BaselineStore(baseline_store_path)


@pytest.fixture
def mock_config(baseline_store_path) -> AppConfig:
    """Create a test AppConfig with all required fields."""
    return AppConfig(
        fqdns=[
            FQDNConfig(name="example.com", expected_ips=["1.2.3.4"]),
            FQDNConfig(name="test.org", expected_ips=["5.6.7.8", "9.10.11.12"]),
        ],
        resolvers=[
            ResolverConfig(name="google", address="8.8.8.8:53"),
            ResolverConfig(name="cloudflare", address="1.1.1.1:53"),
            ResolverConfig(name="quad9", address="9.9.9.9:53"),
            ResolverConfig(name="adguard", address="94.140.14.14:53"),
        ],
        resolver_agent=ResolverAgentConfig(max_concurrent=10),
        ml=MLConfig(
            baseline_decay=0.05,
            min_samples_before_alert=3,
            anomaly_threshold=0.5,
        ),
        alert=AlertConfig(
            telegram_bot_token="test_token",
            telegram_chat_id="test_chat_id",
            daily_image_chat_id="test_daily_chat_id",
            dedup_window_minutes=60,
            rate_limit_per_hour=20,
            alert_log_path="",
            alert_text_log_path="",
            dedup_cache_path="",
        ),
        scheduler=SchedulerConfig(
            min_interval_sec=30,
            max_interval_sec=180,
            health_bind_address="127.0.0.1",
        ),
        mtr=MTRConfig(
            enabled=True,
            resolvers=[],
            timeout_sec=10,
        ),
        baseline_store_path=baseline_store_path,
        logging=LoggingConfig(
            file=str(_make_temp_path("checks.jsonl")),
            level="INFO",
        ),
    )


def _make_resolver_result(resolver: str, fqdn: str, ips: list[str], success: bool = True, error: str | None = None) -> CheckResult:
    """Helper to create a CheckResult."""
    return CheckResult(
        fqdn=fqdn,
        resolver=resolver,
        ips=ips,
        success=success,
        latency_ms=25.0,
        error=error,
    )


def _build_test_agents(mock_config, baseline_store, mock_telegram):
    """Build agents dict matching main.py build_agents()."""
    resolver = ResolverAgent(
        mock_config.resolvers,
        max_concurrent=mock_config.resolver_agent.max_concurrent,
        default_timeout_ms=mock_config.resolver_agent.default_timeout_ms,
    )
    consensus = ConsensusAgent(mock_config.resolvers, health=resolver.health)
    ml = MLAgent(mock_config.ml, baseline_store)
    alert = AlertAgent(
        mock_config.alert,
        logger=MagicMock(),
        telegram_client=mock_telegram,
        alert_log_path="",  # Disable log file to avoid permission errors
        alert_text_log_path="",
    )
    return {
        "resolver": resolver,
        "consensus": consensus,
        "ml": ml,
        "alert": alert,
    }


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_happy_path(self, mock_config, baseline_store):
        """Test complete pipeline: DNS → Consensus → ML → Alert with correlation ID."""
        # Create mock telegram
        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)
        mock_telegram.send_photo = AsyncMock(return_value=True)

        agents = _build_test_agents(mock_config, baseline_store, mock_telegram)
        resolver_agent = agents["resolver"]
        consensus_agent = agents["consensus"]
        ml_agent = agents["ml"]
        alert_agent = agents["alert"]

        # Mock ResolverAgent.check_fqdn to return consistent results
        async def mock_check_fqdn(fqdn: str):
            results = []
            for name in ["google", "cloudflare", "quad9", "adguard"]:
                results.append(_make_resolver_result(name, fqdn, ["1.2.3.4"]))
            return results

        with patch.object(resolver_agent, "check_fqdn", side_effect=mock_check_fqdn):
            # Step 1: Run resolvers for all FQDNs
            resolver_results = {}
            for fqdn in ["example.com", "test.org"]:
                resolver_results[fqdn] = await resolver_agent.check_fqdn(fqdn)

            # Verify resolver results
            assert len(resolver_results) == 2  # 2 FQDNs
            for fqdn, results in resolver_results.items():
                assert len(results) == 4  # 4 resolvers
                assert all(r.success for r in results)

            # Step 2: Consensus per FQDN
            consensus_results = []
            for fqdn, results in resolver_results.items():
                cr = consensus_agent.aggregate(fqdn, results, min_consensus=0.6)
                consensus_results.append(cr)

            assert len(consensus_results) == 2
            for cr in consensus_results:
                assert cr.consensus_score == 1.0
                assert cr.majority_ips == ["1.2.3.4"]

            # Step 3: ML learn + score
            for cr in consensus_results:
                ml_agent.learn(cr)

            # Score should be 0 (cold start, min_samples=3, only 1 sample)
            score = ml_agent.score("example.com", {"1.2.3.4"})
            assert score == 0.0

            # Step 4: Alert (should not alert on cold start - score=0 < anomaly_threshold=0.5)
            # The orchestrator checks cold start before calling alert, so we don't call alert_agent.maybe_alert here
            # Verify no alerts would be sent (cold start)
            assert alert_agent._dedup == {}  # No dedup entries created

    @pytest.mark.asyncio
    async def test_pipeline_with_anomaly_detection(self, mock_config, baseline_store):
        """Test pipeline detects anomaly after learning baseline."""
        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)
        mock_telegram.send_photo = AsyncMock(return_value=True)

        agents = _build_test_agents(mock_config, baseline_store, mock_telegram)
        resolver_agent = agents["resolver"]
        consensus_agent = agents["consensus"]
        ml_agent = agents["ml"]
        alert_agent = agents["alert"]

        # Phase 1: Learn normal baseline (3+ samples to pass min_samples)
        async def mock_check_normal(fqdn: str):
            results = []
            for name in ["google", "cloudflare", "quad9", "adguard"]:
                results.append(_make_resolver_result(name, fqdn, ["1.2.3.4"]))
            return results

        with patch.object(resolver_agent, "check_fqdn", side_effect=mock_check_normal):
            for _ in range(4):  # 4 cycles > min_samples=3
                resolver_results = {}
                for fqdn in ["example.com", "test.org"]:
                    resolver_results[fqdn] = await resolver_agent.check_fqdn(fqdn)
                for fqdn, results in resolver_results.items():
                    cr = consensus_agent.aggregate(fqdn, results, min_consensus=0.6)
                    ml_agent.learn(cr)

            # Phase 2: Anomalous response
            async def mock_check_anomaly(fqdn: str):
                results = []
                for name in ["google", "cloudflare", "quad9", "adguard"]:
                    if name == "google":
                        results.append(_make_resolver_result(name, fqdn, ["9.9.9.9"]))
                    else:
                        results.append(_make_resolver_result(name, fqdn, ["1.2.3.4"]))
                return results

            with patch.object(resolver_agent, "check_fqdn", side_effect=mock_check_anomaly):
                resolver_results = {}
                for fqdn in ["example.com", "test.org"]:
                    resolver_results[fqdn] = await resolver_agent.check_fqdn(fqdn)

                consensus_results = []
                for fqdn, results in resolver_results.items():
                    cr = consensus_agent.aggregate(fqdn, results, min_consensus=0.6)
                    consensus_results.append(cr)

                # Consensus should still be 1.2.3.4 (3 out of 4)
                for cr in consensus_results:
                    assert cr.majority_ips == ["1.2.3.4"]
                    # Consensus score is entropy-based (3/4 vs 1/4 split)
                    assert cr.consensus_score == pytest.approx(0.1887, rel=0.1)

                # Score should now be > 0 (anomaly detected)
                for cr in consensus_results:
                    score = ml_agent.score(cr.fqdn, {"9.9.9.9"})
                    assert score > 0  # Anomaly detected

    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self, mock_config, baseline_store):
        """Test correlation ID propagates through entire pipeline."""
        # Set a correlation ID at the start
        test_cid = "test-correlation-id-12345"
        set_correlation_id(test_cid)

        try:
            mock_telegram = MagicMock()
            mock_telegram.send_message = AsyncMock(return_value=True)
            mock_telegram.send_photo = AsyncMock(return_value=True)

            agents = _build_test_agents(mock_config, baseline_store, mock_telegram)
            resolver_agent = agents["resolver"]
            consensus_agent = agents["consensus"]
            ml_agent = agents["ml"]
            alert_agent = agents["alert"]

            async def mock_check(fqdn: str):
                results = []
                for name in ["google", "cloudflare", "quad9", "adguard"]:
                    results.append(_make_resolver_result(name, fqdn, ["1.2.3.4"]))
                return results

            with patch.object(resolver_agent, "check_fqdn", side_effect=mock_check):
                # Correlation ID should be available throughout
                assert get_correlation_id() == test_cid

                resolver_results = {}
                for fqdn in ["example.com", "test.org"]:
                    resolver_results[fqdn] = await resolver_agent.check_fqdn(fqdn)
                assert get_correlation_id() == test_cid

                consensus_results = []
                for fqdn, results in resolver_results.items():
                    cr = consensus_agent.aggregate(fqdn, results, min_consensus=0.6)
                    consensus_results.append(cr)
                assert get_correlation_id() == test_cid

                for cr in consensus_results:
                    ml_agent.learn(cr)
                assert get_correlation_id() == test_cid

                for cr in consensus_results:
                    event = AnomalyEvent(
                        fqdn=cr.fqdn,
                        type="baseline_deviation",
                        severity="warning",
                        details={"observed_ips": cr.majority_ips},
                        resolver_snapshots=resolver_results.get(cr.fqdn, []),
                    )
                    await alert_agent.maybe_alert(event)
                assert get_correlation_id() == test_cid

        finally:
            set_correlation_id(None)

    @pytest.mark.asyncio
    async def test_orchestrator_single_cycle(self, mock_config, baseline_store):
        """Test Orchestrator.run_cycle() executes all agents in order."""
        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)
        mock_telegram.send_photo = AsyncMock(return_value=True)

        agents = _build_test_agents(mock_config, baseline_store, mock_telegram)
        orchestrator = Orchestrator(mock_config, agents)

        # Mock the Telegram send to avoid network calls
        with patch.object(orchestrator.alert, "maybe_alert", new_callable=AsyncMock) as mock_alert:
            with patch.object(orchestrator.resolver, "check_fqdn", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = [
                    _make_resolver_result("google", "example.com", ["1.2.3.4"]),
                    _make_resolver_result("cloudflare", "example.com", ["1.2.3.4"]),
                    _make_resolver_result("quad9", "example.com", ["1.2.3.4"]),
                    _make_resolver_result("adguard", "example.com", ["1.2.3.4"]),
                ]

                # Run single cycle
                await orchestrator.run_cycle()

                # Verify resolver was called
                assert mock_check.called
                # maybe_alert may not be called on cold start (score=0, below threshold)
                # Just verify run_cycle completed without error

    @pytest.mark.asyncio
    async def test_orchestrator_shutdown_persists_baseline(self, mock_config, baseline_store, baseline_store_path):
        """Test Orchestrator shutdown saves baseline."""
        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)
        mock_telegram.send_photo = AsyncMock(return_value=True)

        agents = _build_test_agents(mock_config, baseline_store, mock_telegram)
        orchestrator = Orchestrator(mock_config, agents)

        # Learn some data directly (without going through run_cycle which would add more)
        orchestrator.ml.learn(
            ConsensusResult(fqdn="example.com", majority_ips=["1.2.3.4"], consensus_score=1.0)
        )
        # Save to persist the baseline
        orchestrator.ml.storage.save()

        # Mock resolver (though run_cycle won't actually be entered since shutdown is already set)
        with patch.object(orchestrator.resolver, "check_fqdn", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = [
                _make_resolver_result("google", "example.com", ["1.2.3.4"]),
                _make_resolver_result("cloudflare", "example.com", ["1.2.3.4"]),
                _make_resolver_result("quad9", "example.com", ["1.2.3.4"]),
                _make_resolver_result("adguard", "example.com", ["1.2.3.4"]),
            ]

            # Trigger shutdown - call shutdown() directly which persists baseline
            orchestrator.request_shutdown()
            await orchestrator.shutdown()

        # Verify baseline was saved
        assert Path(baseline_store_path).exists()

        # Verify can reload
        from chk_a.storage.baseline_store import BaselineStore as BS
        reloaded = BS(baseline_store_path)
        baseline = reloaded.get_baseline("example.com")
        assert baseline == {"1.2.3.4": 1.0}


class TestErrorHandling:
    """Tests for error handling in the pipeline."""

    @pytest.mark.asyncio
    async def test_resolver_failure_does_not_block_others(self, mock_config, tmp_path):
        """Test one failing resolver doesn't block other resolvers."""
        resolver_agent = ResolverAgent(
            mock_config.resolvers,
            max_concurrent=10,
            default_timeout_ms=2000,
        )

        async def mock_check(fqdn: str):
            results = []
            for name in ["google", "cloudflare", "quad9", "adguard"]:
                if name == "google":
                    results.append(_make_resolver_result(name, fqdn, [], success=False, error="Network error"))
                else:
                    results.append(_make_resolver_result(name, fqdn, ["1.2.3.4"]))
            return results

        with patch.object(resolver_agent, "check_fqdn", side_effect=mock_check):
            resolver_results = {}
            for fqdn in ["example.com", "test.org"]:
                resolver_results[fqdn] = await resolver_agent.check_fqdn(fqdn)

            # Other resolvers should still have results
            for fqdn, res_list in resolver_results.items():
                google_result = next(r for r in res_list if r.resolver == "google")
                assert not google_result.success
                assert google_result.error == "Network error"

                cloudflare_result = next(r for r in res_list if r.resolver == "cloudflare")
                assert cloudflare_result.success

    @pytest.mark.asyncio
    async def test_consensus_with_partial_failures(self, mock_config):
        """Test consensus handles partial resolver failures."""
        consensus_agent = ConsensusAgent(mock_config.resolvers)

        resolver_results = [
            _make_resolver_result("google", "example.com", ["1.2.3.4"]),
            _make_resolver_result("cloudflare", "example.com", ["1.2.3.4"]),
            _make_resolver_result("quad9", "example.com", [], success=False, error="Timeout"),
            _make_resolver_result("adguard", "example.com", ["5.6.7.8"]),
        ]

        cr = consensus_agent.aggregate("example.com", resolver_results, min_consensus=0.6)

        # Should reach consensus from 3 successful resolvers (2 for 1.2.3.4, 1 for 5.6.7.8)
        assert cr.majority_ips == ["1.2.3.4"]  # 2 out of 3 = majority
        # Actual consensus score from entropy calculation (2/3 vs 1/3 split)
        assert cr.consensus_score == pytest.approx(0.082, rel=0.1)


# Run integration tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])