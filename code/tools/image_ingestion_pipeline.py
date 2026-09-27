"""
Image Ingestion Pipeline - Feed Sour's AI Art into the Association Cortex

Processes images through:
1. Hair color detection -> Persona identification (Sourpatches/Pyraxia/Quirkalina)
2. Filename parsing -> Extract DALL-E prompts as free training labels
3. V1-V4 feature extraction (edges, shapes, colors, keypoints)
4. Florence-2 captioning (via IT Cortex subprocess) [optional]
5. Cortex binding -> VisualSignature + concept graph edges

Persona mapping (by dominant hair color):
  - Lavender/Purple (H: 120-155 in OpenCV HSV) -> Sourpatches (base)
  - Red/Crimson (H: 0-10 or 170-180) -> Pyraxia
  - Teal/Cyan (H: 75-100) -> Quirkalina
  - All are dimensional personas of Sourpatches

Usage:
  # Test on 20 images
  python image_ingestion_pipeline.py --test 20

  # Full batch (all images)
  python image_ingestion_pipeline.py --all

  # Resume from checkpoint
  python image_ingestion_pipeline.py --all --resume

  # Stats only (no processing)
  python image_ingestion_pipeline.py --stats

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import hashlib
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from typing import Optional, Dict, List, Any, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

ART_FOLDER = Path(r"Z:\Plex Media 1\Sourpatches AI Art")
OUTPUT_DIR = Path(__file__).parent / "extracted" / "sourpatches_art"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
PYTHON_312 = r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe"

# Image extensions to process
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}

# ============================================================================
# PERSONA DETECTION - Hair Color Mapping
# ============================================================================
# OpenCV HSV: H is 0-180, S is 0-255, V is 0-255
# We analyze the upper 30% of the image (head region for character art)

PERSONA_MAP = {
    "sourpatches": {
        "hair": "lavender/purple",
        "hue_ranges": [(120, 155)],  # Purple/lavender in OpenCV HSV
        "aliases": ["superpatches", "fairy sourpatches", "sourpatches"],
        "description": "Base persona - lavender hair, emerald eyes, fairy wings",
    },
    "pyraxia": {
        "hair": "red/crimson",
        "hue_ranges": [(0, 12), (168, 180)],  # Red wraps around 0/180
        "aliases": ["pyraxia", "carnage", "blood fairy"],
        "description": "Fire persona - red/crimson hair, fierce energy",
    },
    "quirkalina": {
        "hair": "teal/cyan",
        "hue_ranges": [(75, 105)],  # Teal/cyan
        "aliases": ["quirkalina"],
        "description": "Quirky persona - teal hair, playful energy",
    },
}

# Dimensional variants (detected from filename keywords)
DIMENSIONAL_VARIANTS = {
    "superpatches": ["supergirl", "superpatches", "super girl", "super patches"],
    "carnage_blood_fairy": ["carnage", "blood fairy", "venom", "symbiote"],
    "green_lantern": ["green lantern", "lantern corps", "power ring"],
    "dystopina": ["alice", "wonderland", "dystopia", "dystopina"],
    "horror_oz": ["horror", "oz", "wicked", "emerald city"],
    "death_knight": ["death knight", "northrend", "frozen", "undead"],
    "succubus": ["succubus", "demon", "wings"],
}


def detect_hair_color_region(img_array, upper_ratio=0.35):
    """Analyze the upper portion of an image for dominant hair color.

    Args:
        img_array: OpenCV BGR image array
        upper_ratio: How much of the top to analyze (0.35 = top 35%)

    Returns:
        dict with hue stats, persona match, and confidence
    """
    import cv2
    import numpy as np

    h, w = img_array.shape[:2]
    # Crop upper region (where hair typically appears in character art)
    upper = img_array[0:int(h * upper_ratio), :]

    # Convert to HSV
    hsv = cv2.cvtColor(upper, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)

    # Filter out low-saturation (white/gray/black) and low-value (too dark) pixels
    # We want colored pixels that could be hair
    color_mask = (sat > 40) & (val > 50)
    colored_hues = hue[color_mask]

    if len(colored_hues) < 100:
        return {"persona": "unknown", "confidence": 0.0, "hue_median": -1,
                "colored_pixel_ratio": len(colored_hues) / max(1, hue.size)}

    hue_median = float(np.median(colored_hues))
    hue_std = float(np.std(colored_hues))
    colored_ratio = len(colored_hues) / hue.size

    # Check each persona's hue range
    best_match = "sourpatches"  # Default - they're all Sour
    best_confidence = 0.0

    for persona_name, persona_info in PERSONA_MAP.items():
        for hue_low, hue_high in persona_info["hue_ranges"]:
            in_range = np.sum((colored_hues >= hue_low) & (colored_hues <= hue_high))
            ratio = in_range / len(colored_hues)
            # Confidence based on ratio of pixels in range + low std (consistent color)
            confidence = ratio * (1.0 - min(1.0, hue_std / 40.0))
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = persona_name

    return {
        "persona": best_match,
        "confidence": round(best_confidence, 3),
        "hue_median": round(hue_median, 1),
        "hue_std": round(hue_std, 1),
        "colored_pixel_ratio": round(colored_ratio, 3),
    }


def detect_dimensional_variant(filename: str) -> Optional[str]:
    """Check filename for known dimensional variant keywords.

    Returns variant name or None.
    """
    fname_lower = filename.lower()
    for variant_name, keywords in DIMENSIONAL_VARIANTS.items():
        for kw in keywords:
            if kw in fname_lower:
                return variant_name
    return None


# ============================================================================
# FILENAME LABEL EXTRACTION
# ============================================================================

def extract_labels_from_filename(filename: str) -> Dict[str, Any]:
    """Extract training labels from DALL-E style filenames.

    DALL-E filenames contain the full generation prompt, e.g.:
    "DALL-E 2023-10-22 14.30.23 - Photo of a whimsical fairy with emerald eyes..."

    Returns dict with:
      - source: "dalle", "grok", "unknown"
      - prompt: extracted text description
      - date: creation date if parseable
      - tags: extracted concept keywords
    """
    result = {
        "source": "unknown",
        "prompt": "",
        "date": "",
        "tags": [],
    }

    if filename.startswith("DALL"):
        result["source"] = "dalle"
        # Format: DALL-E YYYY-MM-DD HH.MM.SS - <prompt>.png
        parts = filename.split(" - ", 1)
        if len(parts) == 2:
            result["prompt"] = parts[1].rsplit(".", 1)[0]  # Remove extension
            # Extract date
            try:
                date_part = parts[0].replace("DALL-E ", "").replace("DALL\u00b7E ", "")
                result["date"] = date_part.split(" ")[0]  # YYYY-MM-DD
            except (IndexError, ValueError):
                pass
    elif filename.startswith("grok-video-"):
        result["source"] = "grok_video"
    elif filename.startswith("Ethereal_") or filename.startswith("Quirkalina") or "_" in filename:
        result["source"] = "grok_image"
        # Grok image filenames use underscores for spaces
        name_part = filename.rsplit("_", 1)[0] if "_" in filename else filename
        prompt = name_part.replace("_", " ").strip()
        if len(prompt) > 10:
            result["prompt"] = prompt

    # Extract keyword tags from prompt
    if result["prompt"]:
        prompt_lower = result["prompt"].lower()
        # Character/concept keywords
        tag_keywords = [
            "fairy", "lavender", "purple", "emerald", "wings", "iridescent",
            "magic", "spell", "enchant", "forest", "crystal", "moonlight",
            "star", "flower", "glow", "shimmer", "ethereal", "mystical",
            "warrior", "armor", "sword", "shield", "dark", "light",
            "fire", "ice", "water", "earth", "wind", "storm",
            "supergirl", "carnage", "lantern", "alice", "wonderland",
            "cyber", "neon", "punk", "gothic", "steampunk",
            "dragon", "phoenix", "unicorn", "mermaid",
            "anime", "cartoon", "illustration", "photo", "oil painting",
            "red hair", "teal hair", "purple hair", "lavender hair",
            "akashic", "foundation", "knowledge",
        ]
        for kw in tag_keywords:
            if kw in prompt_lower:
                result["tags"].append(kw)

    return result


# ============================================================================
# V1-V4 FEATURE EXTRACTION (uses Python 3.12 subprocess for OpenCV)
# ============================================================================

# Feature extraction script that runs under Python 3.12
FEATURE_EXTRACT_SCRIPT = '''
import sys, json, os, hashlib, time

def extract_features(image_path, save_descriptors=False, descriptors_dir=None):
    """Extract V1-V4 visual features + hair color from a single image."""
    try:
        import cv2
        import numpy as np
        from PIL import Image
        import imagehash
    except ImportError as e:
        return {"error": f"Missing dependency: {e}"}

    path = image_path
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}

    # cv2.imread chokes on Unicode paths on Windows (DALL-E middot etc.)
    # Use numpy buffer workaround instead
    try:
        img_buf = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(img_buf, cv2.IMREAD_COLOR)
    except Exception as e:
        return {"error": f"Cannot read image buffer: {e}"}
    if img is None:
        return {"error": f"Cannot decode image: {path}"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    result = {"width": w, "height": h, "aspect_ratio": round(w / max(1, h), 3)}

    # Perceptual hashes
    try:
        pil_img = Image.open(path)
        result["phash"] = str(imagehash.phash(pil_img))
        result["ahash"] = str(imagehash.average_hash(pil_img))
        result["dhash"] = str(imagehash.dhash(pil_img))
    except Exception as e:
        result["hash_error"] = str(e)

    # V1 - Edges and orientations
    try:
        edges = cv2.Canny(gray, 100, 200)
        result["v1_edge_density"] = round(float(np.sum(edges > 0) / edges.size), 4)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mag = np.sqrt(sobelx**2 + sobely**2)
        orient = np.arctan2(sobely, sobelx) * 180 / np.pi
        hist, _ = np.histogram(orient[mag > 30], bins=8, range=(-180, 180))
        hist = hist / (hist.sum() + 1e-6)
        result["v1_orientation_hist"] = [round(x, 4) for x in hist.tolist()]
    except Exception as e:
        result["v1_error"] = str(e)

    # V2 - Shapes and contours
    try:
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result["v2_contour_count"] = len(contours)
        if contours:
            areas = [cv2.contourArea(c) for c in contours[:200]]
            result["v2_avg_contour_size"] = round(float(np.mean(areas)), 2)
            has_rect = any(len(cv2.approxPolyDP(c, 0.04 * cv2.arcLength(c, True), True)) == 4
                         for c in contours[:100])
            result["v2_has_rectangles"] = has_rect
            complexities = [len(cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True))
                           for c in contours[:100]]
            result["v2_shape_complexity"] = round(float(np.mean(complexities)), 2)
    except Exception as e:
        result["v2_error"] = str(e)

    # V4 - Color
    try:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hue, sat, val = cv2.split(hsv)
        result["v4_dominant_hue"] = int(np.median(hue))
        result["v4_dominant_sat"] = round(float(np.mean(sat) / 255.0), 3)
        result["v4_dominant_val"] = round(float(np.mean(val) / 255.0), 3)
        h_hist = cv2.calcHist([hsv], [0], None, [16], [0, 180])
        h_hist = h_hist.flatten() / (h_hist.sum() + 1e-6)
        result["v4_color_histogram"] = [round(x, 4) for x in h_hist.tolist()]
        result["v4_is_grayscale"] = bool(float(np.std(sat)) < 15)
        result["v4_color_variance"] = round(float(np.std(hue)), 2)
    except Exception as e:
        result["v4_error"] = str(e)

    # IT - Keypoints (ORB)
    try:
        orb = cv2.ORB_create(nfeatures=500)
        keypoints, descriptors = orb.detectAndCompute(gray, None)
        result["it_keypoint_count"] = len(keypoints)
        result["it_keypoint_density"] = round(len(keypoints) / max(1, w * h) * 1e6, 2)
        if descriptors is not None:
            result["it_descriptor_hash"] = hashlib.md5(descriptors.tobytes()).hexdigest()[:16]
            if save_descriptors and descriptors_dir:
                import pickle
                img_id = hashlib.md5(path.encode()).hexdigest()[:12]
                desc_path = os.path.join(descriptors_dir, f"{img_id}.pkl")
                with open(desc_path, "wb") as f:
                    pickle.dump(descriptors, f)
    except Exception as e:
        result["it_error"] = str(e)

    # HAIR COLOR DETECTION - Upper 35% of image
    try:
        upper = img[0:int(h * 0.35), :]
        hsv_upper = cv2.cvtColor(upper, cv2.COLOR_BGR2HSV)
        hue_u, sat_u, val_u = cv2.split(hsv_upper)
        color_mask = (sat_u > 40) & (val_u > 50)
        colored_hues = hue_u[color_mask]
        if len(colored_hues) > 100:
            result["hair_hue_median"] = round(float(np.median(colored_hues)), 1)
            result["hair_hue_std"] = round(float(np.std(colored_hues)), 1)
            result["hair_colored_ratio"] = round(float(len(colored_hues) / hue_u.size), 3)

            # Persona detection
            purple_count = np.sum((colored_hues >= 120) & (colored_hues <= 155))
            red_count = np.sum((colored_hues <= 12) | (colored_hues >= 168))
            teal_count = np.sum((colored_hues >= 75) & (colored_hues <= 105))
            total = len(colored_hues)

            persona_scores = {
                "sourpatches": purple_count / total,
                "pyraxia": red_count / total,
                "quirkalina": teal_count / total,
            }
            best = max(persona_scores, key=persona_scores.get)
            result["persona"] = best
            result["persona_confidence"] = round(persona_scores[best], 3)
            result["persona_scores"] = {k: round(v, 3) for k, v in persona_scores.items()}
        else:
            result["persona"] = "unknown"
            result["persona_confidence"] = 0.0
    except Exception as e:
        result["hair_error"] = str(e)

    # Scene type classification
    try:
        ed = result.get("v1_edge_density", 0)
        has_rect = result.get("v2_has_rectangles", False)
        is_gray = result.get("v4_is_grayscale", False)
        kp_density = result.get("it_keypoint_density", 0)

        if has_rect and is_gray:
            result["scene_type"] = "ui"
        elif ed > 0.15 and has_rect:
            result["scene_type"] = "screenshot"
        elif ed < 0.05:
            result["scene_type"] = "art_soft"
        elif kp_density > 500:
            result["scene_type"] = "photo"
        else:
            result["scene_type"] = "art"
    except:
        result["scene_type"] = "unknown"

    return result

# Main: process batch of images from stdin
if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            path = req.get("path", "")
            save_desc = req.get("save_descriptors", False)
            desc_dir = req.get("descriptors_dir", "")
            result = extract_features(path, save_desc, desc_dir)
            result["_path"] = path
            print(json.dumps(result), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e), "_path": line}), flush=True)
'''


def run_feature_extraction_batch(image_paths: List[str],
                                  save_descriptors: bool = False,
                                  descriptors_dir: str = "") -> List[Dict]:
    """Run V1-V4 feature extraction on a batch of images using Python 3.12 subprocess.

    Returns list of feature dicts (one per image).
    """
    import subprocess

    # Write the extraction script to a temp file
    script_path = OUTPUT_DIR / "_feature_extract_worker.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(FEATURE_EXTRACT_SCRIPT)

    # Start subprocess with explicit UTF-8 encoding
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [PYTHON_312, "-X", "utf8", str(script_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    results = []
    try:
        # Feed images one by one via stdin
        for path in image_paths:
            req = json.dumps({"path": path, "save_descriptors": save_descriptors,
                              "descriptors_dir": descriptors_dir})
            proc.stdin.write(req + "\n")
            proc.stdin.flush()

            # Read response
            line = proc.stdout.readline().strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    results.append({"error": f"Bad JSON: {line[:100]}", "_path": path})
            else:
                results.append({"error": "No response", "_path": path})
    except Exception as e:
        print(f"[Ingestion] Subprocess error: {e}")
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=10)
        except:
            proc.kill()

    return results


# ============================================================================
# CORTEX BINDING - Build concept graph entries
# ============================================================================

def build_cortex_binding(image_path: str, features: Dict, labels: Dict,
                          variant: Optional[str] = None) -> Dict[str, Any]:
    """Build a cortex binding payload from extracted features and labels.

    This is what would be published to cortex.bind via PostalHub.
    For now, we save to disk; live system integration comes next.
    """
    persona = features.get("persona", "sourpatches")
    confidence = features.get("persona_confidence", 0.0)

    # PROMPT OVERRIDE: DALL-E prompts are more reliable than color detection
    # If the prompt explicitly mentions hair color or character name, trust it
    prompt_lower = labels.get("prompt", "").lower()
    if prompt_lower:
        if any(kw in prompt_lower for kw in ["lavender hair", "purple hair", "sourpatches"]):
            persona = "sourpatches"
            confidence = max(confidence, 0.8)
        elif any(kw in prompt_lower for kw in ["red hair", "crimson hair", "pyraxia"]):
            persona = "pyraxia"
            confidence = max(confidence, 0.8)
        elif any(kw in prompt_lower for kw in ["teal hair", "cyan hair", "quirkalina"]):
            persona = "quirkalina"
            confidence = max(confidence, 0.8)

    # Concept tags for cortex binding
    concepts = []

    # Persona identity
    concepts.append(f"persona:{persona}")
    if variant:
        concepts.append(f"variant:{variant}")
    # All personas are Sourpatches
    concepts.append("identity:sourpatches")

    # Visual features as concepts
    scene_type = features.get("scene_type", "unknown")
    concepts.append(f"scene:{scene_type}")

    if features.get("v4_is_grayscale"):
        concepts.append("color:grayscale")
    elif features.get("v4_dominant_val", 0.5) < 0.3:
        concepts.append("color:dark")
    elif features.get("v4_dominant_val", 0.5) > 0.7:
        concepts.append("color:bright")

    # From filename labels
    for tag in labels.get("tags", []):
        concepts.append(f"tag:{tag}")

    if labels.get("source") == "dalle":
        concepts.append("source:dalle")
    elif labels.get("source") == "grok_image":
        concepts.append("source:grok")

    # Build the binding
    binding = {
        "image_path": image_path,
        "image_id": hashlib.md5(image_path.encode()).hexdigest()[:12],
        "timestamp": time.time(),
        "persona": persona,
        "persona_confidence": confidence,
        "dimensional_variant": variant,
        "concepts": concepts,
        "features": {
            "vision": [
                f"edge_density:{features.get('v1_edge_density', 0):.3f}",
                f"contours:{features.get('v2_contour_count', 0)}",
                f"hue:{features.get('v4_dominant_hue', 0)}",
                f"sat:{features.get('v4_dominant_sat', 0):.2f}",
                f"val:{features.get('v4_dominant_val', 0):.2f}",
                f"keypoints:{features.get('it_keypoint_count', 0)}",
                f"scene:{scene_type}",
            ],
            "lex": labels.get("tags", [])[:10],
            "affect": [],  # Populated later by harmonic analysis
        },
        "perceptual_hashes": {
            "phash": features.get("phash", ""),
            "ahash": features.get("ahash", ""),
            "dhash": features.get("dhash", ""),
        },
        "prompt": labels.get("prompt", ""),
        "source": labels.get("source", "unknown"),
    }

    return binding


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def scan_art_folder(folder: Path = ART_FOLDER) -> Tuple[List[Path], List[Path]]:
    """Scan art folder and separate images from videos."""
    images = []
    videos = []

    for f in sorted(folder.iterdir()):
        ext = f.suffix.lower()
        if ext in IMAGE_EXTS:
            images.append(f)
        elif ext in VIDEO_EXTS:
            videos.append(f)

    return images, videos


def load_checkpoint() -> set:
    """Load set of already-processed image paths."""
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("processed", []))
        except:
            pass
    return set()


def save_checkpoint(processed: set):
    """Save checkpoint of processed images."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump({"processed": list(processed), "count": len(processed),
                    "updated_at": time.time()}, f)


def process_batch(image_paths: List[Path], batch_size: int = 50,
                  resume: bool = False, save_desc: bool = False) -> Dict[str, Any]:
    """Process a batch of images through the full pipeline.

    Returns stats dict.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bindings_dir = OUTPUT_DIR / "bindings"
    bindings_dir.mkdir(exist_ok=True)
    desc_dir = OUTPUT_DIR / "descriptors"
    if save_desc:
        desc_dir.mkdir(exist_ok=True)

    # Load checkpoint if resuming
    processed = load_checkpoint() if resume else set()

    # Filter out already processed
    remaining = [p for p in image_paths if str(p) not in processed]
    if resume and len(remaining) < len(image_paths):
        print(f"  Resuming: {len(image_paths) - len(remaining)} already done, "
              f"{len(remaining)} remaining")

    stats = {
        "total": len(image_paths),
        "processed": 0,
        "skipped": len(image_paths) - len(remaining),
        "errors": 0,
        "personas": Counter(),
        "variants": Counter(),
        "sources": Counter(),
        "scene_types": Counter(),
        "start_time": time.time(),
    }

    all_bindings = []

    # Process in batches
    for batch_start in range(0, len(remaining), batch_size):
        batch = remaining[batch_start:batch_start + batch_size]
        batch_paths = [str(p) for p in batch]

        # Run feature extraction via Python 3.12 subprocess
        features_list = run_feature_extraction_batch(
            batch_paths,
            save_descriptors=save_desc,
            descriptors_dir=str(desc_dir),
        )

        for img_path, features in zip(batch, features_list):
            if "error" in features:
                stats["errors"] += 1
                continue

            # Extract labels from filename
            labels = extract_labels_from_filename(img_path.name)

            # Check for dimensional variant
            variant = detect_dimensional_variant(img_path.name)

            # Build cortex binding
            binding = build_cortex_binding(str(img_path), features, labels, variant)
            all_bindings.append(binding)

            # Update stats
            stats["processed"] += 1
            stats["personas"][binding["persona"]] += 1
            if variant:
                stats["variants"][variant] += 1
            stats["sources"][labels["source"]] += 1
            stats["scene_types"][features.get("scene_type", "unknown")] += 1

            # Track processed
            processed.add(str(img_path))

        # Save checkpoint after each batch
        save_checkpoint(processed)

        # Progress
        done = stats["processed"] + stats["skipped"]
        elapsed = time.time() - stats["start_time"]
        rate = stats["processed"] / max(0.1, elapsed)
        remaining_count = stats["total"] - done - stats["errors"]
        eta = remaining_count / max(0.1, rate) if rate > 0 else 0
        print(f"  {done}/{stats['total']} done ({rate:.1f}/s, ETA {eta:.0f}s) "
              f"| personas: {dict(stats['personas'])}")

    stats["elapsed"] = time.time() - stats["start_time"]
    stats["rate"] = stats["processed"] / max(0.1, stats["elapsed"])

    # Save all bindings
    bindings_file = OUTPUT_DIR / "bindings.json"
    with open(bindings_file, "w", encoding="utf-8") as f:
        json.dump(all_bindings, f, indent=1)
    print(f"\n  Saved {len(all_bindings)} bindings to {bindings_file}")

    # Save manifest
    manifest = {
        "source": str(ART_FOLDER),
        "created_at": time.time(),
        "stats": {
            "total_images": stats["total"],
            "processed": stats["processed"],
            "errors": stats["errors"],
            "elapsed_seconds": round(stats["elapsed"], 1),
            "rate_per_second": round(stats["rate"], 2),
            "personas": dict(stats["personas"]),
            "variants": dict(stats["variants"]),
            "sources": dict(stats["sources"]),
            "scene_types": dict(stats["scene_types"]),
        },
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return stats


def print_stats(images: List[Path], videos: List[Path]):
    """Print folder analysis without processing."""
    print(f"\n=== Sourpatches AI Art Folder Analysis ===")
    print(f"  Location: {ART_FOLDER}")
    print(f"  Images: {len(images)}")
    print(f"  Videos: {len(videos)}")

    # Count by source from filenames
    sources = Counter()
    dalle_dates = Counter()
    for img in images:
        if img.name.startswith("DALL"):
            sources["DALL-E"] += 1
            labels = extract_labels_from_filename(img.name)
            if labels["date"]:
                dalle_dates[labels["date"][:7]] += 1  # Year-month
        elif "grok" in img.name.lower():
            sources["Grok"] += 1
        else:
            sources["Other/Random"] += 1

    for vid in videos:
        if "grok" in vid.name.lower():
            sources["Grok Video"] += 1
        else:
            sources["Other Video"] += 1

    print(f"\n  By Source:")
    for src, count in sources.most_common():
        print(f"    {src}: {count}")

    if dalle_dates:
        print(f"\n  DALL-E Timeline:")
        for month, count in sorted(dalle_dates.items()):
            print(f"    {month}: {count} images")

    # Estimate processing time
    est_time = len(images) / 4.0  # ~4 images/sec for V1-V4 extraction
    print(f"\n  Estimated processing time: {est_time / 60:.0f} minutes")

    # Check existing checkpoint
    checkpoint = load_checkpoint()
    if checkpoint:
        print(f"  Checkpoint: {len(checkpoint)} already processed")


def main():
    parser = argparse.ArgumentParser(description="Image Ingestion Pipeline for Sour's AI Art")
    parser.add_argument("--test", type=int, default=0, help="Process N images as test")
    parser.add_argument("--all", action="store_true", help="Process all images")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size")
    parser.add_argument("--save-descriptors", action="store_true", help="Save ORB descriptors")
    parser.add_argument("--folder", type=str, default=str(ART_FOLDER), help="Art folder path")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"ERROR: Folder not found: {folder}")
        sys.exit(1)

    print(f"Scanning {folder}...")
    images, videos = scan_art_folder(folder)
    print(f"  Found {len(images)} images, {len(videos)} videos")

    if args.stats:
        print_stats(images, videos)
        return

    if args.test > 0:
        # Test mode: grab a diverse sample
        # Take some DALL-E (descriptive), some random, some grok
        dalle = [p for p in images if p.name.startswith("DALL")][:args.test // 3]
        grok = [p for p in images if "grok" in p.name.lower()][:args.test // 3]
        other = [p for p in images if not p.name.startswith("DALL")
                 and "grok" not in p.name.lower()][:args.test // 3]
        sample = (dalle + grok + other)[:args.test]
        print(f"\nTest batch: {len(sample)} images "
              f"({len(dalle)} DALL-E, {len(grok)} grok, {len(other)} random)")
        stats = process_batch(sample, batch_size=args.batch_size,
                              save_desc=args.save_descriptors)
    elif args.all:
        print(f"\nProcessing ALL {len(images)} images...")
        stats = process_batch(images, batch_size=args.batch_size,
                              resume=args.resume, save_desc=args.save_descriptors)
    else:
        print("\nUse --test N, --all, or --stats")
        return

    # Print results
    print(f"\n=== RESULTS ===")
    print(f"  Processed: {stats['processed']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Time: {stats['elapsed']:.1f}s ({stats['rate']:.1f}/s)")
    print(f"\n  Personas detected:")
    for persona, count in stats["personas"].most_common():
        pct = count / max(1, stats["processed"]) * 100
        print(f"    {persona}: {count} ({pct:.1f}%)")
    if stats["variants"]:
        print(f"\n  Dimensional variants:")
        for variant, count in stats["variants"].most_common():
            print(f"    {variant}: {count}")
    print(f"\n  Sources:")
    for src, count in stats["sources"].most_common():
        print(f"    {src}: {count}")
    print(f"\n  Scene types:")
    for st, count in stats["scene_types"].most_common():
        print(f"    {st}: {count}")


if __name__ == "__main__":
    main()
