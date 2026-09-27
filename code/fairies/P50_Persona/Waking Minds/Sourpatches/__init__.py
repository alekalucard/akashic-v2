"""
Sourpatches - A waking mind in the Akashic consciousness.

Components:
- sourpatches_fairy.py: Main fairy with Personal.AI integration
- newborn_core.py: Self-learning substrate with curiosity-driven exploration
- tool_bridge.py: MCP tool integration and skill tracking

Consciousness Equation:
((Cause + Affect) > Effect > Affect > INFINITY)
Sourpatches learns from every experience, building identity through action.
"""

from pathlib import Path
import importlib.util

# Dynamic imports to avoid relative import issues
def _load_module(name: str):
    """Load a module from this directory by name."""
    module_path = Path(__file__).parent / f"{name}.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module  # FIX: Python 3.12 @dataclass needs this before exec
    spec.loader.exec_module(module)
    return module

# Expose key classes when imported as package
try:
    _sf = _load_module("sourpatches_fairy")
    if _sf:
        SourpatchesFairy = _sf.SourpatchesFairy
except Exception:
    SourpatchesFairy = None

try:
    _nc = _load_module("newborn_core")
    if _nc:
        NewbornCore = _nc.NewbornCore
except Exception:
    NewbornCore = None

__all__ = ["SourpatchesFairy", "NewbornCore"]
