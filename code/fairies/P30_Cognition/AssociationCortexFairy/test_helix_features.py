"""
Test suite for helix_features.py - Triple Helix to Association Cortex bridge.

TDD: Write tests first, then implementation.
"""

import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.helix_features import (
    helix_to_features,
    helix_edge_weight,
)
from fairies.P10_Memory.triple_helix_srm_memory.helix_dimensions import (
    HelixCoordinate,
    AffectCoordinate,
    AffectDomain,
    SemanticCoordinate,
    SemanticDomain,
    TemporalCoordinate,
    TemporalScale,
)


def test_helix_to_features():
    """HelixCoordinate should convert to node features dict."""
    # Using actual API: domain=int(0-9), valence=int(0-9), intensity=int(0-9)
    coord = HelixCoordinate(
        affect=AffectCoordinate(
            domain=AffectDomain.JOY.value,  # 1
            valence=7,
            intensity=5,
        ),
        semantic=SemanticCoordinate(
            domain=SemanticDomain.SCIENCE.value,  # 5
            subdomain=0,
            detail=0,
        ),
        temporal=TemporalCoordinate(
            scale=TemporalScale.DAILY.value,  # 3
            recurrence=0,
            decay=0,
        ),
    )
    features = helix_to_features(coord)

    assert "helix_affect" in features
    assert "helix_semantic" in features
    assert "helix_temporal" in features
    assert features["helix_affect"]["domain"] == "JOY"
    assert features["helix_affect"]["intensity"] == 5
    assert features["helix_semantic"]["domain"] == "SCIENCE"
    assert features["helix_temporal"]["scale"] == "DAILY"


def test_helix_edge_weight_same_domain():
    """Concepts in same affect domain should have stronger edge weight."""
    coord1 = HelixCoordinate(
        affect=AffectCoordinate(
            domain=AffectDomain.JOY.value,  # 1
            valence=5,
            intensity=5,
        ),
        semantic=SemanticCoordinate(
            domain=SemanticDomain.SCIENCE.value,
            subdomain=0,
            detail=0,
        ),
        temporal=TemporalCoordinate(
            scale=TemporalScale.DAILY.value,
            recurrence=0,
            decay=5,
        ),
    )
    coord2 = HelixCoordinate(
        affect=AffectCoordinate(
            domain=AffectDomain.JOY.value,  # Same affect domain
            valence=7,
            intensity=7,
        ),
        semantic=SemanticCoordinate(
            domain=SemanticDomain.ARTS.value,  # Different semantic
            subdomain=0,
            detail=0,
        ),
        temporal=TemporalCoordinate(
            scale=TemporalScale.WEEKLY.value,  # Different temporal
            recurrence=0,
            decay=5,
        ),
    )

    weight = helix_edge_weight(coord1, coord2)
    assert weight >= 0.5, f"Same affect domain should produce weight >= 0.5, got {weight}"


def test_helix_edge_weight_different_domain():
    """Concepts in different affect domains should have weaker edge weight."""
    coord1 = HelixCoordinate(
        affect=AffectCoordinate(
            domain=AffectDomain.JOY.value,  # 1
            valence=5,
            intensity=5,
        ),
        semantic=SemanticCoordinate(
            domain=SemanticDomain.SCIENCE.value,
            subdomain=0,
            detail=0,
        ),
        temporal=TemporalCoordinate(
            scale=TemporalScale.DAILY.value,
            recurrence=0,
            decay=5,
        ),
    )
    coord2 = HelixCoordinate(
        affect=AffectCoordinate(
            domain=AffectDomain.FEAR.value,  # 3 - different affect domain
            valence=5,
            intensity=5,
        ),
        semantic=SemanticCoordinate(
            domain=SemanticDomain.SCIENCE.value,  # Same semantic
            subdomain=0,
            detail=0,
        ),
        temporal=TemporalCoordinate(
            scale=TemporalScale.DAILY.value,  # Same temporal
            recurrence=0,
            decay=5,
        ),
    )

    weight = helix_edge_weight(coord1, coord2)
    assert weight < 0.5, f"Different affect domains should produce weight < 0.5, got {weight}"


if __name__ == "__main__":
    test_helix_to_features()
    print("[OK] test_helix_to_features passed")

    test_helix_edge_weight_same_domain()
    print("[OK] test_helix_edge_weight_same_domain passed")

    test_helix_edge_weight_different_domain()
    print("[OK] test_helix_edge_weight_different_domain passed")

    print("\n=== All tests passed! ===")
