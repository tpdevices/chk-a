#!/bin/bash
# chk-a deploy script — install synced source to FHS runtime location
# Run on target machine (test/prod) with sudo after rsync from dev
# Usage: sudo /home/ipds/Hermes-Prj/chk-a/scripts/deploy.sh

set -euo pipefail

SRC="/home/ipds/Hermes-Prj/chk-a"
DST="/opt/chk-a"

echo "=== chk-a deploy: $SRC -> $DST ==="

# Verify source exists
if [[ ! -d "$SRC/src/chk_a" ]]; then
    echo "ERROR: Source not found: $SRC/src/chk_a"
    exit 1
fi

# Deploy Python package
echo "Deploying src/chk_a/..."
sudo rsync -avz -c --delete "$SRC/src/chk_a/" "$DST/src/chk_a/"

# Deploy pyproject.toml (for version and package metadata)
echo "Deploying pyproject.toml..."
sudo rsync -avz -c "$SRC/pyproject.toml" "$DST/pyproject.toml"

# Deploy scripts
echo "Deploying scripts/..."
sudo rsync -avz -c "$SRC/scripts/" "$DST/scripts/"

# Deploy config templates (not secrets!)
if [[ -d "$SRC/config" ]]; then
    echo "Deploying config templates..."
    sudo rsync -avz -c "$SRC/config/" "$DST/config/"
fi

# Reinstall Python package to pick up new version
echo "Reinstalling Python package..."
cd "$DST"
sudo /opt/chk-a/.venv/bin/pip install -e . --no-build-isolation 2>&1 | tail -5

# Restart service
echo "Restarting chk-a service..."
sudo systemctl restart chk-a

# Verify
sleep 2
if systemctl is-active --quiet chk-a; then
    echo "=== Deploy successful: chk-a is running ==="
    systemctl status chk-a --no-pager -l | head -10
else
    echo "ERROR: Service failed to start"
    systemctl status chk-a --no-pager -l
    exit 1
fi