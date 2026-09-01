# chk-a — Status Report

**Last updated:** 2026-08-31T15:40:00+07:00 (2026-08-31 08:40:00 UTC)
**Project:** chk-a — automated DNS A-record change monitor
**Location:** /home/ipds/Hermes-Prj/chk-a

---

## 1. Project Overview

chk-a is an automated DNS A-record change monitor. It tracks a configurable set of
FQDNs, resolves their A records through multiple configurable DNS resolvers, builds a
machine-learned baseline of "normal" IP sets, detects anomalies (IP changed vs. the
learned baseline OR vs. the resolver-group consensus), and alerts via Telegram. It runs
as a systemd service on Ubuntu 24.04 LTS+ with a randomized check interval not exceeding
3 minutes.

Key user constraints:
- Multi-agent architecture (Resolver → Consensus → ML → Alert → Orchestrator)
- **No Prometheus or any external monitoring program** (strictly removed)
- No heavy ML dependencies (custom EMA + entropy; no torch/sklearn/river/redis/prometheus_client)
- Hash-based file verification for identity checks
- Communicates in Thai; assistant persona "น้องน้ำฟ้า"
- Model provider: nvidia
- Dev machine: Ubuntu on WSL, network 172.20.14.199/20

## 2. Architecture

```
Orchestrator (main loop, jitter 30–180s, /healthz, sd_notify watchdog)
   │
   ├─ ResolverAgent   check_fqdn(fqdn) -> list[CheckResult]   (per resolver)
   ├─ ConsensusAgent  aggregate(fqdn, results, min_consensus) -> ConsensusResult
   ├─ MLAgent         learn(consensus) / score(ips, fqdn) -> float / get_baseline
   │                   (BaselineStore: atomic JSON; sample_count / all_fqdns kept)
   ├─ AlertAgent      maybe_alert(event) -> bool  (async)
   │     └─ TelegramClient  send_message(chat_id, text)  (aiohttp + tenacity 3 retries)
   └─ structured JSON logging with correlation_id (uuid4 per cycle)
```

Source layout (`src/chk_a/`):
- `orchestrator.py` — loop, jitter, `/healthz`, watchdog (no `/metrics`)
- `agents/resolver_agent.py` — DNS resolution per resolver
- `agents/consensus_agent.py` — majority/consensus aggregation
- `agents/ml_agent.py` — EMA baseline + entropy scoring
- `agents/alert_agent.py` — decides when to alert
- `storage/baseline_store.py` — atomic JSON baseline store
- `utils/telegram_client.py` — Telegram Bot API sender
- `utils/systemd_notify.py` — sd_notify (safe no-op outside systemd)
- `utils/context.py` — correlation_id
- `utils/logger.py` — structured JSON logger
- `config/loader.py` — AppConfig (fqdns, resolvers, ml, alert, scheduler, logging, baseline_store_path, hostname)
- `models/schemas.py` — Pydantic v2 models (MetricsConfig removed)
- `main.py` — CLI: `validate-config | check-once | show-baseline | test-telegram | test-daily-image`

## 3. Completed Work

- **Loops 0–7**: full multi-agent system + test suite (79 passed).
- **Strictly removed all metrics/Prometheus** per "ไม่ใช้ prometheus หรือ program monitor อื่น ๆ":
  - Deleted `src/chk_a/utils/metrics.py` (custom Prometheus renderer)
  - Removed `MetricsConfig` from `schemas.py`, `loader.py`, and 3 config files
  - Removed `/metrics` endpoint from `orchestrator.py` (kept only `/healthz`)
  - Removed metrics tests from `test_loop7.py`
  - Updated README/ARCHITECTURE/RUNBOOK/CONTRIBUTING/`md/loop_engineering_prompt.md`
  - Retained `sample_count()`/`all_fqdns()` (real callers: `show-baseline` CLI + `_load_state`)
- **Fixed lint/build**: created `.flake8` (max-line-length=100), removed `[tool.flake8]` from `pyproject.toml`.
- **Real-machine test — Part A (no sudo)**:
  - `validate-config` OK; `check-once` against real DNS; `show-baseline` shows learned baseline
  - Daemon loop: `/healthz` → `{"status":"ok","shutdown":false}`; cycles run with correlation_id; baseline learned; SIGTERM → graceful shutdown ("Shutdown requested"); baseline persisted as valid JSON
  - `pip install -e .` succeeds; `chk-a` console script installed
  - `test-telegram` with no token handled gracefully (return 1, warns, no crash)
  - `systemd-analyze verify chk-a.service` → no syntax errors
  - `pytest` → **79 passed** (green)
- **Created `uninstall.sh`** + sandbox test (removes exactly what `install.sh` created; leaves source untouched).
- **Confirmed Telegram Channel support** (no code change; uses `chat_id`).
- **Real systemd install on target machine (test-chk-a VM)**: `sudo ./install.sh` + `sudo systemctl start chk-a` — **COMPLETED**
- **Real Telegram credentials configured** — `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `/etc/chk-a/env` — **COMPLETED**
- **Telegram alert format improvements (Majority vs Outliers view)**:
  - Added severity emoji: 🔴 CRITICAL / 🟡 WARNING / 🔵 INFO
  - Added type labels: 📊 Baseline Deviation / 🗳️ Consensus Deviation / 🆕 New IP Detected / 🚫 NXDOMAIN
  - Added Majority vs Outliers grouping in alert message
  - Hostname now shows monitor hostname (e.g., `test-chk-a`) not FQDN
  - Resolver name shown in alert
  - Observed IPs shows "timeout (no response)" when empty
- **Plain text alert log**: `YYYY-MM-DD HH:MM:SS hostname resolver ip event_type: FQDN`
- **Daily Telegram image at midnight** with hostname in caption: `🖥️ Host: test-chk-a`
- **Day separators** in all log files at midnight: `=== DAY SEPARATOR: YYYY-MM-DD ===`
- **Config schema**: Added `hostname` field to `AppConfig` with default `socket.gethostname()`

## 4. In Progress

- None — all planned features completed and tested.

## 5. Issues Found

- **sudo interactive password**: agent cannot type it → Part B install/uninstall on the real system is blocked; provided copy-paste command blocks instead.
- **Telegram placeholders**: alerts/`test-telegram` cannot send until real token + channel chat_id are supplied. (RESOLVED on test-chk-a)
- **flake8 7.3.0**: does not read `[tool.flake8]` from `pyproject.toml` unless `tomli` is installed → must use a standalone `.flake8`.
- **Reference-model misinformation (lesson)**: during this session nemotron/laguna claimed "WSL has no systemd" (FALSE — `systemctl is-system-running` = `running`, systemd was PID 1); gpt-oss claimed `install.sh` "creates a /usr/local/bin symlink" (FALSE — it uses `pip install -e` into `/opt/chk-a/.venv`). Always verify against real terminal output and actual file contents, never trust model guesses.
- **Dev vs Test VM sync**: Changes made on test VM must be synced back to dev (WSL) — nearly lost changes due to confusion.

## 6. Next Steps

- Monitor production service on test-chk-a for stability.
- Consider adding persistent dedup cache (survive restarts) for AlertAgent.
- Optional: server-side traceroute path visualization for client→resolver education.

## 7. Related Files

| File | Purpose |
|------|---------|
| `src/chk_a/orchestrator.py` | Main loop, `/healthz`, watchdog, daily tasks |
| `src/chk_a/agents/*.py` | Resolver, Consensus, ML, Alert agents |
| `src/chk_a/storage/baseline_store.py` | Atomic JSON baseline store |
| `src/chk_a/utils/telegram_client.py` | Telegram sender |
| `src/chk_a/utils/systemd_notify.py` | sd_notify helper |
| `src/chk_a/utils/context.py`, `logger.py` | correlation_id + structured log |
| `src/chk_a/config/loader.py`, `models/schemas.py` | Config + Pydantic models |
| `src/chk_a/main.py` | CLI entrypoint |
| `config/settings.yaml`, `*.example` | Config examples (metrics removed) |
| `install.sh` / `uninstall.sh` | Install / uninstall on target |
| `systemd/chk-a.service`, `logrotate.d/chk-a` | systemd unit + logrotate |
| `Makefile`, `pyproject.toml`, `.flake8` | Build/lint/test config |
| `md/loop_engineering_prompt.md` | **Authoritative** loop-engineering spec |
| `tests/test_loop7.py` | correlation_id + CLI tests |

## 8. TODO List

See `TODO.md` for the actionable checklist (with checkboxes and timestamps).