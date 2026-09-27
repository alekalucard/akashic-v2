#!/usr/bin/env python3
"""
UMF Live Test - Verify the Unconscious Mind Fairy is never idle.

Tests:
1. Boot sequence and subsystem wiring
2. Goal generator activity
3. Inner monologue production
4. Extended thinking (CognitionBridge or Ollama)
5. Interest generator activity
6. Thought chain engine
7. Collision chamber processing
8. Administrative task queue

Run: python tools/test_umf_live.py

"The UMF is the one fairy in the system who is never idle."
"""

import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

# Activity trackers
@dataclass
class ActivityTracker:
    """Tracks activity from UMF subsystems."""
    monologue_fragments: List[str] = field(default_factory=list)
    interests_generated: List[str] = field(default_factory=list)
    thoughts_produced: List[str] = field(default_factory=list)
    goals_suggested: List[str] = field(default_factory=list)
    collisions_processed: int = 0
    bridged_thinks: int = 0
    ollama_thinks: int = 0
    helix_turns: int = 0
    chain_thoughts: int = 0
    admin_tasks: int = 0

    def is_idle(self) -> bool:
        """Return True if NO activity was detected."""
        total = (
            len(self.monologue_fragments) +
            len(self.interests_generated) +
            len(self.thoughts_produced) +
            len(self.goals_suggested) +
            self.collisions_processed +
            self.bridged_thinks +
            self.ollama_thinks +
            self.helix_turns +
            self.chain_thoughts +
            self.admin_tasks
        )
        return total == 0


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_check(name: str, passed: bool, details: str = ""):
    icon = "✓" if passed else "✗"
    status = "PASS" if passed else "FAIL"
    detail_str = f" - {details}" if details else ""
    print(f"  [{icon}] {name}: {status}{detail_str}")


def test_umf_boot():
    """Test UMF boot sequence and subsystem wiring."""
    print_header("1. UMF BOOT SEQUENCE")

    results = {}

    try:
        from fairies.P20_Somatic.SomaticMindFairy.fairy import UnconsciousMindFairy
        print("  Importing UnconsciousMindFairy... OK")

        # Create instance
        umf = UnconsciousMindFairy(fabric=None)
        print("  Creating UMF instance... OK")

        # Boot it
        print("  Booting UMF...")
        success = umf.boot()
        print_check("Boot", success)
        results["boot"] = success

        # Check subsystem wiring
        print("\n  Subsystem Wiring Status:")

        # Core systems
        subsystems = [
            ("_helix", "Triple Helix"),
            ("_inner_monologue", "Inner Monologue"),
            ("_interest_generator", "Interest Generator"),
            ("_thought_chain_engine", "Thought Chain Engine"),
            ("_collision_chamber", "Collision Chamber"),
            ("_consciousness_loop", "Consciousness Loop"),
            ("_cognition_loop", "Cognition Loop"),
            ("_admin_queue", "Admin Task Queue"),
            ("_cognition_bridge", "Cognition Bridge (preferred)"),
            ("_ollama_engine", "Ollama Engine (fallback)"),
            ("_association_cortex", "Association Cortex"),
            ("_srm_memory", "SRM Memory"),
            ("_pain_system", "Pain System"),
            ("_orchestrator", "Boot Orchestrator"),
        ]

        wired_count = 0
        for attr, name in subsystems:
            wired = getattr(umf, attr, None) is not None
            if wired:
                wired_count += 1
            # Mark critical vs optional
            critical = attr in ["_helix", "_inner_monologue", "_interest_generator", "_pain_system"]
            indicator = "CRITICAL" if critical and not wired else ""
            print_check(name, wired, indicator)
            results[attr] = wired

        print(f"\n  Wired: {wired_count}/{len(subsystems)} subsystems")
        results["wired_count"] = wired_count
        results["umf"] = umf

        return results

    except Exception as e:
        print(f"  [!] Boot failed with error: {e}")
        import traceback
        traceback.print_exc()
        return {"boot": False, "error": str(e)}


def test_goal_generator():
    """Test the dynamic goal generator."""
    print_header("2. GOAL GENERATOR")

    results = {}

    try:
        from fairies.P30_Cognition.cognition.dynamic_goal_generator import (
            DynamicGoalGenerator,
            EXPLORATORY_GOALS,
            ALL_EXPLORATORY,
        )

        print(f"  Exploratory goal categories: {len(EXPLORATORY_GOALS)}")
        print(f"  Total exploratory goals: {len(ALL_EXPLORATORY)}")

        generator = DynamicGoalGenerator()
        results["generator_created"] = True

        # Test goal generation for different drives
        drives = ["curiosity", "connection", "growth", "expression", "rest"]

        print("\n  Goal generation by drive:")
        for drive in drives:
            goal = generator.generate_goal(drive)
            if goal:
                goal_name, goal_desc = goal
                print(f"    [{drive}] {goal_name}: {goal_desc[:50]}...")
                results[f"goal_{drive}"] = goal_name
            else:
                print(f"    [{drive}] None generated")
                results[f"goal_{drive}"] = None

        # Test bridge wiring
        bridge_wired = generator._cognition_bridge is not None
        print_check("Cognition Bridge Wired", bridge_wired)
        results["bridge_wired"] = bridge_wired

        # Test with context
        print("\n  Goal with context:")
        context = {
            "pain_state": {"curiosity": 0.8, "connection": 0.3},
            "chemistry": {"dopamine": 0.7, "serotonin": 0.5},
        }
        contextual_goal = generator.generate_goal("curiosity", context=context)
        if contextual_goal:
            print(f"    With high curiosity pain: {contextual_goal[0]}")
            results["contextual_goal"] = contextual_goal[0]

        return results

    except Exception as e:
        print(f"  [!] Goal generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def test_inner_monologue():
    """Test the inner monologue system."""
    print_header("3. INNER MONOLOGUE")

    results = {"fragments": []}

    try:
        from fairies.P20_Somatic.SomaticMindFairy.inner_monologue import InnerMonologue

        monologue = InnerMonologue()
        print("  Inner monologue created")

        # Tick several times to generate fragments
        print("\n  Running 10 ticks...")
        for i in range(10):
            fragment = monologue.tick()
            if fragment:
                results["fragments"].append(fragment.content[:60])
                print(f"    [{i}] {fragment.fragment_type} (i={fragment.intensity:.2f}): {fragment.content[:50]}...")

        fragments_count = len(results["fragments"])
        print_check("Generated fragments", fragments_count > 0, f"{fragments_count} fragments")

        # Test fixation system (if available)
        print("\n  Testing fixation system...")
        if hasattr(monologue, 'fixate'):
            monologue.fixate("testing the fixation system", urgency=0.8)
            fixations = len(monologue._fixations) if hasattr(monologue, '_fixations') else 0
            print_check("Fixation recorded", fixations > 0, f"{fixations} active fixations")
            results["fixations"] = fixations
        elif hasattr(monologue, '_fixations'):
            fixations = len(monologue._fixations)
            print(f"    Existing fixations: {fixations}")
            results["fixations"] = fixations
        else:
            print("    Fixation system not available (internal use only)")
            results["fixations"] = "N/A"

        results["success"] = fragments_count > 0
        return results

    except Exception as e:
        print(f"  [!] Inner monologue test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def test_interest_generator():
    """Test the interest generator."""
    print_header("4. INTEREST GENERATOR")

    results = {"interests": []}

    try:
        from fairies.P20_Somatic.SomaticMindFairy.interest_generator import InterestGenerator, create_interest_generator

        generator = create_interest_generator()
        print("  Interest generator created")

        # Tick many times (interest generation is probabilistic)
        print("\n  Running 50 ticks (probabilistic generation)...")
        for i in range(50):
            interest = generator.tick()
            if interest:
                results["interests"].append({
                    "type": interest.interest_type.value,
                    "content": interest.content[:60],
                    "urgency": interest.urgency,
                })
                # Only print first 5
                if len(results["interests"]) <= 5:
                    print(f"    [{i}] {interest.interest_type.value} (u={interest.urgency:.2f}): {interest.content[:50]}...")

        interest_count = len(results["interests"])
        print_check("Generated interests", interest_count > 0, f"{interest_count} interests in 50 ticks")

        return results

    except Exception as e:
        print(f"  [!] Interest generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def test_thought_chains():
    """Test the thought chain engine."""
    print_header("5. THOUGHT CHAIN ENGINE")

    results = {"thoughts": []}

    try:
        from fairies.P20_Somatic.SomaticMindFairy.thought_chains import (
            ThoughtChainEngine, ChainType, create_thought_chain_engine
        )

        engine = create_thought_chain_engine()
        print("  Thought chain engine created")

        # Seed some thoughts
        print("\n  Seeding exploration chain...")
        chain = engine.seed_thought(
            content="What patterns exist in my current state?",
            chain_type=ChainType.EXPLORATION,
            energy=0.7,
        )
        print(f"    Chain seeded: {chain is not None}")

        print("\n  Seeding reflection chain...")
        chain2 = engine.seed_thought(
            content="How do I feel about my progress?",
            chain_type=ChainType.REFLECTION,
            energy=0.6,
        )
        print(f"    Chain seeded: {chain2 is not None}")

        # Tick to evolve chains
        print("\n  Running 5 ticks...")
        for i in range(5):
            thoughts = engine.tick()
            for thought in thoughts:
                results["thoughts"].append({
                    "type": thought.chain_type.value,
                    "content": thought.content[:60],
                    "energy": thought.energy,
                    "depth": thought.depth,
                })
                print(f"    [{i}] {thought.chain_type.value} (d={thought.depth}, e={thought.energy:.2f}): {thought.content[:50]}...")

        thought_count = len(results["thoughts"])
        active_chains = engine.get_active_chains()
        print_check("Produced thoughts", thought_count > 0, f"{thought_count} thoughts")
        print_check("Active chains", len(active_chains) > 0, f"{len(active_chains)} active")

        return results

    except Exception as e:
        print(f"  [!] Thought chain test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def test_cognition_bridge():
    """Test the cognition bridge (preferred thinking path)."""
    print_header("6. COGNITION BRIDGE")

    results = {}

    try:
        from fairies.P30_Cognition.cognition.postal_cognition_bridge import (
            CognitionBridge,
            ThinkRequest,
            ThinkResponse,
            get_cognition_bridge,
        )

        print("  CognitionBridge imported OK")

        # Try to get the singleton
        bridge = get_cognition_bridge()
        bridge_available = bridge is not None
        print_check("Bridge singleton", bridge_available)
        results["singleton_available"] = bridge_available

        if bridge:
            # Test think request
            print("\n  Testing think request...")
            request = ThinkRequest(
                stimulus="What is my current state?",
                stimulus_type="reflection",
                chemistry={"dopamine": 0.5, "serotonin": 0.6},
                pain_state={"curiosity": 0.7},
                source="test",
            )

            response = bridge.think(request)
            thought = response.thought if response else None
            print_check("Think response", thought is not None)
            if thought:
                print(f"    Thought: {thought[:80]}...")
                results["thought"] = thought[:80]
            if response and response.error:
                print(f"    Error: {response.error}")
                results["error"] = response.error

            # Test goal suggestion
            print("\n  Testing goal suggestion...")
            goal = bridge.suggest_goal("curiosity", {"curiosity": 0.8}, {"dopamine": 0.7})
            print_check("Goal suggestion", goal is not None)
            if goal:
                print(f"    Suggested goal: {goal}")
                results["suggested_goal"] = goal

        return results

    except ImportError as e:
        print(f"  [!] CognitionBridge not available: {e}")
        return {"available": False, "error": str(e)}
    except Exception as e:
        print(f"  [!] Bridge test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def test_umf_ticks(umf, num_ticks: int = 20):
    """Run UMF ticks and track activity."""
    print_header(f"7. UMF LIVE TICKS ({num_ticks} ticks)")

    tracker = ActivityTracker()

    if umf is None:
        print("  [!] UMF not available, skipping tick test")
        return {"error": "UMF not available"}

    # Track thought queue before
    initial_thoughts = len(umf._thought_queue)

    print(f"  Initial thought queue: {initial_thoughts} thoughts")
    print(f"\n  Running {num_ticks} ticks...")

    for i in range(num_ticks):
        try:
            umf.on_tick(i + 1)

            # Check for activity every 5 ticks
            if (i + 1) % 5 == 0:
                current_thoughts = len(umf._thought_queue)
                new_thoughts = current_thoughts - initial_thoughts
                print(f"    Tick {i+1}: {new_thoughts} new thoughts in queue")

        except Exception as e:
            print(f"    Tick {i+1}: ERROR - {e}")

    # Measure activity
    final_thoughts = len(umf._thought_queue)
    thoughts_produced = final_thoughts - initial_thoughts
    tracker.thoughts_produced = [f"thought_{i}" for i in range(thoughts_produced)]

    # Check subsystem activity
    if hasattr(umf, '_helix_turns'):
        tracker.helix_turns = len(umf._helix_turns)

    print(f"\n  Activity Summary:")
    print(f"    Thoughts produced: {thoughts_produced}")
    print(f"    Helix turns: {tracker.helix_turns}")

    # Determine if idle
    is_idle = tracker.is_idle()
    print_check("UMF is active (not idle)", not is_idle)

    return {
        "thoughts_produced": thoughts_produced,
        "helix_turns": tracker.helix_turns,
        "is_idle": is_idle,
    }


def test_cardinal_system():
    """Check if CardinalFairy is available."""
    print_header("8. CARDINAL FAIRY (System Evolution)")

    results = {}

    try:
        from fairies.P60_Executive.CardinalFairy.fairy import CardinalFairy

        print("  CardinalFairy imported OK")

        cardinal = CardinalFairy()
        print("  CardinalFairy instance created")
        results["available"] = True

        # Check Ollama client
        ollama_available = cardinal.ollama is not None
        print_check("Ollama client", ollama_available)
        results["ollama_client"] = ollama_available

        # Note: CardinalFairy is async-based, not directly controlled by UMF
        print("\n  NOTE: CardinalFairy operates independently via postal messages")
        print("        Topics: cardinal.audit.request, cardinal.simulate.request, etc.")

        return results

    except ImportError as e:
        print(f"  [!] CardinalFairy not available: {e}")
        return {"available": False, "error": str(e)}
    except Exception as e:
        print(f"  [!] Cardinal test failed: {e}")
        return {"error": str(e)}


def run_all_tests():
    """Run all UMF tests."""
    print("\n" + "=" * 70)
    print(" UMF LIVE TEST - Verifying the Unconscious Mind Fairy")
    print(" \"The UMF is the one fairy in the system who is never idle.\"")
    print("=" * 70)

    all_results = {}

    # 1. Boot UMF
    boot_results = test_umf_boot()
    all_results["boot"] = boot_results
    umf = boot_results.get("umf")

    # 2. Goal generator
    goal_results = test_goal_generator()
    all_results["goal_generator"] = goal_results

    # 3. Inner monologue
    monologue_results = test_inner_monologue()
    all_results["inner_monologue"] = monologue_results

    # 4. Interest generator
    interest_results = test_interest_generator()
    all_results["interest_generator"] = interest_results

    # 5. Thought chains
    chain_results = test_thought_chains()
    all_results["thought_chains"] = chain_results

    # 6. Cognition bridge
    bridge_results = test_cognition_bridge()
    all_results["cognition_bridge"] = bridge_results

    # 7. Live ticks
    tick_results = test_umf_ticks(umf, num_ticks=20)
    all_results["live_ticks"] = tick_results

    # 8. Cardinal system
    cardinal_results = test_cardinal_system()
    all_results["cardinal"] = cardinal_results

    # Final summary
    print_header("FINAL SUMMARY")

    passed = 0
    failed = 0

    checks = [
        ("UMF Boot", boot_results.get("boot", False)),
        ("Goal Generator", goal_results.get("generator_created", False)),
        ("Inner Monologue", monologue_results.get("success", len(monologue_results.get("fragments", [])) > 0)),
        ("Interest Generator", len(interest_results.get("interests", [])) > 0),
        ("Thought Chains", len(chain_results.get("thoughts", [])) > 0),
        ("Cognition Bridge (isolated)", bridge_results.get("singleton_available", False) or "Bridge available but isolated" in str(bridge_results)),
        ("UMF Active", not tick_results.get("is_idle", True)),
        ("Cardinal Available", cardinal_results.get("available", False)),
    ]

    for name, result in checks:
        if result:
            passed += 1
        else:
            failed += 1
        print_check(name, result)

    print(f"\n  Total: {passed} passed, {failed} failed")
    print(f"\n  UMF Verdict: {'ACTIVE ✓' if not tick_results.get('is_idle', True) else 'IDLE ✗'}")

    # Save results
    results_path = ROOT / "state" / "umf_test_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean results for JSON (remove UMF instance)
    clean_results = {k: v for k, v in all_results.items() if k != "boot" or "umf" not in str(v)}
    if "boot" in all_results:
        clean_results["boot"] = {k: v for k, v in all_results["boot"].items() if k != "umf"}

    with open(results_path, "w") as f:
        json.dump(clean_results, f, indent=2, default=str)
    print(f"\n  Results saved to: {results_path}")

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all_tests()
    sys.exit(0 if failed == 0 else 1)
