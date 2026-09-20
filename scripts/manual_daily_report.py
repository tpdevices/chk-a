#!/usr/bin/env python3
"""
Manual Daily Report Generator for chk-a
Generates and sends a daily report covering data from 00:00 today to now.
Run manually when executives need immediate data.

Usage:
    sudo -u chk-a /opt/chk-a/.venv/bin/python /opt/chk-a/scripts/manual_daily_report.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add project to path
sys.path.insert(0, '/opt/chk-a')

from chk_a.config.loader import load_config
from chk_a.storage.baseline_store import BaselineStore
from chk_a.agents.ml_agent import MLAgent
from chk_a.reporting.ml_insights import generate_ml_insights
from chk_a.reporting.graph_generator import generate_summary_dashboard
from chk_a.reporting.telegram_reporter import send_daily_report_telegram
from pydantic import SecretStr


def load_env_file(path: str = '/etc/chk-a/env') -> dict:
    """Load environment variables from file."""
    env_dict = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_dict[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Could not load env file: {e}", file=sys.stderr)
    return env_dict


async def generate_today_report():
    """Generate and send daily report from midnight today to now."""

    # Load config
    print("Loading configuration...")
    config = load_config()

    # Load Telegram credentials
    env = load_env_file()
    bot_token = env.get('TELEGRAM_BOT_TOKEN')
    chat_id = env.get('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in /etc/chk-a/env", file=sys.stderr)
        return False

    # Initialize ML agent with baseline store
    print("Initializing ML agent...")
    store = BaselineStore(config.baseline_store_path)
    ml_agent = MLAgent(config.ml, store)

    # Get hostname
    import socket
    hostname = socket.gethostname()

    # Calculate today's date range: midnight to now
    now = datetime.now()
    today_midnight = datetime(now.year, now.month, now.day, 0, 0, 0)
    month_start = datetime(now.year, now.month, 1, 0, 0, 0)

    print(f"Generating report for {hostname} from {today_midnight.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        print("Generating ML insights for today's data (midnight to now)...")

        log_path = config.logging.file
        mtr_log_path = ""
        if hasattr(config, "mtr") and config.mtr.enabled:
            mtr_log_path = getattr(config.mtr, "log_path", "") or ""

        # 1. Today insights: midnight to now (fractional lookback from now)
        hours_since_midnight = (now - today_midnight).total_seconds() / 3600
        lookback_fraction = hours_since_midnight / 24.0
        # Use reference_date=today_midnight + 23:59:59 to get today's data from midnight
        today_ref = today_midnight.replace(hour=23, minute=59, second=59)

        insights_today = generate_ml_insights(
            log_path=log_path,
            lookback_days=lookback_fraction,
            mtr_log_path=mtr_log_path,
            ml_agent=ml_agent,
            reference_date=today_ref  # today 23:59:59 as reference
        )

        if not insights_today.get("summary", {}).get("total_resolvers", 0):
            print("WARNING: No data available for today's report")
            return False

        print(f"Today insights: {insights_today['summary']['total_resolvers']} resolvers")

        # 2. Month insights: Sep 1 to now (for daily heatmap)
        print("Generating ML insights for month data (Sep 1 to now) for daily heatmap...")
        month_ref = now  # now as reference
        month_lookback = (now - month_start).days + hours_since_midnight / 24.0

        insights_month = generate_ml_insights(
            log_path=log_path,
            lookback_days=month_lookback,
            mtr_log_path=mtr_log_path,
            ml_agent=ml_agent,
            reference_date=month_ref
        )

        print(f"Month insights: {insights_month['summary']['total_resolvers']} resolvers")

        # 3. Merge: use today's insights but replace daily_availability with month's
        availability_today = insights_today.get("availability", {})
        availability_month = insights_month.get("availability", {})

        for resolver, data in availability_today.items():
            if resolver in availability_month:
                # Replace daily_availability with month's (Sep 1 to now)
                data["daily_availability"] = availability_month[resolver].get("daily_availability", {})

        # Update insights with merged availability
        insights_today["availability"] = availability_today

        print(f"ML insights generated (merged): {insights_today['summary']['total_resolvers']} resolvers")

        # Generate graphs (both EN and TH) - send_daily_report_telegram will filter Thai-only
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        output_dir = Path(config.reporting.output_dir) / f"manual-daily-{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        today_str = now.strftime("%Y-%m-%d")

        en_graphs = generate_summary_dashboard(
            insights_today, output_dir, lang="en", hostname=hostname,
            report_date_context=f"Manual daily report for :{today_str} (00:00-now)"
        )
        th_graphs = generate_summary_dashboard(
            insights_today, output_dir, lang="th", hostname=hostname,
            report_date_context=f"รายงานข้อมูลวัน :{today_str} (00:00-ตอนนี้)"
        )
        all_graphs = en_graphs + th_graphs
        print(f"Generated {len(all_graphs)} graph files (EN: {len(en_graphs)}, TH: {len(th_graphs)})")

        # Send via send_daily_report_telegram (filters Thai-only, sends sequentially)
        print("Sending to Telegram...")
        bot_token_secret = SecretStr(bot_token)
        chat_id_secret = SecretStr(chat_id)

        results = await send_daily_report_telegram(
            bot_token=bot_token_secret,
            chat_id=chat_id_secret,
            ml_insights=insights_today,
            graph_paths=all_graphs,
            hostname=hostname,
            lookback_days=lookback_fraction,
        )

        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        print(f"Telegram send results: {success_count}/{total_count} successful")
        for k, v in results.items():
            status = "✓" if v else "✗"
            print(f"  {status} {k}")

        return success_count > 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Manual Daily Report Generator - chk-a")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check if running as chk-a user
    import pwd
    current_user = pwd.getpwuid(os.getuid()).pw_name
    if current_user != 'chk-a':
        print(f"WARNING: Running as '{current_user}', expected 'chk-a'")
        print("Recommended: sudo -u chk-a /opt/chk-a/.venv/bin/python /opt/chk-a/scripts/manual_daily_report.py")

    # Run async function
    success = asyncio.run(generate_today_report())

    print("=" * 60)
    if success:
        print("SUCCESS: Daily report sent successfully!")
    else:
        print("FAILED: Daily report generation/sending failed")
    print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()