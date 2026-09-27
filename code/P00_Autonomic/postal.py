"""
postal.py - Stub for akashic_v2

Forward to shared_postal_hub for compatibility.
"""

from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub


def get_postal_hub():
    """Get postal hub - forwards to shared_postal_hub."""
    return get_shared_postal_hub()


__all__ = ["get_postal_hub"]
