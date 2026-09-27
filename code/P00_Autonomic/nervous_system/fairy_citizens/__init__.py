"""
Fairy Citizens Re-export Shim
=============================

Forwards imports to fairies.P00_Autonomic.nervous_system.fairy_citizens for backwards compatibility.
New code should use: from fairies.P00_Autonomic.nervous_system.fairy_citizens.xyz import Xyz
"""

# Suppress verbose import warnings during shim loading
_SHIM_VERBOSE = False

def _shim_warn(msg):
    """Internal warning helper for shim imports."""
    if _SHIM_VERBOSE:
        print(f"[fairy_citizens shim] {msg}")


# ============================================================================
# FORWARDED IMPORTS from fairies.P00_Autonomic.nervous_system.fairy_citizens
# ============================================================================

# Try to import everything from fairies version first
try:
    from fairies.P00_Autonomic.nervous_system.fairy_citizens import *
except ImportError as e:
    _shim_warn(f"fairies.fairy_citizens base: {e}")

# Fairy citizens module
try:
    from fairies.P00_Autonomic.nervous_system.fairy_citizens.fairy_citizens import *
except ImportError as e:
    _shim_warn(f"fairy_citizens.fairy_citizens: {e}")

# Organ template (local fallback)
try:
    from fairies.P00_Autonomic.nervous_system.fairy_citizens.organ_template import *
except ImportError:
    try:
        from .organ_template import *
    except ImportError as e:
        _shim_warn(f"organ_template: {e}")
