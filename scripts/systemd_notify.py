#!/usr/bin/env python3
"""Systemd service status notifier for chk-a — sends service lifecycle events to Telegram."""

import asyncio
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, '/opt/chk-a')

from chk_a.utils.telegram_client import TelegramClient


async def send_service_notification(action: str, status: str, details: str = "") -> bool:
    """Send service status notification to Telegram."""
    
    # Read credentials from env file
    bot_token = None
    chat_id = None
    with open('/etc/chk-a/env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if key == 'TELEGRAM_BOT_TOKEN':
                    bot_token = value
                elif key == 'TELEGRAM_CHAT_ID':
                    chat_id = value
    
    if not bot_token or not chat_id:
        print("Missing Telegram credentials", file=sys.stderr)
        return False
    
    # Build message
    hostname = os.uname().nodename
    
    emoji_map = {
        'start': '🟢',
        'restart': '🔄',
        'stop': '🔴',
        'fail': '❌',
        'error': '⚠️',
    }
    
    emoji = emoji_map.get(action, 'ℹ️')
    
    message = (
        f"{emoji} <b>Service {action.capitalize()}</b>\n"
        f"<b>Service:</b> chk-a\n"
        f"<b>Host:</b> <code>{hostname}</code>\n"
        f"<b>Status:</b> {status}\n"
    )
    
    if details:
        message += f"<b>Details:</b> <code>{details}</code>\n"
    
    message += f"<b>Time:</b> {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Send
    telegram = TelegramClient(bot_token=bot_token)
    try:
        result = await telegram.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        await telegram.close()
        return result
    except Exception as e:
        print(f"Telegram send failed: {e}", file=sys.stderr)
        await telegram.close()
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: systemd_notify.py <action> <status> [details]", file=sys.stderr)
        print("  action: start|restart|stop|fail|error", file=sys.stderr)
        print("  status: success|failed|error", file=sys.stderr)
        sys.exit(1)
    
    action = sys.argv[1]
    status = sys.argv[2]
    details = sys.argv[3] if len(sys.argv) > 3 else ""
    
    result = asyncio.run(send_service_notification(action, status, details))
    sys.exit(0 if result else 1)


if __name__ == '__main__':
    main()