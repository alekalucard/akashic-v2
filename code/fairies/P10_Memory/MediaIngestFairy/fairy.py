# MediaIngestFairy - Full Dimensional Media Ingestion
# =========================================================
#
# Purpose: Ingest media (video, audio, images) into SRM memory with:
#   - Triple-helix coordinates (Affect x Semantic x Temporal)
#   - Full audio dimensional seeds (spectral, temporal, harmonic)
#   - Channel separation (L/R/C/LFE/Ls/Rs for stereo/5.1 surround)
#   - Visual seeds for video frames
#
# Philosophy: "Store the soul, not the shell. The dimensions ARE the memory."
#
# =========================================================

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import subprocess
import tempfile
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field, asdict

# V2 imports
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy, FairyState

# TracerWorkerMixin is optional - fallback to empty class if not available
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        """Fallback empty mixin when tracer system not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload from TensorEnvelope or dict message."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    return {"raw": message}


# =========================================================
# HELIX COORDINATE SYSTEM
# =========================================================

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
    """Seeds for a single audio channel (L, R, C, LFE, Ls, Rs)"""
    channel: str  # 'L', 'R', 'C', 'LFE', 'Ls', 'Rs', 'mono'

    # Spectral features
    mfcc_mean: List[float] = field(default_factory=list)
    mfcc_std: List[float] = field(default_factory=list)
    chroma: List[float] = field(default_factory=list)
    centroid: float = 0.0
    bandwidth: float = 0.0
    rolloff: float = 0.0

    # Temporal features
    tempo: float = 0.0
    beats: int = 0
    onsets: int = 0
    zcr: float = 0.0
    rms: float = 0.0

    # Harmonic features
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

    # Video dimensions
    video_width: int = 0
    video_height: int = 0
    video_fps: float = 0.0
    video_duration_s: float = 0.0
    video_codec: str = ""

    # Audio dimensions
    audio_sample_rate: int = 0
    audio_channels: int = 0
    audio_codec: str = ""

    # Channel-separated audio seeds (L, R, C, LFE, Ls, Rs)
    channel_seeds: List[AudioChannelSeeds] = field(default_factory=list)

    # Mixed/mono audio seeds (for quick similarity matching)
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


# =========================================================
# MEDIA INGEST FAIRY
# =========================================================

class MediaIngestFairy(Fairy):
    """
    Ingests media files into SRM memory as dimensional seed cards.

    The original file is NOT stored - only its dimensional essence.
    This achieves massive compression (100,000x+) while preserving
    the semantic "soul" of the content.

    Topics published:
      - memory.media.ingested: When media is successfully processed

    Topics subscribed:
      - memory.media.request: Requests to ingest media
    """

    ACTOR_NAME = "MediaIngestFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "media_ingest"

    PURPOSE = "Ingest media into dimensional memory"
    MANTRA = "Store the soul, not the shell"

    def __init__(self, fabric=None, storage_dir: Optional[Path] = None):
        super().__init__(fabric)
        self._init_tracer_worker()

        # Storage paths
        if storage_dir:
            self._storage_dir = Path(storage_dir)
        else:
            self._storage_dir = Path(__file__).parent.parent.parent.parent / "state" / "media_cards"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        # FFmpeg
        self._ffmpeg_path: Optional[str] = None
        self._ffprobe_path: Optional[str] = None

        # Cochlea integration (for audio analysis)
        self._cochlea = None

        # Thread safety
        self._lock = threading.Lock()

        # Stats
        self._stats = {
            "files_ingested": 0,
            "total_source_mb": 0.0,
            "total_card_kb": 0.0,
            "errors": 0,
        }

    # =========================================================
    # LIFECYCLE
    # =========================================================

    def on_boot(self):
        """Initialize on boot"""
        # IMPORTANT: Call super() to trigger HeartbeatMixin auto-start
        super().on_boot()
        self._find_ffmpeg()
        self._init_cochlea()

        if self._ffmpeg_path:
            self.log(f"FFmpeg found: {self._ffmpeg_path}")
        else:
            self.log("Warning: FFmpeg not found - media analysis limited")
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def on_wire(self, postal):
        """Wire to postal system"""
        postal.subscribe("memory.media.request", self._handle_ingest_request)

    def _handle_ingest_request(self, message: Dict[str, Any]):
        """Handle media ingest request from postal"""
        payload = _extract_payload(message)
        filepath = payload.get("filepath")
        tags = payload.get("tags", [])
        title = payload.get("title")

        if not filepath:
            return

        try:
            card = self.ingest(filepath, tags=tags, title=title)

            # Publish result
            if hasattr(self, '_postal') and self._postal:
                self._postal.publish("memory.media.ingested", {
                    "card_id": card.id,
                    "helix": card.helix.dewey_code,
                    "title": card.title,
                    "source_path": str(filepath),
                    "compression_ratio": (card.source_size_mb * 1024) / card.size_kb if card.size_kb > 0 else 0,
                })
        except Exception as e:
            self.log(f"Ingest request failed: {e}")

    # =========================================================
    # FFMPEG DISCOVERY
    # =========================================================

    def _find_ffmpeg(self):
        """Find FFmpeg and FFprobe executables"""
        # Check PATH first
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                self._ffmpeg_path = 'ffmpeg'
                self._ffprobe_path = 'ffprobe'
                return
        except:
            pass

        # Check WinGet location (Windows)
        winget_base = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet' / 'Packages'
        if winget_base.exists():
            for ffmpeg_exe in winget_base.rglob('ffmpeg.exe'):
                self._ffmpeg_path = str(ffmpeg_exe)
                ffprobe = ffmpeg_exe.parent / 'ffprobe.exe'
                if ffprobe.exists():
                    self._ffprobe_path = str(ffprobe)
                return

        # Check common locations
        common_paths = [
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("/usr/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
        ]
        for p in common_paths:
            if p.exists():
                self._ffmpeg_path = str(p)
                self._ffprobe_path = str(p).replace('ffmpeg', 'ffprobe')
                return

    def _init_cochlea(self):
        """Initialize cochlea fairy for audio analysis"""
        try:
            # Try v2 cochlea first
            from fairies.P40_Sensory.audio.cochlea_fairy import get_cochlea_fairy
            self._cochlea = get_cochlea_fairy()
        except ImportError:
            try:
                # Fallback to ebook cochlea
                from fairies.P40_Sensory.audio.cochlea_fairy import get_cochlea_fairy
                self._cochlea = get_cochlea_fairy()
            except ImportError:
                self.log("CochleaFairy not available - audio analysis limited")

    # =========================================================
    # MEDIA INFO EXTRACTION
    # =========================================================

    def _compute_hash(self, filepath: Path) -> str:
        """Compute SHA256 hash of file"""
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def _get_media_info(self, filepath: Path) -> Dict[str, Any]:
        """Get media information using ffprobe"""
        if not self._ffprobe_path:
            return {}

        try:
            cmd = [
                self._ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(filepath)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            self.log(f"ffprobe error: {e}")

        return {}

    # =========================================================
    # AUDIO EXTRACTION
    # =========================================================

    def _extract_audio_channel(
        self,
        media_path: Path,
        channel: str,
        duration_s: float = 60,
        skip_intro_s: float = 60
    ) -> Optional[Path]:
        """
        Extract a single audio channel to temp WAV file.

        Channels: 'L' (left), 'R' (right), 'C' (center), 'LFE', 'Ls', 'Rs', 'mono'
        """
        if not self._ffmpeg_path:
            return None

        temp_wav = Path(tempfile.mktemp(suffix=f'_{channel}.wav'))

        # Channel mapping for 5.1 surround: FL FR FC LFE BL BR
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
            self._ffmpeg_path, '-y',
            '-ss', str(skip_intro_s),  # Skip intro
            '-t', str(duration_s),
            '-i', str(media_path),
            '-vn',  # No video
            '-af', filter_arg,
            '-acodec', 'pcm_s16le',
            '-ar', '22050',
            '-ac', '1',
            str(temp_wav)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and temp_wav.exists():
                return temp_wav
        except Exception as e:
            self.log(f"Channel extraction error ({channel}): {e}")

        return None

    # =========================================================
    # SEED EXTRACTION
    # =========================================================

    def _extract_seeds_from_wav(self, wav_path: Path, channel: str) -> AudioChannelSeeds:
        """Extract dimensional seeds from a WAV file"""
        seeds = AudioChannelSeeds(channel=channel)

        if not self._cochlea:
            return seeds

        try:
            raw_seeds = self._cochlea.extract_all_seeds(str(wav_path))

            # Spectral features
            spectral = raw_seeds.get('spectral', {})
            seeds.mfcc_mean = self._to_list(spectral.get('mfcc_mean', []))
            seeds.mfcc_std = self._to_list(spectral.get('mfcc_std', []))
            seeds.chroma = self._to_list(spectral.get('chroma_mean', []))
            seeds.centroid = float(spectral.get('centroid_mean', 0))
            seeds.bandwidth = float(spectral.get('bandwidth_mean', 0))
            seeds.rolloff = float(spectral.get('rolloff_mean', 0))

            # Temporal features
            temporal = raw_seeds.get('temporal', {})
            seeds.tempo = float(temporal.get('tempo', 0))
            seeds.beats = int(temporal.get('n_beats', 0))
            seeds.onsets = int(temporal.get('n_onsets', 0))
            seeds.zcr = float(temporal.get('zcr_mean', 0))
            seeds.rms = float(temporal.get('rms_mean', 0))

            # Harmonic features
            harmonic = raw_seeds.get('harmonic', {})
            seeds.harmonic_ratio = float(harmonic.get('harmonic_ratio', 0))
            seeds.f0_mean = float(harmonic.get('f0_mean', 0))
            seeds.voiced_ratio = float(harmonic.get('voiced_ratio', 0))

        except Exception as e:
            self.log(f"Seed extraction error: {e}")

        return seeds

    def _to_list(self, arr) -> List[float]:
        """Convert numpy array or list to Python list of floats"""
        if hasattr(arr, 'tolist'):
            return [float(x) for x in arr.tolist()]
        elif isinstance(arr, list):
            return [float(x) for x in arr]
        return []

    # =========================================================
    # HELIX COORDINATE CALCULATION
    # =========================================================

    def _calculate_helix_coordinates(self, card: MediaMemoryCard) -> HelixCoordinate:
        """
        Calculate helix coordinates from the card's seeds.

        Affect: Derived from audio energy/tempo (emotional arousal)
        Semantic: Derived from content type and tags
        Temporal: Derived from duration and structure
        """
        # Affect axis (0-999) - Emotional dimension
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

        # Semantic axis (0-999) - Conceptual dimension
        # 700s = Arts, 800s = Literature/Stories
        semantic_domain = 7  # Arts (video/audio)
        if 'comedy' in card.tags or 'animation' in card.tags:
            semantic_subdomain = 9  # Comedy/Entertainment
        elif 'drama' in card.tags:
            semantic_subdomain = 5  # Drama
        elif 'music' in card.tags:
            semantic_subdomain = 8  # Music
        elif 'documentary' in card.tags:
            semantic_subdomain = 2  # Documentary
        else:
            semantic_subdomain = 0  # General
        semantic_detail = 0
        semantic = semantic_domain * 100 + semantic_subdomain * 10 + semantic_detail

        # Temporal axis (0-999) - Duration/structure dimension
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

    # =========================================================
    # MAIN INGESTION
    # =========================================================

    def ingest(
        self,
        filepath: str,
        tags: Optional[List[str]] = None,
        title: Optional[str] = None,
        sample_duration: float = 60.0,
        skip_intro: float = 60.0,
        extract_channels: bool = True
    ) -> MediaMemoryCard:
        """
        Ingest a media file into SRM memory.

        Args:
            filepath: Path to media file
            tags: Semantic tags for classification
            title: Human-readable title
            sample_duration: Seconds of audio to analyze (default 60)
            skip_intro: Seconds to skip at start (default 60)
            extract_channels: If True, extract L/R/C separately for stereo/5.1

        Returns:
            MediaMemoryCard with all dimensional seeds
        """
        filepath = Path(filepath)
        tags = tags or []

        self.log(f"Ingesting: {filepath.name}")
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
        mono_wav = self._extract_audio_channel(filepath, 'mono', sample_duration, skip_intro)
        if mono_wav:
            temp_files.append(mono_wav)
            card.mixed_seeds = self._extract_seeds_from_wav(mono_wav, 'mono')

        # Extract individual channels for 5.1/stereo
        if extract_channels and card.audio_channels >= 2:
            channels = ['L', 'R']
            if card.audio_channels >= 6:  # 5.1 surround
                channels.extend(['C', 'LFE', 'Ls', 'Rs'])

            for ch in channels:
                ch_wav = self._extract_audio_channel(filepath, ch, sample_duration, skip_intro)
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

        # Save card to storage
        with self._lock:
            card_path = self._storage_dir / f"{card_id}_{filepath.stem[:30]}.json"
            with open(card_path, 'w', encoding='utf-8') as f:
                json.dump(card.to_dict(), f, indent=2, default=str)

            # Update stats
            self._stats["files_ingested"] += 1
            self._stats["total_source_mb"] += card.source_size_mb
            self._stats["total_card_kb"] += card.size_kb

        elapsed = time.time() - start_time
        compression = (card.source_size_mb * 1024) / card.size_kb if card.size_kb > 0 else 0

        self.log(f"Complete: {card.title}")
        self.log(f"  Source: {card.source_size_mb:.1f} MB -> Card: {card.size_kb:.2f} KB ({compression:.0f}x)")
        self.log(f"  Helix: {card.helix.dewey_code}")
        self.log(f"  Channels: {len(card.channel_seeds)} ({', '.join(s.channel for s in card.channel_seeds)})")

        return card

    def load_card(self, card_id: str) -> Optional[MediaMemoryCard]:
        """Load a media memory card by ID"""
        with self._lock:
            for card_file in self._storage_dir.glob(f"{card_id}_*.json"):
                try:
                    with open(card_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Reconstruct card
                    card = MediaMemoryCard(
                        id=data['id'],
                        kind=data['kind'],
                        title=data.get('title', ''),
                        source_path=data.get('source_path', ''),
                        source_hash=data.get('source_hash', ''),
                        source_size_mb=data.get('source_size_mb', 0),
                        tags=data.get('tags', []),
                        created_at=data.get('created_at', 0),
                    )

                    # Helix
                    helix_data = data.get('helix', {})
                    card.helix = HelixCoordinate(
                        affect=helix_data.get('affect', 0),
                        semantic=helix_data.get('semantic', 0),
                        temporal=helix_data.get('temporal', 0),
                    )

                    # Video
                    card.video_width = data.get('video_width', 0)
                    card.video_height = data.get('video_height', 0)
                    card.video_fps = data.get('video_fps', 0)
                    card.video_duration_s = data.get('video_duration_s', 0)
                    card.video_codec = data.get('video_codec', '')

                    # Audio
                    card.audio_sample_rate = data.get('audio_sample_rate', 0)
                    card.audio_channels = data.get('audio_channels', 0)
                    card.audio_codec = data.get('audio_codec', '')

                    # Channel seeds
                    for cs_data in data.get('channel_seeds', []):
                        card.channel_seeds.append(AudioChannelSeeds(**cs_data))

                    # Mixed seeds
                    if data.get('mixed_seeds'):
                        card.mixed_seeds = AudioChannelSeeds(**data['mixed_seeds'])

                    return card

                except Exception as e:
                    self.log(f"Error loading card {card_id}: {e}")

        return None

    def list_cards(self) -> List[Dict[str, Any]]:
        """List all stored media cards"""
        cards = []
        with self._lock:
            for card_file in self._storage_dir.glob("*.json"):
                try:
                    with open(card_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    cards.append({
                        "id": data.get('id'),
                        "title": data.get('title'),
                        "helix": data.get('helix', {}).get('dewey_code',
                            f"{data.get('helix',{}).get('affect',0):03d}." +
                            f"{data.get('helix',{}).get('semantic',0):03d}." +
                            f"{data.get('helix',{}).get('temporal',0):03d}"
                        ) if isinstance(data.get('helix'), dict) else '000.000.000',
                        "kind": data.get('kind'),
                        "source_size_mb": data.get('source_size_mb'),
                    })
                except:
                    pass
        return cards

    def get_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        with self._lock:
            avg_compression = 0
            if self._stats["total_card_kb"] > 0:
                avg_compression = (self._stats["total_source_mb"] * 1024) / self._stats["total_card_kb"]

            return {
                **self._stats,
                "average_compression": round(avg_compression, 1),
                "ffmpeg_available": self._ffmpeg_path is not None,
                "cochlea_available": self._cochlea is not None,
            }


# =========================================================
# SINGLETON ACCESS
# =========================================================

_media_ingest_fairy: Optional[MediaIngestFairy] = None

def get_media_ingest_fairy() -> MediaIngestFairy:
    """Get singleton MediaIngestFairy instance"""
    global _media_ingest_fairy
    if _media_ingest_fairy is None:
        _media_ingest_fairy = MediaIngestFairy()
    return _media_ingest_fairy

def set_media_ingest_fairy(fairy: MediaIngestFairy):
    """Set the singleton instance (for testing/custom config)"""
    global _media_ingest_fairy
    _media_ingest_fairy = fairy


# =========================================================
# CLI
# =========================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest media into SRM memory")
    parser.add_argument("filepath", help="Path to media file")
    parser.add_argument("--tags", nargs="*", default=[], help="Tags for classification")
    parser.add_argument("--title", help="Human-readable title")
    parser.add_argument("--duration", type=float, default=60, help="Sample duration (seconds)")
    parser.add_argument("--skip", type=float, default=60, help="Skip intro (seconds)")
    parser.add_argument("--no-channels", action="store_true", help="Skip channel separation")

    args = parser.parse_args()

    fairy = get_media_ingest_fairy()
    fairy.on_boot()

    card = fairy.ingest(
        args.filepath,
        tags=args.tags,
        title=args.title,
        sample_duration=args.duration,
        skip_intro=args.skip,
        extract_channels=not args.no_channels
    )

    print(f"\nCard ID: {card.id}")
    print(f"Helix: {card.helix.dewey_code}")
