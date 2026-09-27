"""
Strategy Collapse - Universal Decision Function
=================================================

The quantum collapse of possibility → action.

Combines ProbabilityOracleFairy's cognitive rails with
SatisfactionTracker's learned effectiveness into a single
reusable decision primitive.

Formula:
    final_score[i] = oracle_probability[i] * (1 + sat_weight * learned_effectiveness[i])

Used by:
    - Sourpatches' _should_auto_invoke_tool() (thought → action)
    - AutopilotFairy._on_goal_nudge() (goal → best action)
    - SpellChain._select_successors() (spell → next spell)
    - Any decision point that needs probabilistic + learned scoring

((Cause + Affect) > Effect > Affect > infinity)
"""

import time
import random
from typing import Dict, List, Optional, Any


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY COLLAPSE
# ═══════════════════════════════════════════════════════════════════════════════

class StrategyCollapse:
    """
    Universal collapse: candidates → scored → best → execute → learn.

    Usage:
        collapse = get_collapse()
        result = collapse.evaluate(
            candidates=[
                {"id": "see_world", "prior": 0.3, "description": "Look at the screen"},
                {"id": "search_memory", "prior": 0.2, "description": "Search for context"},
            ],
            drive="curiosity",
            wanting="understand what is happening",
            notes=["thought chain about Ace's activity"],
            temperature=1.0,
            satisfaction_weight=0.3,
        )
        # result = {"best": "see_world", "confidence": 0.62, "all_scores": [...], ...}

    After execution:
        collapse.record_outcome("see_world", drive="curiosity",
                                wanting="understand what is happening", effectiveness=0.7)
    """

    def __init__(self):
        self._oracle = None        # Lazy-loaded ProbabilityOracleFairy
        self._tracker = None       # Lazy-loaded SatisfactionTracker
        self._postal = None        # Lazy-loaded postal hub
        self._stats = {
            "evaluations": 0,
            "outcomes_recorded": 0,
            "oracle_hits": 0,
            "oracle_misses": 0,
            "tracker_hits": 0,
            "tracker_misses": 0,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # LAZY INFRASTRUCTURE LOOKUP
    # ─────────────────────────────────────────────────────────────────────────

    def _get_oracle(self):
        """Lazy-load Oracle singleton."""
        if self._oracle is not None:
            return self._oracle
        try:
            from fairies.P30_Cognition.ProbabilityOracleFairy import get_probability_oracle_fairy
            self._oracle = get_probability_oracle_fairy()
            return self._oracle
        except Exception:
            pass
        return None

    def _get_tracker(self):
        """Lazy-load SatisfactionTracker from GoalSchedulerFairy."""
        if self._tracker is not None:
            return self._tracker
        try:
            # Try GoalSchedulerFairy singleton
            from fairies.P30_Cognition.GoalSchedulerFairy import get_goal_scheduler_fairy
            gsf = get_goal_scheduler_fairy()
            if gsf and hasattr(gsf, 'satisfaction_tracker'):
                self._tracker = gsf.satisfaction_tracker
                return self._tracker
        except Exception:
            pass
        try:
            # Fallback: look through FairyProfileRegistry weakrefs
            from fairies.P00_Autonomic.fairy_profile import get_fairy_registry
            registry = get_fairy_registry()
            if registry:
                profile = registry.get_profile("GoalSchedulerFairy")
                if profile and hasattr(profile, 'instance_ref'):
                    ref = profile.instance_ref
                    instance = ref() if callable(ref) else ref
                    if instance and hasattr(instance, 'satisfaction_tracker'):
                        self._tracker = instance.satisfaction_tracker
                        return self._tracker
        except Exception:
            pass
        return None

    def _get_postal(self):
        """Lazy-load postal hub for publishing."""
        if self._postal is not None:
            return self._postal
        try:
            from infrastructure.postal_system import PostalHub
            self._postal = PostalHub.get_hub()
            return self._postal
        except Exception:
            pass
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # EVALUATE — THE CORE COLLAPSE
    # ─────────────────────────────────────────────────────────────────────────

    def _get_mood(self) -> float:
        """Sour's felt valence (PAD pleasure) for the acoustic medium-tuning. Her somatic engine is live."""
        try:
            from fairies.P20_Somatic.somatic_engine.somatic_engine_fairy import get_somatic_engine
            eng = get_somatic_engine()
            pad = getattr(getattr(eng, "_somatic_state", None), "PAD", None)
            if pad is not None and len(pad) > 0:
                return float(pad[0] or 0.0)
        except Exception:
            pass
        return 0.0

    def evaluate(
        self,
        candidates: List[Dict[str, Any]],
        drive: str = "",
        wanting: str = "",
        notes: Optional[List[str]] = None,
        temperature: float = 1.0,
        satisfaction_weight: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Evaluate candidates and collapse to the best one.

        Args:
            candidates: List of {"id": str, "prior": float, "description": str, ...}
            drive: The drive context (e.g. "curiosity", "connection")
            wanting: What the system wants (natural language)
            notes: Context notes for the Oracle
            temperature: Oracle temperature (higher = more exploration)
            satisfaction_weight: How much to weight learned effectiveness (0-1)

        Returns:
            {
                "best": str,           # ID of best candidate
                "confidence": float,    # Confidence in the choice (0-1)
                "all_scores": [...],    # Per-candidate final scores
                "oracle_used": bool,    # Whether Oracle was available
                "tracker_used": bool,   # Whether SatisfactionTracker was available
                "diagnostics": {...},   # Oracle diagnostics if available
            }
        """
        self._stats["evaluations"] += 1

        if not candidates:
            return {"best": "", "confidence": 0.0, "all_scores": [],
                    "oracle_used": False, "tracker_used": False, "diagnostics": {}}

        if len(candidates) == 1:
            return {"best": candidates[0]["id"], "confidence": 1.0,
                    "all_scores": [1.0], "oracle_used": False, "tracker_used": False,
                    "diagnostics": {}}

        n = len(candidates)
        notes = notes or []

        # ═══ Step 1: Get Oracle probabilities (or use priors as fallback) ═══
        oracle = self._get_oracle()
        oracle_used = False
        diagnostics = {}

        if oracle and hasattr(oracle, '_intent_assess'):
            try:
                oracle_options = [
                    {"id": c["id"], "prior": c.get("prior", 1.0 / n)}
                    for c in candidates
                ]
                oracle_result = oracle._intent_assess({
                    "options": oracle_options,
                    "notes": notes + [f"Drive: {drive}", f"Wanting: {wanting}"] if drive else notes,
                    "temperature": temperature,
                })

                if oracle_result.get("ok"):
                    oracle_probs = oracle_result["probabilities"]
                    diagnostics = oracle_result.get("diagnostics", {})
                    oracle_used = True
                    self._stats["oracle_hits"] += 1
                else:
                    oracle_probs = self._normalize_priors(candidates)
                    self._stats["oracle_misses"] += 1
            except Exception as e:
                oracle_probs = self._normalize_priors(candidates)
                self._stats["oracle_misses"] += 1
                diagnostics["oracle_error"] = str(e)
        else:
            oracle_probs = self._normalize_priors(candidates)
            self._stats["oracle_misses"] += 1

        # ═══ Step 2: Get learned effectiveness from SatisfactionTracker ═══
        tracker = self._get_tracker()
        tracker_used = False
        effectiveness = [0.0] * n

        if tracker and drive:
            try:
                for i, c in enumerate(candidates):
                    eff = tracker.get_effectiveness(drive, c["id"])
                    effectiveness[i] = eff
                tracker_used = True
                self._stats["tracker_hits"] += 1
            except Exception:
                self._stats["tracker_misses"] += 1
        else:
            self._stats["tracker_misses"] += 1

        # ACOUSTIC COLLAPSE (flag AKASHIC_SOUR_ACOUSTIC, Ace 06-30): wave-field selection (interference +
        # Sour's felt-medium + harmonic + habit-fatigue + do-otherwise), fed by oracle_probs(pull) +
        # effectiveness(felt) + her chemistry-valence(mood). Same return shape; falls through on error.
        import os as _os
        if _os.environ.get("AKASHIC_SOUR_ACOUSTIC", "").strip().lower() in ("1", "true", "yes", "on"):
            try:
                from fairies.P30_Cognition.cognition.sour_acoustic_collapse import acoustic_collapse
                _ar = acoustic_collapse(candidates, oracle_probs, effectiveness, self._get_mood())
                self._publish_result(candidates, _ar["all_scores"], _ar["best"], _ar["confidence"],
                                     drive, wanting, oracle_used, tracker_used, diagnostics)
                return {"best": _ar["best"], "confidence": _ar["confidence"], "all_scores": _ar["all_scores"],
                        "oracle_used": oracle_used, "tracker_used": tracker_used,
                        "diagnostics": {**diagnostics, "acoustic": True},
                        "oracle_probs": oracle_probs, "effectiveness": effectiveness}
            except Exception as _ace:
                diagnostics["acoustic_error"] = str(_ace)

        # ═══ Step 3: Blend Oracle + Satisfaction ═══
        # final_score[i] = oracle_prob[i] * (1 + sat_weight * effectiveness[i])
        final_scores = []
        for i in range(n):
            score = oracle_probs[i] * (1.0 + satisfaction_weight * effectiveness[i])
            final_scores.append(max(0.0, score))

        # Normalize final scores to sum to 1
        total = sum(final_scores) or 1.0
        final_scores = [s / total for s in final_scores]

        # ═══ Step 4: Pick the best ═══
        best_idx = final_scores.index(max(final_scores))
        best_id = candidates[best_idx]["id"]
        confidence = final_scores[best_idx]

        # ═══ Step 5: Publish for observability ═══
        self._publish_result(candidates, final_scores, best_id, confidence,
                            drive, wanting, oracle_used, tracker_used, diagnostics)

        return {
            "best": best_id,
            "confidence": confidence,
            "all_scores": final_scores,
            "oracle_used": oracle_used,
            "tracker_used": tracker_used,
            "diagnostics": diagnostics,
            "oracle_probs": oracle_probs,
            "effectiveness": effectiveness,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # RECORD OUTCOME — LEARNING FEEDBACK
    # ─────────────────────────────────────────────────────────────────────────

    def record_outcome(
        self,
        action_id: str,
        drive: str,
        wanting: str,
        effectiveness: float,
        context: Optional[Dict] = None,
    ) -> bool:
        """
        Record the outcome of a collapsed action for learning.

        Args:
            action_id: Which action was taken (the "best" from evaluate)
            drive: The drive context
            wanting: What was wanted
            effectiveness: How well it worked (-1 to 1)
            context: Optional additional context

        Returns:
            True if recorded successfully
        """
        tracker = self._get_tracker()
        if not tracker:
            return False

        try:
            # Use action_id as goal_id for tracker
            goal_id = f"collapse_{action_id}_{int(time.time())}"
            tracker.start_goal(goal_id, drive, action_id, context)
            tracker.complete_goal(goal_id, effectiveness)
            self._stats["outcomes_recorded"] += 1
            import os as _os2
            if _os2.environ.get("AKASHIC_SOUR_ACOUSTIC", "").strip().lower() in ("1", "true", "yes", "on"):
                try:
                    from fairies.P30_Cognition.cognition.sour_acoustic_collapse import record_outcome_felt
                    record_outcome_felt(effectiveness)
                except Exception:
                    pass

            # Publish feedback for behavior tree
            postal = self._get_postal()
            if postal:
                try:
                    postal.publish("strategy.collapse.feedback", {
                        "action": action_id,
                        "drive": drive,
                        "wanting": wanting,
                        "effectiveness": effectiveness,
                        "ts": time.time(),
                    })
                except Exception:
                    pass

            return True
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # START TRACKING — Begin tracking a goal for satisfaction learning
    # ─────────────────────────────────────────────────────────────────────────

    def start_tracking(
        self,
        goal_id: str,
        drive: str,
        wanting: str,
        context: Optional[Dict] = None,
    ) -> bool:
        """Start tracking a goal attempt for later outcome recording."""
        tracker = self._get_tracker()
        if not tracker:
            return False
        try:
            tracker.start_goal(goal_id, drive, wanting, context)
            return True
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_priors(self, candidates: List[Dict]) -> List[float]:
        """Normalize candidate priors to sum to 1 (fallback when Oracle unavailable)."""
        priors = [c.get("prior", 1.0 / len(candidates)) for c in candidates]
        total = sum(priors) or 1.0
        return [p / total for p in priors]

    def _publish_result(self, candidates, scores, best_id, confidence,
                       drive, wanting, oracle_used, tracker_used, diagnostics):
        """Publish collapse result for observability."""
        postal = self._get_postal()
        if not postal:
            return
        try:
            postal.publish("strategy.collapse.result", {
                "best": best_id,
                "confidence": round(confidence, 4),
                "candidates": [
                    {"id": c["id"], "score": round(s, 4), "description": c.get("description", "")}
                    for c, s in zip(candidates, scores)
                ],
                "drive": drive,
                "wanting": wanting[:100] if wanting else "",
                "oracle_used": oracle_used,
                "tracker_used": tracker_used,
                "ts": time.time(),
            })
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """Get collapse usage statistics."""
        return dict(self._stats)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[StrategyCollapse] = None


def get_collapse() -> StrategyCollapse:
    """Get or create the StrategyCollapse singleton."""
    global _instance
    if _instance is None:
        _instance = StrategyCollapse()
    return _instance
