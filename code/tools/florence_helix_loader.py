"""
Florence Manifold Loader — Fast model loading via mmap'd binary manifold.

Loads Florence-2-large from a single binary .manifold file that contains
int8-quantized weights in a format designed for memory-mapped access.
The manifold is created once by florence_to_helix.py and stored at:
    state/akashic/florence.manifold

Binary format:
    HEADER  (4096 bytes): magic, version, tensor count, data size, model name
    INDEX   (304 bytes per tensor): name, shape, dtype, scale, zero_point, offset, size
    DATA    (page-aligned): raw uint8 bytes, concatenated

Boot-time loading:
    1. mmap the manifold file (read-only, zero copy)
    2. Parse header + tensor index
    3. Dequantize tensors in parallel (ThreadPoolExecutor, 8 workers)
    4. Build state_dict, load into empty model shell
    5. Move to device, eval mode

Usage:
    from tools.florence_helix_loader import load_florence_from_manifold

    model, processor = load_florence_from_manifold(device="cuda")

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import mmap
import os
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

import torch

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MANIFOLD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state",
    "akashic",
    "florence.manifold",
)

_MODEL_ID = "microsoft/Florence-2-large"

_MAGIC = b"FLRN"
_HEADER_SIZE = 4096
_INDEX_ENTRY_SIZE = 304
_PAGE_SIZE = 4096

# dtype_code mapping (matches florence_to_helix.py conventions)
_DTYPE_CODE_MAP = {
    0: torch.float32,
    1: torch.float16,
    2: torch.bfloat16,
    3: torch.int8,
    4: torch.uint8,
    5: torch.int32,
    6: torch.int64,
}


# ---------------------------------------------------------------------------
# Internal: header / index parsing
# ---------------------------------------------------------------------------

def _parse_header(mm: mmap.mmap) -> Optional[dict]:
    """Parse the 4096-byte manifold header.

    Returns dict with keys: version, num_tensors, total_data_bytes, model_name
    or None on invalid magic.
    """
    magic = mm[0:4]
    if magic != _MAGIC:
        print(f"[Florence] Bad magic: expected {_MAGIC!r}, got {magic!r}",
              file=sys.stderr)
        return None

    version = struct.unpack_from("<I", mm, 4)[0]
    num_tensors = struct.unpack_from("<I", mm, 8)[0]
    total_data_bytes = struct.unpack_from("<Q", mm, 12)[0]
    model_name_raw = mm[20:276]  # 256 bytes
    model_name = model_name_raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")

    return {
        "version": version,
        "num_tensors": num_tensors,
        "total_data_bytes": total_data_bytes,
        "model_name": model_name,
    }


def _parse_index(mm: mmap.mmap, num_tensors: int) -> list:
    """Parse the tensor index starting at offset 4096.

    Each entry is 304 bytes:
        name:        256 bytes null-padded UTF-8
        ndim:        uint32 LE
        shape:       4x uint32 LE (padded to 4 dims)
        dtype_code:  uint32 LE
        scale:       float32 LE
        zero_point:  float32 LE
        data_offset: uint64 LE (relative to DATA section start)
        data_size:   uint64 LE

    Returns list of dicts.
    """
    entries = []
    base = _HEADER_SIZE

    for i in range(num_tensors):
        off = base + i * _INDEX_ENTRY_SIZE

        # Name: 256 bytes
        name_raw = mm[off:off + 256]
        name = name_raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")

        # ndim, shape[4], dtype_code, scale, zero_point, data_offset, data_size
        # Format: I 4I I f f Q Q = 4 + 16 + 4 + 4 + 4 + 8 + 8 = 48 bytes
        vals = struct.unpack_from("<I4IIffQQ", mm, off + 256)
        ndim = vals[0]
        shape_raw = vals[1:5]
        shape = list(shape_raw[:ndim])  # Only take ndim dimensions
        dtype_code = vals[5]
        scale = vals[6]
        zero_point = vals[7]
        data_offset = vals[8]
        data_size = vals[9]

        entries.append({
            "name": name,
            "ndim": ndim,
            "shape": shape,
            "dtype_code": dtype_code,
            "scale": scale,
            "zero_point": zero_point,
            "data_offset": data_offset,
            "data_size": data_size,
        })

    return entries


def _compute_data_section_start(num_tensors: int) -> int:
    """Calculate page-aligned start of DATA section."""
    raw = _HEADER_SIZE + num_tensors * _INDEX_ENTRY_SIZE
    # Round up to next page boundary
    return ((raw + _PAGE_SIZE - 1) // _PAGE_SIZE) * _PAGE_SIZE


# ---------------------------------------------------------------------------
# Internal: tensor dequantization
# ---------------------------------------------------------------------------

def _dequantize_entry(
    mm: mmap.mmap,
    entry: dict,
    data_start: int,
    target_dtype: torch.dtype,
) -> Tuple[str, torch.Tensor]:
    """Dequantize a single tensor from mmap'd data.

    Reads raw uint8 bytes via zero-copy mmap slice, converts to float,
    applies scale/zero_point, reshapes, and casts to target dtype.
    """
    name = entry["name"]
    shape = entry["shape"]
    scale = entry["scale"]
    zero_point = entry["zero_point"]
    offset = data_start + entry["data_offset"]
    size = entry["data_size"]

    # Zero-copy read from mmap into uint8 tensor
    raw_bytes = mm[offset:offset + size]
    uint8_tensor = torch.frombuffer(bytearray(raw_bytes), dtype=torch.uint8)

    # Dequantize: float_val = (uint8_val - zero_point) * scale
    float_tensor = (uint8_tensor.float() - zero_point) * scale

    # Reshape to original dimensions
    if shape:
        float_tensor = float_tensor.reshape(shape)

    # Cast to target dtype
    if target_dtype != torch.float32:
        float_tensor = float_tensor.to(target_dtype)

    return name, float_tensor


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def florence_manifold_exists(manifold_path: str = None) -> bool:
    """Check if the Florence manifold file exists and has valid magic.

    Args:
        manifold_path: Path to the .manifold file.
                       Defaults to state/akashic/florence.manifold.

    Returns:
        True if the file exists and starts with b"FLRN".
    """
    if manifold_path is None:
        manifold_path = _DEFAULT_MANIFOLD_PATH
    manifold_path = os.path.normpath(manifold_path)

    if not os.path.isfile(manifold_path):
        return False

    try:
        with open(manifold_path, "rb") as f:
            magic = f.read(4)
            return magic == _MAGIC
    except OSError:
        return False


def get_florence_manifold_info(manifold_path: str = None) -> Optional[dict]:
    """Read manifold header and return info without loading weights.

    Args:
        manifold_path: Path to the .manifold file.

    Returns:
        Dict with keys: model_name, num_tensors, total_bytes, file_size_mb
        or None if the file is missing/invalid.
    """
    if manifold_path is None:
        manifold_path = _DEFAULT_MANIFOLD_PATH
    manifold_path = os.path.normpath(manifold_path)

    if not os.path.isfile(manifold_path):
        return None

    try:
        file_size = os.path.getsize(manifold_path)
        with open(manifold_path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                header = _parse_header(mm)
                if header is None:
                    return None

                return {
                    "model_name": header["model_name"],
                    "num_tensors": header["num_tensors"],
                    "total_bytes": header["total_data_bytes"],
                    "file_size_mb": round(file_size / (1024 * 1024), 1),
                    "version": header["version"],
                }
    except OSError as exc:
        print(f"[Florence] Failed to read manifold info: {exc}", file=sys.stderr)
        return None


def load_florence_from_manifold(
    manifold_path: str = None,
    device: str = "cuda",
    dtype=None,
    max_workers: int = 8,
) -> Tuple:
    """Load Florence-2-large from a binary manifold file via mmap.

    The manifold file contains int8-quantized weights in a format designed
    for memory-mapped, zero-copy access. Tensors are dequantized in parallel
    using a thread pool.

    Args:
        manifold_path: Path to florence.manifold.
                       Defaults to state/akashic/florence.manifold.
        device:        Target device ("cuda" or "cpu").
        dtype:         Target dtype. Defaults to float16 for CUDA, float32 for CPU.
        max_workers:   Thread pool size for parallel dequantization.

    Returns:
        (model, processor) tuple on success, or (None, None) on failure.
    """
    t0 = time.time()

    if manifold_path is None:
        manifold_path = _DEFAULT_MANIFOLD_PATH
    manifold_path = os.path.normpath(manifold_path)

    # ------------------------------------------------------------------
    # 1. Validate file exists
    # ------------------------------------------------------------------
    if not os.path.isfile(manifold_path):
        print(f"[Florence] Manifold not found: {manifold_path}", file=sys.stderr)
        return (None, None)

    # ------------------------------------------------------------------
    # 2. Validate device / dtype
    # ------------------------------------------------------------------
    if device == "cuda":
        if not torch.cuda.is_available():
            print("[Florence] CUDA requested but not available, using CPU",
                  file=sys.stderr)
            device = "cpu"
        else:
            try:
                torch.cuda.get_device_name(0)
            except Exception:
                print("[Florence] CUDA device unusable, falling back to CPU",
                      file=sys.stderr)
                device = "cpu"

    if dtype is None:
        dtype = torch.float16 if device == "cuda" else torch.float32

    # Force fp32 on CPU (fp16 is extremely slow on CPU)
    if device == "cpu":
        dtype = torch.float32

    # ------------------------------------------------------------------
    # 3. mmap the manifold file
    # ------------------------------------------------------------------
    try:
        f = open(manifold_path, "rb")
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    except OSError as exc:
        print(f"[Florence] Failed to mmap manifold: {exc}", file=sys.stderr)
        return (None, None)

    try:
        # --------------------------------------------------------------
        # 4. Parse header
        # --------------------------------------------------------------
        header = _parse_header(mm)
        if header is None:
            return (None, None)

        num_tensors = header["num_tensors"]
        model_name = header["model_name"]
        print(f"[Florence] Manifold: {model_name}, {num_tensors} tensors, "
              f"v{header['version']}, target={device}/{dtype}")

        # --------------------------------------------------------------
        # 5. Parse tensor index
        # --------------------------------------------------------------
        t_index = time.time()
        entries = _parse_index(mm, num_tensors)
        data_start = _compute_data_section_start(num_tensors)
        t_index_done = time.time()
        print(f"[Florence] Index parsed: {len(entries)} entries in "
              f"{(t_index_done - t_index) * 1000:.0f}ms, "
              f"data starts at offset {data_start}")

        # --------------------------------------------------------------
        # 6. Dequantize tensors in parallel
        # --------------------------------------------------------------
        t_dequant = time.time()
        state_dict = {}
        errors = 0

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _dequantize_entry, mm, entry, data_start, dtype
                ): entry["name"]
                for entry in entries
            }

            for future in as_completed(futures):
                tensor_name = futures[future]
                try:
                    name, tensor = future.result()
                    state_dict[name] = tensor
                except Exception as exc:
                    print(f"[Florence] Failed to dequantize {tensor_name}: {exc}",
                          file=sys.stderr)
                    errors += 1

        t_dequant_done = time.time()
        print(f"[Florence] Dequantized {len(state_dict)} tensors in "
              f"{t_dequant_done - t_dequant:.2f}s "
              f"({max_workers} workers, {errors} errors)")

        if not state_dict:
            print("[Florence] Empty state_dict — nothing to load", file=sys.stderr)
            return (None, None)

    finally:
        mm.close()
        f.close()

    # ------------------------------------------------------------------
    # 7. Create model from config + load state_dict
    # ------------------------------------------------------------------
    try:
        # ── Stub audio_utils + video_utils to prevent access violation on 3.14t ──
        # AutoProcessor → processing_utils → audio_utils → requests → crash
        # Florence-2 never uses audio/video, so stub the modules before import.
        # Use __getattr__ so any attribute access returns a no-op placeholder.
        import types as _types
        class _StubModule(_types.ModuleType):
            """Lazy stub that returns None/no-op for any attribute."""
            def __getattr__(self, name):
                if name.startswith('_'):
                    raise AttributeError(name)
                return None
        for _stub_name in ("transformers.audio_utils", "transformers.video_utils"):
            if _stub_name not in sys.modules:
                sys.modules[_stub_name] = _StubModule(_stub_name)
        del _types, _StubModule

        from transformers import AutoModelForCausalLM, AutoConfig, AutoProcessor

        # Load config from HF cache (tiny metadata, fast)
        config = AutoConfig.from_pretrained(
            _MODEL_ID, trust_remote_code=True
        )

        # Instantiate empty model shell (no weights)
        model = AutoModelForCausalLM.from_config(
            config,
            trust_remote_code=True,
            attn_implementation="eager",
        )

        # Resolve tied weights — Florence-2 (BART-style) ties shared.weight
        # to encoder/decoder embed_tokens and lm_head, but manifold only
        # stores the shared copy. Fill in the tied copies before loading.
        _shared_key = "language_model.model.shared.weight"
        _tied_keys = [
            "language_model.model.encoder.embed_tokens.weight",
            "language_model.model.decoder.embed_tokens.weight",
            "language_model.lm_head.weight",
        ]
        if _shared_key in state_dict:
            for _tk in _tied_keys:
                if _tk not in state_dict:
                    state_dict[_tk] = state_dict[_shared_key]

        # Load our dequantized weights
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing:
            print(f"[Florence] Warning: {len(missing)} missing keys "
                  f"(first 5: {missing[:5]})", file=sys.stderr)
        if unexpected:
            print(f"[Florence] Warning: {len(unexpected)} unexpected keys "
                  f"(first 5: {unexpected[:5]})", file=sys.stderr)

        # Free state_dict memory before moving to device
        del state_dict

        # Move to target device and set eval mode
        model = model.to(device)
        model.eval()

        # Apply prepare_inputs_for_generation monkey-patch for newer
        # transformers versions (matches it_cortex_interior.py)
        try:
            lang_model = model.language_model
            _orig_prep = lang_model.prepare_inputs_for_generation

            def _patched_prep(input_ids, past_key_values=None, **kwargs):
                if past_key_values is not None:
                    try:
                        if past_key_values[0] is None or past_key_values[0][0] is None:
                            past_key_values = None
                    except (IndexError, TypeError):
                        past_key_values = None
                return _orig_prep(input_ids, past_key_values=past_key_values, **kwargs)

            lang_model.prepare_inputs_for_generation = _patched_prep
        except AttributeError:
            pass

    except Exception as exc:
        print(f"[Florence] Failed to create model from state_dict: {exc}",
              file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return (None, None)

    # ------------------------------------------------------------------
    # 8. Load processor (tokenizer + image processor)
    # ------------------------------------------------------------------
    try:
        processor = AutoProcessor.from_pretrained(
            _MODEL_ID, trust_remote_code=True
        )
    except Exception as exc:
        print(f"[Florence] Failed to load processor: {exc}", file=sys.stderr)
        return (None, None)

    # ------------------------------------------------------------------
    # 9. Report timing
    # ------------------------------------------------------------------
    total_time = time.time() - t0
    vram_info = ""
    if device == "cuda":
        try:
            vram_mb = round(torch.cuda.memory_allocated() / 1024 / 1024)
            vram_info = f", VRAM: {vram_mb}MB"
        except Exception:
            pass

    file_mb = round(os.path.getsize(manifold_path) / (1024 * 1024), 1)
    print(f"[Florence] Loaded from manifold in {total_time:.1f}s "
          f"({num_tensors} tensors, {file_mb}MB file, {device}{vram_info})")

    return (model, processor)


# ---------------------------------------------------------------------------
# CLI: benchmark / self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Florence Manifold Loader — Benchmark")
    print("=" * 60)
    print(f"Default manifold path: {_DEFAULT_MANIFOLD_PATH}")
    print(f"Manifold exists: {florence_manifold_exists()}")
    print()

    # Show manifold info without loading
    info = get_florence_manifold_info()
    if info:
        print("Manifold info:")
        for k, v in info.items():
            print(f"  {k}: {v}")
        print()
    else:
        print("No valid manifold found — run florence_to_helix.py first")
        sys.exit(1)

    # Benchmark: load model
    if "--load" in sys.argv or "--benchmark" in sys.argv:
        print("Loading model from manifold...")
        t_start = time.time()
        model, processor = load_florence_from_manifold()
        t_end = time.time()

        if model is None:
            print("Load FAILED")
            sys.exit(1)

        print()
        print("Model summary:")
        print(f"  Type:       {type(model).__name__}")
        print(f"  Processor:  {type(processor).__name__}")
        param_count = sum(p.numel() for p in model.parameters())
        param_mb = round(param_count * 2 / (1024 * 1024), 1)  # assume fp16
        print(f"  Parameters: {param_count:,} ({param_mb}MB at fp16)")
        print(f"  Device:     {next(model.parameters()).device}")
        print(f"  Dtype:      {next(model.parameters()).dtype}")
        print(f"  Total time: {t_end - t_start:.2f}s")

        if torch.cuda.is_available():
            vram = round(torch.cuda.memory_allocated() / 1024 / 1024)
            print(f"  VRAM used:  {vram}MB")

        print()
        print("OK")
    else:
        print("Pass --load or --benchmark to actually load the model.")
