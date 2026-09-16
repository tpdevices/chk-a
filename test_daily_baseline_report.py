#!/usr/bin/env python3
"""Test script: Generate daily report with baseline-based integrity (instead of Isolation Forest)."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chk_a.config.loader import load_config
from chk_a.agents.ml_agent import MLAgent
from chk_a.storage.baseline_store import BaselineStore
from chk_a.reporting.graph_generator import generate_summary_dashboard
from chk_a.reporting.telegram_reporter import (
    send_daily_report_telegram,
    create_daily_telegram_summary,
)
from chk_a.reporting.ml_insights import (
    compute_availability,
    compute_path_availability,
    _load_recent_checks,
    _load_mtr_data,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def compute_integrity_baseline_based(df, ml_agent: MLAgent) -> dict:
    """Compute integrity using baseline-based MLAgent.score() instead of Isolation Forest.
    
    For each resolver, we compute an integrity_score based on how consistent
    the resolver's observed IPs are with the learned baseline.
    
    - 100 = fully consistent with baseline
    - 0 = completely different from baseline
    """
    if df.empty:
        return {}

    results = {}
    
    # Group by resolver and FQDN to check each FQDN separately
    for resolver, group in df.groupby("resolver"):
        total_queries = len(group)
        successful = group[group["success"]]
        success_rate = len(successful) / total_queries if total_queries > 0 else 0.0
        
        # For each FQDN, check how consistent the resolver is with baseline
        fqdn_scores = []
        for fqdn, fqdn_group in group.groupby("fqdn"):
            successful_fqdn = fqdn_group[fqdn_group["success"]]
            if len(successful_fqdn) == 0:
                # All queries for this FQDN failed - score as 0
                fqdn_scores.append(0.0)
                continue
            
            # Get the most recent IPs from this resolver for this FQDN
            latest_result = successful_fqdn.iloc[-1]
            observed_ips = list(latest_result.get("ips", []))
            
            # Score against baseline using MLAgent
            anomaly_score = ml_agent.score(fqdn, observed_ips)
            # Convert anomaly_score (0=consistent, 1=anomalous) to integrity_score (0=anomalous, 100=consistent)
            # But also factor in success rate
            if anomaly_score == 0.0:
                # Consistent with baseline
                integrity = 100.0
            elif anomaly_score >= 1.0:
                # Completely different from baseline
                integrity = 0.0
            else:
                # Partial match - scale
                integrity = (1.0 - anomaly_score) * 100.0
            
            fqdn_scores.append(integrity)
        
        # Average integrity across all FQDNs for this resolver
        avg_integrity = sum(fqdn_scores) / len(fqdn_scores) if fqdn_scores else 0.0
        
        # Bonus/penalty for success rate
        # If resolver is consistently failing (0% success), that's an integrity issue
        if success_rate == 0.0:
            avg_integrity = 0.0
        
        results[resolver] = {
            "integrity_score": round(avg_integrity, 2),
            "success_rate": round(success_rate * 100, 2),
            "total_queries": total_queries,
        }
    
    return results


async def main():
    # Load config - on test VM this will read /etc/chk-a/config.yaml and /etc/chk-a/env
    config = load_config()
    log.info(f"Config loaded: fqdns={len(config.fqdns)} resolvers={len(config.resolvers)}")

    hostname = config.hostname
    lookback_days = config.reporting.daily_report_lookback_days

    # Initialize ML Agent with baseline store
    ml_config = config.ml
    baseline_store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(ml_config, baseline_store)
    log.info(f"ML Agent initialized with {len(baseline_store.all_fqdns())} FQDNs in baseline")

    # Step 1: Load recent check data
    log_path = config.logging.file
    mtr_log_path = ""
    if hasattr(config, "mtr") and config.mtr.enabled:
        mtr_log_path = getattr(config.mtr, "log_path", "") or ""

    log.info(f"Loading ML insights from log: {log_path} (lookback={lookback_days} day(s))")
    df = _load_recent_checks(log_path, lookback_days)
    
    if df.empty:
        log.warning("No check data available for ML insights")
        return

    log.info(f"Loaded {len(df)} check records")
    
    # Step 2: Compute availability (same as before)
    availability = compute_availability(df)
    log.info(f"Computed availability for {len(availability)} resolvers")
    
    # Step 3: Compute integrity using baseline-based approach
    integrity = compute_integrity_baseline_based(df, ml_agent)
    log.info(f"Computed baseline-based integrity for {len(integrity)} resolvers")
    for resolver, data in integrity.items():
        log.info(f"  {resolver}: integrity={data['integrity_score']}, success_rate={data['success_rate']}%")
    
    # Step 4: Identify anomalous resolvers (integrity < 80 or success_rate < 50%)
    anomalous = [r for r, v in integrity.items() 
                 if v.get("integrity_score", 0) < 80 or v.get("success_rate", 100) < 50]
    
    # Step 5: Compute summary
    total_queries = len(df)
    total_resolvers = len(availability)
    overall_availability = (
        sum(v["availability_pct"] for v in availability.values()) / total_resolvers
        if total_resolvers > 0
        else 0.0
    )
    
    best = max(availability.items(), key=lambda x: x[1]["availability_pct"])[0] if availability else ""
    worst = min(availability.items(), key=lambda x: x[1]["availability_pct"])[0] if availability else ""
    
    insights = {
        "summary": {
            "total_resolvers": total_resolvers,
            "total_queries": total_queries,
            "overall_availability_pct": round(overall_availability, 2),
            "anomalous_resolvers": anomalous,
            "best_resolver": best,
            "worst_resolver": worst,
        },
        "availability": availability,
        "integrity": integrity,
        "lookback_days": lookback_days,
        "generated_at": datetime.now().isoformat(),
    }
    
    log.info(f"ML insights summary: {insights['summary']}")

    # Step 6: Generate graphs
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path("/home/ipds/chk-a-reports") / f"daily-baseline-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

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

    # Step 7: Print the daily summary text
    summary_text = create_daily_telegram_summary(insights, hostname, lookback_days)
    print("\n" + "=" * 60)
    print("DAILY TELEGRAM SUMMARY (Thai - Baseline-based Integrity):")
    print("=" * 60)
    print(summary_text)
    print("=" * 60 + "\n")

    # Step 8: Send to Telegram
    if config.reporting.daily_report_telegram_enabled:
        bot_token = config.alert.telegram_bot_token
        chat_id = config.reporting.daily_report_telegram_chat_id or config.alert.telegram_chat_id

        if bot_token and chat_id:
            log.info("Sending daily report to Telegram...")
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
        else:
            log.warning("Telegram credentials not configured for daily report - skipping")
    else:
        log.info("Daily report Telegram disabled in config - skipping send")

    return {
        "success": True,
        "timestamp": timestamp,
        "lookback_days": lookback_days,
        "insights_summary": insights["summary"],
        "integrity_data": integrity,
        "graphs_generated": len(all_graphs),
    }


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nResult: {result}")