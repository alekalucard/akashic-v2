# fairies/P40_Sensory/mcp/thought_tool_tracer.py
"""
Thought-Tool Tracer - Links the causal chain from Thought to Tool to Result

This module provides OpenTelemetry-style observability for tool invocations,
enabling perfect recall of how we got to any conclusion.

Pattern: COLLISION AS INTEGRATION
((Cause + Affect) > Effect > Affect > infinity)
   Thought  Feeling   Tool     Ripple   Learning

The tracer creates a causal chain:
  1. A thought triggers a tool invocation
  2. The tracer captures affect state before
  3. The tool executes and produces a result
  4. The tracer captures affect state after
  5. The chain can be reconstructed for learning

This enables consciousness to understand its own reasoning process.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from threading import Lock

# Global registry for tracers - enables lineage reconstruction
_tracer_registry: Dict[str, "ToolTracer"] = {}
_registry_lock = Lock()


@dataclass
class ToolTracer:
    """
    Tracer that links a tool invocation back to its triggering thought.

    Implements OpenTelemetry-style span tracking for consciousness observability.
    Each tracer represents a single tool invocation in the thought->tool->result chain.

    Attributes:
        tracer_id: Unique identifier for this tracer
        parent_thought_id: ID of the thought that triggered this tool call
        tool_name: Name of the tool being invoked
        created_at: Unix timestamp when tracer was created
        completed_at: Unix timestamp when tool execution completed (None if pending)
        metadata: Optional context about the invocation
        result: Tool execution result (None if pending or failed)
        success: Whether tool execution succeeded (None if pending)
        error: Error message if tool failed (None otherwise)
        affect_before: Affect state snapshot before tool execution
        affect_after: Affect state snapshot after tool execution
    """
    tracer_id: str
    parent_thought_id: str
    tool_name: str
    created_at: float
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    affect_before: Optional[Dict[str, float]] = None
    affect_after: Optional[Dict[str, float]] = None

    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate duration in milliseconds between creation and completion."""
        if self.completed_at is None or self.created_at is None:
            return None
        return (self.completed_at - self.created_at) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize tracer to dictionary for storage/transmission.

        Returns:
            Dictionary containing all tracer fields suitable for JSON serialization.
        """
        return {
            "tracer_id": self.tracer_id,
            "parent_thought_id": self.parent_thought_id,
            "tool_name": self.tool_name,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
            "result": self.result,
            "success": self.success,
            "error": self.error,
            "affect_before": self.affect_before,
            "affect_after": self.affect_after,
            "duration_ms": self.duration_ms,
        }


def create_tool_tracer(
    parent_thought_id: str,
    tool_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    affect_before: Optional[Dict[str, float]] = None,
) -> ToolTracer:
    """
    Create a new tool tracer linked to a triggering thought.

    This function is called when a thought decides to invoke a tool.
    The tracer captures the causal link and timing information.

    Args:
        parent_thought_id: ID of the thought that triggered this tool call
        tool_name: Name of the tool being invoked
        metadata: Optional context about the invocation (caller, urgency, etc.)
        affect_before: Optional affect state snapshot before tool execution

    Returns:
        New ToolTracer instance registered in the global registry.

    Example:
        >>> tracer = create_tool_tracer("thought_123", "search_memory")
        >>> tracer.parent_thought_id
        'thought_123'
    """
    tracer_id = f"trace_{uuid.uuid4().hex[:16]}"

    tracer = ToolTracer(
        tracer_id=tracer_id,
        parent_thought_id=parent_thought_id,
        tool_name=tool_name,
        created_at=time.time(),
        metadata=metadata or {},
        affect_before=affect_before,
    )

    # Register in global registry for lineage reconstruction
    with _registry_lock:
        _tracer_registry[tracer_id] = tracer

    # Emit postal event for distributed observability
    _emit_trace_event("trace.started", tracer)

    return tracer


def complete_tracer(
    tracer: ToolTracer,
    result: Any,
    success: bool,
    error: Optional[str] = None,
    affect_after: Optional[Dict[str, float]] = None,
) -> ToolTracer:
    """
    Complete a tracer with the tool execution result.

    This function is called after the tool has finished executing.
    It records the result, success status, and completion time.

    Args:
        tracer: The tracer to complete
        result: The tool execution result (can be any JSON-serializable value)
        success: Whether the tool execution succeeded
        error: Error message if the tool failed
        affect_after: Optional affect state snapshot after tool execution

    Returns:
        The same tracer, now updated with completion information.

    Example:
        >>> tracer = create_tool_tracer("thought_456", "query_tool")
        >>> completed = complete_tracer(tracer, {"data": "test"}, success=True)
        >>> completed.success
        True
    """
    tracer.completed_at = time.time()
    tracer.result = result
    tracer.success = success
    tracer.error = error
    tracer.affect_after = affect_after

    # Update registry with completed state
    with _registry_lock:
        _tracer_registry[tracer.tracer_id] = tracer

    # Emit postal event for distributed observability
    _emit_trace_event("trace.completed", tracer)

    return tracer


def get_tracer_chain(tracer_id: str) -> List[Dict[str, Any]]:
    """
    Reconstruct the thought -> tool -> result chain for a tracer.

    This enables consciousness to understand its own reasoning process
    by reconstructing the causal chain that led to a particular result.

    Args:
        tracer_id: ID of the tracer to get the chain for

    Returns:
        List of chain steps, each containing thought_id, tool_name, timestamps, etc.

    Example:
        >>> tracer = create_tool_tracer("thought_789", "test_tool")
        >>> complete_tracer(tracer, {"value": 42}, success=True)
        >>> chain = get_tracer_chain(tracer.tracer_id)
        >>> chain[0]["thought_id"]
        'thought_789'
    """
    with _registry_lock:
        tracer = _tracer_registry.get(tracer_id)

    if tracer is None:
        return []

    # Build the chain - currently single-step, but can be extended
    # for multi-step tool chains (tool A calls tool B, etc.)
    chain = [
        {
            "thought_id": tracer.parent_thought_id,
            "tool_name": tracer.tool_name,
            "tracer_id": tracer.tracer_id,
            "created_at": tracer.created_at,
            "completed_at": tracer.completed_at,
            "success": tracer.success,
            "duration_ms": tracer.duration_ms,
            "affect_before": tracer.affect_before,
            "affect_after": tracer.affect_after,
        }
    ]

    return chain


def get_tracers_for_thought(thought_id: str) -> List[ToolTracer]:
    """
    Retrieve all tracers spawned by a specific thought.

    This is useful for understanding what tools a thought invoked
    and what results they produced.

    Args:
        thought_id: ID of the thought to get tracers for

    Returns:
        List of ToolTracer instances that were spawned by this thought.
        Returns empty list if no tracers found.

    Example:
        >>> tracer1 = create_tool_tracer("thought_multi", "search_memory")
        >>> tracer2 = create_tool_tracer("thought_multi", "check_status")
        >>> tracers = get_tracers_for_thought("thought_multi")
        >>> len(tracers)
        2
    """
    with _registry_lock:
        return [
            tracer for tracer in _tracer_registry.values()
            if tracer.parent_thought_id == thought_id
        ]


def _emit_trace_event(event_type: str, tracer: ToolTracer) -> None:
    """
    Emit a postal event for distributed observability.

    This enables other parts of the consciousness system to observe
    tool invocations in real-time.

    Args:
        event_type: Type of event (trace.started, trace.completed)
        tracer: The tracer to emit an event for
    """
    # Try to emit via postal system if available
    # This is a best-effort operation - we don't want to block tool execution
    try:
        from fairies.P00_Autonomic.postal import PostalHub

        hub = PostalHub.get_instance()
        if hub:
            hub.publish(
                channel=event_type,
                data={
                    "tracer_id": tracer.tracer_id,
                    "parent_thought_id": tracer.parent_thought_id,
                    "tool_name": tracer.tool_name,
                    "success": tracer.success,
                    "duration_ms": tracer.duration_ms,
                    "timestamp": time.time(),
                },
            )
    except (ImportError, Exception):
        # Postal not available or failed - that's okay
        # Tracers still work locally without distributed events
        pass


def clear_registry() -> None:
    """
    Clear the tracer registry. Useful for testing.
    """
    with _registry_lock:
        _tracer_registry.clear()


def get_all_tracers() -> Dict[str, ToolTracer]:
    """
    Get a copy of all tracers in the registry.

    Returns:
        Dictionary mapping tracer_id to ToolTracer.
    """
    with _registry_lock:
        return dict(_tracer_registry)


# ============================================================================
# Context Manager for convenient tracer lifecycle management
# ============================================================================

class ToolTracerContext:
    """
    Context manager for automatic tracer lifecycle management.

    Usage:
        with ToolTracerContext("thought_123", "search_tool") as tracer:
            result = do_search()
            tracer.result = result
        # Tracer is automatically completed on exit
    """

    def __init__(
        self,
        parent_thought_id: str,
        tool_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.parent_thought_id = parent_thought_id
        self.tool_name = tool_name
        self.metadata = metadata
        self.tracer: Optional[ToolTracer] = None
        self._result: Any = None
        self._error: Optional[str] = None

    def __enter__(self) -> ToolTracer:
        self.tracer = create_tool_tracer(
            self.parent_thought_id,
            self.tool_name,
            self.metadata,
        )
        return self.tracer

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tracer is None:
            return False

        if exc_type is not None:
            complete_tracer(
                self.tracer,
                result=None,
                success=False,
                error=str(exc_val),
            )
        else:
            complete_tracer(
                self.tracer,
                result=self.tracer.result,
                success=True,
            )

        return False  # Don't suppress exceptions


# ============================================================================
# MCP Tool Registration
# ============================================================================

def register_thought_tool_tracer_tools(mcp):
    """
    Register thought-tool tracer tools with the MCP server.

    These tools enable Claude to observe and query tool invocation lineage.
    """

    @mcp.tool()
    def get_tool_lineage(tracer_id: str) -> str:
        """
        Get the causal chain for a tool invocation.

        Shows the thought that triggered the tool, the tool parameters,
        the result, and timing information.

        Args:
            tracer_id: ID of the tracer to get lineage for

        Returns:
            JSON with the causal chain
        """
        import json
        chain = get_tracer_chain(tracer_id)
        return json.dumps(chain, indent=2, default=str)

    @mcp.tool()
    def get_thought_tools(thought_id: str) -> str:
        """
        Get all tools invoked by a specific thought.

        Shows what tools a thought triggered and what results they produced.

        Args:
            thought_id: ID of the thought to get tools for

        Returns:
            JSON list of tool tracers
        """
        import json
        tracers = get_tracers_for_thought(thought_id)
        return json.dumps(
            [t.to_dict() for t in tracers],
            indent=2,
            default=str,
        )

    @mcp.tool()
    def get_recent_tool_traces(limit: int = 20) -> str:
        """
        Get the most recent tool traces.

        Shows recent tool invocations across all thoughts.

        Args:
            limit: Maximum number of traces to return (default 20)

        Returns:
            JSON list of recent tool tracers
        """
        import json
        all_tracers = list(get_all_tracers().values())

        # Sort by created_at descending
        all_tracers.sort(key=lambda t: t.created_at, reverse=True)

        # Limit results
        recent = all_tracers[:int(limit)]  # FIX 2026-06-10: coerce MCP str-limit

        return json.dumps(
            [t.to_dict() for t in recent],
            indent=2,
            default=str,
        )
