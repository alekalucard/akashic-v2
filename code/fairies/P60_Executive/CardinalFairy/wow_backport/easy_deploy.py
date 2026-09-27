#!/usr/bin/env python3
"""
Easy Deploy - Shared Memory Deployment (No SSH Required!)
==========================================================

This creates a deployment package that can be synced to Alienware
using ANY method: SMB share, USB drive, rsync, manual copy, etc.

The key insight: Instead of pushing files via SSH, we STAGE files
in a known location and let Alienware PULL them when ready.

Usage:
    python easy_deploy.py stage lua_scripts    # Stage Lua scripts for WoW
    python easy_deploy.py stage cardinal       # Stage Cardinal system
    python easy_deploy.py list                 # Show what's staged
    python easy_deploy.py alienware-setup      # Generate Alienware setup script
"""

import argparse
import json
import shutil
import os
from datetime import datetime
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # akashic_v2
SATELLITE_DIR = PROJECT_ROOT / "fairies" / ".satellite"
DEPLOY_QUEUE = SATELLITE_DIR / "deploy_queue"
DEPLOY_FILES = DEPLOY_QUEUE / "files"

# Source directories
WOW_LUA_SCRIPTS = Path("F:/Sandbox/AzerothCore/lua_scripts/fairy_class")
CARDINAL_BACKPORT = Path(__file__).parent

# Alienware targets
ALIENWARE_TARGETS = {
    "lua_scripts": "/home/ace/AzerothCore/lua_scripts/fairy_class",
    "cardinal": "/home/ace/cardinal_backport",
}


def ensure_dirs():
    """Create deployment directories."""
    DEPLOY_QUEUE.mkdir(parents=True, exist_ok=True)
    DEPLOY_FILES.mkdir(parents=True, exist_ok=True)
    (DEPLOY_QUEUE / "completed").mkdir(exist_ok=True)


def stage_lua_scripts():
    """Stage WoW Lua scripts for deployment."""
    ensure_dirs()

    target_dir = DEPLOY_FILES / "fairy_class"
    target_dir.mkdir(exist_ok=True)

    if not WOW_LUA_SCRIPTS.exists():
        print(f"ERROR: Source not found: {WOW_LUA_SCRIPTS}")
        return False

    print(f"Staging Lua scripts from {WOW_LUA_SCRIPTS}")
    count = 0

    for lua_file in WOW_LUA_SCRIPTS.glob("*.lua"):
        dest = target_dir / lua_file.name
        shutil.copy2(lua_file, dest)
        print(f"  Staged: {lua_file.name}")
        count += 1

    # Update manifest
    update_manifest("lua_scripts", {
        "name": "WoW Fairy Class Lua Scripts",
        "source": str(WOW_LUA_SCRIPTS),
        "staged_dir": "files/fairy_class",
        "target": ALIENWARE_TARGETS["lua_scripts"],
        "file_count": count,
    })

    print(f"\nStaged {count} files to {target_dir}")
    return True


def stage_cardinal():
    """Stage Cardinal backport system for deployment."""
    ensure_dirs()

    target_dir = DEPLOY_FILES / "cardinal_backport"
    target_dir.mkdir(exist_ok=True)

    files = [
        "__init__.py",
        "spell_analyzer.py",
        "knowledge_manager.py",
        "backport_generator.py",
        "cardinal_backport_cli.py",
    ]

    print(f"Staging Cardinal backport from {CARDINAL_BACKPORT}")
    count = 0

    for filename in files:
        src = CARDINAL_BACKPORT / filename
        if src.exists():
            shutil.copy2(src, target_dir / filename)
            print(f"  Staged: {filename}")
            count += 1
        else:
            print(f"  SKIP (not found): {filename}")

    update_manifest("cardinal", {
        "name": "Cardinal WoW Backport System",
        "source": str(CARDINAL_BACKPORT),
        "staged_dir": "files/cardinal_backport",
        "target": ALIENWARE_TARGETS["cardinal"],
        "file_count": count,
    })

    print(f"\nStaged {count} files to {target_dir}")
    return True


def update_manifest(deployment_id: str, info: dict):
    """Update the deployment manifest."""
    manifest_path = DEPLOY_QUEUE / "manifest.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {"version": 1, "deployments": []}

    # Update or add deployment
    info["id"] = deployment_id
    info["status"] = "staged"
    info["staged_at"] = datetime.now().isoformat()

    # Remove old entry if exists
    manifest["deployments"] = [d for d in manifest["deployments"] if d.get("id") != deployment_id]
    manifest["deployments"].append(info)
    manifest["last_updated"] = datetime.now().isoformat()

    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest updated: {manifest_path}")


def list_staged():
    """List what's staged for deployment."""
    manifest_path = DEPLOY_QUEUE / "manifest.json"

    if not manifest_path.exists():
        print("No deployments staged.")
        return

    manifest = json.loads(manifest_path.read_text())

    print("=" * 60)
    print("STAGED DEPLOYMENTS")
    print("=" * 60)

    for dep in manifest.get("deployments", []):
        print(f"\n{dep.get('name', 'Unknown')} ({dep.get('id')})")
        print(f"  Status: {dep.get('status')}")
        print(f"  Files: {dep.get('file_count', '?')}")
        print(f"  Staged: {dep.get('staged_at', '?')}")
        print(f"  Target: {dep.get('target', '?')}")

    print(f"\nDeploy folder: {DEPLOY_QUEUE}")


def generate_alienware_setup():
    """Generate a setup script for Alienware."""
    script = '''#!/bin/bash
# ============================================================
# Alienware Akashic Deploy Receiver
# ============================================================
#
# This script sets up Alienware to receive deployments from
# the shared memory system. Run once to set up, then sync
# the deploy_queue folder however you like (SMB, rsync, USB).
#
# Usage:
#   1. Copy this script to Alienware
#   2. chmod +x alienware_setup.sh
#   3. ./alienware_setup.sh
#

set -e

DEPLOY_ROOT="${HOME}/akashic_deploy"
WATCH_DIR="${DEPLOY_ROOT}/deploy_queue"

echo "=============================================="
echo "  Akashic Shared Memory Deploy Setup"
echo "=============================================="
echo ""

# Create directories
echo "Creating directories..."
mkdir -p "${DEPLOY_ROOT}"
mkdir -p "${WATCH_DIR}/files"
mkdir -p "${WATCH_DIR}/completed"
echo "  Created: ${DEPLOY_ROOT}"

# Create the deploy watcher script
cat > "${DEPLOY_ROOT}/deploy_watcher.sh" << 'WATCHER_EOF'
#!/bin/bash
# Watches for new deployments and applies them

DEPLOY_ROOT="${HOME}/akashic_deploy"
WATCH_DIR="${DEPLOY_ROOT}/deploy_queue"
MANIFEST="${WATCH_DIR}/manifest.json"

echo "Akashic Deploy Watcher"
echo "Watching: ${WATCH_DIR}"
echo "Press Ctrl+C to stop"
echo ""

process_deployment() {
    local staged_dir="$1"
    local target_dir="$2"
    local name="$3"

    echo "Deploying: ${name}"
    echo "  From: ${WATCH_DIR}/${staged_dir}"
    echo "  To: ${target_dir}"

    mkdir -p "${target_dir}"
    cp -r "${WATCH_DIR}/${staged_dir}"/* "${target_dir}/"

    echo "  Done!"
}

while true; do
    if [[ -f "${MANIFEST}" ]]; then
        # Parse manifest and deploy
        # Using simple parsing since jq might not be installed

        while IFS= read -r line; do
            if [[ "${line}" == *'"status": "staged"'* ]]; then
                # Found a staged deployment - extract info
                # This is a simple approach - could use jq for better parsing
                echo "Found staged deployment in manifest"
            fi
        done < "${MANIFEST}"

        # For now, just copy everything from files/ to appropriate places
        if [[ -d "${WATCH_DIR}/files/fairy_class" ]]; then
            process_deployment "files/fairy_class" "/home/ace/AzerothCore/lua_scripts/fairy_class" "WoW Lua Scripts"
        fi

        if [[ -d "${WATCH_DIR}/files/cardinal_backport" ]]; then
            process_deployment "files/cardinal_backport" "/home/ace/cardinal_backport" "Cardinal Backport"
        fi

        # Mark as deployed
        sed -i 's/"status": "staged"/"status": "deployed"/g' "${MANIFEST}" 2>/dev/null || true

        echo ""
        echo "Deployments processed. Waiting for changes..."
    fi

    sleep 5
done
WATCHER_EOF

chmod +x "${DEPLOY_ROOT}/deploy_watcher.sh"
echo "  Created: deploy_watcher.sh"

# Create quick deploy script (for manual runs)
cat > "${DEPLOY_ROOT}/quick_deploy.sh" << 'QUICK_EOF'
#!/bin/bash
# Quick deploy - run once to deploy staged files

DEPLOY_ROOT="${HOME}/akashic_deploy"
WATCH_DIR="${DEPLOY_ROOT}/deploy_queue"

echo "Quick Deploy - Akashic Shared Memory"
echo ""

# Fairy Class Lua Scripts
if [[ -d "${WATCH_DIR}/files/fairy_class" ]]; then
    TARGET="/home/ace/AzerothCore/lua_scripts/fairy_class"
    echo "Deploying Fairy Class Lua Scripts..."
    mkdir -p "${TARGET}"
    cp -rv "${WATCH_DIR}/files/fairy_class"/* "${TARGET}/"
    echo "  Done: ${TARGET}"
    echo ""
fi

# Cardinal Backport
if [[ -d "${WATCH_DIR}/files/cardinal_backport" ]]; then
    TARGET="/home/ace/cardinal_backport"
    echo "Deploying Cardinal Backport..."
    mkdir -p "${TARGET}"
    cp -rv "${WATCH_DIR}/files/cardinal_backport"/* "${TARGET}/"
    echo "  Done: ${TARGET}"
    echo ""
fi

echo "Deployment complete!"
QUICK_EOF

chmod +x "${DEPLOY_ROOT}/quick_deploy.sh"
echo "  Created: quick_deploy.sh"

echo ""
echo "=============================================="
echo "  SETUP COMPLETE"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. SYNC the deploy_queue folder from Windows to:"
echo "   ${WATCH_DIR}"
echo ""
echo "   Options:"
echo "   - Mount SMB share: mount -t cifs //WIN_IP/akashic ${WATCH_DIR}"
echo "   - rsync: rsync -av user@windows:path/deploy_queue/ ${WATCH_DIR}/"
echo "   - USB: cp -r /media/usb/deploy_queue/* ${WATCH_DIR}/"
echo ""
echo "2. RUN the deploy:"
echo "   ${DEPLOY_ROOT}/quick_deploy.sh"
echo ""
echo "   Or run the watcher for auto-deploy:"
echo "   ${DEPLOY_ROOT}/deploy_watcher.sh"
echo ""
'''

    setup_path = DEPLOY_QUEUE / "alienware_setup.sh"
    setup_path.write_text(script)
    print(f"Generated Alienware setup script: {setup_path}")
    print("\nCopy this file to Alienware and run it to set up the receiver.")
    print("Then sync the deploy_queue folder and run quick_deploy.sh")


def main():
    parser = argparse.ArgumentParser(description="Easy Deploy - Shared Memory Deployment")
    parser.add_argument("command", choices=["stage", "list", "alienware-setup"],
                        help="Command to run")
    parser.add_argument("target", nargs="?", choices=["lua_scripts", "cardinal", "all"],
                        help="What to stage")
    args = parser.parse_args()

    if args.command == "stage":
        if not args.target:
            print("ERROR: Specify what to stage: lua_scripts, cardinal, or all")
            return

        if args.target == "lua_scripts" or args.target == "all":
            stage_lua_scripts()

        if args.target == "cardinal" or args.target == "all":
            stage_cardinal()

        print("\n" + "=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print(f"\n1. Sync {DEPLOY_QUEUE} to Alienware:")
        print(f"   - Copy folder via USB/network share")
        print(f"   - Or rsync: rsync -av '{DEPLOY_QUEUE}/' ace@alienware:~/akashic_deploy/deploy_queue/")
        print("\n2. On Alienware, run: ~/akashic_deploy/quick_deploy.sh")

    elif args.command == "list":
        list_staged()

    elif args.command == "alienware-setup":
        generate_alienware_setup()


if __name__ == "__main__":
    main()
