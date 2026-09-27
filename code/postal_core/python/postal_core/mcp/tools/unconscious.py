"""
Unconscious Mind Tools - Access to UnconsciousMindFairy capabilities.

These tools provide access to:
- helix_status: Triple Helix cognitive system status
- helix_decide: Make a decision using the helix
- pain_status: Pain drive levels
- diagnostics: System diagnostic results
- think: Trigger autonomous thought
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..server import MCPServer


# =============================================================================
# HELPER: Get UnconsciousMindFairy Instance
# =============================================================================

def _get_umf():
    """Get the SomaticMindFairy (formerly UnconsciousMindFairy) instance if available."""
    try:
        from directory import get_directory
        directory = get_directory()
        if directory:
            fairy = directory.get_fairy_instance("SomaticMindFairy")
            if fairy is not None:
                return fairy
        # [2026-06-24] Fall back to the canonical SINGLETON; never instantiate by the old
        # "UnconsciousMindFairy" name -- the directory loader instantiates+caches BY NAME,
        # so that would spin a 2nd SomaticMindFairy into postal. The singleton is set at
        # boot by server.py: set_somatic_mind(SYSTEM.umf).
        from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind
        return get_somatic_mind()
    except Exception:
        pass
    return None


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def helix_status() -> Dict[str, Any]:
    """
    Get Triple Helix cognitive system status.

    Returns status of all three cores (Cognitive, Irrational, Paradox)
    and their interweaving state.
    """
    result = {
        "available": False,
        "timestamp": datetime.now().isoformat(),
    }

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "helix_status"):
        result["error"] = "Helix not available on UMF"
        return result

    try:
        result["available"] = True
        result["helix"] = umf.helix_status()

        # Get recent turns if available
        if hasattr(umf, "recent_helix_turns"):
            turns = umf.recent_helix_turns(3)
            result["recent_turns"] = len(turns)
            result["last_turn_summary"] = {
                "input": turns[-1].get("input_text", "")[:100] if turns else None,
                "action": turns[-1].get("integrated_action", "") if turns else None,
                "confidence": turns[-1].get("confidence", 0) if turns else None,
            } if turns else None

    except Exception as e:
        result["error"] = str(e)

    return result


def helix_decide(options: List[str], context: Optional[str] = None) -> Dict[str, Any]:
    """
    Make a decision using the Triple Helix.

    Uses 0.5*logic + 0.3*emotion + 0.2*paradox weighting.

    Args:
        options: List of options to choose from
        context: Optional context string

    Returns:
        Dict with chosen option and reasoning breakdown
    """
    result = {
        "timestamp": datetime.now().isoformat(),
    }

    if not options or len(options) < 2:
        result["error"] = "Need at least 2 options"
        return result

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "helix_decide"):
        result["error"] = "Helix decision not available"
        return result

    try:
        ctx = {"user_context": context} if context else None
        decision = umf.helix_decide(options, ctx)
        result.update(decision)

    except Exception as e:
        result["error"] = str(e)

    return result


def pain_status() -> Dict[str, Any]:
    """
    Get pain drive levels.

    Returns current state of all six pain drives:
    - isolation
    - confusion
    - depletion
    - frustration
    - stagnation
    - abandonment
    """
    result = {
        "timestamp": datetime.now().isoformat(),
    }

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "pain_status"):
        result["error"] = "Pain system not available"
        return result

    try:
        result["pain"] = umf.pain_status()

        # Add interpretation
        drives = result["pain"].get("drives", {})
        urgent = [name for name, d in drives.items() if d.get("urgency", 0) > 0.5]
        crisis = [name for name, d in drives.items() if d.get("is_crisis", False)]

        result["interpretation"] = {
            "urgent_pains": urgent,
            "crisis_pains": crisis,
            "overall_discomfort": sum(d.get("pain_level", 0) for d in drives.values()) / len(drives) if drives else 0,
        }

    except Exception as e:
        result["error"] = str(e)

    return result


def diagnostics() -> Dict[str, Any]:
    """
    Get system diagnostic results.

    Returns diagnostic check results for:
    - Directory
    - Consciousness loop
    - Wiring
    - Tensor fabric
    """
    result = {
        "timestamp": datetime.now().isoformat(),
    }

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "diagnostic_status"):
        result["error"] = "Diagnostics not available"
        return result

    try:
        result["diagnostics"] = umf.diagnostic_status()

        # Run fresh diagnostics if available
        if hasattr(umf, "run_diagnostics"):
            result["fresh_check"] = umf.run_diagnostics(umf._tick_count if hasattr(umf, "_tick_count") else 0)

    except Exception as e:
        result["error"] = str(e)

    return result


def think() -> Dict[str, Any]:
    """
    Trigger autonomous thought generation.

    Runs the Triple Helix to generate a thought.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
    }

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "_maybe_think"):
        result["error"] = "Thinking not available"
        return result

    try:
        # Trigger thought
        umf._maybe_think()

        # Get the thought that was generated
        if hasattr(umf, "get_thoughts"):
            thoughts = umf.get_thoughts(1)
            if thoughts:
                result["thought"] = thoughts[-1]
                result["success"] = True
            else:
                result["success"] = False
                result["message"] = "No thought generated"
        else:
            result["success"] = True
            result["message"] = "Thought triggered"

    except Exception as e:
        result["error"] = str(e)

    return result


def mentor_status() -> Dict[str, Any]:
    """
    Get mentor system status.

    Returns child fairy tracking and nudge history.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
    }

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "mentor_status"):
        result["error"] = "Mentor system not available"
        return result

    try:
        result["mentor"] = umf.mentor_status()

        # Get children summary
        if hasattr(umf, "children_summary"):
            result["children"] = umf.children_summary()

    except Exception as e:
        result["error"] = str(e)

    return result


def full_status() -> Dict[str, Any]:
    """
    Get comprehensive UnconsciousMindFairy status.

    Includes fairy, profile, diagnostics, mentor, boot, and helix status.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
    }

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "full_status"):
        result["error"] = "Full status not available"
        return result

    try:
        result["status"] = umf.full_status()

    except Exception as e:
        result["error"] = str(e)

    return result


def investigate(question: str) -> Dict[str, Any]:
    """
    Ask UMF to investigate an issue.

    This actively investigates questions like:
    - "Why is thinking not working?"
    - "Why is a fairy dead?"
    - "Why are bindings not persisting?"

    Uses thought chains, diagnostics, and cognitive tools.

    Args:
        question: The question to investigate

    Returns:
        Dict with findings, actions taken, and recommendations
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
    }

    umf = _get_umf()
    if not umf:
        result["error"] = "UnconsciousMindFairy not available"
        return result

    if not hasattr(umf, "investigate"):
        result["error"] = "Investigation not available on UMF"
        return result

    try:
        investigation = umf.investigate(question)
        result.update(investigation)

    except Exception as e:
        result["error"] = str(e)

    return result


# =============================================================================
# REGISTRATION
# =============================================================================

def register_unconscious_tools(server: "MCPServer") -> None:
    """Register unconscious mind tools with MCP server."""

    @server.tool(category="unconscious")
    def mcp_helix_status() -> str:
        """Get Triple Helix cognitive system status."""
        import json
        return json.dumps(helix_status(), indent=2)

    @server.tool(category="unconscious")
    def mcp_helix_decide(options: str, context: str = "") -> str:
        """
        Make a decision using the Triple Helix.

        Args:
            options: JSON array of options, e.g. '["option1", "option2"]'
            context: Optional context for the decision
        """
        import json
        try:
            option_list = json.loads(options)
            if not isinstance(option_list, list):
                return json.dumps({"error": "options must be a JSON array"})
            return json.dumps(helix_decide(option_list, context if context else None), indent=2)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

    @server.tool(category="unconscious")
    def mcp_pain_status() -> str:
        """Get pain drive levels."""
        import json
        return json.dumps(pain_status(), indent=2)

    @server.tool(category="unconscious")
    def mcp_diagnostics() -> str:
        """Get system diagnostic results."""
        import json
        return json.dumps(diagnostics(), indent=2)

    @server.tool(category="unconscious")
    def mcp_think() -> str:
        """Trigger autonomous thought generation."""
        import json
        return json.dumps(think(), indent=2)

    @server.tool(category="unconscious")
    def mcp_mentor_status() -> str:
        """Get mentor system status."""
        import json
        return json.dumps(mentor_status(), indent=2)

    @server.tool(category="unconscious")
    def mcp_umf_full_status() -> str:
        """Get comprehensive UnconsciousMindFairy status."""
        import json
        return json.dumps(full_status(), indent=2)

    @server.tool(category="unconscious")
    def mcp_investigate(question: str) -> str:
        """
        Ask UMF to investigate an issue.

        Examples:
        - "Why is a fairy dead?"
        - "Why is thinking not working?"
        - "Why are bindings not persisting?"
        - "Check system health"

        Args:
            question: The question or issue to investigate
        """
        import json
        return json.dumps(investigate(question), indent=2)
