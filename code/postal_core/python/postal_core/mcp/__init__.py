"""
MCP Integration for Postal Core.

Provides Model Context Protocol (MCP) server that:
1. Exposes tools for LLM introspection and system control
2. Bridges external Claude connections to the postal system
3. Maintains stdout isolation (MCP uses stdout for JSON-RPC)

Usage:
    from postal_core.mcp import create_mcp_server, MCPBridgeFairy

    # Create server with tools
    mcp = create_mcp_server()

    # Or use the fairy for full postal integration
    bridge = MCPBridgeFairy(fabric)
    bridge.boot()
"""

from .server import create_mcp_server, MCPServer
from .bridge import MCPBridgeFairy

__all__ = [
    "create_mcp_server",
    "MCPServer",
    "MCPBridgeFairy",
]
