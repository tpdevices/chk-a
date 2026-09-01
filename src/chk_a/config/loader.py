"""Configuration loader with YAML file + ${ENV} substitution.

Loads ``config/settings.yaml`` (override with ``CHK_A_CONFIG`` env var) and
substitutes ``${VAR}`` references from the process environment before validating
the result against :class:`AppConfig`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ..models.schemas import (
    AlertConfig,
    FQDNConfig,
    LoggingConfig,
    MLConfig,
    ResolverConfig,
    SchedulerConfig,
)

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Load /etc/chk-a/env if exists (for sudo/cli context)
def _load_env_file() -> None:
    """Load environment variables from /etc/chk-a/env into os.environ."""
    env_path = Path("/etc/chk-a/env")
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
        except Exception:
            pass

# Call on module import
_load_env_file()


class AppConfig(BaseModel):
    """Top-level application configuration."""

    fqdns: list[FQDNConfig] = Field(default_factory=list)
    resolvers: list[ResolverConfig] = Field(default_factory=list)
    ml: MLConfig = Field(default_factory=MLConfig)
    alert: AlertConfig = Field(default_factory=AlertConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    baseline_store_path: str = Field(default="./data/baselines.json")
    hostname: str = Field(default_factory=lambda: __import__("socket").gethostname())


def _substitute(value: Any) -> Any:
    """Recursively replace ``${VAR}`` strings with environment values."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _substitute(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v) for v in value]
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
    with open(yaml_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    data = _substitute(raw)
    return AppConfig.model_validate(data)


__all__ = ["AppConfig", "load_config"]
