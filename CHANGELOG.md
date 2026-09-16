# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **2026-09-16 09:45:00** — `src/chk_a/agents/resolver_agent.py` — Added: DoT (DNS-over-TLS) support via `dns.nameserver.DoTNameserver`. Implemented `_build_dot_nameserver()` with hostname-to-IP resolution for SNI verification, `_query_dot()` using `dns.asyncquery.tls()`. DoH (DNS-over-HTTPS) rewritten to use DNS wireformat (`application/dns-message`) per RFC 8484 for broad provider compatibility.
- **2026-09-16 09:45:00** — `src/chk_a/models/schemas.py` — Added: DoT URL validation in `ResolverConfig._validate_address()` — accepts `tls://host:port` format with RFC 1123 hostname/IP validation and port range check.
- **2026-09-16 09:45:00** — `config/config.yaml` — Added: Documented DoH and DoT resolver examples in config (commented).
- **2026-09-16 09:45:00** — `tests/test_config_loader.py` — Added: `test_resolver_address_valid_dot_url()` and invalid DoT URL test cases.
- **2026-09-16 09:45:00** — `tests/test_resolver_agent.py` — Added: `test_dot_resolver_is_marker()` and `test_dot_resolver_resolves()` unit tests.

### Fixed
- **2026-09-16 09:45:00** — `src/chk_a/agents/resolver_agent.py` — Fixed: DoH now uses wireformat (`application/dns-message`) with POST method instead of JSON API. Works with Google, Cloudflare, and other DoH providers.
- **2026-09-16 09:45:00** — `src/chk_a/agents/resolver_agent.py` — Fixed: DoT `_build_dot_nameserver()` resolves hostname to IP address before creating `DoTNameserver` (dnspython requires IP in address field, hostname for SNI).

### Security
- **2026-09-16 09:45:00** — SEC-010: DoH/DoT support in ResolverAgent — enables encrypted DNS queries for privacy and integrity. All 3 protocols supported: Standard DNS (UDP/TCP 53), DoH (HTTPS 443), DoT (TLS 853).
- **2026-09-16 10:15:00** — `systemd/chk-a.service` — Fixed: Added `CapabilityBoundingSet=CAP_NET_RAW` and `AmbientCapabilities=CAP_NET_RAW` for MTR ICMP mode raw socket access.
- **2026-09-16 10:15:00** — `scripts/systemd_wrapper.py` — Fixed: Changed state file path from `/opt/chk-a/last_state.txt` to `/var/lib/chk-a/last_state.txt` to work with `ProtectSystem=strict` (read-only /opt/chk-a).
- **2026-09-16 11:30:00** — SEC-013: Log file permissions hardening — added configurable `file_mode` (default 0o640) and `dir_mode` (default 0o750) to `LoggingConfig` and `AlertConfig`. Updated `setup_logger()` and `AlertAgent._setup_alert_log_handlers()` to apply permissions on file/directory creation and rotation. Verified on test VM: files 640 (rw-r-----), dirs 750 (rwxr-x---), owned by chk-a:chk-a.

### Added
- **2026-09-15 09:45:00** — `src/chk_a/reporting/ml_insights.py` — Added: Baseline-based integrity scoring using `MLAgent.score()` (total-variation distance against learned baseline) replacing Isolation Forest. New `_compute_integrity_baseline_based()` function computes per-resolver integrity by comparing observed IPs against per-FQDN baselines. Avoids false anomalies when multiple resolvers fail simultaneously (e.g., network outage).
- **2026-09-15 09:45:00** — `src/chk_a/reporting/ml_insights.py` — Added: `ml_agent` parameter to `generate_ml_insights()` and `compute_integrity()` for baseline-based integrity. Falls back to Isolation Forest when `ml_agent` is None (backward compatibility).
- **2026-09-15 09:45:00** — `src/chk_a/reporting/monthly_report.py` — Added: Creates `MLAgent` with `BaselineStore` for both monthly and daily report generation. Passes `ml_agent` to `generate_ml_insights()` for baseline-based integrity scoring.
- **2026-09-15 09:45:00** — `src/chk_a/reporting/graph_generator.py` — Modified: `generate_integrity_chart()` uses `.get("is_anomaly", score < 50)` to support both Isolation Forest and baseline-based integrity data formats.

### Changed
- **2026-09-15 09:45:00** — `src/chk_a/reporting/telegram_reporter.py` — Changed: `create_daily_telegram_summary()` Integrity section renamed to "Response Integrity (Baseline Consistency)" with success rate displayed. Anomalous resolvers section changed to Thai "Resolver ปัญหา Integrity (ML Detected)" with both integrity score and success rate.
- **2026-09-15 09:45:00** — `test_send_daily_report.py` — Updated: Creates `MLAgent` with `BaselineStore` and passes to `generate_ml_insights()` for baseline-based integrity testing.

### Fixed
- **2026-09-15 11:15:00** — `src/chk_a/reporting/ml_insights.py` — Fixed: `_load_recent_checks()` now filters only CheckResult records (must have `fqdn`, `resolver`, `success` fields) to skip log messages (cycle complete, next cycle, etc.) that lack these fields. Prevents NaN columns and KeyError in downstream `compute_availability()`.
- **2026-09-15 11:15:00** — `src/chk_a/reporting/ml_insights.py` — Fixed: `_load_recent_checks()` timestamp parsing handles mixed naive and timezone-aware ISO8601 timestamps. Uses `pd.to_datetime(df["timestamp"], format="mixed", utc=True).dt.tz_localize(None)` to convert all to UTC then drop timezone for consistent naive comparison. Works with both real log format (naive) and mock data format (timezone-aware +07:00).
- **2026-09-15 10:35:00** — `src/chk_a/reporting/ml_insights.py` — Fixed: `_load_recent_checks()` timezone handling for daily report. Added `reference_date` parameter and timezone-aware comparison (Asia/Bangkok +07). Now correctly loads yesterday's data when reference_date is set to end of yesterday. Enables accurate daily report using yesterday's mock/test data.

### Fixed
- **2026-09-15 12:25:00** — `src/chk_a/reporting/ml_insights.py` — Fixed: `_load_recent_checks()` now reads rotated log files (date-stamped `.bz2` and numbered `.gz` backups) automatically. Collects all rotated files from the same directory, opens them with appropriate decompressors (bz2/gzip), filters by date range from filenames, and merges with current log. Enables daily report (1-day lookback) and monthly report (30-day lookback) to read historical data spanning multiple rotated files.
- **2026-09-15 12:25:00** — `src/chk_a/reporting/monthly_report.py` — Confirmed: `generate_ml_insights()` already supports `reference_date` parameter for accurate yesterday/month-end targeting. Daily report function uses `datetime.now() - timedelta(days=1)` as reference to correctly target yesterday's rotated logs.
- **2026-09-15 14:15:00** — `src/chk_a/reporting/ml_insights.py` — Fixed: `_compute_integrity_baseline_based()` now computes and includes `unique_ip_count` and `ip_stability` in `raw_features` for baseline-based integrity. These metrics were previously only computed in Isolation Forest fallback, enabling IP Stability & Diversity chart for baseline method.
- **2026-09-15 14:15:00** — `src/chk_a/orchestrator.py` — Added: `_send_missing_daily_report()` method to check and generate yesterday's daily report on service startup if missing. Called in `run()` after task initialization. Checks `output_dir` for yesterday's report directory; if absent, generates report using `reference_date=yesterday 23:59:59` and sends to Telegram with same format as scheduled 06:00 report.

### Security
- **2026-09-15 09:45:00** — Baseline-based integrity prevents false positive anomalies during mass resolver failures. Isolation Forest flagged the only working resolver as "anomaly" when 6/7 resolvers failed identically. Baseline scoring evaluates each resolver independently against its learned IP baseline.

### Added
- **2026-09-14 14:30:00** — `scripts/deploy.sh` — Added: Deploy script to install synced source from `/home/ipds/Hermes-Prj/chk-a/` to FHS runtime `/opt/chk-a/` on target machine (test/prod). Uses `rsync -c` checksum verification and restarts systemd service. Run with `sudo` after dev→test sync.
- **2026-09-14 14:30:00** — `/etc/chk-a/config.yaml` (test VM) — Added: Missing `daily_report_*` settings to reporting section (`daily_report_enabled`, `daily_report_hour`, `daily_report_minute`, `daily_report_telegram_enabled`, `daily_report_telegram_chat_id`, `daily_report_lookback_days`).

### Fixed
- **2026-09-14 14:30:00** — Runtime code mismatch resolved — Verified hash equality between Dev source `/home/ipds/Hermes-Prj/chk-a/` and Runtime `/opt/chk-a/` (MD5: `b7717b974eab7b7d163300430e2fdf08`). Executed `scripts/deploy.sh` on test VM to sync and restart service.
- **2026-09-13 23:45:00** — `src/chk_a/agents/alert_agent.py` — Fixed: Added log rotation for alert JSONL and plain text logs using `logging.handlers.RotatingFileHandler`. New config fields `alert_log_max_size_mb` and `alert_log_backup_count` in `AlertConfig` (M-08).
- **2026-09-13 23:45:00** — `src/chk_a/models/schemas.py` — Added: `alert_log_max_size_mb` and `alert_log_backup_count` fields to `AlertConfig` for M-08 log rotation configuration.
- **2026-09-13 23:45:00** — `src/chk_a/reporting/graph_generator.py` — Fixed: Thai font loading robustness. Changed to try direct path access first, fallback to `resources.as_file()` context manager only when needed. Creates `FontProperties` inside context to avoid path invalidation (M-07).
- **2026-09-13 23:45:00** — `src/chk_a/orchestrator.py` — Fixed: Health server port now reads from config (`SchedulerConfig.health_port`) instead of environment variable. Both port and bind address now from same config object for consistency (M-06).
- **2026-09-13 23:45:00** — `src/chk_a/models/schemas.py` — Added: `health_port` field to `SchedulerConfig` with validation (0-65535, default=0 disabled).
- **2026-09-13 23:45:00** — `src/chk_a/agents/ml_agent.py` — Fixed: Path learning key collision. Changed prefix from `__path__` to `chk-a:path:` (contains `:` which is forbidden in DNS labels, preventing collision with real FQDNs). Moved prefix to class constant (M-03).
- **2026-09-13 23:45:00** — `src/chk_a/agents/consensus_agent.py` — Fixed: Reputation EMA now only updates for successful results with IPs. Failed/empty results (NXDOMAIN, timeout, etc.) no longer decay resolver reputation (M-02).
- **2026-09-13 23:45:00** — `src/chk_a/agents/resolver_agent.py` — Fixed: Implemented DoH support. Added `_query_doh()` method using `aiohttp` for RFC 8484 DNS JSON format. Removed `NotImplementedError` stub (M-01).
- **2026-09-13 23:45:00** — `src/chk_a/agents/alert_agent.py` — Fixed: Added `asyncio.Lock` protection for token bucket (`_rate_limit_lock`) and dedup cache (`_dedup_lock`) to prevent race conditions (C-01, C-02).
- **2026-09-13 23:45:00** — `src/chk_a/orchestrator.py` — Fixed: Daily report and midnight schedulers now use `ZoneInfo("Asia/Bangkok")` for timezone-aware datetime operations. Absolute time scheduling from fixed reference point prevents drift (H-01).
- **2026-09-13 23:45:00** — `src/chk_a/agents/mtr_agent.py` — Fixed: MTR timeout calculation corrected from `timeout_sec * max_hops + 30` to `max_hops * count * timeout_sec + 60` (H-02).
- **2026-09-13 23:45:00** — `src/chk_a/storage/baseline_store.py` — Fixed: Age key caching. Private/public keys loaded once at initialization and cached. Private key only loaded when decryption needed (H-03).
- **2026-09-13 23:45:00** — `src/chk_a/utils/telegram_client.py` — Fixed: `send_photo()` now streams file via `aiofiles` chunked read instead of `read_bytes()` full memory load (H-04).
- **2026-09-13 23:45:00** — `src/chk_a/orchestrator.py` — Fixed: `_write_check_results()` now batches writes (single `write()` per cycle) instead of line-by-line (H-05).
- **2026-09-13 23:45:00** — `src/chk_a/reporting/telegram_reporter.py` — Fixed: CircuitBreaker now supports both sync and async `can_execute()`. Added internal `_can_execute_locked()` helper. Concurrent graph sending via `asyncio.gather()`. Added `try/finally` for `reporter.close()` (M-05).
- **2026-09-13 12:00:00** — `src/chk_a/reporting/telegram_reporter.py` — Fixed: TelegramReporter now uses token in URL path (required by Telegram Bot API) instead of Authorization header. Daily report 06:00 AM was failing with 404 Not Found. Midnight image at 00:00 worked because it uses TelegramClient (token in URL).
- **2026-09-13 12:00:00** — `tests/test_security_regressions.py` — Updated: Security regression tests for SEC-003 and SEC-007 to verify token-in-URL behavior instead of Authorization header.

### Security
- **2026-09-13 23:45:00** — C-01: AlertAgent token bucket race condition — added `asyncio.Lock` protection for token bucket refill/check/consume sequence.
- **2026-09-13 23:45:00** — C-02: AlertAgent dedup cache race condition — added `asyncio.Lock` protection for all dedup cache operations.
- **2026-09-13 23:45:00** — H-01: Orchestrator timezone-naive scheduler — all datetime operations now use `ZoneInfo("Asia/Bangkok")`.
- **2026-09-13 23:45:00** — H-02: MTR agent timeout calculation — corrected formula with clear comment.
- **2026-09-13 23:45:00** — H-03: BaselineStore age key caching — lazy load and cache keys at init.
- **2026-09-13 23:45:00** — H-04: TelegramClient send_photo memory — streaming via `aiofiles` instead of full memory load.
- **2026-09-13 23:45:00** — H-05: Orchestrator batch writes — single `write()` per cycle.
- **2026-09-13 23:45:00** — M-01: ResolverAgent DoH support — implemented RFC 8484 DNS-over-HTTPS.
- **2026-09-13 23:45:00** — M-02: ConsensusAgent reputation for failed results — skip failed/empty results in reputation EMA.
- **2026-09-13 23:45:00** — M-03: MLAgent path learning key collision — prefix `chk-a:path:` prevents DNS collision.
- **2026-09-13 23:45:00** — M-04: Parallel MTR for outliers — `asyncio.gather` instead of sequential.
- **2026-09-13 23:45:00** — M-05: CircuitBreaker thread-safety — sync/async methods; concurrent sending via `asyncio.gather`.
- **2026-09-13 23:45:00** — M-06: Health server port/address consistency — both from config.
- **2026-09-13 23:45:00** — M-07: Graph generator Thai font loading — robust path handling.
- **2026-09-13 23:45:00** — M-08: AlertAgent log rotation — `RotatingFileHandler` for JSONL and plain text logs.

### Changed
- **2026-09-13 23:45:00** — `tests/test_loop7.py` — Updated: Tests now use `tmp_path` fixture for alert log paths instead of hardcoded `/var/log/chk-a/` (which requires root).
- **2026-09-13 23:45:00** — `tests/test_resolver_agent.py` — Updated: `test_doh_returns_not_supported` renamed to `test_doh_resolver_resolves`, properly mocks aiohttp session as async context manager.

---

## [1.0.0] - 2026-08-29

### Added
- Initial project structure for chk-a DNS A-record monitor
- Multi-agent architecture: Resolver → Consensus → ML → Alert → Orchestrator + MTR
- Systemd service definitions for all agents
- Telegram alerting with deduplication cache persistence
- Daily report generation at midnight with hostname
- Thai language support (fonts-thai-tlwg Loma) for all Thai elements
- Heatmap charts with local time labels (Asia/Bangkok +07)
- MTR agent with CLI integration

### Changed
- N/A (initial release)

### Fixed
- N/A (initial release)

---

## Template for Future Entries

### Added
- **YYYY-MM-DD HH:MM:SS** — Description of new feature/file

### Changed
- **YYYY-MM-DD HH:MM:SS** — Description of modification to existing file

### Fixed
- **YYYY-MM-DD HH:MM:SS** — Description of bug fix

### Removed
- **YYYY-MM-DD HH:MM:SS** — Description of removed feature/file

### Security
- **YYYY-MM-DD HH:MM:SS** — Description of security-related change

---

## Rules for Maintaining This Changelog

1. **Every file change MUST be logged** with:
   - Date and time (local timezone: Asia/Bangkok +07)
   - File path relative to project root
   - Type of change: Added / Changed / Fixed / Removed / Security
   - Brief description of what changed

2. **Format for each entry:**
   ```
   - **YYYY-MM-DD HH:MM:SS** — `path/to/file.ext` — Type: Description
   ```

3. **When to update:** Immediately after any file modification (create, edit, delete)

4. **Where to add:** Under the appropriate section for the current version, or create a new `[Unreleased]` section if needed

5. **Version releases:** When releasing a new version, move `[Unreleased]` entries to a new version section with the release date