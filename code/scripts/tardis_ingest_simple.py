#!/usr/bin/env python3
"""
MEMORY TARDIS - Simple Batch Ingestion (CPU-only, no PyTorch)

Clean version without problematic GPU imports.
Uses pure OpenCV for all feature extraction.
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, List, Set, Any
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class IngestConfig:
    source_dir: str = ""
    workers: int = 4
    batch_size: int = 25
    frame_interval: float = 10.0
    max_frames_per_video: int = 200
    progress_file: str = "tardis_simple_progress.json"
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
    processed_paths: Set[str] = field(default_factory=set)
    seen_hashes: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)

    def save(self, path: Path):
        data = {
            'started_at': self.started_at,
            'last_updated': time.time(),
            'processed_files': self.processed_files,
            'skipped_files': self.skipped_files,
            'failed_files': self.failed_files,
            'image_cards': self.image_cards,
            'video_cards': self.video_cards,
            'processed_paths': list(self.processed_paths)[-10000:],  # Keep last 10k
            'seen_hashes': list(self.seen_hashes),
            'errors': self.errors[-50:],
        }
        with open(path, 'w') as f:
            json.dump(data, f)

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
            processed_paths=set(data.get('processed_paths', [])),
            seen_hashes=set(data.get('seen_hashes', [])),
            errors=data.get('errors', []),
        )


# ==============================================================================
# WORKER FUNCTIONS (run in separate processes)
# ==============================================================================

def extract_image(path: str) -> Optional[Dict]:
    """Extract features from an image. Runs in worker process.

    Uses numpy buffer reading to handle Unicode paths on Windows.
    OpenCV's imread() fails on paths with special characters like ·
    """
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
            return path  # Fallback to original
        buf = ctypes.create_unicode_buffer(buf_size)
        _GetShortPathNameW(path, buf, buf_size)
        return buf.value
    except Exception:
        return path  # Fallback to original on non-Windows or error


def extract_video(path: str, interval: float = 10.0, max_frames: int = 200) -> List[Dict]:
    """Extract features from video frames. Runs in worker process.

    Uses Windows short path names to handle Unicode paths.
    """
    try:
        import cv2
        import numpy as np

        # Use short path on Windows to handle Unicode (DALL·E etc)
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

            # Quick phash
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

def run_ingestion(source_dir: str, workers: int = 4):
    """Run the ingestion."""
    config = IngestConfig(source_dir=source_dir, workers=workers)
    progress_path = ROOT / "state" / config.progress_file
    progress = IngestProgress.load(progress_path)

    print(f"\n{'='*70}")
    print("MEMORY TARDIS - Simple Ingestion")
    print(f"{'='*70}")
    print(f"Source: {source_dir}")
    print(f"Workers: {workers}")
    print(f"Resume from: {progress.processed_files} files")
    print()

    # Scan
    print("[SCAN] Finding media files...")
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

    print(f"[SCAN] Found {len(files)} new files")

    if not files:
        print("[DONE] Nothing to process!")
        return progress

    # Get coordinator
    from memory.helix import get_helix_coordinator
    from memory.helix import HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate, OwnershipLevel
    coord = get_helix_coordinator()

    print(f"[INGEST] Starting with {workers} workers...")
    start = time.time()
    batch_count = 0

    work_items = [(p, t, config.frame_interval, config.max_frames_per_video) for p, t in files]

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_file, item): item[0] for item in work_items}

        for future in as_completed(futures):
            path = futures[future]

            try:
                features = future.result(timeout=120)  # 2 min timeout per file

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

                    if feat['type'] == 'image':
                        progress.image_cards += 1
                    else:
                        progress.video_cards += 1

                progress.processed_files += 1
                progress.processed_paths.add(path)
                batch_count += 1

                # Progress update
                if batch_count % 10 == 0:
                    elapsed = time.time() - start
                    rate = batch_count / elapsed if elapsed > 0 else 0
                    remaining = len(files) - batch_count
                    eta = remaining / rate if rate > 0 else 0
                    print(f"  [{batch_count}/{len(files)}] {rate:.1f}/sec, "
                          f"cards={progress.image_cards + progress.video_cards}, "
                          f"ETA: {eta/60:.0f}m")

                # Save periodically
                if batch_count % config.batch_size == 0:
                    progress.save(progress_path)
                    coord.save()

            except Exception as e:
                progress.failed_files += 1
                progress.errors.append(f"{path}: {str(e)}")

    # Final save
    progress.save(progress_path)
    coord.save()

    elapsed = time.time() - start
    print()
    print(f"{'='*70}")
    print("COMPLETE")
    print(f"{'='*70}")
    print(f"  Time: {elapsed/60:.1f} min")
    print(f"  Processed: {progress.processed_files}")
    print(f"  Image cards: {progress.image_cards}")
    print(f"  Video cards: {progress.video_cards}")
    print(f"  Skipped: {progress.skipped_files}")
    print(f"  Failed: {progress.failed_files}")
    print(f"  Total cards: {len(coord._cards)}")

    return progress


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="Z:/Plex Media 1")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    run_ingestion(args.source, args.workers)
