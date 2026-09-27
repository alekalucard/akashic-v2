#!/usr/bin/env python3
"""
Go Battery Interior — Python fallback subprocess for PlaneBattery.

This is the "interior" of the Go battery dimension. It implements the
exact same JSON protocol that a Go binary would, using Python's
concurrent.futures.ThreadPoolExecutor for parallelism.

Serves two purposes:
    1. RUNNABLE FALLBACK: When no Go binary exists, PlaneBattery spawns
       this script as a subprocess. Process isolation, GIL-bound.
    2. INTERFACE SPEC: Documents exactly what a Go binary must implement.
       Build the Go version to match this protocol.

Protocol (JSON-per-line over stdin/stdout):

    INPUT (stdin):
        {"cmd": "submit", "task_id": "...", "priority": "HIGH|NORMAL|LOW", "payload": {...}}
        {"cmd": "stats"}
        {"cmd": "resize", "workers": N}
        {"cmd": "drain"}
        {"cmd": "ping"}
        {"cmd": "shutdown"}

    OUTPUT (stdout):
        {"event": "ready", "workers": N, "pid": NNN}
        {"event": "result", "task_id": "...", "status": "ok|error", "data": {...}, "duration_ms": N}
        {"event": "stats", "active": N, "queued": N, "completed": N, "p95_ms": N}
        {"event": "pong", "uptime_s": N}
        {"event": "drained", "completed": N}
        {"event": "shutdown_ack"}

    LOGGING (stderr):
        Human-readable messages. Never JSON. Never stdout.

Go binary spec (future implementation):
    - 3 priority lanes (HIGH, NORMAL, LOW) with priority scheduling
    - Autoscale workers every 250ms based on queue depth
    - Backpressure: when HIGH+NORMAL queued > 80% capacity, drop oldest LOW
    - Mirrors tracer_pool/internal/pool/pool.go pattern
    - Signal handling: SIGTERM -> drain -> shutdown_ack -> exit

Usage:
    python go_battery_interior.py --plane P30 --min-workers 2 --max-workers 16

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
Architecture: Ace (2026-02-26)
Implementation: Nous
"""

import argparse
import json
import os
import sys
import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Deque, Dict, List, Optional


# =============================================================================
# Logging — stderr only, stdout is SACRED (JSON pipe)
# =============================================================================

def _log(msg: str):
    """Log to stderr. Never stdout."""
    print(msg, file=sys.stderr, flush=True)


def _emit(msg: dict):
    """Emit a JSON event to stdout. Thread-safe via lock."""
    global _stdout_lock
    line = json.dumps(msg, separators=(",", ":"))
    with _stdout_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


_stdout_lock = threading.Lock()


# =============================================================================
# Task Executor — Priority lanes with ThreadPoolExecutor
# =============================================================================

class PriorityTaskExecutor:
    """Three-lane priority task executor.

    HIGH:   Spell chain critical path, gate decisions
    NORMAL: Regular fairy work, periodic tasks
    LOW:    Background processing, cleanup, speculative work

    Scheduling: HIGH always runs first. NORMAL when no HIGH pending.
    LOW only when both HIGH and NORMAL are empty.

    Backpressure: When total queued > 80% of capacity, drop oldest LOW tasks.
    """

    PRIORITY_ORDER = {"HIGH": 0, "NORMAL": 1, "LOW": 2}

    def __init__(self, min_workers: int = 2, max_workers: int = 16):
        self._min_workers = min_workers
        self._max_workers = max_workers
        self._current_workers = min_workers

        # Priority queues
        self._high_queue: Deque[dict] = deque()
        self._normal_queue: Deque[dict] = deque()
        self._low_queue: Deque[dict] = deque()

        # Thread pool
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_futures: Dict[str, Future] = {}

        # State
        self._lock = threading.Lock()
        self._running = False
        self._draining = False

        # Scheduler thread
        self._scheduler_thread: Optional[threading.Thread] = None

        # Stats
        self._completed: int = 0
        self._dropped: int = 0
        self._errors: int = 0
        self._durations_ms: Deque[float] = deque(maxlen=1000)  # For percentile calc
        self._started_at: float = 0.0

    def start(self):
        """Start the executor and scheduler."""
        self._executor = ThreadPoolExecutor(
            max_workers=self._current_workers,
            thread_name_prefix="go_battery_worker",
        )
        self._running = True
        self._started_at = time.time()

        # Scheduler: pulls tasks from priority queues and submits to executor
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="go_battery_scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()

    def stop(self, drain_first: bool = True):
        """Stop the executor.

        Args:
            drain_first: If True, complete all queued work before stopping.
        """
        if drain_first:
            self._draining = True
            # Wait for queues to drain (max 30s)
            deadline = time.time() + 30.0
            while time.time() < deadline:
                with self._lock:
                    total = (len(self._high_queue) + len(self._normal_queue) +
                             len(self._low_queue) + len(self._active_futures))
                if total == 0:
                    break
                time.sleep(0.1)

        self._running = False
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=not drain_first)
            self._executor = None

    def submit(self, task: dict):
        """Submit a task to the appropriate priority lane."""
        if self._draining:
            return  # Reject new work during drain

        priority = task.get("priority", "NORMAL").upper()
        with self._lock:
            if priority == "HIGH":
                self._high_queue.append(task)
            elif priority == "LOW":
                self._low_queue.append(task)
            else:
                self._normal_queue.append(task)

            # Backpressure: drop oldest LOW if overloaded
            capacity = self._current_workers * 4  # 4x workers = queue limit
            total_queued = len(self._high_queue) + len(self._normal_queue) + len(self._low_queue)
            if total_queued > capacity * 0.8 and self._low_queue:
                dropped = self._low_queue.popleft()
                self._dropped += 1
                task_id = dropped.get("task_id", "unknown")
                _emit({
                    "event": "result",
                    "task_id": task_id,
                    "status": "dropped",
                    "data": {"reason": "backpressure"},
                    "duration_ms": 0,
                })

    def resize(self, workers: int):
        """Resize the worker pool."""
        workers = max(self._min_workers, min(workers, self._max_workers))
        if workers == self._current_workers:
            return

        old = self._current_workers
        self._current_workers = workers

        # Recreate executor with new size (existing tasks continue)
        if self._executor:
            old_executor = self._executor
            self._executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="go_battery_worker",
            )
            # Let old executor drain naturally (daemon threads)
            try:
                old_executor.shutdown(wait=False)
            except Exception:
                pass

        _log(f"[BatteryInterior] Resized {old} -> {workers} workers")

    def stats(self) -> dict:
        """Get executor statistics."""
        with self._lock:
            queued = len(self._high_queue) + len(self._normal_queue) + len(self._low_queue)
            active = len(self._active_futures)

        p95_ms = 0
        if self._durations_ms:
            sorted_d = sorted(self._durations_ms)
            idx = int(len(sorted_d) * 0.95)
            p95_ms = round(sorted_d[min(idx, len(sorted_d) - 1)], 1)

        return {
            "active": active,
            "queued": queued,
            "queued_high": len(self._high_queue),
            "queued_normal": len(self._normal_queue),
            "queued_low": len(self._low_queue),
            "completed": self._completed,
            "dropped": self._dropped,
            "errors": self._errors,
            "workers": self._current_workers,
            "p95_ms": p95_ms,
            "uptime_s": round(time.time() - self._started_at, 1),
        }

    def _scheduler_loop(self):
        """Pull tasks from priority queues, submit to ThreadPoolExecutor."""
        while self._running:
            task = None

            with self._lock:
                # Priority order: HIGH > NORMAL > LOW
                if self._high_queue:
                    task = self._high_queue.popleft()
                elif self._normal_queue:
                    task = self._normal_queue.popleft()
                elif self._low_queue:
                    task = self._low_queue.popleft()

                # Don't exceed worker count in active futures
                if task and len(self._active_futures) >= self._current_workers:
                    # Put it back, wait for a slot
                    priority = task.get("priority", "NORMAL").upper()
                    if priority == "HIGH":
                        self._high_queue.appendleft(task)
                    elif priority == "LOW":
                        self._low_queue.appendleft(task)
                    else:
                        self._normal_queue.appendleft(task)
                    task = None

            if task:
                self._dispatch_task(task)
            else:
                # No work — sleep briefly
                time.sleep(0.01)

    def _dispatch_task(self, task: dict):
        """Submit a task to the ThreadPoolExecutor."""
        if not self._executor:
            return

        task_id = task.get("task_id", f"anon_{time.time()}")

        try:
            future = self._executor.submit(self._execute_task, task)
            with self._lock:
                self._active_futures[task_id] = future

            # Callback to clean up when done
            future.add_done_callback(lambda f, tid=task_id: self._on_task_done(tid, f))
        except Exception as e:
            _emit({
                "event": "result",
                "task_id": task_id,
                "status": "error",
                "data": {"error": str(e)},
                "duration_ms": 0,
            })
            self._errors += 1

    def _execute_task(self, task: dict) -> dict:
        """Execute a single task. Runs in worker thread.

        This is the fallback executor — it simulates work for protocol testing.
        In the real Go binary, this would be actual goroutine-dispatched work.

        The payload contains:
            spell_id, what_intent, who_plane, how_method_name, how_kwargs
        """
        start_ms = time.time() * 1000
        task_id = task.get("task_id", "")
        payload = task.get("payload", {})

        try:
            # In fallback mode, we simulate the work
            # A real Go binary would invoke the actual method/intent
            method_name = payload.get("how_method_name", "")
            intent = payload.get("what_intent", "")
            kwargs = payload.get("how_kwargs", {})

            # If there's a callable packed (won't be in subprocess, but
            # for inline testing), execute it
            if callable(kwargs.get("_callable")):
                result_data = kwargs["_callable"]()
            else:
                # Simulate work (1-5ms per task in fallback)
                time.sleep(0.001 + hash(task_id) % 4 * 0.001)
                result_data = {
                    "method": method_name,
                    "intent": intent,
                    "simulated": True,
                }

            duration_ms = time.time() * 1000 - start_ms
            return {
                "task_id": task_id,
                "status": "ok",
                "data": result_data,
                "duration_ms": round(duration_ms, 1),
            }

        except Exception as e:
            duration_ms = time.time() * 1000 - start_ms
            return {
                "task_id": task_id,
                "status": "error",
                "data": {"error": str(e)},
                "duration_ms": round(duration_ms, 1),
            }

    def _on_task_done(self, task_id: str, future: Future):
        """Callback when a task completes."""
        with self._lock:
            self._active_futures.pop(task_id, None)

        try:
            result = future.result(timeout=0)
        except Exception as e:
            result = {
                "task_id": task_id,
                "status": "error",
                "data": {"error": str(e)},
                "duration_ms": 0,
            }
            self._errors += 1

        self._completed += 1
        duration = result.get("duration_ms", 0)
        self._durations_ms.append(duration)

        # Emit result to stdout
        _emit({"event": "result", **result})


# =============================================================================
# Main Loop — stdin command processor
# =============================================================================

class BatteryInterior:
    """The battery subprocess main loop.

    Reads JSON commands from stdin, dispatches to PriorityTaskExecutor,
    emits events to stdout.
    """

    def __init__(self, plane_id: str, min_workers: int = 2, max_workers: int = 16):
        self.plane_id = plane_id
        self._executor = PriorityTaskExecutor(
            min_workers=min_workers,
            max_workers=max_workers,
        )
        self._running = False
        self._started_at = time.time()

    def run(self):
        """Main loop: read stdin, process commands, emit events."""
        # Start executor
        self._executor.start()
        self._running = True

        # Announce ready
        _emit({
            "event": "ready",
            "workers": self._executor._current_workers,
            "pid": os.getpid(),
            "plane_id": self.plane_id,
            "mode": "python_fallback",
        })

        _log(f"[BatteryInterior:{self.plane_id}] Ready"
             f" (pid={os.getpid()}, workers={self._executor._min_workers}"
             f"-{self._executor._max_workers})")

        # Read stdin line by line
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    _log(f"[BatteryInterior] Bad JSON: {line[:100]}")
                    continue

                cmd = msg.get("cmd", "")

                if cmd == "submit":
                    self._executor.submit(msg)

                elif cmd == "stats":
                    stats = self._executor.stats()
                    _emit({"event": "stats", **stats})

                elif cmd == "resize":
                    workers = msg.get("workers", self._executor._current_workers)
                    self._executor.resize(workers)
                    _emit({"event": "stats", **self._executor.stats()})

                elif cmd == "drain":
                    self._executor._draining = True
                    _log(f"[BatteryInterior:{self.plane_id}] Draining...")
                    # Drain happens asynchronously; we report when empty
                    threading.Thread(
                        target=self._drain_and_report,
                        daemon=True,
                    ).start()

                elif cmd == "ping":
                    _emit({
                        "event": "pong",
                        "uptime_s": round(time.time() - self._started_at, 1),
                        "plane_id": self.plane_id,
                    })

                elif cmd == "shutdown":
                    _log(f"[BatteryInterior:{self.plane_id}] Shutdown requested")
                    break

                else:
                    _log(f"[BatteryInterior] Unknown command: {cmd}")

        except (EOFError, KeyboardInterrupt):
            _log(f"[BatteryInterior:{self.plane_id}] Stdin closed")

        # Graceful shutdown
        self._running = False
        self._executor.stop(drain_first=True)

        _emit({"event": "shutdown_ack", "plane_id": self.plane_id})
        _log(f"[BatteryInterior:{self.plane_id}] Shutdown complete"
             f" (completed={self._executor._completed})")

    def _drain_and_report(self):
        """Wait for queues to empty, then report drained."""
        deadline = time.time() + 30.0
        while time.time() < deadline:
            stats = self._executor.stats()
            if stats["queued"] == 0 and stats["active"] == 0:
                break
            time.sleep(0.1)

        _emit({
            "event": "drained",
            "completed": self._executor._completed,
            "plane_id": self.plane_id,
        })
        _log(f"[BatteryInterior:{self.plane_id}] Drain complete")


# =============================================================================
# Entry point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Go Battery Interior (Python fallback)")
    parser.add_argument("--plane", default="P00", help="Plane ID (P00-P60)")
    parser.add_argument("--min-workers", type=int, default=2, help="Minimum workers")
    parser.add_argument("--max-workers", type=int, default=16, help="Maximum workers")
    args = parser.parse_args()

    interior = BatteryInterior(
        plane_id=args.plane,
        min_workers=args.min_workers,
        max_workers=args.max_workers,
    )
    interior.run()


if __name__ == "__main__":
    main()
