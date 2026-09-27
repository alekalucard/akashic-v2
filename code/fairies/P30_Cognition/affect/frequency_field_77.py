# ═══════════════════════════════════════════════════════════════════════════════
# FREQUENCY FIELD 77 - Neural Frequency Band System
# ═══════════════════════════════════════════════════════════════════════════════
#
# Ported from Whisper Core's affect/frequency_field_77.py
# Adapted for ebook's SharedPostalHub infrastructure
#
# Philosophy: "77 frequencies of consciousness, each a window into the mind."
#
# The FF77 system represents neural state as 77-dimensional frequency vectors.
# Each dimension corresponds to a frequency band that carries meaning:
#   - Bands 0-19:  V1 (Primary Visual) - Edge detection, orientation
#   - Bands 20-39: V2 (Secondary Visual) - Shape, contour
#   - Bands 40-59: V4 (Color Processing) - Color, texture
#   - Bands 60-69: IT (Inferotemporal) - Object recognition
#   - Bands 70-76: Meta (Context) - Scene, affect, attention
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import hashlib
import threading
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Deque
from collections import deque
from datetime import datetime, timezone

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DIM = 77  # The sacred number of frequency bands
MODULE_NAME = "P30_Cognition.affect.frequency_field_77"

# Frequency band assignments
BAND_V1_START, BAND_V1_END = 0, 20      # Primary visual (edges)
BAND_V2_START, BAND_V2_END = 20, 40     # Secondary visual (shapes)
BAND_V4_START, BAND_V4_END = 40, 60     # Color processing
BAND_IT_START, BAND_IT_END = 60, 70     # Object recognition
BAND_META_START, BAND_META_END = 70, 77 # Meta/context

# Topics for postal routing
TOPIC_FREQUENCY = "telemetry.frequency"
TOPIC_PULSE = "telemetry.pulse"
TOPIC_SRM = "memory.semantic.relation"
TOPIC_FF77_STATE = "ff77.state"

# Environment toggles
FF77_ENABLED = os.getenv("FF77_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
FF77_EMIT_RATE = float(os.getenv("FF77_EMIT_RATE", "10.0"))  # Hz
SRM_ENABLED = os.getenv("SRM_ENABLED", "1").lower() in {"1", "true", "yes", "on"}


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

_postal = None

def _get_postal():
    """Get the SharedPostalHub singleton."""
    global _postal
    if _postal is None:
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            _postal = get_shared_postal_hub()
        except ImportError:
            _postal = None
    return _postal


def publish(topic: str, payload: Dict[str, Any], priority: int = 1) -> bool:
    """Publish a message to the postal system."""
    postal = _get_postal()
    if postal is None:
        return False
    try:
        postal.route(topic, payload)
        return True
    except Exception:
        return False


def subscribe(topic: str, handler, **kwargs):
    """Subscribe to a postal topic."""
    postal = _get_postal()
    if postal is None:
        return None
    try:
        return postal.subscribe(topic, handler)
    except Exception:
        return None


def now_ms() -> int:
    """Current timestamp in milliseconds."""
    return int(time.time() * 1000)


# ═══════════════════════════════════════════════════════════════════════════════
# FREQUENCY VECTOR UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def validate_vec77(vec: List[float]) -> bool:
    """Validate a 77-dimensional frequency vector."""
    if not isinstance(vec, (list, tuple, np.ndarray)):
        return False
    if len(vec) != DIM:
        return False
    return all(isinstance(v, (int, float)) for v in vec)


def normalize_vec77(vec: List[float]) -> List[float]:
    """Normalize a 77-dim vector to unit length."""
    arr = np.array(vec, dtype=float)
    norm = np.linalg.norm(arr)
    if norm < 1e-10:
        return [0.0] * DIM
    return (arr / norm).tolist()


def zero_vec77() -> List[float]:
    """Return a zero 77-dim vector."""
    return [0.0] * DIM


def random_vec77(scale: float = 1.0) -> List[float]:
    """Return a random 77-dim vector."""
    return (np.random.randn(DIM) * scale).tolist()


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL TO FF77 CONVERSION
# ═══════════════════════════════════════════════════════════════════════════════

def visual_to_ff77(
    v1_features: Optional[Dict[str, Any]] = None,
    v2_features: Optional[Dict[str, Any]] = None,
    v4_features: Optional[Dict[str, Any]] = None,
    it_features: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None
) -> List[float]:
    """
    Convert visual features (from visual cards) to 77-dim frequency vector.

    Args:
        v1_features: V1 edge detection features (edge_density, orientations)
        v2_features: V2 shape features (contour_count, corner_count)
        v4_features: V4 color features (dominant_hue, saturation, colors)
        it_features: IT object features (scene_type, complexity)
        meta: Meta information (attention, context)

    Returns:
        77-dimensional frequency vector
    """
    vec77 = [0.0] * DIM

    # V1: Edge detection -> bands 0-19
    if v1_features:
        edge_density = v1_features.get("edge_density", 0.0)
        orientations = v1_features.get("orientations", {})

        # Edge density fills first 10 bands
        for i in range(10):
            vec77[BAND_V1_START + i] = edge_density * (1.0 - i * 0.1)

        # Orientation histogram fills bands 10-19
        for i, (angle, strength) in enumerate(sorted(orientations.items())[:10]):
            vec77[BAND_V1_START + 10 + i] = float(strength)

    # V2: Shape detection -> bands 20-39
    if v2_features:
        contour_count = v2_features.get("contour_count", 0)
        corner_count = v2_features.get("corner_count", 0)
        contrast = v2_features.get("contrast", 0.0)

        # Normalize contour count (assume max ~100)
        vec77[BAND_V2_START] = min(1.0, contour_count / 100.0)
        vec77[BAND_V2_START + 1] = min(1.0, corner_count / 50.0)
        vec77[BAND_V2_START + 2] = contrast

        # Fill remaining with decay
        for i in range(3, 20):
            vec77[BAND_V2_START + i] = vec77[BAND_V2_START] * (1.0 - i * 0.05)

    # V4: Color processing -> bands 40-59
    if v4_features:
        dominant_hue = v4_features.get("dominant_hue", 0)
        saturation = v4_features.get("saturation", 0.0)
        colors = v4_features.get("colors", [])

        # Hue as position in color wheel (normalized 0-1)
        vec77[BAND_V4_START] = dominant_hue / 360.0 if dominant_hue else 0.0
        vec77[BAND_V4_START + 1] = saturation

        # Color palette (up to 10 colors)
        for i, color in enumerate(colors[:10]):
            if isinstance(color, (list, tuple)) and len(color) >= 3:
                # RGB to single value
                r, g, b = color[:3]
                vec77[BAND_V4_START + 2 + i] = (r + g + b) / (3 * 255.0)

    # IT: Object recognition -> bands 60-69
    if it_features:
        scene_type = it_features.get("scene_type", "")
        complexity = it_features.get("complexity", 0.0)

        # Scene type encoding
        scene_types = ["photo", "screenshot", "artwork", "diagram", "text", "unknown"]
        scene_idx = scene_types.index(scene_type) if scene_type in scene_types else 5
        vec77[BAND_IT_START] = scene_idx / len(scene_types)
        vec77[BAND_IT_START + 1] = complexity

        # Objects detected (if present)
        objects = it_features.get("objects", [])
        vec77[BAND_IT_START + 2] = min(1.0, len(objects) / 10.0)

    # Meta: Context -> bands 70-76
    if meta:
        attention = meta.get("attention", 0.5)
        arousal = meta.get("arousal", 0.5)
        valence = meta.get("valence", 0.5)

        vec77[BAND_META_START] = attention
        vec77[BAND_META_START + 1] = arousal
        vec77[BAND_META_START + 2] = valence
        vec77[BAND_META_START + 3] = meta.get("confidence", 0.5)
        vec77[BAND_META_START + 4] = meta.get("novelty", 0.5)
        vec77[BAND_META_START + 5] = meta.get("relevance", 0.5)
        vec77[BAND_META_START + 6] = meta.get("coherence", 0.5)

    return vec77


# ═══════════════════════════════════════════════════════════════════════════════
# SRM (SEMANTIC RELATION MEMORY)
# ═══════════════════════════════════════════════════════════════════════════════

def _srm_key(subject: str, predicate: str, obj: str, context: Dict[str, Any]) -> str:
    """Generate idempotent key for SRM triple."""
    h = hashlib.sha256()
    h.update(subject.encode())
    h.update(b"|")
    h.update(predicate.encode())
    h.update(b"|")
    h.update(obj.encode())
    # Include stable context fields
    stable = {k: context[k] for k in sorted(context)
              if k in {"plane", "channel", "module", "version", "time_bucket"}}
    h.update(json.dumps(stable, sort_keys=True).encode())
    return h.hexdigest()[:24]


def emit_srm(
    subject: str,
    predicate: str,
    obj: str,
    strength: float = 0.6,
    tags: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    ttl_sec: Optional[int] = None
) -> bool:
    """
    Emit a Semantic Relation Memory triple.

    Args:
        subject: The subject entity
        predicate: The relationship type
        obj: The object entity
        strength: Relation strength (0.0-1.0)
        tags: Optional tags for filtering
        context: Optional context dict
        ttl_sec: Time-to-live in seconds

    Returns:
        True if emitted successfully
    """
    if not SRM_ENABLED:
        return False

    ctx = context or {}
    env = {
        "intent": "srm.upsert",
        "t": now_ms(),
        "payload": {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "strength": float(max(0.0, min(1.0, strength))),
            "key": _srm_key(subject, predicate, obj, ctx),
            "context": ctx,
        },
        "meta": {
            "module": MODULE_NAME,
            "tags": tags or [],
        }
    }

    if ttl_sec is not None:
        env["ttl_sec"] = int(ttl_sec)

    return publish(TOPIC_SRM, env)


# ═══════════════════════════════════════════════════════════════════════════════
# FREQUENCY FIELD CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class FrequencyField77:
    """
    The 77-band neural frequency field.

    Maintains a rolling buffer of frequency vectors and provides
    methods for emission, aggregation, and analysis.
    """

    def __init__(self, buffer_size: int = 100):
        self.buffer: Deque[Tuple[float, List[float]]] = deque(maxlen=buffer_size)
        self.current_state: List[float] = zero_vec77()
        self._lock = threading.RLock()
        self._last_emit_time = 0.0
        self._emit_interval = 1.0 / FF77_EMIT_RATE

        # Statistics
        self.total_emissions = 0
        self.total_ingestions = 0

        # Subscribe to frequency telemetry
        subscribe(TOPIC_FREQUENCY, self._on_frequency)

    def _on_frequency(self, msg: Dict[str, Any]):
        """Handle incoming frequency vectors."""
        payload = msg.get("payload", msg)
        vec = payload.get("vec", [])
        if validate_vec77(vec):
            with self._lock:
                self.buffer.append((time.time(), vec))
                self.total_ingestions += 1

    def ingest(self, vec77: List[float], update_state: bool = True) -> bool:
        """
        Ingest a frequency vector into the field.

        Args:
            vec77: 77-dimensional frequency vector
            update_state: Whether to update current_state

        Returns:
            True if ingested successfully
        """
        if not validate_vec77(vec77):
            return False

        with self._lock:
            self.buffer.append((time.time(), vec77))
            self.total_ingestions += 1

            if update_state:
                # Exponential moving average
                alpha = 0.3
                self.current_state = [
                    alpha * new + (1 - alpha) * old
                    for new, old in zip(vec77, self.current_state)
                ]

        return True

    def emit_frequency(
        self,
        vec77: Optional[List[float]] = None,
        organ: Optional[str] = None,
        plane: str = "affect",
        channel: str = "frequency"
    ) -> bool:
        """
        Emit a frequency vector to the postal system.

        Args:
            vec77: Vector to emit (uses current_state if None)
            organ: Source organ/module
            plane: Routing plane
            channel: Routing channel

        Returns:
            True if emitted successfully
        """
        if not FF77_ENABLED:
            return False

        # Rate limiting
        now = time.time()
        if now - self._last_emit_time < self._emit_interval:
            return False

        with self._lock:
            vec = vec77 if vec77 is not None else self.current_state

            if not validate_vec77(vec):
                return False

            payload = {
                "plane": plane,
                "channel": channel,
                "frequency_tag": "ff77",
                "organ": organ or MODULE_NAME,
                "vec": [float(v) for v in vec],
                "ts": now_ms(),
            }

            success = publish(TOPIC_FREQUENCY, {
                "intent": "telemetry.frequency",
                "t": now_ms(),
                "payload": payload,
                "meta": {"module": MODULE_NAME}
            })

            if success:
                self._last_emit_time = now
                self.total_emissions += 1

            return success

    def emit_pulse(
        self,
        state: str,
        intensity: float,
        plane: str = "affect",
        channel: str = "pulse"
    ) -> bool:
        """
        Emit a pulse (health/state signal).

        Args:
            state: Current state ("on", "idle", "off")
            intensity: Signal intensity (-1.0 to 1.0)
            plane: Routing plane
            channel: Routing channel

        Returns:
            True if emitted successfully
        """
        payload = {
            "ts_ms": now_ms(),
            "module_path": MODULE_NAME,
            "plane": plane,
            "channel": channel,
            "frequency_tag": "ff77",
            "state": state,
            "intensity": float(intensity),
        }

        return publish(TOPIC_PULSE, {
            "intent": "telemetry.pulse",
            "t": now_ms(),
            "payload": payload,
            "meta": {"module": MODULE_NAME}
        })

    def get_aggregate(self, window_sec: float = 1.0) -> List[float]:
        """
        Get aggregate frequency vector over a time window.

        Args:
            window_sec: Time window in seconds

        Returns:
            Aggregated 77-dim vector
        """
        with self._lock:
            cutoff = time.time() - window_sec
            recent = [vec for ts, vec in self.buffer if ts >= cutoff]

            if not recent:
                return self.current_state.copy()

            # Mean aggregation
            return np.mean(recent, axis=0).tolist()

    def get_band_energy(self, band_start: int, band_end: int) -> float:
        """Get energy in a specific frequency band range."""
        with self._lock:
            return sum(self.current_state[band_start:band_end]) / (band_end - band_start)

    def get_v1_energy(self) -> float:
        """Get V1 (edge) band energy."""
        return self.get_band_energy(BAND_V1_START, BAND_V1_END)

    def get_v2_energy(self) -> float:
        """Get V2 (shape) band energy."""
        return self.get_band_energy(BAND_V2_START, BAND_V2_END)

    def get_v4_energy(self) -> float:
        """Get V4 (color) band energy."""
        return self.get_band_energy(BAND_V4_START, BAND_V4_END)

    def get_it_energy(self) -> float:
        """Get IT (object) band energy."""
        return self.get_band_energy(BAND_IT_START, BAND_IT_END)

    def get_meta_energy(self) -> float:
        """Get Meta band energy."""
        return self.get_band_energy(BAND_META_START, BAND_META_END)

    def get_stats(self) -> Dict[str, Any]:
        """Get field statistics."""
        with self._lock:
            return {
                "buffer_size": len(self.buffer),
                "total_emissions": self.total_emissions,
                "total_ingestions": self.total_ingestions,
                "v1_energy": self.get_v1_energy(),
                "v2_energy": self.get_v2_energy(),
                "v4_energy": self.get_v4_energy(),
                "it_energy": self.get_it_energy(),
                "meta_energy": self.get_meta_energy(),
                "total_energy": sum(self.current_state) / DIM,
            }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_ff77_instance: Optional[FrequencyField77] = None
_ff77_lock = threading.Lock()


def get_frequency_field() -> FrequencyField77:
    """Get the FrequencyField77 singleton."""
    global _ff77_instance
    if _ff77_instance is None:
        with _ff77_lock:
            if _ff77_instance is None:
                _ff77_instance = FrequencyField77()
    return _ff77_instance


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def emit_visual_frequency(
    v1_features: Optional[Dict[str, Any]] = None,
    v2_features: Optional[Dict[str, Any]] = None,
    v4_features: Optional[Dict[str, Any]] = None,
    it_features: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    organ: Optional[str] = None
) -> bool:
    """
    Convert visual features to FF77 and emit.

    This is the main bridge between visual cards and the frequency field.
    """
    vec77 = visual_to_ff77(v1_features, v2_features, v4_features, it_features, meta)
    ff = get_frequency_field()
    ff.ingest(vec77)
    return ff.emit_frequency(vec77, organ=organ, plane="sensory", channel="visual")


def emit_visual_srm(
    image_id: str,
    features: Dict[str, Any],
    scene_type: str = "unknown"
) -> bool:
    """
    Emit SRM triples for visual features.

    Creates semantic relations like:
      - image_123 -> has_scene_type -> photo
      - image_123 -> has_dominant_color -> red
      - image_123 -> has_edge_density -> high
    """
    success = True

    # Scene type relation
    success &= emit_srm(
        subject=f"image:{image_id}",
        predicate="has_scene_type",
        obj=scene_type,
        strength=0.8,
        tags=["visual", "scene"]
    )

    # Color relations
    if "dominant_color" in features:
        success &= emit_srm(
            subject=f"image:{image_id}",
            predicate="has_dominant_color",
            obj=str(features["dominant_color"]),
            strength=0.7,
            tags=["visual", "color"]
        )

    # Edge density relation
    if "edge_density" in features:
        density = features["edge_density"]
        level = "high" if density > 0.5 else "medium" if density > 0.2 else "low"
        success &= emit_srm(
            subject=f"image:{image_id}",
            predicate="has_edge_density",
            obj=level,
            strength=0.6,
            tags=["visual", "v1"]
        )

    return success


# ═══════════════════════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("FREQUENCY FIELD 77 - Test")
    print("=" * 70)

    # Create field
    ff = get_frequency_field()

    # Test visual to FF77 conversion
    test_v1 = {"edge_density": 0.7, "orientations": {"0": 0.5, "45": 0.3, "90": 0.2}}
    test_v2 = {"contour_count": 50, "corner_count": 20, "contrast": 0.6}
    test_v4 = {"dominant_hue": 180, "saturation": 0.8, "colors": [(255, 0, 0), (0, 255, 0)]}
    test_it = {"scene_type": "photo", "complexity": 0.5}

    vec = visual_to_ff77(test_v1, test_v2, test_v4, test_it)
    print(f"\nConverted visual features to FF77:")
    print(f"  V1 bands (0-19):  {vec[0:5]}...")
    print(f"  V2 bands (20-39): {vec[20:25]}...")
    print(f"  V4 bands (40-59): {vec[40:45]}...")
    print(f"  IT bands (60-69): {vec[60:65]}...")
    print(f"  Meta bands (70-76): {vec[70:77]}")

    # Ingest
    ff.ingest(vec)
    print(f"\nIngested vector. Stats:")
    print(json.dumps(ff.get_stats(), indent=2))

    # Test SRM emission
    print("\nTesting SRM emission...")
    emit_visual_srm("test_123", {"dominant_color": "red", "edge_density": 0.7}, "photo")

    print("\n" + "=" * 70)
    print("FF77 Test Complete")
    print("=" * 70)
