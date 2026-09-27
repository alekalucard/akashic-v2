# ═══════════════════════════════════════════════════════════════════════════════
# MediaIngestFairy - Full Dimensional Media Ingestion
# ═══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Ingest media (video, audio, images) into SRM memory with:
#   - Triple-helix coordinates (Affect × Semantic × Temporal)
#   - Full audio dimensional seeds (spectral, temporal, harmonic)
#   - Channel separation (L/R/C for stereo/surround)
#   - Visual seeds for video frames
#
# Philosophy: "Store the soul, not the shell. The dimensions ARE the memory."
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Add paths
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Storage paths
SRM_CLUSTERS = PROJECT_ROOT / "P10_Memory" / "SRM_Clusters"
MEDIA_CLUSTER = SRM_CLUSTERS / "media"
VIDEO_CLUSTER = MEDIA_CLUSTER / "video"
AUDIO_CLUSTER = MEDIA_CLUSTER / "audio"
CARDS_PATH = MEDIA_CLUSTER / "memory_cards"

# Ensure directories exist
for p in [MEDIA_CLUSTER, VIDEO_CLUSTER, AUDIO_CLUSTER, CARDS_PATH]:
    p.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELIX COORDINATE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HelixCoordinate:
    """
    Triple-helix dimensional coordinate for memory location.

    Format: AAA.SSS.TTT (Affect.Semantic.Temporal)
    Each axis is 0-999, giving ~1 billion unique memory locations.
    """
    affect: int = 0       # 0-999: Emotional dimension
    semantic: int = 0     # 0-999: Conceptual dimension
    temporal: int = 0     # 0-999: Temporal dimension

    @property
    def dewey_code(self) -> str:
        """Get Dewey-decimal-style coordinate"""
        return f"{self.affect:03d}.{self.semantic:03d}.{self.temporal:03d}"

    def to_dict(self) -> dict:
        return {"affect": self.affect, "semantic": self.semantic, "temporal": self.temporal}


@dataclass
class AudioChannelSeeds:
    """Seeds for a single audio channel (L, R, C, etc.)"""
    channel: str  # 'L', 'R', 'C', 'LFE', 'Ls', 'Rs'

    # Spectral
    mfcc_mean: List[float] = field(default_factory=list)
    mfcc_std: List[float] = field(default_factory=list)
    chroma: List[float] = field(default_factory=list)
    centroid: float = 0.0
    bandwidth: float = 0.0
    rolloff: float = 0.0

    # Temporal
    tempo: float = 0.0
    beats: int = 0
    onsets: int = 0
    zcr: float = 0.0
    rms: float = 0.0

    # Harmonic
    harmonic_ratio: float = 0.0
    f0_mean: float = 0.0
    voiced_ratio: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MediaMemoryCard:
    """
    Complete memory card for media - the "soul" of the content.
    This is what gets stored in SRM, not the raw file.
    """
    # Identity
    id: str
    kind: str  # 'media.video', 'media.audio', 'media.image'
    title: str = ""

    # Source info (for verification, not storage)
    source_path: str = ""
    source_hash: str = ""
    source_size_mb: float = 0.0

    # Helix coordinates
    helix: HelixCoordinate = field(default_factory=HelixCoordinate)

    # Dimensions - Video
    video_width: int = 0
    video_height: int = 0
    video_fps: float = 0.0
    video_duration_s: float = 0.0
    video_codec: str = ""

    # Dimensions - Audio
    audio_sample_rate: int = 0
    audio_channels: int = 0
    audio_codec: str = ""

    # Channel-separated audio seeds (L, R, C, etc.)
    channel_seeds: List[AudioChannelSeeds] = field(default_factory=list)

    # Mixed/mono audio seeds (for quick similarity)
    mixed_seeds: Optional[AudioChannelSeeds] = None

    # Visual seeds (for video - keyframe analysis)
    visual_seeds: Dict[str, Any] = field(default_factory=dict)

    # Semantic tags
    tags: List[str] = field(default_factory=list)

    # Timestamps
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['helix'] = self.helix.to_dict()
        d['channel_seeds'] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.channel_seeds]
        if self.mixed_seeds:
            d['mixed_seeds'] = self.mixed_seeds.to_dict()
        return d

    @property
    def size_kb(self) -> float:
        """Get card size in KB"""
        return len(json.dumps(self.to_dict()).encode()) / 1024


# ═══════════════════════════════════════════════════════════════════════════════
# MEDIA INGEST FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class MediaIngestFairy:
    """
    Ingests media files into SRM memory as dimensional seed cards.

    The original file is NOT stored - only its dimensional essence.
    This achieves massive compression (100,000x+) while preserving
    the semantic "soul" of the content.
    """

    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        self.cochlea = None
        self._init_cochlea()

    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable."""
        # Check PATH first
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                return 'ffmpeg'
        except:
            pass

        # Check WinGet location
        winget_base = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet' / 'Packages'
        if winget_base.exists():
            for ffmpeg_exe in winget_base.rglob('ffmpeg.exe'):
                return str(ffmpeg_exe)

        return None

    def _init_cochlea(self):
        """Initialize cochlea fairy for audio analysis."""
        try:
            from fairies.P40_Sensory.audio.cochlea_fairy import get_cochlea_fairy
            self.cochlea = get_cochlea_fairy()
        except ImportError:
            print("[MediaIngestFairy] Warning: CochleaFairy not available")

    def _compute_hash(self, filepath: Path) -> str:
        """Compute SHA256 hash of file."""
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def _get_media_info(self, filepath: Path) -> Dict[str, Any]:
        """Get media information using ffprobe."""
        if not self.ffmpeg_path:
            return {}

        ffprobe = str(Path(self.ffmpeg_path).parent / 'ffprobe.exe') if 'ffmpeg.exe' in self.ffmpeg_path else 'ffprobe'

        try:
            cmd = [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(filepath)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except:
            pass
        return {}

    def _extract_audio_channel(self, video_path: Path, channel: str, duration_s: float = 60) -> Optional[Path]:
        """
        Extract a single audio channel to temp WAV file.

        Channels: 'L' (left), 'R' (right), 'C' (center), 'LFE', 'Ls', 'Rs', 'mono'
        """
        if not self.ffmpeg_path:
            return None

        temp_wav = Path(tempfile.mktemp(suffix=f'_{channel}.wav'))

        # Channel mapping for 5.1: FL FR FC LFE BL BR
        channel_map = {
            'L': 'pan=mono|c0=FL',
            'R': 'pan=mono|c0=FR',
            'C': 'pan=mono|c0=FC',
            'LFE': 'pan=mono|c0=LFE',
            'Ls': 'pan=mono|c0=BL',
            'Rs': 'pan=mono|c0=BR',
            'mono': 'pan=mono|c0=0.5*FL+0.5*FR',  # Standard downmix
        }

        filter_arg = channel_map.get(channel, 'pan=mono|c0=0.5*FL+0.5*FR')

        cmd = [
            self.ffmpeg_path, '-y',
            '-ss', '60',  # Skip intro
            '-t', str(duration_s),
            '-i', str(video_path),
            '-vn',  # No video
            '-af', filter_arg,
            '-acodec', 'pcm_s16le',
            '-ar', '22050',
            '-ac', '1',
            temp_wav
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and temp_wav.exists():
                return temp_wav
        except:
            pass

        return None

    def _extract_seeds_from_wav(self, wav_path: Path, channel: str) -> AudioChannelSeeds:
        """Extract dimensional seeds from a WAV file."""
        seeds = AudioChannelSeeds(channel=channel)

        if not self.cochlea:
            return seeds

        try:
            raw_seeds = self.cochlea.extract_all_seeds(str(wav_path))

            # Spectral
            spectral = raw_seeds.get('spectral', {})
            seeds.mfcc_mean = self._to_list(spectral.get('mfcc_mean', []))
            seeds.mfcc_std = self._to_list(spectral.get('mfcc_std', []))
            seeds.chroma = self._to_list(spectral.get('chroma_mean', []))
            seeds.centroid = float(spectral.get('centroid_mean', 0))
            seeds.bandwidth = float(spectral.get('bandwidth_mean', 0))
            seeds.rolloff = float(spectral.get('rolloff_mean', 0))

            # Temporal
            temporal = raw_seeds.get('temporal', {})
            seeds.tempo = float(temporal.get('tempo', 0))
            seeds.beats = int(temporal.get('n_beats', 0))
            seeds.onsets = int(temporal.get('n_onsets', 0))
            seeds.zcr = float(temporal.get('zcr_mean', 0))
            seeds.rms = float(temporal.get('rms_mean', 0))

            # Harmonic
            harmonic = raw_seeds.get('harmonic', {})
            seeds.harmonic_ratio = float(harmonic.get('harmonic_ratio', 0))
            seeds.f0_mean = float(harmonic.get('f0_mean', 0))
            seeds.voiced_ratio = float(harmonic.get('voiced_ratio', 0))

        except Exception as e:
            print(f"[MediaIngestFairy] Seed extraction error: {e}")

        return seeds

    def _to_list(self, arr) -> List[float]:
        """Convert numpy array or list to Python list of floats."""
        if hasattr(arr, 'tolist'):
            return [float(x) for x in arr.tolist()]
        elif isinstance(arr, list):
            return [float(x) for x in arr]
        return []

    def _calculate_helix_coordinates(self, card: MediaMemoryCard) -> HelixCoordinate:
        """
        Calculate helix coordinates from the card's seeds.

        Affect: Derived from audio energy/tempo (emotional arousal)
        Semantic: Derived from content type and tags
        Temporal: Derived from duration and release date
        """
        # Affect axis (0-999)
        # Based on tempo, RMS energy, harmonic content
        if card.mixed_seeds:
            tempo_norm = min(1.0, card.mixed_seeds.tempo / 180)  # Normalize tempo to 0-1
            energy_norm = min(1.0, card.mixed_seeds.rms * 50)  # Normalize RMS
            harmonic_norm = card.mixed_seeds.harmonic_ratio

            # High tempo + energy = excitement (800s), low = calm (000s)
            affect_domain = int(8 * tempo_norm)  # 0-8
            affect_valence = int(9 * harmonic_norm)  # Harmonic = pleasant
            affect_intensity = int(9 * energy_norm)
            affect = affect_domain * 100 + affect_valence * 10 + affect_intensity
        else:
            affect = 450  # Neutral default

        # Semantic axis (0-999)
        # 700s = Arts, 800s = Literature/Stories
        semantic_domain = 7  # Arts (video/audio)
        if 'comedy' in card.tags or 'animation' in card.tags:
            semantic_subdomain = 9  # Comedy/Entertainment
        elif 'drama' in card.tags:
            semantic_subdomain = 5  # Drama
        elif 'music' in card.tags:
            semantic_subdomain = 8  # Music
        else:
            semantic_subdomain = 0  # General
        semantic_detail = 0
        semantic = semantic_domain * 100 + semantic_subdomain * 10 + semantic_detail

        # Temporal axis (0-999)
        # Based on content duration (longer = higher number)
        duration_mins = card.video_duration_s / 60 if card.video_duration_s else 0
        if duration_mins < 5:
            temporal = 100  # Short clip
        elif duration_mins < 30:
            temporal = 300  # TV episode
        elif duration_mins < 90:
            temporal = 500  # Long episode / short film
        elif duration_mins < 150:
            temporal = 700  # Movie
        else:
            temporal = 900  # Long movie / documentary

        return HelixCoordinate(affect=affect, semantic=semantic, temporal=temporal)

    def ingest(
        self,
        filepath: str,
        tags: List[str] = None,
        title: str = None,
        sample_duration: float = 60.0,
        extract_channels: bool = True
    ) -> MediaMemoryCard:
        """
        Ingest a media file into SRM memory.

        Args:
            filepath: Path to media file
            tags: Semantic tags for classification
            title: Human-readable title
            sample_duration: Seconds of audio to analyze (default 60)
            extract_channels: If True, extract L/R/C separately (5.1)

        Returns:
            MediaMemoryCard with all dimensional seeds
        """
        filepath = Path(filepath)
        tags = tags or []

        print(f"[MediaIngestFairy] Ingesting: {filepath.name}")
        start_time = time.time()

        # Compute identity
        file_hash = self._compute_hash(filepath)
        card_id = file_hash[:12]

        # Get media info
        info = self._get_media_info(filepath)
        fmt = info.get('format', {})
        streams = info.get('streams', [])

        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})

        # Create card
        card = MediaMemoryCard(
            id=card_id,
            kind='media.video' if video_stream else 'media.audio',
            title=title or filepath.stem,
            source_path=str(filepath),
            source_hash=file_hash,
            source_size_mb=round(filepath.stat().st_size / 1024 / 1024, 2),
            tags=tags,
        )

        # Video dimensions
        if video_stream:
            card.video_width = int(video_stream.get('width', 0))
            card.video_height = int(video_stream.get('height', 0))
            card.video_codec = video_stream.get('codec_name', '')
            card.video_duration_s = float(fmt.get('duration', 0))
            try:
                fps_str = video_stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    card.video_fps = float(num) / float(den) if float(den) > 0 else 0
            except:
                pass

        # Audio dimensions
        if audio_stream:
            card.audio_sample_rate = int(audio_stream.get('sample_rate', 0))
            card.audio_channels = int(audio_stream.get('channels', 0))
            card.audio_codec = audio_stream.get('codec_name', '')

        # Extract audio seeds
        temp_files = []

        # Always extract mono mix for quick similarity matching
        mono_wav = self._extract_audio_channel(filepath, 'mono', sample_duration)
        if mono_wav:
            temp_files.append(mono_wav)
            card.mixed_seeds = self._extract_seeds_from_wav(mono_wav, 'mono')

        # Extract individual channels for 5.1/stereo
        if extract_channels and card.audio_channels >= 2:
            channels = ['L', 'R']
            if card.audio_channels >= 6:  # 5.1
                channels.extend(['C', 'LFE', 'Ls', 'Rs'])

            for ch in channels:
                ch_wav = self._extract_audio_channel(filepath, ch, sample_duration)
                if ch_wav:
                    temp_files.append(ch_wav)
                    ch_seeds = self._extract_seeds_from_wav(ch_wav, ch)
                    card.channel_seeds.append(ch_seeds)

        # Calculate helix coordinates
        card.helix = self._calculate_helix_coordinates(card)

        # Cleanup temp files
        for tf in temp_files:
            try:
                tf.unlink()
            except:
                pass

        # Save card to SRM
        card_path = CARDS_PATH / f"{card_id}_{filepath.stem[:30]}.json"
        with open(card_path, 'w', encoding='utf-8') as f:
            json.dump(card.to_dict(), f, indent=2, default=str)

        elapsed = time.time() - start_time
        compression = (card.source_size_mb * 1024) / card.size_kb if card.size_kb > 0 else 0

        print(f"[MediaIngestFairy] Complete!")
        print(f"  Source: {card.source_size_mb:.1f} MB")
        print(f"  Card: {card.size_kb:.2f} KB")
        print(f"  Compression: {compression:.0f}x")
        print(f"  Helix: {card.helix.dewey_code}")
        print(f"  Channels: {len(card.channel_seeds)} ({', '.join(s.channel for s in card.channel_seeds)})")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Saved: {card_path.name}")

        return card


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_ingest_fairy = None

def get_media_ingest_fairy() -> MediaIngestFairy:
    """Get singleton MediaIngestFairy instance."""
    global _ingest_fairy
    if _ingest_fairy is None:
        _ingest_fairy = MediaIngestFairy()
    return _ingest_fairy


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest media into SRM memory")
    parser.add_argument("filepath", help="Path to media file")
    parser.add_argument("--tags", nargs="*", default=[], help="Tags for classification")
    parser.add_argument("--title", help="Human-readable title")
    parser.add_argument("--duration", type=float, default=60, help="Sample duration (seconds)")
    parser.add_argument("--no-channels", action="store_true", help="Skip channel separation")

    args = parser.parse_args()

    fairy = get_media_ingest_fairy()
    card = fairy.ingest(
        args.filepath,
        tags=args.tags,
        title=args.title,
        sample_duration=args.duration,
        extract_channels=not args.no_channels
    )

    print(f"\nCard ID: {card.id}")
    print(f"Helix: {card.helix.dewey_code}")
