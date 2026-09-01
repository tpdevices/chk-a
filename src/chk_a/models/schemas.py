"""Pydantic data models (contracts) for the chk-a multi-agent DNS monitor.

These models are the shared vocabulary between all agents:
Resolver -> Consensus -> ML -> Alert.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ResolverConfig(BaseModel):
    """A DNS resolver endpoint used to query A records."""

    name: str
    address: str = Field(  # "IP:port" or DoH URL
        description="Resolver address, e.g. '8.8.8.8:53' or a DoH URL.",
    )
    weight: float = Field(default=1.0, ge=0.0)
    timeout_ms: int = Field(default=2000, ge=100)


class FQDNConfig(BaseModel):
    """An FQDN to monitor."""

    name: str
    expected_ips: list[str] = Field(default_factory=list)  # optional allowlist
    min_consensus: float = Field(default=0.6, ge=0.0, le=1.0)


class CheckResult(BaseModel):
    """Result of a single resolver query for a single FQDN."""

    fqdn: str
    resolver: str
    ips: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None


class ConsensusResult(BaseModel):
    """Weighted majority vote across resolvers for one FQDN."""

    fqdn: str
    majority_ips: list[str] = Field(default_factory=list)
    consensus_score: float = Field(default=0.0, ge=0.0, le=1.0)
    outliers: list[CheckResult] = Field(default_factory=list)
    resolver_reputation: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class AnomalyEvent(BaseModel):
    """A detected anomaly that may trigger an alert."""

    fqdn: str
    type: Literal["baseline_deviation", "consensus_deviation", "new_ip", "nxdomain"]
    severity: Literal["info", "warning", "critical"] = "warning"
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    resolver_snapshots: list[CheckResult] = Field(default_factory=list)
    # NEW: hostname where the check ran, and resolver name that triggered
    hostname: str = ""
    resolver_name: str = ""


class MLConfig(BaseModel):
    """Online-learning hyperparameters."""

    baseline_decay: float = Field(default=0.05, gt=0.0, le=1.0)
    anomaly_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    min_samples_before_alert: int = Field(default=10, ge=1)


class AlertConfig(BaseModel):
    """Telegram alerting configuration."""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    dedup_window_minutes: int = Field(default=30, ge=1)
    rate_limit_per_hour: int = Field(default=20, ge=1)
    alert_log_path: str = ""  # empty = disable JSONL audit log
    # Plain text log (one line per alert: date time hostname resolver ip event)
    alert_text_log_path: str = ""  # empty = disable plain text log
    # Daily image (sent at midnight)
    daily_image_path: str = "img/sleepy.jpg"
    daily_image_chat_id: str = ""  # empty = use telegram_chat_id
    daily_image_caption: str = "🌙 Good night from chk-a! Daily DNS monitor heartbeat."
    # Persistent dedup cache (survives restarts)
    dedup_cache_path: str = ""  # empty = in-memory only


class SchedulerConfig(BaseModel):
    """Cycle scheduler configuration."""

    min_interval_sec: int = Field(default=30, ge=1)
    max_interval_sec: int = Field(default=180, ge=1)
    jitter: bool = True

    @model_validator(mode="after")
    def _check_bounds(self) -> "SchedulerConfig":
        if self.max_interval_sec < self.min_interval_sec:
            raise ValueError("max_interval_sec must be >= min_interval_sec")
        return self


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: str = "/var/log/chk-a/checks.jsonl"
    max_size_mb: int = Field(default=50, ge=1)
    backup_count: int = Field(default=10, ge=0)


__all__ = [
    "ResolverConfig",
    "FQDNConfig",
    "CheckResult",
    "ConsensusResult",
    "AnomalyEvent",
    "MLConfig",
    "AlertConfig",
    "SchedulerConfig",
    "LoggingConfig",
]
