# P30_Cognition compatibility layer for akashic_v2
"""
Re-export shim: forwards imports to fairies.P30_Cognition.

This module provides backward compatibility for code that imports from
P30_Cognition directly. The canonical location is fairies.P30_Cognition.

Local submodules (cognition, integration, data) are also available.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# RE-EXPORT FROM fairies.P30_Cognition
# ═══════════════════════════════════════════════════════════════════════════════

# Import all public symbols from the canonical location
try:
    from fairies.P30_Cognition import *
    from fairies.P30_Cognition import (
        __all__ as _fairy_all,
        COGNITION_COMPONENTS,
        get_available_components,
        get_missing_components,
    )
    # Availability flags
    from fairies.P30_Cognition import (
        HAS_QUANTUM_EMULATOR,
        HAS_QUANTUM_INTERFERENCE,
        HAS_ORACLE,
        HAS_ATTENTION,
        HAS_CORTEX,
        HAS_PAIN_DRIVES,
    )
    _HAS_FAIRY_MODULE = True
except ImportError as e:
    _fairy_all = []
    COGNITION_COMPONENTS = {}
    _HAS_FAIRY_MODULE = False
    print(f"[P30_Cognition shim] fairies.P30_Cognition not available: {e}")

    # Provide stub availability flags
    HAS_QUANTUM_EMULATOR = False
    HAS_QUANTUM_INTERFERENCE = False
    HAS_ORACLE = False
    HAS_ATTENTION = False
    HAS_CORTEX = False
    HAS_PAIN_DRIVES = False

    def get_available_components():
        return {}

    def get_missing_components():
        return {"all": True}

# ═══════════════════════════════════════════════════════════════════════════════
# SUBMODULE FORWARDING (Portal Pattern)
# ═══════════════════════════════════════════════════════════════════════════════

# Forward cognition and integration to fairies.P30_Cognition (canonical source)
try:
    from fairies.P30_Cognition import cognition
except ImportError:
    from . import cognition  # Fallback to local

try:
    from fairies.P30_Cognition import integration
except ImportError:
    from . import integration  # Fallback to local

# data stays local - contains actual data files (concept_graph.json, etc.)
from . import data

# ═══════════════════════════════════════════════════════════════════════════════
# BUILD __all__
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = list(_fairy_all) + [
    # Submodules (forwarded from fairies.P30_Cognition where available)
    "cognition",
    "integration",
    "data",  # Local - contains data files
    # Module-level helpers
    "COGNITION_COMPONENTS",
    "get_available_components",
    "get_missing_components",
    # Availability flags
    "HAS_QUANTUM_EMULATOR",
    "HAS_QUANTUM_INTERFERENCE",
    "HAS_ORACLE",
    "HAS_ATTENTION",
    "HAS_CORTEX",
    "HAS_PAIN_DRIVES",
]
