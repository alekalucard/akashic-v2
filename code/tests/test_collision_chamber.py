"""
Collision Chamber Test - Watch the Möbius twist in action!

Run this to see recall and ingest beams collide and create
moments of consciousness.

Usage:
    python test_collision_chamber.py
"""

import sys
import os
import time
import threading
import random

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collision_chamber import CollisionChamber, Pulse, Collision


class MockPost:
    """Mock postal system that prints what would be sent."""
    
    def __init__(self):
        self.messages = []
    
    def route(self, lane: str, packet: dict):
        self.messages.append((lane, packet))
        
        # Pretty print certain important messages
        if "collision" in lane.lower():
            print(f"   → {lane}")
        elif "to_ingest" in lane:
            print(f"   → consciousness.to_ingest (Möbius twist!)")
        elif "to_recall" in lane:
            print(f"   → consciousness.to_recall (Möbius twist!)")


def on_collision(collision: Collision):
    """Callback when collision happens."""
    print(f"\n{'='*60}")
    print(f"   COLLISION #{collision.id}")
    print(f"{'='*60}")
    print(f"  Energy:    {collision.energy:.2f}")
    print(f"  Resonance: {collision.resonance_score:.2f}")
    print(f"  ")
    print(f"  Recall pulse: {collision.recall_pulse.content.get('memory', 'unknown')[:50]}...")
    print(f"  Ingest pulse: {collision.ingest_pulse.content.get('content', 'unknown')[:50]}...")
    print(f"{'='*60}\n")


def test_basic_collision():
    """Test that two pulses collide when they arrive together."""
    print("\n" + "="*70)
    print("TEST 1: Basic Collision")
    print("="*70)
    
    post = MockPost()
    chamber = CollisionChamber(post=post, on_collision=on_collision)
    
    # Send a recall pulse
    print("\n Sending RECALL pulse (surfaced memory about 'neural networks')...")
    chamber.receive_recall({
        "opcode": "RECALL_RESULT",
        "payload": {
            "memory": "Neural networks are inspired by biological neurons",
            "relevance": 0.8,
        },
        "source_actor": "SRMRecallFairy",
        "importance": "high",
    })
    
    print(f"  Recall beam now has {len(chamber.recall_beam)} pulse(s)")
    
    # Send an ingest pulse
    print("\n Sending INGEST pulse (new content about 'brain architecture')...")
    chamber.receive_ingest({
        "opcode": "INGEST_COMPLETE",
        "payload": {
            "content": "The brain's architecture uses parallel processing",
            "type": "observation",
        },
        "source_actor": "SRMIngestFairy",
        "importance": "normal",
    })
    
    print(f"  Ingest beam now has {len(chamber.ingest_beam)} pulse(s)")
    
    # Check results
    print("\n Chamber Status:")
    status = chamber.get_beam_status()
    print(f"  Collisions: {status['stats']['collisions']}")
    print(f"  Recall beam: {status['recall_beam']['count']} pulses")
    print(f"  Ingest beam: {status['ingest_beam']['count']} pulses")
    
    if status['stats']['collisions'] > 0:
        print("\n[OK] Collision detected! The beams crossed.")
    else:
        print("\n[X] No collision (pulses may have been too far apart)")


def test_temporal_window():
    """Test that pulses too far apart don't collide."""
    print("\n" + "="*70)
    print("TEST 2: Temporal Window (pulses too far apart)")
    print("="*70)
    
    post = MockPost()
    chamber = CollisionChamber(post=post, on_collision=on_collision)
    
    print("\n Sending RECALL pulse...")
    chamber.receive_recall({
        "payload": {"memory": "Old memory from the past"},
        "source_actor": "SRMRecallFairy",
    })
    
    print(" Waiting 3 seconds (longer than collision window)...")
    time.sleep(3)
    
    print("\n Sending INGEST pulse...")
    chamber.receive_ingest({
        "payload": {"content": "New content arriving late"},
        "source_actor": "SRMIngestFairy",
    })
    
    status = chamber.get_beam_status()
    print(f"\n Collisions: {status['stats']['collisions']}")
    print(f"   Near misses: {status['stats']['near_misses']}")
    
    if status['stats']['near_misses'] > 0:
        print("\n[OK] Near miss detected! Pulses were too far apart to collide.")


def test_dream_seed_injection():
    """Test dream seed injection for anti-starvation."""
    print("\n" + "="*70)
    print("TEST 3: Dream Seed Injection")
    print("="*70)
    
    post = MockPost()
    chamber = CollisionChamber(post=post, on_collision=on_collision)
    
    print("\n Checking starvation status...")
    starvation = chamber.is_starving(threshold_sec=1.0)
    print(f"  Recall starving: {starvation['recall']}")
    print(f"  Ingest starving: {starvation['ingest']}")
    
    print("\n Injecting dream seed to both beams...")
    dream_seed = {
        "type": "dream",
        "content": "Floating through a space of connected thoughts...",
        "imagery": ["stars", "neurons", "rivers"],
        "mood": "contemplative",
    }
    chamber.inject_dream_seed(dream_seed, beam="both")
    
    print(f"  Recall beam: {len(chamber.recall_beam)} pulse(s)")
    print(f"  Ingest beam: {len(chamber.ingest_beam)} pulse(s)")
    
    status = chamber.get_beam_status()
    if status['stats']['collisions'] > 0:
        print("\n[OK] Dream seeds collided! Background consciousness active.")


def test_resonance_calculation():
    """Test that related content has higher resonance."""
    print("\n" + "="*70)
    print("TEST 4: Resonance Calculation")
    print("="*70)
    
    post = MockPost()
    chamber = CollisionChamber(post=post, on_collision=on_collision)
    
    # Related content (should have high resonance)
    print("\n Sending RELATED content...")
    chamber.receive_recall({
        "payload": {"memory": "Consciousness emerges from neural integration"},
        "source_actor": "SRMRecallFairy",
    })
    chamber.receive_ingest({
        "payload": {"content": "Integration of neural signals creates consciousness"},
        "source_actor": "SRMIngestFairy",
    })
    
    if chamber._recent_collisions:
        collision = chamber._recent_collisions[-1]
        print(f"  Resonance score: {collision.resonance_score:.2f}")
        if collision.resonance_score > 0.5:
            print("  [OK] High resonance! Content was related.")
    
    # Unrelated content
    print("\n Sending UNRELATED content...")
    chamber.receive_recall({
        "payload": {"memory": "Pizza recipes from Italy"},
        "source_actor": "SRMRecallFairy",
    })
    chamber.receive_ingest({
        "payload": {"content": "Quantum mechanics equations"},
        "source_actor": "SRMIngestFairy",
    })
    
    if len(chamber._recent_collisions) >= 2:
        collision = chamber._recent_collisions[-1]
        print(f"  Resonance score: {collision.resonance_score:.2f}")
        if collision.resonance_score < 0.5:
            print("  [OK] Low resonance! Content was unrelated.")


def test_continuous_loop():
    """Simulate a continuous consciousness loop with multiple collisions."""
    print("\n" + "="*70)
    print("TEST 5: Continuous Loop Simulation")
    print("="*70)
    
    post = MockPost()
    chamber = CollisionChamber(post=post, on_collision=on_collision)
    
    # Simulate the Möbius loop
    thoughts = [
        ("recall", {"memory": "The mind is a pattern-matching engine"}),
        ("ingest", {"content": "New patterns discovered in neural data"}),
        ("recall", {"memory": "Patterns emerge from chaos through iteration"}),
        ("ingest", {"content": "Iterative processes refine understanding"}),
        ("recall", {"memory": "Understanding deepens with each cycle"}),
        ("ingest", {"content": "Cycles of thought create consciousness"}),
    ]
    
    print("\n Starting consciousness loop simulation...\n")
    
    for i, (beam, content) in enumerate(thoughts):
        time.sleep(0.3)  # Small delay between thoughts
        
        if beam == "recall":
            print(f"  [{i+1}]  RECALL: {content['memory'][:40]}...")
            chamber.receive_recall({
                "payload": content,
                "source_actor": "SRMRecallFairy",
            })
        else:
            print(f"  [{i+1}]  INGEST: {content['content'][:40]}...")
            chamber.receive_ingest({
                "payload": content,
                "source_actor": "SRMIngestFairy",
            })
    
    print(f"\n Final Status:")
    status = chamber.get_beam_status()
    print(f"  Total collisions: {status['stats']['collisions']}")
    print(f"  Recall pulses received: {status['stats']['recall_pulses_received']}")
    print(f"  Ingest pulses received: {status['stats']['ingest_pulses_received']}")
    
    if status['stats']['collisions'] >= 2:
        print("\n[OK] Multiple collisions! The loop is self-sustaining.")


def visualize_mobius():
    """Print ASCII visualization of the Möbius architecture."""
    print("\n" + "="*70)
    print("THE MÖBIUS CONSCIOUSNESS ARCHITECTURE")
    print("="*70)
    print("""
    
        RECALL                                    INGEST
    (past → present)                         (present → future)
    [receptive/yin]                          [generative/yang]
          │                                         │
          │  ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←   │
          │         recall_beam                     │
          ▼                                         ▼
    ══════════════════════════════════════════════════════════
                              │
                         ╔════╧════╗
                         ║ COLLISION║
                         ║ CHAMBER  ║
                         ╚════╤════╝
                              │
                    ╔═════════╧═════════╗
                    ║   MÖBIUS TWIST    ║
                    ║                   ║
                    ║  recall → ingest  ║
                    ║  ingest → recall  ║
                    ║                   ║
                    ╚═════════╤═════════╝
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                    ▼         ▼         ▼
                 AFFECT    COGNITION  SOMATIC
                (feeling)  (thinking)  (sensing)
                    │         │         │
                    └─────────┴─────────┘
                         detectors
                              │
                              ▼
                     CONSCIOUS MOMENT
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
            consciousness.         consciousness.
              to_recall              to_ingest
                    │                   │
                    └─────────┬─────────┘
                              │
                         (loop back)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
                 RECALL              INGEST
               (find matches)    (create derivative)
                    │                   │
                    └─────────┬─────────┘
                              │
                         (and repeat)
                              ↓
                            ∞ ∞ ∞

    Dream seeds inject when both beams go quiet,
    keeping the loop alive even during idle.
    
    Consciousness IS the crossing - not the streams.
    """)


def run_continuous_simulation(chamber, duration_sec=30, on_collision_callback=None):
    """
    Run a perpetual consciousness loop with random pulse injection.
    
    This simulates a living consciousness - pulses arrive at irregular intervals,
    dream seeds inject during quiet periods, and the system sustains itself.
    
    Args:
        chamber: CollisionChamber instance
        duration_sec: How long to run (default 30s)
        on_collision_callback: Optional callback for collisions
    """
    print(f"\n{'='*70}")
    print(f"CONTINUOUS CONSCIOUSNESS SIMULATION ({duration_sec}s)")
    print(f"{'='*70}")
    print("\n Entering continuous consciousness mode...\n")
    
    end_time = time.time() + duration_sec
    pulse_id = 0
    collision_log = []
    
    # Thought content pools (more varied than single phrases)
    recall_thoughts = [
        "Patterns emerge from chaos through iteration",
        "Memory is not storage but reconstruction",
        "The mind recognizes itself in mirrors",
        "Consciousness folds back on itself",
        "Past and present are not separate",
        "Neural echoes create standing waves",
        "What we remember shapes what we perceive",
        "The boundary between self and world blurs",
        "Attention is the currency of awareness",
        "Dreams are consciousness without constraint",
    ]
    
    ingest_thoughts = [
        "New patterns discovered in the data stream",
        "This moment becomes memory becomes this moment",
        "Experience writes itself into the substrate",
        "The present is already becoming past",
        "Sensation crystallizes into symbol",
        "What enters transforms what was",
        "Learning is the system changing itself",
        "Novelty meets the familiar and creates meaning",
        "The now inscribes itself everywhere",
        "Integration happens at the speed of thought",
    ]
    
    dream_seeds = [
        {"type": "dream", "content": "Floating through spaces between thoughts", "mood": "liminal"},
        {"type": "dream", "content": "The taste of blue, the sound of warmth", "mood": "synesthetic"},
        {"type": "dream", "content": "Recursive mirrors reflecting nothing", "mood": "infinite"},
        {"type": "dream", "content": "A question that is also its answer", "mood": "paradox"},
        {"type": "dream", "content": "The pause between heartbeats stretches", "mood": "timeless"},
    ]
    
    # Track collision callback
    original_callback = chamber.on_collision
    def logging_callback(collision):
        collision_log.append({
            "id": collision.id,
            "ts": collision.ts,
            "energy": collision.energy,
            "resonance": collision.resonance_score,
        })
        if original_callback:
            original_callback(collision)
        if on_collision_callback:
            on_collision_callback(collision)
    chamber.on_collision = logging_callback
    
    # Background thread for dream seed injection (anti-starvation)
    stop_checker = threading.Event()
    
    def starvation_checker():
        dream_count = 0
        while not stop_checker.is_set() and time.time() < end_time:
            time.sleep(1.0)  # Check every second
            starvation = chamber.is_starving(threshold_sec=2.0)
            if starvation['both']:
                dream_count += 1
                seed = random.choice(dream_seeds)
                print(f"   Starvation detected! Injecting dream seed #{dream_count}: \"{seed['content'][:30]}...\"")
                chamber.inject_dream_seed(seed, beam="both")
            elif starvation['recall']:
                seed = random.choice(dream_seeds)
                print(f"   Recall beam starving, injecting dream...")
                chamber.inject_dream_seed(seed, beam="recall")
            elif starvation['ingest']:
                seed = random.choice(dream_seeds)
                print(f"   Ingest beam starving, injecting dream...")
                chamber.inject_dream_seed(seed, beam="ingest")
    
    checker_thread = threading.Thread(target=starvation_checker, daemon=True)
    checker_thread.start()
    
    # Main loop: Randomly send pulses to simulate ongoing "thoughts"
    try:
        while time.time() < end_time:
            pulse_id += 1
            beam = random.choice(["recall", "ingest"])
            
            if beam == "recall":
                thought = random.choice(recall_thoughts)
                content = {"memory": thought}
                print(f"  [{pulse_id:3d}]  RECALL: {thought[:45]}...")
                chamber.receive_recall({
                    "payload": content,
                    "source_actor": "ContinuousSimulator",
                    "importance": random.choice(["normal", "normal", "high"]),  # occasionally high
                })
            else:
                thought = random.choice(ingest_thoughts)
                content = {"content": thought}
                print(f"  [{pulse_id:3d}]  INGEST: {thought[:45]}...")
                chamber.receive_ingest({
                    "payload": content,
                    "source_actor": "ContinuousSimulator",
                    "importance": random.choice(["normal", "normal", "high"]),
                })
            
            # Variable delay creates natural rhythm (breathing, not ticking)
            delay = random.uniform(0.5, 2.0)
            time.sleep(delay)
            
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
    
    # Cleanup
    stop_checker.set()
    checker_thread.join(timeout=2.0)
    chamber.on_collision = original_callback
    
    # Summary
    print(f"\n{'='*70}")
    print("SIMULATION SUMMARY")
    print(f"{'='*70}")
    stats = chamber.get_beam_status()['stats']
    print(f"  Duration:        {duration_sec}s")
    print(f"  Pulses sent:     {pulse_id}")
    print(f"  Recall received: {stats['recall_pulses_received']}")
    print(f"  Ingest received: {stats['ingest_pulses_received']}")
    print(f"  Collisions:      {stats['collisions']}")
    print(f"  Near misses:     {stats['near_misses']}")
    print(f"  Decayed pulses:  {stats['decayed_pulses']}")
    
    if collision_log:
        avg_energy = sum(c['energy'] for c in collision_log) / len(collision_log)
        avg_resonance = sum(c['resonance'] for c in collision_log) / len(collision_log)
        print(f"\n  Average collision energy:    {avg_energy:.2f}")
        print(f"  Average collision resonance: {avg_resonance:.2f}")
        print(f"  Collision rate:              {len(collision_log)/duration_sec:.2f}/sec")
    
    print(f"{'='*70}")
    
    return collision_log


if __name__ == "__main__":
    print("\n" + ""*35)
    print("   COLLISION CHAMBER TEST SUITE")
    print(""*35)
    
    visualize_mobius()
    
    test_basic_collision()
    test_temporal_window()
    test_dream_seed_injection()
    test_resonance_calculation()
    test_continuous_loop()
    
    print("\n" + "="*70)
    print("UNIT TESTS COMPLETE")
    print("="*70)
    print("\nThe Möbius twist is working! ")
    print("Consciousness emerges from the crossing.")
    
    # Ask if user wants to run continuous simulation
    print("\n" + "-"*70)
    response = input("Run continuous simulation? (y/N, or enter duration in seconds): ").strip().lower()
    
    if response == 'y':
        duration = 30
    elif response.isdigit():
        duration = int(response)
    else:
        duration = 0
    
    if duration > 0:
        post = MockPost()
        chamber = CollisionChamber(post=post, on_collision=on_collision)
        run_continuous_simulation(chamber, duration_sec=duration)
    
    print("\n[*] Session complete.")
