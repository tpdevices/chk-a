# TODO — chk-a

**Last Updated:** 2026-09-17 11:15:00 (Asia/Bangkok UTC+07)

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
**Context:** v1.0.2 released with improved pip installation. Need to test on clean VM.
**Steps:** Fresh Ubuntu 24.04 VM → `curl install.sh` → `sudo ./install.sh v1.0.2` → verify service starts
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

### [ ] Dashboard web UI
**Context:** Add simple web dashboard for real-time status, graphs, alerts history.
**Tech:** FastAPI + HTMX + Chart.js (lightweight, no heavy JS framework)
**Files:** New `src/chk_a/dashboard/` module
**Priority:** Low — future enhancement

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
**Details:** Fixed `TelegramReporter` to use token in URL path (`/bot<token>/method`) per Telegram Bot API spec. Was using `Authorization: Bearer` header (404 error).

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
| **Tests** | `tests/test_*.py` (253 tests), `tests/conftest.py` |
| **Logs** | `/var/log/chk-a/checks.jsonl*`, `/var/log/chk-a/alerts.jsonl*`, `/var/log/chk-a/alerts.log` |
| **Baselines** | `/var/lib/chk-a/baselines.json` |
| **Secrets** | `/etc/chk-a/env` |

---

## 🎯 Next Session Priorities

1. **SEC-014** — HTML escape in Telegram messages (Critical)
2. **install.sh venv bug fix** — Add pip verification in existence check (High)
3. **Production install test** — Verify v1.0.2 on clean VM (High)
4. **SEC-010/011** — DoH/DoT support, CAP_NET_RAW for MTR (Medium)

---

*อัปเดตโดย Hermes Agent session วันที่ 2026-09-16 15:30:00*