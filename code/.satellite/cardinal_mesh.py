#!/usr/bin/env python3
"""
Cardinal Mesh - Peer-to-Peer Coordination Layer
================================================

Cardinals on different machines discover and coordinate with each other
through the shared state. No central server needed - pure P2P via filesystem.

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    CARDINAL MESH                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐         ┌──────────────┐                     │
│   │  WINDOWS     │   ◄─────│  ALIENWARE   │                     │
│   │  CARDINAL    │   peer  │  CARDINAL    │                     │
│   │              │────────►│              │                     │
│   │ Ollama:GPU   │         │ Ollama:ML    │                     │
│   └──────────────┘         └──────────────┘                     │
│          │                        │                              │
│          └────────────────────────┘                              │
│                         │                                        │
│              ┌──────────────────┐                                │
│              │   SHARED STATE   │                                │
│              │  (Network Share) │                                │
│              └──────────────────┘                                │
│                                                                  │
│   peer_registry.json  - Who's online                             │
│   shared_state.json   - Task queue                               │
│   coordination.json   - Who's doing what                         │
└─────────────────────────────────────────────────────────────────┘

Each Cardinal:
1. Announces presence (heartbeat) to peer_registry
2. Claims tasks from shared_state
3. Coordinates via coordination.json
4. Can delegate tasks to better-suited peers
"""

import json
import os
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
import threading

# Configuration
SHARED_PATH = Path(os.getenv("AKASHIC_SHARED",
    str(Path(__file__).parent)))  # .satellite folder

HEARTBEAT_INTERVAL = 30  # seconds
STALE_THRESHOLD = 120    # seconds before peer considered offline


@dataclass
class CardinalPeer:
    """A Cardinal node in the mesh."""
    node_id: str
    hostname: str
    role: str  # "primary", "compute", "satellite"
    capabilities: List[str]  # ["ollama", "gpu", "deploy", "wow_server"]
    ip: str = ""
    last_heartbeat: float = 0
    current_task: str = ""
    load: float = 0.0  # 0.0-1.0, how busy
    ollama_model: str = "mistral"

    @property
    def is_online(self) -> bool:
        return (time.time() - self.last_heartbeat) < STALE_THRESHOLD

    @property
    def status(self) -> str:
        if not self.is_online:
            return "offline"
        if self.current_task:
            return "busy"
        return "available"

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["is_online"] = self.is_online
        d["status"] = self.status
        return d


@dataclass
class CoordinationTask:
    """A task being coordinated across the mesh."""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 5  # 1-10, lower is higher priority
    required_capabilities: List[str] = field(default_factory=list)
    assigned_to: str = ""
    status: str = "pending"  # pending, claimed, in_progress, completed, failed
    created_at: float = 0
    claimed_at: float = 0
    completed_at: float = 0
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


class CardinalMesh:
    """
    Coordinates Cardinals across machines via shared filesystem.

    Think of it as a simple job queue where:
    - Any Cardinal can post tasks
    - Any Cardinal can claim and execute tasks
    - Cardinals prefer tasks matching their capabilities
    """

    def __init__(self, node_id: str = None, role: str = "satellite",
                 capabilities: List[str] = None):
        self.node_id = node_id or socket.gethostname()
        self.role = role
        self.capabilities = capabilities or ["general"]
        self.hostname = socket.gethostname()

        # File paths
        self.peer_registry_file = SHARED_PATH / "peer_registry.json"
        self.coordination_file = SHARED_PATH / "coordination.json"
        self.state_file = SHARED_PATH / "shared_state.json"

        # Local state
        self.peers: Dict[str, CardinalPeer] = {}
        self.tasks: Dict[str, CoordinationTask] = {}
        self._running = False
        self._heartbeat_thread = None

        # Ensure files exist
        self._ensure_files()

    def _ensure_files(self):
        """Create files if they don't exist."""
        SHARED_PATH.mkdir(parents=True, exist_ok=True)

        if not self.peer_registry_file.exists():
            self.peer_registry_file.write_text(json.dumps({
                "peers": {},
                "created": datetime.now().isoformat()
            }, indent=2))

        if not self.coordination_file.exists():
            self.coordination_file.write_text(json.dumps({
                "tasks": {},
                "created": datetime.now().isoformat()
            }, indent=2))

    def log(self, msg: str):
        """Log with timestamp and node ID."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{self.node_id}] {msg}")

    # ========================================================================
    # Peer Registry
    # ========================================================================

    def _load_peer_registry(self) -> Dict:
        """Load peer registry from file."""
        try:
            return json.loads(self.peer_registry_file.read_text())
        except:
            return {"peers": {}}

    def _save_peer_registry(self, data: Dict):
        """Save peer registry to file."""
        data["last_updated"] = datetime.now().isoformat()
        self.peer_registry_file.write_text(json.dumps(data, indent=2))

    def announce(self, load: float = 0.0, current_task: str = ""):
        """Announce this Cardinal's presence to the mesh."""
        registry = self._load_peer_registry()

        try:
            ip = socket.gethostbyname(self.hostname)
        except:
            ip = "127.0.0.1"

        peer_data = {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "ip": ip,
            "role": self.role,
            "capabilities": self.capabilities,
            "last_heartbeat": time.time(),
            "current_task": current_task,
            "load": load,
            "ollama_model": "mistral",
        }

        registry["peers"][self.node_id] = peer_data
        self._save_peer_registry(registry)
        self.log(f"Announced to mesh (load={load:.1%})")

    def discover_peers(self) -> List[CardinalPeer]:
        """Discover other Cardinals in the mesh."""
        registry = self._load_peer_registry()

        peers = []
        for node_id, data in registry.get("peers", {}).items():
            if node_id == self.node_id:
                continue  # Skip self

            peer = CardinalPeer(**data)
            peers.append(peer)
            self.peers[node_id] = peer

        return peers

    def get_online_peers(self) -> List[CardinalPeer]:
        """Get only online peers."""
        self.discover_peers()
        return [p for p in self.peers.values() if p.is_online]

    def find_peer_for_capability(self, capability: str) -> Optional[CardinalPeer]:
        """Find an available peer with a specific capability."""
        for peer in self.get_online_peers():
            if capability in peer.capabilities and peer.status == "available":
                return peer
        return None

    # ========================================================================
    # Task Coordination
    # ========================================================================

    def _load_coordination(self) -> Dict:
        """Load coordination state from file."""
        try:
            return json.loads(self.coordination_file.read_text())
        except:
            return {"tasks": {}}

    def _save_coordination(self, data: Dict):
        """Save coordination state to file."""
        data["last_updated"] = datetime.now().isoformat()
        self.coordination_file.write_text(json.dumps(data, indent=2))

    def post_task(self, task_type: str, payload: Dict[str, Any],
                  priority: int = 5, required_capabilities: List[str] = None) -> str:
        """Post a task for any Cardinal to pick up."""
        task_id = f"task_{int(time.time()*1000)}"

        task = CoordinationTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            required_capabilities=required_capabilities or [],
            created_at=time.time(),
        )

        coord = self._load_coordination()
        coord["tasks"][task_id] = task.to_dict()
        self._save_coordination(coord)

        self.log(f"Posted task: {task_id} ({task_type})")
        return task_id

    def claim_task(self, task_id: str) -> bool:
        """Attempt to claim a task. Returns True if successful."""
        coord = self._load_coordination()
        tasks = coord.get("tasks", {})

        if task_id not in tasks:
            return False

        task = tasks[task_id]

        # Check if already claimed
        if task.get("status") not in ["pending", "failed"]:
            return False

        # Check capabilities
        required = task.get("required_capabilities", [])
        if required and not all(cap in self.capabilities for cap in required):
            return False

        # Claim it
        task["assigned_to"] = self.node_id
        task["status"] = "claimed"
        task["claimed_at"] = time.time()
        self._save_coordination(coord)

        self.log(f"Claimed task: {task_id}")
        return True

    def get_pending_tasks(self) -> List[Dict]:
        """Get tasks this Cardinal could handle."""
        coord = self._load_coordination()
        tasks = []

        for task_id, task in coord.get("tasks", {}).items():
            if task.get("status") not in ["pending", "failed"]:
                continue

            # Check capabilities
            required = task.get("required_capabilities", [])
            if required and not all(cap in self.capabilities for cap in required):
                continue

            tasks.append(task)

        # Sort by priority (lower = higher priority)
        tasks.sort(key=lambda t: t.get("priority", 5))
        return tasks

    def complete_task(self, task_id: str, result: Dict[str, Any], success: bool = True):
        """Mark a task as completed."""
        coord = self._load_coordination()
        tasks = coord.get("tasks", {})

        if task_id not in tasks:
            return

        tasks[task_id]["status"] = "completed" if success else "failed"
        tasks[task_id]["completed_at"] = time.time()
        tasks[task_id]["result"] = result
        self._save_coordination(coord)

        self.log(f"Completed task: {task_id} (success={success})")

    def delegate_task(self, task_type: str, payload: Dict[str, Any],
                      target_node: str = None, capability: str = None) -> Optional[str]:
        """
        Delegate a task to another Cardinal.

        Args:
            task_type: Type of task
            payload: Task payload
            target_node: Specific node to target
            capability: Required capability (finds best peer)
        """
        if target_node:
            # Direct delegation
            return self.post_task(task_type, payload,
                                  required_capabilities=[])
        elif capability:
            peer = self.find_peer_for_capability(capability)
            if peer:
                return self.post_task(task_type, payload,
                                      required_capabilities=[capability])
        return None

    # ========================================================================
    # Heartbeat / Lifecycle
    # ========================================================================

    def _heartbeat_loop(self):
        """Background heartbeat thread."""
        while self._running:
            self.announce()
            time.sleep(HEARTBEAT_INTERVAL)

    def start(self):
        """Start the mesh coordination (announce + heartbeat)."""
        self._running = True
        self.announce()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        self.log("Started mesh coordination")

    def stop(self):
        """Stop the mesh coordination."""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        self.log("Stopped mesh coordination")

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def status(self) -> Dict[str, Any]:
        """Get full mesh status."""
        peers = self.discover_peers()
        tasks = self._load_coordination().get("tasks", {})

        pending = sum(1 for t in tasks.values() if t.get("status") == "pending")
        in_progress = sum(1 for t in tasks.values() if t.get("status") in ["claimed", "in_progress"])
        completed = sum(1 for t in tasks.values() if t.get("status") == "completed")

        return {
            "this_node": {
                "id": self.node_id,
                "role": self.role,
                "capabilities": self.capabilities,
            },
            "peers": {
                "total": len(peers),
                "online": len([p for p in peers if p.is_online]),
                "available": len([p for p in peers if p.status == "available"]),
                "nodes": [p.to_dict() for p in peers],
            },
            "tasks": {
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
                "total": len(tasks),
            }
        }

    def wait_for_peer(self, node_id: str, timeout: int = 60) -> bool:
        """Wait for a specific peer to come online."""
        start = time.time()
        while (time.time() - start) < timeout:
            peers = self.discover_peers()
            for peer in peers:
                if peer.node_id == node_id and peer.is_online:
                    return True
            time.sleep(5)
        return False


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cardinal Mesh Coordination")
    parser.add_argument("command", choices=["status", "announce", "peers", "tasks", "post"],
                        help="Command to run")
    parser.add_argument("--node-id", default=None, help="Node ID (default: hostname)")
    parser.add_argument("--role", default="satellite", help="Node role")
    parser.add_argument("--capabilities", default="general", help="Comma-separated capabilities")
    parser.add_argument("--task-type", default="general", help="Task type for post")
    parser.add_argument("--payload", default="{}", help="JSON payload for post")
    args = parser.parse_args()

    capabilities = [c.strip() for c in args.capabilities.split(",")]
    mesh = CardinalMesh(
        node_id=args.node_id,
        role=args.role,
        capabilities=capabilities
    )

    if args.command == "status":
        status = mesh.status()
        print(json.dumps(status, indent=2))

    elif args.command == "announce":
        mesh.announce()
        print(f"Announced as {mesh.node_id}")

    elif args.command == "peers":
        peers = mesh.get_online_peers()
        print(f"Online peers ({len(peers)}):")
        for peer in peers:
            print(f"  {peer.node_id}: {peer.role} - {peer.capabilities} [{peer.status}]")

    elif args.command == "tasks":
        tasks = mesh.get_pending_tasks()
        print(f"Pending tasks ({len(tasks)}):")
        for task in tasks:
            print(f"  {task['task_id']}: {task['task_type']} (priority={task['priority']})")

    elif args.command == "post":
        payload = json.loads(args.payload)
        task_id = mesh.post_task(args.task_type, payload)
        print(f"Posted task: {task_id}")


if __name__ == "__main__":
    main()
