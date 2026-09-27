"""
Ingest Canary-1b-flash (NeMo) model -> Unified Audio Manifold + Coordinate Cards.

Run ONCE under Python 3.12 (needs nemo-toolkit[asr] + torch installed):
    C:\\Users\\Ace\\AppData\\Local\\Programs\\Python\\Python312\\python.exe ingest_canary_to_cards.py

This script:
1. Loads canary-1b-flash via NeMo's EncDecMultiTaskModel.from_pretrained()
2. Extracts model.state_dict() — all weight tensors
3. Writes tensors into state/akashic/audio.manifold (UNIFIED audio manifold)
   - uint8 quantized, tensors namespaced as "canary/<tensor_name>"
   - Same binary format as florence.manifold (HEADER+INDEX+DATA)
   - LuxTTS gets added to the SAME file later via --append mode
4. Creates COORDINATE cards (~50 bytes each) for each tensor
   - Triple helix addressing: AAA.SSS.TTT (Affect.Semantic.Temporal)
   - Cards are ADDRESSES, not data containers
   - The manifold holds the actual data; cards are how SRM finds it
   - CollisionChamber DESTROYS data and produces coordinate cards from the destruction

Cards are ~200 bytes each × 1,406 tensors = ~300 KB total (not 4.3 GB!)
The engine reads directly from audio.manifold via mmap — cards are for SRM recall.

Follows coordinate_inference.py build_coordinate_card() pattern.
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


# ── Coordinate Card Creation ─────────────────────────────────────────────────
# Cards are COORDINATES (~50 bytes), not data containers.
# Each tensor in the manifold gets a lightweight coordinate card that:
#   - Has AAA.SSS.TTT helix address (D1-D9)
#   - Has α (affect coupling, D10) and τ (temporal weight, D11)
#   - Points to the manifold location (tensor name, offset, size)
#   - Is recalled by the SRM fairy for manifold lookups
# ─────────────────────────────────────────────────────────────────────────────

def _tensor_semantic_subdomain(tensor_name: str) -> int:
    """Infer semantic subdomain from tensor name structure."""
    name = tensor_name.lower()
    if "encoder" in name:
        return 1  # encoding/perception
    if "decoder" in name:
        return 2  # decoding/generation
    if "embed" in name:
        return 3  # embedding space
    if "norm" in name or "ln" in name:
        return 4  # normalization
    if "attn" in name or "attention" in name:
        return 5  # attention mechanism
    if "conv" in name:
        return 6  # convolution
    if "linear" in name or "fc" in name or "proj" in name:
        return 7  # projection
    if "bias" in name:
        return 8  # bias terms
    return 0  # general


def create_tensor_coordinate_card(
    tensor_name: str,
    tensor_shape: list,
    tensor_dtype: str,
    manifold_path: str,
    manifold_offset: int,
    manifold_size: int,
    model_prefix: str = "canary",
    scale: float = 1.0,
    zero_point: float = 0.0,
) -> dict:
    """Create a coordinate card for a single manifold tensor.

    This is the TRUE portal card (~50 byte coordinate + manifold pointer).
    The data lives in the manifold; the card is just the address.

    Returns a card dict following build_coordinate_card() pattern:
        c:  AAA.SSS.TTT helix coordinate
        α:  affect coupling (D10)
        τ:  temporal weight (D11)
        n:  observation count
        d:  degree (edge density)
        h:  content fingerprint (4 chars)
        ref: manifold reference (tensor name, offset, size)
    """
    # ── D1-D3: Affect (neutral for model weights — no emotional content) ──
    # Domain 0 (neutral), valence 5 (balanced), intensity 3 (low arousal)
    affect_code = "053"

    # ── D4-D6: Semantic (technology/engineering domain) ──
    # Domain 6 (technology), subdomain from tensor structure, detail 0
    subdomain = _tensor_semantic_subdomain(tensor_name)
    semantic_code = f"6{subdomain}0"

    # ── D7-D9: Temporal (eternal/archetypal — model weights are permanent) ──
    # Scale 9 (eternal), recurrence 9 (always needed), decay 9 (never decays)
    temporal_code = "999"

    coord_code = f"{affect_code}.{semantic_code}.{temporal_code}"

    # ── D10: affect_coupling α — model weights have no emotional pull ──
    alpha = 0.8  # minimum (no consciousness coupling for raw weights)

    # ── D11: temporal_weight τ — dense tensors get higher dilation ──
    num_elements = 1
    for s in tensor_shape:
        num_elements *= s
    density = min(1.0, num_elements / 5_000_000)  # normalize to ~5M params
    tau = round(1.0 + (density * 0.3), 4)

    # Content fingerprint (from tensor name, not the actual data)
    content_hash = hashlib.md5(
        f"{model_prefix}/{tensor_name}".encode()
    ).hexdigest()[:4]

    # Deterministic card ID from tensor address
    card_id = hashlib.sha256(
        f"{model_prefix}/{tensor_name}".encode()
    ).hexdigest()[:12]

    return {
        "id": card_id,
        # ── The ~50 byte coordinate card (matches build_coordinate_card output) ──
        "c": coord_code,       # D1-D9: AAA.SSS.TTT
        "α": alpha,            # D10: affect coupling
        "τ": tau,              # D11: temporal weight
        "n": 1,                # observation count
        "d": 0,                # degree (edge density)
        "h": content_hash,     # content fingerprint
        # ── Manifold reference (where the actual data lives) ──
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
    model_class: str = "EncDecMultiTaskModel",
    framework: str = "nemo",
) -> dict:
    """Create the manifest coordinate card — summary of the model in the manifold.

    This card lets SRM recall 'what models are in audio.manifold' without
    loading the whole manifold. It's an index card, not a data container.
    """
    card_id = hashlib.sha256(
        f"{model_prefix}_manifest".encode()
    ).hexdigest()[:12]

    return {
        "id": card_id,
        # ── Coordinate (same pattern) ──
        "c": "053.600.999",     # neutral affect, technology, eternal
        "α": 0.8,
        "τ": 1.3,              # max dilation — manifest is critical
        "n": 1,
        "d": num_tensors,      # degree = number of tensor cards it indexes
        "h": hashlib.md5(model_name.encode()).hexdigest()[:4],
        # ── Manifest reference ──
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
        },
        "owner": "AudioCortexFairy",
        "created_at": time.time(),
    }


# ── Unified Audio Manifold (same binary format as florence_to_helix.py) ─────
# ONE file for ALL audio models. Tensor names prefixed: "canary/...", "luxtts/..."
# This way Canary + LuxTTS share gravity mass in a single manifold.

HEADER_SIZE = 4096
MAGIC = b"AUDM"  # Audio Manifold (unified)
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
    """Quantize float tensor to uint8 with per-tensor affine scaling.
    Same as florence_to_helix.py.
    """
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


def write_audio_manifold(state_dict: dict, output_path: str,
                         model_prefix: str = "canary",
                         existing_entries: list = None) -> dict:
    """Write tensors into the unified audio manifold file.

    Tensor names are prefixed with model_prefix/ so multiple models
    can coexist in one file: "canary/encoder.layer.0.weight", "luxtts/decoder.weight"

    Args:
        state_dict: PyTorch state dict to write
        output_path: Path to audio.manifold
        model_prefix: Namespace prefix for this model's tensors
        existing_entries: If appending to existing manifold, pass existing entries

    Returns:
        Stats dict including the entries list (for append mode)
    """
    all_entries = list(existing_entries) if existing_entries else []

    # Namespace tensors with model prefix
    sorted_names = sorted(state_dict.keys())
    num_new_tensors = len(sorted_names)

    print(f"\n[AudioManifold] Quantizing {num_new_tensors} tensors "
          f"(prefix: {model_prefix}/)...")
    t0 = time.time()

    total_original_bytes = 0
    total_quantized_bytes = 0

    for i, name in enumerate(sorted_names):
        tensor = state_dict[name]
        total_original_bytes += tensor.nelement() * tensor.element_size()

        data_bytes, scale, zero_point, dtype_str = quantize_tensor_uint8(tensor)
        dtype_code = DTYPE_MAP.get(dtype_str, 1)

        shape = list(tensor.shape)
        while len(shape) < 4:
            shape.append(0)
        shape = shape[:4]

        # Prefix tensor name with model namespace
        prefixed_name = f"{model_prefix}/{name}"

        all_entries.append({
            "name": prefixed_name,
            "ndim": len(tensor.shape),
            "shape": shape,
            "dtype_code": dtype_code,
            "scale": scale,
            "zero_point": zero_point,
            "data_bytes": data_bytes,
        })
        total_quantized_bytes += len(data_bytes)

        if (i + 1) % 50 == 0 or (i + 1) == num_new_tensors:
            print(f"       [{i+1}/{num_new_tensors}] {model_prefix}/{name[:50]}... "
                  f"({tensor.shape})")

    t_quant = time.time() - t0
    print(f"       Done in {t_quant:.1f}s")
    print(f"       Original:  {total_original_bytes / (1024**2):.1f} MB")
    print(f"       Quantized: {total_quantized_bytes / (1024**2):.1f} MB")

    # Now write the FULL manifold (all entries: existing + new)
    num_total = len(all_entries)
    index_start = HEADER_SIZE
    index_size = num_total * TENSOR_ENTRY_SIZE
    data_start = _align_to_page(index_start + index_size)

    current_offset = 0
    for entry in all_entries:
        entry["data_offset"] = current_offset
        entry["data_size"] = len(entry["data_bytes"])
        current_offset += entry["data_size"]

    total_data_bytes = current_offset
    total_file_size = data_start + total_data_bytes

    print(f"\n[AudioManifold] Writing unified audio manifold: {output_path}")
    print(f"       Total tensors: {num_total} ({num_new_tensors} new)")
    print(f"       Header:     {HEADER_SIZE} bytes")
    print(f"       Index:      {index_size} bytes")
    print(f"       Data:       {total_data_bytes} bytes")
    print(f"       Total:      {total_file_size / (1024**2):.1f} MB")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as f:
        # Header
        header = bytearray(HEADER_SIZE)
        header[0:4] = MAGIC
        struct.pack_into("<I", header, 4, VERSION)
        struct.pack_into("<I", header, 8, num_total)
        # Store total stats
        all_orig = sum(e.get("_orig_bytes", 0) for e in all_entries) or total_original_bytes
        struct.pack_into("<Q", header, 16, total_original_bytes)
        struct.pack_into("<Q", header, 24, total_quantized_bytes)
        struct.pack_into("<Q", header, 32, data_start)
        # Region name
        region_name = b"audio_manifold"
        header[256:256 + len(region_name)] = region_name
        f.write(header)

        # Tensor index
        for entry in all_entries:
            name_bytes = entry["name"].encode("utf-8")[:256].ljust(256, b"\x00")
            packed = TENSOR_ENTRY_STRUCT.pack(
                name_bytes,
                entry["ndim"],
                *entry["shape"],
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
        "num_new_tensors": num_new_tensors,
        "original_bytes": total_original_bytes,
        "quantized_bytes": total_quantized_bytes,
        "file_size": actual_size,
        "quant_time_s": round(t_quant, 1),
        "entries": all_entries,  # For append mode
    }


# ── Main ────────────────────────────────────────────────────────────────────

def ingest(model_name: str = "nvidia/canary-1b-flash",
           output_dir: str = None, manifold_path: str = None):
    """Main ingestion: Canary NeMo model -> audio.manifold + coordinate cards.

    Coordinate cards are ~50 byte addresses (AAA.SSS.TTT + manifold ref).
    The manifold holds the actual quantized tensor data.

    Args:
        model_name: HuggingFace model name
        output_dir: Where to write cards.json (coordinate cards)
        manifold_path: Path to audio.manifold (shared with LuxTTS)
    """
    model_prefix = "canary"
    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"  CANARY MODEL INGESTION -> AUDIO MANIFOLD + COORDINATE CARDS")
    print(f"  Model: {model_name}")
    print(f"  Cards: COORDINATES (~50 bytes each), not data containers")
    print(f"  Manifold: UNIFIED audio.manifold (shared with LuxTTS)")
    print(f"{'='*60}\n")

    # Suppress NeMo noise
    import logging
    for _ln in ('nemo', 'pytorch_lightning', 'lightning',
                'nemo.utils', 'nemo.collections'):
        logging.getLogger(_ln).setLevel(logging.ERROR)

    import torch
    from nemo.collections.asr.models import EncDecMultiTaskModel

    # ── 1. Load model ──
    print(f"[Ingest] Loading {model_name}...")
    t_load = time.time()
    model = EncDecMultiTaskModel.from_pretrained(model_name)
    model.eval()
    print(f"[Ingest] Model loaded in {time.time() - t_load:.1f}s")

    # ── 2. Extract state dict ──
    state_dict = model.state_dict()
    num_params = sum(p.numel() for p in state_dict.values())
    num_tensors = len(state_dict)
    print(f"[Ingest] {num_tensors} tensors, {num_params/1e6:.1f}M parameters")

    # ── 3. Write unified audio.manifold (Canary tensors as "canary/...") ──
    if manifold_path is None:
        manifold_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "state", "akashic", "audio.manifold",
        )

    manifold_stats = write_audio_manifold(
        state_dict, manifold_path,
        model_prefix=model_prefix,
    )

    # ── 4. Create COORDINATE cards for each tensor ──
    # Cards are ADDRESSES (~50 bytes), not data containers.
    # Each tensor gets a helix coordinate card pointing into the manifold.
    # SRM fairy recalls these cards by coordinate proximity.
    print(f"\n[Ingest] Creating coordinate cards for {num_tensors} tensors...")

    cards = []
    entries = manifold_stats["entries"]

    for entry in entries:
        # Strip prefix to get original tensor name
        full_name = entry["name"]  # "canary/encoder.layers.0.weight"
        tensor_name = full_name.split("/", 1)[1] if "/" in full_name else full_name

        card = create_tensor_coordinate_card(
            tensor_name=tensor_name,
            tensor_shape=entry["shape"][:entry["ndim"]],
            tensor_dtype=["float16", "float32", "bfloat16"][entry["dtype_code"]],
            manifold_path=manifold_path,
            manifold_offset=entry["data_offset"],
            manifold_size=entry["data_size"],
            model_prefix=model_prefix,
            scale=entry["scale"],
            zero_point=entry["zero_point"],
        )
        cards.append(card)

    # Add manifest card (index of the whole model)
    original_bytes = sum(
        state_dict[name].nelement() * state_dict[name].element_size()
        for name in state_dict
    )
    manifest_card = create_manifest_coordinate_card(
        model_name=model_name,
        model_prefix=model_prefix,
        num_tensors=num_tensors,
        manifold_path=manifold_path,
        manifold_size_bytes=manifold_stats["file_size"],
        original_size_bytes=original_bytes,
    )
    cards.append(manifest_card)

    # ── 5. Write cards.json (coordinate cards — tiny!) ──
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fairies", "P40_Sensory", "cortex", "canary_cards",
        )
    os.makedirs(output_dir, exist_ok=True)
    cards_path = os.path.join(output_dir, "cards.json")

    print(f"[Ingest] Writing {len(cards)} coordinate cards to {cards_path}...")
    with open(cards_path, "w") as f:
        json.dump(cards, f, indent=2)
    cards_size = os.path.getsize(cards_path)

    # ── 6. Report ──
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE")
    print(f"  State dict:      {original_bytes / (1024**2):.1f} MB ({num_tensors} tensors)")
    print(f"  Audio manifold:  {manifold_stats['file_size'] / (1024**2):.1f} MB (uint8 quantized)")
    print(f"  Compression:     {manifold_stats['file_size'] / max(1, original_bytes) * 100:.1f}%")
    print(f"  Coordinate cards:{cards_size / 1024:.1f} KB ({len(cards)} cards)")
    print(f"  Card avg size:   ~{cards_size // len(cards)} bytes each")
    print(f"  Time:            {elapsed:.1f}s")
    print(f"  Cards output:    {cards_path}")
    print(f"  Manifold output: {manifold_path}")
    print(f"")
    print(f"  Cards are COORDINATES, not data. Engine loads from manifold.")
    print(f"  Next: Run ingest_luxtts_to_audio_manifold.py to add LuxTTS")
    print(f"  to the SAME audio.manifold (prefix: luxtts/)")
    print(f"{'='*60}\n")

    del model, state_dict
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return cards_path, manifold_path


def verify(cards_path: str, manifold_path: str = None):
    """Verify coordinate cards point to valid manifold entries."""
    print(f"\n[Verify] Loading coordinate cards from {cards_path}...")
    with open(cards_path) as f:
        cards = json.load(f)

    manifest = None
    tensor_cards = []
    for card in cards:
        if card.get("type") == "manifest":
            manifest = card
        elif "ref" in card and "tensor" in card.get("ref", {}):
            tensor_cards.append(card)

    print(f"[Verify] Found {len(tensor_cards)} tensor cards + "
          f"{'1 manifest' if manifest else 'NO manifest'}")

    if not manifest:
        print("[Verify] WARNING: No manifest card found")
    else:
        ref = manifest["ref"]
        print(f"[Verify] Model: {ref['model_name']}, {ref['num_tensors']} tensors, "
              f"{ref['manifold_size_mb']} MB manifold")

    # Verify each card has valid coordinate + manifold reference
    valid = 0
    errors = 0
    for card in tensor_cards:
        # Check coordinate format
        coord = card.get("c", "")
        parts = coord.split(".")
        if len(parts) != 3 or not all(len(p) == 3 for p in parts):
            print(f"[Verify] BAD COORD: {card.get('id')} -> {coord}")
            errors += 1
            continue

        # Check manifold reference
        ref = card.get("ref", {})
        if not ref.get("tensor") or ref.get("size", 0) <= 0:
            print(f"[Verify] BAD REF: {card.get('id')} -> {ref}")
            errors += 1
            continue

        valid += 1

    # If manifold path given, verify tensor index matches
    if manifold_path and os.path.exists(manifold_path):
        print(f"[Verify] Checking manifold: {manifold_path}")
        file_size = os.path.getsize(manifold_path)
        print(f"[Verify] Manifold size: {file_size / (1024**2):.1f} MB")

        # Read header to get tensor count
        with open(manifold_path, "rb") as f:
            header = f.read(HEADER_SIZE)
            magic = header[0:4]
            version = struct.unpack_from("<I", header, 4)[0]
            num_tensors = struct.unpack_from("<I", header, 8)[0]

        print(f"[Verify] Manifold: magic={magic}, v{version}, {num_tensors} tensors")

        if num_tensors == len(tensor_cards):
            print(f"[Verify] Tensor count matches: {num_tensors}")
        else:
            print(f"[Verify] MISMATCH: manifold has {num_tensors}, cards have {len(tensor_cards)}")
            errors += 1

    print(f"\n[Verify] {valid} valid, {errors} errors")
    if errors == 0:
        print(f"[Verify] ALL CHECKS PASSED")
    return errors == 0


def cards_only(manifold_path: str, output_dir: str = None, model_prefix: str = "canary"):
    """Generate coordinate cards from an EXISTING audio.manifold (no model loading).

    Use this when the manifold already exists and you just need to
    regenerate the coordinate cards.
    """
    print(f"\n[CardsOnly] Reading manifold: {manifold_path}")

    if not os.path.exists(manifold_path):
        print(f"[CardsOnly] ERROR: Manifold not found: {manifold_path}")
        return None

    file_size = os.path.getsize(manifold_path)
    print(f"[CardsOnly] Manifold size: {file_size / (1024**2):.1f} MB")

    with open(manifold_path, "rb") as f:
        # Read header
        header = f.read(HEADER_SIZE)
        magic = header[0:4]
        if magic != MAGIC:
            print(f"[CardsOnly] ERROR: Bad magic: {magic} (expected {MAGIC})")
            return None

        num_tensors = struct.unpack_from("<I", header, 8)[0]
        original_bytes = struct.unpack_from("<Q", header, 16)[0]
        quantized_bytes = struct.unpack_from("<Q", header, 24)[0]
        data_start = struct.unpack_from("<Q", header, 32)[0]

        print(f"[CardsOnly] {num_tensors} tensors, "
              f"{original_bytes / (1024**2):.1f} MB original -> "
              f"{quantized_bytes / (1024**2):.1f} MB quantized")

        # Read tensor index
        cards = []
        prefix_tensors = 0
        for i in range(num_tensors):
            raw = f.read(TENSOR_ENTRY_SIZE)
            parsed = TENSOR_ENTRY_STRUCT.unpack(raw)
            full_name = parsed[0].rstrip(b"\x00").decode("utf-8")
            ndim = parsed[1]
            shape = list(parsed[2:6])[:ndim]
            dtype_code = parsed[6]
            scale = parsed[7]
            zero_point = parsed[8]
            data_offset = parsed[9]
            data_size = parsed[10]

            # Only create cards for our prefix
            if not full_name.startswith(f"{model_prefix}/"):
                continue

            prefix_tensors += 1
            tensor_name = full_name.split("/", 1)[1]
            dtype_name = ["float16", "float32", "bfloat16"][dtype_code] if dtype_code < 3 else "float32"

            card = create_tensor_coordinate_card(
                tensor_name=tensor_name,
                tensor_shape=shape,
                tensor_dtype=dtype_name,
                manifold_path=manifold_path,
                manifold_offset=data_offset,
                manifold_size=data_size,
                model_prefix=model_prefix,
                scale=scale,
                zero_point=zero_point,
            )
            cards.append(card)

    # Add manifest card
    manifest_card = create_manifest_coordinate_card(
        model_name=f"{model_prefix}-model",
        model_prefix=model_prefix,
        num_tensors=prefix_tensors,
        manifold_path=manifold_path,
        manifold_size_bytes=file_size,
        original_size_bytes=original_bytes,
    )
    cards.append(manifest_card)

    # Write cards.json
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fairies", "P40_Sensory", "cortex", "canary_cards",
        )
    os.makedirs(output_dir, exist_ok=True)
    cards_path = os.path.join(output_dir, "cards.json")

    print(f"[CardsOnly] Writing {len(cards)} coordinate cards to {cards_path}...")
    with open(cards_path, "w") as f:
        json.dump(cards, f, indent=2)
    cards_size = os.path.getsize(cards_path)

    print(f"[CardsOnly] Done: {cards_size / 1024:.1f} KB "
          f"(~{cards_size // len(cards)} bytes/card)")
    return cards_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest Canary-1b-flash into unified audio manifold + coordinate cards"
    )
    parser.add_argument("--model", default="nvidia/canary-1b-flash")
    parser.add_argument("--output", default=None, help="Cards output directory")
    parser.add_argument("--manifold", default=None, help="Path to audio.manifold")
    parser.add_argument("--verify", action="store_true", help="Verify existing cards")
    parser.add_argument("--cards-only", action="store_true",
                        help="Generate coordinate cards from existing manifold (no model loading)")
    parser.add_argument("--cards-path", default=None)
    args = parser.parse_args()

    if args.verify:
        path = args.cards_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fairies", "P40_Sensory", "cortex", "canary_cards", "cards.json",
        )
        manifold = args.manifold or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "state", "akashic", "audio.manifold",
        )
        verify(path, manifold)
    elif args.cards_only:
        manifold = args.manifold or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "state", "akashic", "audio.manifold",
        )
        cards_only(manifold, args.output)
    else:
        ingest(model_name=args.model, output_dir=args.output,
               manifold_path=args.manifold)
