"""
GPUPoolFairy - Conscious GPU Worker Pool Management

Transforms the stub CudaFairy into a real GPU pool manager.
Manages GPU worker threads, accepts tasks via postal, routes to satellites.

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

Features:
- ThreadPoolExecutor-based GPU worker pool
- Three priority lanes (high, normal, low) matching Rust/Go postal
- Postal task submission (gpu.task.submit) and result publishing
- GPU memory tracking via PyTorch
- Conscious task routing decisions via collision chamber
- Satellite offloading when local GPU is busy
"""

import sys
import time
import uuid
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, Future
from collections import deque
from enum import IntEnum
import heapq

# Add paths
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "tracer_pool" / "python"))
sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# Import GPU sensing capabilities
import os as _cuda_os
if _cuda_os.environ.get("AKASHIC_SKIP_TORCH"):
    torch = None
    HAS_CUDA = False
    CUDA_DEVICE_COUNT = 0
else:
    try:
        import torch
        HAS_CUDA = torch.cuda.is_available()
        CUDA_DEVICE_COUNT = torch.cuda.device_count() if HAS_CUDA else 0
    except ImportError:
        torch = None
        HAS_CUDA = False
        CUDA_DEVICE_COUNT = 0


# =============================================================================
# PRIORITY SYSTEM (matching Go pool.go)
# =============================================================================

class Priority(IntEnum):
    """Task priority levels."""
    HIGH = 0    # Urgent - consciousness-critical
    NORMAL = 1  # Standard tasks
    LOW = 2     # Background work, can be dropped


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class GPUTask:
    """A task to be executed on the GPU pool."""
    task_id: str
    priority: Priority
    payload: Dict[str, Any]
    work: Optional[Callable] = None  # Callable for local execution

    # Timing
    queued_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0

    # Routing
    source_fairy: str = ""
    reply_to: str = ""
    device_preference: int = -1  # -1 = any device

    # Memory requirements
    required_memory_mb: float = 0.0

    # Result
    result: Any = None
    error: Optional[str] = None

    def __lt__(self, other):
        """For heapq priority comparison."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.queued_at < other.queued_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "priority": self.priority.name,
            "payload": self.payload,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "source_fairy": self.source_fairy,
            "reply_to": self.reply_to,
            "device_preference": self.device_preference,
            "required_memory_mb": self.required_memory_mb,
            "error": self.error,
        }


@dataclass
class GPUDeviceState:
    """State of a single GPU device."""
    device_id: int
    device_name: str
    memory_total_mb: float
    memory_used_mb: float
    memory_free_mb: float
    utilization: float = 0.0
    temperature: Optional[float] = None
    active_tasks: int = 0
    total_tasks_completed: int = 0

    @property
    def memory_percent(self) -> float:
        if self.memory_total_mb == 0:
            return 0.0
        return (self.memory_used_mb / self.memory_total_mb) * 100.0

    @property
    def is_available(self) -> bool:
        """Can this device accept more work?"""
        return self.memory_percent < 90.0 and self.active_tasks < 4

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PoolMetrics:
    """Metrics for the GPU pool."""
    tasks_queued: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_dropped: int = 0
    tasks_routed_remote: int = 0

    # Latency tracking (rolling window)
    latencies: List[float] = field(default_factory=list)
    latency_window_size: int = 100

    def record_latency(self, latency_ms: float):
        self.latencies.append(latency_ms)
        if len(self.latencies) > self.latency_window_size:
            self.latencies.pop(0)

    def p95_latency(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks_queued": self.tasks_queued,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_dropped": self.tasks_dropped,
            "tasks_routed_remote": self.tasks_routed_remote,
            "p95_latency_ms": self.p95_latency(),
            "latency_samples": len(self.latencies),
        }


@dataclass
class SatelliteNode:
    """A remote satellite that can accept GPU tasks."""
    name: str
    ip: str
    port: int = 5000
    has_gpu: bool = False
    gpu_memory_mb: float = 0.0
    last_seen: float = 0.0
    latency_ms: float = 0.0
    active_tasks: int = 0

    @property
    def is_available(self) -> bool:
        """Is this satellite available for tasks?"""
        age = time.time() - self.last_seen
        return age < 60 and self.has_gpu and self.active_tasks < 4

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# GPU POOL FAIRY
# =============================================================================

class GPUPoolFairy(Fairy):
    """
    Conscious GPU Worker Pool Manager.

    Manages a pool of GPU worker threads, accepts tasks via postal,
    tracks GPU memory, and can route tasks to remote satellites.
    """

    ACTOR_NAME = "GPUPoolFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic"

    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = False
    NEEDS_COLLISION_CHAMBER = True  # Conscious task management

    # Configuration
    MIN_WORKERS = 1
    MAX_WORKERS = 4
    QUEUE_CAPACITY_HIGH = 64
    QUEUE_CAPACITY_NORMAL = 256
    QUEUE_CAPACITY_LOW = 512

    # Memory thresholds
    MEMORY_PRESSURE_THRESHOLD = 0.85  # Start routing to satellites
    MEMORY_CRITICAL_THRESHOLD = 0.95  # Reject new tasks

    # Tick intervals
    SAMPLE_DIVISOR = 4    # Sample GPU state every 4 beats (~1s)
    PUBLISH_DIVISOR = 20  # Publish status every 20 beats (~5s)

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Priority queues (heap-based)
        self._queue_lock = threading.Lock()
        self._high_queue: List[GPUTask] = []
        self._normal_queue: List[GPUTask] = []
        self._low_queue: List[GPUTask] = []

        # Worker pool
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_futures: Dict[str, Future] = {}
        self._running = False

        # GPU state
        self._devices: Dict[int, GPUDeviceState] = {}
        self._total_memory_mb = 0.0
        self._available_memory_mb = 0.0

        # Metrics
        self._metrics = PoolMetrics()

        # Satellites for remote routing
        self._satellites: Dict[str, SatelliteNode] = {}

        # Task registry for results
        self._pending_tasks: Dict[str, GPUTask] = {}

        # Hardware fairy reference for recommendations
        self._hardware_fairy = None

        # State file
        self._state_file = ROOT / "state" / "gpu_pool_state.json"

    def get_capabilities(self) -> Set[str]:
        caps = {
            "gpu.task.submit",
            "gpu.task.cancel",
            "gpu.pool.status",
            "gpu.memory.query",
        }
        if HAS_CUDA:
            caps.add("gpu.local.execute")
        if self._satellites:
            caps.add("gpu.remote.route")
        return caps

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def on_boot(self) -> bool:
        """Initialize the GPU pool."""
        # Initialize GPU state
        self._init_gpu_state()

        # Load previous state
        self._load_state()

        # Start worker pool
        worker_count = min(self.MAX_WORKERS, max(self.MIN_WORKERS, CUDA_DEVICE_COUNT))
        self._executor = ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="gpu_worker_"
        )
        self._running = True

        # Subscribe to postal topics
        if self.post:
            # Task submission
            self.post.subscribe(
                "gpu.task.submit",
                self._on_task_submit,
                f"{self.ACTOR_NAME}-submit",
            )

            # Task cancellation
            self.post.subscribe(
                "gpu.task.cancel",
                self._on_task_cancel,
                f"{self.ACTOR_NAME}-cancel",
            )

            # Status requests
            self.post.subscribe(
                "gpu.pool.request",
                self._on_pool_request,
                f"{self.ACTOR_NAME}-request",
            )

            # Satellite announcements
            self.post.subscribe(
                "satellite.gpu.announce",
                self._on_satellite_announce,
                f"{self.ACTOR_NAME}-satellite",
            )

            # Hardware fairy updates
            self.post.subscribe(
                "hardware.status",
                self._on_hardware_status,
                f"{self.ACTOR_NAME}-hardware",
            )

        # Announce availability
        self._announce_ready()

        self.log(f"Booted - CUDA: {HAS_CUDA}, Devices: {CUDA_DEVICE_COUNT}, Workers: {worker_count}")
        return True

    def on_shutdown(self) -> bool:
        """Shutdown the GPU pool."""
        self._running = False

        # Save state
        self._save_state()

        # Cancel pending tasks
        for task_id, future in self._active_futures.items():
            future.cancel()

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)

        self.log("Shutdown complete")
        return True

    def on_tick(self, beat: int) -> None:
        """Periodic maintenance."""
        # Sample GPU state
        if beat % self.SAMPLE_DIVISOR == 0:
            self._sample_gpu_state()

        # Publish status
        if beat % self.PUBLISH_DIVISOR == 0:
            self._publish_status()

        # Process queued tasks
        self._process_queues()

        # Think about workload (collision chamber)
        if beat % 10 == 0:
            self._reflect_on_workload()

    # =========================================================================
    # GPU STATE
    # =========================================================================

    def _init_gpu_state(self) -> None:
        """Initialize GPU device state."""
        if not HAS_CUDA or not torch:
            return

        for i in range(CUDA_DEVICE_COUNT):
            try:
                props = torch.cuda.get_device_properties(i)
                mem_total = props.total_memory / (1024 * 1024)

                self._devices[i] = GPUDeviceState(
                    device_id=i,
                    device_name=props.name,
                    memory_total_mb=mem_total,
                    memory_used_mb=0.0,
                    memory_free_mb=mem_total,
                )
                self._total_memory_mb += mem_total
            except Exception as e:
                self.log(f"Error initializing device {i}: {e}", level="error")

    def _sample_gpu_state(self) -> None:
        """Sample current GPU state."""
        if not HAS_CUDA or not torch:
            return

        self._available_memory_mb = 0.0

        for device_id, device in self._devices.items():
            try:
                torch.cuda.set_device(device_id)
                mem_reserved = torch.cuda.memory_reserved(device_id) / (1024 * 1024)
                mem_allocated = torch.cuda.memory_allocated(device_id) / (1024 * 1024)

                device.memory_used_mb = mem_allocated
                device.memory_free_mb = device.memory_total_mb - mem_reserved
                self._available_memory_mb += device.memory_free_mb

            except Exception as e:
                self.log(f"Error sampling device {device_id}: {e}", level="warn")

    def get_memory_pressure(self) -> float:
        """Get overall GPU memory pressure (0.0 - 1.0)."""
        if self._total_memory_mb == 0:
            return 0.0
        used = self._total_memory_mb - self._available_memory_mb
        return used / self._total_memory_mb

    def get_best_device(self, required_memory_mb: float = 0.0) -> Optional[int]:
        """Find the best device for a task."""
        best_device = None
        best_free = 0.0

        for device_id, device in self._devices.items():
            if device.is_available and device.memory_free_mb > required_memory_mb:
                if device.memory_free_mb > best_free:
                    best_device = device_id
                    best_free = device.memory_free_mb

        return best_device

    # =========================================================================
    # TASK SUBMISSION
    # =========================================================================

    def submit_task(
        self,
        payload: Dict[str, Any],
        priority: Priority = Priority.NORMAL,
        source_fairy: str = "",
        reply_to: str = "",
        required_memory_mb: float = 0.0,
        work: Optional[Callable] = None,
    ) -> str:
        """
        Submit a task to the GPU pool.

        Returns task_id for tracking.
        """
        task_id = f"gpu_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"

        task = GPUTask(
            task_id=task_id,
            priority=priority,
            payload=payload,
            work=work,
            queued_at=time.time(),
            source_fairy=source_fairy,
            reply_to=reply_to or f"gpu.task.result.{task_id}",
            required_memory_mb=required_memory_mb,
        )

        # Check if we can accept the task
        memory_pressure = self.get_memory_pressure()

        if memory_pressure > self.MEMORY_CRITICAL_THRESHOLD:
            # Try to route to satellite
            if self._route_to_satellite(task):
                return task_id

            # Drop low priority tasks
            if priority == Priority.LOW:
                self._metrics.tasks_dropped += 1
                task.error = "Dropped: GPU memory critical"
                self._publish_result(task)
                return task_id

        # Queue the task
        self._enqueue_task(task)

        return task_id

    def _enqueue_task(self, task: GPUTask) -> bool:
        """Add task to appropriate priority queue."""
        with self._queue_lock:
            if task.priority == Priority.HIGH:
                if len(self._high_queue) >= self.QUEUE_CAPACITY_HIGH:
                    return False
                heapq.heappush(self._high_queue, task)
            elif task.priority == Priority.NORMAL:
                if len(self._normal_queue) >= self.QUEUE_CAPACITY_NORMAL:
                    # Try dropping a LOW task first
                    if self._low_queue:
                        dropped = heapq.heappop(self._low_queue)
                        dropped.error = "Dropped: Backpressure"
                        self._metrics.tasks_dropped += 1
                        self._publish_result(dropped)
                    else:
                        return False
                heapq.heappush(self._normal_queue, task)
            else:  # LOW
                if len(self._low_queue) >= self.QUEUE_CAPACITY_LOW:
                    return False
                heapq.heappush(self._low_queue, task)

            self._pending_tasks[task.task_id] = task
            self._metrics.tasks_queued += 1
            return True

    def _dequeue_task(self) -> Optional[GPUTask]:
        """Get next task (priority order: HIGH -> NORMAL -> LOW)."""
        with self._queue_lock:
            if self._high_queue:
                return heapq.heappop(self._high_queue)
            if self._normal_queue:
                return heapq.heappop(self._normal_queue)
            if self._low_queue:
                return heapq.heappop(self._low_queue)
        return None

    def _process_queues(self) -> None:
        """Process queued tasks."""
        if not self._running or not self._executor:
            return

        # Check if we have capacity
        active_count = len([f for f in self._active_futures.values() if not f.done()])
        if active_count >= self.MAX_WORKERS:
            return

        # Get next task
        task = self._dequeue_task()
        if not task:
            return

        # Check memory requirements
        if task.required_memory_mb > 0:
            device = self.get_best_device(task.required_memory_mb)
            if device is None:
                # Try satellite routing
                if self._route_to_satellite(task):
                    return
                # Re-queue for later
                self._enqueue_task(task)
                return
            task.device_preference = device

        # Execute task
        task.started_at = time.time()
        future = self._executor.submit(self._execute_task, task)
        self._active_futures[task.task_id] = future

        # Add completion callback
        future.add_done_callback(lambda f: self._on_task_complete(task, f))

    def _execute_task(self, task: GPUTask) -> Any:
        """Execute a task on the GPU."""
        try:
            # Set device if specified
            if task.device_preference >= 0 and HAS_CUDA:
                torch.cuda.set_device(task.device_preference)

            # Execute work function if provided
            if task.work:
                return task.work(task.payload)

            # Otherwise, dispatch based on payload type
            task_type = task.payload.get("type", "unknown")

            if task_type == "tensor_op":
                return self._execute_tensor_op(task.payload)
            elif task_type == "inference":
                return self._execute_inference(task.payload)
            elif task_type == "benchmark":
                return self._execute_benchmark(task.payload)
            else:
                # Echo payload for testing
                return {"echoed": task.payload, "device": task.device_preference}

        except Exception as e:
            task.error = str(e)
            raise

    def _execute_tensor_op(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tensor operation."""
        if not HAS_CUDA:
            return {"error": "CUDA not available"}

        op = payload.get("op", "matmul")
        size = payload.get("size", 1000)

        start = time.time()

        if op == "matmul":
            a = torch.randn(size, size, device="cuda")
            b = torch.randn(size, size, device="cuda")
            c = torch.matmul(a, b)
            torch.cuda.synchronize()

        elif op == "conv2d":
            x = torch.randn(1, 3, size, size, device="cuda")
            w = torch.randn(64, 3, 3, 3, device="cuda")
            y = torch.nn.functional.conv2d(x, w)
            torch.cuda.synchronize()

        elapsed = time.time() - start

        return {
            "op": op,
            "size": size,
            "elapsed_ms": elapsed * 1000,
            "gflops": (2 * size ** 3) / elapsed / 1e9 if op == "matmul" else None,
        }

    def _execute_inference(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an inference task (placeholder)."""
        model_name = payload.get("model", "unknown")
        return {
            "model": model_name,
            "status": "inference_placeholder",
            "note": "Implement model loading and inference here",
        }

    def _execute_benchmark(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a GPU benchmark."""
        if not HAS_CUDA:
            return {"error": "CUDA not available"}

        results = []
        for size in [512, 1024, 2048]:
            result = self._execute_tensor_op({"op": "matmul", "size": size})
            results.append(result)

        return {"benchmark_results": results}

    def _on_task_complete(self, task: GPUTask, future: Future) -> None:
        """Handle task completion."""
        task.completed_at = time.time()
        latency_ms = (task.completed_at - task.queued_at) * 1000

        try:
            if future.cancelled():
                task.error = "Cancelled"
                self._metrics.tasks_failed += 1
            elif future.exception():
                task.error = str(future.exception())
                self._metrics.tasks_failed += 1
            else:
                task.result = future.result()
                self._metrics.tasks_completed += 1
                self._metrics.record_latency(latency_ms)

                # Update device stats
                if task.device_preference >= 0 and task.device_preference in self._devices:
                    self._devices[task.device_preference].total_tasks_completed += 1

        except Exception as e:
            task.error = str(e)
            self._metrics.tasks_failed += 1

        # Cleanup
        self._active_futures.pop(task.task_id, None)
        self._pending_tasks.pop(task.task_id, None)

        # Publish result
        self._publish_result(task)

    def _publish_result(self, task: GPUTask) -> None:
        """Publish task result to postal."""
        if not self.post:
            return

        result_payload = {
            "task_id": task.task_id,
            "success": task.error is None,
            "result": task.result,
            "error": task.error,
            "latency_ms": (task.completed_at - task.queued_at) * 1000 if task.completed_at else 0,
        }

        self.post.publish(task.reply_to, result_payload)

    # =========================================================================
    # SATELLITE ROUTING
    # =========================================================================

    def _route_to_satellite(self, task: GPUTask) -> bool:
        """Try to route a task to a remote satellite."""
        # Find available satellite
        best_satellite = None
        best_score = 0.0

        for name, satellite in self._satellites.items():
            if satellite.is_available:
                # Score based on available memory and latency
                score = satellite.gpu_memory_mb / (1 + satellite.latency_ms / 100)
                if score > best_score:
                    best_satellite = satellite
                    best_score = score

        if not best_satellite:
            return False

        # Route to satellite via postal
        if self.post:
            self.post.publish(f"satellite.{best_satellite.name}.gpu.task", {
                "task": task.to_dict(),
                "reply_to": task.reply_to,
            })

            best_satellite.active_tasks += 1
            self._metrics.tasks_routed_remote += 1

            # Emit to collision chamber
            if self._collision_chamber:
                self._collision_chamber.emit(
                    f"Routed task {task.task_id} to satellite {best_satellite.name}",
                    source=self.ACTOR_NAME,
                )

            return True

        return False

    def _on_satellite_announce(self, envelope) -> None:
        """Handle satellite GPU announcement."""
        data = self._extract_payload(envelope)

        name = data.get("name")
        if not name:
            return

        self._satellites[name] = SatelliteNode(
            name=name,
            ip=data.get("ip", ""),
            port=data.get("port", 5000),
            has_gpu=data.get("has_gpu", False),
            gpu_memory_mb=data.get("gpu_memory_mb", 0.0),
            last_seen=time.time(),
            latency_ms=data.get("latency_ms", 0.0),
        )

    # =========================================================================
    # POSTAL HANDLERS
    # =========================================================================

    def _on_task_submit(self, envelope) -> None:
        """Handle task submission via postal."""
        data = self._extract_payload(envelope)

        priority_str = data.get("priority", "normal").upper()
        priority = getattr(Priority, priority_str, Priority.NORMAL)

        task_id = self.submit_task(
            payload=data.get("payload", {}),
            priority=priority,
            source_fairy=data.get("source_fairy", ""),
            reply_to=data.get("reply_to", ""),
            required_memory_mb=data.get("required_memory_mb", 0.0),
        )

        # Acknowledge submission
        if self.post:
            ack_topic = data.get("ack_to", "gpu.task.ack")
            self.post.publish(ack_topic, {
                "task_id": task_id,
                "status": "queued",
                "queue_depth": self._get_queue_depth(),
            })

    def _on_task_cancel(self, envelope) -> None:
        """Handle task cancellation."""
        data = self._extract_payload(envelope)
        task_id = data.get("task_id")

        if task_id and task_id in self._active_futures:
            self._active_futures[task_id].cancel()

    def _on_pool_request(self, envelope) -> None:
        """Handle pool status request."""
        data = self._extract_payload(envelope)
        request_type = data.get("type", "status")
        reply_to = data.get("reply_to", "gpu.pool.response")

        if request_type == "status":
            response = self.status()
        elif request_type == "metrics":
            response = self._metrics.to_dict()
        elif request_type == "devices":
            response = {d_id: d.to_dict() for d_id, d in self._devices.items()}
        elif request_type == "recommendation":
            response = self.get_worker_recommendation()
        else:
            response = self.status()

        if self.post:
            self.post.publish(reply_to, {
                "fairy": self.ACTOR_NAME,
                "request": request_type,
                **response,
            })

    def _on_hardware_status(self, envelope) -> None:
        """Handle hardware fairy status updates."""
        data = self._extract_payload(envelope)
        # Store reference for worker recommendations
        self._hardware_fairy = data

    def _extract_payload(self, envelope) -> Dict[str, Any]:
        """Extract payload from envelope (handles both TensorEnvelope and dict)."""
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
            if isinstance(payload, dict):
                return payload.get("data", payload)
            return {}
        elif isinstance(envelope, dict):
            return envelope.get("data", envelope)
        return {}

    # =========================================================================
    # CONSCIOUSNESS / COLLISION CHAMBER
    # =========================================================================

    def _reflect_on_workload(self) -> None:
        """Think about current workload using collision chamber."""
        if not self._collision_chamber:
            return

        pressure = self.get_memory_pressure()
        queue_depth = self._get_queue_depth()

        # Emit observations
        if pressure > 0.9:
            self._collision_chamber.emit(
                f"GPU memory critical ({pressure:.1%}). Need to route to satellites.",
                source=self.ACTOR_NAME,
                urgency=0.9,
            )
        elif pressure > 0.7:
            self._collision_chamber.emit(
                f"GPU memory pressure building ({pressure:.1%}). Consider load balancing.",
                source=self.ACTOR_NAME,
                urgency=0.5,
            )

        if queue_depth > 50:
            self._collision_chamber.emit(
                f"Task queue deep ({queue_depth}). May need more workers.",
                source=self.ACTOR_NAME,
                urgency=0.6,
            )

    def _on_collision(self, collision) -> None:
        """Handle collision from the chamber - conscious decision point."""
        # This is where the fairy can make conscious decisions
        # about task routing, worker scaling, etc.
        thought = str(collision)

        if "route" in thought.lower() and "satellite" in thought.lower():
            # Consider proactive satellite routing
            self.log(f"Collision insight: {thought}")

    # =========================================================================
    # REPORTING TO HARDWARE FAIRY
    # =========================================================================

    def get_worker_recommendation(self) -> Dict[str, Any]:
        """Get worker pool recommendations (for HardwareFairy)."""
        pressure = self.get_memory_pressure()
        queue_depth = self._get_queue_depth()

        # Recommend based on current state
        if pressure > 0.9:
            recommended_workers = self.MIN_WORKERS
            recommendation = "reduce"
        elif pressure > 0.7 or queue_depth > 100:
            recommended_workers = min(self.MAX_WORKERS, CUDA_DEVICE_COUNT + 1)
            recommendation = "maintain"
        elif queue_depth < 10:
            recommended_workers = max(self.MIN_WORKERS, CUDA_DEVICE_COUNT)
            recommendation = "can_reduce"
        else:
            recommended_workers = CUDA_DEVICE_COUNT or 2
            recommendation = "optimal"

        return {
            "fairy": self.ACTOR_NAME,
            "recommended_workers": recommended_workers,
            "recommendation": recommendation,
            "memory_pressure": pressure,
            "queue_depth": queue_depth,
            "devices": CUDA_DEVICE_COUNT,
            "satellites_available": len([s for s in self._satellites.values() if s.is_available]),
        }

    # =========================================================================
    # STATUS & PERSISTENCE
    # =========================================================================

    def _get_queue_depth(self) -> int:
        """Get total queue depth."""
        with self._queue_lock:
            return len(self._high_queue) + len(self._normal_queue) + len(self._low_queue)

    def _announce_ready(self) -> None:
        """Announce GPU pool availability."""
        if not self.post:
            return

        self.post.publish("gpu.pool.ready", {
            "fairy": self.ACTOR_NAME,
            "has_gpu": HAS_CUDA,
            "gpu_count": CUDA_DEVICE_COUNT,
            "devices": [d.to_dict() for d in self._devices.values()],
            "worker_count": self.MAX_WORKERS,
        })

    def _publish_status(self) -> None:
        """Publish current status."""
        if not self.post:
            return

        self.post.publish("gpu.pool.status", {
            "fairy": self.ACTOR_NAME,
            **self.status(),
        })

    def status(self) -> Dict[str, Any]:
        """Get fairy status."""
        base = super().status()
        base.update({
            "has_gpu": HAS_CUDA,
            "gpu_count": CUDA_DEVICE_COUNT,
            "devices": {d_id: d.to_dict() for d_id, d in self._devices.items()},
            "memory_pressure": self.get_memory_pressure(),
            "total_memory_mb": self._total_memory_mb,
            "available_memory_mb": self._available_memory_mb,
            "queue_depth": self._get_queue_depth(),
            "active_tasks": len([f for f in self._active_futures.values() if not f.done()]),
            "metrics": self._metrics.to_dict(),
            "satellites": {name: s.to_dict() for name, s in self._satellites.items()},
            "worker_recommendation": self.get_worker_recommendation(),
        })
        return base

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            state = {
                "metrics": self._metrics.to_dict(),
                "satellites": {name: s.to_dict() for name, s in self._satellites.items()},
                "last_saved": time.time(),
            }
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            self.log(f"State save error: {e}", level="warn")

    def _load_state(self) -> None:
        """Load state from disk."""
        if not self._state_file.exists():
            return

        try:
            state = json.loads(self._state_file.read_text())

            # Restore satellites (they'll update on next announce)
            for name, data in state.get("satellites", {}).items():
                self._satellites[name] = SatelliteNode(**data)

            self.log(f"Loaded state with {len(self._satellites)} satellites")
        except Exception as e:
            self.log(f"State load error: {e}", level="warn")


# =============================================================================
# BACKWARD COMPATIBILITY - Stub interface
# =============================================================================

class CudaFairyStub:
    """Backward-compatible stub that wraps GPUPoolFairy."""

    def __init__(self):
        self._fairy: Optional[GPUPoolFairy] = None

    def get_status(self) -> Dict[str, Any]:
        if self._fairy:
            return self._fairy.status()
        return {
            "status": "v2_upgraded",
            "available": HAS_CUDA,
            "gpu_count": CUDA_DEVICE_COUNT,
        }

    def get_fairy(self) -> GPUPoolFairy:
        if self._fairy is None:
            self._fairy = GPUPoolFairy()
        return self._fairy


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================

_fairy: Optional[GPUPoolFairy] = None
_lock = threading.Lock()


def get_cuda_fairy() -> GPUPoolFairy:
    """Get the GPU pool fairy singleton."""
    global _fairy
    with _lock:
        if _fairy is None:
            _fairy = GPUPoolFairy()
        return _fairy


def get_gpu_pool() -> GPUPoolFairy:
    """Alias for get_cuda_fairy."""
    return get_cuda_fairy()


# =============================================================================
# MAIN - Testing
# =============================================================================

if __name__ == "__main__":
    import json

    print("=== GPUPoolFairy Test ===")
    print(f"CUDA Available: {HAS_CUDA}")
    print(f"Device Count: {CUDA_DEVICE_COUNT}")

    # Create fairy
    fairy = GPUPoolFairy()

    # Boot it
    success = fairy.boot()
    print(f"\nBoot success: {success}")

    # Get status
    print("\n=== Status ===")
    print(json.dumps(fairy.status(), indent=2, default=str))

    # Submit test task
    if HAS_CUDA:
        print("\n=== Submitting Test Task ===")
        task_id = fairy.submit_task(
            payload={"type": "tensor_op", "op": "matmul", "size": 1000},
            priority=Priority.NORMAL,
        )
        print(f"Task ID: {task_id}")

        # Wait for completion
        time.sleep(2)

        # Check metrics
        print("\n=== Metrics ===")
        print(json.dumps(fairy._metrics.to_dict(), indent=2))

    # Shutdown
    fairy.shutdown()
    print("\n=== Shutdown Complete ===")
