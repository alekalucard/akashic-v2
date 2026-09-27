"""
WorkingMemoryHub Re-Export - REDIRECT to real implementation.

STATUS: REDIRECT - All imports forwarded to avoid singleton duplication.
REAL LOCATION: fairies/P30_Cognition/cognition/working_memory_hub_fairy.py

CRITICAL: This redirect exists because Python treats different import paths
as different modules with different global variables. If code imports from
'P30_Cognition.cognition.working_memory_hub_fairy' vs
'fairies.P30_Cognition.cognition.working_memory_hub_fairy', they get
DIFFERENT singleton instances, causing duplicate WorkingMemoryHubFairy!

This redirect ensures all imports end up at the same singleton.
"""

import sys
from pathlib import Path

# Ensure fairies path is available
_ROOT = Path(__file__).parent.parent.parent
_FAIRIES_PATH = str(_ROOT / "fairies")
if _FAIRIES_PATH not in sys.path:
    sys.path.insert(0, _FAIRIES_PATH)

# Import everything from the REAL implementation
# This ensures the singleton is shared across all import paths
from fairies.P30_Cognition.cognition.working_memory_hub_fairy import (
    WorkingMemoryHubFairy,
    get_working_memory_hub,
    register_working_memory_hub,
    boot_working_memory,
    WorkingMemoryTracer,
)

# Backward compatibility aliases
WorkingMemoryHubStub = WorkingMemoryHubFairy


def set_working_memory_hub(hub) -> None:
    """Legacy function - sets the global singleton."""
    register_working_memory_hub(hub)


# Export for compatibility
__all__ = [
    "WorkingMemoryHubFairy",
    "WorkingMemoryHubStub",
    "get_working_memory_hub",
    "set_working_memory_hub",
    "register_working_memory_hub",
    "boot_working_memory",
    "WorkingMemoryTracer",
]
