# บริบทโครงการ — chk-a

**อัปเดตล่าสุด:** 2026-09-22 15:40:32 (Asia/Bangkok UTC+07)

---

## ภาพรวมโครงการ

**chk-a** เป็นระบบตรวจสอบความผิดปกติของ DNS A-record แบบ Multi-Agent เขียนด้วย Python ระบบจะสอบถาม DNS resolver หลายตัวพร้อมกันสำหรับ FQDN ที่กำหนด สร้างคะแนนเสียงถ่วงน้ำหนัก (Weighted Consensus) เรียนรู้ Baseline แบบ Online Exponential Decay ตรวจจับ Anomaly และส่ง Alert ผ่าน Telegram พร้อมรายงานรายวัน/รายเดือน (ภาษาไทย/อังกฤษ + กราฟ + PDF)

**ที่เก็บโค้ด:** `tpdevices/chk-a` (GitHub, HTTPS with PAT)  
**พัฒนา:** WSL Ubuntu (172.20.14.199/20)  
**เครื่องทดสอบ:** VirtualBox Ubuntu 24.04 ที่ 192.168.56.122 (user: ipds)  
**เครื่อง Production:** `uptime-host` (internal DNS monitoring)  
**Service User:** `chk-a` (uid=999)  
**Python:** 3.14.4 (`python3`, PEP 668 → venv/uv)  
**Timestamp ทั้งหมด:** เวลาท้องถิ่น Asia/Bangkok (+07), รูปแบบ `YYYY-MM-DD HH:MM:SS`

---

## สถาปัตยกรรม

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

## การตัดสินใจออกแบบหลัก

1. **ไม่ใช้ Prometheus/metrics** — Observability ผ่าน JSONL logs ที่มีโครงสร้าง + `/healthz` + systemd watchdog
2. **ไม่ใช้ Heavy ML dependencies** — Online EMA baseline, total-variation anomaly score (Python มาตรฐาน, ไม่ต้องใช้ sklearn/torch)
3. **ภาษาไทยเป็น First-class** — กราฟทั้ง 7 ประเภทมีเวอร์ชัน EN/TH, `_apply_thai_fonts()` พร้อม translation map, ตรวจหา Thai font อัตโนมัติ (Loma/TLWG)
4. **Atomic persistence** — Baseline store ใช้ temp file + `os.replace` + `fsync`; dedup cache เหมือนกัน
5. **Config-driven** — YAML พร้อม `${ENV}` substitution, Pydantic validation, auto-tuned concurrency
6. **Dev↔Test sync** — `rsync -c` (checksum) จาก dev ไป test VM, sync กลับทันทีของการแก้ไขบน VM
7. **Telegram delivery reliability** — ส่งแบบ batch (ปรับ batch size/delay/retries ได้), exponential backoff (2s→4s→8s)
8. **Anomaly/Recovery notifications with images** — Event ID correlation, MTR last unreachable IP, duration tracking, ML logging (2026-09-09)
9. **การแจ้งสถานะ Service** — ใช้ state file เพื่อตรวจจับการ restart, ส่งเหตุการณ์วงจรไปยัง Telegram (2026-09-12)
10. **ข้อตกลงเวลาท้องถิ่น** — ทุก timestamp ใช้เวลาท้องถิ่น Asia/Bangkok (+07); ไม่มี UTC ในการคำนวน, output, หรือเอกสาร (2026-09-12)
11. **Security Code Review เสร็จสิ้น** — Critical/High/Medium findings ทั้งหมดแก้แล้ว (2026-09-13)
12. **มาตรฐานการ Deploy** — Dev source ที่ `/home/ipds/Hermes-Prj/chk-a/`, runtime ที่ `/opt/chk-a/` (FHS), deploy ผ่าน `scripts/deploy.sh` (2026-09-14)
13. **รองรับ Rotated Logs** — `_load_recent_checks()` อ่าน date-stamped `.bz2` และ numbered `.gz` backups อัตโนมัติ (2026-09-15)
14. **Baseline-based Integrity** — ใช้ `MLAgent.score()` (total-variation distance) แทน Isolation Forest, พร้อม IP stability/diversity metrics (2026-09-15)
15. **Startup Missing Report Check** — Orchestrator ตรวจสอบและส่งรายงานวันที่วานขาดหายตอน startup (2026-09-15)
16. **GitHub Release & Production Installer** — Actions workflow build wheel เมื่อ push tag, สร้าง release; `install.sh` ดาวน์โหลดจาก GitHub Releases, ติดตั้งไป `/opt/chk-a/` พร้อม systemd (2026-09-16)
17. **Manual Report Scripts** — `manual_daily_report.py` และ `manual_monthly_report.py` สำหรับรายงาน on-demand (2026-09-17)
18. **แสดง Resolver ทั้งหมดใน Telegram** — ลบ Top 5/10 limits จากสรุปและการส่งกราฟ (2026-09-17 15:30:00, 19:30:00)
19. **Daily Availability Heatmap** — เพิ่ม Heatmap แบบวันในเดือน vs resolver สำหรับรายงานรายเดือน (2026-09-17 20:00:00)
20. **v1.0.15 Release** — แก้ daily report time range bug, daily midnight task image fallback, complete config examples, img/ ใน release assets (2026-09-18)
21. **v1.0.16 Release** — Telegram sequential send + Thai-only graphs (2026-09-19)
22. **v1.0.17 Release** — Latency boxplot sort by median ASC (fastest on top) (2026-09-19)
23. **v1.0.18 Release** — Timezone fix for daily reports + robust Thai filtering (2026-09-19)
24. **v1.0.19 Release** — Graph filename suffix for Thai filtering + consistent daily reports (2026-09-19)
25. **v1.0.20 Release** — Timezone fix for daily reports + robust Thai filtering (2026-09-19)
26. **v1.0.21 Release** — Debug logging for daily reports + robust Thai filtering (2026-09-19)
27. **v1.0.22 Release** — Manual daily report fixes: Thai-only filter, latency boxplot sort, daily heatmap month context (2026-09-20)
28. **v1.0.23 Release** — Service startup report fix: Thai-only, today data 00:00-now, daily heatmap month context, background task (2026-09-20)
29. **v1.0.24 Release** — Fix pyproject.toml version to 1.0.24 (was 1.0.14) — ensures wheel builds with correct version (2026-09-20)
30. **v1.0.25 Release** — Missing daily report month merge + daily heatmap title format (Days 1 to N / วันที่ 1 ถึง N) (2026-09-20)
31. **v1.0.26 Release** — Scheduled daily report (06:00 AM) merge month data (1st to yesterday) for daily availability heatmap (2026-09-21)
32. **v1.0.27 Release** — Version display across all reports (graphs footer, Telegram summaries, dashboard) (2026-09-21)
33. **v1.0.28 Release** — Version detection works both as package and module; SecretStr extraction in CLI (2026-09-21)
34. **v1.0.29 Release** — MTR CLI target validation auto-appends `:53`; Test VM Python cache resolved (2026-09-21)
35. **v1.0.30 Release** — SEC-010/011 tests, Log Rotation tests, tmp_path fixture fixes (2026-09-22)
36. **v1.0.31 Release** — Email Reporting tests (2026-09-22)
37. **v1.0.32 Release** — FQDN-centric Data Model & Store (2026-09-22)
38. **v1.0.33 Release** — Startup heatmap fix, version bump in source files (2026-09-22)
39. **v1.0.34 Release** — Modern graph styling (colorblind-safe palette), alert/recovery version footer (2026-09-22)

---

## การตั้งค่า (Configuration)

**หลัก:** `/etc/chk-a/config.yaml` (test VM & production)  
**อ้างอิง:** `/opt/chk-a/config.example.yaml`

Section สำคัญ:
- `fqdns` — รายการ FQDN พร้อม `min_consensus` และ `expected_ips` (optional)
- `resolvers` — Resolver endpoints (`name`, `address` เป็น `IP:port`, `weight`, `timeout_ms`)
- `resolver_agent` — `max_concurrent`, `default_timeout_ms` (auto-tuned)
- `ml` — `baseline_decay`, `anomaly_threshold`, `min_samples_before_alert`
- `alert` — Telegram credentials, dedup window, rate limit, log paths, daily image config, dedup cache path
- `scheduler` — `min_interval_sec` (30), `max_interval_sec` (180), `jitter`
- `mtr` — enabled flag, interval, max_hops, count, interval_ms, timeout_sec, mode (icmp/tcp/udp), resolvers list
- `reporting` — Monthly/daily schedules, output dir, Telegram/email config, graph inclusion
- `baseline_store_path` — `/var/lib/chk-a/baselines.json`

**Secrets:** `/etc/chk-a/env` — เก็บ `TELEGRAM_BOT_TOKEN` และ `TELEGRAM_CHAT_ID` (test VM & production)

---

## รายละเอียดการรายงาน (Reporting Details)

### รายงานรายเดือน (วันที่ 1 ทุกเดือน, 06:00 น.)
- ML insights จาก lookback 30 วัน
- กราฟ 7 ประเภท × EN/TH = 14 กราฟ + 2 Dashboards = 16 ไฟล์
- **ใหม่: Daily Availability Heatmap** — Heatmap แบบวันในเดือน vs resolver (EN/TH = 2 กราฟเพิ่ม)
- รวม: 18-20 กราฟต่อรายงานรายเดือน
- รายงาน PDF (EN/TH) ผ่าน fpdf2
- Telegram: สรุปภาษาไทย + กราฟ (batched, ส่งกราฟทั้งหมด)
- อีเมล: PDF attachment เต็ม

### รายงานรายวัน (06:00 น., lookback 1 วัน)
- กราฟเหมือนกัน, time window 1 วัน
- Telegram: สรุปภาษาไทย + กราฟ (batched, ส่งกราฟทั้งหมด)

### ประเภทกราฟ (7)
1. Availability Bar (availability % ต่อ resolver)
2. Availability Heatmap (รายชั่วโมงต่อ resolver)
3. **ใหม่: Daily Availability Heatmap** (วันในเดือนต่อ resolver)
4. Integrity Score (ML-based ต่อ resolver)
5. Latency Boxplot (latency distribution ต่อ resolver)
6. IP Stability & Diversity (unique IP set, stability %)
7. MTR Path Visualization (hop loss/latency)
8. Path Availability (ML-based network path health)

### การแสดงภาษาไทย
ทุกกราฟเรียก `_apply_thai_fonts()` → translation map ครอบคลุมทุก label, footer แบ่งซ้าย/ขวา (hostname | timestamp), lang param ควบคุม TH/EN โดยไม่ซ้ำ

---

## รูปแบบ Telegram

### Alert Messages (HTML)
- Severity emojis: 🔴 Critical / 🟡 Warning / 🔵 Info
- Type labels: 📊 Baseline Deviation / 🗳️ Consensus Deviation / 🆕 New IP / 🚫 NXDOMAIN
- จัดกลุ่ม Majority vs Outliers
- Failed resolvers แสดงแยก
- Baseline comparison สำหรับ baseline_deviation
- Hostname, resolver names, timestamp (local time)

### การแจ้งเตือน Anomaly/Recovery (2026-09-09)
- **Event ID:** `{hostname}-YYYYMMDD-HHmmss` (ทั้ง anomaly และ recovery สำหรับ correlation)
- **Anomaly:** `img/priority.jpg` + สาเหตุ, last unreachable IP จาก MTR, consensus score
- **Recovery:** `img/ok.jpg` + ระยะเวลาความผิดปกติ (ชม./นาที/วินาที), ML baseline stability, recovery confidence
- ML logging ลงไฟล์พร้อม start time, end time, duration

### การแจ้งสถานะ Service (2026-09-12)
- **Start:** 🟢 Service Start notification
- **Restart:** 🔄 Service Restart notification (ตรวจจับผ่าน state file)
- **Stop:** 🔴 Service Stop notification
- **Fail:** ❌ Service Fail notification พร้อมรายละเอียด
- **Error:** ⚠️ Service Error notification พร้อมรายละเอียด
- ส่งผ่าน `systemd_wrapper.py` (ExecStartPre สำหรับ start, ExecStop สำหรับ stop)

### Plain Text Log (`/var/log/chk-a/alerts.log`)
```
YYYY-MM-DD HH:MM:SS hostname resolver ip event_type: fqdn
```

### Day Separators ที่เที่ยงคืนในทุกไฟล์ log

---

## การทดสอบและคุณภาพ

- **313/313 tests ผ่าน** บน **ทั้ง dev และ test VM** (นโยบาย zero-regression)
- **Test Location:** ทุกอย่างบน test VM (pytest, CLI, systemd, DNS/Telegram/MTR)
- **Fix Tests, Not Agent Code** — ตามกฎโครงการ
- **Code Review Patterns:** ตาม skill `software-development` → `code-review-patterns`

---

## สถานะความปลอดภัย (Security Status)

**Security Code Review เสร็จสิ้น:** 23 findings
- **2 Critical:** AlertAgent token bucket race (C-01) ✅ แก้แล้ว, AlertAgent dedup cache race (C-02) ✅ แก้แล้ว
- **5 High:** Orchestrator timezone-naive scheduler (H-01) ✅ แก้แล้ว, MTR timeout calc (H-02) ✅ แก้แล้ว, BaselineStore key caching (H-03) ✅ แก้แล้ว, TelegramClient memory (H-04) ✅ แก้แล้ว, Orchestrator batch writes (H-05) ✅ แก้แล้ว
- **8 Medium:** DoH support (M-01) ✅ แก้แล้ว, Consensus reputation (M-02) ✅ แก้แล้ว, MLAgent key collision (M-03) ✅ แก้แล้ว, Parallel MTR (M-04) ✅ แก้แล้ว, CircuitBreaker (M-05) ✅ แก้แล้ว, Health server consistency (M-06) ✅ แก้แล้ว, Thai font loading (M-07) ✅ แก้แล้ว, AlertAgent log rotation (M-08) ✅ แก้แล้ว
- **5 Low/Info:** SEC-010 (DoH/DoT) ✅ แก้แล้ว, SEC-011 (CAP_NET_RAW) ✅ แก้แล้ว, SEC-013 (log perms) ✅ แก้แล้ว, SEC-014 (HTML escape) ✅ แก้แล้ว (2026-09-17), SEC-015..SEC-020 ✅ แก้แล้ว

**แก้แล้ว (Security Regression Tests SEC-001..SEC-020):**
- SEC-001: เพิ่ม `_validate_target_ip()` ใน `mtr_agent.py` ใช้ `ipaddress.ip_address()`
- SEC-002: เพิ่ม path validation ใน `baseline_store.py` `__init__` และ `_is_path_allowed()`, dynamic `_get_allowed_base_dir()` จาก `CHK_A_BASELINE_DIR`
- SEC-003: Parse `/etc/chk-a/env` ตรงเข้า config model (ไม่ `os.environ` pollution); redact tokens ใน logs; ใช้ **token ใน URL path (ข้อกำหนดของ Telegram Bot API), masked ใน logs**
- SEC-004: เปลี่ยน `_health_bind_address()` เป็น instance method อ่านจาก validated config; loopback validation ใน `SchedulerConfig`; ลบ env-var bypass
- SEC-005: ลบ `email_use_tls` field; port-based TLS — port 465 ใช้ `SMTP_SSL`, port 587 ใช้ `SMTP` + `starttls()`
- SEC-006: Pydantic v2 validators ใน models — FQDN (RFC 1035/2181), resolver address (IP:port/hostname:port/DoH), expected IPs
- SEC-007: Telegram API calls ใช้ **token ใน URL path (ข้อกำหนดของ Telegram Bot API), masked ใน logs**
- SEC-008: LRU dedup cache พร้อม TTL และ max-size (OrderedDict, maxsize=10000, ttl_sec=3600)
- SEC-009: Log injection prevention ผ่าน `_sanitize_log_field()` (escape newlines, carriage returns, tabs)
- SEC-012: Hard concurrency ceiling — MTR semaphore (4), max_concurrent capped at 100, Telegram circuit breaker
- SEC-015: Baseline encryption at rest ผ่าน age/pyrage (public key ใน config, private key จาก env)
- SEC-016: Pinned dependencies พร้อม SHA-256 hashes (39 packages), CI with pip-audit
- SEC-017: Config perms `chmod 640`, env perms `chmod 600`, chown root:chk-a
- SEC-018: Telegram circuit breaker (CLOSED/OPEN/HALF_OPEN, threshold=5, recovery=60s)
- SEC-019: Daily report scheduler drift fix — absolute time scheduling with fixed reference point
- SEC-020: MTR/Resolver config sync validation — `mtr.resolvers` ต้องเป็น subset ของ `resolvers`
- Test infrastructure: `tests/conftest.py` กำหนด `CHK_A_BASELINE_DIR=/tmp`

### การแก้ไข Telegram Reporter (2026-09-13)
- **Root Cause:** `TelegramReporter` ใช้ `Authorization: Bearer *** header แต่ Telegram Bot API กำหนดให้ใช้ token ใน URL path (`/bot<token>/method`)
- **Impact:** รายงานรายวัน 06:00 น. ล้มเหลว 404 Not Found; รูปภาพเที่ยงคืนทำงานเพราะใช้ `TelegramClient` (token ใน URL)
- **Fix:** อัปเดต `TelegramReporter` ให้ใช้ token ใน URL path (เหมือนกับ `TelegramClient`)
- **Files Changed:** `src/chk_a/reporting/telegram_reporter.py`, `tests/test_security_regressions.py`
- **Circuit Breaker:** รีคัฟเวอร์อัตโนมัติหลัง 60 วินาที (HALF_OPEN → CLOSED)

### โครงสร้างพื้นฐานการ Deploy (2026-09-14)
- **สร้าง `scripts/deploy.sh`** — Deploy script มาตรฐานติดตั้ง source ที่ sync มาจาก `/home/ipds/Hermes-Prj/chk-a/` ไปยัง FHS runtime `/opt/chk-a/` บนเครื่องเป้าหมาย (test/prod)
- ใช้ `rsync -c` checksum verification และ restart systemd service
- รันด้วย `sudo` หลัง dev→test sync
- ยืนยัน hash ตรงกัน: Dev source `/home/ipds/Hermes-Prj/chk-a/` ↔ Runtime `/opt/chk-a/` (MD5: `b7717b974eab7b7d163300430e2fdf08`)
- แก้ config test VM `/etc/chk-a/config.yaml` — เพิ่ม `daily_report_*` settings ที่หายไป
- Service ทำงานด้วยโค้ดและ config ที่อัปเดตแล้ว

### รองรับ Rotated Logs และ Baseline Integrity Metrics (2026-09-15)
- **`_load_recent_checks()` อ่าน rotated logs อัตโนมัติ** — ไฟล์ date-stamped `.bz2` และ numbered `.gz` backups จาก log directory
- **แก้ไขการ parse timestamp mixed timezone** — รองรับทั้ง naive (real log) และ timezone-aware (mock data) ISO8601 ผ่าน `pd.to_datetime(format="mixed", utc=True).dt.tz_localize(None)`
- **Baseline-based integrity scoring** — ใช้ `MLAgent.score()` (total-variation distance ต่อ learned baseline) แทน Isolation Forest
- **เพิ่ม IP stability & diversity metrics** — คำนวณ `unique_ip_count` และ `ip_stability` สำหรับ baseline method (เดิมขาด เฉพาะ Isolation Forest เท่านั้น)
- **รายงานรายวัน (เมื่อวาน)** — 10,374 records จาก rotated log `checks.jsonl-20260914.bz2` → ส่ง Telegram สำเร็จ
- **รายงานรายเดือน (30 วัน)** — 53,588 records จากหลาย rotated files → สร้างกราฟสำเร็จ
- **Day 1 sample report (ข้อมูลเต็มที่มี)** — 53,588 records → ส่ง Telegram พร้อม 10 กราฟ
- **ตัวอย่างรายงาน 06:00 น. (ข้อมูลเมื่อวาน)** — ใช้ `reference_date=yesterday 23:59` → โหลดข้อมูลเมื่อวานถูกต้อง
- **Real-time daily report (เที่ยงคืนถึงตอนนี้)** — สร้าง script manual run, filter ข้อมูลวันนี้จาก current log

### ตรวจสอบรายงานวันที่วานขาดหายตอน Startup (2026-09-15)
- **Orchestrator ตรวจสอบรายงานวันที่วานขาดหายตอนเริ่ม service** — เรียก `_send_missing_daily_report()` หลัง init tasks
- ตรวจสอบ `output_dir` หาโฟลเดอร์รายงานวันที่วาน; ถ้าไม่มี สร้างและส่งอัตโนมัติ
- ใช้ `reference_date=yesterday 23:59:59` เพื่อ target ข้อมูล rotated log ของเมื่อวานได้ถูกต้อง
- ส่ง Telegram ด้วยรูปแบบเหมือนรายงาน 06:00 น. ที่กำหนด (ภาษาไทย, emoji, protected palette, hostname, timestamp)

### GitHub Release และ Production Installer (2026-09-16)
- **GitHub Actions Release Workflow** — `.github/workflows/release.yml` build wheel เมื่อ push tag (v*), สร้าง GitHub Release พร้อม assets
- **Production Installer (`install.sh`)** — ดาวน์โหลด wheel + assets จาก GitHub Releases, สร้าง venv, ติดตั้ง wheel, config systemd, logrotate
- **Uninstaller (`uninstall.sh`)** — ลบทุกอย่างของ service, configs, logs, state, user
- **Makefile** — Targets: `install`, `install-github`, `uninstall`, `upgrade`, `status`, `logs`, `version`, `release-dry-run`
- **v1.0.0 released** (2026-09-16) — 10 assets: wheel, install.sh, uninstall.sh, Makefile, config.yaml.example, env.example, chk-a.service, logrotate.chk-a
- **v1.0.1 released** (2026-09-16) — แก้ wheel filename resolution ผ่าน GitHub API, เพิ่ม pip installation fallback
- **v1.0.2 released** (2026-09-16) — ปรับปรุง pip installation: `ensurepip` พร้อม log output, fallback `get-pip.py`, verification พร้อม log version

### Install.sh Fixes (2026-09-17)
- **v1.0.3** — Fix install.sh venv reuse bug (added pip verification, improved logging)
- **v1.0.4** — Fix env permission to 0640 so service can read Telegram credentials
- **v1.0.5** — Ensure env.example is present and not empty after download
- **v1.0.6** — Fix env file permissions (0640) so service can read credentials
- **v1.0.7** — Ensure env.example is present and not empty after download
- **v1.0.8** — Move env.example check to /tmp, remove silent failures, add verification step
- **v1.0.9** — Fix wheel download for "latest" (correct GitHub API endpoint), add timeouts/progress bars
- **v1.0.10** — Use dedicated temp dir (mktemp) for downloads, remove existing files before download
- **v1.0.11** — Change default reporting.output_dir to /var/lib/chk-a/reports to fix read-only filesystem error
- **v1.0.12** — Fix HTML parsing in Telegram messages (remove auto-escape from TelegramClient, add proper escaping in callers)
- **v1.0.13** — Support Python 3.10+ (Ubuntu 22.04 LTS), add backports.zoneinfo dependency
- **v1.0.14** — Add manual daily/monthly report scripts for on-demand reporting

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

---

## v1.0.15 Release (2026-09-18)

### แก้ไข (Fixed)
- **2026-09-18 21:00:00** — `src/chk_a/reporting/monthly_report.py` — แก้: Daily report time range bug. เปลี่ยนจาก `datetime.now().replace(hour=23, minute=59) - timedelta(days=1)` (ซึ่งให้เวลาผิดตอนรัน 06:00) เป็น `yesterday = datetime.now() - timedelta(days=1); yesterday_end = yesterday.replace(hour=23, minute=59)` เพื่อให้ได้เวลา 23:59:59 ของเมื่อวานถูกต้อง
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — แก้: Daily midnight task (00:00) error handling สำหรับภาพหาย. เพิ่ม fallback ใช้ anomaly/recovery images จาก AlertAgent, logging รายละเอียดเมื่อภาพหาย, และ skip gracefully

### เพิ่ม (Added)
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — เพิ่ม: Copy `img/` directory ไปเป็น release assets และสร้าง `img.tar.gz` สำหรับการติดตั้ง production
- **2026-09-18 21:00:00** — `install.sh` — เพิ่ม: ดาวน์โหลดและ extract `img.tar.gz` ไป `/opt/chk-a/img/` ระหว่างติดตั้ง production
- **2026-09-18 21:00:00** — `config/config.yaml.example` — เพิ่ม: ตัวอย่าง config ครบทุก section (fqdns, resolvers, resolver_agent, ml, alert, scheduler, logging, mtr, reporting, baseline_store_path) พร้อมคำอธิบายไทยทุก setting
- **2026-09-18 21:00:00** — `config/chk-a.env.example` — เพิ่ม: ตัวอย่าง environment ครบ พร้อม placeholder สำหรับ Telegram, SMTP, และ Age encryption keys

### เปลี่ยนแปลง (Changed)
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — เปลี่ยน: ปรับปรุง daily midnight task logging และ fallback logic สำหรับ daily/anomaly/recovery images
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — เปลี่ยน: ใช้ `config/config.yaml.example` ใหม่ครบถ้วนใน release assets แทน `config/chk-a.config.yaml.example` เก่า

### การ Deploy Production v1.0.15 (2026-09-18)
- ✅ **สร้าง Release v1.0.15** — GitHub Release พร้อม assets ครบ รวมถึง `img.tar.gz`
- ✅ **Production `uptime-host` ติดตั้ง v1.0.15 แล้ว** — โฟลเดอร์ `img/` ถูก deploy ไป `/opt/chk-a/img/`
- ✅ **Production config อัปเดตแล้ว** — เพิ่ม `reporting` section, `mtr` section, `daily_image_path`, `resolver_agent: {}`
- ✅ **00:00 Daily image ทำงานยืนยันแล้ว** — ได้รับข้อความ Telegram พร้อม `sleepy.jpg` + hostname + day separators
- ✅ **06:00 Daily report รอตรวจสอบ** — รอบถัดไปที่กำหนด

---

## v1.0.16 Release (2026-09-19)
- ✅ Telegram sequential send + Thai-only graphs

## v1.0.17 Release (2026-09-19)
- ✅ Latency boxplot sort by median ASC (fastest on top)

## v1.0.18 Release (2026-09-19)
- ✅ Timezone fix for daily reports + robust Thai filtering

## v1.0.19 Release (2026-09-19)
- ✅ Graph filename suffix for Thai filtering + consistent daily reports

## v1.0.20 Release (2026-09-19)
- ✅ Timezone fix for daily reports + robust Thai filtering

## v1.0.21 Release (2026-09-19)
- ✅ Debug logging for daily reports + robust Thai filtering

## v1.0.22 Release (2026-09-20)
- ✅ Manual daily report fixes: Thai-only filter, latency boxplot sort, daily heatmap month context

## v1.0.23 Release (2026-09-20)
- ✅ Service startup report fix: Thai-only, today data 00:00-now, daily heatmap month context, background task

## v1.0.24 Release (2026-09-20)
- ✅ Fix pyproject.toml version to 1.0.24 (was 1.0.14) — ensures wheel builds with correct version

## v1.0.25 Release (2026-09-20 17:30:00)
- ✅ Missing daily report on startup now merges month data (Sep 1 to yesterday) for daily availability heatmap
- ✅ Daily heatmap title format: "Days 1 to N" (EN) / "วันที่ 1 ถึง N" (TH) — clearer than "Month: 1st to DD MMM"
- ✅ Month start fix: Both missing & today reports use `month_start = day 1`

---

## v1.0.26 Release (2026-09-21 06:30:00)
- ✅ Scheduled daily report (06:00 AM) merge month data (1st to yesterday) for daily availability heatmap, สอดคล้องกับ startup report behavior

---

## v1.0.27 Release (2026-09-21 08:00:00)
- ✅ แสดง version ทั่วทุกรายงาน:
  - กราฟ: Version ใน footer กลาง (`vX.Y.Z`) ผ่าน `_add_header_footer()` ใน `graph_generator.py`
  - Telegram Monthly Summary: Version ท้ายข้อความผ่าน `create_telegram_summary()` ใน `telegram_reporter.py`
  - Telegram Daily Summary: Version ท้ายข้อความผ่าน `create_daily_telegram_summary()` ใน `telegram_reporter.py`
  - Dashboard/Reports: Version ส่งผ่าน `generate_summary_dashboard()` ไป 8 chart types ทั้งหมด

---

## v1.0.28 Release (2026-09-21 10:30:00)
- ✅ Version detection ทำงานทั้งตอนติดตั้งเป็น package และรันเป็น module (`-m chk_a.main`). เพิ่ม fallback อ่านจาก `pyproject.toml`
- ✅ CLI commands `test-telegram` และ `test-daily-image` extract secret values จาก `SecretStr` ก่อนส่งให้ `TelegramClient`, แก้ "Object of type SecretStr is not JSON serializable" error

---

## v1.0.29 Release (2026-09-21 15:30:00)
- ✅ MTR CLI target validation auto-appends `:53` สำหรับ bare IP/hostname, ให้ CLI รับ bare IP/hostname เป็น target argument ได้โดยไม่ต้องระบุ port เอง
- ✅ Test VM Python cache issue แก้แล้ว: ลบ `.pyc` cache เพื่อ serve updated `__version__` (1.0.29)

---

## v1.0.30 Release (2026-09-22 14:45:00)
- ✅ **SEC-010**: DoH/DoT resolver support tests เพิ่ม — `test_doh_resolver_resolves()` mocking aiohttp DoH query with DNS wireformat response
- ✅ **SEC-011**: CAP_NET_RAW for MTR ICMP tests เพิ่ม — `TestSEC011_MTRCapNetRaw` class 3 tests verify systemd CAP_NET_RAW capability, MTRConfig ICMP mode support, MTRAgent ICMP privileges
- ✅ **Log Rotation Tests**: Comprehensive tests สำหรับ `_load_recent_checks()` ครอบคลุม plain JSONL, date-stamped `.bz2`, numbered `.gz`, mixed timezone timestamps, fractional lookback, malformed lines, non-CheckResult log lines, empty/nonexistent files, edge cases (18 tests)
- ✅ แก้: `_load_recent_checks()` timestamp parsing สำหรับ mixed naive และ timezone-aware timestamps, preserve local time (Asia/Bangkok) สำหรับ naive timestamps ขณะแปลง aware timestamps ไป Asia/Bangkok
- ✅ แก้: 13 test functions แทนที่ `tmp_path` pytest fixture ด้วย `_make_temp_path()` helper จาก conftest.py เพื่อ baseline path consistency

---

## v1.0.31 Release (2026-09-22 15:30:00)
- ✅ **Email Reporting Tests**: Comprehensive tests สำหรับ EmailSender class (12 tests) ครอบคลุม STARTTLS/implicit TLS, auth/no-auth, missing attachments, exception handling, create_email_body() function (English/Thai languages, missing summary), MonthlyReportGenerator integration

---

## v1.0.32 Release (2026-09-22 16:00:00)
- ✅ **FQDN-centric Data Model**: เพิ่ม `FQDNRecord` และ `FQDNStore` พร้อม identity (fqdn, domain, subdomain, apex), DNS records (current IPs, CNAME chain, TTL), history (IP changes with timestamps/sources), metadata (registrar, expiry, NS), monitoring state (last_checked, status, failures), alerting rules, ML features (baseline IPs, anomaly score, flip-flop count, geo shifts)
- ✅ **FQDN Store Tests**: 25 comprehensive tests ครอบคลุม creation, domain extraction, IP change history, monitoring state transitions, baseline/anomaly updates, serialization, persistence, queries (by domain, status, anomaly, recent changes), path traversal protection, corrupt/empty file handling

---

## v1.0.33 Release (2026-09-22 16:30:00)
- ✅ **Startup Report Heatmap Fix**: แก้ `_send_today_report_on_startup()` ให้ใช้ `reference_date=now` แทน `today_end`, ให้ fractional lookback ครอบคลุม 00:00 ถึงเวลาปัจจุบันถูกต้อง (ไม่ใช่ 09:30-14:30)
- ✅ **Version Bump**: Source files แสดง 1.0.33 ถูกต้อง (เคยเป็น 1.0.32 ใน pyproject.toml และ main.py)
- ✅ Python cache cleared และ package reinstall สำหรับ `__version__` detection ที่ถูกต้อง

---

## v1.0.34 Release (2026-09-22 16:30:00)
- ✅ **Modern Graph Styling**: Overhaul `graph_generator.py` เต็มรูปแบบ พร้อม colorblind-safe palette (viridis heatmap, semantic colors), clean aesthetics (ไม่มี top/right spines, subtle grid), DPI สูงขึ้น (200), colorblind-safe categorical palette (seaborn colorblind), ปรับปรุง Thai font (bold weight, adjusted sizes). Footer version สี primary blue
- ✅ **Alert/Recovery Version Footer**: เพิ่ม version footer ใน Telegram alert และ recovery messages (`🏷️ <b>chk-a v1.0.34</b>`)
- ✅ **Test VM Sync**: Sync source files ทั้งหมดไป test VM ผ่าน rsync, 313/313 tests ผ่านบน test VM
- ✅ **Production Ready**: GitHub Release v1.0.34 published พร้อม assets ทั้งหมด

---

## AI Model Config (สำหรับ cyber-security-review)

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

## หมายเหตุการดำเนินงาน (Operational Notes)

- **SSH:** Dev→Test passwordless (`ipds@192.168.56.122`), reverse NOT possible
- **Logs:** `journalctl -u chk-a-resolver -f` (และ consensus, alert, mtr)
- **Config Change:** แก้ `/etc/chk-a/config.yaml` → `sudo systemctl restart chk-a-*`
- **MTR Resolvers List** ใน config แยกจาก `resolvers` list — ต้อง sync เอง
- **GitHub:** HTTPS with PAT (ไม่มี SSH บน WSL)
- **Service Status Notification:** `systemd_wrapper.py` เรียกผ่าน ExecStartPre (start) และ ExecStop (stop) ใน `systemd/chk-a.service`; state file ที่ `/opt/chk-a/last_state.txt`
- **State File Permission:** ต้องรัน `sudo chown ipds:ipds /opt/chk-a/last_state.txt` หลังสร้างครั้งแรก
- **Time Convention:** ทุก timestamp ใช้เวลาท้องถิ่น Asia/Bangkok (+07); `datetime.now()` ทั่วทั้งโค้ด, ไม่มี `datetime.utcnow()` ที่ไหนเลย
- **Standard Deploy Workflow:**
  1. Dev: แก้โค้ดที่ `/home/ipds/Hermes-Prj/chk-a/`
  2. Dev: `rsync -avz -c /home/ipds/Hermes-Prj/chk-a/ ipds@192.168.56.122:/home/ipds/Hermes-Prj/chk-a/`
  3. Test VM: `sudo /home/ipds/Hermes-Prj/chk-a/scripts/deploy.sh`
- **Production Install Workflow:**
  1. `curl -L -o install.sh https://github.com/tpdevices/chk-a/releases/download/v1.0.34/install.sh`
  2. `chmod +x install.sh`
  3. `sudo ./install.sh v1.0.34`
  4. แก้ `/etc/chk-a/env` ใส่ Telegram credentials
  5. แก้ `/etc/chk-a/config.yaml` ใส่ FQDNs/resolvers
  6. `sudo systemctl restart chk-a`

---

*Created by Hermes Agent session on 2026-09-22 15:40:32 (Asia/Bangkok UTC+07)*