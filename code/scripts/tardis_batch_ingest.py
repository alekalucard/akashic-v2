#!/usr/bin/env python3
"""
MEMORY TARDIS - Batch Media Ingestion

Ingests massive media archives into the Triple Helix memory system.
Designed for 40-60 TB scale with resume support and parallel processing.

Features:
- Parallel worker pool (CPU cores)
- Resume from interruption (progress tracking)
- Deduplication via perceptual hash
- Format detection (images vs videos)
- Batched saves (every N items)
- Progress reporting

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import sys
import os
import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Set, Any
from dataclasses import dataclass, field, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Add paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Check dependencies
try:
    import cv2
    import numpy as np
    HAS_VISION = True
except ImportError:
    HAS_VISION = False
    print("[WARN] OpenCV not available - video processing disabled")

# Check GPU availability (optional - don't fail if not available)
HAS_GPU = False
GPU_DEVICE = None
try:
    import torch
    if torch.cuda.is_available():
        HAS_GPU = True
        GPU_DEVICE = torch.device('cuda:0')
        print(f"[GPU] CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        print("[GPU] CUDA not available, using CPU")
except (ImportError, OSError) as e:
    # OSError catches DLL loading failures
    print(f"[GPU] Using CPU (PyTorch unavailable)")


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class TardisConfig:
    """Configuration for batch ingestion."""
    # Source
    source_dir: str = ""

    # Processing
    workers: int = field(default_factory=lambda: max(1, mp.cpu_count() - 2))
    batch_size: int = 100  # Save progress every N items
    frame_interval: float = 10.0  # Seconds between video frames
    max_frames_per_video: int = 500  # Cap frames per video

    # Resume
    progress_file: str = "tardis_progress.json"

    # Filtering
    image_extensions: Set[str] = field(default_factory=lambda: {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'
    })
    video_extensions: Set[str] = field(default_factory=lambda: {
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'
    })

    # Output
    verbose: bool = True


@dataclass
class TardisProgress:
    """Tracks ingestion progress for resume support."""
    started_at: float = 0.0
    last_updated: float = 0.0

    # Counts
    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0

    # Cards created
    image_cards: int = 0
    video_cards: int = 0
    audio_cards: int = 0

    # Tracking
    processed_paths: Set[str] = field(default_factory=set)
    seen_hashes: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)

    def save(self, path: Path):
        """Save progress to disk."""
        data = {
            'started_at': self.started_at,
            'last_updated': time.time(),
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'skipped_files': self.skipped_files,
            'failed_files': self.failed_files,
            'image_cards': self.image_cards,
            'video_cards': self.video_cards,
            'audio_cards': self.audio_cards,
            'processed_paths': list(self.processed_paths),
            'seen_hashes': list(self.seen_hashes),
            'errors': self.errors[-100:],  # Keep last 100 errors
        }
        with open(path, 'w') as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: Path) -> 'TardisProgress':
        """Load progress from disk."""
        if not path.exists():
            return cls(started_at=time.time())

        with open(path) as f:
            data = json.load(f)

        return cls(
            started_at=data.get('started_at', time.time()),
            last_updated=data.get('last_updated', 0),
            total_files=data.get('total_files', 0),
            processed_files=data.get('processed_files', 0),
            skipped_files=data.get('skipped_files', 0),
            failed_files=data.get('failed_files', 0),
            image_cards=data.get('image_cards', 0),
            video_cards=data.get('video_cards', 0),
            audio_cards=data.get('audio_cards', 0),
            processed_paths=set(data.get('processed_paths', [])),
            seen_hashes=set(data.get('seen_hashes', [])),
            errors=data.get('errors', []),
        )


# ==============================================================================
# FEATURE EXTRACTION (GPU-ACCELERATED when available)
# ==============================================================================

def compute_phash_gpu(img: np.ndarray, hash_size: int = 8) -> str:
    """Compute perceptual hash using GPU (torch) when available."""
    if HAS_GPU:
        try:
            # Resize on CPU (fast enough)
            img_resized = cv2.resize(img, (hash_size * 4, hash_size * 4))
            if len(img_resized.shape) == 3:
                img_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

            # DCT on GPU using torch
            img_tensor = torch.from_numpy(img_resized.astype(np.float32)).to(GPU_DEVICE)
            # torch.fft.dct is not directly available, use rfft as approximation
            dct = torch.fft.rfft2(img_tensor).real
            dct_low = dct[:hash_size, :hash_size].cpu().numpy()
            median = np.median(dct_low)
            bits = (dct_low > median).flatten()
            hash_int = sum(1 << i for i, b in enumerate(bits) if b)
            return f"{hash_int:016x}"
        except Exception:
            pass  # Fall back to CPU

    # CPU fallback
    img_resized = cv2.resize(img, (hash_size * 4, hash_size * 4))
    if len(img_resized.shape) == 3:
        img_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    img_float = img_resized.astype(np.float32)
    dct = cv2.dct(img_float)
    dct_low = dct[:hash_size, :hash_size]
    median = np.median(dct_low)
    bits = (dct_low > median).flatten()
    hash_int = sum(1 << i for i, b in enumerate(bits) if b)
    return f"{hash_int:016x}"


def compute_phash(img: np.ndarray, hash_size: int = 8) -> str:
    """Compute perceptual hash (delegates to GPU version)."""
    return compute_phash_gpu(img, hash_size)


def extract_features_gpu_batch(images: List[np.ndarray]) -> List[Dict]:
    """
    Extract features from a BATCH of images using GPU.

    This is the key optimization - batch processing on GPU is much faster
    than per-image CPU processing.
    """
    if not HAS_GPU or not images:
        return [extract_image_features_cpu(img, f"batch_{i}") for i, img in enumerate(images)]

    try:
        results = []

        # Prepare batch tensors
        batch_gray = []
        batch_small = []

        for img in images:
            if img is None:
                batch_gray.append(None)
                batch_small.append(None)
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            small = cv2.resize(gray, (32, 32))
            batch_gray.append(gray)
            batch_small.append(small)

        # Process valid images on GPU
        valid_indices = [i for i, g in enumerate(batch_gray) if g is not None]

        if valid_indices:
            # Stack valid small images for batch GPU processing
            valid_small = np.stack([batch_small[i].astype(np.float32) for i in valid_indices])
            small_tensor = torch.from_numpy(valid_small).to(GPU_DEVICE)

            # Batch DCT via FFT on GPU
            dct_batch = torch.fft.rfft2(small_tensor).real

            # Batch brightness (mean on GPU)
            brightness_batch = small_tensor.mean(dim=(1, 2)) / 255.0
            brightness_list = brightness_batch.cpu().numpy()

            # Extract results
            for idx, valid_idx in enumerate(valid_indices):
                img = images[valid_idx]
                height, width = img.shape[:2]

                # pHash from DCT
                dct_low = dct_batch[idx, :8, :8].cpu().numpy()
                median = np.median(dct_low)
                bits = (dct_low > median).flatten()
                hash_int = sum(1 << i for i, b in enumerate(bits) if b)
                phash = f"{hash_int:016x}"

                # Brightness from GPU
                brightness = float(brightness_list[idx])

                # Complexity still on CPU (Canny is hard to batch)
                edges = cv2.Canny(batch_gray[valid_idx], 50, 150)
                complexity = float(np.mean(edges > 0))

                # Dominant color
                pixels = img.reshape(-1, 3)
                dominant = pixels.mean(axis=0).astype(int).tolist()

                results.append({
                    'type': 'image',
                    'source': f'batch_{valid_idx}',
                    'phash': phash,
                    'width': width,
                    'height': height,
                    'brightness': brightness,
                    'complexity': complexity,
                    'dominant_color': dominant,
                    'timestamp': 0.0,
                })

        return results

    except Exception as e:
        print(f"[GPU] Batch processing failed: {e}, falling back to CPU")
        return [extract_image_features_cpu(img, f"batch_{i}") for i, img in enumerate(images)]


def extract_image_features_cpu(img: np.ndarray, source: str = "") -> Optional[Dict]:
    """Extract features from a single image on CPU."""
    try:
        if img is None:
            return None

        height, width = img.shape[:2]
        phash = compute_phash(img)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        brightness = float(np.mean(gray) / 255.0)
        edges = cv2.Canny(gray, 50, 150)
        complexity = float(np.mean(edges > 0))
        pixels = img.reshape(-1, 3) if len(img.shape) == 3 else img.reshape(-1, 1)
        dominant = pixels.mean(axis=0).astype(int).tolist()

        return {
            'type': 'image',
            'source': source,
            'phash': phash,
            'width': width,
            'height': height,
            'brightness': brightness,
            'complexity': complexity,
            'dominant_color': dominant,
            'timestamp': 0.0,
        }
    except Exception as e:
        return {'error': str(e), 'source': source}


def extract_image_features(path: str) -> Optional[Dict]:
    """Extract features from a single image (GPU-accelerated when available)."""
    try:
        img = cv2.imread(path)
        if img is None:
            return None

        result = extract_image_features_cpu(img, path)
        if result:
            result['source'] = path
        return result
    except Exception as e:
        return {'error': str(e), 'source': path}


def extract_video_features(
    path: str,
    frame_interval: float = 10.0,
    max_frames: int = 500
) -> List[Dict]:
    """
    Extract features from video frames using GPU batch processing.

    Reads frames in batches, processes them on GPU, returns results.
    This is MUCH faster than per-frame CPU processing.
    """
    features = []
    GPU_BATCH_SIZE = 16  # Process 16 frames at a time on GPU

    try:
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0 or total_frames <= 0:
            cap.release()
            return [{'error': 'Invalid video', 'source': path}]

        frame_skip = int(fps * frame_interval)
        frame_indices = list(range(0, total_frames, frame_skip))[:max_frames]

        # Collect frames in batches for GPU processing
        frame_batch = []
        meta_batch = []  # (idx, timestamp, height, width)

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()

            if not ret:
                continue

            timestamp = idx / fps
            height, width = frame.shape[:2]

            frame_batch.append(frame)
            meta_batch.append((idx, timestamp, height, width))

            # Process batch when full
            if len(frame_batch) >= GPU_BATCH_SIZE:
                batch_features = _process_video_frame_batch(frame_batch, meta_batch, path)
                features.extend(batch_features)
                frame_batch = []
                meta_batch = []

        # Process remaining frames
        if frame_batch:
            batch_features = _process_video_frame_batch(frame_batch, meta_batch, path)
            features.extend(batch_features)

        cap.release()

    except Exception as e:
        return [{'error': str(e), 'source': path}]

    return features


def _process_video_frame_batch(frames: List[np.ndarray], metas: List[tuple], source: str) -> List[Dict]:
    """Process a batch of video frames, using GPU if available."""
    features = []

    if HAS_GPU and len(frames) > 1:
        try:
            # Prepare batch for GPU
            grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
            smalls = [cv2.resize(g, (32, 32)).astype(np.float32) for g in grays]

            # Stack and send to GPU
            small_tensor = torch.from_numpy(np.stack(smalls)).to(GPU_DEVICE)

            # Batch DCT via FFT on GPU
            dct_batch = torch.fft.rfft2(small_tensor).real

            # Batch brightness on GPU
            brightness_batch = small_tensor.mean(dim=(1, 2)) / 255.0
            brightness_list = brightness_batch.cpu().numpy()

            # Extract per-frame features
            for i, (frame, gray, meta) in enumerate(zip(frames, grays, metas)):
                idx, timestamp, height, width = meta

                # pHash from GPU DCT
                dct_low = dct_batch[i, :8, :8].cpu().numpy()
                median = np.median(dct_low)
                bits = (dct_low > median).flatten()
                hash_int = sum(1 << j for j, b in enumerate(bits) if b)
                phash = f"{hash_int:016x}"

                # Brightness from GPU
                brightness = float(brightness_list[i])

                # Complexity on CPU (Canny)
                edges = cv2.Canny(gray, 50, 150)
                complexity = float(np.mean(edges > 0))

                # Dominant color
                pixels = frame.reshape(-1, 3)
                dominant = pixels.mean(axis=0).astype(int).tolist()

                features.append({
                    'type': 'video_frame',
                    'source': source,
                    'phash': phash,
                    'width': width,
                    'height': height,
                    'brightness': brightness,
                    'complexity': complexity,
                    'dominant_color': dominant,
                    'timestamp': timestamp,
                    'frame_index': idx,
                })

            return features

        except Exception as e:
            print(f"[GPU] Video batch failed: {e}, using CPU")

    # CPU fallback (per-frame processing)
    for frame, meta in zip(frames, metas):
        idx, timestamp, height, width = meta

        phash = compute_phash(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray) / 255.0)
        edges = cv2.Canny(gray, 50, 150)
        complexity = float(np.mean(edges > 0))
        pixels = frame.reshape(-1, 3)
        dominant = pixels.mean(axis=0).astype(int).tolist()

        features.append({
            'type': 'video_frame',
            'source': source,
            'phash': phash,
            'width': width,
            'height': height,
            'brightness': brightness,
            'complexity': complexity,
            'dominant_color': dominant,
            'timestamp': timestamp,
            'frame_index': idx,
        })

    return features


def process_file(args: tuple) -> List[Dict]:
    """Process a single file (runs in worker process)."""
    path, file_type, frame_interval, max_frames = args

    if file_type == 'image':
        result = extract_image_features(path)
        return [result] if result else []
    elif file_type == 'video':
        return extract_video_features(path, frame_interval, max_frames)
    else:
        return []


# ==============================================================================
# TARDIS INGESTION ENGINE
# ==============================================================================

class TardisIngestion:
    """
    Batch ingestion engine for the Memory TARDIS.

    Ingests massive media archives with:
    - Parallel processing
    - Resume support
    - Deduplication
    - Progress tracking
    """

    def __init__(self, config: TardisConfig):
        self.config = config
        self.progress_path = ROOT / "state" / config.progress_file
        self.progress = TardisProgress.load(self.progress_path)

        # Helix coordinator (lazy load)
        self._coordinator = None

    @property
    def coordinator(self):
        if self._coordinator is None:
            from memory.helix import get_helix_coordinator
            self._coordinator = get_helix_coordinator()
        return self._coordinator

    def scan_files(self, source_dir: Path) -> List[tuple]:
        """Scan directory for media files."""
        files = []

        all_extensions = self.config.image_extensions | self.config.video_extensions

        for root, dirs, filenames in os.walk(source_dir):
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext not in all_extensions:
                    continue

                full_path = str(Path(root) / filename)

                # Skip already processed
                if full_path in self.progress.processed_paths:
                    continue

                file_type = 'image' if ext in self.config.image_extensions else 'video'
                files.append((full_path, file_type))

        return files

    def ingest_features(self, features: List[Dict]) -> int:
        """Ingest extracted features into Helix."""
        from memory.helix import (
            HelixCoordinate, AffectCoordinate, SemanticCoordinate,
            TemporalCoordinate, OwnershipLevel
        )

        cards_created = 0

        for feat in features:
            if 'error' in feat:
                self.progress.errors.append(f"{feat['source']}: {feat['error']}")
                continue

            phash = feat.get('phash', '')

            # Deduplication
            if phash in self.progress.seen_hashes:
                self.progress.skipped_files += 1
                continue

            self.progress.seen_hashes.add(phash)

            # Build coordinate
            brightness = feat.get('brightness', 0.5)
            complexity = feat.get('complexity', 0.5)

            affect = AffectCoordinate(
                domain=7,
                valence=int(brightness * 9),
                intensity=int(complexity * 9),
            )

            semantic = SemanticCoordinate(
                domain=8,  # Media
                subdomain=1 if feat['type'] == 'video_frame' else 0,
                detail=0,
            )

            temporal = TemporalCoordinate(
                scale=0,
                recurrence=0,
                decay=5,
            )

            coord = HelixCoordinate(affect=affect, semantic=semantic, temporal=temporal)

            try:
                self.coordinator.create_card(
                    content=feat,
                    coord=coord,
                    owner_mind="TardisIngestion",
                    ownership_level=OwnershipLevel.SYSTEM,
                    metadata={'type': feat['type'], 'source': feat['source']},
                )
                cards_created += 1

                if feat['type'] == 'image':
                    self.progress.image_cards += 1
                else:
                    self.progress.video_cards += 1

            except Exception as e:
                self.progress.errors.append(f"Card creation failed: {e}")

        return cards_created

    def run(self, source_dir: str) -> TardisProgress:
        """Run the full ingestion pipeline."""
        source_path = Path(source_dir)

        if not source_path.exists():
            print(f"[ERROR] Source directory not found: {source_dir}")
            return self.progress

        print(f"\n{'='*70}")
        print(f"MEMORY TARDIS - Batch Ingestion")
        print(f"{'='*70}")
        print(f"Source: {source_dir}")
        print(f"Workers: {self.config.workers}")
        print(f"Resume: {self.progress.processed_files} files already done")
        print()

        # Scan for files
        print("[SCAN] Scanning for media files...")
        files = self.scan_files(source_path)
        self.progress.total_files = len(files) + self.progress.processed_files
        print(f"[SCAN] Found {len(files)} new files to process")
        print()

        if not files:
            print("[DONE] No new files to process!")
            return self.progress

        # Prepare work items
        work_items = [
            (path, ftype, self.config.frame_interval, self.config.max_frames_per_video)
            for path, ftype in files
        ]

        # Process with worker pool
        print(f"[INGEST] Starting ingestion with {self.config.workers} workers...")
        start_time = time.time()
        batch_count = 0

        with ProcessPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {executor.submit(process_file, item): item[0] for item in work_items}

            for future in as_completed(futures):
                path = futures[future]

                try:
                    features = future.result()
                    cards = self.ingest_features(features)
                    self.progress.processed_files += 1
                    self.progress.processed_paths.add(path)
                    batch_count += 1

                    # Progress update
                    if self.config.verbose and self.progress.processed_files % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = self.progress.processed_files / elapsed if elapsed > 0 else 0
                        eta = (len(files) - batch_count) / rate if rate > 0 else 0
                        print(f"  [{self.progress.processed_files}/{self.progress.total_files}] "
                              f"{rate:.1f} files/sec, ETA: {eta/60:.1f} min")

                    # Save progress periodically
                    if batch_count % self.config.batch_size == 0:
                        self.progress.save(self.progress_path)
                        self.coordinator.save()

                except Exception as e:
                    self.progress.failed_files += 1
                    self.progress.errors.append(f"{path}: {str(e)}")

        # Final save
        self.progress.save(self.progress_path)
        self.coordinator.save()

        elapsed = time.time() - start_time

        print()
        print(f"{'='*70}")
        print(f"INGESTION COMPLETE")
        print(f"{'='*70}")
        print(f"  Time: {elapsed/60:.1f} minutes")
        print(f"  Files processed: {self.progress.processed_files}")
        print(f"  Image cards: {self.progress.image_cards}")
        print(f"  Video cards: {self.progress.video_cards}")
        print(f"  Skipped (duplicates): {self.progress.skipped_files}")
        print(f"  Failed: {self.progress.failed_files}")
        print(f"  Total cards: {len(self.coordinator._cards)}")

        # Calculate compression
        cards_size = len(self.coordinator._cards) * 500 / 1024 / 1024  # Estimate 500 bytes/card
        print(f"  Estimated card storage: {cards_size:.1f} MB")
        print()

        return self.progress


# ==============================================================================
# MAIN
# ==============================================================================

def ingest_plex_media():
    """Ingest the Plex Media archive."""
    config = TardisConfig(
        source_dir="Z:/Plex Media 1",
        workers=max(1, mp.cpu_count() - 2),
        batch_size=50,
        frame_interval=10.0,
        max_frames_per_video=300,
        verbose=True,
    )

    engine = TardisIngestion(config)
    return engine.run(config.source_dir)


# ==============================================================================
# LIBRARY ORGANIZATION - Tracers create real movie/image gallery structure
# ==============================================================================

@dataclass
class MediaItem:
    """A media item in the library."""
    path: str
    media_type: str  # movie, tv_episode, image, ai_art
    title: str = ""
    series: str = ""  # For TV
    season: int = 0
    episode: int = 0
    year: int = 0
    cluster_id: str = ""


def parse_plex_path(path: str) -> MediaItem:
    """
    Parse Plex media path into structured metadata.

    Plex conventions:
    - Movies/Movie Name (Year)/Movie Name (Year).mkv
    - TV Shows/Series Name/Season XX/Series - S00E00 - Title.mkv
    - Sourpatches AI Art/filename.png
    """
    import re

    parts = Path(path).parts
    filename = Path(path).stem

    item = MediaItem(path=path, media_type='unknown')

    # Detect type from folder
    for i, part in enumerate(parts):
        if 'Movie' in part:
            item.media_type = 'movie'
            # Try to extract title and year
            match = re.search(r'(.+?)\s*\((\d{4})\)', filename)
            if match:
                item.title = match.group(1).strip()
                item.year = int(match.group(2))
            else:
                item.title = filename
            break

        elif 'TV Show' in part or 'Tv Show' in part:
            item.media_type = 'tv_episode'
            # Get series name
            if i + 1 < len(parts):
                item.series = parts[i + 1]
            # Parse season/episode
            match = re.search(r'S(\d+)E(\d+)', filename, re.I)
            if match:
                item.season = int(match.group(1))
                item.episode = int(match.group(2))
            # Get episode title
            title_match = re.search(r'E\d+\s*[-–]\s*(.+)$', filename, re.I)
            if title_match:
                item.title = title_match.group(1).strip()
            break

        elif 'Sourpatches' in part or 'AI Art' in part:
            item.media_type = 'ai_art'
            item.title = filename
            item.series = 'Sourpatches AI Art'
            break

        elif 'Animated' in part:
            if 'Movie' in part:
                item.media_type = 'animated_movie'
            else:
                item.media_type = 'animated_tv'
            item.title = filename
            break

        elif 'Disney' in part:
            item.media_type = 'disney_movie'
            item.title = filename
            break

    # Generate cluster ID based on grouping
    if item.media_type == 'tv_episode':
        # Cluster by series + season
        item.cluster_id = f"{item.series}_S{item.season:02d}"
    elif item.media_type == 'movie':
        # Each movie is its own cluster
        item.cluster_id = f"movie_{item.title}_{item.year}"
    elif item.media_type == 'ai_art':
        # Group by date or batch (could parse from filename)
        item.cluster_id = "sourpatches_art"
    else:
        item.cluster_id = f"{item.media_type}_{item.title}"

    return item


class LibraryOrganizer:
    """
    Organizes media using tracers into a proper library structure.

    Creates:
    - Clusters: Group related media (movie, season, art session)
    - Chains: Sequential ordering (episodes, scenes)
    - Links: Cross-references (actors, themes, styles)
    """

    def __init__(self):
        self.clusters: Dict[str, List[str]] = {}  # cluster_id -> card_ids
        self.chains: Dict[str, List[str]] = {}    # chain_id -> ordered card_ids
        self.series_map: Dict[str, List[str]] = {} # series -> cluster_ids (in order)

    def add_to_library(self, item: MediaItem, card_ids: List[str]):
        """Add a media item to the library structure."""
        # Add to cluster
        if item.cluster_id not in self.clusters:
            self.clusters[item.cluster_id] = []
        self.clusters[item.cluster_id].extend(card_ids)

        # For TV, build the episode chain
        if item.media_type == 'tv_episode':
            chain_key = f"{item.series}_chain"
            if chain_key not in self.chains:
                self.chains[chain_key] = []

            # Insert at correct position based on season/episode
            position = item.season * 1000 + item.episode
            self.chains[chain_key].append((position, card_ids[0] if card_ids else None))

            # Track series -> seasons
            if item.series not in self.series_map:
                self.series_map[item.series] = []
            if item.cluster_id not in self.series_map[item.series]:
                self.series_map[item.series].append(item.cluster_id)

    def get_series_episodes(self, series: str) -> List[str]:
        """Get all episode card IDs for a series in order."""
        chain_key = f"{series}_chain"
        if chain_key not in self.chains:
            return []

        # Sort by position and return card IDs
        sorted_chain = sorted(self.chains[chain_key], key=lambda x: x[0])
        return [card_id for pos, card_id in sorted_chain if card_id]

    def get_cluster_cards(self, cluster_id: str) -> List[str]:
        """Get all cards in a cluster."""
        return self.clusters.get(cluster_id, [])

    def search_by_type(self, media_type: str) -> List[str]:
        """Get all cluster IDs of a specific type."""
        return [cid for cid in self.clusters.keys() if media_type in cid]

    def stats(self) -> Dict:
        """Get library statistics."""
        return {
            'clusters': len(self.clusters),
            'chains': len(self.chains),
            'series': len(self.series_map),
            'total_items': sum(len(cards) for cards in self.clusters.values()),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory TARDIS Batch Ingestion")
    parser.add_argument("source", nargs="?", default="Z:/Plex Media 1", help="Source directory")
    parser.add_argument("--workers", type=int, default=0, help="Number of workers (0=auto)")
    parser.add_argument("--interval", type=float, default=10.0, help="Video frame interval (seconds)")
    parser.add_argument("--max-frames", type=int, default=300, help="Max frames per video")
    parser.add_argument("--batch-size", type=int, default=50, help="Save progress every N files")

    args = parser.parse_args()

    config = TardisConfig(
        source_dir=args.source,
        workers=args.workers if args.workers > 0 else max(1, mp.cpu_count() - 2),
        batch_size=args.batch_size,
        frame_interval=args.interval,
        max_frames_per_video=args.max_frames,
    )

    engine = TardisIngestion(config)
    engine.run(config.source_dir)
