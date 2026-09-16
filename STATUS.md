# Project Status — chk-a

**Last Updated:** 2026-09-15 14:30:00 (Asia/Bangkok UTC+07)

---

## 1. Project Overview

**chk-a** is a multi-agent DNS A-record anomaly monitoring system. It continuously queries multiple DNS resolvers for configured FQDNs, builds a weighted consensus, learns baselines via online exponential-decay counters, detects anomalies, and sends formatted alerts via Telegram with comprehensive reporting (daily/monthly, EN/TH, charts + PDF).

**Repository:** `tpdevices/chk-a` (GitHub, HTTPS with PAT)
**Development:** WSL Ubuntu (172.20.14.199/20)
**Test Target:** VirtualBox Ubuntu 24.04 at 192.168.56.122 (user: ipds)
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
- ✅ Daily report (06:00 AM, lookback 1 day) — **FIXED: Telegram 404 error**
- ✅ 7 chart types × 2 languages (EN/TH) = 14 charts + 2 Dashboards = 16 files
  - Availability Bar, Availability Heatmap, Integrity Score, Latency Boxplot, IP Stability, MTR Path, Path Availability
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
- ✅ **251/251 tests pass** on **both dev and test VM** (zero-regression policy)
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

### **NEW: Rotated Log Support & Baseline Integrity Metrics (2026-09-15)**
- ✅ **`_load_recent_checks()` auto-reads rotated logs** — date-stamped `.bz2` and numbered `.gz` backups from log directory
- ✅ **Mixed timezone timestamp parsing fixed** — handles both naive (real log) and timezone-aware (mock data) ISO8601 timestamps via `pd.to_datetime(format="mixed", utc=True).dt.tz_localize(None)`
- ✅ **Baseline-based integrity scoring** — uses `MLAgent.score()` (total-variation distance against learned baseline) replacing Isolation Forest
- ✅ **IP stability & diversity metrics added** — `unique_ip_count` and `ip_stability` computed for baseline method (was missing, only in Isolation Forest)
- ✅ **Daily report (yesterday)** — 10,374 records from rotated log `checks.jsonl-20260914.bz2` → Telegram sent successfully
- ✅ **Monthly report (30 days)** — 53,588 records from multiple rotated files → graphs generated successfully
- ✅ **Day 1 sample report (full available data)** — 53,588 records → Telegram sent with 10 graphs
- ✅ **06:00 AM daily report sample (yesterday's data)** — uses `reference_date=yesterday 23:59` → correct yesterday data loaded
- ✅ **Real-time daily report (midnight to now)** — manual run script created, filters to today's data from current log

### **NEW: Startup Missing Daily Report Check (2026-09-15)**
- ✅ **Orchestrator checks for missing yesterday's report on startup** — `_send_missing_daily_report()` called after task initialization
- ✅ Checks `output_dir` for yesterday's report directory; if missing, generates and sends automatically
- ✅ Uses `reference_date=yesterday 23:59:59` to correctly target yesterday's rotated logs
- ✅ Sends to Telegram with same format as scheduled 06:00 report (Thai, emoji, protected palette, hostname, timestamp)

---

## 4. In Progress

- 🔄 **P2 Security Remediation** (Medium findings — next sprint):
  - SEC-010: Implement DoH/DoT support in ResolverAgent
  - SEC-011: Verify MTR `CAP_NET_RAW` in systemd unit
  - SEC-013: Log file permissions
  - SEC-014: HTML escape in Telegram messages

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

---

## 6. Next Actions

### This Week (P1)
- Document systemd unit files in repo (reference)
- Add deployment checklist (config perms, systemd caps, log dirs)
- Create runbook for common operations

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
| `src/chk_a/reporting/graph_generator.py` | ~850 | 7 chart types × EN/TH, Thai fonts, translation map |
| `src/chk_a/reporting/monthly_report.py` | ~350 | Report pipeline: insights → graphs → PDF → Telegram/email |
| `src/chk_a/reporting/telegram_reporter.py` | ~400 | Batched photo sending, exponential backoff, HTML summary |
| `src/chk_a/reporting/pdf_generator.py` | ~200 | fpdf2 EN/TH templates |
| `src/chk_a/reporting/ml_insights.py` | ~250 | Availability, integrity, path health, anomaly detection |

### Entry Point & Config
| File | Purpose |
|------|---------|
| `src/chk_a/main.py` | CLI + daemon entry, subcommands |
| `systemd/chk-a.service` | Modified: ExecStartPre/ExecStop use systemd_wrapper.py for status notifications |
| `/etc/chk-a/config.yaml` | Production config (test VM) |
| `/opt/chk-a/config.example.yaml` | Config reference |
| `/etc/chk-a/env` | **Telegram credentials** (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) |

### Scripts
| File | Purpose |
|------|---------|
| `scripts/systemd_wrapper.py` | Systemd service wrapper — detects restarts, sends start/restart/stop/fail notifications |
| `scripts/systemd_notify.py` | Direct systemd status notifier — start/stop/restart/fail/error |
| `scripts/send_test_telegram.py` | Sends test anomaly/recovery Telegram messages with images |
| `scripts/deploy.sh` | **NEW (2026-09-14)** Deploy synced source to FHS runtime `/opt/chk-a/` |

### Test & Scripts
| File | Purpose |
|------|---------|
| `tests/test_alert_agent.py` | Alert agent tests (updated for `send_photo` signature) |
| `tests/conftest.py` | Session-wide test config (`CHK_A_BASELINE_DIR=/tmp`) |
| `tests/test_integration_pipeline.py` | Full pipeline integration tests (7 tests) |
| `tests/test_security_regressions.py` | Security regression tests (74 tests, SEC-001 to SEC-020) |

---

## 8. TODO List

See [TODO.md](TODO.md) for detailed breakdown.

---

*Generated by Hermes Agent session on 2026-09-15 14:30:00*