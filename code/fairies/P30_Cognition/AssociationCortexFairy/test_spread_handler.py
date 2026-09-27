"""
Test suite for cortex.spread postal handler.

Tests:
1. _handle_spread returns activations from seed concept
2. Activations decay properly (seed > neighbors > distant)
3. helix_hint boosting works (same domain concepts get 1.3x)
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass
from typing import Any, Dict

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
    AssociationCortexFairy,
    ConceptGraph,
    _extract_payload,
)


@dataclass
class MockMessage:
    """Mock postal message envelope."""
    payload: Dict[str, Any]


def create_test_fairy_with_graph():
    """Create a fairy with a test graph, bypassing full boot."""
    fairy = AssociationCortexFairy(fabric=None)
    fairy._graph = ConceptGraph(max_nodes=1000, max_edges=5000)
    fairy._graph_loaded = True
    fairy._loading_complete = True
    return fairy


def create_test_graph():
    """
    Create a test concept graph with known structure:

    seed --0.8-- neighbor1 --0.6-- distant1
      |
     0.4
      |
    neighbor2
    """
    graph = ConceptGraph(max_nodes=1000, max_edges=5000)

    # Create nodes
    graph.upsert_node("seed", {"lex": ["test"]})
    graph.upsert_node("neighbor1", {"lex": ["close"]})
    graph.upsert_node("neighbor2", {"lex": ["also_close"]})
    graph.upsert_node("distant1", {"lex": ["far"]})

    # Create edges with varying weights
    graph.link("seed", "neighbor1", "coactivate", weight=0.8)
    graph.link("seed", "neighbor2", "coactivate", weight=0.4)
    graph.link("neighbor1", "distant1", "coactivate", weight=0.6)

    return graph


# =============================================================================
# TEST 1: Basic spread handler returns activations
# =============================================================================

def test_handle_spread_returns_activations():
    """_handle_spread should return activations dict from seed concept."""
    fairy = create_test_fairy_with_graph()
    fairy._graph = create_test_graph()

    # Create mock message
    message = MockMessage(payload={
        "seed": "seed",
        "max_hops": 2,
    })

    result = fairy._handle_spread(message)

    # Should succeed
    assert result.get("ok") is True, f"Expected ok=True, got {result}"
    assert "activations" in result, f"Expected activations in result, got {result}"
    assert result.get("seed") == "seed"
    assert result.get("hops") == 2

    # Should have activations for connected nodes
    activations = result["activations"]
    assert "seed" in activations, "Seed should be in activations"
    assert "neighbor1" in activations, "neighbor1 should be in activations"

    print(f"Activations: {activations}")
    print("PASSED: test_handle_spread_returns_activations")


# =============================================================================
# TEST 2: Activations decay with distance
# =============================================================================

def test_activations_decay_with_distance():
    """Activations should decay: seed > neighbors > distant nodes."""
    fairy = create_test_fairy_with_graph()
    fairy._graph = create_test_graph()

    message = MockMessage(payload={
        "seed": "seed",
        "max_hops": 3,
    })

    result = fairy._handle_spread(message)
    assert result.get("ok") is True

    activations = result["activations"]

    seed_act = activations.get("seed", 0)
    neighbor1_act = activations.get("neighbor1", 0)
    distant1_act = activations.get("distant1", 0)

    # Seed should have highest activation (1.0)
    assert seed_act > neighbor1_act, \
        f"Seed activation ({seed_act}) should be > neighbor1 ({neighbor1_act})"

    # Neighbors should have higher activation than distant
    assert neighbor1_act > distant1_act, \
        f"neighbor1 ({neighbor1_act}) should be > distant1 ({distant1_act})"

    print(f"Decay verified: seed={seed_act:.3f} > neighbor1={neighbor1_act:.3f} > distant1={distant1_act:.3f}")
    print("PASSED: test_activations_decay_with_distance")


# =============================================================================
# TEST 3: helix_hint boosting for same domain
# =============================================================================

def test_helix_hint_boosts_same_domain():
    """helix_hint with affect.domain should boost same-domain concepts by 1.3x."""
    fairy = create_test_fairy_with_graph()
    graph = ConceptGraph(max_nodes=1000, max_edges=5000)

    # Create nodes with affect domains
    graph.upsert_node("joy_seed", {"affect": {"domain": "JOY"}})
    graph.upsert_node("joy_neighbor", {"affect": {"domain": "JOY"}})  # Same domain
    graph.upsert_node("fear_neighbor", {"affect": {"domain": "FEAR"}})  # Different domain

    # Same edge weights to both neighbors
    graph.link("joy_seed", "joy_neighbor", "coactivate", weight=0.5)
    graph.link("joy_seed", "fear_neighbor", "coactivate", weight=0.5)

    fairy._graph = graph

    # First: spread WITHOUT helix_hint
    message_no_hint = MockMessage(payload={
        "seed": "joy_seed",
        "max_hops": 1,
    })
    result_no_hint = fairy._handle_spread(message_no_hint)
    assert result_no_hint.get("ok") is True

    act_no_hint = result_no_hint["activations"]
    joy_no_hint = act_no_hint.get("joy_neighbor", 0)
    fear_no_hint = act_no_hint.get("fear_neighbor", 0)

    # Without hint, both should have similar activation (same edge weight)
    print(f"Without hint: joy_neighbor={joy_no_hint:.4f}, fear_neighbor={fear_no_hint:.4f}")

    # Second: spread WITH helix_hint for JOY domain
    message_with_hint = MockMessage(payload={
        "seed": "joy_seed",
        "max_hops": 1,
        "helix_hint": {"affect": {"domain": "JOY"}},
    })
    result_with_hint = fairy._handle_spread(message_with_hint)
    assert result_with_hint.get("ok") is True

    act_with_hint = result_with_hint["activations"]
    joy_with_hint = act_with_hint.get("joy_neighbor", 0)
    fear_with_hint = act_with_hint.get("fear_neighbor", 0)

    print(f"With JOY hint: joy_neighbor={joy_with_hint:.4f}, fear_neighbor={fear_with_hint:.4f}")

    # With hint, JOY domain should be boosted ~1.3x relative to FEAR
    # Joy should now be higher than fear
    assert joy_with_hint > fear_with_hint, \
        f"JOY neighbor ({joy_with_hint}) should be > FEAR neighbor ({fear_with_hint}) with JOY hint"

    # The boost should be approximately 1.3x
    ratio = joy_with_hint / fear_with_hint if fear_with_hint > 0 else float('inf')
    assert 1.2 <= ratio <= 1.5, \
        f"Boost ratio should be ~1.3x, got {ratio:.2f}x"

    print(f"Boost ratio: {ratio:.2f}x (expected ~1.3x)")
    print("PASSED: test_helix_hint_boosts_same_domain")


# =============================================================================
# TEST 4: Error handling - no seed
# =============================================================================

def test_handle_spread_error_no_seed():
    """_handle_spread should return error if no seed provided."""
    fairy = create_test_fairy_with_graph()
    fairy._graph = create_test_graph()

    message = MockMessage(payload={
        "max_hops": 2,
        # No seed!
    })

    result = fairy._handle_spread(message)

    assert result.get("ok") is False, f"Expected ok=False for missing seed, got {result}"
    assert "error" in result, f"Expected error message, got {result}"

    print(f"Error result: {result}")
    print("PASSED: test_handle_spread_error_no_seed")


# =============================================================================
# TEST 5: Error handling - no graph
# =============================================================================

def test_handle_spread_error_no_graph():
    """_handle_spread should return error if no graph loaded."""
    fairy = AssociationCortexFairy(fabric=None)
    fairy._graph = None  # No graph!

    message = MockMessage(payload={
        "seed": "test",
        "max_hops": 2,
    })

    result = fairy._handle_spread(message)

    assert result.get("ok") is False, f"Expected ok=False for no graph, got {result}"
    assert "error" in result, f"Expected error message, got {result}"

    print(f"Error result: {result}")
    print("PASSED: test_handle_spread_error_no_graph")


# =============================================================================
# TEST 6: Default max_hops
# =============================================================================

def test_handle_spread_default_max_hops():
    """_handle_spread should default to max_hops=2 if not provided."""
    fairy = create_test_fairy_with_graph()
    fairy._graph = create_test_graph()

    message = MockMessage(payload={
        "seed": "seed",
        # No max_hops - should default to 2
    })

    result = fairy._handle_spread(message)

    assert result.get("ok") is True
    assert result.get("hops") == 2, f"Expected default hops=2, got {result.get('hops')}"

    print("PASSED: test_handle_spread_default_max_hops")


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Running cortex.spread handler tests")
    print("=" * 60)

    test_handle_spread_returns_activations()
    print()

    test_activations_decay_with_distance()
    print()

    test_helix_hint_boosts_same_domain()
    print()

    test_handle_spread_error_no_seed()
    print()

    test_handle_spread_error_no_graph()
    print()

    test_handle_spread_default_max_hops()
    print()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
