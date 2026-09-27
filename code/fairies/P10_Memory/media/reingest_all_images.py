# ═══════════════════════════════════════════════════════════════════════════════
# RE-INGEST ALL IMAGES - Convert existing images to visual feature cards
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script re-processes all existing images through the visual ingest pipeline
# to create proper V1/V2/V4/IT/PTR cards for each image.
#
# Expected output: ~5 cards per image = ~11,000+ visual feature cards
#
# ═══════════════════════════════════════════════════════════════════════════════

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fairies.P10_Memory.media.visual_ingest_pipeline import ingest_image_to_cards

# Paths
MEDIA_IMAGES_PATH = Path(__file__).parent.parent / "SRM_Clusters" / "media" / "images"
VISUAL_CARDS_PATH = Path(__file__).parent.parent / "SRM_Clusters" / "visual_cards"
VISUAL_INDEX_PATH = VISUAL_CARDS_PATH / "visual_cards_index.json"

# Ensure output directory exists
VISUAL_CARDS_PATH.mkdir(parents=True, exist_ok=True)


def load_existing_index():
    """Load existing visual cards index if it exists."""
    if VISUAL_INDEX_PATH.exists():
        try:
            with open(VISUAL_INDEX_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"cards": {}, "images_processed": [], "total_cards": 0, "created_at": time.time()}


def save_index(index):
    """Save the visual cards index."""
    index["updated_at"] = time.time()
    with open(VISUAL_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, default=str)


def get_all_images():
    """Get all image files from the media cluster."""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    images = []

    if MEDIA_IMAGES_PATH.exists():
        for f in MEDIA_IMAGES_PATH.iterdir():
            if f.suffix.lower() in valid_extensions:
                images.append(f)

    return sorted(images)


def reingest_all_images(batch_size: int = 50, skip_existing: bool = True):
    """
    Re-ingest all existing images through the visual pipeline.

    Args:
        batch_size: Process images in batches to show progress
        skip_existing: Skip images already in the index

    Returns:
        Statistics dict
    """
    print("=" * 70)
    print("VISUAL MEMORY RE-INGEST - Converting images to feature cards")
    print("=" * 70)

    # Load existing index
    index = load_existing_index()
    processed_set = set(index.get("images_processed", []))

    # Get all images
    images = get_all_images()
    total_images = len(images)

    print(f"\nFound {total_images} images in {MEDIA_IMAGES_PATH}")
    print(f"Already processed: {len(processed_set)}")

    if skip_existing:
        images = [img for img in images if img.name not in processed_set]
        print(f"Remaining to process: {len(images)}")

    if not images:
        print("\nNo new images to process!")
        return {"status": "complete", "processed": 0, "total_cards": index.get("total_cards", 0)}

    print(f"\nStarting re-ingest at {datetime.now().strftime('%H:%M:%S')}")
    print(f"Batch size: {batch_size}")
    print("-" * 70)

    # Statistics
    stats = {
        "processed": 0,
        "failed": 0,
        "cards_created": 0,
        "start_time": time.time(),
        "errors": [],
    }

    # Process in batches
    for batch_start in range(0, len(images), batch_size):
        batch_end = min(batch_start + batch_size, len(images))
        batch = images[batch_start:batch_end]
        batch_num = (batch_start // batch_size) + 1
        total_batches = (len(images) + batch_size - 1) // batch_size

        print(f"\n[Batch {batch_num}/{total_batches}] Processing {len(batch)} images...")

        batch_cards = 0
        for i, img_path in enumerate(batch):
            try:
                # Process image
                result = ingest_image_to_cards(str(img_path), store_file=False)

                if result.get("ok"):
                    # Store cards in index
                    image_id = result["image_id"]
                    for card in result.get("cards", []):
                        card_id = card["id"]
                        index["cards"][card_id] = {
                            "image_id": image_id,
                            "card_type": card["card_type"],
                            "source_path": str(img_path),
                            "created_at": card["ts"],
                            "siblings": card["siblings"],
                            "content_summary": {
                                k: v for k, v in card.get("content", {}).items()
                                if k in ["layer", "scene_type", "edge_density", "dominant_hue",
                                        "contour_count", "width", "height"]
                            },
                        }
                        batch_cards += 1

                    index["images_processed"].append(img_path.name)
                    stats["processed"] += 1
                else:
                    stats["failed"] += 1
                    stats["errors"].append({"path": str(img_path), "error": result.get("error")})

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"path": str(img_path), "error": str(e)})

        stats["cards_created"] += batch_cards
        index["total_cards"] = len(index["cards"])

        # Save index after each batch
        save_index(index)

        # Progress update
        elapsed = time.time() - stats["start_time"]
        images_done = stats["processed"] + stats["failed"]
        rate = images_done / elapsed if elapsed > 0 else 0
        remaining = len(images) - images_done
        eta = remaining / rate if rate > 0 else 0

        print(f"  [OK] Created {batch_cards} cards | Total: {stats['cards_created']} cards")
        print(f"  Progress: {images_done}/{len(images)} images ({100*images_done/len(images):.1f}%)")
        print(f"  Rate: {rate:.1f} img/s | ETA: {eta/60:.1f} min")

    # Final statistics
    stats["end_time"] = time.time()
    stats["duration"] = stats["end_time"] - stats["start_time"]
    stats["total_cards"] = index["total_cards"]

    print("\n" + "=" * 70)
    print("RE-INGEST COMPLETE")
    print("=" * 70)
    print(f"  Images processed: {stats['processed']}")
    print(f"  Images failed: {stats['failed']}")
    print(f"  Total cards created: {stats['cards_created']}")
    print(f"  Cards per image: {stats['cards_created'] / max(1, stats['processed']):.1f}")
    print(f"  Duration: {stats['duration']:.1f} seconds ({stats['duration']/60:.1f} min)")
    print(f"  Index saved to: {VISUAL_INDEX_PATH}")
    print("=" * 70)

    if stats["errors"]:
        print(f"\nFirst 5 errors:")
        for err in stats["errors"][:5]:
            print(f"  - {Path(err['path']).name}: {err['error'][:50]}")

    return stats


def get_reingest_status():
    """Get current status of the visual cards index."""
    index = load_existing_index()
    images = get_all_images()

    return {
        "total_images_available": len(images),
        "images_processed": len(index.get("images_processed", [])),
        "total_cards": index.get("total_cards", 0),
        "cards_by_type": _count_cards_by_type(index),
        "index_path": str(VISUAL_INDEX_PATH),
    }


def _count_cards_by_type(index):
    """Count cards by type."""
    counts = {"v1": 0, "v2": 0, "v4": 0, "it": 0, "ptr": 0}
    for card_id, card in index.get("cards", {}).items():
        card_type = card.get("card_type", "unknown")
        if card_type in counts:
            counts[card_type] += 1
    return counts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Re-ingest images to visual feature cards")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")
    parser.add_argument("--force", action="store_true", help="Reprocess all images, even if already done")
    parser.add_argument("--status", action="store_true", help="Just show current status")

    args = parser.parse_args()

    if args.status:
        status = get_reingest_status()
        print(json.dumps(status, indent=2))
    else:
        reingest_all_images(batch_size=args.batch_size, skip_existing=not args.force)
