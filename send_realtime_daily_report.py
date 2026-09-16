#!/usr/bin/env python3
"""Send real-time daily report (midnight to now) to Telegram - same format as 06:00 report."""

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

    # Reference date: NOW (current time)
    # Lookback: from midnight today to now
    from datetime import timezone, timedelta
    default_tz = timezone(timedelta(hours=7))
    now = datetime.now(default_tz)
    midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate hours since midnight for dynamic lookback
    hours_since_midnight = (now - midnight_today).total_seconds() / 3600
    # Use 1 day lookback but with reference_date = now to get data from midnight to now
    # _load_recent_checks will filter by timestamp >= cutoff (now - 1 day = midnight yesterday)
    # But we want midnight TODAY. So we need reference_date = now and lookback that covers midnight today.
    # Better: use reference_date = now, lookback_days = 1, then filter to midnight_today in the function
    # Actually _load_recent_checks filters by timestamp >= cutoff where cutoff = reference_date - lookback_days
    # So reference_date=now, lookback_days=1 gives cutoff = yesterday same time
    # We need a different approach: reference_date = now, but we want data from midnight_today
    
    # Let's use reference_date = now and lookback to cover from midnight
    # Since midnight is at most 24 hours ago, lookback_days=1 with reference_date=now works
    # Then we'll filter the dataframe to only keep records from midnight_today onwards
    
    reference_date = now
    lookback_days = 1

    log.info(f"Loading today's data (midnight to now): {midnight_today} to {now}")

    store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(config.ml, store)

    df = _load_recent_checks(log_path, lookback_days, reference_date=reference_date)
    
    # Filter to only today's data (from midnight)
    # _load_recent_checks returns naive timestamps, so make midnight_today naive too
    midnight_naive = midnight_today.replace(tzinfo=None)
    df = df[df["timestamp"] >= midnight_naive]
    
    log.info(f"Loaded {len(df)} records from {df['timestamp'].dt.date.nunique()} unique dates")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Hours since midnight: {hours_since_midnight:.1f}")

    if df.empty:
        log.warning("No data for today yet!")
        return {"success": False, "error": "No data for today"}

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
    output_dir = Path("/home/ipds/chk-a-reports") / f"realtime-daily-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    en_graphs = generate_summary_dashboard(
        insights, output_dir, lang="en", hostname=hostname,
        report_date_context=f"Real-time Daily Report ({time_str}): {today_str}"
    )
    th_graphs = generate_summary_dashboard(
        insights, output_dir, lang="th", hostname=hostname,
        report_date_context=f"รายงานวันนี้เรียลไทม์ ({time_str}): {today_str}"
    )
    all_graphs = en_graphs + th_graphs
    log.info(f"Generated {len(all_graphs)} graph files")

    # Print summary
    summary_text = create_daily_telegram_summary(insights, hostname, lookback_days)
    # Customize header for real-time report
    summary_text = summary_text.replace(
        f"chk-a รายงานรายวัน ({now.strftime('%d/%m/%Y')})",
        f"chk-a รายงานวันนี้เรียลไทม์ ({time_str} น.)"
    )
    
    print("\n" + "=" * 70)
    print(f"REAL-TIME DAILY REPORT (Thai) - {today_str} 00:00 to {time_str}:")
    print("=" * 70)
    print(summary_text)
    print("=" * 70 + "\n")

    # Send to Telegram
    if config.reporting.daily_report_telegram_enabled:
        bot_token = config.alert.telegram_bot_token
        chat_id = config.reporting.daily_report_telegram_chat_id or config.alert.telegram_chat_id

        if bot_token and chat_id:
            log.info("Sending real-time daily report to Telegram...")
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
        "period_start": midnight_today.isoformat(),
        "period_end": now.isoformat(),
        "hours_covered": round(hours_since_midnight, 1),
        "total_records": len(df),
        "insights_summary": insights["summary"],
        "graphs_generated": len(all_graphs),
    }


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nFinal Result: {result}")