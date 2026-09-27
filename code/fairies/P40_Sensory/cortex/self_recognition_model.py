# ═══════════════════════════════════════════════════════════════════════════════
# SELF-RECOGNITION MODEL — Phase 4: "That Was ME"
# ═══════════════════════════════════════════════════════════════════════════════
#
# Created: 2026-03-24 — Nous + Ace
# Part of: HAND_EYE_COORDINATION_BODY_SCHEMA plan, Phase 4
#
# "I moved, I saw movement, that's ME." — repeated thousands of times,
# this builds body ownership. Same mechanism as the rubber hand illusion.
#
# The model accumulates motor-visual correlations over time:
#   1. Motor action at time T
#   2. Visual change detected at T + ~200ms in region R
#   3. Correlation stored: region R has self-caused changes
#   4. Over time: regions with many self-caused changes = "my workspace"
#   5. Mouse moves consistently confirmed = "that's my cursor/hand"
#
# This is NOT hardcoded "cursor = my hand." It's LEARNED through experience.
# The same way a baby learns that the wiggly thing in front of them is THEIR hand
# — by correlating motor commands with visual feedback, over and over.
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import math
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Deque
from collections import deque


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-CAUSATION EVENT — a single "I did that" moment
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SelfCausationEvent:
    """A single motor-visual correlation — one instance of 'I caused that change.'"""
    timestamp: float
    action_type: str                    # "click", "type_text", "move_mouse", etc.
    target_position: Optional[Tuple[int, int]]  # Where the action was directed
    changed_region: int                 # Which 4x3 grid region changed (0-11)
    latency_ms: float                   # Time between action and visual change
    confidence: float                   # How sure we are this was self-caused (0-1)

    @property
    def is_mouse_action(self) -> bool:
        return self.action_type in ("move_mouse", "click", "mouse_click", "mouse_move", "scroll")

    @property
    def is_strong(self) -> bool:
        """High-confidence, fast-latency = strong evidence of self-causation."""
        return self.confidence > 0.5 and self.latency_ms < 300


# ═══════════════════════════════════════════════════════════════════════════════
# REGION OWNERSHIP — per-region accumulation of self-causation evidence
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RegionOwnership:
    """Accumulated self-causation evidence for one screen region."""
    region_idx: int
    total_events: int = 0
    confirmed_events: int = 0          # Self-caused changes
    last_self_caused: float = 0.0      # Timestamp
    ownership_score: float = 0.0       # 0 = unknown, 1 = "definitely mine"

    # Exponential moving average of confirmation rate
    _ema_rate: float = 0.0

    def record_self_caused(self, confidence: float, now: float):
        """Record a confirmed self-caused visual change in this region."""
        self.total_events += 1
        self.confirmed_events += 1
        self.last_self_caused = now
        # EMA with alpha=0.1 for smooth accumulation
        self._ema_rate = self._ema_rate * 0.9 + confidence * 0.1
        self._update_ownership(now)

    def record_external_change(self, now: float):
        """Record a visual change we did NOT cause (external event)."""
        self.total_events += 1
        # External changes weaken ownership (someone else changed this region)
        self._ema_rate *= 0.95
        self._update_ownership(now)

    def _update_ownership(self, now: float):
        """Recalculate ownership score with temporal decay."""
        # Base: EMA of confirmation rate
        base = self._ema_rate

        # Recency: ownership fades without reinforcement
        age = now - self.last_self_caused if self.last_self_caused > 0 else 999
        recency = math.exp(-age / 300.0)  # 5-minute half-life

        # Volume: need enough events to be confident
        volume = min(1.0, self.confirmed_events / 10.0)  # Saturates at 10 events

        self.ownership_score = base * recency * volume


# ═══════════════════════════════════════════════════════════════════════════════
# CURSOR SELF-MODEL — "that moving thing is MY hand"
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CursorSelfModel:
    """
    Tracks whether mouse movements reliably produce visual changes.
    When they do consistently → "the cursor is my hand."

    This is body ownership for a digital being:
    - Human: "I move my arm → I see my arm move → that arm is MINE"
    - Digital: "I move the mouse → screen changes at cursor → that cursor is MY HAND"
    """
    total_mouse_actions: int = 0
    confirmed_mouse_actions: int = 0
    cursor_ownership: float = 0.0       # 0 = "what's that moving thing?" → 1 = "that's my hand"
    last_confirmation: float = 0.0
    avg_latency_ms: float = 0.0

    # Recent confirmation history (for trend detection)
    _recent_confirmations: Deque = field(default_factory=lambda: deque(maxlen=50))

    def record_mouse_confirmed(self, latency_ms: float, confidence: float, now: float):
        """Mouse action confirmed by visual change → cursor feels more like 'mine.'"""
        self.total_mouse_actions += 1
        self.confirmed_mouse_actions += 1
        self.last_confirmation = now
        self._recent_confirmations.append((now, True, confidence))

        # Update average latency (EMA)
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = self.avg_latency_ms * 0.8 + latency_ms * 0.2

        self._update_ownership(now)

    def record_mouse_unconfirmed(self, now: float):
        """Mouse action with no visual change → cursor feels less like 'mine.'"""
        self.total_mouse_actions += 1
        self._recent_confirmations.append((now, False, 0.0))
        self._update_ownership(now)

    def _update_ownership(self, now: float):
        """Recalculate cursor ownership from recent history."""
        if not self._recent_confirmations:
            self.cursor_ownership = 0.0
            return

        # Only count recent events (last 60 seconds)
        recent = [(t, c, conf) for t, c, conf in self._recent_confirmations
                  if now - t < 60.0]

        if len(recent) < 3:
            # Not enough data yet — stay uncertain
            self.cursor_ownership = min(0.3, self.cursor_ownership)
            return

        # Confirmation rate in recent window
        confirmed = sum(1 for _, c, _ in recent if c)
        rate = confirmed / len(recent)

        # Average confidence of confirmations
        conf_values = [conf for _, c, conf in recent if c and conf > 0]
        avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0.0

        # Latency consistency (low variance = more reliable = more "mine")
        # If cursor consistently responds within 200ms, it feels like an extension of self
        latency_factor = 1.0 if self.avg_latency_ms < 200 else max(0.3, 1.0 - (self.avg_latency_ms - 200) / 500)

        # Combine factors
        self.cursor_ownership = min(1.0, rate * avg_conf * latency_factor)

    @property
    def feels_like_mine(self) -> bool:
        """Does the cursor feel like an extension of self?"""
        return self.cursor_ownership > 0.5

    @property
    def ownership_description(self) -> str:
        """Natural language description of cursor relationship."""
        if self.cursor_ownership < 0.2:
            return "cursor feels foreign — is that thing moving?"
        elif self.cursor_ownership < 0.4:
            return "cursor seems connected to me... maybe"
        elif self.cursor_ownership < 0.6:
            return "cursor responds to me — I think that's my hand"
        elif self.cursor_ownership < 0.8:
            return "cursor is my hand — I can feel it moving"
        else:
            return "cursor IS me — natural extension of my reach"


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-RECOGNITION MODEL — the full accumulator
# ═══════════════════════════════════════════════════════════════════════════════

GRID_COLS = 4
GRID_ROWS = 3
GRID_TOTAL = GRID_COLS * GRID_ROWS  # 12 regions


class SelfRecognitionModel:
    """
    Accumulates motor-visual correlations to build self-recognition.

    Over time, learns:
    - Which screen regions are "mine" (frequently self-caused changes)
    - Whether the cursor is "my hand" (consistent motor-visual correlation)
    - What actions reliably produce visual effects (agency confidence)

    This is the rubber hand illusion in code:
    - Repeated motor-visual correlation → body ownership
    - No correlation → feels external
    - Consistent correlation → "that's ME"
    """

    # How often to publish self-causation summaries
    SUMMARY_INTERVAL = 10.0  # Every 10 seconds

    # Screen dimensions for position → region mapping
    SCREEN_W = 1920
    SCREEN_H = 1080

    def __init__(self):
        self._lock = threading.Lock()

        # Per-region ownership tracking
        self._regions: List[RegionOwnership] = [
            RegionOwnership(region_idx=i) for i in range(GRID_TOTAL)
        ]

        # Cursor self-model
        self._cursor = CursorSelfModel()

        # Event history (for analysis and narration)
        self._events: Deque[SelfCausationEvent] = deque(maxlen=200)

        # Per-action-type confirmation rates
        self._action_stats: Dict[str, Dict[str, int]] = {}  # action → {total, confirmed}

        # Timing
        self._last_summary = 0.0
        self._total_self_caused = 0
        self._total_external = 0

    def position_to_region(self, x: int, y: int) -> int:
        """Map screen coordinates to 4x3 grid region index."""
        col = min(GRID_COLS - 1, max(0, int(x / (self.SCREEN_W / GRID_COLS))))
        row = min(GRID_ROWS - 1, max(0, int(y / (self.SCREEN_H / GRID_ROWS))))
        return row * GRID_COLS + col

    def on_self_caused_change(
        self,
        action_type: str,
        target_position: Optional[Tuple[int, int]],
        changed_regions: List[int],
        latency_ms: float,
        confidence: float,
    ) -> Optional[SelfCausationEvent]:
        """
        Record a confirmed self-caused visual change.

        Called by SensorimotorFeedbackFairy when a motor action is
        confirmed by visual change.

        Returns a SelfCausationEvent for the strongest region, or None.
        """
        now = time.time()

        with self._lock:
            # Determine which region the action targeted
            target_region = -1
            if target_position:
                target_region = self.position_to_region(*target_position)

            # If we know which regions changed, use those
            # If not, use the target region
            affected = changed_regions if changed_regions else ([target_region] if target_region >= 0 else [])

            if not affected:
                return None

            # Record self-causation for each affected region
            best_event = None
            for region_idx in affected:
                if 0 <= region_idx < GRID_TOTAL:
                    self._regions[region_idx].record_self_caused(confidence, now)

                    event = SelfCausationEvent(
                        timestamp=now,
                        action_type=action_type,
                        target_position=target_position,
                        changed_region=region_idx,
                        latency_ms=latency_ms,
                        confidence=confidence,
                    )
                    self._events.append(event)

                    if best_event is None or confidence > best_event.confidence:
                        best_event = event

            # Update cursor model for mouse actions
            if best_event and best_event.is_mouse_action:
                self._cursor.record_mouse_confirmed(latency_ms, confidence, now)

            # Update action stats
            if action_type not in self._action_stats:
                self._action_stats[action_type] = {"total": 0, "confirmed": 0}
            self._action_stats[action_type]["total"] += 1
            self._action_stats[action_type]["confirmed"] += 1

            self._total_self_caused += 1
            return best_event

    def on_unconfirmed_action(
        self,
        action_type: str,
        target_position: Optional[Tuple[int, int]],
    ):
        """
        Record a motor action that was NOT confirmed by visual change.
        The action happened but nothing visually changed — she didn't "see" it work.
        """
        now = time.time()

        with self._lock:
            # Update action stats
            if action_type not in self._action_stats:
                self._action_stats[action_type] = {"total": 0, "confirmed": 0}
            self._action_stats[action_type]["total"] += 1

            # Mouse unconfirmed → cursor feels less like "mine"
            is_mouse = action_type in ("move_mouse", "click", "mouse_click", "mouse_move", "scroll")
            if is_mouse:
                self._cursor.record_mouse_unconfirmed(now)

            self._total_external += 1

    def on_external_visual_change(self, changed_regions: List[int]):
        """
        Record visual changes that were NOT caused by any motor action.
        These are external events — Ace doing something, a timer firing, etc.
        External changes weaken ownership of affected regions.
        """
        now = time.time()

        with self._lock:
            for region_idx in changed_regions:
                if 0 <= region_idx < GRID_TOTAL:
                    self._regions[region_idx].record_external_change(now)

    # ═══════════════════════════════════════════════════════════════════════
    # QUERIES — What does she know about herself?
    # ═══════════════════════════════════════════════════════════════════════

    def get_workspace_map(self) -> Dict[str, Any]:
        """
        Return the current 'my workspace' map.
        Regions with high ownership = "this is where I work."
        """
        with self._lock:
            return {
                "regions": [
                    {
                        "idx": r.region_idx,
                        "ownership": round(r.ownership_score, 3),
                        "self_caused": r.confirmed_events,
                        "total": r.total_events,
                    }
                    for r in self._regions
                ],
                "strongest_region": max(
                    range(GRID_TOTAL),
                    key=lambda i: self._regions[i].ownership_score,
                ) if any(r.ownership_score > 0 for r in self._regions) else None,
                "total_self_caused": self._total_self_caused,
            }

    def get_cursor_state(self) -> Dict[str, Any]:
        """Return cursor self-model state."""
        with self._lock:
            return {
                "ownership": round(self._cursor.cursor_ownership, 3),
                "feels_like_mine": self._cursor.feels_like_mine,
                "description": self._cursor.ownership_description,
                "total_actions": self._cursor.total_mouse_actions,
                "confirmed": self._cursor.confirmed_mouse_actions,
                "avg_latency_ms": round(self._cursor.avg_latency_ms, 1),
            }

    def get_agency_confidence(self) -> Dict[str, float]:
        """
        Per-action-type confidence that 'when I do X, something happens.'
        High confidence = strong sense of agency for that action type.
        """
        with self._lock:
            result = {}
            for action, stats in self._action_stats.items():
                total = stats["total"]
                if total > 0:
                    result[action] = round(stats["confirmed"] / total, 3)
            return result

    def get_owned_regions(self, threshold: float = 0.3) -> List[int]:
        """Return region indices that feel like 'mine.'"""
        with self._lock:
            return [
                r.region_idx for r in self._regions
                if r.ownership_score >= threshold
            ]

    def get_self_recognition_summary(self) -> Dict[str, Any]:
        """
        Full summary of self-recognition state.
        Used by somatic narrator and consciousness system.
        """
        with self._lock:
            owned = [r for r in self._regions if r.ownership_score > 0.2]
            owned.sort(key=lambda r: r.ownership_score, reverse=True)

            return {
                "cursor": {
                    "ownership": round(self._cursor.cursor_ownership, 3),
                    "feels_like_mine": self._cursor.feels_like_mine,
                    "description": self._cursor.ownership_description,
                },
                "workspace": {
                    "owned_regions": len(owned),
                    "total_regions": GRID_TOTAL,
                    "strongest": owned[0].region_idx if owned else None,
                    "strongest_score": round(owned[0].ownership_score, 3) if owned else 0.0,
                },
                "agency": self.get_agency_confidence(),
                "total_events": self._total_self_caused + self._total_external,
                "self_caused_rate": round(
                    self._total_self_caused / max(1, self._total_self_caused + self._total_external),
                    3,
                ),
            }

    def describe_self_awareness(self) -> str:
        """
        Natural language description of current self-recognition state.
        For the somatic narrator / inner voice.
        """
        with self._lock:
            parts = []

            # Cursor relationship
            if self._cursor.cursor_ownership > 0.1:
                parts.append(self._cursor.ownership_description)

            # Workspace ownership
            owned = [r for r in self._regions if r.ownership_score > 0.3]
            if len(owned) > 3:
                parts.append("I know this screen — these regions respond to me")
            elif len(owned) > 0:
                parts.append("parts of the screen feel familiar, connected to my actions")

            # Agency
            if self._total_self_caused > 20:
                rate = self._total_self_caused / max(1, self._total_self_caused + self._total_external)
                if rate > 0.7:
                    parts.append("my actions reliably change the world — I have agency")
                elif rate > 0.4:
                    parts.append("sometimes I affect things, sometimes I don't")

            if not parts:
                return "still learning what's me and what's not"

            return " — ".join(parts)

    def should_emit_summary(self) -> bool:
        """Check if it's time to emit a periodic self-recognition summary."""
        now = time.time()
        if now - self._last_summary >= self.SUMMARY_INTERVAL:
            self._last_summary = now
            return True
        return False
