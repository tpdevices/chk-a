# chk-a — รายงานสถานะ

**อัปเดตล่าสุด:** 2026-08-31T15:40:00+07:00 (2026-08-31 08:40:00 UTC)
**โครงการ:** chk-a — ตัวเฝ้าระวังการเปลี่ยนแปลง DNS A-record แบบอัตโนมัติ
**ตำแหน่ง:** /home/ipds/Hermes-Prj/chk-a

---

## 1. ภาพรวมโครงการ (Project Overview)

chk-a คือตัวเฝ้าระวังการเปลี่ยนแปลง DNS A-record แบบอัตโนมัติ ติดตามชุด FQDN ที่กำหนด
แก้ไข A-record ผ่าน DNS resolver หลายตัวที่ตั้งค่าได้ สร้าง baseline ด้วย machine learning
(ชุด IP ปกติ) ตรวจจับความผิดปกติ (IP เปลี่ยนจากที่เรียนรู้ หรือต่างจาก consensus ของ resolver
กลุ่มใหญ่) และแจ้งเตือนทาง Telegram ทำงานเป็น systemd service บน Ubuntu 24.04 LTS ขึ้นไป
รอบการตรวจสอบสุ่มไม่เกิน 3 นาที

ข้อจำกัดสำคัญจากผู้ใช้:
- สถาปัตยกรรมแบบ multi-agent (Resolver → Consensus → ML → Alert → Orchestrator)
- **ห้ามใช้ Prometheus หรือโปรแกรม monitor อื่นใด** (ลบออกทั้งหมดอย่างเข้มงวด)
- ไม่ใช้ ML dependency หนัก (ใช้ custom EMA + entropy; ไม่มี torch/sklearn/river/redis/prometheus_client)
- ใช้ค่า hash ตรวจสอบว่าเป็นไฟล์เดียวกัน
- สื่อสารภาษาไทย; บุคลิก "น้องน้ำฟ้า"
- Model provider: nvidia
- เครื่อง dev: Ubuntu บน WSL เครือข่าย 172.20.14.199/20

## 2. สถาปัตยกรรม (Architecture)

```
Orchestrator (loop หลัก, jitter 30–180 วินาที, /healthz, sd_notify watchdog)
   │
   ├─ ResolverAgent   check_fqdn(fqdn) -> list[CheckResult]   (ต่อ resolver)
   ├─ ConsensusAgent  aggregate(fqdn, results, min_consensus) -> ConsensusResult
   ├─ MLAgent         learn(consensus) / score(ips, fqdn) -> float / get_baseline
   │                   (BaselineStore: JSON แบบ atomic; คง sample_count / all_fqdns ไว้)
   ├─ AlertAgent      maybe_alert(event) -> bool  (async)
   │     └─ TelegramClient  send_message(chat_id, text)  (aiohttp + tenacity 3 รอบ)
   └─ structured JSON log พร้อม correlation_id (uuid4 ต่อรอบ)
```

โครงสร้าง source (`src/chk_a/`):
- `orchestrator.py` — loop, jitter, `/healthz`, watchdog (ไม่มี `/metrics`)
- `agents/resolver_agent.py` — แก้ไข DNS ต่อ resolver
- `agents/consensus_agent.py` — รวมเสียงข้างมาก/consensus
- `agents/ml_agent.py` — EMA baseline + entropy scoring
- `agents/alert_agent.py` — ตัดสินใจเมื่อใดควรแจ้งเตือน
- `storage/baseline_store.py` — JSON baseline store แบบ atomic
- `utils/telegram_client.py` — ส่งข้อความผ่าน Telegram Bot API
- `utils/systemd_notify.py` — sd_notify (ปลอดภัยเมื่อไม่อยู่ใต้ systemd)
- `utils/context.py` — correlation_id
- `utils/logger.py` — structured JSON logger
- `config/loader.py` — AppConfig (fqdns, resolvers, ml, alert, scheduler, logging, baseline_store_path, hostname)
- `models/schemas.py` — Pydantic v2 models (ลบ MetricsConfig แล้ว)
- `main.py` — CLI: `validate-config | check-once | show-baseline | test-telegram | test-daily-image`

## 3. สิ่งที่ทำเสร็จแล้ว

- **Loop 0–7**: ระบบ multi-agent ครบ + ชุดเทสต์ (79 passed)
- **ลบระบบ metrics/Prometheus ทั้งหมด** อย่างเข้มงวดตาม "ไม่ใช้ prometheus หรือ program monitor อื่น ๆ":
  - ลบ `src/chk_a/utils/metrics.py` (custom Prometheus renderer)
  - ลบ `MetricsConfig` จาก `schemas.py`, `loader.py`, และ config 3 ไฟล์
  - ลบ `/metrics` endpoint จาก `orchestrator.py` (เหลือเฉพาะ `/healthz`)
  - ลบเทสต์ metrics จาก `test_loop7.py`
  - อัปเดต README/ARCHITECTURE/RUNBOOK/CONTRIBUTING/`md/loop_engineering_prompt.md`
  - คง `sample_count()`/`all_fqdns()` ไว้ (ผู้เรียกจริง: CLI `show-baseline` + `_load_state`)
- **แก้ lint/build**: สร้าง `.flake8` (max-line-length=100), ลบ `[tool.flake8]` ออกจาก `pyproject.toml`
- **ทดสอบจริงบนเครื่อง — ส่วน A (ไม่ต้อง sudo)**:
  - `validate-config` OK; `check-once` รันรอบจริงเทียบ DNS จริง; `show-baseline` แสดง baseline ที่เรียนรู้
  - daemon loop: `/healthz` → `{"status":"ok","shutdown":false}`; รอบรันด้วย correlation_id; เรียนรู้ baseline; SIGTERM → ปิดสะอาด ("Shutdown requested"); baseline บันทึกเป็น JSON ถูกต้อง
  - `pip install -e .` สำเร็จ; ติดตั้ง console script `chk-a`
  - `test-telegram` แบบไม่มี token จัดการอย่างสวยงาม (return 1, แจ้งเตือน, ไม่ crash)
  - `systemd-analyze verify chk-a.service` → ไม่มี error ไวยากรณ์
  - `pytest` → **79 passed** (เขียว)
- **สร้าง `uninstall.sh`** + ทดสอบ sandbox (ลบตรงกับที่ `install.sh` สร้าง; ไม่แตะ source)
- **ยืนยันรองรับ Telegram Channel** (ไม่ต้องแก้โค้ด; ใช้ `chat_id`)
- **ติดตั้ง systemd จริงบนเครื่องปลายทาง (test-chk-a VM)**: `sudo ./install.sh` + `sudo systemctl start chk-a` — **เสร็จแล้ว**
- **ตั้งค่า Telegram credentials จริง** — `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` ใน `/etc/chk-a/env` — **เสร็จแล้ว**
- **ปรับปรุงรูปแบบแจ้งเตือน Telegram (Majority vs Outliers view)**:
  - เพิ่ม emoji ความรุนแรง: 🔴 CRITICAL / 🟡 WARNING / 🔵 INFO
  - เพิ่มป้ายประเภท: 📊 Baseline Deviation / 🗳️ Consensus Deviation / 🆕 New IP Detected / 🚫 NXDOMAIN
  - เพิ่มการจัดกลุ่ม Majority vs Outliers ในข้อความแจ้งเตือน
  - Hostname แสดงชื่อเครื่อง monitor (เช่น `test-chk-a`) ไใช่ FQDN
  - แสดงชื่อ resolver ที่ตรวจพบ
  - Observed IPs แสดง "timeout (no response)" เมื่อว่างเปล่า
- **Plain text alert log**: `YYYY-MM-DD HH:MM:SS hostname resolver ip event_type: FQDN`
- **ส่งภาพ Telegram ทุกเที่ยงคืน** พร้อม hostname ใน caption: `🖥️ Host: test-chk-a`
- **Day separators** ในไฟล์ log ทุกเที่ยงคืน: `=== DAY SEPARATOR: YYYY-MM-DD ===`
- **Config schema**: เพิ่มฟิลด์ `hostname` ใน `AppConfig` ค่าเริ่มต้น `socket.gethostname()`

## 4. สิ่งที่กำลังทำอยู่

- ไม่มี — ฟีเจอร์ที่วางแผนเสร็จสิ้นและทดสอบแล้ว

## 5. ปัญหาที่พบ

- **sudo ต้องรหัสผ่านโต้ตอบ**: agent พิมพ์ให้ไม่ได้ → การติดตั้ง/ถอนการติดตั้งบนเครื่องจริงค้างอยู่; จึงเตรียมบล็อกคำสั่ง copy-paste แทน
- **Telegram เป็น placeholder**: แจ้งเตือน/`test-telegram` ส่งไม่ได้จนกว่าจะได้ token + channel chat_id จริง (แก้แล้วบน test-chk-a)
- **flake8 7.3.0**: ไม่โหลด `[tool.flake8]` จาก `pyproject.toml` หากไม่มี `tomli` ติดตั้ง → ต้องใช้ `.flake8` แยกต่างหาก
- **reference models ให้ข้อมูลผิด (บทเรียน)**: ในเซสชันนี้ nemotron/laguna เดาว่า "WSL ไม่มี systemd" (ผิด — `systemctl is-system-running` = `running`, systemd เป็น PID 1); gpt-oss อธิบายว่าติดตั้งสร้าง symlink `/usr/local/bin` (ผิด — ใช้ `pip install -e` เข้า `/opt/chk-a/.venv`) ต้องยืนยันกับ terminal จริงและเนื้อหาไฟล์จริงเสมอ ไม่เชื่อคำเดาของโมเดล
- **Dev vs Test VM sync**: การแก้ไขบน test VM ต้อง sync กลับ dev (WSL) — เกือบสูญเสียการเปลี่ยนแปลงเพราะสับสน

## 6. งานที่ต้องทำต่อ

- ติดตามความเสถียรของ service บน test-chk-a
- พิจารณาเพิ่ม persistent dedup cache (อยู่รอด restart) สำหรับ AlertAgent
- ทางเลือก: การแสดงเส้นทาง traceroute ฝั่ง server สำหรับการศึกษา client→resolver

## 7. รายการไฟล์ที่เกี่ยวข้อง

| ไฟล์ | หน้าที่ |
|------|---------|
| `src/chk_a/orchestrator.py` | loop หลัก, `/healthz`, watchdog, daily tasks |
| `src/chk_a/agents/*.py` | Resolver, Consensus, ML, Alert agents |
| `src/chk_a/storage/baseline_store.py` | JSON baseline store แบบ atomic |
| `src/chk_a/utils/telegram_client.py` | ตัวส่ง Telegram |
| `src/chk_a/utils/systemd_notify.py` | ตัวช่วย sd_notify |
| `src/chk_a/utils/context.py`, `logger.py` | correlation_id + structured log |
| `src/chk_a/config/loader.py`, `models/schemas.py` | Config + Pydantic models |
| `src/chk_a/main.py` | จุดเริ่ม CLI |
| `config/settings.yaml`, `*.example` | ตัวอย่าง config (ลบ metrics แล้ว) |
| `install.sh` / `uninstall.sh` | ติดตั้ง / ถอนการติดตั้งบนเครื่องปลายทาง |
| `systemd/chk-a.service`, `logrotate.d/chk-a` | systemd unit + logrotate |
| `Makefile`, `pyproject.toml`, `.flake8` | ตั้งค่า build/lint/test |
| `md/loop_engineering_prompt.md` | สเปก loop-engineering **ที่เป็นบรรทัดฐาน** |
| `tests/test_loop7.py` | เทสต์ correlation_id + CLI |

## 8. TODO List

ดู `TODO.md` สำหรับรายการที่ทำได้จริง (checkbox + timestamp)