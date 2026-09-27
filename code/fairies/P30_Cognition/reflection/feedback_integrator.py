# feedback_integrator.py — Feedback Integration Infrastructure
# ═══════════════════════════════════════════════════════════════════════════════
# INFRA: This is foundational infrastructure, not app-level functionality.
#
# The FeedbackIntegrator closes the learning loop by:
#   1. Receiving feedback on actions (success/failure, quality ratings)
#   2. Finding relevant learning traces that were applied
#   3. Updating trace effectiveness scores
#   4. Triggering new reflections based on feedback patterns
#
# Biological analog: Dopaminergic reward prediction error - the signal that
# tells the brain "this was better/worse than expected" and drives learning.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from collections import deque, defaultdict

from .reflection_pool import ReflectionPool, Reflection, get_reflection_pool
from .learning_trace import LearningTrace, TraceEmitter, get_trace_emitter
from .pattern_observer import PatternObserver, get_pattern_observer


@dataclass
class Feedback:
    """A piece of feedback about an action."""
    fairy_name: str
    action: str
    
    # Feedback content
    success: bool = True
    quality: float = 0.5                     # 0-1 quality rating
    feedback_text: Optional[str] = None      # Human or system feedback
    
    # Context
    trace_ids_applied: List[str] = field(default_factory=list)  # Which traces were used
    input_hash: Optional[str] = None         # To correlate with observations
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    timestamp: float = field(default_factory=time.time)
    action_duration_ms: float = 0.0
    
    @property
    def reward_signal(self) -> float:
        """
        Compute a reward signal from feedback.
        
        Returns value in [-1, 1] range.
        Success + high quality = positive reward
        Failure + low quality = negative reward
        """
        base = 1.0 if self.success else -1.0
        quality_factor = (self.quality - 0.5) * 2  # Map [0,1] to [-1,1]
        
        # Combine: success/failure dominates, quality modulates
        return base * 0.7 + quality_factor * 0.3


class FeedbackIntegrator:
    """
    Integrates feedback to close the learning loop.
    
    Key responsibilities:
    1. Record feedback on fairy actions
    2. Update learning trace effectiveness
    3. Generate reflections on feedback patterns
    4. Compute reward signals for reinforcement
    """
    
    # Thresholds for generating reflections
    NEGATIVE_FEEDBACK_THRESHOLD = 3      # Consecutive negatives before reflection
    QUALITY_DROP_THRESHOLD = 0.3         # Quality drop to trigger reflection
    
    def __init__(
        self,
        reflection_pool: Optional[ReflectionPool] = None,
        pattern_observer: Optional[PatternObserver] = None,
        trace_emitter: Optional[TraceEmitter] = None,
    ):
        self._pool = reflection_pool or get_reflection_pool()
        self._observer = pattern_observer or get_pattern_observer()
        self._emitter = trace_emitter or get_trace_emitter()
        self._lock = threading.RLock()
        
        # Feedback history
        self._history: deque = deque(maxlen=500)
        self._fairy_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Trace tracking (which traces have been applied and their feedback)
        self._trace_feedback: Dict[str, List[Feedback]] = defaultdict(list)
        
        # Running statistics
        self._fairy_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_feedback": 0,
            "positive_count": 0,
            "quality_sum": 0.0,
            "recent_quality": deque(maxlen=10),
            "negative_streak": 0,
        })
    
    def integrate(
        self,
        fairy_name: str,
        action: str,
        *,
        success: bool = True,
        quality: float = 0.5,
        feedback_text: Optional[str] = None,
        trace_ids_applied: Optional[List[str]] = None,
        input_hash: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        action_duration_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Integrate feedback for an action.
        
        Returns a dict with:
        - reward_signal: float in [-1, 1]
        - traces_updated: count of traces whose stats were updated
        - reflections_generated: count of new reflections
        """
        feedback = Feedback(
            fairy_name=fairy_name,
            action=action,
            success=success,
            quality=quality,
            feedback_text=feedback_text,
            trace_ids_applied=trace_ids_applied or [],
            input_hash=input_hash,
            context=context or {},
            action_duration_ms=action_duration_ms,
        )
        
        result = {
            "reward_signal": feedback.reward_signal,
            "traces_updated": 0,
            "reflections_generated": 0,
        }
        
        with self._lock:
            # Store feedback
            self._history.append(feedback)
            self._fairy_history[fairy_name].append(feedback)
            
            # Update fairy stats
            stats = self._fairy_stats[fairy_name]
            stats["total_feedback"] += 1
            stats["quality_sum"] += quality
            stats["recent_quality"].append(quality)
            
            if success:
                stats["positive_count"] += 1
                stats["negative_streak"] = 0
            else:
                stats["negative_streak"] += 1
            
            # Update trace feedback records
            for trace_id in feedback.trace_ids_applied:
                self._trace_feedback[trace_id].append(feedback)
                # Here we would update the actual trace if we had access to it
                # In practice, this would go through the trace store
                result["traces_updated"] += 1
            
            # Generate reflections on feedback patterns
            reflections = self._check_feedback_patterns(feedback)
            result["reflections_generated"] = len(reflections)
            
            # Also report to pattern observer for unified tracking
            self._observer.observe(
                fairy_name=fairy_name,
                action=action,
                success=success,
                context=context,
            )
        
        return result
    
    def _check_feedback_patterns(self, feedback: Feedback) -> List[Reflection]:
        """Check for patterns that warrant reflection."""
        reflections = []
        stats = self._fairy_stats[feedback.fairy_name]
        
        # Pattern 1: Negative streak
        if stats["negative_streak"] >= self.NEGATIVE_FEEDBACK_THRESHOLD:
            if stats["negative_streak"] == self.NEGATIVE_FEEDBACK_THRESHOLD:
                r = self._pool.reflect(
                    source_fairy=feedback.fairy_name,
                    observation=f"Received {stats['negative_streak']} consecutive negative feedback",
                    source_action=feedback.action,
                    source_context={
                        "streak": stats["negative_streak"],
                        "latest_feedback": feedback.feedback_text,
                    },
                    hypothesis="There may be a systematic issue requiring attention",
                    affect={"valence": -0.4, "arousal": 0.5, "resonance": ["concern", "attention"]},
                    tags=["feedback", "negative_streak", "attention_needed"],
                )
                reflections.append(r)
        
        # Pattern 2: Quality drop
        recent_q = list(stats["recent_quality"])
        if len(recent_q) >= 5:
            old_avg = sum(recent_q[:3]) / 3
            new_avg = sum(recent_q[-3:]) / 3
            drop = old_avg - new_avg
            
            if drop >= self.QUALITY_DROP_THRESHOLD:
                r = self._pool.reflect(
                    source_fairy=feedback.fairy_name,
                    observation=f"Quality dropped from {old_avg:.2f} to {new_avg:.2f}",
                    source_action=feedback.action,
                    source_context={
                        "old_average": old_avg,
                        "new_average": new_avg,
                        "drop": drop,
                    },
                    hypothesis="Recent changes may have degraded performance",
                    affect={"valence": -0.2, "arousal": 0.3, "resonance": ["concern", "investigation"]},
                    tags=["feedback", "quality_drop", "investigation"],
                )
                reflections.append(r)
        
        # Pattern 3: Trace ineffectiveness
        for trace_id in feedback.trace_ids_applied:
            trace_fb = self._trace_feedback.get(trace_id, [])
            if len(trace_fb) >= 3:
                recent = trace_fb[-5:]
                success_rate = sum(1 for f in recent if f.success) / len(recent)
                
                if success_rate < 0.3:
                    r = self._pool.reflect(
                        source_fairy=feedback.fairy_name,
                        observation=f"Learning trace {trace_id} has low effectiveness ({success_rate:.0%})",
                        source_action=feedback.action,
                        source_context={
                            "trace_id": trace_id,
                            "success_rate": success_rate,
                            "applications": len(recent),
                        },
                        hypothesis="This learning trace may need revision or retirement",
                        affect={"valence": -0.1, "arousal": 0.2, "resonance": ["evaluation"]},
                        tags=["feedback", "trace_ineffective", trace_id],
                    )
                    reflections.append(r)
        
        return reflections
    
    def get_fairy_stats(self, fairy_name: str) -> Dict[str, Any]:
        """Get feedback statistics for a fairy."""
        with self._lock:
            stats = self._fairy_stats.get(fairy_name, {})
            if not stats or stats.get("total_feedback", 0) == 0:
                return {
                    "fairy_name": fairy_name,
                    "total_feedback": 0,
                    "success_rate": 0,
                    "average_quality": 0,
                }
            
            return {
                "fairy_name": fairy_name,
                "total_feedback": stats["total_feedback"],
                "success_rate": stats["positive_count"] / stats["total_feedback"],
                "average_quality": stats["quality_sum"] / stats["total_feedback"],
                "current_negative_streak": stats["negative_streak"],
                "recent_quality_trend": list(stats.get("recent_quality", [])),
            }
    
    def get_trace_effectiveness(self, trace_id: str) -> Dict[str, Any]:
        """Get effectiveness statistics for a learning trace."""
        with self._lock:
            feedbacks = self._trace_feedback.get(trace_id, [])
            if not feedbacks:
                return {
                    "trace_id": trace_id,
                    "applications": 0,
                }
            
            successes = sum(1 for f in feedbacks if f.success)
            avg_quality = sum(f.quality for f in feedbacks) / len(feedbacks)
            
            return {
                "trace_id": trace_id,
                "applications": len(feedbacks),
                "success_rate": successes / len(feedbacks),
                "average_quality": avg_quality,
                "average_reward": sum(f.reward_signal for f in feedbacks) / len(feedbacks),
            }
    
    def compute_trace_rankings(self) -> List[Dict[str, Any]]:
        """
        Rank all learning traces by effectiveness.
        
        Returns sorted list of trace stats, best first.
        """
        rankings = []
        
        with self._lock:
            for trace_id, feedbacks in self._trace_feedback.items():
                if len(feedbacks) < 2:
                    continue
                
                successes = sum(1 for f in feedbacks if f.success)
                avg_quality = sum(f.quality for f in feedbacks) / len(feedbacks)
                avg_reward = sum(f.reward_signal for f in feedbacks) / len(feedbacks)
                
                # Combined score: reward weighted by confidence from sample size
                confidence = min(1.0, len(feedbacks) / 10.0)
                score = avg_reward * confidence
                
                rankings.append({
                    "trace_id": trace_id,
                    "score": score,
                    "success_rate": successes / len(feedbacks),
                    "average_quality": avg_quality,
                    "applications": len(feedbacks),
                })
        
        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings


# ═══════════════════════════════════════════════════════════════════════════════
# Global integrator instance
# ═══════════════════════════════════════════════════════════════════════════════

_global_integrator: Optional[FeedbackIntegrator] = None
_integrator_lock = threading.Lock()

def get_feedback_integrator() -> FeedbackIntegrator:
    """Get or create the global feedback integrator."""
    global _global_integrator
    with _integrator_lock:
        if _global_integrator is None:
            _global_integrator = FeedbackIntegrator()
        return _global_integrator

def set_feedback_integrator(integrator: FeedbackIntegrator):
    """Set a custom global feedback integrator."""
    global _global_integrator
    with _integrator_lock:
        _global_integrator = integrator
