#!/usr/bin/env python3
"""Systemd service wrapper for chk-a — detects restarts and sends notifications."""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, '/opt/chk-a')

from chk_a.utils.telegram_client import TelegramClient

STATE_FILE = '/var/lib/chk-a/last_state.txt'


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


def read_last_state() -> str:
    """Read last known service state."""
    try:
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def write_state(state: str) -> None:
    """Write current service state."""
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        f.write(state)


async def main_async():
    if len(sys.argv) < 2:
        print("Usage: systemd_wrapper.py <command> [args...]", file=sys.stderr)
        print("  commands: start|stop|status", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "start":
        # Check if this is a restart (previous state was running)
        last_state = read_last_state()
        if last_state == "running":
            await send_service_notification("restart", "success", "Service restarted (crash recovery or manual restart)")
        else:
            await send_service_notification("start", "success", "Service started")
        write_state("running")
        
    elif command == "stop":
        last_state = read_last_state()
        write_state("stopped")
        await send_service_notification("stop", "success", "Service stopped")
        
    elif command == "fail":
        # Called when service fails
        last_state = read_last_state()
        write_state("failed")
        details = sys.argv[2] if len(sys.argv) > 2 else "Service failed"
        await send_service_notification("fail", "failed", details)
        
    elif command == "status":
        # Just report current state
        state = read_last_state()
        print(f"Last state: {state}")
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == '__main__':
    main()