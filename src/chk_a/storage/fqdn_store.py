"""FQDN-centric data model and storage for chk-a.

This module provides FQDN as the primary entity with:
- Identity (fqdn, domain, subdomain, apex)
- DNS records (current IPs, CNAME chain, TTL)
- History (IP changes with timestamps/sources)
- Metadata (registrar, expiry, NS)
- Monitoring state (last_checked, status, failures)
- Alerting rules
- ML features (baseline IPs, anomaly score, flip-flop count, geo shifts)
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ..utils.logger import setup_logger

_SCHEMA_VERSION = 1

# Public suffixes for correct domain extraction (ccTLDs and known public suffixes)
# Source: https://publicsuffix.org/list/public_suffix_list.dat
# Minimal set for common cases - extend as needed
_PUBLIC_SUFFIXES = {
    # Two-label public suffixes
    "co.uk", "com.au", "org.uk", "net.uk", "ac.uk", "gov.uk",
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp", "ed.jp",
    "com.br", "org.br", "net.br", "gov.br", "edu.br",
    "co.za", "org.za", "net.za", "ac.za", "gov.za",
    "co.nz", "org.nz", "net.nz", "ac.nz", "gov.nz", "school.nz",
    "co.il", "org.il", "net.il", "ac.il", "gov.il", "muni.il",
    "com.mx", "org.mx", "net.mx", "gob.mx", "edu.mx",
    "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn",
    "com.tw", "org.tw", "net.tw", "gov.tw", "edu.tw",
    "com.hk", "org.hk", "net.hk", "gov.hk", "edu.hk",
    "com.sg", "org.sg", "net.sg", "gov.sg", "edu.sg",
    "com.my", "org.my", "net.my", "gov.my", "edu.my",
    "com.ph", "org.ph", "net.ph", "gov.ph", "edu.ph",
    "com.vn", "org.vn", "net.vn", "gov.vn", "edu.vn",
    "com.th", "org.th", "net.th", "gov.th", "edu.th",
    "co.th", "or.th", "go.th", "ac.th", "in.th",
    "co.id", "or.id", "ac.id", "go.id", "web.id", "sch.id",
    "co.kr", "or.kr", "ne.kr", "go.kr", "ac.kr",
    "co.in", "org.in", "net.in", "gov.in", "ac.in",
    "com.bd", "org.bd", "net.bd", "gov.bd", "edu.bd",
    "com.pk", "org.pk", "net.pk", "gov.pk", "edu.pk",
    "co.ke", "or.ke", "ac.ke", "go.ke", "ne.ke",
    "co.ng", "org.ng", "net.ng", "gov.ng", "edu.ng",
    "com.eg", "org.eg", "net.eg", "gov.eg", "edu.eg",
    "com.sa", "org.sa", "net.sa", "gov.sa", "edu.sa",
    "co.ae", "org.ae", "net.ae", "gov.ae", "ac.ae",
    "co.za", "org.za", "net.za", "ac.za", "gov.za",
    # Common two-letter ccTLDs used as public suffixes
    "com", "org", "net", "edu", "gov", "mil", "int",
}

# Allowed base directory for FQDN stores (prevents path traversal)
def _get_fqdn_allowed_base_dir() -> Path:
    return Path(os.getenv("CHK_A_FQDN_DIR", "/var/lib/chk-a/fqdns")).resolve()


class FQDNRecord:
    """Complete FQDN record with identity, DNS data, history, metadata, and monitoring state."""

    def __init__(
        self,
        fqdn: str,
        domain: str | None = None,
        subdomain: str | None = None,
        apex: str | None = None,
        current_ips: list[str] | None = None,
        cname_chain: list[str] | None = None,
        ttl: int | None = None,
        ip_history: list[dict[str, Any]] | None = None,
        registrar: str | None = None,
        expiry_date: str | None = None,
        nameservers: list[str] | None = None,
        last_checked: datetime | None = None,
        status: str = "unknown",
        consecutive_failures: int = 0,
        alert_rules: dict[str, Any] | None = None,
        baseline_ips: dict[str, float] | None = None,
        anomaly_score: float = 0.0,
        flip_flop_count: int = 0,
        geo_shifts: int = 0,
    ) -> None:
        self.fqdn = fqdn
        self.domain = domain or self._extract_domain(fqdn)
        self.subdomain = subdomain or self._extract_subdomain(fqdn)
        self.apex = apex or self._extract_apex(fqdn)
        self.current_ips = current_ips or []
        self.cname_chain = cname_chain or []
        self.ttl = ttl
        self.ip_history = ip_history or []
        self.registrar = registrar
        self.expiry_date = expiry_date
        self.nameservers = nameservers or []
        self.last_checked = last_checked
        self.status = status
        self.consecutive_failures = consecutive_failures
        self.alert_rules = alert_rules or {}
        self.baseline_ips = baseline_ips or {}
        self.anomaly_score = anomaly_score
        self.flip_flop_count = flip_flop_count
        self.geo_shifts = geo_shifts

    @staticmethod
    def _extract_domain(fqdn: str) -> str:
        """Extract registered domain (e.g., example.com from www.example.com, example.co.uk from www.example.co.uk)."""
        labels = fqdn.split(".")
        if len(labels) >= 3:
            # Check if last 2 labels form a known public suffix
            suffix_2 = ".".join(labels[-2:])
            if suffix_2 in _PUBLIC_SUFFIXES:
                return ".".join(labels[-3:])
            # Check if last 3 labels form a known public suffix (e.g., co.uk)
            if len(labels) >= 4:
                suffix_3 = ".".join(labels[-3:])
                if suffix_3 in _PUBLIC_SUFFIXES:
                    return ".".join(labels[-4:])
        if len(labels) >= 2:
            return ".".join(labels[-2:])
        return fqdn

    @staticmethod
    def _extract_subdomain(fqdn: str) -> str:
        """Extract subdomain part (e.g., www from www.example.com, www from www.example.co.uk)."""
        domain = FQDNRecord._extract_domain(fqdn)
        if fqdn == domain:
            return ""
        # Remove domain part and trailing dot
        subdomain = fqdn[:-(len(domain) + 1)]
        return subdomain

    @staticmethod
    def _extract_apex(fqdn: str) -> str:
        """Extract apex domain (same as registered domain)."""
        return FQDNRecord._extract_domain(fqdn)

    def add_ip_change(self, old_ips: list[str], new_ips: list[str], source: str, timestamp: datetime | None = None) -> None:
        """Record an IP change in history."""
        if timestamp is None:
            timestamp = datetime.now()
        self.ip_history.append({
            "timestamp": timestamp.isoformat(),
            "old_ips": old_ips,
            "new_ips": new_ips,
            "source": source,  # e.g., "resolver", "consensus", "manual"
        })
        self.current_ips = new_ips

    def update_monitoring_state(self, success: bool, latency_ms: float = 0.0, timestamp: datetime | None = None) -> None:
        """Update monitoring state after a check."""
        if timestamp is None:
            timestamp = datetime.now()
        self.last_checked = timestamp
        if success:
            self.status = "healthy"
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.status = "degraded"
            if self.consecutive_failures >= 10:
                self.status = "down"

    def update_baseline(self, ips: dict[str, float]) -> None:
        """Update baseline IPs from ML agent."""
        self.baseline_ips = ips

    def update_anomaly_score(self, score: float) -> None:
        """Update anomaly score."""
        self.anomaly_score = max(0.0, min(1.0, score))

    def increment_flip_flop(self) -> None:
        """Increment flip-flop counter (IP toggling between two states)."""
        self.flip_flop_count += 1

    def increment_geo_shift(self) -> None:
        """Increment geo shift counter (IP moved to different geographic region)."""
        self.geo_shifts += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "fqdn": self.fqdn,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "apex": self.apex,
            "current_ips": self.current_ips,
            "cname_chain": self.cname_chain,
            "ttl": self.ttl,
            "ip_history": self.ip_history,
            "registrar": self.registrar,
            "expiry_date": self.expiry_date,
            "nameservers": self.nameservers,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "alert_rules": self.alert_rules,
            "baseline_ips": self.baseline_ips,
            "anomaly_score": self.anomaly_score,
            "flip_flop_count": self.flip_flop_count,
            "geo_shifts": self.geo_shifts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FQDNRecord":
        """Deserialize from dictionary."""
        record = cls(
            fqdn=data["fqdn"],
            domain=data.get("domain"),
            subdomain=data.get("subdomain"),
            apex=data.get("apex"),
            current_ips=data.get("current_ips"),
            cname_chain=data.get("cname_chain"),
            ttl=data.get("ttl"),
            ip_history=data.get("ip_history"),
            registrar=data.get("registrar"),
            expiry_date=data.get("expiry_date"),
            nameservers=data.get("nameservers"),
            last_checked=None,  # parse below
            status=data.get("status", "unknown"),
            consecutive_failures=data.get("consecutive_failures", 0),
            alert_rules=data.get("alert_rules"),
            baseline_ips=data.get("baseline_ips"),
            anomaly_score=data.get("anomaly_score", 0.0),
            flip_flop_count=data.get("flip_flop_count", 0),
            geo_shifts=data.get("geo_shifts", 0),
        )
        # Parse timestamp
        last_checked = data.get("last_checked")
        if last_checked:
            try:
                record.last_checked = datetime.fromisoformat(last_checked)
            except ValueError:
                pass
        return record


class FQDNStore:
    """JSON-backed store for FQDN records, loaded on startup, saved atomically."""

    def __init__(
            self,
            path: str | os.PathLike,
            logger_name: str = "chk_a.storage.fqdn",
        ) -> None:
            resolved_path = Path(path).resolve()
            if not self._is_path_allowed(resolved_path):
                raise ValueError(
                    f"FQDN store path '{resolved_path}' is outside allowed directory '{_get_fqdn_allowed_base_dir()}'"
                )
            self.path = resolved_path
            self.logger = setup_logger(logger_name)
            self._data: dict[str, Any] = {"version": int(_SCHEMA_VERSION), "records": {}}
            self.load()

    @staticmethod
    def _is_path_allowed(path: Path) -> bool:
        """Check if the given path is within the allowed base directory."""
        try:
            path.relative_to(_get_fqdn_allowed_base_dir())
            return True
        except ValueError:
            return False

    def load(self) -> None:
        """Load FQDN records from disk; a missing/corrupt file yields empty state."""
        if not self.path.exists():
            self._data = {"version": _SCHEMA_VERSION, "records": {}}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict) or "records" not in raw:
                raise ValueError("unexpected FQDN store file shape")
            self._data = {
                "version": _SCHEMA_VERSION,
                "records": raw.get("records", {}),
            }
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            self.logger.warning("Could not load FQDN store %s: %s", self.path, exc)
            self._data = {"version": _SCHEMA_VERSION, "records": {}}

    def save(self) -> None:
        """Atomically persist FQDN records (temp file + os.replace)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent),
            suffix=".tmp",
            prefix=f".{self.path.name}",
        )
        try:
            data_bytes = json.dumps(self._data, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
            with os.fdopen(tmp_fd, "wb") as fh:
                fh.write(data_bytes)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def get(self, fqdn: str) -> FQDNRecord | None:
        """Return FQDNRecord for fqdn or None."""
        raw = self._data["records"].get(fqdn)
        if raw is None:
            return None
        return FQDNRecord.from_dict(raw)

    def set(self, record: FQDNRecord) -> None:
        """Store or update FQDNRecord."""
        self._data["records"][record.fqdn] = record.to_dict()

    def delete(self, fqdn: str) -> bool:
        """Delete FQDN record. Returns True if existed."""
        if fqdn in self._data["records"]:
            del self._data["records"][fqdn]
            return True
        return False

    def all_fqdns(self) -> list[str]:
        """Return all FQDNs in the store."""
        return list(self._data["records"].keys())

    def get_by_domain(self, domain: str) -> list[FQDNRecord]:
        """Return all FQDNRecords under a domain."""
        return [
            FQDNRecord.from_dict(raw)
            for fqdn, raw in self._data["records"].items()
            if raw.get("domain") == domain
        ]

    def get_by_status(self, status: str) -> list[FQDNRecord]:
        """Return all FQDNRecords with a specific status."""
        return [
            FQDNRecord.from_dict(raw)
            for raw in self._data["records"].values()
            if raw.get("status") == status
        ]

    def get_anomalous(self, threshold: float = 0.7) -> list[FQDNRecord]:
        """Return FQDNRecords with anomaly_score above threshold."""
        return [
            FQDNRecord.from_dict(raw)
            for raw in self._data["records"].values()
            if raw.get("anomaly_score", 0.0) >= threshold
        ]

    def get_recently_changed(self, since: datetime) -> list[FQDNRecord]:
        """Return FQDNRecords with IP changes since given time."""
        results = []
        for raw in self._data["records"].values():
            for change in raw.get("ip_history", []):
                try:
                    ts = datetime.fromisoformat(change["timestamp"])
                    if ts >= since:
                        results.append(FQDNRecord.from_dict(raw))
                        break
                except (ValueError, KeyError):
                    continue
        return results


if __name__ == "__main__":
    # Quick smoke test
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "fqdns.json"
        store = FQDNStore(store_path)

        # Create record
        rec = FQDNRecord("www.example.com")
        rec.current_ips = ["1.2.3.4", "5.6.7.8"]
        rec.cname_chain = ["example.com"]
        rec.ttl = 300
        rec.registrar = "Example Registrar"
        rec.expiry_date = "2025-12-31"
        rec.nameservers = ["ns1.example.com", "ns2.example.com"]
        rec.update_monitoring_state(True, 25.0)
        rec.update_baseline({"1.2.3.4": 0.8, "5.6.7.8": 0.2})
        rec.update_anomaly_score(0.3)
        rec.increment_flip_flop()
        rec.increment_geo_shift()

        store.set(rec)
        store.save()

        # Reload and verify
        store2 = FQDNStore(store_path)
        loaded = store2.get("www.example.com")
        assert loaded is not None
        assert loaded.fqdn == "www.example.com"
        assert loaded.domain == "example.com"
        assert loaded.current_ips == ["1.2.3.4", "5.6.7.8"]
        assert loaded.anomaly_score == 0.3
        assert loaded.flip_flop_count == 1
        assert loaded.geo_shifts == 1

        # Test queries
        assert "www.example.com" in store2.all_fqdns()
        assert len(store2.get_by_domain("example.com")) == 1
        assert len(store2.get_by_status("healthy")) == 1
        assert len(store2.get_anomalous(0.5)) == 0
        assert len(store2.get_anomalous(0.2)) == 1

        print("FQDNStore smoke test passed!")