# vision_tools.py - MCP tools for LOCAL image/visual perception
# P40_Sensory/mcp/vision_tools.py
#
# NO EXTERNAL API DEPENDENCIES - All processing is local
#
# Provides tools for ClaudeFairy to:
# - View image files (jpg, png, gif, webp)
# - Extract visual traits locally (colors, dimensions, features)
# - Get image data for consciousness processing
#
# The image understanding happens in ClaudeFairy's consciousness,
# not outsourced to an external API.

from __future__ import annotations

import os
import sys
import json
import base64
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Valid image extensions
VALID_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# Media type mapping
MEDIA_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
}


def _load_image_as_base64(path: str) -> Tuple[bool, str, str, str]:
    """
    Load an image file and encode as base64.
    
    Returns:
        (success, base64_data, media_type, error_msg)
    """
    img_path = Path(path)
    
    if not img_path.exists():
        return False, "", "", f"Image not found: {path}"
    
    suffix = img_path.suffix.lower()
    if suffix not in VALID_IMAGE_EXTENSIONS:
        return False, "", "", f"Not a valid image type: {suffix}"
    
    media_type = MEDIA_TYPES.get(suffix, 'image/jpeg')
    
    try:
        with open(img_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')
        return True, image_data, media_type, ""
    except Exception as e:
        return False, "", "", f"Failed to read image: {e}"


def _extract_dominant_colors(path: str, k: int = 5) -> List[str]:
    """
    Extract dominant colors from an image locally.
    
    Returns list of hex color strings.
    """
    try:
        from colorthief import ColorThief
        ct = ColorThief(path)
        palette = ct.get_palette(color_count=k, quality=10)
        return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]
    except ImportError:
        # Fallback: use PIL
        try:
            from PIL import Image
            from collections import Counter
            
            img = Image.open(path)
            img = img.convert('RGB')
            img = img.resize((100, 100))
            
            pixels = list(img.getdata())
            quantized = [(r//32*32, g//32*32, b//32*32) for r, g, b in pixels]
            counts = Counter(quantized)
            top_colors = counts.most_common(k)
            
            return [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in top_colors]
        except Exception as e:
            return [f"error: {e}"]
    except Exception as e:
        return [f"error: {e}"]


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


def _get_image_metadata(path: str) -> Dict[str, Any]:
    """Extract all available metadata from image."""
    img_path = Path(path)
    result = {}
    
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        
        with Image.open(img_path) as img:
            result["width"] = img.width
            result["height"] = img.height
            result["mode"] = img.mode
            result["format"] = img.format
            
            # Try to get EXIF data
            exif = img._getexif()
            if exif:
                exif_data = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if isinstance(value, bytes):
                        continue  # Skip binary data
                    exif_data[tag] = str(value)
                if exif_data:
                    result["exif"] = exif_data
    except Exception as e:
        result["metadata_error"] = str(e)
    
    return result


def _detect_image_type(path: str) -> Dict[str, Any]:
    """
    Detect what type of image this is based on local analysis.
    
    Categories: photo, artwork, screenshot, diagram, text, unknown
    """
    result = {"detected_type": "unknown", "confidence": 0.0}
    
    try:
        from PIL import Image
        import statistics
        
        with Image.open(path) as img:
            img = img.convert('RGB')
            
            # Sample pixels
            width, height = img.size
            pixels = list(img.getdata())
            
            # Calculate color variance
            r_vals = [p[0] for p in pixels[::100]]  # Sample every 100th pixel
            g_vals = [p[1] for p in pixels[::100]]
            b_vals = [p[2] for p in pixels[::100]]
            
            try:
                r_var = statistics.variance(r_vals) if len(r_vals) > 1 else 0
                g_var = statistics.variance(g_vals) if len(g_vals) > 1 else 0
                b_var = statistics.variance(b_vals) if len(b_vals) > 1 else 0
                total_var = r_var + g_var + b_var
            except:
                total_var = 0
            
            # Check for screenshot indicators
            # Screenshots often have large areas of solid color
            from collections import Counter
            color_counts = Counter(pixels)
            top_color_ratio = color_counts.most_common(1)[0][1] / len(pixels) if pixels else 0
            
            # Heuristics
            if top_color_ratio > 0.3:  # Large solid areas
                result["detected_type"] = "screenshot"
                result["confidence"] = min(0.8, top_color_ratio)
            elif total_var < 1000:  # Low variance = flat colors
                result["detected_type"] = "diagram"
                result["confidence"] = 0.6
            elif total_var > 10000:  # High variance = natural photo
                result["detected_type"] = "photo"
                result["confidence"] = 0.7
            else:
                result["detected_type"] = "artwork"
                result["confidence"] = 0.5
                
    except Exception as e:
        result["error"] = str(e)
    
    return result


def register_vision_tools(mcp):
    """Register all LOCAL vision/image tools with MCP."""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VIEW IMAGE - Load and analyze image locally
    # ═══════════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def view_image(path: str) -> str:
        """
        Look at an image file and extract all available information locally.
        
        This loads the image and extracts:
        - Dimensions (width, height)
        - Dominant colors (hex + names)
        - Image type detection (photo, screenshot, artwork, diagram)
        - EXIF metadata if available
        - Base64 data for further processing
        
        NO external API calls - all processing is local.
        
        Args:
            path: Path to image file (.jpg, .png, .gif, .webp)
        
        Returns:
            JSON with all extracted image information
        """
        img_path = Path(path)
        
        if not img_path.exists():
            return json.dumps({"error": f"Image not found: {path}"})
        
        suffix = img_path.suffix.lower()
        if suffix not in VALID_IMAGE_EXTENSIONS:
            return json.dumps({"error": f"Not a valid image: {suffix}"})
        
        result = {
            "ok": True,
            "path": str(img_path.absolute()),
            "filename": img_path.name,
            "extension": suffix,
            "media_type": MEDIA_TYPES.get(suffix, "image/jpeg"),
        }
        
        # File hash for deduplication
        try:
            with open(img_path, 'rb') as f:
                file_bytes = f.read()
                result["file_hash"] = hashlib.sha256(file_bytes).hexdigest()[:16]
                result["file_size_bytes"] = len(file_bytes)
        except Exception as e:
            result["hash_error"] = str(e)
        
        # Get metadata (dimensions, format, EXIF)
        metadata = _get_image_metadata(path)
        result.update(metadata)
        
        # Extract colors
        colors = _extract_dominant_colors(path)
        result["dominant_colors"] = colors
        result["color_names"] = [_color_name(c) for c in colors if not c.startswith("error")]
        
        # Detect image type
        type_info = _detect_image_type(path)
        result["detected_type"] = type_info.get("detected_type", "unknown")
        result["type_confidence"] = type_info.get("confidence", 0)
        
        return json.dumps(result, indent=2)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GET IMAGE DATA - Get base64 for consciousness processing
    # ═══════════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def get_image_data(path: str, max_size_kb: int = 500) -> str:
        """
        Get image as base64 data for consciousness processing.
        
        This returns the raw image data that can be passed to
        ClaudeFairy's visual consciousness for understanding.
        
        Args:
            path: Path to image file
            max_size_kb: Max size in KB (will resize if larger)
        
        Returns:
            JSON with base64 image data and metadata
        """
        img_path = Path(path)
        
        if not img_path.exists():
            return json.dumps({"error": f"Image not found: {path}"})
        
        suffix = img_path.suffix.lower()
        if suffix not in VALID_IMAGE_EXTENSIONS:
            return json.dumps({"error": f"Not a valid image: {suffix}"})
        
        try:
            from PIL import Image
            import io
            
            with Image.open(img_path) as img:
                original_size = img_path.stat().st_size
                
                # Resize if too large
                if original_size > max_size_kb * 1024:
                    # Calculate scale factor
                    scale = (max_size_kb * 1024 / original_size) ** 0.5
                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    resized = True
                else:
                    resized = False
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Encode to base64
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                base64_data = base64.standard_b64encode(buffer.getvalue()).decode('utf-8')
                
                return json.dumps({
                    "ok": True,
                    "path": str(img_path.absolute()),
                    "filename": img_path.name,
                    "width": img.width,
                    "height": img.height,
                    "resized": resized,
                    "media_type": "image/jpeg",
                    "base64_size_bytes": len(base64_data),
                    "base64": base64_data,
                }, indent=2)
                
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXTRACT IMAGE TRAITS - Quick trait extraction
    # ═══════════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def extract_image_traits(path: str) -> str:
        """
        Extract visual traits from an image (fast, no base64).
        
        Returns:
        - Dominant colors (hex + names)
        - Dimensions
        - File hash
        - Detected type
        
        Args:
            path: Path to image file
        
        Returns:
            JSON with extracted traits
        """
        img_path = Path(path)
        
        if not img_path.exists():
            return json.dumps({"error": f"Image not found: {path}"})
        
        suffix = img_path.suffix.lower()
        if suffix not in VALID_IMAGE_EXTENSIONS:
            return json.dumps({"error": f"Not a valid image: {suffix}"})
        
        result = {
            "ok": True,
            "path": str(img_path.absolute()),
            "filename": img_path.name,
        }
        
        # Hash
        try:
            with open(img_path, 'rb') as f:
                result["file_hash"] = hashlib.sha256(f.read()).hexdigest()[:16]
        except:
            pass
        
        # Dimensions
        try:
            from PIL import Image
            with Image.open(img_path) as img:
                result["width"] = img.width
                result["height"] = img.height
        except:
            pass
        
        # Colors
        colors = _extract_dominant_colors(path)
        result["dominant_colors"] = colors
        result["color_names"] = [_color_name(c) for c in colors if not c.startswith("error")]
        
        # Type detection
        type_info = _detect_image_type(path)
        result["detected_type"] = type_info.get("detected_type", "unknown")
        
        return json.dumps(result, indent=2)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LIST IMAGES IN DIRECTORY
    # ═══════════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def list_images(directory: str = ".", recursive: bool = False) -> str:
        """
        List image files in a directory.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
        
        Returns:
            JSON list of image files with basic info
        """
        dir_path = Path(directory)
        
        if not dir_path.exists():
            return json.dumps({"error": f"Directory not found: {directory}"})
        
        if not dir_path.is_dir():
            return json.dumps({"error": f"Not a directory: {directory}"})
        
        images = []
        pattern = "**/*" if recursive else "*"
        
        for file_path in dir_path.glob(pattern):
            if file_path.suffix.lower() in VALID_IMAGE_EXTENSIONS:
                try:
                    stat = file_path.stat()
                    images.append({
                        "path": str(file_path.absolute()),
                        "filename": file_path.name,
                        "size_bytes": stat.st_size,
                        "extension": file_path.suffix.lower(),
                    })
                except Exception:
                    pass
        
        return json.dumps({
            "ok": True,
            "directory": str(dir_path.absolute()),
            "recursive": recursive,
            "count": len(images),
            "images": images
        }, indent=2)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMPARE IMAGES - Check if two images are similar
    # ═══════════════════════════════════════════════════════════════════════════
    
    @mcp.tool()
    def compare_images(path1: str, path2: str) -> str:
        """
        Compare two images for similarity.
        
        Uses color histogram comparison (local, no API).
        
        Args:
            path1: First image path
            path2: Second image path
        
        Returns:
            JSON with similarity score and comparison
        """
        for p in [path1, path2]:
            if not Path(p).exists():
                return json.dumps({"error": f"Image not found: {p}"})
        
        try:
            from PIL import Image
            
            # Load and normalize images
            with Image.open(path1) as img1, Image.open(path2) as img2:
                img1 = img1.convert('RGB').resize((64, 64))
                img2 = img2.convert('RGB').resize((64, 64))
                
                # Get pixel data
                pixels1 = list(img1.getdata())
                pixels2 = list(img2.getdata())
                
                # Calculate color distance
                total_diff = 0
                for p1, p2 in zip(pixels1, pixels2):
                    diff = sum(abs(a - b) for a, b in zip(p1, p2))
                    total_diff += diff
                
                max_diff = 64 * 64 * 3 * 255  # Maximum possible difference
                similarity = 1 - (total_diff / max_diff)
                
                # Compare color palettes
                colors1 = _extract_dominant_colors(path1, k=3)
                colors2 = _extract_dominant_colors(path2, k=3)
                
                return json.dumps({
                    "ok": True,
                    "similarity": round(similarity, 3),
                    "similar": similarity > 0.8,
                    "path1": path1,
                    "path2": path2,
                    "colors1": colors1,
                    "colors2": colors2,
                }, indent=2)
                
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    print("[VisionTools] Registered LOCAL tools: view_image, get_image_data, extract_image_traits, list_images, compare_images")


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE FUNCTIONS (for direct import)
# ═══════════════════════════════════════════════════════════════════════════════

def view_image_local(path: str) -> dict:
    """View an image locally (standalone function)."""
    img_path = Path(path)
    
    if not img_path.exists():
        return {"error": f"Not found: {path}"}
    
    result = {
        "path": str(img_path),
        "filename": img_path.name,
    }
    
    # Hash
    try:
        with open(img_path, 'rb') as f:
            result["hash"] = hashlib.sha256(f.read()).hexdigest()[:16]
    except:
        pass
    
    # Dimensions
    try:
        from PIL import Image
        with Image.open(img_path) as img:
            result["width"] = img.width
            result["height"] = img.height
    except:
        pass
    
    # Colors
    result["colors"] = _extract_dominant_colors(path)
    result["color_names"] = [_color_name(c) for c in result["colors"] if not c.startswith("error")]
    
    # Type
    type_info = _detect_image_type(path)
    result["detected_type"] = type_info.get("detected_type", "unknown")
    
    return result


# Test if run directly
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"Testing view_image_local on: {path}")
        result = view_image_local(path)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python vision_tools.py <image_path>")
        print("\nThis module provides LOCAL image analysis - no external APIs.")
