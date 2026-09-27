#!/usr/bin/env python3
"""
Deploy Cardinal WoW Backport System to Alienware (192.168.1.24)
===============================================================

This script:
1. Checks SSH connectivity to Alienware
2. Creates necessary directories
3. Copies the backport system files
4. Verifies Ollama is running
5. Creates a systemd service for auto-start (optional)

Prerequisites:
- SSH key auth configured for Alienware
- Ollama installed on Alienware with Mistral model
- Python 3.10+ on Alienware

Usage:
    python deploy_alienware.py
    python deploy_alienware.py --setup-service
"""

import argparse
import subprocess
import sys
from pathlib import Path

ALIENWARE_IP = "192.168.1.24"
ALIENWARE_USER = "alaksander"  # FIX 2026-02-09: was "ace", actual username is "alaksander"
REMOTE_PATH = "/home/alaksander/cardinal_backport"

# Files to deploy
FILES_TO_DEPLOY = [
    "__init__.py",
    "spell_analyzer.py",
    "knowledge_manager.py",
    "backport_generator.py",
    "cardinal_backport_cli.py",
]


def run_ssh(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run command on Alienware via SSH."""
    full_cmd = f'ssh {ALIENWARE_USER}@{ALIENWARE_IP} "{cmd}"'
    return subprocess.run(full_cmd, shell=True, capture_output=True, text=True, check=check)


def run_scp(local: str, remote: str) -> bool:
    """Copy file to Alienware via SCP."""
    cmd = f"scp {local} {ALIENWARE_USER}@{ALIENWARE_IP}:{remote}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    return result.returncode == 0


def check_connectivity():
    """Check SSH connectivity to Alienware."""
    print(f"Checking SSH connectivity to {ALIENWARE_IP}...")
    try:
        result = run_ssh("echo 'SSH OK'", check=False)
        if result.returncode == 0:
            print("  SSH connection: OK")
            return True
        else:
            print(f"  SSH connection: FAILED")
            print(f"  Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"  SSH connection: ERROR - {e}")
        return False


def check_ollama():
    """Check if Ollama is running on Alienware."""
    print("Checking Ollama status...")
    try:
        result = run_ssh("curl -s http://localhost:11434/api/tags", check=False)
        if result.returncode == 0 and "models" in result.stdout:
            print("  Ollama: RUNNING")

            # Check for Mistral model
            if "mistral" in result.stdout.lower():
                print("  Mistral model: AVAILABLE")
            else:
                print("  Mistral model: NOT FOUND")
                print("  Run: ollama pull mistral")

            return True
        else:
            print("  Ollama: NOT RUNNING")
            print("  Run: ollama serve")
            return False
    except Exception as e:
        print(f"  Ollama: ERROR - {e}")
        return False


def create_directories():
    """Create necessary directories on Alienware."""
    print("Creating directories...")

    dirs = [
        REMOTE_PATH,
        f"{REMOTE_PATH}/knowledge",
        f"{REMOTE_PATH}/output",
        f"{REMOTE_PATH}/dbc",
    ]

    for d in dirs:
        run_ssh(f"mkdir -p {d}", check=False)
        print(f"  Created: {d}")


def deploy_files():
    """Deploy Python files to Alienware."""
    print("Deploying files...")

    local_dir = Path(__file__).parent

    for filename in FILES_TO_DEPLOY:
        local_path = local_dir / filename
        if local_path.exists():
            remote_path = f"{REMOTE_PATH}/{filename}"
            if run_scp(str(local_path), remote_path):
                print(f"  Deployed: {filename}")
            else:
                print(f"  FAILED: {filename}")
        else:
            print(f"  SKIP (not found): {filename}")


def create_wrapper_script():
    """Create a wrapper script for easy CLI access."""
    print("Creating wrapper script...")

    wrapper = f'''#!/bin/bash
# Cardinal WoW Backport CLI Wrapper
cd {REMOTE_PATH}
python3 cardinal_backport_cli.py "$@"
'''

    # Write to temp file locally
    temp_path = Path("/tmp/cardinal_backport")
    temp_path.write_text(wrapper)

    # Copy to Alienware
    run_scp(str(temp_path), f"{REMOTE_PATH}/cardinal_backport")

    # Make executable
    run_ssh(f"chmod +x {REMOTE_PATH}/cardinal_backport")

    # Create symlink in ~/bin
    run_ssh(f"mkdir -p ~/bin && ln -sf {REMOTE_PATH}/cardinal_backport ~/bin/cardinal_backport", check=False)

    print("  Wrapper created: ~/bin/cardinal_backport")


def setup_systemd_service():
    """Create systemd service for auto-start (optional)."""
    print("Setting up systemd service...")

    service = f'''[Unit]
Description=Cardinal WoW Backport Knowledge Server
After=network.target ollama.service

[Service]
Type=simple
User={ALIENWARE_USER}
WorkingDirectory={REMOTE_PATH}
ExecStart=/usr/bin/python3 -m http.server 8765 --directory {REMOTE_PATH}/output
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
'''

    # This would require sudo, so just print instructions
    print("  To enable auto-start, run these commands on Alienware:")
    print()
    print(f"  sudo tee /etc/systemd/system/cardinal-backport.service << 'EOF'")
    print(service)
    print("  EOF")
    print()
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable cardinal-backport")
    print("  sudo systemctl start cardinal-backport")


def verify_deployment():
    """Verify the deployment works."""
    print("Verifying deployment...")

    # Try to import the module
    result = run_ssh(f"cd {REMOTE_PATH} && python3 -c 'from spell_analyzer import SpellAnalyzer; print(\"OK\")'", check=False)

    if result.returncode == 0 and "OK" in result.stdout:
        print("  Import test: PASSED")
    else:
        print("  Import test: FAILED")
        print(f"  Error: {result.stderr}")
        return False

    # Try the CLI
    result = run_ssh(f"cd {REMOTE_PATH} && python3 cardinal_backport_cli.py stats", check=False)

    if result.returncode == 0:
        print("  CLI test: PASSED")
    else:
        print("  CLI test: FAILED")
        print(f"  Error: {result.stderr}")
        return False

    return True


def print_usage():
    """Print usage instructions."""
    print()
    print("=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Usage on Alienware:")
    print()
    print("  # Analyze a spell")
    print("  cardinal_backport analyze 116")
    print()
    print("  # Generate backport")
    print("  cardinal_backport backport 116")
    print()
    print("  # Search spells")
    print("  cardinal_backport search 'frostbolt' --online")
    print()
    print("  # Query knowledge")
    print("  cardinal_backport query 'How do I backport a DoT?'")
    print()
    print("Output directory: " + f"{REMOTE_PATH}/output")
    print("Knowledge base: " + f"{REMOTE_PATH}/knowledge")
    print()


def main():
    parser = argparse.ArgumentParser(description="Deploy Cardinal Backport to Alienware")
    parser.add_argument("--setup-service", action="store_true", help="Setup systemd service")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing deployment")
    args = parser.parse_args()

    print("=" * 60)
    print("Cardinal WoW Backport System - Alienware Deployment")
    print("=" * 60)
    print()

    # Check connectivity
    if not check_connectivity():
        print()
        print("ERROR: Cannot connect to Alienware")
        print(f"Make sure SSH is configured for {ALIENWARE_USER}@{ALIENWARE_IP}")
        sys.exit(1)

    print()

    if args.verify_only:
        if verify_deployment():
            print_usage()
        sys.exit(0)

    # Check Ollama
    check_ollama()
    print()

    # Create directories
    create_directories()
    print()

    # Deploy files
    deploy_files()
    print()

    # Create wrapper
    create_wrapper_script()
    print()

    # Optional: setup service
    if args.setup_service:
        setup_systemd_service()
        print()

    # Verify
    if verify_deployment():
        print_usage()
    else:
        print()
        print("WARNING: Deployment may have issues. Check errors above.")


if __name__ == "__main__":
    main()
