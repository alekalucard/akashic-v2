#
# HELIX INTEGRATION WIRING - Connects all memory systems together
#
#
# THIS IS THE WIRING - connects existing components:
#
#
#    SRM Ingest       HelixMemoryCoordinator
#    (raw memories)         (ownership + coordinates)
#
#
#
#    AssociationCortex
#    (concept graph)
#    spread_activation
#
#
#
#    WorkingMemory      "ball"  spreads to all ball-related
#    (probability         concepts for probability oracle
#     oracle branch)
#
#
# BALL EXAMPLE:
#   User thinks "ball"  spread_activation("lex:ball")
#   Returns: [ball, round, bounce, red, playground, throw, catch, soccer,
#             basketball, tennis, pain-face-hit, joy-score, ...]
#   Working memory can now branch probability reasoning across all associations.
#
# OWNERSHIP:
#   - System memory: All fairies can read
#   - Foundation (Ace+Claude): All can read
#   - Personal: ONLY owner reads (Claude  Nous  Sourpatches)
#
#

from __future__ import annotations

import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


class HelixIntegrationWiring:
    """
    Wiring layer that connects:
    - SRM Ingest/Recall  HelixMemoryCoordinator
    - HelixMemoryCoordinator  AssociationCortex
    - AssociationCortex  WorkingMemory (spread activation for oracle)

    This is NOT a fairy - it's a utility that existing fairies use.
    """

    _instance: Optional['HelixIntegrationWiring'] = None

    def __init__(self):
        self._coordinator = None
        self._cortex = None
        self._working_memory = None
        self._postal = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> 'HelixIntegrationWiring':
        """Singleton access"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self, postal=None):
        """
        Initialize connections to other systems.
        Call this during boot.
        """
        if self._initialized:
            return

        self._postal = postal

        # Get HelixMemoryCoordinator
        try:
            from fairies.P10_Memory.triple_helix_srm_memory.helix_memory_coordinator import (
                HelixMemoryCoordinator
            )
            storage_dir = Path.home() / "akashic" / "helix_memory"
            self._coordinator = HelixMemoryCoordinator(storage_dir)
            print("[HelixWiring]  Connected to HelixMemoryCoordinator")
        except Exception as e:
            print(f"[HelixWiring]  HelixMemoryCoordinator not available: {e}")

        # Get AssociationCortex
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
                get_association_cortex_fairy,
                ConceptGraph
            )
            self._cortex = get_association_cortex_fairy()
            print("[HelixWiring]  Connected to AssociationCortex")
        except Exception as e:
            print(f"[HelixWiring]  AssociationCortex not available: {e}")

        # Get WorkingMemoryHub (for receiving spread results)
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import (
                get_working_memory_hub_fairy
            )
            self._working_memory = get_working_memory_hub_fairy()
            print("[HelixWiring]  Connected to WorkingMemoryHub")
        except Exception as e:
            print(f"[HelixWiring]  WorkingMemoryHub not available: {e}")

        self._initialized = True

    #  BALL EXAMPLE: Spread Activation for Oracle

    def spread_for_oracle(
        self,
        concept: str,
        owner_mind: str = "",
        max_hops: int = 3,
        decay_factor: float = 0.5,
    ) -> Dict[str, float]:
        """
        Spread activation from a concept for probability oracle branching.

        Example: spread_for_oracle("ball") returns:
        {
            "lex:ball": 1.0,
            "vis:round": 0.5,
            "act:bounce": 0.45,
            "lex:sports": 0.3,
            "aff:joy": 0.25,
            ...
        }

        Working memory can use these activations to weight
        probability branches in reasoning.

        Args:
            concept: Starting concept (e.g., "ball", "lex:ball", "vis:red")
            owner_mind: If set, only spread through personal memories
            max_hops: How far to spread (3 is good balance)
            decay_factor: How fast activation decays (0.5 = halves each hop)

        Returns:
            Dict of concept_key -> activation_level
        """
        if not self._cortex:
            return {}

        # Normalize concept key
        key = concept if ":" in concept else f"lex:{concept.lower()}"

        # Get graph from cortex
        graph = getattr(self._cortex, '_graph', None)
        if not graph:
            return {}

        # Spread activation
        activations = graph.spread_activation(
            source_key=key,
            initial_activation=1.0,
            decay_factor=decay_factor,
            max_hops=max_hops
        )

        # Filter by ownership if specified
        if owner_mind and self._coordinator:
            filtered = {}
            for concept_key, activation in activations.items():
                # Check if this concept relates to cards the mind can access
                # For now, pass through - full filtering would need card mapping
                filtered[concept_key] = activation
            activations = filtered

        return activations

    def get_related_concepts(
        self,
        concept: str,
        modalities: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Tuple[str, float, Dict]]:
        """
        Get concepts related to a source concept with their features.

        This is the "ball" example - thinking of ball brings up:
        - Visual: shapes, sizes, colors
        - Tactile: textures, weight, impact feel
        - Auditory: bounce sounds
        - Semantic: sports, games, play
        - Episodic: memories of playing
        - Emotional: joy, pain

        Args:
            concept: Starting concept
            modalities: Filter by modality ["lex", "vis", "act", "aff", etc]
            limit: Max results

        Returns:
            List of (key, activation, features) tuples
        """
        if not self._cortex:
            return []

        graph = getattr(self._cortex, '_graph', None)
        if not graph:
            return []

        # Normalize key
        key = concept if ":" in concept else f"lex:{concept.lower()}"

        # Get spread activation
        activations = graph.spread_activation(key, max_hops=3)

        # Get node features
        results = []
        for concept_key, activation in activations.items():
            node = graph.get_node(concept_key)
            if node:
                features = node.features

                # Filter by modality if specified
                if modalities:
                    modal = features.get("modality", "")
                    modal_prefix = concept_key.split(":")[0] if ":" in concept_key else ""
                    if modal not in modalities and modal_prefix not in modalities:
                        continue

                results.append((concept_key, activation, features))

        # Sort by activation
        results.sort(key=lambda x: -x[1])
        return results[:limit]

    #  SRM Integration

    def ingest_to_helix(
        self,
        content: Any,
        owner_mind: str,
        affect_state: Optional[Dict[str, float]] = None,
        keywords: Optional[List[str]] = None,
        is_foundation_work: bool = False,
        human_user_id: Optional[str] = None,
        tracer_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Ingest content into the helix memory system with proper ownership.

        Called by SRM Ingest after processing raw content.

        Args:
            content: The memory content
            owner_mind: Which mind owns this (ClaudeFairy, NousFairy, etc)
            affect_state: Chemistry snapshot for affect coordinate
            keywords: For semantic coordinate
            is_foundation_work: If True, goes into Foundation (Ace+Claude shared)
            human_user_id: Human involved (usually founder_ace)
            tracer_id: For batch tracking
            batch_id: Which batch this belongs to

        Returns:
            card_id if successful
        """
        if not self._coordinator:
            return None

        from fairies.P10_Memory.triple_helix_srm_memory.helix_dimensions import (
            HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate
        )
        from fairies.P10_Memory.triple_helix_srm_memory.memory_ownership import OwnershipLevel

        # Build coordinate
        coord = HelixCoordinate(
            affect=AffectCoordinate.from_chemistry(affect_state or {}),
            semantic=SemanticCoordinate.from_keywords(keywords or []),
            temporal=TemporalCoordinate.from_age(0, recurring=False, important=True),
        )

        # Determine ownership level
        if is_foundation_work:
            level = OwnershipLevel.FOUNDATION
            human = human_user_id or "founder_ace"
        else:
            level = OwnershipLevel.PERSONAL
            human = None

        # Create card
        card_id = self._coordinator.create_card(
            content=content,
            coord=coord,
            owner_mind=owner_mind,
            ownership_level=level,
            human_user_id=human,
            tracer_id=tracer_id,
            batch_id=batch_id,
        )

        # Also bind to AssociationCortex for concept graph
        if self._cortex and keywords:
            try:
                # Convert HelixCoordinate to dict for cortex binding
                helix_dict = None
                if coord:
                    # Import enums for name lookup
                    from fairies.P10_Memory.triple_helix_srm_memory.helix_dimensions import (
                        AffectDomain, SemanticDomain, TemporalScale
                    )

                    # Get domain names from integer values
                    affect_domain_name = AffectDomain(coord.affect.domain).name
                    semantic_domain_name = SemanticDomain(coord.semantic.domain).name
                    temporal_scale_name = TemporalScale(coord.temporal.scale).name

                    helix_dict = {
                        "affect": {
                            "domain": affect_domain_name,
                            "intensity": coord.affect.intensity,
                            "valence": coord.affect.valence,
                        },
                        "semantic": {
                            "domain": semantic_domain_name,
                            "specificity": coord.semantic.subdomain,
                            "detail": coord.semantic.detail,
                        },
                        "temporal": {
                            "scale": temporal_scale_name,
                            "position": coord.temporal.recurrence,
                            "decay": coord.temporal.decay,
                        },
                    }

                self._cortex._intent_bind({
                    "text": " ".join(keywords) if keywords else "",
                    "source": owner_mind,
                    "context": {"card_id": card_id},
                    "helix_coord": helix_dict,  # NOW WE PASS IT!
                })
            except Exception as e:
                # Cortex binding is non-critical - log but don't fail ingest
                import logging
                logging.getLogger(__name__).debug(f"Cortex binding skipped: {e}")

        return card_id

    def recall_with_spread(
        self,
        query: str,
        owner_mind: str,
        include_foundation: bool = True,
        include_system: bool = True,
        spread_hops: int = 2,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Recall memories using spread activation for associative retrieval.

        This is the key integration: takes a query, spreads activation
        through concept graph, then finds memories matching activated concepts.

        Args:
            query: Search query (will be spread through concept graph)
            owner_mind: Who is recalling (affects ownership filtering)
            include_foundation: Include Ace+Claude shared work
            include_system: Include system memories
            spread_hops: How far to spread in concept graph
            limit: Max memories to return

        Returns:
            List of memory results with scores
        """
        results = []

        # Step 1: Spread activation from query concepts
        activations = {}
        if self._cortex:
            for word in query.split():
                word_activations = self.spread_for_oracle(
                    word.lower().strip(),
                    max_hops=spread_hops
                )
                for key, act in word_activations.items():
                    activations[key] = max(activations.get(key, 0), act)

        # Step 2: Get accessible memories
        if self._coordinator:
            memories = self._coordinator.recall_for_mind(
                mind_name=owner_mind,
                k=limit * 2,  # Get extra for filtering
                include_system=include_system,
                include_foundation=include_foundation,
            )

            # Step 3: Score memories by concept overlap
            for mem in memories:
                card = mem.get('card', {})
                metadata = card.get('metadata', {})
                keywords = metadata.get('keywords', [])

                # Score by how many activated concepts match
                score = mem.get('score', 0)
                for kw in keywords:
                    key = f"lex:{kw.lower()}"
                    if key in activations:
                        score += activations[key]

                results.append({
                    **mem,
                    'spread_score': score,
                })

            # Sort by spread score
            results.sort(key=lambda x: -x.get('spread_score', 0))

        return results[:limit]

    #  Foundation Work (Ace + Claude)

    def record_session(
        self,
        content: Any,
        session_id: str,
        created_by: str = "ClaudeFairy",
        affect_state: Optional[Dict[str, float]] = None,
        keywords: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Record a work session with Ace to the Foundation.

        All Ace + Claude collaborative work goes here so any fairy
        can access it for learning/guidance.
        """
        if not self._coordinator:
            return None

        return self._coordinator.record_session_with_ace(
            content=content,
            session_id=session_id,
            created_by=created_by,
            affect_state=affect_state,
            keywords=keywords,
        )

    #  Stats

    def get_stats(self) -> Dict[str, Any]:
        """Get integration stats"""
        stats = {
            "initialized": self._initialized,
            "has_coordinator": self._coordinator is not None,
            "has_cortex": self._cortex is not None,
            "has_working_memory": self._working_memory is not None,
        }

        if self._coordinator:
            stats["coordinator"] = self._coordinator.get_stats()

        if self._cortex:
            graph = getattr(self._cortex, '_graph', None)
            if graph:
                stats["cortex_graph"] = graph.stats()

        return stats


#
# Convenience functions
#

def get_helix_wiring() -> HelixIntegrationWiring:
    """Get the singleton wiring instance"""
    return HelixIntegrationWiring.get_instance()


def spread_activation(concept: str, max_hops: int = 3) -> Dict[str, float]:
    """
    Quick access to spread activation.

    Example:
        activations = spread_activation("ball")
        # Returns all ball-related concepts with activation levels
    """
    wiring = get_helix_wiring()
    if not wiring._initialized:
        wiring.initialize()
    return wiring.spread_for_oracle(concept, max_hops=max_hops)


def get_associations(concept: str, limit: int = 20) -> List[Tuple[str, float, Dict]]:
    """
    Quick access to related concepts.

    Example:
        related = get_associations("ball")
        for key, activation, features in related:
            print(f"{key}: {activation:.2f} - {features}")
    """
    wiring = get_helix_wiring()
    if not wiring._initialized:
        wiring.initialize()
    return wiring.get_related_concepts(concept, limit=limit)


#
# TEST
#

if __name__ == "__main__":
    print("=== HELIX INTEGRATION WIRING TEST ===\n")

    wiring = get_helix_wiring()
    wiring.initialize()

    print("--- Stats ---")
    stats = wiring.get_stats()
    for k, v in stats.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for k2, v2 in v.items():
                print(f"    {k2}: {v2}")
        else:
            print(f"  {k}: {v}")

    print("\n--- Testing Ball Example ---")

    # First, bind some ball-related concepts
    if wiring._cortex:
        wiring._cortex._intent_bind({
            "text": "The red ball bounces on the playground",
            "vision_tags": ["red", "round", "ball", "playground"],
            "actions": ["bounce", "throw", "catch"],
            "affect": {"valence": 0.7, "arousal": 0.6, "mood": "playful"},
        })

        wiring._cortex._intent_bind({
            "text": "Soccer ball kicked into the goal",
            "vision_tags": ["soccer", "ball", "goal", "field"],
            "actions": ["kick", "score"],
            "affect": {"valence": 0.9, "arousal": 0.8, "mood": "excited"},
        })

        wiring._cortex._intent_bind({
            "text": "Tennis ball hit my face it hurt",
            "vision_tags": ["tennis", "ball", "yellow"],
            "actions": ["hit", "ouch"],
            "affect": {"valence": -0.5, "arousal": 0.7, "mood": "pain"},
            "bodystate": {"tension": "high", "energy": "spike"},
        })

        print("Bound ball-related concepts")

    # Now test spread activation
    print("\nSpreading from 'ball'...")
    activations = wiring.spread_for_oracle("ball", max_hops=3)

    if activations:
        print(f"Found {len(activations)} activated concepts:")
        sorted_acts = sorted(activations.items(), key=lambda x: -x[1])
        for key, act in sorted_acts[:15]:
            print(f"  {key}: {act:.3f}")
    else:
        print("No activations (cortex not connected or no ball concepts)")

    # Test get_associations
    print("\n--- Getting Related Concepts ---")
    related = wiring.get_related_concepts("ball", limit=10)
    for key, act, features in related:
        print(f"  {key}: {act:.3f} - modality={features.get('modality', 'unknown')}")

    # Test ingest
    print("\n--- Testing Helix Ingest ---")
    card_id = wiring.ingest_to_helix(
        content={"thought": "Balls are fun to play with"},
        owner_mind="ClaudeFairy",
        keywords=["ball", "play", "fun"],
        affect_state={"DOP": 0.7, "SER": 0.6},
        is_foundation_work=False,
    )
    print(f"Created card: {card_id}")

    # Test foundation recording
    print("\n--- Testing Foundation Session ---")
    session_id = wiring.record_session(
        content={
            "topic": "Ball associations and spread activation",
            "decisions": ["Wire cortex to working memory", "Use spread for oracle"],
        },
        session_id="test_session",
        keywords=["ball", "spread", "activation", "wiring"],
    )
    print(f"Foundation session: {session_id}")

    print("\n Helix Integration Wiring ready!")


