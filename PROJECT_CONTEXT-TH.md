# chk-a — บริบทโครงการ

**อัปเดตล่าสุด:** 2026-08-31T15:40:00+07:00 (2026-08-31 08:40:00 UTC)
**โครงการ:** chk-a — ตัวเฝ้าระวังการเปลี่ยนแปลง DNS A-record แบบอัตโนมัติ
**ตำแหน่ง:** /home/ipds/Hermes-Prj/chk-a

ไฟล์นี้รวบรวมบริบทที่คงทนสำหรับเซสชันทำงานในอนาคตบน chk-a

---

## 1. ภาพรวมโครงการ

chk-a เฝ้าระวัง DNS A-record ของ FQDN ที่ตั้งค่าไว้ผ่าน resolver หลายตัว เรียนรู้ baseline
ของชุด IP ปกติด้วยโมเดล ML เบาๆ (EMA + entropy) ตรวจจับความผิดปกติ และแจ้งเตือนทาง Telegram
ทำงานเป็น systemd service บน Ubuntu 24.04 LTS ขึ้นไป รอบสุ่มไม่เกิน 3 นาที ไม่ใช้ external
monitoring (Prometheus/metrics) — มีแค่ `correlation_id` สำหรับติดตามและ `/healthz` สุขภาพ

## 2. สถาปัตยกรรม

ท่อประทานแบบ multi-agent โดย `orchestrator.py`:
Resolver → Consensus → ML (BaselineStore) → Alert (TelegramClient) → Orchestrator
ดูโครงสร้างเต็มใน `STATUS-TH.md` §2 สเปกการออกแบบที่เป็นบรรทัดฐานอยู่ที่
`md/loop_engineering_prompt.md` (Loop 0–7)

## 3. ข้อตกลงและกฎเหล็ก (จากผู้ใช้)

- **ห้าม Prometheus / ห้ามโปรแกรม monitor อื่น** — เข้มงวด มีได้แค่ `correlation_id` (structured
  JSON log) และ `/healthz` (systemd health check) ห้ามมี metrics endpoint / gauge / scrape port
- **ห้าม ML deps หนัก** — ใช้แค่ custom EMA + entropy ไม่มี torch/sklearn/river/redis/prometheus_client/python-systemd
- **`md/loop_engineering_prompt.md` เป็นบรรทัดฐาน** เหนือ reference models และสเปกที่อนุมาน เมื่อเทสต์
  ล้มเหลวเพราะตีความสเปกต่างกัน ให้**แก้เทสต์ให้ตรงกับ md spec ไม่ใช่แก้ agent code** — เว้นแต่ agent
  จะพัง caller ที่ใช้จริง
- สื่อสารภาษาไทย; บุคลิก "น้องน้ำฟ้า" Model provider: nvidia
- ไฟล์โปรเจกต์ทั้งหมดอยู่ใต้โฟลเดอร์โปรเจกต์เท่านั้น

## 4. สภาพแวดล้อม

- OS: Ubuntu (dev คือ 26.04 บน WSL; เป้าหมาย 24.04 LTS ขึ้นไป) **systemd รันเป็น PID 1** บนกล่อง WSL นี้
  (`systemctl is-system-running` = `running`)
- Python 3.14.4; venv ที่ `venv/` มี pydantic 2.13.5, dnspython, aiohttp, tenacity, pyyaml,
  pydantic-settings, build/black/flake8 (dev)
- เครือข่าย dev: 172.20.14.199/20
- ไม่ใช่ git repository (ยังไม่มี commit)
- เครื่องเป้าหมาย: test-chk-a (Ubuntu 26.04), SSH ผ่าน IP, service ติดตั้งที่ `/opt/chk-a`

## 5. วิธีรัน / ทดสอบ

```bash
source venv/bin/activate
export PYTHONPATH=src
export CHK_A_CONFIG=/path/to/config.yaml   # พาธ log/state ต้องเขียนได้

python -m chk_a.main validate-config
python -m chk_a.main check-once             # รอบจริงหนึ่งรอบ
python -m chk_a.main show-baseline
python -m chk_a.main test-telegram
python -m chk_a.main test-daily-image

# daemon loop (ไม่ต้อง sudo), probe สุขภาพ, แล้ว SIGTERM:
export CHK_A_HEALTH_PORT=8080 CHK_A_WATCHDOG_INTERVAL=0
python -m chk_a.main &
curl -s http://127.0.0.1:8080/healthz
kill -TERM <pid>
```

เกณฑ์คุณภาพ: `pytest -q` (เป้าหมาย 79 passed), `make build`, `make lint` (ใช้ `.flake8`)

## 6. ติดตั้ง / ถอนการติดตั้งบนเครื่องปลายทาง

`install.sh` สร้าง: `/opt/chk-a` (โค้ด+venv ผ่าน `pip install -e`), `/etc/chk-a/` (config + env secrets),
`/var/lib/chk-a` (state), `/var/log/chk-a` (logs), `/etc/systemd/system/chk-a.service`,
`/etc/logrotate.d/chk-a` `uninstall.sh` ลบตรงกับที่สร้าง (ไม่แตะ source checkout) ทั้งคู่ต้อง sudo

บน test-chk-a: service รันอยู่, Telegram alerts ทำงาน, daily image พร้อม hostname ส่งทุกเที่ยงคืน

## 7. ข้อควรระวัง (ที่ได้มาจากประสบการณ์)

- **ยืนยัน อย่าเชื่อคำเดาของโมเดล** reference models เคยเดาว่า WSL ไม่มี systemd และติดตั้งสร้าง symlink — ทั้งคู่ผิด
  ตรวจสอบ terminal จริง/ไฟล์จริงเสมอ
- **flake8 7.3.0** ไม่โหลด `[tool.flake8]` ใน pyproject หากไม่มี `tomli` → ใช้ `.flake8`
- **sudo** ต้องรหัสผ่านโต้ตอบที่ agent พิมพ์ไม่ได้ → เตรียมบล็อกคำสั่ง copy-paste
- **Telegram Channel** ใช้ได้โดยไม่แก้โค้ด: ตั้ง `TELEGRAM_CHAT_ID` เป็น `@channel` หรือ `-100xxxxxxxxxx`;
  บอทต้องเป็น Admin ที่มีสิทธิ์ Post Messages
- **Dev vs Test VM sync**: การแก้ไขบน test VM ต้อง sync กลับ dev (WSL) — เกือบสูญเสียการเปลี่ยนแปลงเพราะสับสน ต้อง rsync จาก dev ไป test เสมอ แล้ว sync กลับการแก้ไขบน VM

## 8. TODO / งานค้าง

ดู `TODO.md` รายการสำคัญ: persistent dedup cache สำหรับ AlertAgent, การแสดงเส้นทาง traceroute ฝั่ง server