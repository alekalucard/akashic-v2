"""
P00_Autonomic Re-export Shim
============================

Forwards imports to fairies.P00_Autonomic for backwards compatibility.
This module serves as a compatibility layer between the legacy import path
(P00_Autonomic.xyz) and the new organized location (fairies.P00_Autonomic.xyz).

New code should use: from fairies.P00_Autonomic.xyz import Xyz

Local modules (not forwarded):
- tracer_worker_system: Imported directly to avoid circular imports
- gm_tools: Local GM tools implementation
- fairy_profile: Local fairy profile classes
- akashic_logging: Local logging utilities
- postal_bridge: Local postal bridge client

Forwarded from fairies.P00_Autonomic:
- postal: Unified postal hub interface
- nervous_system: Core nervous system components
- intent_fabric: Intent tracking and forum awareness
- reflex: Brainstem reflex patterns
- utils: Logging and debugging utilities
"""

import warnings

# Suppress verbose import warnings during shim loading
_SHIM_VERBOSE = False

def _shim_warn(msg):
    """Internal warning helper for shim imports."""
    if _SHIM_VERBOSE:
        print(f"[P00_Autonomic shim] {msg}")


# ============================================================================
# LOCAL IMPORTS (not forwarded - these exist in this directory)
# ============================================================================

# tracer_worker_system is imported directly via:
#   from P00_Autonomic.tracer_worker_system import TracerWorkerMixin
# Don't re-export here to avoid circular import issues

# Local fairy_profile - these may have different exports than fairies version
try:
    from .fairy_profile import *
except ImportError as e:
    _shim_warn(f"fairy_profile: {e}")

# Local akashic_logging
try:
    from .akashic_logging import *
except ImportError as e:
    _shim_warn(f"akashic_logging: {e}")


# ============================================================================
# FORWARDED IMPORTS from fairies.P00_Autonomic
# ============================================================================

# Try to import the fairies.P00_Autonomic module itself for wildcard re-export
try:
    from fairies.P00_Autonomic import *
except ImportError as e:
    _shim_warn(f"fairies.P00_Autonomic base: {e}")

# Core postal system - try fairies first, fall back to local
try:
    from fairies.P00_Autonomic.postal import (
        ConnectivityStatus,
        ConnectivityReport,
        UnifiedPostalHub,
        get_postal_hub,
    )
except ImportError:
    # Fall back to local postal.py if fairies version not available
    try:
        from .postal import get_postal_hub
        _shim_warn("Using local postal.py fallback")
    except ImportError as e:
        _shim_warn(f"postal: {e}")

# Nervous system submodules - try fairies first, fall back to local
try:
    from fairies.P00_Autonomic.nervous_system import *
except ImportError:
    try:
        from .nervous_system import *
    except ImportError as e:
        _shim_warn(f"nervous_system: {e}")

# Specific nervous system components with fallbacks
try:
    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import (
        SharedPostalHub,
        get_shared_postal_hub,
    )
except ImportError:
    try:
        from .nervous_system.shared_postal_hub import SharedPostalHub, get_shared_postal_hub
    except ImportError as e:
        _shim_warn(f"shared_postal_hub: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.wiring_map import *
except ImportError:
    try:
        from .nervous_system.wiring_map import *
    except ImportError as e:
        _shim_warn(f"wiring_map: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.cross_plane_wiring import *
except ImportError:
    try:
        from .nervous_system.cross_plane_wiring import *
    except ImportError as e:
        _shim_warn(f"cross_plane_wiring: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.mcp_postal_bridge import *
except ImportError:
    try:
        from .nervous_system.mcp_postal_bridge import *
    except ImportError as e:
        _shim_warn(f"mcp_postal_bridge: {e}")

# Intent fabric
try:
    from fairies.P00_Autonomic.intent_fabric import *
except ImportError as e:
    _shim_warn(f"intent_fabric: {e}")

# Reflex patterns - DISABLED to break circular import
# The reflex module imports brainstem_reflex_fairy which imports Organ_Template
# causing circular import deadlock before MyFairy is defined.
# Use direct import: from fairies.P00_Autonomic.reflex import XYZ
# try:
#     from fairies.P00_Autonomic.reflex import *
# except ImportError as e:
#     _shim_warn(f"reflex: {e}")

# Utility modules
try:
    from fairies.P00_Autonomic.utils import *
except ImportError as e:
    _shim_warn(f"utils: {e}")

# Equilibrium engine
try:
    from fairies.P00_Autonomic.equilibrium_engine import EquilibriumEngine
except ImportError as e:
    _shim_warn(f"equilibrium_engine: {e}")

# Autonomic watchdog
try:
    from fairies.P00_Autonomic.autonomic_watchdog import AutonomicWatchdog
except ImportError as e:
    _shim_warn(f"autonomic_watchdog: {e}")

# Memory packet system
try:
    from fairies.P00_Autonomic.memory_packet_system import *
except ImportError as e:
    _shim_warn(f"memory_packet_system: {e}")

# Temporal packets
try:
    from fairies.P00_Autonomic.temporal_packets import *
except (ImportError, NameError) as e:
    _shim_warn(f"temporal_packets: {e}")

# GM tools (prefer fairies version, fall back to local)
try:
    from fairies.P00_Autonomic.gm_tools import *
except ImportError:
    try:
        from .gm_tools import *
    except ImportError as e:
        _shim_warn(f"gm_tools: {e}")

# GM handler
try:
    from fairies.P00_Autonomic.gm_handler import *
except ImportError as e:
    _shim_warn(f"gm_handler: {e}")

# MCP bootstrap
try:
    from fairies.P00_Autonomic.mcp_bootstrap import *
except ImportError as e:
    _shim_warn(f"mcp_bootstrap: {e}")

# Unified citizen wiring
try:
    from fairies.P00_Autonomic.unified_citizen_wiring import *
except ImportError as e:
    _shim_warn(f"unified_citizen_wiring: {e}")

# Postal bridge subpackage
try:
    from fairies.P00_Autonomic.postal_bridge import *
except ImportError:
    try:
        from .postal_bridge import *
    except ImportError as e:
        _shim_warn(f"postal_bridge: {e}")


# ============================================================================
# __all__ is intentionally not defined - we re-export everything that loads
# successfully. Use dir(P00_Autonomic) to see available exports.
# ============================================================================
