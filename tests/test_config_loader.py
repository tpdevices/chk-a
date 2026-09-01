"""Unit tests for the chk-a config loader (YAML + ${ENV} substitution)."""

import os
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from chk_a.config.loader import AppConfig, load_config


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    p = tmp_path / "settings.yaml"
    p.write_text(
        textwrap.dedent("""
            fqdns:
              - name: "example.com"
                expected_ips: ["93.184.216.34"]
                min_consensus: 0.6
              - name: "api.github.com"
            resolvers:
              - name: "google"
                address: "8.8.8.8:53"
                weight: 1.0
                timeout_ms: 2000
            ml:
              baseline_decay: 0.05
              anomaly_threshold: 0.7
              min_samples_before_alert: 10
            alert:
              telegram_bot_token: "${TELEGRAM_BOT_TOKEN}"
              telegram_chat_id: "${TELEGRAM_CHAT_ID}"
              dedup_window_minutes: 30
              rate_limit_per_hour: 20
            scheduler:
              min_interval_sec: 30
              max_interval_sec: 180
              jitter: true
            logging:
              level: "INFO"
              file: "/var/log/chk-a/checks.jsonl"
              max_size_mb: 50
              backup_count: 10
            """),
        encoding="utf-8",
    )
    return p


def test_load_config_defaults_only():
    cfg = AppConfig()
    assert cfg.fqdns == []
    assert cfg.resolvers == []
    assert cfg.ml.anomaly_threshold == 0.7
    assert cfg.scheduler.min_interval_sec == 30


def test_load_config_from_yaml(yaml_file: Path):
    cfg = load_config(yaml_file)
    assert len(cfg.fqdns) == 2
    assert cfg.fqdns[0].name == "example.com"
    assert cfg.fqdns[0].expected_ips == ["93.184.216.34"]
    assert cfg.fqdns[1].name == "api.github.com"
    assert cfg.resolvers[0].address == "8.8.8.8:53"
    assert cfg.alert.dedup_window_minutes == 30


def test_env_substitution(yaml_file: Path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100999")
    cfg = load_config(yaml_file)
    assert cfg.alert.telegram_bot_token == "TOKEN123"
    assert cfg.alert.telegram_chat_id == "-100999"


def test_env_substitution_missing_kept_verbatim(yaml_file: Path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    cfg = load_config(yaml_file)
    # When env var is unset, the literal "${TELEGRAM_BOT_TOKEN}" remains.
    assert cfg.alert.telegram_bot_token == "${TELEGRAM_BOT_TOKEN}"


def test_missing_yaml_returns_defaults(tmp_path: Path, monkeypatch):
    missing = tmp_path / "nope.yaml"
    monkeypatch.setenv("CHK_A_CONFIG", str(missing))
    cfg = load_config(missing)
    assert cfg.fqdns == []
    assert cfg.resolvers == []


def test_scheduler_validator_via_yaml(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "scheduler:\n  min_interval_sec: 200\n  max_interval_sec: 180\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(p)
