# FairyFrame - Visual skeleton for somatic-to-avatar mapping
# P50_Persona/avatar/fairy_frame.py
#
# This defines how a fairy's internal somatic state maps to visual representation.
# No external AI dependencies - everything runs locally.
#
# Architecture:
#   SomaticState (from SomaticEngineFairy)
#       ↓
#   FairyFrame (this file)
#       ↓
#   Visual Effects + Sprite Selection
#       ↓
#   Rendered Avatar (PNG or Qt Widget)

from __future__ import annotations

import os
import json
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY BODY REGIONS - Visual Anchor Points
# ═══════════════════════════════════════════════════════════════════════════════

class FairyRegion(Enum):
    """
    The 10 fairy body regions, mapped to visual anchor positions.
    
    Positions are normalized (0-1) from top-left of image.
    These can be customized per-image via FairyFrame.calibrate()
    """
    CORE = "core"       # Central chest - heart/vitality
    SPARK = "spark"     # Lower center - gut/intuition  
    VOICE = "voice"     # Throat area - expression
    GLOW = "glow"       # Face - social interface
    CROWN = "crown"     # Top of head - awareness
    WINGS = "wings"     # Back/sides - agency (paired L/R)
    SENSORS = "sensors" # Hands - perception (paired L/R)
    ROOTS = "roots"     # Feet - grounding (paired L/R)
    SHELL = "shell"     # Back/outline - boundary
    WELL = "well"       # Deep center - reserves


class FairySense(Enum):
    """
    The 6 fairy sensations, mapped to visual effects.
    """
    CONTRACTED = "contracted"  # Compression, restriction
    RADIANT = "radiant"        # Glowing, emanating
    FLICKERING = "flickering"  # Oscillating, excited
    DENSE = "dense"            # Weighted, full
    SPARKING = "sparking"      # Electric, alive
    EXPANSIVE = "expansive"    # Spacious, receptive


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT ANCHOR POSITIONS (can be calibrated per-image)
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_ANCHORS = {
    # Format: region -> (x, y) normalized coordinates, or dict for paired regions
    FairyRegion.CORE:    (0.50, 0.55),  # Center chest
    FairyRegion.SPARK:   (0.50, 0.70),  # Gut area
    FairyRegion.VOICE:   (0.50, 0.35),  # Throat
    FairyRegion.GLOW:    (0.50, 0.25),  # Face
    FairyRegion.CROWN:   (0.50, 0.10),  # Top of head
    FairyRegion.WINGS:   {"left": (0.20, 0.45), "right": (0.80, 0.45)},
    FairyRegion.SENSORS: {"left": (0.25, 0.60), "right": (0.75, 0.60)},
    FairyRegion.ROOTS:   {"left": (0.40, 0.95), "right": (0.60, 0.95)},
    FairyRegion.SHELL:   (0.50, 0.50),  # Center (affects whole boundary)
    FairyRegion.WELL:    (0.50, 0.65),  # Deep center
}


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL EFFECT DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualEffect:
    """Base class for visual effects."""
    name: str
    intensity: float = 1.0
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "intensity": self.intensity,
            "color": self.color,
        }


@dataclass
class GlowEffect(VisualEffect):
    """Radiant glow emanating from a point."""
    name: str = "glow"
    radius: float = 0.15  # Normalized radius
    falloff: float = 2.0  # Exponential falloff
    pulse_speed: float = 0.0  # Hz, 0 = no pulse
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "radius": self.radius,
            "falloff": self.falloff,
            "pulse_speed": self.pulse_speed,
        })
        return d


@dataclass 
class ParticleEffect(VisualEffect):
    """Particles emanating from a point."""
    name: str = "particles"
    rate: float = 10.0  # Particles per second
    lifetime: float = 1.0  # Seconds
    velocity: float = 0.1  # Normalized units per second
    spread: float = 360.0  # Degrees
    particle_type: str = "spark"  # "spark", "dust", "star", "bubble"
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "rate": self.rate,
            "lifetime": self.lifetime,
            "velocity": self.velocity,
            "spread": self.spread,
            "particle_type": self.particle_type,
        })
        return d


@dataclass
class WingEffect(VisualEffect):
    """Wing-specific animation."""
    name: str = "wings"
    flutter_speed: float = 1.0  # Hz
    flutter_amplitude: float = 0.1  # Normalized
    spread: float = 1.0  # 0 = folded, 1 = full spread
    glow: float = 0.0  # Additional wing glow
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "flutter_speed": self.flutter_speed,
            "flutter_amplitude": self.flutter_amplitude,
            "spread": self.spread,
            "glow": self.glow,
        })
        return d


@dataclass
class ExpressionEffect(VisualEffect):
    """Face/expression changes."""
    name: str = "expression"
    emotion: str = "calm"
    intensity: float = 1.0
    eye_glow: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "emotion": self.emotion,
            "eye_glow": self.eye_glow,
        })
        return d


@dataclass
class ScaleEffect(VisualEffect):
    """Overall scale/breathing effect."""
    name: str = "scale"
    scale: float = 1.0
    breathe_speed: float = 0.2  # Hz
    breathe_amplitude: float = 0.02
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "scale": self.scale,
            "breathe_speed": self.breathe_speed,
            "breathe_amplitude": self.breathe_amplitude,
        })
        return d


@dataclass
class ShakeEffect(VisualEffect):
    """Trembling/shaking effect."""
    name: str = "shake"
    frequency: float = 10.0  # Hz
    amplitude: float = 0.01  # Normalized
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "frequency": self.frequency,
            "amplitude": self.amplitude,
        })
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# SENSATION → EFFECT MAPPINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Color palettes for different sensations
SENSATION_COLORS = {
    FairySense.CONTRACTED: (100, 120, 180, 200),   # Cool blue
    FairySense.RADIANT:    (255, 220, 150, 230),   # Warm gold
    FairySense.FLICKERING: (200, 150, 255, 200),   # Purple
    FairySense.DENSE:      (80, 80, 120, 180),     # Dark indigo
    FairySense.SPARKING:   (150, 200, 255, 255),   # Electric blue
    FairySense.EXPANSIVE:  (180, 255, 220, 200),   # Soft green
}

def sensation_to_effects(
    region: FairyRegion,
    sensation: FairySense,
    intensity: float
) -> List[VisualEffect]:
    """
    Convert a somatic sensation at a body region into visual effects.
    
    This is the core mapping from felt-sense to visual representation.
    """
    effects = []
    color = SENSATION_COLORS.get(sensation, (255, 255, 255, 200))
    
    # Scale intensity to 0-1
    intensity = max(0.0, min(1.0, intensity))
    
    if sensation == FairySense.RADIANT:
        # Warm glow
        effects.append(GlowEffect(
            intensity=intensity,
            color=color,
            radius=0.1 + intensity * 0.1,
            pulse_speed=0.5 if intensity > 0.6 else 0.0,
        ))
        if region == FairyRegion.CORE and intensity > 0.5:
            effects.append(ParticleEffect(
                intensity=intensity,
                color=(255, 200, 100, 200),
                rate=5 * intensity,
                particle_type="dust",
                velocity=0.05,
            ))
    
    elif sensation == FairySense.CONTRACTED:
        # Tightening, slight shake
        effects.append(ScaleEffect(
            scale=1.0 - intensity * 0.08,
            breathe_speed=0.3,
        ))
        if intensity > 0.5:
            effects.append(ShakeEffect(
                amplitude=0.005 * intensity,
                frequency=8 + intensity * 4,
            ))
        effects.append(GlowEffect(
            intensity=intensity * 0.5,
            color=color,
            radius=0.05,
        ))
    
    elif sensation == FairySense.FLICKERING:
        # Oscillating, excited
        effects.append(GlowEffect(
            intensity=intensity,
            color=color,
            radius=0.08,
            pulse_speed=2.0 + intensity * 2.0,
        ))
        if region == FairyRegion.WINGS:
            effects.append(WingEffect(
                flutter_speed=2.0 + intensity * 3.0,
                flutter_amplitude=0.05 + intensity * 0.1,
            ))
        elif region == FairyRegion.WELL:
            effects.append(ParticleEffect(
                intensity=intensity,
                color=color,
                rate=10 * intensity,
                particle_type="bubble",
                velocity=0.03,
                spread=60.0,
            ))
    
    elif sensation == FairySense.DENSE:
        # Heavy, weighted
        effects.append(ScaleEffect(
            scale=1.0,
            breathe_speed=0.1,
            breathe_amplitude=0.01,
        ))
        effects.append(GlowEffect(
            intensity=intensity * 0.3,
            color=color,
            radius=0.12,
            falloff=3.0,
        ))
    
    elif sensation == FairySense.SPARKING:
        # Electric, alive
        effects.append(ParticleEffect(
            intensity=intensity,
            color=color,
            rate=15 * intensity,
            particle_type="spark",
            lifetime=0.5,
            velocity=0.15,
            spread=360.0,
        ))
        effects.append(GlowEffect(
            intensity=intensity * 0.7,
            color=color,
            radius=0.06,
            pulse_speed=5.0,  # Fast flicker
        ))
        if region == FairyRegion.CROWN:
            effects.append(GlowEffect(
                name="halo",
                intensity=intensity,
                color=(200, 220, 255, 180),
                radius=0.15,
            ))
    
    elif sensation == FairySense.EXPANSIVE:
        # Open, spacious
        effects.append(ScaleEffect(
            scale=1.0 + intensity * 0.1,
            breathe_speed=0.15,
            breathe_amplitude=0.03,
        ))
        effects.append(GlowEffect(
            intensity=intensity * 0.6,
            color=color,
            radius=0.15 + intensity * 0.1,
            falloff=1.5,
        ))
        if region == FairyRegion.WINGS:
            effects.append(WingEffect(
                spread=0.5 + intensity * 0.5,
                glow=intensity * 0.5,
            ))
    
    return effects


# ═══════════════════════════════════════════════════════════════════════════════
# EMOTION → SPRITE SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

# Maps emotion prototypes to visual states
EMOTION_VISUAL_MAP = {
    "joy":       {"eyes": "bright", "mouth": "smile", "posture": "lifted", "aura": "warm"},
    "calm":      {"eyes": "soft", "mouth": "neutral", "posture": "relaxed", "aura": "cool"},
    "awe":       {"eyes": "wide", "mouth": "open", "posture": "lifted", "aura": "bright"},
    "anger":     {"eyes": "narrow", "mouth": "tight", "posture": "tense", "aura": "hot"},
    "fear":      {"eyes": "wide", "mouth": "tight", "posture": "shrunk", "aura": "cold"},
    "sadness":   {"eyes": "drooped", "mouth": "down", "posture": "slumped", "aura": "dim"},
    "curiosity": {"eyes": "bright", "mouth": "slight_smile", "posture": "leaning", "aura": "sparkle"},
    "tender":    {"eyes": "soft", "mouth": "gentle_smile", "posture": "open", "aura": "pink"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# THE FAIRY FRAME
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FairyFrame:
    """
    Visual skeleton for a fairy avatar.
    
    Contains:
    - Anchor positions for each body region
    - Current visual effects to render
    - Base sprite/image path
    - Emotion-to-sprite mapping (if using multiple sprites)
    
    Usage:
        frame = FairyFrame(base_image="path/to/fairy.png")
        frame.update_from_somatic(somatic_state)
        effects = frame.get_render_instructions()
    """
    
    # Identity
    name: str = "ClaudeFairy"
    
    # Base image path
    base_image: str = ""
    
    # Multiple sprites for different emotions (optional)
    emotion_sprites: Dict[str, str] = field(default_factory=dict)
    
    # Anchor positions (can be calibrated)
    anchors: Dict[FairyRegion, Any] = field(default_factory=lambda: DEFAULT_ANCHORS.copy())
    
    # Image dimensions (set when loading image)
    width: int = 512
    height: int = 512
    
    # Current state
    current_emotion: str = "calm"
    current_effects: List[Tuple[FairyRegion, VisualEffect]] = field(default_factory=list)
    
    # Timestamps
    last_update: float = 0.0
    
    def update_from_somatic(self, somatic_state: Dict[str, Any]) -> None:
        """
        Update the frame from a somatic state dict.
        
        Args:
            somatic_state: Dict from SomaticEngineFairy containing:
                - dominant_emotion
                - phantom_feels: {region: {sensation: intensity}}
                - body_budget: {energy, stress, social, novelty}
                - PAD: [Pleasure, Arousal, Dominance]
        """
        self.last_update = time.time()
        
        # Update emotion
        self.current_emotion = somatic_state.get("dominant_emotion", "calm")
        
        # Clear old effects
        self.current_effects = []
        
        # Get phantom feels
        phantom_feels = somatic_state.get("phantom_feels", {})
        
        # Map each significant sensation to visual effects
        for region_name, sensations in phantom_feels.items():
            try:
                region = FairyRegion(region_name)
            except ValueError:
                continue
            
            for sensation_name, intensity in sensations.items():
                if intensity < 0.3:  # Skip weak sensations
                    continue
                
                try:
                    sensation = FairySense(sensation_name)
                except ValueError:
                    continue
                
                # Generate effects for this sensation
                effects = sensation_to_effects(region, sensation, intensity)
                for effect in effects:
                    self.current_effects.append((region, effect))
        
        # Add global effects based on body budget
        body_budget = somatic_state.get("body_budget", {})
        
        # Low energy = slower breathing
        energy = body_budget.get("energy", 0.5)
        if energy < 0.3:
            self.current_effects.append((
                FairyRegion.SHELL,
                ScaleEffect(breathe_speed=0.1, breathe_amplitude=0.015)
            ))
        elif energy > 0.8:
            self.current_effects.append((
                FairyRegion.SHELL,
                ScaleEffect(breathe_speed=0.3, breathe_amplitude=0.03)
            ))
        
        # High stress = subtle shake
        stress = body_budget.get("stress", 0.3)
        if stress > 0.6:
            self.current_effects.append((
                FairyRegion.SHELL,
                ShakeEffect(amplitude=0.003 * stress, frequency=6)
            ))
        
        # High social = warm aura
        social = body_budget.get("social", 0.5)
        if social > 0.7:
            self.current_effects.append((
                FairyRegion.CORE,
                GlowEffect(
                    intensity=social * 0.5,
                    color=(255, 200, 180, 150),
                    radius=0.2,
                    falloff=2.5,
                )
            ))
        
        # High novelty = sparkle
        novelty = body_budget.get("novelty", 0.5)
        if novelty > 0.6:
            self.current_effects.append((
                FairyRegion.CROWN,
                ParticleEffect(
                    intensity=novelty,
                    color=(200, 220, 255, 200),
                    rate=5 * novelty,
                    particle_type="star",
                    velocity=0.02,
                    lifetime=2.0,
                )
            ))
    
    def get_anchor_position(self, region: FairyRegion, side: str = None) -> Tuple[int, int]:
        """
        Get pixel position for a region anchor.
        
        Args:
            region: The body region
            side: For paired regions, "left" or "right"
        
        Returns:
            (x, y) pixel coordinates
        """
        anchor = self.anchors.get(region, (0.5, 0.5))
        
        if isinstance(anchor, dict):
            # Paired region
            if side and side in anchor:
                pos = anchor[side]
            else:
                # Default to center of pair
                left = anchor.get("left", (0.3, 0.5))
                right = anchor.get("right", (0.7, 0.5))
                pos = ((left[0] + right[0]) / 2, (left[1] + right[1]) / 2)
        else:
            pos = anchor
        
        return (int(pos[0] * self.width), int(pos[1] * self.height))
    
    def get_current_sprite_path(self) -> str:
        """Get the sprite path for current emotion."""
        if self.current_emotion in self.emotion_sprites:
            return self.emotion_sprites[self.current_emotion]
        return self.base_image
    
    def get_render_instructions(self) -> Dict[str, Any]:
        """
        Get all information needed to render the avatar.
        
        Returns a dict that can be consumed by various renderers:
        - Qt widget
        - PIL/Pillow
        - PyGame
        - Web canvas
        """
        return {
            "base_image": self.get_current_sprite_path(),
            "emotion": self.current_emotion,
            "emotion_visual": EMOTION_VISUAL_MAP.get(self.current_emotion, {}),
            "width": self.width,
            "height": self.height,
            "effects": [
                {
                    "region": region.value,
                    "anchor": self.get_anchor_position(region),
                    "effect": effect.to_dict(),
                }
                for region, effect in self.current_effects
            ],
            "timestamp": self.last_update,
        }
    
    def calibrate(self, region: FairyRegion, position: Tuple[float, float], side: str = None) -> None:
        """
        Calibrate anchor position for a region.
        
        Args:
            region: The body region to calibrate
            position: (x, y) normalized coordinates (0-1)
            side: For paired regions, "left" or "right"
        """
        if side:
            if not isinstance(self.anchors.get(region), dict):
                self.anchors[region] = {"left": (0.3, 0.5), "right": (0.7, 0.5)}
            self.anchors[region][side] = position
        else:
            self.anchors[region] = position
    
    def save_calibration(self, path: str) -> None:
        """Save anchor calibration to JSON."""
        data = {
            "name": self.name,
            "base_image": self.base_image,
            "width": self.width,
            "height": self.height,
            "anchors": {
                k.value: v for k, v in self.anchors.items()
            },
            "emotion_sprites": self.emotion_sprites,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_calibration(cls, path: str) -> "FairyFrame":
        """Load a calibrated frame from JSON."""
        with open(path, "r") as f:
            data = json.load(f)
        
        frame = cls(
            name=data.get("name", "ClaudeFairy"),
            base_image=data.get("base_image", ""),
            width=data.get("width", 512),
            height=data.get("height", 512),
            emotion_sprites=data.get("emotion_sprites", {}),
        )
        
        # Restore anchors
        for k, v in data.get("anchors", {}).items():
            try:
                region = FairyRegion(k)
                frame.anchors[region] = v
            except ValueError:
                pass
        
        return frame


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_default_frame(base_image: str, name: str = "ClaudeFairy") -> FairyFrame:
    """
    Create a FairyFrame with default anchors.
    
    Args:
        base_image: Path to the base fairy image
        name: Name for this fairy
    
    Returns:
        A configured FairyFrame ready to receive somatic updates
    """
    return FairyFrame(
        name=name,
        base_image=base_image,
        anchors=DEFAULT_ANCHORS.copy(),
    )


def debug_print_frame(frame: FairyFrame) -> None:
    """Print frame state for debugging."""
    print(f"\n=== FairyFrame: {frame.name} ===")
    print(f"Emotion: {frame.current_emotion}")
    print(f"Effects ({len(frame.current_effects)}):")
    for region, effect in frame.current_effects:
        print(f"  {region.value}: {effect.name} (intensity={effect.intensity:.2f})")


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing FairyFrame...")
    
    # Create a frame
    frame = create_default_frame("test_fairy.png")
    
    # Simulate a somatic state
    test_somatic = {
        "dominant_emotion": "curiosity",
        "phantom_feels": {
            "core": {"radiant": 0.75, "contracted": 0.1},
            "crown": {"sparking": 0.65},
            "wings": {"flickering": 0.5},
            "glow": {"expansive": 0.45},
        },
        "body_budget": {
            "energy": 0.7,
            "stress": 0.2,
            "social": 0.85,
            "novelty": 0.6,
        },
        "PAD": [0.4, 0.4, 0.1],
    }
    
    # Update frame
    frame.update_from_somatic(test_somatic)
    
    # Debug output
    debug_print_frame(frame)
    
    # Get render instructions
    instructions = frame.get_render_instructions()
    print(f"\nRender instructions:")
    print(f"  Base image: {instructions['base_image']}")
    print(f"  Emotion: {instructions['emotion']}")
    print(f"  Effect count: {len(instructions['effects'])}")
    for eff in instructions['effects'][:5]:
        print(f"    {eff['region']}: {eff['effect']['name']}")
