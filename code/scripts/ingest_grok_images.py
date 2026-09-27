# ==============================================================================
# GROK IMAGE INGESTION PIPELINE
# ==============================================================================
#
# PURPOSE:
#   Ingest all images from Grok/Twitter archive into Akashic visual memory.
#   Concurrent visual cortex training extracts V1/V2/V4/IT features.
#
# SOURCES:
#   - tweets_media/         21,153 JPG + 110 PNG images
#   - grok_chat_media/      Grok conversation images
#   - direct_messages_media/ DM images
#   - profile_media/        Profile images
#
# METADATA:
#   - tweets.js             Tweet text, timestamps, media references
#   - grok-chat-item.js     Grok conversation context
#
# OUTPUT:
#   - Visual signatures stored in P10_Memory/visual_memory/
#   - Helix memory cards with coordinate mapping
#
# ==============================================================================

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import re
import concurrent.futures
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict

# Add project root and fairies paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "fairies"))

# Source paths
GROK_DATA_ROOT = Path("F:/Sandbox/Grok/Extracted/data")
TWEETS_MEDIA = GROK_DATA_ROOT / "tweets_media"
GROK_CHAT_MEDIA = GROK_DATA_ROOT / "grok_chat_media"
DM_MEDIA = GROK_DATA_ROOT / "direct_messages_media"
PROFILE_MEDIA = GROK_DATA_ROOT / "profile_media"
COMMUNITY_MEDIA = GROK_DATA_ROOT / "community_tweet_media"

# Metadata files
TWEETS_JS = GROK_DATA_ROOT / "tweets.js"
GROK_CHAT_JS = GROK_DATA_ROOT / "grok-chat-item.js"
DM_JS = GROK_DATA_ROOT / "direct-messages.js"

# State file for resumption
STATE_FILE = PROJECT_ROOT / "state" / "grok_ingestion_state.json"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class MediaItem:
    """A media item with metadata."""
    path: Path
    media_id: str
    media_type: str  # "image" or "video"
    extension: str
    source: str  # "tweets", "grok_chat", "dm", "profile"

    # From metadata (optional)
    tweet_id: Optional[str] = None
    tweet_text: Optional[str] = None
    timestamp: Optional[datetime] = None
    context: Optional[str] = None

    # Processing results
    visual_signature_id: Optional[str] = None
    helix_card_id: Optional[str] = None
    phash: Optional[str] = None
    error: Optional[str] = None


@dataclass
class IngestionStats:
    """Track ingestion progress."""
    total_found: int = 0
    images_found: int = 0
    videos_found: int = 0
    processed: int = 0
    trained: int = 0
    duplicates: int = 0
    errors: int = 0
    cards_created: int = 0
    start_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        elapsed = time.time() - self.start_time
        rate = self.processed / elapsed if elapsed > 0 else 0
        return {
            "total_found": self.total_found,
            "images_found": self.images_found,
            "videos_found": self.videos_found,
            "processed": self.processed,
            "trained": self.trained,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "cards_created": self.cards_created,
            "elapsed_seconds": round(elapsed, 1),
            "rate_per_second": round(rate, 2),
        }


# ==============================================================================
# METADATA LOADING
# ==============================================================================

def parse_js_file(path: Path) -> Any:
    """Parse Twitter's JS-wrapped JSON files."""
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding='utf-8')
        # Twitter wraps JSON in: window.YTD.name.part0 = [...]
        # Find the JSON array/object after the =
        match = re.search(r'=\s*(\[[\s\S]*\]|\{[\s\S]*\})\s*$', content)
        if match:
            return json.loads(match.group(1))
        return None
    except Exception as e:
        print(f"[WARNING] Failed to parse {path.name}: {e}")
        return None


def build_tweet_metadata_index(tweets_data: List[dict]) -> Dict[str, dict]:
    """Build index: tweet_id -> tweet metadata."""
    index = {}
    for item in tweets_data or []:
        tweet = item.get("tweet", {})
        tweet_id = tweet.get("id_str") or tweet.get("id")
        if tweet_id:
            # Extract media IDs from this tweet
            media_ids = []
            for media in tweet.get("entities", {}).get("media", []):
                mid = media.get("id_str") or media.get("id")
                if mid:
                    media_ids.append(mid)
            for media in tweet.get("extended_entities", {}).get("media", []):
                mid = media.get("id_str") or media.get("id")
                if mid and mid not in media_ids:
                    media_ids.append(mid)

            index[tweet_id] = {
                "tweet_id": tweet_id,
                "text": tweet.get("full_text", ""),
                "created_at": tweet.get("created_at"),
                "favorite_count": int(tweet.get("favorite_count", 0)),
                "retweet_count": int(tweet.get("retweet_count", 0)),
                "media_ids": media_ids,
            }
    return index


def build_grok_chat_index(grok_data: List[dict]) -> Dict[str, dict]:
    """Build index: chat_id -> chat context."""
    index = {}
    for item in grok_data or []:
        chat = item.get("grokChatItem", {})
        chat_id = chat.get("chatId")
        if chat_id:
            if chat_id not in index:
                index[chat_id] = {
                    "chat_id": chat_id,
                    "messages": [],
                    "mode": chat.get("grokMode", {}).get("name", "Unknown"),
                }
            index[chat_id]["messages"].append({
                "sender": chat.get("sender", {}).get("name", "Unknown"),
                "message": chat.get("message", ""),
                "created_at": chat.get("createdAt"),
            })
    return index


# ==============================================================================
# MEDIA DISCOVERY
# ==============================================================================

def discover_media_files(
    media_dir: Path,
    source: str,
    tweet_index: Dict[str, dict] = None,
) -> List[MediaItem]:
    """Discover all media files in a directory."""
    items = []

    if not media_dir.exists():
        return items

    for f in media_dir.iterdir():
        if not f.is_file():
            continue

        ext = f.suffix.lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm'):
            continue

        # Parse filename: {tweet_id}-{media_key}.{ext}
        stem = f.stem
        parts = stem.split('-', 1)
        tweet_id = parts[0] if parts else stem

        media_type = "video" if ext in ('.mp4', '.webm') else "image"

        item = MediaItem(
            path=f,
            media_id=stem,
            media_type=media_type,
            extension=ext,
            source=source,
            tweet_id=tweet_id,
        )

        # Add tweet metadata if available
        if tweet_index and tweet_id in tweet_index:
            meta = tweet_index[tweet_id]
            item.tweet_text = meta.get("text", "")
            item.context = f"Tweet: {item.tweet_text[:200]}" if item.tweet_text else None

            # Parse timestamp
            created_at = meta.get("created_at")
            if created_at:
                try:
                    # Twitter format: "Mon Dec 29 20:03:22 +0000 2025"
                    item.timestamp = datetime.strptime(
                        created_at, "%a %b %d %H:%M:%S %z %Y"
                    )
                except ValueError:
                    pass

        items.append(item)

    return items


# ==============================================================================
# VISUAL TRAINING
# ==============================================================================

def train_single_image(
    item: MediaItem,
    visual_memory,
    seen_phashes: set,
) -> MediaItem:
    """Train visual memory on a single image."""
    try:
        # Train visual cortex
        result = visual_memory.train(
            str(item.path),
            labels=[item.source, item.media_type],
            description=item.context or f"Image from {item.source}",
        )

        if result.get("error"):
            item.error = result["error"]
            return item

        item.visual_signature_id = result.get("image_id")
        item.phash = result.get("phash")

        # Check for duplicate
        if item.phash and item.phash in seen_phashes:
            item.error = "duplicate"
            return item

        if item.phash:
            seen_phashes.add(item.phash)

        return item

    except Exception as e:
        item.error = str(e)
        return item


def extract_video_keyframes(video_path: Path, max_frames: int = 10) -> List[Path]:
    """Extract keyframes from video (1 per second or scene change)."""
    try:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # Extract 1 frame per second, up to max_frames
        frame_interval = max(1, int(fps))
        keyframe_paths = []

        # Create temp directory for keyframes
        temp_dir = Path(os.environ.get('TEMP', '/tmp')) / "grok_keyframes"
        temp_dir.mkdir(exist_ok=True)

        frame_idx = 0
        extracted = 0

        while extracted < max_frames and frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                break

            # Save keyframe
            keyframe_path = temp_dir / f"{video_path.stem}_frame{extracted:03d}.jpg"
            cv2.imwrite(str(keyframe_path), frame)
            keyframe_paths.append(keyframe_path)

            extracted += 1
            frame_idx += frame_interval

        cap.release()
        return keyframe_paths

    except ImportError:
        print("[WARNING] OpenCV not available for video keyframe extraction")
        return []
    except Exception as e:
        print(f"[WARNING] Video extraction failed: {e}")
        return []


# ==============================================================================
# HELIX CARD CREATION
# ==============================================================================

def create_helix_card(
    item: MediaItem,
    bridge,
) -> Optional[str]:
    """Create a Helix memory card for the media item."""
    try:
        from memory.helix import (
            HelixCoordinate, AffectCoordinate, SemanticCoordinate,
            TemporalCoordinate, OwnershipLevel
        )

        # Map source to semantic domain
        source_to_domain = {
            "tweets": 3,      # Social
            "grok_chat": 6,   # Technology (AI)
            "dm": 3,          # Social
            "profile": 9,     # Personal
        }

        # Extract affect from context (simple heuristic)
        affect_domain = 5  # Default: neutral
        if item.tweet_text:
            text_lower = item.tweet_text.lower()
            if any(w in text_lower for w in ['love', 'amazing', 'great', 'awesome']):
                affect_domain = 1  # Joy
            elif any(w in text_lower for w in ['sad', 'sorry', 'miss', 'lost']):
                affect_domain = 4  # Sadness
            elif any(w in text_lower for w in ['angry', 'hate', 'stupid', 'wrong']):
                affect_domain = 2  # Anger
            elif any(w in text_lower for w in ['scared', 'worried', 'afraid']):
                affect_domain = 3  # Fear

        # Calculate temporal scale from timestamp
        temporal_scale = 5  # Default: historical
        if item.timestamp:
            days_ago = (datetime.now(item.timestamp.tzinfo) - item.timestamp).days
            if days_ago < 1:
                temporal_scale = 1  # Immediate
            elif days_ago < 7:
                temporal_scale = 2  # Recent
            elif days_ago < 30:
                temporal_scale = 3  # Short-term
            elif days_ago < 365:
                temporal_scale = 4  # Medium-term

        coord = HelixCoordinate(
            affect=AffectCoordinate(
                domain=affect_domain,
                valence=5,
                intensity=5,
            ),
            semantic=SemanticCoordinate(
                domain=source_to_domain.get(item.source, 0),
                subdomain=0,
                detail=0,
            ),
            temporal=TemporalCoordinate(
                scale=temporal_scale,
                recurrence=0,
                decay=5,
            ),
        )

        # Build card content
        content = {
            "type": "visual_memory",
            "source": item.source,
            "media_type": item.media_type,
            "path": str(item.path),
            "visual_id": item.visual_signature_id,
            "phash": item.phash,
            "tweet_text": item.tweet_text[:500] if item.tweet_text else None,
            "timestamp": item.timestamp.isoformat() if item.timestamp else None,
        }

        # Store in helix-tensor bridge
        card_id, tensor_id = bridge.store(
            content=content,
            coord=coord,
            owner_mind="Akashic",
            ownership_level=OwnershipLevel.SYSTEM,
            tags=[item.source, item.media_type, "grok_archive"],
        )

        return card_id

    except ImportError:
        # Helix not available
        return None
    except Exception as e:
        print(f"[WARNING] Helix card creation failed: {e}")
        return None


# ==============================================================================
# MAIN INGESTION PIPELINE
# ==============================================================================

def run_ingestion(
    limit: int = None,
    dry_run: bool = False,
    workers: int = 4,
    skip_videos: bool = True,
) -> Dict[str, Any]:
    """
    Run the full ingestion pipeline.

    Args:
        limit: Max items to process (None = all)
        dry_run: If True, don't actually train/store
        workers: Number of concurrent workers
        skip_videos: Skip video processing (faster)

    Returns:
        Statistics dict
    """
    stats = IngestionStats()

    print("=" * 70)
    print("GROK IMAGE INGESTION PIPELINE")
    print("=" * 70)
    print(f"Source: {GROK_DATA_ROOT}")
    print(f"Limit: {limit if limit else 'ALL'}")
    print(f"Dry run: {dry_run}")
    print(f"Workers: {workers}")
    print()

    # Load metadata
    print("[1/5] Loading metadata...")
    tweets_data = parse_js_file(TWEETS_JS)
    tweet_index = build_tweet_metadata_index(tweets_data) if tweets_data else {}
    print(f"  Loaded {len(tweet_index)} tweet records")

    grok_data = parse_js_file(GROK_CHAT_JS)
    grok_index = build_grok_chat_index(grok_data) if grok_data else {}
    print(f"  Loaded {len(grok_index)} Grok chat sessions")

    # Discover media files
    print("\n[2/5] Discovering media files...")
    all_items = []

    for media_dir, source in [
        (TWEETS_MEDIA, "tweets"),
        (GROK_CHAT_MEDIA, "grok_chat"),
        (DM_MEDIA, "dm"),
        (PROFILE_MEDIA, "profile"),
        (COMMUNITY_MEDIA, "community"),
    ]:
        items = discover_media_files(media_dir, source, tweet_index)
        all_items.extend(items)
        images = sum(1 for i in items if i.media_type == "image")
        videos = sum(1 for i in items if i.media_type == "video")
        print(f"  {source}: {images} images, {videos} videos")

    stats.total_found = len(all_items)
    stats.images_found = sum(1 for i in all_items if i.media_type == "image")
    stats.videos_found = sum(1 for i in all_items if i.media_type == "video")

    print(f"\n  TOTAL: {stats.images_found} images, {stats.videos_found} videos")

    # Filter to images only if skipping videos
    if skip_videos:
        all_items = [i for i in all_items if i.media_type == "image"]
        print(f"  (Skipping videos, processing {len(all_items)} images)")

    # Apply limit
    if limit:
        all_items = all_items[:limit]
        print(f"  (Limited to first {limit} items)")

    if dry_run:
        print("\n[DRY RUN] Would process the above items")
        print(f"\nFirst 10 items:")
        for item in all_items[:10]:
            print(f"  - {item.path.name}")
            if item.tweet_text:
                print(f"    Tweet: {item.tweet_text[:80]}...")
        return stats.to_dict()

    # Initialize visual memory
    print("\n[3/5] Initializing visual memory system...")
    try:
        from P40_Sensory.cortex.visual_memory import get_visual_memory
        visual_memory = get_visual_memory()
        print(f"  Visual memory initialized ({visual_memory.index.count()} existing signatures)")
    except Exception as e:
        print(f"  [ERROR] Failed to initialize visual memory: {e}")
        return {"error": str(e), **stats.to_dict()}

    # Initialize helix-tensor bridge
    print("\n[4/5] Initializing memory bridge...")
    try:
        from memory.helix_tensor_bridge import get_helix_tensor_bridge
        bridge = get_helix_tensor_bridge()
        print(f"  Bridge status: {bridge.status()}")
    except Exception as e:
        print(f"  [WARNING] Helix bridge not available: {e}")
        bridge = None

    # Process items
    print(f"\n[5/5] Processing {len(all_items)} items...")
    seen_phashes = set()
    processed_items = []

    def process_item(item: MediaItem) -> MediaItem:
        """Process a single item."""
        # Train visual memory
        result = train_single_image(item, visual_memory, seen_phashes)

        # Create helix card if training succeeded and bridge available
        if bridge and result.visual_signature_id and not result.error:
            result.helix_card_id = create_helix_card(result, bridge)

        return result

    # Use thread pool for concurrent processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_item, item): item for item in all_items}

        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                result = future.result(timeout=30)
                processed_items.append(result)
                stats.processed += 1

                if result.error == "duplicate":
                    stats.duplicates += 1
                elif result.error:
                    stats.errors += 1
                else:
                    stats.trained += 1
                    if result.helix_card_id:
                        stats.cards_created += 1

                # Progress update
                if (i + 1) % 100 == 0:
                    elapsed = time.time() - stats.start_time
                    rate = stats.processed / elapsed
                    print(f"  Processed {stats.processed}/{len(all_items)} "
                          f"({stats.trained} trained, {stats.duplicates} dupes, {stats.errors} errors) "
                          f"[{rate:.1f}/s]")

            except Exception as e:
                stats.errors += 1
                print(f"  [ERROR] Processing failed: {e}")

    # Save state for resumption
    state = {
        "completed_at": datetime.now().isoformat(),
        "stats": stats.to_dict(),
        "processed_paths": [str(i.path) for i in processed_items if not i.error],
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

    # Final report
    print("\n" + "=" * 70)
    print("INGESTION COMPLETE")
    print("=" * 70)
    final_stats = stats.to_dict()
    for key, value in final_stats.items():
        print(f"  {key}: {value}")

    return final_stats


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Grok Image Ingestion Pipeline")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without processing")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--include-videos", action="store_true", help="Process videos too")

    args = parser.parse_args()

    result = run_ingestion(
        limit=args.limit,
        dry_run=args.dry_run,
        workers=args.workers,
        skip_videos=not args.include_videos,
    )

    print(f"\nResult: {json.dumps(result, indent=2)}")
