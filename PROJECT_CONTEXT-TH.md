# บริบทโครงการ chk-a

**อัปเดตล่าสุด:** 2026-09-23 11:45:00 (Asia/Bangkok UTC+07)

---

## อัตลักษณ์โครงการ

**chk-a** — ระบบตรวจสอบความผิดปกติ DNS A-record แบบ Multi-Agent
- **Resolver** → **Consensus** → **ML** → **Alert** → **Orchestrator** + **MTR**
- ไม่ใช้ Prometheus/metrics, ไม่ใช้ heavy ML dependencies
- `md/loop_engineering_prompt.md` เป็นเอกสารกำหนด loop logic ที่ถูกต้อง
- แก้ tests, ไม่แก้ agent code — agent code เป็นสิ่งที่ต้องคุ้มครอง
- ฟอนต์ไทย (fonts-thai-tlwg/Loma) สำหรับทุกองค์ประกอบไทยในกราฟ
- Footer: ซ้าย=hostname | ขวา=timestamp (เวลาท้องถิ่น Asia/Bangkok +07)
- พารามิเตอร์ `lang` ควบคุม TH/EN — ไม่ทำซ้ำ
- Heatmap x-axis = ป้ายเวลาท้องถิ่น
- ฟังก์ชันวาดกราฟทุกตัว **ต้อง** เรียก `_apply_thai_fonts()`
- ประเภท Alert: 📊 baseline_deviation, 🗳️ consensus_deviation, 🆕 new_ip, 🚫 nxdomain
- Emoji ความรุนแรง: 🔴 CRITICAL, 🟡 WARNING, 🔵 INFO
- กลุ่ม Majority/Minority/Outlier ใน HTML alerts

---

## เวอร์ชันปัจจุบันและสถานะ Release

| องค์ประกอบ | เวอร์ชัน | สถานะ |
|-----------|---------|--------|
| **Source (dev)** | 1.0.36 | ✅ 313 tests ผ่าน |
| **GitHub tag** | v1.0.36 | ✅ pushed |
| **Test VM** | 1.0.36 | ✅ deployed & verified |
| **Production** | v1.0.34 | ✅ ทำงานอยู่ |

**Release ถัดไป:** v1.0.37 (หลัง feature cycle ถัดไป)

---

## สภาพแวดล้อม

| บทบาท | Host | IP | User | Path |
|-------|------|-----|------|------|
| Dev | WSL Ubuntu | 172.20.14.199/20 | ipds | `/home/ipds/Hermes-Prj/chk-a/` |
| Test VM | VirtualBox Ubuntu 24.04 | 192.168.56.122 | ipds | `/home/ipds/Hermes-Prj/chk-a/` (source), `/opt/chk-a/` (runtime) |
| Production | uptime-host | internal | chk-a (uid=999) | `/opt/chk-a/` |

**SSH:** Dev → Test passwordless (reverse NOT possible)  
**Sync:** `rsync -avz -c` (checksum verification)  
**Deploy:** `sudo ./scripts/deploy.sh` บนเครื่องเป้าหมาย

---

## สรุปสถาปัตยกรรม

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│ ResolverAgent   │────▶│ ConsensusAgent   │────▶│ MLAgent     │
│ (parallel DNS)  │     │ (weighted vote,  │     │ (EMA decay, │
│ health EMA      │     │  entropy, outliers│     │  anomaly)   │
└─────────────────┘     └──────────────────┘     └─────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│ MTRAgent        │◀───│ AlertAgent       │◀───│ Orchestrator│
│ (MTR paths)     │     │ (dedup, rate-    │     │ (scheduler, │
│                 │     │  limit, Telegram)│     │  healthz)   │
└─────────────────┘     └──────────────────┘     └─────────────┘
                                                          │
                                                          ▼
                                                ┌─────────────────┐
                                                │ Reporting Stack │
                                                │ (graphs, PDF,   │
                                                │  Telegram,      │
                                                │  email)         │
                                                └─────────────────┘
```

---

## ไฟล์สำคัญและหน้าที่

### Core Agents
- `src/chk_a/agents/resolver_agent.py` — Parallel DNS (A/AAAA), DoH/DoT, health EMA, resolver weights
- `src/chk_a/agents/consensus_agent.py` — Weighted vote, entropy consensus score, outlier detection, reputation
- `src/chk_a/agents/ml_agent.py` — Exponential decay baseline (IP + path), anomaly scoring
- `src/chk_a/agents/alert_agent.py` — Dedup (30น.), token bucket (20/ชม.), Telegram HTML alerts, dual audit logs
- `src/chk_a/agents/mtr_agent.py` — MTR subprocess, JSON parse, hop stats, parallel for outliers

### Orchestration & Config
- `src/chk_a/orchestrator.py` — Cycle coordination, cron-like scheduler (Asia/Bangkok), daily/monthly tasks, healthz, graceful shutdown, **FQDNStore integration**
- `src/chk_a/config/loader.py` — YAML + `${ENV}` substitution, Pydantic v2, auto-tune `max_concurrent`
- `src/chk_a/models/schemas.py` — Contracts ทั้งหมด: CheckResult, ConsensusResult, AnomalyEvent, FQDNRecord, etc.
- `src/chk_a/storage/baseline_store.py` — Atomic JSON persistence (os.replace + fsync)
- `src/chk_a/storage/fqdn_store.py` — FQDN-centric persistence (FQDNRecord, IP history, availability, alert_rules)

### Reporting
- `src/chk_a/reporting/graph_generator.py` — 7 chart types × EN/TH, Thai fonts, translation map, Daily Heatmap
- `src/chk_a/reporting/monthly_report.py` — Pipeline: insights → graphs → PDF → Telegram/email
- `src/chk_a/reporting/telegram_reporter.py` — Batched photo send, exponential backoff, Thai-only filter, sequential send
- `src/chk_a/reporting/pdf_generator.py` — fpdf2 EN/TH templates
- `src/chk_a/reporting/ml_insights.py` — Availability, integrity, path health, anomaly detection, **daily_availability**
- `src/chk_a/reporting/telegram_client.py` — Async client, retry, circuit breaker, token-in-URL
- `src/chk_a/reporting/email_sender.py` — SMTP TLS, PDF attachments, EN/TH body

### Entry Point & System
- `src/chk_a/main.py` — CLI (`validate-config`, `check-once`, `show-baseline`, `test-telegram`, `test-daily-image`, `mtr`) + daemon
- `systemd/chk-a.service` — 4 services, Type=notify, WatchdogSec, CAP_NET_RAW, ExecStartPre/ExecStop → systemd_wrapper.py
- `scripts/systemd_wrapper.py` — ตรวจจับ restart ผ่าน state file, ส่งการแจ้ง start/restart/stop/fail/error
- `scripts/systemd_notify.py` — Notifier ตรงสำหรับ lifecycle events
- `/etc/chk-a/config.yaml` — Production config
- `/etc/chk-a/env` — Telegram credentials (BOT_TOKEN, CHAT_ID)

### FQDN Features (ใหม่ — 2026-09-23)
- `FQDNConfig.alert_rules` — Per-FQDN custom thresholds (`anomaly_threshold`, `consensus_min_score`)
- `AnomalyEvent.type = "ip_change"` — Anomaly type ใหม่สำหรับการเปลี่ยน IP
- `_process_fqdn()` — คำนวณ availability ต่อรอบ, อัปเดต FQDNRecord
- `_alert_ip_change()` — ตรวจจับ IP changes, ส่ง Thai alert
- Thai formatting สำหรับ `ip_change` ใน `alert_agent.py`

---

## Test Suite

**313 tests** ครอบ 10 ไฟล์ — **ผ่านทั้งหมด** (zero regression)

| ไฟล์ | Tests | เน้น |
|------|-------|------|
| `test_alert_agent.py` | ~25 | Alert formatting, dedup, rate-limit, Thai format |
| `test_consensus_agent.py` | ~20 | Weighted vote, entropy, outliers, reputation |
| `test_ml_agent.py` | ~18 | EMA baseline, anomaly scoring, score() |
| `test_resolver_agent.py` | ~15 | Parallel DNS, DoH, health, weights |
| `test_mtr_agent.py` | ~12 | MTR parse, hop stats, parallel outliers |
| `test_orchestrator.py` | ~12 | Scheduler, daily/monthly, FQDNStore integration |
| `test_integration_pipeline.py` | 7 | Full pipeline E2E |
| `test_security_regressions.py` | 74 | SEC-001 ถึง SEC-020 |
| `test_reporting.py` | 18 | Log rotation, `_load_recent_checks()` |
| `test_email_sender.py` | 12 | SMTP, PDF, EN/TH |
| `test_fqdn_store.py` | 25 | FQDNRecord, FQDNStore, queries, path traversal |
| `test_loop7.py` | ~5 | CLI commands |

**Test fixtures:** `tests/conftest.py` — `CHK_A_BASELINE_DIR=/tmp`, `CHK_A_FQDN_DIR=/tmp/chk-a-test/fqdns`, helper `_make_temp_path(subdir=...)`

**กฎสำคัญ:** ใช้ `_make_temp_path()` ห้ามใช้ `tmp_path` fixture

---

## Security Posture (OWASP Top 10 2025 — Self-Review)

| ID | Finding | สถานะ | Fix |
|----|---------|--------|-----|
| SEC-001 | MTR Command Injection | ✅ | `ipaddress.ip_address()` validation |
| SEC-002 | Path Traversal (BaselineStore/FQDNStore) | ✅ | Dynamic allowed base dir validation |
| SEC-003 | Secrets handling | ✅ | Direct env parse, redaction, token-in-URL |
| SEC-004 | Health endpoint exposure | ✅ | Loopback bind only |
| SEC-005 | SMTP TLS enforcement | ✅ | Port 465/587 only |
| SEC-006 | Config input validation | ✅ | Pydantic v2 validators |
| SEC-007 | Telegram token in URL | ✅ | URL path ตาม Bot API, masked logs |
| SEC-008 | Dedup cache LRU + TTL | ✅ | Max-size + TTL eviction |
| SEC-009 | Log injection | ✅ | Sanitization |
| SEC-010 | DoH/DoT support | ✅ | Implemented + tests |
| SEC-011 | CAP_NET_RAW for MTR | ✅ | Systemd caps + tests |
| SEC-012 | Concurrency ceilings | ✅ | Hard limits |
| SEC-013 | Dependency pinning | ✅ | SHA-256 สำหรับ 39 packages |
| SEC-014 | HTML escape in Telegram | ✅ | `_html_escape()` ใน callers |
| SEC-015 | Baseline encryption | ✅ | age/pyrage at rest |
| SEC-016 | Config permissions | ✅ | chmod 640/600, chown root:chk-a |
| SEC-017 | Telegram circuit breaker | ✅ | CLOSED/OPEN/HALF_OPEN |
| SEC-018 | Scheduler drift fix | ✅ | Absolute time scheduling |
| SEC-019 | MTR/Resolver sync validation | ✅ | Cross-config validation |
| SEC-020 | FQDN path traversal | ✅ | เหมือน SEC-002 |

---

## รายงานและการแปลภาษา (Localization)

### ประเภทกราฟ (7 × EN/TH = 14 + 2 Dashboard + 2 Daily Heatmap = 18/เดือน)
1. **Availability Bar** — Resolver success rate
2. **Availability Heatmap (hourly)** — Hour vs resolver success matrix
3. **Availability Heatmap (daily)** — Day-of-month vs resolver (ใหม่ 2026-09-17)
4. **Integrity Score** — Baseline integrity over time
5. **Latency Boxplot** — Per-resolver latency distribution (median ASC sort)
6. **IP Stability** — Unique IP count over time
7. **MTR Path** — Path hop count distribution
8. **Path Availability** — Path success rate
9. **Dashboard** — Combined multi-panel
10. **Dashboard (TH)** — Thai version

### Thai Translation Map
ทุกองค์ประกอบกราฟแปลผ่าน `_apply_thai_fonts()` + translation map:
- Titles, axis labels, legends, annotations
- Footer: `hostname | timestamp` (local time)
- Heatmap x-axis: ป้ายเวลาท้องถิ่น (Asia/Bangkok)

### Alert HTML (ภาษาไทย — v1.0.35)
```
⚠️ พบความผิดปกติของ DNS
Type: 🗳️ ความแตกต่างของคะแนนเสียง (consensus_deviation)
Severity: 🟡 คำเตือน (WARNING)
FQDN: iot-ENZY-hub-PRD-SEA-01.azure-devices.net
Host: uptime-host
🆔 Event ID: uptime-host-20260923-084010
✅ ฝ่ายมาก (9/19):
  IPs: 10.43.44.4
  Resolvers: HQ-22, HQ-23, NTBR-ADDS-22, DR-23, BB, SK, SNR, KA, Azure-EV
⚠️ ฝ่ายน้อย (8/19):
  IPs: 40.78.238.5
  Resolvers: DR-22, MM, MMM, UR, KK1, WNO, LR, CHN
❌ ค่าผิดปกติ (Outliers) — ต่างจากฝ่ายมาก:
  ❌ DR-22: 40.78.238.5  ← ต่างจากฝ่ายมาก!
  ...
❌ ล้มเหลว / ไม่ตอบสนอง (ไม่นับในคะแนนเสียง):
  ❌ BPK: TIMEOUT
  ...
คะแนนเสียง (Consensus): 0.25% — ใกล้ Tie ความไม่แน่นอนสูง
Resolvers: 19 checked
Time: 2026-09-23 08:40:10
🏷️ <b>chk-a v1.0.35</b>
```

### คำอธิบาย Consensus (ภาษาไทย)
| Score | Label | คำอธิบาย |
|-------|-------|----------|
| 100% | ตอบเหมือนกันหมด | Resolver ทุกตัวตอบเหมือนกัน |
| 90-99% | สูงมาก — มี resolver ฝ่ายน้อยผิดปกติ | ฝ่ายมากแข็งแกร่ง |
| 70-89% | ปานกลาง — มี resolver ฝ่ายน้อยผิดปกติ | ฝ่ายมากปานกลาง |
| 50-69% | แยกสองฝ่ายชัดเจน | Split brain / Misconfig |
| 1-49% | ใกล้ Tie ความไม่แน่นอนสูง | ใกล้เสมอ, ความไม่แน่นอนสูง |
| 0% | เสมอภาค | เสมอสมบูรณ์ |

---

## FQDN Data Model (v1.0.32+)

```python
FQDNRecord:
  # Identity
  fqdn: str                    # e.g., "iot-ENZY-hub-PRD-SEA-01.azure-devices.net"
  domain: str                  # "azure-devices.net" (derived)
  subdomain: str               # "iot-ENZY-hub-PRD-SEA-01" (derived)
  apex_domain: str             # "azure-devices.net" (derived)

  # DNS Records
  current_ips: list[str]       # Current A/AAAA records
  cname_chain: list[str]       # CNAME chain if any
  ttl: int                     # Current TTL
  last_resolved: datetime      # Last successful resolution

  # History
  ip_changes: list[IPChange]   # IP changes with timestamp, source, old_ips, new_ips

  # Metadata
  registrar: str               # Registrar info
  expiry_date: datetime        # Domain expiry
  nameservers: list[str]       # Authoritative NS

  # Monitoring State
  last_checked: datetime       # Last check timestamp
  status: str                  # "healthy" | "degraded" | "critical" | "unknown"
  consecutive_failures: int    # Failure streak
  availability_percent: float  # Successful/total * 100 (per cycle)

  # Alerting Rules (Per-FQDN custom thresholds)
  alert_rules: dict[str, Any]  # anomaly_threshold, consensus_min_score

  # ML Features
  baseline_ips: list[str]      # Learned baseline IPs
  anomaly_score: float         # Current anomaly score
  flip_flop_count: int         # IP flip-flop count
  geo_shifts: list[GeoShift]   # Geographic IP shifts
```

---

## Consensus Algorithm

```
Weighted Vote: แต่ละ resolver มี weight = health_ema * config_weight
Entropy: H = -Σ(p_i * log2(p_i)) โดย p_i = vote_weight_i / total_weight
Max Entropy: log2(n_unique_answers)
Consensus Score: (1 - H/H_max) * 100%

ตัวอย่าง:
- 19/19 เหมือนกัน → H=0 → 100%
- 9/19 ต่อ 8/19 + 2 failed → H≈0.997 → 0.25% (near tie)
- 9/19 ต่อ 9/19 + 1 failed → H=1.0 → 0% (tie)
```

**สูตร:** `(1 - normalized_entropy) × 100%`, โดย `normalized_entropy = entropy / max_entropy`

---

## จุดสำคัญของ Configuration

### Required Sections ใน `/etc/chk-a/config.yaml`
```yaml
fqdns:                          # List of FQDNConfig (with alert_rules)
resolvers:                      # List of ResolverConfig (IP:port or hostname:port)
resolver_agent:                 # max_concurrent, timeout, retries
consensus_agent:                # min_consensus_score, outlier_threshold
ml_agent:                       # decay_factor, anomaly_threshold
alert:                          # dedup_window_min, rate_limit_per_hour, telegram
scheduler:                      # check_interval_seconds, daily_report_time, monthly_report_day
logging:                        # level, jsonl_path, plain_path, max_bytes, backup_count
mtr:                            # enabled, max_hops, timeout, packet_size
reporting:                      # output_dir, telegram (chat_id, batch_size), email, pdf
baseline_store_path:            # /var/lib/chk-a/baselines.json
fqdn_store_path:                # /var/lib/chk-a/fqdns.json  (ใหม่)
```

### Secrets ใน `/etc/chk-a/env`
```bash
TELEGRAM_BOT_TOKEN=***
TELEGRAM_CHAT_ID=-100xxxxxxxx
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=***
AGE_KEY=age-******  # For baseline encryption
```

---

## Release & Deploy Process

### Dev → Test VM
```bash
# บน dev machine
rsync -avz -c /home/ipds/Hermes-Prj/chk-a/ ipds@192.168.56.122:/home/ipds/Hermes-Prj/chk-a/

# บน test VM
ssh ipds@192.168.56.122
cd /home/ipds/Hermes-Prj/chk-a
sudo ./scripts/deploy.sh
```

### Test VM → Production (GitHub Release)
```bash
# บน dev machine
git tag v1.0.36
git push origin v1.0.36
# GitHub Actions builds wheel, creates release with assets

# บน production
curl -sSL https://raw.githubusercontent.com/tpdevices/chk-a/v1.0.36/install.sh | sudo bash
```

### Version Bump (ต้องทำทั้ง 3 ไฟล์เสมอ)
1. `pyproject.toml` — `version = "1.0.36"`
2. `src/chk_a/main.py` — CLI version
3. `src/chk_a/__init__.py` — อ่านจาก package metadata, fallback ไป pyproject.toml

**จากนั้น:** Clear Python cache + reinstall: `sudo find /opt/chk-a/.venv -name '*.pyc' -path '*/chk_a/*' -delete && pip install -e .`

---

## CHANGELOG Format (บังคับ)

ทุกการเปลี่ยนไฟล์ **ต้อง** บันทึก:
```
- **YYYY-MM-DD HH:MM:SS** — `path/to/file.ext` — Type: Description
```
Types: Added / Changed / Fixed / Removed / Security

Timezone: **Asia/Bangkok (+07)** เสมอ

---

## ไฟล์ที่คุ้มครอง (ต้องถามก่อนแก้)

| ไฟล์ | เหตุผล |
|------|--------|
| `src/chk_a/reporting/graph_generator.py` | Core styling, palette, Thai fonts |
| `src/chk_a/reporting/telegram_reporter.py` | Telegram delivery logic |
| `src/chk_a/agents/alert_agent.py` | Alert formatting, dedup, rate-limit |
| `src/chk_a/config/loader.py` | Config parsing, env substitution |
| `systemd/chk-a.service` | Systemd hardening |
| `install.sh` / `uninstall.sh` | Production installers |
| `.github/workflows/release.yml` | Release automation |

---

## สถานะที่ทำงานได้ ( ณ 2026-09-23 11:45)

- ✅ 313/313 tests ผ่านบน dev
- ✅ 313/313 tests ผ่านบน test VM (sync ล่าสุด)
- ✅ Thai localization เสร็จ (v1.0.35)
- ✅ FQDN features implemented (availability, per-FQDN thresholds, IP change detection)
- ✅ Source synced ไป test VM (192.168.56.122:/home/ipds/Hermes-Prj/chk-a/)
- ⏳ Test VM deploy รอ (`sudo ./scripts/deploy.sh`)
- ⏳ Production release รอ (v1.0.36 หลัง test verified)

---

*อัปเดตโดย Hermes Agent วันที่ 2026-09-23 11:45:00 (Asia/Bangkok UTC+07)*