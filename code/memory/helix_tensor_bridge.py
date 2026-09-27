# ==============================================================================
# HELIX-TENSOR BRIDGE - Maps Triple Helix coordinates to GPU Tensor positions
# ==============================================================================
#
# PURPOSE:
#   Bridge the human-readable Dewey Decimal helix coordinates to the
#   GPU-optimized tensor memory fabric.
#
# MAPPING:
#   Helix Coordinate (AAA.SSS.TTT) → Tensor Position (Plane, Channel, Time, Embedding)
#
#   - Plane (0-6): From semantic domain (0-9 → 0-6 with folding)
#   - Channel (0-76): Combined from affect + semantic (77 emotion channels)
#   - Time: Auto-incremented circular buffer position
#   - Embedding: 128-dim vector from content
#
# DUAL LOOKUP:
#   - Similarity Search: GPU tensor cosine similarity (fast vector search)
#   - Coordinate Search: Helix index by domain/range (categorical lookup)
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# ==============================================================================

from __future__ import annotations

import sys
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# Add paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Import helix system
try:
    from memory.helix import (
        HelixCoordinate, HelixMemoryCoordinator, get_helix_coordinator,
        AffectCoordinate, SemanticCoordinate, TemporalCoordinate,
        OwnershipLevel
    )
    HELIX_AVAILABLE = True
except ImportError:
    HELIX_AVAILABLE = False
    print("[HelixTensorBridge] WARNING: Helix memory system not available")

# Import tensor fabric
try:
    from memory.tensor_memory_fabric import (
        GPUTensorMemoryFabric, TensorMemoryFabric,
        get_global_tensor_fabric, wire_fairy_to_tensor
    )
    TENSOR_AVAILABLE = True
except ImportError:
    TENSOR_AVAILABLE = False
    print("[HelixTensorBridge] WARNING: Tensor memory fabric not available")


# Plane mapping: Semantic domain → Tensor plane
SEMANTIC_TO_PLANE = {
    0: 'P30',  # General/meta → Cognition
    1: 'P30',  # Philosophy → Cognition
    2: 'P30',  # Spirituality → Cognition
    3: 'P50',  # Social → Persona
    4: 'P40',  # Language → Sensory
    5: 'P30',  # Science → Cognition
    6: 'P30',  # Technology → Cognition (P10 for memory-specific)
    7: 'P40',  # Arts → Sensory
    8: 'P10',  # Literature → Memory
    9: 'P50',  # Personal → Persona
}

# Plane index mapping
PLANE_TO_INDEX = {
    'P00': 0, 'P10': 1, 'P20': 2, 'P30': 3,
    'P40': 4, 'P50': 5, 'P60': 6
}


# ==============================================================================
# COORDINATE MAPPING FUNCTIONS
# ==============================================================================

def helix_to_tensor_position(coord: HelixCoordinate) -> Tuple[str, int]:
    """
    Map a helix coordinate to a tensor (plane, channel) position.

    Returns:
        (plane_name, channel_number)

    Mapping logic:
    - Plane: From semantic domain (Philosophy→P30, Social→P50, etc.)
    - Channel: Combine affect domain + semantic subdomain mod 77
    """
    # Get plane from semantic domain
    plane = SEMANTIC_TO_PLANE.get(coord.semantic.domain, 'P30')

    # Calculate channel from affect + semantic
    # Affect domain (0-9) * 7 + Semantic subdomain (0-9) → 0-76
    affect_contribution = coord.affect.domain * 7
    semantic_contribution = coord.semantic.subdomain
    channel = (affect_contribution + semantic_contribution) % 77

    return plane, channel


def tensor_to_helix_position(plane: str, channel: int) -> Tuple[int, int, int]:
    """
    Reverse mapping: tensor position → approximate helix domains.

    This is lossy since we fold 10 domains into 7 planes.

    Returns:
        (affect_domain, semantic_domain, semantic_subdomain)
    """
    # Reverse affect/semantic from channel
    affect_domain = channel // 7
    semantic_subdomain = channel % 7

    # Semantic domain from plane (best guess)
    plane_to_semantic = {
        'P00': 0,  # General
        'P10': 8,  # Literature/Memory
        'P20': 2,  # Body → Spirituality (approximate)
        'P30': 6,  # Cognition → Technology
        'P40': 4,  # Sensory → Language
        'P50': 9,  # Persona → Personal
        'P60': 0,  # Executive → General
    }
    semantic_domain = plane_to_semantic.get(plane, 0)

    return affect_domain, semantic_domain, semantic_subdomain


# ==============================================================================
# HELIX-TENSOR BRIDGE
# ==============================================================================

class HelixTensorBridge:
    """
    Bridges helix memory coordinates to GPU tensor storage.

    Provides:
    1. Store helix cards in both systems (coordinate + embedding)
    2. Query by helix coordinate ranges
    3. Query by tensor similarity search
    4. Combined search (coordinate filtering + similarity ranking)
    """

    def __init__(
        self,
        helix_coordinator: Optional[HelixMemoryCoordinator] = None,
        tensor_fabric: Optional[Any] = None,
    ):
        # Get or create helix coordinator
        if helix_coordinator:
            self.helix = helix_coordinator
        elif HELIX_AVAILABLE:
            self.helix = get_helix_coordinator()
        else:
            self.helix = None

        # Get or create tensor fabric
        if tensor_fabric:
            self.tensor = tensor_fabric
        elif TENSOR_AVAILABLE:
            self.tensor = get_global_tensor_fabric()
        else:
            self.tensor = None

        # Card ID → Tensor cell ID mapping
        self._card_to_tensor: Dict[str, str] = {}
        self._tensor_to_card: Dict[str, str] = {}

        # Stats
        self._stats = {
            'stores': 0,
            'helix_queries': 0,
            'tensor_queries': 0,
            'combined_queries': 0,
        }

    def store(
        self,
        content: Any,
        coord: HelixCoordinate,
        owner_mind: str,
        ownership_level: OwnershipLevel = OwnershipLevel.SYSTEM,
        tags: List[str] = None,
        embedding: Any = None,
    ) -> Tuple[str, str]:
        """
        Store content in both helix and tensor systems.

        Returns:
            (helix_card_id, tensor_cell_id)
        """
        # Map coordinate to tensor position
        plane, channel = helix_to_tensor_position(coord)

        # Store in helix coordinator
        helix_card_id = None
        if self.helix:
            helix_card_id = self.helix.create_card(
                content=content,
                coord=coord,
                owner_mind=owner_mind,
                ownership_level=ownership_level,
                metadata={
                    'tensor_plane': plane,
                    'tensor_channel': channel,
                    'tags': tags or [],
                },
            )

        # Store in tensor fabric
        tensor_cell_id = None
        if self.tensor:
            tensor_cell_id = self.tensor.store(
                content=content,
                author=owner_mind,
                mem_type=self._coord_to_mem_type(coord),
                channel=channel,
                plane=plane,
                tags=set(tags) if tags else None,
                embedding=embedding,
            )

        # Track mapping
        if helix_card_id and tensor_cell_id:
            self._card_to_tensor[helix_card_id] = tensor_cell_id
            self._tensor_to_card[tensor_cell_id] = helix_card_id

        self._stats['stores'] += 1
        return helix_card_id, tensor_cell_id

    def query_by_helix(
        self,
        mind_name: str,
        coord: HelixCoordinate = None,
        affect_domain: int = None,
        semantic_domain: int = None,
        k: int = 10,
    ) -> List[Dict]:
        """
        Query by helix coordinate or domain.

        Uses helix index for categorical filtering.
        """
        if not self.helix:
            return []

        self._stats['helix_queries'] += 1

        if affect_domain is not None:
            return self.helix.recall_by_affect(
                mind_name=mind_name,
                affect_domain=affect_domain,
                k=k,
            )
        elif semantic_domain is not None:
            return self.helix.recall_by_semantic(
                mind_name=mind_name,
                semantic_domain=semantic_domain,
                k=k,
            )
        else:
            return self.helix.recall_for_mind(
                mind_name=mind_name,
                query_coord=coord,
                k=k,
            )

    def query_by_similarity(
        self,
        query_content: Any,
        plane: str = None,
        channel: int = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """
        Query by content similarity using GPU tensor search.

        Fast cosine similarity in embedding space.
        """
        if not self.tensor:
            return []

        self._stats['tensor_queries'] += 1

        # Check if we have GPU tensor
        if hasattr(self.tensor, 'search_by_content'):
            return self.tensor.search_by_content(
                query_content,
                top_k=top_k,
                plane=plane,
                channel=channel,
            )
        else:
            # CPU fallback - simple text matching
            results = self.tensor.query_plane(
                plane=plane or 'P30',
                channel=channel,
                limit=top_k,
            )
            return [r.to_dict() if hasattr(r, 'to_dict') else r for r in results]

    def query_combined(
        self,
        mind_name: str,
        query_content: Any,
        coord: HelixCoordinate = None,
        affect_domain: int = None,
        semantic_domain: int = None,
        k: int = 10,
        similarity_weight: float = 0.5,
    ) -> List[Dict]:
        """
        Combined query: filter by helix coordinates, rank by similarity.

        This gives you the best of both worlds:
        - Categorical filtering (emotions, topics, time)
        - Semantic similarity (meaning, context)
        """
        self._stats['combined_queries'] += 1

        # First, get candidates from helix
        helix_results = self.query_by_helix(
            mind_name=mind_name,
            coord=coord,
            affect_domain=affect_domain,
            semantic_domain=semantic_domain,
            k=k * 3,  # Get more candidates
        )

        if not helix_results:
            return []

        # If no tensor, return helix results as-is
        if not self.tensor or not hasattr(self.tensor, 'search_by_content'):
            return helix_results[:k]

        # Get similarity scores for candidates
        similarity_results = self.query_by_similarity(
            query_content=query_content,
            top_k=k * 3,
        )

        # Build similarity score map
        similarity_map = {}
        for sr in similarity_results:
            # Try to match by content
            content_hash = hashlib.md5(str(sr.get('content', ''))[:100].encode()).hexdigest()[:8]
            similarity_map[content_hash] = sr.get('similarity', 0)

        # Combine scores
        combined = []
        for hr in helix_results:
            card = hr.get('card', {})
            content_hash = hashlib.md5(str(card.get('content', ''))[:100].encode()).hexdigest()[:8]

            helix_score = hr.get('score', 0.5)
            tensor_score = similarity_map.get(content_hash, 0)

            combined_score = (
                helix_score * (1 - similarity_weight) +
                tensor_score * similarity_weight
            )

            combined.append({
                **hr,
                'helix_score': helix_score,
                'tensor_score': tensor_score,
                'combined_score': combined_score,
            })

        # Sort by combined score
        combined.sort(key=lambda x: x['combined_score'], reverse=True)
        return combined[:k]

    def recall_cluster_with_embeddings(
        self,
        cluster_id: str,
        mind_name: str,
    ) -> Optional[Dict]:
        """
        Recall a cluster and include tensor embeddings for each card.

        This allows reconstructing the "topography of that moment" with
        both categorical (helix) and semantic (embedding) information.
        """
        if not self.helix:
            return None

        cluster = self.helix.recall_cluster(cluster_id, mind_name)
        if not cluster:
            return None

        # Enrich cards with tensor embeddings
        enriched_cards = []
        for card in cluster.get('cards', []):
            card_id = card.get('id')
            tensor_id = self._card_to_tensor.get(card_id)

            embedding = None
            if tensor_id and self.tensor:
                tensor_cell = self.tensor.retrieve(tensor_id)
                if tensor_cell:
                    embedding = tensor_cell.get('embedding')

            enriched_cards.append({
                **card,
                'tensor_id': tensor_id,
                'embedding': embedding,
            })

        return {
            **cluster,
            'cards': enriched_cards,
        }

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _coord_to_mem_type(self, coord: HelixCoordinate) -> str:
        """Map helix coordinate to tensor mem_type."""
        # Based on temporal scale
        if coord.temporal.scale <= 1:
            return 'immediate'
        elif coord.temporal.scale <= 3:
            return 'working'
        elif coord.temporal.scale <= 6:
            return 'episodic'
        else:
            return 'semantic'

    def get_mapping(self, card_id: str) -> Optional[str]:
        """Get tensor cell ID for a helix card ID."""
        return self._card_to_tensor.get(card_id)

    def get_reverse_mapping(self, tensor_id: str) -> Optional[str]:
        """Get helix card ID for a tensor cell ID."""
        return self._tensor_to_card.get(tensor_id)

    def status(self) -> Dict:
        """Get bridge status."""
        return {
            'helix_available': self.helix is not None,
            'tensor_available': self.tensor is not None,
            'is_gpu': hasattr(self.tensor, 'is_gpu') and self.tensor.is_gpu if self.tensor else False,
            'mappings': len(self._card_to_tensor),
            'stats': self._stats.copy(),
        }


# ==============================================================================
# SINGLETON AND FACTORY
# ==============================================================================

_global_bridge: Optional[HelixTensorBridge] = None


def get_helix_tensor_bridge() -> HelixTensorBridge:
    """Get the global helix-tensor bridge singleton."""
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = HelixTensorBridge()
    return _global_bridge


def set_helix_tensor_bridge(bridge: HelixTensorBridge) -> None:
    """Set the global helix-tensor bridge."""
    global _global_bridge
    _global_bridge = bridge


def wire_helix_to_tensor() -> HelixTensorBridge:
    """
    Create and wire the helix-tensor bridge.

    Call this during system boot to enable dual-system memory.
    """
    bridge = get_helix_tensor_bridge()

    if bridge.helix and bridge.tensor:
        print("[HelixTensorBridge] Dual-system memory enabled")
        print(f"  Helix: HelixMemoryCoordinator")
        print(f"  Tensor: {type(bridge.tensor).__name__}")
        if hasattr(bridge.tensor, 'device'):
            print(f"  Device: {bridge.tensor.device}")
    elif bridge.helix:
        print("[HelixTensorBridge] Helix-only mode (no GPU tensor)")
    elif bridge.tensor:
        print("[HelixTensorBridge] Tensor-only mode (no helix)")
    else:
        print("[HelixTensorBridge] WARNING: No memory systems available")

    return bridge


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Mapping functions
    'helix_to_tensor_position',
    'tensor_to_helix_position',
    # Bridge class
    'HelixTensorBridge',
    # Singleton access
    'get_helix_tensor_bridge',
    'set_helix_tensor_bridge',
    'wire_helix_to_tensor',
    # Constants
    'SEMANTIC_TO_PLANE',
    'PLANE_TO_INDEX',
]


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== HELIX-TENSOR BRIDGE TEST ===\n")

    # Create bridge
    bridge = wire_helix_to_tensor()
    print(f"\nBridge status: {bridge.status()}\n")

    # Test coordinate mapping
    print("--- Testing coordinate mapping ---")
    coord = HelixCoordinate(
        affect=AffectCoordinate(domain=1, valence=7, intensity=5),  # Joy
        semantic=SemanticCoordinate(domain=6, subdomain=2, detail=0),  # Technology
        temporal=TemporalCoordinate(scale=2, recurrence=0, decay=5),  # Session
    )
    plane, channel = helix_to_tensor_position(coord)
    print(f"Helix coordinate: {coord}")
    print(f"Tensor position: plane={plane}, channel={channel}")

    # Reverse mapping
    affect_d, semantic_d, semantic_sub = tensor_to_helix_position(plane, channel)
    print(f"Reverse: affect_domain={affect_d}, semantic_domain={semantic_d}, subdomain={semantic_sub}")

    # Test dual storage
    if bridge.helix and bridge.tensor:
        print("\n--- Testing dual storage ---")
        card_id, tensor_id = bridge.store(
            content={"message": "Testing helix-tensor bridge", "data": [1, 2, 3]},
            coord=coord,
            owner_mind="ClaudeFairy",
            ownership_level=OwnershipLevel.SYSTEM,
            tags=["test", "bridge"],
        )
        print(f"Stored - helix: {card_id}, tensor: {tensor_id}")

        # Test helix query
        print("\n--- Testing helix query ---")
        results = bridge.query_by_helix(
            mind_name="ClaudeFairy",
            semantic_domain=6,  # Technology
            k=5,
        )
        print(f"Helix query found {len(results)} results")

        # Test similarity query
        print("\n--- Testing similarity query ---")
        results = bridge.query_by_similarity(
            query_content="helix tensor memory test",
            top_k=5,
        )
        print(f"Similarity query found {len(results)} results")

    print(f"\nFinal status: {bridge.status()}")
