# TemporalPulseDispatcher - Fan out heartbeat to all planes at their frequencies
# P20_Somatic/circulation/temporal_pulse_dispatcher.py
#
# "The heart is the conductor. Each plane is an instrument playing at its own tempo."
#
# This bridges:
# - CirculationPumpFairy (the heart, 1 Hz base)
# - TemporalStratification (plane frequencies)
# - WorkerPool (parallel fan-out)
#
# Result: P30 Cognition fires 4x per heartbeat, P10 Memory fires once every 5 beats

from __future__ import annotations

import time
import queue
import threading
from typing import Dict, Optional, Callable, List, Any
from dataclasses import dataclass, field

# Import temporal frequencies
from .temporal_stratification import PLANE_FREQUENCIES, TemporalBand

# =============================================================================
# DISPATCHER - Temporal Fan-Out to All Planes
# =============================================================================

@dataclass
class PlaneTickState:
    """Tracks tick accumulation for a plane."""
    plane: str
    base_hz: float
    multiplier: float  # How many ticks per base heartbeat
    accumulated: float = 0.0
    last_tick: float = field(default_factory=time.time)
    tick_count: int = 0


class TemporalPulseDispatcher:
    """
    Dispatches heartbeat pulses to all planes at their natural frequencies.
    
    The heart beats at ~1 Hz (base tempo).
    Each plane runs at a MULTIPLE of this:
    
    P00 Autonomic: 10x base  (10 ticks per heartbeat)
    P40 Sensory:    8x base  (8 ticks per heartbeat)
    P30 Cognition:  2x base  (2 ticks per heartbeat)
    P50 Agency:   1.5x base  (1-2 ticks per heartbeat)
    P20 Somatic:    1x base  (1 tick per heartbeat - IS the heartbeat)
    P60 Executive:0.5x base  (1 tick every 2 heartbeats)
    P10 Memory:   0.2x base  (1 tick every 5 heartbeats)
    
    Uses WorkerPool for parallel dispatch to all fairies.
    """
    
    BASE_TEMPO = 1.0  # Heart rate in Hz
    
    def __init__(self, post=None, worker_pool=None):
        self._post = post
        self._worker_pool = worker_pool
        self._running = False
        self._lock = threading.RLock()
        
        # Initialize plane states
        self._planes: Dict[str, PlaneTickState] = {}
        for plane, config in PLANE_FREQUENCIES.items():
            base_hz = config.get("base_hz", 1.0)
            multiplier = base_hz / self.BASE_TEMPO
            self._planes[plane] = PlaneTickState(
                plane=plane,
                base_hz=base_hz,
                multiplier=multiplier,
            )
        
        # Subscribers per plane
        self._plane_subscribers: Dict[str, List[Callable]] = {p: [] for p in self._planes}
        
        # Stats
        self._total_dispatches = 0
        self._heartbeat_count = 0

        # FIX 2026-03-04 Nous: Persistent dispatch worker replaces per-heartbeat Thread().
        # Previously created a NEW Thread() on every heartbeat (4Hz = 4 threads/sec).
        # Each thread lived ~5ms then died. OS thread create/destroy overhead + GC pressure.
        # Now: single persistent daemon thread drains a queue. Zero thread churn.
        self._dispatch_queue = queue.Queue(maxsize=64)
        self._dispatch_worker = threading.Thread(
            target=self._dispatch_worker_loop,
            daemon=True,
            name="temporal_dispatch",
        )
        self._dispatch_worker.start()

        print(f"[TemporalPulseDispatcher] Initialized with {len(self._planes)} planes")
        for p, state in self._planes.items():
            print(f"  {p}: {state.base_hz} Hz ({state.multiplier}x base)")
    
    def on_heartbeat(self, pulse_data: Dict[str, Any]):
        """
        Called on each heartbeat. Dispatches to all planes at their frequencies.

        For a 1 Hz heartbeat:
        - P00 fires 10 times
        - P40 fires 8 times
        - P30 fires 2 times
        - P20 fires 1 time
        - P60 fires every other beat
        - P10 fires every 5th beat

        FIX 2026-02-22 Nous: Decoupled tick CALCULATION from DISPATCH.
        Previously held RLock while doing ~23 synchronous post.route() calls
        per heartbeat — each acquiring postal locks, triggering handler
        callbacks, all competing for GIL with 160+ threads. The heartbeat
        handler blocked for the entire fan-out duration.

        Now:
        1. Lock held only for tick math (microseconds, pure arithmetic)
        2. Dispatch happens in a daemon thread (non-blocking)
        3. Heartbeat handler returns immediately
        4. GIL pressure spread across time instead of concentrated in one burst
        """
        ticks_to_dispatch = []

        with self._lock:
            self._heartbeat_count += 1
            beat_num = pulse_data.get("beat", self._heartbeat_count)

            for plane, state in self._planes.items():
                # Accumulate fractional ticks
                state.accumulated += state.multiplier

                # Fire as many ticks as accumulated
                ticks_to_fire = int(state.accumulated)
                state.accumulated -= ticks_to_fire

                if ticks_to_fire > 0:
                    for tick in range(ticks_to_fire):
                        state.tick_count += 1
                        ticks_to_dispatch.append((plane, state.tick_count, beat_num))

            # Count dispatches under lock (thread-safe)
            self._total_dispatches += len(ticks_to_dispatch)

        # FIX 2026-03-04 Nous: Queue dispatch instead of creating new Thread per heartbeat.
        # Persistent worker thread drains the queue — zero thread churn.
        if ticks_to_dispatch:
            try:
                self._dispatch_queue.put_nowait((ticks_to_dispatch, pulse_data))
            except queue.Full:
                pass  # Drop if backed up — next heartbeat will catch up

    def _dispatch_worker_loop(self):
        """Persistent worker that drains the dispatch queue.

        FIX 2026-03-04 Nous: Replaces per-heartbeat Thread() creation.
        One persistent daemon thread handles ALL temporal dispatch.
        No Future objects created — direct function calls.
        """
        while True:
            try:
                item = self._dispatch_queue.get(timeout=2.0)
            except queue.Empty:
                continue
            if item is None:  # Poison pill
                break
            ticks, pulse_data = item
            for plane, tick_num, beat_num in ticks:
                self._dispatch_plane_tick(plane, tick_num, beat_num, pulse_data)
            self._dispatch_queue.task_done()

    def _dispatch_plane_tick(self, plane: str, tick_num: int, beat_num: int, pulse_data: Dict):
        """Dispatch a tick to a plane — direct call, no futures.

        FIX 2026-03-04 Nous: Removed worker_pool.submit() which created
        Future/_WorkItem objects per dispatch (23 planes × 4Hz = 92 futures/sec).
        Direct calls in the persistent dispatch worker are sufficient —
        the worker thread IS the async context, no need for double-async.
        """
        tick_payload = {
            "plane": plane,
            "tick": tick_num,
            "heartbeat": beat_num,
            "timestamp": time.time(),
            "blood": pulse_data,
        }
        self._do_plane_dispatch(plane, tick_payload)
    
    def _do_plane_dispatch(self, plane: str, payload: Dict):
        """Actually dispatch to postal and direct subscribers."""
        
        # Postal broadcast
        if self._post:
            try:
                self._post.route(f"temporal.{plane.lower()}", payload)
            except Exception as e:
                pass
        
        # Direct subscribers
        for callback in self._plane_subscribers.get(plane, []):
            try:
                callback(payload)
            except Exception:
                pass
    
    def subscribe_plane(self, plane: str, callback: Callable):
        """Subscribe to ticks for a specific plane."""
        if plane in self._plane_subscribers:
            self._plane_subscribers[plane].append(callback)
    
    def get_stats(self) -> Dict:
        """Get dispatch statistics."""
        return {
            "heartbeats": self._heartbeat_count,
            "total_dispatches": self._total_dispatches,
            "planes": {
                p: {
                    "ticks": s.tick_count,
                    "hz": s.base_hz,
                    "multiplier": s.multiplier,
                }
                for p, s in self._planes.items()
            }
        }


# Singleton instance
_DISPATCHER: Optional[TemporalPulseDispatcher] = None

def get_temporal_dispatcher(post=None, worker_pool=None) -> TemporalPulseDispatcher:
    """Get or create the temporal dispatcher singleton."""
    global _DISPATCHER
    if _DISPATCHER is None:
        _DISPATCHER = TemporalPulseDispatcher(post=post, worker_pool=worker_pool)
    return _DISPATCHER
