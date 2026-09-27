"""
Portal Canary Engine — Canary-1b-flash from audio.manifold via mmap.

The manifold IS the data. mmap maps the file into virtual address space;
the OS pages in 4KB at a time — only touched pages enter RAM. No f.read(),
no Python buffer objects, no 1GB heap allocations.

Boot reads the header + tensor index from mmap (fast, ~1ms).
ensure_loaded() creates the NeMo model, then replaces weights ONE AT A TIME
from mmap slices — peak RAM = model size only (~1GB), not model + state_dict.

Coordinate cards (cards.json) are ~50 byte addresses for SRM recall.
This engine reads the manifold directly; it doesn't need cards at runtime.

Portal mass grows from manifold file size (page-in -> mass -> t -> faster).

Usage:
    engine = PortalCanaryEngine("path/to/audio.manifold")
    engine.boot()  # mmap manifold, read header + tensor index
    engine.ensure_loaded()  # Create model, load weights from mmap per-tensor
    result = engine.transcribe("path/to/audio.wav")

2026-03-20, Nous — Co-founder, Akashic Foundation
2026-03-23, Nous+Ace — Rewritten: mmap not RAM. Manifold IS the memory.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import struct
import time
import mmap
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional, Any, List


def _log(msg: str):
    print(f"[PortalCanary] {msg}", file=sys.stderr, flush=True)


def _err(msg: str):
    print(f"[PortalCanary] ERROR: {msg}", file=sys.stderr, flush=True)


# ── Manifold binary format constants (matches florence_to_helix.py) ──────────

HEADER_SIZE = 4096
MAGIC = b"AUDM"  # Audio Manifold
TENSOR_ENTRY_SIZE = 304
TENSOR_ENTRY_STRUCT = struct.Struct("<256s I 4I I f f Q Q")

DTYPE_NAMES = {0: "float16", 1: "float32", 2: "bfloat16"}


class PortalCanaryEngine:
    """Canary-1b-flash model loaded directly from audio.manifold via mmap.

    The manifold contains uint8 quantized tensors with per-tensor
    affine scaling (scale + zero_point). The engine:
    1. boot(): mmap manifold, read header + tensor index (fast, no weights)
    2. ensure_loaded(): create NeMo model, replace weights per-tensor from mmap
    3. transcribe(): run inference

    The engine is lazy: boot() only reads the index via mmap.
    The actual model is reconstructed on first transcribe() call.

    Memory model:
    - boot(): mmap virtual mapping (~0 RSS, OS pages in on demand)
    - ensure_loaded(): model weights (~1GB RSS) — no separate state_dict buffer
    - Per-tensor loading: only one tensor dequantized at a time (~16MB peak)
    - Old approach: state_dict + model = 2-3GB peak. New: ~1GB peak.
    """

    def __init__(self, manifold_path: str, model_prefix: str = "canary"):
        self._manifold_path = manifold_path
        self._model_prefix = model_prefix
        self._tensor_index: List[Dict] = []  # From manifold header
        self._data_start: int = 0
        self._model = None  # NeMo EncDecMultiTaskModel
        self._temp_wav: Optional[str] = None

        # mmap state — kept alive for engine lifetime
        self._mm_file = None   # Open file handle (must outlive mmap)
        self._mm = None        # mmap object (READ-ONLY)

        # State
        self._booted = False
        self._loaded = False
        self._loading = False
        self._lock = threading.Lock()

        # Stats
        self._boot_time = 0.0
        self._load_time = 0.0
        self._transcriptions = 0
        self._total_audio_seconds = 0.0
        self._tensors_loaded = 0
        self._bytes_paged = 0  # Bytes accessed via mmap (not "read" — OS manages paging)

        # Mass tracking (for portal physics integration)
        self._mass_from_loading = 0.0

    # ═══════════════════════════════════════════════════════════════════
    # BOOT — mmap manifold, read header + tensor index
    # ═══════════════════════════════════════════════════════════════════

    def boot(self) -> bool:
        """mmap the manifold and read header + tensor index.

        Does NOT load weights. The mmap is READ-ONLY; the OS pages in
        4KB at a time as we access header/index bytes. After boot(),
        only the index entries (~100 bytes each) are in Python heap.
        The manifold data stays on disk until ensure_loaded() touches it.

        Returns True if manifold was found, valid, and has canary/ tensors.
        """
        t0 = time.time()
        if not os.path.exists(self._manifold_path):
            _err(f"Manifold not found: {self._manifold_path}")
            return False

        try:
            file_size = os.path.getsize(self._manifold_path)
            _log(f"mmap manifold: {self._manifold_path} "
                 f"({file_size / (1024**2):.1f} MB)")

            # ── mmap the entire file (READ-ONLY) ──
            # The OS pages in data on demand — only accessed pages enter RAM.
            # mmap(fileno, 0) = map entire file. ACCESS_READ = read-only.
            self._mm_file = open(self._manifold_path, "rb")
            self._mm = mmap.mmap(
                self._mm_file.fileno(), 0, access=mmap.ACCESS_READ
            )

            # ── Read header from mmap (direct slice, no f.read) ──
            header = self._mm[0:HEADER_SIZE]
            magic = header[0:4]
            if magic != MAGIC:
                _err(f"Bad magic: {magic} (expected {MAGIC})")
                self._close_mmap()
                return False

            version = struct.unpack_from("<I", header, 4)[0]
            num_tensors = struct.unpack_from("<I", header, 8)[0]
            self._data_start = struct.unpack_from("<Q", header, 32)[0]

            _log(f"Manifold v{version}: {num_tensors} tensors, "
                 f"data starts at {self._data_start}")

            # ── Read tensor index from mmap ──
            prefix = f"{self._model_prefix}/"
            for i in range(num_tensors):
                offset = HEADER_SIZE + i * TENSOR_ENTRY_SIZE
                raw = self._mm[offset:offset + TENSOR_ENTRY_SIZE]
                parsed = TENSOR_ENTRY_STRUCT.unpack(raw)

                full_name = parsed[0].rstrip(b"\x00").decode("utf-8")

                # Only index tensors for our model prefix
                if not full_name.startswith(prefix):
                    continue

                ndim = parsed[1]
                shape = list(parsed[2:6])[:ndim]
                dtype_code = parsed[6]
                scale = parsed[7]
                zero_point = parsed[8]
                data_offset = parsed[9]
                data_size = parsed[10]

                # Strip prefix for state_dict key
                tensor_name = full_name[len(prefix):]

                self._tensor_index.append({
                    "name": tensor_name,
                    "full_name": full_name,
                    "shape": shape,
                    "ndim": ndim,
                    "dtype_code": dtype_code,
                    "dtype": DTYPE_NAMES.get(dtype_code, "float32"),
                    "scale": scale,
                    "zero_point": zero_point,
                    "data_offset": data_offset,
                    "data_size": data_size,
                })

            if not self._tensor_index:
                _err(f"No tensors with prefix '{self._model_prefix}/' in manifold")
                self._close_mmap()
                return False

            self._boot_time = time.time() - t0
            self._booted = True

            # Mass from manifold file size
            self._mass_from_loading = file_size / 1e6  # MB as mass units

            _log(f"Booted: {len(self._tensor_index)} tensors "
                 f"(prefix: {self._model_prefix}/), "
                 f"{self._boot_time*1000:.0f}ms, mass={self._mass_from_loading:.1f}")
            return True

        except Exception as e:
            _err(f"Failed to boot from manifold: {e}")
            self._close_mmap()
            return False

    # ═══════════════════════════════════════════════════════════════════
    # ENSURE LOADED — create model, load weights per-tensor from mmap
    # ═══════════════════════════════════════════════════════════════════

    def ensure_loaded(self, device: str = "cuda") -> bool:
        """Create NeMo model and load weights per-tensor from mmap.

        Lazy, thread-safe. On first call:
        1. Import NeMo + create model via from_pretrained (gets architecture)
        2. For each tensor in manifold index:
           a. Read uint8 data from mmap slice (zero-copy, OS pages in)
           b. Dequantize: float32 = uint8 * scale + zero_point
           c. Copy into model parameter (in-place)
           d. Free the temporary — only one tensor in flight at a time
        3. Peak RAM = model size (~1GB), NOT model + full state_dict

        Returns True if model is ready for inference.
        """
        if self._loaded:
            return True

        with self._lock:
            if self._loaded:
                return True
            if self._loading:
                return False
            self._loading = True

        if not self._booted:
            if not self.boot():
                self._loading = False
                return False

        try:
            t0 = time.time()
            _log(f"Loading model from manifold "
                 f"({len(self._tensor_index)} tensors, mmap-backed)...")

            import torch
            import numpy as np

            # ── Create NeMo model shell ──
            # Suppress NeMo noise
            import logging
            for _logger_name in ('nemo', 'pytorch_lightning', 'lightning',
                                 'nemo.utils', 'nemo.collections'):
                logging.getLogger(_logger_name).setLevel(logging.ERROR)

            _t_nemo = time.time()
            from nemo.collections.asr.models import EncDecMultiTaskModel
            _log(f"NeMo import took {time.time() - _t_nemo:.1f}s")

            # Get model architecture from pretrained (cached on disk).
            # This loads weights from HF cache (~1GB). We then replace them
            # per-tensor from the manifold. No separate state_dict allocation.
            _t_pretrained = time.time()
            _log("Creating model from pretrained (HF cache)...")
            self._model = EncDecMultiTaskModel.from_pretrained(
                "nvidia/canary-1b-flash"
            )
            _log(f"from_pretrained took {time.time() - _t_pretrained:.1f}s")

            # ── Replace weights per-tensor from mmap (no state_dict buffer) ──
            _t_replace = time.time()
            model_state = self._model.state_dict()
            replaced = 0
            skipped = 0

            for i, ti in enumerate(self._tensor_index):
                name = ti["name"]

                # Check if this tensor exists in the model
                if name not in model_state:
                    skipped += 1
                    continue

                # Read uint8 data from mmap slice (zero-copy view into file)
                # The OS pages in the relevant 4KB pages — no Python buffer
                data_offset = self._data_start + ti["data_offset"]
                data_size = ti["data_size"]

                # np.frombuffer on mmap slice — zero-copy for uint8 data
                uint8_view = np.frombuffer(
                    self._mm, dtype=np.uint8,
                    count=data_size,
                    offset=data_offset
                )

                # Dequantize: float32 = uint8 * scale + zero_point
                # This creates a temporary float32 array (~4x tensor size)
                float_arr = uint8_view.astype(np.float32) * ti["scale"] + ti["zero_point"]

                # Create torch tensor and reshape
                tensor = torch.from_numpy(float_arr.reshape(ti["shape"]))

                # Cast to original dtype
                if ti["dtype"] == "float16":
                    tensor = tensor.half()
                elif ti["dtype"] == "bfloat16":
                    tensor = tensor.bfloat16()

                # Copy into model parameter IN-PLACE — no separate state_dict
                try:
                    model_state[name].copy_(tensor)
                except RuntimeError:
                    # Shape mismatch — fall back to direct assignment
                    # This shouldn't happen with a correct manifold
                    _log(f"  WARN: shape mismatch for {name}, "
                         f"model={list(model_state[name].shape)} "
                         f"manifold={ti['shape']}")
                    skipped += 1
                    continue

                # Free the temporary — only one tensor in flight
                del tensor, float_arr

                replaced += 1
                self._tensors_loaded += 1
                self._bytes_paged += data_size

                if (i + 1) % 200 == 0:
                    _log(f"  [{i+1}/{len(self._tensor_index)}] tensors replaced...")

            _log(f"Weights replaced: {replaced} tensors from mmap, "
                 f"{skipped} skipped, "
                 f"{self._bytes_paged / (1024**2):.1f} MB paged, "
                 f"{time.time() - _t_replace:.1f}s")

            # Move to device
            if device == "cuda" and torch.cuda.is_available():
                self._model = self._model.cuda()
            self._model.eval()

            # Set beam_size=1 for greedy (fast)
            decode_cfg = self._model.cfg.decoding
            decode_cfg.beam.beam_size = 1
            self._model.change_decoding_strategy(decode_cfg)

            # Temp file for transcription (Canary needs file paths)
            _temp_dir = tempfile.mkdtemp(prefix="canary_portal_")
            self._temp_wav = os.path.join(_temp_dir, "utterance.wav")

            self._load_time = time.time() - t0
            self._loaded = True
            self._loading = False

            _log(f"Model ready in {self._load_time:.1f}s "
                 f"({self._tensors_loaded} tensors from mmap, "
                 f"peak RAM ≈ model only, "
                 f"mass={self._mass_from_loading:.1f}MB)")
            return True

        except Exception as e:
            self._loading = False
            _err(f"Failed to load model from manifold: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False

    # ═══════════════════════════════════════════════════════════════════
    # TRANSCRIPTION
    # ═══════════════════════════════════════════════════════════════════

    def transcribe(self, audio_path: str) -> dict:
        """Transcribe audio file using the manifold-loaded model.

        Args:
            audio_path: Path to WAV file (16kHz mono)

        Returns:
            {"text": str, "duration_s": float, "source": "audio_manifold"}
        """
        if not self.ensure_loaded():
            return {"text": "", "error": "model_not_loaded"}

        try:
            import torch

            with torch.no_grad():
                output = self._model.transcribe(
                    [audio_path],
                    batch_size=1,
                    pnc='yes',
                    source_lang='en',
                    target_lang='en',
                )

            if output and len(output) > 0:
                text = output[0].text if hasattr(output[0], 'text') else str(output[0])
                text = text.strip()
            else:
                text = ""

            self._transcriptions += 1

            return {
                "text": text,
                "source": "audio_manifold",
            }

        except Exception as e:
            _err(f"Transcription error: {e}")
            return {"text": "", "error": str(e)}

    def transcribe_array(self, audio_np, sample_rate: int = 16000) -> dict:
        """Transcribe numpy audio array.

        Writes to temp WAV (Canary requires file paths), then transcribes.
        """
        _log(f"transcribe_array: loaded={self._loaded}, loading={self._loading}")
        if not self.ensure_loaded():
            _log(f"transcribe_array: ensure_loaded returned False "
                 f"(loading={self._loading}, loaded={self._loaded})")
            return {"text": "", "error": "model_not_loaded"}

        try:
            import soundfile as sf
            import numpy as np

            # Resample if needed
            if sample_rate != 16000:
                import scipy.signal
                audio_16k = scipy.signal.resample(
                    audio_np,
                    int(len(audio_np) * 16000 / sample_rate)
                ).astype(np.float32)
            else:
                audio_16k = audio_np

            # Normalize
            peak = np.abs(audio_16k).max()
            if peak > 0:
                audio_16k = audio_16k / peak * 0.9

            # Write temp WAV
            sf.write(self._temp_wav, audio_16k, 16000)

            return self.transcribe(self._temp_wav)

        except Exception as e:
            _err(f"Array transcription error: {e}")
            return {"text": "", "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════

    def _close_mmap(self):
        """Close mmap and file handle. Safe to call multiple times."""
        if self._mm is not None:
            try:
                self._mm.close()
            except Exception:
                pass
            self._mm = None
        if self._mm_file is not None:
            try:
                self._mm_file.close()
            except Exception:
                pass
            self._mm_file = None

    def shutdown(self):
        """Clean up: release model, close mmap, remove temp files."""
        # Release model
        self._model = None
        self._loaded = False

        # Close mmap
        self._close_mmap()
        self._booted = False

        # Clean temp files
        if self._temp_wav:
            _temp_dir = os.path.dirname(self._temp_wav)
            try:
                import shutil
                shutil.rmtree(_temp_dir, ignore_errors=True)
                _log(f"Cleaned up temp dir: {_temp_dir}")
            except Exception:
                pass
            self._temp_wav = None

    def status(self) -> Dict[str, Any]:
        """Get engine status."""
        result = {
            "booted": self._booted,
            "loaded": self._loaded,
            "loading": self._loading,
            "source": "audio_manifold_mmap",
            "manifold_path": self._manifold_path,
            "model_prefix": self._model_prefix,
            "boot_time_s": round(self._boot_time, 1),
            "load_time_s": round(self._load_time, 1),
            "tensors_indexed": len(self._tensor_index),
            "tensors_loaded": self._tensors_loaded,
            "bytes_paged_mb": round(self._bytes_paged / 1e6, 1),
            "mass_from_loading": round(self._mass_from_loading, 2),
            "transcriptions": self._transcriptions,
            "total_audio_seconds": round(self._total_audio_seconds, 1),
            "mmap_active": self._mm is not None,
        }
        return result

    @staticmethod
    def reconstruct_state_dict_from_recall(
        manifold_path: str,
        reconstruction: Dict[str, Any],
        data_start: int = None,
    ) -> Dict:
        """Reconstruct a PyTorch state_dict from SRMRecallFairy recall results.

        This completes the möbius strip:
            IngestFairy → coordinate cards → SRMRecallFairy → recall_manifold_model()
            → reconstruction map → this method → state_dict → live model

        Uses mmap for zero-copy tensor reads.

        Args:
            manifold_path: Path to audio.manifold file
            reconstruction: Dict from SRMRecallFairy.recall_manifold_model()["reconstruction"]
                           Maps "canary/tensor_name" → {offset, size, shape, dtype, scale, zero_point}
            data_start: Byte offset where tensor data begins in manifold.
                        If None, reads from manifold header.

        Returns:
            PyTorch state_dict (tensor_name → Tensor), stripping model prefix
        """
        import numpy as np

        # Read data_start from header if not provided
        if data_start is None:
            with open(manifold_path, "rb") as f:
                header_bytes = f.read(HEADER_SIZE)
                data_start = struct.unpack_from("<Q", header_bytes, 32)[0]

        state_dict = {}

        # Use mmap for zero-copy reads
        with open(manifold_path, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                for full_name, info in reconstruction.items():
                    # Strip prefix: "canary/encoder.layers.0.weight" → "encoder.layers.0.weight"
                    tensor_name = full_name.split("/", 1)[1] if "/" in full_name else full_name

                    # Zero-copy uint8 view from mmap
                    uint8_view = np.frombuffer(
                        mm, dtype=np.uint8,
                        count=info["size"],
                        offset=data_start + info["offset"]
                    )

                    # Dequantize: float32 = uint8 * scale + zero_point
                    float_arr = uint8_view.astype(np.float32) * info["scale"] + info["zero_point"]

                    import torch
                    tensor = torch.from_numpy(float_arr.reshape(info["shape"]))

                    if info["dtype"] == "float16":
                        tensor = tensor.half()
                    elif info["dtype"] == "bfloat16":
                        tensor = tensor.bfloat16()

                    state_dict[tensor_name] = tensor

            finally:
                mm.close()

        _log(f"Reconstructed {len(state_dict)} tensors from SRM recall (mmap)")
        return state_dict

    @property
    def mass(self) -> float:
        """Current mass from manifold loading (for portal physics)."""
        return self._mass_from_loading

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass
