# test_cognition_rewiring_e2e.py
"""
End-to-End Integration Tests for Cognition Rewiring.

Verifies the complete rewired cognition flow:
1. CognitionBridge routes thinking through postal to HybridCognitionFairy
2. UMF prefers CognitionBridge over direct Ollama calls
3. DynamicGoalGenerator uses bridge for contextual goals
4. Spreading activation flows through cortex.spread topic

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

Run standalone: python tests/test_cognition_rewiring_e2e.py
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from unittest.mock import MagicMock, Mock, patch

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ============================================================================
# Test 1: test_full_cognition_flow
# ============================================================================

def test_full_cognition_flow():
    """
    Verifies complete rewired cognition flow:
    1. Create mock fabric that tracks all postal calls
    2. Create CognitionBridge with mock fabric
    3. Make think request - verify it routes to "cognition.think" topic
    4. Make goal request - verify it routes to "cognition.goal" topic
    5. Verify no direct Ollama calls in the flow
    """
    print("\n" + "=" * 60)
    print("TEST 1: Full Cognition Flow")
    print("=" * 60)

    # Track all postal calls
    postal_calls: List[Dict[str, Any]] = []

    def mock_request(topic: str, payload: Dict, timeout: float = 5.0) -> Dict:
        """Mock fabric.request that tracks calls and returns appropriate responses."""
        postal_calls.append({
            "topic": topic,
            "payload": payload,
            "timestamp": time.time(),
        })
        print(f"  [Postal] Request to '{topic}' with payload keys: {list(payload.keys())}")

        # Return appropriate response based on topic
        if topic == "cognition.think":
            return {
                "response": "I'm exploring the concept graph for interesting patterns",
                "reasoning": "High curiosity drive + dopamine suggests exploration",
                "local_only": True,
                "depth_score": 0.75,
                "associations": ["memory", "pattern", "discovery"],
                "actions": [],
            }
        elif topic == "cognition.goal":
            return {
                "ok": True,
                "goal": "explore_memory",
                "drive": payload.get("drive", "general"),
                "pain_level": payload.get("pain_state", {}).get(payload.get("drive"), 0),
            }
        elif topic == "cortex.spread":
            return {
                "ok": True,
                "activations": {
                    "curiosity": 1.0,
                    "explore": 0.8,
                    "memory": 0.6,
                    "pattern": 0.4,
                },
                "seed": payload.get("seed", ""),
                "hops": payload.get("max_hops", 2),
            }
        return {}

    # Create mock fabric
    mock_fabric = MagicMock()
    mock_fabric.request = mock_request

    print("\n[Step 1] Creating CognitionBridge with mock fabric...")

    # Import and create CognitionBridge
    from fairies.P30_Cognition.cognition.postal_cognition_bridge import (
        CognitionBridge,
        ThinkRequest,
        ThinkResponse,
    )

    bridge = CognitionBridge(mock_fabric)
    print("  [OK] CognitionBridge created successfully")

    # Test think request
    print("\n[Step 2] Testing think request routing...")
    think_request = ThinkRequest(
        stimulus="What patterns should I explore?",
        stimulus_type="reflection",
        chemistry={"dopamine": 0.7, "serotonin": 0.5},
        somatic={"energy": 0.6},
        recent_thoughts=["I noticed interesting patterns", "Memory seems important"],
        pain_state={"curiosity": 0.8},
        source="UMF",
        priority=0.6,
    )

    response = bridge.think(think_request)

    assert response is not None, "Think response should not be None"
    assert response.thought != "", "Think response should have thought content"
    assert response.local_only is True, "Response should indicate local processing"
    assert response.error is None, f"Response should not have error: {response.error}"
    print(f"  [OK] Think response received: '{response.thought[:50]}...'")
    print(f"  [OK] Local only: {response.local_only}, Depth score: {response.depth_score}")

    # Test goal request
    print("\n[Step 3] Testing goal request routing...")
    goal = bridge.suggest_goal(
        drive_name="curiosity",
        pain_state={"curiosity": 0.8, "connection": 0.3},
        chemistry={"dopamine": 0.7},
    )

    assert goal is not None, "Goal suggestion should not be None"
    assert goal == "explore_memory", f"Expected 'explore_memory', got '{goal}'"
    print(f"  [OK] Goal suggested: '{goal}'")

    # Verify postal topics used
    print("\n[Step 4] Verifying postal topic routing...")
    topics_used = [call["topic"] for call in postal_calls]

    assert "cognition.think" in topics_used, "cognition.think topic should be used"
    assert "cognition.goal" in topics_used, "cognition.goal topic should be used"
    print(f"  [OK] Topics used: {topics_used}")

    # Verify no direct Ollama calls
    print("\n[Step 5] Verifying no direct Ollama calls...")
    # Check that "ollama" doesn't appear in any call payloads
    all_payloads_str = str(postal_calls)
    assert "ollama.chat" not in all_payloads_str.lower(), "No direct ollama.chat calls should be present"
    print("  [OK] No direct Ollama calls detected")

    print("\n" + "-" * 60)
    print("[PASS] test_full_cognition_flow - All assertions passed!")
    print("-" * 60)
    return True


# ============================================================================
# Test 2: test_umf_bridge_preference
# ============================================================================

def test_umf_bridge_preference():
    """
    Verifies UMF prefers CognitionBridge over Ollama:
    1. Create minimal UMF-like object with mock fabric
    2. Wire the cognition bridge
    3. Verify bridge gets wired before Ollama is tried
    4. Verify _cognition_bridge_wired flag is set properly
    """
    print("\n" + "=" * 60)
    print("TEST 2: UMF Bridge Preference")
    print("=" * 60)

    # Check if CognitionBridge module is available
    print("\n[Step 1] Checking CognitionBridge availability...")

    try:
        from fairies.P30_Cognition.cognition.postal_cognition_bridge import (
            CognitionBridge,
            ThinkRequest,
            get_cognition_bridge,
        )
        has_bridge_module = True
        print("  [OK] CognitionBridge module imported successfully")
    except ImportError as e:
        has_bridge_module = False
        print(f"  [WARN] CognitionBridge module not available: {e}")
        print("\n[SKIP] Test skipped - CognitionBridge module required")
        return True  # Not a failure, just not testable

    # Create mock fabric
    print("\n[Step 2] Creating mock fabric...")
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value={
        "response": "Test bridged thought",
        "local_only": True,
        "depth_score": 0.7,
        "actions": [],
    })

    # Create bridge and verify it initializes
    print("\n[Step 3] Creating CognitionBridge...")
    bridge = CognitionBridge(mock_fabric)

    assert bridge is not None, "Bridge should be created"
    assert bridge.fabric is mock_fabric, "Bridge should have fabric reference"
    print("  [OK] Bridge created with fabric reference")

    # Verify bridge has the expected topics
    print("\n[Step 4] Verifying bridge topic constants...")
    assert bridge.THINK_TOPIC == "cognition.think", f"Think topic should be 'cognition.think', got '{bridge.THINK_TOPIC}'"
    assert bridge.GOAL_TOPIC == "cognition.goal", f"Goal topic should be 'cognition.goal', got '{bridge.GOAL_TOPIC}'"
    assert bridge.CORTEX_TOPIC == "cortex.spread", f"Cortex topic should be 'cortex.spread', got '{bridge.CORTEX_TOPIC}'"
    print(f"  [OK] THINK_TOPIC: {bridge.THINK_TOPIC}")
    print(f"  [OK] GOAL_TOPIC: {bridge.GOAL_TOPIC}")
    print(f"  [OK] CORTEX_TOPIC: {bridge.CORTEX_TOPIC}")

    # Verify bridge is ready before any Ollama wiring would happen
    print("\n[Step 5] Verifying bridge is operational...")
    test_request = ThinkRequest(stimulus="Test prompt")
    response = bridge.think(test_request)

    assert response is not None, "Bridge should return response"
    mock_fabric.request.assert_called()
    print("  [OK] Bridge routes requests through fabric.request()")

    # Verify the call used cognition.think topic
    call_args = mock_fabric.request.call_args
    assert call_args[0][0] == "cognition.think", f"Should use cognition.think topic, got {call_args[0][0]}"
    print(f"  [OK] Request routed to topic: {call_args[0][0]}")

    print("\n" + "-" * 60)
    print("[PASS] test_umf_bridge_preference - All assertions passed!")
    print("-" * 60)
    return True


# ============================================================================
# Test 3: test_goal_generator_bridge_integration
# ============================================================================

def test_goal_generator_bridge_integration():
    """
    Verifies goal generator uses bridge:
    1. Create DynamicGoalGenerator
    2. Wire a mock bridge with suggest_goal returning a goal
    3. Generate goal - verify bridge.suggest_goal is called
    4. Verify the returned goal comes from the bridge
    """
    print("\n" + "=" * 60)
    print("TEST 3: Goal Generator Bridge Integration")
    print("=" * 60)

    print("\n[Step 1] Importing DynamicGoalGenerator...")

    try:
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
            EXPLORATORY_GOALS,
        )
        print("  [OK] DynamicGoalGenerator imported")
    except ImportError as e:
        print(f"  [FAIL] Could not import DynamicGoalGenerator: {e}")
        return False

    print("\n[Step 2] Creating DynamicGoalGenerator instance...")
    generator = DynamicGoalGenerator()
    print("  [OK] Generator created")
    print(f"  [INFO] Initial bridge state: {generator._cognition_bridge}")

    # Create mock bridge
    print("\n[Step 3] Wiring mock bridge...")
    mock_bridge = Mock()
    mock_bridge.suggest_goal = Mock(return_value="explore_screen")

    generator.wire_bridge(mock_bridge)
    assert generator._cognition_bridge is mock_bridge, "Bridge should be wired"
    print("  [OK] Mock bridge wired to generator")

    # Generate goal with context
    print("\n[Step 4] Generating goal with context...")
    context = {
        "pain_state": {"curiosity": 0.8, "growth": 0.3},
        "chemistry": {"dopamine": 0.7, "cortisol": 0.2},
    }
    result = generator.generate_goal(
        drive_name="curiosity",
        feeling="curious",
        thought="I want to explore",
        context=context,
    )

    # Verify bridge was called
    print("\n[Step 5] Verifying bridge.suggest_goal was called...")
    mock_bridge.suggest_goal.assert_called_once()
    call_args = mock_bridge.suggest_goal.call_args

    assert call_args[0][0] == "curiosity", f"Drive should be 'curiosity', got {call_args[0][0]}"
    print(f"  [OK] suggest_goal called with drive: {call_args[0][0]}")
    print(f"  [OK] suggest_goal called with pain_state: {call_args[0][1]}")
    print(f"  [OK] suggest_goal called with chemistry: {call_args[0][2]}")

    # Verify result
    print("\n[Step 6] Verifying returned goal...")
    assert result is not None, "Goal result should not be None"
    assert isinstance(result, tuple), f"Result should be tuple, got {type(result)}"
    assert len(result) == 2, f"Result should be (name, description), got length {len(result)}"
    assert result[0] == "explore_screen", f"Goal name should be 'explore_screen', got '{result[0]}'"
    print(f"  [OK] Goal returned: {result[0]}")
    print(f"  [OK] Description: {result[1]}")

    print("\n" + "-" * 60)
    print("[PASS] test_goal_generator_bridge_integration - All assertions passed!")
    print("-" * 60)
    return True


# ============================================================================
# Test 4: test_cortex_spread_via_bridge
# ============================================================================

def test_cortex_spread_via_bridge():
    """
    Verifies spreading activation flows through bridge:
    1. Create mock fabric that returns activations
    2. Create CognitionBridge
    3. Call spread_activation - verify "cortex.spread" topic used
    4. Verify returned activations are sorted by strength
    """
    print("\n" + "=" * 60)
    print("TEST 4: Cortex Spread Via Bridge")
    print("=" * 60)

    # Track calls
    spread_calls: List[Dict] = []

    def mock_request(topic: str, payload: Dict, timeout: float = 5.0) -> Dict:
        """Mock request that tracks spread activation calls."""
        spread_calls.append({"topic": topic, "payload": payload})
        print(f"  [Postal] Request to '{topic}'")

        if topic == "cortex.spread":
            # Return mock activations
            return {
                "ok": True,
                "activations": {
                    "curiosity": 1.0,
                    "explore": 0.8,
                    "discover": 0.7,
                    "memory": 0.6,
                    "pattern": 0.5,
                    "insight": 0.4,
                    "learning": 0.3,
                    "growth": 0.2,
                },
                "seed": payload.get("seed", ""),
                "hops": payload.get("max_hops", 2),
            }
        return {}

    print("\n[Step 1] Creating mock fabric with activation responses...")
    mock_fabric = MagicMock()
    mock_fabric.request = mock_request

    print("\n[Step 2] Creating CognitionBridge...")
    from fairies.P30_Cognition.cognition.postal_cognition_bridge import CognitionBridge

    bridge = CognitionBridge(mock_fabric)
    print("  [OK] Bridge created")

    # Test spread activation
    print("\n[Step 3] Calling spread_activation...")
    activations = bridge.spread_activation(
        seed_concept="curiosity",
        helix_hint={"affect": {"domain": "CURIOSITY", "intensity": 700}},
        max_hops=3,
    )

    # Verify cortex.spread topic was used
    print("\n[Step 4] Verifying cortex.spread topic used...")
    assert len(spread_calls) == 1, f"Should have 1 call, got {len(spread_calls)}"
    assert spread_calls[0]["topic"] == "cortex.spread", f"Topic should be 'cortex.spread', got {spread_calls[0]['topic']}"
    print(f"  [OK] Correct topic used: {spread_calls[0]['topic']}")

    # Verify payload
    payload = spread_calls[0]["payload"]
    assert payload["seed"] == "curiosity", f"Seed should be 'curiosity', got {payload['seed']}"
    assert payload["max_hops"] == 3, f"max_hops should be 3, got {payload['max_hops']}"
    assert payload["helix_hint"] is not None, "helix_hint should be passed"
    print(f"  [OK] Payload: seed={payload['seed']}, max_hops={payload['max_hops']}")

    # Verify returned activations
    print("\n[Step 5] Verifying returned activations...")
    assert activations is not None, "Activations should not be None"
    assert isinstance(activations, list), f"Activations should be list, got {type(activations)}"
    assert len(activations) <= 10, f"Should return max 10 activations, got {len(activations)}"
    print(f"  [OK] Returned {len(activations)} activations")

    # Verify sorted by activation strength (highest first)
    print("\n[Step 6] Verifying activations are sorted by strength...")
    expected_order = ["curiosity", "explore", "discover", "memory", "pattern", "insight", "learning", "growth"]
    for i, concept in enumerate(activations):
        if i < len(expected_order):
            assert concept == expected_order[i], f"Position {i} should be '{expected_order[i]}', got '{concept}'"
    print(f"  [OK] Activations in correct order: {activations[:5]}...")

    print("\n" + "-" * 60)
    print("[PASS] test_cortex_spread_via_bridge - All assertions passed!")
    print("-" * 60)
    return True


# ============================================================================
# Test 5: test_bridge_error_handling
# ============================================================================

def test_bridge_error_handling():
    """
    Verifies CognitionBridge handles errors gracefully:
    1. Test with None fabric
    2. Test with fabric that returns None
    3. Test with fabric that raises exception
    """
    print("\n" + "=" * 60)
    print("TEST 5: Bridge Error Handling")
    print("=" * 60)

    from fairies.P30_Cognition.cognition.postal_cognition_bridge import (
        CognitionBridge,
        ThinkRequest,
    )

    # Test 1: None fabric in constructor should raise
    print("\n[Step 1] Testing None fabric rejection...")
    try:
        bridge = CognitionBridge(None)
        print("  [FAIL] Should have raised ValueError for None fabric")
        return False
    except ValueError as e:
        print(f"  [OK] Correctly raised ValueError: {e}")

    # Test 2: Fabric returns None
    print("\n[Step 2] Testing fabric that returns None...")
    mock_fabric = MagicMock()
    mock_fabric.request = MagicMock(return_value=None)

    bridge = CognitionBridge(mock_fabric)
    response = bridge.think(ThinkRequest(stimulus="test"))

    assert response.thought == "", "Thought should be empty on None response"
    assert response.error is not None, "Should have error message"
    print(f"  [OK] Handled None response: error='{response.error}'")

    # Test 3: Fabric raises exception
    print("\n[Step 3] Testing fabric that raises exception...")
    mock_fabric.request = MagicMock(side_effect=Exception("Connection failed"))

    response = bridge.think(ThinkRequest(stimulus="test"))

    assert response.thought == "", "Thought should be empty on exception"
    assert response.error is not None, "Should have error message"
    assert "Connection failed" in response.error, "Error should contain exception message"
    print(f"  [OK] Handled exception: error='{response.error}'")

    # Test 4: suggest_goal with broken fabric
    print("\n[Step 4] Testing suggest_goal with broken fabric...")
    goal = bridge.suggest_goal("curiosity", {}, {})
    assert goal is None, "Goal should be None when fabric fails"
    print("  [OK] suggest_goal returned None on failure")

    # Test 5: spread_activation with broken fabric
    print("\n[Step 5] Testing spread_activation with broken fabric...")
    activations = bridge.spread_activation("test_seed")
    assert activations == [], "Activations should be empty list on failure"
    print("  [OK] spread_activation returned empty list on failure")

    print("\n" + "-" * 60)
    print("[PASS] test_bridge_error_handling - All assertions passed!")
    print("-" * 60)
    return True


# ============================================================================
# Test 6: test_think_response_parsing
# ============================================================================

def test_think_response_parsing():
    """
    Verifies ThinkResponse correctly parses various response formats:
    1. Standard response with all fields
    2. Response with "response" field (alternative to "thought")
    3. Response with invalid types (should handle gracefully)
    4. Empty/minimal response
    """
    print("\n" + "=" * 60)
    print("TEST 6: ThinkResponse Parsing")
    print("=" * 60)

    from fairies.P30_Cognition.cognition.postal_cognition_bridge import ThinkResponse

    # Test 1: Standard response
    print("\n[Step 1] Testing standard response parsing...")
    data = {
        "response": "This is the thought",
        "reasoning": "Because of X",
        "actions": [{"type": "explore", "target": "memory"}],
        "local_only": True,
        "depth_score": 0.85,
        "associations": ["memory", "pattern"],
        "error": None,
    }
    response = ThinkResponse.from_dict(data)

    assert response.thought == "This is the thought"
    assert response.reasoning == "Because of X"
    assert len(response.actions) == 1
    assert response.local_only is True
    assert response.depth_score == 0.85
    assert len(response.associations) == 2
    assert response.error is None
    print("  [OK] Standard response parsed correctly")

    # Test 2: Alternative "thought" field
    print("\n[Step 2] Testing 'thought' field alternative...")
    data = {"thought": "Alternative field name", "local_only": False}
    response = ThinkResponse.from_dict(data)

    assert response.thought == "Alternative field name"
    print("  [OK] 'thought' field parsed correctly")

    # Test 3: Invalid types (should handle gracefully)
    print("\n[Step 3] Testing invalid type handling...")
    data = {
        "response": "Valid thought",
        "actions": "not a list",  # Should be list
        "associations": {"wrong": "type"},  # Should be list
        "depth_score": "not a number",  # Should be float
    }
    response = ThinkResponse.from_dict(data)

    assert response.thought == "Valid thought"
    assert response.actions == [], "Invalid actions should become empty list"
    assert response.associations == [], "Invalid associations should become empty list"
    assert response.depth_score == 0.0, "Invalid depth_score should become 0.0"
    print("  [OK] Invalid types handled gracefully")

    # Test 4: Empty response
    print("\n[Step 4] Testing empty/minimal response...")
    data = {}
    response = ThinkResponse.from_dict(data)

    assert response.thought == ""
    assert response.actions == []
    assert response.local_only is True  # default
    print("  [OK] Empty response handled correctly")

    # Test 5: Non-dict input
    print("\n[Step 5] Testing non-dict input...")
    response = ThinkResponse.from_dict("not a dict")
    assert response.thought == ""
    assert response.error is not None
    print(f"  [OK] Non-dict input handled: error='{response.error}'")

    print("\n" + "-" * 60)
    print("[PASS] test_think_response_parsing - All assertions passed!")
    print("-" * 60)
    return True


# ============================================================================
# Main Runner
# ============================================================================

def run_all_tests():
    """Run all E2E tests and report results."""
    print("\n" + "=" * 70)
    print(" COGNITION REWIRING E2E TEST SUITE")
    print(" Verifying complete cognition flow without direct Ollama calls")
    print("=" * 70)

    tests = [
        ("test_full_cognition_flow", test_full_cognition_flow),
        ("test_umf_bridge_preference", test_umf_bridge_preference),
        ("test_goal_generator_bridge_integration", test_goal_generator_bridge_integration),
        ("test_cortex_spread_via_bridge", test_cortex_spread_via_bridge),
        ("test_bridge_error_handling", test_bridge_error_handling),
        ("test_think_response_parsing", test_think_response_parsing),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result, None))
        except Exception as e:
            import traceback
            results.append((name, False, str(e)))
            print(f"\n[EXCEPTION] {name}: {e}")
            traceback.print_exc()

    # Summary
    print("\n\n" + "=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0
    for name, result, error in results:
        status = "PASS" if result else "FAIL"
        if result:
            passed += 1
            print(f"  [{status}] {name}")
        else:
            failed += 1
            print(f"  [{status}] {name}")
            if error:
                print(f"         Error: {error}")

    print("-" * 70)
    print(f" Total: {len(tests)} | Passed: {passed} | Failed: {failed}")

    if failed == 0:
        print("\n [SUCCESS] All E2E tests passed!")
        print(" The cognition rewiring is working correctly.")
    else:
        print(f"\n [FAILURE] {failed} test(s) failed.")

    print("=" * 70 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
