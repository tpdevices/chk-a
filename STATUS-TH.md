# สถานะโครงการ chk-a

**อัปเดตล่าสุด:** 2026-10-02 15:30:00 (Asia/Bangkok UTC+07)

---

## 1. ภาพรวมโครงการ (Project Overview)

**chk-a** เป็นระบบเฝ้าระวัง DNS A-record แบบ multi-agent ที่ตรวจจับการเปลี่ยนแปลง IP address วิเคราะห์ consensus ข้าม resolver หลายตัว ใช้ ML ตรวจจับ anomaly และส่งการแจ้งเตือนผ่าน Telegram

**องค์ประกอบหลัก:**
- **Resolver Agent** — Query DNS แบบขนานไป 22+ public resolvers (DoH/DoT/UDP)
- **Consensus Agent** — การโหวตแบบ Majority พร้อม Outlier detection, EMA reputation scoring
- **ML Agent** — เรียนรู้ Baseline ด้วย Exponential Moving Average + Entropy scoring
- **Alert Agent** — Deduplication, Rate limiting, การแจ้งเตือนภาษาไทย HTML บน Telegram
- **Orchestrator** — Main loop ควบคุม agent ทั้งหมด, systemd integration, MTR traceroute
- **Reporting** — สร้างกราฟ 6 รูป (ภาษาไทย), รายงาน PDF/Email/Telegram

**สภาพแวดล้อม:**
- Dev: WSL Ubuntu (172.20.14.199/20)
- Test: VirtualBox Ubuntu 24.04 (192.168.56.122)
- Production: uptime-host
- เวลาทั้งหมด: Asia/Bangkok (+07)

---

## 2. สถาปัตยกรรม (Architecture)

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
│  • รอบ 30-180s (jittered)     • ติดตาม availability ต่อ FQDN   • ตรวจจับ IP change    │
│  • Systemd notify (Type=notify) • CAP_NET_RAW สำหรับ MTR ICMP    • รายงาน Daily/Monthly │
│  • WatchdogSec=60             • Baseline persistence           • Health endpoint      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Tech Stack:** Python 3.14, asyncio, aiohttp, aiodns, systemd, uv/pip, pytest

---

## 3. สิ่งที่ทำเสร็จแล้ว (Completed Work - 2026-10-02)

### ✅ ฟีเจอร์หลัก (v1.0.34-v1.0.37)

| ฟีเจอร์ | เวอร์ชัน | สถานะ |
|---------|---------|--------|
| ตรวจสอบ DNS หลาย resolver | v1.0.1 | ✅ เสร็จ |
| Consensus + Outlier detection | v1.0.5 | ✅ เสร็จ |
| ML Baseline (EMA + Entropy) | v1.0.10 | ✅ เสร็จ |
| Telegram Alert (HTML + รูป) | v1.0.15 | ✅ เสร็จ |
| Systemd service + Watchdog | v1.0.20 | ✅ เสร็จ |
| MTR Integration (ICMP mode) | v1.0.30 | ✅ เสร็จ |
| Security Regression Suite (20 tests) | v1.0.33 | ✅ 74 tests ผ่าน |
| กราฟทันสมัย (Colorblind-safe) | v1.0.34 | ✅ เสร็จ |
| Thai Localization (เต็มรูปแบบ) | v1.0.35 | ✅ เสร็จ |
| FQDN-centric Features | v1.0.36 | ✅ เสร็จ |
| - Availability tracking ต่อ FQDN | v1.0.36 | ✅ เสร็จ |
| - Custom alert thresholds ต่อ FQDN | v1.0.36 | ✅ เสร็จ |
| - IP change detection/alert | v1.0.36 | ✅ เสร็จ |
| Systemd shutdown fix (notify_stopping) | v1.0.36 | ✅ เสร็จ |
| CAP_NET_RAW สำหรับ MTR ICMP | v1.0.36 | ✅ เสร็จ |
| GitHub Repo Cleanup (ลบ 33 ไฟล์) | v1.0.36 | ✅ เสร็จ |
| Production Deployment Verified | v1.0.36 | ✅ uptime-host ทำงาน |
| **รายงานประจำเดือน: ช่วงเดือนก่อนหน้าเต็มเดือน** | **v1.0.37** | **✅ เสร็จ** |
| **เส้น Overall Average บนกราฟแท่ง** | **v1.0.37** | **✅ เสร็จ** |
| **ส่วน Integrity ใน Telegram Monthly Summary** | **v1.0.37** | **✅ เสร็จ** |
| **Dashboard title: ชื่อเดือนไทย** | **v1.0.37** | **✅ เสร็จ** |
| **Footer timestamp: "สร้างเมื่อ" / "Generated at"** | **v1.0.37** | **✅ เสร็จ** |
| **Daily Heatmap: calendar-month window ผ่าน start_date** | **v1.0.37** | **✅ เสร็จ (dev)** |

### ✅ การทดสอบ
- **313/313 tests ผ่าน** (Zero regression) บน Dev และ Test VM ทั้งคู่
- Security regression tests: 74 tests ครอบคลุม SEC-001 ถึง SEC-020
- Test VM Deployment verified: service เริ่มทำงานปกติ, ไม่มี systemd timeout
- Production (uptime-host) v1.0.36 Deployed: ส่งรายงาน startup สำเร็จ, ส่งกราฟไทย 6 รูป

### ✅ เอกสารและ Repo Hygiene
- CHANGELOG.md อัปเดตครบทุกเวอร์ชัน
- PROJECT_CONTEXT.md / PROJECT_CONTEXT-TH.md อัปเดต
- GitHub Repo สะอาด: 84 tracked files (ลบ obsolete 33 ไฟล์)
- Default branch: `master` อย่างเดียว (ลบ `main` เก่าแล้ว)
- .gitignore เข็มแข็งขึ้น (backup/config patterns)
- แก้ vulture unused code warnings แล้ว

---

## 4. งานที่กำลังดำเนินการ (In Progress)

|| งาน | สถานะ | หมายเหตุ ||
||------|--------|---------||
|| Test VM monthly report verification (v1.0.37) | ✅ **Complete** | Source synced, cache cleared, **313 tests ผ่านทั้งหมด**, รายงาน verified เสร็จ ||
|| Dashboard Web UI | 📋 วางแผน | Low priority - FastAPI + HTMX + Chart.js ||
|| Historical Data Compaction | 📋 วางแผน | Low priority - Retention policy สำหรับ checks.jsonl ||
|| GitHub Actions CI Optimization | 📋 วางแผน | Release workflow ทำงานอยู่แล้ว ||

---

## 5. ปัญหาที่พบและแก้ไขแล้ว (Issues Found & Resolved)

| ปัญหา | วิธีแก้ | เวอร์ชัน |
|-------|---------|---------|
| Systemd shutdown timeout (90s) | เพิ่ม `notify_stopping()` ใน Orchestrator.shutdown() | v1.0.36 |
| MTR ICMP ต้องการ CAP_NET_RAW | เพิ่มใน systemd service CapabilityBoundingSet | v1.0.36 |
| Thai localization test fail บน Test VM | Sync tests/ directory ผ่าน rsync | v1.0.35 |
| 14 test failures บน Test VM | แก้ permissions, sync tests/, sync systemd/ | v1.0.35 |
| install.sh หายบน Test VM | คัดลอก manual, เพิ่ม TODO ใน deploy.sh | v1.0.35 |
| Backup files (.backup) ถูก commit | ลบ, เพิ่ม *.backup ใน .gitignore | v1.0.36 |
| img/sleepy.jpg ถูกลบ (ใช้สำหรับ midnight heartbeat) | Restore จาก git history | v1.0.36 |
| config/chk-a.env.example ถูกลบ (deploy template) | Restore จาก git history | v1.0.36 |
| Config files ซ้ำ (settings.yaml, etc.) | ลบ, เก็บแค่ config.yaml.example | v1.0.36 |
| **Daily Heatmap ใช้ rolling 30-day window** | **เพิ่ม `start_date` parameter สำหรับ calendar-month window** | **v1.0.37** |
| **Test data (r1, fake-resolver) ค้างอยู่** | **ล้าง baseline, FQDN store, checks.jsonl** | **v1.0.37** |

---

## 6. งานต่อไป (Priority Order)

### High Priority
1. **Complete Test VM monthly report verification** — ตรวจสอบ daily/monthly reports บน Test VM หลัง v1.0.37 sync
2. **Dashboard Web UI** — Real-time status, ตาราง FQDN, Graph viewer, Alert history
   - FastAPI + HTMX + Chart.js + Jinja2
   - Endpoints: /api/status, /api/fqdns, /api/graphs, /api/alerts
   - MVP: 2-3 sessions

### Medium Priority
3. **Historical Data Compaction** — Retention policy สำหรับ checks.jsonl / alerts.jsonl
   - Compress ข้อมูลเก่า, เก็บ aggregated summaries
   - ป้องกัน disk เต็มใน production ที่รันนาน

### Low Priority
4. **deploy.sh Enhancement** — Auto-copy install.sh, tests/, systemd/
5. **GitHub Actions Optimization** — Cache uv, Parallel test matrix

---

## 7. ไฟล์ที่เกี่ยวข้อง (Related Files)

### Core Source (src/chk_a/)
```
src/chk_a/
├── __init__.py                    # version 1.0.37
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
│   ├── graph_generator.py         # 6 กราฟไทย, colorblind-safe palette
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
scripts/deploy.sh                  # Deploy script (ต้อง enhance)
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

### เอกสาร
```
CHANGELOG.md                       # ทุกเวอร์ชัน (Keep a Changelog format)
STATUS.md / STATUS-TH.md           # ไฟล์นี้ (EN/TH)
PROJECT_CONTEXT.md / PROJECT_CONTEXT-TH.md  # Project context (EN/TH)
TODO.md                            # Task list
README.md                          # Project overview
HERMES_RULES.md                    # Development rules
md/loop_engineering_prompt.md      # Authoritative loop spec
```

---

## 8. สถานะเวอร์ชัน (Version Status)

|| องค์ประกอบ | เวอร์ชัน | สถานะ ||
||-----------|---------|--------|
|| Source (dev) | 1.0.37 | ✅ 313 tests ผ่าน ||
|| GitHub tag | v1.0.36 | ✅ pushed ||
|| Test VM | 1.0.37 | ✅ **Source synced, cache cleared, 313 tests ผ่านทั้งหมด, รายงาน verified เสร็จ** ||
|| Production | v1.0.36 | ✅ running on uptime-host ||

**Next Release:** v1.0.37 (หลัง Test VM verification เสร็จ)