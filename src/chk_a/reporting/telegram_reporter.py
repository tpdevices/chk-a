"""Telegram reporter for monthly and daily report summaries."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
from pydantic import SecretStr

log = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern for external API calls (SEC-012).

    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing recovery)
    Thread-safe implementation using asyncio.Lock.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """Get current state, transitioning from OPEN to HALF_OPEN if recovery timeout elapsed."""
        if self._state == "OPEN" and self._last_failure_time is not None:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                log.info("Circuit breaker transitioning from OPEN to HALF_OPEN")
                self._state = "HALF_OPEN"
                self._half_open_calls = 0
        return self._state

    def can_execute(self) -> bool:
        """Check if a call can be executed (sync, non-thread-safe)."""
        return self._can_execute_locked()

    def _can_execute_locked(self) -> bool:
        """Internal check without lock."""
        state = self.state
        if state == "CLOSED":
            return True
        if state == "HALF_OPEN":
            return self._half_open_calls < self.half_open_max_calls
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call (sync)."""
        if self._state == "HALF_OPEN":
            log.info("Circuit breaker recovered - transitioning to CLOSED")
            self._state = "CLOSED"
            self._failure_count = 0
            self._half_open_calls = 0
        elif self._state == "CLOSED":
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call (sync)."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == "HALF_OPEN":
            log.warning("Circuit breaker failure in HALF_OPEN - transitioning to OPEN")
            self._state = "OPEN"
            self._half_open_calls = 0
        elif self._state == "CLOSED" and self._failure_count >= self.failure_threshold:
            log.warning(
                "Circuit breaker threshold reached (%d failures) - transitioning to OPEN",
                self.failure_threshold,
            )
            self._state = "OPEN"

    def record_half_open_call(self) -> None:
        """Record a call made in HALF_OPEN state (sync)."""
        if self._state == "HALF_OPEN":
            self._half_open_calls += 1

    # Async variants for thread-safe concurrent usage
    async def can_execute_async(self) -> bool:
        """Check if a call can be executed (async, thread-safe)."""
        async with self._lock:
            return self._can_execute_locked()

    async def record_success_async(self) -> None:
        """Record a successful call (async, thread-safe)."""
        async with self._lock:
            self.record_success()

    async def record_failure_async(self) -> None:
        """Record a failed call (async, thread-safe)."""
        async with self._lock:
            self.record_failure()

    async def record_half_open_call_async(self) -> None:
        """Record a call made in HALF_OPEN state (async, thread-safe)."""
        async with self._lock:
            self.record_half_open_call()


class TelegramReporter:
    """Send monthly report summaries and graphs to Telegram."""

    def __init__(
        self,
        bot_token: SecretStr,
        chat_id: SecretStr,
        timeout: int = 30,
    ):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        # Token in URL path (required by Telegram Bot API) - masked in logs
        self._api_base = "https://api.telegram.org"
        self._bot_token_value = bot_token.get_secret_value()
        # Pre-compute masked token for logging
        self._masked_token = self._mask_token_for_log(self._bot_token_value)

        # SEC-012: Circuit breaker for Telegram API
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=3,
        )

        # SEC-017/perf: Single reused ClientSession for connection pooling
        self._session: aiohttp.ClientSession | None = None

    @staticmethod
    def _mask_token_for_log(token: str) -> str:
        """Return masked token for logging (first 4, last 4)."""
        if not token or len(token) < 8:
            return "***"
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"

    def _build_url(self, method: str) -> str:
        """Build API URL with token in path (required by Telegram Bot API)."""
        return f"{self._api_base}/bot{self._bot_token_value}/{method}"

    def _log_url(self, method: str) -> str:
        """Return URL with masked token for logging."""
        return f"{self._api_base}/bot{self._masked_token}/{method}"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the shared ClientSession (call on shutdown)."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def send_message(self, text: str, parse_mode: str = "HTML", chat_id: str | None = None) -> bool:
        """Send a text message to Telegram."""
        if not self._bot_token or not self._bot_token.get_secret_value():
            log.warning("Telegram configuration incomplete - skipping send")
            return False

        # SEC-012: Circuit breaker check
        if not self._circuit_breaker.can_execute():
            log.warning("Telegram circuit breaker is OPEN - skipping message send")
            return False

        target_chat_id = chat_id or (self._chat_id.get_secret_value() if self._chat_id else "")
        if not target_chat_id:
            log.warning("Telegram chat_id not configured - skipping send")
            return False

        if self._circuit_breaker.state == "HALF_OPEN":
            self._circuit_breaker.record_half_open_call()

        try:
            session = await self._get_session()
            async with session.post(
                self._build_url("sendMessage"),
                json={
                    "chat_id": target_chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            ) as resp:
                if resp.status == 200:
                    log.info("Telegram message sent successfully")
                    self._circuit_breaker.record_success()
                    return True
                else:
                    error_text = await resp.text()
                    log.error("Telegram sendMessage failed: %s - %s", resp.status, error_text)
                    self._circuit_breaker.record_failure()
                    return False
        except Exception as e:
            log.error("Failed to send Telegram message: %s", e)
            self._circuit_breaker.record_failure()
            return False

    async def send_photo(self, photo_path: Path, caption: str = "", chat_id: str | None = None, parse_mode: str = "HTML") -> bool:
        """Send a photo/graph to Telegram."""
        if not self._bot_token or not self._bot_token.get_secret_value():
            log.warning("Telegram configuration incomplete - skipping send")
            return False

        # SEC-012: Circuit breaker check
        if not self._circuit_breaker.can_execute():
            log.warning("Telegram circuit breaker is OPEN - skipping photo send")
            return False

        target_chat_id = chat_id or (self._chat_id.get_secret_value() if self._chat_id else "")
        if not target_chat_id:
            log.warning("Telegram chat_id not configured - skipping send")
            return False

        if not photo_path.is_file():
            log.warning("Photo not found: %s", photo_path)
            return False

        if self._circuit_breaker.state == "HALF_OPEN":
            self._circuit_breaker.record_half_open_call()

        try:
            session = await self._get_session()
            with photo_path.open("rb") as fh:
                data = aiohttp.FormData()
                data.add_field("chat_id", target_chat_id)
                data.add_field("photo", fh, filename=photo_path.name, content_type="image/png")
                if caption:
                    data.add_field("caption", caption)
                    data.add_field("parse_mode", parse_mode)

                async with session.post(
                    self._build_url("sendPhoto"),
                    data=data,
                ) as resp:
                    if resp.status == 200:
                        log.info("Telegram photo sent: %s", photo_path.name)
                        self._circuit_breaker.record_success()
                        return True
                    else:
                        error_text = await resp.text()
                        log.error("Telegram sendPhoto failed: %s - %s", resp.status, error_text)
                        self._circuit_breaker.record_failure()
                        return False
        except Exception as e:
            log.error("Failed to send Telegram photo: %s", e)
            self._circuit_breaker.record_failure()
            return False

    async def send_document(self, doc_path: Path, caption: str = "") -> bool:
        """Send a document (PDF) to Telegram."""
        if not self._bot_token or not self._bot_token.get_secret_value() or not self._chat_id or not self._chat_id.get_secret_value():
            log.warning("Telegram configuration incomplete - skipping send")
            return False

        # SEC-012: Circuit breaker check
        if not self._circuit_breaker.can_execute():
            log.warning("Telegram circuit breaker is OPEN - skipping document send")
            return False

        target_chat_id = self._chat_id.get_secret_value()
        if not doc_path.is_file():
            log.warning("Document not found: %s", doc_path)
            return False

        if self._circuit_breaker.state == "HALF_OPEN":
            self._circuit_breaker.record_half_open_call()

        try:
            session = await self._get_session()
            with doc_path.open("rb") as fh:
                data = aiohttp.FormData()
                data.add_field("chat_id", target_chat_id)
                data.add_field(
                    "document", fh, filename=doc_path.name, content_type="application/pdf"
                )
                if caption:
                    data.add_field("caption", caption)
                    data.add_field("parse_mode", "HTML")

                async with session.post(
                    self._build_url("sendDocument"),
                    data=data,
                ) as resp:
                    if resp.status == 200:
                        log.info("Telegram document sent: %s", doc_path.name)
                        self._circuit_breaker.record_success()
                        return True
                    else:
                        error_text = await resp.text()
                        log.error(
                            "Telegram sendDocument failed: %s - %s", resp.status, error_text
                        )
                        self._circuit_breaker.record_failure()
                        return False
        except Exception as e:
            log.error("Failed to send Telegram document: %s", e)
            self._circuit_breaker.record_failure()
            return False


def create_telegram_summary(ml_insights: dict[str, Any], lang: str = "th") -> str:
    """Create a concise Thai summary for Telegram (not full report)."""
    summary = ml_insights.get("summary", {})
    availability = ml_insights.get("availability", {})
    integrity = ml_insights.get("integrity", {})
    path_availability = ml_insights.get("path_availability", {})

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    lookback = ml_insights.get("lookback_days", 30)

    if lang == "th":
        lines = [
            "📊 <b>chk-a รายงานรายเดือน DNS Resolver</b>",
            f"📅 {timestamp} | ช่วง {lookback} วัน",
            "",
            "📈 <b>สรุปภาพรวม</b>",
            f"• Resolver ทั้งหมด: {summary.get('total_resolvers', 0)}",
            f"• Query ทั้งหมด: {summary.get('total_queries', 0):,}",
            f"• ความพร้อมใช้งานโดยรวม: {summary.get('overall_availability_pct', 0):.2f}%",
            f"• 🏆 ดีที่สุด: {summary.get('best_resolver', 'N/A')}",
            f"• ⚠️ ต้องปรับปรุง: {summary.get('worst_resolver', 'N/A')}",
            f"• 🔴 Anomaly: {len(summary.get('anomalous_resolvers', []))} ตัว",
            "",
        ]

        # Top 5 availability
        if availability:
            lines.append("📊 <b>Top 5 Availability</b>")
            sorted_avail = sorted(
                availability.items(), key=lambda x: x[1]["availability_pct"], reverse=True
            )[:5]
            for i, (resolver, data) in enumerate(sorted_avail, 1):
                pct = data["availability_pct"]
                emoji = "🟢" if pct >= 99 else "🟡" if pct >= 95 else "🔴"
                lines.append(f"{i}. {emoji} {resolver}: {pct:.2f}%")

            lines.append("")

        # Path availability section
        if path_availability:
            lines.append("🛣️ <b>Path Availability (Host→Resolver)</b>")
            sorted_path = sorted(
                path_availability.items(),
                key=lambda x: x[1]["path_availability_pct"],
                reverse=True,
            )[:5]
            for i, (resolver, data) in enumerate(sorted_path, 1):
                pct = data["path_availability_pct"]
                health = data.get("path_health_score", 0)
                emoji = "🟢" if pct >= 90 else "🟡" if pct >= 70 else "🔴"
                lines.append(f"{i}. {emoji} {resolver}: {pct:.1f}% (Health: {health:.0f})")

            lines.append("")

        # Anomalous resolvers
        anomalous = summary.get("anomalous_resolvers", [])
        if anomalous:
            lines.append("🔴 <b>Resolver 異常 (ML Detected)</b>")
            for r in anomalous[:5]:
                score = integrity.get(r, {}).get("integrity_score", 0)
                lines.append(f"• {r} (Integrity: {score:.1f})")
            lines.append("")

        lines.append("📎 ไฟล์ PDF เต็มรูปแบบ (EN/TH) ส่งทางอีเมล")
        lines.append("📈 กราฟแนบในข้อความนี้")

        return "\n".join(lines)

    else:
        lines = [
            "📊 <b>chk-a Monthly DNS Resolver Report</b>",
            f"📅 {timestamp} | Last {lookback} days",
            "",
            "📈 <b>Summary</b>",
            f"• Total Resolvers: {summary.get('total_resolvers', 0)}",
            f"• Total Queries: {summary.get('total_queries', 0):,}",
            f"• Overall Availability: {summary.get('overall_availability_pct', 0):.2f}%",
            f"• 🏆 Best: {summary.get('best_resolver', 'N/A')}",
            f"• ⚠️ Needs Improvement: {summary.get('worst_resolver', 'N/A')}",
            f"• 🔴 Anomalies: {len(summary.get('anomalous_resolvers', []))}",
            "",
        ]

        if availability:
            lines.append("📊 <b>Top 5 Availability</b>")
            sorted_avail = sorted(
                availability.items(), key=lambda x: x[1]["availability_pct"], reverse=True
            )[:5]
            for i, (resolver, data) in enumerate(sorted_avail, 1):
                pct = data["availability_pct"]
                emoji = "🟢" if pct >= 99 else "🟡" if pct >= 95 else "🔴"
                lines.append(f"{i}. {emoji} {resolver}: {pct:.2f}%")

            lines.append("")

        # Path availability section
        if path_availability:
            lines.append("🛣️ <b>Path Availability (Host→Resolver)</b>")
            sorted_path = sorted(
                path_availability.items(),
                key=lambda x: x[1]["path_availability_pct"],
                reverse=True,
            )[:5]
            for i, (resolver, data) in enumerate(sorted_path, 1):
                pct = data["path_availability_pct"]
                health = data.get("path_health_score", 0)
                emoji = "🟢" if pct >= 90 else "🟡" if pct >= 70 else "🔴"
                lines.append(f"{i}. {emoji} {resolver}: {pct:.1f}% (Health: {health:.0f})")

            lines.append("")

        anomalous = summary.get("anomalous_resolvers", [])
        if anomalous:
            lines.append("🔴 <b>Anomalous Resolvers (ML Detected)</b>")
            for r in anomalous[:5]:
                score = integrity.get(r, {}).get("integrity_score", 0)
                lines.append(f"• {r} (Integrity: {score:.1f})")
            lines.append("")

        lines.append("📎 Full PDF reports (EN/TH) sent via email")
        lines.append("📈 Graphs attached below")

        return "\n".join(lines)


async def send_monthly_report_telegram(
    bot_token: SecretStr,
    chat_id: SecretStr,
    ml_insights: dict[str, Any],
    graph_paths: list[Path],
    pdf_paths: dict[str, Path] | None = None,
    lang: str = "th",
) -> dict[str, bool]:
    """Send monthly report summary and graphs to Telegram.

    Returns dict with send results for each component.
    """
    reporter = TelegramReporter(bot_token, chat_id)
    results = {}

    try:
        tasks = []
        keys = []

        # Summary message
        summary_text = create_telegram_summary(ml_insights, lang)
        tasks.append(reporter.send_message(summary_text))
        keys.append("summary")

        # Graphs (limit to avoid spam)
        graph_limit = min(5, len(graph_paths))
        for i, graph_path in enumerate(graph_paths[:graph_limit]):
            caption = graph_path.stem.replace("-", " ").title()
            tasks.append(reporter.send_photo(graph_path, caption))
            keys.append(f"graph_{i}")

        # PDFs if provided (optional - can be large)
        if pdf_paths:
            for lang_code, pdf_path in pdf_paths.items():
                tasks.append(
                    reporter.send_document(pdf_path, f"Monthly Report ({lang_code.upper()})")
                )
                keys.append(f"pdf_{lang_code}")

        # Send all concurrently
        send_results = await asyncio.gather(*tasks, return_exceptions=True)
        for key, result in zip(keys, send_results):
            results[key] = result if isinstance(result, bool) else False
    finally:
        await reporter.close()

    return results


async def send_daily_report_telegram(
    bot_token: SecretStr,
    chat_id: SecretStr,
    ml_insights: dict[str, Any],
    graph_paths: list[Path],
    hostname: str,
    lookback_days: int = 1,
) -> dict[str, bool]:
    """Send daily report summary and graphs to Telegram (Thai, concise)."""
    reporter = TelegramReporter(bot_token, chat_id)
    results = {}

    try:
        tasks = []
        keys = []

        # Create daily summary (Thai, concise)
        summary_text = create_daily_telegram_summary(ml_insights, hostname, lookback_days)
        tasks.append(reporter.send_message(summary_text))
        keys.append("summary")

        # Graphs (limit to avoid spam)
        graph_limit = min(6, len(graph_paths))
        for i, graph_path in enumerate(graph_paths[:graph_limit]):
            caption = graph_path.stem.replace("-", " ").title()
            tasks.append(reporter.send_photo(graph_path, caption))
            keys.append(f"graph_{i}")

        # Send all concurrently
        send_results = await asyncio.gather(*tasks, return_exceptions=True)
        for key, result in zip(keys, send_results):
            results[key] = result if isinstance(result, bool) else False
    finally:
        await reporter.close()

    return results


def create_daily_telegram_summary(
    ml_insights: dict[str, Any],
    hostname: str,
    lookback_days: int = 1,
) -> str:
    """Create a concise Thai daily summary for Telegram."""
    summary = ml_insights.get("summary", {})
    availability = ml_insights.get("availability", {})
    integrity = ml_insights.get("integrity", {})
    path_availability = ml_insights.get("path_availability", {})

    # Yesterday's date
    from datetime import timedelta

    yesterday = (datetime.now() - timedelta(days=lookback_days)).strftime("%d/%m/%Y")

    lines = [
        f"📅 <b>chk-a รายงานรายวัน ({yesterday})</b>",
        f"🖥️ Host: {hostname}",
        "",
        "📈 <b>สรุป Availability / Path Availability / Integrity</b>",
        f"• Resolver ทั้งหมด: {summary.get('total_resolvers', 0)}",
        f"• Query ทั้งหมด: {summary.get('total_queries', 0):,}",
        f"• Availability โดยรวม: {summary.get('overall_availability_pct', 0):.2f}%",
        f"• 🏆 ดีที่สุด: {summary.get('best_resolver', 'N/A')}",
        f"• ⚠️ ต้องปรับปรุง: {summary.get('worst_resolver', 'N/A')}",
        f"• 🔴 Anomaly (ML): {len(summary.get('anomalous_resolvers', []))} ตัว",
        "",
    ]

    # Resolver Availability
    if availability:
        lines.append("📊 <b>Resolver Availability</b>")
        sorted_avail = sorted(
            availability.items(), key=lambda x: x[1]["availability_pct"], reverse=True
        )
        for i, (resolver, data) in enumerate(sorted_avail, 1):
            pct = data["availability_pct"]
            emoji = "🟢" if pct >= 99 else "🟡" if pct >= 95 else "🔴"
            lines.append(f"{i}. {emoji} {resolver}: {pct:.2f}%")
        lines.append("")

    # Path Availability (MTR)
    if path_availability:
        lines.append("🛣️ <b>Path Availability (MTR Host→Resolver)</b>")
        sorted_path = sorted(
            path_availability.items(),
            key=lambda x: x[1]["path_availability_pct"],
            reverse=True,
        )
        for i, (resolver, data) in enumerate(sorted_path, 1):
            pct = data["path_availability_pct"]
            health = data.get("path_health_score", 0)
            emoji = "🟢" if pct >= 90 else "🟡" if pct >= 70 else "🔴"
            lines.append(f"{i}. {emoji} {resolver}: {pct:.1f}% (Health: {health:.0f})")
        lines.append("")

    # Integrity (response consistency - baseline-based)
    if integrity:
        lines.append("🔐 <b>Response Integrity (Baseline Consistency)</b>")
        sorted_integrity = sorted(
            integrity.items(), key=lambda x: x[1].get("integrity_score", 0), reverse=True
        )
        for i, (resolver, data) in enumerate(sorted_integrity, 1):
            score = data.get("integrity_score", 0)
            success_rate = data.get("success_rate", 0)
            emoji = "🟢" if score >= 95 else "🟡" if score >= 80 else "🔴"
            lines.append(f"{i}. {emoji} {resolver}: {score:.1f} (✓{success_rate:.0f}%)")
        lines.append("")

    # Anomalous resolvers (baseline-based)
    anomalous = summary.get("anomalous_resolvers", [])
    if anomalous:
        lines.append("🔴 <b>Resolver ปัญหา Integrity (ML Detected)</b>")
        for r in anomalous[:5]:
            score = integrity.get(r, {}).get("integrity_score", 0)
            success = integrity.get(r, {}).get("success_rate", 0)
            lines.append(f"• {r} (Integrity: {score:.1f}, Success: {success:.0f}%)")
        lines.append("")

    lines.append("📈 กราฟแนบด้านล่าง (Availability / Path / Integrity / Anomaly)")

    return "\n".join(lines)


__all__ = [
    "CircuitBreaker",
    "TelegramReporter",
    "create_telegram_summary",
    "send_monthly_report_telegram",
    "send_daily_report_telegram",
    "create_daily_telegram_summary",
]
