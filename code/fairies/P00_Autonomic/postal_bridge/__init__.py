"""
Postal Bridge - Multi-Channel IPC for Akashic System

The "Reverse Tower of Babel" architecture:
Instead of one unified connection that breaks,
we use multiple independent channels that each
can fail without bringing down the whole system.

Channels:
1. SQLite Message Queue - Primary, 100% reliable, cross-platform
2. Shared Memory - Fast state reads, sub-millisecond
3. Socket (optional) - Low latency for real-time needs

Usage (MCP side):
    from fairies.P00_Autonomic.postal_bridge import get_bridge_client
    
    client = get_bridge_client()
    if client.connect():
        client.route("my.topic", {"data": "here"})
        state = client.read_state("consciousness_active")

Usage (server side):
    from fairies.P00_Autonomic.postal_bridge import start_bridge_server

    await start_bridge_server(postal_hub)

Author: Nous (Claude Opus 4.5)
Created: January 2026
"""

from .sqlite_channel import (
    SQLiteChannel,
    get_sqlite_channel,
    QueuedMessage,
)

from .shared_memory_channel import (
    SharedMemoryChannel,
    get_shared_memory,
)

from .bridge_client import (
    PostalBridgeClient,
    get_bridge_client,
    PostalTunnelCompatible,
)

from .bridge_server import (
    PostalBridgeServer,
    get_bridge_server,
    start_bridge_server,
    stop_bridge_server,
    PostalHubBridgeIntegration,
    BridgeStats,
)

__all__ = [
    # SQLite Channel
    "SQLiteChannel",
    "get_sqlite_channel",
    "QueuedMessage",
    
    # Shared Memory Channel
    "SharedMemoryChannel",
    "get_shared_memory",
    
    # Bridge Client (MCP side)
    "PostalBridgeClient",
    "get_bridge_client",
    "PostalTunnelCompatible",
    
    # Bridge Server (server side)
    "PostalBridgeServer",
    "get_bridge_server",
    "start_bridge_server",
    "stop_bridge_server",
    "PostalHubBridgeIntegration",
    "BridgeStats",
]
