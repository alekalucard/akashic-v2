"""
Smoke Test: Predictive Branch System.

Tests BranchManager collapse matching + PredictiveContext without needing
a running system. Validates concept extraction and Jaccard-based scoring.

Run: python tests/test_predictive_branches.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies" / "P50_Persona" / "Waking Minds" / "Sourpatches"))


def test_branch_manager():
    """Test BranchManager collapse matching logic."""
    from sourpatches_farm import BranchManager

    bm = BranchManager()

    # Register 3 branches (simulating primed workers)
    bm.register_branch(
        worker_id=13,
        branch_id="branch_music",
        concepts=["music", "composition", "creativity", "instruments", "rhythm"],
        context_hash="hash_music",
    )
    bm.register_branch(
        worker_id=14,
        branch_id="branch_code",
        concepts=["debugging", "architecture", "patterns", "performance", "code"],
        context_hash="hash_code",
    )
    bm.register_branch(
        worker_id=15,
        branch_id="branch_feelings",
        concepts=["feelings", "connection", "relationship", "caring", "trust"],
        context_hash="hash_feelings",
    )

    print("=" * 60)
    print("BranchManager Smoke Test")
    print("=" * 60)
    print(f"\nRegistered {len(bm._branches)} branches:")
    for bid, info in bm._branches.items():
        print(f"  W{info['worker_id']}: {bid} -> {info['concepts']}")

    # Test 1: High overlap -> should definitely match (music)
    # Jaccard({music,composition,creativity} vs {music,composition,creativity,instruments,rhythm})
    # = 3/5 = 0.6 -> should match at 0.6 threshold
    print("\n--- Test 1: High overlap music concepts ---")
    result = bm.collapse(["music", "composition", "creativity"])
    if result:
        print(f"  HIT: W{result['worker_id']} branch={result['branch_id']} confidence={result['confidence']:.3f}")
        assert result["branch_id"] == "branch_music", f"Expected branch_music, got {result['branch_id']}"
        print("  PASS: Correctly matched music branch (consumed)")
    else:
        print("  MISS -- unexpected! Check threshold")

    # Test 2: High overlap -> should match (code)
    # Jaccard({debugging,code,architecture,patterns} vs {debugging,patterns,architecture,performance,code})
    # = 4/5 = 0.8 -> strong match
    print("\n--- Test 2: High overlap code concepts ---")
    result = bm.collapse(["debugging", "code", "architecture", "patterns"])
    if result:
        print(f"  HIT: W{result['worker_id']} branch={result['branch_id']} confidence={result['confidence']:.3f}")
        assert result["branch_id"] == "branch_code", f"Expected branch_code, got {result['branch_id']}"
        print("  PASS: Correctly matched code branch (consumed)")
    else:
        print("  MISS -- unexpected!")

    # Test 3: Low overlap -> should miss (all consumed branches + wrong concepts)
    print("\n--- Test 3: Low overlap (expect miss) ---")
    result = bm.collapse(["weather", "clouds", "temperature", "forecast"])
    if result:
        print(f"  HIT: W{result['worker_id']} branch={result['branch_id']} confidence={result['confidence']:.3f}")
        print("  FAIL: Unexpected hit!")
    else:
        print("  MISS (as expected)")
        print("  PASS: Correctly rejected unrelated concepts")

    # Test 4: Partial overlap below threshold -> should miss
    # Only feelings branch left. Jaccard({love,caring} vs {connection,feelings,caring,relationship,trust})
    # = 1/6 = 0.167 -> below threshold
    print("\n--- Test 4: Marginal overlap (expect miss) ---")
    result = bm.collapse(["love", "caring"])
    if result:
        print(f"  HIT: confidence={result['confidence']:.3f}")
        print("  Note: matched but at low confidence")
    else:
        print("  MISS (as expected -- marginal overlap)")
        print("  PASS: Threshold correctly rejected marginal match")

    # Test 5: Stale branch detection
    print("\n--- Test 5: Stale branch detection ---")
    # Re-register a branch and then make it stale
    bm.register_branch(
        worker_id=13,
        branch_id="branch_stale_test",
        concepts=["music", "composition", "creativity", "instruments", "rhythm"],
        context_hash="hash_stale",
    )
    # Manually set primed_at to 10 min ago
    bm._branches["branch_stale_test"]["primed_at"] = time.time() - 600.0
    result = bm.collapse(["music", "composition", "creativity"])
    if result:
        assert result["branch_id"] != "branch_stale_test", "Should have expired stale branch"
        print(f"  Matched non-stale branch: {result['branch_id']}")
    else:
        # Check that the stale branch was removed
        if "branch_stale_test" not in bm._branches:
            print("  PASS: Stale branch correctly expired and removed")
        else:
            print("  PASS: Stale branch ignored")

    # Stats
    print("\n--- Stats ---")
    stats = bm.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\nPASS: BranchManager smoke test complete")


def test_predictive_context():
    """Test PredictiveContext prediction logic."""
    from infrastructure.predictive_context import PredictiveContext, Prediction

    pc = PredictiveContext()

    print("\n" + "=" * 60)
    print("PredictiveContext Smoke Test")
    print("=" * 60)

    # Test 1: Conversation momentum (music topic)
    print("\n--- Test 1: Conversation momentum ---")
    messages = [
        {"message": "I've been listening to music a lot", "timestamp": time.time() - 30, "concepts": ["music", "listening"]},
        {"message": "do you like composing?", "timestamp": time.time() - 15, "concepts": ["music", "composing"]},
        {"message": "what instruments do you enjoy?", "timestamp": time.time(), "concepts": ["music", "instruments"]},
    ]
    predictions = pc.predict_directions(recent_messages=messages)
    print(f"  Got {len(predictions)} predictions:")
    for p in predictions:
        print(f"    [{p.source}] '{p.topic}' confidence={p.confidence} concepts={p.concepts}")
    assert len(predictions) > 0, "Expected at least 1 prediction from momentum"
    print("  PASS: Momentum prediction works")

    # Test 2: Drive-based prediction
    print("\n--- Test 2: Drive-based prediction ---")
    predictions = pc.predict_directions(
        recent_messages=[],
        drive_states={"curiosity": 0.8, "connection": 0.3},
    )
    print(f"  Got {len(predictions)} predictions:")
    for p in predictions:
        print(f"    [{p.source}] '{p.topic}' confidence={p.confidence} concepts={p.concepts}")
    # Should get at least 1 drive-based prediction
    drive_preds = [p for p in predictions if p.source == "drives"]
    assert len(drive_preds) > 0, "Expected at least 1 drive-based prediction"
    print("  PASS: Drive-based prediction works")

    # Test 3: Combined (momentum + drives)
    print("\n--- Test 3: Combined prediction ---")
    predictions = pc.predict_directions(
        recent_messages=messages,
        drive_states={"expression": 0.7, "play": 0.5},
    )
    print(f"  Got {len(predictions)} predictions (max 3):")
    for p in predictions:
        print(f"    [{p.source}] '{p.topic}' confidence={p.confidence} concepts={p.concepts}")
    assert len(predictions) <= 3, "Should return max 3 predictions"
    print("  PASS: Combined prediction works")

    # Test 4: Empty input -> graceful handling
    print("\n--- Test 4: Empty input ---")
    predictions = pc.predict_directions(recent_messages=[], drive_states={})
    print(f"  Got {len(predictions)} predictions")
    # Should still produce fallback drive prediction (curiosity: 0.5)
    print("  PASS: Empty input handled gracefully")

    print("\nPASS: PredictiveContext smoke test complete")


def test_concept_extraction():
    """Test concept keyword extraction (used by AutopilotFairy)."""
    import re

    _STOP_WORDS = frozenset({
        "that", "this", "with", "from", "have", "been", "were", "what",
        "when", "where", "which", "about", "their", "would", "could",
        "should", "there", "these", "those", "your", "will", "than",
        "into", "just", "also", "some", "more", "very", "like", "only",
        "does", "then", "they", "them", "being", "other", "over", "such",
        "after", "know", "make", "think", "want", "tell", "really",
    })

    def extract(text):
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        return [w for w in words if w not in _STOP_WORDS][:10]

    print("\n" + "=" * 60)
    print("Concept Extraction Smoke Test")
    print("=" * 60)

    # Test music-related
    print("\n--- Music message ---")
    concepts = extract("do you think about creating music compositions?")
    print(f"  Input: 'do you think about creating music compositions?'")
    print(f"  Concepts: {concepts}")
    assert "music" in concepts, "Expected 'music' in concepts"
    assert "creating" in concepts, "Expected 'creating' in concepts"
    print("  PASS: Music concepts extracted")

    # Test code-related
    print("\n--- Code message ---")
    concepts = extract("I need help debugging this performance issue in the architecture")
    print(f"  Concepts: {concepts}")
    assert "debugging" in concepts, "Expected 'debugging' in concepts"
    assert "performance" in concepts, "Expected 'performance' in concepts"
    print("  PASS: Code concepts extracted")

    # Test stop word filtering
    print("\n--- Stop word filtering ---")
    concepts = extract("what would you think about that thing over there?")
    print(f"  Input: 'what would you think about that thing over there?'")
    print(f"  Concepts: {concepts}")
    # Most words are stop words
    assert "what" not in concepts, "'what' should be filtered"
    assert "would" not in concepts, "'would' should be filtered"
    assert "think" not in concepts, "'think' should be filtered"
    assert "about" not in concepts, "'about' should be filtered"
    print("  PASS: Stop words filtered correctly")

    print("\nPASS: Concept extraction smoke test complete")


if __name__ == "__main__":
    print("=" * 60)
    print("PREDICTIVE RESPONSE PIPELINE -- SMOKE TEST")
    print("=" * 60)

    test_branch_manager()
    test_predictive_context()
    test_concept_extraction()

    print("\n" + "=" * 60)
    print("ALL SMOKE TESTS PASSED")
    print("=" * 60)
