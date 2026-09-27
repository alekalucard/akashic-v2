"""
Wiring Map - Compatibility layer for akashic_v2

Provides V1 wiring scan interfaces.
"""

from typing import Dict, List, Any


def scan_wiring() -> Dict[str, Any]:
    """Scan the system wiring - stub for v2."""
    return {
        "status": "v2_stub",
        "connections": [],
        "fairies": [],
    }


def get_wiring_map() -> Dict[str, Any]:
    """Get the current wiring map - stub for v2."""
    return {
        "nodes": [],
        "edges": [],
        "status": "v2_stub",
    }
