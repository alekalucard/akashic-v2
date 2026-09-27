"""Scan Plex library structure for media extraction planning."""
import os, sys, json, subprocess, time
from pathlib import Path
from collections import defaultdict

PLEX_ROOT = Path(r"Z:\Plex Media 1")
CATEGORIES = ["Movies", "Animated Movies", "Disney Movie Collection", "TV Shows", "Animated Tv Shows"]
VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".flv", ".mov"}

def scan_category(cat_path: Path) -> dict:
    """Count videos and check a sample for subtitle streams."""
    result = {
        "path": str(cat_path),
        "subdirs": 0,
        "video_files": 0,
        "total_size_gb": 0.0,
        "extensions": defaultdict(int),
        "sample_subtitle_check": [],
    }

    if not cat_path.exists():
        result["error"] = "Path not found"
        return result

    # Count subdirectories (each is typically a movie/show)
    try:
        subdirs = [d for d in cat_path.iterdir() if d.is_dir()]
        result["subdirs"] = len(subdirs)
    except Exception as e:
        result["error"] = str(e)
        return result

    # Walk and count video files
    video_files = []
    for root, dirs, files in os.walk(cat_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTS:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    result["total_size_gb"] += size / (1024**3)
                    result["video_files"] += 1
                    result["extensions"][ext] += 1
                    video_files.append(fp)
                except:
                    pass

    # Sample 5 videos for subtitle stream check (ffprobe)
    import random
    samples = random.sample(video_files, min(5, len(video_files))) if video_files else []
    for vf in samples:
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", vf],
                capture_output=True, text=True, timeout=30
            )
            if out.returncode == 0:
                data = json.loads(out.stdout)
                streams = data.get("streams", [])
                audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
                sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
                result["sample_subtitle_check"].append({
                    "file": os.path.basename(vf),
                    "audio_streams": len(audio_streams),
                    "audio_codecs": [s.get("codec_name","?") for s in audio_streams],
                    "subtitle_streams": len(sub_streams),
                    "sub_codecs": [s.get("codec_name","?") for s in sub_streams],
                    "sub_languages": [s.get("tags",{}).get("language","?") for s in sub_streams],
                })
        except Exception as e:
            result["sample_subtitle_check"].append({
                "file": os.path.basename(vf),
                "error": str(e)
            })

    # Convert defaultdict
    result["extensions"] = dict(result["extensions"])
    result["total_size_gb"] = round(result["total_size_gb"], 2)
    return result

def main():
    print(f"Scanning Plex library at {PLEX_ROOT}...")
    print(f"Categories: {CATEGORIES}\n")

    grand_total_videos = 0
    grand_total_gb = 0

    results = {}
    for cat in CATEGORIES:
        cat_path = PLEX_ROOT / cat
        print(f"Scanning {cat}...", end=" ", flush=True)
        t0 = time.time()
        info = scan_category(cat_path)
        elapsed = time.time() - t0
        print(f"done ({elapsed:.1f}s)")
        results[cat] = info
        grand_total_videos += info["video_files"]
        grand_total_gb += info["total_size_gb"]

    # Print summary
    print("\n" + "="*70)
    print("PLEX LIBRARY SCAN RESULTS")
    print("="*70)

    for cat, info in results.items():
        print(f"\n{cat}:")
        print(f"  Subdirectories: {info['subdirs']}")
        print(f"  Video files:    {info['video_files']}")
        print(f"  Total size:     {info['total_size_gb']:.1f} GB")
        print(f"  Extensions:     {info['extensions']}")
        if info["sample_subtitle_check"]:
            print(f"  Subtitle samples:")
            for s in info["sample_subtitle_check"]:
                if "error" in s:
                    print(f"    {s['file']}: ERROR - {s['error']}")
                else:
                    print(f"    {s['file']}:")
                    print(f"      Audio: {s['audio_streams']} streams ({', '.join(s['audio_codecs'])})")
                    print(f"      Subs:  {s['subtitle_streams']} streams ({', '.join(s['sub_codecs'])})")
                    if s['sub_languages']:
                        print(f"      Langs: {', '.join(s['sub_languages'])}")

    print(f"\n{'='*70}")
    print(f"TOTALS: {grand_total_videos} video files, {grand_total_gb:.1f} GB")
    print(f"{'='*70}")

    # Save results
    out_path = PLEX_ROOT.parent / "plex_scan_results.json" if PLEX_ROOT.parent.exists() else Path("plex_scan_results.json")
    # Save to tools/extracted instead
    out_path = Path(r"F:\Sandbox\failure_factory\akashic_v2\tools\extracted\plex_scan_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to {out_path}")

if __name__ == "__main__":
    main()
