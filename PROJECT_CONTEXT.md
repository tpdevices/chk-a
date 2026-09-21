# Project Context — chk-a

**Last Updated:** 2026-09-21 15:30:00 (Asia/Bangkok UTC+07)

---

## Project Overview

**chk-a** is a multi-agent DNS A-record anomaly monitoring system. It continuously queries multiple DNS resolvers for configured FQDNs, builds a weighted consensus, learns baselines via online exponential-decay counters, detects anomalies, and sends formatted alerts via Telegram with comprehensive reporting (daily/monthly, EN/TH, charts + PDF).

**Repository:** `tpdevices/chk-a` (GitHub, HTTPS with PAT)  
**Development:** WSL Ubuntu (172.20.14.199/20)  
**Test Target:** VirtualBox Ubuntu 24.04 at 192.168.56.122 (user: ipds)  
**Production:** `uptime-host` (internal DNS monitoring)  
**Service User:** `chk-a` (uid=999)  
**Python:** 3.14.4 (`python3`, PEP 668 → venv/uv)  
**All timestamps:** Local Asia/Bangkok (+07), format `YYYY-MM-DD HH:MM:SS`

---

## Architecture

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

## Key Design Decisions

1. **No Prometheus/metrics** — Observability via structured JSONL logs + `/healthz` + systemd watchdog
2. **No Heavy ML dependencies** — Online EMA baseline, total-variation anomaly score (stdlib only, no sklearn/torch)
3. **Thai Language First-class** — All 7 chart types have EN/TH versions, `_apply_thai_fonts()` with translation map, auto-detect Thai font (Loma/TLWG)
4. **Atomic Persistence** — Baseline store uses temp file + `os.replace` + `fsync`; dedup cache same pattern
5. **Config-driven** — YAML with `${ENV}` substitution, Pydantic validation, auto-tuned concurrency
6. **Dev↔Test Sync** — `rsync -c` (checksum) from dev to test VM, immediate sync back of VM edits
7. **Telegram Delivery Reliability** — Batched sending (configurable batch size/delay/retries), exponential backoff (2s→4s→8s)
8. **Anomaly/Recovery Notifications with Images** — Event ID correlation, MTR last unreachable IP, duration tracking, ML logging (2026-09-09)
9. **Systemd Service Status Notification** — Wrapper-based approach using state file to detect restarts, sends lifecycle events to Telegram (2026-09-12)
10. **Local Time Convention** — All timestamps use Asia/Bangkok local time (+07); no UTC in calculations, outputs, or documentation (2026-09-12)
11. **Security Code Review Complete** — All Critical/High/Medium findings fixed (2026-09-13)
12. **Standard Deployment Path** — Dev source at `/home/ipds/Hermes-Prj/chk-a/`, runtime at `/opt/chk-a/` (FHS), deploy via `scripts/deploy.sh` (2026-09-14)
13. **Rotated Log Support** — `_load_recent_checks()` auto-reads date-stamped `.bz2` and numbered `.gz` backups (2026-09-15)
14. **Baseline-based Integrity** — Uses `MLAgent.score()` (total-variation distance) replacing Isolation Forest, with IP stability/diversity metrics (2026-09-15)
15. **Startup Missing Report Check** — Orchestrator checks and sends yesterday's daily report on startup if missing (2026-09-15)
16. **GitHub Release & Production Installer** — Actions workflow builds wheel on tag, creates release; `install.sh` downloads from GitHub Releases, installs to `/opt/chk-a/` with systemd (2026-09-16)
17. **Manual Report Scripts** — `manual_daily_report.py` and `manual_monthly_report.py` for on-demand reporting (2026-09-17)
18. **All Resolvers Displayed in Telegram** — Removed Top 5/10 limits from summaries and graph sending (2026-09-17 15:30:00, 19:30:00)
19. **Daily Availability Heatmap** — Added day-of-month vs resolver heatmap for monthly reports (2026-09-17 20:00:00)
20. **v1.0.15 Release** — Fixed daily report time range bug, daily midnight task image fallback, complete config examples, img/ in release assets (2026-09-18)
21. **v1.0.16 Release** — Telegram sequential send + Thai-only graphs (2026-09-19)
22. **v1.0.17 Release** — Latency boxplot sort by median ASC (fastest on top) (2026-09-19)
23. **v1.0.18 Release** — Timezone fix for daily reports + robust Thai filtering (2026-09-19)
24. **v1.0.19 Release** — Graph filename suffix for Thai filtering + consistent daily reports (2026-09-19)
25. **v1.0.20 Release** — Timezone fix for daily reports + robust Thai filtering (2026-09-19)
26. **v1.0.21 Release** — Debug logging for daily reports + robust Thai filtering (2026-09-19)
27. **v1.0.22 Release** — Manual daily report fixes: Thai-only filter, latency boxplot sort, daily heatmap month context (2026-09-20)
26. **v1.0.23 Release** — Service startup report fix: Thai-only, today data 00:00-now, daily heatmap month context, background task (2026-09-20)
27. **v1.0.24 Release** — Fix pyproject.toml version to 1.0.24 (was 1.0.14) — ensures wheel builds with correct version (2026-09-20)
28. **v1.0.25 Release** — Missing daily report month merge + daily heatmap title format (Days 1 to N / วันที่ 1 ถึง N) (2026-09-20)

---

## Configuration

**Primary:** `/etc/chk-a/config.yaml` (test VM & production)  
**Reference:** `/opt/chk-a/config.example.yaml`

Key Sections:
- `fqdns` — List of FQDNs with `min_consensus` and `expected_ips` (optional)
- `resolvers` — Resolver endpoints (`name`, `address` as `IP:port`, `weight`, `timeout_ms`)
- `resolver_agent` — `max_concurrent`, `default_timeout_ms` (auto-tuned)
- `ml` — `baseline_decay`, `anomaly_threshold`, `min_samples_before_alert`
- `alert` — Telegram credentials, dedup window, rate limit, log paths, daily image config, dedup cache path
- `scheduler` — `min_interval_sec` (30), `max_interval_sec` (180), `jitter`
- `mtr` — enabled flag, interval, max_hops, count, interval_ms, timeout_sec, mode (icmp/tcp/udp), resolvers list
- `reporting` — Monthly/daily schedules, output dir, Telegram/email config, graph inclusion
- `baseline_store_path` — `/var/lib/chk-a/baselines.json`

**Secrets:** `/etc/chk-a/env` — Stores `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (test VM & production)

---

## Reporting Details

### Monthly Report (1st of month, 06:00 AM)
- ML insights from 30-day lookback
- 7 chart types × EN/TH = 14 charts + 2 Dashboards = 16 files
- **NEW: Daily Availability Heatmap** — day-of-month vs resolver availability matrix (EN/TH = 2 additional graphs)
- Total: 18-20 graphs per monthly report
- PDF reports (EN/TH) via fpdf2
- Telegram: Thai summary + charts (batched, all graphs sent)
- Email: Full PDF attachment

### Daily Report (06:00 AM, lookback 1 day)
- Same charts, 1-day time window
- Telegram: Thai summary + charts (batched, all graphs sent)

### Chart Types (7)
1. Availability Bar (availability % per resolver)
2. Availability Heatmap (hourly per resolver)
3. **NEW: Daily Availability Heatmap** (day-of-month per resolver)
4. Integrity Score (ML-based per resolver)
5. Latency Boxplot (latency distribution per resolver)
6. IP Stability & Diversity (unique IP set, stability %)
7. MTR Path Visualization (hop loss/latency)
8. Path Availability (ML-based network path health)

### Thai Display
Every chart calls `_apply_thai_fonts()` → translation map covers all labels, footer split left/right (hostname | timestamp), lang param controls TH/EN without duplication

---

## Telegram Formats

### Alert Messages (HTML)
- Severity emojis: 🔴 Critical / 🟡 Warning / 🔵 Info
- Type labels: 📊 Baseline Deviation / 🗳️ Consensus Deviation / 🆕 New IP / 🚫 NXDOMAIN
- Groups Majority vs Outliers
- Failed resolvers shown separately
- Baseline comparison for baseline_deviation
- Hostname, resolver names, timestamp (local time)

### Anomaly/Recovery Notifications (2026-09-09)
- **Event ID:** `{hostname}-YYYYMMDD-HHmmss` (both anomaly and recovery for correlation)
- **Anomaly:** `img/priority.jpg` + cause, last unreachable IP from MTR, consensus score
- **Recovery:** `img/ok.jpg` + anomaly duration (h/m/s), ML baseline stability, recovery confidence
- ML logging to file with start time, end time, duration

### Service Status Notifications (2026-09-12)
- **Start:** 🟢 Service Start notification
- **Restart:** 🔄 Service Restart notification (detected via state file)
- **Stop:** 🔴 Service Stop notification
- **Fail:** ❌ Service Fail notification with details
- **Error:** ⚠️ Service Error notification with details
- Sent via `systemd_wrapper.py` (ExecStartPre for start, ExecStop for stop)

### Plain Text Log (`/var/log/chk-a/alerts.log`)
```
YYYY-MM-DD HH:MM:SS hostname resolver ip event_type: fqdn
```

### Day Separators at midnight in all log files

---

## Testing & Quality

- **257/257 tests pass** on **both dev and test VM** (zero-regression policy)
- **Test Location:** Everything on test VM (pytest, CLI, systemd, DNS/Telegram/MTR)
- **Fix Tests, Not Agent Code** — per project rules
- **Code Review Patterns:** Per skill `software-development` → `code-review-patterns`

---

## Security Status

**Security Code Review Complete:** 23 findings
- **2 Critical:** AlertAgent token bucket race (C-01) ✅ FIXED, AlertAgent dedup cache race (C-02) ✅ FIXED
- **5 High:** Orchestrator timezone-naive scheduler (H-01) ✅ FIXED, MTR timeout calc (H-02) ✅ FIXED, BaselineStore key caching (H-03) ✅ FIXED, TelegramClient memory (H-04) ✅ FIXED, Orchestrator batch writes (H-05) ✅ FIXED
- **8 Medium:** DoH support (M-01) ✅ FIXED, Consensus reputation (M-02) ✅ FIXED, MLAgent key collision (M-03) ✅ FIXED, Parallel MTR (M-04) ✅ FIXED, CircuitBreaker (M-05) ✅ FIXED, Health server consistency (M-06) ✅ FIXED, Thai font loading (M-07) ✅ FIXED, AlertAgent log rotation (M-08) ✅ FIXED
- **5 Low/Info:** SEC-010 (DoH/DoT) ✅ FIXED, SEC-011 (CAP_NET_RAW) ✅ FIXED, SEC-013 (log perms) ✅ FIXED, SEC-014 (HTML escape) ✅ FIXED (2026-09-17), SEC-015..SEC-020 ✅ FIXED

**Fixed (Security Regression Tests SEC-001..SEC-020):**
- SEC-001: Added `_validate_target_ip()` in `mtr_agent.py` using `ipaddress.ip_address()`
- SEC-002: Added path validation in `baseline_store.py` `__init__` and `_is_path_allowed()`, dynamic `_get_allowed_base_dir()` from `CHK_A_BASELINE_DIR`
- SEC-003: Parse `/etc/chk-a/env` directly into config model (no `os.environ` pollution); redact tokens in logs; use **token in URL path (required by Telegram Bot API), masked in logs**
- SEC-004: Changed `_health_bind_address()` to instance method reading from validated config; loopback validation in `SchedulerConfig`; removed env-var bypass
- SEC-005: Removed `email_use_tls` field; port-based TLS — port 465 uses `SMTP_SSL`, port 587 uses `SMTP` + `starttls()`
- SEC-006: Pydantic v2 validators in models — FQDN (RFC 1035/2181), resolver address (IP:port/hostname:port/DoH), expected IPs
- SEC-007: Telegram API calls use **token in URL path (required by Telegram Bot API), masked in logs**
- SEC-008: LRU dedup cache with TTL and max-size (OrderedDict, maxsize=10000, ttl_sec=3600)
- SEC-009: Log injection prevention via `_sanitize_log_field()` (escapes newlines, carriage returns, tabs)
- SEC-012: Hard concurrency ceiling — MTR semaphore (4), max_concurrent capped at 100, Telegram circuit breaker
- SEC-015: Baseline encryption at rest via age/pyrage (public key in config, private key from env)
- SEC-016: Pinned dependencies with SHA-256 hashes (39 packages), CI with pip-audit
- SEC-017: Config perms `chmod 640`, env perms `chmod 600`, chown root:chk-a
- SEC-018: Telegram circuit breaker (CLOSED/OPEN/HALF_OPEN, threshold=5, recovery=60s)
- SEC-019: Daily report scheduler drift fix — absolute time scheduling with fixed reference point
- SEC-020: MTR/Resolver config sync validation — `mtr.resolvers` must be subset of `resolvers`
- Test infrastructure: `tests/conftest.py` sets `CHK_A_BASELINE_DIR=/tmp`

### Telegram Reporter Fix (2026-09-13)
- **Root Cause:** `TelegramReporter` used `Authorization: Bearer *** header but Telegram Bot API requires token in URL path (`/bot<token>/method`)
- **Impact:** Daily report at 06:00 AM failed with 404 Not Found; midnight image worked because it uses `TelegramClient` (token in URL)
- **Fix:** Updated `TelegramReporter` to use token in URL path (matching `TelegramClient` behavior)
- **Files Changed:** `src/chk_a/reporting/telegram_reporter.py`, `tests/test_security_regressions.py`
- **Circuit Breaker:** Automatically recovers after 60s (HALF_OPEN → CLOSED)

### Deployment Infrastructure (2026-09-14)
- **Created `scripts/deploy.sh`** — Standard deploy script to install synced source from `/home/ipds/Hermes-Prj/chk-a/` to FHS runtime `/opt/chk-a/` on target machine (test/prod)
- Uses `rsync -c` checksum verification and restarts systemd service
- Run with `sudo` after dev→test sync
- Verified hash equality: Dev source `/home/ipds/Hermes-Prj/chk-a/` ↔ Runtime `/opt/chk-a/` (MD5: `b7717b974eab7b7d163300430e2fdf08`)
- Fixed test VM config `/etc/chk-a/config.yaml` — Added missing `daily_report_*` settings
- Service running with updated code and config

### Rotated Log Support & Baseline Integrity Metrics (2026-09-15)
- **`_load_recent_checks()` auto-reads rotated logs** — date-stamped `.bz2` and numbered `.gz` backups from log directory
- **Mixed timezone timestamp parsing fixed** — handles both naive (real log) and timezone-aware (mock data) ISO8601 timestamps via `pd.to_datetime(format="mixed", utc=True).dt.tz_localize(None)`
- **Baseline-based integrity scoring** — uses `MLAgent.score()` (total-variation distance against learned baseline) replacing Isolation Forest
- **IP stability & diversity metrics added** — `unique_ip_count` and `ip_stability` computed for baseline method (was missing, only in Isolation Forest)
- **Daily report (yesterday)** — 10,374 records from rotated log `checks.jsonl-20260914.bz2` → Telegram sent successfully
- **Monthly report (30 days)** — 53,588 records from multiple rotated files → graphs generated successfully
- **Day 1 sample report (full available data)** — 53,588 records → Telegram sent with 10 graphs
- **06:00 AM daily report sample (yesterday's data)** — uses `reference_date=yesterday 23:59` → correct yesterday data loaded
- **Real-time daily report (midnight to now)** — manual run script created, filters to today's data from current log

### Startup Missing Daily Report Check (2026-09-15)
- **Orchestrator checks for missing yesterday's report on startup** — `_send_missing_daily_report()` called after task initialization
- Checks `output_dir` for yesterday's report directory; if missing, generates and sends automatically
- Uses `reference_date=yesterday 23:59:59` to correctly target yesterday's rotated logs
- Sends to Telegram with same format as scheduled 06:00 report (Thai, emoji, protected palette, hostname, timestamp)

### GitHub Release & Production Installer (2026-09-16)
- **GitHub Actions Release Workflow** — `.github/workflows/release.yml` builds wheel on tag push (v*), creates GitHub Release with assets
- **Production Installer (`install.sh`)** — Downloads wheel + assets from GitHub Releases, creates venv, installs wheel, configures systemd, logrotate
- **Uninstaller (`uninstall.sh`)** — Complete removal of service, configs, logs, state, user
- **Makefile** — Targets: `install`, `install-github`, `uninstall`, `upgrade`, `status`, `logs`, `version`, `release-dry-run`
- **v1.0.0 released** (2026-09-16) — 10 assets: wheel, install.sh, uninstall.sh, Makefile, config.yaml.example, env.example, chk-a.service, logrotate.chk-a
- **v1.0.1 released** (2026-09-16) — Fixed wheel filename resolution via GitHub API, added pip installation fallback
- **v1.0.2 released** (2026-09-16) — Enhanced pip installation: `ensurepip` with output logging, fallback to `get-pip.py`, verification with version logging

### Install.sh Fixes (2026-09-17)
- **v1.0.3** — Fix install.sh venv reuse bug (added pip verification, improved logging)
- **v1.0.4** — Fix env permission to 0640 so service can read Telegram credentials
- **v1.0.5** — Ensure env.example is present and not empty after download
- **v1.0.6** — Fix env file permissions (0640) so service can read credentials
- **v1.0.7** — Ensure env.example is present and not empty after download
- **v1.0.8** — Move env.example check to /tmp, remove silent failures, add verification step
- **v1.0.9** — Fix wheel download for "latest" (correct GitHub API endpoint), add timeouts/progress bars
- **v1.0.10** — Use dedicated temp dir (mktemp) for downloads, remove existing files before download
- **v1.0.11** — Change default reporting.output_dir to /var/lib/chk-a/reports to fix read-only filesystem error
- **v1.0.12** — Fix HTML parsing in Telegram messages (remove auto-escape from TelegramClient, add proper escaping in callers)
- **v1.0.13** — Support Python 3.10+ (Ubuntu 22.04 LTS), add backports.zoneinfo dependency
- **v1.0.14** — Add manual daily/monthly report scripts for on-demand reporting

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
- **Fixed:** Daily report time range bug (monthly_report.py), daily midnight task image fallback (orchestrator.py)
- **Added:** img/ directory in release assets (img.tar.gz), complete config.yaml.example with Thai comments, complete chk-a.env.example
- **Changed:** Release workflow uses new config.yaml.example, install.sh extracts img.tar.gz to /opt/chk-a/img/
- **Production:** uptime-host installed v1.0.15, 00:00 daily image confirmed working

### v1.0.16 Release (2026-09-19)
- Telegram sequential send + Thai-only graphs

### v1.0.17 Release (2026-09-19)
- Latency boxplot sort by median ASC (fastest on top)

### v1.0.18 Release (2026-09-19)
- Timezone fix for daily reports + robust Thai filtering

### v1.0.19 Release (2026-09-19)
- Graph filename suffix for Thai filtering + consistent daily reports

### v1.0.20 Release (2026-09-19)
- Timezone fix for daily reports + robust Thai filtering

### v1.0.21 Release (2026-09-19)
- Debug logging for daily reports + robust Thai filtering

### v1.0.22 Release (2026-09-20)
- Manual daily report fixes: Thai-only filter, latency boxplot sort, daily heatmap month context

### v1.0.23 Release (2026-09-20)
- Service startup report fix: Thai-only, today data 00:00-now, daily heatmap month context, background task

### v1.0.24 Release (2026-09-20)
- Fix pyproject.toml version to 1.0.24 (was 1.0.14) — ensures wheel builds with correct version

### v1.0.25 Release (2026-09-20)
- Missing daily report month merge + daily heatmap title format (Days 1 to N / วันที่ 1 ถึง N)

---

## AI Model Config (for cyber-security-review)

**Available Providers:** NVIDIA (primary), 9router/OpenRouter/AnyAPI/Aihubmix (gateways), Ollama-Local, Poolside.AI

**Recommended Reference Models:**
1. `nvidia/nemotron-3-ultra-550b-a55b` — Primary analyst (highest reasoning strength)
2. `poolside/laguna-s-2.1` — Code specialist (security code review)
3. `anthropic/claude-3.5-sonnet` — General analyst (balanced, context 200k)
4. `openai/gpt-4o` — Multimodal (diagrams, configs)
5. `qwen2.5-coder:7b` (Ollama-Local) — Local static analysis

**Recommended Aggregators:**
1. `nvidia/nemotron-3-ultra-550b-a55b` — Primary (evidence weighing, CVSS scoring)
2. `anthropic/claude-3.5-sonnet` — Fallback (calibrated judgment)

---

## Operational Notes

- **SSH:** Dev→Test passwordless (`ipds@192.168.56.122`), reverse NOT possible
- **Logs:** `journalctl -u chk-a-resolver -f` (and consensus, alert, mtr)
- **Config Change:** Edit `/etc/chk-a/config.yaml` → `sudo systemctl restart chk-a-*`
- **MTR Resolvers List** in config separate from `resolvers` list — must sync manually
- **GitHub:** HTTPS with PAT (no SSH on WSL)
- **Service Status Notification:** `systemd_wrapper.py` is called via ExecStartPre (start) and ExecStop (stop) in `systemd/chk-a.service`; state file at `/opt/chk-a/last_state.txt`
- **State File Permission:** Must run `sudo chown ipds:ipds /opt/chk-a/last_state.txt` after initial creation
- **Time Convention:** All timestamps use local Asia/Bangkok time (+07); `datetime.now()` throughout, no `datetime.utcnow()` anywhere
- **Standard Deploy Workflow:**
  1. Dev: Edit code in `/home/ipds/Hermes-Prj/chk-a/`
  2. Dev: `rsync -avz -c /home/ipds/Hermes-Prj/chk-a/ ipds@192.168.56.122:/home/ipds/Hermes-Prj/chk-a/`
  3. Test VM: `sudo /home/ipds/Hermes-Prj/chk-a/scripts/deploy.sh`
- **Production Install Workflow:**
  1. `curl -L -o install.sh https://github.com/tpdevices/chk-a/releases/download/v1.0.25/install.sh`
  2. `chmod +x install.sh`
  3. `sudo ./install.sh v1.0.25`
  4. Edit `/etc/chk-a/env` with Telegram credentials
  5. Edit `/etc/chk-a/config.yaml` with FQDNs/resolvers
  6. `sudo systemctl restart chk-a`

---

*Created by Hermes Agent session on 2026-09-20 17:30:00 (Asia/Bangkok UTC+07)*