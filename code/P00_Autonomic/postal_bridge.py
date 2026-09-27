"""
postal_bridge.py - Stub for akashic_v2

Provides bridge client stub for MCP tools.
In akashic_v2, use P00_Autonomic.nervous_system.shared_postal_hub instead.
"""

from typing import Optional


class BridgeClient:
    """Stub bridge client."""

    def __init__(self):
        self.connected = False

    def connect(self) -> bool:
        """Connect to bridge (stub)."""
        return False

    def route(self, topic: str, payload: dict):
        """Route message (stub)."""
        pass

    def query(self, topic: str, timeout: float = 5.0):
        """Query (stub)."""
        return None


_client: Optional[BridgeClient] = None


def get_bridge_client() -> BridgeClient:
    """Get bridge client singleton."""
    global _client
    if _client is None:
        _client = BridgeClient()
    return _client


__all__ = ["BridgeClient", "get_bridge_client"]
