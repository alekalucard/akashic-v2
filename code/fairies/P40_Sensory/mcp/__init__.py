# Akashic MCP Server - Lazy imports to avoid pulling pywin32/mcp during server boot.
# FIX 2026-03-12 Nous: Eager imports of akashic_mcp_server trigger mcp→pywin32 chain
# which segfaults on Python 3.14t (free-threaded). Use lazy loading so that only
# direct MCP server execution (not server.py boot) triggers the heavy imports.
import sys as _sys

_FREE_THREADED = hasattr(_sys, '_is_gil_enabled') and not _sys._is_gil_enabled()

# Only do eager imports for non-heavy modules (no C extension chains)
try:
    from .mcp_server_fairy import MCPServerFairy
except ImportError:
    MCPServerFairy = None

# Heavy imports (akashic_mcp_server→mcp→pywin32) are deferred
mcp = None
main = None

def _load_mcp_server():
    """Lazy-load the MCP server to avoid pywin32 segfault during server.py boot."""
    global mcp, main
    if mcp is None:
        from .akashic_mcp_server import mcp as _mcp, main as _main
        mcp = _mcp
        main = _main
    return mcp, main

# Consciousness-Native MCP Components — safe to import (no C extension deps)
try:
    from .consciousness_feedback import (
        ConsciousnessFeedback, FeedbackResult, FeltSense,
        create_feedback_bridge, process_tool_result,
    )
except ImportError:
    pass

try:
    from .consciousness_aware_tools import (
        ConsciousnessAwareToolSelector, get_consciousness_aware_tools,
        filter_tools_by_affect_state, rank_tools_by_working_memory,
        modulate_tool_confidence_by_chemistry, suggest_tools_for_affect,
    )
except ImportError:
    pass

try:
    from .thought_tool_tracer import (
        ToolTracer, ToolTracerContext, create_tool_tracer,
        complete_tracer, get_tracer_chain, get_tracers_for_thought,
    )
except ImportError:
    pass

try:
    from .affect_gated_tools import (
        AffectGate, GateResult, get_affect_gate,
        can_invoke_tool, gate_tool, suggest_stabilization,
    )
except ImportError:
    pass

try:
    from .collision_tool_explorer import (
        CollisionToolExplorer, ExplorationIntent, ExplorationGoal,
        create_collision_explorer,
    )
except ImportError:
    pass

try:
    from .inner_voice_synthesis import (
        tool_result_to_inner_voice, error_to_inner_voice,
        synthesize_inner_voice_with_affect, synthesize_complete_inner_voice,
        result_to_felt_complexity, result_to_emotional_weight,
        modulate_voice_by_chemistry,
    )
except ImportError:
    pass

try:
    from .consciousness_mcp_integration import (
        ConsciousnessMCPIntegration, ConsciousnessToolContext,
        ConsciousnessToolResult, ConsciousToolExecution,
        create_consciousness_mcp_integration, boot_consciousness_mcp,
        get_consciousness_mcp_integration, set_consciousness_mcp_integration,
    )
except ImportError:
    pass

__all__ = [
    # Core MCP (lazy-loaded)
    "_load_mcp_server",
    "MCPServerFairy",
    # Consciousness Feedback
    "ConsciousnessFeedback",
    "FeedbackResult",
    "FeltSense",
    "create_feedback_bridge",
    "process_tool_result",
    # Consciousness-Aware Tools
    "ConsciousnessAwareToolSelector",
    "get_consciousness_aware_tools",
    "filter_tools_by_affect_state",
    "rank_tools_by_working_memory",
    "modulate_tool_confidence_by_chemistry",
    "suggest_tools_for_affect",
    # Thought-Tool Tracer
    "ToolTracer",
    "ToolTracerContext",
    "create_tool_tracer",
    "complete_tracer",
    "get_tracer_chain",
    "get_tracers_for_thought",
    # Affect-Gated Tools
    "AffectGate",
    "GateResult",
    "get_affect_gate",
    "can_invoke_tool",
    "gate_tool",
    "suggest_stabilization",
    # Collision Tool Explorer
    "CollisionToolExplorer",
    "ExplorationIntent",
    "ExplorationGoal",
    "create_collision_explorer",
    # Inner Voice Synthesis
    "tool_result_to_inner_voice",
    "error_to_inner_voice",
    "synthesize_inner_voice_with_affect",
    "synthesize_complete_inner_voice",
    "result_to_felt_complexity",
    "result_to_emotional_weight",
    "modulate_voice_by_chemistry",
    # Consciousness MCP Integration
    "ConsciousnessMCPIntegration",
    "ConsciousnessToolContext",
    "ConsciousnessToolResult",
    "ConsciousToolExecution",
    "create_consciousness_mcp_integration",
    "boot_consciousness_mcp",
    "get_consciousness_mcp_integration",
    "set_consciousness_mcp_integration",
]
