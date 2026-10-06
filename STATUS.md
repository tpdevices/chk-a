# chk-a Project Status

**Last Updated:** 2026-10-06 06:15:00 (Asia/Bangkok UTC+07)

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

```plaintext
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

## 3. Completed Work (as of 2026-10-06)

### ✅ Core Features (v1.0.34-v1.0.40)

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
| **Monthly Report: Previous calendar month range** | **v1.0.37** | **✅ Complete** |
| **Overall Average lines on bar charts** | **v1.0.37** | **✅ Complete** |
| **Integrity section in Telegram monthly summary** | **v1.0.37** | **✅ Complete** |
| **Dashboard title: Thai month name** | **v1.0.37** | **✅ Complete** |
| **Footer timestamp: "สร้างเมื่อ" / "Generated at"** | **v1.0.37** | **✅ Complete** |
| **Daily Heatmap: calendar-month window via start_date** | **v1.0.37** | **✅ Complete** |
| **Missing daily report detection for multi-day downtime** | **v1.0.37** | **✅ Complete** |
| **Thai font rendering in PDF reports (TLWG Loma TTF)** | **v1.0.37** | **✅ Complete** |
| **Thai font loading for matplotlib graphs (TLWG Loma)** | **v1.0.37** | **✅ Complete** |
| **_apply_thai_fonts() for all text elements** | **v1.0.37** | **✅ Complete** |
| **PDF graph language separation (EN/TH graphs)** | **v1.0.37** | **✅ Complete** |
| **_send_missing_daily_report() IndexError fix** | **v1.0.38** | **✅ Complete** |
| **Daily heatmap header: month context (YYYY-MM)** | **v1.0.39** | **✅ Complete** |
| **logrotate: daily rotate 365 (keep 1 year logs)** | **v1.0.40** | **✅ Complete** |

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
| Test VM monthly report verification (v1.0.37) | ✅ **Complete** | Source synced, cache cleared, **all 313 tests passing**, report verification done |
| Dashboard Web UI | 📋 Planned | High priority - FastAPI + HTMX + Chart.js |
| Historical data compaction | 📋 Planned | Medium priority - Retention policy for checks.jsonl |
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
| **Daily Heatmap used rolling 30-day window** | **Added `start_date` parameter for calendar-month window** | **v1.0.37** |
| **Test data (r1, fake-resolver) persisted** | **Cleared baseline, FQDN store, checks.jsonl** | **v1.0.37** |
| **Missing daily report for multi-day downtime** | **Added `_find_last_daily_report_date()` and `_generate_daily_report_for_date()`** | **v1.0.37** |
| **Thai font rendering in PDF (TLWG Loma TTF)** | **Use system fonts instead of bundled OTF** | **v1.0.37** |
| **Thai font loading for matplotlib (TLWG Loma TTF)** | **Proper variant separation, bold font file direct** | **v1.0.37** |
| **_apply_thai_fonts() for all text elements** | **Footer, y-axis labels, tick labels, legend, annotations** | **v1.0.37** |
| **PDF graph language separation (EN/TH)** | **English PDF uses EN graphs, Thai PDF uses TH graphs** | **v1.0.37** |
| **_send_missing_daily_report() IndexError on fresh install** | **Added guard clause for empty missed_days list** | **v1.0.38** |
| **Daily heatmap header used generic report context** | **Override with month-specific context (YYYY-MM, Days 1 to N)** | **v1.0.39** |
| **logrotate only kept 14 days of logs** | **Changed rotate 14 → rotate 365 for 1 year retention** | **v1.0.40** |

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
3. **deploy.sh Enhancement** — Auto-copy install.sh, tests/, systemd/
4. **GitHub Actions Optimization** — Cache uv, parallel test matrix

---

## 7. Related Files

### Core Source (src/chk_a/)
```
src/chk_a/
├── __init__.py                    # version 1.0.40
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
logrotate.d/chk-a                  # Logrotate config (daily, rotate 365)
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
| Source (dev) | 1.0.40 | ✅ 313 tests pass |
| GitHub tag | v1.0.40 | ✅ pushed |
| Test VM | 1.0.37 | ✅ Source synced, cache cleared, all 313 tests passing, report verified |
| Production | v1.0.36 | ✅ running on uptime-host |
| GitHub Release | v1.0.40 | ✅ **Created** |

**Next Release:** v1.0.41 (Dashboard Web UI)

---

## 9. Self-Improvement Notes (Skill Updates)

### Skills Improved During This Session:
1. **Thai Font Handling for PDF/Graphs** — Learned to use system TLWG Loma TTF fonts with proper variant registration (Regular, Bold, Oblique, BoldOblique) instead of bundled OTF fonts. Registered fonts with matplotlib font manager for proper rendering.

2. **Matplotlib Thai Font Application** — Improved `_apply_thai_fonts()` to comprehensively apply Thai fonts to ALL text elements: axis labels, tick labels, legend, annotations, figure texts (header, footer), axis offset text. Fixed footer skipping issue (y < 0.05 was previously skipped).

3. **Multi-language Graph Generation** — Implemented proper language-specific graph generation: English PDF uses English graphs (`*.png`), Thai PDF uses Thai graphs (`*-th.png`). Added explicit filtering with logging for verification.

4. **Multi-day Missing Daily Report Detection** — Implemented `_find_last_daily_report_date()` to find most recent report date from existing reports, and `_generate_daily_report_for_date()` to generate reports for each missed day. Handles consecutive missed days (e.g., weekend downtime).

5. **Thai Font Registration for PDF (ReportLab)** — Registered 4 TLWG Loma TTF font variants (Regular, Bold, Oblique, BoldOblique) with pdfmetrics for proper Thai text rendering in PDF reports. All paragraph/table styles now use Thai fonts when `lang="th"`.

6. **Cross-environment Testing** — Validated all 313 tests pass on both Dev (WSL) and Test VM (VirtualBox). Verified PDF graph language separation by extracting embedded images and comparing file sizes.

7. **Production Startup Crash Fix** — Fixed IndexError in `_send_missing_daily_report()` when `last_report_date >= yesterday` (empty missed_days list). Added guard clause with early return and informative logging.

8. **Graph Header Context Customization** — Daily Availability Heatmap now uses month-specific header context (YYYY-MM, Days 1 to N) instead of generic report_date_context. Both Thai and English versions updated.

9. **Logrotate Retention Policy** — Updated logrotate config from rotate 14 to rotate 365 for 1-year log retention while keeping daily rotation.

### Lessons Learned for Future Work:
- **Always verify Thai font rendering at pixel level** — Don't assume font registration works; extract and analyze embedded images.
- **Use system fonts over bundled fonts** — System TLWG Loma TTF fonts work better with both ReportLab and matplotlib than bundled OTF fonts.
- **Register fonts with matplotlib font manager** — Use `fm.fontManager.addfont()` for proper font discovery.
- **Log graph filtering explicitly** — Added explicit logging for graph language filtering to aid debugging.
- **Verify multi-environment test consistency** — Run tests on both Dev and Test VM before releasing.
- **Guard against empty collections before indexing** — Always check `if not list:` before accessing `list[0]` or `list[-1]`.
- **Override context for specific chart types** — Generic context may not suit all charts; allow per-chart context override.
- **Document retention policies in config** — Logrotate and application-level retention should be aligned.

---

*"Self-improvement is the continuous refinement of tools and techniques based on real-world validation, not just theoretical understanding."*