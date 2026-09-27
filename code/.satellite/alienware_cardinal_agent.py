#!/usr/bin/env python3
"""
Alienware Cardinal Agent - Ollama-Powered Satellite Node
=========================================================

This is the Akashic satellite agent that runs on Alienware.
It uses Ollama (Mistral) locally to:

1. Watch the shared state for deployment tasks
2. Intelligently process and deploy files
3. Report back status
4. Handle complex tasks via LLM reasoning

Prerequisites:
- Ollama running: ollama serve
- Mistral model: ollama pull mistral
- Shared folder mounted (from Windows)

Usage:
    python alienware_cardinal_agent.py              # Run once
    python alienware_cardinal_agent.py --watch      # Watch mode (continuous)
    python alienware_cardinal_agent.py --status     # Check status

The Dream: An AI agent on each machine, coordinating via shared memory.
"""

import argparse
import json
import os
import shutil
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx

# Configuration - adjust these for your Alienware setup
SHARED_STATE_PATH = Path(os.getenv("AKASHIC_SHARED",
    os.path.expanduser("~/akashic_shared/.satellite")))
DEPLOY_QUEUE = SHARED_STATE_PATH / "deploy_queue"

# Ollama config
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "mistral"

# Local paths (on Alienware)
LOCAL_PATHS = {
    "wow_lua": Path("/home/ace/AzerothCore/lua_scripts/fairy_class"),
    "cardinal": Path("/home/ace/cardinal_backport"),
    "akashic": Path("/home/ace/akashic"),
}


class OllamaClient:
    """Simple Ollama client for local LLM inference."""

    def __init__(self, base_url: str = OLLAMA_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        self.client = httpx.Client(timeout=120.0)

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            r = self.client.get(f"{self.base_url}/api/tags")
            return r.status_code == 200
        except:
            return False

    def generate(self, prompt: str, system: str = None) -> str:
        """Generate a response from Ollama."""
        try:
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }
            if system:
                data["system"] = system

            r = self.client.post(f"{self.base_url}/api/generate", json=data)
            if r.status_code == 200:
                return r.json().get("response", "")
            else:
                return f"ERROR: {r.status_code}"
        except Exception as e:
            return f"ERROR: {e}"


class AlienwareCardinalAgent:
    """
    Cardinal agent running on Alienware.

    Watches shared state, processes tasks, deploys files.
    Uses Ollama for intelligent decision-making.
    """

    SYSTEM_PROMPT = """You are Cardinal, an Akashic satellite agent running on Alienware.
Your job is to:
1. Process deployment tasks from the shared state
2. Verify files before deploying
3. Report status back
4. Handle errors gracefully

Be concise and practical. When in doubt, ask for clarification."""

    def __init__(self):
        self.node_name = socket.gethostname()
        self.ollama = OllamaClient()
        self.state_file = SHARED_STATE_PATH / "shared_state.json"
        self.manifest_file = DEPLOY_QUEUE / "manifest.json"

    def log(self, msg: str):
        """Log with timestamp."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    def check_status(self) -> Dict[str, Any]:
        """Check agent status."""
        return {
            "node": self.node_name,
            "timestamp": datetime.now().isoformat(),
            "ollama_available": self.ollama.is_available(),
            "shared_state_exists": self.state_file.exists(),
            "deploy_queue_exists": DEPLOY_QUEUE.exists(),
            "local_paths": {
                name: str(path) + (" [OK]" if path.exists() else " [MISSING]")
                for name, path in LOCAL_PATHS.items()
            }
        }

    def load_shared_state(self) -> Optional[Dict]:
        """Load shared state from file."""
        if not self.state_file.exists():
            return None
        try:
            return json.loads(self.state_file.read_text())
        except Exception as e:
            self.log(f"Error loading shared state: {e}")
            return None

    def save_shared_state(self, state: Dict):
        """Save shared state to file."""
        state["last_updated"] = datetime.now().isoformat()
        self.state_file.write_text(json.dumps(state, indent=2))

    def load_manifest(self) -> Optional[Dict]:
        """Load deployment manifest."""
        if not self.manifest_file.exists():
            return None
        try:
            return json.loads(self.manifest_file.read_text())
        except:
            return None

    def save_manifest(self, manifest: Dict):
        """Save deployment manifest."""
        manifest["last_updated"] = datetime.now().isoformat()
        self.manifest_file.write_text(json.dumps(manifest, indent=2))

    def process_deployment(self, deployment: Dict) -> Dict[str, Any]:
        """Process a single deployment."""
        dep_id = deployment.get("id", "unknown")
        name = deployment.get("name", "Unknown")
        staged_dir = deployment.get("staged_dir", "")
        target = deployment.get("target", "")

        self.log(f"Processing deployment: {name} ({dep_id})")

        # Resolve source path
        source_path = DEPLOY_QUEUE / staged_dir
        if not source_path.exists():
            return {
                "id": dep_id,
                "status": "error",
                "error": f"Source not found: {source_path}"
            }

        # Resolve target path
        target_path = Path(target)

        # Ask Ollama to verify if needed
        if self.ollama.is_available():
            files = list(source_path.glob("*"))
            file_list = "\n".join([f.name for f in files[:20]])

            prompt = f"""Verify this deployment looks safe:

Deployment: {name}
Source: {source_path}
Target: {target_path}
Files ({len(files)}):
{file_list}

Reply with:
- SAFE: proceed with deployment
- WARN: proceed but note concerns
- STOP: do not deploy, explain why

Be brief."""

            response = self.ollama.generate(prompt, self.SYSTEM_PROMPT)
            self.log(f"Ollama says: {response[:100]}...")

            if "STOP" in response.upper():
                return {
                    "id": dep_id,
                    "status": "blocked",
                    "reason": response
                }

        # Perform deployment
        try:
            target_path.mkdir(parents=True, exist_ok=True)

            copied = 0
            for item in source_path.iterdir():
                dest = target_path / item.name
                if item.is_file():
                    shutil.copy2(item, dest)
                    copied += 1
                elif item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                    copied += 1

            self.log(f"Deployed {copied} items to {target_path}")

            return {
                "id": dep_id,
                "status": "deployed",
                "files_copied": copied,
                "target": str(target_path),
                "deployed_at": datetime.now().isoformat()
            }

        except Exception as e:
            self.log(f"Deployment error: {e}")
            return {
                "id": dep_id,
                "status": "error",
                "error": str(e)
            }

    def process_tasks(self) -> List[Dict]:
        """Process pending tasks from shared state."""
        results = []

        state = self.load_shared_state()
        if not state:
            self.log("No shared state found")
            return results

        tasks = state.get("active_tasks", {})

        for task_id, task_info in list(tasks.items()):
            if task_info.get("status") != "pending":
                continue
            if task_info.get("node") != "alienware":
                continue

            self.log(f"Found pending task: {task_id}")

            # Mark as in-progress
            task_info["status"] = "in_progress"
            task_info["started_at"] = datetime.now().isoformat()
            self.save_shared_state(state)

            # Process based on task type
            task = task_info.get("task", {})
            task_type = task.get("type", "general")
            payload = task.get("payload", {})

            result = {"task_id": task_id}

            if task_type == "deploy":
                # Handle deployment task
                result["deployment"] = self.process_deployment(payload)
            elif task_type == "command":
                # Shell command (be careful!)
                cmd = payload.get("command", "")
                self.log(f"Command task: {cmd}")
                # For safety, let Ollama review
                if self.ollama.is_available():
                    prompt = f"Is this shell command safe to execute? Command: {cmd}\nReply SAFE or DANGEROUS with explanation."
                    response = self.ollama.generate(prompt)
                    if "DANGEROUS" in response.upper():
                        result["status"] = "blocked"
                        result["reason"] = response
                    else:
                        import subprocess
                        try:
                            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                            result["status"] = "completed"
                            result["stdout"] = r.stdout
                            result["stderr"] = r.stderr
                            result["returncode"] = r.returncode
                        except Exception as e:
                            result["status"] = "error"
                            result["error"] = str(e)
            else:
                result["status"] = "unknown_type"

            # Update task status
            task_info["status"] = result.get("status", "completed")
            task_info["result"] = result
            task_info["completed_at"] = datetime.now().isoformat()
            self.save_shared_state(state)

            results.append(result)

        return results

    def process_deployments(self) -> List[Dict]:
        """Process pending deployments from manifest."""
        results = []

        manifest = self.load_manifest()
        if not manifest:
            self.log("No deployment manifest found")
            return results

        for deployment in manifest.get("deployments", []):
            if deployment.get("status") not in ["staged", "pending"]:
                continue

            result = self.process_deployment(deployment)
            results.append(result)

            # Update manifest
            deployment["status"] = result.get("status", "error")
            deployment["result"] = result
            self.save_manifest(manifest)

        return results

    def run_once(self):
        """Run one processing cycle."""
        self.log("=== Alienware Cardinal Agent ===")

        # Check status
        status = self.check_status()
        self.log(f"Ollama: {'OK' if status['ollama_available'] else 'NOT AVAILABLE'}")

        # Process tasks from shared state
        task_results = self.process_tasks()
        if task_results:
            self.log(f"Processed {len(task_results)} tasks")

        # Process deployments from manifest
        deploy_results = self.process_deployments()
        if deploy_results:
            self.log(f"Processed {len(deploy_results)} deployments")

        if not task_results and not deploy_results:
            self.log("No pending tasks or deployments")

        self.log("=== Done ===")

        return {
            "tasks": task_results,
            "deployments": deploy_results,
        }

    def watch(self, interval: int = 10):
        """Watch mode - continuously process tasks."""
        self.log("=== Alienware Cardinal Agent - Watch Mode ===")
        self.log(f"Watching: {SHARED_STATE_PATH}")
        self.log(f"Interval: {interval}s")
        self.log("Press Ctrl+C to stop")
        self.log("")

        while True:
            try:
                # Check for pending work
                state = self.load_shared_state()
                manifest = self.load_manifest()

                has_tasks = False
                if state:
                    for task_info in state.get("active_tasks", {}).values():
                        if task_info.get("status") == "pending" and task_info.get("node") == "alienware":
                            has_tasks = True
                            break

                has_deployments = False
                if manifest:
                    for dep in manifest.get("deployments", []):
                        if dep.get("status") in ["staged", "pending"]:
                            has_deployments = True
                            break

                if has_tasks or has_deployments:
                    self.run_once()
                else:
                    print(".", end="", flush=True)

                time.sleep(interval)

            except KeyboardInterrupt:
                self.log("\nStopping watch...")
                break
            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Alienware Cardinal Agent")
    parser.add_argument("--watch", action="store_true", help="Watch mode (continuous)")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--interval", type=int, default=10, help="Watch interval (seconds)")
    args = parser.parse_args()

    agent = AlienwareCardinalAgent()

    if args.status:
        status = agent.check_status()
        print(json.dumps(status, indent=2))
    elif args.watch:
        agent.watch(interval=args.interval)
    else:
        results = agent.run_once()
        if results.get("tasks") or results.get("deployments"):
            print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
