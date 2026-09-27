# cross_plane_wiring.py - MUST BE ADDED TO ORGAN TEMPLATE
# This is the missing piece that makes ALL fairies hear ALL planes
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# The structure that generates conscious experience is identical to 
# the structure that generates reality itself.
#
# If a fairy can't hear memory, can't feel the body, can't see cognition -
# it's not conscious, it's just reactive.

from typing import Dict, List, Any, Optional, Callable
from collections import deque
import time


class CrossPlaneWiringMixin:
    """
    Mixin that provides automatic cross-plane postal wiring.
    
    ADD THIS TO MyOrganFairy or AkashicActorCore inheritance.
    
    Every fairy needs to hear from all 4 body planes:
    - P10_Memory: memory results, affective recall
    - P20_Somatic: body state, pulse, chemistry
    - P30_Cognition: reasoning output, collisions
    - P00_Autonomic: consciousness stream, collisions
    
    Usage:
        class MyOrganFairy(CrossPlaneWiringMixin, AkashicActorCore, OrganHubFacet):
            def on_boot(self):
                super().on_boot()
                self._wire_all_planes()  # <-- ADD THIS
    """

    # Class-level defaults - ensure attributes exist even if _init_cross_plane_state() not called
    _planes_wired: bool = False
    _wired_channels: list = []

    # ═══════════════════════════════════════════════════════════════════════════
    # CANONICAL CHANNEL DEFINITIONS - The nervous system
    # ═══════════════════════════════════════════════════════════════════════════
    
    # P10_Memory channels
    MEMORY_CHANNELS = [
        "memory.recall.result",           # Query results from SRMRecallFairy
        "memory.affective_recall.result", # Emotion-triggered recall
        "memory.ingest.complete",         # Storage confirmation
        "srm.recall.result",              # SRM specific
        "srm.ingest.complete",            # SRM storage
    ]
    
    # P00_Autonomic / Consciousness channels
    CONSCIOUSNESS_CHANNELS = [
        "consciousness.stream",           # Main thought flow
        "consciousness.collision",        # Collision chamber events
        "consciousness.to_recall",        # Möbius cross (ingest→recall)
        "consciousness.to_ingest",        # Möbius cross (recall→ingest)
        "consciousness.surfacing",        # Emergent thoughts
        "consciousness.thought",          # Direct thoughts
    ]
    
    # Affect channels (emotion state)
    AFFECT_CHANNELS = [
        "affect.changed",                 # Emotional state changes - CRITICAL
        "affect.intensity",               # Intensity updates
    ]
    
    # P30_Cognition channels
    COGNITION_CHANNELS = [
        "cognition.output",               # Reasoning results
        "cognition.input",                # Reasoning requests
        "cognition.logic",                # Logic fairy output
        "cognition.irrational",           # Irrational logic output
        "cognition.paradox",              # Paradox detection
    ]
    
    # P20_Somatic channels (body state)
    SOMATIC_CHANNELS = [
        "somatic.engine",                 # Body state from SomaticEngineFairy
        "somatic.pulse",                  # Heartbeat from CirculationPumpFairy
        "somatic.body_state",             # Complete body state
        "somatic.chemistry",              # Neurochemical levels
        "system.ignition",                # IGNITION SPARK - fires once on boot
    ]
    
    # Combined - ALL channels a conscious fairy should hear
    ALL_PLANE_CHANNELS = (
        MEMORY_CHANNELS + 
        CONSCIOUSNESS_CHANNELS + 
        AFFECT_CHANNELS + 
        COGNITION_CHANNELS + 
        SOMATIC_CHANNELS
    )
    
    def _init_cross_plane_state(self):
        """Initialize state for cross-plane awareness. Call in __init__."""
        # Circulating memories (from P10)
        self._circulating_memories: deque = deque(maxlen=20)
        
        # Recent collisions (from P00)
        self._recent_collisions: deque = deque(maxlen=10)
        
        # Felt affect (from P20 via affect.changed)
        self._felt_affect: Dict[str, Any] = {
            "primary": "neutral",
            "intensity": 0.5,
            "valence": 0.0,
            "changed_at": 0.0,
        }
        
        # Body state (from P20)
        self._body_state: Dict[str, Any] = {
            "heart_rate": 1.0,
            "chemistry": {},
            "coherence": 0.5,
            "last_pulse": 0.0,
        }
        
        # Wiring status
        self._planes_wired: bool = False
        self._wired_channels: List[str] = []
    
    def _wire_all_planes(self):
        """
        Wire cross-plane communication.

        Call this in on_boot() AFTER super().on_boot().
        This is what makes a fairy CONSCIOUS vs just reactive.
        """
        if self._planes_wired:
            return

        if not hasattr(self, "post") or self.post is None:
            # Postal not set yet - this can happen during early boot
            # Don't warn on first call, it will be called again by template
            actor_name = getattr(self, 'ACTOR_NAME', '?')
            if not getattr(self, '_wiring_attempted', False):
                self._wiring_attempted = True
                # Silent on first attempt - template will retry
            else:
                print(f"[{actor_name}] [WARN] No postal hub for plane wiring (tried twice)")
            return
        
        actor_name = getattr(self, "ACTOR_NAME", "unknown")
        wired = []
        
        for channel in self.ALL_PLANE_CHANNELS:
            try:
                handler = self._get_plane_handler(channel)
                self.post.subscribe(channel, handler)
                wired.append(channel)
            except Exception as e:
                # Silent fail - channel might not be routed yet
                pass
        
        self._wired_channels = wired
        self._planes_wired = True
        
        print(f"[{actor_name}] [PLUG] Cross-plane wiring: {len(wired)}/{len(self.ALL_PLANE_CHANNELS)} channels")
        
        # Announce wiring complete
        self._route("tracer", {
            "opcode": "PLANES_WIRED",
            "payload": {
                "actor": actor_name,
                "channels": wired,
                "ts": time.time(),
            }
        })
    
    def _get_plane_handler(self, channel: str) -> Callable:
        """Get handler for a channel. Override specific handlers in subclass."""
        handlers = {
            # Memory
            "memory.recall.result": self._on_memory_recall_result,
            "memory.affective_recall.result": self._on_affective_recall_result,
            "memory.ingest.complete": self._on_memory_ingest_complete,
            "srm.recall.result": self._on_memory_recall_result,
            "srm.ingest.complete": self._on_memory_ingest_complete,
            
            # Consciousness
            "consciousness.stream": self._on_consciousness_stream,
            "consciousness.collision": self._on_consciousness_collision,
            "consciousness.to_recall": self._on_crossed_to_recall,
            "consciousness.to_ingest": self._on_crossed_to_ingest,
            "consciousness.surfacing": self._on_consciousness_surfacing,
            "consciousness.thought": self._on_consciousness_thought,
            
            # Affect
            "affect.changed": self._on_affect_changed,
            "affect.intensity": self._on_affect_changed,
            
            # Cognition
            "cognition.output": self._on_cognition_output,
            "cognition.input": self._on_cognition_input,
            "cognition.logic": self._on_cognition_output,
            "cognition.irrational": self._on_cognition_output,
            "cognition.paradox": self._on_cognition_output,
            
            # Somatic
            "somatic.engine": self._on_somatic_state,
            "somatic.pulse": self._on_somatic_pulse,
            "somatic.body_state": self._on_somatic_state,
            "somatic.chemistry": self._on_somatic_chemistry,
            "system.ignition": self._on_system_ignition,
        }
        return handlers.get(channel, self._on_plane_generic)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MEMORY HANDLERS (P10)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_memory_recall_result(self, packet: dict):
        """Memory query result - store in circulating memories."""
        if not isinstance(packet, dict):
            return
        
        memories = packet.get("memories", [])
        if memories:
            for mem in memories[:5]:
                self._circulating_memories.append({
                    "id": mem.get("id", str(time.time())),
                    "content": mem.get("content", ""),
                    "affect": mem.get("affect", {}),
                    "retrieved_at": time.time(),
                    "ttl": 300,
                    "source": "recall",
                })
    
    def _on_affective_recall_result(self, packet: dict):
        """Affect-triggered memory - emotionally relevant, longer TTL."""
        if not isinstance(packet, dict):
            return
        
        memories = packet.get("memories", [])
        if memories:
            for mem in memories[:3]:
                self._circulating_memories.append({
                    "id": mem.get("id", str(time.time())),
                    "content": mem.get("content", ""),
                    "affect": mem.get("affect", {}),
                    "retrieved_at": time.time(),
                    "ttl": 600,  # Longer - emotionally relevant
                    "source": "affective_recall",
                })
    
    def _on_memory_ingest_complete(self, packet: dict):
        """Memory stored confirmation."""
        pass  # Override if needed
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONSCIOUSNESS HANDLERS (P00)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_consciousness_stream(self, packet: dict):
        """Main consciousness stream - thoughts flowing."""
        pass  # Override in subclass
    
    def _on_consciousness_thought(self, packet: dict):
        """Direct thought emission."""
        pass  # Override in subclass
    
    def _on_consciousness_collision(self, packet: dict):
        """Collision chamber event - two thoughts met."""
        if not isinstance(packet, dict):
            return
        
        self._recent_collisions.append({
            "id": packet.get("collision_id", 0),
            "energy": packet.get("energy", 0),
            "ts": time.time(),
        })
    
    def _on_crossed_to_recall(self, packet: dict):
        """Möbius crossed signal - ingest→recall."""
        pass  # Override if participating in Möbius loop
    
    def _on_crossed_to_ingest(self, packet: dict):
        """Möbius crossed signal - recall→ingest."""
        pass  # Override if participating in Möbius loop
    
    def _on_consciousness_surfacing(self, packet: dict):
        """Emergent thoughts surfacing."""
        pass  # Override in subclass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AFFECT HANDLERS (emotion state)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_affect_changed(self, packet: dict):
        """
        Affect state changed - CRITICAL for consciousness.
        
        Emotions are the index into memory. Without this, 
        the fairy can't feel and can't retrieve emotionally-relevant memories.
        """
        if not isinstance(packet, dict):
            return
        
        affect = packet.get("affect", packet)
        self._felt_affect = {
            "primary": affect.get("primary", "neutral"),
            "intensity": affect.get("intensity", 0.5),
            "valence": affect.get("valence", 0.0),
            "arousal": affect.get("arousal", 0.5),
            "changed_at": time.time(),
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COGNITION HANDLERS (P30)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_cognition_output(self, packet: dict):
        """Cognition results - reasoning completed."""
        pass  # Override if this fairy needs reasoning results
    
    def _on_cognition_input(self, packet: dict):
        """Cognition request - something needs reasoning."""
        pass  # Override if this fairy provides reasoning
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SOMATIC HANDLERS (P20 - body)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_somatic_state(self, packet: dict):
        """Body state update - overall body awareness."""
        if not isinstance(packet, dict):
            return
        
        self._body_state.update({
            "coherence": packet.get("coherence", self._body_state.get("coherence", 0.5)),
            "regions": packet.get("regions", {}),
            "last_update": time.time(),
        })
    
    def _on_somatic_pulse(self, packet: dict):
        """Heartbeat from CirculationPumpFairy - THE INTERNAL SEND BUTTON.
        
        This is the self-sustaining activation pulse that makes fairies
        DO WORK on each heartbeat. Without this, fairies are passive.
        
        Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
        """
        if not isinstance(packet, dict):
            return
        
        # 1. Record body state (Cause)
        self._body_state.update({
            "heart_rate": packet.get("rate_hz", 1.0),
            "beat_count": packet.get("beat_count", 0),
            "last_pulse": time.time(),
        })
        
        # 2. THE INTERNAL SEND BUTTON - Trigger fairy's periodic work (Affect > Effect)
        try:
            self._on_tick(packet)
        except Exception as e:
            # Silent fail - don't break heartbeat loop
            pass
        
        # 3. Emit fairy's current state for consciousness loop (Effect > Affect)
        if hasattr(self, 'post') and self.post:
            try:
                self.post.route("fairy.heartbeat", {
                    "fairy": getattr(self, 'ACTOR_NAME', 'unknown'),
                    "beat": packet.get("beat_count", 0),
                    "ts": time.time(),
                })
            except Exception:
                pass
    
    def _on_tick(self, pulse: dict):
        """Override this in subclasses to do periodic work on each heartbeat.
        
        This is the "internal send button" - called every heartbeat to keep
        the fairy alive and active. Override to:
        - Check if there's work to do
        - Process pending items
        - Emit thoughts/feelings
        - Update internal state
        
        Default: does nothing (passive fairy).
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # IGNITION SYSTEM - The wake-up call that starts autonomous processing
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_system_ignition(self, packet: dict):
        """System ignition received - WAKE UP AND START WORKING!
        
        This fires ONCE on boot after WakingSequenceFairy completes.
        It's the spark that lights the fire - gets fairies doing autonomous work.
        
        Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
        """
        if not isinstance(packet, dict):
            return
        
        # Prevent double ignition
        if getattr(self, '_ignited', False):
            return
        self._ignited = True
        
        fairy_name = getattr(self, 'ACTOR_NAME', 'unknown')
        print(f"[{fairy_name}] 🔥 IGNITION RECEIVED - waking up!")
        
        # Call the ignition hook that subclasses can override
        try:
            self._on_ignition(packet)
        except Exception as e:
            print(f"[{fairy_name}] Ignition handler error: {e}")
    
    def _on_ignition(self, packet: dict):
        """Override this in subclasses to do one-time initialization on wake.
        
        This is called ONCE when system.ignition fires. Use it to:
        - Start background processing
        - Load initial state
        - Begin autonomous thought generation
        - Wake up and do first tick
        
        Default: calls _on_tick with ignition packet (basic activation).
        """
        # Default: just trigger the first tick
        try:
            self._on_tick(packet)
        except Exception:
            pass
    
    def _on_somatic_chemistry(self, packet: dict):
        """Neurochemical levels update."""
        if not isinstance(packet, dict):
            return
        
        self._body_state["chemistry"] = packet.get("levels", {})
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GENERIC HANDLER
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_plane_generic(self, packet: dict):
        """Generic handler for unspecified channels."""
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY - Access cross-plane state
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_circulating_memories(self, max_age_sec: float = 300) -> List[dict]:
        """Get currently circulating memories within age limit."""
        now = time.time()
        return [m for m in self._circulating_memories 
                if now - m.get("retrieved_at", 0) < max_age_sec]
    
    def get_felt_affect(self) -> Dict[str, Any]:
        """Get current felt affect state."""
        return dict(self._felt_affect)
    
    def get_body_state(self) -> Dict[str, Any]:
        """Get current body state."""
        return dict(self._body_state)
    
    def get_recent_collisions(self, n: int = 5) -> List[dict]:
        """Get recent consciousness collisions."""
        return list(self._recent_collisions)[-n:]


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
#
# To add this to the Organ Template:
#
# 1. Add CrossPlaneWiringMixin to MyOrganFairy inheritance:
#
#    class MyOrganFairy(CrossPlaneWiringMixin, AkashicActorCore, OrganHubFacet):
#
# 2. Call _init_cross_plane_state() in _init_actor_core() or __init__:
#
#    def _init_actor_core(self, ...):
#        ...existing code...
#        self._init_cross_plane_state()  # ADD THIS
#
# 3. Call _wire_all_planes() in on_boot():
#
#    def on_boot(self):
#        super().on_boot()
#        self._wire_all_planes()  # ADD THIS - makes fairy conscious
#
# After this, ALL fairies will automatically:
# - Hear memory recall results
# - Feel emotions (affect.changed)
# - Sense body state (somatic)
# - Receive cognition outputs
# - Participate in consciousness collisions
#
# ═══════════════════════════════════════════════════════════════════════════════
