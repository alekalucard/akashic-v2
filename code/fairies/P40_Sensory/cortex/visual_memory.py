# ══════════════════════════════════════════════════════════════════════════════
# VISUAL MEMORY - The Mind's Eye
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
#
# This is how fairies REMEMBER what they've seen - not just file paths,
# but actual visual features that can be recognized and recalled.
#
# Mirrors human visual cortex hierarchy:
#   V1 - Primary visual cortex (edges, orientations)
#   V2 - Secondary (contours, shapes, figure/ground)
#   V4 - Color processing, complex shapes
#   IT - Inferotemporal (object recognition, faces)
#
# When an image is "trained", we extract all these features and store them.
# When we "see" something new, we can match it against trained memories.
# When we "imagine", we can reconstruct the visual experience internally.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import pickle
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
import threading

# We need specific Python for OpenCV
PYTHON_312 = r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe"

# Storage paths
VISUAL_MEMORY_PATH = Path(__file__).parent.parent.parent / "P10_Memory" / "visual_memory"
FEATURES_PATH = VISUAL_MEMORY_PATH / "features"
INDEX_PATH = VISUAL_MEMORY_PATH / "visual_index.json"
DESCRIPTORS_PATH = VISUAL_MEMORY_PATH / "descriptors"  # Binary ORB descriptors

# Ensure directories
VISUAL_MEMORY_PATH.mkdir(parents=True, exist_ok=True)
FEATURES_PATH.mkdir(exist_ok=True)
DESCRIPTORS_PATH.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL FEATURE SET - What we extract from each image
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class V1Features:
    """Primary visual cortex - edges and orientations."""
    edge_density: float = 0.0           # How many edges (0-1)
    edge_orientation_hist: List[float] = field(default_factory=list)  # 8 bins
    horizontal_edges: float = 0.0       # Proportion horizontal
    vertical_edges: float = 0.0         # Proportion vertical
    diagonal_edges: float = 0.0         # Proportion diagonal


@dataclass 
class V2Features:
    """Secondary visual cortex - shapes and contours."""
    contour_count: int = 0              # Number of distinct shapes
    avg_contour_size: float = 0.0       # Average shape size
    shape_complexity: float = 0.0       # How complex are the shapes
    has_rectangles: bool = False        # UI elements, windows
    has_circles: bool = False           # Buttons, icons
    has_text_regions: bool = False      # Areas that look like text


@dataclass
class V4Features:
    """Color processing cortex."""
    dominant_hue: int = 0               # 0-180 (HSV hue)
    dominant_saturation: float = 0.0    # 0-1
    dominant_value: float = 0.0         # 0-1 (brightness)
    color_histogram: List[float] = field(default_factory=list)  # 16 bins
    is_grayscale: bool = False
    is_dark: bool = False               # Overall dark image
    is_bright: bool = False             # Overall bright image
    color_variance: float = 0.0         # How varied are colors


@dataclass
class ITFeatures:
    """Inferotemporal cortex - object recognition."""
    keypoint_count: int = 0             # ORB keypoints found
    keypoint_density: float = 0.0       # Keypoints per pixel
    descriptor_hash: str = ""           # Hash of descriptor set for quick matching
    scene_type: str = "unknown"         # screenshot, photo, diagram, ui, art
    # Descriptors stored separately (binary, too large for JSON)


@dataclass
class VisualSignature:
    """Complete visual signature of a trained image."""
    image_id: str                       # Links to MediaRecord
    source_path: str                    # Original image path
    trained_at: float                   # Timestamp
    
    # Perceptual hashes for quick matching
    phash: str = ""                     # Perceptual hash
    ahash: str = ""                     # Average hash
    dhash: str = ""                     # Difference hash
    
    # Hierarchical features
    v1: V1Features = field(default_factory=V1Features)
    v2: V2Features = field(default_factory=V2Features)
    v4: V4Features = field(default_factory=V4Features)
    it: ITFeatures = field(default_factory=ITFeatures)
    
    # Image metadata
    width: int = 0
    height: int = 0
    aspect_ratio: float = 1.0
    
    # Human-provided context (for learning)
    labels: List[str] = field(default_factory=list)
    description: str = ""
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "image_id": self.image_id,
            "source_path": self.source_path,
            "trained_at": self.trained_at,
            "phash": self.phash,
            "ahash": self.ahash,
            "dhash": self.dhash,
            "v1": asdict(self.v1),
            "v2": asdict(self.v2),
            "v4": asdict(self.v4),
            "it": asdict(self.it),
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "labels": self.labels,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "VisualSignature":
        """Create from dict."""
        sig = cls(
            image_id=d["image_id"],
            source_path=d["source_path"],
            trained_at=d["trained_at"],
        )
        sig.phash = d.get("phash", "")
        sig.ahash = d.get("ahash", "")
        sig.dhash = d.get("dhash", "")
        sig.width = d.get("width", 0)
        sig.height = d.get("height", 0)
        sig.aspect_ratio = d.get("aspect_ratio", 1.0)
        sig.labels = d.get("labels", [])
        sig.description = d.get("description", "")
        
        if "v1" in d:
            sig.v1 = V1Features(**d["v1"])
        if "v2" in d:
            sig.v2 = V2Features(**d["v2"])
        if "v4" in d:
            sig.v4 = V4Features(**d["v4"])
        if "it" in d:
            sig.it = ITFeatures(**d["it"])
        
        return sig


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL MEMORY INDEX
# ══════════════════════════════════════════════════════════════════════════════

class VisualMemoryIndex:
    """Index of all trained visual memories."""
    
    def __init__(self, index_path: Path = INDEX_PATH):
        self.index_path = index_path
        self.signatures: Dict[str, VisualSignature] = {}
        self.phash_to_id: Dict[str, str] = {}  # Quick perceptual hash lookup
        self._load()
    
    def _load(self):
        """Load index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for sid, sig_dict in data.get("signatures", {}).items():
                    sig = VisualSignature.from_dict(sig_dict)
                    self.signatures[sid] = sig
                    if sig.phash:
                        self.phash_to_id[sig.phash] = sid
                print(f"[VisualMemory] Loaded {len(self.signatures)} visual signatures")
            except Exception as e:
                print(f"[VisualMemory] Load error: {e}")
    
    def _save(self):
        """Save index to disk."""
        data = {
            "signatures": {sid: sig.to_dict() for sid, sig in self.signatures.items()},
            "count": len(self.signatures),
            "updated_at": time.time(),
        }
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[VisualMemory] Save error: {e}")
    
    def add(self, signature: VisualSignature) -> str:
        """Add a visual signature."""
        self.signatures[signature.image_id] = signature
        if signature.phash:
            self.phash_to_id[signature.phash] = signature.image_id
        self._save()
        return signature.image_id
    
    def get(self, image_id: str) -> Optional[VisualSignature]:
        """Get signature by ID."""
        return self.signatures.get(image_id)
    
    def get_by_phash(self, phash: str) -> Optional[VisualSignature]:
        """Get signature by perceptual hash."""
        sid = self.phash_to_id.get(phash)
        if sid:
            return self.signatures.get(sid)
        return None
    
    def count(self) -> int:
        return len(self.signatures)
    
    def list_all(self) -> List[VisualSignature]:
        return list(self.signatures.values())


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE EXTRACTION - The Training Process
# ══════════════════════════════════════════════════════════════════════════════

def extract_visual_features(image_path: str) -> Optional[VisualSignature]:
    """
    Extract all visual features from an image.
    
    This is the TRAINING process - converting raw pixels into
    visual cortex representations.
    """
    try:
        import cv2
        import numpy as np
        import imagehash
        from PIL import Image
    except ImportError as e:
        print(f"[VisualMemory] Missing dependency: {e}")
        return None
    
    path = Path(image_path)
    if not path.exists():
        return None
    
    # Generate ID from path hash
    image_id = hashlib.md5(str(path.absolute()).encode()).hexdigest()[:12]
    
    # Load image
    img = cv2.imread(str(path))
    if img is None:
        return None
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    
    # Create signature
    sig = VisualSignature(
        image_id=image_id,
        source_path=str(path.absolute()),
        trained_at=time.time(),
        width=width,
        height=height,
        aspect_ratio=width / height if height > 0 else 1.0,
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # PERCEPTUAL HASHES (quick recognition)
    # ─────────────────────────────────────────────────────────────────────────
    try:
        pil_img = Image.open(image_path)
        sig.phash = str(imagehash.phash(pil_img))
        sig.ahash = str(imagehash.average_hash(pil_img))
        sig.dhash = str(imagehash.dhash(pil_img))
    except Exception as e:
        print(f"[VisualMemory] Hash error: {e}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # V1 FEATURES - Edges and orientations
    # ─────────────────────────────────────────────────────────────────────────
    try:
        edges = cv2.Canny(gray, 100, 200)
        sig.v1.edge_density = float(np.sum(edges > 0) / edges.size)
        
        # Sobel for orientation
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        # Calculate edge orientations
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        orientation = np.arctan2(sobely, sobelx) * 180 / np.pi
        
        # Histogram of orientations (8 bins: 0, 45, 90, 135, ...)
        hist, _ = np.histogram(orientation[magnitude > 30], bins=8, range=(-180, 180))
        hist = hist / (hist.sum() + 1e-6)
        sig.v1.edge_orientation_hist = hist.tolist()
        
        # Dominant orientations
        sig.v1.horizontal_edges = float(hist[0] + hist[4])  # 0 and 180 degrees
        sig.v1.vertical_edges = float(hist[2] + hist[6])    # 90 and -90 degrees
        sig.v1.diagonal_edges = float(hist[1] + hist[3] + hist[5] + hist[7])
    except Exception as e:
        print(f"[VisualMemory] V1 error: {e}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # V2 FEATURES - Shapes and contours
    # ─────────────────────────────────────────────────────────────────────────
    try:
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        sig.v2.contour_count = len(contours)
        
        if contours:
            areas = [cv2.contourArea(c) for c in contours]
            sig.v2.avg_contour_size = float(np.mean(areas)) if areas else 0.0
            
            # Check for rectangles and circles
            for c in contours[:100]:  # Limit for speed
                approx = cv2.approxPolyDP(c, 0.04 * cv2.arcLength(c, True), True)
                if len(approx) == 4:
                    sig.v2.has_rectangles = True
                area = cv2.contourArea(c)
                perimeter = cv2.arcLength(c, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.7:
                        sig.v2.has_circles = True
            
            # Shape complexity (average vertices per contour)
            complexities = [len(cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)) 
                          for c in contours[:100]]
            sig.v2.shape_complexity = float(np.mean(complexities)) if complexities else 0.0
    except Exception as e:
        print(f"[VisualMemory] V2 error: {e}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # V4 FEATURES - Color processing
    # ─────────────────────────────────────────────────────────────────────────
    try:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        # Dominant values
        sig.v4.dominant_hue = int(np.median(h))
        sig.v4.dominant_saturation = float(np.mean(s) / 255.0)
        sig.v4.dominant_value = float(np.mean(v) / 255.0)
        
        # Color histogram (16 hue bins)
        h_hist = cv2.calcHist([hsv], [0], None, [16], [0, 180])
        h_hist = h_hist.flatten() / (h_hist.sum() + 1e-6)
        sig.v4.color_histogram = h_hist.tolist()
        
        # Color properties
        sig.v4.is_grayscale = float(np.std(s)) < 15
        sig.v4.is_dark = sig.v4.dominant_value < 0.3
        sig.v4.is_bright = sig.v4.dominant_value > 0.7
        sig.v4.color_variance = float(np.std(h))
    except Exception as e:
        print(f"[VisualMemory] V4 error: {e}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # IT FEATURES - Object recognition (ORB keypoints)
    # ─────────────────────────────────────────────────────────────────────────
    try:
        orb = cv2.ORB_create(nfeatures=500)
        keypoints, descriptors = orb.detectAndCompute(gray, None)
        
        sig.it.keypoint_count = len(keypoints)
        sig.it.keypoint_density = len(keypoints) / (width * height) if width * height > 0 else 0
        
        # Store descriptors separately (binary file)
        if descriptors is not None:
            desc_path = DESCRIPTORS_PATH / f"{image_id}.pkl"
            with open(desc_path, 'wb') as f:
                pickle.dump(descriptors, f)
            sig.it.descriptor_hash = hashlib.md5(descriptors.tobytes()).hexdigest()[:16]
        
        # Classify scene type based on features
        if sig.v2.has_rectangles and sig.v4.is_grayscale:
            sig.it.scene_type = "ui"
        elif sig.v1.edge_density > 0.15 and sig.v2.has_rectangles:
            sig.it.scene_type = "screenshot"
        elif sig.v4.color_variance < 20 and sig.v1.edge_density < 0.05:
            sig.it.scene_type = "diagram"
        elif sig.it.keypoint_count > 200:
            sig.it.scene_type = "photo"
        else:
            sig.it.scene_type = "art"
    except Exception as e:
        print(f"[VisualMemory] IT error: {e}")
    
    return sig


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL MEMORY CLASS - The Mind's Eye
# ══════════════════════════════════════════════════════════════════════════════

class VisualMemory:
    """
    The visual memory system - stores and recalls trained visual signatures.
    
    This is the bridge between MediaMemoryFairy (stores images) and
    VisualCortexFairy (sees the screen). It provides:
    
    1. TRAINING - Extract and store visual features from images
    2. RECOGNITION - Match incoming vision against stored memories
    3. RECALL - Retrieve visual signatures for internal visualization
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.index = VisualMemoryIndex()
        self._initialized = True
        print(f"[VisualMemory] Initialized with {self.index.count()} trained images")
    
    def train(self, image_path: str, labels: List[str] = None, 
              description: str = "") -> Optional[Dict[str, Any]]:
        """
        Train visual memory on an image.
        
        This extracts all visual features and stores them for later recognition.
        """
        sig = extract_visual_features(image_path)
        if sig is None:
            return {"error": f"Failed to extract features from {image_path}"}
        
        # Add human-provided context
        sig.labels = labels or []
        sig.description = description
        
        # Store
        self.index.add(sig)
        
        return {
            "ok": True,
            "image_id": sig.image_id,
            "scene_type": sig.it.scene_type,
            "features": {
                "edge_density": sig.v1.edge_density,
                "contours": sig.v2.contour_count,
                "dominant_hue": sig.v4.dominant_hue,
                "keypoints": sig.it.keypoint_count,
            },
            "phash": sig.phash,
        }
    
    def recognize(self, image_path: str, threshold: int = 10) -> Optional[Dict[str, Any]]:
        """
        Check if we've seen this image before.
        
        Uses perceptual hash comparison for quick matching.
        Returns the closest match if found.
        """
        try:
            import imagehash
            from PIL import Image
            
            pil_img = Image.open(image_path)
            query_phash = imagehash.phash(pil_img)
            
            best_match = None
            best_distance = float('inf')
            
            for sig in self.index.list_all():
                if sig.phash:
                    stored_phash = imagehash.hex_to_hash(sig.phash)
                    distance = query_phash - stored_phash
                    if distance < best_distance:
                        best_distance = distance
                        best_match = sig
            
            if best_match and best_distance <= threshold:
                return {
                    "recognized": True,
                    "image_id": best_match.image_id,
                    "distance": best_distance,
                    "confidence": 1.0 - (best_distance / 64.0),  # phash is 64 bits
                    "labels": best_match.labels,
                    "description": best_match.description,
                    "scene_type": best_match.it.scene_type,
                }
            
            return {"recognized": False, "closest_distance": best_distance}
            
        except Exception as e:
            return {"error": str(e)}
    
    def recall(self, image_id: str) -> Optional[VisualSignature]:
        """
        Recall a visual memory by ID.
        
        Returns the full visual signature for internal visualization.
        """
        return self.index.get(image_id)
    
    def describe_visual_field(self, sig: VisualSignature) -> str:
        """
        Generate a natural language description of what was seen.
        
        This is for internal visualization - the VR construct.
        """
        parts = []
        
        # Scene type
        scene_desc = {
            "screenshot": "a computer screen capture",
            "photo": "a photograph",
            "diagram": "a diagram or illustration",
            "ui": "a user interface",
            "art": "an artistic image",
        }
        parts.append(f"This is {scene_desc.get(sig.it.scene_type, 'an image')}")
        
        # Color
        if sig.v4.is_grayscale:
            parts.append("in grayscale")
        elif sig.v4.is_dark:
            parts.append("with dark tones")
        elif sig.v4.is_bright:
            parts.append("with bright colors")
        
        # Complexity
        if sig.v1.edge_density > 0.15:
            parts.append("with high visual detail")
        elif sig.v1.edge_density < 0.03:
            parts.append("with minimal detail")
        
        # Shapes
        if sig.v2.has_rectangles and sig.v2.has_circles:
            parts.append("containing rectangular and circular elements")
        elif sig.v2.has_rectangles:
            parts.append("with rectangular structures")
        
        # Human context
        if sig.labels:
            parts.append(f"labeled as: {', '.join(sig.labels)}")
        if sig.description:
            parts.append(f"described as: {sig.description}")
        
        return ". ".join(parts) + "."
    
    def get_stats(self) -> Dict[str, Any]:
        """Get visual memory statistics."""
        sigs = self.index.list_all()
        
        scene_counts = {}
        for sig in sigs:
            st = sig.it.scene_type
            scene_counts[st] = scene_counts.get(st, 0) + 1
        
        return {
            "total_trained": len(sigs),
            "scene_types": scene_counts,
            "has_labels": sum(1 for s in sigs if s.labels),
            "has_descriptions": sum(1 for s in sigs if s.description),
        }


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_visual_memory() -> VisualMemory:
    """Get the singleton visual memory instance."""
    return VisualMemory()


def train_image(image_path: str, labels: List[str] = None, 
                description: str = "") -> Dict[str, Any]:
    """Train visual memory on a single image."""
    return get_visual_memory().train(image_path, labels, description)


def recognize_image(image_path: str) -> Dict[str, Any]:
    """Check if an image has been seen before."""
    return get_visual_memory().recognize(image_path)


def recall_visual_memory(image_id: str) -> Optional[VisualSignature]:
    """Recall a visual memory."""
    return get_visual_memory().recall(image_id)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Visual Memory Test ===\n")
    
    vm = get_visual_memory()
    print(f"Stats: {vm.get_stats()}")
    
    # Test training on an image
    from pathlib import Path
    test_images = list(Path("P10_Memory/SRM_Clusters/media/images").glob("*.png"))[:1]
    
    if test_images:
        print(f"\nTraining on: {test_images[0].name}")
        result = vm.train(str(test_images[0]), labels=["test"], description="test image")
        print(f"Result: {result}")
        
        if result.get("ok"):
            sig = vm.recall(result["image_id"])
            if sig:
                print(f"\nRecalled description:")
                print(vm.describe_visual_field(sig))
