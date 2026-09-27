"""
Tests for consciousness_aware_tools.py - Consciousness-Native MCP Tool Selection

These tests verify that MCP tools are filtered, ranked, and suggested based on
the current consciousness state, including:
- Affect state (stress, arousal, valence)
- Working memory contents (recent thoughts/tracers)
- Neurochemistry levels (dopamine, cortisol, etc.)
- Emotional state

TDD: These tests are written FIRST - the implementation should make them pass.

Run: python -m pytest tests/mcp/test_consciousness_aware_tools.py -v
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_affect_state():
    """Create a mock affect state with configurable stress/arousal/valence."""
    return {
        "valence": 0.3,       # Slightly positive
        "arousal": 0.5,       # Medium arousal
        "stress": 0.2,        # Low stress
        "mood": "focused",
        "dominant_emotion": "curiosity",
        "dominant_intensity": 0.6,
    }


@pytest.fixture
def mock_high_stress_state():
    """Affect state with high stress."""
    return {
        "valence": -0.3,      # Negative
        "arousal": 0.8,       # High arousal
        "stress": 0.85,       # HIGH stress
        "mood": "anxious",
        "dominant_emotion": "anxiety",
        "dominant_intensity": 0.8,
    }


@pytest.fixture
def mock_working_memory():
    """Mock working memory with recent thoughts/tracers."""
    return {
        "recent_thoughts": [
            {
                "content": "Working on fixing the postal bridge connection issue",
                "tags": ["debugging", "postal", "networking"],
                "priority": 0.8,
                "timestamp": 1704067200,
            },
            {
                "content": "Need to understand the fairy registry architecture",
                "tags": ["architecture", "registry", "fairies"],
                "priority": 0.6,
                "timestamp": 1704067100,
            },
            {
                "content": "User asked about memory consolidation",
                "tags": ["memory", "user-request", "consolidation"],
                "priority": 0.7,
                "timestamp": 1704067000,
            },
        ],
        "active_goals": [
            "debug postal connection",
            "respond to user query",
        ],
        "context_keywords": ["postal", "debugging", "connection", "fairy", "registry"],
    }


@pytest.fixture
def mock_neurochemistry():
    """Mock neurochemistry levels."""
    return {
        "DOP": 0.6,   # Dopamine - moderate (engaged)
        "SER": 0.5,   # Serotonin - normal
        "NOR": 0.4,   # Norepinephrine - low
        "ACH": 0.7,   # Acetylcholine - high (focused)
        "OXY": 0.3,   # Oxytocin - low
        "COR": 0.2,   # Cortisol - low (not stressed)
        "GABA": 0.5,  # GABA - normal
        "END": 0.3,   # Endorphins - low
    }


@pytest.fixture
def mock_stressed_chemistry():
    """Neurochemistry for stressed state."""
    return {
        "DOP": 0.2,   # Dopamine - low
        "SER": 0.3,   # Serotonin - low
        "NOR": 0.8,   # Norepinephrine - HIGH (alert)
        "ACH": 0.4,   # Acetylcholine - impaired
        "OXY": 0.1,   # Oxytocin - very low
        "COR": 0.9,   # Cortisol - HIGH (stress)
        "GABA": 0.2,  # GABA - low (not calm)
        "END": 0.1,   # Endorphins - low
    }


@pytest.fixture
def sample_tools():
    """Sample tool definitions for testing."""
    return [
        {
            "name": "read_file",
            "description": "Read contents of a file",
            "risk_level": "low",
            "category": "file_ops",
            "keywords": ["read", "file", "content"],
        },
        {
            "name": "write_file",
            "description": "Write content to a file",
            "risk_level": "medium",
            "category": "file_ops",
            "keywords": ["write", "file", "modify", "create"],
        },
        {
            "name": "delete_file",
            "description": "Delete a file permanently",
            "risk_level": "high",
            "category": "file_ops",
            "keywords": ["delete", "remove", "destroy", "file"],
        },
        {
            "name": "explore_codebase",
            "description": "Explore and discover new code patterns",
            "risk_level": "low",
            "category": "exploration",
            "keywords": ["explore", "discover", "search", "code"],
        },
        {
            "name": "experiment_with_api",
            "description": "Try experimental API calls",
            "risk_level": "high",
            "category": "exploration",
            "keywords": ["experiment", "api", "try", "test"],
        },
        {
            "name": "postal_debug",
            "description": "Debug postal bridge connections",
            "risk_level": "low",
            "category": "debugging",
            "keywords": ["postal", "debug", "connection", "bridge"],
        },
        {
            "name": "fairy_registry_status",
            "description": "Check fairy registry status",
            "risk_level": "low",
            "category": "monitoring",
            "keywords": ["fairy", "registry", "status", "health"],
        },
        {
            "name": "memory_consolidation",
            "description": "Trigger memory consolidation process",
            "risk_level": "medium",
            "category": "memory",
            "keywords": ["memory", "consolidation", "store", "save"],
        },
        {
            "name": "inject_emotion",
            "description": "Inject an emotional response",
            "risk_level": "medium",
            "category": "somatic",
            "keywords": ["emotion", "inject", "feeling", "mood"],
        },
        {
            "name": "calm_response",
            "description": "Trigger calming somatic response",
            "risk_level": "low",
            "category": "somatic",
            "keywords": ["calm", "relax", "soothe", "peace"],
        },
    ]


# =============================================================================
# TEST 1: Filter Tools by Affect State
# =============================================================================

class TestFilterToolsByAffectState:
    """
    Test that tools are filtered based on current affect state.

    High stress should filter OUT:
    - High-risk tools (delete, experimental)
    - Exploratory tools (when we need focus)

    High stress should KEEP:
    - Low-risk tools
    - Calming/soothing tools
    - Essential debugging tools
    """

    def test_high_stress_filters_out_risky_tools(
        self, sample_tools, mock_high_stress_state
    ):
        """High stress should filter out high-risk tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            filter_tools_by_affect_state
        )

        filtered = filter_tools_by_affect_state(
            tools=sample_tools,
            affect_state=mock_high_stress_state
        )

        # High-risk tools should be filtered out under high stress
        tool_names = [t["name"] for t in filtered]

        assert "delete_file" not in tool_names, \
            "delete_file should be filtered under high stress"
        assert "experiment_with_api" not in tool_names, \
            "experimental tools should be filtered under high stress"

    def test_high_stress_keeps_calming_tools(
        self, sample_tools, mock_high_stress_state
    ):
        """High stress should keep calming/soothing tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            filter_tools_by_affect_state
        )

        filtered = filter_tools_by_affect_state(
            tools=sample_tools,
            affect_state=mock_high_stress_state
        )

        tool_names = [t["name"] for t in filtered]

        assert "calm_response" in tool_names, \
            "Calming tools should be available under high stress"

    def test_high_stress_filters_out_exploratory_tools(
        self, sample_tools, mock_high_stress_state
    ):
        """High stress should filter out exploratory tools (need focus)."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            filter_tools_by_affect_state
        )

        filtered = filter_tools_by_affect_state(
            tools=sample_tools,
            affect_state=mock_high_stress_state
        )

        tool_names = [t["name"] for t in filtered]

        # Exploration is risky under stress
        assert "explore_codebase" not in tool_names, \
            "Exploratory tools should be filtered under high stress"

    def test_low_stress_allows_all_tools(
        self, sample_tools, mock_affect_state
    ):
        """Low stress should allow all tools including risky ones."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            filter_tools_by_affect_state
        )

        filtered = filter_tools_by_affect_state(
            tools=sample_tools,
            affect_state=mock_affect_state  # Low stress state
        )

        # All tools should be available
        assert len(filtered) == len(sample_tools), \
            "All tools should be available under low stress"

    def test_filter_returns_tool_dicts(
        self, sample_tools, mock_affect_state
    ):
        """Filtered result should be list of tool dicts."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            filter_tools_by_affect_state
        )

        filtered = filter_tools_by_affect_state(
            tools=sample_tools,
            affect_state=mock_affect_state
        )

        assert isinstance(filtered, list)
        assert all(isinstance(t, dict) for t in filtered)
        assert all("name" in t for t in filtered)


# =============================================================================
# TEST 2: Rank Tools by Working Memory
# =============================================================================

class TestRankToolsByWorkingMemory:
    """
    Test that tools are ranked by relevance to working memory contents.

    Tools matching recent thoughts/goals should rank higher:
    - Keyword overlap with recent thoughts
    - Category matching active goals
    - Recency-weighted relevance
    """

    def test_rank_tools_by_recent_thought_relevance(
        self, sample_tools, mock_working_memory
    ):
        """Tools matching recent thought keywords should rank higher."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            rank_tools_by_working_memory
        )

        ranked = rank_tools_by_working_memory(
            tools=sample_tools,
            working_memory=mock_working_memory
        )

        # postal_debug should rank high (matches "postal bridge connection" thought)
        tool_names = [t["name"] for t in ranked]

        # Get position of postal_debug
        postal_idx = tool_names.index("postal_debug")

        # Should be in top 3 (high relevance to recent thoughts)
        assert postal_idx < 3, \
            f"postal_debug should rank in top 3, but was at position {postal_idx}"

    def test_rank_tools_by_active_goal_relevance(
        self, sample_tools, mock_working_memory
    ):
        """Tools matching active goals should rank higher."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            rank_tools_by_working_memory
        )

        ranked = rank_tools_by_working_memory(
            tools=sample_tools,
            working_memory=mock_working_memory
        )

        tool_names = [t["name"] for t in ranked]

        # Active goal is "debug postal connection"
        # postal_debug should be highly ranked
        postal_idx = tool_names.index("postal_debug")
        assert postal_idx < 3, \
            "Tools matching active goals should rank highly"

    def test_rank_includes_relevance_scores(
        self, sample_tools, mock_working_memory
    ):
        """Ranked tools should include relevance scores."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            rank_tools_by_working_memory
        )

        ranked = rank_tools_by_working_memory(
            tools=sample_tools,
            working_memory=mock_working_memory
        )

        # Each tool should have a relevance score
        assert all("relevance_score" in t for t in ranked), \
            "Ranked tools should include relevance_score"

        # Scores should be between 0 and 1
        scores = [t["relevance_score"] for t in ranked]
        assert all(0.0 <= s <= 1.0 for s in scores), \
            "Relevance scores should be between 0 and 1"

    def test_rank_is_descending(
        self, sample_tools, mock_working_memory
    ):
        """Tools should be ranked in descending order of relevance."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            rank_tools_by_working_memory
        )

        ranked = rank_tools_by_working_memory(
            tools=sample_tools,
            working_memory=mock_working_memory
        )

        scores = [t["relevance_score"] for t in ranked]

        # Should be sorted descending
        assert scores == sorted(scores, reverse=True), \
            "Tools should be ranked in descending order of relevance"

    def test_empty_working_memory_returns_original_order(
        self, sample_tools
    ):
        """Empty working memory should return tools in original order."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            rank_tools_by_working_memory
        )

        empty_memory = {
            "recent_thoughts": [],
            "active_goals": [],
            "context_keywords": [],
        }

        ranked = rank_tools_by_working_memory(
            tools=sample_tools,
            working_memory=empty_memory
        )

        # All should have same (neutral) relevance
        scores = [t["relevance_score"] for t in ranked]
        assert len(set(scores)) <= 2, \
            "Empty working memory should give equal relevance scores"


# =============================================================================
# TEST 3: Tool Confidence Modulated by Chemistry
# =============================================================================

class TestToolConfidenceModulatedByChemistry:
    """
    Test that tool confidence is modulated by neurochemistry.

    Different chemical states affect tool confidence:
    - High dopamine -> Higher confidence in reward-seeking tools
    - High cortisol -> Lower confidence in risky tools
    - High ACH -> Higher confidence in focused/precision tools
    - Low GABA -> Lower confidence in calm-requiring tools
    """

    def test_high_cortisol_reduces_risky_tool_confidence(
        self, sample_tools, mock_stressed_chemistry
    ):
        """High cortisol should reduce confidence in risky tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry
        )

        modulated = modulate_tool_confidence_by_chemistry(
            tools=sample_tools,
            chemistry=mock_stressed_chemistry
        )

        # Find high-risk tools
        risky_tools = [t for t in modulated if t["risk_level"] == "high"]

        for tool in risky_tools:
            assert tool["confidence_modifier"] < 1.0, \
                f"High cortisol should reduce confidence in {tool['name']}"

    def test_high_ach_increases_focus_tool_confidence(
        self, sample_tools, mock_neurochemistry
    ):
        """High acetylcholine should increase confidence in focused tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry
        )

        # High ACH (0.7) in mock_neurochemistry
        modulated = modulate_tool_confidence_by_chemistry(
            tools=sample_tools,
            chemistry=mock_neurochemistry
        )

        # Debugging tools require focus
        debug_tool = next(t for t in modulated if t["name"] == "postal_debug")

        assert debug_tool["confidence_modifier"] >= 1.0, \
            "High ACH should increase confidence in focus-requiring tools"

    def test_low_dopamine_reduces_exploration_confidence(
        self, sample_tools, mock_stressed_chemistry
    ):
        """Low dopamine should reduce confidence in exploratory tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry
        )

        # Low DOP (0.2) in mock_stressed_chemistry
        modulated = modulate_tool_confidence_by_chemistry(
            tools=sample_tools,
            chemistry=mock_stressed_chemistry
        )

        explore_tool = next(t for t in modulated if t["name"] == "explore_codebase")

        assert explore_tool["confidence_modifier"] < 1.0, \
            "Low dopamine should reduce confidence in exploratory tools"

    def test_confidence_modifiers_are_bounded(
        self, sample_tools, mock_neurochemistry
    ):
        """Confidence modifiers should be reasonably bounded."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry
        )

        modulated = modulate_tool_confidence_by_chemistry(
            tools=sample_tools,
            chemistry=mock_neurochemistry
        )

        for tool in modulated:
            assert "confidence_modifier" in tool, \
                f"Tool {tool['name']} missing confidence_modifier"
            # Should be bounded (0.1 to 2.0 is reasonable range)
            assert 0.1 <= tool["confidence_modifier"] <= 2.0, \
                f"confidence_modifier for {tool['name']} out of bounds"

    def test_balanced_chemistry_gives_neutral_confidence(
        self, sample_tools
    ):
        """Balanced neurochemistry should give ~1.0 confidence modifiers."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry
        )

        balanced = {
            "DOP": 0.5,
            "SER": 0.5,
            "NOR": 0.5,
            "ACH": 0.5,
            "OXY": 0.5,
            "COR": 0.5,
            "GABA": 0.5,
            "END": 0.5,
        }

        modulated = modulate_tool_confidence_by_chemistry(
            tools=sample_tools,
            chemistry=balanced
        )

        modifiers = [t["confidence_modifier"] for t in modulated]

        # Most should be close to 1.0
        avg_modifier = sum(modifiers) / len(modifiers)
        assert 0.9 <= avg_modifier <= 1.1, \
            "Balanced chemistry should give near-neutral confidence"


# =============================================================================
# TEST 4: Suggest Tools for Affect State
# =============================================================================

class TestSuggestToolsForAffect:
    """
    Test that appropriate tools are suggested based on emotional state.

    Different emotional states should suggest different tool categories:
    - Anxious/stressed -> Suggest calming, safe tools
    - Curious -> Suggest exploratory tools
    - Frustrated -> Suggest debugging, clarity tools
    - Focused -> Suggest precision, task-completion tools
    """

    def test_suggest_calming_tools_for_anxious_state(
        self, sample_tools, mock_high_stress_state
    ):
        """Anxious state should suggest calming tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            suggest_tools_for_affect
        )

        suggestions = suggest_tools_for_affect(
            tools=sample_tools,
            affect_state=mock_high_stress_state
        )

        suggested_names = [t["name"] for t in suggestions]

        assert "calm_response" in suggested_names, \
            "Should suggest calming tools for anxious state"

    def test_suggest_exploratory_tools_for_curious_state(
        self, sample_tools
    ):
        """Curious state should suggest exploratory tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            suggest_tools_for_affect
        )

        curious_state = {
            "valence": 0.6,
            "arousal": 0.6,
            "stress": 0.1,
            "mood": "curious",
            "dominant_emotion": "curiosity",
            "dominant_intensity": 0.8,
        }

        suggestions = suggest_tools_for_affect(
            tools=sample_tools,
            affect_state=curious_state
        )

        suggested_names = [t["name"] for t in suggestions]

        assert "explore_codebase" in suggested_names, \
            "Should suggest exploratory tools for curious state"

    def test_suggest_debugging_tools_for_frustrated_state(
        self, sample_tools
    ):
        """Frustrated state should suggest debugging/clarity tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            suggest_tools_for_affect
        )

        frustrated_state = {
            "valence": -0.4,
            "arousal": 0.7,
            "stress": 0.6,
            "mood": "frustrated",
            "dominant_emotion": "frustration",
            "dominant_intensity": 0.7,
        }

        suggestions = suggest_tools_for_affect(
            tools=sample_tools,
            affect_state=frustrated_state
        )

        # Should suggest debugging and monitoring tools
        categories = [t["category"] for t in suggestions]

        assert "debugging" in categories or "monitoring" in categories, \
            "Should suggest debugging/monitoring tools for frustrated state"

    def test_suggestions_include_reason(
        self, sample_tools, mock_affect_state
    ):
        """Suggestions should include reason for suggestion."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            suggest_tools_for_affect
        )

        suggestions = suggest_tools_for_affect(
            tools=sample_tools,
            affect_state=mock_affect_state
        )

        for suggestion in suggestions:
            assert "suggestion_reason" in suggestion, \
                f"Suggestion {suggestion['name']} missing suggestion_reason"
            assert isinstance(suggestion["suggestion_reason"], str), \
                "suggestion_reason should be a string"

    def test_suggestions_limited_to_reasonable_count(
        self, sample_tools, mock_affect_state
    ):
        """Suggestions should be limited to a reasonable count."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            suggest_tools_for_affect
        )

        suggestions = suggest_tools_for_affect(
            tools=sample_tools,
            affect_state=mock_affect_state
        )

        # Should suggest 3-5 tools max (not overwhelming)
        assert 1 <= len(suggestions) <= 5, \
            f"Should suggest 1-5 tools, got {len(suggestions)}"

    def test_suggest_different_tools_for_different_emotions(
        self, sample_tools
    ):
        """Different emotional states should suggest different tools."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            suggest_tools_for_affect
        )

        calm_state = {
            "valence": 0.5,
            "arousal": 0.2,
            "stress": 0.1,
            "mood": "peaceful",
            "dominant_emotion": "calm",
            "dominant_intensity": 0.8,
        }

        excited_state = {
            "valence": 0.8,
            "arousal": 0.9,
            "stress": 0.2,
            "mood": "excited",
            "dominant_emotion": "excitement",
            "dominant_intensity": 0.9,
        }

        calm_suggestions = suggest_tools_for_affect(
            tools=sample_tools,
            affect_state=calm_state
        )
        excited_suggestions = suggest_tools_for_affect(
            tools=sample_tools,
            affect_state=excited_state
        )

        calm_names = set(t["name"] for t in calm_suggestions)
        excited_names = set(t["name"] for t in excited_suggestions)

        # Should have at least some different suggestions
        assert calm_names != excited_names, \
            "Different emotional states should suggest at least some different tools"


# =============================================================================
# INTEGRATION TEST
# =============================================================================

class TestConsciousnessAwareToolSelection:
    """
    Integration test for full consciousness-aware tool selection pipeline.
    """

    def test_full_pipeline_filter_rank_suggest(
        self,
        sample_tools,
        mock_affect_state,
        mock_working_memory,
        mock_neurochemistry,
    ):
        """Test the full pipeline: filter -> rank -> confidence -> suggest."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            get_consciousness_aware_tools
        )

        result = get_consciousness_aware_tools(
            tools=sample_tools,
            affect_state=mock_affect_state,
            working_memory=mock_working_memory,
            chemistry=mock_neurochemistry,
        )

        # Should return a dict with available tools and suggestions
        assert "available_tools" in result
        assert "suggested_tools" in result
        assert "filtered_count" in result

        # Available tools should be ranked and have confidence modifiers
        for tool in result["available_tools"]:
            assert "relevance_score" in tool
            assert "confidence_modifier" in tool

        # Suggested tools should have reasons
        for tool in result["suggested_tools"]:
            assert "suggestion_reason" in tool

    def test_pipeline_under_high_stress(
        self,
        sample_tools,
        mock_high_stress_state,
        mock_working_memory,
        mock_stressed_chemistry,
    ):
        """Pipeline should be conservative under high stress."""
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            get_consciousness_aware_tools
        )

        result = get_consciousness_aware_tools(
            tools=sample_tools,
            affect_state=mock_high_stress_state,
            working_memory=mock_working_memory,
            chemistry=mock_stressed_chemistry,
        )

        # Should have filtered some tools
        assert result["filtered_count"] > 0, \
            "Should filter some tools under high stress"

        # Available tools should not include high-risk
        available_names = [t["name"] for t in result["available_tools"]]
        assert "delete_file" not in available_names

        # Suggestions should include calming tools
        suggested_names = [t["name"] for t in result["suggested_tools"]]
        assert any("calm" in name for name in suggested_names), \
            "Should suggest calming tools under high stress"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
