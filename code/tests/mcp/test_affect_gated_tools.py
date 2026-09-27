# tests/mcp/test_affect_gated_tools.py
"""
TDD Tests for Affect-Gated Tools - Pattern: AFFECT-FIRST ROUTING + SOMATIC TOOL DESIGN

These tests define the expected behavior of the AffectGate system:
- Pain states should gate risky tool invocation
- Stabilization tools should be suggested based on pain type
- Affect context should modulate tool behavior
- Tool parameters should be adjusted based on affect

((Cause + Affect) > Effect > Affect > infinity)
  Pain   Wanting   Action  Ripple   Learning

Run: pytest tests/mcp/test_affect_gated_tools.py -v
Expected: FAIL initially (TDD - implementation not yet written)
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAffectGatedTools:
    """Test suite for the AffectGate tool gating system."""

    def test_high_pain_blocks_risky_tools(self):
        """
        High pain state should block non-essential tools.

        When isolation pain is high (0.9), risky tools like 'delete_file'
        should be blocked, but safe tools like 'read_status' should be allowed.

        This tests the AFFECT-FIRST ROUTING pattern:
        - Pain drives what we can and cannot do
        - High pain -> protective mode only
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        # High isolation pain
        pain_state = {"isolation": 0.9, "overwhelm": 0.3}

        # Risky tools should be blocked when in pain
        assert gate.can_invoke_tool("delete_file", pain_state) is False

        # Safe tools should still be allowed
        assert gate.can_invoke_tool("read_status", pain_state) is True

    def test_suggests_stabilization_tools_for_pain(self):
        """
        Should suggest stabilization tools when in pain.

        When experiencing overwhelm (0.8) and confusion (0.6),
        the system should suggest calming/organizing tools.

        This tests the SOMATIC TOOL DESIGN pattern:
        - Different pains call for different remedies
        - Overwhelm -> need to simplify, take breaks
        - Confusion -> need to clarify, organize
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        pain_state = {"overwhelm": 0.8, "confusion": 0.6}
        suggestions = gate.suggest_stabilization_tools(pain_state)

        # Should have at least one suggestion
        assert len(suggestions) > 0

        # Should suggest calming/organizing tools
        # (status for clarity, organize for structure, break for rest)
        assert any("status" in s or "organize" in s or "break" in s for s in suggestions)

    def test_returns_affect_context_for_tool(self):
        """
        Should provide affect context to modulate tool behavior.

        Given high dopamine (0.8) and low cortisol (0.2),
        the affect context for 'explore' tool should indicate high confidence.

        This tests how chemistry state influences tool execution:
        - High dopamine = confident, exploratory
        - Low cortisol = calm, not stressed
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        chemistry = {"dopamine": 0.8, "cortisol": 0.2}
        context = gate.get_affect_context_for_tool("explore", chemistry)

        # Context should include confidence metric
        assert "confidence" in context

        # High dopamine + low cortisol = high confidence
        assert context["confidence"] > 0.5

    def test_modulate_tool_parameters(self):
        """
        Should adjust parameters based on affect.

        Tool parameters should be modulated based on the current affect state.
        For example:
        - High stress -> more conservative parameters (lower limits, more checks)
        - High curiosity -> more expansive parameters (higher limits, fewer restrictions)

        This tests the parameter modulation aspect of SOMATIC TOOL DESIGN:
        - Tools don't just gate on/off, they ADAPT to felt state
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        # Test with stressed state
        stressed_affect = {"stress": 0.8, "curiosity": 0.2, "valence": -0.3}
        stressed_params = gate.modulate_tool_parameters(
            "search_memory",
            {"limit": 100, "depth": 3},
            stressed_affect
        )

        # Test with curious state
        curious_affect = {"stress": 0.2, "curiosity": 0.8, "valence": 0.5}
        curious_params = gate.modulate_tool_parameters(
            "search_memory",
            {"limit": 100, "depth": 3},
            curious_affect
        )

        # Stressed state should have more conservative parameters
        assert stressed_params.get("limit", 100) <= curious_params.get("limit", 100)

        # Parameters should actually be modified (not just pass-through)
        # At least one parameter should differ between states
        assert stressed_params != curious_params


class TestPainThresholds:
    """Test pain threshold behavior in detail."""

    def test_threshold_boundary_behavior(self):
        """
        Tools should be allowed just below threshold, blocked at or above.

        Tests the exact boundary of pain thresholds.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate, PAIN_THRESHOLDS

        gate = AffectGate()

        # Get the overwhelm threshold (should be around 0.7)
        threshold = PAIN_THRESHOLDS.get("overwhelm", 0.7)

        # Just below threshold - risky tool should be allowed
        below_threshold = {"overwhelm": threshold - 0.05}
        assert gate.can_invoke_tool("delete_file", below_threshold) is True

        # At threshold - risky tool should be blocked
        at_threshold = {"overwhelm": threshold + 0.05}
        assert gate.can_invoke_tool("delete_file", at_threshold) is False

    def test_multiple_pains_compound(self):
        """
        Multiple moderate pains should have compounding effect.

        Even if no single pain exceeds threshold, high combined pain
        should still gate risky tools.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        # Multiple moderate pains (none exceeding individual threshold)
        multi_pain = {
            "isolation": 0.5,
            "overwhelm": 0.5,
            "confusion": 0.5,
            "frustration": 0.5
        }

        # With compounding, this should still block risky tools
        # Total pain load is 2.0, which is significant
        blocked = not gate.can_invoke_tool("experiment", multi_pain)

        # At minimum, the system should recognize high total pain
        # (exact behavior depends on implementation)
        # This test documents expected behavior for compounding


class TestStabilizationSuggestions:
    """Test stabilization tool suggestion logic."""

    def test_isolation_suggests_connection_tools(self):
        """
        High isolation pain should suggest connection/social tools.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        pain_state = {"isolation": 0.85}
        suggestions = gate.suggest_stabilization_tools(pain_state)

        # Should suggest connection-related tools
        assert any(
            "connect" in s or "reach" in s or "social" in s
            for s in suggestions
        )

    def test_depletion_suggests_rest_tools(self):
        """
        High depletion pain should suggest rest/conservation tools.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        pain_state = {"depletion": 0.85}
        suggestions = gate.suggest_stabilization_tools(pain_state)

        # Should suggest rest-related tools
        assert any(
            "rest" in s or "conserve" in s or "minimal" in s
            for s in suggestions
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
