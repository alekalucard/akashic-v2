"""
waking_sequence_fairy.py - Forwarding stub for fairies/ directory

The WakingSequenceFairy lives in P00_Autonomic/nervous_system/.
This module forwards imports for backward compatibility.
"""

import sys
from pathlib import Path

# Ensure project root is in path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Forward all imports to the canonical location
try:
    from fairies.P00_Autonomic.nervous_system.waking_sequence_fairy import (
        WakingSequenceFairy,
        get_waking_sequence_fairy,
        trigger_wake,
    )
except ImportError:
    # Fallback: Try absolute import with full path
    import importlib.util
    _waking_path = _project_root / "P00_Autonomic" / "nervous_system" / "waking_sequence_fairy.py"
    if _waking_path.exists():
        spec = importlib.util.spec_from_file_location("waking_sequence_fairy", _waking_path)
        _waking_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_waking_mod)
        WakingSequenceFairy = _waking_mod.WakingSequenceFairy
        get_waking_sequence_fairy = _waking_mod.get_waking_sequence_fairy
        trigger_wake = _waking_mod.trigger_wake
    else:
        # Final fallback: provide stubs
        print(f"[WakingSequence] WARNING: Could not load from {_waking_path}")
        WakingSequenceFairy = None
        get_waking_sequence_fairy = lambda: None
        trigger_wake = lambda: None

__all__ = ["WakingSequenceFairy", "get_waking_sequence_fairy", "trigger_wake"]
