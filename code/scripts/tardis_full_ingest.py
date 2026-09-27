#!/usr/bin/env python3
"""
MEMORY TARDIS - Full Archive Ingestion

Ingests all media from multiple source directories with unified deduplication.
Maintains a global perceptual hash index for cross-drive dedup.
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, List, Set
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ==============================================================================
# SOURCE DIRECTORIES - Add all your media locations here!
# ==============================================================================

MEDIA_SOURCES = [
    # Z: Drive - Plex Media
    "Z:/Plex Media 1/Sourpatches AI Art",
    "Z:/Plex Media 1/Animated Movies",
    "Z:/Plex Media 1/Animated TV Shows",
    "Z:/Plex Media 1/Disney Movie Collection",
    "Z:/Plex Media 1/Movies",
    "Z:/Plex Media 1/TV Shows",

    # D: Drive - Personal archives
    "D:/Akashic Foundation Images",
    "D:/New Images",
    "D:/Images Shared on X",
    "D:/Images Shared on Uncut",
    "D:/Failed Images",
]

# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class IngestConfig:
    workers: int = 6
    batch_size: int = 50
    frame_interval: float = 10.0
    max_frames_per_video: int = 200
    progress_file: str = "tardis_full_progress.json"
    image_extensions: Set[str] = field(default_factory=lambda: {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'
    })
    video_extensions: Set[str] = field(default_factory=lambda: {
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.m4v'
    })


@dataclass
class IngestProgress:
    started_at: float = 0.0
    processed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    image_cards: int = 0
    video_cards: int = 0
    completed_sources: List[str] = field(default_factory=list)
    processed_paths: Set[str] = field(default_factory=set)
    seen_hashes: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)
    source_stats: Dict[str, Dict] = field(default_factory=dict)

    def save(self, path: Path):
        data = {
            'started_at': self.started_at,
            'last_updated': time.time(),
            'processed_files': self.processed_files,
            'skipped_files': self.skipped_files,
            'failed_files': self.failed_files,
            'image_cards': self.image_cards,
            'video_cards': self.video_cards,
            'completed_sources': self.completed_sources,
            'processed_paths': list(self.processed_paths)[-50000:],  # Keep last 50k
            'seen_hashes': list(self.seen_hashes),
            'errors': self.errors[-100:],
            'source_stats': self.source_stats,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> 'IngestProgress':
        if not path.exists():
            return cls(started_at=time.time())
        with open(path) as f:
            data = json.load(f)
        return cls(
            started_at=data.get('started_at', time.time()),
            processed_files=data.get('processed_files', 0),
            skipped_files=data.get('skipped_files', 0),
            failed_files=data.get('failed_files', 0),
            image_cards=data.get('image_cards', 0),
            video_cards=data.get('video_cards', 0),
            completed_sources=data.get('completed_sources', []),
            processed_paths=set(data.get('processed_paths', [])),
            seen_hashes=set(data.get('seen_hashes', [])),
            errors=data.get('errors', []),
            source_stats=data.get('source_stats', {}),
        )


# ==============================================================================
# WORKER FUNCTIONS (run in separate processes)
# ==============================================================================

def extract_image(path: str) -> Optional[Dict]:
    """Extract features from an image. Uses numpy buffer for Unicode paths."""
    try:
        import cv2
        import numpy as np

        # Read via numpy buffer to handle Unicode paths (DALL·E etc)
        with open(path, 'rb') as f:
            data = np.frombuffer(f.read(), np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return None

        h, w = img.shape[:2]

        # Perceptual hash
        small = cv2.resize(img, (32, 32))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        dct = cv2.dct(gray)
        dct_low = dct[:8, :8]
        median = np.median(dct_low)
        bits = (dct_low > median).flatten()
        phash = f"{sum(1 << i for i, b in enumerate(bits) if b):016x}"

        # Features
        gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray_full) / 255.0)
        edges = cv2.Canny(gray_full, 50, 150)
        complexity = float(np.mean(edges > 0))
        dominant = img.reshape(-1, 3).mean(axis=0).astype(int).tolist()

        return {
            'type': 'image',
            'source': path,
            'phash': phash,
            'width': w,
            'height': h,
            'brightness': brightness,
            'complexity': complexity,
            'dominant_color': dominant,
            'timestamp': 0.0,
        }
    except Exception as e:
        return {'error': str(e), 'source': path}


def get_short_path_win(path: str) -> str:
    """Get Windows 8.3 short path name for Unicode path handling."""
    try:
        import ctypes
        from ctypes import wintypes
        _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        _GetShortPathNameW.restype = wintypes.DWORD

        buf_size = _GetShortPathNameW(path, None, 0)
        if buf_size == 0:
            return path
        buf = ctypes.create_unicode_buffer(buf_size)
        _GetShortPathNameW(path, buf, buf_size)
        return buf.value
    except Exception:
        return path


def extract_video(path: str, interval: float = 10.0, max_frames: int = 200) -> List[Dict]:
    """Extract features from video frames."""
    try:
        import cv2
        import numpy as np

        short_path = get_short_path_win(path)
        cap = cv2.VideoCapture(short_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0 or total <= 0:
            cap.release()
            return [{'error': 'Invalid video', 'source': path}]

        skip = max(1, int(fps * interval))
        indices = list(range(0, total, skip))[:max_frames]

        results = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]
            ts = idx / fps

            small = cv2.resize(frame, (32, 32))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
            dct = cv2.dct(gray)
            dct_low = dct[:8, :8]
            median = np.median(dct_low)
            bits = (dct_low > median).flatten()
            phash = f"{sum(1 << i for i, b in enumerate(bits) if b):016x}"

            gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray_full) / 255.0)
            edges = cv2.Canny(gray_full, 50, 150)
            complexity = float(np.mean(edges > 0))
            dominant = frame.reshape(-1, 3).mean(axis=0).astype(int).tolist()

            results.append({
                'type': 'video_frame',
                'source': path,
                'phash': phash,
                'width': w,
                'height': h,
                'brightness': brightness,
                'complexity': complexity,
                'dominant_color': dominant,
                'timestamp': ts,
            })

        cap.release()
        return results

    except Exception as e:
        return [{'error': str(e), 'source': path}]


def process_file(args: tuple) -> List[Dict]:
    """Process a single file."""
    path, ftype, interval, max_frames = args
    if ftype == 'image':
        r = extract_image(path)
        return [r] if r else []
    else:
        return extract_video(path, interval, max_frames)


# ==============================================================================
# MAIN INGESTION
# ==============================================================================

def run_full_ingestion(workers: int = 6, sources: List[str] = None):
    """Run ingestion across all sources."""
    if sources is None:
        sources = MEDIA_SOURCES

    config = IngestConfig(workers=workers)
    progress_path = ROOT / "state" / config.progress_file
    progress = IngestProgress.load(progress_path)

    print(f"\n{'='*70}")
    print("MEMORY TARDIS - Full Archive Ingestion")
    print(f"{'='*70}")
    print(f"Workers: {workers}")
    print(f"Sources: {len(sources)}")
    print(f"Resume from: {progress.processed_files} files, {len(progress.seen_hashes)} unique hashes")
    print()

    # Get coordinator
    from memory.helix import get_helix_coordinator
    from memory.helix import HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate, OwnershipLevel
    coord = get_helix_coordinator()

    total_start = time.time()

    for source_dir in sources:
        if source_dir in progress.completed_sources:
            print(f"[SKIP] Already completed: {source_dir}")
            continue

        if not os.path.exists(source_dir):
            print(f"[SKIP] Not found: {source_dir}")
            continue

        print(f"\n[SOURCE] {source_dir}")
        print("-" * 70)

        # Scan this source
        all_ext = config.image_extensions | config.video_extensions
        files = []

        for root, dirs, filenames in os.walk(source_dir):
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext not in all_ext:
                    continue
                full = str(Path(root) / fname)
                if full in progress.processed_paths:
                    continue
                ftype = 'image' if ext in config.image_extensions else 'video'
                files.append((full, ftype))

        print(f"  Found {len(files)} new files")

        if not files:
            progress.completed_sources.append(source_dir)
            progress.save(progress_path)
            continue

        source_start = time.time()
        source_cards = 0
        batch_count = 0

        work_items = [(p, t, config.frame_interval, config.max_frames_per_video) for p, t in files]

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_file, item): item[0] for item in work_items}

            for future in as_completed(futures):
                path = futures[future]

                try:
                    features = future.result(timeout=120)

                    for feat in features:
                        if 'error' in feat:
                            progress.errors.append(f"{feat['source']}: {feat['error']}")
                            continue

                        phash = feat.get('phash', '')
                        if phash in progress.seen_hashes:
                            progress.skipped_files += 1
                            continue

                        progress.seen_hashes.add(phash)

                        # Create helix coordinate
                        br = feat.get('brightness', 0.5)
                        cx = feat.get('complexity', 0.5)

                        hcoord = HelixCoordinate(
                            affect=AffectCoordinate(domain=7, valence=int(br*9), intensity=int(cx*9)),
                            semantic=SemanticCoordinate(domain=8, subdomain=1 if feat['type']=='video_frame' else 0, detail=0),
                            temporal=TemporalCoordinate(scale=0, recurrence=0, decay=5),
                        )

                        coord.create_card(
                            content=feat,
                            coord=hcoord,
                            owner_mind="TardisIngest",
                            ownership_level=OwnershipLevel.SYSTEM,
                        )

                        source_cards += 1
                        if feat['type'] == 'image':
                            progress.image_cards += 1
                        else:
                            progress.video_cards += 1

                    progress.processed_files += 1
                    progress.processed_paths.add(path)
                    batch_count += 1

                    # Progress update
                    if batch_count % 25 == 0:
                        elapsed = time.time() - source_start
                        rate = batch_count / elapsed if elapsed > 0 else 0
                        remaining = len(files) - batch_count
                        eta = remaining / rate if rate > 0 else 0
                        total_cards = progress.image_cards + progress.video_cards
                        print(f"    [{batch_count}/{len(files)}] {rate:.1f}/sec, "
                              f"cards={total_cards}, ETA: {eta/60:.0f}m")

                    # Save periodically
                    if batch_count % config.batch_size == 0:
                        progress.save(progress_path)
                        coord.save()

                except Exception as e:
                    progress.failed_files += 1
                    progress.errors.append(f"{path}: {str(e)}")

        # Source complete
        source_elapsed = time.time() - source_start
        progress.completed_sources.append(source_dir)
        progress.source_stats[source_dir] = {
            'files': batch_count,
            'cards': source_cards,
            'time_sec': source_elapsed,
        }
        progress.save(progress_path)
        coord.save()

        print(f"  Completed: {batch_count} files, {source_cards} cards in {source_elapsed/60:.1f}m")

    # Final save
    progress.save(progress_path)
    coord.save()

    total_elapsed = time.time() - total_start
    print()
    print(f"{'='*70}")
    print("FULL INGESTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Time: {total_elapsed/60:.1f} min ({total_elapsed/3600:.1f} hours)")
    print(f"  Files processed: {progress.processed_files}")
    print(f"  Image cards: {progress.image_cards}")
    print(f"  Video cards: {progress.video_cards}")
    print(f"  Duplicates skipped: {progress.skipped_files}")
    print(f"  Failed: {progress.failed_files}")
    print(f"  Unique hashes: {len(progress.seen_hashes)}")
    print(f"  Total cards in helix: {len(coord._cards)}")
    print()
    print("Source breakdown:")
    for src, stats in progress.source_stats.items():
        print(f"  {Path(src).name}: {stats['files']} files, {stats['cards']} cards")

    return progress


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--source", type=str, help="Process single source instead of all")
    args = parser.parse_args()

    if args.source:
        run_full_ingestion(args.workers, [args.source])
    else:
        run_full_ingestion(args.workers)
