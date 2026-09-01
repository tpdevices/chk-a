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

from .agents.alert_agent import AlertAgent
from .agents.consensus_agent import ConsensusAgent
from .agents.ml_agent import MLAgent
from .agents.resolver_agent import ResolverAgent
from .config.loader import AppConfig
from .models.schemas import (
    AnomalyEvent,
    CheckResult,
    ConsensusResult,
    FQDNConfig,
)
from .utils.context import new_correlation_id, set_correlation_id
from .utils.logger import setup_logger, write_day_separator
from .utils.systemd_notify import notify_ready, notify_watchdog


class Orchestrator:
    """Coordinates the resolver/consensus/ML/alert agents per cycle."""

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
        self.alert: AlertAgent = agents["alert"]
        self.logger = logger or setup_logger("chk_a.orchestrator")
        self._shutdown: asyncio.Event | None = None
        self.hostname = config.hostname
        # Daily task state
        self._daily_task: asyncio.Task | None = None

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
            health_task = asyncio.create_task(self._run_health_server(port))

        watchdog_task = None
        wd_interval = self._watchdog_interval()
        if wd_interval > 0:
            watchdog_task = asyncio.create_task(self._run_watchdog(wd_interval))

        # Start daily midnight task (image + log separators)
        self._daily_task = asyncio.create_task(self._run_daily_midnight())

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
            for task in (health_task, watchdog_task, self._daily_task):
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
        for fqdn in fqdns:
            try:
                await self._process_fqdn(fqdn, results_per_fqdn[fqdn])
            except Exception as exc:  # noqa: BLE001 - one FQDN must not kill the cycle
                self.logger.exception("Error processing %s: %s", fqdn, exc)
        duration = time.perf_counter() - start
        self.logger.info("=== Cycle complete (correlation_id=%s, %.1fs) ===", cid, duration)

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
            all_results.append({
                "resolver": r.resolver,
                "ips": r.ips,
                "latency_ms": r.latency_ms,
                "timestamp": r.timestamp.isoformat(),
                "success": r.success,
                "error": r.error,
            })
        
        outlier_details = []
        for r in consensus.outliers:
            outlier_details.append({
                "resolver": r.resolver,
                "ips": r.ips,
                "error": r.error,
            })
        
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
        )
        sent = await self.alert.maybe_alert(event)
        self.logger.info("Baseline deviation %s score=%.2f alert_sent=%s", fqdn, score, sent)

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
            all_results.append({
                "resolver": r.resolver,
                "ips": r.ips,
                "latency_ms": r.latency_ms,
                "timestamp": r.timestamp.isoformat(),
                "success": r.success,
                "error": r.error,
            })
        
        outlier_details = []
        for r in consensus.outliers:
            outlier_details.append({
                "resolver": r.resolver,
                "ips": r.ips,
                "error": r.error,
            })
        
        event = AnomalyEvent(
            fqdn=fqdn,
            type="consensus_deviation",
            severity="warning",
            details={
                "observed_ips": outlier_ips,
                "baseline_ips": list(consensus.majority_ips),
                "consensus_score": consensus.consensus_score,
                "resolver_count": len(results),
                "majority_ips": list(consensus.majority_ips),
                "all_results": all_results,
                "outlier_details": outlier_details,
            },
            resolver_snapshots=results,
            hostname=socket.gethostname(),
            resolver_name=resolver_name,
        )
        sent = await self.alert.maybe_alert(event)
        self.logger.info("Consensus deviation %s alert_sent=%s", fqdn, sent)

    # -- signals / health --------------------------------------------------
    def _install_signal_handlers(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        def _handler() -> None:
            self.request_shutdown()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handler)
            except (NotImplementedError, RuntimeError):
                try:
                    signal.signal(
                        sig,
                        lambda s, f: loop.call_soon_threadsafe(_handler),
                    )
                except (ValueError, OSError):
                    pass

    @staticmethod
    def _health_port() -> int:
        try:
            return int(os.environ.get("CHK_A_HEALTH_PORT", "0") or "0")
        except ValueError:
            return 0

    @staticmethod
    def _watchdog_interval() -> int:
        """Seconds between systemd WATCHDOG pings (0 disables).

        Defaults to 30s, i.e. half of the service ``WatchdogSec=60`` so systemd
        never times out. Override with ``CHK_A_WATCHDOG_INTERVAL``.
        """
        try:
            val = int(os.environ.get("CHK_A_WATCHDOG_INTERVAL", "30") or "30")
        except ValueError:
            return 30
        return max(0, val)

    async def _run_watchdog(self, interval: int) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                notify_watchdog()
        except asyncio.CancelledError:
            raise

    async def _run_health_server(self, port: int) -> None:
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
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        self.logger.info("Health endpoint listening on :%d/healthz", port)
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await runner.cleanup()
            raise

    # -- daily midnight task -------------------------------------------------
    async def _run_daily_midnight(self) -> None:
        """Run daily tasks at midnight: send image + write day separators to logs."""
        try:
            while not self._shutdown.is_set():
                now = datetime.now()
                # Calculate seconds until next midnight
                next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                delay = (next_midnight - now).total_seconds()
                self.logger.info("Next daily task at %s (in %.1fs)", next_midnight.isoformat(), delay)
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                if self._shutdown.is_set():
                    break
                await self._execute_daily_tasks()
        except asyncio.CancelledError:
            raise

    async def _execute_daily_tasks(self) -> None:
        """Execute the daily midnight tasks."""
        alert_cfg = self.config.alert
        chat_id = alert_cfg.daily_image_chat_id or alert_cfg.telegram_chat_id
        if chat_id and alert_cfg.telegram_bot_token:
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


__all__ = ["Orchestrator"]
