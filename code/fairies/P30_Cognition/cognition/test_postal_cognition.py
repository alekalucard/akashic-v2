# test_postal_cognition.py
"""
Tests for Postal Cognition Bridge - TDD approach.

These tests verify that thinking requests route through postal
to HybridCognitionFairy instead of direct Ollama calls.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from unittest.mock import MagicMock, AsyncMock
from fairies.P30_Cognition.cognition.postal_cognition_bridge import (
    CognitionBridge,
    ThinkRequest,
    ThinkResponse,
    get_cognition_bridge,
)


def test_think_request_creation():
    """ThinkRequest should capture context for cognition."""
    req = ThinkRequest(
        stimulus="What should I explore?",
        chemistry={"dopamine": 0.7, "cortisol": 0.2},
        recent_thoughts=["I noticed something interesting"],
        pain_state={"curiosity": 0.8},
    )

    assert req.stimulus == "What should I explore?"
    assert req.chemistry["dopamine"] == 0.7
    assert len(req.recent_thoughts) == 1
    assert req.stimulus_type == "reflection"  # default
    assert req.source == "UMF"  # default
    assert req.priority == 0.5  # default


def test_think_request_to_dict():
    """ThinkRequest.to_dict() should serialize all fields."""
    req = ThinkRequest(
        stimulus="Test stimulus",
        stimulus_type="goal",
        chemistry={"dopamine": 0.5},
        somatic={"arousal": 0.3},
        recent_thoughts=["thought1", "thought2"],
        pain_state={"boredom": 0.6},
        helix_hint={"affect": "curiosity", "temporal": "recent"},
        source="TestFairy",
        priority=0.8,
    )

    d = req.to_dict()

    assert d["stimulus"] == "Test stimulus"
    assert d["stimulus_type"] == "goal"
    assert d["chemistry"] == {"dopamine": 0.5}
    assert d["somatic"] == {"arousal": 0.3}
    assert d["recent_thoughts"] == ["thought1", "thought2"]
    assert d["pain_state"] == {"boredom": 0.6}
    assert d["helix_hint"] == {"affect": "curiosity", "temporal": "recent"}
    assert d["source"] == "TestFairy"
    assert d["priority"] == 0.8


def test_think_response_creation():
    """ThinkResponse should capture cognition results."""
    response = ThinkResponse(
        thought="Exploring memory associations",
        reasoning="Based on high curiosity drive",
        actions=[{"type": "explore", "target": "memory"}],
        local_only=True,
        depth_score=0.8,
    )

    assert response.thought == "Exploring memory associations"
    assert response.local_only is True
    assert len(response.actions) == 1
    assert response.depth_score == 0.8
    assert response.error is None


def test_think_response_from_dict():
    """ThinkResponse.from_dict() should parse cognition response."""
    data = {
        "response": "I should explore the concept graph",
        "reasoning": "High curiosity detected",
        "actions": [{"type": "explore", "target": "graph"}],
        "local_only": False,
        "depth_score": 0.75,
        "associations": ["memory", "learning", "patterns"],
    }

    response = ThinkResponse.from_dict(data)

    assert response.thought == "I should explore the concept graph"
    assert response.reasoning == "High curiosity detected"
    assert len(response.actions) == 1
    assert response.local_only is False
    assert response.depth_score == 0.75
    assert len(response.associations) == 3


def test_think_response_from_dict_alternative_key():
    """ThinkResponse.from_dict() should handle 'thought' key too."""
    data = {
        "thought": "Alternative thought key",
        "local_only": True,
    }

    response = ThinkResponse.from_dict(data)

    assert response.thought == "Alternative thought key"


def test_think_response_from_dict_invalid_type():
    """ThinkResponse.from_dict() should handle non-dict input."""
    response = ThinkResponse.from_dict("not a dict")

    assert response.thought == ""
    assert response.error is not None
    assert "Invalid response type" in response.error


def test_think_response_from_dict_invalid_actions():
    """ThinkResponse.from_dict() should coerce invalid actions to empty list."""
    data = {
        "thought": "Test thought",
        "actions": "not a list",  # Invalid - should be list
        "associations": {"not": "list"},  # Invalid - should be list
    }

    response = ThinkResponse.from_dict(data)

    assert response.thought == "Test thought"
    assert response.actions == []
    assert response.associations == []


def test_think_response_from_dict_depth_score_coercion():
    """ThinkResponse.from_dict() should handle depth_score type coercion."""
    data = {
        "thought": "Test thought",
        "depth_score": "0.75",  # String instead of float
    }

    response = ThinkResponse.from_dict(data)

    assert response.depth_score == 0.75

    # Test invalid depth_score
    data_invalid = {
        "thought": "Test",
        "depth_score": "invalid",
    }

    response_invalid = ThinkResponse.from_dict(data_invalid)
    assert response_invalid.depth_score == 0.0


def test_bridge_configurable_timeout():
    """CognitionBridge should accept configurable timeout."""
    mock_fabric = MagicMock()

    bridge = CognitionBridge(mock_fabric, timeout=10.0)

    assert bridge._request_timeout == 10.0


def test_bridge_routes_to_postal():
    """CognitionBridge should route think requests through postal."""
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value={
        "response": "I should explore the concept graph",
        "local_only": True,
        "depth_score": 0.75,
    })

    bridge = CognitionBridge(mock_fabric)

    req = ThinkRequest(stimulus="What now?")
    response = bridge.think(req)

    mock_fabric.request.assert_called_once()
    call_args = mock_fabric.request.call_args
    assert call_args[0][0] == "cognition.think"  # Topic
    assert "stimulus" in call_args[0][1]  # Payload has stimulus

    # Check response was parsed
    assert response.thought == "I should explore the concept graph"
    assert response.local_only is True
    assert response.depth_score == 0.75


def test_bridge_handles_no_fabric():
    """CognitionBridge should raise ValueError when no fabric."""
    with pytest.raises(ValueError) as exc_info:
        CognitionBridge(None)

    assert "requires a valid TensorMemoryFabric" in str(exc_info.value)


def test_bridge_handles_no_response():
    """CognitionBridge should handle empty response from fabric."""
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value=None)

    bridge = CognitionBridge(mock_fabric)

    req = ThinkRequest(stimulus="Test")
    response = bridge.think(req)

    assert response.thought == ""
    assert response.error is not None
    assert "No response" in response.error


def test_bridge_handles_exception():
    """CognitionBridge should catch and report exceptions."""
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(side_effect=Exception("Connection failed"))

    bridge = CognitionBridge(mock_fabric)

    req = ThinkRequest(stimulus="Test")
    response = bridge.think(req)

    assert response.thought == ""
    assert response.error is not None
    assert "failed" in response.error


def test_spread_activation():
    """CognitionBridge.spread_activation should route to cortex."""
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value={
        "activations": {
            "explore": 0.9,
            "memory": 0.7,
            "learning": 0.5,
        }
    })

    bridge = CognitionBridge(mock_fabric)

    concepts = bridge.spread_activation("curiosity", max_hops=2)

    mock_fabric.request.assert_called_once()
    call_args = mock_fabric.request.call_args
    assert call_args[0][0] == "cortex.spread"
    assert call_args[0][1]["seed"] == "curiosity"
    assert call_args[0][1]["max_hops"] == 2

    # Results should be sorted by activation
    assert concepts[0] == "explore"  # highest activation
    assert len(concepts) == 3


def test_spread_activation_with_helix_hint():
    """spread_activation should pass helix_hint to cortex."""
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value={"activations": {"test": 0.5}})

    bridge = CognitionBridge(mock_fabric)

    helix_hint = {"affect": "curiosity", "temporal": "recent"}
    bridge.spread_activation("seed", helix_hint=helix_hint)

    call_args = mock_fabric.request.call_args
    assert call_args[0][1]["helix_hint"] == helix_hint


def test_spread_activation_no_fabric():
    """CognitionBridge should raise ValueError when no fabric."""
    with pytest.raises(ValueError) as exc_info:
        CognitionBridge(None)

    assert "requires a valid TensorMemoryFabric" in str(exc_info.value)


def test_suggest_goal():
    """CognitionBridge.suggest_goal should route to cognition.goal."""
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value={
        "goal": "explore_concept_graph"
    })

    bridge = CognitionBridge(mock_fabric)

    goal = bridge.suggest_goal(
        drive_name="curiosity",
        pain_state={"boredom": 0.7},
        chemistry={"dopamine": 0.3},
    )

    mock_fabric.request.assert_called_once()
    call_args = mock_fabric.request.call_args
    assert call_args[0][0] == "cognition.goal"
    assert call_args[0][1]["drive"] == "curiosity"
    assert call_args[0][1]["pain_state"] == {"boredom": 0.7}
    assert call_args[0][1]["chemistry"] == {"dopamine": 0.3}

    assert goal == "explore_concept_graph"


def test_suggest_goal_no_result():
    """suggest_goal should return None when no goal suggested."""
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value={})

    bridge = CognitionBridge(mock_fabric)

    goal = bridge.suggest_goal("test", {}, {})

    assert goal is None


def test_get_cognition_bridge_singleton():
    """get_cognition_bridge should return singleton."""
    # Reset singleton first
    import fairies.P30_Cognition.cognition.postal_cognition_bridge as module
    module._BRIDGE = None

    mock_fabric = MagicMock()

    bridge1 = get_cognition_bridge(mock_fabric)
    bridge2 = get_cognition_bridge()  # Should return same instance

    assert bridge1 is bridge2
    assert bridge1.fabric is mock_fabric


if __name__ == "__main__":
    print("Running postal cognition bridge tests...")

    test_think_request_creation()
    print("  [PASS] test_think_request_creation")

    test_think_request_to_dict()
    print("  [PASS] test_think_request_to_dict")

    test_think_response_creation()
    print("  [PASS] test_think_response_creation")

    test_think_response_from_dict()
    print("  [PASS] test_think_response_from_dict")

    test_think_response_from_dict_alternative_key()
    print("  [PASS] test_think_response_from_dict_alternative_key")

    test_think_response_from_dict_invalid_type()
    print("  [PASS] test_think_response_from_dict_invalid_type")

    test_think_response_from_dict_invalid_actions()
    print("  [PASS] test_think_response_from_dict_invalid_actions")

    test_think_response_from_dict_depth_score_coercion()
    print("  [PASS] test_think_response_from_dict_depth_score_coercion")

    test_bridge_configurable_timeout()
    print("  [PASS] test_bridge_configurable_timeout")

    test_bridge_routes_to_postal()
    print("  [PASS] test_bridge_routes_to_postal")

    test_bridge_handles_no_fabric()
    print("  [PASS] test_bridge_handles_no_fabric")

    test_bridge_handles_no_response()
    print("  [PASS] test_bridge_handles_no_response")

    test_bridge_handles_exception()
    print("  [PASS] test_bridge_handles_exception")

    test_spread_activation()
    print("  [PASS] test_spread_activation")

    test_spread_activation_with_helix_hint()
    print("  [PASS] test_spread_activation_with_helix_hint")

    test_spread_activation_no_fabric()
    print("  [PASS] test_spread_activation_no_fabric")

    test_suggest_goal()
    print("  [PASS] test_suggest_goal")

    test_suggest_goal_no_result()
    print("  [PASS] test_suggest_goal_no_result")

    test_get_cognition_bridge_singleton()
    print("  [PASS] test_get_cognition_bridge_singleton")

    print("\nAll tests passed!")
