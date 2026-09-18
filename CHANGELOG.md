# CHANGELOG

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed
- **2026-09-18 21:00:00** — `src/chk_a/reporting/monthly_report.py` — Fixed: Daily report time range bug. Changed from `datetime.now().replace(hour=23, minute=59) - timedelta(days=1)` (which gave wrong time when run at 06:00) to `yesterday = datetime.now() - timedelta(days=1); yesterday_end = yesterday.replace(hour=23, minute=59)` to correctly get yesterday's 23:59:59.
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — Fixed: Daily midnight task (00:00) error handling for missing images. Added fallback to anomaly/recovery images from AlertAgent, detailed logging for missing images, and graceful skip when no image available.

### Added
- **2026-09-18 21:00:00** — `.github/workflows/release.yml` — Added: Copy `img/` directory to release assets and create `img.tar.gz` for production installation.
- **2026-09-18 21:00:00** — `install.sh` — Added: Download and extract `img.tar.gz` to `/opt/chk-a/img/` during production install.
- **2026-09-18 21:00:00** — `config/config.yaml.example` — Added: Complete configuration example with all sections (fqdns, resolvers, resolver_agent, ml, alert, scheduler, logging, mtr, reporting, baseline_store_path) with Thai comments explaining each setting.
- **2026-09-18 21:00:00** — `config/chk-a.env.example` — Added: Complete environment example with placeholders for Telegram, SMTP, and Age encryption keys.

### Changed
- **2026-09-18 21:00:00** — `src/chk_a/orchestrator.py` — Changed: Improved daily midnight task logging and fallback logic for daily/anomaly/recovery images.

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