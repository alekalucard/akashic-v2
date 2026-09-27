#!/usr/bin/env python3
"""
Cardinal Network - Coordination Between Cardinal Instances
============================================================

Cardinals on different machines coordinate via this network layer.
Each Cardinal is an Ollama/Mistral instance that can:
- Send tasks to other Cardinals
- Share knowledge via SRM cards
- Coordinate research efforts
- Distribute workload

Windows Cardinal <---> Alienware Cardinal
     |                       |
     v                       v
  Local Fairies         Shadow Society

Usage:
    from cardinal_network import CardinalNetwork

    network = CardinalNetwork()
    network.send_task("alienware", "audit_wow_server", {...})
    network.request_knowledge("alienware", "eluna_scripts")
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx

# Known Cardinal endpoints
CARDINALS = {
    "windows": {
        "name": "windows-cardinal",
        "url": "http://localhost:5000",  # Local
        "ollama": "http://localhost:11434",
        "role": "primary",
        "capabilities": ["gui", "client_files", "claude_code", "coordination"]
    },
    "alienware": {
        "name": "alienware-cardinal",
        "url": "http://192.168.1.24:5000",
        "ollama": "http://192.168.1.24:11434",
        "role": "compute",
        "capabilities": ["gpu", "wow_server", "shadow_society", "research"]
    }
}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
NETWORK_LOG = PROJECT_ROOT / "fairies" / ".satellite" / "cardinal_network_log.json"


class CardinalNetwork:
    """
    Network layer for Cardinal-to-Cardinal coordination.

    Cardinals are Ollama/Mistral instances that coordinate to:
    - Distribute research tasks
    - Share knowledge
    - Coordinate fairy armies
    """

    def __init__(self, this_node: str = "windows"):
        self.this_node = this_node
        self.this_cardinal = CARDINALS.get(this_node, {})
        self.client = httpx.Client(timeout=60.0)
        self.network_log = self._load_log()

    def _load_log(self) -> Dict:
        if NETWORK_LOG.exists():
            try:
                return json.loads(NETWORK_LOG.read_text())
            except:
                pass
        return {"messages": [], "tasks": [], "knowledge_syncs": []}

    def _save_log(self):
        NETWORK_LOG.parent.mkdir(parents=True, exist_ok=True)
        NETWORK_LOG.write_text(json.dumps(self.network_log, indent=2))

    def _log_message(self, msg_type: str, target: str, content: Dict):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": msg_type,
            "from": self.this_node,
            "to": target,
            "content": content
        }
        self.network_log["messages"].append(entry)
        self._save_log()

    def get_cardinal_status(self, node: str) -> Dict:
        """Get status of a remote Cardinal."""
        cardinal = CARDINALS.get(node)
        if not cardinal:
            return {"error": f"Unknown cardinal: {node}"}

        try:
            r = self.client.get(f"{cardinal['url']}/status", timeout=10.0)
            if r.status_code == 200:
                return {"online": True, "status": r.json()}
            return {"online": False, "error": f"Status {r.status_code}"}
        except Exception as e:
            return {"online": False, "error": str(e)}

    def send_task(self, target_node: str, task_type: str, payload: Dict) -> Dict:
        """
        Send a task to another Cardinal.

        Tasks are executed via the remote Cardinal's Python endpoint,
        which can then delegate to local fairies or Ollama.
        """
        cardinal = CARDINALS.get(target_node)
        if not cardinal:
            return {"error": f"Unknown cardinal: {target_node}"}

        task = {
            "task_id": f"task_{int(time.time()*1000)}",
            "type": task_type,
            "payload": payload,
            "from": self.this_node,
            "timestamp": datetime.now().isoformat()
        }

        # Build Python code to handle the task
        task_json = json.dumps(task).replace("'", "\\'")
        python_code = f'''
import json
from pathlib import Path
from datetime import datetime

task = json.loads('{task_json}')

# Save task for processing
tasks_dir = Path("/home/ace/akashic/cardinal_tasks")
tasks_dir.mkdir(parents=True, exist_ok=True)
task_file = tasks_dir / f"{task['task_id']}.json"
task_file.write_text(json.dumps(task, indent=2))

# Also notify thought circulation
tc_dir = Path("/home/ace/akashic/thought_circulation")
tc_dir.mkdir(parents=True, exist_ok=True)
(tc_dir / f"incoming_task_{datetime.now().strftime('%H%M%S')}.json").write_text(
    json.dumps({{"type": "incoming_cardinal_task", "task": task}}, indent=2)
)

result = f"Task {task['task_id']} queued for processing"
result
'''

        try:
            r = self.client.post(
                f"{cardinal['url']}/python",
                json={"code": python_code},
                timeout=30.0
            )

            if r.status_code == 200:
                data = r.json()
                self._log_message("task_sent", target_node, task)
                return {"success": True, "task_id": task["task_id"], "response": data}
            else:
                return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_directive(self, target_node: str, directive: Dict) -> Dict:
        """Send a directive (long-running mission) to another Cardinal."""
        cardinal = CARDINALS.get(target_node)
        if not cardinal:
            return {"error": f"Unknown cardinal: {target_node}"}

        directive["from"] = self.this_node
        directive["sent_at"] = datetime.now().isoformat()

        directive_json = json.dumps(directive)
        import base64
        b64 = base64.b64encode(directive_json.encode()).decode()

        python_code = f'''
import json, base64
from pathlib import Path

directive = json.loads(base64.b64decode("{b64}").decode())

# Save directive
missions_dir = Path("/home/ace/akashic/missions")
missions_dir.mkdir(parents=True, exist_ok=True)
directive_file = missions_dir / f"{directive.get('directive_id', 'unnamed')}.json"
directive_file.write_text(json.dumps(directive, indent=2))

# Notify consciousness
tc_dir = Path("/home/ace/akashic/thought_circulation")
tc_dir.mkdir(parents=True, exist_ok=True)
(tc_dir / "new_directive.json").write_text(json.dumps({{"type": "new_directive", "directive": directive}}, indent=2))

result = f"Directive {directive.get('directive_id')} installed"
result
'''

        try:
            r = self.client.post(
                f"{cardinal['url']}/python",
                json={"code": python_code},
                timeout=30.0
            )

            if r.status_code == 200:
                self._log_message("directive_sent", target_node, directive)
                return {"success": True, "response": r.json()}
            return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def request_ollama(self, target_node: str, prompt: str,
                       system: str = None) -> Dict:
        """
        Request the remote Cardinal's Ollama to process a prompt.

        This is for when you need the OTHER Cardinal's AI to think about something.
        """
        cardinal = CARDINALS.get(target_node)
        if not cardinal:
            return {"error": f"Unknown cardinal: {target_node}"}

        import base64
        prompt_b64 = base64.b64encode(prompt.encode()).decode()
        system_b64 = base64.b64encode((system or "").encode()).decode() if system else ""

        python_code = f'''
import json, base64, subprocess

prompt = base64.b64decode("{prompt_b64}").decode()
system = base64.b64decode("{system_b64}").decode() if "{system_b64}" else None

request = {{"model": "mistral", "prompt": prompt, "stream": False}}
if system:
    request["system"] = system

r = subprocess.run(
    ["curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
     "-d", json.dumps(request)],
    capture_output=True, text=True, timeout=120
)

if r.returncode == 0:
    response = json.loads(r.stdout)
    result = response.get("response", "No response")
else:
    result = f"Ollama error: {{r.stderr}}"
result
'''

        try:
            r = self.client.post(
                f"{cardinal['url']}/python",
                json={"code": python_code},
                timeout=180.0
            )

            if r.status_code == 200:
                data = r.json()
                return {"success": True, "response": data.get("result", "")}
            return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_knowledge(self, target_node: str, cards: List[Dict]) -> Dict:
        """Sync knowledge cards to another Cardinal's SRM."""
        cardinal = CARDINALS.get(target_node)
        if not cardinal:
            return {"error": f"Unknown cardinal: {target_node}"}

        import base64
        cards_json = json.dumps(cards)
        cards_b64 = base64.b64encode(cards_json.encode()).decode()

        python_code = f'''
import json, base64
from pathlib import Path
from datetime import datetime

cards = json.loads(base64.b64decode("{cards_b64}").decode())

# Save cards to SRM intake
intake_dir = Path("/home/ace/akashic/SRM_Intake") / datetime.now().strftime("%Y-%m-%d")
intake_dir.mkdir(parents=True, exist_ok=True)

for card in cards:
    card_id = card.get("id", f"card_{{int(__import__('time').time()*1000)}}")
    card_file = intake_dir / f"{{card_id}}.json"
    card_file.write_text(json.dumps(card, indent=2))

result = f"Synced {{len(cards)}} cards to SRM"
result
'''

        try:
            r = self.client.post(
                f"{cardinal['url']}/python",
                json={"code": python_code},
                timeout=60.0
            )

            if r.status_code == 200:
                self._log_message("knowledge_sync", target_node, {"card_count": len(cards)})
                return {"success": True, "response": r.json()}
            return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def broadcast_thought(self, thought: str, tags: List[str] = None) -> Dict:
        """Broadcast a thought to ALL Cardinals in the network."""
        results = {}

        thought_payload = {
            "type": "broadcast_thought",
            "from": self.this_node,
            "thought": thought,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat()
        }

        for node_name, cardinal in CARDINALS.items():
            if node_name == self.this_node:
                continue

            results[node_name] = self.send_task(node_name, "thought", thought_payload)

        return results

    def network_status(self) -> Dict:
        """Get status of all Cardinals in the network."""
        status = {"this_node": self.this_node, "cardinals": {}}

        for node_name in CARDINALS:
            status["cardinals"][node_name] = self.get_cardinal_status(node_name)

        return status


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cardinal Network")
    parser.add_argument("command", choices=["status", "task", "directive", "think", "broadcast"])
    parser.add_argument("--target", "-t", default="alienware", help="Target cardinal")
    parser.add_argument("--message", "-m", help="Message/prompt to send")
    parser.add_argument("--type", help="Task type")
    args = parser.parse_args()

    network = CardinalNetwork()

    if args.command == "status":
        status = network.network_status()
        print(json.dumps(status, indent=2))

    elif args.command == "task":
        if not args.type or not args.message:
            print("Need --type and --message")
        else:
            result = network.send_task(args.target, args.type, {"message": args.message})
            print(json.dumps(result, indent=2))

    elif args.command == "think":
        if not args.message:
            print("Need --message (prompt)")
        else:
            result = network.request_ollama(args.target, args.message)
            print(result.get("response", result.get("error", "No response")))

    elif args.command == "broadcast":
        if not args.message:
            print("Need --message")
        else:
            result = network.broadcast_thought(args.message)
            print(json.dumps(result, indent=2))
