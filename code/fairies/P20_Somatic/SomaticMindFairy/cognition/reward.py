"""
Reward System - Dr. Zero architecture for finding the learning edge.

The key insight: maximum reward comes from PARTIAL success.
Too easy = no learning (low reward)
Too hard = no success (zero reward)
Partial success = learning is happening (maximum reward)
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from .executor import ExecutionResult, SuccessLevel


def goal_reward(k_successes: int, n_attempts: int) -> float:
    """
    Calculate reward that peaks at partial success.

    The "learning edge" is where some attempts succeed and some fail.
    This is where real learning happens - goals are challenging but achievable.

    Args:
        k_successes: Number of successful attempts
        n_attempts: Total attempts made

    Returns:
        Reward value 0.0 to 1.0, maximized when k is around n/2

    Examples:
        goal_reward(0, 5) = 0.0     # Too hard, no learning
        goal_reward(5, 5) = 0.1     # Too easy, boring
        goal_reward(2, 5) = 0.75    # Sweet spot!
        goal_reward(3, 5) = 0.5     # Also good
    """
    if n_attempts == 0:
        return 0.0

    if k_successes == 0:
        return 0.0  # Too hard - nothing learned

    if k_successes == n_attempts:
        return 0.1  # Too easy - small reward, but not zero

    # Learning edge: reward partial success
    # Formula: (n - k) / (n - 1)
    # Maximum when k = 1 (barely succeeding)
    # Decreases as k approaches n (getting too easy)
    return (n_attempts - k_successes) / (n_attempts - 1)


def calibrate_difficulty(
    current_difficulty: float,
    recent_results: List[ExecutionResult],
    target_success_rate: float = 0.5
) -> float:
    """
    Adjust difficulty to maintain the learning edge.

    If we're succeeding too much, increase difficulty.
    If we're failing too much, decrease difficulty.

    Args:
        current_difficulty: Current difficulty setting (0.0-1.0)
        recent_results: Recent execution results
        target_success_rate: Where we want to be (default 50%)

    Returns:
        Adjusted difficulty (0.0-1.0)
    """
    if not recent_results:
        return current_difficulty

    # Calculate actual success rate
    success_counts = {"full": 0, "partial": 0, "none": 0}
    for result in recent_results:
        success_counts[result.success.value] += 1

    n = len(recent_results)
    # Full = 1.0, Partial = 0.5, None = 0.0
    actual_rate = (
        success_counts["full"] * 1.0 +
        success_counts["partial"] * 0.5
    ) / n

    # How far from target?
    error = actual_rate - target_success_rate

    # Adjust difficulty
    # If succeeding too much (error > 0), increase difficulty
    # If failing too much (error < 0), decrease difficulty
    adjustment = error * 0.2  # 20% correction rate

    new_difficulty = current_difficulty + adjustment

    # Clamp to valid range
    return max(0.1, min(0.9, new_difficulty))


@dataclass
class RewardSignal:
    """A complete reward signal for learning.

    FIX 2026-04-27 (Nous + Ace, Pattern D): extended with substrate-energy
    fields. The original task-completion reward (raw + difficulty_bonus +
    efficiency_bonus → total_reward) is preserved for back-compat. The new
    substrate fields (compression_progress + paradox_resolution +
    gravity_stability_delta → substrate_total_reward) report whether the
    cycle ACTUALLY changed the substrate, not just whether hops completed.

    learning_edge_status taxonomy expanded from 3 to 5 states. The original
    3-state {too_easy, optimal, too_hard} was based on hop-success only.
    The new 5-state {fully-mastered, task-success-no-substrate-progress,
    true-learning-edge, task-fail-substrate-progress, overload} requires
    BOTH task and substrate dimensions to agree.

    Mapping for back-compat consumers:
      old "too_easy" -> "fully-mastered"
      old "optimal"  -> "true-learning-edge" (when substrate also progressed)
                     -> "task-success-no-substrate-progress" (when it didn't)
      old "too_hard" -> "overload" (when substrate also flat)
                     -> "task-fail-substrate-progress" (when substrate
                                                         compressed despite
                                                         hop-fail; rare but
                                                         meaningful — the
                                                         system learned even
                                                         though the task
                                                         didn't complete)
    """
    raw_reward: float           # Base goal_reward value
    difficulty_bonus: float     # Bonus for attempting harder goals
    efficiency_bonus: float     # Bonus for fast completion
    total_reward: float         # Combined reward (TASK-completion based)

    # Substrate-energy components (Pattern D, 2026-04-27)
    compression_progress: float = 0.0   # Cortex compression delta (positive = more compressed)
    paradox_resolution: float = 0.0     # AER residue delta (positive = paradox energy resolved)
    gravity_stability_delta: float = 0.0  # τ-variance delta (positive = well stabilizing)
    substrate_total_reward: float = 0.0 # Combined substrate signal

    # Calibration feedback
    recommended_difficulty: float = 0.5
    learning_edge_status: str = "optimal"  # 5-state taxonomy (see class docstring)


def calculate_reward(
    result: ExecutionResult,
    difficulty: float,
    recent_history: Optional[List[ExecutionResult]] = None,
    substrate_delta: Optional[Dict[str, float]] = None,
) -> RewardSignal:
    """
    Calculate complete reward signal from execution result.

    Args:
        result: The execution result to evaluate
        difficulty: The difficulty level of the goal
        recent_history: Recent results for calibration
        substrate_delta: Optional dict with substrate-energy deltas
                         (compression_progress, paradox_resolution,
                          gravity_stability_delta). When None or all-zero,
                         reward falls back to pure task-completion (back-compat).

    Returns:
        RewardSignal with reward components and feedback

    FIX 2026-04-27 (Nous + Ace, Pattern D): substrate_delta added.
    When provided, the cycle is rated on BOTH task-completion AND
    substrate-energy progress. learning_edge_status uses the 5-state
    taxonomy. When substrate_delta is None (legacy callers), behavior
    is identical to pre-2026-04-27.
    """
    # Map success level to success count
    success_map = {
        SuccessLevel.FULL: result.hops_completed,     # All succeeded
        SuccessLevel.PARTIAL: result.hops_completed,  # Some succeeded
        SuccessLevel.NONE: 0,                         # None succeeded
    }

    k_successes = success_map[result.success]
    n_attempts = len(result.plan.hop_chain)

    # Base reward from goal_reward formula
    raw_reward = goal_reward(k_successes, n_attempts)

    # Difficulty bonus: harder goals get bonus
    # But only if we made progress
    if k_successes > 0:
        difficulty_bonus = difficulty * 0.3  # Up to 30% bonus
    else:
        difficulty_bonus = 0.0

    # Efficiency bonus: faster than expected
    expected_duration = result.plan.total_estimated_duration
    if expected_duration > 0 and result.total_duration > 0:
        time_ratio = result.total_duration / expected_duration
        if time_ratio < 1.0:
            efficiency_bonus = (1.0 - time_ratio) * 0.2  # Up to 20% bonus
        else:
            efficiency_bonus = 0.0
    else:
        efficiency_bonus = 0.0

    # Total reward (TASK-COMPLETION based, back-compat)
    total_reward = raw_reward + difficulty_bonus + efficiency_bonus

    # ─── Substrate-energy reward (Pattern D, 2026-04-27) ────────────────────
    # Schmidhuber controller-WM closure: reward should reflect whether the
    # substrate ACTUALLY compressed/resolved/stabilized, not just whether
    # the task hops completed. When substrate_delta is None, this stays at
    # zero and behavior is identical to pre-Pattern-D.
    sd = substrate_delta or {}
    compression_progress = float(sd.get("compression_progress", 0.0))
    paradox_resolution = float(sd.get("paradox_resolution", 0.0))
    gravity_stability_delta = float(sd.get("gravity_stability_delta", 0.0))

    # Weighted combination — compression weighted highest (Schmidhuber's
    # primary signal), paradox second, gravity third. Bounded to [-1, 1]
    # so substrate-reward is comparable in magnitude to task-reward.
    substrate_total = max(-1.0, min(1.0,
        0.5 * compression_progress +
        0.3 * paradox_resolution +
        0.2 * gravity_stability_delta
    ))

    # ─── 5-state learning_edge_status taxonomy ──────────────────────────────
    # Combines task-completion (FULL/PARTIAL/NONE) with substrate-progress
    # (positive/zero). When substrate_delta is None (legacy), substrate is
    # treated as zero and we fall back to a 3-state mapping.
    substrate_progressed = substrate_total > 0.05  # threshold for noise
    has_substrate_signal = substrate_delta is not None

    if has_substrate_signal:
        if result.success == SuccessLevel.NONE:
            status = "task-fail-substrate-progress" if substrate_progressed else "overload"
        elif result.success == SuccessLevel.FULL:
            status = "true-learning-edge" if substrate_progressed else "fully-mastered"
        else:  # PARTIAL
            status = "true-learning-edge" if substrate_progressed else "task-success-no-substrate-progress"
    else:
        # Legacy 3-state (no substrate signal available)
        if result.success == SuccessLevel.NONE:
            status = "too_hard"
        elif result.success == SuccessLevel.FULL:
            status = "too_easy"
        else:
            status = "optimal"

    # Calibrate difficulty for next time
    history = recent_history or []
    history_with_current = history + [result]
    recommended = calibrate_difficulty(
        difficulty,
        history_with_current[-10:],  # Use last 10
    )

    return RewardSignal(
        raw_reward=raw_reward,
        difficulty_bonus=difficulty_bonus,
        efficiency_bonus=efficiency_bonus,
        total_reward=total_reward,
        compression_progress=compression_progress,
        paradox_resolution=paradox_resolution,
        gravity_stability_delta=gravity_stability_delta,
        substrate_total_reward=substrate_total,
        recommended_difficulty=recommended,
        learning_edge_status=status,
    )


class RewardTracker:
    """
    Tracks rewards over time for learning optimization.

    Maintains running statistics and adapts the reward system.

    FIX 2026-04-27 (Nous + Ace, Pattern D): substrate-energy tracking added.
    The original task-reward tracking is preserved unchanged. The new
    substrate-reward + true_learning_rate fields report whether cycles
    are ACTUALLY compressing the substrate. learning_efficiency
    (3-state-based, back-compat) and true_learning_rate (5-state-based,
    Pattern D) are tracked separately so consumers reading the old field
    keep working.
    """

    # 5-state taxonomy for Pattern D status counting
    _PATTERN_D_STATES = (
        "fully-mastered",
        "task-success-no-substrate-progress",
        "true-learning-edge",
        "task-fail-substrate-progress",
        "overload",
    )
    # 3-state legacy taxonomy
    _LEGACY_STATES = ("too_easy", "optimal", "too_hard")

    def __init__(self, window_size: int = 50):
        self._history: List[RewardSignal] = []
        self._window_size = window_size
        self._cumulative_reward: float = 0.0
        self._cumulative_substrate_reward: float = 0.0  # Pattern D
        self._current_difficulty: float = 0.5

    def record(self, signal: RewardSignal):
        """Record a reward signal."""
        self._history.append(signal)
        self._cumulative_reward += signal.total_reward
        self._cumulative_substrate_reward += signal.substrate_total_reward  # Pattern D

        # Adapt difficulty
        self._current_difficulty = signal.recommended_difficulty

        # Trim old history
        if len(self._history) > self._window_size:
            self._history = self._history[-self._window_size:]

    @property
    def current_difficulty(self) -> float:
        """Get current recommended difficulty."""
        return self._current_difficulty

    @property
    def average_reward(self) -> float:
        """Average TASK reward over window."""
        if not self._history:
            return 0.0
        return sum(s.total_reward for s in self._history) / len(self._history)

    @property
    def average_substrate_reward(self) -> float:
        """Average SUBSTRATE reward over window (Pattern D, 2026-04-27)."""
        if not self._history:
            return 0.0
        return sum(s.substrate_total_reward for s in self._history) / len(self._history)

    @property
    def learning_efficiency(self) -> float:
        """
        Legacy 3-state learning efficiency (back-compat).

        Counts both "optimal" (legacy) and "true-learning-edge" (Pattern D)
        as the at-learning-edge state, since true-learning-edge is the
        substrate-aware refinement of optimal.
        """
        if not self._history:
            return 0.0

        optimal_count = sum(
            1 for s in self._history
            if s.learning_edge_status in ("optimal", "true-learning-edge")
        )
        return optimal_count / len(self._history)

    @property
    def true_learning_rate(self) -> float:
        """
        Pattern D substrate-aware learning rate (2026-04-27).

        Proportion of cycles where status == "true-learning-edge" — i.e.,
        where the substrate ACTUALLY compressed/resolved/stabilized AND the
        task was at the partial-success learning edge. This is the real
        Schmidhuber sweet spot: controller behavior at substrate's frontier.

        Distinct from learning_efficiency: this excludes legacy "optimal"
        cycles that didn't have substrate signal data, AND excludes
        "task-success-no-substrate-progress" cycles (which legacy would
        have counted as optimal but Pattern D recognizes as the
        foreign-currency cycle — task succeeded without substrate change).
        """
        if not self._history:
            return 0.0
        true_count = sum(
            1 for s in self._history
            if s.learning_edge_status == "true-learning-edge"
        )
        return true_count / len(self._history)

    @property
    def foreign_currency_rate(self) -> float:
        """
        Pattern D diagnostic (2026-04-27).

        Proportion of cycles where task succeeded but substrate didn't
        progress. High values indicate Dr Zero is "succeeding at things
        that don't matter" — completing hops without compressing the
        substrate. This is the symptom Pattern D was designed to expose.
        """
        if not self._history:
            return 0.0
        fc_count = sum(
            1 for s in self._history
            if s.learning_edge_status == "task-success-no-substrate-progress"
        )
        return fc_count / len(self._history)

    def status(self) -> Dict[str, Any]:
        """Get tracker status."""
        if not self._history:
            return {
                "samples": 0,
                "difficulty": self._current_difficulty,
                "avg_reward": 0.0,
                "avg_substrate_reward": 0.0,
                "learning_efficiency": 0.0,
                "true_learning_rate": 0.0,
                "foreign_currency_rate": 0.0,
                "cumulative_reward": 0.0,
                "cumulative_substrate_reward": 0.0,
            }

        # Pattern D 5-state distribution + legacy 3-state distribution.
        # Both reported so consumers reading either format keep working.
        status_counts = {s: 0 for s in self._PATTERN_D_STATES}
        legacy_counts = {s: 0 for s in self._LEGACY_STATES}
        for signal in self._history:
            s = signal.learning_edge_status
            if s in status_counts:
                status_counts[s] += 1
            if s in legacy_counts:
                legacy_counts[s] += 1

        return {
            "samples": len(self._history),
            "difficulty": self._current_difficulty,
            "avg_reward": self.average_reward,
            "avg_substrate_reward": self.average_substrate_reward,
            "learning_efficiency": self.learning_efficiency,
            "true_learning_rate": self.true_learning_rate,
            "foreign_currency_rate": self.foreign_currency_rate,
            "cumulative_reward": self._cumulative_reward,
            "cumulative_substrate_reward": self._cumulative_substrate_reward,
            "status_distribution": status_counts,         # Pattern D 5-state
            "legacy_status_distribution": legacy_counts,  # back-compat 3-state
        }
