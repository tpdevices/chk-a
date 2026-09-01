# chk-a — Project Context

**Last updated:** 2026-08-31T15:40:00+07:00 (2026-08-31 08:40:00 UTC)
**Project:** chk-a — automated DNS A-record change monitor
**Location:** /home/ipds/Hermes-Prj/chk-a

This file captures durable context for future sessions working on chk-a.

---

## 1. Project Overview

chk-a monitors DNS A-records of configured FQDNs across multiple resolvers, learns a
baseline of normal IP sets with a lightweight ML model (EMA + entropy), detects anomalies,
and alerts via Telegram. Runs as a systemd service on Ubuntu 24.04 LTS+ with a randomized
interval ≤ 3 minutes. No external monitoring (Prometheus/metrics) is used — only
`correlation_id` tracing and a `/healthz` health check.

## 2. Architecture

Multi-agent pipeline orchestrated by `orchestrator.py`:
Resolver → Consensus → ML (BaselineStore) → Alert (TelegramClient) → Orchestrator.
See `STATUS.md` §2 for the full layout. The authoritative design spec lives in
`md/loop_engineering_prompt.md` (Loops 0–7).

## 3. Conventions & Hard Rules (from user)

- **No Prometheus / no external monitoring** — strictly. Only `correlation_id` (structured
  JSON log) and `/healthz` (systemd health check) are allowed. No metrics endpoints,
  gauges, or scrape ports.
- **No heavy ML deps** — custom EMA + entropy only. No torch/sklearn/river/redis/
  prometheus_client/python-systemd.
- **`md/loop_engineering_prompt.md` is AUTHORITATIVE** over reference models and inferred
  specs. When a test fails on spec interpretation, **fix the test to match the md spec,
  not the agent code** — unless the agent genuinely breaks a real caller.
- Communicate in Thai; persona "น้องน้ำฟ้า". Model provider: nvidia.
- All project files stay under the project folder.

## 4. Environment

- OS: Ubuntu (dev is 26.04 on WSL; target is 24.04 LTS+). **systemd runs as PID 1** on
  this WSL box (`systemctl is-system-running` = `running`).
- Python 3.14.4; venv at `venv/` with pydantic 2.13.5, dnspython, aiohttp, tenacity,
  pyyaml, pydantic-settings, build/black/flake8 (dev).
- Dev network: 172.20.14.199/20.
- Not a git repository (no commits yet).
- Target VM: test-chk-a (Ubuntu 26.04), SSH via IP, service deployed at `/opt/chk-a`

## 5. How to Run / Test

```bash
source venv/bin/activate
export PYTHONPATH=src
export CHK_A_CONFIG=/path/to/config.yaml   # writable paths for logs/state

python -m chk_a.main validate-config
python -m chk_a.main check-once             # one real cycle
python -m chk_a.main show-baseline
python -m chk_a.main test-telegram
python -m chk_a.main test-daily-image

# Daemon loop (no sudo), probe health, then SIGTERM:
export CHK_A_HEALTH_PORT=8080 CHK_A_WATCHDOG_INTERVAL=0
python -m chk_a.main &
curl -s http://127.0.0.1:8080/healthz
kill -TERM <pid>
```

Quality gates: `pytest -q` (target 79 passed), `make build`, `make lint` (uses `.flake8`).

## 6. Install / Uninstall on Target

`install.sh` creates: `/opt/chk-a` (code+venv via `pip install -e`), `/etc/chk-a/`
(config + env secrets), `/var/lib/chk-a` (state), `/var/log/chk-a` (logs),
`/etc/systemd/system/chk-a.service`, `/etc/logrotate.d/chk-a`.
`uninstall.sh` removes exactly those (never the source checkout). Both require sudo.

On test-chk-a: service is running, Telegram alerts working, daily image with hostname sent at midnight.

## 7. Gotchas (hard-won)

- **Verify, don't trust model guesses.** Reference models incorrectly claimed WSL lacks
  systemd and that install.sh makes a symlink — both false. Check real terminal/files.
- **flake8 7.3.0** ignores `[tool.flake8]` in pyproject without `tomli` → use `.flake8`.
- **sudo** needs an interactive password the agent cannot type → prepare copy-paste blocks.
- **Telegram Channel** works with no code change: set `TELEGRAM_CHAT_ID` to `@channel` or
  `-100xxxxxxxxxx`; bot must be Admin with Post Messages.
- **Dev vs Test VM sync**: Changes made on test VM must be synced back to dev (WSL) — nearly lost changes due to confusion. Always rsync from dev to test, then sync back any VM-side edits.

## 8. TODO / Open Items

See `TODO.md`. Top open items: persistent dedup cache for AlertAgent, server-side traceroute visualization.