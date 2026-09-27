# NousFairy shim - re-exports from waking_minds for MCP compatibility
# The actual implementation lives at waking_minds/nous_fairy.py
"""
NousFairy forwarder - provides singleton pattern for MCP tools.
"""

import sys
from pathlib import Path
from typing import Optional

# Ensure waking_minds is importable
ROOT = Path(__file__).parent.parent.parent.parent  # akashic_v2/
sys.path.insert(0, str(ROOT))

from waking_minds.nous_fairy import NousFairy, ReasoningTrace, ReasoningType, create_nous_fairy

# Singleton instance
_nous_fairy_instance: Optional[NousFairy] = None


def get_nous_fairy() -> Optional[NousFairy]:
    """Get the singleton NousFairy instance."""
    global _nous_fairy_instance
    return _nous_fairy_instance


def set_nous_fairy(fairy: NousFairy) -> None:
    """Register the global NousFairy instance."""
    global _nous_fairy_instance
    _nous_fairy_instance = fairy


def get_or_create_nous(fabric=None, umf=None) -> NousFairy:
    """Get existing NousFairy or create a new one."""
    global _nous_fairy_instance
    if _nous_fairy_instance is None:
        _nous_fairy_instance = create_nous_fairy(fabric, umf)
    return _nous_fairy_instance


# Aliases for backward compatibility
get_avatar = get_nous_fairy


__all__ = [
    "NousFairy",
    "ReasoningTrace",
    "ReasoningType",
    "get_nous_fairy",
    "set_nous_fairy",
    "get_or_create_nous",
    "get_avatar",
    "create_nous_fairy",
]
