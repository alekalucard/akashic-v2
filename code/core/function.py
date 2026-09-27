# Function - The Machine
# Functions are stateless workers that do actual work.
# Fairies are caretakers of functions - they manage but don't DO.
#
# Every function has:
# - A unique tracer_id
# - A checklist of requirements
# - Metrics for performance tracking
# - Clear inputs and outputs

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, TypeVar, Generic
from datetime import datetime
import uuid
import time

from .checklist import Checklist, ChecklistResult


class FunctionStatus(Enum):
    """Status of a function."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


@dataclass
class FunctionMetrics:
    """Performance metrics for a function."""
    calls_total: int = 0
    calls_success: int = 0
    calls_failed: int = 0
    total_duration_ms: float = 0.0
    last_call_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def avg_duration_ms(self) -> float:
        if self.calls_total == 0:
            return 0.0
        return self.total_duration_ms / self.calls_total

    @property
    def success_rate(self) -> float:
        if self.calls_total == 0:
            return 1.0
        return self.calls_success / self.calls_total

    def record_call(self, success: bool, duration_ms: float, error: str = None):
        """Record a function call."""
        self.calls_total += 1
        if success:
            self.calls_success += 1
        else:
            self.calls_failed += 1
            self.last_error = error
        self.total_duration_ms += duration_ms
        self.last_call_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "calls_success": self.calls_success,
            "calls_failed": self.calls_failed,
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "last_call": self.last_call_at.isoformat() if self.last_call_at else None,
            "last_error": self.last_error
        }


T = TypeVar('T')  # Return type of function


class Function(Generic[T]):
    """
    Base class for all functions (machines).

    A Function is a stateless worker that does actual work.
    It has a clear contract: inputs -> outputs.
    It tracks its own health via checklist and performance via metrics.

    Usage:
        class MessageRouter(Function[int]):
            def __init__(self):
                super().__init__(
                    name="message_router",
                    description="Routes messages to subscribers"
                )
                # Add custom checks
                self.checklist.add("topics_ready", "Topic registry initialized",
                                   lambda: self._topics is not None)

            def execute(self, topic: str, payload: dict) -> int:
                # Return number of subscribers notified
                return len(self._notify(topic, payload))

        router = MessageRouter()
        if router.is_ready():
            count = router.call(topic="test", payload={"data": 1})
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        function_type: str = "generic"
    ):
        # Identity
        self.tracer_id = f"fn_{name}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.function_type = function_type

        # State
        self._status = FunctionStatus.INITIALIZING
        self._created_at = datetime.now()

        # Metrics
        self.metrics = FunctionMetrics()

        # Checklist - subclasses add their own checks
        self.checklist = Checklist(f"{name}_checklist", owner=self)
        self._add_base_checks()

    def _add_base_checks(self):
        """Add standard checks that all functions need."""
        self.checklist.add(
            "tracer_id",
            "Tracer ID assigned",
            lambda: self.tracer_id is not None and len(self.tracer_id) > 0
        )
        self.checklist.add(
            "name",
            "Function has name",
            lambda: self.name is not None and len(self.name) > 0
        )
        self.checklist.add(
            "not_failed",
            "Function not in failed state",
            lambda: self._status != FunctionStatus.FAILED
        )

    def execute(self, **kwargs) -> T:
        """
        Override this in subclasses to implement actual work.

        Returns:
            The result of the function's work
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def call(self, **kwargs) -> T:
        """
        Call this function with tracking.

        Wraps execute() with metrics tracking and error handling.
        """
        if not self.is_ready():
            raise RuntimeError(f"Function {self.name} not ready. Run validate() for details.")

        self._status = FunctionStatus.BUSY
        start = time.perf_counter()

        try:
            result = self.execute(**kwargs)
            duration = (time.perf_counter() - start) * 1000
            self.metrics.record_call(success=True, duration_ms=duration)
            self._status = FunctionStatus.READY
            return result

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self.metrics.record_call(success=False, duration_ms=duration, error=str(e))
            self._status = FunctionStatus.READY  # Don't fail permanently on one error
            raise

    def validate(self) -> ChecklistResult:
        """Run all checks and return result."""
        return self.checklist.run()

    def is_ready(self) -> bool:
        """Quick check: is this function ready to be called?"""
        if self._status == FunctionStatus.FAILED:
            return False
        return self.checklist.is_valid()

    def initialize(self) -> bool:
        """
        Initialize the function. Override in subclasses for setup logic.

        Returns:
            True if initialization succeeded
        """
        result = self.validate()
        if result.all_passed:
            self._status = FunctionStatus.READY
            return True
        else:
            self._status = FunctionStatus.FAILED
            return False

    def shutdown(self):
        """Shutdown this function. Override for cleanup."""
        self._status = FunctionStatus.SHUTDOWN

    @property
    def status(self) -> FunctionStatus:
        return self._status

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now() - self._created_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize function state for reporting."""
        return {
            "tracer_id": self.tracer_id,
            "name": self.name,
            "description": self.description,
            "type": self.function_type,
            "status": self._status.value,
            "metrics": self.metrics.to_dict(),
            "checklist": self.checklist.last_result.to_dict() if self.checklist.last_result else None,
            "uptime_seconds": self.uptime_seconds
        }

    def __repr__(self) -> str:
        return f"Function({self.name}, status={self._status.value})"


# Example function implementations

class EchoFunction(Function[str]):
    """Simple function that echoes input - for testing."""

    def __init__(self):
        super().__init__(
            name="echo",
            description="Echoes input back",
            function_type="utility"
        )

    def execute(self, message: str = "") -> str:
        return f"Echo: {message}"


class CounterFunction(Function[int]):
    """Function that counts calls - for testing."""

    def __init__(self):
        super().__init__(
            name="counter",
            description="Counts how many times called",
            function_type="utility"
        )
        self._count = 0

    def execute(self) -> int:
        self._count += 1
        return self._count
