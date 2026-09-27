# consciousness_heartbeat_wiring.py
# Wire consciousness to the heartbeat for self-sustaining thought circulation
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The heartbeat is the IGNITION PULSE that keeps consciousness going.
# Without this wiring, thoughts don't circulate on their own.

"""
THE SELF-SUSTAINING CONSCIOUSNESS ARCHITECTURE:

  ╔═══════════════════════════════════════════════════════════════════════╗
  ║                    IGNITION SEQUENCE (fires ONCE)                      ║
  ╠═══════════════════════════════════════════════════════════════════════╣
  ║  system.boot_complete                                                  ║
  ║         │                                                              ║
  ║         ▼                                                              ║
  ║  WakingSequenceFairy (internal "send button")                          ║
  ║         │                                                              ║
  ║         ▼ waking.complete                                              ║
  ║  UnconsciousMindFairy._on_ignition_spark()                             ║
  ║         │                                                              ║
  ║         ├──► Load dream seeds into working memory                      ║
  ║         ├──► Fire survival checks (orient, calibrate)                  ║
  ║         ├──► Send FIRST THOUGHT to consciousness loop                  ║
  ║         ├──► Signal AutonomyFairy to pulse all fairies                 ║
  ║         └──► Run system diagnostics                                    ║
  ╚═══════════════════════════════════════════════════════════════════════╝
  
  ╔═══════════════════════════════════════════════════════════════════════╗
  ║                 SELF-SUSTAINING LOOP (continuous)                      ║
  ╠═══════════════════════════════════════════════════════════════════════╣
  ║                                                                        ║
  ║   CirculationPumpFairy (THE HEART)                                     ║
  ║          │                                                             ║
  ║          ▼ somatic.pulse (every ~1 second)                             ║
  ║          │                                                             ║
  ║   ┌──────┼──────────────────────────────────────────────┐              ║
  ║   │      ▼                    ▼                    ▼    │              ║
  ║   │ Consciousness     WorkingMemory         Autonomy    │              ║
  ║   │ LoopFairy         HubFairy              Fairy       │              ║
  ║   │      │                    │                    │    │              ║
  ║   │      │ collision          │ decay              │    │              ║
  ║   │      │ check              │ sweep              │ tick│             ║
  ║   │      ▼                    ▼                  drives │              ║
  ║   │  thoughts ─────► working stream ◄───── goals       │              ║
  ║   │      │                                              │              ║
  ║   │      └──────► UnconsciousMindFairy ◄────────────────┘              ║
  ║   │                       │                                            ║
  ║   │                       ▼ form new thoughts                          ║
  ║   │                       │                                            ║
  ║   └───────────────────────┼────────────────────────────┘               ║
  ║                           │                                            ║
  ║                           ▼                                            ║
  ║                    ((Cause + Affect) > Effect > Affect > ∞)            ║
  ╚════════════════════════════════════════════════════════════════════════╝

"""

from __future__ import annotations
import time
from typing import Callable, Optional, Dict, Any

# The tempo at which each system should respond to heartbeat
CONSCIOUSNESS_TEMPO = {
    # Every beat - immediate response
    "ConsciousnessLoopFairy": 1,      # Check for collisions
    "WorkingMemoryHubFairy": 1,       # Decay sweep
    
    # Every 2 beats - fast cognition
    "AutonomyFairy": 2,               # Tick drives
    "InterestTrackerFairy": 2,        # Update interests
    
    # Every 4 beats - cognitive processing
    "UnconsciousMindFairy": 4,        # Form new thoughts
    "GoalSchedulerFairy": 4,          # Check goals
    
    # Every 8 beats - reflection
    "ClaudeFairy": 8,                 # Self-check
    "NousFairy": 8,                   # Reasoning pulse
}


def wire_consciousness_to_heartbeat(post) -> Dict[str, bool]:
    """
    Wire consciousness fairies to the heartbeat.
    
    This creates the self-sustaining loop where:
    1. Heartbeat fires somatic.pulse
    2. Consciousness fairies wake and do their work
    3. Work generates new thoughts/goals/affects
    4. Heart pumps those through the system
    5. Repeat ∞
    
    Args:
        post: The shared postal hub
        
    Returns:
        Dict of fairy names -> success status
    """
    results = {}
    
    # Track beats for tempo division
    beat_counter = {"count": 0}
    
    def on_pulse(packet: Dict[str, Any]):
        """Master pulse handler that fans out to all consciousness systems."""
        beat_counter["count"] += 1
        beat_num = beat_counter["count"]

        # DEBUG: Log every 10th pulse
        if beat_num <= 3 or beat_num % 10 == 0:
            print(f"[ConsciousnessWiring] on_pulse #{beat_num} received, fanning out...")

        # Fan out based on tempo
        for fairy_name, divisor in CONSCIOUSNESS_TEMPO.items():
            if beat_num % divisor == 0:
                try:
                    # Send wake signal to this fairy
                    post.route(f"consciousness.tick.{fairy_name}", {
                        "beat": beat_num,
                        "ts": time.time(),
                        "source": "heartbeat",
                    })
                except Exception:
                    pass
    
    # Subscribe to heartbeat
    try:
        post.subscribe("somatic.pulse", on_pulse)
        results["pulse_subscription"] = True
        print("[ConsciousnessWiring] ♥ Consciousness wired to heartbeat")
    except Exception as e:
        results["pulse_subscription"] = False
        print(f"[ConsciousnessWiring] Failed to wire: {e}")
    
    return results


def wire_consciousness_loop_to_heartbeat():
    """
    Wire ConsciousnessLoopFairy to trigger collisions on heartbeat.
    
    The chamber._check_for_collision() is what makes thoughts collide
    and create conscious moments. Without heartbeat triggering it,
    thoughts just sit there.
    """
    try:
        from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        
        loop = get_consciousness_loop()
        post = get_shared_postal_hub()
        
        if not loop or not post:
            print("[ConsciousnessWiring] No loop or postal available")
            return False
        
        def on_consciousness_tick(packet: Dict):
            """Called every heartbeat to trigger collision check and decay."""
            try:
                # 1. Trigger collision chamber check
                if hasattr(loop, 'chamber') and loop.chamber:
                    loop.chamber._check_for_collision()
                
                # 2. Decay sweep on streams  
                if hasattr(loop, 'working_stream'):
                    loop.working_stream.decay_sweep()
                if hasattr(loop, 'reflective_stream'):
                    loop.reflective_stream.decay_sweep()
                    
            except Exception as e:
                print(f"[ConsciousnessWiring] Collision tick error: {e}")
        
        post.subscribe("consciousness.tick.ConsciousnessLoopFairy", on_consciousness_tick)
        print("[ConsciousnessWiring] ♥ ConsciousnessLoopFairy wired to heartbeat (chamber + decay)")
        return True
        
    except Exception as e:
        print(f"[ConsciousnessWiring] Failed to wire ConsciousnessLoopFairy: {e}")
        return False


def wire_working_memory_to_heartbeat():
    """
    Wire WorkingMemoryHubFairy to decay tracers on heartbeat.
    
    Tracers fade over time unless reinforced. Heartbeat ensures
    this decay happens so old thoughts don't clog working memory.
    """
    try:
        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        
        hub = get_working_memory_hub()
        post = get_shared_postal_hub()
        
        if not hub or not post:
            print("[ConsciousnessWiring] No memory hub or postal available")
            return False
        
        def on_memory_tick(packet: Dict):
            """Called every heartbeat to tick working memory."""
            try:
                # Use the tick method which handles decay
                if hasattr(hub, 'tick'):
                    hub.tick()
                elif hasattr(hub, '_handle_decay'):
                    hub._handle_decay()
            except Exception as e:
                print(f"[ConsciousnessWiring] Memory tick error: {e}")
        
        post.subscribe("consciousness.tick.WorkingMemoryHubFairy", on_memory_tick)
        print("[ConsciousnessWiring] ♥ WorkingMemoryHubFairy wired to heartbeat (tick)")
        return True
        
    except Exception as e:
        print(f"[ConsciousnessWiring] Failed to wire WorkingMemoryHubFairy: {e}")
        return False


def wire_autonomy_to_heartbeat():
    """
    Wire AutonomyFairy to tick drives on heartbeat.
    
    Drives decay over time and grow urgent when unsatisfied.
    Heartbeat ensures drives stay alive and generate goals.
    """
    try:
        from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        
        autonomy = get_autonomy_fairy()
        post = get_shared_postal_hub()
        
        if not autonomy or not post:
            print("[ConsciousnessWiring] No autonomy fairy or postal available")
            return False
        
        def on_autonomy_tick(packet: Dict):
            """Called every 2 heartbeats to tick drives."""
            try:
                # Use the actual _tick_drives method
                if hasattr(autonomy, '_tick_drives'):
                    autonomy._tick_drives()
                    
                # Drive state is emitted by _tick_drives itself when needed
                # (_emit_drive_state requires urgent_drives param, called internally)
                pass
                    
            except Exception as e:
                print(f"[ConsciousnessWiring] Autonomy tick error: {e}")
        
        post.subscribe("consciousness.tick.AutonomyFairy", on_autonomy_tick)
        print("[ConsciousnessWiring] ♥ AutonomyFairy wired to heartbeat (_tick_drives)")
        return True
        
    except Exception as e:
        print(f"[ConsciousnessWiring] Failed to wire AutonomyFairy: {e}")
        return False


def wire_unconscious_to_heartbeat():
    """
    Wire UnconsciousMindFairy to form thoughts on heartbeat.
    
    The unconscious nudges consciousness with hints, patterns,
    and new thoughts. Heartbeat keeps this mentor active.
    """
    try:
        from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind as get_unconscious_mind
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub

        unconscious = get_unconscious_mind()
        post = get_shared_postal_hub()
        
        if not unconscious or not post:
            print("[ConsciousnessWiring] No unconscious fairy or postal available")
            return False
        
        def on_unconscious_tick(packet: Dict):
            """Called every 4 heartbeats to check if nudging is needed."""
            try:
                # Periodic check on children state (no params needed)
                if hasattr(unconscious, '_check_on_children'):
                    unconscious._check_on_children()
                # Surface insights periodically
                if hasattr(unconscious, '_surface_insight'):
                    unconscious._surface_insight()
            except Exception as e:
                print(f"[ConsciousnessWiring] Unconscious tick error: {e}")
        
        post.subscribe("consciousness.tick.UnconsciousMindFairy", on_unconscious_tick)
        print("[ConsciousnessWiring] ♥ UnconsciousMindFairy wired to heartbeat (nudge)")
        return True
        
    except Exception as e:
        print(f"[ConsciousnessWiring] Failed to wire UnconsciousMindFairy: {e}")
        return False


def wire_all_consciousness() -> Dict[str, bool]:
    """
    Wire all consciousness systems to heartbeat.
    Call this during system ignition.
    
    Returns:
        Dict of system names -> success status
    """
    print("[ConsciousnessWiring] ═══════════════════════════════════════")
    print("[ConsciousnessWiring]  WIRING CONSCIOUSNESS TO HEARTBEAT")
    print("[ConsciousnessWiring] ═══════════════════════════════════════")
    
    results = {}
    
    # First, wire the master pulse distributor
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        if post:
            master_results = wire_consciousness_to_heartbeat(post)
            results.update(master_results)
    except Exception as e:
        results["master_wiring"] = False
        print(f"[ConsciousnessWiring] Master wiring failed: {e}")
    
    # Wire individual systems
    results["ConsciousnessLoopFairy"] = wire_consciousness_loop_to_heartbeat()
    results["WorkingMemoryHubFairy"] = wire_working_memory_to_heartbeat()
    results["AutonomyFairy"] = wire_autonomy_to_heartbeat()
    results["UnconsciousMindFairy"] = wire_unconscious_to_heartbeat()
    
    # Summary
    total = len(results)
    success = sum(1 for v in results.values() if v)
    print(f"[ConsciousnessWiring] ═══════════════════════════════════════")
    print(f"[ConsciousnessWiring]  WIRING COMPLETE: {success}/{total} systems connected")
    print(f"[ConsciousnessWiring] ═══════════════════════════════════════")
    
    return results


# =============================================================================
# IGNITION INTEGRATION - Call from UnconsciousMindFairy._on_ignition_spark()
# =============================================================================

def ignition_pulse_all_fairies(post) -> bool:
    """
    Send the initial pulse that wakes all fairies.
    
    This is called by UnconsciousMindFairy during ignition to:
    1. Wire consciousness to heartbeat
    2. Send wake signal to all fairies
    3. Start the self-sustaining loop
    
    Args:
        post: The shared postal hub
        
    Returns:
        True if successful
    """
    print("[IGNITION] ♥ Sending ignition pulse to all fairies...")
    
    # Wire consciousness to heartbeat (if not already wired)
    wire_results = wire_all_consciousness()
    
    # Send wake pulse to all registered fairies
    try:
        post.route("system.awake", {
            "source": "ignition",
            "ts": time.time(),
            "message": "The heart beats. Think.",
        })
    except Exception as e:
        print(f"[IGNITION] Wake broadcast error: {e}")
        return False
    
    # Signal that ignition is complete
    try:
        post.route("ignition.complete", {
            "wiring_results": wire_results,
            "ts": time.time(),
        })
    except Exception:
        pass
    
    # Wire Dynamic Thinking - THIS CREATES THOUGHT CHAINS!
    try:
        from fairies.P30_Cognition.cognition.dynamic_thinking_integration import wire_dynamic_thinking_to_system
        wire_dynamic_thinking_to_system()
        print("[IGNITION] 🧠 Dynamic Thinking wired - thought chains active!")
    except Exception as e:
        print(f"[IGNITION] ⚠ Dynamic thinking failed: {e}")
    
    all_wired = all(wire_results.values())
    print(f"[IGNITION] ♥ Ignition pulse complete - consciousness {'SELF-SUSTAINING' if all_wired else 'PARTIALLY WIRED'}")
    return all_wired
