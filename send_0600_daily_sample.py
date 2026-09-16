#!/usr/bin/env python3
"""Send 06:00 AM daily report sample using yesterday's data (2026-09-14)."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from chk_a.config.loader import load_config
from chk_a.reporting.ml_insights import (
    _load_recent_checks, compute_availability, compute_integrity
)
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
    config = load_config()
    log.info(f"Config loaded: fqdns={len(config.fqdns)} resolvers={len(config.resolvers)}")

    hostname = config.hostname
    log_path = config.logging.file

    # Reference date: TODAY at 06:00:00 (simulating daily report run time)
    # Lookback 1 day = yesterday (2026-09-14)
    from datetime import timezone, timedelta
    default_tz = timezone(timedelta(hours=7))
    reference_date = datetime(2026, 9, 15, 6, 0, 0, tzinfo=default_tz)  # Today 06:00
    lookback_days = 1

    log.info(f"Loading yesterday's data (reference={reference_date}, lookback={lookback_days} day)...")

    store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(config.ml, store)

    df = _load_recent_checks(log_path, lookback_days, reference_date=reference_date)
    log.info(f"Loaded {len(df)} records from {df['timestamp'].dt.date.nunique()} unique dates")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    availability = compute_availability(df)
    integrity = compute_integrity(df, ml_agent=ml_agent)

    insights = {
        "availability": availability,
        "integrity": integrity,
        "path_availability": {},
        "mtr": {},
        "summary": {
            "total_resolvers": len(availability),
            "total_queries": len(df),
            "overall_availability_pct": sum(a["availability_pct"] for a in availability.values()) / len(availability) if availability else 0,
            "anomalous_resolvers": [r for r, i in integrity.items() if i.get("is_anomaly", False)],
            "best_resolver": max(availability.items(), key=lambda x: x[1]["availability_pct"])[0] if availability else None,
            "worst_resolver": min(availability.items(), key=lambda x: x[1]["availability_pct"])[0] if availability else None,
        },
        "generated_at": datetime.now().isoformat(),
        "lookback_days": lookback_days,
    }

    # Generate graphs
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path("/home/ipds/chk-a-reports") / f"daily-0600-sample-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    yesterday_str = (reference_date - timedelta(days=1)).strftime("%Y-%m-%d")

    en_graphs = generate_summary_dashboard(
        insights, output_dir, lang="en", hostname=hostname,
        report_date_context=f"Daily Report 06:00: {yesterday_str}"
    )
    th_graphs = generate_summary_dashboard(
        insights, output_dir, lang="th", hostname=hostname,
        report_date_context=f"รายงานประจำวัน 06:00 น.: {yesterday_str}"
    )
    all_graphs = en_graphs + th_graphs
    log.info(f"Generated {len(all_graphs)} graph files")

    # Print summary
    summary_text = create_daily_telegram_summary(insights, hostname, lookback_days)
    print("\n" + "=" * 70)
    print("06:00 DAILY REPORT SAMPLE (Thai) - Yesterday's Data:")
    print("=" * 70)
    print(summary_text)
    print("=" * 70 + "\n")

    # Send to Telegram
    if config.reporting.daily_report_telegram_enabled:
        bot_token = config.alert.telegram_bot_token
        chat_id = config.reporting.daily_report_telegram_chat_id or config.alert.telegram_chat_id

        if bot_token and chat_id:
            log.info("Sending 06:00 daily report sample to Telegram...")
            from pydantic import SecretStr
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
            print(f"\n✅ Telegram sent successfully!")
            for key, val in telegram_results.items():
                print(f"   {key}: {val}")
        else:
            log.warning("Telegram credentials not configured")
    else:
        log.info("Daily report Telegram disabled in config")

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "reference_date": reference_date.isoformat(),
        "lookback_days": lookback_days,
        "total_records": len(df),
        "insights_summary": insights["summary"],
        "graphs_generated": len(all_graphs),
    }


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nFinal Result: {result}")