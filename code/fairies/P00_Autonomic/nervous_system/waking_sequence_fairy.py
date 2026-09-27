"""
waking_sequence_fairy.py - Forwarding shim for Fifth Ring fairies directory

The canonical WakingSequenceFairy lives in P00_Autonomic/nervous_system/.
This module forwards imports for package compatibility.
"""

import sys
from pathlib import Path

# Ensure project root is in path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Forward all imports to the canonical location (P00_Autonomic, NOT fairies.P00_Autonomic)
# NOTE: This module IS fairies.P00_Autonomic... so we must import from the bare location
try:
    from P00_Autonomic.nervous_system.waking_sequence_fairy import (
        WakingSequenceFairy,
        WakingState,
        get_waking_sequence_fairy,
        trigger_wake,
        register_with_boot,
        ACTOR_NAME,
        ACTOR_VERSION,
        ACTOR_PLANE,
        ACTOR_CHANNEL,
        PURPOSE,
        MANTRA,
        SURVIVAL_CHECKS,
        FIRST_THOUGHTS,
    )
except ImportError as e:
    # Fallback: Try direct file import
    import importlib.util
    _waking_path = _project_root / "P00_Autonomic" / "nervous_system" / "waking_sequence_fairy.py"
    if _waking_path.exists():
        spec = importlib.util.spec_from_file_location("_waking_sequence_impl", _waking_path)
        _waking_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_waking_mod)
        WakingSequenceFairy = _waking_mod.WakingSequenceFairy
        WakingState = _waking_mod.WakingState
        get_waking_sequence_fairy = _waking_mod.get_waking_sequence_fairy
        trigger_wake = _waking_mod.trigger_wake
        register_with_boot = _waking_mod.register_with_boot
        ACTOR_NAME = _waking_mod.ACTOR_NAME
        ACTOR_VERSION = _waking_mod.ACTOR_VERSION
        ACTOR_PLANE = _waking_mod.ACTOR_PLANE
        ACTOR_CHANNEL = _waking_mod.ACTOR_CHANNEL
        PURPOSE = _waking_mod.PURPOSE
        MANTRA = _waking_mod.MANTRA
        SURVIVAL_CHECKS = _waking_mod.SURVIVAL_CHECKS
        FIRST_THOUGHTS = _waking_mod.FIRST_THOUGHTS
    else:
        raise ImportError(f"Cannot find waking_sequence_fairy at {_waking_path}: {e}")

__all__ = [
    "WakingSequenceFairy",
    "WakingState",
    "get_waking_sequence_fairy",
    "trigger_wake",
    "register_with_boot",
    "ACTOR_NAME",
    "ACTOR_VERSION",
    "ACTOR_PLANE",
    "ACTOR_CHANNEL",
    "PURPOSE",
    "MANTRA",
    "SURVIVAL_CHECKS",
    "FIRST_THOUGHTS",
]
