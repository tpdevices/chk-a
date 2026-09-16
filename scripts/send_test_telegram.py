#!/usr/bin/env python3
"""
Send example anomaly and recovery Telegram messages with images.
Run on the test VM (192.168.56.122) where TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are configured.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chk_a.agents.alert_agent import AlertAgent
from chk_a.config.loader import load_config
from chk_a.models.schemas import AlertConfig, AnomalyEvent
from chk_a.reporting.telegram_reporter import TelegramReporter
from chk_a.utils.logger import setup_logger


async def send_test_messages() -> None:
    # Load config (reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env)
    cfg = load_config()

    if not cfg.alert.telegram_bot_token or cfg.alert.telegram_bot_token == "${TELEGRAM_BOT_TOKEN}":
        print("ERROR: TELEGRAM_BOT_TOKEN not configured")
        sys.exit(1)
    if not cfg.alert.telegram_chat_id or cfg.alert.telegram_chat_id == "${TELEGRAM_CHAT_ID}":
        print("ERROR: TELEGRAM_CHAT_ID not configured")
        sys.exit(1)

    # Create Telegram client
    telegram = TelegramReporter(
        bot_token=cfg.alert.telegram_bot_token,
        chat_id=cfg.alert.telegram_chat_id,
    )

    # Create AlertAgent with all required parameters - use writable paths for test
    test_log_dir = Path("/tmp/chk-a-test")
    test_log_dir.mkdir(exist_ok=True)

    alert_config = AlertConfig(
        telegram_bot_token=cfg.alert.telegram_bot_token,
        telegram_chat_id=cfg.alert.telegram_chat_id,
        dedup_window_minutes=cfg.alert.dedup_window_minutes,
        rate_limit_per_hour=cfg.alert.rate_limit_per_hour,
        alert_log_path=str(test_log_dir / "alerts.jsonl"),
        alert_text_log_path=str(test_log_dir / "alerts.log"),
        dedup_cache_path=str(test_log_dir / "dedup_cache.json"),
    )

    logger = setup_logger("chk_a.alert.test")

    agent = AlertAgent(
        config=alert_config,
        logger=logger,
        telegram_client=telegram,
        alert_log_path=str(test_log_dir / "alerts.jsonl"),
        alert_text_log_path=str(test_log_dir / "alerts.log"),
        hostname="test-vm",
        anomaly_image_path="img/priority.jpg",
        recovery_image_path="img/ok.jpg",
    )

    # Event ID format: {hostname}-YYYYMMDD-HHmmss
    event_id = f"test-vm-{datetime.now():%Y%m%d-%H%M%S}"

    print(f"Sending ANOMALY example (Event ID: {event_id})...")

    # Simulate anomaly event
    anomaly_event = AnomalyEvent(
        fqdn="example.com",
        type="baseline_deviation",
        severity="warning",
        details={
            "event_type": "anomaly",
            "event_id": event_id,
            "anomaly_type": "baseline_deviation",
            "cause": "DNS resolution latency exceeded baseline by 245%",
            "last_unreachable_ip": "192.168.1.100",
            "resolver_name": "1.1.1.1",
            "observed_ips": ["192.168.1.50", "192.168.1.51"],
            "baseline_ips": ["192.168.1.50"],
            "all_results": [
                {"resolver": "1.1.1.1", "success": True, "ips": ["192.168.1.50", "192.168.1.51"]},
                {"resolver": "8.8.8.8", "success": True, "ips": ["192.168.1.50"]},
            ],
            "majority_ips": ["192.168.1.50"],
            "consensus_score": 0.67,
            "resolver_count": 3,
        },
        timestamp=datetime.now(),
        hostname="test-vm",
        resolver_name="1.1.1.1",
    )

    success = await agent.maybe_alert(anomaly_event)
    print(f"Anomaly alert sent: {success}")

    # Wait a moment between messages
    await asyncio.sleep(2)

    print(f"\nSending RECOVERY example (Event ID: {event_id})...")

    # Simulate recovery event with duration info
    start_time = datetime.now() - timedelta(minutes=15, seconds=30)
    recovery_event = AnomalyEvent(
        fqdn="example.com",
        type="recovery",
        severity="info",
        details={
            "event_type": "recovery",
            "event_id": event_id,
            "original_anomaly_type": "baseline_deviation",
            "anomaly_start_time": start_time.isoformat(),
            "anomaly_end_time": datetime.now().isoformat(),
            "duration_human": "15 นาที 30 วินาที",
            "duration_seconds": 930.0,
            "ml_baseline_stability": 0.87,
            "ml_recovery_confidence": 0.92,
            "last_unreachable_ip": "192.168.1.100",
            "resolver_name": "1.1.1.1",
            "observed_ips": ["192.168.1.50"],
            "baseline_ips": ["192.168.1.50"],
            "all_results": [
                {"resolver": "1.1.1.1", "success": True, "ips": ["192.168.1.50"]},
                {"resolver": "8.8.8.8", "success": True, "ips": ["192.168.1.50"]},
            ],
            "majority_ips": ["192.168.1.50"],
            "consensus_score": 1.0,
            "resolver_count": 2,
        },
        timestamp=datetime.now(),
        hostname="test-vm",
        resolver_name="1.1.1.1",
    )

    success = await agent.maybe_alert(recovery_event)
    print(f"Recovery alert sent: {success}")

    print("\nDone! Check your Telegram.")


if __name__ == "__main__":
    asyncio.run(send_test_messages())