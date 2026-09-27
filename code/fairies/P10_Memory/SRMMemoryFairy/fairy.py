"""
SRMMemoryFairy - Semantic Relational Memory Gateway

The memory system that bridges consciousness and persistence.

Architecture:
- Each fairy has its own SRM node (contributing to association cortex)
- Recall beam: memories surfaced from past -> collision chamber
- Ingest beam: new content being encoded -> collision chamber
- Memories feed the Mobius strip immediately upon creation
- Association cortex aggregates all fairy nodes for inner monologue

This fairy doesn't just store - it PARTICIPATES in consciousness by
feeding memories into the collision chamber where they become experience.
"""

from __future__ import annotations

import sys
import time
import json
import hashlib
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

# Add paths for v2 imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


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


def _safe_json_default(obj):
    """Safe JSON encoder default for non-serializable objects.

    FIX 2026-02-06: Handles dataclass objects (like OwnershipContext) and Enums
    that leak into memory content from upstream postal messages. Without this,
    json.dumps raises TypeError for these objects.

    Priority:
    1. to_dict() — dataclasses with custom serialization
    2. .value — Enums
    3. str() — last resort
    """
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


if TYPE_CHECKING:
    from consciousness import CollisionChamber, ConsciousnessLoop


# Golden ratio for Fibonacci-style decay
PHI = 1.618

# Storage directory for file persistence
SRM_INTAKE_DIR = ROOT / "SRM_Intake"


# =============================================================================
# OWNERSHIP MODEL - Who can access what memories
# =============================================================================

class OwnershipLevel:
    """
    Memory ownership/access levels.

    - SYSTEM: All fairies can read (infrastructure, shared state)
    - FOUNDATION: Shared human+AI foundation work (Ace + minds collaboration)
    - PERSONAL: Private to one mind (Claude's thoughts stay with Claude)
    - SHARED: Explicitly shared between specific minds
    """
    SYSTEM = "system"
    FOUNDATION = "foundation"
    PERSONAL = "personal"
    SHARED = "shared"


# =============================================================================
# MEMORY RECORD
# =============================================================================

@dataclass
class MemoryRecord:
    """A single memory in the SRM system."""
    id: str
    content: Dict[str, Any]
    source: str  # Which fairy created this
    memory_type: str = "experience"  # experience, learning, reflection, collision
    importance: float = 0.5  # 0-1 scale
    energy: float = 1.0  # Decays over time
    ownership: str = "system"  # system, foundation, personal, shared
    owner_mind: str = ""  # For personal memories, which mind owns it
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    associations: List[str] = field(default_factory=list)  # IDs of related memories
    persisted: bool = False  # Has this been written to disk?

    def decay(self, rate: float = 0.001) -> float:
        """Apply Fibonacci-style energy decay."""
        age = time.time() - self.accessed_at
        ratio = age * rate
        decay_factor = 1.0 / (1.0 + ratio ** PHI)
        self.energy = max(0.1, self.energy * decay_factor)
        return self.energy

    def access(self) -> None:
        """Record an access, boosting energy."""
        self.accessed_at = time.time()
        self.access_count += 1
        # Boost energy on access (memory consolidation)
        self.energy = min(1.0, self.energy + 0.1)

    def relevance_score(self, query_tags: List[str] = None) -> float:
        """Calculate relevance based on recency, energy, and tag match."""
        recency = 1.0 / (1.0 + ((time.time() - self.accessed_at) / 3600) ** PHI)
        tag_match = 0.0
        if query_tags and self.tags:
            overlap = len(set(query_tags) & set(self.tags))
            tag_match = overlap / max(len(query_tags), 1)
        return (self.energy * 0.4 + recency * 0.3 + self.importance * 0.2 + tag_match * 0.1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "type": self.memory_type,
            "importance": self.importance,
            "energy": self.energy,
            "ownership": self.ownership,
            "owner_mind": self.owner_mind,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "tags": self.tags,
            "associations": self.associations,
            "persisted": self.persisted,
        }


# =============================================================================
# FAIRY SRM NODE
# =============================================================================

class FairySRMNode:
    """
    A fairy's personal SRM node - its contribution to the association cortex.

    Each fairy has one of these, storing memories relevant to that fairy's
    domain. The association cortex queries all nodes when the inner monologue
    needs context.
    """

    def __init__(self, fairy_name: str, max_size: int = 1000):
        self.fairy_name = fairy_name
        self.memories: Dict[str, MemoryRecord] = {}
        self.max_size = max_size
        self._lock = threading.Lock()

        # Stats
        self.total_stored = 0
        self.total_recalled = 0
        self.total_decayed = 0

    def store(self, content: Dict[str, Any], **kwargs) -> MemoryRecord:
        """Store a memory in this node."""
        with self._lock:
            # Generate ID from content hash
            # FIX 2026-02-06: Use safe encoder to handle dataclass/Enum objects
            # that may leak into content from upstream (e.g., OwnershipContext
            # from collision products). Without this, json.dumps raises
            # "Object of type OwnershipContext is not JSON serializable".
            content_str = json.dumps(content, sort_keys=True, default=_safe_json_default)
            mem_id = hashlib.md5(content_str.encode()).hexdigest()[:12]

            # Check for duplicate
            if mem_id in self.memories:
                # Update existing - memory consolidation
                existing = self.memories[mem_id]
                existing.access()
                return existing

            # Create new memory with ownership
            memory = MemoryRecord(
                id=mem_id,
                content=content,
                source=self.fairy_name,
                memory_type=kwargs.get("memory_type", "experience"),
                importance=kwargs.get("importance", 0.5),
                ownership=kwargs.get("ownership", OwnershipLevel.SYSTEM),
                owner_mind=kwargs.get("owner_mind", ""),
                tags=kwargs.get("tags", []),
                associations=kwargs.get("associations", []),
            )

            self.memories[mem_id] = memory
            self.total_stored += 1

            # Prune if over capacity
            self._prune_if_needed()

            return memory

    def recall(
        self,
        query: str = None,
        tags: List[str] = None,
        limit: int = 5,
        requester_mind: str = None,
    ) -> List[MemoryRecord]:
        """
        Recall memories matching query/tags.

        Ownership filtering:
        - SYSTEM memories: accessible to all
        - FOUNDATION memories: accessible to all minds
        - PERSONAL memories: only accessible to owner_mind
        - SHARED memories: accessible to all minds (for now)
        """
        with self._lock:
            candidates = list(self.memories.values())

            # Filter by ownership if requester specified
            if requester_mind:
                candidates = [
                    m for m in candidates
                    if (m.ownership == OwnershipLevel.SYSTEM or
                        m.ownership == OwnershipLevel.FOUNDATION or
                        m.ownership == OwnershipLevel.SHARED or
                        (m.ownership == OwnershipLevel.PERSONAL and
                         m.owner_mind == requester_mind))
                ]

            # Text search if query provided
            if query:
                query_lower = query.lower()
                candidates = [
                    m for m in candidates
                    if query_lower in json.dumps(m.content).lower()
                ]

            # Calculate relevance scores
            scored = [(m, m.relevance_score(tags)) for m in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)

            # Mark as accessed
            results = []
            for memory, score in scored[:limit]:
                memory.access()
                self.total_recalled += 1
                results.append(memory)

            return results

    def decay_sweep(self) -> int:
        """Apply decay to all memories, remove dead ones."""
        with self._lock:
            to_remove = []
            for mem_id, memory in self.memories.items():
                memory.decay()
                if memory.energy < 0.05:  # Threshold for forgetting
                    to_remove.append(mem_id)

            for mem_id in to_remove:
                del self.memories[mem_id]
                self.total_decayed += 1

            return len(to_remove)

    def _prune_if_needed(self) -> None:
        """Remove lowest-energy memories if over capacity."""
        if len(self.memories) <= self.max_size:
            return

        # Sort by energy (lowest first)
        sorted_mems = sorted(
            self.memories.items(),
            key=lambda x: x[1].energy
        )

        # Remove bottom 10%
        remove_count = max(1, len(self.memories) - self.max_size)
        for mem_id, _ in sorted_mems[:remove_count]:
            del self.memories[mem_id]
            self.total_decayed += 1

    def status(self) -> Dict[str, Any]:
        return {
            "fairy": self.fairy_name,
            "memory_count": len(self.memories),
            "max_size": self.max_size,
            "total_stored": self.total_stored,
            "total_recalled": self.total_recalled,
            "total_decayed": self.total_decayed,
        }

    # -------------------------------------------------------------------------
    # FILE PERSISTENCE
    # -------------------------------------------------------------------------

    def persist_memory(self, memory: MemoryRecord, storage_dir: Path = None) -> bool:
        """
        Persist a single memory to disk (SRM_Intake).

        File format: {timestamp}_{fairy}_{id}.json
        """
        if memory.persisted:
            return True

        storage_dir = storage_dir or SRM_INTAKE_DIR
        storage_dir.mkdir(parents=True, exist_ok=True)

        try:
            filename = f"{int(memory.created_at)}_{self.fairy_name}_{memory.id}.json"
            filepath = storage_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(memory.to_dict(), f, indent=2)

            memory.persisted = True
            return True
        except Exception as e:
            print(f"[{self.fairy_name}] Persist failed: {e}")
            return False

    def persist_all(self, storage_dir: Path = None) -> int:
        """Persist all unpersisted memories."""
        count = 0
        with self._lock:
            for memory in self.memories.values():
                if not memory.persisted:
                    if self.persist_memory(memory, storage_dir):
                        count += 1
        return count

    def load_from_disk(self, storage_dir: Path = None) -> int:
        """
        Load memories from disk into this node.

        Only loads files matching this fairy's name pattern.
        """
        storage_dir = storage_dir or SRM_INTAKE_DIR
        if not storage_dir.exists():
            return 0

        count = 0
        pattern = f"*_{self.fairy_name}_*.json"

        for filepath in storage_dir.glob(pattern):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Reconstruct memory record
                memory = MemoryRecord(
                    id=data["id"],
                    content=data["content"],
                    source=data["source"],
                    memory_type=data.get("type", "experience"),
                    importance=data.get("importance", 0.5),
                    energy=data.get("energy", 0.5),
                    ownership=data.get("ownership", OwnershipLevel.SYSTEM),
                    owner_mind=data.get("owner_mind", ""),
                    created_at=data.get("created_at", time.time()),
                    accessed_at=data.get("accessed_at", time.time()),
                    access_count=data.get("access_count", 0),
                    tags=data.get("tags", []),
                    associations=data.get("associations", []),
                    persisted=True,
                )

                with self._lock:
                    if memory.id not in self.memories:
                        self.memories[memory.id] = memory
                        count += 1

            except Exception as e:
                print(f"[{self.fairy_name}] Load failed for {filepath}: {e}")

        return count


# =============================================================================
# ASSOCIATION CORTEX
# =============================================================================

class AssociationCortex:
    """
    The aggregator of all fairy SRM nodes.

    When the inner monologue needs context, it queries here rather than
    picking tokens randomly. This is what makes recall meaningful.
    """

    def __init__(self):
        self.nodes: Dict[str, FairySRMNode] = {}
        self._lock = threading.Lock()

    def register_node(self, fairy_name: str, node: FairySRMNode) -> None:
        """Register a fairy's SRM node."""
        with self._lock:
            self.nodes[fairy_name] = node

    def get_or_create_node(self, fairy_name: str) -> FairySRMNode:
        """Get a fairy's node, creating if needed."""
        with self._lock:
            if fairy_name not in self.nodes:
                self.nodes[fairy_name] = FairySRMNode(fairy_name)
            return self.nodes[fairy_name]

    def query(
        self,
        query: str = None,
        tags: List[str] = None,
        limit: int = 10,
        requester_mind: str = None,
    ) -> List[MemoryRecord]:
        """
        Query across ALL fairy nodes - the global recall.

        This is what the inner monologue uses for context-aware generation.
        Ownership filtering respects memory boundaries.
        """
        all_results = []

        with self._lock:
            for node in self.nodes.values():
                results = node.recall(query, tags, limit=limit * 2, requester_mind=requester_mind)
                all_results.extend(results)

        # Sort by relevance across all sources
        all_results.sort(key=lambda m: m.relevance_score(tags), reverse=True)
        return all_results[:limit]

    def spread_activation(
        self,
        concept: str,
        requester_mind: str = None,
        max_hops: int = 3,
        decay_factor: float = 0.5,
    ) -> Dict[str, float]:
        """
        Spread activation from a concept through memory associations.

        Like thinking of "ball" and activating:
        - ball -> round -> bounce -> sports -> joy
        - Each hop decays the activation by decay_factor

        Returns dict of concept -> activation level
        """
        activations = {concept: 1.0}
        visited = set()
        current_layer = {concept}

        for hop in range(max_hops):
            next_layer = set()
            current_activation = 1.0 * (decay_factor ** hop)

            for active_concept in current_layer:
                if active_concept in visited:
                    continue
                visited.add(active_concept)

                # Find memories related to this concept
                related = self.query(
                    query=active_concept,
                    limit=10,
                    requester_mind=requester_mind,
                )

                for memory in related:
                    # Extract concepts from tags and content
                    concepts_found = set(memory.tags)
                    for key in memory.content.keys():
                        concepts_found.add(key)

                    for new_concept in concepts_found:
                        if new_concept not in visited:
                            next_layer.add(new_concept)
                            # Accumulate activation
                            prev = activations.get(new_concept, 0)
                            activations[new_concept] = max(prev, current_activation * decay_factor)

            current_layer = next_layer

        return activations

    def status(self) -> Dict[str, Any]:
        """Get cortex status."""
        with self._lock:
            total_memories = sum(len(n.memories) for n in self.nodes.values())
            return {
                "node_count": len(self.nodes),
                "total_memories": total_memories,
                "nodes": {name: node.status() for name, node in self.nodes.items()},
            }


# =============================================================================
# SRM MEMORY FAIRY
# =============================================================================

class SRMMemoryFairy(Fairy):
    """
    The Memory Gateway Fairy.

    Responsibilities:
    1. Manage per-fairy SRM nodes
    2. Feed memories to collision chamber (recall beam)
    3. Encode new experiences (ingest beam)
    4. Maintain association cortex for inner monologue
    5. Bridge consciousness loop with persistent memory
    """

    ACTOR_NAME = "SRMMemoryFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.srm"
    USE_EXEC_CTX = True  # FIX 2026-05-17 Layer 1: opt in (uses _srm_bg_queue + exec_ctx — Layer 2 audit pending)

    PURPOSE = "Bridge consciousness and persistence"
    MANTRA = "Memory is not storage, it is participation"

    NEEDS_TENSOR = True
    NEEDS_HEARTBEAT = True

    # Memory timing
    RECALL_INTERVAL = 3  # Ticks between spontaneous recalls
    DECAY_INTERVAL = 20  # Ticks between decay sweeps
    CONSOLIDATION_INTERVAL = 50  # Ticks between memory consolidation

    def __init__(self, fabric=None, **kwargs):
        super().__init__(fabric, **kwargs)

        # Association cortex (aggregates all fairy nodes)
        self.cortex = AssociationCortex()

        # My own SRM node (for meta-memories about memory operations)
        self._my_node = self.cortex.get_or_create_node(self.ACTOR_NAME)

        # Consciousness integration
        self._collision_chamber: Optional["CollisionChamber"] = None
        self._consciousness_loop: Optional["ConsciousnessLoop"] = None
        self._consciousness_wired = False

        # Recent activity for collision feeding
        self._recent_recalls: deque = deque(maxlen=20)
        self._recent_ingests: deque = deque(maxlen=20)

        # Timing counters
        self._tick_count = 0

    def on_boot(self) -> bool:
        """Boot the memory fairy."""
        super().on_boot()

        # Subscribe to memory-related topics
        if self.post:
            self.post.subscribe(
                "memory.store",
                self._on_memory_store,
                "srm_store_handler",
            )
            self.post.subscribe(
                "memory.recall",
                self._on_memory_recall,
                "srm_recall_handler",
            )
            # ALSO subscribe to memory.recall.request (new pattern used by tool_bridge)
            self.post.subscribe(
                "memory.recall.request",
                self._on_memory_recall,
                "srm_recall_request_handler",
            )
            self.post.subscribe(
                "consciousness.collision",
                self._on_collision,
                "srm_collision_handler",
            )

        print(f"[{self.ACTOR_NAME}] Booted with association cortex")
        # Heartbeat via FairyBase postal system - Fifth Ring Principle
        return True

    def on_shutdown(self) -> None:
        """Shutdown the memory fairy."""
        # Persist important memories before shutdown
        self._consolidate_memories()
        super().on_shutdown()
        print(f"[{self.ACTOR_NAME}] Shutdown complete")

    def on_tick(self, beat: int) -> None:
        """Called on each consciousness tick.

        FIX 2026-03-02 Nous: All heavy operations moved to background threads.
        Previous behavior ran _spontaneous_recall, _decay_sweep, _consolidate_memories
        synchronously — blocking the consciousness handler pool worker for seconds.
        Now fire-and-forget with skip-if-running guards to prevent stacking.
        """
        import threading as _thr

        # Handle both int and TensorEnvelope (defensive)
        if hasattr(beat, 'payload'):
            beat = beat.payload.get('beat', 0) if isinstance(beat.payload, dict) else 0
        beat = int(beat) if beat else 0
        self._tick_count = beat

        # ── BACKGROUND WORK: recall, decay, consolidation ──
        # FIX 2026-04-10 (Nous + Ace): Replaced 3x bare Thread().start() with
        # a single shared 2-worker queue pool. Old pattern spawned a new Thread
        # every 3/20/50 beats → ~4.2 Thread objects/min. Under Python 3.14t
        # free-threaded GC, finished Thread objects (Condition+RLock+deque cycles)
        # accumulated → 700+ orphans by beat 10000, contributing to the "10k beat
        # RAM spike" Ace observed. New: 2 reusable workers, zero new Thread objects.
        if not hasattr(self, '_srm_bg_queue'):
            import queue as _q
            self._srm_bg_queue = _q.Queue(maxsize=8)
            for _wi in range(2):
                _t = _thr.Thread(
                    target=self._srm_bg_worker_loop,
                    daemon=True,
                    name=f"SRMMemory-bg-{_wi}",
                )
                _t.start()

        # Submit work to the shared pool (non-blocking, skip if full)
        if beat % self.RECALL_INTERVAL == 0:
            try:
                self._srm_bg_queue.put_nowait(("recall", beat))
            except Exception:
                pass

        if beat % self.DECAY_INTERVAL == 0:
            try:
                self._srm_bg_queue.put_nowait(("decay", beat))
            except Exception:
                pass

        if beat % self.CONSOLIDATION_INTERVAL == 0:
            try:
                self._srm_bg_queue.put_nowait(("consolidation", beat))
            except Exception:
                pass

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # -------------------------------------------------------------------------
    # CONSCIOUSNESS WIRING
    # -------------------------------------------------------------------------

    def wire_to_consciousness(
        self,
        loop: "ConsciousnessLoop",
        chamber: "CollisionChamber",
    ) -> bool:
        """
        Wire the memory system to consciousness.

        This enables:
        - Memories feeding the collision chamber
        - Collision products being stored as memories
        - Inner monologue getting context from association cortex
        """
        self._consciousness_loop = loop
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
        print(f"[{self.ACTOR_NAME}] Wired to consciousness (via exec_ctx)")
        return True

    # -------------------------------------------------------------------------
    # MEMORY OPERATIONS
    # -------------------------------------------------------------------------

    def store(
        self,
        fairy_name: str,
        content: Dict[str, Any],
        feed_chamber: bool = True,
        **kwargs
    ) -> MemoryRecord:
        """
        Store a memory for a fairy.

        This is the INGEST operation - new content entering the system.
        It immediately feeds the collision chamber's ingest beam.
        """
        # Get or create the fairy's node
        node = self.cortex.get_or_create_node(fairy_name)

        # Store the memory
        memory = node.store(content, **kwargs)

        # Track for collision feeding
        self._recent_ingests.append(memory)

        # Feed the collision chamber immediately
        if feed_chamber and self._collision_chamber:
            self._collision_chamber.receive_ingest(
                content=memory.to_dict(),
                source=fairy_name,
                importance=kwargs.get("importance", "normal"),
            )

        # Publish event
        if self.post:
            self.post.publish("memory.stored", {
                "id": memory.id,
                "source": fairy_name,
                "type": memory.memory_type,
                "ts": time.time(),
            })

        return memory

    def recall(
        self,
        query: str = None,
        tags: List[str] = None,
        fairy_name: str = None,
        limit: int = 5,
        feed_chamber: bool = True,
        requester_mind: str = None,
    ) -> List[MemoryRecord]:
        """
        Recall memories.

        This is the RECALL operation - memories surfacing from the past.
        Results feed the collision chamber's recall beam.

        Ownership filtering:
        - If requester_mind is set, respects memory ownership boundaries
        - Personal memories only returned to their owner
        """
        if fairy_name:
            # Recall from specific fairy's node
            node = self.cortex.get_or_create_node(fairy_name)
            results = node.recall(query, tags, limit, requester_mind=requester_mind)
        else:
            # Query across all nodes (association cortex)
            results = self.cortex.query(query, tags, limit, requester_mind=requester_mind)

        # Track for collision feeding
        for memory in results:
            self._recent_recalls.append(memory)

            # Feed the collision chamber
            if feed_chamber and self._collision_chamber:
                self._collision_chamber.receive_recall(
                    content=memory.to_dict(),
                    source=memory.source,
                    importance="high" if memory.importance > 0.7 else "normal",
                )

        return results

    def spread_for_oracle(
        self,
        concept: str,
        requester_mind: str = None,
        max_hops: int = 3,
        decay_factor: float = 0.5,
    ) -> Dict[str, float]:
        """
        Spread activation from a concept for probability oracle branching.

        Example: spread_for_oracle("ball") returns:
        {
            "ball": 1.0,
            "round": 0.5,
            "bounce": 0.45,
            "sports": 0.3,
            "joy": 0.25,
            ...
        }

        Working memory can use these activations to weight
        probability branches in reasoning.
        """
        return self.cortex.spread_activation(
            concept, requester_mind, max_hops, decay_factor
        )

    def get_context_for_monologue(
        self,
        current_thought: str = None,
        tags: List[str] = None,
        limit: int = 5,
        requester_mind: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Get relevant context for the inner monologue.

        This is what makes token selection contextual rather than random.
        The association cortex provides relevant memories based on
        current thought content and tags.
        """
        results = self.cortex.query(current_thought, tags, limit, requester_mind=requester_mind)
        return [m.to_dict() for m in results]

    # -------------------------------------------------------------------------
    # EVENT HANDLERS
    # -------------------------------------------------------------------------

    def _on_memory_store(self, msg) -> None:
        """Handle memory.store events."""
        payload = _extract_payload(msg)
        fairy_name = payload.get("source", "unknown")
        content = payload.get("content", {})
        self.store(fairy_name, content, **payload)

    def _on_memory_recall(self, msg) -> None:
        """Handle memory.recall events."""
        payload = _extract_payload(msg)
        query = payload.get("query")
        tags = payload.get("tags", [])
        fairy_name = payload.get("source")
        self.recall(query, tags, fairy_name)

    def _on_collision(self, msg) -> None:
        """
        Handle consciousness.collision events.

        Collision products get stored as special memories - this is how
        consciousness creates new memories from the intersection of
        recall (past) and ingest (present).
        """
        payload = _extract_payload(msg)
        # Extract collision products
        products = payload.get("products", {})

        # Store the collision itself as a memory
        collision_memory = {
            "type": "collision",
            "collision_id": payload.get("collision_id"),
            "energy": payload.get("energy", 0.5),
            "resonance": payload.get("resonance", 0.5),
            "recall_source": payload.get("recall", {}).get("source", "unknown"),
            "ingest_source": payload.get("ingest", {}).get("source", "unknown"),
            "products": products,
        }

        # High-energy collisions become important memories
        importance = 0.5 + (payload.get("energy", 0) * 0.3) + (payload.get("resonance", 0) * 0.2)

        self.store(
            self.ACTOR_NAME,
            collision_memory,
            memory_type="collision",
            importance=min(1.0, importance),
            tags=["collision", "consciousness"],
            feed_chamber=False,  # Don't re-feed, it came from there
        )

    # -------------------------------------------------------------------------
    # BACKGROUND WORKER POOL (FIX 2026-04-10 Nous + Ace)
    # -------------------------------------------------------------------------

    def _srm_bg_worker_loop(self):
        """Reusable background worker for recall/decay/consolidation.

        Replaces 3x bare Thread().start() per tick cycle. 2 workers
        drain the shared queue. No new Thread objects created per beat.
        """
        while True:
            try:
                task_type, _beat = self._srm_bg_queue.get(timeout=5.0)
            except Exception:
                continue

            try:
                if task_type == "recall":
                    self._spontaneous_recall()
                elif task_type == "decay":
                    self._decay_sweep()
                elif task_type == "consolidation":
                    self._consolidate_memories()
            except Exception as _e:
                try:
                    print(f"[{self.ACTOR_NAME}] bg-worker {task_type} error: {_e}",
                          flush=True)
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # INTERNAL PROCESSES
    # -------------------------------------------------------------------------

    def _spontaneous_recall(self) -> None:
        """
        Spontaneous memory surfacing - the unconscious contribution.

        Even without explicit queries, memories bubble up based on
        recent activity and association strength.
        """
        if not self._collision_chamber:
            return

        # Get a sampling of high-energy memories
        memories = self.cortex.query(limit=3)

        for memory in memories:
            # Only feed high-energy memories spontaneously
            if memory.energy > 0.5:
                self._collision_chamber.receive_recall(
                    content=memory.to_dict(),
                    source=memory.source,
                    importance="normal",
                )

    def _decay_sweep(self) -> None:
        """Apply decay to all memory nodes."""
        total_decayed = 0
        for node in self.cortex.nodes.values():
            decayed = node.decay_sweep()
            total_decayed += decayed

        if total_decayed > 0:
            print(f"[{self.ACTOR_NAME}] Decayed {total_decayed} faded memories")

    def _consolidate_memories(self) -> None:
        """
        Memory consolidation - strengthening important memories.

        This is like sleep-based memory consolidation in biological systems.
        """
        # Consolidate collision memories (most important)
        collision_memories = [
            m for m in self._my_node.memories.values()
            if m.memory_type == "collision" and m.energy > 0.6
        ]

        for memory in collision_memories:
            # Boost energy of high-resonance collisions
            if memory.content.get("resonance", 0) > 0.7:
                memory.energy = min(1.0, memory.energy + 0.1)
                memory.importance = min(1.0, memory.importance + 0.05)

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Get memory system status."""
        state_obj = getattr(self, 'state', getattr(self, '_state', None))
        state_value = getattr(state_obj, 'value', None) if state_obj else "unknown"
        return {
            "fairy": {
                "name": self.ACTOR_NAME,
                "state": state_value,
            },
            "consciousness_wired": self._consciousness_wired,
            "cortex": self.cortex.status(),
            "recent_recalls": len(self._recent_recalls),
            "recent_ingests": len(self._recent_ingests),
            "tick_count": self._tick_count,
        }


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_memory_fairy: Optional[SRMMemoryFairy] = None


def get_memory_fairy() -> Optional[SRMMemoryFairy]:
    """Get the global memory fairy instance."""
    return _memory_fairy


def set_memory_fairy(fairy: SRMMemoryFairy) -> None:
    """Set the global memory fairy instance."""
    global _memory_fairy
    _memory_fairy = fairy
