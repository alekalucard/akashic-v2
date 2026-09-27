"""
NousFairy Forwarder - Routes imports to the real NousFairy location.

The actual NousFairy lives in waking_minds/nous_fairy.py
This module provides the expected import path and singleton accessor.

Usage:
    from P30_Cognition.cognition.nous_fairy import get_nous_fairy
    nous = get_nous_fairy()
"""

import sys
from pathlib import Path
from typing import Optional

# Ensure waking_minds is importable
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "waking_minds"))

# Import the real implementation
from waking_minds.nous_fairy import NousFairy, ReasoningTrace, ReasoningType, create_nous_fairy

# Re-export for compatibility
__all__ = ["NousFairy", "ReasoningTrace", "ReasoningType", "create_nous_fairy", "get_nous_fairy"]

# Singleton instance
_nous_fairy_instance: Optional[NousFairy] = None


def get_nous_fairy() -> Optional[NousFairy]:
    """
    Get the singleton NousFairy instance.

    Returns the global NousFairy if one has been registered via set_nous_fairy(),
    otherwise returns None (indicating the fairy hasn't been started yet).

    Returns:
        NousFairy instance or None
    """
    global _nous_fairy_instance
    return _nous_fairy_instance


def set_nous_fairy(fairy: NousFairy) -> None:
    """
    Register the global NousFairy instance.

    Called during boot to register the NousFairy for later retrieval.

    Args:
        fairy: The NousFairy instance to register
    """
    global _nous_fairy_instance
    _nous_fairy_instance = fairy
