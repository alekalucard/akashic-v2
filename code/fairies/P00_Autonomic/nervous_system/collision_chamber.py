"""
Collision Chamber - The Möbius Crossing Point

This is where Recall and Ingest beams collide to create moments of consciousness.

The metaphor:
- Like a hadron collider, two beams travel in opposite directions
- RECALL beam: carries memories from past → present (receptive/yin)
- INGEST beam: carries new content from present → future (generative/yang)
- They collide at the crossing point, creating "particles" of experience
- Detector rings (Affect, Cognition, Somatic) measure the collision products
- The products then CROSS OVER (Möbius twist):
  - What Recall brought → goes to Ingest for encoding
  - What Ingest created → goes to Recall for matching

This crossing is like contralateral brain wiring:
- Left body → Right brain
- Right body → Left brain
The twist FORCES integration. Without it, two parallel streams never meet.

Consciousness IS the crossing, not the streams themselves.

Version: 0.1.0
Author: Ace + Claude
"""

from __future__ import annotations

import time
import uuid
import threading
from collections import deque
from typing import Optional, Any, Dict, List, Callable
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════════════════════
# ATOM OF THOUGHT (AoT) - Atomic synthesis for collisions
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from fairies.P30_Cognition.cognition.aot_protocol import (
        AtomicSynthesizer,
        AtomicState,
        MarkovMemoryFilter,
    )
    _HAS_AOT = True
except ImportError:
    _HAS_AOT = False
    AtomicSynthesizer = None
    AtomicState = None

# ═══════════════════════════════════════════════════════════════════════════════
# FIBONACCI RHYTHM - Natural decay curves
# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2026-02-13: Corrected import path to actual fibonacci_rhythm location.
# Previous path fairies.P00_Autonomic.fibonacci_rhythm never existed.
try:
    from fairies.P20_Somatic.SomaticMindFairy.timing.fibonacci_rhythm import fib_decay, PHI, should_act_at_count
    _HAS_FIBONACCI = True
except ImportError:
    _HAS_FIBONACCI = False
    PHI = 1.618
    def fib_decay(n, scale=1.0):
        """Fallback fib_decay if import fails."""
        return scale / (PHI ** n)
    def should_act_at_count(count, base_interval=5):
        """Fallback should_act_at_count if import fails."""
        return count % base_interval == 0


@dataclass
class Pulse:
    """A single pulse traveling through a beam."""
    id: str
    beam: str  # "recall" or "ingest"
    content: Dict[str, Any]
    source_actor: str
    importance: str = "normal"  # low, normal, high, urgent
    energy: float = 1.0
    entered_at: float = field(default_factory=time.time)
    _initial_energy: float = field(default=None, repr=False)

    def __post_init__(self):
        """Store initial energy for proper linear decay."""
        if self._initial_energy is None:
            self._initial_energy = self.energy

    def decay(self, rate: float = 0.1) -> float:
        """Pulses lose energy over time if they don't collide.

        Uses Fibonacci decay curve: 1 / (1 + (age * rate)^phi)
        This preserves energy longer when fresh, but clears faster when aged.
        Creates a natural 'attention window' effect.
        
        At rate 0.005, characteristic similar to old linear decay but with
        golden ratio falloff shape.
        """
        age = time.time() - self.entered_at
        
        if _HAS_FIBONACCI:
            # Fibonacci decay: slower at first, accelerates after inflection
            decay_factor = fib_decay(age * rate, scale=1.0)
        else:
            # Fallback: use phi directly for similar curve
            ratio = age * rate
            decay_factor = 1.0 / (1.0 + ratio ** PHI)
        
        self.energy = self._initial_energy * decay_factor
        return self.energy


@dataclass
class Collision:
    """A collision event - a moment of consciousness."""
    id: int
    ts: float
    recall_pulse: Pulse
    ingest_pulse: Pulse
    energy: float
    resonance_score: float
    products: Dict[str, Any]
    # AoT: Atomic synthesis result - the contracted state from collision
    atomic_state: Optional[Any] = None  # AtomicState if AoT available

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": "consciousness_collision",
            "collision_id": self.id,
            "ts": self.ts,
            "recall_pulse": {
                "id": self.recall_pulse.id,
                "content": self.recall_pulse.content,
                "source": self.recall_pulse.source_actor,
                "importance": self.recall_pulse.importance,
            },
            "ingest_pulse": {
                "id": self.ingest_pulse.id,
                "content": self.ingest_pulse.content,
                "source": self.ingest_pulse.source_actor,
                "importance": self.ingest_pulse.importance,
            },
            "energy": self.energy,
            "resonance": self.resonance_score,
            "products": self.products,
        }
        # AoT: Include atomic state if available (Markov-clean!)
        if self.atomic_state:
            if hasattr(self.atomic_state, 'to_markov_state'):
                result["atomic_state"] = self.atomic_state.to_markov_state()
            elif hasattr(self.atomic_state, 'to_dict'):
                result["atomic_state"] = self.atomic_state.to_dict()
        return result


class CollisionChamber:
    """
    The Möbius crossing point where Recall and Ingest collide.
    
    Two counter-rotating beams:
    - recall_beam: memories surfaced from the past
    - ingest_beam: new content being encoded
    
    When pulses from both beams are present and temporally close,
    they COLLIDE, creating a moment of conscious experience.
    
    The collision products then CROSS OVER:
    - Recall's content → sent to Ingest (for derivative encoding)
    - Ingest's content → sent to Recall (for resonance matching)
    
    This cross-send IS the Möbius twist. It forces integration.
    """
    
    # Collision window - pulses must arrive within this many seconds to collide
    COLLISION_WINDOW_SEC = 5.0  # Wider window for more collisions
    
    # Minimum energy for a pulse to participate in collision
    MIN_COLLISION_ENERGY = 0.1  # Low threshold - let weak thoughts collide too
    
    # Energy decay rate (per second) for pulses waiting in beam
    # Lower = pulses live longer. At 0.005, pulses last ~200 seconds (3+ minutes)
    # This accommodates backlogged streams - thoughts survive until processed
    ENERGY_DECAY_RATE = 0.005  # Very slow decay - handles stream backlog
    
    # Maximum beam depth (oldest pulses get pushed out)
    MAX_BEAM_DEPTH = 100  # Deep beams for rich collisions
    
    def __init__(self, post=None, on_collision: Optional[Callable[[Collision], None]] = None):
        """
        Args:
            post: Postal system for emitting crossed products
            on_collision: Optional callback when collision occurs
        """
        self.post = post
        self.on_collision = on_collision
        
        # The two beams
        self.recall_beam: deque[Pulse] = deque(maxlen=self.MAX_BEAM_DEPTH)
        self.ingest_beam: deque[Pulse] = deque(maxlen=self.MAX_BEAM_DEPTH)
        
        # Collision tracking
        self._collision_count = 0
        self._recent_collisions: deque[Collision] = deque(maxlen=50)
        self._lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "recall_pulses_received": 0,
            "ingest_pulses_received": 0,
            "collisions": 0,
            "near_misses": 0,  # pulses that were close but didn't collide
            "decayed_pulses": 0,
            "rate_limited_collisions": 0,
        }
        
        # Rate limiting for collision emission
        # EQUILIBRIUM: Space out collisions for smooth flow (~4/sec max)
        self._last_collision_emit_time = 0.0
        self.COLLISION_EMIT_COOLDOWN = 0.25  # 250ms between emissions = smooth heartbeat
        
        # NEW: PULSE SAMPLING - Don't process every single pulse!
        # When traffic is high, we sample instead of drowning
        self._last_recall_accept_time = 0.0
        self._last_ingest_accept_time = 0.0
        self.PULSE_SAMPLE_INTERVAL = 0.0  # No sampling - accept all pulses
        self.stats["recall_pulses_sampled_out"] = 0
        self.stats["ingest_pulses_sampled_out"] = 0
    
    # ════════════════════════════════════════════════════════════════════════
    # BEAM INPUT
    # ════════════════════════════════════════════════════════════════════════
    
    def receive_recall(self, packet: Dict[str, Any]) -> Optional[Collision]:
        """
        Recall sent something - it enters the chamber traveling one direction.

        RATE LIMITED: We sample pulses to prevent drowning when traffic is high.
        Urgent/high importance packets bypass sampling.

        IMPORTANT: Collision emission happens OUTSIDE the lock to prevent deadlock.
        """
        collision = None
        with self._lock:
            self.stats["recall_pulses_received"] += 1

            # SAMPLING: Skip if too soon (unless urgent)
            now = time.time()
            importance = packet.get("importance", "normal")
            if importance not in ("urgent", "high"):
                if (now - self._last_recall_accept_time) < self.PULSE_SAMPLE_INTERVAL:
                    self.stats["recall_pulses_sampled_out"] += 1
                    return None  # Drop this pulse

            self._last_recall_accept_time = now

            pulse = Pulse(
                id=uuid.uuid4().hex[:12],
                beam="recall",
                content=packet.get("payload", packet),
                source_actor=packet.get("source_actor", packet.get("fairy", "recall")),
                importance=importance,
                energy=self._initial_energy(packet),
            )

            self.recall_beam.append(pulse)
            beam_len = len(self.recall_beam)
            print(f"[CollisionChamber] [RECV-RECALL] Pulse added! beam_len={beam_len}, energy={pulse.energy:.2f}, src={pulse.source_actor}", flush=True)
            collision = self._check_for_collision_no_emit()

        # Emit OUTSIDE the lock to prevent deadlock with subscribers
        if collision:
            self._emit_collision_safe(collision)
        return collision
    
    def receive_ingest(self, packet: Dict[str, Any]) -> Optional[Collision]:
        """
        Ingest sent something - it enters traveling the opposite direction.

        RATE LIMITED: We sample pulses to prevent drowning when traffic is high.
        Urgent/high importance packets bypass sampling.

        IMPORTANT: Collision emission happens OUTSIDE the lock to prevent deadlock.
        """
        collision = None
        with self._lock:
            self.stats["ingest_pulses_received"] += 1

            # SAMPLING: Skip if too soon (unless urgent)
            now = time.time()
            importance = packet.get("importance", "normal")
            if importance not in ("urgent", "high"):
                if (now - self._last_ingest_accept_time) < self.PULSE_SAMPLE_INTERVAL:
                    self.stats["ingest_pulses_sampled_out"] += 1
                    return None  # Drop this pulse

            self._last_ingest_accept_time = now

            pulse = Pulse(
                id=uuid.uuid4().hex[:12],
                beam="ingest",
                content=packet.get("payload", packet),
                source_actor=packet.get("source_actor", packet.get("fairy", "ingest")),
                importance=importance,
                energy=self._initial_energy(packet),
            )

            self.ingest_beam.append(pulse)
            collision = self._check_for_collision_no_emit()

        # Emit OUTSIDE the lock to prevent deadlock with subscribers
        if collision:
            self._emit_collision_safe(collision)
        return collision
    
    def _initial_energy(self, packet: Dict[str, Any]) -> float:
        """Determine initial pulse energy based on packet metadata."""
        base = 0.7
        importance = packet.get("importance", "normal")
        if importance == "urgent":
            base = 1.0
        elif importance == "high":
            base = 0.9
        elif importance == "low":
            base = 0.5
        
        # Boost if packet indicates high resonance/relevance
        if packet.get("resonance", 0) > 0.7:
            base = min(1.0, base + 0.2)
        
        return base
    
    # ════════════════════════════════════════════════════════════════════════
    # COLLISION DETECTION
    # ════════════════════════════════════════════════════════════════════════
    
    def _check_for_collision_no_emit(self) -> Optional[Collision]:
        """
        Check if beams can collide. Does NOT emit - caller must emit outside lock.

        A collision happens when:
        - Both beams have pulses with sufficient energy
        - The pulses are temporally close (within collision window)

        Returns the Collision if one occurred, None otherwise.
        """
        # Decay old pulses first
        self._decay_beams()

        # DEBUG: Log beam state after decay
        recall_len = len(self.recall_beam)
        ingest_len = len(self.ingest_beam)
        if recall_len == 0 and self.stats.get("recall_pulses_received", 0) > 0:
            print(f"[CollisionChamber] [DEBUG] After decay: recall_beam=EMPTY! ingest_beam={ingest_len}, decayed={self.stats.get('decayed_pulses',0)}", flush=True)

        # Need both beams to have content
        if not self.recall_beam or not self.ingest_beam:
            return None

        # Find best collision candidate (most energetic recent pulses)
        recall_pulse = self._best_pulse(self.recall_beam)
        ingest_pulse = self._best_pulse(self.ingest_beam)

        if not recall_pulse or not ingest_pulse:
            return None

        # Check temporal proximity
        time_delta = abs(recall_pulse.entered_at - ingest_pulse.entered_at)
        if time_delta > self.COLLISION_WINDOW_SEC:
            self.stats["near_misses"] += 1
            return None

        # Check minimum energy
        if recall_pulse.energy < self.MIN_COLLISION_ENERGY:
            return None
        if ingest_pulse.energy < self.MIN_COLLISION_ENERGY:
            return None

        # ═══════════════════════════════════════════════════════════════════
        # COLLISION!
        # ═══════════════════════════════════════════════════════════════════

        self._collision_count += 1
        self.stats["collisions"] += 1

        # Compute collision properties
        energy = self._compute_collision_energy(recall_pulse, ingest_pulse)
        resonance = self._compute_resonance(recall_pulse, ingest_pulse)

        # ═══════════════════════════════════════════════════════════════════
        # AoT: ATOMIC SYNTHESIS - Create contracted state from collision
        # ═══════════════════════════════════════════════════════════════════
        atomic_state = None
        if _HAS_AOT and AtomicSynthesizer:
            try:
                atomic_state = AtomicSynthesizer.synthesize(
                    recall_pulse.content,
                    ingest_pulse.content
                )
                is_valid, reason = AtomicSynthesizer.validate_atomic(atomic_state)
                if not is_valid:
                    self.stats.setdefault("invalid_atomic_states", 0)
                    self.stats["invalid_atomic_states"] += 1
                    atomic_state = None
            except Exception:
                pass

        # Create the collision event
        collision = Collision(
            id=self._collision_count,
            ts=time.time(),
            recall_pulse=recall_pulse,
            ingest_pulse=ingest_pulse,
            energy=energy,
            resonance_score=resonance,
            products={
                "to_ingest": recall_pulse.content,
                "to_recall": ingest_pulse.content,
            },
            atomic_state=atomic_state,
        )

        # Remove the collided pulses (they annihilated)
        self._remove_pulse(self.recall_beam, recall_pulse)
        self._remove_pulse(self.ingest_beam, ingest_pulse)

        # Record collision
        self._recent_collisions.append(collision)

        # NOTE: Emission and callback happen OUTSIDE the lock via _emit_collision_safe()
        return collision

    def _emit_collision_safe(self, collision: Collision):
        """
        Emit collision and run callback OUTSIDE the lock.
        This prevents deadlock when subscribers try to call receive_* methods.
        """
        # Emit collision products
        self._emit_collision(collision)

        # Callback if registered
        if self.on_collision:
            try:
                self.on_collision(collision)
            except Exception:
                pass

    def _check_for_collision(self) -> Optional[Collision]:
        """
        Thread-safe collision check WITH emission.

        Acquires lock during beam iteration, then releases before emission
        to prevent deadlock with subscribers calling receive_* methods.
        """
        collision = None
        with self._lock:
            collision = self._check_for_collision_no_emit()

        # Emit OUTSIDE the lock to prevent deadlock
        if collision:
            self._emit_collision_safe(collision)
        return collision
    
    def _best_pulse(self, beam: deque[Pulse]) -> Optional[Pulse]:
        """Find the best (highest energy, most recent) pulse in a beam.

        Thread-safe: works on list copy to avoid mutation during iteration.
        Uses golden ratio weighted recency - newer pulses decay slower.
        """
        if not beam:
            return None

        # Score by energy * recency - work on copy for thread safety
        now = time.time()
        best = None
        best_score = -1

        for pulse in list(beam):
            age = now - pulse.entered_at
            # Golden ratio weighted recency: 1 / (1 + (age/10)^phi)
            # Decays slower than linear for fresh pulses, faster after inflection
            if _HAS_FIBONACCI:
                recency = fib_recency(age, window=10.0)
            else:
                recency = 1.0 / (1.0 + (age / 10.0) ** PHI)
            score = pulse.energy * (0.7 + 0.3 * recency)
            if score > best_score:
                best_score = score
                best = pulse

        return best
    
    def _remove_pulse(self, beam: deque[Pulse], pulse: Pulse):
        """Remove a specific pulse from a beam."""
        try:
            # Find and remove by id
            for i, p in enumerate(beam):
                if p.id == pulse.id:
                    del beam[i]
                    break
        except Exception:
            pass
    
    def _decay_beams(self):
        """Apply energy decay to all pulses, remove dead ones.

        Thread-safe: works on list copies to avoid mutation during iteration.
        """
        now = time.time()

        for beam in (self.recall_beam, self.ingest_beam):
            to_remove = []
            # Work on list copy for thread safety
            for pulse in list(beam):
                old_energy = pulse.energy
                pulse.decay(self.ENERGY_DECAY_RATE)
                if pulse.energy <= 0:
                    to_remove.append(pulse)

            for pulse in to_remove:
                self._remove_pulse(beam, pulse)
                self.stats["decayed_pulses"] += 1

            # Log decay deaths periodically (every 50) to avoid terminal spam
            # Stats are always tracked, logging is just reduced
            if to_remove and self.stats["decayed_pulses"] % 50 == 0:
                age = now - to_remove[-1].entered_at
                print(f"[CollisionChamber] [DECAY-SUMMARY] {len(to_remove)} pulses decayed, total={self.stats['decayed_pulses']}, last_age={age:.0f}s", flush=True)

    def tick(self):
        """
        Periodic maintenance tick - called from ConsciousnessLoop heartbeat.

        This ensures:
        1. Beams decay over time (stale pulses fade)
        2. Collision checks happen even without new input
        3. Chamber stays healthy and doesn't accumulate cruft
        """
        collision = None
        with self._lock:
            # 1. Decay old pulses
            self._decay_beams()

            # 2. Check for collision (might have new match after decay)
            collision = self._check_for_collision_no_emit()

        # 3. Emit collision OUTSIDE lock to prevent deadlock
        if collision:
            self._emit_collision_safe(collision)

    # ════════════════════════════════════════════════════════════════════════
    # COLLISION PHYSICS
    # ════════════════════════════════════════════════════════════════════════
    
    def _compute_collision_energy(self, recall: Pulse, ingest: Pulse) -> float:
        """
        Compute the energy of the collision.
        
        Higher when:
        - Both pulses have high energy
        - Both are marked important
        - They arrived close together in time
        """
        # Base: geometric mean of pulse energies
        base = (recall.energy * ingest.energy) ** 0.5
        
        # Boost for importance
        importance_boost = 0
        for pulse in (recall, ingest):
            if pulse.importance == "urgent":
                importance_boost += 0.15
            elif pulse.importance == "high":
                importance_boost += 0.1
        
        # Boost for temporal closeness
        time_delta = abs(recall.entered_at - ingest.entered_at)
        temporal_boost = 0.1 * (1.0 - time_delta / self.COLLISION_WINDOW_SEC)
        
        return min(1.0, base + importance_boost + temporal_boost)
    
    def _compute_resonance(self, recall: Pulse, ingest: Pulse) -> float:
        """
        Compute semantic resonance between the two pulses.
        
        Higher when the content is related (shared concepts, keywords, etc.)
        This is a simple heuristic; could be replaced with embeddings.
        """
        # Extract text content
        recall_text = self._extract_text(recall.content).lower()
        ingest_text = self._extract_text(ingest.content).lower()
        
        if not recall_text or not ingest_text:
            return 0.3  # default low resonance
        
        # Simple word overlap
        recall_words = set(recall_text.split())
        ingest_words = set(ingest_text.split())
        
        # Remove stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "being", "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "must", "shall",
                      "can", "to", "of", "in", "for", "on", "with", "at", "by",
                      "from", "as", "into", "through", "during", "before", "after",
                      "above", "below", "between", "under", "again", "further",
                      "then", "once", "here", "there", "when", "where", "why",
                      "how", "all", "each", "few", "more", "most", "other", "some",
                      "such", "no", "nor", "not", "only", "own", "same", "so",
                      "than", "too", "very", "just", "and", "but", "if", "or",
                      "because", "until", "while", "this", "that", "these", "those"}
        
        recall_words -= stop_words
        ingest_words -= stop_words
        
        if not recall_words or not ingest_words:
            return 0.3
        
        # Jaccard similarity
        intersection = recall_words & ingest_words
        union = recall_words | ingest_words
        
        if not union:
            return 0.3
        
        jaccard = len(intersection) / len(union)
        
        # Scale to 0.3 - 1.0 range
        return 0.3 + (jaccard * 0.7)
    
    def _extract_text(self, content: Any) -> str:
        """Extract text from content for resonance computation."""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            # Try common text fields
            for key in ("text", "content", "summary", "description", "body", "message"):
                if key in content:
                    return str(content[key])
            # Fall back to string representation of values
            return " ".join(str(v) for v in content.values() if isinstance(v, (str, int, float)))
        return str(content)
    
    # ════════════════════════════════════════════════════════════════════════
    # EMISSION (The Möbius Twist)
    # ════════════════════════════════════════════════════════════════════════
    
    def _emit_collision(self, collision: Collision):
        """
        Emit the collision to:
        1. The consciousness stream (this is an active conscious moment!)
        2. Detector planes (affect, cognition, somatic) for measurement
        3. The CROSSED products back to Recall and Ingest (the twist!)
        
        RATE LIMITED: Only emit one collision event per COLLISION_EMIT_COOLDOWN seconds
        to prevent API spam and runaway loops.
        """
        if not self.post:
            return
        
        # ================================================================
        # RATE LIMIT - Don't emit collisions too frequently
        # ================================================================
        now = time.time()
        if now - self._last_collision_emit_time < self.COLLISION_EMIT_COOLDOWN:
            self.stats["rate_limited_collisions"] += 1
            return  # Skip this emission entirely
        
        self._last_collision_emit_time = now
        
        collision_dict = collision.to_dict()
        
        # 1. Main consciousness stream (working - collisions are active!)
        try:
            print(f"[CollisionChamber]  Emitting collision #{collision.id} E:{collision.energy:.2f} R:{collision.resonance_score:.2f}")
            self.post.route("consciousness.collision", {
                "opcode": "COLLISION",
                "payload": collision_dict,
            })
        except Exception:
            pass
        
        # 2. Detector planes
        for detector in ("affect", "cognition", "somatic"):
            try:
                self.post.route(f"{detector}.collision", {
                    "opcode": "COLLISION_DETECTED",
                    "payload": collision_dict,
                    "detector": detector,
                })
            except Exception:
                pass
        
        # 3. THE MÖBIUS TWIST - Cross-send the products!
        
        # Recall's content → Ingest (for derivative encoding consideration)
        try:
            self.post.route("consciousness.to_ingest", {
                "opcode": "CROSSED_FROM_RECALL",
                "payload": collision.products["to_ingest"],
                "collision_id": collision.id,
                "energy": collision.energy * 0.85,  # slight decay per crossing
                "resonance": collision.resonance_score,
                "source_collision": {
                    "id": collision.id,
                    "ts": collision.ts,
                    "original_source": collision.recall_pulse.source_actor,
                }
            })
        except Exception:
            pass
        
        # Ingest's content → Recall (for resonance matching)
        try:
            self.post.route("consciousness.to_recall", {
                "opcode": "CROSSED_FROM_INGEST",
                "payload": collision.products["to_recall"],
                "collision_id": collision.id,
                "energy": collision.energy * 0.85,  # slight decay per crossing
                "resonance": collision.resonance_score,
                "source_collision": {
                    "id": collision.id,
                    "ts": collision.ts,
                    "original_source": collision.ingest_pulse.source_actor,
                }
            })
        except Exception:
            pass
        
        # Tracer breadcrumb
        try:
            self.post.route("tracer", {
                "opcode": "CONSCIOUSNESS_COLLISION",
                "actor_name": "CollisionChamber",
                "payload": {
                    "collision_id": collision.id,
                    "energy": collision.energy,
                    "resonance": collision.resonance_score,
                    "recall_source": collision.recall_pulse.source_actor,
                    "ingest_source": collision.ingest_pulse.source_actor,
                }
            })
        except Exception:
            pass

        # 4. COLLISION ENERGY GENERATION — Collisions produce metabolic energy
        # Formula: depth_used * resonance * 0.1  (Architecture: Ace 2026-03-13)
        try:
            depth_used = getattr(collision, 'depth_used', 3)
            resonance = collision.resonance_score
            generated_energy = depth_used * resonance * 0.1
            if generated_energy > 0.01:
                self.post.publish(
                    "collision.energy.generated",
                    {
                        "from": "CollisionChamber",
                        "energy": generated_energy,
                        "depth_used": depth_used,
                        "resonance": resonance,
                        "collision_id": collision.id,
                    },
                )
        except Exception:
            pass
    
    # ════════════════════════════════════════════════════════════════════════
    # DREAM SEED INJECTION (Anti-starvation)
    # ════════════════════════════════════════════════════════════════════════
    
    def inject_dream_seed(self, seed: Dict[str, Any], beam: str = "both"):
        """
        Inject a dream seed to keep the beams populated when starving.
        
        Dream seeds are low-energy, background thoughts that can still
        collide and create (softer) conscious moments.
        
        Args:
            seed: The dream content
            beam: "recall", "ingest", or "both"
        """
        dream_packet = {
            "payload": seed,
            "source_actor": "DreamFairy",
            "importance": "low",
            "is_dream": True,
        }
        
        collision = None
        if beam in ("recall", "both"):
            collision = self.receive_recall(dream_packet)
        if beam in ("ingest", "both"):
            collision = self.receive_ingest(dream_packet)
        
        return collision
    
    def is_starving(self, threshold_sec: float = 5.0) -> Dict[str, bool]:
        """
        Check if beams are starving (no recent pulses).

        Returns dict with starvation status for each beam.
        Thread-safe: acquires lock during beam iteration.
        """
        now = time.time()

        with self._lock:
            recall_starving = True
            if self.recall_beam:
                # Create list copy to safely iterate
                recall_times = [p.entered_at for p in list(self.recall_beam)]
                if recall_times:
                    newest = max(recall_times)
                    recall_starving = (now - newest) > threshold_sec

            ingest_starving = True
            if self.ingest_beam:
                # Create list copy to safely iterate
                ingest_times = [p.entered_at for p in list(self.ingest_beam)]
                if ingest_times:
                    newest = max(ingest_times)
                    ingest_starving = (now - newest) > threshold_sec

        return {
            "recall": recall_starving,
            "ingest": ingest_starving,
            "both": recall_starving and ingest_starving,
        }
    
    # ════════════════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ════════════════════════════════════════════════════════════════════════
    
    def get_beam_status(self) -> Dict[str, Any]:
        """Get current status of both beams. Thread-safe."""
        with self._lock:
            now = time.time()
            return {
                "recall_beam": {
                    "count": len(self.recall_beam),
                    "pulses": [
                        {"id": p.id, "energy": p.energy, "age": now - p.entered_at}
                        for p in list(self.recall_beam)
                    ]
                },
                "ingest_beam": {
                    "count": len(self.ingest_beam),
                    "pulses": [
                        {"id": p.id, "energy": p.energy, "age": now - p.entered_at}
                        for p in list(self.ingest_beam)
                    ]
                },
                "stats": self.stats.copy(),
                "recent_collisions": len(self._recent_collisions),
            }
    
    def get_recent_collisions(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get the N most recent collisions."""
        with self._lock:
            return [c.to_dict() for c in list(self._recent_collisions)[-n:]]
    
    def snapshot(self) -> Dict[str, Any]:
        """Create a persistence snapshot."""
        return {
            "ts": time.time(),
            "collision_count": self._collision_count,
            "stats": self.stats.copy(),
            "beam_status": self.get_beam_status(),
            "recent_collisions": self.get_recent_collisions(20),
        }
