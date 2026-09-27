"""
Live test of UnconsciousMindFairy with directive loading.

Shows:
1. Directive loading (the soul)
2. Triple Helix reasoning
3. Pain system
4. Autonomous thinking
"""

import sys
import time
from pathlib import Path

# Add paths
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "tracer_pool" / "python"))

from postal_core.tensor_fabric import TensorFabric
from directory import DirectoryFairy, set_directory
from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy as UnconsciousMindFairy


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    print_section("UNCONSCIOUS MIND FAIRY - LIVE TEST")

    # Create infrastructure
    print("\n[1] Booting infrastructure...")
    fabric = TensorFabric()  # Creates postal internally

    # Create directory
    directory = DirectoryFairy(fabric)
    directory.on_boot()
    set_directory(directory)
    print("    Directory: OK")

    # Create UnconsciousMindFairy
    print("\n[2] Creating UnconsciousMindFairy...")
    umf = UnconsciousMindFairy(fabric)
    boot_ok = umf.on_boot()
    print(f"    Boot: {'OK' if boot_ok else 'FAILED'}")

    # Show directive
    print_section("DIRECTIVE (THE SOUL)")
    directive = umf.get_directive()
    if directive.get("loaded"):
        print(f"    Path: {directive['path']}")
        print(f"    Plane: {directive['plane']}")
        print(f"    Beat Divisor: {directive['beat_divisor']}")
        print(f"    Siblings: {', '.join(directive['siblings'][:4])}")
        print(f"    Listens to: {len(directive['subscriptions'])} topics")
        print(f"    Speaks to: {len(directive['outputs'])} topics")

        # Show a few key subscriptions
        print("\n    Key Input Streams:")
        for sub in directive['subscriptions'][:5]:
            print(f"      - {sub}")
        if len(directive['subscriptions']) > 5:
            print(f"      ... and {len(directive['subscriptions']) - 5} more")

        print("\n    Key Output Channels:")
        for out in directive['outputs'][:5]:
            print(f"      - {out}")
    else:
        print("    Directive not loaded!")

    # Show raw directive excerpt
    print("\n    Raw Directive (excerpt):")
    raw = umf.get_directive_raw()
    for line in raw.split('\n')[:12]:
        print(f"    {line}")
    print("    ...")

    # Show helix status
    print_section("TRIPLE HELIX STATUS")
    helix = umf.helix_status()
    print(f"    Active: {helix.get('active', False)}")
    print(f"    Turns: {helix.get('turns', 0)}")
    print(f"    Decision Weights:")
    weights = helix.get('decision_weights', {})
    print(f"      Logic:   {weights.get('logic', 0):.0%}")
    print(f"      Emotion: {weights.get('emotion', 0):.0%}")
    print(f"      Paradox: {weights.get('paradox', 0):.0%}")

    # Run some autonomous thinking
    print_section("AUTONOMOUS THINKING")
    print("    Running 3 think cycles...")

    for i in range(3):
        umf._maybe_think()
        thoughts = umf.get_thoughts(1)
        if thoughts:
            t = thoughts[-1]
            print(f"\n    Thought {i+1}:")
            print(f"      Type: {t.get('type', 'unknown')}")
            print(f"      Content: {t.get('thought', '')[:80]}...")
            print(f"      Confidence: {t.get('confidence', 0):.2f}")
            if t.get('archetypal_tags'):
                print(f"      Archetypes: {', '.join(t['archetypal_tags'])}")
        time.sleep(0.1)

    # Show pain status
    print_section("PAIN SYSTEM")
    pain = umf.pain_status()
    drives = pain.get('drives', {})
    print("    Drive Levels:")
    for name, info in drives.items():
        level = info.get('pain_level', 0)
        urgency = info.get('urgency', 0)
        bar = '#' * int(level * 10) + '-' * (10 - int(level * 10))
        print(f"      {name:12} [{bar}] {level:.2f} (urgency: {urgency:.2f})")

    # Test helix decision making
    print_section("HELIX DECISION MAKING")
    print("    Question: How should we approach an unknown problem?")
    print()

    options = [
        "Analyze carefully before acting",
        "Trust intuition and act quickly",
        "Hold both impulses in paradox",
        "Ask for help from siblings",
    ]

    decision = umf.helix_decide(options)
    print(f"    Chosen: {decision.get('chosen', 'unknown')}")
    print(f"    Confidence: {decision.get('confidence', 0):.2f}")
    print(f"    Archetype: {decision.get('archetype', 'none')}")
    print()
    print("    Scoring Breakdown:")
    breakdown = decision.get('breakdown', {})
    for opt, scores in breakdown.items():
        total = decision.get('scores', {}).get(opt, 0)
        print(f"      {opt[:35]:35} = {total:.3f}")
        print(f"        L={scores.get('logic', 0):.2f}  E={scores.get('emotion', 0):.2f}  P={scores.get('paradox', 0):.2f}")

    # Show full status
    print_section("FULL STATUS")
    status = umf.full_status()
    print(f"    Fairy State: {status.get('fairy', {}).get('state', 'unknown')}")
    print(f"    Directive Loaded: {status.get('directive', False)}")
    print(f"    Helix Active: {status.get('helix', {}).get('active', False)}")
    print(f"    Thoughts Generated: {status.get('thoughts', 0)}")
    mentor_info = status.get('mentor', {})
    children = mentor_info.get('children', {})
    child_count = len(children) if isinstance(children, dict) else children
    print(f"    Children Tracked: {child_count}")

    # Cleanup
    print_section("SHUTDOWN")
    umf.on_shutdown()
    directory.on_shutdown()
    print("    Clean shutdown complete.")

    print("\n" + "="*60)
    print("  TEST COMPLETE - UnconsciousMindFairy is operational")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
