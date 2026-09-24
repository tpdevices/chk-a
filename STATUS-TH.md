# สถานะโครงการ chk-a

**อัปเดตล่าสุด:** 2026-09-23 11:45:00 (Asia/Bangkok UTC+07)

---

## 1. ภาพรวมโครงการ

**chk-a** เป็นระบบตรวจสอบความผิดปกติของ DNS A-record แบบ Multi-Agent เขียนด้วย Python ระบบจะสอบถาม DNS resolver หลายตัวพร้อมกันสำหรับ FQDN ที่กำหนด สร้างคะแนนเสียงถ่วงน้ำหนัก (Weighted Consensus) เรียนรู้ Baseline แบบ Online Exponential Decay ตรวจจับ Anomaly และส่ง Alert ผ่าน Telegram พร้อมรายงานรายวัน/รายเดือน (ภาษาไทย/อังกฤษ + กราฟ + PDF)

**ที่เก็บโค้ด:** `tpdevices/chk-a` (GitHub, HTTPS with PAT)  
**พัฒนา:** WSL Ubuntu (172.20.14.199/20)  
**เครื่องทดสอบ:** VirtualBox Ubuntu 24.04 ที่ 192.168.56.122 (user: ipds)  
**เครื่อง Production:** `uptime-host` (internal DNS monitoring)  
**Service User:** `chk-a` (uid=999)  
**Python:** 3.14.4 (`python3`, PEP 668 → venv/uv)  
**Timestamp ทั้งหมด:** เวลาท้องถิ่น Asia/Bangkok (+07), รูปแบบ `YYYY-MM-DD HH:MM:SS`

---

## 2. สถาปัตยกรรม

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

**Systemd Services (4 ตัว):**
- `chk-a-resolver` — ResolverAgent
- `chk-a-consensus` — ConsensusAgent + MLAgent
- `chk-a-alert` — AlertAgent + Orchestrator
- `chk-a-mtr` — MTRAgent

**การแจ้งสถานะ Service (2026-09-12):**
- `scripts/systemd_wrapper.py` — Wrapper สคริปต์ที่เรียกผ่าน ExecStartPre (start) และ ExecStop (stop)
- `scripts/systemd_notify.py` — Notifier ตรงสำหรับ start/stop/restart/fail/error
- ติดตามสถานะผ่าน `/opt/chk-a/last_state.txt` (แยกแยะ restart กับการเริ่มต้นใหม่)
- Telegram emojis: 🟢 start, 🔄 restart, 🔴 stop, ❌ fail, ⚠️ error
- บูรณาการใน `systemd/chk-a.service` ผ่าน ExecStartPre และ ExecStop

---

## 3. สิ่งที่ทำเสร็จแล้ว

### ระบบหลัก (Core System)
- ✅ Agent ทั้ง 5 ตัวทำงานและเชื่อมผ่าน `Orchestrator` แล้ว
- ✅ ระบบ Config: YAML + `${ENV}` substitution, Pydantic validation, auto-tuned `max_concurrent`
- ✅ Baseline Store ทำงานแบบ Atomic persistence (`os.replace` + `fsync`)
- ✅ Structured JSONL Logging พร้อม Correlation ID
- ✅ Systemd Integration (Type=notify, WatchdogSec, ReadWritePaths สำหรับ dedup cache)
- ✅ Graceful Shutdown (SIGTERM/SIGINT) พร้อมการคงค่า baseline

### รายงาน (Loop 7 — Reporting)
- ✅ รายงานรายเดือน (วันที่ 1 ทุกเดือน, 06:00 น.)
- ✅ รายงานรายวัน (06:00 น., lookback 1 วัน) — **แก้แล้ว: Telegram 404 error + time range bug**
- ✅ กราฟ 7 ประเภท × 2 ภาษา (EN/TH) = 14 กราฟ + 2 Dashboards = 16 ไฟล์
  - Availability Bar, Availability Heatmap, Integrity Score, Latency Boxplot, IP Stability, MTR Path, Path Availability
- ✅ **ใหม่: Daily Availability Heatmap** — Heatmap แบบวันในเดือน vs resolver สำหรับรายงานรายเดือน (2026-09-17)
- ✅ รองรับภาษาไทยผ่าน `_apply_thai_fonts()` พร้อม translation map ครอบคลุมทุกประเภทกราฟ
- ✅ รายงาน PDF (EN/TH) ผ่าน fpdf2
- ✅ Telegram batch sending (ปรับ batch size, delay, exponential backoff retry ได้)
- ✅ ส่งอีเมล (SMTP พร้อม TLS)

### การเชื่อมต่อ Telegram
- ✅ รูปภาพรายวันตอนเที่ยงคืน พร้อม hostname ใน caption
- ✅ Day separators ในทุกไฟล์ log ที่เที่ยงคืน
- ✅ Plain text alert log format: `date time hostname resolver ip event`
- ✅ Alert Deduplication (หน้าต่าง 30 นาที, cache JSON persistent)
- ✅ Token Bucket Rate Limiting (ค่าเริ่มต้น 20/ชม.)
- ✅ Alert แบบ HTML-formatted: มุมมอง Majority vs Outliers, emojis (🔴/🟡/🔵), type labels (📊/🗳️/🆕/🚫)
- ✅ **แสดง Resolver ทั้งหมดในสรุป** (ลบ Top 5/10 limits) — 2026-09-17
- ✅ **ส่งกราฟทั้งหมด** ไป Telegram (ลบ 5/6 graph limits) — 2026-09-17

### การแจ้งเตือน Anomaly/Recovery (2026-09-09)
- ✅ Event ID format: `{hostname}-YYYYMMDD-HHmmss` สำหรับทั้ง anomaly และ recovery
- ✅ Anomaly: `img/priority.jpg` + สาเหตุ, last unreachable IP จาก MTR, consensus score
- ✅ Recovery: `img/ok.jpg` + ระยะเวลาความผิดปกติ (ชม./นาที/วินาที), ML baseline stability, recovery confidence
- ✅ Event ID ในทั้งคู่เพื่อ correlation
- ✅ ML logging ลงไฟล์พร้อม start time, end time, duration
- ✅ **ส่งข้อความ Telegram จริงและยืนยันบน test VM แล้ว**

### การแจ้งสถานะ Service (2026-09-12)
- ✅ สร้าง `scripts/systemd_wrapper.py` — Wrapper ที่ตรวจจับการ restart ผ่าน state file
- ✅ สร้าง `scripts/systemd_notify.py` — Notifier ตรงสำหรับเหตุการณ์เริ่มต้น/หยุด/รีสตาร์ท/ล้มเหลว/ข้อผิดพลาด
- ✅ ปรับปรุง `systemd/chk-a.service` — ExecStartPre (start) และ ExecStop (stop) ใช้ wrapper
- ✅ State file ที่ `/opt/chk-a/last_state.txt` ติดตามสถานะล่าสุดเพื่อแยกแยะ restart กับการเริ่มต้นใหม่
- ✅ ยืนยันการแจ้งเตือน Telegram: start, restart, stop ส่งข้อความที่ถูกต้อง
- ✅ ตรวจจับการรีสตาร์ท: สถานะก่อนหน้าเป็น "running" + การเริ่มต้นใหม่ → ข้อความ "Service Restart"
- ✅ แก้ไข: ปัญหาสิทธิ์ state file แก้โดย `sudo chown ipds:ipds /opt/chk-a/last_state.txt`

### การตรวจสอบข้อตกลงเวลาท้องถิ่น (2026-09-12)
- ✅ `ml_insights.py`: `datetime.utcnow()` → `datetime.now()` 4 จุด (cutoff calc + generated_at)
- ✅ `pdf_generator.py`: ลบคำว่า " UTC" ออกจาก timestamp หัว/ท้าย PDF
- ✅ `email_sender.py`: ลบคำว่า " UTC" ออกจาก timestamp เนื้อหาอีเมล
- ✅ ยืนยัน `datetime.now()` ทุกจุดในโปรเจกต์ใช้เวลาท้องถิ่นแล้ว
- ✅ ทุก timestamp ในโปรเจกต์ใช้เวลาท้องถิ่น Asia/Bangkok (+07) อย่างสม่ำเสมอ

### การทดสอบและการดำเนินงาน
- ✅ **313/313 tests ผ่าน** บน **ทั้ง dev และ test VM** (นโยบาย zero-regression)
- ✅ CLI subcommands: `validate-config`, `check-once`, `show-baseline`, `test-telegram`, `test-daily-image`, `mtr`
- ✅ Dev↔Test VM sync ผ่าน `rsync -c` (checksum) พร้อม sync กลับทันทีของการแก้ไขบน VM
- ✅ Test VM: Ubuntu 24.04 ที่ 192.168.56.122 (user: ipds), service รันเป็น `chk-a` (uid=999)
- ✅ **Dev→Test sync ด้วย path ที่ถูกต้อง** `/home/ipds/Hermes-Prj/chk-a/` บนทั้งสองเครื่องเสร็จสิ้น

### Security Review และการแก้ไข (เสร็จสมบูรณ์ — 2026-09-13)
- ✅ Security Code Review ครบถ้วน (23 findings: 2 Critical, 5 High, 8 Medium, 5 Low, 3 Info)
- ✅ **C-01 แก้แล้ว**: AlertAgent token bucket race condition — ป้องกันด้วย `asyncio.Lock`
- ✅ **C-02 แก้แล้ว**: AlertAgent dedup cache race condition — ป้องกันด้วย `asyncio.Lock`
- ✅ **H-01 แก้แล้ว**: Orchestrator timezone-naive scheduler — ใช้ `ZoneInfo("Asia/Bangkok")` ทั่วทั้งโค้ด
- ✅ **H-02 แก้แล้ว**: MTR agent timeout calculation — แก้สูตรให้ถูกต้อง
- ✅ **H-03 แก้แล้ว**: BaselineStore age key caching — lazy load พร้อม cache
- ✅ **H-04 แก้แล้ว**: TelegramClient `send_photo` memory — สตรีมแทน `read_bytes()`
- ✅ **H-05 แก้แล้ว**: Orchestrator batch writes — ใช้ `write()` เดียวต่อรอบ
- ✅ **M-01 แก้แล้ว**: ResolverAgent DoH support — ทำงานได้แล้ว (เดิมเป็น `NotImplementedError`)
- ✅ **M-02 แก้แล้ว**: ConsensusAgent reputation สำหรับผลลัพธ์ที่ล้มเหลว — ข้าม failed/empty results
- ✅ **M-03 แก้แล้ว**: MLAgent path learning key collision — prefix `chk-a:path:` (ไม่ชน DNS)
- ✅ **M-04 แก้แล้ว**: Parallel MTR สำหรับ outliers — `asyncio.gather`
- ✅ **M-05 แก้แล้ว**: CircuitBreaker thread-safety + concurrent sending
- ✅ **M-06 แก้แล้ว**: Health server port/address consistency — ทั้งคู่มาจาก config
- ✅ **M-07 แก้แล้ว**: Graph generator Thai font loading — การจัดการ path ที่มั่นคง
- ✅ **M-08 แก้แล้ว**: AlertAgent log rotation — `RotatingFileHandler` สำหรับ JSONL และ plain text
- ✅ SEC-001 แก้แล้ว: MTR Command Injection — IP validation ผ่าน `ipaddress.ip_address()`
- ✅ SEC-002 แก้แล้ว: BaselineStore Path Traversal — path validation พร้อม allowed base dir แบบ dynamic
- ✅ SEC-003 แก้แล้ว: Secrets handling — parse `/etc/chk-a/env` ตรงเข้า config model, redact tokens ใน logs, ใช้ token ใน URL path
- ✅ SEC-004 แก้แล้ว: Health endpoint — bind ไป loopback เท่านั้น
- ✅ SEC-005 แก้แล้ว: บังคับ TLS สำหรับ SMTP — port 465/587 เท่านั้น
- ✅ SEC-006 แก้แล้ว: Input validation บน config fields สำคัญ — Pydantic v2 validators
- ✅ SEC-007 แก้แล้ว: Telegram token ใน URL — token ใน URL path (Telegram Bot API), masked ใน logs
- ✅ SEC-008 แก้แล้ว: LRU dedup cache พร้อม TTL และ max-size
- ✅ SEC-009 แก้แล้ว: Log injection prevention
- ✅ SEC-012 แก้แล้ว: Hard ceilings on concurrency
- ✅ SEC-015 แก้แล้ว: Baseline encryption at rest (age/pyrage)
- ✅ SEC-016 แก้แล้ว: Dependency pinning พร้อม SHA-256 hashes (39 packages)
- ✅ SEC-017 แก้แล้ว: Config file permissions (chmod 640/600, chown root:chk-a)
- ✅ SEC-018 แก้แล้ว: Telegram circuit breaker (CLOSED/OPEN/HALF_OPEN)
- ✅ SEC-019 แก้แล้ว: Daily report scheduler drift fix (absolute time scheduling)
- ✅ SEC-020 แก้แล้ว: MTR/Resolver config sync validation

### การแก้ไข Telegram Reporter (2026-09-13)
- ✅ **แก้แล้ว: รายงานรายวัน 06:00 น. ส่ง Telegram ล้มเหลว 404** — สาเหตุหลัก: `TelegramReporter` ใช้ `Authorization: Bearer *** header แต่ Telegram Bot API กำหนดให้ใช้ token ใน URL path (`/bot<token>/method`)
- ✅ อัปเดต `TelegramReporter` ให้ใช้ token ใน URL path (เหมือนกับ `TelegramClient`)
- ✅ อัปเดต security regression tests ให้ตรวจสอบ token-in-URL behavior
- ✅ Circuit breaker รีคัฟเวอร์อัตโนมัติหลัง 60 วินาที (HALF_OPEN → CLOSED)

### โครงสร้างพื้นฐานการ Deploy (2026-09-14)
- ✅ สร้าง `scripts/deploy.sh` — Deploy script มาตรฐานติดตั้ง source ที่ sync มาจาก `/home/ipds/Hermes-Prj/chk-a/` ไปยัง FHS runtime `/opt/chk-a/` บนเครื่องเป้าหมาย (test/prod)
- ✅ ใช้ `rsync -c` checksum verification และ restart systemd service
- ✅ รันด้วย `sudo` หลัง dev→test sync
- ✅ ยืนยัน hash ตรงกัน: Dev source `/home/ipds/Hermes-Prj/chk-a/` ↔ Runtime `/opt/chk-a/` (MD5: `b7717b974eab7b7d163300430e2fdf08`)
- ✅ แก้ config test VM `/etc/chk-a/config.yaml` — เพิ่ม `daily_report_*` settings ที่หายไป
- ✅ Service ทำงานด้วยโค้ดและ config ที่อัปเดตแล้ว

### รองรับ Rotated Logs และ Baseline Integrity Metrics (2026-09-15)
- ✅ **`_load_recent_checks()` อ่าน rotated logs อัตโนมัติ** — ไฟล์ date-stamped `.bz2` และ numbered `.gz` backups จาก log directory
- ✅ **แก้ไขการ parse timestamp mixed timezone** — รองรับทั้ง naive (real log) และ timezone-aware (mock data) ISO8601 ผ่าน `pd.to_datetime(format="mixed", utc=True).dt.tz_localize(None)`
- ✅ **Baseline-based integrity scoring** — ใช้ `MLAgent.score()` (total-variation distance ต่อ learned baseline) แทน Isolation Forest
- ✅ **เพิ่ม IP stability & diversity metrics** — คำนวณ `unique_ip_count` และ `ip_stability` สำหรับ baseline method (เดิมขาด เฉพาะ Isolation Forest เท่านั้น)
- ✅ **รายงานรายวัน (เมื่อวาน)** — 10,374 records จาก rotated log `checks.jsonl-20260914.bz2` → ส่ง Telegram สำเร็จ
- ✅ **รายงานรายเดือน (30 วัน)** — 53,588 records จากหลาย rotated files → สร้างกราฟสำเร็จ
- ✅ **Day 1 sample report (ข้อมูลเต็มที่มี)** — 53,588 records → ส่ง Telegram พร้อม 10 กราฟ
- ✅ **ตัวอย่างรายงาน 06:00 น. (ข้อมูลเมื่อวาน)** — ใช้ `reference_date=yesterday 23:59` → โหลดข้อมูลเมื่อวานถูกต้อง
- ✅ **Real-time daily report (เที่ยงคืนถึงตอนนี้)** — สร้าง script manual run, filter ข้อมูลวันนี้จาก current log

### ตรวจสอบรายงานวันที่วานขาดหายตอน Startup (2026-09-15)
- ✅ **Orchestrator ตรวจสอบรายงานวันที่วานขาดหายตอนเริ่ม service** — เรียก `_send_missing_daily_report()` หลัง init tasks
- ✅ ตรวจสอบ `output_dir` หาโฟลเดอร์รายงานวันที่วาน; ถ้าไม่มี สร้างและส่งอัตโนมัติ
- ✅ ใช้ `reference_date=yesterday 23:59:59` เพื่อ target ข้อมูล rotated log ของเมื่อวานได้ถูกต้อง
- ✅ ส่ง Telegram ด้วยรูปแบบเหมือนรายงาน 06:00 น. ที่กำหนด (ภาษาไทย, emoji, protected palette, hostname, timestamp)

### GitHub Release และ Production Installer (2026-09-16)
- ✅ **GitHub Actions Release Workflow** — `.github/workflows/release.yml` build wheel เมื่อ push tag (v*), สร้าง GitHub Release พร้อม assets
- ✅ **Production Installer (`install.sh`)** — ดาวน์โหลด wheel + assets จาก GitHub Releases, สร้าง venv, ติดตั้ง wheel, config systemd, logrotate
- ✅ **Uninstaller (`uninstall.sh`)** — ลบทุกอย่างของ service, configs, logs, state, user
- ✅ **Makefile** — Targets: `install`, `install-github`, `uninstall`, `upgrade`, `status`, `logs`, `version`, `release-dry-run`
- ✅ **v1.0.0 released** (2026-09-16) — 10 assets: wheel, install.sh, uninstall.sh, Makefile, config.yaml.example, env.example, chk-a.service, logrotate.chk-a
- ✅ **v1.0.1 released** (2026-09-16) — แก้ wheel filename resolution ผ่าน GitHub API, เพิ่ม pip installation fallback
- ✅ **v1.0.2 released** (2026-09-16) — ปรับปรุง pip installation: `ensurepip` พร้อม log output, fallback `get-pip.py`, verification พร้อม log version

### Install.sh Fixes (2026-09-17)
- ✅ **v1.0.3** — Fix install.sh venv reuse bug (added pip verification, improved logging)
- ✅ **v1.0.4** — Fix env permission to 0640 so service can read Telegram credentials
- ✅ **v1.0.5** — Ensure env.example is present and not empty after download
- ✅ **v1.0.6** — Fix env file permissions (0640) so service can read credentials
- ✅ **v1.0.7** — Ensure env.example is present and not empty after download
- ✅ **v1.0.8** — Move env.example check to /tmp, remove silent failures, add verification step
- ✅ **v1.0.9** — Fix wheel download for "latest" (correct GitHub API endpoint), add timeouts/progress bars
- ✅ **v1.0.10** — Use dedicated temp dir (mktemp) for downloads, remove existing files before download
- ✅ **v1.0.11** — Change default reporting.output_dir to /var/lib/chk-a/reports to fix read-only filesystem error
- ✅ **v1.0.12** — Fix HTML parsing in Telegram messages (remove auto-escape from TelegramClient, add proper escaping in callers)
- ✅ **v1.0.13** — Support Python 3.10+ (Ubuntu 22.04 LTS), add backports.zoneinfo dependency
- ✅ **v1.0.14** — Add manual daily/monthly report scripts for on-demand reporting

### Manual Report Scripts (2026-09-17)
- ✅ `scripts/manual_daily_report.py` — รายงานรายวัน on-demand จากเที่ยงคืนถึงตอนนี้
- ✅ `scripts/manual_monthly_report.py` — รายงานรายเดือน on-demand จากวันที่ 1 ถึงตอนนี้
- ✅ **แก้แล้ว: ทั้งคู่แสดง Resolver ทั้งหมด** (ลบ hardcoded `[:10]` limits) — 2026-09-17 19:30:00
- ทั้งคู่สร้างสรุปไทย/อังกฤษ + กราฟ ส่ง Telegram on-demand

### Daily Availability Heatmap สำหรับรายงานรายเดือน (2026-09-17 20:00:00)
- ✅ เพิ่ม `daily_availability` computation ใน `ml_insights.py::compute_availability()`
- ✅ เพิ่ม `generate_availability_daily_heatmap()` ใน `graph_generator.py` พร้อมเวอร์ชันไทย
- ✅ บูรณาการใน `generate_summary_dashboard()` — รายงานรายเดือนมีทั้ง Hourly และ Daily Heatmap
- ✅ รายงานรายเดือน: กราฟ 18-20 รูป (7 chart types × EN/TH = 14 + 2 Dashboard = 16 + 2 Daily Heatmap = 18)

### v1.0.15 Release (2026-09-18)
#### แก้ไข (Fixed)
- **2026-09-18 21:00:00** — `src/chk_a/reporting/monthly_report.py` — แก้: Daily report time range bug. เปลี่ยนจาก `datetime.now().replace(hour=23, minute=59) - timedelta(days=1)` (ซึ่งให้เวลาผิดตอนรัน 06:00) เป็น `yesterday = datetime.now() - timedelta(days=1); yesterday_end = yesterday.replace(hour=23, minute=59)` เพื่อให้ได้เวลา 23:59:59 ของเมื่อวานถูกต้อง
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — แก้: Daily midnight task (00:00) error handling สำหรับภาพหาย. เพิ่ม fallback ใช้ anomaly/recovery images จาก AlertAgent, logging รายละเอียดเมื่อภาพหาย, และ skip gracefully

#### เพิ่ม (Added)
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — เพิ่ม: Copy `img/` directory ไปเป็น release assets และสร้าง `img.tar.gz` สำหรับการติดตั้ง production
- **2026-09-18 21:00:00** — `install.sh` — เพิ่ม: ดาวน์โหลดและ extract `img.tar.gz` ไป `/opt/chk-a/img/` ระหว่างติดตั้ง production
- **2026-09-18 21:00:00** — `config/config.yaml.example` — เพิ่ม: ตัวอย่าง config ครบทุก section (fqdns, resolvers, resolver_agent, ml, alert, scheduler, logging, mtr, reporting, baseline_store_path) พร้อมคำอธิบายไทยทุก setting
- **2026-09-18 21:00:00** — `config/chk-a.env.example` — เพิ่ม: ตัวอย่าง environment ครบ พร้อม placeholder สำหรับ Telegram, SMTP, และ Age encryption keys

#### เปลี่ยนแปลง (Changed)
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — เปลี่ยน: ปรับปรุง daily midnight task logging และ fallback logic สำหรับ daily/anomaly/recovery images
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — เปลี่ยน: ใช้ `config/config.yaml.example` ใหม่ครบถ้วนใน release assets แทน `config/chk-a.config.yaml.example` เก่า

### Production Deployment v1.0.15 (2026-09-18)
- ✅ **สร้าง Release v1.0.15** — GitHub Release พร้อม assets ครบ รวมถึง `img.tar.gz`
- ✅ **Production `uptime-host` ติดตั้ง v1.0.15 แล้ว** — โฟลเดอร์ `img/` ถูก deploy ไป `/opt/chk-a/img/`
- ✅ **Production config อัปเดตแล้ว** — เพิ่ม `reporting` section, `mtr` section, `daily_image_path`, `resolver_agent: {}`
- ✅ **00:00 Daily image ทำงานยืนยันแล้ว** — ได้รับข้อความ Telegram พร้อม `sleepy.jpg` + hostname + day separators
- ✅ **06:00 Daily report รอตรวจสอบ** — รอบถัดไปที่กำหนด

### v1.0.16 Release (2026-09-19)
- ✅ Telegram sequential send + Thai-only graphs

### v1.0.17 Release (2026-09-19)
- ✅ Latency boxplot sort by median ASC (fastest on top)

### v1.0.18 Release (2026-09-19)
- ✅ Timezone fix for daily reports + robust Thai filtering

### v1.0.19 Release (2026-09-19)
- ✅ Graph filename suffix for Thai filtering + consistent daily reports

### v1.0.20 Release (2026-09-19)
- ✅ Timezone fix for daily reports + robust Thai filtering

### v1.0.21 Release (2026-09-19)
- ✅ Debug logging for daily reports + robust Thai filtering

### v1.0.22 Release (2026-09-20)
- ✅ Manual daily report fixes: Thai-only filter, latency boxplot sort, daily heatmap month context

### v1.0.23 Release (2026-09-20)
- ✅ Service startup report fix: Thai-only, today data 00:00-now, daily heatmap month context, background task

### v1.0.24 Release (2026-09-20)
- ✅ Fix pyproject.toml version to 1.0.24 (was 1.0.14) — ensures wheel builds with correct version

### v1.0.25 Release (2026-09-20 17:30:00)
- ✅ Missing daily report on startup now merges month data (Sep 1 to yesterday) for daily availability heatmap
- ✅ Daily heatmap title format: "Days 1 to N" (EN) / "วันที่ 1 ถึง N" (TH) — clearer than "Month: 1st to DD MMM"
- ✅ Month start fix: Both missing & today reports use `month_start = day 1`

### v1.0.26 Release (2026-09-21 06:30:00)
- ✅ Scheduled daily report (06:00 น.) merge month data (1st ถึงเมื่อวาน) สำหรับ daily availability heatmap, สอดคล้องกับ startup report behavior

### v1.0.27 Release (2026-09-21 08:00:00)
- ✅ แสดง version ทั่วทุกรายงาน:
  - กราฟ: Version ใน footer กลาง (`vX.Y.Z`) ผ่าน `_add_header_footer()` ใน `graph_generator.py`
  - Telegram Monthly Summary: Version ท้ายข้อความผ่าน `create_telegram_summary()` ใน `telegram_reporter.py`
  - Telegram Daily Summary: Version ท้ายข้อความผ่าน `create_daily_telegram_summary()` ใน `telegram_reporter.py`
  - Dashboard/Reports: Version ส่งผ่าน `generate_summary_dashboard()` ไป 8 chart types ทั้งหมด

### v1.0.28 Release (2026-09-21 10:30:00)
- ✅ Version detection ทำงานทั้งตอนติดตั้งเป็น package และรันเป็น module (`-m chk_a.main`). เพิ่ม fallback อ่านจาก `pyproject.toml`
- ✅ CLI commands `test-telegram` และ `test-daily-image` extract secret values จาก `SecretStr` ก่อนส่งให้ `TelegramClient`, แก้ "Object of type SecretStr is not JSON serializable" error

### v1.0.29 Release (2026-09-21 15:30:00)
- ✅ MTR CLI target validation auto-appends `:53` สำหรับ bare IP/hostname, ให้ CLI รับ bare IP/hostname เป็น target argument ได้โดยไม่ต้องระบุ port เอง
- ✅ Test VM Python cache issue แก้แล้ว: ลบ `.pyc` cache เพื่อ serve updated `__version__` (1.0.29)

### v1.0.30 Release (2026-09-22 14:45:00)
- ✅ **SEC-010**: DoH/DoT resolver support tests เพิ่ม — `test_doh_resolver_resolves()` mocking aiohttp DoH query with DNS wireformat response
- ✅ **SEC-011**: CAP_NET_RAW for MTR ICMP tests เพิ่ม — `TestSEC011_MTRCapNetRaw` class 3 tests verify systemd CAP_NET_RAW capability, MTRConfig ICMP mode support, MTRAgent ICMP privileges
- ✅ **Log Rotation Tests**: Comprehensive tests สำหรับ `_load_recent_checks()` ครอบคลุม plain JSONL, date-stamped `.bz2`, numbered `.gz`, mixed timezone timestamps, fractional lookback, malformed lines, non-CheckResult log lines, empty/nonexistent files, edge cases (18 tests)
- ✅ แก้: `_load_recent_checks()` timestamp parsing สำหรับ mixed naive และ timezone-aware timestamps, preserve local time (Asia/Bangkok) สำหรับ naive timestamps ขณะแปลง aware timestamps ไป Asia/Bangkok
- ✅ แก้: 13 test functions แทนที่ `tmp_path` pytest fixture ด้วย `_make_temp_path()` helper จาก conftest.py เพื่อ baseline path consistency

### v1.0.31 Release (2026-09-22 15:30:00)
- ✅ **Email Reporting Tests**: Comprehensive tests สำหรับ EmailSender class (12 tests) ครอบคลุม STARTTLS/implicit TLS, auth/no-auth, missing attachments, exception handling, create_email_body() function (English/Thai languages, missing summary), MonthlyReportGenerator integration

### v1.0.32 Release (2026-09-22 16:00:00)
- ✅ **FQDN-centric Data Model**: เพิ่ม `FQDNRecord` และ `FQDNStore` พร้อม identity (fqdn, domain, subdomain, apex), DNS records (current IPs, CNAME chain, TTL), history (IP changes with timestamps/sources), metadata (registrar, expiry, NS), monitoring state (last_checked, status, failures), alerting rules, ML features (baseline IPs, anomaly score, flip-flop count, geo shifts)
- ✅ **FQDN Store Tests**: 25 comprehensive tests ครอบคลุม creation, domain extraction, IP change history, monitoring state transitions, baseline/anomaly updates, serialization, persistence, queries (by domain, status, anomaly, recent changes), path traversal protection, corrupt/empty file handling

### v1.0.33 Release (2026-09-22 16:30:00)
- ✅ **Startup Report Heatmap Fix**: แก้ `_send_today_report_on_startup()` ให้ใช้ `reference_date=now` แทน `today_end`, ให้ fractional lookback ครอบคลุม 00:00 ถึงเวลาปัจจุบันถูกต้อง (ไม่ใช่ 09:30-14:30)
- ✅ **Version Bump**: Source files แสดง 1.0.33 ถูกต้อง (เคยเป็น 1.0.32 ใน pyproject.toml และ main.py)
- ✅ Python cache cleared และ package reinstall สำหรับ `__version__` detection ที่ถูกต้อง

### v1.0.34 Release (2026-09-22 16:30:00)
- ✅ **Modern Graph Styling**: Overhaul `graph_generator.py` เต็มรูปแบบ พร้อม colorblind-safe palette (viridis heatmap, semantic colors), clean aesthetics (ไม่มี top/right spines, subtle grid), DPI สูงขึ้น (200), colorblind-safe categorical palette (seaborn colorblind), ปรับปรุง Thai font (bold weight, adjusted sizes). Footer version สี primary blue
- ✅ **Alert/Recovery Version Footer**: เพิ่ม version footer ใน Telegram alert และ recovery messages (`🏷️ <b>chk-a v1.0.34</b>`)
- ✅ **Test VM Sync**: Sync source files ทั้งหมดไป test VM ผ่าน rsync, 313/313 tests ผ่านบน test VM
- ✅ **Production Ready**: GitHub Release v1.0.34 published พร้อม assets ทั้งหมด

### v1.0.35 Release (2026-09-23 10:00:00)
- ✅ **Thai Localization สำหรับ Telegram alerts และ reports ทั้งหมด** — Thai rewrite เต็มรูปแบบของ `_format_html()` สำหรับ anomaly/recovery/hourly_reminder, Thai monthly/daily report summaries
- ✅ **Terminology สอดคล้องกัน**: `ฝ่ายมาก` (Majority), `ฝ่ายน้อย` (Minority), `เสมอ` (Tie), `ค่าผิดปกติ` (Outliers), `ล้มเหลว / ไม่ตอบสนอง` (Failed)
- ✅ **Consensus descriptions**: `100% = ตอบเหมือนกันหมด`, `90-99% = สูงมาก — มี resolver ฝ่ายน้อยผิดปกติ`, `70-89% = ปานกลาง — มี resolver ฝ่ายน้อยผิดปกติ`, `50-69% = แยกสองฝ่ายชัดเจน`, `1-49% = ใกล้ Tie ความไม่แน่นอนสูง`, `0% = เสมอภาค`
- ✅ **313/313 tests ผ่านทั้งหมด** (zero regression)

### FQDN Features Implementation (2026-09-23)
- ✅ **Per-FQDN Custom Alert Thresholds** — `FQDNConfig.alert_rules` dict พร้อม `anomaly_threshold`, `consensus_min_score` ต่อ FQDN
- ✅ **FQDN Availability Tracking** — คำนวณต่อรอบ (`successful_resolvers / total * 100`)
- ✅ **IP Change Detection/Alert** — `_alert_ip_change()` ทริกเกอร์เมื่อ `current_ips != observed_ips`, ส่ง Thai-formatted alert
- ✅ **FQDNStore Integration** — Import & init ใน Orchestrator, FQDNRecord อัปเดตทุกรอบ
- ✅ **Thai Formatting สำหรับ `ip_change`** — เพิ่มใน `alert_agent.py` type_map และ `_format_html()`
- ✅ **313/313 tests ผ่านทั้งหมด** (รวม FQDN features ใหม่)
- ✅ **Synced to Test VM** — พร้อม deploy

---

## 4. สิ่งที่กำลังทำอยู่

- **Test VM Deploy** — รอ `sudo ./scripts/deploy.sh` บน 192.168.56.122

---

## 5. ปัญหาที่พบ

### แก้เสร็จแล้ว
- ✅ seaborn installed on test VM
- ✅ `send_photo` mock signature fixed in test_alert_agent.py
- ✅ State file permission issue resolved: `sudo chown ipds:ipds /opt/chk-a/last_state.txt`
- ✅ `sudo: A terminal is required to authenticate` — user runs sudo commands directly on test VM
- ✅ **Daily report Telegram 404 error** — Fixed by using token in URL path (Telegram Bot API requirement)
- ✅ **Test VM missing daily_report_* config** — Added to `/etc/chk-a/config.yaml`
- ✅ **Runtime code mismatch** — Fixed by running `scripts/deploy.sh` on test VM
- ✅ **Missing yesterday's report on startup** — Auto-check and generate on service start
- ✅ **v1.0.0/v1.0.1 install.sh wheel download** — Fixed via GitHub API lookup + constructed filename fallback
- ✅ **v1.0.1/v1.0.2 pip installation** — Added ensurepip + get-pip.py fallback + verification
- ✅ **v1.0.3-v1.0.14** — Sequential fixes for install.sh, env permissions, env.example, wheel download, temp dirs, output_dir, Python 3.10+, manual report scripts
- ✅ **Daily report time range bug** — Fixed in v1.0.15 (monthly_report.py)
- ✅ **Daily midnight task missing image** — Fixed in v1.0.15 (orchestrator.py fallback logic)
- ✅ **Release assets missing img.tar.gz** — Fixed in v1.0.15 (release.yml + install.sh)
- ✅ **Daily startup report: Thai-only graphs + today's data (00:00 to now)** — Fixed in v1.0.23/v1.0.25
- ✅ **Missing daily report month merge** — Fixed in v1.0.25
- ✅ **Daily heatmap title format** — Fixed in v1.0.25 ("Days 1 to N" / "วันที่ 1 ถึง N")
- ✅ **Scheduled daily report month merge** — Fixed in v1.0.26
- ✅ **Version display across all reports** — Fixed in v1.0.27
- ✅ **Version detection (package vs module)** — Fixed in v1.0.28
- ✅ **SecretStr JSON serialization in CLI** — Fixed in v1.0.28
- ✅ **MTR CLI target validation** — Fixed in v1.0.29
- ✅ **Test VM Python cache** — Fixed in v1.0.29
- ✅ **SEC-010/011 tests** — Added in v1.0.30
- ✅ **Log rotation tests** — Added in v1.0.30
- ✅ **tmp_path fixture misuse** — Fixed in v1.0.30
- ✅ **Email reporting tests** — Added in v1.0.31
- ✅ **FQDN-centric model** — implemented ใน v1.0.32
- ✅ **Startup heatmap window bug** — Fixed in v1.0.33
- ✅ **Version bump in source files** — Fixed in v1.0.33
- ✅ **Alert/Recovery version footer** — Added in v1.0.33 (local)
- ✅ **Modern graph styling** — implemented ใน v1.0.34
- ✅ **Thai localization complete** — implemented ใน v1.0.35
- ✅ **FQDN features complete** — implemented 2026-09-23

### กำลังดำเนินการ
ไม่มี — ปัญหาที่รู้จักทั้งหมดแก้เสร็จแล้ว

---

## 6. งานที่ต้องทำต่อ

### Sprint นี้ (P2)
- Deploy ไป test VM และ verify FQDN features
- Verify IP change alerts บน test VM
- Tag v1.0.36 สำหรับ production release

### Quarter นี้ (P3)
- Dashboard web UI (FastAPI + HTMX + Chart.js)
- GitHub repo cleanup & branch consolidation
- Historical data compaction

---

## 7. ไฟล์ที่เกี่ยวข้อง

### Core Agents
| ไฟล์ | บรรทัด | วัตถุประสงค์ |
|------|-------|-------------|
| `src/chk_a/agents/resolver_agent.py` | ~280 | Parallel DNS query, health EMA |
| `src/chk_a/agents/consensus_agent.py` | ~220 | Weighted vote, entropy, outliers, reputation |
| `src/chk_a/agents/ml_agent.py` | ~180 | Exponential decay baseline, anomaly scoring |
| `src/chk_a/agents/alert_agent.py` | ~350 | Dedup, rate-limit, Telegram, dual audit logs |
| `src/chk_a/agents/mtr_agent.py` | ~400 | MTR subprocess, JSON parsing, hop stats |
| `src/chk_a/storage/fqdn_store.py` | ~350 | FQDN-centric data model & storage |

### Orchestration & Config
| ไฟล์ | บรรทัด | วัตถุประสงค์ |
|------|-------|-------------|
| `src/chk_a/orchestrator.py` | ~550 | Cycle coordination, scheduler, healthz, daily/monthly tasks |
| `src/chk_a/config/loader.py` | ~200 | YAML + env substitution, Pydantic, auto-tune |
| `src/chk_a/models/schemas.py` | ~250 | Pydantic contracts ทั้งหมด |
| `src/chk_a/storage/baseline_store.py` | ~120 | Atomic JSON baseline persistence |

### Reporting
| ไฟล์ | บรรทัด | วัตถุประสงค์ |
|------|-------|-------------|
| `src/chk_a/reporting/graph_generator.py` | ~950 | 7 chart types × EN/TH, Thai fonts, translation map + Daily Heatmap |
| `src/chk_a/reporting/monthly_report.py` | ~350 | Report pipeline: insights → graphs → PDF → Telegram/email |
| `src/chk_a/reporting/telegram_reporter.py` | ~400 | Batched photo sending, exponential backoff, HTML summary |
| `src/chk_a/reporting/pdf_generator.py` | ~200 | fpdf2 EN/TH templates |
| `src/chk_a/reporting/ml_insights.py` | ~260 | Availability, integrity, path health, anomaly detection + daily_availability |
| `src/chk_a/reporting/telegram_client.py` | ~180 | Async Telegram client with retry, circuit breaker |
| `src/chk_a/reporting/email_sender.py` | ~200 | SMTP email with TLS, PDF attachments |

### Entry Point & Config
| ไฟล์ | วัตถุประสงค์ |
|------|-------------|
| `src/chk_a/main.py` | CLI + daemon entry, subcommands |
| `systemd/chk-a.service` | ปรับปรุง: ExecStartPre/ExecStop ใช้ systemd_wrapper.py สำหรับการแจ้งสถานะ |
| `/etc/chk-a/config.yaml` | การตั้งค่าผลิต (test VM & production) |
| `/opt/chk-a/config.example.yaml` | Config reference |
| `/etc/chk-a/env` | **Telegram credentials** (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) |

### Scripts
| ไฟล์ | วัตถุประสงค์ |
|------|-------------|
| `scripts/systemd_wrapper.py` | Systemd service wrapper — ตรวจจับการ restart, ส่งการแจ้ง start/restart/stop/fail |
| `scripts/systemd_notify.py` | Notifier สถานะ systemd — start/stop/restart/fail/error |
| `scripts/send_test_telegram.py` | ส่งข้อความ Telegram ทดสอบ anomaly/recovery พร้อมรูปภาพ |
| `scripts/deploy.sh` | Deploy source ที่ sync มาไปยัง FHS runtime `/opt/chk-a/` |
| `scripts/manual_daily_report.py` | On-demand daily report from midnight to now |
| `scripts/manual_monthly_report.py` | On-demand monthly report from 1st to now |
| `show_fqdn_examples.py` | Demo script สำหรับ FQDN data structures |

### Test & Scripts
| ไฟล์ | วัตถุประสงค์ |
|------|-------------|
| `tests/test_alert_agent.py` | Alert agent tests (อัปเดตแล้วสำหรับ `send_photo` signature + Thai format) |
| `tests/conftest.py` | Session-wide test config (`CHK_A_BASELINE_DIR=/tmp`, `CHK_A_FQDN_DIR=/tmp/chk-a-test/fqdns`) |
| `tests/test_integration_pipeline.py` | Full pipeline integration tests (7 tests) |
| `tests/test_security_regressions.py` | Security regression tests (74 tests, SEC-001 ถึง SEC-020) |
| `tests/test_fqdn_store.py` | FQDN store tests (25 tests) |
| `tests/test_reporting.py` | Log rotation tests (18 tests) |
| `tests/test_email_sender.py` | Email sender tests (12 tests) |
| `tests/test_orchestrator.py` | Orchestrator tests (12 tests, อัปเดตสำหรับ FQDNStore) |

### Release & Deployment
| ไฟล์ | วัตถุประสงค์ |
|------|-------------|
| `.github/workflows/release.yml` | GitHub Actions: build wheel, create release on tag push |
| `install.sh` | Production installer from GitHub Releases |
| `uninstall.sh` | Production uninstaller |
| `Makefile` | Dev/ops targets: install, uninstall, upgrade, status, logs, version |

---

## 8. TODO List

ดูรายละเอียดใน [TODO.md](TODO.md)

---

*สร้างโดย Hermes Agent session วันที่ 2026-09-23 11:45:00 (Asia/Bangkok UTC+07)*