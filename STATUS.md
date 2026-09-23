# Project Status — chk-a

**Last Updated:** 2026-09-22 15:40:32 (Asia/Bangkok UTC+07)

---

## 1. Project Overview

**chk-a** is a multi-agent DNS A-record anomaly monitoring system. It continuously queries multiple DNS resolvers for configured FQDNs, builds a weighted consensus, learns baselines via online exponential-decay counters, detects anomalies, and sends formatted alerts via Telegram with comprehensive reporting (daily/monthly, EN/TH, charts + PDF).

**Repository:** `tpdevices/chk-a` (GitHub, HTTPS with PAT)  
**Development:** WSL Ubuntu (172.20.14.199/20)  
**Test Target:** VirtualBox Ubuntu 24.04 at 192.168.56.122 (user: ipds)  
**Production:** `uptime-host` (internal DNS monitoring)  
**Service User:** `chk-a` (uid=999)  
**Python:** 3.14.4 (`python3`, PEP 668 → venv/uv)  
**All timestamps:** Local Asia/Bangkok (+07), format `YYYY-MM-DD HH:MM:SS`

---

## 2. Architecture

```
ResolverAgent → ConsensusAgent → MLAgent → AlertAgent → Telegram
     │              │               │            │
     ▼              ▼               ▼            ▼
CheckResult[]  ConsensusResult  BaselineStore  AnomalyEvent
               (entropy score)   (EMA decay)   (dedup+ratelimit)
                    │               │            │
                    └───────────────┴────────────┘
                                    │
                                    ▼
                           Orchestrator (scheduler, healthz, shutdown)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
               MTRAgent       Reporting         BaselineStore
               (MTR paths)    (graphs/PDF/      (atomic JSON)
                              Telegram/email)
```

**Systemd Services (4):**
- `chk-a-resolver` — ResolverAgent
- `chk-a-consensus` — ConsensusAgent + MLAgent
- `chk-a-alert` — AlertAgent + Orchestrator
- `chk-a-mtr` — MTRAgent

**Systemd Service Status Notification (2026-09-12):**
- `scripts/systemd_wrapper.py` — Wrapper script called via ExecStartPre (start) and ExecStop (stop)
- `scripts/systemd_notify.py` — Direct notifier for start/stop/restart/fail/error
- State tracking via `/opt/chk-a/last_state.txt` (detects restarts vs fresh starts)
- Telegram emojis: 🟢 start, 🔄 restart, 🔴 stop, ❌ fail, ⚠️ error
- Integrated into `systemd/chk-a.service` via ExecStartPre and ExecStop

---

## 3. Completed Work

### Core System
- ✅ All 5 agents implemented and wired through `Orchestrator`
- ✅ Config system: YAML + `${ENV}` substitution, Pydantic validation, auto-tuned `max_concurrent`
- ✅ Baseline Store with Atomic persistence (`os.replace` + `fsync`)
- ✅ Structured JSONL Logging with Correlation ID
- ✅ Systemd Integration (Type=notify, WatchdogSec, ReadWritePaths for dedup cache)
- ✅ Graceful Shutdown (SIGTERM/SIGINT) with baseline persistence

### Reporting (Loop 7)
- ✅ Monthly report (1st of month, 06:00 AM)
- ✅ Daily report (06:00 AM, lookback 1 day) — **FIXED: Telegram 404 error + time range bug**
- ✅ 7 chart types × 2 languages (EN/TH) = 14 charts + 2 Dashboards = 16 files
  - Availability Bar, Availability Heatmap, Integrity Score, Latency Boxplot, IP Stability, MTR Path, Path Availability
- ✅ **NEW: Daily Availability Heatmap** — Day-of-month vs resolver availability matrix for monthly reports (2026-09-17)
- ✅ Thai language support via `_apply_thai_fonts()` with translation map covering all chart types
- ✅ PDF reports (EN/TH) via fpdf2
- ✅ Telegram batch sending (configurable batch size, delay, exponential backoff retry)
- ✅ Email delivery (SMTP with TLS)

### Telegram Integration
- ✅ Daily image at midnight with hostname in caption
- ✅ Day separators in all log files at midnight
- ✅ Plain text alert log format: `date time hostname resolver ip event`
- ✅ Alert Deduplication (30 min window, persistent JSON cache)
- ✅ Token Bucket Rate Limiting (20/hr default)
- ✅ HTML-formatted alerts: Majority vs Outliers view, emojis (🔴/🟡/🔵), type labels (📊/🗳️/🆕/🚫)
- ✅ **All resolvers displayed** in summaries (removed Top 5/10 limits) — 2026-09-17
- ✅ **All graphs sent** to Telegram (removed 5/6 graph limits) — 2026-09-17

### Anomaly/Recovery Notifications (2026-09-09)
- ✅ Event ID format: `{hostname}-YYYYMMDD-HHmmss` for both anomaly and recovery
- ✅ Anomaly: `img/priority.jpg` + cause, last unreachable IP from MTR, consensus score
- ✅ Recovery: `img/ok.jpg` + anomaly duration (h/m/s), ML baseline stability, recovery confidence
- ✅ Event ID in both for correlation
- ✅ ML logging to file with start time, end time, duration
- ✅ **Actual Telegram messages sent and verified on test VM**

### Systemd Service Status Notification (2026-09-12)
- ✅ Created `scripts/systemd_wrapper.py` — wrapper that detects restarts via state file
- ✅ Created `scripts/systemd_notify.py` — direct notifier for lifecycle events
- ✅ Modified `systemd/chk-a.service` — ExecStartPre (start) and ExecStop (stop) use wrapper
- ✅ State file at `/opt/chk-a/last_state.txt` tracks last state to distinguish restart vs fresh start
- ✅ Telegram notifications verified: start, restart, stop all send correct messages
- ✅ Restart detection: previous state "running" + new start → "Service Restart" message
- ✅ Fix: State file permission issue resolved with `sudo chown ipds:ipds`

### Local Time Convention Audit (2026-09-12)
- ✅ `ml_insights.py`: `datetime.utcnow()` → `datetime.now()` in 4 locations (cutoff calc + generated_at)
- ✅ `pdf_generator.py`: Removed " UTC" suffix from PDF header/footer timestamps
- ✅ `email_sender.py`: Removed " UTC" suffix from email body timestamp
- ✅ Verified all other `datetime.now()` usages in project are already local-time
- ✅ All project timestamps now consistently use Asia/Bangkok local time (+07)

### Testing & Operations
- ✅ **313/313 tests pass** on **both dev and test VM** (zero-regression policy)
- ✅ CLI subcommands: `validate-config`, `check-once`, `show-baseline`, `test-telegram`, `test-daily-image`, `mtr`
- ✅ Dev↔Test VM sync via `rsync -c` (checksum) with immediate sync back of VM edits
- ✅ Test VM: Ubuntu 24.04 at 192.168.56.122 (user: ipds), service runs as `chk-a` (uid=999)
- ✅ **Dev→Test sync with CORRECT path** `/home/ipds/Hermes-Prj/chk-a/` on both machines completed

### Security Review & Remediation (Complete — 2026-09-13)
- ✅ Full Security Code Review completed (23 findings: 2 Critical, 5 High, 8 Medium, 5 Low, 3 Info)
- ✅ **C-01 FIXED**: AlertAgent token bucket race condition — `asyncio.Lock` protection
- ✅ **C-02 FIXED**: AlertAgent dedup cache race condition — `asyncio.Lock` protection
- ✅ **H-01 FIXED**: Orchestrator timezone-naive scheduler — `ZoneInfo("Asia/Bangkok")` throughout
- ✅ **H-02 FIXED**: MTR agent timeout calculation — corrected formula
- ✅ **H-03 FIXED**: BaselineStore age key caching — lazy load with cache
- ✅ **H-04 FIXED**: TelegramClient `send_photo` memory — streaming instead of `read_bytes()`
- ✅ **H-05 FIXED**: Orchestrator batch writes — single `write()` per cycle
- ✅ **M-01 FIXED**: ResolverAgent DoH support — implemented (was `NotImplementedError`)
- ✅ **M-02 FIXED**: ConsensusAgent reputation for failed results — skip failed/empty results
- ✅ **M-03 FIXED**: MLAgent path learning key collision — prefix `chk-a:path:` (no DNS collision)
- ✅ **M-04 FIXED**: Parallel MTR for outliers — `asyncio.gather`
- ✅ **M-05 FIXED**: CircuitBreaker thread-safety + concurrent sending
- ✅ **M-06 FIXED**: Health server port/address consistency — both from config
- ✅ **M-07 FIXED**: Graph generator Thai font loading — robust path handling
- ✅ **M-08 FIXED**: AlertAgent log rotation — `RotatingFileHandler` for JSONL and plain text
- ✅ SEC-001 FIXED: MTR Command Injection — IP validation via `ipaddress.ip_address()`
- ✅ SEC-002 FIXED: BaselineStore Path Traversal — path validation with dynamic allowed base dir
- ✅ SEC-003 FIXED: Secrets handling — direct env file parse, log redaction, token in URL path
- ✅ SEC-004 FIXED: Health endpoint — loopback bind only
- ✅ SEC-005 FIXED: Enforce TLS for SMTP — port 465/587 only
- ✅ SEC-006 FIXED: Input validation on critical config fields — Pydantic v2 validators
- ✅ SEC-007 FIXED: Telegram token in URL — token in URL path (Telegram Bot API), masked in logs
- ✅ SEC-008 FIXED: LRU dedup cache with TTL and max-size
- ✅ SEC-009 FIXED: Log injection prevention
- ✅ SEC-012 FIXED: Hard ceilings on concurrency
- ✅ SEC-015 FIXED: Baseline encryption at rest (age/pyrage)
- ✅ SEC-016 FIXED: Dependency pinning with SHA-256 hashes (39 packages)
- ✅ SEC-017 FIXED: Config file permissions (chmod 640/600, chown root:chk-a)
- ✅ SEC-018 FIXED: Telegram circuit breaker (CLOSED/OPEN/HALF_OPEN)
- ✅ SEC-019 FIXED: Daily report scheduler drift fix (absolute time scheduling)
- ✅ SEC-020 FIXED: MTR/Resolver config sync validation

### Telegram Reporter Fix (2026-09-13)
- ✅ **FIXED: Daily report 06:00 AM Telegram 404 error** — Root cause: `TelegramReporter` used `Authorization: Bearer *** header but Telegram Bot API requires token in URL path (`/bot<token>/method`)
- ✅ Updated `TelegramReporter` to use token in URL path (matching `TelegramClient` behavior)
- ✅ Updated security regression tests to verify token-in-URL behavior
- ✅ Circuit breaker automatically recovers after 60s (HALF_OPEN → CLOSED)

### Deployment Infrastructure (2026-09-14)
- ✅ Created `scripts/deploy.sh` — Standard deploy script to install synced source from `/home/ipds/Hermes-Prj/chk-a/` to FHS runtime `/opt/chk-a/` on target machine (test/prod)
- ✅ Uses `rsync -c` checksum verification and restarts systemd service
- ✅ Run with `sudo` after dev→test sync
- ✅ Verified hash equality: Dev source `/home/ipds/Hermes-Prj/chk-a/` ↔ Runtime `/opt/chk-a/` (MD5: `b7717b974eab7b7d163300430e2fdf08`)
- ✅ Fixed test VM config `/etc/chk-a/config.yaml` — Added missing `daily_report_*` settings
- ✅ Service running with updated code and config

### Rotated Log Support & Baseline Integrity Metrics (2026-09-15)
- ✅ **`_load_recent_checks()` auto-reads rotated logs** — date-stamped `.bz2` and numbered `.gz` backups from log directory
- ✅ **Mixed timezone timestamp parsing fixed** — handles both naive (real log) and timezone-aware (mock data) ISO8601 timestamps via `pd.to_datetime(format="mixed", utc=True).dt.tz_localize(None)`
- ✅ **Baseline-based integrity scoring** — uses `MLAgent.score()` (total-variation distance against learned baseline) replacing Isolation Forest
- ✅ **IP stability & diversity metrics added** — `unique_ip_count` and `ip_stability` computed for baseline method (was missing, only in Isolation Forest)
- ✅ **Daily report (yesterday)** — 10,374 records from rotated log `checks.jsonl-20260914.bz2` → Telegram sent successfully
- ✅ **Monthly report (30 days)** — 53,588 records from multiple rotated files → graphs generated successfully
- ✅ **Day 1 sample report (full available data)** — 53,588 records → Telegram sent with 10 graphs
- ✅ **06:00 AM daily report sample (yesterday's data)** — uses `reference_date=yesterday 23:59` → correct yesterday data loaded
- ✅ **Real-time daily report (midnight to now)** — manual run script created, filters to today's data from current log

### Startup Missing Daily Report Check (2026-09-15)
- ✅ **Orchestrator checks for missing yesterday's report on startup** — `_send_missing_daily_report()` called after task initialization
- ✅ Checks `output_dir` for yesterday's report directory; if missing, generates and sends automatically
- ✅ Uses `reference_date=yesterday 23:59:59` to correctly target yesterday's rotated logs
- ✅ Sends to Telegram with same format as scheduled 06:00 report (Thai, emoji, protected palette, hostname, timestamp)

### GitHub Release & Production Installer (2026-09-16)
- ✅ **GitHub Actions Release Workflow** — `.github/workflows/release.yml` builds wheel on tag push (v*), creates GitHub Release with assets
- ✅ **Production Installer (`install.sh`)** — Downloads wheel + assets from GitHub Releases, creates venv, installs wheel, configures systemd, logrotate
- ✅ **Uninstaller (`uninstall.sh`)** — Complete removal of service, configs, logs, state, user
- ✅ **Makefile** — Targets: `install`, `install-github`, `uninstall`, `upgrade`, `status`, `logs`, `version`, `release-dry-run`
- ✅ **v1.0.0** released (2026-09-16) — 10 assets: wheel, install.sh, uninstall.sh, Makefile, config.yaml.example, env.example, chk-a.service, logrotate.chk-a
- ✅ **v1.0.1** released (2026-09-16) — Fixed wheel filename resolution via GitHub API, added pip installation fallback
- ✅ **v1.0.2** released (2026-09-16) — Enhanced pip installation: `ensurepip` with output logging, fallback to `get-pip.py`, verification with version logging

### Install.sh Fixes (2026-09-17)
- ✅ **v1.0.3** — Fix install.sh venv reuse bug (added pip verification, improved logging)
- ✅ **v1.0.4** — Fix env permission to 0640 so service can read Telegram credentials
- ✅ **v1.0.5** — Ensure env.example is present and not empty after download
- ✅ **v1.0.6** — Fix env file permissions (0640) so service can read credentials
- ✅ **v1.0.7** — Ensure env.example is present and not empty after download
- ✅ **v1.0.8** — Move env.example check to /tmp, remove silent failures, add verification step
- ✅ **v1.0.9** — Fix wheel download for "latest" (correct GitHub API endpoint), add timeouts/progress bars
- ✅ **v1.0.10** — Use dedicated temp dir (mktemp) for downloads, remove existing files before download
- ✅ **v1.0.11** — Change default reporting.output_dir to /var/lib/chk-a/reports to fix read-only filesystem error
- ✅ **v1.0.12** — Fix HTML parsing in Telegram messages (remove auto-escape from TelegramClient, add proper escaping in callers)
- ✅ **v1.0.13** — Support Python 3.10+ (Ubuntu 22.04 LTS), add backports.zoneinfo dependency
- ✅ **v1.0.14** — Add manual daily/monthly report scripts for on-demand reporting

### Manual Report Scripts (2026-09-17)
- ✅ `scripts/manual_daily_report.py` — On-demand daily report from midnight to now
- ✅ `scripts/manual_monthly_report.py` — On-demand monthly report from 1st of month to now
- ✅ **Fixed: Both scripts now show ALL resolvers** (removed hardcoded `[:10]` limits) — 2026-09-17 19:30:00
- Both generate Thai/English summaries + graphs, send to Telegram on demand

### Daily Availability Heatmap for Monthly Reports (2026-09-17 20:00:00)
- ✅ Added `daily_availability` computation in `ml_insights.py::compute_availability()`
- ✅ Added `generate_availability_daily_heatmap()` in `graph_generator.py` with Thai version
- ✅ Integrated into `generate_summary_dashboard()` — monthly reports now include both hourly and daily heatmaps
- ✅ Monthly reports: 18-20 graphs total (7 chart types × EN/TH = 14 + 2 Dashboard = 16 + 2 Daily Heatmap = 18)

### v1.0.15 Release (2026-09-18)
#### Fixed
- **2026-09-18 21:00:00** — `src/chk_a/reporting/monthly_report.py` — Fixed: Daily report time range bug. Changed from `datetime.now().replace(hour=23, minute=59) - timedelta(days=1)` (which gave wrong time when run at 06:00) to `yesterday = datetime.now() - timedelta(days=1); yesterday_end = yesterday.replace(hour=23, minute=59)` to correctly get yesterday's 23:59:59.
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — Fixed: Daily midnight task (00:00) error handling for missing images. Added fallback to anomaly/recovery images from AlertAgent, detailed logging for missing images, and graceful skip when no image available.

#### Added
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — Added: Copy `img/` directory to release assets and create `img.tar.gz` for production installation.
- **2026-09-18 21:00:00** — `install.sh` — Added: Download and extract `img.tar.gz` to `/opt/chk-a/img/` during production install.
- **2026-09-18 21:00:00** — `config/config.yaml.example` — Added: Complete configuration example with all sections (fqdns, resolvers, resolver_agent, ml, alert, scheduler, logging, mtr, reporting, baseline_store_path) with Thai comments explaining each setting.
- **2026-09-18 21:00:00** — `config/chk-a.env.example` — Added: Complete environment example with placeholders for Telegram, SMTP, and Age encryption keys.

#### Changed
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — Changed: Improved daily midnight task logging and fallback logic for daily/anomaly/recovery images.
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — Changed: Use new complete `config/config.yaml.example` in release assets instead of old `config/chk-a.config.yaml.example`.

### Production Deployment v1.0.15 (2026-09-18)
- ✅ **Release v1.0.15 created** — GitHub Release with all assets including `img.tar.gz`
- ✅ **Production `uptime-host` installed v1.0.15** — `img/` directory deployed to `/opt/chk-a/img/`
- ✅ **Production config updated** — Added `reporting` section, `mtr` section, `daily_image_path`, `resolver_agent: {}`
- ✅ **00:00 Daily image CONFIRMED WORKING** — Received Telegram message with `sleepy.jpg` + hostname + day separators
- ✅ **06:00 Daily report pending verification** — Next scheduled run

### v1.0.16 Release (2026-09-19)
- ✅ Telegram sequential send + Thai-only graphs

### v1.0.17 Release (2026-09-19)
- ✅ Latency boxplot sort by median ASC (fastest on top)

### v1.0.18 Release (2026-09-19)
- ✅ Timezone fix for daily reports + robust Thai filtering

### v1.0.19 Release (2026-09-19)
- ✅ Graph filename suffix for Thai filtering + consistent daily reports

### v1.0.20 Release (2026-09-19)
- ✅ Timezone fix for daily reports + robust Thai filtering

### v1.0.21 Release (2026-09-19)
- ✅ Debug logging for daily reports + robust Thai filtering

### v1.0.22 Release (2026-09-20)
- ✅ Manual daily report fixes: Thai-only filter, latency boxplot sort, daily heatmap month context

### v1.0.23 Release (2026-09-20)
- ✅ Service startup report fix: Thai-only, today data 00:00-now, daily heatmap month context, background task

### v1.0.24 Release (2026-09-20)
- ✅ Fix pyproject.toml version to 1.0.24 (was 1.0.14) — ensures wheel builds with correct version

### v1.0.25 Release (2026-09-20 17:30:00)
- ✅ Missing daily report on startup now merges month data (Sep 1 to yesterday) for daily availability heatmap
- ✅ Daily heatmap title format: "Days 1 to N" (EN) / "วันที่ 1 ถึง N" (TH) — clearer than "Month: 1st to DD MMM"
- ✅ Month start fix: Both missing & today reports use `month_start = day 1`

### v1.0.26 Release (2026-09-21 06:30:00)
- ✅ Scheduled daily report (06:00 AM) now merges month data (1st to yesterday) for daily availability heatmap, instead of only yesterday's data. Consistent with startup report behavior.

### v1.0.27 Release (2026-09-21 08:00:00)
- ✅ Version display across all reports:
  - Graphs: Version shown in footer center (`vX.Y.Z`) via `_add_header_footer()` in `graph_generator.py`
  - Telegram Monthly Summary: Version at end of message via `create_telegram_summary()` in `telegram_reporter.py`
  - Telegram Daily Summary: Version at end of message via `create_daily_telegram_summary()` in `telegram_reporter.py`
  - Dashboard/Reports: Version passed through `generate_summary_dashboard()` to all 8 chart types

### v1.0.28 Release (2026-09-21 10:30:00)
- ✅ Version detection now works both when installed as package and when running as module (`-m chk_a.main`). Added fallback to read from `pyproject.toml`.
- ✅ CLI commands `test-telegram` and `test-daily-image` now properly extract secret values from `SecretStr` before passing to `TelegramClient`, fixing "Object of type SecretStr is not JSON serializable" error.

### v1.0.29 Release (2026-09-21 15:30:00)
- ✅ MTR CLI target validation auto-appends `:53` for bare IP/hostname, allowing CLI to accept bare IP/hostname as target argument without manual port specification.
- ✅ Test VM Python cache issue resolved: cleared `.pyc` cache to serve updated `__version__` (1.0.29).

### v1.0.30 Release (2026-09-22 14:45:00)
- ✅ **SEC-010**: DoH/DoT resolver support tests added — `test_doh_resolver_resolves()` mocking aiohttp DoH query with DNS wireformat response
- ✅ **SEC-011**: CAP_NET_RAW for MTR ICMP tests added — `TestSEC011_MTRCapNetRaw` class with 3 tests verifying systemd CAP_NET_RAW capability, MTRConfig ICMP mode support, and MTRAgent ICMP privileges
- ✅ **Log Rotation Tests**: Comprehensive tests for `_load_recent_checks()` covering plain JSONL, date-stamped `.bz2` rotated files, numbered `.gz` backups, mixed timezone timestamps, fractional lookback, malformed lines, non-CheckResult log lines, empty/nonexistent files, and edge cases (18 tests)
- ✅ Fixed: `_load_recent_checks()` timestamp parsing for mixed naive and timezone-aware timestamps, preserving local time (Asia/Bangkok) for naive timestamps while converting aware timestamps to Asia/Bangkok
- ✅ Fixed: 13 test functions replacing `tmp_path` pytest fixture with `_make_temp_path()` helper from conftest.py for baseline path consistency

### v1.0.31 Release (2026-09-22 15:30:00)
- ✅ **Email Reporting Tests**: Comprehensive tests for EmailSender class (12 tests) covering STARTTLS/implicit TLS, auth/no-auth, missing attachments, exception handling, create_email_body() function (English/Thai languages, missing summary), and MonthlyReportGenerator integration

### v1.0.32 Release (2026-09-22 16:00:00)
- ✅ **FQDN-centric Data Model**: Added `FQDNRecord` and `FQDNStore` with identity (fqdn, domain, subdomain, apex), DNS records (current IPs, CNAME chain, TTL), history (IP changes with timestamps/sources), metadata (registrar, expiry, NS), monitoring state (last_checked, status, failures), alerting rules, ML features (baseline IPs, anomaly score, flip-flop count, geo shifts)
- ✅ **FQDN Store Tests**: 25 comprehensive tests covering creation, domain extraction, IP change history, monitoring state transitions, baseline/anomaly updates, serialization, persistence, queries (by domain, status, anomaly, recent changes), path traversal protection, corrupt/empty file handling

### v1.0.33 Release (2026-09-22 16:30:00)
- ✅ **Startup Report Heatmap Fix**: Fixed `_send_today_report_on_startup()` to use `reference_date=now` instead of `today_end`, so fractional lookback correctly covers 00:00 to current time (not 09:30-14:30)
- ✅ **Version Bump**: Source files now correctly show 1.0.33 (was 1.0.32 in pyproject.toml and main.py)
- ✅ Python cache cleared and package reinstalled for correct `__version__` detection

### v1.0.34 Release (2026-09-22 16:30:00)
- ✅ **Modern Graph Styling**: Complete overhaul of `graph_generator.py` with colorblind-safe palette (viridis heatmap, semantic colors), clean aesthetics (no top/right spines, subtle grid), higher DPI (200), colorblind-safe categorical palette (seaborn colorblind), Thai font improvements (bold weight, adjusted sizes). Footer version now in primary blue color.
- ✅ **Alert/Recovery Version Footer**: Added version footer to Telegram alert and recovery messages (`🏷️ <b>chk-a v1.0.34</b>`)
- ✅ **Test VM Sync**: All source files synced to test VM via rsync, 313/313 tests passing on test VM
- ✅ **Production Ready**: GitHub Release v1.0.34 published with all assets

---

## 4. In Progress

None — all critical issues resolved as of v1.0.34.

---

## 5. Known Issues

### Resolved
- ✅ seaborn installed on test VM
- ✅ `send_photo` mock signature fixed in test_alert_agent.py
- ✅ State file permission issue resolved: `sudo chown ipds:ipds /opt/chk-a/last_state.txt`
- ✅ `sudo: A terminal is required to authenticate` — user runs sudo commands directly on test VM
- ✅ **Daily report Telegram 404 error** — Fixed by using token in URL path (Telegram Bot API requirement)
- ✅ **Test VM missing daily_report_* config** — Added to `/etc/chk-a/config.yaml`
- ✅ **Runtime code mismatch** — Fixed by running `scripts/deploy.sh` on test VM
- ✅ **Missing yesterday's report on startup** — Auto-check and generate on service start
- ✅ **v1.0.0/v1.0.1 install.sh wheel download** — Fixed via GitHub API lookup + constructed filename fallback
- ✅ **v1.0.1/v1.0.2 pip installation** — Added ensurepip + get-pip.py fallback + verification
- ✅ **v1.0.3-v1.0.14** — Sequential fixes for install.sh, env permissions, env.example, wheel download, temp dirs, output_dir, Python 3.10+, manual report scripts
- ✅ **Daily report time range bug** — Fixed in v1.0.15 (monthly_report.py)
- ✅ **Daily midnight task missing image** — Fixed in v1.0.15 (orchestrator.py fallback logic)
- ✅ **Release assets missing img.tar.gz** — Fixed in v1.0.15 (release.yml + install.sh)
- ✅ **Daily startup report: Thai-only graphs + today's data (00:00 to now)** — Fixed in v1.0.23/v1.0.25
- ✅ **Missing daily report month merge** — Fixed in v1.0.25
- ✅ **Daily heatmap title format** — Fixed in v1.0.25 ("Days 1 to N" / "วันที่ 1 ถึง N")
- ✅ **Scheduled daily report month merge** — Fixed in v1.0.26
- ✅ **Version display across all reports** — Fixed in v1.0.27
- ✅ **Version detection (package vs module)** — Fixed in v1.0.28
- ✅ **SecretStr JSON serialization in CLI** — Fixed in v1.0.28
- ✅ **MTR CLI target validation** — Fixed in v1.0.29
- ✅ **Test VM Python cache** — Fixed in v1.0.29
- ✅ **SEC-010/011 tests** — Added in v1.0.30
- ✅ **Log rotation tests** — Added in v1.0.30
- ✅ **tmp_path fixture misuse** — Fixed in v1.0.30
- ✅ **Email reporting tests** — Added in v1.0.31
- ✅ **FQDN-centric model** — Implemented in v1.0.32
- ✅ **Startup heatmap window bug** — Fixed in v1.0.33
- ✅ **Version bump in source files** — Fixed in v1.0.33
- ✅ **Alert/Recovery version footer** — Added in v1.0.33 (local)
- ✅ **Modern graph styling** — Implemented in v1.0.34

### Active
None — all known issues resolved.

---

## 6. Next Actions

### This Sprint (P2)
- SEC-010/011 — DoH/DoT support, CAP_NET_RAW for MTR (already implemented, tests added)
- Add log rotation test coverage (completed in v1.0.30)
- Email reporting integration (tests added in v1.0.31, implementation exists)
- FQDN-centric model integration with agents (completed in v1.0.32)

### This Quarter (P3)
- Dashboard web UI (FastAPI + HTMX + Chart.js)
- GitHub repo cleanup & branch consolidation
- Historical data compaction

---

## 7. Related Files

### Core Agents
| File | Lines | Purpose |
|------|-------|---------|
| `src/chk_a/agents/resolver_agent.py` | ~280 | Parallel DNS query, health EMA |
| `src/chk_a/agents/consensus_agent.py` | ~220 | Weighted vote, entropy, outliers, reputation |
| `src/chk_a/agents/ml_agent.py` | ~180 | Exponential decay baseline, anomaly scoring |
| `src/chk_a/agents/alert_agent.py` | ~350 | Dedup, rate-limit, Telegram, dual audit logs |
| `src/chk_a/agents/mtr_agent.py` | ~400 | MTR subprocess, JSON parsing, hop stats |
| `src/chk_a/storage/fqdn_store.py` | ~350 | FQDN-centric data model & storage |

### Orchestration & Config
| File | Lines | Purpose |
|------|-------|---------|
| `src/chk_a/orchestrator.py` | ~550 | Cycle coordination, scheduler, healthz, daily/monthly tasks |
| `src/chk_a/config/loader.py` | ~200 | YAML + env substitution, Pydantic, auto-tune |
| `src/chk_a/models/schemas.py` | ~250 | All Pydantic contracts |
| `src/chk_a/storage/baseline_store.py` | ~120 | Atomic JSON baseline persistence |

### Reporting
| File | Lines | Purpose |
|------|-------|---------|
| `src/chk_a/reporting/graph_generator.py` | ~950 | 7 chart types × EN/TH, Thai fonts, translation map + Daily Heatmap |
| `src/chk_a/reporting/monthly_report.py` | ~350 | Report pipeline: insights → graphs → PDF → Telegram/email |
| `src/chk_a/reporting/telegram_reporter.py` | ~400 | Batched photo sending, exponential backoff, HTML summary |
| `src/chk_a/reporting/pdf_generator.py` | ~200 | fpdf2 EN/TH templates |
| `src/chk_a/reporting/ml_insights.py` | ~260 | Availability, integrity, path health, anomaly detection + daily_availability |
| `src/chk_a/reporting/telegram_client.py` | ~180 | Async Telegram client with retry, circuit breaker |
| `src/chk_a/reporting/email_sender.py` | ~200 | SMTP email with TLS, PDF attachments |

### Entry Point & Config
| File | Purpose |
|------|---------|
| `src/chk_a/main.py` | CLI + daemon entry, subcommands |
| `systemd/chk-a.service` | Modified: ExecStartPre/ExecStop use systemd_wrapper.py for status notifications |
| `/etc/chk-a/config.yaml` | Production config (test VM & production) |
| `/opt/chk-a/config.example.yaml` | Config reference |
| `/etc/chk-a/env` | **Telegram credentials** (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) |

### Scripts
| File | Purpose |
|------|---------|
| `scripts/systemd_wrapper.py` | Systemd service wrapper — detects restarts, sends start/restart/stop/fail notifications |
| `scripts/systemd_notify.py` | Direct systemd status notifier — start/stop/restart/fail/error |
| `scripts/send_test_telegram.py` | Sends test anomaly/recovery Telegram messages with images |
| `scripts/deploy.sh` | Deploy synced source to FHS runtime `/opt/chk-a/` |
| `scripts/manual_daily_report.py` | On-demand daily report from midnight to now |
| `scripts/manual_monthly_report.py` | On-demand monthly report from 1st to now |

### Test & Scripts
| File | Purpose |
|------|---------|
| `tests/test_alert_agent.py` | Alert agent tests (updated for `send_photo` signature) |
| `tests/conftest.py` | Session-wide test config (`CHK_A_BASELINE_DIR=/tmp`) |
| `tests/test_integration_pipeline.py` | Full pipeline integration tests (7 tests) |
| `tests/test_security_regressions.py` | Security regression tests (74 tests, SEC-001 to SEC-020) |
| `tests/test_fqdn_store.py` | FQDN store tests (25 tests) |
| `tests/test_reporting.py` | Log rotation tests (18 tests) |
| `tests/test_email_sender.py` | Email sender tests (12 tests) |

### Release & Deployment
| File | Purpose |
|------|---------|
| `.github/workflows/release.yml` | GitHub Actions: build wheel, create release on tag push |
| `install.sh` | Production installer from GitHub Releases |
| `uninstall.sh` | Production uninstaller |
| `Makefile` | Dev/ops targets: install, uninstall, upgrade, status, logs, version |

---

## 8. TODO List

See [TODO.md](TODO.md) for detailed breakdown.

---

*Generated by Hermes Agent session on 2026-09-22 15:40:32 (Asia/Bangkok UTC+07)*