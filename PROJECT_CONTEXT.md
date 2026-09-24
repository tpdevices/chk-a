# Project Context - chk-a

**Last Updated:** 2026-09-24 15:30:00 (Asia/Bangkok UTC+07)

---

## Project Summary

**chk-a** is a multi-agent DNS A-record monitoring system written in Python 3.14+. It continuously resolves a list of FQDNs across 22+ public DNS resolvers (DoH, DoT, UDP), computes consensus with outlier detection, maintains ML baselines using EMA + entropy scoring, and sends rich Telegram alerts with Thai localization and graphs.

**Pipeline:** Resolver → Consensus → ML → Alert → Orchestrator (+ MTR traceroute)

---

## Current Version & Release State

| Component | Version | Status |
|-----------|---------|--------|
| **Source (dev)** | 1.0.36 | ✅ 313 tests pass |
| **GitHub tag** | v1.0.36 | ✅ pushed |
| **Test VM** | 1.0.36 | ✅ deployed & verified |
| **Production** | v1.0.36 | ✅ running on uptime-host |

**Next release:** v1.0.37 (after next feature cycle)

---

## Completed Features

### Core Pipeline (v1.0.1 - v1.0.33)
- ✅ Multi-resolver DNS monitoring (DoH/DoT/UDP, 22+ resolvers)
- ✅ Consensus engine with majority voting and outlier detection
- ✅ EMA reputation scoring for resolvers
- ✅ ML baseline learning with Exponential Moving Average
- ✅ Entropy-based anomaly scoring
- ✅ Token-bucket rate limiting + deduplication (Alert Agent)
- ✅ Telegram HTML alerts with images (6 graph types)
- ✅ Systemd service with Type=notify, WatchdogSec=60
- ✅ MTR integration (ICMP mode with CAP_NET_RAW)
- ✅ Security regression suite (SEC-001 to SEC-020, 74 tests)

### Thai Localization (v1.0.35)
- ✅ All Telegram alert headers, severity labels, type labels in Thai
- ✅ Consensus descriptions in Thai (6 levels)
- ✅ Resolver group labels (Majority/Minority/Outliers/Failed) in Thai
- ✅ Monthly/Daily report summaries in Thai
- ✅ Version footer in Thai on all reports

### FQDN-Centric Features (v1.0.36)
- ✅ **Availability tracking** — Per-FQDN availability % per cycle (successful_resolvers / total * 100)
- ✅ **Custom alert thresholds** — Per-FQDN `anomaly_threshold` and `consensus_min_score` overrides
- ✅ **IP change detection** — New `AnomalyEvent.type = "ip_change"` with Thai formatting
- ✅ **FQDNStore** — Persistent storage at `/var/lib/chk-a/fqdns.json` with atomic writes
- ✅ **Config integration** — `fqdn_store_path` in AppConfig

### System Fixes (v1.0.36)
- ✅ **Systemd shutdown timeout** — Added `notify_stopping()` in `Orchestrator.shutdown()` for graceful Type=notify shutdown
- ✅ **MTR ICMP capability** — `CapabilityBoundingSet=CAP_NET_RAW` + `AmbientCapabilities=CAP_NET_RAW` in systemd unit

### Repo Cleanup (v1.0.36)
- ✅ Removed 33 obsolete files (duplicate configs, test scripts, build artifacts, backup files)
- ✅ Hardened `.gitignore` with `*.backup`, `*.orig`, config/scripts patterns
- ✅ Fixed vulture unused code warnings (2 files)
- ✅ Single branch `master` (deleted old `main`)
- ✅ 84 tracked files, clean working tree

---

## Test Status

- **Total tests:** 313
- **Passing:** 313 (100%)
- **Regression:** Zero
- **Security tests:** 74 (SEC-001 to SEC-020)
- **Environments verified:** Dev (WSL), Test VM (VirtualBox), Production (uptime-host)

---

## Deployment Architecture

```
Dev (WSL Ubuntu)          Test VM (VirtualBox)        Production (uptime-host)
172.20.14.199              192.168.56.122              (direct GitHub deploy)
     │                          │                          │
     │  rsync -avz -c           │                          │
     ├──── source ─────────────▶│                          │
     │                          │                          │
     │                          │  sudo ./scripts/deploy.sh│
     │                          ├───▶ /opt/chk-a/          │
     │                          │      systemd service      │
     │                          │                          │
     │                          │                          │  curl install.sh | sudo bash
     │                          │                          ├───▶ /opt/chk-a/
     │                          │                          │      systemd service
     │                          │                          │
Secrets:                     Secrets:                    Secrets:
(none)                       /etc/chk-a/env              /etc/chk-a/env
                             TELEGRAM_BOT_TOKEN          TELEGRAM_BOT_TOKEN
                             TELEGRAM_CHAT_ID            TELEGRAM_CHAT_ID
```

**Sync Rule:** Dev → Test only (checksum every file). Test → Dev forbidden. Production via GitHub only.

---

## Key Configuration Files

| File | Purpose |
|------|---------|
| `config/config.yaml.example` | Runtime config template (Thai comments, all options) |
| `config/chk-a.env.example` | Systemd EnvironmentFile template (Telegram creds, paths) |
| `systemd/chk-a.service` | Systemd unit with CAP_NET_RAW, Type=notify, WatchdogSec |
| `pyproject.toml` | Project metadata, dependencies, version (1.0.36) |

---

## Data Paths (Production/Test)

| Data | Path |
|------|------|
| FQDN Store | `/var/lib/chk-a/fqdns.json` |
| Baseline Store | `/var/lib/chk-a/baselines.json` |
| Check Logs | `/var/log/chk-a/checks.jsonl` |
| Alert Logs (JSONL) | `/var/log/chk-a/alerts.jsonl` |
| Alert Logs (Text) | `/var/log/chk-a/alerts.log` |
| Audit Logs | `/var/log/chk-a/audit.log` |
| Reports/Graphs | `/var/lib/chk-a/reports/` |
| Daily Image | `img/sleepy.jpg` (midnight heartbeat) |
| Anomaly Image | `img/priority.jpg` |
| Recovery Image | `img/ok.jpg` |

---

## Known Constraints (Hard Rules)

- ❌ No Prometheus / metrics
- ❌ No heavy ML dependencies (scikit-learn, torch, etc.)
- ✅ `md/loop_engineering_prompt.md` is authoritative for loop behavior
- ✅ Fix tests, not agent code (agent code is source of truth)
- ✅ Zero-regression policy (all 313 tests must pass)
- ✅ Thai fonts (Loma/TLWG) for all Thai graph elements
- ✅ Asia/Bangkok (+07) timestamps everywhere
- ✅ Hash verification (md5sum/sha256sum) for file identity
- ✅ CHANGELOG.md updated on every change

---

## Next Steps (Priority)

1. **Dashboard Web UI** (High) — FastAPI + HTMX + Chart.js, real-time status, FQDN table, graphs
2. **Historical Data Compaction** (Medium) — Retention policy for checks.jsonl/alerts.jsonl
3. **deploy.sh Enhancement** (Low) — Auto-copy install.sh, tests/, systemd/
4. **GitHub Actions Optimization** (Low) — uv cache, parallel test matrix