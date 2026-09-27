#!/usr/bin/env python3
"""
Test Video Processing Pipeline
==============================

Tests the full video pipeline on an MKV file:
1. Extract frames at regular intervals (1 per 10 seconds)
2. Run visual feature extraction on each frame
3. Extract audio track
4. Run audio feature extraction (cochlear analysis)
5. Report all extracted features

Usage:
    python test_video_processing.py <path_to_video>
    python test_video_processing.py  # Uses default American Dad episode
"""

from __future__ import annotations

import os
import sys
import time
import json
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Try to import required libraries
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("[WARN] OpenCV not available - video frame extraction disabled")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("[WARN] numpy not available")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[WARN] Pillow not available")

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("[WARN] librosa not available - audio analysis disabled")


# ===========================================================================
# FFMPEG UTILITIES
# ===========================================================================

def find_ffmpeg() -> Tuple[Optional[str], Optional[str]]:
    """Find ffmpeg and ffprobe executables."""
    ffmpeg_path = None
    ffprobe_path = None

    # Check PATH
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            ffmpeg_path = 'ffmpeg'
            ffprobe_path = 'ffprobe'
            return ffmpeg_path, ffprobe_path
    except:
        pass

    # Check WinGet location (Windows)
    winget_base = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet' / 'Packages'
    if winget_base.exists():
        for ffmpeg_exe in winget_base.rglob('ffmpeg.exe'):
            ffmpeg_path = str(ffmpeg_exe)
            ffprobe = ffmpeg_exe.parent / 'ffprobe.exe'
            if ffprobe.exists():
                ffprobe_path = str(ffprobe)
            return ffmpeg_path, ffprobe_path

    return ffmpeg_path, ffprobe_path


def get_video_info(video_path: str, ffprobe_path: str) -> Dict[str, Any]:
    """Get video metadata using ffprobe."""
    try:
        cmd = [
            ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] ffprobe failed: {e}")
    return {}


# ===========================================================================
# FRAME EXTRACTION
# ===========================================================================

@dataclass
class FrameInfo:
    """Information about an extracted frame."""
    frame_number: int
    timestamp_s: float
    width: int
    height: int
    brightness: float  # 0-1
    complexity: float  # 0-1 (unique colors / max colors)
    dominant_color: Tuple[int, int, int]
    has_text_regions: bool
    hash: str


def extract_frames_cv2(
    video_path: str,
    interval_s: float = 10.0,
    max_frames: int = 200
) -> List[Tuple[float, np.ndarray]]:
    """Extract frames at regular intervals using OpenCV."""
    if not HAS_OPENCV:
        print("[ERROR] OpenCV required for frame extraction")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total_frames / fps if fps > 0 else 0

    print(f"[INFO] Video: {fps:.1f} FPS, {total_frames} frames, {duration_s:.1f} seconds")

    frames = []
    interval_frames = int(interval_s * fps)

    frame_idx = 0
    while True:
        if len(frames) >= max_frames:
            print(f"[INFO] Reached max frames limit ({max_frames})")
            break

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            break

        timestamp_s = frame_idx / fps
        frames.append((timestamp_s, frame))

        print(f"  [FRAME] {len(frames):3d}: {timestamp_s:6.1f}s (frame {frame_idx})")

        frame_idx += interval_frames

    cap.release()
    print(f"[INFO] Extracted {len(frames)} frames")
    return frames


def analyze_frame(frame: np.ndarray, timestamp_s: float, frame_number: int) -> FrameInfo:
    """Analyze a single frame for visual features."""
    height, width = frame.shape[:2]

    # Convert to RGB for analysis
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Brightness (average luminance)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray) / 255.0)

    # Complexity (unique colors as proxy)
    # Downsample for speed
    small = cv2.resize(rgb_frame, (100, 100))
    flat = small.reshape(-1, 3)
    unique_colors = len(np.unique(flat, axis=0))
    complexity = unique_colors / 10000.0  # Max possible is 10000

    # Dominant color (most common in k-means)
    # Simplified: just use average color
    avg_color = tuple(int(x) for x in np.mean(flat, axis=0))

    # Text detection heuristic (edge density in grayscale)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / edges.size
    has_text_regions = edge_density > 0.1  # Arbitrary threshold

    # Perceptual hash (simplified - just MD5 of downscaled)
    hash_data = cv2.resize(gray, (8, 8)).tobytes()
    frame_hash = hashlib.md5(hash_data).hexdigest()[:16]

    return FrameInfo(
        frame_number=frame_number,
        timestamp_s=timestamp_s,
        width=width,
        height=height,
        brightness=brightness,
        complexity=complexity,
        dominant_color=avg_color,
        has_text_regions=has_text_regions,
        hash=frame_hash
    )


# ===========================================================================
# AUDIO EXTRACTION AND ANALYSIS
# ===========================================================================

@dataclass
class AudioInfo:
    """Information about extracted audio."""
    duration_s: float
    sample_rate: int
    channels: int
    codec: str


@dataclass
class AudioFeatures:
    """Audio feature analysis results."""
    duration_s: float
    tempo: float
    n_beats: int
    spectral_centroid_mean: float
    spectral_bandwidth_mean: float
    rms_mean: float
    zcr_mean: float
    harmonic_ratio: float
    mfcc_summary: List[float]  # First 5 MFCCs mean
    chroma_summary: List[float]  # 12 chroma bins mean


def extract_audio(
    video_path: str,
    ffmpeg_path: str,
    output_path: Optional[str] = None,
    duration_s: Optional[float] = None
) -> Optional[str]:
    """Extract audio track to WAV file."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')

    cmd = [
        ffmpeg_path, '-y',
        '-i', video_path,
        '-vn',  # No video
        '-acodec', 'pcm_s16le',
        '-ar', '22050',
        '-ac', '1',  # Mono
    ]

    if duration_s:
        cmd.extend(['-t', str(duration_s)])

    cmd.append(output_path)

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0 and Path(output_path).exists():
            print(f"[INFO] Audio extracted to: {output_path}")
            return output_path
        else:
            print(f"[ERROR] FFmpeg failed: {result.stderr.decode()[:500]}")
    except Exception as e:
        print(f"[ERROR] Audio extraction failed: {e}")

    return None


def analyze_audio(wav_path: str) -> Optional[AudioFeatures]:
    """Analyze audio file with librosa."""
    if not HAS_LIBROSA:
        print("[ERROR] librosa required for audio analysis")
        return None

    try:
        print("[INFO] Loading audio...")
        y, sr = librosa.load(wav_path, sr=22050, mono=True)
        duration_s = len(y) / sr
        print(f"[INFO] Audio: {duration_s:.1f}s, {sr}Hz sample rate")

        # Tempo and beats
        print("[INFO] Analyzing tempo...")
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        tempo_val = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        # Spectral features
        print("[INFO] Extracting spectral features...")
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)

        # Energy features
        print("[INFO] Extracting energy features...")
        rms = librosa.feature.rms(y=y)
        zcr = librosa.feature.zero_crossing_rate(y=y)

        # Harmonic/percussive
        print("[INFO] Harmonic-percussive separation...")
        harmonic, percussive = librosa.effects.hpss(y)
        h_energy = np.sum(harmonic ** 2)
        p_energy = np.sum(percussive ** 2)
        harmonic_ratio = h_energy / (h_energy + p_energy + 1e-10)

        # MFCCs
        print("[INFO] Extracting MFCCs...")
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_summary = [float(x) for x in mfcc[:5].mean(axis=1)]

        # Chroma
        print("[INFO] Extracting chroma...")
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_summary = [float(x) for x in chroma.mean(axis=1)]

        return AudioFeatures(
            duration_s=duration_s,
            tempo=tempo_val,
            n_beats=len(beat_frames),
            spectral_centroid_mean=float(spectral_centroid.mean()),
            spectral_bandwidth_mean=float(spectral_bandwidth.mean()),
            rms_mean=float(rms.mean()),
            zcr_mean=float(zcr.mean()),
            harmonic_ratio=float(harmonic_ratio),
            mfcc_summary=mfcc_summary,
            chroma_summary=chroma_summary
        )

    except Exception as e:
        print(f"[ERROR] Audio analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ===========================================================================
# MAIN TEST
# ===========================================================================

def test_video_processing(video_path: str) -> Dict[str, Any]:
    """
    Run full video processing test.

    Returns dict with all extracted features and timing info.
    """
    results = {
        "video_path": video_path,
        "test_start": time.time(),
        "dependencies": {
            "opencv": HAS_OPENCV,
            "numpy": HAS_NUMPY,
            "pillow": HAS_PIL,
            "librosa": HAS_LIBROSA
        },
        "frames": [],
        "audio": None,
        "errors": [],
        "timing": {}
    }

    # Find FFmpeg
    print("\n" + "="*60)
    print("FINDING FFMPEG")
    print("="*60)

    ffmpeg_path, ffprobe_path = find_ffmpeg()
    if ffmpeg_path:
        print(f"[OK] FFmpeg: {ffmpeg_path}")
        print(f"[OK] FFprobe: {ffprobe_path}")
        results["ffmpeg"] = ffmpeg_path
    else:
        print("[ERROR] FFmpeg not found!")
        results["errors"].append("FFmpeg not found")
        return results

    # Check video exists
    if not Path(video_path).exists():
        print(f"[ERROR] Video file not found: {video_path}")
        results["errors"].append(f"Video not found: {video_path}")
        return results

    # Get video info
    print("\n" + "="*60)
    print("VIDEO METADATA")
    print("="*60)

    info = get_video_info(video_path, ffprobe_path)
    if info:
        fmt = info.get('format', {})
        streams = info.get('streams', [])

        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})

        results["metadata"] = {
            "format": fmt.get('format_name', 'unknown'),
            "duration": float(fmt.get('duration', 0)),
            "size_mb": int(fmt.get('size', 0)) / (1024 * 1024),
            "video": {
                "codec": video_stream.get('codec_name', ''),
                "width": video_stream.get('width', 0),
                "height": video_stream.get('height', 0),
                "fps": video_stream.get('r_frame_rate', '')
            },
            "audio": {
                "codec": audio_stream.get('codec_name', ''),
                "sample_rate": audio_stream.get('sample_rate', ''),
                "channels": audio_stream.get('channels', 0)
            }
        }

        print(f"  Format: {results['metadata']['format']}")
        print(f"  Duration: {results['metadata']['duration']:.1f}s")
        print(f"  Size: {results['metadata']['size_mb']:.1f} MB")
        print(f"  Video: {results['metadata']['video']['codec']} "
              f"{results['metadata']['video']['width']}x{results['metadata']['video']['height']} "
              f"@ {results['metadata']['video']['fps']}")
        print(f"  Audio: {results['metadata']['audio']['codec']} "
              f"{results['metadata']['audio']['sample_rate']}Hz "
              f"{results['metadata']['audio']['channels']}ch")

    # Extract and analyze frames
    print("\n" + "="*60)
    print("FRAME EXTRACTION (1 per 10 seconds)")
    print("="*60)

    t0 = time.time()
    frames = extract_frames_cv2(video_path, interval_s=10.0, max_frames=200)
    results["timing"]["frame_extraction"] = time.time() - t0

    print(f"\n[INFO] Analyzing {len(frames)} frames...")
    t0 = time.time()

    for i, (timestamp, frame) in enumerate(frames):
        frame_info = analyze_frame(frame, timestamp, i)
        results["frames"].append(asdict(frame_info))

        if (i + 1) % 10 == 0:
            print(f"  Analyzed {i+1}/{len(frames)} frames...")

    results["timing"]["frame_analysis"] = time.time() - t0

    # Frame statistics
    if results["frames"]:
        brightnesses = [f["brightness"] for f in results["frames"]]
        complexities = [f["complexity"] for f in results["frames"]]

        results["frame_stats"] = {
            "count": len(results["frames"]),
            "brightness_mean": np.mean(brightnesses),
            "brightness_std": np.std(brightnesses),
            "complexity_mean": np.mean(complexities),
            "complexity_std": np.std(complexities),
            "unique_hashes": len(set(f["hash"] for f in results["frames"]))
        }

        print(f"\n[STATS] Frame Statistics:")
        print(f"  Total frames: {results['frame_stats']['count']}")
        print(f"  Brightness: {results['frame_stats']['brightness_mean']:.2f} +/- {results['frame_stats']['brightness_std']:.2f}")
        print(f"  Complexity: {results['frame_stats']['complexity_mean']:.2f} +/- {results['frame_stats']['complexity_std']:.2f}")
        print(f"  Unique hashes: {results['frame_stats']['unique_hashes']}")

    # Extract and analyze audio
    print("\n" + "="*60)
    print("AUDIO EXTRACTION AND ANALYSIS")
    print("="*60)

    t0 = time.time()
    wav_path = extract_audio(video_path, ffmpeg_path)
    results["timing"]["audio_extraction"] = time.time() - t0

    if wav_path:
        t0 = time.time()
        audio_features = analyze_audio(wav_path)
        results["timing"]["audio_analysis"] = time.time() - t0

        if audio_features:
            results["audio"] = asdict(audio_features)

            print(f"\n[STATS] Audio Statistics:")
            print(f"  Duration: {audio_features.duration_s:.1f}s")
            print(f"  Tempo: {audio_features.tempo:.1f} BPM")
            print(f"  Beats: {audio_features.n_beats}")
            print(f"  Spectral Centroid: {audio_features.spectral_centroid_mean:.1f} Hz")
            print(f"  RMS Energy: {audio_features.rms_mean:.4f}")
            print(f"  Harmonic Ratio: {audio_features.harmonic_ratio:.2%}")

        # Clean up temp file
        try:
            Path(wav_path).unlink()
        except:
            pass

    # Summary
    results["test_end"] = time.time()
    results["test_duration"] = results["test_end"] - results["test_start"]

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print(f"  Total time: {results['test_duration']:.1f}s")
    print(f"  Frame extraction: {results['timing'].get('frame_extraction', 0):.1f}s")
    print(f"  Frame analysis: {results['timing'].get('frame_analysis', 0):.1f}s")
    print(f"  Audio extraction: {results['timing'].get('audio_extraction', 0):.1f}s")
    print(f"  Audio analysis: {results['timing'].get('audio_analysis', 0):.1f}s")

    if results["errors"]:
        print(f"\n[ERRORS]:")
        for err in results["errors"]:
            print(f"  - {err}")

    return results


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    # Default video path
    DEFAULT_VIDEO = r"F:\Sandbox\American.Dad!.S20E11.A.Little.Mystery.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv"

    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        video_path = DEFAULT_VIDEO

    print("\n" + "="*60)
    print("VIDEO PROCESSING PIPELINE TEST")
    print("="*60)
    print(f"Video: {video_path}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    results = test_video_processing(video_path)

    # Save results to JSON
    output_path = PROJECT_ROOT / "state" / "video_test_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n[INFO] Results saved to: {output_path}")
