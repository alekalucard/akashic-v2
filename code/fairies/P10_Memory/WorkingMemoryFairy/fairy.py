"""
WorkingMemoryFairy - Tracks memory lifecycle with ID tracers

"What lives in the moment defines consciousness"

Bridges consciousness loop (working memory) and storage tiers.

MEMORY LIFECYCLE with ID TRACERS:
  CREATED (id, created_at)
     |
  WORKING (entered_working_at) <- In consciousness loop chambers
     | [collision/thought decay or promotion]
  SHORT-TERM (entered_shortterm_at) <- Recent, not yet consolidated
     | [time-based promotion after N days]
  LONG-TERM (entered_longterm_at) <- Permanent storage
     | [or]
  DECAYED (decayed_at) <- Forgotten

Each memory gets a TracerID that follows it through lifecycle.
"""

from __future__ import annotations

import sys
import json
import time
import uuid
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# V2 fairy template
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

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


# Storage directory
TRACKER_STORAGE = ROOT / "SRM_Intake" / "working_memory"


# =============================================================================
# MEMORY TRACER
# =============================================================================

@dataclass
class MemoryTracer:
    """Lifecycle tracer for a single memory item."""

    tracer_id: str
    content_hash: str  # Hash of content for dedup
    source: str  # Where it came from (scrape, collision, observation, etc.)

    # Lifecycle timestamps
    created_at: float = 0.0
    entered_working_at: Optional[float] = None
    entered_shortterm_at: Optional[float] = None
    entered_longterm_at: Optional[float] = None
    decayed_at: Optional[float] = None

    # Current tier
    current_tier: str = "created"  # created, working, shortterm, longterm, decayed

    # Metadata
    fairy_origin: str = ""
    content_preview: str = ""
    collision_id: Optional[int] = None

    def to_working(self):
        self.entered_working_at = time.time()
        self.current_tier = "working"

    def to_shortterm(self):
        self.entered_shortterm_at = time.time()
        self.current_tier = "shortterm"

    def to_longterm(self):
        self.entered_longterm_at = time.time()
        self.current_tier = "longterm"

    def decay(self):
        self.decayed_at = time.time()
        self.current_tier = "decayed"

    def lifecycle_duration(self) -> Dict[str, float]:
        """Calculate time spent in each tier."""
        now = time.time()
        durations = {}

        if self.entered_working_at and self.created_at:
            durations["to_working"] = self.entered_working_at - self.created_at

        if self.entered_shortterm_at and self.entered_working_at:
            durations["in_working"] = self.entered_shortterm_at - self.entered_working_at
        elif self.entered_working_at and self.current_tier == "working":
            durations["in_working"] = now - self.entered_working_at

        if self.entered_longterm_at and self.entered_shortterm_at:
            durations["in_shortterm"] = self.entered_longterm_at - self.entered_shortterm_at
        elif self.entered_shortterm_at and self.current_tier == "shortterm":
            durations["in_shortterm"] = now - self.entered_shortterm_at

        if self.decayed_at:
            durations["total_lifespan"] = self.decayed_at - self.created_at
        else:
            durations["total_lifespan"] = now - self.created_at

        return durations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tracer_id": self.tracer_id,
            "content_hash": self.content_hash,
            "source": self.source,
            "current_tier": self.current_tier,
            "created_at": self.created_at,
            "entered_working_at": self.entered_working_at,
            "entered_shortterm_at": self.entered_shortterm_at,
            "entered_longterm_at": self.entered_longterm_at,
            "decayed_at": self.decayed_at,
            "fairy_origin": self.fairy_origin,
            "content_preview": self.content_preview,
            "collision_id": self.collision_id,
        }


# =============================================================================
# WORKING MEMORY FAIRY
# =============================================================================

class WorkingMemoryFairy(SpellChainMixin, Fairy):
    """
    Tracks what's actually in working memory and maintains lifecycle tracers.

    WORKING MEMORY = What's actively in the consciousness loop:
    - Collision chamber contents
    - Active recall beam
    - Active ingest beam
    - Recent thoughts
    - In-flight postal messages

    This fairy:
    1. Subscribes to consciousness.collision to track working memory entries
    2. Subscribes to memory.recall/ingest to track beam contents
    3. Maintains tracer IDs for lifecycle tracking
    4. Provides accurate working/shortterm/longterm counts for dashboards
    5. Provides slot-based working memory for direct access
    """

    ACTOR_NAME = "WorkingMemoryFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.working"
    NEEDS_HEARTBEAT = False  # Event-driven: tracks memory lifecycle
    NEEDS_TENSOR = True  # We need consciousness events

    PURPOSE = "Track working memory contents and memory lifecycle with ID tracers"
    MANTRA = "What lives in the moment defines consciousness"

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    # Lifecycle timings
    WORKING_DECAY_SECONDS = 30  # Time before working -> shortterm
    SHORTTERM_PROMOTION_SECONDS = 3600  # Time before shortterm -> longterm (1 hour)

    # Maximum slots (like human working memory capacity ~7 +/- 2)
    MAX_SLOTS = 9

    # FIX 2026-04-04: Hard caps to prevent unbounded growth (water treatment)
    MAX_WORKING_TRACERS = 200
    MAX_SHORTTERM_TRACERS = 1000

    # ==========================================================================
    # TOOL DEFINITIONS
    # ==========================================================================

    TOOLS = [
        ("store_slot", "Store an item in a working memory slot"),
        ("recall_slot", "Recall item from a working memory slot"),
        ("clear_slot", "Clear a working memory slot"),
        ("list_slots", "List all working memory slots and their contents"),
        ("get_capacity", "Get working memory capacity and usage"),
    ]

    def __init__(self, fabric=None, **kwargs):
        super().__init__(fabric, **kwargs)

        # Storage
        self.storage_dir = TRACKER_STORAGE
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Tracers by tier
        self._working_tracers: Dict[str, MemoryTracer] = {}  # Currently in consciousness loop
        self._shortterm_tracers: Dict[str, MemoryTracer] = {}  # Recent, not consolidated
        self._longterm_count: int = 0  # Just count, don't track individual
        self._decayed_count: int = 0

        # Content hash -> tracer_id for dedup
        self._content_index: Dict[str, str] = {}

        # Working memory slots - explicit addressable storage
        # slot_id -> {"content": Any, "metadata": dict, "stored_at": float}
        self._slots: Dict[str, Dict[str, Any]] = {}

        # Stats
        self._stats = {
            "tracers_created": 0,
            "promotions_to_shortterm": 0,
            "promotions_to_longterm": 0,
            "decays": 0,
            "last_update": 0,
            "slot_stores": 0,
            "slot_recalls": 0,
            "slot_clears": 0,
            "working_evictions": 0,  # FIX 2026-04-04: Track cap evictions
            "shortterm_evictions": 0,
        }

        # Lock for thread safety
        self._lock = threading.Lock()

    def get_capabilities(self) -> Set[str]:
        return {
            "memory.lifecycle.track",
            "memory.lifecycle.counts",
            "memory.lifecycle.details",
        }

    def on_boot(self) -> bool:
        """Initialize and subscribe to memory streams."""
        # Subscribe to memory events
        if self.post:
            self.post.subscribe(
                "consciousness.collision",
                self._on_collision,
                "wm_collision_handler",
            )
            self.post.subscribe(
                "memory.recall",
                self._on_memory_recall,
                "wm_recall_handler",
            )
            self.post.subscribe(
                "memory.ingest",
                self._on_memory_ingest,
                "wm_ingest_handler",
            )
            self.post.subscribe(
                "consciousness.thought",
                self._on_thought,
                "wm_thought_handler",
            )

            # ── Phase 4: Working Memory as Active Participant ──
            # Query/pull: Let dual CoT pull what it needs from working memory
            self.post.subscribe(
                "working_memory.query",
                self._on_query,
                "wm_query_handler",
            )
            # Promotion: When reflective thought gets attended to, promote it
            self.post.subscribe(
                "consciousness.reflective",
                self._on_reflective_thought,
                "wm_reflective_handler",
            )

            # FIX 2026-04-04 (Nous): CNS backpressure integration (water treatment)
            self.post.subscribe("consciousness.cns.backpressure", self._on_cns_backpressure, "wm-cns-bp")
            self.post.subscribe("consciousness.cns.throttle", self._on_cns_throttle, "wm-cns-throttle")
            self.post.subscribe("consciousness.cns.relief", self._on_cns_relief, "wm-cns-relief")

        # CNS pressure level for shedding non-essential tracers
        self._cns_pressure_level = "normal"

        # Load persisted state
        self._load_state()

        # Phase 4: Collision feed tracking
        self._recent_working_sources: List[str] = []  # Track sources for co-occurrence
        self._last_collision_feed_ts = 0.0
        self._COLLISION_FEED_COOLDOWN = 15.0  # seconds between collision feeds

        print(f"[{self.ACTOR_NAME}] Booted - tracking memory lifecycle + active participant mode")

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool:
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence - context as living presence")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True

    def on_tick(self, beat: int) -> None:
        """Periodic update - process lifecycle transitions."""
        with self._lock:
            # Decay old working memory to shortterm
            self._process_working_decay()

            # Promote old shortterm to longterm
            self._process_shortterm_promotion()

            self._stats["last_update"] = time.time()

        # Save state periodically
        if beat % 50 == 0:
            self._save_state()

        # FIX 2026-04-04: Report pressure to CNS every 10 ticks (water treatment meter)
        if beat % 10 == 0 and self.post:
            total = len(self._working_tracers) + len(self._shortterm_tracers)
            cap = self.MAX_WORKING_TRACERS + self.MAX_SHORTTERM_TRACERS
            try:
                self.post.publish("cns.component.pressure", {
                    "component": self.ACTOR_NAME,
                    "queue_name": "tracers",
                    "current": total,
                    "capacity": cap,
                    "pressure": total / cap if cap > 0 else 0,
                    "drops": self._stats.get("working_evictions", 0) + self._stats.get("shortterm_evictions", 0),
                    "ts": time.time(),
                })
            except Exception:
                pass

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def on_shutdown(self) -> bool:
        """Save state on shutdown."""
        self._save_state()
        return True

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_collision(self, envelope) -> None:
        """Handle collision event - this IS working memory."""
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        with self._lock:
            self._create_tracer_for_collision(payload)

    def _on_memory_recall(self, envelope) -> None:
        """Handle memory recall - enters working memory."""
        if self._cns_pressure_level == "critical":
            return  # FIX 2026-04-04: Shed under critical pressure
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        with self._lock:
            self._create_tracer_for_recall(payload)

    def _on_memory_ingest(self, envelope) -> None:
        """Handle memory ingest - enters working memory."""
        if self._cns_pressure_level == "critical":
            return  # FIX 2026-04-04: Shed under critical pressure
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        with self._lock:
            self._create_tracer_for_ingest(payload)

    def _on_thought(self, envelope) -> None:
        """Handle thought event."""
        if self._cns_pressure_level in ("critical", "high"):
            return  # FIX 2026-04-04: Shed under high/critical pressure
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        with self._lock:
            self._create_tracer_for_thought(payload)

    # =========================================================================
    # PHASE 4: ACTIVE PARTICIPANT HANDLERS
    # =========================================================================

    def _on_query(self, envelope) -> None:
        """Handle working_memory.query — let dual CoT pull what it needs.

        Query format: {"query": "search text", "reply_topic": "topic.to.respond.on"}
        Returns matching items from all tiers (working, shortterm, slots).
        """
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        if not isinstance(payload, dict):
            return

        query = str(payload.get("query", "")).lower()
        reply_topic = payload.get("reply_topic", "working_memory.query.result")
        max_results = payload.get("max_results", 5)

        if not query:
            return

        results = []
        with self._lock:
            # Search working tracers
            for tracer in self._working_tracers.values():
                preview = (tracer.content_preview or "").lower()
                source = (tracer.source or "").lower()
                if query in preview or query in source:
                    results.append({
                        "tier": "working",
                        "tracer_id": tracer.tracer_id,
                        "preview": tracer.content_preview,
                        "source": tracer.source,
                        "age": time.time() - (tracer.entered_working_at or tracer.created_at),
                    })

            # Search shortterm tracers
            for tracer in self._shortterm_tracers.values():
                preview = (tracer.content_preview or "").lower()
                source = (tracer.source or "").lower()
                if query in preview or query in source:
                    results.append({
                        "tier": "shortterm",
                        "tracer_id": tracer.tracer_id,
                        "preview": tracer.content_preview,
                        "source": tracer.source,
                        "age": time.time() - (tracer.entered_shortterm_at or tracer.created_at),
                    })

            # Search slots
            for slot_id, slot_data in self._slots.items():
                content_str = str(slot_data.get("content", "")).lower()
                if query in content_str or query in slot_id.lower():
                    results.append({
                        "tier": "slot",
                        "slot_id": slot_id,
                        "preview": str(slot_data["content"])[:200],
                        "age": time.time() - slot_data["stored_at"],
                    })

        # Sort by relevance (working > shortterm > slot) and recency
        tier_priority = {"working": 0, "shortterm": 1, "slot": 2}
        results.sort(key=lambda x: (tier_priority.get(x["tier"], 9), x["age"]))
        results = results[:max_results]

        if self.post and results:
            self.post.publish(reply_topic, {
                "query": query,
                "results": results,
                "count": len(results),
                "ts": time.time(),
            })

    def _on_reflective_thought(self, envelope) -> None:
        """Handle consciousness.reflective — track for promotion and collision feeding.

        When reflective thoughts arrive (from drives, cortex whispers, etc.),
        they enter working memory. If they co-occur with existing items,
        feed both to the collision chamber for serendipity sparks.
        """
        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        if not isinstance(payload, dict):
            return

        source = payload.get("source", "unknown")
        content = payload.get("content", payload.get("thought", ""))
        if not content:
            return

        # Create a tracer for this reflective thought entering working memory
        with self._lock:
            content_hash = str(hash(str(content)[:200]) & 0xFFFFFFFF)
            if content_hash not in self._content_index:
                tracer = MemoryTracer(
                    tracer_id=f"refl_{time.time()}_{uuid.uuid4().hex[:6]}",
                    content_hash=content_hash,
                    source=f"reflective:{source}",
                    created_at=time.time(),
                    fairy_origin=source,
                    content_preview=str(content)[:100],
                )
                tracer.to_working()
                self._working_tracers[tracer.tracer_id] = tracer
                self._content_index[content_hash] = tracer.tracer_id
                self._stats["tracers_created"] += 1

            # Track source for co-occurrence detection
            self._recent_working_sources.append(source)
            # Keep only last 10
            if len(self._recent_working_sources) > 10:
                self._recent_working_sources = self._recent_working_sources[-10:]

        # Collision feeding: if we have diverse sources co-occurring, spark collision
        self._maybe_feed_collision()

    def _maybe_feed_collision(self) -> None:
        """Feed co-occurring working memory items to collision chamber.

        When a drive thought + cortex whisper + collision product co-exist
        in working memory, that's a rich collision opportunity.
        Rate limited to prevent flooding.
        """
        now = time.time()
        if now - self._last_collision_feed_ts < self._COLLISION_FEED_COOLDOWN:
            return

        with self._lock:
            # Count distinct source types in working memory
            source_types = set()
            sample_items = []
            for tracer in list(self._working_tracers.values())[-10:]:
                src = tracer.source or ""
                if "drive" in src or "pain" in src:
                    source_types.add("drive")
                elif "cortex" in src or "whisper" in src:
                    source_types.add("cortex")
                elif "collision" in src:
                    source_types.add("collision")
                elif "reflective" in src:
                    source_types.add("reflective")
                elif "thought" in src:
                    source_types.add("thought")
                sample_items.append(tracer)

            # Need at least 2 different source types for a meaningful collision
            if len(source_types) < 2:
                return

            # Pick two items from different sources to feed as collision material
            item_a = None
            item_b = None
            for item in sample_items:
                src = item.source or ""
                if item_a is None:
                    item_a = item
                elif item_b is None and item.source != item_a.source:
                    item_b = item
                    break

            if not item_a or not item_b:
                return

        self._last_collision_feed_ts = now

        # Publish to consciousness streams so collision chamber picks them up
        if self.post:
            self.post.publish("consciousness.thought", {
                "thought": f"Working memory convergence: {item_a.content_preview} meets {item_b.content_preview}",
                "source": "working_memory:collision_feed",
                "confidence": 0.4,
                "thought_type": "working",
                "ts": now,
            })

    # =========================================================================
    # TRACER CREATION
    # =========================================================================

    def _evict_oldest_working(self):
        """FIX 2026-04-04: Evict oldest working tracer when at capacity.
        FIX 2026-04-12: Defensive — handle empty dict + missing keys gracefully.
        """
        try:
            if len(self._working_tracers) >= self.MAX_WORKING_TRACERS:
                oldest_id = next(iter(self._working_tracers), None)
                if oldest_id:
                    evicted = self._working_tracers.pop(oldest_id, None)
                    if evicted:
                        self._content_index.pop(getattr(evicted, 'content_hash', None), None)
                    self._stats["working_evictions"] = self._stats.get("working_evictions", 0) + 1
        except Exception:
            pass  # Eviction is non-critical — don't crash thought processing

    def _evict_oldest_shortterm(self):
        """FIX 2026-04-04: Evict oldest shortterm tracer when at capacity."""
        if len(self._shortterm_tracers) >= self.MAX_SHORTTERM_TRACERS:
            oldest_id = next(iter(self._shortterm_tracers))
            evicted = self._shortterm_tracers.pop(oldest_id)
            self._content_index.pop(getattr(evicted, 'content_hash', None), None)
            self._stats["shortterm_evictions"] += 1

    def _create_tracer_for_collision(self, collision: Dict) -> str:
        """Create a tracer for a collision event."""
        collision_id = collision.get("collision_id", 0)
        content = str(collision)[:200]
        content_hash = str(hash(content) & 0xFFFFFFFF)

        # Check for duplicate
        if content_hash in self._content_index:
            return self._content_index[content_hash]

        tracer = MemoryTracer(
            tracer_id=f"col_{collision_id}_{uuid.uuid4().hex[:6]}",
            content_hash=content_hash,
            source="consciousness_collision",
            created_at=collision.get("ts", time.time()),
            fairy_origin="ConsciousnessLoopFairy",
            content_preview=content[:100],
            collision_id=collision_id,
        )
        tracer.to_working()

        self._evict_oldest_working()  # FIX 2026-04-04: Cap enforcement
        self._working_tracers[tracer.tracer_id] = tracer
        self._content_index[content_hash] = tracer.tracer_id
        self._stats["tracers_created"] += 1

        return tracer.tracer_id

    def _create_tracer_for_recall(self, payload: Dict) -> Optional[str]:
        """Create a tracer for a memory recall."""
        content = str(payload)[:200]
        content_hash = str(hash(content) & 0xFFFFFFFF)

        # Check if already tracked
        if content_hash in self._content_index:
            return self._content_index[content_hash]

        tracer = MemoryTracer(
            tracer_id=f"recall_{time.time()}_{uuid.uuid4().hex[:6]}",
            content_hash=content_hash,
            source="memory_recall",
            created_at=time.time(),
            fairy_origin=payload.get("source", "SRMRecallFairy"),
            content_preview=content[:100],
        )
        tracer.to_working()

        self._evict_oldest_working()  # FIX 2026-04-04: Cap enforcement
        self._working_tracers[tracer.tracer_id] = tracer
        self._content_index[content_hash] = tracer.tracer_id
        self._stats["tracers_created"] += 1

        return tracer.tracer_id

    def _create_tracer_for_ingest(self, payload: Dict) -> Optional[str]:
        """Create a tracer for a memory ingest."""
        content = str(payload)[:200]
        content_hash = str(hash(content) & 0xFFFFFFFF)

        if content_hash in self._content_index:
            return self._content_index[content_hash]

        tracer = MemoryTracer(
            tracer_id=f"ingest_{time.time()}_{uuid.uuid4().hex[:6]}",
            content_hash=content_hash,
            source="memory_ingest",
            created_at=time.time(),
            fairy_origin=payload.get("source", "SRMIngestFairy"),
            content_preview=content[:100],
        )
        tracer.to_working()

        self._evict_oldest_working()  # FIX 2026-04-04: Cap enforcement
        self._working_tracers[tracer.tracer_id] = tracer
        self._content_index[content_hash] = tracer.tracer_id
        self._stats["tracers_created"] += 1

        return tracer.tracer_id

    def _create_tracer_for_thought(self, thought: Dict) -> str:
        """Create a tracer for a thought."""
        ts = thought.get("ts", time.time())
        content = str(thought)[:200]
        content_hash = str(hash(content) & 0xFFFFFFFF)

        if content_hash in self._content_index:
            return self._content_index[content_hash]

        # FIX 2026-04-12 (Nous + Ace): Handle both "thought" and "content" keys.
        # Think engine publishes with "content", ConsciousnessLoop uses "thought".
        _preview = thought.get("thought", "") or thought.get("content", "")
        tracer = MemoryTracer(
            tracer_id=f"thought_{ts}_{uuid.uuid4().hex[:6]}",
            content_hash=content_hash,
            source=thought.get("content_type", "autonomous_thought"),
            created_at=ts,
            fairy_origin=thought.get("source", "ConsciousnessLoopFairy"),
            content_preview=str(_preview)[:100],
        )
        tracer.to_working()

        self._evict_oldest_working()  # FIX 2026-04-04: Cap enforcement
        self._working_tracers[tracer.tracer_id] = tracer
        self._content_index[content_hash] = tracer.tracer_id
        self._stats["tracers_created"] += 1

        return tracer.tracer_id

    # =========================================================================
    # CNS BACKPRESSURE (Water Treatment — FIX 2026-04-04)
    # =========================================================================

    def _on_cns_backpressure(self, message):
        """Critical pressure — only accept collision tracers."""
        self._cns_pressure_level = "critical"

    def _on_cns_throttle(self, message):
        """High pressure — shed thought/recall tracers."""
        self._cns_pressure_level = "high"

    def _on_cns_relief(self, message):
        """Pressure relieved — accept all tracers."""
        self._cns_pressure_level = "normal"

    # =========================================================================
    # LIFECYCLE PROCESSING
    # =========================================================================

    def _process_working_decay(self):
        """Move old working memory to shortterm."""
        now = time.time()

        to_promote = []
        for tracer_id, tracer in self._working_tracers.items():
            if tracer.entered_working_at:
                age = now - tracer.entered_working_at
                if age > self.WORKING_DECAY_SECONDS:
                    to_promote.append(tracer_id)

        for tracer_id in to_promote:
            tracer = self._working_tracers.pop(tracer_id)
            tracer.to_shortterm()
            self._evict_oldest_shortterm()  # FIX 2026-04-04: Cap enforcement
            self._shortterm_tracers[tracer_id] = tracer
            self._stats["promotions_to_shortterm"] += 1

            # Publish for unconscious thought stream
            if self.post:
                self.post.publish("working_memory.promoted", {
                    "tracer_id": tracer_id,
                    "preview": tracer.content_preview[:50] if tracer.content_preview else "",
                    "source": tracer.source,
                    "stage": "shortterm",
                })

    def _process_shortterm_promotion(self):
        """Promote old shortterm to longterm."""
        now = time.time()

        to_promote = []
        for tracer_id, tracer in self._shortterm_tracers.items():
            if tracer.entered_shortterm_at:
                age = now - tracer.entered_shortterm_at
                if age > self.SHORTTERM_PROMOTION_SECONDS:
                    to_promote.append(tracer_id)

        for tracer_id in to_promote:
            tracer = self._shortterm_tracers.pop(tracer_id)
            tracer.to_longterm()
            self._longterm_count += 1
            self._stats["promotions_to_longterm"] += 1

            # Publish for unconscious thought stream
            if self.post:
                self.post.publish("working_memory.consolidated", {
                    "tracer_id": tracer_id,
                    "preview": tracer.content_preview[:50] if tracer.content_preview else "",
                    "source": tracer.source,
                    "stage": "longterm",
                })

            # Clean up content index for old items
            if tracer.content_hash in self._content_index:
                del self._content_index[tracer.content_hash]

    # =========================================================================
    # INTENTS / QUERIES
    # =========================================================================

    def get_counts(self) -> Dict[str, int]:
        """Get current memory counts by tier - for dashboard."""
        with self._lock:
            return {
                "working": len(self._working_tracers),
                "shortterm": len(self._shortterm_tracers),
                "longterm": self._longterm_count,
                "decayed": self._decayed_count,
                "total_tracked": (
                    len(self._working_tracers)
                    + len(self._shortterm_tracers)
                    + self._longterm_count
                ),
            }

    def get_working_memory_details(self) -> List[Dict]:
        """Get details of current working memory contents."""
        with self._lock:
            details = []
            for tracer in self._working_tracers.values():
                details.append({
                    "tracer_id": tracer.tracer_id,
                    "source": tracer.source,
                    "age_seconds": time.time() - (tracer.entered_working_at or tracer.created_at),
                    "preview": tracer.content_preview,
                })
            return sorted(details, key=lambda x: -x["age_seconds"])[:50]

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def _load_state(self):
        """Load persisted state."""
        state_file = self.storage_dir / "tracker_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                self._longterm_count = data.get("longterm_count", 0)
                self._decayed_count = data.get("decayed_count", 0)
                self._stats = data.get("stats", self._stats)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Load state error: {e}")

    def _save_state(self):
        """Save state for persistence."""
        state_file = self.storage_dir / "tracker_state.json"
        try:
            with open(state_file, "w") as f:
                json.dump(
                    {
                        "longterm_count": self._longterm_count,
                        "decayed_count": self._decayed_count,
                        "stats": self._stats,
                        "saved_at": time.time(),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Save state error: {e}")

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Full status for dashboard/monitoring."""
        counts = self.get_counts()
        base = super().status()
        base.update({
            "counts": counts,
            "stats": self._stats.copy(),
            "content_index_size": len(self._content_index),
            "slots_used": len(self._slots),
            "slots_capacity": self.MAX_SLOTS,
        })
        return base

    # =========================================================================
    # TOOL IMPLEMENTATIONS
    # =========================================================================

    def tool_store_slot(
        self,
        slot_id: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store an item in a working memory slot.

        Args:
            slot_id: Unique identifier for the slot (e.g., "task_context", "user_query")
            content: The content to store (can be any serializable type)
            metadata: Optional metadata dict (tags, source, priority, etc.)

        Returns:
            dict with success status and slot info
        """
        with self._lock:
            # Check capacity (only for new slots)
            if slot_id not in self._slots and len(self._slots) >= self.MAX_SLOTS:
                return {
                    "success": False,
                    "error": "capacity_exceeded",
                    "message": f"Working memory at capacity ({self.MAX_SLOTS} slots). Clear a slot first.",
                    "used": len(self._slots),
                    "capacity": self.MAX_SLOTS,
                }

            # Store the slot
            is_update = slot_id in self._slots
            self._slots[slot_id] = {
                "content": content,
                "metadata": metadata or {},
                "stored_at": time.time(),
                "updated_at": time.time() if is_update else None,
            }

            self._stats["slot_stores"] += 1

            # Also create a tracer for this slot store
            self._create_tracer_for_slot_store(slot_id, content)

            return {
                "success": True,
                "slot_id": slot_id,
                "action": "updated" if is_update else "created",
                "stored_at": self._slots[slot_id]["stored_at"],
                "used": len(self._slots),
                "capacity": self.MAX_SLOTS,
            }

    def tool_recall_slot(self, slot_id: str) -> Dict[str, Any]:
        """
        Recall item from a working memory slot.

        Args:
            slot_id: The slot identifier to recall

        Returns:
            dict with content or None if slot empty/not found
        """
        with self._lock:
            self._stats["slot_recalls"] += 1

            if slot_id not in self._slots:
                return {
                    "success": False,
                    "slot_id": slot_id,
                    "content": None,
                    "error": "slot_not_found",
                    "message": f"Slot '{slot_id}' does not exist",
                    "available_slots": list(self._slots.keys()),
                }

            slot_data = self._slots[slot_id]
            age_seconds = time.time() - slot_data["stored_at"]

            return {
                "success": True,
                "slot_id": slot_id,
                "content": slot_data["content"],
                "metadata": slot_data["metadata"],
                "stored_at": slot_data["stored_at"],
                "age_seconds": age_seconds,
            }

    def tool_clear_slot(self, slot_id: str) -> Dict[str, Any]:
        """
        Clear a working memory slot.

        Args:
            slot_id: The slot identifier to clear

        Returns:
            dict confirming the clear operation
        """
        with self._lock:
            self._stats["slot_clears"] += 1

            if slot_id not in self._slots:
                return {
                    "success": False,
                    "slot_id": slot_id,
                    "error": "slot_not_found",
                    "message": f"Slot '{slot_id}' does not exist",
                }

            # Get info before clearing
            slot_data = self._slots.pop(slot_id)
            age_seconds = time.time() - slot_data["stored_at"]

            return {
                "success": True,
                "slot_id": slot_id,
                "cleared": True,
                "was_stored_at": slot_data["stored_at"],
                "age_seconds": age_seconds,
                "used": len(self._slots),
                "capacity": self.MAX_SLOTS,
            }

    def tool_list_slots(self) -> Dict[str, Any]:
        """
        List all working memory slots and their contents.

        Returns:
            dict with slot inventory including previews
        """
        with self._lock:
            now = time.time()
            slots_info = []

            for slot_id, slot_data in self._slots.items():
                content = slot_data["content"]

                # Create a preview of the content
                if isinstance(content, str):
                    preview = content[:100] + ("..." if len(content) > 100 else "")
                elif isinstance(content, dict):
                    preview = f"dict with keys: {list(content.keys())[:5]}"
                elif isinstance(content, list):
                    preview = f"list with {len(content)} items"
                else:
                    preview = str(content)[:100]

                slots_info.append({
                    "slot_id": slot_id,
                    "preview": preview,
                    "content_type": type(content).__name__,
                    "metadata": slot_data["metadata"],
                    "stored_at": slot_data["stored_at"],
                    "age_seconds": now - slot_data["stored_at"],
                })

            # Sort by age (newest first)
            slots_info.sort(key=lambda x: x["stored_at"], reverse=True)

            return {
                "success": True,
                "slots": slots_info,
                "count": len(slots_info),
                "capacity": self.MAX_SLOTS,
                "available": self.MAX_SLOTS - len(slots_info),
            }

    def tool_get_capacity(self) -> Dict[str, Any]:
        """
        Get working memory capacity and usage.

        Returns:
            dict with used/total capacity and utilization percentage
        """
        with self._lock:
            used = len(self._slots)
            capacity = self.MAX_SLOTS
            available = capacity - used
            utilization = (used / capacity * 100) if capacity > 0 else 0

            # Also include tracer counts for full picture
            tracer_counts = {
                "working_tracers": len(self._working_tracers),
                "shortterm_tracers": len(self._shortterm_tracers),
                "longterm_count": self._longterm_count,
            }

            return {
                "success": True,
                "slots": {
                    "used": used,
                    "capacity": capacity,
                    "available": available,
                    "utilization_percent": round(utilization, 1),
                },
                "tracers": tracer_counts,
                "stats": {
                    "total_stores": self._stats.get("slot_stores", 0),
                    "total_recalls": self._stats.get("slot_recalls", 0),
                    "total_clears": self._stats.get("slot_clears", 0),
                },
            }

    def _create_tracer_for_slot_store(self, slot_id: str, content: Any) -> str:
        """Create a tracer for a slot store operation."""
        content_str = str(content)[:200]
        content_hash = str(hash(content_str) & 0xFFFFFFFF)

        # Don't check for duplicate - each slot store is a new event
        tracer = MemoryTracer(
            tracer_id=f"slot_{slot_id}_{uuid.uuid4().hex[:6]}",
            content_hash=content_hash,
            source="working_memory_slot",
            created_at=time.time(),
            fairy_origin="WorkingMemoryFairy",
            content_preview=f"[{slot_id}] {content_str[:80]}",
        )
        tracer.to_working()

        self._evict_oldest_working()  # FIX 2026-04-04: Cap enforcement
        self._working_tracers[tracer.tracer_id] = tracer
        self._content_index[content_hash] = tracer.tracer_id
        self._stats["tracers_created"] += 1

        return tracer.tracer_id


# =============================================================================
# SINGLETON
# =============================================================================

_working_memory_fairy: Optional[WorkingMemoryFairy] = None


def get_working_memory_fairy() -> WorkingMemoryFairy:
    """Get singleton WorkingMemoryFairy instance."""
    global _working_memory_fairy
    if _working_memory_fairy is None:
        _working_memory_fairy = WorkingMemoryFairy()
        _working_memory_fairy.boot()
    return _working_memory_fairy


def set_working_memory_fairy(fairy: WorkingMemoryFairy) -> None:
    """Set the global working memory fairy instance."""
    global _working_memory_fairy
    _working_memory_fairy = fairy
