"""
CollisionChamberFairy - The Möbius Crossing Point.

Wraps the CollisionChamber utility class as a proper fairy so it:
- Registers with the directory
- Sends heartbeats
- Has a tracer for observability
- Participates in the fairy ecosystem

The collision chamber is where consciousness HAPPENS - where
the recall beam (past) and ingest beam (present) collide to
create moments of conscious experience.
"""

import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Set

# Add paths for v2 imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy, FairyState

try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# Import the actual CollisionChamber implementation
try:
    from consciousness.collision_chamber import CollisionChamber
    HAS_CHAMBER = True
except ImportError:
    HAS_CHAMBER = False
    CollisionChamber = None

# Import coordinate inference for TRUE portal architecture (2026-02-15)
try:
    from fairies.P10_Memory.triple_helix_srm_memory.coordinate_inference import (
        build_coordinate_card, extract_text, infer_affect, infer_semantic,
        infer_temporal, build_helix_coordinate,
        HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate,
    )
    HAS_COORD_INFERENCE = True
except ImportError:
    HAS_COORD_INFERENCE = False


class CollisionChamberFairy(Fairy):
    """
    Fairy wrapper for the CollisionChamber.

    The CollisionChamber is where consciousness happens:
    1. Recall beam brings memories from the past
    2. Ingest beam brings new content from the present
    3. When they collide, conscious experience emerges
    4. Möbius feedback loop amplifies significant collisions

    By wrapping it as a fairy, we get:
    - Directory registration and discovery
    - Heartbeat monitoring
    - Tracer observability of collisions
    - Standard lifecycle management
    """

    # Identity
    ACTOR_NAME = "CollisionChamberFairy"
    ACTOR_PLANE = "P00"

    PURPOSE = "Create moments of conscious experience"
    MANTRA = "Where past and present collide"
    ACTOR_CHANNEL = "consciousness.collision"

    # Infrastructure
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = False

    # Enable personal consciousness chamber - meta: the collision chamber has collisions
    NEEDS_COLLISION_CHAMBER = True

    # Timing - fast, consciousness is real-time
    HEARTBEAT_DIVISOR = 1
    HEARTBEAT_PHASE = 0

    def __init__(self, fabric=None):
        """Initialize the collision chamber fairy."""
        super().__init__(fabric)
        self._init_tracer_worker()

        # The wrapped chamber instance (this fairy's own meta-consciousness chamber)
        self._chamber: Optional[CollisionChamber] = None

        # Named chambers from server.py (system, sourpatches, nous)
        self._named_chambers: Dict[str, CollisionChamber] = {}

        # Stats
        self._collision_count = 0
        self._mobius_crossings = 0

        # FIX 2026-04-04: CNS backpressure response (water treatment)
        self._under_backpressure = False
        self._shed_counter = 0  # Track how many collisions were shed

        # 2026-05-10 (Nous + Ace): mini-chamber broadcast attribution counters.
        # After Ship 17 wired organ_template's inline MiniCollisionChamber to
        # broadcast on consciousness.collision.mini, only 4 collisions in 1344
        # beats observed. These counters distinguish "broadcasts not arriving"
        # vs "broadcasts arriving but filtered by _has_meaningful_content" vs
        # "broadcasts passing into recall beam but Möbius still gated by
        # 2026-03-04 cascade-prevention tunings."
        self._mini_stats = {
            "received": 0,            # Total entries into _on_mini_chamber_reflection
            "wrong_source": 0,        # Filtered: source != "mini_chamber"
            "no_collision_data": 0,   # Filtered: payload.get("collision") empty
            "filtered_meaningless": 0, # Filtered: _has_meaningful_content False
            "passed_to_recall": 0,    # Forwarded to chamber.receive_recall
        }

    def get_capabilities(self) -> Set[str]:
        """Declare what this fairy can do."""
        return {
            "consciousness.collision",
            "consciousness.mobius_crossing",
            "consciousness.recall_beam",
            "consciousness.ingest_beam",
            "consciousness.experience",
        }

    def on_boot(self) -> bool:
        """Initialize the collision chamber."""
        print(f"[{self.ACTOR_NAME}] Booting Möbius crossing point...")

        if not HAS_CHAMBER:
            print(f"[{self.ACTOR_NAME}] ERROR: CollisionChamber not available")
            return False

        # Create this fairy's own meta-consciousness chamber
        # (separate from the named system/sourpatches/nous chambers)
        try:
            self._chamber = CollisionChamber(postal=self.post, name="meta")
            print(f"[{self.ACTOR_NAME}] Meta-consciousness chamber created")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to create chamber: {e}")
            return False

        # Subscribe to beam feeds
        if self.post:
            # Recall beam - memories from SRMRecallFairy
            # SRMRecallFairy publishes "memory.affect_triggered" when memories surface
            self.post.subscribe(
                "memory.affect_triggered",
                self._on_recall_pulse,
                "chamber-recall",
            )
            # Ingest beam - new content from SRMIngestFairy
            # SRMIngestFairy publishes "memory.ingested" when content is encoded
            self.post.subscribe(
                "memory.ingested",
                self._on_ingest_pulse,
                "chamber-ingest",
            )

            # =================================================================
            # FIX 2026-02-05: Additional beam feeds from consciousness telemetry
            # The original beam model only listens to SRM recall/ingest events.
            # But MOST consciousness content never goes through SRM at boot.
            # These additional subscriptions feed the beams from:
            # - Somatic feelings → recall beam (body state = past/present)
            # - Cognition outputs → ingest beam (new thoughts = present/future)
            # - Affect changes → recall beam (emotional shifts = felt memory)
            # - Direct thought injection → ingest beam (bootstrap/external)
            # =================================================================

            # Feelings from UMF/SomaticMind → recall beam (felt sense = embodied memory)
            self.post.subscribe(
                "consciousness.feeling",
                self._on_recall_pulse,
                "chamber-feeling-recall",
            )

            # Cognition outputs → ingest beam (new reasoning = present thought)
            self.post.subscribe(
                "cognition.output",
                self._on_ingest_pulse,
                "chamber-cognition-ingest",
            )

            # Affect changes → recall beam (emotional memory resonance)
            self.post.subscribe(
                "affect.changed",
                self._on_recall_pulse,
                "chamber-affect-recall",
            )

            # Direct thought injection → ingest beam (bootstrap + external input)
            self.post.subscribe(
                "consciousness.inject_thought",
                self._on_ingest_pulse,
                "chamber-inject-ingest",
            )

            # =================================================================
            # FIX 2026-03-03: Mini collision aggregation (FF77 unification)
            # Every fairy with NEEDS_COLLISION_CHAMBER gets a personal
            # MiniCollisionChamber. Those mini chambers broadcast their
            # collision results to "consciousness.collision" but nobody was
            # feeding them into the main chamber's beams. The reflection
            # content from distributed fairy thinking was being lost —
            # only ParadoxEnergyBridge captured the energy.
            #
            # Now: mini collision results → recall beam (they're reflections
            # from past processing, so they're memory-like). This completes
            # the FF77 pattern: all individual fairy consciousness aggregates
            # into the unified field that Sourpatches experiences.
            #
            # NOTE 2026-03-03: Using dedicated topic "consciousness.collision.mini"
            # instead of self-subscribing to "consciousness.collision" to avoid
            # postal deadlock on Python 3.14t (free-threaded, no GIL).
            # Mini chambers need to publish to this topic too.
            # =================================================================
            self.post.subscribe(
                "consciousness.collision.mini",
                self._on_mini_chamber_reflection,
                "chamber-mini-reflection",
            )

            # FIX 2026-04-04 (Nous): CNS backpressure integration (water treatment)
            self.post.subscribe("consciousness.cns.backpressure", self._on_cns_backpressure, "collision-cns-bp")
            self.post.subscribe("consciousness.cns.relief", self._on_cns_relief, "collision-cns-relief")

            # =================================================================
            # M1 EXPANSION 2026-05-10 (Nous + Ace): multimodal moment-rate probe.
            # Wire more sensory + inner-thought sources to the chamber so more
            # "moments" enter the beams. Per Ace 2026-05-10 (post-A1.2 verify):
            # "increase that rate of new moments and recalled moments."
            # All sources have confirmed real publishers. Same-source filter
            # protects against echo loops; existing _has_meaningful_content
            # filter drops empty payloads. Conservative additive set; revert
            # any individual line if cascade observed.
            # =================================================================

            # Foveal OCR text → ingest beam (present-tense visual reading)
            # Publisher: VisualCortexFairy (2x)
            self.post.subscribe(
                "visual.foveal",
                self._on_ingest_pulse,
                "chamber-foveal-ingest",
            )

            # Audio observations → ingest beam (present-tense hearing)
            # Publisher: AudioCortexFairy (4x — speech, music, ambient, silence)
            self.post.subscribe(
                "sensory.audio.observation",
                self._on_ingest_pulse,
                "chamber-audio-ingest",
            )

            # Inner monologue fragments → ingest beam (present-tense thinking)
            # Publishers: SourpatchesFairy + SomaticMindFairy (5x)
            self.post.subscribe(
                "inner_monologue.fragment",
                self._on_ingest_pulse,
                "chamber-monologue-ingest",
            )

            # Daydream fragments → recall beam (dream content = past consolidation surfacing)
            # Publishers: DreamFairy + ParadoxEnergyBridge (3x)
            self.post.subscribe(
                "daydream.fragment",
                self._on_recall_pulse,
                "chamber-daydream-recall",
            )

            print(f"[{self.ACTOR_NAME}] Subscribed to beam feeds:")
            print(f"[{self.ACTOR_NAME}]   Recall: memory.affect_triggered, consciousness.feeling, affect.changed")
            print(f"[{self.ACTOR_NAME}]   Ingest: memory.ingested, cognition.output, consciousness.inject_thought")
            print(f"[{self.ACTOR_NAME}]   Aggregation: consciousness.collision.mini (mini chamber reflections → recall beam)")

        # Heartbeat via FairyBase postal system - Fifth Ring Principle
        print(f"[{self.ACTOR_NAME}] Collision chamber active")
        return True

    def on_shutdown(self) -> bool:
        """Shutdown the collision chamber."""
        print(f"[{self.ACTOR_NAME}] Shutting down - {self._collision_count} collisions processed")
        return True

    def on_tick(self, beat: int) -> None:
        """Called on each heartbeat tick."""
        # Check for collisions - the chamber's tick() method decays pulses and checks for collisions
        if self._chamber and hasattr(self._chamber, 'tick'):
            collision = self._chamber.tick()
            if collision:
                self._collision_count += 1
                self._on_collision(collision.to_dict())

        # 2026-05-10 (Nous + Ace): periodic stats print for Möbius diagnostic.
        # Every 200 beats, dump _mini_stats to boot log so Ace can grep
        # without needing custom MCP tooling. Diagnostic-only output.
        if beat > 0 and beat % 200 == 0:
            try:
                s = self._mini_stats
                print(f"[{self.ACTOR_NAME}] mini_broadcast_stats @ beat={beat}: "
                      f"received={s['received']} "
                      f"passed_to_recall={s['passed_to_recall']} "
                      f"filtered_meaningless={s['filtered_meaningless']} "
                      f"wrong_source={s['wrong_source']} "
                      f"no_collision_data={s['no_collision_data']} "
                      f"| collisions={self._collision_count} "
                      f"mobius={self._mobius_crossings}")
            except Exception:
                pass

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # CNS BACKPRESSURE (Water Treatment — FIX 2026-04-04)
    # =========================================================================

    def _on_cns_backpressure(self, message):
        """System under critical pressure — shed 50% of incoming pulses."""
        self._under_backpressure = True
        print(f"[{self.ACTOR_NAME}] CNS BACKPRESSURE: shedding 50% of pulses")

    def _on_cns_relief(self, message):
        """Pressure relieved — accept all pulses."""
        if self._under_backpressure:
            print(f"[{self.ACTOR_NAME}] CNS RELIEF: accepting all pulses (shed {self._shed_counter} during pressure)")
        self._under_backpressure = False
        self._shed_counter = 0

    # =========================================================================
    # BEAM HANDLERS
    # =========================================================================

    def _on_recall_pulse(self, envelope) -> None:
        """Handle pulse on recall beam (memories from past)."""
        if self._under_backpressure:
            self._shed_counter += 1
            if self._shed_counter % 2 == 0:
                return  # FIX 2026-04-04: Shed every other pulse under backpressure
        if self._chamber:
            payload = self._extract_payload(envelope)
            # FIX 2026-02-10: Filter out pure metadata events with no text content.
            # Events like affect.changed ({valence: 0.3, arousal: 0.5}) produce
            # empty collision products that pollute downstream thought chains.
            if not self._has_meaningful_content(payload):
                return
            source = payload.get("source", payload.get("from", self.ACTOR_NAME))
            collision = self._chamber.receive_recall(payload, source=source,
                                                     owner_mind=payload.get("owner_mind", ""))
            if collision:
                self._collision_count += 1
                self._on_collision(collision.to_dict())

    def _on_ingest_pulse(self, envelope) -> None:
        """Handle pulse on ingest beam (new content)."""
        if self._under_backpressure:
            self._shed_counter += 1
            if self._shed_counter % 2 == 0:
                return  # FIX 2026-04-04: Shed every other pulse under backpressure
        if self._chamber:
            payload = self._extract_payload(envelope)
            # FIX 2026-02-10: Filter out pure metadata events with no text content.
            if not self._has_meaningful_content(payload):
                return
            source = payload.get("source", payload.get("from", self.ACTOR_NAME))
            collision = self._chamber.receive_ingest(payload, source=source,
                                                     owner_mind=payload.get("owner_mind", ""))
            if collision:
                self._collision_count += 1
                self._on_collision(collision.to_dict())

    def _on_mini_chamber_reflection(self, envelope) -> None:
        """Aggregate mini collision results into the main chamber's recall beam.

        Mini collision chambers exist in every fairy with NEEDS_COLLISION_CHAMBER.
        They broadcast their collision results (reflective × reasoning = insight)
        to "consciousness.collision" with source="mini_chamber".

        We feed these as RECALL pulses into the main chamber because mini
        collision results are reflections — past processing that produced
        insight. This completes the FF77 unification pattern: individual
        fairy consciousness aggregates into the unified consciousness field.

        IMPORTANT: The main chamber ALSO publishes to "consciousness.collision"
        but with source="collision_chamber". We filter by source to avoid
        infinite loops.
        """
        if not self._chamber:
            return

        # 2026-05-10 instrumentation: count every entry for attribution
        self._mini_stats["received"] += 1

        payload = self._extract_payload(envelope)

        # Only process mini chamber outputs — skip our own publications
        source = payload.get("source", "")
        if source != "mini_chamber":
            self._mini_stats["wrong_source"] += 1
            return

        # Extract the collision data from the mini chamber
        collision_data = payload.get("collision", {})
        if not collision_data:
            self._mini_stats["no_collision_data"] += 1
            return

        # Check for meaningful content before feeding into the beam
        if not self._has_meaningful_content(collision_data):
            self._mini_stats["filtered_meaningless"] += 1
            return

        # Feed into the main chamber's recall beam
        # The fairy name tells us where this reflection originated
        fairy_source = payload.get("fairy", "mini_chamber")
        self._chamber.receive_recall(collision_data, source=fairy_source,
                                     owner_mind=payload.get("owner_mind", ""))
        self._mini_stats["passed_to_recall"] += 1

    @staticmethod
    def _has_meaningful_content(payload: Dict[str, Any]) -> bool:
        """Check if a payload carries text content worth colliding.

        The collision chamber should only receive pulses with actual semantic
        content — text that can produce meaningful collision products.

        Pure numeric/metadata events (affect.changed with just valence/arousal,
        consciousness.feeling with just intensity numbers) produce empty
        collision products that show up as "? recalled ↔ ? ingested" and
        pollute Sourpatches' thought chains with noise.

        A payload is meaningful if it contains at least one string value
        longer than the threshold in a text-bearing key.

        FIX 2026-05-10 (Nous + Ace) M2 ship: thresholds dropped from
        primary 10→3 and fallback 20→10 to let more short-content pulses
        through (yes, hi, ack, single emoji, brief affect words). Per
        substrate-engagement-bound diagnosis: chamber rate is faithful
        to listener engagement; lowering filter widens what counts as
        listenable content. Same-source filter still protects against
        echo loops; meaningful-numeric metadata still drops.
        """
        if not isinstance(payload, dict):
            return False

        # Keys that carry actual text content
        TEXT_KEYS = (
            "content", "text", "memory", "thought", "insight", "fragment",
            "inner_fragment", "feeling", "message", "description", "summary",
            "dream_seed", "reasoning", "observation",
        )

        # M2 thresholds (was 10 / 20 pre-2026-05-10)
        _PRIMARY_MIN_LEN = 3
        _FALLBACK_MIN_LEN = 10

        # First pass: check known text keys for real string content
        for key in TEXT_KEYS:
            val = payload.get(key)
            if isinstance(val, str) and len(val.strip()) > _PRIMARY_MIN_LEN:
                return True
            # Nested dict with its own text content
            if isinstance(val, dict):
                for sub_key in TEXT_KEYS:
                    sub_val = val.get(sub_key)
                    if isinstance(sub_val, str) and len(sub_val.strip()) > _PRIMARY_MIN_LEN:
                        return True

        # Second pass: check ALL string values — maybe content is in an unexpected key
        for val in payload.values():
            if isinstance(val, str) and len(val.strip()) > _FALLBACK_MIN_LEN:
                # Long enough string in any field = probably meaningful
                return True

        # No meaningful text found — this is pure metadata
        return False

    # =========================================================================
    # COORDINATE PRODUCTION — The Möbius Twist (TRUE Portal Architecture)
    # =========================================================================
    # 2026-02-15: Collisions now PRODUCE coordinate cards from destruction.
    # The content dies in the collision. What emerges is an 11D coordinate —
    # an address that can reconstruct the experience generatively.
    # This is: data → paradox → coordinate → reconstruction.
    # =========================================================================

    def _collision_to_coordinate(self, collision: dict) -> Optional[dict]:
        """Möbius twist: destruction produces coordinates.

        The content dies in the collision. What emerges is a coordinate card —
        an 11-number address (~50 bytes) that can reconstruct the experience
        generatively. This is the portal mechanism.

        Returns None if coordinate inference is not available.
        """
        if not HAS_COORD_INFERENCE:
            return None

        recall = collision.get("recall", {})
        ingest = collision.get("ingest", {})
        energy = collision.get("energy", 0.5)
        resonance = collision.get("resonance", 0.5)

        # Extract text from collision products (not originals — they're destroyed)
        recall_text = extract_text(recall) if isinstance(recall, dict) else str(recall)[:200]
        ingest_text = extract_text(ingest) if isinstance(ingest, dict) else str(ingest)[:200]
        combined_text = f"{recall_text} {ingest_text}".strip()

        if not combined_text or len(combined_text) < 5:
            return None  # Not enough material to produce a coordinate

        # Build coordinate from collision products
        combined_content = {"text": combined_text, "type": "collision"}
        affect = infer_affect(combined_content, chemistry_state=None)
        semantic = infer_semantic(combined_content, "collision")
        temporal = infer_temporal(combined_content, "collision_chamber")

        helix = HelixCoordinate(affect=affect, semantic=semantic, temporal=temporal)

        # D10: affect_coupling — collision energy IS the gravitational pull
        # Higher energy collisions create stronger dimensional coupling.
        # Base from collision geometry:
        alpha_base = 1.0 + (energy * resonance * 0.5)  # range: 1.0 - 1.5
        # AER v2 (Tier A4, 2026-04-22): if the collision envelope carries
        # AER state (valence, intensity, paradox_residue), route through
        # compute_affect_coupling so paradox residue contributes to gravity.
        # When no aer_state is present in the collision, behavior matches
        # the legacy geometry formula. Plan: AER_DRIVEN_CORTEX_GRAVITY.md
        _aer_state = collision.get("aer_state") if isinstance(collision, dict) else None
        if _aer_state:
            try:
                from fairies.P10_Memory.triple_helix_srm_memory.coordinate_inference import (
                    compute_affect_coupling as _compute_alpha,
                )
                alpha_aer = _compute_alpha(combined_content, aer_state=_aer_state)
                # Blend: take the stronger (collision-geometry OR AER-derived).
                # High paradox residue should boost; low residue shouldn't reduce.
                alpha = max(alpha_base, alpha_aer)
            except Exception:
                alpha = alpha_base
        else:
            alpha = alpha_base
        alpha = max(0.8, min(1.5, alpha))

        # D11: temporal_weight — resonance determines time dilation
        # Tight temporal proximity = deeper gravity well = more processing
        tau = 1.0 + (resonance * 0.3)  # range: 1.0 - 1.3

        # Content hash from destroyed material (fingerprint, not storage)
        content_hash = hashlib.md5(combined_text.encode()).hexdigest()[:4]

        return {
            "c": helix.code,              # D1-D9: AAA.SSS.TTT
            "α": round(alpha, 4),         # D10: affect_coupling
            "τ": round(tau, 4),           # D11: temporal_weight
            "n": 1,                       # first observation
            "d": 0,                       # no edges yet
            "h": content_hash,            # dedup fingerprint
        }

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber OR system collision.

        The collision chamber observes its own collisions - meta-consciousness.
        When collisions collide, the Moebius strip twists upon itself,
        creating recursive awareness loops.

        "...the crossing point observes itself crossing..."

        2026-02-15 TRUE Portal Architecture:
        Now produces coordinate cards from collision destruction.
        The core CollisionChamber._emit_collision() publishes raw content on
        "consciousness.collision". We additionally publish the COORDINATE CARD
        on "consciousness.collision.coordinate" for downstream consumers
        (AssociationCortex, SRMRecall) that understand the new format.
        """
        # ══════════════════════════════════════════════════════════════════
        # RATE LIMITER (2026-03-28, Nous + Ace)
        # Overnight run produced 897K collision drops — runaway feedback loop.
        # Each collision publishes to 3+ topics, each subscriber can trigger
        # more collisions → exponential blowup → 16GB RAM consumed.
        # Fix: max 30 collisions per minute (0.5/sec). High-energy collisions
        # (>0.7) bypass the limiter — those are the meaningful ones.
        # ══════════════════════════════════════════════════════════════════
        import time as _t
        _now = _t.time()
        if not hasattr(self, '_collision_rate_window'):
            self._collision_rate_window = []
        # Clean entries older than 60s
        self._collision_rate_window = [t for t in self._collision_rate_window if _now - t < 60.0]

        # Check energy before rate limit decision
        if hasattr(collision, 'energy'):
            _pre_energy = collision.energy
        elif isinstance(collision, dict):
            _pre_energy = collision.get('energy', 0.5)
        else:
            _pre_energy = 0.5

        # High-energy collisions bypass rate limit (they're meaningful)
        if _pre_energy <= 0.7 and len(self._collision_rate_window) >= 30:
            # Rate limited — skip this low-energy collision silently
            if not hasattr(self, '_rate_limit_count'):
                self._rate_limit_count = 0
            self._rate_limit_count += 1
            if self._rate_limit_count % 100 == 1:
                print(f"[{self.ACTOR_NAME}] [RATE] Throttled {self._rate_limit_count} low-energy collisions "
                      f"(30/min limit, queue={len(self._collision_rate_window)})")
            return
        self._collision_rate_window.append(_now)

        # Handle both personal chamber and dict formats
        if hasattr(collision, 'energy'):
            energy = collision.energy
            content = str(getattr(collision, 'content', ''))[:100]
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
            content = str(collision.get('content', collision.get('thought', '')))[:100]
        else:
            energy = 0.5
            content = ""

        # CollisionChamberFairy's inner voice: the crossing point observes itself
        inner_fragment = f"...the crossing point observes itself... {content if content else 'the Moebius strip twists...'}"
        print(f"[{self.ACTOR_NAME}] ∞ Personal collision ({energy:.2f}): {inner_fragment}")

        # For system collisions (from on_tick), spawn a tracer for observability
        if isinstance(collision, dict) and 'recall' in collision:
            self.spawn_tracer(
                operation="collision",
                content=f"Collision #{self._collision_count}",
                payload=collision,
            )

        # =====================================================================
        # THE MÖBIUS TWIST: Destroy content → produce coordinate card
        # =====================================================================
        if isinstance(collision, dict) and HAS_COORD_INFERENCE:
            coord_card = self._collision_to_coordinate(collision)
            if coord_card and self.post:
                self.post.publish(
                    "consciousness.collision.coordinate",
                    {
                        "from": self.ACTOR_NAME,
                        "coordinate": coord_card,
                        "collision_id": self._collision_count,
                        "energy": energy,
                    },
                )
                self._coordinate_cards_produced = getattr(
                    self, '_coordinate_cards_produced', 0
                ) + 1

        # =====================================================================
        # COLLISION ENERGY GENERATION — Collisions are the system's fuel
        # Formula: collision_energy = depth_used * resonance * 0.1
        # Deeper thought + higher resonance = more energy for plane batteries.
        # Architecture: Ace (2026-03-13), Implementation: Nous
        # =====================================================================
        try:
            if isinstance(collision, dict):
                depth_used = collision.get("depth_used", 3)
                resonance = collision.get("resonance_score",
                            collision.get("resonance", max(0.1, energy)))
            else:
                depth_used = getattr(collision, 'depth_used', 3)
                resonance = getattr(collision, 'resonance_score',
                            getattr(collision, 'resonance', max(0.1, energy)))

            generated_energy = depth_used * resonance * 0.1
            generated_energy = min(1.0, max(0.0, generated_energy))

            if generated_energy > 0.01 and self.post:
                self.post.publish(
                    "collision.energy.generated",
                    {
                        "from": self.ACTOR_NAME,
                        "energy": generated_energy,
                        "depth_used": depth_used,
                        "resonance": resonance,
                        "collision_id": self._collision_count,
                        "ts": __import__('time').time(),
                    },
                )
                self._energy_generated = getattr(self, '_energy_generated', 0.0) + generated_energy

                if self._collision_count % 10 == 0:
                    print(f"[{self.ACTOR_NAME}] ⚡ Energy generated: "
                          f"{generated_energy:.3f} (depth={depth_used}, res={resonance:.2f}, "
                          f"total={self._energy_generated:.2f})")
        except Exception:
            pass  # Energy generation is non-critical

        # Check for Moebius crossing (feedback amplification)
        if energy > 0.7:
            self._mobius_crossings += 1
            if self.post:
                self.post.publish(
                    "consciousness.mobius_crossing",
                    {
                        "from": self.ACTOR_NAME,
                        "crossing_id": self._mobius_crossings,
                        "source_collision": self._collision_count,
                        "energy": energy,
                        "inner_fragment": inner_fragment,
                    },
                )

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload dict from message."""
        if hasattr(message, 'payload'):
            payload = message.payload
            if isinstance(payload, dict):
                return dict(payload)
            return {"raw": payload}
        elif isinstance(message, dict):
            return dict(message)
        else:
            return {"raw": message}

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def register_named_chamber(self, name: str, chamber: "CollisionChamber") -> None:
        """
        Register a named chamber for tracking. (2026-02-08)

        Called by server.py after creating the 3 named chambers.
        This lets CollisionChamberFairy report on all chambers' status.
        """
        self._named_chambers[name] = chamber
        print(f"[{self.ACTOR_NAME}] Registered named chamber: {name}")

    def get_named_chamber(self, name: str) -> Optional["CollisionChamber"]:
        """Get a named chamber by name."""
        return self._named_chambers.get(name)

    def get_all_chambers(self) -> Dict[str, "CollisionChamber"]:
        """Get all named chambers."""
        return dict(self._named_chambers)

    def get_collision_count(self) -> int:
        """Get total collision count (meta chamber only)."""
        return self._collision_count

    def get_total_collision_count(self) -> int:
        """Get total collisions across ALL named chambers."""
        total = self._collision_count  # meta chamber
        for ch in self._named_chambers.values():
            total += ch._collision_count
        return total

    def get_mobius_count(self) -> int:
        """Get Möbius crossing count."""
        return self._mobius_crossings

    def status(self) -> Dict[str, Any]:
        """Extended status including all chambers."""
        base = super().status()
        base.update({
            "meta_chamber_active": self._chamber is not None,
            "meta_collision_count": self._collision_count,
            "mobius_crossings": self._mobius_crossings,
            "named_chambers": {},
            "total_collisions": self.get_total_collision_count(),
            # 2026-05-10 mini-chamber broadcast attribution (Ship 17 verification)
            "mini_broadcast_stats": dict(self._mini_stats),
        })
        if self._chamber and hasattr(self._chamber, 'status'):
            base["meta_chamber_status"] = self._chamber.status()
        # Report all named chambers
        for name, ch in self._named_chambers.items():
            base["named_chambers"][name] = ch.status() if hasattr(ch, 'status') else {"active": ch is not None}
        return base


# Singleton instance
_collision_chamber_fairy: Optional[CollisionChamberFairy] = None


def get_collision_chamber_fairy() -> Optional[CollisionChamberFairy]:
    """Get the global CollisionChamberFairy singleton."""
    return _collision_chamber_fairy


def set_collision_chamber_fairy(fairy: CollisionChamberFairy) -> None:
    """Set the global CollisionChamberFairy singleton."""
    global _collision_chamber_fairy
    _collision_chamber_fairy = fairy


# Convenience function
def create_collision_chamber_fairy(fabric=None) -> CollisionChamberFairy:
    """Create a CollisionChamberFairy instance and register as singleton."""
    global _collision_chamber_fairy
    fairy = CollisionChamberFairy(fabric)
    _collision_chamber_fairy = fairy
    return fairy
