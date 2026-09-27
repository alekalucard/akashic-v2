# test_goal_generator_cortex.py
"""
Tests for DynamicGoalGenerator cortex integration.

Tests that the generator:
1. Uses cognition bridge when available
2. Falls back to normal behavior when bridge returns None
3. Accepts manual bridge wiring
4. Correctly looks up goal descriptions from EXPLORATORY_GOALS
"""

import pytest
from unittest.mock import Mock, patch
from typing import Optional, Dict


class TestGoalGeneratorCortexIntegration:
    """Test DynamicGoalGenerator integration with CognitionBridge."""

    def test_generator_uses_bridge_when_wired(self):
        """Generator should use bridge.suggest_goal when bridge is available."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        # Create generator and mock bridge
        generator = DynamicGoalGenerator()
        mock_bridge = Mock()
        mock_bridge.suggest_goal.return_value = "explore_screen"

        # Wire the bridge
        generator.wire_bridge(mock_bridge)

        # Generate goal with context
        context = {
            "pain_state": {"curiosity": 0.8},
            "chemistry": {"dopamine": 0.6},
        }
        result = generator.generate_goal("curiosity", context=context)

        # Should have used the bridge
        mock_bridge.suggest_goal.assert_called_once_with(
            "curiosity",
            {"curiosity": 0.8},
            {"dopamine": 0.6},
        )

        # Should return the suggested goal with description
        assert result is not None
        assert result[0] == "explore_screen"
        assert "screen" in result[1].lower() or "read" in result[1].lower()

    def test_generator_falls_back_when_bridge_returns_none(self):
        """Generator should fall back to normal behavior when bridge returns None."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        generator = DynamicGoalGenerator()
        mock_bridge = Mock()
        mock_bridge.suggest_goal.return_value = None  # Bridge returns nothing

        generator.wire_bridge(mock_bridge)

        # Generate goal
        result = generator.generate_goal("curiosity")

        # Should have tried the bridge
        mock_bridge.suggest_goal.assert_called_once()

        # Should still return a valid goal (from fallback behavior)
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_generator_works_without_bridge(self):
        """Generator should work normally when no bridge is wired."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        generator = DynamicGoalGenerator()
        # Don't wire any bridge

        # Should still generate goals
        result = generator.generate_goal("curiosity")

        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_wire_bridge_method(self):
        """wire_bridge should set the internal bridge reference."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        generator = DynamicGoalGenerator()
        mock_bridge = Mock()

        # Initially no bridge
        assert generator._cognition_bridge is None

        # Wire it
        generator.wire_bridge(mock_bridge)

        # Now should have bridge
        assert generator._cognition_bridge is mock_bridge

    def test_get_goal_description_finds_exploratory_goals(self):
        """_get_goal_description should find descriptions from EXPLORATORY_GOALS."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
            EXPLORATORY_GOALS,
        )

        generator = DynamicGoalGenerator()

        # Test finding a known goal
        desc = generator._get_goal_description("explore_screen", "curiosity")
        assert "screen" in desc.lower() or "look" in desc.lower()

        # Test finding from a different drive
        desc = generator._get_goal_description("greet_ace", "connection")
        assert "ace" in desc.lower() or "greeting" in desc.lower()

    def test_get_goal_description_fallback(self):
        """_get_goal_description should provide fallback for unknown goals."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        generator = DynamicGoalGenerator()

        # Unknown goal should get fallback description
        desc = generator._get_goal_description("totally_unknown_goal", "curiosity")
        assert "Pursue" in desc
        assert "totally_unknown_goal" in desc
        assert "curiosity" in desc

    def test_bridge_goal_gets_marked_used(self):
        """Goals from bridge should be marked as used for cooldown tracking."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        generator = DynamicGoalGenerator()
        mock_bridge = Mock()
        mock_bridge.suggest_goal.return_value = "explore_screen"

        generator.wire_bridge(mock_bridge)

        # Generate goal
        generator.generate_goal("curiosity")

        # Goal should now be on cooldown
        assert generator._is_on_cooldown("explore_screen")

    def test_try_wire_bridge_handles_import_failure(self):
        """_try_wire_bridge should handle import failures gracefully."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        # Patch the import to fail
        with patch.dict("sys.modules", {"fairies.P30_Cognition.cognition.postal_cognition_bridge": None}):
            generator = DynamicGoalGenerator()

        # Should still work, just without bridge
        assert generator._cognition_bridge is None

    def test_bridge_with_empty_context(self):
        """Bridge should handle missing context gracefully."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )

        generator = DynamicGoalGenerator()
        mock_bridge = Mock()
        mock_bridge.suggest_goal.return_value = "explore_screen"

        generator.wire_bridge(mock_bridge)

        # Generate goal without context
        result = generator.generate_goal("curiosity", context=None)

        # Should have called with empty dicts
        mock_bridge.suggest_goal.assert_called_once_with(
            "curiosity",
            {},  # empty pain_state
            {},  # empty chemistry
        )

        assert result is not None


class TestBridgeIntegrationWithRealBridge:
    """Tests using actual bridge class (mocked fabric)."""

    def test_with_real_bridge_class(self):
        """Test integration with actual CognitionBridge class."""
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
        )
        from fairies.P30_Cognition.cognition.postal_cognition_bridge import (
            CognitionBridge,
        )

        # Create mock fabric
        mock_fabric = Mock()
        mock_fabric.request.return_value = {"goal": "explore_tools"}

        # Create real bridge with mock fabric
        bridge = CognitionBridge(mock_fabric)

        # Wire to generator
        generator = DynamicGoalGenerator()
        generator.wire_bridge(bridge)

        # Generate goal
        result = generator.generate_goal(
            "curiosity",
            context={"pain_state": {"curiosity": 0.5}, "chemistry": {"dopamine": 0.3}},
        )

        # Should have called postal
        mock_fabric.request.assert_called()

        # Should return the goal
        assert result is not None
        assert result[0] == "explore_tools"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
