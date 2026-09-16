#!/usr/bin/env python3
"""Test script to generate and send a sample daily report to Telegram (baseline-based integrity)."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chk_a.config.loader import load_config
from chk_a.reporting.ml_insights import generate_ml_insights
from chk_a.reporting.graph_generator import generate_summary_dashboard
from chk_a.reporting.telegram_reporter import (
    send_daily_report_telegram,
    create_daily_telegram_summary,
)
from chk_a.storage.baseline_store import BaselineStore
from chk_a.agents.ml_agent import MLAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def main():
    # Load config - on test VM this will read /etc/chk-a/config.yaml and /etc/chk-a/env
    config = load_config()
    log.info(f"Config loaded: fqdns={len(config.fqdns)} resolvers={len(config.resolvers)}")

    hostname = config.hostname
    lookback_days = config.reporting.daily_report_lookback_days

    # Step 1: Generate ML insights from today's data (what's currently in the log)
    log_path = config.logging.file
    mtr_log_path = ""
    if hasattr(config, "mtr") and config.mtr.enabled:
        mtr_log_path = getattr(config.mtr, "log_path", "") or ""

    log.info(f"Generating ML insights from log: {log_path} (lookback={lookback_days} day(s))")

    # Create MLAgent for baseline-based integrity scoring
    store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(config.ml, store)

    insights = generate_ml_insights(log_path, lookback_days, mtr_log_path, ml_agent=ml_agent)
    log.info(
        "Daily ML insights generated: %d resolvers, %.2f%% overall availability",
        insights["summary"]["total_resolvers"],
        insights["summary"]["overall_availability_pct"],
    )

    # Step 2: Generate graphs for daily report
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path("/home/ipds/chk-a-reports") / f"daily-test-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use today's date for title context (since we're using current log data)
    today_str = datetime.now().strftime("%Y-%m-%d")

    en_graphs = generate_summary_dashboard(
        insights, output_dir, lang="en", hostname=hostname,
        report_date_context=f"Daily report for :{today_str}"
    )
    th_graphs = generate_summary_dashboard(
        insights, output_dir, lang="th", hostname=hostname,
        report_date_context=f"รายงานข้อมูลประจำวัน :{today_str}"
    )
    all_graphs = en_graphs + th_graphs
    log.info(f"Generated {len(all_graphs)} graph files for daily report")

    # Step 3: Print the daily summary text that would be sent
    summary_text = create_daily_telegram_summary(insights, hostname, lookback_days)
    print("\n" + "=" * 60)
    print("DAILY TELEGRAM SUMMARY (Thai):")
    print("=" * 60)
    print(summary_text)
    print("=" * 60 + "\n")

    # Step 4: Send to Telegram
    if config.reporting.daily_report_telegram_enabled:
        bot_token = config.alert.telegram_bot_token
        chat_id = config.reporting.daily_report_telegram_chat_id or config.alert.telegram_chat_id

        if bot_token and chat_id:
            log.info("Sending daily report to Telegram...")
            from pydantic import SecretStr
            # Extract string value from SecretStr if needed
            chat_id_str = chat_id.get_secret_value() if isinstance(chat_id, SecretStr) else str(chat_id)
            telegram_results = await send_daily_report_telegram(
                bot_token=bot_token,
                chat_id=SecretStr(chat_id_str),
                ml_insights=insights,
                graph_paths=all_graphs,
                hostname=hostname,
                lookback_days=lookback_days,
            )
            log.info(f"Telegram results: {telegram_results}")
        else:
            log.warning("Telegram credentials not configured for daily report - skipping")
    else:
        log.info("Daily report Telegram disabled in config - skipping send")

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "lookback_days": lookback_days,
        "insights_summary": insights["summary"],
        "graphs_generated": len(all_graphs),
    }


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nResult: {result}")