"""
Tests for FairyWorkerPool - Tracer-Tracked Parallel Execution

Following TDD: Write tests first, watch them fail, then implement.
"""
import pytest
import time
import threading
from typing import Any


class TestWorkerTaskDataclass:
    """Tests for WorkerTask dataclass structure."""

    def test_worker_task_has_required_fields(self):
        """WorkerTask should have all required fields with correct types."""
        from fairy_template.workers import WorkerTask

        task = WorkerTask(
            tracer_id="test_123",
            intent="test_intent",
            fn=lambda: None,
            args=(),
            kwargs={}
        )

        assert task.tracer_id == "test_123"
        assert task.intent == "test_intent"
        assert callable(task.fn)
        assert task.args == ()
        assert task.kwargs == {}

    def test_worker_task_has_defaults(self):
        """WorkerTask should have sensible defaults for optional fields."""
        from fairy_template.workers import WorkerTask

        task = WorkerTask(
            tracer_id="test_123",
            intent="test_intent",
            fn=lambda: None,
            args=(),
            kwargs={}
        )

        assert task.status == "pending"
        assert task.result is None
        assert task.error is None
        assert task.started_at is None
        assert task.completed_at is None

    def test_worker_task_status_can_be_set(self):
        """WorkerTask status should be mutable."""
        from fairy_template.workers import WorkerTask

        task = WorkerTask(
            tracer_id="test_123",
            intent="test_intent",
            fn=lambda: None,
            args=(),
            kwargs={},
            status="running"
        )

        assert task.status == "running"


class TestFairyWorkerPoolConstruction:
    """Tests for FairyWorkerPool constructor."""

    def test_pool_requires_fairy_name(self):
        """Pool must be constructed with a fairy name."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        assert pool.fairy_name == "TestFairy"
        pool.shutdown()

    def test_pool_has_default_max_workers(self):
        """Pool should default to 4 workers."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        assert pool.max_workers == 4
        pool.shutdown()

    def test_pool_has_default_timeout(self):
        """Pool should default to 30.0 second timeout."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        assert pool.timeout == 30.0
        pool.shutdown()

    def test_pool_accepts_custom_max_workers(self):
        """Pool should accept custom max_workers."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy", max_workers=8)
        assert pool.max_workers == 8
        pool.shutdown()

    def test_pool_accepts_custom_timeout(self):
        """Pool should accept custom timeout."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy", timeout=60.0)
        assert pool.timeout == 60.0
        pool.shutdown()


class TestFairyWorkerPoolSubmit:
    """Tests for submit method."""

    def test_submit_returns_tracer_id(self):
        """Submit should return a tracer_id string."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: 42, intent="compute")

        assert isinstance(tracer_id, str)
        assert len(tracer_id) > 0
        pool.shutdown()

    def test_submit_tracer_id_contains_fairy_name(self):
        """Tracer ID should contain the fairy name."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="MyFairy")
        tracer_id = pool.submit(fn=lambda: 42, intent="compute")

        assert "MyFairy" in tracer_id
        pool.shutdown()

    def test_submit_tracer_id_contains_intent(self):
        """Tracer ID should contain the intent."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: 42, intent="my_special_intent")

        assert "my_special_intent" in tracer_id
        pool.shutdown()

    def test_submit_tracer_id_is_unique(self):
        """Each tracer ID should be unique."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_ids = [pool.submit(fn=lambda: i, intent="compute") for i in range(10)]

        assert len(set(tracer_ids)) == 10  # All unique
        pool.shutdown()

    def test_submit_with_args(self):
        """Submit should accept positional arguments."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def add(a, b):
            return a + b

        tracer_id = pool.submit(fn=add, args=(3, 4), intent="add")
        result = pool.get_result(tracer_id, timeout=5.0)

        assert result == 7
        pool.shutdown()

    def test_submit_with_kwargs(self):
        """Submit should accept keyword arguments."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        tracer_id = pool.submit(
            fn=greet,
            args=("World",),
            kwargs={"greeting": "Hi"},
            intent="greet"
        )
        result = pool.get_result(tracer_id, timeout=5.0)

        assert result == "Hi, World!"
        pool.shutdown()

    def test_submit_default_intent_is_unknown(self):
        """Submit should default intent to 'unknown'."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: 42)

        assert "unknown" in tracer_id
        pool.shutdown()


class TestFairyWorkerPoolGetResult:
    """Tests for get_result method."""

    def test_get_result_returns_computed_value(self):
        """get_result should return the computed value."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: 42, intent="compute")
        result = pool.get_result(tracer_id, timeout=5.0)

        assert result == 42
        pool.shutdown()

    def test_get_result_blocks_until_complete(self):
        """get_result should block until the task completes."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def slow_task():
            time.sleep(0.2)
            return "done"

        tracer_id = pool.submit(fn=slow_task, intent="slow")
        start = time.time()
        result = pool.get_result(tracer_id, timeout=5.0)
        elapsed = time.time() - start

        assert result == "done"
        assert elapsed >= 0.2
        pool.shutdown()

    def test_get_result_respects_timeout(self):
        """get_result should return None if timeout exceeded."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def very_slow_task():
            time.sleep(10)
            return "done"

        tracer_id = pool.submit(fn=very_slow_task, intent="slow")
        result = pool.get_result(tracer_id, timeout=0.1)

        assert result is None
        pool.shutdown(wait=False)

    def test_get_result_unknown_tracer_returns_none(self):
        """get_result for unknown tracer_id should return None."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        result = pool.get_result("nonexistent_tracer_123", timeout=0.1)

        assert result is None
        pool.shutdown()


class TestFairyWorkerPoolGetStatus:
    """Tests for get_status method."""

    def test_get_status_pending(self):
        """get_status should return 'pending' for queued tasks."""
        from fairy_template.workers import FairyWorkerPool

        # Use only 1 worker to ensure second task stays pending
        pool = FairyWorkerPool(fairy_name="TestFairy", max_workers=1)

        # Block the only worker
        blocker = pool.submit(fn=lambda: time.sleep(1), intent="block")
        time.sleep(0.05)  # Let blocker start

        # Submit another task that must wait
        tracer_id = pool.submit(fn=lambda: 42, intent="compute")
        status = pool.get_status(tracer_id)

        assert status in ("pending", "running")  # May have started if blocker finished
        pool.shutdown(wait=False)

    def test_get_status_running(self):
        """get_status should return 'running' for executing tasks."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        started = threading.Event()

        def slow_task():
            started.set()
            time.sleep(1)
            return "done"

        tracer_id = pool.submit(fn=slow_task, intent="slow")
        started.wait(timeout=1.0)
        status = pool.get_status(tracer_id)

        assert status == "running"
        pool.shutdown(wait=False)

    def test_get_status_completed(self):
        """get_status should return 'completed' for finished tasks."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: 42, intent="compute")
        pool.get_result(tracer_id, timeout=5.0)  # Wait for completion
        status = pool.get_status(tracer_id)

        assert status == "completed"
        pool.shutdown()

    def test_get_status_failed(self):
        """get_status should return 'failed' for tasks that raised exceptions."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def failing_task():
            raise ValueError("Intentional error")

        tracer_id = pool.submit(fn=failing_task, intent="fail")
        pool.get_result(tracer_id, timeout=5.0)  # Wait for completion
        status = pool.get_status(tracer_id)

        assert status == "failed"
        pool.shutdown()

    def test_get_status_unknown(self):
        """get_status should return 'unknown' for untracked tracer_ids."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        status = pool.get_status("nonexistent_tracer_123")

        assert status == "unknown"
        pool.shutdown()


class TestFairyWorkerPoolGetTaskInfo:
    """Tests for get_task_info method."""

    def test_get_task_info_returns_dict(self):
        """get_task_info should return a dictionary."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: 42, intent="compute")
        pool.get_result(tracer_id, timeout=5.0)
        info = pool.get_task_info(tracer_id)

        assert isinstance(info, dict)
        pool.shutdown()

    def test_get_task_info_contains_required_fields(self):
        """get_task_info should contain all required fields."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: 42, intent="compute")
        pool.get_result(tracer_id, timeout=5.0)
        info = pool.get_task_info(tracer_id)

        assert "tracer_id" in info
        assert "intent" in info
        assert "status" in info
        assert "result" in info
        assert "error" in info
        assert "started_at" in info
        assert "completed_at" in info
        assert "duration_ms" in info
        pool.shutdown()

    def test_get_task_info_duration_ms_is_positive(self):
        """get_task_info duration_ms should be positive for completed tasks."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def slow_task():
            time.sleep(0.1)
            return "done"

        tracer_id = pool.submit(fn=slow_task, intent="slow")
        pool.get_result(tracer_id, timeout=5.0)
        info = pool.get_task_info(tracer_id)

        assert info["duration_ms"] >= 100  # At least 100ms
        pool.shutdown()

    def test_get_task_info_returns_none_for_unknown(self):
        """get_task_info should return None for unknown tracer_ids."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        info = pool.get_task_info("nonexistent_tracer_123")

        assert info is None
        pool.shutdown()

    def test_get_task_info_includes_error_for_failed_task(self):
        """get_task_info should include error message for failed tasks."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def failing_task():
            raise ValueError("Intentional error message")

        tracer_id = pool.submit(fn=failing_task, intent="fail")
        pool.get_result(tracer_id, timeout=5.0)
        info = pool.get_task_info(tracer_id)

        assert info["status"] == "failed"
        assert "Intentional error message" in info["error"]
        pool.shutdown()


class TestFairyWorkerPoolShutdown:
    """Tests for shutdown method."""

    def test_shutdown_wait_true_waits_for_tasks(self):
        """shutdown(wait=True) should wait for running tasks to complete."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        completed = threading.Event()

        def slow_task():
            time.sleep(0.2)
            completed.set()
            return "done"

        pool.submit(fn=slow_task, intent="slow")
        pool.shutdown(wait=True)

        assert completed.is_set()

    def test_shutdown_wait_false_returns_immediately(self):
        """shutdown(wait=False) should return immediately."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def very_slow_task():
            time.sleep(10)
            return "done"

        pool.submit(fn=very_slow_task, intent="slow")
        start = time.time()
        pool.shutdown(wait=False)
        elapsed = time.time() - start

        assert elapsed < 1.0  # Should be nearly instant


class TestFairyWorkerPoolGetStats:
    """Tests for get_stats method."""

    def test_get_stats_returns_dict(self):
        """get_stats should return a dictionary."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        stats = pool.get_stats()

        assert isinstance(stats, dict)
        pool.shutdown()

    def test_get_stats_contains_required_fields(self):
        """get_stats should contain all required fields."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy", max_workers=4)
        stats = pool.get_stats()

        assert stats["fairy"] == "TestFairy"
        assert stats["max_workers"] == 4
        assert "total_tasks" in stats
        assert "by_status" in stats
        pool.shutdown()

    def test_get_stats_counts_tasks_correctly(self):
        """get_stats should correctly count tasks by status."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        # Submit several tasks
        for i in range(5):
            tracer_id = pool.submit(fn=lambda x=i: x * 2, intent="compute")
            pool.get_result(tracer_id, timeout=5.0)

        stats = pool.get_stats()

        assert stats["total_tasks"] == 5
        assert stats["by_status"]["completed"] == 5
        pool.shutdown()

    def test_get_stats_tracks_failed_tasks(self):
        """get_stats should track failed tasks."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")

        def failing_task():
            raise RuntimeError("fail")

        # Submit failing tasks
        for _ in range(3):
            tracer_id = pool.submit(fn=failing_task, intent="fail")
            pool.get_result(tracer_id, timeout=5.0)

        stats = pool.get_stats()

        assert stats["by_status"]["failed"] == 3
        pool.shutdown()


class TestFairyWorkerPoolThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_submits_are_thread_safe(self):
        """Multiple threads submitting tasks should not cause errors."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy", max_workers=8)
        tracer_ids = []
        lock = threading.Lock()
        errors = []

        def submit_task(n):
            try:
                tracer_id = pool.submit(fn=lambda x=n: x * 2, intent="compute")
                with lock:
                    tracer_ids.append(tracer_id)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=submit_task, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(tracer_ids) == 20
        assert len(set(tracer_ids)) == 20  # All unique
        pool.shutdown()

    def test_concurrent_get_status_is_thread_safe(self):
        """Multiple threads checking status should not cause errors."""
        from fairy_template.workers import FairyWorkerPool

        pool = FairyWorkerPool(fairy_name="TestFairy")
        tracer_id = pool.submit(fn=lambda: time.sleep(0.5), intent="slow")
        errors = []

        def check_status():
            try:
                for _ in range(10):
                    pool.get_status(tracer_id)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=check_status) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        pool.shutdown()
