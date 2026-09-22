"""Integration tests for log rotation and report generation.

Tests _load_recent_checks() handling of rotated log files (.bz2, .gz)
and mixed timezone timestamp parsing.
"""

from __future__ import annotations

import bz2
import gzip
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from chk_a.reporting.ml_insights import _load_recent_checks, compute_availability

# Set allowed base dir for tests
BASELINE_TEST_DIR = "/tmp/chk-a-test"
os.environ["CHK_A_BASELINE_DIR"] = BASELINE_TEST_DIR
Path(BASELINE_TEST_DIR).mkdir(parents=True, exist_ok=True)


def _make_test_log_dir() -> Path:
    """Create a unique test log directory for each test to avoid conflicts."""
    test_dir = Path(BASELINE_TEST_DIR) / f"test_{uuid.uuid4().hex[:8]}"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def _make_log_path(test_dir: Path) -> Path:
    """Create a log file path with standard name checks.jsonl."""
    return test_dir / "checks.jsonl"


def _make_check_record(
    fqdn: str,
    resolver: str,
    ips: list[str],
    success: bool = True,
    latency_ms: float = 25.0,
    timestamp: datetime | None = None,
    error: str | None = None,
) -> dict:
    """Create a check result record matching CheckResult schema."""
    if timestamp is None:
        timestamp = datetime.now()
    # Store timestamp in ISO format (local time, may be naive)
    ts_str = timestamp.isoformat()
    return {
        "fqdn": fqdn,
        "resolver": resolver,
        "ips": ips,
        "success": success,
        "latency_ms": latency_ms,
        "timestamp": ts_str,
        "error": error,
    }


def _write_log_file(path: Path, records: list[dict]) -> None:
    """Write records to a plain JSONL log file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _write_bz2_log_file(path: Path, records: list[dict]) -> None:
    """Write records to a bz2 compressed log file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with bz2.open(path, "wt", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _write_gz_log_file(path: Path, records: list[dict]) -> None:
    """Write records to a gz compressed log file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


class TestLogRotation:
    """Tests for _load_recent_checks() with rotated log files."""

    def test_load_recent_checks_plain_file(self):
        """Test loading from a plain (current) log file."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()
        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=1)),
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=now - timedelta(hours=2)),
            _make_check_record("example.com", "quad9", ["9.9.9.9"], timestamp=now - timedelta(days=2)),  # outside 1 day
        ]
        _write_log_file(log_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=now)

        assert len(df) == 2  # Only records within 1 day
        assert all(df["resolver"].isin(["google", "cloudflare"]))

    def test_load_recent_checks_dateext_bz2(self):
        """Test loading from date-stamped .bz2 rotated file."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Create current log file (empty)
        log_path.touch()

        # Create rotated file for yesterday: checks.jsonl-YYYYMMDD.bz2
        yesterday = now - timedelta(days=1)
        date_str = yesterday.strftime("%Y%m%d")
        rotated_path = log_path.parent / f"checks.jsonl-{date_str}.bz2"

        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=yesterday + timedelta(hours=10)),
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=yesterday + timedelta(hours=12)),
        ]
        _write_bz2_log_file(rotated_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=2, reference_date=now)

        assert len(df) == 2
        assert all(df["resolver"].isin(["google", "cloudflare"]))

    def test_load_recent_checks_numbered_gz(self):
        """Test loading from numbered .gz backup files."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Create current log file (empty)
        log_path.touch()

        # Create numbered backup: checks.jsonl.1.gz
        rotated_path = log_path.parent / "checks.jsonl.1.gz"

        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=6)),
            _make_check_record("example.com", "quad9", ["9.9.9.9"], timestamp=now - timedelta(days=3)),  # outside 1 day
        ]
        _write_gz_log_file(rotated_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=now)

        assert len(df) == 1  # Only google record within 1 day
        assert df.iloc[0]["resolver"] == "google"

    def test_load_recent_checks_multiple_rotated_files(self):
        """Test loading from multiple rotated files (bz2 + gz)."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Current log (today)
        today_records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=1)),
        ]
        _write_log_file(log_path, today_records)

        # Yesterday (bz2)
        yesterday = now - timedelta(days=1)
        date_str = yesterday.strftime("%Y%m%d")
        rotated_yesterday = log_path.parent / f"checks.jsonl-{date_str}.bz2"
        yesterday_records = [
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=yesterday + timedelta(hours=10)),
        ]
        _write_bz2_log_file(rotated_yesterday, yesterday_records)

        # Day before yesterday (gz numbered)
        rotated_old = log_path.parent / "checks.jsonl.1.gz"
        old_records = [
            _make_check_record("example.com", "quad9", ["1.2.3.4"], timestamp=now - timedelta(days=2, hours=5)),
        ]
        _write_gz_log_file(rotated_old, old_records)

        # 3 days lookback should include all
        df = _load_recent_checks(str(log_path), lookback_days=3, reference_date=now)
        assert len(df) == 3

        # 1.5 days lookback should include today + yesterday only
        df = _load_recent_checks(str(log_path), lookback_days=1.5, reference_date=now)
        assert len(df) == 2

    def test_load_recent_checks_mixed_timezone_timestamps(self):
        """Test loading logs with mixed naive and timezone-aware timestamps."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Create records with different timestamp formats
        records = [
            # Naive timestamp (local time)
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=1)),
            # Timezone-aware timestamp (UTC)
            {
                "fqdn": "example.com",
                "resolver": "cloudflare",
                "ips": ["1.2.3.4"],
                "success": True,
                "latency_ms": 25.0,
                "timestamp": (now - timedelta(hours=2)).replace(tzinfo=timezone.utc).isoformat(),
                "error": None,
            },
            # Timezone-aware timestamp (Asia/Bangkok +07)
            {
                "fqdn": "example.com",
                "resolver": "quad9",
                "ips": ["1.2.3.4"],
                "success": True,
                "latency_ms": 25.0,
                "timestamp": (now - timedelta(hours=3)).replace(tzinfo=timezone(timedelta(hours=7))).isoformat(),
                "error": None,
            },
        ]
        _write_log_file(log_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=now)

        assert len(df) == 3  # All within 1 day
        assert set(df["resolver"].tolist()) == {"google", "cloudflare", "quad9"}

    def test_load_recent_checks_fractional_lookback(self):
        """Test fractional lookback_days (e.g., hours since midnight)."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Midnight today
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hours_since_midnight = (now - midnight).total_seconds() / 3600
        lookback_fraction = hours_since_midnight / 24

        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=midnight + timedelta(hours=1)),
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=midnight + timedelta(hours=6)),
            _make_check_record("example.com", "quad9", ["1.2.3.4"], timestamp=now - timedelta(days=1)),  # yesterday
        ]
        _write_log_file(log_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=lookback_fraction, reference_date=now)

        # Should only include today's records (from midnight to now)
        assert len(df) == 2
        assert all(df["resolver"].isin(["google", "cloudflare"]))

    def test_load_recent_checks_skips_malformed_lines(self):
        """Test that malformed JSON lines are skipped gracefully."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=1)),
            "not a json line",
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=now - timedelta(hours=2)),
            "{invalid json",
            _make_check_record("example.com", "quad9", ["1.2.3.4"], timestamp=now - timedelta(hours=3)),
        ]
        _write_log_file(log_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=now)

        assert len(df) == 3  # Only valid JSON lines
        assert set(df["resolver"].tolist()) == {"google", "cloudflare", "quad9"}

    def test_load_recent_checks_skips_non_checkresult_lines(self):
        """Test that log messages (cycle complete, etc.) are skipped."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=1)),
            {"timestamp": now.isoformat(), "level": "INFO", "logger": "chk_a.orchestrator", "message": "Cycle complete", "correlation_id": "abc123"},
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=now - timedelta(hours=2)),
            {"timestamp": now.isoformat(), "level": "INFO", "logger": "chk_a.orchestrator", "message": "Next cycle in 30s"},
        ]
        _write_log_file(log_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=now)

        assert len(df) == 2  # Only CheckResult records
        assert set(df["resolver"].tolist()) == {"google", "cloudflare"}

    def test_load_recent_checks_empty_file(self):
        """Test loading from empty log file."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        log_path.touch()

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=datetime.now())

        assert df.empty

    def test_load_recent_checks_nonexistent_file(self):
        """Test loading from nonexistent log file."""
        test_dir = _make_test_log_dir()
        log_path = test_dir / "nonexistent.jsonl"

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=datetime.now())

        assert df.empty


class TestComputeAvailability:
    """Tests for compute_availability() with various log scenarios."""

    def test_compute_availability_with_rotated_logs(self):
        """Test availability computation using data from rotated logs."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Current log
        today_records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=1), success=True),
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=now - timedelta(hours=2), success=True),
            _make_check_record("example.com", "quad9", ["9.9.9.9"], timestamp=now - timedelta(hours=3), success=False, error="TIMEOUT"),
        ]
        _write_log_file(log_path, today_records)

        # Yesterday (bz2)
        yesterday = now - timedelta(days=1)
        date_str = yesterday.strftime("%Y%m%d")
        rotated_yesterday = log_path.parent / f"checks.jsonl-{date_str}.bz2"
        yesterday_records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=yesterday + timedelta(hours=10), success=True),
            _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=yesterday + timedelta(hours=12), success=True),
            _make_check_record("example.com", "quad9", ["9.9.9.9"], timestamp=yesterday + timedelta(hours=14), success=True),
        ]
        _write_bz2_log_file(rotated_yesterday, yesterday_records)

        df = _load_recent_checks(str(log_path), lookback_days=2, reference_date=now)
        avail = compute_availability(df)

        # Google: 2 success / 2 total = 100%
        assert avail["google"]["availability_pct"] == 100.0
        assert avail["google"]["successful_queries"] == 2
        assert avail["google"]["total_queries"] == 2

        # Cloudflare: 2 success / 2 total = 100%
        assert avail["cloudflare"]["availability_pct"] == 100.0

        # Quad9: 1 success / 2 total = 50%
        assert avail["quad9"]["availability_pct"] == 50.0
        assert avail["quad9"]["successful_queries"] == 1
        assert avail["quad9"]["total_queries"] == 2

    def test_compute_availability_daily_availability(self):
        """Test daily_availability output for daily heatmap."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Spread records across 3 days
        for day_offset in range(3):
            day = now - timedelta(days=day_offset)
            records = [
                _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=day + timedelta(hours=10), success=True),
                _make_check_record("example.com", "cloudflare", ["1.2.3.4"], timestamp=day + timedelta(hours=12), success=True),
            ]
            # Write to date-stamped bz2 file
            date_str = day.strftime("%Y%m%d")
            rotated_path = log_path.parent / f"checks.jsonl-{date_str}.bz2"
            _write_bz2_log_file(rotated_path, records)

        # Also add current log (today)
        _write_log_file(log_path, [])

        df = _load_recent_checks(str(log_path), lookback_days=3, reference_date=now)
        avail = compute_availability(df)

        # Each resolver should have daily_availability for 3 days
        assert "daily_availability" in avail["google"]
        assert "daily_availability" in avail["cloudflare"]

        # Should have 3 entries (one per day)
        assert len(avail["google"]["daily_availability"]) == 3
        assert len(avail["cloudflare"]["daily_availability"]) == 3

        # All should be 100% (2 success / 2 total per day)
        for day_pct in avail["google"]["daily_availability"].values():
            assert day_pct == 100.0


class TestLogRotationEdgeCases:
    """Edge cases for log rotation handling."""

    def test_load_recent_checks_rotated_file_outside_lookback_excluded(self):
        """Test that rotated files outside lookback window are excluded."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        log_path.touch()

        # File from 10 days ago (should be excluded for 7-day lookback)
        old_date = (now - timedelta(days=10)).strftime("%Y%m%d")
        rotated_path = log_path.parent / f"checks.jsonl-{old_date}.bz2"
        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(days=10)),
        ]
        _write_bz2_log_file(rotated_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=7, reference_date=now)

        assert len(df) == 0

    def test_load_recent_checks_invalid_dateext_skipped(self):
        """Test that dateext files with invalid dates are skipped (but included if no date)."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        log_path.touch()

        # Invalid date in filename
        rotated_path = log_path.parent / "checks.jsonl-notadate.bz2"
        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=now - timedelta(hours=1)),
        ]
        _write_bz2_log_file(rotated_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=now)

        # Should still include (fallback: no date check, filter by timestamp)
        assert len(df) == 1

    def test_load_recent_checks_preserves_local_time(self):
        """Test that timestamps are preserved in local time (Asia/Bangkok)."""
        test_dir = _make_test_log_dir()
        log_path = _make_log_path(test_dir)
        now = datetime.now()

        # Record at specific local time
        local_ts = now.replace(hour=10, minute=30, second=0, microsecond=0)
        records = [
            _make_check_record("example.com", "google", ["1.2.3.4"], timestamp=local_ts),
        ]
        _write_log_file(log_path, records)

        df = _load_recent_checks(str(log_path), lookback_days=1, reference_date=now)

        assert len(df) == 1
        # Timestamp should be in Asia/Bangkok timezone
        ts = df.iloc[0]["timestamp"]
        assert ts.tzinfo is not None
        # Hour should be preserved (10:30 in local time)
        assert ts.hour == 10
        assert ts.minute == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])