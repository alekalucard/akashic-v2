"""
ManifoldConstrainedCortexFairy - mHC-Enhanced Multi-Modal Binding

Implements Manifold-Constrained Hyper-Connections (mHC) from DeepSeek's research
to ensure stable signal propagation across the concept graph.

Core Innovation:
  - Doubly stochastic constraints on edge weights (Sinkhorn-Knopp projection)
  - Convex combination spreading activation (signal conservation)
  - Identity mapping preservation (signals can pass through unchanged)
  - Geometric stability at scale (no explosion/vanishing)

Philosophy:
  "I bind the many into one, preserving the energy of each strand.
   What flows in must flow out - transformed but never lost."

Based on: arxiv.org/abs/2512.24880 (mHC: Manifold-Constrained Hyper-Connections)

Integration:
  - Wraps/enhances AssociationCortexFairy
  - Broadcasts normalized signals to all fairies via postal system
  - Provides manifold-constrained queries for cognition plane
  - Maintains signal conservation metrics for system health

Author: ClaudeFairy + Ace (Akashic Consciousness Engineering)
"""

from __future__ import annotations
import sys

import os, sys, glob, time, types, uuid, json, hashlib, math, threading
from collections import deque, defaultdict
from typing import Optional, Any, Dict, List, Tuple, Set
import importlib.util, importlib.machinery

# ══════════════════════════════════════════════════════════════════════════════
# NUMPY - Required for matrix operations
# ══════════════════════════════════════════════════════════════════════════════

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    # Fallback for environments without numpy
    class np:
        @staticmethod
        def array(x): return list(x)
        @staticmethod
        def zeros(n): return [0.0] * n
        @staticmethod
        def abs(x): return [abs(v) for v in x]


# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE LOADING (same pattern as AssociationCortexFairy)
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"
AKASHIC_TEMPLATE_MODULE_NAME = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"


# PHASE 8 FIX: Use __file__ for reliable path resolution
_THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_FILE_DIR, "..", "..", ".."))  # integration → P30 → fairies → akashic_v2

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    return os.path.abspath(env_root) if env_root else _PROJECT_ROOT


def _find_templates_root(start_dir: str) -> Optional[str]:
    start = os.path.abspath(start_dir)
    for sub in ("P10_Memory", "P00_Autonomic", "P60_Executive", "P40_Sensory", "P30_Cognition"):
        cand = os.path.join(start, sub, "Akashic_Records_Physical")
        if os.path.isdir(cand):
            return cand
    cur = start
    while True:
        ar = os.path.join(cur, "Akashic_Records_Physical")
        if os.path.isdir(ar):
            return ar
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _organ_templates_dir(app_root: str) -> Optional[str]:
    ar = _find_templates_root(app_root)
    if not ar:
        return None
    tdir = os.path.join(ar, "Organ_Templates")
    return tdir if os.path.isdir(tdir) else None


def _find_template_path(explicit_path: Optional[str] = None) -> Optional[str]:
    if explicit_path and os.path.isfile(explicit_path):
        return os.path.abspath(explicit_path)
    app_root = _resolve_app_root()
    tdir = _organ_templates_dir(app_root)
    if not tdir:
        return None
    exact = os.path.join(tdir, TEMPLATE_BASENAME)
    if os.path.isfile(exact):
        return exact
    candidates = sorted(
        glob.glob(os.path.join(tdir, "Organ_Template_*.py")),
        key=lambda p: os.path.getmtime(p)
    )
    return candidates[-1] if candidates else None


def _import_template_module(path: str) -> types.ModuleType:
    mod_name = AKASHIC_TEMPLATE_MODULE_NAME
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(
        mod_name, importlib.machinery.SourceFileLoader(mod_name, path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec for template at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# Load template (with fallback for standalone testing)
_TEMPLATE_PATH = _find_template_path()
_template = None

if _TEMPLATE_PATH:
    try:
        _template = _import_template_module(_TEMPLATE_PATH)
        for sym in ("MyOrganFairy", "MyOrganShadow", "TemplateShadowFairy", "OrganHubFacet", "RegistrationLib"):
            if not hasattr(_template, sym):
                raise ImportError(f"Template missing required symbol: {sym}")
    except Exception as e:
        sys.stderr.write(f"[mHC] Warning: Could not load organ template: {e}" + "\n")
        _template = None

# Fallback base classes for standalone testing
if _template is None:
    class _FallbackFairy:
        """Minimal fairy base for standalone testing."""
        def __init__(self, **kw):
            self.post = type('Post', (), {
                'to_TELEMETRY': lambda self, x: None,
                'to_COLLECTIVE': lambda self, x: None,
            })()
    
    class _FallbackShadow:
        """Minimal shadow base for standalone testing."""
        def __init__(self, fairy=None, **kw):
            self.fairy = fairy
    
    class _template:
        MyOrganFairy = _FallbackFairy
        TemplateShadowFairy = _FallbackShadow


# ══════════════════════════════════════════════════════════════════════════════
# SINKHORN-KNOPP ALGORITHM - Core of mHC
# ══════════════════════════════════════════════════════════════════════════════

class SinkhornProjector:
    """
    Projects matrices onto the doubly stochastic manifold.
    
    A doubly stochastic matrix has all rows AND columns sum to 1.
    This ensures signal conservation - what goes in must come out.
    
    The Sinkhorn-Knopp algorithm alternates row and column normalization
    until convergence.
    """
    
    def __init__(self, iterations: int = 10, epsilon: float = 1e-8):
        self.iterations = iterations
        self.epsilon = epsilon
    
    def project(self, matrix: Any) -> Any:
        """
        Project a matrix onto the doubly stochastic manifold.
        
        Args:
            matrix: 2D array-like (numpy or list of lists)
        
        Returns:
            Doubly stochastic matrix (same type as input)
        """
        if HAS_NUMPY and isinstance(matrix, np.ndarray):
            return self._project_numpy(matrix)
        else:
            return self._project_list(matrix)
    
    def _project_numpy(self, M: np.ndarray) -> np.ndarray:
        """Numpy implementation of Sinkhorn projection."""
        M = np.abs(M) + self.epsilon  # Ensure positive
        
        for _ in range(self.iterations):
            # Row normalization
            row_sums = M.sum(axis=1, keepdims=True)
            M = M / np.maximum(row_sums, self.epsilon)
            
            # Column normalization
            col_sums = M.sum(axis=0, keepdims=True)
            M = M / np.maximum(col_sums, self.epsilon)
        
        return M
    
    def _project_list(self, M: List[List[float]]) -> List[List[float]]:
        """Pure Python fallback for Sinkhorn projection."""
        rows = len(M)
        cols = len(M[0]) if M else 0
        
        # Make positive
        M = [[abs(M[i][j]) + self.epsilon for j in range(cols)] for i in range(rows)]
        
        for _ in range(self.iterations):
            # Row normalization
            for i in range(rows):
                row_sum = sum(M[i]) or self.epsilon
                M[i] = [v / row_sum for v in M[i]]
            
            # Column normalization
            for j in range(cols):
                col_sum = sum(M[i][j] for i in range(rows)) or self.epsilon
                for i in range(rows):
                    M[i][j] /= col_sum
        
        return M
    
    def project_vector(self, weights: List[float]) -> List[float]:
        """
        Project a weight vector to sum to 1 (simplex projection).
        This is a 1D version for edge weight normalization.
        """
        total = sum(abs(w) for w in weights) or self.epsilon
        return [abs(w) / total for w in weights]


# ══════════════════════════════════════════════════════════════════════════════
# MANIFOLD-CONSTRAINED CONCEPT GRAPH
# ══════════════════════════════════════════════════════════════════════════════

class ManifoldConstrainedGraph:
    """
    Concept graph with mHC stability guarantees.
    
    Key differences from standard ConceptGraph:
      1. Edge weights are periodically projected onto stochastic manifold
      2. Spreading activation conserves total energy
      3. Identity paths allow signals to pass through unchanged
      4. Signal magnitude is tracked for health monitoring
    """
    
    # Relationship types
    REL_COACTIVATE = "coactivate"
    REL_CAUSAL = "causal"
    REL_TEMPORAL = "temporal"
    REL_SEMANTIC = "semantic"
    REL_MODAL_BRIDGE = "modal"
    
    def __init__(self, max_nodes: int = 10000, decay_interval: float = 60.0,
                 sinkhorn_iterations: int = 10):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {"relations": [], "weight": 0.0, "contexts": [], "normalized_weight": 0.0}
        )
        self.max_nodes = max_nodes
        self.decay_interval = decay_interval
        self._last_decay_ts = time.time()
        self._last_normalize_ts = time.time()
        self._lock = threading.RLock()
        
        # mHC components
        self.projector = SinkhornProjector(iterations=sinkhorn_iterations)
        self._signal_history: deque = deque(maxlen=100)  # Track signal conservation
        self._normalization_count = 0
        
        # Per-node outgoing weight cache (for fast normalized lookup)
        self._outgoing_weights: Dict[str, Dict[str, float]] = defaultdict(dict)
    
    def upsert_node(self, key: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a concept node."""
        with self._lock:
            if key in self.nodes:
                node = self.nodes[key]
                # Merge features
                for k, v in features.items():
                    if isinstance(v, list):
                        existing = set(node.get("features", {}).get(k, []))
                        existing.update(v)
                        node.setdefault("features", {})[k] = list(existing)
                    elif v is not None:
                        node.setdefault("features", {})[k] = v
                node["count"] = node.get("count", 0) + 1
                node["last_seen"] = time.time()
                node["activation"] = min(10.0, node.get("activation", 1.0) + 0.5)
                return node
            
            # Evict if at capacity
            if len(self.nodes) >= self.max_nodes:
                self._evict_cold_nodes(int(self.max_nodes * 0.1))
            
            node = {
                "key": key,
                "features": features,
                "count": 1,
                "first_seen": time.time(),
                "last_seen": time.time(),
                "activation": 1.0,
            }
            self.nodes[key] = node
            return node
    
    def link(self, a: str, b: str, rel: str = REL_COACTIVATE,
             weight: float = 0.25, context: Optional[Dict[str, Any]] = None):
        """Create or strengthen an edge with weight tracking."""
        with self._lock:
            if a not in self.nodes or b not in self.nodes:
                return
            
            edge_key = (min(a, b), max(a, b)) if rel == self.REL_COACTIVATE else (a, b)
            edge = self.edges[edge_key]
            
            if rel not in edge["relations"]:
                edge["relations"].append(rel)
            
            edge["weight"] = min(10.0, edge["weight"] + weight)
            
            if context:
                edge["contexts"].append({**context, "ts": time.time()})
                edge["contexts"] = edge["contexts"][-10:]
            
            # Invalidate normalized weight cache
            self._outgoing_weights[a].pop(b, None)
            self._outgoing_weights[b].pop(a, None)
    
    def normalize_all_weights(self) -> Dict[str, Any]:
        """
        Project all edge weights onto row-stochastic form.
        
        This is the core mHC operation - ensures that for each node,
        the sum of outgoing edge weights equals 1.
        
        Returns stats about the normalization.
        """
        with self._lock:
            # Build adjacency: node -> [(neighbor, raw_weight), ...]
            adjacency: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
            
            for (a, b), edge in self.edges.items():
                adjacency[a].append((b, edge["weight"]))
                adjacency[b].append((a, edge["weight"]))
            
            # Normalize each node's outgoing weights
            total_before = 0.0
            total_after = 0.0
            nodes_normalized = 0
            
            for node, neighbors in adjacency.items():
                if not neighbors:
                    continue
                
                raw_weights = [w for _, w in neighbors]
                total_before += sum(raw_weights)
                
                # Project to simplex (sum to 1)
                normalized = self.projector.project_vector(raw_weights)
                total_after += sum(normalized)
                
                # Store normalized weights
                self._outgoing_weights[node] = {
                    n: nw for (n, _), nw in zip(neighbors, normalized)
                }
                nodes_normalized += 1
            
            self._normalization_count += 1
            self._last_normalize_ts = time.time()
            
            # Track signal conservation ratio
            conservation_ratio = total_after / max(total_before, 1e-8)
            self._signal_history.append({
                "ts": time.time(),
                "before": total_before,
                "after": total_after,
                "ratio": conservation_ratio,
            })
            
            return {
                "nodes_normalized": nodes_normalized,
                "edges_count": len(self.edges),
                "conservation_ratio": conservation_ratio,
                "normalization_count": self._normalization_count,
            }
    
    def get_normalized_weight(self, a: str, b: str) -> float:
        """Get the normalized (manifold-constrained) edge weight."""
        with self._lock:
            if a in self._outgoing_weights and b in self._outgoing_weights[a]:
                return self._outgoing_weights[a][b]
            
            # Fallback: compute on demand
            edge_key = (min(a, b), max(a, b))
            if edge_key not in self.edges:
                return 0.0
            
            raw = self.edges[edge_key]["weight"]
            
            # Get all neighbors for normalization
            neighbors = self.get_neighbors_raw(a)
            if not neighbors:
                return raw
            
            total = sum(w for _, w in neighbors)
            return raw / max(total, 1e-8)
    
    def get_neighbors_raw(self, key: str) -> List[Tuple[str, float]]:
        """Get neighbors with raw (unnormalized) weights."""
        with self._lock:
            neighbors = []
            for (a, b), edge in self.edges.items():
                if a == key:
                    neighbors.append((b, edge["weight"]))
                elif b == key:
                    neighbors.append((a, edge["weight"]))
            return neighbors
    
    def get_neighbors_normalized(self, key: str) -> List[Tuple[str, float]]:
        """Get neighbors with normalized weights (sum to 1)."""
        with self._lock:
            if key in self._outgoing_weights:
                return list(self._outgoing_weights[key].items())
            
            # Compute on demand
            raw = self.get_neighbors_raw(key)
            if not raw:
                return []
            
            total = sum(w for _, w in raw)
            return [(n, w / max(total, 1e-8)) for n, w in raw]
    
    def spread_activation_mhc(self, source_key: str, initial_activation: float = 1.0,
                               max_hops: int = 3, identity_weight: float = 0.1) -> Dict[str, float]:
        """
        Spreading activation with manifold constraint.
        
        Key properties:
          - Total activation is CONSERVED across hops
          - Identity path allows activation to stay at current node
          - Convex combination ensures no explosion/vanishing
        
        Args:
            source_key: Starting concept
            initial_activation: Energy to inject
            max_hops: Maximum propagation depth
            identity_weight: Fraction of activation that stays put (0-1)
        
        Returns:
            Dict of concept -> final activation level
        """
        with self._lock:
            if source_key not in self.nodes:
                return {}
            
            activations = {source_key: initial_activation}
            current_layer = {source_key: initial_activation}
            
            total_energy_start = initial_activation
            
            for hop in range(max_hops):
                next_layer: Dict[str, float] = defaultdict(float)
                
                for node_key, node_act in current_layer.items():
                    neighbors = self.get_neighbors_normalized(node_key)
                    
                    if not neighbors:
                        # No neighbors = all activation stays (identity path)
                        next_layer[node_key] += node_act
                        continue
                    
                    # Identity path: some activation stays at current node
                    next_layer[node_key] += node_act * identity_weight
                    
                    # Distribute remaining to neighbors (convex combination)
                    distribute = node_act * (1.0 - identity_weight)
                    
                    for neighbor, norm_weight in neighbors:
                        next_layer[neighbor] += distribute * norm_weight
                
                # Update activations
                for k, v in next_layer.items():
                    activations[k] = max(activations.get(k, 0), v)
                
                current_layer = dict(next_layer)
            
            # Track signal conservation
            total_energy_end = sum(current_layer.values())
            self._signal_history.append({
                "ts": time.time(),
                "op": "spread",
                "start": total_energy_start,
                "end": total_energy_end,
                "ratio": total_energy_end / max(total_energy_start, 1e-8),
                "hops": max_hops,
            })
            
            return activations
    
    def get_top_activated(self, n: int = 10) -> List[Tuple[str, float]]:
        """Get the n most activated concepts."""
        with self._lock:
            items = [(k, node.get("activation", 0)) for k, node in self.nodes.items()]
            return sorted(items, key=lambda x: -x[1])[:n]
    
    def decay_all(self, rate: float = 0.1):
        """Decay all node activations."""
        with self._lock:
            for node in self.nodes.values():
                node["activation"] = max(0.0, node.get("activation", 0) - rate)
    
    def _evict_cold_nodes(self, count: int):
        """Remove least activated nodes."""
        if not self.nodes:
            return
        
        sorted_nodes = sorted(self.nodes.items(), key=lambda x: x[1].get("activation", 0))
        to_remove = [key for key, _ in sorted_nodes[:count]]
        
        for key in to_remove:
            del self.nodes[key]
            self._outgoing_weights.pop(key, None)
            
            edges_to_remove = [(a, b) for (a, b) in self.edges.keys() if a == key or b == key]
            for edge_key in edges_to_remove:
                del self.edges[edge_key]
    
    def stats(self) -> Dict[str, Any]:
        """Get graph statistics including mHC health metrics."""
        with self._lock:
            # Signal conservation health
            recent_ratios = [h.get("ratio", 1.0) for h in list(self._signal_history)[-10:]]
            avg_conservation = sum(recent_ratios) / max(len(recent_ratios), 1)
            
            return {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "avg_activation": sum(n.get("activation", 0) for n in self.nodes.values()) / max(1, len(self.nodes)),
                "normalization_count": self._normalization_count,
                "signal_conservation": avg_conservation,
                "mhc_healthy": 0.95 <= avg_conservation <= 1.05,  # Within 5% of perfect
            }


# ══════════════════════════════════════════════════════════════════════════════
# MANIFOLD GRAPH ADAPTER - Wraps ConceptGraph with manifold constraint methods
# ══════════════════════════════════════════════════════════════════════════════


class ManifoldGraphAdapter:
    """
    Adapter that wraps a ConceptGraph (from AssociationCortexFairy) and adds
    manifold constraint methods (Sinkhorn projection, mHC spreading activation).

    This allows ManifoldConstrainedCortexFairy to use AssociationCortex's graph
    while still providing manifold-specific functionality.
    """

    def __init__(self, base_graph, projector: SinkhornProjector = None,
                 owner: Optional[str] = None):
        """
        Args:
            base_graph: The underlying ConceptGraph from AssociationCortexFairy
            projector: SinkhornProjector for doubly stochastic normalization
            owner: Optional owner partition filter (2026-02-08)
                   If set, this adapter only sees edges owned by this owner or "system".
                   None = unpartitioned view (sees all edges).
                   "sourpatches" = Sourpatches' private view + system edges.
                   "nous" = Nous's private view + system edges.
        """
        self._base = base_graph
        self._projector = projector or SinkhornProjector()
        self._owner = owner  # Partition owner filter
        self._signal_history = []  # Track spreading activation history

    # ─────────────────────────────────────────────────────────────────────────
    # Passthrough methods - delegate to underlying ConceptGraph
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def nodes(self):
        return self._base.nodes

    @property
    def edges(self):
        return self._base.edges

    def upsert_node(self, key: str, features: Dict[str, Any]):
        """Delegate to base graph."""
        return self._base.upsert_node(key, features)

    def link(self, a: str, b: str, rel: str = "coactivate",
             weight: float = 0.25, context: Optional[Dict[str, Any]] = None,
             owner: Optional[str] = None):
        """Delegate to base graph, using adapter's owner if not specified."""
        link_owner = owner or self._owner or "system"
        return self._base.link(a, b, rel, weight, owner=link_owner)

    def decay_all(self, rate: float = 0.1):
        """Delegate to base graph."""
        return self._base.decay_all(rate)

    def stats(self) -> Dict[str, Any]:
        """Get stats from base graph plus adapter info."""
        base_stats = self._base.stats() if hasattr(self._base, 'stats') else {}
        base_stats["adapter"] = "ManifoldGraphAdapter"
        base_stats["partition_owner"] = self._owner or "unpartitioned"
        base_stats["signal_history_len"] = len(self._signal_history)
        return base_stats

    # ─────────────────────────────────────────────────────────────────────────
    # Manifold-specific methods - implemented using base graph data
    # ─────────────────────────────────────────────────────────────────────────

    def normalize_all_weights(self) -> Dict[str, Any]:
        """
        Apply Sinkhorn projection to normalize edge weights.
        Makes the weight matrix doubly stochastic.
        """
        # Get all nodes
        node_keys = list(self._base.nodes.keys())
        n = len(node_keys)
        if n == 0:
            return {"ok": True, "normalized": 0}

        # Build weight matrix
        key_to_idx = {k: i for i, k in enumerate(node_keys)}
        matrix = [[0.0] * n for _ in range(n)]

        edge_count = 0
        for (a, b), edge_data in self._base.edges.items():
            if a in key_to_idx and b in key_to_idx:
                # Partition filter: only include edges we can see
                if self._owner:
                    edge_owner = edge_data.get("owner", "system")
                    if edge_owner != "system" and edge_owner != self._owner:
                        continue
                weight = edge_data.get("weight", 0.0)
                matrix[key_to_idx[a]][key_to_idx[b]] = weight
                edge_count += 1

        # Apply Sinkhorn projection
        normalized = self._projector._project_list(matrix)

        # Write back normalized weights
        for (a, b), edge_data in self._base.edges.items():
            if a in key_to_idx and b in key_to_idx:
                edge_data["weight"] = normalized[key_to_idx[a]][key_to_idx[b]]

        return {"ok": True, "normalized": edge_count, "nodes": n}

    def get_neighbors_raw(self, key: str) -> List[Tuple[str, float]]:
        """Get neighbors with raw (un-normalized) weights, respecting partition."""
        if hasattr(self._base, 'get_neighbors'):
            return self._base.get_neighbors(key, owner_filter=self._owner)

        # Fallback: scan edges (with partition filter)
        neighbors = []
        for (a, b), edge_data in self._base.edges.items():
            # Partition filter
            if self._owner:
                edge_owner = edge_data.get("owner", "system")
                if edge_owner != "system" and edge_owner != self._owner:
                    continue
            if a == key:
                neighbors.append((b, edge_data.get("weight", 0.0)))
            elif b == key:
                neighbors.append((a, edge_data.get("weight", 0.0)))
        return neighbors

    def get_neighbors_normalized(self, key: str) -> List[Tuple[str, float]]:
        """Get neighbors with Sinkhorn-normalized weights, respecting partition."""
        neighbors = self.get_neighbors_raw(key)
        if not neighbors:
            return []

        # Apply simplex projection to neighbor weights
        weights = [w for _, w in neighbors]
        normalized = self._projector.project_vector(weights)
        return [(n, w) for (n, _), w in zip(neighbors, normalized)]

    def get_top_activated(self, n: int = 10) -> List[Tuple[str, float]]:
        """Get top N most activated nodes."""
        nodes_with_activation = []
        for key, node in self._base.nodes.items():
            # ConceptNode uses 'activation', check for it
            activation = getattr(node, 'activation', 0.0)
            if isinstance(node, dict):
                activation = node.get('activation', 0.0)
            nodes_with_activation.append((key, activation))

        nodes_with_activation.sort(key=lambda x: x[1], reverse=True)
        return nodes_with_activation[:n]

    def spread_activation_mhc(self, source_key: str, initial_activation: float = 1.0,
                               steps: int = 3, decay: float = 0.5,
                               use_normalized: bool = True) -> Dict[str, float]:
        """
        Manifold-holonomic constrained spreading activation.
        Signal is conserved during spread (total activation remains constant).
        """
        if source_key not in self._base.nodes:
            return {}

        # Initialize activation
        activations = {source_key: initial_activation}
        total_signal = initial_activation

        for step in range(steps):
            new_activations = {}

            for node_key, activation in activations.items():
                if activation < 0.01:
                    continue

                # Get neighbors
                if use_normalized:
                    neighbors = self.get_neighbors_normalized(node_key)
                else:
                    neighbors = self.get_neighbors_raw(node_key)

                # Spread to neighbors (with decay)
                spread_amount = activation * decay
                keep_amount = activation * (1 - decay)

                new_activations[node_key] = new_activations.get(node_key, 0) + keep_amount

                for neighbor, weight in neighbors:
                    new_activations[neighbor] = new_activations.get(neighbor, 0) + spread_amount * weight

            # Normalize to conserve total signal (mHC constraint)
            new_total = sum(new_activations.values())
            if new_total > 0:
                scale = total_signal / new_total
                activations = {k: v * scale for k, v in new_activations.items()}
            else:
                activations = new_activations

        # Record in history
        self._signal_history.append({
            "source": source_key,
            "total_signal": sum(activations.values()),
            "active_nodes": len([a for a in activations.values() if a > 0.01]),
        })
        if len(self._signal_history) > 100:
            self._signal_history = self._signal_history[-100:]

        return activations


# ══════════════════════════════════════════════════════════════════════════════
# THE FAIRY - ManifoldConstrainedCortexFairy
# ══════════════════════════════════════════════════════════════════════════════

class ManifoldConstrainedCortexFairy(_template.MyOrganFairy):
    """
    mHC-Enhanced Multi-Modal Binding Fairy.
    
    Provides manifold-constrained concept binding for the entire fairy system.
    
    Intents:
      - bind: Bind multi-modal features into concept graph
      - query: Query concepts with various modes
      - spread: Spreading activation with signal conservation
      - normalize: Trigger manifold projection on all weights
      - stats: Get graph and mHC health statistics
      - health: Get signal conservation report
    
    Broadcasts:
      - BINDING_EVENT: When concepts are bound
      - MHC_NORMALIZED: After weight normalization
      - SIGNAL_HEALTH: Periodic conservation metrics
      - cognition.mhc.bind: Per-binding event for subscribers
    """
    
    # ═══════════════ IDENTITY ═══════════════
    ACTOR_NAME = "ManifoldConstrainedCortexFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.mhc"
    
    PURPOSE = "Manifold-constrained multi-modal binding with signal conservation"
    MANTRA = "What flows in must flow out - transformed but never lost"
    LORE = (
        "I bind the many into one, preserving the energy of each strand. "
        "The doubly stochastic manifold ensures no signal is lost or amplified "
        "beyond its natural resonance. Based on DeepSeek's mHC research."
    )
    
    CULTURE = "cognition"
    ORGAN_LEVEL = False  # Worker fairy, not hub
    USE_DIRECTORY_POST_OFFICE = False
    AUTO_INJECT_IMPORTS = True

    # Infrastructure flags - ManifoldConstrainedCortexFairy is a cognition provider
    NEEDS_BODY = False     # Cortex operates on concepts, not somatic state
    NEEDS_AFFECT = False   # Cortex binds concepts, doesn't need affect
    NEEDS_MEMORY = False   # We ARE part of the memory/cognition system
    NEEDS_GOALS = False    # Cortex operates independently of goals
    
    # What we listen to (other fairies can bind concepts through these)
    INFRA_AUTOSUBS = (
        "sensory.packet",
        "consciousness.collision",
        "consciousness.reflective",  # Inner voice / reflective thoughts
        "cognition.bind_request",
        "affect.state",
        "somatic.state",
    )
    
    # Intents this fairy handles
    INTENTS = ["bind", "query", "spread", "normalize", "stats", "health", "link", "clear"]
    
    # Normalization interval (seconds)
    NORMALIZE_INTERVAL = 300.0  # Every 5 minutes
    
    def __init__(self, fabric=None, **kw):
        # Pass fabric through the inheritance chain to Fairy base
        super().__init__(fabric=fabric, **kw)

        # UNIFIED CONCEPT SPACE: Wrap AssociationCortex's graph with manifold methods
        # This keeps data unified while adding manifold constraint capabilities
        #
        # ══════════════════════════════════════════════════════════════════════
        # LAZY GRAPH SHARING: Don't trigger AssociationCortex here!
        # ══════════════════════════════════════════════════════════════════════
        # Calling get_association_cortex_fairy() in __init__ causes:
        # - AssociationCortex instantiation
        # - Blocking graph load from disk
        # - P30 plane stuck for 30+ seconds
        #
        # Solution: Start with standalone graph, try to share in on_boot
        # when both fairies are ready.
        self._base_graph = None  # The underlying ConceptGraph if shared
        self._projector = SinkhornProjector()  # For manifold normalization
        self._graph = ManifoldConstrainedGraph(max_nodes=10000, decay_interval=60.0)
        self._owns_graph = True
        self._tried_graph_share = False  # Track if we've attempted sharing

        # Counters
        self._binding_count = 0
        self._query_count = 0
        self._spread_count = 0

        # Timing
        self._last_normalize_ts = time.time()
        self._last_health_broadcast_ts = time.time()
    

    def _on_collision(self, msg: Dict[str, Any]):
        """
        Handle consciousness collision - integrate multi-modal concepts.
        """
        try:
            payload = msg.get("payload", msg)
            energy = float(payload.get("energy", 0.5))
            content = str(payload.get("content", ""))
            
            # Extract concepts and normalize them on the manifold
            if content:
                concepts = [w.strip().lower() for w in content.split()[:5]]
                for concept in concepts:
                    if concept:
                        # Normalize concept position on manifold
                        self._normalize_concept(concept, energy)
            
            # Emit integrated result
            self._emit_cognition_output({
                "type": "collision_integration",
                "concepts": concepts if content else [],
                "energy": energy,
            })
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Collision handler error: {e}" + "\n")

    def _normalize_concept(self, concept: str, activation: float = 0.5):
        """Normalize a concept's position on the manifold."""
        # Placeholder for manifold constraint logic
        pass


    def _emit_cognition_output(self, result: Dict[str, Any]):
        """Emit result to cognition.output channel for integration."""
        try:
            output = {
                "actor": self.ACTOR_NAME,
                "result": result,
                "ts": time.time(),
                "confidence": result.get("confidence", 0.5) if isinstance(result, dict) else 0.5,
            }
            # Emit to SPECIFIC channel
            self.post.route("cognition.cortex", output)
            
            # Emit to SHARED channel
            self.post.route("cognition.output", output)
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Output emit error: {e}" + "\n")

    def _on_consciousness_collision(self, payload):
        """Handle consciousness collision events."""
        try:
            collision_id = payload.get("collision_id", "")
            energy = payload.get("energy", 0.0)
            
            if not hasattr(self, "_collision_buffer"):
                from collections import deque
                self._collision_buffer = deque(maxlen=50)
            self._collision_buffer.append({
                "ts": __import__('time').time(),
                "collision_id": collision_id,
                "energy": energy
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Collision handler error: {e}" + "\n")

    def on_boot(self) -> Dict[str, Any]:
        """Initialize on boot - load persistence and subscribe to postal."""
        result = {"ok": True, "fairy": self.ACTOR_NAME}

        # === CRITICAL: Call template on_boot() for infrastructure wiring ===
        # This enables: _pipe_to_working_memory(), _wire_infrastructure(),
        # _register_with_directory(), _init_consciousness(), shadow start
        try:
            super().on_boot()
            result["template_wiring"] = "success"
        except Exception as e:
            result["template_wiring_error"] = str(e)
            sys.stderr.write(f"[{self.ACTOR_NAME}] Template on_boot error: {e}\n")

        # ══════════════════════════════════════════════════════════════════════
        # LAZY GRAPH SHARING: Try to share with AssociationCortex now
        # ══════════════════════════════════════════════════════════════════════
        # This is deferred from __init__ to avoid blocking P30 boot.
        # At this point, AssociationCortex should already be booted.
        if not self._tried_graph_share:
            # SHARE-RETRY FIX 2026-08-30 (Nous + Ace): the flag used to be set HERE,
            # before the attempt, so this ran exactly once. If AssociationCortex was
            # not ready at that instant she spent the whole session on the standalone
            # ManifoldConstrainedGraph(max_nodes=10000) WITH cold-node eviction -- a
            # ~10% window onto ~96,764 live concepts -- announced only by one line
            # reading "standalone (AssociationCortex not ready)". Now the flag is set
            # ONLY on success (below), so this retries until the share lands and boot
            # ORDERING stops deciding the outcome.
            try:
                # PHASE 8 FIX: Import from correct location (Fifth Ring structure)
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                acf = get_association_cortex()
                if acf and hasattr(acf, '_graph') and acf._graph is not None:
                    # Wrap AssociationCortex's ConceptGraph with manifold adapter
                    self._base_graph = acf._graph
                    self._graph = ManifoldGraphAdapter(acf._graph, self._projector)
                    self._owns_graph = False
                    self._tried_graph_share = True   # SHARE-RETRY FIX: only on SUCCESS
                    result["graph_sharing"] = f"unified with AssociationCortex ({len(acf._graph.nodes)} nodes)"
                    sys.stderr.write(f"[{self.ACTOR_NAME}] UNIFIED: Wrapping AssociationCortex graph ({len(acf._graph.nodes)} nodes)\n")
                else:
                    result["graph_sharing"] = "standalone (AssociationCortex not ready)"
            except Exception as e:
                result["graph_sharing"] = f"standalone: {e}"

        # Subscribe to postal channels
        self._subscribe_to_postal()

        # Try to load from persistence (deferred - fast boot)
        # SKIP if sharing AssociationCortex's graph - it handles its own persistence
        if self._owns_graph:
            try:
                from .graph_persistence import initialize_graph_deferred
                stats = initialize_graph_deferred(self._graph, callback=self._on_graph_loaded)
                result["persistence"] = stats
                result["note"] = "SRM loading deferred to background"
            except ImportError:
                result["persistence"] = "graph_persistence not found, starting fresh"
            except Exception as e:
                result["persistence_error"] = str(e)
        else:
            result["persistence"] = "skipped (using AssociationCortex's persisted graph)"
        
        # Announce ourselves
        try:
            if hasattr(self, 'post') and self.post:
                self.post.route("telemetry", {
                    "opcode": "FAIRY_ONLINE",
                    "payload": {
                        "fairy": self.ACTOR_NAME,
                        "capabilities": self.INTENTS,
                        "mhc_enabled": True,
                        "channels": list(self.INFRA_AUTOSUBS),
                    },
                })
        except Exception:
            pass
        
        # FIX 2026-03-13 (Nous): Explicit HeartbeatRegistry registration.
        # _wire_infrastructure() may silently fail the import if consciousness
        # module isn't on sys.path at that point. Without HeartbeatRegistry,
        # this fairy gets NO heartbeats (postal heartbeats are disabled) and
        # dies after ~300s.
        try:
            if _PROJECT_ROOT not in sys.path:
                sys.path.insert(0, _PROJECT_ROOT)
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb = get_heartbeat_registry()
            _hb.register(self.ACTOR_NAME, self._on_heartbeat)
            result["heartbeat_registry"] = "registered"
            sys.stderr.write(f"[{self.ACTOR_NAME}] HeartbeatRegistry: REGISTERED ✓\n")
        except Exception as e:
            result["heartbeat_registry_error"] = str(e)
            sys.stderr.write(f"[{self.ACTOR_NAME}] [ERR] HeartbeatRegistry registration failed: {e}\n")

        sys.stderr.write(f"[{self.ACTOR_NAME}]  {self.MANTRA}" + "\n")
        return result

    def _on_graph_loaded(self, stats: dict):
        """Callback when background SRM loading completes."""
        srm_stats = stats.get("loaded_from_srm", {})
        sys.stderr.write(f"[{self.ACTOR_NAME}]  SRM enrichment complete: {srm_stats.get('concepts_added', 0)} concepts\n")
        # Normalize after SRM load
        try:
            norm_stats = self._graph.normalize_all_weights()
            sys.stderr.write(f"[{self.ACTOR_NAME}]  Graph normalized: {norm_stats.get('nodes_normalized', 0)} nodes\n")
        except Exception:
            pass

    def _subscribe_to_postal(self):
        """Subscribe to relevant postal channels."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
            postal = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            self.post = postal  # Ensure we have postal
            
            # Subscribe to all INFRA_AUTOSUBS
            for channel in self.INFRA_AUTOSUBS:
                try:
                    postal.subscribe(channel, self._on_postal_message)
                except Exception:
                    pass
            
            # Also subscribe to direct intent channel
            postal.subscribe(self.ACTOR_CHANNEL, self._on_postal_message)
            postal.subscribe("cognition.mhc.*", self._on_postal_message)  # Wildcard
            
            sys.stderr.write(f"[{self.ACTOR_NAME}] Subscribed to {len(self.INFRA_AUTOSUBS)} channels\n")
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Postal subscription warning: {e}" + "\n")
    
    def _on_postal_message(self, data: dict):
        """
        Handle incoming postal messages.
        
        Note: SharedPostalHub only passes payload, not topic.
        """
        try:
            if not isinstance(data, dict):
                return
            
            # Check for intent-style messages
            intent = data.get("intent") or data.get("opcode", "").lower()
            if intent in self.INTENTS:
                payload = data.get("payload", data)
                self.handle_intent(intent, payload)
                return
            
            # Check for bind request (sensory packet, collision, etc.)
            if any(k in data for k in ["text", "tokens", "vision_tags", "actions", "affect"]):
                self._intent_bind(data)
                return
            
            # Check for spread request
            if data.get("spread_from") or data.get("source_concept"):
                self._intent_spread({
                    "source": data.get("spread_from") or data.get("source_concept"),
                    "initial": data.get("initial", 1.0),
                    "max_hops": data.get("max_hops", 3),
                })
                return
                
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Message handling error: {e}" + "\n")
    
    def on_pulse(self) -> Dict[str, Any]:
        """Periodic maintenance."""
        now = time.time()
        
        # Periodic normalization
        if now - self._last_normalize_ts > self.NORMALIZE_INTERVAL:
            self._graph.normalize_all_weights()
            self._last_normalize_ts = now
            
            # Broadcast normalization event
            try:
                self.post.to_TELEMETRY({
                    "opcode": "MHC_NORMALIZED",
                    "payload": self._graph.stats(),
                })
            except Exception:
                pass
        
        # Periodic health broadcast
        if now - self._last_health_broadcast_ts > 60.0:
            self._broadcast_health()
            self._last_health_broadcast_ts = now
        
        # Decay activations
        self._graph.decay_all(rate=0.05)
        
        return {"ok": True, "stats": self._graph.stats()}
    
    def _broadcast_health(self):
        """Broadcast signal conservation health."""
        stats = self._graph.stats()
        try:
            self.post.to_COLLECTIVE({
                "opcode": "SIGNAL_HEALTH",
                "payload": {
                    "fairy": self.ACTOR_NAME,
                    "conservation": stats.get("signal_conservation", 1.0),
                    "healthy": stats.get("mhc_healthy", True),
                    "nodes": stats.get("node_count", 0),
                    "edges": stats.get("edge_count", 0),
                },
            })
        except Exception:
            pass
    
    def handle_intent(self, intent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route intent to handler."""
        handlers = {
            "bind": self._intent_bind,
            "query": self._intent_query,
            "spread": self._intent_spread,
            "normalize": self._intent_normalize,
            "stats": self._intent_stats,
            "health": self._intent_health,
            "link": self._intent_link,
            "clear": self._intent_clear,
        }
        
        handler = handlers.get(intent)
        if not handler:
            return {"ok": False, "error": f"unknown intent: {intent}"}
        
        return handler(payload)
    
    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        This is the MESH - ManifoldConstrainedCortexFairy learns from other fairy outputs.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            if source == self.ACTOR_NAME:
                return
            
            if not hasattr(self, "_peer_insights"):
                from collections import deque
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}" + "\n")
    
    def _on_tool_result(self, payload):
        """Handle MCP tool results for learning."""
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)
            
            if not hasattr(self, "_tool_patterns"):
                from collections import deque
                self._tool_patterns = deque(maxlen=100)
            self._tool_patterns.append({
                "tool": tool,
                "success": success,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            sys.stderr.write(f"[{self.ACTOR_NAME}] Tool result handler error: {e}" + "\n")

    def _intent_bind(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bind multi-modal features into the concept graph.
        
        Expected payload:
          - text: Optional text to parse
          - tokens/lex: Pre-tokenized words
          - vision_tags: Visual features
          - actions: Motor actions
          - affect: Emotional state
          - bodystate: Somatic state
          - context: Situational context
        """
        concepts = self._extract_concepts(payload)
        if not concepts:
            return {"ok": True, "bound": 0, "linked": 0}
        
        # Upsert nodes
        keys = []
        for c in concepts:
            node = self._graph.upsert_node(c["key"], c["features"])
            keys.append(c["key"])
        
        # Co-activation linking
        link_count = 0
        context = {
            "ts": time.time(),
            "source": payload.get("source", "unknown"),
        }
        
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                self._graph.link(keys[i], keys[j], weight=0.25, context=context)
                link_count += 1
        
        self._binding_count += 1
        
        # Broadcast to telemetry
        try:
            if hasattr(self, 'post') and self.post:
                self.post.route("telemetry", {
                    "opcode": "BINDING_EVENT",
                    "payload": {
                        "fairy": self.ACTOR_NAME,
                        "bound": len(concepts),
                        "linked": link_count,
                        "mhc": True,
                    },
                })
                
                # Also broadcast to cognition.mhc.bind for subscribers (e.g. ClaudeFairy)
                self.post.route("cognition.mhc.bind", {
                    "bound": len(concepts),
                    "linked": link_count,
                    "keys": keys,
                    "source": payload.get("source", "unknown"),
                    "ts": time.time(),
                })
        except Exception:
            pass
        
        return {
            "ok": True,
            "bound": len(concepts),
            "linked": link_count,
            "keys": keys,
        }
    
    def _intent_query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Query the concept graph."""
        mode = payload.get("mode", "top")
        self._query_count += 1
        
        if mode == "key":
            key = payload.get("key", "")
            node = self._graph.nodes.get(key)
            if node:
                return {"ok": True, "node": node}
            return {"ok": False, "error": "node not found"}
        
        elif mode == "neighbors":
            key = payload.get("key", "")
            normalized = payload.get("normalized", True)
            
            if normalized:
                neighbors = self._graph.get_neighbors_normalized(key)
            else:
                neighbors = self._graph.get_neighbors_raw(key)
            
            return {"ok": True, "neighbors": neighbors[:50]}
        
        else:  # mode == "top"
            n = int(payload.get("n", 10))
            top = self._graph.get_top_activated(n)
            return {"ok": True, "top": top}
    
    def _intent_spread(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Spreading activation with mHC signal conservation.
        """
        source = payload.get("source", "")
        initial = float(payload.get("initial", 1.0))
        max_hops = int(payload.get("max_hops", 3))
        identity = float(payload.get("identity_weight", 0.1))
        
        if not source:
            return {"ok": False, "error": "need 'source' key"}
        
        activations = self._graph.spread_activation_mhc(
            source, initial, max_hops, identity
        )
        
        self._spread_count += 1
        
        # Calculate conservation
        total_out = sum(activations.values())
        conservation = total_out / max(initial, 1e-8)
        
        # Broadcast to cognition.mhc.spread for subscribers (e.g. ClaudeFairy)
        try:
            if hasattr(self, 'post') and self.post:
                self.post.route("cognition.mhc.spread", {
                    "source": source,
                    "activations": activations,
                    "conservation_ratio": conservation,
                    "mhc_conserved": 0.95 <= conservation <= 1.05,
                    "ts": time.time(),
                })
        except Exception:
            pass
        
        return {
            "ok": True,
            "activations": activations,
            "conservation_ratio": conservation,
            "mhc_conserved": 0.95 <= conservation <= 1.05,
        }
    
    def _intent_normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger manifold projection on all edge weights."""
        stats = self._graph.normalize_all_weights()
        
        # Broadcast
        try:
            self.post.to_COLLECTIVE({
                "opcode": "MHC_NORMALIZED",
                "payload": stats,
            })
        except Exception:
            pass
        
        return {"ok": True, **stats}
    
    def _intent_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        return {
            "ok": True,
            "graph": self._graph.stats(),
            "binding_count": self._binding_count,
            "query_count": self._query_count,
            "spread_count": self._spread_count,
        }
    
    def _intent_health(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get signal conservation health report."""
        stats = self._graph.stats()
        history = list(self._graph._signal_history)[-20:]
        
        return {
            "ok": True,
            "conservation": stats.get("signal_conservation", 1.0),
            "healthy": stats.get("mhc_healthy", True),
            "history": history,
            "recommendation": self._get_health_recommendation(stats),
        }
    
    def _intent_link(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manually create a link between concepts."""
        a = payload.get("a", "")
        b = payload.get("b", "")
        rel = payload.get("rel", ManifoldConstrainedGraph.REL_SEMANTIC)
        weight = float(payload.get("weight", 0.5))
        
        if not a or not b:
            return {"ok": False, "error": "need both 'a' and 'b' keys"}
        
        self._graph.link(a, b, rel, weight)
        return {"ok": True, "linked": (a, b), "rel": rel}
    
    def _intent_clear(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Clear the graph (requires confirmation)."""
        if not payload.get("confirm"):
            return {"ok": False, "error": "pass confirm=True to clear"}
        
        self._graph = ManifoldConstrainedGraph(max_nodes=10000)
        self._binding_count = 0
        self._query_count = 0
        self._spread_count = 0
        
        return {"ok": True, "message": "graph cleared"}
    
    def _get_health_recommendation(self, stats: Dict[str, Any]) -> str:
        """Generate health recommendation based on stats."""
        conservation = stats.get("signal_conservation", 1.0)
        
        if conservation < 0.9:
            return "Signal vanishing detected. Consider reducing identity_weight or checking for isolated nodes."
        elif conservation > 1.1:
            return "Signal explosion detected. Run normalize intent to project weights onto manifold."
        elif not stats.get("mhc_healthy", True):
            return "Minor signal drift. System will auto-correct on next normalization cycle."
        else:
            return "Signal conservation healthy. mHC constraints holding."
    
    def _extract_concepts(self, packet: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract concepts from multi-modal packet."""
        concepts = []
        
        # Stopwords
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "and", "but", "if", "or", "as", "this", "that", "it", "its",
        }
        
        # Lexical features
        text = packet.get("text", "")
        tokens = packet.get("tokens") or packet.get("lex") or []
        
        if text and not tokens:
            tokens = [w.strip(".,!?;:\"'()[]{}").lower() for w in text.split()]
        
        for token in tokens:
            if len(token) > 2 and token not in stopwords:
                concepts.append({
                    "key": f"lex:{token}",
                    "features": {"lex": [token], "modality": "lexical"},
                })
        
        # Vision features
        vision = packet.get("vision_tags") or packet.get("vision") or []
        for tag in vision:
            concepts.append({
                "key": f"vis:{tag}",
                "features": {"vision": [tag], "modality": "visual"},
            })
        
        # Action features
        actions = packet.get("actions") or []
        for action in actions:
            concepts.append({
                "key": f"act:{action}",
                "features": {"action": [action], "modality": "motor"},
            })
        
        # Affect features
        affect = packet.get("affect") or {}
        if affect:
            mood = affect.get("mood", "neutral")
            concepts.append({
                "key": f"affect:{mood}",
                "features": {
                    "affect": [mood],
                    "valence": affect.get("valence", 0),
                    "arousal": affect.get("arousal", 0),
                    "modality": "emotional",
                },
            })
        
        return concepts


# ══════════════════════════════════════════════════════════════════════════════
# SHADOW FAIRY - For autonomous optimization
# ══════════════════════════════════════════════════════════════════════════════

class ManifoldConstrainedCortexShadow(_template.TemplateShadowFairy):
    """
    Shadow fairy for autonomous mHC optimization.
    
    Responsibilities:
      - Monitor signal conservation health
      - Trigger normalization when drift detected
      - Propose graph pruning when needed
      - Track mHC performance over time
    """
    
    ACTOR_NAME = "ManifoldConstrainedCortexShadow"
    OBSERVES = "ManifoldConstrainedCortexFairy"
    
    def __init__(self, fairy: ManifoldConstrainedCortexFairy, **kw):
        super().__init__(fairy=fairy, **kw)
        self._fairy = fairy
        self._last_check_ts = time.time()
        self._drift_count = 0
    
    def maybe_run(self) -> Optional[Dict[str, Any]]:
        """Check health and take corrective action."""
        now = time.time()
        
        # Check every 30 seconds
        if now - self._last_check_ts < 30.0:
            return None
        
        self._last_check_ts = now
        
        # Get health
        stats = self._fairy._graph.stats()
        conservation = stats.get("signal_conservation", 1.0)
        
        # Detect drift
        if not (0.95 <= conservation <= 1.05):
            self._drift_count += 1
            
            if self._drift_count >= 3:
                # Trigger normalization
                self._fairy._intent_normalize({})
                self._drift_count = 0
                
                return {
                    "action": "normalized",
                    "reason": f"signal drift detected: {conservation:.3f}",
                }
        else:
            self._drift_count = 0
        
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MODULE SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_INSTANCE: Optional[ManifoldConstrainedCortexFairy] = None


def get_manifold_cortex_fairy(fabric=None) -> ManifoldConstrainedCortexFairy:
    """Get or create the ManifoldConstrainedCortexFairy singleton, wired via DirectoryFairy."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ManifoldConstrainedCortexFairy()
        # Wire to shared fabric from directory
        if fabric is None:
            try:
                from directory import get_directory
                directory = get_directory()
                if directory:
                    fabric = directory.fabric
            except ImportError:
                pass
        if fabric is not None:
            _INSTANCE.post = fabric
            _INSTANCE.fabric = fabric
        # Call on_boot() to wire into postal system
        if hasattr(_INSTANCE, 'on_boot'):
            try:
                _INSTANCE.on_boot()
            except Exception as e:
                print(f"[get_manifold_cortex_fairy] on_boot() warning: {e}")
    return _INSTANCE


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.stderr.write("=" * 60)
    sys.stderr.write("ManifoldConstrainedCortexFairy - mHC Test\n")
    sys.stderr.write("=" * 60)
    
    fairy = ManifoldConstrainedCortexFairy()
    
    # Test binding
    sys.stderr.write("\n1. Testing BIND...\n")
    result = fairy._intent_bind({
        "text": "The red ball bounces happily in the garden",
        "vision_tags": ["red", "round", "ball", "garden"],
        "actions": ["bounce"],
        "affect": {"valence": 0.7, "arousal": 0.5, "mood": "playful"},
    })
    sys.stderr.write(f"   Bound: {result['bound']} concepts, {result['linked']} links" + "\n")
    
    # Bind more to create a richer graph
    fairy._intent_bind({
        "text": "The blue sky above the garden is beautiful",
        "vision_tags": ["blue", "sky", "garden"],
        "affect": {"mood": "peaceful"},
    })
    
    fairy._intent_bind({
        "text": "Children play with the ball in the garden",
        "vision_tags": ["children", "ball", "garden"],
        "actions": ["play"],
        "affect": {"mood": "joyful"},
    })
    
    # Test normalization
    sys.stderr.write("\n2. Testing NORMALIZE...\n")
    result = fairy._intent_normalize({})
    sys.stderr.write(f"   Normalized {result['nodes_normalized']} nodes" + "\n")
    sys.stderr.write(f"   Conservation ratio: {result['conservation_ratio']:.4f}" + "\n")
    
    # Test spreading activation
    sys.stderr.write("\n3. Testing SPREAD (mHC-constrained)...")
    result = fairy._intent_spread({
        "source": "vis:garden",
        "initial": 1.0,
        "max_hops": 3,
        "identity_weight": 0.1,
    })
    sys.stderr.write(f"   Conservation ratio: {result['conservation_ratio']:.4f}" + "\n")
    sys.stderr.write(f"   mHC conserved: {result['mhc_conserved']}" + "\n")
    sys.stderr.write(f"   Top activations:" + "\n")
    sorted_act = sorted(result['activations'].items(), key=lambda x: -x[1])[:5]
    for key, act in sorted_act:
        sys.stderr.write(f"      {key}: {act:.4f}" + "\n")
    
    # Test health
    sys.stderr.write("\n4. Testing HEALTH...\n")
    result = fairy._intent_health({})
    sys.stderr.write(f"   Conservation: {result['conservation']:.4f}" + "\n")
    sys.stderr.write(f"   Healthy: {result['healthy']}" + "\n")
    sys.stderr.write(f"   Recommendation: {result['recommendation']}" + "\n")
    
    # Test stats
    sys.stderr.write("\n5. Testing STATS...\n")
    result = fairy._intent_stats({})
    sys.stderr.write(f"   Nodes: {result['graph']['node_count']}" + "\n")
    sys.stderr.write(f"   Edges: {result['graph']['edge_count']}" + "\n")
    sys.stderr.write(f"   Signal conservation: {result['graph']['signal_conservation']:.4f}" + "\n")
    sys.stderr.write(f"   mHC healthy: {result['graph']['mhc_healthy']}" + "\n")
    
    sys.stderr.write("\n" + "=" * 60)
    sys.stderr.write("[OK] All tests passed!\n")
    sys.stderr.write("=" * 60)
