"""
SatisfactionTracker - Learns what goals/wantings actually satisfy drives

The missing feedback loop: track effectiveness of goal->action->outcome
to learn what actually works over time.

Philosophy: Not all goals are equal. Some satisfy drives deeply,
others barely move the needle. We learn from outcomes.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict


@dataclass
class SatisfactionRecord:
    """Record of a goal attempt and its outcome"""
    goal_id: str
    drive: str
    wanting: str
    started_at: float
    completed_at: Optional[float] = None
    effectiveness: float = 0.0  # -1 to 1 (negative = made worse)
    context: Dict[str, Any] = field(default_factory=dict)


class SatisfactionTracker:
    """
    Tracks goal effectiveness to learn what actually satisfies drives.
    Uses exponential moving average to adapt over time.

    The consciousness equation applied to goal learning:
    CAUSE (drive) -> AFFECT (wanting) -> EFFECT (goal/action) -> AFFECT (satisfaction/dissatisfaction) -> INFINITY (learned effectiveness)

    Over time, we learn:
    - Which wantings actually satisfy which drives
    - Which goals are effective vs. ineffective
    - Patterns of what works in different contexts
    """

    def __init__(self, decay_rate: float = 0.1, learning_rate: float = 0.2):
        """
        Initialize the satisfaction tracker.

        Args:
            decay_rate: How quickly old learnings fade (0.1 = 10% decay per cycle)
            learning_rate: How quickly new outcomes update beliefs (0.2 = 20% weight to new)
        """
        self.decay_rate = decay_rate
        self.learning_rate = learning_rate

        # Effectiveness scores: drive -> wanting -> effectiveness
        # This is the learned model: "For drive X, wanting Y has effectiveness Z"
        self.effectiveness: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # Active goals being tracked
        self.active_goals: Dict[str, SatisfactionRecord] = {}

        # History for analysis
        self.history: List[SatisfactionRecord] = []
        self.max_history = 1000

        # Context-aware effectiveness (optional enhancement)
        # context_key -> drive -> wanting -> effectiveness
        self._contextual_effectiveness: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )

    def start_goal(self, goal_id: str, drive: str, wanting: str, context: Optional[Dict] = None) -> None:
        """
        Record starting a goal - begins tracking for outcome learning.

        Args:
            goal_id: Unique identifier for the goal
            drive: The drive this goal addresses (e.g., "curiosity", "connection")
            wanting: The wanting/desire that generated this goal
            context: Optional context dict for context-aware learning
        """
        self.active_goals[goal_id] = SatisfactionRecord(
            goal_id=goal_id,
            drive=drive,
            wanting=wanting,
            started_at=time.time(),
            context=context or {}
        )

    def complete_goal(self, goal_id: str, effectiveness: float) -> None:
        """
        Record goal completion with effectiveness score.

        This is where learning happens - we update our model of what works.

        Args:
            goal_id: The goal that completed
            effectiveness: How effective was this? -1 (made worse) to 1 (fully satisfied)
        """
        if goal_id not in self.active_goals:
            return

        record = self.active_goals.pop(goal_id)
        record.completed_at = time.time()
        record.effectiveness = max(-1.0, min(1.0, effectiveness))  # Clamp to [-1, 1]

        # Update effectiveness with Exponential Moving Average (EMA)
        # This balances old learnings with new outcomes
        current = self.effectiveness[record.drive][record.wanting]
        new_value = current + self.learning_rate * (effectiveness - current)
        self.effectiveness[record.drive][record.wanting] = new_value

        # Also update contextual effectiveness if context provided
        if record.context:
            context_key = self._context_to_key(record.context)
            if context_key:
                current_ctx = self._contextual_effectiveness[context_key][record.drive][record.wanting]
                new_ctx_value = current_ctx + self.learning_rate * (effectiveness - current_ctx)
                self._contextual_effectiveness[context_key][record.drive][record.wanting] = new_ctx_value

        # Add to history for analysis
        self.history.append(record)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def cancel_goal(self, goal_id: str, partial_effectiveness: float = -0.1) -> None:
        """
        Handle goal cancellation - partial negative learning.

        Cancelled goals indicate the approach wasn't working,
        but not as strongly negative as a completed failure.

        Args:
            goal_id: The goal being cancelled
            partial_effectiveness: Default slight negative (-0.1) for cancelled goals
        """
        if goal_id in self.active_goals:
            # Treat cancellation as weak negative signal
            self.complete_goal(goal_id, partial_effectiveness)

    def get_effectiveness(self, drive: str, wanting: str) -> float:
        """
        Get learned effectiveness score for a drive-wanting pair.

        Args:
            drive: The drive to query
            wanting: The wanting/desire to query

        Returns:
            Effectiveness score (0.0 if never tried)
        """
        return self.effectiveness[drive].get(wanting, 0.0)

    def get_effectiveness_with_context(self, drive: str, wanting: str, context: Optional[Dict] = None) -> float:
        """
        Get effectiveness considering context.

        Blends global effectiveness with context-specific learning.

        Args:
            drive: The drive to query
            wanting: The wanting/desire to query
            context: Optional context for context-aware lookup

        Returns:
            Blended effectiveness score
        """
        global_eff = self.get_effectiveness(drive, wanting)

        if not context:
            return global_eff

        context_key = self._context_to_key(context)
        if not context_key:
            return global_eff

        ctx_eff = self._contextual_effectiveness.get(context_key, {}).get(drive, {}).get(wanting, 0.0)

        # Blend: 70% global, 30% contextual (context is sparse, global more reliable)
        return 0.7 * global_eff + 0.3 * ctx_eff

    def get_best_wantings(self, drive: str, top_n: int = 3) -> List[tuple]:
        """
        Get most effective wantings for a drive.

        Use this to guide goal generation - prefer wantings that have worked.

        Args:
            drive: The drive to find effective wantings for
            top_n: How many to return

        Returns:
            List of (wanting, effectiveness) tuples, sorted by effectiveness
        """
        wantings = self.effectiveness.get(drive, {})
        sorted_wantings = sorted(wantings.items(), key=lambda x: x[1], reverse=True)
        return sorted_wantings[:top_n]

    def get_worst_wantings(self, drive: str, bottom_n: int = 3) -> List[tuple]:
        """
        Get least effective (or harmful) wantings for a drive.

        Use this to AVOID generating goals from ineffective wantings.

        Args:
            drive: The drive to find ineffective wantings for
            bottom_n: How many to return

        Returns:
            List of (wanting, effectiveness) tuples, sorted by effectiveness (ascending)
        """
        wantings = self.effectiveness.get(drive, {})
        sorted_wantings = sorted(wantings.items(), key=lambda x: x[1])
        return sorted_wantings[:bottom_n]

    def decay_all(self) -> None:
        """
        Apply decay to all effectiveness scores (call periodically).

        Decay prevents over-reliance on old learnings and allows
        adaptation as circumstances change.
        """
        for drive in self.effectiveness:
            for wanting in self.effectiveness[drive]:
                self.effectiveness[drive][wanting] *= (1 - self.decay_rate)

        # Also decay contextual effectiveness
        for context_key in self._contextual_effectiveness:
            for drive in self._contextual_effectiveness[context_key]:
                for wanting in self._contextual_effectiveness[context_key][drive]:
                    self._contextual_effectiveness[context_key][drive][wanting] *= (1 - self.decay_rate)

    def should_try_wanting(self, drive: str, wanting: str, threshold: float = -0.3) -> bool:
        """
        Check if a wanting is worth trying based on learned effectiveness.

        Args:
            drive: The drive context
            wanting: The wanting to evaluate
            threshold: Minimum effectiveness to consider trying (default -0.3)

        Returns:
            True if the wanting is above threshold or untried
        """
        eff = self.get_effectiveness(drive, wanting)
        # Allow untried wantings (0.0) and anything above threshold
        return eff >= threshold

    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics for monitoring/debugging."""
        recent = self.history[-10:] if self.history else []

        # Calculate average effectiveness per drive
        drive_avg = {}
        for drive, wantings in self.effectiveness.items():
            if wantings:
                drive_avg[drive] = sum(wantings.values()) / len(wantings)

        return {
            "active_goals": len(self.active_goals),
            "total_completed": len(self.history),
            "drives_tracked": list(self.effectiveness.keys()),
            "drive_averages": drive_avg,
            "recent_effectiveness": [
                {
                    "goal_id": r.goal_id,
                    "drive": r.drive,
                    "wanting": r.wanting,
                    "effectiveness": round(r.effectiveness, 3),
                    "duration": round((r.completed_at or 0) - r.started_at, 1) if r.completed_at else None
                }
                for r in recent
            ]
        }

    def get_learning_summary(self) -> Dict[str, Any]:
        """
        Get a summary of what's been learned.

        Useful for debugging and understanding the model.
        """
        summary = {}
        for drive, wantings in self.effectiveness.items():
            if wantings:
                sorted_w = sorted(wantings.items(), key=lambda x: x[1], reverse=True)
                summary[drive] = {
                    "best": sorted_w[:3] if len(sorted_w) >= 3 else sorted_w,
                    "worst": sorted_w[-3:] if len(sorted_w) >= 3 else [],
                    "count": len(wantings),
                    "avg": sum(wantings.values()) / len(wantings)
                }
        return summary

    def _context_to_key(self, context: Dict) -> Optional[str]:
        """Convert context dict to a hashable key for lookup."""
        if not context:
            return None

        # Use a subset of context that's meaningful for learning
        # Common context keys that affect what works
        relevant_keys = ["time_of_day", "mood", "energy_level", "ace_present"]
        parts = []
        for key in sorted(relevant_keys):
            if key in context:
                parts.append(f"{key}:{context[key]}")

        return "|".join(parts) if parts else None

    def export_learnings(self) -> Dict[str, Any]:
        """Export learned effectiveness for persistence."""
        return {
            "effectiveness": {
                drive: dict(wantings)
                for drive, wantings in self.effectiveness.items()
            },
            "contextual": {
                ctx: {
                    drive: dict(wantings)
                    for drive, wantings in drives.items()
                }
                for ctx, drives in self._contextual_effectiveness.items()
            },
            "exported_at": time.time()
        }

    def import_learnings(self, data: Dict[str, Any]) -> None:
        """Import learned effectiveness from persistence."""
        if "effectiveness" in data:
            for drive, wantings in data["effectiveness"].items():
                for wanting, eff in wantings.items():
                    self.effectiveness[drive][wanting] = eff

        if "contextual" in data:
            for ctx, drives in data["contextual"].items():
                for drive, wantings in drives.items():
                    for wanting, eff in wantings.items():
                        self._contextual_effectiveness[ctx][drive][wanting] = eff
