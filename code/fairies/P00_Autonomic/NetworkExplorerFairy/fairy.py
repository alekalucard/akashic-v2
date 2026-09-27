"""
NetworkExplorerFairy — Wrapper for the real implementation.

Real code lives at: hardware/network_explorer_fairy.py
This wrapper makes it discoverable by boot CASCADE.
"""
import sys
import importlib.util
from pathlib import Path

_real_path = Path(__file__).resolve().parent.parent.parent.parent / "hardware" / "network_explorer_fairy.py"
_spec = importlib.util.spec_from_file_location(
    "hardware.network_explorer_fairy",
    str(_real_path),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

ACTOR_NAME = "NetworkExplorerFairy"
FAIRY_CLASS = _mod.NetworkExplorerFairy
