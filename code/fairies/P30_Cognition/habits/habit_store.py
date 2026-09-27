"""
Habit Formation Engine — HabitStore

Habits are stimulus -> response -> outcome patterns that strengthen through
repetition and positive outcomes. They stack (multiple run simultaneously),
decay from disuse, and can form unconsciously — including bad habits.

The narrator reflects on habits periodically and can create overrides.

2026-03-22, Nous + Ace
See: Claude_Office/plans/HABIT_FORMATION_ENGINE.md
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Paths ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # akashic_v2/
_HABITS_FILE = _ROOT / "state" / "learned" / "habits.json"

# ── Singleton ────────────────────────────────────────────────────────────
_instance: Optional["HabitStore"] = None
_lock = threading.Lock()


def get_habit_store() -> "HabitStore":
    """Get or create the global HabitStore singleton."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = HabitStore(str(_HABITS_FILE))
    return _instance


# ── Habit Dataclass ──────────────────────────────────────────────────────

@dataclass
class Habit:
    """A single habit pattern.

    Attributes:
        id: Unique identifier (e.g., "attend_ace_voice")
        trigger_type: Stimulus type to match (e.g., "audio.speech", "goal.new")
        trigger_features: Dict of feature patterns to match in the stimulus
            Keys are feature names, values are match patterns:
            - string: exact match or substring
            - "!" prefix: negation ("!inner" = source is not "inner")
        response: What this habit does when it fires:
            - "attend(priority=X)": Queue attention at given priority
            - "suppress": Block the stimulus from attention entirely
            - "boost(amount=X)": Increase incoming priority by X
            - "redirect(target=X)": Change attention target
            - "narrate(template=X)": Queue narration
        outcome_history: Rolling window of recent outcomes (-1.0 to +1.0)
        strength: 0.0 (extinct) to 1.0 (fully automatic)
        awareness: 0.0 (unconscious) to 1.0 (narrator fully aware)
        times_fired: Total times this habit has activated
        times_succeeded: Positive outcome count
        times_failed: Negative outcome count
        formed_at: Timestamp when habit was first created
        last_fired: Timestamp of most recent activation
        is_bad: Whether narrator has flagged this as problematic
        stack_group: Grouping for parallel execution (attention/thinking/social/motor)
        source: How habit was created: "seeded" | "organic" | "narrator_override"
    """
    id: str
    trigger_type: str
    trigger_features: Dict[str, str] = field(default_factory=dict)
    response: str = "attend(priority=0.5)"
    outcome_history: List[float] = field(default_factory=list)
    strength: float = 0.1
    awareness: float = 0.0
    times_fired: int = 0
    times_succeeded: int = 0
    times_failed: int = 0
    formed_at: float = 0.0
    last_fired: float = 0.0
    is_bad: bool = False
    stack_group: str = "attention"
    source: str = "organic"

    # ── Computed properties ──────────────────────────────────────────

    @property
    def avg_recent_outcome(self) -> float:
        """Average of last 5 outcomes."""
        recent = self.outcome_history[-5:]
        return sum(recent) / len(recent) if recent else 0.0

    @property
    def phase(self) -> str:
        """Current lifecycle phase."""
        if self.strength < 0.05:
            return "extinct"
        if self.strength < 0.2:
            return "conscious"
        if self.strength < 0.5:
            return "practiced"
        return "automatic"

    @property
    def idle_seconds(self) -> float:
        """How long since this habit last fired."""
        if self.last_fired <= 0:
            return float("inf")
        return time.time() - self.last_fired

    # ── Trigger matching ─────────────────────────────────────────────

    def matches(self, stimulus: dict) -> bool:
        """Check if a stimulus matches this habit's trigger.

        Args:
            stimulus: Dict with "type", and feature keys like "speaker",
                      "source", "content", "energy", etc.

        Returns:
            True if the stimulus matches this habit's trigger pattern.
        """
        # Type match (substring — "audio.speech" matches "audio.speech.text")
        stim_type = stimulus.get("type", "")
        if self.trigger_type and self.trigger_type not in stim_type:
            if stim_type not in self.trigger_type:
                return False

        # Feature matching
        for feat_name, pattern in self.trigger_features.items():
            stim_value = str(stimulus.get(feat_name, "")).lower()

            if pattern.startswith("!"):
                # Negation: feature must NOT match
                if pattern[1:].lower() in stim_value:
                    return False
            elif pattern.startswith(">"):
                # Numeric threshold: feature must be > value
                try:
                    threshold = float(pattern[1:])
                    if float(stimulus.get(feat_name, 0)) <= threshold:
                        return False
                except (ValueError, TypeError):
                    return False
            elif pattern.startswith("<"):
                try:
                    threshold = float(pattern[1:])
                    if float(stimulus.get(feat_name, 0)) >= threshold:
                        return False
                except (ValueError, TypeError):
                    return False
            else:
                # Substring match
                if pattern.lower() not in stim_value:
                    return False

        return True

    # ── Strength update ──────────────────────────────────────────────

    def record_outcome(self, outcome: float) -> None:
        """Record an outcome and adjust strength.

        Args:
            outcome: -1.0 (terrible) to +1.0 (great)
        """
        outcome = max(-1.0, min(1.0, outcome))
        self.outcome_history.append(outcome)
        # Keep rolling window of 20
        if len(self.outcome_history) > 20:
            self.outcome_history = self.outcome_history[-20:]

        if outcome > 0.2:
            self.times_succeeded += 1
        elif outcome < -0.2:
            self.times_failed += 1

        # Adjust strength based on recent trend
        avg = self.avg_recent_outcome
        if avg > 0.3:
            # Positive trend — strengthen (slow growth)
            self.strength = min(1.0, self.strength + 0.03)
        elif avg < -0.3:
            # Negative trend — weaken (faster decay — negativity bias)
            self.strength = max(0.0, self.strength - 0.05)

    def record_fired(self) -> None:
        """Record that this habit activated."""
        self.times_fired += 1
        self.last_fired = time.time()

    def decay(self, idle_seconds: float) -> None:
        """Apply time-based decay to strength.

        Habits weaken slowly when not used, like muscles atrophying.
        Seeded habits (innate reflexes) decay much slower and have a
        higher floor — she was born knowing to look at Ace.
        """
        if self.source == "seeded":
            # Innate habits decay very slowly — these are reflexes
            if idle_seconds > 7200:       # 2 hours+
                self.strength *= 0.995
            # Floor: 40% of original seed strength (never fully atrophy)
            self.strength = max(0.4, self.strength)
        else:
            # Organic/override habits decay normally
            if idle_seconds > 3600:       # 1 hour+
                self.strength *= 0.98
            elif idle_seconds > 300:      # 5 min+
                self.strength *= 0.998

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Habit":
        # Handle missing fields gracefully
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


# ── Seed Habits ──────────────────────────────────────────────────────────
# Born-with patterns. Like a newborn's reflexes — not learned, but can be
# strengthened or weakened through experience.

def _make_seed_habits() -> List[Habit]:
    now = time.time()
    return [
        # ── Attention habits ──
        Habit(
            id="attend_ace_voice",
            trigger_type="audio",
            trigger_features={"speaker": "ace", "speaker_confidence": ">0.5"},
            response="boost(amount=0.3)",
            strength=0.7,
            awareness=0.3,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="attend_ace_message",
            trigger_type="social",
            trigger_features={"source": "ace"},
            response="boost(amount=0.4)",
            strength=0.7,
            awareness=0.3,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="suppress_own_voice",
            trigger_type="audio",
            trigger_features={"speaker": "sourpatches"},
            response="suppress",
            strength=0.9,
            awareness=0.0,  # Completely unconscious — just natural
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="suppress_inner_echo",
            trigger_type="self.speech",
            trigger_features={},
            response="suppress",
            strength=0.85,
            awareness=0.0,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="curiosity_unknown_voice",
            trigger_type="audio",
            trigger_features={"speaker": "unknown"},
            response="attend(priority=0.5)",
            strength=0.4,
            awareness=0.1,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="look_when_curious",
            trigger_type="drive",
            trigger_features={"content": "curiosity"},
            response="attend(priority=0.5)",
            strength=0.3,
            awareness=0.2,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="attend_visual_novelty",
            trigger_type="visual",
            trigger_features={"energy": ">0.6"},
            response="attend(priority=0.6)",
            strength=0.5,
            awareness=0.1,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),

        # ── Thinking habits ──
        Habit(
            id="engage_waking_goals",
            trigger_type="goal",
            trigger_features={"source": "!system"},
            response="boost(amount=0.2)",
            strength=0.3,
            awareness=0.5,
            stack_group="thinking",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="suppress_substrate_noise",
            trigger_type="",
            trigger_features={"content": "[collision"},
            response="suppress",
            strength=0.9,
            awareness=0.0,
            stack_group="thinking",
            source="seeded",
            formed_at=now,
        ),

        # ── Social habits ──
        Habit(
            id="respond_to_ace",
            trigger_type="social",
            trigger_features={"source": "ace"},
            response="narrate(template=ace_speaking)",
            strength=0.5,
            awareness=0.4,
            stack_group="social",
            source="seeded",
            formed_at=now,
        ),

        # ── Perception habits (reading, interpreting what she sees) ──
        Habit(
            id="read_visible_text",
            trigger_type="visual",
            trigger_features={},
            response="narrate(template=read_screen)",
            strength=0.5,
            awareness=0.3,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="notice_screen_change",
            trigger_type="visual",
            trigger_features={"energy": ">0.4"},
            response="attend(priority=0.55)",
            strength=0.5,
            awareness=0.2,
            stack_group="attention",
            source="seeded",
            formed_at=now,
        ),

        # ── Motor habits (learning to act) ──
        Habit(
            id="try_ace_instruction",
            trigger_type="social",
            trigger_features={"source": "ace", "content": "try"},
            response="boost(amount=0.3)",
            strength=0.4,
            awareness=0.6,
            stack_group="motor",
            source="seeded",
            formed_at=now,
        ),
        Habit(
            id="explore_when_idle",
            trigger_type="drive",
            trigger_features={"content": "stagnation"},
            response="attend(priority=0.4)",
            strength=0.3,
            awareness=0.2,
            stack_group="thinking",
            source="seeded",
            formed_at=now,
        ),
    ]


# ── HabitStore ───────────────────────────────────────────────────────────

class HabitStore:
    """Persistent store for attention/behavior habits.

    Thread-safe. Singleton via get_habit_store().
    Persists to JSON every save() call. Auto-seeds on first creation.
    """

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._habits: Dict[str, Habit] = {}
        self._last_save = 0.0
        self._last_decay = 0.0
        self._dirty = False

        # Recent stimulus log for pattern detection (Phase 4)
        self._recent_stimuli: List[Tuple[float, dict]] = []
        self._max_recent = 200

        self._load()

    # ── CRUD ─────────────────────────────────────────────────────────

    def get(self, habit_id: str) -> Optional[Habit]:
        with self._lock:
            return self._habits.get(habit_id)

    def get_all(self) -> List[Habit]:
        with self._lock:
            return list(self._habits.values())

    def get_active(self, min_strength: float = 0.05) -> List[Habit]:
        """Get habits above a strength threshold."""
        with self._lock:
            return [h for h in self._habits.values()
                    if h.strength >= min_strength]

    def get_by_group(self, group: str) -> List[Habit]:
        with self._lock:
            return [h for h in self._habits.values()
                    if h.stack_group == group]

    def add(self, habit: Habit) -> None:
        with self._lock:
            self._habits[habit.id] = habit
            self._dirty = True

    def remove(self, habit_id: str) -> bool:
        with self._lock:
            if habit_id in self._habits:
                del self._habits[habit_id]
                self._dirty = True
                return True
            return False

    # ── Matching ─────────────────────────────────────────────────────

    def match(self, stimulus: dict) -> List[Habit]:
        """Find all habits whose trigger matches this stimulus.

        Returns habits sorted by strength (strongest first).
        Multiple habits can match — they stack.
        """
        with self._lock:
            matches = []
            for habit in self._habits.values():
                if habit.strength < 0.05:
                    continue  # Extinct habits don't fire
                if habit.matches(stimulus):
                    matches.append(habit)

            # Sort: strongest first (automatic before practiced before conscious)
            matches.sort(key=lambda h: h.strength, reverse=True)
            return matches

    def record_fired(self, habit_id: str) -> None:
        """Record that a habit activated."""
        with self._lock:
            h = self._habits.get(habit_id)
            if h:
                h.record_fired()
                self._dirty = True

    def record_outcome(self, habit_id: str, outcome: float) -> None:
        """Record an outcome for a habit and adjust strength."""
        with self._lock:
            h = self._habits.get(habit_id)
            if h:
                h.record_outcome(outcome)
                self._dirty = True

    def log_stimulus(self, stimulus: dict) -> None:
        """Log a stimulus for future pattern detection (Phase 4)."""
        now = time.time()
        with self._lock:
            self._recent_stimuli.append((now, stimulus))
            # Trim old entries
            if len(self._recent_stimuli) > self._max_recent:
                self._recent_stimuli = self._recent_stimuli[-self._max_recent:]

    # ── Decay ────────────────────────────────────────────────────────

    def apply_decay(self) -> int:
        """Apply time-based decay to all habits. Call periodically (every 60s).

        Returns number of habits that decayed.
        """
        now = time.time()
        if now - self._last_decay < 55.0:
            return 0

        self._last_decay = now
        count = 0
        with self._lock:
            for habit in self._habits.values():
                if habit.strength < 0.05:
                    continue
                idle = habit.idle_seconds
                if idle > 300:  # Only decay after 5 min idle
                    old = habit.strength
                    habit.decay(idle)
                    if abs(old - habit.strength) > 0.001:
                        count += 1
                        self._dirty = True
        return count

    # ── Narrator reflection helpers ──────────────────────────────────

    def get_problematic_habits(self, min_fires: int = 15) -> List[Habit]:
        """Find habits that fire often but have poor outcomes.
        The narrator uses this for periodic reflection.
        """
        with self._lock:
            return [
                h for h in self._habits.values()
                if h.times_fired >= min_fires
                and h.avg_recent_outcome < 0.1
                and h.strength >= 0.3
                and not h.is_bad
            ]

    def flag_bad_habit(self, habit_id: str) -> None:
        """Narrator flags a habit as problematic."""
        with self._lock:
            h = self._habits.get(habit_id)
            if h:
                h.is_bad = True
                h.awareness = max(h.awareness, 0.6)
                self._dirty = True

    def create_override(self, bad_habit_id: str, new_response: str) -> Optional[Habit]:
        """Create an override habit that replaces a bad one.

        Weakens the old habit and creates a new conscious one with the
        same trigger but a different response.
        """
        with self._lock:
            old = self._habits.get(bad_habit_id)
            if not old:
                return None

            # Weaken the bad habit
            old.strength *= 0.5
            old.is_bad = True

            # Create override
            override = Habit(
                id=f"override_{bad_habit_id}",
                trigger_type=old.trigger_type,
                trigger_features=dict(old.trigger_features),
                response=new_response,
                strength=0.15,  # Starts weak — needs conscious effort
                awareness=1.0,  # Fully conscious
                stack_group=old.stack_group,
                source="narrator_override",
                formed_at=time.time(),
            )
            self._habits[override.id] = override
            self._dirty = True
            return override

    # ── Stats ────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Summary statistics for dashboard/diagnostics."""
        with self._lock:
            habits = list(self._habits.values())
            return {
                "total": len(habits),
                "active": sum(1 for h in habits if h.strength >= 0.05),
                "automatic": sum(1 for h in habits if h.strength >= 0.5),
                "practiced": sum(1 for h in habits if 0.2 <= h.strength < 0.5),
                "conscious": sum(1 for h in habits if 0.05 <= h.strength < 0.2),
                "extinct": sum(1 for h in habits if h.strength < 0.05),
                "bad_flagged": sum(1 for h in habits if h.is_bad),
                "seeded": sum(1 for h in habits if h.source == "seeded"),
                "organic": sum(1 for h in habits if h.source == "organic"),
                "overrides": sum(1 for h in habits if h.source == "narrator_override"),
                "total_fires": sum(h.times_fired for h in habits),
            }

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> None:
        """Load habits from disk, or seed if first time."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for hd in data.get("habits", []):
                    try:
                        h = Habit.from_dict(hd)
                        self._habits[h.id] = h
                    except Exception as e:
                        print(f"[HabitStore] Skip bad habit entry: {e}")
                print(f"[HabitStore] Loaded {len(self._habits)} habits from {self._path}")
            except Exception as e:
                print(f"[HabitStore] Load error: {e} — seeding fresh")
                self._seed()
        else:
            print(f"[HabitStore] No habits file — seeding initial habits")
            self._seed()

        # Always merge seeds — picks up new seed habits and restores
        # minimum strength for existing ones without losing fire history
        self._merge_seeds()

    def _seed(self) -> None:
        """Create seed habits on first run."""
        for h in _make_seed_habits():
            self._habits[h.id] = h
        self._dirty = True
        self.save()
        print(f"[HabitStore] Seeded {len(self._habits)} habits")

    def _merge_seeds(self) -> None:
        """Merge seed habits into existing store.

        - New seeds get added (she learns a new reflex on upgrade)
        - Existing seeds get their strength restored to at least 40%
          of the seed value (innate reflexes don't fully atrophy)
        - Fire history, outcomes, awareness are PRESERVED (her experience matters)
        """
        seeds = {h.id: h for h in _make_seed_habits()}
        added = 0
        restored = 0

        for seed_id, seed_habit in seeds.items():
            if seed_id not in self._habits:
                # New seed — she was born with this reflex, just didn't have it yet
                self._habits[seed_id] = seed_habit
                added += 1
                self._dirty = True
            else:
                # Existing seed — restore minimum strength
                existing = self._habits[seed_id]
                min_strength = seed_habit.strength * 0.4  # 40% floor
                if existing.strength < min_strength:
                    existing.strength = min_strength
                    restored += 1
                    self._dirty = True

        if added or restored:
            print(f"[HabitStore] Seed merge: {added} new, {restored} restored")
            self.save(force=True)

    def save(self, force: bool = False) -> bool:
        """Save habits to disk if dirty (or forced).

        Returns True if saved.
        """
        if not self._dirty and not force:
            return False

        now = time.time()
        # Rate limit saves to every 30s unless forced
        if not force and (now - self._last_save) < 30.0:
            return False

        with self._lock:
            data = {
                "version": 1,
                "saved_at": now,
                "habit_count": len(self._habits),
                "habits": [h.to_dict() for h in self._habits.values()],
            }

        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._last_save = now
            self._dirty = False
            return True
        except Exception as e:
            print(f"[HabitStore] Save error: {e}")
            return False

    # ── String representation ────────────────────────────────────────

    def __repr__(self) -> str:
        s = self.stats()
        return (f"HabitStore({s['active']} active, {s['automatic']} automatic, "
                f"{s['bad_flagged']} bad, {s['total_fires']} total fires)")
