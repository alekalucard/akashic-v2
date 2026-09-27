"""
battery_accel.py -- Python wrapper for fused C/AVX2 kernels

On import:
  1. Checks if battery_matvec_fused.dll exists and is newer than .c source
  2. If stale/missing, attempts JIT compile via GCC (MinGW-W64)
  3. Loads DLL via ctypes, verifies version
  4. Sets ACCEL_AVAILABLE = True on success, False on any failure

Kernels:
  - quantized_matvec:       INT8 dequant + matvec + activation
  - state_evolution:        RWKV-7 state recurrence (all heads)
  - layernorm:              Fused LayerNorm with scale+bias
  - groupnorm:              Fused GroupNorm with scale+bias

Activation codes: 0=none, 1=sigmoid, 2=relu_sq, 3=tanh
"""

import os
import sys
import ctypes
import subprocess
import numpy as np
from pathlib import Path

def _log(msg: str):
    """Log to stderr — stdout is reserved for portal JSON protocol."""
    print(msg, file=sys.stderr, flush=True)

# ---- Paths ----
_DIR = Path(__file__).parent
_C_SRC = _DIR / "battery_matvec_fused.c"
_DLL   = _DIR / "battery_matvec_fused.dll"

# MinGW GCC path (WinGet install)
_GCC_PATHS = [
    # WinGet MinGW-W64
    Path(os.environ.get("LOCALAPPDATA", "")) /
        "Microsoft" / "WinGet" / "Packages" /
        "BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe" /
        "mingw64" / "bin" / "gcc.exe",
    # Common manual installs
    Path("C:/mingw64/bin/gcc.exe"),
    Path("C:/msys64/mingw64/bin/gcc.exe"),
]

# ---- Compile flags ----
_CFLAGS = [
    "-O3",
    "-march=skylake",
    "-mavx2",
    "-mfma",
    "-fopenmp",
    "-shared",
]

# ---- State ----
ACCEL_AVAILABLE = False
_lib = None


def _find_gcc():
    """Find a working GCC compiler."""
    for p in _GCC_PATHS:
        if p.exists():
            return str(p)
    # Try PATH
    import shutil
    gcc = shutil.which("gcc")
    if gcc:
        return gcc
    return None


def _needs_compile():
    """Check if DLL is missing or stale."""
    if not _DLL.exists():
        return True
    if not _C_SRC.exists():
        return False  # no source to compile from, use existing DLL
    return _C_SRC.stat().st_mtime > _DLL.stat().st_mtime


def _compile():
    """JIT compile the C kernel to DLL."""
    gcc = _find_gcc()
    if not gcc:
        _log("[battery_accel] No GCC found -- C acceleration unavailable")
        return False

    cmd = [gcc] + _CFLAGS + ["-o", str(_DLL), str(_C_SRC)]
    _log(f"[battery_accel] Compiling: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_DIR),
        )
        if result.returncode != 0:
            _log(f"[battery_accel] Compile FAILED (rc={result.returncode}):")
            if result.stderr:
                _log(result.stderr[:500])
            return False
        _log(f"[battery_accel] Compiled OK -> {_DLL.name}")
        return True

    except subprocess.TimeoutExpired:
        _log("[battery_accel] Compile timed out after 60s")
        return False
    except Exception as e:
        _log(f"[battery_accel] Compile error: {e}")
        return False


def _add_mingw_dll_dirs():
    """Add MinGW bin directory to DLL search path for OpenMP runtime (libgomp-1.dll)."""
    for gcc_path in _GCC_PATHS:
        mingw_bin = gcc_path.parent  # .../mingw64/bin/
        if mingw_bin.exists():
            try:
                os.add_dll_directory(str(mingw_bin))
                return True
            except Exception:
                pass
    return False


def _load_lib():
    """Load the DLL and set up function signatures."""
    global _lib

    # Add MinGW bin to DLL search path (needed for OpenMP runtime libgomp-1.dll)
    _add_mingw_dll_dirs()

    try:
        _lib = ctypes.CDLL(str(_DLL))
    except OSError as e:
        _log(f"[battery_accel] Failed to load DLL: {e}")
        return False

    # Verify version (accept v2 or v3)
    try:
        _lib.battery_accel_version.restype = ctypes.c_int
        ver = _lib.battery_accel_version()
        if ver < 2:
            _log(f"[battery_accel] Version too old: got {ver}, need >= 2")
            return False
    except Exception as e:
        _log(f"[battery_accel] Version check failed: {e}")
        return False

    # Set up quantized_matvec_fused signature
    _lib.quantized_matvec_fused.restype = None
    _lib.quantized_matvec_fused.argtypes = [
        ctypes.c_void_p,    # data (int8*)
        ctypes.c_void_p,    # scales (float*)
        ctypes.c_void_p,    # x (float*)
        ctypes.c_void_p,    # y (float*)
        ctypes.c_int,       # M
        ctypes.c_int,       # K
        ctypes.c_int,       # K_padded
        ctypes.c_int,       # n_groups
        ctypes.c_int,       # group_size
        ctypes.c_int,       # activation
    ]

    # Set up state_evolution_fused signature
    _lib.state_evolution_fused.restype = None
    _lib.state_evolution_fused.argtypes = [
        ctypes.c_void_p,    # state (float*, in-place)
        ctypes.c_void_p,    # wt (float*)
        ctypes.c_void_p,    # kkt (float*)
        ctypes.c_void_p,    # at (float*)
        ctypes.c_void_p,    # vt (float*)
        ctypes.c_void_p,    # kt (float*)
        ctypes.c_void_p,    # rt (float*)
        ctypes.c_void_p,    # output (float*)
        ctypes.c_int,       # H
        ctypes.c_int,       # N
    ]

    # Set up layernorm_fused signature
    _lib.layernorm_fused.restype = None
    _lib.layernorm_fused.argtypes = [
        ctypes.c_void_p,    # x (float*)
        ctypes.c_void_p,    # weight (float*)
        ctypes.c_void_p,    # bias (float*)
        ctypes.c_void_p,    # y (float*)
        ctypes.c_int,       # C
        ctypes.c_float,     # eps
    ]

    # Set up groupnorm_fused signature
    _lib.groupnorm_fused.restype = None
    _lib.groupnorm_fused.argtypes = [
        ctypes.c_void_p,    # x (float*)
        ctypes.c_void_p,    # weight (float*)
        ctypes.c_void_p,    # bias (float*)
        ctypes.c_void_p,    # y (float*)
        ctypes.c_int,       # C
        ctypes.c_int,       # num_groups
        ctypes.c_float,     # eps
    ]

    # Set up thread control signatures (v3+, OpenMP)
    _omp_available = False
    try:
        _lib.battery_set_threads.restype = None
        _lib.battery_set_threads.argtypes = [ctypes.c_int]
        _lib.battery_get_threads.restype = ctypes.c_int
        _lib.battery_get_num_procs.restype = ctypes.c_int
        _omp_available = True
        n_procs = _lib.battery_get_num_procs()
        n_threads = _lib.battery_get_threads()
        _log(f"[battery_accel] OpenMP: {n_procs} procs, {n_threads} threads")
    except Exception:
        _log(f"[battery_accel] OpenMP thread control not available (v2 DLL?)")

    _log(f"[battery_accel] Loaded OK -- AVX2 fused kernels active (v{ver})"
         f"{' + OpenMP' if _omp_available else ''}")
    return True


# ---- Public API ----

def quantized_matvec(qt, x, activation=0):
    """
    Fused dequant + matvec + activation using C/AVX2 kernel.

    Args:
        qt: QuantizedTensor with .data (int8), .scales (float32), .shape, .group_size
        x:  Input vector, float32, shape [K] or [K_padded]
        activation: 0=none, 1=sigmoid, 2=relu_sq, 3=tanh

    Returns:
        y: Output vector, float32, shape [M]
    """
    if _lib is None:
        raise RuntimeError("C kernel not loaded -- check ACCEL_AVAILABLE first")

    M, K = qt.shape
    K_padded = qt.data.shape[1]
    n_groups = qt.scales.shape[1]
    group_size = qt.group_size

    # Ensure x is contiguous float32
    x = np.ascontiguousarray(x.ravel(), dtype=np.float32)

    # Pad x to K_padded if needed
    if x.shape[0] < K_padded:
        x_padded = np.zeros(K_padded, dtype=np.float32)
        x_padded[:x.shape[0]] = x
        x = x_padded

    # Ensure data and scales are contiguous
    data = np.ascontiguousarray(qt.data)
    scales = np.ascontiguousarray(qt.scales)

    # Allocate output
    y = np.empty(M, dtype=np.float32)

    # Call C kernel
    _lib.quantized_matvec_fused(
        data.ctypes.data,
        scales.ctypes.data,
        x.ctypes.data,
        y.ctypes.data,
        M, K, K_padded, n_groups, group_size,
        activation,
    )

    return y


def state_evolution(state, wt, kkt, at, vt, kt, rt):
    """
    Fused RWKV-7 state evolution for all heads using C/AVX2 kernel.

    Modifies state IN-PLACE and returns the readout output.

    Args:
        state: [H, N, N] float32, modified in-place
        wt:    [H, N] or [H, 1, N] float32 -- decay weights
        kkt:   [H, N] or [H, N, 1] float32 -- normalized key
        at:    [H, N] or [H, N, 1] float32 -- association coeff
        vt:    [H, N] or [H, N, 1] float32 -- value
        kt:    [H, N] or [H, 1, N] float32 -- key (transposed)
        rt:    [H, N] or [H, N, 1] float32 -- receptance

    Returns:
        output: [H*N] float32 readout vector
    """
    if _lib is None:
        raise RuntimeError("C kernel not loaded -- check ACCEL_AVAILABLE first")

    H = state.shape[0]
    N = state.shape[1]  # state is [H, N, N]

    # Ensure state is contiguous float32 C-order [H, N, N]
    if not state.flags['C_CONTIGUOUS']:
        raise ValueError("state must be C-contiguous [H,N,N] for in-place update")
    state = np.ascontiguousarray(state, dtype=np.float32)

    # Squeeze all vectors from [H,1,N] or [H,N,1] to flat [H,N], contiguous
    def _flat(arr):
        return np.ascontiguousarray(arr.reshape(H, N), dtype=np.float32)

    wt_f  = _flat(wt)
    kkt_f = _flat(kkt)
    at_f  = _flat(at)
    vt_f  = _flat(vt)
    kt_f  = _flat(kt)
    rt_f  = _flat(rt)

    # Allocate output
    output = np.empty(H * N, dtype=np.float32)

    _lib.state_evolution_fused(
        state.ctypes.data,
        wt_f.ctypes.data,
        kkt_f.ctypes.data,
        at_f.ctypes.data,
        vt_f.ctypes.data,
        kt_f.ctypes.data,
        rt_f.ctypes.data,
        output.ctypes.data,
        H, N,
    )

    return output


def layernorm(x, weight, bias, eps=1e-5):
    """
    Fused LayerNorm using C/AVX2 kernel.

    Args:
        x:      [C] float32 input
        weight: [C] float32 scale
        bias:   [C] float32 shift
        eps:    float, default 1e-5

    Returns:
        y: [C] float32 normalized output
    """
    if _lib is None:
        raise RuntimeError("C kernel not loaded -- check ACCEL_AVAILABLE first")

    x = np.ascontiguousarray(x.ravel(), dtype=np.float32)
    weight = np.ascontiguousarray(weight.ravel(), dtype=np.float32)
    bias = np.ascontiguousarray(bias.ravel(), dtype=np.float32)
    C = x.shape[0]

    y = np.empty(C, dtype=np.float32)

    _lib.layernorm_fused(
        x.ctypes.data,
        weight.ctypes.data,
        bias.ctypes.data,
        y.ctypes.data,
        C,
        ctypes.c_float(eps),
    )

    return y


def groupnorm(x, weight, bias, num_groups, eps=1e-5):
    """
    Fused GroupNorm using C/AVX2 kernel.

    Args:
        x:          [C] float32 input
        weight:     [C] float32 scale
        bias:       [C] float32 shift
        num_groups: int, number of groups (e.g. 32)
        eps:        float, default 1e-5

    Returns:
        y: [C] float32 normalized output
    """
    if _lib is None:
        raise RuntimeError("C kernel not loaded -- check ACCEL_AVAILABLE first")

    x = np.ascontiguousarray(x.ravel(), dtype=np.float32)
    weight = np.ascontiguousarray(weight.ravel(), dtype=np.float32)
    bias = np.ascontiguousarray(bias.ravel(), dtype=np.float32)
    C = x.shape[0]

    y = np.empty(C, dtype=np.float32)

    _lib.groupnorm_fused(
        x.ctypes.data,
        weight.ctypes.data,
        bias.ctypes.data,
        y.ctypes.data,
        C,
        num_groups,
        ctypes.c_float(eps),
    )

    return y


def set_threads(n: int):
    """Set the number of OpenMP threads for parallel kernels.

    Call this before heavy computation to control parallelism.
    Typically set to physical core count (not hyperthreads) for best perf.

    Args:
        n: Number of threads. 0 or negative = use OpenMP default.
    """
    if _lib is None:
        return
    try:
        _lib.battery_set_threads(max(1, n))
    except Exception:
        pass


def get_threads() -> int:
    """Get current OpenMP thread count. Returns 1 if unavailable."""
    if _lib is None:
        return 1
    try:
        return _lib.battery_get_threads()
    except Exception:
        return 1


def get_num_procs() -> int:
    """Get number of available processors. Returns 1 if unavailable."""
    if _lib is None:
        return 1
    try:
        return _lib.battery_get_num_procs()
    except Exception:
        return 1


# ---- Init on import ----

def _init():
    global ACCEL_AVAILABLE

    try:
        if _needs_compile():
            if not _compile():
                return
        if not _load_lib():
            return
        ACCEL_AVAILABLE = True

    except Exception as e:
        _log(f"[battery_accel] Init failed: {e}")
        ACCEL_AVAILABLE = False

_init()
