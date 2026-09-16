"""Monthly report orchestrator for chk-a.

This module coordinates the entire monthly report generation pipeline:
1. Load ML insights from historical check data
2. Generate graphs
3. Create PDF reports (English + Thai)
4. Send summary + graphs to Telegram
5. Send full PDF reports via email
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config.loader import AppConfig

# Late import to avoid circular dependency
from ..agents.ml_agent import MLAgent
from .ml_insights import generate_ml_insights
from .graph_generator import generate_summary_dashboard, generate_summary_dashboard_th
from .pdf_generator import generate_pdf_report_en, generate_pdf_report_th
from .email_sender import EmailSender, create_email_body
from .telegram_reporter import send_monthly_report_telegram

log = logging.getLogger(__name__)


class MonthlyReportGenerator:
    """Orchestrates monthly report generation and delivery."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.reporting_config = config.reporting
        self.hostname = config.hostname

    def _get_timestamp(self) -> str:
        """Generate timestamp for filenames: YYYYMMDD-HHMMSS"""
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def _get_output_paths(self, timestamp: str) -> dict[str, Path]:
        """Generate output file paths for all report artifacts."""
        output_dir = Path(self.reporting_config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        fmt = self.reporting_config.filename_format
        base = fmt.replace("{timestamp}", timestamp).replace("{ext}", "")

        return {
            "dir": output_dir,
            "pdf_en": output_dir / f"{base}en.pdf",
            "pdf_th": output_dir / f"{base}th.pdf",
            "graphs_dir": output_dir / f"graphs-{timestamp}",
        }

    def generate_insights(self) -> dict[str, Any]:
        """Step 1: Generate ML insights from historical data."""
        log.info("Generating ML insights from log data...")
        log_path = self.config.logging.file
        lookback = self.reporting_config.lookback_days

        # MTR log path
        mtr_log_path = ""
        if hasattr(self.config, "mtr") and self.config.mtr.enabled:
            mtr_log_path = getattr(self.config.mtr, "log_path", "") or ""

        # Create MLAgent for baseline-based integrity scoring
        from ..storage.baseline_store import BaselineStore
        store = BaselineStore(self.config.baseline_store_path)
        ml_agent = MLAgent(self.config.ml, store)

        insights = generate_ml_insights(log_path, lookback, mtr_log_path, ml_agent=ml_agent)
        log.info(
            "ML insights generated: %d resolvers, %.2f%% overall availability",
            insights["summary"]["total_resolvers"],
            insights["summary"]["overall_availability_pct"],
        )
        return insights

    def generate_graphs(self, insights: dict[str, Any], graphs_dir: Path) -> list[Path]:
        """Step 2: Generate all graphs."""
        log.info("Generating graphs...")
        graphs_dir.mkdir(parents=True, exist_ok=True)

        # Calculate last month for title context
        lastmonth = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

        # Generate English graphs with date context in title
        en_graphs = generate_summary_dashboard(
            insights, graphs_dir, lang="en", hostname=self.hostname,
            report_date_context=f"Monthly report for :{lastmonth}"
        )
        # Generate Thai graphs (separate files for Thai labels)
        th_graphs = generate_summary_dashboard(
            insights, graphs_dir, lang="th", hostname=self.hostname,
            report_date_context=f"รายงานข้อมูลของเดือน :{lastmonth}"
        )

        all_graphs = en_graphs + th_graphs
        log.info("Generated %d graph files", len(all_graphs))
        return all_graphs

    def generate_pdfs(
        self,
        insights: dict[str, Any],
        graph_paths: list[Path],
        pdf_en_path: Path,
        pdf_th_path: Path,
    ) -> tuple[Path, Path]:
        """Step 3: Generate PDF reports in English and Thai."""
        log.info("Generating PDF reports...")

        # Filter graphs for PDF embedding (use English versions)
        pdf_graphs = [p for p in graph_paths if not p.name.endswith("-th.png")]

        generate_pdf_report_en(insights, pdf_graphs, pdf_en_path, hostname=self.hostname)
        generate_pdf_report_th(insights, pdf_graphs, pdf_th_path, hostname=self.hostname)

        log.info("PDF reports generated: %s, %s", pdf_en_path.name, pdf_th_path.name)
        return pdf_en_path, pdf_th_path

    async def send_telegram(
        self,
        insights: dict[str, Any],
        graph_paths: list[Path],
        pdf_paths: dict[str, Path] | None = None,
    ) -> dict[str, bool]:
        """Step 4: Send summary and graphs to Telegram."""
        if not self.reporting_config.telegram_enabled:
            log.info("Telegram reporting disabled - skipping")
            return {}

        # Use alert config for bot token and chat_id if not overridden
        bot_token = self.config.alert.telegram_bot_token
        chat_id = self.reporting_config.telegram_chat_id or self.config.alert.telegram_chat_id

        if not bot_token or not chat_id:
            log.warning("Telegram credentials not configured - skipping")
            return {}

        log.info("Sending monthly report to Telegram...")
        results = await send_monthly_report_telegram(
            bot_token=bot_token,
            chat_id=chat_id,
            ml_insights=insights,
            graph_paths=graph_paths,
            pdf_paths=pdf_paths,
            lang="th",  # Thai summary for Telegram
        )
        return results

    def send_email(
        self,
        insights: dict[str, Any],
        pdf_en_path: Path,
        pdf_th_path: Path,
    ) -> bool:
        """Step 5: Send full PDF reports via email."""
        if not self.reporting_config.email_enabled:
            log.info("Email reporting disabled - skipping")
            return False

        smtp_host = self.reporting_config.smtp_host
        smtp_port = self.reporting_config.smtp_port
        username = self.reporting_config.smtp_username
        password = self.reporting_config.smtp_password
        use_tls = self.reporting_config.email_use_tls
        from_addr = self.reporting_config.email_from
        to_addrs = self.reporting_config.email_to

        if not all([smtp_host, from_addr, to_addrs]):
            log.warning("Email configuration incomplete - skipping")
            return False

        log.info("Sending monthly report via email...")

        sender = EmailSender(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=username,
            password=password,
            use_tls=use_tls,
        )

        # Create email bodies
        body_text_en, body_html_en = create_email_body(insights, lang="en")
        body_text_th, body_html_th = create_email_body(insights, lang="th")

        # Combine both languages
        body_text = body_text_en + "\n\n" + "=" * 50 + "\n\n" + body_text_th
        body_html = body_html_en + "<hr>" + body_html_th

        attachments = [pdf_en_path, pdf_th_path]

        subject = f"chk-a Monthly DNS Resolver Report - {datetime.now().strftime('%Y-%m-%d')}"

        return sender.send_report(
            from_addr=from_addr,
            to_addrs=to_addrs,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )

    def run(self) -> dict[str, Any]:
        """Execute the complete monthly report generation pipeline.

        Returns a dict with results and generated file paths.
        """
        timestamp = self._get_timestamp()
        paths = self._get_output_paths(timestamp)

        results = {
            "timestamp": timestamp,
            "success": False,
            "steps": {},
            "files": {},
        }

        try:
            # Step 1: ML Insights
            insights = self.generate_insights()
            results["steps"]["insights"] = True
            results["insights_summary"] = insights["summary"]

            # Step 2: Graphs
            graph_paths = self.generate_graphs(insights, paths["graphs_dir"])
            results["steps"]["graphs"] = True
            results["files"]["graphs"] = [str(p) for p in graph_paths]

            # Step 3: PDFs
            pdf_en, pdf_th = self.generate_pdfs(
                insights, graph_paths, paths["pdf_en"], paths["pdf_th"]
            )
            results["steps"]["pdfs"] = True
            results["files"]["pdf_en"] = str(pdf_en)
            results["files"]["pdf_th"] = str(pdf_th)

            # Step 4: Telegram (async)
            pdf_paths_for_telegram = {"en": pdf_en, "th": pdf_th}
            telegram_results = asyncio.run(
                self.send_telegram(insights, graph_paths, pdf_paths_for_telegram)
            )
            results["steps"]["telegram"] = telegram_results

            # Step 5: Email
            email_sent = self.send_email(insights, pdf_en, pdf_th)
            results["steps"]["email"] = email_sent

            results["success"] = True
            log.info("Monthly report generation completed successfully")

        except Exception as e:
            log.exception("Monthly report generation failed: %s", e)
            results["error"] = str(e)

        return results


def generate_monthly_report(config: AppConfig) -> dict[str, Any]:
    """Convenience function to generate monthly report.

    Can be called directly or scheduled.
    """
    generator = MonthlyReportGenerator(config)
    return generator.run()


# For manual testing / CLI invocation
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    from ..config.loader import load_config

    config = load_config()
    result = generate_monthly_report(config)

    print(f"Success: {result['success']}")
    print(f"Files: {result.get('files', {})}")
    if not result["success"]:
        print(f"Error: {result.get('error')}")
        sys.exit(1)


# =============================================================================
# DAILY REPORT (7:00 AM) - lookback 1 day (yesterday)
# =============================================================================
async def generate_daily_report(config: AppConfig) -> dict[str, Any]:
    """Generate daily report for yesterday and send to Telegram.

    Reports on:
    - Availability of each resolver
    - Path Availability (MTR) to each resolver
    - Integrity of resolver responses
    All with ML insights (anomaly detection via EMA + entropy)

    Sends: Thai text summary + graphs to Telegram
    """
    import logging
    from datetime import datetime, timedelta

    log = logging.getLogger(__name__)

    # Use daily report config
    reporting_config = config.reporting
    lookback = reporting_config.daily_report_lookback_days
    hostname = config.hostname

    log.info("Generating daily report (lookback=%d day(s))", lookback)

    # Step 1: Generate ML insights from yesterday's data
    log_path = config.logging.file
    mtr_log_path = ""
    if hasattr(config, "mtr") and config.mtr.enabled:
        mtr_log_path = getattr(config.mtr, "log_path", "") or ""

    from .ml_insights import generate_ml_insights
    from ..storage.baseline_store import BaselineStore
    from ..agents.ml_agent import MLAgent

    # Create MLAgent for baseline-based integrity scoring
    store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(config.ml, store)

    # For daily report, use yesterday as reference date to get yesterday's data
    yesterday_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) - timedelta(days=1)
    insights = generate_ml_insights(log_path, lookback, mtr_log_path, ml_agent=ml_agent, reference_date=yesterday_end)
    log.info(
        "Daily ML insights generated: %d resolvers, %.2f%% overall availability",
        insights["summary"]["total_resolvers"],
        insights["summary"]["overall_availability_pct"],
    )

    # Step 2: Generate graphs for daily report
    from .graph_generator import generate_summary_dashboard

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(reporting_config.output_dir) / f"daily-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Calculate yesterday for title context
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    en_graphs = generate_summary_dashboard(
        insights, output_dir, lang="en", hostname=hostname,
        report_date_context=f"Daily report for :{yesterday}"
    )
    th_graphs = generate_summary_dashboard(
        insights, output_dir, lang="th", hostname=hostname,
        report_date_context=f"รายงานข้อมูลของวัน :{yesterday}"
    )
    all_graphs = en_graphs + th_graphs
    log.info("Generated %d graph files for daily report", len(all_graphs))

    # Step 3: Send to Telegram (Thai summary + graphs)
    telegram_results = {}
    if reporting_config.daily_report_telegram_enabled:
        bot_token = config.alert.telegram_bot_token
        chat_id = reporting_config.daily_report_telegram_chat_id or config.alert.telegram_chat_id

        if bot_token and chat_id:
            from .telegram_reporter import send_daily_report_telegram

            log.info("Sending daily report to Telegram...")
            telegram_results = await send_daily_report_telegram(
                bot_token=bot_token,
                chat_id=chat_id,
                ml_insights=insights,
                graph_paths=all_graphs,
                hostname=hostname,
                lookback_days=lookback,
            )
        else:
            log.warning("Telegram credentials not configured for daily report - skipping")

    result = {
        "success": True,
        "timestamp": timestamp,
        "lookback_days": lookback,
        "insights_summary": insights["summary"],
        "graphs_generated": len(all_graphs),
        "telegram_sent": telegram_results,
    }

    log.info("Daily report generation completed successfully")
    return result
