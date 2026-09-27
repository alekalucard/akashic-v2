"""
Process Worker Pool — Separate-process computation for heavy fairies.

NOTE (2026-03-14): With Python 3.14 free-threaded (no GIL), threads already
run in true parallel. The original motivation (GIL bypass) is largely obsolete.
This pool is now LAZY — only starts if a fairy actually calls .submit().
For most CPU-bound work, regular threads are sufficient on free-threaded Python.

This module runs heavy computations in SEPARATE PROCESSES for cases where
full interpreter isolation is needed (e.g., conflicting C extension state).

The pattern: most fairy work is "receive message -> compute -> publish result".
Messaging stays in the main process, heavy computation goes to workers.

Usage:
    from infrastructure.process_worker import fairy_worker_pool

    # Submit CPU-bound work (runs in separate process with own GIL)
    future = fairy_worker_pool.submit(expensive_function, arg1, arg2)
    result = future.result(timeout=30)  # blocks, but releasing GIL

    # Or with callback (non-blocking)
    future = fairy_worker_pool.submit(expensive_function, arg1, arg2)
    future.add_done_callback(lambda f: post.publish("result", f.result()))

    # For repeated work patterns, register a named worker:
    fairy_worker_pool.register_worker("cortex_bind", bind_concepts_func)
    result = fairy_worker_pool.run("cortex_bind", concepts, context)

IMPORTANT: Functions submitted to the pool must be:
    1. Top-level functions (not methods) — or use functools.partial
    2. Arguments must be picklable (dicts, lists, strings, numbers, numpy arrays)
    3. Return values must be picklable

For fairy methods, use the pattern:
    def _heavy_compute(data_dict):
        '''Top-level function that can run in worker process.'''
        # Import heavy modules HERE (only loaded in worker process)
        import numpy as np
        result = np.expensive_operation(data_dict["input"])
        return {"output": result.tolist()}

    class MyFairy:
        def _on_message(self, msg):
            future = fairy_worker_pool.submit(_heavy_compute, {"input": msg["data"]})
            future.add_done_callback(self._on_result)

        def _on_result(self, future):
            try:
                result = future.result()
                self.post.publish("my.output", result)
            except Exception as e:
                print(f"Worker failed: {e}")
"""

import os
import time
import threading
from concurrent.futures import ProcessPoolExecutor, Future
from typing import Any, Callable, Dict, Optional


class FairyWorkerPool:
    """Process pool for offloading heavy fairy computation.

    Creates a fixed pool of worker processes, each with its own Python
    interpreter and GIL. Work submitted here does NOT contend with the
    main process's 160+ threads.

    Thread-safe: multiple fairies can submit work concurrently.
    """

    def __init__(self, max_workers: int = 0, name: str = "fairy-workers"):
        """Initialize the process worker pool.

        Args:
            max_workers: Number of worker processes. 0 = auto (cpu_count // 4,
                        minimum 2, maximum 4). We don't want too many because
                        each process consumes ~50-100MB RAM.
            name: Pool name for logging.
        """
        if max_workers <= 0:
            cpu = os.cpu_count() or 4
            max_workers = max(2, min(4, cpu // 4))

        self._name = name
        self._max_workers = max_workers
        self._pool: Optional[ProcessPoolExecutor] = None
        self._started = False
        self._lock = threading.Lock()

        # Stats
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        self._total_time_ms = 0.0

        # Named workers (registered functions)
        self._named_workers: Dict[str, Callable] = {}

    def start(self):
        """Start the process pool. Called lazily on first submit."""
        with self._lock:
            if self._started:
                return
            try:
                self._pool = ProcessPoolExecutor(
                    max_workers=self._max_workers,
                    # mp_context ensures clean forking on Windows
                )
                self._started = True
                print(f"[{self._name}] Started {self._max_workers} worker processes (separate interpreters)")
            except Exception as e:
                print(f"[{self._name}] Failed to start: {e}")
                self._pool = None

    def submit(self, fn: Callable, *args, **kwargs) -> Optional[Future]:
        """Submit work to a worker process.

        Args:
            fn: Top-level function to execute (must be picklable)
            *args, **kwargs: Arguments (must be picklable)

        Returns:
            Future that resolves to the function's return value,
            or None if pool isn't available.
        """
        if not self._started:
            self.start()

        if not self._pool:
            # Fallback: run in main process (degraded but functional)
            return self._fallback_submit(fn, *args, **kwargs)

        try:
            t0 = time.time()
            future = self._pool.submit(fn, *args, **kwargs)
            self._submitted += 1

            def _on_done(f):
                elapsed = (time.time() - t0) * 1000
                self._total_time_ms += elapsed
                if f.exception():
                    self._failed += 1
                else:
                    self._completed += 1

            future.add_done_callback(_on_done)
            return future
        except Exception as e:
            print(f"[{self._name}] Submit failed: {e}")
            return self._fallback_submit(fn, *args, **kwargs)

    def _fallback_submit(self, fn, *args, **kwargs):
        """Run in main process as fallback (degraded performance)."""
        future = Future()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future

    def register_worker(self, name: str, fn: Callable):
        """Register a named worker function.

        Args:
            name: Worker name (e.g., "cortex_bind", "inference_forward")
            fn: Top-level function to call
        """
        self._named_workers[name] = fn

    def run(self, worker_name: str, *args, **kwargs) -> Optional[Future]:
        """Run a named worker.

        Args:
            worker_name: Previously registered worker name
            *args, **kwargs: Arguments to pass

        Returns:
            Future with result.
        """
        fn = self._named_workers.get(worker_name)
        if not fn:
            raise ValueError(f"Unknown worker: {worker_name}. "
                           f"Registered: {list(self._named_workers.keys())}")
        return self.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True):
        """Shutdown the process pool."""
        if self._pool:
            print(f"[{self._name}] Shutting down {self._max_workers} workers "
                  f"({self._completed} completed, {self._failed} failed)")
            self._pool.shutdown(wait=wait)
            self._pool = None
            self._started = False

    def status(self) -> dict:
        """Get pool status."""
        return {
            "name": self._name,
            "started": self._started,
            "max_workers": self._max_workers,
            "submitted": self._submitted,
            "completed": self._completed,
            "failed": self._failed,
            "avg_time_ms": round(self._total_time_ms / max(1, self._completed + self._failed), 1),
            "named_workers": list(self._named_workers.keys()),
        }


# ── Module-level singleton ──────────────────────────────────────────────
# Lazy-initialized on first use
fairy_worker_pool = FairyWorkerPool(name="fairy-workers")


def get_pool() -> FairyWorkerPool:
    """Get the global fairy worker pool.

    Convenience function for fairies:
        from infrastructure.process_worker import get_pool
        future = get_pool().submit(expensive_fn, data)
    """
    return fairy_worker_pool
