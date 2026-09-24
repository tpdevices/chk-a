# TODO — chk-a

**Last Updated:** 2026-09-23 11:45:00 (Asia/Bangkok UTC+07)

---

## 🔴 Critical / Blocking

None — all critical issues resolved as of v1.0.35 + FQDN features.

---

## 🟡 High Priority

### [x] SEC-014: HTML Escape in Telegram Messages
**Context:** Telegram messages use HTML parse_mode. User-supplied data (FQDN, resolver names, IPs) must be HTML-escaped to prevent injection.
**Files:** `src/chk_a/agents/alert_agent.py`, `src/chk_a/reporting/telegram_reporter.py`, `src/chk_a/utils/telegram_client.py`
**Test:** Added test for HTML injection attempt in message fields
**Priority:** Critical — XSS vector in Telegram HTML messages
**Status:** COMPLETED 2026-09-17 — Added `_html_escape()` function in `telegram_reporter.py` and `telegram_client.py`, applied to all user-supplied data in `send_message()`, `send_photo()`, `create_telegram_summary()`, `create_daily_telegram_summary()`. Security regression tests added in `tests/test_security_regressions.py::TestSEC014_HTMLInjection` (4 tests passing).

### [x] Fix install.sh venv reuse bug
**Context:** v1.0.2 install.sh checks `[[ ! -x "${VENV_DIR}/bin/python" ]]` to decide whether to create venv + install pip. If venv exists from failed run, pip installation is skipped.
**Fix:** Add pip verification inside the venv existence check. If python exists but pip doesn't, install pip.
**Workaround (current):** `sudo rm -rf /opt/chk-a/.venv && sudo ./install.sh v1.0.2`
**Files:** `install.sh`
**Priority:** High — blocks clean installs on retry
**Status:** COMPLETED 2026-09-17 — Added `NEED_PIP_INSTALL` flag to verify pip presence in existing venv and install if missing. Improved logging for pip installation steps.

### [x] Thai Localization for Alert/Report Messages
**Context:** User requested full Thai language support for all Telegram alerts and reports
**Files:** `src/chk_a/agents/alert_agent.py`, `src/chk_a/reporting/telegram_reporter.py`, `tests/test_alert_agent.py`
**Priority:** High — User request
**Status:** COMPLETED 2026-09-23 — Complete Thai rewrite of `_format_html()` for all alert types, Thai monthly/daily report summaries, updated test assertions. All 313 tests passing.

### [x] Verify production install on fresh VM (v1.0.15)
**Context:** v1.0.15 released with all fixes including daily report time range bug, daily midnight task image fallback, complete config examples, img/ in release assets.
**Steps:** Fresh Ubuntu 24.04 VM → `curl install.sh` → `sudo ./install.sh v1.0.15` → verify service starts
**Priority:** High — release validation
**Status:** COMPLETED 2026-09-18 — Production `uptime-host` installed v1.0.15 successfully. 00:00 daily image confirmed working.

### [x] FQDN Features: Availability, Per-FQDN Thresholds, IP Change Detection
**Context:** User requested FQDN-centric features: availability tracking per FQDN, custom alert thresholds per FQDN, IP change detection/alert
**Files:** `src/chk_a/models/schemas.py`, `src/chk_a/orchestrator.py`, `src/chk_a/storage/fqdn_store.py`, `src/chk_a/agents/alert_agent.py`, `src/chk_a/config/loader.py`, `tests/conftest.py`, `tests/test_orchestrator.py`, `tests/test_integration_pipeline.py`, `tests/test_loop7.py`
**Priority:** High — User request
**Status:** COMPLETED 2026-09-23 — All FQDN features implemented:
- `FQDNConfig.alert_rules` dict for per-FQDN thresholds
- `AnomalyEvent.type = "ip_change"` for IP change detection
- `_process_fqdn()` computes availability per cycle, updates FQDNRecord
- `_alert_ip_change()` triggers when IPs change, sends Thai alert
- Thai formatting for `ip_change` in `alert_agent.py`
- All 313 tests passing
- Synced to Test VM, awaiting deploy

---

## 🟢 Medium Priority

### [x] Add DoH/DoT resolver support (SEC-010)
**Context:** Current resolvers config only supports IP:port or hostname:port (Do53). Add DoH (DNS over HTTPS) and DoT (DNS over TLS) support.
**Files:** `src/chk_a/agents/resolver_agent.py`, `src/chk_a/models/schemas.py`, `config/config.yaml`
**Status:** COMPLETED 2026-09-22 — schemas updated (DohConfig, DotConfig), resolver agent implementation exists (`_query_doh`, `_query_dot`), tests added in v1.0.30
**Priority:** Medium — feature enhancement

### [x] CAP_NET_RAW for MTR without root (SEC-011)
**Context:** MTR requires CAP_NET_RAW for ICMP. Current systemd service runs as `chk-a` user without capabilities.
**Fix:** Add `AmbientCapabilities=CAP_NET_RAW` to systemd service or use setcap on mtr binary
**Files:** `systemd/chk-a.service`, `install.sh`
**Status:** COMPLETED 2026-09-22 — systemd service already has `CapabilityBoundingSet=CAP_NET_RAW` and `AmbientCapabilities=CAP_NET_RAW`, tests added in v1.0.30
**Priority:** Medium — security hardening

### [x] Add log rotation test coverage
**Context:** `_load_recent_checks()` handles rotated logs (.bz2, .gz). Need integration tests.
**Files:** `tests/test_reporting.py` (new), `src/chk_a/reporting/ml_insights.py`
**Status:** COMPLETED 2026-09-22 — 18 comprehensive tests added in v1.0.30 covering plain JSONL, date-stamped `.bz2`, numbered `.gz`, mixed timezone timestamps, fractional lookback, malformed lines, non-CheckResult lines, empty/nonexistent files
**Priority:** Medium — reliability

### [x] Email reporting integration
**Context:** Config has email section but implementation is stub. Monthly reports should send PDF via email.
**Files:** `src/chk_a/reporting/email_sender.py`, `src/chk_a/reporting/monthly_report.py`, `src/chk_a/orchestrator.py`
**Status:** COMPLETED 2026-09-22 — EmailSender class exists with STARTTLS/Implicit TLS, auth/no-auth, PDF attachments, Thai/English body; 12 tests added in v1.0.31
**Priority:** Medium — feature completion

### [x] Telegram report sending: sequential + Thai-only graphs
**Context:** User requested Telegram reports to send only Thai-language graphs (not English) and send sequentially (one-by-one waiting for success confirmation) instead of concurrent burst sending.
**Files:** `src/chk_a/reporting/telegram_reporter.py` — Modified `send_monthly_report_telegram()` and `send_daily_report_telegram()` to filter `-th.png` graphs, send sequentially with 0.5s delay, detailed logging per graph.
**Priority:** Medium — UX improvement for Telegram delivery reliability
**Status:** COMPLETED 2026-09-19 — Sequential send implemented, Thai-only filtering, rate-limit friendly delays, detailed per-graph logging.

### [x] Fix graph filename suffix for Thai filtering
**Context:** `telegram_reporter.py` filters for `-th.png` suffix but `generate_summary_dashboard()` didn't add language suffix to filenames.
**Files:** `src/chk_a/reporting/graph_generator.py` — Added `lang_suffix` to all graph filenames (e.g., `availability-bar20260919-143000-th.png`).
**Priority:** Critical — enables correct Thai-only filtering
**Status:** COMPLETED 2026-09-19 — Language suffix added to all generated graph files.

### [x] Fix orchestrator.py indentation + daily report timezone logic
**Context:** Indentation error in `_send_missing_daily_report()` breaking tests. Daily report logic in `generate_daily_report()` and startup report used wrong reference_date causing yesterday's data instead of today's.
**Files:** `src/chk_a/orchestrator.py` (indentation fix + timezone logic), `src/chk_a/reporting/monthly_report.py` (timezone-aware datetime + THAI-only graphs)
**Priority:** Critical — blocks tests and production correctness
**Status:** COMPLETED 2026-09-19 — Indentation fixed, timezone-aware datetime (Asia/Bangkok), fractional lookback for midnight-to-now, THAI-only graphs for all daily reports.

### [x] FQDN-centric data model & storage
**Context:** Current system tracks resolver-centric data only. Need FQDN as primary entity with: identity (fqdn, domain, subdomain, apex), DNS records (current IPs, CNAME chain, TTL), history (IP changes with timestamps/sources), metadata (registrar, expiry, NS), monitoring state (last_checked, status, failures), alerting rules, ML features (baseline IPs, anomaly score, flip-flop count, geo shifts).
**Files:** `src/chk_a/models/schemas.py` (FQDNRecord), `src/chk_a/storage/fqdn_store.py` (new), `src/chk_a/agents/resolver_agent.py` (ingestion), `src/chk_a/orchestrator.py` (scheduler)
**Status:** COMPLETED 2026-09-22 — FQDNRecord and FQDNStore implemented with full feature set, 25 tests in v1.0.32
**Priority:** Medium — architectural improvement for traceability & correlation

---

## 🔵 Low Priority / Nice to Have

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
4. Clean up config folder (remove duplicate `.example` files)
5. Audit unused Python files with `vulture`/`pyflakes`
6. Archive or remove unused scripts
7. Update `.gitignore` to prevent future artifact commits
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

### [x] v1.0.15 Release (2026-09-18)
**Details:**
- **Fixed:** Daily report time range bug (monthly_report.py), daily midnight task image fallback (orchestrator.py)
- **Added:** img/ directory in release assets (img.tar.gz), complete config.yaml.example with Thai comments, complete chk-a.env.example
- **Changed:** Release workflow uses new config.yaml.example, install.sh extracts img.tar.gz to /opt/chk-a/img/
- **Production:** uptime-host installed v1.0.15, 00:00 daily image confirmed working

### [x] v1.0.16 Release (2026-09-19)
**Details:** Telegram sequential send + Thai-only graphs

### [x] v1.0.17 Release (2026-09-19)
**Details:** Latency boxplot sort by median ASC (fastest on top)

### [x] v1.0.18 Release (2026-09-19)
**Details:** Timezone fix for daily reports + robust Thai filtering

### [x] v1.0.19 Release (2026-09-19)
**Details:** Graph filename suffix for Thai filtering + consistent daily reports

### [x] v1.0.20 Release (2026-09-19)
**Details:** Timezone fix for daily reports + robust Thai filtering

### [x] v1.0.21 Release (2026-09-19)
**Details:** Debug logging for daily reports + robust Thai filtering

### [x] v1.0.22 Release (2026-09-20)
**Details:** Manual daily report fixes: Thai-only filter, latency boxplot sort, daily heatmap month context

### [x] v1.0.23 Release (2026-09-20)
**Details:** Service startup report fix: Thai-only, today data 00:00-now, daily heatmap month context, background task

### [x] v1.0.24 Release (2026-09-20)
**Details:** Fix pyproject.toml version to 1.0.24 (was 1.0.14) — ensures wheel builds with correct version

### [x] v1.0.25 Release (2026-09-20 17:30:00)
**Details:**
- Missing daily report on startup now merges month data (Sep 1 to yesterday) for daily availability heatmap
- Daily heatmap title format: "Days 1 to N" (EN) / "วันที่ 1 ถึง N" (TH) — clearer than "Month: 1st to DD MMM"
- Month start fix: Both missing & today reports use `month_start = day 1`

### [x] v1.0.26 Release (2026-09-21 06:30:00)
**Details:**
- Fixed: Scheduled daily report (06:00 AM) now merges month data (1st to yesterday) for daily availability heatmap, instead of only yesterday's data. Consistent with startup report behavior.

### [x] v1.0.27 Release (2026-09-21 08:00:00)
**Details:**
- Version display across all reports:
  - Graphs: Version shown in footer center (`vX.Y.Z`) via `_add_header_footer()` in `graph_generator.py`
  - Telegram Monthly Summary: Version at end of message via `create_telegram_summary()` in `telegram_reporter.py`
  - Telegram Daily Summary: Version at end of message via `create_daily_telegram_summary()` in `telegram_reporter.py`
  - Dashboard/Reports: Version passed through `generate_summary_dashboard()` to all 8 chart types

### [x] v1.0.28 Release (2026-09-21 10:30:00)
**Details:**
- Fixed: Version detection now works both when installed as package and when running as module (`-m chk_a.main`). Added fallback to read from `pyproject.toml`.
- Fixed: CLI commands `test-telegram` and `test-daily-image` now properly extract secret values from `SecretStr` before passing to `TelegramClient`, fixing "Object of type SecretStr is not JSON serializable" error.

### [x] v1.0.29 Release (2026-09-21 15:30:00)
**Details:**
- Fixed: MTR CLI target validation auto-appends `:53` for bare IP/hostname, allowing CLI to accept bare IP/hostname as target argument without manual port specification.
- Test VM Python cache issue: Python `.pyc` cache in `/opt/chk-a/.venv/lib/python3.14/site-packages/chk_a/__pycache__/` was serving stale `__init__.py` (v0.1.0). Cleared cache with `sudo find /opt/chk-a/.venv -name '*.pyc' -path '*/chk_a/*' -delete` to serve updated `__version__` (1.0.29).

### [x] v1.0.30 Release (2026-09-22 14:45:00)
**Details:**
- SEC-010/011 tests added (DoH/DoT, CAP_NET_RAW)
- Log Rotation Tests added (18 tests)
- Fixed 13 test functions: tmp_path → _make_temp_path()

### [x] v1.0.31 Release (2026-09-22 15:30:00)
**Details:**
- Email Reporting Tests added (12 tests)

### [x] v1.0.32 Release (2026-09-22 16:00:00)
**Details:**
- FQDN-centric Data Model & Store implemented (FQDNRecord, FQDNStore, 25 tests)

### [x] v1.0.33 Release (2026-09-22 16:30:00)
**Details:**
- Startup heatmap fix (00:00 to now), version bump in source files
- Alert/Recovery version footer added

### [x] v1.0.34 Release (2026-09-22 16:30:00)
**Details:**
- Modern graph styling (colorblind-safe, viridis heatmap, clean aesthetics)
- Alert/Recovery version footer included in release

### [x] v1.0.35 Release (2026-09-23 10:00:00)
**Details:**
- Thai localization for all Telegram alerts and reports
- Consensus descriptions, resolver group labels, severity/type labels all in Thai
- All 313 tests passing (zero regression)

### [x] FQDN Features Complete (2026-09-23 11:45:00)
**Details:**
- Per-FQDN custom alert thresholds (`FQDNConfig.alert_rules`)
- FQDN availability tracking (successful/total * 100 per cycle)
- IP change detection/alert (`_alert_ip_change()`, `ip_change` anomaly type)
- FQDNStore integration in Orchestrator
- Thai formatting for `ip_change` alerts
- All 313 tests passing
- Synced to Test VM, awaiting deploy

---

## 📋 Related Files

| Category | Files |
|----------|-------|
| **Core Agents** | `src/chk_a/agents/resolver_agent.py`, `consensus_agent.py`, `ml_agent.py`, `alert_agent.py`, `mtr_agent.py` |
| **Orchestrator** | `src/chk_a/orchestrator.py`, `src/chk_a/main.py` |
| **Reporting** | `src/chk_a/reporting/graph_generator.py`, `telegram_reporter.py`, `telegram_client.py`, `pdf_generator.py`, `email_sender.py` |
| **Storage** | `src/chk_a/storage/baseline_store.py`, `src/chk_a/storage/fqdn_store.py` |
| **Models/Config** | `src/chk_a/models/schemas.py`, `config/config.yaml`, `/etc/chk-a/config.yaml` |
| **Systemd** | `systemd/chk-a.service`, `scripts/systemd_wrapper.py`, `scripts/systemd_notify.py` |
| **Deploy/Install** | `scripts/deploy.sh`, `install.sh`, `uninstall.sh`, `Makefile`, `.github/workflows/release.yml` |
| **Tests** | `tests/test_*.py` (313 tests), `tests/conftest.py` |
| **Logs** | `/var/log/chk-a/checks.jsonl*`, `/var/log/chk-a/alerts.jsonl*`, `/var/log/chk-a/alerts.log` |
| **Baselines** | `/var/lib/chk-a/baselines.json` |
| **FQDN Store** | `/var/lib/chk-a/fqdns.json` (NEW) |
| **Secrets** | `/etc/chk-a/env` |

---

## 🎯 Next Session Priorities

1. **Deploy to Test VM** — Run `sudo ./scripts/deploy.sh` on 192.168.56.122
2. **Verify FQDN features on Test VM** — Check availability tracking, IP change alerts
3. **Tag v1.0.36** — After test verification, release to production via GitHub Actions
4. **Dashboard web UI** (FastAPI + HTMX + Chart.js) — Low
5. **GitHub repo cleanup & branch consolidation** — Low
6. **Historical data compaction** — Low
7. **Multi-host orchestration** — Low
8. **Prometheus metrics export (optional)** — Low

---

*อัปเดตโดย Hermes Agent session วันที่ 2026-09-23 11:45:00 (Asia/Bangkok UTC+07)*