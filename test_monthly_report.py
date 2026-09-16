#!/usr/bin/env python3
"""Test monthly report generation using 30 days of rotated log data."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chk_a.config.loader import load_config
from chk_a.reporting.ml_insights import (
    _load_recent_checks, compute_availability, compute_integrity, generate_ml_insights
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
    # Load config
    config = load_config()
    log.info(f"Config loaded: fqdns={len(config.fqdns)} resolvers={len(config.resolvers)}")

    hostname = config.hostname

    log_path = config.logging.file
    mtr_log_path = ""
    if hasattr(config, "mtr") and config.mtr.enabled:
        mtr_log_path = getattr(config.mtr, "log_path", "") or ""

    # Reference date: today (2026-09-15), lookback=30 days for monthly
    from datetime import timezone, timedelta
    default_tz = timezone(timedelta(hours=7))
    reference_date = datetime(2026, 9, 15, 10, 0, 0, tzinfo=default_tz)
    lookback_days = 30

    log.info(f"Generating ML insights from log: {log_path} (lookback={lookback_days} days, reference_date={reference_date})")

    # Create MLAgent for baseline-based integrity scoring
    store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(config.ml, store)

    # Load data from rotated logs (30 days)
    df = _load_recent_checks(log_path, lookback_days, reference_date=reference_date)
    log.info(f"Loaded {len(df)} records from rotated logs (30 days)")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Unique dates: {df['timestamp'].dt.date.nunique()}")
    
    if df.empty:
        log.error("No data loaded!")
        return {"success": False, "error": "No data"}
    
    availability = compute_availability(df)
    integrity = compute_integrity(df, ml_agent=ml_agent)
    
    insights = {
        "availability": availability,
        "integrity": integrity,
        "summary": {
            "total_resolvers": len(availability),
            "total_queries": len(df),
            "overall_availability_pct": sum(a["availability_pct"] for a in availability.values()) / len(availability) if availability else 0,
            "anomalous_resolvers": [r for r, i in integrity.items() if i.get("is_anomaly", False)],
            "best_resolver": max(availability.items(), key=lambda x: x[1]["availability_pct"])[0] if availability else None,
            "worst_resolver": min(availability.items(), key=lambda x: x[1]["availability_pct"])[0] if availability else None,
        }
    }

    log.info(
        "Monthly ML insights generated: %d resolvers, %.2f%% overall availability",
        insights["summary"]["total_resolvers"],
        insights["summary"]["overall_availability_pct"],
    )

    # Step 2: Generate graphs for monthly report
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path("/home/ipds/chk-a-reports") / f"monthly-test-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    month_str = (reference_date - timedelta(days=1)).strftime("%Y-%m")

    en_graphs = generate_summary_dashboard(
        insights, output_dir, lang="en", hostname=hostname,
        report_date_context=f"Monthly report for :{month_str}"
    )
    th_graphs = generate_summary_dashboard(
        insights, output_dir, lang="th", hostname=hostname,
        report_date_context=f"รายงานข้อมูลประจำเดือน :{month_str}"
    )
    all_graphs = en_graphs + th_graphs
    log.info(f"Generated {len(all_graphs)} graph files for monthly report")

    # Step 3: Print the summary text
    summary_text = create_daily_telegram_summary(insights, hostname, lookback_days)
    print("\n" + "=" * 60)
    print("MONTHLY TELEGRAM SUMMARY (Thai):")
    print("=" * 60)
    print(summary_text)
    print("=" * 60 + "\n")

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