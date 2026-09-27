"""
CircadianClock - Self-learning timing system for the brain.

The circadian clock manages the brain's internal rhythms:
- When to consolidate memories
- When to run cognition cycles
- When to check for new stimuli
- When the system should rest vs be active

It learns from system behavior patterns and adapts its timing
to optimize for the learning edge (Dr. Zero architecture).

Key principles:
1. Start with Fibonacci base rhythms (natural feel)
2. Track actual system performance at different times
3. Adjust rhythms based on what works best
4. Respect resource constraints (don't overwork the system)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from collections import deque
import time

from .fibonacci_rhythm import (
    fib_decay,
    fib_intervals,
    should_act_at_count,
    next_fib_interval,
    golden_weights,
    PHI,
)


@dataclass
class RhythmPattern:
    """A learned timing pattern for a specific activity."""
    name: str
    base_interval: float  # Base time between activities (seconds)
    current_interval: float  # Adapted interval
    success_rate: float = 0.5  # How often this timing works well
    sample_count: int = 0  # How many samples we've learned from
    last_triggered: float = 0.0  # Timestamp of last trigger

    # Learning parameters
    adaptation_rate: float = 0.1  # How fast to adapt (0-1)
    min_interval: float = 1.0  # Never go faster than this
    max_interval: float = 300.0  # Never go slower than this

    def should_trigger(self, now: float = None) -> bool:
        """Check if this rhythm should trigger now."""
        if now is None:
            now = time.time()
        elapsed = now - self.last_triggered
        return elapsed >= self.current_interval

    def trigger(self, now: float = None):
        """Mark this rhythm as triggered."""
        if now is None:
            now = time.time()
        self.last_triggered = now

    def record_outcome(self, success: bool, efficiency: float = 1.0):
        """
        Record the outcome of this rhythm's activity.

        Args:
            success: Did the activity succeed?
            efficiency: How efficient was it (0-1, 1 = optimal)
        """
        self.sample_count += 1

        # Update success rate with exponential moving average
        self.success_rate = (
            (1 - self.adaptation_rate) * self.success_rate +
            self.adaptation_rate * (1.0 if success else 0.0)
        )

        # Adapt interval based on efficiency
        if efficiency > 0.8 and self.success_rate > 0.7:
            # Doing well - could go slightly faster
            self.current_interval *= 0.95
        elif efficiency < 0.3 or self.success_rate < 0.4:
            # Struggling - slow down
            self.current_interval *= 1.1

        # Clamp to bounds
        self.current_interval = max(self.min_interval,
                                    min(self.max_interval, self.current_interval))

    def time_until_next(self, now: float = None) -> float:
        """Get seconds until next trigger."""
        if now is None:
            now = time.time()
        elapsed = now - self.last_triggered
        remaining = self.current_interval - elapsed
        return max(0.0, remaining)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_interval": self.base_interval,
            "current_interval": self.current_interval,
            "success_rate": self.success_rate,
            "sample_count": self.sample_count,
            "adaptation": f"{(self.current_interval / self.base_interval - 1) * 100:.1f}%",
        }


@dataclass
class ClockState:
    """Current state of the circadian clock."""
    tick_count: int = 0
    cycle_count: int = 0
    total_runtime: float = 0.0
    active_since: float = field(default_factory=time.time)

    # Learning metrics
    total_successes: int = 0
    total_failures: int = 0

    @property
    def success_ratio(self) -> float:
        total = self.total_successes + self.total_failures
        return self.total_successes / total if total > 0 else 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick_count": self.tick_count,
            "cycle_count": self.cycle_count,
            "runtime_seconds": self.total_runtime,
            "success_ratio": self.success_ratio,
        }


class CircadianClock:
    """
    Self-learning timing system for the unconscious mind.

    Manages multiple rhythm patterns, each governing a different
    type of brain activity. Learns from outcomes to optimize timing.

    Usage:
        clock = CircadianClock()

        # Register rhythms for different activities
        clock.register_rhythm("cognition", base_interval=5.0)
        clock.register_rhythm("memory_consolidation", base_interval=30.0)
        clock.register_rhythm("stimulus_check", base_interval=1.0)

        # In your main loop
        while running:
            triggers = clock.tick()
            for rhythm_name in triggers:
                if rhythm_name == "cognition":
                    result = run_cognition_cycle()
                    clock.record_outcome(rhythm_name, result.success, result.efficiency)
    """

    def __init__(self, tick_interval: float = 1.0):
        """
        Initialize the circadian clock.

        Args:
            tick_interval: Base tick rate in seconds
        """
        self._tick_interval = tick_interval
        self._rhythms: Dict[str, RhythmPattern] = {}
        self._state = ClockState()
        self._callbacks: Dict[str, List[Callable]] = {}
        self._running = False
        self._last_tick = time.time()

        # History for pattern learning
        self._trigger_history: deque = deque(maxlen=1000)
        self._outcome_history: deque = deque(maxlen=1000)

    def register_rhythm(
        self,
        name: str,
        base_interval: float,
        min_interval: float = 1.0,
        max_interval: float = 300.0,
        adaptation_rate: float = 0.1,
        callback: Optional[Callable[[], Any]] = None,
    ) -> RhythmPattern:
        """
        Register a new rhythm pattern.

        Args:
            name: Unique name for this rhythm
            base_interval: Starting interval in seconds
            min_interval: Minimum allowed interval
            max_interval: Maximum allowed interval
            adaptation_rate: How fast to adapt (0-1)
            callback: Optional function to call when rhythm triggers

        Returns:
            The created RhythmPattern
        """
        rhythm = RhythmPattern(
            name=name,
            base_interval=base_interval,
            current_interval=base_interval,
            min_interval=min_interval,
            max_interval=max_interval,
            adaptation_rate=adaptation_rate,
            last_triggered=time.time(),
        )
        self._rhythms[name] = rhythm

        if callback:
            self._callbacks.setdefault(name, []).append(callback)

        return rhythm

    def register_callback(self, rhythm_name: str, callback: Callable[[], Any]):
        """Register a callback for when a rhythm triggers."""
        self._callbacks.setdefault(rhythm_name, []).append(callback)

    def tick(self, now: float = None) -> List[str]:
        """
        Advance the clock by one tick.

        Checks all rhythms and returns names of those that should trigger.
        Also fires registered callbacks.

        Args:
            now: Current timestamp (uses time.time() if not provided)

        Returns:
            List of rhythm names that triggered
        """
        if now is None:
            now = time.time()

        self._state.tick_count += 1
        self._state.total_runtime = now - self._state.active_since

        # Check if this tick count is Fibonacci (special beat)
        is_fib_beat = should_act_at_count(self._state.tick_count)

        triggered = []

        for name, rhythm in self._rhythms.items():
            if rhythm.should_trigger(now):
                rhythm.trigger(now)
                triggered.append(name)

                # Record in history
                self._trigger_history.append({
                    "rhythm": name,
                    "timestamp": now,
                    "tick": self._state.tick_count,
                    "is_fib_beat": is_fib_beat,
                })

                # Fire callbacks
                for callback in self._callbacks.get(name, []):
                    try:
                        callback()
                    except Exception as e:
                        # Log but don't crash
                        pass

        # On Fibonacci beats, potentially trigger special consolidation
        if is_fib_beat and self._state.tick_count > 1:
            self._state.cycle_count += 1

        self._last_tick = now
        return triggered

    def record_outcome(
        self,
        rhythm_name: str,
        success: bool,
        efficiency: float = 1.0
    ):
        """
        Record the outcome of a rhythm's triggered activity.

        This is how the clock learns - it adjusts timing based
        on whether activities succeed and how efficient they are.

        Args:
            rhythm_name: Name of the rhythm that was triggered
            success: Did the activity succeed?
            efficiency: How efficient was it (0-1, 1 = optimal)
        """
        if rhythm_name not in self._rhythms:
            return

        rhythm = self._rhythms[rhythm_name]
        rhythm.record_outcome(success, efficiency)

        # Track global stats
        if success:
            self._state.total_successes += 1
        else:
            self._state.total_failures += 1

        # Record in history
        self._outcome_history.append({
            "rhythm": rhythm_name,
            "timestamp": time.time(),
            "success": success,
            "efficiency": efficiency,
            "new_interval": rhythm.current_interval,
        })

    def get_rhythm(self, name: str) -> Optional[RhythmPattern]:
        """Get a rhythm by name."""
        return self._rhythms.get(name)

    def time_until_next(self, rhythm_name: str = None) -> float:
        """
        Get time until next trigger.

        Args:
            rhythm_name: Specific rhythm, or None for any rhythm

        Returns:
            Seconds until next trigger
        """
        now = time.time()

        if rhythm_name:
            rhythm = self._rhythms.get(rhythm_name)
            return rhythm.time_until_next(now) if rhythm else float('inf')

        # Find soonest trigger across all rhythms
        soonest = float('inf')
        for rhythm in self._rhythms.values():
            remaining = rhythm.time_until_next(now)
            soonest = min(soonest, remaining)
        return soonest

    def next_trigger(self) -> Optional[str]:
        """Get name of rhythm that will trigger next."""
        now = time.time()
        soonest_name = None
        soonest_time = float('inf')

        for name, rhythm in self._rhythms.items():
            remaining = rhythm.time_until_next(now)
            if remaining < soonest_time:
                soonest_time = remaining
                soonest_name = name

        return soonest_name

    def status(self) -> Dict[str, Any]:
        """Get full clock status."""
        return {
            "state": self._state.to_dict(),
            "rhythms": {name: r.to_dict() for name, r in self._rhythms.items()},
            "next_trigger": self.next_trigger(),
            "time_until_next": self.time_until_next(),
            "learning": {
                "total_triggers": len(self._trigger_history),
                "total_outcomes": len(self._outcome_history),
                "global_success_rate": self._state.success_ratio,
            },
        }

    def reset(self):
        """Reset clock to initial state."""
        self._state = ClockState()
        for rhythm in self._rhythms.values():
            rhythm.current_interval = rhythm.base_interval
            rhythm.success_rate = 0.5
            rhythm.sample_count = 0
            rhythm.last_triggered = time.time()
        self._trigger_history.clear()
        self._outcome_history.clear()

    # =========================================================================
    # PATTERN ANALYSIS (Self-learning)
    # =========================================================================

    def analyze_patterns(self) -> Dict[str, Any]:
        """
        Analyze historical patterns to find optimal timing.

        Looks at when activities succeeded vs failed and
        what intervals were being used.
        """
        if len(self._outcome_history) < 10:
            return {"status": "insufficient_data", "samples": len(self._outcome_history)}

        # Group outcomes by rhythm
        by_rhythm: Dict[str, List[Dict]] = {}
        for outcome in self._outcome_history:
            rhythm = outcome["rhythm"]
            by_rhythm.setdefault(rhythm, []).append(outcome)

        analysis = {}
        for rhythm_name, outcomes in by_rhythm.items():
            successes = [o for o in outcomes if o["success"]]
            failures = [o for o in outcomes if not o["success"]]

            # Find optimal interval range
            if successes:
                success_intervals = [o["new_interval"] for o in successes]
                avg_success_interval = sum(success_intervals) / len(success_intervals)
            else:
                avg_success_interval = None

            if failures:
                failure_intervals = [o["new_interval"] for o in failures]
                avg_failure_interval = sum(failure_intervals) / len(failure_intervals)
            else:
                avg_failure_interval = None

            analysis[rhythm_name] = {
                "total_samples": len(outcomes),
                "success_rate": len(successes) / len(outcomes),
                "avg_success_interval": avg_success_interval,
                "avg_failure_interval": avg_failure_interval,
                "recommendation": self._recommend_interval(
                    avg_success_interval, avg_failure_interval
                ),
            }

        return analysis

    def _recommend_interval(
        self,
        success_interval: Optional[float],
        failure_interval: Optional[float]
    ) -> str:
        """Generate timing recommendation based on analysis."""
        if success_interval is None and failure_interval is None:
            return "maintain_current"

        if success_interval is not None and failure_interval is None:
            return f"optimal_around_{success_interval:.1f}s"

        if success_interval is None and failure_interval is not None:
            return f"avoid_around_{failure_interval:.1f}s"

        # Both have data
        if success_interval < failure_interval:
            return f"faster_is_better_target_{success_interval:.1f}s"
        else:
            return f"slower_is_better_target_{success_interval:.1f}s"

    def apply_learned_patterns(self):
        """Apply insights from pattern analysis to current rhythms."""
        analysis = self.analyze_patterns()

        if analysis.get("status") == "insufficient_data":
            return

        for rhythm_name, insights in analysis.items():
            rhythm = self._rhythms.get(rhythm_name)
            if not rhythm:
                continue

            avg_success = insights.get("avg_success_interval")
            if avg_success is not None and insights["success_rate"] > 0.6:
                # Gradually move toward successful interval
                target = avg_success
                current = rhythm.current_interval
                # Move 10% toward target
                rhythm.current_interval = current + 0.1 * (target - current)
                rhythm.current_interval = max(rhythm.min_interval,
                                              min(rhythm.max_interval,
                                                  rhythm.current_interval))


def create_default_clock() -> CircadianClock:
    """
    Create a CircadianClock with sensible default rhythms.

    Returns:
        Configured CircadianClock
    """
    clock = CircadianClock(tick_interval=1.0)

    # Core brain rhythms
    clock.register_rhythm(
        "heartbeat",
        base_interval=1.0,
        min_interval=0.5,
        max_interval=5.0,
        adaptation_rate=0.05,  # Slow to change
    )

    clock.register_rhythm(
        "cognition_cycle",
        base_interval=5.0,  # Fibonacci number
        min_interval=2.0,
        max_interval=60.0,
        adaptation_rate=0.1,
    )

    clock.register_rhythm(
        "memory_consolidation",
        base_interval=21.0,  # Fibonacci number
        min_interval=8.0,   # Fibonacci
        max_interval=300.0,
        adaptation_rate=0.15,
    )

    clock.register_rhythm(
        "stimulus_scan",
        base_interval=2.0,
        min_interval=0.5,
        max_interval=10.0,
        adaptation_rate=0.2,  # Quick to adapt
    )

    clock.register_rhythm(
        "self_reflection",
        base_interval=55.0,  # Fibonacci number
        min_interval=21.0,   # Fibonacci
        max_interval=600.0,
        adaptation_rate=0.1,
    )

    return clock
