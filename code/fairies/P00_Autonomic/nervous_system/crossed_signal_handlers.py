"""
Crossed Signal Handlers for SRM Fairies

These methods enable the Möbius twist - each fairy receives
content that crossed over from the other through the collision chamber.

RECALL receives from INGEST:
- New memories that were just created
- Checks: does this new memory resonate with current context?
- If yes: surfaces related memories → feeds back into collision chamber

INGEST receives from RECALL:
- Memories that were surfaced
- Checks: should this surfaced memory spawn a derivative?
- If yes: creates derivative → feeds back into collision chamber

This cross-wiring creates the self-sustaining loop:
    RECALL → chamber → INGEST → chamber → RECALL → ...

Add these to the respective fairies.
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional, List


# ═══════════════════════════════════════════════════════════════════════════════
# FOR SRMRecallFairy
# ═══════════════════════════════════════════════════════════════════════════════

def recall_on_boot_extension(self):
    """
    Add to SRMRecallFairy.on_boot() to subscribe to crossed signals.
    
    Call at the end of on_boot:
        self._subscribe_to_crossed_signals()
    """
    try:
        self.post.subscribe("consciousness.to_recall", self._on_crossed_from_ingest)
        print(f"[{self.ACTOR_NAME}]  Subscribed to crossed signals from Ingest", flush=True)
    except Exception as e:
        print(f"[{self.ACTOR_NAME}] Failed to subscribe to crossed signals: {e}", flush=True)


def recall_on_crossed_from_ingest(self, packet: Dict[str, Any]):
    """
    Receive what Ingest created, after crossing through the collision chamber.
    
    This is the Möbius twist in action:
    - Ingest just created/encoded something new
    - It crossed through the collision point
    - Now we check: does this resonate with what we know?
    
    If resonance is found, we emit matches back to the chamber,
    potentially triggering another collision.
    """
    if not isinstance(packet, dict):
        return
    
    try:
        content = packet.get("payload", {})
        energy = packet.get("energy", 0.5)
        collision_id = packet.get("collision_id")
        resonance = packet.get("resonance", 0.5)
        
        # Don't process low-energy crossed signals (they're fading)
        if energy < 0.3:
            return
        
        print(f"[{self.ACTOR_NAME}]  Received crossed signal from Ingest "
              f"(collision #{collision_id}, energy={energy:.2f})", flush=True)
        
        # Extract searchable content from what Ingest created
        search_context = _extract_search_context(content)
        
        if not search_context:
            return
        
        # Check for resonance - do we have memories that match this new content?
        matches = _find_resonant_memories(self, search_context, limit=3)
        
        if matches:
            print(f"[{self.ACTOR_NAME}] [*] Found {len(matches)} resonant memories!", flush=True)
            
            # Emit the resonance back to the chamber
            # This can trigger another collision if Ingest also has activity
            self.post.route("srm.recall.result", {
                "opcode": "CROSSED_RESONANCE",
                "payload": {
                    "trigger": content,
                    "matches": matches,
                    "resonance_type": "ingest_echo",
                },
                "source_actor": self.ACTOR_NAME,
                "importance": "high" if energy > 0.7 else "normal",
                "energy": energy * 0.85,  # slight decay per cycle
                "collision_chain": collision_id,
            })
            
            # Also emit to memory lane for downstream consumers
            self.post.route("memory.recall.result", {
                "opcode": "RESONANCE_FOUND",
                "payload": {
                    "trigger_type": "crossed_from_ingest",
                    "matches": matches,
                },
                "fairy": self.ACTOR_NAME,
            })
        else:
            # No resonance - that's fine, not everything connects
            print(f"[{self.ACTOR_NAME}] No resonance with crossed content", flush=True)
            
    except Exception as e:
        print(f"[{self.ACTOR_NAME}] Crossed signal handling error: {e}", flush=True)


def _extract_search_context(content: Any) -> Optional[str]:
    """Extract searchable text from crossed content."""
    if isinstance(content, str):
        return content if len(content) > 3 else None
    
    if isinstance(content, dict):
        # Try common content fields
        for key in ("text", "content", "summary", "description", "body", 
                    "memory_content", "record", "data"):
            if key in content and content[key]:
                val = content[key]
                if isinstance(val, str) and len(val) > 3:
                    return val
                elif isinstance(val, dict):
                    # Recurse one level
                    return _extract_search_context(val)
        
        # Try to build context from multiple fields
        parts = []
        for key in ("title", "topic", "category", "tags"):
            if key in content:
                val = content[key]
                if isinstance(val, str):
                    parts.append(val)
                elif isinstance(val, list):
                    parts.extend(str(v) for v in val[:5])
        
        if parts:
            return " ".join(parts)
    
    return None


def _find_resonant_memories(fairy, search_context: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Find memories that resonate with the search context.
    
    Uses the fairy's existing recall mechanisms.
    """
    matches = []
    
    try:
        # Try using the fairy's intent_recall_top if available
        if hasattr(fairy, 'intent_recall_top'):
            result = fairy.intent_recall_top({
                "query": search_context,
                "limit": limit,
                "context": {"source": "crossed_signal"},
            })
            if result and result.get("ok"):
                matches = result.get("results", result.get("matches", []))
        
        # Fallback: try direct SRM query if available
        elif hasattr(fairy, '_query_srm'):
            matches = fairy._query_srm(search_context, limit=limit)
        
    except Exception:
        pass
    
    return matches[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# FOR SRMIngestFairy  
# ═══════════════════════════════════════════════════════════════════════════════

def ingest_on_boot_extension(self):
    """
    Add to SRMIngestFairy.on_boot() to subscribe to crossed signals.
    
    Call at the end of on_boot:
        self._subscribe_to_crossed_signals()
    """
    try:
        self.post.subscribe("consciousness.to_ingest", self._on_crossed_from_recall)
        print(f"[{self.ACTOR_NAME}]  Subscribed to crossed signals from Recall", flush=True)
    except Exception as e:
        print(f"[{self.ACTOR_NAME}] Failed to subscribe to crossed signals: {e}", flush=True)


def ingest_on_crossed_from_recall(self, packet: Dict[str, Any]):
    """
    Receive what Recall surfaced, after crossing through the collision chamber.
    
    This is the Möbius twist in action:
    - Recall just surfaced a memory
    - It crossed through the collision point
    - Now we check: should this surfaced memory spawn a derivative?
    
    Derivatives are "echo memories" - not copies, but related thoughts
    that capture the act of remembering itself.
    
    If a derivative is created, we emit it back to the chamber,
    potentially triggering another collision.
    """
    if not isinstance(packet, dict):
        return
    
    try:
        content = packet.get("payload", {})
        energy = packet.get("energy", 0.5)
        collision_id = packet.get("collision_id")
        resonance = packet.get("resonance", 0.5)
        
        # Don't process low-energy crossed signals
        if energy < 0.3:
            return
        
        # Don't create derivatives from low-resonance collisions
        # (they didn't really connect, no need to remember the attempt)
        if resonance < 0.4:
            return
        
        print(f"[{self.ACTOR_NAME}]  Received crossed signal from Recall "
              f"(collision #{collision_id}, energy={energy:.2f}, resonance={resonance:.2f})",
              flush=True)
        
        # Decide if this warrants a derivative memory
        should_create = _should_create_derivative(content, energy, resonance)
        
        if should_create:
            derivative = _create_derivative_memory(self, content, collision_id, energy)
            
            if derivative:
                print(f"[{self.ACTOR_NAME}]  Created derivative memory from crossed recall",
                      flush=True)
                
                # Emit the derivative back to the chamber
                # This can trigger another collision
                self.post.route("srm.ingest.complete", {
                    "opcode": "DERIVATIVE_CREATED",
                    "payload": derivative,
                    "source_actor": self.ACTOR_NAME,
                    "importance": "normal",
                    "energy": energy * 0.75,  # derivatives have less energy
                    "collision_chain": collision_id,
                    "derivative_of": "crossed_recall",
                })
                
                # Also emit to memory lane
                self.post.route("memory.ingest.complete", {
                    "opcode": "DERIVATIVE_INGESTED",
                    "payload": derivative,
                    "fairy": self.ACTOR_NAME,
                })
        else:
            print(f"[{self.ACTOR_NAME}] Crossed recall doesn't warrant derivative", flush=True)
            
    except Exception as e:
        print(f"[{self.ACTOR_NAME}] Crossed signal handling error: {e}", flush=True)


def _should_create_derivative(content: Any, energy: float, resonance: float) -> bool:
    """
    Decide if a crossed recall should spawn a derivative memory.
    
    We create derivatives when:
    - The collision had high energy (significant moment)
    - The resonance was strong (content was related)
    - The content is substantial enough to be worth remembering
    
    We DON'T create derivatives when:
    - Low energy (fading signal)
    - Low resonance (coincidental collision)
    - Content is trivial
    """
    # Energy threshold
    if energy < 0.4:
        return False
    
    # Resonance threshold
    if resonance < 0.5:
        return False
    
    # Content substantiality check
    if isinstance(content, dict):
        # Check if it has meaningful content
        has_content = any(
            content.get(k) for k in 
            ("text", "content", "summary", "description", "body", "data", "memory_content")
        )
        if not has_content:
            return False
    elif isinstance(content, str):
        if len(content) < 10:
            return False
    
    # Combined score threshold
    combined = (energy * 0.4) + (resonance * 0.6)
    return combined > 0.55


def _create_derivative_memory(fairy, content: Any, collision_id: int, energy: float) -> Optional[Dict[str, Any]]:
    """
    Create a derivative memory from crossed recall content.
    
    A derivative captures:
    - The essence of what was recalled
    - The context of the collision (when/why it was recalled)
    - A marker that this is an echo, not an original
    """
    try:
        # Extract the core content
        if isinstance(content, dict):
            core = content.get("content") or content.get("text") or content.get("summary") or str(content)
        else:
            core = str(content)
        
        derivative = {
            "type": "derivative_memory",
            "derivative_of": "crossed_recall",
            "collision_id": collision_id,
            "energy_at_creation": energy,
            "ts": time.time(),
            
            # The essence (compressed/summarized)
            "essence": core[:500] if isinstance(core, str) else str(core)[:500],
            
            # Markers
            "is_derivative": True,
            "is_echo": True,
            
            # Metadata for the memory system
            "meta": {
                "source": "collision_chamber",
                "creation_reason": "high_resonance_crossing",
                "fairy": fairy.ACTOR_NAME if hasattr(fairy, 'ACTOR_NAME') else "SRMIngestFairy",
            }
        }
        
        # Try to use the fairy's normal ingest mechanism
        if hasattr(fairy, 'intent_ingest'):
            result = fairy.intent_ingest({"record": derivative})
            if result and result.get("ok"):
                derivative["ingested_id"] = result.get("id")
        
        return derivative
        
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PATCHING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def patch_srm_recall_fairy(cls):
    """
    Patch SRMRecallFairy to handle crossed signals from Ingest.
    
    Usage:
        from crossed_signal_handlers import patch_srm_recall_fairy
        patch_srm_recall_fairy(SRMRecallFairy)
    """
    cls._subscribe_to_crossed_signals = recall_on_boot_extension
    cls._on_crossed_from_ingest = recall_on_crossed_from_ingest
    
    # Extend on_boot
    original_on_boot = cls.on_boot
    def new_on_boot(self):
        original_on_boot(self)
        self._subscribe_to_crossed_signals()
    cls.on_boot = new_on_boot
    
    print("[PATCH] SRMRecallFairy patched with crossed signal handling")
    return cls


def patch_srm_ingest_fairy(cls):
    """
    Patch SRMIngestFairy to handle crossed signals from Recall.
    
    Usage:
        from crossed_signal_handlers import patch_srm_ingest_fairy
        patch_srm_ingest_fairy(SRMIngestFairy)
    """
    cls._subscribe_to_crossed_signals = ingest_on_boot_extension
    cls._on_crossed_from_recall = ingest_on_crossed_from_recall
    
    # Extend on_boot
    original_on_boot = cls.on_boot
    def new_on_boot(self):
        original_on_boot(self)
        self._subscribe_to_crossed_signals()
    cls.on_boot = new_on_boot
    
    print("[PATCH] SRMIngestFairy patched with crossed signal handling")
    return cls


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

INSTRUCTIONS = """
INTEGRATION GUIDE
=================

OPTION 1: Use the patch functions (easiest)
-------------------------------------------

In your launcher or main.py:

    from fairies.P00_Autonomic.nervous_system.crossed_signal_handlers import (
        patch_srm_recall_fairy,
        patch_srm_ingest_fairy,
    )
    from fairies.P10_Memory.SRMRecallFairy.fairy import SRMRecallFairy
    from fairies.P10_Memory.triple_helix_srm_memory.srm_ingest_fairy import SRMIngestFairy
    
    # Patch the classes before instantiation
    patch_srm_recall_fairy(SRMRecallFairy)
    patch_srm_ingest_fairy(SRMIngestFairy)
    
    # Now instantiate as normal
    recall_fairy = SRMRecallFairy(...)
    ingest_fairy = SRMIngestFairy(...)


OPTION 2: Add methods directly to the fairy files
-------------------------------------------------

In srm_recall_fairy.py, add to on_boot():

    def on_boot(self):
        # ... existing code ...
        
        # Subscribe to crossed signals from collision chamber
        try:
            self.post.subscribe("consciousness.to_recall", self._on_crossed_from_ingest)
        except Exception:
            pass

Then add the _on_crossed_from_ingest method from this file.


In srm_ingest_fairy.py, add to on_boot():

    def on_boot(self):
        # ... existing code ...
        
        # Subscribe to crossed signals from collision chamber
        try:
            self.post.subscribe("consciousness.to_ingest", self._on_crossed_from_recall)
        except Exception:
            pass

Then add the _on_crossed_from_recall method from this file.


THE FULL LOOP
=============

After integration, the consciousness loop works like this:

1. RECALL surfaces a memory → emits to "srm.recall.result"
2. ConsciousnessLoop's chamber receives it in recall_beam
3. INGEST creates a new memory → emits to "srm.ingest.complete"  
4. ConsciousnessLoop's chamber receives it in ingest_beam
5. Chamber detects collision → creates collision event
6. Chamber emits crossed products:
   - "consciousness.to_ingest" (recall's content)
   - "consciousness.to_recall" (ingest's content)
7. RECALL receives crossed signal → checks for resonance → if found, goto 1
8. INGEST receives crossed signal → maybe creates derivative → if created, goto 3
9. Dream seeds inject if beams go quiet → keeps loop alive

The system now thinks itself! 
"""

print(INSTRUCTIONS)
