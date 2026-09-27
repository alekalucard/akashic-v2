"""
GoBatteryClient - Python client for Go battery subprocess.

Follows the portal_plane_interior.py pattern: stdin/stdout JSON pipe.
Each plane's PlaneBattery owns one GoBatteryClient that manages a Go
subprocess (or Python fallback subprocess) for true CPU parallelism.

Protocol (JSON-per-line over stdin/stdout):

Python -> Subprocess:
    {"cmd": "submit", "task_id": "...", "priority": "HIGH|NORMAL|LOW", "payload": {...}}
    {"cmd": "stats"}
    {"cmd": "resize", "workers": N}
    {"cmd": "drain"}               -- complete all queued work, accept no new
    {"cmd": "ping"}
    {"cmd": "shutdown"}

Subprocess -> Python:
    {"event": "ready", "workers": N, "pid": NNN}
    {"event": "result", "task_id": "...", "status": "ok|error", "data": {...}, "duration_ms": N}
    {"event": "stats", "active": N, "queued": N, "completed": N, "p95_ms": N}
    {"event": "pong", "uptime_s": N}
    {"event": "drained", "completed": N}
    {"event": "shutdown_ack"}

Fallback cascade:
    1. Go binary (go_battery[.exe])       -- true goroutine parallelism
    2. Python subprocess (go_battery_interior.py) -- process isolation, GIL-bound
    3. None (PlaneBattery falls back to inline ThreadPoolExecutor)

Architecture: Ace (2026-02-26)
Implementation: Nous
"""

import json
import os
import sys
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

# ── Infrastructure Tracer ────────────────────────────────────────────────
_infra_tracer_ref = None
def _get_tracer():
    global _infra_tracer_ref
    if _infra_tracer_ref is not None:
        return _infra_tracer_ref
    try:
        from infrastructure.infra_tracer import get_infra_tracer
        _infra_tracer_ref = get_infra_tracer()
        _infra_tracer_ref.register_actor("go_battery", role="worker",
                                         description="Go/Python subprocess for parallel task execution")
        return _infra_tracer_ref
    except Exception:
        return None


# =============================================================================
# Configuration
# =============================================================================

# How long to wait for the subprocess to report "ready" after spawn
STARTUP_TIMEOUT_S = 10.0

# How long to wait for shutdown acknowledgment
SHUTDOWN_TIMEOUT_S = 5.0

# Max results buffered before oldest are dropped
RESULT_BUFFER_MAX = 4096

# How often the reader thread checks for subprocess death (seconds)
READER_POLL_INTERVAL_S = 0.1

# Binary search names (Go compiled binary)
GO_BINARY_NAMES = ["go_battery.exe", "go_battery"]

# Fallback script (Python subprocess)
FALLBACK_SCRIPT = "go_battery_interior.py"


# =============================================================================
# GoBatteryClient
# =============================================================================

class GoBatteryClient:
    """Python client for Go (or fallback Python) battery subprocess.

    Manages the subprocess lifecycle and provides a clean API for
    PlaneBattery to submit work and poll results.

    Thread safety: All public methods are thread-safe. The reader thread
    runs continuously, buffering results for poll_results() to consume.
    """

    def __init__(
        self,
        plane_id: str,
        binary_path: str = "",
        min_workers: int = 2,
        max_workers: int = 16,
    ):
        self.plane_id = plane_id
        self._binary_path = binary_path
        self._min_workers = min_workers
        self._max_workers = max_workers

        # Subprocess handle
        self._process: Optional[subprocess.Popen] = None
        self._pid: int = 0

        # Threading
        self._reader_thread: Optional[threading.Thread] = None
        self._write_lock = threading.Lock()
        self._result_lock = threading.Lock()
        self._ready_event = threading.Event()

        # Result buffer (deque = O(1) popleft, bounded)
        self._results: Deque[dict] = deque(maxlen=RESULT_BUFFER_MAX)

        # Stats cache (updated by reader thread from "stats" events)
        self._last_stats: dict = {}
        self._stats_lock = threading.Lock()

        # Lifecycle
        self._alive = False
        self._shutting_down = False
        self._using_fallback = False  # True if using Python fallback instead of Go

        # Counters
        self._submitted: int = 0
        self._completed: int = 0
        self._errors: int = 0
        self._started_at: float = 0.0

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_alive(self) -> bool:
        """True if subprocess is running and responsive."""
        if not self._alive:
            return False
        if self._process and self._process.poll() is not None:
            # Process died unexpectedly
            self._alive = False
            return False
        return True

    @property
    def using_fallback(self) -> bool:
        """True if using Python fallback instead of Go binary."""
        return self._using_fallback

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self) -> bool:
        """Start the battery subprocess.

        Tries Go binary first, falls back to Python subprocess.
        Returns True if subprocess started successfully.
        """
        if self._alive:
            return True

        # Resolve binary path
        binary = self._binary_path or self.find_binary()
        if binary and Path(binary).suffix in (".py",):
            # It's a Python script — use interpreter
            cmd = [sys.executable, binary]
            self._using_fallback = True
        elif binary:
            cmd = [binary]
            self._using_fallback = False
        else:
            # No binary found — try Python fallback
            fallback = self.find_fallback()
            if fallback:
                cmd = [sys.executable, fallback]
                self._using_fallback = True
            else:
                print(f"[GoBattery:{self.plane_id}] No binary or fallback found")
                return False

        # Spawn subprocess
        try:
            self._process = subprocess.Popen(
                cmd + [
                    "--plane", self.plane_id,
                    "--min-workers", str(self._min_workers),
                    "--max-workers", str(self._max_workers),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,  # Line-buffered
                text=True,
                cwd=str(Path(__file__).parent.parent),  # Project root
            )
        except Exception as e:
            print(f"[GoBattery:{self.plane_id}] Failed to spawn: {e}")
            return False

        self._pid = self._process.pid
        self._started_at = time.time()

        # Start reader thread (reads stdout for events)
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"go_battery_reader_{self.plane_id}",
            daemon=True,
        )
        self._reader_thread.start()

        # Start stderr drain thread (prevents pipe deadlock)
        _stderr_thread = threading.Thread(
            target=self._stderr_drain,
            name=f"go_battery_stderr_{self.plane_id}",
            daemon=True,
        )
        _stderr_thread.start()

        # Wait for "ready" event from subprocess
        mode = "fallback" if self._using_fallback else "go"
        if self._ready_event.wait(timeout=STARTUP_TIMEOUT_S):
            self._alive = True
            print(f"[GoBattery:{self.plane_id}] Started (pid={self._pid},"
                  f" mode={mode}, workers={self._min_workers}-{self._max_workers})")
            # ── Trace subprocess spawn ──
            _t = _get_tracer()
            if _t:
                _t.lifecycle("go_battery", "subprocess_spawned", {
                    "plane": self.plane_id, "pid": self._pid,
                    "mode": mode, "workers": f"{self._min_workers}-{self._max_workers}",
                })
            return True
        else:
            print(f"[GoBattery:{self.plane_id}] Startup timeout ({STARTUP_TIMEOUT_S}s)")
            _t = _get_tracer()
            if _t:
                _t.emit("go_battery", "subprocess_timeout", {
                    "plane": self.plane_id, "timeout_s": STARTUP_TIMEOUT_S,
                }, severity="error")
            self._kill_process()
            return False

    def stop(self, timeout: float = SHUTDOWN_TIMEOUT_S) -> bool:
        """Gracefully stop the subprocess.

        Sends shutdown command and waits for acknowledgment.
        Falls back to kill after timeout.
        """
        if not self._process:
            self._alive = False
            return True

        self._shutting_down = True

        # Send shutdown command
        try:
            self._send({"cmd": "shutdown"})
        except Exception:
            pass

        # Wait for process to exit
        try:
            self._process.wait(timeout=timeout)
            self._alive = False
            print(f"[GoBattery:{self.plane_id}] Stopped gracefully")
            _t = _get_tracer()
            if _t:
                _t.lifecycle("go_battery", "subprocess_stopped", {
                    "plane": self.plane_id, "submitted": self._submitted,
                    "completed": self._completed, "errors": self._errors,
                })
            return True
        except subprocess.TimeoutExpired:
            print(f"[GoBattery:{self.plane_id}] Shutdown timeout, killing")
            _t = _get_tracer()
            if _t:
                _t.emit("go_battery", "subprocess_force_killed", {
                    "plane": self.plane_id, "pid": self._pid,
                }, severity="warning")
            self._kill_process()
            return False

    def _kill_process(self):
        """Force-kill the subprocess."""
        if self._process:
            try:
                self._process.kill()
                self._process.wait(timeout=2.0)
            except Exception:
                pass
        self._alive = False

    # =========================================================================
    # Communication
    # =========================================================================

    def _send(self, msg: dict) -> bool:
        """Send a JSON message to the subprocess stdin.

        Thread-safe: protected by write lock.
        Returns True if sent successfully.
        """
        if not self._process or not self._process.stdin:
            return False

        with self._write_lock:
            try:
                line = json.dumps(msg, separators=(",", ":")) + "\n"
                self._process.stdin.write(line)
                self._process.stdin.flush()
                return True
            except (BrokenPipeError, OSError, ValueError):
                self._alive = False
                return False

    def _reader_loop(self):
        """Background thread: read JSON events from subprocess stdout."""
        while True:
            if not self._process or not self._process.stdout:
                break

            try:
                line = self._process.stdout.readline()
            except (ValueError, OSError):
                break

            if not line:
                # EOF — process exited
                break

            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = msg.get("event", "")

            if event == "ready":
                self._ready_event.set()

            elif event == "result":
                with self._result_lock:
                    self._results.append(msg)
                    self._completed += 1

            elif event == "stats":
                with self._stats_lock:
                    self._last_stats = msg

            elif event == "pong":
                pass  # Liveness confirmed

            elif event == "drained":
                pass  # Drain complete

            elif event == "shutdown_ack":
                break

        # Mark as dead when reader exits
        if not self._shutting_down:
            self._alive = False

    def _stderr_drain(self):
        """Background thread: drain stderr to prevent pipe deadlock.

        Optionally logs subprocess output for debugging.
        """
        while True:
            if not self._process or not self._process.stderr:
                break
            try:
                line = self._process.stderr.readline()
            except (ValueError, OSError):
                break
            if not line:
                break
            # Log subprocess stderr with prefix
            stripped = line.rstrip()
            if stripped:
                print(f"[GoBattery:{self.plane_id}:sub] {stripped}")

    # =========================================================================
    # Task API (called by PlaneBattery)
    # =========================================================================

    def submit_task(
        self,
        task_id: str,
        priority: str = "NORMAL",
        payload: Optional[dict] = None,
    ) -> bool:
        """Submit a task to the subprocess.

        Args:
            task_id: Unique ID for this task (for matching results)
            priority: "HIGH", "NORMAL", or "LOW"
            payload: JSON-serializable task data

        Returns:
            True if submitted successfully
        """
        if not self.is_alive:
            return False

        msg = {
            "cmd": "submit",
            "task_id": task_id,
            "priority": priority,
            "payload": payload or {},
        }

        success = self._send(msg)
        if success:
            self._submitted += 1
        return success

    def poll_results(self, max_results: int = 32) -> List[dict]:
        """Poll for completed task results.

        Non-blocking: returns immediately with whatever results are available.

        Returns:
            List of result dicts: {"task_id": ..., "status": "ok|error",
                                   "data": {...}, "duration_ms": N}
        """
        results = []
        with self._result_lock:
            while self._results and len(results) < max_results:
                results.append(self._results.popleft())
        return results

    def get_stats(self) -> dict:
        """Get subprocess performance stats.

        Returns cached stats from last "stats" event, plus client-side counters.
        Also sends a fresh stats request (response arrives asynchronously).
        """
        # Request fresh stats (will be picked up by reader thread)
        if self.is_alive:
            self._send({"cmd": "stats"})

        with self._stats_lock:
            stats = dict(self._last_stats)

        stats.update({
            "client_submitted": self._submitted,
            "client_completed": self._completed,
            "client_errors": self._errors,
            "client_result_buffer": len(self._results),
            "uptime_s": round(time.time() - self._started_at, 1) if self._started_at else 0,
            "using_fallback": self._using_fallback,
        })
        return stats

    def resize(self, workers: int) -> bool:
        """Request subprocess to resize worker pool.

        Args:
            workers: New worker count (clamped to min/max)
        """
        if not self.is_alive:
            return False
        workers = max(self._min_workers, min(workers, self._max_workers))
        return self._send({"cmd": "resize", "workers": workers})

    def drain(self) -> bool:
        """Request subprocess to drain: complete queued work, reject new."""
        if not self.is_alive:
            return False
        return self._send({"cmd": "drain"})

    def ping(self) -> bool:
        """Send a ping to check liveness."""
        return self._send({"cmd": "ping"})

    # =========================================================================
    # Binary / fallback discovery
    # =========================================================================

    @classmethod
    def find_binary(cls) -> Optional[str]:
        """Find Go battery binary in standard locations.

        Search order:
            1. Project root (akashic_v2/)
            2. Project bin/ directory
            3. tracer_pool/ directory (alongside Go sources)
            4. PATH

        Returns:
            Absolute path to binary, or None if not found.
        """
        project_root = Path(__file__).parent.parent

        # Search directories
        search_dirs = [
            project_root,
            project_root / "bin",
            project_root / "tracer_pool",
            project_root / "tracer_pool" / "build",
        ]

        for search_dir in search_dirs:
            for name in GO_BINARY_NAMES:
                candidate = search_dir / name
                if candidate.exists() and candidate.is_file():
                    return str(candidate.resolve())

        # Check PATH
        import shutil
        for name in GO_BINARY_NAMES:
            found = shutil.which(name)
            if found:
                return found

        return None

    @classmethod
    def find_fallback(cls) -> Optional[str]:
        """Find Python fallback script.

        Returns:
            Absolute path to go_battery_interior.py, or None.
        """
        project_root = Path(__file__).parent.parent
        fallback = project_root / FALLBACK_SCRIPT
        if fallback.exists():
            return str(fallback.resolve())
        return None

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def status(self) -> dict:
        """Get comprehensive client status."""
        return {
            "plane_id": self.plane_id,
            "alive": self.is_alive,
            "pid": self._pid,
            "using_fallback": self._using_fallback,
            "submitted": self._submitted,
            "completed": self._completed,
            "errors": self._errors,
            "result_buffer_size": len(self._results),
            "uptime_s": round(time.time() - self._started_at, 1) if self._started_at else 0,
        }

    def __repr__(self):
        mode = "fallback" if self._using_fallback else "go"
        alive = "alive" if self.is_alive else "dead"
        return (f"GoBatteryClient({self.plane_id}, {mode}, {alive},"
                f" submitted={self._submitted}, completed={self._completed})")
