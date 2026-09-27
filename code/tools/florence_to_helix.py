#!/usr/bin/env python
"""
florence_to_helix.py — Convert Florence-2-large weights into a single binary
manifold file for zero-copy GPU loading via mmap.

Outputs: state/akashic/florence.manifold

Binary layout:
    HEADER        (4096 bytes)  — magic, version, counts, model name
    TENSOR INDEX  (304 bytes per tensor) — name, shape, quant params, offsets
    DATA SECTION  (page-aligned) — raw uint8 quantized tensor bytes

Usage:
    python tools/florence_to_helix.py              # Convert model
    python tools/florence_to_helix.py --verify     # Convert + verify 5 random tensors

Requires: torch, safetensors  (Python 3.12 w/ CUDA)
"""

import argparse
import json
import mmap
import os
import random
import struct
import sys
import time

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MODEL_PATH = (
    r"C:\Users\Ace\.cache\huggingface\hub\models--microsoft--Florence-2-large"
    r"\snapshots\21a599d414c4d928c9032694c424fb94458e3594\model.safetensors"
)

MANIFOLD_PATH = (
    r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\florence.manifold"
)

INDEX_PATH = (
    r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\akashic.index"
)

# ---------------------------------------------------------------------------
# Binary format constants
# ---------------------------------------------------------------------------
HEADER_SIZE = 4096
MAGIC = b"FLRN"
VERSION = 1

# Tensor index entry: 304 bytes each
#   name:        256 bytes (null-padded UTF-8)
#   ndim:        uint32 LE
#   shape:       4x uint32 LE (16 bytes)
#   dtype_code:  uint32 LE (0=float16, 1=float32, 2=bfloat16)
#   scale:       float32 LE
#   zero_point:  float32 LE
#   data_offset: uint64 LE
#   data_size:   uint64 LE
# Total: 256 + 4 + 16 + 4 + 4 + 4 + 8 + 8 = 304
TENSOR_ENTRY_SIZE = 304
TENSOR_ENTRY_STRUCT = struct.Struct("<256s I 4I I f f Q Q")

# dtype mapping
DTYPE_MAP = {
    "torch.float16": 0,
    "torch.float32": 1,
    "torch.bfloat16": 2,
}
DTYPE_NAMES = {v: k for k, v in DTYPE_MAP.items()}


def _align_to_page(offset: int, page_size: int = 4096) -> int:
    """Round offset up to the next page boundary."""
    return (offset + page_size - 1) // page_size * page_size


# ---------------------------------------------------------------------------
# Int8 quantization (per-tensor min/max)
# ---------------------------------------------------------------------------
def quantize_tensor_uint8(tensor):
    """Quantize a float tensor to uint8 with per-tensor affine scaling.

    Returns (uint8_bytes, scale, zero_point, original_dtype_str).
    Dequantize: float_val = uint8_val * scale + zero_point
    Where: scale = (max - min) / 255, zero_point = min
    So: float_val = uint8_val * scale + min
    """
    import torch

    flat = tensor.detach().float().flatten()
    t_min = flat.min().item()
    t_max = flat.max().item()

    if t_max == t_min:
        # Constant tensor
        scale = 1.0
        zero_point = t_min
        int8_data = torch.zeros(flat.shape, dtype=torch.uint8)
    else:
        scale = (t_max - t_min) / 255.0
        zero_point = t_min
        int8_data = ((flat - t_min) / scale).round().clamp(0, 255).to(torch.uint8)

    return int8_data.numpy().tobytes(), scale, zero_point, str(tensor.dtype)


# ---------------------------------------------------------------------------
# Write the manifold file
# ---------------------------------------------------------------------------
def write_manifold(state_dict: dict, output_path: str) -> dict:
    """Write all tensors to a single binary manifold file.

    Returns stats dict.
    """
    sorted_names = sorted(state_dict.keys())
    num_tensors = len(sorted_names)

    # Phase 1: Quantize all tensors, collect metadata
    print(f"\n[2/5] Quantizing {num_tensors} tensors to uint8...")
    t0 = time.time()

    entries = []  # (name, shape, dtype_code, scale, zero_point, data_bytes)
    total_original_bytes = 0
    total_quantized_bytes = 0

    for i, name in enumerate(sorted_names):
        tensor = state_dict[name]
        total_original_bytes += tensor.nelement() * tensor.element_size()

        data_bytes, scale, zero_point, dtype_str = quantize_tensor_uint8(tensor)
        dtype_code = DTYPE_MAP.get(dtype_str, 1)  # default to float32

        shape = list(tensor.shape)
        # Pad shape to 4 dims
        while len(shape) < 4:
            shape.append(0)
        shape = shape[:4]  # Truncate if somehow > 4 dims

        entries.append({
            "name": name,
            "ndim": len(tensor.shape),
            "shape": shape,
            "dtype_code": dtype_code,
            "scale": scale,
            "zero_point": zero_point,
            "data_bytes": data_bytes,
        })
        total_quantized_bytes += len(data_bytes)

        if (i + 1) % 50 == 0 or (i + 1) == num_tensors:
            print(f"       [{i+1}/{num_tensors}] {name[:60]}... ({tensor.shape})")

    t_quant = time.time() - t0
    print(f"       Done in {t_quant:.1f}s")
    print(f"       Original:  {total_original_bytes / (1024**2):.1f} MB")
    print(f"       Quantized: {total_quantized_bytes / (1024**2):.1f} MB")

    # Phase 2: Compute offsets
    index_start = HEADER_SIZE
    index_size = num_tensors * TENSOR_ENTRY_SIZE
    data_start = _align_to_page(index_start + index_size)

    # Assign data offsets (relative to data_start)
    current_offset = 0
    for entry in entries:
        entry["data_offset"] = current_offset
        entry["data_size"] = len(entry["data_bytes"])
        current_offset += entry["data_size"]

    total_data_bytes = current_offset
    total_file_size = data_start + total_data_bytes

    # Phase 3: Write the file
    print(f"\n[3/5] Writing manifold: {output_path}")
    print(f"       Header:     {HEADER_SIZE} bytes")
    print(f"       Index:      {index_size} bytes ({num_tensors} entries x {TENSOR_ENTRY_SIZE})")
    print(f"       Data start: {data_start} (page-aligned)")
    print(f"       Data:       {total_data_bytes} bytes")
    print(f"       Total:      {total_file_size / (1024**2):.1f} MB")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    t0 = time.time()
    with open(output_path, "wb") as f:
        # --- HEADER (4096 bytes) ---
        header = bytearray(HEADER_SIZE)

        # Magic (4 bytes)
        header[0:4] = MAGIC
        # Version (4 bytes, uint32 LE)
        struct.pack_into("<I", header, 4, VERSION)
        # Num tensors (4 bytes, uint32 LE)
        struct.pack_into("<I", header, 8, num_tensors)
        # Total data bytes (8 bytes, uint64 LE)
        struct.pack_into("<Q", header, 12, total_data_bytes)
        # Model name (256 bytes, null-padded UTF-8)
        model_name = b"microsoft/Florence-2-large"
        header[20:20 + len(model_name)] = model_name

        f.write(header)

        # --- TENSOR INDEX ---
        for entry in entries:
            name_bytes = entry["name"].encode("utf-8")[:256]
            name_padded = name_bytes.ljust(256, b"\x00")

            packed = TENSOR_ENTRY_STRUCT.pack(
                name_padded,
                entry["ndim"],
                entry["shape"][0], entry["shape"][1],
                entry["shape"][2], entry["shape"][3],
                entry["dtype_code"],
                entry["scale"],
                entry["zero_point"],
                entry["data_offset"],
                entry["data_size"],
            )
            f.write(packed)

        # --- PADDING to page-align data section ---
        current_pos = HEADER_SIZE + index_size
        pad_bytes = data_start - current_pos
        if pad_bytes > 0:
            f.write(b"\x00" * pad_bytes)

        # --- DATA SECTION ---
        for entry in entries:
            f.write(entry["data_bytes"])

    t_write = time.time() - t0
    actual_size = os.path.getsize(output_path)
    print(f"       Written in {t_write:.1f}s — {actual_size / (1024**2):.1f} MB on disk")

    return {
        "num_tensors": num_tensors,
        "total_original_bytes": total_original_bytes,
        "total_quantized_bytes": total_quantized_bytes,
        "total_file_size": actual_size,
        "data_start": data_start,
        "t_quant": t_quant,
        "t_write": t_write,
    }


# ---------------------------------------------------------------------------
# Update akashic.index
# ---------------------------------------------------------------------------
def update_akashic_index(manifold_path: str, stats: dict):
    """Add a 'florence' entry to the akashic.index JSON file."""
    print(f"\n[4/5] Updating akashic.index...")

    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"magic": "AKASHIC_MANIFOLD", "version": 1, "regions": []}

    # Remove existing florence entry if present
    if "blobs" not in index:
        index["blobs"] = []

    index["blobs"] = [b for b in index["blobs"] if b.get("name") != "florence"]

    # Add new entry
    index["blobs"].append({
        "name": "florence",
        "type": "blob",
        "owner": "FlorenceHelixConverter",
        "path": os.path.basename(manifold_path),
        "format": "FLRN_v1",
        "gpu_mirror": True,
        "num_tensors": stats["num_tensors"],
        "original_bytes": stats["total_original_bytes"],
        "quantized_bytes": stats["total_quantized_bytes"],
        "file_size": stats["total_file_size"],
        "data_offset": stats["data_start"],
        "model": "microsoft/Florence-2-large",
        "quantization": "uint8_affine",
        "created": time.time(),
    })

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"       Added 'florence' blob entry to {INDEX_PATH}")


# ---------------------------------------------------------------------------
# Verification via mmap
# ---------------------------------------------------------------------------
def run_verification(manifold_path: str, state_dict=None, num_samples: int = 5):
    """Pick random tensors, mmap-read from manifold, dequantize, compare."""
    import numpy as np

    print(f"\n{'=' * 70}")
    print(f"VERIFICATION (mmap zero-copy read)")
    print(f"{'=' * 70}")

    if not os.path.exists(manifold_path):
        print(f"  [ERROR] Manifold not found: {manifold_path}")
        return False

    # Read header
    with open(manifold_path, "rb") as f:
        raw_header = f.read(HEADER_SIZE)

    magic = raw_header[0:4]
    if magic != MAGIC:
        print(f"  [ERROR] Bad magic: {magic!r} (expected {MAGIC!r})")
        return False

    version = struct.unpack_from("<I", raw_header, 4)[0]
    num_tensors = struct.unpack_from("<I", raw_header, 8)[0]
    total_data = struct.unpack_from("<Q", raw_header, 12)[0]
    model_name = raw_header[20:276].split(b"\x00", 1)[0].decode("utf-8")

    print(f"  Magic:       {magic}")
    print(f"  Version:     {version}")
    print(f"  Tensors:     {num_tensors}")
    print(f"  Data bytes:  {total_data:,}")
    print(f"  Model:       {model_name}")

    # Read tensor index
    index_start = HEADER_SIZE
    index_size = num_tensors * TENSOR_ENTRY_SIZE
    data_start = _align_to_page(index_start + index_size)

    file_size = os.path.getsize(manifold_path)

    # mmap the entire file for zero-copy reads
    with open(manifold_path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

        # Parse index entries
        tensor_entries = []
        for i in range(num_tensors):
            offset = index_start + i * TENSOR_ENTRY_SIZE
            unpacked = TENSOR_ENTRY_STRUCT.unpack_from(mm, offset)

            name = unpacked[0].split(b"\x00", 1)[0].decode("utf-8")
            ndim = unpacked[1]
            shape = list(unpacked[2:6])[:ndim]  # Only take ndim dimensions
            dtype_code = unpacked[6]
            scale = unpacked[7]
            zero_point = unpacked[8]
            data_offset = unpacked[9]
            data_size = unpacked[10]

            tensor_entries.append({
                "name": name,
                "ndim": ndim,
                "shape": shape,
                "dtype_code": dtype_code,
                "scale": scale,
                "zero_point": zero_point,
                "data_offset": data_offset,
                "data_size": data_size,
            })

        # Pick random tensors to verify
        sample_indices = random.sample(range(num_tensors), min(num_samples, num_tensors))

        # Load original if needed
        if state_dict is None:
            print(f"\n  Loading original model for comparison...")
            from safetensors.torch import load_file
            state_dict = load_file(MODEL_PATH)

        print(f"\n  Verifying {len(sample_indices)} random tensors:")
        print(f"  {'Parameter':<55} {'Shape':<18} {'Max Err':>10} {'Scale':>10}")
        print(f"  {'-'*55} {'-'*18} {'-'*10} {'-'*10}")

        all_pass = True
        for idx in sample_indices:
            entry = tensor_entries[idx]
            name = entry["name"]

            # Read uint8 data from mmap (zero-copy!)
            abs_offset = data_start + entry["data_offset"]
            raw_data = mm[abs_offset:abs_offset + entry["data_size"]]
            uint8_arr = np.frombuffer(raw_data, dtype=np.uint8)

            # Dequantize: float_val = uint8_val * scale + zero_point (which is min)
            reconstructed = uint8_arr.astype(np.float32) * entry["scale"] + entry["zero_point"]

            # Compare to original
            if name in state_dict:
                import torch
                original = state_dict[name].detach().float().flatten().numpy()
                abs_err = np.abs(original - reconstructed)
                max_err = abs_err.max()

                expected_max = entry["scale"] / 2.0
                status = "OK" if max_err <= expected_max * 1.1 else "WARN"
                if status == "WARN":
                    all_pass = False

                short = name if len(name) <= 55 else "..." + name[-52:]
                shape_str = str(entry["shape"])
                print(f"  {short:<55} {shape_str:<18} {max_err:>10.6f} {entry['scale']:>10.6f}  {status}")
            else:
                print(f"  {name:<55} NOT IN ORIGINAL")
                all_pass = False

        mm.close()

    verdict = "PASS" if all_pass else "WARN"
    print(f"\n  VERDICT: {verdict}")
    print(f"{'=' * 70}")
    return all_pass


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------
def convert(verify: bool = False):
    from safetensors.torch import load_file

    print("=" * 70)
    print("FLORENCE-2-LARGE -> BINARY MANIFOLD CONVERSION")
    print("=" * 70)

    # 1. Load model
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Model not found at:\n  {MODEL_PATH}")
        sys.exit(1)

    original_file_size = os.path.getsize(MODEL_PATH)
    print(f"\n[1/5] Loading safetensors: {MODEL_PATH}")
    print(f"       File size: {original_file_size / (1024**3):.2f} GB")

    t_start = time.time()
    state_dict = load_file(MODEL_PATH)
    t_load = time.time() - t_start
    print(f"       Loaded {len(state_dict)} parameters in {t_load:.1f}s")

    # 2-3. Quantize + write manifold
    stats = write_manifold(state_dict, MANIFOLD_PATH)

    # 4. Update akashic.index
    update_akashic_index(MANIFOLD_PATH, stats)

    # 5. Summary
    t_total = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"CONVERSION COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Model:            microsoft/Florence-2-large")
    print(f"  Parameters:       {stats['num_tensors']}")
    print(f"  Safetensors:      {original_file_size / (1024**3):.2f} GB")
    print(f"  Original (fp):    {stats['total_original_bytes'] / (1024**2):.1f} MB")
    print(f"  Quantized (uint8):{stats['total_quantized_bytes'] / (1024**2):.1f} MB")
    print(f"  File on disk:     {stats['total_file_size'] / (1024**2):.1f} MB")
    print(f"  Compression:      {original_file_size / stats['total_file_size']:.1f}x vs safetensors")
    print(f"  Output:           {MANIFOLD_PATH}")
    print(f"  Format:           FLRN v{VERSION} (mmap-ready, zero-copy GPU load)")
    print(f"  Time:             {t_load:.1f}s load + {stats['t_quant']:.1f}s quant + "
          f"{stats['t_write']:.1f}s write = {t_total:.1f}s total")
    print(f"{'=' * 70}")

    # Optional verification
    if verify:
        run_verification(MANIFOLD_PATH, state_dict, num_samples=5)

    del state_dict


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Convert Florence-2-large weights to binary manifold file"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="After conversion, verify 5 random tensors via mmap read"
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Skip conversion, just verify existing manifold"
    )
    args = parser.parse_args()

    if args.verify_only:
        run_verification(MANIFOLD_PATH)
    else:
        convert(verify=args.verify)


if __name__ == "__main__":
    main()
