# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL INGEST PIPELINE - Train Visual Cortex + Create SRM Cards
# ═══════════════════════════════════════════════════════════════════════════════
#
# Philosophy: "See by remembering" - Human vision works by pattern-matching
# against stored memories. This pipeline:
#
# 1. Processes images through VisualMemory (V1/V2/V4/IT feature extraction)
# 2. Creates separate helix cards for each visual layer
# 3. Links cards as siblings for complete recall
# 4. Routes through SRM for consciousness integration
#
# Card structure per image:
#   - V1 Card: Edges, orientations (primary visual cortex)
#   - V2 Card: Shapes, contours, text regions (secondary visual cortex)
#   - V4 Card: Colors, brightness, hues (color processing)
#   - IT Card: Objects, scene type, keypoints (object recognition)
#   - PTR Card: File location + metadata (pointer to actual image)
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL CARD TYPES - Each layer of visual processing becomes a card
# ═══════════════════════════════════════════════════════════════════════════════

VISUAL_CARD_TYPES = {
    "v1": "visual.primary",      # Edges, orientations
    "v2": "visual.secondary",    # Shapes, contours
    "v4": "visual.color",        # Colors, brightness
    "it": "visual.object",       # Objects, scene type
    "ptr": "visual.pointer",     # File reference
}

# Semantic domains for visual cards (affect-based addressing)
VISUAL_SEMANTIC_DOMAINS = {
    "v1": 10,   # Low-level features
    "v2": 20,   # Mid-level shapes
    "v4": 30,   # Color/emotion (colors have emotional weight)
    "it": 40,   # High-level recognition
    "ptr": 5,   # Pointer (metadata)
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELIX CARD CREATION
# ═══════════════════════════════════════════════════════════════════════════════

def create_visual_helix_card(
    card_type: str,
    content: Dict[str, Any],
    image_id: str,
    source_path: str,
    sibling_ids: List[str] = None,
    tags: List[str] = None,
    affect: float = 0.5,
) -> Dict[str, Any]:
    """
    Create a helix card for a visual feature layer.

    Each card has:
    - L strand: Positive affect address (what we see)
    - R strand: Negative affect address (what it's NOT)
    - C strand: Emotional/energy context
    """
    ts = time.time()
    card_id = f"vis_{card_type}_{hashlib.md5(f'{image_id}{card_type}{ts}'.encode()).hexdigest()[:10]}"

    sem_domain = VISUAL_SEMANTIC_DOMAINS.get(card_type, 20)
    media_type = VISUAL_CARD_TYPES.get(card_type, "visual.unknown")

    # W-coordinates (who/what/when/where/why/how)
    w_coords = {
        "who": "VisualCortex",
        "what": f"{card_type.upper()} features of image {image_id[:8]}",
        "when": ts,
        "where": source_path,
        "why": f"visual_training_{card_type}",
        "how": "visual_ingest_pipeline",
    }

    # Helix structure
    helix = {
        "L": {
            "addr": {"affect": affect, "sem_domain": sem_domain, "depth": 0},
            "concept": f"visual_{card_type}",
            "w": w_coords,
        },
        "R": {
            "addr": {"affect": -affect, "sem_domain": sem_domain, "depth": 0},
            "concept": f"visual_{card_type}_inverse",
            "w": w_coords,
        },
        "C": {
            "affect": "curious" if card_type == "it" else "observant",
            "energy": affect,
            "coherence": 0.8,
        },
    }

    return {
        "id": card_id,
        "ts": ts,
        "helix": helix,
        "content": content,
        "ptr": source_path,
        "image_id": image_id,
        "card_type": card_type,
        "media_type": media_type,
        "siblings": sibling_ids or [],
        "tags": tags or ["visual", "trained", f"layer_{card_type}"],
        "ownership": "VISUAL_CORTEX",
    }


def create_v1_card(features: Dict, image_id: str, source_path: str, siblings: List[str]) -> Dict:
    """Create V1 (Primary Visual Cortex) card - edges and orientations."""
    content = {
        "layer": "V1",
        "description": "Primary visual cortex - edges and orientations",
        "edge_density": features.get("edge_density", 0.0),
        "edge_orientation_hist": features.get("edge_orientation_hist", []),
        "horizontal_edges": features.get("horizontal_edges", 0.0),
        "vertical_edges": features.get("vertical_edges", 0.0),
        "diagonal_edges": features.get("diagonal_edges", 0.0),
    }
    # Higher edge density = more visual complexity = higher affect
    affect = min(0.9, features.get("edge_density", 0.5) + 0.3)
    return create_visual_helix_card("v1", content, image_id, source_path, siblings,
                                     tags=["visual", "v1", "edges", "orientation"], affect=affect)


def create_v2_card(features: Dict, image_id: str, source_path: str, siblings: List[str]) -> Dict:
    """Create V2 (Secondary Visual Cortex) card - shapes and contours."""
    content = {
        "layer": "V2",
        "description": "Secondary visual cortex - shapes and contours",
        "contour_count": features.get("contour_count", 0),
        "avg_contour_size": features.get("avg_contour_size", 0.0),
        "shape_complexity": features.get("shape_complexity", 0.0),
        "has_rectangles": features.get("has_rectangles", False),
        "has_circles": features.get("has_circles", False),
        "has_text_regions": features.get("has_text_regions", False),
    }
    # More contours = more interesting scene
    affect = min(0.9, 0.3 + (features.get("contour_count", 0) / 100))
    return create_visual_helix_card("v2", content, image_id, source_path, siblings,
                                     tags=["visual", "v2", "shapes", "contours"], affect=affect)


def create_v4_card(features: Dict, image_id: str, source_path: str, siblings: List[str]) -> Dict:
    """Create V4 (Color Processing) card - colors and brightness."""
    content = {
        "layer": "V4",
        "description": "Color processing cortex - hues, saturation, brightness",
        "dominant_hue": features.get("dominant_hue", 0),
        "dominant_saturation": features.get("dominant_saturation", 0.0),
        "dominant_value": features.get("dominant_value", 0.0),
        "color_histogram": features.get("color_histogram", []),
        "is_grayscale": features.get("is_grayscale", False),
        "is_dark": features.get("is_dark", False),
        "is_bright": features.get("is_bright", False),
        "color_variance": features.get("color_variance", 0.0),
    }
    # Colors have emotional weight - saturated colors = higher affect
    affect = 0.4 + (features.get("dominant_saturation", 0.5) * 0.5)
    return create_visual_helix_card("v4", content, image_id, source_path, siblings,
                                     tags=["visual", "v4", "color", "brightness"], affect=affect)


def create_it_card(features: Dict, image_id: str, source_path: str, siblings: List[str]) -> Dict:
    """Create IT (Inferotemporal) card - object recognition and scene type."""
    content = {
        "layer": "IT",
        "description": "Inferotemporal cortex - object recognition and scene classification",
        "keypoint_count": features.get("keypoint_count", 0),
        "keypoint_density": features.get("keypoint_density", 0.0),
        "descriptor_hash": features.get("descriptor_hash", ""),
        "scene_type": features.get("scene_type", "unknown"),
    }
    # Object recognition is high-level - always important
    affect = 0.7
    return create_visual_helix_card("it", content, image_id, source_path, siblings,
                                     tags=["visual", "it", "objects", "scene",
                                           features.get("scene_type", "unknown")], affect=affect)


def create_ptr_card(image_id: str, source_path: str, stored_path: str,
                    width: int, height: int, phash: str, labels: List[str],
                    siblings: List[str]) -> Dict:
    """Create pointer card - reference to actual image file + metadata."""
    content = {
        "layer": "PTR",
        "description": "Pointer to stored image with metadata",
        "source_path": source_path,
        "stored_path": stored_path,
        "width": width,
        "height": height,
        "aspect_ratio": width / height if height > 0 else 1.0,
        "phash": phash,
        "labels": labels,
    }
    return create_visual_helix_card("ptr", content, image_id, source_path, siblings,
                                     tags=["visual", "ptr", "metadata"] + labels, affect=0.5)


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED VISUAL INGEST
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_features_pil_fallback(image_path: str) -> Dict[str, Any]:
    """
    PIL-only fallback for feature extraction when OpenCV isn't available.

    Extracts basic V1/V2/V4/IT features using only PIL.
    """
    from PIL import Image, ImageFilter, ImageStat
    from collections import Counter
    import hashlib

    path = Path(image_path)
    image_id = hashlib.md5(str(path.absolute()).encode()).hexdigest()[:12]

    try:
        img = Image.open(path)
        width, height = img.size

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # ═══ V1 Features (edges via PIL edge filter) ═══
        edges = img.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges.convert('L'))
        edge_density = edge_stat.mean[0] / 255.0  # Normalized edge intensity

        # Approximate edge orientations (simplified)
        v1_features = {
            "edge_density": edge_density,
            "edge_orientation_hist": [0.125] * 8,  # Uniform fallback
            "horizontal_edges": 0.25,
            "vertical_edges": 0.25,
            "diagonal_edges": 0.5,
        }

        # ═══ V2 Features (shapes/contours approximated) ═══
        # Use contrast as proxy for contour count
        stat = ImageStat.Stat(img.convert('L'))
        contrast = stat.stddev[0] / 128.0  # 0-2 scale

        v2_features = {
            "contour_count": int(contrast * 50),  # Estimate
            "avg_contour_size": width * height / 100,
            "shape_complexity": contrast,
            "has_rectangles": True,  # Assume screenshots have rectangles
            "has_circles": False,
            "has_text_regions": edge_density > 0.1,  # Text creates edges
        }

        # ═══ V4 Features (colors via PIL) ═══
        # Resize for speed
        small = img.resize((100, 100), Image.Resampling.LANCZOS)
        pixels = list(small.getdata())

        # Get dominant colors
        r_vals = [p[0] for p in pixels]
        g_vals = [p[1] for p in pixels]
        b_vals = [p[2] for p in pixels]

        # Convert to HSV-like
        avg_r, avg_g, avg_b = sum(r_vals)/len(r_vals), sum(g_vals)/len(g_vals), sum(b_vals)/len(b_vals)
        max_c = max(avg_r, avg_g, avg_b)
        min_c = min(avg_r, avg_g, avg_b)

        # Approximate hue (0-180 range like OpenCV)
        if max_c == min_c:
            hue = 0
        elif max_c == avg_r:
            hue = 30 * ((avg_g - avg_b) / (max_c - min_c + 1e-6)) % 180
        elif max_c == avg_g:
            hue = 30 * (2 + (avg_b - avg_r) / (max_c - min_c + 1e-6)) % 180
        else:
            hue = 30 * (4 + (avg_r - avg_g) / (max_c - min_c + 1e-6)) % 180

        saturation = (max_c - min_c) / (max_c + 1e-6)
        value = max_c / 255.0

        # Check if grayscale
        is_grayscale = all(abs(p[0] - p[1]) < 20 and abs(p[1] - p[2]) < 20 for p in pixels[:100])

        v4_features = {
            "dominant_hue": int(hue),
            "dominant_saturation": saturation,
            "dominant_value": value,
            "color_histogram": [0.0625] * 16,  # Uniform fallback
            "is_grayscale": is_grayscale,
            "is_dark": value < 0.3,
            "is_bright": value > 0.7,
            "color_variance": stat.stddev[0] if len(stat.stddev) > 0 else 0,
        }

        # ═══ IT Features (scene type detection) ═══
        # Simple heuristics for scene type
        if is_grayscale and edge_density > 0.15:
            scene_type = "diagram"
        elif edge_density > 0.2 and v2_features["has_text_regions"]:
            scene_type = "screenshot"
        elif saturation < 0.2:
            scene_type = "document"
        else:
            scene_type = "photo"

        it_features = {
            "keypoint_count": int(edge_density * 500),  # Estimate
            "keypoint_density": edge_density,
            "descriptor_hash": "",
            "scene_type": scene_type,
        }

        # ═══ Perceptual hash (if imagehash available) ═══
        phash = ""
        try:
            import imagehash
            phash = str(imagehash.phash(img))
        except ImportError:
            phash = hashlib.md5(img.tobytes()[:10000]).hexdigest()[:16]

        return {
            "ok": True,
            "image_id": image_id,
            "source_path": str(path),
            "width": width,
            "height": height,
            "phash": phash,
            "v1": v1_features,
            "v2": v2_features,
            "v4": v4_features,
            "it": it_features,
        }

    except Exception as e:
        return {"error": str(e)}


def ingest_image_to_cards(
    image_path: str,
    labels: List[str] = None,
    description: str = "",
    store_file: bool = True,
) -> Dict[str, Any]:
    """
    Unified visual ingest pipeline.

    1. Extract features via VisualMemory.train() (or PIL fallback)
    2. Create separate cards for each visual layer
    3. Link cards as siblings
    4. Return all cards for SRM ingestion

    Args:
        image_path: Path to image file
        labels: Human-provided labels for training
        description: Optional description
        store_file: Whether to copy file to storage

    Returns:
        Dict with cards array and metadata
    """
    labels = labels or []
    img_path = Path(image_path)

    if not img_path.exists():
        return {"error": f"Image not found: {image_path}"}

    # ═══ STEP 1: Train visual memory (extract hierarchical features) ═══
    signature = None
    features_dict = None

    try:
        from fairies.P40_Sensory.cortex.visual_memory import get_visual_memory, extract_visual_features

        visual_mem = get_visual_memory()

        # Extract all visual features
        signature = extract_visual_features(str(img_path))
        if signature is None:
            # cv2 not available, use PIL fallback (silent)
            features_dict = _extract_features_pil_fallback(str(img_path))
            if features_dict.get("error"):
                return {"error": f"PIL fallback failed: {features_dict['error']}"}
            image_id = features_dict["image_id"]
        else:
            # Train the visual memory (stores signature)
            train_result = visual_mem.train(str(img_path), labels=labels, description=description)
            if train_result.get("error"):
                return {"error": f"Training failed: {train_result['error']}"}
            image_id = signature.image_id

    except ImportError as e:
        # Full fallback: Use PIL-only extraction (silent)
        features_dict = _extract_features_pil_fallback(str(img_path))
        if features_dict.get("error"):
            return {"error": f"PIL fallback failed: {features_dict['error']}"}
        image_id = features_dict["image_id"]

    # ═══ STEP 2: Store file if requested ═══
    stored_path = str(img_path)
    if store_file:
        try:
            from fairies.P10_Memory.media.media_memory_fairy import IMAGES_PATH
            import shutil

            IMAGES_PATH.mkdir(parents=True, exist_ok=True)
            ext = img_path.suffix.lower()
            stored_filename = f"{image_id}{ext}"
            stored_path = str(IMAGES_PATH / stored_filename)
            shutil.copy2(image_path, stored_path)
        except Exception as e:
            print(f"[VisualIngest] Could not store file: {e}")
            stored_path = str(img_path)

    # ═══ STEP 3: Create cards for each visual layer ═══
    cards = []
    sibling_ids = []  # We'll fill this after creating all cards

    if signature:
        # Extract feature dicts from VisualSignature object
        v1_features = asdict(signature.v1) if hasattr(signature.v1, '__dict__') else {}
        v2_features = asdict(signature.v2) if hasattr(signature.v2, '__dict__') else {}
        v4_features = asdict(signature.v4) if hasattr(signature.v4, '__dict__') else {}
        it_features = asdict(signature.it) if hasattr(signature.it, '__dict__') else {}
        width, height = signature.width, signature.height
        phash = signature.phash

    elif features_dict:
        # Use PIL fallback features
        v1_features = features_dict.get("v1", {})
        v2_features = features_dict.get("v2", {})
        v4_features = features_dict.get("v4", {})
        it_features = features_dict.get("it", {})
        width = features_dict.get("width", 0)
        height = features_dict.get("height", 0)
        phash = features_dict.get("phash", "")
    else:
        # No features available - minimal card only
        ptr_card = create_ptr_card(
            image_id, str(img_path), stored_path,
            0, 0, "", labels, []
        )
        return {
            "ok": True,
            "image_id": image_id,
            "card_count": 1,
            "cards": [ptr_card],
            "sibling_ids": [ptr_card["id"]],
            "source_path": str(img_path),
            "stored_path": stored_path,
            "labels": labels,
            "layers_extracted": ["ptr"],
        }

    # Create cards for all layers (siblings list empty for now)
    v1_card = create_v1_card(v1_features, image_id, str(img_path), [])
    v2_card = create_v2_card(v2_features, image_id, str(img_path), [])
    v4_card = create_v4_card(v4_features, image_id, str(img_path), [])
    it_card = create_it_card(it_features, image_id, str(img_path), [])
    ptr_card = create_ptr_card(
        image_id, str(img_path), stored_path,
        width, height, phash, labels, []
    )

    cards = [v1_card, v2_card, v4_card, it_card, ptr_card]
    layers = ["v1", "v2", "v4", "it", "ptr"]

    # ═══ STEP 4: Link as siblings ═══
    sibling_ids = [c["id"] for c in cards]
    for card in cards:
        card["siblings"] = [s for s in sibling_ids if s != card["id"]]

    return {
        "ok": True,
        "image_id": image_id,
        "card_count": len(cards),
        "cards": cards,
        "sibling_ids": sibling_ids,
        "source_path": str(img_path),
        "stored_path": stored_path,
        "labels": labels,
        "layers_extracted": layers,
    }


def ingest_and_route_to_srm(
    image_path: str,
    labels: List[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """
    Full pipeline: Extract features -> Create cards -> Route to SRM -> Emit FF77.

    This is the main entry point for visual ingestion.
    Pipeline: Visual -> Cards -> SRM -> FF77 -> Chemistry -> Embodiment
    """
    # Step 1: Create cards
    result = ingest_image_to_cards(image_path, labels, description)
    if result.get("error"):
        return result

    # Step 1.5: Emit FF77 frequency vector (visual -> affect -> chemistry)
    try:
        from fairies.P30_Cognition.affect.frequency_field_77 import (
            emit_visual_frequency, emit_visual_srm
        )

        # Find V1/V2/V4/IT features from cards
        v1_features, v2_features, v4_features, it_features = {}, {}, {}, {}
        for card in result.get("cards", []):
            content = card.get("content", {})
            layer = content.get("layer", "")
            if layer == "V1":
                v1_features = {
                    "edge_density": content.get("edge_density", 0.0),
                    "orientations": {},  # Simplified
                }
            elif layer == "V2":
                v2_features = {
                    "contour_count": content.get("contour_count", 0),
                    "corner_count": 0,
                    "contrast": content.get("shape_complexity", 0.0),
                }
            elif layer == "V4":
                v4_features = {
                    "dominant_hue": content.get("dominant_hue", 0),
                    "saturation": content.get("dominant_saturation", 0.0),
                    "colors": [],
                }
            elif layer == "IT":
                it_features = {
                    "scene_type": content.get("scene_type", "unknown"),
                    "complexity": content.get("keypoint_density", 0.0),
                }

        # Emit FF77 frequency vector
        emit_visual_frequency(
            v1_features=v1_features,
            v2_features=v2_features,
            v4_features=v4_features,
            it_features=it_features,
            meta={"attention": 0.6, "novelty": 0.5},
            organ="VisualIngestPipeline"
        )

        # Also emit SRM triples for visual features
        emit_visual_srm(
            image_id=result["image_id"],
            features={
                "dominant_color": v4_features.get("dominant_hue", 0),
                "edge_density": v1_features.get("edge_density", 0.0),
            },
            scene_type=it_features.get("scene_type", "unknown")
        )

        result["ff77_emitted"] = True
    except ImportError as e:
        result["ff77_emitted"] = False
        result["ff77_note"] = f"FF77 not available: {e}"
    except Exception as e:
        result["ff77_emitted"] = False
        result["ff77_error"] = str(e)

    # Step 2: Route each card to SRM
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()

        ingested_ids = []
        for card in result["cards"]:
            # Create SRM-compatible record from card
            record = {
                "id": card["id"],
                "who": card["helix"]["L"]["w"]["who"],
                "what": card["helix"]["L"]["w"]["what"],
                "when": card["ts"],
                "where": card["helix"]["L"]["w"]["where"],
                "why": card["helix"]["L"]["w"]["why"],
                "how": card["helix"]["L"]["w"]["how"],
                "ts": card["ts"],
                "media_type": card["media_type"],
                "content": json.dumps(card["content"]),
                "ptr": card["ptr"],
                "tags": card["tags"],
                "siblings": card["siblings"],
                "image_id": card["image_id"],
            }

            # Route to SRM ingest
            post.route("srm.ingest", {
                "opcode": "INGEST_VISUAL_CARD",
                "record": record,
                "card": card,
            })
            ingested_ids.append(card["id"])

        # Emit to consciousness stream
        post.route("consciousness.stream", {
            "type": "visual_training",
            "stream": "working",
            "source": "VisualIngestPipeline",
            "content": {
                "image_id": result["image_id"],
                "cards_created": len(result["cards"]),
                "layers": result["layers_extracted"],
                "labels": labels,
            },
            "ts": time.time(),
        })

        result["ingested_to_srm"] = True
        result["ingested_ids"] = ingested_ids

    except Exception as e:
        print(f"[VisualIngest] SRM routing failed: {e}")
        result["ingested_to_srm"] = False
        result["srm_error"] = str(e)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH INGEST
# ═══════════════════════════════════════════════════════════════════════════════

def batch_ingest_directory(
    directory: str,
    labels: List[str] = None,
    recursive: bool = False,
) -> Dict[str, Any]:
    """
    Batch ingest all images in a directory.

    Returns statistics on cards created per image.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return {"error": f"Directory not found: {directory}"}

    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    pattern = "**/*" if recursive else "*"

    results = []
    total_cards = 0

    for file_path in dir_path.glob(pattern):
        if file_path.suffix.lower() in valid_extensions:
            result = ingest_and_route_to_srm(str(file_path), labels=labels)
            results.append({
                "path": str(file_path),
                "image_id": result.get("image_id"),
                "card_count": result.get("card_count", 0),
                "ok": result.get("ok", False),
                "error": result.get("error"),
            })
            total_cards += result.get("card_count", 0)

    return {
        "ok": True,
        "images_processed": len(results),
        "total_cards_created": total_cards,
        "avg_cards_per_image": total_cards / len(results) if results else 0,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOL REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def register_visual_ingest_tools(mcp):
    """Register visual ingest tools with MCP."""

    @mcp.tool()
    def visual_ingest_image(
        path: str,
        labels: str = "",
        description: str = "",
    ) -> str:
        """
        Ingest an image through the visual cortex training pipeline.

        This creates 5 cards per image:
        - V1: Edges and orientations (primary visual cortex)
        - V2: Shapes and contours (secondary visual cortex)
        - V4: Colors and brightness (color processing)
        - IT: Objects and scene type (object recognition)
        - PTR: File pointer and metadata

        All cards are linked as siblings for complete recall.

        Args:
            path: Path to image file
            labels: Comma-separated labels for training
            description: Optional description

        Returns:
            JSON with cards created and ingestion status
        """
        label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []
        result = ingest_and_route_to_srm(path, labels=label_list, description=description)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def visual_ingest_directory(
        directory: str,
        labels: str = "",
        recursive: str = "false",
    ) -> str:
        """
        Batch ingest all images in a directory through visual cortex.

        Creates ~5 cards per image for complete visual understanding.

        Args:
            directory: Directory to scan
            labels: Comma-separated labels for all images
            recursive: "true" to scan subdirectories

        Returns:
            JSON with statistics (total cards, cards per image)
        """
        label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []
        is_recursive = recursive.lower() in ("true", "yes", "1")
        result = batch_ingest_directory(directory, labels=label_list, recursive=is_recursive)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def visual_card_count_for_recall(
        image_path: str,
    ) -> str:
        """
        Check how many cards would be created for an image.

        Use this to verify card count for perfect recall.

        Args:
            image_path: Path to image

        Returns:
            JSON with card count breakdown by layer
        """
        result = ingest_image_to_cards(image_path, store_file=False)
        if result.get("error"):
            return json.dumps(result)

        breakdown = {
            "total_cards": result["card_count"],
            "layers": result["layers_extracted"],
            "cards_by_layer": {},
        }

        for card in result.get("cards", []):
            layer = card.get("card_type", "unknown")
            breakdown["cards_by_layer"][layer] = {
                "id": card["id"],
                "content_keys": list(card.get("content", {}).keys()),
                "affect": card["helix"]["C"]["energy"],
            }

        return json.dumps(breakdown, indent=2, default=str)

    print("[VisualIngest] Registered: visual_ingest_image, visual_ingest_directory, visual_card_count_for_recall")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"Testing visual ingest pipeline on: {path}")
        result = ingest_image_to_cards(path, labels=["test"], store_file=False)
        print(json.dumps(result, indent=2, default=str))
        print(f"\n=== CARD COUNT FOR PERFECT RECALL: {result.get('card_count', 0)} cards ===")
    else:
        print("Usage: python visual_ingest_pipeline.py <image_path>")
        print("\nThis creates 5 cards per image:")
        print("  V1 - Edges/orientations (primary visual cortex)")
        print("  V2 - Shapes/contours (secondary visual cortex)")
        print("  V4 - Colors/brightness (color processing)")
        print("  IT - Objects/scene (object recognition)")
        print("  PTR - File pointer/metadata")
