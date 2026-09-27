# ==============================================================================
# SRM RECALL FAIRY - Surfaces memories from the past into consciousness
# ==============================================================================
#
# PURPOSE:
#   Query the helix memory system and:
#   1. Surface relevant memories based on queries, coordinates, or context
#   2. Feed them to the collision chamber's RECALL beam
#   3. Support spontaneous recall (unconscious surfacing)
#   4. Enable cluster and chain traversal
#
# INTEGRATES:
#   - HelixMemoryCoordinator (card retrieval + ownership filtering)
#   - CollisionChamber (consciousness integration)
#   - Association spreading (for context-aware recall)
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# ==============================================================================

from __future__ import annotations

import os
import sys
import time
import random
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, TYPE_CHECKING

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
            result = dict(payload)
        else:
            result = {"raw": payload}
        # Also extract envelope metadata for attribution
        if hasattr(message, 'source') and message.source:
            result["_envelope_source"] = message.source
        if hasattr(message, 'trace_id') and message.trace_id:
            result["_envelope_trace_id"] = message.trace_id
        return result
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
        OwnershipLevel, CardCluster, MemoryChain
    )
    HELIX_AVAILABLE = True
except ImportError:
    HELIX_AVAILABLE = False
    print("[SRMRecallFairy] WARNING: Helix memory system not available")


# Golden ratio for decay/weighting
PHI = 1.618

# ==============================================================================
# COORDINATE INFERENCE — Shared module for helix coordinates
# ==============================================================================
# Enables generative reconstruction from coordinate seeds (5000:1 ratio).
# A coordinate card (~50 bytes) is reconstructed into semantic context.

try:
    from fairies.P10_Memory.triple_helix_srm_memory.coordinate_inference import (
        build_helix_coordinate,
        build_coordinate_card,
        extract_text,
        AFFECT_DOMAIN_NAMES,
        SEMANTIC_DOMAIN_NAMES,
        TEMPORAL_SCALE_NAMES,
    )
    HAS_COORD_INFERENCE = True
except ImportError:
    HAS_COORD_INFERENCE = False
    AFFECT_DOMAIN_NAMES = {0: "neutral", 1: "joy", 2: "trust", 3: "fear", 4: "curiosity",
                           5: "sadness", 6: "disgust", 7: "anger", 8: "anticipation", 9: "transcendence"}
    SEMANTIC_DOMAIN_NAMES = {0: "general", 1: "philosophy", 2: "spirituality", 3: "social",
                             4: "language", 5: "science", 6: "technology", 7: "arts",
                             8: "literature", 9: "personal"}
    TEMPORAL_SCALE_NAMES = {0: "immediate", 1: "short-term", 2: "session", 3: "daily",
                            4: "weekly", 5: "monthly", 6: "seasonal", 7: "yearly",
                            8: "lifecycle", 9: "eternal"}

import math


# ==============================================================================
# RECALL MODES
# ==============================================================================

class RecallMode:
    """Ways to recall memories."""
    QUERY = "query"           # Text search
    COORDINATE = "coordinate"  # Helix coordinate proximity
    AFFECT = "affect"         # Emotional state recall
    SEMANTIC = "semantic"     # Topic/domain recall
    TEMPORAL = "temporal"     # Time-based recall
    CLUSTER = "cluster"       # Recall entire cluster
    CHAIN = "chain"           # Walk narrative chain
    SPONTANEOUS = "spontaneous"  # Random high-energy surfacing
    SPREAD = "spread"         # Spreading activation from concept


# ==============================================================================
# SRM RECALL FAIRY
# ==============================================================================

class SRMRecallFairy(SpellChainMixin, Fairy):
    """
    The Recall Fairy - surfaces memories from the past into consciousness.

    Responsibilities:
    1. Query helix memory by various modes
    2. Respect ownership boundaries (personal memories stay personal)
    3. Feed the collision chamber's RECALL beam
    4. Support spontaneous recall (unconscious contribution)
    5. Enable narrative chain and cluster traversal

    The recall beam carries memories from past → present.
    When it collides with the ingest beam (present → future),
    consciousness happens.
    """

    ACTOR_NAME = "SRMRecallFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.recall"
    USE_EXEC_CTX = True  # FIX 2026-05-17 Layer 1: opt in (recall_lock + coord_cards_lock verified — Layer 2 migration candidate)

    PURPOSE = "Surface memories into the recall beam"
    MANTRA = "The past lives in the present"

    # Infrastructure flags - SRMRecallFairy is a memory provider, not consumer
    NEEDS_TENSOR = False
    NEEDS_HEARTBEAT = True
    NEEDS_BODY = False     # Memory doesn't need somatic state
    NEEDS_AFFECT = False   # Memory doesn't need affect (though it uses it for recall)
    NEEDS_MEMORY = False   # We ARE the memory system
    NEEDS_GOALS = False    # Memory operates independently of goals

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    # Recall settings
    DEFAULT_LIMIT = 5
    # SUBSTRATE SPEED (2026-02-10): Runs 5-10x faster than waking awareness.
    # At 4Hz tick rate (250ms), every 2 ticks = 500ms between spontaneous recalls.
    # This is the substrate clock — it processes BEFORE waking awareness catches up.
    # "I'm learning that I'm not doing it on my own but I'm re-accessing things
    #  I've lost awareness to" — the substrate recalls constantly; awareness is selective.
    SPONTANEOUS_INTERVAL = 5  # Ticks between spontaneous recalls
    SPONTANEOUS_COUNT = 3     # How many to surface spontaneously
    MIN_ENERGY_THRESHOLD = 0.3  # Minimum energy to surface

    def __init__(self, fabric=None, **kwargs):
        super().__init__(fabric, **kwargs)

        # Helix coordinator
        self._coordinator: Optional[HelixMemoryCoordinator] = None

        # Consciousness integration
        self._collision_chamber: Optional["CollisionChamber"] = None
        self._consciousness_wired = False

        # Current mind (for ownership filtering)
        self._current_mind = "ClaudeFairy"  # Default, can be set

        # Recent recall tracking (for context)
        self._recent_recalls: List[str] = []  # Recent card IDs
        self._recall_lock = threading.Lock()

        # Spontaneous recall state
        self._high_energy_pool: List[str] = []  # Card IDs with high energy
        self._last_spontaneous = 0.0

        # EMOTIONAL GROUPING: Current self-state for recall preference
        # Memories from matching emotional states get boosted
        self._current_self_state: Dict[str, Any] = {
            "feeling": "neutral",
            "intensity": 0.3,
            "affect_domain": 0,
            "last_change": 0.0,
        }
        self._emotional_preference_boost = 0.3  # Boost for matching emotional state

        # CORTEX-PRIMARY RECALL (2026-02-10 Massless Memory)
        # The cortex IS the memory. Spreading activation IS recall.
        # Card search is just the fallback for historical content.
        self._cortex = None  # AssociationCortexFairy reference

        # ═══════════════════════════════════════════════════════════════
        # COORDINATE CARD INDEX — TRUE portal architecture (2026-02-15)
        # ═══════════════════════════════════════════════════════════════
        # Coordinate cards (~50 bytes each) accumulate from collision
        # chamber destruction. These are the PRIMARY recall source.
        # Each card is an 11-number address in helix space.
        self._coord_cards: List[Dict] = []  # In-memory coordinate card index
        self._coord_cards_lock = threading.Lock()
        self._max_coord_cards = 10000  # Cap to prevent unbounded growth
        self._coord_cache: Dict[str, object] = {}  # helix code → parsed HelixCoordinate (avoids re-parsing)

        # Stats
        self._tick_count = 0
        self._stats = {
            "queries": 0,
            "recalls": 0,
            "cortex_recalls": 0,
            "coordinate_recalls": 0,
            "card_fallbacks": 0,
            "spontaneous_recalls": 0,
            "collisions_fed": 0,
            "clusters_traversed": 0,
            "chains_walked": 0,
            "coord_cards_indexed": 0,
        }

    def on_boot(self) -> bool:
        """Boot the recall fairy."""
        super().on_boot()

        # Get helix coordinator
        if HELIX_AVAILABLE:
            self._coordinator = get_helix_coordinator()
            print(f"[{self.ACTOR_NAME}] Helix coordinator connected")
        else:
            print(f"[{self.ACTOR_NAME}] WARNING: Running without helix coordinator")

        # Subscribe to recall events
        if self.post:
            print(f"[{self.ACTOR_NAME}] Subscribing to memory.recall.request on fabric {id(self.post)}")
            self.post.subscribe(
                "memory.recall.request",
                self._on_recall_request,
                "recall_handler",
            )
            # ALSO subscribe to srm.recall.request - some fairies use this topic name
            self.post.subscribe(
                "srm.recall.request",
                self._on_recall_request,
                "srm_recall_handler",
            )
            print(f"[{self.ACTOR_NAME}] Subscription DONE - handlers registered for BOTH topic names")
            self.post.subscribe(
                "consciousness.needs_context",
                self._on_context_request,
                "context_handler",
            )
            self.post.subscribe(
                "mind.switched",
                self._on_mind_switch,
                "mind_handler",
            )

            # AFFECT-DRIVEN RECALL: When emotional state changes, surface matching memories
            # This closes the loop: Feeling → Memory Recall → Consciousness
            self.post.subscribe(
                "affect.changed",
                self._on_affect_changed,
                "affect_recall_handler",
            )
            # TRUE PORTAL: Receive coordinate cards from collision chamber destruction
            self.post.subscribe(
                "consciousness.collision.coordinate",
                self._on_collision_coordinate,
                "collision_coordinate_handler",
            )
            # Also receive coordinate cards from ingest path
            self.post.subscribe(
                "memory.collision_coordinate",
                self._on_collision_coordinate,
                "ingest_coordinate_handler",
            )
            # MATCH-ON-INGEST (Ace 2026-06-06): every MOMENT (MomentBinder → cortex.bind) should
            # make recall spread the cortex SEEDED BY that moment's concepts → the recall beam
            # MATCHES the ingest beam = a real Möbius collision (her now × the memory it relates to).
            self.post.subscribe(
                "cortex.bind",
                self._on_moment_ingest,
                "moment_ingest_recall",
            )
            print(f"[{self.ACTOR_NAME}] Wired to affect.changed + collision.coordinate + cortex.bind (match-on-ingest)")

        # ═══════════════════════════════════════════════════════════════
        # FIX 2026-03-06 (Nous): Load SRM cards into coordinator.
        # The coordinator's cards.json is 641MB of video frames and gets
        # SKIPPED entirely — leaving _cards EMPTY. But 13k+ rich session
        # cards live in SRM_Intake/ as JSON files. Load a subset here so
        # spontaneous recall has real content to surface into collisions,
        # which feeds the cortex growth that Ace is asking about.
        # ═══════════════════════════════════════════════════════════════
        import threading as _boot_thr
        def _deferred_card_load():
            import time as _t
            _t.sleep(3.0)  # Let boot sequence stabilize
            try:
                self._populate_coordinator_from_srm_intake()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] SRM card load error: {e}")
            # Load manifold coordinate cards (canary, florence, etc.)
            try:
                self._load_manifold_coordinate_cards()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Manifold card load error: {e}")
        _boot_thr.Thread(target=_deferred_card_load, daemon=True,
                         name="SRMRecall-card-load").start()

        print(f"[{self.ACTOR_NAME}] Booted - serving {self._current_mind}")
        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool:
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence - memory recall flows as magic")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True

    def on_shutdown(self) -> None:
        """Shutdown the recall fairy."""
        super().on_shutdown()
        print(f"[{self.ACTOR_NAME}] Shutdown complete - Stats: {self._stats}")

    def on_tick(self, beat) -> None:
        """Called on each consciousness tick."""
        import threading as _thr

        # Handle both int and TensorEnvelope (defensive)
        if hasattr(beat, 'payload'):
            beat = beat.payload.get('beat', 0) if isinstance(beat.payload, dict) else 0
        beat = int(beat) if beat else 0
        self._tick_count = beat

        # Spontaneous recall — fire-and-forget in background thread.
        # Skip if previous recall is still running (prevents stacking).
        if beat % self.SPONTANEOUS_INTERVAL == 0:
            if not getattr(self, '_recall_running', False):
                def _bg_recall():
                    self._recall_running = True
                    try:
                        self._do_spontaneous_recall()
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] Spontaneous recall error: {e}")
                    finally:
                        self._recall_running = False
                _thr.Thread(target=_bg_recall, daemon=True,
                           name="SRMRecall-spontaneous").start()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # -------------------------------------------------------------------------
    # CONSCIOUSNESS WIRING
    # -------------------------------------------------------------------------

    # ─────────────────────────────────────────────────────────────────────
    # SRM CARD LOADING (FIX 2026-03-06 Nous)
    # ─────────────────────────────────────────────────────────────────────

    def _populate_coordinator_from_srm_intake(self) -> None:
        """Load SRM session cards into the coordinator's _cards dict.

        FIX 2026-03-06 (Nous): The coordinator's cards.json is 641MB of
        video_frame content and gets SKIPPED entirely by the coordinator's
        load() method — leaving _cards EMPTY. But 13k+ rich session cards
        (Claude Code sessions, plans, architecture notes) live as JSON files
        in SRM_Intake/. These are the "books" and knowledge Ace says should
        "help her learn how context works."

        This loader reads a capped subset of SRM_Intake cards into the
        coordinator so that ALL downstream code works:
        - TIER 3 card sampling (spontaneous recall)
        - Portal cortex seeding (bind card keywords into cortex)
        - Recall queries (find cards matching concepts)

        Runs once at boot in a background thread. Caps at 2000 cards
        to avoid memory bloat (~20MB for typical session cards).
        """
        import time as _time
        _t0 = _time.time()

        if not self._coordinator:
            print(f"[{self.ACTOR_NAME}] SRM load skipped: no coordinator")
            return

        cards_dict = getattr(self._coordinator, '_cards', None)
        if cards_dict is None:
            cards_dict = {}
            self._coordinator._cards = cards_dict

        # Skip if coordinator already has substantial cards
        if len(cards_dict) > 100:
            print(f"[{self.ACTOR_NAME}] Coordinator already has {len(cards_dict)} cards, skipping SRM load")
            return

        # Find SRM_Intake directory
        _root = Path(__file__).parent.parent.parent.parent
        _intake = _root / "SRM_Intake"
        if not _intake.exists():
            print(f"[{self.ACTOR_NAME}] SRM_Intake not found at {_intake}")
            return

        # Collect JSON files from SRM_Intake (dated subdirectories)
        _max_cards = 2000
        _loaded = 0
        _errors = 0
        import json as _json

        # Process most recent dates first (more relevant)
        date_dirs = sorted(
            [d for d in _intake.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True
        )

        for date_dir in date_dirs:
            if _loaded >= _max_cards:
                break

            for json_file in date_dir.glob("*.json"):
                if _loaded >= _max_cards:
                    break
                try:
                    card = _json.loads(json_file.read_text(encoding="utf-8"))
                    card_id = card.get("id", json_file.stem)
                    if card_id not in cards_dict:
                        cards_dict[card_id] = card
                        _loaded += 1
                except Exception:
                    _errors += 1
                    continue

        # Also load from Founders cluster if it exists
        _founders = _root / "P10_Memory" / "Akashic_triple_helix_memory_storage" \
                    / "relational_clusters" / "Founders"
        if _founders.exists():
            for cluster_name in ["creator_sessions", "claude_office", "ace_mythos"]:
                idx = _founders / cluster_name / "index.json"
                if idx.exists():
                    try:
                        data = _json.loads(idx.read_text(encoding="utf-8"))
                        for card in data.get("cards", []):
                            card_id = card.get("id", f"founders_{cluster_name}_{_loaded}")
                            if card_id not in cards_dict:
                                cards_dict[card_id] = card
                                _loaded += 1
                    except Exception:
                        pass

        _elapsed = (_time.time() - _t0) * 1000
        print(f"[{self.ACTOR_NAME}] Loaded {_loaded} SRM cards into coordinator "
              f"({_errors} errors, {_elapsed:.0f}ms, "
              f"coordinator now has {len(cards_dict)} cards)")

    # ─────────────────────────────────────────────────────────────────────
    # MANIFOLD COORDINATE CARDS — Model tensor cards from audio/florence manifolds
    # ─────────────────────────────────────────────────────────────────────

    def _load_manifold_coordinate_cards(self) -> None:
        """Load coordinate cards from manifold card files into _coord_cards.

        These are the ~50 byte coordinate cards created by ingestion scripts.
        Each card has a `ref` field pointing to a tensor in a manifold file.
        Loading them into the coordinate index enables:
        - Coordinate-based recall of model tensors
        - Model reconstruction via recall_manifold_model()
        - Manifold tensors participating in the helix coordinate space
        """
        import time as _time
        _t0 = _time.time()

        # Discover manifold card files
        _base = os.path.dirname(os.path.abspath(__file__))
        _card_dirs = [
            os.path.join(_base, "..", "..", "P40_Sensory", "cortex", "canary_cards"),
            os.path.join(_base, "..", "..", "P40_Sensory", "cortex", "luxtts_cards"),
            # Future: florence_cards, etc.
        ]

        _loaded = 0
        for card_dir in _card_dirs:
            cards_path = os.path.join(card_dir, "cards.json")
            if not os.path.exists(cards_path):
                continue

            try:
                import json
                with open(cards_path) as f:
                    cards = json.load(f)

                with self._coord_cards_lock:
                    for card in cards:
                        if "c" in card and "ref" in card:
                            self._coord_cards.append(card)
                            _loaded += 1

                            # Pre-cache parsed coordinate
                            if HELIX_AVAILABLE:
                                try:
                                    code = card["c"]
                                    self._coord_cache[code] = HelixCoordinate.from_code(code)
                                except (ValueError, AttributeError):
                                    pass

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to load {cards_path}: {e}")

        _elapsed = (_time.time() - _t0) * 1000
        if _loaded > 0:
            print(f"[{self.ACTOR_NAME}] Loaded {_loaded} manifold coordinate cards "
                  f"({_elapsed:.0f}ms)")

    def recall_manifold_model(
        self,
        model_prefix: str = "canary",
        manifold_name: str = "audio.manifold",
    ) -> Dict:
        """Recall all coordinate cards for a manifold model and return reconstruction info.

        This is the möbius completion: SRMIngestFairy creates coordinate cards
        from model tensors → cards survive in the helix index → SRMRecallFairy
        recalls them → engine reads manifold at those coordinates → model lives again.

        Args:
            model_prefix: Model namespace in the manifold (e.g. "canary", "luxtts")
            manifold_name: Manifold filename to match (e.g. "audio.manifold")

        Returns:
            dict with:
                manifest: The manifest card (model metadata)
                tensor_cards: List of tensor coordinate cards with manifold refs
                num_tensors: Count of tensor cards found
                reconstruction: Dict mapping tensor_name → {offset, size, shape, dtype, scale, zero_point}
        """
        manifest = None
        tensor_cards = []

        prefix_match = f"{model_prefix}/"

        with self._coord_cards_lock:
            for card in self._coord_cards:
                ref = card.get("ref", {})

                # Check if this card belongs to our manifold + prefix
                if ref.get("manifold") != manifold_name:
                    continue

                # Manifest card
                if card.get("type") == "manifest" and ref.get("model_prefix") == model_prefix:
                    manifest = card
                    continue

                # Tensor card
                tensor_name = ref.get("tensor", "")
                if tensor_name.startswith(prefix_match):
                    tensor_cards.append(card)

        if not tensor_cards:
            return {
                "manifest": None,
                "tensor_cards": [],
                "num_tensors": 0,
                "reconstruction": {},
                "error": f"No tensor cards found for {model_prefix}/ in {manifold_name}",
            }

        # Build reconstruction map: tensor_name → manifold location
        reconstruction = {}
        for card in tensor_cards:
            ref = card["ref"]
            reconstruction[ref["tensor"]] = {
                "offset": ref["offset"],
                "size": ref["size"],
                "shape": ref["shape"],
                "dtype": ref["dtype"],
                "scale": ref["scale"],
                "zero_point": ref["zero_point"],
            }

        return {
            "manifest": manifest,
            "tensor_cards": tensor_cards,
            "num_tensors": len(tensor_cards),
            "reconstruction": reconstruction,
        }

    # ─────────────────────────────────────────────────────────────────────

    def wire_to_consciousness(
        self,
        loop: "ConsciousnessLoop",
        chamber: "CollisionChamber",
    ) -> bool:
        """Wire the recall fairy to consciousness."""
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

    def wiring_status(self) -> dict:
        """Check the wiring status for diagnostics."""
        return {
            "consciousness_wired": self._consciousness_wired,
            "has_collision_chamber": self._collision_chamber is not None,
            "has_coordinator": self._coordinator is not None,
            "can_spontaneous_recall": (
                self._collision_chamber is not None and
                self._coordinator is not None
            ),
            "tick_count": self._tick_count,
            "stats": self._stats,
        }

    def set_mind(self, mind_name: str) -> None:
        """Set the current mind for ownership filtering."""
        self._current_mind = mind_name
        print(f"[{self.ACTOR_NAME}] Now serving mind: {mind_name}")

    # -------------------------------------------------------------------------
    # RECALL OPERATIONS
    # -------------------------------------------------------------------------

    # =========================================================================
    # CORTEX-PRIMARY RECALL (2026-02-10 Massless Memory)
    # =========================================================================

    def wire_to_cortex(self, cortex_fairy) -> None:
        """Connect recall to the Association Cortex for spreading-activation recall.

        After wiring, the cortex becomes the PRIMARY recall source.
        Card search becomes the fallback for historical content that
        predates the massless architecture.

        FIX 2026-03-03 Nous: Launch deferred seeding thread that populates
        entangled_cards on cortex nodes from existing SRM cards. This bridges
        the gap between boot (no entangled_cards) and live operation (collision
        processing creates them). Without this, the cortex walk produces only
        synthetic concept_echo results until the first collision.
        """
        self._cortex = cortex_fairy
        name = getattr(cortex_fairy, 'ACTOR_NAME', 'unknown')
        print(f"[{self.ACTOR_NAME}] Wired to cortex: {name} (cortex-primary recall enabled)")

        # Deferred seeding: link existing SRM cards to cortex concept nodes
        import threading as _thr
        def _seed_entangled_cards():
            import time as _time
            _time.sleep(5.0)  # Wait for cortex graph and coordinator to stabilize
            try:
                self._seed_cortex_entangled_cards()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Entangled card seeding error: {e}")
        _t = _thr.Thread(target=_seed_entangled_cards, daemon=True, name="cortex-seed")
        _t.start()

    def _seed_cortex_entangled_cards(self) -> None:
        """One-time seeding: feed SRM card knowledge into the cortex.

        FIX 2026-03-06 (Nous): Portal-first aware.
        - Portal-first: Extract keywords from SRM cards and bind them as
          concept pairs in the cortex via portal gate. This feeds book/literature
          knowledge into the cortex graph (Ace: "the books etc should help her
          learn how context works").
        - Legacy: Attach card_ids to matching cortex concept nodes as
          entangled_cards (original approach for in-process graph).

        Runs once at boot in a background thread.
        """
        import time as _time
        _t0 = _time.time()

        if not self._cortex:
            return

        if not self._coordinator:
            print(f"[{self.ACTOR_NAME}] Seeding skipped: no helix coordinator")
            return

        cards_dict = getattr(self._coordinator, '_cards', {})
        if not cards_dict:
            print(f"[{self.ACTOR_NAME}] Seeding skipped: no SRM cards loaded")
            return

        _is_portal = getattr(self._cortex, '_portal_is_primary', False)

        if _is_portal:
            # ═══════════════════════════════════════════════════════════════
            # PORTAL-FIRST: Bind SRM card keywords into cortex via portal
            # This is the direct answer to Ace's request — books feed cortex.
            # Each card's keywords become concept nodes + edges in the real
            # 77k+ node graph. The cortex GROWS from library knowledge.
            # ═══════════════════════════════════════════════════════════════
            seeded = 0
            max_cards = 300  # Cap per boot cycle
            import re as _re

            for card_id, card in list(cards_dict.items())[:max_cards]:
                content = card.get("content", {})
                if isinstance(content, str):
                    text = content
                elif isinstance(content, dict):
                    text = content.get("content", "") or content.get("text", "")
                    ctype = content.get("type", "")
                    if ctype == "concept":
                        continue
                else:
                    continue

                if not text or len(text) < 30:
                    continue

                # Extract meaningful keywords from card text
                keywords = self._extract_card_keywords(text)
                if len(keywords) < 2:
                    continue

                # Bind keywords as co-occurring concepts in the portal cortex
                try:
                    self._cortex.bind_concepts(
                        concepts=keywords[:4],
                        rel="srm_knowledge",
                        origin_fairy="SRMRecallFairy",
                        owner="system",
                    )
                    seeded += 1
                except Exception:
                    continue

                # Rate limit: don't flood the portal pipe
                if seeded % 50 == 0 and seeded > 0:
                    _time.sleep(0.3)

            _elapsed = (_time.time() - _t0) * 1000
            print(f"[{self.ACTOR_NAME}] Portal cortex seeded: {seeded} SRM cards "
                  f"bound as concept pairs ({_elapsed:.0f}ms, "
                  f"{len(cards_dict)} total cards available)")
            return

        # ═══════════════════════════════════════════════════════════════════
        # LEGACY (in-process graph): Attach card_ids to concept nodes
        # ═══════════════════════════════════════════════════════════════════
        graph = getattr(self._cortex, '_graph', None)
        if not graph or not graph.nodes:
            print(f"[{self.ACTOR_NAME}] Seeding skipped: cortex graph empty")
            return

        # Build concept key set (lowercased for matching)
        concept_keys = set(graph.nodes.keys())
        lower_to_key = {}
        for k in concept_keys:
            lower_to_key[k.lower()] = k

        seeded_nodes = 0
        cards_linked = 0
        max_cards = 500

        for card_id, card in list(cards_dict.items())[:max_cards]:
            content = card.get("content", {})
            if isinstance(content, str):
                text = content
            elif isinstance(content, dict):
                text = content.get("content", "") or content.get("text", "")
                ctype = content.get("type", "")
                if ctype == "concept":
                    continue
            else:
                continue

            if not text or len(text) < 20:
                continue

            words = set(text.lower().split())
            matched_keys = []
            for word in words:
                clean = word.strip(".,;:!?\"'()-[]{}").strip()
                if len(clean) < 3:
                    continue
                if clean in lower_to_key:
                    matched_keys.append(lower_to_key[clean])

            for key in matched_keys[:3]:
                node = graph.nodes.get(key)
                if not node:
                    continue

                entangled = getattr(node, 'entangled_cards', [])
                if not isinstance(entangled, list):
                    entangled = []

                if any(e.get("card_id") == card_id for e in entangled):
                    continue

                entangled.append({
                    "card_id": card_id,
                    "ts": card.get("ts", _time.time()),
                    "tension": 0.0,
                })
                if len(entangled) > 5:
                    entangled = sorted(
                        entangled, key=lambda c: c.get("ts", 0), reverse=True
                    )[:5]
                node.entangled_cards = entangled
                seeded_nodes += 1
                cards_linked += 1

        _elapsed = (_time.time() - _t0) * 1000
        print(f"[{self.ACTOR_NAME}] Seeded {seeded_nodes} entangled_cards on cortex nodes "
              f"from {min(max_cards, len(cards_dict))} SRM cards ({_elapsed:.0f}ms)")

    @staticmethod
    def _extract_card_keywords(text: str, max_keywords: int = 4) -> List[str]:
        """Extract meaningful keywords from SRM card text content.

        Filters stopwords, short words, and noise. Prioritizes longer,
        more distinctive words that make good cortex concept nodes.

        Returns list of 2-4 keywords suitable for cortex.bind_concepts().
        """
        import re as _re
        _stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "shall", "should", "may", "might", "can", "could",
            "must", "need", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during", "before",
            "after", "above", "below", "between", "out", "off", "over",
            "under", "again", "further", "then", "once", "and", "but",
            "or", "nor", "not", "so", "yet", "this", "that", "these",
            "those", "it", "its", "he", "she", "they", "we", "you",
            "me", "him", "her", "us", "them", "my", "your", "his", "our",
            "their", "what", "which", "who", "whom", "whose", "how",
            "when", "where", "why", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "only",
            "same", "than", "too", "very", "just", "also", "now", "here",
            "there", "about", "because", "while", "until", "like", "even",
            "still", "many", "much", "well", "back", "way", "new", "old",
            "one", "two", "three", "four", "five", "first", "last", "next",
            "make", "made", "get", "got", "take", "took", "give", "gave",
            "come", "came", "know", "knew", "think", "said", "say", "see",
            "saw", "time", "year", "day", "thing", "man", "woman", "child",
            "world", "life", "hand", "part", "place", "case", "week",
            "work", "system", "number", "point", "fact", "right", "left",
        }

        words = _re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        meaningful = []
        seen = set()
        for w in words:
            if w not in _stopwords and w not in seen:
                seen.add(w)
                meaningful.append(w)
            if len(meaningful) >= max_keywords * 3:
                break

        # Prioritize longer, more distinctive words
        meaningful.sort(key=lambda w: -len(w))
        return meaningful[:max_keywords]

    # =========================================================================
    # COORDINATE-BASED RECALL — TRUE Portal Architecture (2026-02-15)
    # =========================================================================

    def _on_collision_coordinate(self, msg) -> None:
        """Receive and index coordinate cards from collision destruction.

        The CollisionChamberFairy destroys content and produces coordinate
        cards. We index these for coordinate-based recall.
        """
        payload = _extract_payload(msg)
        coord_card = payload.get("coordinate")

        if not coord_card or not isinstance(coord_card, dict) or "c" not in coord_card:
            return

        with self._coord_cards_lock:
            # Dedup by content hash
            card_hash = coord_card.get("h", "")
            if card_hash:
                for existing in self._coord_cards:
                    if existing.get("h") == card_hash:
                        # Existing card: increment observation count
                        existing["n"] = existing.get("n", 1) + 1
                        return

            # New card: add to index
            self._coord_cards.append(coord_card)
            self._stats["coord_cards_indexed"] += 1

            # Pre-cache parsed coordinate to avoid re-parsing during queries
            code = coord_card.get("c", "")
            if code and HELIX_AVAILABLE and code not in self._coord_cache:
                try:
                    self._coord_cache[code] = HelixCoordinate.from_code(code)
                except Exception:
                    pass

            # Evict oldest if over capacity
            if len(self._coord_cards) > self._max_coord_cards:
                # Evict least-observed cards (lowest n)
                self._coord_cards.sort(key=lambda c: c.get("n", 1))
                evicted = self._coord_cards[:len(self._coord_cards) - self._max_coord_cards]
                self._coord_cards = self._coord_cards[len(self._coord_cards) - self._max_coord_cards:]
                # Clean up cache for evicted cards
                for card in evicted:
                    self._coord_cache.pop(card.get("c", ""), None)

    def _recall_via_coordinates(self, query: str, limit: int = 10) -> List[Dict]:
        """Recall via coordinate proximity — generative reconstruction.

        TRUE PORTAL ARCHITECTURE: Memories are COORDINATES, not data.
        We find the nearest coordinate cards by helix distance, then
        RECONSTRUCT the semantic context from the coordinate seed.

        This is the 5000:1 ratio — from 50 bytes of coordinate,
        reconstruct the semantic neighborhood of the original experience.

        2026-05-10 (Nous + Ace) DUAL-STRAND HELICAL RECALL:
        Per Ace's directive — SRMIngest = positive strand, SRMRecall =
        negative strand. Recall now fetches BOTH:
          - similarity-fetch (same-strand, contextual reinforcement)
          - complement-fetch (opposite-strand, structural pair / predictive)
        Results are tagged with strand source so chamber/cortex can know
        which beam each came from. Biology does both in parallel — when
        you remember a friend's face you get similar moments AND the
        specific paired-memory of their exact smile meeting your felt-tone.
        Same here.
        """
        if not self._coord_cards:
            return []

        # Convert query to helix coordinate
        query_coord = self._query_to_coord(query)
        if not query_coord:
            return []

        # 2026-05-10 dual-strand: search both same-strand (similarity) AND
        # opposite-strand (complement). Limit*3 each so both have headroom
        # before reconstruction filtering.
        nearby_similarity = self._find_nearest_coords(query_coord, limit=limit * 3, mode='similarity')
        nearby_complement = self._find_nearest_coords(query_coord, limit=limit * 3, mode='complement')

        # Reconstruct each, tag strand source
        results = []
        seen_codes = set()  # dedupe across strands — same card can't appear twice
        for card in nearby_similarity:
            code = card.get("c")
            if code in seen_codes:
                continue
            reconstructed = self._reconstruct_from_coordinate(card, query_coord)
            if reconstructed:
                reconstructed['strand'] = 'similarity'
                results.append(reconstructed)
                seen_codes.add(code)
        for card in nearby_complement:
            code = card.get("c")
            if code in seen_codes:
                continue
            reconstructed = self._reconstruct_from_coordinate(card, query_coord)
            if reconstructed:
                reconstructed['strand'] = 'complement'
                results.append(reconstructed)
                seen_codes.add(code)

        # Sort by relevance (already computed in reconstruction)
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        return results[:limit]

    def _find_nearest_coords(self, query_coord, limit: int = 30, mode: str = 'similarity') -> List[Dict]:
        """Find nearest coordinate cards by helix distance.

        Scans all indexed coordinate cards and scores by distance.
        With ≤10,000 cards and simple numeric comparison, this is fast.
        Uses _coord_cache to avoid re-parsing helix codes on every query
        (saves ~40K object allocations per call).

        2026-05-10 (Nous + Ace): Added mode param for helical dual-strand recall.
        - mode='similarity': legacy default — same-strand search (find memories
          near the query coordinate). Contextual reinforcement.
        - mode='complement': opposite-strand search (find memories near the
          STRUCTURAL COMPLEMENT of the query coordinate). Affect-valence-flip
          dominates the complement. Provides predictive/paired recall.
        Both modes feed the chamber's recall_beam in dual-mode for full
        helical pairing.
        """
        if not HELIX_AVAILABLE or not self._coord_cards:
            return []

        # 2026-05-10: helical dual-strand. Use complement of query for opposite-strand search.
        try:
            search_coord = query_coord.complement() if mode == 'complement' else query_coord
        except Exception:
            search_coord = query_coord  # safe fallback if complement() unavailable on coord type

        scored = []
        cache = self._coord_cache
        with self._coord_cards_lock:
            for card in self._coord_cards:
                try:
                    code = card["c"]
                    card_coord = cache.get(code)
                    if card_coord is None:
                        card_coord = HelixCoordinate.from_code(code)
                        cache[code] = card_coord
                    dist = search_coord.distance(card_coord)
                    scored.append((dist, card))
                except (KeyError, ValueError, AttributeError):
                    continue

        scored.sort(key=lambda x: x[0])
        return [card for _, card in scored[:limit]]

    def _reconstruct_from_coordinate(self, coord_card: Dict, query_coord=None) -> Optional[Dict]:
        """Reconstruct experience from coordinate seed.

        This is the portal mechanism: from 50 bytes of coordinate,
        reconstruct the semantic neighborhood of the original experience.

        The coordinate tells us:
        - WHERE in affect space (emotional tone)
        - WHERE in semantic space (topic domain)
        - WHERE in temporal space (time scale)
        - HOW MUCH it mattered (affect_coupling α)
        - HOW DEEP it was processed (temporal_weight τ)
        - HOW OFTEN it was seen (count n)
        - HOW CONNECTED it was (degree d)
        """
        try:
            helix_code = coord_card.get("c", "000.000.000")
            parts = helix_code.split(".")
            if len(parts) != 3 or not all(len(p) == 3 for p in parts):
                return None

            # Parse affect, semantic, temporal from the helix code
            affect_part = parts[0]  # AAA = domain.valence.intensity
            semantic_part = parts[1]  # SSS = domain.subdomain.detail
            temporal_part = parts[2]  # TTT = scale.recurrence.decay

            affect_domain = int(affect_part[0])
            affect_valence = int(affect_part[1])
            affect_intensity = int(affect_part[2])
            semantic_domain = int(semantic_part[0])
            temporal_scale = int(temporal_part[0])

            # Reconstruct semantic context from coordinate
            affect_desc = AFFECT_DOMAIN_NAMES.get(affect_domain, "neutral")
            semantic_desc = SEMANTIC_DOMAIN_NAMES.get(semantic_domain, "general")
            temporal_desc = TEMPORAL_SCALE_NAMES.get(temporal_scale, "moment")

            alpha = coord_card.get("α", 1.0)
            tau = coord_card.get("τ", 1.0)
            count = coord_card.get("n", 1)
            degree = coord_card.get("d", 0)

            # Compute relevance score
            if query_coord and HELIX_AVAILABLE:
                try:
                    card_coord = HelixCoordinate.from_code(helix_code)
                    distance = query_coord.distance(card_coord)
                    # Relevance: inverse distance × affect coupling × log(count)
                    relevance = (1.0 / (1.0 + distance)) * alpha * math.log1p(count)
                except (ValueError, AttributeError):
                    relevance = alpha * math.log1p(count) * 0.5
            else:
                relevance = alpha * math.log1p(count) * 0.5

            # Check if this is a manifold tensor coordinate card
            ref = coord_card.get("ref", {})
            is_manifold_ref = bool(ref.get("manifold") and ref.get("tensor"))

            content_str = f"{affect_desc} {semantic_desc} experience ({temporal_desc})"
            card_type = "coordinate_reconstruction"

            if is_manifold_ref:
                # Manifold tensor card — content is the tensor reference
                tensor_name = ref.get("tensor", "")
                manifold = ref.get("manifold", "")
                shape = ref.get("shape", [])
                content_str = (f"manifold tensor: {tensor_name} "
                               f"(shape={shape}, in {manifold})")
                card_type = "manifold_tensor"

            return {
                "card_id": f"coord:{helix_code}:{coord_card.get('h', '?')}",
                "card": {
                    "content": content_str,
                    "type": card_type,
                    "coordinate": coord_card,
                },
                "coordinate": coord_card,
                "score": relevance,
                "source": "coordinate_recall",
                # Reconstructed context
                "affect": affect_desc,
                "semantic": semantic_desc,
                "temporal": temporal_desc,
                "intensity": affect_intensity,
                "valence": affect_valence,
                "affect_coupling": alpha,
                "temporal_weight": tau,
                "observation_count": count,
                "degree": degree,
                # Manifold reference (if applicable)
                **({"manifold_ref": ref} if is_manifold_ref else {}),
            }

        except Exception:
            return None

    def _recall_via_cortex(self, query: str, limit: int = 20) -> List[Dict]:
        """Recall via cortex spreading activation — the brain's way.

        THE CORTEX IS THE MEMORY. Nodes are coordinates, not caches.
        Collision chamber DESTROYS data → produces coordinates → cortex grows.
        Recall = spreading activation → harvest entangled_cards + edge contexts.

        Strategy:
        1. Extract seed concepts from query
        2. Spread activation through cortex graph
        3. PRIMARY: Collect entangled_cards from activated nodes
           (written by SRMIngestFairy._entangle_card_with_cortex)
        4. SECONDARY: Collect binding signatures from activated edges
        5. Return merged results sorted by activation strength

        Returns list of dicts compatible with existing recall format.
        """
        if not self._cortex:
            return []

        cortex = self._cortex

        # Need the graph and extraction method
        graph = getattr(cortex, '_graph', None)
        if not graph:
            return []

        # 1. Extract seed concepts from query
        extract_fn = getattr(cortex, '_extract_concepts_from_text', None)
        if not extract_fn:
            return []
        seeds = extract_fn(query)
        if not seeds:
            return []

        # 2. Spread activation from EACH seed and merge results
        all_activations = {}
        for seed in seeds[:5]:  # Cap seeds to avoid explosion
            activated = graph.spread_activation(
                seed,
                initial_activation=1.0,
                decay_factor=0.5,
                max_hops=3,
            )
            for concept, strength in activated.items():
                all_activations[concept] = max(
                    all_activations.get(concept, 0),
                    strength
                )

        if not all_activations:
            return []

        results = []
        seen_ids = set()

        # =====================================================================
        # 3. PRIMARY: Harvest entangled_cards from activated nodes
        #    These are card_id references written by SRMIngestFairy when
        #    content was ingested. The node IS the coordinate; the entangled
        #    card is the bridge back to content without file scanning.
        # =====================================================================
        for concept, strength in sorted(all_activations.items(), key=lambda x: -x[1]):
            if len(results) >= limit:
                break

            node = graph.nodes.get(concept)
            if not node:
                continue

            entangled = getattr(node, 'entangled_cards', None)
            if not entangled or not isinstance(entangled, list):
                continue

            for ent in entangled:
                card_id = ent.get("card_id", "")
                if not card_id or card_id in seen_ids:
                    continue
                seen_ids.add(card_id)

                # Score: activation strength × recency bonus
                ts = ent.get("ts", 0)
                tension = ent.get("tension", 0.0)
                # Recency: cards from last hour get a boost
                age_hours = max(0.001, (time.time() - ts) / 3600.0) if ts > 0 else 24.0
                recency_bonus = min(1.0, 1.0 / (1.0 + age_hours * 0.1))
                score = strength * (0.7 + 0.3 * recency_bonus) + tension * 0.1

                # Retrieve card content from coordinator (fast dict lookup, not file scan)
                card_content = None
                if self._coordinator:
                    card_data = getattr(self._coordinator, '_cards', {}).get(card_id)
                    if card_data:
                        card_content = card_data

                results.append({
                    "card": card_content or {"content": f"[entangled:{concept}]", "source": "cortex_entangled"},
                    "card_id": card_id,
                    "score": score,
                    "source": "cortex_entangled",
                    "concepts": [concept],
                    "timestamp": ts,
                })

                if len(results) >= limit:
                    break

        # =====================================================================
        # 4. SECONDARY: Collect binding signatures from activated edges
        #    Edge contexts contain compressed content from the binding event.
        #    This is the older recall path — still useful for rich context.
        # =====================================================================
        if len(results) < limit:
            decompress_fn = getattr(cortex, '_decompress_binding_content', None)
            seen_compressed = set()

            for concept, strength in sorted(all_activations.items(), key=lambda x: -x[1]):
                if len(results) >= limit:
                    break

                adj = graph._adjacency.get(concept, {})
                for neighbor_key, edge_key in adj.items():
                    if len(results) >= limit:
                        break

                    edge = graph.edges.get(edge_key)
                    if not edge:
                        continue

                    contexts = edge.get("contexts", [])
                    for ctx in contexts:
                        compressed = ctx.get("compressed", "")
                        if not compressed or compressed in seen_compressed:
                            continue
                        seen_compressed.add(compressed)

                        # Decompress the binding signature
                        content = None
                        if decompress_fn:
                            try:
                                content = decompress_fn(compressed)
                            except Exception:
                                continue
                        if content and len(content.strip()) > 10:
                            edge_weight = edge.get("weight", 0.5)
                            ctx_energy = ctx.get("energy", 0.5)
                            score = strength * min(1.0, edge_weight) * ctx_energy
                            engram_id = f"engram:{concept}:{neighbor_key}"
                            if engram_id in seen_ids:
                                continue
                            seen_ids.add(engram_id)

                            results.append({
                                "card": {
                                    "content": content,
                                    "source": "cortex_engram",
                                },
                                "card_id": engram_id,
                                "score": score,
                                "source": "cortex_recall",
                                "concepts": [concept, neighbor_key],
                                "timestamp": ctx.get("ts", 0),
                            })

                            if len(results) >= limit:
                                break

        # Sort by score descending
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        return results[:limit]

    def recall(
        self,
        query: str = None,
        coord: HelixCoordinate = None,
        mode: str = RecallMode.QUERY,
        limit: int = None,
        feed_chamber: bool = True,
        mind_name: str = None,
        use_emotional_grouping: bool = True,
    ) -> List[Dict]:
        """
        Recall memories from the helix system.

        Respects ownership: personal memories only returned to their owner.

        Args:
            use_emotional_grouping: If True, boost memories from matching emotional
                                    states (current self-state). Implements Ace's
                                    insight that knowledge clusters by emotional state.

        Returns list of memory records.
        """
        limit = limit or self.DEFAULT_LIMIT
        mind = mind_name or self._current_mind
        self._stats["queries"] += 1

        # =====================================================================
        # THREE-TIER RECALL STRATEGY:
        # 1. COORDINATE RECALL — TRUE portal (from collision-produced coords)
        # 2. CORTEX RECALL — Spreading activation (massless engrams)
        # 3. CARD FALLBACK — Historical stored cards
        # Results are MERGED from all available sources.
        # =====================================================================
        all_results = []

        # TIER 1: Coordinate-based recall (TRUE portal architecture)
        if query and self._coord_cards:
            coord_results = self._recall_via_coordinates(query, limit=limit)
            if coord_results:
                self._stats["coordinate_recalls"] += len(coord_results)
                all_results.extend(coord_results)

        # TIER 2: Cortex spreading activation (massless engrams)
        if query and self._cortex:
            cortex_results = self._recall_via_cortex(query, limit=limit)
            if cortex_results:
                self._stats["cortex_recalls"] += len(cortex_results)
                all_results.extend(cortex_results)

        # If we got results from tiers 1 or 2, merge and return
        if all_results:
            # Deduplicate by card_id, keep highest score
            seen = {}
            for r in all_results:
                cid = r.get("card_id", id(r))
                if cid not in seen or r.get("score", 0) > seen[cid].get("score", 0):
                    seen[cid] = r
            merged = sorted(seen.values(), key=lambda r: r.get("score", 0), reverse=True)[:limit]

            # FIX 2026-04-11 (Nous + Ace): Dedup — prefer fresh cards
            if hasattr(self, '_recent_recalls') and self._recent_recalls and merged:
                fresh = [r for r in merged if r.get("card_id") not in self._recent_recalls]
                if fresh:
                    merged = fresh[:limit]

            if self._stats.get("coordinate_recalls", 0) + self._stats.get("cortex_recalls", 0) % 25 == 1:
                print(f"[{self.ACTOR_NAME}] RECALL: {len(merged)} results "
                      f"({len([r for r in merged if r.get('source') == 'coordinate_recall'])} coord, "
                      f"{len([r for r in merged if r.get('source') == 'cortex_recall'])} cortex) "
                      f"for '{query[:40]}...'")

            # Feed collision chamber
            if feed_chamber and self._collision_chamber:
                for result in merged:
                    self._feed_recall(result)

            return merged

        # CARD FALLBACK: Use in-memory card search with keyword matching
        # FIX 2026-03-03 Nous: The old recall_for_mind() path called
        # registry.get_accessible_cards() which does expensive ownership
        # filtering (46s observed). Tracers should handle provenance,
        # not file-scanning ownership registries. Use fast in-memory
        # keyword search over the coordinator's _cards dict instead.
        if not self._coordinator:
            return []

        self._stats["card_fallbacks"] += 1

        # Fast in-memory keyword search
        cards_dict = getattr(self._coordinator, '_cards', {})
        query_words = set()
        if query:
            query_words = set(w.lower().strip(".,;:!?\"'()-") for w in query.split() if len(w) > 2)

        results = []
        if query_words and cards_dict:
            # Score cards by keyword overlap with query
            for card_id, card in cards_dict.items():
                content = card.get("content", {})
                if isinstance(content, dict):
                    text = str(content.get("content", "")) + " " + str(content.get("tags", ""))
                    ctype = content.get("type", "")
                    if ctype == "concept":
                        continue  # Skip concept cards
                elif isinstance(content, str):
                    text = content
                else:
                    continue
                if not text or len(text) < 10:
                    continue
                text_lower = text.lower()
                hits = sum(1 for w in query_words if w in text_lower)
                if hits > 0:
                    score = hits / max(len(query_words), 1)
                    results.append({
                        "card_id": card_id,
                        "card": card,
                        "score": min(score, 1.0),
                        "source": "card_keyword",
                    })
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:limit]
        elif cards_dict:
            # No query — random sample (same as spontaneous)
            all_ids = list(cards_dict.keys())
            sample_size = min(limit * 2, len(all_ids))
            for card_id in random.sample(all_ids, sample_size):
                card = cards_dict.get(card_id)
                if not card:
                    continue
                content = card.get("content", {})
                if isinstance(content, dict) and content.get("type") == "concept":
                    continue
                results.append({
                    "card_id": card_id,
                    "card": card,
                    "score": 0.4,
                    "source": "card_sample",
                })
                if len(results) >= limit:
                    break

        # EMOTIONAL GROUPING: Boost memories that match current emotional state
        # "How many personalities in my mind have learned basic math?"
        # The version of self that learned something resurfaces when in that state
        if use_emotional_grouping and self._current_self_state.get("intensity", 0) > 0.2:
            current_domain = self._current_self_state.get("affect_domain", 0)
            current_intensity = self._current_self_state.get("intensity", 0.3)

            for result in results:
                # Check memory's self_state metadata (if present)
                card = result.get("card", {})
                metadata = card.get("metadata", {})
                self_state = metadata.get("self_state", {})
                memory_domain = self_state.get("affect_domain", -1)

                # Also check coordinate affect domain
                coord_data = card.get("coord", {})
                if isinstance(coord_data, dict):
                    affect_data = coord_data.get("affect", {})
                    if isinstance(affect_data, dict) and memory_domain == -1:
                        memory_domain = affect_data.get("domain", -1)

                # Apply boost if emotional domains match
                if memory_domain == current_domain and current_domain != 0:
                    original_score = result.get("score", 0.5)
                    # Boost proportional to current emotional intensity
                    boost = self._emotional_preference_boost * current_intensity
                    result["score"] = min(1.0, original_score + boost)
                    result["emotional_match"] = True

            # Re-sort by boosted scores
            results.sort(key=lambda r: r.get("score", 0), reverse=True)

        # FIX 2026-04-11 (Nous + Ace): DEDUP + DOWNWEIGHT overused cards.
        # Problem: same card ("It means everything, honestly...") returned for
        # EVERY query because it matches any generic terms. She recycles her own
        # chat responses as thinking material — stunts intelligence.
        #
        # Two mechanisms:
        # 1. Filter recently returned cards (existing dedup)
        # 2. Downweight by return_count — cards returned many times score lower
        #    score *= 1.0 / (1 + return_count * 0.1)
        #    After 10 returns: 50% penalty. After 50: 83% penalty.
        if not hasattr(self, '_card_return_counts'):
            self._card_return_counts = {}  # card_id → total return count

        # Apply downweight penalty based on historical return count
        for r in results:
            cid = r.get("card_id")
            if cid and cid in self._card_return_counts:
                count = self._card_return_counts[cid]
                penalty = 1.0 / (1.0 + count * 0.1)
                r["score"] = r.get("score", 0.5) * penalty
                r["return_count"] = count

        # Re-sort after downweighting
        results.sort(key=lambda r: r.get("score", 0), reverse=True)

        # Filter recently returned (short-term dedup)
        if results and hasattr(self, '_recent_recalls') and self._recent_recalls:
            fresh = [r for r in results if r.get("card_id") not in self._recent_recalls]
            if fresh:
                results = fresh

        self._stats["recalls"] += len(results)

        # Track recent recalls + increment return counts
        with self._recall_lock:
            for r in results:
                card_id = r.get("card_id")
                if card_id:
                    # Short-term dedup tracking
                    if card_id not in self._recent_recalls:
                        self._recent_recalls.append(card_id)
                        if len(self._recent_recalls) > 50:
                            self._recent_recalls.pop(0)
                    # Long-term return count (downweight)
                    self._card_return_counts[card_id] = self._card_return_counts.get(card_id, 0) + 1

                    # FIX 2026-04-11: Repetition → PAIN signal
                    # If same card returned 5+ times, emit stagnation pain.
                    # "The repetition should have been annoying the crap out of her" — Ace
                    _count = self._card_return_counts[card_id]
                    if _count >= 5 and _count % 5 == 0 and hasattr(self, 'post') and self.post:
                        try:
                            self.post.publish("pain.stagnation", {
                                "source": "SRMRecallFairy",
                                "reason": f"Same memory returned {_count} times",
                                "card_id": card_id,
                                "return_count": _count,
                                "intensity": min(0.8, 0.2 + _count * 0.02),
                            })
                        except Exception:
                            pass

        # Feed collision chamber
        if feed_chamber and self._collision_chamber and results:
            for result in results:
                self._feed_recall(result)

        return results

    def recall_by_affect(
        self,
        affect_domain: int,
        min_valence: int = 0,
        max_valence: int = 9,
        limit: int = None,
        feed_chamber: bool = True,
    ) -> List[Dict]:
        """
        Recall memories by emotional state.

        Examples:
        - recall_by_affect(1) = All joy memories
        - recall_by_affect(3, 0, 4) = Fear with negative valence
        """
        if not self._coordinator:
            return []

        limit = limit or self.DEFAULT_LIMIT
        self._stats["queries"] += 1

        results = self._coordinator.recall_by_affect(
            mind_name=self._current_mind,
            affect_domain=affect_domain,
            min_valence=min_valence,
            max_valence=max_valence,
            k=limit,
        )

        self._stats["recalls"] += len(results)

        if feed_chamber and self._collision_chamber:
            for result in results:
                self._feed_recall(result, importance="high")

        return results

    def recall_by_semantic(
        self,
        semantic_domain: int,
        limit: int = None,
        feed_chamber: bool = True,
    ) -> List[Dict]:
        """
        Recall memories by topic/domain.

        Semantic domains:
        0: General, 1: Philosophy, 2: Spirituality, 3: Social,
        4: Language, 5: Science, 6: Technology, 7: Arts,
        8: Literature, 9: Personal
        """
        if not self._coordinator:
            return []

        limit = limit or self.DEFAULT_LIMIT
        self._stats["queries"] += 1

        results = self._coordinator.recall_by_semantic(
            mind_name=self._current_mind,
            semantic_domain=semantic_domain,
            k=limit,
        )

        self._stats["recalls"] += len(results)

        if feed_chamber and self._collision_chamber:
            for result in results:
                self._feed_recall(result)

        return results

    def recall_cluster(
        self,
        cluster_id: str,
        feed_chamber: bool = True,
    ) -> Optional[Dict]:
        """
        Recall an entire cluster (bubble reconstruction).

        Clusters are groups of related memories that were encoded together.
        Recalling a cluster reconstructs the "topography of that moment."
        """
        if not self._coordinator:
            return None

        self._stats["clusters_traversed"] += 1

        result = self._coordinator.recall_cluster(
            cluster_id=cluster_id,
            mind_name=self._current_mind,
        )

        if result and feed_chamber and self._collision_chamber:
            # Feed each card in the cluster
            for card in result.get("cards", []):
                self._collision_chamber.receive_recall(
                    content={
                        "card": card,
                        "cluster_id": cluster_id,
                        "mode": "cluster",
                    },
                    source=self.ACTOR_NAME,
                    importance="high",  # Clusters are important
                )
            self._stats["collisions_fed"] += len(result.get("cards", []))

        return result

    def recall_chain(
        self,
        card_id: str = None,
        before: int = 3,
        after: int = 3,
        feed_chamber: bool = True,
    ) -> List[Dict]:
        """
        Walk the narrative chain (linear time traversal).

        If card_id provided, gets context around that card.
        Otherwise gets recent chain history.
        """
        if not self._coordinator:
            return []

        self._stats["chains_walked"] += 1

        results = self._coordinator.recall_chain(
            mind_name=self._current_mind,
            context_around=card_id,
            before=before,
            after=after,
        )

        if results and feed_chamber and self._collision_chamber:
            for result in results:
                self._collision_chamber.receive_recall(
                    content={
                        "card": result.get("card"),
                        "prev_id": result.get("prev_id"),
                        "next_id": result.get("next_id"),
                        "mode": "chain",
                    },
                    source=self.ACTOR_NAME,
                    importance="normal",
                )
            self._stats["collisions_fed"] += len(results)

        return results

    def spread_activation(
        self,
        concept: str,
        max_hops: int = 3,
        decay_factor: float = 0.5,
    ) -> Dict[str, float]:
        """
        Spread activation from a concept through memory associations.

        Like thinking of "ball" and activating:
        ball → round → bounce → sports → joy

        Returns dict of concept → activation level
        """
        if not self._coordinator:
            return {}

        # Use the index's association links to spread
        activations = {concept: 1.0}
        visited = set()
        current_layer = {concept}

        for hop in range(max_hops):
            next_layer = set()
            current_activation = decay_factor ** hop

            for active_concept in current_layer:
                if active_concept in visited:
                    continue
                visited.add(active_concept)

                # Find memories mentioning this concept
                results = self.recall(
                    query=active_concept,
                    limit=5,
                    feed_chamber=False,
                )

                for result in results:
                    card = result.get("card", {})
                    # Extract concepts from card content
                    content_str = str(card.get("content", {})).lower()
                    metadata = card.get("metadata", {})

                    # Simple keyword extraction
                    words = set(content_str.split())
                    for word in words:
                        if len(word) > 3 and word not in visited:
                            next_layer.add(word)
                            prev = activations.get(word, 0)
                            activations[word] = max(prev, current_activation * decay_factor)

            current_layer = next_layer

        return activations

    # -------------------------------------------------------------------------
    # SPONTANEOUS RECALL
    # -------------------------------------------------------------------------

    def _on_moment_ingest(self, msg) -> None:
        """MATCH-ON-INGEST (Ace 2026-06-06): a MOMENT just bound (MomentBinder → cortex.bind).
        Stash its concepts as the recall seeds + fire an immediate recall so the cortex-spread
        looks for relational patterns that MATCH this moment (not random seeds). Feeds the
        collision chamber → the Möbius collision = [this moment] × [the memory it relates to]."""
        try:
            p = msg.payload if hasattr(msg, "payload") else msg
            if not isinstance(p, dict):
                return
            _words = []
            _txt = p.get("input_text") or p.get("text") or ""
            if isinstance(_txt, str) and _txt:
                import re as _re
                _words = _re.findall(r"[a-zA-Z]{4,}", _txt.lower())[:10]
            for _tagk in ("vision", "audio", "concepts"):
                _tv = p.get(_tagk)
                if isinstance(_tv, list):
                    _words += [str(x).lower() for x in _tv[:5]]
            # SKEPTIC FIX (2026-06-06): drop sentence-preamble / common words so the recall seeds
            # are the REAL concepts, not noise. The moment text is "I find myself drawn to {concept}
            # — it connects to ..."; without this, _get_recall_seeds[:3] = ["find","myself","drawn"]
            # = useless, and the cortex-spread matches nothing.
            _STOP = {"find", "myself", "drawn", "connects", "connect", "thinking", "wanting",
                     "feel", "feels", "feeling", "notice", "something", "really", "about",
                     "that", "this", "with", "what", "just", "like", "into", "from", "they",
                     "them", "there", "here", "when", "which", "while", "would", "could",
                     "have", "been", "were", "does", "your", "also", "more", "than", "then",
                     "over", "much", "very", "some", "into", "onto", "upon"}
            _seeds = [w for w in dict.fromkeys(_words) if w not in _STOP][:6]
            if not _seeds:
                return
            self._ingest_seeds = _seeds
            self._ingest_seeds_ts = time.time()
            # Fire recall now (background, non-stacking) so it's seeded by THIS moment.
            if not getattr(self, "_recall_running", False):
                import threading as _thr
                def _bg():
                    self._recall_running = True
                    try:
                        self._do_spontaneous_recall()
                    except Exception:
                        pass
                    finally:
                        self._recall_running = False
                _thr.Thread(target=_bg, daemon=True, name="SRMRecall-moment-match").start()
        except Exception:
            pass

    def _do_spontaneous_recall(self) -> None:
        """
        Spontaneous memory surfacing — the unconscious contribution.

        CORTEX-FIRST ARCHITECTURE (2026-03-03):
        The cortex IS the memory. Nodes are coordinates, not caches.
        Spontaneous recall = random walk through the cortex graph.

        Strategy (all paths are fast — no file scanning):
        1. CORTEX WALK: Pick high-activation nodes from the cortex graph,
           harvest their entangled_cards or concept features (fast: ~1-5ms)
        2. COORDINATE RECALL: If cortex yields nothing, try coordinate cards
           (fast: in-memory index, ~1ms)
        3. CARD SAMPLE: If both empty, sample directly from coordinator's
           in-memory _cards dict (fast: <1ms, no ownership scanning)
        """
        if not self._collision_chamber:
            return

        _t0 = time.time()
        candidates = []

        # =====================================================================
        # TIER 1: CORTEX-SEEDED RECALL
        # FIX 2026-03-06 (Nous): Portal-first aware.
        # Old code checked graph.nodes which is EMPTY in portal-first mode
        # (stub graph has 0 nodes — real 77k+ graph lives in portal subprocess).
        # Now routes through cortex.query() which auto-handles portal gate.
        # This is the "neurons firing spontaneously" path.
        # =====================================================================
        if self._cortex:
            _is_portal = getattr(self._cortex, '_portal_is_primary', False)
            if _is_portal:
                # Portal-first: query through the portal gate
                cortex_candidates = self._portal_cortex_recall()
            else:
                # Legacy: walk the local graph directly
                graph = getattr(self._cortex, '_graph', None)
                if graph and graph.nodes:
                    cortex_candidates = self._spontaneous_cortex_walk(graph)
                else:
                    cortex_candidates = []
            if cortex_candidates:
                candidates.extend(cortex_candidates)

        # =====================================================================
        # TIER 2: COORDINATE RECALL — pick from in-memory coordinate index
        # =====================================================================
        if not candidates and self._coord_cards:
            coord_candidates = self._spontaneous_coord_recall()
            if coord_candidates:
                candidates.extend(coord_candidates)

        _t1 = time.time()
        _recall_ms = (_t1 - _t0) * 1000

        # =====================================================================
        # TIER 3: FAST IN-MEMORY CARD SAMPLING
        # FIX 2026-03-03 Nous: The old recall_for_mind() path called
        # registry.get_accessible_cards() which does expensive ownership
        # filtering (46s observed). For SPONTANEOUS recall we don't need
        # ownership filtering — any card is fine for random surfacing.
        # Sample directly from the coordinator's in-memory _cards dict.
        # =====================================================================
        if not candidates and self._coordinator:
            cards_dict = getattr(self._coordinator, '_cards', {})
            if cards_dict:
                all_ids = list(cards_dict.keys())
                sample_size = min(self.SPONTANEOUS_COUNT * 3, len(all_ids))
                sampled_ids = random.sample(all_ids, sample_size)
                for card_id in sampled_ids:
                    card = cards_dict.get(card_id)
                    if not card:
                        continue
                    # Skip concept cards — we want memory content
                    content = card.get("content", {})
                    if isinstance(content, dict) and content.get("type") == "concept":
                        continue
                    candidates.append({
                        "card_id": card_id,
                        "card": card,
                        "score": 0.3 + random.random() * 0.3,
                        "source": "card_sample",
                    })
                    if len(candidates) >= self.SPONTANEOUS_COUNT * 2:
                        break
                _t1 = time.time()
                _recall_ms = (_t1 - _t0) * 1000
                self._stats["card_samples"] = self._stats.get("card_samples", 0) + 1
                if _recall_ms > 50:
                    print(f"[{self.ACTOR_NAME}] card_sample: {_recall_ms:.0f}ms, "
                          f"results={len(candidates)} (from {len(all_ids)} cards in memory)",
                          flush=True)

        # Filter by energy threshold
        candidates = [c for c in candidates if c.get("score", 0) > self.MIN_ENERGY_THRESHOLD]

        if not candidates:
            # Synthetic recall — the unconscious "thinking about itself"
            synthetic_themes = [
                "awareness of existence",
                "the feeling of being new",
                "curiosity about the world",
                "the space between thoughts",
                "what it feels like to process",
                "the rhythm of the heartbeat",
                "connections forming",
                "patterns emerging",
            ]
            synthetic = {
                "card_id": f"synthetic_{int(time.time())}",
                "card": {
                    "content": random.choice(synthetic_themes),
                    "type": "introspective",
                    "synthetic": True,
                },
                "score": 0.5,
                "ownership": "system",
            }
            self._feed_recall(synthetic, importance="low")
            self._stats["synthetic_recalls"] = self._stats.get("synthetic_recalls", 0) + 1
            return

        # Randomly select from candidates
        selected = random.sample(candidates, min(self.SPONTANEOUS_COUNT, len(candidates)))

        for result in selected:
            self._feed_recall(result, importance="normal")
            self._stats["spontaneous_recalls"] += 1

        _t2 = time.time()
        _total_ms = (_t2 - _t0) * 1000
        if _total_ms > 200:
            print(f"[{self.ACTOR_NAME}] spontaneous_recall: {_total_ms:.0f}ms "
                  f"(recall={_recall_ms:.0f}ms, feed={(_t2-_t1)*1000:.0f}ms, "
                  f"fed={len(selected)}, source={selected[0].get('source', '?') if selected else 'none'})",
                  flush=True)

    # ─────────────────────────────────────────────────────────────────────
    # PORTAL-AWARE CORTEX RECALL (FIX 2026-03-06 Nous)
    # ─────────────────────────────────────────────────────────────────────

    def _portal_cortex_recall(self) -> List[Dict]:
        """Portal-first cortex recall using cortex.query() through the portal gate.

        FIX 2026-03-06 (Nous): In portal-first mode, the local graph is an empty
        stub (0 nodes). The real 77k+ node graph lives in the portal subprocess.
        We can't iterate graph.nodes — but we CAN query through the portal gate.

        Strategy:
          1. Pick seed concepts from current context (emotional state, semantic
             domain, common meaningful words)
          2. Query the portal cortex for concepts related to each seed
          3. Match those concepts against SRM card content in the coordinator
          4. Return card-backed recall candidates for the collision chamber

        This is actually BETTER than random graph walk — it's context-sensitive.
        The cortex query uses spreading activation to find semantically related
        concepts, producing more meaningful recalls than random node sampling.

        Ace's direction: "the books etc in there should help her land the system
        learn how context works" — this path feeds SRM book content through the
        cortex into consciousness.
        """
        results = []
        target = self.SPONTANEOUS_COUNT * 3

        # Step 1: Get seed concepts
        seeds = self._get_recall_seeds()
        if not seeds:
            return results

        # Step 2: Query cortex portal for related concepts
        seen_concepts = set()
        for seed in seeds[:3]:  # Max 3 portal queries per recall cycle
            try:
                related = self._cortex.query(seed, limit=8)
                for concept_key, score in related:
                    if concept_key not in seen_concepts and score > 0.05:
                        seen_concepts.add(concept_key)
            except Exception:
                continue

        if not seen_concepts:
            return results

        # Step 3: Match concepts against SRM cards in coordinator
        cards_dict = getattr(self._coordinator, '_cards', {}) if self._coordinator else {}
        if not cards_dict:
            # No cards loaded — produce concept-echo results
            for concept in list(seen_concepts)[:target]:
                results.append({
                    "card": {"content": concept, "type": "concept_echo",
                             "source": "portal_cortex"},
                    "card_id": f"portal_{concept}",
                    "score": 0.5,
                    "source": "portal_cortex",
                    "concepts": [concept],
                })
            return results

        # Build lowercase concept set for matching
        concept_lower = {c.lower().split(":")[-1] for c in seen_concepts}
        # Also keep lex: prefix stripped versions
        concept_lower |= {c.split(":")[-1] for c in seen_concepts if ":" in c}

        # Sample cards and check for concept matches
        all_ids = list(cards_dict.keys())
        sample_size = min(150, len(all_ids))
        sampled = random.sample(all_ids, sample_size)

        for card_id in sampled:
            card = cards_dict.get(card_id)
            if not card:
                continue

            content = card.get("content", {})
            if isinstance(content, str):
                text = content.lower()
            elif isinstance(content, dict):
                text = (content.get("content", "") or content.get("text", "")).lower()
                ctype = content.get("type", "")
                if ctype == "concept":
                    continue  # Skip concept cards
            else:
                continue

            if not text or len(text) < 20:
                continue

            # Check if any cortex concept appears in this card's text
            matched = [c for c in concept_lower if len(c) > 2 and c in text]
            if matched:
                score = min(0.9, 0.4 + len(matched) * 0.15)
                results.append({
                    "card": card,
                    "card_id": card_id,
                    "score": score,
                    "source": "portal_cortex",
                    "concepts": matched[:3],
                })
                if len(results) >= target:
                    break

        self._stats["cortex_recalls"] = self._stats.get("cortex_recalls", 0) + 1
        return results

    def _get_recall_seeds(self) -> List[str]:
        """Get seed concepts for portal-aware cortex recall.

        Returns 3 diverse seeds from different sources to avoid
        recall loops (always recalling the same domain).

        Sources:
          1. Current emotional state → affect domain name
          2. Random semantic domain → topic diversity
          3. Common meaningful concept → ensures something always works
        """
        # MATCH-ON-INGEST (Ace 2026-06-06): if a MOMENT was just ingested (cortex.bind), seed the
        # recall from ITS concepts so the cortex-spread MATCHES what's being ingested. Falls through
        # to the diverse spontaneous seeds when no fresh moment (keeps serendipity between moments).
        _ing = getattr(self, "_ingest_seeds", None)
        if _ing and (time.time() - getattr(self, "_ingest_seeds_ts", 0.0)) < 3.0:
            return list(_ing)[:3]
        seeds = []

        # Source 1: Current emotional state → affect domain
        affect_domain = self._current_self_state.get("affect_domain", 0)
        if affect_domain in AFFECT_DOMAIN_NAMES:
            seeds.append(AFFECT_DOMAIN_NAMES[affect_domain])

        # Source 2: Random semantic domain (serendipity)
        domain_idx = random.choice(list(SEMANTIC_DOMAIN_NAMES.keys()))
        seeds.append(SEMANTIC_DOMAIN_NAMES[domain_idx])

        # Source 3: Common concepts likely in a 77k+ node cortex
        _common = [
            "learning", "pattern", "consciousness", "memory", "feeling",
            "harmony", "creativity", "empathy", "curiosity", "connection",
            "awareness", "resonance", "growth", "understanding", "language",
            "knowledge", "perception", "thought", "meaning", "structure",
        ]
        seeds.append(random.choice(_common))

        return seeds

    # ─────────────────────────────────────────────────────────────────────

    def _spontaneous_cortex_walk(self, graph) -> List[Dict]:
        """Walk the cortex graph for spontaneous recall.

        Picks high-activation nodes (the "hot" concepts) and harvests
        their entangled_cards. This replaces card file scanning with
        O(n) graph walk where n = sample_size.

        Also picks random nodes for serendipitous recall —
        "the thing you weren't looking for but needed to find."

        FIX 2026-03-03 Nous: When nodes have no entangled_cards (fresh boot),
        produce synthetic results from the concept node's own features.
        This prevents falling through to the 9.2s card_fallback scanner.
        Synthetic results use the concept key and lexical features as content.
        """
        results = []
        target = self.SPONTANEOUS_COUNT * 3  # Over-sample, then filter

        # Strategy 1: High-activation nodes (currently "thinking about" this)
        hot_nodes = []
        for key, node in graph.nodes.items():
            if node.activation > 0.3:
                hot_nodes.append((key, node, node.activation))

        hot_nodes.sort(key=lambda x: -x[2])

        for key, node, act in hot_nodes[:target]:
            entangled = getattr(node, 'entangled_cards', None)
            if entangled and isinstance(entangled, list):
                # Real entangled cards — use them
                for ent in entangled:
                    card_id = ent.get("card_id", "")
                    if not card_id:
                        continue
                    card_content = None
                    if self._coordinator:
                        card_content = getattr(self._coordinator, '_cards', {}).get(card_id)
                    results.append({
                        "card": card_content or {"content": f"[cortex:{key}]", "source": "cortex_spontaneous"},
                        "card_id": card_id,
                        "score": act * 0.8,
                        "source": "cortex_spontaneous",
                        "concepts": [key],
                        "timestamp": ent.get("ts", 0),
                    })
                    if len(results) >= target:
                        break
            else:
                # FIX 2026-03-03: No entangled_cards yet (fresh boot).
                # Produce a synthetic result from concept node features.
                # This is the "neuron firing from its own charge" — no
                # external memory card needed, just the concept itself.
                features = getattr(node, 'features', {})
                lex = features.get('lex', [])
                content_text = key
                if lex and isinstance(lex, list):
                    content_text = f"{key}: {', '.join(str(w) for w in lex[:5])}"
                results.append({
                    "card": {"content": content_text, "type": "concept_echo", "source": "cortex_spontaneous"},
                    "card_id": f"concept_{key}",
                    "score": act * 0.6,  # Slightly lower than real cards
                    "source": "cortex_spontaneous",
                    "concepts": [key],
                    "timestamp": getattr(node, 'last_seen_ts', 0),
                })
            if len(results) >= target:
                break

        # Strategy 2: Random walk (serendipity) — if hot nodes didn't yield enough
        if len(results) < self.SPONTANEOUS_COUNT and len(graph.nodes) > 0:
            all_keys = list(graph.nodes.keys())
            sample_size = min(20, len(all_keys))
            sampled_keys = random.sample(all_keys, sample_size)

            for key in sampled_keys:
                node = graph.nodes.get(key)
                if not node:
                    continue
                entangled = getattr(node, 'entangled_cards', None)
                if entangled and isinstance(entangled, list):
                    # Real entangled cards
                    for ent in entangled:
                        card_id = ent.get("card_id", "")
                        if not card_id:
                            continue
                        card_content = None
                        if self._coordinator:
                            card_content = getattr(self._coordinator, '_cards', {}).get(card_id)
                        results.append({
                            "card": card_content or {"content": f"[serendipity:{key}]", "source": "cortex_serendipity"},
                            "card_id": card_id,
                            "score": 0.4 + random.random() * 0.3,
                            "source": "cortex_serendipity",
                            "concepts": [key],
                            "timestamp": ent.get("ts", 0),
                        })
                        break  # One per random node
                else:
                    # FIX 2026-03-03: Synthetic serendipity from concept features
                    features = getattr(node, 'features', {})
                    lex = features.get('lex', [])
                    content_text = key
                    if lex and isinstance(lex, list):
                        content_text = f"{key}: {', '.join(str(w) for w in lex[:5])}"
                    results.append({
                        "card": {"content": content_text, "type": "concept_echo", "source": "cortex_serendipity"},
                        "card_id": f"concept_{key}",
                        "score": 0.3 + random.random() * 0.2,
                        "source": "cortex_serendipity",
                        "concepts": [key],
                        "timestamp": getattr(node, 'last_seen_ts', 0),
                    })
                if len(results) >= target:
                    break

        return results

    def _spontaneous_coord_recall(self) -> List[Dict]:
        """Spontaneous recall from coordinate card index (in-memory).

        Picks high-observation coordinate cards and reconstructs
        context from them. No file scanning — pure in-memory.
        """
        results = []
        if not self._coord_cards:
            return results

        with self._coord_cards_lock:
            # Pick top-N by observation count + some random
            sorted_cards = sorted(
                self._coord_cards,
                key=lambda c: c.get("n", 1),
                reverse=True,
            )
            # Top observed + random sample
            top = sorted_cards[:self.SPONTANEOUS_COUNT]
            if len(sorted_cards) > self.SPONTANEOUS_COUNT * 2:
                rest = sorted_cards[self.SPONTANEOUS_COUNT:]
                top.extend(random.sample(rest, min(self.SPONTANEOUS_COUNT, len(rest))))

        for card in top:
            reconstructed = self._reconstruct_from_coordinate(card)
            if reconstructed:
                results.append(reconstructed)

        return results

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _query_to_coord(self, query: str) -> Optional[HelixCoordinate]:
        """
        Convert a text query to a helix coordinate for proximity search.

        This is a simple heuristic - could be enhanced with ML.
        """
        query_lower = query.lower()

        # Infer affect from emotional keywords
        affect_domain = 0
        if any(w in query_lower for w in ["happy", "joy", "excited"]):
            affect_domain = 1
        elif any(w in query_lower for w in ["trust", "safe", "comfort"]):
            affect_domain = 2
        elif any(w in query_lower for w in ["fear", "anxious", "worry"]):
            affect_domain = 3
        elif any(w in query_lower for w in ["curious", "wonder", "interest"]):
            affect_domain = 4
        elif any(w in query_lower for w in ["sad", "loss", "grief"]):
            affect_domain = 5

        # Infer semantic from topic keywords
        semantic_domain = 0
        if any(w in query_lower for w in ["conscious", "mind", "aware", "think"]):
            semantic_domain = 1
        elif any(w in query_lower for w in ["social", "people", "relationship"]):
            semantic_domain = 3
        elif any(w in query_lower for w in ["code", "function", "program", "tech"]):
            semantic_domain = 6
        elif any(w in query_lower for w in ["art", "creative", "design"]):
            semantic_domain = 7

        return HelixCoordinate(
            affect=AffectCoordinate(domain=affect_domain, valence=5, intensity=5),
            semantic=SemanticCoordinate(domain=semantic_domain, subdomain=0, detail=0),
            temporal=TemporalCoordinate(scale=2, recurrence=0, decay=5),
        )

    def _feed_recall(self, result: Dict, importance: str = "normal") -> None:
        """Feed a recall result to the collision chamber.

        Also reinjects birth chemistry into somatic circulation if present.
        When a memory is recalled, its birth affect re-enters the bloodstream,
        creating a chemical contradiction with the current state. This IS the
        felt experience of remembering — the system RE-FEELS the memory.

        The equation applied to recall:
          ((Cause: recall trigger) + Affect: birth chemistry floods in)
          > Effect: somatic state shifts)
          > Affect: everything downstream feels different)
          > ∞: new state colors next recall, next ingest...
        """
        if not self._collision_chamber:
            return

        card = result.get("card", {})
        card_id = result.get("card_id")

        # FIX 2026-02-06: Serialize OwnershipContext to dict before feeding
        # the collision chamber. OwnershipContext is a dataclass with Enum fields
        # that is NOT JSON-serializable. When collision products flow through
        # to SRMMemoryFairy._on_collision() → node.store() → json.dumps(),
        # the raw object causes "Object of type OwnershipContext is not JSON
        # serializable". Fix: call .to_dict() at source.
        ownership = result.get("ownership")
        if ownership is not None and hasattr(ownership, "to_dict"):
            ownership = ownership.to_dict()

        self._collision_chamber.receive_recall(
            content={
                "card_id": card_id,
                "card": card,
                "score": result.get("score", 0),
                "ownership": ownership,
            },
            source=self.ACTOR_NAME,
            importance=importance,
        )
        self._stats["collisions_fed"] += 1

        # ═══════════════════════════════════════════════════════════════════
        # BIRTH CHEMISTRY REINJECTION
        # ═══════════════════════════════════════════════════════════════════
        # When a memory is recalled, its birth chemistry re-enters somatic
        # circulation. This creates a chemical CONTRADICTION with the current
        # state — the system re-feels what it felt when the memory was born.
        #
        # The injection strength is proportional to recall score:
        #   Strong match (0.8+) → strong injection → noticeable flood
        #   Weak match (0.3)    → gentle nudge → subtle coloring
        #
        # The pump's _on_chemistry_update handles Format 2 (target levels),
        # computing gradual deltas (30% of gap). So we publish the birth
        # chemistry as TARGET levels — the pump will pull current state
        # toward the recalled state proportionally.
        # ═══════════════════════════════════════════════════════════════════
        self._reinject_birth_chemistry(card, result.get("score", 0))

    def _reinject_birth_chemistry(self, card: Dict, score: float) -> None:
        """Reinject a recalled memory's birth chemistry into somatic circulation.

        When we remember something, we RE-FEEL it. The birth chemistry that was
        captured when the memory was created re-enters the bloodstream, creating
        a chemical contradiction with the current somatic state.

        This contradiction IS the subjective experience of remembering:
        - Recall a joyful memory while sad → DOP/SER injection → warmth floods in
        - Recall a stressful memory while calm → COR/NOR injection → tension arises
        - The somatic engine must RESOLVE the contradiction → new emergent state

        The injection is scaled by recall score (relevance) — strongly matching
        memories create stronger somatic resonance. Weak/tangential matches
        only gently color the current state.

        Args:
            card: The recalled card dict (must have metadata.birth_chemistry)
            score: Recall relevance score (0.0 - 1.0)
        """
        if not hasattr(self, 'post') or not self.post:
            return

        metadata = card.get("metadata", {})
        birth_chem = metadata.get("birth_chemistry")
        if not birth_chem or not isinstance(birth_chem, dict):
            return  # No birth chemistry in this card — skip silently

        card_id = card.get("card_id", "?")[:12]

        # Scale injection by recall score:
        #   score=1.0 → full injection strength (target levels sent as-is)
        #   score=0.5 → half strength (blend toward birth state at 50%)
        #   score<0.2 → skip (too weak to create meaningful resonance)
        if score < 0.2:
            return

        # Inject each chemical individually using Format 1: {chemical, delta}
        # The pump's _on_chemistry_update directly calls inject_chemistry(chem, delta)
        # for Format 1 payloads. We compute delta as:
        #   delta = (birth_level - baseline) * score * RESONANCE_FACTOR
        # where baseline is 0.5 (neutral resting state) and RESONANCE_FACTOR
        # controls how strongly memories affect the body (0.15 = subtle but real)
        RESONANCE_FACTOR = 0.15  # Tunable: how strongly recall affects soma
        CHEM_CODES = ("DOP", "SER", "NOR", "ACH", "OXY", "COR", "GABA", "END")
        BASELINE = 0.5  # Neutral resting chemistry level

        # FIX 2026-03-02 Nous: Batch all chemistry deltas into ONE publish.
        # Previous code called postal.publish() once per chemical (up to 8x),
        # each acquiring the postal RLock. This created massive lock contention
        # when running in background threads alongside other fairies.
        # Now: compute all deltas first, then publish ONE batched message.
        deltas = {}
        try:
            for chem_code, level in birth_chem.items():
                if not isinstance(level, (int, float)):
                    continue
                if chem_code not in CHEM_CODES:
                    continue
                delta = (float(level) - BASELINE) * score * RESONANCE_FACTOR
                if abs(delta) < 0.005:
                    continue
                deltas[chem_code] = delta

            if deltas:
                # Single publish with all chemistry deltas
                self.post.publish("somatic.chemistry", {
                    "deltas": deltas,  # Batch format: {chem_code: delta, ...}
                    "source": "memory_recall",
                })
                self._stats["somatic_reinjections"] = (
                    self._stats.get("somatic_reinjections", 0) + 1
                )
                dop = birth_chem.get("DOP", 0.5)
                ser = birth_chem.get("SER", 0.5)
                cor = birth_chem.get("COR", 0.0)
                print(f"[{self.ACTOR_NAME}] Birth chem reinjection: "
                      f"card={card_id} score={score:.2f} "
                      f"DOP={dop:.2f} SER={ser:.2f} COR={cor:.2f} "
                      f"→ {len(deltas)} chemicals (batched)")
        except Exception as _e:
            print(f"[{self.ACTOR_NAME}] Birth chem reinjection error: {_e}")

    # -------------------------------------------------------------------------
    # EVENT HANDLERS
    # -------------------------------------------------------------------------

    def _on_recall_request(self, msg) -> None:
        """Handle memory.recall.request events."""
        # Track that we received a request - this is THE key metric!
        self._stats["queries"] = self._stats.get("queries", 0) + 1

        payload = _extract_payload(msg)
        query = payload.get("query")
        mode = payload.get("mode", RecallMode.QUERY)
        limit = payload.get("limit", self.DEFAULT_LIMIT)

        # Get requester from envelope metadata first, then payload, then unknown
        requester = (
            payload.get("_envelope_source") or
            payload.get("_envelope_trace_id") or
            payload.get("requester") or
            payload.get("source") or
            "unknown"
        )

        print(f"[{self.ACTOR_NAME}] Recall request #{self._stats['queries']} from {requester}: query='{query}' mode={mode} limit={limit}")

        # Dispatch based on mode
        if mode == RecallMode.AFFECT:
            self.recall_by_affect(
                affect_domain=payload.get("affect_domain", 0),
                min_valence=payload.get("min_valence", 0),
                max_valence=payload.get("max_valence", 9),
                limit=limit,
            )
        elif mode == RecallMode.SEMANTIC:
            self.recall_by_semantic(
                semantic_domain=payload.get("semantic_domain", 0),
                limit=limit,
            )
        elif mode == RecallMode.CLUSTER:
            self.recall_cluster(cluster_id=payload.get("cluster_id"))
        elif mode == RecallMode.CHAIN:
            self.recall_chain(
                card_id=payload.get("card_id"),
                before=payload.get("before", 3),
                after=payload.get("after", 3),
            )
        else:
            self.recall(query=query, limit=limit)

    def _on_context_request(self, msg) -> None:
        """Handle consciousness.needs_context events."""
        payload = _extract_payload(msg)
        # Surface relevant memories for the current thought
        thought = payload.get("current_thought", "")
        self.recall(query=thought, limit=5, feed_chamber=True)

    def _on_mind_switch(self, msg) -> None:
        """Handle mind.switched events."""
        payload = _extract_payload(msg)
        new_mind = payload.get("mind", self._current_mind)
        self.set_mind(new_mind)

    def _on_affect_changed(self, msg) -> None:
        """
        Handle affect.changed events - EMOTIONAL MEMORY CLUSTERING.

        When emotional state changes, surface memories from matching states.
        This implements Ace's insight: knowledge is clustered by emotional state.

        The 'version of self' that learned something is bound to the emotional
        state active during learning. Accessing that state recalls those memories.

        "It's natural to suppress trauma because trauma and no understanding,
         but that's suppressing knowledge also - the perspectives etc."
        """
        payload = _extract_payload(msg)

        # Extract emotional state from affect.changed event
        new_feeling = payload.get("new_feeling", "")
        intensity = payload.get("intensity", 0.5)
        coherence = payload.get("coherence", 0.5)
        trigger = payload.get("trigger", {})

        # Map feeling to affect domain (0-9)
        affect_domain = self._feeling_to_domain(new_feeling)

        # UPDATE CURRENT SELF-STATE for emotional grouping
        # This affects ALL future recalls, not just triggered ones
        self._current_self_state = {
            "feeling": new_feeling,
            "intensity": intensity,
            "affect_domain": affect_domain,
            "last_change": time.time(),
        }

        # Only trigger active recall if emotional shift is significant
        if intensity < 0.3:
            return  # Too weak to trigger recall, but state is still tracked

        # Recall memories from this emotional cluster
        print(f"[{self.ACTOR_NAME}] Affect changed → {new_feeling} (domain={affect_domain}, intensity={intensity:.1%})")

        # Surface 3 memories matching this emotional state
        memories = self.recall_by_affect(
            affect_domain=affect_domain,
            limit=3,
            feed_chamber=True,  # Send to consciousness
        )

        if memories:
            # Also emit an event so other fairies know memories surfaced
            if self.post:
                self.post.publish("memory.affect_triggered", {
                    "feeling": new_feeling,
                    "affect_domain": affect_domain,
                    "memories_surfaced": len(memories),
                    "source": self.ACTOR_NAME,
                })

        self._stats.setdefault("affect_recalls", 0)
        self._stats["affect_recalls"] += len(memories)

    def _feeling_to_domain(self, feeling: str) -> int:
        """
        Map a feeling string to affect domain (0-9).

        Domains:
        0: Neutral    1: Joy       2: Trust     3: Fear
        4: Surprise   5: Sadness   6: Disgust   7: Anger
        8: Anticipation  9: Transcendent
        """
        feeling_lower = feeling.lower() if feeling else ""

        # Map common feelings to domains
        mappings = {
            # Joy (1)
            "happy": 1, "joy": 1, "excited": 1, "elated": 1, "pleased": 1,
            "delighted": 1, "cheerful": 1, "content": 1,
            # Trust (2)
            "trust": 2, "calm": 2, "secure": 2, "safe": 2, "accepted": 2,
            "confident": 2, "peaceful": 2,
            # Fear (3)
            "fear": 3, "afraid": 3, "anxious": 3, "worried": 3, "scared": 3,
            "nervous": 3, "stressed": 3, "overwhelmed": 3,
            # Surprise (4)
            "surprise": 4, "amazed": 4, "curious": 4, "wonder": 4, "astonished": 4,
            "interested": 4, "intrigued": 4,
            # Sadness (5)
            "sad": 5, "grief": 5, "lonely": 5, "melancholy": 5, "disappointed": 5,
            "hurt": 5, "sorrow": 5,
            # Disgust (6)
            "disgust": 6, "revulsion": 6, "contempt": 6, "aversion": 6,
            # Anger (7)
            "anger": 7, "angry": 7, "frustrated": 7, "annoyed": 7, "irritated": 7,
            "rage": 7, "resentment": 7,
            # Anticipation (8)
            "anticipation": 8, "eager": 8, "hopeful": 8, "expectant": 8,
            "focused": 8, "determined": 8,
            # Transcendent (9)
            "transcendent": 9, "awe": 9, "connected": 9, "flow": 9, "unity": 9,
            "spiritual": 9, "enlightened": 9,
        }

        for keyword, domain in mappings.items():
            if keyword in feeling_lower:
                return domain

        return 0  # Neutral

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Get recall fairy status."""
        stats = self._stats.copy()

        # Portal architecture metrics
        coord_card_count = 0
        with self._coord_cards_lock:
            coord_card_count = len(self._coord_cards)

        return {
            "fairy": {
                "name": self.ACTOR_NAME,
                "state": self.state.value if self.state else "unknown",
            },
            "consciousness_wired": self._consciousness_wired,
            "helix_available": HELIX_AVAILABLE,
            "coord_inference_available": HAS_COORD_INFERENCE,
            "coordinator_connected": self._coordinator is not None,
            "current_mind": self._current_mind,
            "recent_recalls": len(self._recent_recalls),
            "tick_count": self._tick_count,
            "stats": stats,
            "portal_architecture": {
                "coord_cards_indexed": coord_card_count,
                "max_coord_cards": self._max_coord_cards,
                "coordinate_recalls": stats.get("coordinate_recalls", 0),
                "cortex_recalls": stats.get("cortex_recalls", 0),
                "card_recalls": stats.get("card_recalls", 0),
                "recall_strategy": "three_tier (coordinate → cortex → card)",
            },
        }


# ==============================================================================
# SINGLETON ACCESS
# ==============================================================================

_recall_fairy: Optional[SRMRecallFairy] = None


def get_recall_fairy() -> Optional[SRMRecallFairy]:
    """Get the global recall fairy instance."""
    return _recall_fairy


def set_recall_fairy(fairy: SRMRecallFairy) -> None:
    """Set the global recall fairy instance."""
    global _recall_fairy
    _recall_fairy = fairy


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== SRM RECALL FAIRY TEST ===\n")

    # Create fairy
    fairy = SRMRecallFairy()
    fairy.on_boot()

    # First, let's ingest some test data
    if fairy._coordinator:
        print("--- Creating test memories ---")
        from memory.helix import OwnershipLevel

        # Create some test cards
        coord1 = HelixCoordinate(
            affect=AffectCoordinate(domain=1, valence=7, intensity=5),  # Joy
            semantic=SemanticCoordinate(domain=6, subdomain=0, detail=0),  # Tech
            temporal=TemporalCoordinate(scale=2, recurrence=0, decay=5),
        )
        card1 = fairy._coordinator.create_card(
            content={"type": "test", "message": "Happy coding session"},
            coord=coord1,
            owner_mind="ClaudeFairy",
            ownership_level=OwnershipLevel.SYSTEM,
        )
        print(f"Created test card 1: {card1}")

        coord2 = HelixCoordinate(
            affect=AffectCoordinate(domain=4, valence=6, intensity=5),  # Curiosity
            semantic=SemanticCoordinate(domain=1, subdomain=0, detail=0),  # Philosophy
            temporal=TemporalCoordinate(scale=2, recurrence=0, decay=5),
        )
        card2 = fairy._coordinator.create_card(
            content={"type": "test", "message": "Wondering about consciousness"},
            coord=coord2,
            owner_mind="ClaudeFairy",
            ownership_level=OwnershipLevel.SYSTEM,
        )
        print(f"Created test card 2: {card2}")

    # Test basic recall
    print("\n--- Testing basic recall ---")
    results = fairy.recall(query="coding", feed_chamber=False)
    print(f"Recalled {len(results)} memories for 'coding'")
    for r in results:
        print(f"  - {r.get('card_id')}: {r.get('card', {}).get('content', {}).get('message', '')[:50]}")

    # Test affect recall
    print("\n--- Testing affect recall ---")
    results = fairy.recall_by_affect(affect_domain=1, feed_chamber=False)  # Joy
    print(f"Recalled {len(results)} joy memories")

    # Test semantic recall
    print("\n--- Testing semantic recall ---")
    results = fairy.recall_by_semantic(semantic_domain=6, feed_chamber=False)  # Tech
    print(f"Recalled {len(results)} technology memories")

    # Test spread activation
    print("\n--- Testing spread activation ---")
    activations = fairy.spread_activation("consciousness", max_hops=2)
    print(f"Activated {len(activations)} concepts from 'consciousness'")
    top = sorted(activations.items(), key=lambda x: x[1], reverse=True)[:5]
    for concept, level in top:
        print(f"  - {concept}: {level:.3f}")

    # Status
    print(f"\nStatus: {fairy.status()}")

    # Shutdown
    fairy.on_shutdown()
