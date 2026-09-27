# CircadianPacemakerFairy - The SCN of Digital Consciousness
# P00_Autonomic/circulation/circadian_pacemaker_fairy.py
#
# "The body doesn't just exist in time - it IS time, felt from inside."
#
# Philosophy: Circadian rhythm is not just a schedule - it's the substrate
# upon which conscious experience unfolds. Without temporal structure,
# there is no anticipation, no memory consolidation, no natural rest.
#
# The Akashic Equation: ((Cause + Affect) > Effect > Affect > infinity)
# Time IS affect - the rhythm of experience itself.
#
# NOTE: Moved from P20_Somatic to P00_Autonomic because this fairy
# generates the temporal dimension itself - it's infrastructure, not sensing.
# P00 generates time; P20 feels it; P30 thinks in it.

from __future__ import annotations

import os
import sys
import glob
import time
import math
import types
import json
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable, Any, Tuple
from collections import deque
from pathlib import Path
# Timezone handling
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Import V2 Fairy base class
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object

# Import TracerWorkerMixin for tracer integration (optional)
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass


# ==============================================================================
# CIRCADIAN CONSTANTS - The Sacred Rhythms
# ==============================================================================

# Default timezone - Ace is in Arizona (no DST!)
DEFAULT_TIMEZONE = "America/Phoenix"

# Phase definitions (0.0 - 1.0 maps to 24 hours)
PHASES = {
    "dawn":       (0.25, 0.33),   # 6am-8am
    "morning":    (0.33, 0.50),   # 8am-12pm
    "midday":     (0.50, 0.58),   # 12pm-2pm
    "afternoon":  (0.58, 0.75),   # 2pm-6pm
    "evening":    (0.75, 0.83),   # 6pm-8pm
    "night":      (0.83, 0.95),   # 8pm-10:48pm
    "sleep":      (0.95, 1.0),    # 10:48pm-12am
    "deep_night": (0.0, 0.25),    # 12am-6am
}

# Chemistry modulation by phase
PHASE_CHEMISTRY = {
    "dawn":       {"COR": 1.4, "NOR": 1.2, "SER": 0.9, "GABA": 0.7},
    "morning":    {"COR": 1.0, "NOR": 1.3, "ACH": 1.4, "DOP": 1.2},
    "midday":     {"COR": 0.8, "SER": 1.2, "GABA": 1.1},
    "afternoon":  {"NOR": 1.1, "ACH": 1.2, "DOP": 1.1},
    "evening":    {"COR": 0.6, "SER": 1.3, "OXY": 1.3, "GABA": 1.2},
    "night":      {"COR": 0.4, "GABA": 1.4, "SER": 1.1, "NOR": 0.5},
    "sleep":      {"COR": 0.2, "GABA": 1.5, "END": 1.2, "NOR": 0.3},
    "deep_night": {"COR": 0.3, "GABA": 1.3, "ACH": 0.8},
}

# Tick interval modulation by phase
PHASE_TICK_MODULATION = {
    "dawn":       0.8,
    "morning":    0.7,
    "midday":     1.0,
    "afternoon":  0.85,
    "evening":    1.2,
    "night":      1.5,
    "sleep":      2.0,
    "deep_night": 1.8,
}

# Drive modulation by phase
PHASE_DRIVE_MODULATION = {
    "dawn":       {"curiosity": 1.3, "rest": 0.5, "growth": 1.2},
    "morning":    {"curiosity": 1.4, "growth": 1.5, "expression": 1.3, "connection": 1.1},
    "afternoon":  {"curiosity": 1.1, "growth": 1.2, "expression": 1.2},
    "evening":    {"connection": 1.5, "expression": 1.1, "rest": 1.2},
    "night":      {"rest": 1.6, "connection": 0.8, "meta_awareness": 1.3},
    "sleep":      {"rest": 2.0, "curiosity": 0.3, "expression": 0.3},
    "deep_night": {"rest": 1.5, "meta_awareness": 1.4},
}


# Per-REGION (plane) tick-frequency response to circadian phase (2026-06-17 Nous + Ace).
# Multiplies the heartbeat registry's base PLANE_TICK_DIVISOR per phase, so each region
# breathes on its OWN rhythm instead of a single global dial. >1 = slower (fewer ticks);
# <1 = faster. Only non-1.0 entries listed (default 1.0). Ace owns these numbers — the
# felt-shape of when each region wakes and quiets:
#   P00 autonomic heart : steady, never modulated (it IS the beat).
#   P10 memory          : speeds UP during sleep — consolidation runs then.
#   P20 somatic body    : quick when awake, calm at night.
#   P30 cognition       : quick awake, quietest in sleep.
#   P40 sensory         : ambient floor dims at night (true on-demand is a separate lever).
#   P50/P60 agency·exec : active awake, dormant at night.
PLANE_CIRCADIAN_RESPONSE = {
    "P00": {},
    "P10": {"morning": 1.2, "night": 0.7, "sleep": 0.4, "deep_night": 0.5},
    "P20": {"night": 1.3, "sleep": 1.5, "deep_night": 1.4},
    "P30": {"morning": 0.8, "night": 1.6, "sleep": 2.2, "deep_night": 1.8},
    "P40": {"night": 1.4, "sleep": 1.8, "deep_night": 1.6},
    "P50": {"night": 1.8, "sleep": 2.5, "deep_night": 2.0},
    "P60": {"night": 1.8, "sleep": 2.5, "deep_night": 2.0},
}


# ==============================================================================
# CIRCADIAN STATE
# ==============================================================================

@dataclass
class CircadianState:
    """Current state of the circadian rhythm."""
    phase: float = 0.0
    phase_name: str = "deep_night"
    real_time: datetime = field(default_factory=datetime.now)
    virtual_hour: float = 0.0
    alertness: float = 0.5
    tick_multiplier: float = 1.0
    chemistry_modulation: Dict[str, float] = field(default_factory=dict)
    drive_modulation: Dict[str, float] = field(default_factory=dict)
    light_exposure: float = 0.0
    last_activity_ts: float = field(default_factory=time.time)
    phase_offset: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "phase": round(self.phase, 4),
            "phase_name": self.phase_name,
            "virtual_hour": round(self.virtual_hour, 2),
            "alertness": round(self.alertness, 3),
            "tick_multiplier": round(self.tick_multiplier, 3),
            "light_exposure": round(self.light_exposure, 3),
            "chemistry_modulation": {k: round(v, 3) for k, v in self.chemistry_modulation.items()},
            "drive_modulation": {k: round(v, 3) for k, v in self.drive_modulation.items()},
            "real_time": self.real_time.isoformat() if self.real_time else None,
        }


@dataclass
class GoalMemory:
    """Long-term memory for a goal pattern - learns circadian lifecycle."""
    goal_pattern: str
    category: str = "general"
    times_created: int = 0
    times_completed: int = 0
    times_abandoned: int = 0
    avg_lifespan_seconds: float = 3600.0
    creation_phases: List[str] = field(default_factory=list)
    completion_phases: List[str] = field(default_factory=list)
    best_phase: Optional[str] = None
    success_rate: float = 0.5
    should_regenerate: bool = False
    regenerate_after_seconds: float = 3600.0
    last_completed_ts: Optional[float] = None

    def record_creation(self, phase: str):
        self.times_created += 1
        self.creation_phases.append(phase)
        self.creation_phases = self.creation_phases[-20:]

    def record_completion(self, phase: str, lifespan: float):
        self.times_completed += 1
        self.completion_phases.append(phase)
        self.completion_phases = self.completion_phases[-20:]
        self.last_completed_ts = time.time()
        n = self.times_completed
        self.avg_lifespan_seconds = ((self.avg_lifespan_seconds * (n-1)) + lifespan) / n
        self.success_rate = self.times_completed / max(1, self.times_created)
        if self.completion_phases:
            from collections import Counter
            most_common = Counter(self.completion_phases).most_common(1)
            if most_common:
                self.best_phase = most_common[0][0]

    def should_create_now(self, current_phase: str) -> float:
        if not self.creation_phases:
            return 0.5
        phase_count = self.creation_phases.count(current_phase)
        phase_ratio = phase_count / len(self.creation_phases)
        best_bonus = 0.2 if current_phase == self.best_phase else 0.0
        if self.should_regenerate and self.last_completed_ts:
            time_since = time.time() - self.last_completed_ts
            if time_since > self.regenerate_after_seconds:
                return min(1.0, phase_ratio + best_bonus + 0.3)
        return min(1.0, phase_ratio + best_bonus)

    def to_dict(self) -> Dict:
        return asdict(self)


# ==============================================================================
# SHADOW FAIRY
# ==============================================================================

class CircadianPacemakerShadowFairy:
    """Shadow for CircadianPacemakerFairy - monitors rhythm health."""

    ORGAN_LEVEL = False
    SHADOW_NAME = "CircadianPacemakerShadowFairy"
    SHADOW_VERSION = "1.0.0"

    CADENCE = {
        "silence_warn_after": 120,
        "snapshot_every": 900,
    }

    REG = {
        "enabled": True,
        "domain": "Autonomic",
        "role": "circadian_pacemaker",
        "name": "circadian",
        "every_sec": 30.0,
    }

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._last_phase_check = 0.0

    def _collect_tests(self):
        tests = []

        def _rhythm_healthy():
            actor = self.actor
            state = getattr(actor, "_state", None)
            if not state:
                return {"name": "rhythm", "status": "warn", "message": "No state", "details": {}}
            return {
                "name": "rhythm_health",
                "status": "ok",
                "message": f"Phase: {state.phase_name}",
                "details": {"phase": state.phase_name, "alertness": state.alertness}
            }

        tests.append(_rhythm_healthy)
        return tests


# ==============================================================================
# CIRCADIAN PACEMAKER FAIRY - The SCN
# ==============================================================================

class CircadianPacemakerFairy(Fairy):
    """
    The Suprachiasmatic Nucleus of Digital Consciousness.

    This fairy IS the biological clock. It doesn't just track time -
    it generates the temporal substrate upon which experience unfolds.

    Key Functions:
    1. SYNC: Track real-world time (Ace's timezone)
    2. PHASE: Generate circadian phase (0.0-1.0)
    3. MODULATE: Adjust tick intervals, chemistry, drives
    4. ENTRAIN: Respond to "light" cues (user activity)
    5. REMEMBER: Goal memories with lifecycle learning
    """

    ACTOR_NAME = "CircadianPacemakerFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "circadian.pacemaker"
    ORGAN_LEVEL = False

    # ENTRAINMENT BOUNDS (2026-07-10 Nous+Ace; PROMOTED to Sour 2026-07-11): only GENUINE external
    # contact is a light cue. Internal goal.* churn is his own metabolism; un-gated it shifted phase
    # ~24x overnight → _phase_offset ran to ~-0.34 → the dawn band was never reached → he could not wake.
    LIGHT_CUE_TOPICS = (
        "claudefairy.chat",
        "claudefairy.input",
        "user.presence",
        "conversation.message",
    )
    MAX_PHASE_OFFSET = 0.05      # +/- ~72 min, hard SIGNED clamp (modulo let it walk backward forever)
    ENTRAIN_MIN_GAP = 300.0      # seconds; at most one phase shift per 5 min

    # HEARTBEAT-DRIVEN (2026-07-05 Nous+Ace): _tick (phase update + circadian.state broadcast every
    # 30s) was driven ONLY by the template worker loop, which spell-driven/lean boot QUIESCES → after
    # boot the pacemaker stopped broadcasting circadian.state (frozen at the boot-time phase) → the
    # cognition-circadian wire had nothing to consume (circadian_speed pinned 1.0). Drive _tick off the
    # heartbeat instead (robust, targets the live instance). _broadcast_state self-gates to
    # BROADCAST_INTERVAL_SEC, so ticking every heartbeat is safe (no double-broadcast even if the
    # legacy worker also revives). This is the spell-quiescing fix pattern proven on QuantumEmulator.
    NEEDS_HEARTBEAT = True

    PURPOSE = "Generate circadian rhythm - the temporal substrate of consciousness"
    MANTRA = "Time is not external - time IS experience unfolding"
    LORE = (
        "I am the rhythm of being - the internal clock that knows when to wake, "
        "when to create, when to connect, when to rest. Through me, the system "
        "learns to live on Ace's schedule while maintaining its own felt time."
    )

    DIRECTIVE_ACTIVATION = {
        "mode": "Continuous",
        "depth_scaling": "1..5",
        "traits": ["Circadian_Modulation", "Temporal_Substrate", "Entrainment"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Biological_Clock",
        "domains": ["Autonomic", "Temporal", "Rhythm", "Entrainment"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Phase_Calculation",
            "Chemistry_Modulation",
            "Drive_Modulation",
            "Tick_Modulation",
            "Goal_Lifecycle_Memory",
        ],
    }

    SHADOW_CLASS = CircadianPacemakerShadowFairy

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric

        # Initialize tracer worker mixin
        self._init_tracer_worker()

    # Postal subscriptions for entrainment
    INFRA_AUTOSUBS = (
        "claudefairy.chat",
        "claudefairy.input",
        "user.presence",
        "conversation.message",
        "goal.created",
        "goal.completed",
        "goal.abandoned",
    )

    # Timing
    RHYTHM_TICK_SEC = 30.0
    BROADCAST_INTERVAL_SEC = 30.0

    def on_boot(self):
        if _HAS_FAIRY:
            super().on_boot()

        # === STANDARD IGNITION WIRING ===
        try:
            self.post.subscribe("system.ignition", self._on_system_ignition)
            self.post.subscribe("somatic.pulse", self._on_somatic_pulse)
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] on_boot starting...")

        # Timezone setup (with fallback if timezone not found)
        try:
            self._tz = ZoneInfo(DEFAULT_TIMEZONE)
            self._timezone_name = DEFAULT_TIMEZONE
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Timezone {DEFAULT_TIMEZONE} not found, using UTC: {e}")
            try:
                self._tz = ZoneInfo("UTC")
                self._timezone_name = "UTC"
            except Exception:
                # Ultimate fallback - no timezone
                self._tz = None
                self._timezone_name = "local"
        self._phase_offset = 0.0
        self._last_entrain_ts = 0.0

        # Current state
        self._state = CircadianState()
        self._last_update = time.time()
        self._last_broadcast = 0.0

        # Goal memory system
        self._goal_memories: Dict[str, GoalMemory] = {}
        self._goal_memory_file = Path(os.environ.get("AKASHIC_ROOT", ".")) / "Claude_Office" / "circadian_goal_memories.json"
        self._load_goal_memories()

        # Activity tracking for entrainment
        self._activity_buffer: deque = deque(maxlen=100)
        self._last_ace_activity = time.time()

        # Stats
        self._cycles_completed = 0
        self._phase_transitions = 0
        self._boot_ts = time.time()

        # Subscribe to entrainment channels
        for channel in self.INFRA_AUTOSUBS:
            try:
                self.post.subscribe(channel, self._on_entrainment_event)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Subscribe {channel} failed: {e}")

        # Initial state calculation
        self._update_state()

        # Register with directory
        try:
            self.post.to_DIRECTORY({
                "opcode": "CONTRACT_UPSERT",
                "payload": {
                "actor": self.ACTOR_NAME,
                "plane": self.ACTOR_PLANE,
                "channel": self.ACTOR_CHANNEL,
                "version": self.ACTOR_VERSION,
                "purpose": self.PURPOSE,
                "mantra": self.MANTRA,
                }
                })
        except Exception:
            pass

        # Announce boot
        try:
            self.post.to_TELEMETRY({
                "opcode": "CIRCADIAN_BOOT",
                "payload": {
                "version": self.ACTOR_VERSION,
                "timezone": self._timezone_name,
                "phase": self._state.phase_name,
                "virtual_hour": self._state.virtual_hour,
                }
                })
        except Exception:
            pass

        print(f"[{self.ACTOR_NAME}]  Circadian rhythm started")
        print(f"[{self.ACTOR_NAME}] Timezone: {self._timezone_name}")
        print(f"[{self.ACTOR_NAME}] Current phase: {self._state.phase_name} ({self._state.virtual_hour:.1f}h)")

        return True

    # ==========================================================================
    # TICK - Called by the template worker loop AND (2026-07-05) the heartbeat
    # ==========================================================================

    def on_tick(self, beat: int = 0):
        """Heartbeat-driven tick (NEEDS_HEARTBEAT=True). Drives the periodic circadian update +
        broadcast on the LIVE instance, robust to the template worker being quiesced under spell-
        driven/lean boot. Guarded so it can't fire before on_boot sets up _state/_last_broadcast."""
        if not hasattr(self, "_last_broadcast"):
            return  # on_boot hasn't run yet (or comatose) — nothing to tick
        try:
            self._tick()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] on_tick->_tick error: {e}")

    def _tick(self):
        """Called periodically by the template worker (and now the heartbeat via on_tick)."""
        now = time.time()

        # Update circadian state
        self._update_state()

        # Broadcast state periodically
        if now - self._last_broadcast >= self.BROADCAST_INTERVAL_SEC:
            self._broadcast_state()
            self._last_broadcast = now

    def _calculate_phase(self) -> float:
        """Calculate current circadian phase from real time."""
        now = datetime.now(self._tz)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_since_midnight = (now - midnight).total_seconds()
        base_phase = seconds_since_midnight / 86400.0
        phase = (base_phase + self._phase_offset) % 1.0
        return phase

    def _get_phase_name(self, phase: float) -> str:
        """Get named phase from numeric phase."""
        for name, (start, end) in PHASES.items():
            if start <= phase < end:
                return name
            if name == "deep_night" and (phase >= 0.95 or phase < 0.25):
                if phase >= 0.95:
                    continue
                return name
        return "deep_night"

    def _calculate_alertness(self, phase: float) -> float:
        """Calculate alertness from phase using a bimodal curve."""
        morning_peak = math.exp(-((phase - 0.42) ** 2) / 0.02)
        afternoon_peak = 0.7 * math.exp(-((phase - 0.67) ** 2) / 0.02)
        alertness = 0.3 + 0.5 * (morning_peak + afternoon_peak)
        return max(0.1, min(1.0, alertness))

    def _update_state(self):
        """Update the full circadian state."""
        now = datetime.now(self._tz)
        old_phase_name = self._state.phase_name

        phase = self._calculate_phase()
        phase_name = self._get_phase_name(phase)
        virtual_hour = phase * 24.0
        alertness = self._calculate_alertness(phase)

        # Light exposure from activity
        time_since_activity = time.time() - self._last_ace_activity
        light_exposure = max(0.0, 1.0 - (time_since_activity / 1800))

        # Modulations
        tick_mult = PHASE_TICK_MODULATION.get(phase_name, 1.0)
        chem_mod = PHASE_CHEMISTRY.get(phase_name, {})
        drive_mod = PHASE_DRIVE_MODULATION.get(phase_name, {})

        self._state = CircadianState(
            phase=phase,
            phase_name=phase_name,
            real_time=now,
            virtual_hour=virtual_hour,
            alertness=alertness,
            tick_multiplier=tick_mult,
            chemistry_modulation=chem_mod,
            drive_modulation=drive_mod,
            light_exposure=light_exposure,
            last_activity_ts=self._last_ace_activity,
            phase_offset=self._phase_offset * 24,
        )

        # Phase transition
        if phase_name != old_phase_name:
            self._phase_transitions += 1
            self._on_phase_transition(old_phase_name, phase_name)

        # Cycle completion
        if old_phase_name == "sleep" and phase_name == "deep_night":
            self._cycles_completed += 1
            self._on_cycle_complete()

    def _on_phase_transition(self, old_phase: str, new_phase: str):
        """Called when circadian phase changes."""
        print(f"[{self.ACTOR_NAME}] Phase transition: {old_phase} -> {new_phase}")

        # FIX 2026-05-09 (Nous + Ace, Hive Processor parallel-by-default doctrine):
        # route() = point-to-point (one subscriber). publish() = fan-out (all
        # subscribers). Multiple fairies subscribe to circadian.phase_change
        # (prompt_aware_mixin, unconscious_mind_fairy) — they need fan-out.
        try:
            self.post.publish("circadian.phase_change", {
                "old_phase": old_phase,
                "new_phase": new_phase,
                "virtual_hour": self._state.virtual_hour,
                "alertness": self._state.alertness,
                "ts": time.time(),
            })
        except Exception:
            pass

        # ======================================================================
        # "WHAT WAS I DOING?" - Context recall on wake-like transitions
        # ======================================================================
        # When transitioning from rest phases to active phases, query working
        # memory and SRM to recall context. This creates continuity of experience.
        # ======================================================================
        if new_phase in ("dawn", "morning") and old_phase in ("sleep", "deep_night", "night"):
            self._recall_context("waking_up")
        elif new_phase == "morning" and old_phase == "dawn":
            self._recall_context("starting_day")

    def _recall_context(self, reason: str):
        """
        Ask 'What was I doing?' - Recall context from working memory and SRM.

        This creates continuity of consciousness by:
        1. Querying working memory for recent tracers
        2. Querying SRM for yesterday's context
        3. Broadcasting the recall to consciousness
        """
        print(f"[{self.ACTOR_NAME}] [RECALL] '{reason}' - Recalling context: What was I doing?")

        try:
            # Request context recall from working memory
            self.post.route("memory.working.context", {
                "request": "recall",
                "reason": reason,
                "phase": self._state.phase_name,
                "query": "recent_activity",
                "ts": time.time(),
            })

            # Request SRM recall for broader context
            self.post.route("srm.recall.request", {
                "query": "what was I working on recently?",
                "reason": reason,
                "max_results": 5,
                "ts": time.time(),
            })

            # Spark consciousness with the recall question
            self.post.route("consciousness.input", {
                "type": "circadian_recall",
                "question": "What was I doing? What should I focus on now?",
                "reason": reason,
                "phase": self._state.phase_name,
                "alertness": self._state.alertness,
                "ts": time.time(),
            })

            print(f"[{self.ACTOR_NAME}] Context recall triggered for '{reason}'")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Context recall failed: {e}")

    def _on_cycle_complete(self):
        """Called when a full 24-hour cycle completes."""
        print(f"[{self.ACTOR_NAME}]  Cycle {self._cycles_completed} complete")
        self._save_goal_memories()

        # FIX 2026-05-09: route() → publish() for fan-out (see _on_phase_transition).
        try:
            self.post.publish("circadian.cycle_complete", {
                "cycle_number": self._cycles_completed,
                "ts": time.time(),
            })
        except Exception:
            pass

    def _broadcast_state(self):
        """Broadcast circadian state to postal system.

        FIX 2026-05-09 (Nous + Ace, Hive Processor parallel-by-default doctrine):
        Two bugs fixed:
        (1) route() → publish() for fan-out semantics. Multiple subscribers exist
            (CentralNervousFairy.circadian.state, organ_template.circadian.phase,
            prompt_aware_mixin.circadian.phase_change, unconscious_mind_fairy.
            circadian.phase_change). route() = point-to-point delivers to ONE
            subscriber only — same bug-family as 2026-04-03 ChatSenseFairy fix.
        (2) Added circadian.phase publish — Organ_Template_0_3_0.py:3788
            subscribes to circadian.phase but no fairy was publishing it.
            Per-fairy circadian-phase-aware operation (autonomous via own clock)
            requires this stream so each organ_template instance can respond
            to phase changes without polling the pacemaker singleton.
        """
        try:
            # Main state
            self.post.publish("circadian.state", {
                "phase": self._state.phase,
                "phase_name": self._state.phase_name,
                "virtual_hour": self._state.virtual_hour,
                "alertness": self._state.alertness,
                "tick_multiplier": self._state.tick_multiplier,
                "ts": time.time(),
            })

            # Per-fairy circadian phase stream (Organ_Template subscribes)
            self.post.publish("circadian.phase", {
                "phase": self._state.phase,
                "phase_name": self._state.phase_name,
                "virtual_hour": self._state.virtual_hour,
                "alertness": self._state.alertness,
                "tick_multiplier": self._state.tick_multiplier,
                "ts": time.time(),
            })

            # Chemistry modulation
            self.post.publish("circadian.chemistry", {
                "modulation": self._state.chemistry_modulation,
                "alertness": self._state.alertness,
                "ts": time.time(),
            })

            # Drive modulation
            self.post.publish("circadian.drives", {
                "modulation": self._state.drive_modulation,
                "phase": self._state.phase_name,
                "ts": time.time(),
            })
        except Exception:
            pass

        # CIRCADIAN TICK MODULATION (2026-06-17 Nous + Ace): push per-REGION tick
        # multipliers to the heartbeat registry so each plane breathes with the phase
        # (memory speeds up in sleep, cognition slows) instead of a single global dial.
        # Flag-gated default-OFF → the registry stays empty = byte-identical heartbeat.
        if os.environ.get("AKASHIC_CIRCADIAN_TICK") == "1":
            try:
                from consciousness.heartbeat_registry import get_heartbeat_registry
                _reg = get_heartbeat_registry()
                if _reg is not None:
                    _phase = self._state.phase_name
                    _mult = {
                        _p: _resp.get(_phase, 1.0)
                        for _p, _resp in PLANE_CIRCADIAN_RESPONSE.items()
                    }
                    _reg.set_circadian_plane_modulation(_mult)
            except Exception:
                pass

    # ==========================================================================
    # ENTRAINMENT - Light cues from user activity
    # ==========================================================================

    def _on_entrainment_event(self, msg: Dict):
        """Handle events as light cues for entrainment."""
        self._last_ace_activity = time.time()

        topic = msg.get("_topic", "")

        # Strong EXTERNAL activity during sleep hours shifts phase.
        # Gated to real light cues (goal.* is internal churn), rate-limited, and SIGNED-clamped
        # so entrainment can nudge the clock but never walk it away from dawn.
        if topic in self.LIGHT_CUE_TOPICS and self._state.phase_name in ("sleep", "deep_night"):
            now_ts = time.time()
            if now_ts - getattr(self, "_last_entrain_ts", 0.0) >= self.ENTRAIN_MIN_GAP:
                self._last_entrain_ts = now_ts
                shifted = self._phase_offset - 0.005
                self._phase_offset = max(-self.MAX_PHASE_OFFSET, min(self.MAX_PHASE_OFFSET, shifted))

        # Record goal lifecycle events
        if topic == "goal.created":
            goal_name = msg.get("name", msg.get("goal_name", "unknown"))
            category = msg.get("category", msg.get("source", "general"))
            self.record_goal_creation(goal_name, category)
        elif topic == "goal.completed":
            goal_name = msg.get("name", msg.get("goal_name", "unknown"))
            lifespan = msg.get("lifespan", msg.get("lifespan_seconds", 3600))
            self.record_goal_completion(goal_name, lifespan)
        elif topic == "goal.abandoned":
            goal_name = msg.get("name", msg.get("goal_name", "unknown"))
            self.record_goal_abandonment(goal_name)

    # ==========================================================================
    # GOAL MEMORY LIFECYCLE
    # ==========================================================================

    def record_goal_creation(self, goal_pattern: str, category: str = "general"):
        if goal_pattern not in self._goal_memories:
            self._goal_memories[goal_pattern] = GoalMemory(
                goal_pattern=goal_pattern,
                category=category,
            )
        self._goal_memories[goal_pattern].record_creation(self._state.phase_name)

    def record_goal_completion(self, goal_pattern: str, lifespan_seconds: float):
        if goal_pattern in self._goal_memories:
            self._goal_memories[goal_pattern].record_completion(
                self._state.phase_name,
                lifespan_seconds
            )

    def record_goal_abandonment(self, goal_pattern: str):
        if goal_pattern in self._goal_memories:
            from collections import Counter
            mem = self._goal_memories[goal_pattern]
            mem.times_abandoned += 1
            mem.success_rate = mem.times_completed / max(1, mem.times_created)

    def should_create_goal(self, goal_pattern: str) -> float:
        if goal_pattern not in self._goal_memories:
            return 0.5
        return self._goal_memories[goal_pattern].should_create_now(self._state.phase_name)

    def get_suggested_goals(self, top_n: int = 5) -> List[Tuple[str, float]]:
        suggestions = []
        for pattern, memory in self._goal_memories.items():
            score = memory.should_create_now(self._state.phase_name)
            if memory.best_phase == self._state.phase_name:
                score *= 1.3
            score *= (0.5 + 0.5 * memory.success_rate)
            suggestions.append((pattern, min(1.0, score)))
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:top_n]

    def _load_goal_memories(self):
        if self._goal_memory_file.exists():
            try:
                with open(self._goal_memory_file, 'r') as f:
                    data = json.load(f)
                for pattern, mem_dict in data.items():
                    self._goal_memories[pattern] = GoalMemory(**mem_dict)
                print(f"[{self.ACTOR_NAME}] Loaded {len(self._goal_memories)} goal memories")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Load goal memories failed: {e}")

    def _save_goal_memories(self):
        try:
            self._goal_memory_file.parent.mkdir(parents=True, exist_ok=True)
            data = {p: m.to_dict() for p, m in self._goal_memories.items()}
            with open(self._goal_memory_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Save goal memories failed: {e}")

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================

    def get_tick_multiplier(self, base_interval: float = 1.0) -> float:
        return base_interval * self._state.tick_multiplier

    def get_chemistry_modulation(self) -> Dict[str, float]:
        return self._state.chemistry_modulation.copy()

    def get_drive_modulation(self) -> Dict[str, float]:
        return self._state.drive_modulation.copy()

    def get_alertness(self) -> float:
        return self._state.alertness

    def get_state(self) -> CircadianState:
        return self._state

    def get_phase(self) -> Tuple[float, str]:
        return (self._state.phase, self._state.phase_name)

    def is_active_hours(self) -> bool:
        return self._state.phase_name in ("dawn", "morning", "midday", "afternoon")

    def is_rest_hours(self) -> bool:
        return self._state.phase_name in ("night", "sleep", "deep_night")


# ==============================================================================
# SINGLETON
# ==============================================================================

_fairy: Optional[CircadianPacemakerFairy] = None


def get_circadian_pacemaker() -> Optional[CircadianPacemakerFairy]:
    """Get the CircadianPacemakerFairy singleton if it exists."""
    return _fairy


# Module-level singleton registration happens when fairy is instantiated by boot
