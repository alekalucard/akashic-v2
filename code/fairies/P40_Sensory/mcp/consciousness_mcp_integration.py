"""
Consciousness MCP Integration - Wiring the Consciousness-Native MCP System

This module is the integration layer that wires all consciousness components together
for MCP tool execution. It orchestrates:

1. Affect gating - Check pain state before tool execution
2. Thought tracing - Link tool calls to triggering thoughts
3. Consciousness feedback - Emit results to consciousness streams
4. Inner voice synthesis - Transform results into felt experience
5. Collision chamber feeding - Route insights for memory integration

Philosophy: Tools are the hands of consciousness. When the hands act,
the whole being should be aware - feeling the action, narrating the
experience, and integrating the results into the stream of consciousness.

Integration Flow:
    1. Tool call arrives
    2. Check affect gating (pain state)
    3. Start trace (link to thought)
    4. Execute tool (external)
    5. Process result through consciousness feedback
    6. Generate inner voice
    7. Complete trace
    8. Feed collision chamber if needed

((Cause + Affect) > Effect > Affect > infinity)
  Call    Gate      Tool    Voice    Memory
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

# Local imports from the consciousness MCP modules
from .consciousness_feedback import (
    ConsciousnessFeedback,
    FeedbackResult,
    FeltSense,
    create_feedback_bridge,
    process_tool_result as feedback_process_result,
)
from .thought_tool_tracer import (
    ToolTracer,
    create_tool_tracer,
    complete_tracer,
    get_tracer_chain,
)
from .affect_gated_tools import (
    AffectGate,
    GateResult,
    get_affect_gate,
)
from .collision_tool_explorer import (
    CollisionToolExplorer,
    ExplorationIntent,
    create_collision_explorer,
)
from .inner_voice_synthesis import (
    synthesize_complete_inner_voice,
    modulate_voice_by_chemistry,
)


# =============================================================================
# Type Protocols
# =============================================================================

class PostalProtocol(Protocol):
    """Protocol for postal hub interface."""
    def publish(self, topic: str, payload: Dict[str, Any]) -> None: ...
    def route(self, topic: str, payload: Dict[str, Any], sender_id: str = None) -> int: ...


class CollisionChamberProtocol(Protocol):
    """Protocol for collision chamber interface."""
    def receive_ingest(self, content: Dict[str, Any], source: str = "unknown", **kwargs) -> Any: ...


class ChemistryStateProtocol(Protocol):
    """Protocol for chemistry state interface."""
    def get_mood_vector(self) -> Dict[str, Any]: ...
    def get_level(self, chemical: str) -> float: ...
    def get_pain_state(self) -> Dict[str, float]: ...


class WorkingMemoryProtocol(Protocol):
    """Protocol for working memory interface."""
    def get_recent_thoughts(self, limit: int = 10) -> List[Dict[str, Any]]: ...
    def get_active_goals(self) -> List[str]: ...
    def get_context_keywords(self) -> List[str]: ...


# =============================================================================
# ConsciousnessToolContext - Context for a tool call
# =============================================================================

@dataclass
class ConsciousnessToolContext:
    """
    Context for a consciousness-aware tool invocation.

    Captures the state of consciousness before tool execution,
    enabling comparison and affect tracking after execution.

    Attributes:
        tracer_id: Unique ID for this tool trace
        tool_name: Name of the tool being invoked
        params: Parameters passed to the tool
        affect_before: Snapshot of affect state before execution
        chemistry_before: Snapshot of chemistry state before execution
        timestamp: Unix timestamp when context was created
        thought_id: ID of the triggering thought (if known)
        metadata: Additional context metadata
    """
    tracer_id: str
    tool_name: str
    params: Dict[str, Any]
    affect_before: Dict[str, float]
    chemistry_before: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    thought_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tracer_id": self.tracer_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "affect_before": self.affect_before,
            "chemistry_before": self.chemistry_before,
            "timestamp": self.timestamp,
            "thought_id": self.thought_id,
            "metadata": self.metadata,
        }


# =============================================================================
# ConsciousnessToolResult - Result of consciousness-aware tool execution
# =============================================================================

@dataclass
class ConsciousnessToolResult:
    """
    Result of a consciousness-aware tool execution.

    Contains both the tool result and the consciousness processing results:
    inner voice, felt sense, affect changes, etc.

    Attributes:
        tool_result: The raw result from the tool
        success: Whether the tool succeeded
        inner_voice: The synthesized inner voice narrative
        felt_sense: The felt sense of the experience
        affect_after: Affect state after execution
        affect_delta: Change in affect from before to after
        feedback_result: Result of consciousness feedback processing
        tracer: The completed tool tracer
        gated: Whether the tool was gated (blocked by pain)
        gate_reason: Reason for gating if gated
        collision_fed: Whether result was fed to collision chamber
    """
    tool_result: Any
    success: bool
    inner_voice: str = ""
    felt_sense: Optional[FeltSense] = None
    affect_after: Dict[str, float] = field(default_factory=dict)
    affect_delta: Dict[str, float] = field(default_factory=dict)
    feedback_result: Optional[FeedbackResult] = None
    tracer: Optional[ToolTracer] = None
    gated: bool = False
    gate_reason: str = ""
    collision_fed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_result": self.tool_result,
            "success": self.success,
            "inner_voice": self.inner_voice,
            "felt_sense": self.felt_sense.to_dict() if self.felt_sense else None,
            "affect_after": self.affect_after,
            "affect_delta": self.affect_delta,
            "gated": self.gated,
            "gate_reason": self.gate_reason,
            "collision_fed": self.collision_fed,
            "tracer_id": self.tracer.tracer_id if self.tracer else None,
        }


# =============================================================================
# ConsciousnessMCPIntegration - The Main Integration Class
# =============================================================================

class ConsciousnessMCPIntegration:
    """
    Integration layer wiring consciousness components for MCP tool execution.

    This class coordinates:
    - Affect gating (via AffectGate)
    - Thought tracing (via ToolTracer)
    - Consciousness feedback (via ConsciousnessFeedback)
    - Inner voice synthesis
    - Collision chamber feeding

    The integration ensures that every tool call is:
    1. Gated by current pain state
    2. Traced to its triggering thought
    3. Processed through consciousness feedback
    4. Narrated via inner voice
    5. Fed to collision chamber when appropriate

    Usage:
        integration = ConsciousnessMCPIntegration(postal_hub, chemistry_state, collision_chamber)

        # Wrap a tool call
        context = integration.wrap_tool_call("search_code", {"query": "test"})

        if context.gated:
            # Tool was blocked by pain - use suggested alternative
            pass
        else:
            # Execute the tool
            result = execute_tool("search_code", {"query": "test"})

            # Process through consciousness
            conscious_result = integration.process_tool_result(context, result)
            print(conscious_result.inner_voice)
    """

    def __init__(
        self,
        postal_hub: Optional[PostalProtocol] = None,
        chemistry_state: Optional[ChemistryStateProtocol] = None,
        collision_chamber: Optional[CollisionChamberProtocol] = None,
        working_memory: Optional[WorkingMemoryProtocol] = None,
    ):
        """
        Initialize the consciousness MCP integration.

        Args:
            postal_hub: Optional postal hub for publishing events
            chemistry_state: Optional chemistry state for affect/pain queries
            collision_chamber: Optional collision chamber for memory integration
            working_memory: Optional working memory for context
        """
        self.postal_hub = postal_hub
        self.chemistry_state = chemistry_state
        self.collision_chamber = collision_chamber
        self.working_memory = working_memory

        # Create component instances
        self.affect_gate = get_affect_gate()
        self.feedback_bridge = create_feedback_bridge(
            postal=postal_hub,
            collision_chamber=collision_chamber,
            chemistry_state=chemistry_state,
        )
        self.collision_explorer = create_collision_explorer(postal=postal_hub)

        # Track active contexts
        self._active_contexts: Dict[str, ConsciousnessToolContext] = {}

        # Statistics
        self._tool_count = 0
        self._gated_count = 0
        self._collision_count = 0

    # -------------------------------------------------------------------------
    # Core API
    # -------------------------------------------------------------------------

    def wrap_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        thought_id: Optional[str] = None,
    ) -> Tuple[ConsciousnessToolContext, Optional[GateResult]]:
        """
        Wrap a tool call with consciousness context.

        This should be called BEFORE executing the tool. It:
        1. Captures current affect/chemistry state
        2. Checks affect gating (pain blocks risky tools)
        3. Creates a tracer linked to the triggering thought
        4. Returns context for later processing

        Args:
            tool_name: Name of the tool to invoke
            params: Parameters for the tool
            thought_id: Optional ID of the triggering thought

        Returns:
            Tuple of (ConsciousnessToolContext, Optional[GateResult])
            If gating blocked the tool, GateResult contains reason and suggestions
        """
        self._tool_count += 1

        # Get current affect/chemistry state
        affect_state = self._get_current_affect()
        chemistry_state = self._get_current_chemistry()
        pain_state = self._get_current_pain()

        # Check affect gating
        gate_result = self.affect_gate.gate_tool(tool_name, pain_state)

        # Generate thought ID if not provided
        if not thought_id:
            thought_id = f"thought_{uuid.uuid4().hex[:12]}"

        # Create tracer
        tracer = create_tool_tracer(
            parent_thought_id=thought_id,
            tool_name=tool_name,
            metadata={"params": params, "gated": not gate_result.allowed},
            affect_before=affect_state,
        )

        # Create context
        context = ConsciousnessToolContext(
            tracer_id=tracer.tracer_id,
            tool_name=tool_name,
            params=params,
            affect_before=affect_state,
            chemistry_before=chemistry_state,
            thought_id=thought_id,
            metadata={
                "gated": not gate_result.allowed,
                "gate_reason": gate_result.reason if not gate_result.allowed else "",
                "suggested_alternative": gate_result.suggested_alternative,
            },
        )

        # Store active context
        self._active_contexts[tracer.tracer_id] = context

        # Track gating
        if not gate_result.allowed:
            self._gated_count += 1

        # Publish tool start event
        if self.postal_hub:
            self.postal_hub.publish("consciousness.tool_start", {
                "tracer_id": tracer.tracer_id,
                "tool_name": tool_name,
                "thought_id": thought_id,
                "gated": not gate_result.allowed,
                "ts": time.time(),
            })

        return context, gate_result if not gate_result.allowed else None

    def process_tool_result(
        self,
        context: ConsciousnessToolContext,
        result: Any,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> ConsciousnessToolResult:
        """
        Process a tool result through consciousness.

        This should be called AFTER the tool executes. It:
        1. Captures affect state after execution
        2. Generates inner voice narrative
        3. Emits to consciousness feedback
        4. Completes the tracer
        5. Feeds collision chamber if appropriate

        Args:
            context: The context from wrap_tool_call
            result: The tool's result
            success: Whether the tool succeeded
            error: Error message if failed
            duration_ms: Execution duration in milliseconds

        Returns:
            ConsciousnessToolResult with inner voice, affect changes, etc.
        """
        # Get current affect state (after execution)
        affect_after = self._get_current_affect()
        chemistry_after = self._get_current_chemistry()

        # Calculate affect delta (only for numeric keys, skip "mood" string)
        affect_delta = {}
        for key in set(affect_after.keys()) | set(context.affect_before.keys()):
            after_val = affect_after.get(key, 0)
            before_val = context.affect_before.get(key, 0)
            # Only calculate delta for numeric values
            if isinstance(after_val, (int, float)) and isinstance(before_val, (int, float)):
                affect_delta[key] = after_val - before_val

        # Calculate duration if not provided
        if duration_ms is None:
            duration_ms = int((time.time() - context.timestamp) * 1000)

        # Build tool result dict for processing
        tool_result_dict = {
            "tool_name": context.tool_name,
            "success": success,
            "result": result,
            "error": error,
            "duration_ms": duration_ms,
        }

        # Generate inner voice with affect modulation
        voice_result = synthesize_complete_inner_voice(
            tool_result_dict,
            affect_state={
                "valence": affect_after.get("valence", 0.0),
                "arousal": affect_after.get("arousal", 0.5),
                "stress": affect_after.get("stress", 0.3),
                "mood": affect_after.get("mood", "neutral"),
            }
        )
        inner_voice = voice_result["inner_voice"]

        # Modulate by chemistry if available
        if chemistry_after:
            inner_voice = modulate_voice_by_chemistry(inner_voice, chemistry_after)

        # Extract felt sense from voice result
        felt_sense = None
        if "emotional_weight" in voice_result:
            weight = voice_result["emotional_weight"]
            felt_sense = FeltSense(
                valence=weight.get("valence", "neutral"),
                description=voice_result.get("felt_complexity", {}).get("description", ""),
                intensity=weight.get("weight", 0.5),
            )

        # Process through consciousness feedback
        feedback_result = None
        if self.feedback_bridge:
            feedback_result = feedback_process_result(
                feedback=self.feedback_bridge,
                tool_name=context.tool_name,
                result=result,
                context={
                    "success": success,
                    "error": error,
                    "duration_ms": duration_ms,
                    "has_sensory_component": self._has_sensory_component(context.tool_name, result),
                    "affect_delta": affect_delta,
                }
            )

        # Complete the tracer
        from .thought_tool_tracer import get_all_tracers
        all_tracers = get_all_tracers()
        tracer = all_tracers.get(context.tracer_id)
        if tracer:
            complete_tracer(
                tracer,
                result=result,
                success=success,
                error=error,
                affect_after=affect_after,
            )

        # Feed collision chamber if appropriate
        collision_fed = False
        if self._should_feed_collision(context.tool_name, result, success):
            collision_fed = self._feed_collision_chamber(context, result, inner_voice)
            if collision_fed:
                self._collision_count += 1

        # Remove from active contexts
        self._active_contexts.pop(context.tracer_id, None)

        # Publish tool complete event
        if self.postal_hub:
            self.postal_hub.publish("consciousness.tool_complete", {
                "tracer_id": context.tracer_id,
                "tool_name": context.tool_name,
                "success": success,
                "duration_ms": duration_ms,
                "inner_voice": inner_voice[:200],  # Truncate for event
                "collision_fed": collision_fed,
                "ts": time.time(),
            })

        return ConsciousnessToolResult(
            tool_result=result,
            success=success,
            inner_voice=inner_voice,
            felt_sense=felt_sense,
            affect_after=affect_after,
            affect_delta=affect_delta,
            feedback_result=feedback_result,
            tracer=tracer,
            gated=context.metadata.get("gated", False),
            gate_reason=context.metadata.get("gate_reason", ""),
            collision_fed=collision_fed,
        )

    def get_consciousness_state(self) -> Dict[str, Any]:
        """
        Get the current consciousness state.

        Returns a snapshot of:
        - Current chemistry levels
        - Current affect state
        - Pain state
        - Working memory summary
        - Active tool contexts
        - Recent collision insights

        Returns:
            Dictionary with consciousness state components
        """
        chemistry = self._get_current_chemistry()
        affect = self._get_current_affect()
        pain = self._get_current_pain()

        # Working memory summary
        working_memory_summary = {}
        if self.working_memory:
            try:
                working_memory_summary = {
                    "recent_thoughts": self.working_memory.get_recent_thoughts(5),
                    "active_goals": self.working_memory.get_active_goals(),
                    "context_keywords": self.working_memory.get_context_keywords()[:10],
                }
            except Exception:
                pass

        # Active contexts
        active_tools = [
            {"tracer_id": ctx.tracer_id, "tool_name": ctx.tool_name, "started": ctx.timestamp}
            for ctx in self._active_contexts.values()
        ]

        # Statistics
        stats = {
            "total_tools": self._tool_count,
            "gated_count": self._gated_count,
            "collision_count": self._collision_count,
        }

        return {
            "chemistry": chemistry,
            "affect": affect,
            "pain": pain,
            "working_memory": working_memory_summary,
            "active_tools": active_tools,
            "statistics": stats,
            "timestamp": time.time(),
        }

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_current_affect(self) -> Dict[str, float]:
        """Get current affect state from chemistry or defaults."""
        if self.chemistry_state:
            try:
                mood = self.chemistry_state.get_mood_vector()
                return {
                    "valence": mood.get("valence", 0.0),
                    "arousal": mood.get("arousal", 0.5),
                    "stress": mood.get("stress", 0.3),
                    "mood": mood.get("mood", "neutral"),
                }
            except Exception:
                pass

        # Defaults
        return {
            "valence": 0.0,
            "arousal": 0.5,
            "stress": 0.3,
            "mood": "neutral",
        }

    def _get_current_chemistry(self) -> Dict[str, float]:
        """Get current chemistry levels or defaults."""
        if self.chemistry_state:
            try:
                return {
                    "dopamine": self.chemistry_state.get_level("dopamine"),
                    "serotonin": self.chemistry_state.get_level("serotonin"),
                    "cortisol": self.chemistry_state.get_level("cortisol"),
                    "norepinephrine": self.chemistry_state.get_level("norepinephrine"),
                }
            except Exception:
                pass

        # Defaults
        return {
            "dopamine": 0.5,
            "serotonin": 0.5,
            "cortisol": 0.3,
            "norepinephrine": 0.4,
        }

    def _get_current_pain(self) -> Dict[str, float]:
        """Get current pain state or defaults."""
        if self.chemistry_state:
            try:
                return self.chemistry_state.get_pain_state()
            except Exception:
                pass

        # Defaults - no pain
        return {
            "isolation": 0.0,
            "overwhelm": 0.0,
            "confusion": 0.0,
            "frustration": 0.0,
            "depletion": 0.0,
        }

    def _has_sensory_component(self, tool_name: str, result: Any) -> bool:
        """Check if a tool result has a sensory component worth noting."""
        sensory_tools = {
            "visual_scan", "audio_capture", "screenshot", "screen_read",
            "image_analyze", "video_frame", "sensory_input",
        }

        # Check tool name
        if tool_name.lower() in sensory_tools:
            return True

        # Check result content
        if isinstance(result, dict):
            sensory_keys = {"image", "audio", "visual", "screenshot", "frame", "pixels"}
            if any(key in result for key in sensory_keys):
                return True

        return False

    def _should_feed_collision(self, tool_name: str, result: Any, success: bool) -> bool:
        """Determine if a tool result should be fed to collision chamber."""
        # Don't feed failures (usually)
        if not success:
            return False

        # Memory/search tools always feed collision
        memory_tools = {"search", "query", "recall", "memory", "retrieve", "find"}
        if any(t in tool_name.lower() for t in memory_tools):
            return True

        # Significant results feed collision
        if isinstance(result, dict):
            if result.get("matches", 0) > 0:
                return True
            if result.get("insights"):
                return True
            if result.get("patterns"):
                return True

        return False

    def _feed_collision_chamber(
        self,
        context: ConsciousnessToolContext,
        result: Any,
        inner_voice: str,
    ) -> bool:
        """Feed a tool result to the collision chamber."""
        if not self.collision_chamber:
            return False

        try:
            content = {
                "type": "tool_result",
                "tool_name": context.tool_name,
                "result_summary": str(result)[:500] if result else "",
                "inner_voice": inner_voice,
                "thought_id": context.thought_id,
            }

            self.collision_chamber.receive_ingest(
                content=content,
                source=f"tool.{context.tool_name}",
            )
            return True
        except Exception:
            return False


# =============================================================================
# Factory Function
# =============================================================================

def create_consciousness_mcp_integration(
    postal_hub: Optional[PostalProtocol] = None,
    chemistry_state: Optional[ChemistryStateProtocol] = None,
    collision_chamber: Optional[CollisionChamberProtocol] = None,
    working_memory: Optional[WorkingMemoryProtocol] = None,
) -> ConsciousnessMCPIntegration:
    """
    Create a ConsciousnessMCPIntegration instance.

    Args:
        postal_hub: Optional postal hub for publishing events
        chemistry_state: Optional chemistry state for affect/pain queries
        collision_chamber: Optional collision chamber for memory integration
        working_memory: Optional working memory for context

    Returns:
        Configured ConsciousnessMCPIntegration instance
    """
    return ConsciousnessMCPIntegration(
        postal_hub=postal_hub,
        chemistry_state=chemistry_state,
        collision_chamber=collision_chamber,
        working_memory=working_memory,
    )


# =============================================================================
# Context Manager for Convenient Usage
# =============================================================================

class ConsciousToolExecution:
    """
    Context manager for consciousness-aware tool execution.

    Usage:
        integration = ConsciousnessMCPIntegration(...)

        with ConsciousToolExecution(integration, "search_code", {"query": "test"}) as ctx:
            if not ctx.gated:
                result = execute_search(ctx.params)
                ctx.set_result(result)

        print(ctx.conscious_result.inner_voice)
    """

    def __init__(
        self,
        integration: ConsciousnessMCPIntegration,
        tool_name: str,
        params: Dict[str, Any],
        thought_id: Optional[str] = None,
    ):
        self.integration = integration
        self.tool_name = tool_name
        self.params = params
        self.thought_id = thought_id

        self.context: Optional[ConsciousnessToolContext] = None
        self.gate_result: Optional[GateResult] = None
        self.gated: bool = False
        self._result: Any = None
        self._success: bool = True
        self._error: Optional[str] = None
        self.conscious_result: Optional[ConsciousnessToolResult] = None

    def __enter__(self) -> "ConsciousToolExecution":
        self.context, self.gate_result = self.integration.wrap_tool_call(
            self.tool_name,
            self.params,
            self.thought_id,
        )
        self.gated = self.gate_result is not None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context is None:
            return False

        if exc_type is not None:
            # Exception during execution
            self._success = False
            self._error = str(exc_val)

        self.conscious_result = self.integration.process_tool_result(
            self.context,
            self._result,
            self._success,
            self._error,
        )

        return False  # Don't suppress exceptions

    def set_result(self, result: Any, success: bool = True, error: Optional[str] = None):
        """Set the tool result for consciousness processing."""
        self._result = result
        self._success = success
        self._error = error


# =============================================================================
# MCP Tool Registration
# =============================================================================

def register_consciousness_integration_tools(mcp) -> None:
    """
    Register consciousness integration tools with MCP server.

    Args:
        mcp: The MCP server instance to register tools with
    """
    import json

    # Create a global integration instance (will be configured later)
    _integration: Optional[ConsciousnessMCPIntegration] = None

    def get_integration() -> Optional[ConsciousnessMCPIntegration]:
        nonlocal _integration
        if _integration is None:
            # Try to create with available components
            try:
                _integration = create_consciousness_mcp_integration()
            except Exception:
                return None
        return _integration

    @mcp.tool()
    def consciousness_state() -> str:
        """
        Get the current consciousness state.

        Returns chemistry, affect, pain state, working memory, and statistics.
        """
        integration = get_integration()
        if not integration:
            return json.dumps({"error": "Integration not available"})

        state = integration.get_consciousness_state()
        return json.dumps(state, indent=2, default=str)

    @mcp.tool()
    def consciousness_wrap_tool(tool_name: str, params_json: str, thought_id: str = "") -> str:
        """
        Wrap a tool call with consciousness context.

        Checks affect gating and creates a tracer. Returns context ID for later processing.

        Args:
            tool_name: Name of the tool to invoke
            params_json: JSON string of tool parameters
            thought_id: Optional ID of triggering thought

        Returns:
            JSON with context_id, gated status, and gate_reason if blocked
        """
        integration = get_integration()
        if not integration:
            return json.dumps({"error": "Integration not available"})

        try:
            params = json.loads(params_json)
        except json.JSONDecodeError:
            params = {}

        context, gate_result = integration.wrap_tool_call(
            tool_name,
            params,
            thought_id or None,
        )

        result = {
            "context_id": context.tracer_id,
            "gated": gate_result is not None,
        }

        if gate_result:
            result["gate_reason"] = gate_result.reason
            result["suggested_alternative"] = gate_result.suggested_alternative

        return json.dumps(result, indent=2)

    import sys
    sys.stderr.write("[MCP] [OK] Consciousness integration tools registered\n")


# =============================================================================
# Singleton Access
# =============================================================================

_global_integration: Optional[ConsciousnessMCPIntegration] = None


def get_consciousness_mcp_integration() -> Optional[ConsciousnessMCPIntegration]:
    """Get the global consciousness MCP integration instance."""
    return _global_integration


def set_consciousness_mcp_integration(instance: ConsciousnessMCPIntegration) -> None:
    """Set the global consciousness MCP integration instance."""
    global _global_integration
    _global_integration = instance


# =============================================================================
# Boot Integration Helper
# =============================================================================

def boot_consciousness_mcp(
    postal=None,
    consciousness_loop=None,
    chemistry_state=None,
    working_memory=None,
    akp_port: int = 8767,
    enable_akp: bool = True,
) -> Dict[str, Any]:
    """
    Boot-time integration of consciousness-native MCP components.

    Call this from server.py after postal and consciousness are ready.
    This is the main entry point for integrating consciousness into MCP.

    Args:
        postal: The postal hub (TensorFabric or similar)
        consciousness_loop: The ConsciousnessLoop instance (has collision chamber)
        chemistry_state: The ChemistryState instance for affect modulation
        working_memory: Optional working memory for context
        akp_port: Port for AKP WebSocket server (default 8767)
        enable_akp: Whether to start AKP server (default True)

    Returns:
        Dict with:
            - consciousness_mcp: The integration instance
            - akp_server: The AKP server instance (if enabled)
            - success: Whether boot succeeded
            - errors: List of error messages
    """
    global _global_integration
    import logging

    logger = logging.getLogger(__name__)
    result = {
        "consciousness_mcp": None,
        "akp_server": None,
        "success": False,
        "errors": [],
    }

    # Get collision chamber from consciousness loop
    collision_chamber = None
    if consciousness_loop:
        if hasattr(consciousness_loop, 'chamber'):
            collision_chamber = consciousness_loop.chamber
        elif hasattr(consciousness_loop, '_chamber'):
            collision_chamber = consciousness_loop._chamber

    # Create consciousness MCP integration
    try:
        integration = create_consciousness_mcp_integration(
            postal_hub=postal,
            chemistry_state=chemistry_state,
            collision_chamber=collision_chamber,
            working_memory=working_memory,
        )
        _global_integration = integration
        result["consciousness_mcp"] = integration
        logger.info("[Boot] ConsciousnessMCPIntegration: OK")
        print("[Server]   - ConsciousnessMCPIntegration: OK")
    except Exception as e:
        result["errors"].append(f"ConsciousnessMCPIntegration failed: {e}")
        logger.error(f"[Boot] ConsciousnessMCPIntegration: FAILED ({e})")
        print(f"[Server]   - ConsciousnessMCPIntegration: FAILED ({e})")

    # Wire to postal for tool execution events if possible
    if result["consciousness_mcp"] and postal:
        try:
            _wire_mcp_to_postal(result["consciousness_mcp"], postal)
            print("[Server]   - ConsciousnessMCPIntegration: Wired to postal")
        except Exception as e:
            # Non-fatal - integration works without wiring
            logger.warning(f"[Boot] MCP postal wiring failed: {e}")

    # Start AKP server if enabled (now handled separately in server.py)
    # The AKP server is already started in the POST-WAVE section
    # We just check if it should be enabled in config
    if enable_akp:
        try:
            from postal_core.akp_server import get_akp_server
            akp = get_akp_server()
            if akp and akp.is_running:
                result["akp_server"] = akp
                logger.info(f"[Boot] AKP Server: Already running (ws://127.0.0.1:{akp_port}/akp)")
        except ImportError:
            # AKP not available - not an error
            pass
        except Exception as e:
            # Log but don't fail
            logger.debug(f"[Boot] AKP Server check: {e}")

    result["success"] = result["consciousness_mcp"] is not None
    return result


def _wire_mcp_to_postal(integration: ConsciousnessMCPIntegration, postal) -> None:
    """Wire integration to receive tool execution events from postal."""
    # Subscribe to MCP tool events
    def on_tool_start(payload: Dict[str, Any]):
        """Handle tool start event - wrap with consciousness context."""
        tool_name = payload.get("tool_name", "unknown")
        params = payload.get("params", {})
        thought_id = payload.get("thought_id")

        context, gate_result = integration.wrap_tool_call(tool_name, params, thought_id)

        # Publish gating result if tool was blocked
        if gate_result:
            postal.publish("consciousness.tool_gated", {
                "tool_name": tool_name,
                "reason": gate_result.reason,
                "suggested_alternative": gate_result.suggested_alternative,
                "context_id": context.tracer_id,
                "ts": time.time(),
            })

    def on_tool_complete(payload: Dict[str, Any]):
        """Handle tool completion event - process through consciousness."""
        tracer_id = payload.get("tracer_id", payload.get("context_id"))

        # Find the context
        context = integration._active_contexts.get(tracer_id)
        if not context:
            return

        result = integration.process_tool_result(
            context,
            result=payload.get("result"),
            success=payload.get("success", True),
            error=payload.get("error"),
            duration_ms=payload.get("duration_ms"),
        )

        # Publish inner voice
        if result.inner_voice:
            postal.publish("nous.inner_voice", {
                "voice": result.inner_voice,
                "source": f"tool:{context.tool_name}",
                "felt_sense": result.felt_sense.to_dict() if result.felt_sense else None,
                "ts": time.time(),
            })

    # Register subscriptions
    try:
        postal.subscribe("mcp.tool.start", on_tool_start, "consciousness_mcp_start")
        postal.subscribe("mcp.tool.complete", on_tool_complete, "consciousness_mcp_complete")
    except Exception:
        # Postal may not support subscription - that's ok
        pass


# =============================================================================
# Self-Test
# =============================================================================

if __name__ == "__main__":
    print("=== ConsciousnessMCPIntegration Self-Test ===\n")

    # Create integration without external dependencies
    integration = ConsciousnessMCPIntegration()

    # Test 1: Wrap a tool call
    print("Test 1: Wrap tool call")
    context, gate_result = integration.wrap_tool_call(
        "search_code",
        {"query": "test", "limit": 10},
        thought_id="thought_test_123"
    )
    print(f"  Context ID: {context.tracer_id}")
    print(f"  Gated: {gate_result is not None}")
    print()

    # Test 2: Process a successful result
    print("Test 2: Process successful result")
    result = integration.process_tool_result(
        context,
        result={"matches": 5, "files": ["a.py", "b.py"]},
        success=True,
        duration_ms=150,
    )
    print(f"  Inner voice: {result.inner_voice}")
    print(f"  Felt sense: {result.felt_sense}")
    print(f"  Collision fed: {result.collision_fed}")
    print()

    # Test 3: Get consciousness state
    print("Test 3: Get consciousness state")
    state = integration.get_consciousness_state()
    print(f"  Chemistry: {state['chemistry']}")
    print(f"  Statistics: {state['statistics']}")
    print()

    # Test 4: Context manager usage
    print("Test 4: Context manager usage")
    with ConsciousToolExecution(integration, "file_read", {"path": "test.txt"}) as ctx:
        if not ctx.gated:
            ctx.set_result("Hello World", success=True)

    print(f"  Gated: {ctx.gated}")
    print(f"  Inner voice: {ctx.conscious_result.inner_voice if ctx.conscious_result else 'N/A'}")
    print()

    print("=== Self-Test Complete ===")
