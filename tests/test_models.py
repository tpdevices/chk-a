"""Unit tests for chk-a Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from chk_a.models.schemas import (
    AlertConfig,
    AnomalyEvent,
    CheckResult,
    ConsensusResult,
    FQDNConfig,
    LoggingConfig,
    MLConfig,
    ResolverConfig,
    SchedulerConfig,
)


def test_resolver_config_defaults():
    r = ResolverConfig(name="google", address="8.8.8.8:53")
    assert r.weight == 1.0
    assert r.timeout_ms == 2000


def test_resolver_config_bounds():
    with pytest.raises(ValidationError):
        ResolverConfig(name="x", address="1.2.3.4:53", weight=-1.0)
    with pytest.raises(ValidationError):
        ResolverConfig(name="x", address="1.2.3.4:53", timeout_ms=50)


def test_fqdn_config_defaults_and_bounds():
    f = FQDNConfig(name="example.com")
    assert f.expected_ips == []
    assert f.min_consensus == 0.6
    with pytest.raises(ValidationError):
        FQDNConfig(name="x", min_consensus=1.5)


def test_check_result_defaults():
    c = CheckResult(fqdn="example.com", resolver="google")
    assert c.ips == []
    assert c.success is True
    assert isinstance(c.timestamp, datetime)


def test_consensus_result_bounds():
    with pytest.raises(ValidationError):
        ConsensusResult(fqdn="x", consensus_score=1.5)


def test_anomaly_event_literal_types():
    e = AnomalyEvent(fqdn="x", type="new_ip", severity="critical")
    assert e.type == "new_ip"
    assert e.severity == "critical"
    with pytest.raises(ValidationError):
        AnomalyEvent(fqdn="x", type="bogus")
    with pytest.raises(ValidationError):
        AnomalyEvent(fqdn="x", type="new_ip", severity="bogus")


def test_ml_config_bounds():
    with pytest.raises(ValidationError):
        MLConfig(baseline_decay=0.0)
    with pytest.raises(ValidationError):
        MLConfig(anomaly_threshold=2.0)
    with pytest.raises(ValidationError):
        MLConfig(min_samples_before_alert=0)


def test_alert_config_defaults():
    a = AlertConfig()
    assert a.dedup_window_minutes == 30
    assert a.rate_limit_per_hour == 20


def test_scheduler_config_bounds_and_validator():
    s = SchedulerConfig(min_interval_sec=30, max_interval_sec=180)
    assert s.jitter is True
    with pytest.raises(ValidationError):
        SchedulerConfig(min_interval_sec=200, max_interval_sec=180)


def test_logging_config_defaults():
    l = LoggingConfig()
    assert l.level == "INFO"
    assert l.max_size_mb == 50
    assert l.backup_count == 10


def test_consensus_reputation_roundtrip():
    cr = ConsensusResult(
        fqdn="x",
        majority_ips=["1.2.3.4"],
        consensus_score=0.9,
        resolver_reputation={"google": 0.95},
    )
    assert cr.resolver_reputation["google"] == 0.95
