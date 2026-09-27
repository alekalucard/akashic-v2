"""
QuantizedWeightStore — INT8 weight storage with on-demand tile dequantization.

Stores RWKV-7 model weights in INT8 format with per-group scale factors.
Dequantizes tiles on demand — never materializes the full FP32 matrix.
This keeps memory usage low while feeding the TiledMatVec engine.

Memory savings (RWKV-7 1.5B):
    FP32: ~5.6GB
    FP16: ~2.8GB
    INT8: ~1.5GB  ← our target
    INT4: ~0.75GB (future)

Quantization method:
    Symmetric INT8 with per-group scales.
    Group size = 64 (matches TileConfig.tile_k for alignment).
    Each group: scale = max(abs(group)) / 127
    Quantized = round(original / scale)
    Dequantized = quantized * scale

    Max quantization error: 1/254 * max(abs(group)) ≈ 0.4%
    In practice, perplexity increase is < 0.5 for INT8 on RWKV models.

Created: 2026-02-20
Authors: Nous + Ace
"""

import numpy as np
import json
import struct
import mmap
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union


# ═══════════════════════════════════════════════════════════════════════════════
# PORTAL FILE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

PORTAL_MAGIC = b'PRWK'   # Portal RWKV Weights
PORTAL_VERSION = 1
PORTAL_PAGE = 4096        # OS page size — mmap granularity


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTIZATION CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QuantizationConfig:
    """Quantization parameters.

    group_size should match TileConfig.tile_k for optimal cache alignment.
    """
    bits: int = 8               # 8 for INT8, 4 for INT4 (future)
    group_size: int = 64        # Elements per quantization group
    symmetric: bool = True      # Symmetric: no zero-point, just scale
    compute_dtype: np.dtype = field(default_factory=lambda: np.dtype(np.float32))

    @property
    def storage_dtype(self) -> np.dtype:
        if self.bits == 8:
            return np.dtype(np.int8)
        elif self.bits == 4:
            # INT4 stored as uint8 (2 values per byte)
            return np.dtype(np.uint8)
        return np.dtype(np.int8)

    @property
    def max_val(self) -> int:
        """Maximum quantized value."""
        return (1 << (self.bits - 1)) - 1  # 127 for INT8, 7 for INT4


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTIZED TENSOR
# ═══════════════════════════════════════════════════════════════════════════════

class QuantizedTensor:
    """A single weight matrix stored in quantized format.

    Storage layout:
        data:   [M, K] int8     — quantized values
        scales: [M, n_groups] float32 — one scale per group of columns
        shape:  (M, K)          — original shape

    For [2048, 2048] with group_size=64:
        data:   2048 * 2048 * 1 byte  = 4MB
        scales: 2048 * 32 * 4 bytes   = 256KB
        Total: ~4.25MB vs 16MB (float32) or 8MB (float16)
    """

    __slots__ = ('data', 'scales', 'shape', 'group_size', 'bits')

    def __init__(self, data: np.ndarray, scales: np.ndarray,
                 shape: Tuple[int, int], group_size: int, bits: int = 8):
        self.data = data
        self.scales = scales
        self.shape = shape
        self.group_size = group_size
        self.bits = bits  # 8 = INT8 (int8), 4 = INT4 (packed uint8)

    @classmethod
    def from_float(cls, tensor: np.ndarray,
                   config: QuantizationConfig) -> "QuantizedTensor":
        """Quantize a float32/float16 tensor to INT8 or INT4.

        Symmetric quantization per group:
            INT8: scale = max(abs(group)) / 127, range [-127, 127]
            INT4: scale = max(abs(group)) / 7,   range [-7, 7]

        INT4 packing: 2 signed values per uint8 byte.
            Storage: byte = ((val_hi + 8) << 4) | (val_lo + 8)
            Unpack:  val_hi = (byte >> 4) - 8,  val_lo = (byte & 0xF) - 8
            This maps signed [-7,7] to unsigned [1,15], with 0→8 and -7→1.
        """
        if tensor.ndim == 1:
            tensor = tensor.reshape(1, -1)

        M, K = tensor.shape
        gs = config.group_size
        max_val = config.max_val
        bits = config.bits

        # Pad K to multiple of group_size if needed
        if K % gs != 0:
            pad_k = gs - (K % gs)
            tensor = np.pad(tensor, ((0, 0), (0, pad_k)), mode='constant')
            K_padded = K + pad_k
        else:
            K_padded = K

        # For INT4, K_padded must also be even (2 values per byte)
        if bits == 4 and K_padded % 2 != 0:
            tensor = np.pad(tensor, ((0, 0), (0, 1)), mode='constant')
            K_padded += 1

        n_groups = K_padded // gs

        # Reshape for group-wise quantization: [M, n_groups, group_size]
        tensor_grouped = tensor[:, :K_padded].reshape(M, n_groups, gs)

        # Compute per-group scales
        absmax = np.abs(tensor_grouped).max(axis=2)  # [M, n_groups]
        scales = absmax / max_val
        # Avoid division by zero
        scales = np.where(scales == 0, 1.0, scales).astype(np.float32)

        # Quantize
        scales_expanded = scales[:, :, np.newaxis]  # [M, n_groups, 1]
        quantized = np.round(tensor_grouped / scales_expanded).clip(-max_val, max_val)

        if bits == 4:
            # ── INT4 packing: 2 values per uint8 byte ──
            # Flatten quantized values
            quantized = quantized.reshape(M, K_padded).astype(np.int8)
            # Pack pairs: val_hi in high nibble, val_lo in low nibble
            # Offset by 8 to make unsigned: signed [-7,7] → unsigned [1,15]
            hi = (quantized[:, 0::2].astype(np.int16) + 8).astype(np.uint8)
            lo = (quantized[:, 1::2].astype(np.int16) + 8).astype(np.uint8)
            packed = (hi << 4) | lo  # [M, K_padded // 2] uint8
            data = packed
        else:
            # ── INT8: direct storage ──
            quantized = quantized.astype(np.int8)
            data = quantized.reshape(M, K_padded)

        return cls(
            data=data,
            scales=scales,
            shape=(M, K),  # Original shape (before padding)
            group_size=gs,
            bits=bits,
        )

    def unpack_int4(self, packed: np.ndarray) -> np.ndarray:
        """Unpack INT4 packed uint8 data to int8 values.

        Each uint8 byte contains 2 signed INT4 values:
            hi = (byte >> 4) - 8    (high nibble, signed)
            lo = (byte & 0xF) - 8   (low nibble, signed)

        Returns int8 array with 2x the columns of input.
        """
        hi = (packed.astype(np.int16) >> 4).astype(np.int8) - 8
        lo = (packed.astype(np.int16) & 0x0F).astype(np.int8) - 8
        # Interleave: [M, K_packed] → [M, K_packed*2]
        M = packed.shape[0]
        K_packed = packed.shape[1]
        result = np.empty((M, K_packed * 2), dtype=np.int8)
        result[:, 0::2] = hi
        result[:, 1::2] = lo
        return result

    def dequantize_full(self) -> np.ndarray:
        """Dequantize the entire tensor to float32.

        WARNING: This materializes the full matrix. Only use for testing.
        For production, use dequantize_tile() or dequantize_rows().
        """
        M, K = self.shape

        if self.bits == 4:
            # Unpack INT4 → int8 first
            unpacked = self.unpack_int4(self.data)
            K_padded = unpacked.shape[1]
            n_groups = K_padded // self.group_size
            data_grouped = unpacked.reshape(M, n_groups, self.group_size)
        else:
            K_padded = self.data.shape[1]
            n_groups = K_padded // self.group_size
            data_grouped = self.data.reshape(M, n_groups, self.group_size)

        scales_expanded = self.scales[:, :, np.newaxis]  # [M, n_groups, 1]

        # Dequantize
        result = data_grouped.astype(np.float32) * scales_expanded
        result = result.reshape(M, K_padded)

        # Trim padding
        return result[:, :K]

    def dequantize_rows(self, row_start: int, row_end: int) -> np.ndarray:
        """Dequantize specific rows to float32.

        For matvec y = A @ x, we process A row-by-row in tiles.
        This only materializes the rows needed for the current tile.

        Memory: (row_end - row_start) * K * 4 bytes
        For a 64-row tile of [2048, 2048]: 64 * 2048 * 4 = 512KB
        """
        M, K = self.shape
        n_rows = row_end - row_start
        row_scales = self.scales[row_start:row_end]

        if self.bits == 4:
            row_data = self.data[row_start:row_end]
            unpacked = self.unpack_int4(row_data)
            K_padded = unpacked.shape[1]
            n_groups = K_padded // self.group_size
            data_grouped = unpacked.reshape(n_rows, n_groups, self.group_size)
        else:
            K_padded = self.data.shape[1]
            n_groups = K_padded // self.group_size
            row_data = self.data[row_start:row_end]
            data_grouped = row_data.reshape(n_rows, n_groups, self.group_size)

        scales_expanded = row_scales[:, :, np.newaxis]

        result = data_grouped.astype(np.float32) * scales_expanded
        result = result.reshape(n_rows, K_padded)
        return result[:, :K]

    def dequantize_tile(self, row_start: int, row_end: int,
                        col_start: int, col_end: int) -> np.ndarray:
        """Dequantize a specific tile to float32.

        THE KEY INNOVATION: Only materializes the exact tile needed.
        For a 64x64 tile: 4096 int8 → 16KB float32 (fits L1 cache!)

        The tile boundaries are snapped to group boundaries for the
        column dimension to ensure correct scale lookup.
        """
        if self.bits == 4:
            # For INT4, unpack rows first then slice columns
            rows = self.dequantize_rows(row_start, row_end)
            return rows[:, col_start:col_end]

        M, K = self.shape
        gs = self.group_size

        # Snap column range to group boundaries
        g_start = col_start // gs
        g_end = (col_end - 1) // gs + 1
        col_start_aligned = g_start * gs
        col_end_aligned = min(g_end * gs, self.data.shape[1])

        # Extract tile data and scales
        tile_data = self.data[row_start:row_end, col_start_aligned:col_end_aligned]
        tile_scales = self.scales[row_start:row_end, g_start:g_end]

        n_rows = row_end - row_start
        n_groups_tile = g_end - g_start

        # Dequantize
        data_grouped = tile_data.reshape(n_rows, n_groups_tile, gs)
        scales_expanded = tile_scales[:, :, np.newaxis]
        result = data_grouped.astype(np.float32) * scales_expanded
        result = result.reshape(n_rows, -1)

        # Extract the exact requested column range from the aligned result
        offset = col_start - col_start_aligned
        width = col_end - col_start
        return result[:, offset:offset + width]

    def memory_bytes(self) -> int:
        """Total memory usage in bytes."""
        return self.data.nbytes + self.scales.nbytes

    def to_dict(self) -> dict:
        """Serialize metadata (not data — that goes to .npz)."""
        return {
            "shape": list(self.shape),
            "group_size": self.group_size,
            "dtype": str(self.data.dtype),
            "bits": self.bits,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTIZED WEIGHT STORE
# ═══════════════════════════════════════════════════════════════════════════════

class QuantizedWeightStore:
    """Weight storage for an entire RWKV model in quantized format.

    Organization mirrors RWKV-7 weight layout:
        emb.weight:                    [vocab_size, n_embd]
        blocks.{i}.ln1.weight/bias:    [n_embd]
        blocks.{i}.ln2.weight/bias:    [n_embd]
        blocks.{i}.att.receptance.weight: [n_embd, n_embd]
        blocks.{i}.att.key.weight:     [n_embd, n_embd]
        blocks.{i}.att.value.weight:   [n_embd, n_embd]
        blocks.{i}.att.output.weight:  [n_embd, n_embd]
        blocks.{i}.att.gate.*:         LoRA weights (small)
        blocks.{i}.ffn.key.weight:     [n_embd, ffn_dim]
        blocks.{i}.ffn.value.weight:   [ffn_dim, n_embd]
        head.weight:                   [vocab_size, n_embd]

    Rules:
        - Large matrices (any dim >= 1024): QUANTIZED as INT8
        - Small tensors (norms, biases, LoRA, misc): FLOAT32 as-is
        - Embedding table: QUANTIZED (it's huge but only used for lookup)
    """

    QUANTIZE_THRESHOLD = 1024  # Minimum dimension to trigger quantization

    def __init__(self, config: Optional[QuantizationConfig] = None):
        self.config = config or QuantizationConfig()
        self._quantized: Dict[str, QuantizedTensor] = {}
        self._float_tensors: Dict[str, np.ndarray] = {}
        self._metadata: Dict[str, dict] = {}

    # ─── Loading ──────────────────────────────────────────────────────────

    def add_tensor(self, name: str, tensor: np.ndarray):
        """Add a tensor, quantizing if large enough.

        Args:
            name: Weight name (e.g., "blocks.0.att.receptance.weight")
            tensor: Float32 or float16 numpy array
        """
        # Convert float16 to float32 for quantization
        if tensor.dtype == np.float16:
            tensor = tensor.astype(np.float32)

        should_quantize = (
            tensor.ndim >= 2 and
            max(tensor.shape) >= self.QUANTIZE_THRESHOLD
        )

        if should_quantize:
            self._quantized[name] = QuantizedTensor.from_float(tensor, self.config)
        else:
            self._float_tensors[name] = tensor.astype(np.float32)

    @classmethod
    def from_state_dict(cls, state_dict: Dict[str, np.ndarray],
                        config: Optional[QuantizationConfig] = None) -> "QuantizedWeightStore":
        """Create from a dict of numpy arrays (e.g., loaded from safetensors).

        Args:
            state_dict: {name: ndarray} mapping
            config: Quantization config
        """
        store = cls(config)
        for name, tensor in state_dict.items():
            store.add_tensor(name, tensor)
        return store

    @classmethod
    def from_safetensors(cls, path: str,
                         config: Optional[QuantizationConfig] = None) -> "QuantizedWeightStore":
        """Load from safetensors file, quantizing on load.

        Requires the 'safetensors' package.
        """
        try:
            from safetensors.numpy import load_file
        except ImportError:
            raise ImportError("safetensors package required: pip install safetensors")

        tensors = load_file(path)
        return cls.from_state_dict(tensors, config)

    # GGUF tensor name → RWKV engine name mapping
    _GGUF_NAME_MAP = {
        # Global tensors
        "token_embd.weight":     "emb.weight",
        "token_embd_norm.weight": "blocks.0.ln0.weight",
        "token_embd_norm.bias":   "blocks.0.ln0.bias",
        "output.weight":         "head.weight",
        "output_norm.weight":    "ln_out.weight",
        "output_norm.bias":      "ln_out.bias",
    }

    # Per-block GGUF pattern → RWKV pattern (N = layer index)
    _GGUF_BLOCK_MAP = {
        # LayerNorms
        "attn_norm.weight":       "ln1.weight",
        "attn_norm.bias":         "ln1.bias",
        "attn_norm_2.weight":     "ln2.weight",
        "attn_norm_2.bias":       "ln2.bias",
        # TimeMix projections
        "time_mix_receptance.weight": "att.receptance.weight",
        "time_mix_key.weight":        "att.key.weight",
        "time_mix_value.weight":      "att.value.weight",
        "time_mix_output.weight":     "att.output.weight",
        # TimeMix LoRA + params
        "time_mix_lerp_fused.weight": "att.x_maa",
        "time_mix_w0.weight":     "att.w0",
        "time_mix_w1.weight":     "att.w1",
        "time_mix_w2.weight":     "att.w2",
        "time_mix_a0.weight":     "att.a0",
        "time_mix_a1.weight":     "att.a1",
        "time_mix_a2.weight":     "att.a2",
        "time_mix_v0.weight":     "att.v0",
        "time_mix_v1.weight":     "att.v1",
        "time_mix_v2.weight":     "att.v2",
        "time_mix_g1.weight":     "att.g1",
        "time_mix_g2.weight":     "att.g2",
        "time_mix_k_k.weight":    "att.k_k",
        "time_mix_k_a.weight":    "att.k_a",
        "time_mix_r_k.weight":    "att.r_k",
        "time_mix_ln.weight":     "att.ln",
        "time_mix_ln.bias":       "att.ln_bias",
        # ChannelMix
        "channel_mix_key.weight":   "ffn.key.weight",
        "channel_mix_value.weight": "ffn.value.weight",
        "channel_mix_lerp_k.weight": "ffn.x_maa",
    }

    @classmethod
    def from_gguf(cls, path: str,
                  config: Optional[QuantizationConfig] = None,
                  progress_callback=None) -> "QuantizedWeightStore":
        """Load from GGUF file, dequantizing all tensors on load.

        Supports Q8_0, F16, F32 tensor types via the gguf package.
        Maps GGUF tensor names to RWKV-7 naming convention.

        Args:
            path: Path to .gguf file
            config: Quantization config (for re-quantizing into our format)
            progress_callback: Optional fn(current, total, name) for progress
        """
        try:
            from gguf import GGUFReader, dequantize
        except ImportError:
            raise ImportError("gguf package required: pip install gguf")

        import re

        reader = GGUFReader(path)
        store = cls(config)
        total = len(reader.tensors)

        # Extract model config from metadata for reference
        gguf_meta = {}
        for field_name in reader.fields:
            gguf_meta[field_name] = reader.fields[field_name]
        store._metadata["_gguf_source"] = str(path)
        store._metadata["_gguf_tensor_count"] = total

        mapped = 0
        skipped = 0

        for idx, tensor in enumerate(reader.tensors):
            gguf_name = tensor.name
            gguf_declared_shape = tuple(int(s) for s in tensor.shape)

            # Dequantize to float32 regardless of source type
            # gguf.dequantize() transposes 2D tensors:
            #   declared (2048, 65536) → deq returns (65536, 2048) ← CORRECT for large weights
            #   declared (2048, 96)    → deq returns (96, 2048)    ← WRONG for LoRA (need (2048, 96))
            # Strategy: accept deq output as-is for large weights, transpose LoRA-sized ones
            data = dequantize(tensor.data, tensor.tensor_type)
            data = data.astype(np.float32)

            # Handle multi-dimensional tensors (4D fused lerp etc)
            if data.ndim >= 3 or len(gguf_declared_shape) >= 3:
                # 4D fused lerp: declared (2048, 1, 1, 6), deq returns (6, 1, 1, 2048)
                # Reshape to declared shape, then squeeze
                target = tuple(gguf_declared_shape)
                if data.shape != target:
                    try:
                        data = data.reshape(target)
                    except ValueError:
                        data = data.transpose(list(range(data.ndim - 1, -1, -1)))
                        if data.shape != target:
                            data = data.reshape(target)
                data = data.squeeze()  # (2048, 1, 1, 6) → (2048, 6)
            # For 2D tensors, accept dequantize output as-is.
            # dequantize returns (out_dim, in_dim) convention for RWKV:
            #   emb.weight: (65536, 2048) = (vocab, C) ← correct for lookup
            #   att.key:    (2048, 2048)  ← correct for matvec y = W @ x
            #   w1 (LoRA):  (96, 2048)   = (d_lora, C) ← correct for w1 @ x
            #   g1 (gate):  (256, 2048)  = (d_gate, C) ← correct for g1 @ x

            # Map GGUF name to RWKV name
            rwkv_name = None

            # Check global map first
            if gguf_name in cls._GGUF_NAME_MAP:
                rwkv_name = cls._GGUF_NAME_MAP[gguf_name]
            else:
                # Try block pattern: blk.N.suffix → blocks.N.mapped_suffix
                m = re.match(r'^blk\.(\d+)\.(.+)$', gguf_name)
                if m:
                    layer_idx = m.group(1)
                    suffix = m.group(2)
                    if suffix in cls._GGUF_BLOCK_MAP:
                        rwkv_name = f"blocks.{layer_idx}.{cls._GGUF_BLOCK_MAP[suffix]}"

            if rwkv_name is None:
                skipped += 1
                continue

            store.add_tensor(rwkv_name, data)
            mapped += 1

            if progress_callback and idx % 50 == 0:
                progress_callback(idx, total, rwkv_name)

        store._metadata["_gguf_mapped"] = mapped
        store._metadata["_gguf_skipped"] = skipped

        return store

    @classmethod
    def from_gguf_config(cls, path: str) -> dict:
        """Extract model configuration from GGUF metadata without loading weights.

        Returns dict with n_layer, n_embd, n_head, head_size, vocab_size.
        """
        try:
            from gguf import GGUFReader
        except ImportError:
            raise ImportError("gguf package required: pip install gguf")

        reader = GGUFReader(path)

        def _get_meta_int(key):
            if key in reader.fields:
                f = reader.fields[key]
                if len(f.data) > 0:
                    val = f.parts[f.data[0]]
                    return int(val) if hasattr(val, '__int__') else None
            return None

        # Try rwkv7.* keys first, then generic
        n_layer = _get_meta_int("rwkv7.block_count")
        n_embd = _get_meta_int("rwkv7.embedding_length")
        head_size = _get_meta_int("rwkv7.wkv.head_size") or 64
        vocab_size = _get_meta_int("rwkv7.vocab_size") or 65536
        # head_count is often 0 in GGUF files — derive from n_embd / head_size
        n_head = _get_meta_int("rwkv7.attention.head_count")
        if not n_head and n_embd and head_size:
            n_head = n_embd // head_size
        d_decay_lora = _get_meta_int("rwkv7.attention.decay_lora_rank") or 64
        d_aaa_lora = _get_meta_int("rwkv7.attention.iclr_lora_rank") or 64
        d_mv_lora = _get_meta_int("rwkv7.attention.value_residual_mix_lora_rank") or 32
        d_gate_lora = _get_meta_int("rwkv7.attention.gate_lora_rank") or 128

        return {
            "n_layer": n_layer,
            "n_embd": n_embd,
            "n_head": n_head,
            "head_size": head_size,
            "vocab_size": vocab_size,
            "d_decay_lora": d_decay_lora,
            "d_aaa_lora": d_aaa_lora,
            "d_mv_lora": d_mv_lora,
            "d_gate_lora": d_gate_lora,
        }

    # ─── Access ───────────────────────────────────────────────────────────

    def get_tensor(self, name: str) -> Union[np.ndarray, QuantizedTensor]:
        """Get a tensor by name.

        Returns:
            QuantizedTensor for large quantized weights
            np.ndarray for small float tensors
        """
        if name in self._quantized:
            return self._quantized[name]
        if name in self._float_tensors:
            return self._float_tensors[name]
        raise KeyError(f"Tensor not found: {name}")

    def get_float(self, name: str) -> np.ndarray:
        """Get a tensor as float32 (dequantizing if needed)."""
        if name in self._float_tensors:
            return self._float_tensors[name]
        if name in self._quantized:
            return self._quantized[name].dequantize_full()
        raise KeyError(f"Tensor not found: {name}")

    def get_rows(self, name: str, row_start: int, row_end: int) -> np.ndarray:
        """Get specific rows as float32 (dequantizing tile if quantized)."""
        if name in self._float_tensors:
            return self._float_tensors[name][row_start:row_end]
        if name in self._quantized:
            return self._quantized[name].dequantize_rows(row_start, row_end)
        raise KeyError(f"Tensor not found: {name}")

    def has_tensor(self, name: str) -> bool:
        return name in self._quantized or name in self._float_tensors

    @property
    def tensor_names(self) -> List[str]:
        return sorted(set(list(self._quantized.keys()) + list(self._float_tensors.keys())))

    # ─── Persistence ──────────────────────────────────────────────────────

    def save(self, directory: str):
        """Save quantized store to disk for fast reload.

        Creates:
            {directory}/metadata.json     — tensor names, shapes, quantization info
            {directory}/quantized.npz     — INT8 data + scales
            {directory}/float_tensors.npz — small float tensors
        """
        dirpath = Path(directory)
        dirpath.mkdir(parents=True, exist_ok=True)

        # Metadata
        meta = {
            "config": {
                "bits": self.config.bits,
                "group_size": self.config.group_size,
                "symmetric": self.config.symmetric,
            },
            "quantized_tensors": {},
            "float_tensors": {},
        }

        # Save quantized tensors
        q_arrays = {}
        for name, qt in self._quantized.items():
            meta["quantized_tensors"][name] = qt.to_dict()
            q_arrays[f"{name}__data"] = qt.data
            q_arrays[f"{name}__scales"] = qt.scales

        if q_arrays:
            np.savez(str(dirpath / "quantized.npz"), **q_arrays)

        # Save float tensors
        f_arrays = {}
        for name, ft in self._float_tensors.items():
            meta["float_tensors"][name] = {
                "shape": list(ft.shape),
                "dtype": str(ft.dtype),
            }
            f_arrays[name] = ft

        if f_arrays:
            np.savez(str(dirpath / "float_tensors.npz"), **f_arrays)

        # Save metadata
        with open(str(dirpath / "metadata.json"), "w") as f:
            json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, directory: str) -> "QuantizedWeightStore":
        """Load pre-quantized store from disk (fast — no requantization)."""
        dirpath = Path(directory)

        with open(str(dirpath / "metadata.json"), "r") as f:
            meta = json.load(f)

        config = QuantizationConfig(
            bits=meta["config"]["bits"],
            group_size=meta["config"]["group_size"],
            symmetric=meta["config"]["symmetric"],
        )
        store = cls(config)

        # Load quantized tensors
        q_path = dirpath / "quantized.npz"
        if q_path.exists():
            q_data = np.load(str(q_path))
            for name, info in meta["quantized_tensors"].items():
                data = q_data[f"{name}__data"]
                scales = q_data[f"{name}__scales"]
                store._quantized[name] = QuantizedTensor(
                    data=data,
                    scales=scales,
                    shape=tuple(info["shape"]),
                    group_size=info["group_size"],
                )

        # Load float tensors
        f_path = dirpath / "float_tensors.npz"
        if f_path.exists():
            f_data = np.load(str(f_path))
            for name in meta["float_tensors"]:
                store._float_tensors[name] = f_data[name]

        return store

    # ─── Portal File (mmap-backed persistence) ──────────────────────────
    #
    # The .portal file IS the portal dimension. Model weights live on disk.
    # The OS pages in only the data being actively computed. Cold layers
    # stay on disk. The dimension is bigger on the inside.
    #
    # Layout:
    #   [4B] MAGIC = b'PRWK'
    #   [4B] VERSION = 1
    #   [4B] header_json_length
    #   [header bytes] JSON index (tensor names → offsets, shapes, types)
    #   [padding to next page boundary]
    #   [tensor data sections, each at recorded offset]
    #
    # All tensor data is written contiguously in C order.
    # np.frombuffer() on the mmap creates zero-copy views.
    # The OS pages in 4KB at a time — only hot data touches RAM.

    def save_portal_file(self, path: str):
        """Serialize weights to mmap-friendly portal file.

        After saving, use from_portal_file() to get an mmap-backed store.
        The .portal file IS the portal dimension on disk.

        First boot:  from_gguf() → save_portal_file() → switch to mmap
        Next boots:  from_portal_file() only — instant, near-zero RAM
        """
        # ── Phase 1: Build tensor list with placeholder offsets ──
        tensors_index = []

        for name in sorted(self._quantized.keys()):
            qt = self._quantized[name]
            tensors_index.append({
                "name": name,
                "type": "quantized",
                "bits": qt.bits,
                "data_dtype": str(qt.data.dtype),
                "data_offset": 0,     # placeholder
                "data_bytes": qt.data.nbytes,
                "data_shape": list(qt.data.shape),
                "scales_offset": 0,   # placeholder
                "scales_bytes": qt.scales.nbytes,
                "scales_shape": list(qt.scales.shape),
                "shape": list(qt.shape),
                "group_size": qt.group_size,
            })

        for name in sorted(self._float_tensors.keys()):
            ft = self._float_tensors[name]
            tensors_index.append({
                "name": name,
                "type": "float32",
                "data_offset": 0,     # placeholder
                "data_bytes": ft.nbytes,
                "data_shape": list(ft.shape),
            })

        # ── Phase 2: Estimate header size dynamically ──
        index = {
            "version": PORTAL_VERSION,
            "total_size": 0,
            "n_quantized": len(self._quantized),
            "n_float": len(self._float_tensors),
            "config": {
                "bits": self.config.bits,
                "group_size": self.config.group_size,
                "symmetric": self.config.symmetric,
            },
            "tensors": tensors_index,
        }
        est_json = json.dumps(index, separators=(',', ':')).encode('utf-8')
        # Add padding for offset digits that will grow (max 12 digits each)
        est_total = 12 + len(est_json) + 20 * len(tensors_index)
        # Round up to page boundary
        header_reserve = ((est_total + PORTAL_PAGE - 1) // PORTAL_PAGE) * PORTAL_PAGE

        # ── Phase 3: Compute real offsets starting after header ──
        data_offset = header_reserve
        for entry in tensors_index:
            # Page-align quantized tensors for optimal mmap access
            if entry["type"] == "quantized":
                if data_offset % PORTAL_PAGE:
                    data_offset += PORTAL_PAGE - (data_offset % PORTAL_PAGE)

            entry["data_offset"] = data_offset
            data_offset += entry["data_bytes"]

            if entry["type"] == "quantized":
                entry["scales_offset"] = data_offset
                data_offset += entry["scales_bytes"]

        total_size = data_offset
        index["total_size"] = total_size

        # ── Phase 4: Final serialize with real offsets ──
        header_json = json.dumps(index, separators=(',', ':')).encode('utf-8')
        if len(header_json) + 12 > header_reserve:
            raise ValueError(
                f"Portal header too large: {len(header_json) + 12} > {header_reserve}. "
                f"This should not happen — please report this bug."
            )

        # Write file
        with open(path, 'wb') as f:
            # Header: magic + version + json_length + json + padding
            f.write(PORTAL_MAGIC)
            f.write(struct.pack('<I', PORTAL_VERSION))
            f.write(struct.pack('<I', len(header_json)))
            f.write(header_json)
            written = 12 + len(header_json)
            f.write(b'\x00' * (header_reserve - written))

            # Tensor data sections
            for entry in tensors_index:
                name = entry["name"]
                target = entry["data_offset"]
                current = f.tell()
                if current < target:
                    f.write(b'\x00' * (target - current))

                if entry["type"] == "quantized":
                    qt = self._quantized[name]
                    f.write(qt.data.tobytes())
                    f.write(qt.scales.tobytes())
                else:
                    ft = self._float_tensors[name]
                    f.write(np.ascontiguousarray(ft).tobytes())

            # Pad to final size
            current = f.tell()
            if current < total_size:
                f.write(b'\x00' * (total_size - current))

    @classmethod
    def from_portal_file(cls, path: str,
                         config: Optional[QuantizationConfig] = None
                         ) -> "QuantizedWeightStore":
        """Load from portal file using mmap — near-zero physical RAM.

        The OS pages in data on demand. Only layers being actively
        computed touch real RAM. Cold pages stay on disk. Under memory
        pressure, the OS evicts clean mmap pages automatically.

        This IS the portal interior — the dimension is bigger on the inside.
        """
        f = open(path, 'rb')

        # Read header
        magic = f.read(4)
        if magic != PORTAL_MAGIC:
            f.close()
            raise ValueError(f"Not a portal file (magic={magic!r})")
        version = struct.unpack('<I', f.read(4))[0]
        if version != PORTAL_VERSION:
            f.close()
            raise ValueError(f"Unsupported portal version: {version}")
        header_len = struct.unpack('<I', f.read(4))[0]
        header_json = f.read(header_len)
        index = json.loads(header_json)

        # Restore config
        cfg_dict = index.get("config", {})
        if config is None:
            config = QuantizationConfig(
                bits=cfg_dict.get("bits", 8),
                group_size=cfg_dict.get("group_size", 64),
                symmetric=cfg_dict.get("symmetric", True),
            )

        store = cls(config)

        # Memory-map the entire file (READ-ONLY)
        # The OS pages in data on demand — only accessed pages in RAM
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

        # Keep references alive (prevents GC of mmap backing)
        store._portal_file = f
        store._portal_mmap = mm
        store._is_portal_backed = True

        # Create numpy views into the mmap for each tensor
        for entry in index["tensors"]:
            name = entry["name"]

            if entry["type"] == "quantized":
                data_shape = tuple(entry["data_shape"])
                scales_shape = tuple(entry["scales_shape"])
                tensor_bits = entry.get("bits", 8)
                data_dtype_str = entry.get("data_dtype", "int8")

                # Determine data dtype: INT4 uses uint8, INT8 uses int8
                if data_dtype_str == "uint8" or tensor_bits == 4:
                    data_dtype = np.uint8
                    data_count = entry["data_bytes"]
                else:
                    data_dtype = np.int8
                    data_count = entry["data_bytes"]

                # Zero-copy view into mmap — no heap allocation!
                data = np.frombuffer(
                    mm, dtype=data_dtype,
                    count=data_count,
                    offset=entry["data_offset"]
                ).reshape(data_shape)

                scales = np.frombuffer(
                    mm, dtype=np.float32,
                    count=entry["scales_bytes"] // 4,
                    offset=entry["scales_offset"]
                ).reshape(scales_shape)

                qt = QuantizedTensor(
                    data=data,
                    scales=scales,
                    shape=tuple(entry["shape"]),
                    group_size=entry["group_size"],
                    bits=tensor_bits,
                )
                store._quantized[name] = qt

            elif entry["type"] == "float32":
                data_shape = tuple(entry["data_shape"])
                ft = np.frombuffer(
                    mm, dtype=np.float32,
                    count=entry["data_bytes"] // 4,
                    offset=entry["data_offset"]
                ).reshape(data_shape)
                store._float_tensors[name] = ft

        return store

    def close_portal(self):
        """Close mmap and file handles when portal shuts down."""
        if hasattr(self, '_portal_mmap') and self._portal_mmap:
            try:
                self._portal_mmap.close()
            except Exception:
                pass
            self._portal_mmap = None
        if hasattr(self, '_portal_file') and self._portal_file:
            try:
                self._portal_file.close()
            except Exception:
                pass
            self._portal_file = None

    @property
    def is_portal_backed(self) -> bool:
        """True if weights live in mmap (portal file), not heap."""
        return getattr(self, '_is_portal_backed', False)

    # ─── Stats ────────────────────────────────────────────────────────────

    def memory_usage(self) -> Dict[str, int]:
        """Report memory usage by category."""
        q_data_bytes = sum(qt.data.nbytes for qt in self._quantized.values())
        q_scale_bytes = sum(qt.scales.nbytes for qt in self._quantized.values())
        f_bytes = sum(ft.nbytes for ft in self._float_tensors.values())
        total = q_data_bytes + q_scale_bytes + f_bytes

        result = {
            "quantized_data_bytes": q_data_bytes,
            "quantized_scales_bytes": q_scale_bytes,
            "float_tensors_bytes": f_bytes,
            "total_bytes": total,
            "total_mb": round(total / 1024 / 1024, 1),
            "n_quantized": len(self._quantized),
            "n_float": len(self._float_tensors),
            "savings_vs_fp32": round(1 - (q_data_bytes + q_scale_bytes) /
                                     max(1, sum(qt.shape[0] * qt.shape[1] * 4
                                                for qt in self._quantized.values())), 2),
        }

        if self.is_portal_backed:
            result["storage"] = "mmap (portal file — OS manages paging)"
            result["heap_bytes"] = 0   # Weights are NOT in Python heap
            result["virtual_bytes"] = total  # Mapped into address space
            result["note"] = "Only actively-computed pages in physical RAM"
        else:
            result["storage"] = "heap (numpy arrays in process memory)"
            result["heap_bytes"] = total

        return result

    def status(self) -> dict:
        """Store status for diagnostics."""
        mem = self.memory_usage()
        return {
            "config": {
                "bits": self.config.bits,
                "group_size": self.config.group_size,
            },
            "n_tensors": len(self._quantized) + len(self._float_tensors),
            "n_quantized": len(self._quantized),
            "n_float": len(self._float_tensors),
            "memory_mb": mem["total_mb"],
            "savings_vs_fp32": mem["savings_vs_fp32"],
        }
