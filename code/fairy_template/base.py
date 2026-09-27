"""
Fairy Base - BACKWARD COMPATIBILITY ONLY

FIFTH RING PRINCIPLE: NO MIXINS
===============================
This file exists ONLY for backward compatibility.

The actual utilities are in:
- P00_Autonomic.nervous_system.shared_postal_hub (system utilities)
- P10_Memory.Akashic_Records_Physical.Organ_Templates (fairy class)

New code should import directly from those locations.
"""

import os
import sys
import glob
import importlib.util
import importlib.machinery
from pathlib import Path

# Add paths for imports
ROOT = Path(__file__).parent.parent
_paths = [
    str(ROOT / "fairies"),
    str(ROOT / "tracer_pool"),
    str(ROOT / "postal_core" / "python"),
    str(ROOT),
]
for _p in _paths:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ═══ BACKWARD COMPATIBILITY REDIRECTS ═══
# System utilities - redirect to nervous system
from P00_Autonomic.nervous_system.shared_postal_hub import (
    set_shared_fabric,
    get_shared_fabric,
    signal_global_shutdown,
    is_global_shutdown,
    reset_global_shutdown,
)

# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE WIRING - Dynamic import from "Organ_Templates" folder
# ══════════════════════════════════════════════════════════════════════════════
TEMPLATE_VERSION = "0.1.2"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"

def _find_template_path():
    """Find the organ template dynamically."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates")
        if os.path.isdir(ar):
            exact = os.path.join(ar, TEMPLATE_BASENAME)
            if os.path.isfile(exact):
                return exact
            candidates = sorted(glob.glob(os.path.join(ar, "Organ_Template_*.py")),
                              key=lambda p: os.path.getmtime(p))
            return candidates[-1] if candidates else None
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None

def _import_template():
    """Import template module."""
    path = _find_template_path()
    if not path:
        raise ImportError("Cannot find Organ_Template_*.py in Organ_Templates folder")
    mod_name = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(mod_name, importlib.machinery.SourceFileLoader(mod_name, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

_template = _import_template()

# Fairy class - redirect to Organ Template
Fairy = _template.MyFairy
FairyBase = _template.MyFairy
