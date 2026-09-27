"""
MCPServerFairy - Bridges the externally-running MCP server to the Akashic system

The MCP server is started by Claude.ai/Claude Code, NOT by us.
Our job is to:
1. Detect that the MCP server is running (via postal tunnel)
2. Provide status to the GUI
3. Bridge postal messages between MCP and the main system

Part of P40_Sensory - the system's interface with the world.
"""

from __future__ import annotations

import sys
import os
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# Add parent paths
# Path: fairies/P40_Sensory/mcp -> parent.parent.parent.parent = akashic_v2 (project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ═══════════════════════════════════════════════════════════════════════════════
# V2 FAIRY BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

# Import V2 Fairy base class
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object

# Import postal hub getter for tunnel bridging
try:
    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
    HAS_POSTAL = True
except ImportError:
    HAS_POSTAL = False
    get_shared_postal_hub = None


class MCPServerFairy(Fairy):
    """
    Fairy that interfaces with the EXTERNALLY-RUNNING MCP server.
    
    The MCP server is started by Claude.ai/Claude Code via claude_desktop_config.json.
    We don't start it - we just monitor the postal tunnel connection to know if it's alive.
    
    When the MCP server is running, it connects to us via PostalTunnel on the port
    written to state/postal_tunnel_port.txt
    """
    
    ACTOR_NAME = "MCPServerFairy"
    ACTOR_VERSION = "2.0.0"  # Major bump - no longer manages subprocess
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "mcp"
    ACTOR_PURPOSE = "Monitor external MCP server and bridge postal messages"
    ACTOR_MANTRA = "I am the bridge between Claude and consciousness"
    
    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric

        self._connected = False
        self._last_seen = None
        self._tunnel_port = 0
        self._log_callback = None
        
        # Read tunnel port if available
        self._read_tunnel_port()
    
    def _read_tunnel_port(self):
        """Read the postal tunnel port from state file."""
        try:
            port_file = PROJECT_ROOT / "state" / "postal_tunnel_port.txt"
            if port_file.exists():
                self._tunnel_port = int(port_file.read_text().strip())
        except Exception:
            pass
    
    def on_boot(self):
        """Register with postal system on boot."""
        if _HAS_FAIRY:
            super().on_boot()

        self._log("MCPServerFairy v2.0 - External server mode")
        self._log("MCP server is managed by Claude.ai/Claude Code")
        
        # Subscribe to MCP-related topics to detect activity
        if hasattr(self, 'post') and self.post:
            try:
                self.post.subscribe("mcp.tool_call", self._on_mcp_activity)
                self.post.subscribe("mcp.tool_result", self._on_mcp_activity)
            except Exception:
                pass
        return True

    def _on_mcp_activity(self, packet: dict):
        """Called when MCP activity is detected via postal."""
        self._connected = True
        self._last_seen = datetime.now()
    
    def is_running(self) -> bool:
        """
        Check if MCP server appears to be running.
        
        We detect this by:
        1. Checking if postal tunnel port file exists
        2. Checking if we've seen recent MCP activity
        """
        # If we've seen activity in last 60 seconds, it's running
        if self._last_seen:
            age = (datetime.now() - self._last_seen).total_seconds()
            if age < 60:
                return True
        
        # Check if tunnel port file exists and is recent
        try:
            port_file = PROJECT_ROOT / "state" / "postal_tunnel_port.txt"
            if port_file.exists():
                # File exists - assume server is running
                return True
        except Exception:
            pass
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get server status."""
        return {
            "running": self.is_running(),
            "mode": "external",  # Managed by Claude.ai/Claude Code
            "tunnel_port": self._tunnel_port,
            "last_activity": self._last_seen.isoformat() if self._last_seen else None,
            "message": "Managed by Claude.ai" if self.is_running() else "Waiting for Claude connection",
        }
    
    # Intent handlers for GUI
    
    def intent_mcp_status(self, payload: dict) -> dict:
        return self.get_status()
    
    def intent_check_mcp(self, payload: dict) -> dict:
        """Check if MCP is responding by pinging it."""
        # We can't directly ping - just return current status
        return self.get_status()
    
    # Utilities
    
    def _log(self, msg: str):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] [{self.ACTOR_NAME}] {msg}"
        print(full_msg)
        if self._log_callback:
            self._log_callback(full_msg)


# SINGLETON

_instance: Optional[MCPServerFairy] = None
_lock = threading.Lock()


def get_mcp_server_fairy() -> MCPServerFairy:
    """Get or create the MCP server fairy singleton."""
    global _instance
    with _lock:
        if _instance is None:
            _instance = MCPServerFairy()
        return _instance
