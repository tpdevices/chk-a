# บริบทโครงการ - chk-a

**อัปเดตล่าสุด:** 2026-09-24 15:30:00 (Asia/Bangkok UTC+07)

---

## สรุปโครงการ

**chk-a** เป็นระบบเฝ้าระวัง DNS A-record แบบ multi-agent เขียนด้วย Python 3.14+ ระบบจะ resolve FQDN รายการต่างๆ ข้าม 22+ public DNS resolvers (DoH, DoT, UDP) คำนวณ consensus พร้อม outlier detection เรียนรู้ ML baseline ด้วย EMA + entropy scoring และส่งการแจ้งเตือน Telegram ที่สมบูรณ์แบบพร้อมภาษาไทยและกราฟ

**Pipeline:** Resolver → Consensus → ML → Alert → Orchestrator (+ MTR traceroute)

---

## เวอร์ชันปัจจุบันและสถานะ Release

| องค์ประกอบ | เวอร์ชัน | สถานะ |
|-----------|---------|--------|
| **Source (dev)** | 1.0.36 | ✅ 313 tests ผ่าน |
| **GitHub tag** | v1.0.36 | ✅ pushed |
| **Test VM** | 1.0.36 | ✅ deployed & verified |
| **Production** | v1.0.36 | ✅ running on uptime-host |

**Next release:** v1.0.37 (หลัง feature cycle ถัดไป)

---

## ฟีเจอร์ที่ทำเสร็จแล้ว

### Core Pipeline (v1.0.1 - v1.0.33)
- ✅ ตรวจสอบ DNS หลาย resolver (DoH/DoT/UDP, 22+ resolvers)
- ✅ Consensus engine พร้อม Majority voting และ Outlier detection
- ✅ EMA reputation scoring สำหรับ resolvers
- ✅ ML baseline learning ด้วย Exponential Moving Average
- ✅ Entropy-based anomaly scoring
- ✅ Token-bucket rate limiting + deduplication (Alert Agent)
- ✅ Telegram HTML alerts พร้อมรูปภาพ (6 ประเภทกราฟ)
- ✅ Systemd service Type=notify, WatchdogSec=60
- ✅ MTR Integration (ICMP mode พร้อม CAP_NET_RAW)
- ✅ Security Regression Suite (SEC-001 ถึง SEC-020, 74 tests)

### Thai Localization (v1.0.35)
- ✅ ทุกส่วนหัว Alert, Severity labels, Type labels เป็นภาษาไทย
- ✅ Consensus descriptions ภาษาไทย (6 ระดับ)
- ✅ Resolver group labels (Majority/Minority/Outliers/Failed) ภาษาไทย
- ✅ Monthly/Daily report summaries ภาษาไทย
- ✅ Version footer ภาษาไทย ในทุกรายงาน

### FQDN-Centric Features (v1.0.36)
- ✅ **Availability tracking** — Availability % ต่อ FQDN ต่อรอบ (successful_resolvers / total * 100)
- ✅ **Custom alert thresholds** — Per-FQDN `anomaly_threshold` และ `consensus_min_score` overrides
- ✅ **IP change detection** — `AnomalyEvent.type = "ip_change"` ใหม่ พร้อม Thai formatting
- ✅ **FQDNStore** — Persistent storage ที่ `/var/lib/chk-a/fqdns.json` พร้อม atomic writes
- ✅ **Config integration** — `fqdn_store_path` ใน AppConfig

### System Fixes (v1.0.36)
- ✅ **Systemd shutdown timeout** — เพิ่ม `notify_stopping()` ใน `Orchestrator.shutdown()` สำหรับ graceful Type=notify shutdown
- ✅ **MTR ICMP capability** — `CapabilityBoundingSet=CAP_NET_RAW` + `AmbientCapabilities=CAP_NET_RAW` ใน systemd unit

### Repo Cleanup (v1.0.36)
- ✅ ลบ obsolete files 33 ไฟล์ (duplicate configs, test scripts, build artifacts, backup files)
- ✅ Hardened `.gitignore` พร้อม `*.backup`, `*.orig`, config/scripts patterns
- ✅ แก้ vulture unused code warnings (2 ไฟล์)
- ✅ Single branch `master` (ลบ `main` เก่าแล้ว)
- ✅ 84 tracked files, working tree clean

---

## สถานะการทดสอบ

- **Total tests:** 313
- **Passing:** 313 (100%)
- **Regression:** Zero
- **Security tests:** 74 (SEC-001 ถึง SEC-020)
- **Environments verified:** Dev (WSL), Test VM (VirtualBox), Production (uptime-host)

---

## สถาปัตยกรรมการ Deploy

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

**Sync Rule:** Dev → Test เท่านั้น (checksum ทุกไฟล์) Test → Dev ห้าม Production ผ่าน GitHub เท่านั้น

---

## ไฟล์ Config สำคัญ

| ไฟล์ | วัตถุประสงค์ |
|------|------------|
| `config/config.yaml.example` | Runtime config template (Thai comments, ทุกตัวเลือก) |
| `config/chk-a.env.example` | Systemd EnvironmentFile template (Telegram creds, paths) |
| `systemd/chk-a.service` | Systemd unit พร้อม CAP_NET_RAW, Type=notify, WatchdogSec |
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

## ข้อจำกัดแน่นอน (Hard Rules)

- ❌ ห้ามใช้ Prometheus / metrics
- ❌ ห้ามใช้ heavy ML dependencies (scikit-learn, torch, etc.)
- ✅ `md/loop_engineering_prompt.md` เป็นเอกสาร authoritative สำหรับ loop behavior
- ✅ แก้ tests, ไม่แก้ agent code (agent code เป็น source of truth)
- ✅ Zero-regression policy (313 tests ต้องผ่านหมด)
- ✅ Thai fonts (Loma/TLWG) สำหรับทุกกราฟไทย
- ✅ Asia/Bangkok (+07) timestamps ทุกที่
- ✅ Hash verification (md5sum/sha256sum) สำหรับยืนยันไฟล์
- ✅ CHANGELOG.md อัปเดตทุกครั้งที่มีการเปลี่ยนแปลง

---

## ขั้นตอนต่อไป (Priority)

1. **Dashboard Web UI** (High) — FastAPI + HTMX + Chart.js, real-time status, FQDN table, graphs
2. **Historical Data Compaction** (Medium) — Retention policy สำหรับ checks.jsonl/alerts.jsonl
3. **deploy.sh Enhancement** (Low) — Auto-copy install.sh, tests/, systemd/
4. **GitHub Actions Optimization** (Low) — uv cache, parallel test matrix