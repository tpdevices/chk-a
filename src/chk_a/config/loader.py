"""Configuration loader with YAML file + ${ENV} substitution.

Loads ``config/settings.yaml`` (override with ``CHK_A_CONFIG`` env var) and
substitutes ``${VAR}`` references from the process environment before validating
the result against :class:`AppConfig`.

Security: Validates critical fields and masks secrets in logs.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, SecretStr

from ..models.schemas import (
    AlertConfig,
    FQDNConfig,
    LoggingConfig,
    MLConfig,
    MTRConfig,
    ResolverAgentConfig,
    ResolverConfig,
    SchedulerConfig,
    ReportingConfig,
)

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Validation constants
_TELEGRAM_TOKEN_PATTERN = re.compile(r"^\d{8,10}:[A-Za-z0-9_-]{35}$")


def _mask_token(token: str) -> str:
    """Mask token for logging (first 4, last 4)."""
    if not token or len(token) < 8:
        return "***"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def _load_env_file(path: str = "/etc/chk-a/env") -> dict[str, str]:
    """Load environment variables from a file into a dict.
    
    Does NOT pollute os.environ - returns parsed dict for safe substitution.
    """
    env_dict: dict[str, str] = {}
    env_path = Path(path)
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_dict[key.strip()] = value.strip()
        except Exception:
            pass
    return env_dict


class AppConfig(BaseModel):
    """Top-level application configuration."""

    fqdns: list[FQDNConfig] = Field(default_factory=list)
    resolvers: list[ResolverConfig] = Field(default_factory=list)
    resolver_agent: ResolverAgentConfig = Field(default_factory=ResolverAgentConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    alert: AlertConfig = Field(default_factory=AlertConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    mtr: MTRConfig = Field(default_factory=MTRConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    baseline_store_path: str = Field(default="./data/baselines.json")
    hostname: str = Field(default_factory=lambda: __import__("socket").gethostname())

    @field_validator("fqdns", mode="after")
    @classmethod
    def _validate_fqdns(cls, v: list[FQDNConfig]) -> list[FQDNConfig]:
        # FQDN validation now done in FQDNConfig model validators
        return v

    @field_validator("resolvers", mode="after")
    @classmethod
    def _validate_resolvers(cls, v: list[ResolverConfig]) -> list[ResolverConfig]:
        # Resolver address validation now done in ResolverConfig model validator
        names = set()
        for r in v:
            if r.name in names:
                raise ValueError(f"Duplicate resolver name: {r.name}")
            names.add(r.name)
        return v

    @field_validator("alert", mode="after")
    @classmethod
    def _validate_alert(cls, v: AlertConfig) -> AlertConfig:
        token = v.telegram_bot_token.get_secret_value() if v.telegram_bot_token else ""
        if token and not _TELEGRAM_TOKEN_PATTERN.match(token):
            # Only warn in logs, don't fail validation (token might be from env var not yet substituted)
            import logging
            logger = logging.getLogger("chk_a.config")
            logger.warning("Telegram bot token format looks invalid (expected NNNNNNNN:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA)")
        return v

    @field_validator("baseline_store_path", mode="after")
    @classmethod
    def _validate_baseline_path(cls, v: str) -> str:
        # Prevent path traversal - check BEFORE normpath (normpath resolves .. away)
        import os
        if ".." in v.split(os.sep) or ".." in Path(v).parts:
            raise ValueError("Path traversal not allowed in baseline_store_path")
        normalized = os.path.normpath(v)
        if ".." in Path(normalized).parts:
            raise ValueError("Path traversal not allowed in baseline_store_path")
        return normalized

    @field_validator("alert", mode="after")
    @classmethod
    def _validate_alert_paths(cls, v: AlertConfig) -> AlertConfig:
        for field_name in ("alert_log_path", "alert_text_log_path", "daily_image_path", "dedup_cache_path"):
            path_val = getattr(v, field_name, "")
            if path_val:
                import os
                from pathlib import Path
                if ".." in path_val.split(os.sep) or ".." in Path(path_val).parts:
                    raise ValueError(f"Path traversal not allowed in alert.{field_name}")
                normalized = os.path.normpath(path_val)
                if ".." in Path(normalized).parts:
                    raise ValueError(f"Path traversal not allowed in alert.{field_name}")
                setattr(v, field_name, normalized)
        return v

    @field_validator("mtr", mode="after")
    @classmethod
    def _validate_mtr_resolvers_subset(cls, v: MTRConfig, info) -> MTRConfig:
        """Validate that mtr.resolvers is a subset of resolvers names."""
        # Get resolvers from the config being validated
        if hasattr(info, "data") and "resolvers" in info.data:
            resolver_names = {r.name for r in info.data["resolvers"]}
            if v.resolvers:
                missing = set(v.resolvers) - resolver_names
                if missing:
                    raise ValueError(
                        f"MTR resolvers contains names not in resolvers list: {sorted(missing)}. "
                        f"Available resolvers: {sorted(resolver_names)}"
                    )
        return v

    @field_validator("alert", mode="before")
    @classmethod
    def _validate_alert_paths_dict(cls, v: dict | AlertConfig) -> dict | AlertConfig:
        if isinstance(v, dict):
            for field_name in ("alert_log_path", "alert_text_log_path", "daily_image_path", "dedup_cache_path"):
                path_val = v.get(field_name, "")
                if path_val:
                    import os
                    from pathlib import Path
                    if ".." in path_val.split(os.sep) or ".." in Path(path_val).parts:
                        raise ValueError(f"Path traversal not allowed in alert.{field_name}")
                    normalized = os.path.normpath(path_val)
                    if ".." in Path(normalized).parts:
                        raise ValueError(f"Path traversal not allowed in alert.{field_name}")
        return v

    @field_validator("mtr", mode="after")
    @classmethod
    def _validate_mtr_paths(cls, v: MTRConfig) -> MTRConfig:
        if v.log_path:
            import os
            from pathlib import Path
            if ".." in v.log_path.split(os.sep) or ".." in Path(v.log_path).parts:
                raise ValueError("Path traversal not allowed in mtr.log_path")
            normalized = os.path.normpath(v.log_path)
            if ".." in Path(normalized).parts:
                raise ValueError("Path traversal not allowed in mtr.log_path")
            v.log_path = normalized
        # Validate port requirement per mode
        if v.mode in ("tcp", "udp") and v.port is None:
            raise ValueError(f"port is required when mode is {v.mode}")
        if v.mode == "icmp" and v.port is not None:
            raise ValueError("port must be None when mode is icmp")
        return v

    @field_validator("mtr", mode="before")
    @classmethod
    def _validate_mtr_port_mode(cls, v: dict | MTRConfig) -> dict | MTRConfig:
        if isinstance(v, dict):
            mode = v.get("mode", "icmp")
            port = v.get("port")
            if mode in ("tcp", "udp") and port is None:
                raise ValueError(f"port is required when mode is {mode}")
            if mode == "icmp" and port is not None:
                raise ValueError("port must be None when mode is icmp")
        return v

    @field_validator("logging", mode="after")
    @classmethod
    def _validate_logging_paths(cls, v: LoggingConfig) -> LoggingConfig:
        if v.file:
            import os
            from pathlib import Path
            # Prevent path traversal - check BEFORE normpath (normpath resolves .. away)
            if ".." in v.file.split(os.sep) or ".." in Path(v.file).parts:
                raise ValueError("Path traversal not allowed in logging.file")
            normalized = os.path.normpath(v.file)
            if ".." in Path(normalized).parts:
                raise ValueError("Path traversal not allowed in logging.file")
            v.file = normalized
        return v

    @field_validator("reporting", mode="after")
    @classmethod
    def _validate_reporting_paths(cls, v: ReportingConfig) -> ReportingConfig:
        if v.output_dir:
            import os
            from pathlib import Path
            # Prevent path traversal - check BEFORE normpath (normpath resolves .. away)
            if ".." in v.output_dir.split(os.sep) or ".." in Path(v.output_dir).parts:
                raise ValueError("Path traversal not allowed in reporting.output_dir")
            normalized = os.path.normpath(v.output_dir)
            if ".." in Path(normalized).parts:
                raise ValueError("Path traversal not allowed in reporting.output_dir")
            v.output_dir = normalized
        return v


def _substitute(value: Any, env_vars: dict[str, str] | None = None) -> Any:
    """Recursively replace ``${VAR}`` strings with environment values.
    
    Uses env_vars dict (from /etc/chk-a/env) if provided, then falls back to os.environ.
    If not found in either, keeps the original ${VAR} placeholder.
    """
    if isinstance(value, str):
        def replace_match(m):
            var_name = m.group(1)
            # First check env_vars (from /etc/chk-a/env)
            if env_vars is not None and var_name in env_vars:
                return env_vars[var_name]
            # Then check os.environ (for tests and runtime)
            if var_name in os.environ:
                return os.environ[var_name]
            # Not found - keep placeholder
            return m.group(0)
        return _ENV_PATTERN.sub(replace_match, value)
    if isinstance(value, dict):
        return {k: _substitute(v, env_vars) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, env_vars) for v in value]
    return value


def _find_config_path(explicit_path: str | os.PathLike | None = None) -> Path | None:
    """Find config file in priority order:
    1. Explicit path argument (if provided and exists)
    2. CHK_A_CONFIG environment variable (if set and exists)
    3. /etc/chk-a/config.yaml (production)
    4. config/settings.yaml (development default)
    Returns None if no config file found.

    Note: If explicit path or CHK_A_CONFIG is provided but file doesn't exist,
    we return None (caller will return defaults) rather than falling back.
    """
    # If explicit path provided, use it only if exists
    if explicit_path is not None:
        p = Path(explicit_path)
        return p if p.exists() else None

    # If CHK_A_CONFIG set, use it only if exists
    if env_path := os.environ.get("CHK_A_CONFIG"):
        p = Path(env_path)
        return p if p.exists() else None

    # Auto-detect: production then development
    for candidate in [Path("/etc/chk-a/config.yaml"), Path("config/settings.yaml")]:
        if candidate.exists():
            return candidate

    return None


def load_config(path: str | os.PathLike | None = None) -> AppConfig:
    """Load configuration from ``path`` (or auto-detected location).

    Missing files yield an :class:`AppConfig` with all defaults.
    """
    yaml_path = _find_config_path(path)
    if yaml_path is None:
        return AppConfig()
    
    # Load env file for substitution (does not pollute os.environ)
    env_vars = _load_env_file()
    
    with open(yaml_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    data = _substitute(raw, env_vars)
    
    # Validate and log with masked secrets
    config = AppConfig.model_validate(data)
    
    # Log config summary with masked secrets
    import logging
    logger = logging.getLogger("chk_a.config")
    bot_token = config.alert.telegram_bot_token.get_secret_value() if config.alert.telegram_bot_token else ""
    chat_id = config.alert.telegram_chat_id.get_secret_value() if config.alert.telegram_chat_id else ""
    logger.info(
        "Config loaded: fqdns=%d resolvers=%d telegram_token=%s telegram_chat_id=%s",
        len(config.fqdns),
        len(config.resolvers),
        _mask_token(bot_token) if bot_token else "unset",
        chat_id[:4] + "***" if chat_id else "unset",
    )

    # Auto-tune resolver_agent parameters based on configured resolvers and FQDNs
    _auto_tune_resolver_agent(config)

    return config


def _auto_tune_resolver_agent(config: AppConfig) -> None:
    """Auto-tune ResolverAgent parameters based on resolver/FQDN counts."""
    resolver_count = len(config.resolvers)
    fqdn_count = len(config.fqdns)

    # If max_concurrent not explicitly set (None), calculate optimal value
    if config.resolver_agent.max_concurrent is None:
        # Base concurrency: scale with resolver count but cap reasonably
        # Formula: min(resolver_count, max(10, resolver_count // 2 + 5))
        # This gives: 1-5 resolvers -> 10, 10 -> 10, 20 -> 15, 30 -> 20, 50 -> 30
        base_concurrent = max(10, resolver_count // 2 + 5)
        config.resolver_agent.max_concurrent = min(resolver_count, base_concurrent)

    # Ensure default_timeout_ms is reasonable (already has default 2000)
    # Could auto-adjust based on network conditions in future

    # Log the auto-tuned values for visibility
    import logging

    logger = logging.getLogger("chk_a.config")
    if resolver_count > 0:
        logger.info(
            "Auto-tuned ResolverAgent: max_concurrent=%d (resolvers=%d, fqdns=%d)",
            config.resolver_agent.max_concurrent,
            resolver_count,
            fqdn_count,
        )


__all__ = ["AppConfig", "load_config"]
