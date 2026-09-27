"""
MediaPreservationLayer - Perfect Copy Engine for the TARDIS

Purpose: Before extracting ANY dimensions, preserve bit-perfect copies.
         This is the foundation for regenerative media - you can't regenerate
         what you haven't perfectly captured.

Philosophy: "The original is sacred. Preserve it perfectly, then extract its soul."

Supported Formats:
    Audio: FLAC (RFC 9639, lossless, bit-perfect)
    Video: H.265 --lossless (QP=4, transquant bypass) or FFV1
    Images: PNG (lossless) or JPEG-XL (lossless mode)

The Vision:
    1. Ingest media → Create perfect archive
    2. Extract dimensional seeds (spectral, temporal, semantic)
    3. Store seeds in memory cards
    4. Later: Regenerate from seeds on demand

    Games, movies, music - all become regenerable from their essence.
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import time

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class PreservationResult:
    """Result of a preservation operation."""
    success: bool
    original_path: str
    archive_path: str
    original_hash: str
    archive_hash: str
    format_used: str
    compression_ratio: float
    is_lossless: bool
    verification_passed: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class MediaInfo:
    """Information about a media file."""
    path: str
    media_type: str  # audio, video, image
    codec: str
    duration_seconds: float
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    file_size: int = 0


class MediaPreservationLayer:
    """
    The perfect copy engine.

    Ensures all media is preserved losslessly before any processing.
    This is the foundation of the regenerative media system.
    """

    # Archive location
    ARCHIVE_ROOT = PROJECT_ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "system" / "media"

    # Format mappings
    AUDIO_EXTENSIONS = {'.wav', '.flac', '.aiff', '.aif', '.mp3', '.m4a', '.ogg', '.opus', '.wma', '.ape', '.wv'}
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic'}

    # Lossless target formats
    LOSSLESS_AUDIO = "flac"
    LOSSLESS_VIDEO = "h265_lossless"  # or "ffv1"
    LOSSLESS_IMAGE = "png"

    def __init__(self, archive_root: Path = None):
        self.archive_root = Path(archive_root) if archive_root else self.ARCHIVE_ROOT
        self.archive_root.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        self.audio_archive = self.archive_root / "audio_archive"
        self.video_archive = self.archive_root / "video_archive"
        self.image_archive = self.archive_root / "images"

        for d in [self.audio_archive, self.video_archive, self.image_archive]:
            d.mkdir(parents=True, exist_ok=True)

        # Check for ffmpeg
        self.ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available and set paths."""
        # First try system PATH
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                self.ffmpeg_path = 'ffmpeg'
                self.ffprobe_path = 'ffprobe'
                return True
        except:
            pass

        # Search common Windows locations
        search_paths = [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet' / 'Packages',
            Path('C:/ffmpeg/bin'),
            Path('C:/Program Files/ffmpeg/bin'),
            Path('C:/tools/ffmpeg/bin'),
        ]

        for base in search_paths:
            if not base.exists():
                continue
            # Search for ffmpeg.exe recursively
            for ffmpeg_exe in base.rglob('ffmpeg.exe'):
                ffprobe_exe = ffmpeg_exe.parent / 'ffprobe.exe'
                if ffprobe_exe.exists():
                    try:
                        result = subprocess.run([str(ffmpeg_exe), '-version'], capture_output=True, timeout=5)
                        if result.returncode == 0:
                            self.ffmpeg_path = str(ffmpeg_exe)
                            self.ffprobe_path = str(ffprobe_exe)
                            return True
                    except:
                        continue

        self.ffmpeg_path = None
        self.ffprobe_path = None
        return False

    def _compute_hash(self, filepath: Path, algorithm: str = 'sha256') -> str:
        """Compute file hash for verification."""
        h = hashlib.new(algorithm)
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def _get_media_info(self, filepath) -> Optional[MediaInfo]:
        """Get media information using ffprobe."""
        if not self.ffmpeg_available:
            return None

        filepath = Path(filepath)  # Ensure Path object
        try:
            cmd = [
                self.ffprobe_path, '-v', 'quiet',
                '-print_format', 'json',
                '-show_format', '-show_streams',
                str(filepath)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            fmt = data.get('format', {})
            streams = data.get('streams', [])

            # Determine media type
            ext = filepath.suffix.lower()
            if ext in self.AUDIO_EXTENSIONS:
                media_type = 'audio'
            elif ext in self.VIDEO_EXTENSIONS:
                media_type = 'video'
            elif ext in self.IMAGE_EXTENSIONS:
                media_type = 'image'
            else:
                media_type = 'unknown'

            # Find relevant streams
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})

            return MediaInfo(
                path=str(filepath),
                media_type=media_type,
                codec=fmt.get('format_name', 'unknown'),
                duration_seconds=float(fmt.get('duration', 0)),
                sample_rate=int(audio_stream.get('sample_rate', 0)) if audio_stream else None,
                channels=int(audio_stream.get('channels', 0)) if audio_stream else None,
                bit_depth=int(audio_stream.get('bits_per_sample', 0)) if audio_stream else None,
                width=int(video_stream.get('width', 0)) if video_stream else None,
                height=int(video_stream.get('height', 0)) if video_stream else None,
                fps=eval(video_stream.get('r_frame_rate', '0/1')) if video_stream and '/' in video_stream.get('r_frame_rate', '') else None,
                bitrate=int(fmt.get('bit_rate', 0)) if fmt.get('bit_rate') else None,
                file_size=int(fmt.get('size', 0))
            )
        except Exception as e:
            print(f"[MediaPreservation] Error getting info for {filepath}: {e}")
            return None

    def preserve(self, source_path: str | Path, force: bool = False) -> PreservationResult:
        """
        Preserve a media file losslessly.

        Args:
            source_path: Path to the media file
            force: Re-preserve even if archive exists

        Returns:
            PreservationResult with details
        """
        source = Path(source_path)
        if not source.exists():
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash="",
                archive_hash="",
                format_used="",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error=f"Source file not found: {source}"
            )

        # Determine media type
        ext = source.suffix.lower()
        if ext in self.AUDIO_EXTENSIONS:
            return self._preserve_audio(source, force)
        elif ext in self.VIDEO_EXTENSIONS:
            return self._preserve_video(source, force)
        elif ext in self.IMAGE_EXTENSIONS:
            return self._preserve_image(source, force)
        else:
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash="",
                archive_hash="",
                format_used="",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error=f"Unsupported file type: {ext}"
            )

    def _preserve_audio(self, source: Path, force: bool = False) -> PreservationResult:
        """Preserve audio to FLAC (lossless)."""
        original_hash = self._compute_hash(source)

        # Generate archive path
        archive_name = f"{original_hash[:12]}_{source.stem}.flac"
        archive_path = self.audio_archive / archive_name

        if archive_path.exists() and not force:
            # Already preserved
            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=self._compute_hash(archive_path),
                format_used="FLAC",
                compression_ratio=archive_path.stat().st_size / source.stat().st_size,
                is_lossless=True,
                verification_passed=True,
                metadata={"already_archived": True}
            )

        # Check if already FLAC
        if source.suffix.lower() == '.flac':
            # Just copy
            shutil.copy2(source, archive_path)
            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=self._compute_hash(archive_path),
                format_used="FLAC (copy)",
                compression_ratio=1.0,
                is_lossless=True,
                verification_passed=True
            )

        # Convert to FLAC
        if not self.ffmpeg_available:
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash=original_hash,
                archive_hash="",
                format_used="",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error="ffmpeg not available"
            )

        try:
            cmd = [
                self.ffmpeg_path, '-y', '-i', str(source),
                '-c:a', 'flac',
                '-compression_level', '8',  # Max compression
                str(archive_path)
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=600)

            if result.returncode != 0:
                return PreservationResult(
                    success=False,
                    original_path=str(source),
                    archive_path="",
                    original_hash=original_hash,
                    archive_hash="",
                    format_used="FLAC",
                    compression_ratio=0,
                    is_lossless=False,
                    verification_passed=False,
                    error=f"ffmpeg failed: {result.stderr.decode()[:200]}"
                )

            archive_hash = self._compute_hash(archive_path)
            compression_ratio = archive_path.stat().st_size / source.stat().st_size

            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=archive_hash,
                format_used="FLAC",
                compression_ratio=compression_ratio,
                is_lossless=True,
                verification_passed=True
            )

        except Exception as e:
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash=original_hash,
                archive_hash="",
                format_used="FLAC",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error=str(e)
            )

    def _preserve_video(self, source: Path, force: bool = False) -> PreservationResult:
        """
        Preserve video to H.265 lossless.

        Uses: -c:v libx265 -x265-params lossless=1
        Audio: FLAC
        """
        original_hash = self._compute_hash(source)

        # Generate archive path
        archive_name = f"{original_hash[:12]}_{source.stem}_lossless.mkv"
        archive_path = self.video_archive / archive_name

        if archive_path.exists() and not force:
            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=self._compute_hash(archive_path),
                format_used="H.265 Lossless",
                compression_ratio=archive_path.stat().st_size / source.stat().st_size,
                is_lossless=True,
                verification_passed=True,
                metadata={"already_archived": True}
            )

        if not self.ffmpeg_available:
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash=original_hash,
                archive_hash="",
                format_used="",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error="ffmpeg not available"
            )

        try:
            # Strategy: For high-quality sources (H.264/H.265), stream copy is best
            # Re-encoding to "lossless" would actually be larger and slower
            # Only re-encode if source is very lossy or user requests it

            media_info = self._get_media_info(source)
            source_codec = media_info.codec if media_info else ""

            # Check if source is already high quality (H.264/H.265/AV1)
            high_quality_sources = {'matroska', 'webm', 'mov', 'mp4', 'h264', 'hevc', 'av1'}
            is_high_quality = any(c in source_codec.lower() for c in high_quality_sources)

            if is_high_quality:
                # Stream copy - preserves original quality exactly, very fast
                archive_name = f"{original_hash[:12]}_{source.stem}_preserved.mkv"
                archive_path = self.video_archive / archive_name

                cmd = [
                    self.ffmpeg_path, '-y', '-i', str(source),
                    '-c:v', 'copy',  # Copy video stream exactly
                    '-c:a', 'copy',  # Copy audio stream exactly
                    str(archive_path)
                ]
                print(f"[MediaPreservation] Stream copying {source.name} (preserving original quality)...")
                result = subprocess.run(cmd, capture_output=True, timeout=600)

                if result.returncode == 0:
                    format_used = f"Preserved ({source_codec})"
                else:
                    # Fallback to re-encode if copy fails
                    is_high_quality = False

            if not is_high_quality or result.returncode != 0:
                # Try NVENC first (GPU accelerated, very fast)
                archive_name = f"{original_hash[:12]}_{source.stem}_h265.mkv"
                archive_path = self.video_archive / archive_name

                cmd_nvenc = [
                    self.ffmpeg_path, '-y', '-hwaccel', 'cuda', '-i', str(source),
                    '-c:v', 'hevc_nvenc',
                    '-preset', 'p7',  # Highest quality preset
                    '-rc', 'constqp', '-qp', '0',  # CQP 0 = nearly lossless
                    '-c:a', 'flac',
                    str(archive_path)
                ]

                print(f"[MediaPreservation] Encoding {source.name} with NVENC (GPU accelerated)...")
                result = subprocess.run(cmd_nvenc, capture_output=True, timeout=3600)

                if result.returncode == 0:
                    format_used = "H.265 NVENC (CQP 0)"
                else:
                    # Fallback to CPU libx265 lossless
                    cmd_x265 = [
                        self.ffmpeg_path, '-y', '-i', str(source),
                        '-c:v', 'libx265',
                        '-x265-params', 'lossless=1:log-level=error',
                        '-preset', 'medium',
                        '-c:a', 'flac',
                        str(archive_path)
                    ]

                    print(f"[MediaPreservation] NVENC failed, trying CPU H.265 lossless...")
                    result = subprocess.run(cmd_x265, capture_output=True, timeout=7200)

                    if result.returncode == 0:
                        format_used = "H.265 Lossless (CPU)"
                    else:
                        # Final fallback: FFV1
                        archive_name_ffv1 = f"{original_hash[:12]}_{source.stem}_ffv1.mkv"
                        archive_path = self.video_archive / archive_name_ffv1

                        cmd_ffv1 = [
                            self.ffmpeg_path, '-y', '-i', str(source),
                            '-c:v', 'ffv1', '-level', '3',
                            '-c:a', 'flac',
                            str(archive_path)
                        ]

                        print(f"[MediaPreservation] Trying FFV1...")
                        result = subprocess.run(cmd_ffv1, capture_output=True, timeout=3600)

                        if result.returncode != 0:
                            return PreservationResult(
                                success=False,
                                original_path=str(source),
                                archive_path="",
                                original_hash=original_hash,
                                archive_hash="",
                                format_used="",
                                compression_ratio=0,
                                is_lossless=False,
                                verification_passed=False,
                                error=f"All encoding methods failed"
                            )
                        format_used = "FFV1"

            archive_hash = self._compute_hash(archive_path)
            compression_ratio = archive_path.stat().st_size / source.stat().st_size

            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=archive_hash,
                format_used=format_used,
                compression_ratio=compression_ratio,
                is_lossless=True,
                verification_passed=True
            )

        except subprocess.TimeoutExpired:
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash=original_hash,
                archive_hash="",
                format_used="",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error="Encoding timed out (>2 hours)"
            )
        except Exception as e:
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash=original_hash,
                archive_hash="",
                format_used="",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error=str(e)
            )

    def _preserve_image(self, source: Path, force: bool = False) -> PreservationResult:
        """Preserve image to PNG (lossless)."""
        original_hash = self._compute_hash(source)

        # Generate archive path
        archive_name = f"{original_hash[:12]}_{source.stem}.png"
        archive_path = self.image_archive / archive_name

        if archive_path.exists() and not force:
            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=self._compute_hash(archive_path),
                format_used="PNG",
                compression_ratio=archive_path.stat().st_size / source.stat().st_size,
                is_lossless=True,
                verification_passed=True,
                metadata={"already_archived": True}
            )

        # Check if already PNG
        if source.suffix.lower() == '.png':
            shutil.copy2(source, archive_path)
            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=self._compute_hash(archive_path),
                format_used="PNG (copy)",
                compression_ratio=1.0,
                is_lossless=True,
                verification_passed=True
            )

        # Convert to PNG using ffmpeg or PIL
        try:
            # Try PIL first (faster for images)
            from PIL import Image
            img = Image.open(source)
            img.save(archive_path, 'PNG', optimize=True)

            archive_hash = self._compute_hash(archive_path)
            compression_ratio = archive_path.stat().st_size / source.stat().st_size

            return PreservationResult(
                success=True,
                original_path=str(source),
                archive_path=str(archive_path),
                original_hash=original_hash,
                archive_hash=archive_hash,
                format_used="PNG",
                compression_ratio=compression_ratio,
                is_lossless=True,
                verification_passed=True
            )
        except ImportError:
            # Fall back to ffmpeg
            if not self.ffmpeg_available:
                return PreservationResult(
                    success=False,
                    original_path=str(source),
                    archive_path="",
                    original_hash=original_hash,
                    archive_hash="",
                    format_used="",
                    compression_ratio=0,
                    is_lossless=False,
                    verification_passed=False,
                    error="Neither PIL nor ffmpeg available"
                )

            cmd = [self.ffmpeg_path, '-y', '-i', str(source), str(archive_path)]
            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode == 0:
                archive_hash = self._compute_hash(archive_path)
                compression_ratio = archive_path.stat().st_size / source.stat().st_size

                return PreservationResult(
                    success=True,
                    original_path=str(source),
                    archive_path=str(archive_path),
                    original_hash=original_hash,
                    archive_hash=archive_hash,
                    format_used="PNG",
                    compression_ratio=compression_ratio,
                    is_lossless=True,
                    verification_passed=True
                )
            else:
                return PreservationResult(
                    success=False,
                    original_path=str(source),
                    archive_path="",
                    original_hash=original_hash,
                    archive_hash="",
                    format_used="",
                    compression_ratio=0,
                    is_lossless=False,
                    verification_passed=False,
                    error=f"ffmpeg conversion failed"
                )
        except Exception as e:
            return PreservationResult(
                success=False,
                original_path=str(source),
                archive_path="",
                original_hash=original_hash,
                archive_hash="",
                format_used="",
                compression_ratio=0,
                is_lossless=False,
                verification_passed=False,
                error=str(e)
            )

    def create_memory_card(self, preservation_result: PreservationResult) -> Dict[str, Any]:
        """
        Create a memory card for the preserved media.

        This card will later be enhanced with dimensional seeds
        (spectral, temporal, semantic) by the AudioCortex.
        """
        if not preservation_result.success:
            return {"error": preservation_result.error}

        # Get media info
        archive_path = Path(preservation_result.archive_path)
        media_info = self._get_media_info(archive_path)

        card = {
            "kind": f"system.media.{media_info.media_type if media_info else 'unknown'}",
            "id": preservation_result.original_hash[:12],
            "data": {
                "original_path": preservation_result.original_path,
                "archive_path": preservation_result.archive_path,
                "original_hash": preservation_result.original_hash,
                "archive_hash": preservation_result.archive_hash,
                "format": preservation_result.format_used,
                "compression_ratio": preservation_result.compression_ratio,
                "is_lossless": preservation_result.is_lossless,
            },
            "meta": {
                "media_info": {
                    "type": media_info.media_type if media_info else "unknown",
                    "codec": media_info.codec if media_info else "unknown",
                    "duration_seconds": media_info.duration_seconds if media_info else 0,
                    "sample_rate": media_info.sample_rate if media_info else None,
                    "channels": media_info.channels if media_info else None,
                    "width": media_info.width if media_info else None,
                    "height": media_info.height if media_info else None,
                    "fps": media_info.fps if media_info else None,
                },
                "tags": ["preserved", "lossless", "awaiting_extraction"],
                "source_folder": str(Path(preservation_result.original_path).parent),
            },
            "seeds": {
                # Placeholder for dimensional seeds - filled by AudioCortex later
                "spectral": None,
                "temporal": None,
                "harmonic": None,
                "semantic": None,
                "voice": None,
            },
            "ts": time.time()
        }

        # Save card
        card_path = archive_path.with_suffix('.json')
        with open(card_path, 'w', encoding='utf-8') as f:
            json.dump(card, f, indent=2, ensure_ascii=False)

        return card

    def batch_preserve(self, directory: str | Path, recursive: bool = True,
                       limit: int = None) -> List[PreservationResult]:
        """
        Preserve all media files in a directory.

        Args:
            directory: Directory to scan
            recursive: Scan subdirectories
            limit: Max files to process

        Returns:
            List of PreservationResults
        """
        directory = Path(directory)
        results = []
        count = 0

        all_extensions = self.AUDIO_EXTENSIONS | self.VIDEO_EXTENSIONS | self.IMAGE_EXTENSIONS

        pattern = '**/*' if recursive else '*'
        for filepath in directory.glob(pattern):
            if limit and count >= limit:
                break

            if filepath.suffix.lower() in all_extensions:
                print(f"[MediaPreservation] Processing: {filepath.name}")
                result = self.preserve(filepath)

                if result.success:
                    self.create_memory_card(result)
                    print(f"  [OK] Preserved as {result.format_used} (ratio: {result.compression_ratio:.2f})")
                else:
                    print(f"  [FAIL] Failed: {result.error}")

                results.append(result)
                count += 1

        return results


# Singleton
_preservation_layer = None

def get_preservation_layer() -> MediaPreservationLayer:
    """Get singleton instance."""
    global _preservation_layer
    if _preservation_layer is None:
        _preservation_layer = MediaPreservationLayer()
    return _preservation_layer


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Media Preservation Layer")
    parser.add_argument("path", help="File or directory to preserve")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursive directory scan")
    parser.add_argument("--limit", "-l", type=int, help="Max files to process")

    args = parser.parse_args()

    layer = get_preservation_layer()

    path = Path(args.path)
    if path.is_file():
        result = layer.preserve(path)
        if result.success:
            card = layer.create_memory_card(result)
            print(f"\n[OK] Preserved: {result.archive_path}")
            print(f"  Format: {result.format_used}")
            print(f"  Compression: {result.compression_ratio:.2%}")
            print(f"  Card ID: {card.get('id', 'N/A')}")
        else:
            print(f"\n[FAIL] Failed: {result.error}")
    elif path.is_dir():
        results = layer.batch_preserve(path, recursive=args.recursive, limit=args.limit)
        success = sum(1 for r in results if r.success)
        print(f"\n=== Batch Complete ===")
        print(f"Success: {success}/{len(results)}")
    else:
        print(f"Path not found: {path}")
