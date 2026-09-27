"""
Media Extraction Pipeline — Stage 0 of STT Distillation
=========================================================

Extracts (audio_segment, video_frame, subtitle_text) triples from MKV files
for cortex ingestion and distillation training.

Pipeline:
  1. Probe MKV -> find audio + subtitle + video streams
  2. Extract audio -> 16kHz mono WAV
  3. Extract SRT subtitles -> parse into timed segments
  4. Extract video keyframes at subtitle timestamps
  5. Segment audio at SRT timestamps -> (clip, text) pairs
  6. Filter out non-dialogue (music, sound effects, <2 words)
  7. Package for cortex ingestion

Usage:
  python media_extraction_pipeline.py <input.mkv> [--output-dir <dir>]
  python media_extraction_pipeline.py --scan-dir <dir>  # Batch mode

Output structure:
  output_dir/
    manifest.json         # Full catalog of all segments
    audio_full.wav        # Complete audio track (16kHz mono)
    subtitles.srt         # Extracted subtitle file
    segments/
      seg_0001.json       # {text, start, end, duration, features, frame_path}
      seg_0001.wav        # Audio clip for this segment
      seg_0001.png        # Video frame at midpoint of segment
      ...

2026-03-19 — Nous + Ace — CUSTOM_STT_DISTILLATION.md Stage 0
"""

import subprocess
import json
import re
import sys
import os
import struct
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# SRT PARSER
# ═══════════════════════════════════════════════════════════════════════

def parse_srt(srt_text: str) -> List[Dict[str, Any]]:
    """Parse SRT subtitle text into list of {index, start, end, text} dicts.

    Timestamps are in seconds (float).
    Strips HTML tags and formatting from subtitle text.
    """
    segments = []
    # Split on blank lines (SRT blocks separated by empty lines)
    blocks = re.split(r'\n\s*\n', srt_text.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # Line 1: index number
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue

        # Line 2: timestamps  "00:01:23,456 --> 00:01:25,789"
        ts_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
            lines[1].strip()
        )
        if not ts_match:
            continue

        g = ts_match.groups()
        start = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
        end = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000

        # Lines 3+: subtitle text
        text = ' '.join(lines[2:])
        # Strip HTML tags (<i>, <b>, etc.)
        text = re.sub(r'<[^>]+>', '', text)
        # Strip speaker labels like "- " at start
        text = re.sub(r'^-\s*', '', text.strip())
        # Normalize whitespace
        text = ' '.join(text.split())

        if text:
            segments.append({
                'index': idx,
                'start': round(start, 3),
                'end': round(end, 3),
                'duration': round(end - start, 3),
                'text': text,
            })

    return segments


# ═══════════════════════════════════════════════════════════════════════
# SEGMENT FILTER
# ═══════════════════════════════════════════════════════════════════════

# SDH-style sound descriptions to filter out
SDH_PATTERNS = [
    r'^\[.*\]$',           # [music playing], [door slams], etc.
    r'^\(.*\)$',           # (sighs), (laughs), etc.
    r'^♪.*♪$',             # Music lyrics
    r'^♫.*♫$',             # Music lyrics
    r'^\*.*\*$',           # *gasps*, *sighs*
]

SDH_COMPILED = [re.compile(p, re.IGNORECASE) for p in SDH_PATTERNS]


def is_dialogue(segment: Dict[str, Any], min_words: int = 2, min_duration: float = 0.3) -> bool:
    """Filter: is this segment actual dialogue (not sound effects, music, etc.)?"""
    text = segment['text']
    duration = segment['duration']

    # Too short
    if duration < min_duration:
        return False

    # SDH descriptions
    for pat in SDH_COMPILED:
        if pat.match(text):
            return False

    # Contains only music symbols
    if text.strip('♪♫ ') == '':
        return False

    # Too few words (likely sound effect label)
    word_count = len(text.split())
    if word_count < min_words:
        return False

    return True


# ═══════════════════════════════════════════════════════════════════════
# FFMPEG/FFPROBE HELPERS
# ═══════════════════════════════════════════════════════════════════════

def probe_file(filepath: str) -> Dict[str, Any]:
    """Run ffprobe and return stream info as JSON dict."""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams', '-show_format',
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def find_streams(probe_data: Dict) -> Dict[str, Any]:
    """Find the best audio, subtitle, and video streams."""
    streams = probe_data.get('streams', [])

    audio_stream = None
    sub_stream = None
    sub_sdh_stream = None
    video_stream = None

    for s in streams:
        codec_type = s.get('codec_type', '')
        lang = s.get('tags', {}).get('language', 'und')

        if codec_type == 'audio' and audio_stream is None:
            if lang in ('eng', 'und', ''):
                audio_stream = s

        elif codec_type == 'subtitle':
            if lang in ('eng', 'und', ''):
                disp = s.get('disposition', {})
                if disp.get('hearing_impaired', 0):
                    sub_sdh_stream = s
                elif sub_stream is None:
                    sub_stream = s

        elif codec_type == 'video' and video_stream is None:
            video_stream = s

    return {
        'audio': audio_stream,
        'subtitle': sub_stream or sub_sdh_stream,  # Prefer normal subs over SDH
        'subtitle_sdh': sub_sdh_stream,
        'video': video_stream,
        'duration': float(probe_data.get('format', {}).get('duration', 0)),
    }


def extract_audio(input_path: str, output_path: str, sample_rate: int = 16000) -> bool:
    """Extract audio from MKV -> 16kHz mono WAV."""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vn',                          # No video
        '-acodec', 'pcm_s16le',        # 16-bit PCM
        '-ar', str(sample_rate),        # Resample to 16kHz
        '-ac', '1',                     # Mono
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode == 0


def extract_subtitles(input_path: str, output_path: str, stream_index: int = 0) -> bool:
    """Extract subtitle stream from MKV -> SRT file."""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-map', f'0:{stream_index}',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode == 0


def extract_frame(input_path: str, timestamp: float, output_path: str,
                  width: int = 512) -> bool:
    """Extract a single video frame at the given timestamp."""
    cmd = [
        'ffmpeg', '-y',
        '-ss', f'{timestamp:.3f}',
        '-i', input_path,
        '-vframes', '1',
        '-vf', f'scale={width}:-1',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0


def extract_audio_segment(full_audio_path: str, start: float, end: float,
                          output_path: str) -> bool:
    """Extract a time-range clip from the full audio WAV."""
    duration = end - start
    cmd = [
        'ffmpeg', '-y',
        '-ss', f'{start:.3f}',
        '-t', f'{duration:.3f}',
        '-i', full_audio_path,
        '-acodec', 'copy',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════

def process_media_file(input_path: str, output_dir: str = None,
                       extract_frames: bool = True,
                       extract_clips: bool = True) -> Dict[str, Any]:
    """
    Full extraction pipeline for a single media file.

    Returns manifest dict with all segment metadata.
    """
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Setup output directory
    if output_dir is None:
        basename = Path(input_path).stem
        # Clean up filename for directory name
        clean_name = re.sub(r'[^\w\s-]', '', basename)[:60]
        output_dir = os.path.join(os.path.dirname(input_path), 'extracted', clean_name)

    os.makedirs(output_dir, exist_ok=True)
    segments_dir = os.path.join(output_dir, 'segments')
    os.makedirs(segments_dir, exist_ok=True)

    print(f"[Pipeline] Processing: {os.path.basename(input_path)}")
    print(f"[Pipeline] Output: {output_dir}")

    # Step 1: Probe
    print("[Pipeline] Step 1/6: Probing file...")
    probe = probe_file(input_path)
    streams = find_streams(probe)

    if not streams['audio']:
        raise RuntimeError("No English audio stream found")
    if not streams['subtitle']:
        print("[Pipeline] WARNING: No subtitle stream found! Will extract audio only.")

    audio_idx = streams['audio']['index']
    sub_idx = streams['subtitle']['index'] if streams['subtitle'] else None
    video_idx = streams['video']['index'] if streams['video'] else None
    duration = streams['duration']

    print(f"[Pipeline]   Audio: stream {audio_idx} ({streams['audio'].get('codec_name', '?')})")
    if sub_idx is not None:
        print(f"[Pipeline]   Subs:  stream {sub_idx} ({streams['subtitle'].get('codec_name', '?')})")
    if video_idx is not None:
        print(f"[Pipeline]   Video: stream {video_idx} ({streams['video'].get('codec_name', '?')})")
    print(f"[Pipeline]   Duration: {duration:.1f}s ({duration/60:.1f} min)")

    # Step 2: Extract audio
    audio_path = os.path.join(output_dir, 'audio_full.wav')
    print("[Pipeline] Step 2/6: Extracting audio -> 16kHz mono WAV...")
    if not extract_audio(input_path, audio_path):
        raise RuntimeError("Audio extraction failed")
    audio_size = os.path.getsize(audio_path)
    print(f"[Pipeline]   Audio: {audio_size / 1024 / 1024:.1f} MB")

    # Step 3: Extract subtitles
    srt_path = os.path.join(output_dir, 'subtitles.srt')
    subtitle_segments = []
    if sub_idx is not None:
        print("[Pipeline] Step 3/6: Extracting subtitles...")
        if extract_subtitles(input_path, srt_path, sub_idx):
            with open(srt_path, 'r', encoding='utf-8', errors='replace') as f:
                srt_text = f.read()
            subtitle_segments = parse_srt(srt_text)
            print(f"[Pipeline]   Parsed {len(subtitle_segments)} subtitle blocks")
        else:
            print("[Pipeline]   WARNING: Subtitle extraction failed")
    else:
        print("[Pipeline] Step 3/6: No subtitles to extract")

    # Step 4: Filter to dialogue only
    print("[Pipeline] Step 4/6: Filtering to dialogue...")
    dialogue_segments = [s for s in subtitle_segments if is_dialogue(s)]
    filtered_count = len(subtitle_segments) - len(dialogue_segments)
    print(f"[Pipeline]   {len(dialogue_segments)} dialogue segments ({filtered_count} filtered)")

    # Step 5: Extract audio clips + video frames per segment
    print("[Pipeline] Step 5/6: Extracting segment clips + frames...")
    processed_segments = []

    for i, seg in enumerate(dialogue_segments):
        seg_id = f"seg_{i+1:04d}"
        seg_info = {
            **seg,
            'id': seg_id,
            'source_file': os.path.basename(input_path),
        }

        # Audio clip
        if extract_clips:
            clip_path = os.path.join(segments_dir, f"{seg_id}.wav")
            if extract_audio_segment(audio_path, seg['start'], seg['end'], clip_path):
                seg_info['audio_clip'] = f"segments/{seg_id}.wav"
                seg_info['audio_clip_size'] = os.path.getsize(clip_path)
            else:
                seg_info['audio_clip'] = None

        # Video frame (at midpoint of segment)
        if extract_frames and video_idx is not None:
            frame_time = (seg['start'] + seg['end']) / 2
            frame_path = os.path.join(segments_dir, f"{seg_id}.png")
            if extract_frame(input_path, frame_time, frame_path):
                seg_info['frame'] = f"segments/{seg_id}.png"
                seg_info['frame_timestamp'] = round(frame_time, 3)
            else:
                seg_info['frame'] = None

        processed_segments.append(seg_info)

        # Progress every 50 segments
        if (i + 1) % 50 == 0 or i == len(dialogue_segments) - 1:
            print(f"[Pipeline]   {i+1}/{len(dialogue_segments)} segments processed")

    # Step 6: Build manifest
    print("[Pipeline] Step 6/6: Building manifest...")

    total_dialogue_duration = sum(s['duration'] for s in processed_segments)

    manifest = {
        'version': '1.0',
        'source': {
            'file': os.path.basename(input_path),
            'path': input_path,
            'duration': round(duration, 3),
            'duration_min': round(duration / 60, 1),
        },
        'streams': {
            'audio_index': audio_idx,
            'audio_codec': streams['audio'].get('codec_name', ''),
            'subtitle_index': sub_idx,
            'subtitle_codec': streams['subtitle'].get('codec_name', '') if streams['subtitle'] else None,
            'video_index': video_idx,
        },
        'extraction': {
            'audio_path': 'audio_full.wav',
            'subtitle_path': 'subtitles.srt' if sub_idx else None,
            'sample_rate': 16000,
            'channels': 1,
        },
        'stats': {
            'total_subtitle_blocks': len(subtitle_segments),
            'dialogue_segments': len(processed_segments),
            'filtered_segments': filtered_count,
            'total_dialogue_seconds': round(total_dialogue_duration, 1),
            'total_dialogue_minutes': round(total_dialogue_duration / 60, 1),
            'dialogue_coverage': round(total_dialogue_duration / max(duration, 1) * 100, 1),
        },
        'segments': processed_segments,
    }

    manifest_path = os.path.join(output_dir, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n[Pipeline] COMPLETE")
    print(f"  Source: {os.path.basename(input_path)}")
    print(f"  Duration: {duration/60:.1f} min")
    print(f"  Dialogue segments: {len(processed_segments)}")
    print(f"  Dialogue time: {total_dialogue_duration/60:.1f} min ({manifest['stats']['dialogue_coverage']}% coverage)")
    print(f"  Manifest: {manifest_path}")

    return manifest


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Extract audio + subtitles + frames from media files for cortex ingestion'
    )
    parser.add_argument('input', nargs='?', help='Input MKV/MP4 file')
    parser.add_argument('--output-dir', '-o', help='Output directory')
    parser.add_argument('--scan-dir', '-d', help='Scan directory for MKV files (batch mode)')
    parser.add_argument('--no-frames', action='store_true', help='Skip frame extraction')
    parser.add_argument('--no-clips', action='store_true', help='Skip per-segment audio clips')
    parser.add_argument('--stats-only', action='store_true', help='Only probe and show stats')

    args = parser.parse_args()

    if args.scan_dir:
        # Batch mode: scan directory for MKV files
        scan_path = Path(args.scan_dir)
        mkv_files = list(scan_path.rglob('*.mkv')) + list(scan_path.rglob('*.mp4'))
        print(f"[Pipeline] Found {len(mkv_files)} media files in {scan_path}")

        for f in mkv_files:
            try:
                if args.stats_only:
                    probe = probe_file(str(f))
                    streams = find_streams(probe)
                    has_subs = '✓' if streams['subtitle'] else '✗'
                    dur = streams['duration']
                    print(f"  {has_subs} subs | {dur/60:5.1f} min | {f.name}")
                else:
                    process_media_file(
                        str(f),
                        output_dir=args.output_dir,
                        extract_frames=not args.no_frames,
                        extract_clips=not args.no_clips,
                    )
            except Exception as e:
                print(f"[Pipeline] ERROR on {f.name}: {e}")
        return

    if not args.input:
        parser.print_help()
        return

    if args.stats_only:
        probe = probe_file(args.input)
        streams = find_streams(probe)
        print(json.dumps({
            'file': args.input,
            'duration': streams['duration'],
            'has_audio': streams['audio'] is not None,
            'has_subtitle': streams['subtitle'] is not None,
            'has_video': streams['video'] is not None,
        }, indent=2))
        return

    process_media_file(
        args.input,
        output_dir=args.output_dir,
        extract_frames=not args.no_frames,
        extract_clips=not args.no_clips,
    )


if __name__ == '__main__':
    main()
