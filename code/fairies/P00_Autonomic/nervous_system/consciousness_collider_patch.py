"""
Consciousness Loop Integration Patch

This file contains the methods to add to ConsciousnessLoopFairy to integrate
the CollisionChamber (Möbius crossing point).

USAGE:
Add these imports and methods to consciousness_loop_fairy.py

Or run:
    from consciousness_collider_patch import patch_consciousness_loop
    patch_consciousness_loop(ConsciousnessLoopFairy)
"""

from __future__ import annotations
import time
import os
import json
import random
from typing import Optional, Dict, Any, List


def patch_consciousness_loop(cls):
    """
    Patch a ConsciousnessLoopFairy class to add collision chamber support.
    
    Usage:
        from consciousness_collider_patch import patch_consciousness_loop
        patch_consciousness_loop(ConsciousnessLoopFairy)
    """
    
    # Store original __init__
    original_init = cls.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        
        # Import here to avoid circular imports
        from collision_chamber import CollisionChamber
        
        # Create the collision chamber
        self.chamber = CollisionChamber(
            post=self.post,
            on_collision=self._on_collision_callback
        )
        
        # Dream seed loading
        self._dream_seeds = []
        self._load_dream_seeds()
        
        # Starvation check interval
        self._last_starvation_check = time.time()
        self._starvation_check_interval = 3.0  # seconds
        
        print(f"[{self.ACTOR_NAME}]  Collision chamber initialized", flush=True)
    
    def _on_collision_callback(self, collision):
        """Called when a collision occurs in the chamber."""
        try:
            # Log the collision
            print(f"[{self.ACTOR_NAME}]  COLLISION #{collision.id} "
                  f"energy={collision.energy:.2f} resonance={collision.resonance_score:.2f}",
                  flush=True)

            collision_dict = collision.to_dict()

            # Add to working stream (collisions are active conscious moments)
            self.working_stream.append({
                "type": "consciousness_collision",
                "collision": collision_dict,
                "route_to": "working",
            })

            # ═══════════════════════════════════════════════════════════════
            # FIX 2026-03-07 (Nous): Route to consciousness.collision topic
            # Without this, InterestScheduler and other postal subscribers
            # never see collisions from the main chamber. PAI-sourced
            # collisions were going unprocessed because only working_stream
            # was populated, not the postal topic.
            # ═══════════════════════════════════════════════════════════════
            if self.post:
                self.post.route("consciousness.collision", {
                    "opcode": "COLLISION",
                    "payload": collision_dict,
                })

            # Notify shadow
            if self.shadow:
                self.shadow.on_thought_emitted("working")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision callback error: {e}", flush=True)
    
    def _subscribe_to_collision_sources(self):
        """
        Subscribe to the lanes that feed the collision chamber.
        
        RECALL → chamber.receive_recall
        INGEST → chamber.receive_ingest
        """
        # Sources that feed RECALL beam
        recall_sources = [
            "srm.recall.result",      # Direct recall results
            "memory.recall.result",   # Memory subsystem recalls
            "recall.complete",        # Generic recall completion
        ]
        
        # Sources that feed INGEST beam
        ingest_sources = [
            "srm.ingest.complete",    # Direct ingest completions
            "memory.ingest.complete", # Memory subsystem ingests
            "ingest.complete",        # Generic ingest completion
        ]
        
        for source in recall_sources:
            try:
                self.post.subscribe(source, self._on_recall_for_chamber)
                print(f"[{self.ACTOR_NAME}]  Subscribed to {source} → recall beam", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe {source}: {e}", flush=True)
        
        for source in ingest_sources:
            try:
                self.post.subscribe(source, self._on_ingest_for_chamber)
                print(f"[{self.ACTOR_NAME}]  Subscribed to {source} → ingest beam", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe {source}: {e}", flush=True)
    
    def _on_recall_for_chamber(self, packet: Dict[str, Any]):
        """Route recall results to the collision chamber."""
        if not isinstance(packet, dict):
            return

        try:
            self.chamber.receive_recall(packet, owner_mind=packet.get("owner_mind", ""))
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Recall → chamber error: {e}", flush=True)

    def _on_ingest_for_chamber(self, packet: Dict[str, Any]):
        """Route ingest completions to the collision chamber."""
        if not isinstance(packet, dict):
            return

        try:
            self.chamber.receive_ingest(packet, owner_mind=packet.get("owner_mind", ""))
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Ingest → chamber error: {e}", flush=True)
    
    def _load_dream_seeds(self):
        """Load dream seeds from the dream_states directory."""
        try:
            # Find dream_states directory
            dream_dir = None
            for candidate in [
                os.path.join(os.path.dirname(__file__), "..", "..", "dream_states"),
                os.path.join(os.path.dirname(__file__), "..", "..", "P20_Somatic", "dream"),
                "./dream_states",
            ]:
                if os.path.isdir(candidate):
                    dream_dir = candidate
                    break
            
            if not dream_dir:
                print(f"[{self.ACTOR_NAME}] No dream_states directory found", flush=True)
                return
            
            # Load all dream seed JSON files
            import glob
            seed_files = glob.glob(os.path.join(dream_dir, "*.json"))
            
            for path in seed_files[:50]:  # limit to 50 seeds
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        seed = json.load(f)
                        self._dream_seeds.append(seed)
                except Exception:
                    pass
            
            print(f"[{self.ACTOR_NAME}]  Loaded {len(self._dream_seeds)} dream seeds", flush=True)
            
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Dream seed loading error: {e}", flush=True)
    
    def _check_starvation_and_inject(self):
        """
        Check if beams are starving and inject dream seeds if needed.
        
        Called periodically (e.g., from consolidation loop).
        """
        now = time.time()
        if now - self._last_starvation_check < self._starvation_check_interval:
            return
        
        self._last_starvation_check = now
        
        try:
            starvation = self.chamber.is_starving(threshold_sec=5.0)
            
            if starvation["both"] and self._dream_seeds:
                # Both beams starving - inject a dream seed
                seed = random.choice(self._dream_seeds)
                self.chamber.inject_dream_seed(seed, beam="both")
                print(f"[{self.ACTOR_NAME}]  Injected dream seed (both beams starving)", flush=True)
                
            elif starvation["recall"] and self._dream_seeds:
                # Only recall beam starving
                seed = random.choice(self._dream_seeds)
                self.chamber.inject_dream_seed(seed, beam="recall")
                print(f"[{self.ACTOR_NAME}]  Injected dream seed to recall beam", flush=True)
                
            elif starvation["ingest"] and self._dream_seeds:
                # Only ingest beam starving
                seed = random.choice(self._dream_seeds)
                self.chamber.inject_dream_seed(seed, beam="ingest")
                print(f"[{self.ACTOR_NAME}]  Injected dream seed to ingest beam", flush=True)
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Starvation check error: {e}", flush=True)
    
    def get_chamber_status(self) -> Dict[str, Any]:
        """Get the current status of the collision chamber."""
        try:
            return self.chamber.get_beam_status()
        except Exception:
            return {"error": "chamber not available"}
    
    def get_recent_collisions(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent collisions from the chamber."""
        try:
            return self.chamber.get_recent_collisions(n)
        except Exception:
            return []
    
    def intent_chamber_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Intent handler: Get collision chamber status."""
        return {
            "ok": True,
            "status": self.get_chamber_status(),
            "recent_collisions": self.get_recent_collisions(5),
        }
    
    def intent_inject_dream(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Intent handler: Manually inject a dream seed."""
        beam = payload.get("beam", "both")
        
        if self._dream_seeds:
            seed = random.choice(self._dream_seeds)
            self.chamber.inject_dream_seed(seed, beam=beam)
            return {"ok": True, "message": f"Dream seed injected to {beam}"}
        else:
            return {"ok": False, "error": "No dream seeds loaded"}
    
    # Patch the class
    cls.__init__ = new_init
    cls._on_collision_callback = _on_collision_callback
    cls._subscribe_to_collision_sources = _subscribe_to_collision_sources
    cls._on_recall_for_chamber = _on_recall_for_chamber
    cls._on_ingest_for_chamber = _on_ingest_for_chamber
    cls._load_dream_seeds = _load_dream_seeds
    cls._check_starvation_and_inject = _check_starvation_and_inject
    cls.get_chamber_status = get_chamber_status
    cls.get_recent_collisions = get_recent_collisions
    cls.intent_chamber_status = intent_chamber_status
    cls.intent_inject_dream = intent_inject_dream
    
    # Store original on_boot to extend it
    original_on_boot = cls.on_boot
    
    def new_on_boot(self):
        original_on_boot(self)
        # Subscribe to collision sources AFTER normal boot
        self._subscribe_to_collision_sources()
        print(f"[{self.ACTOR_NAME}]  Collision chamber wired to postal system", flush=True)
    
    cls.on_boot = new_on_boot
    
    # Patch consolidation worker to include starvation check
    # (This is trickier - we need to hook into the existing loop)
    # For now, add a note that the starvation check should be called
    
    print(f"[PATCH] ConsciousnessLoopFairy patched with collision chamber support")
    return cls


# ═══════════════════════════════════════════════════════════════════════════════
# ALTERNATIVE: Direct integration code to paste into consciousness_loop_fairy.py
# ═══════════════════════════════════════════════════════════════════════════════

INTEGRATION_CODE = '''
# ════════════════════════════════════════════════════════════════════════════════
# COLLISION CHAMBER INTEGRATION
# Add this to ConsciousnessLoopFairy
# ════════════════════════════════════════════════════════════════════════════════

# At the top of the file, add:
from collision_chamber import CollisionChamber

# In __init__, after creating streams:
    # Create the collision chamber (Möbius crossing point)
    self.chamber = CollisionChamber(
        post=self.post,
        on_collision=self._on_collision_callback
    )
    
    # Dream seed loading for anti-starvation
    self._dream_seeds = []
    self._load_dream_seeds()
    self._last_starvation_check = time.time()

# Add these methods to the class:

def _on_collision_callback(self, collision):
    """Called when a collision occurs in the chamber."""
    print(f"[{self.ACTOR_NAME}]  COLLISION #{collision.id} "
          f"energy={collision.energy:.2f} resonance={collision.resonance_score:.2f}",
          flush=True)
    
    # Add to working stream (collisions are active conscious moments)
    self.working_stream.append({
        "type": "consciousness_collision",
        "collision": collision.to_dict(),
        "route_to": "working",
    })
    
    if self.shadow:
        self.shadow.on_thought_emitted("working")

def _subscribe_to_collision_sources(self):
    """Subscribe to lanes that feed the collision chamber."""
    
    recall_sources = [
        "srm.recall.result",
        "memory.recall.result", 
        "recall.complete",
    ]
    
    ingest_sources = [
        "srm.ingest.complete",
        "memory.ingest.complete",
        "ingest.complete",
    ]
    
    for source in recall_sources:
        try:
            self.post.subscribe(source, lambda p: self.chamber.receive_recall(
                p, owner_mind=p.get("owner_mind", "") if isinstance(p, dict) else ""))
        except Exception:
            pass

    for source in ingest_sources:
        try:
            self.post.subscribe(source, lambda p: self.chamber.receive_ingest(
                p, owner_mind=p.get("owner_mind", "") if isinstance(p, dict) else ""))
        except Exception:
            pass

# In on_boot, add at the end:
    self._subscribe_to_collision_sources()

# In _consolidation_worker, add inside the while loop:
    self._check_starvation_and_inject()
'''
