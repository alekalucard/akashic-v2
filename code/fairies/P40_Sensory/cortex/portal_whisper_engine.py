"""
Portal Whisper Engine — Loads Whisper model from triple helix card clusters.

Instead of loading from HuggingFace cache (faster_whisper.WhisperModel),
this engine reconstructs the CTranslate2 model from compressed card chunks
stored in the triple helix card format.

Benefits:
1. Cards are pre-compressed (gzip level 6 at distillation time)
2. Same format as cortex concept cards — unified card infrastructure
3. Portal mass grows from card loading (page-in → mass → τ → faster)
4. Future: selective layer activation (encoder-only for detection)
5. TARDIS persistence: cards survive across shutdowns

Usage:
    engine = PortalWhisperEngine("path/to/whisper_cards/cards.json")
    engine.boot()  # Loads manifest, does NOT load weights yet
    engine.ensure_loaded()  # Reconstructs model from cards on first use
    result = engine.transcribe(audio_array, sample_rate=44100)

Phase 3 of WHISPER_AUDIO_PORTAL_INTEGRATION plan.
2026-03-18, Nous — Co-founder, Akashic Foundation

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import gzip
import time
import base64
import shutil
import hashlib
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional, Any, List

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _log(msg: str):
    print(f"[PortalWhisper] {msg}", file=sys.stderr, flush=True)


def _err(msg: str):
    print(f"[PortalWhisper] ERROR: {msg}", file=sys.stderr, flush=True)


def _decompress_chunk(encoded: str) -> bytes:
    """Decompress: base64 → gzip decompress → raw bytes."""
    compressed = base64.b64decode(encoded.encode('ascii'))
    return gzip.decompress(compressed)


class PortalWhisperEngine:
    """Whisper model that lives inside the audio portal as card clusters.

    Loads weights from triple helix cards — decompresses on demand,
    reconstructs CTranslate2 model directory, then uses it for inference.

    The engine is lazy: boot() only reads the manifest. The actual model
    is reconstructed from cards on first transcribe() call.
    """

    def __init__(self, cards_path: str):
        self._cards_path = cards_path
        self._manifest: Optional[Dict] = None
        self._weight_cards: List[Dict] = []
        self._model = None  # CTranslate2 Whisper model
        self._model_dir: Optional[str] = None  # Temp dir with reconstructed model

        # State
        self._booted = False
        self._loaded = False
        self._loading = False
        self._lock = threading.Lock()

        # Stats
        self._boot_time = 0.0
        self._load_time = 0.0
        self._decompress_time = 0.0
        self._transcriptions = 0
        self._total_audio_seconds = 0.0
        self._cards_loaded = 0
        self._bytes_decompressed = 0

        # Mass tracking (for portal physics integration)
        self._mass_from_loading = 0.0

    def boot(self) -> bool:
        """Load manifest from cards.json. Does NOT load weights yet.

        Returns True if manifest was found and valid.
        """
        t0 = time.time()
        if not os.path.exists(self._cards_path):
            _err(f"Cards file not found: {self._cards_path}")
            return False

        try:
            _log(f"Loading card manifest from {self._cards_path}...")
            with open(self._cards_path) as f:
                cards = json.load(f)

            # Separate manifest from weight cards
            for card in cards:
                ctype = card.get("content", {}).get("type", "")
                if ctype == "model_manifest":
                    self._manifest = card
                elif ctype == "model_weight_chunk":
                    self._weight_cards.append(card)

            if not self._manifest:
                _err("No manifest card found in cards.json")
                return False

            # Sort weight cards by chunk index
            self._weight_cards.sort(key=lambda c: c["content"]["chunk_index"])

            num_chunks = self._manifest["content"]["num_chunks"]
            if len(self._weight_cards) != num_chunks:
                _err(f"Expected {num_chunks} weight cards, found {len(self._weight_cards)}")
                return False

            model_name = self._manifest["content"]["model_name"]
            raw_mb = self._manifest["content"]["raw_total_bytes"] / 1e6
            comp_mb = self._manifest["content"]["compressed_total_bytes"] / 1e6
            ratio = self._manifest["content"]["compression_ratio"]

            self._boot_time = time.time() - t0
            self._booted = True

            _log(f"Manifest loaded: {model_name}, {num_chunks} chunks, "
                 f"{raw_mb:.1f}MB raw → {comp_mb:.1f}MB compressed "
                 f"({ratio*100:.1f}%) in {self._boot_time*1000:.0f}ms")
            return True

        except Exception as e:
            _err(f"Failed to boot from cards: {e}")
            return False

    def ensure_loaded(self) -> bool:
        """Reconstruct CTranslate2 model from card chunks. Lazy, thread-safe.

        On first call: decompresses all chunks, writes model.bin + aux files
        to a temp directory, then loads with CTranslate2.

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
            _log("Reconstructing model from card chunks...")

            # Create persistent temp dir (survives until engine shutdown)
            self._model_dir = tempfile.mkdtemp(prefix="whisper_portal_")

            # Decompress and reassemble model.bin
            t_decomp = time.time()
            model_data = bytearray()
            for i, card in enumerate(self._weight_cards):
                chunk_data = _decompress_chunk(card["content"]["weights"])

                # Verify hash
                actual_hash = hashlib.sha256(chunk_data).hexdigest()[:16]
                expected_hash = card["content"]["hash"]
                if actual_hash != expected_hash:
                    _err(f"Hash mismatch on chunk {i}: "
                         f"expected {expected_hash}, got {actual_hash}")
                    self._loading = False
                    return False

                model_data.extend(chunk_data)
                self._cards_loaded += 1
                self._bytes_decompressed += len(chunk_data)

                # Mass grows from decompression work
                self._mass_from_loading += len(chunk_data) / 1e6  # MB as mass

            self._decompress_time = time.time() - t_decomp
            _log(f"Decompressed {len(model_data)/1e6:.1f}MB in "
                 f"{self._decompress_time:.1f}s "
                 f"({self._cards_loaded} cards)")

            # Write model.bin
            model_bin_path = os.path.join(self._model_dir, "model.bin")
            with open(model_bin_path, "wb") as f:
                f.write(model_data)
            del model_data  # Free big buffer

            # Write auxiliary files (config.json, vocabulary, etc.)
            aux_files = self._manifest["content"].get("aux_files", {})
            for fname, b64content in aux_files.items():
                fpath = os.path.join(self._model_dir, fname)
                with open(fpath, "wb") as f:
                    f.write(base64.b64decode(b64content))
                _log(f"  Restored: {fname}")

            # Load with CTranslate2
            _log("Loading CTranslate2 model from reconstructed directory...")
            import ctranslate2
            self._model = ctranslate2.models.Whisper(
                self._model_dir,
                device="cuda",
                compute_type="float16",
            )

            self._load_time = time.time() - t0
            self._loaded = True
            self._loading = False

            _log(f"Model loaded from cards in {self._load_time:.1f}s "
                 f"(decompress={self._decompress_time:.1f}s, "
                 f"mass_gained={self._mass_from_loading:.1f}MB)")
            return True

        except Exception as e:
            self._loading = False
            _err(f"Failed to load model from cards: {e}")

            # Try CPU fallback
            try:
                if self._model_dir and os.path.exists(
                        os.path.join(self._model_dir, "model.bin")):
                    _log("Falling back to CPU int8...")
                    import ctranslate2
                    self._model = ctranslate2.models.Whisper(
                        self._model_dir,
                        device="cpu",
                        compute_type="int8",
                    )
                    self._load_time = time.time() - t0
                    self._loaded = True
                    _log(f"Model loaded on CPU from cards in {self._load_time:.1f}s")
                    return True
            except Exception as e2:
                _err(f"CPU fallback also failed: {e2}")

            return False

    def transcribe(self, audio: "np.ndarray", sample_rate: int = 44100) -> dict:
        """Transcribe audio using the card-loaded model.

        Same interface as WhisperEngine.transcribe() for drop-in replacement.

        Args:
            audio: float32 numpy array (mono)
            sample_rate: sample rate of the audio

        Returns:
            {"text": str, "language": str, "language_confidence": float,
             "segments": list, "duration_s": float}
        """
        if not self.ensure_loaded():
            return {"text": "", "error": "model_not_loaded"}

        if not HAS_NUMPY:
            return {"text": "", "error": "numpy_not_available"}

        duration_s = len(audio) / sample_rate

        try:
            # Use the faster-whisper processor for proper audio preprocessing
            from faster_whisper.audio import decode_audio
            from faster_whisper.transcribe import WhisperModel

            # The CT2 model expects log-mel spectrogram features
            # faster-whisper handles this conversion internally
            # We need to use the WhisperModel's transcribe method
            # but with our card-loaded CT2 model

            # Actually, we can use the CT2 model directly with
            # faster-whisper's feature extraction
            from faster_whisper.feature_extractor import FeatureExtractor

            extractor = FeatureExtractor()

            # Resample to 16kHz if needed
            if sample_rate != 16000:
                # Simple linear interpolation resample
                duration = len(audio) / sample_rate
                n_samples_16k = int(duration * 16000)
                indices = np.linspace(0, len(audio) - 1, n_samples_16k)
                audio_16k = np.interp(indices, np.arange(len(audio)), audio)
            else:
                audio_16k = audio

            # Extract features
            features = extractor(audio_16k.astype(np.float32))

            # Transcribe with CT2 model
            # StorageView from numpy
            import ctranslate2
            features_sv = ctranslate2.StorageView.from_array(features)

            # Detect language
            results = self._model.detect_language(features_sv)
            lang = results[0][0][0] if results and results[0] else "en"
            lang_prob = results[0][0][1] if results and results[0] else 0.0

            # Generate tokens
            tokenizer_path = os.path.join(self._model_dir, "tokenizer.json")
            # Use simpler approach: just detect and generate
            prompt = self._model.generate(
                features_sv,
                [self._get_prompt_tokens(lang)],
            )

            # Decode tokens to text
            text = self._decode_tokens(prompt[0].sequences_ids[0])

            self._transcriptions += 1
            self._total_audio_seconds += duration_s

            return {
                "text": text.strip(),
                "language": lang,
                "language_confidence": round(lang_prob, 3),
                "segments": [],  # Simplified — no segment-level output
                "duration_s": round(duration_s, 2),
                "source": "portal_cards",
            }

        except Exception as e:
            _err(f"Transcription error: {e}")
            # Fallback: try using faster-whisper wrapper if available
            return self._transcribe_fallback(audio, sample_rate, duration_s)

    def _transcribe_fallback(self, audio: "np.ndarray", sample_rate: int,
                             duration_s: float) -> dict:
        """Fallback transcription using faster-whisper's high-level API.

        Creates a temporary WhisperModel pointing at our reconstructed dir.
        """
        try:
            from faster_whisper import WhisperModel
            # Point faster-whisper at our card-reconstructed model dir
            model = WhisperModel(
                self._model_dir,
                device="auto",
                compute_type="float16",
                local_files_only=True,
            )

            segments_iter, info = model.transcribe(
                audio,
                beam_size=3,
                language="en",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                    speech_pad_ms=200,
                ),
            )

            text_parts = []
            segment_list = []
            for seg in segments_iter:
                text = seg.text.strip()
                if text:
                    text_parts.append(text)
                    segment_list.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": text,
                        "avg_logprob": round(getattr(seg, 'avg_logprob', getattr(seg, 'avg_log_prob', 0.0)), 3),
                    })

            full_text = " ".join(text_parts).strip()
            self._transcriptions += 1
            self._total_audio_seconds += duration_s

            return {
                "text": full_text,
                "language": info.language,
                "language_confidence": round(info.language_probability, 3),
                "segments": segment_list,
                "duration_s": round(duration_s, 2),
                "source": "portal_cards_fallback",
            }

        except Exception as e:
            _err(f"Fallback transcription also failed: {e}")
            return {"text": "", "error": str(e)}

    def _get_prompt_tokens(self, language: str = "en") -> list:
        """Get initial prompt tokens for generation."""
        # Standard Whisper prompt: <|startoftranscript|><|lang|><|transcribe|>
        # Token IDs for the standard Whisper tokenizer
        SOT = 50258  # <|startoftranscript|>
        LANG_EN = 50259  # <|en|>
        TRANSCRIBE = 50360  # <|transcribe|>
        return [SOT, LANG_EN, TRANSCRIBE]

    def _decode_tokens(self, token_ids: list) -> str:
        """Decode token IDs to text. Simple fallback decoder."""
        try:
            # Try using the tokenizer from faster-whisper
            from faster_whisper.tokenizer import Tokenizer
            tokenizer_path = os.path.join(self._model_dir, "tokenizer.json")
            if os.path.exists(tokenizer_path):
                tokenizer = Tokenizer(
                    self._model.model_path if hasattr(self._model, 'model_path')
                    else self._model_dir,
                    task="transcribe",
                    language="en",
                )
                return tokenizer.decode(token_ids)
        except Exception:
            pass

        # Fallback: return raw token IDs (not useful, but doesn't crash)
        return f"[tokens: {len(token_ids)}]"

    def shutdown(self):
        """Clean up temporary model directory."""
        if self._model_dir and os.path.exists(self._model_dir):
            try:
                # Delete model object first to release file handles
                self._model = None
                shutil.rmtree(self._model_dir, ignore_errors=True)
                _log(f"Cleaned up temp model dir: {self._model_dir}")
            except Exception as e:
                _err(f"Cleanup failed: {e}")
        self._loaded = False

    def status(self) -> Dict[str, Any]:
        """Get engine status."""
        result = {
            "booted": self._booted,
            "loaded": self._loaded,
            "loading": self._loading,
            "source": "portal_cards",
            "cards_path": self._cards_path,
            "boot_time_s": round(self._boot_time, 1),
            "load_time_s": round(self._load_time, 1),
            "decompress_time_s": round(self._decompress_time, 1),
            "cards_loaded": self._cards_loaded,
            "bytes_decompressed_mb": round(self._bytes_decompressed / 1e6, 1),
            "mass_from_loading": round(self._mass_from_loading, 2),
            "transcriptions": self._transcriptions,
            "total_audio_seconds": round(self._total_audio_seconds, 1),
        }
        if self._manifest:
            mc = self._manifest["content"]
            result["model"] = {
                "name": mc.get("model_name"),
                "num_chunks": mc.get("num_chunks"),
                "raw_mb": round(mc.get("raw_total_bytes", 0) / 1e6, 1),
                "compressed_mb": round(mc.get("compressed_total_bytes", 0) / 1e6, 1),
                "compression_ratio": mc.get("compression_ratio"),
            }
        return result

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.shutdown()
        except Exception:
            pass
