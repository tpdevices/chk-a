#!/usr/bin/env bash
#
# chk-a installer (Loop 6)
#
# Creates the unprivileged 'chk-a' service account, installs the package into
# /opt/chk-a, drops config/log/state dirs, registers the systemd unit and
# logrotate rule, then enables the service.
#
# Run as root:  sudo ./install.sh
#
set -euo pipefail

# Resolve the directory this script lives in (the project root).
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_USER="chk-a"
APP_GROUP="chk-a"
INSTALL_DIR="/opt/chk-a"
ETC_DIR="/etc/chk-a"
LOG_DIR="/var/log/chk-a"
LIB_DIR="/var/lib/chk-a"
SERVICE_SRC="${SRC_DIR}/systemd/chk-a.service"
SERVICE_DST="/etc/systemd/system/chk-a.service"
LOGROTATE_SRC="${SRC_DIR}/logrotate.d/chk-a"
LOGROTATE_DST="/etc/logrotate.d/chk-a"
VENV="${INSTALL_DIR}/.venv"

echo "==> Installing chk-a from ${SRC_DIR}"

# 1. Service account (system user, no login shell, no home dir).
if ! getent group "${APP_GROUP}" >/dev/null 2>&1; then
    echo "==> Creating group ${APP_GROUP}"
    groupadd --system "${APP_GROUP}"
fi
if ! id "${APP_USER}" >/dev/null 2>&1; then
    echo "==> Creating user ${APP_USER}"
    useradd --system --no-create-home --shell /usr/sbin/nologin \
        --gid "${APP_GROUP}" --comment "chk-a DNS monitor" "${APP_USER}"
fi

# 1b. Create home directory for matplotlib config (fixes MPLCONFIGDIR warning).
echo "==> Creating home directory for ${APP_USER}"
mkdir -p "/home/${APP_USER}/.config/matplotlib"
chown -R "${APP_USER}:${APP_GROUP}" "/home/${APP_USER}"

# 2. Directories.
echo "==> Creating directories"
mkdir -p "${INSTALL_DIR}" "${ETC_DIR}" "${LOG_DIR}" "${LIB_DIR}"
mkdir -p "${LIB_DIR}/matplotlib"

# 3. Copy project into the install dir (preserve provenance for -e install).
echo "==> Copying project files to ${INSTALL_DIR}"
# Clean install dir but keep the venv if it already exists.
find "${INSTALL_DIR}" -mindepth 1 -maxdepth 1 ! -name '.venv' -exec rm -rf {} +
cp -a "${SRC_DIR}/src" "${SRC_DIR}/pyproject.toml" "${INSTALL_DIR}/"
cp -a "${SRC_DIR}/config" "${SRC_DIR}/systemd" "${SRC_DIR}/logrotate.d" "${INSTALL_DIR}/" 2>/dev/null || true
cp -a "${SRC_DIR}/img" "${INSTALL_DIR}/" 2>/dev/null || true

# 4. Virtual environment + install.
if [ ! -x "${VENV}/bin/python" ]; then
    echo "==> Creating virtualenv at ${VENV}"
    python3 -m venv "${VENV}"
    # Ensure pip exists (Ubuntu 26.04+ may not include it by default)
    "${VENV}/bin/python" -m ensurepip --upgrade 2>/dev/null || true
fi
echo "==> Installing package (editable)"
"${VENV}/bin/python" -m pip install --upgrade pip >/dev/null
"${VENV}/bin/python" -m pip install -e "${INSTALL_DIR}"

# 5. Config + env (copy example; do not overwrite an existing live config).
echo "==> Installing config templates"
cp -f "${SRC_DIR}/config/chk-a.config.yaml.example" "${ETC_DIR}/config.yaml.example"
cp -f "${SRC_DIR}/config/chk-a.env.example" "${ETC_DIR}/env.example"
if [ ! -f "${ETC_DIR}/config.yaml" ]; then
    cp -f "${ETC_DIR}/config.yaml.example" "${ETC_DIR}/config.yaml"
fi
if [ ! -f "${ETC_DIR}/env" ]; then
    cp -f "${ETC_DIR}/env.example" "${ETC_DIR}/env"
fi

# 6. systemd unit + logrotate.
echo "==> Installing systemd unit and logrotate rule"
cp -f "${SERVICE_SRC}" "${SERVICE_DST}"
cp -f "${LOGROTATE_SRC}" "${LOGROTATE_DST}"

# 7. Ownership + permissions.
echo "==> Fixing ownership"
chown -R "${APP_USER}:${APP_GROUP}" "${LOG_DIR}" "${LIB_DIR}" "${ETC_DIR}"
chmod 0750 "${LOG_DIR}" "${LIB_DIR}" "${ETC_DIR}"
# SEC-017: Config file permissions - root owner, chk-a group, 600 for secrets
chown root:"${APP_GROUP}" "${ETC_DIR}/config.yaml" "${ETC_DIR}/env" 2>/dev/null || true
chmod 0640 "${ETC_DIR}/config.yaml" 2>/dev/null || true
chmod 0600 "${ETC_DIR}/env" 2>/dev/null || true

# 8. Enable + start.
echo "==> Reloading systemd and enabling service"
systemctl daemon-reload
systemctl enable --now chk-a || {
    echo "!! Service failed to start. Check: journalctl -u chk-a -e"
    echo "!! Remember to fill in TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in ${ETC_DIR}/env"
    exit 1
}

echo "==> chk-a installed and enabled."
echo "    Config : ${ETC_DIR}/config.yaml"
echo "    Secrets: ${ETC_DIR}/env  (set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)"
echo "    Logs   : journalctl -u chk-a -f"
