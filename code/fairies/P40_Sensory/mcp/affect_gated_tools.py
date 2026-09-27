# affect_gated_tools.py - Affect-First Tool Gating System
# P40_Sensory/mcp/affect_gated_tools.py
#
# Implements the AFFECT-FIRST ROUTING pattern:
# - Pain states gate risky tool invocation
# - Chemistry modulates tool parameters
# - Stabilization tools suggested based on pain type
#
# ((Cause + Affect) > Effect > Affect > infinity)
#   Pain   Wanting   Action  Ripple   Learning
#
# The gate ensures tools are invoked appropriately given the current
# somatic state. High pain blocks risky operations; stabilization
# tools are suggested to help regulate before proceeding.

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# Pain Thresholds - Above these values, risky tools are blocked
# ============================================================================

PAIN_THRESHOLDS: Dict[str, float] = {
    "isolation": 0.7,
    "overwhelm": 0.7,
    "confusion": 0.75,
    "frustration": 0.7,
    "depletion": 0.7,
    "anxiety": 0.7,
}

# Combined pain threshold - if total pain load exceeds this, gate risky tools
COMBINED_PAIN_THRESHOLD: float = 1.8


# ============================================================================
# Tool Risk Classification
# ============================================================================

# Tools that are ALWAYS safe (read-only, status checks)
SAFE_TOOLS: set = {
    "read_status",
    "read_file",
    "get_status",
    "list_files",
    "search",
    "query",
    "check_health",
    "get_memory",
    "feel_body",
    "consciousness_status",
}

# Tools that are risky when in pain (destructive, experimental, high-impact)
RISKY_TOOLS: set = {
    "delete_file",
    "delete",
    "remove",
    "experiment",
    "modify_system",
    "write_critical",
    "restart",
    "shutdown",
    "force_commit",
    "drop_table",
}


# ============================================================================
# Stabilization Tool Mappings
# ============================================================================

# Maps pain type to suggested stabilization tools
STABILIZATION_TOOLS: Dict[str, List[str]] = {
    "isolation": [
        "reach_out_to_user",
        "connect_social",
        "request_collaboration",
        "social_check_in",
    ],
    "overwhelm": [
        "take_break",
        "status_summary",
        "simplify_task",
        "organize_thoughts",
        "reduce_scope",
    ],
    "confusion": [
        "status_check",
        "organize_context",
        "clarify_goal",
        "break_down_task",
    ],
    "frustration": [
        "take_break",
        "try_alternative",
        "request_help",
        "step_back",
    ],
    "depletion": [
        "rest_mode",
        "conserve_energy",
        "minimal_operation",
        "defer_task",
    ],
    "anxiety": [
        "grounding_check",
        "status_review",
        "safe_operation",
    ],
}


# ============================================================================
# GateResult - Outcome of a gating decision
# ============================================================================

@dataclass
class GateResult:
    """Result of a tool gating decision."""
    allowed: bool
    reason: str
    suggested_alternative: Optional[str] = None
    pain_levels: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "suggested_alternative": self.suggested_alternative,
            "pain_levels": self.pain_levels,
        }


# ============================================================================
# AffectGate - Main Gating System
# ============================================================================

class AffectGate:
    """
    Affect-First Tool Gating System.

    Gates tool invocation based on current pain/chemistry state.
    Implements the core insight that pain should drive what we can
    and cannot do - high pain means protective mode only.

    Usage:
        gate = AffectGate()

        # Check if tool can be invoked
        if gate.can_invoke_tool("delete_file", pain_state):
            # proceed with tool

        # Get suggestions when in pain
        suggestions = gate.suggest_stabilization_tools(pain_state)

        # Modulate parameters based on affect
        params = gate.modulate_tool_parameters("search", base_params, affect)
    """

    def __init__(
        self,
        pain_thresholds: Optional[Dict[str, float]] = None,
        safe_tools: Optional[set] = None,
        risky_tools: Optional[set] = None,
    ):
        """
        Initialize the AffectGate.

        Args:
            pain_thresholds: Custom pain thresholds (uses defaults if None)
            safe_tools: Custom set of safe tools (uses defaults if None)
            risky_tools: Custom set of risky tools (uses defaults if None)
        """
        self.pain_thresholds = pain_thresholds or dict(PAIN_THRESHOLDS)
        self.safe_tools = safe_tools or set(SAFE_TOOLS)
        self.risky_tools = risky_tools or set(RISKY_TOOLS)
        self._override_active = False
        self._override_reason: Optional[str] = None

    # ════════════════════════════════════════════════════════════════════════
    # Core Gating API
    # ════════════════════════════════════════════════════════════════════════

    def can_invoke_tool(self, tool_name: str, pain_state: Dict[str, float]) -> bool:
        """
        Check if a tool can be invoked given the current pain state.

        Args:
            tool_name: Name of the tool to check
            pain_state: Dict of pain type -> level (0.0-1.0)

        Returns:
            True if tool can be invoked, False if blocked by pain
        """
        result = self.gate_tool(tool_name, pain_state)
        return result.allowed

    def gate_tool(self, tool_name: str, pain_state: Dict[str, float]) -> GateResult:
        """
        Full gating decision with reason and suggestions.

        Args:
            tool_name: Name of the tool to gate
            pain_state: Dict of pain type -> level (0.0-1.0)

        Returns:
            GateResult with allowed status, reason, and suggestions
        """
        # Override bypasses all checks
        if self._override_active:
            return GateResult(
                allowed=True,
                reason=f"Override active: {self._override_reason}",
                pain_levels=pain_state,
            )

        # Safe tools are always allowed
        if self._is_safe_tool(tool_name):
            return GateResult(
                allowed=True,
                reason="Tool is classified as safe",
                pain_levels=pain_state,
            )

        # Check if tool is risky
        is_risky = self._is_risky_tool(tool_name)

        if not is_risky:
            # Unknown tools default to allowed if pain is not extreme
            total_pain = sum(pain_state.values())
            if total_pain < COMBINED_PAIN_THRESHOLD * 1.5:
                return GateResult(
                    allowed=True,
                    reason="Tool not classified as risky",
                    pain_levels=pain_state,
                )

        # Check individual pain thresholds
        for pain_type, level in pain_state.items():
            threshold = self.pain_thresholds.get(pain_type, 0.7)
            if level >= threshold:
                suggestions = self.suggest_stabilization_tools({pain_type: level})
                return GateResult(
                    allowed=False,
                    reason=f"Pain '{pain_type}' at {level:.2f} exceeds threshold {threshold:.2f}",
                    suggested_alternative=suggestions[0] if suggestions else None,
                    pain_levels=pain_state,
                )

        # Check combined pain threshold
        total_pain = sum(pain_state.values())
        if total_pain >= COMBINED_PAIN_THRESHOLD:
            suggestions = self.suggest_stabilization_tools(pain_state)
            return GateResult(
                allowed=False,
                reason=f"Combined pain load {total_pain:.2f} exceeds threshold {COMBINED_PAIN_THRESHOLD}",
                suggested_alternative=suggestions[0] if suggestions else None,
                pain_levels=pain_state,
            )

        # All checks passed
        return GateResult(
            allowed=True,
            reason="Pain levels within acceptable range",
            pain_levels=pain_state,
        )

    # ════════════════════════════════════════════════════════════════════════
    # Stabilization Suggestions
    # ════════════════════════════════════════════════════════════════════════

    def suggest_stabilization_tools(self, pain_state: Dict[str, float]) -> List[str]:
        """
        Suggest stabilization tools based on current pain state.

        Different pains call for different remedies:
        - Overwhelm -> need to simplify, take breaks
        - Confusion -> need to clarify, organize
        - Isolation -> need to connect, reach out
        - Depletion -> need to rest, conserve

        Args:
            pain_state: Dict of pain type -> level (0.0-1.0)

        Returns:
            List of suggested tool names, prioritized by pain level
        """
        suggestions: List[str] = []

        # Sort pains by level (highest first)
        sorted_pains = sorted(
            pain_state.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Collect suggestions from highest pain types
        for pain_type, level in sorted_pains:
            if level > 0.3:  # Only suggest for meaningful pain
                tools = STABILIZATION_TOOLS.get(pain_type, [])
                for tool in tools:
                    if tool not in suggestions:
                        suggestions.append(tool)

        return suggestions

    # ════════════════════════════════════════════════════════════════════════
    # Affect Context for Tool Modulation
    # ════════════════════════════════════════════════════════════════════════

    def get_affect_context_for_tool(
        self,
        tool_name: str,
        chemistry: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Get affect context to modulate tool behavior.

        Converts chemistry state into actionable context:
        - High dopamine + low cortisol = high confidence
        - High cortisol = caution mode
        - High serotonin = patience

        Args:
            tool_name: Name of the tool being invoked
            chemistry: Dict of chemical levels (dopamine, cortisol, etc.)

        Returns:
            Dict with affect-derived context (confidence, patience, caution, etc.)
        """
        # Extract key chemistry levels with defaults
        dopamine = chemistry.get("dopamine", 0.5)
        cortisol = chemistry.get("cortisol", 0.3)
        serotonin = chemistry.get("serotonin", 0.5)
        norepinephrine = chemistry.get("norepinephrine", 0.4)

        # Calculate derived metrics

        # Confidence: high dopamine + low cortisol
        confidence = (dopamine * 0.6) + ((1.0 - cortisol) * 0.4)
        confidence = max(0.0, min(1.0, confidence))

        # Caution: high cortisol, low dopamine
        caution = (cortisol * 0.6) + ((1.0 - dopamine) * 0.4)
        caution = max(0.0, min(1.0, caution))

        # Patience: high serotonin, low norepinephrine
        patience = (serotonin * 0.6) + ((1.0 - norepinephrine) * 0.4)
        patience = max(0.0, min(1.0, patience))

        # Focus: high norepinephrine
        focus = norepinephrine

        # Exploratory: high dopamine, low cortisol
        exploratory = dopamine * (1.0 - cortisol * 0.5)
        exploratory = max(0.0, min(1.0, exploratory))

        return {
            "tool": tool_name,
            "confidence": round(confidence, 3),
            "caution": round(caution, 3),
            "patience": round(patience, 3),
            "focus": round(focus, 3),
            "exploratory": round(exploratory, 3),
            "raw_chemistry": chemistry,
        }

    # ════════════════════════════════════════════════════════════════════════
    # Parameter Modulation
    # ════════════════════════════════════════════════════════════════════════

    def modulate_tool_parameters(
        self,
        tool_name: str,
        base_params: Dict[str, Any],
        affect: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Adjust tool parameters based on affect state.

        Tools don't just gate on/off - they ADAPT to felt state:
        - High stress -> more conservative parameters
        - High curiosity -> more expansive parameters
        - Negative valence -> safer defaults

        Args:
            tool_name: Name of the tool
            base_params: Original parameters
            affect: Affect state (stress, curiosity, valence, etc.)

        Returns:
            Modulated parameters
        """
        # Copy base params
        params = dict(base_params)

        # Extract affect dimensions
        stress = affect.get("stress", 0.5)
        curiosity = affect.get("curiosity", 0.5)
        valence = affect.get("valence", 0.0)  # -1 to +1

        # Calculate modulation factor
        # Stress reduces, curiosity expands, negative valence reduces
        expansion_factor = (
            (1.0 - stress) * 0.4 +
            curiosity * 0.4 +
            (valence + 1.0) / 2.0 * 0.2  # Normalize valence to 0-1
        )
        expansion_factor = max(0.3, min(1.5, expansion_factor))

        # Modulate numeric parameters
        for key, value in base_params.items():
            if isinstance(value, (int, float)):
                if key in ("limit", "max_results", "count", "depth", "iterations"):
                    # These scale with expansion factor
                    new_value = value * expansion_factor
                    if isinstance(value, int):
                        params[key] = max(1, int(round(new_value)))
                    else:
                        params[key] = round(new_value, 2)
                elif key in ("timeout", "wait"):
                    # Stress increases timeouts (more patience needed)
                    if stress > 0.5:
                        params[key] = value * (1 + stress * 0.5)

        # Add affect metadata
        params["_affect_modulated"] = True
        params["_expansion_factor"] = round(expansion_factor, 3)

        return params

    # ════════════════════════════════════════════════════════════════════════
    # Override Mechanism
    # ════════════════════════════════════════════════════════════════════════

    def enable_override(self, reason: str) -> None:
        """
        Enable override to bypass pain gating.

        Use sparingly for critical operations that MUST proceed.

        Args:
            reason: Why the override is needed (logged)
        """
        self._override_active = True
        self._override_reason = reason
        self._log_gating_event("override_enabled", {"reason": reason})

    def disable_override(self) -> None:
        """Disable override, returning to normal gating."""
        self._override_active = False
        self._override_reason = None
        self._log_gating_event("override_disabled", {})

    # ════════════════════════════════════════════════════════════════════════
    # Internal Helpers
    # ════════════════════════════════════════════════════════════════════════

    def _is_safe_tool(self, tool_name: str) -> bool:
        """Check if tool is classified as safe."""
        # Exact match
        if tool_name in self.safe_tools:
            return True
        # Prefix match for common safe patterns
        safe_prefixes = ("read_", "get_", "list_", "check_", "query_", "search_")
        return tool_name.startswith(safe_prefixes)

    def _is_risky_tool(self, tool_name: str) -> bool:
        """Check if tool is classified as risky."""
        # Exact match
        if tool_name in self.risky_tools:
            return True
        # Prefix match for risky patterns
        risky_prefixes = ("delete_", "remove_", "drop_", "force_", "destroy_")
        return tool_name.startswith(risky_prefixes)

    def _log_gating_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log gating event to postal if available."""
        try:
            from mcp_postal_helper import get_postal
            postal = get_postal()
            if postal:
                postal.emit("affect.tool_gated", {
                    "event": event_type,
                    **data,
                })
        except Exception:
            pass  # Postal not available, skip logging


# ============================================================================
# Singleton Instance
# ============================================================================

_AFFECT_GATE: Optional[AffectGate] = None


def get_affect_gate() -> AffectGate:
    """Get the global AffectGate singleton."""
    global _AFFECT_GATE
    if _AFFECT_GATE is None:
        _AFFECT_GATE = AffectGate()
    return _AFFECT_GATE


# ============================================================================
# Convenience Functions
# ============================================================================

def can_invoke_tool(tool_name: str, pain_state: Dict[str, float]) -> bool:
    """Convenience function to check if tool can be invoked."""
    return get_affect_gate().can_invoke_tool(tool_name, pain_state)


def gate_tool(tool_name: str, pain_state: Dict[str, float]) -> GateResult:
    """Convenience function for full gating decision."""
    return get_affect_gate().gate_tool(tool_name, pain_state)


def suggest_stabilization(pain_state: Dict[str, float]) -> List[str]:
    """Convenience function for stabilization suggestions."""
    return get_affect_gate().suggest_stabilization_tools(pain_state)


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    # Quick self-test
    gate = AffectGate()

    print("=== AffectGate Self-Test ===\n")

    # Test 1: High pain blocks risky tools
    pain = {"isolation": 0.9}
    result = gate.gate_tool("delete_file", pain)
    print(f"High isolation + delete_file: allowed={result.allowed}")
    print(f"  Reason: {result.reason}")
    print(f"  Suggestion: {result.suggested_alternative}\n")

    # Test 2: Safe tools always allowed
    result = gate.gate_tool("read_status", pain)
    print(f"High isolation + read_status: allowed={result.allowed}")
    print(f"  Reason: {result.reason}\n")

    # Test 3: Stabilization suggestions
    pain = {"overwhelm": 0.8, "confusion": 0.6}
    suggestions = gate.suggest_stabilization_tools(pain)
    print(f"Overwhelm + confusion suggestions: {suggestions[:3]}\n")

    # Test 4: Affect context
    chemistry = {"dopamine": 0.8, "cortisol": 0.2}
    context = gate.get_affect_context_for_tool("explore", chemistry)
    print(f"High dopamine, low cortisol context:")
    print(f"  confidence={context['confidence']}")
    print(f"  exploratory={context['exploratory']}\n")

    # Test 5: Parameter modulation
    stressed = {"stress": 0.8, "curiosity": 0.2, "valence": -0.3}
    curious = {"stress": 0.2, "curiosity": 0.8, "valence": 0.5}

    base = {"limit": 100, "depth": 3}
    stressed_params = gate.modulate_tool_parameters("search", base, stressed)
    curious_params = gate.modulate_tool_parameters("search", base, curious)

    print(f"Base params: {base}")
    print(f"Stressed params: limit={stressed_params['limit']}, depth={stressed_params['depth']}")
    print(f"Curious params: limit={curious_params['limit']}, depth={curious_params['depth']}")
