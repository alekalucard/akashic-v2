#!/usr/bin/env python3
"""
Tag Failed Images as negative learning examples.
Re-processes just the Failed Images folder and tags them appropriately.
"""

import sys
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def extract_image(path: str):
    """Extract features from an image."""
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
            # NEGATIVE LEARNING TAGS
            'learning_type': 'negative',
            'source_category': 'failed_example',
            'defect_learning': True,
            'defect_notes': 'AI generation failure - may contain anatomical errors, extra fingers, visual artifacts'
        }
    except Exception as e:
        return {'error': str(e), 'source': path}


def main():
    import os

    source_dir = "D:/Failed Images"

    print("="*70)
    print("TAGGING FAILED IMAGES AS NEGATIVE LEARNING EXAMPLES")
    print("="*70)

    if not os.path.exists(source_dir):
        print(f"Source not found: {source_dir}")
        return

    # Find all images
    image_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    files = []
    for root, dirs, filenames in os.walk(source_dir):
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in image_ext:
                files.append(str(Path(root) / fname))

    print(f"Found {len(files)} images in Failed Images folder")

    # Get coordinator
    from memory.helix import get_helix_coordinator
    from memory.helix import HelixCoordinate, AffectCoordinate, SemanticCoordinate, TemporalCoordinate, OwnershipLevel
    coord = get_helix_coordinator()

    print(f"Helix coordinator has {len(coord._cards)} existing cards")

    # Process images
    created = 0
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(extract_image, f): f for f in files}

        for future in as_completed(futures):
            path = futures[future]
            try:
                feat = future.result(timeout=30)

                if feat is None or 'error' in feat:
                    print(f"  [SKIP] Failed to process: {Path(path).name}")
                    continue

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

                created += 1
                print(f"  [TAGGED] {Path(path).name} - NEGATIVE LEARNING")

            except Exception as e:
                print(f"  [ERROR] {Path(path).name}: {e}")

    # Save
    coord.save()

    print()
    print("="*70)
    print("COMPLETE")
    print("="*70)
    print(f"  Created {created} negative learning cards")
    print(f"  Total cards in helix: {len(coord._cards)}")
    print()
    print("These cards are tagged with:")
    print("  learning_type: 'negative'")
    print("  source_category: 'failed_example'")
    print("  defect_learning: True")


if __name__ == "__main__":
    main()
