# CHANGELOG

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.29] - 2026-09-21 15:30:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-21 11:00:00** — `src/chk_a/main.py` — Fixed: MTR CLI target validation auto-appends `:53` for bare IP/hostname, allowing CLI to accept bare IP/hostname as target argument without manual port specification.
- **2026-09-21 15:30:00** — Test VM Python cache issue: Python `.pyc` cache in `/opt/chk-a/.venv/lib/python3.14/site-packages/chk_a/__pycache__/` was serving stale `__init__.py` (v0.1.0). Cleared cache with `sudo find /opt/chk-a/.venv -name '*.pyc' -path '*/chk_a/*' -delete` to serve updated `__version__` (1.0.29).

### Changed
- **2026-09-21 11:00:00** — `pyproject.toml` — Bumped version to 1.0.29.
- **2026-09-21 15:30:00** — Updated documentation: Added cache clearing step to Test VM deployment guide.

---

## [1.0.28] - 2026-09-21 10:30:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-21 10:30:00** — `src/chk_a/__init__.py` — Fixed: Version detection now works both when installed as package and when running as module (`-m chk_a.main`). Added fallback to read from `pyproject.toml`.
- **2026-09-21 10:30:00** — `src/chk_a/main.py` — Fixed: CLI commands `test-telegram` and `test-daily-image` now properly extract secret values from `SecretStr` before passing to `TelegramClient`, fixing "Object of type SecretStr is not JSON serializable" error.

### Changed
- **2026-09-21 10:30:00** — `pyproject.toml` — Bumped version to 1.0.28.

---

## [1.0.27] - 2026-09-21 08:00:00 (Asia/Bangkok UTC+07)

### Added
- **2026-09-21 08:00:00** — Version display across all reports:
  - Graphs: Version shown in footer center (`vX.Y.Z`) via `_add_header_footer()` in `graph_generator.py`
  - Telegram Monthly Summary: Version at end of message via `create_telegram_summary()` in `telegram_reporter.py`
  - Telegram Daily Summary: Version at end of message via `create_daily_telegram_summary()` in `telegram_reporter.py`
  - Dashboard/Reports: Version passed through `generate_summary_dashboard()` to all 8 chart types

### Changed
- **2026-09-21 08:00:00** — `src/chk_a/__init__.py` — `__version__` now reads from `importlib.metadata` (package version) instead of hardcoded
- **2026-09-21 08:00:00** — `src/chk_a/reporting/monthly_report.py` — Monthly & scheduled daily reports pass version to graphs and Telegram
- **2026-09-21 08:00:00** — `src/chk_a/orchestrator.py` — Startup & missing daily reports pass version to graphs and Telegram
- **2026-09-21 08:00:00** — `pyproject.toml` — Bumped version to 1.0.27

---

## [1.0.26] - 2026-09-21 06:30:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-21 06:30:00** — `src/chk_a/reporting/monthly_report.py` — Fixed: Scheduled daily report (06:00 AM) now merges month data (1st to yesterday) for daily availability heatmap, instead of only yesterday's data. Consistent with startup report behavior.

### Changed
- **2026-09-21 06:30:00** — `pyproject.toml` — Bumped version to 1.0.26.

---

## [1.0.25] - 2026-09-20 17:30:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-20 17:30:00** — `src/chk_a/orchestrator.py` — Fixed: Missing daily report on startup now merges month data (Sep 1 to yesterday) for daily availability heatmap, instead of only yesterday's data.
- **2026-09-20 17:30:00** — `src/chk_a/reporting/graph_generator.py` — Fixed: Daily availability heatmap title now shows correct day range format "Days 1 to N" (English) / "วันที่ 1 ถึง N" (Thai) instead of "Month: 1st to DD MMM".

### Added
- **2026-09-20 17:30:00** — `src/chk_a/orchestrator.py` — Added: Month data loading for missing daily report. Merges `daily_availability` from month insights (Sep 1 to yesterday) into yesterday insights.

### Changed
- **2026-09-20 17:30:00** — `src/chk_a/reporting/graph_generator.py` — Changed: Daily heatmap title format from "Month: 1st to DD MMM" to "Days 1 to N" / "วันที่ 1 ถึง N" for clarity.

---

## [1.0.24] - 2026-09-20 15:40:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-20 15:40:00** — `src/chk_a/orchestrator.py` — Fixed: Service startup report now sends Thai-only graphs with today's data (00:00 to now) and daily availability heatmap showing month context (Sep 1 to today). Uses dual data loading (today + month) merged before graph generation.
- **2026-09-20 15:40:00** — `src/chk_a/orchestrator.py` — Fixed: Startup report runs as background task (`asyncio.create_task`) to avoid blocking service startup and systemd timeout (90s).

### Added
- **2026-09-20 15:40:00** — `src/chk_a/orchestrator.py` — Added: Month data loading for daily availability heatmap in startup report. Merges `daily_availability` from month insights (Sep 1 to now) into today insights.
- **2026-09-20 15:40:00** — `src/chk_a/orchestrator.py` — Added: Background task handling for startup report with proper shutdown wait in `Orchestrator.shutdown()`.

### Changed
- **2026-09-20 15:40:00** — `src/chk_a/orchestrator.py` — Changed: `_send_today_report_on_startup()` now uses `today_end` (23:59:59) as reference date with fractional lookback for today data, and separate `month_lookback` for month data (Sep 1 to now).

---

## [1.0.22] - 2026-09-20 14:30:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-20 14:30:00** — `scripts/manual_daily_report.py` — Fixed: Manual daily report now correctly generates single report with Thai-only graphs. Uses `send_daily_report_telegram()` which filters Thai-only (`-th.png`) and sends sequentially.
- **2026-09-20 14:30:00** — `src/chk_a/reporting/graph_generator.py` — Fixed: Latency boxplot now correctly sorts by median latency ASC (fastest on top) by adding `ax.invert_yaxis()`. Cloudflare (~15ms) now at top, SDNS (~266ms) at bottom.
- **2026-09-20 14:30:00** — `scripts/manual_daily_report.py` — Fixed: Daily availability heatmap now shows month context (Sep 1 to today) instead of only today's data, by merging today insights with month insights for `daily_availability`.

### Added
- **2026-09-20 14:30:00** — `scripts/manual_daily_report.py` — Added: Dual data loading — today data (midnight to now) for hourly heatmap/latency/integrity, and month data (Sep 1 to now) for daily availability heatmap. Merged before graph generation.
- **2026-09-20 14:30:00** — `src/chk_a/reporting/ml_insights.py` — Added: `generate_ml_insights()` and `_load_mtr_data()` now accept `float` for `lookback_days` to support fractional lookback (e.g., hours since midnight).
- **2026-09-20 14:30:00** — `src/chk_a/reporting/telegram_reporter.py` — Added: `send_daily_report_telegram()` and `create_daily_telegram_summary()` now accept `float` for `lookback_days`.

### Changed
- **2026-09-20 14:30:00** — `scripts/manual_daily_report.py` — Changed: Replaced custom Telegram sending logic with `send_daily_report_telegram()` to leverage Thai-only filtering and sequential sending with 0.5s delay.
- **2026-09-20 14:30:00** — `src/chk_a/reporting/ml_insights.py` — Changed: `lookback_days` parameter type from `int` to `float` for fractional day support.
- **2026-09-20 14:30:00** — `src/chk_a/reporting/telegram_reporter.py` — Changed: `lookback_days` parameter type from `int` to `float` for consistency.

---

## [1.0.21] - 2026-09-19 06:50:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-19 06:50:00** — `src/chk_a/reporting/telegram_reporter.py` — Fixed: Added warning log when non-Thai graphs are filtered out and debug log for all received graph paths. This helps identify which English graphs are leaking through the Thai-only filter.
- **2026-09-19 06:50:00** — `src/chk_a/orchestrator.py` — Fixed: Added debug logging for startup report time parameters (now, today_midnight, hours_since_midnight, lookback_fraction) and generated graph filenames.
- **2026-09-19 06:50:00** — `src/chk_a/reporting/monthly_report.py` — Fixed: Added debug logging for scheduled daily report graph filenames.

### Added
- **2026-09-19 06:50:00** — `src/chk_a/reporting/telegram_reporter.py` — Added: Warning log `FILTERED OUT non-Thai graphs (N): [...]` when English graphs are detected and filtered out.
- **2026-09-19 06:50:00** — `src/chk_a/orchestrator.py` — Added: Debug logs for startup report time calculation and graph filenames.
- **2026-09-19 06:50:00** — `src/chk_a/reporting/monthly_report.py` — Added: Debug logs for scheduled daily report graph filenames.

### Changed
- **2026-09-19 06:50:00** — `src/chk_a/reporting/telegram_reporter.py` — Changed: Thai filter now robustly checks both `-th.png` suffix and `-th` stem. Added warning log when non-Thai graphs are filtered out.
- **2026-09-19 06:50:00** — `src/chk_a/orchestrator.py` — Changed: Enhanced debug logging for `_send_today_report_on_startup()` and `_send_missing_daily_report()`.

---

## [1.0.20] - 2026-09-19 10:00:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-19 10:00:00** — `src/chk_a/reporting/ml_insights.py` — Fixed: `_load_recent_checks()` now properly handles timezone-aware comparisons. Parse timestamps without `utc=True`, keep in Asia/Bangkok local time, proper tz-aware comparison between log timestamps and cutoff. Supports fractional `lookback_days` for midnight-to-now reports.
- **2026-09-19 10:00:00** — `src/chk_a/reporting/telegram_reporter.py` — Fixed: Robust Thai filtering now checks both `-th.png` suffix and `-th` stem. Added warning log when non-Thai graphs are filtered out.

### Changed
- **2026-09-19 10:00:00** — `src/chk_a/reporting/ml_insights.py` — Changed: `_load_recent_checks()` timezone handling rewritten. Debug logging added for verification.
- **2026-09-19 10:00:00** — `src/chk_a/reporting/telegram_reporter.py` — Changed: Thai filter now checks both `-th.png` suffix and `-th` stem. Warning log when non-Thai graphs filtered.

---

## [1.0.19] - 2026-09-19 09:00:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-19 10:00:00** — `src/chk_a/reporting/graph_generator.py` — Fixed: `generate_summary_dashboard()` now adds language suffix to filenames (`-th` for Thai, none for English). This allows `telegram_reporter.py` to correctly filter and send only Thai graphs (`-th.png`). Filename format changed from `name-timestamp.png` to `nametimestamp-lang.png`.

### Added
- **2026-09-19 10:00:00** — `src/chk_a/reporting/graph_generator.py` — Added: Language suffix (`lang_suffix`) to all generated graph filenames (e.g., `availability-bar20260919-143000-th.png`).

### Changed
- **2026-09-19 10:00:00** — `src/chk_a/reporting/graph_generator.py` — Changed: `generate_summary_dashboard()` adds language suffix to filenames for filtering. Format: `nametimestamp-lang.png` (e.g., `availability-bar20260919-143000-th.png`). Enables correct Thai-only filtering in telegram_reporter.

---

## [1.0.18] - 2026-09-19 09:00:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-19 09:30:00** — `src/chk_a/orchestrator.py` — Fixed: Indentation error in `_send_missing_daily_report()` method (lines 1202-1220). Fixed malformed try/except blocks with duplicate/broken exception handling.
- **2026-09-19 09:30:00** — `src/chk_a/reporting/monthly_report.py` — Fixed: `generate_daily_report()` now uses timezone-aware datetime (Asia/Bangkok) and generates THAI-ONLY graphs for Telegram consistency. Removed English graph generation for daily scheduled report.
- **2026-09-19 09:30:00** — `src/chk_a/orchestrator.py` — Fixed: `_send_today_report_on_startup()` now correctly calculates lookback window from midnight to now using fractional lookback days instead of fixed 24h lookback.

### Changed
- **2026-09-19 09:30:00** — `src/chk_a/reporting/monthly_report.py` — Changed: `generate_daily_report()` now generates THAI-ONLY graphs for scheduled daily report (consistent with telegram_reporter sequential sending). Removed English graph generation.
- **2026-09-19 09:30:00** — `src/chk_a/orchestrator.py` — Changed: `_send_today_report_on_startup()` and `_send_missing_daily_report()` now consistent in using THAI-ONLY graphs and proper timezone handling.

---

## [1.0.17] - 2026-09-19 09:00:00 (Asia/Bangkok UTC+07)

### Changed
- **2026-09-19 09:00:00** — `src/chk_a/reporting/graph_generator.py` — Changed: `generate_latency_boxplot()` now sorts resolvers by median latency ASC (fastest on top). Added sort indicator subtitle to title. Consistency with "best on top" pattern across all charts.

---

## [1.0.16] - 2026-09-19 08:30:00 (Asia/Bangkok UTC+07)

### Changed
- **2026-09-19 08:30:00** — `src/chk_a/reporting/telegram_reporter.py` — Changed: Telegram report sending now sequential (one-by-one) instead of concurrent. Only Thai-language graphs (suffix -th.png) are sent. Added 0.5s delay between sends to avoid rate limiting. Detailed logging for each graph send result.

---

## [1.0.15] - 2026-09-18 23:55:00 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-18 21:00:00** — `src/chk_a/reporting/monthly_report.py` — Fixed: Daily report time range bug. Changed from `datetime.now().replace(hour=23, minute=59) - timedelta(days=1)` (which gave wrong time when run at 06:00) to `yesterday = datetime.now() - timedelta(days=1); yesterday_end = yesterday.replace(hour=23, minute=59)` to correctly get yesterday's 23:59:59.
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — Fixed: Daily midnight task (00:00) error handling for missing images. Added fallback to anomaly/recovery images from AlertAgent, detailed logging for missing images, and graceful skip when no image available.
- **2026-09-19 09:30:00** — `src/chk_a/orchestrator.py` — Fixed: Indentation error in `_send_missing_daily_report()` method (lines 1202-1220). Fixed malformed try/except blocks with duplicate/broken exception handling.
- **2026-09-19 09:30:00** — `src/chk_a/reporting/monthly_report.py` — Fixed: `generate_daily_report()` now uses timezone-aware datetime (Asia/Bangkok) and generates THAI-ONLY graphs for Telegram consistency. Removed English graph generation for daily scheduled report.
- **2026-09-19 09:30:00** — `src/chk_a/orchestrator.py` — Fixed: `_send_today_report_on_startup()` now correctly calculates lookback window from midnight to now using fractional lookback days instead of fixed 24h lookback.
- **2026-09-19 10:00:00** — `src/chk_a/reporting/graph_generator.py` — Fixed: `generate_summary_dashboard()` now adds language suffix to filenames (`-th` for Thai, none for English). This allows `telegram_reporter.py` to correctly filter and send only Thai graphs (`-th.png`). Filename format changed from `name-timestamp.png` to `nametimestamp-lang.png`.

### Added
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — Added: Copy `img/` directory to release assets and create `img.tar.gz` for production installation.
- **2026-09-18 21:00:00** — `install.sh` — Added: Download and extract `img.tar.gz` to `/opt/chk-a/img/` during production install.
- **2026-09-18 21:00:00** — `config/config.yaml.example` — Added: Complete configuration example with all sections (fqdns, resolvers, resolver_agent, ml, alert, scheduler, logging, mtr, reporting, baseline_store_path) with Thai comments explaining each setting.
- **2026-09-18 21:00:00** — `config/chk-a.env.example` — Added: Complete environment example with placeholders for Telegram, SMTP, and Age encryption keys.
- **2026-09-19 08:00:00** — `TODO.md` — Added: FQDN-centric data model & storage task (Medium priority). Includes schema (FQDNRecord), new fqdn_store.py, resolver_agent ingestion pipeline, and orchestrator scheduler integration for traceability & correlation.

### Changed
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — Changed: Improved daily midnight task logging and fallback logic for daily/anomaly/recovery images.
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — Changed: Use new complete `config/config.yaml.example` in release assets instead of old `config/chk-a.config.yaml.example`.
- **2026-09-19 08:30:00** — `src/chk_a/reporting/telegram_reporter.py` — Changed: Telegram report sending now sequential (one-by-one) instead of concurrent. Only Thai-language graphs (suffix -th.png) are sent. Added 0.5s delay between sends to avoid rate limiting. Detailed logging for each graph send result.
- **2026-09-19 09:00:00** — `src/chk_a/reporting/graph_generator.py` — Changed: `generate_latency_boxplot()` now sorts resolvers by median latency ASC (fastest on top). Added sort indicator subtitle to title. Consistency with "best on top" pattern across all charts.
- **2026-09-19 09:30:00** — `src/chk_a/reporting/monthly_report.py` — Changed: `generate_daily_report()` now generates THAI-ONLY graphs for scheduled daily report (consistent with telegram_reporter sequential sending). Removed English graph generation.
- **2026-09-19 09:30:00** — `src/chk_a/orchestrator.py` — Changed: `_send_today_report_on_startup()` and `_send_missing_daily_report()` now consistent in using THAI-ONLY graphs and proper timezone handling.
- **2026-09-19 10:00:00** — `src/chk_a/reporting/graph_generator.py` — Changed: `generate_summary_dashboard()` adds language suffix to filenames for filtering. Format: `nametimestamp-lang.png` (e.g., `availability-bar20260919-143000-th.png`). Enables correct Thai-only filtering in telegram_reporter.

---

## [1.0.14] - 2026-09-17 20:30:00 (Asia/Bangkok UTC+07)

### Added
- **2026-09-17 14:47:55** — `scripts/manual_daily_report.py`, `scripts/manual_monthly_report.py` — Added: Manual on-demand report scripts. `manual_daily_report.py` generates daily report from midnight to now. `manual_monthly_report.py` generates monthly report from 1st of month to now. Both send Thai summary + graphs to Telegram on demand.
- **2026-09-17 14:45:00** — `scripts/manual_daily_report.py` — Added: On-demand daily report script (midnight to now) with Thai/English summaries and graphs sent to Telegram.
- **2026-09-17 14:30:00** — `scripts/manual_monthly_report.py` — Added: On-demand monthly report script (1st of month to now) with Thai/English summaries and graphs sent to Telegram.
- **2026-09-17 20:00:00** — Daily Availability Heatmap for monthly reports — Added `generate_availability_daily_heatmap()` in `graph_generator.py` and `daily_availability` computation in `ml_insights.py`. Monthly reports now include both hourly and daily heatmaps (2 heatmaps × EN/TH = 4 additional graphs).

### Fixed
- **2026-09-17 14:47:55** — `pyproject.toml` — Fixed: Python requirement already at 3.10+ (v1.0.13), confirmed compatibility with Ubuntu 22.04 LTS.
- **2026-09-17 15:30:00** — `src/chk_a/reporting/telegram_reporter.py` — Fixed: Monthly report now shows ALL resolvers (not just Top 5) in text summary. Daily/Monthly reports now send ALL graphs (removed 5/6 graph limit).
- **2026-09-17 19:30:00** — `scripts/manual_daily_report.py`, `scripts/manual_monthly_report.py` — Fixed: Manual report scripts now show ALL resolvers (removed hardcoded `[:10]` limits in availability, path availability, and integrity sections). Updated labels from "Top 10" to "All Resolvers".

### Security
- **2026-09-17 10:30:00** — SEC-014: HTML escape in Telegram messages — added `_html_escape()` function and applied to all user-supplied data in `TelegramClient.send_message()`, `TelegramClient.send_photo()`, `create_telegram_summary()`, and `create_daily_telegram_summary()`. Added security regression tests for HTML injection prevention.

### Changed
- **2026-09-17 14:59:20** — `scripts/` — Added manual report scripts for on-demand reporting (daily from midnight, monthly from 1st of month).
- **2026-09-17 15:30:00** — `src/chk_a/reporting/telegram_reporter.py` — Changed: Monthly summary now lists all resolvers; all generated graphs are sent to Telegram.
- **2026-09-17 19:30:00** — `scripts/manual_daily_report.py`, `scripts/manual_monthly_report.py` — Changed: Manual reports now display all resolvers instead of limiting to 10.
- **2026-09-17 20:00:00** — `src/chk_a/reporting/ml_insights.py`, `src/chk_a/reporting/graph_generator.py` — Added daily availability heatmap to monthly reports (shows day-of-month vs resolver availability matrix).

---

## [1.0.13] - 2026-09-17 13:32:37 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 13:32:37** — `pyproject.toml` — Fixed: Lowered Python requirement from 3.11+ to 3.10+ to support Ubuntu 22.04 LTS (Python 3.10.12). Added conditional dependency `backports.zoneinfo` for Python <3.9. Updated Black target versions to py310/py311.

### Added
- **2026-09-17 13:32:37** — `pyproject.toml` — Added: Conditional dependency `backports.zoneinfo; python_version < "3.9"` for zoneinfo support on Python 3.10.

---

## [1.0.12] - 2026-09-17 12:39:20 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 12:39:20** — `telegram_client.py`, `systemd_wrapper.py` — Fixed: Removed HTML auto-escape from TelegramClient (caller responsibility). Added proper HTML escaping in systemd_wrapper.py for hostname and details. HTML parsing in Telegram now renders correctly (bold, monospace, etc.).

### Security
- **2026-09-17 12:39:20** — SEC-014: HTML escape in Telegram messages — removed auto-escape from TelegramClient, shifted responsibility to callers for proper HTML escaping.

---

## [1.0.11] - 2026-09-17 12:26:18 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 12:26:18** — `schemas.py` / `orchestrator.py` — Fixed: Changed default reporting.output_dir from "reports" to "/var/lib/chk-a/reports" to avoid read-only filesystem error under ProtectSystem=strict. Ensures daily/monthly reports can be written.

---

## [1.0.10] - 2026-09-17 12:14:41 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 12:14:41** — `install.sh` — Fixed: Use dedicated temp directory (mktemp) for downloads; remove existing files before download; added download helper with cleanup; fixed pip verification typo; ensures clean downloads and avoids permission issues.

---

## [1.0.9] - 2026-09-17 12:08:31 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 12:08:31** — `install.sh` — Fixed: Use correct GitHub API endpoint for latest release; added timeout and progress bar to all downloads; fixed wheel filename resolution for "latest"; always run chown/chmod for config files; added verification step for env file readability.

---

## [1.0.8] - 2026-09-17 11:55:16 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 11:55:16** — `install.sh` — Fixed: Moved env.example check to after download in /tmp; removed silent failure on chown/chmod for critical files; added verification that /etc/chk-a/env is readable by service user before starting service.

---

## [1.0.7] - 2026-09-17 11:45:15 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 11:45:15** — `install.sh` — Fixed: Added check to ensure env.example exists and is not empty after download; if missing or empty, creates a minimal one with placeholder values to prevent missing file errors.

---

## [1.0.6] - 2026-09-17 11:37:33 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 11:37:33** — `install.sh` — Fixed: Changed permission of /etc/chk-a/env from 0600 to 0640 to allow the chk-a service user to read the Telegram credentials.

---

## [1.0.5] - 2026-09-17 11:45:15 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 11:45:15** — `install.sh` — Fixed: Ensure env.example is present and not empty after download.

---

## [1.0.4] - 2026-09-17 10:55:37 (Asia/Bangkok UTC+07)

### Fixed
- **2026-09-17 10:55:37** — `install.sh` — Fixed: Added robust download and extraction of scripts.tar.gz with verification and error handling; ensured ownership of installed files.

---

## [1.0.3] - 2026-09-17 10:10:05 (Asia/Bangkok UTC+07)

### Security
- **2026-09-17 10:30:00** — SEC-014: HTML escape in Telegram messages — added `_html_escape()` function and applied to all user-supplied data in `TelegramClient.send_message()`, `TelegramClient.send_photo()`, `create_telegram_summary()`, and `create_daily_telegram_summary()`. Added security regression tests for HTML injection prevention.

### Fixed
- **2026-09-17 11:00:00** — `install.sh` — Fixed: venv reuse bug where existing venv from failed installation skipped pip installation. Added `NEED_PIP_INSTALL` flag to verify pip presence in existing venv and install if missing. Improved logging for pip installation steps.

### Added
- **2026-09-17 11:15:00** — `MANIFEST.in` — Added: `include scripts/*.py` to ensure scripts directory is included in the wheel.
- **2026-09-17 11:20:00** — `.github/workflows/release.yml` — Added: Copy scripts directory to release assets and create `scripts.tar.gz` for easy download.
- **2026-09-17 11:25:00** — Build system: Updated wheel to include `scripts/` directory, ensuring `systemd_wrapper.py` and `systemd_notify.py` are installed.

---

## [1.0.2] - 2026-09-16

### Added
- **2026-09-16 14:30:00** — `install.sh` — Improved pip installation in virtualenv: uses `ensurepip` with output logging, fallback to `get-pip.py` if ensurepip fails, verification with version logging. Better error handling for venv creation.
- **2026-09-16 14:30:00** — `install.sh` — Added detailed logging for each pip installation step: "Installing pip via ensurepip...", "pip installed successfully: pip X.Y.Z from ...", "Falling back to get-pip.py...", "pip installed via get-pip.py: pip X.Y.Z from ..."

### Fixed
- **2026-09-16 14:30:00** — `install.sh` — Fixed: pip installation now properly handles edge cases where venv is created but pip is not available. Added explicit verification step after installation.

### Known Issues
- **2026-09-16 14:30:00** — `install.sh` — Venv reuse bug: if venv exists from a previous failed installation, pip installation is skipped because the check only verifies python binary exists. Workaround: `sudo rm -rf /opt/chk-a/.venv && sudo ./install.sh v1.0.2`. Fix planned: add pip verification in venv existence check.

---

## [1.0.1] - 2026-09-16

### Fixed
- **2026-09-16 09:30:00** — `install.sh` — Fixed: Wheel filename resolution now uses GitHub API (`/releases/tags/v{version}`) instead of guessing pattern. Handles variable wheel names like `chk_a-0.1.0-py3-none-any.whl`.
- **2026-09-16 09:30:00** — `install.sh` — Added: Pip installation fallback using `get-pip.py` when `ensurepip` is not available or fails.
- **2026-09-16 09:30:00** — `install.sh` — Fixed: Wheel download URL construction to match actual GitHub Release asset naming.

### Added
- **2026-09-16 09:30:00** — `install.sh` — Added error handling and logging for wheel download, supplementary files download, and pip installation steps.

---

## [1.0.0] - 2026-09-16

### Added
- **2026-09-16 08:00:00** — `.github/workflows/release.yml` — GitHub Actions workflow to build wheel on tag push (v*), create GitHub Release with assets (wheel, install.sh, uninstall.sh, Makefile, config.yaml.example, env.example, chk-a.service, logrotate.chk-a).
- **2026-09-16 08:00:00** — `install.sh` — Production installer: downloads wheel + assets from GitHub Releases, creates venv, installs wheel, configures systemd services, sets up logrotate.
- **2026-09-16 08:00:00** — `uninstall.sh` — Production uninstaller: removes all service files, configs, logs, state, and user.
- **2026-09-16 08:00:00** — `Makefile` — Targets: `install`, `install-github`, `uninstall`, `upgrade`, `status`, `logs`, `version`, `release-dry-run`.
- **2026-09-16 08:00:00** — `config.yaml.example` — Example configuration for production deployments.
- **2026-09-16 08:00:00** — `env.example` — Example environment file for Telegram credentials.
- **2026-09-16 08:00:00** — `systemd/chk-a.service` — Systemd service template with security hardening (ProtectSystem=strict, CapabilityBoundingSet=CAP_NET_RAW, etc.).
- **2026-09-16 08:00:00** — `logrotate.chk-a` — Logrotate configuration for `/var/log/chk-a/*.log` and `/var/log/chk-a/*.jsonl`.

### Security
- **2026-09-16 08:00:00** — Production installer follows security best practices: dedicated service user (chk-a, uid=999), config permissions 640, env permissions 600, log directory permissions 750, systemd hardening.

---

## [0.1.0] - 2026-08-29

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