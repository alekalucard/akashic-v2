#!/usr/bin/env python3
"""
MEMORY TARDIS - Images Only Ingestion

Ingests all IMAGE folders first (no video processing).
Maintains unified deduplication across all drives.
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, List, Set
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ==============================================================================
# IMAGE-ONLY SOURCES
# ==============================================================================

IMAGE_SOURCES = [
    # D: Drive - Personal image archives
    "D:/Akashic Foundation Images",
    "D:/New Images",
    "D:/Images Shared on X",
    "D:/Images Shared on Uncut",
    "D:/Failed Images",

    # Z: Drive - Already done, but included for completeness
    # "Z:/Plex Media 1/Sourpatches AI Art",  # DONE - 16k cards
]

# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class IngestConfig:
    workers: int = 6
    batch_size: int = 50
    progress_file: str = "tardis_images_progress.json"
    image_extensions: Set[str] = field(default_factory=lambda: {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'
    })


@dataclass
class IngestProgress:
    started_at: float = 0.0
    processed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    image_cards: int = 0
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
            'completed_sources': self.completed_sources,
            'processed_paths': list(self.processed_paths)[-50000:],
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
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(
                started_at=data.get('started_at', time.time()),
                processed_files=data.get('processed_files', 0),
                skipped_files=data.get('skipped_files', 0),
                failed_files=data.get('failed_files', 0),
                image_cards=data.get('image_cards', 0),
                completed_sources=data.get('completed_sources', []),
                processed_paths=set(data.get('processed_paths', [])),
                seen_hashes=set(data.get('seen_hashes', [])),
                errors=data.get('errors', []),
                source_stats=data.get('source_stats', {}),
            )
        except:
            return cls(started_at=time.time())

    def merge_hashes_from(self, other_progress_path: Path):
        """Merge seen_hashes from another progress file for cross-session dedup."""
        if other_progress_path.exists():
            try:
                with open(other_progress_path) as f:
                    data = json.load(f)
                other_hashes = set(data.get('seen_hashes', []))
                before = len(self.seen_hashes)
                self.seen_hashes.update(other_hashes)
                added = len(self.seen_hashes) - before
                if added > 0:
                    print(f"  [DEDUP] Merged {added} hashes from {other_progress_path.name}")
            except:
                pass


# ==============================================================================
# WORKER FUNCTION
# ==============================================================================

def extract_image(path: str) -> Optional[Dict]:
    """Extract features from an image. Uses numpy buffer for Unicode paths."""
    try:
        import cv2
        import numpy as np

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


def process_file(path: str) -> Optional[Dict]:
    """Process a single image file."""
    return extract_image(path)


# ==============================================================================
# MAIN INGESTION
# ==============================================================================

def run_images_ingestion(workers: int = 6):
    """Run ingestion for all image sources."""
    config = IngestConfig(workers=workers)
    progress_path = ROOT / "state" / config.progress_file
    progress = IngestProgress.load(progress_path)

    # Merge hashes from previous runs for cross-session deduplication
    progress.merge_hashes_from(ROOT / "state" / "tardis_simple_progress.json")
    progress.merge_hashes_from(ROOT / "state" / "tardis_full_progress.json")

    print(f"\n{'='*70}")
    print("MEMORY TARDIS - Images Only Ingestion")
    print(f"{'='*70}")
    print(f"Workers: {workers}")
    print(f"Sources: {len(IMAGE_SOURCES)}")
    print(f"Existing hashes (for dedup): {len(progress.seen_hashes)}")
    print()

    # Get coordinator
    from memory.helix import get_helix_coordinator
    from memory.helix import HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate, OwnershipLevel
    coord = get_helix_coordinator()

    total_start = time.time()
    total_new_cards = 0

    for source_dir in IMAGE_SOURCES:
        if source_dir in progress.completed_sources:
            print(f"[SKIP] Already completed: {source_dir}")
            continue

        if not os.path.exists(source_dir):
            print(f"[SKIP] Not found: {source_dir}")
            continue

        print(f"\n[SOURCE] {source_dir}")
        print("-" * 70)

        # Scan for images only
        files = []
        for root, dirs, filenames in os.walk(source_dir):
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext not in config.image_extensions:
                    continue
                full = str(Path(root) / fname)
                if full in progress.processed_paths:
                    continue
                files.append(full)

        print(f"  Found {len(files)} new image files")

        if not files:
            progress.completed_sources.append(source_dir)
            progress.save(progress_path)
            continue

        source_start = time.time()
        source_cards = 0
        batch_count = 0

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_file, f): f for f in files}

            for future in as_completed(futures):
                path = futures[future]

                try:
                    feat = future.result(timeout=60)

                    if feat is None:
                        progress.failed_files += 1
                        batch_count += 1
                        progress.processed_paths.add(path)
                        continue

                    if 'error' in feat:
                        progress.errors.append(f"{feat['source']}: {feat['error']}")
                        progress.failed_files += 1
                        batch_count += 1
                        progress.processed_paths.add(path)
                        continue

                    phash = feat.get('phash', '')
                    if phash in progress.seen_hashes:
                        progress.skipped_files += 1
                        batch_count += 1
                        progress.processed_paths.add(path)
                        continue

                    progress.seen_hashes.add(phash)

                    # Create helix coordinate
                    br = feat.get('brightness', 0.5)
                    cx = feat.get('complexity', 0.5)

                    hcoord = HelixCoordinate(
                        affect=AffectCoordinate(domain=7, valence=int(br*9), intensity=int(cx*9)),
                        semantic=SemanticCoordinate(domain=8, subdomain=0, detail=0),
                        temporal=TemporalCoordinate(scale=0, recurrence=0, decay=5),
                    )

                    coord.create_card(
                        content=feat,
                        coord=hcoord,
                        owner_mind="TardisIngest",
                        ownership_level=OwnershipLevel.SYSTEM,
                    )

                    source_cards += 1
                    total_new_cards += 1
                    progress.image_cards += 1
                    progress.processed_files += 1
                    progress.processed_paths.add(path)
                    batch_count += 1

                    # Progress update
                    if batch_count % 25 == 0:
                        elapsed = time.time() - source_start
                        rate = batch_count / elapsed if elapsed > 0 else 0
                        remaining = len(files) - batch_count
                        eta = remaining / rate if rate > 0 else 0
                        print(f"    [{batch_count}/{len(files)}] {rate:.1f}/sec, "
                              f"new={source_cards}, skipped={progress.skipped_files}, "
                              f"ETA: {eta/60:.0f}m")

                    # Save periodically
                    if batch_count % config.batch_size == 0:
                        progress.save(progress_path)
                        coord.save()

                except Exception as e:
                    progress.failed_files += 1
                    progress.errors.append(f"{path}: {str(e)}")
                    progress.processed_paths.add(path)
                    batch_count += 1

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

        print(f"  [DONE] Completed: {batch_count} files, {source_cards} new cards in {source_elapsed/60:.1f}m")

    # Final save
    progress.save(progress_path)
    coord.save()

    total_elapsed = time.time() - total_start
    print()
    print(f"{'='*70}")
    print("IMAGES INGESTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Time: {total_elapsed/60:.1f} min")
    print(f"  New cards created: {total_new_cards}")
    print(f"  Total image cards: {progress.image_cards}")
    print(f"  Duplicates skipped: {progress.skipped_files}")
    print(f"  Failed: {progress.failed_files}")
    print(f"  Unique hashes: {len(progress.seen_hashes)}")
    print(f"  Total cards in helix: {len(coord._cards)}")
    print()
    print("Source breakdown:")
    for src, stats in progress.source_stats.items():
        src_name = Path(src).name
        print(f"  {src_name}: {stats['files']} files, {stats['cards']} new cards")

    return progress


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    run_images_ingestion(args.workers)
