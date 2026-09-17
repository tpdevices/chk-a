#!/usr/bin/env python3
"""
Manual Monthly Report Generator for chk-a
Generates and sends a monthly report covering data from 1st of current month 00:00 to now.
Run manually when executives need immediate monthly data.

Usage:
    sudo -u chk-a /opt/chk-a/.venv/bin/python /opt/chk-a/scripts/manual_monthly_report.py
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
from chk_a.reporting.telegram_reporter import TelegramReporter
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


async def generate_current_month_report():
    """Generate and send monthly report from 1st of month 00:00 to now."""
    
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
    
    # Calculate current month range: 1st of month 00:00 to now
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1, 0, 0, 0)
    
    print(f"Generating report for {hostname} from {month_start.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Calculate lookback days from month start to now
        days_diff = (now - month_start).days + 1
        print(f"Report period: {days_diff} days (from {month_start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})")
        
        # Generate ML insights for current month data
        print("Generating ML insights for current month data...")
        
        from chk_a.reporting.ml_insights import generate_ml_insights
        
        log_path = config.logging.file
        mtr_log_path = ""
        if hasattr(config, "mtr") and config.mtr.enabled:
            mtr_log_path = getattr(config.mtr, "log_path", "") or ""
        
        # Generate insights with reference_date=now, lookback=days_diff
        # This gives us data from month_start to now
        insights = generate_ml_insights(
            log_path=log_path,
            lookback_days=days_diff,
            mtr_log_path=mtr_log_path,
            ml_agent=ml_agent,
            reference_date=now
        )
        
        if not insights.get("summary", {}).get("total_resolvers", 0):
            print("WARNING: No data available for current month report")
            return False
        
        print(f"ML insights generated: {insights['summary']['total_resolvers']} resolvers")
        
        # Generate graphs
        print("Generating graphs...")
        from chk_a.reporting.graph_generator import generate_summary_dashboard
        
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        output_dir = Path(config.reporting.output_dir) / f"manual-monthly-{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        month_str = now.strftime("%Y-%m")
        
        en_graphs = generate_summary_dashboard(
            insights, output_dir, lang="en", hostname=hostname,
            report_date_context=f"Manual monthly report for :{month_str} (1st-now)"
        )
        th_graphs = generate_summary_dashboard(
            insights, output_dir, lang="th", hostname=hostname,
            report_date_context=f"รายงานข้อมูลเดือน :{month_str} (1-ตอนนี้)"
        )
        all_graphs = en_graphs + th_graphs
        print(f"Generated {len(all_graphs)} graph files")
        
        # Send to Telegram
        print("Sending to Telegram...")
        from pydantic import SecretStr
        
        bot_token_secret = SecretStr(bot_token)
        chat_id_secret = SecretStr(chat_id)
        
        reporter = TelegramReporter(
            bot_token=bot_token_secret,
            chat_id=chat_id_secret
        )
        
        try:
            # Create custom monthly summary for "current month from 1st to now"
            month_name_th = [
                "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
            ][now.month - 1]
            
            month_str_th = f"{month_name_th} {now.year}"
            month_str_en = now.strftime("%B %Y")
            
            summary_text = (
                f"📅 <b>chk-a รายงานเดือนปัจจุบัน ({month_str_en})</b>\n"
                f"🖥️ Host: {hostname}\n"
                f"📅 เดือน: {month_str_th}\n"
                f"⏰ ช่วงเวลา: 1 ถึง {now.strftime('%d')} {month_name_th} {now.year} ({now.strftime('%H:%M')})\n"
                f"\n"
                f"📈 <b>สรุปภาพรวม</b>\n"
                f"• Resolver ทั้งหมด: {insights['summary'].get('total_resolvers', 0)}\n"
                f"• Query ทั้งหมด: {insights['summary'].get('total_queries', 0):,}\n"
                f"• Availability โดยรวม: {insights['summary'].get('overall_availability_pct', 0):.2f}%\n"
                f"• 🏆 ดีที่สุด: {insights['summary'].get('best_resolver', 'N/A')}\n"
                f"• ⚠️ ต้องปรับปรุง: {insights['summary'].get('worst_resolver', 'N/A')}\n"
                f"• 🔴 Anomaly (ML): {len(insights['summary'].get('anomalous_resolvers', []))} ตัว\n"
                f"\n"
            )
            
            # Add availability section
            availability = insights.get("availability", {})
            if availability:
                summary_text += "📊 <b>Top 10 Resolver Availability</b>\n"
                sorted_avail = sorted(
                    availability.items(), key=lambda x: x[1]["availability_pct"], reverse=True
                )[:10]
                for i, (resolver, data) in enumerate(sorted_avail, 1):
                    pct = data["availability_pct"]
                    emoji = "🟢" if pct >= 99 else "🟡" if pct >= 95 else "🔴"
                    summary_text += f"{i}. {emoji} {resolver}: {pct:.2f}%\n"
                summary_text += "\n"
            
            # Add path availability
            path_availability = insights.get("path_availability", {})
            if path_availability:
                summary_text += "🛣️ <b>Path Availability (MTR Host→Resolver)</b>\n"
                sorted_path = sorted(
                    path_availability.items(),
                    key=lambda x: x[1]["path_availability_pct"],
                    reverse=True,
                )[:10]
                for i, (resolver, data) in enumerate(sorted_path, 1):
                    pct = data["path_availability_pct"]
                    health = data.get("path_health_score", 0)
                    emoji = "🟢" if pct >= 90 else "🟡" if pct >= 70 else "🔴"
                    summary_text += f"{i}. {emoji} {resolver}: {pct:.1f}% (Health: {health:.0f})\n"
                summary_text += "\n"
            
            # Add integrity
            integrity = insights.get("integrity", {})
            if integrity:
                summary_text += "🔐 <b>Response Integrity (Baseline Consistency)</b>\n"
                sorted_integrity = sorted(
                    integrity.items(), key=lambda x: x[1].get("integrity_score", 0), reverse=True
                )[:10]
                for i, (resolver, data) in enumerate(sorted_integrity, 1):
                    score = data.get("integrity_score", 0)
                    success_rate = data.get("success_rate", 0)
                    emoji = "🟢" if score >= 95 else "🟡" if score >= 80 else "🔴"
                    summary_text += f"{i}. {emoji} {resolver}: {score:.1f} (✓{success_rate:.0f}%)\n"
                summary_text += "\n"
            
            # Anomalous resolvers
            anomalous = insights["summary"].get("anomalous_resolvers", [])
            if anomalous:
                summary_text += "🔴 <b>Resolver ปัญหา Integrity (ML Detected)</b>\n"
                integrity = insights.get("integrity", {})
                for r in anomalous[:5]:
                    score = integrity.get(r, {}).get("integrity_score", 0)
                    success = integrity.get(r, {}).get("success_rate", 0)
                    summary_text += f"• {r} (Integrity: {score:.1f}, Success: {success:.0f}%)\n"
                summary_text += "\n"
            
            summary_text += f"📈 กราฟแนบด้านล่าง (Availability / Path / Integrity / Anomaly)\n"
            summary_text += f"📊 ข้อมูลตั้งแต่วันที่ 1 ถึง {now.strftime('%d')} {month_name_th} {now.year}\n"
            
            # Send summary message
            await reporter.send_message(summary_text)
            
            # Generate and send graphs
            timestamp = now.strftime("%Y%m%d-%H%M%S")
            output_dir = Path(config.reporting.output_dir) / f"manual-monthly-{timestamp}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            from chk_a.reporting.graph_generator import generate_summary_dashboard
            
            en_graphs = generate_summary_dashboard(
                insights, output_dir, lang="en", hostname=hostname,
                report_date_context=f"Manual monthly report for :{month_str_en} (1st-now)"
            )
            th_graphs = generate_summary_dashboard(
                insights, output_dir, lang="th", hostname=hostname,
                report_date_context=f"รายงานข้อมูลเดือน :{month_str_th} (1-ตอนนี้)"
            )
            all_graphs = en_graphs + th_graphs
            
            print(f"Generated {len(all_graphs)} graph files")
            
            # Send graphs concurrently
            tasks = []
            for graph_path in all_graphs:
                caption = graph_path.stem.replace("-", " ").title()
                tasks.append(reporter.send_photo(graph_path, caption))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r is True)
                print(f"Sent {success_count}/{len(tasks)} graphs to Telegram")
            
            await reporter.close()
            return True
            
        finally:
            await reporter.close()
            
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Manual Monthly Report Generator - chk-a")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Check if running as chk-a user
    import pwd
    current_user = pwd.getpwuid(os.getuid()).pw_name
    if current_user != 'chk-a':
        print(f"WARNING: Running as '{current_user}', expected 'chk-a'")
        print("Recommended: sudo -u chk-a /opt/chk-a/.venv/bin/python /opt/chk-a/scripts/manual_monthly_report.py")
    
    # Run async function
    success = asyncio.run(generate_current_month_report())
    
    print("=" * 60)
    if success:
        print("SUCCESS: Monthly report sent successfully!")
    else:
        print("FAILED: Monthly report generation/sending failed")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()