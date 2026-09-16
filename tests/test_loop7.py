"""Tests for Loop 7: correlation context and CLI subcommands.

Note: the optional Prometheus /metrics endpoint was removed per the
"no prometheus or other monitor" requirement, so only the per-cycle
``correlation_id`` tracing and the CLI subcommands are exercised here.
"""

from __future__ import annotations

import asyncio
import os

os.environ["CHK_A_BASELINE_DIR"] = "/tmp"

from chk_a.config.loader import load_config
from chk_a.utils.context import (
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)


# -- correlation context ----------------------------------------------------
def test_correlation_id_roundtrip() -> None:
    assert get_correlation_id() is None
    cid = new_correlation_id()
    assert len(cid) == 32  # uuid4 hex
    set_correlation_id(cid)
    assert get_correlation_id() == cid
    set_correlation_id(None)
    assert get_correlation_id() is None


def test_correlation_id_unique() -> None:
    assert new_correlation_id() != new_correlation_id()


# -- CLI subcommands -------------------------------------------------------
def test_validate_config_cli() -> None:
    from chk_a.main import cmd_validate_config

    config = load_config("config/settings.yaml")
    # settings.yaml is a valid example config -> exit 0
    assert cmd_validate_config(config) == 0


def test_show_baseline_cli_runs(capsys, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from chk_a.main import cmd_show_baseline
    from chk_a.utils.logger import setup_logger

    config = load_config("config/settings.yaml")
    config.baseline_store_path = str(tmp_path / "baselines.json")
    config.alert.alert_log_path = str(tmp_path / "alerts.jsonl")
    config.alert.alert_text_log_path = str(tmp_path / "alerts.log")
    config.alert.dedup_cache_path = str(tmp_path / "dedup_cache.json")
    logger = setup_logger("chk_a.test")
    rc = cmd_show_baseline(config, logger)
    assert rc == 0
    out = capsys.readouterr().out
    assert "example.com" in out


def test_check_once_cli_runs(tmp_path) -> None:
    from chk_a.main import cmd_check_once
    from chk_a.utils.logger import setup_logger

    config = load_config("config/settings.yaml")
    config.baseline_store_path = str(tmp_path / "baselines.json")
    config.alert.alert_log_path = str(tmp_path / "alerts.jsonl")
    config.alert.alert_text_log_path = str(tmp_path / "alerts.log")
    config.alert.dedup_cache_path = str(tmp_path / "dedup_cache.json")
    logger = setup_logger("chk_a.test")
    # Runs a real (network) cycle; should complete without raising.
    rc = asyncio.run(cmd_check_once(config, logger))
    assert rc == 0
