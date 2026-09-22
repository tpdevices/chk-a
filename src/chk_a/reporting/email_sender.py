"""Email sender for monthly reports via SMTP."""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from pydantic import SecretStr

log = logging.getLogger(__name__)


class EmailSender:
    """Send monthly reports via SMTP with attachments."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str | SecretStr,
        timeout: int = 30,
        ssl_context: ssl.SSLContext | None = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password.get_secret_value() if isinstance(password, SecretStr) else password
        self.timeout = timeout
        self.ssl_context = ssl_context or ssl.create_default_context()

    def send_report(
        self,
        from_addr: str,
        to_addrs: list[str],
        subject: str,
        body_text: str,
        body_html: str | None,
        attachments: list[Path],
    ) -> bool:
        """Send email with report attachments.

        Returns True on success, False on failure.
        """
        if not self.smtp_host or not from_addr or not to_addrs:
            log.warning("Email configuration incomplete - skipping send")
            return False

        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

            # Create alternative part for text/html
            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(body_text, "plain", "utf-8"))
            if body_html:
                alt_part.attach(MIMEText(body_html, "html", "utf-8"))
            msg.attach(alt_part)

            # Attach files
            for attach_path in attachments:
                if not attach_path.is_file():
                    log.warning("Attachment not found: %s", attach_path)
                    continue
                with attach_path.open("rb") as fh:
                    part = MIMEApplication(fh.read(), Name=attach_path.name)
                part["Content-Disposition"] = f'attachment; filename="{attach_path.name}"'
                msg.attach(part)

            # Send
            context = self.ssl_context
            if self.smtp_port == 465:
                # Implicit TLS (SMTPS)
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context, timeout=self.timeout) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                # STARTTLS on port 587 (or other)
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout) as server:
                    server.starttls(context=context)
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg)

            log.info("Email sent successfully to %s", ", ".join(to_addrs))
            return True

        except Exception as e:
            log.error("Failed to send email: %s", e)
            return False


def create_email_body(ml_insights: dict[str, Any], lang: str = "en") -> tuple[str, str]:
    """Create plain text and HTML email bodies."""
    summary = ml_insights.get("summary", {})
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if lang == "th":
        text = f"""รายงานรายเดือน chk-a DNS Resolver
สร้างเมื่อ: {timestamp}
ช่วงเวลา: {ml_insights.get('lookback_days', 30)} วันที่ผ่านมา

=== สรุป ===
จำนวน Resolver ทั้งหมด: {summary.get('total_resolvers', 0)}
จำนวน Query ทั้งหมด: {summary.get('total_queries', 0):,}
ความพร้อมใช้งานโดยรวม: {summary.get('overall_availability_pct', 0):.2f}%
Resolver ที่ดีที่สุด: {summary.get('best_resolver', 'N/A')}
Resolver ที่ต้องปรับปรุง: {summary.get('worst_resolver', 'N/A')}
Resolver 異常 (Anomaly): {len(summary.get('anomalous_resolvers', []))}

รายละเอียดเต็มและกราฟอยู่ในไฟล์ PDF ที่แนบมาครับ

---
chk-a DNS Monitor
"""
        html = f"""<html><body>
<h2>รายงานรายเดือน chk-a DNS Resolver</h2>
<p>สร้างเมื่อ: {timestamp}<br>
ช่วงเวลา: {ml_insights.get('lookback_days', 30)} วันที่ผ่านมา</p>

<h3>สรุป</h3>
<ul>
<li>จำนวน Resolver ทั้งหมด: {summary.get('total_resolvers', 0)}</li>
<li>จำนวน Query ทั้งหมด: {summary.get('total_queries', 0):,}</li>
<li>ความพร้อมใช้งานโดยรวม: {summary.get('overall_availability_pct', 0):.2f}%</li>
<li>Resolver ที่ดีที่สุด: {summary.get('best_resolver', 'N/A')}</li>
<li>Resolver ที่ต้องปรับปรุง: {summary.get('worst_resolver', 'N/A')}</li>
<li>Resolver 異常 (Anomaly): {len(summary.get('anomalous_resolvers', []))}</li>
</ul>

<p>รายละเอียดเต็มและกราฟอยู่ในไฟล์ PDF ที่แนบมา</p>
<hr>
<p><small>chk-a DNS Monitor</small></p>
</body></html>"""
    else:
        text = f"""chk-a Monthly DNS Resolver Report
Generated: {timestamp}
Period: Last {ml_insights.get('lookback_days', 30)} days

=== Summary ===
Total Resolvers: {summary.get('total_resolvers', 0)}
Total Queries: {summary.get('total_queries', 0):,}
Overall Availability: {summary.get('overall_availability_pct', 0):.2f}%
Best Resolver: {summary.get('best_resolver', 'N/A')}
Worst Resolver: {summary.get('worst_resolver', 'N/A')}
Anomalous Resolvers: {len(summary.get('anomalous_resolvers', []))}

Full details and graphs are in the attached PDF files.

---
chk-a DNS Monitor
"""
        html = f"""<html><body>
<h2>chk-a Monthly DNS Resolver Report</h2>
<p>Generated: {timestamp}<br>
Period: Last {ml_insights.get('lookback_days', 30)} days</p>

<h3>Summary</h3>
<ul>
<li>Total Resolvers: {summary.get('total_resolvers', 0)}</li>
<li>Total Queries: {summary.get('total_queries', 0):,}</li>
<li>Overall Availability: {summary.get('overall_availability_pct', 0):.2f}%</li>
<li>Best Resolver: {summary.get('best_resolver', 'N/A')}</li>
<li>Worst Resolver: {summary.get('worst_resolver', 'N/A')}</li>
<li>Anomalous Resolvers: {len(summary.get('anomalous_resolvers', []))}</li>
</ul>

<p>Full details and graphs are in the attached PDF files.</p>
<hr>
<p><small>chk-a DNS Monitor</small></p>
</body></html>"""

    return text, html
