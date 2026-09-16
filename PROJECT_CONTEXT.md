# Project Context — chk-a

**Last Updated:** 2026-09-15 14:30:00 (Asia/Bangkok UTC+07)

---

## Project Overview

**chk-a** is a multi-agent DNS A-record anomaly monitoring system. It continuously queries multiple DNS resolvers for configured FQDNs, builds a weighted consensus, learns baselines via online exponential-decay counters, detects anomalies, and sends formatted alerts via Telegram with comprehensive reporting (daily/monthly, EN/TH, charts + PDF).

**Repository:** `tpdevices/chk-a` (GitHub, HTTPS with PAT)
**Development:** WSL Ubuntu (172.20.14.199/20)
**Test Target:** VirtualBox Ubuntu 24.04 at 192.168.56.122 (user: ipds)
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

---

## Configuration

**Primary:** `/etc/chk-a/config.yaml` (test VM)
**Reference:** `/opt/chk-a/config.example.yaml`

Key Sections:
- `fqdns` — List of FQDNs with `min_consensus` and `expected_ips` (optional)
- `resolvers` — Resolver endpoints (`name`, `address` as `IP:port`, `weight`, `timeout_ms`)
- `ml` — `baseline_decay`, `anomaly_threshold`, `min_samples_before_alert`
- `alert` — Telegram credentials, dedup window, rate limit, log paths, daily image config, dedup cache path
- `scheduler` — `min_interval_sec` (30), `max_interval_sec` (180), `jitter`
- `mtr` — enabled flag, interval, max_hops, count, interval_ms, timeout_sec, mode (icmp/tcp/udp), resolvers list
- `reporting` — Monthly/daily schedules, output dir, Telegram/email config, graph inclusion
- `baseline_store_path` — `/var/lib/chk-a/baselines.json`

**Secrets:** `/etc/chk-a/env` — Stores `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (test VM)

---

## Reporting Details

### Monthly Report (1st of month, 06:00 AM)
- ML insights from 30-day lookback
- 7 chart types × EN/TH = 14 charts + 2 Dashboards = 16 files
- PDF reports (EN/TH) via fpdf2
- Telegram: Thai summary + charts (batched, 5 images per batch)
- Email: Full PDF attachment

### Daily Report (06:00 AM, lookback 1 day)
- Same charts, 1-day time window
- Telegram: Thai summary + charts (batched)

### Chart Types (7)
1. Availability Bar (availability % per resolver)
2. Availability Heatmap (hourly per resolver)
3. Integrity Score (ML-based per resolver)
4. Latency Boxplot (latency distribution per resolver)
5. IP Stability & Diversity (unique IP set, stability %)
6. MTR Path Visualization (hop loss/latency)
7. Path Availability (ML-based network path health)

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

- **251/251 tests pass** on **both dev and test VM** (zero-regression policy)
- **Test Location:** Everything on test VM (pytest, CLI, systemd, DNS/Telegram/MTR)
- **Fix Tests, Not Agent Code** — per project rules
- **Code Review Patterns:** Per skill `software-development` → `code-review-patterns`

---

## Security Status

**Security Code Review Complete:** 23 findings
- **2 Critical:** AlertAgent token bucket race (C-01) ✅ FIXED, AlertAgent dedup cache race (C-02) ✅ FIXED
- **5 High:** Orchestrator timezone-naive scheduler (H-01) ✅ FIXED, MTR timeout calc (H-02) ✅ FIXED, BaselineStore key caching (H-03) ✅ FIXED, TelegramClient memory (H-04) ✅ FIXED, Orchestrator batch writes (H-05) ✅ FIXED
- **8 Medium:** DoH support (M-01) ✅ FIXED, Consensus reputation (M-02) ✅ FIXED, MLAgent key collision (M-03) ✅ FIXED, Parallel MTR (M-04) ✅ FIXED, CircuitBreaker (M-05) ✅ FIXED, Health server consistency (M-06) ✅ FIXED, Thai font loading (M-07) ✅ FIXED, AlertAgent log rotation (M-08) ✅ FIXED
- **5 Low/Info:** SEC-010 (DoH/DoT), SEC-011 (CAP_NET_RAW), SEC-013 (log perms), SEC-014 (HTML escape), SEC-015..SEC-020 ✅ FIXED

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

---

*Created by Hermes Agent session on 2026-09-15 14:30:00*