"""
CochleaFairy - Tonotopic Frequency Decomposition

Plane: P40_Sensory
Mantra: "The membrane sings the frequencies of the world"

Purpose: Simulate the human cochlea's frequency analysis.
         Transform audio waveforms into tonotopic nerve activity.

Biological Basis:
    - Basilar membrane: Mechanical frequency analyzer
    - Inner hair cells (~3,500): Primary transduction
    - Outer hair cells (~12,000): Amplification, level-dependent tuning
    - Tonotopy: High frequencies at base, low at apex

Technical Implementation:
    - Gammatone filterbank (models basilar membrane)
    - Level-dependent bandwidth (louder = broader)
    - Temporal fine structure preservation
    - Neural-style spike activity output
"""

from __future__ import annotations

import os
import sys
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
import time

# Add project root
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("[CochleaFairy] Warning: librosa not available, some features disabled")

try:
    import scipy.signal as signal
    from scipy.io import wavfile
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class CochleaOutput:
    """Output from cochlear processing."""
    tonotopic_activation: np.ndarray  # Shape: (n_channels, time_frames)
    frequency_bands: np.ndarray  # Center frequencies for each channel
    level_estimate_db: float  # Estimated sound level in dB
    temporal_envelope: np.ndarray  # Amplitude envelope
    fine_structure: Optional[np.ndarray] = None  # Phase/timing info
    sample_rate: int = 48000
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tonotopic_shape": list(self.tonotopic_activation.shape),
            "n_channels": len(self.frequency_bands),
            "freq_range": [float(self.frequency_bands[0]), float(self.frequency_bands[-1])],
            "level_db": self.level_estimate_db,
            "sample_rate": self.sample_rate,
            "timestamp": self.timestamp,
        }


@dataclass
class SpectralSeeds:
    """Spectral dimension seeds for memory storage."""
    mel_spectrogram: np.ndarray
    mfcc: np.ndarray  # 40 coefficients
    chroma: np.ndarray  # 12 pitch classes
    spectral_centroid: np.ndarray
    spectral_bandwidth: np.ndarray
    spectral_rolloff: np.ndarray
    spectral_contrast: np.ndarray
    tonnetz: np.ndarray  # Tonal centroid features

    def to_dict(self) -> Dict[str, List]:
        """Convert to JSON-serializable dict (store as lists)."""
        return {
            "mel_shape": list(self.mel_spectrogram.shape),
            "mfcc_mean": self.mfcc.mean(axis=1).tolist(),
            "mfcc_std": self.mfcc.std(axis=1).tolist(),
            "chroma_mean": self.chroma.mean(axis=1).tolist(),
            "centroid_mean": float(self.spectral_centroid.mean()),
            "bandwidth_mean": float(self.spectral_bandwidth.mean()),
            "rolloff_mean": float(self.spectral_rolloff.mean()),
            "contrast_mean": self.spectral_contrast.mean(axis=1).tolist(),
            "tonnetz_mean": self.tonnetz.mean(axis=1).tolist(),
        }


@dataclass
class TemporalSeeds:
    """Temporal dimension seeds for memory storage."""
    zero_crossing_rate: np.ndarray
    rms_energy: np.ndarray
    tempo: float
    beat_frames: np.ndarray
    onset_envelope: np.ndarray
    onset_frames: np.ndarray

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "zcr_mean": float(self.zero_crossing_rate.mean()),
            "rms_mean": float(self.rms_energy.mean()),
            "rms_std": float(self.rms_energy.std()),
            "tempo": self.tempo,
            "n_beats": len(self.beat_frames),
            "n_onsets": len(self.onset_frames),
            "onset_density": len(self.onset_frames) / (len(self.onset_envelope) + 1),
        }


@dataclass
class HarmonicSeeds:
    """Harmonic dimension seeds for memory storage."""
    harmonic: np.ndarray  # Harmonic component
    percussive: np.ndarray  # Percussive component
    f0: np.ndarray  # Fundamental frequency contour
    voiced_flag: np.ndarray  # Whether each frame is voiced

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        h_energy = np.sum(self.harmonic ** 2) if self.harmonic is not None else 0
        p_energy = np.sum(self.percussive ** 2) if self.percussive is not None else 0
        total = h_energy + p_energy + 1e-10

        return {
            "harmonic_ratio": float(h_energy / total),
            "percussive_ratio": float(p_energy / total),
            "f0_mean": float(np.nanmean(self.f0)) if self.f0 is not None else 0,
            "f0_std": float(np.nanstd(self.f0)) if self.f0 is not None else 0,
            "voiced_ratio": float(self.voiced_flag.mean()) if self.voiced_flag is not None else 0,
        }


class CochleaFairy:
    """
    Simulate human cochlear frequency analysis.

    Models the tonotopic organization of the basilar membrane
    using a gammatone filterbank, with level-dependent tuning.
    """

    ACTOR_NAME = "CochleaFairy"
    NEEDS_HEARTBEAT = False  # Passive audio processor, no heartbeat loop
    MANTRA = "The membrane sings the frequencies of the world"
    # FIX 2026-05-11 (Nous + Ace): Option B opt-in (per project_cortex_cluster_per_fairy_option_b_opt_in_shipped.md 2026-05-09).
    # Gives CochleaFairy her own FairySRMCluster on boot so she can accumulate audio-pattern
    # cortex topology. Step toward replacing canary STT with cortex-native STT in cochlea-SRM-cluster.
    USE_SRM_CLUSTER = True

    # Default parameters matching human hearing
    DEFAULT_N_CHANNELS = 128  # Number of frequency channels
    DEFAULT_F_LOW = 20  # Hz (lower limit of hearing)
    DEFAULT_F_HIGH = 20000  # Hz (upper limit of hearing)
    DEFAULT_SAMPLE_RATE = 48000  # High quality audio

    def __init__(self, n_channels: int = DEFAULT_N_CHANNELS,
                 f_low: float = DEFAULT_F_LOW,
                 f_high: float = DEFAULT_F_HIGH,
                 sample_rate: int = DEFAULT_SAMPLE_RATE):
        """
        Initialize the cochlea model.

        Args:
            n_channels: Number of frequency channels (resolution)
            f_low: Lowest frequency in Hz
            f_high: Highest frequency in Hz
            sample_rate: Audio sample rate
        """
        self.n_channels = n_channels
        self.f_low = f_low
        self.f_high = f_high
        self.sample_rate = sample_rate

        # Create frequency bands (ERB scale - matches human perception)
        self.frequency_bands = self._create_erb_frequencies(n_channels, f_low, f_high)

        print(f"[{self.ACTOR_NAME}] Initialized with {n_channels} channels "
              f"({f_low}Hz - {f_high}Hz)")

    def _create_erb_frequencies(self, n_channels: int, f_low: float, f_high: float) -> np.ndarray:
        """
        Create frequency bands on ERB (Equivalent Rectangular Bandwidth) scale.
        This matches human auditory perception better than linear or mel scale.
        """
        # ERB scale conversion
        erb_low = 21.4 * np.log10(4.37 * f_low / 1000 + 1)
        erb_high = 21.4 * np.log10(4.37 * f_high / 1000 + 1)

        # Linear spacing in ERB domain
        erb_points = np.linspace(erb_low, erb_high, n_channels)

        # Convert back to Hz
        frequencies = (10 ** (erb_points / 21.4) - 1) * 1000 / 4.37

        return frequencies

    def _estimate_level_db(self, audio: np.ndarray) -> float:
        """Estimate sound level in dB SPL (approximate)."""
        rms = np.sqrt(np.mean(audio ** 2))
        # Convert to dB (reference: full scale = 0 dB)
        if rms > 0:
            db = 20 * np.log10(rms)
        else:
            db = -100
        return float(db)

    def _gammatone_filterbank(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply gammatone filterbank to audio.

        Gammatone filters model the frequency selectivity of the cochlea.
        """
        if not SCIPY_AVAILABLE:
            # Fallback to simple FFT-based approach
            return self._simple_filterbank(audio)

        n_samples = len(audio)
        output = np.zeros((self.n_channels, n_samples))

        for i, cf in enumerate(self.frequency_bands):
            # Gammatone filter parameters
            erb = 24.7 * (4.37 * cf / 1000 + 1)  # ERB at this frequency
            b = 1.019 * erb  # Bandwidth

            # Design 4th order gammatone filter
            # Using butterworth approximation for simplicity
            order = 4
            low = max(cf - b/2, 1)
            high = min(cf + b/2, self.sample_rate/2 - 1)

            try:
                sos = signal.butter(order, [low, high], btype='band',
                                    fs=self.sample_rate, output='sos')
                output[i] = signal.sosfilt(sos, audio)
            except:
                # If filter design fails, use simple approach
                output[i] = audio

        return output

    def _simple_filterbank(self, audio: np.ndarray) -> np.ndarray:
        """Simple FFT-based filterbank as fallback."""
        # Compute STFT
        n_fft = 2048
        hop_length = 512

        if LIBROSA_AVAILABLE:
            stft = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)
            freqs = librosa.fft_frequencies(sr=self.sample_rate, n_fft=n_fft)
        else:
            # Manual STFT
            from numpy.fft import rfft
            n_frames = 1 + (len(audio) - n_fft) // hop_length
            stft = np.zeros((n_fft // 2 + 1, n_frames), dtype=complex)
            for i in range(n_frames):
                frame = audio[i * hop_length:i * hop_length + n_fft]
                if len(frame) == n_fft:
                    stft[:, i] = rfft(frame * np.hanning(n_fft))
            freqs = np.fft.rfftfreq(n_fft, 1 / self.sample_rate)

        # Map to our frequency channels
        output = np.zeros((self.n_channels, stft.shape[1]))
        for i, cf in enumerate(self.frequency_bands):
            # Find nearest FFT bin
            bin_idx = np.argmin(np.abs(freqs - cf))
            # Use magnitude
            output[i] = np.abs(stft[bin_idx])

        return output

    def process(self, audio: Union[np.ndarray, str, Path],
                sample_rate: int = None) -> CochleaOutput:
        """
        Process audio through the cochlea model.

        Args:
            audio: Audio waveform (numpy array) or path to audio file
            sample_rate: Sample rate (if audio is array)

        Returns:
            CochleaOutput with tonotopic activation pattern
        """
        # Load audio if path
        if isinstance(audio, (str, Path)):
            audio, sample_rate = self._load_audio(audio)

        if sample_rate is None:
            sample_rate = self.sample_rate

        # Resample if needed
        if sample_rate != self.sample_rate:
            audio = self._resample(audio, sample_rate, self.sample_rate)

        # Ensure mono
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        # Normalize
        audio = audio / (np.max(np.abs(audio)) + 1e-10)

        # Estimate level
        level_db = self._estimate_level_db(audio)

        # Apply gammatone filterbank
        tonotopic = self._gammatone_filterbank(audio)

        # Compute temporal envelope (half-wave rectification + smoothing)
        envelope = np.abs(tonotopic).mean(axis=0)

        # Smooth envelope
        if SCIPY_AVAILABLE:
            from scipy.ndimage import gaussian_filter1d
            envelope = gaussian_filter1d(envelope, sigma=10)

        return CochleaOutput(
            tonotopic_activation=tonotopic,
            frequency_bands=self.frequency_bands,
            level_estimate_db=level_db,
            temporal_envelope=envelope,
            sample_rate=self.sample_rate
        )

    def _load_audio(self, path: Union[str, Path]) -> Tuple[np.ndarray, int]:
        """Load audio from file."""
        path = Path(path)

        if LIBROSA_AVAILABLE:
            audio, sr = librosa.load(path, sr=self.sample_rate, mono=True)
            return audio, sr

        if SCIPY_AVAILABLE and path.suffix.lower() == '.wav':
            sr, audio = wavfile.read(path)
            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            elif audio.dtype == np.int32:
                audio = audio.astype(np.float32) / 2147483648.0
            return audio, sr

        raise RuntimeError(f"Cannot load audio: neither librosa nor scipy available")

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate."""
        if LIBROSA_AVAILABLE:
            return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)

        if SCIPY_AVAILABLE:
            from scipy.signal import resample
            n_samples = int(len(audio) * target_sr / orig_sr)
            return resample(audio, n_samples)

        # Simple linear interpolation fallback
        ratio = target_sr / orig_sr
        n_samples = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, n_samples)
        return np.interp(indices, np.arange(len(audio)), audio)

    def extract_spectral_seeds(self, audio: Union[np.ndarray, str, Path],
                                sample_rate: int = None) -> SpectralSeeds:
        """
        Extract spectral dimension seeds for memory storage.

        These seeds capture the "frequency fingerprint" of the audio.
        """
        if not LIBROSA_AVAILABLE:
            raise RuntimeError("librosa required for spectral seed extraction")

        # Load if path
        if isinstance(audio, (str, Path)):
            audio, sample_rate = librosa.load(audio, sr=self.sample_rate, mono=True)
        elif sample_rate is None:
            sample_rate = self.sample_rate

        # Extract features
        mel = librosa.feature.melspectrogram(y=audio, sr=sample_rate, n_mels=128)
        mfcc = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=40)
        chroma = librosa.feature.chroma_stft(y=audio, sr=sample_rate)
        centroid = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)
        bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sample_rate)
        rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sample_rate)
        contrast = librosa.feature.spectral_contrast(y=audio, sr=sample_rate)
        tonnetz = librosa.feature.tonnetz(y=audio, sr=sample_rate)

        return SpectralSeeds(
            mel_spectrogram=mel,
            mfcc=mfcc,
            chroma=chroma,
            spectral_centroid=centroid,
            spectral_bandwidth=bandwidth,
            spectral_rolloff=rolloff,
            spectral_contrast=contrast,
            tonnetz=tonnetz
        )

    def extract_temporal_seeds(self, audio: Union[np.ndarray, str, Path],
                                sample_rate: int = None) -> TemporalSeeds:
        """
        Extract temporal dimension seeds for memory storage.

        These seeds capture the "rhythm fingerprint" of the audio.
        """
        if not LIBROSA_AVAILABLE:
            raise RuntimeError("librosa required for temporal seed extraction")

        # Load if path
        if isinstance(audio, (str, Path)):
            audio, sample_rate = librosa.load(audio, sr=self.sample_rate, mono=True)
        elif sample_rate is None:
            sample_rate = self.sample_rate

        # Extract features
        zcr = librosa.feature.zero_crossing_rate(audio)
        rms = librosa.feature.rms(y=audio)
        tempo, beat_frames = librosa.beat.beat_track(y=audio, sr=sample_rate)
        onset_env = librosa.onset.onset_strength(y=audio, sr=sample_rate)
        onset_frames = librosa.onset.onset_detect(y=audio, sr=sample_rate)

        return TemporalSeeds(
            zero_crossing_rate=zcr[0],
            rms_energy=rms[0],
            tempo=float(tempo) if np.isscalar(tempo) else float(tempo[0]),
            beat_frames=beat_frames,
            onset_envelope=onset_env,
            onset_frames=onset_frames
        )

    def extract_harmonic_seeds(self, audio: Union[np.ndarray, str, Path],
                                sample_rate: int = None) -> HarmonicSeeds:
        """
        Extract harmonic dimension seeds for memory storage.

        These seeds capture the "tonal fingerprint" of the audio.
        """
        if not LIBROSA_AVAILABLE:
            raise RuntimeError("librosa required for harmonic seed extraction")

        # Load if path
        if isinstance(audio, (str, Path)):
            audio, sample_rate = librosa.load(audio, sr=self.sample_rate, mono=True)
        elif sample_rate is None:
            sample_rate = self.sample_rate

        # Harmonic-percussive separation
        harmonic, percussive = librosa.effects.hpss(audio)

        # Fundamental frequency estimation
        f0, voiced_flag, _ = librosa.pyin(
            audio, fmin=50, fmax=2000, sr=sample_rate
        )

        return HarmonicSeeds(
            harmonic=harmonic,
            percussive=percussive,
            f0=f0,
            voiced_flag=voiced_flag
        )

    def extract_all_seeds(self, audio: Union[np.ndarray, str, Path],
                          sample_rate: int = None) -> Dict[str, Any]:
        """
        Extract all dimensional seeds from audio.

        Returns a complete seed package for memory storage.
        """
        seeds = {}

        try:
            spectral = self.extract_spectral_seeds(audio, sample_rate)
            seeds["spectral"] = spectral.to_dict()
        except Exception as e:
            seeds["spectral"] = {"error": str(e)}

        try:
            temporal = self.extract_temporal_seeds(audio, sample_rate)
            seeds["temporal"] = temporal.to_dict()
        except Exception as e:
            seeds["temporal"] = {"error": str(e)}

        try:
            harmonic = self.extract_harmonic_seeds(audio, sample_rate)
            seeds["harmonic"] = harmonic.to_dict()
        except Exception as e:
            seeds["harmonic"] = {"error": str(e)}

        return seeds


# Singleton
_cochlea_fairy = None

def get_cochlea_fairy() -> CochleaFairy:
    """Get singleton instance."""
    global _cochlea_fairy
    if _cochlea_fairy is None:
        _cochlea_fairy = CochleaFairy()
    return _cochlea_fairy


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CochleaFairy - Tonotopic Analysis")
    parser.add_argument("audio_path", help="Path to audio file")
    parser.add_argument("--extract-seeds", "-e", action="store_true",
                        help="Extract all dimensional seeds")

    args = parser.parse_args()

    fairy = get_cochlea_fairy()

    if args.extract_seeds:
        print(f"\n[CochleaFairy] Extracting seeds from: {args.audio_path}")
        seeds = fairy.extract_all_seeds(args.audio_path)

        print("\n=== Spectral Seeds ===")
        for k, v in seeds.get("spectral", {}).items():
            print(f"  {k}: {v}")

        print("\n=== Temporal Seeds ===")
        for k, v in seeds.get("temporal", {}).items():
            print(f"  {k}: {v}")

        print("\n=== Harmonic Seeds ===")
        for k, v in seeds.get("harmonic", {}).items():
            print(f"  {k}: {v}")
    else:
        print(f"\n[CochleaFairy] Processing: {args.audio_path}")
        output = fairy.process(args.audio_path)
        print(f"\n=== Cochlea Output ===")
        print(f"  Channels: {output.tonotopic_activation.shape[0]}")
        print(f"  Time frames: {output.tonotopic_activation.shape[1]}")
        print(f"  Frequency range: {output.frequency_bands[0]:.1f} - {output.frequency_bands[-1]:.1f} Hz")
        print(f"  Level: {output.level_estimate_db:.1f} dB")
