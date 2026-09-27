"""
Nervous System Re-export Shim
=============================

Forwards imports to fairies.P00_Autonomic.nervous_system for backwards compatibility.
New code should use: from fairies.P00_Autonomic.nervous_system.xyz import Xyz

This compatibility layer tries fairies versions first, then falls back to local modules.
"""

# Suppress verbose import warnings during shim loading
_SHIM_VERBOSE = False

def _shim_warn(msg):
    """Internal warning helper for shim imports."""
    if _SHIM_VERBOSE:
        print(f"[nervous_system shim] {msg}")


# ============================================================================
# FORWARDED IMPORTS from fairies.P00_Autonomic.nervous_system
# ============================================================================

# Try to import everything from fairies version first
try:
    from fairies.P00_Autonomic.nervous_system import *
except ImportError as e:
    _shim_warn(f"fairies.nervous_system base: {e}")

# Shared postal hub - critical component
try:
    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import (
        SharedPostalHub,
        get_shared_postal_hub,
    )
except ImportError:
    try:
        from .shared_postal_hub import SharedPostalHub, get_shared_postal_hub
    except ImportError as e:
        _shim_warn(f"shared_postal_hub: {e}")

# Wiring map
try:
    from fairies.P00_Autonomic.nervous_system.wiring_map import *
except ImportError:
    try:
        from .wiring_map import *
    except ImportError as e:
        _shim_warn(f"wiring_map: {e}")

# Cross-plane wiring
try:
    from fairies.P00_Autonomic.nervous_system.cross_plane_wiring import *
except ImportError:
    try:
        from .cross_plane_wiring import *
    except ImportError as e:
        _shim_warn(f"cross_plane_wiring: {e}")

# MCP postal bridge
try:
    from fairies.P00_Autonomic.nervous_system.mcp_postal_bridge import *
except ImportError:
    try:
        from .mcp_postal_bridge import *
    except ImportError as e:
        _shim_warn(f"mcp_postal_bridge: {e}")

# Boot profiler
try:
    from fairies.P00_Autonomic.nervous_system.boot_profiler import *
except ImportError:
    try:
        from .boot_profiler import *
    except ImportError as e:
        _shim_warn(f"boot_profiler: {e}")

# Resource pools
try:
    from fairies.P00_Autonomic.nervous_system.resource_pools import *
except ImportError:
    try:
        from .resource_pools import *
    except ImportError as e:
        _shim_warn(f"resource_pools: {e}")

# Postal hub
try:
    from fairies.P00_Autonomic.nervous_system.postal_hub import *
except ImportError:
    try:
        from .postal_hub import *
    except ImportError as e:
        _shim_warn(f"postal_hub: {e}")


# ============================================================================
# LOCAL IMPORTS (fallbacks for modules that exist locally)
# ============================================================================

# Waking sequence fairy - CANONICAL LOCATION IS HERE (P00_Autonomic), so try local first!
# This prevents circular import chains when fairies/ tries to import back here.
try:
    from .waking_sequence_fairy import (
        WakingSequenceFairy,
        get_waking_sequence_fairy,
        trigger_wake,
    )
except ImportError as e:
    _shim_warn(f"waking_sequence_fairy (local): {e}")

# Consciousness loop fairy - LAZY IMPORT to break circular dependency
# The Organ Template imports shared_postal_hub, which imports this __init__.py,
# which was trying to import ConsciousnessLoopFairy before MyFairy was defined.
_ConsciousnessLoopFairy = None
_consciousness_loop_funcs = None

def _load_consciousness_loop():
    """Lazy load ConsciousnessLoopFairy to break circular import."""
    global _ConsciousnessLoopFairy, _consciousness_loop_funcs
    if _ConsciousnessLoopFairy is None:
        try:
            from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import (
                ConsciousnessLoopFairy as _CLF,
                get_consciousness_loop as _gcl,
                set_consciousness_loop as _scl,
            )
            _ConsciousnessLoopFairy = _CLF
            _consciousness_loop_funcs = (_gcl, _scl)
        except ImportError as e:
            _shim_warn(f"ConsciousnessLoopFairy: {e}")
    return _ConsciousnessLoopFairy

def get_consciousness_loop():
    """Get the consciousness loop (lazy loaded)."""
    _load_consciousness_loop()
    if _consciousness_loop_funcs:
        return _consciousness_loop_funcs[0]()
    return None

def set_consciousness_loop(loop):
    """Set the consciousness loop (lazy loaded)."""
    _load_consciousness_loop()
    if _consciousness_loop_funcs:
        return _consciousness_loop_funcs[1](loop)


# ============================================================================
# HARDWARE SUBPACKAGE
# ============================================================================

# Import hardware submodule components
try:
    from fairies.P00_Autonomic.nervous_system.hardware import *
except ImportError:
    try:
        from .hardware import *
    except ImportError as e:
        _shim_warn(f"hardware: {e}")


# ============================================================================
# FAIRY CITIZENS SUBPACKAGE
# ============================================================================

try:
    from fairies.P00_Autonomic.nervous_system.fairy_citizens import *
except ImportError:
    try:
        from .fairy_citizens import *
    except ImportError as e:
        _shim_warn(f"fairy_citizens: {e}")


# ============================================================================
# Additional fairies nervous system modules
# ============================================================================

try:
    from fairies.P00_Autonomic.nervous_system.unified_postal import *
except ImportError as e:
    _shim_warn(f"unified_postal: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.iodine_tracer import *
except ImportError as e:
    _shim_warn(f"iodine_tracer: {e}")

# salience_filter - DISABLED to break circular import
# Chain: salience_filter -> aer_metrics -> emotional_algebra -> P20_Somatic -> SomaticMindFairy -> Organ_Template
# Use direct import if needed: from fairies.P00_Autonomic.nervous_system.salience_filter import XYZ
# try:
#     from fairies.P00_Autonomic.nervous_system.salience_filter import *
# except ImportError as e:
#     _shim_warn(f"salience_filter: {e}")

# graceful_shutdown_fairy - DISABLED to break circular import
# Chain: graceful_shutdown -> dream_seed -> working_memory_hub -> temporal_stratification -> P20_Somatic -> Organ_Template
# try:
#     from fairies.P00_Autonomic.nervous_system.graceful_shutdown_fairy import *
# except ImportError as e:
#     _shim_warn(f"graceful_shutdown_fairy: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.process_hygiene import *
except ImportError as e:
    _shim_warn(f"process_hygiene: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.collision_chamber import *
except ImportError as e:
    _shim_warn(f"collision_chamber: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.boot_observer import *
except ImportError as e:
    _shim_warn(f"boot_observer: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.dynamic_fairy_scanner import *
except ImportError as e:
    _shim_warn(f"dynamic_fairy_scanner: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.fairy_census import *
except ImportError as e:
    _shim_warn(f"fairy_census: {e}")

try:
    from fairies.P00_Autonomic.nervous_system.fairy_corporate_directory import *
except ImportError as e:
    _shim_warn(f"fairy_corporate_directory: {e}")


# ============================================================================
# __all__ is intentionally not defined - we re-export everything that loads
# successfully. Use dir(P00_Autonomic.nervous_system) to see available exports.
# ============================================================================
