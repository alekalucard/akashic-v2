"""
Hardware Re-export Shim
=======================

Forwards imports to fairies.P00_Autonomic.nervous_system.hardware for backwards compatibility.
New code should use: from fairies.P00_Autonomic.nervous_system.hardware.xyz import Xyz
"""

# Suppress verbose import warnings during shim loading
_SHIM_VERBOSE = False

def _shim_warn(msg):
    """Internal warning helper for shim imports."""
    if _SHIM_VERBOSE:
        print(f"[hardware shim] {msg}")


# ============================================================================
# FORWARDED IMPORTS from fairies.P00_Autonomic.nervous_system.hardware
# ============================================================================

# Try to import everything from fairies version first
try:
    from fairies.P00_Autonomic.nervous_system.hardware import *
except ImportError as e:
    _shim_warn(f"fairies.hardware base: {e}")

# CUDA fairy
try:
    from fairies.P00_Autonomic.nervous_system.hardware.cuda_fairy import *
except ImportError:
    try:
        from .cuda_fairy import *
    except ImportError as e:
        _shim_warn(f"cuda_fairy: {e}")

# Memory pressure fairy
try:
    from fairies.P00_Autonomic.nervous_system.hardware.memory_pressure_fairy import *
except ImportError:
    try:
        from .memory_pressure_fairy import *
    except ImportError as e:
        _shim_warn(f"memory_pressure_fairy: {e}")

# Worker equilibrium
try:
    from fairies.P00_Autonomic.nervous_system.hardware.worker_equilibrium import *
except ImportError:
    try:
        from .worker_equilibrium import *
    except ImportError as e:
        _shim_warn(f"worker_equilibrium: {e}")

# System worker pool fairy
# 2026-05-15 (Nous + Ace): Canonical implementation lives HERE (atoms-of-thought
# substrate engine, used by server.py + interest_generator). The fairies/ duplicate
# was the "need-before-greed" experiment that never landed consumers; deleted.
try:
    from .system_worker_pool_fairy import *
except ImportError as e:
    _shim_warn(f"system_worker_pool_fairy: {e}")

# Hardware regulation fairy
try:
    from fairies.P00_Autonomic.nervous_system.hardware.hardware_regulation_fairy import *
except ImportError as e:
    _shim_warn(f"hardware_regulation_fairy: {e}")

# Worker cell colony
try:
    from fairies.P00_Autonomic.nervous_system.hardware.worker_cell_colony import *
except ImportError as e:
    _shim_warn(f"worker_cell_colony: {e}")
