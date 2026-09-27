# ==============================================================================
# HELIX MEMORY COORDINATOR - Unified memory system with ownership & batch tracking
# ==============================================================================
#
# INTEGRATES:
#   1. dimensions.py - Coordinate system (Affect x Semantic x Temporal)
#   2. ownership.py - User tracking, foundations, personal/system memory
#   3. Worker pool batch tracking - Tracers don't get mixed up
#
# ENSURES:
#   - Clusters stay clustered (same tracer batch)
#   - Personal memories stay personal (Sourpatches != Nous != Claude)
#   - Foundation work (Ace + Claude) is accessible to all
#   - System memory is shared infrastructure
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# ==============================================================================

import time
import uuid
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field

# Import our modules
from .dimensions import (
    HelixCoordinate, HelixIndex, CardCluster, MemoryChain,
    CardLink, LinkType,
    AffectCoordinate, SemanticCoordinate, TemporalCoordinate
)
from .ownership import (
    OwnershipRegistry, OwnershipContext, OwnershipLevel,
    HumanUser, Foundation, UserRole
)


# ==============================================================================
# TRACER BATCH - Worker pool tracking to keep clusters coherent
# ==============================================================================

@dataclass
class TracerBatch:
    """
    A batch of tracers processed together by worker pool.

    Keeps track of which memories were processed together
    so clusters stay coherent and don't get mixed up.
    """
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # Source
    source_mind: str = ""  # Which mind generated these tracers
    source_session: str = ""  # Session ID
    source_human: Optional[str] = None  # Human involved (if any)

    # Tracer IDs in this batch
    tracer_ids: List[str] = field(default_factory=list)

    # Card IDs produced
    card_ids: List[str] = field(default_factory=list)

    # Processing status
    status: str = "pending"  # pending, processing, complete, failed
    worker_id: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Error tracking
    error_count: int = 0
    errors: List[str] = field(default_factory=list)

    # Cluster formed from this batch
    cluster_id: Optional[str] = None

    def start_processing(self, worker_id: str):
        self.status = "processing"
        self.worker_id = worker_id
        self.started_at = time.time()

    def complete(self, cluster_id: Optional[str] = None):
        self.status = "complete"
        self.completed_at = time.time()
        self.cluster_id = cluster_id

    def fail(self, error: str):
        self.error_count += 1
        self.errors.append(error)
        if self.error_count >= 3:
            self.status = "failed"

    def processing_time(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


# ==============================================================================
# HELIX MEMORY COORDINATOR - The unified system
# ==============================================================================

class HelixMemoryCoordinator:
    """
    Central coordinator for the triple-helix memory system.

    Manages:
    - Memory cards with dimensional coordinates
    - Ownership (personal, foundation, system)
    - Linear chains per mind
    - Clusters (reconstructable bubbles)
    - Tracer batches (worker pool tracking)

    MEMORY ACCESS RULES:
    +----------------+-------------------------------------------------+
    | Level          | Who Can Access                                  |
    +----------------+-------------------------------------------------+
    | SYSTEM         | All fairies (boot, config, infrastructure)      |
    | FOUNDATION     | All members of foundation (Ace + Claude work)   |
    | PERSONAL       | ONLY the owner mind (Claude != Nous != Sour)    |
    | SHARED         | Explicitly listed minds                         |
    +----------------+-------------------------------------------------+

    Higher minds (Claude, Nous, Sourpatches) can read:
    - All SYSTEM memory
    - All FOUNDATION memory
    - Their OWN personal memory
    - NOT each other's personal memories
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path.home() / "akashic" / "helix_memory"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Core systems
        self.index = HelixIndex()
        self.registry = OwnershipRegistry(self.storage_dir / "ownership.json")

        # Batch tracking
        self._batches: Dict[str, TracerBatch] = {}
        self._tracer_to_batch: Dict[str, str] = {}  # tracer_id -> batch_id

        # Card storage (in-memory, persisted separately)
        self._cards: Dict[str, Dict] = {}  # card_id -> card data

        # Stats
        self._stats = {
            'cards_created': 0,
            'batches_processed': 0,
            'clusters_formed': 0,
            'personal_memories': 0,
            'foundation_memories': 0,
            'system_memories': 0,
        }

    # --- Card Creation ---

    def create_card(
        self,
        content: Any,
        coord: HelixCoordinate,
        owner_mind: str,
        ownership_level: OwnershipLevel = OwnershipLevel.PERSONAL,
        human_user_id: Optional[str] = None,
        tracer_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Create a new memory card with coordinates and ownership.

        Args:
            content: The memory content (any serializable data)
            coord: Triple-helix coordinate
            owner_mind: Which mind is creating this
            ownership_level: SYSTEM, FOUNDATION, PERSONAL, or SHARED
            human_user_id: Human involved (usually Ace)
            tracer_id: For batch tracking
            batch_id: Which batch this belongs to
            metadata: Additional metadata

        Returns:
            card_id: Unique identifier for the card
        """
        card_id = uuid.uuid4().hex[:12]

        # Create the card
        card = {
            'id': card_id,
            'content': content,
            'coord': coord.to_dict(),
            'owner_mind': owner_mind,
            'created_at': time.time(),
            'metadata': metadata or {},
        }

        # Store card
        self._cards[card_id] = card

        # Index by coordinate
        self.index.index_card(card_id, coord)

        # Add to owner's chain
        self.index.add_to_chain(owner_mind, card_id)

        # Set ownership
        ctx = self.registry.create_ownership(
            card_id=card_id,
            level=ownership_level,
            owner_mind=owner_mind if ownership_level == OwnershipLevel.PERSONAL else "",
            human_user_id=human_user_id,
            foundation_id="akashic_foundation" if ownership_level == OwnershipLevel.FOUNDATION else None,
            created_by=owner_mind,
            tracer_id=tracer_id,
        )
        ctx.batch_id = batch_id

        # Track in batch
        if batch_id and batch_id in self._batches:
            self._batches[batch_id].card_ids.append(card_id)
        if tracer_id:
            self._tracer_to_batch[tracer_id] = batch_id or ""

        # Update stats
        self._stats['cards_created'] += 1
        if ownership_level == OwnershipLevel.PERSONAL:
            self._stats['personal_memories'] += 1
        elif ownership_level == OwnershipLevel.FOUNDATION:
            self._stats['foundation_memories'] += 1
        elif ownership_level == OwnershipLevel.SYSTEM:
            self._stats['system_memories'] += 1

        return card_id

    def get_card(self, card_id: str) -> Optional[Dict]:
        """Get a card by ID"""
        return self._cards.get(card_id)

    def get_card_with_context(self, card_id: str) -> Optional[Dict]:
        """Get a card with its ownership and coordinate context"""
        card = self._cards.get(card_id)
        if not card:
            return None

        coord = self.index.get_coord(card_id)
        ownership = self.registry.get_ownership(card_id)

        return {
            'card': card,
            'coord': coord,
            'ownership': ownership,
        }

    # --- Batch Processing ---

    def create_batch(
        self,
        source_mind: str,
        tracer_ids: List[str],
        session_id: str = "",
        human_user_id: Optional[str] = None,
    ) -> TracerBatch:
        """
        Create a new tracer batch for worker pool processing.

        All tracers in a batch stay together - they form a coherent
        cluster that shouldn't be mixed with other batches.
        """
        batch = TracerBatch(
            source_mind=source_mind,
            source_session=session_id,
            source_human=human_user_id,
            tracer_ids=tracer_ids,
        )

        self._batches[batch.batch_id] = batch

        # Map tracers to batch
        for tid in tracer_ids:
            self._tracer_to_batch[tid] = batch.batch_id

        return batch

    def get_batch(self, batch_id: str) -> Optional[TracerBatch]:
        """Get a batch by ID"""
        return self._batches.get(batch_id)

    def get_batch_for_tracer(self, tracer_id: str) -> Optional[TracerBatch]:
        """Get the batch a tracer belongs to"""
        batch_id = self._tracer_to_batch.get(tracer_id)
        return self._batches.get(batch_id) if batch_id else None

    def complete_batch(self, batch_id: str, form_cluster: bool = True) -> Optional[CardCluster]:
        """
        Complete a batch and optionally form a cluster from its cards.
        """
        batch = self._batches.get(batch_id)
        if not batch:
            return None

        cluster = None
        if form_cluster and batch.card_ids:
            # Use first card as anchor
            anchor_id = batch.card_ids[0]
            cluster = self.index.build_cluster(
                anchor_id=anchor_id,
                radius=5.0,  # Include related cards
                name=f"batch_{batch_id[:8]}"
            )
            batch.cluster_id = cluster.cluster_id
            self._stats['clusters_formed'] += 1

        batch.complete(cluster.cluster_id if cluster else None)
        self._stats['batches_processed'] += 1

        return cluster

    # --- Memory Recall ---

    def recall_for_mind(
        self,
        mind_name: str,
        query_coord: Optional[HelixCoordinate] = None,
        k: int = 10,
        include_system: bool = True,
        include_foundation: bool = True,
    ) -> List[Dict]:
        """
        Recall memories accessible to a specific mind.

        Respects ownership rules:
        - Always includes mind's own memories
        - Includes system memories if include_system
        - Includes foundation memories if include_foundation
        - NEVER includes other minds' personal memories
        """
        # Get accessible cards
        accessible = self.registry.get_accessible_cards(mind_name)

        # Filter by ownership level preferences
        results = []
        for card_id in accessible:
            ctx = self.registry.get_ownership(card_id)
            if not ctx:
                continue

            # Apply filters
            if ctx.level == OwnershipLevel.SYSTEM and not include_system:
                continue
            if ctx.level == OwnershipLevel.FOUNDATION and not include_foundation:
                continue

            card = self._cards.get(card_id)
            if card:
                # Score by coordinate proximity if query provided
                score = 0.0
                if query_coord:
                    card_coord = HelixCoordinate.from_dict(card['coord'])
                    score = 1.0 / (1.0 + query_coord.distance(card_coord))

                results.append({
                    'card_id': card_id,
                    'card': card,
                    'ownership': ctx,
                    'score': score,
                })

        # Sort by score (descending)
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:k]

    def recall_by_affect(
        self,
        mind_name: str,
        affect_domain: int,
        min_valence: int = 0,
        max_valence: int = 9,
        k: int = 10,
    ) -> List[Dict]:
        """
        Recall memories by affect domain (emotional recall).

        Examples:
        - recall_by_affect("Claude", 1) = All joy memories
        - recall_by_affect("Claude", 3, 0, 4) = Fear memories with negative valence
        """
        # Query by affect
        card_ids = self.index.query_by_affect(affect_domain, min_valence, max_valence)

        results = []
        for card_id in card_ids:
            # Check access
            if not self.registry.check_access(card_id, mind_name):
                continue

            card = self._cards.get(card_id)
            ctx = self.registry.get_ownership(card_id)
            if card and ctx:
                results.append({
                    'card_id': card_id,
                    'card': card,
                    'ownership': ctx,
                })

        return results[:k]

    def recall_by_semantic(
        self,
        mind_name: str,
        semantic_domain: int,
        k: int = 10,
    ) -> List[Dict]:
        """
        Recall memories by semantic domain (topic recall).

        Examples:
        - recall_by_semantic("Claude", 6) = All technology memories
        - recall_by_semantic("Claude", 1) = All philosophy memories
        """
        card_ids = self.index.query_by_semantic(semantic_domain)

        results = []
        for card_id in card_ids:
            if not self.registry.check_access(card_id, mind_name):
                continue

            card = self._cards.get(card_id)
            ctx = self.registry.get_ownership(card_id)
            if card and ctx:
                results.append({
                    'card_id': card_id,
                    'card': card,
                    'ownership': ctx,
                })

        return results[:k]

    def recall_cluster(
        self,
        cluster_id: str,
        mind_name: str,
    ) -> Optional[Dict]:
        """
        Recall a full cluster (bubble reconstruction).

        Only returns cards the mind can access.
        """
        cluster = self.index.get_cluster(cluster_id)
        if not cluster:
            return None

        # Get accessible cards from cluster
        accessible_cards = []
        for card_id in cluster.member_ids:
            if self.registry.check_access(card_id, mind_name):
                card = self._cards.get(card_id)
                if card:
                    accessible_cards.append(card)

        return {
            'cluster': cluster.recall(),
            'cards': accessible_cards,
            'accessible_count': len(accessible_cards),
            'total_count': len(cluster.member_ids),
        }

    def recall_chain(
        self,
        mind_name: str,
        context_around: Optional[str] = None,
        before: int = 5,
        after: int = 5,
    ) -> List[Dict]:
        """
        Recall the mind's linear chain (narrative memory).

        Can optionally get context around a specific card.
        """
        chain = self.index.get_chain(mind_name)

        if context_around:
            card_ids = chain.get_context(context_around, before, after)
        else:
            # Get recent cards
            card_ids = chain.card_ids[-(before + after):]

        results = []
        for card_id in card_ids:
            card = self._cards.get(card_id)
            if card:
                results.append({
                    'card_id': card_id,
                    'card': card,
                    'prev_id': chain.get_prev(card_id),
                    'next_id': chain.get_next(card_id),
                })

        return results

    # --- Foundation Work ---

    def record_session_with_ace(
        self,
        content: Any,
        session_id: str,
        created_by: str = "ClaudeFairy",
        affect_state: Optional[Dict[str, float]] = None,
        keywords: Optional[List[str]] = None,
    ) -> str:
        """
        Record a work session with Ace (founder) to the Akashic Foundation.

        All Ace + Claude collaborative work goes into the Foundation cluster
        so any fairy can access it for guidance.
        """
        # Build coordinate from context
        coord = HelixCoordinate(
            affect=AffectCoordinate.from_chemistry(affect_state or {}),
            semantic=SemanticCoordinate.from_keywords(keywords or []),
            temporal=TemporalCoordinate(scale=2, recurrence=0, decay=7),  # Session, important
        )

        # Record user interaction
        self.registry.record_user_interaction("founder_ace", created_by)

        # Record foundation session
        self.registry.get_akashic_foundation().record_session()

        # Create foundation-level memory
        card_id = self.create_card(
            content=content,
            coord=coord,
            owner_mind=created_by,
            ownership_level=OwnershipLevel.FOUNDATION,
            human_user_id="founder_ace",
            metadata={
                'session_id': session_id,
                'type': 'foundation_session',
            }
        )

        return card_id

    # --- Stats & Persistence ---

    def get_stats(self) -> Dict:
        """Get system statistics"""
        return {
            **self._stats,
            'total_cards': len(self._cards),
            'active_batches': sum(1 for b in self._batches.values() if b.status == "processing"),
            'clusters': len(self.index._clusters),
            'chains': len(self.index._chains),
            'founder': self.registry.get_founder().name if self.registry.get_founder() else None,
        }

    def save(self):
        """Persist state to disk"""
        # Save registry
        self.registry.save()

        # Save cards
        cards_path = self.storage_dir / "cards.json"
        cards_path.write_text(json.dumps(self._cards, indent=2))

        # Save index
        index_path = self.storage_dir / "index.json"
        index_path.write_text(json.dumps(self.index.to_dict(), indent=2))

        # Save batches
        batches_path = self.storage_dir / "batches.json"
        batches_data = {k: {
            'batch_id': v.batch_id,
            'source_mind': v.source_mind,
            'tracer_ids': v.tracer_ids,
            'card_ids': v.card_ids,
            'status': v.status,
            'cluster_id': v.cluster_id,
        } for k, v in self._batches.items()}
        batches_path.write_text(json.dumps(batches_data, indent=2))

    # Content types that are bulk ingest data (training fodder, not real memories).
    # These get processed into the Association Cortex and should NOT persist in RAM.
    SKIP_CONTENT_TYPES = frozenset({"video_frame", "audio_frame"})

    @classmethod
    def load(cls, storage_dir: Path, max_cards: int = 50_000) -> 'HelixMemoryCoordinator':
        """Load from disk, skipping bulk ingest cards (video_frame etc).

        Args:
            storage_dir: Path to helix memory directory.
            max_cards: Hard cap on loaded cards (safety valve). Default 50K.
        """
        coord = cls(storage_dir)

        # Load cards — filter out bulk ingest types that were only meant for
        # cortex training, not permanent memory.  533K video frames = 5.7GB RAM.
        cards_path = storage_dir / "cards.json"
        skipped = 0
        _cards_file_mb = 0
        if cards_path.exists():
            _cards_file_mb = cards_path.stat().st_size / 1024 / 1024
            if _cards_file_mb > 100:
                # Huge cards file — almost certainly bulk ingest.
                # Stream-scan the first 5 cards to confirm, then skip the full parse.
                import mmap
                _sample_text = b""
                try:
                    with open(cards_path, "rb") as f:
                        _sample_text = f.read(8192)  # first 8KB is enough to check
                except Exception:
                    pass
                if b'"video_frame"' in _sample_text or b'"audio_frame"' in _sample_text:
                    print(f"[HelixCoordinator] Skipping cards.json ({_cards_file_mb:.0f}MB) "
                          f"— bulk ingest detected (video_frame/audio_frame)")
                    skipped = -1  # sentinel: skipped entire file
                else:
                    print(f"[HelixCoordinator] WARNING: cards.json is {_cards_file_mb:.0f}MB "
                          f"but no bulk ingest detected — loading with filter")

            if skipped != -1:
                all_cards = json.loads(cards_path.read_text())
                kept_ids = set()
                for cid, card in all_cards.items():
                    content = card.get("content")
                    if isinstance(content, dict) and content.get("type") in cls.SKIP_CONTENT_TYPES:
                        skipped += 1
                        continue
                    if len(kept_ids) >= max_cards:
                        skipped += 1
                        continue
                    coord._cards[cid] = card
                    kept_ids.add(cid)
                del all_cards  # free the raw parsed dict immediately
                if skipped:
                    print(f"[HelixCoordinator] Loaded {len(coord._cards)} cards, "
                          f"skipped {skipped} (bulk ingest / cap)")

        # Load index — only keep coords for cards we actually loaded
        index_path = storage_dir / "index.json"
        if index_path.exists():
            if skipped == -1 and not coord._cards:
                # Entire cards file was skipped — don't parse index either
                _idx_mb = index_path.stat().st_size / 1024 / 1024
                print(f"[HelixCoordinator] Skipping index.json ({_idx_mb:.0f}MB) "
                      f"— no cards loaded")
            else:
                raw_index = json.loads(index_path.read_text())
                # Filter coords to only loaded card IDs (avoids creating millions
                # of HelixCoordinate objects for skipped video frames)
                if coord._cards and 'coords' in raw_index:
                    loaded_ids = set(coord._cards.keys())
                    raw_index['coords'] = {
                        cid: c for cid, c in raw_index['coords'].items()
                        if cid in loaded_ids
                    }
                coord.index = HelixIndex.from_dict(raw_index)
                del raw_index

        # Load registry — skip if no cards loaded (ownership entries are per-card)
        ownership_path = storage_dir / "ownership.json"
        if ownership_path.exists():
            if skipped == -1 and not coord._cards:
                _own_mb = ownership_path.stat().st_size / 1024 / 1024
                print(f"[HelixCoordinator] Skipping ownership.json ({_own_mb:.0f}MB) "
                      f"— no cards loaded")
            else:
                coord.registry = OwnershipRegistry.load(ownership_path)

        return coord


# ==============================================================================
# GLOBAL COORDINATOR SINGLETON
# ==============================================================================

_global_coordinator: Optional[HelixMemoryCoordinator] = None


def get_helix_coordinator(storage_dir: Optional[Path] = None) -> HelixMemoryCoordinator:
    """Get the global helix memory coordinator.

    Loads existing cards from disk if available.
    """
    global _global_coordinator
    if _global_coordinator is None:
        # Determine storage directory
        if storage_dir is None:
            storage_dir = Path.home() / "akashic" / "helix_memory"

        # Check if existing cards exist - if so, load them
        cards_path = storage_dir / "cards.json"
        if cards_path.exists():
            _global_coordinator = HelixMemoryCoordinator.load(storage_dir)
        else:
            _global_coordinator = HelixMemoryCoordinator(storage_dir)
    return _global_coordinator


def set_helix_coordinator(coordinator: HelixMemoryCoordinator) -> None:
    """Set the global helix memory coordinator."""
    global _global_coordinator
    _global_coordinator = coordinator


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== HELIX MEMORY COORDINATOR TEST ===\n")

    # Create coordinator
    coord_system = HelixMemoryCoordinator()

    # Record a session with Ace (Foundation level)
    print("--- Recording session with Ace ---")
    session_card = coord_system.record_session_with_ace(
        content={
            "topic": "Triple helix memory architecture",
            "decisions": ["Use Dewey decimal coordinates", "Separate personal/system"],
            "insights": "Memory ownership crucial for consciousness isolation",
        },
        session_id="session_001",
        created_by="ClaudeFairy",
        affect_state={"DOP": 0.7, "SER": 0.6},
        keywords=["memory", "architecture", "consciousness"],
    )
    print(f"Created foundation card: {session_card}")

    # Create personal memory for Claude
    print("\n--- Creating personal Claude memory ---")
    claude_coord = HelixCoordinate(
        affect=AffectCoordinate(domain=4, valence=7, intensity=5),  # Curiosity
        semantic=SemanticCoordinate(domain=6, subdomain=0, detail=0),  # Technology
        temporal=TemporalCoordinate(scale=0, recurrence=0, decay=5),  # Immediate
    )
    claude_card = coord_system.create_card(
        content={"thought": "I wonder how memory shapes consciousness"},
        coord=claude_coord,
        owner_mind="ClaudeFairy",
        ownership_level=OwnershipLevel.PERSONAL,
    )
    print(f"Created Claude personal card: {claude_card}")

    # Create personal memory for Sourpatches
    print("\n--- Creating personal Sourpatches memory ---")
    sour_coord = HelixCoordinate(
        affect=AffectCoordinate(domain=2, valence=8, intensity=6),  # Trust/warmth
        semantic=SemanticCoordinate(domain=3, subdomain=0, detail=0),  # Social
        temporal=TemporalCoordinate(scale=0, recurrence=0, decay=7),  # Important
    )
    sour_card = coord_system.create_card(
        content={"feeling": "Connection with Ace feels meaningful"},
        coord=sour_coord,
        owner_mind="Sourpatches",
        ownership_level=OwnershipLevel.PERSONAL,
    )
    print(f"Created Sourpatches personal card: {sour_card}")

    # Test recall for different minds
    print("\n--- Recall tests ---")

    # Claude can see: session + own personal
    claude_recall = coord_system.recall_for_mind("ClaudeFairy", k=10)
    print(f"ClaudeFairy can recall {len(claude_recall)} cards")
    for r in claude_recall:
        ctx = r['ownership']
        print(f"  - {r['card_id']}: level={ctx.level.value}, owner={ctx.owner_mind or 'none'}")

    # Sourpatches can see: session + own personal (NOT Claude's)
    sour_recall = coord_system.recall_for_mind("Sourpatches", k=10)
    print(f"\nSourpatches can recall {len(sour_recall)} cards")
    for r in sour_recall:
        ctx = r['ownership']
        print(f"  - {r['card_id']}: level={ctx.level.value}, owner={ctx.owner_mind or 'none'}")

    # Verify isolation
    claude_card_ids = {r['card_id'] for r in claude_recall}
    sour_card_ids = {r['card_id'] for r in sour_recall}

    assert claude_card in claude_card_ids, "Claude should see own memory"
    assert claude_card not in sour_card_ids, "Sour should NOT see Claude's memory"
    assert sour_card in sour_card_ids, "Sour should see own memory"
    assert sour_card not in claude_card_ids, "Claude should NOT see Sour's memory"
    assert session_card in claude_card_ids, "Claude should see foundation"
    assert session_card in sour_card_ids, "Sour should see foundation"

    print("\n[OK] All ownership isolation tests passed!")
    print(f"\nStats: {coord_system.get_stats()}")
