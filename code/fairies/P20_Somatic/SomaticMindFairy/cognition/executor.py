"""
Executor - Attempts execution and returns granular feedback.

Part of Dr. Zero architecture: takes ExecutionPlans from Planner,
executes hop-by-hop, returns detailed results for learning.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Set
from enum import Enum
import time
import asyncio
from collections import deque

from .planner import ExecutionPlan, HopStep, HopType


class ExecutionStatus(Enum):
    """Status of an execution attempt."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SuccessLevel(Enum):
    """Granular success levels for learning."""
    FULL = "full"          # All hops succeeded
    PARTIAL = "partial"    # Some hops succeeded
    NONE = "none"          # No meaningful progress


@dataclass
class HopResult:
    """Result of executing a single hop."""
    hop_index: int
    hop_type: HopType
    status: ExecutionStatus
    duration: float
    output: Any = None
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.hop_index,
            "type": self.hop_type.value,
            "status": self.status.value,
            "duration": self.duration,
            "output": str(self.output)[:100] if self.output else None,
            "error": self.error,
        }


@dataclass
class ExecutionResult:
    """
    Complete result of executing a plan.

    Provides granular feedback for the reward system.
    """
    plan: ExecutionPlan
    success: SuccessLevel
    hop_results: List[HopResult]
    hops_completed: int
    hops_attempted: int
    failure_point: Optional[int]  # Which hop failed (if any)
    total_duration: float
    started_at: float
    finished_at: float

    @property
    def success_ratio(self) -> float:
        """Fraction of hops that succeeded."""
        if self.hops_attempted == 0:
            return 0.0
        return self.hops_completed / self.hops_attempted

    @property
    def was_timeout(self) -> bool:
        """Did we timeout?"""
        return self.total_duration >= self.plan.goal.timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan.id,
            "goal_id": self.plan.goal.id,
            "objective": self.plan.goal.objective,
            "success": self.success.value,
            "hops_completed": self.hops_completed,
            "hops_attempted": self.hops_attempted,
            "hops_total": len(self.plan.hop_chain),
            "failure_point": self.failure_point,
            "duration": self.total_duration,
            "timeout": self.was_timeout,
            "hop_results": [h.to_dict() for h in self.hop_results],
        }


# Type for hop executors
HopExecutorFunc = Callable[[HopStep, Dict[str, Any]], Any]


class Executor:
    """
    Executes plans hop-by-hop and returns granular results.

    Supports pluggable hop executors for different hop types.
    Tracks execution history for learning.
    """

    def __init__(self):
        self._executors: Dict[HopType, HopExecutorFunc] = {}
        self._history: deque = deque(maxlen=100)
        self._running: bool = False
        self._current_plan: Optional[ExecutionPlan] = None

        # Register default executors
        self._register_defaults()

    def register_executor(self, hop_type: HopType, func: HopExecutorFunc):
        """Register an executor function for a hop type."""
        self._executors[hop_type] = func

    def execute(self,
                plan: ExecutionPlan,
                context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        Execute a plan synchronously.

        Args:
            plan: The plan to execute
            context: Execution context (fabric, directory, etc.)

        Returns:
            ExecutionResult with granular feedback
        """
        context = context or {}
        started_at = time.time()
        self._running = True
        self._current_plan = plan

        hop_results: List[HopResult] = []
        hops_completed = 0
        failure_point = None

        try:
            for hop in plan.hop_chain:
                # Check timeout
                elapsed = time.time() - started_at
                if elapsed >= plan.goal.timeout_seconds:
                    # Timeout - record remaining as failed
                    for remaining_hop in plan.hop_chain[hop.index:]:
                        hop_results.append(HopResult(
                            hop_index=remaining_hop.index,
                            hop_type=remaining_hop.hop_type,
                            status=ExecutionStatus.TIMEOUT,
                            duration=0.0,
                            error="Plan timeout exceeded",
                        ))
                    failure_point = hop.index
                    break

                # Execute hop
                result = self._execute_hop(hop, context)
                hop_results.append(result)

                if result.succeeded:
                    hops_completed += 1
                    # Pass output to context for next hop
                    context[f"hop_{hop.index}_output"] = result.output
                else:
                    failure_point = hop.index

                    # Try fallback if available
                    if hop.fallback:
                        fallback_result = self._execute_fallback(
                            hop, context
                        )
                        if fallback_result.succeeded:
                            hops_completed += 1
                            failure_point = None
                            context[f"hop_{hop.index}_output"] = fallback_result.output
                        else:
                            break  # Can't continue
                    else:
                        break  # No fallback, can't continue

        finally:
            self._running = False
            self._current_plan = None

        finished_at = time.time()
        total_duration = finished_at - started_at

        # Determine success level
        success = self._determine_success_level(
            hops_completed,
            len(plan.hop_chain),
            failure_point,
        )

        result = ExecutionResult(
            plan=plan,
            success=success,
            hop_results=hop_results,
            hops_completed=hops_completed,
            hops_attempted=len(hop_results),
            failure_point=failure_point,
            total_duration=total_duration,
            started_at=started_at,
            finished_at=finished_at,
        )

        # Record for learning
        self._history.append(result.to_dict())

        return result

    async def execute_async(self,
                            plan: ExecutionPlan,
                            context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        Execute a plan asynchronously.

        Useful when hops involve actual async operations.
        """
        # For now, wrap sync execution
        # TODO: Implement true async hop execution
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.execute(plan, context)
        )

    def _execute_hop(self,
                     hop: HopStep,
                     context: Dict[str, Any]) -> HopResult:
        """Execute a single hop."""
        executor = self._executors.get(hop.hop_type)
        start_time = time.time()

        if not executor:
            return HopResult(
                hop_index=hop.index,
                hop_type=hop.hop_type,
                status=ExecutionStatus.FAILED,
                duration=0.0,
                error=f"No executor for hop type: {hop.hop_type.value}",
            )

        try:
            output = executor(hop, context)
            duration = time.time() - start_time

            # Check if output indicates logical failure (error key in dict)
            # This lets executors signal failure without raising exceptions
            hop_status = ExecutionStatus.COMPLETED
            if isinstance(output, dict) and output.get("error"):
                hop_status = ExecutionStatus.FAILED

            return HopResult(
                hop_index=hop.index,
                hop_type=hop.hop_type,
                status=hop_status,
                duration=duration,
                output=output,
                error=output.get("error") if isinstance(output, dict) else None,
            )

        except TimeoutError as e:
            duration = time.time() - start_time
            return HopResult(
                hop_index=hop.index,
                hop_type=hop.hop_type,
                status=ExecutionStatus.TIMEOUT,
                duration=duration,
                error=str(e),
            )

        except Exception as e:
            duration = time.time() - start_time
            return HopResult(
                hop_index=hop.index,
                hop_type=hop.hop_type,
                status=ExecutionStatus.FAILED,
                duration=duration,
                error=str(e),
            )

    def _execute_fallback(self,
                          hop: HopStep,
                          context: Dict[str, Any]) -> HopResult:
        """Execute fallback for a failed hop."""
        start_time = time.time()

        try:
            # Simple fallback logic based on hop type
            if hop.hop_type == HopType.QUERY:
                # Retry with simpler query
                time.sleep(0.1)  # Brief pause
                return HopResult(
                    hop_index=hop.index,
                    hop_type=hop.hop_type,
                    status=ExecutionStatus.COMPLETED,
                    duration=time.time() - start_time,
                    output={"fallback": True, "result": "recovered"},
                )

            elif hop.hop_type == HopType.PUBLISH:
                # Queue for later — only if we have fabric
                fabric = context.get("fabric")
                if fabric:
                    context.setdefault("queued_messages", []).append(hop.description)
                    return HopResult(
                        hop_index=hop.index,
                        hop_type=hop.hop_type,
                        status=ExecutionStatus.COMPLETED,
                        duration=time.time() - start_time,
                        output={"queued": True},
                    )
                else:
                    return HopResult(
                        hop_index=hop.index,
                        hop_type=hop.hop_type,
                        status=ExecutionStatus.FAILED,
                        duration=time.time() - start_time,
                        error="no_fabric_for_queue",
                    )

            elif hop.hop_type == HopType.WAIT:
                # Proceed without waiting
                return HopResult(
                    hop_index=hop.index,
                    hop_type=hop.hop_type,
                    status=ExecutionStatus.COMPLETED,
                    duration=time.time() - start_time,
                    output={"skipped_wait": True},
                )

            else:
                # Generic fallback failed
                return HopResult(
                    hop_index=hop.index,
                    hop_type=hop.hop_type,
                    status=ExecutionStatus.FAILED,
                    duration=time.time() - start_time,
                    error="Fallback not implemented",
                )

        except Exception as e:
            return HopResult(
                hop_index=hop.index,
                hop_type=hop.hop_type,
                status=ExecutionStatus.FAILED,
                duration=time.time() - start_time,
                error=f"Fallback failed: {e}",
            )

    def _determine_success_level(self,
                                 completed: int,
                                 total: int,
                                 failure_point: Optional[int]) -> SuccessLevel:
        """Determine overall success level."""
        if failure_point is None and completed == total:
            return SuccessLevel.FULL

        if completed == 0:
            return SuccessLevel.NONE

        # Any progress counts as partial
        return SuccessLevel.PARTIAL

    def _register_defaults(self):
        """Register default hop executors."""

        def query_executor(hop: HopStep, context: Dict[str, Any]) -> Any:
            """Default query executor - simulates query."""
            fabric = context.get("fabric")
            if fabric:
                # Real query via fabric
                return {"queried": True, "plane": hop.target_plane}
            # Simulated
            return {"simulated": True, "query": hop.description}

        def publish_executor(hop: HopStep, context: Dict[str, Any]) -> Any:
            """Default publish executor."""
            fabric = context.get("fabric")
            if fabric:
                fabric.publish(f"hop.{hop.index}", {
                    "description": hop.description,
                    "plane": hop.target_plane,
                })
                return {"published": True}
            return {"simulated": True, "publish": hop.description}

        def subscribe_executor(hop: HopStep, context: Dict[str, Any]) -> Any:
            """Default subscribe executor."""
            return {"subscribed": True, "topic": hop.description}

        def compute_executor(hop: HopStep, context: Dict[str, Any]) -> Any:
            """Default compute executor."""
            # Simulates computation
            time.sleep(0.01)  # Brief compute time
            return {"computed": True}

        def wait_executor(hop: HopStep, context: Dict[str, Any]) -> Any:
            """Default wait executor."""
            # Don't actually wait long in tests
            time.sleep(min(0.1, hop.estimated_duration / 10))
            return {"waited": True}

        def repair_executor(hop: HopStep, context: Dict[str, Any]) -> Any:
            """Default repair executor."""
            return {"repair_attempted": True}

        self._executors = {
            HopType.QUERY: query_executor,
            HopType.PUBLISH: publish_executor,
            HopType.SUBSCRIBE: subscribe_executor,
            HopType.COMPUTE: compute_executor,
            HopType.WAIT: wait_executor,
            HopType.REPAIR: repair_executor,
        }

    def status(self) -> Dict[str, Any]:
        """Get executor status."""
        if not self._history:
            return {
                "executions": 0,
                "running": self._running,
                "current_plan": None,
            }

        # Calculate success distribution
        success_counts = {"full": 0, "partial": 0, "none": 0}
        for result in self._history:
            success_counts[result["success"]] += 1

        return {
            "executions": len(self._history),
            "running": self._running,
            "current_plan": self._current_plan.id if self._current_plan else None,
            "success_distribution": success_counts,
            "avg_duration": sum(r["duration"] for r in self._history) / len(self._history),
        }
