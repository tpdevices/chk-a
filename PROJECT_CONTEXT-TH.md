# บริบทโครงการ chk-a

**อัปเดตล่าสุด:** 2026-09-15 14:30:00 (Asia/Bangkok UTC+07)

---

## ภาพรวมโครงการ

**chk-a** เป็นระบบตรวจสอบความผิดปกติของ DNS A-record แบบ Multi-Agent เขียนด้วย Python ระบบจะสอบถาม DNS resolver หลายตัวพร้อมกันสำหรับ FQDN ที่กำหนด สร้างคะแนนเสียงถ่วงน้ำหนัก (Weighted Consensus) เรียนรู้ Baseline แบบ Online Exponential Decay ตรวจจับ Anomaly และส่ง Alert ผ่าน Telegram พร้อมรายงานรายวัน/รายเดือน (ภาษาไทย/อังกฤษ + กราฟ + PDF)

**ที่เก็บโค้ด:** `tpdevices/chk-a` (GitHub, HTTPS with PAT)
**พัฒนา:** WSL Ubuntu (172.20.14.199/20)
**เครื่องทดสอบ:** VirtualBox Ubuntu 24.04 ที่ 192.168.56.122 (user: ipds)
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

---

## การตั้งค่า (Configuration)

**หลัก:** `/etc/chk-a/config.yaml` (test VM)
**อ้างอิง:** `/opt/chk-a/config.example.yaml`

Section สำคัญ:
- `fqdns` — รายการ FQDN พร้อม `min_consensus` และ `expected_ips` (optional)
- `resolvers` — รายการ resolver endpoint (`name`, `address` เป็น `IP:port`, `weight`, `timeout_ms`)
- `ml` — `baseline_decay`, `anomaly_threshold`, `min_samples_before_alert`
- `alert` — Telegram credentials, dedup window, rate limit, log paths, daily image config, dedup cache path
- `scheduler` — `min_interval_sec` (30), `max_interval_sec` (180), `jitter`
- `mtr` — enabled flag, interval, max_hops, count, interval_ms, timeout_sec, mode (icmp/tcp/udp), resolvers list
- `reporting` — ตารางเวลารายเดือน/รายวัน, output dir, Telegram/email config, graph inclusion
- `baseline_store_path` — `/var/lib/chk-a/baselines.json`

**Secrets:** `/etc/chk-a/env` — เก็บ `TELEGRAM_BOT_TOKEN` และ `TELEGRAM_CHAT_ID` (test VM)

---

## รายละเอียดการรายงาน

### รายงานรายเดือน (วันที่ 1 ทุกเดือน, 06:00 น.)
- ML insights จาก lookback 30 วัน
- กราฟ 7 ประเภท × EN/TH = 14 กราฟ + 2 Dashboards = 16 ไฟล์
- PDF รายงาน (EN/TH) ผ่าน fpdf2
- Telegram: สรุปภาษาไทย + กราฟ (ส่งแบบ batch, ครั้งละ 5 รูป)
- อีเมล: แนบ PDF เต็มรูปแบบ

### รายงานรายวัน (06:00 น., lookback 1 วัน)
- กราฟเหมือนกัน, หน้าต่างเวลา 1 วัน
- Telegram: สรุปภาษาไทย + กราฟ (ส่งแบบ batch)

### กราฟ (7 ประเภท)
1. Availability Bar (เปอร์เซ็นต์ availability ต่อ resolver)
2. Availability Heatmap (รายชั่วโมงต่อ resolver)
3. Integrity Score (ML-based ต่อ resolver)
4. Latency Boxplot (การกระจาย latency ต่อ resolver)
5. IP Stability & Diversity (ชุด IP ที่ไม่ซ้ำ, stability %)
6. MTR Path Visualization (hop loss/latency)
7. Path Availability (ML-based network path health)

### การแสดงผลภาษาไทย
กราฟทุกตัวเรียก `_apply_thai_fonts()` → translation map ครอบคลุมทุก label, footer แยกซ้าย/ขวา (hostname | timestamp), lang param ควบคุม TH/EN ไม่ซ้ำซ้อน

---

## รูปแบบ Telegram

### ข้อความ Alert (HTML)
- Severity emoji: 🔴 Critical / 🟡 Warning / 🔵 Info
- Type label: 📊 Baseline Deviation / 🗳️ Consensus Deviation / 🆕 New IP / 🚫 NXDOMAIN
- จับกลุ่ม Majority vs Outliers
- Resolver ที่ล้มเหลว แสดงแยก
- เปรียบเทียบ Baseline สำหรับ baseline_deviation
- Hostname, resolver names, timestamp (เวลาท้องถิ่น)

### การแจ้งเตือน Anomaly/Recovery (2026-09-09)
- **Event ID:** `{hostname}-YYYYMMDD-HHmmss` (ทั้ง anomaly และ recovery เพื่อ correlation)
- **Anomaly:** `img/priority.jpg` + สาเหตุ, last unreachable IP จาก MTR, consensus score
- **Recovery:** `img/ok.jpg` + ระยะเวลาความผิดปกติ (ชม./นาที/วินาที), ML baseline stability, recovery confidence
- ML logging ลงไฟล์พร้อม start time, end time, duration

### การแจ้งสถานะ Service (2026-09-12)
- **Start:** 🟢 การแจ้ง Service Start
- **Restart:** 🔄 การแจ้ง Service Restart (ตรวจจับผ่าน state file)
- **Stop:** 🔴 การแจ้ง Service Stop
- **Fail:** ❌ การแจ้ง Service Fail พร้อมรายละเอียด
- **Error:** ⚠️ การแจ้ง Service Error พร้อมรายละเอียด
- ส่งผ่าน `systemd_wrapper.py` (ExecStartPre สำหรับ start, ExecStop สำหรับ stop)

### Plain Text Log (`/var/log/chk-a/alerts.log`)
```
YYYY-MM-DD HH:MM:SS hostname resolver ip event_type: fqdn
```

### Day Separators ที่เที่ยงคืนในทุกไฟล์ log

---

## การทดสอบและคุณภาพ

- **251/251 tests ผ่าน** บน **ทั้ง dev และ test VM** (นโยบาย zero-regression)
- **สถานที่ทดสอบ:** ทุกอย่างบน test VM (pytest, CLI, systemd, DNS/Telegram/MTR)
- **แก้ test ไม่แก้ agent code** — ตามกติกาโครงการ
- **Code review patterns:** ตาม skill `software-development` → `code-review-patterns`

---

## สถานะความปลอดภัย (Security)

**Security Code Review ครบถ้วน:** 23 ข้อพบ
- **2 Critical:** AlertAgent token bucket race (C-01) ✅ แก้แล้ว, AlertAgent dedup cache race (C-02) ✅ แก้แล้ว
- **5 High:** Orchestrator timezone-naive scheduler (H-01) ✅ แก้แล้ว, MTR timeout calc (H-02) ✅ แก้แล้ว, BaselineStore key caching (H-03) ✅ แก้แล้ว, TelegramClient memory (H-04) ✅ แก้แล้ว, Orchestrator batch writes (H-05) ✅ แก้แล้ว
- **8 Medium:** DoH support (M-01) ✅ แก้แล้ว, Consensus reputation (M-02) ✅ แก้แล้ว, MLAgent key collision (M-03) ✅ แก้แล้ว, Parallel MTR (M-04) ✅ แก้แล้ว, CircuitBreaker (M-05) ✅ แก้แล้ว, Health server consistency (M-06) ✅ แก้แล้ว, Thai font loading (M-07) ✅ แก้แล้ว, AlertAgent log rotation (M-08) ✅ แก้แล้ว
- **5 Low/Info:** SEC-010 (DoH/DoT), SEC-011 (CAP_NET_RAW), SEC-013 (log perms), SEC-014 (HTML escape), SEC-015..SEC-020 ✅ แก้แล้ว

**แก้แล้ว (Security Regression Tests SEC-001..SEC-020):**
- SEC-001: เพิ่ม `_validate_target_ip()` ใน `mtr_agent.py` ผ่าน `ipaddress.ip_address()`
- SEC-002: เพิ่ม path validation ใน `baseline_store.py` `__init__` และ `_is_path_allowed()`, dynamic `_get_allowed_base_dir()` จาก `CHK_A_BASELINE_DIR`
- SEC-003: Parse `/etc/chk-a/env` เข้า config model โดยตรง (ไม่มลทิน `os.environ`); redact tokens ใน logs; **ใช้ token ใน URL path (ข้อกำหนดของ Telegram Bot API), masked ใน logs**
- SEC-004: เปลี่ยน `_health_bind_address()` เป็น instance method อ่านจาก validated config; loopback validation ใน `SchedulerConfig`; ลบ env-var bypass
- SEC-005: ลบ `email_use_tls` field; port-based TLS — port 465 ใช้ `SMTP_SSL`, port 587 ใช้ `SMTP` + `starttls()`
- SEC-006: Pydantic v2 validators ใน models — FQDN (RFC 1035/2181), resolver address (IP:port/hostname:port/DoH), expected IPs
- SEC-007: Telegram API calls ใช้ **token ใน URL path (ข้อกำหนดของ Telegram Bot API), masked ใน logs**
- SEC-008: LRU dedup cache พร้อม TTL และ max-size (OrderedDict, maxsize=10000, ttl_sec=3600)
- SEC-009: Log injection prevention ผ่าน `_sanitize_log_field()` (escapes newlines, carriage returns, tabs)
- SEC-012: Hard concurrency ceiling — MTR semaphore (4), max_concurrent capped at 100, Telegram circuit breaker
- SEC-015: Baseline encryption at rest ผ่าน age/pyrage (public key ใน config, private key จาก env)
- SEC-016: Pinned dependencies พร้อม SHA-256 hashes (39 packages), CI พร้อม pip-audit
- SEC-017: Config perms `chmod 640`, env perms `chmod 600`, chown root:chk-a
- SEC-018: Telegram circuit breaker (CLOSED/OPEN/HALF_OPEN, threshold=5, recovery=60s)
- SEC-019: Daily report scheduler drift fix — absolute time scheduling พร้อม fixed reference point
- SEC-020: MTR/Resolver config sync validation — `mtr.resolvers` ต้องเป็น subset ของ `resolvers`
- Test infrastructure: `tests/conftest.py` ตั้ง `CHK_A_BASELINE_DIR=/tmp`

### การแก้ไข Telegram Reporter (2026-09-13)
- **สาเหตุหลัก:** `TelegramReporter` ใช้ `Authorization: Bearer *** header แต่ Telegram Bot API กำหนดให้ใช้ token ใน URL path (`/bot<token>/method`)
- **ผลกระทบ:** รายงานรายวัน 06:00 น. ล้มเหลว 404 Not Found; รูปภาพเที่ยงคืนทำงานได้เพราะใช้ `TelegramClient` (token ใน URL)
- **การแก้ไข:** อัปเดต `TelegramReporter` ให้ใช้ token ใน URL path (เหมือนกับ `TelegramClient`)
- **ไฟล์ที่แก้:** `src/chk_a/reporting/telegram_reporter.py`, `tests/test_security_regressions.py`
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

---

## การตั้งค่า AI Model (สำหรับ cyber-security-review)

**Provider ที่มีอยู่:** NVIDIA (หลัก), 9router/OpenRouter/AnyAPI/Aihubmix (gateways), Ollama-Local, Poolside.AI

**Reference Models ที่แนะนำ:**
1. `nvidia/nemotron-3-ultra-550b-a55b` — Primary analyst (reasoning strength สูงสุด)
2. `poolside/laguna-s-2.1` — Code specialist (security code review)
3. `anthropic/claude-3.5-sonnet` — General analyst (balanced, context 200k)
4. `openai/gpt-4o` — Multimodal (diagrams, configs)
5. `qwen2.5-coder:7b` (Ollama-Local) — Local static analysis

**Aggregator ที่แนะนำ:**
1. `nvidia/nemotron-3-ultra-550b-a55b` — หลัก (evidence weighing, CVSS scoring)
2. `anthropic/claude-3.5-sonnet` — Fallback (calibrated judgment)

---

## หมายเหตุการดำเนินงาน

- **SSH:** Dev→Test passwordless (`ipds@192.168.56.122`), reverse ไม่ได้
- **Logs:** `journalctl -u chk-a-resolver -f` (และ consensus, alert, mtr)
- **เปลี่ยน Config:** แก้ `/etc/chk-a/config.yaml` → `sudo systemctl restart chk-a-*`
- **MTR Resolvers List** ใน config แยกต่างหาก — ต้อง sync เองกับ `resolvers` list
- **GitHub:** HTTPS with PAT (ไม่ใช้ SSH บน WSL)
- **การแจ้งสถานะ Service:** `systemd_wrapper.py` เรียกผ่าน ExecStartPre (start) และ ExecStop (stop) ใน `systemd/chk-a.service`; state file ที่ `/opt/chk-a/last_state.txt`
- **State File Permission:** ต้องรัน `sudo chown ipds:ipds /opt/chk-a/last_state.txt` หลังสร้างครั้งแรก
- **Time Convention:** ทุก timestamp ใช้เวลาท้องถิ่น Asia/Bangkok (+07); `datetime.now()` ทั่วทั้งโปรเจกต์, ไม่มี `datetime.utcnow()` ที่ไหนเลย
- **Standard Deploy Workflow:**
  1. Dev: แก้โค้ดใน `/home/ipds/Hermes-Prj/chk-a/`
  2. Dev: `rsync -avz -c /home/ipds/Hermes-Prj/chk-a/ ipds@192.168.56.122:/home/ipds/Hermes-Prj/chk-a/`
  3. Test VM: `sudo /home/ipds/Hermes-Prj/chk-a/scripts/deploy.sh`

---

*สร้างโดย Hermes Agent session วันที่ 2026-09-15 14:30:00*