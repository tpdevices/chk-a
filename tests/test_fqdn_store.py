"""Tests for FQDN-centric data model and storage."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from chk_a.storage.fqdn_store import FQDNRecord, FQDNStore

# Set allowed base dir for all tests in this module
FQDN_TEST_DIR = "/tmp/chk-a-test/fqdns"
os.environ["CHK_A_FQDN_DIR"] = FQDN_TEST_DIR
Path(FQDN_TEST_DIR).mkdir(parents=True, exist_ok=True)


def _make_test_path(suffix: str = "fqdns.json") -> Path:
    """Create a temp file path within the allowed test directory."""
    import uuid
    return Path(FQDN_TEST_DIR) / f"test_{uuid.uuid4().hex[:8]}_{suffix}"


class TestFQDNRecord:
    """Tests for FQDNRecord data model."""

    def test_create_minimal(self):
        """Test creating minimal FQDNRecord."""
        rec = FQDNRecord("www.example.com")
        assert rec.fqdn == "www.example.com"
        assert rec.domain == "example.com"
        assert rec.subdomain == "www"
        assert rec.apex == "example.com"
        assert rec.current_ips == []
        assert rec.status == "unknown"

    def test_create_with_data(self):
        """Test creating FQDNRecord with all fields."""
        rec = FQDNRecord(
            fqdn="api.github.com",
            current_ips=["1.2.3.4", "5.6.7.8"],
            cname_chain=["github.com"],
            ttl=300,
            registrar="GitHub Inc.",
            expiry_date="2025-12-31",
            nameservers=["ns1.github.com", "ns2.github.com"],
        )
        assert rec.fqdn == "api.github.com"
        assert rec.domain == "github.com"
        assert rec.subdomain == "api"
        assert rec.apex == "github.com"
        assert rec.current_ips == ["1.2.3.4", "5.6.7.8"]
        assert rec.cname_chain == ["github.com"]
        assert rec.ttl == 300
        assert rec.registrar == "GitHub Inc."
        assert rec.expiry_date == "2025-12-31"
        assert rec.nameservers == ["ns1.github.com", "ns2.github.com"]

    def test_extract_domain_variants(self):
        """Test domain extraction for various FQDN formats."""
        assert FQDNRecord._extract_domain("example.com") == "example.com"
        assert FQDNRecord._extract_domain("www.example.com") == "example.com"
        assert FQDNRecord._extract_domain("api.v2.example.com") == "example.com"
        assert FQDNRecord._extract_domain("a.b.c.d.example.co.uk") == "example.co.uk"
        assert FQDNRecord._extract_domain("www.example.co.uk") == "example.co.uk"
        assert FQDNRecord._extract_domain("example.co.uk") == "example.co.uk"

    def test_extract_subdomain(self):
        """Test subdomain extraction."""
        assert FQDNRecord._extract_subdomain("example.com") == ""
        assert FQDNRecord._extract_subdomain("www.example.com") == "www"
        assert FQDNRecord._extract_subdomain("api.v2.example.com") == "api.v2"

    def test_extract_apex(self):
        """Test apex extraction."""
        assert FQDNRecord._extract_apex("example.com") == "example.com"
        assert FQDNRecord._extract_apex("www.example.com") == "example.com"
        assert FQDNRecord._extract_apex("api.example.com") == "example.com"

    def test_add_ip_change(self):
        """Test recording IP change history."""
        rec = FQDNRecord("test.example.com", current_ips=["1.1.1.1"])
        ts = datetime(2026, 9, 22, 12, 0, 0)
        rec.add_ip_change(["1.1.1.1"], ["2.2.2.2", "3.3.3.3"], "consensus", ts)

        assert rec.current_ips == ["2.2.2.2", "3.3.3.3"]
        assert len(rec.ip_history) == 1
        assert rec.ip_history[0]["old_ips"] == ["1.1.1.1"]
        assert rec.ip_history[0]["new_ips"] == ["2.2.2.2", "3.3.3.3"]
        assert rec.ip_history[0]["source"] == "consensus"
        assert rec.ip_history[0]["timestamp"] == ts.isoformat()

    def test_update_monitoring_state_success(self):
        """Test monitoring state update on success."""
        rec = FQDNRecord("test.example.com", consecutive_failures=5, status="degraded")
        ts = datetime(2026, 9, 22, 12, 0, 0)
        rec.update_monitoring_state(True, 25.0, ts)

        assert rec.status == "healthy"
        assert rec.consecutive_failures == 0
        assert rec.last_checked == ts

    def test_update_monitoring_state_failure(self):
        """Test monitoring state update on failure."""
        rec = FQDNRecord("test.example.com", consecutive_failures=0, status="healthy")
        rec.update_monitoring_state(False, 0.0)

        assert rec.consecutive_failures == 1
        assert rec.status == "healthy"  # Still healthy at 1 failure

    def test_update_monitoring_state_degraded(self):
        """Test degraded status at 3 failures."""
        rec = FQDNRecord("test.example.com", consecutive_failures=2)
        rec.update_monitoring_state(False)  # Now at 3

        assert rec.consecutive_failures == 3
        assert rec.status == "degraded"

    def test_update_monitoring_state_down(self):
        """Test down status at 10 failures."""
        rec = FQDNRecord("test.example.com", consecutive_failures=9)
        rec.update_monitoring_state(False)

        assert rec.consecutive_failures == 10
        assert rec.status == "down"

    def test_update_baseline(self):
        """Test updating baseline IPs."""
        rec = FQDNRecord("test.example.com")
        rec.update_baseline({"1.2.3.4": 0.7, "5.6.7.8": 0.3})
        assert rec.baseline_ips == {"1.2.3.4": 0.7, "5.6.7.8": 0.3}

    def test_update_anomaly_score_clamping(self):
        """Test anomaly score is clamped to [0, 1]."""
        rec = FQDNRecord("test.example.com")
        rec.update_anomaly_score(1.5)
        assert rec.anomaly_score == 1.0
        rec.update_anomaly_score(-0.5)
        assert rec.anomaly_score == 0.0
        rec.update_anomaly_score(0.5)
        assert rec.anomaly_score == 0.5

    def test_increment_counters(self):
        """Test flip-flop and geo shift counters."""
        rec = FQDNRecord("test.example.com")
        assert rec.flip_flop_count == 0
        assert rec.geo_shifts == 0
        rec.increment_flip_flop()
        rec.increment_flip_flop()
        rec.increment_geo_shift()
        assert rec.flip_flop_count == 2
        assert rec.geo_shifts == 1

    def test_serialization_roundtrip(self):
        """Test to_dict and from_dict roundtrip."""
        rec = FQDNRecord(
            fqdn="www.example.com",
            current_ips=["1.2.3.4"],
            cname_chain=["example.com"],
            ttl=300,
            registrar="Test Registrar",
            expiry_date="2025-12-31",
            nameservers=["ns1.example.com"],
        )
        rec.update_monitoring_state(True, 25.0)
        rec.update_baseline({"1.2.3.4": 1.0})
        rec.update_anomaly_score(0.25)
        rec.increment_flip_flop()

        data = rec.to_dict()
        rec2 = FQDNRecord.from_dict(data)

        assert rec2.fqdn == rec.fqdn
        assert rec2.domain == rec.domain
        assert rec2.subdomain == rec.subdomain
        assert rec2.apex == rec.apex
        assert rec2.current_ips == rec.current_ips
        assert rec2.cname_chain == rec.cname_chain
        assert rec2.ttl == rec.ttl
        assert rec2.registrar == rec.registrar
        assert rec2.expiry_date == rec.expiry_date
        assert rec2.nameservers == rec.nameservers
        assert rec2.last_checked == rec.last_checked
        assert rec2.status == rec.status
        assert rec2.consecutive_failures == rec.consecutive_failures
        assert rec2.baseline_ips == rec.baseline_ips
        assert rec2.anomaly_score == rec.anomaly_score
        assert rec2.flip_flop_count == rec.flip_flop_count
        assert rec2.geo_shifts == rec.geo_shifts


class TestFQDNStore:
    """Tests for FQDNStore persistence."""

    def test_store_create_and_load(self):
        """Test basic store create, save, and load."""
        path = _make_test_path()
        store = FQDNStore(path)

        rec = FQDNRecord("www.example.com", current_ips=["1.2.3.4"])
        rec.update_monitoring_state(True)
        store.set(rec)
        store.save()

        # Reload
        store2 = FQDNStore(path)
        loaded = store2.get("www.example.com")
        assert loaded is not None
        assert loaded.fqdn == "www.example.com"
        assert loaded.current_ips == ["1.2.3.4"]
        assert loaded.status == "healthy"

    def test_store_get_missing(self):
        """Test get returns None for missing FQDN."""
        path = _make_test_path()
        store = FQDNStore(path)
        assert store.get("missing.example.com") is None

    def test_store_delete(self):
        """Test delete removes record."""
        path = _make_test_path()
        store = FQDNStore(path)

        rec = FQDNRecord("www.example.com")
        store.set(rec)
        store.save()

        assert store.delete("www.example.com") is True
        assert store.get("www.example.com") is None
        assert store.delete("www.example.com") is False  # Already deleted

    def test_store_all_fqdns(self):
        """Test all_fqdns returns all keys."""
        path = _make_test_path()
        store = FQDNStore(path)

        store.set(FQDNRecord("www.example.com"))
        store.set(FQDNRecord("api.example.com"))
        store.set(FQDNRecord("other.org"))
        store.save()

        fqdns = store.all_fqdns()
        assert len(fqdns) == 3
        assert set(fqdns) == {"www.example.com", "api.example.com", "other.org"}

    def test_store_get_by_domain(self):
        """Test get_by_domain filters correctly."""
        path = _make_test_path()
        store = FQDNStore(path)

        store.set(FQDNRecord("www.example.com"))
        store.set(FQDNRecord("api.example.com"))
        store.set(FQDNRecord("blog.example.com"))
        store.set(FQDNRecord("other.org"))
        store.save()

        example_com = store.get_by_domain("example.com")
        assert len(example_com) == 3
        assert all(r.domain == "example.com" for r in example_com)

        other_org = store.get_by_domain("other.org")
        assert len(other_org) == 1
        assert other_org[0].fqdn == "other.org"

    def test_store_get_by_status(self):
        """Test get_by_status filters correctly."""
        path = _make_test_path()
        store = FQDNStore(path)

        rec1 = FQDNRecord("healthy.example.com")
        rec1.update_monitoring_state(True)
        store.set(rec1)

        rec2 = FQDNRecord("degraded.example.com")
        rec2.consecutive_failures = 5
        rec2.status = "degraded"
        store.set(rec2)

        rec3 = FQDNRecord("down.example.com")
        rec3.consecutive_failures = 10
        rec3.status = "down"
        store.set(rec3)

        store.save()

        healthy = store.get_by_status("healthy")
        assert len(healthy) == 1
        assert healthy[0].fqdn == "healthy.example.com"

        degraded = store.get_by_status("degraded")
        assert len(degraded) == 1
        assert degraded[0].fqdn == "degraded.example.com"

        down = store.get_by_status("down")
        assert len(down) == 1
        assert down[0].fqdn == "down.example.com"

    def test_store_get_anomalous(self):
        """Test get_anomalous filters by anomaly_score."""
        path = _make_test_path()
        store = FQDNStore(path)

        rec1 = FQDNRecord("normal.example.com")
        rec1.update_anomaly_score(0.2)
        store.set(rec1)

        rec2 = FQDNRecord("warning.example.com")
        rec2.update_anomaly_score(0.7)
        store.set(rec2)

        rec3 = FQDNRecord("critical.example.com")
        rec3.update_anomaly_score(0.9)
        store.set(rec3)

        store.save()

        anomalous = store.get_anomalous(0.7)
        assert len(anomalous) == 2
        assert {r.fqdn for r in anomalous} == {"warning.example.com", "critical.example.com"}

        critical = store.get_anomalous(0.8)
        assert len(critical) == 1
        assert critical[0].fqdn == "critical.example.com"

    def test_store_get_recently_changed(self):
        """Test get_recently_changed finds recent IP changes."""
        path = _make_test_path()
        store = FQDNStore(path)

        now = datetime.now()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        # Recent change (2 hours ago)
        rec1 = FQDNRecord("recent.example.com", current_ips=["1.1.1.1"])
        rec1.add_ip_change(["1.1.1.1"], ["2.2.2.2"], "consensus", now - timedelta(hours=2))
        store.set(rec1)

        # Older change (yesterday) - 36 hours ago
        rec2 = FQDNRecord("yesterday.example.com", current_ips=["3.3.3.3"])
        rec2.add_ip_change(["3.3.3.3"], ["4.4.4.4"], "resolver", now - timedelta(hours=36))
        store.set(rec2)

        # Old change (last week)
        rec3 = FQDNRecord("old.example.com", current_ips=["5.5.5.5"])
        rec3.add_ip_change(["5.5.5.5"], ["6.6.6.6"], "manual", last_week)
        store.set(rec3)

        store.save()

        recent = store.get_recently_changed(now - timedelta(days=1))
        assert len(recent) == 1
        assert recent[0].fqdn == "recent.example.com"

        last_two_days = store.get_recently_changed(now - timedelta(days=2))
        assert len(last_two_days) == 2
        assert {r.fqdn for r in last_two_days} == {"recent.example.com", "yesterday.example.com"}

        all_changes = store.get_recently_changed(now - timedelta(days=10))
        assert len(all_changes) == 3

    def test_store_path_traversal_protection(self):
        """Test store rejects paths outside allowed directory."""
        with pytest.raises(ValueError, match="outside allowed directory"):
            FQDNStore("/etc/passwd")

    def test_store_corrupt_file_handling(self):
        """Test store handles corrupt file gracefully."""
        path = _make_test_path()
        # Write corrupt JSON
        path.write_text("{ invalid json")

        store = FQDNStore(path)
        # Should not raise, just initialize empty
        assert store._data == {"version": 1, "records": {}}
        assert store.get("any.example.com") is None

    def test_store_empty_file(self):
        """Test store handles empty file."""
        path = _make_test_path()
        path.touch()

        store = FQDNStore(path)
        assert store._data == {"version": 1, "records": {}}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])