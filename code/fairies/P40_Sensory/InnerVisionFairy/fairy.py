"""
InnerVisionFairy — Wrapper for TelemetryVisionFairy.

Real code lives at: fairies/P40_Sensory/telemetry_vision/telemetry_vision_fairy.py
This wrapper makes it discoverable by boot CASCADE as "InnerVisionFairy".
"""
import sys
import importlib.util
from pathlib import Path

_real_path = Path(__file__).parent.parent / "telemetry_vision" / "telemetry_vision_fairy.py"
_spec = importlib.util.spec_from_file_location(
    "fairies.P40_Sensory.telemetry_vision.telemetry_vision_fairy",
    str(_real_path),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

ACTOR_NAME = "InnerVisionFairy"
FAIRY_CLASS = _mod.TelemetryVisionFairy
