#!/bin/bash
# ============================================================================
# Satellite Setup Script - Deploy akashic_v2 to satellite node
# ============================================================================
#
# Usage:
#   bash setup_satellite.sh [satellite_ip] [username]
#
# This will:
#   1. Set up passwordless SSH (if needed)
#   2. rsync the entire akashic_v2 codebase to satellite
#   3. Generate satellite node_identity.json
#   4. Install Python dependencies
#   5. Create systemd service for auto-start
#
# "The shadow research society runs in parallel"
# ============================================================================

set -e

SATELLITE_IP="${1:-192.168.1.24}"
SATELLITE_USER="${2:-alaksander}"
SATELLITE_PATH="/home/${SATELLITE_USER}/akashic_v2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Detect primary IP (first non-loopback IP)
PRIMARY_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "auto")

echo "=============================================="
echo "  AKASHIC V2 SATELLITE DEPLOYMENT"
echo "=============================================="
echo "  Satellite IP:   $SATELLITE_IP"
echo "  Satellite User: $SATELLITE_USER"
echo "  Satellite Path: $SATELLITE_PATH"
echo "  Primary IP:     $PRIMARY_IP"
echo "  Source:         $PROJECT_DIR"
echo "=============================================="
echo ""

# Step 1: Ensure SSH key exists
echo "[1/6] Checking SSH setup..."
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo "  No SSH key found. Generating..."
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
fi

# Test passwordless SSH
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "${SATELLITE_USER}@${SATELLITE_IP}" "echo ok" &>/dev/null; then
    echo "  Copying SSH key to satellite..."
    ssh-copy-id -i ~/.ssh/id_rsa.pub "${SATELLITE_USER}@${SATELLITE_IP}"
fi
echo "  SSH: OK"

# Step 2: rsync codebase
echo "[2/6] Syncing codebase to satellite..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='state/' \
    --exclude='*.pyc' \
    --exclude='.satellite/deploy_queue/' \
    --exclude='boot_*.log' \
    --exclude='*.log' \
    "${PROJECT_DIR}/" \
    "${SATELLITE_USER}@${SATELLITE_IP}:${SATELLITE_PATH}/"
echo "  Sync: OK"

# Step 3: Create state directory and node identity on satellite
echo "[3/6] Generating satellite identity..."
SATELLITE_HOSTNAME=$(ssh "${SATELLITE_USER}@${SATELLITE_IP}" "hostname")
ssh "${SATELLITE_USER}@${SATELLITE_IP}" "mkdir -p ${SATELLITE_PATH}/state && cat > ${SATELLITE_PATH}/state/node_identity.json << IDEOF
{
    \"name\": \"alienware\",
    \"role\": \"satellite\",
    \"hostname\": \"${SATELLITE_HOSTNAME}\",
    \"platform\": \"Linux\",
    \"primary_ip\": \"${PRIMARY_IP}\",
    \"created\": \"$(date -Iseconds)\"
}
IDEOF"
echo "  Identity: OK"

# Step 4: Install Python dependencies (if requirements.txt exists)
echo "[4/6] Checking Python dependencies..."
if [ -f "${PROJECT_DIR}/requirements.txt" ]; then
    ssh "${SATELLITE_USER}@${SATELLITE_IP}" "cd ${SATELLITE_PATH} && pip3 install -r requirements.txt 2>/dev/null || pip install -r requirements.txt 2>/dev/null || echo 'pip install skipped'"
else
    echo "  No requirements.txt found, skipping"
fi
echo "  Dependencies: OK"

# Step 5: Create systemd service
echo "[5/6] Creating systemd service..."
ssh "${SATELLITE_USER}@${SATELLITE_IP}" "cat > /tmp/akashic-satellite.service << 'SVCEOF'
[Unit]
Description=Akashic V2 Satellite Server
After=network.target

[Service]
Type=simple
User=${SATELLITE_USER}
WorkingDirectory=${SATELLITE_PATH}
ExecStart=/usr/bin/python3 ${SATELLITE_PATH}/server.py --satellite
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF
"

ssh "${SATELLITE_USER}@${SATELLITE_IP}" "sudo mv /tmp/akashic-satellite.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable akashic-satellite" 2>/dev/null || echo "  systemd setup skipped (may need sudo)"
echo "  Service: OK"

# Step 6: Start satellite
echo "[6/6] Starting satellite..."
ssh "${SATELLITE_USER}@${SATELLITE_IP}" "sudo systemctl restart akashic-satellite" 2>/dev/null || {
    echo "  systemd start failed, trying manual start..."
    ssh "${SATELLITE_USER}@${SATELLITE_IP}" "cd ${SATELLITE_PATH} && nohup python3 server.py --satellite > /tmp/akashic-satellite.log 2>&1 &"
}

# Wait a moment and check
sleep 3
echo ""
echo "=============================================="
echo "  SATELLITE DEPLOYMENT COMPLETE!"
echo "=============================================="
echo ""
echo "  Verify satellite is running:"
echo "    curl http://${SATELLITE_IP}:8081/health"
echo ""
echo "  Check status:"
echo "    ssh ${SATELLITE_USER}@${SATELLITE_IP} 'systemctl status akashic-satellite'"
echo ""
echo "  View logs:"
echo "    ssh ${SATELLITE_USER}@${SATELLITE_IP} 'journalctl -u akashic-satellite -f'"
echo ""
echo "  Manual start:"
echo "    ssh ${SATELLITE_USER}@${SATELLITE_IP} 'cd ${SATELLITE_PATH} && python3 server.py --satellite'"
echo ""
echo "  Re-deploy (after code changes):"
echo "    bash ${SCRIPT_DIR}/setup_satellite.sh ${SATELLITE_IP} ${SATELLITE_USER}"
echo "=============================================="
