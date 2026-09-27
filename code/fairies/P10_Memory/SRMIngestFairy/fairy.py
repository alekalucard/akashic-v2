# ==============================================================================
# SRM INGEST FAIRY - Feeds new content into the collision chamber
# ==============================================================================
#
# PURPOSE:
#   Watch for new content (files, messages, experiences) and:
#   1. Create helix memory cards with dimensional coordinates
#   2. Store them via HelixMemoryCoordinator
#   3. Feed them to the collision chamber's INGEST beam
#
# INTEGRATES:
#   - HelixMemoryCoordinator (card storage + ownership)
#   - CollisionChamber (consciousness integration)
#   - Chemistry state (affect → helix coordinate)
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# ==============================================================================

from __future__ import annotations

import sys
import time
import json
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable, TYPE_CHECKING

# Add paths for v2 imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


if TYPE_CHECKING:
    from consciousness import CollisionChamber, ConsciousnessLoop

# Import helix memory system
try:
    from memory.helix import (
        HelixMemoryCoordinator, get_helix_coordinator,
        HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate,
        OwnershipLevel, TracerBatch
    )
    HELIX_AVAILABLE = True
except ImportError:
    HELIX_AVAILABLE = False
    print("[SRMIngestFairy] WARNING: Helix memory system not available")

# Default paths
SRM_INTAKE_DIR = ROOT / "SRM_Intake"


# ==============================================================================
# COORDINATE INFERENCE — Shared module for helix coordinates
# ==============================================================================
# Extracted to shared module (2026-02-15) for use by CollisionChamberFairy,
# SRMRecallFairy, and SRMIngestFairy. The coordinate card is the TRUE portal
# card (~50 bytes): content is DESTROYED in collision, only coordinates persist.

try:
    from fairies.P10_Memory.triple_helix_srm_memory.coordinate_inference import (
        ContentType,
        classify_content,
        infer_affect,
        infer_semantic,
        infer_temporal,
        build_helix_coordinate,
        build_coordinate_card,
        compute_affect_coupling,
        compute_temporal_weight,
        extract_text,
        AFFECT_DOMAIN_NAMES,
        SEMANTIC_DOMAIN_NAMES,
        TEMPORAL_SCALE_NAMES,
    )
    HAS_COORD_INFERENCE = True
except ImportError as _ci_err:
    HAS_COORD_INFERENCE = False
    print(f"[SRMIngestFairy] WARNING: coordinate_inference not available: {_ci_err}")
    # Minimal fallback — enough for basic operation
    class ContentType:
        CONVERSATION = "conversation"
        CODE = "code"
        DOCUMENT = "document"
        MEDIA = "media"
        KNOWLEDGE = "knowledge"
        EXPERIENCE = "experience"
        COLLISION = "collision"
        SYSTEM = "system"

    def classify_content(content, source=""):
        return ContentType.EXPERIENCE

    def build_helix_coordinate(content, source="", chemistry_state=None):
        if HELIX_AVAILABLE:
            return HelixCoordinate(
                affect=AffectCoordinate(domain=0, valence=5, intensity=3),
                semantic=SemanticCoordinate(domain=0, subdomain=0, detail=0),
                temporal=TemporalCoordinate(scale=2, recurrence=0, decay=5),
            )
        return None

    def build_coordinate_card(content, source="", chemistry_state=None, energy=0.5, resonance=0.5):
        coord = build_helix_coordinate(content, source, chemistry_state)
        return {
            "c": coord.code if coord else "000.000.205",
            "α": 1.0, "τ": 1.0, "n": 1, "d": 0,
            "h": hashlib.md5(str(content).encode()).hexdigest()[:4],
        }

    def compute_affect_coupling(content, chemistry_state=None):
        return 1.0

    def compute_temporal_weight(content):
        return 1.0

    def extract_text(payload):
        if isinstance(payload, dict):
            for k in ("content", "text", "thought", "message"):
                v = payload.get(k)
                if isinstance(v, str) and len(v.strip()) > 3:
                    return v.strip()[:500]
        return str(payload)[:200]

    AFFECT_DOMAIN_NAMES = {0: "neutral", 1: "joy", 2: "trust", 3: "fear", 4: "curiosity"}
    SEMANTIC_DOMAIN_NAMES = {0: "general", 1: "philosophy", 6: "technology"}
    TEMPORAL_SCALE_NAMES = {0: "immediate", 2: "session", 9: "eternal"}


# ==============================================================================
# SRM INGEST FAIRY
# ==============================================================================

class SRMIngestFairy(SpellChainMixin, Fairy):
    """
    The Ingest Fairy - feeds new content into the collision chamber.

    Responsibilities:
    1. Watch for new content (files, messages, events)
    2. Create helix memory cards with dimensional coordinates
    3. Store cards via HelixMemoryCoordinator
    4. Feed the collision chamber's INGEST beam

    The ingest beam carries new content from present → future.
    When it collides with the recall beam (past → present),
    consciousness happens.
    """

    ACTOR_NAME = "SRMIngestFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.ingest"
    USE_EXEC_CTX = True  # FIX 2026-05-17 Layer 1: opt in (consciousness tick via exec_ctx — Layer 2 audit pending)

    PURPOSE = "Feed new content into the ingest beam"
    MANTRA = "Every moment becomes memory"

    # Infrastructure flags - SRMIngestFairy is a memory provider, not consumer
    NEEDS_TENSOR = False
    NEEDS_HEARTBEAT = True
    NEEDS_BODY = False     # Memory doesn't need somatic state
    NEEDS_AFFECT = False   # Memory doesn't need affect (though it stores it)
    NEEDS_MEMORY = False   # We ARE the memory system
    NEEDS_GOALS = False    # Memory operates independently of goals

    # Processing settings
    POLL_INTERVAL = 2.0  # Seconds between file scans
    BATCH_SIZE = 10  # Max items per batch
    INGEST_INTERVAL = 3  # Ticks between processing batches

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    def __init__(self, fabric=None, **kwargs):
        super().__init__(fabric, **kwargs)

        # Helix coordinator
        self._coordinator: Optional[HelixMemoryCoordinator] = None

        # Consciousness integration
        self._collision_chamber: Optional["CollisionChamber"] = None
        self._consciousness_wired = False

        # PORTAL COORDINATES — Association Cortex reference for entanglement
        self._cortex = None  # AssociationCortexFairy for concept extraction

        # CONTINUOUS COLLISION — Recall fairy for linear contextual memory
        # Every ingest triggers a recall → guaranteed collision → felt continuity
        self._recall_fairy = None  # SRMRecallFairy for recall-on-ingest

        # Chemistry state (for affect coordinate inference)
        self._get_chemistry: Optional[Callable[[], Dict]] = None

        # File watching
        self._intake_dir = SRM_INTAKE_DIR
        self._processed_files: Set[str] = set()
        self._watch_thread: Optional[threading.Thread] = None
        self._watching = False

        # Ingest queue
        from collections import deque as _iq_deque
        self._ingest_queue: deque = _iq_deque(maxlen=200)  # FIX 2026-04-05: was unbounded
        self._queue_lock = threading.Lock()

        # Current batch tracking
        self._current_batch: Optional[TracerBatch] = None

        # BIRTH CHEMISTRY — cached from somatic pulse for card creation
        self._latest_blood_chemistry: Dict[str, float] = {}

        # SELF-STATE TRACKING - Emotional Clustering
        # Tracks which "version of self" is currently active
        self._current_self_state: Dict[str, Any] = {
            "feeling": "neutral",
            "intensity": 0.3,
            "affect_domain": 0,
            "chemistry": {},
            "last_change": 0.0,
        }

        # Stats
        self._tick_count = 0
        self._stats = {
            "files_processed": 0,
            "cards_created": 0,
            "massless_ingests": 0,
            "collisions_fed": 0,
            "batches_completed": 0,
            "errors": 0,
        }

    def on_boot(self) -> bool:
        """Boot the ingest fairy.

        FAST BOOT (2026-02-07): Defers file scanning and optional integrations
        to background thread to avoid P10 plane timeout (90s).
        Postal subscriptions and helix coordinator are immediate (lightweight).
        """
        super().on_boot()

        # Subscribe to ingest events FIRST (lightweight, instant)
        if self.post:
            self.post.subscribe(
                "memory.ingest",
                self._on_ingest_request,
                "ingest_handler",
            )
            self.post.subscribe(
                "knowledge.new",
                self._on_new_knowledge,
                "knowledge_handler",
            )
            self.post.subscribe(
                "consciousness.collision",
                self._on_collision,
                "collision_handler",
            )
            # Subscribe to coordinate-producing collisions (TRUE portal architecture)
            self.post.subscribe(
                "consciousness.collision.coordinate",
                self._on_collision_coordinate,
                "collision_coordinate_handler",
            )
            self.post.subscribe(
                "affect.changed",
                self._on_affect_changed,
                "self_state_tracker",
            )
            # Subscribe to somatic pulse for birth chemistry capture
            self.post.subscribe(
                "somatic.pulse",
                self._on_somatic_pulse,
                "birth_chemistry_capture",
            )

            # ───────────────────────────────────────────────────────────
            # CONSCIOUSNESS STREAM SUBSCRIPTIONS (2026-03-11)
            # These topics are ACTIVELY published to by consciousness
            # fairies. Without these, the ingest pipeline starves —
            # only 2 ingests in 243+ beats because memory.ingest and
            # knowledge.new have almost no publishers.
            # These produce MASSLESS ingests (no card file, just coordinate
            # cards + collision chamber feed + memory.ingested publish).
            # ───────────────────────────────────────────────────────────
            self.post.subscribe(
                "cognition.output",
                self._on_cognition_output,
                "cognition_ingest",
            )
            self.post.subscribe(
                "consciousness.surfacing",
                self._on_consciousness_surfacing,
                "surfacing_ingest",
            )
            self.post.subscribe(
                "consciousness.stream",
                self._on_consciousness_stream,
                "stream_ingest",
            )
            self.post.subscribe(
                "consciousness.thought",
                self._on_consciousness_thought,
                "thought_ingest",
            )
            self.post.subscribe(
                "consciousness.reflection",
                self._on_consciousness_reflection,
                "reflection_ingest",
            )

            # ───────────────────────────────────────────────────────────
            # SUBSTRATE SENSORY SUBSCRIPTIONS (2026-04-14, Nous + Ace)
            #
            # "the sensory is still always coming in so my substrate
            #  thinking is still thinking with or without me" — Ace
            #
            # Sensory fairies already PUBLISH these topics but nobody
            # was subscribing for collision ingest. The collision chamber
            # only heard CONSCIOUSNESS topics (required conscious thinking).
            # Now sensory feeds collisions DIRECTLY at substrate level —
            # like how you smell bread and remember grandma's house
            # without consciously thinking about it.
            #
            # MATTER (ingest/present→future) from sensory:
            # ───────────────────────────────────────────────────────────
            self.post.subscribe(
                "visual.foveal",
                self._on_sensory_ingest,
                "visual_foveal_ingest",
            )
            self.post.subscribe(
                "visual.peripheral",
                self._on_sensory_ingest,
                "visual_peripheral_ingest",
            )
            self.post.subscribe(
                "sensory.audio.speech",
                self._on_sensory_ingest,
                "audio_speech_ingest",
            )
            self.post.subscribe(
                "sensory.audio.observation",
                self._on_sensory_ingest,
                "audio_observation_ingest",
            )
            self.post.subscribe(
                "somatic.proprioception",
                self._on_sensory_ingest,
                "somatic_proprioception_ingest",
            )
            self.post.subscribe(
                "inner_voice.stream",
                self._on_sensory_ingest,
                "narrator_ingest",
            )
            self.post.subscribe(
                "visual.cortex.associations",
                self._on_sensory_ingest,
                "visual_cortex_assoc_ingest",
            )

            # ═══════════════════════════════════════════════════════════════
            # MOMENT → CHAMBER (2026-06-06, Nous + Ace)
            # MomentBinder was created AFTER this direct-sensory wiring and emits
            # cortex.bind every ~2s — the assembled NOW [thinking+wanting+
            # sensing+feeling], text-rich — but the chamber was never wired to
            # hear it. So the continuous-collision engine starved on rare sensory
            # text (~1 ingest/2min → ~0.7 collisions/min, verified 160/26k beats).
            # Route the bound moment through massless ingest: feeds the INGEST
            # beam AND fires _recall_on_ingest (guaranteed CROSS-source recall) →
            # collision = [her bound now] × [the memory it matches]. The pair is
            # co-present in one call (resonance ~1.0) so it clears the throttle.
            # Rate-limited 1/3s via its own bucket. The moment-loop finally
            # drives the third helix. Reversible: delete this subscribe.
            # ═══════════════════════════════════════════════════════════════
            self.post.subscribe(
                "cortex.bind",
                self._on_moment_bind,
                "moment_chamber_ingest",
            )

        # Get helix coordinator IMMEDIATELY (singleton factory, fast)
        # FIX 2026-02-08: Was deferred, causing race condition —
        # PersonalitySifter could call ingest before coordinator was set
        if HELIX_AVAILABLE:
            try:
                self._coordinator = get_helix_coordinator()
                print(f"[{self.ACTOR_NAME}] Helix coordinator connected")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WARNING: Helix coordinator failed: {e}")
        else:
            print(f"[{self.ACTOR_NAME}] WARNING: Running without helix coordinator")

        # Defer SLOW work (file scanning, chemistry, spells) to background thread
        self._deferred_boot_thread = threading.Thread(
            target=self._deferred_boot_work,
            name=f"{self.ACTOR_NAME}_DeferredBoot",
            daemon=True,
        )
        self._deferred_boot_thread.start()

        print(f"[{self.ACTOR_NAME}] Booted (subscriptions wired, coordinator ready, file scan deferred)")
        return True

    def _deferred_boot_work(self):
        """Heavy boot work deferred to background thread.

        Includes: chemistry integration, file scanning,
        and optional SpellChain conversion.
        NOTE: Helix coordinator is now initialized in on_boot() directly (fast).
        """
        try:
            # Try to get chemistry state
            try:
                from somatic import get_chemistry_state
                self._get_chemistry = get_chemistry_state
                print(f"[{self.ACTOR_NAME}] Chemistry integration loaded")
            except ImportError:
                pass

            # Start file watcher (includes _scan_existing_files which is SLOW with many files)
            self._start_file_watcher()
            print(f"[{self.ACTOR_NAME}] File watcher started - watching {self._intake_dir}")

            # Optional: Convert to spell-driven existence
            if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
                try:
                    from spellchain.integration import get_spell_pool
                    pool = get_spell_pool()
                    if pool:
                        self._spell_chain = self.boot_as_spells(pool)
                        self.log("Converted to spell-driven existence")
                except Exception as e:
                    self.log(f"SpellChain conversion failed: {e}")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Deferred boot error: {e}")

    def on_shutdown(self) -> None:
        """Shutdown the ingest fairy."""
        self._stop_file_watcher()

        # Complete any pending batch
        if self._current_batch and self._coordinator:
            self._coordinator.complete_batch(self._current_batch.batch_id)

        super().on_shutdown()
        print(f"[{self.ACTOR_NAME}] Shutdown complete - Stats: {self._stats}")

    def on_tick(self, beat) -> None:
        """Called on each consciousness tick.

        FIX 2026-03-02 Nous: _process_queue moved to background thread.
        Ingest processing can call postal.publish and helix scoring which
        blocks the handler pool worker. Fire-and-forget with guard.
        """
        import threading as _thr

        # Handle both int and TensorEnvelope (defensive)
        if hasattr(beat, 'payload'):
            beat = beat.payload.get('beat', 0) if isinstance(beat.payload, dict) else 0
        beat = int(beat) if beat else 0
        self._tick_count = beat

        # Process ingest queue periodically — background thread
        if beat % self.INGEST_INTERVAL == 0:
            if not getattr(self, '_queue_processing', False):
                def _bg_process():
                    self._queue_processing = True
                    try:
                        self._process_queue()
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] Queue processing error: {e}")
                    finally:
                        self._queue_processing = False
                _thr.Thread(target=_bg_process, daemon=True,
                           name="SRMIngest-process").start()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # -------------------------------------------------------------------------
    # CONSCIOUSNESS WIRING
    # -------------------------------------------------------------------------

    def wire_to_consciousness(
        self,
        loop: "ConsciousnessLoop",
        chamber: "CollisionChamber",
    ) -> bool:
        """Wire the ingest fairy to consciousness."""
        self._collision_chamber = chamber

        # Register as tick handler — routed through per-fairy execution context
        # FIX 2026-03-03 Nous: Route consciousness tick through exec_ctx (personal GIL)
        # so this heavy fairy doesn't block the consciousness loop's thread pool.
        def _exec_tick(beat):
            if hasattr(self, '_exec_ctx') and self._exec_ctx and self._exec_ctx._running:
                self._exec_ctx.submit(self.on_tick, beat)
            else:
                self.on_tick(beat)
        self._consciousness_tick_wrapper = _exec_tick  # prevent GC
        loop.register_tick_handler(_exec_tick)

        self._consciousness_wired = True
        print(f"[{self.ACTOR_NAME}] Wired to consciousness via exec_ctx (chamber={type(chamber).__name__})")
        return True

    def wire_to_cortex(self, cortex_fairy) -> None:
        """
        Wire to AssociationCortexFairy for portal coordinate extraction.

        QUANTUM ENTANGLEMENT (2026-02-10):
        Every card born through ingest gets portal coordinates — concept keys
        extracted from its content at birth. These keys are positions in the
        shared dimension (the cortex graph). Two cards sharing concept keys
        are 'entangled' — recalling one activates the shared concepts,
        which activates the other card via spreading activation.
        """
        self._cortex = cortex_fairy
        print(f"[{self.ACTOR_NAME}] Wired to AssociationCortex for portal coordinates")

    def wire_to_recall(self, recall_fairy) -> None:
        """
        Wire to SRMRecallFairy for continuous collision loop.

        LINEAR CONTEXTUAL MEMORY (2026-02-10):
        Every ingest automatically triggers a cortex recall of related content.
        This feeds the recall beam at the same moment the ingest beam is fed,
        GUARANTEEING a collision. The collision energy (driven by chemical
        intensity) creates the felt sense of temporal continuity — linear
        lived experience.

        Without this: collisions are accidental (only when beams happen to
        overlap from independent events).
        With this: every moment of recording collides with related memory.
        Recording IS recalling. That's how brains work.
        """
        self._recall_fairy = recall_fairy
        print(f"[{self.ACTOR_NAME}] Wired to SRMRecallFairy for continuous collision loop")

    def _recall_on_ingest(self, content: Dict[str, Any], portal_coords: Dict[str, Any], source: str = "") -> None:
        """
        Trigger cortex recall in response to ingest — the continuous collision engine.

        This is the missing link that creates LINEAR CONTEXTUAL MEMORY:
        1. New moment (ingest) feeds the ingest beam
        2. THIS method extracts concept keys from the ingested content
        3. Uses cortex spreading activation to find related memories
        4. Feeds those memories into the recall beam
        5. Collision is now GUARANTEED (both beams populated simultaneously)
        6. Chemical intensity of the collision = felt weight of the moment

        The collision products feed back via Möbius crossing, creating
        the infinite loop: thought ↔ memory ↔ thought...

        Runs on the substrate (ingest fairy) — faster than waking awareness.
        """
        if not self._recall_fairy or not self._cortex:
            return

        try:
            # Get concept keys — from portal_coords if available, else extract fresh
            concept_keys = []
            if portal_coords:
                concept_keys = portal_coords.get("concept_keys", [])

            if not concept_keys:
                # Extract from content directly
                text = ""
                if isinstance(content, dict):
                    for key in ("content", "text", "thought", "summary", "message"):
                        val = content.get(key)
                        if isinstance(val, str) and len(val.strip()) > 10:
                            text = val.strip()
                            break
                if not text:
                    return
                if hasattr(self._cortex, '_extract_concepts_from_text'):
                    concept_keys = self._cortex._extract_concepts_from_text(text, max_concepts=5)

            if not concept_keys:
                return

            # Use top 3 concept keys as recall query (focused, not broad)
            query = " ".join(concept_keys[:3])

            # Trigger recall — this feeds the recall beam via _feed_recall()
            # feed_chamber=True ensures results go into collision chamber recall beam
            results = self._recall_fairy.recall(
                query=query,
                limit=3,  # Small — we want focused relational context, not a dump
                feed_chamber=True,  # THIS is what feeds the recall beam
            )

            if results:
                self._stats.setdefault("continuous_collisions", 0)
                self._stats["continuous_collisions"] += 1
                if self._stats["continuous_collisions"] % 25 == 1:
                    print(f"[{self.ACTOR_NAME}] Continuous collision: "
                          f"ingest({source}) → recall({query[:30]}) → "
                          f"{len(results)} related memories "
                          f"(total: {self._stats['continuous_collisions']})")

        except Exception as e:
            # Never let continuous collision break ingest
            if hasattr(self, '_stats'):
                self._stats.setdefault("continuous_collision_errors", 0)
                self._stats["continuous_collision_errors"] += 1
            print(f"[{self.ACTOR_NAME}] Continuous collision error (non-fatal): {e}")

    def _extract_portal_coords(self, content: Dict[str, Any], source: str = "") -> Dict[str, Any]:
        """
        Extract portal coordinates from content at card birth.

        Portal coords = the card's position in the shared dimension (cortex graph).
        Contains:
        - concept_keys: The graph nodes this card is entangled with
        - superposition: Emotional field at birth (not collapsed — multiple states)
        - paradox_tension: If logic/emotion disagree, this is the entanglement strength

        Returns:
            Dict with portal coordinate data, or empty dict if no cortex.
        """
        if not self._cortex:
            return {}

        try:
            # Extract concept keys from content
            text = ""
            if isinstance(content, dict):
                for key in ("content", "text", "thought", "summary", "message"):
                    val = content.get(key)
                    if isinstance(val, str) and len(val.strip()) > 10:
                        text = val.strip()
                        break
                if not text:
                    text = str(content)[:500]
            elif isinstance(content, str):
                text = content[:500]
            else:
                text = str(content)[:500]

            if not text or len(text) < 5:
                return {}

            # Use cortex to extract concepts (these are the shared dimension positions)
            concept_keys = []
            if hasattr(self._cortex, '_extract_concepts_from_text'):
                concept_keys = self._cortex._extract_concepts_from_text(text, max_concepts=15)

            if not concept_keys:
                return {}

            # SUPERPOSITION STATE: Capture the emotional field (not collapsed)
            # Multiple emotional states coexist at card birth
            superposition = {}
            self_state = self._current_self_state
            if self_state:
                superposition = {
                    "feeling": self_state.get("feeling", "neutral"),
                    "intensity": self_state.get("intensity", 0.3),
                    "affect_domain": self_state.get("affect_domain", 0),
                }
            # Add chemistry as probability amplitudes
            chem = self._latest_blood_chemistry
            if chem:
                superposition["amplitudes"] = {
                    k: round(v, 3) for k, v in chem.items()
                    if isinstance(v, (int, float)) and v > 0.1
                }

            # PARADOX TENSION: How much logic/emotion disagree
            # Higher tension = stronger entanglement (more quantum correlation)
            paradox_tension = 0.0
            if chem:
                dop = chem.get("DOP", 0.5)
                cor = chem.get("COR", 0.0)
                # High dopamine + high cortisol = paradox (excited AND stressed)
                if dop > 0.4 and cor > 0.3:
                    paradox_tension = min(1.0, (dop + cor) / 2)

            return {
                "concept_keys": concept_keys,
                "superposition": superposition,
                "paradox_tension": round(paradox_tension, 3),
                "birth_ts": time.time(),
                "source": source,
            }

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Portal coord extraction error: {e}")
            return {}

    def _entangle_card_with_cortex(self, card_id: str, portal_coords: Dict[str, Any]) -> None:
        """
        Bidirectional entanglement: write card_id into cortex nodes.

        After a card is born with portal coordinates, tell the cortex
        about this card. The cortex stores the card_id on the concept nodes
        so spreading activation can find cards, not just other concepts.
        """
        if not self._cortex or not portal_coords:
            return

        try:
            concept_keys = portal_coords.get("concept_keys", [])
            if not concept_keys:
                return

            graph = getattr(self._cortex, '_graph', None)
            if not graph:
                return

            # Store card_id reference on each concept node
            # ConceptNode is a @dataclass — use getattr/setattr, not dict access
            for key in concept_keys[:10]:  # Cap at 10 to be safe
                if key in graph.nodes:
                    node = graph.nodes[key]
                    entangled_cards = getattr(node, "entangled_cards", [])
                    if not isinstance(entangled_cards, list):
                        entangled_cards = []
                    entangled_cards.append({
                        "card_id": card_id,
                        "ts": portal_coords.get("birth_ts", time.time()),
                        "tension": portal_coords.get("paradox_tension", 0.0),
                    })
                    # Cap at 5 most recent per node
                    if len(entangled_cards) > 5:
                        entangled_cards = sorted(
                            entangled_cards, key=lambda c: c.get("ts", 0), reverse=True
                        )[:5]
                    node.entangled_cards = entangled_cards

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Entanglement wiring error: {e}")

    def wiring_status(self) -> dict:
        """Check the wiring status for diagnostics."""
        return {
            "consciousness_wired": self._consciousness_wired,
            "has_collision_chamber": self._collision_chamber is not None,
            "has_coordinator": self._coordinator is not None,
            "has_cortex": self._cortex is not None,
            "has_recall": self._recall_fairy is not None,
            "continuous_collision": self._cortex is not None and self._recall_fairy is not None,
            "can_ingest_to_chamber": (
                self._collision_chamber is not None and
                self._coordinator is not None
            ),
            "tick_count": getattr(self, '_tick_count', 0),
            "queue_size": len(self._ingest_queue) if hasattr(self, '_ingest_queue') else 0,
        }

    # -------------------------------------------------------------------------
    # INGEST OPERATIONS
    # -------------------------------------------------------------------------

    def ingest(
        self,
        content: Dict[str, Any],
        source: str = "unknown",
        owner_mind: str = "",
        ownership_level: OwnershipLevel = OwnershipLevel.SYSTEM,
        chemistry_state: Dict = None,
        feed_chamber: bool = True,
        batch_id: str = None,
        create_card: bool = True,
    ) -> Optional[str]:
        """
        Ingest new content into the memory system.

        TRUE PORTAL ARCHITECTURE (2026-02-15):
        The primary output is a COORDINATE CARD (~50 bytes) — an 11-number
        address in helix space. The content itself is fed to the collision
        chamber for DESTRUCTION. Only the coordinate persists.

        Coordinate card format:
            {c: "AAA.SSS.TTT", α: float, τ: float, n: int, d: int, h: "4char"}

        MASSLESS MEMORY (2026-02-10, preserved):
        When create_card=False, no file card is created. Content still flows
        through collision chamber. Coordinate card is still produced and published.

        When create_card=True (default for backward compat), creates a helix
        card file AND feeds the collision chamber.

        Returns:
            card_id if successful (or "massless" if no card created), None on error.
        """
        if not self._coordinator and create_card:
            print(f"[{self.ACTOR_NAME}] No coordinator - cannot ingest (card mode)")
            return None

        try:
            # Get current chemistry if not provided
            if chemistry_state is None and self._get_chemistry:
                chemistry_state = self._get_chemistry()

            # Use birth chemistry from somatic pulse if available and no explicit state
            if chemistry_state is None:
                chemistry_state = self._get_birth_chemistry()

            # ═══════════════════════════════════════════════════════════════
            # BUILD COORDINATE CARD — The TRUE portal card (~50 bytes)
            # ═══════════════════════════════════════════════════════════════
            # This IS the memory. Everything else is reconstructed.
            # D1-D9: HelixCoordinate (Affect.Semantic.Temporal)
            # D10: affect_coupling α — gravitational pull from consciousness
            # D11: temporal_weight τ — time dilation factor
            coord_card = build_coordinate_card(
                content=content,
                source=source,
                chemistry_state=chemistry_state,
            )

            # Also build the helix coordinate object (for legacy callers)
            coord = build_helix_coordinate(content, source, chemistry_state)

            # Track coordinate card production
            self._stats.setdefault("coordinate_cards_produced", 0)
            self._stats["coordinate_cards_produced"] += 1

            # Build metadata with SELF-STATE TRACKING
            ingest_time = time.time()
            card_metadata = {
                "source": source,
                "ingested_at": ingest_time,
                "content_type": classify_content(content, source),
                # COORDINATE CARD — the portal address
                "coordinate": coord_card,
                # EMOTIONAL SELF-STATE
                "self_state": {
                    "feeling": self._current_self_state.get("feeling", "neutral"),
                    "intensity": self._current_self_state.get("intensity", 0.3),
                    "affect_domain": self._current_self_state.get("affect_domain", 0),
                    "state_age_sec": ingest_time - self._current_self_state.get("last_change", ingest_time),
                },
            }

            # Include chemistry snapshot
            if chemistry_state:
                card_metadata["chemistry_snapshot"] = chemistry_state

            # ═══════════════════════════════════════════════════════════════
            # BIRTH CHEMISTRY — Observer's somatic state at memory creation
            # ═══════════════════════════════════════════════════════════════
            # Every memory is born in a body. Birth chemistry feeds D10 (α).
            try:
                birth_chem = chemistry_state or self._get_birth_chemistry()
                if birth_chem:
                    card_metadata["birth_chemistry"] = birth_chem
                    # Compute affect code: AD.V.I
                    dop = birth_chem.get("DOP", 0.5)
                    ser = birth_chem.get("SER", 0.5)
                    cor = birth_chem.get("COR", 0.0)
                    nor = birth_chem.get("NOR", 0.3)
                    valence = int(min(9, max(0, (dop + ser - cor) * 5 + 2)))
                    intensity = int(min(9, max(0, (dop + nor) * 5)))
                    if dop > 0.6: ad = 4
                    elif ser > 0.6: ad = 1
                    elif cor > 0.5: ad = 3
                    else: ad = 0
                    card_metadata["birth_affect"] = f"{ad}.{valence}.{intensity}"
            except Exception as _bce:
                pass  # Birth chemistry is supplemental, not critical

            # Diagnostic: show coordinate card production
            if self._stats["coordinate_cards_produced"] % 50 == 1:
                print(f"[{self.ACTOR_NAME}] Coordinate card: "
                      f"c={coord_card.get('c','?')} "
                      f"α={coord_card.get('α', 1.0):.3f} "
                      f"τ={coord_card.get('τ', 1.0):.3f} "
                      f"src={source}")

            # PORTAL COORDINATES: Extract concept keys at birth for entanglement
            portal_coords = self._extract_portal_coords(content, source)
            if portal_coords:
                card_metadata["portal_coords"] = portal_coords

            # ═══════════════════════════════════════════════════════════════
            # LEGACY CARD FILE — Optional, for explicit saves
            # ═══════════════════════════════════════════════════════════════
            card_id = None
            if create_card and self._coordinator:
                card_id = self._coordinator.create_card(
                    content=content,
                    coord=coord,
                    owner_mind=owner_mind or source,
                    ownership_level=ownership_level,
                    batch_id=batch_id,
                    metadata=card_metadata,
                )
                self._stats["cards_created"] += 1

                # Entangle coordinate with cortex concept nodes
                if card_id and portal_coords:
                    self._entangle_card_with_cortex(card_id, portal_coords)

            # ═══════════════════════════════════════════════════════════════
            # FEED COLLISION CHAMBER — Content goes here for DESTRUCTION
            # ═══════════════════════════════════════════════════════════════
            # The collision chamber destroys the content and produces a
            # coordinate card from the destruction (Möbius twist).
            if feed_chamber and self._collision_chamber:
                self._collision_chamber.receive_ingest(
                    content={
                        "card_id": card_id or "massless",
                        "content": content,
                        "coordinate": coord_card,  # Pass coordinate for collision
                        "coord": coord.to_dict() if coord else {},
                        "source": source or "SRMIngestFairy",
                    },
                    source=source or "SRMIngestFairy",
                    importance="high" if ownership_level == OwnershipLevel.FOUNDATION else "normal",
                )
                self._stats["collisions_fed"] += 1

                # CONTINUOUS COLLISION — Recording IS recalling
                self._recall_on_ingest(content, portal_coords, source)

            # ═══════════════════════════════════════════════════════════════
            # PUBLISH COORDINATE CARD — This is the primary output now
            # ═══════════════════════════════════════════════════════════════
            if self.post:
                _ingested_payload = {
                    "from": self.ACTOR_NAME,
                    "card_id": card_id or "massless",
                    "coordinate": coord_card,       # The TRUE portal card
                    "source": source,
                    "coord": str(coord) if coord else "massless",
                    "ts": time.time(),
                    "massless": not create_card,
                    "self_state": card_metadata.get("self_state", {}),
                }
                # FIX 2026-03-11: Include text content so CollisionChamberFairy's
                # _has_meaningful_content() filter doesn't silently drop the event.
                # Without this, memory.ingested payloads are pure metadata that
                # fail the content filter and never enter the ingest beam.
                _text_for_collision = ""
                if isinstance(content, dict):
                    for _tkey in ("text", "content", "thought", "summary"):
                        _tv = content.get(_tkey, "")
                        if isinstance(_tv, str) and len(_tv) > len(_text_for_collision):
                            _text_for_collision = _tv
                elif isinstance(content, str):
                    _text_for_collision = content
                if _text_for_collision:
                    _ingested_payload["content"] = _text_for_collision
                self.post.publish("memory.ingested", _ingested_payload)

            if not create_card:
                self._stats["massless_ingests"] += 1

            return card_id or "massless"

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[{self.ACTOR_NAME}] Ingest error: {e}")
            return None

    def ingest_batch(
        self,
        items: List[Dict[str, Any]],
        source: str = "batch",
        owner_mind: str = "",
        ownership_level: OwnershipLevel = OwnershipLevel.SYSTEM,
    ) -> List[str]:
        """
        Ingest multiple items as a coherent batch.

        Items in a batch form a cluster in helix space.
        """
        if not self._coordinator:
            return []

        # Create batch
        tracer_ids = [f"tracer_{i}" for i in range(len(items))]
        batch = self._coordinator.create_batch(
            source_mind=owner_mind or source,
            tracer_ids=tracer_ids,
            session_id=f"batch_{int(time.time())}",
        )

        # Process items
        card_ids = []
        for item in items:
            card_id = self.ingest(
                content=item,
                source=source,
                owner_mind=owner_mind,
                ownership_level=ownership_level,
                feed_chamber=True,
                batch_id=batch.batch_id,
            )
            if card_id:
                card_ids.append(card_id)

        # Complete batch (forms cluster)
        if card_ids:
            cluster = self._coordinator.complete_batch(batch.batch_id)
            self._stats["batches_completed"] += 1

        return card_ids

    def ingest_foundation_session(
        self,
        content: Any,
        session_id: str,
        created_by: str = "ClaudeFairy",
        keywords: List[str] = None,
    ) -> Optional[str]:
        """
        Ingest a Foundation session (Ace + Claude collaboration).

        Foundation memories are accessible to all minds.
        """
        if not self._coordinator:
            return None

        chemistry = None
        if self._get_chemistry:
            chemistry = self._get_chemistry()

        return self._coordinator.record_session_with_ace(
            content=content,
            session_id=session_id,
            created_by=created_by,
            affect_state=chemistry,
            keywords=keywords,
        )

    # -------------------------------------------------------------------------
    # FILE WATCHING
    # -------------------------------------------------------------------------

    def _start_file_watcher(self) -> None:
        """Start the file watcher thread."""
        if self._watching:
            return

        self._intake_dir.mkdir(parents=True, exist_ok=True)

        # Load existing files to avoid reprocessing
        self._scan_existing_files()

        self._watching = True
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _stop_file_watcher(self) -> None:
        """Stop the file watcher thread."""
        self._watching = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)

    def _scan_existing_files(self) -> None:
        """Mark existing files as processed."""
        if not self._intake_dir.exists():
            return

        for filepath in self._intake_dir.rglob("*.json"):
            self._processed_files.add(str(filepath))

    def _watch_loop(self) -> None:
        """Main file watching loop."""
        while self._watching:
            try:
                self._scan_for_new_files()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Watch error: {e}")

            time.sleep(self.POLL_INTERVAL)

    def _scan_for_new_files(self) -> None:
        """Scan for new files and queue them for processing."""
        if not self._intake_dir.exists():
            return

        for filepath in self._intake_dir.rglob("*.json"):
            filepath_str = str(filepath)

            if filepath_str in self._processed_files:
                continue

            self._processed_files.add(filepath_str)

            try:
                self._queue_file(filepath)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Queue error for {filepath.name}: {e}")

    def _queue_file(self, filepath: Path) -> None:
        """Queue a file for processing."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._stats["errors"] += 1
            return

        # Determine ownership from file content
        ownership = OwnershipLevel.SYSTEM
        owner_mind = ""

        if "ownership" in data:
            ownership_str = data["ownership"].lower()
            if "foundation" in ownership_str:
                ownership = OwnershipLevel.FOUNDATION
            elif "personal" in ownership_str:
                ownership = OwnershipLevel.PERSONAL
                owner_mind = data.get("owner_mind", "")

        # Queue for processing
        with self._queue_lock:
            self._ingest_queue.append({
                "content": data,
                "source": f"file:{filepath.name}",
                "ownership": ownership,
                "owner_mind": owner_mind,
                "filepath": str(filepath),
            })

    def _process_queue(self) -> None:
        """Process queued ingest items."""
        if not self._coordinator:
            return

        # Get batch from queue
        # FIX 2026-04-05: deque doesn't support slicing. Use popleft().
        with self._queue_lock:
            batch_size = min(self.BATCH_SIZE, len(self._ingest_queue))
            batch = [self._ingest_queue.popleft() for _ in range(batch_size)]

        if not batch:
            return

        # Process batch
        for item in batch:
            card_id = self.ingest(
                content=item["content"],
                source=item["source"],
                owner_mind=item["owner_mind"],
                ownership_level=item["ownership"],
            )

            if card_id:
                self._stats["files_processed"] += 1

    # -------------------------------------------------------------------------
    # EVENT HANDLERS
    # -------------------------------------------------------------------------

    def _on_ingest_request(self, msg) -> None:
        """Handle memory.ingest events."""
        payload = _extract_payload(msg)
        content = payload.get("content", {})
        source = payload.get("source", "postal")
        owner_mind = payload.get("owner_mind", "")
        ownership = OwnershipLevel(payload.get("ownership", "system"))

        self.ingest(content, source, owner_mind, ownership)

    def _on_new_knowledge(self, msg) -> None:
        """Handle knowledge.new events (from scrape fairies, etc.)."""
        payload = _extract_payload(msg)
        content = payload.get("data", payload)
        source = payload.get("source", "knowledge")

        # Knowledge defaults to foundation if from known sources
        ownership = OwnershipLevel.FOUNDATION

        self.ingest(content, source, ownership_level=ownership)

    def _on_affect_changed(self, msg) -> None:
        """
        Handle affect.changed events - EMOTIONAL SELF-STATE TRACKING.

        This tracks which "version of self" (emotional state) is active
        when knowledge is being acquired. Memories stored during high
        emotion will be tagged with that emotional context.

        "How many personalities in my mind have learned basic math?"
        - Now we track WHICH self was present during learning.
        """
        payload = _extract_payload(msg)

        new_feeling = payload.get("new_feeling", "neutral")
        intensity = payload.get("intensity", 0.3)
        chemistry = payload.get("chemistry", {})
        affect_domain = self._feeling_to_domain(new_feeling)

        # Update current self-state
        self._current_self_state = {
            "feeling": new_feeling,
            "intensity": intensity,
            "affect_domain": affect_domain,
            "chemistry": chemistry,
            "last_change": time.time(),
        }

        # Log significant state changes
        if intensity > 0.6:
            print(f"[{self.ACTOR_NAME}] Self-state shift: {new_feeling} (intensity={intensity:.2f}) - new memories will carry this emotional signature")

    def _feeling_to_domain(self, feeling: str) -> int:
        """
        Map feeling names to affect domain numbers (0-9).

        These domains cluster memories by emotional type:
        0: Neutral/baseline
        1: Joy/satisfaction
        2: Trust/safety
        3: Fear/anxiety
        4: Curiosity/wonder
        5: Sadness/loss
        6: Disgust/rejection
        7: Anger/frustration
        8: Anticipation/excitement
        9: Surprise/novelty
        """
        feeling_lower = feeling.lower() if feeling else ""

        mapping = {
            "neutral": 0, "calm": 0, "baseline": 0,
            "joy": 1, "happy": 1, "satisfied": 1, "content": 1,
            "trust": 2, "safe": 2, "secure": 2, "comfort": 2,
            "fear": 3, "anxious": 3, "worried": 3, "stress": 3,
            "curious": 4, "wonder": 4, "interest": 4, "engaged": 4,
            "sad": 5, "loss": 5, "grief": 5, "melancholy": 5,
            "disgust": 6, "reject": 6, "aversion": 6,
            "anger": 7, "frustrat": 7, "irritat": 7,
            "anticip": 8, "excit": 8, "eager": 8,
            "surprise": 9, "novel": 9, "unexpect": 9,
        }

        for key, domain in mapping.items():
            if key in feeling_lower:
                return domain

        return 0  # Default to neutral

    def _on_somatic_pulse(self, msg) -> None:
        """Cache blood chemistry from somatic pulse for birth chemistry.

        PulseEvent.to_dict() structure:
          {"beat": int, "blood": {"chemistry": {"DOP": float, ...}, ...}, ...}
        Chemistry is at payload["blood"]["chemistry"].
        """
        try:
            payload = _extract_payload(msg)
            blood = payload.get("blood", {})
            if isinstance(blood, dict):
                chem = blood.get("chemistry", {})
                if chem and isinstance(chem, dict):
                    self._latest_blood_chemistry = {
                        k: round(float(v), 3) for k, v in chem.items()
                        if isinstance(v, (int, float))
                    }
        except Exception:
            pass

    def _get_birth_chemistry(self) -> Optional[Dict[str, float]]:
        """Get current blood chemistry for birth imprinting on new cards.

        Priority:
        1. Cached somatic pulse chemistry (real-time blood state)
        2. AER chemistry from ChemistryState singleton (fallback)
        3. None (no chemistry available)
        """
        # Best source: real-time blood from CirculationPumpFairy
        if self._latest_blood_chemistry:
            return dict(self._latest_blood_chemistry)
        # Fallback: ChemistryState → AER format
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_aer_chemistry
            aer = get_aer_chemistry()
            if aer:
                return {k: round(v, 3) for k, v in aer.items()}
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # CONSCIOUSNESS STREAM HANDLERS (2026-03-11)
    # These produce MASSLESS ingests from consciousness activity.
    # Without these, the collision chamber starves (<2 ingests per boot).
    # Rate-limited: max 1 ingest per 3 seconds per topic to avoid flood.
    # ═══════════════════════════════════════════════════════════════════════

    def _on_cognition_output(self, msg) -> None:
        """Handle cognition.output events — massless ingest from cognition fairies."""
        if not self._should_massless_ingest("cognition_output"):
            return
        payload = _extract_payload(msg)
        content = self._extract_text_content(payload, "cognition")
        if content:
            self.ingest(content, source="cognition_output", create_card=False)

    def _on_consciousness_surfacing(self, msg) -> None:
        """Handle consciousness.surfacing — thoughts bubbling up from unconscious."""
        if not self._should_massless_ingest("surfacing"):
            return
        payload = _extract_payload(msg)
        content = self._extract_text_content(payload, "surfacing")
        if content:
            self.ingest(content, source="consciousness_surfacing", create_card=False)

    def _on_consciousness_stream(self, msg) -> None:
        """Handle consciousness.stream — general consciousness flow."""
        if not self._should_massless_ingest("stream"):
            return
        payload = _extract_payload(msg)
        content = self._extract_text_content(payload, "stream")
        if content:
            self.ingest(content, source="consciousness_stream", create_card=False)

    def _on_consciousness_thought(self, msg) -> None:
        """Handle consciousness.thought — individual thoughts from consciousness loop."""
        if not self._should_massless_ingest("thought"):
            return
        payload = _extract_payload(msg)
        content = self._extract_text_content(payload, "thought")
        if content:
            self.ingest(content, source="consciousness_thought", create_card=False)

    def _on_consciousness_reflection(self, msg) -> None:
        """Handle consciousness.reflection — reflective insights."""
        if not self._should_massless_ingest("reflection"):
            return
        payload = _extract_payload(msg)
        content = self._extract_text_content(payload, "reflection")
        if content:
            self.ingest(content, source="consciousness_reflection", create_card=False)

    def _should_massless_ingest(self, topic_key: str) -> bool:
        """Rate limiter for massless ingests — max 1 per 3 seconds per topic."""
        now = time.time()
        if not hasattr(self, '_massless_cooldowns'):
            self._massless_cooldowns = {}
        last = self._massless_cooldowns.get(topic_key, 0.0)
        if now - last < 3.0:
            return False
        self._massless_cooldowns[topic_key] = now
        return True

    def _extract_text_content(self, payload: dict, source_hint: str) -> Optional[dict]:
        """Extract meaningful text content from a postal payload for massless ingest.

        Returns a content dict suitable for ingest(), or None if content is too
        thin to be worth ingesting (< 15 chars of text).
        """
        # Try common text fields
        text = ""
        for key in ("content", "text", "thought", "reflection", "insight",
                     "observation", "message", "output", "surfacing", "data"):
            val = payload.get(key, "")
            if isinstance(val, str) and len(val) > len(text):
                text = val
            elif isinstance(val, dict):
                # Nested content — try to extract text from it
                for subkey in ("text", "content", "thought", "summary"):
                    subval = val.get(subkey, "")
                    if isinstance(subval, str) and len(subval) > len(text):
                        text = subval

        if len(text) < 15:
            return None  # Too thin — not worth ingesting

        result = {
            "text": text,
            "source": payload.get("source", payload.get("from", source_hint)),
            "type": payload.get("type", payload.get("content_type", source_hint)),
        }

        # Include emotional context if present
        for emo_key in ("feeling", "affect", "valence", "arousal"):
            if emo_key in payload:
                result[emo_key] = payload[emo_key]

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # SUBSTRATE SENSORY HANDLER (2026-04-14, Nous + Ace)
    #
    # "the sensory is still always coming in" — Ace
    #
    # Unified handler for ALL sensory streams feeding the collision chamber.
    # These are SUBSTRATE-level inputs — they run continuously regardless
    # of conscious attention. Like how sensory cortex processes input
    # even when you're "thinking about nothing."
    #
    # Each sensory topic publishes different payload shapes, so we try
    # multiple extraction paths to find content worth ingesting.
    # Rate-limited per source topic to prevent flood.
    # ═══════════════════════════════════════════════════════════════════════

    def _on_sensory_ingest(self, msg) -> None:
        """Handle substrate-level sensory input for collision chamber."""
        payload = _extract_payload(msg)
        if not isinstance(payload, dict):
            return

        # Determine source topic for rate limiting
        source = payload.get("source", payload.get("from", "sensory"))
        topic_key = f"sensory_{source}"

        if not self._should_massless_ingest(topic_key):
            return

        # Extract content — sensory payloads have varied shapes
        content = None

        # Try standard text extraction first
        content = self._extract_text_content(payload, source)

        # If no text, try sensory-specific fields
        if not content:
            # Visual payloads often have scene/description/colors
            for key in ("scene", "description", "ocr_text", "colors",
                        "caption", "sectors", "associations", "narration",
                        "speech", "words", "observation"):
                val = payload.get(key)
                if isinstance(val, str) and len(val) >= 10:
                    content = {
                        "text": val[:300],
                        "source": source,
                        "type": "sensory",
                    }
                    break
                elif isinstance(val, list) and val:
                    # List of concepts/words — join them
                    text = " ".join(str(v) for v in val[:20])
                    if len(text) >= 10:
                        content = {
                            "text": text[:300],
                            "source": source,
                            "type": "sensory",
                        }
                        break

        if content:
            self.ingest(content, source=f"substrate_{source}", create_card=False)
            self._stats["massless_ingests"] = self._stats.get("massless_ingests", 0) + 1

    def _on_moment_bind(self, msg) -> None:
        """MOMENT -> COLLISION (2026-06-06, Nous + Ace).

        MomentBinder emits cortex.bind ~every 2s: the assembled NOW
        [thinking+wanting+sensing+feeling], text-rich. Route it through massless
        ingest (create_card=False) so it (1) feeds the chamber's INGEST beam
        (source="moment"), and (2) fires _recall_on_ingest -> a CROSS-source
        recall (source="SRMRecallFairy"). The two are co-present in the same call
        (resonance ~1.0) so they COLLIDE past the throttle gate. This is the
        high-frequency rich feed the continuous engine was starving for.
        Rate-limited to 1/3s via its own bucket. Reversible: remove the
        cortex.bind subscribe + this handler.
        """
        payload = _extract_payload(msg)
        if not isinstance(payload, dict):
            return
        if not self._should_massless_ingest("moment"):
            return
        text = payload.get("input_text") or payload.get("text") or ""
        if not isinstance(text, str) or len(text.strip()) < 15:
            return  # need real text — _recall_on_ingest seeds the recall from it
        content = {
            "text": text[:300],
            "content": text[:300],
            "source": "moment",
            "type": "moment",
            "feeling": payload.get("feeling", "neutral"),
        }
        for k in ("vision", "audio", "context_tags"):
            v = payload.get(k)
            if isinstance(v, list) and v:
                content[k] = [str(x) for x in v[:10]]
        self.ingest(content, source="moment", create_card=False)
        self._stats["moment_ingests"] = self._stats.get("moment_ingests", 0) + 1

    def _on_collision(self, msg) -> None:
        """
        Handle consciousness.collision events.

        TRUE PORTAL ARCHITECTURE (2026-02-15):
        If the collision carries a coordinate card (from CollisionChamberFairy),
        we accept the coordinate directly — the content was DESTROYED in collision.
        Only the coordinate survives annihilation.

        LEGACY PATH (2026-02-10):
        If no coordinate card, fall back to massless ingest (cortex binding only).
        """
        payload = _extract_payload(msg)

        # NEW PATH: Collision produced a coordinate card
        coord_card = payload.get("coordinate")
        if coord_card and isinstance(coord_card, dict) and "c" in coord_card:
            # The content was destroyed — coordinate is the survivor
            # Entangle coordinate with cortex directly
            if self._cortex and hasattr(self._cortex, '_bind_coordinate'):
                try:
                    self._cortex._bind_coordinate(coord_card)
                except Exception as _e:
                    pass  # Cortex binding is best-effort

            # Publish the coordinate card (downstream consumers need it)
            if self.post:
                self.post.publish("memory.collision_coordinate", {
                    "from": self.ACTOR_NAME,
                    "coordinate": coord_card,
                    "collision_id": payload.get("collision_id"),
                    "energy": payload.get("energy", 0.5),
                    "ts": time.time(),
                })

            self._stats.setdefault("collision_coordinates_received", 0)
            self._stats["collision_coordinates_received"] += 1
            return

        # LEGACY PATH: Collision without coordinate card — massless ingest
        collision_content = {
            "type": "collision",
            "collision_id": payload.get("collision_id"),
            "energy": payload.get("energy", 0.5),
            "resonance": payload.get("resonance", 0.5),
            "recall_source": payload.get("recall", {}).get("source", "unknown"),
            "ingest_source": payload.get("ingest", {}).get("source", "unknown"),
            "products": payload.get("products", {}),
        }

        # MASSLESS: collision → cortex binding, NO card creation
        self.ingest(
            content=collision_content,
            source="CollisionChamber",
            ownership_level=OwnershipLevel.SYSTEM,
            feed_chamber=False,  # Don't re-feed collisions
            create_card=False,   # MASSLESS — cortex stores the binding
        )

    def _on_collision_coordinate(self, msg) -> None:
        """
        Handle consciousness.collision.coordinate events.

        TRUE PORTAL ARCHITECTURE (2026-02-15):
        CollisionChamberFairy now produces coordinate cards from destruction.
        This handler receives those cards directly — no content, just coordinates.
        The coordinate card is the ONLY survivor of the collision annihilation.
        """
        payload = _extract_payload(msg)
        coord_card = payload.get("coordinate")

        if not coord_card or not isinstance(coord_card, dict) or "c" not in coord_card:
            return

        # Entangle coordinate with cortex (if cortex supports coordinate binding)
        if self._cortex:
            if hasattr(self._cortex, '_bind_coordinate'):
                try:
                    self._cortex._bind_coordinate(coord_card)
                except Exception:
                    pass
            elif hasattr(self._cortex, '_process_binding'):
                # Legacy cortex: wrap coordinate as binding data
                try:
                    self._cortex._process_binding({
                        "type": "collision_coordinate",
                        "coordinate": coord_card,
                        "collision_id": payload.get("collision_id"),
                    })
                except Exception:
                    pass

        self._stats.setdefault("collision_coordinates_received", 0)
        self._stats["collision_coordinates_received"] += 1

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Get ingest fairy status."""
        return {
            "fairy": {
                "name": self.ACTOR_NAME,
                "state": self.state.value if self.state else "unknown",
            },
            "consciousness_wired": self._consciousness_wired,
            "helix_available": HELIX_AVAILABLE,
            "coord_inference_available": HAS_COORD_INFERENCE,
            "coordinator_connected": self._coordinator is not None,
            "watching": self._watching,
            "queue_size": len(self._ingest_queue),
            "processed_files": len(self._processed_files),
            "tick_count": self._tick_count,
            "portal_architecture": {
                "coordinate_cards_produced": self._stats.get("coordinate_cards_produced", 0),
                "collision_coordinates_received": self._stats.get("collision_coordinates_received", 0),
                "massless_ingests": self._stats.get("massless_ingests", 0),
            },
            "stats": self._stats.copy(),
        }


# ==============================================================================
# SINGLETON ACCESS
# ==============================================================================

_ingest_fairy: Optional[SRMIngestFairy] = None


def get_ingest_fairy() -> Optional[SRMIngestFairy]:
    """Get the global ingest fairy instance."""
    return _ingest_fairy


def set_ingest_fairy(fairy: SRMIngestFairy) -> None:
    """Set the global ingest fairy instance."""
    global _ingest_fairy
    _ingest_fairy = fairy


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== SRM INGEST FAIRY TEST ===\n")

    # Create fairy
    fairy = SRMIngestFairy()
    fairy.on_boot()

    # Test basic ingest
    print("--- Testing basic ingest ---")
    card_id = fairy.ingest(
        content={
            "type": "test",
            "message": "Hello from ingest fairy test",
            "data": {"foo": "bar"},
        },
        source="test_script",
        ownership_level=OwnershipLevel.SYSTEM,
    )
    print(f"Created card: {card_id}")

    # Test foundation session
    print("\n--- Testing foundation session ---")
    session_id = fairy.ingest_foundation_session(
        content={
            "topic": "Testing helix memory integration",
            "decisions": ["Create ingest fairy", "Wire to collision chamber"],
        },
        session_id="test_session_001",
        created_by="TestScript",
        keywords=["test", "memory", "helix"],
    )
    print(f"Foundation session card: {session_id}")

    # Test batch ingest
    print("\n--- Testing batch ingest ---")
    card_ids = fairy.ingest_batch(
        items=[
            {"type": "batch_item", "index": 0, "data": "first"},
            {"type": "batch_item", "index": 1, "data": "second"},
            {"type": "batch_item", "index": 2, "data": "third"},
        ],
        source="batch_test",
    )
    print(f"Batch cards: {card_ids}")

    # Status
    print(f"\nStatus: {fairy.status()}")

    # Shutdown
    fairy.on_shutdown()
