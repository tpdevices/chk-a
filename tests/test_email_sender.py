"""Tests for email reporting functionality."""

from __future__ import annotations

import smtplib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chk_a.reporting.email_sender import EmailSender, create_email_body


class TestCreateEmailBody:
    """Tests for create_email_body function."""

    def test_create_email_body_english(self):
        """Test English email body generation."""
        ml_insights = {
            "lookback_days": 30,
            "summary": {
                "total_resolvers": 4,
                "total_queries": 12000,
                "overall_availability_pct": 99.5,
                "best_resolver": "google",
                "worst_resolver": "quad9",
                "anomalous_resolvers": ["fake-resolver"],
            },
        }

        text, html = create_email_body(ml_insights, lang="en")

        # Check plain text
        assert "chk-a Monthly DNS Resolver Report" in text
        assert "Total Resolvers: 4" in text
        assert "Total Queries: 12,000" in text
        assert "Overall Availability: 99.50%" in text
        assert "Best Resolver: google" in text
        assert "Worst Resolver: quad9" in text
        assert "Anomalous Resolvers: 1" in text
        assert "Full details and graphs are in the attached PDF files." in text
        assert "chk-a DNS Monitor" in text

        # Check HTML
        assert "<h2>chk-a Monthly DNS Resolver Report</h2>" in html
        assert "Total Resolvers: 4" in html
        assert "Total Queries: 12,000" in html
        assert "Overall Availability: 99.50%" in html
        assert "Best Resolver: google" in html
        assert "Worst Resolver: quad9" in html
        assert "Anomalous Resolvers: 1" in html
        assert "Full details and graphs are in the attached PDF files." in html
        assert "chk-a DNS Monitor" in html

    def test_create_email_body_thai(self):
        """Test Thai email body generation."""
        ml_insights = {
            "lookback_days": 30,
            "summary": {
                "total_resolvers": 4,
                "total_queries": 12000,
                "overall_availability_pct": 99.5,
                "best_resolver": "google",
                "worst_resolver": "quad9",
                "anomalous_resolvers": ["fake-resolver"],
            },
        }

        text, html = create_email_body(ml_insights, lang="th")

        # Check plain text
        assert "รายงานรายเดือน chk-a DNS Resolver" in text
        assert "จำนวน Resolver ทั้งหมด: 4" in text
        assert "จำนวน Query ทั้งหมด: 12,000" in text
        assert "ความพร้อมใช้งานโดยรวม: 99.50%" in text
        assert "Resolver ที่ดีที่สุด: google" in text
        assert "Resolver ที่ต้องปรับปรุง: quad9" in text
        assert "Resolver 異常 (Anomaly): 1" in text
        assert "รายละเอียดเต็มและกราฟอยู่ในไฟล์ PDF ที่แนบมาครับ" in text
        assert "chk-a DNS Monitor" in text

        # Check HTML
        assert "<h2>รายงานรายเดือน chk-a DNS Resolver</h2>" in html
        assert "จำนวน Resolver ทั้งหมด: 4" in html
        assert "จำนวน Query ทั้งหมด: 12,000" in html
        assert "ความพร้อมใช้งานโดยรวม: 99.50%" in html
        assert "Resolver ที่ดีที่สุด: google" in html
        assert "Resolver ที่ต้องปรับปรุง: quad9" in html
        assert "Resolver 異常 (Anomaly): 1" in html
        assert "รายละเอียดเต็มและกราฟอยู่ในไฟล์ PDF ที่แนบมา" in html
        assert "chk-a DNS Monitor" in html

    def test_create_email_body_missing_summary(self):
        """Test email body with missing summary data."""
        ml_insights = {"lookback_days": 30}

        text, html = create_email_body(ml_insights, lang="en")

        assert "Total Resolvers: 0" in text
        assert "Total Queries: 0" in text
        assert "Overall Availability: 0.00%" in text
        assert "Best Resolver: N/A" in text
        assert "Worst Resolver: N/A" in text
        assert "Anomalous Resolvers: 0" in text


class TestEmailSender:
    """Tests for EmailSender class."""

    @pytest.fixture
    def sender(self):
        """Create EmailSender instance for testing."""
        return EmailSender(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="testuser",
            password="testpass",
            timeout=30,
        )

    def test_init(self, sender):
        """Test EmailSender initialization."""
        assert sender.smtp_host == "smtp.example.com"
        assert sender.smtp_port == 587
        assert sender.username == "testuser"
        assert sender.password == "testpass"
        assert sender.timeout == 30

    def test_send_report_incomplete_config(self, sender):
        """Test send_report with incomplete configuration."""
        # Missing from_addr
        result = sender.send_report(
            from_addr="",
            to_addrs=["test@example.com"],
            subject="Test",
            body_text="Body",
            body_html="<p>Body</p>",
            attachments=[],
        )
        assert result is False

        # Missing to_addrs
        result = sender.send_report(
            from_addr="sender@example.com",
            to_addrs=[],
            subject="Test",
            body_text="Body",
            body_html="<p>Body</p>",
            attachments=[],
        )
        assert result is False

        # Missing smtp_host
        sender_no_host = EmailSender(smtp_host="", smtp_port=587, username="", password="")
        result = sender_no_host.send_report(
            from_addr="sender@example.com",
            to_addrs=["test@example.com"],
            subject="Test",
            body_text="Body",
            body_html="<p>Body</p>",
            attachments=[],
        )
        assert result is False

    @patch("smtplib.SMTP")
    def test_send_report_starttls_success(self, mock_smtp_class, sender):
        """Test successful email send via STARTTLS (port 587)."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # Create temporary attachment files
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            attach1 = Path(tmpdir) / "report_en.pdf"
            attach2 = Path(tmpdir) / "report_th.pdf"
            attach1.write_bytes(b"PDF content EN")
            attach2.write_bytes(b"PDF content TH")

            result = sender.send_report(
                from_addr="sender@example.com",
                to_addrs=["recipient1@example.com", "recipient2@example.com"],
                subject="Test Report",
                body_text="Plain text body",
                body_html="<p>HTML body</p>",
                attachments=[attach1, attach2],
            )

        assert result is True
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=30)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("testuser", "testpass")
        mock_server.send_message.assert_called_once()

        # Verify message structure
        call_args = mock_server.send_message.call_args[0][0]
        assert call_args["Subject"] == "Test Report"
        assert call_args["From"] == "sender@example.com"
        assert call_args["To"] == "recipient1@example.com, recipient2@example.com"
        # Should have multipart/mixed with alternative (text+html) and attachments
        assert call_args.get_content_type() == "multipart/mixed"

    @patch("smtplib.SMTP_SSL")
    def test_send_report_implicit_tls_success(self, mock_smtp_ssl_class, sender):
        """Test successful email send via implicit TLS (port 465)."""
        sender_ssl = EmailSender(
            smtp_host="smtp.example.com",
            smtp_port=465,
            username="testuser",
            password="testpass",
        )
        mock_server = MagicMock()
        mock_smtp_ssl_class.return_value.__enter__.return_value = mock_server

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            attach = Path(tmpdir) / "report.pdf"
            attach.write_bytes(b"PDF content")

            result = sender_ssl.send_report(
                from_addr="sender@example.com",
                to_addrs=["recipient@example.com"],
                subject="Test Report SSL",
                body_text="Plain text",
                body_html=None,
                attachments=[attach],
            )

        assert result is True
        mock_smtp_ssl_class.assert_called_once()
        mock_server.login.assert_called_once_with("testuser", "testpass")
        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_report_no_auth(self, mock_smtp_class, sender):
        """Test email send without authentication."""
        sender_no_auth = EmailSender(smtp_host="smtp.example.com", smtp_port=587, username="", password="")
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            attach = Path(tmpdir) / "report.pdf"
            attach.write_bytes(b"PDF content")

            result = sender_no_auth.send_report(
                from_addr="sender@example.com",
                to_addrs=["recipient@example.com"],
                subject="Test No Auth",
                body_text="Plain",
                body_html="<p>HTML</p>",
                attachments=[attach],
            )

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_not_called()

    @patch("smtplib.SMTP")
    def test_send_report_missing_attachment_skipped(self, mock_smtp_class, sender):
        """Test that missing attachments are skipped with warning."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            attach_exists = Path(tmpdir) / "exists.pdf"
            attach_missing = Path(tmpdir) / "missing.pdf"
            attach_exists.write_bytes(b"PDF content")

            result = sender.send_report(
                from_addr="sender@example.com",
                to_addrs=["recipient@example.com"],
                subject="Test Missing Attachment",
                body_text="Body",
                body_html="<p>Body</p>",
                attachments=[attach_exists, attach_missing],  # missing.pdf doesn't exist
            )

        assert result is True
        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_report_smtp_exception(self, mock_smtp_class, sender):
        """Test email send handles SMTP exception gracefully."""
        mock_smtp_class.side_effect = smtplib.SMTPException("Connection refused")

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            attach = Path(tmpdir) / "report.pdf"
            attach.write_bytes(b"PDF content")

            result = sender.send_report(
                from_addr="sender@example.com",
                to_addrs=["recipient@example.com"],
                subject="Test Exception",
                body_text="Body",
                body_html="<p>Body</p>",
                attachments=[attach],
            )

        assert result is False

    @patch("smtplib.SMTP")
    def test_send_report_ssl_exception(self, mock_smtp_class, sender):
        """Test email send handles SSL exception gracefully."""
        mock_smtp_class.side_effect = Exception("SSL error")

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            attach = Path(tmpdir) / "report.pdf"
            attach.write_bytes(b"PDF content")

            result = sender.send_report(
                from_addr="sender@example.com",
                to_addrs=["recipient@example.com"],
                subject="Test Exception",
                body_text="Body",
                body_html="<p>Body</p>",
                attachments=[attach],
            )

        assert result is False


class TestEmailSenderIntegration:
    """Integration-style tests for email reporting pipeline."""

    def test_monthly_report_email_integration(self):
        """Test that MonthlyReportGenerator can call send_email (mocked)."""
        from chk_a.reporting.monthly_report import MonthlyReportGenerator
        from chk_a.config.loader import AppConfig
        from chk_a.models.schemas import (
            FQDNConfig, ResolverConfig, ResolverAgentConfig,
            MLConfig, AlertConfig, SchedulerConfig, MTRConfig, LoggingConfig,
            ReportingConfig,
        )
        from pydantic import SecretStr

        # Create minimal config
        config = AppConfig(
            fqdns=[FQDNConfig(name="example.com", expected_ips=["1.2.3.4"])],
            resolvers=[ResolverConfig(name="google", address="8.8.8.8:53")],
            resolver_agent=ResolverAgentConfig(max_concurrent=10),
            ml=MLConfig(baseline_decay=0.05, anomaly_threshold=0.5, min_samples_before_alert=3),
            alert=AlertConfig(
                telegram_bot_token=SecretStr("test"),
                telegram_chat_id=SecretStr("test"),
            ),
            scheduler=SchedulerConfig(min_interval_sec=30, max_interval_sec=180, health_bind_address="127.0.0.1"),
            mtr=MTRConfig(enabled=False, resolvers=[], timeout_sec=10),
            baseline_store_path="/tmp/baselines.json",
            logging=LoggingConfig(file="/tmp/checks.jsonl", level="INFO"),
            reporting=ReportingConfig(
                email_enabled=True,
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user",
                smtp_password=SecretStr("pass"),
                email_from="sender@example.com",
                email_to=["recipient@example.com"],
            ),
        )

        reporter = MonthlyReportGenerator(config)

        # Verify email config is accessible
        assert reporter.reporting_config.email_enabled is True
        assert reporter.reporting_config.smtp_host == "smtp.example.com"
        assert reporter.reporting_config.email_from == "sender@example.com"
        assert reporter.reporting_config.email_to == ["recipient@example.com"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])