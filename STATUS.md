# chk-a Project Status

**Last Updated:** 2026-09-24 15:30:00 (Asia/Bangkok UTC+07)

---

## 1. Project Overview

**chk-a** is a multi-agent DNS A-record monitoring system that detects IP address changes, performs consensus analysis across multiple resolvers, applies ML-based anomaly detection, and sends alerts via Telegram.

**Key Components:**
- **Resolver Agent** — Parallel DNS queries to 22+ public resolvers (DoH/DoT/UDP)
- **Consensus Agent** — Majority voting with outlier detection, EMA reputation scoring
- **ML Agent** — Baseline learning with Exponential Moving Average + entropy scoring
- **Alert Agent** — Deduplication, rate limiting, Thai-formatted HTML Telegram alerts
- **Orchestrator** — Main loop coordinating all agents, systemd integration, MTR traceroute
- **Reporting** — Graph generation (6 Thai graphs), PDF/Email/Telegram reports

**Environment:**
- Dev: WSL Ubuntu (172.20.14.199/20)
- Test: VirtualBox Ubuntu 24.04 (192.168.56.122)
- Production: uptime-host
- All timestamps: Asia/Bangkok (+07)

---

## 2. Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────┐     ┌──────────┐     ┌──────────────┐
│  Resolver   │────▶│  Consensus   │────▶│   ML    │────▶│  Alert   │────▶│  Telegram    │
│   Agent     │     │   Agent      │     │  Agent  │     │  Agent   │     │  Reporter    │
└─────────────┘     └──────────────┘     └─────────┘     └──────────┘     └──────────────┘
       │                   │                   │                  │                 │
       ▼                   ▼                   ▼                  ▼                 ▼
  22+ resolvers      Majority vote      EMA baseline      Dedup + Rate       Graphs + Alerts
  (DoH/DoT/UDP)      Outlier detect     Entropy scoring   limit (token        (HTML + Images)
                                             bucket)
                                                     
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR (Main Loop)                                 │
│  • 30-180s jittered interval    • FQDN availability tracking    • IP change detection │
│  • Systemd notify (Type=notify) • CAP_NET_RAW for MTR ICMP      • Daily/Monthly reports│
│  • WatchdogSec=60               • Baseline persistence          • Health endpoint      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Tech Stack:** Python 3.14, asyncio, aiohttp, aiodns, systemd, uv/pip, pytest

---

## 3. Completed Work (as of 2026-09-24)

### ✅ Core Features (v1.0.34-v1.0.36)

| Feature | Version | Status |
|---------|---------|--------|
| Multi-resolver DNS monitoring | v1.0.1 | ✅ Complete |
| Consensus with outlier detection | v1.0.5 | ✅ Complete |
| ML baseline (EMA + entropy) | v1.0.10 | ✅ Complete |
| Telegram alerts (HTML + images) | v1.0.15 | ✅ Complete |
| Systemd service with watchdog | v1.0.20 | ✅ Complete |
| MTR integration (ICMP mode) | v1.0.30 | ✅ Complete |
| Security regression suite (20 tests) | v1.0.33 | ✅ 74 tests passing |
| Graph modernization (colorblind-safe) | v1.0.34 | ✅ Complete |
| Thai localization (all alerts/reports) | v1.0.35 | ✅ Complete |
| FQDN-centric features | v1.0.36 | ✅ Complete |
| - Availability tracking per FQDN | v1.0.36 | ✅ Complete |
| - Per-FQDN custom alert thresholds | v1.0.36 | ✅ Complete |
| - IP change detection/alert | v1.0.36 | ✅ Complete |
| Systemd shutdown fix (notify_stopping) | v1.0.36 | ✅ Complete |
| CAP_NET_RAW for MTR ICMP | v1.0.36 | ✅ Complete |
| GitHub repo cleanup (33 files removed) | v1.0.36 | ✅ Complete |
| Production deployment verified | v1.0.36 | ✅ uptime-host running |

### ✅ Testing
- **313/313 tests passing** (zero regression) on both Dev and Test VM
- Security regression tests: 74 tests covering SEC-001 through SEC-020
- Test VM deployment verified: service starts cleanly, no systemd timeout
- Production (uptime-host) v1.0.36 deployed: startup reports sent, 6 Thai graphs delivered

### ✅ Documentation & Repo Hygiene
- CHANGELOG.md updated with all versions
- PROJECT_CONTEXT.md / PROJECT_CONTEXT-TH.md updated
- GitHub repo cleaned: 84 tracked files (removed 33 obsolete files)
- Default branch: `master` only (old `main` deleted)
- .gitignore hardened with backup/config patterns
- vulture unused code warnings fixed

---

## 4. In Progress

| Task | Status | Notes |
|------|--------|-------|
| Dashboard Web UI | 📋 Planned | Low priority - FastAPI + HTMX + Chart.js |
| Historical data compaction | 📋 Planned | Low priority - Retention policy for checks.jsonl |
| GitHub Actions CI optimization | 📋 Planned | Release workflow working |

---

## 5. Issues Found & Resolved

| Issue | Resolution | Version |
|-------|------------|---------|
| Systemd shutdown timeout (90s) | Added `notify_stopping()` in Orchestrator.shutdown() | v1.0.36 |
| MTR ICMP requires CAP_NET_RAW | Added to systemd service CapabilityBoundingSet | v1.0.36 |
| Thai localization test failures on Test VM | Synced tests/ directory via rsync | v1.0.35 |
| 14 test failures on Test VM (permissions, Thai, consensus) | Fixed permissions, synced tests/, synced systemd/ | v1.0.35 |
| Missing install.sh on Test VM | Copied manually, added to deploy.sh TODO | v1.0.35 |
| Backup files committed (.backup) | Removed, added *.backup to .gitignore | v1.0.36 |
| img/sleepy.jpg deleted (used for midnight heartbeat) | Restored from git history | v1.0.36 |
| config/chk-a.env.example deleted (deploy template) | Restored from git history | v1.0.36 |
| Duplicate config files (settings.yaml, etc.) | Removed, kept only config.yaml.example | v1.0.36 |

---

## 6. Next Work Items (Priority Order)

### High Priority
1. **Dashboard Web UI** — Real-time status, FQDN table, graph viewer, alert history
   - FastAPI + HTMX + Chart.js + Jinja2
   - Endpoints: /api/status, /api/fqdns, /api/graphs, /api/alerts
   - MVP: 2-3 sessions

### Medium Priority
2. **Historical Data Compaction** — Retention policy for checks.jsonl / alerts.jsonl
   - Compress old data, keep aggregated summaries
   - Prevent disk growth on long-running production

### Low Priority
3. **deploy.sh enhancement** — Auto-copy install.sh, tests/, systemd/
4. **GitHub Actions optimization** — Cache uv, parallel test matrix

---

## 7. Related Files

### Core Source (src/chk_a/)
```
src/chk_a/
├── __init__.py                    # version 1.0.36
├── main.py                        # CLI entry, cmd_test_daily_image
├── orchestrator.py                # Main loop, systemd notify, daily tasks
├── agents/
│   ├── alert_agent.py             # AlertAgent, Thai formatting, dedup, rate limit
│   ├── consensus_agent.py         # ConsensusAgent, EMA reputation
│   ├── ml_agent.py                # MLAgent, EMA baseline, entropy
│   ├── mtr_agent.py               # MTRAgent, ICMP mode (CAP_NET_RAW)
│   └── resolver_agent.py          # ResolverAgent, DoH/DoT/UDP
├── config/loader.py               # AppConfig, FQDNConfig, fqdn_store_path
├── models/schemas.py              # AnomalyEvent, FQDNConfig, AlertConfig
├── reporting/
│   ├── graph_generator.py         # 6 Thai graphs, colorblind-safe palette
│   ├── telegram_reporter.py       # TelegramClient, daily/monthly reports
│   ├── monthly_report.py          # Monthly PDF/Telegram generation
│   ├── pdf_generator.py           # PDF reports (TH/EN)
│   └── email_sender.py            # SMTP email reports
├── storage/
│   ├── baseline_store.py          # JSONL baseline persistence
│   └── fqdn_store.py              # FQDNStore, availability tracking
└── utils/
    ├── systemd_notify.py          # notify_ready, notify_watchdog, notify_stopping
    ├── logger.py                  # Structured JSON logging
    └── telegram_client.py         # Async Telegram Bot API client
```

### Config & Deploy
```
config/config.yaml.example         # Runtime config template (Thai comments)
config/chk-a.env.example           # Systemd EnvironmentFile template
systemd/chk-a.service              # Systemd unit (Type=notify, CAP_NET_RAW)
scripts/deploy.sh                  # Deploy script (needs enhancement)
scripts/systemd_wrapper.py         # Systemd notify wrapper
install.sh                         # Production installer
uninstall.sh                       # Clean uninstall
```

### Tests (313 tests)
```
tests/
├── conftest.py                    # _make_temp_path, CHK_A_FQDN_DIR
├── test_alert_agent.py            # 16 tests - Thai alerts, dedup, rate limit
├── test_orchestrator.py           # Orchestrator loop, FQDN processing
├── test_consensus_agent.py        # Consensus voting, reputation
├── test_resolver_agent.py         # DNS resolution, DoH
├── test_ml_agent.py               # EMA baseline, entropy
├── test_mtr_agent.py              # MTR ICMP, CAP_NET_RAW
├── test_fqdn_store.py             # FQDN availability, IP change
├── test_integration_pipeline.py   # End-to-end pipeline
├── test_loop7.py                  # CLI commands, validate_config
├── test_deployment.py             # Config validation, deploy checks
├── test_reporting.py              # Graphs, Telegram, PDF
├── test_security_regressions.py   # 74 tests - SEC-001 to SEC-020
└── ... (baseline_store, config_loader, models, email_sender)
```

### Documentation
```
CHANGELOG.md                       # All versions (Keep a Changelog format)
STATUS.md / STATUS-TH.md           # This file (EN/TH)
PROJECT_CONTEXT.md / PROJECT_CONTEXT-TH.md  # Project context (EN/TH)
TODO.md                            # Task list
README.md                          # Project overview
HERMES_RULES.md                    # Development rules
md/loop_engineering_prompt.md      # Authoritative loop spec
```

---

## 8. Version Status

| Component | Version | Status |
|-----------|---------|--------|
| Source (dev) | 1.0.36 | ✅ 313 tests pass |
| GitHub tag | v1.0.36 | ✅ pushed |
| Test VM | 1.0.36 | ✅ deployed & verified |
| Production | v1.0.36 | ✅ running on uptime-host |

**Next Release:** v1.0.37 (after next feature cycle)