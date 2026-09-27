# ═══════════════════════════════════════════════════════════════════════════════════════════
# TARDIS VOCODERS - Neural Audio Reconstruction
# ═══════════════════════════════════════════════════════════════════════════════════════════
#
# Multiple backends for mel spectrogram -> audio reconstruction:
#   1. Griffin-Lim (fast, decent quality, CPU)
#   2. Griffin-Lim GPU (torchaudio, faster)
#   3. HiFi-GAN (neural, highest quality)
#
# "The best vocoder is the one that sounds like it was never encoded."
# ═══════════════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Literal
import numpy as np

# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Vocoder models cache
VOCODER_CACHE = PROJECT_ROOT / "state" / "models" / "vocoders"
VOCODER_CACHE.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# VOCODER BACKENDS
# ═══════════════════════════════════════════════════════════════════════════════════════════

VocoderBackend = Literal["griffin_lim", "griffin_lim_gpu", "hifigan"]


class VocoderBase:
    """Base class for vocoders."""

    name: str = "base"
    quality: int = 0  # 0-10 quality rating
    requires_gpu: bool = False

    def mel_to_audio(self, mel_spec: np.ndarray, sr: int = 22050,
                     hop_length: int = 512, n_fft: int = 2048) -> np.ndarray:
        """Convert mel spectrogram to audio waveform."""
        raise NotImplementedError


class GriffinLimVocoder(VocoderBase):
    """
    Griffin-Lim algorithm - iterative phase reconstruction.

    Fast CPU-based vocoder. Quality depends on iterations.
    Works with any mel spectrogram without training.
    """

    name = "griffin_lim"
    quality = 6
    requires_gpu = False

    def __init__(self, n_iter: int = 64):
        self.n_iter = n_iter
        self._init_librosa()

    def _init_librosa(self):
        try:
            import librosa
            self.librosa = librosa
            self.available = True
        except ImportError:
            self.available = False
            print("[Vocoder] Griffin-Lim unavailable: librosa not installed")

    def mel_to_audio(self, mel_spec: np.ndarray, sr: int = 22050,
                     hop_length: int = 512, n_fft: int = 2048) -> np.ndarray:
        """Reconstruct audio using Griffin-Lim."""
        if not self.available:
            raise RuntimeError("librosa not available")

        # mel_spec should be in dB scale, convert to power
        mel_power = self.librosa.db_to_power(mel_spec.astype(np.float32))

        # Invert mel spectrogram to audio
        audio = self.librosa.feature.inverse.mel_to_audio(
            mel_power, sr=sr, hop_length=hop_length, n_fft=n_fft, n_iter=self.n_iter
        )

        return audio


class GriffinLimGPUVocoder(VocoderBase):
    """
    GPU-accelerated Griffin-Lim using torchaudio.

    Faster than CPU Griffin-Lim, same algorithm.
    """

    name = "griffin_lim_gpu"
    quality = 6
    requires_gpu = True

    def __init__(self, n_iter: int = 64):
        self.n_iter = n_iter
        self._init_torch()

    def _init_torch(self):
        try:
            import torch
            import torchaudio
            self.torch = torch
            self.torchaudio = torchaudio
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.available = True

            if self.device == "cpu":
                print("[Vocoder] Griffin-Lim GPU: CUDA not available, using CPU")
        except ImportError:
            self.available = False
            print("[Vocoder] Griffin-Lim GPU unavailable: torchaudio not installed")

    def mel_to_audio(self, mel_spec: np.ndarray, sr: int = 22050,
                     hop_length: int = 512, n_fft: int = 2048) -> np.ndarray:
        """Reconstruct audio using torchaudio Griffin-Lim."""
        if not self.available:
            raise RuntimeError("torchaudio not available")

        # Convert mel dB to power
        mel_power = np.power(10.0, mel_spec / 10.0)

        # Create inverse mel filter bank
        n_mels = mel_spec.shape[0]
        mel_basis = self.torchaudio.functional.melscale_fbanks(
            n_freqs=n_fft // 2 + 1,
            f_min=0.0,
            f_max=sr / 2.0,
            n_mels=n_mels,
            sample_rate=sr,
        ).to(self.device)

        # Pseudo-inverse to go from mel to linear spectrogram
        mel_tensor = self.torch.from_numpy(mel_power).float().to(self.device)
        mel_basis_pinv = self.torch.linalg.pinv(mel_basis.T)
        linear_spec = self.torch.matmul(mel_basis_pinv, mel_tensor)
        linear_spec = self.torch.clamp(linear_spec, min=1e-10)

        # Apply Griffin-Lim
        griffinlim = self.torchaudio.transforms.GriffinLim(
            n_fft=n_fft,
            hop_length=hop_length,
            power=1.0,
            n_iter=self.n_iter
        ).to(self.device)

        # Griffin-Lim expects magnitude spectrogram
        magnitude = self.torch.sqrt(linear_spec)
        audio = griffinlim(magnitude)

        return audio.cpu().numpy()


class HiFiGANVocoder(VocoderBase):
    """
    HiFi-GAN neural vocoder - highest quality mel-to-audio.

    Uses a pre-trained generator network to reconstruct audio.
    Much higher quality than Griffin-Lim, especially for speech.

    Reference: https://github.com/jik876/hifi-gan
    """

    name = "hifigan"
    quality = 9
    requires_gpu = True

    def __init__(self, model_name: str = "hifigan_v1"):
        self.model_name = model_name
        self.generator = None
        self._init_model()

    def _init_model(self):
        """Initialize HiFi-GAN model."""
        try:
            import torch
            self.torch = torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

            # Try to load pre-trained HiFi-GAN
            # Option 1: speechbrain has a nice wrapper
            # NOTE: speechbrain 1.0.3 has a bug with huggingface_hub 1.2+ (use_auth_token)
            try:
                from speechbrain.inference.vocoders import HIFIGAN
                self.generator = HIFIGAN.from_hparams(
                    source="speechbrain/tts-hifigan-ljspeech",
                    savedir=str(VOCODER_CACHE / "speechbrain_hifigan")
                )
                self.backend = "speechbrain"
                self.available = True
                print(f"[Vocoder] HiFi-GAN loaded (speechbrain, {self.device})")
                return
            except TypeError as e:
                if "use_auth_token" in str(e):
                    # Known version mismatch - speechbrain needs update
                    pass
            except Exception as e:
                pass

            # Option 2: torchaudio bundle
            try:
                import torchaudio
                bundle = torchaudio.pipelines.HIFIGAN_VOCODER
                self.generator = bundle.get_vocoder().to(self.device)
                self.backend = "torchaudio"
                self.available = True
                print(f"[Vocoder] HiFi-GAN loaded (torchaudio, {self.device})")
                return
            except Exception as e:
                pass

            # Option 3: Manual loading from checkpoint
            # (Would need to download weights)

            self.available = False
            print("[Vocoder] HiFi-GAN unavailable: no backend found")
            print("  Install: pip install speechbrain  OR  torchaudio>=2.0")

        except ImportError:
            self.available = False
            print("[Vocoder] HiFi-GAN unavailable: torch not installed")

    def mel_to_audio(self, mel_spec: np.ndarray, sr: int = 22050,
                     hop_length: int = 512, n_fft: int = 2048) -> np.ndarray:
        """Reconstruct audio using HiFi-GAN."""
        if not self.available:
            raise RuntimeError("HiFi-GAN not available")

        # Normalize mel spectrogram for HiFi-GAN
        # HiFi-GAN typically expects normalized log-mel spectrograms
        mel_tensor = self.torch.from_numpy(mel_spec).float().unsqueeze(0)

        if self.backend == "speechbrain":
            # speechbrain expects (batch, n_mels, time)
            mel_tensor = mel_tensor.to(self.device)
            # Normalize to expected range
            mel_norm = (mel_tensor - mel_tensor.min()) / (mel_tensor.max() - mel_tensor.min() + 1e-8)
            mel_norm = mel_norm * 2 - 1  # Scale to [-1, 1]

            with self.torch.no_grad():
                audio = self.generator.decode_batch(mel_norm.transpose(1, 2))
            return audio.squeeze().cpu().numpy()

        elif self.backend == "torchaudio":
            # torchaudio HiFi-GAN expects (batch, n_mels, time)
            mel_tensor = mel_tensor.to(self.device)

            with self.torch.no_grad():
                audio = self.generator(mel_tensor)
            return audio.squeeze().cpu().numpy()

        else:
            raise RuntimeError(f"Unknown HiFi-GAN backend: {self.backend}")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# VOCODER FACTORY
# ═══════════════════════════════════════════════════════════════════════════════════════════

_vocoder_cache = {}


def get_vocoder(backend: VocoderBackend = "hifigan",
                fallback: bool = True) -> VocoderBase:
    """
    Get a vocoder instance.

    Args:
        backend: Which vocoder to use
        fallback: If preferred backend unavailable, fall back to Griffin-Lim

    Returns:
        Vocoder instance
    """
    global _vocoder_cache

    if backend in _vocoder_cache:
        vocoder = _vocoder_cache[backend]
        if vocoder.available:
            return vocoder

    # Try to create requested vocoder
    if backend == "hifigan":
        vocoder = HiFiGANVocoder()
        if vocoder.available:
            _vocoder_cache[backend] = vocoder
            return vocoder
        elif fallback:
            print("[Vocoder] HiFi-GAN unavailable, falling back to Griffin-Lim GPU")
            return get_vocoder("griffin_lim_gpu", fallback=True)

    elif backend == "griffin_lim_gpu":
        vocoder = GriffinLimGPUVocoder()
        if vocoder.available:
            _vocoder_cache[backend] = vocoder
            return vocoder
        elif fallback:
            print("[Vocoder] Griffin-Lim GPU unavailable, falling back to CPU")
            return get_vocoder("griffin_lim", fallback=False)

    elif backend == "griffin_lim":
        vocoder = GriffinLimVocoder()
        _vocoder_cache[backend] = vocoder
        return vocoder

    raise RuntimeError(f"No vocoder available for backend: {backend}")


def list_vocoders() -> list:
    """List all available vocoders."""
    vocoders = []

    # Check each backend
    for backend in ["hifigan", "griffin_lim_gpu", "griffin_lim"]:
        try:
            v = get_vocoder(backend, fallback=False)
            vocoders.append({
                "name": v.name,
                "quality": v.quality,
                "requires_gpu": v.requires_gpu,
                "available": v.available
            })
        except:
            pass

    return vocoders


def reconstruct_audio(mel_spec: np.ndarray,
                      backend: VocoderBackend = "hifigan",
                      sr: int = 22050,
                      hop_length: int = 512,
                      n_fft: int = 2048) -> np.ndarray:
    """
    High-level audio reconstruction function.

    Automatically picks best available vocoder.
    """
    vocoder = get_vocoder(backend, fallback=True)
    print(f"[Vocoder] Using {vocoder.name} (quality: {vocoder.quality}/10)")
    return vocoder.mel_to_audio(mel_spec, sr=sr, hop_length=hop_length, n_fft=n_fft)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PHASE-AWARE RECONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════════════════

def reconstruct_with_phase(magnitude: np.ndarray, phase: np.ndarray,
                           sr: int = 22050, hop_length: int = 512) -> np.ndarray:
    """
    Reconstruct audio using stored phase information.

    If phase was saved during encoding, this gives PERFECT reconstruction.
    """
    try:
        import librosa

        # Combine magnitude and phase
        stft = magnitude * np.exp(1j * phase)

        # Inverse STFT
        audio = librosa.istft(stft, hop_length=hop_length)
        return audio

    except ImportError:
        raise RuntimeError("librosa required for phase-aware reconstruction")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 60)
    print("TARDIS VOCODERS - Available Backends")
    print("=" * 60)

    vocoders = list_vocoders()
    for v in vocoders:
        status = "✓" if v["available"] else "✗"
        gpu = "GPU" if v["requires_gpu"] else "CPU"
        print(f"  [{status}] {v['name']:20s} Quality: {v['quality']}/10  ({gpu})")

    print()
    print("Best available:", get_vocoder("hifigan", fallback=True).name)
