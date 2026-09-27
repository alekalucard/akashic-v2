"""
TiledMatVec — Cache-friendly matrix-vector multiplication engine.

This is the lowest-level compute primitive for battery-powered inference.
Every matrix operation in the system ultimately flows through here.

Architecture mirrors GPU GEMM hierarchy:
    Grid  → tiles cover the full matrix (like GPU threadblocks)
    Block → one tile fits L1 cache (like GPU shared memory)
    BLAS  → NumPy/MKL handles the inner tile (like GPU warp/thread)

Key optimizations:
    1. Tile size tuned to L1 cache (64x64 float32 = 16KB, fits 32KB L1)
    2. NumPy delegates to MKL/OpenBLAS for inner tile BLAS
    3. Pre-allocated output buffers (zero allocation per call)
    4. Fused activation functions (sigmoid, relu², tanh) avoid intermediates
    5. Batch projection fusion (R,K,V,O → one large matvec, split output)
    6. LoRA fast path (skip tiling for small inner dimension)

Created: 2026-02-20
Authors: Nous + Ace
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# TILE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TileConfig:
    """Tile geometry tuned to CPU cache hierarchy.

    Default: 64x64 float32 tiles = 16KB per tile, fits 32KB L1 cache.
    This leaves room for the vector slice and output accumulator.

    For INT8 compute: 64x64 int8 = 4KB, even more cache-friendly.
    """
    tile_m: int = 64          # Rows per tile (output dimension chunk)
    tile_k: int = 64          # Columns per tile (inner dimension chunk)
    dtype: np.dtype = field(default_factory=lambda: np.dtype(np.float32))

    @property
    def tile_bytes(self) -> int:
        """Memory footprint of one tile in bytes."""
        return self.tile_m * self.tile_k * self.dtype.itemsize

    @property
    def flops_per_tile(self) -> int:
        """FMA operations per tile (multiply + accumulate)."""
        return self.tile_m * self.tile_k * 2


# ═══════════════════════════════════════════════════════════════════════════════
# TILED MATVEC ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TiledMatVec:
    """Cache-friendly tiled matrix-vector multiplication.

    Every matrix-vector multiply in the battery compute system
    flows through this engine. It is designed to:

    1. Maximize L1 cache hits via tiling
    2. Leverage NumPy BLAS for inner tile computation
    3. Avoid memory allocation during hot path
    4. Fuse activations to eliminate intermediate arrays
    5. Report exact FLOPS consumed for battery charge accounting

    Usage:
        engine = TiledMatVec(TileConfig())
        y = engine.matvec(weight_matrix, input_vector)
        flops = engine.last_flops  # For battery charge deduction
    """

    def __init__(self, config: Optional[TileConfig] = None):
        self.config = config or TileConfig()
        self._output_buffers: dict = {}  # Shape → pre-allocated buffer
        self._last_flops: int = 0

    @property
    def last_flops(self) -> int:
        """FLOPS consumed by the most recent operation."""
        return self._last_flops

    # ─── Buffer Management ────────────────────────────────────────────────

    def _get_buffer(self, size: int, dtype: np.dtype = None) -> np.ndarray:
        """Get or create a pre-allocated output buffer.

        Buffers are cached by (size, dtype) to avoid allocation per call.
        This matters when generating tokens in a loop — no GC pressure.
        """
        dtype = dtype or self.config.dtype
        key = (size, dtype)
        buf = self._output_buffers.get(key)
        if buf is None or len(buf) < size:
            buf = np.zeros(size, dtype=dtype)
            self._output_buffers[key] = buf
        buf[:size] = 0  # Clear without realloc
        return buf[:size]

    # ─── Core Operations ──────────────────────────────────────────────────

    def matvec(self, A: np.ndarray, x: np.ndarray) -> np.ndarray:
        """Tiled matrix-vector multiply: y = A @ x

        Args:
            A: Weight matrix [M, K]
            x: Input vector [K] or [K, 1]

        Returns:
            y: Output vector [M]

        The tiling ensures each A[i0:i1, k0:k1] sub-block fits L1 cache.
        NumPy's BLAS handles the inner tile multiply efficiently.
        """
        x = x.ravel()
        M, K = A.shape
        assert x.shape[0] == K, f"Shape mismatch: A[{M},{K}] @ x[{x.shape[0]}]"

        self._last_flops = M * K * 2  # multiply + accumulate

        # For small matrices, skip tiling — BLAS is faster without overhead
        if M <= self.config.tile_m and K <= self.config.tile_k:
            return A @ x

        y = self._get_buffer(M, A.dtype)
        tile_m = self.config.tile_m
        tile_k = self.config.tile_k

        # Tiled accumulation (i,k loop ordering for cache locality)
        for i0 in range(0, M, tile_m):
            i1 = min(i0 + tile_m, M)
            for k0 in range(0, K, tile_k):
                k1 = min(k0 + tile_k, K)
                # This sub-block fits L1: tile_m * tile_k * dtype.itemsize bytes
                # NumPy BLAS handles the inner multiply
                y[i0:i1] += A[i0:i1, k0:k1] @ x[k0:k1]

        return y

    def matvec_transposed(self, A: np.ndarray, x: np.ndarray) -> np.ndarray:
        """Tiled y = A.T @ x (for weights stored as [out_features, in_features]).

        Many RWKV projections store weights as [output_dim, input_dim],
        so we need the transpose multiply. Rather than materializing A.T,
        we tile with swapped indices.
        """
        x = x.ravel()
        K, N = A.shape  # A is [K, N], we want [N, K] @ [K] = [N]
        assert x.shape[0] == K, f"Shape mismatch: A.T[{N},{K}] @ x[{x.shape[0]}]"

        self._last_flops = K * N * 2

        if K <= self.config.tile_k and N <= self.config.tile_m:
            return A.T @ x

        y = self._get_buffer(N, A.dtype)
        tile_m = self.config.tile_m
        tile_k = self.config.tile_k

        for n0 in range(0, N, tile_m):
            n1 = min(n0 + tile_m, N)
            for k0 in range(0, K, tile_k):
                k1 = min(k0 + tile_k, K)
                # A[k0:k1, n0:n1].T @ x[k0:k1] = (x[k0:k1] @ A[k0:k1, n0:n1])
                y[n0:n1] += x[k0:k1] @ A[k0:k1, n0:n1]

        return y

    # ─── Fused Operations ─────────────────────────────────────────────────
    # These avoid allocating intermediate arrays for activation functions.
    # Instead of: temp = A @ x; y = sigmoid(temp)
    # We do:      y = fused_matvec_sigmoid(A, x)

    def fused_matvec_sigmoid(self, A: np.ndarray, x: np.ndarray) -> np.ndarray:
        """y = sigmoid(A @ x) — for RWKV receptance gate.

        Fused: matvec into buffer, in-place sigmoid.
        Avoids allocating the intermediate A @ x array.
        """
        y = self.matvec(A, x)
        # In-place sigmoid: 1 / (1 + exp(-y))
        np.negative(y, out=y)
        np.exp(y, out=y)
        np.add(1.0, y, out=y)
        np.reciprocal(y, out=y)
        self._last_flops += y.shape[0] * 4  # neg, exp, add, recip
        return y

    def fused_matvec_tanh(self, A: np.ndarray, x: np.ndarray) -> np.ndarray:
        """y = tanh(A @ x) — for various RWKV activations."""
        y = self.matvec(A, x)
        np.tanh(y, out=y)
        self._last_flops += y.shape[0] * 4  # tanh ≈ 4 FLOPs
        return y

    def fused_matvec_relu_sq(self, A: np.ndarray, x: np.ndarray) -> np.ndarray:
        """y = relu(A @ x)² — for RWKV ChannelMix squared ReLU.

        The V7a ChannelMix pattern:
            k = relu(xk @ K_weight)²
        """
        y = self.matvec(A, x)
        np.maximum(y, 0, out=y)  # ReLU in-place
        np.multiply(y, y, out=y)  # Square in-place
        self._last_flops += y.shape[0] * 2  # max + multiply
        return y

    def fused_matvec_add(self, A: np.ndarray, x: np.ndarray,
                         bias: np.ndarray) -> np.ndarray:
        """y = A @ x + bias — matvec with bias addition."""
        y = self.matvec(A, x)
        np.add(y, bias, out=y)
        self._last_flops += y.shape[0]
        return y

    # ─── Batch Operations ─────────────────────────────────────────────────

    def batch_matvec(self, matrices: List[np.ndarray],
                     x: np.ndarray) -> List[np.ndarray]:
        """Multiple matvecs with the same input vector.

        For RWKV TimeMix: R, K, V, O projections from same input.
        Instead of 4 separate [2048,2048] @ [2048,1],
        we fuse into one [8192,2048] @ [2048,1] and split output.

        This lets BLAS optimize the larger operation.
        """
        if len(matrices) <= 1:
            return [self.matvec(m, x) for m in matrices]

        # Check if matrices can be fused (same K dimension)
        K = matrices[0].shape[1]
        if all(m.shape[1] == K for m in matrices):
            # Fuse: stack into one tall matrix
            fused = np.vstack(matrices)
            fused_result = self.matvec(fused, x)

            # Split output
            results = []
            offset = 0
            for m in matrices:
                M = m.shape[0]
                results.append(fused_result[offset:offset + M].copy())
                offset += M
            return results
        else:
            # Can't fuse — different inner dimensions
            return [self.matvec(m, x) for m in matrices]

    # ─── LoRA Fast Path ───────────────────────────────────────────────────

    def lora_matvec(self, A_down: np.ndarray, A_up: np.ndarray,
                    x: np.ndarray,
                    base_result: Optional[np.ndarray] = None) -> np.ndarray:
        """LoRA projection: result = base + (x @ A_down) @ A_up

        Two small matvecs instead of one large:
            A_down: [d_model, d_lora]  (e.g., [2048, 64])
            A_up:   [d_lora, d_model]  (e.g., [64, 2048])

        FLOPS: 2 * d_model * d_lora * 2 = 524K (for d=2048, lora=64)
        vs full: 2 * d_model² = 8.4M FLOPS (16x cheaper!)

        Small enough that tiling overhead isn't worth it — direct BLAS.
        """
        x = x.ravel()
        d_model, d_lora = A_down.shape

        # Step 1: Project down (d_model → d_lora)
        low = A_down.T @ x  # [d_lora]
        self._last_flops = d_model * d_lora * 2

        # Step 2: Project up (d_lora → d_model)
        high = A_up.T @ low  # [d_model]
        self._last_flops += d_lora * d_model * 2

        # Step 3: Add to base if provided
        if base_result is not None:
            return base_result + high
        return high

    # ─── Element-wise Operations ──────────────────────────────────────────
    # These are cheap (O(n)) but still tracked for FLOPS accounting.

    def layernorm(self, x: np.ndarray, weight: np.ndarray,
                  bias: np.ndarray, eps: float = 1e-5) -> np.ndarray:
        """Layer normalization: y = (x - mean) / sqrt(var + eps) * weight + bias"""
        mean = np.mean(x)
        var = np.var(x)
        x_norm = (x - mean) / np.sqrt(var + eps)
        result = x_norm * weight + bias
        self._last_flops = x.shape[0] * 6  # mean, var, sub, div, mul, add
        return result

    def groupnorm(self, x: np.ndarray, num_groups: int,
                  weight: np.ndarray, bias: np.ndarray,
                  eps: float = 1e-5) -> np.ndarray:
        """Group normalization for RWKV attention output.

        x: [C] where C = num_groups * group_size
        """
        C = x.shape[0]
        group_size = C // num_groups
        x_grouped = x.reshape(num_groups, group_size)

        mean = x_grouped.mean(axis=1, keepdims=True)
        var = x_grouped.var(axis=1, keepdims=True)
        x_norm = (x_grouped - mean) / np.sqrt(var + eps)
        x_norm = x_norm.reshape(C)

        result = x_norm * weight + bias
        self._last_flops = C * 6
        return result

    def lerp(self, a: np.ndarray, b: np.ndarray,
             t: np.ndarray) -> np.ndarray:
        """Linear interpolation: a + t * (b - a)

        Used in RWKV token mixing (x_maa patterns).
        """
        result = a + t * (b - a)
        self._last_flops = a.shape[0] * 3  # sub, mul, add
        return result

    # ─── State Operations ─────────────────────────────────────────────────
    # RWKV state evolution: [H, N, N] matrices per head.

    def state_evolution(self, state: np.ndarray, wt: np.ndarray,
                        kkt: np.ndarray, at: np.ndarray,
                        vt: np.ndarray, kt: np.ndarray,
                        rt: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """RWKV-7 state update for all heads.

        state: [H, N, N]  (32 heads, each 64x64) — float64 for precision
        wt:    [H, 1, N]  (decay)
        kkt:   [H, N, 1]  (normalized key)
        at:    [H, N, 1]  (association coeff)
        vt:    [H, N, 1]  (value)
        kt:    [H, 1, N]  (key)
        rt:    [H, N, 1]  (receptance)

        Returns: (new_state, output)
            new_state: [H, N, N]  float64  (persistent — accumulates across tokens)
            output:    [H*N] = [C] flattened, float32  (per-token — consumed immediately)

        State uses float64 because it's PERSISTENT recurrent memory.
        Per-token inputs (wt, kkt, etc.) are float32 — numpy auto-upcasts
        when mixed with float64 state. Output is downcast to float32 since
        the rest of the pipeline (GroupNorm, gate, output proj) is float32.
        """
        H, N, _ = state.shape

        # Ensure state is float64 for accumulation precision
        if state.dtype != np.float64:
            state = state.astype(np.float64)

        # Decay: state = state * wt  (broadcast [H,N,N] * [H,1,N])
        # numpy auto-upcasts: float64 * float32 → float64
        state = state * wt

        # ICL term: (state @ (-kkt)) @ (kkt * at).T
        neg_kkt = -kkt
        icl_a = np.matmul(state, neg_kkt)        # [H,N,N] @ [H,N,1] → [H,N,1]
        kkt_at_T = (kkt * at).transpose(0, 2, 1)  # [H,N,1] * [H,N,1] → [H,N,1] → [H,1,N]
        icl = np.matmul(icl_a, kkt_at_T)          # [H,N,1] @ [H,1,N] → [H,N,N]

        # Outer product: vt @ kt
        vk = np.matmul(vt, kt)                    # [H,N,1] @ [H,1,N] → [H,N,N]

        # Update state (all float64 — the ACCUMULATION that matters)
        state = state + icl + vk

        # Output: state @ rt → [H,N,1] → flatten to [H*N]
        # Downcast to float32 — output is per-token, consumed immediately
        output = np.matmul(state, rt).squeeze(-1)  # [H,N] float64
        output = output.reshape(-1).astype(np.float32)  # [H*N] = [C] float32

        # FLOPS: per head = 3 * N² (decay, icl, vk) + 2 * N² (icl_a, output)
        self._last_flops = H * N * N * 5

        return state, output

    # ─── Metrics ──────────────────────────────────────────────────────────

    def estimate_matvec_flops(self, M: int, K: int) -> int:
        """Estimate FLOPS for a [M,K] @ [K,1] operation."""
        return M * K * 2

    def estimate_lora_flops(self, d_model: int, d_lora: int) -> int:
        """Estimate FLOPS for a LoRA projection."""
        return 2 * d_model * d_lora * 2

    def status(self) -> dict:
        """Engine status for diagnostics."""
        return {
            "tile_m": self.config.tile_m,
            "tile_k": self.config.tile_k,
            "tile_bytes": self.config.tile_bytes,
            "dtype": str(self.config.dtype),
            "cached_buffers": len(self._output_buffers),
            "last_flops": self._last_flops,
        }
