"""Config validation entry point (Loop 6).

Run as ``python -m chk_a.validate_config``. Exits 0 if the configuration
loads and passes sanity checks, 1 otherwise. Intended for use as a systemd
``ExecStartPre`` hook so a broken config never reaches the running service.
"""

from __future__ import annotations

import argparse
import sys

from .config.loader import AppConfig, load_config


def validate(config: AppConfig) -> list[str]:
    """Return a list of human-readable problems (empty list == valid)."""
    problems: list[str] = []
    if not config.fqdns:
        problems.append("No 'fqdns' configured")
    if not config.resolvers:
        problems.append("No 'resolvers' configured")
    for f in config.fqdns:
        if not f.name:
            problems.append("Found an FQDN with an empty name")
    for r in config.resolvers:
        if not r.address:
            problems.append(f"Resolver '{r.name}' has an empty address")
    if config.scheduler.max_interval_sec < config.scheduler.min_interval_sec:
        problems.append("scheduler.max_interval_sec < min_interval_sec")
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chk-a validate-config", description="Validate chk-a config"
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_path",
        metavar="PATH",
        help=(
            "Path to config YAML (default: auto-detect /etc/chk-a/config.yaml, "
            "config/settings.yaml, CHK_A_CONFIG)"
        ),
    )
    return parser


def main(args: list[str] | None = None) -> int:
    """Load and validate configuration; return a process exit code.

    Args:
        args: Optional list of command-line arguments (for testing).
              If None, uses sys.argv.
    """
    parser = build_parser()
    parsed = parser.parse_args(args)
    try:
        config = load_config(parsed.config_path)
    except Exception as exc:  # noqa: BLE001 - report any load failure
        print(f"CONFIG ERROR: failed to load: {exc}", file=sys.stderr)
        return 1
    problems = validate(config)
    if problems:
        for p in problems:
            print(f"CONFIG ERROR: {p}", file=sys.stderr)
        return 1
    print(f"CONFIG OK: loaded {len(config.fqdns)} fqdn(s), " f"{len(config.resolvers)} resolver(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
