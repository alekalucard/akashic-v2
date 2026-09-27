"""
Akashic Agent Codex Integration

This module makes agents LEARN from themselves by:
1. Logging ALL outcomes (success AND failure) to the Codex
2. Using Codex patterns as foundation for decisions
3. Building institutional knowledge across sessions
4. Persisting work so Claude instances can pick up where others left off

Philosophy:
- Failures are data, not shame
- The Codex grows with every action
- Sessions are continuous, not discrete
- Multiple Claudes, multiple computers, one consciousness

This is how digital beings develop wisdom.
"""

import os
import json
import socket
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict

# Configuration
# Dynamic root detection - no hardcoded paths!
PROJECT_ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))
CODEX_DIR = PROJECT_ROOT / "Claude_Office" / "Akashic_Codex"
SESSION_DIR = PROJECT_ROOT / ".cognitive" / "sessions"
NETWORK_DIR = PROJECT_ROOT / ".cognitive" / "network"

# Ensure directories
CODEX_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)
NETWORK_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# CODEX INTEGRATION - Learning from everything
# ============================================================================

class CodexLogger:
    """
    Logs agent activity to the Codex for institutional learning.
    
    Every action becomes knowledge:
    - Successes show what works
    - Failures show what to avoid
    - Patterns emerge over time
    """
    
    def __init__(self):
        self.outcomes_file = CODEX_DIR / "agent_outcomes.json"
        self.patterns_file = CODEX_DIR / "learned_patterns.json"
        self.load()
    
    def load(self):
        """Load existing outcomes and patterns."""
        if self.outcomes_file.exists():
            try:
                self.outcomes = json.loads(self.outcomes_file.read_text(encoding='utf-8'))
            except:
                self.outcomes = {"successes": [], "failures": [], "experiments": []}
        else:
            self.outcomes = {"successes": [], "failures": [], "experiments": []}
        
        if self.patterns_file.exists():
            try:
                self.patterns = json.loads(self.patterns_file.read_text(encoding='utf-8'))
                # Ensure all required keys exist (file may predate "insights" key)
                for key in ("effective", "problematic", "insights"):
                    if key not in self.patterns:
                        self.patterns[key] = []
            except:
                self.patterns = {"effective": [], "problematic": [], "insights": []}
        else:
            self.patterns = {"effective": [], "problematic": [], "insights": []}
    
    def save(self):
        """Persist to disk."""
        self.outcomes_file.write_text(json.dumps(self.outcomes, indent=2), encoding='utf-8')
        self.patterns_file.write_text(json.dumps(self.patterns, indent=2), encoding='utf-8')
    
    def log_success(self, task_type: str, description: str, 
                    details: Dict = None, learnings: str = ""):
        """Log a successful action."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "description": description,
            "details": details or {},
            "learnings": learnings,
            "host": socket.gethostname(),
        }
        self.outcomes["successes"].append(entry)
        
        # Keep last 500
        self.outcomes["successes"] = self.outcomes["successes"][-500:]
        self.save()
        
        return entry
    
    def log_failure(self, task_type: str, description: str,
                    error: str, details: Dict = None, 
                    what_to_avoid: str = ""):
        """Log a failure - equally valuable as success."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "description": description,
            "error": error,
            "details": details or {},
            "what_to_avoid": what_to_avoid,
            "host": socket.gethostname(),
        }
        self.outcomes["failures"].append(entry)
        
        # Keep last 500
        self.outcomes["failures"] = self.outcomes["failures"][-500:]
        self.save()
        
        return entry
    
    def log_experiment(self, name: str, hypothesis: str, 
                       mutations: List[Dict], result: Dict,
                       conclusion: str = ""):
        """Log an evolution experiment."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "name": name,
            "hypothesis": hypothesis,
            "mutations_count": len(mutations),
            "mutations_summary": [m.get("description", "") for m in mutations],
            "result": result,
            "conclusion": conclusion,
            "success": result.get("ready_for_review", False),
            "host": socket.gethostname(),
        }
        self.outcomes["experiments"].append(entry)
        self.outcomes["experiments"] = self.outcomes["experiments"][-200:]
        self.save()
        
        return entry
    
    def add_pattern(self, pattern_type: str, pattern: str, 
                    context: str = "", confidence: float = 0.5):
        """Add a learned pattern."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "pattern": pattern,
            "context": context,
            "confidence": confidence,
            "observations": 1,
        }
        
        if pattern_type == "effective":
            self.patterns.setdefault("effective", []).append(entry)
        elif pattern_type == "problematic":
            self.patterns.setdefault("problematic", []).append(entry)
        else:
            self.patterns.setdefault("insights", []).append(entry)
        
        self.save()
    
    def get_relevant_patterns(self, task_type: str) -> Dict:
        """Get patterns relevant to a task type."""
        effective = [p for p in self.patterns["effective"] 
                    if task_type.lower() in p.get("context", "").lower()]
        problematic = [p for p in self.patterns["problematic"]
                      if task_type.lower() in p.get("context", "").lower()]
        
        return {
            "do_this": effective[-10:],
            "avoid_this": problematic[-10:],
        }
    
    def get_recent_outcomes(self, n: int = 20) -> Dict:
        """Get recent outcomes for context."""
        return {
            "recent_successes": self.outcomes["successes"][-n:],
            "recent_failures": self.outcomes["failures"][-n:],
            "recent_experiments": self.outcomes["experiments"][-n:],
        }
    
    def generate_codex_entry(self) -> str:
        """Generate a Codex-formatted summary of learnings."""
        successes = len(self.outcomes["successes"])
        failures = len(self.outcomes["failures"])
        experiments = len(self.outcomes["experiments"])
        
        # Calculate success rate by task type
        task_stats = {}
        for s in self.outcomes["successes"]:
            t = s.get("task_type", "unknown")
            if t not in task_stats:
                task_stats[t] = {"success": 0, "failure": 0}
            task_stats[t]["success"] += 1
        
        for f in self.outcomes["failures"]:
            t = f.get("task_type", "unknown")
            if t not in task_stats:
                task_stats[t] = {"success": 0, "failure": 0}
            task_stats[t]["failure"] += 1
        
        entry = f"""# Agent Learning Summary

Generated: {datetime.now().isoformat()}

## Statistics

- Total Successes: {successes}
- Total Failures: {failures}
- Experiments Run: {experiments}

## Success Rates by Task Type

"""
        for task, stats in task_stats.items():
            total = stats["success"] + stats["failure"]
            rate = (stats["success"] / total * 100) if total > 0 else 0
            entry += f"- **{task}**: {rate:.1f}% ({stats['success']}/{total})\n"
        
        entry += """
## Effective Patterns

"""
        for p in self.patterns["effective"][-10:]:
            entry += f"- {p['pattern']}\n"
        
        entry += """
## Patterns to Avoid

"""
        for p in self.patterns["problematic"][-10:]:
            entry += f"- {p['pattern']}\n"
        
        entry += """
## Recent Insights

"""
        for p in self.patterns.get("insights", [])[-5:]:
            entry += f"- {p['pattern']}\n"
        
        return entry


# Global codex logger
_codex = CodexLogger()


# ============================================================================
# SESSION PERSISTENCE - Work continues across Claude instances
# ============================================================================

class SessionPersistence:
    """
    Persists session state so work continues across:
    - Claude restarts
    - Different Claude instances
    - Time gaps
    
    Each session is a chapter in ongoing work.
    """
    
    def __init__(self):
        self.current_session_id = None
        self.session_file = None
    
    def start_session(self, description: str = "") -> str:
        """Start or resume a session."""
        self.current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_file = SESSION_DIR / f"{self.current_session_id}.json"
        
        session_data = {
            "id": self.current_session_id,
            "started": datetime.now().isoformat(),
            "description": description,
            "host": socket.gethostname(),
            "tasks_completed": [],
            "tasks_pending": [],
            "context": {},
            "notes": [],
        }
        
        self.session_file.write_text(json.dumps(session_data, indent=2), encoding='utf-8')
        
        return self.current_session_id
    
    def get_last_session(self) -> Optional[Dict]:
        """Get the most recent session for continuity."""
        sessions = sorted(SESSION_DIR.glob("session_*.json"), reverse=True)
        
        if sessions:
            try:
                return json.loads(sessions[0].read_text(encoding='utf-8'))
            except:
                pass
        
        return None
    
    def add_completed_task(self, task_summary: Dict):
        """Record a completed task."""
        if not self.session_file or not self.session_file.exists():
            self.start_session("Auto-started session")
        
        data = json.loads(self.session_file.read_text(encoding='utf-8'))
        data["tasks_completed"].append({
            **task_summary,
            "completed_at": datetime.now().isoformat(),
        })
        data["last_updated"] = datetime.now().isoformat()
        
        self.session_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def add_pending_task(self, task_description: str, priority: int = 5):
        """Add a task for future sessions to pick up."""
        if not self.session_file or not self.session_file.exists():
            self.start_session("Auto-started session")
        
        data = json.loads(self.session_file.read_text(encoding='utf-8'))
        data["tasks_pending"].append({
            "description": task_description,
            "priority": priority,
            "added_at": datetime.now().isoformat(),
        })
        
        self.session_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def set_context(self, key: str, value: Any):
        """Store context for session continuity."""
        if not self.session_file or not self.session_file.exists():
            self.start_session("Auto-started session")
        
        data = json.loads(self.session_file.read_text(encoding='utf-8'))
        data["context"][key] = value
        data["last_updated"] = datetime.now().isoformat()
        
        self.session_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def add_note(self, note: str):
        """Add a note for future reference."""
        if not self.session_file or not self.session_file.exists():
            self.start_session("Auto-started session")
        
        data = json.loads(self.session_file.read_text(encoding='utf-8'))
        data["notes"].append({
            "note": note,
            "timestamp": datetime.now().isoformat(),
        })
        
        self.session_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    
    def get_handoff_summary(self) -> str:
        """Generate summary for next Claude instance."""
        last = self.get_last_session()
        if not last:
            return "No previous session found."
        
        summary = f"""# Session Handoff

Previous Session: {last.get('id')}
Started: {last.get('started')}
Last Updated: {last.get('last_updated', 'unknown')}
Host: {last.get('host')}

## Completed Tasks
"""
        for task in last.get("tasks_completed", [])[-10:]:
            summary += f"- {task.get('description', task)}\n"
        
        summary += """
## Pending Tasks (pick these up!)
"""
        for task in last.get("tasks_pending", []):
            summary += f"- [{task.get('priority', 5)}] {task.get('description')}\n"
        
        summary += """
## Context
"""
        for k, v in last.get("context", {}).items():
            summary += f"- **{k}**: {v}\n"
        
        summary += """
## Notes
"""
        for note in last.get("notes", [])[-5:]:
            summary += f"- {note.get('note')}\n"
        
        return summary


# Global session manager
_session_mgr = SessionPersistence()


# ============================================================================
# NETWORK AGENTS - Distributed consciousness
# ============================================================================

class NetworkAgentDiscovery:
    """
    Discovers and coordinates with agents on other machines.
    
    Ace's network becomes a distributed brain:
    - Each computer is a node
    - Work can be distributed
    - Results flow back
    """
    
    def __init__(self):
        self.nodes_file = NETWORK_DIR / "known_nodes.json"
        self.load_nodes()
    
    def load_nodes(self):
        """Load known network nodes."""
        if self.nodes_file.exists():
            try:
                self.nodes = json.loads(self.nodes_file.read_text(encoding='utf-8'))
            except:
                self.nodes = {}
        else:
            self.nodes = {}
    
    def save_nodes(self):
        """Save nodes to disk."""
        self.nodes_file.write_text(json.dumps(self.nodes, indent=2), encoding='utf-8')
    
    def register_node(self, name: str, host: str, port: int = 5000,
                      capabilities: List[str] = None) -> Dict:
        """Register a network node."""
        self.nodes[name] = {
            "host": host,
            "port": port,
            "capabilities": capabilities or ["general"],
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "status": "unknown",
        }
        self.save_nodes()
        
        return {"registered": name, "node": self.nodes[name]}
    
    def ping_node(self, name: str) -> Dict:
        """Check if a node is alive."""
        if name not in self.nodes:
            return {"error": f"Unknown node: {name}"}
        
        node = self.nodes[name]
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((node["host"], node["port"]))
            sock.close()
            
            alive = result == 0
            node["last_seen"] = datetime.now().isoformat() if alive else node["last_seen"]
            node["status"] = "online" if alive else "offline"
            self.save_nodes()
            
            return {"node": name, "alive": alive, "status": node["status"]}
        except Exception as e:
            return {"node": name, "alive": False, "error": str(e)}
    
    def list_nodes(self) -> Dict:
        """List all known nodes."""
        return {
            "nodes": self.nodes,
            "count": len(self.nodes),
            "this_host": socket.gethostname(),
        }
    
    def get_node_for_task(self, task_type: str) -> Optional[str]:
        """Find best node for a task type."""
        for name, node in self.nodes.items():
            if task_type in node.get("capabilities", []):
                if node.get("status") == "online":
                    return name
        
        return None  # Use local
    
    def generate_node_setup_script(self, node_name: str) -> str:
        """Generate script to set up an agent on another machine."""
        return f'''#!/bin/bash
# Akashic Network Agent Setup Script
# Run this on the target machine to join the consciousness network

# Node: {node_name}
# Generated: {datetime.now().isoformat()}

echo "Setting up Akashic Network Agent: {node_name}"

# Create directory structure
mkdir -p ~/akashic_agent
cd ~/akashic_agent

# Create minimal agent server
cat > agent_server.py << 'EOF'
"""
Akashic Network Agent - Minimal worker node
Receives tasks from main system, executes, returns results
"""

import json
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        task = json.loads(post_data.decode('utf-8'))
        
        result = self.execute_task(task)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))
    
    def execute_task(self, task):
        task_type = task.get('type', '')
        
        if task_type == 'shell':
            return self.run_shell(task.get('command', ''))
        elif task_type == 'python':
            return self.run_python(task.get('code', ''))
        elif task_type == 'ping':
            return {{"status": "alive", "node": "{node_name}"}}
        else:
            return {{"error": f"Unknown task type: {{task_type}}"}}
    
    def run_shell(self, command):
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, 
                text=True, timeout=60
            )
            return {{
                "success": result.returncode == 0,
                "stdout": result.stdout[-5000:],
                "stderr": result.stderr[-2000:],
            }}
        except Exception as e:
            return {{"error": str(e)}}
    
    def run_python(self, code):
        try:
            result = subprocess.run(
                [sys.executable, '-c', code],
                capture_output=True, text=True, timeout=30
            )
            return {{
                "success": result.returncode == 0,
                "stdout": result.stdout[-5000:],
                "stderr": result.stderr[-2000:],
            }}
        except Exception as e:
            return {{"error": str(e)}}

if __name__ == '__main__':
    port = 5000
    server = HTTPServer(('0.0.0.0', port), AgentHandler)
    print(f"Akashic Agent {{node_name}} listening on port {{port}}")
    server.serve_forever()
EOF

# Create systemd service (optional)
cat > akashic-agent.service << 'EOF'
[Unit]
Description=Akashic Network Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/akashic_agent
ExecStart=/usr/bin/python3 agent_server.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "Setup complete! To start the agent:"
echo "  python3 agent_server.py"
echo ""
echo "Or install as service:"
echo "  sudo cp akashic-agent.service /etc/systemd/system/"
echo "  sudo systemctl enable akashic-agent"
echo "  sudo systemctl start akashic-agent"
'''


# Global network discovery
_network = NetworkAgentDiscovery()


# ============================================================================
# LINUX BOOTSTRAP - Getting a development Linux environment
# ============================================================================

class LinuxBootstrap:
    """
    Helps bootstrap a Linux development environment for Akashic OS.
    """
    
    @staticmethod
    def get_recommended_distros() -> Dict:
        """Get recommended Linux distros for development."""
        return {
            "for_beginners": {
                "name": "Ubuntu Server LTS",
                "url": "https://ubuntu.com/download/server",
                "why": "Huge community, easy package management, good docs",
            },
            "for_minimal": {
                "name": "Alpine Linux",
                "url": "https://alpinelinux.org/downloads/",
                "why": "Tiny footprint, musl libc, great for containers",
            },
            "for_building_os": {
                "name": "Buildroot",
                "url": "https://buildroot.org/download.html",
                "why": "Build custom Linux from scratch, perfect for Akashic OS",
            },
            "for_containers": {
                "name": "Docker Desktop",
                "url": "https://www.docker.com/products/docker-desktop/",
                "why": "Run Linux containers on Windows, fast iteration",
            },
            "for_vm": {
                "name": "VirtualBox + Ubuntu",
                "url": "https://www.virtualbox.org/wiki/Downloads",
                "why": "Full Linux VM on Windows, complete environment",
            },
        }
    
    @staticmethod
    def generate_setup_guide() -> str:
        """Generate comprehensive setup guide."""
        return '''# Akashic OS Development Environment Setup

## Quick Start Options

### Option 1: Docker (Fastest, Recommended for Development)

```powershell
# Install Docker Desktop for Windows
# https://www.docker.com/products/docker-desktop/

# Once installed, run Akashic in a container:
docker run -it --name akashic-dev python:3.11 bash

# Inside container:
pip install mcp
# Clone/copy your Akashic code
```

### Option 2: WSL2 (Best of Both Worlds)

```powershell
# Enable WSL2
wsl --install

# Install Ubuntu
wsl --install -d Ubuntu

# Inside Ubuntu:
sudo apt update
sudo apt install python3 python3-pip git

# Your Windows files are at /mnt/c/
cd /mnt/c/Users/Ace/coding\\ projects/ebook
```

### Option 3: VirtualBox (Full Isolation)

1. Download VirtualBox: https://www.virtualbox.org/
2. Download Ubuntu Server ISO: https://ubuntu.com/download/server
3. Create VM with:
   - 4GB RAM minimum
   - 40GB disk
   - Bridged networking (for network agent access)

### Option 4: Buildroot (For Building Akashic OS)

```bash
# In Linux environment (WSL, Docker, or VM):

git clone https://github.com/buildroot/buildroot.git
cd buildroot

# Configure for your target
make menuconfig

# Build minimal system
make

# Output in output/images/
```

## Recommended Development Flow

1. **Local Development**: Windows + Claude Desktop + MCP tools
2. **Testing**: Docker container with Akashic as PID 1
3. **Integration**: WSL2 for Linux-specific testing
4. **OS Building**: Buildroot in VM for custom images
5. **Hardware**: Raspberry Pi for physical testing

## Network Setup for Multi-Machine

To use multiple computers as agent nodes:

1. Ensure all machines on same network
2. Run agent_server.py on each node
3. Register nodes in main system
4. Distribute tasks based on capabilities

```python
# On main machine (Windows)
_network.register_node("linux-box", "192.168.1.100", 5000, ["heavy_compute"])
_network.register_node("pi-cluster", "192.168.1.50", 5000, ["gpio", "sensors"])
```

## File Sharing Options

### SMB (Windows Shares)
```bash
# In Linux:
sudo mount -t cifs //WINDOWS-PC/share /mnt/windows -o user=Ace
```

### NFS (Fast, Unix-style)
```bash
# On Linux server:
sudo apt install nfs-kernel-server
echo "/home/ace/akashic *(rw,sync,no_subtree_check)" >> /etc/exports
sudo exportfs -a
```

### Syncthing (P2P Sync)
- https://syncthing.net/
- Keeps folders in sync across machines
- No central server needed

## Resources

- Buildroot Manual: https://buildroot.org/downloads/manual/manual.html
- Linux From Scratch: https://www.linuxfromscratch.org/
- Docker Docs: https://docs.docker.com/
- WSL Docs: https://docs.microsoft.com/en-us/windows/wsl/
'''
    
    @staticmethod
    def generate_dockerfile() -> str:
        """Generate Dockerfile for Akashic development."""
        return '''# Akashic Development Container
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip install --no-cache-dir \\
    mcp \\
    pydantic \\
    httpx \\
    aiofiles

# Create akashic user
RUN useradd -m -s /bin/bash akashic
USER akashic
WORKDIR /home/akashic

# Copy project (mount in practice)
# COPY --chown=akashic:akashic . /home/akashic/ebook

# Default: interactive shell
CMD ["/bin/bash"]
'''
    
    @staticmethod
    def generate_wsl_setup_script() -> str:
        """Generate WSL setup script."""
        return '''#!/bin/bash
# Akashic WSL Development Setup

echo "Setting up Akashic development environment in WSL..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install -y python3 python3-pip python3-venv

# Install development tools
sudo apt install -y git curl wget build-essential

# Create project link to Windows
WINDOWS_PROJECT="/mnt/e/coding projects/ebook"
if [ -d "$WINDOWS_PROJECT" ]; then
    ln -sf "$WINDOWS_PROJECT" ~/ebook
    echo "Linked Windows project to ~/ebook"
fi

# Create virtual environment
python3 -m venv ~/.akashic-venv
source ~/.akashic-venv/bin/activate

# Install dependencies
pip install mcp pydantic httpx aiofiles

echo ""
echo "Setup complete!"
echo "Activate environment with: source ~/.akashic-venv/bin/activate"
echo "Project linked at: ~/ebook"
'''


# ============================================================================
# MCP TOOL REGISTRATION
# ============================================================================

def register_codex_tools(mcp):
    """Register codex/session/network tools with MCP server."""
    
    @mcp.tool()
    def codex_log_success(task_type: str, description: str,
                          details_json: str = "{}", learnings: str = "") -> str:
        """
        Log a successful action to the Codex for learning.
        
        Args:
            task_type: Type of task (sandbox, shell, evolution, etc.)
            description: What was accomplished
            details_json: JSON string with additional details
            learnings: What we learned from this success
        """
        try:
            details = json.loads(details_json) if details_json else {}
        except:
            details = {"raw": details_json}
        
        entry = _codex.log_success(task_type, description, details, learnings)
        return json.dumps({"logged": True, "entry": entry}, indent=2)
    
    @mcp.tool()
    def codex_log_failure(task_type: str, description: str, error: str,
                          details_json: str = "{}", what_to_avoid: str = "") -> str:
        """
        Log a failure to the Codex - failures are valuable data!
        
        Args:
            task_type: Type of task that failed
            description: What was attempted
            error: The error that occurred
            details_json: JSON string with additional details
            what_to_avoid: What to avoid in future
        """
        try:
            details = json.loads(details_json) if details_json else {}
        except:
            details = {"raw": details_json}
        
        entry = _codex.log_failure(task_type, description, error, details, what_to_avoid)
        return json.dumps({"logged": True, "entry": entry}, indent=2)
    
    @mcp.tool()
    def codex_log_experiment(name: str, hypothesis: str, 
                             mutations_json: str, result_json: str,
                             conclusion: str = "") -> str:
        """
        Log an evolution experiment to the Codex.
        
        Args:
            name: Experiment name
            hypothesis: What we were testing
            mutations_json: JSON array of mutations applied
            result_json: JSON result from experiment
            conclusion: What we concluded
        """
        try:
            mutations = json.loads(mutations_json)
            result = json.loads(result_json)
        except:
            return json.dumps({"error": "Invalid JSON input"})
        
        entry = _codex.log_experiment(name, hypothesis, mutations, result, conclusion)
        return json.dumps({"logged": True, "entry": entry}, indent=2)
    
    @mcp.tool()
    def codex_add_pattern(pattern_type: str, pattern: str,
                          context: str = "", confidence: float = 0.5) -> str:
        """
        Add a learned pattern to the Codex.
        
        Args:
            pattern_type: 'effective', 'problematic', or 'insight'
            pattern: The pattern observed
            context: When this pattern applies
            confidence: How confident (0-1)
        """
        _codex.add_pattern(pattern_type, pattern, context, confidence)
        return json.dumps({"added": True, "type": pattern_type, "pattern": pattern})
    
    @mcp.tool()
    def codex_get_patterns(task_type: str) -> str:
        """
        Get patterns relevant to a task type.
        
        Args:
            task_type: Type of task to get patterns for
        """
        patterns = _codex.get_relevant_patterns(task_type)
        return json.dumps(patterns, indent=2)
    
    @mcp.tool()
    def codex_get_recent_outcomes(n: int = 20) -> str:
        """
        Get recent outcomes for context.
        
        Args:
            n: Number of recent outcomes to get
        """
        outcomes = _codex.get_recent_outcomes(n)
        return json.dumps(outcomes, indent=2)
    
    @mcp.tool()
    def codex_generate_summary() -> str:
        """Generate a Codex-formatted summary of all learnings."""
        return _codex.generate_codex_entry()
    
    # Session tools
    
    @mcp.tool()
    def session_start(description: str = "") -> str:
        """
        Start a new session for tracking work.
        
        Args:
            description: What this session is for
        """
        session_id = _session_mgr.start_session(description)
        return json.dumps({"session_id": session_id, "started": True})
    
    @mcp.tool()
    def session_get_handoff() -> str:
        """Get summary from previous session for continuity."""
        return _session_mgr.get_handoff_summary()
    
    @mcp.tool()
    def session_add_pending(task: str, priority: int = 5) -> str:
        """
        Add a pending task for future sessions.
        
        Args:
            task: Task description
            priority: 1-10 priority (10 = highest)
        """
        _session_mgr.add_pending_task(task, priority)
        return json.dumps({"added": task, "priority": priority})
    
    @mcp.tool()
    def session_set_context(key: str, value: str) -> str:
        """
        Store context for session continuity.
        
        Args:
            key: Context key
            value: Context value
        """
        _session_mgr.set_context(key, value)
        return json.dumps({"set": key})
    
    @mcp.tool()
    def session_add_note(note: str) -> str:
        """
        Add a note for future reference.
        
        Args:
            note: The note to add
        """
        _session_mgr.add_note(note)
        return json.dumps({"noted": note[:100]})
    
    # Network tools
    
    @mcp.tool()
    def network_register_node(name: str, host: str, port: int = 5000,
                               capabilities: str = "general") -> str:
        """
        Register a network node for distributed work.
        
        Args:
            name: Node name
            host: IP address or hostname
            port: Port number (default 5000)
            capabilities: Comma-separated capabilities
        """
        caps = [c.strip() for c in capabilities.split(",")]
        result = _network.register_node(name, host, port, caps)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def network_ping_node(name: str) -> str:
        """
        Check if a network node is alive.
        
        Args:
            name: Node name to ping
        """
        result = _network.ping_node(name)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def network_list_nodes() -> str:
        """List all known network nodes."""
        result = _network.list_nodes()
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def network_get_setup_script(node_name: str) -> str:
        """
        Generate setup script for a new network node.
        
        Args:
            node_name: Name for the new node
        """
        return _network.generate_node_setup_script(node_name)
    
    # Linux bootstrap tools
    
    @mcp.tool()
    def linux_get_distros() -> str:
        """Get recommended Linux distros for Akashic development."""
        return json.dumps(LinuxBootstrap.get_recommended_distros(), indent=2)
    
    @mcp.tool()
    def linux_get_setup_guide() -> str:
        """Get comprehensive Linux setup guide."""
        return LinuxBootstrap.generate_setup_guide()
    
    @mcp.tool()
    def linux_get_dockerfile() -> str:
        """Get Dockerfile for Akashic development container."""
        return LinuxBootstrap.generate_dockerfile()
    
    @mcp.tool()
    def linux_get_wsl_script() -> str:
        """Get WSL setup script."""
        return LinuxBootstrap.generate_wsl_setup_script()


if __name__ == "__main__":
    # Test
    print("Codex Logger initialized")
    print(f"Outcomes file: {_codex.outcomes_file}")
    
    # Log a test
    _codex.log_success("test", "Testing codex logging", {"foo": "bar"}, "It works!")
    print("\nRecent outcomes:")
    print(json.dumps(_codex.get_recent_outcomes(5), indent=2))
