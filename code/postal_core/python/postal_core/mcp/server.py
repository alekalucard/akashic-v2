"""
MCP Server - FastMCP server with stdout protection.

CRITICAL: MCP uses stdout for JSON-RPC protocol.
Any print() or stdout write breaks the protocol.
This module redirects all stdout to stderr before importing anything.
"""

from __future__ import annotations

import sys
import os
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
from datetime import datetime

# =============================================================================
# STDOUT PROTECTION - Must happen FIRST, before any other imports
# =============================================================================

_original_stdout = sys.stdout


class _StderrRedirector:
    """Redirects all writes to stderr instead of stdout."""

    def write(self, text):
        sys.stderr.write(text)

    def flush(self):
        sys.stderr.flush()


# Replace stdout with redirector IMMEDIATELY
_print_redirector = _StderrRedirector()


def protect_stdout():
    """Enable stdout protection for MCP mode."""
    sys.stdout = _print_redirector
    os.environ["AKASHIC_MCP_MODE"] = "1"


def restore_stdout():
    """Restore original stdout (for testing)."""
    sys.stdout = _original_stdout
    os.environ.pop("AKASHIC_MCP_MODE", None)


def get_mcp_stdout():
    """Get the original stdout for MCP JSON-RPC communication."""
    return _original_stdout


# =============================================================================
# MCP SERVER
# =============================================================================

# Try to import FastMCP
try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    FastMCP = None


class MCPServer:
    """
    MCP Server wrapper with tool management.

    Provides:
    - Stdout protection (automatic)
    - Tool registration with categories
    - Postal integration hooks
    - Introspection of registered tools
    """

    def __init__(self, name: str = "akashic", version: str = "2.0.0"):
        """
        Initialize MCP server.

        Args:
            name: Server name for MCP protocol
            version: Server version
        """
        self.name = name
        self.version = version
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._categories: Dict[str, List[str]] = {}
        self._mcp: Optional[FastMCP] = None
        self._postal_callback: Optional[Callable] = None

        if HAS_MCP:
            protect_stdout()
            self._mcp = FastMCP(name)
        else:
            print(f"[MCPServer] Warning: MCP not available, running in stub mode")

    @property
    def mcp(self) -> Optional[FastMCP]:
        """Get underlying FastMCP instance."""
        return self._mcp

    def tool(self, category: str = "general"):
        """
        Decorator to register a tool.

        Args:
            category: Tool category for organization

        Usage:
            @server.tool(category="introspection")
            def my_tool(arg: str) -> str:
                '''Tool description.'''
                return "result"
        """
        def decorator(func: Callable) -> Callable:
            # Register with our tracking
            tool_name = func.__name__
            self._tools[tool_name] = {
                "name": tool_name,
                "category": category,
                "doc": func.__doc__ or "",
                "func": func,
            }

            # Add to category index
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(tool_name)

            # Register with FastMCP if available
            if self._mcp:
                return self._mcp.tool()(func)
            return func

        return decorator

    def resource(self, uri: str):
        """
        Decorator to register a resource.

        Args:
            uri: Resource URI (e.g., "akashic://system/status")
        """
        def decorator(func: Callable) -> Callable:
            if self._mcp:
                return self._mcp.resource(uri)(func)
            return func
        return decorator

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools."""
        return [
            {
                "name": info["name"],
                "category": info["category"],
                "description": info["doc"].split("\n")[0] if info["doc"] else "",
            }
            for info in self._tools.values()
        ]

    def list_categories(self) -> Dict[str, List[str]]:
        """List tool categories with their tools."""
        return dict(self._categories)

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Get tool info by name."""
        return self._tools.get(name)

    def set_postal_callback(self, callback: Callable[[str, Dict], None]):
        """
        Set callback for postal integration.

        The callback is called with (tool_name, result) after each tool execution.
        """
        self._postal_callback = callback

    def run(self, transport: str = "stdio"):
        """
        Run the MCP server.

        Args:
            transport: Transport type ("stdio" or "sse")
        """
        if not self._mcp:
            print("[MCPServer] Cannot run - MCP not available")
            return

        self._mcp.run(transport=transport)


def create_mcp_server(name: str = "akashic", version: str = "2.0.0") -> MCPServer:
    """
    Create an MCP server instance.

    Args:
        name: Server name
        version: Server version

    Returns:
        MCPServer instance
    """
    return MCPServer(name=name, version=version)
