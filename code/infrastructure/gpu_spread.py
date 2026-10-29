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
import threading

# 2026-10-20 (Nous, gpu_spread_race_1020): the guards (ONE graph build per instance, BOUNDED concurrent spreads, a VRAM floor, an optional
# shared graph) live in gpu_spread_fix.py and are armed only by state/gpu_spread_fix.json. Absent / malformed = every guard OFF = today's code
# path. _gsf is None when that module cannot be imported: every path below is then today's.
try:
    if __package__:
        from . import gpu_spread_fix as _gsf          # imported as infrastructure.gpu_spread (wmh_tools.py)
    else:
        import gpu_spread_fix as _gsf                 # imported bare (portal_gate.py, the interior)
except Exception:
    _gsf = None


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

        # 2026-10-20 (Nous, gpu_spread_race_1020): per-instance guard state. The lock is ALWAYS created here (creating it lazily would itself
        # be a check-then-act under -Xgil=0). Used only when state/gpu_spread_fix.json arms build_lock; set before _load_csr (it sets _csr_ident).
        self._fix_build_lock = threading.Lock()
        self._fix_build_started = None    # (monotonic start, thread name) while a guarded build runs
        self._fix_denied_since = None     # first refusal by the VRAM floor of a cold build
        self._fix_mig_denied_since = None # first refusal by the VRAM floor of a CPU->GPU migration (its own patience clock)
        self._fix_migrate_at = 0.0        # no CPU->GPU migration attempt before this time
        self._weights_real = None         # True when _real_weights read the manifold, False when it fell back to flat 1.0
        self._csr_ident = None            # (realpath, size, mtime_ns, entries) of the CSR bytes this instance loaded, when stable

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

        _fix_st0 = None
        try:
            _fix_st0 = os.stat(self.csr_path)         # gpu_spread_race_1020: identity of the bytes (shared_graph only)
        except Exception:
            pass

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

                try:
                    _fix_st1 = os.stat(self.csr_path)
                    if (_fix_st0 is not None and _fix_st1.st_size == _fix_st0.st_size
                            and _fix_st1.st_mtime_ns == _fix_st0.st_mtime_ns):
                        self._csr_ident = (os.path.realpath(self.csr_path), _fix_st1.st_size, _fix_st1.st_mtime_ns, total_entries)
                except Exception:
                    pass

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
            self._weights_real = True
            return w
        except Exception as _e:
            self._weights_real = False
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

    def refresh_affect(self, fx=None):
        """Re-sync the affect vector -- it mutates via diffusion every consolidation."""
        if fx is not None and fx.build_lock:
            return self._fix_refresh_affect()       # gpu_spread_race_1020: under the build lock, from ONE snapshot
        if self._ma_ready and self._manifold is not None and self._ac_t is not None:
            try:
                self._ac_t = self._load_affect_vec(self._ac_t.device)
                self._ma = (self._src_t, self._dst_t, self._w_t, self._ac_t)
            except Exception:
                pass

    def _spread_max_affect(self, seed_indices, seed_weights, depth, decay, ma=None, fx=None):
        """Max-product (scatter_reduce amax) + real-weights + affect push-pull bias.
        e_new[dst] = max over edges of e[src]*w*decay*(1+K*(ac[dst]-1)); running-max across hops."""
        _src_t, _dst_t, _w_t, _ac_t = ma if ma is not None else self._ma   # one snapshot; never mix devices mid-hop
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
            self.refresh_affect(fx)
        return e

    # ---- gpu_spread_race_1020 (Nous, 2026-10-20) -- the guards. Reached ONLY when state/gpu_spread_fix.json arms them. -----------------
    def _degraded(self, why, seed_indices, depth, t0):
        """What a caller gets when a guard could not give it a slot or a graph: status ok, nothing activated, device 'degraded'. Counted
        and logged (an empty ok must be loud). NEVER the CPU path: every caller treats an ok result as final."""
        try:
            _gsf.note_degraded(why)
        except Exception:
            pass
        try:
            _d = min(self.MAX_HOPS, max(1, depth))
        except Exception:
            _d = 1
        return {"status": "ok", "activated": [], "device": "degraded", "degraded": why,
                "elapsed_ms": round((time.time() - t0) * 1000, 2), "depth": _d,
                "seeds": len(seed_indices), "top_k_found": 0}

    def _fix_wants_migration(self, ma, device):
        """The migration condition of spread() as it was: built on the CPU while the GPU was busy, the GPU is free now."""
        return bool(device == "cuda:0" and not self._force_cpu and ma[0].device.type == "cpu")

    def _fix_copy_mib(self):
        """One device copy of the graph: 20 bytes per CSR entry (src, dst int64 + w float32) + 4 per node (affect)."""
        try:
            return (20.0 * len(self._col) + 4.0 * self.N) / float(1 << 20)
        except Exception:
            return 0.0

    def _fix_share_key(self):
        """Instances share a GPU graph only when they loaded identical CSR bytes (stat before == after the read) AND hold the same manifold
        object. An instance with no manifold never shares (its build would be flat weights)."""
        ci = self._csr_ident
        mm = self._manifold
        if ci is None or mm is None:
            return None
        return (ci[0], ci[1], ci[2], ci[3], self.N, id(mm))

    def _fix_ensure_ma(self, device, fx):
        """build_lock armed: the (src, dst, w, ac) tuple for this spread, built at most ONCE per instance. -> (tuple, None), or (None, why)
        and the caller returns a degraded result. The tuple IS the readiness flag (_build_max_affect publishes it last), so a reader never
        sees half a build. A cold caller waits at most fx.timeout_s for the builder (and not at all for one stuck over 30 s); a CPU->GPU
        migration never waits: the losers keep using the CPU copy. An exception from the builder propagates exactly as it does today (the
        sticky-CPU latch), after the locks are released."""
        ma = self._ma
        if ma is not None and not self._fix_wants_migration(ma, device):
            return ma, None
        cold = ma is None
        lock = self._fix_build_lock
        if cold:
            if not _gsf.acquire_build(lock, fx, self):
                return None, "build_wait"
        else:
            if _gsf._now() < self._fix_migrate_at or not lock.acquire(False):
                return ma, None
        try:
            ma = self._ma                       # THE SECOND CHECK, under the lock
            if ma is not None and not self._fix_wants_migration(ma, device):
                return ma, None
            cold = ma is None
            _t = _gsf._now()
            if not cold:
                self._fix_migrate_at = _t + _gsf.MIGRATE_RETRY_S
            self._fix_build_started = (_t, threading.current_thread().name)
            key = None
            klock = None
            if fx.shared_graph and device == "cuda:0":
                key = self._fix_share_key()
                if key is not None:
                    klock = _gsf.key_lock(key)
                    if klock is None or not klock.acquire(True, fx.timeout_s):
                        key = None
                        klock = None
            try:
                if key is not None:
                    hit = _gsf.shared_get(key)
                    if hit is not None:
                        _ac = self._load_affect_vec(device)
                        self._src_t, self._dst_t, self._w_t, self._ac_t = hit[0], hit[1], hit[2], _ac
                        _adopted = (hit[0], hit[1], hit[2], _ac)
                        self._ma = _adopted
                        self._ma_ready = True
                        _gsf.count("shared_adopt")
                        _log("[GPUSpread] max-affect: adopted the shared GPU graph (same CSR bytes, same manifold), dev=%s" % device)
                        return _adopted, None                 # the tuple we built, not a re-read of self._ma (a latch may have cleared it)
                free = None
                if device == "cuda:0":
                    _ok, free = _gsf.vram_ok(self._fix_copy_mib(), fx, self, cold)
                    if not _ok:
                        return ((None, "vram_floor") if cold else (ma, None))
                if not cold:
                    _log("[GPUSpread] max-affect tensors were built on CPU while the GPU was "
                         "busy; GPU is free now -- rebuilding on cuda:0")
                _gsf.note_build(self, device, "cold" if cold else "migrate", free)
                self._build_max_affect(device)
                self._fix_denied_since = None
                self._fix_mig_denied_since = None
                new = self._ma
                if new is None:
                    # a sticky-CPU latch that did not take the build lock (the switch was flipped OFF in between, or another path) cleared the
                    # tuple between the builder's publish and this read: never hand back a bare None, say why
                    _gsf.count("build_lost")
                    return None, "build_lost"
                if key is not None and self._weights_real is True and new is not None and new[0].device.type == "cuda":
                    _gsf.shared_put(key, new)
                return new, None
            finally:
                if klock is not None:
                    klock.release()
        finally:
            self._fix_build_started = None
            lock.release()

    def _fix_refresh_affect(self):
        """refresh_affect under build_lock: it takes the build lock WITHOUT waiting (busy = skip; the next refresh is
        AFFECT_REFRESH_EVERY spreads away) and publishes (src, dst, w, new ac) from ONE snapshot, so it can never pair old tensors with a
        concurrent rebuild's new ones."""
        lock = self._fix_build_lock
        if not lock.acquire(False):
            return
        try:
            ma = self._ma
            if ma is None or self._manifold is None:
                return
            try:
                new_ac = self._load_affect_vec(ma[3].device)
                self._ac_t = new_ac
                self._ma = (ma[0], ma[1], ma[2], new_ac)
            except Exception:
                pass
        finally:
            lock.release()

    def _fix_latch(self, e, fx, seed_indices, depth, decay, top_k, t0=None):
        """The sticky-CPU latch of spread() under build_lock: the test-and-set of _force_cpu and the reset of the cached tensors happen under
        the build lock, and only the thread that flipped the flag retries (ONE CPU rebuild, not one per failing thread). The retry's
        spread() re-enters this thread's own slot. A lock it cannot get in fx.timeout_s (or a builder wedged over 30 s) = a DEGRADED
        'latch_wait' result, not today's error dict: every gate site sends a non-ok status to the CPU mmap spread, and in the wedge this guard
        exists for that would start the CPU storm (review F3, 10-20). A thread that got the lock but did not flip (another thread already
        did) keeps today's error dict."""
        flipped = False
        if not _gsf.acquire_build(self._fix_build_lock, fx, self):
            return self._degraded("latch_wait", seed_indices, depth, t0 if t0 is not None else time.time())
        try:
            if not self._force_cpu:
                self._force_cpu = True
                flipped = True
                self._graph_gpu = None
                self._src_t = None; self._dst_t = None; self._w_t = None; self._ac_t = None
                self._ma = None
                self._ma_ready = False
                try:
                    _k = self._fix_share_key()
                    if _k is not None:
                        _gsf.shared_drop(_k)
                except Exception:
                    pass
        finally:
            self._fix_build_lock.release()
        if flipped:
            _log("[GPUSpread] Falling back to CPU (sticky) -- dropping GPU-cached tensors, rebuilding on CPU...")
            try:
                return self.spread(seed_indices, depth, decay, top_k)
            except Exception as e2:
                _log(f"[GPUSpread] CPU fallback also failed: {e2}")
        return {"status": "error", "message": str(e)}

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
        # 2026-10-20 (Nous, gpu_spread_race_1020): with every guard OFF (the default) this is today's body, run unchanged by _spread_body.
        fx = None
        try:
            if _gsf is not None:
                fx = _gsf.switch()
        except Exception:
            fx = None
        if fx is None or not fx.spread_armed or not self._loaded:
            return self._spread_body(seed_indices, depth, decay, top_k, seed_weights, long_range, None)
        _gsf.on_call()
        if fx.spread_slots is None:
            return self._spread_body(seed_indices, depth, decay, top_k, seed_weights, long_range, fx)
        _fx_t0 = time.time()
        with _gsf.slot(fx) as (_fx_ok, _fx_why):
            if not _fx_ok:
                return self._degraded(_fx_why, seed_indices, depth, _fx_t0)
            return self._spread_body(seed_indices, depth, decay, top_k, seed_weights, long_range, fx)

    def _spread_body(self, seed_indices, depth, decay, top_k, seed_weights, long_range, fx=None):
        """spread() as it was before gpu_spread_race_1020. fx None = exactly those statements; fx = the armed guards."""
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
                _fx_ma = None
                if fx is not None and fx.build_lock:
                    # gpu_spread_race_1020: ONE build per instance (double-checked), bounded waits, optional VRAM floor / shared graph
                    _fx_ma, _fx_why = self._fix_ensure_ma(device, fx)
                    if _fx_ma is None:
                        return self._degraded(_fx_why or "unknown", seed_indices, depth, t0)
                elif not self._ma_ready:
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
                activation = self._spread_max_affect(seed_indices, seed_weights, depth, decay, ma=_fx_ma, fx=fx)
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
            if fx is not None and fx.build_lock:
                return self._fix_latch(e, fx, seed_indices, depth, decay, top_k, t0)
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
        _st = {
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
        try:
            if _gsf is not None and _gsf.switch().armed:       # gpu_spread_race_1020: only while a guard is armed
                _st["fix"] = _gsf.stats()
        except Exception:
            pass
        return _st


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
