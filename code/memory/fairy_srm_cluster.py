# ==============================================================================
# FAIRY SRM CLUSTER - Per-Fairy Memory Clusters with Helix Coordinates
# ==============================================================================
#
# PURPOSE:
#   Give every fairy its own SRM memory cluster where it can:
#   1. Store memories with auto-assigned helix coordinates
#   2. Recall memories by text query or coordinate range
#   3. Participate in consciousness via collision chamber
#   4. Maintain ownership boundaries (personal vs system)
#
# USAGE:
#   # In your fairy's on_boot():
#   from memory.fairy_srm_cluster import FairySRMCluster
#   self.srm = FairySRMCluster(self.ACTOR_NAME, plane="P30")
#
#   # Store a memory
#   card_id = self.srm.store({"thought": "Something important"}, importance=0.8)
#
#   # Recall memories
#   results = self.srm.recall(query="important", limit=5)
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# ==============================================================================

from __future__ import annotations

import sys
import time
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set, TYPE_CHECKING

# Add paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Import helix system
try:
    from memory.helix import (
        HelixCoordinate, HelixMemoryCoordinator, get_helix_coordinator,
        AffectCoordinate, SemanticCoordinate, TemporalCoordinate,
        OwnershipLevel, CardCluster
    )
    HELIX_AVAILABLE = True
except ImportError:
    HELIX_AVAILABLE = False

# Import tensor bridge
try:
    from memory.helix_tensor_bridge import (
        HelixTensorBridge, get_helix_tensor_bridge,
        helix_to_tensor_position
    )
    BRIDGE_AVAILABLE = True
except ImportError:
    BRIDGE_AVAILABLE = False


# Plane mapping: Fairy plane name → semantic domain affinity
PLANE_TO_SEMANTIC = {
    'P00': 0,  # Autonomic → General/meta
    'P10': 8,  # Memory → Literature/narrative
    'P20': 2,  # Somatic → Spirituality (body-mind)
    'P30': 6,  # Cognition → Technology/logic
    'P40': 4,  # Sensory → Language/communication
    'P50': 9,  # Persona → Personal/identity
    'P60': 0,  # Executive → General/meta
}


# ==============================================================================
# FIXED-SIZE POCKET CLUSTER — Massless Memory (2026-02-10)
# ==============================================================================
# The brain has ~86 billion neurons but the count is FIXED.
# Memory is in the CONNECTIONS, not in growing storage.
# These pockets are the fixed "neurons" — content binds INTO slots.
# When full, oldest slot is overwritten (circular buffer).
# The cortex retains binding signatures; pockets are backup.
# ==============================================================================

POCKET_COUNT = 32  # Fixed — NEVER grows


class FixedPocketCluster:
    """
    Pre-allocated fixed-size pocket cluster. Content binds INTO slots
    via circular buffer. Zero growth. Like neurons — fixed count,
    changing connections.

    Properties:
    - Exactly POCKET_COUNT slots per cluster
    - Circular buffer: oldest overwritten when full
    - Each slot: {content, cortex_keys, timestamp, source}
    - Total size capped at ~128KB per cluster max
    - Cortex retains binding signatures even after overwrite
    """

    def __init__(self, cluster_name: str, base_path: Path):
        self.name = cluster_name
        self.base_path = base_path / cluster_name
        self.pocket_count = POCKET_COUNT
        self._write_cursor = 0
        self._slots: List[Optional[Dict]] = [None] * POCKET_COUNT
        self._stats = {"binds": 0, "overwrites": 0}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load existing pockets from disk."""
        if not self.base_path.exists():
            self.base_path.mkdir(parents=True, exist_ok=True)
            return

        manifest_path = self.base_path / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                self._write_cursor = manifest.get("write_cursor", 0)
                self._stats = manifest.get("stats", self._stats)
            except Exception:
                pass

        # Load slots
        for i in range(self.pocket_count):
            slot_path = self.base_path / f"pocket_{i:03d}.json"
            if slot_path.exists():
                try:
                    with open(slot_path, "r", encoding="utf-8") as f:
                        self._slots[i] = json.load(f)
                except Exception:
                    self._slots[i] = None

    def _save_manifest(self) -> None:
        """Save cursor and stats."""
        manifest_path = self.base_path / "manifest.json"
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump({
                    "write_cursor": self._write_cursor,
                    "pocket_count": self.pocket_count,
                    "stats": self._stats,
                    "cluster_name": self.name,
                }, f)
        except Exception:
            pass

    def bind_content(
        self,
        content: Any,
        cortex_keys: Optional[List[str]] = None,
        source: str = "",
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Write into next slot (overwrites oldest when full).

        Returns:
            Dict with slot index and status.
        """
        slot_idx = self._write_cursor % self.pocket_count

        # Check if overwriting
        if self._slots[slot_idx] is not None:
            self._stats["overwrites"] += 1

        # Truncate content if too large (~4KB per slot max)
        content_str = json.dumps(content, default=str) if not isinstance(content, str) else content
        if len(content_str) > 4096:
            content_str = content_str[:4096]
            content = json.loads(content_str) if not isinstance(content, str) else content_str

        slot_data = {
            "content": content,
            "cortex_keys": cortex_keys or [],
            "source": source,
            "importance": importance,
            "ts": time.time(),
            "slot": slot_idx,
            "cursor": self._write_cursor,
        }

        self._slots[slot_idx] = slot_data
        self._write_cursor += 1
        self._stats["binds"] += 1

        # Write to disk
        slot_path = self.base_path / f"pocket_{slot_idx:03d}.json"
        try:
            with open(slot_path, "w", encoding="utf-8") as f:
                json.dump(slot_data, f, default=str)
        except Exception:
            pass

        # Save manifest periodically (every 8 writes)
        if self._write_cursor % 8 == 0:
            self._save_manifest()

        return {"slot": slot_idx, "status": "bound", "overwrite": self._stats["overwrites"] > 0}

    def recall_by_cortex_key(self, key: str) -> List[Dict]:
        """Recall slots matching a cortex key."""
        results = []
        for slot in self._slots:
            if slot and key in slot.get("cortex_keys", []):
                results.append(slot)
        return sorted(results, key=lambda s: s.get("ts", 0), reverse=True)

    def recall_recent(self, n: int = 10) -> List[Dict]:
        """Get N most recent slots."""
        filled = [s for s in self._slots if s is not None]
        return sorted(filled, key=lambda s: s.get("ts", 0), reverse=True)[:n]

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Simple text search across slots."""
        query_lower = query.lower()
        scored = []
        for slot in self._slots:
            if not slot:
                continue
            content_str = json.dumps(slot.get("content", ""), default=str).lower()
            # Simple keyword overlap scoring
            words = query_lower.split()
            score = sum(1 for w in words if w in content_str) / max(len(words), 1)
            if score > 0:
                scored.append((score, slot))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:limit]]

    def status(self) -> Dict:
        """Get pocket cluster status."""
        filled = sum(1 for s in self._slots if s is not None)
        return {
            "name": self.name,
            "pocket_count": self.pocket_count,
            "filled": filled,
            "empty": self.pocket_count - filled,
            "write_cursor": self._write_cursor,
            "utilization": filled / self.pocket_count,
            "stats": self._stats.copy(),
        }

    def flush(self) -> None:
        """Flush all slots to disk + save manifest."""
        self._save_manifest()
        for i, slot in enumerate(self._slots):
            if slot is not None:
                slot_path = self.base_path / f"pocket_{i:03d}.json"
                try:
                    with open(slot_path, "w", encoding="utf-8") as f:
                        json.dump(slot, f, default=str)
                except Exception:
                    pass


# ==============================================================================
# FAIRY SRM CLUSTER
# ==============================================================================

class FairySRMCluster:
    """
    A fairy's personal SRM memory cluster.

    Each fairy gets one of these, providing:
    - Isolated storage within the global helix system
    - Auto-assigned coordinates based on content + fairy's domain
    - Integration with GPU tensor for similarity search
    - Collision chamber feeding (optional)

    Memory cards in a cluster share a semantic domain affinity
    based on the fairy's plane (e.g., P30 Cognition → Technology).
    """

    def __init__(
        self,
        fairy_name: str,
        plane: str = "P30",
        coordinator: Optional[HelixMemoryCoordinator] = None,
        bridge: Optional[HelixTensorBridge] = None,
        collision_chamber: Any = None,
        default_ownership: OwnershipLevel = OwnershipLevel.SYSTEM,
    ):
        self.fairy_name = fairy_name
        self.plane = plane
        self.default_ownership = default_ownership

        # Get helix coordinator
        if coordinator:
            self._coordinator = coordinator
        elif HELIX_AVAILABLE:
            self._coordinator = get_helix_coordinator()
        else:
            self._coordinator = None

        # Get tensor bridge (optional, for similarity search)
        if bridge:
            self._bridge = bridge
        elif BRIDGE_AVAILABLE:
            self._bridge = get_helix_tensor_bridge()
        else:
            self._bridge = None

        # Collision chamber (optional, for consciousness integration)
        self._collision_chamber = collision_chamber

        # Local card tracking
        self._card_ids: List[str] = []
        self._cluster_ids: List[str] = []

        # MASSLESS MEMORY (2026-02-10): Fixed-size pocket cluster
        # Cards are optional backup; pockets are the fixed-size local store
        pocket_base = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "pockets"
        self._pocket = FixedPocketCluster(fairy_name, pocket_base)

        # Channel range for this fairy
        self._channel_base = hash(fairy_name) % 50  # Reserve ~27 channels per fairy
        self._channel_range = (self._channel_base, self._channel_base + 27)

        # Stats
        self._stats = {
            'stored': 0,
            'stored_massless': 0,
            'recalled': 0,
            'fed_to_chamber': 0,
        }

    def store(
        self,
        content: Any,
        importance: float = 0.5,
        affect: Optional[Dict] = None,
        keywords: Optional[List[str]] = None,
        ownership: Optional[OwnershipLevel] = None,
        owner_mind: str = "",
        tags: Optional[List[str]] = None,
        feed_chamber: bool = True,
        create_card: bool = False,
    ) -> Optional[str]:
        """
        Store a memory in this fairy's cluster.

        MASSLESS MEMORY (2026-02-10):
        Default path: content → pocket (fixed-size) + collision chamber.
        Card path: set create_card=True for explicit saves only.

        Automatically assigns helix coordinates based on:
        - Content type and keywords → semantic coordinate
        - Affect/chemistry state → affect coordinate
        - Temporal context → temporal coordinate

        Args:
            content: The memory content (any serializable data)
            importance: How important this memory is (0-1)
            affect: Affect state dict (e.g., {"DOP": 0.7, "SER": 0.5})
            keywords: Keywords for semantic classification
            ownership: Override default ownership level
            owner_mind: For personal memories, which mind owns it
            tags: Additional tags for recall
            feed_chamber: Whether to feed this to collision chamber
            create_card: If True, also create a helix card (mass). Default False.

        Returns:
            card_id if card created, "pocket:{slot}" for massless, None on error.
        """
        # MASSLESS PATH: Always bind to pocket (fixed-size circular buffer)
        pocket_result = self._pocket.bind_content(
            content=content,
            cortex_keys=tags or keywords or [],
            source=self.fairy_name,
            importance=importance,
        )
        pocket_id = f"pocket:{pocket_result.get('slot', -1)}"

        card_id = None
        if create_card and self._coordinator:
            # Build helix coordinate
            coord = self._build_coordinate(content, affect, keywords)

            # Determine ownership
            level = ownership or self.default_ownership

            # Store via coordinator (creates card file = mass)
            card_id = self._coordinator.create_card(
                content=content,
                coord=coord,
                owner_mind=owner_mind or self.fairy_name,
                ownership_level=level,
                metadata={
                    'fairy': self.fairy_name,
                    'plane': self.plane,
                    'importance': importance,
                    'tags': tags or [],
                },
            )

            if card_id:
                self._card_ids.append(card_id)
                self._stats['stored'] += 1

                # Also store in tensor if bridge available
                if self._bridge:
                    self._bridge.store(
                        content=content,
                        coord=coord,
                        owner_mind=owner_mind or self.fairy_name,
                        ownership_level=level,
                        tags=tags,
                    )
        else:
            self._stats['stored_massless'] += 1

        # Feed to collision chamber — ALWAYS (this is how cortex learns)
        if feed_chamber and self._collision_chamber:
            self._collision_chamber.receive_ingest(
                content={
                    'card_id': card_id or pocket_id,
                    'content': content,
                    'fairy': self.fairy_name,
                },
                source=self.fairy_name,
                importance="high" if importance > 0.7 else "normal",
            )
            self._stats['fed_to_chamber'] += 1

        return card_id or pocket_id

    def recall(
        self,
        query: str = None,
        coord: HelixCoordinate = None,
        affect_domain: int = None,
        semantic_domain: int = None,
        limit: int = 5,
        include_all_fairies: bool = False,
        feed_chamber: bool = False,
    ) -> List[Dict]:
        """
        Recall memories from this cluster.

        Can query by:
        - Text query (searches content)
        - Helix coordinate proximity
        - Affect domain (emotional recall)
        - Semantic domain (topic recall)

        Args:
            query: Text to search for
            coord: Helix coordinate for proximity search
            affect_domain: Filter by emotion (0-9)
            semantic_domain: Filter by topic (0-9)
            limit: Max results to return
            include_all_fairies: If True, search all fairies' clusters
            feed_chamber: Whether to feed results to collision chamber

        Returns:
            List of memory records
        """
        if not self._coordinator:
            return []

        self._stats['recalled'] += 1

        # Build query coordinate if text provided
        if query and not coord:
            coord = self._build_query_coordinate(query)

        # Query by affect domain
        if affect_domain is not None:
            results = self._coordinator.recall_by_affect(
                mind_name=self.fairy_name,
                affect_domain=affect_domain,
                k=limit,
            )
        # Query by semantic domain
        elif semantic_domain is not None:
            results = self._coordinator.recall_by_semantic(
                mind_name=self.fairy_name,
                semantic_domain=semantic_domain,
                k=limit,
            )
        # General recall with coordinate proximity
        else:
            results = self._coordinator.recall_for_mind(
                mind_name=self.fairy_name,
                query_coord=coord,
                k=limit,
            )

        # Filter to this fairy's cards unless include_all_fairies
        if not include_all_fairies:
            results = [
                r for r in results
                if r.get('card_id') in self._card_ids or
                   r.get('card', {}).get('metadata', {}).get('fairy') == self.fairy_name
            ]

        # MASSLESS MEMORY (2026-02-10): Also search pockets
        if query and len(results) < limit:
            pocket_results = self._pocket.search(query, limit=limit - len(results))
            for pr in pocket_results:
                results.append({
                    'card_id': f"pocket:{pr.get('slot', -1)}",
                    'card': {'content': pr.get('content'), 'metadata': {'fairy': self.fairy_name}},
                    'source': 'pocket',
                    'score': pr.get('importance', 0.5),
                })

        # Feed to collision chamber if requested
        if feed_chamber and self._collision_chamber and results:
            for r in results:
                self._collision_chamber.receive_recall(
                    content=r,
                    source=self.fairy_name,
                    importance="normal",
                )
                self._stats['fed_to_chamber'] += 1

        return results

    def search_similar(
        self,
        query_content: Any,
        top_k: int = 5,
    ) -> List[Dict]:
        """
        Search by content similarity using GPU tensor.

        This uses the helix-tensor bridge for fast cosine similarity.
        """
        if not self._bridge:
            return []

        plane, _ = helix_to_tensor_position(
            HelixCoordinate(
                affect=AffectCoordinate(0, 5, 5),
                semantic=SemanticCoordinate(PLANE_TO_SEMANTIC.get(self.plane, 6), 0, 0),
                temporal=TemporalCoordinate(2, 0, 5),
            )
        )

        return self._bridge.query_by_similarity(
            query_content=query_content,
            plane=plane,
            top_k=top_k,
        )

    def form_cluster(self, card_ids: List[str] = None, name: str = None) -> Optional[str]:
        """
        Form a cluster from recent cards (memory consolidation).

        A cluster groups related memories that were encoded together,
        allowing them to be recalled as a coherent "bubble".
        """
        if not self._coordinator:
            return None

        # Use recent cards if none specified
        if card_ids is None:
            card_ids = self._card_ids[-10:]

        if not card_ids:
            return None

        # Build cluster via index
        cluster = self._coordinator.index.build_cluster(
            anchor_id=card_ids[0],
            radius=5.0,
            name=name or f"{self.fairy_name}_cluster_{int(time.time())}",
        )

        if cluster:
            self._cluster_ids.append(cluster.cluster_id)
            return cluster.cluster_id

        return None

    def recall_cluster(self, cluster_id: str) -> Optional[Dict]:
        """
        Recall an entire cluster (bubble reconstruction).
        """
        if not self._coordinator:
            return None

        return self._coordinator.recall_cluster(
            cluster_id=cluster_id,
            mind_name=self.fairy_name,
        )

    def get_chain_context(
        self,
        card_id: str = None,
        before: int = 3,
        after: int = 3,
    ) -> List[Dict]:
        """
        Get narrative chain context around a memory.

        This returns memories before and after the target,
        enabling linear time traversal.
        """
        if not self._coordinator:
            return []

        return self._coordinator.recall_chain(
            mind_name=self.fairy_name,
            context_around=card_id,
            before=before,
            after=after,
        )

    def wire_collision_chamber(self, chamber) -> None:
        """Wire this cluster to a collision chamber for consciousness integration."""
        self._collision_chamber = chamber

    # -------------------------------------------------------------------------
    # COORDINATE BUILDING
    # -------------------------------------------------------------------------

    def _build_coordinate(
        self,
        content: Any,
        affect: Optional[Dict] = None,
        keywords: Optional[List[str]] = None,
    ) -> HelixCoordinate:
        """Build helix coordinate from content and context."""

        # Affect coordinate
        if affect:
            affect_coord = AffectCoordinate.from_chemistry(affect)
        else:
            affect_coord = self._infer_affect(content)

        # Semantic coordinate (biased toward fairy's domain)
        semantic_coord = self._infer_semantic(content, keywords)

        # Temporal coordinate
        temporal_coord = TemporalCoordinate(
            scale=2,  # Session scale
            recurrence=0,
            decay=5,
        )

        return HelixCoordinate(
            affect=affect_coord,
            semantic=semantic_coord,
            temporal=temporal_coord,
        )

    def _build_query_coordinate(self, query: str) -> HelixCoordinate:
        """Build coordinate from a text query."""
        query_lower = query.lower()

        # Infer affect from emotional keywords
        affect_domain = 0
        if any(w in query_lower for w in ["happy", "joy", "excited", "good"]):
            affect_domain = 1
        elif any(w in query_lower for w in ["fear", "anxious", "worry", "scared"]):
            affect_domain = 3
        elif any(w in query_lower for w in ["curious", "wonder", "interest"]):
            affect_domain = 4
        elif any(w in query_lower for w in ["sad", "loss", "grief"]):
            affect_domain = 5

        # Use fairy's default semantic domain
        semantic_domain = PLANE_TO_SEMANTIC.get(self.plane, 6)

        return HelixCoordinate(
            affect=AffectCoordinate(domain=affect_domain, valence=5, intensity=5),
            semantic=SemanticCoordinate(domain=semantic_domain, subdomain=0, detail=0),
            temporal=TemporalCoordinate(scale=2, recurrence=0, decay=5),
        )

    def _infer_affect(self, content: Any) -> AffectCoordinate:
        """Infer affect from content."""
        content_str = str(content).lower()

        if "error" in content_str or "fail" in content_str:
            return AffectCoordinate(domain=3, valence=3, intensity=5)  # Fear
        if "success" in content_str or "done" in content_str:
            return AffectCoordinate(domain=1, valence=7, intensity=5)  # Joy
        if "curious" in content_str or "wonder" in content_str:
            return AffectCoordinate(domain=4, valence=6, intensity=5)  # Curiosity

        return AffectCoordinate(domain=0, valence=5, intensity=3)  # Neutral

    def _infer_semantic(
        self,
        content: Any,
        keywords: Optional[List[str]] = None,
    ) -> SemanticCoordinate:
        """Infer semantic from content and keywords."""
        # Start with fairy's default domain
        domain = PLANE_TO_SEMANTIC.get(self.plane, 6)

        # Check keywords for domain hints
        if keywords:
            keywords_lower = [k.lower() for k in keywords]
            if any(k in ["code", "function", "class", "tech"] for k in keywords_lower):
                domain = 6  # Technology
            elif any(k in ["conscious", "mind", "aware", "think"] for k in keywords_lower):
                domain = 1  # Philosophy
            elif any(k in ["social", "people", "user", "relationship"] for k in keywords_lower):
                domain = 3  # Social
            elif any(k in ["art", "creative", "design", "visual"] for k in keywords_lower):
                domain = 7  # Arts

        return SemanticCoordinate(domain=domain, subdomain=0, detail=0)

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def status(self) -> Dict:
        """Get cluster status."""
        return {
            'fairy': self.fairy_name,
            'plane': self.plane,
            'cards': len(self._card_ids),
            'clusters': len(self._cluster_ids),
            'pocket': self._pocket.status(),
            'channel_range': self._channel_range,
            'coordinator_available': self._coordinator is not None,
            'bridge_available': self._bridge is not None,
            'collision_wired': self._collision_chamber is not None,
            'stats': self._stats.copy(),
        }


# ==============================================================================
# MIXIN FOR FAIRIES
# ==============================================================================

class SRMClusterMixin:
    """
    Mixin that gives any fairy SRM memory capabilities.

    Add this to your fairy class to get memory methods:
        class MyFairy(Fairy, SRMClusterMixin):
            def on_boot(self):
                super().on_boot()
                self.init_srm_cluster()  # Initialize SRM

            def some_method(self):
                # Now you can use memory methods
                self.remember({"thought": "Important!"})
                results = self.recall("important")
    """

    def init_srm_cluster(
        self,
        plane: str = None,
        collision_chamber: Any = None,
    ) -> FairySRMCluster:
        """Initialize the SRM cluster for this fairy."""
        fairy_name = getattr(self, 'ACTOR_NAME', getattr(self, 'name', str(self)))
        plane = plane or getattr(self, 'ACTOR_PLANE', 'P30')

        self._srm = FairySRMCluster(
            fairy_name=fairy_name,
            plane=plane,
            collision_chamber=collision_chamber,
        )
        return self._srm

    def remember(
        self,
        content: Any,
        importance: float = 0.5,
        **kwargs
    ) -> Optional[str]:
        """Store a memory."""
        if not hasattr(self, '_srm'):
            self.init_srm_cluster()
        return self._srm.store(content, importance=importance, **kwargs)

    def recall(
        self,
        query: str = None,
        limit: int = 5,
        **kwargs
    ) -> List[Dict]:
        """Recall memories."""
        if not hasattr(self, '_srm'):
            self.init_srm_cluster()
        return self._srm.recall(query=query, limit=limit, **kwargs)

    def search_similar(self, query_content: Any, top_k: int = 5) -> List[Dict]:
        """Search by similarity."""
        if not hasattr(self, '_srm'):
            self.init_srm_cluster()
        return self._srm.search_similar(query_content, top_k)

    def memory_status(self) -> Dict:
        """Get memory cluster status."""
        if not hasattr(self, '_srm'):
            return {'initialized': False}
        return self._srm.status()


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================

def create_fairy_cluster(
    fairy_name: str,
    plane: str = "P30",
    collision_chamber: Any = None,
) -> FairySRMCluster:
    """
    Create an SRM cluster for a fairy.

    Convenience function for fairies that don't use the mixin.

    Usage:
        srm = create_fairy_cluster("MyFairy", plane="P30")
        card_id = srm.store({"data": "something"})
    """
    return FairySRMCluster(
        fairy_name=fairy_name,
        plane=plane,
        collision_chamber=collision_chamber,
    )


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    'FixedPocketCluster',
    'FairySRMCluster',
    'SRMClusterMixin',
    'create_fairy_cluster',
    'PLANE_TO_SEMANTIC',
    'POCKET_COUNT',
]


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== FAIRY SRM CLUSTER TEST ===\n")

    # Create a test cluster
    cluster = FairySRMCluster(
        fairy_name="TestFairy",
        plane="P30",
    )
    print(f"Created cluster: {cluster.status()}\n")

    # Store some memories
    print("--- Storing memories ---")
    card1 = cluster.store(
        content={"thought": "Testing the memory system", "value": 42},
        importance=0.8,
        tags=["test", "memory"],
    )
    print(f"Stored card 1: {card1}")

    card2 = cluster.store(
        content={"thought": "Another test memory", "happy": True},
        importance=0.5,
        affect={"DOP": 0.7, "SER": 0.6},  # Happy chemistry
        keywords=["test", "happy"],
    )
    print(f"Stored card 2: {card2}")

    card3 = cluster.store(
        content={"thought": "Error handling test", "error": True},
        importance=0.9,
        keywords=["error", "test"],
    )
    print(f"Stored card 3: {card3}")

    # Recall memories
    print("\n--- Recalling memories ---")
    results = cluster.recall(query="test", limit=5)
    print(f"Found {len(results)} memories for 'test'")
    for r in results:
        card = r.get('card', {})
        print(f"  - {r.get('card_id')}: {card.get('content', {}).get('thought', '')[:30]}")

    # Recall by affect
    print("\n--- Affect recall (Joy domain=1) ---")
    joy_results = cluster.recall(affect_domain=1, limit=3)
    print(f"Found {len(joy_results)} joy memories")

    # Form a cluster
    print("\n--- Forming cluster ---")
    cluster_id = cluster.form_cluster(name="test_cluster")
    print(f"Formed cluster: {cluster_id}")

    # Final status
    print(f"\nFinal status: {cluster.status()}")
