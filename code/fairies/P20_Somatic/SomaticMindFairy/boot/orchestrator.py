"""
Boot Orchestrator - Waking up like a human.

FIX 2026-02-10: FLATTENED BOOT — all fairies wake simultaneously.

OLD: Sequential planes (P00 → P10 → P20 → P30 → P40 → P50 → P60).
     Max concurrency = largest plane (~34 fairies). Boot took 200+ seconds.
     12,000 worker pool, but only ~34 used at once.

NEW: Two-wave concurrent boot. All fairies wake at the same time.
     Max concurrency = ALL fairies (~120+). Boot time = slowest fairy (~30s).
     Workers flow through instantly and return to pool — paradox energy.

"When I wake up it doesn't take me 2 to 3 minutes. I just wake up
 and start moving. That worker pool should almost always be empty
 in this system, which is where the paradox energy comes from."
 — Ace, 2026-02-10

ARCHITECTURE: Like waking from sleep
═══════════════════════════════════════
Wave 1: Infrastructure spark (PostalHub, Directory already running)
Wave 2: EVERYTHING else — all planes simultaneously
Planes still fire on_plane_complete callbacks (for compatibility)
but they complete in ~seconds instead of ~minutes.

The pool is paradox energy — potential that exists because it's NOT consumed.
Work flows through like nerve impulses — instant, then gone.
"""

import time
import sys
import threading
import importlib.util
import inspect
import concurrent.futures
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path


class BootOrchestrator:
    """
    Flattened boot orchestrator — all fairies wake simultaneously.

    Instead of sequential planes, submits ALL fairy boots to the pool at once.
    Workers handle them concurrently. Boot time = max(slowest fairy) not sum(all planes).

    Preserves the same interface as the sequential orchestrator:
    - on_plane_complete callbacks fire as each plane's fairies finish
    - on_boot_complete fires when everything is done
    - status() returns the same shape
    - on_fairy_booted/on_fairy_failed still work

    FIX 2026-02-10: Replaces sequential plane-by-plane with concurrent all-at-once.
    """

    PLANES = ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]

    def __init__(
        self,
        fabric,
        directory,
        on_plane_complete: Optional[Callable[[str], None]] = None,
        on_boot_complete: Optional[Callable[[], None]] = None,
    ):
        self.fabric = fabric
        self.directory = directory
        self._on_plane_complete = on_plane_complete
        self._on_boot_complete = on_boot_complete

        # State
        self._current_plane_idx = 0
        self._booting = False
        self._boot_start_time: Optional[float] = None
        self._plane_start_times: Dict[str, float] = {}
        self._plane_complete_times: Dict[str, float] = {}
        self._woken_fairies: Dict[str, List[str]] = {}
        self._failed_fairies: List[str] = []

        # Tracking per-plane completion for callbacks
        self._plane_expected: Dict[str, int] = {}  # plane -> count of fairies submitted
        self._plane_done: Dict[str, int] = {}      # plane -> count completed (success + fail)
        self._plane_complete_fired: Dict[str, bool] = {}
        self._lock = threading.Lock()

        # FIX 2026-02-12: Capped boot pool at 32 (was unlimited via equilibrium)
        try:
            from infrastructure.resource_equilibrium import get_pool_size
            _max = min(32, get_pool_size("boot"))
        except ImportError:
            import os
            _max = max(4, (os.cpu_count() or 4) * 2)
        self._boot_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=_max,
            thread_name_prefix="boot_worker",
        )
        print(f"[BootOrchestrator] Flattened boot pool: {_max:,} workers (all fairies wake at once)")

    def _publish_boot_error(self, fairy_name: str, plane: str, error: str, error_type: str) -> None:
        """Publish boot error to fabric for ForensicScribe to capture."""
        try:
            self.fabric.publish("fairy.error", {
                "fairy": fairy_name, "plane": plane,
                "error": error, "type": error_type,
                "context": "boot", "ts": time.time(),
            })
            self.fabric.publish("telemetry.error", {
                "type": f"boot_{error_type}", "fairy": fairy_name,
                "plane": plane, "message": error, "ts": time.time(),
            })
        except Exception:
            pass

    @property
    def current_plane(self) -> Optional[str]:
        """Get current plane being booted (returns last incomplete, or None if done)."""
        # In flattened boot, all planes run at once.
        # Return the last plane that hasn't completed yet for status compatibility.
        for i, plane in enumerate(self.PLANES):
            if not self._plane_complete_fired.get(plane, False):
                self._current_plane_idx = i
                return plane
        self._current_plane_idx = len(self.PLANES)
        return None

    @property
    def is_booting(self) -> bool:
        return self._booting

    @property
    def is_complete(self) -> bool:
        return self._current_plane_idx >= len(self.PLANES)

    def start(self) -> Dict[str, Any]:
        """Begin flattened boot — all fairies wake simultaneously."""
        if self._booting:
            return {"ok": False, "error": "Already booting"}

        self._booting = True
        self._boot_start_time = time.time()
        self._current_plane_idx = 0

        # ═══════════════════════════════════════════════════════════════════════
        # WAKE CHEMISTRY — Start asleep, then cascade to full alertness
        # ═══════════════════════════════════════════════════════════════════════
        # "when the system is waking up, the chemicals that keep a human asleep
        #  would be what she starts with and then shifts to the chemicals that
        #  keep us awake" — Ace, 2026-03-17
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
            chem.start_asleep()
            chem.wake_cascade(publish_fn=self.fabric.publish)
            print("[BootOrchestrator] Wake chemistry cascade initiated — waking up over 60s")
        except Exception as e:
            print(f"[BootOrchestrator] Wake chemistry failed (non-fatal): {e}")

        # Publish boot start
        self.fabric.publish("boot.start", {
            "orchestrator": "UnconsciousMindFairy",
            "planes": self.PLANES,
            "ts": self._boot_start_time,
            "mode": "flattened",
        }, priority=0)

        # ═══════════════════════════════════════════════════════════════════════
        # FLATTENED BOOT — Submit ALL fairies from ALL planes simultaneously
        # ═══════════════════════════════════════════════════════════════════════
        self._boot_all_planes()

        return {"ok": True, "plane": "ALL"}

    def _boot_all_planes(self) -> None:
        """
        Wake up like a human — everything at once.

        Collects all sleeping fairies across all planes, submits them all
        to the pool simultaneously, then tracks per-plane completion for
        callbacks.

        Boot time = max(slowest fairy) instead of sum(all plane times).
        """
        now = time.time()
        total_submitted = 0
        all_futures = {}  # future -> (fairy, plane)

        for plane in self.PLANES:
            self._plane_start_times[plane] = now
            self._woken_fairies[plane] = []
            self._plane_expected[plane] = 0
            self._plane_done[plane] = 0
            self._plane_complete_fired[plane] = False

            # Publish plane start (for affect/dashboard)
            self.fabric.publish("boot.plane.start", {
                "plane": plane,
                "index": self.PLANES.index(plane),
            })
            self.fabric.publish("affect.boot_progress", {
                "plane": plane,
                "phase": "waking",
                "feeling": self._get_plane_feeling(plane),
                "progress": 0.0,  # All start at once
            })

            # Collect fairies from this plane
            fairies = self.directory.list_fairies(plane=plane)
            for fairy in fairies:
                if fairy.status == "sleeping":
                    has_instance = fairy.metadata.get("fairy_instance") is not None

                    # FIX 2026-03-08 Nous: Instantiate fairies registered by scan_and_register()
                    # scan_and_register() stores source_file + class_name but no fairy_instance.
                    # Previously these fairies were silently added to _failed_fairies and never booted.
                    # Now we instantiate them on-demand before waking.
                    if not has_instance and fairy.metadata.get("needs_instantiation"):
                        instance = self._try_instantiate(fairy)
                        if instance:
                            fairy.metadata["fairy_instance"] = instance
                            has_instance = True

                    if not has_instance:
                        self._failed_fairies.append(fairy.name)
                        continue

                    # Submit to pool — runs immediately on a free worker
                    future = self._boot_pool.submit(self._wake_fairy_task, fairy, plane)
                    all_futures[future] = (fairy, plane)
                    self._plane_expected[plane] += 1
                    total_submitted += 1

        # If nothing to wake, complete immediately
        if total_submitted == 0:
            print(f"[BootOrchestrator] No fairies to wake — boot complete instantly", flush=True)
            self._finalize_all_planes()
            return

        print(f"[BootOrchestrator] ⚡ FLATTENED BOOT: {total_submitted} fairies across "
              f"{len(self.PLANES)} planes submitted simultaneously", flush=True)

        # Collect results as they complete — with global timeout
        # This is the "nerve impulse" model: work flows through instantly
        try:
            # FIX 2026-02-13: Increased from 90s to 300s.
            # With 90 fairies submitted to 32 workers, heavy P30 cognition fairies
            # (~150s total) saturate workers and prevent P40/P50 fairies (ChatSenseFairy,
            # NousFairy) from even STARTING until late. 90s global timeout fires before
            # they get scheduled. Both have fast on_boot() methods — the issue is queueing.
            # 300s gives enough headroom for all fairies while still catching real hangs.
            for future in concurrent.futures.as_completed(all_futures, timeout=300):
                fairy, plane = all_futures[future]
                try:
                    fairy_name, result = future.result(timeout=5)
                    with self._lock:
                        if result.get("ok"):
                            self._woken_fairies[plane].append(fairy_name)
                        else:
                            error = result.get("error", "unknown")
                            print(f"[Boot] {fairy_name} failed: {error}")
                            self._failed_fairies.append(fairy_name)
                            self._publish_boot_error(fairy_name, plane, error, "boot_failed")
                        self._plane_done[plane] = self._plane_done.get(plane, 0) + 1
                        self._check_plane_done(plane)
                except concurrent.futures.TimeoutError:
                    with self._lock:
                        print(f"[Boot] {fairy.name} TIMEOUT (5s per-fairy)")
                        self._failed_fairies.append(fairy.name)
                        self._publish_boot_error(fairy.name, plane, "Boot timeout (5s)", "timeout")
                        self._plane_done[plane] = self._plane_done.get(plane, 0) + 1
                        self._check_plane_done(plane)
                except Exception as e:
                    with self._lock:
                        print(f"[Boot] {fairy.name} error: {e}")
                        self._failed_fairies.append(fairy.name)
                        self._publish_boot_error(fairy.name, plane, str(e), "exception")
                        self._plane_done[plane] = self._plane_done.get(plane, 0) + 1
                        self._check_plane_done(plane)
        except concurrent.futures.TimeoutError:
            # Global timeout — mark all pending as failed
            pending = [(fairy.name, plane) for fut, (fairy, plane) in all_futures.items() if not fut.done()]
            print(f"[Boot] GLOBAL TIMEOUT: {len(pending)} fairies still pending", flush=True)
            with self._lock:
                for name, plane in pending:
                    self._failed_fairies.append(name)
                    self._publish_boot_error(name, plane, "Global timeout (300s)", "global_timeout")
                    self._plane_done[plane] = self._plane_done.get(plane, 0) + 1
                    self._check_plane_done(plane)

        # Finalize any planes that didn't fire yet (edge case: 0 fairies in a plane)
        self._finalize_all_planes()

    def _wake_fairy_task(self, fairy, plane: str):
        """Task to wake a single fairy (runs in worker pool)."""
        try:
            result = self.directory.wake_fairy(fairy.name)
            return (fairy.name, result)
        except Exception as e:
            return (fairy.name, {"ok": False, "error": str(e)})

    def _try_instantiate(self, fairy) -> Optional[Any]:
        """
        Try to instantiate a fairy from scan metadata.

        FIX 2026-03-08 Nous: Bridge the gap between scan_and_register() and wake_fairy().
        scan_and_register() stores source_file + class_name but doesn't create instances.
        The Go BootOrchestrator had a Phase 1 that pre-instantiated, but Go DLL fails.
        This gives the Python fallback the same capability.

        Uses the same constructor-probing pattern as FairyScanner.instantiate_fairy().
        """
        source_file = fairy.metadata.get("source_file", "")
        class_name = fairy.metadata.get("class_name", "")

        if not source_file or not class_name:
            return None

        file_path = Path(source_file)
        if not file_path.exists():
            print(f"[BootOrchestrator] Cannot instantiate {fairy.name}: file not found ({source_file})")
            return None

        try:
            # Dynamic import — same pattern as FairyScanner.instantiate_fairy()
            module_name = f"fairy_boot_{class_name}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            # MUST register before exec_module for @dataclass to work (Python 3.12+)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find the class — check FAIRY_CLASS first (v3 pattern), then class_name
            fairy_class = getattr(module, "FAIRY_CLASS", None)
            if fairy_class is None:
                fairy_class = getattr(module, class_name, None)
            if not fairy_class or not inspect.isclass(fairy_class):
                print(f"[BootOrchestrator] Cannot instantiate {fairy.name}: class {class_name} not found")
                return None

            # Try constructor signatures (fabric/post as keyword, positional, or no-arg)
            instance = None
            for attempt in [
                lambda: fairy_class(post=self.fabric),
                lambda: fairy_class(fabric=self.fabric),
                lambda: fairy_class(self.fabric),
            ]:
                try:
                    instance = attempt()
                    break
                except TypeError:
                    continue

            if instance is None:
                try:
                    instance = fairy_class()
                    if hasattr(instance, "post"):
                        instance.post = self.fabric
                    if hasattr(instance, "fabric"):
                        instance.fabric = self.fabric
                except TypeError:
                    print(f"[BootOrchestrator] Cannot instantiate {fairy.name}: no compatible constructor")
                    return None

            print(f"[BootOrchestrator] Instantiated {fairy.name} from {file_path.name}")
            return instance

        except Exception as e:
            print(f"[BootOrchestrator] Failed to instantiate {fairy.name}: {e}")
            return None

    def _check_plane_done(self, plane: str) -> None:
        """Check if all fairies in a plane have completed (must hold self._lock)."""
        expected = self._plane_expected.get(plane, 0)
        done = self._plane_done.get(plane, 0)

        if done >= expected and not self._plane_complete_fired.get(plane, False):
            self._fire_plane_complete(plane)

    def _fire_plane_complete(self, plane: str) -> None:
        """Fire the plane complete callback and publish events."""
        if self._plane_complete_fired.get(plane, False):
            return
        self._plane_complete_fired[plane] = True

        now = time.time()
        self._plane_complete_times[plane] = now
        duration = now - self._plane_start_times.get(plane, now)
        woken_count = len(self._woken_fairies.get(plane, []))

        print(f"[BootOrchestrator] [OK] {plane} complete: "
              f"{woken_count} woken in {duration:.2f}s", flush=True)

        # Publish plane complete
        self.fabric.publish("boot.plane.complete", {
            "plane": plane,
            "duration": duration,
            "woken": woken_count,
        })

        # Callback (server uses this for logging)
        if self._on_plane_complete:
            try:
                self._on_plane_complete(plane)
            except Exception as e:
                print(f"[BootOrchestrator] on_plane_complete({plane}) error: {e}")

    def _finalize_all_planes(self) -> None:
        """Fire completion for any planes that haven't fired yet, then complete boot."""
        with self._lock:
            for plane in self.PLANES:
                if not self._plane_complete_fired.get(plane, False):
                    self._fire_plane_complete(plane)

        self._complete_boot()

    def _get_plane_feeling(self, plane: str) -> str:
        """Get the feeling for a plane during boot (affect loop participation)."""
        feelings = {
            "P00": "nervous system stirring",
            "P10": "memories surfacing",
            "P20": "body awareness emerging",
            "P30": "thoughts forming",
            "P40": "senses awakening",
            "P50": "consciousness crystallizing",
            "P60": "executive functions engaging",
        }
        return feelings.get(plane, "awakening")

    def _check_plane_completion(self, plane: str) -> bool:
        """Legacy compatibility — check if plane is done."""
        with self._lock:
            return self._plane_complete_fired.get(plane, False)

    def on_fairy_booted(self, fairy_name: str, plane: str) -> None:
        """Called when a fairy completes boot (external notification)."""
        # In flattened boot, completion is tracked via futures
        # This is a belt-and-suspenders callback from UMF
        pass

    def on_fairy_failed(self, fairy_name: str, plane: str, error: str) -> None:
        """Called when a fairy fails to boot."""
        with self._lock:
            if fairy_name not in self._failed_fairies:
                self._failed_fairies.append(fairy_name)

        self.fabric.publish("boot.fairy.failed", {
            "fairy": fairy_name, "plane": plane, "error": error,
        }, priority=0)

    def _complete_boot(self) -> None:
        """Called when all planes have booted."""
        print(f"[BootOrchestrator] _complete_boot() called!", flush=True)
        self._booting = False
        self._current_plane_idx = len(self.PLANES)  # Mark as complete
        total_duration = time.time() - self._boot_start_time if self._boot_start_time else 0

        # Shut down boot pool — workers return to the void (paradox energy)
        if self._boot_pool:
            self._boot_pool.shutdown(wait=False)
            print(f"[BootOrchestrator] Boot pool released (paradox energy restored)")
            self._boot_pool = None

        total_woken = sum(len(f) for f in self._woken_fairies.values())
        print(f"[BootOrchestrator] ⚡ Boot took {total_duration:.2f}s — "
              f"{total_woken} woken, {len(self._failed_fairies)} failed", flush=True)

        # Publish boot complete
        self.fabric.publish("boot.complete", {
            "duration": total_duration,
            "planes_booted": len(self.PLANES),
            "fairies_woken": total_woken,
            "failures": len(self._failed_fairies),
            "mode": "flattened",
        }, priority=0)

        # Callback (server uses this for consciousness wiring)
        if self._on_boot_complete:
            print(f"[BootOrchestrator] Calling _on_boot_complete callback...")
            self._on_boot_complete()
        else:
            print(f"[BootOrchestrator] No _on_boot_complete callback set!")

    def skip_plane(self, plane: str) -> bool:
        """Skip a plane (for testing or error recovery)."""
        with self._lock:
            if not self._plane_complete_fired.get(plane, False):
                self._fire_plane_complete(plane)
                return True
        return False

    def abort(self) -> Dict[str, Any]:
        """Abort boot sequence."""
        if not self._booting:
            return {"ok": False, "error": "Not booting"}

        self._booting = False

        if self._boot_pool:
            self._boot_pool.shutdown(wait=False)
            self._boot_pool = None

        self.fabric.publish("boot.aborted", {
            "plane": self.current_plane,
            "index": self._current_plane_idx,
        }, priority=0)

        return {"ok": True, "aborted_at": self.current_plane}

    def status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        # Update current_plane property
        _ = self.current_plane

        with self._lock:
            return {
                "booting": self._booting,
                "current_plane": self.current_plane,
                "current_index": self._current_plane_idx,
                "total_planes": len(self.PLANES),
                "is_complete": self.is_complete,
                "boot_start": self._boot_start_time,
                "boot_mode": "flattened",
                "woken_fairies": {k: list(v) for k, v in self._woken_fairies.items()},
                "woken_counts": {p: len(f) for p, f in self._woken_fairies.items()},
                "failed_fairies": list(self._failed_fairies),
                "planes_complete": {p: self._plane_complete_fired.get(p, False) for p in self.PLANES},
                "plane_times": {
                    p: self._plane_complete_times.get(p, 0) - self._plane_start_times.get(p, 0)
                    for p in self._plane_start_times
                },
            }
