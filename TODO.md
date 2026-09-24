# TODO - chk-a Project

**Last Updated:** 2026-09-24 15:30:00 (Asia/Bangkok UTC+07)

---

## ✅ Completed (v1.0.36)

### Core Features
- [x] Multi-resolver DNS monitoring (DoH/DoT/UDP)
- [x] Consensus with majority voting + outlier detection
- [x] EMA reputation scoring for resolvers
- [x] ML baseline (EMA + entropy scoring)
- [x] Alert Agent: deduplication + token-bucket rate limiting
- [x] Telegram alerts (HTML + 6 graph types)
- [x] Systemd service (Type=notify, WatchdogSec=60)
- [x] MTR integration (ICMP mode, CAP_NET_RAW)

### Security & Quality
- [x] Security regression suite (SEC-001 to SEC-020, 74 tests)
- [x] Zero-regression policy (313/313 tests passing)
- [x] Graph modernization (colorblind-safe palette, 200 DPI, Thai fonts)

### Thai Localization (v1.0.35)
- [x] All Telegram alert headers, severity, types in Thai
- [x] Consensus descriptions (6 levels) in Thai
- [x] Resolver group labels in Thai
- [x] Monthly/Daily report summaries in Thai
- [x] Version footer in Thai

### FQDN-Centric Features (v1.0.36)
- [x] Availability tracking per FQDN per cycle
- [x] Per-FQDN custom alert thresholds (anomaly_threshold, consensus_min_score)
- [x] IP change detection (new AnomalyEvent.type = "ip_change")
- [x] FQDNStore with atomic writes (/var/lib/chk-a/fqdns.json)
- [x] fqdn_store_path in AppConfig

### System Fixes (v1.0.36)
- [x] Systemd shutdown timeout — notify_stopping() in Orchestrator.shutdown()
- [x] CAP_NET_RAW for MTR ICMP in systemd unit

### Repo Cleanup (v1.0.36)
- [x] Removed 33 obsolete files
- [x] Hardened .gitignore (backup, config, script patterns)
- [x] Fixed vulture unused code warnings
- [x] Single master branch (deleted old main)
- [x] Restored img/sleepy.jpg, config/chk-a.env.example

### Deployment
- [x] Test VM verified (313 tests, service running)
- [x] Production (uptime-host) v1.0.36 deployed and verified

---

## 📋 Planned (Priority Order)

### High Priority
- [ ] **Dashboard Web UI** — Real-time monitoring interface
  - [ ] FastAPI backend with async endpoints
  - [ ] HTMX frontend for zero-JS complexity
  - [ ] Chart.js for live graphs
  - [ ] Endpoints: `/api/status`, `/api/fqdns`, `/api/graphs`, `/api/alerts`
  - [ ] Jinja2 templates with Thai locale
  - [ ] Systemd integration (health endpoint already exists)
  - [ ] MVP: 2-3 sessions

### Medium Priority
- [ ] **Historical Data Compaction** — Retention policy for log files
  - [ ] checks.jsonl rotation + compression
  - [ ] alerts.jsonl rotation + compression
  - [ ] Aggregated summaries (hourly/daily) for long-term trends
  - [ ] Configurable retention (default: 90 days raw, 2 years aggregated)
  - [ ] Prevent disk growth on long-running production

### Low Priority
- [ ] **deploy.sh Enhancement**
  - [ ] Auto-copy install.sh to /opt/chk-a/
  - [ ] Auto-sync tests/ directory
  - [ ] Auto-sync systemd/ directory
  - [ ] Idempotent deploy (safe to re-run)

- [ ] **GitHub Actions CI Optimization**
  - [ ] uv cache for faster installs
  - [ ] Parallel test matrix (Python 3.12, 3.13, 3.14)
  - [ ] Release workflow: build wheel, create release, upload assets

- [ ] **Documentation Improvements**
  - [ ] API documentation (OpenAPI from FastAPI)
  - [ ] Architecture decision records (ADRs)
  - [ ] Runbook for common operations

---

## 🔧 Technical Debt / Nice to Have

- [ ] Structured logging improvements (structured context in all log lines)
- [ ] Metrics endpoint (/metrics) for external scraping (if needed later)
- [ ] Resolver health dashboard (per-resolver latency/error rates)
- [ ] Configuration hot-reload (SIGHUP handling)
- [ ] Integration test with real DNS resolvers (CI)
- [ ] Chaos testing (resolver failures, network partitions)

---

## 📝 Notes

**Dev/Test/Production Workflow:**
- Dev only develops (no testing)
- Test only tests (no development)
- Sync: Dev → Test only via `rsync -avz -c` (checksum every file, every time)
- Production: GitHub only (curl install.sh | sudo bash)
- CHANGELOG.md updated on every change (both Dev and Test)

**Hard Rules (from HERMES_RULES.md):**
- No Prometheus / metrics
- No heavy ML dependencies
- md/loop_engineering_prompt.md is authoritative
- Fix tests, not agent code
- Zero-regression (313 tests must pass)
- Thai fonts (Loma/TLWG) for all Thai graphs
- Asia/Bangkok (+07) timestamps
- Hash verification for file identity