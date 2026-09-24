"""Pydantic data models (contracts) for the chk-a multi-agent DNS monitor.

These models are the shared vocabulary between all agents:
Resolver -> Consensus -> ML -> Alert.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator, SecretStr


class LogPermissionsConfig(BaseModel):
    """Shared log file and directory permissions configuration."""
    
    # File permissions (octal, e.g., 0o640 = rw-r-----)
    file_mode: int = Field(default=0o640, ge=0o000, le=0o777, description="Log file permissions (octal)")
    # Directory permissions
    dir_mode: int = Field(default=0o750, ge=0o000, le=0o777, description="Log directory permissions (octal)")


class ResolverConfig(BaseModel):
    """A DNS resolver endpoint used to query A records."""

    name: str
    address: str = Field(  # "IP:port" or DoH URL or DoT URL
        description="Resolver address, e.g. '8.8.8.8:53' or a DoH/DoT URL.",
    )
    weight: float = Field(default=1.0, ge=0.0)
    timeout_ms: int = Field(default=2000, ge=100)

    @field_validator("address", mode="after")
    @classmethod
    def _validate_address(cls, v: str) -> str:
        """Validate resolver address is either IP:port or a valid DoH/DoT URL."""
        import ipaddress
        from urllib.parse import urlparse
        
        v = v.strip()
        if not v:
            raise ValueError("Resolver address cannot be empty")
        
        # Check if it's a DoH URL (starts with http:// or https://)
        if v.startswith(("http://", "https://")):
            parsed = urlparse(v)
            if not parsed.netloc:
                raise ValueError(f"Invalid DoH URL: {v}")
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"DoH URL must use http or https scheme: {v}")
            return v
        
        # Check if it's a DoT URL (starts with tls://)
        if v.startswith("tls://"):
            parsed = urlparse(v)
            if not parsed.netloc:
                raise ValueError(f"Invalid DoT URL: {v}")
            if parsed.scheme != "tls":
                raise ValueError(f"DoT URL must use tls scheme: {v}")
            # Validate host:port format in netloc
            if ":" not in parsed.netloc:
                raise ValueError(f"DoT URL must include port (e.g., tls://host:853): {v}")
            host, port_str = parsed.netloc.rsplit(":", 1)
            try:
                port = int(port_str)
                if not (1 <= port <= 65535):
                    raise ValueError
            except ValueError:
                raise ValueError(f"Invalid port in DoT URL: {v}")
            # Validate host is a valid IP address or hostname
            try:
                ipaddress.ip_address(host)
                return v
            except ValueError:
                if not cls._is_valid_hostname(host):
                    raise ValueError(f"Invalid host in DoT URL: {host}")
                return v
        
        # Otherwise, expect IP:port format
        if ":" not in v:
            raise ValueError(f"Resolver address must be 'IP:port' or DoH/DoT URL, got: {v}")
        
        host, port_str = v.rsplit(":", 1)
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            raise ValueError(f"Invalid port in resolver address: {v}")
        
        # Validate host is a valid IP address or hostname
        try:
            ipaddress.ip_address(host)
            return v
        except ValueError:
            # Not an IP, validate as hostname
            if not cls._is_valid_hostname(host):
                raise ValueError(f"Invalid host in resolver address: {host}")
            return v
    
    @staticmethod
    def _is_valid_hostname(hostname: str) -> bool:
        """Validate hostname format per RFC 1123."""
        if len(hostname) > 253:
            return False
        if hostname.endswith("."):
            hostname = hostname[:-1]
        labels = hostname.split(".")
        for label in labels:
            if not label or len(label) > 63:
                return False
            if not all(c.isalnum() or c == "-" for c in label):
                return False
            if label.startswith("-") or label.endswith("-"):
                return False
        return True


class FQDNConfig(BaseModel):
    """An FQDN to monitor."""

    name: str
    expected_ips: list[str] = Field(default_factory=list)  # optional allowlist
    min_consensus: float = Field(default=0.6, ge=0.0, le=1.0)
    # Per-FQDN custom alert rules (optional, overrides global config)
    alert_rules: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", mode="after")
    @classmethod
    def _validate_fqdn_name(cls, v: str) -> str:
        """Validate FQDN name format."""
        v = v.strip().rstrip(".")
        if not v:
            raise ValueError("FQDN name cannot be empty")
        if len(v) > 253:
            raise ValueError(f"FQDN name too long (max 253 chars): {v}")
        
        # Validate each label
        labels = v.split(".")
        for label in labels:
            if not label:
                raise ValueError(f"Empty label in FQDN: {v}")
            if len(label) > 63:
                raise ValueError(f"Label too long (max 63 chars): {label}")
            if not all(c.isalnum() or c == "-" for c in label):
                raise ValueError(f"Invalid characters in label: {label}")
            if label.startswith("-") or label.endswith("-"):
                raise ValueError(f"Label cannot start/end with hyphen: {label}")
        
        return v
    
    @field_validator("expected_ips", mode="after")
    @classmethod
    def _validate_expected_ips(cls, v: list[str]) -> list[str]:
        """Validate each expected IP is a valid IPv4 or IPv6 address."""
        import ipaddress
        for ip_str in v:
            ip_str = ip_str.strip()
            if not ip_str:
                raise ValueError("Expected IP cannot be empty string")
            try:
                ipaddress.ip_address(ip_str)
            except ValueError:
                raise ValueError(f"Invalid IP address in expected_ips: {ip_str}")
        return v


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
    type: Literal["baseline_deviation", "consensus_deviation", "new_ip", "nxdomain", "ip_change", "recovery", "hourly_reminder"]
    severity: Literal["info", "warning", "critical"] = "warning"
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    resolver_snapshots: list[CheckResult] = Field(default_factory=list)
    # NEW: hostname where the check ran, and resolver name that triggered
    hostname: str = ""
    resolver_name: str = ""
    # Event ID for tracking anomaly lifecycle
    event_id: str = ""


class MLConfig(BaseModel):
    """Online-learning hyperparameters."""

    baseline_decay: float = Field(default=0.05, gt=0.0, le=1.0)
    anomaly_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    min_samples_before_alert: int = Field(default=10, ge=1)


class AlertConfig(LogPermissionsConfig):
    """Telegram alerting configuration."""

    telegram_bot_token: SecretStr = Field(default=SecretStr(""))
    telegram_chat_id: SecretStr = Field(default=SecretStr(""))
    dedup_window_minutes: int = Field(default=30, ge=1)
    rate_limit_per_hour: int = Field(default=20, ge=1)
    alert_log_path: str = ""  # empty = disable JSONL audit log
    # Plain text log (one line per alert: date time hostname resolver ip event)
    alert_text_log_path: str = ""  # empty = disable plain text log
    # Log rotation for alert logs
    alert_log_max_size_mb: int = Field(default=50, ge=1, le=1000, description="Max size per alert log file (MB)")
    alert_log_backup_count: int = Field(default=10, ge=0, le=100, description="Number of rotated alert log files to keep")
    # Daily image (sent at midnight)
    daily_image_path: str = "img/sleepy.jpg"
    daily_image_chat_id: SecretStr = Field(default=SecretStr(""))  # empty = use telegram_chat_id
    daily_image_caption: str = "🌙 Good night from chk-a! Daily DNS monitor heartbeat."
    # Persistent dedup cache (survives restarts)
    dedup_cache_path: str = ""  # empty = in-memory only
    # Max dedup cache size (prevents unbounded memory growth)
    dedup_max_size: int = Field(default=10000, ge=100, le=1000000)
    # Baseline encryption at rest (SEC-015)
    baseline_encryption_enabled: bool = Field(default=False, description="Enable baseline file encryption with age")
    baseline_age_public_key: str = Field(default="", description="age public key for encryption (age1...)")
    baseline_age_private_key_env: str = Field(default="CHK_A_BASELINE_AGE_KEY", description="Env var name holding age private key for decryption")

    @field_validator("alert_log_path", "alert_text_log_path", "daily_image_path", "dedup_cache_path", mode="after")
    @classmethod
    def _validate_alert_paths(cls, v: str) -> str:
        if v:
            import os
            from pathlib import Path
            if ".." in v.split(os.sep) or ".." in Path(v).parts:
                raise ValueError("Path traversal not allowed")
            normalized = os.path.normpath(v)
            if ".." in Path(normalized).parts:
                raise ValueError("Path traversal not allowed")
            return normalized
        return v

    @field_validator("baseline_age_public_key", mode="after")
    @classmethod
    def _validate_age_public_key(cls, v: str) -> str:
        if v and not v.startswith("age1"):
            raise ValueError("baseline_age_public_key must be an age public key starting with 'age1'")
        return v


class ResolverAgentConfig(BaseModel):
    """ResolverAgent concurrency and timeout tuning."""

    max_concurrent: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Max concurrent DNS queries per FQDN (None = auto-tune from resolver count)",
    )

    @field_validator("max_concurrent", mode="after")
    @classmethod
    def _validate_max_concurrent(cls, v: int | None) -> int | None:
        """SEC-012: Enforce hard ceiling cap on resolver concurrency."""
        if v is not None and v < 1:
            raise ValueError("max_concurrent must be >= 1 when set")
        if v is not None and v > 100:
            raise ValueError("max_concurrent must be <= 100 (hard ceiling)")
        return v
    default_timeout_ms: int = Field(
        default=2000,
        ge=100,
        le=30000,
        description="Default timeout for resolvers without explicit timeout_ms",
    )


class SchedulerConfig(BaseModel):
    """Cycle scheduler configuration."""

    min_interval_sec: int = Field(default=30, ge=1)
    max_interval_sec: int = Field(default=180, ge=1)
    jitter: bool = True
    health_port: int = Field(default=0, ge=0, le=65535, description="Port for /healthz endpoint (0=disabled, default: 0)")
    health_bind_address: str = Field(default="127.0.0.1", description="Bind address for /healthz endpoint (default: 127.0.0.1)")

    @model_validator(mode="after")
    def _check_bounds(self) -> "SchedulerConfig":
        if self.max_interval_sec < self.min_interval_sec:
            raise ValueError("max_interval_sec must be >= min_interval_sec")
        return self

    @field_validator("health_bind_address", mode="after")
    @classmethod
    def _validate_health_bind_address(cls, v: str) -> str:
        """Validate health bind address is a loopback address only (security hardening)."""
        import ipaddress
        
        # Allow explicit loopback addresses
        allowed = {"127.0.0.1", "::1", "localhost"}
        if v in allowed:
            return v
        
        # Try to parse as IP address and check if loopback
        try:
            ip = ipaddress.ip_address(v)
            if ip.is_loopback:
                return v
        except ValueError:
            pass
        
        # Not a loopback address - reject
        raise ValueError(
            f"health_bind_address must be a loopback address (127.0.0.1, ::1, or localhost), got: {v}"
        )


class LoggingConfig(LogPermissionsConfig):
    """Logging configuration."""

    level: str = "INFO"
    file: str = "/var/log/chk-a/checks.jsonl"
    max_size_mb: int = Field(default=50, ge=1)
    backup_count: int = Field(default=10, ge=0)


class MTRConfig(BaseModel):
    """MTR configuration for continuous network path monitoring with statistical aggregation."""

    enabled: bool = Field(default=False, description="Enable periodic MTR checks")
    interval_sec: int = Field(
        default=3600, ge=60, description="Interval between MTR runs (seconds)"
    )
    max_hops: int = Field(default=30, ge=1, le=64, description="Maximum TTL/hops")
    count: int = Field(default=10, ge=1, le=100, description="Number of pings per hop (MTR -c)")
    interval_ms: int = Field(
        default=1000,
        ge=100,
        le=60000,
        description="Interval between pings in milliseconds (MTR -i)",
    )
    timeout_sec: int = Field(
        default=10, ge=1, le=60, description="Timeout per ping in seconds (MTR -W)"
    )
    mode: Literal["icmp", "tcp", "udp"] = Field(
        default="icmp", description="MTR probe mode: icmp (default), tcp, or udp"
    )
    port: int | None = Field(
        default=None, ge=1, le=65535, description="Destination port for TCP/UDP mode (required for tcp/udp)"
    )
    resolvers: list[str] = Field(
        default_factory=list, description="Resolver names to trace (empty = all)"
    )
    log_path: str = Field(
        default="/var/log/chk-a/mtr.jsonl",
        description="Path to store MTR results in JSONL format",
    )
    # SEC-012: Hard concurrency ceiling for MTR runs
    max_concurrent: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum concurrent MTR runs (hard ceiling 10)",
    )

    @field_validator("port", mode="after")
    @classmethod
    def _validate_port_for_mode(cls, v: int | None, info) -> int | None:
        mode = info.data.get("mode") if hasattr(info, "data") else None
        if mode in ("tcp", "udp") and v is None:
            raise ValueError(f"port is required when mode is {mode}")
        if mode == "icmp" and v is not None:
            raise ValueError("port must be None when mode is icmp")
        return v

    @field_validator("log_path", mode="after")
    @classmethod
    def _validate_log_path(cls, v: str) -> str:
        if v:
            import os
            from pathlib import Path
            if ".." in v.split(os.sep) or ".." in Path(v).parts:
                raise ValueError("Path traversal not allowed in mtr.log_path")
            normalized = os.path.normpath(v)
            if ".." in Path(normalized).parts:
                raise ValueError("Path traversal not allowed in mtr.log_path")
            return normalized
        return v


class ReportingConfig(BaseModel):
    """Monthly and daily reporting configuration."""

    # Monthly report settings
    enabled: bool = Field(default=True, description="Enable monthly report generation")
    schedule_day: int = Field(
        default=1, ge=1, le=28, description="Day of month to generate report (1-28)"
    )
    schedule_hour: int = Field(default=6, ge=0, le=23, description="Hour to generate report (0-23)")
    schedule_minute: int = Field(
        default=0, ge=0, le=59, description="Minute to generate report (0-59)"
    )
    output_dir: str = Field(default="/var/lib/chk-a/reports", description="Directory to save report files")
    filename_format: str = Field(
        default="monthly-report-{timestamp}.{ext}",
        description="Filename format with {timestamp} and {ext} placeholders",
    )
    # Email configuration
    email_enabled: bool = Field(default=False, description="Enable email delivery")
    smtp_host: str = Field(default="", description="SMTP server host")
    smtp_port: int = Field(default=587, ge=1, le=65535, description="SMTP server port (587=STARTTLS, 465=implicit TLS)")
    smtp_username: str = Field(default="", description="SMTP username")
    smtp_password: SecretStr = Field(default=SecretStr(""), description="SMTP password")
    email_from: str = Field(default="", description="Sender email address")
    email_to: list[str] = Field(default_factory=list, description="Recipient email addresses")

    @model_validator(mode="after")
    def _validate_email_tls(self) -> "ReportingConfig":
        if self.email_enabled:
            if not self.smtp_host:
                raise ValueError("smtp_host is required when email_enabled is true")
            if self.smtp_port not in (465, 587):
                raise ValueError("smtp_port must be 465 (implicit TLS) or 587 (STARTTLS) when email_enabled is true")
        return self

    # Telegram configuration
    telegram_enabled: bool = Field(default=True, description="Enable Telegram summary delivery")
    telegram_chat_id: str = Field(
        default="", description="Telegram chat ID for summary (empty = use alert chat_id)"
    )
    # Report content
    include_graphs: bool = Field(default=True, description="Include graphs in reports")
    include_ml_insights: bool = Field(default=True, description="Include ML insights in reports")
    lookback_days: int = Field(default=30, ge=1, le=365, description="Days of history to analyze")

    # Daily report settings (NEW)
    daily_report_enabled: bool = Field(
        default=True, description="Enable daily report generation at 6:00 AM"
    )
    daily_report_hour: int = Field(
        default=6, ge=0, le=23, description="Hour for daily report (0-23)"
    )
    daily_report_minute: int = Field(
        default=0, ge=0, le=59, description="Minute for daily report (0-59)"
    )
    daily_report_telegram_enabled: bool = Field(
        default=True, description="Enable Telegram for daily report"
    )
    daily_report_telegram_chat_id: str = Field(
        default="", description="Telegram chat ID for daily report (empty = use alert chat_id)"
    )
    daily_report_lookback_days: int = Field(
        default=1, ge=1, le=7, description="Days of history for daily report (default 1 = yesterday)"
    )


__all__ = [
    "ResolverConfig",
    "FQDNConfig",
    "CheckResult",
    "ConsensusResult",
    "AnomalyEvent",
    "MLConfig",
    "AlertConfig",
    "ResolverAgentConfig",
    "SchedulerConfig",
    "LoggingConfig",
    "MTRConfig",
    "ReportingConfig",
]
