#!/usr/bin/env bash
#
# chk-a installer - GitHub Releases distribution
#
# Usage: sudo ./install.sh [version]
#   version: GitHub release tag (e.g., v1.0.0) or "latest" (default)
#
# This script downloads the wheel from GitHub Releases and installs it.
# It does NOT require the source repository to be present.

set -euo pipefail

# Configuration
REPO="tpdevices/chk-a"
INSTALL_DIR="/opt/chk-a"
VENV_DIR="${INSTALL_DIR}/.venv"
ETC_DIR="/etc/chk-a"
LOG_DIR="/var/log/chk-a"
LIB_DIR="/var/lib/chk-a"
SERVICE_USER="chk-a"
SERVICE_GROUP="chk-a"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log()   { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
debug() { [[ "${DEBUG:-0}" -eq 1 ]] && echo -e "${BLUE}[DEBUG]${NC} $*"; }

# Help message
usage() {
    cat <<EOF
Usage: sudo $0 [VERSION]

Install chk-a from GitHub Releases.

Arguments:
  VERSION    GitHub release tag (e.g., v1.0.0) or "latest" (default)

Examples:
  sudo $0              # Install latest release
  sudo $0 v1.0.0       # Install specific version
  sudo $0 v1.0.1       # Upgrade to v1.0.1
  DEBUG=1 sudo $0      # Debug mode

Environment variables:
  REPO              GitHub repository (default: tpdevices/chk-a)
  INSTALL_DIR       Installation directory (default: /opt/chk-a)
  PYTHON_VERSION    Python version to use (default: python3.14)

Files created:
  ${INSTALL_DIR}/         - Application + virtualenv
  ${ETC_DIR}/config.yaml  - Configuration (from template)
  ${ETC_DIR}/env          - Secrets (from template, EDIT REQUIRED)
  ${LOG_DIR}/             - Log files
  ${LIB_DIR}/             - State files (baselines, dedup cache)
  /etc/systemd/system/chk-a.service  - systemd unit
  /etc/logrotate.d/chk-a             - logrotate config

EOF
}

# Parse arguments
VERSION="${1:-latest}"
if [[ "$VERSION" == "-h" || "$VERSION" == "--help" ]]; then
    usage
    exit 0
fi

# Validate root
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (use sudo)"
    exit 1
fi

# Determine download URL
if [[ "$VERSION" == "latest" ]]; then
    DOWNLOAD_BASE="https://github.com/${REPO}/releases/latest/download"
else
    DOWNLOAD_BASE="https://github.com/${REPO}/releases/download/${VERSION}"
fi

WHEEL_URL="${DOWNLOAD_BASE}/chk_a-*-py3-none-any.whl"
INSTALL_SH_URL="${DOWNLOAD_BASE}/install.sh"
MAKEFILE_URL="${DOWNLOAD_BASE}/Makefile"
CONFIG_EXAMPLE_URL="${DOWNLOAD_BASE}/config.yaml.example"
ENV_EXAMPLE_URL="${DOWNLOAD_BASE}/env.example"
SERVICE_URL="${DOWNLOAD_BASE}/chk-a.service"
LOGROTATE_URL="${DOWNLOAD_BASE}/logrotate.chk-a"

log "Installing chk-a ${VERSION} from ${REPO}"
log "Install directory: ${INSTALL_DIR}"

# 1. Create service user and group
log "Creating service user/group..."
if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
    groupadd --system "${SERVICE_GROUP}"
fi
if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin \
        --gid "${SERVICE_GROUP}" --comment "chk-a DNS monitor" "${SERVICE_USER}"
fi

# Create home directory for matplotlib config
mkdir -p "/home/${SERVICE_USER}/.config/matplotlib"
chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "/home/${SERVICE_USER}"

# 2. Create directories
log "Creating directories..."
mkdir -p "${INSTALL_DIR}" "${ETC_DIR}" "${LOG_DIR}" "${LIB_DIR}"
mkdir -p "${LIB_DIR}/matplotlib"

# 3. Download wheel
log "Downloading wheel from GitHub Releases..."
cd /tmp

# Try to get the exact wheel filename from GitHub API first
WHEEL_FILE=$(curl -sL "https://api.github.com/repos/${REPO}/releases/tags/${VERSION}" | grep -o '"name": "chk_a-[^"]*\.whl"' | head -1 | cut -d'"' -f4)

if [[ -z "${WHEEL_FILE}" ]]; then
    # Fallback: try to construct filename from version
    VERSION_NUM=$(echo "${VERSION}" | sed 's/^v//')
    WHEEL_FILE="chk_a-${VERSION_NUM}-py3-none-any.whl"
    log "Using constructed wheel filename: ${WHEEL_FILE}"
fi

WHEEL_URL="${DOWNLOAD_BASE}/${WHEEL_FILE}"

log "Downloading: ${WHEEL_FILE}"
curl -L -o "${WHEEL_FILE}" "${WHEEL_URL}" || {
    err "Failed to download wheel from ${WHEEL_URL}"
    exit 1
}

# 4. Download supplementary files
log "Downloading supplementary files..."
curl -L -o install.sh "${INSTALL_SH_URL}" 2>/dev/null || warn "Could not download install.sh (using embedded)"
curl -L -o Makefile "${MAKEFILE_URL}" 2>/dev/null || warn "Could not download Makefile"
curl -L -o config.yaml.example "${CONFIG_EXAMPLE_URL}" 2>/dev/null || warn "Could not download config.yaml.example"
curl -L -o env.example "${ENV_EXAMPLE_URL}" 2>/dev/null || warn "Could not download env.example"
curl -L -o chk-a.service "${SERVICE_URL}" 2>/dev/null || warn "Could not download chk-a.service"
curl -L -o logrotate.chk-a "${LOGROTATE_URL}" 2>/dev/null || warn "Could not download logrotate.chk-a"

# 5. Setup virtualenv and install wheel
log "Setting up virtualenv..."
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    PYTHON_BIN="${PYTHON_VERSION:-python3.14}"
    if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
        PYTHON_BIN="python3"
        warn "python3.14 not found, falling back to python3"
    fi
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    # Ensure pip is installed (some distributions don't include it by default)
    log "Installing pip via ensurepip..."
    if ! "${VENV_DIR}/bin/python" -m ensurepip --upgrade 2>&1; then
        warn "ensurepip failed, trying get-pip.py..."
        if ! curl -sL https://bootstrap.pypa.io/get-pip.py | "${VENV_DIR}/bin/python" - 2>&1; then
            err "Failed to install pip via get-pip.py"
            exit 1
        fi
    fi
    # Verify pip works
    if ! "${VENV_DIR}/bin/python" -m pip --version >/dev/null 2>&1; then
        err "pip installation verification failed"
        exit 1
    fi
    log "pip installed successfully: $("${VENV_DIR}/bin/python" -m pip --version)"
fi

log "Installing wheel..."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
"${VENV_DIR}/bin/python" -m pip install "${WHEEL_FILE}"

# 6. Deploy config templates
log "Deploying config templates..."
if [[ -f "config.yaml.example" ]]; then
    cp -f "config.yaml.example" "${ETC_DIR}/config.yaml.example"
else
    # Fallback: create minimal config template
    cat > "${ETC_DIR}/config.yaml.example" <<'CFGEOF'
# chk-a Configuration
# Edit this file for your environment

fqdns:
  - name: "example.com"
    expected_ips: ["93.184.216.34"]
    min_consensus: 0.6

resolvers:
  - name: "google"
    address: "8.8.8.8:53"
    weight: 1.0
    timeout_ms: 2000
  - name: "cloudflare"
    address: "1.1.1.1:53"
    weight: 1.0
    timeout_ms: 2000

ml:
  baseline_decay: 0.05
  anomaly_threshold: 0.7
  min_samples_before_alert: 10
  alert_text_log_path: "/var/log/chk-a/alerts.log"

alert:
  alert_text_log_path: "/var/log/chk-a/alerts.log"
  telegram_bot_token: "${TELEGRAM_BOT_TOKEN}"
  telegram_chat_id: "${TELEGRAM_CHAT_ID}"
  dedup_window_minutes: 30
  rate_limit_per_hour: 20
  alert_log_path: "/var/log/chk-a/alerts.jsonl"
  dedup_cache_path: "/var/lib/chk-a/dedup_cache.json"

scheduler:
  min_interval_sec: 30
  max_interval_sec: 180
  jitter: true

logging:
  level: "INFO"
  file: "/var/log/chk-a/checks.jsonl"
  max_size_mb: 50
  backup_count: 10

baseline_store_path: "/var/lib/chk-a/baselines.json"
CFGEOF
fi

if [[ -f "env.example" ]]; then
    cp -f "env.example" "${ETC_DIR}/env.example"
else
    cat > "${ETC_DIR}/env.example" <<'ENVEOF'
# chk-a environment file
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
CHK_A_CONFIG=/etc/chk-a/config.yaml
CHK_A_HEALTH_PORT=0
CHK_A_WATCHDOG_INTERVAL=30
ENVEOF
fi

# Copy actual config/secrets if they don't exist (preserve existing)
[[ -f "${ETC_DIR}/config.yaml" ]] || cp -f "${ETC_DIR}/config.yaml.example" "${ETC_DIR}/config.yaml"
[[ -f "${ETC_DIR}/env" ]] || cp -f "${ETC_DIR}/env.example" "${ETC_DIR}/env"

# 7. Install systemd service and logrotate
log "Installing systemd service and logrotate..."
if [[ -f "chk-a.service" ]]; then
    cp -f "chk-a.service" /etc/systemd/system/chk-a.service
else
    warn "chk-a.service not found in release assets, skipping systemd install"
fi

if [[ -f "logrotate.chk-a" ]]; then
    cp -f "logrotate.chk-a" /etc/logrotate.d/chk-a
else
    warn "logrotate.chk-a not found in release assets, skipping logrotate install"
fi

# 8. Fix ownership and permissions
log "Fixing ownership and permissions..."
chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${LOG_DIR}" "${LIB_DIR}" "${ETC_DIR}"
chmod 0750 "${LOG_DIR}" "${LIB_DIR}" "${ETC_DIR}"
chown root:"${SERVICE_GROUP}" "${ETC_DIR}/config.yaml" "${ETC_DIR}/env" 2>/dev/null || true
chmod 0640 "${ETC_DIR}/config.yaml" 2>/dev/null || true
chmod 0600 "${ETC_DIR}/env" 2>/dev/null || true

# 9. Enable and start service
log "Reloading systemd and enabling service..."
systemctl daemon-reload

if systemctl enable --now chk-a; then
    log "Service started successfully!"
else
    warn "Service failed to start. Check logs:"
    warn "  journalctl -u chk-a -e"
    warn ""
    warn "IMPORTANT: You MUST edit ${ETC_DIR}/env with your Telegram credentials:"
    warn "  TELEGRAM_BOT_TOKEN=your_token"
    warn "  TELEGRAM_CHAT_ID=your_chat_id"
    warn "Then restart: systemctl restart chk-a"
    exit 1
fi

# 10. Summary
echo
log "========================================="
log "  chk-a ${VERSION} installed successfully!"
log "========================================="
echo
log "Configuration:"
log "  Config file: ${ETC_DIR}/config.yaml"
log "  Secrets:     ${ETC_DIR}/env  (REQUIRED: add Telegram credentials)"
log "  Logs:        journalctl -u chk-a -f"
log "  Log files:   ${LOG_DIR}/"
echo
log "Next steps:"
log "  1. Edit ${ETC_DIR}/env with your Telegram bot token and chat ID"
log "  2. Edit ${ETC_DIR}/config.yaml with your FQDNs and resolvers"
log "  3. systemctl restart chk-a"
log "  4. journalctl -u chk-a -f  (watch for 'Cycle complete')"
echo
log "Upgrade later:  sudo $0 v1.0.1"
log "Rollback:       sudo $0 v1.0.0"