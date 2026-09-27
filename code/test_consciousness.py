"""
Test the V2 Consciousness System

Shows:
1. ConsciousnessLoop heartbeat
2. Dual thought streams (working + reflective)
3. CollisionChamber with Recall/Ingest beams
4. Collisions creating bound thoughts
"""

import sys
import time
from pathlib import Path

# Add paths
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

from consciousness import (
    ConsciousnessLoop,
    CollisionChamber,
    Collision,
)


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    print_section("V2 CONSCIOUSNESS SYSTEM TEST")

    # Track collisions
    collisions_received = []

    def on_collision(collision: Collision):
        collisions_received.append(collision)
        print(f"  [COLLISION #{collision.id}] Energy={collision.energy:.2f} Resonance={collision.resonance:.2f}")
        print(f"    Recall: {collision.recall_pulse.source} -> {str(collision.recall_pulse.content)[:40]}...")
        print(f"    Ingest: {collision.ingest_pulse.source} -> {str(collision.ingest_pulse.content)[:40]}...")

    # Create collision chamber
    print("\n[1] Creating CollisionChamber...")
    chamber = CollisionChamber(on_collision=on_collision)
    print("    Chamber: OK")

    # Create consciousness loop
    print("\n[2] Creating ConsciousnessLoop...")
    loop = ConsciousnessLoop(tick_interval=0.1)  # Fast for testing
    loop.set_chamber(chamber)
    print("    Loop: OK")

    # Start the loop
    print("\n[3] Starting consciousness loop...")
    loop.start()
    print("    Loop running!")

    # Add some thoughts to the streams
    print_section("THOUGHT STREAMS")
    print("    Adding thoughts to working and reflective streams...")

    for i in range(5):
        loop.add_thought(
            content=f"Working thought {i}: processing task",
            source="TaskFairy",
            stream="working",
            confidence=0.8,
        )
        loop.add_thought(
            content=f"Reflective thought {i}: consolidating memory",
            source="MemoryFairy",
            stream="reflective",
            confidence=0.7,
        )

    print(f"    Working stream: {len(loop.working)} thoughts")
    print(f"    Reflective stream: {len(loop.reflective)} thoughts")

    # Let the loop process
    print("\n    Waiting for collisions (2 seconds)...")
    time.sleep(2)

    # Show stream status
    print(f"\n    After processing:")
    print(f"    Working stream: {len(loop.working)} thoughts")
    print(f"    Reflective stream: {len(loop.reflective)} thoughts")
    print(f"    Collisions from streams: {loop.collisions_triggered}")

    # Test the collision chamber directly
    print_section("COLLISION CHAMBER - Recall/Ingest Beams")
    print("    Sending pulses to Recall and Ingest beams...")

    # Send some recall pulses (memories)
    for i in range(3):
        chamber.receive_recall(
            content={"memory": f"Past event {i}", "emotion": "nostalgia"},
            source="RecallFairy",
            importance="normal",
        )

    # Send some ingest pulses (new content)
    for i in range(3):
        chamber.receive_ingest(
            content={"perception": f"New input {i}", "salience": 0.8},
            source="IngestFairy",
            importance="high",
        )

    print(f"\n    Chamber status:")
    status = chamber.status()
    print(f"    Recall beam: {status['recall_beam_size']} pulses")
    print(f"    Ingest beam: {status['ingest_beam_size']} pulses")
    print(f"    Total collisions: {status['collision_count']}")

    # Let it process
    print("\n    Waiting for chamber collisions (1 second)...")
    time.sleep(1)

    # Final status
    print_section("FINAL STATUS")

    loop_status = loop.status()
    print(f"    Loop running: {loop_status['running']}")
    print(f"    Beat count: {loop_status['beat_count']}")
    print(f"    Ticks processed: {loop_status['ticks_processed']}")
    print(f"    Collisions triggered: {loop_status['collisions_triggered']}")
    print(f"    Handlers registered: {loop_status['handlers_registered']}")

    chamber_status = chamber.status()
    print(f"\n    Chamber collisions: {chamber_status['collision_count']}")
    print(f"    Recall received: {chamber_status['stats']['recall_received']}")
    print(f"    Ingest received: {chamber_status['stats']['ingest_received']}")
    print(f"    Pulses decayed: {chamber_status['stats']['decayed']}")

    # Show recent collisions
    recent = chamber.recent_collisions(5)
    if recent:
        print(f"\n    Recent collisions: {len(recent)}")
        for c in recent[-3:]:
            print(f"      #{c['collision_id']}: {c['recall']['source']} x {c['ingest']['source']} (E={c['energy']:.2f})")

    # Shutdown
    print_section("SHUTDOWN")
    loop.stop()
    print("    Loop stopped.")

    print("\n" + "="*60)
    print("  TEST COMPLETE - Consciousness system operational")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
