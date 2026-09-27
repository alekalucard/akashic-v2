"""
Ingest LuxTTS (YatharthS/LuxTTS) -> Unified Audio Manifold + Coordinate Cards.

APPENDS to the EXISTING audio.manifold that already has Canary STT tensors.
Both models share ONE manifold file — unified gravity mass.

Run ONCE under Python 3.12 (needs torch installed):
    C:\\Users\\Ace\\AppData\\Local\\Programs\\Python\\Python312\\python.exe ingest_luxtts_to_audio_manifold.py

LuxTTS has two weight files:
  - model.pt['model']:  890 tensors (ZipVoiceDistill flow-matching)
  - vocoder/vocos.bin:  113 tensors (Vocos vocoder)
Both are namespaced as "luxtts/model/..." and "luxtts/vocos/..." in the manifold.

Coordinate cards (~50 bytes each) are written to luxtts_cards/cards.json.

2026-03-20, Nous + Ace — Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import struct
import hashlib
import argparse
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# Manifold format constants (same as ingest_canary_to_cards.py / florence_to_helix.py)
# ══════════════════════════════════════════════════════════════════════════════

HEADER_SIZE = 4096
MAGIC = b"AUDM"
VERSION = 1
TENSOR_ENTRY_SIZE = 304
TENSOR_ENTRY_STRUCT = struct.Struct("<256s I 4I I f f Q Q")

DTYPE_MAP = {
    "torch.float16": 0,
    "torch.float32": 1,
    "torch.bfloat16": 2,
}


def _align_to_page(offset: int, page_size: int = 4096) -> int:
    return (offset + page_size - 1) // page_size * page_size


def quantize_tensor_uint8(tensor):
    """Quantize float tensor to uint8 with per-tensor affine scaling."""
    import torch
    flat = tensor.detach().cpu().float().flatten()
    t_min = flat.min().item()
    t_max = flat.max().item()

    if t_max == t_min:
        scale = 1.0
        zero_point = t_min
        int8_data = torch.zeros(flat.shape, dtype=torch.uint8)
    else:
        scale = (t_max - t_min) / 255.0
        zero_point = t_min
        int8_data = ((flat - t_min) / scale).round().clamp(0, 255).to(torch.uint8)

    return int8_data.numpy().tobytes(), scale, zero_point, str(tensor.dtype)


# ══════════════════════════════════════════════════════════════════════════════
# Read existing manifold entries (for append mode)
# ══════════════════════════════════════════════════════════════════════════════

def read_existing_manifold(manifold_path: str) -> list:
    """Read existing tensor entries from a manifold file.

    Returns list of entry dicts (name, ndim, shape, dtype_code, scale,
    zero_point, data_bytes) for each tensor already in the manifold.
    """
    if not os.path.exists(manifold_path):
        return []

    entries = []
    with open(manifold_path, "rb") as f:
        header = f.read(HEADER_SIZE)
        magic = header[0:4]
        if magic != MAGIC:
            print(f"[ReadManifold] Bad magic: {magic}")
            return []

        num_tensors = struct.unpack_from("<I", header, 8)[0]
        data_start = struct.unpack_from("<Q", header, 32)[0]

        # Read tensor index
        index_entries = []
        for i in range(num_tensors):
            raw = f.read(TENSOR_ENTRY_SIZE)
            parsed = TENSOR_ENTRY_STRUCT.unpack(raw)
            index_entries.append({
                "name": parsed[0].rstrip(b"\x00").decode("utf-8"),
                "ndim": parsed[1],
                "shape": list(parsed[2:6]),
                "dtype_code": parsed[6],
                "scale": parsed[7],
                "zero_point": parsed[8],
                "data_offset": parsed[9],
                "data_size": parsed[10],
            })

        # Read data for each existing tensor
        for entry in index_entries:
            f.seek(data_start + entry["data_offset"])
            data = f.read(entry["data_size"])
            entries.append({
                "name": entry["name"],
                "ndim": entry["ndim"],
                "shape": entry["shape"],
                "dtype_code": entry["dtype_code"],
                "scale": entry["scale"],
                "zero_point": entry["zero_point"],
                "data_bytes": data,
            })

    print(f"[ReadManifold] Read {len(entries)} existing tensors from {manifold_path}")
    return entries


# ══════════════════════════════════════════════════════════════════════════════
# Write unified manifold (all entries: existing + new)
# ══════════════════════════════════════════════════════════════════════════════

def write_audio_manifold(all_entries: list, output_path: str) -> dict:
    """Write all tensor entries to the unified audio manifold.

    Args:
        all_entries: List of entry dicts (name, ndim, shape, dtype_code,
                     scale, zero_point, data_bytes)
        output_path: Path to audio.manifold

    Returns:
        Stats dict
    """
    num_total = len(all_entries)
    index_start = HEADER_SIZE
    index_size = num_total * TENSOR_ENTRY_SIZE
    data_start = _align_to_page(index_start + index_size)

    # Assign data offsets
    current_offset = 0
    for entry in all_entries:
        entry["data_offset"] = current_offset
        entry["data_size"] = len(entry["data_bytes"])
        current_offset += entry["data_size"]

    total_data_bytes = current_offset
    total_file_size = data_start + total_data_bytes

    # Count by prefix
    prefix_counts = {}
    for e in all_entries:
        prefix = e["name"].split("/")[0] if "/" in e["name"] else "unknown"
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

    print(f"\n[AudioManifold] Writing unified audio manifold: {output_path}")
    print(f"       Total tensors: {num_total}")
    for prefix, count in sorted(prefix_counts.items()):
        print(f"         {prefix}/: {count} tensors")
    print(f"       Total data:   {total_data_bytes / (1024**2):.1f} MB")
    print(f"       Total file:   {total_file_size / (1024**2):.1f} MB")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as f:
        # Header
        header = bytearray(HEADER_SIZE)
        header[0:4] = MAGIC
        struct.pack_into("<I", header, 4, VERSION)
        struct.pack_into("<I", header, 8, num_total)
        struct.pack_into("<Q", header, 32, data_start)
        region_name = b"audio_manifold"
        header[256:256 + len(region_name)] = region_name
        f.write(header)

        # Tensor index
        for entry in all_entries:
            name_bytes = entry["name"].encode("utf-8")[:256].ljust(256, b"\x00")
            packed = TENSOR_ENTRY_STRUCT.pack(
                name_bytes,
                entry["ndim"],
                *entry["shape"][:4] if len(entry["shape"]) >= 4 else
                    (entry["shape"] + [0] * (4 - len(entry["shape"])))[:4],
                entry["dtype_code"],
                entry["scale"],
                entry["zero_point"],
                entry["data_offset"],
                entry["data_size"],
            )
            f.write(packed)

        # Pad to data start
        current_pos = HEADER_SIZE + index_size
        if current_pos < data_start:
            f.write(b"\x00" * (data_start - current_pos))

        # Data
        for entry in all_entries:
            f.write(entry["data_bytes"])

    actual_size = os.path.getsize(output_path)
    print(f"[AudioManifold] Written: {actual_size / (1024**2):.1f} MB")

    return {
        "path": output_path,
        "num_tensors": num_total,
        "file_size": actual_size,
        "data_start": data_start,
        "prefix_counts": prefix_counts,
        "entries": all_entries,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Coordinate card creation (same pattern as ingest_canary_to_cards.py)
# ══════════════════════════════════════════════════════════════════════════════

def _tensor_semantic_subdomain(tensor_name: str) -> int:
    """Infer semantic subdomain from tensor name structure."""
    name = tensor_name.lower()
    if "encoder" in name:
        return 1
    if "decoder" in name:
        return 2
    if "embed" in name:
        return 3
    if "norm" in name or "ln" in name:
        return 4
    if "attn" in name or "attention" in name:
        return 5
    if "conv" in name:
        return 6
    if "linear" in name or "fc" in name or "proj" in name:
        return 7
    if "bias" in name:
        return 8
    if "vocos" in name or "vocoder" in name or "upsample" in name:
        return 9  # vocoder-specific
    return 0


def create_tensor_coordinate_card(
    tensor_name: str,
    tensor_shape: list,
    tensor_dtype: str,
    manifold_path: str,
    manifold_offset: int,
    manifold_size: int,
    model_prefix: str = "luxtts",
    scale: float = 1.0,
    zero_point: float = 0.0,
) -> dict:
    """Create a coordinate card for a single manifold tensor."""
    # D1-D3: Affect (neutral for model weights)
    affect_code = "053"
    # D4-D6: Semantic (technology domain, TTS subdomain)
    subdomain = _tensor_semantic_subdomain(tensor_name)
    semantic_code = f"6{subdomain}0"
    # D7-D9: Temporal (eternal — model weights are permanent)
    temporal_code = "999"

    coord_code = f"{affect_code}.{semantic_code}.{temporal_code}"

    # D10: affect_coupling α
    alpha = 0.8
    # D11: temporal_weight τ
    num_elements = 1
    for s in tensor_shape:
        num_elements *= s
    density = min(1.0, num_elements / 5_000_000)
    tau = round(1.0 + (density * 0.3), 4)

    content_hash = hashlib.md5(
        f"{model_prefix}/{tensor_name}".encode()
    ).hexdigest()[:4]

    card_id = hashlib.sha256(
        f"{model_prefix}/{tensor_name}".encode()
    ).hexdigest()[:12]

    return {
        "id": card_id,
        "c": coord_code,
        "α": alpha,
        "τ": tau,
        "n": 1,
        "d": 0,
        "h": content_hash,
        "ref": {
            "manifold": os.path.basename(manifold_path),
            "tensor": f"{model_prefix}/{tensor_name}",
            "offset": manifold_offset,
            "size": manifold_size,
            "shape": tensor_shape,
            "dtype": tensor_dtype,
            "scale": scale,
            "zero_point": zero_point,
        },
        "owner": "AudioCortexFairy",
    }


def create_manifest_coordinate_card(
    model_name: str,
    model_prefix: str,
    num_tensors: int,
    manifold_path: str,
    manifold_size_bytes: int,
    original_size_bytes: int,
    model_class: str = "ZipVoiceDistill+Vocos",
    framework: str = "torch",
) -> dict:
    """Create the manifest coordinate card for LuxTTS."""
    card_id = hashlib.sha256(
        f"{model_prefix}_manifest".encode()
    ).hexdigest()[:12]

    return {
        "id": card_id,
        "c": "053.690.999",  # neutral affect, technology+vocoder, eternal
        "α": 0.8,
        "τ": 1.3,
        "n": 1,
        "d": num_tensors,
        "h": hashlib.md5(model_name.encode()).hexdigest()[:4],
        "type": "manifest",
        "ref": {
            "manifold": os.path.basename(manifold_path),
            "model_name": model_name,
            "model_prefix": model_prefix,
            "model_class": model_class,
            "framework": framework,
            "num_tensors": num_tensors,
            "manifold_size_mb": round(manifold_size_bytes / (1024**2), 1),
            "original_size_mb": round(original_size_bytes / (1024**2), 1),
            "compression": "uint8_affine",
            "components": ["model (ZipVoiceDistill)", "vocos (Vocoder)"],
        },
        "owner": "AudioCortexFairy",
        "created_at": time.time(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Main ingestion
# ══════════════════════════════════════════════════════════════════════════════

def ingest(model_path: str = None, manifold_path: str = None, output_dir: str = None):
    """Ingest LuxTTS into the unified audio.manifold.

    APPENDS to existing manifold (preserves Canary tensors).
    Creates coordinate cards in luxtts_cards/cards.json.
    """
    model_prefix = "luxtts"
    t0 = time.time()

    print(f"\n{'='*60}")
    print(f"  LUXTTS INGESTION -> AUDIO MANIFOLD + COORDINATE CARDS")
    print(f"  Mode: APPEND to existing audio.manifold (alongside Canary)")
    print(f"  Cards: COORDINATES (~50 bytes each)")
    print(f"{'='*60}\n")

    import torch

    # ── 1. Resolve model path ──
    if model_path is None:
        try:
            from huggingface_hub import snapshot_download
            model_path = snapshot_download("YatharthS/LuxTTS")
        except ImportError:
            # Try known cache path
            model_path = os.path.join(
                os.path.expanduser("~"), ".cache", "huggingface", "hub",
                "models--YatharthS--LuxTTS", "snapshots",
                "527f245a276a0eb42ea103a7a512bcfd771eb9b6",
            )

    model_pt = os.path.join(model_path, "model.pt")
    vocos_bin = os.path.join(model_path, "vocoder", "vocos.bin")

    if not os.path.exists(model_pt):
        print(f"[Ingest] ERROR: model.pt not found at {model_pt}")
        return None, None
    if not os.path.exists(vocos_bin):
        print(f"[Ingest] ERROR: vocos.bin not found at {vocos_bin}")
        return None, None

    # ── 2. Load both state dicts ──
    print(f"[Ingest] Loading model.pt from {model_pt}...")
    raw_checkpoint = torch.load(model_pt, map_location="cpu", weights_only=True)
    model_sd = raw_checkpoint["model"]
    del raw_checkpoint

    print(f"[Ingest] Loading vocos.bin from {vocos_bin}...")
    vocos_sd = torch.load(vocos_bin, map_location="cpu", weights_only=True)

    model_params = sum(t.numel() for t in model_sd.values())
    vocos_params = sum(t.numel() for t in vocos_sd.values())
    model_bytes = sum(t.numel() * t.element_size() for t in model_sd.values())
    vocos_bytes = sum(t.numel() * t.element_size() for t in vocos_sd.values())
    total_original = model_bytes + vocos_bytes

    print(f"[Ingest] model.pt:  {len(model_sd)} tensors, {model_params/1e6:.1f}M params, "
          f"{model_bytes/(1024**2):.1f} MB")
    print(f"[Ingest] vocos.bin: {len(vocos_sd)} tensors, {vocos_params/1e6:.1f}M params, "
          f"{vocos_bytes/(1024**2):.1f} MB")
    print(f"[Ingest] Total:     {len(model_sd)+len(vocos_sd)} tensors, "
          f"{(model_params+vocos_params)/1e6:.1f}M params, "
          f"{total_original/(1024**2):.1f} MB")

    # ── 3. Read existing manifold entries (Canary tensors) ──
    if manifold_path is None:
        manifold_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "state", "akashic", "audio.manifold",
        )

    existing_entries = read_existing_manifold(manifold_path)
    existing_count = len(existing_entries)

    # Remove any existing luxtts/ tensors (in case of re-ingestion)
    existing_entries = [e for e in existing_entries if not e["name"].startswith(f"{model_prefix}/")]
    if existing_count != len(existing_entries):
        print(f"[Ingest] Removed {existing_count - len(existing_entries)} existing luxtts/ entries (re-ingestion)")

    # ── 4. Quantize and add LuxTTS tensors ──
    print(f"\n[Ingest] Quantizing LuxTTS tensors (uint8 affine)...")
    t_quant = time.time()

    new_entries = []
    total_quantized = 0

    # Main model tensors: luxtts/model/...
    for name in sorted(model_sd.keys()):
        tensor = model_sd[name]
        data_bytes, scale, zero_point, dtype_str = quantize_tensor_uint8(tensor)
        dtype_code = DTYPE_MAP.get(dtype_str, 1)
        shape = list(tensor.shape)
        while len(shape) < 4:
            shape.append(0)

        new_entries.append({
            "name": f"{model_prefix}/model/{name}",
            "ndim": len(tensor.shape),
            "shape": shape[:4],
            "dtype_code": dtype_code,
            "scale": scale,
            "zero_point": zero_point,
            "data_bytes": data_bytes,
        })
        total_quantized += len(data_bytes)

    # Vocos tensors: luxtts/vocos/...
    for name in sorted(vocos_sd.keys()):
        tensor = vocos_sd[name]
        data_bytes, scale, zero_point, dtype_str = quantize_tensor_uint8(tensor)
        dtype_code = DTYPE_MAP.get(dtype_str, 1)
        shape = list(tensor.shape)
        while len(shape) < 4:
            shape.append(0)

        new_entries.append({
            "name": f"{model_prefix}/vocos/{name}",
            "ndim": len(tensor.shape),
            "shape": shape[:4],
            "dtype_code": dtype_code,
            "scale": scale,
            "zero_point": zero_point,
            "data_bytes": data_bytes,
        })
        total_quantized += len(data_bytes)

    quant_time = time.time() - t_quant
    print(f"[Ingest] Quantized {len(new_entries)} tensors in {quant_time:.1f}s")
    print(f"[Ingest] Original:  {total_original / (1024**2):.1f} MB")
    print(f"[Ingest] Quantized: {total_quantized / (1024**2):.1f} MB "
          f"({total_quantized / max(1, total_original) * 100:.1f}%)")

    # ── 5. Write unified manifold (existing + new) ──
    all_entries = existing_entries + new_entries

    manifold_stats = write_audio_manifold(all_entries, manifold_path)

    # ── 6. Create coordinate cards for LuxTTS tensors ──
    print(f"\n[Ingest] Creating coordinate cards for {len(new_entries)} LuxTTS tensors...")

    cards = []
    # Use the final entries from manifold_stats (they have correct offsets)
    final_entries = manifold_stats["entries"]

    for entry in final_entries:
        if not entry["name"].startswith(f"{model_prefix}/"):
            continue

        # Get tensor name without the top prefix
        tensor_name = entry["name"][len(f"{model_prefix}/"):]

        card = create_tensor_coordinate_card(
            tensor_name=tensor_name,
            tensor_shape=entry["shape"][:entry["ndim"]],
            tensor_dtype=["float16", "float32", "bfloat16"][entry["dtype_code"]]
                if entry["dtype_code"] < 3 else "float32",
            manifold_path=manifold_path,
            manifold_offset=entry["data_offset"],
            manifold_size=entry["data_size"],
            model_prefix=model_prefix,
            scale=entry["scale"],
            zero_point=entry["zero_point"],
        )
        cards.append(card)

    # Manifest card
    manifest_card = create_manifest_coordinate_card(
        model_name="YatharthS/LuxTTS",
        model_prefix=model_prefix,
        num_tensors=len(new_entries),
        manifold_path=manifold_path,
        manifold_size_bytes=manifold_stats["file_size"],
        original_size_bytes=total_original,
    )
    cards.append(manifest_card)

    # Write cards
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fairies", "P40_Sensory", "cortex", "luxtts_cards",
        )
    os.makedirs(output_dir, exist_ok=True)
    cards_path = os.path.join(output_dir, "cards.json")

    print(f"[Ingest] Writing {len(cards)} coordinate cards to {cards_path}...")
    with open(cards_path, "w") as f:
        json.dump(cards, f, indent=2)
    cards_size = os.path.getsize(cards_path)

    # ── 7. Also regenerate Canary cards (their manifold offsets changed!) ──
    canary_cards = []
    for entry in final_entries:
        if not entry["name"].startswith("canary/"):
            continue
        tensor_name = entry["name"][len("canary/"):]
        card = create_tensor_coordinate_card(
            tensor_name=tensor_name,
            tensor_shape=entry["shape"][:entry["ndim"]],
            tensor_dtype=["float16", "float32", "bfloat16"][entry["dtype_code"]]
                if entry["dtype_code"] < 3 else "float32",
            manifold_path=manifold_path,
            manifold_offset=entry["data_offset"],
            manifold_size=entry["data_size"],
            model_prefix="canary",
            scale=entry["scale"],
            zero_point=entry["zero_point"],
        )
        canary_cards.append(card)

    if canary_cards:
        # Add canary manifest
        canary_orig = sum(e["data_size"] for e in final_entries if e["name"].startswith("canary/"))
        canary_manifest = create_manifest_coordinate_card(
            model_name="nvidia/canary-1b-flash",
            model_prefix="canary",
            num_tensors=len(canary_cards),
            manifold_path=manifold_path,
            manifold_size_bytes=manifold_stats["file_size"],
            original_size_bytes=canary_orig,
            model_class="EncDecMultiTaskModel",
            framework="nemo",
        )
        canary_cards.append(canary_manifest)

        canary_cards_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fairies", "P40_Sensory", "cortex", "canary_cards", "cards.json",
        )
        with open(canary_cards_path, "w") as f:
            json.dump(canary_cards, f, indent=2)
        canary_cards_size = os.path.getsize(canary_cards_path)
        print(f"[Ingest] Regenerated {len(canary_cards)} Canary cards "
              f"({canary_cards_size / 1024:.1f} KB) — offsets updated")

    # ── 8. Report ──
    elapsed = time.time() - t0
    prefix_counts = manifold_stats["prefix_counts"]

    print(f"\n{'='*60}")
    print(f"  LUXTTS INGESTION COMPLETE")
    print(f"  LuxTTS original:   {total_original / (1024**2):.1f} MB ({len(new_entries)} tensors)")
    print(f"  LuxTTS quantized:  {total_quantized / (1024**2):.1f} MB (uint8 affine)")
    print(f"  Audio manifold:    {manifold_stats['file_size'] / (1024**2):.1f} MB (unified)")
    for prefix, count in sorted(prefix_counts.items()):
        print(f"    {prefix}/: {count} tensors")
    print(f"  LuxTTS cards:      {cards_size / 1024:.1f} KB ({len(cards)} coordinate cards)")
    print(f"  Time:              {elapsed:.1f}s")
    print(f"  Manifold output:   {manifold_path}")
    print(f"  Cards output:      {cards_path}")
    print(f"")
    print(f"  Both Canary STT + LuxTTS now share ONE audio.manifold!")
    print(f"  Unified gravity mass for the audio portal.")
    print(f"{'='*60}\n")

    del model_sd, vocos_sd
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return cards_path, manifold_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest LuxTTS into unified audio manifold (APPEND alongside Canary)"
    )
    parser.add_argument("--model-path", default=None,
                        help="Path to LuxTTS model directory (or HF cache)")
    parser.add_argument("--manifold", default=None, help="Path to audio.manifold")
    parser.add_argument("--output", default=None, help="LuxTTS cards output directory")
    args = parser.parse_args()

    ingest(model_path=args.model_path, manifold_path=args.manifold,
           output_dir=args.output)
