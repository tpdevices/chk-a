# chk-a — Multi-Agent DNS A-Record Anomaly Monitor

`chk-a` watches a set of FQDNs and detects when their A-record IPs change in
anomalous ways. It queries each FQDN from several DNS resolvers, builds a
weighted consensus, learns a per-FQDN baseline online (no batch training, no
heavy ML deps), and raises a Telegram alert when an IP set deviates from what
it has learned or from what the resolver group agrees on.

It runs as a `systemd` service on Ubuntu 24.04 LTS+, with a randomized cycle
interval of 30–180 seconds.

---

## Features

- **Multi-resolver consensus** — queries every configured resolver in parallel,
  weights each by its configured weight × its live success-rate EMA, and flags
  resolvers that disagree while carrying little weight (outliers).
- **Online ML baseline** — a per-FQDN decayed IP counter (custom EMA + total-
  variation distance). No `torch` / `sklearn` / `river`. Learns continuously and
  forgets stale IPs gradually.
- **Two anomaly signals**
  - `baseline_deviation` — observed IP set diverges from the learned baseline
    (anomaly score > `ml.anomaly_threshold`).
  - `consensus_deviation` — a resolver reports IPs no one else agrees on.
- **Deduplicated, rate-limited Telegram alerts** — HTML formatting, in-memory
  dedup window, token-bucket rate limit, and a JSONL audit log.
- **Observability** — structured JSON logging with a per-cycle `correlation_id`
  and a `/healthz` endpoint for the systemd watchdog.
- **Production hardening** — runs as an unprivileged user under a `systemd`
  `Type=notify` unit with `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`,
  and dropped capabilities.

---

## Quickstart (development)

```bash
cd /home/ipds/Hermes-Prj/chk-a
make dev-install          # create venv + install with dev deps
cp config/settings.yaml.example config/settings.yaml
$EDITOR config/settings.yaml        # set fqdns / resolvers
make test                # run the suite
PYTHONPATH=src python -m chk_a.validate-config
PYTHONPATH=src python -m chk_a.check-once          # one cycle, prints results
PYTHONPATH=src python -m chk_a.show-baseline       # print learned baselines
```

Run the daemon locally (foreground):

```bash
PYTHONPATH=src python -m chk_a
```

---

## CLI commands

| Command | Purpose |
|---------|---------|
| `chk-a` | Run the monitoring daemon (default). |
| `chk-a validate-config` | Load + validate config; exit `0` if OK, `1` on problems. Used as the systemd `ExecStartPre`. |
| `chk-a check-once` | Run exactly one monitoring cycle and exit. |
| `chk-a show-baseline` | Print the learned ML baselines (JSON) for every configured FQDN. |
| `chk-a test-telegram` | Send a Telegram test message and report success/failure. |

---

## Configuration

Configuration is loaded from `CHK_A_CONFIG` (default `config/settings.yaml`).
`${ENV}` references are substituted from the process environment, so secrets
(Telegram token / chat id) are never committed.

```yaml
fqdns:
  - name: "example.com"
    expected_ips: ["93.184.216.34"]   # optional allowlist
    min_consensus: 0.6
resolvers:
  - name: "google"
    address: "8.8.8.8:53"
    weight: 1.0
    timeout_ms: 2000
ml:
  baseline_decay: 0.05          # EMA decay applied to IP counters each cycle
  anomaly_threshold: 0.7        # score above this -> baseline_deviation alert
  min_samples_before_alert: 10  # learn cycles before alerts are emitted
alert:
  telegram_bot_token: "${TELEGRAM_BOT_TOKEN}"
  telegram_chat_id: "${TELEGRAM_CHAT_ID}"
  dedup_window_minutes: 30
  rate_limit_per_hour: 20
  alert_log_path: "/var/log/chk-a/alerts.jsonl"
scheduler:
  min_interval_sec: 30
  max_interval_sec: 180
  jitter: true
logging:
  level: "INFO"
  file: "/var/log/chk-a/checks.jsonl"
baseline_store_path: "/var/lib/chk-a/baselines.json"
```

See `config/chk-a.config.yaml.example` and `config/chk-a.env.example` for the
production layout (`/etc/chk-a/...`).

---

## Install as a systemd service

```bash
sudo ./install.sh
sudo systemctl status chk-a
sudo journalctl -u chk-a -f
```

The installer creates the unprivileged `chk-a` user, installs the package into
`/opt/chk-a`, drops config/log/state directories, registers the unit + logrotate,
and enables it.

## Uninstall

To remove the service and every file it installed on the target machine, run the
uninstaller (it only touches installed artifacts under `/opt`, `/etc` and `/var`
— your source checkout is left untouched):

```bash
sudo ./uninstall.sh            # prompts for confirmation
sudo ./uninstall.sh -y         # non-interactive
sudo ./uninstall.sh --keep-user  # keep the chk-a system account
```

What it removes: the `chk-a` systemd unit, the logrotate rule, `/opt/chk-a`,
`/etc/chk-a`, `/var/lib/chk-a`, `/var/log/chk-a`, and (by default) the `chk-a`
system user/group. Equivalent `make` target:

```bash
make uninstall                 # sudo ./uninstall.sh
```

---

## Project layout

```
chk-a/
├── config/                 # settings.yaml + env/config examples
├── md/                     # loop_engineering_prompt.md (authoritative spec)
├── src/chk_a/
│   ├── agents/             # resolver, consensus, ml, alert
│   ├── config/loader.py    # YAML + ${ENV} config loader
│   ├── models/schemas.py   # pydantic contracts
│   ├── storage/            # atomic JSON baseline store
│   ├── utils/              # logger, telegram, systemd_notify, context
│   ├── orchestrator.py     # scheduler + agent wiring
│   ├── validate_config.py  # ExecStartPre hook
│   └── main.py             # CLI entry point
├── systemd/chk-a.service
├── logrotate.d/chk-a
├── install.sh
├── Makefile
└── tests/
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the agent/data-flow design and the
ML details, [RUNBOOK.md](./RUNBOOK.md) for operations and troubleshooting, and
[CONTRIBUTING.md](./CONTRIBUTING.md) for development conventions.
