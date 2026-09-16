"""Alert Agent — deduplication, rate limiting, Telegram formatting, JSONL + plain text log (Loop 4).

``maybe_alert`` decides whether an :class:`AnomalyEvent` should actually be sent:

  * **Deduplication** — identical events (same FQDN + type + observed IPs) within
    ``dedup_window_minutes`` are suppressed (in-memory cache, no Redis needed).
    LRU eviction with max size and TTL prevents unbounded memory growth.
  * **Rate limiting** — a token bucket refilled at ``rate_limit_per_hour`` tokens
    per hour; when empty the alert is dropped with a warning.
  * **Formatting** — an HTML message per the Loop 4 spec, sent via the
    :class:`TelegramClient`. Includes hostname and resolver name.
  * **Audit log (JSONL)** — every sent alert is appended as one JSON line to an optional
    JSONL file (atomic append + fsync).
  * **Plain text log** — every sent alert is appended as a plain text line with:
    date, time, hostname, resolver, ip, event. Newlines/tabs escaped to prevent log injection.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import logging.handlers
import os
import platform
import tempfile
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from ..models.schemas import AlertConfig, AnomalyEvent
from ..utils.logger import setup_logger


def _html_escape(value: Any) -> str:
    """HTML escape a value for safe inclusion in Telegram HTML messages."""
    if value is None:
        return "N/A"
    return html.escape(str(value))


def _format_html(event: AnomalyEvent) -> str:
    """Render the anomaly as HTML with Majority vs Outliers view."""
    d = event.details
    all_results = d.get("all_results", [])
    majority_ips = d.get("majority_ips", [])
    baseline_ips = d.get("baseline_ips", [])
    consensus = d.get("consensus_score", 0.0)
    resolver_count = d.get("resolver_count", 0)
    hostname = _html_escape(event.hostname or platform.node())

    # Severity emoji & label
    severity_map = {
        "critical": ("🔴", "CRITICAL"),
        "warning": ("🟡", "WARNING"),
        "info": ("🔵", "INFO"),
    }
    sev_emoji, sev_label = severity_map.get(event.severity, ("⚪", event.severity.upper()))

    # Type label (human-friendly)
    type_map = {
        "baseline_deviation": "📊 Baseline Deviation",
        "consensus_deviation": "🗳️ Consensus Deviation",
        "new_ip": "🆕 New IP Detected",
        "nxdomain": "🚫 NXDOMAIN",
        "recovery": "✅ Recovery",
        "hourly_reminder": "⏰ Hourly Reminder",
    }
    type_label = type_map.get(event.type, _html_escape(event.type))

    # Header based on event type
    if event.type == "recovery":
        header = "<b>✅ DNS Recovery Detected</b>"
    elif event.type == "hourly_reminder":
        header = "<b>⏰ Anomaly Hourly Reminder</b>"
    else:
        header = "<b>⚠️ DNS Anomaly Detected</b>"

    lines = [
        header,
        f"<b>Type:</b> {type_label} (<code>{_html_escape(event.type)}</code>)",
        f"<b>Severity:</b> {sev_emoji} {sev_label}",
        f"<b>FQDN:</b> <code>{_html_escape(event.fqdn)}</code>",
        f"<b>Host:</b> <code>{hostname}</code>",
    ]

    # Event ID
    event_id = event.event_id or d.get("event_id", "")
    if event_id:
        lines.append(f"<b>🆔 Event ID:</b> <code>{_html_escape(event_id)}</code>")

    # Handle recovery event specially
    if event.type == "recovery":
        original_type = _html_escape(d.get("original_anomaly_type", "unknown"))
        start_time = _html_escape(d.get("anomaly_start_time", "unknown"))
        end_time = _html_escape(d.get("anomaly_end_time", "unknown"))
        duration_human = _html_escape(d.get("duration_human", "unknown"))
        duration_seconds = d.get("duration_seconds", 0)
        ml_stability = d.get("ml_baseline_stability", 0.0)
        ml_confidence = d.get("ml_recovery_confidence", 0.0)

        lines.append(f"<b>🔄 Original Anomaly:</b> {original_type}")
        lines.append(f"<b>⏱️ Duration:</b> {duration_human} ({duration_seconds:.1f} วินาที)")
        lines.append(f"<b>🕐 Started:</b> <code>{start_time}</code>")
        lines.append(f"<b>🕐 Resolved:</b> <code>{end_time}</code>")
        lines.append(f"<b>📈 ML Baseline Stability:</b> {ml_stability:.2%}")
        lines.append(f"<b>🎯 ML Recovery Confidence:</b> {ml_confidence:.2%}")

        # Current observed IPs
        observed = d.get("observed_ips", [])
        if observed:
            lines.append(f"<b>✅ Current IPs:</b> {', '.join(f'<code>{_html_escape(ip)}</code>' for ip in observed)}")

        # Baseline comparison
        baseline = d.get("baseline_ips", [])
        if baseline:
            lines.append(f"<b>📋 Baseline IPs:</b> {', '.join(f'<code>{_html_escape(ip)}</code>' for ip in baseline)}")

        lines.extend([
            f"<b>Consensus:</b> {consensus:.2%}",
            f"<b>Resolvers:</b> {resolver_count} checked",
            f"<b>Time:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ])
        return "\n".join(lines)

    # Handle hourly reminder event specially
    if event.type == "hourly_reminder":
        original_type = _html_escape(d.get("original_anomaly_type", "unknown"))
        start_time = _html_escape(d.get("anomaly_start_time", "unknown"))
        reminder_time = _html_escape(d.get("reminder_time", "unknown"))
        duration_human = _html_escape(d.get("duration_human", "unknown"))
        duration_seconds = d.get("duration_seconds", 0)
        reminder_count = d.get("reminder_count", 0)
        is_first = d.get("is_first_reminder", False)
        config_changed = d.get("config_changed", False)
        baseline_changes = d.get("baseline_changes", [])

        reminder_label = "ครั้งแรก" if is_first else f"ครั้งที่ {reminder_count}"
        lines.append(f"<b>🔄 Original Anomaly:</b> {original_type}")
        lines.append(f"<b>⏰ Reminder:</b> {reminder_label} (ทุก 1 ชม.)")
        lines.append(f"<b>⏱️ Duration:</b> {duration_human} ({duration_seconds:.1f} วินาที)")
        lines.append(f"<b>🕐 Started:</b> <code>{start_time}</code>")
        lines.append(f"<b>🕐 Reminder Sent:</b> <code>{reminder_time}</code>")

        if config_changed and baseline_changes:
            lines.append(f"<b>⚙️ Config Changed:</b> {'; '.join(_html_escape(c) for c in baseline_changes)}")

        # Current observed IPs
        observed = d.get("observed_ips", [])
        if observed:
            lines.append(f"<b>📍 Current Observed IPs:</b> {', '.join(f'<code>{_html_escape(ip)}</code>' for ip in observed)}")

        # Baseline comparison
        baseline = d.get("baseline_ips", [])
        if baseline:
            lines.append(f"<b>📋 Current Baseline IPs:</b> {', '.join(f'<code>{_html_escape(ip)}</code>' for ip in baseline)}")

        lines.extend([
            f"<b>Consensus:</b> {consensus:.2%}",
            f"<b>Resolvers:</b> {resolver_count} checked",
            f"<b>Time:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ])
        return "\n".join(lines)

    # Successful resolvers grouped by IP set
    successful = [r for r in all_results if r.get("success") and r.get("ips")]
    if successful:
        # Group by IP tuple
        ip_groups: dict[tuple, list[str]] = {}
        for r in successful:
            key = tuple(sorted(r["ips"]))
            ip_groups.setdefault(key, []).append(r["resolver"])

        for ips, resolvers in ip_groups.items():
            is_majority = list(ips) == majority_ips
            prefix = "✅" if is_majority else "⚠️"
            label = "Majority" if is_majority else "Alternative"
            lines.append(f"<b>{prefix} {label} ({len(resolvers)}/{len(all_results)}):</b>")
            lines.append(f"  <b>IPs:</b> {', '.join(f'<code>{_html_escape(ip)}</code>' for ip in ips)}")
            lines.append(f"  <b>Resolvers:</b> {', '.join(f'<code>{_html_escape(r)}</code>' for r in resolvers)}")

    # Outliers / Failed
    failed = [r for r in all_results if not r.get("success")]
    majority_set = set(majority_ips)
    outliers_ips = [
        r
        for r in all_results
        if r.get("success") and r.get("ips") and not (set(r["ips"]) & majority_set)
    ]

    if outliers_ips:
        lines.append("<b>❌ Outliers:</b>")
        for r in outliers_ips:
            lines.append(
                f"  ❌ <code>{_html_escape(r['resolver'])}</code>: "
                f"{', '.join(f'<code>{_html_escape(ip)}</code>' for ip in r['ips'])}  ← DIFFERENT!"
            )

    if failed:
        lines.append("<b>❌ Failed / No Response:</b>")
        for r in failed:
            err = _html_escape(r.get("error") or "timeout")
            lines.append(f"  ❌ <code>{_html_escape(r['resolver'])}</code>: <i>{err}</i>")

    # Baseline comparison for baseline_deviation
    if event.type == "baseline_deviation" and baseline_ips:
        lines.append(
            f"<b>Baseline IPs:</b> {', '.join(f'<code>{_html_escape(ip)}</code>' for ip in baseline_ips)}"
        )

    # MTR path analysis for anomalies
    if event.type in ("baseline_deviation", "consensus_deviation") and d.get("mtr_results"):
        lines.append("<b>🛣️ MTR Path Analysis:</b>")
        for mtr in d.get("mtr_results", []):
            resolver_name = _html_escape(mtr.get("resolver_name", "unknown"))
            last_hop = _html_escape(mtr.get("last_hop_ip")) if mtr.get("last_hop_ip") else None
            problem_hops = mtr.get("problem_hops", 0)
            hop_count = mtr.get("hop_count", 0)

            lines.append(f"  <b>{resolver_name}:</b>")
            if last_hop:
                lines.append(f"    <b>Last Hop IP:</b> <code>{last_hop}</code>")
            lines.append(f"    <b>Problem Hops:</b> {problem_hops} / {hop_count} hops")
            if problem_hops > 0:
                lines.append(f"    <b>⚠️ Path issues detected</b> — potential bottleneck at <code>{last_hop}</code>")
            else:
                lines.append(f"    <b>✅ Path clean</b> — anomaly likely at destination")

    lines.extend(
        [
            f"<b>Consensus:</b> {consensus:.2%}",
            f"<b>Resolvers:</b> {resolver_count} checked",
            f"<b>Time:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
    )
    return "\n".join(lines)


class AlertAgent:
    """Decides when to send an anomaly alert and how to format/deliver it."""

    def __init__(
        self,
        config: AlertConfig,
        logger: Any,
        telegram_client: Any,
        alert_log_path: str | None = None,
        alert_text_log_path: str | None = None,
        hostname: str | None = None,
        # Image paths for anomaly/recovery notifications
        anomaly_image_path: str = "img/priority.jpg",
        recovery_image_path: str = "img/ok.jpg",
    ) -> None:
        self.config = config
        self.logger = logger or setup_logger("chk_a.alert")
        self.telegram = telegram_client
        self.alert_log_path = alert_log_path or config.alert_log_path
        self.alert_text_log_path = alert_text_log_path or config.alert_text_log_path
        self.hostname = hostname or platform.node()
        # Image paths for anomaly/recovery notifications
        self.anomaly_image_path = Path(anomaly_image_path)
        self.recovery_image_path = Path(recovery_image_path)
        # Dedup cache: LRU OrderedDict with max size and TTL.
        # Key: (fqdn, type, frozenset(ips)), Value: timestamp
        self._dedup: OrderedDict[tuple, float] = OrderedDict()
        # Max cache size (prevents unbounded memory growth)
        self._dedup_max_size = config.dedup_max_size if hasattr(config, 'dedup_max_size') and config.dedup_max_size else 10000
        # TTL in seconds (uses dedup_window_minutes from config)
        self._dedup_ttl = self.config.dedup_window_minutes * 60
        # Persistent dedup cache path (optional)
        self.dedup_cache_path = Path(config.dedup_cache_path) if config.dedup_cache_path else None
        # Token bucket (tokens refilled at rate_limit_per_hour per hour).
        self._capacity = float(config.rate_limit_per_hour)
        self._tokens = self._capacity
        self._last_refill = time.monotonic()

        # Set up rotating file handlers for alert logs
        self._alert_jsonl_handler = None
        self._alert_text_handler = None
        self._setup_alert_log_handlers()

        # Load persistent cache if configured
        if self.dedup_cache_path:
            self._load_dedup_cache()

        # Concurrency locks for thread-safe operations
        self._dedup_lock = asyncio.Lock()
        self._rate_limit_lock = asyncio.Lock()

    def _setup_alert_log_handlers(self) -> None:
        """Set up rotating file handlers for JSONL and plain text alert logs."""
        # JSONL handler
        if self.alert_log_path:
            log_path = Path(self.alert_log_path)
            # Create directory with proper permissions
            log_path.parent.mkdir(parents=True, exist_ok=True, mode=self.config.dir_mode if hasattr(self.config, 'dir_mode') else 0o750)
            # Set directory permissions if it already existed
            try:
                os.chmod(log_path.parent, self.config.dir_mode if hasattr(self.config, 'dir_mode') else 0o750)
            except (OSError, PermissionError):
                pass  # Ignore permission errors
            self._alert_jsonl_handler = logging.handlers.RotatingFileHandler(
                self.alert_log_path,
                maxBytes=self.config.alert_log_max_size_mb * 1024 * 1024,
                backupCount=self.config.alert_log_backup_count,
                encoding="utf-8",
            )
            self._alert_jsonl_handler.setFormatter(logging.Formatter("%(message)s"))
            # Set file permissions
            try:
                os.chmod(self.alert_log_path, self.config.file_mode if hasattr(self.config, 'file_mode') else 0o640)
            except (OSError, PermissionError):
                pass

        # Plain text handler
        if self.alert_text_log_path:
            log_path = Path(self.alert_text_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True, mode=self.config.dir_mode if hasattr(self.config, 'dir_mode') else 0o750)
            try:
                os.chmod(log_path.parent, self.config.dir_mode if hasattr(self.config, 'dir_mode') else 0o750)
            except (OSError, PermissionError):
                pass
            self._alert_text_handler = logging.handlers.RotatingFileHandler(
                self.alert_text_log_path,
                maxBytes=self.config.alert_log_max_size_mb * 1024 * 1024,
                backupCount=self.config.alert_log_backup_count,
                encoding="utf-8",
            )
            self._alert_text_handler.setFormatter(logging.Formatter("%(message)s"))
            try:
                os.chmod(self.alert_text_log_path, self.config.file_mode if hasattr(self.config, 'file_mode') else 0o640)
            except (OSError, PermissionError):
                pass

    def _load_dedup_cache(self) -> None:
        """Load dedup cache from disk (JSON)."""
        if not self.dedup_cache_path or not self.dedup_cache_path.exists():
            return
        try:
            with open(self.dedup_cache_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            # Convert list keys back to tuples with frozenset
            for key_str, timestamp in raw.items():
                # key_str format: "fqdn|type|ip1,ip2,..."
                parts = key_str.split("|", 2)
                if len(parts) == 3:
                    fqdn, type_, ips_str = parts
                    ips = frozenset(ips_str.split(",")) if ips_str else frozenset()
                    self._dedup[(fqdn, type_, ips)] = float(timestamp)
            self.logger.info(
                "Loaded dedup cache: %d entries from %s", len(self._dedup), self.dedup_cache_path
            )
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            self.logger.warning(
                "Could not load dedup cache from %s: %s", self.dedup_cache_path, exc
            )
            self._dedup = {}

    def _save_dedup_cache(self) -> None:
        """Atomically persist dedup cache to disk (JSON)."""
        if not self.dedup_cache_path:
            return
        try:
            self.dedup_cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Convert tuple keys to strings for JSON serialization
            raw = {}
            for (fqdn, type_, ips), timestamp in self._dedup.items():
                key_str = f"{fqdn}|{type_}|{','.join(sorted(ips))}"
                raw[key_str] = timestamp
            tmp_fd, tmp_name = tempfile.mkstemp(
                dir=str(self.dedup_cache_path.parent),
                suffix=".tmp",
                prefix=f".{self.dedup_cache_path.name}",
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                    json.dump(raw, fh, indent=2, sort_keys=True)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_name, self.dedup_cache_path)
            except OSError:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except Exception as exc:
            self.logger.warning("Failed to save dedup cache to %s: %s", self.dedup_cache_path, exc)

    def _prune_dedup_cache(self, now: float) -> None:
        """Remove expired entries from dedup cache and enforce LRU max size."""
        # Remove expired entries (TTL)
        expired = [k for k, v in self._dedup.items() if (now - v) >= self._dedup_ttl]
        for k in expired:
            del self._dedup[k]

        # Enforce LRU max size - remove oldest entries if over capacity
        while len(self._dedup) > self._dedup_max_size:
            self._dedup.popitem(last=False)  # Remove oldest (LRU)

        if expired:
            self.logger.debug("Pruned %d expired dedup entries, cache size: %d", len(expired), len(self._dedup))

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _sanitize_log_field(value: Any) -> str:
        """Sanitize log field to prevent log injection (newlines, tabs, control chars)."""
        if value is None:
            return "N/A"
        s = str(value)
        # Replace newlines, carriage returns, tabs with escaped versions
        return s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

    @staticmethod
    def _html_escape(value: Any) -> str:
        """HTML escape a value for safe inclusion in Telegram HTML messages."""
        if value is None:
            return "N/A"
        return html.escape(str(value))

    @staticmethod
    def _dedup_key(event: AnomalyEvent) -> tuple:
        ips = event.details.get("observed_ips") or event.details.get("ips", []) or []
        return (event.fqdn, event.type, frozenset(ips))

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * (self._capacity / 3600.0))
        self._last_refill = now

    def _write_jsonl(self, event: AnomalyEvent) -> None:
        if not self.alert_log_path or not self._alert_jsonl_handler:
            return
        record = {"timestamp": event.timestamp.isoformat(), "event": event.model_dump()}
        line = json.dumps(record, ensure_ascii=False, default=str)
        # Use a temporary logger to emit the line through the rotating handler
        logger = logging.getLogger("chk_a.alert.jsonl")
        logger.addHandler(self._alert_jsonl_handler)
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info(line)

    def _write_text_log(self, event: AnomalyEvent) -> None:
        """Write a plain text log line: date time hostname resolver ip event.
        All user-controllable fields are sanitized to prevent log injection.
        """
        if not self.alert_text_log_path or not self._alert_text_handler:
            return

        # Handle recovery event specially
        if event.type == "recovery":
            d = event.details
            original_type = self._sanitize_log_field(d.get("original_anomaly_type", "unknown"))
            start_time = self._sanitize_log_field(d.get("anomaly_start_time", "unknown"))
            end_time = self._sanitize_log_field(d.get("anomaly_end_time", "unknown"))
            duration_human = self._sanitize_log_field(d.get("duration_human", "unknown"))
            duration_seconds = d.get("duration_seconds", 0)
            observed = d.get("observed_ips", [])
            primary_ip = self._sanitize_log_field(observed[0] if observed else "N/A")
            resolver_name = self._sanitize_log_field(event.resolver_name or "unknown")
            fqdn = self._sanitize_log_field(event.fqdn)
            hostname = self._sanitize_log_field(self.hostname)
            # Format: date time hostname resolver ip event [recovery: original_type duration]
            dt = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            line = f"{dt} {hostname} {resolver_name} {primary_ip} recovery: {original_type} duration={duration_human} ({duration_seconds:.1f}s) started={start_time} ended={end_time} {fqdn}"
        elif event.type == "hourly_reminder":
            d = event.details
            original_type = self._sanitize_log_field(d.get("original_anomaly_type", "unknown"))
            start_time = self._sanitize_log_field(d.get("anomaly_start_time", "unknown"))
            reminder_time = self._sanitize_log_field(d.get("reminder_time", "unknown"))
            duration_human = self._sanitize_log_field(d.get("duration_human", "unknown"))
            duration_seconds = d.get("duration_seconds", 0)
            reminder_count = d.get("reminder_count", 0)
            config_changed = d.get("config_changed", False)
            baseline_changes = d.get("baseline_changes", [])
            observed = d.get("observed_ips", [])
            primary_ip = self._sanitize_log_field(observed[0] if observed else "N/A")
            resolver_name = self._sanitize_log_field(event.resolver_name or "unknown")
            fqdn = self._sanitize_log_field(event.fqdn)
            hostname = self._sanitize_log_field(self.hostname)
            config_note = f" config_changed={config_changed}" + (f" changes={'; '.join(baseline_changes)}" if baseline_changes else "")
            # Format: date time hostname resolver ip hourly_reminder: original_type duration reminder_count
            dt = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            line = f"{dt} {hostname} {resolver_name} {primary_ip} hourly_reminder: {original_type} duration={duration_human} ({duration_seconds:.1f}s) reminder=#{reminder_count} started={start_time} reminder_sent={reminder_time}{config_note} {fqdn}"
        else:
            # Get primary IP from observed IPs
            observed = event.details.get("observed_ips") or event.details.get("ips", []) or []
            primary_ip = self._sanitize_log_field(observed[0] if observed else "N/A")
            resolver_name = self._sanitize_log_field(event.resolver_name or "unknown")
            event_type = self._sanitize_log_field(event.type)
            fqdn = self._sanitize_log_field(event.fqdn)
            hostname = self._sanitize_log_field(self.hostname)
            # Format: date time hostname resolver ip event
            dt = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            line = f"{dt} {hostname} {resolver_name} {primary_ip} {event_type}: {fqdn}"

        # Use a temporary logger to emit the line through the rotating handler
        logger = logging.getLogger("chk_a.alert.text")
        logger.addHandler(self._alert_text_handler)
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info(line)

    async def _send_alert_with_image(self, event: AnomalyEvent, text: str, image_path: Path | None) -> bool:
        """Send an alert with optional image to Telegram."""
        # Try to send image first if path exists
        chat_id = self.config.telegram_chat_id.get_secret_value() if self.config.telegram_chat_id else ""
        if image_path and image_path.is_file():
            ok = await self.telegram.send_photo(chat_id, image_path, caption=text, parse_mode="HTML")
            if not ok:
                # Fallback to text-only message if image send fails
                self.logger.warning("Failed to send image %s, falling back to text-only", image_path)
                ok = await self.telegram.send_message(text, "HTML", chat_id)
            return ok
        # No image available, send text-only
        ok = await self.telegram.send_message(text, "HTML", chat_id)
        return ok

    # -- main entry --------------------------------------------------------
    async def maybe_alert(self, event: AnomalyEvent) -> bool:
        """Return ``True`` if the event was sent, ``False`` if suppressed/dropped."""
        key = self._dedup_key(event)
        now = time.time()

        # Use lock to protect all dedup cache and rate limit operations
        async with self._dedup_lock:
            # Prune expired entries from persistent cache
            self._prune_dedup_cache(now)

            # 1. Deduplication.
            last = self._dedup.get(key)
            if last is not None and (now - last) < self._dedup_ttl:
                self.logger.info("Alert suppressed (dedup): %s/%s", event.fqdn, event.type)
                return False

            # 2. Rate limiting (token bucket) - protected by separate lock
            async with self._rate_limit_lock:
                self._refill()
                if self._tokens < 1.0:
                    self.logger.warning("Alert dropped (rate limit): %s/%s", event.fqdn, event.type)
                    return False

                # 3. Format + send with image.
                text = _format_html(event)

                # Select image based on event type
                if event.type == "recovery":
                    image_path = self.recovery_image_path
                else:
                    image_path = self.anomaly_image_path

                ok = await self._send_alert_with_image(event, text, image_path)
                if not ok:
                    self.logger.warning("Alert not sent (telegram failed): %s/%s", event.fqdn, event.type)
                    return False

                # 4. Success: audit logs (JSONL + plain text), mark dedup, consume a token.
                self._write_jsonl(event)
                self._write_text_log(event)
                # Mark dedup entry as most-recently-used (move to end of OrderedDict)
                if key in self._dedup:
                    del self._dedup[key]
                self._dedup[key] = now
                self._tokens -= 1.0

                # Persist cache after successful alert
                self._save_dedup_cache()
                return True


__all__ = ["AlertAgent", "_format_html"]