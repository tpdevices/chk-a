# Runbook

Operations, troubleshooting, and alert-response procedures for `chk-a`.

---

## Common operations

### Install / upgrade
```bash
sudo ./install.sh
sudo systemctl daemon-reload
sudo systemctl restart chk-a
```

### Status
```bash
systemctl status chk-a
journalctl -u chk-a -f
```

### Validate config before (re)start
```bash
sudo /opt/chk-a/.venv/bin/python -m chk_a.validate-config
# or via the installed entry point
chk-a-validate
```
The systemd unit runs this as `ExecStartPre`; a broken config blocks startup.

### Run a single cycle (no daemon)
```bash
sudo -u chk-a /opt/chk-a/.venv/bin/python -m chk_a.check-once
```

### Inspect the learned baseline
```bash
sudo -u chk-a /opt/chk-a/.venv/bin/python -m chk_a.show-baseline
```

### Send a Telegram test message
```bash
sudo -u chk-a /opt/chk-a/.venv/bin/python -m chk_a.test-telegram
```

### Health check
```bash
curl -s http://localhost:8080/healthz   # if CHK_A_HEALTH_PORT set
```

---

## Configuration changes

1. Edit `/etc/chk-a/config.yaml` (or `config/settings.yaml` in dev).
2. `sudo systemctl restart chk-a`.
3. Watch `journalctl -u chk-a -f` for the first cycle and any `CONFIG ERROR`.

To rotate the Telegram token, edit `/etc/chk-a/env` and `systemctl restart chk-a`
(`EnvironmentFile=` is re-read on restart).

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Service fails to start, `journalctl` shows `CONFIG ERROR` | Broken/missing config | Run `chk-a-validate`; fix `config.yaml`. |
| `Type=notify` timeout / service killed after ~90s | sd_notify not reaching systemd | Ensure `WatchdogSec` matches the ping interval; check `systemd_notify` logs. (We use a dependency-free helper, no `python-systemd` needed.) |
| No alerts arriving | Token/chat id wrong, or rate-limited | Run `chk-a test-telegram`; check `alert_log_path` JSONL; verify `rate_limit_per_hour`. |
| Alerts suppressed | Dedup window active | Same `(fqdn,type,ips)` within `dedup_window_minutes` is expected; widen if needed. |
| High `anomalies_total` early on | Baseline still learning | `min_samples_before_alert` gates alerts; wait for samples to accumulate. |
| `checks_total{...,result="failure"}` rising | A resolver is flaky/unreachable | Check `resolver_success_rate` / `resolver_avg_latency_ms`; remove or reweight the resolver. |
| Baseline "forgets" a legit IP | `baseline_decay` too high | Lower `ml.baseline_decay` (e.g. 0.02). |
| Too many false positives | `anomaly_threshold` too low | Raise `ml.anomaly_threshold` (e.g. 0.8). |

---

## Alert response

When a `baseline_deviation` or `consensus_deviation` alert fires:

1. **Confirm** — open the alert JSONL (`alert_log_path`) and read `observed_ips`,
   `baseline_ips`, `consensus_score`, `resolver_count`, and the `correlation_id`.
2. **Correlate** — grep logs for the same `correlation_id` to see per-resolver
   results and which resolvers were flagged as outliers.
3. **Triage**
   - **Legit change** (planned migration, CDN rotation): let the baseline re-learn;
     optionally clear `/var/lib/chk-a/baselines.json` for a clean start.
   - **Single-resolver outlier**: usually a poisoned/cached resolver — check that
     resolver's `resolver_success_rate`; consider removing it.
   - **Real hijack / DNS poisoning**: treat as a security incident — the observed
     IPs differ from the learned baseline across *most* resolvers.
4. **Reset baseline if needed**
   ```bash
   sudo systemctl stop chk-a
   sudo rm -f /var/lib/chk-a/baselines.json
   sudo systemctl start chk-a
   ```

---

## Log locations

- Application JSONL: `/var/log/chk-a/checks.jsonl`
- Alert audit JSONL: `/var/log/chk-a/alerts.jsonl`
- systemd journal: `journalctl -u chk-a`
- Baseline store: `/var/lib/chk-a/baselines.json`

All log lines within one cycle share a `correlation_id` for tracing.
