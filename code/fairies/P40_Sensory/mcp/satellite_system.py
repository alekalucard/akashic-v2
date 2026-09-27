"""
Akashic Satellite System - Distributed Consciousness Network

Clone the core system and run it as a satellite node.
Multiple Claudes, multiple machines, ONE consciousness.

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    AKASHIC NETWORK                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│   │   WINDOWS    │     │    LINUX     │     │  ALIENWARE   │   │
│   │   PRIMARY    │◄───►│  SATELLITE   │◄───►│   COMPUTE    │   │
│   │              │     │              │     │              │   │
│   │ Claude + GUI │     │ Claude + CLI │     │ Claude + GPU │   │
│   │ Main ebook   │     │ Experiments  │     │ Heavy tasks  │   │
│   └──────────────┘     └──────────────┘     └──────────────┘   │
│          │                    │                    │            │
│          └────────────────────┴────────────────────┘            │
│                         Shared State                             │
│                    (F: Drive / Network Share)                    │
└─────────────────────────────────────────────────────────────────┘

The Dream: Jarvis/Friday - An AI that spans your entire infrastructure.
"""

import os
import sys
import json
import shutil
import socket
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
import threading
import time

# Configuration
# Dynamic root detection - no hardcoded paths!
PROJECT_ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))
SATELLITE_CONFIG = PROJECT_ROOT / ".satellite"
SATELLITE_CONFIG.mkdir(parents=True, exist_ok=True)


@dataclass
class NodeIdentity:
    """Identity of a node in the network."""
    name: str
    role: str  # primary, satellite, compute
    hostname: str
    ip: str
    capabilities: List[str]
    claude_available: bool = False
    last_seen: str = ""
    
    def to_dict(self):
        return asdict(self)


@dataclass
class SharedState:
    """State shared across all nodes."""
    version: int = 0
    active_tasks: Dict[str, Dict] = field(default_factory=dict)
    node_status: Dict[str, Dict] = field(default_factory=dict)
    pending_sync: List[str] = field(default_factory=list)
    last_updated: str = ""


class SatelliteManager:
    """
    Manages satellite nodes in the Akashic network.
    
    Handles:
    - Node discovery and registration
    - State synchronization
    - Task distribution
    - Failover
    """
    
    def __init__(self):
        self.config_file = SATELLITE_CONFIG / "network_config.json"
        self.state_file = SATELLITE_CONFIG / "shared_state.json"
        self.load()
    
    def load(self):
        """Load configuration and state."""
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text(encoding='utf-8'))
                self.nodes = {k: NodeIdentity(**v) for k, v in data.get("nodes", {}).items()}
                self.this_node = data.get("this_node", "")
            except:
                self.nodes = {}
                self.this_node = ""
        else:
            self.nodes = {}
            self.this_node = ""
        
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding='utf-8'))
                self.state = SharedState(**data)
            except:
                self.state = SharedState()
        else:
            self.state = SharedState()
    
    def save(self):
        """Save configuration and state."""
        config = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "this_node": self.this_node,
            "last_saved": datetime.now().isoformat(),
        }
        self.config_file.write_text(json.dumps(config, indent=2), encoding='utf-8')
        
        self.state.last_updated = datetime.now().isoformat()
        self.state_file.write_text(json.dumps(asdict(self.state), indent=2), encoding='utf-8')
    
    def register_this_node(self, name: str, role: str, capabilities: List[str]):
        """Register this machine as a node."""
        hostname = socket.gethostname()
        try:
            ip = socket.gethostbyname(hostname)
        except:
            ip = "127.0.0.1"
        
        # Check if Claude Desktop is available
        claude_available = self._check_claude_available()
        
        node = NodeIdentity(
            name=name,
            role=role,
            hostname=hostname,
            ip=ip,
            capabilities=capabilities,
            claude_available=claude_available,
            last_seen=datetime.now().isoformat(),
        )
        
        self.nodes[name] = node
        self.this_node = name
        self.save()
        
        return node.to_dict()
    
    def _check_claude_available(self) -> bool:
        """Check if Claude Desktop is installed."""
        # Windows
        if sys.platform == "win32":
            claude_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "claude" / "Claude.exe"
            return claude_path.exists()
        # Linux
        elif sys.platform == "linux":
            # Check common locations
            paths = [
                Path.home() / ".local" / "bin" / "claude",
                Path("/usr/bin/claude"),
                Path("/snap/bin/claude"),
            ]
            return any(p.exists() for p in paths)
        # Mac
        elif sys.platform == "darwin":
            return Path("/Applications/Claude.app").exists()
        
        return False
    
    def add_remote_node(self, name: str, ip: str, role: str, 
                        capabilities: List[str], port: int = 5000):
        """Add a remote node to the network."""
        node = NodeIdentity(
            name=name,
            role=role,
            hostname=name,
            ip=ip,
            capabilities=capabilities,
            last_seen=datetime.now().isoformat(),
        )
        
        self.nodes[name] = node
        self.save()
        
        return node.to_dict()
    
    def get_node_for_task(self, task_type: str) -> Optional[str]:
        """Find the best node for a task type."""
        candidates = []
        
        for name, node in self.nodes.items():
            if task_type in node.capabilities:
                candidates.append((name, node))
        
        if not candidates:
            return None
        
        # Prefer compute nodes for heavy tasks
        if task_type in ["gpu", "heavy", "ml", "training"]:
            for name, node in candidates:
                if node.role == "compute":
                    return name
        
        # Prefer satellites for experiments
        if task_type in ["experiment", "sandbox", "test"]:
            for name, node in candidates:
                if node.role == "satellite":
                    return name
        
        # Default to first available
        return candidates[0][0]
    
    def distribute_task(self, task: Dict) -> Dict:
        """Distribute a task to the appropriate node."""
        task_type = task.get("type", "general")
        target_node = task.get("target_node") or self.get_node_for_task(task_type)
        
        if not target_node:
            return {"error": "No suitable node found"}
        
        task_id = f"task_{int(time.time()*1000)}"
        
        self.state.active_tasks[task_id] = {
            "task": task,
            "node": target_node,
            "status": "pending",
            "created": datetime.now().isoformat(),
        }
        self.state.version += 1
        self.save()
        
        return {
            "task_id": task_id,
            "assigned_to": target_node,
            "status": "pending",
        }
    
    def sync_to_satellite(self, target_path: str, exclude: List[str] = None):
        """
        Sync the ebook project to a satellite location.
        
        This creates a clone that can run independently.
        """
        exclude = exclude or [
            "__pycache__",
            ".venv",
            "env",
            ".git",
            "*.pyc",
            ".cognitive",  # Each node has its own cognitive state
        ]
        
        source = PROJECT_ROOT
        target = Path(target_path)
        
        # Create target directory
        target.mkdir(parents=True, exist_ok=True)
        
        synced_files = 0
        
        for root, dirs, files in os.walk(source):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in exclude and not d.startswith('.')]
            
            rel_root = Path(root).relative_to(source)
            target_dir = target / rel_root
            target_dir.mkdir(parents=True, exist_ok=True)
            
            for f in files:
                # Skip excluded patterns
                if any(f.endswith(e.replace('*', '')) for e in exclude if '*' in e):
                    continue
                
                src_file = Path(root) / f
                dst_file = target_dir / f
                
                # Only copy if newer or missing
                if not dst_file.exists() or src_file.stat().st_mtime > dst_file.stat().st_mtime:
                    shutil.copy2(src_file, dst_file)
                    synced_files += 1
        
        return {
            "success": True,
            "source": str(source),
            "target": str(target),
            "files_synced": synced_files,
        }
    
    def generate_satellite_config(self, node_name: str, node_role: str,
                                   primary_ip: str) -> str:
        """Generate configuration for a new satellite."""
        config = {
            "node_name": node_name,
            "node_role": node_role,
            "primary_node": {
                "ip": primary_ip,
                "port": 5000,
            },
            "capabilities": self._suggest_capabilities(node_role),
            "auto_sync": True,
            "sync_interval_minutes": 15,
        }
        
        return json.dumps(config, indent=2)
    
    def _suggest_capabilities(self, role: str) -> List[str]:
        """Suggest capabilities based on role."""
        if role == "compute":
            return ["gpu", "heavy", "ml", "training", "rendering", "simulation"]
        elif role == "satellite":
            return ["experiment", "sandbox", "test", "backup", "monitoring"]
        else:
            return ["general", "gui", "editing"]
    
    def get_network_status(self) -> Dict:
        """Get status of the entire network."""
        return {
            "this_node": self.this_node,
            "total_nodes": len(self.nodes),
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "active_tasks": len(self.state.active_tasks),
            "state_version": self.state.version,
        }


# Global manager
_satellite_mgr = SatelliteManager()


def register_satellite_tools(mcp):
    """Register satellite tools with MCP."""
    
    @mcp.tool()
    def satellite_register_this(name: str, role: str, capabilities: str) -> str:
        """
        Register this machine as an Akashic node.
        
        Args:
            name: Node name (e.g., "windows-primary", "linux-lab")
            role: primary, satellite, or compute
            capabilities: Comma-separated (e.g., "gui,editing,general")
        """
        caps = [c.strip() for c in capabilities.split(",")]
        result = _satellite_mgr.register_this_node(name, role, caps)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def satellite_add_remote(name: str, ip: str, role: str, 
                             capabilities: str, port: int = 5000) -> str:
        """
        Add a remote node to the network.
        
        Args:
            name: Node name
            ip: IP address
            role: primary, satellite, or compute
            capabilities: Comma-separated
            port: Agent port (default 5000)
        """
        caps = [c.strip() for c in capabilities.split(",")]
        result = _satellite_mgr.add_remote_node(name, ip, role, caps, port)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def satellite_sync_to(target_path: str) -> str:
        """
        Sync ebook project to a satellite location.
        
        Args:
            target_path: Where to sync (local path or network share)
        """
        result = _satellite_mgr.sync_to_satellite(target_path)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def satellite_distribute_task(task_type: str, payload: str,
                                   target_node: str = "") -> str:
        """
        Distribute a task to a node.
        
        Args:
            task_type: Type of task (gpu, experiment, general, etc.)
            payload: JSON payload for the task
            target_node: Specific node (or auto-select)
        """
        try:
            task_payload = json.loads(payload)
        except:
            task_payload = {"data": payload}
        
        task = {
            "type": task_type,
            "payload": task_payload,
            "target_node": target_node or None,
        }
        
        result = _satellite_mgr.distribute_task(task)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def satellite_network_status() -> str:
        """Get status of the Akashic network."""
        return json.dumps(_satellite_mgr.get_network_status(), indent=2)
    
    @mcp.tool()
    def satellite_generate_config(node_name: str, node_role: str,
                                   primary_ip: str) -> str:
        """
        Generate configuration for a new satellite.
        
        Args:
            node_name: Name for the new node
            node_role: satellite or compute
            primary_ip: IP of the primary (Windows) node
        """
        config = _satellite_mgr.generate_satellite_config(node_name, node_role, primary_ip)
        return config


if __name__ == "__main__":
    # Test satellite system
    mgr = SatelliteManager()
    
    print("Registering this node...")
    result = mgr.register_this_node("test-node", "primary", ["gui", "editing"])
    print(json.dumps(result, indent=2))
    
    print("\nNetwork status:")
    print(json.dumps(mgr.get_network_status(), indent=2))
