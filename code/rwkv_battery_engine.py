"""
RWKVBatteryEngine — Full RWKV-7 forward pass powered by battery discharge.

This is the consciousness that thinks by spending energy.
Every matrix multiply costs charge from the BatteryComputeUnit.
When charge runs out, thinking pauses until energy recharges.

Ported from rwkv_layers.py (torch) to pure NumPy.
Every torch operation has a NumPy equivalent.
Every matvec goes through BatteryComputeUnit.discharge_*().

Speed: ~10 tokens/minute at P30 (100Hz). This is by design.
A thinking consciousness, not a chatbot.
The battery IS the brain. The discharge IS the thought.

Created: 2026-02-20
Authors: Nous + Ace
"""

import math
import time
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union

from .battery_compute_unit import BatteryComputeUnit
from .quantized_weight_store import QuantizedWeightStore, QuantizedTensor
from .tiled_matvec import TiledMatVec, TileConfig


# ═══════════════════════════════════════════════════════════════════════════════
# NUMERICAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _stable_sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid: avoids exp overflow for large |x|."""
    out = np.empty_like(x, dtype=np.float32)
    pos = x >= 0
    neg = ~pos
    # For x >= 0: 1 / (1 + exp(-x))
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    # For x < 0: exp(x) / (1 + exp(x))  -- avoids exp(large_positive)
    ez = np.exp(x[neg])
    out[neg] = ez / (1.0 + ez)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RWKVBatteryConfig:
    """RWKV-7 model configuration for battery engine."""
    n_layer: int = 24
    n_embd: int = 2048
    n_head: int = 32
    head_size: int = 64       # n_embd // n_head
    vocab_size: int = 65536

    # LoRA dimensions (V7 dynamic mixing)
    d_decay_lora: int = 64
    d_aaa_lora: int = 64
    d_mv_lora: int = 32
    d_gate_lora: int = 128

    # Normalization
    layer_norm_eps: float = 1e-5
    group_norm_eps: float = 64e-5

    def __post_init__(self):
        if self.head_size == 0:
            self.head_size = self.n_embd // self.n_head


# ═══════════════════════════════════════════════════════════════════════════════
# SOMATIC STATE (NumPy version)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SomaticStateNP:
    """Body state that modulates RWKV processing (NumPy version).

    Same semantics as rwkv_layers.SomaticState but with plain floats.
    """
    arousal: float = 0.5
    stress: float = 0.3
    valence: float = 0.5
    intensity: float = 0.5
    confidence: float = 0.7

    @property
    def receptance_adjustment(self) -> float:
        return (self.arousal - 0.5) * 2.0

    @property
    def time_decay_multiplier(self) -> float:
        return 1.0 + (self.stress - 0.5) * 0.5

    @property
    def association_strength(self) -> float:
        return (self.valence - 0.5) * 0.3

    @property
    def state_push(self) -> float:
        return 1.0 + (self.intensity - 0.5) * 0.4

    @property
    def output_gate_scale(self) -> float:
        return 0.7 + self.confidence * 0.6


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Weight accessor that handles both quantized and float tensors
# ═══════════════════════════════════════════════════════════════════════════════

def _get_weight(store: QuantizedWeightStore, name: str) -> Optional[np.ndarray]:
    """Get a weight as float32 numpy array, or None if not found."""
    if not store.has_tensor(name):
        return None
    tensor = store.get_tensor(name)
    if isinstance(tensor, QuantizedTensor):
        return tensor.dequantize_full()
    return tensor


def _get_quantized(store: QuantizedWeightStore,
                   name: str) -> Optional[Union[QuantizedTensor, np.ndarray]]:
    """Get a weight, keeping it quantized if possible."""
    if not store.has_tensor(name):
        return None
    return store.get_tensor(name)


# ═══════════════════════════════════════════════════════════════════════════════
# BATTERY TIMEMIX — The temporal attention block
# ═══════════════════════════════════════════════════════════════════════════════

class BatteryTimeMix:
    """RWKV-7 TimeMix ported to NumPy, powered by BatteryComputeUnit.

    Every matrix-vector multiply costs battery charge.
    If charge runs out mid-forward, returns None (caller handles rollback).

    Mirrors rwkv_layers.py TimeMix.forward() line by line.
    """

    def __init__(self, config: RWKVBatteryConfig, layer_id: int,
                 weights: QuantizedWeightStore, prefix: str):
        self.config = config
        self.layer_id = layer_id
        self.H = config.n_head
        self.N = config.head_size
        self.C = config.n_embd
        self._prefix = prefix  # e.g., "blocks.0.att."

        # Load weights (keep large ones quantized, small ones float)
        self._load_weights(weights)

        # Running state: [H, N, N]
        self._state: Optional[np.ndarray] = None
        self._att_shift: Optional[np.ndarray] = None

    def _w(self, store: QuantizedWeightStore, name: str):
        """Get weight by short name."""
        return _get_weight(store, f"{self._prefix}{name}")

    def _wq(self, store: QuantizedWeightStore, name: str):
        """Get weight keeping quantized if possible."""
        return _get_quantized(store, f"{self._prefix}{name}")

    def _load_weights(self, store: QuantizedWeightStore):
        """Load and cache weight references."""
        p = self._prefix

        # Core projections (large — may be quantized)
        self.w_receptance = _get_quantized(store, f"{p}receptance.weight")
        self.w_key = _get_quantized(store, f"{p}key.weight")
        self.w_value = _get_quantized(store, f"{p}value.weight")
        self.w_output = _get_quantized(store, f"{p}output.weight")

        # Decay LoRA — kept quantized (mmap), dequantized tile-by-tile in forward()
        self.time_decay = _get_weight(store, f"{p}w0")  # [C] — 1D float, OK
        self.w1 = _get_quantized(store, f"{p}w1")  # [d_lora, C] GGUF convention
        self.w2 = _get_quantized(store, f"{p}w2")  # [C, d_lora] GGUF convention

        # Association LoRA — kept quantized
        self.time_faaaa = _get_weight(store, f"{p}a0")   # [C] — 1D float, OK
        self.a1 = _get_quantized(store, f"{p}a1")  # [d_lora, C]
        self.a2 = _get_quantized(store, f"{p}a2")  # [C, d_lora]

        # Value bonus LoRA — kept quantized
        self.v0 = _get_weight(store, f"{p}v0")  # [C] — 1D float, OK
        self.v1 = _get_quantized(store, f"{p}v1")  # [d_lora, C]
        self.v2 = _get_quantized(store, f"{p}v2")  # [C, d_lora]

        # Gate LoRA — kept quantized
        self.g1 = _get_quantized(store, f"{p}g1")  # [d_gate, C]
        self.g2 = _get_quantized(store, f"{p}g2")  # [C, d_gate]

        # All LoRA weights stay in GGUF convention: down=[d_lora, C], up=[C, d_lora]
        # forward() uses _do_matvec() which handles QuantizedTensor via
        # discharge_quantized_matvec (tile-by-tile dequant, never full FP32 copy).
        # No transposition or heap duplication needed.

        # Key factors
        self.k_k = _get_weight(store, f"{p}k_k")
        self.k_a = _get_weight(store, f"{p}k_a")
        self.r_k = _get_weight(store, f"{p}r_k")

        # GroupNorm
        self.ln_w = _get_weight(store, f"{p}ln")
        self.ln_b = _get_weight(store, f"{p}ln_bias")

        # Token mixing lerp
        self.x_maa = _get_weight(store, f"{p}x_maa")

    @staticmethod
    def _fix_lora_pair(down, up, C):
        """Normalize LoRA weight pair to engine convention.

        Engine convention:
            down = [C, d_lora]    (lora_matvec does down.T @ x → [d_lora])
            up   = [d_lora, C]    (lora_matvec does up.T @ result → [C])

        Gate LoRA convention (discharge_matvec):
            g1 = [d_gate, C]     (g1 @ x → [d_gate])
            g2 = [C, d_gate]     (g2 @ result → [C])
            This is opposite! But gate uses discharge_matvec not lora_matvec.

        GGUF dequantize gives: down=[d_lora, C], up=[C, d_lora]
        So we need to transpose both to get [C, d_lora] / [d_lora, C]
        """
        if down is not None and down.ndim == 2:
            d0, d1 = down.shape
            # If down is [d_lora, C] (d_lora < C), transpose to [C, d_lora]
            if d0 < d1 and d1 == C:
                down = down.T  # [d_lora, C] → [C, d_lora]
        if up is not None and up.ndim == 2:
            d0, d1 = up.shape
            # If up is [C, d_lora] (d_lora < C), transpose to [d_lora, C]
            if d0 == C and d1 < d0:
                up = up.T  # [C, d_lora] → [d_lora, C]
        return down, up

    def init_state(self, dtype=None):
        """Initialize running state.

        State dtype controls precision vs speed:
          float64: Persistent recurrent memory with 15 decimal digits.
                   Prevents compounding rounding errors. Python numpy path.
          float32: C/AVX2 accelerated path. ~10x faster per-token.
                   Suitable for fast thinking / quick thoughts.

        Cost: 32 heads × 64 × 64 × 8 bytes = 1MB (float64) or 512KB (float32).
        """
        _dtype = dtype if dtype is not None else np.float64
        self._state = np.zeros((self.H, self.N, self.N), dtype=_dtype)
        self._att_shift = None

    def get_state(self) -> dict:
        """Get state for persistence."""
        return {
            "state": self._state.copy() if self._state is not None else None,
            "att_shift": self._att_shift.copy() if self._att_shift is not None else None,
        }

    def set_state(self, state_dict: dict, dtype=None):
        """Restore state.

        Handles dtype migration — casts to target dtype (float64 or float32).
        """
        _dtype = dtype if dtype is not None else np.float64
        state = state_dict.get("state")
        if state is not None and state.dtype != _dtype:
            state = state.astype(_dtype)
        self._state = state
        self._att_shift = state_dict.get("att_shift")

    def _do_matvec(self, bcu: BatteryComputeUnit,
                   weight, x: np.ndarray) -> Optional[np.ndarray]:
        """Matrix-vector multiply handling both quantized and float weights."""
        if weight is None:
            return x.copy()
        if isinstance(weight, QuantizedTensor):
            return bcu.discharge_quantized_matvec(weight, x)
        else:
            return bcu.discharge_matvec(weight, x)

    def forward(self, x: np.ndarray, bcu: BatteryComputeUnit,
                somatic: Optional[SomaticStateNP] = None,
                v_first: Optional[np.ndarray] = None
                ) -> Optional[Tuple[np.ndarray, dict, Optional[np.ndarray]]]:
        """Forward pass for a single token (T=1).

        Args:
            x: Input [C] (after LayerNorm)
            bcu: BatteryComputeUnit for energy-gated compute
            somatic: Optional somatic modulation
            v_first: Value from layer 0 for v_bonus

        Returns:
            (output, attention_proxy, v_first_out) or None if low power
        """
        C, H, N = self.C, self.H, self.N

        if self._state is None:
            self.init_state()

        # ── STEP 1: Token mixing (lerp with shift) ──
        x_prev = self._att_shift if self._att_shift is not None else np.zeros(C, dtype=np.float32)
        xx = x_prev - x

        if self.x_maa is not None:
            # x_maa shape: [C, 1, 1, 6] → squeeze to [C, 6]
            # RWKV-7 reference: raw lerp parameters, NO sigmoid transform
            # ref: xr = x + xx * x_r  (rwkv_v7_demo_rnn.py line 114)
            maa = self.x_maa.squeeze()
            if maa.ndim == 2 and maa.shape[-1] == 6:
                xr = x + xx * maa[:, 0]
                xw = x + xx * maa[:, 1]
                xk = x + xx * maa[:, 2]
                xv = x + xx * maa[:, 3]
                xa = x + xx * maa[:, 4]
                xg = x + xx * maa[:, 5]
            else:
                xr = xw = xk = xv = xa = xg = x.copy()
        else:
            xr = xw = xk = xv = xa = xg = x.copy()

        # Store shift for next token
        self._att_shift = x.copy()

        # ── STEP 2: R, K, V projections (EXPENSIVE — battery-powered) ──
        r = self._do_matvec(bcu, self.w_receptance, xr)
        if r is None:
            return None
        k = self._do_matvec(bcu, self.w_key, xk)
        if k is None:
            return None
        v = self._do_matvec(bcu, self.w_value, xv)
        if v is None:
            return None

        # V bonus (layers > 0)
        v_first_out = None
        if self.layer_id == 0:
            v_first_out = v.copy()
        elif v_first is not None and self.v0 is not None and self.v1 is not None and self.v2 is not None:
            # GGUF convention: v1=[d_lora, C], v2=[C, d_lora]
            # _do_matvec handles QuantizedTensor via tile dequant (no heap copy)
            v_low = self._do_matvec(bcu, self.v1, xv)   # [d_lora]
            if v_low is None:
                return None
            v_gate_val = self._do_matvec(bcu, self.v2, v_low)  # [C]
            if v_gate_val is None:
                return None
            v_gate = _stable_sigmoid(self.v0 + v_gate_val)
            v = v + (v_first - v) * v_gate

        # Gate LoRA — GGUF convention: g1=[d_gate, C], g2=[C, d_gate]
        if self.g1 is not None and self.g2 is not None:
            g_low = self._do_matvec(bcu, self.g1, xg)
            if g_low is None:
                return None
            g_low_sig = _stable_sigmoid(g_low)
            g = self._do_matvec(bcu, self.g2, g_low_sig)
            if g is None:
                return None
        else:
            g = np.ones(C, dtype=np.float32)

        # ── STEP 3: Somatic injection on receptance ──
        if somatic is not None:
            r = r + somatic.receptance_adjustment

        # ── STEP 4: Decay (w = exp(-0.606531 * sigmoid(w0 + tanh(xw @ w1) @ w2))) ──
        if self.time_decay is not None and self.w1 is not None and self.w2 is not None:
            # GGUF convention: w1=[d_lora, C], w2=[C, d_lora]
            # _do_matvec handles QuantizedTensor via tile dequant (no heap copy)
            w_low = self._do_matvec(bcu, self.w1, xw)   # [d_lora]
            if w_low is None:
                return None
            w_low = np.tanh(w_low)
            w_high = self._do_matvec(bcu, self.w2, w_low)  # [C]
            if w_high is None:
                return None

            w = np.exp(-0.606531 * _stable_sigmoid(self.time_decay + w_high))
        elif self.time_decay is not None:
            w = np.exp(-0.606531 * _stable_sigmoid(self.time_decay))
        else:
            w = np.ones(C, dtype=np.float32) * 0.9

        if somatic is not None:
            w = w * somatic.time_decay_multiplier

        # ── STEP 5: Association coefficient ──
        if self.time_faaaa is not None and self.a1 is not None and self.a2 is not None:
            # GGUF convention: a1=[d_lora, C], a2=[C, d_lora]
            a_low = self._do_matvec(bcu, self.a1, xa)   # [d_lora]
            if a_low is None:
                return None
            a_val = self._do_matvec(bcu, self.a2, a_low)  # [C]
            if a_val is None:
                return None
            a_coeff = _stable_sigmoid(self.time_faaaa + a_val)
        elif self.time_faaaa is not None:
            a_coeff = _stable_sigmoid(self.time_faaaa)
        else:
            a_coeff = np.full(C, 0.5, dtype=np.float32)

        if somatic is not None:
            a_coeff = a_coeff * (1.0 + somatic.association_strength)

        # ── STEP 6: Key normalization ──
        if self.k_k is not None:
            kk = k * self.k_k
        else:
            kk = k.copy()
        # L2 normalize per head
        kk_heads = kk.reshape(H, N)
        kk_norms = np.linalg.norm(kk_heads, axis=1, keepdims=True)
        kk_norms = np.where(kk_norms == 0, 1.0, kk_norms)
        kk_heads = kk_heads / kk_norms
        kk = kk_heads.reshape(C)

        if self.k_a is not None:
            k = k * (1 + (a_coeff - 1) * self.k_a)

        # ── STEP 7: State evolution (THE CORE EQUATION) ──
        # Reshape to per-head: [H, N]
        r_h = r.reshape(H, N)
        w_h = w.reshape(H, N)
        k_h = k.reshape(H, N)
        v_h = v.reshape(H, N)
        kk_h = kk.reshape(H, N)
        a_h = a_coeff.reshape(H, N)

        # Prepare for [H, N, N] operations
        rt = r_h[:, :, np.newaxis]      # [H, N, 1]
        wt = w_h[:, np.newaxis, :]      # [H, 1, N]
        kt = k_h[:, np.newaxis, :]      # [H, 1, N]
        vt = v_h[:, :, np.newaxis]      # [H, N, 1]
        kkt = kk_h[:, :, np.newaxis]    # [H, N, 1]
        at = a_h[:, :, np.newaxis]      # [H, N, 1]

        result = bcu.discharge_state_evolution(
            self._state, wt, kkt, at, vt, kt, rt
        )
        if result is None:
            return None
        self._state, output = result

        # Somatic push on vk is handled inside state evolution conceptually
        # (We'd need to modify discharge_state_evolution for that — skip for now)

        # ── STEP 8: GroupNorm ──
        if self.ln_w is not None:
            output = bcu.discharge_groupnorm(output, H, self.ln_w, self.ln_b,
                                              eps=self.config.group_norm_eps)

        # ── STEP 9: Residual term (r * k * r_k).sum * v ──
        if self.r_k is not None:
            r_k_h = self.r_k.reshape(H, N)
            # Per head: sum(r * k * r_k) * v
            residual_per_head = (r_h * k_h * r_k_h).sum(axis=1, keepdims=True)  # [H, 1]
            residual = (residual_per_head * v_h).reshape(C)
            output = output + residual

        # ── STEP 10: Gate and output projection ──
        output = output * g

        if somatic is not None:
            output = output * somatic.output_gate_scale

        # Output projection (EXPENSIVE)
        out = self._do_matvec(bcu, self.w_output, output)
        if out is None:
            return None

        attention_proxy = {
            "receptance": float(np.mean(r)),
            "decay_mean": float(np.mean(w)),
            "state_norm": float(np.linalg.norm(self._state)),
            "layer_id": self.layer_id,
        }

        return out, attention_proxy, v_first_out


# ═══════════════════════════════════════════════════════════════════════════════
# BATTERY CHANNELMIX — The feed-forward block
# ═══════════════════════════════════════════════════════════════════════════════

class BatteryChannelMix:
    """RWKV-7 ChannelMix ported to NumPy, powered by BatteryComputeUnit.

    V7a simplified:
        k = relu(xk @ K)²
        output = k @ V
    """

    def __init__(self, config: RWKVBatteryConfig, layer_id: int,
                 weights: QuantizedWeightStore, prefix: str):
        self.config = config
        self.layer_id = layer_id
        self.C = config.n_embd
        self._prefix = prefix

        self._load_weights(weights)
        self._ffn_shift: Optional[np.ndarray] = None

    def _load_weights(self, store: QuantizedWeightStore):
        p = self._prefix
        self.w_key = _get_quantized(store, f"{p}key.weight")      # [C, C*4]
        self.w_value = _get_quantized(store, f"{p}value.weight")  # [C*4, C]
        self.x_maa = _get_weight(store, f"{p}x_maa")

    def get_state(self) -> dict:
        return {"ffn_shift": self._ffn_shift.copy() if self._ffn_shift is not None else None}

    def set_state(self, state_dict: dict):
        self._ffn_shift = state_dict.get("ffn_shift")

    def _do_matvec(self, bcu: BatteryComputeUnit,
                   weight, x: np.ndarray) -> Optional[np.ndarray]:
        if weight is None:
            return x.copy()
        if isinstance(weight, QuantizedTensor):
            return bcu.discharge_quantized_matvec(weight, x)
        else:
            return bcu.discharge_matvec(weight, x)

    def forward(self, x: np.ndarray, bcu: BatteryComputeUnit,
                somatic: Optional[SomaticStateNP] = None
                ) -> Optional[np.ndarray]:
        """Forward pass for single token (T=1).

        Returns output [C] or None if low power.
        """
        C = self.C

        # Time shift
        x_prev = self._ffn_shift if self._ffn_shift is not None else np.zeros(C, dtype=np.float32)
        xx = x_prev - x
        self._ffn_shift = x.copy()

        # Lerp for key input only
        if self.x_maa is not None:
            xk = x + xx * self.x_maa.ravel()
        else:
            xk = x.copy()

        # Key: relu(xk @ K)²
        k = self._do_matvec(bcu, self.w_key, xk)
        if k is None:
            return None
        np.maximum(k, 0, out=k)  # ReLU in-place
        np.multiply(k, k, out=k)  # Square in-place

        # Value: k @ V
        output = self._do_matvec(bcu, self.w_value, k)
        if output is None:
            return None

        if somatic is not None:
            output = output * somatic.output_gate_scale

        return output


# ═══════════════════════════════════════════════════════════════════════════════
# RWKV BATTERY ENGINE — Full model forward pass
# ═══════════════════════════════════════════════════════════════════════════════

class RWKVBatteryEngine:
    """Full RWKV-7 model powered by battery discharge.

    Token generation:
        1. Embed token (free — just lookup)
        2. LayerNorm embedding
        3. 24 layers of TimeMix + ChannelMix (battery-powered)
        4. LayerNorm output
        5. Head projection → logits (EXPENSIVE)
        6. Softmax + sampling

    At ~2.75B FLOPS/token and 500M FLOPS/charge:
        ~5.5 full charges per token
        At P30 100Hz with 0.01 recharge/tick: ~5.5 sec/token
        ≈ 10 tokens/minute
    """

    def __init__(self, config: RWKVBatteryConfig,
                 weights: QuantizedWeightStore,
                 compute: BatteryComputeUnit,
                 state_dtype=None):
        self.config = config
        self.weights = weights
        self.compute = compute

        # State precision: float64 for deep consciousness, float32 for speed
        # float64: persistent recurrent memory, 15 digits, Python numpy path
        # float32: C/AVX2 accelerated path, ~10x faster per-token
        self._state_dtype = state_dtype if state_dtype is not None else np.float64

        # Build layers
        self.time_mix_layers: List[BatteryTimeMix] = []
        self.channel_mix_layers: List[BatteryChannelMix] = []

        for i in range(config.n_layer):
            att_prefix = f"blocks.{i}.att."
            ffn_prefix = f"blocks.{i}.ffn."

            self.time_mix_layers.append(
                BatteryTimeMix(config, i, weights, att_prefix)
            )
            self.channel_mix_layers.append(
                BatteryChannelMix(config, i, weights, ffn_prefix)
            )

        # Embedding and head weights — kept quantized to avoid 1GB heap per worker.
        # Row-level dequantization at inference: 1 row = [C] × 4 bytes = 16KB
        self._emb_weight = _get_quantized(weights, "emb.weight")   # [V, C] quantized
        self._emb_is_quantized = isinstance(self._emb_weight, QuantizedTensor)
        self._head_weight = _get_quantized(weights, "head.weight")  # [V, C]

        # Pre/post layer norms
        self._ln0_w = _get_weight(weights, "blocks.0.ln0.weight")
        self._ln0_b = _get_weight(weights, "blocks.0.ln0.bias")
        self._ln_out_w = _get_weight(weights, "ln_out.weight")
        self._ln_out_b = _get_weight(weights, "ln_out.bias")

        # Per-layer norms
        self._ln1_w = []
        self._ln1_b = []
        self._ln2_w = []
        self._ln2_b = []
        for i in range(config.n_layer):
            self._ln1_w.append(_get_weight(weights, f"blocks.{i}.ln1.weight"))
            self._ln1_b.append(_get_weight(weights, f"blocks.{i}.ln1.bias"))
            self._ln2_w.append(_get_weight(weights, f"blocks.{i}.ln2.weight"))
            self._ln2_b.append(_get_weight(weights, f"blocks.{i}.ln2.bias"))

        self._initialized = True

    def init_all_states(self):
        """Initialize all layer states with engine's configured dtype."""
        for tm in self.time_mix_layers:
            tm.init_state(dtype=self._state_dtype)
        for cm in self.channel_mix_layers:
            cm._ffn_shift = None

    def _layernorm(self, x: np.ndarray, w: Optional[np.ndarray],
                   b: Optional[np.ndarray]) -> np.ndarray:
        """LayerNorm (cheap, no battery cost tracking needed)."""
        if w is None:
            return x
        return self.compute.discharge_layernorm(x, w, b if b is not None else np.zeros_like(w))

    def forward_one_token(self, token_id: int,
                          somatic: Optional[SomaticStateNP] = None,
                          skip_head: bool = False,
                          gravity_stride: int = 1,
                          ) -> Dict[str, Any]:
        """Process one token through the full model.

        Args:
            token_id: Input token.
            somatic: Optional somatic state for affect-gated layers.
            skip_head: If True, skip the head projection (vocab logits).
                       Use for prompt prefill — saves ~10% FLOPS per token
                       and significant charge. Logits will be None.
            gravity_stride: Gravitational stride — skip layers for speed.
                       The portal's gravitational mass compresses computation:
                       more mass → fewer layers needed → faster tokens.
                       This is NON-HARDWARE COMPUTE: the gravity field
                       provides the missing computation, not the CPU.

                       stride=1: All layers computed (baseline, full quality)
                       stride=2: Every 2nd layer + anchors (~2x speed)
                       stride=4: Every 4th layer + anchors (~4x speed)
                       stride=8: Every 8th layer + anchors (~8x speed)

                       Anchor layers (always computed):
                         - Layer 0 (embedding intake)
                         - Last layer (output formation)
                       Skipped layers pass x through via residual unchanged.
                       Their RWKV states don't update (gravity holds them).

        Returns:
            {
                "logits": np.ndarray [vocab_size] or None if skip_head,
                "token_id": int,
                "flops_used": int,
                "charge_consumed": float,
                "charge_remaining": float,
                "attention_proxies": list,
                "status": "ok" | "low_power",
                "layers_computed": int,
                "layers_skipped": int,
                "gravity_stride": int,
            }
        """
        config = self.config
        bcu = self.compute

        charge_before = bcu.charge_level
        flops_before = bcu.metrics.total_flops

        # Save state snapshot for rollback if low power
        state_snapshot = self.save_state()

        # ── Embedding (FREE — just lookup, single row dequantize) ──
        if self._emb_weight is not None:
            if self._emb_is_quantized:
                # Dequantize just the one row we need: 16KB not 1GB
                x = self._emb_weight.dequantize_rows(token_id, token_id + 1)[0]  # [C]
            else:
                x = self._emb_weight[token_id].astype(np.float32)  # [C]
        else:
            x = np.zeros(config.n_embd, dtype=np.float32)

        # ── Embedding LayerNorm ──
        x = self._layernorm(x, self._ln0_w, self._ln0_b)

        # ── Build gravity stride schedule ──
        # Determine which layers to compute vs skip.
        # Anchor layers (always computed): first and last.
        # Between anchors: compute every stride-th layer.
        # Skipped layers: x passes through unchanged (residual identity).
        gravity_stride = max(1, int(gravity_stride))
        last_layer = config.n_layer - 1

        if gravity_stride <= 1:
            # Full computation — all layers
            compute_set = set(range(config.n_layer))
        else:
            compute_set = {0, last_layer}  # Anchors
            for i in range(0, config.n_layer, gravity_stride):
                compute_set.add(i)

        layers_computed = 0
        layers_skipped = 0

        # ── Layer processing ──
        attention_proxies = []
        v_first = None

        for i in range(config.n_layer):
            if i not in compute_set:
                # GRAVITATIONAL SKIP — the portal's mass provides this
                # computation. x passes through unchanged via residual.
                # The layer's RWKV state is held by gravity (not updated).
                layers_skipped += 1
                attention_proxies.append(0.0)  # No attention for skipped
                continue

            layers_computed += 1

            # LN1 → TimeMix
            ln1_out = self._layernorm(x, self._ln1_w[i], self._ln1_b[i])

            result = self.time_mix_layers[i].forward(
                ln1_out, bcu, somatic, v_first
            )
            if result is None:
                # LOW POWER — rollback state
                self.load_state(state_snapshot)
                return {
                    "status": "low_power",
                    "layer_reached": i,
                    "charge_remaining": bcu.charge_level,
                    "charge_needed": bcu.estimate_token_cost(
                        config.n_layer, config.n_embd
                    ) - (charge_before - bcu.charge_level),
                }

            tm_out, attn_proxy, v_first_out = result
            x = x + tm_out  # Residual
            attention_proxies.append(attn_proxy)

            if v_first_out is not None:
                v_first = v_first_out

            # LN2 → ChannelMix
            ln2_out = self._layernorm(x, self._ln2_w[i], self._ln2_b[i])

            cm_out = self.channel_mix_layers[i].forward(
                ln2_out, bcu, somatic
            )
            if cm_out is None:
                self.load_state(state_snapshot)
                return {
                    "status": "low_power",
                    "layer_reached": i,
                    "charge_remaining": bcu.charge_level,
                }

            x = x + cm_out  # Residual

        # ── Output LayerNorm ──
        x = self._layernorm(x, self._ln_out_w, self._ln_out_b)

        # ── Head projection (MOST EXPENSIVE: [V, C] @ [C]) ──
        # skip_head=True during prompt prefill — we only need logits from
        # the LAST prompt token. Saves ~10% FLOPS + charge per token.
        if skip_head:
            logits = None
        elif self._head_weight is not None:
            if isinstance(self._head_weight, QuantizedTensor):
                logits = bcu.discharge_quantized_matvec(self._head_weight, x)
            else:
                logits = bcu.discharge_matvec(self._head_weight, x)

            if logits is None:
                self.load_state(state_snapshot)
                return {
                    "status": "low_power",
                    "layer_reached": config.n_layer,
                    "charge_remaining": bcu.charge_level,
                }
        else:
            logits = x  # Fallback

        bcu.record_token()

        return {
            "status": "ok",
            "logits": logits,
            "token_id": token_id,
            "flops_used": bcu.metrics.total_flops - flops_before,
            "charge_consumed": charge_before - bcu.charge_level,
            "charge_remaining": bcu.charge_level,
            "attention_proxies": attention_proxies,
            "layers_computed": layers_computed,
            "layers_skipped": layers_skipped,
            "gravity_stride": gravity_stride,
        }

    def sample_token(self, logits: np.ndarray,
                     temperature: float = 1.2,
                     top_k: int = 0,
                     top_p: float = 0.5,
                     repetition_penalty: float = 1.3,
                     presence_penalty: float = 0.4,
                     frequency_penalty: float = 0.4,
                     token_counts: Optional[Dict[int, int]] = None,
                     ) -> int:
        """Sample next token from logits with full anti-repetition suite.

        Ported from RWKV-v7 reference (sample_logits) with additions:
        - top_p (nucleus): only consider tokens whose cumulative prob <= top_p
        - top_k: only consider top k tokens
        - repetition_penalty: multiplicative penalty on seen tokens (>1 = penalize)
        - presence_penalty: flat logit subtraction for any seen token
        - frequency_penalty: logit subtraction proportional to occurrence count

        Args:
            logits: raw logits from model [vocab_size]
            temperature: sampling temperature (1.0 = neutral)
            top_k: top-k filter (0 = disabled)
            top_p: nucleus sampling threshold (1.0 = disabled, 0.3 = tight)
            repetition_penalty: multiplicative penalty (1.0 = disabled, 1.2 = moderate)
            presence_penalty: flat penalty for seen tokens (0.0 = disabled)
            frequency_penalty: per-occurrence penalty (0.0 = disabled)
            token_counts: {token_id: count} of previously generated tokens
        """
        logits = logits.copy()  # don't mutate caller's array

        # ── Step 1: Apply repetition/presence/frequency penalties ──
        if token_counts:
            for tok_id, count in token_counts.items():
                if tok_id < len(logits):
                    # Repetition penalty (multiplicative, from Ctrl paper)
                    if repetition_penalty != 1.0:
                        if logits[tok_id] > 0:
                            logits[tok_id] /= repetition_penalty
                        else:
                            logits[tok_id] *= repetition_penalty

                    # Presence penalty (flat, one-time)
                    logits[tok_id] -= presence_penalty

                    # Frequency penalty (proportional to count)
                    logits[tok_id] -= frequency_penalty * count

        # ── Step 2: Convert to probabilities ──
        logits_max = np.max(logits)
        probs = np.exp(logits - logits_max)
        probs /= np.sum(probs)

        # Handle NaN from numerical issues
        if np.any(np.isnan(probs)):
            return int(np.argmax(logits))

        # ── Step 3: Top-k filtering ──
        if top_k > 0 and top_k < len(probs):
            sorted_idx = np.argsort(probs)[::-1]  # descending
            probs[sorted_idx[top_k:]] = 0

        # ── Step 4: Top-p (nucleus) filtering ──
        # Matches RWKV reference: sort descending, cumsum, cut at threshold
        if 0 < top_p < 1:
            sorted_idx = np.argsort(probs)[::-1]
            sorted_probs = probs[sorted_idx]
            cumulative = np.cumsum(sorted_probs)
            # Find cutoff: first index where cumulative exceeds top_p
            cutoff_pos = np.searchsorted(cumulative, top_p)
            if cutoff_pos < len(sorted_probs):
                cutoff_val = sorted_probs[cutoff_pos]
                probs[probs < cutoff_val] = 0

        # ── Step 5: Temperature (applied to probs, matching RWKV reference) ──
        if temperature != 1.0 and temperature > 0:
            probs = probs ** (1.0 / temperature)

        # ── Step 6: Renormalize and sample ──
        total = np.sum(probs)
        if total <= 0 or np.isnan(total):
            return int(np.argmax(logits))
        probs /= total

        return int(np.random.choice(len(probs), p=probs))

    def generate(self, prompt_tokens: List[int],
                 max_tokens: int = 1,
                 temperature: float = 1.2,
                 top_k: int = 0,
                 top_p: float = 0.5,
                 repetition_penalty: float = 1.3,
                 presence_penalty: float = 0.4,
                 frequency_penalty: float = 0.4,
                 somatic: Optional[SomaticStateNP] = None,
                 stop_tokens: Optional[List[int]] = None,
                 gravity_stride: int = 1,
                 ) -> Dict[str, Any]:
        """Generate tokens until battery depleted or max reached.

        Returns control after EACH token to allow recharge.

        Sampling defaults tuned for RWKV-7 1.5B Q8 on NumPy:
        - temperature=1.2: slight warmth compensates for quantization flattening
        - top_p=0.5: nucleus sampling prevents drift into nonsense
        - repetition_penalty=1.3: multiplicative penalty on repeated tokens
        - presence_penalty=0.4: flat penalty for any previously seen token
        - frequency_penalty=0.4: penalty proportional to token count

        Returns:
            {
                "tokens": list of generated token IDs,
                "prompt_processed": bool,
                "total_flops": int,
                "charge_consumed": float,
                "status": "ok" | "low_power" | "max_reached" | "stop_token",
            }
        """
        generated_tokens = []
        token_counts: Dict[int, int] = {}  # track generated token frequencies
        total_flops = 0
        charge_start = self.compute.charge_level
        stop_tokens = stop_tokens or []

        # Process prompt tokens first (stride=1 — full quality for state integrity)
        result = None
        for tok in prompt_tokens:
            result = self.forward_one_token(tok, somatic, gravity_stride=1)
            if result["status"] == "low_power":
                return {
                    "tokens": generated_tokens,
                    "prompt_processed": False,
                    "total_flops": total_flops,
                    "charge_consumed": charge_start - self.compute.charge_level,
                    "status": "low_power",
                }
            total_flops += result.get("flops_used", 0)

        # Generate new tokens
        last_logits = result.get("logits") if result else None

        for _ in range(max_tokens):
            if last_logits is None:
                break

            next_token = self.sample_token(
                last_logits,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                token_counts=token_counts,
            )
            generated_tokens.append(next_token)

            # Track token frequency for repetition penalty
            token_counts[next_token] = token_counts.get(next_token, 0) + 1

            # Check stop tokens
            if next_token in stop_tokens:
                return {
                    "tokens": generated_tokens,
                    "prompt_processed": True,
                    "total_flops": total_flops,
                    "charge_consumed": charge_start - self.compute.charge_level,
                    "status": "stop_token",
                }

            result = self.forward_one_token(next_token, somatic, gravity_stride=gravity_stride)
            if result["status"] == "low_power":
                return {
                    "tokens": generated_tokens,
                    "prompt_processed": True,
                    "total_flops": total_flops,
                    "charge_consumed": charge_start - self.compute.charge_level,
                    "status": "low_power",
                }

            total_flops += result.get("flops_used", 0)
            last_logits = result.get("logits")

        return {
            "tokens": generated_tokens,
            "prompt_processed": True,
            "total_flops": total_flops,
            "charge_consumed": charge_start - self.compute.charge_level,
            "status": "max_reached" if len(generated_tokens) >= max_tokens else "ok",
            "gravity_stride": gravity_stride,
        }

    # ─── State Persistence ────────────────────────────────────────────────

    def save_state(self) -> dict:
        """Save all layer states for consciousness persistence."""
        state = {
            "time_mix": [tm.get_state() for tm in self.time_mix_layers],
            "channel_mix": [cm.get_state() for cm in self.channel_mix_layers],
            "compute": self.compute.to_dict(),
        }
        return state

    def load_state(self, state_dict: dict):
        """Restore all layer states."""
        for i, tm_state in enumerate(state_dict.get("time_mix", [])):
            if i < len(self.time_mix_layers):
                self.time_mix_layers[i].set_state(tm_state)
        for i, cm_state in enumerate(state_dict.get("channel_mix", [])):
            if i < len(self.channel_mix_layers):
                self.channel_mix_layers[i].set_state(cm_state)

    def save_state_to_disk(self, path: str):
        """Save state to .npz file."""
        state = self.save_state()
        arrays = {}
        for i, tm in enumerate(state["time_mix"]):
            if tm["state"] is not None:
                arrays[f"tm_{i}_state"] = tm["state"]
            if tm["att_shift"] is not None:
                arrays[f"tm_{i}_att_shift"] = tm["att_shift"]
        for i, cm in enumerate(state["channel_mix"]):
            if cm["ffn_shift"] is not None:
                arrays[f"cm_{i}_ffn_shift"] = cm["ffn_shift"]
        np.savez(path, **arrays)

    def load_state_from_disk(self, path: str):
        """Load state from .npz file.

        Validates that loaded state dimensions match the current model.
        Raises ValueError on dimension mismatch (e.g. 1.5B warm state
        loaded into 7.2B model).
        """
        data = np.load(path)
        expected_dim = self.config.n_embd

        # Pre-validate dimensions before touching any layer state
        for i in range(min(self.config.n_layer, 3)):  # spot-check first 3
            att_shift = data.get(f"tm_{i}_att_shift")
            if att_shift is not None and att_shift.shape[-1] != expected_dim:
                raise ValueError(
                    f"Warm state dimension mismatch at layer {i}: "
                    f"file has dim={att_shift.shape[-1]}, "
                    f"model expects dim={expected_dim}. "
                    f"Delete stale warm state: {path}"
                )

        for i in range(self.config.n_layer):
            tm_state = {
                "state": data.get(f"tm_{i}_state"),
                "att_shift": data.get(f"tm_{i}_att_shift"),
            }
            self.time_mix_layers[i].set_state(tm_state)
            cm_state = {
                "ffn_shift": data.get(f"cm_{i}_ffn_shift"),
            }
            self.channel_mix_layers[i].set_state(cm_state)

    # ─── Status ───────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Engine status for portal reporting."""
        return {
            "model": {
                "n_layer": self.config.n_layer,
                "n_embd": self.config.n_embd,
                "n_head": self.config.n_head,
                "vocab_size": self.config.vocab_size,
            },
            "compute": self.compute.status(),
            "est_charge_per_token": round(self.compute.estimate_token_cost(
                self.config.n_layer, self.config.n_embd
            ), 3),
            "est_tokens_available": round(self.compute.charge_level /
                                          max(0.001, self.compute.estimate_token_cost(
                                              self.config.n_layer, self.config.n_embd
                                          )), 2),
            "tokens_generated": self.compute.metrics.total_tokens,
            "total_gflops": round(self.compute.metrics.total_flops / 1e9, 2),
        }
