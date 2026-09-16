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
    # Mock /etc/chk-a/env to not interfere with test
    monkeypatch.setattr("chk_a.config.loader._load_env_file", lambda: {})
    cfg = load_config(yaml_file)
    assert cfg.alert.telegram_bot_token.get_secret_value() == "TOKEN123"
    assert cfg.alert.telegram_chat_id.get_secret_value() == "-100999"


def test_env_substitution_missing_kept_verbatim(yaml_file: Path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    # Mock /etc/chk-a/env to not interfere with test
    monkeypatch.setattr("chk_a.config.loader._load_env_file", lambda: {})
    cfg = load_config(yaml_file)
    # When env var is unset, the literal "${TELEGRAM_BOT_TOKEN}" remains.
    assert cfg.alert.telegram_bot_token.get_secret_value() == "${TELEGRAM_BOT_TOKEN}"


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


def test_health_bind_address_valid_loopback(tmp_path: Path):
    """Test that valid loopback addresses are accepted for health_bind_address."""
    for addr in ["127.0.0.1", "::1", "localhost", "127.0.0.2", "127.255.255.255"]:
        p = tmp_path / f"health_{addr.replace(':', '_').replace('.', '_')}.yaml"
        p.write_text(
            f"scheduler:\n  health_bind_address: \"{addr}\"\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.scheduler.health_bind_address == addr


def test_health_bind_address_rejects_non_loopback(tmp_path: Path):
    """Test that non-loopback addresses are rejected for health_bind_address."""
    for addr in ["0.0.0.0", "192.168.1.1", "10.0.0.1", "::ffff:192.168.1.1", "example.com"]:
        p = tmp_path / f"health_{addr.replace(':', '_').replace('.', '_')}.yaml"
        p.write_text(
            f"scheduler:\n  health_bind_address: \"{addr}\"\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            load_config(p)


def test_email_enabled_requires_smtp_host(tmp_path: Path):
    """Test that smtp_host is required when email_enabled is true."""
    p = tmp_path / "email_no_host.yaml"
    p.write_text(
        "reporting:\n  email_enabled: true\n  smtp_port: 587\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="smtp_host is required"):
        load_config(p)


def test_email_enabled_requires_valid_tls_port(tmp_path: Path):
    """Test that smtp_port must be 465 or 587 when email_enabled is true."""
    # Valid ports
    for port in [465, 587]:
        p = tmp_path / f"email_port_{port}.yaml"
        p.write_text(
            f"reporting:\n  email_enabled: true\n  smtp_host: \"smtp.example.com\"\n  smtp_port: {port}\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.reporting.smtp_port == port

    # Invalid ports
    for port in [25, 2525, 8025, 588]:
        p = tmp_path / f"email_port_{port}.yaml"
        p.write_text(
            f"reporting:\n  email_enabled: true\n  smtp_host: \"smtp.example.com\"\n  smtp_port: {port}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="smtp_port must be 465"):
            load_config(p)


def test_email_disabled_allows_any_port(tmp_path: Path):
    """Test that when email_enabled is false, any port is allowed."""
    for port in [25, 587, 465, 2525, 8025]:
        p = tmp_path / f"email_disabled_port_{port}.yaml"
        p.write_text(
            f"reporting:\n  email_enabled: false\n  smtp_port: {port}\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.reporting.smtp_port == port


def test_resolver_address_valid_ip_port(tmp_path: Path):
    """Test valid IP:port resolver addresses."""
    for addr in ["8.8.8.8:53", "1.1.1.1:53", "192.168.1.1:5353", "2001:4860:4860::8888:53"]:
        p = tmp_path / f"resolver_{addr.replace(':', '_').replace('.', '_')}.yaml"
        p.write_text(
            f"resolvers:\n  - name: \"test\"\n    address: \"{addr}\"\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.resolvers[0].address == addr


def test_resolver_address_valid_doh_url(tmp_path: Path):
    """Test valid DoH URLs."""
    for url in ["https://dns.google/dns-query", "https://cloudflare-dns.com/dns-query", "http://localhost:8080/dns-query"]:
        p = tmp_path / f"resolver_doh_{url.replace(':', '_').replace('/', '_').replace('.', '_')}.yaml"
        p.write_text(
            f"resolvers:\n  - name: \"test\"\n    address: \"{url}\"\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.resolvers[0].address == url


def test_resolver_address_valid_dot_url(tmp_path: Path):
    """Test valid DoT (DNS-over-TLS) URLs."""
    for url in ["tls://dns.google:853", "tls://1.1.1.1:853", "tls://dns.quad9.net:853"]:
        p = tmp_path / f"resolver_dot_{url.replace(':', '_').replace('/', '_').replace('.', '_')}.yaml"
        p.write_text(
            f"resolvers:\n  - name: \"test\"\n    address: \"{url}\"\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.resolvers[0].address == url


def test_resolver_address_valid_hostname_port(tmp_path: Path):
    """Test valid hostname:port resolver addresses."""
    for addr in ["dns.google:53", "one.one.one.one:53", "my-resolver.example.com:5353"]:
        p = tmp_path / f"resolver_{addr.replace(':', '_').replace('.', '_')}.yaml"
        p.write_text(
            f"resolvers:\n  - name: \"test\"\n    address: \"{addr}\"\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.resolvers[0].address == addr


def test_resolver_address_rejects_invalid(tmp_path: Path):
    """Test that invalid resolver addresses are rejected."""
    invalid = [
        "",  # empty
        "8.8.8.8",  # missing port
        "not_an_ip:53",  # invalid hostname (underscore not allowed)
        "8.8.8.8:99999",  # port out of range
        "8.8.8.8:0",  # port 0
        "ftp://example.com/dns",  # invalid scheme
        "8.8.8.8:-1",  # negative port
        # Invalid DoT URLs
        "tls://",  # empty host
        "tls://example.com",  # missing port
        "tls://example.com:99999",  # port out of range
        "tls://example.com:0",  # port 0
        "tls://not_an_ip:853",  # invalid hostname
        "ssl://example.com:853",  # wrong scheme
    ]
    for addr in invalid:
        p = tmp_path / f"resolver_bad_{addr.replace(':', '_').replace('.', '_').replace('/', '_')}.yaml"
        p.write_text(
            f"resolvers:\n  - name: \"test\"\n    address: \"{addr}\"\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            load_config(p)


def test_fqdn_name_valid(tmp_path: Path):
    """Test valid FQDN names."""
    for name in ["example.com", "api.github.com", "sub.domain.example.org", "a.b.c.d.e.f.g.h"]:
        p = tmp_path / f"fqdn_{name.replace('.', '_')}.yaml"
        p.write_text(
            f"fqdns:\n  - name: \"{name}\"\n",
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.fqdns[0].name == name


def test_fqdn_name_rejects_invalid(tmp_path: Path):
    """Test that invalid FQDN names are rejected."""
    invalid = [
        ("", "empty"),
        ("example..com", "empty_label"),
        ("-example.com", "starts_hyphen"),
        ("example-.com", "ends_hyphen"),
        ("example.com-", "ends_hyphen"),
        ("exa_mple.com", "underscore"),
        ("a" * 254, "too_long"),
        ("a" * 64 + ".com", "label_too_long"),
    ]
    for name, label in invalid:
        p = tmp_path / f"fqdn_bad_{label}.yaml"
        p.write_text(
            f"fqdns:\n  - name: \"{name}\"\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            load_config(p)


def test_fqdn_expected_ips_valid(tmp_path: Path):
    """Test valid expected IPs."""
    p = tmp_path / "fqdn_ips.yaml"
    p.write_text(
        "fqdns:\n  - name: \"example.com\"\n    expected_ips: [\"93.184.216.34\", \"2001:db8::1\", \"192.168.1.1\"]\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.fqdns[0].expected_ips == ["93.184.216.34", "2001:db8::1", "192.168.1.1"]


def test_fqdn_expected_ips_rejects_invalid(tmp_path: Path):
    """Test that invalid expected IPs are rejected."""
    invalid_ips = ["not-an-ip", "999.999.999.999", "2001:db8::gggg", "", "192.168.1.256"]
    for ip in invalid_ips:
        p = tmp_path / f"fqdn_bad_ip_{ip.replace(':', '_').replace('.', '_')}.yaml"
        p.write_text(
            f"fqdns:\n  - name: \"example.com\"\n    expected_ips: [\"{ip}\"]\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            load_config(p)


def test_mtr_resolvers_subset_valid(tmp_path: Path):
    """Test that MTR resolvers subset validation passes for valid subset."""
    p = tmp_path / "mtr_valid.yaml"
    p.write_text(
        "resolvers:\n  - name: \"google\"\n    address: \"8.8.8.8:53\"\n  - name: \"cloudflare\"\n    address: \"1.1.1.1:53\"\nmtr:\n  enabled: true\n  resolvers: [\"google\", \"cloudflare\"]\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.mtr.resolvers == ["google", "cloudflare"]


def test_mtr_resolvers_subset_empty_allowed(tmp_path: Path):
    """Test that empty MTR resolvers list is allowed (means all)."""
    p = tmp_path / "mtr_empty.yaml"
    p.write_text(
        "resolvers:\n  - name: \"google\"\n    address: \"8.8.8.8:53\"\nmtr:\n  enabled: true\n  resolvers: []\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.mtr.resolvers == []


def test_mtr_resolvers_subset_rejects_missing(tmp_path: Path):
    """Test that MTR resolvers not in resolvers list are rejected."""
    p = tmp_path / "mtr_missing.yaml"
    p.write_text(
        "resolvers:\n  - name: \"google\"\n    address: \"8.8.8.8:53\"\nmtr:\n  enabled: true\n  resolvers: [\"google\", \"nonexistent\"]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="MTR resolvers contains names not in resolvers list"):
        load_config(p)
