"""
Helix Coordinate -> Association Cortex Feature Bridge

Converts triple helix coordinates into ConceptNode features and edge weights.
The triple helix represents memory across three axes:
  - Affect: Emotional dimension (domain, valence, intensity)
  - Semantic: Conceptual dimension (domain, subdomain, detail)
  - Temporal: Time dimension (scale, recurrence, decay)

This bridge allows the Association Cortex to leverage helix coordinates
for concept binding and edge weight calculations, enabling emotionally-
resonant memory retrieval and association.

Philosophy: Same affect domain produces stronger edges - emotional resonance
creates tighter conceptual binding.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fairies.P10_Memory.triple_helix_srm_memory.helix_dimensions import HelixCoordinate

# Import the enums for reverse lookup
from fairies.P10_Memory.triple_helix_srm_memory.helix_dimensions import (
    AffectDomain,
    SemanticDomain,
    TemporalScale,
)


def _domain_name(domain_int: int, enum_class) -> str:
    """Convert domain integer to enum name."""
    for member in enum_class:
        if member.value == domain_int:
            return member.name
    return "UNKNOWN"


def helix_to_features(coord: "HelixCoordinate") -> Dict[str, Any]:
    """
    Convert a HelixCoordinate to ConceptNode features dict.

    Args:
        coord: A HelixCoordinate from the triple helix memory system

    Returns:
        A dict with helix_affect, helix_semantic, helix_temporal, and helix_vector
    """
    return {
        "helix_affect": {
            "domain": _domain_name(coord.affect.domain, AffectDomain),
            "valence": coord.affect.valence,
            "intensity": coord.affect.intensity,
            "code": coord.affect.code,
        },
        "helix_semantic": {
            "domain": _domain_name(coord.semantic.domain, SemanticDomain),
            "subdomain": coord.semantic.subdomain,
            "detail": coord.semantic.detail,
            "code": coord.semantic.code,
        },
        "helix_temporal": {
            "scale": _domain_name(coord.temporal.scale, TemporalScale),
            "recurrence": coord.temporal.recurrence,
            "decay": coord.temporal.decay,
            "code": coord.temporal.code,
        },
        # Normalized vector for similarity calculations (0-1 range)
        "helix_vector": [
            coord.affect.code / 999.0,
            coord.semantic.code / 999.0,
            coord.temporal.code / 999.0,
        ],
    }


def helix_edge_weight(
    coord1: "HelixCoordinate",
    coord2: "HelixCoordinate",
    affect_weight: float = 2.5,
    semantic_weight: float = 1.0,
    temporal_weight: float = 0.5,
) -> float:
    """
    Calculate edge weight based on helix coordinate similarity.

    Same affect domain produces stronger edges - emotional resonance
    creates tighter conceptual binding. This reflects how memories
    with similar emotional signatures are more readily associated.

    Args:
        coord1: First helix coordinate
        coord2: Second helix coordinate
        affect_weight: Weight multiplier for affect similarity (default 1.5)
        semantic_weight: Weight multiplier for semantic similarity (default 1.0)
        temporal_weight: Weight multiplier for temporal similarity (default 0.8)

    Returns:
        Edge weight between 0.0 and 1.0, where higher = stronger connection
    """
    # Affect similarity - same domain gives bonus (emotional resonance)
    if coord1.affect.domain == coord2.affect.domain:
        # Same affect domain: high baseline + distance-based refinement
        valence_diff = abs(coord1.affect.valence - coord2.affect.valence) / 9.0
        intensity_diff = abs(coord1.affect.intensity - coord2.affect.intensity) / 9.0
        affect_sim = 1.0 - (valence_diff + intensity_diff) / 2.0
    else:
        # Different affect domains: significantly lower baseline
        # Emotional dissonance creates weaker associations
        affect_sim = 0.15

    # Semantic similarity - same domain gives bonus
    if coord1.semantic.domain == coord2.semantic.domain:
        subdomain_diff = abs(coord1.semantic.subdomain - coord2.semantic.subdomain) / 9.0
        detail_diff = abs(coord1.semantic.detail - coord2.semantic.detail) / 9.0
        semantic_sim = 1.0 - (subdomain_diff + detail_diff) / 2.0
    else:
        # Different semantic domains: lower baseline
        semantic_sim = 0.3

    # Temporal similarity - same scale gives bonus
    if coord1.temporal.scale == coord2.temporal.scale:
        recurrence_diff = abs(coord1.temporal.recurrence - coord2.temporal.recurrence) / 9.0
        decay_diff = abs(coord1.temporal.decay - coord2.temporal.decay) / 9.0
        temporal_sim = 1.0 - (recurrence_diff + decay_diff) / 2.0
    else:
        # Different temporal scales: lower baseline
        temporal_sim = 0.4

    # Weighted combination
    total_weight = affect_weight + semantic_weight + temporal_weight
    similarity = (
        affect_sim * affect_weight +
        semantic_sim * semantic_weight +
        temporal_sim * temporal_weight
    ) / total_weight

    return similarity


def helix_edge_weight_from_features(
    features_a: Dict[str, Any],
    features_b: Dict[str, Any],
) -> float:
    """
    Calculate edge weight from node features (after helix was attached).

    Returns weight between 0.1 (very different) and 1.0 (identical helix).
    """
    helix_a = features_a.get("helix_affect", {})
    helix_b = features_b.get("helix_affect", {})

    if not helix_a or not helix_b:
        return 0.25  # Default weight if no helix info

    # Same affect domain = emotional resonance
    if helix_a.get("domain") == helix_b.get("domain"):
        # Intensity similarity bonus
        int_a = helix_a.get("intensity", 500)
        int_b = helix_b.get("intensity", 500)
        intensity_sim = 1.0 - abs(int_a - int_b) / 999.0
        return 0.5 + 0.5 * intensity_sim  # Range: 0.5 - 1.0
    else:
        return 0.15  # Cross-domain: weak link
