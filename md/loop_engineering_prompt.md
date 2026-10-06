# Loop‑Engineering Prompt สำหรับโครงการ **chk‑a**
> สร้างสคริปต์ตรวจสอบ A‑record ของ FQDN จาก resolver ที่กำหนดในไฟล์, ทำการเรียนรู้ (ML) จากข้อมูลที่ได้, ตรวจจับความผิดปกติ, บันทึกลง log และส่งแจ้งเตือน Telegram  
> ระบบทำงานเป็น **multi‑agent service** บน Ubuntu 24.04+ โดยสุ่มช่วงเวลาระหว่างรอบไม่เกิน 3 นาที  

---

## 🎯 วัตถุประสงค์หลัก
1. **Resolver Agent** – ดึง A‑record ของแต่ละ FQDN จาก resolver‑list (ไฟล์ YAML/JSON) อย่าง asynchronous  
2. **Consensus Agent** – คำนวณ “majority” IP จากกลุ่ม resolver, ให้คะแนนความเชื่อมั่นของแต่ละ resolver  
3. **ML / Baseline Agent** – สร้าง baseline ของ IP ที่คาดว่าจะเจอ (online learning, EMA หรือ River‑based)  
4. **Anomaly Detector** – เปรียบเทียบผลลัพธ์ของ Resolver + Baseline; หากคะแนนความผิดปกติเกิน threshold ให้สร้างเหตุการณ์ (AnomalyEvent)  
5. **Alert Agent** – เขียนเหตุการณ์ลงไฟล์ log (JSONL) พร้อม deduplication, rate‑limit และส่งข้อความ Telegram (HTML/Markdown)  
6. **Scheduler / Service Wrapper** – รัน loop อย่างต่อเนื่อง, สุ่ม delay 30‑180 s, จัดการ signal SIGTERM/SIGINT, ทำให้เป็น systemd service  

---

## 📁 โครงสร้างโฟลเดอร์ (สรุป)
```
chk-a/
├─ md/                         ←  (ที่เก็บ Prompt นี้)
│   └─ loop_engineering_prompt.md   ←  (ไฟล์นี้)
├─ src/
│   ├─ agents/
│   │   ├─ resolver_agent.py
│   │   ├─ consensus_agent.py
│   │   ├─ ml_agent.py
│   │   └─ alert_agent.py
│   ├─ config/
│   │   └─ loader.py
│   ├─ storage/
│   │   └─ baseline_store.py
│   ├─ models/
│   │   └─ schemas.py
│   ├─ utils/
│   │   ├─ logger.py
│   │   ├─ telegram.py
│   │   └─ scheduler.py
│   └─ main.py
├─ config/
│   └─ settings.yaml
├─ tests/
├─ pyproject.toml
├─ systemd/
│   └─ chk-a.service
└─ README.md
```

---

## 🔁 Loop Engineering Plan (7 Loops)

### Loop 0 – Scaffold & Contracts
**Goal**: โครงสร้างโปรเจกต์, Pydantic models, config loader, JSONL logger  
**Prompt**:
```markdown
Create the project skeleton for chk-a:
- pyproject.toml with deps: dnspython>=2.6, pydantic>=2.7, pydantic-settings>=2.3, pyyaml>=6.0, aiohttp>=3.9, river>=0.21, python-systemd>=235, tenacity>=8.2
- Directory structure: src/chk_a/{agents,config,storage,models,utils}
- Define all Pydantic models (ResolverConfig, FQDNConfig, CheckResult, ConsensusResult, AnomalyEvent, MLConfig, AlertConfig, SchedulerConfig, LoggingConfig)
- Write config loader with env var substitution (${VAR}) using pydantic-settings
- Write JSONL logger with RotatingFileHandler (max 50MB, 10 backups)
- Unit tests for models + config loader
- Run: pytest -xvs tests/
```

---

### Loop 1 – Resolver Agent (Parallel DNS)
**Goal**: Async DNS queries to multiple resolvers with health tracking  
**Prompt**:
```markdown
Implement ResolverAgent class:
- __init__(resolvers: list[ResolverConfig], logger)
- async check_fqdn(fqdn: str) -> list[CheckResult]
- Use dnspython async resolver (dns.asyncresolver)
- Per-resolver timeout (configurable, default 2000ms)
- Concurrent queries via asyncio.gather with semaphore (max 10 concurrent)
- Handle: NXDOMAIN, SERVFAIL, TIMEOUT, empty answer, CNAME chains
- Track per-resolver health: success_rate (EMA α=0.1), avg_latency_ms
- Return CheckResult for each resolver (success=True/False, ips=[], latency_ms, error)
- Tests: mock DNS responses using aioresponses or unittest.mock, test error cases
- Run: pytest tests/test_resolver_agent.py -xvs
```

---

### Loop 2 – Consensus Agent (Voting & Statistics)
**Goal**: Weighted majority vote, entropy scoring, resolver reputation  
**Prompt**:
```markdown
Implement ConsensusAgent class:
- Input: list[CheckResult] for one FQDN
- Output: ConsensusResult
- Algorithm: Weighted majority vote
  - weight = resolver_config.weight * resolver_health.success_rate
  - Tally IPs by weight
  - majority_ips = IPs with cumulative weight >= min_consensus (default 0.6)
- Compute consensus_score = 1 - normalized_shannon_entropy(weight_distribution)
  - entropy = -sum(p_i * log2(p_i)) where p_i = weight_i / total_weight
  - normalized = entropy / log2(n_unique_ips) → 0=full agreement, 1=max disagreement
- Outliers: CheckResult where IPs not in majority_ips AND weight < 0.2 * total_weight
- Update resolver reputation: EMA of agreement_with_consensus (α=0.05)
- Tests: scenarios 3-1 split, 2-2 split, all different, single resolver
- Run: pytest tests/test_consensus_agent.py -xvs
```

---

### Loop 3 – ML / Baseline Agent (Online Learning)
**Goal**: Incremental baseline per FQDN with exponential decay  
**Prompt**:
```markdown
Implement MLAgent class:
- __init__(config: MLConfig, storage: BaselineStore, logger)
- State per FQDN: Counter[IP] with exponential decay, sample_count
- Method learn(consensus: ConsensusResult) -> None:
  - For each IP in consensus.majority_ips: counter[ip] *= (1 - decay); counter[ip] += 1
  - decay = config.baseline_decay (default 0.05)
  - sample_count += 1
  - Persist to storage atomically (write temp + os.rename)
- Method score(fqdn: str, observed_ips: set[str]) -> float:
  - If sample_count < config.min_samples_before_alert (default 10): return 0.0
  - baseline_probs = normalize(counter values)
  - observed_probs = uniform over observed_ips
  - anomaly_score = 1 - sum(min(baseline_probs[ip], observed_probs[ip]) for ip in union)
  - Return anomaly_score (0-1)
- Method get_baseline(fqdn: str) -> dict[str, float]: return normalized baseline
- Storage: JSON file with atomic writes, load on startup
- Tests: simulate gradual drift, sudden change, new IP, cold start
- Run: pytest tests/test_ml_agent.py -xvs
```

---

### Loop 4 – Alert Agent (Log + Telegram)
**Goal**: Deduplication, rate limiting, Telegram formatting  
**Prompt**:
```markdown
Implement AlertAgent class:
- __init__(config: AlertConfig, logger, telegram_client: TelegramClient)
- Method maybe_alert(event: AnomalyEvent) -> bool:
  - Dedup key = (event.fqdn, event.type, frozenset(event.details.get('ips', [])))
  - Check Redis/in-memory cache with TTL = config.dedup_window_minutes (default 30)
  - If seen: return False (suppressed)
  - Rate limit: token bucket (capacity=config.rate_limit_per_hour, refill=1/3600 per sec)
  - If rate limited: queue or drop (log warning)
  - Format Telegram message (HTML):
    <b>⚠️ DNS Anomaly Detected</b>
    <b>Type:</b> {event.type} | <b>Severity:</b> {event.severity}
    <b>FQDN:</b> <code>{event.fqdn}</code>
    <b>Observed IPs:</b> {', '.join(f'<code>{ip}</code>' for ip in event.details['observed_ips'])}
    <b>Baseline IPs:</b> {', '.join(f'<code>{ip}</code>' for ip in event.details['baseline_ips'])}
    <b>Consensus:</b> {event.details['consensus_score']:.2%}
    <b>Resolvers:</b> {event.details['resolver_count']} checked
    <b>Time:</b> {event.timestamp.isoformat()}
  - Send via TelegramClient.send_message(chat_id, text, parse_mode='HTML')
  - Log to JSONL: {timestamp, event.model_dump()}
  - Return True
- TelegramClient: aiohttp session, retry with tenacity (3 retries, exponential backoff)
- Tests: dedup window, rate limit, formatting, network error handling
- Run: pytest tests/test_alert_agent.py -xvs
```

---

### Loop 5 – Orchestrator + Scheduler (Main Loop)
**Goal**: End-to-end cycle with random jitter, graceful shutdown  
**Prompt**:
```markdown
Implement Orchestrator class and main entry point:
- __init__(config: AppConfig, agents: dict, logger)
- async run_cycle():
  1. For each FQDN in parallel: resolver_agent.check_fqdn(fqdn)
  2. For each FQDN: consensus_agent.process(results)
  3. For each FQDN: ml_agent.learn(consensus)
  4. For each FQDN: score = ml_agent.score(fqdn, observed_ips)
  5. If score > config.ml.anomaly_threshold (default 0.7):
       Create AnomalyEvent with type="baseline_deviation" or "consensus_deviation"
       alert_agent.maybe_alert(event)
  6. Also check consensus outliers → type="consensus_deviation"
- Scheduler: asyncio.sleep(random.uniform(min_interval, max_interval)) between cycles
  - min_interval=30, max_interval=180 (config.scheduler)
- Signal handling: SIGTERM/SIGINT → set shutdown flag, persist ML baseline, flush logs, exit cleanly
- Optional: HTTP /healthz endpoint for systemd watchdog (port from env)
- Main function: load config, init agents, run orchestrator until shutdown
- Tests: integration test with mocked agents, verify full cycle, test shutdown
- Run: pytest tests/test_orchestrator.py -xvs
```

---

### Loop 6 – Systemd Service & Deployment
**Goal**: Production-ready systemd service with install script  
**Prompt**:
```markdown
Create deployment artifacts:
- systemd/chk-a.service:
  [Unit]
  Description=chk-a DNS Anomaly Monitor
  After=network-online.target
  Wants=network-online.target
  
  [Service]
  Type=notify
  User=chk-a
  Group=chk-a
  WorkingDirectory=/opt/chk-a
  ExecStart=/opt/chk-a/.venv/bin/python -m chk_a.main
  ExecStartPre=/opt/chk-a/.venv/bin/python -m chk_a.validate_config
  Restart=on-failure
  RestartSec=10
  WatchdogSec=60
  StandardOutput=journal
  StandardError=journal
  EnvironmentFile=/etc/chk-a/env
  # Hardening
  NoNewPrivileges=yes
  PrivateTmp=yes
  ProtectSystem=strict
  ProtectHome=yes
  ReadWritePaths=/var/log/chk-a /var/lib/chk-a
  CapabilityBoundingSet=
  
  [Install]
  WantedBy=multi-user.target

- install.sh: creates user chk-a, dirs (/opt/chk-a, /etc/chk-a, /var/log/chk-a, /var/lib/chk-a), venv, pip install -e ., copies config.yaml.example, enables service
- /etc/chk-a/config.yaml.example (full example with comments)
- /etc/chk-a/env.example (TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID=)
- logrotate.d/chk-a (daily, rotate 365, compress, delaycompress, missingok)
- Makefile targets: install, uninstall, test, lint, build, dev-install
- Validate: systemd-analyze verify /etc/systemd/system/chk-a.service
- Run: sudo make install && sudo systemctl daemon-reload && sudo systemctl enable --now chk-a
```

---

### Loop 7 – Observability, Hardening & Docs
**Goal**: Production hardening, documentation  
**Prompt**:
```markdown
Add production hardening:
- Structured logging: add correlation_id (uuid4) per cycle, include in all log lines
- CLI commands:
  - chk-a validate-config  (exit 0/1, print errors)
  - chk-a check-once       (single cycle, print results, exit)
  - chk-a show-baseline    (print learned baselines)
  - chk-a test-telegram    (send test message)
- Security: drop all capabilities, private /tmp, no new privileges
- Documentation:
  - README.md (quickstart, config, architecture)
  - ARCHITECTURE.md (agent diagram, data flow, ML details)
  - RUNBOOK.md (common operations, troubleshooting, alert response)
  - CONTRIBUTING.md
- Run: pytest -xvs && make lint && make build
```

---

## ✅ Acceptance Criteria (Definition of Done)

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | All 4 agents implemented + tests pass | `pytest -xvs` → 100% pass |
| 2 | Config loads from YAML + env vars | `chk-a validate-config` exits 0 |
| 3 | Single check cycle works end-to-end | `chk-a check-once` prints results |
| 4 | ML baseline persists across restarts | Stop/start service, verify baseline intact |
| 5 | Anomaly triggers log + Telegram | Inject bad IP, verify alert in log & Telegram |
| 6 | Deduplication works | Repeat same anomaly within 30 min → no duplicate alert |
| 7 | Rate limiting works | Burst >20/hr → excess dropped/logged |
| 8 | Systemd service starts/enables | `systemctl status chk-a` → active (running) |
| 9 | Random interval 30-180s | Check log timestamps, verify jitter |
| 10 | Graceful shutdown on SIGTERM | `systemctl stop chk-a` → clean exit, baseline saved |
| 11 | Zero heavy ML deps (no torch, sklearn) | `pipdeptree` shows only river |
| 12 | Config validation catches errors | Invalid YAML → clear error message |

---

## 🛠️ Quick Start Commands

```bash
# 1. Clone & setup
git clone <repo> chk-a && cd chk-a
make dev-install  # creates venv, installs deps, pre-commit

# 2. Configure
sudo cp config/settings.yaml.example /etc/chk-a/config.yaml
sudo cp config/env.example /etc/chk-a/env
sudo vim /etc/chk-a/config.yaml /etc/chk-a/env

# 3. Validate
chk-a validate-config

# 4. Test run once
chk-a check-once

# 5. Install as service
sudo make install
sudo systemctl enable --now chk-a

# 6. Monitor
journalctl -u chk-a -f
tail -f /var/log/chk-a/checks.jsonl | jq .
```

---

## 💡 Pro Tips สำหรับ Loop Engineering

1. **Run each loop to 100% green before next** — ไม่ยอม compromise
2. **Commit after each loop** — `git commit -m "loop N: <agent>"`
3. **Integration test at Loop 5** — mock all agents, test full cycle
4. **Telegram formatting** — ใช้ `<code>` สำหรับ IP, `<b>` สำหรับ severity
5. **Resolver health** — track per-resolver để weight consensus ในรอบต่อไป
6. **ML cold start** — require `min_samples_before_alert` ก่อน alert จริง
7. **Atomic writes** — baseline JSON: write to .tmp → os.rename() ป้องกัน corrupt
8. **Watchdog** — systemd WatchdogSec=60, orchestrator calls sd_notify('WATCHDOG=1') ทุก cycle

---

## 📝 Config Schema Reference (settings.yaml)

```yaml
fqdns:
  - name: "example.com"
    expected_ips: ["93.184.216.34"]      # optional allowlist
    min_consensus: 0.6                   # majority threshold
  - name: "api.github.com"
    min_consensus: 0.5

resolvers:
  - name: "google"
    address: "8.8.8.8:53"
    weight: 1.0
    timeout_ms: 2000
  - name: "cloudflare"
    address: "1.1.1.1:53"
    weight: 1.0
    timeout_ms: 2000
  - name: "quad9"
    address: "9.9.9.9:53"
    weight: 1.0
    timeout_ms: 2000
  - name: "local"
    address: "127.0.0.1:53"
    weight: 0.5
    timeout_ms: 1000

ml:
  baseline_decay: 0.05                   # EMA decay factor
  anomaly_threshold: 0.7                 # alert if score > this
  min_samples_before_alert: 10           # cold start protection

alert:
  telegram_bot_token: "${TELEGRAM_BOT_TOKEN}"
  telegram_chat_id: "${TELEGRAM_CHAT_ID}"
  dedup_window_minutes: 30
  rate_limit_per_hour: 20

scheduler:
  min_interval_sec: 30
  max_interval_sec: 180
  jitter: true

logging:
  level: "INFO"
  file: "/var/log/chk-a/checks.jsonl"
  max_size_mb: 50
  backup_count: 10
```

---

## 🔐 Environment Variables (/etc/chk-a/env)

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=-1001234567890
# Optional:
# CHK_A_LOG_LEVEL=DEBUG
```

---

**พร้อมใช้งานแล้วครับ!** ให้เริ่มที่ Loop 0 แล้วทำทีละลูปจนครบ Loop 7 จะได้ระบบ chk-a ครบถ้วน production-ready 💙