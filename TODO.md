# TODO — chk-a

**Last Updated:** 2026-09-17 20:30:00 (Asia/Bangkok UTC+07)

---

## 🔴 Critical / Blocking

### [x] SEC-014: HTML Escape in Telegram Messages
**Context:** Telegram messages use HTML parse_mode. User-supplied data (FQDN, resolver names, IPs) must be HTML-escaped to prevent injection.
**Files:** `src/chk_a/agents/alert_agent.py`, `src/chk_a/reporting/telegram_reporter.py`, `src/chk_a/utils/telegram_client.py`
**Test:** Added test for HTML injection attempt in message fields
**Priority:** Critical — XSS vector in Telegram HTML messages
**Status:** COMPLETED 2026-09-17 — Added `_html_escape()` function in `telegram_reporter.py` and `telegram_client.py`, applied to all user-supplied data in `send_message()`, `send_photo()`, `create_telegram_summary()`, `create_daily_telegram_summary()`. Security regression tests added in `tests/test_security_regressions.py::TestSEC014_HTMLInjection` (4 tests passing).

---

## 🟡 High Priority

### [x] Fix install.sh venv reuse bug
**Context:** v1.0.2 install.sh checks `[[ ! -x "${VENV_DIR}/bin/python" ]]` to decide whether to create venv + install pip. If venv exists from failed run, pip installation is skipped.
**Fix:** Add pip verification inside the venv existence check. If python exists but pip doesn't, install pip.
**Workaround (current):** `sudo rm -rf /opt/chk-a/.venv && sudo ./install.sh v1.0.2`
**Files:** `install.sh`
**Priority:** High — blocks clean installs on retry
**Status:** COMPLETED 2026-09-17 — Added `NEED_PIP_INSTALL` flag to verify pip presence in existing venv and install if missing. Improved logging for pip installation steps.

### [ ] Verify production install on fresh VM
**Context:** v1.0.14 released with all fixes. Need to test on clean VM.
**Steps:** Fresh Ubuntu 24.04 VM → `curl install.sh` → `sudo ./install.sh v1.0.14` → verify service starts
**Priority:** High — release validation

---

## 🟢 Medium Priority

### [ ] Add DoH/DoT resolver support (SEC-010)
**Context:** Current resolvers config only supports IP:port or hostname:port (Do53). Add DoH (DNS over HTTPS) and DoT (DNS over TLS) support.
**Files:** `src/chk_a/agents/resolver_agent.py`, `src/chk_a/models/schemas.py`, `config/config.yaml`
**Status:** Partially done — schemas updated, resolver agent needs implementation
**Priority:** Medium — feature enhancement

### [ ] CAP_NET_RAW for MTR without root (SEC-011)
**Context:** MTR requires CAP_NET_RAW for ICMP. Current systemd service runs as `chk-a` user without capabilities.
**Fix:** Add `AmbientCapabilities=CAP_NET_RAW` to systemd service or use setcap on mtr binary
**Files:** `systemd/chk-a.service`, `install.sh`
**Priority:** Medium — security hardening

### [ ] Add log rotation test coverage
**Context:** `_load_recent_checks()` handles rotated logs (.bz2, .gz). Need integration tests.
**Files:** `tests/test_reporting.py` (new), `src/chk_a/reporting/graph_generator.py`
**Priority:** Medium — reliability

### [ ] Email reporting integration
**Context:** Config has email section but implementation is stub. Monthly reports should send PDF via email.
**Files:** `src/chk_a/reporting/email_reporter.py` (new), `src/chk_a/orchestrator.py`
**Priority:** Medium — feature completion

---

## 🔵 Low Priority / Nice to Have

### [ ] Config.yaml Parameter Documentation & Setup Guide
**Context:** Create comprehensive documentation for all config.yaml parameters with explanations, valid values, recommended settings, and setup guides.
**Files:** `docs/config-guide.md` (new), `config/config.yaml.example` (update with comments)
**Sections to document:**
- `fqdns`: name, expected_ips, min_consensus - meaning and recommended values
- `resolvers`: name, address (Do53/DoH/DoT formats), weight, timeout_ms
- `ml`: baseline_decay, anomaly_threshold, min_samples_before_alert
- `alert`: telegram credentials, dedup_window_minutes, rate_limit_per_hour, log paths
- `scheduler`: min_interval_sec, max_interval_sec, jitter
- `mtr`: enabled, interval_sec, max_hops, count, interval_ms, timeout_sec, mode (icmp/tcp/udp), port, resolvers list
- `baseline_store_path`
- `reporting`: schedules, output_dir, telegram/email config, graph inclusion, lookback_days
**Priority:** Low — documentation completeness
**Related:** `config/`, `docs/`, onboarding for new users

### [ ] Dashboard web UI
**Context:** Add simple web dashboard for real-time status, graphs, alerts history.
**Tech:** FastAPI + HTMX + Chart.js (lightweight, no heavy JS framework)
**Files:** New `src/chk_a/dashboard/` module
**Priority:** Low — future enhancement

### [ ] GitHub repo cleanup & branch consolidation
**Context:** Repository has both `main` and `master` branches, plus unused/old files. Need to consolidate to single branch, remove unused files, and organize structure.
**Steps:**
1. Audit branches - determine which is canonical (likely `main` if CI/CD uses it)
2. Merge/consolidate branches
3. Remove build artifacts from git history (`*.whl`, `*.tar.gz`)
3. Clean up config folder (remove duplicate `.example` files)
4. Audit unused Python files with `vulture`/`pyflakes`
5. Archive or remove unused scripts
6. Update `.gitignore` to prevent future artifact commits
**Priority:** Low — technical debt reduction
**Related:** `config/`, `scripts/`, root artifacts, branch strategy

### [ ] Prometheus metrics export (optional)
**Context:** Project rule says "no Prometheus", but optional `/metrics` endpoint could be added behind feature flag for users who want it.
**Files:** New `src/chk_a/metrics.py`, optional dependency
**Priority:** Low — optional feature

### [ ] Multi-host orchestration
**Context:** Support monitoring multiple hosts from single orchestrator (currently single-host per service).
**Files:** `src/chk_a/orchestrator.py`, config schema
**Priority:** Low — architecture evolution

### [ ] Historical data compaction
**Context:** Baseline store grows over time. Add compaction for old baselines (keep daily aggregates, drop per-check).
**Files:** `src/chk_a/storage/baseline_store.py`
**Priority:** Low — maintenance

---

## ✅ Completed (Recent)

### [x] SEC-001..SEC-020: Security regression tests (2026-09-13)
**Details:** 20 security tests covering path traversal, token handling, config validation, log injection, concurrency limits, encryption, dependencies, permissions, circuit breaker, scheduler drift, MTR/resolver sync

### [x] Telegram Reporter Fix — Token in URL path (2026-09-13)
**Details:** Fixed `TelegramReporter` to use token in URL path (`/bot<token>/method`) per Telegram Bot API spec. Was using `Authorization: *** header (404 error).

### [x] Deploy Script — `scripts/deploy.sh` (2026-09-14)
**Details:** Standard deploy from dev source `/home/ipds/Hermes-Prj/chk-a/` to FHS runtime `/opt/chk-a/` with rsync checksum verification and systemd restart.

### [x] Rotated Log Support — `_load_recent_checks()` (2026-09-15)
**Details:** Auto-reads date-stamped `.bz2` and numbered `.gz` backups. Fixed mixed timezone timestamp parsing.

### [x] Baseline Integrity Metrics (2026-09-15)
**Details:** Replaced Isolation Forest with `MLAgent.score()` (total-variation distance). Added IP stability & diversity metrics for baseline method.

### [x] Startup Missing Daily Report Check (2026-09-15)
**Details:** Orchestrator checks for missing yesterday's report on startup and sends it automatically.

### [x] GitHub Release Workflow + Production Installer (2026-09-16)
**Details:** 
- `.github/workflows/release.yml` — build wheel on tag push, create GitHub Release
- `install.sh` / `uninstall.sh` — production installer/uninstaller
- `Makefile` — install, uninstall, upgrade, status, logs, version targets
- v1.0.0, v1.0.1, v1.0.2 released

### [x] v1.0.2 pip installation improvement (2026-09-16)
**Details:** `ensurepip` with output logging, fallback to `get-pip.py`, verification with version logging. Known bug: venv reuse skips pip install.

### [x] Install.sh Fixes v1.0.3-v1.0.14 (2026-09-17)
**Details:**
- v1.0.3: Fix install.sh venv reuse bug (added pip verification, improved logging)
- v1.0.4: Fix env permission to 0640 so service can read Telegram credentials
- v1.0.5: Ensure env.example is present and not empty after download
- v1.0.6: Fix env file permissions (0640) so service can read credentials
- v1.0.7: Ensure env.example is present and not empty after download
- v1.0.8: Move env.example check to /tmp, remove silent failures, add verification step
- v1.0.9: Fix wheel download for "latest" (correct GitHub API endpoint), add timeouts/progress bars
- v1.0.10: Use dedicated temp dir (mktemp) for downloads, remove existing files before download
- v1.0.11: Change default reporting.output_dir to /var/lib/chk-a/reports to fix read-only filesystem error
- v1.0.12: Fix HTML parsing in Telegram messages (remove auto-escape from TelegramClient, add proper escaping in callers)
- v1.0.13: Support Python 3.10+ (Ubuntu 22.04 LTS), add backports.zoneinfo dependency
- v1.0.14: Add manual daily/monthly report scripts for on-demand reporting

### [x] Manual Report Scripts (2026-09-17)
**Details:**
- `scripts/manual_daily_report.py` — On-demand daily report from midnight to now
- `scripts/manual_monthly_report.py` — On-demand monthly report from 1st of month to now
- Both generate Thai/English summaries + graphs, send to Telegram on demand
- **Fixed: Both scripts now show ALL resolvers** (removed hardcoded `[:10]` limits) — 2026-09-17 19:30:00

### [x] Telegram Report Complete Coverage (2026-09-17)
**Details:**
- Monthly text summary: removed Top 5 limit → shows ALL resolvers
- Daily/Monthly graph sending: removed 5/6 graph limit → sends ALL graphs
- Manual report scripts: removed hardcoded `[:10]` limits in availability, path availability, integrity sections
- Labels updated from "Top 10" to "All Resolvers"

### [x] Daily Availability Heatmap for Monthly Reports (2026-09-17 20:00:00)
**Details:**
- Added `daily_availability` computation in `ml_insights.py::compute_availability()`
- Added `generate_availability_daily_heatmap()` in `graph_generator.py` with Thai version
- Integrated into `generate_summary_dashboard()` — monthly reports now include both hourly and daily heatmaps
- Monthly reports: 18-20 graphs total (7 chart types × EN/TH = 14 + 2 Dashboard = 16 + 2 Daily Heatmap = 18)

---

## 📋 Related Files

| Category | Files |
|----------|-------|
| **Core Agents** | `src/chk_a/agents/resolver_agent.py`, `consensus_agent.py`, `ml_agent.py`, `alert_agent.py`, `mtr_agent.py` |
| **Orchestrator** | `src/chk_a/orchestrator.py`, `src/chk_a/main.py` |
| **Reporting** | `src/chk_a/reporting/graph_generator.py`, `telegram_reporter.py`, `telegram_client.py`, `pdf_generator.py` |
| **Storage** | `src/chk_a/storage/baseline_store.py` |
| **Models/Config** | `src/chk_a/models/schemas.py`, `config/config.yaml`, `/etc/chk-a/config.yaml` |
| **Systemd** | `systemd/chk-a.service`, `scripts/systemd_wrapper.py`, `scripts/systemd_notify.py` |
| **Deploy/Install** | `scripts/deploy.sh`, `install.sh`, `uninstall.sh`, `Makefile`, `.github/workflows/release.yml` |
| **Tests** | `tests/test_*.py` (257 tests), `tests/conftest.py` |
| **Logs** | `/var/log/chk-a/checks.jsonl*`, `/var/log/chk-a/alerts.jsonl*`, `/var/log/chk-a/alerts.log` |
| **Baselines** | `/var/lib/chk-a/baselines.json` |
| **Secrets** | `/etc/chk-a/env` |

---

## 🎯 Next Session Priorities

1. **Verify production install on fresh VM** — v1.0.14 (High)
2. **SEC-010/011** — DoH/DoT support, CAP_NET_RAW for MTR (Medium)
3. **Add log rotation test coverage** (Medium)
4. **Email reporting integration** (Medium)
5. **Dashboard web UI** (Low)
6. **GitHub repo cleanup & branch consolidation** (Low)

---

*อัปเดตโดย Hermes Agent session วันที่ 2026-09-17 20:30:00 (Asia/Bangkok UTC+07)*