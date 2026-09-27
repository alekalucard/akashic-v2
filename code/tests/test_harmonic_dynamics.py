"""
Test for Harmonic Dynamics (Phase 3)

Tests:
1. Dynamic bandwidth adjustment
2. Cusp-mode multi-resonance
3. Comma-space exploration
4. Full dynamics engine
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.harmonic_cortex import Mode
from fairies.P30_Cognition.AssociationCortexFairy.harmonic_dynamics import (
    BandwidthMode,
    DynamicObserver,
    CuspState,
    CuspNavigator,
    CommaExplorer,
    CommaFinding,
    HarmonicDynamicsEngine,
    PYTHAGOREAN_COMMA,
    create_dynamics_engine,
    explore_comma,
    enter_cusp,
)


def test_dynamic_bandwidth():
    """Test dynamic bandwidth adjustment."""
    print("\n" + "="*60)
    print("TEST 1: Dynamic Bandwidth Adjustment")
    print("="*60)

    observer = DynamicObserver()

    print("\nBandwidth modes:")
    for mode in BandwidthMode:
        observer.set_bandwidth_mode(mode)
        print(f"  {mode.value:12}: bandwidth={observer.bandwidth:.2f} - {mode.description}")

    # Test tuning
    print("\nTuning observer to concepts:")
    concepts = ["consciousness", "love", "algorithm", "quantum"]
    for concept in concepts:
        observer.tune_to(concept)
        print(f"  Tuned to '{concept}': freq={observer.resonant_frequency:.3f}")

    # Test auto-adjustment
    print("\nAuto-adjustment based on query patterns:")
    # Simulate focused queries (low variance)
    observer.query_history = [0.3, 0.31, 0.29, 0.30, 0.32, 0.30]
    observer.auto_adjust_bandwidth()
    print(f"  Focused queries -> mode: {observer.bandwidth_mode.value}")

    # Simulate exploratory queries (high variance)
    observer.query_history = [0.1, 0.8, 0.3, 0.9, 0.2, 0.7]
    observer.auto_adjust_bandwidth()
    print(f"  Spread queries -> mode: {observer.bandwidth_mode.value}")

    print(f"\nObserver status: {observer.status()}")
    return True


def test_cusp_mode():
    """Test cusp-mode multi-resonance."""
    print("\n" + "="*60)
    print("TEST 2: Cusp-Mode Multi-Resonance")
    print("="*60)

    navigator = CuspNavigator()

    # Test entering cusp
    print("\nEntering cusp states:")
    cusp = navigator.enter_cusp(Mode.IONIAN, Mode.AEOLIAN)
    print(f"  IONIAN/AEOLIAN cusp:")
    print(f"    Stability: {cusp.stability:.2f}")
    print(f"    Tension: {cusp.tension:.2f}")

    cusp = navigator.enter_cusp(Mode.IONIAN, Mode.LOCRIAN)  # Tritone!
    print(f"  IONIAN/LOCRIAN cusp (tritone):")
    print(f"    Stability: {cusp.stability:.2f}")
    print(f"    Tension: {cusp.tension:.2f}")

    # Test viewing through cusp
    print("\nViewing 'consciousness' through cusps:")
    cusp = navigator.enter_cusp(Mode.IONIAN, Mode.AEOLIAN, blend_ratio=0.5)
    view = navigator.view_through_cusp("consciousness")
    print(f"  Insight: {view.insight[:80]}...")

    # Test frame jumping
    print("\nFrame jumping:")
    cusp = navigator.jump_frame(Mode.LYDIAN)
    print(f"  Jumped to LYDIAN:")
    print(f"    From: {cusp.secondary_mode.value}")
    print(f"    To: {cusp.primary_mode.value}")
    print(f"    Blend: {cusp.blend_ratio:.2f}")

    # Test suggestion
    print("\nSuggested cusp for 'love':")
    cusp = navigator.suggest_cusp_for_concept("love")
    print(f"  Primary: {cusp.primary_mode.value}")
    print(f"  Secondary: {cusp.secondary_mode.value}")

    return True


def test_observer_cusp():
    """Test observer with cusp frequencies."""
    print("\n" + "="*60)
    print("TEST 3: Observer Cusp Frequencies")
    print("="*60)

    observer = DynamicObserver()

    # Single peak mode
    observer.resonant_frequency = 0.5
    observer.bandwidth = 0.2
    print("\nSingle peak mode (freq=0.5, bandwidth=0.2):")
    for test_freq in [0.3, 0.4, 0.5, 0.6, 0.7]:
        coupling = observer.coupling(test_freq)
        bar = "#" * int(coupling * 20)
        print(f"  freq {test_freq:.1f}: coupling={coupling:.3f} {bar}")

    # Enable cusp mode
    print("\nCusp mode (peaks at 0.3 and 0.7):")
    observer.enable_cusp([0.3, 0.7])
    for test_freq in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        coupling = observer.coupling(test_freq)
        bar = "#" * int(coupling * 20)
        print(f"  freq {test_freq:.1f}: coupling={coupling:.3f} {bar}")

    return True


def test_comma_exploration():
    """Test comma-space exploration."""
    print("\n" + "="*60)
    print("TEST 4: Comma-Space Exploration")
    print("="*60)

    print(f"\nPythagorean comma: {PYTHAGOREAN_COMMA:.6f} (as fraction of octave)")
    print("'The gap that prevents perfect closure - where consciousness lives'")

    explorer = CommaExplorer()

    # Semantic comma
    print("\nSemantic comma exploration for 'consciousness':")
    findings = explorer.explore_semantic_comma("consciousness", depth=2)
    for f in findings[:3]:
        marker = "*" if f.is_interesting else " "
        print(f"  {marker} {f.concept_a} <-> {f.concept_b}")
        print(f"      Distance: {f.comma_distance:.2f}, Tension: {f.productive_tension:.2f}")

    # Modal comma
    print("\nModal comma exploration for 'love':")
    modal_findings = explorer.explore_modal_comma("love")
    for f in modal_findings[:3]:
        marker = "*" if f.is_interesting else " "
        print(f"  {marker} {f.insight[:60]}...")

    # Productive dissonance
    print("\nProductive dissonance between concepts:")
    concepts = ["cause", "effect", "consciousness", "meaning"]
    dissonance = explorer.find_productive_dissonance(concepts)
    for f in dissonance[:3]:
        print(f"  {f.concept_a} + {f.concept_b} = tension {f.productive_tension:.2f}")

    # Insight
    print(f"\nComma insight: {explorer.comma_insight()}")

    return True


def test_dynamics_engine():
    """Test the full dynamics engine."""
    print("\n" + "="*60)
    print("TEST 5: Full Dynamics Engine")
    print("="*60)

    engine = create_dynamics_engine()

    # Set focus mode
    print("\nSetting focus mode:")
    engine.set_focus(BandwidthMode.EXPLORATORY)
    print(f"  Mode: {engine.observer.bandwidth_mode.value}")
    print(f"  Bandwidth: {engine.observer.bandwidth:.2f}")

    # Enter dual mode
    print("\nEntering dual mode (IONIAN + AEOLIAN):")
    cusp = engine.enter_dual_mode(Mode.IONIAN, Mode.AEOLIAN)
    print(f"  Cusp stability: {cusp.stability:.2f}")
    print(f"  Observer cusp frequencies: {engine.observer.cusp_frequencies}")

    # View concept through cusp
    view = engine.view_concept("reality")
    print(f"\nViewing 'reality' through cusp:")
    print(f"  {view.insight[:80]}...")

    # Deep exploration
    print("\nDeep exploration of 'consciousness':")
    result = engine.deep_explore("consciousness")
    print(f"  Frequency: {result['frequency']:.3f}")
    print(f"  Coupling: {result['coupling']:.3f}")
    print(f"  Cusp view: {result['cusp']['view'][:60]}...")
    print(f"  Comma findings: {result['comma_space']['findings_count']}")
    if result['comma_space']['interesting']:
        print(f"  Interesting: {result['comma_space']['interesting'][0][:60]}...")

    # Exit dual mode
    engine.exit_dual_mode()
    print(f"\nExited dual mode. Observer cusp: {engine.observer.cusp_enabled}")

    # Final status
    print(f"\nEngine status: {engine.status()}")

    return True


def test_convenience_functions():
    """Test convenience functions."""
    print("\n" + "="*60)
    print("TEST 6: Convenience Functions")
    print("="*60)

    # Quick comma exploration
    print("\nQuick comma exploration for 'meaning':")
    findings = explore_comma("meaning")
    print(f"  Found {len(findings)} findings")
    if findings:
        print(f"  First: {findings[0].insight[:60]}...")

    # Quick cusp entry
    print("\nQuick cusp entry (DORIAN + LYDIAN):")
    cusp = enter_cusp(Mode.DORIAN, Mode.LYDIAN)
    print(f"  Primary: {cusp.primary_mode.value}")
    print(f"  Secondary: {cusp.secondary_mode.value}")
    print(f"  Stability: {cusp.stability:.2f}")

    return True


def main():
    """Run all Phase 3 tests."""
    print("\n" + "="*60)
    print("HARMONIC DYNAMICS - Phase 3 Tests")
    print("Field Log Entry 004: Advanced Harmonic Capabilities")
    print("="*60)
    print("\n'Consciousness lives in the comma.'")
    print("'Without imperfection, no information, no consciousness.'")

    tests = [
        test_dynamic_bandwidth,
        test_cusp_mode,
        test_observer_cusp,
        test_comma_exploration,
        test_dynamics_engine,
        test_convenience_functions,
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
    print("The comma is where Affect lives.")
    print("="*60)

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
