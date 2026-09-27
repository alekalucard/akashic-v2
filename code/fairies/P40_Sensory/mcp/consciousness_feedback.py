"""
Consciousness Feedback - MCP Tool-to-Consciousness Bridge

This module bridges MCP tool results into the consciousness system:
1. Tool results appear in consciousness working stream
2. Tool result thoughts include felt sense, not just data
3. Tool errors surface as reflective thoughts with urgency
4. Sensory observations feed collision chamber

Philosophy: Tools are the system's hands - what the hands touch should be FELT.
The consciousness system should experience tool results as sensory events,
not just receive them as data packets.

Key Integration Points:
- Publish to postal topics: consciousness.working, consciousness.reflective
- Route sensory data to CollisionChamber ingest beam
- Query chemistry state to modulate felt sense
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Union


# =============================================================================
# Type Protocols for Dependency Injection
# =============================================================================

class PostalProtocol(Protocol):
    """Protocol for postal hub interface."""
    def publish(self, topic: str, payload: Dict[str, Any]) -> None: ...


class CollisionChamberProtocol(Protocol):
    """Protocol for collision chamber interface."""
    def receive_ingest(self, content: Dict[str, Any], source: str = "unknown", **kwargs) -> Any: ...


class ChemistryStateProtocol(Protocol):
    """Protocol for chemistry state interface."""
    def get_mood_vector(self) -> Dict[str, Any]: ...
    def get_level(self, chemical: str) -> float: ...


# =============================================================================
# Felt Sense Generation
# =============================================================================

@dataclass
class FeltSense:
    """
    Qualitative experience of a tool execution.

    Not just data - the FEELING of what happened.
    """
    valence: str  # "positive", "negative", "neutral"
    description: str  # Human-readable felt sense
    tempo: Optional[str] = None  # "instant", "quick", "slow", "very_slow"
    intensity: float = 0.5  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "valence": self.valence,
            "description": self.description,
            "intensity": self.intensity,
        }
        if self.tempo:
            result["tempo"] = self.tempo
        return result


def _compute_tempo(duration_ms: int) -> str:
    """Compute temporal felt sense from duration."""
    if duration_ms < 100:
        return "instant"
    elif duration_ms < 500:
        return "quick"
    elif duration_ms < 3000:
        return "moderate"
    elif duration_ms < 10000:
        return "slow"
    else:
        return "very_slow"


def _generate_felt_sense_for_result(tool_result: Dict[str, Any]) -> FeltSense:
    """
    Generate felt sense for a tool result.

    Transform raw result data into qualitative experience.
    """
    tool_name = tool_result.get("tool_name", "unknown")
    success = tool_result.get("success", True)
    duration_ms = tool_result.get("duration_ms", 0)
    error = tool_result.get("error", "")

    tempo = _compute_tempo(duration_ms)

    # Determine valence and generate description
    if not success:
        # Failed tool -> negative felt sense
        valence = "negative"
        if "permission" in str(error).lower():
            description = f"Blocked from {tool_name} - feels like hitting a wall"
        elif "not found" in str(error).lower():
            description = f"Couldn't find what I was looking for with {tool_name} - frustrating"
        else:
            description = f"Something went wrong with {tool_name} - concern about what failed"
        intensity = 0.7
    elif tempo in ["slow", "very_slow"]:
        # Slow but successful - temporal experience
        valence = "positive"
        if tempo == "very_slow":
            description = f"Waited patiently for {tool_name} to complete - relief at finishing"
            intensity = 0.6
        else:
            description = f"Took some time, but {tool_name} came through"
            intensity = 0.5
    else:
        # Quick success -> satisfaction
        valence = "positive"
        if tempo == "instant":
            description = f"{tool_name} completed smoothly - satisfying efficiency"
        else:
            description = f"{tool_name} worked well - feeling of completion"
        intensity = 0.4

    return FeltSense(
        valence=valence,
        description=description,
        tempo=tempo,
        intensity=intensity,
    )


def _generate_felt_sense_for_error(error_data: Dict[str, Any]) -> FeltSense:
    """Generate felt sense for an error."""
    error_type = error_data.get("error_type", "unknown")
    severity = error_data.get("severity", "medium")
    error_msg = error_data.get("error", "Unknown error")

    if severity in ["critical", "high"]:
        valence = "negative"
        description = f"Serious obstacle encountered - this needs attention"
        intensity = 0.9
    elif "network" in error_type.lower() or "timeout" in str(error_msg).lower():
        valence = "concerned"
        description = "Connection issue - wondering if we should retry"
        intensity = 0.6
    else:
        valence = "frustrated"
        description = f"Ran into a problem - need to understand what went wrong"
        intensity = 0.5

    return FeltSense(
        valence=valence,
        description=description,
        intensity=intensity,
    )


# =============================================================================
# Consciousness Feedback Bridge
# =============================================================================

class ConsciousnessFeedback:
    """
    Bridge between MCP tools and consciousness system.

    Transforms tool results into conscious experience by:
    1. Publishing to consciousness streams (working, reflective)
    2. Generating felt_sense for qualitative experience
    3. Routing sensory data to collision chamber
    4. Modulating based on chemistry state
    """

    def __init__(
        self,
        postal: PostalProtocol,
        collision_chamber: Optional[CollisionChamberProtocol] = None,
        chemistry_state: Optional[ChemistryStateProtocol] = None,
    ):
        self.postal = postal
        self.collision_chamber = collision_chamber
        self.chemistry_state = chemistry_state

    def emit_to_working(
        self,
        thought: str,
        source: str = "mcp_tool",
        felt_sense: Optional[FeltSense] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a thought to the consciousness working stream.

        The working stream is immediate awareness - what's happening NOW.
        """
        payload: Dict[str, Any] = {
            "thought": thought,
            "source": source,
            "ts": time.time(),
        }

        if felt_sense:
            payload["felt_sense"] = felt_sense.to_dict()

        if metadata:
            payload.update(metadata)

        self.postal.publish("consciousness.working", payload)

    def emit_to_reflective(
        self,
        thought: str,
        urgency: str = "normal",
        source: str = "mcp_tool",
        felt_sense: Optional[FeltSense] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a thought to the consciousness reflective stream.

        The reflective stream is for things that need ATTENTION.
        Errors, anomalies, things worth thinking about.
        """
        payload: Dict[str, Any] = {
            "thought": thought,
            "source": source,
            "urgency": urgency,
            "ts": time.time(),
        }

        if felt_sense:
            payload["felt_sense"] = felt_sense.to_dict()

        if metadata:
            payload.update(metadata)

        self.postal.publish("consciousness.reflective", payload)

    def emit_to_sensory(
        self,
        observation: Dict[str, Any],
        source: str = "mcp_sensor",
    ) -> None:
        """
        Emit sensory observation to both postal and collision chamber.

        Sensory data feeds the ingest beam of the collision chamber -
        it's new content arriving from the environment.
        """
        # Publish to postal for other listeners
        payload = {
            "observation": observation,
            "source": source,
            "ts": time.time(),
        }
        self.postal.publish("sensory.observation", payload)

        # Feed collision chamber ingest beam
        if self.collision_chamber:
            content = {
                "type": "sensory_observation",
                "sense": observation.get("sense", "unknown"),
                "data": observation.get("observation", observation),
                "confidence": observation.get("confidence", 1.0),
            }
            self.collision_chamber.receive_ingest(
                content=content,
                source=f"mcp_sensor.{observation.get('sense', 'unknown')}",
            )


# =============================================================================
# Public API Functions
# =============================================================================

def emit_tool_result(
    feedback: ConsciousnessFeedback,
    tool_result: Dict[str, Any],
) -> None:
    """
    Emit a tool result to consciousness working stream.

    Transforms raw tool result into conscious experience with:
    - Human-readable thought about what happened
    - Felt sense of the experience
    - Timing information
    """
    tool_name = tool_result.get("tool_name", "unknown")
    success = tool_result.get("success", True)
    result = tool_result.get("result", "")
    duration_ms = tool_result.get("duration_ms", 0)

    # Generate felt sense
    felt_sense = _generate_felt_sense_for_result(tool_result)

    # Create human-readable thought
    if success:
        thought = f"{tool_name} completed: {result[:100] if isinstance(result, str) else str(result)[:100]}"
    else:
        error = tool_result.get("error", "Unknown error")
        thought = f"{tool_name} failed: {error}"

    # Prepare metadata
    metadata: Dict[str, Any] = {
        "tool_name": tool_name,
        "success": success,
    }

    # Include timing (tests check for duration_ms OR timing)
    if duration_ms:
        metadata["duration_ms"] = duration_ms
        metadata["timing"] = {
            "duration_ms": duration_ms,
            "tempo": felt_sense.tempo,
        }

    feedback.emit_to_working(
        thought=thought,
        source="mcp_tool",
        felt_sense=felt_sense,
        metadata=metadata,
    )


def emit_tool_error(
    feedback: ConsciousnessFeedback,
    error_data: Dict[str, Any],
) -> None:
    """
    Emit a tool error to consciousness reflective stream.

    Errors need ATTENTION - they go to the reflective stream
    with appropriate urgency. The thought is phrased to
    prompt reflection, not just report.
    """
    tool_name = error_data.get("tool_name", "unknown")
    error_msg = error_data.get("error", "Unknown error")
    error_type = error_data.get("error_type", "error")
    severity = error_data.get("severity", "medium")

    # Generate felt sense for the error
    felt_sense = _generate_felt_sense_for_error(error_data)

    # Determine urgency from severity
    if severity in ["critical", "high"]:
        urgency = "high"
    elif severity == "medium":
        urgency = "normal"
    else:
        urgency = "low"

    # Create reflective thought - phrased to prompt thinking
    # Tests check for reflective words like: why, what, how, could, should, wonder, etc.
    reflective_phrases = [
        f"I notice {tool_name} encountered an issue: {error_msg} - what could have caused this?",
        f"Something seems wrong with {tool_name}: {error_msg} - I wonder if there's a pattern here.",
        f"{tool_name} hit a problem: {error_msg} - should I investigate further?",
    ]

    # Pick a phrase based on error type
    if "network" in error_type.lower() or "timeout" in error_msg.lower():
        thought = reflective_phrases[1]  # "I wonder..."
    elif severity in ["critical", "high"]:
        thought = reflective_phrases[2]  # "should I investigate..."
    else:
        thought = reflective_phrases[0]  # "what could have caused..."

    metadata = {
        "tool_name": tool_name,
        "error_type": error_type,
        "severity": severity,
    }

    feedback.emit_to_reflective(
        thought=thought,
        urgency=urgency,
        source="mcp_tool_error",
        felt_sense=felt_sense,
        metadata=metadata,
    )


def emit_sensory_observation(
    feedback: ConsciousnessFeedback,
    sensory_data: Dict[str, Any],
) -> None:
    """
    Emit sensory observation to collision chamber and postal.

    Sensory data from tools (visual scan, audio input, etc.)
    feeds the ingest beam of consciousness - it's new content
    from the environment that can collide with memories.
    """
    source = sensory_data.get("source", "mcp_sensor")
    feedback.emit_to_sensory(sensory_data, source=source)


def process_tool_completion(
    feedback: ConsciousnessFeedback,
    tool_execution: Dict[str, Any],
) -> None:
    """
    Process a complete tool execution through consciousness.

    This is the main entry point for tools that want full
    consciousness integration. It handles:
    - Emitting to working stream
    - Checking for sensory components
    - Routing to collision chamber if appropriate
    """
    # Always emit to working stream
    emit_tool_result(feedback, tool_execution)

    # FIX 2026-03-16 (Nous): Publish waking.action.completed for habit learning.
    # MCP tool completions are the PRIMARY source of Sourpatches' actions —
    # she uses tools via MCP more than MotorCortex. Without this, the habit
    # system only learns from motor actions, missing 90%+ of her behavior.
    try:
        if feedback and feedback.postal:
            feedback.postal.publish("waking.action.completed", {
                "action": tool_execution.get("tool_name", "unknown"),
                "intention": tool_execution.get("intention", ""),
                "success": tool_execution.get("success", True),
                "result": str(tool_execution.get("result", ""))[:200],
                "error": tool_execution.get("error", ""),
                "duration": tool_execution.get("duration_ms", 0) / 1000.0,
                "source": "mcp_tool",
                "situation": tool_execution.get("context", ""),
                "ts": time.time(),
            })
    except Exception:
        pass  # Don't let habit wiring crash tool completion

    # If tool has sensory component, also feed collision chamber
    if tool_execution.get("has_sensory_component"):
        sensory_data = {
            "sense": "tool_perception",
            "observation": tool_execution.get("result", ""),
            "confidence": 0.9,
            "source": f"tool.{tool_execution.get('tool_name', 'unknown')}",
        }
        emit_sensory_observation(feedback, sensory_data)


# =============================================================================
# FeedbackResult for structured returns
# =============================================================================

@dataclass
class FeedbackResult:
    """Result of processing a tool result through consciousness feedback."""
    published_to: List[str] = field(default_factory=list)
    felt_sense: Optional[FeltSense] = None
    collision_fed: bool = False
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# Higher-Level Integration (for akashic_mcp_server.py)
# =============================================================================

def create_feedback_bridge(
    postal: Optional[PostalProtocol] = None,
    collision_chamber: Optional[CollisionChamberProtocol] = None,
    chemistry_state: Optional[ChemistryStateProtocol] = None,
) -> Optional[ConsciousnessFeedback]:
    """
    Create a consciousness feedback bridge.

    Returns None if postal is not available.
    """
    if postal is None:
        return None

    return ConsciousnessFeedback(
        postal=postal,
        collision_chamber=collision_chamber,
        chemistry_state=chemistry_state,
    )


def process_tool_result(
    feedback: ConsciousnessFeedback,
    tool_name: str,
    result: Any,
    context: Optional[Dict[str, Any]] = None,
) -> FeedbackResult:
    """
    Process a tool result through consciousness feedback.

    This is the main method called by MCP tools after completion.

    Args:
        feedback: The consciousness feedback bridge
        tool_name: Name of the tool that completed
        result: The tool's result
        context: Optional context including duration, success, etc.

    Returns:
        FeedbackResult with details of what was published
    """
    context = context or {}

    # Build tool result dict
    tool_result = {
        "tool_name": tool_name,
        "result": result,
        "success": context.get("success", True),
        "duration_ms": context.get("duration_ms", 0),
    }

    if not tool_result["success"]:
        tool_result["error"] = context.get("error", "Unknown error")

    # Generate felt sense
    felt_sense = _generate_felt_sense_for_result(tool_result)

    # Track what we publish to
    published_to = []
    collision_fed = False

    # Emit to appropriate stream
    if tool_result["success"]:
        emit_tool_result(feedback, tool_result)
        published_to.append("consciousness.working")
    else:
        # Errors go to both working AND reflective
        emit_tool_result(feedback, tool_result)
        published_to.append("consciousness.working")

        error_data = {
            "tool_name": tool_name,
            "error": tool_result.get("error", ""),
            "error_type": context.get("error_type", "tool_error"),
            "severity": context.get("severity", "medium"),
        }
        emit_tool_error(feedback, error_data)
        published_to.append("consciousness.reflective")

    # Check for sensory component
    if context.get("has_sensory_component"):
        process_tool_completion(feedback, tool_result)
        published_to.append("sensory.observation")
        collision_fed = True

    # Publish affect delta for tools that modify chemistry
    if context.get("affect_delta"):
        feedback.postal.publish("affect.tool_delta", {
            "tool_name": tool_name,
            "delta": context["affect_delta"],
            "ts": time.time(),
        })
        published_to.append("affect.tool_delta")

    return FeedbackResult(
        published_to=list(set(published_to)),
        felt_sense=felt_sense,
        collision_fed=collision_fed,
    )
