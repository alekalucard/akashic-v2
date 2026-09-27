"""
Memory Module - P10 Plane Implementation
=========================================

GPU-accelerated tensor memory for the Akashic system.

4D Tensor Structure:
    [Plane, Channel, Time, Embedding]
    [7,     77,      1000, 128      ]  = 69.3M parameters

Triple Helix Memory:
    9-digit Dewey Decimal coordinates (AAA.SSS.TTT)
    - Affect (emotional dimension)
    - Semantic (conceptual dimension)
    - Temporal (time dimension)

Features:
- Per-plane thread isolation (parallel access)
- GPU cosine similarity search
- Batch memory decay
- Fairy wiring (remember/recall/search methods)
- Helix coordinate system (human-readable addressing)
- Ownership model (SYSTEM, FOUNDATION, PERSONAL, SHARED)

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

# Tensor Memory Fabric (GPU-accelerated)
from .tensor_memory_fabric import (
    MemoryCell,
    PlaneSlice,
    TensorMemoryFabric,
    GPUTensorMemoryFabric,
    create_tensor_fabric,
    get_global_tensor_fabric,
    register_tensor_provider,
    wire_fairy_to_tensor,
    wire_self,
    give_tensor_memory,
)

# Triple Helix Memory System
try:
    from .helix import (
        # Dimension Enums
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
        # Ownership
        OwnershipLevel,
        UserRole,
        HumanUser,
        Foundation,
        OwnershipContext,
        OwnershipRegistry,
        # Coordinator
        TracerBatch,
        HelixMemoryCoordinator,
        get_helix_coordinator,
        set_helix_coordinator,
    )
    HELIX_AVAILABLE = True
except ImportError as e:
    HELIX_AVAILABLE = False
    print(f"[Memory] Helix system not available: {e}")

# Helix-Tensor Bridge
try:
    from .helix_tensor_bridge import (
        HelixTensorBridge,
        helix_to_tensor_position,
        tensor_to_helix_position,
        get_helix_tensor_bridge,
        set_helix_tensor_bridge,
        wire_helix_to_tensor,
    )
    BRIDGE_AVAILABLE = True
except ImportError as e:
    BRIDGE_AVAILABLE = False
    print(f"[Memory] Helix-Tensor bridge not available: {e}")

__all__ = [
    # Tensor Memory
    "MemoryCell",
    "PlaneSlice",
    "TensorMemoryFabric",
    "GPUTensorMemoryFabric",
    "create_tensor_fabric",
    "get_global_tensor_fabric",
    "register_tensor_provider",
    "wire_fairy_to_tensor",
    "wire_self",
    "give_tensor_memory",
]

# Add helix exports if available
if HELIX_AVAILABLE:
    __all__.extend([
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
        # Ownership
        "OwnershipLevel",
        "UserRole",
        "HumanUser",
        "Foundation",
        "OwnershipContext",
        "OwnershipRegistry",
        # Coordinator
        "TracerBatch",
        "HelixMemoryCoordinator",
        "get_helix_coordinator",
        "set_helix_coordinator",
    ])

# Add bridge exports if available
if BRIDGE_AVAILABLE:
    __all__.extend([
        "HelixTensorBridge",
        "helix_to_tensor_position",
        "tensor_to_helix_position",
        "get_helix_tensor_bridge",
        "set_helix_tensor_bridge",
        "wire_helix_to_tensor",
    ])

# Per-Fairy SRM Cluster System
try:
    from .fairy_srm_cluster import (
        FairySRMCluster,
        SRMClusterMixin,
        create_fairy_cluster,
        PLANE_TO_SEMANTIC,
    )
    CLUSTER_AVAILABLE = True
    __all__.extend([
        "FairySRMCluster",
        "SRMClusterMixin",
        "create_fairy_cluster",
        "PLANE_TO_SEMANTIC",
    ])
except ImportError as e:
    CLUSTER_AVAILABLE = False
    print(f"[Memory] Fairy SRM cluster not available: {e}")
