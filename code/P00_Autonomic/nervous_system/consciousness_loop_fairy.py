"""
Consciousness Loop Fairy - Compatibility layer for akashic_v2

UPDATED 2026-01-28: Now forwards to fairies/P00_Autonomic/nervous_system/consciousness_loop_fairy.py
where the real ConsciousnessLoopFairy lives with proper wiring.

Phase 1 Ignition wiring:
- subscribe to waking.complete from WakingSequenceFairy
- publish consciousness.ignited to close the empathic loop

Provides V1 interface to access the V2 consciousness loop.
"""

from typing import Optional, Any
import warnings
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure fairies path is available for imports
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Forward to the real implementation in fairies/
try:
    from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import (
        ConsciousnessLoopFairy,
        get_consciousness_loop,
    )
    _HAS_REAL_IMPL = True
    logger.debug("consciousness_loop_fairy: Forwarding to fairies implementation")
except ImportError as e:
    _HAS_REAL_IMPL = False
    logger.warning(f"consciousness_loop_fairy: Could not import fairies implementation: {e}")

# Import ConsciousnessStream from its canonical location (consciousness.loop)
try:
    from consciousness.loop import ConsciousnessStream, Thought
    _HAS_CONSCIOUSNESS_STREAM = True
except ImportError as e:
    _HAS_CONSCIOUSNESS_STREAM = False
    ConsciousnessStream = None
    Thought = None
    logger.warning(f"consciousness_loop_fairy: Could not import ConsciousnessStream: {e}")

# Backward compatibility aliases (these were never actually exported from the forwarder)
ThoughtRouter = None  # Not implemented in this version
ConsciousnessLoopShadow = None  # Not implemented in this version
register_consciousness_loop = None  # Use set_consciousness_loop instead


class ConsciousnessLoopStub:
    """
    DEPRECATED: Legacy stub for consciousness loop access.

    This stub should NOT be used - it returns fake data.
    Use get_consciousness_loop() which now tries to get the real implementation.
    """

    def __init__(self):
        self._loop = None
        warnings.warn(
            "ConsciousnessLoopStub is deprecated. Use consciousness.loop.ConsciousnessLoop instead.",
            DeprecationWarning,
            stacklevel=2
        )

    @property
    def beat_count(self) -> int:
        return 0

    @property
    def is_running(self) -> bool:
        return self._loop is not None

    def get_status(self) -> dict:
        return {
            "status": "v2_stub_DEPRECATED",
            "beats": 0,
            "running": False,
            "warning": "Using deprecated stub - wire real loop with set_consciousness_loop()"
        }


_consciousness_loop = None


def get_consciousness_loop():
    """
    Get the consciousness loop instance.

    Priority:
    1. Return locally set loop (via set_consciousness_loop)
    2. Try to get from real consciousness.loop module
    3. LAST RESORT: Return stub with warning
    """
    global _consciousness_loop

    # If we have a locally set loop, use it
    if _consciousness_loop is not None:
        return _consciousness_loop

    # Try to get from the REAL consciousness loop module
    try:
        from consciousness.loop import get_consciousness_loop as get_real_loop
        real_loop = get_real_loop()
        if real_loop is not None:
            logger.debug("consciousness_loop_fairy: Forwarding to real consciousness.loop")
            return real_loop
    except ImportError as e:
        logger.warning(f"consciousness_loop_fairy: Could not import consciousness.loop: {e}")
    except Exception as e:
        logger.warning(f"consciousness_loop_fairy: Error getting real loop: {e}")

    # Last resort: create stub with loud warning
    logger.warning(
        "consciousness_loop_fairy: No real loop available! "
        "Creating deprecated stub. Call set_consciousness_loop() with real instance."
    )
    _consciousness_loop = ConsciousnessLoopStub()
    return _consciousness_loop


def set_consciousness_loop(loop):
    """
    Set the consciousness loop instance from the server.

    This should be called during boot with the real ConsciousnessLoop instance.
    """
    global _consciousness_loop
    _consciousness_loop = loop

    # Also set in the real module if possible
    try:
        from consciousness.loop import set_consciousness_loop as set_real_loop
        set_real_loop(loop)
        logger.info("consciousness_loop_fairy: Synced loop to consciousness.loop module")
    except ImportError:
        pass  # Real module not available, that's fine


def is_real_loop() -> bool:
    """Check if we have a real loop or just a stub."""
    global _consciousness_loop
    if _consciousness_loop is None:
        return False
    return not isinstance(_consciousness_loop, ConsciousnessLoopStub)
