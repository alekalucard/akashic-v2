"""
Integration Module - Cross-System Cognitive Operations

This module contains systems that span multiple planes:
- GPU acceleration for concept graphs
- Neural binding operations
- Cross-plane coordination

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

from .gpu_concept_graph import (
    GPUConceptGraph,
    GPUGraphStats,
    get_gpu_concept_graph,
    gpu_spread_activation,
    has_gpu_support,
)

__all__ = [
    "GPUConceptGraph",
    "GPUGraphStats",
    "get_gpu_concept_graph",
    "gpu_spread_activation",
    "has_gpu_support",
]
