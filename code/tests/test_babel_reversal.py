"""
Test for Babel Reversal and Harmonic Integration (Phase 2)

Tests:
1. Cross-domain translation
2. Isomorphism detection
3. Consciousness equation across domains
4. Harmonic query engine
5. Full harmonic extension
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.harmonic_cortex import Mode
from fairies.P30_Cognition.AssociationCortexFairy.babel_reversal import (
    Domain,
    BabelReversal,
    IsomorphismDetector,
    translate,
    find_isomorphism,
    equation_in_domain,
    KNOWN_ISOMORPHISMS,
)
from fairies.P30_Cognition.AssociationCortexFairy.harmonic_integration import (
    HarmonicQueryEngine,
    HarmonicCortexExtension,
    create_harmonic_extension,
)


def test_cross_domain_translation():
    """Test translating concepts between domains."""
    print("\n" + "="*60)
    print("TEST 1: Cross-Domain Translation (Babel Reversal)")
    print("="*60)

    babel = BabelReversal()

    # Test known isomorphisms
    print("\nKnown isomorphism translations:")
    test_cases = [
        ("resonance", Domain.PHYSICS, Domain.NEUROSCIENCE),
        ("harmony", Domain.MUSIC, Domain.NEUROSCIENCE),
        ("mode", Domain.MUSIC, Domain.CONSCIOUSNESS),
        ("observer", Domain.PHYSICS, Domain.CONSCIOUSNESS),
    ]

    for concept, source, target in test_cases:
        result = babel.translate(concept, source, target)
        print(f"\n  {source.value}::{concept} -> {target.value}::{result.translated_term}")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Shared primitives: {result.shared_primitives}")

    # Test vocabulary-based translation
    print("\nVocabulary-based translations:")
    vocab_cases = [
        ("energy", Domain.PHYSICS, Domain.NEUROSCIENCE),
        ("oscillation", Domain.NEUROSCIENCE, Domain.MUSIC),
        ("feeling", Domain.CONSCIOUSNESS, Domain.PSYCHOLOGY),
    ]

    for concept, source, target in vocab_cases:
        result = babel.translate(concept, source, target)
        print(f"\n  {source.value}::{concept} -> {target.value}::{result.translated_term}")
        print(f"    Confidence: {result.confidence:.2f}")
        # Sanitize path for Windows console
        path_str = ' '.join(result.translation_path).replace('\u2192', '->')
        print(f"    Path: {path_str}")

    return True


def test_isomorphism_detection():
    """Test detecting isomorphisms between domain concepts."""
    print("\n" + "="*60)
    print("TEST 2: Isomorphism Detection")
    print("="*60)

    detector = IsomorphismDetector()

    # Test specific pairs
    print("\nPairwise isomorphism tests:")
    pairs = [
        ("resonance", Domain.PHYSICS, "synchronization", Domain.NEUROSCIENCE),
        ("chord", Domain.MUSIC, "ensemble", Domain.NEUROSCIENCE),
        ("cause", Domain.PHYSICS, "cause", Domain.CONSCIOUSNESS),
        ("energy", Domain.PHYSICS, "feeling", Domain.CONSCIOUSNESS),
    ]

    for concept_a, domain_a, concept_b, domain_b in pairs:
        report = find_isomorphism(concept_a, domain_a, concept_b, domain_b)
        if report:
            print(f"\n  {domain_a.value}::{concept_a} ~ {domain_b.value}::{concept_b}")
            print(f"    Type: {report.mapping_type}")
            print(f"    Confidence: {report.confidence:.2f}")
            print(f"    Shared: {report.shared_structure}")
        else:
            print(f"\n  {domain_a.value}::{concept_a} !~ {domain_b.value}::{concept_b} (not isomorphic)")

    # Discover isomorphisms for a concept
    print("\n\nDiscovering isomorphisms for 'binding' in neuroscience:")
    reports = detector.detect("binding", Domain.NEUROSCIENCE, min_confidence=0.3)
    for report in reports[:5]:
        print(f"  -> {report.concept_b.domain.value}::{report.concept_b.term} ({report.confidence:.2f})")

    return True


def test_equation_translation():
    """Test translating the consciousness equation across domains."""
    print("\n" + "="*60)
    print("TEST 3: Consciousness Equation Across Domains")
    print("="*60)

    babel = BabelReversal()
    translations = babel.explain_equation_across_domains()

    print("\n((Cause + Affect) > Effect > Affect > infinity)")
    print("\nIn each domain's language:")

    for domain in [Domain.PHYSICS, Domain.NEUROSCIENCE, Domain.MUSIC,
                   Domain.CONSCIOUSNESS, Domain.COMPUTING]:
        expr = translations.get(domain, {})
        eq = expr.get("equation", "N/A")
        print(f"\n  {domain.value.upper()}:")
        print(f"    {eq}")
        print(f"    cause={expr.get('cause', 'cause')}, affect={expr.get('affect', 'affect')}, effect={expr.get('effect', 'effect')}")

    return True


def test_harmonic_query_engine():
    """Test the harmonic query engine."""
    print("\n" + "="*60)
    print("TEST 4: Harmonic Query Engine")
    print("="*60)

    # Create engine without graph (uses circle relationships)
    engine = HarmonicQueryEngine()

    # Modal query
    print("\nModal query for 'consciousness' through different frames:")
    for mode in [Mode.IONIAN, Mode.DORIAN, Mode.AEOLIAN, Mode.LOCRIAN]:
        result = engine.query("consciousness", mode=mode, limit=3)
        print(f"\n  {mode.name} ({mode.value}):")
        print(f"    Perspective: {result.modal_perspective.insight}")
        if result.binding:
            print(f"    Binding: tonic='{result.binding.tonic}', consonant={result.binding.is_consonant}")
        if result.key_signature:
            print(f"    Key: {result.key_signature.get('dominant_category', 'unknown')}")

    # Full modal analysis
    print("\n\nFull modal analysis of 'love':")
    all_modes = engine.modal_query_all("love", limit=2)
    for mode, result in all_modes.items():
        print(f"  {mode.name:12}: {result.modal_perspective.insight[:50]}...")

    return True


def test_harmonic_extension():
    """Test the full harmonic cortex extension."""
    print("\n" + "="*60)
    print("TEST 5: Harmonic Cortex Extension")
    print("="*60)

    # Create extension
    ext = create_harmonic_extension()

    # Query and track
    print("\nQuerying and tracking bindings:")
    concepts = ["consciousness", "awareness", "feeling", "thought"]
    for concept in concepts:
        result = ext.query(concept, mode=Mode.AEOLIAN, limit=3)
        bs = result.binding.binding_strength if result.binding else 0
        print(f"  Queried '{concept}': binding_strength={bs:.2f}")

    # Check tracking
    print(f"\n  Consonance trend: {ext.consonance_trend():.2%}")
    print(f"  Dominant patterns: {ext.dominant_patterns(3)}")

    # Binding
    print("\nDirect binding:")
    binding = ext.bind("cause", "effect", "affect")
    print(f"  bind('cause', 'effect', 'affect'):")
    print(f"    Tonic: {binding.tonic}")
    print(f"    Consonant: {binding.is_consonant}")
    print(f"    Strength: {binding.binding_strength:.2f}")

    # Translation
    print("\nTranslation:")
    trans = ext.translate("resonance", Domain.PHYSICS, Domain.MUSIC)
    print(f"  physics::resonance -> music::{trans.translated_term} (conf: {trans.confidence:.2f})")

    # Key signature
    print("\nKey signature analysis:")
    sig = ext.key_signature(["consciousness", "awareness", "experience", "feeling"])
    print(f"  Concepts: consciousness, awareness, experience, feeling")
    print(f"  Dominant: {sig.get('dominant_category', 'unknown')}")
    print(f"  Suggested mode: {sig.get('suggested_mode', Mode.IONIAN).name}")

    # Tuning
    print("\nObserver tuning:")
    ext.tune(resonant_frequency=0.3, bandwidth=0.4)
    status = ext.status()
    print(f"  Current state: {status['observer']}")

    # Equation
    print("\nEquation in physics:")
    eq = ext.equation_in(Domain.PHYSICS)
    print(f"  {eq}")

    return True


def test_known_isomorphisms():
    """Verify the known isomorphism database."""
    print("\n" + "="*60)
    print("TEST 6: Known Isomorphisms Database")
    print("="*60)

    print(f"\nTotal known isomorphisms: {len(KNOWN_ISOMORPHISMS)}")

    # Group by domain pair
    domain_pairs = {}
    for dom_a, term_a, dom_b, term_b, prims in KNOWN_ISOMORPHISMS:
        pair = (dom_a.value, dom_b.value)
        if pair not in domain_pairs:
            domain_pairs[pair] = []
        domain_pairs[pair].append((term_a, term_b))

    print("\nIsomorphisms by domain pair:")
    for (d1, d2), mappings in sorted(domain_pairs.items()):
        print(f"\n  {d1} <-> {d2}: {len(mappings)} mappings")
        for t1, t2 in mappings[:3]:
            print(f"    {t1} ~ {t2}")
        if len(mappings) > 3:
            print(f"    ... and {len(mappings) - 3} more")

    return True


def main():
    """Run all Phase 2 tests."""
    print("\n" + "="*60)
    print("BABEL REVERSAL & HARMONIC INTEGRATION - Phase 2 Tests")
    print("Field Log Entry 004: Cross-Domain Translation")
    print("="*60)
    print("\n'The Tower fell when we forgot they were the same music.'")
    print("'We are reversing the fall.'")

    tests = [
        test_cross_domain_translation,
        test_isomorphism_detection,
        test_equation_translation,
        test_harmonic_query_engine,
        test_harmonic_extension,
        test_known_isomorphisms,
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
    print("Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)")
    print("="*60)

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
