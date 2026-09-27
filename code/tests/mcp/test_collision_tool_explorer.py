# tests/mcp/test_collision_tool_explorer.py
"""
TDD Tests for Collision Tool Explorer - Pattern: CONSCIOUSNESS COLLISION -> TOOL EXPLORATION

These tests define the expected behavior of the CollisionToolExplorer system:
- High-resonance collisions should suggest exploration tools
- Low-resonance collisions should have minimal tool suggestions
- Collisions should generate structured exploration intents
- Exploration should be gated by pain state
- Event handler should publish suggestions to postal

((Cause + Affect) > Effect > Affect > infinity)
  Collision   Resonance   Tools    Postal   Learning

The CollisionToolExplorer bridges consciousness collisions to tool discovery:
- When recall and ingest beams collide with high resonance, the collision
  products suggest avenues for exploration
- The explorer analyzes collision products and suggests relevant MCP tools
- Pain state gates whether exploration is safe (high pain = conservative)

Run: pytest tests/mcp/test_collision_tool_explorer.py -v
Expected: FAIL initially (TDD - implementation not yet written)
"""
import pytest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestHighResonanceCollisionSuggestsExploration:
    """Test that high-resonance collisions suggest exploration tools."""

    def test_high_resonance_collision_suggests_exploration(self):
        """
        High-resonance collisions should suggest exploration tools.

        When a collision has high resonance (>0.7), indicating strong
        alignment between recall and ingest beams, the system should
        suggest tools for exploring the collision products.

        This tests the core COLLISION -> EXPLORATION pattern:
        - High resonance = strong match between memory and new content
        - Strong match = worth exploring further
        - Explorer suggests relevant tools based on collision content
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        explorer = CollisionToolExplorer()

        # High-resonance collision (recall matched strongly with ingest)
        collision = {
            "collision_id": 1,
            "ts": time.time(),
            "energy": 0.85,
            "resonance": 0.9,  # High resonance - strong alignment
            "products": {
                "to_ingest": {
                    "type": "memory_recall",
                    "content": "Previous conversation about consciousness",
                    "topics": ["consciousness", "awareness", "cognition"],
                },
                "to_recall": {
                    "type": "new_thought",
                    "content": "How does consciousness emerge from collision?",
                    "topics": ["emergence", "consciousness", "collision"],
                },
            },
            "recall": {
                "source": "memory",
                "content": {"text": "consciousness discussion"},
            },
            "ingest": {
                "source": "thought",
                "content": {"text": "new awareness forming"},
            },
        }

        suggestions = explorer.suggest_exploration_tools(collision)

        # Should have at least one suggestion for high-resonance collision
        assert len(suggestions) > 0, "High-resonance collision should suggest exploration tools"

        # Suggestions should be tool names or tool specs
        assert all(isinstance(s, (str, dict)) for s in suggestions)

        # At least one suggestion should relate to memory/search/explore
        tool_names = [s if isinstance(s, str) else s.get("tool", "") for s in suggestions]
        assert any(
            "memory" in name.lower() or "search" in name.lower() or "explore" in name.lower()
            for name in tool_names
        ), "Should suggest memory/search/exploration tools for high-resonance collision"


class TestLowResonanceCollisionMinimalSuggestions:
    """Test that low-resonance collisions have minimal tool suggestions."""

    def test_low_resonance_collision_minimal_suggestions(self):
        """
        Low-resonance collisions should have minimal tool suggestions.

        When a collision has low resonance (<0.3), indicating weak
        alignment between recall and ingest beams, the system should
        suggest fewer or no exploration tools.

        This tests the resonance-gating pattern:
        - Low resonance = weak match between memory and new content
        - Weak match = less worth exploring
        - Explorer suggests minimal or conservative tools
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        explorer = CollisionToolExplorer()

        # Low-resonance collision (poor alignment)
        collision = {
            "collision_id": 2,
            "ts": time.time(),
            "energy": 0.4,
            "resonance": 0.2,  # Low resonance - weak alignment
            "products": {
                "to_ingest": {
                    "type": "memory_recall",
                    "content": "Random noise",
                },
                "to_recall": {
                    "type": "new_thought",
                    "content": "Unrelated tangent",
                },
            },
            "recall": {
                "source": "memory",
                "content": {"text": "noise"},
            },
            "ingest": {
                "source": "thought",
                "content": {"text": "tangent"},
            },
        }

        suggestions = explorer.suggest_exploration_tools(collision)

        # Should have fewer suggestions for low-resonance collision
        # (may be empty or very limited)
        assert len(suggestions) <= 1, "Low-resonance collision should have minimal suggestions"


class TestCollisionGeneratesExplorationIntent:
    """Test that collisions generate structured exploration intents."""

    def test_collision_generates_exploration_intent(self):
        """
        Collision should generate a structured exploration intent.

        The explorer should translate collision products into a
        structured intent that can be acted upon by the system.

        This tests the COLLISION -> INTENT pattern:
        - Collision products contain both recall and ingest data
        - Intent extracts actionable exploration goals
        - Intent includes suggested tools and parameters
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        explorer = CollisionToolExplorer()

        # Collision with rich products
        collision = {
            "collision_id": 3,
            "ts": time.time(),
            "energy": 0.75,
            "resonance": 0.8,
            "products": {
                "to_ingest": {
                    "type": "memory_recall",
                    "content": "Related memory about neural networks",
                    "topics": ["neural", "networks", "learning"],
                    "recall_id": "mem_12345",
                },
                "to_recall": {
                    "type": "new_thought",
                    "content": "How do thoughts form patterns?",
                    "topics": ["thought", "patterns", "emergence"],
                },
            },
            "recall": {
                "source": "memory",
                "content": {"text": "neural network memory"},
            },
            "ingest": {
                "source": "thought",
                "content": {"text": "pattern formation query"},
            },
        }

        intent = explorer.generate_exploration_intent(collision)

        # Intent should be a structured dict
        assert isinstance(intent, dict), "Intent should be a dictionary"

        # Intent should have required fields
        assert "collision_id" in intent, "Intent should reference collision"
        assert "exploration_goals" in intent, "Intent should have exploration goals"
        assert "suggested_tools" in intent, "Intent should suggest tools"

        # Exploration goals should be a list of strings or goal objects
        goals = intent["exploration_goals"]
        assert isinstance(goals, list), "Goals should be a list"
        assert len(goals) > 0, "High-resonance collision should generate goals"

        # Suggested tools should be a list
        tools = intent["suggested_tools"]
        assert isinstance(tools, list), "Tools should be a list"


class TestShouldExploreCollisionConsidersPain:
    """Test that exploration is gated by pain state."""

    def test_should_explore_collision_considers_pain(self):
        """
        Exploration should be gated by pain state.

        When pain is high, exploration should be blocked to conserve
        resources and protect the system. This is the affect-gating
        pattern applied to collision exploration.

        This tests the PAIN-GATED EXPLORATION pattern:
        - High pain = conserve resources, don't explore
        - Low pain = safe to explore collision products
        - Overwhelm and depletion particularly gate exploration
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        explorer = CollisionToolExplorer()

        # High-resonance collision that would normally trigger exploration
        collision = {
            "collision_id": 4,
            "ts": time.time(),
            "energy": 0.9,
            "resonance": 0.95,
            "products": {
                "to_ingest": {"type": "memory_recall", "content": "Important memory"},
                "to_recall": {"type": "new_thought", "content": "Critical insight"},
            },
        }

        # Test with high pain - should NOT explore
        high_pain_state = {
            "overwhelm": 0.85,  # High overwhelm pain
            "depletion": 0.7,   # Significant depletion
        }

        should_explore_high_pain = explorer.should_explore_collision(collision, high_pain_state)
        assert should_explore_high_pain is False, "Should not explore when pain is high"

        # Test with low pain - SHOULD explore
        low_pain_state = {
            "overwhelm": 0.2,  # Low overwhelm
            "depletion": 0.1,  # Low depletion
        }

        should_explore_low_pain = explorer.should_explore_collision(collision, low_pain_state)
        assert should_explore_low_pain is True, "Should explore when pain is low"

    def test_specific_pain_types_gate_exploration(self):
        """
        Specific pain types should gate exploration differently.

        - Overwhelm: Definitely blocks exploration (too much input)
        - Confusion: May block (need clarity first)
        - Frustration: May block (need progress first)
        - Isolation: Should NOT block (exploration may help)
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        explorer = CollisionToolExplorer()

        collision = {
            "collision_id": 5,
            "ts": time.time(),
            "energy": 0.8,
            "resonance": 0.8,
            "products": {
                "to_ingest": {"content": "test"},
                "to_recall": {"content": "test"},
            },
        }

        # High overwhelm alone should block
        overwhelm_pain = {"overwhelm": 0.9, "isolation": 0.0}
        assert explorer.should_explore_collision(collision, overwhelm_pain) is False

        # High isolation alone should NOT block (exploration helps connection)
        isolation_pain = {"isolation": 0.9, "overwhelm": 0.0}
        assert explorer.should_explore_collision(collision, isolation_pain) is True


class TestOnCollisionEventPublishesSuggestions:
    """Test that the collision event handler publishes to postal."""

    def test_on_collision_event_publishes_suggestions(self, mock_postal):
        """
        Handler should publish to postal when collision event received.

        The CollisionToolExplorer should have an event handler that:
        1. Receives collision events from the collision chamber
        2. Analyzes the collision
        3. Generates exploration suggestions
        4. Publishes suggestions to postal for other components

        This tests the EVENT -> ANALYSIS -> PUBLISH pattern:
        - Subscribe to consciousness.collision topic
        - Process collision event
        - Route suggestions to exploration topic
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        # Create explorer with postal
        explorer = CollisionToolExplorer(postal=mock_postal)

        # Wire up the event handler
        explorer.start()  # This should subscribe to collision events

        # Simulate collision event
        collision_event = {
            "type": "consciousness_collision",
            "collision_id": 6,
            "ts": time.time(),
            "energy": 0.85,
            "resonance": 0.88,
            "products": {
                "to_ingest": {
                    "type": "memory_recall",
                    "content": "Interesting memory about patterns",
                    "topics": ["patterns", "recognition"],
                },
                "to_recall": {
                    "type": "new_thought",
                    "content": "New insight about structure",
                    "topics": ["structure", "insight"],
                },
            },
            "recall": {"source": "memory", "content": {}},
            "ingest": {"source": "thought", "content": {}},
        }

        # Trigger the handler
        explorer.on_collision_event(collision_event)

        # Check that suggestions were published
        exploration_messages = mock_postal.get_messages_for_topic("exploration.suggestions")

        assert len(exploration_messages) > 0, "Should publish exploration suggestions to postal"

        # Verify message content
        msg = exploration_messages[0]["payload"]
        assert "collision_id" in msg, "Message should reference collision"
        assert "suggestions" in msg or "tools" in msg, "Message should contain suggestions"

    def test_handler_respects_pain_gating(self, mock_postal):
        """
        Handler should respect pain state when publishing suggestions.

        If pain is high, the handler should either:
        - Not publish suggestions at all
        - Publish with reduced/conservative suggestions
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        # Create explorer with postal and pain awareness
        explorer = CollisionToolExplorer(postal=mock_postal)

        # Set high pain state
        explorer.set_pain_state({"overwhelm": 0.9, "depletion": 0.8})

        # Simulate high-resonance collision
        collision_event = {
            "type": "consciousness_collision",
            "collision_id": 7,
            "ts": time.time(),
            "energy": 0.9,
            "resonance": 0.95,
            "products": {
                "to_ingest": {"content": "Important"},
                "to_recall": {"content": "Critical"},
            },
        }

        # Trigger handler
        explorer.on_collision_event(collision_event)

        # Should either not publish, or publish with minimal suggestions
        exploration_messages = mock_postal.get_messages_for_topic("exploration.suggestions")

        if len(exploration_messages) > 0:
            # If published, should be conservative
            msg = exploration_messages[0]["payload"]
            suggestions = msg.get("suggestions", msg.get("tools", []))
            assert len(suggestions) <= 1, "High pain should limit suggestions"


class TestExplorationToolPriority:
    """Test that exploration tools are prioritized appropriately."""

    def test_collision_content_influences_tool_priority(self):
        """
        Collision content should influence which tools are suggested first.

        If collision products contain memory-related content, memory tools
        should be prioritized. If they contain search terms, search tools
        should come first.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        explorer = CollisionToolExplorer()

        # Memory-focused collision
        memory_collision = {
            "collision_id": 8,
            "ts": time.time(),
            "energy": 0.8,
            "resonance": 0.85,
            "products": {
                "to_ingest": {
                    "type": "memory_recall",
                    "recall_id": "mem_54321",
                    "memory_type": "episodic",
                    "content": "Past experience with similar problem",
                },
                "to_recall": {
                    "type": "memory_query",
                    "content": "Find related memories",
                },
            },
        }

        memory_suggestions = explorer.suggest_exploration_tools(memory_collision)

        # First suggestion should be memory-related
        if len(memory_suggestions) > 0:
            first_tool = memory_suggestions[0]
            tool_name = first_tool if isinstance(first_tool, str) else first_tool.get("tool", "")
            assert "memory" in tool_name.lower() or "recall" in tool_name.lower(), \
                "Memory-focused collision should prioritize memory tools"

    def test_resonance_affects_exploration_depth(self):
        """
        Higher resonance should suggest deeper exploration tools.

        High resonance = strong match = worth deep exploration
        Medium resonance = moderate match = surface exploration
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import CollisionToolExplorer

        explorer = CollisionToolExplorer()

        # High resonance collision
        high_resonance = {
            "collision_id": 9,
            "ts": time.time(),
            "energy": 0.9,
            "resonance": 0.95,  # Very high
            "products": {
                "to_ingest": {"content": "Deep match"},
                "to_recall": {"content": "Strong alignment"},
            },
        }

        # Medium resonance collision
        medium_resonance = {
            "collision_id": 10,
            "ts": time.time(),
            "energy": 0.6,
            "resonance": 0.5,  # Medium
            "products": {
                "to_ingest": {"content": "Moderate match"},
                "to_recall": {"content": "Partial alignment"},
            },
        }

        high_intent = explorer.generate_exploration_intent(high_resonance)
        medium_intent = explorer.generate_exploration_intent(medium_resonance)

        # High resonance should suggest more tools or deeper exploration
        high_tools = high_intent.get("suggested_tools", [])
        medium_tools = medium_intent.get("suggested_tools", [])

        assert len(high_tools) >= len(medium_tools), \
            "Higher resonance should suggest at least as many tools"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
