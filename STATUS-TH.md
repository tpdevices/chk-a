# สถานะโครงการ chk-a

**อัปเดตล่าสุด:** 2026-10-06 06:15:00 (Asia/Bangkok UTC+07)

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

## 3. สิ่งที่ทำเสร็จแล้ว (Completed Work - 2026-10-06)

### ✅ ฟีเจอร์หลัก (v1.0.34-v1.0.40)

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
| **Daily Heatmap: calendar-month window ผ่าน start_date** | **v1.0.37** | **✅ เสร็จ** |
| **ตรวจจับรายงานรายวันที่หายไปหลายวันติดต่อกัน** | **v1.0.37** | **✅ เสร็จ** |
| **การแสดงผลฟอนต์ไทยใน PDF (TLWG Loma TTF)** | **v1.0.37** | **✅ เสร็จ** |
| **การโหลดฟอนต์ไทยสำหรับ matplotlib (TLWG Loma)** | **v1.0.37** | **✅ เสร็จ** |
| **_apply_thai_fonts() สำหรับทุกข้อความในกราฟ** | **v1.0.37** | **✅ เสร็จ** |
| **การแยกภาษากราฟใน PDF (EN/TH graphs)** | **v1.0.37** | **✅ เสร็จ** |
| **แก้ IndexError ใน _send_missing_daily_report()** | **v1.0.38** | **✅ เสร็จ** |
| **Daily heatmap header: month context (YYYY-MM)** | **v1.0.39** | **✅ เสร็จ** |
| **logrotate: daily rotate 365 (เก็บ log 1 ปี)** | **v1.0.40** | **✅ เสร็จ** |

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

| งาน | สถานะ | หมายเหตุ |
|------|--------|---------|
| Test VM monthly report verification (v1.0.37) | ✅ **Complete** | Source synced, cache cleared, **313 tests ผ่านทั้งหมด**, รายงาน verified เสร็จ |
| Dashboard Web UI | 📋 วางแผน | High priority - FastAPI + HTMX + Chart.js |
| Historical Data Compaction | 📋 วางแผน | Medium priority - Retention policy สำหรับ checks.jsonl |
| GitHub Actions CI Optimization | 📋 วางแผน | Release workflow ทำงานอยู่แล้ว |

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
| **รายงานรายวันที่หายไปหลายวันติดต่อกัน** | **เพิ่ม `_find_last_daily_report_date()` และ `_generate_daily_report_for_date()`** | **v1.0.37** |
| **การแสดงผลฟอนต์ไทยใน PDF (TLWG Loma TTF)** | **ใช้ system fonts แทน bundled OTF** | **v1.0.37** |
| **การโหลดฟอนต์ไทยสำหรับ matplotlib (TLWG Loma)** | **แยก variant ให้ถูกต้อง, bold font file โดยตรง** | **v1.0.37** |
| **_apply_thai_fonts() สำหรับทุกข้อความในกราฟ** | **Footer, y-axis labels, tick labels, legend, annotations** | **v1.0.37** |
| **การแยกภาษากราฟใน PDF (EN/TH graphs)** | **English PDF ใช้ EN graphs, Thai PDF ใช้ TH graphs** | **v1.0.37** |
| **_send_missing_daily_report() IndexError ตอน fresh install** | **เพิ่ม guard clause สำหรับ missed_days ว่างเปล่า** | **v1.0.38** |
| **Daily heatmap header ใช้ generic report context** | **Override ด้วย month-specific header (YYYY-MM, Days 1 to N)** | **v1.0.39** |
| **logrotate เก็บ log แค่ 14 วัน** | **เปลี่ยน rotate 14 → rotate 365 สำหรับเก็บ 1 ปี** | **v1.0.40** |

---

## 6. งานต่อไป (Priority Order)

### High Priority
1. **Dashboard Web UI** — Real-time status, ตาราง FQDN, Graph viewer, Alert history
   - FastAPI + HTMX + Chart.js + Jinja2
   - Endpoints: /api/status, /api/fqdns, /api/graphs, /api/alerts
   - MVP: 2-3 sessions

### Medium Priority
2. **Historical Data Compaction** — Retention policy สำหรับ checks.jsonl / alerts.jsonl
   - Compress ข้อมูลเก่า, เก็บ aggregated summaries
   - ป้องกัน disk เต็มใน production ที่รันนาน

### Low Priority
3. **deploy.sh Enhancement** — Auto-copy install.sh, tests/, systemd/
4. **GitHub Actions Optimization** — Cache uv, Parallel test matrix

---

## 7. ไฟล์ที่เกี่ยวข้อง (Related Files)

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

||| องค์ประกอบ | เวอร์ชัน | สถานะ ||
|||-----------|---------|--------|
||| Source (dev) | 1.0.40 | ✅ 313 tests ผ่าน ||
||| GitHub tag | v1.0.40 | ✅ pushed ||
||| Test VM | 1.0.37 | ✅ **Source synced, cache cleared, 313 tests ผ่านทั้งหมด, รายงาน verified เสร็จ** ||
||| Production | v1.0.36 | ✅ running on uptime-host ||
||| GitHub Release | v1.0.40 | ✅ **Created** ||

**Next Release:** v1.0.41 (Dashboard Web UI)

---

## 9. บันทึกการปรับปรุงทักษะ (Self-Improvement Notes)

### ทักษะที่พัฒนาขึ้นใน Session นี้:
1. **การจัดการฟอนต์ไทยสำหรับ PDF/Graphs** — เรียนรู้การใช้ system TLWG Loma TTF fonts พร้อมการลงทะเบียน variant ให้ถูกต้อง (Regular, Bold, Oblique, BoldOblique) แทน bundled OTF fonts ลงทะเบียนฟอนต์กับ matplotlib font manager เพื่อการแสดงผลที่ถูกต้อง

2. **การใช้ฟอนต์ไทยใน Matplotlib** — ปรับปรุง `_apply_thai_fonts()` ให้ครอบคลุม **ทุก text elements**: axis labels, tick labels, legend, annotations, figure texts (header, footer), axis offset text แก้ไขปัญหา footer ถูก skip (y < 0.05 ถูก skip เดิม)

3. **การสร้างกราฟหลายภาษา** — นำไปใช้การสร้างกราฟเฉพาะภาษา: English PDF ใช้ English graphs (`*.png`), Thai PDF ใช้ Thai graphs (`*-th.png`) เพิ่มการ filter พร้อม logging เพื่อการตรวจสอบ

4. **การตรวจจับรายงานรายวันที่หายไปหลายวันติดต่อกัน** — นำ `_find_last_daily_report_date()` ไปใช้หาวันที่รายงานล่าสุดจากรายงานที่มีอยู่ และ `_generate_daily_report_for_date()` สร้างรายงานสำหรับแต่ละวันที่หายไป จัดการวันหายติดต่อกันได้ (เช่น weekend downtime)

5. **การลงทะเบียนฟอนต์ไทยสำหรับ PDF (ReportLab)** — ลงทะเบียน 4 TLWG Loma TTF font variants (Regular, Bold, Oblique, BoldOblique) กับ pdfmetrics สำหรับการแสดงผลภาษาไทยที่ถูกต้องใน PDF reports ทุก paragraph/table styles ใช้ Thai fonts เมื่อ `lang="th"`

6. **การทดสอบข้ามสภาพแวดล้อม** — ยืนยัน 313 tests ผ่านทั้ง Dev (WSL) และ Test VM (VirtualBox) ยืนยัน PDF graph language separation โดย extract embedded images และเปรียบเทียบขนาดไฟล์

7. **แก้ Production Startup Crash** — แก้ IndexError ใน `_send_missing_daily_report()` เมื่อ `last_report_date >= yesterday` (missed_days ว่างเปล่า) เพิ่ม guard clause พร้อม early return และ logging ที่ให้ข้อมูล

8. **การปรับแต่ง Graph Header Context** — Daily Availability Heatmap ใช้ month-specific header context (YYYY-MM, Days 1 to N) แทน generic report_date_context ทั้งเวอร์ชันไทยและอังกฤษ

9. **Logrotate Retention Policy** — อัปเดต logrotate config จาก rotate 14 เป็น rotate 365 สำหรับเก็บ log 1 ปี พร้อม daily rotation

### บทเรียนสำหรับงานอนาคต:
- **ตรวจสอบการแสดงผลฟอนต์ไทยที่ระดับพิกเซล** — อย่าสมมติว่าการลงทะเบียนฟอนต์ทำงาน; ให้ extract และวิเคราะห์ embedded images
- **ใช้ system fonts แทน bundled fonts** — System TLWG Loma TTF fonts ทำงานได้ดีกว่ากับ ReportLab และ matplotlib เทียบกับ bundled OTF fonts
- **ลงทะเบียนฟอนต์กับ matplotlib font manager** — ใช้ `fm.fontManager.addfont()` สำหรับ font discovery ที่ถูกต้อง
- **Log graph filtering ให้ชัดเจน** — เพิ่ม explicit logging สำหรับ graph language filtering เพื่อช่วย debugging
- **ตรวจสอบความสอดคล้องของการทดสอบข้ามสภาพแวดล้อม** — รัน tests บน Dev และ Test VM ทั้งสองก่อน release
- **Guard against empty collections before indexing** — ต้องเช็ค `if not list:` ก่อนเข้าถึง `list[0]` หรือ `list[-1]` เสมอ
- **Override context สำหรับ chart type เฉพาะ** — Generic context อาจไม่เหมาะกับทุก chart; ควรให้ override context ต่อ chart ได้
- **Document retention policies ใน config** — Logrotate และ application-level retention ควรสอดคล้องกัน

---

*"Self-improvement is the continuous refinement of tools and techniques based on real-world validation, not just theoretical understanding."*