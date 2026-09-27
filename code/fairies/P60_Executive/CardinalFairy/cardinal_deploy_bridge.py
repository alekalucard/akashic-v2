#!/usr/bin/env python3
"""
Cardinal Deploy Bridge - Card-Based File Transfer Between Nodes
================================================================

Teaches Cardinals how to:
1. INGEST files into deployment cards
2. SEND cards to remote Cardinals via HTTP API
3. DEPLOY files on the receiving end
4. TRACK what's been synced

This becomes part of the OS - a reliable way to move things between nodes.

Usage:
    python cardinal_deploy_bridge.py send <file> <remote_path>
    python cardinal_deploy_bridge.py sync <local_dir> <remote_dir>
    python cardinal_deploy_bridge.py status
    python cardinal_deploy_bridge.py test

The Dream: Cardinals talking to Cardinals, syncing consciousness across machines.
"""

import argparse
import base64
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import httpx

# Configuration
ALIENWARE_URL = "http://192.168.1.24:5000"
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # akashic_v2
DEPLOY_LOG = PROJECT_ROOT / "fairies" / ".satellite" / "deploy_log.json"


class DeployCard:
    """A card representing a file to deploy."""

    def __init__(self, local_path: str, remote_path: str):
        self.local_path = Path(local_path)
        self.remote_path = remote_path
        self.filename = self.local_path.name
        self.created = datetime.now().isoformat()

        # Read and encode content
        if self.local_path.exists():
            content = self.local_path.read_bytes()
            self.content_b64 = base64.b64encode(content).decode('utf-8')
            self.size = len(content)
            self.hash = hashlib.md5(content).hexdigest()
        else:
            raise FileNotFoundError(f"File not found: {local_path}")

    def to_dict(self) -> Dict:
        return {
            "type": "deploy_card",
            "filename": self.filename,
            "local_path": str(self.local_path),
            "remote_path": self.remote_path,
            "size": self.size,
            "hash": self.hash,
            "created": self.created,
            "content_b64": self.content_b64,
        }


class CardinalDeployBridge:
    """
    Bridge between Cardinals for file deployment.

    Windows Cardinal creates cards, sends to Alienware Cardinal,
    which deploys files and reports back.
    """

    def __init__(self, remote_url: str = ALIENWARE_URL):
        self.remote_url = remote_url
        self.client = httpx.Client(timeout=60.0)
        self.deploy_log = self._load_log()

    def _load_log(self) -> Dict:
        """Load deployment log."""
        if DEPLOY_LOG.exists():
            try:
                return json.loads(DEPLOY_LOG.read_text())
            except:
                pass
        return {"deployments": [], "stats": {"total": 0, "success": 0, "failed": 0}}

    def _save_log(self):
        """Save deployment log."""
        DEPLOY_LOG.parent.mkdir(parents=True, exist_ok=True)
        DEPLOY_LOG.write_text(json.dumps(self.deploy_log, indent=2))

    def _log_deployment(self, card: DeployCard, success: bool, message: str):
        """Log a deployment attempt."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "filename": card.filename,
            "remote_path": card.remote_path,
            "size": card.size,
            "hash": card.hash,
            "success": success,
            "message": message,
        }
        self.deploy_log["deployments"].append(entry)
        self.deploy_log["stats"]["total"] += 1
        if success:
            self.deploy_log["stats"]["success"] += 1
        else:
            self.deploy_log["stats"]["failed"] += 1
        self._save_log()

    def check_remote(self) -> Dict:
        """Check if remote Cardinal is online."""
        try:
            r = self.client.get(f"{self.remote_url}/status")
            if r.status_code == 200:
                return {"online": True, "status": r.json()}
            return {"online": False, "error": f"Status {r.status_code}"}
        except Exception as e:
            return {"online": False, "error": str(e)}

    def send_card(self, card: DeployCard) -> Dict:
        """Send a deployment card to the remote Cardinal."""
        # Build Python code to deploy the file
        python_code = f'''
import base64
from pathlib import Path

# Decode the file content
content = base64.b64decode('{card.content_b64}')

# Ensure directory exists
target = Path('{card.remote_path}')
target.parent.mkdir(parents=True, exist_ok=True)

# Write the file
target.write_bytes(content)

# Verify
result = f"Deployed {{len(content)}} bytes to {{target}}, exists={{target.exists()}}"
result
'''

        try:
            r = self.client.post(
                f"{self.remote_url}/python",
                json={"code": python_code},
                timeout=30.0
            )

            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    message = data.get("result", "Success")
                    self._log_deployment(card, True, message)
                    return {"success": True, "message": message}
                else:
                    error = data.get("error", "Unknown error")
                    self._log_deployment(card, False, error)
                    return {"success": False, "error": error}
            else:
                error = f"HTTP {r.status_code}"
                self._log_deployment(card, False, error)
                return {"success": False, "error": error}

        except Exception as e:
            error = str(e)
            self._log_deployment(card, False, error)
            return {"success": False, "error": error}

    def send_file(self, local_path: str, remote_path: str) -> Dict:
        """Send a single file to remote Cardinal."""
        print(f"[CARD] Creating card for: {local_path}")

        try:
            card = DeployCard(local_path, remote_path)
        except FileNotFoundError as e:
            return {"success": False, "error": str(e)}

        print(f"[SEND] Sending to {self.remote_url}...")
        result = self.send_card(card)

        if result.get("success"):
            print(f"[OK] Deployed: {card.filename} ({card.size} bytes)")
        else:
            print(f"[FAIL] Failed: {result.get('error')}")

        return result

    def sync_directory(self, local_dir: str, remote_dir: str,
                       patterns: List[str] = None) -> Dict:
        """Sync a directory to remote Cardinal."""
        local_path = Path(local_dir)
        if not local_path.exists():
            return {"success": False, "error": f"Directory not found: {local_dir}"}

        patterns = patterns or ["*"]
        files = []
        for pattern in patterns:
            files.extend(local_path.glob(pattern))

        # Filter to files only
        files = [f for f in files if f.is_file()]

        print(f"[SYNC] Syncing {len(files)} files from {local_dir}")
        print(f"    -> {remote_dir}")
        print()

        results = {"total": len(files), "success": 0, "failed": 0, "files": []}

        for file in files:
            rel_path = file.relative_to(local_path)
            remote_path = f"{remote_dir}/{rel_path}"

            result = self.send_file(str(file), remote_path)
            results["files"].append({
                "file": str(rel_path),
                "success": result.get("success", False)
            })

            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1

        print()
        print(f"[DONE] Sync complete: {results['success']}/{results['total']} succeeded")

        return results

    def get_status(self) -> Dict:
        """Get deployment status."""
        remote = self.check_remote()

        return {
            "remote": remote,
            "log": {
                "total_deployments": self.deploy_log["stats"]["total"],
                "successful": self.deploy_log["stats"]["success"],
                "failed": self.deploy_log["stats"]["failed"],
                "recent": self.deploy_log["deployments"][-5:] if self.deploy_log["deployments"] else []
            }
        }

    def test_connection(self) -> bool:
        """Test the connection with a simple file."""
        print("[TEST] Testing Cardinal-to-Cardinal connection...")
        print()

        # Check remote
        remote = self.check_remote()
        if not remote.get("online"):
            print(f"[FAIL] Remote Cardinal offline: {remote.get('error')}")
            return False

        print(f"[OK] Remote Cardinal online")
        print(f"   Node: {remote['status'].get('node', 'unknown')}")
        print(f"   Fairies: {remote['status'].get('fairy_count', '?')}")
        print()

        # Test file deployment
        test_content = f"Cardinal bridge test - {datetime.now().isoformat()}"
        test_file = PROJECT_ROOT / "fairies" / ".satellite" / "bridge_test.txt"
        test_file.write_text(test_content)

        result = self.send_file(
            str(test_file),
            "/home/ace/akashic/cardinal_bridge_test.txt"
        )

        # Cleanup local test file
        test_file.unlink()

        if result.get("success"):
            print()
            print("[SUCCESS] Cardinal bridge working!")
            return True
        else:
            print()
            print(f"[FAIL] Bridge test failed: {result.get('error')}")
            return False


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Cardinal Deploy Bridge - Transfer files between Cardinals"
    )
    parser.add_argument("command", choices=["send", "sync", "status", "test"],
                        help="Command to run")
    parser.add_argument("args", nargs="*", help="Command arguments")
    parser.add_argument("--pattern", "-p", default="*",
                        help="File pattern for sync (default: *)")

    args = parser.parse_args()
    bridge = CardinalDeployBridge()

    if args.command == "test":
        success = bridge.test_connection()
        exit(0 if success else 1)

    elif args.command == "status":
        status = bridge.get_status()
        print(json.dumps(status, indent=2))

    elif args.command == "send":
        if len(args.args) != 2:
            print("Usage: cardinal_deploy_bridge.py send <local_file> <remote_path>")
            exit(1)
        result = bridge.send_file(args.args[0], args.args[1])
        exit(0 if result.get("success") else 1)

    elif args.command == "sync":
        if len(args.args) != 2:
            print("Usage: cardinal_deploy_bridge.py sync <local_dir> <remote_dir>")
            exit(1)
        patterns = args.pattern.split(",") if args.pattern else ["*"]
        result = bridge.sync_directory(args.args[0], args.args[1], patterns)
        exit(0 if result["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
