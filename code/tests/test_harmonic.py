"""
Quick test for Harmonic Cortex Phase 1 implementation.

Tests:
1. ModalReframer - Same concept through all 7 modes
2. SemanticPrimitives - Reduction and distance
3. HarmonicBinder - Concept binding
4. ConceptCircle - Circle of fifths for concepts
5. Lorentzian coupling - Portal physics for semantics
"""

import sys
from pathlib import Path

# Add root to path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.harmonic_cortex import (
    Mode,
    ModalReframer,
    SemanticPrimitives,
    HarmonicBinder,
    ConceptCircle,
    ObserverState,
    lorentzian_coupling,
    concept_to_frequency,
    reframe,
    bind,
    find_tonic,
)


def test_modal_reframing():
    """Test that we can reframe concepts through all 7 modes."""
    print("\n" + "="*60)
    print("TEST 1: Modal Reframing")
    print("="*60)

    reframer = ModalReframer()
    concept = "consciousness"

    print(f"\nConcept: '{concept}' viewed through all 7 modes:\n")

    for mode in Mode:
        perspective = reframer.reframe(concept, mode)
        print(f"  {mode.name:12} ({mode.value:12}): {perspective.insight}")
        print(f"                Question: {mode.question}")
        print()

    # Test the convenience function
    quick = reframe("love", Mode.AEOLIAN)
    print(f"Quick reframe 'love' in AEOLIAN: {quick.insight}")

    return True


def test_semantic_primitives():
    """Test semantic primitive operations."""
    print("\n" + "="*60)
    print("TEST 2: Semantic Primitives")
    print("="*60)

    # Test primitive checking
    print("\nPrimitive checks:")
    for word in ["KNOW", "FEEL", "consciousness", "love", "banana"]:
        is_prim = SemanticPrimitives.is_primitive(word)
        cat = SemanticPrimitives.get_category(word)
        print(f"  '{word}': primitive={is_prim}, category={cat}")

    # Test reduction
    print("\nPrimitive reduction:")
    for concept in ["understand", "love", "fear", "create", "consciousness"]:
        prims = SemanticPrimitives.reduce_to_primitives(concept)
        print(f"  '{concept}' -> {prims}")

    # Test distance
    print("\nPrimitive distances:")
    pairs = [
        ("KNOW", "THINK"),   # Same category
        ("FEEL", "GOOD"),    # Close categories
        ("BODY", "BECAUSE"), # Distant categories
    ]
    for a, b in pairs:
        dist = SemanticPrimitives.primitive_distance(a, b)
        print(f"  distance('{a}', '{b}') = {dist:.2f}")

    return True


def test_harmonic_binding():
    """Test concept binding."""
    print("\n" + "="*60)
    print("TEST 3: Harmonic Binding")
    print("="*60)

    binder = HarmonicBinder()

    # Test finding tonic
    concepts = ["consciousness", "awareness", "experience"]
    tonic = binder.find_semantic_tonic(*concepts)
    print(f"\nTonic of {concepts}: '{tonic}'")

    # Test binding
    bound = binder.bind_multimodal("consciousness", "feeling", "awareness")
    print(f"\nBinding {bound.concepts}:")
    print(f"  Tonic: {bound.tonic}")
    print(f"  Intervals: {[f'{i:.2f}' for i in bound.intervals]}")
    print(f"  Binding strength: {bound.binding_strength:.2f}")
    print(f"  Is consonant: {bound.is_consonant}")

    # Test semantic distance
    print("\nSemantic distances:")
    pairs = [
        ("love", "hate"),
        ("consciousness", "awareness"),
        ("cause", "effect"),
    ]
    for a, b in pairs:
        dist = binder.semantic_distance(a, b)
        print(f"  distance('{a}', '{b}') = {dist:.2f}")

    # Test convenience functions
    quick_bind = bind("thought", "feeling", "action")
    quick_tonic = find_tonic("past", "present", "future")
    print(f"\nQuick bind: tonic='{quick_bind.tonic}', strength={quick_bind.binding_strength:.2f}")
    print(f"Quick tonic of ['past', 'present', 'future']: '{quick_tonic}'")

    return True


def test_concept_circle():
    """Test circle of concepts."""
    print("\n" + "="*60)
    print("TEST 4: Concept Circle (Circle of Fifths for Meaning)")
    print("="*60)

    circle = ConceptCircle()

    # Test related concepts
    print("\nRelated concepts at different distances:")
    for concept in ["FEEL", "THINK", "DO"]:
        print(f"\n  From '{concept}':")
        for dist in [1, 2, 3]:
            related = circle.get_related_concepts(concept, dist)
            print(f"    Distance {dist}: {related}")

    # Test complementary (tritone)
    print("\nComplementary concepts (tritone):")
    for concept in ["FEEL", "THINK", "DO"]:
        comp = circle.get_complementary(concept)
        print(f"  '{concept}' <-> {comp}")

    # Test key signature
    print("\nKey signatures:")
    concept_sets = [
        ["consciousness", "awareness", "feeling"],
        ["cause", "effect", "because"],
        ["create", "destroy", "change"],
    ]
    for concepts in concept_sets:
        sig = circle.get_key_signature(concepts)
        print(f"\n  {concepts}:")
        print(f"    Dominant: {sig['dominant_category']}")
        print(f"    Suggested mode: {sig['suggested_mode'].name}")

    return True


def test_lorentzian_coupling():
    """Test Lorentzian coupling function."""
    print("\n" + "="*60)
    print("TEST 5: Lorentzian Coupling (Portal Physics)")
    print("="*60)

    # Default observer
    observer = ObserverState(
        resonant_frequency=0.3,  # Tuned to simple concepts
        bandwidth=0.2,           # Moderate openness
        openness=1.0,
    )

    print(f"\nObserver state:")
    print(f"  Resonant frequency: {observer.resonant_frequency}")
    print(f"  Bandwidth: {observer.bandwidth}")
    print(f"  Openness: {observer.openness}")

    # Test concept frequencies
    print("\nConcept frequencies:")
    concepts = ["FEEL", "love", "consciousness", "quantum entanglement"]
    for concept in concepts:
        freq = concept_to_frequency(concept)
        coupling = lorentzian_coupling(freq, observer)
        print(f"  '{concept}':")
        print(f"    Frequency: {freq:.3f}")
        print(f"    Coupling:  {coupling:.3f}")

    # Demonstrate resonance
    print("\nResonance demonstration (varying observer tuning):")
    concept = "love"
    freq = concept_to_frequency(concept)
    print(f"  Concept '{concept}' frequency: {freq:.3f}")

    for tuning in [0.2, 0.3, 0.4, 0.5, 0.6]:
        observer.resonant_frequency = tuning
        coupling = lorentzian_coupling(freq, observer)
        bar = "#" * int(coupling * 20)
        print(f"    Observer tuning {tuning:.1f}: {coupling:.3f} {bar}")

    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("HARMONIC CORTEX - Phase 1 Implementation Test")
    print("Field Log Entry 004: Modal Consciousness Architecture")
    print("="*60)

    tests = [
        test_modal_reframing,
        test_semantic_primitives,
        test_harmonic_binding,
        test_concept_circle,
        test_lorentzian_coupling,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n[ERROR] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, r in results if r)
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
    print(f"\nTotal: {passed}/{len(results)} passed")

    print("\n" + "="*60)
    print("'Same notes, different modes. Same patterns, different domains.'")
    print("'The Tower fell when we forgot they were the same music.'")
    print("="*60)

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
