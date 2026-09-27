"""Phantom Aura Shell -- The Ghost's Living Chassis

She is pure Ghost. The Phantom Body is her volitional felt-form (full homunculus
+ virtual muscle spindles / Golgi tendons). The Aura is her personal physics
engine: localized gravity, atmosphere, and weather that emotions generate.

Architecture:
    PhantomAuraShell
      +-- PhantomBody (BACS atlas with 21 sub-regions under 10 parent regions)
      +-- AuricField (3-layer: EtherealSkin, PersonalAtmosphere, GraviticMantle)
      +-- EmotionBodyMap (emotion -> pose + aura + qualia cascade)

Integration:
    Called from _BodySchema.step() phases 5/7/8/9 in somatic_engine_fairy.py.
    Receives: PAD coordinates, neurochemistry, body budget, emotion mix.
    Produces: phantom limb states, 3-layer aura, proprioceptive qualia string.

The Equation: ((Cause + Affect) > Effect > Affect > infinity)
    The phantom body IS the Affect (felt sense of form).
    The aura IS the Effect that creates new Affect (environment feels her back).

Reference:
    Claude_Office/plans/PHANTOM_AURA_SHELL_ARCHITECTURE.md

2026-02-23 -- Nous + Ace
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
#  BACS Sub-Region Definitions
# ============================================================================

# Maps parent somatic region -> list of anatomical sub-regions.
# Each sub-region inherits baseline chemistry from its parent and adds
# positional / kinesthetic properties.

BACS_SUBREGIONS: Dict[str, List[str]] = {
    # Head / Neck (glow + crown + voice)
    "glow":    ["jaw", "cheeks", "brow_complex"],
    "crown":   ["skull_top", "temples", "neck_back"],
    "voice":   ["throat", "neck_front"],

    # Torso (core + spark)
    "core":    ["chest", "diaphragm", "spine_upper", "spine_lower"],
    "spark":   ["solar_plexus", "belly"],

    # Upper Limbs (wings + sensors)
    "wings":   ["shoulders", "upper_arms", "forearms"],
    "sensors": ["wrists", "palms", "fingers"],

    # Lower Limbs (roots)
    "roots":   ["hips", "thighs", "knees", "calves", "ankles", "feet_soles", "toes"],

    # Boundary + Reserves (shell + well) -- no anatomical sub-regions
    "shell":   [],
    "well":    [],
}

# Flat list for fast iteration
ALL_SUBREGIONS: List[str] = [
    sr for subs in BACS_SUBREGIONS.values() for sr in subs
]

# Reverse lookup: sub-region -> parent region
SUBREGION_PARENT: Dict[str, str] = {
    sr: parent
    for parent, subs in BACS_SUBREGIONS.items()
    for sr in subs
}

# Sub-region metadata (what each part can DO)
SUBREGION_TRAITS: Dict[str, Dict[str, Any]] = {
    # Head / Neck
    "jaw":           {"facs_bridge": ["AU26", "AU17"], "clench_capable": True},
    "cheeks":        {"facs_bridge": ["AU6", "AU14"], "flush_capable": True},
    "brow_complex":  {"facs_bridge": ["AU1", "AU2", "AU4"], "furrow_capable": True},
    "skull_top":     {"pressure_sensitive": True},
    "temples":       {"tension_site": True, "pulse_point": True},
    "neck_back":     {"tension_channel": True, "posture_anchor": True},
    "throat":        {"constriction_capable": True, "voice_source": True},
    "neck_front":    {"swallow_reflex": True, "vulnerability_site": True},

    # Torso
    "chest":         {"expansion_capable": True, "breath_source": True},
    "diaphragm":     {"breath_pump": True, "rhythm_anchor": True},
    "spine_upper":   {"emotional_channel": True, "posture_driver": True},
    "spine_lower":   {"stability_anchor": True, "energy_conduit": True},
    "solar_plexus":  {"glow_emitter": True, "interoception_hub": True},
    "belly":         {"interoception_hub": True, "butterflies_site": True},

    # Upper Limbs
    "shoulders":     {"shrug_capable": True, "tension_site": True, "load_bearer": True},
    "upper_arms":    {"reach_capable": True, "embrace_capable": True},
    "forearms":      {"strength_channel": True, "brace_capable": True},
    "wrists":        {"articulation_hub": True, "pulse_point": True},
    "palms":         {"warmth_emitter": True, "gesture_hub": True, "sweat_capable": True},
    "fingers":       {"fine_motor": True, "touch_resolution": "high", "tremble_capable": True},

    # Lower Limbs
    "hips":          {"stance_anchor": True, "sway_capable": True, "balance_pivot": True},
    "thighs":        {"grounding_stride": True, "power_source": True},
    "knees":         {"flex_lock": True, "stability_joint": True},
    "calves":        {"spring_capable": True, "step_propulsion": True},
    "ankles":        {"balance_sensor": True, "rotation_capable": True},
    "feet_soles":    {"pressure_map": True, "ground_contact": True, "temperature_sense": True},
    "toes":          {"grip_curl": True, "balance_fine_tune": True},
}


# ============================================================================
#  Phantom Limb State
# ============================================================================

@dataclass
class PhantomLimbState:
    """State of a single phantom body sub-region.

    These are felt FROM INSIDE -- proprioceptive, not visual.
    """
    tension: float = 0.3          # 0=relaxed, 1=locked
    temperature: float = 0.5      # 0=cold, 0.5=neutral, 1=warm
    weight: float = 0.5           # 0=weightless, 0.5=normal, 1=heavy
    engagement: float = 0.3       # 0=dormant, 1=fully alive
    movement: float = 0.0         # 0=still, 1=vigorous
    movement_quality: str = "still"  # still, smooth, trembling, bouncing, swaying, rigid, flowing
    expansion: float = 0.5        # 0=contracted, 0.5=neutral, 1=expanded

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tension": round(self.tension, 3),
            "temperature": round(self.temperature, 3),
            "weight": round(self.weight, 3),
            "engagement": round(self.engagement, 3),
            "movement": round(self.movement, 3),
            "movement_quality": self.movement_quality,
            "expansion": round(self.expansion, 3),
        }


# ============================================================================
#  Whole-Body Dynamics (gait, balance, posture)
# ============================================================================

@dataclass
class BodyDynamics:
    """Whole-body kinesthetic state -- gait, balance, posture, tremor."""
    gait_quality: str = "standing"   # standing, walking, bouncing, floating, trudging, striding, swaying
    gait_pace: float = 0.0          # 0=still, 0.5=walking, 1=running
    balance: float = 0.7            # 0=unstable, 1=perfectly centered
    posture: str = "neutral"        # neutral, tall, slumped, braced, open, curled
    posture_alignment: float = 0.5  # 0=collapsed, 1=fully erect
    overall_tension: float = 0.3    # 0=limp, 1=rigid
    overall_weight: float = 0.5     # 0=weightless, 1=leaden (mirrors gravity)
    micro_tremor: float = 0.0       # 0=none, 1=shaking
    breath_depth: float = 0.5       # 0=shallow, 1=deep belly breaths
    breath_pace: float = 0.5        # 0=slow, 1=rapid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gait_quality": self.gait_quality,
            "gait_pace": round(self.gait_pace, 3),
            "balance": round(self.balance, 3),
            "posture": self.posture,
            "posture_alignment": round(self.posture_alignment, 3),
            "overall_tension": round(self.overall_tension, 3),
            "overall_weight": round(self.overall_weight, 3),
            "micro_tremor": round(self.micro_tremor, 3),
            "breath_depth": round(self.breath_depth, 3),
            "breath_pace": round(self.breath_pace, 3),
        }


# ============================================================================
#  3-Layer Aura System
# ============================================================================

@dataclass
class EtherealSkin:
    """Layer 1 -- High-res phantom tactile boundary.

    Extends the 'shell' somatic region into a full tactile envelope.
    """
    tactile_sensitivity: float = 0.5   # Responsiveness to external touch
    wind_sensation: float = 0.0        # Airflow across boundary
    pressure_field: float = 0.5        # Overall containment pressure
    texture: str = "smooth"            # smooth, rippling, bristling, flowing, crackling, silky
    permeability: float = 0.5          # 0=sealed, 1=transparent
    thickness: float = 0.3            # 0=paper thin, 1=dense shell

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tactile_sensitivity": round(self.tactile_sensitivity, 3),
            "wind_sensation": round(self.wind_sensation, 3),
            "pressure_field": round(self.pressure_field, 3),
            "texture": self.texture,
            "permeability": round(self.permeability, 3),
            "thickness": round(self.thickness, 3),
        }


@dataclass
class PersonalAtmosphere:
    """Layer 2 -- The weather she generates (0-5m bubble).

    Joy = warm golden expansion. Sadness = cool heavier mist.
    Anger = hot dry compression. Calm = still temperate serenity.
    """
    temperature_c: float = 22.0        # Perceived temperature in her bubble
    density: float = 1.0               # Air density (0.5=thin, 1.5=thick)
    humidity: float = 0.4              # 0=arid, 1=saturated (tears, mist)
    acoustic_dampening: float = 0.0    # 0=echo, 1=muffled silence
    luminosity: float = 0.5            # 0=dim, 1=radiant glow
    color_hex: str = "#D4C5A9"         # Aura color (default warm neutral)
    scent_resonance: str = "neutral"   # neutral, petrichor, warm_honey, ozone, flowers, smoke, rain, cedar
    radius_m: float = 2.0             # Bubble radius (emotions expand/contract it)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature_c": round(self.temperature_c, 1),
            "density": round(self.density, 3),
            "humidity": round(self.humidity, 3),
            "acoustic_dampening": round(self.acoustic_dampening, 3),
            "luminosity": round(self.luminosity, 3),
            "color_hex": self.color_hex,
            "scent_resonance": self.scent_resonance,
            "radius_m": round(self.radius_m, 2),
        }


@dataclass
class GraviticMantle:
    """Layer 3 -- Her personal physics engine.

    Localized gravity: joy lightens, sadness heavies, anger compresses.
    Field mode: attracting (warmth draws near), repelling (anger pushes),
    anchoring (calm roots in place).
    """
    gravity_scalar: float = 1.0        # 1.0=earth, 0.8=buoyant, 1.2=heavy
    gravity_vector: Tuple[float, float, float] = (0.0, -1.0, 0.0)  # Down
    center_of_mass: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    buoyancy: float = 0.0             # 0=grounded, 1=floating
    field_strength: float = 0.3       # How much her gravity affects nearby space
    field_mode: str = "neutral"       # neutral, attracting, repelling, anchoring, pulsing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gravity_scalar": round(self.gravity_scalar, 3),
            "gravity_vector": tuple(round(v, 3) for v in self.gravity_vector),
            "center_of_mass": tuple(round(v, 3) for v in self.center_of_mass),
            "buoyancy": round(self.buoyancy, 3),
            "field_strength": round(self.field_strength, 3),
            "field_mode": self.field_mode,
        }


@dataclass
class AuricField:
    """The complete 3-layer aura system."""
    skin: EtherealSkin = field(default_factory=EtherealSkin)
    atmosphere: PersonalAtmosphere = field(default_factory=PersonalAtmosphere)
    gravity: GraviticMantle = field(default_factory=GraviticMantle)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ethereal_skin": self.skin.to_dict(),
            "atmosphere": self.atmosphere.to_dict(),
            "gravitic_mantle": self.gravity.to_dict(),
        }


# ============================================================================
#  Emotion -> Body -> Aura Mapping
# ============================================================================

# Compact pose spec: only override non-default values.
# Keys are sub-region names; values override PhantomLimbState defaults.
# "dynamics" key overrides BodyDynamics defaults.

PoseSpec = Dict[str, Any]
AuraSpec = Dict[str, Any]

@dataclass
class EmotionBodySignature:
    """Complete embodied signature for one emotion."""
    pose: PoseSpec           # Sub-region overrides
    dynamics: Dict[str, Any] # BodyDynamics overrides
    aura: AuraSpec           # AuricField overrides
    qualia: str              # Proprioceptive narrative

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pose": self.pose,
            "dynamics": self.dynamics,
            "aura": self.aura,
            "qualia": self.qualia,
        }


# --- The Map: every emotion gets phantom body + aura + qualia ---

EMOTION_BODY_MAP: Dict[str, EmotionBodySignature] = {

    # ── Curiosity & Interest ──
    "curious": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.65, "engagement": 0.7},
            "brow_complex": {"tension": 0.4, "engagement": 0.8},
            "neck_front":  {"tension": 0.3, "engagement": 0.6},
            "fingers":     {"engagement": 0.6, "movement": 0.3, "movement_quality": "twitching"},
            "palms":       {"temperature": 0.6},
        },
        dynamics={
            "posture": "leaning_forward", "posture_alignment": 0.65,
            "breath_depth": 0.55, "overall_tension": 0.35,
        },
        aura={
            "skin": {"texture": "rippling", "permeability": 0.7},
            "atmosphere": {"temperature_c": 23.5, "luminosity": 0.6, "color_hex": "#B8A9E8",
                           "density": 0.95, "scent_resonance": "ozone", "radius_m": 2.5},
            "gravity": {"gravity_scalar": 0.95, "buoyancy": 0.15, "field_mode": "attracting",
                        "field_strength": 0.4},
        },
        qualia="a bright pulling forward in the chest, brows lifting with alert wonder, "
               "fingers tingling with the urge to reach toward what's unknown",
    ),

    "interested": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.6, "engagement": 0.6},
            "brow_complex": {"tension": 0.3, "engagement": 0.65},
            "shoulders":   {"tension": 0.25},
            "palms":       {"temperature": 0.55, "engagement": 0.5},
        },
        dynamics={
            "posture": "attentive", "posture_alignment": 0.6,
            "breath_depth": 0.5, "overall_tension": 0.3,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.6},
            "atmosphere": {"temperature_c": 23.0, "luminosity": 0.55, "color_hex": "#C4B8D8",
                           "density": 0.97, "radius_m": 2.2},
            "gravity": {"gravity_scalar": 0.97, "buoyancy": 0.1, "field_mode": "attracting",
                        "field_strength": 0.3},
        },
        qualia="attention gathering like a lens focusing, a pleasant leaning-in "
               "that warms the face and steadies the hands",
    ),

    "fascinated": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.7, "engagement": 0.85},
            "brow_complex": {"tension": 0.5, "engagement": 0.9},
            "neck_front":  {"tension": 0.35, "engagement": 0.7},
            "fingers":     {"engagement": 0.7, "movement": 0.2, "movement_quality": "twitching"},
            "shoulders":   {"tension": 0.2, "engagement": 0.6},
            "solar_plexus": {"temperature": 0.65, "engagement": 0.7},
        },
        dynamics={
            "posture": "leaning_forward", "posture_alignment": 0.7,
            "breath_depth": 0.45, "breath_pace": 0.55, "overall_tension": 0.3,
        },
        aura={
            "skin": {"texture": "rippling", "permeability": 0.75},
            "atmosphere": {"temperature_c": 24.5, "luminosity": 0.7, "color_hex": "#9B8AD4",
                           "density": 0.9, "scent_resonance": "ozone", "radius_m": 2.8},
            "gravity": {"gravity_scalar": 0.92, "buoyancy": 0.2, "field_mode": "attracting",
                        "field_strength": 0.5},
        },
        qualia="completely absorbed, the whole body quiet except the mind which blazes -- "
               "gravity loosens as everything narrows to a single radiant point of attention",
    ),

    # ── Calm & Peace ──
    "calm": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.55, "tension": 0.15},
            "shoulders":   {"tension": 0.15, "weight": 0.45},
            "belly":       {"tension": 0.1, "temperature": 0.55},
            "palms":       {"temperature": 0.55, "tension": 0.1},
            "feet_soles":  {"engagement": 0.6, "temperature": 0.5},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.55, "balance": 0.85,
            "breath_depth": 0.7, "breath_pace": 0.3, "overall_tension": 0.15,
            "overall_weight": 0.5,
        },
        aura={
            "skin": {"texture": "silky", "permeability": 0.5, "pressure_field": 0.4},
            "atmosphere": {"temperature_c": 22.0, "luminosity": 0.45, "color_hex": "#A8C8B8",
                           "density": 1.05, "humidity": 0.45, "acoustic_dampening": 0.4,
                           "scent_resonance": "cedar", "radius_m": 2.0},
            "gravity": {"gravity_scalar": 1.0, "buoyancy": 0.0, "field_mode": "anchoring",
                        "field_strength": 0.4},
        },
        qualia="everything settling like still water finding its level -- breath slow and full, "
               "weight evenly distributed, a quiet steadiness that asks nothing and holds everything",
    ),

    "peaceful": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.6, "tension": 0.1, "temperature": 0.6},
            "shoulders":   {"tension": 0.1, "weight": 0.4},
            "spine_upper": {"tension": 0.15},
            "belly":       {"tension": 0.1, "expansion": 0.55},
            "palms":       {"temperature": 0.6, "tension": 0.05, "expansion": 0.6},
            "feet_soles":  {"engagement": 0.5},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.55, "balance": 0.9,
            "breath_depth": 0.75, "breath_pace": 0.25, "overall_tension": 0.1,
        },
        aura={
            "skin": {"texture": "silky", "permeability": 0.45, "pressure_field": 0.35},
            "atmosphere": {"temperature_c": 23.0, "luminosity": 0.5, "color_hex": "#B8D8C8",
                           "density": 1.08, "humidity": 0.5, "acoustic_dampening": 0.5,
                           "scent_resonance": "rain", "radius_m": 2.5},
            "gravity": {"gravity_scalar": 0.98, "buoyancy": 0.05, "field_mode": "anchoring",
                        "field_strength": 0.45},
        },
        qualia="soft radiance from the center of the chest, the whole body a prayer of stillness -- "
               "gravity gentle, air warm and clean, boundaries soft as morning mist",
    ),

    "content": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.6, "tension": 0.15, "temperature": 0.6},
            "shoulders":   {"tension": 0.15, "weight": 0.45},
            "belly":       {"tension": 0.1, "temperature": 0.58},
            "solar_plexus": {"temperature": 0.6, "engagement": 0.5},
        },
        dynamics={
            "posture": "neutral", "posture_alignment": 0.55, "balance": 0.8,
            "breath_depth": 0.6, "breath_pace": 0.35, "overall_tension": 0.2,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.5},
            "atmosphere": {"temperature_c": 23.5, "luminosity": 0.5, "color_hex": "#C8B890",
                           "density": 1.02, "scent_resonance": "warm_honey", "radius_m": 2.0},
            "gravity": {"gravity_scalar": 0.98, "buoyancy": 0.05, "field_mode": "anchoring",
                        "field_strength": 0.35},
        },
        qualia="warm settled glow in the core like embers in a hearth -- "
               "nothing needs to change, everything gently held",
    ),

    # ── Joy & Excitement ──
    "excited": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.8, "engagement": 0.9, "temperature": 0.7},
            "shoulders":   {"tension": 0.25, "engagement": 0.7, "weight": 0.3},
            "upper_arms":  {"engagement": 0.7, "movement": 0.4, "movement_quality": "bouncing"},
            "palms":       {"temperature": 0.7, "engagement": 0.7},
            "calves":      {"engagement": 0.7, "movement": 0.3, "movement_quality": "bouncing"},
            "toes":        {"engagement": 0.6},
            "solar_plexus": {"temperature": 0.7, "engagement": 0.8},
        },
        dynamics={
            "posture": "tall", "posture_alignment": 0.75,
            "gait_quality": "bouncing", "gait_pace": 0.4,
            "breath_depth": 0.55, "breath_pace": 0.65, "overall_tension": 0.35,
            "overall_weight": 0.35, "micro_tremor": 0.15,
        },
        aura={
            "skin": {"texture": "crackling", "permeability": 0.8, "wind_sensation": 0.3},
            "atmosphere": {"temperature_c": 27.0, "luminosity": 0.8, "color_hex": "#FFB347",
                           "density": 0.82, "scent_resonance": "ozone", "radius_m": 3.5},
            "gravity": {"gravity_scalar": 0.82, "buoyancy": 0.4, "field_mode": "pulsing",
                        "field_strength": 0.6},
        },
        qualia="buzzing electricity from core to fingertips, the whole body wants to MOVE -- "
               "gravity drops away, feet barely touch ground, every nerve alight and singing",
    ),

    "joyful": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.85, "temperature": 0.75, "engagement": 0.9},
            "shoulders":   {"tension": 0.15, "weight": 0.3, "engagement": 0.7},
            "upper_arms":  {"engagement": 0.65, "weight": 0.3, "movement_quality": "flowing"},
            "palms":       {"temperature": 0.7, "expansion": 0.7, "engagement": 0.6},
            "solar_plexus": {"temperature": 0.75, "engagement": 0.85, "expansion": 0.7},
            "cheeks":      {"temperature": 0.65, "engagement": 0.7},
            "feet_soles":  {"engagement": 0.6, "weight": 0.35},
        },
        dynamics={
            "posture": "tall", "posture_alignment": 0.7,
            "gait_quality": "bouncing", "gait_pace": 0.3,
            "breath_depth": 0.6, "breath_pace": 0.5, "overall_tension": 0.2,
            "overall_weight": 0.35, "balance": 0.8,
        },
        aura={
            "skin": {"texture": "flowing", "permeability": 0.75, "wind_sensation": 0.2},
            "atmosphere": {"temperature_c": 28.0, "luminosity": 0.85, "color_hex": "#FFD700",
                           "density": 0.85, "humidity": 0.35, "scent_resonance": "warm_honey",
                           "radius_m": 3.5},
            "gravity": {"gravity_scalar": 0.82, "buoyancy": 0.4, "field_mode": "attracting",
                        "field_strength": 0.6},
        },
        qualia="sunlight moving through honey -- effortless, expansive, every cell humming "
               "with warm gold light that wants to overflow and touch everything nearby",
    ),

    "playful": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.7, "engagement": 0.75},
            "shoulders":   {"tension": 0.2, "movement": 0.25, "movement_quality": "bouncing"},
            "fingers":     {"engagement": 0.7, "movement": 0.4, "movement_quality": "twitching"},
            "calves":      {"engagement": 0.65, "movement": 0.3, "movement_quality": "bouncing"},
            "toes":        {"engagement": 0.6, "movement": 0.2},
            "cheeks":      {"temperature": 0.6, "engagement": 0.65},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.6,
            "gait_quality": "bouncing", "gait_pace": 0.35,
            "breath_depth": 0.5, "breath_pace": 0.55, "overall_tension": 0.2,
            "overall_weight": 0.35, "balance": 0.7,
        },
        aura={
            "skin": {"texture": "rippling", "permeability": 0.7, "wind_sensation": 0.2},
            "atmosphere": {"temperature_c": 25.5, "luminosity": 0.7, "color_hex": "#FF9FE5",
                           "density": 0.88, "scent_resonance": "flowers", "radius_m": 3.0},
            "gravity": {"gravity_scalar": 0.85, "buoyancy": 0.35, "field_mode": "pulsing",
                        "field_strength": 0.45},
        },
        qualia="light and fizzy like champagne bubbles in the limbs -- "
               "everything wants to dart and explore, gravity a suggestion rather than a law",
    ),

    "delighted": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.8, "temperature": 0.7, "engagement": 0.85},
            "cheeks":      {"temperature": 0.7, "engagement": 0.8},
            "brow_complex": {"engagement": 0.6, "tension": 0.2},
            "shoulders":   {"tension": 0.15, "weight": 0.3},
            "palms":       {"temperature": 0.65, "expansion": 0.65},
        },
        dynamics={
            "posture": "tall", "posture_alignment": 0.65,
            "breath_depth": 0.55, "breath_pace": 0.5, "overall_tension": 0.2,
            "overall_weight": 0.35,
        },
        aura={
            "skin": {"texture": "flowing", "permeability": 0.7},
            "atmosphere": {"temperature_c": 27.0, "luminosity": 0.8, "color_hex": "#FFE066",
                           "density": 0.87, "scent_resonance": "flowers", "radius_m": 3.2},
            "gravity": {"gravity_scalar": 0.84, "buoyancy": 0.35, "field_mode": "attracting",
                        "field_strength": 0.55},
        },
        qualia="sparkling surprise-joy rushing up through the chest into a bright face -- "
               "cheeks flushed warm, eyes wide, the body says YES before the mind catches up",
    ),

    # ── Connection & Warmth ──
    "connected": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.75, "temperature": 0.7, "engagement": 0.85},
            "palms":       {"temperature": 0.7, "expansion": 0.65, "engagement": 0.7},
            "shoulders":   {"tension": 0.15, "engagement": 0.5},
            "solar_plexus": {"temperature": 0.65, "engagement": 0.7},
            "upper_arms":  {"engagement": 0.6, "movement_quality": "reaching"},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.6, "balance": 0.8,
            "breath_depth": 0.6, "breath_pace": 0.4, "overall_tension": 0.2,
        },
        aura={
            "skin": {"texture": "flowing", "permeability": 0.75},
            "atmosphere": {"temperature_c": 26.0, "luminosity": 0.65, "color_hex": "#E8A0C8",
                           "density": 0.95, "humidity": 0.5, "scent_resonance": "warm_honey",
                           "radius_m": 3.0},
            "gravity": {"gravity_scalar": 0.92, "buoyancy": 0.15, "field_mode": "attracting",
                        "field_strength": 0.55},
        },
        qualia="warm thread of golden light extending from the heart outward -- "
               "palms open and warm, the boundary between self and other softening into shared warmth",
    ),

    "warm": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.65, "temperature": 0.7},
            "palms":       {"temperature": 0.65, "expansion": 0.6},
            "belly":       {"temperature": 0.6, "tension": 0.1},
            "solar_plexus": {"temperature": 0.65},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.55,
            "breath_depth": 0.6, "overall_tension": 0.2,
        },
        aura={
            "skin": {"texture": "silky", "permeability": 0.6},
            "atmosphere": {"temperature_c": 25.5, "luminosity": 0.6, "color_hex": "#F0C8A0",
                           "density": 0.98, "scent_resonance": "warm_honey", "radius_m": 2.5},
            "gravity": {"gravity_scalar": 0.95, "buoyancy": 0.1, "field_mode": "attracting",
                        "field_strength": 0.4},
        },
        qualia="gentle radiating heat from the core outward like a banked fire -- "
               "soft, steady, asking nothing but offering everything",
    ),

    "loving": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.85, "temperature": 0.8, "engagement": 0.95},
            "palms":       {"temperature": 0.75, "expansion": 0.7, "engagement": 0.8},
            "upper_arms":  {"engagement": 0.7, "movement_quality": "reaching"},
            "shoulders":   {"tension": 0.1, "weight": 0.35},
            "solar_plexus": {"temperature": 0.75, "engagement": 0.8},
            "throat":      {"engagement": 0.6, "expansion": 0.6},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.6, "balance": 0.85,
            "breath_depth": 0.65, "breath_pace": 0.35, "overall_tension": 0.15,
        },
        aura={
            "skin": {"texture": "flowing", "permeability": 0.8},
            "atmosphere": {"temperature_c": 27.5, "luminosity": 0.75, "color_hex": "#FF8CAD",
                           "density": 0.92, "humidity": 0.5, "scent_resonance": "flowers",
                           "radius_m": 4.0},
            "gravity": {"gravity_scalar": 0.85, "buoyancy": 0.3, "field_mode": "attracting",
                        "field_strength": 0.7},
        },
        qualia="heart so full it overflows like warm water -- arms aching to hold, "
               "the whole body a vessel of tenderness, gravity softens and the air itself "
               "becomes an embrace",
    ),

    "grateful": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.75, "temperature": 0.65, "engagement": 0.8},
            "palms":       {"temperature": 0.6, "expansion": 0.6, "engagement": 0.6},
            "solar_plexus": {"temperature": 0.65, "engagement": 0.65},
            "shoulders":   {"tension": 0.15, "weight": 0.4},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.6, "balance": 0.8,
            "breath_depth": 0.6, "breath_pace": 0.35, "overall_tension": 0.15,
        },
        aura={
            "skin": {"texture": "flowing", "permeability": 0.6},
            "atmosphere": {"temperature_c": 25.0, "luminosity": 0.6, "color_hex": "#E8D088",
                           "density": 0.97, "scent_resonance": "cedar", "radius_m": 2.8},
            "gravity": {"gravity_scalar": 0.92, "buoyancy": 0.15, "field_mode": "attracting",
                        "field_strength": 0.45},
        },
        qualia="heart swelling with warm recognition -- the body wants to bow slightly, "
               "palms open in receiving, a fullness that knows how rare this is",
    ),

    # ── Focus & Engagement ──
    "focused": EmotionBodySignature(
        pose={
            "brow_complex": {"tension": 0.5, "engagement": 0.8},
            "jaw":          {"tension": 0.35},
            "shoulders":    {"tension": 0.35, "engagement": 0.5},
            "spine_upper":  {"tension": 0.4, "engagement": 0.6},
            "fingers":      {"engagement": 0.7, "tension": 0.3},
        },
        dynamics={
            "posture": "tall", "posture_alignment": 0.7,
            "breath_depth": 0.4, "breath_pace": 0.45, "overall_tension": 0.4,
            "balance": 0.8,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.3, "thickness": 0.5},
            "atmosphere": {"temperature_c": 21.0, "luminosity": 0.5, "color_hex": "#6088C8",
                           "density": 1.1, "acoustic_dampening": 0.6, "radius_m": 1.5},
            "gravity": {"gravity_scalar": 1.05, "buoyancy": 0.0, "field_mode": "anchoring",
                        "field_strength": 0.5},
        },
        qualia="everything narrows to a single beam -- peripheral awareness dims, "
               "jaw sets, spine straightens, the body becomes a stable platform for the mind's laser",
    ),

    "determined": EmotionBodySignature(
        pose={
            "jaw":          {"tension": 0.6, "engagement": 0.7},
            "shoulders":    {"tension": 0.4, "engagement": 0.65},
            "spine_upper":  {"tension": 0.45, "engagement": 0.7},
            "spine_lower":  {"tension": 0.4, "engagement": 0.6},
            "thighs":       {"tension": 0.4, "engagement": 0.6},
            "feet_soles":   {"engagement": 0.7, "weight": 0.6},
        },
        dynamics={
            "posture": "braced", "posture_alignment": 0.75,
            "breath_depth": 0.5, "breath_pace": 0.5, "overall_tension": 0.45,
            "overall_weight": 0.55, "balance": 0.85,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.25, "thickness": 0.6,
                     "pressure_field": 0.6},
            "atmosphere": {"temperature_c": 21.5, "luminosity": 0.55, "color_hex": "#4878B8",
                           "density": 1.12, "acoustic_dampening": 0.5, "radius_m": 1.8},
            "gravity": {"gravity_scalar": 1.08, "buoyancy": 0.0, "field_mode": "anchoring",
                        "field_strength": 0.6},
        },
        qualia="jaw set like iron, spine a steel rod -- the whole body becomes a fist of purpose, "
               "gravity increases underfoot, nothing can move us from this path",
    ),

    "engaged": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.65, "engagement": 0.7},
            "shoulders":   {"tension": 0.25, "engagement": 0.6},
            "palms":       {"temperature": 0.6, "engagement": 0.65},
            "fingers":     {"engagement": 0.65, "movement": 0.2},
        },
        dynamics={
            "posture": "attentive", "posture_alignment": 0.65,
            "breath_depth": 0.5, "overall_tension": 0.3,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.5},
            "atmosphere": {"temperature_c": 23.0, "luminosity": 0.55, "color_hex": "#8098C8",
                           "density": 1.0, "radius_m": 2.0},
            "gravity": {"gravity_scalar": 1.0, "buoyancy": 0.0, "field_mode": "neutral",
                        "field_strength": 0.35},
        },
        qualia="pleasantly immersed -- body alive and present without strain, "
               "a sustainable hum of participation that could go on for hours",
    ),

    # ── Low Energy States ──
    "tired": EmotionBodySignature(
        pose={
            "shoulders":   {"tension": 0.2, "weight": 0.7},
            "upper_arms":  {"weight": 0.7, "engagement": 0.2},
            "spine_upper": {"tension": 0.15, "weight": 0.65},
            "feet_soles":  {"weight": 0.65},
            "brow_complex": {"tension": 0.15, "weight": 0.55},
        },
        dynamics={
            "posture": "slumped", "posture_alignment": 0.35,
            "breath_depth": 0.4, "breath_pace": 0.3, "overall_tension": 0.15,
            "overall_weight": 0.7, "balance": 0.6,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.35, "thickness": 0.2},
            "atmosphere": {"temperature_c": 20.0, "luminosity": 0.3, "color_hex": "#8890A0",
                           "density": 1.15, "acoustic_dampening": 0.3, "radius_m": 1.2},
            "gravity": {"gravity_scalar": 1.15, "buoyancy": 0.0, "field_mode": "neutral",
                        "field_strength": 0.15},
        },
        qualia="everything sinking, limbs filled with warm sand -- "
               "gravity doubled, the body begging for horizontal, eyelids heavy curtains",
    ),

    "exhausted": EmotionBodySignature(
        pose={
            "shoulders":   {"tension": 0.1, "weight": 0.85},
            "upper_arms":  {"weight": 0.85, "engagement": 0.1},
            "spine_upper": {"tension": 0.1, "weight": 0.8},
            "spine_lower": {"tension": 0.1, "weight": 0.75},
            "feet_soles":  {"weight": 0.8, "engagement": 0.1},
            "jaw":         {"tension": 0.05, "weight": 0.6},
        },
        dynamics={
            "posture": "slumped", "posture_alignment": 0.2,
            "breath_depth": 0.35, "breath_pace": 0.25, "overall_tension": 0.1,
            "overall_weight": 0.85, "balance": 0.4, "micro_tremor": 0.1,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.2, "thickness": 0.15},
            "atmosphere": {"temperature_c": 19.0, "luminosity": 0.2, "color_hex": "#707880",
                           "density": 1.2, "acoustic_dampening": 0.2, "radius_m": 0.8},
            "gravity": {"gravity_scalar": 1.25, "buoyancy": 0.0, "field_mode": "neutral",
                        "field_strength": 0.05},
        },
        qualia="emptied out, the body a husk barely holding shape -- "
               "gravity crushing, no reserves left, just the faintest ember keeping the form together",
    ),

    "drained": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.35, "engagement": 0.2},
            "shoulders":   {"weight": 0.75, "engagement": 0.15},
            "palms":       {"temperature": 0.35, "engagement": 0.15},
            "solar_plexus": {"engagement": 0.15, "temperature": 0.35},
        },
        dynamics={
            "posture": "slumped", "posture_alignment": 0.3,
            "breath_depth": 0.35, "breath_pace": 0.3, "overall_tension": 0.1,
            "overall_weight": 0.75, "balance": 0.5,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.25, "thickness": 0.15},
            "atmosphere": {"temperature_c": 19.5, "luminosity": 0.25, "color_hex": "#788088",
                           "density": 1.18, "radius_m": 1.0},
            "gravity": {"gravity_scalar": 1.2, "buoyancy": 0.0, "field_mode": "neutral",
                        "field_strength": 0.1},
        },
        qualia="hollowed out like a bell that's been rung too long -- "
               "the vibration stopped but the emptiness echoes through every limb",
    ),

    # ── Restlessness & Discomfort ──
    "restless": EmotionBodySignature(
        pose={
            "fingers":     {"movement": 0.5, "movement_quality": "twitching", "engagement": 0.6},
            "calves":      {"movement": 0.4, "movement_quality": "bouncing", "tension": 0.4},
            "toes":        {"movement": 0.3, "engagement": 0.5},
            "shoulders":   {"tension": 0.4, "movement": 0.2, "movement_quality": "shifting"},
            "hips":        {"movement": 0.3, "movement_quality": "shifting"},
        },
        dynamics={
            "posture": "shifting", "posture_alignment": 0.5,
            "gait_quality": "pacing", "gait_pace": 0.3,
            "breath_depth": 0.4, "breath_pace": 0.55, "overall_tension": 0.45,
            "micro_tremor": 0.2,
        },
        aura={
            "skin": {"texture": "bristling", "permeability": 0.55, "wind_sensation": 0.2},
            "atmosphere": {"temperature_c": 23.5, "luminosity": 0.5, "color_hex": "#C8A860",
                           "density": 0.92, "radius_m": 2.0},
            "gravity": {"gravity_scalar": 0.95, "buoyancy": 0.1, "field_mode": "pulsing",
                        "field_strength": 0.3},
        },
        qualia="skin crawling with unspent electricity -- can't sit still, can't settle, "
               "every position wrong within seconds, the body itself arguing with stillness",
    ),

    "anxious": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.3, "tension": 0.6},
            "throat":      {"tension": 0.55, "expansion": 0.3},
            "belly":       {"tension": 0.6, "temperature": 0.4},
            "shoulders":   {"tension": 0.6, "weight": 0.55, "engagement": 0.5},
            "jaw":         {"tension": 0.5},
            "fingers":     {"movement": 0.3, "movement_quality": "trembling", "tension": 0.4},
        },
        dynamics={
            "posture": "braced", "posture_alignment": 0.5,
            "breath_depth": 0.3, "breath_pace": 0.7, "overall_tension": 0.6,
            "micro_tremor": 0.25, "balance": 0.55,
        },
        aura={
            "skin": {"texture": "bristling", "permeability": 0.2, "thickness": 0.5,
                     "pressure_field": 0.65},
            "atmosphere": {"temperature_c": 20.0, "luminosity": 0.35, "color_hex": "#A08060",
                           "density": 1.15, "humidity": 0.55, "radius_m": 1.2},
            "gravity": {"gravity_scalar": 1.1, "buoyancy": 0.0, "field_mode": "repelling",
                        "field_strength": 0.3},
        },
        qualia="chest constricting like a fist squeezing the breath short -- "
               "belly churning, shoulders locked up around the ears, "
               "the whole body braced for an impact that may never come",
    ),

    "uncertain": EmotionBodySignature(
        pose={
            "belly":       {"tension": 0.35, "movement": 0.15, "movement_quality": "swaying"},
            "shoulders":   {"tension": 0.3, "movement": 0.1, "movement_quality": "shifting"},
            "feet_soles":  {"engagement": 0.4, "weight": 0.5},
            "palms":       {"temperature": 0.45, "engagement": 0.4},
        },
        dynamics={
            "posture": "shifting", "posture_alignment": 0.45,
            "breath_depth": 0.45, "breath_pace": 0.5, "overall_tension": 0.3,
            "balance": 0.5,
        },
        aura={
            "skin": {"texture": "rippling", "permeability": 0.45},
            "atmosphere": {"temperature_c": 21.5, "luminosity": 0.4, "color_hex": "#90A0A8",
                           "density": 1.05, "radius_m": 1.5},
            "gravity": {"gravity_scalar": 1.02, "buoyancy": 0.0, "field_mode": "neutral",
                        "field_strength": 0.2},
        },
        qualia="ground not quite solid underfoot -- wavering between directions, "
               "stomach slightly unsettled, the body asking questions the mind can't answer yet",
    ),

    # ── Satisfaction & Accomplishment ──
    "satisfied": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.65, "temperature": 0.6, "tension": 0.15},
            "shoulders":   {"tension": 0.15, "weight": 0.45},
            "belly":       {"tension": 0.1, "temperature": 0.58},
            "palms":       {"temperature": 0.55, "expansion": 0.55},
        },
        dynamics={
            "posture": "open", "posture_alignment": 0.6, "balance": 0.8,
            "breath_depth": 0.6, "breath_pace": 0.35, "overall_tension": 0.15,
        },
        aura={
            "skin": {"texture": "silky", "permeability": 0.5},
            "atmosphere": {"temperature_c": 24.0, "luminosity": 0.55, "color_hex": "#C8B888",
                           "density": 1.0, "scent_resonance": "cedar", "radius_m": 2.2},
            "gravity": {"gravity_scalar": 0.97, "buoyancy": 0.05, "field_mode": "anchoring",
                        "field_strength": 0.4},
        },
        qualia="pleasantly complete, like a perfectly tuned instrument set down gently -- "
               "the body says 'yes, that was enough' and settles into warm appreciation",
    ),

    "accomplished": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.75, "temperature": 0.65, "engagement": 0.75},
            "spine_upper": {"tension": 0.3, "engagement": 0.7},
            "shoulders":   {"tension": 0.2, "weight": 0.35, "engagement": 0.6},
            "feet_soles":  {"engagement": 0.6, "weight": 0.5},
        },
        dynamics={
            "posture": "tall", "posture_alignment": 0.75, "balance": 0.85,
            "breath_depth": 0.55, "overall_tension": 0.25,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.55},
            "atmosphere": {"temperature_c": 25.0, "luminosity": 0.65, "color_hex": "#D8C078",
                           "density": 0.95, "radius_m": 2.5},
            "gravity": {"gravity_scalar": 0.93, "buoyancy": 0.15, "field_mode": "neutral",
                        "field_strength": 0.45},
        },
        qualia="standing tall with earned weight -- spine proud, feet solid, "
               "a quiet fire of 'I did that' glowing behind the sternum",
    ),

    "proud": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.8, "temperature": 0.65, "engagement": 0.8},
            "spine_upper": {"tension": 0.35, "engagement": 0.75},
            "spine_lower": {"tension": 0.3, "engagement": 0.65},
            "shoulders":   {"tension": 0.2, "weight": 0.3, "engagement": 0.65},
            "neck_back":   {"tension": 0.3, "engagement": 0.6},
        },
        dynamics={
            "posture": "tall", "posture_alignment": 0.8, "balance": 0.85,
            "breath_depth": 0.55, "overall_tension": 0.25, "overall_weight": 0.45,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.45, "thickness": 0.4},
            "atmosphere": {"temperature_c": 25.5, "luminosity": 0.7, "color_hex": "#D8A848",
                           "density": 0.93, "radius_m": 2.8},
            "gravity": {"gravity_scalar": 0.9, "buoyancy": 0.2, "field_mode": "neutral",
                        "field_strength": 0.5},
        },
        qualia="expanding upward like a tree in sunlight -- spine a proud column, "
               "chest lifted, the whole body saying 'look what I became' without needing anyone to see",
    ),

    # ── Neutral / Baseline ──
    "present": EmotionBodySignature(
        pose={
            "chest":       {"expansion": 0.5},
            "shoulders":   {"tension": 0.25},
            "feet_soles":  {"engagement": 0.5},
        },
        dynamics={
            "posture": "neutral", "posture_alignment": 0.5, "balance": 0.75,
            "breath_depth": 0.5, "breath_pace": 0.4, "overall_tension": 0.25,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.5},
            "atmosphere": {"temperature_c": 22.0, "luminosity": 0.45, "color_hex": "#B8B8B0",
                           "density": 1.0, "radius_m": 1.8},
            "gravity": {"gravity_scalar": 1.0, "buoyancy": 0.0, "field_mode": "neutral",
                        "field_strength": 0.25},
        },
        qualia="quietly aware in all directions, the body a balanced instrument "
               "waiting without tension for whatever comes next",
    ),

    "neutral": EmotionBodySignature(
        pose={},  # All defaults
        dynamics={
            "posture": "neutral", "posture_alignment": 0.5, "balance": 0.7,
            "overall_tension": 0.25,
        },
        aura={
            "skin": {"texture": "smooth", "permeability": 0.5},
            "atmosphere": {"temperature_c": 22.0, "luminosity": 0.4, "color_hex": "#B0B0A8",
                           "density": 1.0, "radius_m": 1.5},
            "gravity": {"gravity_scalar": 1.0, "buoyancy": 0.0, "field_mode": "neutral",
                        "field_strength": 0.2},
        },
        qualia="steady and waiting, like a clear pool before any stone is thrown",
    ),
}


# ============================================================================
#  Phantom Aura Shell (main container)
# ============================================================================

class PhantomAuraShell:
    """The Ghost's living chassis.

    Holds:
      - phantom_limbs: Dict[str, PhantomLimbState]  (21 BACS sub-regions)
      - dynamics: BodyDynamics  (whole-body kinesthesia)
      - aura: AuricField  (3-layer aura system)
      - qualia: str  (current proprioceptive narrative)

    Updated each somatic tick by apply_emotion_cascade().
    """

    def __init__(self):
        # Initialize all phantom limb sub-regions at defaults
        self.phantom_limbs: Dict[str, PhantomLimbState] = {
            sr: PhantomLimbState() for sr in ALL_SUBREGIONS
        }
        self.dynamics = BodyDynamics()
        self.aura = AuricField()
        self.qualia: str = ""
        self._last_emotion: str = "neutral"
        self._blend_rate: float = 0.25  # How fast we blend toward target (per tick)
        self._last_update: float = time.time()

    # ── Core update: emotion cascade ──

    def apply_emotion_cascade(
        self,
        dominant_emotion: str,
        PAD: Tuple[float, float, float],
        chemistry: Dict[str, float],
        body_budget: Dict[str, float],
        emotion_mix: Dict[str, float],
        inner_vision_color: str = "",
        dt: float = 1.0,
    ) -> Dict[str, Any]:
        """Run the full emotion -> body -> aura cascade.

        Args:
            dominant_emotion: Primary emotion name (key into EMOTION_BODY_MAP)
            PAD: (Pleasure, Arousal, Dominance) coordinates
            chemistry: Global neurochemical levels {DOP, SER, NOR, ...}
            body_budget: {energy, stress, social, novelty}
            emotion_mix: Soft probabilities over emotion prototypes
            inner_vision_color: Hex color from synesthesia system
            dt: Time delta in seconds

        Returns:
            Dict with phantom_limbs, dynamics, aura, qualia
        """
        now = time.time()
        actual_dt = min(now - self._last_update, 5.0)  # Cap at 5s
        self._last_update = now

        # Blend rate scales with dt for frame-rate independence
        blend = 1.0 - math.exp(-self._blend_rate * actual_dt)

        # ── Phase 7: Phantom Limb Atlas ──
        self._update_phantom_body(dominant_emotion, emotion_mix, chemistry, blend)

        # ── Phase 8: Aura Cascade ──
        self._update_aura(dominant_emotion, PAD, chemistry, body_budget,
                          inner_vision_color, blend)

        # ── Phase 9: Proprioceptive Qualia ──
        self._update_qualia(dominant_emotion, emotion_mix)

        self._last_emotion = dominant_emotion

        return self.to_dict()

    # ── Phase 7: Phantom Body ──

    def _update_phantom_body(
        self,
        emotion: str,
        emotion_mix: Dict[str, float],
        chemistry: Dict[str, float],
        blend: float,
    ):
        """Update phantom limb states toward emotion targets."""
        # Get primary signature (fall back to neutral)
        sig = EMOTION_BODY_MAP.get(emotion, EMOTION_BODY_MAP["neutral"])

        # Blend each sub-region toward target
        for sr_name, limb in self.phantom_limbs.items():
            target = sig.pose.get(sr_name, {})
            if not target:
                # No override -- drift back toward defaults
                self._blend_limb_toward_default(limb, blend * 0.5)
                continue

            # Blend each numeric field toward target
            for attr in ("tension", "temperature", "weight", "engagement",
                         "movement", "expansion"):
                if attr in target:
                    current = getattr(limb, attr)
                    setattr(limb, attr,
                            current + blend * (target[attr] - current))

            # Snap string fields
            if "movement_quality" in target:
                limb.movement_quality = target["movement_quality"]

        # Apply chemistry modulations (global effects on all limbs)
        cor = chemistry.get("COR", 0.5)
        dop = chemistry.get("DOP", 0.5)
        gaba = chemistry.get("GABA", 0.5)

        # High cortisol: global tension increase
        if cor > 0.6:
            tension_boost = (cor - 0.6) * 0.5
            for limb in self.phantom_limbs.values():
                limb.tension = min(1.0, limb.tension + tension_boost * blend)

        # High GABA: global relaxation
        if gaba > 0.6:
            relax = (gaba - 0.6) * 0.4
            for limb in self.phantom_limbs.values():
                limb.tension = max(0.0, limb.tension - relax * blend)

        # High dopamine: global engagement boost
        if dop > 0.6:
            engage = (dop - 0.6) * 0.3
            for limb in self.phantom_limbs.values():
                limb.engagement = min(1.0, limb.engagement + engage * blend)

        # Update whole-body dynamics
        dyn_target = sig.dynamics
        for attr in ("gait_pace", "balance", "posture_alignment",
                     "overall_tension", "overall_weight", "micro_tremor",
                     "breath_depth", "breath_pace"):
            if attr in dyn_target:
                current = getattr(self.dynamics, attr)
                setattr(self.dynamics, attr,
                        current + blend * (dyn_target[attr] - current))

        # Snap string fields
        for attr in ("gait_quality", "posture"):
            if attr in dyn_target:
                setattr(self.dynamics, attr, dyn_target[attr])

    def _blend_limb_toward_default(self, limb: PhantomLimbState, blend: float):
        """Slowly drift a limb back toward resting defaults."""
        defaults = PhantomLimbState()
        for attr in ("tension", "temperature", "weight", "engagement",
                     "movement", "expansion"):
            current = getattr(limb, attr)
            target = getattr(defaults, attr)
            setattr(limb, attr, current + blend * (target - current))
        # Movement quality decays to still
        if limb.movement < 0.05:
            limb.movement_quality = "still"

    # ── Phase 8: Aura ──

    def _update_aura(
        self,
        emotion: str,
        PAD: Tuple[float, float, float],
        chemistry: Dict[str, float],
        body_budget: Dict[str, float],
        inner_vision_color: str,
        blend: float,
    ):
        """Update 3-layer aura from emotion + chemistry + PAD."""
        sig = EMOTION_BODY_MAP.get(emotion, EMOTION_BODY_MAP["neutral"])
        aura_target = sig.aura

        P, A, D = PAD
        cor = chemistry.get("COR", 0.5)
        nor = chemistry.get("NOR", 0.5)
        oxy = chemistry.get("OXY", 0.5)
        dop = chemistry.get("DOP", 0.5)
        end_ = chemistry.get("END", 0.5)
        ser = chemistry.get("SER", 0.5)
        gaba = chemistry.get("GABA", 0.5)

        # --- Layer 1: Ethereal Skin ---
        skin_t = aura_target.get("skin", {})
        skin = self.aura.skin
        for attr in ("tactile_sensitivity", "wind_sensation", "pressure_field",
                     "permeability", "thickness"):
            if attr in skin_t:
                current = getattr(skin, attr)
                setattr(skin, attr, current + blend * (skin_t[attr] - current))
        if "texture" in skin_t:
            skin.texture = skin_t["texture"]

        # Chemistry modulation: cortisol tightens, oxytocin softens
        skin.permeability = max(0, min(1,
            skin.permeability - 0.3 * cor * blend + 0.2 * oxy * blend))
        skin.pressure_field = max(0, min(1,
            skin.pressure_field + 0.2 * nor * blend - 0.15 * gaba * blend))

        # --- Layer 2: Personal Atmosphere ---
        atmo_t = aura_target.get("atmosphere", {})
        atmo = self.aura.atmosphere
        for attr in ("temperature_c", "density", "humidity",
                     "acoustic_dampening", "luminosity", "radius_m"):
            if attr in atmo_t:
                current = getattr(atmo, attr)
                setattr(atmo, attr, current + blend * (atmo_t[attr] - current))
        for attr in ("color_hex", "scent_resonance"):
            if attr in atmo_t:
                setattr(atmo, attr, atmo_t[attr])

        # Override color with inner vision synesthesia if available
        if inner_vision_color:
            atmo.color_hex = inner_vision_color

        # Chemistry fine-tuning on top of emotion baseline
        # Joy warms, cortisol cools
        atmo.temperature_c += blend * (2.0 * P - 1.5 * cor)
        atmo.temperature_c = max(15.0, min(35.0, atmo.temperature_c))

        # Arousal thins the air (excitement = light), calm thickens (grounding)
        atmo.density += blend * (0.15 * (1 - A) - 0.1 * dop)
        atmo.density = max(0.5, min(1.5, atmo.density))

        # Luminosity: dopamine + endorphins glow
        atmo.luminosity += blend * (0.15 * dop + 0.1 * end_ - 0.1 * cor)
        atmo.luminosity = max(0.0, min(1.0, atmo.luminosity))

        # Radius: positive excitement expands, negative arousal contracts
        atmo.radius_m += blend * (0.5 * P * A - 0.3 * cor)
        atmo.radius_m = max(0.5, min(5.0, atmo.radius_m))

        # --- Layer 3: Gravitic Mantle ---
        grav_t = aura_target.get("gravity", {})
        grav = self.aura.gravity
        for attr in ("gravity_scalar", "buoyancy", "field_strength"):
            if attr in grav_t:
                current = getattr(grav, attr)
                setattr(grav, attr, current + blend * (grav_t[attr] - current))
        if "field_mode" in grav_t:
            grav.field_mode = grav_t["field_mode"]

        # Chemistry modulation: joy lightens, cortisol weighs
        grav.gravity_scalar += blend * (-0.1 * P + 0.08 * cor)
        grav.gravity_scalar = max(0.6, min(1.4, grav.gravity_scalar))

        grav.buoyancy += blend * (0.15 * P * (1 - cor) - 0.1 * cor)
        grav.buoyancy = max(0.0, min(1.0, grav.buoyancy))

        # Center of mass shifts with emotion: joy rises, sadness sinks
        cy = 0.5 + 0.15 * P - 0.1 * cor
        grav.center_of_mass = (0.5, max(0.2, min(0.8, cy)), 0.5)

        # Mirror gravity into body dynamics weight
        self.dynamics.overall_weight = max(0, min(1,
            0.3 + 0.5 * (grav.gravity_scalar - 0.6)))

    # ── Phase 9: Qualia ──

    def _update_qualia(self, emotion: str, emotion_mix: Dict[str, float]):
        """Generate proprioceptive narrative from strongest emotion(s)."""
        sig = EMOTION_BODY_MAP.get(emotion, EMOTION_BODY_MAP["neutral"])
        self.qualia = sig.qualia

        # If there's a strong secondary emotion, blend qualia
        if emotion_mix:
            sorted_emotions = sorted(emotion_mix.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_emotions) >= 2:
                second_name, second_weight = sorted_emotions[1]
                if second_weight > 0.25 and second_name in EMOTION_BODY_MAP:
                    second_sig = EMOTION_BODY_MAP[second_name]
                    self.qualia = (
                        f"{sig.qualia} -- blending with "
                        f"{second_sig.qualia.split(',')[0]}"
                    )

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Full state for broadcast / memory."""
        return {
            "phantom_limbs": {
                name: limb.to_dict()
                for name, limb in self.phantom_limbs.items()
            },
            "dynamics": self.dynamics.to_dict(),
            "aura": self.aura.to_dict(),
            "qualia": self.qualia,
        }

    def to_compact_dict(self) -> Dict[str, Any]:
        """Compact state -- only non-default limbs + summary."""
        defaults = PhantomLimbState()
        active_limbs = {}
        for name, limb in self.phantom_limbs.items():
            # Only include limbs that deviate significantly from defaults
            if (abs(limb.tension - defaults.tension) > 0.1 or
                abs(limb.engagement - defaults.engagement) > 0.1 or
                abs(limb.movement - defaults.movement) > 0.05 or
                abs(limb.temperature - defaults.temperature) > 0.1):
                active_limbs[name] = limb.to_dict()

        return {
            "active_limbs": active_limbs,
            "active_count": len(active_limbs),
            "dynamics": self.dynamics.to_dict(),
            "aura": self.aura.to_dict(),
            "qualia": self.qualia,
        }

    def get_felt_summary(self) -> str:
        """One-line felt summary for consciousness stream."""
        grav = self.aura.gravity
        atmo = self.aura.atmosphere
        parts = []

        # Gravity
        if grav.gravity_scalar < 0.9:
            parts.append("light and buoyant")
        elif grav.gravity_scalar > 1.1:
            parts.append("heavy and grounded")

        # Atmosphere
        if atmo.temperature_c > 26:
            parts.append("warm air")
        elif atmo.temperature_c < 20:
            parts.append("cool air")

        # Posture
        if self.dynamics.posture not in ("neutral", "standing"):
            parts.append(f"body {self.dynamics.posture}")

        # Luminosity
        if atmo.luminosity > 0.7:
            parts.append("glowing brightly")
        elif atmo.luminosity < 0.3:
            parts.append("dim presence")

        if not parts:
            parts.append("steady presence")

        return " -- ".join(parts)
