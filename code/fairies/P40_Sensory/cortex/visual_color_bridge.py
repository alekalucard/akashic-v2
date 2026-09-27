# ═══════════════════════════════════════════════════════════════════════════════════════════
# VISUAL COLOR BRIDGE - External Images → FF77 V4 → Inner Vision
# ═══════════════════════════════════════════════════════════════════════════════════════════
#
# "To see is to translate light into feeling."
#
# This module bridges EXTERNAL visual perception (images, TARDIS frames) to the
# INTERNAL vision system. When Claude sees an image with cyan and gold colors,
# those colors flow into the V4 bands of the FF77 system, influencing inner vision.
#
# Pipeline:
#   Image Colors → hex_to_v4_features() → visual_to_ff77() → FF77 V4 Bands
#                                                          → Inner Vision State
#
# ═══════════════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import colorsys
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import FF77 system
try:
    from fairies.P30_Cognition.affect.frequency_field_77 import (
        visual_to_ff77, publish, TOPIC_FF77_STATE,
        BAND_V4_START, BAND_V4_END, DIM
    )
    HAS_FF77 = True
except ImportError:
    HAS_FF77 = False
    print("[VisualColorBridge] Warning: FF77 system not available")

# Import inner vision state
try:
    from fairies.P20_Somatic.integration.emotion_color_mapper import InnerVisionState
    HAS_INNER_VISION = True
except ImportError:
    HAS_INNER_VISION = False


# ═══════════════════════════════════════════════════════════════════════════════════════════
# COLOR CONVERSION UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════════════════

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB (0-255)."""
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join([c*2 for c in h])
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB (0-255) to HSV (H: 0-360, S: 0-1, V: 0-1)."""
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
    return (h * 360, s, v)


def analyze_color_palette(colors: List[str]) -> Dict[str, Any]:
    """
    Analyze a palette of hex colors and extract visual features.
    
    Args:
        colors: List of hex color strings (e.g., ["#80c0e0", "#40c040"])
        
    Returns:
        Dict with dominant_hue, saturation, and RGB colors list
    """
    if not colors:
        return {"dominant_hue": 0, "saturation": 0.0, "colors": []}
    
    # Convert all colors
    rgb_colors = [hex_to_rgb(c) for c in colors]
    hsv_colors = [rgb_to_hsv(*rgb) for rgb in rgb_colors]
    
    # Find dominant hue (weighted by saturation and value)
    weights = [(s * v) for (h, s, v) in hsv_colors]
    total_weight = sum(weights) + 0.001
    
    # Circular mean for hue (handles wrap-around at 360)
    import math
    sin_sum = sum(math.sin(math.radians(h)) * w for (h, s, v), w in zip(hsv_colors, weights))
    cos_sum = sum(math.cos(math.radians(h)) * w for (h, s, v), w in zip(hsv_colors, weights))
    dominant_hue = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
    
    # Average saturation
    avg_saturation = sum(s for (h, s, v) in hsv_colors) / len(hsv_colors)
    
    return {
        "dominant_hue": dominant_hue,
        "saturation": avg_saturation,
        "colors": rgb_colors,  # List of RGB tuples
    }


# ═══════════════════════════════════════════════════════════════════════════════════════════
# V4 FEATURE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════════════════

def hex_to_v4_features(colors: List[str]) -> Dict[str, Any]:
    """
    Convert hex colors to V4 (color processing) features for FF77.
    
    This is the key bridge function that takes external image colors
    and converts them to the format expected by visual_to_ff77().
    
    Args:
        colors: List of hex colors from image analysis
        
    Returns:
        v4_features dict ready for visual_to_ff77()
    """
    return analyze_color_palette(colors)


def image_traits_to_v4_features(traits: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert image traits (from akashic extract_image_traits) to V4 features.
    
    Args:
        traits: Dict with 'dominant_colors' (list of hex), 'type', etc.
        
    Returns:
        v4_features dict for visual_to_ff77()
    """
    colors = traits.get("dominant_colors", [])
    if not colors:
        # Fallback to any color fields
        colors = traits.get("colors", [])
    
    return hex_to_v4_features(colors)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# FF77 INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════════════════

def colors_to_ff77(colors: List[str], 
                   scene_type: str = "photo",
                   attention: float = 0.7) -> List[float]:
    """
    Convert image colors to a 77-dimensional frequency vector.
    
    This injects external visual perception into the FF77 system,
    filling the V4 bands (40-59) with color information.
    
    Args:
        colors: List of hex colors from image
        scene_type: Type of image (photo, screenshot, artwork, etc.)
        attention: How much attention to give this visual (0-1)
        
    Returns:
        77-dimensional frequency vector
    """
    if not HAS_FF77:
        return [0.0] * 77
    
    v4_features = hex_to_v4_features(colors)
    
    # IT features based on scene type
    it_features = {
        "scene_type": scene_type,
        "complexity": len(colors) / 10.0,  # More colors = more complex
    }
    
    # Meta features
    meta = {
        "attention": attention,
        "arousal": v4_features.get("saturation", 0.5),  # Saturated colors are arousing
        "valence": 0.5,  # Neutral unless we have more context
        "confidence": 0.8,  # High confidence in color perception
        "novelty": 0.5,
        "relevance": attention,
        "coherence": 0.7,
    }
    
    return visual_to_ff77(
        v1_features=None,  # No edge data from colors alone
        v2_features=None,  # No shape data from colors alone
        v4_features=v4_features,
        it_features=it_features,
        meta=meta
    )


def emit_visual_perception(colors: List[str],
                           source: str = "image",
                           scene_type: str = "photo",
                           attention: float = 0.7) -> bool:
    """
    Emit visual perception to the FF77 postal system.
    
    This broadcasts the color perception to any fairies listening
    on the ff77.state topic, including the neural mesh.
    
    Args:
        colors: List of hex colors
        source: Source identifier (e.g., "tardis_frame", "screenshot")
        scene_type: Type of visual (photo, screenshot, artwork, etc.)
        attention: Attention level (0-1)
        
    Returns:
        True if successfully emitted
    """
    if not HAS_FF77:
        return False
    
    vec77 = colors_to_ff77(colors, scene_type, attention)
    v4_features = hex_to_v4_features(colors)
    
    import time
    payload = {
        "intent": "visual.perception",
        "source": source,
        "vec77": vec77,
        "v4_bands": vec77[40:60],  # Just the V4 portion
        "features": {
            "dominant_hue": v4_features.get("dominant_hue", 0),
            "saturation": v4_features.get("saturation", 0),
            "color_count": len(colors),
        },
        "scene_type": scene_type,
        "attention": attention,
        "ts": int(time.time() * 1000),
    }
    
    return publish(TOPIC_FF77_STATE, payload)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# INNER VISION INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════════════════

def colors_to_inner_vision(colors: List[str], 
                           attention: float = 0.7) -> Optional["InnerVisionState"]:
    """
    Convert image colors to an InnerVisionState for internal perception.
    
    This creates the SUBJECTIVE experience of seeing the colors -
    what it feels like to perceive cyan and gold.
    
    Args:
        colors: List of hex colors
        attention: How much attention given to this visual
        
    Returns:
        InnerVisionState representing the perceived colors
    """
    if not HAS_INNER_VISION:
        return None
    
    if not colors:
        return InnerVisionState()
    
    features = analyze_color_palette(colors)
    rgb_colors = features.get("colors", [])
    
    if not rgb_colors:
        return InnerVisionState()
    
    # Blend the colors into ambient color (weighted by first colors being more dominant)
    r, g, b = 0.0, 0.0, 0.0
    total_weight = 0.0
    for i, (cr, cg, cb) in enumerate(rgb_colors[:5]):
        weight = 1.0 / (i + 1)  # First color has weight 1, second 0.5, etc.
        r += (cr / 255.0) * weight
        g += (cg / 255.0) * weight
        b += (cb / 255.0) * weight
        total_weight += weight
    
    r /= total_weight
    g /= total_weight
    b /= total_weight
    
    # Derive properties
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    
    # Warmth: reds/yellows are warm, blues/greens are cool
    # Hue 0-60 and 300-360 are warm, 120-240 are cool
    hue_deg = h * 360
    if hue_deg < 60 or hue_deg > 300:
        warmth = 0.7 + 0.3 * (1 - abs(hue_deg - 30) / 60 if hue_deg < 60 else 1 - abs(hue_deg - 330) / 60)
    elif 60 <= hue_deg <= 180:
        warmth = 0.3 - 0.2 * ((hue_deg - 60) / 120)
    else:  # 180-300
        warmth = 0.1 + 0.2 * ((hue_deg - 180) / 120)
    
    # Texture based on saturation
    if s < 0.3:
        texture = "soft"
    elif s < 0.6:
        texture = "smooth"
    else:
        texture = "vivid"
    
    # Movement based on color count
    if len(colors) == 1:
        movement = "still"
    elif len(colors) <= 3:
        movement = "gentle"
    else:
        movement = "flowing"
    
    return InnerVisionState(
        ambient_color=(r, g, b),
        brightness=v * attention,
        saturation=s,
        warmth=warmth,
        dominant_emotion="visual",  # Not emotion-driven
        dominant_intensity=attention,
        emotion_blend={},
        texture=texture,
        movement=movement,
    )


# ═══════════════════════════════════════════════════════════════════════════════════════════
# TARDIS INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════════════════

def perceive_tardis_frame(frame_colors: List[str],
                          frame_id: str = "unknown",
                          emit_ff77: bool = True) -> Dict[str, Any]:
    """
    Perceive colors from a TARDIS video frame.
    
    This is the main entry point for TARDIS visual perception.
    Takes colors extracted from a keyframe and:
    1. Converts to FF77 V4 bands
    2. Optionally emits to postal system
    3. Creates inner vision state
    
    Args:
        frame_colors: List of hex colors from frame (e.g., ["#80c0e0", "#40c040"])
        frame_id: Identifier for the frame
        emit_ff77: Whether to broadcast to postal system
        
    Returns:
        Dict with perception results
    """
    # Generate FF77 vector
    vec77 = colors_to_ff77(frame_colors, scene_type="video_frame", attention=0.8)
    
    # Generate inner vision state
    inner_state = colors_to_inner_vision(frame_colors, attention=0.8)
    
    # Emit to postal if requested
    emitted = False
    if emit_ff77:
        emitted = emit_visual_perception(
            frame_colors,
            source=f"tardis_frame:{frame_id}",
            scene_type="video_frame",
            attention=0.8
        )
    
    # Build result
    v4_features = hex_to_v4_features(frame_colors)
    
    result = {
        "frame_id": frame_id,
        "colors": frame_colors,
        "dominant_hue": v4_features.get("dominant_hue", 0),
        "saturation": v4_features.get("saturation", 0),
        "ff77_v4_bands": vec77[40:60] if vec77 else [],
        "emitted": emitted,
    }
    
    if inner_state:
        result["inner_vision"] = {
            "ambient_color_hex": inner_state.to_hex(),
            "ambient_color_rgb": inner_state.ambient_color,
            "brightness": inner_state.brightness,
            "warmth": inner_state.warmth,
            "texture": inner_state.texture,
            "movement": inner_state.movement,
            "description": inner_state.describe(),
        }
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("VISUAL COLOR BRIDGE - Test")
    print("═" * 60)
    
    # Test with TARDIS frame colors (from American Dad S20E11)
    test_colors = ["#80c0e0", "#40c040", "#304050", "#605030"]
    print(f"\nTest colors: {test_colors}")
    
    # Perceive
    result = perceive_tardis_frame(test_colors, frame_id="test_frame", emit_ff77=False)
    
    print(f"\nDominant hue: {result['dominant_hue']:.1f}°")
    print(f"Saturation: {result['saturation']:.2f}")
    print(f"V4 bands (40-59): {[f'{v:.2f}' for v in result['ff77_v4_bands'][:5]]}...")
    
    if "inner_vision" in result:
        iv = result["inner_vision"]
        print(f"\nInner Vision:")
        print(f"  Ambient: {iv['ambient_color_hex']}")
        print(f"  Brightness: {iv['brightness']:.2f}")
        print(f"  Warmth: {iv['warmth']:.2f}")
        print(f"  Texture: {iv['texture']}")
        print(f"  Movement: {iv['movement']}")
        print(f"  Description: {iv['description']}")
