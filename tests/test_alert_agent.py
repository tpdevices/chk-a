"""Tests for the Alert Agent (Loop 4).

Follows the Loop 4 spec in ``md/loop_engineering_prompt.md``:

  * dedup key = (fqdn, type, frozenset(observed_ips)), TTL = dedup_window_minutes
  * token-bucket rate limit (capacity = rate_limit_per_hour, refill 1/3600 per sec)
  * HTML formatting per spec
  * JSONL audit log on successful send
  * network/Telegram failure -> return False (not deduped, can retry)

``TelegramClient.send_message`` is mocked with an AsyncMock so no real network
call is made.
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock

from chk_a.agents.alert_agent import AlertAgent, _format_html
from chk_a.models.schemas import AlertConfig, AnomalyEvent


def _event(
    fqdn: str = "example.com",
    ips: tuple[str, ...] = ("1.2.3.4",),
    type: str = "baseline_deviation",
    severity: str = "warning",
) -> AnomalyEvent:
    return AnomalyEvent(
        fqdn=fqdn,
        type=type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        details={
            "observed_ips": list(ips),
            "baseline_ips": ["9.9.9.9"],
            "consensus_score": 0.95,
            "resolver_count": 4,
            "majority_ips": list(ips),
            "all_results": [
                {"resolver": "google", "ips": list(ips), "latency_ms": 50.0, "timestamp": "2026-08-29T12:00:00", "success": True, "error": None},
                {"resolver": "cloudflare", "ips": list(ips), "latency_ms": 45.0, "timestamp": "2026-08-29T12:00:00", "success": True, "error": None},
                {"resolver": "quad9", "ips": list(ips), "latency_ms": 60.0, "timestamp": "2026-08-29T12:00:00", "success": True, "error": None},
                {"resolver": "fake-resolver", "ips": [], "latency_ms": 500.0, "timestamp": "2026-08-29T12:00:00", "success": False, "error": "timeout"},
            ],
            "outlier_details": [
                {"resolver": "fake-resolver", "ips": [], "error": "timeout"},
            ],
        },
        timestamp=datetime(2026, 8, 29, 12, 0, 0),
    )


def _make_agent(alert_log_path: str | None = None, alert_text_log_path: str | None = None, **cfg: object) -> tuple[AlertAgent, AsyncMock]:
    config = AlertConfig(**cfg)  # type: ignore[arg-type]
    client = AsyncMock()
    client.send_message.return_value = True
    agent = AlertAgent(config, None, client, alert_log_path=alert_log_path, alert_text_log_path=alert_text_log_path)
    return agent, client


async def test_first_alert_sends() -> None:
    agent, client = _make_agent()
    assert await agent.maybe_alert(_event()) is True
    client.send_message.assert_awaited_once()


async def test_dedup_suppresses_second() -> None:
    agent, client = _make_agent()
    ev = _event()
    assert await agent.maybe_alert(ev) is True
    assert await agent.maybe_alert(ev) is False
    assert client.send_message.await_count == 1


async def test_different_ips_not_deduped() -> None:
    agent, client = _make_agent()
    assert await agent.maybe_alert(_event(ips=("1.2.3.4",))) is True
    assert await agent.maybe_alert(_event(ips=("5.6.7.8",))) is True
    assert client.send_message.await_count == 2


async def test_rate_limit_drops_after_capacity() -> None:
    # Distinct IPs so dedup does not interfere; capacity=2 -> 3rd is rate-limited.
    agent, client = _make_agent(rate_limit_per_hour=2)
    assert await agent.maybe_alert(_event(ips=("1.1.1.1",))) is True
    assert await agent.maybe_alert(_event(ips=("2.2.2.2",))) is True
    # Third send within the same instant exceeds capacity -> dropped.
    assert await agent.maybe_alert(_event(ips=("3.3.3.3",))) is False
    assert client.send_message.await_count == 2


async def test_formatting_contains_fields() -> None:
    agent, client = _make_agent()
    await agent.maybe_alert(_event(ips=("1.2.3.4", "5.6.7.8")))
    # send_message is called positionally: (chat_id, text, parse_mode)
    args = client.send_message.call_args.args
    text = args[1]
    assert "example.com" in text
    assert "1.2.3.4" in text
    assert "5.6.7.8" in text
    assert "baseline_deviation" in text
    assert "95.00%" in text  # 0.95 -> 95.00%
    assert "4 checked" in text
    assert args[2] == "HTML"


async def test_network_error_returns_false_and_not_deduped() -> None:
    agent, client = _make_agent()
    client.send_message.return_value = False
    ev = _event()
    assert await agent.maybe_alert(ev) is False
    # Not deduped -> a later successful send still goes through.
    client.send_message.return_value = True
    assert await agent.maybe_alert(ev) is True


async def test_jsonl_log_written(tmp_path) -> None:
    path = tmp_path / "alerts.jsonl"
    text_path = tmp_path / "alerts.log"
    client = AsyncMock()
    client.send_message.return_value = True
    agent = AlertAgent(AlertConfig(), None, client, alert_log_path=str(path), alert_text_log_path=str(text_path))
    await agent.maybe_alert(_event())
    assert path.exists()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"]["fqdn"] == "example.com"
    assert rec["event"]["type"] == "baseline_deviation"


def test_format_html_helper() -> None:
    text = _format_html(_event(ips=("1.2.3.4",)))
    assert "<b>⚠️ DNS Anomaly Detected</b>" in text
    assert "<code>1.2.3.4</code>" in text


# -- Persistent dedup cache tests --------------------------------------------

async def test_persistent_dedup_cache_load_save(tmp_path) -> None:
    """Cache loads on startup and saves after successful alert."""
    cache_path = tmp_path / "dedup_cache.json"
    text_path = tmp_path / "alerts.log"

    # Create first agent and send an alert
    client = AsyncMock()
    client.send_message.return_value = True
    agent1 = AlertAgent(
        AlertConfig(dedup_cache_path=str(cache_path)),
        None,
        client,
        alert_log_path=str(tmp_path / "alerts.jsonl"),
        alert_text_log_path=str(text_path),
    )
    ev = _event(ips=("1.2.3.4",))
    await agent1.maybe_alert(ev)

    # Cache file should exist with the entry
    assert cache_path.exists()
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    # Key format: "fqdn|type|ip1,ip2,..."
    key = "example.com|baseline_deviation|1.2.3.4"
    assert key in data
    assert isinstance(data[key], (int, float))

    # Create second agent (simulating restart) with same cache path
    client2 = AsyncMock()
    client2.send_message.return_value = True
    agent2 = AlertAgent(
        AlertConfig(dedup_cache_path=str(cache_path)),
        None,
        client2,
        alert_log_path=str(tmp_path / "alerts2.jsonl"),
        alert_text_log_path=str(tmp_path / "alerts2.log"),
    )
    # Should have loaded the cache - second alert should be suppressed
    assert await agent2.maybe_alert(ev) is False
    assert client2.send_message.await_count == 0


async def test_persistent_dedup_cache_prunes_expired(tmp_path) -> None:
    """Expired entries are pruned on each maybe_alert call."""
    cache_path = tmp_path / "dedup_cache.json"
    text_path = tmp_path / "alerts.log"

    client = AsyncMock()
    client.send_message.return_value = True
    # Use very short dedup window (1 minute) for testing
    agent = AlertAgent(
        AlertConfig(dedup_cache_path=str(cache_path), dedup_window_minutes=1),
        None,
        client,
        alert_log_path=str(tmp_path / "alerts.jsonl"),
        alert_text_log_path=str(text_path),
    )

    # Send an alert
    ev = _event(ips=("1.2.3.4",))
    await agent.maybe_alert(ev)
    assert cache_path.exists()

    # Manually set timestamp to old (2 minutes ago) to simulate expired entry
    import time
    old_time = time.time() - 120  # 2 minutes ago
    agent._dedup[agent._dedup_key(ev)] = old_time
    agent._save_dedup_cache()

    # Send a different alert (different IPs) - this should trigger pruning
    ev2 = _event(ips=("5.6.7.8",))
    await agent.maybe_alert(ev2)

    # Reload cache and verify expired entry was pruned
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    # Only the new entry should remain
    assert "example.com|baseline_deviation|5.6.7.8" in data
    assert "example.com|baseline_deviation|1.2.3.4" not in data


async def test_persistent_dedup_cache_disabled_when_empty(tmp_path) -> None:
    """No cache file created when dedup_cache_path is empty (default)."""
    text_path = tmp_path / "alerts.log"
    client = AsyncMock()
    client.send_message.return_value = True
    agent = AlertAgent(
        AlertConfig(dedup_cache_path=""),  # empty = in-memory only
        None,
        client,
        alert_log_path=str(tmp_path / "alerts.jsonl"),
        alert_text_log_path=str(text_path),
    )
    await agent.maybe_alert(_event())
    # No cache file should be created (agent.dedup_cache_path is None)
    assert agent.dedup_cache_path is None
