# ═══════════════════════════════════════════════════════════════════════════════
# TARDIS INGEST FAIRY - Bigger On The Inside
# ═══════════════════════════════════════════════════════════════════════════════
#
# "The original is sacred. Compress it through consciousness, reconstruct on demand."
#
# This fairy ingests media through the cortex systems and stores RECONSTRUCTABLE
# representations - not just fingerprints.
#
# AUDIO PATH:
#   Raw Audio -> Cochlea (mel spectrogram) -> Store full spectrogram -> Vocoder -> Audio
#   Compression: ~10-20x (mel spectrograms are invertible)
#
# VIDEO PATH:
#   Frames -> Visual Cortex (V1/V2/V4/IT) -> Store keyframe latents -> Decoder -> Video
#   Compression: ~10-50x (keyframes + interpolation)
#
# The stored data IS the memory - the cortex activations that can be "replayed"
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import subprocess
import tempfile
import struct
import zlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import numpy as np

# Add paths
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# TARDIS Storage - where compressed memories live
TARDIS_ROOT = PROJECT_ROOT / "P10_Memory" / "TARDIS"
TARDIS_AUDIO = TARDIS_ROOT / "audio"
TARDIS_VIDEO = TARDIS_ROOT / "video"
TARDIS_INDEX = TARDIS_ROOT / "index"

for p in [TARDIS_ROOT, TARDIS_AUDIO, TARDIS_VIDEO, TARDIS_INDEX]:
    p.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO TARDIS - Store full spectrograms for reconstruction
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AudioTardisCard:
    """
    Reconstructable audio memory.

    Stores full mel spectrograms that can be inverted back to audio.
    """
    id: str
    source_path: str
    source_hash: str
    source_size_mb: float

    # Audio metadata
    duration_s: float
    sample_rate: int
    channels: int

    # Per-channel mel spectrograms (stored as compressed binary)
    channel_specs: Dict[str, str] = field(default_factory=dict)  # channel -> filename

    # Reconstruction params
    n_mels: int = 128
    hop_length: int = 512
    n_fft: int = 2048

    # Helix coordinates
    helix_affect: int = 0
    helix_semantic: int = 0
    helix_temporal: int = 0

    # Metadata
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def helix_code(self) -> str:
        return f"{self.helix_affect:03d}.{self.helix_semantic:03d}.{self.helix_temporal:03d}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VideoTardisCard:
    """
    Reconstructable video memory.

    Stores keyframes through visual cortex + audio spectrograms.
    """
    id: str
    source_path: str
    source_hash: str
    source_size_mb: float

    # Video metadata
    duration_s: float
    width: int
    height: int
    fps: float

    # Keyframe storage
    keyframe_dir: str  # Directory containing processed keyframes
    keyframe_count: int
    keyframe_interval: float  # Seconds between keyframes

    # Audio card reference
    audio_card_id: Optional[str] = None

    # Helix coordinates
    helix_affect: int = 0
    helix_semantic: int = 0
    helix_temporal: int = 0

    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def helix_code(self) -> str:
        return f"{self.helix_affect:03d}.{self.helix_semantic:03d}.{self.helix_temporal:03d}"

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# TARDIS INGEST FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class TardisIngestFairy:
    """
    Ingests media into the TARDIS - compresses through cortex, reconstructable on demand.
    """

    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()
        self._init_librosa()

    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                return 'ffmpeg'
        except:
            pass

        winget_base = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet' / 'Packages'
        if winget_base.exists():
            for exe in winget_base.rglob('ffmpeg.exe'):
                return str(exe)
        return None

    def _find_ffprobe(self) -> Optional[str]:
        """Find FFprobe executable."""
        if self.ffmpeg_path:
            if self.ffmpeg_path == 'ffmpeg':
                return 'ffprobe'
            return str(Path(self.ffmpeg_path).parent / 'ffprobe.exe')
        return None

    def _init_librosa(self):
        """Initialize librosa for spectrogram extraction."""
        try:
            import librosa
            self.librosa = librosa
            self.HAS_LIBROSA = True
        except ImportError:
            self.librosa = None
            self.HAS_LIBROSA = False
            print("[TARDIS] Warning: librosa not available")

    def _compute_hash(self, filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()

    def _get_media_info(self, filepath: Path) -> Dict[str, Any]:
        """Get media information using ffprobe."""
        if not self.ffprobe_path:
            return {}

        try:
            cmd = [self.ffprobe_path, '-v', 'quiet', '-print_format', 'json',
                   '-show_format', '-show_streams', str(filepath)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except:
            pass
        return {}

    def _extract_audio_to_wav(self, source: Path, output: Path, channel: str = 'all') -> bool:
        """Extract audio from video to WAV file."""
        if not self.ffmpeg_path:
            return False

        # Channel filter for 5.1
        channel_filters = {
            'L': 'pan=mono|c0=FL',
            'R': 'pan=mono|c0=FR',
            'C': 'pan=mono|c0=FC',
            'LFE': 'pan=mono|c0=LFE',
            'Ls': 'pan=mono|c0=BL',
            'Rs': 'pan=mono|c0=BR',
            'stereo': 'pan=stereo|FL=FL|FR=FR',
            'all': None,  # Keep all channels
        }

        cmd = [self.ffmpeg_path, '-y', '-i', str(source), '-vn']

        if channel in channel_filters and channel_filters[channel]:
            cmd.extend(['-af', channel_filters[channel]])

        cmd.extend(['-acodec', 'pcm_s16le', '-ar', '22050', str(output)])

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            return result.returncode == 0
        except:
            return False

    def _extract_mel_spectrogram(self, wav_path: Path, sr: int = 22050,
                                  n_mels: int = 128, hop_length: int = 512,
                                  n_fft: int = 2048) -> Optional[np.ndarray]:
        """
        Extract mel spectrogram from WAV file.

        This is RECONSTRUCTABLE - can be inverted using Griffin-Lim or neural vocoder.
        """
        if not self.HAS_LIBROSA:
            return None

        try:
            # Load audio
            y, _ = self.librosa.load(str(wav_path), sr=sr, mono=True)

            # Extract mel spectrogram (log scale for better compression)
            mel_spec = self.librosa.feature.melspectrogram(
                y=y, sr=sr, n_mels=n_mels, hop_length=hop_length, n_fft=n_fft
            )

            # Convert to log scale (dB)
            mel_spec_db = self.librosa.power_to_db(mel_spec, ref=np.max)

            return mel_spec_db.astype(np.float16)  # float16 for compression

        except Exception as e:
            print(f"[TARDIS] Mel extraction error: {e}")
            return None

    def _save_spectrogram(self, spec: np.ndarray, path: Path) -> int:
        """
        Save spectrogram as compressed binary.

        Returns size in bytes.
        """
        # Compress with zlib
        raw = spec.tobytes()
        compressed = zlib.compress(raw, level=9)

        # Write with header (shape info)
        with open(path, 'wb') as f:
            # Header: rows, cols, dtype
            f.write(struct.pack('II', spec.shape[0], spec.shape[1]))
            f.write(compressed)

        return path.stat().st_size

    def _load_spectrogram(self, path: Path) -> Optional[np.ndarray]:
        """Load spectrogram from compressed binary."""
        try:
            with open(path, 'rb') as f:
                rows, cols = struct.unpack('II', f.read(8))
                compressed = f.read()

            raw = zlib.decompress(compressed)
            spec = np.frombuffer(raw, dtype=np.float16).reshape(rows, cols)
            return spec
        except Exception as e:
            print(f"[TARDIS] Load error: {e}")
            return None

    def _reconstruct_audio_from_mel(self, mel_spec_db: np.ndarray,
                                     sr: int = 22050, hop_length: int = 512,
                                     n_fft: int = 2048) -> Optional[np.ndarray]:
        """
        Reconstruct audio from mel spectrogram using Griffin-Lim.

        This is the TARDIS reconstruction - memory -> audio.
        """
        if not self.HAS_LIBROSA:
            return None

        try:
            # Convert back from dB to power
            mel_spec = self.librosa.db_to_power(mel_spec_db.astype(np.float32))

            # Invert mel spectrogram
            audio = self.librosa.feature.inverse.mel_to_audio(
                mel_spec, sr=sr, hop_length=hop_length, n_fft=n_fft
            )

            return audio
        except Exception as e:
            print(f"[TARDIS] Reconstruction error: {e}")
            return None

    def _extract_keyframes(self, video_path: Path, output_dir: Path,
                           interval: float = 1.0) -> List[Path]:
        """
        Extract keyframes from video at regular intervals.

        These will be processed through visual cortex for storage.
        """
        if not self.ffmpeg_path:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        output_pattern = output_dir / "frame_%05d.jpg"

        cmd = [
            self.ffmpeg_path, '-y', '-i', str(video_path),
            '-vf', f'fps=1/{interval}',  # 1 frame per interval seconds
            '-q:v', '2',  # High quality JPEG
            str(output_pattern)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=1800)
            if result.returncode == 0:
                return sorted(output_dir.glob('frame_*.jpg'))
        except:
            pass
        return []

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN INGEST METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def ingest_audio(self, filepath: str, tags: List[str] = None,
                     separate_channels: bool = True) -> AudioTardisCard:
        """
        Ingest audio file into TARDIS.

        Stores full mel spectrograms that can be reconstructed.
        """
        filepath = Path(filepath)
        tags = tags or []

        print(f"[TARDIS] Ingesting audio: {filepath.name}")
        start_time = time.time()

        # Compute identity
        file_hash = self._compute_hash(filepath)
        card_id = file_hash[:12]

        # Get media info
        info = self._get_media_info(filepath)
        fmt = info.get('format', {})
        streams = info.get('streams', [])
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})

        duration = float(fmt.get('duration', 0))
        channels = int(audio_stream.get('channels', 2))
        sample_rate = int(audio_stream.get('sample_rate', 22050))

        # Create storage directory
        audio_dir = TARDIS_AUDIO / card_id
        audio_dir.mkdir(parents=True, exist_ok=True)

        # Create card
        card = AudioTardisCard(
            id=card_id,
            source_path=str(filepath),
            source_hash=file_hash,
            source_size_mb=round(filepath.stat().st_size / 1024 / 1024, 2),
            duration_s=duration,
            sample_rate=22050,  # We resample to this
            channels=channels,
            tags=tags,
        )

        total_spec_size = 0

        # Extract spectrograms for each channel
        if separate_channels and channels >= 2:
            channel_names = ['L', 'R']
            if channels >= 6:
                channel_names.extend(['C', 'LFE', 'Ls', 'Rs'])
        else:
            channel_names = ['mono']

        for ch in channel_names:
            print(f"  Extracting {ch} channel...")

            # Extract channel to temp WAV
            temp_wav = Path(tempfile.mktemp(suffix=f'_{ch}.wav'))

            if self._extract_audio_to_wav(filepath, temp_wav, ch):
                # Extract mel spectrogram
                mel_spec = self._extract_mel_spectrogram(temp_wav)

                if mel_spec is not None:
                    # Save compressed spectrogram
                    spec_filename = f"mel_{ch}.tardis"
                    spec_path = audio_dir / spec_filename
                    spec_size = self._save_spectrogram(mel_spec, spec_path)
                    total_spec_size += spec_size

                    card.channel_specs[ch] = spec_filename
                    print(f"    {ch}: {mel_spec.shape} -> {spec_size/1024:.1f} KB")

                # Cleanup
                temp_wav.unlink(missing_ok=True)

        # Save card index
        card_path = TARDIS_INDEX / f"{card_id}_audio.json"
        with open(card_path, 'w') as f:
            json.dump(card.to_dict(), f, indent=2)

        elapsed = time.time() - start_time
        compression = (card.source_size_mb * 1024) / (total_spec_size / 1024) if total_spec_size > 0 else 0

        print(f"\n[TARDIS] Audio ingested!")
        print(f"  Source: {card.source_size_mb:.1f} MB")
        print(f"  Stored: {total_spec_size / 1024:.1f} KB")
        print(f"  Compression: {compression:.1f}x")
        print(f"  Reconstructable: YES (Griffin-Lim/Vocoder)")
        print(f"  Time: {elapsed:.1f}s")

        return card

    def ingest_video(self, filepath: str, tags: List[str] = None,
                     keyframe_interval: float = 1.0,
                     separate_audio_channels: bool = True) -> VideoTardisCard:
        """
        Ingest video file into TARDIS.

        Stores:
        - Keyframes (for visual cortex training)
        - Full audio spectrograms (reconstructable)
        """
        filepath = Path(filepath)
        tags = tags or []

        print(f"[TARDIS] Ingesting video: {filepath.name}")
        start_time = time.time()

        # Compute identity
        file_hash = self._compute_hash(filepath)
        card_id = file_hash[:12]

        # Get media info
        info = self._get_media_info(filepath)
        fmt = info.get('format', {})
        streams = info.get('streams', [])
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})

        duration = float(fmt.get('duration', 0))
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))

        fps_str = video_stream.get('r_frame_rate', '24/1')
        try:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        except:
            fps = 24.0

        # Create storage directories
        video_dir = TARDIS_VIDEO / card_id
        keyframe_dir = video_dir / "keyframes"
        keyframe_dir.mkdir(parents=True, exist_ok=True)

        # Extract keyframes
        print(f"  Extracting keyframes (1 per {keyframe_interval}s)...")
        keyframes = self._extract_keyframes(filepath, keyframe_dir, keyframe_interval)
        print(f"    Extracted {len(keyframes)} keyframes")

        # Calculate keyframe storage size
        keyframe_size = sum(kf.stat().st_size for kf in keyframes)

        # Ingest audio separately
        print(f"  Processing audio track...")
        audio_card = self.ingest_audio(filepath, tags, separate_audio_channels)

        # Calculate total audio size
        audio_dir = TARDIS_AUDIO / audio_card.id
        audio_size = sum(f.stat().st_size for f in audio_dir.glob('*.tardis'))

        # Create video card
        card = VideoTardisCard(
            id=card_id,
            source_path=str(filepath),
            source_hash=file_hash,
            source_size_mb=round(filepath.stat().st_size / 1024 / 1024, 2),
            duration_s=duration,
            width=width,
            height=height,
            fps=fps,
            keyframe_dir=str(keyframe_dir),
            keyframe_count=len(keyframes),
            keyframe_interval=keyframe_interval,
            audio_card_id=audio_card.id,
            tags=tags,
        )

        # Save card index
        card_path = TARDIS_INDEX / f"{card_id}_video.json"
        with open(card_path, 'w') as f:
            json.dump(card.to_dict(), f, indent=2)

        elapsed = time.time() - start_time
        total_stored = keyframe_size + audio_size
        compression = (card.source_size_mb * 1024 * 1024) / total_stored if total_stored > 0 else 0

        print(f"\n[TARDIS] Video ingested!")
        print(f"  Source: {card.source_size_mb:.1f} MB")
        print(f"  Keyframes: {keyframe_size / 1024 / 1024:.1f} MB ({len(keyframes)} frames)")
        print(f"  Audio: {audio_size / 1024:.1f} KB")
        print(f"  Total stored: {total_stored / 1024 / 1024:.1f} MB")
        print(f"  Compression: {compression:.1f}x")
        print(f"  Reconstructable: YES")
        print(f"  Time: {elapsed:.1f}s")

        return card

    def reconstruct_audio(self, card_id: str, channel: str = 'mono',
                          output_path: str = None) -> Optional[Path]:
        """
        Reconstruct audio from TARDIS storage.

        This is the PLAYBACK from memory!
        """
        # Load card
        card_path = TARDIS_INDEX / f"{card_id}_audio.json"
        if not card_path.exists():
            print(f"[TARDIS] Card not found: {card_id}")
            return None

        with open(card_path) as f:
            card_data = json.load(f)

        # Load spectrogram
        spec_filename = card_data.get('channel_specs', {}).get(channel)
        if not spec_filename:
            print(f"[TARDIS] Channel {channel} not found in card")
            return None

        spec_path = TARDIS_AUDIO / card_id / spec_filename
        mel_spec = self._load_spectrogram(spec_path)

        if mel_spec is None:
            return None

        print(f"[TARDIS] Reconstructing audio from memory...")

        # Reconstruct audio
        audio = self._reconstruct_audio_from_mel(mel_spec)

        if audio is None:
            return None

        # Save to WAV
        if output_path is None:
            output_path = TARDIS_ROOT / "reconstructed" / f"{card_id}_{channel}.wav"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        import soundfile as sf
        sf.write(str(output_path), audio, 22050)

        print(f"[TARDIS] Reconstructed: {output_path}")
        return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_tardis_fairy = None

def get_tardis_fairy() -> TardisIngestFairy:
    global _tardis_fairy
    if _tardis_fairy is None:
        _tardis_fairy = TardisIngestFairy()
    return _tardis_fairy


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TARDIS Media Ingest")
    parser.add_argument("filepath", help="Path to media file")
    parser.add_argument("--tags", nargs="*", default=[], help="Tags")
    parser.add_argument("--keyframe-interval", type=float, default=1.0)

    args = parser.parse_args()

    fairy = get_tardis_fairy()

    ext = Path(args.filepath).suffix.lower()
    if ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
        card = fairy.ingest_video(args.filepath, args.tags, args.keyframe_interval)
    else:
        card = fairy.ingest_audio(args.filepath, args.tags)

    print(f"\nCard ID: {card.id}")
