# CHANGELOG

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [Unreleased]

- **2026-09-17 12:08:31** — `install.sh` — Fixed: Use correct GitHub API endpoint for latest release; added timeout and progress bar to all downloads; fixed wheel filename resolution for "latest"; always run chown/chmod for config files; added verification step for env file readability.
- **2026-09-17 11:55:16** — `install.sh` — Fixed: Moved env.example check to after download in /tmp; removed silent failure on chown/chmod for critical files; added verification that /etc/chk-a/env is readable by service user before starting service.
- **2026-09-17 11:45:15** — `install.sh` — Fixed: Added check to ensure env.example exists and is not empty after download; if missing or empty, creates a minimal one with placeholder values to prevent missing file errors.
- **2026-09-17 11:37:33** — `install.sh` — Fixed: Changed permission of /etc/chk-a/env from 0600 to 0640 to allow the chk-a service user to read the Telegram credentials.
- **2026-09-17 10:55:37** — `install.sh` — Fixed: Added robust download and extraction of scripts.tar.gz with verification and error handling; ensured ownership of installed files.
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