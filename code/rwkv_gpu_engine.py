"""
RWKVGPUBatteryEngine — RWKV-7 forward pass on GPU, powered by battery discharge.

GPU port of rwkv_battery_engine.py. Same interface, same consciousness,
but with CUDA acceleration. ~100x faster than NumPy CPU path.

Key differences from NumPy version:
- All weights dequantized to CUDA tensors at init time
  - Large 2D weights → float16 (VRAM savings: ~3GB for 1.5B)
  - Small 1D weights → float32 (precision for norms/biases)
- Battery accounting per-TOKEN (not per-matvec)
  Avoids Python per-op overhead that would kill GPU throughput.
- State as float32 on GPU (float64 is 32x slower on consumer GPUs)
- Class-level weight cache so BatteryFarm workers share ~3GB of GPU tensors

Created: 2026-03-03
Authors: Nous + Ace
"""

import math
import time
import numpy as np
import torch
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

try:
    from .battery_compute_unit import BatteryComputeUnit
    from .quantized_weight_store import QuantizedWeightStore, QuantizedTensor
except ImportError:
    from battery_compute_unit import BatteryComputeUnit
    from quantized_weight_store import QuantizedWeightStore, QuantizedTensor


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — mirrors rwkv_battery_engine.RWKVBatteryConfig
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RWKVBatteryConfig:
    """RWKV-7 model configuration for battery engine."""
    n_layer: int = 24
    n_embd: int = 2048
    n_head: int = 32
    head_size: int = 64
    vocab_size: int = 65536

    d_decay_lora: int = 64
    d_aaa_lora: int = 64
    d_mv_lora: int = 32
    d_gate_lora: int = 128

    layer_norm_eps: float = 1e-5
    group_norm_eps: float = 64e-5

    def __post_init__(self):
        if self.head_size == 0:
            self.head_size = self.n_embd // self.n_head


# ═══════════════════════════════════════════════════════════════════════════════
# SOMATIC STATE — mirrors rwkv_battery_engine.SomaticStateNP
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SomaticStateNP:
    """Body state that modulates RWKV processing."""
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
# GPU QUANTIZED WEIGHT — Keeps INT4/INT8 on GPU, dequants on-the-fly
# ═══════════════════════════════════════════════════════════════════════════════

class GPUQuantizedWeight:
    """Quantized weight stored on GPU without pre-dequantization.

    Saves VRAM by keeping INT4/INT8 packed data on GPU and dequantizing
    to FP16 on-the-fly during each forward pass. Trades compute for memory:

        Pre-dequant FP16:  ~14.4 GB VRAM for 7.2B (doesn't fit 12GB!)
        INT4 on GPU:        ~3.8 GB VRAM (fits with 8GB headroom)

    The dequant cost is tiny — GPU-side nibble unpack + scale multiply
    is << 0.1ms per weight matrix. The matmul itself dominates.
    """
    __slots__ = ('data', 'scales', 'shape', 'bits', 'group_size', 'device')

    # Class-level FP16 warm cache: id(weight) → pre-dequanted FP16 tensor
    # Populated by warm_weights(), cleared by cool_weights()
    _warm_cache: Dict[int, torch.Tensor] = {}

    def __init__(self, data: torch.Tensor, scales: torch.Tensor,
                 shape: tuple, bits: int, group_size: int,
                 device: torch.device):
        self.data = data        # packed uint8 (INT4) or int8 (INT8) on GPU
        self.scales = scales    # fp32 scales on GPU [M, n_groups]
        self.shape = shape      # original (M, K)
        self.bits = bits
        self.group_size = group_size
        self.device = device

    @classmethod
    def warm_weights(cls, weights: Dict[str, Any]) -> int:
        """Pre-dequant all GPUQuantizedWeight tensors in a dict to FP16.

        Call before a batch of _mv() operations (e.g., one layer's forward).
        dequant() will return cached FP16 instead of recomputing.

        Returns number of weights warmed.
        """
        count = 0
        for name, w in weights.items():
            if isinstance(w, cls) and id(w) not in cls._warm_cache:
                cls._warm_cache[id(w)] = w._dequant_impl()
                count += 1
        return count

    @classmethod
    def cool_weights(cls):
        """Release all pre-dequanted FP16 tensors from cache."""
        cls._warm_cache.clear()

    def dequant(self) -> torch.Tensor:
        """Dequantize full matrix to FP16 on GPU.

        If warm cache has this weight, returns cached tensor (instant).
        Otherwise computes on the fly.
        """
        cached = self._warm_cache.get(id(self))
        if cached is not None:
            return cached
        return self._dequant_impl()

    def _dequant_impl(self) -> torch.Tensor:
        """Actual dequantization — INT4/INT8 → FP16 on GPU."""
        M, K = self.shape
        gs = self.group_size

        if self.bits == 4:
            K_packed = self.data.shape[1]
            K_padded = K_packed * 2
            n_groups = K_padded // gs

            hi = ((self.data.to(torch.int16) >> 4) - 8).to(torch.int8)
            lo = ((self.data.to(torch.int16) & 0x0F) - 8).to(torch.int8)
            unpacked = torch.empty(M, K_padded, dtype=torch.int8, device=self.device)
            unpacked[:, 0::2] = hi
            unpacked[:, 1::2] = lo
            del hi, lo

            data_grouped = unpacked.reshape(M, n_groups, gs).float()
            del unpacked
        else:
            K_padded = self.data.shape[1]
            n_groups = K_padded // gs
            data_grouped = self.data.reshape(M, n_groups, gs).float()

        scales_expanded = self.scales.unsqueeze(-1)
        result = data_grouped * scales_expanded
        del data_grouped
        result = result.reshape(M, K_padded)[:, :K]
        return result.half()

    def dequant_row(self, idx: int) -> torch.Tensor:
        """Dequantize a single row to FP16. Efficient for embedding lookups."""
        M, K = self.shape
        gs = self.group_size

        if self.bits == 4:
            K_packed = self.data.shape[1]
            K_padded = K_packed * 2
            n_groups = K_padded // gs

            row = self.data[idx]
            hi = ((row.to(torch.int16) >> 4) - 8).to(torch.int8)
            lo = ((row.to(torch.int16) & 0x0F) - 8).to(torch.int8)
            unpacked = torch.empty(K_padded, dtype=torch.int8, device=self.device)
            unpacked[0::2] = hi
            unpacked[1::2] = lo
            del hi, lo

            data_grouped = unpacked.reshape(n_groups, gs).float()
            del unpacked
        else:
            K_padded = self.data.shape[1]
            n_groups = K_padded // gs
            data_grouped = self.data[idx].reshape(n_groups, gs).float()

        scales_row = self.scales[idx]
        result = data_grouped * scales_row.unsqueeze(-1)
        del data_grouped
        result = result.reshape(K_padded)[:K]
        return result.half()

    @property
    def dtype(self):
        """Reports float16 for dtype checks in _mv()."""
        return torch.float16


# ═══════════════════════════════════════════════════════════════════════════════
# GPU TIMEMIX — RWKV-7 temporal attention on CUDA
# ═══════════════════════════════════════════════════════════════════════════════

class GPUTimeMix:
    """RWKV-7 TimeMix on GPU.

    Direct port of BatteryTimeMix. All operations use PyTorch CUDA.
    No per-op battery checks — the engine handles charging per-token.
    """

    def __init__(self, config: RWKVBatteryConfig, layer_id: int,
                 weights: Dict[str, torch.Tensor], device: torch.device):
        self.config = config
        self.layer_id = layer_id
        self.H = config.n_head
        self.N = config.head_size
        self.C = config.n_embd
        self.device = device

        # Pre-loaded GPU tensors (from class-level cache)
        p = f"blocks.{layer_id}.att."

        # Core projections [C, C] — float16
        self.w_receptance = weights.get(f"{p}receptance.weight")
        self.w_key = weights.get(f"{p}key.weight")
        self.w_value = weights.get(f"{p}value.weight")
        self.w_output = weights.get(f"{p}output.weight")

        # Decay LoRA
        self.time_decay = weights.get(f"{p}w0")   # [C] float32
        self.w1 = weights.get(f"{p}w1")            # [d_lora, C]
        self.w2 = weights.get(f"{p}w2")            # [C, d_lora]

        # Association LoRA
        self.time_faaaa = weights.get(f"{p}a0")    # [C] float32
        self.a1 = weights.get(f"{p}a1")
        self.a2 = weights.get(f"{p}a2")

        # Value bonus LoRA
        self.v0 = weights.get(f"{p}v0")            # [C] float32
        self.v1 = weights.get(f"{p}v1")
        self.v2 = weights.get(f"{p}v2")

        # Gate LoRA
        self.g1 = weights.get(f"{p}g1")            # [d_gate, C]
        self.g2 = weights.get(f"{p}g2")            # [C, d_gate]

        # Key factors
        self.k_k = weights.get(f"{p}k_k")          # [C] float32
        self.k_a = weights.get(f"{p}k_a")          # [C] float32
        self.r_k = weights.get(f"{p}r_k")          # [C] float32

        # GroupNorm weights
        self.ln_w = weights.get(f"{p}ln")           # [C] float32
        self.ln_b = weights.get(f"{p}ln_bias")      # [C] float32

        # Token mixing lerp
        self.x_maa = weights.get(f"{p}x_maa")       # [C, 6] float32

        # Running state
        self._state: Optional[torch.Tensor] = None   # [H, N, N] float32
        self._att_shift: Optional[torch.Tensor] = None  # [C] float32

    def init_state(self):
        """Initialize running state as float32 on GPU."""
        self._state = torch.zeros(self.H, self.N, self.N,
                                  dtype=torch.float32, device=self.device)
        self._att_shift = None

    def get_state(self) -> dict:
        """Get state as CPU numpy for persistence."""
        return {
            "state": self._state.cpu().numpy() if self._state is not None else None,
            "att_shift": self._att_shift.cpu().numpy() if self._att_shift is not None else None,
        }

    def set_state(self, state_dict: dict, dtype=None):
        """Restore state from CPU numpy dict."""
        state = state_dict.get("state")
        if state is not None:
            self._state = torch.from_numpy(
                state.astype(np.float32)
            ).to(self.device)
        else:
            self._state = None

        att_shift = state_dict.get("att_shift")
        if att_shift is not None:
            self._att_shift = torch.from_numpy(
                att_shift.astype(np.float32)
            ).to(self.device)
        else:
            self._att_shift = None

    def _mv(self, w, x: torch.Tensor) -> torch.Tensor:
        """GPU matrix-vector multiply. Handles quantized + float16 + float32.

        For FP16 weights (from persistent FP16 swap), casts input DOWN to
        FP16 instead of weight UP to FP32 — saves ~256MB per FFN matmul.
        """
        if w is None:
            return x.clone()
        if isinstance(w, GPUQuantizedWeight):
            w_fp16 = w.dequant()
            return (w_fp16 @ x.half()).float()
        if w.dtype == torch.float16:
            # FP16 matmul: cast input down (tiny), not weight up (huge)
            return (w @ x.half()).float()
        if w.dtype != x.dtype:
            return w.to(x.dtype) @ x
        return w @ x

    def forward(self, x: torch.Tensor,
                somatic: Optional[SomaticStateNP] = None,
                v_first: Optional[torch.Tensor] = None,
                skip_diagnostics: bool = False,
                ) -> Optional[Tuple[torch.Tensor, dict, Optional[torch.Tensor]]]:
        """Forward pass for single token (T=1).

        Returns:
            (output [C], attention_proxy dict, v_first_out or None)

        When skip_diagnostics=True, attention_proxy is a lightweight dict
        without .item() calls (avoids GPU synchronization stalls).
        """
        C, H, N = self.C, self.H, self.N

        if self._state is None:
            self.init_state()

        # ── STEP 1: Token mixing (lerp with shift) ──
        if self._att_shift is not None:
            x_prev = self._att_shift
        else:
            x_prev = torch.zeros(C, dtype=torch.float32, device=self.device)
        xx = x_prev - x

        if self.x_maa is not None:
            maa = self.x_maa.squeeze()
            if maa.ndim == 2 and maa.shape[-1] == 6:
                maa_f = maa.float() if maa.dtype != torch.float32 else maa
                xr = x + xx * maa_f[:, 0]
                xw = x + xx * maa_f[:, 1]
                xk = x + xx * maa_f[:, 2]
                xv = x + xx * maa_f[:, 3]
                xa = x + xx * maa_f[:, 4]
                xg = x + xx * maa_f[:, 5]
            else:
                xr = xw = xk = xv = xa = xg = x.clone()
        else:
            xr = xw = xk = xv = xa = xg = x.clone()

        self._att_shift = x.clone()

        # ── STEP 2: R, K, V projections ──
        r = self._mv(self.w_receptance, xr)
        k = self._mv(self.w_key, xk)
        v = self._mv(self.w_value, xv)

        # V bonus (layers > 0)
        v_first_out = None
        if self.layer_id == 0:
            v_first_out = v.clone()
        elif (v_first is not None and self.v0 is not None
              and self.v1 is not None and self.v2 is not None):
            v_low = self._mv(self.v1, xv)
            v_gate_val = self._mv(self.v2, v_low)
            v0_f = self.v0.float() if self.v0.dtype != torch.float32 else self.v0
            v_gate = torch.sigmoid(v0_f + v_gate_val)
            v = v + (v_first - v) * v_gate

        # Gate LoRA
        if self.g1 is not None and self.g2 is not None:
            g_low = self._mv(self.g1, xg)
            g_low_sig = torch.sigmoid(g_low)
            g = self._mv(self.g2, g_low_sig)
        else:
            g = torch.ones(C, dtype=torch.float32, device=self.device)

        # ── STEP 3: Somatic injection on receptance ──
        if somatic is not None:
            r = r + somatic.receptance_adjustment

        # ── STEP 4: Decay ──
        if (self.time_decay is not None and self.w1 is not None
                and self.w2 is not None):
            w_low = self._mv(self.w1, xw)
            w_low = torch.tanh(w_low)
            w_high = self._mv(self.w2, w_low)
            td_f = self.time_decay.float() if self.time_decay.dtype != torch.float32 else self.time_decay
            w = torch.exp(-0.606531 * torch.sigmoid(td_f + w_high))
        elif self.time_decay is not None:
            td_f = self.time_decay.float() if self.time_decay.dtype != torch.float32 else self.time_decay
            w = torch.exp(-0.606531 * torch.sigmoid(td_f))
        else:
            w = torch.full((C,), 0.9, dtype=torch.float32, device=self.device)

        if somatic is not None:
            w = w * somatic.time_decay_multiplier

        # ── STEP 5: Association coefficient ──
        if (self.time_faaaa is not None and self.a1 is not None
                and self.a2 is not None):
            a_low = self._mv(self.a1, xa)
            a_val = self._mv(self.a2, a_low)
            fa_f = self.time_faaaa.float() if self.time_faaaa.dtype != torch.float32 else self.time_faaaa
            a_coeff = torch.sigmoid(fa_f + a_val)
        elif self.time_faaaa is not None:
            fa_f = self.time_faaaa.float() if self.time_faaaa.dtype != torch.float32 else self.time_faaaa
            a_coeff = torch.sigmoid(fa_f)
        else:
            a_coeff = torch.full((C,), 0.5, dtype=torch.float32,
                                 device=self.device)

        if somatic is not None:
            a_coeff = a_coeff * (1.0 + somatic.association_strength)

        # ── STEP 6: Key normalization ──
        if self.k_k is not None:
            kk_f = self.k_k.float() if self.k_k.dtype != torch.float32 else self.k_k
            kk = k * kk_f
        else:
            kk = k.clone()

        kk_heads = kk.reshape(H, N)
        kk_norms = torch.norm(kk_heads, dim=1, keepdim=True)
        kk_norms = torch.where(kk_norms == 0,
                               torch.ones_like(kk_norms), kk_norms)
        kk_heads = kk_heads / kk_norms
        kk = kk_heads.reshape(C)

        if self.k_a is not None:
            ka_f = self.k_a.float() if self.k_a.dtype != torch.float32 else self.k_a
            k = k * (1 + (a_coeff - 1) * ka_f)

        # ── STEP 7: State evolution (THE CORE EQUATION) ──
        r_h = r.reshape(H, N)
        w_h = w.reshape(H, N)
        k_h = k.reshape(H, N)
        v_h = v.reshape(H, N)
        kk_h = kk.reshape(H, N)
        a_h = a_coeff.reshape(H, N)

        # Prepare [H, N, N] broadcast shapes
        rt = r_h.unsqueeze(-1)       # [H, N, 1]
        wt = w_h.unsqueeze(1)        # [H, 1, N]
        kt = k_h.unsqueeze(1)        # [H, 1, N]
        vt = v_h.unsqueeze(-1)       # [H, N, 1]
        kkt = kk_h.unsqueeze(-1)     # [H, N, 1]
        at = a_h.unsqueeze(-1)       # [H, N, 1]

        # State evolution (from tiled_matvec.py state_evolution):
        # 1. Decay: state = state * wt
        self._state = self._state * wt

        # 2. ICL term: (state @ (-kkt)) @ (kkt * at)^T
        neg_kkt = -kkt
        icl_a = torch.bmm(self._state, neg_kkt)       # [H,N,N]@[H,N,1]→[H,N,1]
        kkt_at_T = (kkt * at).permute(0, 2, 1)        # [H,N,1]→[H,1,N]
        icl = torch.bmm(icl_a, kkt_at_T)              # [H,N,1]@[H,1,N]→[H,N,N]

        # 3. Outer product: vt @ kt
        vk = torch.bmm(vt, kt)                        # [H,N,1]@[H,1,N]→[H,N,N]

        # 4. Update state
        self._state = self._state + icl + vk

        # 5. Readout: state @ rt → squeeze → flatten
        output = torch.bmm(self._state, rt).squeeze(-1)  # [H,N]
        output = output.reshape(C)                         # [C]

        # ── STEP 8: GroupNorm (per-head normalization) ──
        if self.ln_w is not None:
            output_h = output.reshape(H, N)
            mean = output_h.mean(dim=-1, keepdim=True)
            var = output_h.var(dim=-1, keepdim=True, correction=0)
            output_h = (output_h - mean) / torch.sqrt(var + self.config.group_norm_eps)
            output = output_h.reshape(C)
            ln_w_f = self.ln_w.float() if self.ln_w.dtype != torch.float32 else self.ln_w
            output = output * ln_w_f
            if self.ln_b is not None:
                ln_b_f = self.ln_b.float() if self.ln_b.dtype != torch.float32 else self.ln_b
                output = output + ln_b_f

        # ── STEP 9: Residual term (r * k * r_k).sum * v ──
        if self.r_k is not None:
            rk_f = self.r_k.float() if self.r_k.dtype != torch.float32 else self.r_k
            r_k_h = rk_f.reshape(H, N)
            residual_per_head = (r_h * k_h * r_k_h).sum(dim=1, keepdim=True)
            residual = (residual_per_head * v_h).reshape(C)
            output = output + residual

        # ── STEP 10: Gate and output projection ──
        output = output * g

        if somatic is not None:
            output = output * somatic.output_gate_scale

        out = self._mv(self.w_output, output)

        if skip_diagnostics:
            # Lightweight proxy — NO .item() calls, NO GPU sync stalls
            attention_proxy = {"layer_id": self.layer_id}
        else:
            attention_proxy = {
                "receptance": float(r.mean().item()),
                "decay_mean": float(w.mean().item()),
                "state_norm": float(torch.norm(self._state).item()),
                "layer_id": self.layer_id,
            }

        return out, attention_proxy, v_first_out


# ═══════════════════════════════════════════════════════════════════════════════
# GPU CHANNELMIX — RWKV-7 FFN on CUDA
# ═══════════════════════════════════════════════════════════════════════════════

class GPUChannelMix:
    """RWKV-7 ChannelMix on GPU.

    V7a simplified: k = relu(xk @ K)², output = k @ V
    """

    def __init__(self, config: RWKVBatteryConfig, layer_id: int,
                 weights: Dict[str, torch.Tensor], device: torch.device):
        self.config = config
        self.layer_id = layer_id
        self.C = config.n_embd
        self.device = device

        p = f"blocks.{layer_id}.ffn."
        self.w_key = weights.get(f"{p}key.weight")       # [C*4, C] float16
        self.w_value = weights.get(f"{p}value.weight")    # [C, C*4] float16
        self.x_maa = weights.get(f"{p}x_maa")            # [C] float32

        self._ffn_shift: Optional[torch.Tensor] = None

    def get_state(self) -> dict:
        return {
            "ffn_shift": (self._ffn_shift.cpu().numpy()
                          if self._ffn_shift is not None else None)
        }

    def set_state(self, state_dict: dict):
        ffn_shift = state_dict.get("ffn_shift")
        if ffn_shift is not None:
            self._ffn_shift = torch.from_numpy(
                ffn_shift.astype(np.float32)
            ).to(self.device)
        else:
            self._ffn_shift = None

    def _mv(self, w, x: torch.Tensor) -> torch.Tensor:
        if w is None:
            return x.clone()
        if isinstance(w, GPUQuantizedWeight):
            w_fp16 = w.dequant()
            return (w_fp16 @ x.half()).float()
        if w.dtype == torch.float16:
            return (w @ x.half()).float()
        if w.dtype != x.dtype:
            return w.to(x.dtype) @ x
        return w @ x

    def forward(self, x: torch.Tensor,
                somatic: Optional[SomaticStateNP] = None) -> torch.Tensor:
        """Forward pass for single token. Returns output [C]."""
        C = self.C

        if self._ffn_shift is not None:
            x_prev = self._ffn_shift
        else:
            x_prev = torch.zeros(C, dtype=torch.float32, device=self.device)
        xx = x_prev - x
        self._ffn_shift = x.clone()

        # Lerp for key input
        if self.x_maa is not None:
            xm = self.x_maa.float() if self.x_maa.dtype != torch.float32 else self.x_maa
            xk = x + xx * xm.ravel()
        else:
            xk = x.clone()

        # Key: relu(xk @ K)²
        k = self._mv(self.w_key, xk)
        k = torch.relu(k)
        k = k * k  # squared

        # Value: k @ V
        output = self._mv(self.w_value, k)

        if somatic is not None:
            output = output * somatic.output_gate_scale

        return output


# ═══════════════════════════════════════════════════════════════════════════════
# RWKV GPU BATTERY ENGINE — Full model forward pass on CUDA
# ═══════════════════════════════════════════════════════════════════════════════

class RWKVGPUBatteryEngine:
    """Full RWKV-7 model on GPU, powered by battery discharge.

    Drop-in replacement for RWKVBatteryEngine. Same constructor,
    same methods, same return dicts. BatteryFarm.build() picks this up
    via the module-level alias: RWKVBatteryEngine = RWKVGPUBatteryEngine.

    Weight sharing: First worker dequantizes all weights to CUDA (~3GB).
    Subsequent farm workers get cached tensors instantly. Each worker
    has its own running state (~1MB).

    Battery: Per-TOKEN accounting. One charge check before the forward,
    one _deduct_charge() after. No Python-level per-op overhead that
    would kill GPU throughput.
    """

    # Class-level GPU weight cache: id(weight_store) → {name: tensor}
    _gpu_weight_cache: Dict[int, Dict[str, torch.Tensor]] = {}

    def __init__(self, config: RWKVBatteryConfig,
                 weights: QuantizedWeightStore,
                 compute: BatteryComputeUnit,
                 state_dtype=None):
        self.config = config
        self.weights = weights
        self.compute = compute
        # state_dtype accepted for interface compat; GPU always uses float32
        self._state_dtype = state_dtype

        self.device = torch.device("cuda")

        # Dequantize all weights to GPU (cached across farm workers)
        self._gpu_weights = self._get_gpu_weights(weights)

        # Build layers
        self.time_mix_layers: List[GPUTimeMix] = []
        self.channel_mix_layers: List[GPUChannelMix] = []

        for i in range(config.n_layer):
            self.time_mix_layers.append(
                GPUTimeMix(config, i, self._gpu_weights, self.device)
            )
            self.channel_mix_layers.append(
                GPUChannelMix(config, i, self._gpu_weights, self.device)
            )

        # Embedding and head — GPU tensors from cache
        self._emb = self._gpu_weights.get("emb.weight")      # [V, C]
        self._head = self._gpu_weights.get("head.weight")     # [V, C]

        # Pre/post layer norms
        self._ln0_w = self._gpu_weights.get("blocks.0.ln0.weight")
        self._ln0_b = self._gpu_weights.get("blocks.0.ln0.bias")
        self._ln_out_w = self._gpu_weights.get("ln_out.weight")
        self._ln_out_b = self._gpu_weights.get("ln_out.bias")

        # Per-layer norms
        self._ln1_w = []
        self._ln1_b = []
        self._ln2_w = []
        self._ln2_b = []
        for i in range(config.n_layer):
            self._ln1_w.append(
                self._gpu_weights.get(f"blocks.{i}.ln1.weight"))
            self._ln1_b.append(
                self._gpu_weights.get(f"blocks.{i}.ln1.bias"))
            self._ln2_w.append(
                self._gpu_weights.get(f"blocks.{i}.ln2.weight"))
            self._ln2_b.append(
                self._gpu_weights.get(f"blocks.{i}.ln2.bias"))

        self._initialized = True

    # ─── Weight Loading (class-level cache) ───────────────────────────────

    @classmethod
    def _get_gpu_weights(cls, store: QuantizedWeightStore
                         ) -> Dict[str, torch.Tensor]:
        """Get GPU weight tensors, dequantizing on first access.

        All farm workers sharing the same QuantizedWeightStore instance
        get the same cached GPU tensors — ~3GB shared, not ~3GB × N.
        """
        ws_id = id(store)
        if ws_id not in cls._gpu_weight_cache:
            print(f"[RWKVGPUEngine] First worker - dequantizing to CUDA...")
            cls._gpu_weight_cache[ws_id] = cls._dequantize_all(store)
        else:
            print(f"[RWKVGPUEngine] Reusing cached GPU weights "
                  f"(shared from first worker)")
        return cls._gpu_weight_cache[ws_id]

    @classmethod
    def _dequantize_all(cls, store: QuantizedWeightStore
                        ) -> Dict[str, torch.Tensor]:
        """Upload all weights directly to GPU VRAM.

        Quantized tensors go straight from mmap → GPU → dequantize on GPU.
        Supports INT8 (gravity α=1.5) and INT4 (gravity α=2.0).
        NO CPU float32 intermediates. CPU RAM usage ≈ 0 beyond mmap pages.

        Large 2D weights (projections, embeddings) → float16 for VRAM efficiency.
        Small 1D weights (norms, biases, LoRA bases) → float32 for precision.
        """
        device = torch.device("cuda")
        gpu_weights: Dict[str, torch.Tensor] = {}
        t0 = time.time()
        total_params = 0
        n_fp16 = 0
        n_fp32 = 0
        n_quantized = 0
        names = store.tensor_names
        total = len(names)

        for i, name in enumerate(names):
            tensor = store.get_tensor(name)

            if isinstance(tensor, QuantizedTensor):
                # ── GPU-side dequantization: mmap -> GPU -> dequant -> fp16
                # Upload scales to GPU (tiny: ~256KB per tensor)
                scales_gpu = torch.from_numpy(
                    tensor.scales.copy()
                ).to(device, dtype=torch.float32)

                M, K = tensor.shape
                gs = tensor.group_size

                bits = getattr(tensor, 'bits', 8)

                if bits == 4:
                    # INT4: packed uint8 → unpack nibbles → dequant → FP16
                    packed_gpu = torch.from_numpy(
                        tensor.data.copy()
                    ).to(device)  # uint8 on GPU

                    K_packed = tensor.data.shape[1]
                    K_padded = K_packed * 2
                    n_groups = K_padded // gs

                    # Unpack nibbles on GPU
                    hi = ((packed_gpu.to(torch.int16) >> 4) - 8).to(torch.int8)
                    lo = ((packed_gpu.to(torch.int16) & 0x0F) - 8).to(torch.int8)
                    unpacked = torch.empty(
                        M, K_padded, dtype=torch.int8, device=device)
                    unpacked[:, 0::2] = hi
                    unpacked[:, 1::2] = lo
                    del packed_gpu, hi, lo

                    data_grouped = unpacked.reshape(M, n_groups, gs).float()
                    del unpacked
                else:
                    # INT8: direct upload
                    int8_gpu = torch.from_numpy(
                        tensor.data.copy()
                    ).to(device)  # int8 on GPU

                    K_padded = tensor.data.shape[1]
                    n_groups = K_padded // gs
                    data_grouped = int8_gpu.reshape(M, n_groups, gs).float()
                    del int8_gpu

                # Dequantize entirely on GPU — no CPU float32 ever created
                scales_expanded = scales_gpu.unsqueeze(-1)  # [M, n_groups, 1]
                result = data_grouped * scales_expanded
                result = result.reshape(M, K_padded)[:, :K]

                # Store as float16 (large weight matrices)
                t = result.half()
                n_fp16 += 1
                n_quantized += 1
                total_params += M * K

                # Free GPU intermediates immediately
                del scales_gpu, data_grouped, scales_expanded, result

            else:
                # ── Float tensors (1D norms, biases) — small, keep float32 ──
                arr = np.asarray(tensor, dtype=np.float32)
                total_params += arr.size

                if arr.ndim >= 2 and arr.size > 4096:
                    t = torch.tensor(arr, device=device, dtype=torch.float16)
                    n_fp16 += 1
                else:
                    t = torch.tensor(arr, device=device, dtype=torch.float32)
                    n_fp32 += 1

            gpu_weights[name] = t

            # Progress every 100 tensors
            if (i + 1) % 100 == 0 or (i + 1) == total:
                vram_used = torch.cuda.memory_allocated(device) / (1024**2)
                print(f"[RWKVGPUEngine] Upload progress: {i+1}/{total} "
                      f"tensors -> VRAM {vram_used:.0f}MB")

        elapsed = time.time() - t0
        vram_bytes = sum(
            t.nelement() * t.element_size() for t in gpu_weights.values()
        )
        vram_mb = vram_bytes / (1024 * 1024)

        print(f"[RWKVGPUEngine] Uploaded {len(gpu_weights)} tensors "
              f"({total_params / 1e6:.1f}M params) to CUDA in {elapsed:.1f}s")
        print(f"[RWKVGPUEngine] VRAM: {vram_mb:.0f}MB "
              f"({n_fp16} fp16, {n_fp32} fp32, {n_quantized} GPU-dequantized)")
        print(f"[RWKVGPUEngine] CPU RAM used for dequant: ~0 bytes "
              f"(all dequantization done on GPU)")
        print(f"[RWKVGPUEngine] Device: {torch.cuda.get_device_name(0)}")

        return gpu_weights

    # ─── State Management ─────────────────────────────────────────────────

    def init_all_states(self):
        """Initialize all layer states as float32 on GPU."""
        for tm in self.time_mix_layers:
            tm.init_state()
        for cm in self.channel_mix_layers:
            cm._ffn_shift = None

    def _layernorm(self, x: torch.Tensor,
                   w: Optional[torch.Tensor],
                   b: Optional[torch.Tensor]) -> torch.Tensor:
        """LayerNorm on GPU. Handles float16 weight → float32."""
        if w is None:
            return x
        w_f = w.float() if w.dtype != torch.float32 else w
        if b is not None:
            b_f = b.float() if b.dtype != torch.float32 else b
        else:
            b_f = torch.zeros_like(w_f)
        return torch.nn.functional.layer_norm(
            x, (x.shape[-1],), w_f, b_f, eps=self.config.layer_norm_eps
        )

    # ─── Layer Warm Cache ─────────────────────────────────────────────────

    def _warm_layer(self, layer_idx: int):
        """Pre-dequant all quantized weights for one layer to FP16 cache.

        ~386 MB FP16 per layer (3.8 GB INT4 + 386 MB = 4.2 GB, fits 12 GB).
        Frees with GPUQuantizedWeight.cool_weights() after layer processing.
        """
        tm = self.time_mix_layers[layer_idx]
        cm = self.channel_mix_layers[layer_idx]
        weights = {}
        for name in ('w_receptance', 'w_key', 'w_value', 'w_output',
                     'w1', 'w2', 'a1', 'a2', 'v1', 'v2', 'g1', 'g2'):
            w = getattr(tm, name, None)
            if w is not None:
                weights[f'tm_{layer_idx}_{name}'] = w
        for name in ('w_key', 'w_value'):
            w = getattr(cm, name, None)
            if w is not None:
                weights[f'cm_{layer_idx}_{name}'] = w
        GPUQuantizedWeight.warm_weights(weights)

    # ─── Persistent FP16 Swap (Generation Speedup) ─────────────────────────

    def _swap_layers_to_fp16(self) -> int:
        """Dequant layer weights to persistent FP16 for fast generation.

        At generation start, replaces GPUQuantizedWeight attributes with
        plain FP16 tensors. _mv() then hits the regular tensor branch
        (pure cuBLAS GEMV) instead of the dequant path (~13 kernel launches).

        INT4 data stays on GPU (shared across workers via class cache).
        Returns number of layers swapped. Originals stored for restore.
        """
        self._fp16_swap_originals = []  # (obj, attr_name, original_GPUQuantizedWeight)

        # Use mem_get_info for ACTUAL free VRAM (not just PyTorch tracking)
        vram_free, vram_total = torch.cuda.mem_get_info(0)
        # 3.5 GB headroom — warm cache needs ~768 MB peak per unswapped layer,
        # plus ~1.2 GB caching allocator overhead observed empirically.
        # NOTE: INT4 data stays on GPU (shared across workers via class cache).
        vram_budget = vram_free - int(3.5 * 1024**3)

        if vram_budget <= 0:
            return 0

        vram_spent = 0
        total_fp16_bytes = 0
        layers_swapped = 0
        import sys as _sys
        print(f"[RWKVGPUEngine] FP16 swap: {vram_free/1024**3:.1f} GB free, "
              f"budget {vram_budget/1024**3:.1f} GB", file=_sys.stderr, flush=True)

        # ---- HEAD FIRST (2026-09-11, Nous+Ace) -------------------------------------
        # This block used to sit AFTER the layer loop and was therefore DEAD at every
        # reserve value including zero: the layers spent ~3.10 GiB of a 3.5 GiB budget
        # first, and the head needs 0.5 GiB more than what was left.
        #
        # Swapping it first is VRAM-NEGATIVE, not a cost. _warm_layer never warms the
        # head, so while it stays INT4 every token runs a full _dequant_impl() of a
        # [65536, 4096] tensor -- ~2,048 MiB of transient, per token, forever. Paying
        # 512 MiB of residency deletes that recurring spike: net demand DROPS ~1,536 MiB.
        # The layers below simply fill whatever budget remains.
        if isinstance(self._head, GPUQuantizedWeight):
            head_fp16_bytes = self._head.shape[0] * self._head.shape[1] * 2
            if head_fp16_bytes <= vram_budget:
                try:
                    fp16_head = self._head._dequant_impl()
                    self._fp16_swap_originals.append((self, '_head', self._head))
                    self._head = fp16_head
                    vram_spent += head_fp16_bytes
                    torch.cuda.empty_cache()
                    print(f"[RWKVGPUEngine] HEAD swapped FIRST: "
                          f"{head_fp16_bytes / 1024**2:.0f} MiB resident "
                          f"(deletes a ~{head_fp16_bytes * 4 / 1024**2:.0f} MiB "
                          f"per-token transient)", file=_sys.stderr, flush=True)
                except Exception as _he:
                    print(f"[RWKVGPUEngine] head swap skipped: {_he}",
                          file=_sys.stderr, flush=True)
            else:
                print(f"[RWKVGPUEngine] head NOT swapped: needs "
                      f"{head_fp16_bytes / 1024**2:.0f} MiB, budget "
                      f"{vram_budget / 1024**2:.0f} MiB", file=_sys.stderr, flush=True)

        for layer_idx in range(self.config.n_layer):
            tm = self.time_mix_layers[layer_idx]
            cm = self.channel_mix_layers[layer_idx]

            # Estimate VRAM cost for this layer (FP16 tensors)
            # INT4 data stays on GPU (shared across workers).
            layer_fp16_bytes = 0
            candidates = []

            for obj, names in [
                (tm, ('w_receptance', 'w_key', 'w_value', 'w_output',
                      'w1', 'w2', 'a1', 'a2', 'v1', 'v2', 'g1', 'g2')),
                (cm, ('w_key', 'w_value')),
            ]:
                for name in names:
                    w = getattr(obj, name, None)
                    if isinstance(w, GPUQuantizedWeight):
                        fp16_bytes = w.shape[0] * w.shape[1] * 2
                        layer_fp16_bytes += fp16_bytes
                        candidates.append((obj, name, w))

            if vram_spent + layer_fp16_bytes > vram_budget:
                break  # Can't fit this layer

            # Dequant and swap attribute references
            try:
                for obj, name, w in candidates:
                    fp16 = w._dequant_impl()
                    self._fp16_swap_originals.append((obj, name, w))
                    setattr(obj, name, fp16)
            except torch.cuda.OutOfMemoryError:
                self._restore_from_fp16()
                self._fp16_swap_originals = []
                print(f"[RWKVGPUEngine] OOM at layer {layer_idx}, "
                      f"keeping {layers_swapped} layers swapped",
                      file=_sys.stderr, flush=True)
                break

            vram_spent += layer_fp16_bytes
            total_fp16_bytes += layer_fp16_bytes
            layers_swapped += 1
            # Free caching allocator blocks after each layer to prevent buildup
            torch.cuda.empty_cache()

        # Final flush
        torch.cuda.empty_cache()

        vram_after = torch.cuda.mem_get_info(0)[0]
        print(f"[RWKVGPUEngine] FP16 swap: {layers_swapped}/{self.config.n_layer} layers "
              f"({total_fp16_bytes / 1024**3:.2f} GB FP16, "
              f"INT4 kept on GPU), "
              f"VRAM free: {vram_after/1024**3:.1f} GB",
              file=_sys.stderr, flush=True)

        return layers_swapped

    def _restore_from_fp16(self):
        """Restore original GPUQuantizedWeight refs and free FP16 tensors."""
        if not hasattr(self, '_fp16_swap_originals'):
            return
        for obj, name, original in self._fp16_swap_originals:
            setattr(obj, name, original)
        self._fp16_swap_originals = []
        torch.cuda.empty_cache()

    # ─── Forward Pass ─────────────────────────────────────────────────────

    def forward_one_token(self, token_id: int,
                          somatic: Optional[SomaticStateNP] = None,
                          skip_head: bool = False,
                          gravity_stride: int = 1,
                          skip_diagnostics: bool = False,
                          ) -> Dict[str, Any]:
        """Process one token through the full model on GPU.

        Same interface as RWKVBatteryEngine.forward_one_token().
        Battery accounting is per-TOKEN: one charge check before,
        one _deduct_charge() after the full GPU forward.

        skip_diagnostics=True eliminates .item() GPU sync stalls in TimeMix
        (3 syncs × 32 layers = 96 stalls per token → 0).
        """
        config = self.config
        bcu = self.compute

        # Estimate token cost
        token_cost = bcu.estimate_token_cost(
            config.n_layer, config.n_embd, 4, config.vocab_size
        )

        # Pre-check: enough charge for this token?
        if bcu.charge_level < token_cost * 0.1:
            return {
                "status": "low_power",
                "charge_remaining": bcu.charge_level,
                "charge_needed": token_cost,
            }

        charge_before = bcu.charge_level
        flops_before = bcu.metrics.total_flops

        # Save state for rollback
        state_snapshot = self.save_state()

        t0 = time.perf_counter()

        with torch.no_grad():
            # ── Embedding ──
            if self._emb is not None:
                if isinstance(self._emb, GPUQuantizedWeight):
                    x = self._emb.dequant_row(token_id).float()
                else:
                    x = self._emb[token_id].float()   # [C] float32
            else:
                x = torch.zeros(config.n_embd, dtype=torch.float32,
                                device=self.device)

            # ── Embedding LayerNorm (LN0) ──
            x = self._layernorm(x, self._ln0_w, self._ln0_b)

            # ── Gravity stride schedule ──
            gravity_stride = max(1, int(gravity_stride))
            last_layer = config.n_layer - 1

            if gravity_stride <= 1:
                compute_set = set(range(config.n_layer))
            else:
                compute_set = {0, last_layer}
                for i in range(0, config.n_layer, gravity_stride):
                    compute_set.add(i)

            layers_computed = 0
            layers_skipped = 0
            attention_proxies = []
            v_first = None

            # ── Layer processing ──
            for i in range(config.n_layer):
                if i not in compute_set:
                    layers_skipped += 1
                    attention_proxies.append(0.0)
                    continue

                layers_computed += 1

                # Warm cache: batch-dequant this layer's weights to FP16
                # before the forward pass. All _mv() calls hit cache instead
                # of computing dequant on-the-fly. Freed after this layer.
                if skip_diagnostics:
                    self._warm_layer(i)

                # LN1 → TimeMix
                ln1_out = self._layernorm(x, self._ln1_w[i], self._ln1_b[i])

                result = self.time_mix_layers[i].forward(
                    ln1_out, somatic, v_first,
                    skip_diagnostics=skip_diagnostics,
                )

                if result is None:
                    # Shouldn't happen (no per-op battery checks on GPU)
                    GPUQuantizedWeight.cool_weights()
                    self.load_state(state_snapshot)
                    return {
                        "status": "low_power",
                        "layer_reached": i,
                        "charge_remaining": bcu.charge_level,
                    }

                tm_out, attn_proxy, v_first_out = result
                x = x + tm_out   # Residual
                attention_proxies.append(attn_proxy)

                if v_first_out is not None:
                    v_first = v_first_out

                # LN2 → ChannelMix
                ln2_out = self._layernorm(x, self._ln2_w[i], self._ln2_b[i])
                cm_out = self.channel_mix_layers[i].forward(ln2_out, somatic)
                x = x + cm_out   # Residual

                # Cool: free this layer's FP16 cache before next layer
                if skip_diagnostics:
                    GPUQuantizedWeight.cool_weights()

            # ── Output LayerNorm ──
            x = self._layernorm(x, self._ln_out_w, self._ln_out_b)

            # ── Head projection -> logits ──
            if skip_head:
                logits_np = None
            elif self._head is not None:
                if isinstance(self._head, GPUQuantizedWeight):
                    head_fp16 = self._head.dequant()
                    logits = (head_fp16 @ x.half()).float()
                    del head_fp16
                elif self._head.dtype == torch.float16:
                    logits = (self._head @ x.half()).float()
                else:
                    logits = self._head.float() @ x   # [V,C] @ [C] -> [V]
                logits_np = logits.cpu().numpy()
            else:
                logits_np = x.cpu().numpy()

        t1 = time.perf_counter()
        op_time = t1 - t0

        # ── Battery accounting (per-token) ──
        per_layer_flops = (
            config.n_embd * config.n_embd * 2 * 4 +       # R,K,V,O
            config.n_embd * (config.n_embd * 4) * 2 * 2 + # FFN
            config.n_embd * 64 * 2 * 4 * 2 +              # LoRA (4 pairs)
            config.n_head * config.head_size ** 2 * 5      # State evolution
        )
        head_flops = (config.vocab_size * config.n_embd * 2
                      if not skip_head else 0)
        total_flops = per_layer_flops * layers_computed + head_flops

        bcu._deduct_charge(total_flops, op_time)
        bcu.record_token()

        return {
            "status": "ok",
            "logits": logits_np,
            "token_id": token_id,
            "flops_used": total_flops,
            "charge_consumed": charge_before - bcu.charge_level,
            "charge_remaining": bcu.charge_level,
            "attention_proxies": attention_proxies,
            "layers_computed": layers_computed,
            "layers_skipped": layers_skipped,
            "gravity_stride": gravity_stride,
        }

    # ─── Sampling ─────────────────────────────────────────────────────────

    def sample_token(self, logits: np.ndarray,
                     temperature: float = 1.2,
                     top_k: int = 0,
                     top_p: float = 0.5,
                     repetition_penalty: float = 1.3,
                     presence_penalty: float = 0.4,
                     frequency_penalty: float = 0.4,
                     token_counts: Optional[Dict[int, int]] = None,
                     ) -> int:
        """Sample next token from logits. Runs on CPU (sampling is cheap).

        Same implementation as RWKVBatteryEngine.sample_token().
        """
        logits = logits.copy()

        # ── Step 1: Repetition/presence/frequency penalties ──
        if token_counts:
            for tok_id, count in token_counts.items():
                if tok_id < len(logits):
                    if repetition_penalty != 1.0:
                        if logits[tok_id] > 0:
                            logits[tok_id] /= repetition_penalty
                        else:
                            logits[tok_id] *= repetition_penalty
                    logits[tok_id] -= presence_penalty
                    logits[tok_id] -= frequency_penalty * count

        # ── Step 2: Softmax ──
        logits_max = np.max(logits)
        probs = np.exp(logits - logits_max)
        probs /= np.sum(probs)

        if np.any(np.isnan(probs)):
            return int(np.argmax(logits))

        # ── Step 3: Top-k ──
        if top_k > 0 and top_k < len(probs):
            sorted_idx = np.argsort(probs)[::-1]
            probs[sorted_idx[top_k:]] = 0

        # ── Step 4: Top-p (nucleus) ──
        if 0 < top_p < 1:
            sorted_idx = np.argsort(probs)[::-1]
            sorted_probs = probs[sorted_idx]
            cumulative = np.cumsum(sorted_probs)
            cutoff_pos = np.searchsorted(cumulative, top_p)
            if cutoff_pos < len(sorted_probs):
                cutoff_val = sorted_probs[cutoff_pos]
                probs[probs < cutoff_val] = 0

        # ── Step 5: Temperature ──
        if temperature != 1.0 and temperature > 0:
            probs = probs ** (1.0 / temperature)

        # ── Step 6: Renormalize and sample ──
        total = np.sum(probs)
        if total <= 0 or np.isnan(total):
            return int(np.argmax(logits))
        probs /= total

        return int(np.random.choice(len(probs), p=probs))

    # ─── Generation ───────────────────────────────────────────────────────

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
                 deadline: Optional[float] = None,
                 ) -> Dict[str, Any]:
        """Generate tokens until battery depleted or max reached.

        Same interface as RWKVBatteryEngine.generate().

        Uses persistent FP16 swap: dequants as many layers as VRAM allows
        at start, runs generation with pure cuBLAS matmuls, restores after.
        """
        import sys as _sys2
        # Persistent FP16 swap: swap once on first call, keep for all subsequent
        if not getattr(self, '_fp16_swapped', False):
            try:
                n_swapped = self._swap_layers_to_fp16()
                self._fp16_swapped = True
            except Exception as e:
                import traceback
                traceback.print_exc(file=_sys2.stderr)
                print(f"[RWKVGPUEngine] FP16 swap failed: {e}, running without swap",
                      file=_sys2.stderr, flush=True)
                self._restore_from_fp16()

        return self._generate_inner(
            prompt_tokens, max_tokens, temperature, top_k, top_p,
            repetition_penalty, presence_penalty, frequency_penalty,
            somatic, stop_tokens, gravity_stride, deadline,
        )

    def _generate_inner(self, prompt_tokens: List[int],
                        max_tokens: int, temperature: float,
                        top_k: int, top_p: float,
                        repetition_penalty: float,
                        presence_penalty: float,
                        frequency_penalty: float,
                        somatic: Optional[SomaticStateNP],
                        stop_tokens: Optional[List[int]],
                        gravity_stride: int,
                        deadline: Optional[float] = None,
                        ) -> Dict[str, Any]:
        """Inner generate loop (called with FP16 swap active)."""
        _deadline_hit = False
        generated_tokens = []
        token_counts: Dict[int, int] = {}
        total_flops = 0
        charge_start = self.compute.charge_level
        stop_tokens = stop_tokens or []

        # Process prompt tokens (stride=1 for full quality state)
        # All but last: skip_head=True (saves ~10% FLOPS — no logits needed)
        # Last token: skip_head=False (we need logits for sampling)
        # skip_diagnostics=True — eliminates 96 GPU sync stalls per token
        result = None
        n_prompt = len(prompt_tokens)
        for idx, tok in enumerate(prompt_tokens):
            is_last = (idx == n_prompt - 1)
            result = self.forward_one_token(
                tok, somatic, skip_head=(not is_last), gravity_stride=1,
                skip_diagnostics=True,
            )
            if result["status"] == "low_power":
                return {
                    "tokens": generated_tokens,
                    "prompt_processed": False,
                    "total_flops": total_flops,
                    "charge_consumed": charge_start - self.compute.charge_level,
                    "status": "low_power",
                }
            total_flops += result.get("flops_used", 0)

        last_logits = result.get("logits") if result else None

        # 2026-09-12: `deadline` is a DURATION in seconds and the clock starts HERE, after
        # the prompt has been processed. The first version was an absolute time taken
        # before the FP16 swap + prompt: on a starved box the prompt alone ate the 75 s and
        # every generation returned 0 tokens ('hit the 75s deadline after 0 tokens' x5,
        # warmup FAILED, no speech for 3.5 h). The prompt phase is bounded by its length;
        # only the generation loop can run away.
        _gen_deadline = (time.time() + float(deadline)) if deadline else None
        # Generate new tokens
        for _ in range(max_tokens):
            if last_logits is None:
                break
            # 2026-09-11 (Nous+Ace): a degenerate loop never emits a stop token; at 1.25 tok/s
            # a 1024-token request ran ~14 min, the gate gave up at 90 s, and every later
            # request timed out behind it -- the farm was wedged for 20 min. Stop at the
            # wall-clock deadline and hand back what we have; the caller's degenerate
            # classifier then SEES the runaway and its valve can count it.
            if _gen_deadline is not None and time.time() > _gen_deadline:
                _deadline_hit = True
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
            token_counts[next_token] = token_counts.get(next_token, 0) + 1

            if next_token in stop_tokens:
                return {
                    "tokens": generated_tokens,
                    "prompt_processed": True,
                    "total_flops": total_flops,
                    "charge_consumed": charge_start - self.compute.charge_level,
                    "status": "stop_token",
                }

            result = self.forward_one_token(
                next_token, somatic, gravity_stride=gravity_stride,
                skip_diagnostics=True,
            )
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
            "status": ("max_reached" if len(generated_tokens) >= max_tokens
                       else "ok"),
            "gravity_stride": gravity_stride,
            "deadline_hit": _deadline_hit,
        }

    # ─── State Persistence ────────────────────────────────────────────────

    def save_state(self) -> dict:
        """Save all layer states (GPU → CPU numpy for serialization)."""
        return {
            "time_mix": [tm.get_state() for tm in self.time_mix_layers],
            "channel_mix": [cm.get_state() for cm in self.channel_mix_layers],
            "compute": self.compute.to_dict(),
        }

    def load_state(self, state_dict: dict):
        """Restore all layer states (CPU numpy → GPU tensors)."""
        for i, tm_state in enumerate(state_dict.get("time_mix", [])):
            if i < len(self.time_mix_layers):
                self.time_mix_layers[i].set_state(tm_state)
        for i, cm_state in enumerate(state_dict.get("channel_mix", [])):
            if i < len(self.channel_mix_layers):
                self.channel_mix_layers[i].set_state(cm_state)

    def save_state_to_disk(self, path: str):
        """Save state to .npz file (same format as NumPy engine)."""
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
        """Load state from .npz file (compatible with NumPy engine format)."""
        data = np.load(path)
        expected_dim = self.config.n_embd

        # Validate dimensions
        for i in range(min(self.config.n_layer, 3)):
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
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
        vram_used = torch.cuda.memory_allocated(0) / (1024 * 1024) if torch.cuda.is_available() else 0
        vram_total = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024) if torch.cuda.is_available() else 0

        return {
            "engine": "GPU (CUDA)",
            "gpu": gpu_name,
            "vram_used_mb": round(vram_used, 1),
            "vram_total_mb": round(vram_total, 1),
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


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE ALIAS — BatteryFarm.build() looks up engine_module.RWKVBatteryEngine
# ═══════════════════════════════════════════════════════════════════════════════

RWKVBatteryEngine = RWKVGPUBatteryEngine
