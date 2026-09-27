"""
CircadianRhythmFairy — Wrapper for CircadianPacemakerFairy.

The real implementation lives at:
  fairies/P00_Autonomic/circulation/circadian_pacemaker_fairy.py

This wrapper makes it discoverable by the boot CASCADE system
which expects fairies/{Plane}/{FairyName}/fairy.py structure.
"""
import sys
import importlib.util
from pathlib import Path

# Load the real module
_real_path = Path(__file__).parent.parent / "circulation" / "circadian_pacemaker_fairy.py"
_spec = importlib.util.spec_from_file_location(
    "fairies.P00_Autonomic.circulation.circadian_pacemaker_fairy",
    str(_real_path),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod  # Register BEFORE exec for @dataclass
_spec.loader.exec_module(_mod)

# Re-export for boot discovery
CircadianPacemakerFairy = _mod.CircadianPacemakerFairy

# Boot system looks for ACTOR_NAME and FAIRY_CLASS
ACTOR_NAME = "CircadianRhythmFairy"
FAIRY_CLASS = CircadianPacemakerFairy
