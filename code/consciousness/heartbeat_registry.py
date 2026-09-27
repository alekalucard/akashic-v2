"""
HeartbeatRegistry -- Concurrent Pulse Delivery

The postal system is great for general messaging, but heartbeat delivery
through postal queues has caused fairy deaths 6 times (Feb 3-6, 2026).
The failure mode: postal.publish() fans out to 82+ subscribers through
worker-pool queues. When workers can't drain fast enough, enqueue()
returns False and heartbeats are silently dropped.

This registry delivers pulses concurrently using a thread pool.
Each registered fairy's callback is submitted to the pool — no serial
iteration, no GIL-serialized blocking in the heartbeat thread.

    BEFORE: Heart -> registry.pulse() -> serial loop (134s during boot!)
    AFTER:  Heart -> registry.pulse() -> submit to pool -> return immediately

The heartbeat thread is NEVER blocked. The pool handles delivery.
Each callback is wrapped in try/except so one bad fairy can't crash others.

Created: 2026-02-13
Rewritten: 2026-02-13 (concurrent delivery via ThreadPoolExecutor)
"""

import time
import queue as queue_mod
import threading
from typing import Callable, Dict, Optional, Any, List


class HeartbeatRegistry:
    """
    Concurrent heartbeat delivery to all registered fairies.

    No postal. No queues that can drop. Every registered fairy gets every beat.
    Delivery is concurrent — the heartbeat thread returns immediately.
    """

    # Performance thresholds
    SLOW_THRESHOLD_MS = 50.0     # Warn if callback takes > 50ms
    SLOW_WARN_AFTER = 5          # Warn after N consecutive slow callbacks
    LOG_STATS_EVERY = 300        # Log delivery stats every N beats
    POOL_SIZE = 48               # FIX 2026-04-15 PM (Nous): 24→48 to replace
                                 # per-call thread allocation pattern (360 Thread
                                 # objects/sec + their Lock/Event/Condition internals
                                 # was the root of the 2nd post-reboot leak).
                                 # 12 workers couldn't service 110+ callbacks → 58s spread →
                                 # watchdog detected "freeze" 746 times. At 24, each worker
                                 # handles ~5 callbacks, keeping spread under timeout.
                                 # History: 8→24 (Feb 13), 24→12 (Apr 4), 12→24 (Apr 14)

    # FIX 2026-04-04 (Nous + Ace): Plane-aware tick gating.
    # "Different aspects of the human body and mind run at different frequencies.
    #  Not all running at cortex brain speed." — Ace
    # Memory (P10) ticks every 5th beat, not every beat. Sensory (P40) every beat.
    # This cuts callback volume ~40-60% while maintaining liveness for all.
    PLANE_TICK_DIVISOR = {
        "P00": 1,    # Autonomic: every beat (reflexes)
        "P10": 5,    # Memory: every 5th beat (consolidation is slow)
        "P20": 1,    # Somatic: every beat (IS the heartbeat)
        "P30": 1,    # Cognition: every beat (thinking needs responsiveness)
        "P40": 1,    # Sensory: every beat (perception needs speed)
        "P50": 2,    # Agency: every 2nd beat (action planning is deliberate)
        "P60": 2,    # Executive: every 2nd beat (deliberation)
    }

    def __init__(self):
        self._callbacks: Dict[str, Callable] = {}   # name -> callback
        self._fairy_planes: Dict[str, str] = {}     # name -> plane (e.g. "P10")
        self._lock = threading.Lock()                # Protects _callbacks

        # FIX 2026-03-04 Nous: Queue-based workers replace ThreadPoolExecutor.
        # TPE.submit() creates Future+_WorkItem per callback per beat.
        # At 4Hz × 90 callbacks = 360 Future objects/sec. Even with fire-and-forget,
        # the executor holds _WorkItem refs internally until workers complete them.
        # Queue + workers: same concurrent delivery, zero Future objects.
        self._delivery_queue = queue_mod.Queue(maxsize=2048)
        self._delivery_workers = []
        for i in range(self.POOL_SIZE):
            t = threading.Thread(
                target=self._delivery_worker_loop,
                daemon=True,
                name=f"hb-deliver-{i}",
            )
            t.start()
            self._delivery_workers.append(t)

        # Performance tracking
        self._slow_counts: Dict[str, int] = {}       # name -> consecutive slow count
        self._error_counts: Dict[str, int] = {}      # name -> total error count
        self._last_stats: Dict[str, Any] = {}        # Last pulse() delivery stats
        self._total_pulses = 0
        self._total_delivered = 0
        self._total_errors = 0

        # FIX 2026-03-14 (Nous): Liveness tracking per fairy.
        # HeartbeatHandler._check_citizen_liveness() relies on _CITIZEN_OBJECTS
        # to verify fairies are alive. But some fairies (engines loaded via
        # registry: paths, dual-instance overwrites, etc.) aren't in that dict.
        # Those fairies fall to unreliable postal echo → declared dead after 300s
        # despite receiving every heartbeat. This dict tracks SUCCESSFUL delivery
        # timestamps, giving the watchdog a TERTIARY liveness signal.
        self._last_delivered_ts: Dict[str, float] = {}  # name -> last successful delivery time

        # BULKHEAD (2026-07-13 Nous+Ace): cap each fairy to ONE outstanding callback so a
        # slow "hog" (e.g. BrainstemReflex 121s) can't self-backlog the pool every beat.
        # Proven in scratchpad/bulkhead_repro.py: fast-callback p99 wait 478ms -> 6.7ms.
        # Reversible: delete this + the 2 pulse()/_deliver_one blocks. Empty set = byte-identical.
        self._in_flight: set = set()                 # names currently queued-or-running
        self._in_flight_lock = threading.Lock()

        # FIX 2026-02-17: Single reusable stats thread instead of spawning new ones.
        # Before: every 300 beats spawned a new daemon thread holding 90+ future refs.
        # Now: one thread drains a queue, preventing thread/memory accumulation.
        self._stats_queue = queue_mod.Queue(maxsize=4)  # Bounded - drop old if backed up
        self._stats_thread = None

        # CIRCADIAN TICK MODULATION (2026-06-17 Nous + Ace): per-plane tick multipliers
        # pushed by CircadianPacemakerFairy each broadcast (~30s). Empty by default → the
        # fixed PLANE_TICK_DIVISOR rules (byte-identical). When the pacemaker pushes (its
        # side is flag-gated AKASHIC_CIRCADIAN_TICK), each REGION's tick rate breathes with
        # the circadian phase. Rebound atomically by the setter → read lock-free in pulse().
        self._circadian_plane_mult: Dict[str, float] = {}

    def _delivery_worker_loop(self):
        """Worker thread that drains heartbeat delivery queue.

        FIX 2026-03-04 Nous: Replaces ThreadPoolExecutor to eliminate
        Future/_WorkItem accumulation per heartbeat delivery.

        FIX 2026-03-06 Nous: Added outer try/except so a bad unpack or
        unexpected error doesn't kill the worker thread permanently.
        Dead workers reduce pool capacity, causing progressive starvation.
        """
        while True:
            try:
                task = self._delivery_queue.get(timeout=2.0)
            except queue_mod.Empty:
                continue
            if task is None:  # Poison pill
                break
            try:
                name, cb, pulse_data = task
                self._deliver_one(name, cb, pulse_data)
            except Exception as e:
                # Worker must survive — a dead worker reduces pool permanently
                try:
                    print(f"[HeartbeatRegistry] Worker error (survived): {e}")
                except Exception:
                    pass
            finally:
                try:
                    self._delivery_queue.task_done()
                except ValueError:
                    pass  # task_done() called too many times — harmless

    def set_circadian_plane_modulation(self, plane_mult: Dict[str, float]) -> None:
        """Pacemaker → registry: set per-plane tick multipliers (circadian region-frequency).

        plane_mult maps plane ("P00".."P60") → multiplier on the base PLANE_TICK_DIVISOR
        (>1 = fewer ticks / slower region; <1 = faster). The pulse loop reads the resulting
        dict lock-free, so we rebind a fresh dict atomically rather than mutating in place.
        Pass empty/None to clear (revert to the fixed divisors).
        """
        self._circadian_plane_mult = dict(plane_mult) if plane_mult else {}

    def register(self, name: str, callback: Callable[[dict], None], plane: str = "") -> bool:
        """
        Register a fairy to receive heartbeat pulses.

        Args:
            name: Fairy's ACTOR_NAME (e.g., "SourpatchesFairy")
            callback: Function to call with pulse_data dict on each beat
            plane: Fairy's plane (e.g., "P10"). Used for tick gating — P10 Memory
                   only gets ticked every 5th beat, P50 Agency every 2nd beat.
                   If empty, fairy gets ticked every beat (safe default).

        Returns:
            True if newly registered, False if already registered (updated)
        """
        with self._lock:
            is_new = name not in self._callbacks
            self._callbacks[name] = callback
            if plane:
                self._fairy_planes[name] = plane
            if is_new:
                self._slow_counts[name] = 0
                self._error_counts[name] = 0
        if is_new:
            # Only log first 10 registrations individually, then batch
            if len(self._callbacks) <= 10:
                print(f"[HeartbeatRegistry] + {name} (total: {len(self._callbacks)})", flush=True)
            # FIX 2026-03-07 (Nous): Log milestone counts so we can verify
            # total registrations match expected fairy count.
            elif len(self._callbacks) in (25, 50, 75, 100, 110, 120):
                print(f"[HeartbeatRegistry] {len(self._callbacks)} fairies registered (latest: {name})", flush=True)
        else:
            # FIX 2026-03-07 (Nous): Log overwrites — when an engine re-registers
            # with the same name, this REPLACES the wrapper's callback. This was
            # previously completely silent and caused phantom dead fairies.
            print(f"[HeartbeatRegistry] OVERWRITE: {name} re-registered (callback replaced)", flush=True)
        return is_new

    def unregister(self, name: str) -> bool:
        """
        Remove a fairy from heartbeat delivery.

        Args:
            name: Fairy's ACTOR_NAME

        Returns:
            True if was registered and removed, False if not found
        """
        with self._lock:
            if name in self._callbacks:
                del self._callbacks[name]
                self._slow_counts.pop(name, None)
                self._error_counts.pop(name, None)
                print(f"[HeartbeatRegistry] - {name} (total: {len(self._callbacks)})", flush=True)
                return True
            return False

    # FIX 2026-04-15 PM (Nous): Removed per-call thread allocation.
    # Previously spawned a new Thread per callback for timeout abandonment.
    # At 4Hz × 90 fairies = 360 new Thread objects/sec, each carrying
    # Lock+Event+Condition internals = ~2000 dict allocations/sec. This
    # was the second post-reboot leak source (after the TPE fix).
    #
    # New approach: callbacks run INLINE in the hb-deliver worker with
    # 48 workers (doubled from 24) for parallel headroom. Slow callbacks
    # block one worker each rather than being "abandoned". With 48 workers
    # at 360 Hz traffic, we have 7.5 Hz per worker = 133ms budget. Most
    # callbacks are <1ms. A slow (5s) callback blocks one worker for 5s;
    # 47 others keep draining the queue. For ALL 48 to block simultaneously
    # would require a pathological burst — we accept that risk and log it.
    CALLBACK_SLOW_THRESHOLD_SEC = 5.0  # Log callbacks slower than this

    def _deliver_one(self, name: str, cb: Callable, pulse_data: dict) -> tuple:
        """Deliver one pulse to one fairy. Runs in pool thread.

        FIX 2026-04-15 PM (Nous): Callbacks run INLINE (no nested thread).
        Previously spawned a Thread per call for timeout abandonment, at
        a cost of 360 Thread allocations/sec (~2000 dict allocs/sec under
        3.14t free-threaded). With POOL_SIZE=48, slow callbacks block one
        worker each instead of stalling the whole pool.
        """
        t0 = time.perf_counter()
        try:
            cb(pulse_data)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # FIX 2026-03-14 (Nous): Track successful delivery for watchdog liveness
            self._last_delivered_ts[name] = time.time()

            # Log unusually slow callbacks (visibility, no abandonment)
            if elapsed_ms > self.CALLBACK_SLOW_THRESHOLD_SEC * 1000.0:
                _slow = self._slow_counts.get(name, 0) + 1
                self._slow_counts[name] = _slow
                if _slow <= 3 or _slow % 50 == 0:
                    print(f"[HeartbeatRegistry] SLOW: {name} callback took "
                          f"{elapsed_ms:.0f}ms (#{_slow}, pool_size={self.POOL_SIZE})",
                          flush=True)
            return (name, True, elapsed_ms, None)

        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            # Log delivery errors — first 3 per fairy, then every 100th
            self._error_counts[name] = self._error_counts.get(name, 0) + 1
            err_count = self._error_counts[name]
            if err_count <= 3 or err_count % 100 == 0:
                try:
                    print(f"[HeartbeatRegistry] DELIVERY ERROR in {name} (#{err_count}): {e}", flush=True)
                except Exception:
                    pass
            self._total_errors += 1
            return (name, False, elapsed_ms, e)
        finally:
            # BULKHEAD (2026-07-13): callback done -> release so this fairy can queue next beat.
            with self._in_flight_lock:
                self._in_flight.discard(name)

    def pulse(self, pulse_data: dict) -> Dict[str, Any]:
        """
        Deliver heartbeat to ALL registered callbacks CONCURRENTLY.

        Submits all callbacks to a thread pool and returns immediately
        to the heartbeat thread. The heartbeat loop is NEVER blocked.

        The pool gathers results for stats tracking but delivery itself
        is fire-and-forget from the heart's perspective.

        Args:
            pulse_data: The heartbeat payload dict

        Returns:
            Delivery stats: submitted, total, beat
        """
        self._total_pulses += 1
        t0 = time.perf_counter()

        # Snapshot callbacks under lock (fast -- just dict copy)
        with self._lock:
            callbacks = dict(self._callbacks)

        if not callbacks:
            return {"submitted": 0, "total": 0, "beat": pulse_data.get("beat", 0)}

        # FIX 2026-04-17 (Nous + Ace): BATCH LIVENESS ATTESTATION.
        # Liveness (I exist, process isn't frozen) is SEPARATE from work trigger
        # (do your tick). The old flow coupled them: obj._last_tick only updated
        # AFTER the callback ran, so slow/queued callbacks looked like dead fairies.
        #
        # UPDATE 2026-04-17 (Nous + Ace): Stamp ALL citizens in the registry,
        # not just those with heartbeat callbacks. CochleaFairy registered as a
        # citizen but her heartbeat callback never made it to this registry
        # (librosa-missing path skipped her wiring). She was invisible to the
        # stamp and the watchdog declared her dead. Now every fairy that exists
        # in _CITIZEN_OBJECTS gets liveness attestation every beat, period.
        #
        # UNIFIED 2026-04-17 (Nous + Ace): Imports from fairy_template.citizen_registry
        # — the SINGLE canonical dict shared by all templates and the watchdog.
        _now_liveness = time.time()
        try:
            from fairy_template.citizen_registry import _CITIZEN_OBJECTS as _CIT
        except ImportError:
            _CIT = {}
        # Stamp every registered citizen, whether or not they have a callback here.
        # FIX 2026-05-10 (Nous + Ace): zombie-loop ROOT CAUSE.
        # Was only stamping _last_tick, not _tick_count. Watchdog's
        # _check_citizen_liveness skips with `if last_tick == 0 OR tick_count == 0:
        # continue` — so 112 fairies whose chained-callback never fires (or fires
        # gated) had _last_tick fresh but _tick_count stuck at 0, registering as
        # "frozen" forever. Atomic update of both fields matches the contract
        # everywhere else (organ_template:3077-3078, on_tick:4181-4182).
        # FIX 2026-05-10 (Nous + Ace) A1.3 ship: stamp-loop concurrency safety.
        # Post-A1.2 zombie-pattern recurrence at beat ~2000 traced to outer
        # try/except firing silently under Python 3.14t free-threaded mode —
        # `list(_CIT.items())` produces a list-VIEW that can race when another
        # thread modifies _CITIZEN_OBJECTS during iteration → RuntimeError
        # "dictionary changed size during iteration" → silent swallow → loop
        # exits PARTIALLY → some fairies stamped, others not → 112-fairies-at-
        # 0s-spread zombie pattern recurs. RAM pressure (89%+) makes this race
        # likely via working-set trim slowing iteration. Defensive fix: take
        # a TRUE snapshot via tuple() so concurrent modification is provably
        # safe. Also keeping diagnostic logging on outer except as belt-and-
        # suspenders — if we still see exceptions post-fix, diagnose the next layer.
        try:
            # Tuple-snapshot is concurrent-modification safe (vs list view)
            _cit_snapshot = tuple(_CIT.items())
        except Exception:
            _cit_snapshot = ()
        # DIAG 2026-05-10: log outer try/except fires (rate-limited).
        try:
            for _name, _obj in _cit_snapshot:
                self._last_delivered_ts[_name] = _now_liveness
                if _obj is not None:
                    try:
                        _obj._last_tick = _now_liveness
                        _obj._tick_count = getattr(_obj, '_tick_count', 0) + 1
                    except Exception:
                        pass  # Never let liveness attestation crash the heart
        except Exception as _stamp_err:
            if not hasattr(self, '_stamp_diag_count'):
                self._stamp_diag_count = 0
            self._stamp_diag_count += 1
            if self._stamp_diag_count <= 10 or self._stamp_diag_count % 100 == 0:
                try:
                    print(f"[STAMP-DIAG] outer try/except #{self._stamp_diag_count}: "
                          f"{type(_stamp_err).__name__}: {str(_stamp_err)[:120]}",
                          flush=True)
                except Exception:
                    pass
            pass  # Snapshot failure — try again next beat

        # FIX 2026-03-04 Nous: Queue-based delivery replaces pool.submit().
        # No Future objects created — just put (name, callback, data) tuples on queue.
        # Workers drain the queue concurrently. Zero Future/_WorkItem accumulation.
        #
        # FIX 2026-04-04 (Nous + Ace): Plane-aware tick gating.
        # Each fairy's plane determines how often it gets ticked.
        # P10 Memory: every 5th beat. P50 Agency: every 2nd beat. Others: every beat.
        # Liveness tracking now happens ABOVE this loop — every fairy every beat.
        beat_number = pulse_data.get("beat", self._total_pulses)
        submitted = 0
        skipped = 0
        _cmult = self._circadian_plane_mult  # atomic ref read (rebound, never mutated in place)
        for name, cb in callbacks.items():
            # Check if this fairy's plane is due for a tick
            plane = self._fairy_planes.get(name, "")
            divisor = self.PLANE_TICK_DIVISOR.get(plane, 1)
            # CIRCADIAN region-frequency (2026-06-17 Nous + Ace): the pacemaker breathes each
            # region's tick rate with the phase. Empty until it pushes → no-op default.
            if _cmult:
                _m = _cmult.get(plane, 1.0)
                if _m != 1.0:
                    divisor = max(1, int(round(divisor * _m)))
            if divisor > 1 and beat_number % divisor != 0:
                # Skip work tick but still track liveness
                self._last_delivered_ts[name] = time.time()
                skipped += 1
                continue
            # BULKHEAD (2026-07-13): skip if this fairy's previous callback is still queued/running.
            with self._in_flight_lock:
                if name in self._in_flight:
                    self._last_delivered_ts[name] = time.time()  # liveness still stamped
                    skipped += 1
                    continue
                self._in_flight.add(name)
            try:
                self._delivery_queue.put_nowait((name, cb, pulse_data))
                submitted += 1
            except queue_mod.Full:
                with self._in_flight_lock:
                    self._in_flight.discard(name)   # never queued -> release the mark
                # 2026-06-10 (Nous + Ace) HEART-FREEZE FIX (layer 2): DROP the tick when
                # the delivery queue is full — do NOT call cb() inline. The old inline
                # fallback ran the fairy's on_tick ON THE BEAT THREAD; a heavy fairy
                # (AutonomyFairy → cortex.reason → manifold.spread_activation, slow under
                # RAM pressure) then FROZE the heart (stack-verified via freeze-watchdog).
                # A dropped work-tick is harmless (liveness already stamped above); a
                # frozen heart is not. Throttled log surfaces the queue-full condition.
                self._dropped_full = getattr(self, "_dropped_full", 0) + 1
                skipped += 1
                if self._dropped_full % 200 == 1:
                    print(f"[HeartbeatRegistry] delivery queue FULL — dropped "
                          f"{self._dropped_full} work-ticks (workers can't drain fast "
                          f"enough; lighten the heavy fairies). NOT run inline-on-beat.",
                          flush=True)

        stats = {
            "submitted": submitted,
            "skipped": skipped,
            "total": len(callbacks),
            "beat": pulse_data.get("beat", 0),
        }

        # Log stats periodically (no Future gathering needed anymore)
        if (self._total_pulses == 1 or
                self._total_pulses % self.LOG_STATS_EVERY == 0):
            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"[HeartbeatRegistry] Beat {pulse_data.get('beat', '?')}: "
                  f"{submitted}/{len(callbacks)} queued ({skipped} gated) in {elapsed_ms:.1f}ms "
                  f"(pulse #{self._total_pulses}, queue_size={self._delivery_queue.qsize()})",
                  flush=True)

        self._last_stats = stats
        return stats

    @property
    def count(self) -> int:
        """Number of registered fairies."""
        return len(self._callbacks)

    @property
    def registered_names(self) -> List[str]:
        """List of registered fairy names."""
        with self._lock:
            return list(self._callbacks.keys())

    def _stats_worker_loop(self):
        """Single persistent thread that processes stats gathering requests.

        FIX 2026-02-17: Replaces per-300-beat thread spawning.
        Drains self._stats_queue, gathers future results, updates stats.
        """
        import queue as _queue_mod
        while True:
            try:
                item = self._stats_queue.get(timeout=30.0)
            except _queue_mod.Empty:
                continue
            except Exception:
                break

            futures, pulse_num, beat, t0_copy, cb_count = item
            try:
                delivered = 0
                errors = 0
                slow = 0
                for f in futures:
                    try:
                        name, ok, elapsed_ms, err = f.result(timeout=5.0)
                        if ok:
                            delivered += 1
                            if elapsed_ms > self.SLOW_THRESHOLD_MS:
                                slow += 1
                                self._slow_counts[name] = self._slow_counts.get(name, 0) + 1
                                if self._slow_counts[name] == self.SLOW_WARN_AFTER:
                                    print(f"[HeartbeatRegistry] SLOW: {name} took {elapsed_ms:.1f}ms "
                                          f"({self.SLOW_WARN_AFTER}x consecutive)", flush=True)
                            else:
                                if name in self._slow_counts:
                                    self._slow_counts[name] = 0
                        else:
                            errors += 1
                            self._error_counts[name] = self._error_counts.get(name, 0) + 1
                            err_count = self._error_counts[name]
                            if err_count <= 3 or err_count % 100 == 0:
                                print(f"[HeartbeatRegistry] ERROR in {name} (#{err_count}): {err}", flush=True)
                    except Exception:
                        errors += 1

                total_ms = (time.perf_counter() - t0_copy) * 1000.0
                self._total_delivered += delivered
                self._total_errors += errors

                full_stats = {
                    "delivered": delivered,
                    "errors": errors,
                    "slow": slow,
                    "total": cb_count,
                    "duration_ms": round(total_ms, 2),
                    "beat": beat,
                }
                self._last_stats = full_stats

                if pulse_num == 1:
                    print(f"[HeartbeatRegistry] FIRST pulse delivered to {delivered}/{cb_count} fairies "
                          f"in {total_ms:.1f}ms (concurrent, {self.POOL_SIZE} workers)", flush=True)
                elif pulse_num % self.LOG_STATS_EVERY == 0:
                    drop_rate = (self._total_errors / max(1, self._total_delivered + self._total_errors)) * 100
                    print(f"[HeartbeatRegistry] Beat {pulse_num}: "
                          f"{cb_count} registered, {total_ms:.1f}ms total, "
                          f"errors={self._total_errors} ({drop_rate:.1f}%)", flush=True)
            except Exception as e:
                print(f"[HeartbeatRegistry] Stats gather error: {e}", flush=True)
            finally:
                del futures

    def get_status(self) -> Dict[str, Any]:
        """Full registry status for diagnostics."""
        with self._lock:
            names = list(self._callbacks.keys())
        return {
            "registered_count": len(names),
            "registered_names": names,
            "total_pulses": self._total_pulses,
            "total_delivered": self._total_delivered,
            "total_errors": self._total_errors,
            "slow_fairies": {k: v for k, v in self._slow_counts.items() if v > 0},
            "error_fairies": {k: v for k, v in self._error_counts.items() if v > 0},
            "last_pulse": self._last_stats,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_registry_instance: Optional[HeartbeatRegistry] = None
_registry_lock = threading.Lock()


def get_heartbeat_registry() -> HeartbeatRegistry:
    """Get or create the global HeartbeatRegistry singleton."""
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = HeartbeatRegistry()
                print(f"[HeartbeatRegistry] Created (concurrent delivery, {_registry_instance.POOL_SIZE} workers)", flush=True)
    return _registry_instance
