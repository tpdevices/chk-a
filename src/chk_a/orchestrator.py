"""Orchestrator + Scheduler (Loop 5).

Drives the full multi-agent cycle:

    Resolver -> Consensus -> ML.learn -> ML.score -> Alert

with a randomized inter-cycle delay (30-180s), graceful shutdown on
SIGTERM/SIGINT (persist baseline, flush logs), and an optional HTTP
``/healthz`` endpoint for the systemd watchdog.

Note: no Prometheus or external monitor is used. Observability is provided
solely through structured JSON logs (with a per-cycle ``correlation_id``) and
the ``/healthz`` liveness endpoint.
"""

from __future__ import annotations

import json
import asyncio
import contextlib
import os
import random
import signal
import time
import socket
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from .agents.alert_agent import AlertAgent
from .agents.consensus_agent import ConsensusAgent
from .agents.ml_agent import MLAgent
from .agents.mtr_agent import MTRAgent
from .agents.resolver_agent import ResolverAgent
from .config.loader import AppConfig
from .models.schemas import (
    AnomalyEvent,
    CheckResult,
    ConsensusResult,
    FQDNConfig,
)
from .reporting.monthly_report import generate_monthly_report, generate_daily_report
from .utils.context import new_correlation_id, set_correlation_id
from .utils.logger import setup_logger
from .utils.systemd_notify import notify_ready, notify_watchdog


# Recovery tracking state
class ActiveAnomaly:
    """Tracks an active anomaly for recovery detection."""

    def __init__(
        self,
        fqdn: str,
        anomaly_type: str,
        start_time: datetime,
        details: dict[str, Any],
        resolver_name: str,
        event_id: str,
        baseline_ips: list[str] | None = None,
    ) -> None:
        self.fqdn = fqdn
        self.anomaly_type = anomaly_type
        self.start_time = start_time
        self.details = details
        self.resolver_name = resolver_name
        self.last_seen = start_time
        self.alert_sent = False
        self.event_id = event_id
        # Hourly reminder tracking
        self.last_reminder_time: datetime | None = None
        self.reminder_count = 0
        # Baseline snapshot at anomaly start (for config change detection)
        self.baseline_at_start = baseline_ips or []

    def duration_seconds(self, now: datetime | None = None) -> float:
        """Return duration in seconds since anomaly started."""
        if now is None:
            now = datetime.now(TZ)
        # Handle both naive and timezone-aware start_time
        if self.start_time.tzinfo is None:
            # Assume naive datetime is in local timezone (TZ)
            start_time = self.start_time.replace(tzinfo=TZ)
        else:
            start_time = self.start_time
        return (now - start_time).total_seconds()

    def duration_human(self, now: datetime | None = None) -> str:
        """Return human-readable duration string."""
        seconds = self.duration_seconds(now)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        parts = []
        if hours > 0:
            parts.append(f"{hours} ชม.")
        if minutes > 0:
            parts.append(f"{minutes} นาที")
        if secs > 0 or not parts:
            parts.append(f"{secs} วินาที")
        return " ".join(parts)


# Timezone constant for Asia/Bangkok
TZ = ZoneInfo("Asia/Bangkok")


def _anomaly_key(fqdn: str, anomaly_type: str) -> str:
    """Generate a unique key for tracking an active anomaly."""
    return f"{fqdn}|{anomaly_type}"


class Orchestrator:
    """Coordinates the resolver/consensus/ML/alert agents per cycle."""

    @staticmethod
    def _anomaly_key(fqdn: str, anomaly_type: str) -> str:
        """Generate a unique key for tracking an active anomaly."""
        return _anomaly_key(fqdn, anomaly_type)

    def __init__(
        self,
        config: AppConfig,
        agents: dict[str, Any],
        logger: Any = None,
    ) -> None:
        self.config = config
        self.resolver: ResolverAgent = agents["resolver"]
        self.consensus: ConsensusAgent = agents["consensus"]
        self.ml: MLAgent = agents["ml"]
        self.mtr: MTRAgent | None = agents.get("mtr")
        self.alert: AlertAgent = agents["alert"]
        self.logger = logger or setup_logger("chk_a.orchestrator")
        self._shutdown: asyncio.Event | None = None
        self.hostname = config.hostname
        # Daily task state
        self._daily_task: asyncio.Task | None = None
        # Daily report task state
        self._daily_report_task: asyncio.Task | None = None
        # Monthly report task state
        self._monthly_task: asyncio.Task | None = None
        # Active anomaly tracking for recovery detection
        self._active_anomalies: dict[str, ActiveAnomaly] = {}  # key: fqdn|type

    # -- lifecycle ---------------------------------------------------------
    async def run(self, handle_signals: bool = True) -> None:
        """Run the monitor loop until a shutdown is requested."""
        self._shutdown = asyncio.Event()
        self.logger.info(
            "Orchestrator starting (FQDNs=%d, resolvers=%d)",
            len(self.config.fqdns),
            len(self.config.resolvers),
        )
        if handle_signals:
            self._install_signal_handlers()

        health_task = None
        port = self._health_port()
        if port:
            bind_address = self._health_bind_address()
            health_task = asyncio.create_task(self._run_health_server(port, bind_address))

        watchdog_task = None
        wd_interval = self._watchdog_interval()
        if wd_interval > 0:
            watchdog_task = asyncio.create_task(self._run_watchdog(wd_interval))

        # Start daily midnight task (image + log separators)
        self._daily_task = asyncio.create_task(self._run_daily_midnight())

        # Start daily report task (7:00 AM by default)
        self._daily_report_task = asyncio.create_task(self._run_daily_report())

        # Start monthly report task (1st of month)
        self._monthly_task = asyncio.create_task(self._run_monthly_report())

        # Check and send yesterday's daily report if missing (on startup)
        await self._send_missing_daily_report()

        # Tell systemd we are ready to serve (Type=notify / WatchdogSec).
        notify_ready()

        try:
            while not self._shutdown.is_set():
                await self.run_cycle()
                if self._shutdown.is_set():
                    break
                delay = random.uniform(
                    self.config.scheduler.min_interval_sec,
                    self.config.scheduler.max_interval_sec,
                )
                self.logger.info("Next cycle in %.1fs", delay)
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
        finally:
            for task in (
                health_task,
                watchdog_task,
                self._daily_task,
                self._daily_report_task,
                self._monthly_task,
            ):
                if task is not None:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            await self.shutdown()

    def request_shutdown(self) -> None:
        """Signal the loop to stop at the next safe point."""
        self.logger.info("Shutdown requested")
        if self._shutdown is not None:
            self._shutdown.set()

    async def shutdown(self) -> None:
        """Persist the ML baseline and release resources cleanly."""
        self.logger.info("Persisting ML baseline and flushing logs")
        with contextlib.suppress(Exception):
            self.ml.storage.save()
        with contextlib.suppress(Exception):
            await self.alert.telegram.close()

    # -- one cycle ---------------------------------------------------------
    async def run_cycle(self) -> None:
        """Execute a single monitoring cycle across all configured FQDNs."""
        cid = new_correlation_id()
        set_correlation_id(cid)
        start = time.perf_counter()
        self.logger.info("=== Cycle start (correlation_id=%s) ===", cid)
        fqdns = [f.name for f in self.config.fqdns]
        if not fqdns:
            self.logger.warning("No FQDNs configured; skipping cycle")
            return

        results_per_fqdn = await self._resolve_all(fqdns)
        # Persist check results to JSONL for reporting/ML insights
        self._write_check_results(results_per_fqdn)
        for fqdn in fqdns:
            try:
                await self._process_fqdn(fqdn, results_per_fqdn[fqdn])
            except Exception as exc:  # noqa: BLE001 - one FQDN must not kill the cycle
                self.logger.exception("Error processing %s: %s", fqdn, exc)
        duration = time.perf_counter() - start
        self.logger.info("=== Cycle complete (correlation_id=%s, %.1fs) ===", cid, duration)

    def _write_check_results(self, results_per_fqdn: dict[str, list[CheckResult]]) -> None:
        """Write CheckResult objects to JSONL log file for reporting."""
        log_file = self.config.logging.file
        if not log_file:
            return
        try:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            for results in results_per_fqdn.values():
                for result in results:
                    lines.append(result.model_dump_json())
            with path.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as exc:  # noqa: BLE001 - logging must not break the cycle
            self.logger.exception("Failed to write check results to %s: %s", log_file, exc)

    async def _resolve_all(self, fqdns: list[str]) -> dict[str, list[CheckResult]]:
        tasks = {fqdn: self.resolver.check_fqdn(fqdn) for fqdn in fqdns}
        resolved = await asyncio.gather(*tasks.values())
        return dict(zip(fqdns, resolved))

    async def _process_fqdn(self, fqdn: str, results: list[CheckResult]) -> None:
        cfg = self._fqdn_config(fqdn)
        min_consensus = cfg.min_consensus if cfg else 0.6
        consensus = self.consensus.aggregate(fqdn, results, min_consensus=min_consensus)
        self.ml.learn(consensus)

        observed_ips = list(consensus.majority_ips)
        score = self.ml.score(fqdn, observed_ips)

        # Check for recovery of active anomalies for this FQDN
        await self._check_recovery(fqdn, consensus, results, score)

        if score > self.config.ml.anomaly_threshold:
            await self._alert_baseline(fqdn, consensus, results, score)
        if consensus.outliers:
            await self._alert_consensus(fqdn, consensus, results)

    def _fqdn_config(self, fqdn: str) -> FQDNConfig | None:
        for f in self.config.fqdns:
            if f.name == fqdn:
                return f
        return None

    # -- alert helpers -----------------------------------------------------
    async def _run_mtr_on_anomaly(self, resolver_name: str, anomaly_type: str, fqdn: str) -> dict[str, Any] | None:
        """Run MTR trace to the problematic resolver when anomaly is detected.

        Returns MTR result with path data and last-hop IP for ML/tracking.
        """
        if not self.mtr:
            self.logger.warning("MTR agent not available, skipping path trace")
            return None

        # Find resolver config
        resolver = self.resolver.resolvers.get(resolver_name)
        if not resolver:
            self.logger.warning("Resolver %s not found for MTR trace", resolver_name)
            return None

        # Extract target IP and port from resolver address
        target_ip, target_port = self._parse_resolver_for_mtr(resolver.address)

        self.logger.info(
            "Running MTR trace to resolver %s (%s) for anomaly %s on %s",
            resolver_name, target_ip, anomaly_type, fqdn
        )

        try:
            # Run MTR with TCP/UDP mode to check relevant ports
            result = await self.mtr.trace_resolver(
                resolver_name=resolver_name,
                resolve_hostnames=False,  # IP-only for speed
                mode="tcp" if target_port else "icmp",
                port=target_port,
            )

            # Extract path information
            mtr_data = self._extract_mtr_features(result)
            mtr_data["resolver_name"] = resolver_name
            mtr_data["target_ip"] = target_ip
            mtr_data["target_port"] = target_port
            mtr_data["anomaly_type"] = anomaly_type
            mtr_data["fqdn"] = fqdn

            # Log MTR data to JSONL for ML
            self._log_mtr_data(mtr_data)

            # Learn path patterns in ML
            if mtr_data.get("hops"):
                self.ml.learn_path_pattern(fqdn, resolver_name, mtr_data)

            return mtr_data

        except Exception as exc:
            self.logger.exception("MTR trace failed for %s: %s", resolver_name, exc)
            return None

    def _parse_resolver_for_mtr(self, address: str) -> tuple[str, int | None]:
        """Parse resolver address to extract IP and port for MTR.

        Returns (target_ip, port) where port is the resolver's DNS port (typically 53).
        """
        # Handle "IP:port" format
        if ":" in address and not address.startswith(("http://", "https://")):
            host, port_str = address.rsplit(":", 1)
            try:
                port = int(port_str)
                return host, port
            except ValueError:
                pass
        # Handle "[IPv6]:port" format
        if address.startswith("["):
            end = address.find("]:")
            if end > 0:
                host = address[1:end]
                port_str = address[end+2:]
                try:
                    port = int(port_str)
                    return host, port
                except ValueError:
                    pass
        return address, None

    def _extract_mtr_features(self, result) -> dict[str, Any]:
        """Extract ML-relevant features from MTR result."""
        if not result.success or not result.hops:
            return {"success": False, "error": result.error, "hops": []}

        hops_data = []
        last_hop_ip = None
        last_hop_loss = None

        for hop in result.hops:
            hop_data = {
                "hop_num": hop.hop_num,
                "host": hop.host,
                "loss_pct": hop.loss_pct,
                "avg_ms": hop.avg_ms,
                "worst_ms": hop.worst_ms,
                "best_ms": hop.best_ms,
            }
            hops_data.append(hop_data)
            # Track last hop with data
            if hop.host and hop.host not in ("???", "*"):
                last_hop_ip = hop.host
                last_hop_loss = hop.loss_pct

        # Find problematic hop (high loss/latency)
        problem_hops = [h for h in hops_data if h["loss_pct"] > 10 or h["avg_ms"] > 200]

        return {
            "success": True,
            "hops": hops_data,
            "hop_count": len(hops_data),
            "last_hop_ip": last_hop_ip,
            "last_hop_loss_pct": last_hop_loss,
            "problem_hops": problem_hops,
            "has_problems": len(problem_hops) > 0,
            "command": result.command,
            "tests": result.tests,
        }

    def _log_mtr_data(self, mtr_data: dict[str, Any]) -> None:
        """Log MTR data to JSONL file for ML training."""
        log_file = self.config.logging.file
        if not log_file:
            return
        try:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Add MTR-specific fields
            mtr_log = {
                "timestamp": datetime.now().isoformat(),
                "type": "mtr_trace",
                "data": mtr_data,
            }
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(mtr_log, ensure_ascii=False) + "\n")
        except Exception as exc:
            self.logger.exception("Failed to write MTR data to log: %s", exc)

    async def _alert_baseline(
        self,
        fqdn: str,
        consensus: ConsensusResult,
        results: list[CheckResult],
        score: float,
    ) -> None:
        baseline = self.ml.get_baseline(fqdn)
        # Determine which resolver contributed to the anomaly (first successful result)
        resolver_name = results[0].resolver if results else "unknown"

        # Prepare full resolver details for alert formatting
        all_results = []
        for r in results:
            all_results.append(
                {
                    "resolver": r.resolver,
                    "ips": r.ips,
                    "latency_ms": r.latency_ms,
                    "timestamp": r.timestamp.isoformat(),
                    "success": r.success,
                    "error": r.error,
                }
            )

        outlier_details = []
        for r in consensus.outliers:
            outlier_details.append(
                {
                    "resolver": r.resolver,
                    "ips": r.ips,
                    "error": r.error,
                }
            )

        # Generate event ID: {hostname}-YYYYMMDD-HHmmss
        event_id = f"{self.hostname}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        event = AnomalyEvent(
            fqdn=fqdn,
            type="baseline_deviation",
            severity="critical" if score >= 0.9 else "warning",
            details={
                "observed_ips": list(consensus.majority_ips),
                "baseline_ips": list(baseline.keys()),
                "consensus_score": consensus.consensus_score,
                "resolver_count": len(results),
                "anomaly_score": round(score, 4),
                "majority_ips": list(consensus.majority_ips),
                "all_results": all_results,
                "outlier_details": outlier_details,
            },
            resolver_snapshots=results,
            hostname=socket.gethostname(),
            resolver_name=resolver_name,
            event_id=event_id,
        )
        sent = await self.alert.maybe_alert(event)
        self.logger.info("Baseline deviation %s score=%.2f alert_sent=%s", fqdn, score, sent)

        # Run MTR trace for path analysis on anomaly for all outlier resolvers
        mtr_results = []
        if consensus.outliers:
            # Run MTR traces concurrently
            tasks = [
                self._run_mtr_on_anomaly(outlier.resolver, "baseline_deviation", fqdn)
                for outlier in consensus.outliers
            ]
            mtr_data_list = await asyncio.gather(*tasks, return_exceptions=True)
            for mtr_data in mtr_data_list:
                if isinstance(mtr_data, dict) and mtr_data.get("success"):
                    mtr_results.append(mtr_data)

        # Add MTR info to event for Telegram
        if mtr_results:
            event.details["mtr_results"] = mtr_results

        # Track this anomaly for recovery detection
        await self._track_new_anomaly(fqdn, "baseline_deviation", consensus, results, score)

    async def _alert_consensus(
        self,
        fqdn: str,
        consensus: ConsensusResult,
        results: list[CheckResult],
    ) -> None:
        outlier_ips: list[str] = []
        for r in consensus.outliers:
            outlier_ips.extend(r.ips)
        # Determine which resolver triggered the outlier (first outlier's resolver)
        resolver_name = consensus.outliers[0].resolver if consensus.outliers else "unknown"

        # Prepare full resolver details for alert formatting
        all_results = []
        for r in results:
            all_results.append(
                {
                    "resolver": r.resolver,
                    "ips": r.ips,
                    "latency_ms": r.latency_ms,
                    "timestamp": r.timestamp.isoformat(),
                    "success": r.success,
                    "error": r.error,
                }
            )

        # Generate event ID: {hostname}-YYYYMMDD-HHmmss
        event_id = f"{self.hostname}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        event = AnomalyEvent(
            fqdn=fqdn,
            type="consensus_deviation",
            severity="warning",
            details={
                "observed_ips": outlier_ips,
                "baseline_ips": [],
                "consensus_score": consensus.consensus_score,
                "resolver_count": len(results),
                "anomaly_score": 1.0,
                "majority_ips": list(consensus.majority_ips),
                "all_results": all_results,
                "outlier_details": [
                    {
                        "resolver": r.resolver,
                        "ips": r.ips,
                        "error": r.error,
                    }
                    for r in consensus.outliers
                ],
            },
            resolver_snapshots=results,
            hostname=socket.gethostname(),
            resolver_name=resolver_name,
            event_id=event_id,
        )
        sent = await self.alert.maybe_alert(event)
        self.logger.info("Consensus deviation %s alert_sent=%s", fqdn, sent)

        # Track this anomaly for recovery detection
        await self._track_new_anomaly(fqdn, "consensus_deviation", consensus, results, 1.0)

    # -- recovery detection ------------------------------------------------
    async def _track_new_anomaly(
        self,
        fqdn: str,
        anomaly_type: str,
        consensus: ConsensusResult,
        results: list[CheckResult],
        score: float,
    ) -> None:
        """Track a new anomaly for recovery detection."""
        key = _anomaly_key(fqdn, anomaly_type)
        if key in self._active_anomalies:
            # Update existing anomaly
            anomaly = self._active_anomalies[key]
            anomaly.last_seen = datetime.now()
            anomaly.details["observed_ips"] = list(consensus.majority_ips)
            anomaly.details["anomaly_score"] = round(score, 4)
        else:
            # Create new anomaly
            event_id = f"{self.hostname}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            anomaly = ActiveAnomaly(
                fqdn=fqdn,
                anomaly_type=anomaly_type,
                start_time=datetime.now(TZ),
                details={
                    "observed_ips": list(consensus.majority_ips),
                    "consensus_score": consensus.consensus_score,
                    "resolver_count": len(results),
                    "anomaly_score": round(score, 4),
                    "majority_ips": list(consensus.majority_ips),
                },
                resolver_name=results[0].resolver if results else "unknown",
                event_id=event_id,
                baseline_ips=list(self.ml.get_baseline(fqdn).keys()),
            )
            self._active_anomalies[key] = anomaly
            self.logger.info("Tracking new anomaly: %s", key)

    async def _check_recovery(
        self,
        fqdn: str,
        consensus: ConsensusResult,
        results: list[CheckResult],
        score: float,
    ) -> None:
        """Check if any active anomaly for this FQDN has recovered."""
        for key in list(self._active_anomalies.keys()):
            if not key.startswith(f"{fqdn}|"):
                continue
            anomaly = self._active_anomalies[key]
            # Check if consensus is back to normal (high consensus, no outliers)
            if consensus.consensus_score >= 0.9 and not consensus.outliers and score < self.config.ml.anomaly_threshold:
                # Recovery detected
                await self._send_recovery_alert(anomaly, consensus, results)
                del self._active_anomalies[key]
                self.logger.info("Anomaly recovered: %s", key)

    async def _send_recovery_alert(
        self,
        anomaly: ActiveAnomaly,
        consensus: ConsensusResult,
        results: list[CheckResult],
    ) -> None:
        """Send recovery alert."""
        # Prepare current observed IPs
        observed_ips = list(consensus.majority_ips)
        baseline_ips = list(anomaly.baseline_at_start)

        # Calculate duration
        end_time = datetime.now(TZ)
        duration_seconds = anomaly.duration_seconds(end_time)
        duration_human = anomaly.duration_human(end_time)

        # Calculate ML stability/confidence
        ml_stability = min(1.0, consensus.consensus_score)
        ml_confidence = 1.0 - anomaly.details.get("anomaly_score", 0.0)

        event = AnomalyEvent(
            fqdn=anomaly.fqdn,
            type="recovery",
            severity="info",
            details={
                "original_anomaly_type": anomaly.anomaly_type,
                "anomaly_start_time": anomaly.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "anomaly_end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_human": duration_human,
                "duration_seconds": duration_seconds,
                "ml_baseline_stability": ml_stability,
                "ml_recovery_confidence": ml_confidence,
                "observed_ips": observed_ips,
                "baseline_ips": baseline_ips,
                "consensus_score": consensus.consensus_score,
                "resolver_count": len(results),
                "reminder_count": anomaly.reminder_count,
                "config_changed": False,
                "baseline_changes": [],
            },
            resolver_snapshots=results,
            hostname=socket.gethostname(),
            resolver_name=anomaly.resolver_name,
            event_id=anomaly.event_id,
        )
        await self.alert.maybe_alert(event)
        self.logger.info("Recovery alert sent for %s", anomaly.fqdn)

    # -- hourly reminder ---------------------------------------------------
    async def _send_hourly_reminders(self) -> None:
        """Send hourly reminders for active anomalies."""
        now = datetime.now()
        for key, anomaly in self._active_anomalies.items():
            if anomaly.last_reminder_time is None:
                # First reminder after 1 hour
                if anomaly.duration_seconds(now) >= 3600:
                    await self._send_reminder(anomaly, is_first=True)
            else:
                # Subsequent reminders every hour
                if (now - anomaly.last_reminder_time).total_seconds() >= 3600:
                    await self._send_reminder(anomaly, is_first=False)

    async def _send_reminder(self, anomaly: ActiveAnomaly, is_first: bool) -> None:
        """Send hourly reminder for an active anomaly."""
        anomaly.reminder_count += 1
        anomaly.last_reminder_time = datetime.now()

        event = AnomalyEvent(
            fqdn=anomaly.fqdn,
            type="hourly_reminder",
            severity="warning",
            details={
                "original_anomaly_type": anomaly.anomaly_type,
                "anomaly_start_time": anomaly.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "reminder_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "duration_human": anomaly.duration_human(),
                "duration_seconds": anomaly.duration_seconds(),
                "reminder_count": anomaly.reminder_count,
                "is_first_reminder": is_first,
                "config_changed": False,
                "baseline_changes": [],
                "observed_ips": anomaly.details.get("observed_ips", []),
                "baseline_ips": anomaly.baseline_at_start,
            },
            resolver_snapshots=[],
            hostname=socket.gethostname(),
            resolver_name=anomaly.resolver_name,
            event_id=anomaly.event_id,
        )
        await self.alert.maybe_alert(event)
        self.logger.info("Hourly reminder #%d sent for %s", anomaly.reminder_count, anomaly.fqdn)

    # -- signal handling ---------------------------------------------------
    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.request_shutdown)

    # -- health endpoint ---------------------------------------------------
    def _health_port(self) -> int:
        """Return health check port from config (0 = disabled)."""
        return self.config.scheduler.health_port

    def _health_bind_address(self) -> str:
        return self.config.scheduler.health_bind_address

    def _watchdog_interval(self) -> int:
        try:
            return int(os.environ.get("CHK_A_WATCHDOG_INTERVAL", "0") or "0")
        except ValueError:
            return 0

    async def _run_health_server(self, port: int, bind_address: str = "127.0.0.1") -> None:
        from aiohttp import web

        async def _health(request: Any) -> Any:
            return web.json_response(
                {
                    "status": "ok",
                    "shutdown": bool(self._shutdown and self._shutdown.is_set()),
                }
            )

        app = web.Application()
        app.router.add_get("/healthz", _health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, bind_address, port)
        await site.start()
        self.logger.info("Health endpoint listening on %s:%d/healthz", bind_address, port)
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await runner.cleanup()
            raise

    async def _run_watchdog(self, interval: int) -> None:
        """Systemd watchdog notification."""
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(interval)
                notify_watchdog()
            except asyncio.CancelledError:
                break

    # -- daily midnight task -------------------------------------------------
    async def _run_daily_midnight(self) -> None:
        """Run daily tasks at midnight: send image + write day separators to logs."""
        try:
            while self._shutdown is not None and not self._shutdown.is_set():
                now = datetime.now(TZ)
                # Calculate seconds until next midnight
                next_midnight = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                delay = (next_midnight - now).total_seconds()
                self.logger.info(
                    "Next daily task at %s (in %.1fs)", next_midnight.isoformat(), delay
                )
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                if self._shutdown is not None and self._shutdown.is_set():
                    break
                await self._execute_daily_tasks()
        except asyncio.CancelledError:
            raise

    async def _execute_daily_tasks(self) -> None:
        """Execute the daily midnight tasks."""
        alert_cfg = self.config.alert
        chat_id = (alert_cfg.daily_image_chat_id.get_secret_value() if alert_cfg.daily_image_chat_id else "") or (alert_cfg.telegram_chat_id.get_secret_value() if alert_cfg.telegram_chat_id else "")
        bot_token = alert_cfg.telegram_bot_token.get_secret_value() if alert_cfg.telegram_bot_token else ""
        if chat_id and bot_token:
            # Resolve image path relative to project root if not absolute
            img_path = Path(alert_cfg.daily_image_path)
            if not img_path.is_absolute():
                # Try from working directory, then from /opt/chk-a (installed location)
                for base in [Path.cwd(), Path("/opt/chk-a")]:
                    candidate = base / img_path
                    if candidate.is_file():
                        img_path = candidate
                        break
            # Send image with hostname in caption
            hostname = self.hostname
            caption = f"{alert_cfg.daily_image_caption}\n🖥️ Host: <code>{hostname}</code>"
            ok = await self.alert.telegram.send_photo(
                chat_id=chat_id,
                photo_path=img_path,
                caption=caption,
                parse_mode="HTML",
            )
            self.logger.info("Daily image sent: ok=%s path=%s", ok, img_path)
        else:
            self.logger.info("Daily image skipped: missing chat_id or bot_token")

        # Write day separators to log files
        self._write_day_separators()

    def _write_day_separators(self) -> None:
        """Write day separator lines to all configured log files."""
        log_files = [
            self.config.logging.file,
            self.config.alert.alert_log_path,
            self.config.alert.alert_text_log_path,
        ]
        # Also include baseline store if it's a file we can append to
        baseline_path = Path(self.config.baseline_store_path)
        if baseline_path.parent.exists():
            # We don't write to baseline JSON, but we could write a separator comment
            pass

        today = datetime.now().strftime("%Y-%m-%d")
        separator = f"\n{'=' * 60}\n=== DAY SEPARATOR: {today} ===\n{'=' * 60}\n\n"
        for log_file in log_files:
            if not log_file:
                continue
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(separator)
                    fh.flush()
                    os.fsync(fh.fileno())
                self.logger.info("Day separator written to %s", log_path)
            except Exception as exc:
                self.logger.warning("Failed to write day separator to %s: %s", log_file, exc)

    async def _run_monthly_report(self) -> None:
        """Run monthly report generation on the 1st of each month at configured time."""
        if not self.config.reporting.enabled:
            self.logger.info("Monthly report generation disabled in config")
            return

        schedule_day = self.config.reporting.schedule_day
        schedule_hour = self.config.reporting.schedule_hour
        schedule_minute = self.config.reporting.schedule_minute

        self.logger.info(
            "Monthly report scheduler started: day=%d, time=%02d:%02d",
            schedule_day,
            schedule_hour,
            schedule_minute,
        )

        while self._shutdown is not None and not self._shutdown.is_set():
            try:
                now = datetime.now(TZ)
                # Calculate next run time (1st of next month at scheduled time)
                if (
                    now.day == schedule_day
                    and now.hour == schedule_hour
                    and now.minute >= schedule_minute
                ):
                    # Already past the scheduled time today, schedule for next month
                    if now.month == 12:
                        next_run = datetime(
                            now.year + 1, 1, schedule_day, schedule_hour, schedule_minute, tzinfo=TZ
                        )
                    else:
                        next_run = datetime(
                            now.year, now.month + 1, schedule_day, schedule_hour, schedule_minute, tzinfo=TZ
                        )
                elif now.day < schedule_day or (
                    now.day == schedule_day
                    and (
                        now.hour < schedule_hour
                        or (now.hour == schedule_hour and now.minute < schedule_minute)
                    )
                ):
                    # Schedule for this month
                    next_run = datetime(
                        now.year, now.month, schedule_day, schedule_hour, schedule_minute, tzinfo=TZ
                    )
                else:
                    # Past the day, schedule for next month
                    if now.month == 12:
                        next_run = datetime(
                            now.year + 1, 1, schedule_day, schedule_hour, schedule_minute, tzinfo=TZ
                        )
                    else:
                        next_run = datetime(
                            now.year, now.month + 1, schedule_day, schedule_hour, schedule_minute, tzinfo=TZ
                        )

                wait_seconds = (next_run - now).total_seconds()
                self.logger.info(
                    "Next monthly report scheduled for %s (in %.0f seconds)", next_run, wait_seconds
                )

                # Wait until scheduled time or shutdown
                try:
                    if self._shutdown is not None:
                        await asyncio.wait_for(self._shutdown.wait(), timeout=wait_seconds)
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Time to run the report

                if self._shutdown is not None and self._shutdown.is_set():
                    break

                self.logger.info("Starting monthly report generation...")
                try:
                    result = await generate_monthly_report(self.config)
                    self.logger.info("Monthly report generation completed: %s", result)
                except Exception as exc:
                    self.logger.exception("Monthly report generation failed: %s", exc)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.exception("Error in monthly report scheduler: %s", exc)
                # Wait a bit before retrying
                await asyncio.sleep(60)

    # -- daily report task -------------------------------------------------
    async def _run_daily_report(self) -> None:
        """Run daily report generation at configured time (default 6:00 AM).

        Uses absolute time scheduling from a fixed reference point to prevent drift.
        """
        if not self.config.reporting.daily_report_enabled:
            self.logger.info("Daily report generation disabled in config")
            return

        schedule_hour = self.config.reporting.daily_report_hour
        schedule_minute = self.config.reporting.daily_report_minute
        lookback_days = self.config.reporting.daily_report_lookback_days

        self.logger.info(
            "Daily report scheduler started: time=%02d:%02d, lookback=%d day(s)",
            schedule_hour,
            schedule_minute,
            lookback_days,
        )

        # SEC-019: Absolute time scheduling to prevent drift
        # Calculate the first scheduled run as an absolute datetime (Asia/Bangkok)
        now = datetime.now(TZ)
        first_run = datetime(now.year, now.month, now.day, schedule_hour, schedule_minute, tzinfo=TZ)
        if now >= first_run:
            first_run = first_run + timedelta(days=1)

        # Reference point for absolute scheduling
        reference_run = first_run

        while self._shutdown is not None and not self._shutdown.is_set():
            try:
                now = datetime.now(TZ)

                # Calculate next run from reference (adds exact 24h increments)
                next_run = reference_run
                while now >= next_run:
                    reference_run = reference_run + timedelta(days=1)
                    next_run = reference_run

                wait_seconds = (next_run - now).total_seconds()
                self.logger.info(
                    "Next daily report scheduled for %s (in %.0f seconds)", next_run, wait_seconds
                )

                # Wait until scheduled time or shutdown
                try:
                    if self._shutdown is not None:
                        await asyncio.wait_for(self._shutdown.wait(), timeout=wait_seconds)
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Time to run the report

                if self._shutdown is not None and self._shutdown.is_set():
                    break

                self.logger.info("Starting daily report generation...")
                try:
                    result = await generate_daily_report(self.config)
                    self.logger.info("Daily report generation completed: %s", result)
                except Exception as exc:
                    self.logger.exception("Daily report generation failed: %s", exc)

                # Advance reference by exactly 24 hours for next iteration (no drift)
                reference_run = reference_run + timedelta(days=1)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.exception("Error in daily report scheduler: %s", exc)
                # Wait a bit before retrying
                await asyncio.sleep(60)

    async def _send_missing_daily_report(self) -> None:
        """Check if yesterday's daily report was sent; if not, generate and send it.
        
        This runs on service startup to ensure we don't miss a daily report
        if the service was down during the scheduled time (06:00 AM).
        """
        if not self.config.reporting.daily_report_enabled:
            self.logger.info("Daily report generation disabled in config, skipping startup check")
            return

        # Determine yesterday's date
        yesterday = datetime.now(TZ) - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        
        # Check if we already have a report file for yesterday
        output_dir = Path(self.config.reporting.output_dir)
        if not output_dir.exists():
            self.logger.info("No output directory found, will generate yesterday's report")
        else:
            # Look for any report file with yesterday's date
            found = False
            for report_file in output_dir.glob(f"*{yesterday_str}*"):
                if report_file.is_dir():
                    found = True
                    break
            if found:
                self.logger.info("Yesterday's daily report (%s) already exists, skipping", yesterday_str)
                return
        
        self.logger.info("No daily report found for %s, generating on startup...", yesterday_str)
        
        try:
            # Generate daily report using yesterday as reference
            lookback_days = self.config.reporting.daily_report_lookback_days
            yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
            
            # We need to call generate_daily_report with the correct reference date
            # The generate_daily_report function uses generate_ml_insights which accepts reference_date
            from .reporting.ml_insights import generate_ml_insights
            from .reporting.graph_generator import generate_summary_dashboard
            from .reporting.telegram_reporter import send_daily_report_telegram
            from .storage.baseline_store import BaselineStore
            from .agents.ml_agent import MLAgent
            
            log_path = self.config.logging.file
            mtr_log_path = ""
            if hasattr(self.config, "mtr") and self.config.mtr.enabled:
                mtr_log_path = getattr(self.config.mtr, "log_path", "") or ""
            
            # Create MLAgent for baseline-based integrity scoring
            store = BaselineStore(self.config.baseline_store_path)
            ml_agent = MLAgent(self.config.ml, store)
            
            insights = generate_ml_insights(
                log_path, 
                lookback_days, 
                mtr_log_path, 
                ml_agent=ml_agent, 
                reference_date=yesterday_end
            )
            
            if not insights.get("summary", {}).get("total_resolvers", 0):
                self.logger.warning("No data available for yesterday's report (%s)", yesterday_str)
                return
            
            # Generate graphs
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            report_output_dir = output_dir / f"daily-startup-{timestamp}"
            report_output_dir.mkdir(parents=True, exist_ok=True)
            
            en_graphs = generate_summary_dashboard(
                insights, report_output_dir, lang="en", hostname=self.hostname,
                report_date_context=f"Daily report for :{yesterday_str} (startup)"
            )
            th_graphs = generate_summary_dashboard(
                insights, report_output_dir, lang="th", hostname=self.hostname,
                report_date_context=f"รายงานข้อมูลของวัน :{yesterday_str} (เริ่มต้น)"
            )
            all_graphs = en_graphs + th_graphs
            self.logger.info("Generated %d graph files for missing daily report", len(all_graphs))
            
            # Send to Telegram
            if self.config.reporting.daily_report_telegram_enabled:
                bot_token = self.config.alert.telegram_bot_token
                chat_id = self.config.reporting.daily_report_telegram_chat_id or self.config.alert.telegram_chat_id
                
                if bot_token and chat_id:
                    self.logger.info("Sending missing daily report to Telegram...")
                    from pydantic import SecretStr
                    chat_id_str = chat_id.get_secret_value() if isinstance(chat_id, SecretStr) else str(chat_id)
                    await send_daily_report_telegram(
                        bot_token=bot_token,
                        chat_id=SecretStr(chat_id_str),
                        ml_insights=insights,
                        graph_paths=all_graphs,
                        hostname=self.hostname,
                        lookback_days=lookback_days,
                    )
                    self.logger.info("Missing daily report for %s sent to Telegram successfully", yesterday_str)
                else:
                    self.logger.warning("Telegram credentials not configured for daily report")
            else:
                self.logger.info("Daily report Telegram disabled in config")
                
        except Exception as exc:
            self.logger.exception("Failed to generate/send missing daily report for %s: %s", yesterday_str, exc)

__all__ = ["Orchestrator"]