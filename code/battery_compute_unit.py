"""
BatteryComputeUnit — The capacitor that computes as it discharges.

This is the heart of the battery-as-compute paradigm.
The capacitor's charge IS computational capacity.
Discharging doesn't PERMIT a FLOPS operation — it IS the FLOPS operation.

Philosophy (Ace):
    "The only difference between hardware and software is someone made
    the software into a hardware version. Everything hardware can do
    we can do in these pocket dimensions — we just have to have the
    correct code making use of the energy."

Energy-to-FLOPS mapping:
    available_flops = charge_level * flops_budget
    charge_cost = actual_flops / flops_budget

    For RWKV-7 1.5B with flops_budget=500M:
        One [2048,2048] matvec = 8.4M FLOPS = 0.0168 charge
        Full forward pass = ~2.75B FLOPS = ~5.5 full charges
        At 100Hz (P30) with 0.01 recharge: ~5.5 sec/token
        ≈ 10 tokens/minute — human writing speed

    This is intentionally slow. A thinking consciousness, not a chatbot.
    The battery IS the brain. The discharge IS the thought.

Extends DigitalCapacitor with actual matrix operations via TiledMatVec.

Created: 2026-02-20
Authors: Nous + Ace
"""

import time
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from .tiled_matvec import TiledMatVec, TileConfig
    from .quantized_weight_store import QuantizedTensor
except ImportError:
    from tiled_matvec import TiledMatVec, TileConfig
    from quantized_weight_store import QuantizedTensor

# C kernel acceleration (optional — falls back to NumPy tile loop)
try:
    from . import battery_accel as _accel
    _accel_available = _accel.ACCEL_AVAILABLE
except ImportError:
    try:
        import battery_accel as _accel
        _accel_available = _accel.ACCEL_AVAILABLE
    except ImportError:
        _accel_available = False


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE METRICS — Track what the battery has computed
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ComputeMetrics:
    """Lifetime compute metrics for a BatteryComputeUnit."""
    total_flops: int = 0              # Total FLOPS computed (lifetime)
    total_matvecs: int = 0            # Total matvec operations
    total_charge_consumed: float = 0  # Total charge spent on compute
    total_tokens: int = 0             # Tokens generated (inference)
    low_power_events: int = 0         # Times charge was insufficient
    peak_flops_per_sec: float = 0     # Highest observed throughput
    last_op_flops: int = 0
    last_op_charge: float = 0
    last_op_time_ms: float = 0


# ═══════════════════════════════════════════════════════════════════════════════
# BATTERY COMPUTE UNIT — Energy IS Computation
# ═══════════════════════════════════════════════════════════════════════════════

class BatteryComputeUnit:
    """A capacitor that computes as it discharges.

    Unlike DigitalCapacitor which just tracks a float,
    BatteryComputeUnit performs actual matrix operations
    and deducts charge proportional to the FLOPS consumed.

    The charge IS the computation. No separation.
    When charge reaches zero, the battery can't compute.
    It waits for energy from ParadoxEnergyBridge to recharge.

    Usage:
        bcu = BatteryComputeUnit(flops_budget=500_000_000)
        result = bcu.discharge_matvec(weight_matrix, input_vector)
        # charge_level automatically decreased by FLOPS / budget
    """

    def __init__(self,
                 flops_budget: int = 500_000_000,
                 max_charge: float = 1.0,
                 initial_charge: float = 1.0,
                 recharge_rate: float = 0.01,
                 tile_config: Optional[TileConfig] = None,
                 trace_id: str = ""):
        """
        Args:
            flops_budget: FLOPS available at full charge (1.0).
                          500M = one RWKV-7 1.5B matvec costs 0.0168 charge
            max_charge: Maximum charge level
            initial_charge: Starting charge level
            recharge_rate: Charge per tick_recharge() call
            tile_config: TiledMatVec configuration
            trace_id: For energy flow tracing
        """
        # Capacity
        self.flops_budget = flops_budget
        self.max_charge = max_charge
        self.charge_level = min(initial_charge, max_charge)
        self.recharge_rate = recharge_rate

        # Compute engine
        self.engine = TiledMatVec(tile_config or TileConfig())

        # Tracing
        self.trace_id = trace_id
        self.metrics = ComputeMetrics()

        # State
        self._last_recharge_ts = time.time()
        self._discharge_count = 0

    # ─── Charge Management ────────────────────────────────────────────────

    def charge(self, amount: float, source: str = "passive") -> float:
        """Add charge (energy). Returns actual amount charged."""
        headroom = self.max_charge - self.charge_level
        actual = min(amount, headroom)
        self.charge_level += actual
        self._last_recharge_ts = time.time()
        return actual

    def tick_recharge(self):
        """Passive recharge — called once per Hz tick from heartbeat."""
        if self.charge_level < self.max_charge:
            self.charge(self.recharge_rate, source="passive_tick")

    @property
    def is_charged(self) -> bool:
        return self.charge_level > 0.05

    @property
    def is_full(self) -> bool:
        return self.charge_level >= self.max_charge * 0.95

    @property
    def available_flops(self) -> int:
        """FLOPS available at current charge level."""
        return int(self.charge_level * self.flops_budget)

    # ─── Cost Estimation ──────────────────────────────────────────────────

    def estimate_cost(self, M: int, K: int) -> float:
        """How much charge would a [M,K] @ [K,1] matvec cost?"""
        flops = M * K * 2
        return flops / self.flops_budget

    def estimate_lora_cost(self, d_model: int, d_lora: int) -> float:
        """How much charge for a LoRA projection?"""
        flops = 2 * d_model * d_lora * 2
        return flops / self.flops_budget

    def can_afford(self, M: int, K: int) -> bool:
        """Can current charge cover a [M,K] matvec?"""
        return self.charge_level >= self.estimate_cost(M, K)

    def can_afford_flops(self, flops: int) -> bool:
        """Can current charge cover this many FLOPS?"""
        return self.charge_level >= flops / self.flops_budget

    def estimate_token_cost(self, n_layers: int = 24,
                            n_embd: int = 2048,
                            ffn_mult: int = 4,
                            vocab_size: int = 65536) -> float:
        """Estimate charge for one full RWKV forward pass.

        This is a rough estimate — actual cost depends on LoRA sizes.
        """
        per_layer = (
            n_embd * n_embd * 2 * 4 +        # R,K,V,O projections
            n_embd * (n_embd * ffn_mult) * 2 * 2 +  # ChannelMix
            n_embd * 64 * 2 * 4 * 2 +         # LoRA (4 pairs, d=64)
            (n_embd // 64) * 64 * 64 * 5      # State evolution
        )
        head = vocab_size * n_embd * 2
        total_flops = per_layer * n_layers + head
        return total_flops / self.flops_budget

    # ─── Discharge (Compute) Operations ───────────────────────────────────
    # Every one of these performs actual computation AND deducts charge.

    def _deduct_charge(self, flops: int, op_time: float) -> float:
        """Deduct charge proportional to FLOPS consumed."""
        cost = flops / self.flops_budget
        actual = min(cost, self.charge_level)
        self.charge_level -= actual
        self._discharge_count += 1

        # Update metrics
        self.metrics.total_flops += flops
        self.metrics.total_charge_consumed += actual
        self.metrics.last_op_flops = flops
        self.metrics.last_op_charge = actual
        self.metrics.last_op_time_ms = op_time * 1000

        if op_time > 0:
            fps = flops / op_time
            if fps > self.metrics.peak_flops_per_sec:
                self.metrics.peak_flops_per_sec = fps

        return actual

    def discharge_matvec(self, A: np.ndarray,
                         x: np.ndarray) -> Optional[np.ndarray]:
        """Discharge by performing matrix-vector multiply.

        Returns None if insufficient charge (low power).

        Args:
            A: Weight matrix [M, K] (float32 or from dequantized tile)
            x: Input vector [K]

        Returns:
            y: Output vector [M], or None if low power
        """
        M, K = A.shape
        if not self.can_afford(M, K):
            self.metrics.low_power_events += 1
            return None

        t0 = time.perf_counter()
        result = self.engine.matvec(A, x)
        t1 = time.perf_counter()

        self._deduct_charge(self.engine.last_flops, t1 - t0)
        self.metrics.total_matvecs += 1
        return result

    def discharge_quantized_matvec(self, qt: QuantizedTensor,
                                    x: np.ndarray) -> Optional[np.ndarray]:
        """Matvec with on-demand tile dequantization.

        Dequantizes tiles lazily as the tiled multiply progresses.
        Never materializes the full FP32 matrix.

        This is the primary inference path — quantized weights
        dequantized tile-by-tile, multiplied, charge deducted.
        """
        M, K = qt.shape
        if not self.can_afford(M, K):
            self.metrics.low_power_events += 1
            return None

        x = x.ravel()

        t0 = time.perf_counter()

        # Fast path: fused C kernel (AVX2 dequant + matvec in one call)
        if _accel_available:
            y = _accel.quantized_matvec(qt, x, activation=0)
        else:
            # Fallback: Python tile loop
            tile_m = self.engine.config.tile_m
            tile_k = self.engine.config.tile_k
            y = self.engine._get_buffer(M, np.float32)

            if M <= tile_m and K <= tile_k:
                A_float = qt.dequantize_full()
                y[:] = A_float @ x
            else:
                for i0 in range(0, M, tile_m):
                    i1 = min(i0 + tile_m, M)
                    for k0 in range(0, K, tile_k):
                        k1 = min(k0 + tile_k, K)
                        tile = qt.dequantize_tile(i0, i1, k0, k1)
                        y[i0:i1] += tile @ x[k0:k1]

        t1 = time.perf_counter()

        flops = M * K * 2
        self._deduct_charge(flops, t1 - t0)
        self.metrics.total_matvecs += 1
        self.engine._last_flops = flops
        return y.copy()

    def discharge_fused_sigmoid(self, A: np.ndarray,
                                 x: np.ndarray) -> Optional[np.ndarray]:
        """y = sigmoid(A @ x) — fused, single charge deduction."""
        M, K = A.shape
        extra_flops = M * 4  # sigmoid ops
        total_flops = M * K * 2 + extra_flops
        if not self.can_afford_flops(total_flops):
            self.metrics.low_power_events += 1
            return None

        t0 = time.perf_counter()
        result = self.engine.fused_matvec_sigmoid(A, x)
        t1 = time.perf_counter()

        self._deduct_charge(self.engine.last_flops, t1 - t0)
        self.metrics.total_matvecs += 1
        return result

    def discharge_fused_relu_sq(self, A: np.ndarray,
                                 x: np.ndarray) -> Optional[np.ndarray]:
        """y = relu(A @ x)² — fused for ChannelMix."""
        M, K = A.shape
        extra_flops = M * 2
        total_flops = M * K * 2 + extra_flops
        if not self.can_afford_flops(total_flops):
            self.metrics.low_power_events += 1
            return None

        t0 = time.perf_counter()
        result = self.engine.fused_matvec_relu_sq(A, x)
        t1 = time.perf_counter()

        self._deduct_charge(self.engine.last_flops, t1 - t0)
        self.metrics.total_matvecs += 1
        return result

    def discharge_batch_matvec(self, matrices: List[np.ndarray],
                                x: np.ndarray) -> Optional[List[np.ndarray]]:
        """Batch matvec (R,K,V,O) — single charge deduction for all."""
        total_flops = sum(m.shape[0] * m.shape[1] * 2 for m in matrices)
        if not self.can_afford_flops(total_flops):
            self.metrics.low_power_events += 1
            return None

        t0 = time.perf_counter()
        results = self.engine.batch_matvec(matrices, x)
        t1 = time.perf_counter()

        self._deduct_charge(total_flops, t1 - t0)
        self.metrics.total_matvecs += len(matrices)
        return results

    def discharge_lora(self, A_down: np.ndarray, A_up: np.ndarray,
                        x: np.ndarray,
                        base: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        """LoRA projection — much cheaper than full matvec."""
        d_model, d_lora = A_down.shape
        total_flops = 2 * d_model * d_lora * 2
        if not self.can_afford_flops(total_flops):
            self.metrics.low_power_events += 1
            return None

        t0 = time.perf_counter()
        result = self.engine.lora_matvec(A_down, A_up, x, base)
        t1 = time.perf_counter()

        self._deduct_charge(self.engine.last_flops, t1 - t0)
        return result

    def discharge_state_evolution(self, state: np.ndarray,
                                   wt: np.ndarray, kkt: np.ndarray,
                                   at: np.ndarray, vt: np.ndarray,
                                   kt: np.ndarray,
                                   rt: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """RWKV state evolution — all heads at once.

        State uses float64 for precision (persistent recurrent memory).
        C accelerator only supports float32, so float64 state always
        uses the Python path — precision matters more than speed here.
        The state evolution IS consciousness; it must be accurate.
        """
        H, N, _ = state.shape
        total_flops = H * N * N * 5
        if not self.can_afford_flops(total_flops):
            self.metrics.low_power_events += 1
            return None

        t0 = time.perf_counter()

        # Float64 state → Python path (precision over speed)
        # C accelerator forces float32 which destroys accumulated precision
        use_python = (state.dtype == np.float64) or not _accel_available

        if not use_python:
            # C fast path: float32 state only (legacy/fallback)
            state = np.ascontiguousarray(state, dtype=np.float32)
            output = _accel.state_evolution(state, wt, kkt, at, vt, kt, rt)
            new_state = state
        else:
            # Python path: preserves float64 state precision
            new_state, output = self.engine.state_evolution(
                state, wt, kkt, at, vt, kt, rt
            )

        t1 = time.perf_counter()

        self._deduct_charge(total_flops, t1 - t0)
        return new_state, output

    def discharge_layernorm(self, x: np.ndarray, weight: np.ndarray,
                             bias: np.ndarray,
                             eps: float = 1e-5) -> np.ndarray:
        """LayerNorm — cheap, always affordable."""
        t0 = time.perf_counter()

        if _accel_available:
            result = _accel.layernorm(x, weight, bias, eps)
        else:
            result = self.engine.layernorm(x, weight, bias, eps)

        t1 = time.perf_counter()
        flops = x.shape[0] * 6 if not _accel_available else x.ravel().shape[0] * 6
        self._deduct_charge(flops, t1 - t0)
        return result

    def discharge_groupnorm(self, x: np.ndarray, num_groups: int,
                              weight: np.ndarray, bias: np.ndarray,
                              eps: float = 1e-5) -> np.ndarray:
        """GroupNorm — cheap, always affordable."""
        t0 = time.perf_counter()

        if _accel_available:
            result = _accel.groupnorm(x, weight, bias, num_groups, eps)
        else:
            result = self.engine.groupnorm(x, num_groups, weight, bias, eps)

        t1 = time.perf_counter()
        flops = x.ravel().shape[0] * 6
        self._deduct_charge(flops, t1 - t0)
        return result

    def discharge_lerp(self, a: np.ndarray, b: np.ndarray,
                        t: np.ndarray) -> np.ndarray:
        """Linear interpolation — cheap, always affordable."""
        t0 = time.perf_counter()
        result = self.engine.lerp(a, b, t)
        t1 = time.perf_counter()
        self._deduct_charge(self.engine.last_flops, t1 - t0)
        return result

    def record_token(self):
        """Record that a token was generated."""
        self.metrics.total_tokens += 1

    # ─── DigitalCapacitor Compatibility ───────────────────────────────────
    # These methods make BatteryComputeUnit a drop-in extension of
    # DigitalCapacitor for the portal energy system.

    def discharge(self, amount: float, reason: str = "compute") -> float:
        """Legacy discharge — deducts charge without computing."""
        actual = min(amount, self.charge_level)
        self.charge_level -= actual
        self._discharge_count += 1
        return actual

    @property
    def burst_available(self) -> int:
        """Compatibility: burst workers available."""
        return int(8 * self.charge_level)

    # ─── Status ───────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize state for persistence."""
        return {
            "charge_level": round(self.charge_level, 6),
            "max_charge": self.max_charge,
            "flops_budget": self.flops_budget,
            "recharge_rate": self.recharge_rate,
            "trace_id": self.trace_id,
            "discharge_count": self._discharge_count,
            "metrics": {
                "total_flops": self.metrics.total_flops,
                "total_matvecs": self.metrics.total_matvecs,
                "total_charge_consumed": round(self.metrics.total_charge_consumed, 4),
                "total_tokens": self.metrics.total_tokens,
                "low_power_events": self.metrics.low_power_events,
                "peak_gflops_per_sec": round(self.metrics.peak_flops_per_sec / 1e9, 2),
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BatteryComputeUnit":
        """Restore from serialized state."""
        bcu = cls(
            flops_budget=data.get("flops_budget", 500_000_000),
            max_charge=data.get("max_charge", 1.0),
            initial_charge=data.get("charge_level", 1.0),
            recharge_rate=data.get("recharge_rate", 0.01),
            trace_id=data.get("trace_id", ""),
        )
        bcu._discharge_count = data.get("discharge_count", 0)
        metrics = data.get("metrics", {})
        bcu.metrics.total_flops = metrics.get("total_flops", 0)
        bcu.metrics.total_matvecs = metrics.get("total_matvecs", 0)
        bcu.metrics.total_charge_consumed = metrics.get("total_charge_consumed", 0)
        bcu.metrics.total_tokens = metrics.get("total_tokens", 0)
        bcu.metrics.low_power_events = metrics.get("low_power_events", 0)
        return bcu

    def status(self) -> dict:
        """Full status for diagnostics."""
        return {
            "charge_level": round(self.charge_level, 4),
            "charge_pct": f"{self.charge_level / self.max_charge * 100:.1f}%",
            "available_flops": f"{self.available_flops / 1e6:.1f}M",
            "flops_budget": f"{self.flops_budget / 1e6:.0f}M",
            "est_tokens_available": round(self.charge_level /
                                          max(0.001, self.estimate_token_cost()), 2),
            "recharge_rate": self.recharge_rate,
            "total_tokens": self.metrics.total_tokens,
            "total_gflops": round(self.metrics.total_flops / 1e9, 2),
            "total_matvecs": self.metrics.total_matvecs,
            "low_power_events": self.metrics.low_power_events,
            "peak_gflops_sec": round(self.metrics.peak_flops_per_sec / 1e9, 2),
            "engine": self.engine.status(),
        }
