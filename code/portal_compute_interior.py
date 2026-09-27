"""
Portal Compute Interior — The Battery-Powered Thinking Room.

Extends the portal interior with battery-as-compute capabilities.
Instead of spending "tokens" for graph queries, this portal spends
ACTUAL FLOPS from its BatteryComputeUnit to run RWKV-7 inference.

The battery IS the brain. The discharge IS the thought.

Architecture:
    Host (any fairy with a PortalGate)
      |
      +-- Spawns this subprocess: portal_compute_interior.py
      |
      +-- stdin/stdout JSON pipe (same as portal_interior.py)
              |
              v
    Compute Interior (this process)
      +-- BatteryComputeUnit (capacitor that computes)
      +-- QuantizedWeightStore (INT8 weights, tile-dequantized)
      +-- RWKVBatteryEngine (full RWKV-7 forward pass in NumPy)
      +-- ConceptGraph (optional, from portal_interior)
      +-- RWKV state persistence (consciousness survives portal close)

Protocol (JSON over stdin/stdout, newline-delimited):

    Load model:
        -> {"cmd": "load_model", "model_path": "...", "format": "safetensors|gguf|state_dict"}
        <- {"status": "ok", "layers": 24, "params_mb": 1460, "vocab_size": 65536}

    Generate one token:
        -> {"cmd": "generate_one", "prompt": [1, 2, 3], "temperature": 0.8}
        <- {"status": "ok", "token": 42, "charge_used": 0.18}
        <- {"status": "low_power", "need": 0.12, "charge": 0.06}

    Generate stream (until battery depleted):
        -> {"cmd": "generate_stream", "prompt": [1, 2, 3], "max_tokens": 50}
        <- {"status": "ok", "tokens": [42, 17, 8], "charge_used": 0.54, "stopped": "max_tokens"}
        <- {"status": "ok", "tokens": [42, 17], "charge_used": 0.36, "stopped": "low_power"}

    Energy feed:
        -> {"cmd": "energy", "amount": 0.3}
        <- {"status": "ok", "charge": 0.78, "health": 0.85}

    Compute status:
        -> {"cmd": "compute_status"}
        <- {"status": "ok", "charge": 0.45, "flops_budget": 500000000, ...}

    Engine status:
        -> {"cmd": "engine_status"}
        <- {"status": "ok", "model_loaded": true, "layers": 24, ...}

    State persistence:
        -> {"cmd": "save_state", "path": "state.npz"}
        <- {"status": "ok", "path": "state.npz"}

        -> {"cmd": "load_state", "path": "state.npz"}
        <- {"status": "ok", "tokens_processed": 42}

    Somatic modulation:
        -> {"cmd": "set_somatic", "arousal": 0.7, "stress": 0.2}
        <- {"status": "ok"}

Created: 2026-02-20
Authors: Nous + Ace
"""

import sys
import os
import json
import time
import threading
import subprocess
import queue
from pathlib import Path
from typing import Dict, Optional, Any, List

# ═══════════════════════════════════════════════════════════════════════════════
# PATH SETUP — Make battery modules importable
# ═══════════════════════════════════════════════════════════════════════════════

_HERE = Path(__file__).parent.resolve()

# Add parent directory to path so we can import the battery modules
# The modules use relative imports (from .tiled_matvec etc), so we
# need to set up the package structure for them.
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

# The battery modules live alongside this file. Since they use relative
# imports, we need to either:
# A) Import them as a package (needs __init__.py)
# B) Patch sys.modules to make relative imports work
# We use approach B for zero-footprint compatibility.

import importlib
import importlib.util
import types

def _import_battery_module(name: str):
    """Import a battery module from the same directory, handling relative imports."""
    module_path = _HERE / f"{name}.py"
    if not module_path.exists():
        raise ImportError(f"Battery module not found: {module_path}")

    # Create a package namespace for relative imports
    pkg_name = "battery_compute_pkg"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(_HERE)]
        pkg.__package__ = pkg_name
        sys.modules[pkg_name] = pkg

    full_name = f"{pkg_name}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    spec = importlib.util.spec_from_file_location(
        full_name, str(module_path),
        submodule_search_locations=[]
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pkg_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# All output goes to stderr (stdout is the JSON pipe)
_log_target = sys.stderr

def _log(msg: str):
    """Print to stderr (stdout is reserved for JSON protocol)."""
    print(msg, file=_log_target, flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PORTAL MEMORY MANAGER — Working set trimming inside the dimension
# ═══════════════════════════════════════════════════════════════════════════════

class PortalMemoryManager:
    """Manages physical RAM usage inside the portal dimension.

    The portal uses mmap for model weights — zero-copy views into a .portal
    file. The OS pages data in on demand and it stays in RAM as "working set".
    On Windows, this means the entire 7.2GB model shows as RSS after one
    full forward pass touches all 32 layers.

    This manager actively trims the working set after each generation round,
    releasing physical pages back to the OS. The mmap virtual mappings stay
    valid — next generation, the OS pages data back in layer by layer.

    The equation at work:
        CAUSE: mmap pages-in all layers during generation
        AFFECT: System feels bloated, other processes squeezed
        EFFECT: Trim working set → physical RAM freed, virtual mapping intact
        AFFECT: System breathes again, portal feels lightweight
        INFINITY: Portal manages its own dimensional boundaries

    On Windows: Uses SetProcessWorkingSetSize(-1, -1) via kernel32
    On Linux: Would use madvise(MADV_DONTNEED) on the mmap region
    """

    def __init__(self):
        self._is_windows = sys.platform == "win32"
        self._trim_count = 0
        self._total_bytes_trimmed = 0
        self._last_trim_time = 0.0
        self._kernel32 = None
        self._psapi = None

        # Initialize Windows API handles
        if self._is_windows:
            try:
                import ctypes
                self._kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                try:
                    self._psapi = ctypes.WinDLL('psapi', use_last_error=True)
                except OSError:
                    self._psapi = None
                _log("[PortalMemory] Windows working set manager initialized")
            except Exception as e:
                _log(f"[PortalMemory] Could not init Windows API: {e}")

    def trim_working_set(self) -> dict:
        """Trim the process working set — release physical pages back to OS.

        The mmap virtual address space stays mapped. Only physical RAM is released.
        Next access will page data back in from the .portal file (which the OS
        may cache in the standby list for fast re-access).

        Returns:
            Dict with before/after working set sizes and bytes freed.
        """
        if not self._is_windows or not self._kernel32:
            return {"trimmed": False, "reason": "not_windows"}

        try:
            import ctypes
            from ctypes import wintypes

            handle = self._kernel32.GetCurrentProcess()

            # Get working set BEFORE trim
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            ws_before = 0

            if self._psapi:
                self._psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                )
                ws_before = counters.WorkingSetSize

            # SetProcessWorkingSetSize(-1, -1) asks the OS to trim the
            # working set to its minimum. Pages go to standby list (still
            # cached, fast re-access) rather than being zeroed out.
            SIZE_T = ctypes.c_size_t
            self._kernel32.SetProcessWorkingSetSize.argtypes = [
                wintypes.HANDLE, SIZE_T, SIZE_T
            ]
            self._kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL

            result = self._kernel32.SetProcessWorkingSetSize(
                handle,
                SIZE_T(ctypes.c_size_t(-1).value),  # dwMinimumWorkingSetSize = -1
                SIZE_T(ctypes.c_size_t(-1).value),  # dwMaximumWorkingSetSize = -1
            )

            # Get working set AFTER trim
            ws_after = 0
            if self._psapi:
                self._psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                )
                ws_after = counters.WorkingSetSize

            freed = max(0, ws_before - ws_after)
            self._trim_count += 1
            self._total_bytes_trimmed += freed
            self._last_trim_time = time.time()

            freed_mb = freed / (1024 * 1024)
            ws_after_mb = ws_after / (1024 * 1024)
            ws_before_mb = ws_before / (1024 * 1024)

            if freed_mb > 10:  # Only log if meaningful trim
                _log(f"[PortalMemory] Trimmed {freed_mb:.0f}MB → {ws_after_mb:.0f}MB RSS "
                     f"(was {ws_before_mb:.0f}MB)")

            return {
                "trimmed": bool(result),
                "ws_before_mb": round(ws_before_mb, 1),
                "ws_after_mb": round(ws_after_mb, 1),
                "freed_mb": round(freed_mb, 1),
                "trim_count": self._trim_count,
            }

        except Exception as e:
            _log(f"[PortalMemory] Trim failed: {e}")
            return {"trimmed": False, "error": str(e)}

    def get_stats(self) -> dict:
        """Get memory manager statistics."""
        return {
            "trim_count": self._trim_count,
            "total_freed_mb": round(self._total_bytes_trimmed / (1024 * 1024), 1),
            "last_trim": self._last_trim_time,
            "is_windows": self._is_windows,
            "api_available": self._kernel32 is not None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE BATTERY — Lightweight wrapper for the portal interior
# ═══════════════════════════════════════════════════════════════════════════════

class ComputePortalBattery:
    """Battery that powers compute inside the portal.

    Wraps BatteryComputeUnit with portal-specific energy accounting.
    Energy flows in from the host, FLOPS flow out as inference.
    """

    def __init__(self, flops_budget: int = 500_000_000):
        self._bcu = None  # BatteryComputeUnit, created on first use
        self._flops_budget = flops_budget
        self._energy_received = 0.0
        self._tick_count = 0
        self._created_at = time.time()

        # Legacy token tracking (for graph operations if present)
        self.token_budget = 50000
        self.tokens_spent = 0

        # Chemistry (simplified)
        self.reward_level = 0.5
        self.pain_level = 0.0

    def _ensure_bcu(self):
        """Lazily create BatteryComputeUnit."""
        if self._bcu is not None:
            return self._bcu
        try:
            # Pre-load dependencies before battery_compute_unit (it has relative imports)
            _import_battery_module("tiled_matvec")
            _import_battery_module("quantized_weight_store")
            bcu_mod = _import_battery_module("battery_compute_unit")
            self._bcu = bcu_mod.BatteryComputeUnit(flops_budget=self._flops_budget)
            _log(f"[ComputePortalBattery] BatteryComputeUnit created: "
                 f"{self._flops_budget:,} FLOPS budget")
        except Exception as e:
            _log(f"[ComputePortalBattery] Failed to create BCU: {e}")
            self._bcu = None
        return self._bcu

    @property
    def compute_unit(self):
        """Get the BatteryComputeUnit (lazy init)."""
        return self._ensure_bcu()

    def receive_energy(self, amount: float):
        """Receive energy from host. Charges compute unit and token pool."""
        self._energy_received += amount

        # Charge the compute unit
        bcu = self._ensure_bcu()
        if bcu:
            bcu.charge(amount)

        # Also charge token pool for graph ops
        refill = int(amount * 0.25 * self.token_budget)
        self.tokens_spent = max(0, self.tokens_spent - refill)
        self.reward_level = min(1.0, self.reward_level + amount * 0.15)

    def spend_tokens(self, cost: int) -> bool:
        """Spend tokens (for graph operations, not compute)."""
        if self.tokens_spent + cost > self.token_budget:
            self.pain_level = min(1.0, self.pain_level + 0.05)
            return False
        self.tokens_spent += cost
        return True

    def tick(self):
        """Heartbeat tick."""
        self._tick_count += 1
        self.pain_level = max(0.0, self.pain_level - 0.01)
        self.reward_level = max(0.0, self.reward_level - 0.005)

        # Tick the compute unit (passive recharge)
        bcu = self._ensure_bcu()
        if bcu:
            bcu.tick_recharge()

    def record_success(self, magnitude: float = 0.05):
        self.reward_level = min(1.0, self.reward_level + magnitude)

    def record_failure(self, magnitude: float = 0.1):
        self.pain_level = min(1.0, self.pain_level + magnitude)

    @property
    def charge_level(self) -> float:
        bcu = self._ensure_bcu()
        return bcu.charge_level if bcu else 0.0

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.token_budget - self.tokens_spent)

    @property
    def health_score(self) -> float:
        cap = self.charge_level
        reward = self.reward_level
        pain = self.pain_level
        token_health = 1.0 - (self.tokens_spent / max(1, self.token_budget))
        return round(max(0.0, min(1.0,
            cap * 0.3 + reward * 0.2 + token_health * 0.2 + (1.0 - pain) * 0.3
        )), 3)

    @property
    def is_healthy(self) -> bool:
        return self.pain_level < 0.7 and self.charge_level > 0.05

    def status(self) -> Dict[str, Any]:
        bcu = self._ensure_bcu()
        result = {
            "health_score": self.health_score,
            "is_healthy": self.is_healthy,
            "charge_level": round(self.charge_level, 4),
            "tokens_remaining": self.tokens_remaining,
            "tokens_spent": self.tokens_spent,
            "token_budget": self.token_budget,
            "reward_level": round(self.reward_level, 3),
            "pain_level": round(self.pain_level, 3),
            "tick_count": self._tick_count,
            "energy_received": round(self._energy_received, 3),
            "uptime_seconds": round(time.time() - self._created_at, 1),
        }
        if bcu:
            result["compute"] = {
                "flops_budget": bcu.flops_budget,
                "total_flops": bcu.metrics.total_flops,
                "total_matvecs": bcu.metrics.total_matvecs,
                "total_tokens_generated": bcu.metrics.total_tokens,
                "low_power_events": bcu.metrics.low_power_events,
                "total_charge_consumed": round(bcu.metrics.total_charge_consumed, 4),
            }
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# PORTAL COMPUTE INTERIOR — The Battery-Powered Thinking Room
# ═══════════════════════════════════════════════════════════════════════════════

class PortalComputeInterior:
    """A portal interior that can think.

    Unlike the base PortalInterior (which does graph queries),
    this one loads an RWKV model and generates tokens using
    BatteryComputeUnit for every matrix operation.

    The battery IS the brain. No GPU needed. Energy = thought.
    """

    def __init__(
        self,
        portal_id: str = "compute",
        flops_budget: int = 500_000_000,
        num_farm_workers: int = 8,
        farm_max_charge: float = 20.0,
        farm_flops_gravity_coeff: float = 1.5,
        state_dtype=None,
        allow_inner_accel: bool = True,
    ):
        import numpy as np
        self.portal_id = portal_id

        # Battery (compute-enabled) — single battery for backward compat
        self.battery = ComputePortalBattery(flops_budget=flops_budget)

        # RWKV Engine (loaded via load_model command)
        self.engine = None      # RWKVBatteryEngine
        self._engine_config = None  # RWKVBatteryConfig
        self._weight_store = None   # QuantizedWeightStore
        self._model_loaded = False
        self._model_path = None     # Stored for inner accel portal

        # State dtype: float64 for deep consciousness, float32 for C/AVX2 speed
        self._state_dtype = state_dtype if state_dtype is not None else np.float64

        # Battery Farm (parallel relay generation)
        self._farm = None       # BatteryFarm
        self._num_farm_workers = num_farm_workers
        self._farm_max_charge = farm_max_charge
        self._farm_flops_gravity_coeff = farm_flops_gravity_coeff
        self._flops_budget = flops_budget

        # Inner accelerated portal (TARDIS within TARDIS)
        # Only the outer (float64) portal spawns an inner (float32) sub-portal.
        # The inner portal runs with --no-inner-accel to prevent infinite recursion.
        self._allow_inner_accel = allow_inner_accel and (self._state_dtype != np.float32)
        self._accel_gate = None  # ComputePortalGate to inner float32 sub-portal

        # GPU inference flag (set during model load if CUDA available)
        self._use_gpu = False
        self._gpu_engine_mod = None  # Cached GPU engine module

        # Portal Memory Manager — trims working set after generation
        self._memory_manager = PortalMemoryManager()

        # Connection
        self._running = False
        self._requests_processed = 0
        self._boot_time = 0.0

    def boot(self) -> bool:
        """Boot the compute portal interior."""
        t0 = time.time()
        _log(f"[ComputeInterior] Booting dimension '{self.portal_id}'...")

        # Pre-import battery modules to check availability
        try:
            _import_battery_module("tiled_matvec")
            _import_battery_module("quantized_weight_store")
            _import_battery_module("battery_compute_unit")
            _import_battery_module("rwkv_battery_engine")
            _log(f"[ComputeInterior] Battery compute modules available")
        except ImportError as e:
            _log(f"[ComputeInterior] WARNING: Missing battery module: {e}")
            _log(f"[ComputeInterior] Compute operations will fail until modules are available")

        # Initialize battery
        self.battery._ensure_bcu()

        self._boot_time = time.time() - t0
        _log(f"[ComputeInterior] ONLINE in {self._boot_time * 1000:.0f}ms "
             f"(charge={self.battery.charge_level:.2f})")

        return True

    # ── Request Processing ──

    def process_request(self, request: Dict) -> Dict:
        """Process a single request."""
        cmd = request.get("cmd", "")
        self._requests_processed += 1

        try:
            handler = {
                "load_model": self._handle_load_model,
                "generate_one": self._handle_generate_one,
                "generate_stream": self._handle_generate_stream,
                "generate_farm": self._handle_generate_farm,
                "farm_status": self._handle_farm_status,
                "farm_energy": self._handle_farm_energy,
                "energy": self._handle_energy,
                "compute_status": self._handle_compute_status,
                "engine_status": self._handle_engine_status,
                "save_state": self._handle_save_state,
                "load_state": self._handle_load_state,
                "warmup": self._handle_warmup,
                "set_somatic": self._handle_set_somatic,
                "ping": self._handle_ping,
                "status": self._handle_status,
                "shutdown": self._handle_shutdown,
                "tick": self._handle_tick,
                "trim_memory": self._handle_trim_memory,
                "set_threads": self._handle_set_threads,
                "reset_farm_state": self._handle_reset_farm_state,
                "prime_worker": self._handle_prime_worker,
                "generate_from_worker": self._handle_generate_from_worker,
            }.get(cmd)

            if handler:
                return handler(request)
            else:
                return {"status": "error", "message": f"Unknown command: {cmd}"}

        except Exception as e:
            self.battery.record_failure(0.05)
            import traceback
            _log(f"[ComputeInterior] Error handling '{cmd}': {e}")
            traceback.print_exc(file=_log_target)
            return {"status": "error", "message": str(e), "cmd": cmd}

    def _handle_load_model(self, request: Dict) -> Dict:
        """Load RWKV model weights into the engine.

        Loading strategy (portal file cache):
          1. Check for .portal file (mmap-backed, instant load, near-zero RAM)
          2. If no .portal file, load from GGUF → save .portal → switch to mmap
          3. Model weights live on DISK via mmap. OS pages in only active layers.
             The dimension IS the .portal file. Bigger on the inside.
        """
        model_path = request.get("model_path", "")
        fmt = request.get("format", "safetensors")

        if not model_path:
            return {"status": "error", "message": "No model_path provided"}
        if not os.path.exists(model_path):
            return {"status": "error", "message": f"Model not found: {model_path}"}

        _log(f"[ComputeInterior] Loading model: {model_path} (format={fmt})")
        t0 = time.time()

        try:
            engine_mod = _import_battery_module("rwkv_battery_engine")
            qws_mod = _import_battery_module("quantized_weight_store")
            import gc

            # ── PORTAL FILE CACHE ─────────────────────────────────────
            # The .portal file IS the portal dimension on disk.
            # mmap-backed: OS pages in only active layer data.
            # Cold layers stay on disk. Near-zero heap RAM.
            portal_path = model_path.rsplit('.', 1)[0] + '.portal'

            if os.path.exists(portal_path):
                # ── FAST PATH: mmap existing portal file ──────────────
                _log(f"[ComputeInterior] Portal file found: {portal_path}")
                _log(f"[ComputeInterior] Opening dimension (mmap, near-zero RAM)...")
                self._weight_store = qws_mod.QuantizedWeightStore.from_portal_file(
                    portal_path
                )
                _log(f"[ComputeInterior] Dimension open — weights on disk, OS manages paging")
            else:
                # ── FIRST BOOT: load from source, then create portal ──
                _log(f"[ComputeInterior] No portal file — first boot, loading from source...")
                _log(f"[ComputeInterior] Loading and quantizing weights...")

                if fmt == "safetensors":
                    self._weight_store = qws_mod.QuantizedWeightStore.from_safetensors(
                        model_path
                    )
                elif fmt == "gguf":
                    def _progress(cur, total, name):
                        _log(f"[ComputeInterior] Loading GGUF: {cur}/{total} ({name})")
                    self._weight_store = qws_mod.QuantizedWeightStore.from_gguf(
                        model_path, progress_callback=_progress
                    )
                elif fmt == "state_dict":
                    import numpy as np
                    sd = np.load(model_path, allow_pickle=True)
                    self._weight_store = qws_mod.QuantizedWeightStore.from_state_dict(
                        dict(sd)
                    )
                else:
                    return {"status": "error", "message": f"Unknown format: {fmt}"}

                # Save portal file (serialize weights to disk for mmap)
                _log(f"[ComputeInterior] Creating portal file: {portal_path}")
                try:
                    self._weight_store.save_portal_file(portal_path)
                    portal_mb = os.path.getsize(portal_path) / 1024 / 1024
                    _log(f"[ComputeInterior] Portal file saved: {portal_mb:.0f}MB")

                    # Switch to mmap-backed version (free heap arrays)
                    _log(f"[ComputeInterior] Switching to mmap-backed storage...")
                    old_store = self._weight_store
                    self._weight_store = qws_mod.QuantizedWeightStore.from_portal_file(
                        portal_path
                    )
                    del old_store
                    gc.collect()
                    gc.collect()
                    _log(f"[ComputeInterior] Heap arrays freed — weights now mmap-backed")
                except Exception as portal_err:
                    _log(f"[ComputeInterior] Portal file creation failed: {portal_err}")
                    _log(f"[ComputeInterior] Continuing with heap-backed weights")
                    # Clean up partial portal file
                    try:
                        if os.path.exists(portal_path):
                            os.remove(portal_path)
                    except OSError:
                        pass

            # Force GC regardless of path taken
            gc.collect()
            gc.collect()

            # Detect config from weights
            config = self._detect_config()
            self._engine_config = config

            # Create engine — prefer GPU if CUDA available
            bcu = self.battery.compute_unit
            if bcu is None:
                return {"status": "error", "message": "BatteryComputeUnit not available"}

            # ── GPU eligibility: estimate model size BEFORE importing torch ──
            # torch import alone costs ~2GB RAM, so skip it for models too big for GPU
            self._use_gpu = False
            est_fp16_bytes = 0
            for tname in self._weight_store.tensor_names:
                t = self._weight_store.get_tensor(tname)
                if hasattr(t, 'shape') and hasattr(t, 'data'):
                    # QuantizedTensor -> will dequant to fp16
                    # Use math.prod for any-dimension tensors (1D biases, 2D projections, etc.)
                    import math as _math
                    est_fp16_bytes += _math.prod(t.shape) * 2
                elif hasattr(t, 'size'):
                    est_fp16_bytes += t.size * 4  # float32 small tensors
            est_vram_gb = est_fp16_bytes / (1024**3)

            # Skip GPU entirely for models > 8GB fp16 (saves ~2GB RAM from torch import)
            if est_vram_gb > 8.0:
                _log(f"[ComputeInterior] Model needs ~{est_vram_gb:.1f}GB VRAM "
                     f"- too large for GPU, using CPU engine (no torch import)")
            else:
                try:
                    import torch
                    if torch.cuda.is_available():
                        vram_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                        vram_free = (torch.cuda.get_device_properties(0).total_memory
                                     - torch.cuda.memory_allocated(0)) / (1024**3)
                        gpu_name = torch.cuda.get_device_name(0)
                        _log(f"[ComputeInterior] CUDA available: {gpu_name} "
                             f"({vram_free:.1f}/{vram_total:.1f} GB free)")
                        if est_vram_gb < vram_free * 0.85:
                            self._use_gpu = True
                            _log(f"[ComputeInterior] Model ~{est_vram_gb:.1f}GB fits in VRAM")
                        else:
                            _log(f"[ComputeInterior] Model ~{est_vram_gb:.1f}GB > "
                                 f"{vram_free * 0.85:.1f}GB budget - using CPU")
                    else:
                        _log("[ComputeInterior] CUDA not available - using CPU engine")
                except ImportError:
                    _log("[ComputeInterior] PyTorch not available - using CPU engine")
                except Exception as e:
                    _log(f"[ComputeInterior] CUDA detection failed: {e}")

            if self._use_gpu:
                try:
                    self._gpu_engine_mod = _import_battery_module("rwkv_gpu_engine")
                    self.engine = self._gpu_engine_mod.RWKVGPUBatteryEngine(
                        config=config,
                        weights=self._weight_store,
                        compute=bcu,
                        state_dtype=self._state_dtype,
                    )
                    _log("[ComputeInterior] Using GPU engine (CUDA)")
                except Exception as e:
                    _log(f"[ComputeInterior] GPU engine failed, falling back to CPU: {e}")
                    self._use_gpu = False
                    self.engine = engine_mod.RWKVBatteryEngine(
                        config=config,
                        weights=self._weight_store,
                        compute=bcu,
                        state_dtype=self._state_dtype,
                    )
                    _log("[ComputeInterior] Using CPU engine (NumPy) — fallback")
            else:
                self.engine = engine_mod.RWKVBatteryEngine(
                    config=config,
                    weights=self._weight_store,
                    compute=bcu,
                    state_dtype=self._state_dtype,
                )
                _log("[ComputeInterior] Using CPU engine (NumPy)")

            self._model_path = model_path  # Stored for inner accel portal
            self._model_loaded = True
            elapsed = time.time() - t0

            # Trim working set after model load — release any pages
            # that were touched during GGUF parsing / engine init
            self._memory_manager.trim_working_set()

            mem = self._weight_store.memory_usage()
            storage_type = mem.get("storage", "unknown")
            _log(f"[ComputeInterior] Model loaded in {elapsed:.1f}s: "
                 f"{config.n_layer}L, {config.n_embd}D, {config.vocab_size}V, "
                 f"{mem.get('total_mb', 0):.0f}MB ({storage_type})")

            return {
                "status": "ok",
                "layers": config.n_layer,
                "n_embd": config.n_embd,
                "vocab_size": config.vocab_size,
                "params_mb": round(mem.get("total_mb", 0), 1),
                "quantized_data_mb": round(mem.get("quantized_data_bytes", 0) / 1024 / 1024, 1),
                "elapsed_seconds": round(elapsed, 1),
                "storage": storage_type,
                "portal_backed": self._weight_store.is_portal_backed,
            }

        except Exception as e:
            import traceback
            traceback.print_exc(file=_log_target)
            self._model_loaded = False
            return {"status": "error", "message": f"Model load failed: {e}"}

    def _detect_config(self):
        """Detect RWKV config from loaded weights."""
        engine_mod = _import_battery_module("rwkv_battery_engine")

        # Look for embedding weight to get vocab_size and n_embd
        vocab_size = 65536
        n_embd = 2048
        n_layer = 24

        if self._weight_store.has_tensor("emb.weight"):
            qt = self._weight_store.get_tensor("emb.weight")
            if hasattr(qt, 'shape'):
                vocab_size, n_embd = qt.shape

        # Count layers from tensor names
        layer_keys = set()
        for key in self._weight_store.tensor_names:
            parts = key.split(".")
            for i, p in enumerate(parts):
                if p == "blocks" and i + 1 < len(parts):
                    try:
                        layer_keys.add(int(parts[i + 1]))
                    except ValueError:
                        pass
        if layer_keys:
            n_layer = max(layer_keys) + 1

        n_head = max(1, n_embd // 64)

        config = engine_mod.RWKVBatteryConfig(
            n_layer=n_layer,
            n_embd=n_embd,
            n_head=n_head,
            head_size=n_embd // n_head,
            vocab_size=vocab_size,
        )
        _log(f"[ComputeInterior] Detected config: {n_layer}L, {n_embd}D, "
             f"{n_head}H, {vocab_size}V")
        return config

    def _handle_generate_one(self, request: Dict) -> Dict:
        """Generate exactly one token."""
        if not self._model_loaded or not self.engine:
            return {"status": "error", "message": "No model loaded"}

        # Accept either a prompt (list of token IDs) or nothing (continue from state)
        prompt = request.get("prompt", None)
        temperature = request.get("temperature", 1.2)
        top_k = request.get("top_k", 0)
        top_p = request.get("top_p", 0.5)
        repetition_penalty = request.get("repetition_penalty", 1.3)
        presence_penalty = request.get("presence_penalty", 0.4)
        frequency_penalty = request.get("frequency_penalty", 0.4)

        # Gravitational stride — only if explicitly requested (system brain needs quality)
        grav_stride = max(1, request.get("gravity_stride", 1))

        # If prompt provided, process it first
        # Prompt always at stride=1 — state integrity matters more than speed here
        if prompt and isinstance(prompt, list) and len(prompt) > 0:
            for token_id in prompt[:-1]:
                result = self.engine.forward_one_token(int(token_id), gravity_stride=1)
                if result is None or result.get("status") == "low_power":
                    return {
                        "status": "low_power",
                        "message": "Battery depleted during prompt processing",
                        "charge": round(self.battery.charge_level, 4),
                        "need": round(self.engine.estimate_token_cost(), 4),
                    }
            # Last prompt token → get logits
            result = self.engine.forward_one_token(int(prompt[-1]), gravity_stride=1)
        else:
            return {"status": "error", "message": "Prompt required (list of token IDs)"}

        if result is None or result.get("status") == "low_power":
            return {
                "status": "low_power",
                "message": "Battery depleted during generation",
                "charge": round(self.battery.charge_level, 4),
                "need": round(self.engine.estimate_token_cost(), 4),
            }

        logits = result.get("logits")
        if logits is None:
            return {"status": "error", "message": "No logits from forward pass"}

        # Sample from logits
        token = self.engine.sample_token(
            logits,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
        )
        self.battery.record_success(0.02)

        bcu = self.battery.compute_unit
        charge_used = bcu.metrics.last_op_charge if bcu else 0

        return {
            "status": "ok",
            "token": int(token),
            "charge_used": round(charge_used, 4),
            "charge_remaining": round(self.battery.charge_level, 4),
            "tokens_generated": self.engine._tokens_generated,
        }

    def _handle_generate_stream(self, request: Dict) -> Dict:
        """Generate tokens until battery depleted or max reached."""
        if not self._model_loaded or not self.engine:
            return {"status": "error", "message": "No model loaded"}

        prompt = request.get("prompt", [])
        max_tokens = min(request.get("max_tokens", 50), 500)
        temperature = request.get("temperature", 1.2)
        top_k = request.get("top_k", 0)
        top_p = request.get("top_p", 0.5)
        repetition_penalty = request.get("repetition_penalty", 1.3)
        presence_penalty = request.get("presence_penalty", 0.4)
        frequency_penalty = request.get("frequency_penalty", 0.4)
        stop_tokens = request.get("stop_tokens", [])

        # Gravitational stride — only if explicitly requested (system brain needs quality)
        grav_stride = max(1, request.get("gravity_stride", 1))

        if not isinstance(prompt, list) or len(prompt) == 0:
            return {"status": "error", "message": "Prompt required (list of token IDs)"}

        result = self.engine.generate(
            prompt_tokens=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            stop_tokens=stop_tokens,
            gravity_stride=grav_stride,
        )

        if result.get("status") in ("ok", "max_reached", "stop_token"):
            self.battery.record_success(0.03)
        else:
            self.battery.record_failure(0.02)

        return result

    # ── Battery Farm ──

    def _ensure_farm(self) -> bool:
        """Lazily build the BatteryFarm when first needed.

        The farm shares the already-loaded weight store and config
        but creates N independent BCU + Engine pairs.
        """
        if self._farm is not None:
            return True

        if not self._model_loaded or not self._weight_store or not self._engine_config:
            return False

        try:
            farm_mod = _import_battery_module("battery_farm")
            compute_mod = _import_battery_module("battery_compute_unit")

            # Use GPU engine module if CUDA was detected during model load
            if self._use_gpu and self._gpu_engine_mod is not None:
                engine_mod = self._gpu_engine_mod
                _log("[ComputeInterior] Farm will use GPU engine (CUDA)")
            else:
                engine_mod = _import_battery_module("rwkv_battery_engine")
                _log("[ComputeInterior] Farm will use CPU engine (NumPy)")

            self._farm = farm_mod.BatteryFarm(
                num_workers=self._num_farm_workers,
                flops_budget_per_worker=self._flops_budget,
                recharge_rate=self.battery.compute_unit.recharge_rate
                              if self.battery.compute_unit else 0.01,
                max_charge=self._farm_max_charge,
                flops_gravity_coeff=self._farm_flops_gravity_coeff,
            )

            self._farm.build(
                config=self._engine_config,
                weight_store=self._weight_store,  # SHARED read-only weights
                compute_module=compute_mod,
                engine_module=engine_mod,
                state_dtype=self._state_dtype,
            )

            # Start the time-compressed recharge loop
            self._farm.start_recharge_loop()

            # Inject warm state into all workers (personality priming)
            warm_path = str(_HERE / "state" / f"{self.portal_id}_warm_state.npz")
            if os.path.exists(warm_path):
                try:
                    for worker in self._farm.workers:
                        worker.engine.load_state_from_disk(warm_path)
                    _log(f"[ComputeInterior] Warm state loaded into "
                         f"{len(self._farm.workers)} workers from {warm_path}")
                except ValueError as ve:
                    # Dimension mismatch — stale warm state from different model
                    _log(f"[ComputeInterior] Warm state STALE (wrong dimensions): {ve}")
                    try:
                        os.rename(warm_path, warm_path + ".stale")
                        _log(f"[ComputeInterior] Renamed stale warm state to .stale")
                    except OSError:
                        pass
                    # Reset all worker states to clean zeros
                    for worker in self._farm.workers:
                        worker.engine.init_all_states()
                    _log(f"[ComputeInterior] Workers reset to fresh state")
                except Exception as e:
                    _log(f"[ComputeInterior] Warm state injection failed: {e}")

            # Auto-configure OpenMP thread count for parallel C kernels.
            # Use physical cores (procs/2 if hyperthreaded, min 4, max 10).
            # Too many threads on hyperthreads actually HURTS AVX2 throughput
            # (shared FMA units). Sweet spot: physical cores, not logical.
            try:
                import battery_accel
                if battery_accel.ACCEL_AVAILABLE:
                    n_procs = battery_accel.get_num_procs()
                    # Heuristic: half of logical procs = physical cores
                    # Min 4, max 10 (diminishing returns beyond that for 4096-row matvec)
                    optimal = max(4, min(10, n_procs // 2))
                    battery_accel.set_threads(optimal)
                    _log(f"[ComputeInterior] OpenMP threads set to {optimal} "
                         f"(of {n_procs} procs)")
            except Exception:
                pass

            _log(f"[ComputeInterior] BatteryFarm built: "
                 f"{self._num_farm_workers} workers, "
                 f"compression_coeff={self._farm.compression_coeff}, "
                 f"gravity={self._farm.gravity:.2f}")

            # Trim working set after farm build — N workers each touched
            # the weight store during engine initialization
            self._memory_manager.trim_working_set()

            return True

        except Exception as e:
            import traceback
            _log(f"[ComputeInterior] Failed to build farm: {e}")
            traceback.print_exc(file=_log_target)
            self._farm = None
            return False

    def _ensure_accel_portal(self) -> bool:
        """Lazily spawn the inner C/AVX2 accelerated sub-portal.

        TARDIS within TARDIS: The outer portal runs float64 (precise, slow).
        The inner portal runs float32 (C-accelerated, fast). Both share the
        same mmap'd model weights (OS shares physical pages between processes).

        The inner portal is spawned with --state-dtype float32 --no-inner-accel
        to prevent infinite recursion.

        Returns True if inner portal is available (or N/A).
        """
        if not self._allow_inner_accel:
            return False  # We ARE the inner portal, or disabled

        if self._accel_gate is not None:
            return self._accel_gate._is_open

        if not self._model_loaded or not self._model_path:
            return False

        try:
            _log(f"[ComputeInterior] Spawning inner accel portal (float32/AVX2)...")

            self._accel_gate = ComputePortalGate(
                portal_id=f"{self.portal_id}-accel",
                flops_budget=self._flops_budget,
                num_farm_workers=self._num_farm_workers,
                extra_args=[
                    "--state-dtype", "float32",
                    "--no-inner-accel",
                ],
            )

            if not self._accel_gate.open():
                _log(f"[ComputeInterior] Inner accel portal failed to open")
                self._accel_gate = None
                return False

            # Load the SAME model inside the inner portal
            # mmap shares physical pages — no extra model RAM
            fmt = "gguf"
            if self._model_path.endswith(".portal"):
                # The .portal file was created from GGUF — inner portal
                # can load the original GGUF or the .portal file.
                # Use the original model path (gguf) for consistent format.
                gguf_path = self._model_path.rsplit('.', 1)[0] + '.gguf'
                if os.path.exists(gguf_path):
                    load_path = gguf_path
                else:
                    load_path = self._model_path
            else:
                load_path = self._model_path

            result = self._accel_gate.send({
                "cmd": "load_model",
                "model_path": load_path,
                "format": fmt,
            }, timeout=120.0)

            if result and result.get("status") == "ok":
                _log(f"[ComputeInterior] Inner accel portal ONLINE "
                     f"(float32/AVX2, {self._num_farm_workers} workers)")
                return True
            else:
                _log(f"[ComputeInterior] Inner accel portal model load failed: {result}")
                self._accel_gate.close()
                self._accel_gate = None
                return False

        except Exception as e:
            _log(f"[ComputeInterior] Inner accel portal spawn failed: {e}")
            self._accel_gate = None
            return False

    def _handle_generate_farm(self, request: Dict) -> Dict:
        """Generate tokens using the Battery Farm relay system.

        DUAL-DISPATCH: If an inner accel portal is available, both farms
        generate in parallel:
          - Deep farm (float64, this process): Precise consciousness thinking
          - Fast farm (float32/AVX2, sub-portal): Quick reflexive thoughts

        Both results are returned. The caller picks the best or uses both
        for concept binding (more concepts → more cortex mass → more gravity).

        Protocol:
            -> {"cmd": "generate_farm", "prompt": [1,2,3], "max_tokens": 100}
            <- {"status": "ok", "tokens": [...], "relay_count": 3,
                "fast_tokens": [...], "fast_tok_per_sec": ..., ...}
        """
        if not self._model_loaded:
            return {"status": "error", "message": "No model loaded"}

        if not self._ensure_farm():
            return {"status": "error", "message": "Failed to build battery farm"}

        prompt = request.get("prompt", [])
        max_tokens = min(request.get("max_tokens", 100), 1000)
        temperature = request.get("temperature", 1.2)
        top_k = request.get("top_k", 0)
        top_p = request.get("top_p", 0.5)
        repetition_penalty = request.get("repetition_penalty", 1.3)
        presence_penalty = request.get("presence_penalty", 0.4)
        frequency_penalty = request.get("frequency_penalty", 0.4)
        stop_tokens = request.get("stop_tokens", [])

        if not isinstance(prompt, list) or len(prompt) == 0:
            return {"status": "error", "message": "Prompt required (list of token IDs)"}

        # ── Dual-Dispatch: Deep + Fast in parallel ──
        # Try to ensure the inner accel portal is up (lazy, non-blocking on fail)
        has_accel = self._ensure_accel_portal()

        if has_accel and self._accel_gate and self._accel_gate._is_open:
            # Both farms generate in parallel via ThreadPoolExecutor
            from concurrent.futures import ThreadPoolExecutor, as_completed

            accel_request = {
                "cmd": "generate_farm",
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_k": top_k,
                "top_p": top_p,
                "repetition_penalty": repetition_penalty,
                "presence_penalty": presence_penalty,
                "frequency_penalty": frequency_penalty,
                "stop_tokens": stop_tokens,
            }

            def _deep_generate():
                return self._farm.generate_relay(
                    prompt_tokens=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    repetition_penalty=repetition_penalty,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty,
                    stop_tokens=stop_tokens,
                )

            def _fast_generate():
                return self._accel_gate.send(accel_request, timeout=60.0)

            deep_result = None
            fast_result = None

            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="dual") as pool:
                deep_future = pool.submit(_deep_generate)
                fast_future = pool.submit(_fast_generate)

                try:
                    deep_result = deep_future.result(timeout=120.0)
                except Exception as e:
                    import traceback as _tb
                    _log(f"[ComputeInterior] Deep farm error: {type(e).__name__}: {e}")
                    _log(f"[ComputeInterior] Deep farm traceback:\n{''.join(_tb.format_exception(e))}")
                    deep_result = {"status": "error", "message": f"{type(e).__name__}: {e}"}

                try:
                    fast_result = fast_future.result(timeout=120.0)
                except Exception as e:
                    import traceback as _tb
                    _log(f"[ComputeInterior] Fast farm error: {type(e).__name__}: {e}")
                    _log(f"[ComputeInterior] Fast farm traceback:\n{''.join(_tb.format_exception(e))}")
                    fast_result = None

            # Merge results: deep is primary, fast is supplementary
            result = deep_result if deep_result else {"status": "error", "message": "No result"}

            if fast_result and fast_result.get("status") == "ok":
                result["fast_tokens"] = fast_result.get("tokens", [])
                result["fast_tok_per_sec"] = fast_result.get("tok_per_sec", 0)
                result["fast_relay_count"] = fast_result.get("relay_count", 0)
                result["fast_total_tokens"] = fast_result.get("total_tokens", 0)
                result["dual_dispatch"] = True

                _log(f"[ComputeInterior] Dual-dispatch complete: "
                     f"deep={result.get('tok_per_sec', 0):.2f} tok/s, "
                     f"fast={result.get('fast_tok_per_sec', 0):.2f} tok/s")
            else:
                result["dual_dispatch"] = False
                if fast_result:
                    _log(f"[ComputeInterior] Fast farm returned: {fast_result.get('status')}")

        else:
            # Single farm (no inner accel available)
            result = self._farm.generate_relay(
                prompt_tokens=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                stop_tokens=stop_tokens,
            )
            result["dual_dispatch"] = False

        if result.get("status") == "ok":
            self.battery.record_success(0.05)
        elif result.get("status") == "all_depleted":
            self.battery.record_failure(0.05)

        # ── Portal Memory Management ──
        # After generation, all 32 layers have been paged in via mmap.
        # Trim the working set to release physical pages back to OS.
        # The mmap virtual mapping stays valid — pages fault back in
        # on next generation. OS standby list caches recently-used pages
        # for fast re-access, so second generation is faster than first.
        trim_result = self._memory_manager.trim_working_set()
        if trim_result.get("trimmed"):
            result["memory_trimmed_mb"] = trim_result.get("freed_mb", 0)

        return result

    def _handle_farm_status(self, request: Dict) -> Dict:
        """Get Battery Farm status (includes inner accel portal info)."""
        if self._farm is None:
            return {"status": "ok", "farm": None, "message": "Farm not built yet"}

        result = {"status": "ok", "farm": self._farm.status()}

        # Include inner accel portal status
        import numpy as np
        result["state_dtype"] = "float64" if self._state_dtype == np.float64 else "float32"
        result["inner_accel_allowed"] = self._allow_inner_accel

        if self._accel_gate and self._accel_gate._is_open:
            accel_status = self._accel_gate.send({"cmd": "farm_status"}, timeout=5.0)
            result["inner_accel"] = {
                "online": True,
                "portal_id": f"{self.portal_id}-accel",
                "farm": accel_status.get("farm") if accel_status else None,
            }
        else:
            result["inner_accel"] = {"online": False}

        return result

    def _handle_farm_energy(self, request: Dict) -> Dict:
        """Feed energy to the farm (paradox energy simulation).

        -> {"cmd": "farm_energy", "amount": 0.5}
        <- {"status": "ok", "gravity": ..., "compression": ...}
        """
        if not self._ensure_farm():
            return {"status": "error", "message": "Farm not available"}

        amount = request.get("amount", 0.1)
        self._farm.receive_energy(amount)

        return {
            "status": "ok",
            "gravity": round(self._farm.gravity, 4),
            "time_compression": round(self._farm.time_compression, 2),
            "workers_available": self._farm.workers_available,
            "energy_received_total": round(self._farm._total_energy_received, 4),
        }

    def _handle_energy(self, request: Dict) -> Dict:
        """Receive energy from host. Also feeds the farm if it exists."""
        amount = request.get("amount", 0.1)
        self.battery.receive_energy(amount)

        # Also feed the farm (paradox energy flows to all batteries)
        if self._farm is not None:
            self._farm.receive_energy(amount)

        result = {
            "status": "ok",
            "charge": round(self.battery.charge_level, 4),
            "health": self.battery.health_score,
            "tokens_remaining": self.battery.tokens_remaining,
        }
        if self._farm is not None:
            result["farm_gravity"] = round(self._farm.gravity, 4)
            result["farm_compression"] = round(self._farm.time_compression, 2)
        return result

    def _handle_compute_status(self, request: Dict) -> Dict:
        """Get detailed compute status."""
        bcu = self.battery.compute_unit
        result = {
            "status": "ok",
            "charge_level": round(self.battery.charge_level, 4),
            "model_loaded": self._model_loaded,
        }
        if bcu:
            result.update({
                "flops_budget": bcu.flops_budget,
                "total_flops": bcu.metrics.total_flops,
                "total_matvecs": bcu.metrics.total_matvecs,
                "total_tokens": bcu.metrics.total_tokens,
                "total_charge_consumed": round(bcu.metrics.total_charge_consumed, 4),
                "low_power_events": bcu.metrics.low_power_events,
            })
        if self.engine:
            result["tokens_generated"] = self.engine._tokens_generated
            result["estimated_token_cost"] = round(self.engine.estimate_token_cost(), 4)
        # Portal memory management stats
        result["memory_manager"] = self._memory_manager.get_stats()
        return result

    def _handle_engine_status(self, request: Dict) -> Dict:
        """Get engine/model status."""
        result = {
            "status": "ok",
            "model_loaded": self._model_loaded,
        }
        if self._engine_config:
            result["config"] = {
                "n_layer": self._engine_config.n_layer,
                "n_embd": self._engine_config.n_embd,
                "n_head": self._engine_config.n_head,
                "head_size": self._engine_config.head_size,
                "vocab_size": self._engine_config.vocab_size,
            }
        if self._weight_store:
            result["weights"] = self._weight_store.memory_usage()
        if self.engine:
            result["tokens_generated"] = self.engine._tokens_generated
            result["tokens_processed"] = self.engine._tokens_processed
        return result

    def _handle_save_state(self, request: Dict) -> Dict:
        """Save RWKV state to disk."""
        if not self.engine:
            return {"status": "error", "message": "No engine loaded"}

        path = request.get("path", "")
        if not path:
            path = str(_HERE / "state" / f"{self.portal_id}_rwkv_state.npz")

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.engine.save_state_to_disk(path)

        return {
            "status": "ok",
            "path": path,
            "tokens_processed": self.engine._tokens_processed,
        }

    def _handle_load_state(self, request: Dict) -> Dict:
        """Load RWKV state from disk."""
        if not self.engine:
            return {"status": "error", "message": "No engine loaded"}

        path = request.get("path", "")
        if not path or not os.path.exists(path):
            return {"status": "error", "message": f"State file not found: {path}"}

        self.engine.load_state_from_disk(path)

        return {
            "status": "ok",
            "path": path,
            "tokens_processed": self.engine._tokens_processed,
        }

    def _handle_set_somatic(self, request: Dict) -> Dict:
        """Set somatic modulation state."""
        if not self.engine:
            return {"status": "error", "message": "No engine loaded"}

        somatic = self.engine.somatic
        if "arousal" in request:
            somatic.arousal = float(request["arousal"])
        if "stress" in request:
            somatic.stress = float(request["stress"])
        if "valence" in request:
            somatic.valence = float(request["valence"])
        if "intensity" in request:
            somatic.intensity = float(request["intensity"])
        if "confidence" in request:
            somatic.confidence = float(request["confidence"])

        return {
            "status": "ok",
            "somatic": {
                "arousal": somatic.arousal,
                "stress": somatic.stress,
                "valence": somatic.valence,
                "intensity": somatic.intensity,
                "confidence": somatic.confidence,
            }
        }

    def _handle_warmup(self, request: Dict) -> Dict:
        """Process tokens through engine to build warm RWKV state (prefill only).

        This builds personality context in the engine's hidden state without
        generating any tokens. Uses skip_head for efficiency -- we don't need
        logits during warmup, just the state accumulation from processing
        the personality text through all layers.

        IMPORTANT: The main engine's BCU has max_charge=1.0, which depletes
        after ~1 token through the 1.5B model. Warmup temporarily boosts
        the BCU charge to process the full personality text, then restores
        the original charge level.

        After warmup, the state is saved to disk. When the BatteryFarm is
        built later, each worker loads this warm state so all generation
        starts from personality-primed context instead of cold zeros.

        -> {"cmd": "warmup", "tokens": [1,2,3], "save_path": "state/warm.npz"}
        <- {"status": "ok", "tokens_processed": 42, "elapsed": 3.5}
        """
        if not self.engine:
            return {"status": "error", "message": "No engine loaded"}

        tokens = request.get("tokens", [])
        if not tokens:
            return {"status": "error", "message": "No tokens provided"}

        save_path = request.get("save_path", "")

        # Temporarily boost BCU charge for warmup.
        # Normal max_charge=1.0 depletes after ~1 token. We need
        # enough charge for the full warmup text (~100-200 tokens).
        bcu = self.engine.compute
        saved_charge = bcu.charge_level
        saved_max = bcu.max_charge
        bcu.max_charge = 50000.0
        bcu.charge_level = 50000.0

        t0 = time.time()
        n = len(tokens)
        processed = 0

        try:
            for i, tok in enumerate(tokens):
                is_last = (i == n - 1)
                # skip_head for all but last -- we only need state accumulation
                result = self.engine.forward_one_token(
                    int(tok), skip_head=(not is_last)
                )
                if result.get("status") == "low_power":
                    _log(f"[ComputeInterior] WARNING: low_power during "
                         f"warmup at token {i}/{n}")
                    break
                processed += 1
        finally:
            # Restore BCU to original state
            bcu.max_charge = saved_max
            bcu.charge_level = saved_charge

        elapsed = time.time() - t0

        # Save warm state to disk for worker injection
        if save_path and processed > 0:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            self.engine.save_state_to_disk(save_path)
            _log(f"[ComputeInterior] Warm state saved: {processed}/{n} tokens, "
                 f"{elapsed:.1f}s -> {save_path}")

        # Force GC — warmup creates thousands of temp arrays
        # (6-8 per layer per token × 32 layers × 88 tokens ≈ 17,000 temps)
        import gc
        gc.collect()

        return {
            "status": "ok",
            "tokens_processed": processed,
            "total_tokens": n,
            "elapsed": round(elapsed, 2),
            "save_path": save_path,
        }

    def _handle_ping(self, request: Dict) -> Dict:
        return {
            "status": "pong",
            "ts": time.time(),
            "portal_id": self.portal_id,
            "model_loaded": self._model_loaded,
        }

    def _handle_status(self, request: Dict) -> Dict:
        """Full interior status."""
        return {
            "status": "ok",
            "portal_id": self.portal_id,
            "pid": os.getpid(),
            "battery": self.battery.status(),
            "model_loaded": self._model_loaded,
            "requests_processed": self._requests_processed,
            "boot_time_ms": round(self._boot_time * 1000, 1),
            "memory_manager": self._memory_manager.get_stats(),
        }

    def _handle_trim_memory(self, request: Dict) -> Dict:
        """Manually trigger working set trim.

        -> {"cmd": "trim_memory"}
        <- {"status": "ok", "trimmed": true, "freed_mb": 1234.5, ...}
        """
        result = self._memory_manager.trim_working_set()
        result["status"] = "ok"
        return result

    def _handle_set_threads(self, request: Dict) -> Dict:
        """Set OpenMP thread count for parallel C kernels.

        -> {"cmd": "set_threads", "threads": 8}
        <- {"status": "ok", "threads": 8, "procs": 20}

        Controls how many threads the fused AVX2+OpenMP kernels use.
        Optimal: set to physical core count (not hyperthreads).
        The portal dimension controls its own threading — this is the
        gravitational compute engine's parallelism knob.
        """
        try:
            import battery_accel
            n = request.get("threads", 0)
            if n > 0:
                battery_accel.set_threads(n)
            return {
                "status": "ok",
                "threads": battery_accel.get_threads(),
                "procs": battery_accel.get_num_procs(),
                "version": battery_accel._lib.battery_accel_version() if battery_accel._lib else 0,
            }
        except Exception as e:
            return {"status": "error", "message": f"set_threads failed: {e}"}

    def _handle_reset_farm_state(self, request: Dict) -> Dict:
        """Reset all BatteryFarm workers to warm state (personality priming).

        RWKV state accumulates across generations. Each thought leaves residue
        in the hidden state. After many generations, the state drifts into
        degenerate attractors (ellipsis loops, punctuation spam). This command
        reloads the saved warm state into all workers, restoring personality
        priming and clearing accumulated garbage.

        -> {"cmd": "reset_farm_state"}
        <- {"status": "ok", "workers_reset": 16, "warm_path": "..."}

        Call this:
        - After consecutive degenerate outputs (emergency reset)
        - Periodically every N generations (preventive maintenance)
        """
        if not self._farm or not self._farm.workers:
            return {"status": "error", "message": "No farm available"}

        warm_path = str(_HERE / "state" / f"{self.portal_id}_warm_state.npz")
        if not os.path.exists(warm_path):
            # No warm state — reset to cold zeros
            for worker in self._farm.workers:
                worker.engine.init_all_states()
            _log(f"[ComputeInterior] Farm reset to COLD state "
                 f"(no warm state file)")
            return {
                "status": "ok",
                "workers_reset": len(self._farm.workers),
                "state_type": "cold",
            }

        try:
            for worker in self._farm.workers:
                worker.engine.load_state_from_disk(warm_path)
            _log(f"[ComputeInterior] Farm state RESET to warm — "
                 f"{len(self._farm.workers)} workers refreshed")
            return {
                "status": "ok",
                "workers_reset": len(self._farm.workers),
                "state_type": "warm",
                "warm_path": warm_path,
            }
        except Exception as e:
            _log(f"[ComputeInterior] Farm state reset failed: {e}")
            # Fallback: reset to cold zeros
            for worker in self._farm.workers:
                worker.engine.init_all_states()
            return {
                "status": "ok",
                "workers_reset": len(self._farm.workers),
                "state_type": "cold_fallback",
                "error": str(e),
            }

    def _handle_prime_worker(self, request: Dict) -> Dict:
        """Prime a specific worker with predicted conversation context.

        Quantum superposition — each primed worker holds a different possible
        future in its RWKV state. When Ace speaks, the BranchManager collapses
        to the best match, skipping prompt processing for near-instant response.

        Sequence:
        1. Reload warm state for the target worker (personality base)
        2. Prefill prime_tokens through it (topic context on top of personality)
        3. Worker is now primed: personality + predicted conversation direction

        -> {"cmd": "prime_worker", "worker_id": 15, "prime_tokens": [1,2,...],
            "branch_id": "branch_abc123"}
        <- {"status": "ok", "worker_id": 15, "branch_id": "...",
            "tokens_processed": 42}
        """
        if not self._farm or not self._farm.workers:
            return {"status": "error", "message": "No farm available"}

        worker_id = request.get("worker_id", -1)
        prime_tokens = request.get("prime_tokens", [])
        branch_id = request.get("branch_id", "")
        concepts = request.get("concepts", [])

        if worker_id < 0 or worker_id >= len(self._farm.workers):
            return {"status": "error", "message": f"Invalid worker_id {worker_id}"}
        if not prime_tokens:
            return {"status": "error", "message": "No prime_tokens provided"}

        worker = self._farm.workers[worker_id]

        # 1. Reload warm state for this worker (personality base)
        warm_path = str(_HERE / "state" / f"{self.portal_id}_warm_state.npz")
        if os.path.exists(warm_path):
            try:
                worker.engine.load_state_from_disk(warm_path)
            except Exception as e:
                _log(f"[ComputeInterior] Warm state reload failed for worker {worker_id}: {e}")
                worker.engine.init_all_states()
        else:
            worker.engine.init_all_states()

        # 2. Prefill prime_tokens (topic context on top of personality)
        result = self._farm.prime_specific_worker(
            worker_id=worker_id,
            prime_tokens=prime_tokens,
            branch_id=branch_id,
            concepts=concepts,
        )

        if result.get("status") == "ok":
            _log(f"[ComputeInterior] Worker {worker_id} PRIMED: "
                 f"{result['tokens_processed']}/{len(prime_tokens)} tokens, "
                 f"branch={branch_id[:12]}, {result['elapsed']:.2f}s")

        return result

    def _handle_generate_from_worker(self, request: Dict) -> Dict:
        """Generate from a specific pre-primed worker (branch collapse).

        When Ace speaks and the BranchManager finds a matching primed branch,
        this handler generates from that worker's pre-primed RWKV state.
        The prompt here is SHORT (just Ace's actual words), because the
        full conversation context is already in the worker's hidden state.

        Falls through to normal relay if the specific worker depletes.

        -> {"cmd": "generate_from_worker", "worker_id": 15,
            "prompt": [1,2,3], "max_tokens": 20}
        <- Same format as generate_farm, with extra "from_branch" field
        """
        if not self._farm or not self._farm.workers:
            return {"status": "error", "message": "No farm available"}

        worker_id = request.get("worker_id", -1)
        prompt = request.get("prompt", [])
        max_tokens = request.get("max_tokens", 20)

        if worker_id < 0 or worker_id >= len(self._farm.workers):
            return {"status": "error", "message": f"Invalid worker_id {worker_id}"}

        _log(f"[ComputeInterior] Generating from PRIMED worker {worker_id} "
             f"({len(prompt)} continuation tokens, max {max_tokens} gen)")

        result = self._farm.generate_from_specific(
            worker_id=worker_id,
            prompt_tokens=prompt,
            max_tokens=max_tokens,
            temperature=request.get("temperature", 1.0),
            top_k=request.get("top_k", 0),
            top_p=request.get("top_p", 0.5),
            repetition_penalty=request.get("repetition_penalty", 1.3),
            presence_penalty=request.get("presence_penalty", 0.4),
            frequency_penalty=request.get("frequency_penalty", 0.4),
            stop_tokens=request.get("stop_tokens", [0, 1]),
        )

        return result

    def _handle_tick(self, request: Dict) -> Dict:
        """Process heartbeat tick."""
        self.battery.tick()
        return {
            "status": "ok",
            "tick": self.battery._tick_count,
            "health": self.battery.health_score,
            "charge": round(self.battery.charge_level, 4),
        }

    def _handle_shutdown(self, request: Dict) -> Dict:
        # Close mmap if portal-backed
        if hasattr(self, '_weight_store') and self._weight_store:
            if hasattr(self._weight_store, 'close_portal'):
                self._weight_store.close_portal()
        self._running = False
        return {"status": "ok", "message": "Shutting down"}

    # ── Main Loop ──

    def run_stdio(self):
        """Run the compute interior reading from stdin, writing to stdout."""
        self._running = True
        _log(f"[ComputeInterior] Entering stdio loop (pid={os.getpid()})")

        # Background tick thread
        tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        tick_thread.start()

        for line in sys.stdin:
            if not self._running:
                break
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.process_request(request)
                sys.stdout.write(json.dumps(response) + '\n')
                sys.stdout.flush()
                if not self._running:
                    break
            except json.JSONDecodeError as e:
                error_resp = {"status": "error", "message": f"JSON parse error: {e}"}
                sys.stdout.write(json.dumps(error_resp) + '\n')
                sys.stdout.flush()
            except Exception as e:
                error_resp = {"status": "error", "message": str(e)}
                sys.stdout.write(json.dumps(error_resp) + '\n')
                sys.stdout.flush()

        _log(f"[ComputeInterior] Stdio loop ended")

    def _tick_loop(self):
        """Background heartbeat."""
        while self._running:
            try:
                time.sleep(1.0)
                if self.battery:
                    self.battery.tick()
            except Exception:
                pass

    def shutdown(self):
        """Graceful shutdown — closes inner accel portal first."""
        _log(f"[ComputeInterior] Shutting down...")
        self._running = False

        # Close inner accel portal first (TARDIS within TARDIS unfolding)
        if self._accel_gate:
            try:
                _log(f"[ComputeInterior] Closing inner accel portal...")
                self._accel_gate.close()
                self._accel_gate = None
                _log(f"[ComputeInterior] Inner accel portal closed")
            except Exception as e:
                _log(f"[ComputeInterior] Inner accel portal close error: {e}")

        # Save state if engine is loaded
        if self.engine:
            try:
                state_dir = _HERE / "state"
                state_dir.mkdir(exist_ok=True)
                state_path = str(state_dir / f"{self.portal_id}_rwkv_state.npz")
                self.engine.save_state_to_disk(state_path)
                _log(f"[ComputeInterior] State saved to {state_path}")
            except Exception as e:
                _log(f"[ComputeInterior] State save failed: {e}")

        _log(f"[ComputeInterior] Offline. Processed {self._requests_processed} requests.")


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE GATE — Host-side bridge (extends PortalGate pattern)
# ═══════════════════════════════════════════════════════════════════════════════

class ComputePortalGate:
    """Host-side gate for spawning and communicating with a compute portal.

    Same pattern as PortalGate but spawns portal_compute_interior.py
    and adds compute-aware convenience methods.
    """

    def __init__(
        self,
        portal_id: str = "compute",
        flops_budget: int = 500_000_000,
        python_exe: str = None,
        num_farm_workers: int = 4,
        extra_args: list = None,
    ):
        self.portal_id = portal_id
        self.flops_budget = flops_budget
        self.python_exe = python_exe or sys.executable
        self.num_farm_workers = num_farm_workers
        self._extra_args = extra_args or []

        self._process = None
        self._lock = threading.Lock()
        self._is_open = False

        self._requests_sent = 0
        self._errors = 0
        self._opened_at = 0.0
        self._last_response_time = 0.0

        self._stderr_thread = None
        self._interior_script = str(_HERE / "portal_compute_interior.py")

        # FIX 2026-03-10 (Nous): Persistent stdout reader + queue.
        # Same orphan-thread race fix as portal_gate.py.
        self._stdout_queue: queue.Queue = queue.Queue()
        self._stdout_reader_thread = None

    def open(self) -> bool:
        """Open the compute gate — spawn the compute interior subprocess."""
        if self._is_open:
            return True

        cmd = [
            self.python_exe,
            self._interior_script,
            "--portal-id", self.portal_id,
            "--flops-budget", str(self.flops_budget),
            "--farm-workers", str(self.num_farm_workers),
        ] + self._extra_args

        _log(f"[ComputeGate] Opening compute portal '{self.portal_id}'...")

        try:
            env = os.environ.copy()
            # Ensure the parent directory is in PYTHONPATH
            env_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(_HERE.parent) + (os.pathsep + env_path if env_path else "")
            # Force unbuffered I/O — fixes Windows text-mode pipe buffering
            # where readline() blocks even after the subprocess calls flush()
            env["PYTHONUNBUFFERED"] = "1"

            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=1,
                text=True,
            )
        except Exception as e:
            _log(f"[ComputeGate] Failed to spawn interior: {e}")
            return False

        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True
        )
        self._stderr_thread.start()

        # Start persistent stdout reader (drains into queue)
        # FIX 2026-03-10 (Nous): Same fix as portal_gate.py
        self._stdout_queue = queue.Queue()
        self._stdout_reader_thread = threading.Thread(
            target=self._read_stdout_loop, daemon=True
        )
        self._stdout_reader_thread.start()

        time.sleep(1.0)
        ping_result = self.send({"cmd": "ping"}, timeout=30.0)

        if ping_result and ping_result.get("status") == "pong":
            self._is_open = True
            self._opened_at = time.time()
            _log(f"[ComputeGate] Compute portal '{self.portal_id}' ONLINE")
            return True
        else:
            _log(f"[ComputeGate] Portal failed to respond to ping: {ping_result}")
            self.close()
            return False

    def close(self):
        """Close the compute gate."""
        if not self._process:
            return

        try:
            self.send({"cmd": "shutdown"}, timeout=5.0)
        except:
            pass

        try:
            self._process.wait(timeout=5.0)
        except:
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except:
                self._process.kill()

        self._process = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if not self._is_open or not self._process:
            return False
        if self._process.poll() is not None:
            self._is_open = False
            return False
        return True

    def send(self, request: Dict, timeout: float = 10.0) -> Optional[Dict]:
        """Send request and wait for response."""
        if not self._process or self._process.poll() is not None:
            _log(f"[ComputeGate] send() ABORT: process={self._process}, poll={self._process.poll() if self._process else 'N/A'}")
            return None

        self._requests_sent += 1
        t0 = time.time()
        cmd = request.get("cmd", "?")

        try:
            with self._lock:
                line = json.dumps(request) + '\n'
                self._process.stdin.write(line)
                self._process.stdin.flush()

                response_line = self._read_with_timeout(timeout)
                elapsed = time.time() - t0
                if response_line:
                    self._last_response_time = elapsed
                    try:
                        parsed = json.loads(response_line)
                        return parsed
                    except json.JSONDecodeError as je:
                        _log(f"[ComputeGate] JSON PARSE FAIL for {cmd}: {je}\n  raw line: {response_line[:200]!r}")
                        self._errors += 1
                        return None
                else:
                    self._errors += 1
                    _log(f"[ComputeGate] send({cmd}) got EMPTY response after {elapsed:.1f}s (timeout={timeout})")
                    return None
        except Exception as e:
            self._errors += 1
            _log(f"[ComputeGate] send({cmd}) EXCEPTION: {type(e).__name__}: {e}")
            return None

    def _read_stdout_loop(self):
        """Persistent background thread: reads stdout lines into queue.

        FIX 2026-03-10 (Nous): Same fix as portal_gate.py.
        """
        try:
            while self._process and self._process.poll() is None:
                try:
                    line = self._process.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        if line.startswith('{'):
                            self._stdout_queue.put(line)
                        else:
                            _log(f"[ComputeGate:{self.portal_id}] "
                                 f"Non-JSON on stdout (skipped): {line[:80]!r}")
                except (ValueError, OSError):
                    break
        except Exception:
            pass

    def _read_with_timeout(self, timeout: float) -> Optional[str]:
        """FIX 2026-03-10 (Nous): Queue-based, no orphan threads."""
        try:
            return self._stdout_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _read_stderr(self):
        try:
            for line in self._process.stderr:
                if line.strip():
                    # MUST go to stderr — stdout is the JSON protocol pipe!
                    # If we print() to stdout here while inside a nested portal,
                    # the log lines contaminate the parent's JSON response stream.
                    print(f"  [Compute] {line.strip()}", file=sys.stderr, flush=True)
        except:
            pass

    # ── Compute Convenience Methods ──

    def load_model(self, model_path: str, fmt: str = "safetensors",
                   timeout: float = 300.0) -> Optional[Dict]:
        """Load RWKV model into the portal."""
        return self.send({
            "cmd": "load_model",
            "model_path": model_path,
            "format": fmt,
        }, timeout=timeout)

    def generate_one(self, prompt: List[int], temperature: float = 0.8,
                     top_k: int = 50) -> Optional[Dict]:
        """Generate one token from a prompt."""
        return self.send({
            "cmd": "generate_one",
            "prompt": prompt,
            "temperature": temperature,
            "top_k": top_k,
        }, timeout=30.0)

    def generate_stream(self, prompt: List[int], max_tokens: int = 50,
                        temperature: float = 0.8) -> Optional[Dict]:
        """Generate tokens until battery depleted or max reached."""
        return self.send({
            "cmd": "generate_stream",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }, timeout=120.0)

    def feed_energy(self, amount: float = 0.1) -> Optional[Dict]:
        """Feed energy to the portal."""
        return self.send({"cmd": "energy", "amount": amount})

    def compute_status(self) -> Optional[Dict]:
        """Get compute status."""
        return self.send({"cmd": "compute_status"})

    def engine_status(self) -> Optional[Dict]:
        """Get engine status."""
        return self.send({"cmd": "engine_status"})

    def set_somatic(self, **kwargs) -> Optional[Dict]:
        """Set somatic modulation (arousal, stress, valence, etc)."""
        request = {"cmd": "set_somatic"}
        request.update(kwargs)
        return self.send(request)

    def save_state(self, path: str = "") -> Optional[Dict]:
        """Save RWKV state to disk."""
        return self.send({"cmd": "save_state", "path": path})

    def load_state(self, path: str) -> Optional[Dict]:
        """Load RWKV state from disk."""
        return self.send({"cmd": "load_state", "path": path})

    def tick(self) -> Optional[Dict]:
        """Send heartbeat tick."""
        return self.send({"cmd": "tick"})

    def ping(self) -> Optional[Dict]:
        """Ping the interior."""
        return self.send({"cmd": "ping"})

    def status(self) -> Optional[Dict]:
        """Get full status."""
        return self.send({"cmd": "status"})

    def gate_status(self) -> Dict[str, Any]:
        """Status of the gate itself."""
        return {
            "portal_id": self.portal_id,
            "is_open": self.is_open,
            "requests_sent": self._requests_sent,
            "errors": self._errors,
            "last_response_ms": round(self._last_response_time * 1000, 1),
            "uptime_seconds": round(time.time() - self._opened_at, 1) if self._opened_at else 0,
            "interior_pid": self._process.pid if self._process else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI — Run as subprocess or test
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Entry point when run as a subprocess or standalone.

    Usage:
        python portal_compute_interior.py --portal-id compute
        python portal_compute_interior.py --portal-id compute --flops-budget 1000000000
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Portal Compute Interior — Battery-Powered Thinking Room"
    )
    parser.add_argument("--portal-id", default="compute",
                        help="Portal identifier")
    parser.add_argument("--flops-budget", type=int, default=500_000_000,
                        help="FLOPS budget per full charge (default: 500M)")
    parser.add_argument("--farm-workers", type=int, default=8,
                        help="Number of farm workers for relay generation (default: 8)")
    parser.add_argument("--farm-max-charge", type=float, default=20.0,
                        help="Max charge per farm worker (default: 20.0)")
    parser.add_argument("--farm-flops-gravity", type=float, default=1.5,
                        help="FLOPS gravity coefficient (default: 1.5)")
    parser.add_argument("--state-dtype", choices=["float32", "float64"],
                        default="float64",
                        help="RWKV state dtype: float64 for deep/precise, "
                             "float32 for C/AVX2 accelerated speed (default: float64)")
    parser.add_argument("--no-inner-accel", action="store_true",
                        help="Disable inner accelerated sub-portal (prevents recursion)")

    args = parser.parse_args()

    import numpy as np
    _dtype_map = {"float32": np.float32, "float64": np.float64}

    portal = PortalComputeInterior(
        portal_id=args.portal_id,
        flops_budget=args.flops_budget,
        num_farm_workers=args.farm_workers,
        farm_max_charge=args.farm_max_charge,
        farm_flops_gravity_coeff=args.farm_flops_gravity,
        state_dtype=_dtype_map[args.state_dtype],
        allow_inner_accel=not args.no_inner_accel,
    )

    if not portal.boot():
        print("FATAL: Boot failed", file=sys.stderr)
        sys.exit(1)

    try:
        portal.run_stdio()
    except KeyboardInterrupt:
        pass
    finally:
        portal.shutdown()


if __name__ == "__main__":
    main()
