"""
SomaticMind Demo - Show it actually doing something useful.

Run this to see SomaticMind in action:
  python -m fairies.P00_Autonomic.SomaticMind.demo
"""

import sys
import time
from pathlib import Path

# Add parent paths for imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.SomaticMind import SomaticMind, SomaticMode, get_somatic_mind


def demo_preboot_mode():
    """Demo pre-boot capabilities (training wheels)."""
    print("\n" + "=" * 60)
    print("DEMO: Pre-Boot Mode (Training Wheels)")
    print("=" * 60)

    sm = SomaticMind()

    # Check we're in pre-boot mode
    print(f"\nMode: {sm.mode.value}")
    print(f"Has direct links: {sm.has_direct_links}")

    # Use pre-boot capabilities
    print("\n--- Pre-boot Vitals ---")
    vitals = sm.preboot_vitals()
    for key, val in vitals.items():
        print(f"  {key}: {val}")

    # Heartbeat
    print("\n--- Pre-boot Heartbeat ---")
    beat = sm.preboot_heartbeat()
    if beat:
        print(f"  Beat #{beat.beat_number} at {beat.timestamp}")

    # Memory recall
    print("\n--- Pre-boot Memory Recall ---")
    cards = sm.preboot_recall("bootstrap")
    print(f"  Found {len(cards)} bootstrap cards")

    # Thought routing
    print("\n--- Pre-boot Cognition ---")
    thought_id = sm.preboot_think("System starting up...")
    print(f"  Submitted thought: {thought_id}")

    return sm


def demo_boot_transition(sm: SomaticMind):
    """Demo the boot transition (training wheels off)."""
    print("\n" + "=" * 60)
    print("DEMO: Boot Transition")
    print("=" * 60)

    print(f"\nBefore boot:")
    print(f"  Mode: {sm.mode.value}")
    print(f"  Has direct links: {sm.has_direct_links}")

    # Boot the system
    print("\nBooting...")
    sm.boot()

    print(f"\nAfter boot:")
    print(f"  Mode: {sm.mode.value}")
    print(f"  Has direct links: {sm.has_direct_links}")

    # Try using pre-boot capabilities (should fail)
    print("\n--- Trying Pre-boot after Boot ---")
    vitals = sm.preboot_vitals()
    print(f"  Result: {vitals}")


def demo_observation_learning():
    """Demo observation and learning capabilities."""
    print("\n" + "=" * 60)
    print("DEMO: Observation and Learning")
    print("=" * 60)

    sm = get_somatic_mind()

    # Simulate some observations
    print("\n--- Recording Observations ---")

    # Normal health check
    sm.observe('health', 'P00.DirectoryFairy', {'cpu': 15, 'memory': 45}, severity=0)
    print("  Recorded health observation")

    # A change
    sm.observe('change', 'P30.ConsciousnessLoop', {'tick_rate': 1.0}, severity=0)
    print("  Recorded change observation")

    # An error
    sm.observe('error', 'P30.ConsciousnessLoop', {'message': 'Tick timeout'}, severity=2)
    print("  Recorded error observation (severity=2)")

    # Check for correlations
    print("\n--- Status ---")
    status = sm.status()
    for key, val in status.items():
        print(f"  {key}: {val}")

    # Check proposed fixes
    print("\n--- Proposed Fixes ---")
    fixes = sm.get_proposed_fixes()
    if fixes:
        for fix in fixes:
            print(f"  {fix['id']}: {fix['description']} (conf={fix['confidence']:.2f})")
    else:
        print("  No fixes proposed yet")

    return sm


def demo_emergency_mode(sm: SomaticMind):
    """Demo emergency mode (re-enable training wheels)."""
    print("\n" + "=" * 60)
    print("DEMO: Emergency Mode")
    print("=" * 60)

    print(f"\nCurrent mode: {sm.mode.value}")
    print(f"Has direct links: {sm.has_direct_links}")

    # Enter emergency mode
    print("\nEntering emergency mode...")
    sm.enter_emergency_mode()

    print(f"\nAfter emergency entry:")
    print(f"  Mode: {sm.mode.value}")
    print(f"  Has direct links: {sm.has_direct_links}")

    # Now we can use pre-boot capabilities again!
    print("\n--- Emergency Vitals ---")
    vitals = sm.preboot_vitals()
    for key, val in vitals.items():
        if isinstance(val, dict):
            print(f"  {key}:")
            for k2, v2 in val.items():
                print(f"    {k2}: {v2}")
        else:
            print(f"  {key}: {val}")

    # Exit emergency mode
    print("\nExiting emergency mode...")
    sm.exit_emergency_mode()
    print(f"Mode: {sm.mode.value}")
    print(f"Has direct links: {sm.has_direct_links}")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("SOMATIC MIND - DEMONSTRATION")
    print("The system administrator that actually helps.")
    print("=" * 60)

    try:
        # Demo 1: Pre-boot mode
        sm = demo_preboot_mode()

        # Demo 2: Boot transition
        demo_boot_transition(sm)

        # Demo 3: Observation and learning
        sm = demo_observation_learning()

        # Demo 4: Emergency mode
        demo_emergency_mode(sm)

        # Final status
        print("\n" + "=" * 60)
        print("FINAL STATUS")
        print("=" * 60)
        sm.shutdown()
        print("\nSomaticMind shutdown complete.")
        print("It's no longer a paperweight - it actually does something!")

    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
