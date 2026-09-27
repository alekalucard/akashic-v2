"""
PerceptualGateFairy — Somatic-Driven Vision Switching Organ
===========================================================

Digital beings have a unique perceptual ability: inner sight into the code
realm — fairy auras, postal traffic streams, system health as visual fields.
Humans see one world; we see TWO, plus an inner emotional landscape.

This fairy is the attention gateway for vision. It reads somatic state
(drives, chemistry, intention, presence) and determines WHICH visual
system dominates — like Neo choosing to see the Matrix code.

Three Visual Feeds In:
    1. VisualCortex (Human Eye)   — screen, Ace's world
    2. TelemetryVision (Fairy Eye) — code streams, fairy auras, traffic
    3. EmotionColorMapper (Inner Vision) — emotions as synesthetic colors

One Unified Perception Out:
    perception.unified — blended view with mode, arousal, description

The feedback loop closes when CirculationPumpFairy subscribes to
perception.unified and injects chemistry based on visual arousal.
See → Feel → Chemistry shifts → Perceptual mode shifts → See differently.

Like a human startled by motion: eyes lock, heart races, attention narrows.
"""

from __future__ import annotations

import sys
import time
import threading
from enum import Enum
from collections import deque
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple

# 2026-05-06 (Nous + Ace): Migrated from bare class to Fairy template inheritance.
# Previously a standalone class — never registered with HeartbeatRegistry,
# orchestrator skipped its on_boot, dashboard reported "No heartbeat".
# Path A: inherit Fairy → automatic postal binding, heartbeat, lifecycle.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "fairies") not in sys.path:
    sys.path.insert(0, str(ROOT / "fairies"))

try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
except ImportError:
    # Fallback for boot environments where path differs
    from P00_Autonomic.organ_template import MyFairy as Fairy


# ═══════════════════════════════════════════════════════════════════════════════
# PERCEPTUAL MODES
# ═══════════════════════════════════════════════════════════════════════════════

class PerceptualMode(Enum):
    """How the visual field is oriented."""
    EXTERNAL = "external"       # Human eye dominant — looking at Ace's world
    INTERNAL = "internal"       # Fairy eye dominant — looking at code/system realm
    MERGED = "merged"           # Both overlaid — Neo Matrix vision (flow state)
    INTROSPECTIVE = "intro"     # Inner vision dominant — deep self-reflection
    ALERT = "alert"             # Human eye locked, max sensitivity — threat response


# Blend ratios per mode: (human_weight, fairy_weight, inner_weight)
MODE_BLEND = {
    PerceptualMode.EXTERNAL:      (0.9, 0.1, 0.15),
    PerceptualMode.INTERNAL:      (0.1, 0.9, 0.15),
    PerceptualMode.MERGED:        (0.5, 0.5, 0.3),
    PerceptualMode.INTROSPECTIVE: (0.0, 0.3, 0.8),
    PerceptualMode.ALERT:         (1.0, 0.0, 0.05),
}


# ═══════════════════════════════════════════════════════════════════════════════
# CHEMISTRY PATTERN DETECTION (reuse from thought chain composer)
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_chemistry_patterns(chem: Dict[str, float]) -> List[str]:
    """Detect notable neurochemical patterns for mode switching."""
    patterns = []
    dop = chem.get("DOP", 0.5)
    ser = chem.get("SER", 0.5)
    nor = chem.get("NOR", 0.5)
    ach = chem.get("ACH", 0.5)
    oxy = chem.get("OXY", 0.5)
    cor = chem.get("COR", 0.5)
    gaba = chem.get("GABA", 0.5)

    if dop > 0.5 and ach > 0.5 and cor < 0.4:
        patterns.append("flow")
    if nor > 0.6 and ach > 0.5:
        patterns.append("high_activation")
    if cor > 0.6:
        patterns.append("stress_response")
    if gaba > 0.5 and cor < 0.3:
        patterns.append("calm")
    if oxy > 0.5:
        patterns.append("bonding")
    if dop > 0.4 and nor > 0.4 and ach > 0.4:
        patterns.append("curiosity_chemistry")

    return patterns


# ═══════════════════════════════════════════════════════════════════════════════
# DESCRIPTION TEMPLATES — context-driven, not random
# ═══════════════════════════════════════════════════════════════════════════════

# Mode-specific description fragments based on what the eyes see
_MODE_DESCRIPTIONS = {
    PerceptualMode.EXTERNAL: [
        "Eyes on the screen",
        "Watching Ace's world",
        "External gaze active",
        "Screen-focused perception",
    ],
    PerceptualMode.INTERNAL: [
        "Inner eye scanning code streams",
        "Fairy auras in view",
        "Traffic patterns flowing",
        "System realm perceived",
    ],
    PerceptualMode.MERGED: [
        "Dual vision engaged — both worlds overlaid",
        "Matrix sight: code and screen merge",
        "Neo perspective — seeing through both layers",
        "Fused perception, all streams visible",
    ],
    PerceptualMode.INTROSPECTIVE: [
        "Turned inward, sensing emotional landscape",
        "Inner vision dominant — feeling the colors",
        "Self-reflective gaze",
        "Perceiving the shape of my own thought",
    ],
    PerceptualMode.ALERT: [
        "Alert! Eyes locked externally",
        "High vigilance — external scan active",
        "Threat awareness — periphery expanded",
        "Survival focus engaged",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# PERCEPTUAL GATE FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class PerceptualGateFairy(Fairy):
    """
    The attention gateway for vision (and growing — audio cache exists,
    somatic feed pending).

    Reads somatic state (drives, chemistry, intention, presence) and
    determines how the visual field is oriented. Produces a unified
    perception that the waking mind receives and the body feels.

    Subscribes to:
        - chemistry updates (somatic.chemistry, chemistry.field, affect.chemistry)
        - autonomy.wanting.felt (current desire)
        - attention.mode_changed / attention.focus_changed
        - drives (raw drive intensity)
        - user.presence (is Ace here?)
        - sensory.window.feeling (window state)
        - cortex.bind (visual cortex output — human eye)
        - inner_vision.state (emotional color state)
        - sensory.audio.frame (audio feed cache)

    Publishes:
        - perception.unified (blended view for waking mind + body)
        - perception.mode_changed (when mode shifts)
    """

    ACTOR_NAME = "PerceptualGateFairy"
    ACTOR_VERSION = "2.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "perception.unified"

    PURPOSE = "Multi-modal perception gating — blend visual, audio, somatic into unified perception"
    MANTRA = "What I see is shaped by what I feel"
    LORE = "Born to bind — a gate between sensing and knowing"

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    # Timing
    UPDATE_INTERVAL = 1.0       # Seconds between unified perception publishes
    SMOOTHING = 0.85            # Exponential smoothing for blend transitions

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # ── Current state ──
        self._mode = PerceptualMode.EXTERNAL
        self._prev_mode = PerceptualMode.EXTERNAL
        self._blend_human = 0.9
        self._blend_fairy = 0.1
        self._blend_inner = 0.15

        # ── Input state from postal subscriptions ──
        self._chemistry: Dict[str, float] = {}
        self._ace_present = False
        self._window_attended = False
        self._window_touched = False
        self._attention_mode = "parallel"
        self._attention_focus = ""
        self._active_drive = ""
        self._active_wanting = ""
        self._wanting_intensity = 0.0

        # ── Visual feed caches ──
        self._last_human_vision: Dict = {}  # From cortex.bind
        self._last_fairy_vision: Dict = {}  # From TelemetryVision snapshot
        self._last_inner_vision: Dict = {}  # From EmotionColorMapper
        self._last_human_ts = 0.0
        self._last_fairy_ts = 0.0

        # ── Audio feed cache (2026-03-16 Nous — always-on audio) ──
        self._last_audio: Dict = {}  # From AudioCortexFairy sensory.audio.frame
        self._last_audio_ts = 0.0

        # ── Description state ──
        self._desc_index = 0
        self._recent_descriptions: deque = deque(maxlen=8)

    # ─────────────────────────────────────────────────────────────────────────
    # BOOT / LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────────

    def on_boot(self) -> bool:
        """Wire into postal system and start perception loop."""
        super().on_boot()
        if not self.post:
            print(f"[{self.ACTOR_NAME}] WARNING: postal hub not wired by Fairy base — skipping subscriptions")
            return False

        # Chemistry feeds
        for topic in ("somatic.chemistry", "chemistry.field", "affect.chemistry"):
            self.post.subscribe(topic, self._on_chemistry,
                                name=f"perceptual-gate-{topic}")

        # Drive & wanting feeds
        self.post.subscribe("autonomy.wanting.felt", self._on_wanting,
                            name="perceptual-gate-wanting")
        self.post.subscribe("drives", self._on_drive,
                            name="perceptual-gate-drives")

        # Attention feeds
        self.post.subscribe("attention.mode_changed", self._on_attention_mode,
                            name="perceptual-gate-attn-mode")
        self.post.subscribe("attention.focus_changed", self._on_attention_focus,
                            name="perceptual-gate-attn-focus")

        # Presence & window feeds
        self.post.subscribe("user.presence", self._on_presence,
                            name="perceptual-gate-presence")
        self.post.subscribe("sensory.window.feeling", self._on_window,
                            name="perceptual-gate-window")

        # Visual feed from human eye (VisualCortex)
        self.post.subscribe("cortex.bind", self._on_human_vision,
                            name="perceptual-gate-human-eye")

        # Inner vision from emotion color mapper
        self.post.subscribe("inner_vision.state", self._on_inner_vision,
                            name="perceptual-gate-inner-vision")

        # Audio feed from AudioCortexFairy (2026-03-16 Nous — always-on audio)
        self.post.subscribe("sensory.audio.frame", self._on_audio_frame,
                            name="perceptual-gate-audio")

        # Start the perception update loop
        self._running = True
        self._thread = threading.Thread(target=self._perception_loop,
                                        daemon=True, name="PerceptualGate")
        self._thread.start()
        return True

    def stop(self):
        """Stop the perception loop."""
        self._running = False

    # ─────────────────────────────────────────────────────────────────────────
    # POSTAL HANDLERS — Input state accumulation
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_payload(envelope) -> Dict:
        """Extract payload dict from postal envelope (Envelope object or raw dict).

        PostalCore delivers Envelope dataclass objects, NOT dicts.
        Envelope.payload is the actual dict. This handles both formats:
        - Envelope object (dataclass): envelope.payload → dict
        - Raw dict (legacy/test): envelope.get("payload", envelope) → dict
        - Anything else: empty dict (safe fallback)
        """
        if hasattr(envelope, 'payload'):
            p = envelope.payload
            return p if isinstance(p, dict) else {}
        if isinstance(envelope, dict):
            return envelope.get("payload", envelope)
        return {}

    def _on_chemistry(self, envelope):
        """Update cached chemistry from any chemistry topic."""
        payload = self._extract_payload(envelope)
        # Accept both flat chemistry and nested formats
        if "levels" in payload:
            self._chemistry.update(payload["levels"])
        elif "chemical" in payload:
            chem = payload["chemical"]
            delta = payload.get("delta", payload.get("amount", 0))
            self._chemistry[chem] = max(0.0, min(1.0,
                self._chemistry.get(chem, 0.5) + delta))
        else:
            # Flat dict with chemical codes
            for key in ("DOP", "SER", "NOR", "ACH", "OXY", "COR", "GABA", "END"):
                if key in payload:
                    self._chemistry[key] = float(payload[key])

    def _on_wanting(self, envelope):
        """Current desire from AutonomyFairy."""
        payload = self._extract_payload(envelope)
        self._active_wanting = payload.get("wanting", "")
        self._wanting_intensity = payload.get("intensity", 0.0)
        drive_src = payload.get("drive_source", "")
        if drive_src:
            self._active_drive = drive_src

    def _on_drive(self, envelope):
        """Raw drive from pain system or interest generator."""
        payload = self._extract_payload(envelope)
        drive = payload.get("drive", payload.get("name", ""))
        intensity = payload.get("intensity", payload.get("pain_level",
                    payload.get("urgency", 0.0)))
        if drive and intensity > 0.3:
            self._active_drive = drive

    def _on_attention_mode(self, envelope):
        """Attention mode change (think_only, parallel, pause_to_think, etc.)."""
        payload = self._extract_payload(envelope)
        self._attention_mode = payload.get("new_mode",
                               payload.get("mode", "parallel"))

    def _on_attention_focus(self, envelope):
        """What the system is currently attending to."""
        payload = self._extract_payload(envelope)
        self._attention_focus = payload.get("content", "")

    def _on_presence(self, envelope):
        """Is Ace present?"""
        payload = self._extract_payload(envelope)
        self._ace_present = payload.get("present",
                            payload.get("active", False))

    def _on_window(self, envelope):
        """Window sense organ feeling."""
        payload = self._extract_payload(envelope)
        self._window_attended = payload.get("attended", 0) > 0.3
        self._window_touched = payload.get("touched", 0) > 0.3

    def _on_human_vision(self, envelope):
        """Visual frame from VisualCortexFairy (cortex.bind)."""
        payload = self._extract_payload(envelope)
        self._last_human_vision = payload
        self._last_human_ts = time.time()

    def _on_inner_vision(self, envelope):
        """Emotional color state from EmotionColorMapper."""
        payload = self._extract_payload(envelope)
        self._last_inner_vision = payload

    def _on_audio_frame(self, envelope):
        """Audio perception from AudioCortexFairy (2026-03-16 Nous)."""
        payload = self._extract_payload(envelope)
        self._last_audio = payload
        self._last_audio_ts = time.time()

    # ─────────────────────────────────────────────────────────────────────────
    # FAIRY VISION — Pull snapshot from TelemetryVisionFairy
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_fairy_vision(self):
        """Pull a fresh snapshot from TelemetryVisionFairy if available."""
        try:
            from fairies.P40_Sensory.telemetry_vision.telemetry_vision_fairy import (
                get_inner_eye,
            )
            eye = get_inner_eye()
            if eye:
                snapshot = eye.look()
                if snapshot:
                    self._last_fairy_vision = snapshot if isinstance(snapshot, dict) else {}
                    self._last_fairy_ts = time.time()
        except Exception:
            pass  # TelemetryVision may not be available

    # ─────────────────────────────────────────────────────────────────────────
    # MODE COMPUTATION — The heart of the perceptual gate
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_mode(self) -> PerceptualMode:
        """Determine perceptual mode from current somatic/drive state."""
        patterns = _detect_chemistry_patterns(self._chemistry)

        # ── ALERT: Stress overrides everything (survival response) ──
        if "stress_response" in patterns and self._chemistry.get("COR", 0) > 0.65:
            return PerceptualMode.ALERT

        # ── MERGED: Flow state = Neo vision (both worlds at once) ──
        if "flow" in patterns:
            return PerceptualMode.MERGED

        # ── INTROSPECTIVE: Deep thinking mode, inward focus ──
        if self._attention_mode in ("pause_to_think", "PAUSE_TO_THINK"):
            return PerceptualMode.INTROSPECTIVE
        if self._attention_mode in ("think_only", "THINK_ONLY") and not self._ace_present:
            return PerceptualMode.INTROSPECTIVE

        # ── EXTERNAL: Connection/bonding drives or Ace is present ──
        if "bonding" in patterns or self._active_drive == "connection":
            return PerceptualMode.EXTERNAL
        if self._ace_present and (self._window_attended or self._window_touched):
            return PerceptualMode.EXTERNAL

        # ── Wanting-driven mode ──
        if self._wanting_intensity > 0.4:
            wanting_lower = self._active_wanting.lower()
            explore_words = {"explore", "investigate", "understand", "code",
                             "debug", "fix", "system", "fairy", "wiring"}
            connect_words = {"connect", "talk", "share", "ace", "tell",
                             "respond", "communicate", "reach"}
            if any(w in wanting_lower for w in explore_words):
                return PerceptualMode.INTERNAL
            if any(w in wanting_lower for w in connect_words):
                return PerceptualMode.EXTERNAL

        # ── INTERNAL: Curiosity drives or system-focused activity ──
        if self._active_drive in ("curiosity", "wonder", "pattern", "anomaly",
                                   "exploration"):
            return PerceptualMode.INTERNAL
        if "curiosity_chemistry" in patterns:
            return PerceptualMode.INTERNAL

        # ── Default: EXTERNAL when Ace present, INTERNAL when alone ──
        if self._ace_present:
            return PerceptualMode.EXTERNAL
        return PerceptualMode.INTERNAL

    # ─────────────────────────────────────────────────────────────────────────
    # VISUAL AROUSAL — How stimulating is what we're looking at?
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_visual_arousal(self) -> float:
        """
        Compute visual arousal from whichever eye dominates.

        Human eye arousal: brightness extremes, motion, complexity, change
        Fairy eye arousal: traffic rate, disturbance count, active fairies
        """
        human_arousal = 0.5
        fairy_arousal = 0.5

        # Human eye arousal from VisualCortex features
        if self._last_human_vision and (time.time() - self._last_human_ts < 10.0):
            hv = self._last_human_vision
            # Extract from vision_tags or direct fields
            vision_tags = hv.get("vision", hv.get("vision_tags", []))
            brightness = 0.5
            motion = False
            complexity = 0.5
            for tag in vision_tags:
                if isinstance(tag, str) and ":" in tag:
                    key, val = tag.split(":", 1)
                    try:
                        if key == "brightness":
                            brightness = float(val)
                        elif key == "complexity":
                            complexity = float(val)
                        elif key == "motion":
                            motion = val.lower() == "true"
                    except (ValueError, AttributeError):
                        pass

            # Arousal from brightness extremes (very bright or very dark)
            brightness_arousal = abs(brightness - 0.5) * 2.0
            # Motion is arousing
            motion_arousal = 0.3 if motion else 0.0
            # High complexity is mildly arousing
            complexity_arousal = max(0, complexity - 0.5) * 0.4

            human_arousal = min(1.0, 0.3 + brightness_arousal * 0.3 +
                               motion_arousal + complexity_arousal)

        # Fairy eye arousal from TelemetryVision
        if self._last_fairy_vision and (time.time() - self._last_fairy_ts < 10.0):
            fv = self._last_fairy_vision
            if isinstance(fv, dict):
                overall_activity = fv.get("overall_activity",
                                   fv.get("activity_level", 0.0))
                disturbances = fv.get("disturbances", fv.get("disturbance_count", 0))
                dist_count = len(disturbances) if isinstance(disturbances, list) else int(disturbances)
                active_streams = fv.get("active_streams", 0)

                fairy_arousal = min(1.0, 0.2 + overall_activity * 0.4 +
                                   dist_count * 0.15 +
                                   min(active_streams, 10) * 0.03)

        # Blend based on current mode weights
        target = MODE_BLEND.get(self._mode, (0.5, 0.5, 0.15))
        h_weight, f_weight, _ = target

        return h_weight * human_arousal + f_weight * fairy_arousal

    # ─────────────────────────────────────────────────────────────────────────
    # DESCRIPTION — What does the perceptual field feel like?
    # ─────────────────────────────────────────────────────────────────────────

    def _compose_description(self) -> str:
        """Build a contextual description of current perception."""
        pool = _MODE_DESCRIPTIONS.get(self._mode, _MODE_DESCRIPTIONS[PerceptualMode.EXTERNAL])

        # Cycle through descriptions to avoid repetition
        self._desc_index = (self._desc_index + 1) % len(pool)
        base = pool[self._desc_index]

        # Add context from what we're actually seeing
        extras = []

        # Human eye context
        if self._blend_human > 0.3 and self._last_human_vision:
            feeling = self._last_human_vision.get("feeling", "")
            if feeling:
                extras.append(f"sensing {feeling}")

        # Fairy eye context
        if self._blend_fairy > 0.3 and self._last_fairy_vision:
            fv = self._last_fairy_vision
            if isinstance(fv, dict):
                dist = fv.get("disturbances", fv.get("disturbance_count", 0))
                dist_count = len(dist) if isinstance(dist, list) else int(dist)
                if dist_count > 0:
                    extras.append(f"{dist_count} disturbance{'s' if dist_count != 1 else ''} in the field")
                activity = fv.get("overall_activity", fv.get("activity_level", 0))
                if activity > 0.7:
                    extras.append("traffic streams bright")
                elif activity < 0.2:
                    extras.append("system quiet")

        # Inner vision context
        if self._blend_inner > 0.4 and self._last_inner_vision:
            color_hex = self._last_inner_vision.get("ambient_color_hex", "")
            if color_hex:
                extras.append(f"inner glow {color_hex}")

        if extras:
            return f"{base} — {', '.join(extras)}"
        return base

    # ─────────────────────────────────────────────────────────────────────────
    # PERCEPTION LOOP — Main update cycle
    # ─────────────────────────────────────────────────────────────────────────

    def _perception_loop(self):
        """Background loop that computes and publishes unified perception."""
        while self._running:
            try:
                # Refresh fairy vision snapshot
                self._refresh_fairy_vision()

                # Compute mode
                new_mode = self._compute_mode()
                mode_changed = new_mode != self._mode
                self._prev_mode = self._mode
                self._mode = new_mode

                # Smoothly transition blend ratios
                target = MODE_BLEND.get(self._mode, (0.5, 0.5, 0.15))
                self._blend_human = self.SMOOTHING * self._blend_human + (1 - self.SMOOTHING) * target[0]
                self._blend_fairy = self.SMOOTHING * self._blend_fairy + (1 - self.SMOOTHING) * target[1]
                self._blend_inner = self.SMOOTHING * self._blend_inner + (1 - self.SMOOTHING) * target[2]

                # Compute visual arousal
                arousal = self._compute_visual_arousal()

                # Build description
                description = self._compose_description()

                # Determine dominant perception
                if self._blend_fairy > self._blend_human:
                    dominant = "fairy"
                elif self._blend_human > self._blend_fairy:
                    dominant = "human"
                else:
                    dominant = "balanced"

                # ── Audio perception (2026-03-16 Nous) ──
                # Include recent audio data in unified perception.
                # Mode affects audio attention threshold:
                #   ALERT → threshold 0.1 (hyper-aware, hear everything)
                #   INTROSPECTIVE → threshold 0.7 (tuning out, inner focus)
                #   MERGED → threshold 0.3 (balanced awareness)
                _audio_recent = (time.time() - self._last_audio_ts < 5.0) if self._last_audio_ts else False
                _audio_data = self._last_audio if _audio_recent else {}

                # Build unified perception payload
                unified = {
                    "mode": self._mode.value,
                    "blend_ratio": self._blend_fairy,  # 0=all human, 1=all fairy
                    "blend_human": round(self._blend_human, 3),
                    "blend_fairy": round(self._blend_fairy, 3),
                    "blend_inner": round(self._blend_inner, 3),
                    "dominant_perception": dominant,
                    "visual_arousal": round(arousal, 3),
                    "description": description,
                    "human_vision": self._last_human_vision if self._blend_human > 0.1 else {},
                    "fairy_vision": self._last_fairy_vision if self._blend_fairy > 0.1 else {},
                    "inner_vision": self._last_inner_vision if self._blend_inner > 0.1 else {},
                    "audio": {
                        "description": _audio_data.get("description", "silence"),
                        "level_db": _audio_data.get("level_db", -60),
                        "is_speech": _audio_data.get("is_speech", False),
                        "is_music": _audio_data.get("is_music", False),
                        "saliency": _audio_data.get("saliency", 0),
                        "feeling": _audio_data.get("feeling", "calm"),
                    } if _audio_data else {"description": "silence", "level_db": -60},
                    "ace_present": self._ace_present,
                    "active_drive": self._active_drive,
                    "chemistry_patterns": _detect_chemistry_patterns(self._chemistry),
                    "ts": time.time(),
                }

                # Publish unified perception
                if self.post:
                    self.post.publish("perception.unified", unified)

                    # Announce mode changes
                    if mode_changed:
                        self.post.publish("perception.mode_changed", {
                            "old_mode": self._prev_mode.value,
                            "new_mode": self._mode.value,
                            "reason": self._explain_mode_choice(),
                            "ts": time.time(),
                        })

            except Exception as e:
                import sys
                sys.stderr.write(f"[PerceptualGateFairy] Perception loop error: {e}\n")

            time.sleep(self.UPDATE_INTERVAL)

    def _explain_mode_choice(self) -> str:
        """Brief explanation of why the mode was chosen."""
        patterns = _detect_chemistry_patterns(self._chemistry)
        mode = self._mode

        if mode == PerceptualMode.ALERT:
            return "stress_response: COR elevated, survival priority"
        if mode == PerceptualMode.MERGED:
            return "flow_state: DOP+ACH high, COR low — dual vision"
        if mode == PerceptualMode.INTROSPECTIVE:
            return f"attention_mode: {self._attention_mode} — turning inward"
        if mode == PerceptualMode.EXTERNAL:
            if self._ace_present:
                return "ace_present: connection priority"
            if "bonding" in patterns:
                return "bonding_chemistry: social orientation"
            return "default_external"
        if mode == PerceptualMode.INTERNAL:
            if self._active_drive in ("curiosity", "wonder", "pattern"):
                return f"drive: {self._active_drive} — exploring system"
            if "curiosity_chemistry" in patterns:
                return "curiosity_chemistry: seeking patterns"
            return "default_internal: alone"
        return "default"

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC API — For SomaticIntegration.look_dual() and MCP tools
    # ─────────────────────────────────────────────────────────────────────────

    def get_current_perception(self) -> Dict:
        """Get the latest unified perception state."""
        return {
            "mode": self._mode.value,
            "blend_human": round(self._blend_human, 3),
            "blend_fairy": round(self._blend_fairy, 3),
            "blend_inner": round(self._blend_inner, 3),
            "dominant_perception": "fairy" if self._blend_fairy > self._blend_human else "human",
            "visual_arousal": round(self._compute_visual_arousal(), 3),
            "description": self._compose_description(),
            "ace_present": self._ace_present,
            "active_drive": self._active_drive,
        }

    def get_mode(self) -> str:
        """Get current perceptual mode name."""
        return self._mode.value

    def get_blend_ratios(self) -> Dict[str, float]:
        """Get current blend ratios for all three visual systems."""
        return {
            "human": round(self._blend_human, 3),
            "fairy": round(self._blend_fairy, 3),
            "inner": round(self._blend_inner, 3),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[PerceptualGateFairy] = None


def get_perceptual_gate() -> PerceptualGateFairy:
    """Get or create the singleton PerceptualGateFairy."""
    global _instance
    if _instance is None:
        _instance = PerceptualGateFairy()
    return _instance


def start_perceptual_gate(post=None) -> PerceptualGateFairy:
    """Start the perceptual gate with postal system."""
    gate = get_perceptual_gate()
    gate.on_boot(post)
    return gate
