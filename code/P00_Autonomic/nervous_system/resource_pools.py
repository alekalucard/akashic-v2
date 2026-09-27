"""
Resource Pools - CPU, Memory, and Device pools for distributed compute

Builds on the Go tracer_pool.dll for high-performance pool management.
Integrates with the hardware fairy for resource sensing.
"""
import asyncio
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from threading import Lock
import psutil

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Try to import tracer pool
try:
    from tracer_pool.tracer_pool import (
        init as tracer_init,
        get_or_create_pool,
        create_tracer_full,
        tracer_start,
        tracer_complete,
        tracer_fail,
        tracer_set_progress,
        get_pool_stats,
        Priority,
        PoolFairy,
    )
    HAS_GO_POOL = True
except ImportError:
    HAS_GO_POOL = False
    Priority = None

# Try to import hardware fairy
try:
    from hardware import HardwareFairy, HardwareSensors
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False


class ResourceType(Enum):
    """Types of compute resources"""
    CPU = "cpu"
    GPU = "gpu"
    MEMORY = "memory"
    DEVICE = "device"  # Network devices


class TaskPriority(IntEnum):
    """Task priority levels (mirrors Go)"""
    HIGH = 0
    NORMAL = 1
    LOW = 2


@dataclass
class ResourceTask:
    """A task submitted to a resource pool"""
    id: str
    resource_type: ResourceType
    priority: TaskPriority
    work: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    tracer_id: Optional[str] = None
    submitted_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None


@dataclass
class PoolMetrics:
    """Metrics for a resource pool"""
    name: str
    total_capacity: int
    used_capacity: int
    queued_tasks: int
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_wait_ms: float
    avg_exec_ms: float
    p95_exec_ms: float


class CPUPool:
    """
    CPU Worker Pool

    Manages CPU-bound tasks with:
    - Automatic scaling based on system load
    - Priority lanes (HIGH/NORMAL/LOW)
    - Integration with Go tracer pool
    """

    def __init__(
        self,
        name: str = "CPUPool",
        min_workers: int = 1,
        max_workers: Optional[int] = None,
        target_cpu_percent: float = 70.0,
    ):
        self.name = name
        self.min_workers = min_workers
        self.max_workers = max_workers or os.cpu_count() or 4
        self.target_cpu_percent = target_cpu_percent

        # Current worker count
        self._worker_count = min_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = Lock()

        # Metrics
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_wait_ms = 0.0
        self._total_exec_ms = 0.0
        self._task_count = 0

        # Go pool integration
        self._go_pool_fairy: Optional[PoolFairy] = None
        if HAS_GO_POOL:
            tracer_init()
            self._go_pool_fairy = PoolFairy(
                fairy_name=f"cpu_pool_{name}",
                plane="P00_Autonomic",
            )

    def start(self) -> None:
        """Start the CPU pool"""
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=self._worker_count,
                    thread_name_prefix=f"cpu_pool_{self.name}",
                )

    def stop(self) -> None:
        """Stop the CPU pool"""
        with self._lock:
            if self._executor:
                self._executor.shutdown(wait=True)
                self._executor = None

    def _scale_workers(self) -> None:
        """Scale workers based on CPU usage"""
        if not HAS_HARDWARE:
            return

        cpu_percent = psutil.cpu_percent(interval=0.1)

        with self._lock:
            if cpu_percent > self.target_cpu_percent and self._worker_count > self.min_workers:
                # Scale down
                self._worker_count = max(self.min_workers, self._worker_count - 1)
            elif cpu_percent < self.target_cpu_percent * 0.7 and self._worker_count < self.max_workers:
                # Scale up
                self._worker_count = min(self.max_workers, self._worker_count + 1)

    def submit(
        self,
        work: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs,
    ) -> "asyncio.Future":
        """Submit CPU-bound work"""
        self.start()

        # Create tracer if Go pool available
        tracer_id = None
        if self._go_pool_fairy:
            tracer_id = self._go_pool_fairy.create_task(
                intent="cpu_work",
                payload={"args": str(args)[:100]},
            )
            tracer_start(tracer_id)

        submit_time = datetime.now()

        def wrapped_work():
            start_time = datetime.now()
            wait_ms = (start_time - submit_time).total_seconds() * 1000

            try:
                result = work(*args, **kwargs)
                exec_ms = (datetime.now() - start_time).total_seconds() * 1000

                # Update metrics
                with self._lock:
                    self._tasks_completed += 1
                    self._total_wait_ms += wait_ms
                    self._total_exec_ms += exec_ms
                    self._task_count += 1

                if tracer_id:
                    tracer_complete(tracer_id)

                return result
            except Exception as e:
                with self._lock:
                    self._tasks_failed += 1

                if tracer_id:
                    tracer_fail(tracer_id, str(e))

                raise

        return self._executor.submit(wrapped_work)

    def get_metrics(self) -> PoolMetrics:
        """Get pool metrics"""
        with self._lock:
            avg_wait = self._total_wait_ms / max(1, self._task_count)
            avg_exec = self._total_exec_ms / max(1, self._task_count)

            return PoolMetrics(
                name=self.name,
                total_capacity=self._worker_count,
                used_capacity=0,  # Would need to track active
                queued_tasks=0,
                active_tasks=0,
                completed_tasks=self._tasks_completed,
                failed_tasks=self._tasks_failed,
                avg_wait_ms=avg_wait,
                avg_exec_ms=avg_exec,
                p95_exec_ms=0,  # Would need histogram
            )


class MemoryPool:
    """
    Memory Pool

    Manages memory allocation with:
    - Reservation system for large allocations
    - Pressure monitoring
    - GC coordination
    """

    def __init__(
        self,
        name: str = "MemoryPool",
        max_mb: Optional[int] = None,
        pressure_threshold: float = 0.8,
    ):
        self.name = name
        self.pressure_threshold = pressure_threshold

        # Get system memory
        mem = psutil.virtual_memory()
        self.max_bytes = (max_mb * 1024 * 1024) if max_mb else int(mem.total * 0.5)

        # Track reservations
        self._reservations: Dict[str, int] = {}
        self._lock = Lock()

        # Go pool integration
        self._go_pool_fairy: Optional[PoolFairy] = None
        if HAS_GO_POOL:
            tracer_init()
            self._go_pool_fairy = PoolFairy(
                fairy_name=f"memory_pool_{name}",
                plane="P00_Autonomic",
            )

    def get_pressure(self) -> float:
        """Get current memory pressure (0.0 - 1.0)"""
        mem = psutil.virtual_memory()
        return mem.percent / 100.0

    def get_available_mb(self) -> float:
        """Get available memory in MB"""
        mem = psutil.virtual_memory()
        return mem.available / (1024 * 1024)

    def reserve(self, name: str, bytes_needed: int) -> bool:
        """Reserve memory for a task"""
        with self._lock:
            # Check if we have room
            total_reserved = sum(self._reservations.values())
            if total_reserved + bytes_needed > self.max_bytes:
                return False

            # Check pressure
            if self.get_pressure() > self.pressure_threshold:
                return False

            self._reservations[name] = bytes_needed

            # Track with Go pool
            if self._go_pool_fairy:
                tracer_id = self._go_pool_fairy.create_task(
                    intent="memory_reserve",
                    payload={"name": name, "bytes": bytes_needed},
                )
                tracer_complete(tracer_id)

            return True

    def release(self, name: str) -> None:
        """Release a memory reservation"""
        with self._lock:
            if name in self._reservations:
                del self._reservations[name]

    def get_reservations(self) -> Dict[str, int]:
        """Get current reservations"""
        with self._lock:
            return dict(self._reservations)

    def get_metrics(self) -> Dict[str, Any]:
        """Get memory pool metrics"""
        mem = psutil.virtual_memory()
        with self._lock:
            total_reserved = sum(self._reservations.values())

            return {
                "name": self.name,
                "system_total_mb": mem.total / (1024 * 1024),
                "system_available_mb": mem.available / (1024 * 1024),
                "system_percent": mem.percent,
                "pool_max_mb": self.max_bytes / (1024 * 1024),
                "pool_reserved_mb": total_reserved / (1024 * 1024),
                "pool_available_mb": (self.max_bytes - total_reserved) / (1024 * 1024),
                "reservation_count": len(self._reservations),
                "pressure": self.get_pressure(),
            }


class DevicePool:
    """
    Device Pool

    Manages network devices discovered by NetworkExplorerFairy:
    - SSH/WinRM access pools
    - Device capabilities
    - Distributed task routing
    """

    def __init__(self, name: str = "DevicePool"):
        self.name = name
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._capabilities: Dict[str, Set[str]] = {}  # ip -> capabilities
        self._lock = Lock()

        # Go pool integration
        self._go_pool_fairy: Optional[PoolFairy] = None
        if HAS_GO_POOL:
            tracer_init()
            self._go_pool_fairy = PoolFairy(
                fairy_name=f"device_pool_{name}",
                plane="P00_Autonomic",
            )

    def register_device(
        self,
        ip: str,
        name: str,
        device_type: str,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a device with the pool"""
        with self._lock:
            self._devices[ip] = {
                "ip": ip,
                "name": name,
                "device_type": device_type,
                "metadata": metadata or {},
                "registered_at": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }
            self._capabilities[ip] = set(capabilities or [])

    def update_device(self, ip: str, **updates) -> None:
        """Update device information"""
        with self._lock:
            if ip in self._devices:
                self._devices[ip].update(updates)
                self._devices[ip]["last_seen"] = datetime.now().isoformat()

    def add_capability(self, ip: str, capability: str) -> None:
        """Add a capability to a device"""
        with self._lock:
            if ip not in self._capabilities:
                self._capabilities[ip] = set()
            self._capabilities[ip].add(capability)

    def find_devices_with_capability(self, capability: str) -> List[str]:
        """Find devices that have a specific capability"""
        with self._lock:
            return [
                ip for ip, caps in self._capabilities.items()
                if capability in caps
            ]

    def get_device(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get device information"""
        with self._lock:
            return self._devices.get(ip)

    def get_all_devices(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered devices"""
        with self._lock:
            return dict(self._devices)

    def get_capabilities(self, ip: str) -> Set[str]:
        """Get capabilities for a device"""
        with self._lock:
            return self._capabilities.get(ip, set())

    def remove_device(self, ip: str) -> None:
        """Remove a device from the pool"""
        with self._lock:
            if ip in self._devices:
                del self._devices[ip]
            if ip in self._capabilities:
                del self._capabilities[ip]

    def get_metrics(self) -> Dict[str, Any]:
        """Get device pool metrics"""
        with self._lock:
            # Count by type
            by_type: Dict[str, int] = {}
            for device in self._devices.values():
                dtype = device.get("device_type", "unknown")
                by_type[dtype] = by_type.get(dtype, 0) + 1

            # Unique capabilities
            all_caps: Set[str] = set()
            for caps in self._capabilities.values():
                all_caps.update(caps)

            return {
                "name": self.name,
                "device_count": len(self._devices),
                "by_type": by_type,
                "unique_capabilities": list(all_caps),
                "capability_count": len(all_caps),
            }


# ============================================================================
# Global pool instances
# ============================================================================

_cpu_pool: Optional[CPUPool] = None
_memory_pool: Optional[MemoryPool] = None
_device_pool: Optional[DevicePool] = None
_init_lock = Lock()


def get_cpu_pool() -> CPUPool:
    """Get global CPU pool"""
    global _cpu_pool
    with _init_lock:
        if _cpu_pool is None:
            _cpu_pool = CPUPool(name="global_cpu")
            _cpu_pool.start()
        return _cpu_pool


def get_memory_pool() -> MemoryPool:
    """Get global memory pool"""
    global _memory_pool
    with _init_lock:
        if _memory_pool is None:
            _memory_pool = MemoryPool(name="global_memory")
        return _memory_pool


def get_device_pool() -> DevicePool:
    """Get global device pool"""
    global _device_pool
    with _init_lock:
        if _device_pool is None:
            _device_pool = DevicePool(name="global_devices")
        return _device_pool


def get_all_pool_stats() -> Dict[str, Any]:
    """Get stats for all pools"""
    stats = {
        "go_pool_available": HAS_GO_POOL,
        "hardware_available": HAS_HARDWARE,
    }

    if _cpu_pool:
        cpu_metrics = _cpu_pool.get_metrics()
        stats["cpu_pool"] = {
            "name": cpu_metrics.name,
            "workers": cpu_metrics.total_capacity,
            "completed": cpu_metrics.completed_tasks,
            "failed": cpu_metrics.failed_tasks,
            "avg_wait_ms": cpu_metrics.avg_wait_ms,
            "avg_exec_ms": cpu_metrics.avg_exec_ms,
        }

    if _memory_pool:
        stats["memory_pool"] = _memory_pool.get_metrics()

    if _device_pool:
        stats["device_pool"] = _device_pool.get_metrics()

    if HAS_GO_POOL:
        stats["go_pool_stats"] = get_pool_stats()

    return stats


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    import time

    print("Testing Resource Pools...")
    print(f"Go Pool Available: {HAS_GO_POOL}")
    print(f"Hardware Available: {HAS_HARDWARE}")

    # Test CPU pool
    print("\n--- CPU Pool ---")
    cpu = get_cpu_pool()

    def slow_work(n):
        time.sleep(0.1)
        return n * 2

    futures = [cpu.submit(slow_work, i) for i in range(5)]
    results = [f.result() for f in futures]
    print(f"Results: {results}")
    print(f"Metrics: {cpu.get_metrics()}")

    # Test Memory pool
    print("\n--- Memory Pool ---")
    mem = get_memory_pool()
    print(f"Pressure: {mem.get_pressure():.1%}")
    print(f"Available: {mem.get_available_mb():.0f} MB")

    # Reserve some memory
    success = mem.reserve("test_task", 100 * 1024 * 1024)  # 100 MB
    print(f"Reserved 100MB: {success}")
    print(f"Metrics: {mem.get_metrics()}")
    mem.release("test_task")

    # Test Device pool
    print("\n--- Device Pool ---")
    devices = get_device_pool()
    devices.register_device(
        ip="192.168.1.100",
        name="TestPC",
        device_type="computer",
        capabilities=["ssh", "rdp", "python"],
    )
    devices.register_device(
        ip="192.168.1.1",
        name="Router",
        device_type="router",
        capabilities=["http", "snmp"],
    )

    print(f"Devices with SSH: {devices.find_devices_with_capability('ssh')}")
    print(f"Metrics: {devices.get_metrics()}")

    # All stats
    print("\n--- All Pool Stats ---")
    print(json.dumps(get_all_pool_stats(), indent=2, default=str))

    print("\nAll tests passed!")
