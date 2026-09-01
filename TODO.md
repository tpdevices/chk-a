# chk-a — TODO

**Last updated:** 2026-08-31T15:40:00+07:00 (2026-08-31 08:40:00 UTC)
**Project:** chk-a — automated DNS A-record change monitor
**Location:** /home/ipds/Hermes-Prj/chk-a

---

## Open Tasks

- [ ] **Persistent dedup cache for AlertAgent** — survive service restarts (currently in-memory only)
- [ ] **Server-side traceroute path visualization** — client→resolver education feature
- [ ] **Commit the project** to version control (currently not a git repo)
- [ ] **Monitor production stability** on test-chk-a VM

## Completed (this session)

- [x] Strictly removed all metrics/Prometheus (custom `metrics.py`, `MetricsConfig`, `/metrics`, config blocks, tests, docs).
- [x] Fixed lint/build: created `.flake8`, removed `[tool.flake8]` from `pyproject.toml`.
- [x] Real-machine test Part A (no sudo): validate-config, check-once (real DNS), show-baseline, daemon loop + `/healthz` + SIGTERM, `pip install -e .`, `test-telegram` graceful no-token, `systemd-analyze verify`. pytest 79 passed.
- [x] Created `uninstall.sh` + sandbox test (removes exactly what `install.sh` created; source untouched).
- [x] Confirmed Telegram Channel support (no code change).
- [x] **Real systemd install on target machine (test-chk-a VM)** — `sudo ./install.sh` + `sudo systemctl start chk-a` completed.
- [x] **Real Telegram credentials configured** — `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `/etc/chk-a/env`.
- [x] **Telegram alert format improvements (Majority vs Outliers view)**:
  - Added severity emoji: 🔴 CRITICAL / 🟡 WARNING / 🔵 INFO
  - Added type labels: 📊 Baseline Deviation / 🗳️ Consensus Deviation / 🆕 New IP Detected / 🚫 NXDOMAIN
  - Added Majority vs Outliers grouping in alert message
  - Hostname now shows monitor hostname (e.g., `test-chk-a`) not FQDN
  - Resolver name shown in alert
  - Observed IPs shows "timeout (no response)" when empty
- [x] **Plain text alert log**: `YYYY-MM-DD HH:MM:SS hostname resolver ip event_type: FQDN`
- [x] **Daily Telegram image at midnight** with hostname in caption: `🖥️ Host: test-chk-a`
- [x] **Day separators** in all log files at midnight: `=== DAY SEPARATOR: YYYY-MM-DD ===`
- [x] **Config schema**: Added `hostname` field to `AppConfig` with default `socket.gethostname()`
- [x] **Tests**: 79/79 passed
- [x] **Updated STATUS.md, STATUS-TH.md, PROJECT_CONTEXT.md, PROJECT_CONTEXT-TH.md, TODO.md** with timestamps.

## Self-Improvement (applied this session)

- Created/updated skill **`chk-a-dns-monitor`** capturing:
  - Project conventions (no-metrics rule, no-heavy-ML, `md/loop_engineering_prompt.md` authoritative, fix-tests-not-agent).
  - Verification discipline: never trust reference-model environment guesses — verify against real terminal/files (WSL systemd was running; install.sh uses `pip install -e`, not a symlink).
  - flake8 7.3.0 + `.flake8` gotcha.
  - sudo interactive-password limitation → prepare copy-paste command blocks.
  - Telegram Channel works via `chat_id` with no code change.
  - **Dev ↔ Test VM sync discipline**: Always rsync from dev to test, then sync back any VM-side edits immediately.
  - **Majority vs Outliers alert format**: Better UX for SOC/NetOps — group by agreement, highlight differences.
  - **Telegram image with hostname**: Added `parse_mode="HTML"` for proper rendering.