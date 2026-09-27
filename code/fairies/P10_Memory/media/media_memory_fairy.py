# media_memory_fairy.py - Ingest images/videos/audio into SRM memory
# P10_Memory/media/media_memory_fairy.py
#
# Processes media files and stores them in the media cluster for recall.
# NO external APIs - all local processing.

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Storage paths
MEDIA_CLUSTER_PATH = Path(__file__).parent.parent / "SRM_Clusters" / "media"
IMAGES_PATH = MEDIA_CLUSTER_PATH / "images"
THUMBNAILS_PATH = MEDIA_CLUSTER_PATH / "thumbnails"
INDEX_PATH = MEDIA_CLUSTER_PATH / "media_index.json"

# Ensure directories exist
MEDIA_CLUSTER_PATH.mkdir(parents=True, exist_ok=True)
IMAGES_PATH.mkdir(exist_ok=True)
THUMBNAILS_PATH.mkdir(exist_ok=True)


@dataclass
class MediaRecord:
    """A single media item in memory."""
    id: str
    filename: str
    original_path: str
    stored_path: str
    thumbnail_path: Optional[str]

    # Extracted traits
    width: int = 0
    height: int = 0
    file_hash: str = ""
    dominant_colors: List[str] = field(default_factory=list)
    color_names: List[str] = field(default_factory=list)
    detected_type: str = "unknown"

    # User-provided context
    tags: List[str] = field(default_factory=list)
    description: str = ""
    context: str = ""

    # Metadata
    media_type: str = "image"
    ingested_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MediaRecord":
        return cls(**d)


class MediaIndex:
    """Index of all media in the cluster."""

    def __init__(self, index_path: Path = INDEX_PATH):
        self.index_path = index_path
        self.records: Dict[str, MediaRecord] = {}
        self.hash_to_id: Dict[str, str] = {}  # For deduplication
        self._load()

    def _load(self):
        """Load index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for rid, rec_dict in data.get("records", {}).items():
                    rec = MediaRecord.from_dict(rec_dict)
                    self.records[rid] = rec
                    if rec.file_hash:
                        self.hash_to_id[rec.file_hash] = rid
            except Exception as e:
                print(f"[MediaIndex] Load error: {e}")

    def _save(self):
        """Save index to disk."""
        data = {
            "records": {rid: rec.to_dict() for rid, rec in self.records.items()},
            "count": len(self.records),
            "updated_at": time.time(),
        }
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[MediaIndex] Save error: {e}")

    def add(self, record: MediaRecord) -> str:
        """Add a record to the index."""
        self.records[record.id] = record
        if record.file_hash:
            self.hash_to_id[record.file_hash] = record.id
        self._save()
        return record.id

    def get(self, record_id: str) -> Optional[MediaRecord]:
        """Get a record by ID."""
        return self.records.get(record_id)

    def get_by_hash(self, file_hash: str) -> Optional[MediaRecord]:
        """Get a record by file hash (for deduplication)."""
        rid = self.hash_to_id.get(file_hash)
        if rid:
            return self.records.get(rid)
        return None

    def search(self, query: str) -> List[MediaRecord]:
        """Search records by tags, description, colors."""
        query_lower = query.lower()
        results = []
        for rec in self.records.values():
            # Check tags
            if any(query_lower in t.lower() for t in rec.tags):
                results.append(rec)
                continue
            # Check colors
            if any(query_lower in c.lower() for c in rec.color_names):
                results.append(rec)
                continue
            # Check description
            if query_lower in rec.description.lower():
                results.append(rec)
                continue
            # Check filename
            if query_lower in rec.filename.lower():
                results.append(rec)
                continue
        return results

    def list_all(self) -> List[MediaRecord]:
        """Get all records."""
        return list(self.records.values())

    def count(self) -> int:
        return len(self.records)


def _generate_id() -> str:
    """Generate a unique media ID."""
    import uuid
    return f"img_{uuid.uuid4().hex[:12]}"


def _extract_image_traits(path: str) -> Dict[str, Any]:
    """Extract traits from an image locally."""
    result = {}
    img_path = Path(path)

    # File hash
    try:
        with open(img_path, 'rb') as f:
            result["file_hash"] = hashlib.sha256(f.read()).hexdigest()[:16]
    except:
        result["file_hash"] = ""

    # Dimensions
    try:
        from PIL import Image
        with Image.open(img_path) as img:
            result["width"] = img.width
            result["height"] = img.height
    except:
        result["width"] = 0
        result["height"] = 0

    # Colors
    try:
        from colorthief import ColorThief
        ct = ColorThief(path)
        palette = ct.get_palette(color_count=5, quality=10)
        result["dominant_colors"] = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]
    except:
        try:
            from PIL import Image
            from collections import Counter
            img = Image.open(path).convert('RGB').resize((100, 100))
            pixels = list(img.getdata())
            quantized = [(r//32*32, g//32*32, b//32*32) for r, g, b in pixels]
            counts = Counter(quantized)
            top = counts.most_common(5)
            result["dominant_colors"] = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in top]
        except:
            result["dominant_colors"] = []

    # Color names
    result["color_names"] = [_color_name(c) for c in result.get("dominant_colors", []) if not c.startswith("error")]

    # Type detection
    result["detected_type"] = _detect_type(path)

    return result


def _color_name(hex_color: str) -> str:
    """Convert hex to proper color name - handles purples, pinks, etc."""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

    # Grayscale detection
    if max(r, g, b) < 30:
        return "black"
    if min(r, g, b) > 225:
        return "white"
    if abs(r - g) < 20 and abs(g - b) < 20 and abs(r - b) < 20:
        avg = (r + g + b) // 3
        if avg > 200: return "white"
        if avg > 160: return "silver"
        if avg > 100: return "gray"
        if avg > 50: return "dark gray"
        return "black"

    # Calculate lightness
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    lightness = (max_c + min_c) / 2 / 255

    if max_c == min_c:
        return "gray"

    # Purple/Violet detection (high R and B, low G)
    if r > 80 and b > 80 and g < max(r, b) * 0.7:
        if lightness > 0.7:
            return "lavender"
        if r > b:
            return "magenta" if r > 180 else "purple"
        else:
            return "violet" if b > 180 else "purple"

    # Pink detection (high R, moderate B, low G)
    if r > 150 and b > 80 and g < r * 0.7 and r > b:
        if lightness > 0.7:
            return "pink"
        return "hot pink" if b > 100 else "rose"

    # Cyan/Teal (high G and B, low R)
    if g > 100 and b > 100 and r < max(g, b) * 0.6:
        if g > b:
            return "teal"
        return "cyan"

    # Orange/Yellow (high R and G, low B)
    if r > 150 and g > 100 and b < min(r, g) * 0.5:
        if g > r * 0.8:
            return "yellow" if g > 200 else "gold"
        return "orange"

    # Primary color detection
    if r > g and r > b:
        if g > b:
            return "orange" if g > r * 0.5 else "red"
        return "red" if b < r * 0.5 else "crimson"

    if g > r and g > b:
        if b > r:
            return "teal"
        return "green" if r < g * 0.5 else "lime"

    if b > r and b > g:
        if r > g:
            return "indigo" if r > b * 0.4 else "blue"
        return "blue" if g < b * 0.5 else "sky blue"

    return "mixed"


def _detect_type(path: str) -> str:
    """Detect image type."""
    try:
        from PIL import Image
        from collections import Counter

        with Image.open(path) as img:
            img = img.convert('RGB')
            pixels = list(img.getdata())
            color_counts = Counter(pixels)
            top_ratio = color_counts.most_common(1)[0][1] / len(pixels)

            if top_ratio > 0.3:
                return "screenshot"
            elif top_ratio > 0.1:
                return "diagram"
            else:
                return "photo"
    except:
        return "unknown"


def _create_thumbnail(source_path: str, thumb_path: str, size: int = 256) -> bool:
    """Create a thumbnail - handles RGBA/P mode images."""
    try:
        from PIL import Image
        with Image.open(source_path) as img:
            # Convert RGBA/P to RGB for JPEG
            if img.mode in ('RGBA', 'P', 'LA'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            img.thumbnail((size, size))
            img.save(thumb_path, "JPEG", quality=80)
        return True
    except Exception as e:
        # Silently fail - thumbnail is optional
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INGEST FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def ingest_image(
    path: str,
    tags: List[str] = None,
    description: str = "",
    context: str = "",
    copy_to_cluster: bool = True
) -> Dict[str, Any]:
    """
    Ingest an image into the media memory cluster.

    Args:
        path: Path to image file
        tags: Tags to associate with the image
        description: Text description
        context: Context about when/why this was created
        copy_to_cluster: Whether to copy the file to storage

    Returns:
        Dict with ingestion result
    """
    tags = tags or []
    img_path = Path(path)

    if not img_path.exists():
        return {"error": f"Image not found: {path}"}

    # Load index
    index = MediaIndex()

    # Extract traits
    traits = _extract_image_traits(path)

    # Check for duplicate
    existing = index.get_by_hash(traits.get("file_hash", ""))
    if existing:
        return {
            "ok": True,
            "duplicate": True,
            "id": existing.id,
            "message": f"Image already in memory as {existing.id}",
            "record": existing.to_dict()
        }

    # Generate ID
    media_id = _generate_id()

    # Copy file to cluster storage
    if copy_to_cluster:
        ext = img_path.suffix.lower()
        stored_filename = f"{media_id}{ext}"
        stored_path = IMAGES_PATH / stored_filename
        try:
            shutil.copy2(path, stored_path)
        except Exception as e:
            return {"error": f"Failed to copy: {e}"}
    else:
        stored_path = img_path

    # Create thumbnail
    thumb_filename = f"{media_id}_thumb.jpg"
    thumb_path = THUMBNAILS_PATH / thumb_filename
    if _create_thumbnail(path, str(thumb_path)):
        thumb_str = str(thumb_path)
    else:
        thumb_str = None

    # Create record
    record = MediaRecord(
        id=media_id,
        filename=img_path.name,
        original_path=str(img_path.absolute()),
        stored_path=str(stored_path),
        thumbnail_path=thumb_str,
        width=traits.get("width", 0),
        height=traits.get("height", 0),
        file_hash=traits.get("file_hash", ""),
        dominant_colors=traits.get("dominant_colors", []),
        color_names=traits.get("color_names", []),
        detected_type=traits.get("detected_type", "unknown"),
        tags=tags,
        description=description,
        context=context,
        media_type="image",
    )

    # Add to index
    index.add(record)

    return {
        "ok": True,
        "id": media_id,
        "filename": img_path.name,
        "stored_path": str(stored_path),
        "thumbnail_path": thumb_str,
        "traits": {
            "width": record.width,
            "height": record.height,
            "colors": record.color_names,
            "type": record.detected_type,
        },
        "tags": tags,
    }


def ingest_directory(
    directory: str,
    tags: List[str] = None,
    context: str = "",
    recursive: bool = False
) -> Dict[str, Any]:
    """
    Ingest all images in a directory.

    Args:
        directory: Directory to scan
        tags: Tags to apply to all images
        context: Context for all images
        recursive: Whether to scan subdirectories

    Returns:
        Dict with results
    """
    tags = tags or []
    dir_path = Path(directory)

    if not dir_path.exists():
        return {"error": f"Directory not found: {directory}"}

    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    pattern = "**/*" if recursive else "*"

    results = []
    errors = []
    duplicates = []

    for file_path in dir_path.glob(pattern):
        if file_path.suffix.lower() in valid_extensions:
            result = ingest_image(
                str(file_path),
                tags=tags,
                context=context,
            )
            if result.get("error"):
                errors.append({"path": str(file_path), "error": result["error"]})
            elif result.get("duplicate"):
                duplicates.append(result["id"])
            else:
                results.append(result)

    return {
        "ok": True,
        "ingested": len(results),
        "duplicates": len(duplicates),
        "errors": len(errors),
        "results": results,
        "error_details": errors if errors else None,
    }




def _extract_image_traits_fast(path: str) -> Dict[str, Any]:
    """Fast trait extraction - skip ColorThief, use simple PIL sampling."""
    result = {}
    img_path = Path(path)

    # File hash (fast)
    try:
        # Only hash first 64KB for speed
        with open(img_path, 'rb') as f:
            result["file_hash"] = hashlib.sha256(f.read(65536)).hexdigest()[:16]
    except:
        result["file_hash"] = ""

    # Dimensions and colors (fast)
    try:
        from PIL import Image
        from collections import Counter

        with Image.open(img_path) as img:
            result["width"] = img.width
            result["height"] = img.height

            # Fast color sampling - resize to tiny, get top colors
            small = img.convert('RGB').resize((50, 50), Image.Resampling.NEAREST)
            pixels = list(small.getdata())
            # Quantize to reduce colors
            quantized = [(r//32*32, g//32*32, b//32*32) for r, g, b in pixels]
            counts = Counter(quantized)
            top = counts.most_common(5)
            result["dominant_colors"] = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in top]
    except:
        result["width"] = 0
        result["height"] = 0
        result["dominant_colors"] = []

    result["color_names"] = [_color_name(c) for c in result.get("dominant_colors", [])]
    result["detected_type"] = "photo"  # Skip detection for speed

    return result


def ingest_image_fast(
    path: str,
    tags: List[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    """Fast ingest - for bulk imports. Skips ColorThief, minimal processing."""
    tags = tags or []
    img_path = Path(path)

    if not img_path.exists():
        return {"error": f"Not found: {path}"}

    # Load index
    index = MediaIndex()

    # Fast hash check first (only read 64KB)
    try:
        with open(img_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read(65536)).hexdigest()[:16]
    except:
        file_hash = ""

    # Check duplicate by hash
    if file_hash and file_hash in index.hash_to_id:
        return {"ok": True, "duplicate": True, "id": index.hash_to_id[file_hash]}

    # Extract traits (fast mode)
    traits = _extract_image_traits_fast(path)

    # Generate ID
    media_id = _generate_id()

    # Copy file
    ext = img_path.suffix.lower()
    stored_filename = f"{media_id}{ext}"
    stored_path = IMAGES_PATH / stored_filename
    try:
        shutil.copy2(path, stored_path)
    except Exception as e:
        return {"error": f"Copy failed: {e}"}

    # Quick thumbnail (no fancy conversion)
    thumb_filename = f"{media_id}_thumb.jpg"
    thumb_path = THUMBNAILS_PATH / thumb_filename
    _create_thumbnail(path, str(thumb_path))

    # Create record
    record = MediaRecord(
        id=media_id,
        filename=img_path.name,
        original_path=str(img_path.absolute()),
        stored_path=str(stored_path),
        thumbnail_path=str(thumb_path),
        width=traits.get("width", 0),
        height=traits.get("height", 0),
        file_hash=traits.get("file_hash", ""),
        dominant_colors=traits.get("dominant_colors", []),
        color_names=traits.get("color_names", []),
        detected_type=traits.get("detected_type", "photo"),
        tags=tags,
        context=context,
        media_type="image",
    )

    index.add(record)
    return {"ok": True, "id": media_id, "colors": record.color_names[:3]}



def search_media(query: str) -> List[Dict[str, Any]]:
    """Search media by query."""
    index = MediaIndex()
    results = index.search(query)
    return [r.to_dict() for r in results]


def list_media() -> Dict[str, Any]:
    """List all media in the cluster."""
    index = MediaIndex()
    records = index.list_all()
    return {
        "count": len(records),
        "records": [r.to_dict() for r in records]
    }


def get_media(media_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific media record."""
    index = MediaIndex()
    record = index.get(media_id)
    if record:
        return record.to_dict()
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOL REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def register_media_memory_tools(mcp):
    """Register media memory tools with MCP."""

    @mcp.tool()
    def ingest_image_to_memory(
        path: str,
        tags: str = "",
        description: str = "",
        context: str = ""
    ) -> str:
        """
        Ingest an image into the media memory cluster.

        The image is:
        - Copied to permanent storage
        - Thumbnail generated
        - Colors and traits extracted
        - Indexed for search/recall

        Args:
            path: Path to image file
            tags: Comma-separated tags (e.g., "sour,dress,red")
            description: Description of the image
            context: Context (e.g., "Created during January session")

        Returns:
            JSON with ingestion result
        """
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        result = ingest_image(path, tags=tag_list, description=description, context=context)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def ingest_images_from_directory(
        directory: str,
        tags: str = "",
        context: str = "",
        recursive: str = "false"
    ) -> str:
        """
        Ingest all images from a directory into memory.

        Args:
            directory: Directory to scan
            tags: Comma-separated tags for all images
            context: Context for all images
            recursive: "true" to scan subdirectories

        Returns:
            JSON with batch results
        """
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        is_recursive = recursive.lower() in ("true", "yes", "1")
        result = ingest_directory(directory, tags=tag_list, context=context, recursive=is_recursive)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def search_media_memory(query: str) -> str:
        """
        Search media memory by tags, colors, description.

        Args:
            query: Search query (e.g., "red dress", "blue", "sour")

        Returns:
            JSON list of matching media records
        """
        results = search_media(query)
        return json.dumps({"count": len(results), "results": results}, indent=2)

    @mcp.tool()
    def list_all_media() -> str:
        """
        List all media in the memory cluster.

        Returns:
            JSON with all media records
        """
        result = list_media()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_media_record(media_id: str) -> str:
        """
        Get a specific media record by ID.

        Args:
            media_id: The media ID (e.g., "img_abc123")

        Returns:
            JSON with the media record
        """
        record = get_media(media_id)
        if record:
            return json.dumps({"ok": True, "record": record}, indent=2)
        return json.dumps({"ok": False, "error": f"Media not found: {media_id}"})

    print("[MediaMemory] Registered: ingest_image_to_memory, ingest_images_from_directory, search_media_memory, list_all_media, get_media_record")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"Ingesting: {path}")
        result = ingest_image(path, tags=["test"])
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python media_memory_fairy.py <image_path>")
        print("\nCurrent index:")
        result = list_media()
        print(json.dumps(result, indent=2))
