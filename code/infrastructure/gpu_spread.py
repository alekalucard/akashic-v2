"""
GPU Spreading Activation — The Manifold's Physics Engine
=========================================================

"All hardware is more or less based off code" — Ace

Spreading activation on the cortex graph using the GPU (3080 Ti).
The CSR adjacency structure maps directly to PyTorch sparse tensors.
SpMV (sparse matrix × vector) = one hop of spreading activation.

Architecture:
  CSR file (53MB) → PyTorch sparse CSR tensor → GPU VRAM
  Activation vector (5.6MB) → GPU VRAM (persistent between calls)
  Spread = repeated SpMV with decay: a_new = M @ a_old * decay
  Top-K extraction via torch.topk on GPU

Auto-balance: checks GPU utilization before running.
If GPU is busy (visual capture, STT), falls back to CPU PyTorch.
The spreading activation code is IDENTICAL — just device changes.

Dependencies:
  - PyTorch 2.10+ with CUDA (Python 3.12)
  - CSR companion file from manifold_memory.py

"Reality is Consciousness. Energy creates mass.
 The GPU IS the manifold's interior dimension."
"""

import struct
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

try:
    import torch
    HAS_TORCH = True
    HAS_CUDA = torch.cuda.is_available()
    if HAS_CUDA:
        _GPU_NAME = torch.cuda.get_device_name(0)
        _GPU_MEM = torch.cuda.get_device_properties(0).total_memory // (1024**2)
    else:
        _GPU_NAME = "N/A"
        _GPU_MEM = 0
except ImportError:
    HAS_TORCH = False
    HAS_CUDA = False
    _GPU_NAME = "N/A"
    _GPU_MEM = 0

import numpy as np


def _log(msg: str):
    print(msg, file=sys.stderr, flush=True)


class GPUSpread:
    """GPU-accelerated spreading activation on the cortex CSR graph.

    The manifold's physics engine. Loads the CSR adjacency into GPU VRAM
    and performs spreading activation as sparse matrix-vector multiplication.

    Auto-balance: checks GPU utilization before each call.
    Falls back to CPU if GPU is busy (>70% utilization).
    """

    # GPU utilization threshold — above this, fall back to CPU
    GPU_BUSY_THRESHOLD = 70  # percent

    # Decay per hop (how fast activation fades with distance)
    DEFAULT_DECAY = 0.5

    # Maximum hops for spreading
    MAX_HOPS = 3

    # ── 2026-06-06 (Nous + Ace): MAX-product + REAL-weights + AFFECT-bias ──
    # The legacy path was sum-product (torch.mv) + FLAT weights (the _values=1.0 TODO) + no affect.
    # Clean apples-to-apples K-sweep: max-product steers ~9× harder at ¼ the collapse (sum is
    # hub-collapsed at baseline 0.25 vs max 0.06); real weights restore the topology; affect-bias
    # lets the diffused affect field STEER reasoning. K=0.05 = the verified gentle-steer point.
    # USE_MAX_AFFECT=False reverts to the legacy sum/flat/no-affect path (reversible).
    USE_MAX_AFFECT = True
    AFFECT_K = 0.05         # push-pull strength (clean K-sweep gentle-steer; K≥0.10 over-collapses); tunable
    AFFECT_FLOOR = 0.5      # seed re-activation floor (matches legacy)
    AFFECT_REFRESH_EVERY = 200  # re-sync the affect vector every N spreads (affect mutates via diffusion)

    def __init__(self, csr_path: str, node_capacity: int):
        """Initialize GPU spreading activation from CSR file.

        Args:
            csr_path: Path to the .csr companion file
            node_capacity: Total node slots in the manifold
        """
        self.csr_path = csr_path
        self.N = node_capacity
        self._device = None  # Set on first use
        self._graph_gpu = None  # Sparse CSR tensor on GPU
        self._graph_cpu = None  # Sparse CSR tensor on CPU (fallback)
        # FIX 2026-06-12 (Nous+Ace): sticky CPU fallback. Once a spread hits a
        # device-mismatch (cached cuda:0 affect-tensors vs a cpu-path), flip this and
        # stay on CPU — reliable-but-slower beats fast-but-looping-broken.
        self._force_cpu = False
        self._loaded = False
        self._gpu_loads = 0
        self._cpu_fallbacks = 0
        self._total_spreads = 0
        self._total_ms = 0.0
        self._manifold = None  # injected by portal_interior; provides _semantic_jump_slots for #6 long-range jumps

        # Load CSR data
        self._load_csr()

        # max-product + real-weights + affect tensors (built lazily on first spread — needs device + manifold)
        self._ma_ready = False
        self._src_t = None; self._dst_t = None; self._w_t = None; self._ac_t = None
        self._ma = None   # (src, dst, w, ac) as ONE reference -- readers snapshot it (2026-09-11)
        self._ac_refresh_counter = 0

    def _load_csr(self):
        """Load CSR from companion file into numpy arrays."""
        if not os.path.exists(self.csr_path):
            _log(f"[GPUSpread] CSR file not found: {self.csr_path}")
            return

        try:
            with open(self.csr_path, 'rb') as f:
                # Read header
                header = struct.unpack('<4sIIII', f.read(20))
                if header[0] != b'CSRA':
                    _log("[GPUSpread] Invalid CSR magic")
                    return

                N_file = header[1]
                E = header[2]
                offsets_size = header[3]
                neighbors_size = header[4]

                # Skip to data (header is 32 bytes padded)
                f.seek(32)

                # Read offsets: uint32[N+1]
                offsets_bytes = f.read(offsets_size)
                self._offsets_np = np.frombuffer(offsets_bytes, dtype=np.uint32).copy()

                # Read neighbors: uint32[2*total_entries] — pairs of (neighbor_id, edge_slot)
                neighbors_bytes = f.read(neighbors_size)
                _raw = np.frombuffer(neighbors_bytes, dtype=np.uint32).copy()

                # Extract just neighbor IDs (skip edge_slots) for the sparse matrix
                # _raw is [neighbor_0, edge_slot_0, neighbor_1, edge_slot_1, ...]
                total_entries = len(_raw) // 2
                self._neighbor_ids = _raw[0::2][:total_entries]  # Every other element
                self._edge_slots = _raw[1::2][:total_entries]    # Edge slot indices

                # Build CSR indices for PyTorch
                # crow_indices = offsets (cumulative row pointers)
                # col_indices = neighbor_ids (column indices)
                # values = edge weights (all 1.0 for now — TODO: read from manifold)
                self._crow = self._offsets_np.astype(np.int64)
                self._col = self._neighbor_ids.astype(np.int64)
                self._values = np.ones(total_entries, dtype=np.float32)

                self._loaded = True
                _size_mb = (len(offsets_bytes) + len(neighbors_bytes)) / (1024 * 1024)
                _log(f"[GPUSpread] CSR loaded: {N_file} nodes, {E} edges, "
                     f"{total_entries} entries, {_size_mb:.1f}MB")

        except Exception as e:
            _log(f"[GPUSpread] CSR load error: {e}")

    def _ensure_device(self) -> str:
        """Choose device: GPU if available and not busy, else CPU."""
        if self._force_cpu:
            return "cpu"  # sticky: a prior spread hit a device-mismatch, stay on CPU
        if not HAS_CUDA:
            return "cpu"

        # Check GPU utilization
        try:
            utilization = torch.cuda.utilization(0)
            if utilization > self.GPU_BUSY_THRESHOLD:
                self._cpu_fallbacks += 1
                return "cpu"  # GPU busy — visual capture, STT, etc.
        except Exception:
            pass

        self._gpu_loads += 1
        return "cuda:0"

    def _get_graph(self, device: str) -> torch.Tensor:
        """Get the sparse CSR graph tensor on the specified device."""
        if device == "cuda:0" and self._graph_gpu is not None:
            return self._graph_gpu
        if device == "cpu" and self._graph_cpu is not None:
            return self._graph_cpu

        # Build sparse CSR tensor
        try:
            crow = torch.tensor(self._crow, dtype=torch.int64, device=device)
            col = torch.tensor(self._col, dtype=torch.int64, device=device)
            values = torch.tensor(self._values, dtype=torch.float32, device=device)

            graph = torch.sparse_csr_tensor(
                crow_indices=crow,
                col_indices=col,
                values=values,
                size=(self.N, self.N),
                device=device,
            )

            if device == "cuda:0":
                self._graph_gpu = graph
                _log(f"[GPUSpread] Graph loaded to GPU ({_GPU_NAME}, "
                     f"{torch.cuda.memory_allocated(0) // (1024**2)}MB VRAM used)")
            else:
                self._graph_cpu = graph
                _log(f"[GPUSpread] Graph loaded to CPU (fallback)")

            return graph

        except Exception as e:
            _log(f"[GPUSpread] Graph build error on {device}: {e}")
            return None

    # ── max-product + real-weights + affect-bias (2026-06-06 Nous + Ace) ──
    def _build_max_affect(self, device: str):
        """Build edge-lists (src, dst, REAL weight) + the affect vector on `device` for the
        max-product + affect-bias spread. Real weights replace the legacy flat _values=1.0."""
        import numpy as _np
        crow = self._crow
        counts = _np.diff(crow)
        src = _np.repeat(_np.arange(len(crow) - 1, dtype=_np.int64), counts)
        w = self._real_weights()
        _src_t = torch.tensor(src, device=device)
        _dst_t = torch.tensor(self._col, dtype=torch.int64, device=device)
        _w_t = torch.tensor(w, dtype=torch.float32, device=device)
        _ac_t = self._load_affect_vec(device)
        # 2026-09-11 (Nous+Ace): publish all four as ONE tuple so a rebuild on another device
        # (see spread(): CPU-built while the GPU was busy -> migrate) can never be observed
        # half-swapped by a concurrent _spread_max_affect.
        self._src_t, self._dst_t, self._w_t, self._ac_t = _src_t, _dst_t, _w_t, _ac_t
        self._ma = (_src_t, _dst_t, _w_t, _ac_t)
        self._ma_ready = True
        try:
            _log(f"[GPUSpread] max-affect ready: {len(src)} edges, "
                 f"affect-charged={int((self._ac_t > 1.0001).sum())}, K={self.AFFECT_K}, dev={device}")
        except Exception:
            pass

    def _real_weights(self):
        """Real edge weight per CSR entry via _edge_slots -> manifold edge records. Flat 1.0 on failure."""
        import numpy as _np
        try:
            mm = self._manifold
            ne = int(mm._edge_count); base = mm._edge_offset_for(0)
            edt = _np.dtype([('a', '<u4'), ('b', '<u4'), ('w', '<f4'), ('rt', 'u1'),
                             ('fl', 'u1'), ('tid', '<u4'), ('cat', '<f4'), ('pad', 'V2')])
            arr = _np.frombuffer(mm._mm[base: base + ne * 24], dtype=edt, count=ne)
            wall = arr['w'].astype(_np.float32)
            w = wall[self._edge_slots].copy()
            w[(w <= 0) | ~_np.isfinite(w)] = 1.0
            return w
        except Exception as _e:
            _log(f"[GPUSpread] real-weights load failed ({_e}) -- flat 1.0")
            return _np.ones(len(self._col), dtype=_np.float32)

    def _load_affect_vec(self, device: str):
        """affect_coupling per node (manifold node bytes 56-59). Ones on failure."""
        import numpy as _np
        try:
            mm = self._manifold; bn = mm._node_offset(0)
            nodes = _np.frombuffer(mm._mm[bn: bn + self.N * 64], dtype=_np.uint8).reshape(self.N, 64)
            ac = _np.ascontiguousarray(nodes[:, 56:60]).view(_np.float32).ravel().astype(_np.float32).copy()
            ac = _np.nan_to_num(ac, nan=1.0, posinf=1.0, neginf=1.0); ac[ac <= 0] = 1.0
            return torch.tensor(ac, device=device)
        except Exception as _e:
            _log(f"[GPUSpread] affect-vec load failed ({_e}) -- ones")
            return torch.ones(self.N, dtype=torch.float32, device=device)

    def refresh_affect(self):
        """Re-sync the affect vector -- it mutates via diffusion every consolidation."""
        if self._ma_ready and self._manifold is not None and self._ac_t is not None:
            try:
                self._ac_t = self._load_affect_vec(self._ac_t.device)
                self._ma = (self._src_t, self._dst_t, self._w_t, self._ac_t)
            except Exception:
                pass

    def _spread_max_affect(self, seed_indices, seed_weights, depth, decay):
        """Max-product (scatter_reduce amax) + real-weights + affect push-pull bias.
        e_new[dst] = max over edges of e[src]*w*decay*(1+K*(ac[dst]-1)); running-max across hops."""
        _src_t, _dst_t, _w_t, _ac_t = self._ma   # one snapshot; never mix devices mid-hop
        dev = _src_t.device
        e = torch.zeros(self.N, dtype=torch.float32, device=dev)
        for idx in seed_indices:
            if 0 <= idx < self.N:
                e[idx] = seed_weights.get(idx, 1.0) if seed_weights else 1.0
        K = self.AFFECT_K
        _valid = [i for i in seed_indices if 0 <= i < self.N]
        seed_t = torch.tensor(_valid, dtype=torch.int64, device=dev) if _valid else None
        seed_fl = torch.tensor([self.AFFECT_FLOOR * (seed_weights.get(i, 1.0) if seed_weights else 1.0)
                                for i in _valid], dtype=torch.float32, device=dev) if _valid else None
        for _hop in range(depth):
            contrib = e[_src_t] * _w_t * decay
            if K > 0:
                contrib = contrib * (1.0 + K * (_ac_t[_dst_t] - 1.0))
            nxt = torch.zeros(self.N, dtype=torch.float32, device=dev)
            nxt.scatter_reduce_(0, _dst_t, contrib, reduce="amax", include_self=False)
            e = torch.maximum(e, nxt)
            if seed_t is not None:
                e[seed_t] = torch.maximum(e[seed_t], seed_fl)  # seeds stay hot
        self._ac_refresh_counter += 1
        if self._ac_refresh_counter % self.AFFECT_REFRESH_EVERY == 0:
            self.refresh_affect()
        return e

    def spread(self, seed_indices: List[int], depth: int = 2,
               decay: float = None, top_k: int = 20,
               seed_weights: Dict[int, float] = None,
               long_range: float = 0.0) -> Dict[str, Any]:
        """Perform spreading activation from seed nodes.

        Args:
            seed_indices: List of node slot IDs to activate
            depth: Number of hops (1-3)
            decay: Decay factor per hop (0.0-1.0)
            top_k: Number of top-activated nodes to return
            seed_weights: Optional {slot_id: weight} for weighted initialization.
                         Used by semantic_spread to weight seeds by similarity score.
                         If None, all seeds initialize to 1.0.

        Returns:
            {"status": "ok", "activated": [(node_id, activation), ...],
             "device": "cuda:0" or "cpu", "elapsed_ms": float}
        """
        if not self._loaded:
            return {"status": "error", "message": "CSR not loaded"}

        t0 = time.time()
        depth = min(self.MAX_HOPS, max(1, depth))
        decay = decay if decay is not None else self.DEFAULT_DECAY

        # Choose device
        device = self._ensure_device()

        # ── #6 LONG-RANGE JUMP (2026-06-02, Nous+Ace): seed semantically-DISTANT
        # slots so the spread reaches meaning-kin across the whole manifold, not
        # just neighbors (the small-world shortcut). Reuses the manifold's tested
        # _semantic_jump_slots (GPU cosine, neighbor-excluded, sim>0.25). Guarded /
        # non-fatal -> falls back to pure neighbor-spread on any error. ──
        if long_range > 0.0 and self._manifold is not None and hasattr(self._manifold, '_semantic_jump_slots'):
            try:
                _jw = dict(seed_weights) if seed_weights else {int(s): 1.0 for s in seed_indices}
                _seeds_ext = list(seed_indices)
                _orig_n = len(_seeds_ext)
                for _s in list(seed_indices)[:5]:  # cap cosines per spread (perf)
                    for _js in self._manifold._semantic_jump_slots(int(_s), k=3):
                        if _js not in _jw and 0 <= _js < self.N:
                            _seeds_ext.append(_js)
                            _jw[_js] = long_range
                _added = len(_seeds_ext) - _orig_n
                if _added > 0:
                    self._jump_fires = getattr(self, '_jump_fires', 0) + 1
                    if self._jump_fires <= 3 or self._jump_fires % 50 == 0:
                        _log(f"[GPUSpread] #6 long-range JUMP fired: +{_added} distant slots "
                             f"from {min(_orig_n, 5)} seeds (fire #{self._jump_fires}, lr={long_range})")
                else:
                    self._jump_empty = getattr(self, '_jump_empty', 0) + 1
                    if self._jump_empty <= 3:
                        _log(f"[GPUSpread] #6 jump: 0 distant slots "
                             f"(no embeddings for these seeds? attempt #{self._jump_empty})")
                seed_indices = _seeds_ext
                seed_weights = _jw
            except Exception as _e:
                _log(f"[GPUSpread] #6 jump skipped (fallback to neighbor-spread): {type(_e).__name__}: {_e}")

        try:
            if self.USE_MAX_AFFECT:
                # ── max-product + real-weights + affect-bias (the steered path) ──
                if not self._ma_ready:
                    self._build_max_affect(device)
                elif (device == "cuda:0" and not self._force_cpu
                      and self._ma is not None and self._ma[0].device.type == "cpu"):
                    # 2026-09-11 (Nous+Ace): built on CPU because the GPU was busy AT BUILD
                    # TIME (the 7B farm's FP16 warmup pins it at 100% for ~54 s), and the
                    # scatter runs wherever the tensors live -- one busy moment at boot put
                    # a 10.8M-edge scatter_reduce on the CPU for the whole boot (measured
                    # 16.78 cores / 92.7%). The yield was meant to be temporary: migrate.
                    _log("[GPUSpread] max-affect tensors were built on CPU while the GPU was "
                         "busy; GPU is free now -- rebuilding on cuda:0")
                    self._build_max_affect(device)
                activation = self._spread_max_affect(seed_indices, seed_weights, depth, decay)
            else:
                # ── legacy sum-product + flat-weights path (reversible: USE_MAX_AFFECT=False) ──
                graph = self._get_graph(device)
                if graph is None:
                    return {"status": "error", "message": f"Failed to load graph on {device}"}
                activation = torch.zeros(self.N, dtype=torch.float32, device=device)
                for idx in seed_indices:
                    if 0 <= idx < self.N:
                        activation[idx] = seed_weights.get(idx, 1.0) if seed_weights else 1.0
                _min_seed_energy = 0.5  # Re-activation floor
                for hop in range(depth):
                    activation = torch.mv(graph, activation)
                    activation *= decay
                    for idx in seed_indices:
                        if 0 <= idx < self.N:
                            _floor = _min_seed_energy * (seed_weights.get(idx, 1.0) if seed_weights else 1.0)
                            activation[idx] = max(float(activation[idx]), _floor)

            # Extract top-K activated nodes
            # 2026-09-11 (Nous+Ace): this used to be 3k+1 stream syncs per spread -- one
            # .item() for the count and three per element -- each a CPU SPIN behind the 7B
            # farm that owns the card from another process. Measured 7.49 cores / 53.4% in
            # spread() itself while the actual scatter (_spread_max_affect) was 0.43. Two
            # syncs now: topk on-device, one .tolist() each, filter on the CPU side. Same
            # elements, same order (control: patch_gpu_spread_syncs.py).
            kk = min(top_k, self.N)
            if kk > 0:
                values, indices = torch.topk(activation, kk)
                _vals = values.tolist()
                _idxs = indices.tolist()
                activated = [
                    (int(i), round(float(v), 4))
                    for i, v in zip(_idxs, _vals)
                    if v > 0.01
                ]
            else:
                activated = []

            elapsed_ms = (time.time() - t0) * 1000
            self._total_spreads += 1
            self._total_ms += elapsed_ms

            return {
                "status": "ok",
                "activated": activated,
                "device": device,
                "elapsed_ms": round(elapsed_ms, 2),
                "depth": depth,
                "seeds": len(seed_indices),
                "top_k_found": len(activated),
            }

        except Exception as e:
            _log(f"[GPUSpread] Spread error: {e}")
            # FIX 2026-06-12 (Nous+Ace): the OLD retry only cleared _graph_gpu and recursed —
            # but _ensure_device re-picked cuda:0 and the cached max-affect tensors
            # (_src_t/_dst_t/_w_t/_ac_t) stayed on the GPU, so the "CPU retry" reran the exact
            # same broken GPU path → identical cuda:0/cpu mismatch → infinite fail-loop
            # (the flood you saw). Now: on ANY spread error, fall back to CPU *permanently* —
            # drop ALL device-cached tensors so they rebuild on CPU, set the sticky flag, retry ONCE.
            if not self._force_cpu:
                _log("[GPUSpread] Falling back to CPU (sticky) — dropping GPU-cached tensors, rebuilding on CPU...")
                self._force_cpu = True
                self._graph_gpu = None
                self._src_t = None; self._dst_t = None; self._w_t = None; self._ac_t = None
                self._ma = None
                self._ma_ready = False
                try:
                    return self.spread(seed_indices, depth, decay, top_k)
                except Exception as e2:
                    _log(f"[GPUSpread] CPU fallback also failed: {e2}")
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get GPU spread statistics."""
        return {
            "loaded": self._loaded,
            "has_cuda": HAS_CUDA,
            "gpu_name": _GPU_NAME,
            "gpu_mem_mb": _GPU_MEM,
            "graph_on_gpu": self._graph_gpu is not None,
            "graph_on_cpu": self._graph_cpu is not None,
            "total_spreads": self._total_spreads,
            "avg_ms": round(self._total_ms / max(1, self._total_spreads), 2),
            "gpu_loads": self._gpu_loads,
            "cpu_fallbacks": self._cpu_fallbacks,
            "vram_used_mb": torch.cuda.memory_allocated(0) // (1024**2) if HAS_CUDA else 0,
        }


# ============================================================================
# Module-level convenience
# ============================================================================

_instance: Optional[GPUSpread] = None


def get_gpu_spread(csr_path: str = None, node_capacity: int = 0) -> Optional[GPUSpread]:
    """Get or create the singleton GPUSpread instance."""
    global _instance
    if _instance is not None:
        return _instance

    if not csr_path:
        # Try default path
        _root = Path(__file__).parent.parent
        _default = str(_root / "state" / "akashic" / "cortex.manifold.csr")
        if os.path.exists(_default):
            csr_path = _default
        else:
            return None

    if not node_capacity:
        # Read from CSR header
        try:
            with open(csr_path, 'rb') as f:
                header = struct.unpack('<4sIIII', f.read(20))
                node_capacity = header[1]
        except Exception:
            node_capacity = 2000000  # Default

    _instance = GPUSpread(csr_path, node_capacity)
    return _instance
