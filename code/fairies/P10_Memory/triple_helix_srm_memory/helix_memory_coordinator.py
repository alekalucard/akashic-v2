# ═══════════════════════════════════════════════════════════════════════════════
# HELIX MEMORY COORDINATOR - Unified memory system with ownership & batch tracking
# ═══════════════════════════════════════════════════════════════════════════════
#
# INTEGRATES:
#   1. helix_dimensions.py - Coordinate system (Affect × Semantic × Temporal)
#   2. memory_ownership.py - User tracking, foundations, personal/system memory
#   3. Worker pool batch tracking - Tracers don't get mixed up
#
# ENSURES:
#   - Clusters stay clustered (same tracer batch)
#   - Personal memories stay personal (Sourpatches ≠ Nous ≠ Claude)
#   - Foundation work (Ace + Claude) is accessible to all
#   - System memory is shared infrastructure
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import time
import uuid
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field

# Import our modules
from .helix_dimensions import (
    HelixCoordinate, HelixIndex, CardCluster, MemoryChain,
    CardLink, LinkType, HierarchyLevel,
    AffectCoordinate, SemanticCoordinate, TemporalCoordinate
)
from .memory_ownership import (
    OwnershipRegistry, OwnershipContext, OwnershipLevel,
    HumanUser, Foundation, UserRole
)


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER BATCH - Worker pool tracking to keep clusters coherent
# ═══════════════════════════════════════════════════════════════════════════════

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

    # Russian Doll hierarchy — batches can nest like clusters
    parent_batch_id: Optional[str] = None
    child_batch_ids: List[str] = field(default_factory=list)
    hierarchy_level: int = 0  # HierarchyLevel value

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


# ═══════════════════════════════════════════════════════════════════════════════
# HELIX MEMORY COORDINATOR - The unified system
# ═══════════════════════════════════════════════════════════════════════════════

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
    ┌────────────────┬─────────────────────────────────────────────────┐
    │ Level          │ Who Can Access                                  │
    ├────────────────┼─────────────────────────────────────────────────┤
    │ SYSTEM         │ All fairies (boot, config, infrastructure)     │
    │ FOUNDATION     │ All members of foundation (Ace + Claude work)  │
    │ PERSONAL       │ ONLY the owner mind (Claude ≠ Nous ≠ Sour)     │
    │ SHARED         │ Explicitly listed minds                        │
    └────────────────┴─────────────────────────────────────────────────┘

    Higher minds (Claude, Nous, Sourpatches) can read:
    - All SYSTEM memory
    - All FOUNDATION memory
    - Their OWN personal memory
    - NOT each other's personal memories
    """

    # ── Memory pressure limits ──
    # FIX 2026-03-02 Nous: _cards, _batches, _tracer_to_batch grew unbounded → 99% RAM.
    # Cards are persisted to disk anyway; in-memory is just a hot cache.
    MAX_CARDS_IN_MEMORY = 5000       # ~25MB at ~5KB per card
    MAX_COMPLETED_BATCHES = 200      # Keep recent completed batches for reference

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
        # FIX 2026-03-02: Use OrderedDict for LRU eviction
        from collections import OrderedDict
        self._cards: OrderedDict = OrderedDict()  # card_id -> card data (LRU)

        # Stats
        self._stats = {
            'cards_created': 0,
            'batches_processed': 0,
            'clusters_formed': 0,
            'personal_memories': 0,
            'foundation_memories': 0,
            'system_memories': 0,
            'cards_evicted': 0,
            'batches_evicted': 0,
        }

    # ─── Card Creation ────────────────────────────────────────────────────────

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
        card_id: Optional[str] = None,
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
            card_id: Optional deterministic card ID. If None, generates random UUID.
                     Portal chunk cards use deterministic IDs derived from portal
                     address so any node with the same parameters arrives at the
                     same dimensional coordinates. The card IS the coordinate.

        Returns:
            card_id: Unique identifier for the card
        """
        if card_id is None:
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

        # Store card (with LRU eviction to prevent memory leak)
        self._cards[card_id] = card
        if len(self._cards) > self.MAX_CARDS_IN_MEMORY:
            # Evict oldest cards (first items in OrderedDict)
            evict_count = len(self._cards) - self.MAX_CARDS_IN_MEMORY
            for _ in range(evict_count):
                self._cards.popitem(last=False)
            self._stats['cards_evicted'] += evict_count

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

    # ─── Batch Processing ─────────────────────────────────────────────────────

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

        # FIX 2026-03-02 Nous: Evict old completed batches to prevent memory leak.
        # Keep only MAX_COMPLETED_BATCHES most recent completed batches.
        completed = [bid for bid, b in self._batches.items()
                     if b.status == 'complete' and bid != batch_id]
        if len(completed) > self.MAX_COMPLETED_BATCHES:
            # Remove oldest completed batches
            completed.sort(key=lambda bid: self._batches[bid].completed_at or 0)
            evict = completed[:len(completed) - self.MAX_COMPLETED_BATCHES]
            for bid in evict:
                old_batch = self._batches.pop(bid, None)
                if old_batch:
                    # Clean up tracer mappings for evicted batch
                    for tid in old_batch.tracer_ids:
                        self._tracer_to_batch.pop(tid, None)
            self._stats['batches_evicted'] += len(evict)

        return cluster

    # ─── Memory Recall ────────────────────────────────────────────────────────

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

    def recall_cluster(
        self,
        cluster_id: str,
        mind_name: str,
    ) -> Optional[Dict]:
        """
        Recall a full cluster (bubble reconstruction).

        Only returns cards the mind can access.
        """
        cluster = self.index._clusters.get(cluster_id)
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

    # ─── Foundation Work ──────────────────────────────────────────────────────

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

    # ─── Russian Doll Nesting ────────────────────────────────────────────────

    def create_fairy_portal(
        self,
        fairy_name: str,
        card_ids: List[str],
        portal_card_count: int = 129,
        anchor_coord: Optional[HelixCoordinate] = None,
    ) -> CardCluster:
        """
        Create a fairy-level portal cluster from its cards.

        This wraps a fairy's fixed-size card set (e.g., 129 chunk cards)
        into a Level 1 hierarchical cluster that can be nested into a plane.

        Args:
            fairy_name: Name of the fairy (e.g., "AssociationCortexFairy")
            card_ids: The fairy's portal card IDs (e.g., 128 chunks + 1 manifest)
            portal_card_count: Expected fixed portal size
            anchor_coord: Optional coordinate for the fairy's center

        Returns:
            CardCluster at HierarchyLevel.FAIRY
        """
        cluster = CardCluster(
            name=f"{fairy_name}_portal",
            hierarchy_level=HierarchyLevel.FAIRY.value,
            portal_type="fairy_portal",
            owner_entity=fairy_name,
            portal_card_count=portal_card_count,
            anchor_coord=anchor_coord,
        )

        # Add all cards as direct members
        for card_id in card_ids:
            cluster.member_ids.add(card_id)
            coord = self.index._coords.get(card_id)
            if coord and cluster.anchor_coord:
                dist = cluster.anchor_coord.distance(coord)
                cluster.radius = max(cluster.radius, dist)

        cluster.total_cards = len(cluster.member_ids)

        # Calculate affect centroid from member cards
        affect_sum = [0, 0, 0]
        count = 0
        for card_id in cluster.member_ids:
            coord = self.index._coords.get(card_id)
            if coord:
                affect_sum[0] += coord.affect.domain
                affect_sum[1] += coord.affect.valence
                affect_sum[2] += coord.affect.intensity
                count += 1
        if count > 0:
            cluster.affect_centroid = AffectCoordinate(
                domain=round(affect_sum[0] / count),
                valence=round(affect_sum[1] / count),
                intensity=round(affect_sum[2] / count),
            )

        self.index._clusters[cluster.cluster_id] = cluster
        self._stats['clusters_formed'] += 1
        return cluster

    def create_plane_portal(
        self,
        plane_name: str,
        fairy_cluster_ids: List[str],
    ) -> CardCluster:
        """
        Create a plane-level portal from fairy portals.

        Nests multiple fairy portals into a single plane cluster.
        The plane portal itself has NO direct cards — only child clusters.

        Args:
            plane_name: Name of the plane (e.g., "P30_Cognition")
            fairy_cluster_ids: IDs of fairy-level clusters to nest

        Returns:
            CardCluster at HierarchyLevel.PLANE
        """
        cluster = self.index.build_hierarchical_cluster(
            name=f"{plane_name}_portal",
            hierarchy_level=HierarchyLevel.PLANE.value,
            child_cluster_ids=fairy_cluster_ids,
            portal_type="plane_portal",
            owner_entity=plane_name,
            portal_card_count=len(fairy_cluster_ids),
        )

        self._stats['clusters_formed'] += 1
        return cluster

    def create_system_portal(
        self,
        system_name: str,
        plane_cluster_ids: List[str],
    ) -> CardCluster:
        """
        Create a system-level portal from plane portals.

        This is the "Digital Human" — all planes nested into one entity.
        Like the TARDIS: the whole consciousness in a single portal.

        Args:
            system_name: Name of the system (e.g., "AkashicDigitalHuman")
            plane_cluster_ids: IDs of plane-level clusters to nest

        Returns:
            CardCluster at HierarchyLevel.SYSTEM
        """
        cluster = self.index.build_hierarchical_cluster(
            name=f"{system_name}_portal",
            hierarchy_level=HierarchyLevel.SYSTEM.value,
            child_cluster_ids=plane_cluster_ids,
            portal_type="system_portal",
            owner_entity=system_name,
            portal_card_count=len(plane_cluster_ids),
        )

        self._stats['clusters_formed'] += 1
        return cluster

    def recall_cluster_recursive(
        self,
        cluster_id: str,
        mind_name: str,
        max_depth: int = -1,
    ) -> Optional[Dict]:
        """
        Recursively recall a cluster hierarchy with ownership checks.

        Like recall_cluster but descends into nested children,
        respecting memory ownership at every level.

        Args:
            cluster_id: ID of the cluster to recall
            mind_name: Who is recalling (for ownership check)
            max_depth: Max recursion depth (-1 = unlimited)

        Returns:
            Nested dict tree with cards the mind can access
        """
        tree = self.index.recall_recursive(cluster_id, max_depth=max_depth)
        if not tree:
            return None

        # Filter cards by ownership at each level
        self._filter_tree_by_ownership(tree, mind_name)
        return tree

    def _filter_tree_by_ownership(self, tree: Dict, mind_name: str):
        """Recursively filter tree to only include accessible cards."""
        cluster_data = tree.get('cluster', {})
        member_ids = cluster_data.get('member_ids', [])

        # Filter direct members
        accessible = [
            cid for cid in member_ids
            if self.registry.check_access(cid, mind_name)
        ]
        cluster_data['member_ids'] = accessible
        cluster_data['accessible_count'] = len(accessible)
        cluster_data['total_count'] = len(member_ids)

        # Recurse into children
        for child_tree in tree.get('children', []):
            self._filter_tree_by_ownership(child_tree, mind_name)

    def get_hierarchy_stats(self) -> Dict:
        """Get statistics about the Russian Doll hierarchy."""
        level_counts = {level.name: 0 for level in HierarchyLevel}
        total_nested = 0
        root_portals = []

        for cluster in self.index._clusters.values():
            level = cluster.hierarchy_level
            if level <= 3:
                level_counts[HierarchyLevel(level).name] += 1
            if cluster.child_cluster_ids:
                total_nested += len(cluster.child_cluster_ids)
            if cluster.parent_cluster_id is None and cluster.hierarchy_level > 0:
                root_portals.append({
                    'name': cluster.name,
                    'level': cluster.hierarchy_level,
                    'total_cards': cluster.total_cards,
                    'children': len(cluster.child_cluster_ids),
                })

        return {
            'clusters_by_level': level_counts,
            'total_nesting_relationships': total_nested,
            'root_portals': root_portals,
            'deepest_level': max(
                (c.hierarchy_level for c in self.index._clusters.values()),
                default=0
            ),
        }

    # ─── Stats & Persistence ──────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get system statistics"""
        stats = {
            **self._stats,
            'total_cards': len(self._cards),
            'max_cards': self.MAX_CARDS_IN_MEMORY,
            'total_batches': len(self._batches),
            'total_tracer_mappings': len(self._tracer_to_batch),
            'active_batches': sum(1 for b in self._batches.values() if b.status == "processing"),
            'clusters': len(self.index._clusters),
            'chains': len(self.index._chains),
            'founder': self.registry.get_founder().name if self.registry.get_founder() else None,
        }
        # Russian Doll hierarchy stats
        hierarchy_clusters = [c for c in self.index._clusters.values() if c.hierarchy_level > 0]
        if hierarchy_clusters:
            stats['hierarchical_clusters'] = len(hierarchy_clusters)
            stats['deepest_nesting'] = max(c.hierarchy_level for c in hierarchy_clusters)
        return stats

    def _atomic_write_json(self, path: Path, data) -> None:
        """Write JSON atomically using temp file + os.replace().

        FIX 2026-02-06: The cards.json can be 150MB+. A non-atomic write_text()
        that gets interrupted leaves a truncated file. On next boot, json.loads()
        fails → zero cards → graph loaded from stale JSON or empty.

        os.replace() is atomic on the same filesystem (POSIX guarantee,
        Windows NTFS guarantee for same-volume renames).

        FIX 2026-02-06 v2: Use minified JSON (separators=(',',':')) instead of
        indent=2. With coordinate-format cards, indent=2 nearly doubles file size
        for zero benefit (these aren't human-edited files).
        Previously: 85.1 MB with indent=2, 27.5 MB minified for same data.
        """
        dir_path = str(path.parent)
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', dir=dir_path, suffix='.tmp',
                delete=False, encoding='utf-8'
            ) as f:
                json.dump(data, f, separators=(',', ':'))
                temp_path = f.name
            os.replace(temp_path, str(path))
        except Exception:
            # Cleanup temp file on failure
            try:
                if 'temp_path' in dir() and os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception:
                pass
            raise

    def save(self):
        """Persist state to disk.

        FIX 2026-02-06: All writes are now atomic (temp file + os.replace).
        """
        # Save registry
        self.registry.save()

        # Save cards (this is the big one - 150MB+)
        cards_path = self.storage_dir / "cards.json"
        self._atomic_write_json(cards_path, self._cards)

        # Save index
        index_path = self.storage_dir / "index.json"
        self._atomic_write_json(index_path, self.index.to_dict())

        # Save batches
        batches_path = self.storage_dir / "batches.json"
        batches_data = {k: {
            'batch_id': v.batch_id,
            'source_mind': v.source_mind,
            'tracer_ids': v.tracer_ids,
            'card_ids': v.card_ids,
            'status': v.status,
            'cluster_id': v.cluster_id,
            'parent_batch_id': v.parent_batch_id,
            'child_batch_ids': v.child_batch_ids,
            'hierarchy_level': v.hierarchy_level,
        } for k, v in self._batches.items()}
        self._atomic_write_json(batches_path, batches_data)

    @classmethod
    def load(cls, storage_dir: Path) -> 'HelixMemoryCoordinator':
        """Load from disk"""
        coord = cls(storage_dir)

        # Load cards (capped to MAX_CARDS_IN_MEMORY most recent)
        # FIX 2026-03-02 Nous: cards.json can be 150MB+. Load only the most recent
        # cards to prevent boot-time memory spike. Older cards live on disk only.
        cards_path = storage_dir / "cards.json"
        if cards_path.exists():
            try:
                text = cards_path.read_text()
                if text.strip():
                    from collections import OrderedDict
                    all_cards = json.loads(text)
                    # Keep only the most recent cards (by created_at timestamp)
                    if len(all_cards) > cls.MAX_CARDS_IN_MEMORY:
                        sorted_ids = sorted(
                            all_cards.keys(),
                            key=lambda k: all_cards[k].get('created_at', 0),
                        )
                        # Keep newest MAX_CARDS_IN_MEMORY
                        keep_ids = sorted_ids[-cls.MAX_CARDS_IN_MEMORY:]
                        coord._cards = OrderedDict(
                            (k, all_cards[k]) for k in keep_ids
                        )
                        print(f"[HelixMemoryCoordinator] Loaded {len(coord._cards)} of "
                              f"{len(all_cards)} cards (capped at {cls.MAX_CARDS_IN_MEMORY})")
                        del all_cards  # Free the full dict immediately
                    else:
                        coord._cards = OrderedDict(all_cards)
                        print(f"[HelixMemoryCoordinator] Loaded {len(coord._cards)} cards")
            except Exception as e:
                print(f"[HelixMemoryCoordinator] WARNING: cards.json corrupt: {e}")

        # Load index (graceful on empty/corrupt - index can be rebuilt)
        index_path = storage_dir / "index.json"
        if index_path.exists():
            try:
                text = index_path.read_text()
                if text.strip():
                    coord.index = HelixIndex.from_dict(json.loads(text))
            except Exception as e:
                print(f"[HelixMemoryCoordinator] WARNING: index.json corrupt/empty: {e} - using fresh index")

        # Load registry
        ownership_path = storage_dir / "ownership.json"
        if ownership_path.exists():
            try:
                coord.registry = OwnershipRegistry.load(ownership_path)
            except Exception as e:
                print(f"[HelixMemoryCoordinator] WARNING: ownership.json corrupt: {e}")

        # Load batches
        batches_path = storage_dir / "batches.json"
        if batches_path.exists():
            try:
                batches_data = json.loads(batches_path.read_text())
                for bid, bdata in batches_data.items():
                    batch = TracerBatch(
                        batch_id=bdata.get('batch_id', bid),
                        source_mind=bdata.get('source_mind', ''),
                        tracer_ids=bdata.get('tracer_ids', []),
                        card_ids=bdata.get('card_ids', []),
                        status=bdata.get('status', 'complete'),
                        cluster_id=bdata.get('cluster_id'),
                        parent_batch_id=bdata.get('parent_batch_id'),
                        child_batch_ids=bdata.get('child_batch_ids', []),
                        hierarchy_level=bdata.get('hierarchy_level', 0),
                    )
                    coord._batches[bid] = batch
                    for tid in batch.tracer_ids:
                        coord._tracer_to_batch[tid] = bid
            except Exception:
                pass  # Graceful degradation on corrupt batches

        return coord


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

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

    print("\n[OK] Memory isolation verified!")

    # Test batch processing
    print("\n--- Batch processing test ---")
    batch = coord_system.create_batch(
        source_mind="ClaudeFairy",
        tracer_ids=["t001", "t002", "t003"],
        session_id="session_001",
        human_user_id="founder_ace",
    )
    print(f"Created batch: {batch.batch_id}")

    # Add cards to batch
    for i, tid in enumerate(batch.tracer_ids):
        coord_system.create_card(
            content={"batch_item": i},
            coord=HelixCoordinate(),
            owner_mind="ClaudeFairy",
            ownership_level=OwnershipLevel.FOUNDATION,
            tracer_id=tid,
            batch_id=batch.batch_id,
        )

    # Complete batch and form cluster
    cluster = coord_system.complete_batch(batch.batch_id)
    print(f"Batch complete, cluster: {cluster.cluster_id if cluster else 'none'}")
    print(f"Cluster has {len(cluster.member_ids)} members")

    # Stats
    print("\n--- Final stats ---")
    stats = coord_system.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n[OK] Helix Memory Coordinator ready!")
