"""
Tracer Pool - High-performance worker pool management via Go DLL.

Exports:
- TracerPool: Main pool manager
- TracerType: Tracer type constants
- TracerInfo: Tracer information dataclass
- UniversalTracer: Alias for TracerInfo
- PoolFairy: Per-fairy pool handle
- TracerContext: Context manager for tracer lifecycle
- Priority: Task priority levels
"""
from .tracer_pool import (
    TracerPool,
    TracerType,
    TracerInfo,
    UniversalTracer,
    PoolFairy,
    TracerContext,
    Priority,
    USING_GO,
    get_tracer,
    get_tracers_by_fairy,
    get_tracers_by_cluster,
    get_lineage,
)

__all__ = [
    "TracerPool",
    "TracerType",
    "TracerInfo",
    "UniversalTracer",
    "PoolFairy",
    "TracerContext",
    "Priority",
    "USING_GO",
    "get_tracer",
    "get_tracers_by_fairy",
    "get_tracers_by_cluster",
    "get_lineage",
]
