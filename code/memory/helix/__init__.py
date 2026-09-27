"""
Helix Memory System - Triple-Helix Dewey Decimal Coordinates
============================================================

Memory cards cataloged like a Dewey decimal library with THREE dimensions:
  - Affect (emotional dimension 0-999)
  - Semantic (conceptual dimension 0-999)
  - Temporal (time dimension 0-999)

A 9-digit address: AAA.SSS.TTT
  Example: 127.153.325

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

from .dimensions import (
    # Enums
    AffectDomain,
    SemanticDomain,
    TemporalScale,
    LinkType,
    # Coordinates
    AffectCoordinate,
    SemanticCoordinate,
    TemporalCoordinate,
    HelixCoordinate,
    # Links and structures
    CardLink,
    MemoryChain,
    CardCluster,
    # Index
    HelixIndex,
)

from .ownership import (
    # Enums
    OwnershipLevel,
    UserRole,
    # Data classes
    HumanUser,
    Foundation,
    OwnershipContext,
    # Registry
    OwnershipRegistry,
)

from .coordinator import (
    TracerBatch,
    HelixMemoryCoordinator,
    get_helix_coordinator,
    set_helix_coordinator,
)

__all__ = [
    # Dimension Enums
    "AffectDomain",
    "SemanticDomain",
    "TemporalScale",
    "LinkType",
    # Coordinates
    "AffectCoordinate",
    "SemanticCoordinate",
    "TemporalCoordinate",
    "HelixCoordinate",
    # Links and structures
    "CardLink",
    "MemoryChain",
    "CardCluster",
    # Index
    "HelixIndex",
    # Ownership Enums
    "OwnershipLevel",
    "UserRole",
    # Ownership classes
    "HumanUser",
    "Foundation",
    "OwnershipContext",
    "OwnershipRegistry",
]
