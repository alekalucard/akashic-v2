# pattern_observer.py — Pattern Observation Infrastructure
# ═══════════════════════════════════════════════════════════════════════════════
# INFRA: This is foundational infrastructure, not app-level functionality.
#
# The PatternObserver watches fairy behavior and automatically generates
# reflections when it detects interesting patterns:
#   - Repeated actions with different outcomes
#   - Unexpected results (delta between expected and actual)
#   - Emotional shifts during processing
#   - Clustering of similar events
#
# Biological analog: The anterior cingulate cortex - monitors for errors,
# conflicts, and surprising outcomes, then signals for attention/learning.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Tuple
from collections import deque, defaultdict

from .reflection_pool import ReflectionPool, Reflection, get_reflection_pool


@dataclass
class Observation:
    """A single observation of fairy behavior."""
    fairy_name: str
    action: str
    input_summary: str = ""
    output_summary: str = ""
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    success: bool = True
    duration_ms: float = 0.0
    affect_before: Optional[Dict[str, Any]] = None
    affect_after: Optional[Dict[str, Any]] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    @property
    def signature(self) -> str:
        """Generate a signature for deduplication."""
        h = hashlib.sha256()
        h.update(self.fairy_name.encode())
        h.update(self.action.encode())
        h.update(self.input_summary[:100].encode())
        return h.hexdigest()[:16]
    
    @property
    def has_delta(self) -> bool:
        """Check if there's a meaningful delta between expected and actual."""
        if not self.expected_outcome or not self.actual_outcome:
            return False
        return self.expected_outcome != self.actual_outcome
    
    @property
    def affect_shift(self) -> Optional[Dict[str, float]]:
        """Calculate affect shift if before/after available."""
        if not self.affect_before or not self.affect_after:
            return None
        
        shift = {}
        for key in ["valence", "arousal"]:
            before = self.affect_before.get(key, 0.0)
            after = self.affect_after.get(key, 0.0)
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                shift[key] = after - before
        
        return shift if shift else None


class PatternObserver:
    """
    Observes fairy behavior and generates reflections on interesting patterns.
    
    Core detection mechanisms:
    1. Delta detection: Expected != Actual
    2. Repetition detection: Same action with varied outcomes
    3. Affect shift detection: Significant emotional changes
    4. Failure clustering: Multiple failures in sequence
    5. Success streaks: Multiple successes worth celebrating
    """
    
    # Detection thresholds
    AFFECT_SHIFT_THRESHOLD = 0.2       # Min shift to trigger reflection
    FAILURE_CLUSTER_SIZE = 3           # Failures before pattern reflection
    SUCCESS_STREAK_SIZE = 5            # Successes before celebration reflection
    REPETITION_WINDOW = 20             # Observations to consider for repetition
    
    def __init__(
        self,
        reflection_pool: Optional[ReflectionPool] = None,
        auto_reflect: bool = True,
    ):
        self._pool = reflection_pool or get_reflection_pool()
        self._auto_reflect = auto_reflect
        self._lock = threading.RLock()
        
        # Observation history
        self._history: deque = deque(maxlen=500)
        
        # Per-fairy tracking
        self._fairy_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._fairy_action_outcomes: Dict[str, Dict[str, List[bool]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Pattern counters
        self._failure_streaks: Dict[str, int] = defaultdict(int)
        self._success_streaks: Dict[str, int] = defaultdict(int)
        
        # Recent reflections (for deduplication)
        self._recent_reflection_sigs: deque = deque(maxlen=50)
    
    def observe(
        self,
        fairy_name: str,
        action: str,
        *,
        input_summary: str = "",
        output_summary: str = "",
        expected_outcome: Optional[str] = None,
        actual_outcome: Optional[str] = None,
        success: bool = True,
        duration_ms: float = 0.0,
        affect_before: Optional[Dict[str, Any]] = None,
        affect_after: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Reflection]:
        """
        Record an observation and potentially generate reflections.
        
        Returns any reflections that were generated.
        """
        obs = Observation(
            fairy_name=fairy_name,
            action=action,
            input_summary=input_summary,
            output_summary=output_summary,
            expected_outcome=expected_outcome,
            actual_outcome=actual_outcome,
            success=success,
            duration_ms=duration_ms,
            affect_before=affect_before,
            affect_after=affect_after,
            context=context or {},
        )
        
        reflections = []
        
        with self._lock:
            # Store observation
            self._history.append(obs)
            self._fairy_history[fairy_name].append(obs)
            self._fairy_action_outcomes[fairy_name][action].append(success)
            
            # Update streaks
            if success:
                self._failure_streaks[fairy_name] = 0
                self._success_streaks[fairy_name] += 1
            else:
                self._success_streaks[fairy_name] = 0
                self._failure_streaks[fairy_name] += 1
            
            if self._auto_reflect:
                # Check for patterns that warrant reflection
                reflections.extend(self._check_delta_pattern(obs))
                reflections.extend(self._check_affect_shift(obs))
                reflections.extend(self._check_failure_cluster(obs))
                reflections.extend(self._check_success_streak(obs))
                reflections.extend(self._check_outcome_variance(obs))
        
        return reflections
    
    def _check_delta_pattern(self, obs: Observation) -> List[Reflection]:
        """Generate reflection if there's a significant delta."""
        if not obs.has_delta:
            return []
        
        sig = f"delta:{obs.signature}"
        if sig in self._recent_reflection_sigs:
            return []
        
        self._recent_reflection_sigs.append(sig)
        
        r = self._pool.reflect(
            source_fairy=obs.fairy_name,
            observation=f"Action '{obs.action}' produced unexpected result",
            source_action=obs.action,
            source_context=obs.context,
            expected=obs.expected_outcome,
            actual=obs.actual_outcome,
            hypothesis=f"The action '{obs.action}' may need adjustment for this input type",
            affect=obs.affect_after or {"valence": -0.1, "arousal": 0.3, "resonance": ["surprise"]},
            tags=["delta", "unexpected", obs.action],
        )
        
        return [r]
    
    def _check_affect_shift(self, obs: Observation) -> List[Reflection]:
        """Generate reflection on significant affect shifts."""
        shift = obs.affect_shift
        if not shift:
            return []
        
        valence_shift = abs(shift.get("valence", 0.0))
        arousal_shift = abs(shift.get("arousal", 0.0))
        
        if valence_shift < self.AFFECT_SHIFT_THRESHOLD and arousal_shift < self.AFFECT_SHIFT_THRESHOLD:
            return []
        
        sig = f"affect:{obs.fairy_name}:{int(time.time() / 60)}"  # One per minute per fairy
        if sig in self._recent_reflection_sigs:
            return []
        
        self._recent_reflection_sigs.append(sig)
        
        direction = "positive" if shift.get("valence", 0) > 0 else "negative"
        intensity = "significant" if max(valence_shift, arousal_shift) > 0.4 else "notable"
        
        r = self._pool.reflect(
            source_fairy=obs.fairy_name,
            observation=f"Experienced {intensity} {direction} affect shift during '{obs.action}'",
            source_action=obs.action,
            source_context={**obs.context, "affect_shift": shift},
            hypothesis=f"This action type influences emotional state in a {direction} direction",
            affect={
                "valence": shift.get("valence", 0),
                "arousal": shift.get("arousal", 0),
                "resonance": ["affect_shift", direction],
            },
            tags=["affect", "shift", direction],
        )
        
        return [r]
    
    def _check_failure_cluster(self, obs: Observation) -> List[Reflection]:
        """Generate reflection on failure clusters."""
        if obs.success:
            return []
        
        streak = self._failure_streaks[obs.fairy_name]
        if streak < self.FAILURE_CLUSTER_SIZE:
            return []
        
        # Only reflect once per cluster
        if streak > self.FAILURE_CLUSTER_SIZE:
            return []
        
        sig = f"failcluster:{obs.fairy_name}:{int(time.time() / 300)}"  # One per 5 min
        if sig in self._recent_reflection_sigs:
            return []
        
        self._recent_reflection_sigs.append(sig)
        
        # Get recent failures for context
        recent = list(self._fairy_history[obs.fairy_name])[-self.FAILURE_CLUSTER_SIZE:]
        failed_actions = [o.action for o in recent if not o.success]
        
        r = self._pool.reflect(
            source_fairy=obs.fairy_name,
            observation=f"Experienced {streak} consecutive failures",
            source_action=obs.action,
            source_context={
                "streak": streak,
                "failed_actions": failed_actions,
            },
            hypothesis="There may be a systematic issue or environmental factor causing repeated failures",
            affect={"valence": -0.3, "arousal": 0.4, "resonance": ["concern", "pattern"]},
            tags=["failure", "cluster", "attention_needed"],
        )
        
        return [r]
    
    def _check_success_streak(self, obs: Observation) -> List[Reflection]:
        """Generate reflection on success streaks (celebration/reinforcement)."""
        if not obs.success:
            return []
        
        streak = self._success_streaks[obs.fairy_name]
        if streak < self.SUCCESS_STREAK_SIZE:
            return []
        
        # Only reflect at milestones
        if streak not in [self.SUCCESS_STREAK_SIZE, 10, 25, 50, 100]:
            return []
        
        sig = f"successstreak:{obs.fairy_name}:{streak}"
        if sig in self._recent_reflection_sigs:
            return []
        
        self._recent_reflection_sigs.append(sig)
        
        r = self._pool.reflect(
            source_fairy=obs.fairy_name,
            observation=f"Achieved {streak} consecutive successes!",
            source_action=obs.action,
            source_context={"streak": streak},
            hypothesis="Current approach is working well - worth reinforcing",
            affect={"valence": 0.5, "arousal": 0.3, "resonance": ["celebration", "reinforcement"]},
            tags=["success", "streak", "celebration"],
        )
        
        return [r]
    
    def _check_outcome_variance(self, obs: Observation) -> List[Reflection]:
        """Generate reflection if same action has highly variable outcomes."""
        outcomes = self._fairy_action_outcomes[obs.fairy_name][obs.action]
        
        if len(outcomes) < 10:
            return []
        
        # Check recent variance
        recent = outcomes[-20:]
        success_rate = sum(recent) / len(recent)
        
        # High variance = success rate between 30-70%
        if not (0.3 < success_rate < 0.7):
            return []
        
        sig = f"variance:{obs.fairy_name}:{obs.action}:{int(time.time() / 600)}"  # One per 10 min
        if sig in self._recent_reflection_sigs:
            return []
        
        self._recent_reflection_sigs.append(sig)
        
        r = self._pool.reflect(
            source_fairy=obs.fairy_name,
            observation=f"Action '{obs.action}' has highly variable outcomes ({success_rate*100:.0f}% success)",
            source_action=obs.action,
            source_context={
                "success_rate": success_rate,
                "sample_size": len(recent),
            },
            hypothesis="This action may be sensitive to conditions not yet identified",
            affect={"valence": 0.0, "arousal": 0.2, "resonance": ["uncertainty", "investigation"]},
            tags=["variance", "investigation", obs.action],
        )
        
        return [r]
    
    def get_fairy_stats(self, fairy_name: str) -> Dict[str, Any]:
        """Get observation statistics for a fairy."""
        with self._lock:
            history = list(self._fairy_history.get(fairy_name, []))
            
            if not history:
                return {"fairy_name": fairy_name, "observations": 0}
            
            successes = sum(1 for o in history if o.success)
            
            # Action breakdown
            action_stats = {}
            for action, outcomes in self._fairy_action_outcomes[fairy_name].items():
                if outcomes:
                    action_stats[action] = {
                        "count": len(outcomes),
                        "success_rate": sum(outcomes) / len(outcomes),
                    }
            
            return {
                "fairy_name": fairy_name,
                "observations": len(history),
                "success_rate": successes / len(history) if history else 0,
                "current_success_streak": self._success_streaks.get(fairy_name, 0),
                "current_failure_streak": self._failure_streaks.get(fairy_name, 0),
                "actions": action_stats,
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall observation statistics."""
        with self._lock:
            total = len(self._history)
            successes = sum(1 for o in self._history if o.success)
            
            # Fairy breakdown
            fairy_counts = {}
            for fname, hist in self._fairy_history.items():
                fairy_counts[fname] = len(hist)
            
            return {
                "total_observations": total,
                "success_rate": successes / total if total else 0,
                "fairies_observed": len(fairy_counts),
                "observations_per_fairy": fairy_counts,
            }


# ═══════════════════════════════════════════════════════════════════════════════
# Global observer instance
# ═══════════════════════════════════════════════════════════════════════════════

_global_observer: Optional[PatternObserver] = None
_observer_lock = threading.Lock()

def get_pattern_observer() -> PatternObserver:
    """Get or create the global pattern observer."""
    global _global_observer
    with _observer_lock:
        if _global_observer is None:
            _global_observer = PatternObserver()
        return _global_observer

def set_pattern_observer(observer: PatternObserver):
    """Set a custom global pattern observer."""
    global _global_observer
    with _observer_lock:
        _global_observer = observer
