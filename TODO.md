# TODO List - chk-a Project

**Last Updated:** 2026-09-16 11:45:00 (Asia/Bangkok UTC+07)

---

## 🔴 P0 — Critical (Today)

---

## 🟠 P1 — High (This Week)
- [ ] Document systemd unit files in repo (for reference)
- [ ] Add deployment checklist (config perms, systemd caps, log dirs)
- [ ] Create runbook for common operations (add resolver, add FQDN, rotate tokens)

---

## 🟡 P2 — Medium (Next Sprint)
- [x] SEC-010: Implement DoH/DoT support in ResolverAgent — COMPLETED (2026-09-16)
  - DoH (DNS-over-HTTPS) with wireformat (RFC 8484) — Google, Cloudflare verified
  - DoT (DNS-over-TLS) with hostname-to-IP resolution — Google verified, Cloudflare network blocked
  - Config validation for `tls://host:port` format
  - Unit tests added and passing
- [x] SEC-011: Verify MTR `CAP_NET_RAW` in systemd unit — COMPLETED (2026-09-16)
  - Added `CapabilityBoundingSet=CAP_NET_RAW` and `AmbientCapabilities=CAP_NET_RAW`
  - Fixed systemd_wrapper state file path for `ProtectSystem=strict`
  - MTR ICMP mode verified working on test VM
- [x] SEC-013: Log file permissions hardening — COMPLETED (2026-09-16)
  - Added `file_mode` (default 0o640) and `dir_mode` (default 0o750) to `LoggingConfig` and `AlertConfig`
  - Updated `setup_logger()` and `AlertAgent._setup_alert_log_handlers()` to apply permissions
  - Verified on test VM: files 640 (rw-r-----), dirs 750 (rwxr-x---), owned by chk-a:chk-a
- [ ] SEC-014: HTML escape in Telegram messages

---

## 🟢 P3 — Low (Ongoing)

---

## 🔧 Functional Improvements
- [x] **Systemd Service Status Notification** — COMPLETED (2026-09-12)
  - Created `scripts/systemd_wrapper.py` — Wrapper with restart detection via state file
  - Created `scripts/systemd_notify.py` — Direct notifier for start/stop/restart/fail/error
  - Modified `systemd/chk-a.service` — ExecStartPre (start) and ExecStop (stop) use wrapper
  - Telegram emojis: 🟢 start, 🔄 restart, 🔴 stop, ❌ fail, ⚠️ error
  - State file at `/opt/chk-a/last_state.txt` tracks last state
- [x] **SEC-008:** Dedup cache LRU + TTL + max-size — COMPLETED (2026-09-11)
- [x] **SEC-009:** Log injection prevention — COMPLETED (2026-09-11)
- [x] **SEC-012:** Hard ceilings on concurrency — COMPLETED (2026-09-11)
- [x] **SEC-015:** Baseline encryption at rest — COMPLETED (2026-09-11)
- [x] **SEC-016:** Dependency pinning with hashes — COMPLETED (2026-09-12)
- [x] **SEC-017:** Config file permissions — COMPLETED (2026-09-12)
- [x] **SEC-018:** Telegram circuit breaker — COMPLETED (2026-09-11)
- [x] **SEC-019:** Daily report scheduler drift fix — COMPLETED (2026-09-12)
- [x] **SEC-020:** MTR/Resolver config sync validation — COMPLETED (2026-09-12)
- [x] **MTR/Resolver config sync validation** — COMPLETED (2026-09-12)
  - Added `_validate_mtr_resolvers_subset()` validator in `AppConfig`
  - Ensures `mtr.resolvers` is a subset of `resolvers` names
  - 3 tests added: valid subset, empty allowed, missing rejected
- [x] **Thai font bundling** — COMPLETED (2026-09-12)
  - Bundled Loma Thai fonts (4 .otf files) in `src/chk_a/fonts/`
  - Added `[tool.setuptools.package-data]` in `pyproject.toml` + `MANIFEST.in`
  - `graph_generator.py` loads fonts via `importlib.resources` with fallback to system fonts
- [x] **Daily report scheduler drift fix** — COMPLETED (2026-09-12)
  - Changed `_run_daily_report()` to use absolute time scheduling from fixed reference point
  - `reference_run += timedelta(days=1)` eliminates cumulative drift
  - Daily report runs exactly at configured hour:minute (default 06:00) every day
- [x] **Telegram ClientSession reuse** — COMPLETED (2026-09-12)
  - Single `aiohttp.ClientSession` for connection pooling across all Telegram API calls
  - `_get_session()` lazy-initializes session, `close()` method for graceful shutdown
- [x] **All timestamps local-time convention audit** — COMPLETED (2026-09-12)
  - `ml_insights.py`: `datetime.utcnow()` → `datetime.now()` in 4 locations (cutoff calc + generated_at)
  - `pdf_generator.py`: Removed " UTC" suffix from PDF header/footer timestamps
  - `email_sender.py`: Removed " UTC" suffix from email body timestamp
  - Verified all other datetime.now() usages in project are already local-time
  - All project timestamps now consistently use Asia/Bangkok local time (+07)
  - Orchestrator: `_run_mtr_on_anomaly()` runs MTR trace on anomaly detection
  - MTR Agent: Uses TCP/UDP mode on resolver's DNS port for path analysis
  - ML Agent: `learn_path_pattern()` learns path signatures, `score_path_anomaly()` scores path anomalies
  - Alert Agent: Telegram includes MTR analysis (Last Hop IP, Problem Hops, Path status)
  - JSONL logging for MTR traces for ML training
- [x] **Telegram Reporter Fix (Daily Report 06:00 AM 404 Error)** — COMPLETED (2026-09-13)
  - Root cause: `TelegramReporter` used `Authorization: Bearer *** header but Telegram Bot API requires token in URL path (`/bot<token>/method`)
  - Fixed `TelegramReporter` to use token in URL path (matching `TelegramClient` behavior)
  - Updated security regression tests to verify token-in-URL behavior
  - Circuit breaker automatically recovers after 60s (HALF_OPEN → CLOSED)
  - Files: `src/chk_a/reporting/telegram_reporter.py`, `tests/test_security_regressions.py`
- [x] **Deployment Infrastructure** — COMPLETED (2026-09-14)
  - Created `scripts/deploy.sh` — Standard deploy script to install synced source from `/home/ipds/Hermes-Prj/chk-a/` to FHS runtime `/opt/chk-a/` on target machine (test/prod)
  - Uses `rsync -c` checksum verification and restarts systemd service
  - Run with `sudo` after dev→test sync
  - Verified hash equality: Dev source `/home/ipds/Hermes-Prj/chk-a/` ↔ Runtime `/opt/chk-a/` (MD5: `b7717b974eab7b7d163300430e2fdf08`)
  - Fixed test VM config `/etc/chk-a/config.yaml` — Added missing `daily_report_*` settings
  - Service running with updated code and config
- [x] **Rotated Log Support & Baseline Integrity Metrics** — COMPLETED (2026-09-15)
  - `_load_recent_checks()` now auto-reads rotated log files (date-stamped `.bz2` and numbered `.gz` backups)
  - Mixed timezone timestamp parsing fixed — handles both naive (real log) and timezone-aware (mock data) ISO8601 timestamps
  - Baseline-based integrity scoring using `MLAgent.score()` (total-variation distance) replacing Isolation Forest
  - Added IP stability & diversity metrics (`unique_ip_count`, `ip_stability`) for baseline method
  - Daily report (yesterday): 10,374 records from rotated log `checks.jsonl-20260914.bz2` → Telegram sent
  - Monthly report (30 days): 53,588 records from multiple rotated files → graphs generated
  - Day 1 sample report (full available data): 53,588 records → Telegram sent with 10 graphs
  - 06:00 AM daily report sample (yesterday's data): uses `reference_date=yesterday 23:59`
  - Real-time daily report (midnight to now): manual run script created
- [x] **Startup Missing Daily Report Check** — COMPLETED (2026-09-15)
  - Orchestrator calls `_send_missing_daily_report()` on startup after task initialization
  - Checks `output_dir` for yesterday's report directory; if missing, generates and sends automatically
  - Uses `reference_date=yesterday 23:59:59` to correctly target yesterday's rotated logs
  - Sends to Telegram with same format as scheduled 06:00 report (Thai, emoji, protected palette, hostname, timestamp)

---

## 🧪 Testing
- [x] **Add unit tests for all agents (target: 80%+ coverage)** — COMPLETED (2026-09-12)
  - `mtr_agent.py`: 27% → 95% (37 tests)
  - `ml_agent.py`: 27% → 92%
  - `baseline_store.py`: 61% → 95% (15 tests)
  - `resolver_agent.py`: 99%
  - `consensus_agent.py`: 96%
  - `alert_agent.py`: 91%
  - Removed orphaned `traceroute_agent.py`
- [x] **Add integration test for full pipeline** — COMPLETED (2026-09-12)
  - Created `tests/test_integration_pipeline.py` (7 tests, 426 lines)
  - All 177 tests pass on both dev and test VM
- [x] **Security regression tests for SEC-001 through SEC-020** — COMPLETED (2026-09-12)
  - Created `tests/test_security_regressions.py` (74 tests, 685 lines)
  - All 251 tests pass on both dev and test VM

---

## 📦 Operational
- [ ] Document systemd unit files in repo (for reference)
- [ ] Add deployment checklist (config perms, systemd caps, log dirs)
- [ ] Create runbook for common operations (add resolver, add FQDN, rotate tokens)

---

## ✅ Completed
- [x] Core 5 agents implemented and wired
- [x] Config system with YAML + env substitution + Pydantic
- [x] Atomic baseline store
- [x] Structured JSONL logging with correlation IDs
- [x] Systemd integration (notify, watchdog, ReadWritePaths)
- [x] Graceful shutdown with baseline persistence
- [x] Monthly report generation (charts, PDF, Telegram, email)
- [x] Daily report generation (charts, Telegram)
- [x] 7 chart types × EN/TH with Thai font support
- [x] Telegram batched sending with exponential backoff
- [x] Daily image at midnight with hostname
- [x] Day separators in logs
- [x] Plain text alert log format
- [x] Alert deduplication (persistent cache)
- [x] Token bucket rate limiting
- [x] HTML alert formatting with Majority/Outliers
- [x] **251/251 tests passing** on both dev and test VM
- [x] All CLI subcommands operational
- [x] Dev↔Test VM sync via rsync -c
- [x] Full security code review (23 findings documented)
- [x] Anomaly/Recovery Telegram notifications with images
- [x] Systemd service status notification feature
- [x] **All Critical/High/Medium Security Findings Fixed** (2026-09-13)
  - C-01, C-02 (Critical - AlertAgent concurrency)
  - H-01 through H-05 (High - timezone, timeouts, caching, memory, batch writes)
  - M-01 through M-08 (Medium - DoH, reputation, key collision, parallel MTR, circuit breaker, health server, Thai font, log rotation)
- [x] **STATUS.md, STATUS-TH.md, PROJECT_CONTEXT.md, PROJECT_CONTEXT-TH.md, TODO.md, CHANGELOG.md updated** (2026-09-15 14:30:00)
- [x] Consensus: majority percentage calculation verified (75% = 1.0 - normalized_entropy, 5/7 resolvers see majority IP)

---

*Last updated: 2026-09-15 14:30:00 (Asia/Bangkok UTC+07)*