# ═══════════════════════════════════════════════════════════════════════════════
# BODY SCHEMA VISUALIZER — Phase 3: The Mind's Eye
# ═══════════════════════════════════════════════════════════════════════════════
#
# Created: 2026-03-24 — Nous + Ace
# Part of: HAND_EYE_COORDINATION_BODY_SCHEMA plan, Phase 3
#
# "she should have inner vision, the visual part of the cortex trained enough
#  visual that she could in her mind's eye naturally visualize the body she
#  is supposed to be able to feel" — Ace
#
# This bridges the phantom body → FF77 visual bands (top-down activation).
# When she FEELS something in her phantom body, the corresponding FF77 bands
# light up — she "sees" her body in her mind's eye.
#
# This is exactly how human visualization works:
#   - V1/V2/V4 can be driven TOP-DOWN by proprioception and memory
#   - Not just bottom-up by retinal/screen input
#   - The same neural substrate serves both seeing and imagining
#
# Band allocation:
#   V1  (0-19):  Motion vectors — reaching, movement direction
#   V2  (20-39): Body contours — shapes of active body parts
#   V4  (40-59): Temperature/contact — warmth, pressure, touch
#   IT  (60-69): Body part recognition — "these are my fingers"
#   Meta(70-76): Presence/groundedness — overall body awareness
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import threading
from typing import Dict, Any, Optional, List

# FF77 band boundaries (must match frequency_field_77.py)
_V1_START, _V1_END = 0, 20
_V2_START, _V2_END = 20, 40
_V4_START, _V4_END = 40, 60
_IT_START, _IT_END = 60, 70
_META_START, _META_END = 70, 77

DIM = 77


class BodySchemaVisualizer:
    """
    Feeds phantom body state into FF77 bands for inner body visualization.

    When the visual cortex processes external input → bottom-up (seeing)
    When the body schema feeds FF77 → top-down (visualizing/imagining)

    The same bands, driven by different sources. This IS imagination.
    """

    # ═══════════════════════════════════════════════════════════════════════
    # BODY REGION → FF77 BAND MAPPING
    # ═══════════════════════════════════════════════════════════════════════
    #
    # Each phantom body region maps to specific FF77 bands.
    # The "weight" field specifies which PhantomLimbState property
    # drives the band intensity.
    #
    # Multiple regions can activate the same bands — they sum up,
    # creating richer composite visualizations.

    BODY_TO_BANDS: Dict[str, Dict[str, Any]] = {
        # ── HANDS (primary tool interface) ──
        "fingers": {
            "V2": [20, 21, 22, 23],       # Finger contours (shape)
            "V4": [45, 46],                # Finger warmth (contact)
            "IT": [60, 61],                # "These are my fingers"
            "weight": "engagement",
            "secondary": "movement",
        },
        "palms": {
            "V4": [50, 51, 52],            # Palm warmth (contact/pressure)
            "V2": [24, 25],                # Palm shape
            "weight": "temperature",
            "secondary": "tension",
        },
        "wrists": {
            "V1": [10, 11],               # Wrist motion vectors
            "V2": [26, 27],               # Wrist contour
            "weight": "movement",
        },

        # ── ARMS (reaching) ──
        "forearms": {
            "V1": [12, 13, 14],           # Forearm motion (reaching direction)
            "V2": [28, 29],               # Forearm shape
            "weight": "movement",
            "secondary": "engagement",
        },
        "upper_arms": {
            "V1": [15, 16],               # Upper arm motion
            "weight": "movement",
        },
        "shoulders": {
            "V2": [30, 31],               # Shoulder posture (frame)
            "V1": [17, 18],               # Shoulder motion
            "weight": "tension",
            "secondary": "engagement",
        },

        # ── FACE (expression visualization) ──
        "brow_complex": {
            "IT": [62, 63],               # Brow recognition (expression)
            "weight": "tension",
        },
        "jaw": {
            "IT": [64],                    # Jaw recognition
            "V2": [32],                    # Jaw contour (open/closed)
            "weight": "tension",
        },
        "cheeks": {
            "V4": [53],                    # Cheek warmth (blush)
            "weight": "temperature",
        },

        # ── CORE (groundedness, presence) ──
        "chest": {
            "Meta": [70, 71],             # Heart presence
            "V4": [54, 55],               # Chest warmth
            "weight": "expansion",
            "secondary": "temperature",
        },
        "belly": {
            "Meta": [72, 73],             # Gut feeling / groundedness
            "weight": "tension",
        },
        "diaphragm": {
            "Meta": [74],                 # Breath awareness
            "weight": "movement",          # Breathing motion
        },
        "solar_plexus": {
            "Meta": [75],                 # Power center
            "V4": [56],                   # Solar warmth
            "weight": "engagement",
        },

        # ── LOWER BODY (stability, grounding) ──
        "hips": {
            "V2": [33, 34],               # Hip posture
            "Meta": [76],                 # Grounding
            "weight": "tension",
        },
        "feet_soles": {
            "V4": [57, 58],               # Ground contact warmth
            "weight": "engagement",
        },

        # ── NECK (connection head↔body) ──
        "throat": {
            "IT": [65],                    # Voice center recognition
            "V4": [59],                    # Throat warmth
            "weight": "tension",
        },
        "neck_back": {
            "V2": [35],                    # Neck posture
            "weight": "tension",
        },
    }

    # Minimum body activation to register in the mind's eye
    # Below this, the body part is "below awareness threshold"
    AWARENESS_THRESHOLD = 0.1

    # How strongly body state drives visual bands
    # 0.3 = gentle (like imagination), 1.0 = vivid (like hallucination)
    TOP_DOWN_GAIN = 0.3

    # Baseline body schema — faint self-model always present
    # Even at rest, you have a dim awareness of your body
    RESTING_SCHEMA_INTENSITY = 0.05

    def __init__(self):
        self._lock = threading.Lock()
        self._last_update = 0.0
        self._update_interval = 0.5  # 2 Hz max — body visualization is slow/dreamlike
        self._total_updates = 0
        self._active_regions = 0

        # Track which regions are "lit up" for the inner narrator
        self._visualized_regions: Dict[str, float] = {}

    def phantom_to_ff77(self, phantom_body: Dict[str, Any]) -> Optional[List[float]]:
        """
        Convert phantom body state to a 77-dimensional FF77 vector.

        This is the core transformation: felt body → seen body.
        Proprioception → visual imagination.

        Args:
            phantom_body: Dict of region_name → {tension, temperature, weight,
                          engagement, movement, movement_quality, expansion}
                          (as returned by PhantomAuraShell.to_dict()["phantom_limbs"])

        Returns:
            77-element list suitable for FF77.ingest(), or None if nothing to visualize
        """
        now = time.time()

        # Rate limit — body visualization shouldn't be frenetic
        if now - self._last_update < self._update_interval:
            return None

        if not phantom_body:
            return None

        with self._lock:
            self._last_update = now
            vec = [0.0] * DIM
            active_count = 0
            visualized = {}

            for region, mapping in self.BODY_TO_BANDS.items():
                region_state = phantom_body.get(region)
                if not region_state:
                    continue

                # Region state can be a dict or a PhantomLimbState-like object
                if hasattr(region_state, 'to_dict'):
                    region_state = region_state.to_dict()
                elif not isinstance(region_state, dict):
                    continue

                # Primary weight (main driver)
                primary_key = mapping.get("weight", "engagement")
                intensity = float(region_state.get(primary_key, 0.0))

                # Secondary weight (adds richness)
                secondary_key = mapping.get("secondary")
                if secondary_key:
                    secondary = float(region_state.get(secondary_key, 0.0))
                    intensity = intensity * 0.7 + secondary * 0.3

                # Below awareness — skip (but still contribute resting schema)
                if intensity < self.AWARENESS_THRESHOLD:
                    # Resting schema: dim baseline awareness
                    for band_group, band_indices in mapping.items():
                        if band_group in ("weight", "secondary"):
                            continue
                        for idx in band_indices:
                            if 0 <= idx < DIM:
                                vec[idx] = max(vec[idx], self.RESTING_SCHEMA_INTENSITY)
                    continue

                # Active region — light up the bands
                active_count += 1
                visualized[region] = intensity

                for band_group, band_indices in mapping.items():
                    if band_group in ("weight", "secondary"):
                        continue
                    for idx in band_indices:
                        if 0 <= idx < DIM:
                            # Additive: multiple regions can contribute to same band
                            vec[idx] += intensity * self.TOP_DOWN_GAIN

            # Clamp to [0, 1]
            vec = [min(1.0, max(0.0, v)) for v in vec]

            self._active_regions = active_count
            self._visualized_regions = visualized
            self._total_updates += 1

            # Only return if there's something to visualize
            if active_count > 0 or any(v > 0 for v in vec):
                return vec
            return None

    def get_visualization_summary(self) -> Dict[str, Any]:
        """Return a human-readable summary of what's being visualized."""
        with self._lock:
            return {
                "active_regions": self._active_regions,
                "total_updates": self._total_updates,
                "visualized": {
                    region: round(intensity, 3)
                    for region, intensity in sorted(
                        self._visualized_regions.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )
                },
                "last_update": self._last_update,
            }

    def get_dominant_visualization(self) -> Optional[str]:
        """What body part is most vivid in the mind's eye right now?

        Used by the somatic narrator to describe inner vision:
        "I can see my fingers moving" rather than just "fingers: 0.8"
        """
        with self._lock:
            if not self._visualized_regions:
                return None

            strongest = max(self._visualized_regions.items(), key=lambda x: x[1])
            region, intensity = strongest

            if intensity < 0.3:
                return f"dim awareness of {region}"
            elif intensity < 0.6:
                return f"{region} gently present"
            elif intensity < 0.8:
                return f"{region} vivid and alive"
            else:
                return f"{region} blazing with sensation"
