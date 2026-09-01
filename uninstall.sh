#!/usr/bin/env bash
#
# chk-a uninstaller
#
# Removes every file and directory that install.sh created on the target
# machine. It does NOT touch the source checkout (e.g. /home/ipds/Hermes-Prj/chk-a)
# — only the installed artifacts under /opt, /etc and /var.
#
# Run as root:  sudo ./uninstall.sh
# Non-interactive:  sudo ./uninstall.sh -y
# Keep the service account:  sudo ./uninstall.sh --keep-user
#
set -euo pipefail

# ---- paths installed by install.sh (kept in sync with install.sh) ----
SERVICE_NAME="chk-a"
INSTALL_DIR="/opt/chk-a"
CONFIG_DIR="/etc/chk-a"
STATE_DIR="/var/lib/chk-a"
LOG_DIR="/var/log/chk-a"
SYSTEMD_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
LOGROTATE_CONF="/etc/logrotate.d/${SERVICE_NAME}"
APP_USER="chk-a"
APP_GROUP="chk-a"

# ---- flags ----
ASSUME_YES=0
KEEP_USER=0
while [ $# -gt 0 ]; do
    case "$1" in
        -y|--yes) ASSUME_YES=1 ;;
        --keep-user) KEEP_USER=1 ;;
        -h|--help)
            echo "Usage: sudo ./uninstall.sh [-y] [--keep-user]"
            echo "  -y, --yes      Do not prompt for confirmation"
            echo "  --keep-user    Do not delete the ${APP_USER} system account"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

# ---- colors ----
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; NC=''
fi
log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- root check ----
if [ "$(id -u)" -ne 0 ]; then
    log_error "This script must be run as root (use sudo)."
    exit 1
fi

# ---- confirmation ----
if [ "${ASSUME_YES}" -ne 1 ]; then
    echo "This will remove the chk-a service and all installed files:"
    echo "  - systemd unit : ${SYSTEMD_UNIT}"
    echo "  - logrotate    : ${LOGROTATE_CONF}"
    echo "  - install dir  : ${INSTALL_DIR}"
    echo "  - config dir   : ${CONFIG_DIR}"
    echo "  - state dir    : ${STATE_DIR}"
    echo "  - log dir      : ${LOG_DIR}"
    [ "${KEEP_USER}" -ne 1 ] && echo "  - service user : ${APP_USER} (system account)"
    echo
    read -r -p "Continue? [y/N] " reply
    case "${reply}" in
        y|Y|yes|YES) ;;
        *) log_warn "Aborted."; exit 0 ;;
    esac
fi

log_info "Uninstalling ${SERVICE_NAME}..."

# ---- 1. stop + disable the service (before deleting its files) ----
if systemctl list-unit-files "${SERVICE_NAME}.service" >/dev/null 2>&1; then
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        log_info "Stopping ${SERVICE_NAME} service..."
        systemctl stop "${SERVICE_NAME}" || log_warn "Failed to stop service (continuing)."
    fi
    if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        log_info "Disabling ${SERVICE_NAME} service..."
        systemctl disable "${SERVICE_NAME}" || log_warn "Failed to disable service (continuing)."
    fi
fi

# ---- 2. remove systemd unit + logrotate ----
if [ -f "${SYSTEMD_UNIT}" ]; then
    log_info "Removing systemd unit ${SYSTEMD_UNIT}"
    rm -f "${SYSTEMD_UNIT}"
fi
if [ -f "${LOGROTATE_CONF}" ]; then
    log_info "Removing logrotate rule ${LOGROTATE_CONF}"
    rm -f "${LOGROTATE_CONF}"
fi
log_info "Reloading systemd daemon..."
systemctl daemon-reload || log_warn "daemon-reload failed (continuing)."

# ---- 3. remove installed directories ----
for d in "${INSTALL_DIR}" "${CONFIG_DIR}" "${STATE_DIR}" "${LOG_DIR}"; do
    if [ -e "${d}" ]; then
        log_info "Removing ${d}"
        rm -rf "${d}"
    else
        log_info "Already absent: ${d}"
    fi
done

# ---- 4. remove the service account (created by install.sh) ----
if [ "${KEEP_USER}" -ne 1 ]; then
    if id "${APP_USER}" >/dev/null 2>&1; then
        log_info "Removing user ${APP_USER}"
        userdel "${APP_USER}" 2>/dev/null || log_warn "userdel failed (continuing)."
    fi
    if getent group "${APP_GROUP}" >/dev/null 2>&1; then
        log_info "Removing group ${APP_GROUP}"
        groupdel "${APP_GROUP}" 2>/dev/null || log_warn "groupdel failed (continuing)."
    fi
else
    log_info "Keeping service account ${APP_USER} (--keep-user)."
fi

log_info "chk-a has been uninstalled."
log_info "The source checkout was NOT touched."
