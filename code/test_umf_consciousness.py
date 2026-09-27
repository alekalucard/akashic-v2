"""
Test UnconsciousMindFairy wired to Consciousness System

Shows:
1. UMF wired to ConsciousnessLoop
2. Heartbeat-driven on_tick()
3. Collision processing through Triple Helix
4. Thought injection back into streams
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
from consciousness import ConsciousnessLoop, CollisionChamber
from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy as UnconsciousMindFairy


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    print_section("UMF + CONSCIOUSNESS INTEGRATION TEST")

    # Create infrastructure
    print("\n[1] Booting infrastructure...")
    fabric = TensorFabric()

    # Create directory
    directory = DirectoryFairy(fabric)
    directory.on_boot()
    set_directory(directory)
    print("    Directory: OK")

    # Create consciousness system
    print("\n[2] Creating consciousness system...")
    chamber = CollisionChamber()
    loop = ConsciousnessLoop(tick_interval=0.1)  # 10Hz for testing
    loop.set_chamber(chamber)
    print("    CollisionChamber: OK")
    print("    ConsciousnessLoop: OK")

    # Create UMF
    print("\n[3] Creating UnconsciousMindFairy...")
    umf = UnconsciousMindFairy(fabric)
    umf.on_boot()
    print("    UMF: OK")

    # Wire UMF to consciousness
    print("\n[4] Wiring UMF to consciousness...")
    wired = umf.wire_to_consciousness(loop, chamber)
    print(f"    Wired: {'OK' if wired else 'FAILED'}")

    # Start the consciousness loop
    print("\n[5] Starting consciousness loop...")
    loop.start()
    print("    Loop: RUNNING")

    # Let UMF run through some ticks
    print_section("CONSCIOUSNESS TICKING")
    print("    Letting consciousness tick for 2 seconds...")
    time.sleep(2)

    status = umf.consciousness_status()
    print(f"\n    Consciousness Status:")
    print(f"    - Wired: {status['wired']}")
    print(f"    - Loop running: {status['loop_running']}")
    print(f"    - Loop beats: {status['loop_beats']}")
    print(f"    - Chamber collisions: {status['chamber_collisions']}")

    # Send some pulses to trigger collisions
    print_section("TRIGGERING COLLISIONS")
    print("    Sending Recall and Ingest pulses...")

    for i in range(3):
        chamber.receive_recall(
            content={"memory": f"Past pattern {i}", "relevance": 0.8},
            source="MemoryFairy",
        )
        chamber.receive_ingest(
            content={"perception": f"New observation {i}", "novelty": 0.7},
            source="SensoryFairy",
        )

    # Wait for processing
    print("    Waiting for helix processing...")
    time.sleep(1)

    # Check UMF state
    print_section("UMF STATE AFTER COLLISIONS")

    # Helix status
    helix = umf.helix_status()
    print(f"    Helix turns: {helix.get('turns', 0)}")
    print(f"    Decision weights: L={helix['decision_weights']['logic']:.0%} E={helix['decision_weights']['emotion']:.0%} P={helix['decision_weights']['paradox']:.0%}")

    # Recent thoughts
    thoughts = umf.get_thoughts(5)
    print(f"\n    Recent thoughts: {len(thoughts)}")
    for t in thoughts[-3:]:
        print(f"      - [{t.get('type', '?')}] {t.get('thought', '')[:50]}...")

    # Consciousness streams
    print(f"\n    Working stream: {len(loop.working)} thoughts")
    print(f"    Reflective stream: {len(loop.reflective)} thoughts")

    # Test thought injection
    print_section("THOUGHT INJECTION")
    print("    Injecting thought into consciousness...")
    umf.inject_thought(
        content="A deliberate thought from the unconscious",
        stream="working",
        confidence=0.9,
    )
    print(f"    Working stream now: {len(loop.working)} thoughts")

    # Final status
    print_section("FINAL STATUS")
    loop_status = loop.status()
    print(f"    Loop beats: {loop_status['beat_count']}")
    print(f"    Collisions triggered: {loop_status['collisions_triggered']}")
    print(f"    Chamber collisions: {chamber.stats['collisions']}")

    full = umf.full_status()
    print(f"\n    UMF State: {full['fairy']['state']}")
    print(f"    UMF Thoughts: {full['thoughts']}")
    print(f"    Helix active: {full['helix']['active']}")

    # Shutdown
    print_section("SHUTDOWN")
    loop.stop()
    umf.on_shutdown()
    directory.on_shutdown()
    print("    Clean shutdown complete.")

    print("\n" + "="*60)
    print("  TEST COMPLETE - UMF + Consciousness integrated")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
