"""Alert Agent — deduplication, rate limiting, Telegram formatting, JSONL + plain text log (Loop 4).

``maybe_alert`` decides whether an :class:`AnomalyEvent` should actually be sent:

  * **Deduplication** — identical events (same FQDN + type + observed IPs) within
    ``dedup_window_minutes`` are suppressed (in-memory cache, no Redis needed).
  * **Rate limiting** — a token bucket refilled at ``rate_limit_per_hour`` tokens
    per hour; when empty the alert is dropped with a warning.
  * **Formatting** — an HTML message per the Loop 4 spec, sent via the
    :class:`TelegramClient`. Includes hostname and resolver name.
  * **Audit log (JSONL)** — every sent alert is appended as one JSON line to an optional
    JSONL file (atomic append + fsync).
  * **Plain text log** — every sent alert is appended as a plain text line with:
    date, time, hostname, resolver, ip, event.
"""

from __future__ import annotations

import json
import os
import platform
import tempfile
import time
from pathlib import Path
from typing import Any

from ..models.schemas import AlertConfig, AnomalyEvent
from ..utils.logger import setup_logger


def _format_html(event: AnomalyEvent) -> str:
    """Render the anomaly as HTML with Majority vs Outliers view."""
    d = event.details
    all_results = d.get("all_results", [])
    majority_ips = d.get("majority_ips", [])
    baseline_ips = d.get("baseline_ips", [])
    outlier_details = d.get("outlier_details", [])
    consensus = d.get("consensus_score", 0.0)
    resolver_count = d.get("resolver_count", 0)
    hostname = event.hostname or platform.node()
    
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
    }
    type_label = type_map.get(event.type, event.type)
    
    lines = [
        f"<b>⚠️ DNS Anomaly Detected</b>",
        f"<b>Type:</b> {type_label} (<code>{event.type}</code>)",
        f"<b>Severity:</b> {sev_emoji} {sev_label}",
        f"<b>FQDN:</b> <code>{event.fqdn}</code>",
        f"<b>Host:</b> <code>{hostname}</code>",
    ]
    
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
            lines.append(f"  <b>IPs:</b> {', '.join(f'<code>{ip}</code>' for ip in ips)}")
            lines.append(f"  <b>Resolvers:</b> {', '.join(f'<code>{r}</code>' for r in resolvers)}")
    
    # Outliers / Failed
    failed = [r for r in all_results if not r.get("success")]
    outliers_ips = [r for r in all_results if r.get("success") and r.get("ips") and list(r["ips"]) != majority_ips]
    
    if outliers_ips:
        lines.append(f"<b>❌ Outliers:</b>")
        for r in outliers_ips:
            lines.append(f"  ❌ <code>{r['resolver']}</code>: {', '.join(f'<code>{ip}</code>' for ip in r['ips'])}  ← DIFFERENT!")
    
    if failed:
        lines.append(f"<b>❌ Failed / No Response:</b>")
        for r in failed:
            err = r.get("error") or "timeout"
            lines.append(f"  ❌ <code>{r['resolver']}</code>: <i>{err}</i>")
    
    # Baseline comparison for baseline_deviation
    if event.type == "baseline_deviation" and baseline_ips:
        lines.append(f"<b>Baseline IPs:</b> {', '.join(f'<code>{ip}</code>' for ip in baseline_ips)}")
    
    lines.extend([
        f"<b>Consensus:</b> {consensus:.2%}",
        f"<b>Resolvers:</b> {resolver_count} checked",
        f"<b>Time:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
    ])
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
    ) -> None:
        self.config = config
        self.logger = logger or setup_logger("chk_a.alert")
        self.telegram = telegram_client
        self.alert_log_path = alert_log_path or config.alert_log_path
        self.alert_text_log_path = alert_text_log_path or config.alert_text_log_path
        self.hostname = hostname or platform.node()
        # Dedup cache: key -> last alerted epoch seconds.
        self._dedup: dict[tuple, float] = {}
        # Persistent dedup cache path (optional)
        self.dedup_cache_path = Path(config.dedup_cache_path) if config.dedup_cache_path else None
        # Token bucket (tokens refilled at rate_limit_per_hour per hour).
        self._capacity = float(config.rate_limit_per_hour)
        self._tokens = self._capacity
        self._last_refill = time.monotonic()

        # Load persistent cache if configured
        if self.dedup_cache_path:
            self._load_dedup_cache()

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
            self.logger.info("Loaded dedup cache: %d entries from %s", len(self._dedup), self.dedup_cache_path)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            self.logger.warning("Could not load dedup cache from %s: %s", self.dedup_cache_path, exc)
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
        """Remove expired entries from dedup cache."""
        window_sec = self.config.dedup_window_minutes * 60
        expired = [k for k, v in self._dedup.items() if (now - v) >= window_sec]
        for k in expired:
            del self._dedup[k]
        if expired:
            self.logger.debug("Pruned %d expired dedup entries", len(expired))

    # -- helpers -----------------------------------------------------------
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
        if not self.alert_log_path:
            return
        record = {"timestamp": event.timestamp.isoformat(), "event": event.model_dump()}
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(self.alert_log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _write_text_log(self, event: AnomalyEvent) -> None:
        """Write a plain text log line: date time hostname resolver ip event"""
        if not self.alert_text_log_path:
            return
        # Get primary IP from observed IPs
        observed = event.details.get("observed_ips") or event.details.get("ips", []) or []
        primary_ip = observed[0] if observed else "N/A"
        resolver_name = event.resolver_name or "unknown"
        # Format: date time hostname resolver ip event
        dt = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{dt} {self.hostname} {resolver_name} {primary_ip} {event.type}: {event.fqdn}\n"
        try:
            with open(self.alert_text_log_path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
        except Exception as exc:
            self.logger.warning("Failed to write text alert log: %s", exc)

    # -- main entry --------------------------------------------------------
    async def maybe_alert(self, event: AnomalyEvent) -> bool:
        """Return ``True`` if the event was sent, ``False`` if suppressed/dropped."""
        key = self._dedup_key(event)
        now = time.time()

        # Prune expired entries from persistent cache
        self._prune_dedup_cache(now)

        # 1. Deduplication.
        last = self._dedup.get(key)
        if last is not None and (now - last) < self.config.dedup_window_minutes * 60:
            self.logger.info("Alert suppressed (dedup): %s/%s", event.fqdn, event.type)
            return False

        # 2. Rate limiting (token bucket).
        self._refill()
        if self._tokens < 1.0:
            self.logger.warning("Alert dropped (rate limit): %s/%s", event.fqdn, event.type)
            return False

        # 3. Format + send.
        text = _format_html(event)
        ok = await self.telegram.send_message(self.config.telegram_chat_id, text, "HTML")
        if not ok:
            self.logger.warning("Alert not sent (telegram failed): %s/%s", event.fqdn, event.type)
            return False

        # 4. Success: audit logs (JSONL + plain text), mark dedup, consume a token.
        self._write_jsonl(event)
        self._write_text_log(event)
        self._dedup[key] = now
        self._tokens -= 1.0

        # Persist cache after successful alert
        self._save_dedup_cache()
        return True


__all__ = ["AlertAgent", "_format_html"]
