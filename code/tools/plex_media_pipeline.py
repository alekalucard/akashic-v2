"""
Plex Media Extraction Pipeline — Voice + Dialogue + STT Training
================================================================
Scans the Plex library, extracts audio + subtitles, segments dialogue,
extracts voice signatures, and ingests everything into the cortex.

Phases:
  0: Catalog (ffprobe metadata scan → master_catalog.json)
  1: Extract (ffmpeg → audio.wav + subs.srt per video)
  2: Segment (split audio at SRT timestamps → individual clips)
  3: Voice (MFCC voice signature extraction per segment)
  4: Ingest (cortex.bind + cortex.train_batch via PostalTunnel)

Usage:
  python plex_media_pipeline.py --phase 0                    # Catalog only
  python plex_media_pipeline.py --phase 1 --category Movies  # Extract one category
  python plex_media_pipeline.py --phase 0-4                  # Full pipeline
  python plex_media_pipeline.py --phase 0 --limit 100        # Test on first 100
"""

import argparse
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
import wave
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
PLEX_ROOT = Path(r"Z:\Plex Media 1")
EXTRACT_ROOT = ROOT / "tools" / "extracted" / "plex_media"
CATALOG_PATH = EXTRACT_ROOT / "master_catalog.json"
PROGRESS_PATH = EXTRACT_ROOT / "pipeline_progress.json"

CATEGORIES = [
    "Disney Movie Collection",  # Tier 1: emotional, clean audio
    "Animated Movies",          # Tier 1: distinctive voices
    "Movies",                   # Tier 2: diverse dialogue
    "Animated Tv Shows",        # Tier 3: recurring characters
    "TV Shows",                 # Tier 4: massive volume
]

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".flv", ".mov"}

# ─── Filename Parsing ────────────────────────────────────────────────────────

# TV: Show.Name.S01E02.quality.source.codec-GROUP.mkv
RE_TV = re.compile(
    r"^(?P<show>.+?)[.\s]S(?P<season>\d{1,2})E(?P<episode>\d{1,3})"
    r"(?:.*?(?P<quality>\d{3,4}p))?"
    r".*\.(?P<ext>\w+)$",
    re.IGNORECASE,
)

# Movie: Movie.Name.2019.1080p.BluRay.x264-GROUP.mkv
RE_MOVIE = re.compile(
    r"^(?P<title>.+?)[.\s](?P<year>(?:19|20)\d{2})[.\s]"
    r"(?:.*?(?P<quality>\d{3,4}p))?"
    r".*\.(?P<ext>\w+)$",
    re.IGNORECASE,
)

# Simple: just the filename
RE_SIMPLE = re.compile(r"^(?P<title>.+)\.(?P<ext>\w+)$")


def parse_filename(filename: str, category: str) -> dict:
    """Extract structured info from a media filename."""
    info = {"raw_filename": filename, "category": category}

    # Try TV pattern first for TV categories
    if "TV" in category or "Tv" in category:
        m = RE_TV.match(filename)
        if m:
            info["type"] = "tv"
            info["show"] = m.group("show").replace(".", " ").strip()
            info["season"] = int(m.group("season"))
            info["episode"] = int(m.group("episode"))
            info["quality"] = m.group("quality") or "unknown"
            return info

    # Try movie pattern
    m = RE_MOVIE.match(filename)
    if m:
        info["type"] = "movie"
        info["title"] = m.group("title").replace(".", " ").strip()
        info["year"] = int(m.group("year"))
        info["quality"] = m.group("quality") or "unknown"
        return info

    # Fallback
    m = RE_SIMPLE.match(filename)
    if m:
        info["type"] = "unknown"
        info["title"] = m.group("title").replace(".", " ").strip()
    else:
        info["type"] = "unknown"
        info["title"] = filename

    return info


# ─── Phase 0: Catalog ───────────────────────────────────────────────────────

def ffprobe_file(filepath: str) -> dict:
    """Run ffprobe on a single file and return stream info."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                filepath,
            ],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            return {"error": f"ffprobe returned {result.returncode}"}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "ffprobe timeout"}
    except json.JSONDecodeError:
        return {"error": "ffprobe output not valid JSON"}
    except Exception as e:
        return {"error": str(e)}


def catalog_file(filepath: str, category: str) -> dict:
    """Catalog a single video file."""
    filename = os.path.basename(filepath)
    entry = parse_filename(filename, category)
    entry["file_path"] = filepath
    entry["file_size_mb"] = round(os.path.getsize(filepath) / (1024 * 1024), 1)

    probe = ffprobe_file(filepath)
    if "error" in probe:
        entry["probe_error"] = probe["error"]
        entry["priority_score"] = -10
        return entry

    # Extract format info
    fmt = probe.get("format", {})
    entry["duration_sec"] = float(fmt.get("duration", 0))
    entry["duration_str"] = _format_duration(entry["duration_sec"])
    entry["container"] = fmt.get("format_name", "unknown")

    # Analyze streams
    streams = probe.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    entry["audio"] = []
    for a in audio_streams:
        entry["audio"].append({
            "codec": a.get("codec_name", "?"),
            "channels": a.get("channels", 0),
            "sample_rate": a.get("sample_rate", "?"),
            "language": a.get("tags", {}).get("language", "?"),
        })

    entry["subtitles"] = []
    for s in sub_streams:
        entry["subtitles"].append({
            "codec": s.get("codec_name", "?"),
            "language": s.get("tags", {}).get("language", "?"),
            "title": s.get("tags", {}).get("title", ""),
        })

    # Find best English subtitle stream index
    entry["best_sub_index"] = None
    entry["best_sub_codec"] = None
    for i, s in enumerate(sub_streams):
        lang = s.get("tags", {}).get("language", "").lower()
        codec = s.get("codec_name", "")
        if lang in ("eng", "en", "english", "?", "und", ""):
            # Prefer subrip over ass/dvd_subtitle
            if codec == "subrip":
                entry["best_sub_index"] = i
                entry["best_sub_codec"] = codec
                break
            elif codec in ("ass", "ssa") and entry["best_sub_index"] is None:
                entry["best_sub_index"] = i
                entry["best_sub_codec"] = codec
            elif entry["best_sub_index"] is None:
                entry["best_sub_index"] = i
                entry["best_sub_codec"] = codec

    # Priority scoring
    score = 0
    if entry["best_sub_index"] is not None:
        score += 3
        if entry["best_sub_codec"] == "subrip":
            score += 1  # SRT is easiest to parse
    else:
        score -= 2  # No usable subs

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mkv":
        score += 2
    elif ext == ".mp4":
        score += 1

    if entry.get("quality") in ("1080p", "2160p"):
        score += 1

    audio_codecs = [a["codec"] for a in entry["audio"]]
    if any(c in ("dts", "ac3", "eac3", "truehd", "flac") for c in audio_codecs):
        score += 1

    if entry["duration_sec"] < 60:  # Too short (trailer?)
        score -= 3
    elif entry["duration_sec"] < 300:  # Under 5 min
        score -= 1

    entry["priority_score"] = score
    return entry


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def run_phase_0(categories: list, limit: int = 0, workers: int = 4):
    """Phase 0: Catalog all video files via ffprobe."""
    print("=" * 70)
    print("PHASE 0: CATALOGING PLEX LIBRARY")
    print("=" * 70)

    # Load existing catalog for resume
    catalog = []
    cataloged_paths = set()
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r") as f:
            catalog = json.load(f)
        cataloged_paths = {e["file_path"] for e in catalog}
        print(f"Resuming: {len(catalog)} already cataloged")

    # Discover all video files
    all_files = []
    for cat in categories:
        cat_path = PLEX_ROOT / cat
        if not cat_path.exists():
            print(f"  SKIP: {cat} (not found)")
            continue
        count = 0
        for root, dirs, files in os.walk(cat_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTS:
                    fp = os.path.join(root, f)
                    if fp not in cataloged_paths:
                        all_files.append((fp, cat))
                        count += 1
        print(f"  {cat}: {count} new files to catalog")

    if limit > 0:
        all_files = all_files[:limit]

    total = len(all_files)
    if total == 0:
        print("Nothing new to catalog!")
        return catalog

    print(f"\nCataloging {total} files with {workers} workers...")
    t0 = time.time()
    done = 0
    errors = 0

    def _process(args):
        fp, cat = args
        return catalog_file(fp, cat)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process, item): item for item in all_files}

        for future in as_completed(futures):
            try:
                entry = future.result()
                catalog.append(entry)
                if "probe_error" in entry:
                    errors += 1
            except Exception as e:
                fp, cat = futures[future]
                catalog.append({
                    "file_path": fp, "category": cat,
                    "probe_error": str(e), "priority_score": -10,
                })
                errors += 1

            done += 1
            if done % 100 == 0 or done == total:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(
                    f"  {done}/{total} cataloged "
                    f"({rate:.1f}/s, {errors} errors, "
                    f"ETA {_format_duration(eta)})"
                )

                # Save checkpoint every 500
                if done % 500 == 0:
                    _save_catalog(catalog)

    elapsed = time.time() - t0
    _save_catalog(catalog)

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"CATALOG COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Total entries:  {len(catalog)}")
    print(f"  New this run:   {total}")
    print(f"  Errors:         {errors}")
    print(f"  Elapsed:        {_format_duration(elapsed)}")

    # Stats
    has_subs = sum(1 for e in catalog if e.get("best_sub_index") is not None)
    no_subs = sum(1 for e in catalog if e.get("best_sub_index") is None and "probe_error" not in e)
    total_hours = sum(e.get("duration_sec", 0) for e in catalog) / 3600
    sub_hours = sum(
        e.get("duration_sec", 0) for e in catalog
        if e.get("best_sub_index") is not None
    ) / 3600

    print(f"\n  With English subs: {has_subs} ({has_subs*100//max(len(catalog),1)}%)")
    print(f"  Without subs:      {no_subs}")
    print(f"  Total duration:    {total_hours:.0f} hours")
    print(f"  Sub'd duration:    {sub_hours:.0f} hours (extractable)")

    # By category
    by_cat = defaultdict(lambda: {"count": 0, "subs": 0, "hours": 0})
    for e in catalog:
        cat = e.get("category", "unknown")
        by_cat[cat]["count"] += 1
        if e.get("best_sub_index") is not None:
            by_cat[cat]["subs"] += 1
        by_cat[cat]["hours"] += e.get("duration_sec", 0) / 3600

    print(f"\n  By category:")
    for cat in CATEGORIES:
        s = by_cat[cat]
        if s["count"] > 0:
            print(f"    {cat}: {s['count']} files, {s['subs']} with subs, {s['hours']:.0f} hrs")

    # Priority distribution
    scores = [e.get("priority_score", 0) for e in catalog]
    high = sum(1 for s in scores if s >= 4)
    med = sum(1 for s in scores if 1 <= s < 4)
    low = sum(1 for s in scores if s < 1)
    print(f"\n  Priority: {high} high (>=4), {med} medium (1-3), {low} low (<1)")

    return catalog


def _save_catalog(catalog: list):
    """Save catalog to disk."""
    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=1)


# ─── Phase 1: Extract Audio + Subtitles ─────────────────────────────────────

def run_phase_1(catalog: list, categories: list, limit: int = 0):
    """Phase 1: Extract audio (16kHz mono WAV) + subtitles from cataloged files."""
    print("\n" + "=" * 70)
    print("PHASE 1: EXTRACTING AUDIO + SUBTITLES")
    print("=" * 70)

    # Load progress
    progress = _load_progress()
    extracted = set(progress.get("phase1_done", []))

    # Filter to extractable files
    candidates = [
        e for e in catalog
        if e.get("best_sub_index") is not None
        and e.get("priority_score", 0) >= 1
        and "probe_error" not in e
        and e.get("category") in categories
        and e["file_path"] not in extracted
    ]

    # Sort by priority (highest first)
    candidates.sort(key=lambda e: e.get("priority_score", 0), reverse=True)

    if limit > 0:
        candidates = candidates[:limit]

    total = len(candidates)
    if total == 0:
        print("Nothing to extract!")
        return

    print(f"Extracting {total} files (skipping {len(extracted)} already done)")
    t0 = time.time()
    done = 0
    errors = 0

    for entry in candidates:
        fp = entry["file_path"]
        cat = entry.get("category", "unknown")

        # Build output path
        if entry.get("type") == "tv":
            show = _safe_name(entry.get("show", "unknown"))
            ep = f"S{entry.get('season', 0):02d}E{entry.get('episode', 0):02d}"
            out_dir = EXTRACT_ROOT / _safe_name(cat) / show / ep
        elif entry.get("type") == "movie":
            title = _safe_name(entry.get("title", "unknown"))
            year = entry.get("year", "")
            out_dir = EXTRACT_ROOT / _safe_name(cat) / f"{title}_{year}"
        else:
            title = _safe_name(entry.get("title", os.path.basename(fp)))
            out_dir = EXTRACT_ROOT / _safe_name(cat) / title

        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "audio.wav"
        subs_path = out_dir / "subs.srt"
        meta_path = out_dir / "metadata.json"

        # Skip if already extracted
        if audio_path.exists() and (subs_path.exists() or meta_path.exists()):
            extracted.add(fp)
            done += 1
            continue

        try:
            # Extract audio: mono, 16kHz, PCM 16-bit
            sub_idx = entry["best_sub_index"]
            cmd = [
                "ffmpeg", "-y", "-i", fp,
                "-map", "0:a:0",
                "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
                str(audio_path),
            ]

            # Extract subtitles (separate command for reliability)
            sub_codec = entry.get("best_sub_codec", "subrip")
            sub_cmd = [
                "ffmpeg", "-y", "-i", fp,
                "-map", f"0:s:{sub_idx}",
            ]
            # ASS/SSA needs conversion to SRT
            if sub_codec in ("ass", "ssa"):
                sub_cmd += ["-c:s", "srt"]
            sub_cmd.append(str(subs_path))

            # Run audio extraction
            r = subprocess.run(cmd, capture_output=True, timeout=300,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg audio failed: {r.stderr[-200:]}")

            # Run subtitle extraction
            r2 = subprocess.run(sub_cmd, capture_output=True, timeout=60,
                                encoding="utf-8", errors="replace")
            if r2.returncode != 0:
                # Some files have subtitle issues, still keep the audio
                subs_path = None

            # Save metadata
            meta = {
                "source_file": fp,
                "category": cat,
                "parsed": {k: v for k, v in entry.items()
                           if k in ("type", "title", "show", "season", "episode",
                                    "year", "quality")},
                "duration_sec": entry.get("duration_sec", 0),
                "audio_codec": entry.get("audio", [{}])[0].get("codec", "?"),
                "sub_codec": sub_codec,
                "has_subs": subs_path is not None and subs_path.exists(),
                "extracted_at": time.time(),
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

            extracted.add(fp)

        except Exception as e:
            errors += 1
            # Write error metadata
            with open(out_dir / "error.txt", "w") as f:
                f.write(f"{fp}\n{str(e)}\n")

        done += 1
        if done % 10 == 0 or done == total:
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            print(
                f"  {done}/{total} extracted "
                f"({rate:.2f}/s, {errors} errors, "
                f"ETA {_format_duration(eta)})"
            )

        # Save progress every 50
        if done % 50 == 0:
            progress["phase1_done"] = list(extracted)
            _save_progress(progress)

    # Final save
    progress["phase1_done"] = list(extracted)
    _save_progress(progress)

    elapsed = time.time() - t0
    print(f"\nPhase 1 complete: {done} extracted, {errors} errors, {_format_duration(elapsed)}")


# ─── Phase 2: Segment at Subtitle Timestamps ────────────────────────────────

def parse_srt(srt_path: str) -> list:
    """Parse an SRT file into segments."""
    segments = []
    try:
        with open(srt_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except:
        return segments

    # SRT format: index\ntimestamp --> timestamp\ntext\n\n
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # Find timestamp line
        ts_line = None
        text_lines = []
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line = line
                text_lines = lines[i + 1:]
                break

        if not ts_line:
            continue

        try:
            parts = ts_line.split("-->")
            start = _parse_srt_time(parts[0].strip())
            end = _parse_srt_time(parts[1].strip())
            text = " ".join(text_lines).strip()

            # Clean HTML tags
            text = re.sub(r"<[^>]+>", "", text)
            # Clean ASS style overrides
            text = re.sub(r"\{[^}]+\}", "", text)

            if text and start < end:
                segments.append({
                    "start": start,
                    "end": end,
                    "duration": round(end - start, 3),
                    "text": text,
                })
        except:
            continue

    return segments


def _parse_srt_time(ts: str) -> float:
    """Parse SRT timestamp (HH:MM:SS,mmm) to seconds."""
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def _is_dialogue(text: str) -> bool:
    """Filter out non-dialogue subtitle entries."""
    t = text.strip()

    # Music markers
    if t.startswith(("♪", "♫", "[Music", "[music", "(Music", "(music")):
        return False

    # Sound effects in brackets
    if re.match(r"^\[.+\]$", t) or re.match(r"^\(.+\)$", t):
        return False

    # Too short
    words = t.split()
    if len(words) < 2:
        return False

    # Must have some alpha content
    alpha_ratio = sum(1 for c in t if c.isalpha()) / max(len(t), 1)
    if alpha_ratio < 0.4:
        return False

    return True


def segment_audio(audio_path: str, segments: list, out_dir: Path) -> list:
    """Split audio file at segment timestamps, return segment metadata."""
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    results = []
    try:
        with wave.open(audio_path, "rb") as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            total_frames = wf.getnframes()
            all_data = wf.readframes(total_frames)
    except Exception as e:
        print(f"    Error reading {audio_path}: {e}")
        return results

    bytes_per_sample = sampwidth * n_channels

    for i, seg in enumerate(segments):
        if not _is_dialogue(seg["text"]):
            continue

        # Duration filter
        dur = seg["duration"]
        if dur < 0.5 or dur > 30.0:
            continue

        start_frame = int(seg["start"] * sample_rate)
        end_frame = int(seg["end"] * sample_rate)

        # Bounds check
        start_frame = max(0, min(start_frame, total_frames))
        end_frame = max(start_frame, min(end_frame, total_frames))

        if end_frame <= start_frame:
            continue

        start_byte = start_frame * bytes_per_sample
        end_byte = end_frame * bytes_per_sample
        clip_data = all_data[start_byte:end_byte]

        clip_path = clips_dir / f"seg_{i:05d}.wav"
        try:
            with wave.open(str(clip_path), "wb") as wf_out:
                wf_out.setnchannels(n_channels)
                wf_out.setsampwidth(sampwidth)
                wf_out.setframerate(sample_rate)
                wf_out.writeframes(clip_data)

            results.append({
                "index": i,
                "clip_path": str(clip_path),
                "start": seg["start"],
                "end": seg["end"],
                "duration": dur,
                "text": seg["text"],
                "sample_rate": sample_rate,
                "n_frames": end_frame - start_frame,
            })
        except Exception as e:
            continue

    return results


def run_phase_2(categories: list, limit: int = 0):
    """Phase 2: Segment extracted audio at subtitle timestamps."""
    print("\n" + "=" * 70)
    print("PHASE 2: SEGMENTING DIALOGUE")
    print("=" * 70)

    progress = _load_progress()
    segmented = set(progress.get("phase2_done", []))

    # Find all extracted directories with audio + subs
    dirs_to_process = []
    for cat in categories:
        cat_dir = EXTRACT_ROOT / _safe_name(cat)
        if not cat_dir.exists():
            continue
        for item_dir in sorted(cat_dir.iterdir()):
            if not item_dir.is_dir():
                continue
            audio = item_dir / "audio.wav"
            subs = item_dir / "subs.srt"
            if audio.exists() and subs.exists() and str(item_dir) not in segmented:
                dirs_to_process.append(item_dir)

    if limit > 0:
        dirs_to_process = dirs_to_process[:limit]

    total = len(dirs_to_process)
    if total == 0:
        print("Nothing to segment!")
        return

    print(f"Segmenting {total} items ({len(segmented)} already done)")
    t0 = time.time()
    total_segments = 0
    total_dialogue = 0
    errors = 0

    for idx, item_dir in enumerate(dirs_to_process, 1):
        audio_path = str(item_dir / "audio.wav")
        subs_path = str(item_dir / "subs.srt")

        try:
            # Parse subtitles
            srt_segments = parse_srt(subs_path)
            if not srt_segments:
                segmented.add(str(item_dir))
                continue

            total_segments += len(srt_segments)

            # Segment audio
            clips = segment_audio(audio_path, srt_segments, item_dir)
            total_dialogue += len(clips)

            # Save segments manifest
            manifest = {
                "total_srt_segments": len(srt_segments),
                "dialogue_clips": len(clips),
                "filtered_out": len(srt_segments) - len(clips),
                "total_dialogue_sec": sum(c["duration"] for c in clips),
                "clips": clips,
            }
            with open(item_dir / "segments.json", "w") as f:
                json.dump(manifest, f, indent=1)

            segmented.add(str(item_dir))

        except Exception as e:
            errors += 1

        if idx % 10 == 0 or idx == total:
            elapsed = time.time() - t0
            print(
                f"  {idx}/{total} segmented "
                f"({total_dialogue} dialogue clips, {errors} errors, "
                f"{_format_duration(elapsed)})"
            )

        if idx % 50 == 0:
            progress["phase2_done"] = list(segmented)
            _save_progress(progress)

    progress["phase2_done"] = list(segmented)
    _save_progress(progress)

    elapsed = time.time() - t0
    print(f"\nPhase 2 complete: {total_dialogue} dialogue clips from {total_segments} subs")
    print(f"  {_format_duration(elapsed)}, {errors} errors")


# ─── Phase 3: Voice Signature Extraction ─────────────────────────────────────

def extract_mfcc_signature(wav_path: str, sample_rate: int = 16000) -> dict:
    """Extract a 29-float voice signature from a WAV clip.

    Uses pure Python — no external libs. Computes:
    - 13 MFCC mean coefficients
    - 13 MFCC std coefficients
    - pitch mean, pitch std
    - spectral centroid mean
    """
    try:
        with wave.open(wav_path, "rb") as wf:
            sr = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            sampwidth = wf.getsampwidth()
    except:
        return None

    # Convert to float samples
    if sampwidth == 2:
        samples = struct.unpack(f"<{n_frames}h", raw)
        samples = [s / 32768.0 for s in samples]
    elif sampwidth == 4:
        samples = struct.unpack(f"<{n_frames}i", raw)
        samples = [s / 2147483648.0 for s in samples]
    else:
        return None

    if len(samples) < 512:
        return None

    # Simple spectral analysis via DFT on frames
    frame_size = 512
    hop = 256
    n_fft = frame_size

    mfcc_frames = []
    centroids = []
    pitches = []

    for start in range(0, len(samples) - frame_size, hop):
        frame = samples[start:start + frame_size]

        # Apply Hamming window
        windowed = [
            frame[i] * (0.54 - 0.46 * math.cos(2 * math.pi * i / (frame_size - 1)))
            for i in range(frame_size)
        ]

        # Simple power spectrum (real DFT via sum of cosines — approximate)
        # For performance, compute only 64 frequency bins
        n_bins = 64
        power = []
        for k in range(n_bins):
            freq = k * sr / n_fft
            re_sum = sum(
                windowed[n] * math.cos(2 * math.pi * k * n / n_fft)
                for n in range(frame_size)
            )
            im_sum = sum(
                windowed[n] * math.sin(2 * math.pi * k * n / n_fft)
                for n in range(frame_size)
            )
            power.append(re_sum * re_sum + im_sum * im_sum)

        total_power = sum(power) + 1e-10

        # Spectral centroid
        centroid = sum(i * p for i, p in enumerate(power)) / total_power
        centroids.append(centroid * sr / n_fft)

        # Mel filter bank (13 filters, simplified triangular)
        mel_energies = []
        for m in range(13):
            center_bin = int((m + 1) * n_bins / 15)
            low = max(0, center_bin - 3)
            high = min(n_bins - 1, center_bin + 3)
            energy = sum(power[low:high + 1]) + 1e-10
            mel_energies.append(math.log(energy))

        # DCT to get MFCCs (simplified type-II DCT)
        mfcc = []
        for i in range(13):
            val = sum(
                mel_energies[j] * math.cos(math.pi * i * (j + 0.5) / 13)
                for j in range(13)
            )
            mfcc.append(val)
        mfcc_frames.append(mfcc)

        # Simple pitch detection (autocorrelation on frame)
        if total_power > 0.001:  # Only for voiced frames
            min_lag = int(sr / 600)  # 600 Hz max
            max_lag = int(sr / 70)   # 70 Hz min
            max_lag = min(max_lag, frame_size // 2)

            best_lag = min_lag
            best_corr = -1
            for lag in range(min_lag, max_lag):
                corr = sum(
                    frame[n] * frame[n + lag]
                    for n in range(frame_size - lag)
                )
                if corr > best_corr:
                    best_corr = corr
                    best_lag = lag

            if best_corr > 0:
                pitch = sr / best_lag
                if 70 <= pitch <= 600:
                    pitches.append(pitch)

    if not mfcc_frames:
        return None

    # Aggregate
    n = len(mfcc_frames)
    mfcc_mean = [sum(f[i] for f in mfcc_frames) / n for i in range(13)]
    mfcc_std = [
        math.sqrt(sum((f[i] - mfcc_mean[i]) ** 2 for f in mfcc_frames) / max(n - 1, 1))
        for i in range(13)
    ]

    pitch_mean = sum(pitches) / len(pitches) if pitches else 0
    pitch_std = (
        math.sqrt(sum((p - pitch_mean) ** 2 for p in pitches) / max(len(pitches) - 1, 1))
        if len(pitches) > 1 else 0
    )

    centroid_mean = sum(centroids) / len(centroids) if centroids else 0

    return {
        "mfcc_mean": [round(v, 4) for v in mfcc_mean],
        "mfcc_std": [round(v, 4) for v in mfcc_std],
        "pitch_mean": round(pitch_mean, 2),
        "pitch_std": round(pitch_std, 2),
        "centroid_mean": round(centroid_mean, 2),
    }


def run_phase_3(categories: list, limit: int = 0):
    """Phase 3: Extract voice signatures from segmented clips."""
    print("\n" + "=" * 70)
    print("PHASE 3: VOICE SIGNATURE EXTRACTION")
    print("=" * 70)

    progress = _load_progress()
    voiced = set(progress.get("phase3_done", []))

    # Find segmented directories
    dirs_to_process = []
    for cat in categories:
        cat_dir = EXTRACT_ROOT / _safe_name(cat)
        if not cat_dir.exists():
            continue
        for item_dir in sorted(cat_dir.iterdir()):
            if not item_dir.is_dir():
                continue
            segs = item_dir / "segments.json"
            if segs.exists() and str(item_dir) not in voiced:
                dirs_to_process.append(item_dir)

    if limit > 0:
        dirs_to_process = dirs_to_process[:limit]

    total = len(dirs_to_process)
    if total == 0:
        print("Nothing to voice-profile!")
        return

    print(f"Processing {total} items ({len(voiced)} already done)")
    t0 = time.time()
    total_clips = 0
    total_voiced = 0

    for idx, item_dir in enumerate(dirs_to_process, 1):
        try:
            with open(item_dir / "segments.json", "r") as f:
                seg_data = json.load(f)

            clips = seg_data.get("clips", [])
            total_clips += len(clips)

            voiced_clips = []
            for clip in clips:
                clip_path = clip.get("clip_path", "")
                if not os.path.exists(clip_path):
                    continue

                sig = extract_mfcc_signature(clip_path)
                if sig:
                    clip["voice_signature"] = sig
                    voiced_clips.append(clip)
                    total_voiced += 1

            # Save enhanced segments
            seg_data["voiced_clips"] = len(voiced_clips)
            seg_data["clips"] = clips  # Updated with signatures
            with open(item_dir / "segments.json", "w") as f:
                json.dump(seg_data, f, indent=1)

            voiced.add(str(item_dir))

        except Exception as e:
            pass

        if idx % 5 == 0 or idx == total:
            elapsed = time.time() - t0
            print(
                f"  {idx}/{total} items, {total_voiced}/{total_clips} clips voiced "
                f"({_format_duration(elapsed)})"
            )

        if idx % 20 == 0:
            progress["phase3_done"] = list(voiced)
            _save_progress(progress)

    progress["phase3_done"] = list(voiced)
    _save_progress(progress)

    elapsed = time.time() - t0
    print(f"\nPhase 3 complete: {total_voiced} voice signatures from {total_clips} clips")
    print(f"  {_format_duration(elapsed)}")


# ─── Phase 4: Cortex Ingestion ──────────────────────────────────────────────

def run_phase_4(categories: list, limit: int = 0, dry_run: bool = False):
    """Phase 4: Ingest segmented dialogue + voice signatures into cortex."""
    print("\n" + "=" * 70)
    print(f"PHASE 4: CORTEX INGESTION {'(DRY RUN)' if dry_run else ''}")
    print("=" * 70)

    # Connect to postal
    postal = None
    if not dry_run:
        try:
            mcp_path = str(ROOT / "fairies" / "P40_Sensory" / "mcp")
            if mcp_path not in sys.path:
                sys.path.insert(0, mcp_path)
            from postal_tunnel import PostalTunnelClient
            postal = PostalTunnelClient()
            postal.connect()
            if postal.ping():
                print("Connected to PostalHub via tunnel")
            else:
                print("WARNING: PostalHub ping failed, continuing anyway")
        except Exception as e:
            print(f"ERROR: Cannot connect to PostalHub: {e}")
            print("Run with --dry-run to test without postal connection")
            return

    progress = _load_progress()
    ingested = set(progress.get("phase4_done", []))

    # Collect all segments
    all_segments = []
    for cat in categories:
        cat_dir = EXTRACT_ROOT / _safe_name(cat)
        if not cat_dir.exists():
            continue
        for item_dir in sorted(cat_dir.iterdir()):
            if not item_dir.is_dir() or str(item_dir) in ingested:
                continue
            seg_file = item_dir / "segments.json"
            meta_file = item_dir / "metadata.json"
            if not seg_file.exists():
                continue

            try:
                with open(seg_file, "r") as f:
                    seg_data = json.load(f)
                meta = {}
                if meta_file.exists():
                    with open(meta_file, "r") as f:
                        meta = json.load(f)

                clips = seg_data.get("clips", [])
                for clip in clips:
                    if clip.get("text"):
                        clip["_item_dir"] = str(item_dir)
                        clip["_meta"] = meta
                        clip["_category"] = cat
                        all_segments.append(clip)
            except:
                continue

    if limit > 0:
        all_segments = all_segments[:limit]

    total = len(all_segments)
    if total == 0:
        print("Nothing to ingest!")
        return

    print(f"Ingesting {total} dialogue segments")
    t0 = time.time()
    bound = 0
    errors = 0
    batch_texts = []
    items_by_dir = defaultdict(int)

    for i, seg in enumerate(all_segments):
        text = seg["text"]
        meta = seg.get("_meta", {})
        parsed = meta.get("parsed", {})
        cat = seg.get("_category", "unknown")
        item_dir = seg.get("_item_dir", "")

        # Build source label
        if parsed.get("type") == "tv":
            source = f"{parsed.get('show', 'unknown')} S{parsed.get('season', 0):02d}E{parsed.get('episode', 0):02d}"
        elif parsed.get("type") == "movie":
            source = f"{parsed.get('title', 'unknown')} ({parsed.get('year', '')})"
        else:
            source = parsed.get("title", "unknown")

        # Build input text for cortex.bind
        # Must be <500 chars, >40% alpha
        input_text = f"{source}: {text}"
        if len(input_text) > 490:
            input_text = input_text[:490]

        # Build features
        features = {
            "vision": [],
            "lex": text.split()[:20],
            "affect": [],
        }
        if seg.get("voice_signature"):
            features["voice"] = seg["voice_signature"]

        # Context tags
        tags = [cat.lower().replace(" ", "_")]
        if parsed.get("show"):
            tags.append(parsed["show"].lower().replace(" ", "_"))
        if parsed.get("title"):
            tags.append(parsed["title"].lower().replace(" ", "_"))
        if parsed.get("year"):
            tags.append(str(parsed["year"]))

        # cortex.bind
        bind_payload = {
            "input_text": input_text,
            "features": features,
            "persona": "sourpatches",
            "context_tags": tags,
            "source": "plex_media",
            "feeling": "curious",
        }

        if not dry_run and postal:
            try:
                postal.route("cortex.bind", bind_payload)
                bound += 1
            except Exception as e:
                errors += 1

        # Collect for train_batch
        batch_texts.append({
            "text": text,
            "source": source,
            "weight": 1.0,
        })

        # Send train_batch every 500
        if len(batch_texts) >= 500:
            if not dry_run and postal:
                try:
                    postal.route("cortex.train_batch", {
                        "items": batch_texts,
                        "source": "plex_media",
                        "source_fairy": "NousFairy",
                        "trace_id": f"plex_{int(time.time())}",
                    })
                except:
                    pass
            batch_texts = []

        items_by_dir[item_dir] += 1

        if (i + 1) % 500 == 0 or (i + 1) == total:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(
                f"  {i + 1}/{total} ingested "
                f"({rate:.1f}/s, {errors} errors)"
            )

    # Final batch
    if batch_texts and not dry_run and postal:
        try:
            postal.route("cortex.train_batch", {
                "items": batch_texts,
                "source": "plex_media",
                "source_fairy": "NousFairy",
                "trace_id": f"plex_{int(time.time())}",
            })
        except:
            pass

    # Mark dirs as done
    for item_dir in items_by_dir:
        ingested.add(item_dir)
    progress["phase4_done"] = list(ingested)
    _save_progress(progress)

    elapsed = time.time() - t0
    print(f"\nPhase 4 complete: {bound} bound, {errors} errors, {_format_duration(elapsed)}")


# ─── Utilities ───────────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Make a filesystem-safe name."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip(". ")


def _load_progress() -> dict:
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_progress(progress: dict):
    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_PATH, "w") as f:
        json.dump(progress, f, indent=1)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plex Media Extraction Pipeline")
    parser.add_argument("--phase", default="0", help="Phase(s) to run: 0, 1, 2, 3, 4, or 0-4")
    parser.add_argument("--category", nargs="*", help="Categories to process (default: all)")
    parser.add_argument("--limit", type=int, default=0, help="Limit items per phase (0=all)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for Phase 0")
    parser.add_argument("--dry-run", action="store_true", help="Phase 4: don't actually ingest")
    args = parser.parse_args()

    cats = args.category if args.category else CATEGORIES

    # Parse phase range
    if "-" in args.phase:
        start, end = args.phase.split("-")
        phases = list(range(int(start), int(end) + 1))
    else:
        phases = [int(args.phase)]

    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)

    catalog = []

    if 0 in phases:
        catalog = run_phase_0(cats, limit=args.limit, workers=args.workers)

    if any(p in phases for p in [1, 2, 3, 4]):
        # Load catalog if not from phase 0
        if not catalog and CATALOG_PATH.exists():
            with open(CATALOG_PATH, "r") as f:
                catalog = json.load(f)

    if 1 in phases:
        run_phase_1(catalog, cats, limit=args.limit)

    if 2 in phases:
        run_phase_2(cats, limit=args.limit)

    if 3 in phases:
        run_phase_3(cats, limit=args.limit)

    if 4 in phases:
        run_phase_4(cats, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
