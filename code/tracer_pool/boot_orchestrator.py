"""
Go-powered boot orchestrator for concurrent fairy booting.

Replaces Python's GIL-limited ThreadPoolExecutor with Go goroutines
for true parallel fairy boot. Each fairy boots in its own goroutine —
no GIL contention between fairies.

Go handles: scheduling, concurrency, timeouts, progress tracking.
Python handles: actual fairy __init__() and on_boot() calls.

Architecture:
    Python (server.py)
        → GoBootOrchestrator.boot_all(fairy_specs)
            → Go DLL: BootAllFairies(specs_json)
                → N goroutines, each calls C callback
                    → Python: _boot_fairy_callback(name, path, plane)
                        → directory.wake_fairy(name)
            → Go DLL returns results JSON
        → Python processes results, fires callbacks

"When I wake up it doesn't take me 2 to 3 minutes. I just wake up
 and start moving." — Ace
"""
import ctypes
import json
import os
import sys
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


# ============================================================================
# C callback types matching Go bridge.go
# ============================================================================

# BootFairyCallback: int (name, path, plane, error_out, error_buf_size)
#   Returns 0 on success, non-zero on failure
BOOT_FAIRY_CALLBACK = ctypes.CFUNCTYPE(
    ctypes.c_int,       # return: 0=success, else failure
    ctypes.c_char_p,    # name
    ctypes.c_char_p,    # path
    ctypes.c_char_p,    # plane
    ctypes.c_char_p,    # error_out buffer
    ctypes.c_int,       # error_buf_size
)

# BootProgressCallback: void (total, completed, succeeded, failed)
BOOT_PROGRESS_CALLBACK = ctypes.CFUNCTYPE(
    None,               # void return
    ctypes.c_int,       # total
    ctypes.c_int,       # completed
    ctypes.c_int,       # succeeded
    ctypes.c_int,       # failed
)


# ============================================================================
# Data types
# ============================================================================

@dataclass
class FairySpec:
    """Specification for a fairy to boot."""
    name: str
    plane: str
    path: str = ""
    priority: int = 1    # 0=high, 1=normal, 2=low
    heavy: bool = False   # True = known to be slow (model loading etc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "plane": self.plane,
            "path": self.path,
            "priority": self.priority,
            "heavy": self.heavy,
        }


@dataclass
class FairyResult:
    """Result of booting a single fairy."""
    name: str
    plane: str
    ok: bool
    error: str = ""
    duration_ms: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0


@dataclass
class BootResult:
    """Aggregate result of booting all fairies."""
    total_fairies: int = 0
    succeeded: int = 0
    failed: int = 0
    timedout: int = 0
    total_ms: float = 0.0
    slowest_fairy: str = ""
    slowest_ms: float = 0.0
    plane_results: Dict[str, int] = field(default_factory=dict)
    fairy_results: List[FairyResult] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "BootResult":
        fairy_results = []
        for fr in data.get("fairy_results", []):
            fairy_results.append(FairyResult(
                name=fr.get("name", ""),
                plane=fr.get("plane", ""),
                ok=fr.get("ok", False),
                error=fr.get("error", ""),
                duration_ms=fr.get("duration_ms", 0.0),
                started_at=fr.get("started_at", 0.0),
                finished_at=fr.get("finished_at", 0.0),
            ))
        return cls(
            total_fairies=data.get("total_fairies", 0),
            succeeded=data.get("succeeded", 0),
            failed=data.get("failed", 0),
            timedout=data.get("timedout", 0),
            total_ms=data.get("total_ms", 0.0),
            slowest_fairy=data.get("slowest_fairy", ""),
            slowest_ms=data.get("slowest_ms", 0.0),
            plane_results=data.get("plane_results", {}),
            fairy_results=fairy_results,
        )


# ============================================================================
# Heavy fairy detection
# ============================================================================

# Fairies known to load models or do heavy init
HEAVY_FAIRIES = {
    "AkashicInferenceFairy",
    "NousFairy",
    "SourpatchesFairy",
    "QuantumSearchFairy",
    "ThoughtChainEngineFairy",
    "DynamicThinkingOrchestratorFairy",
    "CognitionTeamFairy",
    "SomaticAvatarFairy",
}

# High priority fairies (boot first — infrastructure + memory pipeline)
# Memory fairies MUST boot before waking minds (Sourpatches, Nous) so they
# have memories to think with. The consciousness loop needs memories to collide.
# Priority order within HIGH: infrastructure → memory pipeline → gates
HIGH_PRIORITY_FAIRIES = {
    # Infrastructure (boot backbone)
    "UnconsciousMindFairy",
    "ConsciousnessLoopFairy",
    "WorkingMemoryHubFairy",
    "DirectoryFairy",
    "PostalCoreFairy",
    "CirculationPumpFairy",
    # Memory pipeline (feeds consciousness with memories to collide)
    "SRMIngestFairy",
    "SRMRecallFairy",
    "CollisionChamberFairy",
    "AssociationCortexFairy",
    # Three Gates (route signals to waking minds)
    "AutonomyFairy",
    "AutopilotFairy",
    "EmbodimentFairy",
}


def classify_fairy(name: str) -> Tuple[int, bool]:
    """Classify a fairy into priority and heavy flag."""
    priority = 1  # Normal
    heavy = name in HEAVY_FAIRIES

    if name in HIGH_PRIORITY_FAIRIES:
        priority = 0  # High
    elif heavy:
        priority = 2  # Low (let light fairies boot first)

    return priority, heavy


# ============================================================================
# GoBootOrchestrator
# ============================================================================

class GoBootOrchestrator:
    """
    Go-powered concurrent boot orchestrator.

    Drop-in replacement for BootOrchestrator (from SomaticMindFairy/boot/).
    Uses Go goroutines via the tracer_pool.dll for true parallel boot.

    Usage:
        orchestrator = GoBootOrchestrator(
            fabric=SYSTEM.fabric,
            directory=SYSTEM.directory,
            on_plane_complete=my_callback,
            on_boot_complete=my_callback,
        )
        orchestrator.start()
    """

    PLANES = ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]

    # Planes that boot inside portals (subprocesses) instead of in-process.
    # These are SKIPPED by _build_fairy_specs(). The server opens PlanePortalGates for them.
    # Build outside-in: start with P60, then P50+P60, then P40+P50+P60, etc.
    # Dict format: plane_code -> {"mode": "full"|"partial", "exclude": [...]}
    #   "full": entire plane boots in portal (skip all fairies)
    #   "partial": some fairies stay in main process, rest go to portal
    #              "exclude" lists dir patterns that STAY (everything else goes to portal)
    PORTAL_PLANES: dict = {}  # Populated by server.py before start()

    def __init__(
        self,
        fabric,
        directory,
        on_plane_complete: Optional[Callable[[str], None]] = None,
        on_boot_complete: Optional[Callable[[], None]] = None,
        max_concurrent: int = 0,           # 0 = unlimited goroutines
        per_fairy_timeout_ms: int = 60000,  # 60s per fairy
        global_timeout_ms: int = 180000,    # 180s global (3 min)
        timing_state=None,                  # BootTimingState from ProfileRecaller
    ):
        self.fabric = fabric
        self.directory = directory
        self._on_plane_complete = on_plane_complete
        self._on_boot_complete = on_boot_complete
        self._max_concurrent = max_concurrent
        self._per_fairy_timeout_ms = per_fairy_timeout_ms
        self._global_timeout_ms = global_timeout_ms

        # Boot timing learner (self-regulating boot performance)
        self._timing_state = timing_state
        self._init_timings: Dict[str, float] = {}  # Phase 1 per-fairy init timing (ms)

        # State
        self._booting = False
        self._boot_start = 0.0
        self._boot_result: Optional[BootResult] = None
        self.is_complete = False

        # Per-plane tracking (for backward compatibility)
        self._woken_fairies: Dict[str, List[str]] = {p: [] for p in self.PLANES}
        self._failed_fairies: List[str] = []
        self._planes_complete: Dict[str, bool] = {p: False for p in self.PLANES}
        self._plane_times: Dict[str, float] = {}

        # Progress tracking (updated by Go callback)
        self._progress_total = 0
        self._progress_completed = 0
        self._progress_succeeded = 0
        self._progress_failed = 0

        # Boot skip registry (fail-fast for known failures)
        try:
            from state.boot_skip_registry import boot_skip_registry
            self._skip_registry = boot_skip_registry
        except ImportError:
            self._skip_registry = None

        # Load Go DLL
        self._lib = self._load_dll()
        self._go_available = self._lib is not None

        # Keep callback references alive (prevent GC)
        self._boot_cb_ref = None
        self._progress_cb_ref = None

    def _load_dll(self) -> Optional[ctypes.CDLL]:
        """Load the tracer_pool DLL with boot orchestrator support."""
        dll_path = Path(__file__).parent / "tracer_pool.dll"
        if not dll_path.exists():
            print(f"[GoBootOrch] DLL not found at {dll_path}, falling back to Python threading")
            return None

        try:
            lib = ctypes.CDLL(str(dll_path))
            self._setup_argtypes(lib)

            # Initialize boot orchestrator in Go
            lib.BootOrchestratorInit(
                ctypes.c_int(self._max_concurrent),
                ctypes.c_int(self._per_fairy_timeout_ms),
                ctypes.c_int(self._global_timeout_ms),
            )
            print(f"[GoBootOrch] Go DLL loaded OK ({dll_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return lib
        except (OSError, AttributeError) as e:
            print(f"[GoBootOrch] DLL load failed: {e}, falling back to Python threading")
            return None

    def _setup_argtypes(self, lib: ctypes.CDLL):
        """Set up ctypes function signatures for boot functions."""
        lib.BootOrchestratorInit.restype = ctypes.c_int
        lib.BootOrchestratorInit.argtypes = [
            ctypes.c_int,  # maxConcurrent
            ctypes.c_int,  # perFairyTimeoutMs
            ctypes.c_int,  # globalTimeoutMs
        ]

        lib.BootSetCallback.restype = ctypes.c_int
        lib.BootSetCallback.argtypes = [
            BOOT_FAIRY_CALLBACK,      # boot fairy callback
            BOOT_PROGRESS_CALLBACK,   # progress callback
        ]

        lib.BootAllFairies.restype = ctypes.c_char_p
        lib.BootAllFairies.argtypes = [ctypes.c_char_p]  # specs JSON

        lib.BootGetProgress.restype = ctypes.c_char_p
        lib.BootGetProgress.argtypes = []

        lib.BootIsRunning.restype = ctypes.c_int
        lib.BootIsRunning.argtypes = []

        # FreeString already set up by tracer_pool
        try:
            lib.FreeString.restype = None
            lib.FreeString.argtypes = [ctypes.c_char_p]
        except AttributeError:
            pass

    def _make_boot_callback(self):
        """Create the C callback that Go calls to boot each fairy.

        HYBRID DESIGN (2026-02-15):
        By the time Go calls this, all fairies have ALREADY been imported
        and instantiated by Python threads (_pre_instantiate_all).
        This callback just does wake_fairy() → on_boot() — LIGHTWEIGHT.
        No importlib, no module compilation, no heavy Python stack work.
        Safe to call from Go goroutine stacks.
        """
        def _boot_fairy(name_ptr, path_ptr, plane_ptr, error_out, error_buf_size):
            try:
                name = name_ptr.decode('utf-8') if name_ptr else ""
                plane = plane_ptr.decode('utf-8') if plane_ptr else ""

                # All fairies should be pre-instantiated by now
                # Just wake (on_boot) — lightweight, no importlib
                result = self.directory.wake_fairy(name)

                if result and result.get("ok"):
                    if plane in self._woken_fairies:
                        self._woken_fairies[plane].append(name)
                    return 0  # Success
                else:
                    error = result.get("error", "unknown error") if result else "wake_fairy returned None"
                    self._failed_fairies.append(name)
                    error_bytes = error.encode('utf-8')[:error_buf_size - 1]
                    ctypes.memmove(error_out, error_bytes, len(error_bytes))
                    ctypes.memset(
                        ctypes.cast(error_out, ctypes.c_void_p).value + len(error_bytes),
                        0, 1
                    )
                    return 1

            except Exception as e:
                self._failed_fairies.append(name if name_ptr else "unknown")
                error_msg = f"{type(e).__name__}: {e}"
                error_bytes = error_msg.encode('utf-8')[:error_buf_size - 1]
                ctypes.memmove(error_out, error_bytes, len(error_bytes))
                ctypes.memset(
                    ctypes.cast(error_out, ctypes.c_void_p).value + len(error_bytes),
                    0, 1
                )
                return 1

        return BOOT_FAIRY_CALLBACK(_boot_fairy)

    def _instantiate_and_boot_fairy(self, name: str, record) -> Dict[str, Any]:
        """
        Single-pass: import + __init__ + on_boot for a fairy that only has specs.

        This replaces the old 2-pass flow:
        - OLD: FairyScanner.instantiate_fairy() (import+init) -> GoBootOrch.wake_fairy() (on_boot)
        - NEW: GoBootOrch._instantiate_and_boot_fairy() does import -> init -> boot in one call

        After instantiation, delegates to directory.wake_fairy() for the actual
        boot + event publishing (fairy.wake, fairy.booted, etc.)

        Args:
            name: Fairy actor name
            record: FairyRecord from directory with metadata (source_file, class_name)

        Returns:
            {"ok": True/False, "name": name, ...}
        """
        import importlib.util
        import inspect

        source_file = record.metadata.get("source_file", "")
        class_name = record.metadata.get("class_name", "") or name

        if not source_file or not Path(source_file).exists():
            return {"ok": False, "name": name, "error": f"Source file not found: {source_file}"}

        try:
            # Phase A: Dynamic import
            module_name = f"fairy_dynamic_{class_name}"
            spec = importlib.util.spec_from_file_location(module_name, source_file)
            if not spec or not spec.loader:
                return {"ok": False, "name": name, "error": "Could not create import spec"}

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module  # Register BEFORE exec for @dataclass
            spec.loader.exec_module(module)

            # Find the class
            fairy_class = getattr(module, class_name, None)
            if not fairy_class or not inspect.isclass(fairy_class):
                return {"ok": False, "name": name, "error": f"Class {class_name} not found in module"}

            # Phase B: Instantiate (__init__) with fabric
            instance = None
            _last_init_error = None

            # Try different constructor signatures
            # FIX 2026-02-23: Added post= trial for organ-template fairies,
            # and catch Exception (not just TypeError) on no-arg trial to avoid
            # swallowing internal errors as "signature mismatch".

            # 1. fabric as keyword arg
            try:
                instance = fairy_class(fabric=self.fabric)
            except TypeError:
                pass

            # 2. fabric as positional arg
            if instance is None:
                try:
                    instance = fairy_class(self.fabric)
                except TypeError:
                    pass

            # 3. post= keyword (organ-template Fairy base uses this)
            if instance is None:
                try:
                    instance = fairy_class(post=self.fabric)
                except TypeError:
                    pass

            # 4. no-arg constructor, wire fabric after
            if instance is None:
                try:
                    instance = fairy_class()
                    if hasattr(instance, "fabric"):
                        instance.fabric = self.fabric
                    if hasattr(instance, "post") and instance.post is None:
                        instance.post = self.fabric
                    if hasattr(instance, "_post") and instance._post is None:
                        instance._post = self.fabric
                except TypeError as te:
                    _last_init_error = f"All constructor signatures failed (no-arg TypeError: {te})"
                except Exception as e:
                    _last_init_error = f"No-arg constructor exception: {type(e).__name__}: {e}"

            if instance is None and _last_init_error:
                return {"ok": False, "name": name, "error": _last_init_error}

            if not instance:
                return {"ok": False, "name": name, "error": "Instantiation returned None"}

            # Re-wire internal hub/registration fabric refs
            if hasattr(instance, "hub") and hasattr(getattr(instance, "hub", None), "fabric"):
                instance.hub.fabric = self.fabric
            if hasattr(instance, "registration") and hasattr(getattr(instance, "registration", None), "fabric"):
                instance.registration.fabric = self.fabric

            # Store instance in directory so wake_fairy() can find it
            record.metadata["fairy_instance"] = instance
            record.metadata["needs_instantiation"] = False

            # Phase C: Delegate to directory.wake_fairy() for boot + event publishing
            # This handles: fairy.wake event -> boot()/on_boot() -> fairy.booted event -> status="running"
            return self.directory.wake_fairy(name)

        except Exception as e:
            try:
                self.directory.registry.set_status(name, "failed")
            except Exception:
                pass
            return {"ok": False, "name": name, "error": f"{type(e).__name__}: {e}"}

    def _make_progress_callback(self):
        """Create the C callback for progress updates."""
        def _progress(total, completed, succeeded, failed):
            self._progress_total = total
            self._progress_completed = completed
            self._progress_succeeded = succeeded
            self._progress_failed = failed

            # Print progress every 10 fairies
            if completed > 0 and (completed % 10 == 0 or completed == total):
                pct = (completed / total * 100) if total > 0 else 0
                print(
                    f"[GoBootOrch] Progress: {completed}/{total} "
                    f"({pct:.0f}%) — {succeeded} ok, {failed} failed"
                )

        return BOOT_PROGRESS_CALLBACK(_progress)

    def start(self) -> Dict[str, Any]:
        """
        Begin concurrent boot — all fairies wake simultaneously.

        Compatible with BootOrchestrator.start() API.
        """
        if self._booting:
            return {"ok": False, "error": "already booting"}

        self._booting = True
        self._boot_start = time.time()

        # ═══════════════════════════════════════════════════════════════════
        # WAKE CHEMISTRY — Start asleep, then cascade to full alertness
        # ═══════════════════════════════════════════════════════════════════
        # "when the system is waking up, the chemicals that keep a human
        #  asleep would be what she starts with and then shifts to the
        #  chemicals that keep us awake" — Ace, 2026-03-17
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            _chem = get_chemistry_state()
            _chem.start_asleep()
            _pub = self.fabric.publish if self.fabric else None
            _chem.wake_cascade(publish_fn=_pub)
            print("[GoBootOrch] Wake chemistry cascade initiated — waking up over 60s")
        except Exception as _wce:
            print(f"[GoBootOrch] Wake chemistry failed (non-fatal): {_wce}")

        # Publish boot start event
        if self.fabric:
            try:
                self.fabric.publish("boot.start", {
                    "mode": "hybrid_go" if self._go_available else "hybrid_python",
                    "timestamp": self._boot_start,
                })
            except Exception:
                pass

        mode = "hybrid_go" if self._go_available else "hybrid_python"
        print(f"[GoBootOrch] start() called — mode={mode}, go_available={self._go_available}")

        # Run boot in background thread (so server.py can continue)
        boot_thread = threading.Thread(
            target=self._run_boot,
            name="go-boot-orchestrator",
            daemon=True,
        )
        boot_thread.start()

        return {"ok": True, "plane": "ALL", "mode": mode}

    # Plane wave configuration: stagger boot to prevent thread explosion.
    # Each wave boots its planes, then waits for daemon threads to settle
    # before starting the next wave. This keeps peak thread count low.
    BOOT_WAVES = [
        # Wave 1: Infrastructure — must be stable before anything else
        {"planes": ["P00"], "settle_s": 1.5, "label": "Infrastructure"},
        # Wave 2: Memory + Somatic — foundational services
        {"planes": ["P10", "P20"], "settle_s": 1.5, "label": "Memory+Somatic"},
        # Wave 3: Cognition — heaviest plane (~18 fairies, many spawn threads)
        {"planes": ["P30"], "settle_s": 2.0, "label": "Cognition"},
        # Wave 4: Sensory + Persona + Executive — lighter, can overlap
        {"planes": ["P40", "P50", "P60"], "settle_s": 0.5, "label": "Sensory+Persona+Executive"},
    ]

    def _run_boot(self):
        """Execute the boot sequence — FLAT PARALLEL, Go-first.

        FLAT DESIGN (2026-02-26):
        Boot ALL fairies in a single parallel pass. No wave staggering.
        Each fairy has its own postal channel — nobody talks on the same
        channel — so concurrent boot is safe. The wave-staggered design
        (2026-02-23) was a Python thread workaround, but Go goroutines
        don't have that problem: they're lightweight green threads that
        don't touch the GIL.

        TWO-PHASE HYBRID:
          Phase 1 (Python threads): Import modules + __init__()
            - Must be Python — importlib needs proper Python stack frames
            - ThreadPoolExecutor capped at 16 workers
          Phase 2 (Go goroutines OR Python threads): on_boot() calls
            - Go-first: goroutines via tracer_pool.dll (true parallel)
            - Python fallback: ThreadPoolExecutor when DLL unavailable
            - on_boot() is lightweight wiring — no importlib needed
        """
        try:
            # Build all specs upfront
            all_specs = self._build_fairy_specs()
            if not all_specs:
                print("[GoBootOrch] No fairies to boot!")
                return

            import threading as _thr
            thread_count = _thr.active_count()
            go_label = "GO GOROUTINES" if self._go_available else "PYTHON THREADS"
            print(f"\n[GoBootOrch] === FLAT PARALLEL BOOT: {len(all_specs)} fairies, "
                  f"{thread_count} threads, Phase 2 via {go_label} ===")

            # Phase 1: Pre-instantiate ALL fairies (Python threads — importlib)
            needs_inst = [s for s in all_specs if self._spec_needs_instantiation(s)]
            if needs_inst:
                self._pre_instantiate_all(needs_inst)

            # Phase 2: on_boot() calls — Go goroutines when available
            thread_count = _thr.active_count()
            if thread_count > 200:
                print(f"[GoBootOrch]   WARNING: {thread_count} threads active before Phase 2")

            if self._go_available:
                self._run_go_boot_with_specs(all_specs)
            else:
                print("[GoBootOrch]   Go DLL not available, using Python thread pool")
                self._run_python_boot_with_specs(all_specs)

            # Final thread diagnostic
            final_threads = _thr.active_count()
            total_booted = sum(len(v) for v in self._woken_fairies.values())
            print(f"\n[GoBootOrch] --- BOOT COMPLETE ---")
            print(f"[GoBootOrch]   Fairies booted: {total_booted}/{len(all_specs)}")
            print(f"[GoBootOrch]   Failed: {len(self._failed_fairies)}")
            print(f"[GoBootOrch]   Final thread count: {final_threads}")
            if final_threads > 200:
                print(f"[GoBootOrch]   WARNING: High thread count — sample:")
                for t in sorted(_thr.enumerate(), key=lambda x: x.name)[:30]:
                    print(f"[GoBootOrch]     {t.name} (daemon={t.daemon})")

        except Exception as e:
            print(f"[GoBootOrch] BOOT FAILED: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._finalize_boot()

    def _spec_needs_instantiation(self, spec: FairySpec) -> bool:
        """Check if a fairy spec still needs import+init."""
        try:
            record = self.directory.registry.get(spec.name)
            if not record:
                return False
            return (record.metadata.get("needs_instantiation", False)
                    and not record.metadata.get("fairy_instance"))
        except Exception:
            return False

    def _pre_instantiate_all(self, specs: List[FairySpec]):
        """Phase 1: Import + __init__() all fairies using Python threads.

        This is the HEAVY work — importlib, module compilation, constructor calls.
        Must run on Python threads (not Go goroutines) because importlib needs
        proper Python stack frames.

        After this, every fairy has a fairy_instance in the directory — ready
        for Go to call on_boot() via lightweight wake_fairy().
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        print(f"\n[GoBootOrch] ═══ PHASE 1: PRE-INSTANTIATE ({len(specs)} fairies) ═══")
        print(f"[GoBootOrch] Python threads: import + __init__() (importlib-safe)")
        t0 = time.time()

        # Scale pool to wave size — no point having 32 threads for 5 fairies
        pool_size = min(len(specs), min(16, max(4, os.cpu_count())))
        instantiated = 0
        failed = 0

        # Per-fairy init timing capture (import + __init__ only, no on_boot)
        _fairy_start_times: Dict[str, float] = {}

        with ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="inst") as pool:
            futures = {}
            for spec in specs:
                _fairy_start_times[spec.name] = time.time()
                future = pool.submit(self._instantiate_single_fairy, spec.name)
                futures[future] = spec

            try:
                for future in as_completed(futures, timeout=120):
                    spec = futures[future]
                    try:
                        name, ok, error = future.result(timeout=10)
                        # Capture init timing (import + __init__ phase only)
                        _start = _fairy_start_times.get(name, 0.0)
                        if _start > 0:
                            self._init_timings[name] = (time.time() - _start) * 1000.0
                        if ok:
                            instantiated += 1
                        else:
                            failed += 1
                            print(f"[GoBootOrch]   INIT FAIL: {name}: {error}")
                    except Exception as e:
                        failed += 1
                        print(f"[GoBootOrch]   INIT FAIL: {spec.name}: {type(e).__name__}: {e}")
            except TimeoutError:
                # Identify which fairies are still pending
                pending = [futures[f].name for f in futures if not f.done()]
                timed_out = len(pending)
                failed += timed_out
                print(f"[GoBootOrch] ⚠ Phase 1 TIMEOUT: {timed_out} fairies still pending after 120s:")
                for pname in pending:
                    print(f"[GoBootOrch]   TIMEOUT: {pname}")
                    self._failed_fairies.append(pname)

        elapsed = time.time() - t0
        print(f"[GoBootOrch] Phase 1 done: {instantiated} instantiated, "
              f"{failed} failed ({elapsed:.1f}s)")

    def _instantiate_single_fairy(self, name: str) -> Tuple[str, bool, str]:
        """Import + __init__() a single fairy. Returns (name, ok, error)."""
        try:
            record = self.directory.registry.get(name)
            if not record:
                if self._skip_registry:
                    self._skip_registry.record_failure(name, "Not found in registry")
                return (name, False, "Not found in registry")

            # Already instantiated?
            if record.metadata.get("fairy_instance"):
                return (name, True, "")

            result = self._instantiate_and_boot_fairy_init_only(name, record)
            if result.get("ok"):
                return (name, True, "")
            else:
                error = result.get("error", "unknown")
                source = record.metadata.get("source_file", "")
                if self._skip_registry:
                    self._skip_registry.record_failure(name, f"Init failed: {error}", source_file=source)
                return (name, False, error)
        except Exception as e:
            if self._skip_registry:
                self._skip_registry.record_failure(name, f"{type(e).__name__}: {e}")
            return (name, False, f"{type(e).__name__}: {e}")

    def _instantiate_and_boot_fairy_init_only(self, name: str, record) -> Dict[str, Any]:
        """Import + __init__() ONLY — no on_boot(). Stores instance in directory.

        This is the importlib-heavy work that crashes on Go goroutine stacks.
        After this, the fairy has an instance ready for wake_fairy() → on_boot().
        """
        import importlib.util
        import inspect

        source_file = record.metadata.get("source_file", "")
        class_name = record.metadata.get("class_name", "") or name

        if not source_file or not Path(source_file).exists():
            return {"ok": False, "name": name, "error": f"Source file not found: {source_file}"}

        try:
            # Dynamic import
            module_name = f"fairy_dynamic_{class_name}"
            spec = importlib.util.spec_from_file_location(module_name, source_file)
            if not spec or not spec.loader:
                return {"ok": False, "name": name, "error": "Could not create import spec"}

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module  # Register BEFORE exec for @dataclass
            spec.loader.exec_module(module)

            # Find the class
            fairy_class = getattr(module, class_name, None)
            if not fairy_class or not inspect.isclass(fairy_class):
                return {"ok": False, "name": name, "error": f"Class {class_name} not found in module"}

            # Instantiate (__init__) with fabric — try 4 signatures
            # FIX 2026-02-23: Added post= trial, better error reporting
            instance = None
            _last_init_error = None
            try:
                instance = fairy_class(fabric=self.fabric)
            except TypeError:
                pass
            if instance is None:
                try:
                    instance = fairy_class(self.fabric)
                except TypeError:
                    pass
            if instance is None:
                try:
                    instance = fairy_class(post=self.fabric)
                except TypeError:
                    pass
            if instance is None:
                try:
                    instance = fairy_class()
                    if hasattr(instance, "fabric"):
                        instance.fabric = self.fabric
                    if hasattr(instance, "post") and instance.post is None:
                        instance.post = self.fabric
                    if hasattr(instance, "_post") and instance._post is None:
                        instance._post = self.fabric
                except TypeError as te:
                    _last_init_error = f"All constructor signatures failed (no-arg TypeError: {te})"
                except Exception as e:
                    _last_init_error = f"No-arg constructor exception: {type(e).__name__}: {e}"
            if instance is None and _last_init_error:
                return {"ok": False, "name": name, "error": _last_init_error}

            if not instance:
                return {"ok": False, "name": name, "error": "Instantiation returned None"}

            # Re-wire internal fabric refs
            if hasattr(instance, "hub") and hasattr(getattr(instance, "hub", None), "fabric"):
                instance.hub.fabric = self.fabric
            if hasattr(instance, "registration") and hasattr(getattr(instance, "registration", None), "fabric"):
                instance.registration.fabric = self.fabric

            # Store instance — ready for wake_fairy() → on_boot()
            record.metadata["fairy_instance"] = instance
            record.metadata["needs_instantiation"] = False

            return {"ok": True, "name": name}

        except Exception as e:
            try:
                self.directory.registry.set_status(name, "failed")
            except Exception:
                pass
            return {"ok": False, "name": name, "error": f"{type(e).__name__}: {e}"}

    def _run_go_boot_with_specs(self, specs: List[FairySpec]):
        """Phase 2: Boot all pre-instantiated fairies via Go goroutines.

        HYBRID DESIGN: By this point, all fairies have been imported and
        instantiated by Python threads (Phase 1). The Go callback just calls
        wake_fairy() → on_boot() — no importlib, safe for Go goroutine stacks.
        """
        print(f"\n[GoBootOrch] ═══ PHASE 2: GO GOROUTINE BOOT ({len(specs)} fairies) ═══")
        print(f"[GoBootOrch] Go goroutines: on_boot() calls (lightweight, no importlib)")

        # Create and register callbacks (MUST keep references alive!)
        self._boot_cb_ref = self._make_boot_callback()
        self._progress_cb_ref = self._make_progress_callback()

        # Register callbacks with Go
        result = self._lib.BootSetCallback(self._boot_cb_ref, self._progress_cb_ref)
        if result != 0:
            print("[GoBootOrch] Failed to set Go callbacks, falling back to Python")
            self._run_python_boot_with_specs(specs)
            return

        # Serialize specs to JSON
        specs_dicts = [s.to_dict() for s in specs]
        specs_json = json.dumps(specs_dicts).encode('utf-8')

        # Launch boot — Go goroutines call _boot_fairy callback for each fairy
        # Each callback does wake_fairy() → on_boot() (lightweight)
        result_ptr = self._lib.BootAllFairies(specs_json)

        if result_ptr:
            result_json = result_ptr.decode('utf-8')
            result_data = json.loads(result_json)

            if "error" in result_data:
                print(f"[GoBootOrch] Boot error: {result_data['error']}")
            else:
                self._boot_result = BootResult.from_json(result_data)
                self._process_results(self._boot_result)

    def _run_python_boot_with_specs(self, specs: List[FairySpec]):
        """Phase 2 fallback: Boot all pre-instantiated fairies via Python threads.

        Same as Go path but uses ThreadPoolExecutor when DLL is unavailable.
        All fairies are already instantiated — just need on_boot().
        """
        print(f"\n[GoBootOrch] ═══ PHASE 2: PYTHON THREAD BOOT ({len(specs)} fairies) ═══")
        print(f"[GoBootOrch] Python threads: on_boot() calls (reusing thread pool)")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # FIX 2026-02-15: Capped from 64 to 16.
        # FIX 2026-02-23: Scale to wave size — no point spinning 16 threads for 3 fairies.
        # With wave-staggered boot, each wave is smaller, so smaller pools are fine.
        pool_size = min(len(specs), min(12, max(4, os.cpu_count())))

        # FIX 2026-02-20: DON'T use `with` block — its __exit__ calls
        # pool.shutdown(wait=True) which blocks until ALL futures complete.
        # If 4 fairies are hung, we'd wait forever. Instead, explicitly
        # shutdown with wait=False after timeout so _finalize_boot() runs
        # and the GUI gets is_complete=True.
        pool = ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="boot")
        futures = {}
        for spec in specs:
            future = pool.submit(self._boot_single_fairy_py, spec)
            futures[future] = spec

        try:
            for future in as_completed(futures, timeout=self._global_timeout_ms / 1000):
                spec = futures[future]
                try:
                    name, ok, error = future.result(timeout=10)
                    if ok:
                        if spec.plane in self._woken_fairies:
                            self._woken_fairies[spec.plane].append(name)
                    else:
                        self._failed_fairies.append(name)
                except Exception as e:
                    self._failed_fairies.append(spec.name)
        except TimeoutError:
            # Identify which fairies are still pending
            pending = [futures[f].name for f in futures if not f.done()]
            timeout_s = self._global_timeout_ms / 1000
            print(f"[GoBootOrch] ⚠ Phase 2 TIMEOUT: {len(pending)} fairies still pending after {timeout_s:.0f}s:")
            for pname in pending:
                print(f"[GoBootOrch]   TIMEOUT (on_boot): {pname}")
                self._failed_fairies.append(pname)
        finally:
            # Don't wait for hung fairies — they'll complete in background
            pool.shutdown(wait=False, cancel_futures=True)
            print(f"[GoBootOrch] Thread pool shutdown (non-blocking, hung fairies continue in background)")

    def _boot_single_fairy_py(self, spec: FairySpec) -> Tuple[str, bool, str]:
        """Boot a single pre-instantiated fairy (Python fallback path).

        All fairies should have instances by now (Phase 1 did import+init).
        Just calls wake_fairy() → on_boot().
        """
        try:
            result = self.directory.wake_fairy(spec.name)
            if result and result.get("ok"):
                return (spec.name, True, "")
            else:
                error = result.get("error", "unknown") if result else "None result"
                return (spec.name, False, error)
        except Exception as e:
            return (spec.name, False, f"{type(e).__name__}: {e}")

    # ── Legacy wrappers for backward compatibility ────────────────────────
    def _run_go_boot(self):
        """Legacy: now delegates to hybrid boot."""
        specs = self._build_fairy_specs()
        if specs:
            needs_inst = [s for s in specs if self._spec_needs_instantiation(s)]
            if needs_inst:
                self._pre_instantiate_all(needs_inst)
            self._run_go_boot_with_specs(specs)

    def _run_python_fallback(self):
        """Legacy: now delegates to hybrid boot."""
        specs = self._build_fairy_specs()
        if specs:
            needs_inst = [s for s in specs if self._spec_needs_instantiation(s)]
            if needs_inst:
                self._pre_instantiate_all(needs_inst)
            self._run_python_boot_with_specs(specs)

    def _build_fairy_specs(self) -> List[FairySpec]:
        """Build list of fairy specs from directory.

        Accepts BOTH:
        - Fairies with fairy_instance (pre-instantiated, just need on_boot)
        - Fairies with needs_instantiation=True (need import + __init__ + on_boot)
        """
        specs = []
        skipped_not_sleeping = 0
        skipped_unbootable = 0
        skipped_known_fail = 0
        total_listed = 0
        needs_inst_count = 0

        # FIX 2026-02-23: Exclude non-fairy classes that get picked up by FairyScanner
        # These have ACTOR_NAME but are not standalone bootable fairies:
        # - Shadow classes: need parent fairy instance, not standalone
        # - Mock/test classes: only for unit tests
        # - Organ template base classes: not meant to be booted directly
        _BOOT_EXCLUDE_NAMES = {
            "my_organ",                           # OrganHubFacet base class
            "organ.clerk.primrose",               # OrganHubFairy (internal registrar)
            "organ_template_seed",                # TemplateSeedFairy (config manager)
            "MockRecallFairy",                    # Test mock class
        }
        _BOOT_EXCLUDE_SUFFIXES = ("Shadow",)      # Shadow classes need parent fairy

        for plane in self.PLANES:
            # Russian Doll: skip planes that boot inside portals
            _portal_cfg = self.PORTAL_PLANES.get(plane)
            if _portal_cfg:
                _portal_mode = _portal_cfg.get("mode", "full") if isinstance(_portal_cfg, dict) else "full"
                _portal_exclude = _portal_cfg.get("exclude", []) if isinstance(_portal_cfg, dict) else []
                if _portal_mode == "full":
                    print(f"[GoBootOrch] Skipping {plane} -- boots inside portal subprocess")
                    self._planes_complete[plane] = True
                    continue
                else:
                    # Partial: some fairies stay, rest go to portal
                    # The exclude list names dir patterns that STAY in main process
                    print(f"[GoBootOrch] Partial portal for {plane} -- "
                          f"only fairies in {_portal_exclude} boot in-process")

            try:
                fairies = self.directory.list_fairies(plane=plane)
            except Exception as e:
                print(f"[GoBootOrch] Failed to list fairies for {plane}: {e}")
                continue

            plane_count = 0
            for fairy in fairies:
                total_listed += 1
                if fairy.status != "sleeping":
                    skipped_not_sleeping += 1
                    continue

                # Skip excluded classes (shadows, mocks, organ templates)
                if fairy.name in _BOOT_EXCLUDE_NAMES or fairy.name.lower().endswith(tuple(x.lower() for x in _BOOT_EXCLUDE_SUFFIXES)):
                    skipped_unbootable += 1
                    continue

                # Russian Doll partial: only boot fairies whose source path
                # matches one of the exclude patterns (those STAY in main process)
                if _portal_cfg and _portal_mode == "partial" and _portal_exclude:
                    _fairy_path = (fairy.metadata.get("source_file", "") or
                                   getattr(fairy, 'path', '') or '')
                    _fairy_stays = False
                    for _excl_pat in _portal_exclude:
                        if _excl_pat in _fairy_path:
                            _fairy_stays = True
                            break
                    if not _fairy_stays:
                        # This fairy goes to the portal, skip it here
                        skipped_unbootable += 1
                        continue

                # Skip known failures (source file not changed since last failure)
                if self._skip_registry and self._skip_registry.should_skip(fairy.name):
                    skipped_known_fail += 1
                    self._failed_fairies.append(fairy.name)
                    continue

                has_instance = fairy.metadata.get("fairy_instance") is not None
                needs_instantiation = fairy.metadata.get("needs_instantiation", False)

                # Must have EITHER an instance OR a source file to instantiate from
                if not has_instance and not needs_instantiation:
                    self._failed_fairies.append(fairy.name)
                    skipped_unbootable += 1
                    continue

                if needs_instantiation:
                    needs_inst_count += 1

                priority, heavy = classify_fairy(fairy.name)
                specs.append(FairySpec(
                    name=fairy.name,
                    plane=plane,
                    path=fairy.metadata.get("source_file", "") or getattr(fairy, 'path', '') or '',
                    priority=priority,
                    heavy=heavy,
                ))
                plane_count += 1

            if plane_count > 0:
                print(f"[GoBootOrch]   {plane}: {plane_count} fairies to boot")

        if skipped_known_fail:
            print(f"[GoBootOrch] Skip registry: {skipped_known_fail} fairies skipped (known failures)")
        print(f"[GoBootOrch] Fairy scan: {total_listed} listed, {len(specs)} bootable, "
              f"{skipped_not_sleeping} not sleeping, {skipped_unbootable} unbootable"
              + (f", {skipped_known_fail} skip-listed" if skipped_known_fail else ""))
        if needs_inst_count:
            print(f"[GoBootOrch]   ({needs_inst_count} need import+init+boot, "
                  f"{len(specs) - needs_inst_count} just need on_boot)")

        # Apply learned boot timing profiles (adjusts priority, timeout, heavy flags)
        # No-op until MIN_BASELINE_BOOTS reached per fairy (observation-only period)
        if self._timing_state:
            try:
                from tracer_pool.boot_timing_learner import PriorityAdjuster
                PriorityAdjuster(self._timing_state).adjust_specs(specs)
            except Exception as e:
                print(f"[GoBootOrch] Boot timing adjuster failed (non-fatal): {e}")

        # Sort by priority (high priority first)
        specs.sort(key=lambda s: s.priority)
        return specs

    def _process_results(self, result: BootResult):
        """Process Go boot results into per-plane tracking."""
        print(f"\n[GoBootOrch] ═══ BOOT COMPLETE ═══")
        print(f"  Total: {result.total_fairies}")
        print(f"  Succeeded: {result.succeeded}")
        print(f"  Failed: {result.failed}")
        print(f"  Timedout: {result.timedout}")
        print(f"  Time: {result.total_ms:.0f}ms ({result.total_ms/1000:.1f}s)")
        if result.slowest_fairy:
            print(f"  Slowest: {result.slowest_fairy} ({result.slowest_ms:.0f}ms)")

        # Build per-plane results
        for fr in result.fairy_results:
            if fr.ok:
                if fr.plane in self._woken_fairies:
                    # Avoid duplicates (already tracked in callback)
                    if fr.name not in self._woken_fairies[fr.plane]:
                        self._woken_fairies[fr.plane].append(fr.name)
            else:
                if fr.name not in self._failed_fairies:
                    self._failed_fairies.append(fr.name)

        # Mark planes as complete
        for plane in self.PLANES:
            self._planes_complete[plane] = True
            if self._on_plane_complete:
                try:
                    self._on_plane_complete(plane)
                except Exception:
                    pass

    def _finalize_boot(self):
        """Complete the boot sequence."""
        duration = time.time() - self._boot_start
        total_woken = sum(len(v) for v in self._woken_fairies.values())

        # --- Boot Timing Learner: transform results + persist profiles ---
        if self._timing_state and self._boot_result:
            try:
                from tracer_pool.boot_timing_learner import BootResultTransformer, ProfilePersister
                BootResultTransformer(self._timing_state).transform(
                    self._boot_result,
                    init_timings=self._init_timings,
                )
                ProfilePersister().persist(self._timing_state, fabric=self.fabric)
            except Exception as e:
                print(f"[GoBootOrch] Boot timing persist failed (non-fatal): {e}")

        # Publish boot.complete event
        if self.fabric:
            try:
                self.fabric.publish("boot.complete", {
                    "duration": duration,
                    "planes_booted": len(self.PLANES),
                    "fairies_woken": total_woken,
                    "failures": len(self._failed_fairies),
                    "mode": "hybrid_go" if self._go_available else "hybrid_python",
                })
            except Exception:
                pass

        # Fire completion callback
        if self._on_boot_complete:
            try:
                self._on_boot_complete()
            except Exception as e:
                print(f"[GoBootOrch] on_boot_complete callback error: {e}")

        self._booting = False
        self.is_complete = True

        print(f"\n[GoBootOrch] Boot finished: {total_woken} fairies in {duration:.1f}s "
              f"({len(self._failed_fairies)} failures)")

    def status(self) -> Dict[str, Any]:
        """
        Get boot status (backward compatible with BootOrchestrator.status()).

        FIX 2026-02-15: Return meaningful progress instead of current_plane=None.
        Go boots ALL planes simultaneously, so 'current_plane' shows which planes
        still have fairies booting, and current_index reflects real progress.
        """
        total_woken = sum(len(v) for v in self._woken_fairies.values())
        total_target = max(self._progress_total, 1)  # Avoid division by zero

        # Compute which planes are actively booting (have woken some but not all)
        active_planes = [
            p for p in self.PLANES
            if len(self._woken_fairies.get(p, [])) > 0 and not self._planes_complete.get(p, False)
        ]
        # Compute completed plane count
        completed_planes = sum(1 for v in self._planes_complete.values() if v)

        # Pick a descriptive "current_plane" for backward compat
        if self.is_complete:
            current_plane = "ALL"
        elif active_planes:
            current_plane = ", ".join(active_planes[:3])
        elif self._booting:
            current_plane = "starting..."
        else:
            current_plane = "idle"

        return {
            "booting": self._booting,
            "current_plane": current_plane,
            "current_index": completed_planes if not self.is_complete else len(self.PLANES),
            "total_planes": len(self.PLANES),
            "is_complete": self.is_complete,
            "boot_start": self._boot_start,
            "boot_mode": "hybrid_go" if self._go_available else "hybrid_python",
            "woken_fairies": {p: list(f) for p, f in self._woken_fairies.items()},
            "woken_counts": {p: len(f) for p, f in self._woken_fairies.items()},
            "failed_fairies": list(self._failed_fairies),
            "planes_complete": dict(self._planes_complete),
            "plane_times": dict(self._plane_times),
            "progress": {
                "total": self._progress_total,
                "completed": self._progress_completed,
                "succeeded": self._progress_succeeded,
                "failed": self._progress_failed,
                "woken": total_woken,
            },
        }

    @property
    def is_booting(self) -> bool:
        return self._booting

    @property
    def current_plane(self) -> Optional[str]:
        """Backward compat: Return descriptive string instead of None."""
        if self.is_complete:
            return "ALL"
        elif self._booting:
            active = [p for p in self.PLANES if len(self._woken_fairies.get(p, [])) > 0]
            return ", ".join(active[:3]) if active else "starting..."
        return None

    def _check_plane_completion(self, plane: str):
        """Backward compat: no-op (Go handles completion tracking)."""
        pass


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    print("GoBootOrchestrator — DLL check")
    dll_path = Path(__file__).parent / "tracer_pool.dll"
    print(f"  DLL exists: {dll_path.exists()}")

    if dll_path.exists():
        try:
            lib = ctypes.CDLL(str(dll_path))
            # Check if boot functions exist
            for fn_name in ["BootOrchestratorInit", "BootSetCallback", "BootAllFairies",
                           "BootGetProgress", "BootIsRunning"]:
                try:
                    getattr(lib, fn_name)
                    print(f"  {fn_name}: OK")
                except AttributeError:
                    print(f"  {fn_name}: MISSING (not yet compiled)")
        except OSError as e:
            print(f"  Load failed: {e}")
    else:
        print("  Run build.bat to compile Go DLL")
