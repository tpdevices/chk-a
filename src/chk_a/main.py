"""Main entry point and CLI for chk-a (Loop 5 + Loop 7).

Loads configuration, wires up the four agents plus the baseline store and
Telegram client, then runs the :class:`Orchestrator` until shutdown.

Loop 7 adds CLI subcommands (``validate-config``, ``check-once``,
``show-baseline``, ``test-telegram``) so operators can inspect and exercise the
system without running the full daemon.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .agents.alert_agent import AlertAgent
from .agents.consensus_agent import ConsensusAgent
from .agents.ml_agent import MLAgent
from .agents.resolver_agent import ResolverAgent
from .config.loader import AppConfig, load_config
from .orchestrator import Orchestrator
from .storage.baseline_store import BaselineStore
from .utils.logger import setup_logger
from .utils.telegram_client import TelegramClient
from .validate_config import validate


def build_agents(config: AppConfig, logger: Any) -> dict[str, Any]:
    """Construct and wire the four agents plus their dependencies."""
    resolver = ResolverAgent(config.resolvers)
    # Consensus reuses the resolver health EMA so flaky resolvers are down-weighted.
    consensus = ConsensusAgent(config.resolvers, health=resolver.health)
    store = BaselineStore(config.baseline_store_path)
    ml = MLAgent(config.ml, store)
    telegram = TelegramClient(config.alert.telegram_bot_token)
    import platform
    hostname = platform.node()
    alert = AlertAgent(
        config.alert,
        logger,
        telegram,
        alert_log_path=config.alert.alert_log_path,
        alert_text_log_path=config.alert.alert_text_log_path,
        hostname=hostname,
    )
    return {
        "resolver": resolver,
        "consensus": consensus,
        "ml": ml,
        "alert": alert,
    }


# -- CLI subcommands -------------------------------------------------------
def cmd_validate_config(config: AppConfig) -> int:
    """Load and validate configuration; print errors; exit 0/1."""
    problems = validate(config)
    if problems:
        for p in problems:
            print(f"CONFIG ERROR: {p}", file=sys.stderr)
        return 1
    print(f"CONFIG OK: loaded {len(config.fqdns)} fqdn(s), " f"{len(config.resolvers)} resolver(s)")
    return 0


async def cmd_check_once(config: AppConfig, logger: Any) -> int:
    """Run a single monitoring cycle and print the results, then exit."""
    agents = build_agents(config, logger)
    orch = Orchestrator(config, agents, logger)
    await orch.run_cycle()
    print("check-once: cycle complete (see logs for details)")
    return 0


def cmd_show_baseline(config: AppConfig, logger: Any) -> int:
    """Print the learned ML baselines for every configured FQDN."""
    agents = build_agents(config, logger)
    ml: MLAgent = agents["ml"]
    fqdns = [f.name for f in config.fqdns]
    if not fqdns:
        print("No FQDNs configured")
        return 0
    out: dict[str, Any] = {}
    for fqdn in fqdns:
        out[fqdn] = {
            "baseline": ml.get_baseline(fqdn),
            "samples": ml.sample_count(fqdn),
        }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


async def cmd_test_telegram(config: AppConfig, logger: Any) -> int:
    """Send a test message via Telegram and report success/failure."""
    telegram = TelegramClient(config.alert.telegram_bot_token, logger_name="chk_a.cli")
    if not config.alert.telegram_bot_token or not config.alert.telegram_chat_id:
        print(
            "TELEGRAM ERROR: telegram_bot_token / telegram_chat_id not set "
            "(check config or /etc/chk-a/env)",
            file=sys.stderr,
        )
        await telegram.close()
        return 1
    ok = await telegram.send_message(
        config.alert.telegram_chat_id,
        "<b>chk-a</b> test message — monitoring is wired correctly. ✅",
        "HTML",
    )
    await telegram.close()
    if ok:
        print("TELEGRAM OK: test message sent")
        return 0
    print("TELEGRAM ERROR: failed to send (see logs)", file=sys.stderr)
    return 1


async def cmd_test_daily_image(config: AppConfig, logger: Any) -> int:
    """Send the daily image via Telegram and report success/failure."""
    telegram = TelegramClient(config.alert.telegram_bot_token, logger_name="chk_a.cli")
    chat_id = config.alert.daily_image_chat_id or config.alert.telegram_chat_id
    if not config.alert.telegram_bot_token or not chat_id:
        print(
            "TELEGRAM ERROR: telegram_bot_token / chat_id not set "
            "(check config or /etc/chk-a/env)",
            file=sys.stderr,
        )
        await telegram.close()
        return 1
    
    # Resolve image path
    img_path = Path(config.alert.daily_image_path)
    if not img_path.is_absolute():
        for base in [Path.cwd(), Path("/opt/chk-a")]:
            candidate = base / img_path
            if candidate.is_file():
                img_path = candidate
                break
    
    if not img_path.is_file():
        print(f"TELEGRAM ERROR: image not found at {img_path}", file=sys.stderr)
        await telegram.close()
        return 1
    
    # Add hostname to caption
    hostname = config.hostname
    caption = f"{config.alert.daily_image_caption}\n🖥️ Host: <code>{hostname}</code>"
    
    ok = await telegram.send_photo(
        chat_id=chat_id,
        photo_path=img_path,
        caption=caption,
        parse_mode="HTML",
    )
    await telegram.close()
    if ok:
        print(f"TELEGRAM OK: daily image sent from {img_path}")
        return 0
    print("TELEGRAM ERROR: failed to send image (see logs)", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chk-a", description="chk-a DNS anomaly monitor")
    parser.add_argument(
        "-c", "--config",
        dest="config_path",
        metavar="PATH",
        help="Path to config YAML (default: auto-detect /etc/chk-a/config.yaml, config/settings.yaml, CHK_A_CONFIG)"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("validate-config", help="Validate config and exit (0/1)")
    sub.add_parser("check-once", help="Run a single monitoring cycle and exit")
    sub.add_parser("show-baseline", help="Print learned ML baselines")
    sub.add_parser("test-telegram", help="Send a Telegram test message")
    sub.add_parser("test-daily-image", help="Send the daily image via Telegram")

    # Default (no subcommand) runs the daemon.
    return parser


def main() -> int:
    """Dispatch CLI subcommands or run the orchestrator loop."""
    parser = build_parser()
    args = parser.parse_args()

    config = load_config(args.config_path)
    logger = setup_logger(
        "chk_a",
        level=config.logging.level,
        log_file=config.logging.file,
    )

    if args.command == "validate-config":
        return cmd_validate_config(config)
    if args.command == "show-baseline":
        return cmd_show_baseline(config, logger)
    if args.command == "test-daily-image":
        return asyncio.run(cmd_test_daily_image(config, logger))
    if args.command in ("check-once", "test-telegram"):
        try:
            if args.command == "check-once":
                return asyncio.run(cmd_check_once(config, logger))
            return asyncio.run(cmd_test_telegram(config, logger))
        except KeyboardInterrupt:
            logger.info("Interrupted; exiting")
            return 130

    # No subcommand -> run the daemon.
    agents = build_agents(config, logger)
    orch = Orchestrator(config, agents, logger)
    try:
        asyncio.run(orch.run())
    except KeyboardInterrupt:
        logger.info("Interrupted; exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
