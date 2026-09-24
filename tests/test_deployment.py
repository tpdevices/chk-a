"""Tests for Loop 6 deployment helpers: config validation and sd_notify."""

from __future__ import annotations

import importlib

import pytest

from chk_a.config.loader import AppConfig, load_config
from chk_a.validate_config import validate


def test_validate_ok_with_real_config():
    cfg = load_config("config/config.yaml.example")
    assert validate(cfg) == []


def test_validate_reports_empty_fqdns(monkeypatch, tmp_path):
    # A config with no fqdns/resolvers must be flagged.
    cfg = AppConfig()
    problems = validate(cfg)
    assert any("fqdns" in p for p in problems)
    assert any("resolvers" in p for p in problems)


def test_validate_reports_bad_scheduler():
    cfg = AppConfig()
    cfg.scheduler.min_interval_sec = 180
    cfg.scheduler.max_interval_sec = 30
    problems = validate(cfg)
    assert any("max_interval_sec" in p for p in problems)


def test_validate_config_module_exit_codes(monkeypatch):
    # Patch load_config to return a valid config -> exit 0.
    import chk_a.validate_config as vc

    monkeypatch.setattr(vc, "load_config", lambda *a, **k: AppConfig(fqdns=[], resolvers=[]))
    # Force a non-empty problem list by emptying fqdns on a fresh config.
    cfg = AppConfig()
    monkeypatch.setattr(vc, "load_config", lambda *a, **k: cfg)
    assert vc.main([]) == 1  # empty fqdns -> failure

    good = AppConfig(
        fqdns=[
            __import__("chk_a.models.schemas", fromlist=["FQDNConfig"]).FQDNConfig(name="x.com")
        ],
        resolvers=[
            __import__("chk_a.models.schemas", fromlist=["ResolverConfig"]).ResolverConfig(
                name="r", address="8.8.8.8:53"
            )
        ],
    )
    monkeypatch.setattr(vc, "load_config", lambda *a, **k: good)
    assert vc.main([]) == 0


def test_systemd_notify_falls_back_without_socket(monkeypatch):
    # Without NOTIFY_SOCKET the helper must be a safe no-op (returns False).
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    from chk_a.utils import systemd_notify

    importlib.reload(systemd_notify)
    assert systemd_notify.notify_ready() is False
    assert systemd_notify.notify_watchdog() is False
    assert systemd_notify.notify_stopping() is False
