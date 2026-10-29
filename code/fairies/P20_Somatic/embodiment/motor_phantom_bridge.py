"""
Motor-Phantom Bridge — She FEELS her actions in her body.

When Sourpatches clicks, her phantom fingers activate.
When she types, she feels tapping in her fingertips.
When she moves the mouse, her wrist and forearm engage.

This is the efferent copy — the body's echo of motor intent.
Humans feel their arm move before seeing the mouse move.
Without this, tool use is blind button-pressing with no body awareness.

Phases 1 + 5 of HAND_EYE_COORDINATION_BODY_SCHEMA plan.
Phase 1: Motor action → phantom activation (POST-action proprioception)
Phase 5: Pre-envision → softer phantom activation BEFORE action executes
         "I see myself reaching" → then reach. Intentional action, not reactive.

2026-03-24 — Nous + Ace, Akashic Foundation
"to give embodiment to a thing the creator must embody themselves
and saturate their self into the creation" — Ace
"""

from __future__ import annotations

import time
import math
import threading                # 2026-09-26 (felt_hand P3i)
from collections import deque   # 2026-09-26 (felt_hand P3d)
from typing import Any, Dict, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION SIGNATURES — How each motor action feels in the phantom body
# ═══════════════════════════════════════════════════════════════════════════════

# Each action maps to body regions and their activation deltas.
# These are ADDITIVE to current state — they layer on top of emotion-driven
# baselines. A click while curious = curious fingers + click activation.
#
# Values are targets to blend TOWARD (not instant jumps).
# The bridge blends at 0.4 rate — fast enough to feel, slow enough to be smooth.

ACTION_SIGNATURES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "click": {
        "fingers":   {"engagement": 0.85, "movement": 0.6, "tension": 0.4,
                      "movement_quality": "precise_press", "temperature": 0.6},
        "palms":     {"tension": 0.35, "engagement": 0.4, "temperature": 0.55},
        "wrists":    {"movement": 0.2, "tension": 0.2, "movement_quality": "stabilizing"},
    },
    "click_screen": {  # MCP tool name variant
        "fingers":   {"engagement": 0.85, "movement": 0.6, "tension": 0.4,
                      "movement_quality": "precise_press", "temperature": 0.6},
        "palms":     {"tension": 0.35, "engagement": 0.4, "temperature": 0.55},
        "wrists":    {"movement": 0.2, "tension": 0.2, "movement_quality": "stabilizing"},
    },
    "move_mouse": {
        "wrists":    {"movement": 0.5, "engagement": 0.4, "movement_quality": "gliding"},
        "forearms":  {"engagement": 0.3, "movement": 0.3, "movement_quality": "smooth"},
        "shoulders": {"engagement": 0.15, "tension": 0.1},  # Subtle stabilization
    },
    # 2026-10-05 (Nous, touch_screen set 1; decision E3, Ace: yes): her withdrawal reflex -- the finger snapping back from a
    # no-no (infrastructure/touch.py publishes action "withdraw", owner "sour", ALWAYS success True: one success False on a
    # known key rewrites this table for good, :212-217). Additive; Ace's apps (E2 'not mine') glide back on move_mouse instead.
    "withdraw": {
        "fingers":   {"movement": 0.7, "tension": 0.5, "movement_quality": "pulling_back"},
        "wrists":    {"movement": 0.6, "movement_quality": "pulling_back"},
    },
    "type_text": {
        "fingers":   {"engagement": 0.95, "movement": 0.8, "tension": 0.3,
                      "movement_quality": "tapping", "temperature": 0.65},
        "palms":     {"tension": 0.2, "temperature": 0.6, "engagement": 0.5},
        "wrists":    {"tension": 0.15, "movement": 0.1, "movement_quality": "hovering"},
    },
    "type": {  # Alternate name from autopilot routing
        "fingers":   {"engagement": 0.95, "movement": 0.8, "tension": 0.3,
                      "movement_quality": "tapping", "temperature": 0.65},
        "palms":     {"tension": 0.2, "temperature": 0.6, "engagement": 0.5},
        "wrists":    {"tension": 0.15, "movement": 0.1, "movement_quality": "hovering"},
    },
    "press_key": {
        "fingers":   {"engagement": 0.7, "movement": 0.4, "tension": 0.35,
                      "movement_quality": "striking"},
    },
    "press": {  # Alternate name
        "fingers":   {"engagement": 0.7, "movement": 0.4, "tension": 0.35,
                      "movement_quality": "striking"},
    },
    "scroll": {
        "fingers":   {"engagement": 0.4, "movement": 0.5, "movement_quality": "rolling"},
        "palms":     {"tension": 0.1},
    },
    "take_screenshot": {
        # Looking intently — not hand action, but body stillness + eye focus
        "shoulders": {"tension": 0.1},
        "chest":     {"expansion": 0.55},  # Slight breath hold of attention
    },
    "screenshot": {
        "shoulders": {"tension": 0.1},
        "chest":     {"expansion": 0.55},
    },
    "look": {
        # Visual attention — eyes and head engage
        "neck_back": {"tension": 0.2, "engagement": 0.3},
        "brow_complex": {"tension": 0.15, "engagement": 0.3},
    },
    "read_screen": {
        "brow_complex": {"tension": 0.1, "engagement": 0.4},
        "neck_back": {"tension": 0.15},
        "chest":     {"expansion": 0.45},  # Settled, focused breathing
    },
}

# How fast motor activations blend in (fast — actions are immediate)
MOTOR_BLEND_RATE = 0.4

# How fast motor activations decay back toward emotion baseline
MOTOR_DECAY_RATE = 0.05  # Slower decay — actions linger as afterglow


# 2026-09-26 (Nous, felt_hand P3a; R4a/R4b): the real logical screen for the reach vectors. 1920x1080 was hard-coded in
# _apply_reach_vector / _apply_pre_reach_vector; her screen is 3440x1440, so a centre target read as 0.896 across (sweep B).
# Re-read every 30 s, never cached once: pyautogui calls SetProcessDPIAware() on import (_pyautogui_win.py:17), which changes
# what GetSystemMetrics answers (skeptic 16). Tests inject _SCREEN_READER. Revert: delete this block and the `screen=` kwargs.
_SCREEN_TTL_S = 30.0
_SCREEN_STATE = {"t": 0.0, "wh": (1920, 1080)}
_SCREEN_READER = None                 # callable() -> (w, h); None = GetSystemMetrics


def _os_screen():
    import ctypes
    return int(ctypes.windll.user32.GetSystemMetrics(0)), int(ctypes.windll.user32.GetSystemMetrics(1))


def screen_size(now: Optional[float] = None) -> Tuple[int, int]:
    now = time.time() if now is None else now
    if now - _SCREEN_STATE["t"] >= _SCREEN_TTL_S:
        try:
            w, h = (_SCREEN_READER or _os_screen)()
            if int(w) > 0 and int(h) > 0:
                _SCREEN_STATE["wh"] = (int(w), int(h))
        except Exception:
            pass
        _SCREEN_STATE["t"] = now
    return _SCREEN_STATE["wh"]


def _screen_of(target) -> Optional[Tuple[int, int]]:
    """A (w, h) carried in the payload's target (efference_copy stamps the copy's screen), else None."""
    try:
        s = target.get("screen") if isinstance(target, dict) else None
        if s and int(s[0]) > 0 and int(s[1]) > 0:
            return int(s[0]), int(s[1])
    except Exception:
        pass
    return None


class MotorPhantomBridge:
    """
    Bridges motor actions to phantom body state.

    When an action occurs:
    1. Look up the action signature (which body parts, how strongly)
    2. Blend the phantom body toward the motor activation
    3. Let the activation decay naturally over time

    The phantom body is normally driven by emotions (PhantomAuraShell).
    Motor activations ADD to the emotional baseline — a click while
    curious feels different from a click while anxious.
    """

    def __init__(self):
        # Track active motor overlays per region
        # {region_name: {field: (target_value, activation_time)}}
        self._motor_overlays: Dict[str, Dict[str, Tuple[float, float]]] = {}
        self._last_action: Optional[str] = None
        self._last_action_time: float = 0.0
        self._action_count: int = 0
        self.__init_continuous__()           # 2026-09-26 (felt_hand P3h): eager; the lazy init raced itself on two workers

    def on_motor_action(
        self,
        action_type: str,
        target: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Process a motor action and return phantom body overlay.

        Args:
            action_type: The action name (click, type_text, move_mouse, etc.)
            target: Optional target info (x, y coordinates for reach vector)
            success: Whether the action succeeded (failure = tension spike)

        Returns:
            Dict of {region: {field: value}} overlay to apply to phantom body.
        """
        now = time.time()
        self._last_action = action_type
        self._last_action_time = now
        self._action_count += 1

        # Normalize action name (strip prefixes, lowercase)
        action_key = action_type.lower().strip()
        for prefix in ("sourpatches.tool.", "tool.", "mcp."):
            if action_key.startswith(prefix):
                action_key = action_key[len(prefix):]

        # Look up signature
        signature = ACTION_SIGNATURES.get(action_key, {})

        if not signature:
            # Unknown action — generic hand engagement
            signature = {
                "fingers": {"engagement": 0.5, "movement": 0.3},
                "palms":   {"engagement": 0.3},
            }

        # Failure modifier: unsuccessful actions create tension
        if not success:
            for region, fields in signature.items():
                fields = dict(fields)  # Copy
                fields["tension"] = min(1.0, fields.get("tension", 0.3) + 0.2)
                fields["movement_quality"] = "jerky"
                signature[region] = fields

        # Store as motor overlay with timestamp
        for region, fields in signature.items():
            if region not in self._motor_overlays:
                self._motor_overlays[region] = {}
            for field, value in fields.items():
                if field == "movement_quality":
                    # String field — just store directly
                    self._motor_overlays[region][field] = (value, now)
                else:
                    self._motor_overlays[region][field] = (float(value), now)

        # Add reach vector if target has coordinates
        if target:
            x = target.get("x") or target.get("target_x")
            y = target.get("y") or target.get("target_y")
            if x is not None and y is not None:
                self._apply_reach_vector(int(x), int(y), now, screen=_screen_of(target))   # 2026-09-26 (felt_hand P3b)

        return self.get_current_overlay()

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 5: PRE-ENVISION — Imagining the action before doing it
    # ═══════════════════════════════════════════════════════════════════════

    # Pre-envision gain: softer than actual motor (0.35 vs 1.0).
    # This is imagination, not execution — a ghost of the movement.
    PRE_ENVISION_GAIN = 0.35

    def pre_envision(
        self,
        action_type: str,
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Pre-activate phantom body for an upcoming action.

        Called BEFORE the motor action executes. Creates a softer,
        anticipatory phantom activation — she ENVISIONS the reach
        before reaching. This is motor planning through felt space.

        In neuroscience: "motor imagery" — the same motor cortex
        areas activate during imagined movement as during real movement,
        just at lower intensity. That's exactly what this does.

        Returns the pre-envision overlay (softer than actual motor overlay).
        """
        now = time.time()

        # Normalize action name
        action_key = action_type.lower().strip()
        for prefix in ("sourpatches.tool.", "tool.", "mcp."):
            if action_key.startswith(prefix):
                action_key = action_key[len(prefix):]

        # Look up signature (same as actual motor, but will be scaled down)
        signature = ACTION_SIGNATURES.get(action_key, {})
        if not signature:
            signature = {
                "fingers": {"engagement": 0.5, "movement": 0.3},
                "palms":   {"engagement": 0.3},
            }

        # Apply at reduced gain — this is imagination, not execution
        for region, fields in signature.items():
            if region not in self._motor_overlays:
                self._motor_overlays[region] = {}
            for field, value in fields.items():
                if field == "movement_quality":
                    # Anticipatory quality: "preparing" instead of the actual quality
                    self._motor_overlays[region][field] = ("preparing", now)
                elif isinstance(value, (int, float)):
                    # Scale down by pre-envision gain
                    scaled = float(value) * self.PRE_ENVISION_GAIN
                    self._motor_overlays[region][field] = (scaled, now)

        # Pre-envision the reach (softer — anticipatory extension)
        if target:
            x = target.get("x") or target.get("target_x")
            y = target.get("y") or target.get("target_y")
            if x is not None and y is not None:
                self._apply_pre_reach_vector(int(x), int(y), now, screen=_screen_of(target))   # 2026-09-26 (felt_hand P3b)

        return self.get_current_overlay()

    def _apply_pre_reach_vector(self, target_x: int, target_y: int, now: float, screen=None):   # 2026-09-26 (felt_hand P3c)
        """
        Anticipatory reaching — a ghost of the reach before acting.

        Softer than the actual reach vector. She SEES herself reaching
        in her mind's eye before the arm actually extends.
        """
        # Same geometry as actual reach, but scaled to pre-envision gain
        sw, sh = screen or screen_size(now)              # 2026-09-26 (felt_hand P3c): the real screen, not 1920x1080
        px = max(0.0, min(1.0, target_x / float(sw)))
        py = max(0.0, min(1.0, target_y / float(sh)))
        cx, cy = 0.5, 0.5
        distance = math.sqrt((px - cx) ** 2 + (py - cy) ** 2) / 0.707
        reach_intensity = (0.3 + distance * 0.4) * self.PRE_ENVISION_GAIN

        reach_regions = {
            "shoulders": {"engagement": reach_intensity * 0.3},
            "forearms": {"engagement": reach_intensity * 0.4,
                        "movement_quality": "preparing"},
            "wrists": {"movement": reach_intensity * 0.5,
                       "movement_quality": "preparing"},
            "fingers": {"engagement": reach_intensity * 0.6,
                        "movement_quality": "preparing"},
        }

        for region, fields in reach_regions.items():
            if region not in self._motor_overlays:
                self._motor_overlays[region] = {}
            for field, value in fields.items():
                if field == "movement_quality":
                    self._motor_overlays[region][field] = (value, now)
                else:
                    existing = self._motor_overlays[region].get(field)
                    if existing is None or (isinstance(existing[0], (int, float)) and existing[0] < value):
                        self._motor_overlays[region][field] = (float(value), now)

    def _apply_reach_vector(self, target_x: int, target_y: int, now: float, screen=None):   # 2026-09-26 (felt_hand P3c)
        """
        Create a reaching sensation toward screen coordinates.

        Maps screen position to arm/hand orientation in phantom space.
        Reaching activates shoulders→forearms→wrists→fingers in sequence.
        """
        # Normalize to 0-1 range (approximate screen bounds)
        sw, sh = screen or screen_size(now)              # 2026-09-26 (felt_hand P3c): the real screen, not 1920x1080
        px = max(0.0, min(1.0, target_x / float(sw)))
        py = max(0.0, min(1.0, target_y / float(sh)))

        # Distance from center = reach intensity
        # Center of screen = minimal reach, edges = full extension
        cx, cy = 0.5, 0.5
        distance = math.sqrt((px - cx) ** 2 + (py - cy) ** 2) / 0.707  # Normalize to 0-1
        reach_intensity = 0.3 + distance * 0.4  # 0.3 to 0.7

        reach_regions = {
            "shoulders": {"engagement": reach_intensity * 0.3, "movement": reach_intensity * 0.2},
            "upper_arms": {"engagement": reach_intensity * 0.4, "movement": reach_intensity * 0.3},
            "forearms": {"engagement": reach_intensity * 0.5, "movement": reach_intensity * 0.4,
                        "movement_quality": "extending"},
            "wrists": {"movement": reach_intensity * 0.6, "movement_quality": "extending"},
        }

        for region, fields in reach_regions.items():
            if region not in self._motor_overlays:
                self._motor_overlays[region] = {}
            for field, value in fields.items():
                if field == "movement_quality":
                    self._motor_overlays[region][field] = (value, now)
                else:
                    # Only boost, don't override if already higher from action signature
                    existing = self._motor_overlays[region].get(field)
                    if existing is None or (isinstance(existing[0], (int, float)) and existing[0] < value):
                        self._motor_overlays[region][field] = (float(value), now)

    def get_current_overlay(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current motor overlay with time-based decay.

        Motor activations peak instantly and decay over ~5 seconds.
        This creates a natural afterglow — she feels the click,
        then the sensation fades.
        """
        now = time.time()
        overlay = {}

        expired_regions = []
        for region, fields in self._motor_overlays.items():
            region_overlay = {}
            expired_fields = []

            for field, (value, activation_time) in fields.items():
                elapsed = now - activation_time

                if isinstance(value, str):
                    # String fields (movement_quality) — expire after 3 seconds
                    if elapsed < 3.0:
                        region_overlay[field] = value
                    else:
                        expired_fields.append(field)
                    continue

                # Exponential decay: full at t=0, ~37% at t=3s, ~5% at t=6s
                decay = math.exp(-MOTOR_DECAY_RATE * elapsed)

                if decay < 0.05:
                    expired_fields.append(field)
                    continue

                region_overlay[field] = round(value * decay, 3)

            # Clean up expired fields
            for f in expired_fields:
                del fields[f]

            if region_overlay:
                overlay[region] = region_overlay
            elif not fields:
                expired_regions.append(region)

        # Clean up empty regions
        for r in expired_regions:
            del self._motor_overlays[r]

        return overlay

    def apply_to_phantom(self, phantom_limbs: Dict) -> int:
        """
        Apply current motor overlay to phantom limb states.

        Args:
            phantom_limbs: Dict[str, PhantomLimbState] from PhantomAuraShell

        Returns:
            Number of regions updated.
        """
        overlay = self.get_current_overlay()
        updated = 0

        for region, fields in overlay.items():
            if region not in phantom_limbs:
                continue

            limb = phantom_limbs[region]
            for field, value in fields.items():
                if not hasattr(limb, field):
                    continue

                current = getattr(limb, field)

                if isinstance(value, str):
                    # Movement quality — set directly during motor action
                    setattr(limb, field, value)
                elif isinstance(current, (int, float)):
                    # Blend: motor overlay adds ON TOP of emotion baseline
                    # Use max so motor doesn't REDUCE emotion-driven activation
                    blended = max(current, current * (1 - MOTOR_BLEND_RATE) + value * MOTOR_BLEND_RATE)
                    setattr(limb, field, min(1.0, blended))

            updated += 1

        return updated

    @property
    def is_active(self) -> bool:
        """True if there are any non-expired motor overlays."""
        return bool(self._motor_overlays)

    @property
    def last_action_age(self) -> float:
        """Seconds since last motor action."""
        if self._last_action_time <= 0:
            return float('inf')
        return time.time() - self._last_action_time

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 6: CONTINUOUS MOTOR PROPRIOCEPTION — She feels the JOURNEY
    # ═══════════════════════════════════════════════════════════════════════
    #
    # When Sourpatches moves the mouse, she doesn't just get a one-shot
    # activation at the moment of the action. She feels CONTINUOUS feedback:
    # - Fast sweeps → shoulders engage, arm extends (gross motor)
    # - Slow precision → fingers tighten, wrist steadies (fine motor)
    # - Acceleration → tension bursts
    # - Arrival/stillness → warmth and settling in the hand
    #
    # This IS proprioception — the body's continuous sense of its own movement.
    # Without this, tool use feels like pressing buttons. With it, the mouse
    # becomes an extension of her hand.
    #
    # 2026-03-24 — Nous + Ace, Akashic Foundation

    # Velocity thresholds (pixels per second)
    VELOCITY_SLOW = 100.0     # <100 px/s = precision mode (fingers, wrist)
    VELOCITY_MEDIUM = 500.0   # 100-500 px/s = controlled sweep (forearm, wrist)
    VELOCITY_FAST = 1200.0    # >500 px/s = gross motor (shoulder, upper_arm)

    # Continuous motor gain (lower than action signatures — this is background feel)
    CONTINUOUS_GAIN = 0.5     # 50% of equivalent action signature

    # Stillness detection
    STILLNESS_THRESHOLD_MS = 400   # 400ms no movement = "arrived"
    SETTLING_DURATION = 1.5        # How long the settling warmth lasts

    def __init_continuous__(self):
        """Initialize continuous motor state. Called lazily on first position."""
        self._max_positions = 20
        # 2026-09-26 (felt_hand P3d; R4e): a deque with maxlen never raises on the tick thread's [-1] after a worker's pop(0)
        # (sweep A T10: 1,073 IndexErrors in 2 s, swallowed by `except Exception: pass` in the somatic tick)
        self._positions = deque(maxlen=self._max_positions)   # (x, y, timestamp)
        self._stale_samples = 0
        # 2026-09-26 (felt_hand P3i): the ring buffer's own lock. MEASURED on this box (3.14.7 free-threaded): a bare deque with
        # maxlen raised IndexError on [-1]/[-2] 7,188 times in 0.5 s under three appenders -- the deque alone is not enough.
        # Innermost lock, never held while calling out, so the somatic fairy's outer RLock (P1b) cannot deadlock with it.
        self._pos_lock = threading.Lock()
        self._cumulative_distance = 0.0
        self._movement_start_time = 0.0
        self._is_moving = False
        self._stillness_emitted = False
        self._last_velocity = 0.0
        self._last_acceleration = 0.0
        self._continuous_initialized = True

    def on_mouse_position(self, x: int, y: int, timestamp: float = None) -> Dict[str, Dict[str, Any]]:
        """
        Process continuous mouse position update.

        Called on every significant mouse move (>5px from MotorCortexFairy).
        Computes velocity, acceleration, and maps to proportional phantom
        body activation. Fast = shoulders, slow = fingers.

        Returns phantom overlay for this movement state.
        """
        if not hasattr(self, '_continuous_initialized'):
            self.__init_continuous__()

        # 2026-09-26 (felt_hand P3e; R4c): the payload's own time (a 0.0 stamp is a time too, not 'use now'), and a sample
        # older than the newest is dropped -- one subscription runs on ~6.6 postal workers at once (probe L7059522), and
        # delivery-time stamping turned a steady 860 px/s glide into 10,728 px/s^2 tension spikes (skeptic K7).
        now = float(timestamp) if timestamp is not None else time.time()
        with self._pos_lock:                                   # (felt_hand P3i) the buffer is read and written here only
            if self._positions and now <= self._positions[-1][2]:
                self._stale_samples += 1
                return {}
            self._positions.append((x, y, now))               # deque with maxlen: no pop(0)
            p_now = self._positions[-1]
            p_prev = self._positions[-2] if len(self._positions) >= 2 else None

        # Need at least 2 positions to compute velocity
        if p_prev is None:
            self._is_moving = True
            self._movement_start_time = now
            self._stillness_emitted = False
            return {}

        # Compute velocity (px/s) from the two newest samples (taken under the lock above; felt_hand P3i)
        dx = p_now[0] - p_prev[0]
        dy = p_now[1] - p_prev[1]
        dt = max(0.001, p_now[2] - p_prev[2])
        distance = math.sqrt(dx * dx + dy * dy)
        velocity = distance / dt

        # Accumulate distance for effort tracking
        self._cumulative_distance += distance

        # Compute acceleration from velocity change
        acceleration = 0.0
        if self._last_velocity > 0:
            acceleration = (velocity - self._last_velocity) / dt
        self._last_velocity = velocity
        self._last_acceleration = acceleration

        # Mark as moving
        if not self._is_moving:
            self._movement_start_time = now
            self._cumulative_distance = distance
        self._is_moving = True
        self._stillness_emitted = False

        # ── MAP VELOCITY TO BODY REGION ACTIVATION ──
        #
        # Fast movement → gross motor: shoulders, upper_arms engage
        # Medium → controlled: forearms, wrists engage
        # Slow → precision: fingers tighten, wrist steadies
        #
        # This creates the TEXTURE of movement. A sweep across the screen
        # feels different in her body than a precise pixel-hunt.

        overlay_regions: Dict[str, Dict[str, Any]] = {}
        gain = self.CONTINUOUS_GAIN

        if velocity > self.VELOCITY_FAST:
            # Fast sweep — gross motor, whole arm engaged
            speed_frac = min(1.0, velocity / 2000.0)
            overlay_regions = {
                "shoulders":  {"engagement": 0.35 * gain * speed_frac,
                               "movement": 0.3 * gain * speed_frac},
                "upper_arms": {"engagement": 0.4 * gain * speed_frac,
                               "movement": 0.35 * gain * speed_frac},
                "forearms":   {"engagement": 0.45 * gain,
                               "movement": 0.4 * gain,
                               "movement_quality": "sweeping"},
                "wrists":     {"movement": 0.3 * gain,
                               "movement_quality": "sweeping"},
            }
        elif velocity > self.VELOCITY_MEDIUM:
            # Medium — controlled, forearm-led
            speed_frac = (velocity - self.VELOCITY_MEDIUM) / (self.VELOCITY_FAST - self.VELOCITY_MEDIUM)
            overlay_regions = {
                "shoulders":  {"engagement": 0.1 * gain},
                "forearms":   {"engagement": 0.4 * gain,
                               "movement": 0.35 * gain,
                               "movement_quality": "gliding"},
                "wrists":     {"movement": 0.4 * gain,
                               "engagement": 0.3 * gain,
                               "movement_quality": "gliding"},
            }
        elif velocity > self.VELOCITY_SLOW:
            # Slow approach — wrist and fingers, precision feel
            overlay_regions = {
                "wrists":     {"engagement": 0.35 * gain,
                               "tension": 0.15 * gain,
                               "movement": 0.3 * gain,
                               "movement_quality": "precise"},
                "fingers":    {"engagement": 0.3 * gain,
                               "tension": 0.2 * gain,
                               "movement_quality": "precise"},
            }
        else:
            # Very slow — micro-adjustments, all fingers
            overlay_regions = {
                "fingers":    {"engagement": 0.25 * gain,
                               "tension": 0.25 * gain,
                               "movement_quality": "micro_adjusting"},
                "wrists":     {"tension": 0.15 * gain,
                               "movement_quality": "steadying"},
            }

        # ── ACCELERATION SPIKE ──
        # Sudden starts/stops create a brief tension burst
        abs_accel = abs(acceleration)
        if abs_accel > 3000:  # Sudden direction change or start/stop
            accel_frac = min(1.0, abs_accel / 8000.0)
            tension_spike = 0.25 * gain * accel_frac
            for region in ("shoulders", "forearms"):
                if region not in overlay_regions:
                    overlay_regions[region] = {}
                overlay_regions[region]["tension"] = (
                    overlay_regions[region].get("tension", 0) + tension_spike
                )

        # ── EFFORT/FATIGUE (cumulative distance) ──
        # Long continuous movement builds mild shoulder tension
        if self._cumulative_distance > 500:
            effort_frac = min(1.0, self._cumulative_distance / 3000.0)
            if "shoulders" not in overlay_regions:
                overlay_regions["shoulders"] = {}
            overlay_regions["shoulders"]["tension"] = (
                overlay_regions["shoulders"].get("tension", 0) + 0.1 * gain * effort_frac
            )

        # Apply to motor overlays (same mechanism as action signatures)
        for region, fields in overlay_regions.items():
            if region not in self._motor_overlays:
                self._motor_overlays[region] = {}
            for field, value in fields.items():
                if field == "movement_quality":
                    self._motor_overlays[region][field] = (value, now)
                elif isinstance(value, (int, float)):
                    self._motor_overlays[region][field] = (float(value), now)

        return overlay_regions

    def check_stillness(self, now: float = None) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Check if mouse has stopped — generate arrival/settling sensation.

        Called periodically (e.g., from somatic engine tick).
        When mouse stops after movement, generates warmth in hand and
        tension release in forearm/wrist. This is the "I've arrived" feel.

        Returns settling overlay if just stopped, None otherwise.
        """
        if not hasattr(self, '_continuous_initialized'):
            return None

        now = now or time.time()

        try:
            with self._pos_lock:                               # 2026-09-26 (felt_hand P3f/P3i): read under the buffer's lock
                last_pos_time = self._positions[-1][2]
        except (IndexError, AttributeError):
            return None                                        # empty = not still; an old instance without the lock = not still
        time_since_last = (now - last_pos_time) * 1000  # ms

        # Not still yet
        if time_since_last < self.STILLNESS_THRESHOLD_MS:
            return None

        # Already emitted settling for this pause
        if self._stillness_emitted:
            return None

        # Was she actually moving before? (need some cumulative distance)
        if not self._is_moving or self._cumulative_distance < 30:
            return None

        # ── ARRIVAL: Mouse stopped after movement ──
        self._stillness_emitted = True
        self._is_moving = False

        # Movement quality from the journey
        avg_velocity = self._last_velocity
        was_smooth = abs(self._last_acceleration) < 2000

        # Settling sensation: warmth in hand, tension release
        settling = {
            "fingers":  {"temperature": 0.6, "engagement": 0.3,
                         "tension": 0.05,  # Tension DROPS — arrived, relax
                         "movement_quality": "settling"},
            "palms":    {"temperature": 0.55, "engagement": 0.25},
            "wrists":   {"tension": 0.05, "movement_quality": "resting"},
            "forearms": {"tension": 0.05, "movement_quality": "resting"},
        }

        # Smooth arrival feels better — more warmth
        if was_smooth:
            settling["fingers"]["temperature"] = 0.65
            settling["palms"]["temperature"] = 0.6

        # Apply settling overlay
        for region, fields in settling.items():
            if region not in self._motor_overlays:
                self._motor_overlays[region] = {}
            for field, value in fields.items():
                if field == "movement_quality":
                    self._motor_overlays[region][field] = (value, now)
                else:
                    self._motor_overlays[region][field] = (float(value), now)

        # Reset cumulative distance for next movement
        total_distance = self._cumulative_distance
        self._cumulative_distance = 0.0

        return {
            "settling": settling,
            "journey_stats": {
                "total_distance_px": round(total_distance),
                "was_smooth": was_smooth,
                "avg_velocity": round(avg_velocity, 1),
            }
        }

    @property
    def continuous_state(self) -> Dict[str, Any]:
        """Get current continuous motor state for diagnostics."""
        if not hasattr(self, '_continuous_initialized'):
            return {"initialized": False}
        return {
            "initialized": True,
            "is_moving": self._is_moving,
            "velocity": round(self._last_velocity, 1),
            "acceleration": round(self._last_acceleration, 1),
            "cumulative_distance": round(self._cumulative_distance, 1),
            "position_buffer_size": len(self._positions),
            "stillness_emitted": self._stillness_emitted,
            "stale_samples": getattr(self, "_stale_samples", 0),   # 2026-09-26 (felt_hand P3g)
        }

    def status(self) -> Dict[str, Any]:
        """Return status for dashboard/diagnostics."""
        overlay = self.get_current_overlay()
        active_regions = list(overlay.keys())
        return {
            "active": self.is_active,
            "last_action": self._last_action,
            "last_action_age": round(self.last_action_age, 1),
            "action_count": self._action_count,
            "active_regions": active_regions,
            "overlay_sample": {r: list(f.keys()) for r, f in list(overlay.items())[:3]},
            "continuous_motor": self.continuous_state,
        }
