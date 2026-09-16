#!/usr/bin/env python3
"""Test script to generate and send a sample daily report to Telegram using yesterday's mock data."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chk_a.config.loader import load_config
from chk_a.reporting.ml_insights import generate_ml_insights, _load_recent_checks
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

    # Use mock data file for yesterday (2026-09-14)
    log_path = "/home/ipds/chk-a-test-data/checks_yesterday.jsonl"
    mtr_log_path = ""
    if hasattr(config, "mtr") and config.mtr.enabled:
        mtr_log_path = getattr(config.mtr, "log_path", "") or ""

    # For yesterday's data, use yesterday end as reference date
    yesterday_end = datetime(2026, 9, 14, 23, 59, 59)
    log.info(f"Generating ML insights from MOCK log: {log_path} (lookback={lookback_days} day(s), reference_date={yesterday_end})")

    # Verify data loads
    df = _load_recent_checks(log_path, lookback_days, reference_date=yesterday_end)
    log.info(f"Loaded {len(df)} records from mock data file")
    if df.empty:
        log.error("No data loaded! Checking file contents...")
        log.info(f"File exists: {Path(log_path).is_file()}")
        with open(log_path) as f:
            for i, line in enumerate(f):
                if i < 3:
                    log.info(f"Line {i}: {line.strip()[:100]}")
                else:
                    break
        return {"success": False, "error": "no data loaded"}

    # Create MLAgent for baseline-based integrity scoring
    store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(config.ml, store)

    insights = generate_ml_insights(log_path, lookback_days, mtr_log_path, ml_agent=ml_agent, reference_date=yesterday_end)
    log.info(
        "Daily ML insights generated: %d resolvers, %.2f%% overall availability",
        insights["summary"]["total_resolvers"],
        insights["summary"]["overall_availability_pct"],
    )

    # Step 2: Generate graphs for daily report
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path("/home/ipds/chk-a-reports") / f"daily-yesterday-test-{timestamp}"
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
    log.info(f"Generated {len(all_graphs)} graph files for daily report")

    # Step 3: Print the daily summary text that would be sent
    summary_text = create_daily_telegram_summary(insights, hostname, lookback_days)
    print("\n" + "=" * 60)
    print("DAILY TELEGRAM SUMMARY (Thai) - USING YESTERDAY'S MOCK DATA:")
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
        "timestamp": timestamp,
        "lookback_days": lookback_days,
        "insights_summary": insights["summary"],
        "graphs_generated": len(all_graphs),
    }


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nResult: {result}")