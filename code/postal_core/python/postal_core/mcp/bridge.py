"""
MCP Bridge Fairy - Connects external LLM to the postal system.

This fairy:
1. Runs the MCP server for Claude connections
2. Bridges tool calls to postal messages
3. Monitors for external connections
4. Provides introspection tools for system understanding

Part of P00_Autonomic - the nervous system layer.
"""

from __future__ import annotations

import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Set
from datetime import datetime

# Add paths for imports
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    from fairy_template.states import FairyState
    HAS_FAIRY = True
except ImportError:
    HAS_FAIRY = False
    Fairy = object
    FairyState = None

from .server import MCPServer, create_mcp_server, HAS_MCP
from .tools import register_all_tools


class MCPBridgeFairy(Fairy if HAS_FAIRY else object):
    """
    Fairy that bridges MCP to the postal system.

    When Claude connects via MCP, this fairy:
    - Receives tool calls
    - Translates to postal messages
    - Returns results
    - Maintains connection state
    """

    ACTOR_NAME = "MCPBridgeFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "mcp"
    NEEDS_TENSOR = True
    NEEDS_HEARTBEAT = True

    def __init__(self, fabric=None):
        """
        Initialize MCP Bridge Fairy.

        Args:
            fabric: TensorFabric for messaging (optional during standalone MCP mode)
        """
        if HAS_FAIRY:
            super().__init__(fabric)

        self._server: Optional[MCPServer] = None
        self._connected = False
        self._last_activity: Optional[datetime] = None
        self._tool_calls = 0
        self._server_thread: Optional[threading.Thread] = None

    def get_capabilities(self) -> Set[str]:
        """Declare capabilities."""
        return {
            "mcp.serve",
            "mcp.bridge",
            "system.introspect",
            "llm.connect",
        }

    def on_boot(self) -> bool:
        """
        Boot sequence - create MCP server and register tools.
        """
        # Create MCP server
        self._server = create_mcp_server(name="akashic", version="2.0.0")

        # Register all tools (introspection, file_ops, memory, fairy, unconscious)
        register_all_tools(self._server)

        # Set up postal callback if we have fabric
        if hasattr(self, "fabric") and self.fabric:
            self._server.set_postal_callback(self._on_tool_result)

            # Subscribe to MCP-related postal topics
            self.fabric.subscribe("mcp.status_request", self._on_status_request, "mcp-status")

        return True

    def on_tick(self, beat: int) -> None:
        """Heartbeat - monitor connection state."""
        # Check if we've had recent activity
        if self._last_activity:
            age = (datetime.now() - self._last_activity).total_seconds()
            if age > 60:
                self._connected = False

    def on_shutdown(self) -> bool:
        """Shutdown sequence."""
        self._connected = False
        return True

    def _on_tool_result(self, tool_name: str, result: Dict) -> None:
        """Called when a tool completes - bridge to postal."""
        self._tool_calls += 1
        self._last_activity = datetime.now()
        self._connected = True

        if hasattr(self, "fabric") and self.fabric:
            self.fabric.publish(
                "mcp.tool_result",
                {
                    "tool": tool_name,
                    "result": result,
                    "ts": time.time(),
                },
            )

    def _on_status_request(self, envelope) -> None:
        """Handle status request from postal."""
        if hasattr(self, "fabric") and self.fabric:
            self.fabric.publish(
                "mcp.status",
                self.get_status(),
            )

    def get_status(self) -> Dict[str, Any]:
        """Get bridge status."""
        return {
            "connected": self._connected,
            "mcp_available": HAS_MCP,
            "tool_calls": self._tool_calls,
            "last_activity": self._last_activity.isoformat() if self._last_activity else None,
            "server_running": self._server_thread is not None and self._server_thread.is_alive(),
        }

    def get_server(self) -> Optional[MCPServer]:
        """Get the MCP server instance."""
        return self._server

    def run_server(self, transport: str = "stdio", blocking: bool = True) -> None:
        """
        Run the MCP server.

        Args:
            transport: "stdio" for CLI, "sse" for HTTP
            blocking: If True, blocks until server stops
        """
        if not self._server:
            print("[MCPBridgeFairy] No server - call boot() first")
            return

        if blocking:
            self._server.run(transport=transport)
        else:
            self._server_thread = threading.Thread(
                target=self._server.run,
                args=(transport,),
                daemon=True,
            )
            self._server_thread.start()

    def list_tools(self) -> list:
        """List all registered MCP tools."""
        if self._server:
            return self._server.list_tools()
        return []


# =============================================================================
# STANDALONE RUNNER
# =============================================================================

def main():
    """Run MCP server standalone (without full Akashic boot)."""
    print("[MCPBridge] Starting standalone MCP server...", file=sys.stderr)

    # Create bridge without fabric
    bridge = MCPBridgeFairy(fabric=None)
    bridge.on_boot()

    # List available tools
    tools = bridge.list_tools()
    print(f"[MCPBridge] Registered {len(tools)} tools:", file=sys.stderr)
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}", file=sys.stderr)

    # Run server (stdio mode for Claude Desktop)
    print("[MCPBridge] Running stdio server...", file=sys.stderr)
    bridge.run_server(transport="stdio", blocking=True)


if __name__ == "__main__":
    main()
