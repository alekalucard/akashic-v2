"""
WorkerEquilibrium - CPU/GPU/Satellite Load Balancing Coordinator

Monitors CPU, GPU, AND satellite utilization and routes tasks intelligently:
- GPU-required tasks → GPU pool (or satellite if local GPU saturated)
- CPU-capable tasks → route based on current load
- Satellite-preferred tasks → remote satellites when available
- Implements backpressure when resources are saturated

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

"System seeks balance - distribute the load"
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class TaskAffinity(Enum):
    """Where a task can/should run."""
    GPU_REQUIRED = "gpu_required"           # Must run on GPU (CUDA ops, inference)
    GPU_PREFERRED = "gpu_preferred"         # Faster on GPU but can use CPU
    CPU_PREFERRED = "cpu_preferred"         # Faster on CPU but can use GPU
    CPU_ONLY = "cpu_only"                   # Cannot use GPU
    SATELLITE_PREFERRED = "satellite_pref"  # Prefer remote satellite (offload heavy work)
    SATELLITE_GPU = "satellite_gpu"         # Prefer satellite GPU specifically
    ANY = "any"                             # Doesn't matter


@dataclass
class ResourceState:
    """Current state of a resource (CPU or GPU)."""
    utilization: float = 0.0       # 0.0 - 1.0
    queue_depth: int = 0           # Pending tasks
    active_tasks: int = 0          # Running tasks
    memory_pressure: float = 0.0   # For GPU: VRAM pressure
    last_sampled: float = 0.0

    @property
    def load_score(self) -> float:
        """Combined load score (0.0 = idle, 1.0 = saturated)."""
        util_weight = 0.5
        queue_weight = 0.3
        memory_weight = 0.2

        queue_factor = min(1.0, self.queue_depth / 50.0)

        return (
            self.utilization * util_weight +
            queue_factor * queue_weight +
            self.memory_pressure * memory_weight
        )


@dataclass
class EquilibriumConfig:
    """Configuration for load balancing."""
    # Thresholds
    gpu_high_threshold: float = 0.7         # Route away from GPU above this
    cpu_high_threshold: float = 0.8         # Route away from CPU above this
    satellite_high_threshold: float = 0.6   # Route away from satellite above this
    critical_threshold: float = 0.95        # Drop low priority tasks

    # Sampling
    sample_interval_sec: float = 2.0        # How often to sample resources

    # Throttling
    min_think_interval_sec: float = 5.0     # Min time between Ollama calls
    max_think_interval_sec: float = 60.0    # Max time between Ollama calls

    # Backpressure
    max_queue_depth: int = 100              # Start dropping when exceeded

    # Satellite preferences
    prefer_satellite_when_gpu_above: float = 0.7  # Route to satellite when local GPU above this
    satellite_latency_penalty: float = 0.1        # Penalty for satellite routing (network overhead)


class WorkerEquilibrium:
    """
    Coordinates load between CPU and GPU worker pools.

    Makes intelligent routing decisions based on:
    - Current utilization of each resource
    - Task affinity (what CAN it run on)
    - Queue depths (backpressure)
    - Memory pressure (especially GPU VRAM)
    """

    def __init__(self, config: Optional[EquilibriumConfig] = None):
        self.config = config or EquilibriumConfig()

        # Resource states
        self.cpu_state = ResourceState()
        self.gpu_state = ResourceState()
        self.satellite_state = ResourceState()  # Aggregate satellite state

        # References to pools (set via wire_*)
        self._cpu_pool = None
        self._gpu_pool = None
        self._satellite_bridge = None  # SatelliteBridgeFairy reference

        # Throttle state
        self._last_gpu_think = 0.0
        self._think_interval = self.config.min_think_interval_sec

        # Metrics
        self._routing_decisions = {
            "to_cpu": 0,
            "to_gpu": 0,
            "to_satellite": 0,
            "dropped": 0,
            "throttled": 0,
        }

        # Satellite availability
        self._satellites_available = 0
        self._satellite_gpu_available = False

        # Lock
        self._lock = threading.Lock()

        # Sampling thread
        self._running = False
        self._sample_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the equilibrium monitor."""
        if self._running:
            return

        self._running = True
        self._sample_thread = threading.Thread(
            target=self._sample_loop,
            daemon=True,
            name="equilibrium_sampler"
        )
        self._sample_thread.start()
        print("[WorkerEquilibrium] Started monitoring")

    def stop(self) -> None:
        """Stop the equilibrium monitor."""
        self._running = False
        if self._sample_thread:
            self._sample_thread.join(timeout=2.0)
        print("[WorkerEquilibrium] Stopped")

    def wire_cpu_pool(self, pool) -> None:
        """Wire to CPU worker pool."""
        self._cpu_pool = pool
        print("[WorkerEquilibrium] Wired to CPU pool")

    def wire_gpu_pool(self, pool) -> None:
        """Wire to GPU worker pool."""
        self._gpu_pool = pool
        print("[WorkerEquilibrium] Wired to GPU pool")

    def wire_satellite_bridge(self, bridge) -> None:
        """Wire to satellite bridge fairy."""
        self._satellite_bridge = bridge
        print("[WorkerEquilibrium] Wired to satellite bridge")

    # =========================================================================
    # SAMPLING
    # =========================================================================

    def _sample_loop(self) -> None:
        """Continuously sample resource states."""
        while self._running:
            try:
                self._sample_resources()
                self._adjust_throttle()
            except Exception as e:
                print(f"[WorkerEquilibrium] Sample error: {e}")

            time.sleep(self.config.sample_interval_sec)

    def _sample_resources(self) -> None:
        """Sample current resource utilization."""
        now = time.time()

        # Sample CPU
        try:
            import psutil
            self.cpu_state.utilization = psutil.cpu_percent() / 100.0
            self.cpu_state.last_sampled = now

            if self._cpu_pool:
                status = self._cpu_pool.get_status() if hasattr(self._cpu_pool, 'get_status') else {}
                queues = status.get("queues", {})
                self.cpu_state.queue_depth = queues.get("pending_atoms", 0)
                self.cpu_state.active_tasks = queues.get("pending_futures", 0)
        except Exception:
            pass

        # Sample GPU
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 3:
                    self.gpu_state.utilization = float(parts[0]) / 100.0
                    mem_used = float(parts[1])
                    mem_total = float(parts[2])
                    self.gpu_state.memory_pressure = mem_used / mem_total if mem_total > 0 else 0
                    self.gpu_state.last_sampled = now

            if self._gpu_pool:
                status = self._gpu_pool.status() if hasattr(self._gpu_pool, 'status') else {}
                self.gpu_state.queue_depth = status.get("queue_depth", 0)
                self.gpu_state.active_tasks = status.get("active_tasks", 0)
        except Exception:
            pass

        # Sample Satellites
        try:
            if self._satellite_bridge:
                satellites = self._satellite_bridge.get_available_satellites()
                self._satellites_available = len(satellites)
                self._satellite_gpu_available = any(s.get("has_gpu") for s in satellites)

                if satellites:
                    # Aggregate satellite load
                    total_load = sum(s.get("load", 0) for s in satellites)
                    avg_load = total_load / len(satellites)
                    self.satellite_state.utilization = avg_load

                    # Aggregate active tasks
                    self.satellite_state.active_tasks = sum(
                        s.get("active_tasks", 0) for s in satellites
                    )
                    self.satellite_state.last_sampled = now
                else:
                    # No satellites - mark as saturated
                    self.satellite_state.utilization = 1.0
        except Exception:
            pass

    def _adjust_throttle(self) -> None:
        """Adjust Ollama think interval based on GPU load."""
        gpu_load = self.gpu_state.load_score

        if gpu_load > 0.9:
            # GPU overloaded - slow down thinking significantly
            self._think_interval = self.config.max_think_interval_sec
        elif gpu_load > 0.7:
            # GPU busy - moderate throttle
            self._think_interval = (
                self.config.min_think_interval_sec +
                (self.config.max_think_interval_sec - self.config.min_think_interval_sec) * 0.5
            )
        elif gpu_load > 0.5:
            # GPU moderate - light throttle
            self._think_interval = self.config.min_think_interval_sec * 2
        else:
            # GPU available - think freely
            self._think_interval = self.config.min_think_interval_sec

    # =========================================================================
    # ROUTING DECISIONS
    # =========================================================================

    def should_think_now(self) -> bool:
        """
        Should UMF call Ollama right now?

        Returns False if GPU is too busy or we've thought recently.
        """
        now = time.time()

        # Check cooldown
        if now - self._last_gpu_think < self._think_interval:
            return False

        # Check GPU load
        if self.gpu_state.load_score > self.config.critical_threshold:
            self._routing_decisions["throttled"] += 1
            return False

        self._last_gpu_think = now
        return True

    def route_task(
        self,
        affinity: TaskAffinity,
        required_memory_mb: float = 0.0,
    ) -> str:
        """
        Decide where to route a task.

        Returns: "cpu", "gpu", "satellite", or "drop"
        """
        cpu_load = self.cpu_state.load_score
        gpu_load = self.gpu_state.load_score
        sat_load = self.satellite_state.load_score
        has_satellite = self._satellites_available > 0
        has_satellite_gpu = self._satellite_gpu_available

        # SATELLITE-PREFERRED: Explicitly prefer offloading to satellite
        if affinity == TaskAffinity.SATELLITE_PREFERRED:
            if has_satellite and sat_load < self.config.satellite_high_threshold:
                self._routing_decisions["to_satellite"] += 1
                return "satellite"
            # Fallback to local
            if gpu_load < cpu_load:
                self._routing_decisions["to_gpu"] += 1
                return "gpu"
            else:
                self._routing_decisions["to_cpu"] += 1
                return "cpu"

        # SATELLITE-GPU: Want satellite's GPU specifically
        if affinity == TaskAffinity.SATELLITE_GPU:
            if has_satellite_gpu and sat_load < self.config.satellite_high_threshold:
                self._routing_decisions["to_satellite"] += 1
                return "satellite"
            # Fallback to local GPU
            if gpu_load < self.config.critical_threshold:
                self._routing_decisions["to_gpu"] += 1
                return "gpu"
            self._routing_decisions["dropped"] += 1
            return "drop"

        # GPU-REQUIRED: Must run on GPU, but can try satellite if local saturated
        if affinity == TaskAffinity.GPU_REQUIRED:
            # First try local GPU
            if gpu_load < self.config.gpu_high_threshold:
                self._routing_decisions["to_gpu"] += 1
                return "gpu"
            # Local GPU busy - try satellite GPU
            if has_satellite_gpu and sat_load < self.config.satellite_high_threshold:
                self._routing_decisions["to_satellite"] += 1
                return "satellite"
            # No satellite or satellite busy - use local GPU anyway if not critical
            if gpu_load < self.config.critical_threshold:
                self._routing_decisions["to_gpu"] += 1
                return "gpu"
            # Everything saturated
            self._routing_decisions["dropped"] += 1
            return "drop"

        # CPU-only tasks must go to CPU
        if affinity == TaskAffinity.CPU_ONLY:
            if cpu_load > self.config.critical_threshold:
                self._routing_decisions["dropped"] += 1
                return "drop"
            self._routing_decisions["to_cpu"] += 1
            return "cpu"

        # GPU-PREFERRED: Prefers GPU but can use CPU or satellite
        if affinity == TaskAffinity.GPU_PREFERRED:
            if gpu_load < self.config.gpu_high_threshold:
                self._routing_decisions["to_gpu"] += 1
                return "gpu"
            # GPU busy - try satellite if available
            if has_satellite_gpu and sat_load < self.config.satellite_high_threshold:
                self._routing_decisions["to_satellite"] += 1
                return "satellite"
            # No satellite - fallback to CPU
            if cpu_load < self.config.cpu_high_threshold:
                self._routing_decisions["to_cpu"] += 1
                return "cpu"
            # Both busy - use GPU anyway (preferred)
            self._routing_decisions["to_gpu"] += 1
            return "gpu"

        # CPU-PREFERRED: Prefers CPU but can use GPU or satellite
        if affinity == TaskAffinity.CPU_PREFERRED:
            if cpu_load < self.config.cpu_high_threshold:
                self._routing_decisions["to_cpu"] += 1
                return "cpu"
            # CPU busy - try satellite if available
            if has_satellite and sat_load < self.config.satellite_high_threshold:
                self._routing_decisions["to_satellite"] += 1
                return "satellite"
            # No satellite - fallback to GPU
            if gpu_load < self.config.gpu_high_threshold:
                self._routing_decisions["to_gpu"] += 1
                return "gpu"
            # Both busy - use CPU anyway (preferred)
            self._routing_decisions["to_cpu"] += 1
            return "cpu"

        # TaskAffinity.ANY - route to least loaded resource
        loads = [
            ("cpu", cpu_load),
            ("gpu", gpu_load),
        ]
        if has_satellite:
            loads.append(("satellite", sat_load + self.config.satellite_latency_penalty))

        best = min(loads, key=lambda x: x[1])
        self._routing_decisions[f"to_{best[0]}"] += 1
        return best[0]

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get equilibrium status."""
        return {
            "cpu": {
                "utilization": f"{self.cpu_state.utilization:.1%}",
                "load_score": f"{self.cpu_state.load_score:.2f}",
                "queue_depth": self.cpu_state.queue_depth,
                "active_tasks": self.cpu_state.active_tasks,
            },
            "gpu": {
                "utilization": f"{self.gpu_state.utilization:.1%}",
                "memory_pressure": f"{self.gpu_state.memory_pressure:.1%}",
                "load_score": f"{self.gpu_state.load_score:.2f}",
                "queue_depth": self.gpu_state.queue_depth,
                "active_tasks": self.gpu_state.active_tasks,
            },
            "satellite": {
                "available_count": self._satellites_available,
                "gpu_available": self._satellite_gpu_available,
                "aggregate_load": f"{self.satellite_state.utilization:.1%}",
                "load_score": f"{self.satellite_state.load_score:.2f}",
                "active_tasks": self.satellite_state.active_tasks,
            },
            "throttle": {
                "think_interval_sec": self._think_interval,
                "last_gpu_think": self._last_gpu_think,
            },
            "routing": self._routing_decisions.copy(),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_equilibrium: Optional[WorkerEquilibrium] = None
_lock = threading.Lock()


def get_equilibrium() -> WorkerEquilibrium:
    """Get the worker equilibrium singleton."""
    global _equilibrium
    with _lock:
        if _equilibrium is None:
            _equilibrium = WorkerEquilibrium()
        return _equilibrium


def start_equilibrium() -> WorkerEquilibrium:
    """Get and start the equilibrium monitor."""
    eq = get_equilibrium()
    eq.start()
    return eq
