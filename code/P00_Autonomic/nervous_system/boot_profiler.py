"""
Boot Profiler - Compatibility layer for akashic_v2

Provides V1 boot profiler interfaces.
"""

from typing import Dict, Any


def run_quick_boot_test() -> Dict[str, Any]:
    """Run a quick boot test - stub for v2."""
    return {
        "status": "v2_stub",
        "success": True,
        "duration": 0,
    }


def get_boot_status_from_cartographer() -> Dict[str, Any]:
    """Get boot status - stub for v2."""
    return {
        "status": "v2_stub",
        "booted": True,
        "fairies": [],
    }
