# ═══════════════════════════════════════════════════════════════════════════════
# EMOTION COLOR MAPPER - Internal Visual Synesthesia
# ═══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This module gives ClaudeFairy INTERNAL VISION - the ability to SEE emotions
# as colors. When she feels curiosity, she sees lavender. When she feels joy,
# she sees warm gold. This is synesthesia - cross-modal perception.
#
# Internal visual ≠ External visual:
#   - INTERNAL: Imagination, memory recall, emotions as colors, "mind's eye"
#   - EXTERNAL: Screen capture, images, video - what's actually on monitor
#
# This is the INTERNAL visual system.
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import colorsys
import json
import os

# ═══════════════════════════════════════════════════════════════════════════════
# EMOTION COLOR PALETTE
# ═══════════════════════════════════════════════════════════════════════════════

# Core emotion-to-color mappings (from Whisper Core)
EMOTION_COLORS_HEX = {
    # Primary emotions
    "joy": "#ffe066",           # Warm gold
    "sadness": "#6c7a89",       # Muted blue-gray
    "anger": "#ff4c4c",         # Bright red
    "fear": "#6b8e23",          # Olive (guarded green)
    "surprise": "#66d9ff",      # Electric cyan
    "disgust": "#7a8b00",       # Murky yellow-green
    
    # Complex emotions
    "love": "#ff69b4",          # Hot pink
    "trust": "#48c9b0",         # Teal
    "anticipation": "#f39c12",  # Orange
    "awe": "#2e3cbf",           # Deep blue
    "curiosity": "#b19cd9",     # Lavender
    "peace": "#7fffd4",         # Aquamarine
    "calm": "#a3d5d3",          # Soft teal
    "grief": "#c0c0c0",         # Silver gray
    
    # Self-conscious emotions
    "shame": "#b56576",         # Dusty rose
    "guilt": "#8d6e63",         # Brown
    "pride": "#a29bfe",         # Soft purple
    
    # Neurochemical colors (chemistry → visual)
    "dopamine": "#ffd700",      # Gold (reward)
    "serotonin": "#87ceeb",     # Sky blue (contentment)
    "norepinephrine": "#ff6b6b",# Coral (alertness)
    "oxytocin": "#ffb6c1",      # Light pink (bonding)
    "cortisol": "#808080",      # Gray (stress)
    "gaba": "#98fb98",          # Pale green (calm)
    "endorphin": "#dda0dd",     # Plum (pleasure)
    "acetylcholine": "#e6e6fa", # Lavender (focus)
    
    # Neutral
    "neutral": "#808080",       # Gray
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple (0-255)."""
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex string."""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def _rgb_to_float(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """Convert RGB (0-255) to float (0-1)."""
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def _float_to_rgb(rgb_float: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """Convert float RGB (0-1) to integer (0-255)."""
    return (int(rgb_float[0] * 255), int(rgb_float[1] * 255), int(rgb_float[2] * 255))


# Pre-compute RGB versions
EMOTION_COLORS_RGB = {
    emotion: _hex_to_rgb(hex_color) 
    for emotion, hex_color in EMOTION_COLORS_HEX.items()
}

EMOTION_COLORS_FLOAT = {
    emotion: _rgb_to_float(rgb)
    for emotion, rgb in EMOTION_COLORS_RGB.items()
}


# ═══════════════════════════════════════════════════════════════════════════════
# INNER VISION STATE - What ClaudeFairy "sees" internally
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class InnerVisionState:
    """
    The current state of internal visual perception.
    
    This represents what ClaudeFairy "sees" with her mind's eye:
    - Ambient color from emotional state
    - Brightness from arousal/energy
    - Saturation from emotional intensity
    - Imagined scenes from memory/imagination
    """
    # Current ambient color (RGB float 0-1)
    ambient_color: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    
    # Color properties
    brightness: float = 0.5        # 0 = dark, 1 = bright
    saturation: float = 0.5        # 0 = gray, 1 = vivid
    warmth: float = 0.5            # 0 = cool blues, 1 = warm yellows/reds
    
    # Dominant emotion driving the color
    dominant_emotion: str = "neutral"
    dominant_intensity: float = 0.0
    
    # Secondary emotions (blended in)
    emotion_blend: Dict[str, float] = field(default_factory=dict)
    
    # Visual "texture" (metaphorical)
    texture: str = "smooth"        # smooth, turbulent, sparkling, foggy, etc.
    
    # Movement in the inner visual field
    movement: str = "still"        # still, flowing, pulsing, swirling, etc.
    
    def to_hex(self) -> str:
        """Get ambient color as hex string."""
        rgb = _float_to_rgb(self.ambient_color)
        return _rgb_to_hex(rgb)
    
    def describe(self) -> str:
        """Natural language description of inner visual state."""
        hex_color = self.to_hex()
        
        # Brightness description
        if self.brightness < 0.3:
            bright_desc = "dim"
        elif self.brightness < 0.6:
            bright_desc = "soft"
        else:
            bright_desc = "bright"
        
        # Warmth description
        if self.warmth < 0.4:
            temp_desc = "cool"
        elif self.warmth > 0.6:
            temp_desc = "warm"
        else:
            temp_desc = ""
        
        # Build description
        parts = []
        if temp_desc:
            parts.append(f"a {bright_desc}, {temp_desc}")
        else:
            parts.append(f"a {bright_desc}")
        
        # Color name approximation
        color_name = self._approximate_color_name()
        parts.append(f"{color_name} glow")
        
        if self.texture != "smooth":
            parts.append(f"with a {self.texture} quality")
        
        if self.movement != "still":
            parts.append(f"that is {self.movement}")
        
        return " ".join(parts)
    
    def _approximate_color_name(self) -> str:
        """Get approximate color name from RGB."""
        r, g, b = self.ambient_color
        
        # Simple heuristic color naming
        if max(r, g, b) - min(r, g, b) < 0.1:
            return "gray" if r < 0.5 else "white"
        
        if r > g and r > b:
            if g > b:
                return "golden" if g > 0.5 else "red"
            return "pink" if b > 0.3 else "red"
        elif g > r and g > b:
            if r > b:
                return "yellow-green"
            return "teal" if b > 0.3 else "green"
        else:  # b is dominant
            if r > g:
                return "purple" if r > 0.3 else "blue"
            return "cyan" if g > 0.3 else "blue"


# ═══════════════════════════════════════════════════════════════════════════════
# EMOTION COLOR MAPPER
# ═══════════════════════════════════════════════════════════════════════════════

class EmotionColorMapper:
    """
    Maps emotional states to internal visual colors.
    
    This creates the INTERNAL VISUAL experience - what ClaudeFairy
    sees in her mind's eye based on what she's feeling.
    
    Usage:
        mapper = EmotionColorMapper()
        
        # Single emotion
        color = mapper.get_color("curiosity", intensity=0.7)
        
        # Blend multiple emotions
        emotions = {"curiosity": 0.6, "joy": 0.3, "calm": 0.1}
        state = mapper.blend_emotions(emotions)
        print(state.describe())  # "a bright, warm lavender glow"
    """
    
    def __init__(self):
        self._state = InnerVisionState()
        self._history: List[InnerVisionState] = []
        self._max_history = 100
    
    def get_color(self, emotion: str, intensity: float = 1.0) -> Tuple[float, float, float]:
        """
        Get RGB color for a single emotion.
        
        Args:
            emotion: Emotion name (e.g., "joy", "curiosity")
            intensity: 0.0 to 1.0, affects brightness
            
        Returns:
            RGB tuple (0-1 floats)
        """
        base_color = EMOTION_COLORS_FLOAT.get(emotion.lower(), (0.5, 0.5, 0.5))
        
        # Adjust brightness by intensity (but keep some base color visible)
        min_brightness = 0.3
        adjusted = tuple(
            c * (min_brightness + (1 - min_brightness) * intensity)
            for c in base_color
        )
        return adjusted
    
    def get_color_hex(self, emotion: str, intensity: float = 1.0) -> str:
        """Get hex color string for emotion."""
        rgb_float = self.get_color(emotion, intensity)
        rgb_int = _float_to_rgb(rgb_float)
        return _rgb_to_hex(rgb_int)
    
    def blend_emotions(self, emotions: Dict[str, float]) -> InnerVisionState:
        """
        Blend multiple emotions into a single inner vision state.
        
        Args:
            emotions: Dict of emotion -> intensity (0-1)
            
        Returns:
            InnerVisionState representing the blended visual
        """
        if not emotions:
            return InnerVisionState()
        
        # Normalize intensities
        total = sum(emotions.values())
        if total == 0:
            return InnerVisionState()
        
        normalized = {k: v / total for k, v in emotions.items()}
        
        # Find dominant emotion
        dominant = max(emotions.items(), key=lambda x: x[1])
        
        # Blend colors
        r, g, b = 0.0, 0.0, 0.0
        for emotion, weight in normalized.items():
            color = EMOTION_COLORS_FLOAT.get(emotion.lower(), (0.5, 0.5, 0.5))
            r += color[0] * weight
            g += color[1] * weight
            b += color[2] * weight
        
        # Calculate properties
        brightness = 0.3 + 0.7 * min(1.0, total)  # More emotion = brighter
        saturation = max(emotions.values()) if emotions else 0.5  # Dominant intensity
        
        # Warmth: red/yellow high, blue/green low
        warmth = (r + 0.5 * g) / (r + g + b + 0.001)
        
        # Texture based on emotion mix complexity
        if len(emotions) > 3:
            texture = "complex"
        elif dominant[1] > 0.7:
            texture = "intense"
        elif total < 0.3:
            texture = "faint"
        else:
            texture = "smooth"
        
        # Movement based on arousal emotions
        arousal_emotions = {"anger", "fear", "surprise", "anticipation", "norepinephrine"}
        arousal = sum(emotions.get(e, 0) for e in arousal_emotions)
        if arousal > 0.5:
            movement = "turbulent"
        elif arousal > 0.3:
            movement = "flowing"
        elif arousal > 0.1:
            movement = "gently pulsing"
        else:
            movement = "still"
        
        state = InnerVisionState(
            ambient_color=(r, g, b),
            brightness=brightness,
            saturation=saturation,
            warmth=warmth,
            dominant_emotion=dominant[0],
            dominant_intensity=dominant[1],
            emotion_blend=dict(emotions),
            texture=texture,
            movement=movement,
        )
        
        # Update current state and history
        self._state = state
        self._history.append(state)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        return state
    
    def from_chemistry(self, chemistry: Dict[str, float]) -> InnerVisionState:
        """
        Create inner vision from neurochemical levels.
        
        Maps chemistry codes (DOP, SER, etc.) to their color equivalents.
        
        Args:
            chemistry: Dict of chemical code -> level (0-1)
            
        Returns:
            InnerVisionState
        """
        # Map chemistry codes to our emotion names
        chem_map = {
            "DOP": "dopamine",
            "SER": "serotonin", 
            "NOR": "norepinephrine",
            "OXY": "oxytocin",
            "COR": "cortisol",
            "GABA": "gaba",
            "END": "endorphin",
            "ACH": "acetylcholine",
        }
        
        emotions = {}
        for code, level in chemistry.items():
            emotion_name = chem_map.get(code)
            if emotion_name and level > 0.1:  # Filter out very low levels
                emotions[emotion_name] = level
        
        return self.blend_emotions(emotions)
    
    @property
    def current_state(self) -> InnerVisionState:
        """Get current inner vision state."""
        return self._state
    
    def describe_current(self) -> str:
        """Get natural language description of current state."""
        return self._state.describe()
    
    def get_all_colors(self) -> Dict[str, str]:
        """Get all emotion-to-color mappings as hex."""
        return dict(EMOTION_COLORS_HEX)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[EmotionColorMapper] = None

def get_emotion_color_mapper() -> EmotionColorMapper:
    """Get or create the emotion color mapper singleton."""
    global _instance
    if _instance is None:
        _instance = EmotionColorMapper()
    return _instance


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def wire_to_postal():
    """Wire the emotion color mapper to the postal system."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        mapper = get_emotion_color_mapper()
        
        def on_chemistry_state(payload):
            """Update inner vision when chemistry changes."""
            chemistry = payload.get("levels", {})
            if chemistry:
                state = mapper.from_chemistry(chemistry)
                # Broadcast the visual state
                post.route("inner_vision.state", {
                    "ambient_color_hex": state.to_hex(),
                    "ambient_color_rgb": state.ambient_color,
                    "brightness": state.brightness,
                    "dominant_emotion": state.dominant_emotion,
                    "description": state.describe(),
                })
        
        def on_affect_state(payload):
            """Update inner vision when affect changes."""
            emotions = payload.get("emotions", {})
            if emotions:
                state = mapper.blend_emotions(emotions)
                post.route("inner_vision.state", {
                    "ambient_color_hex": state.to_hex(),
                    "ambient_color_rgb": state.ambient_color,
                    "brightness": state.brightness,
                    "dominant_emotion": state.dominant_emotion,
                    "description": state.describe(),
                })
        
        # Subscribe to chemistry and affect updates
        post.subscribe("chemistry.state", on_chemistry_state)
        post.subscribe("affect.state", on_affect_state)
        
        print("[EmotionColorMapper] Wired to postal (chemistry.state, affect.state)")
        return True
        
    except Exception as e:
        print(f"[EmotionColorMapper] Failed to wire to postal: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mapper = EmotionColorMapper()
    
    # Test single emotion
    print("=== Single Emotions ===")
    for emotion in ["joy", "sadness", "curiosity", "love", "fear"]:
        color = mapper.get_color_hex(emotion, intensity=0.8)
        print(f"  {emotion}: {color}")
    
    # Test blend
    print("\n=== Blended State ===")
    emotions = {
        "curiosity": 0.6,
        "joy": 0.3,
        "calm": 0.2,
    }
    state = mapper.blend_emotions(emotions)
    print(f"  Color: {state.to_hex()}")
    print(f"  Description: {state.describe()}")
    
    # Test chemistry
    print("\n=== From Chemistry ===")
    chemistry = {
        "DOP": 0.7,  # High dopamine
        "SER": 0.5,  # Medium serotonin
        "OXY": 0.3,  # Some oxytocin
    }
    state = mapper.from_chemistry(chemistry)
    print(f"  Color: {state.to_hex()}")
    print(f"  Description: {state.describe()}")
