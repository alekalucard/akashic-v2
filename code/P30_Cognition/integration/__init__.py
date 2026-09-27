"""
P30_Cognition Integration Module

Contains cortex fairies that integrate multiple cognitive processes:
- AssociationCortexFairy: Semantic binding and concept graphs
- (Future) ManifoldConstrainedCortex: Constraint-based reasoning
"""

from .association_cortex_fairy import (
    AssociationCortexFairyStub,
    ConceptGraph,
    get_association_cortex_fairy,
    set_association_cortex_fairy,
)

__all__ = [
    "AssociationCortexFairyStub",
    "ConceptGraph",
    "get_association_cortex_fairy",
    "set_association_cortex_fairy",
]
