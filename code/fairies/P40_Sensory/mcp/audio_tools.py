"""
Audio Cortex MCP Tools

Provides tools for:
- Media preservation (lossless archival)
- Audio seed extraction (spectral, temporal, harmonic)
- Cochlear processing (tonotopic analysis)
"""

import sys
import json
from pathlib import Path

# Add project root
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def register_audio_tools(mcp):
    """Register audio processing tools with MCP server."""

    @mcp.tool()
    def preserve_media(
        path: str,
        force: bool = False
    ) -> str:
        """
        Preserve media file losslessly to the archive.

        Creates bit-perfect copies:
        - Audio → FLAC (lossless)
        - Video → H.265 lossless or FFV1
        - Images → PNG (lossless)

        Args:
            path: Path to media file (audio, video, or image)
            force: Re-preserve even if already archived

        Returns:
            JSON with preservation result and memory card
        """
        try:
            from fairies.P40_Sensory.audio.media_preservation_layer import get_preservation_layer

            layer = get_preservation_layer()
            result = layer.preserve(path, force=force)

            if result.success:
                card = layer.create_memory_card(result)
                return json.dumps({
                    "success": True,
                    "archive_path": result.archive_path,
                    "format": result.format_used,
                    "compression_ratio": round(result.compression_ratio, 3),
                    "is_lossless": result.is_lossless,
                    "card_id": card.get("id", ""),
                    "original_hash": result.original_hash[:16]
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "error": result.error
                })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def batch_preserve_media(
        directory: str,
        recursive: bool = True,
        limit: int = 100
    ) -> str:
        """
        Preserve all media files in a directory.

        Args:
            directory: Directory to scan
            recursive: Include subdirectories
            limit: Maximum files to process

        Returns:
            JSON with batch results
        """
        try:
            from fairies.P40_Sensory.audio.media_preservation_layer import get_preservation_layer

            layer = get_preservation_layer()
            results = layer.batch_preserve(directory, recursive=recursive, limit=limit)

            success_count = sum(1 for r in results if r.success)
            failed = [{"path": r.original_path, "error": r.error}
                      for r in results if not r.success]

            return json.dumps({
                "total": len(results),
                "success": success_count,
                "failed": len(failed),
                "failed_files": failed[:10],  # First 10 failures
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def extract_audio_seeds(
        audio_path: str
    ) -> str:
        """
        Extract all dimensional seeds from an audio file.

        Seeds extracted:
        - Spectral: mel, mfcc, chroma, centroid, bandwidth, rolloff
        - Temporal: zcr, rms, tempo, beats, onsets
        - Harmonic: harmonic/percussive ratio, f0, voiced ratio

        These seeds can later be used to regenerate or search audio.

        Args:
            audio_path: Path to audio file

        Returns:
            JSON with all extracted seeds
        """
        try:
            from fairies.P40_Sensory.audio.cochlea_fairy import get_cochlea_fairy

            fairy = get_cochlea_fairy()
            seeds = fairy.extract_all_seeds(audio_path)

            return json.dumps({
                "success": True,
                "path": audio_path,
                "seeds": seeds
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def analyze_audio_cochlea(
        audio_path: str
    ) -> str:
        """
        Process audio through cochlear simulation.

        Returns tonotopic analysis mimicking human cochlea:
        - Frequency decomposition (20Hz-20kHz, 128 channels)
        - Level estimation
        - Temporal envelope

        Args:
            audio_path: Path to audio file

        Returns:
            JSON with cochlear analysis
        """
        try:
            from fairies.P40_Sensory.audio.cochlea_fairy import get_cochlea_fairy

            fairy = get_cochlea_fairy()
            output = fairy.process(audio_path)

            return json.dumps({
                "success": True,
                "path": audio_path,
                "analysis": output.to_dict()
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_media_preservation_stats() -> str:
        """
        Get statistics about the media archive.

        Returns:
            JSON with archive statistics
        """
        try:
            from fairies.P40_Sensory.audio.media_preservation_layer import get_preservation_layer

            layer = get_preservation_layer()

            # Count files in each archive
            audio_count = len(list(layer.audio_archive.glob("*.flac")))
            video_count = len(list(layer.video_archive.glob("*.mkv")))
            image_count = len(list(layer.image_archive.glob("*.png")))

            # Calculate total size
            def dir_size(path):
                return sum(f.stat().st_size for f in path.glob("*") if f.is_file())

            audio_size = dir_size(layer.audio_archive)
            video_size = dir_size(layer.video_archive)
            image_size = dir_size(layer.image_archive)

            return json.dumps({
                "archive_root": str(layer.archive_root),
                "audio": {
                    "count": audio_count,
                    "size_mb": round(audio_size / (1024 * 1024), 2)
                },
                "video": {
                    "count": video_count,
                    "size_mb": round(video_size / (1024 * 1024), 2)
                },
                "images": {
                    "count": image_count,
                    "size_mb": round(image_size / (1024 * 1024), 2)
                },
                "total_size_gb": round((audio_size + video_size + image_size) / (1024 ** 3), 2),
                "ffmpeg_available": layer.ffmpeg_available
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    print("[AudioTools] Registered: preserve_media, batch_preserve_media, extract_audio_seeds, analyze_audio_cochlea, get_media_preservation_stats")
