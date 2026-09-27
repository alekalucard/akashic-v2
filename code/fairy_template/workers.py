"""
Fairy Worker Pool - Tracer-Tracked Parallel Execution

Every fairy has workers (like blood cells) that do the actual work.
All work is tracked via tracer IDs for perfect recall.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, Future
import threading
import uuid
import time


@dataclass
class WorkerTask:
    """
    Represents a single unit of work submitted to the pool.

    Tracks the full lifecycle from submission to completion,
    including timing information for performance analysis.
    """
    tracer_id: str
    intent: str
    fn: Callable
    args: Tuple
    kwargs: Dict[str, Any]
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class FairyWorkerPool:
    """
    A tracer-tracked parallel execution pool for fairy workers.

    Every task submitted to the pool is assigned a unique tracer ID
    that can be used to track status, retrieve results, and recall
    the full execution history.

    Usage:
        pool = FairyWorkerPool(fairy_name="MyFairy", max_workers=4)
        tracer_id = pool.submit(fn=my_function, args=(1, 2), intent="compute")
        result = pool.get_result(tracer_id, timeout=10.0)
        pool.shutdown()
    """

    def __init__(
        self,
        fairy_name: str,
        max_workers: int = 4,
        timeout: float = 30.0
    ):
        """
        Initialize the worker pool.

        Args:
            fairy_name: Name of the fairy owning this pool (used in tracer IDs)
            max_workers: Maximum number of concurrent workers (default: 4)
            timeout: Default timeout for operations in seconds (default: 30.0)
        """
        self.fairy_name = fairy_name
        self.max_workers = max_workers
        self.timeout = timeout

        # LAZY: Don't create ThreadPoolExecutor until first submit().
        # 90 fairies × 4 threads = 360 idle threads wasting ~1GB+ RAM.
        self._executor: Optional[ThreadPoolExecutor] = None
        self._tasks: Dict[str, WorkerTask] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._max_completed = 50  # Evict oldest completed tasks beyond this

    def submit(
        self,
        fn: Callable,
        args: Tuple = (),
        kwargs: Optional[dict] = None,
        intent: str = "unknown"
    ) -> str:
        """
        Submit a task for execution.

        Args:
            fn: The callable to execute
            args: Positional arguments for the callable
            kwargs: Keyword arguments for the callable
            intent: Description of what the task is doing (for tracking)

        Returns:
            tracer_id: Unique identifier for tracking this task
        """
        if kwargs is None:
            kwargs = {}

        # Generate unique tracer ID: {fairy_name}_{intent}_{uuid8}
        uuid8 = uuid.uuid4().hex[:8]
        tracer_id = f"{self.fairy_name}_{intent}_{uuid8}"

        # Create task record
        task = WorkerTask(
            tracer_id=tracer_id,
            intent=intent,
            fn=fn,
            args=args,
            kwargs=kwargs,
            status="pending"
        )

        with self._lock:
            # Lazy-create executor on first submit
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

            # Evict oldest completed tasks to prevent unbounded growth
            self._evict_completed()

            self._tasks[tracer_id] = task
            # Submit to executor
            future = self._executor.submit(self._run_task, tracer_id)
            self._futures[tracer_id] = future

        return tracer_id

    def _run_task(self, tracer_id: str) -> Any:
        """
        Internal method to execute a task and update its state.

        Args:
            tracer_id: The tracer ID of the task to run

        Returns:
            The result of the task execution
        """
        with self._lock:
            task = self._tasks.get(tracer_id)
            if task is None:
                return None
            task.status = "running"
            task.started_at = time.time()

        try:
            result = task.fn(*task.args, **task.kwargs)
            with self._lock:
                task.result = result
                task.status = "completed"
                task.completed_at = time.time()
            return result
        except Exception as e:
            with self._lock:
                task.error = str(e)
                task.status = "failed"
                task.completed_at = time.time()
            return None

    def get_result(self, tracer_id: str, timeout: Optional[float] = None) -> Any:
        """
        Get the result of a task, blocking until complete or timeout.

        Args:
            tracer_id: The tracer ID of the task
            timeout: Maximum time to wait in seconds (uses pool default if None)

        Returns:
            The task result, or None if timeout/error/unknown
        """
        if timeout is None:
            timeout = self.timeout

        with self._lock:
            future = self._futures.get(tracer_id)
            task = self._tasks.get(tracer_id)

        if future is None or task is None:
            return None

        try:
            future.result(timeout=timeout)
        except Exception:
            pass

        with self._lock:
            return task.result

    def get_status(self, tracer_id: str) -> str:
        """
        Get the current status of a task.

        Args:
            tracer_id: The tracer ID of the task

        Returns:
            Status string: "pending", "running", "completed", "failed", or "unknown"
        """
        with self._lock:
            task = self._tasks.get(tracer_id)
            if task is None:
                return "unknown"
            return task.status

    def get_task_info(self, tracer_id: str) -> Optional[dict]:
        """
        Get full information about a task.

        Args:
            tracer_id: The tracer ID of the task

        Returns:
            Dictionary with task details including duration_ms, or None if unknown
        """
        with self._lock:
            task = self._tasks.get(tracer_id)
            if task is None:
                return None

            # Calculate duration if we have timing info
            duration_ms = None
            if task.started_at is not None and task.completed_at is not None:
                duration_ms = (task.completed_at - task.started_at) * 1000

            return {
                "tracer_id": task.tracer_id,
                "intent": task.intent,
                "status": task.status,
                "result": task.result,
                "error": task.error,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "duration_ms": duration_ms
            }

    def _evict_completed(self) -> None:
        """Evict oldest completed/failed tasks when over the cap. Must hold _lock."""
        completed = [
            (tid, t) for tid, t in self._tasks.items()
            if t.status in ("completed", "failed") and t.completed_at is not None
        ]
        if len(completed) <= self._max_completed:
            return
        # Sort by completion time, evict oldest
        completed.sort(key=lambda x: x[1].completed_at)
        to_evict = len(completed) - self._max_completed
        for tid, task in completed[:to_evict]:
            # Release callable references before removal
            task.fn = None
            task.args = ()
            task.kwargs = {}
            task.result = None
            self._tasks.pop(tid, None)
            self._futures.pop(tid, None)

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the worker pool.

        Args:
            wait: If True, wait for running tasks to complete (default: True)
        """
        if self._executor is not None:
            self._executor.shutdown(wait=wait)

    def get_stats(self) -> dict:
        """
        Get statistics about the worker pool.

        Returns:
            Dictionary containing:
                - fairy: Name of the fairy
                - max_workers: Maximum worker count
                - total_tasks: Total tasks submitted
                - by_status: Dict of task counts by status
        """
        with self._lock:
            by_status: Dict[str, int] = {}
            for task in self._tasks.values():
                by_status[task.status] = by_status.get(task.status, 0) + 1

            return {
                "fairy": self.fairy_name,
                "max_workers": self.max_workers,
                "total_tasks": len(self._tasks),
                "by_status": by_status
            }
