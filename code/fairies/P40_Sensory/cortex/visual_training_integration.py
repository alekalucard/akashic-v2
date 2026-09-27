# ══════════════════════════════════════════════════════════════════════════════
# VISUAL TRAINING INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════
#
# Bridges MediaMemoryFairy (stores images) with VisualMemory (trains recognition)
#
# When an image is ingested:
#   1. MediaMemoryFairy stores the file and extracts basic metadata
#   2. VisualMemory extracts cortex features (V1/V2/V4/IT)
#   3. Both records are linked by image_id
#
# This enables fairies to:
#   - RECOGNIZE images they've seen before
#   - RECALL visual details from memory
#   - IMAGINE (internal visualization via the VR construct)
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fairies.P40_Sensory.cortex.visual_memory import get_visual_memory, train_image


def ingest_and_train(
    image_path: str,
    tags: List[str] = None,
    description: str = "",
    context: str = "",
    skip_if_exists: bool = True,
) -> Dict[str, Any]:
    """
    Ingest an image AND train the visual cortex on it.
    
    This is the unified entry point that ensures both:
    1. The image is stored in media memory (for retrieval)
    2. The visual features are extracted (for recognition)
    
    Args:
        image_path: Path to the image file
        tags: Tags for the image
        description: Human description 
        context: Additional context
        skip_if_exists: Skip if already ingested
        
    Returns:
        Dict with both ingestion and training results
    """
    tags = tags or []
    
    # Import MediaMemoryFairy functions
    try:
        from fairies.P10_Memory.media.media_memory_fairy import ingest_image_fast, MediaIndex
    except ImportError as e:
        return {"error": f"Cannot import media_memory_fairy: {e}"}
    
    # Check if already exists
    if skip_if_exists:
        index = MediaIndex()
        # Quick hash check
        import hashlib
        try:
            with open(image_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read(65536)).hexdigest()[:16]
            if file_hash in index.hash_to_id:
                existing_id = index.hash_to_id[file_hash]
                return {
                    "ok": True,
                    "duplicate": True,
                    "media_id": existing_id,
                    "message": "Already ingested",
                }
        except:
            pass
    
    # Step 1: Ingest to media memory
    media_result = ingest_image_fast(
        image_path,
        tags=tags,
        context=context,
    )
    
    if media_result.get("error"):
        return {"error": f"Media ingestion failed: {media_result['error']}"}
    
    if media_result.get("duplicate"):
        return {
            "ok": True,
            "duplicate": True,
            "media_id": media_result["id"],
        }
    
    media_id = media_result.get("id")
    
    # Step 2: Train visual memory
    vm = get_visual_memory()
    train_result = vm.train(
        image_path,
        labels=tags,
        description=description or context,
    )
    
    if train_result.get("error"):
        # Media was ingested but training failed - still partially successful
        return {
            "ok": True,
            "media_id": media_id,
            "trained": False,
            "train_error": train_result["error"],
        }
    
    return {
        "ok": True,
        "media_id": media_id,
        "visual_id": train_result.get("image_id"),
        "trained": True,
        "scene_type": train_result.get("scene_type"),
        "features": train_result.get("features"),
    }


def batch_train_existing(
    limit: int = 100,
    start_offset: int = 0,
) -> Dict[str, Any]:
    """
    Train visual memory on existing media that hasn't been trained yet.
    
    Use this to backfill visual training on already-ingested images.
    """
    from fairies.P10_Memory.media.media_memory_fairy import MediaIndex
    
    index = MediaIndex()
    vm = get_visual_memory()
    
    # Get all media records
    all_records = index.list_all()
    
    # Find untrained ones (check if visual signature exists)
    untrained = []
    for rec in all_records:
        sig = vm.recall(rec.id)
        if sig is None:
            untrained.append(rec)
    
    print(f"[BatchTrain] {len(untrained)} images need training out of {len(all_records)}")
    
    # Process batch
    to_process = untrained[start_offset:start_offset + limit]
    
    trained = 0
    errors = []
    
    for i, rec in enumerate(to_process):
        # Use stored path
        img_path = rec.stored_path
        
        result = vm.train(
            img_path,
            labels=rec.tags,
            description=rec.description or rec.context,
        )
        
        if result.get("ok"):
            trained += 1
            if trained % 50 == 0:
                print(f"[BatchTrain] Trained {trained}/{len(to_process)}...")
        else:
            errors.append({"id": rec.id, "error": result.get("error")})
    
    return {
        "ok": True,
        "total_media": len(all_records),
        "needed_training": len(untrained),
        "processed": len(to_process),
        "trained": trained,
        "errors": len(errors),
        "error_details": errors[:10] if errors else None,  # First 10 errors
    }


def clear_and_retrain_all(confirm: bool = False) -> Dict[str, Any]:
    """
    Clear all visual memory and retrain from media.
    
    WARNING: This deletes all visual signatures and retrains from scratch.
    
    Args:
        confirm: Must be True to actually execute
    """
    if not confirm:
        return {
            "error": "Must pass confirm=True to clear visual memory",
            "warning": "This will delete all trained visual signatures!",
        }
    
    from fairies.P40_Sensory.cortex.visual_memory import (
        VISUAL_MEMORY_PATH, INDEX_PATH, DESCRIPTORS_PATH
    )
    import shutil
    
    # Clear visual memory
    cleared_files = 0
    
    if INDEX_PATH.exists():
        INDEX_PATH.unlink()
        cleared_files += 1
    
    if DESCRIPTORS_PATH.exists():
        for f in DESCRIPTORS_PATH.glob("*"):
            f.unlink()
            cleared_files += 1
    
    print(f"[ClearRetrain] Cleared {cleared_files} visual memory files")
    
    # Now retrain everything
    result = batch_train_existing(limit=10000)
    result["cleared_files"] = cleared_files
    
    return result


def get_training_status() -> Dict[str, Any]:
    """Get current training status - how many images are trained vs not."""
    from fairies.P10_Memory.media.media_memory_fairy import MediaIndex
    
    index = MediaIndex()
    vm = get_visual_memory()
    
    all_records = index.list_all()
    vm_stats = vm.get_stats()
    
    # Count trained
    trained_ids = set(sig.image_id for sig in vm.index.list_all())
    
    untrained = 0
    for rec in all_records:
        # Check by stored path hash
        import hashlib
        expected_id = hashlib.md5(rec.stored_path.encode()).hexdigest()[:12]
        if expected_id not in trained_ids:
            untrained += 1
    
    return {
        "total_media": len(all_records),
        "total_trained": vm_stats["total_trained"],
        "untrained": untrained,
        "scene_types": vm_stats["scene_types"],
        "coverage": f"{(vm_stats['total_trained'] / max(1, len(all_records))) * 100:.1f}%",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Visual Training Integration")
    parser.add_argument("command", choices=["status", "train", "batch", "clear-retrain"])
    parser.add_argument("--limit", type=int, default=100, help="Batch limit")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive ops")
    
    args = parser.parse_args()
    
    if args.command == "status":
        result = get_training_status()
        print(json.dumps(result, indent=2))
    
    elif args.command == "batch":
        result = batch_train_existing(limit=args.limit)
        print(json.dumps(result, indent=2))
    
    elif args.command == "clear-retrain":
        result = clear_and_retrain_all(confirm=args.confirm)
        print(json.dumps(result, indent=2))
