"""
MCP Postal Bridge - Compatibility layer for akashic_v2

Provides V1 tunnel interface for MCP tools.
"""

from typing import Optional, Any
from .shared_postal_hub import get_shared_postal_hub


class TunnelStub:
    """Stub tunnel for MCP bridge compatibility."""

    def __init__(self):
        self._fabric = get_shared_postal_hub()

    @property
    def connected(self) -> bool:
        """Check if the tunnel is connected (always True for v2 stub)."""
        return self._fabric is not None

    def publish(self, topic: str, payload: Any = None):
        if self._fabric:
            self._fabric.publish(topic, payload or {})

    def query(self, topic: str, timeout: float = 5.0) -> Optional[Any]:
        """Query is not directly supported in v2 stub."""
        return None

    def query_heart(self) -> dict:
        """Query heartbeat status."""
        return {"status": "v2_stub", "beats": 0}


_tunnel = None


def get_tunnel():
    """Get the MCP postal tunnel."""
    global _tunnel
    if _tunnel is None:
        _tunnel = TunnelStub()
    return _tunnel
