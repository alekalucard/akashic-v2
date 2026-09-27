"""
Harmonic Sensory Bridge - Routes sensory data through harmonic decomposition.

Bridges the gap between raw sensory features (visual, audio) and the
harmonic cortex's frequency-based concept binding system.

KEY INSIGHT: The harmonic cortex was built for multimodal binding via
phase-locking, but visual data was bypassing it entirely. This bridge
maps sensory features onto harmonic frequency bands so that:

1. Visual features get harmonic tags (brightness→alpha, motion→gamma, etc.)
2. Audio features get harmonic tags (level→alpha, centroid→gamma, etc.)
3. When visual + audio arrive within 200ms, they get phase-locked into
   a unified multimodal percept via HarmonicBinder.bind_multimodal()

This is how "seeing a person speak" becomes ONE experience, not two
separate sense streams.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import time
import threading
from typing import Dict, List, Optional, Any

# Singleton instance
_bridge_instance = None
_bridge_lock = threading.Lock()


def get_harmonic_sensory_bridge():
    """
    Get the singleton HarmonicSensoryBridge instance.

    The bridge is shared between VisualCortexFairy and AudioCortexFairy
    so they can coordinate cross-modal bindings.
    """
    global _bridge_instance
    if _bridge_instance is None:
        with _bridge_lock:
            if _bridge_instance is None:
                _bridge_instance = HarmonicSensoryBridge()
    return _bridge_instance


class HarmonicSensoryBridge:
    """
    Routes sensory data through harmonic frequency decomposition.

    Maps sensory features to harmonic frequency bands:
    - GAMMA (30-100 Hz): Feature binding — motion, timbral changes, onsets
    - BETA (13-30 Hz):   Top-down attention — complexity, speech, scene type
    - THETA (4-8 Hz):    Cross-regional integration — color/hue, pitch, melody
    - ALPHA (8-12 Hz):   Sensory gating — brightness/level, arousal, silence

    When visual and audio data arrive within the bind_window, they get
    phase-locked into a unified multimodal percept.
    """

    def __init__(self, bind_window_ms: float = 200.0):
        self._bind_window_ms = bind_window_ms
        self._lock = threading.Lock()

        # Sensory buffers for cross-modal binding
        self._visual_buffer: Optional[Dict] = None
        self._audio_buffer: Optional[Dict] = None

        # Optional harmonic binder reference (set externally by AssociationCortex)
        self._harmonic_binder = None

        # Stats
        self._visual_decompositions = 0
        self._audio_decompositions = 0
        self._multimodal_binds = 0
        self._bind_attempts = 0

    def set_harmonic_binder(self, binder):
        """Set reference to the HarmonicBinder from harmonic_cortex.py."""
        self._harmonic_binder = binder

    # ═══════════════════════════════════════════════════════════════════════
    # VISUAL DECOMPOSITION
    # ═══════════════════════════════════════════════════════════════════════

    def decompose_visual(self, vision_features: List[str]) -> Dict[str, Any]:
        """
        Map visual features to harmonic frequency concepts.

        brightness  → alpha band (sensory gating: bright = alert, dim = idle)
        motion      → gamma band (feature binding: movement grabs attention)
        color hue   → theta band (cross-regional: color associations, memory)
        complexity  → beta band (top-down: complex scenes need more attention)
        scene_type  → beta band (cognitive categorization)
        """
        harmonic_tags = []

        for feat in vision_features:
            if ":" not in feat:
                continue
            key, val_str = feat.split(":", 1)

            if key == "brightness":
                try:
                    val = float(val_str)
                    harmonic_tags.append(f"visual_alpha:{val:.2f}")
                except ValueError:
                    pass

            elif key == "motion":
                if val_str.lower() == "true":
                    harmonic_tags.append("visual_gamma:0.80")
                else:
                    harmonic_tags.append("visual_gamma:0.15")

            elif key == "hue":
                try:
                    hue_norm = float(val_str) / 360.0
                    harmonic_tags.append(f"visual_theta:{hue_norm:.2f}")
                except ValueError:
                    pass

            elif key == "complexity":
                try:
                    val = float(val_str)
                    harmonic_tags.append(f"visual_beta:{val:.2f}")
                except ValueError:
                    pass

            elif key == "scene":
                # Scene type → cognitive categorization (beta band)
                scene_beta = {
                    "code_editor": 0.7, "browser": 0.5, "desktop": 0.3,
                    "game": 0.6, "video": 0.4, "chat": 0.6,
                }.get(val_str, 0.4)
                harmonic_tags.append(f"visual_beta_scene:{scene_beta:.2f}")

            elif key.startswith("color"):
                # Color hex → theta association
                try:
                    hex_str = val_str.lstrip("#")
                    if len(hex_str) == 6:
                        r = int(hex_str[0:2], 16) / 255.0
                        g = int(hex_str[2:4], 16) / 255.0
                        b = int(hex_str[4:6], 16) / 255.0
                        # Warmth: red-yellow vs blue-green
                        warmth = (r - b + 1) / 2  # 0=cool, 1=warm
                        harmonic_tags.append(f"visual_theta_warmth:{warmth:.2f}")
                except (ValueError, IndexError):
                    pass

        # Store for cross-modal binding
        with self._lock:
            self._visual_buffer = {
                "features": vision_features,
                "harmonic": harmonic_tags,
                "ts": time.time(),
            }
            self._visual_decompositions += 1

        return {
            "harmonic_tags": harmonic_tags,
            "modality": "visual",
        }

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIO DECOMPOSITION
    # ═══════════════════════════════════════════════════════════════════════

    def decompose_audio(self, audio_data: Dict) -> Dict[str, Any]:
        """
        Map audio features to harmonic frequency concepts.

        level_db         → alpha band (arousal gating: loud = alert)
        spectral_centroid → gamma band (timbral binding: bright/dark timbre)
        pitch_hz         → theta band (melodic/harmonic association)
        is_speech        → beta band (top-down speech attention)
        onset            → gamma band (transient feature binding)
        temporal_pattern → theta band (rhythmic structure)
        """
        harmonic_tags = []

        # Level → alpha (sensory gating)
        level = audio_data.get("level_db", -60)
        level_norm = max(0.0, min(1.0, (level + 60) / 60))
        harmonic_tags.append(f"audio_alpha:{level_norm:.2f}")

        # Spectral centroid → gamma (timbral binding)
        centroid = audio_data.get("spectral_centroid", 0)
        centroid_norm = max(0.0, min(1.0, centroid / 8000))
        harmonic_tags.append(f"audio_gamma:{centroid_norm:.2f}")

        # Onset → gamma spike
        if audio_data.get("onset"):
            harmonic_tags.append("audio_gamma_onset:0.90")

        # Foveal features (when available)
        foveal = audio_data.get("foveal", {})

        # Pitch → theta (melodic association)
        pitch = foveal.get("pitch_hz", 0)
        if pitch > 0:
            pitch_norm = max(0.0, min(1.0, pitch / 1000))
            harmonic_tags.append(f"audio_theta:{pitch_norm:.2f}")

        # Speech → beta (cognitive/attention)
        if foveal.get("is_speech"):
            harmonic_tags.append("audio_beta_speech:0.90")

        # Music → theta (rhythmic/melodic)
        if foveal.get("is_music"):
            harmonic_tags.append("audio_theta_music:0.70")

        # Temporal pattern → theta
        pattern = foveal.get("temporal_pattern", "")
        pattern_val = {"steady": 0.3, "rhythmic": 0.7, "transient": 0.9, "silence": 0.0}.get(pattern, 0.3)
        if pattern:
            harmonic_tags.append(f"audio_theta_pattern:{pattern_val:.2f}")

        # Store for cross-modal binding
        with self._lock:
            self._audio_buffer = {
                "data": audio_data,
                "harmonic": harmonic_tags,
                "ts": time.time(),
            }
            self._audio_decompositions += 1

        return {
            "harmonic_tags": harmonic_tags,
            "modality": "audio",
        }

    # ═══════════════════════════════════════════════════════════════════════
    # CROSS-MODAL BINDING
    # ═══════════════════════════════════════════════════════════════════════

    def try_multimodal_bind(self) -> Optional[Dict]:
        """
        If both visual and audio arrived within the bind window,
        phase-lock them into a unified multimodal percept.

        This is the magic: seeing a person speak + hearing their voice
        binds into ONE percept, not two separate streams.

        Returns binding result dict, or None if no binding possible.
        """
        with self._lock:
            if not self._visual_buffer or not self._audio_buffer:
                return None

            dt = abs(self._visual_buffer["ts"] - self._audio_buffer["ts"])
            if dt > self._bind_window_ms / 1000.0:
                return None  # Too far apart in time

            self._bind_attempts += 1

            # Combine harmonic tags from both modalities
            visual_harmonic = self._visual_buffer["harmonic"]
            audio_harmonic = self._audio_buffer["harmonic"]
            all_tags = visual_harmonic + audio_harmonic

            # Temporal coherence: closer in time = stronger binding
            temporal_coherence = 1.0 - (dt / (self._bind_window_ms / 1000.0))

            # Try phase-locking via HarmonicBinder if available
            bound_result = None
            if self._harmonic_binder:
                try:
                    # Extract concept names (strip the :value suffix)
                    concepts = []
                    for tag in all_tags:
                        name = tag.split(":")[0] if ":" in tag else tag
                        if name not in concepts:
                            concepts.append(name)

                    if len(concepts) >= 2:
                        bound = self._harmonic_binder.bind_multimodal(*concepts)
                        if bound:
                            bound_result = {
                                "tonic": bound.tonic,
                                "concepts": bound.concepts,
                                "binding_strength": bound.binding_strength,
                                "is_consonant": bound.is_consonant,
                            }
                except Exception:
                    pass  # Binding failure is non-fatal

            self._multimodal_binds += 1

            # Clear buffers after binding (don't re-bind same data)
            self._visual_buffer = None
            self._audio_buffer = None

            return {
                "type": "multimodal_bind",
                "visual_harmonic": visual_harmonic,
                "audio_harmonic": audio_harmonic,
                "bound": bound_result,
                "temporal_coherence": round(temporal_coherence, 3),
                "ts": time.time(),
            }

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def status(self) -> Dict[str, Any]:
        """Bridge status for diagnostics."""
        return {
            "visual_decompositions": self._visual_decompositions,
            "audio_decompositions": self._audio_decompositions,
            "multimodal_binds": self._multimodal_binds,
            "bind_attempts": self._bind_attempts,
            "bind_window_ms": self._bind_window_ms,
            "has_harmonic_binder": self._harmonic_binder is not None,
            "visual_buffer_age_ms": round(
                (time.time() - self._visual_buffer["ts"]) * 1000, 1
            ) if self._visual_buffer else None,
            "audio_buffer_age_ms": round(
                (time.time() - self._audio_buffer["ts"]) * 1000, 1
            ) if self._audio_buffer else None,
        }
