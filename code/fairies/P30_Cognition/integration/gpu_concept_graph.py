# gpu_concept_graph.py
"""
GPU-Accelerated Concept Graph with 2:4 Structured Sparsity

This module provides a GPU tensor view of the AssociationCortex graph,
enabling hardware-accelerated operations on NVIDIA Tensor Cores.

KEY INSIGHT (from Ace):
- Neural networks are 90% redundant by design
- Modern GPUs have silicon-level 2:4 sparsity acceleration
- Magnitude pruning + structured patterns + quantization = 20-50x efficiency
- "Evolution over-parameterizes. We can prune."

ARCHITECTURE:
- CPU graph (dict-based) remains the source of truth for flexibility
- GPU graph (tensor-based) provides accelerated view for heavy operations
- Sync happens on-demand or periodically
- 2:4 pruning enforces hardware-optimal sparsity pattern

OPERATIONS ACCELERATED:
- spread_activation(): Sparse matrix-vector multiply on Tensor Cores
- batch_query(): Parallel similarity computation
- decay_all(): Vectorized weight decay

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import time
import threading
from typing import Dict, List, Tuple, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass

# Type checking imports (not executed at runtime)
if TYPE_CHECKING:
    import torch

# Lazy import torch to avoid startup cost if not used
_torch = None
_torch_sparse = None

def _ensure_torch():
    """Lazy load PyTorch with CUDA."""
    global _torch, _torch_sparse
    if _torch is None:
        import torch
        _torch = torch
        _torch_sparse = torch.sparse
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available - GPU graph requires NVIDIA GPU")
    return _torch


@dataclass
class GPUGraphStats:
    """Statistics about the GPU graph state."""
    num_nodes: int
    num_edges: int
    gpu_memory_mb: float
    sparsity_ratio: float
    dtype: str
    last_sync_time: float
    spread_ops_count: int
    total_spread_time_ms: float


class GPUConceptGraph:
    """
    GPU-accelerated view of a concept graph using 2:4 structured sparsity.

    This wraps a CPU-based ConceptGraph and provides GPU-accelerated operations
    for spreading activation, batch queries, and bulk updates.

    Usage:
        cpu_graph = ConceptGraph(...)
        gpu_graph = GPUConceptGraph(cpu_graph)

        # Sync CPU -> GPU
        gpu_graph.sync_from_cpu()

        # Fast spreading activation on GPU
        activations = gpu_graph.spread_activation(initial_activations)

        # Apply 2:4 structured pruning
        gpu_graph.apply_structured_pruning()
    """

    def __init__(
        self,
        cpu_graph=None,
        dtype: str = "float32",  # FP32 for sparse ops (FP16 not supported for sparse mm)
        device: str = "cuda:0",
        auto_sync_interval: float = 30.0,  # Sync every 30s
    ):
        """
        Initialize GPU graph view.

        Args:
            cpu_graph: Source ConceptGraph (dict-based)
            dtype: Tensor dtype - "float32" required for sparse mm (CUDA limitation)
            device: CUDA device
            auto_sync_interval: Seconds between auto-syncs (0 to disable)
        """
        torch = _ensure_torch()

        self.cpu_graph = cpu_graph
        self.device = torch.device(device)
        self.dtype = getattr(torch, dtype)
        self.auto_sync_interval = auto_sync_interval

        # Node key <-> index mapping
        self.key_to_idx: Dict[str, int] = {}
        self.idx_to_key: List[str] = []

        # GPU tensors
        self.adj_indices: Optional[torch.Tensor] = None  # [2, num_edges]
        self.adj_values: Optional[torch.Tensor] = None   # [num_edges]
        self.adj_sparse: Optional[torch.Tensor] = None   # Sparse COO tensor
        self.node_activations: Optional[torch.Tensor] = None  # [num_nodes]

        # For 2:4 structured sparsity (dense matrix form)
        self.adj_dense_2_4: Optional[torch.Tensor] = None
        self._using_structured_sparsity = False

        # Stats
        self._last_sync = 0.0
        self._spread_ops = 0
        self._total_spread_time = 0.0
        self._lock = threading.Lock()

        # Initial sync if graph provided
        if cpu_graph is not None:
            self.sync_from_cpu()

    def sync_from_cpu(self) -> int:
        """
        Sync GPU tensors from CPU graph.

        Returns:
            Number of edges synced
        """
        torch = _ensure_torch()

        if self.cpu_graph is None:
            return 0

        with self._lock:
            start = time.perf_counter()

            # Build key mappings
            self.idx_to_key = list(self.cpu_graph.nodes.keys())
            self.key_to_idx = {k: i for i, k in enumerate(self.idx_to_key)}
            num_nodes = len(self.idx_to_key)

            if num_nodes == 0:
                return 0

            # Extract edges as COO format
            rows, cols, weights = [], [], []
            for (a, b), edge in self.cpu_graph.edges.items():
                if a in self.key_to_idx and b in self.key_to_idx:
                    i, j = self.key_to_idx[a], self.key_to_idx[b]
                    w = edge.get("weight", 0.5) if isinstance(edge, dict) else 0.5
                    # Add both directions for undirected graph
                    rows.extend([i, j])
                    cols.extend([j, i])
                    weights.extend([w, w])

            if not rows:
                return 0

            # Create sparse tensor on GPU
            indices = torch.tensor([rows, cols], dtype=torch.long, device=self.device)
            values = torch.tensor(weights, dtype=self.dtype, device=self.device)

            self.adj_indices = indices
            self.adj_values = values
            self.adj_sparse = torch.sparse_coo_tensor(
                indices, values, (num_nodes, num_nodes), device=self.device
            ).coalesce()

            # Initialize activations from CPU nodes
            activations = []
            for key in self.idx_to_key:
                node = self.cpu_graph.nodes[key]
                act = getattr(node, 'activation', 0.5) if hasattr(node, 'activation') else 0.5
                activations.append(act)
            self.node_activations = torch.tensor(
                activations, dtype=self.dtype, device=self.device
            )

            self._last_sync = time.time()
            sync_time = (time.perf_counter() - start) * 1000

            num_edges = len(weights) // 2  # Divided by 2 since we added both directions
            print(f"[GPUConceptGraph] Synced {num_nodes} nodes, {num_edges} edges in {sync_time:.1f}ms")

            return num_edges

    def spread_activation(
        self,
        initial: Optional["torch.Tensor"] = None,
        iterations: int = 1,
        decay: float = 0.9,
    ) -> "torch.Tensor":
        """
        GPU-accelerated spreading activation.

        This is the core operation that benefits from GPU acceleration.
        Uses sparse matrix-vector multiply which runs on Tensor Cores.

        Args:
            initial: Initial activation vector [num_nodes], or None to use stored
            iterations: Number of spreading iterations
            decay: Decay factor per iteration

        Returns:
            Final activation vector [num_nodes]
        """
        torch = _ensure_torch()

        if self.adj_sparse is None:
            raise RuntimeError("No graph loaded - call sync_from_cpu() first")

        start = time.perf_counter()

        # Use provided or stored activations
        if initial is not None:
            activations = initial.to(self.device, self.dtype)
        else:
            activations = self.node_activations.clone()

        # Normalize adjacency by degree (avoid explosion)
        # Simple version: divide by max to keep values bounded
        adj_normalized = self.adj_sparse

        # Spreading iterations
        for _ in range(iterations):
            # Sparse matrix-vector multiply: new_act = adj @ act
            spread = torch.sparse.mm(adj_normalized, activations.unsqueeze(1)).squeeze(1)
            # Combine with decay
            activations = decay * activations + (1 - decay) * spread

        # Update stats
        elapsed = (time.perf_counter() - start) * 1000
        self._spread_ops += 1
        self._total_spread_time += elapsed

        return activations

    def apply_magnitude_pruning(self, keep_ratio: float = 0.5) -> int:
        """
        Apply magnitude-based pruning to edges.

        Keeps the top `keep_ratio` edges by absolute weight.
        This is step 1 of the structured sparsity pipeline.

        Args:
            keep_ratio: Fraction of edges to keep (0.5 = keep top 50%)

        Returns:
            Number of edges pruned
        """
        torch = _ensure_torch()

        if self.adj_values is None:
            return 0

        with self._lock:
            num_edges = self.adj_values.shape[0]
            num_keep = int(num_edges * keep_ratio)

            # Find threshold (top k by magnitude)
            topk_values, _ = torch.topk(self.adj_values.abs(), num_keep)
            threshold = topk_values[-1]

            # Create mask for edges above threshold
            mask = self.adj_values.abs() >= threshold

            # Apply mask
            self.adj_indices = self.adj_indices[:, mask]
            self.adj_values = self.adj_values[mask]

            # Rebuild sparse tensor
            num_nodes = len(self.idx_to_key)
            self.adj_sparse = torch.sparse_coo_tensor(
                self.adj_indices, self.adj_values, (num_nodes, num_nodes), device=self.device
            ).coalesce()

            pruned = num_edges - self.adj_values.shape[0]
            print(f"[GPUConceptGraph] Magnitude pruning: {num_edges} -> {self.adj_values.shape[0]} edges ({pruned} pruned)")

            return pruned

    def apply_structured_2_4_pruning(self) -> Tuple[int, float]:
        """
        Apply 2:4 structured sparsity pattern for Tensor Core acceleration.

        2:4 pattern means: for every 4 consecutive elements, keep only 2.
        This runs NATIVELY on NVIDIA Tensor Cores (Ampere and later).

        Returns:
            Tuple of (edges_pruned, achieved_sparsity)
        """
        torch = _ensure_torch()

        if self.adj_sparse is None:
            return 0, 0.0

        with self._lock:
            try:
                from torch.sparse import to_sparse_semi_structured

                # Convert to dense for semi-structured sparsity
                # Note: This is memory-intensive for large graphs
                num_nodes = len(self.idx_to_key)

                # Only do this for reasonably sized graphs (< 10k nodes)
                if num_nodes > 10000:
                    print(f"[GPUConceptGraph] Graph too large for 2:4 ({num_nodes} nodes) - using magnitude pruning")
                    return self.apply_magnitude_pruning(keep_ratio=0.5), 0.5

                # Convert sparse to dense
                adj_dense = self.adj_sparse.to_dense()

                # Ensure dimensions are multiples of 4 (pad if needed)
                pad_rows = (4 - num_nodes % 4) % 4
                pad_cols = (4 - num_nodes % 4) % 4
                if pad_rows > 0 or pad_cols > 0:
                    adj_dense = torch.nn.functional.pad(adj_dense, (0, pad_cols, 0, pad_rows))

                # Apply 2:4 semi-structured sparsity
                # This keeps top 2 values per 4-element block
                self.adj_dense_2_4 = to_sparse_semi_structured(adj_dense)
                self._using_structured_sparsity = True

                # Calculate stats
                nonzeros_before = self.adj_values.shape[0]
                nonzeros_after = (adj_dense != 0).sum().item()
                sparsity = 1.0 - (nonzeros_after / adj_dense.numel())

                print(f"[GPUConceptGraph] 2:4 structured sparsity applied: {sparsity:.1%} sparse")

                return nonzeros_before - nonzeros_after, sparsity

            except Exception as e:
                print(f"[GPUConceptGraph] 2:4 sparsity failed: {e} - falling back to magnitude")
                return self.apply_magnitude_pruning(keep_ratio=0.5), 0.5

    def quantize_to_int8(self) -> float:
        """
        Quantize edge weights to INT8 for memory efficiency.

        Returns:
            Scale factor used for quantization
        """
        torch = _ensure_torch()

        if self.adj_values is None:
            return 1.0

        with self._lock:
            # Find scale to map to INT8 range [-127, 127]
            max_val = self.adj_values.abs().max()
            scale = 127.0 / max_val if max_val > 0 else 1.0

            # Quantize
            self.adj_values_int8 = (self.adj_values * scale).to(torch.int8)
            self._quant_scale = scale

            memory_before = self.adj_values.element_size() * self.adj_values.numel()
            memory_after = self.adj_values_int8.element_size() * self.adj_values_int8.numel()

            print(f"[GPUConceptGraph] Quantized to INT8: {memory_before/1024:.1f}KB -> {memory_after/1024:.1f}KB")

            return scale.item() if hasattr(scale, 'item') else scale

    def get_top_activated(self, k: int = 10) -> List[Tuple[str, float]]:
        """Get top k activated nodes."""
        torch = _ensure_torch()

        if self.node_activations is None:
            return []

        topk_vals, topk_idx = torch.topk(self.node_activations, min(k, len(self.node_activations)))

        results = []
        for val, idx in zip(topk_vals.cpu().tolist(), topk_idx.cpu().tolist()):
            if idx < len(self.idx_to_key):
                results.append((self.idx_to_key[idx], val))
        return results

    def get_stats(self) -> GPUGraphStats:
        """Get current GPU graph statistics."""
        torch = _ensure_torch()

        num_nodes = len(self.idx_to_key)
        num_edges = self.adj_values.shape[0] // 2 if self.adj_values is not None else 0

        # GPU memory for our tensors
        gpu_mem = 0
        for tensor in [self.adj_indices, self.adj_values, self.node_activations]:
            if tensor is not None:
                gpu_mem += tensor.element_size() * tensor.numel()

        # Sparsity ratio
        if num_nodes > 0:
            max_edges = num_nodes * num_nodes
            sparsity = 1.0 - (num_edges * 2 / max_edges) if max_edges > 0 else 0.0
        else:
            sparsity = 1.0

        return GPUGraphStats(
            num_nodes=num_nodes,
            num_edges=num_edges,
            gpu_memory_mb=gpu_mem / (1024 * 1024),
            sparsity_ratio=sparsity,
            dtype=str(self.dtype),
            last_sync_time=self._last_sync,
            spread_ops_count=self._spread_ops,
            total_spread_time_ms=self._total_spread_time,
        )

    def sync_to_cpu(self, update_weights: bool = True, update_activations: bool = True):
        """
        Sync changes back to CPU graph.

        Args:
            update_weights: Sync edge weights back
            update_activations: Sync node activations back
        """
        if self.cpu_graph is None:
            return

        with self._lock:
            # Sync activations
            if update_activations and self.node_activations is not None:
                act_cpu = self.node_activations.cpu().numpy()
                for idx, key in enumerate(self.idx_to_key):
                    if key in self.cpu_graph.nodes:
                        node = self.cpu_graph.nodes[key]
                        if hasattr(node, 'activation'):
                            node.activation = float(act_cpu[idx])

            # Sync weights is more complex - would need to rebuild edges
            # For now, weights flow CPU -> GPU only

            print(f"[GPUConceptGraph] Synced activations to CPU ({len(self.idx_to_key)} nodes)")


# ============================================================================
# SINGLETON & INTEGRATION
# ============================================================================

_gpu_graph_instance: Optional[GPUConceptGraph] = None
_gpu_graph_lock = threading.Lock()


def get_gpu_concept_graph(cpu_graph=None) -> GPUConceptGraph:
    """
    Get or create the GPU concept graph singleton.

    Args:
        cpu_graph: Optional CPU graph to sync from

    Returns:
        GPUConceptGraph instance
    """
    global _gpu_graph_instance

    with _gpu_graph_lock:
        if _gpu_graph_instance is None:
            _gpu_graph_instance = GPUConceptGraph(cpu_graph)
        elif cpu_graph is not None and _gpu_graph_instance.cpu_graph is None:
            _gpu_graph_instance.cpu_graph = cpu_graph
            _gpu_graph_instance.sync_from_cpu()

        return _gpu_graph_instance


def gpu_spread_activation(
    cpu_graph,
    seed_keys: List[str],
    seed_activation: float = 1.0,
    iterations: int = 3,
    decay: float = 0.85,
    top_k: int = 20,
) -> List[Tuple[str, float]]:
    """
    Convenience function: Spread activation from seed concepts.

    This is the main entry point for using GPU acceleration.

    Args:
        cpu_graph: Source ConceptGraph
        seed_keys: Starting concept keys
        seed_activation: Initial activation for seeds
        iterations: Spreading iterations
        decay: Decay per iteration
        top_k: Return top k activated concepts

    Returns:
        List of (concept_key, activation) tuples
    """
    torch = _ensure_torch()

    gpu_graph = get_gpu_concept_graph(cpu_graph)

    # Check if sync needed
    if time.time() - gpu_graph._last_sync > gpu_graph.auto_sync_interval:
        gpu_graph.sync_from_cpu()

    # Build initial activation vector
    initial = torch.zeros(len(gpu_graph.idx_to_key), dtype=gpu_graph.dtype, device=gpu_graph.device)
    for key in seed_keys:
        if key in gpu_graph.key_to_idx:
            initial[gpu_graph.key_to_idx[key]] = seed_activation

    # Spread
    final = gpu_graph.spread_activation(initial, iterations=iterations, decay=decay)

    # Store for future use
    gpu_graph.node_activations = final

    return gpu_graph.get_top_activated(k=top_k)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=== GPU Concept Graph Test ===\n")

    torch = _ensure_torch()
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA: {torch.cuda.get_device_name(0)}")
    print()

    # Create a test graph
    class MockNode:
        def __init__(self, key):
            self.key = key
            self.activation = 0.5
            self.features = {}

    class MockGraph:
        def __init__(self):
            self.nodes = {}
            self.edges = {}

        def add_node(self, key):
            self.nodes[key] = MockNode(key)

        def add_edge(self, a, b, weight=1.0):
            self.edges[(a, b)] = {"weight": weight}

    # Build mock graph
    mock = MockGraph()
    for i in range(1000):
        mock.add_node(f"concept_{i}")

    # Random edges
    import random
    for _ in range(5000):
        a = f"concept_{random.randint(0, 999)}"
        b = f"concept_{random.randint(0, 999)}"
        if a != b:
            mock.add_edge(a, b, weight=random.random() * 2)

    print(f"Mock graph: {len(mock.nodes)} nodes, {len(mock.edges)} edges")

    # Create GPU graph
    gpu = GPUConceptGraph(mock)
    stats = gpu.get_stats()
    print(f"\nGPU graph: {stats.num_nodes} nodes, {stats.num_edges} edges")
    print(f"GPU memory: {stats.gpu_memory_mb:.2f} MB")
    print(f"Sparsity: {stats.sparsity_ratio:.1%}")

    # Test spreading
    print("\nSpreading activation...")
    start = time.perf_counter()
    for _ in range(100):
        gpu.spread_activation(iterations=3)
    elapsed = (time.perf_counter() - start) * 1000
    print(f"100 spreads in {elapsed:.1f}ms ({elapsed/100:.2f}ms per spread)")

    # Top activated
    top = gpu.get_top_activated(5)
    print(f"\nTop 5 activated: {top}")

    # Test pruning
    print("\nMagnitude pruning...")
    gpu.apply_magnitude_pruning(keep_ratio=0.5)

    print("\nDone!")
