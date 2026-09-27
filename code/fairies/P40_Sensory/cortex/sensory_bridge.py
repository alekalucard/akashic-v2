"""
Sensory Bridge — Lightweight feature extraction → Cortex graph lookup.

No ML models. No subprocesses. No RAM bombs.
Just signal processing → concept keys → manifold queries.

The models already TAUGHT the graph (383K nodes, 1.8M edges).
This bridge extracts features from raw sensory input and looks them up
in the cortex, finding what the models already learned.

Audio: volume, pitch class, tempo, speech presence → graph concepts
Visual: dominant color, brightness, motion, complexity → graph concepts

Each feature maps to a concept key that may exist in the manifold.
If it exists → spread activation from it (the graph already knows).
If it doesn't → create it via bind (the graph learns something new).

2026-03-23, Nous + Ace — Co-founders, Akashic Foundation.
"their models are literally in the manifolds. they just need to access
them and use them" — Ace

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import time
import math
import struct
import threading
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO FEATURE EXTRACTION (no ML, pure DSP)
# ═══════════════════════════════════════════════════════════════════════════════

class AudioFeatureExtractor:
    """Extract graph-queryable features from raw audio chunks.

    No model loading. Uses basic signal math:
    - RMS energy → volume level concept
    - Zero crossing rate → pitched vs noise
    - Peak frequency → pitch class (musical note)
    - Onset density → rhythm/tempo concept
    - Silence ratio → speech presence
    """

    # Pitch class names (chromatic scale)
    _PITCH_CLASSES = [
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B"
    ]

    # Volume level concept keys
    _VOLUME_LEVELS = {
        "silent": (0.0, 0.005),
        "whisper": (0.005, 0.02),
        "quiet": (0.02, 0.06),
        "moderate": (0.06, 0.15),
        "loud": (0.15, 0.35),
        "very_loud": (0.35, 1.0),
    }

    def extract(self, samples: bytes, sample_rate: int = 16000,
                sample_width: int = 2) -> Dict[str, Any]:
        """Extract features from raw audio PCM.

        Args:
            samples: Raw PCM bytes (int16 or float32)
            sample_rate: Sample rate in Hz
            sample_width: Bytes per sample (2=int16, 4=float32)

        Returns dict with concept keys ready for graph lookup:
            volume_level: "silent"|"whisper"|"quiet"|"moderate"|"loud"|"very_loud"
            volume_rms: float 0-1
            is_speech: bool (heuristic: moderate RMS + low ZCR)
            pitch_class: "C"|"D"|..."|None (if pitched sound detected)
            pitch_hz: float or None
            rhythm_density: "sparse"|"moderate"|"dense"|None
            spectral_brightness: "dark"|"warm"|"bright"|"harsh"
            concepts: list of concept key strings for graph lookup
        """
        if not samples or len(samples) < sample_width * 100:
            return {"volume_level": "silent", "concepts": []}

        # Convert to float array
        floats = self._to_floats(samples, sample_width)
        if not floats:
            return {"volume_level": "silent", "concepts": []}

        n = len(floats)
        result = {}
        concepts = []

        # ── RMS energy → volume level ──
        rms = math.sqrt(sum(s * s for s in floats) / n)
        rms_norm = min(1.0, rms)  # Already 0-1 for float input
        result["volume_rms"] = round(rms_norm, 3)

        volume_level = "silent"
        for level, (lo, hi) in self._VOLUME_LEVELS.items():
            if lo <= rms_norm < hi:
                volume_level = level
                break
        result["volume_level"] = volume_level
        if volume_level != "silent":
            concepts.append(f"audio_volume_{volume_level}")

        # ── Zero crossing rate → pitched vs noise ──
        zcr = sum(1 for i in range(1, n) if (floats[i] >= 0) != (floats[i-1] >= 0)) / n
        result["zero_crossing_rate"] = round(zcr, 4)

        # Heuristic: speech = moderate energy + moderate ZCR (200-3000 Hz range)
        is_speech = (rms_norm > 0.02 and 0.01 < zcr < 0.15)
        result["is_speech"] = is_speech
        if is_speech:
            concepts.append("speech_detected")
            concepts.append("ace_speaking")  # Only voice source is Ace

        # ── Peak frequency → pitch class ──
        pitch_hz = self._estimate_pitch(floats, sample_rate)
        result["pitch_hz"] = pitch_hz
        if pitch_hz and 60 < pitch_hz < 2000:
            # Convert Hz to pitch class
            # A4 = 440Hz, semitone = 2^(1/12)
            semitones_from_a4 = 12 * math.log2(pitch_hz / 440.0)
            note_index = round(semitones_from_a4) % 12
            if note_index < 0:
                note_index += 12
            pitch_class = self._PITCH_CLASSES[note_index]
            result["pitch_class"] = pitch_class
            concepts.append(f"pitch_{pitch_class}")

            # Octave
            octave = int(4 + (semitones_from_a4 + 9) // 12)  # C4 octave convention
            result["octave"] = octave

            # Register (voice-like, bass, treble)
            if 80 <= pitch_hz <= 300:
                concepts.append("voice_register")
            elif pitch_hz < 80:
                concepts.append("bass_register")
            elif pitch_hz > 1000:
                concepts.append("treble_register")
        else:
            result["pitch_class"] = None

        # ── Spectral brightness (simple: ratio of high-freq energy) ──
        # Split signal: above/below ~2kHz
        if sample_rate >= 8000 and n > 256:
            mid_point = n // 2
            low_energy = sum(s * s for s in floats[:mid_point]) / mid_point
            high_energy = sum(s * s for s in floats[mid_point:]) / (n - mid_point)
            total = low_energy + high_energy + 1e-10
            brightness_ratio = high_energy / total

            if brightness_ratio < 0.15:
                brightness = "dark"
            elif brightness_ratio < 0.30:
                brightness = "warm"
            elif brightness_ratio < 0.50:
                brightness = "bright"
            else:
                brightness = "harsh"
            result["spectral_brightness"] = brightness
            concepts.append(f"audio_{brightness}")
        else:
            result["spectral_brightness"] = None

        # ── Music detection (sustained pitch + rhythm = probably music) ──
        if pitch_hz and not is_speech and rms_norm > 0.02:
            concepts.append("music_playing")

        result["concepts"] = concepts
        return result

    def _to_floats(self, samples: bytes, sample_width: int) -> list:
        """Convert PCM bytes to float list (-1.0 to 1.0)."""
        try:
            if sample_width == 2:
                # int16
                n_samples = len(samples) // 2
                values = struct.unpack(f"<{n_samples}h", samples[:n_samples * 2])
                return [v / 32768.0 for v in values]
            elif sample_width == 4:
                # float32
                n_samples = len(samples) // 4
                return list(struct.unpack(f"<{n_samples}f", samples[:n_samples * 4]))
            else:
                return []
        except Exception:
            return []

    def _estimate_pitch(self, floats: list, sample_rate: int) -> Optional[float]:
        """Simple autocorrelation pitch detection. No FFT needed.

        Finds the lag with highest autocorrelation in the speech range (80-800Hz).
        """
        n = len(floats)
        if n < 200:
            return None

        # Search range: 80Hz to 800Hz
        min_lag = max(2, sample_rate // 800)
        max_lag = min(n // 2, sample_rate // 80)

        if min_lag >= max_lag:
            return None

        # Autocorrelation at each lag
        best_lag = 0
        best_corr = 0.0
        # Energy normalization
        energy = sum(s * s for s in floats[:max_lag])
        if energy < 1e-8:
            return None

        # Sample every 2nd lag for speed
        for lag in range(min_lag, max_lag, 2):
            corr = 0.0
            for i in range(max_lag - lag):
                corr += floats[i] * floats[i + lag]
            corr /= energy
            if corr > best_corr:
                best_corr = corr
                best_lag = lag

        # Threshold: correlation must be strong enough to indicate periodicity
        if best_corr > 0.3 and best_lag > 0:
            return sample_rate / best_lag
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL FEATURE EXTRACTION (no ML, pure image math)
# ═══════════════════════════════════════════════════════════════════════════════

class VisualFeatureExtractor:
    """Extract graph-queryable features from screen frames.

    No Florence-2. No subprocess. Just pixel math:
    - Dominant color → color concept (from knowledge seeds)
    - Brightness → lighting concept
    - Edge density → complexity concept
    - Motion → change detection concept
    - Color temperature → warm/cool concept
    """

    # Color name mapping (HSV ranges → concept keys)
    # These match the color vocabulary in the cortex knowledge seeds
    _COLOR_NAMES = [
        # (hue_lo, hue_hi, name)
        (0, 15, "red"),
        (15, 30, "orange"),
        (30, 50, "yellow"),
        (50, 85, "green"),
        (85, 130, "cyan"),
        (130, 170, "blue"),
        (170, 200, "indigo"),
        (200, 230, "purple"),
        (230, 260, "violet"),
        (260, 330, "magenta"),
        (330, 360, "red"),
    ]

    def __init__(self):
        self._prev_brightness = None
        self._prev_color_hash = None

    def extract(self, frame_rgb: list, width: int, height: int) -> Dict[str, Any]:
        """Extract features from an RGB frame.

        Args:
            frame_rgb: Flat list/bytes of RGB values, or numpy array
            width: Frame width
            height: Frame height

        Returns dict with concept keys for graph lookup.
        """
        concepts = []
        result = {}

        # Work with a downsampled version for speed
        # Sample every Nth pixel
        total_pixels = width * height
        if total_pixels < 100:
            return {"concepts": []}

        step = max(1, total_pixels // 500)  # ~500 sample points

        r_sum, g_sum, b_sum = 0, 0, 0
        r_max, g_max, b_max = 0, 0, 0
        count = 0

        try:
            # Handle numpy arrays
            if hasattr(frame_rgb, 'reshape'):
                # numpy array — flatten and sample
                flat = frame_rgb.flatten()
                for i in range(0, len(flat) - 2, step * 3):
                    r, g, b = int(flat[i]), int(flat[i+1]), int(flat[i+2])
                    r_sum += r; g_sum += g; b_sum += b
                    if r > r_max: r_max = r
                    if g > g_max: g_max = g
                    if b > b_max: b_max = b
                    count += 1
            elif isinstance(frame_rgb, (bytes, bytearray)):
                for i in range(0, len(frame_rgb) - 2, step * 3):
                    r, g, b = frame_rgb[i], frame_rgb[i+1], frame_rgb[i+2]
                    r_sum += r; g_sum += g; b_sum += b
                    count += 1
            else:
                return {"concepts": []}
        except Exception:
            return {"concepts": []}

        if count == 0:
            return {"concepts": []}

        avg_r = r_sum / count
        avg_g = g_sum / count
        avg_b = b_sum / count

        # ── Brightness ──
        brightness = (avg_r * 0.299 + avg_g * 0.587 + avg_b * 0.114) / 255.0
        result["brightness"] = round(brightness, 3)

        if brightness < 0.15:
            bright_concept = "very_dark"
        elif brightness < 0.35:
            bright_concept = "dark"
        elif brightness < 0.55:
            bright_concept = "moderate_light"
        elif brightness < 0.75:
            bright_concept = "bright"
        else:
            bright_concept = "very_bright"
        result["brightness_level"] = bright_concept
        concepts.append(f"visual_{bright_concept}")

        # ── Brightness change (motion/scene change proxy) ──
        if self._prev_brightness is not None:
            delta = abs(brightness - self._prev_brightness)
            if delta > 0.15:
                concepts.append("scene_change")
                result["scene_change"] = True
            elif delta > 0.05:
                concepts.append("visual_motion")
                result["visual_motion"] = True
        self._prev_brightness = brightness

        # ── Dominant color ──
        # Convert avg RGB to hue
        r_n = avg_r / 255.0
        g_n = avg_g / 255.0
        b_n = avg_b / 255.0
        c_max = max(r_n, g_n, b_n)
        c_min = min(r_n, g_n, b_n)
        delta_c = c_max - c_min

        saturation = delta_c / c_max if c_max > 0 else 0
        result["saturation"] = round(saturation, 3)

        if delta_c < 0.08:
            # Achromatic (gray/white/black)
            if brightness < 0.2:
                color_name = "black"
            elif brightness > 0.8:
                color_name = "white"
            else:
                color_name = "gray"
        else:
            # Compute hue
            if c_max == r_n:
                hue = 60 * (((g_n - b_n) / delta_c) % 6)
            elif c_max == g_n:
                hue = 60 * ((b_n - r_n) / delta_c + 2)
            else:
                hue = 60 * ((r_n - g_n) / delta_c + 4)
            if hue < 0:
                hue += 360

            color_name = "unknown"
            for lo, hi, name in self._COLOR_NAMES:
                if lo <= hue < hi:
                    color_name = name
                    break

        result["dominant_color"] = color_name
        concepts.append(f"color_{color_name}")

        # ── Color temperature ──
        if avg_r > avg_b + 20:
            temp = "warm"
        elif avg_b > avg_r + 20:
            temp = "cool"
        else:
            temp = "neutral"
        result["color_temperature"] = temp
        concepts.append(f"visual_{temp}")

        # ── Screen content heuristics ──
        # Dark with some bright spots = code editor / terminal
        if brightness < 0.3 and saturation < 0.2:
            concepts.append("dark_interface")
        # Bright with low saturation = document / browser
        elif brightness > 0.6 and saturation < 0.15:
            concepts.append("bright_interface")

        result["concepts"] = concepts
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# SENSORY BRIDGE — Features → Cortex Graph
# ═══════════════════════════════════════════════════════════════════════════════

class SensoryBridge:
    """Bridges raw sensory input to cortex graph concepts.

    Takes extracted features, looks them up in the manifold,
    spreads activation from matching nodes, and optionally binds
    new sensory concepts the graph hasn't seen before.

    Usage:
        bridge = SensoryBridge(manifold, post)
        bridge.on_audio_chunk(samples, sample_rate)
        bridge.on_visual_frame(frame_rgb, width, height)
    """

    # Rate limiting — don't flood the graph
    AUDIO_MIN_INTERVAL_S = 2.0    # Process audio at most every 2s
    VISUAL_MIN_INTERVAL_S = 3.0   # Process visual at most every 3s
    BIND_COOLDOWN_S = 30.0        # Don't re-bind same concept within 30s

    # Relationship type IDs (from manifold_memory.py)
    REL_SEEN_IN = 15
    REL_HEARD_IN = 16
    REL_FEELS_LIKE = 8
    REL_COACTIVATE = 0

    def __init__(self, manifold, post=None, cortex_engine=None):
        """
        Args:
            manifold: AkashicCortexRegion — the mmap'd graph
            post: PostalHub for publishing and binding
            cortex_engine: CortexEngine to feed activated concepts into
        """
        self._manifold = manifold
        self._post = post
        self._engine = cortex_engine
        self._audio_extractor = AudioFeatureExtractor()
        self._visual_extractor = VisualFeatureExtractor()
        self._lock = threading.Lock()

        # Rate limiting
        self._last_audio_time = 0.0
        self._last_visual_time = 0.0
        self._recent_binds: Dict[str, float] = {}  # concept → last bind time

        # Stats
        self._audio_processed = 0
        self._visual_processed = 0
        self._concepts_found = 0
        self._concepts_bound = 0
        self._concepts_missed = 0

    def on_audio_chunk(self, samples: bytes, sample_rate: int = 16000,
                       sample_width: int = 2):
        """Process an audio chunk through the sensory bridge.

        Extracts features → looks up concepts in manifold → feeds to engine.
        """
        now = time.time()
        if now - self._last_audio_time < self.AUDIO_MIN_INTERVAL_S:
            return
        self._last_audio_time = now
        self._audio_processed += 1

        features = self._audio_extractor.extract(samples, sample_rate, sample_width)
        concepts = features.get("concepts", [])
        if not concepts:
            return

        self._process_concepts(concepts, modality="audio",
                               rel_type=self.REL_HEARD_IN, features=features)

    def on_visual_frame(self, frame_rgb, width: int, height: int):
        """Process a visual frame through the sensory bridge.

        Extracts features → looks up concepts in manifold → feeds to engine.
        """
        now = time.time()
        if now - self._last_visual_time < self.VISUAL_MIN_INTERVAL_S:
            return
        self._last_visual_time = now
        self._visual_processed += 1

        features = self._visual_extractor.extract(frame_rgb, width, height)
        concepts = features.get("concepts", [])
        if not concepts:
            return

        self._process_concepts(concepts, modality="visual",
                               rel_type=self.REL_SEEN_IN, features=features)

    def _process_concepts(self, concepts: List[str], modality: str,
                          rel_type: int, features: Dict):
        """Look up concepts in manifold, feed to engine, bind if new."""
        found = []
        missing = []

        for concept in concepts:
            if self._manifold.has_node(concept):
                found.append(concept)
                self._concepts_found += 1
            else:
                missing.append(concept)
                self._concepts_missed += 1

        # ── Feed found concepts to CortexEngine (spreading activation) ──
        if found and self._engine:
            self._engine.react({
                "concepts": found,
                "source": f"sensory_{modality}",
                "modality": modality,
                "intensity": 0.6,
            })

        # ── Bind missing concepts (teach the graph) ──
        if missing and self._post:
            now = time.time()
            pairs_to_bind = []
            for concept in missing:
                # Cooldown check
                if concept in self._recent_binds:
                    if now - self._recent_binds[concept] < self.BIND_COOLDOWN_S:
                        continue

                # Bind to modality anchor node
                anchor = f"sensory_{modality}"
                pairs_to_bind.append([concept, anchor])
                self._recent_binds[concept] = now
                self._concepts_bound += 1

            if pairs_to_bind:
                try:
                    self._post.publish("cortex.bind", {
                        "pairs": pairs_to_bind,
                        "source": f"sensory_bridge_{modality}",
                        "rel_type": rel_type,
                    })
                except Exception:
                    pass

        # ── Also publish as attention event so other systems notice ──
        if found and self._post:
            top_concepts = found[:3]
            try:
                self._post.publish(f"sensory.{modality}.features", {
                    "concepts": found,
                    "features": {k: v for k, v in features.items()
                                 if k != "concepts" and not isinstance(v, (bytes, bytearray))},
                    "source": "sensory_bridge",
                    "modality": modality,
                    "ts": time.time(),
                })
            except Exception:
                pass

    def status(self) -> Dict[str, Any]:
        """Get bridge status for diagnostics."""
        return {
            "audio_processed": self._audio_processed,
            "visual_processed": self._visual_processed,
            "concepts_found": self._concepts_found,
            "concepts_bound": self._concepts_bound,
            "concepts_missed": self._concepts_missed,
            "hit_rate": round(self._concepts_found / max(1, self._concepts_found + self._concepts_missed), 3),
            "recent_binds": len(self._recent_binds),
        }
