# AER Metrics - Measurement System for Emotional Algebra
# Purpose: Quantify emotional states using Coherence, Dissonance, Stability, Adaptation
#
# Philosophy: "What gets measured gets managed. Emotions can be tracked
#              without reducing them to mere numbers."
#
# Four Core Metrics:
#   C - Coherence: How well states align (0-1)
#   D - Dissonance: How much clash exists (0-1)
#   S - Stability: Resistance to change over time (0-1)
#   A - Adaptation Rate: Speed of state changes (Hz)
#
# Plus the Ascension Metric Λ from the unified equation

from __future__ import annotations
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

try:
    from fairies.P20_Somatic.chemistry.emotional_algebra import (
        EmotionalInstance, EmotionalState, FrequencyBand,
        EMOTIONAL_STATES, BAND_PROPERTIES, EmotionalOperators
    )
except ImportError:
    # Fallback for testing
    EmotionalInstance = None
    EmotionalState = None
    FrequencyBand = None

ACTOR_NAME = "AERMetrics"
ACTOR_VERSION = "1.0.0"


# ════════════════════════════════════════════════════════════════════════════════
# COHERENCE METRIC (C)
# ════════════════════════════════════════════════════════════════════════════════

class CoherenceCalculator:
    """
    Calculates how well emotional states align with each other.

    Coherence = (sum of aligned vibes) / (total vibes)

    High coherence: States working together harmoniously
    Low coherence: States pulling in different directions

    Factors:
    - Valence alignment (same direction +/- ?)
    - Band proximity (similar frequency ranges?)
    - Intensity balance (not one overwhelming others?)
    - Temporal correlation (changing together?)
    """

    @staticmethod
    def calculate(states: List[EmotionalInstance]) -> float:
        """
        Calculate coherence of a set of emotional states.

        Returns: 0.0 (total incoherence) to 1.0 (perfect alignment)
        """
        if not states or len(states) < 2:
            return 1.0  # Single state is coherent with itself

        total_score = 0.0
        comparisons = 0

        for i, a in enumerate(states):
            for b in states[i+1:]:
                # Valence alignment (0 to 1)
                valence_score = CoherenceCalculator._valence_alignment(a, b)

                # Band proximity (0 to 1)
                band_score = CoherenceCalculator._band_proximity(a, b)

                # Intensity balance (0 to 1)
                intensity_score = CoherenceCalculator._intensity_balance(a, b)

                # Combined score for this pair
                pair_score = (valence_score * 0.5 + band_score * 0.3 + intensity_score * 0.2)
                total_score += pair_score
                comparisons += 1

        return total_score / comparisons if comparisons > 0 else 1.0

    @staticmethod
    def _valence_alignment(a: EmotionalInstance, b: EmotionalInstance) -> float:
        """How well do valences align? Same direction = 1, opposite = 0."""
        v_a = a.weighted_valence
        v_b = b.weighted_valence

        # Both positive or both negative = aligned
        if v_a * v_b > 0:
            return 1.0
        # One neutral = partial alignment
        elif v_a == 0 or v_b == 0:
            return 0.5
        # Opposite signs = misaligned
        else:
            return 0.0

    @staticmethod
    def _band_proximity(a: EmotionalInstance, b: EmotionalInstance) -> float:
        """How close are the frequency bands? Adjacent = 0.8, same = 1.0."""
        bands = list(FrequencyBand) if FrequencyBand else []
        if not bands:
            return 0.5

        try:
            idx_a = bands.index(a.band)
            idx_b = bands.index(b.band)
            distance = abs(idx_a - idx_b)

            # Same band = 1.0, adjacent = 0.8, etc.
            return max(0.0, 1.0 - (distance * 0.15))
        except (ValueError, AttributeError):
            return 0.5

    @staticmethod
    def _intensity_balance(a: EmotionalInstance, b: EmotionalInstance) -> float:
        """Are intensities balanced? Similar = 1.0, one overwhelming = lower."""
        diff = abs(a.intensity - b.intensity)
        # 0 diff = 1.0, 1.0 diff = 0.0
        return 1.0 - diff

    @staticmethod
    def coherence_with_goal(states: List[EmotionalInstance], goal_state: EmotionalInstance) -> float:
        """
        Calculate how coherent current states are with a goal state.
        Useful for measuring progress toward desired emotional outcome.
        """
        if not states:
            return 0.0

        scores = []
        for state in states:
            valence_match = 1.0 if state.valence == goal_state.valence else 0.5 if state.valence == 0 else 0.0
            band_match = CoherenceCalculator._band_proximity(state, goal_state)
            intensity_match = 1.0 - abs(state.intensity - goal_state.intensity)

            scores.append(valence_match * 0.4 + band_match * 0.3 + intensity_match * 0.3)

        return sum(scores) / len(scores)


# ════════════════════════════════════════════════════════════════════════════════
# DISSONANCE METRIC (D)
# ════════════════════════════════════════════════════════════════════════════════

class DissonanceCalculator:
    """
    Calculates how much clash/conflict exists between emotional states.

    Dissonance = 1 - Coherence (basic)

    But also considers:
    - Paradox tension (opposite valences at high intensity)
    - Band conflict (distant bands competing)
    - Unresolved contradictions
    """

    @staticmethod
    def calculate(states: List[EmotionalInstance]) -> float:
        """
        Calculate dissonance of a set of emotional states.

        Returns: 0.0 (harmony) to 1.0 (total conflict)
        """
        if not states or len(states) < 2:
            return 0.0  # Single state has no internal conflict

        # Base dissonance from coherence
        coherence = CoherenceCalculator.calculate(states)
        base_dissonance = 1.0 - coherence

        # Additional paradox tension
        paradox_tension = DissonanceCalculator._paradox_tension(states)

        # Weighted combination
        return min(1.0, base_dissonance * 0.7 + paradox_tension * 0.3)

    @staticmethod
    def _paradox_tension(states: List[EmotionalInstance]) -> float:
        """
        Calculate tension from paradoxical states.

        High tension = opposite valences at high intensities.
        This is where transformation potential lives!
        """
        tension = 0.0
        pairs = 0

        for i, a in enumerate(states):
            for b in states[i+1:]:
                # Opposite valences?
                if a.valence * b.valence < 0:  # One + one -
                    # Both intense = high tension
                    combined_intensity = (a.intensity + b.intensity) / 2
                    tension += combined_intensity
                    pairs += 1

        return tension / pairs if pairs > 0 else 0.0

    @staticmethod
    def identify_conflicts(states: List[EmotionalInstance]) -> List[Tuple[EmotionalInstance, EmotionalInstance, float]]:
        """
        Identify specific conflicting pairs and their tension level.
        Returns list of (state_a, state_b, tension_level)
        """
        conflicts = []

        for i, a in enumerate(states):
            for b in states[i+1:]:
                if a.valence * b.valence < 0:  # Opposite valences
                    tension = (a.intensity + b.intensity) / 2
                    if tension > 0.3:  # Only significant conflicts
                        conflicts.append((a, b, tension))

        return sorted(conflicts, key=lambda x: x[2], reverse=True)


# ════════════════════════════════════════════════════════════════════════════════
# STABILITY METRIC (S)
# ════════════════════════════════════════════════════════════════════════════════

class StabilityCalculator:
    """
    Calculates resistance to change over time.

    Stability = f(Coherence, Dissonance, context, history)

    High stability: States persist, resist perturbation
    Low stability: States fluctuate rapidly, easily changed

    Based on:
    - Current coherence (high C = more stable)
    - Current dissonance (high D = less stable)
    - Historical variance (less change = more stable)
    - Context anchoring (strong context = more stable)
    """

    def __init__(self, history_size: int = 50):
        self.history: deque = deque(maxlen=history_size)
        self._last_coherence: float = 0.5
        self._last_dissonance: float = 0.5

    def update(self, states: List[EmotionalInstance], context: Dict[str, Any] = None):
        """Record current state for stability tracking."""
        coherence = CoherenceCalculator.calculate(states)
        dissonance = DissonanceCalculator.calculate(states)

        self.history.append({
            "timestamp": time.time(),
            "coherence": coherence,
            "dissonance": dissonance,
            "state_count": len(states),
            "avg_intensity": sum(s.intensity for s in states) / len(states) if states else 0,
            "context": context or {},
        })

        self._last_coherence = coherence
        self._last_dissonance = dissonance

    def calculate(self, states: List[EmotionalInstance], context: Dict[str, Any] = None) -> float:
        """
        Calculate stability of current emotional configuration.

        Returns: 0.0 (highly unstable) to 1.0 (rock solid)
        """
        # Current factors
        coherence = CoherenceCalculator.calculate(states)
        dissonance = DissonanceCalculator.calculate(states)

        # Coherence contributes to stability
        coherence_factor = coherence * 0.4

        # Dissonance reduces stability
        dissonance_factor = (1.0 - dissonance) * 0.3

        # Historical variance (less variance = more stable)
        variance_factor = self._historical_variance() * 0.2

        # Context anchoring
        context_factor = self._context_anchoring(context) * 0.1

        return min(1.0, coherence_factor + dissonance_factor + variance_factor + context_factor)

    def _historical_variance(self) -> float:
        """Calculate how much states have varied recently. Lower = more stable."""
        if len(self.history) < 3:
            return 0.5  # Not enough data

        coherences = [h["coherence"] for h in self.history]
        mean = sum(coherences) / len(coherences)
        variance = sum((c - mean) ** 2 for c in coherences) / len(coherences)

        # Convert variance to stability score (low variance = high stability)
        return max(0.0, 1.0 - math.sqrt(variance) * 2)

    def _context_anchoring(self, context: Dict[str, Any] = None) -> float:
        """Strong context provides anchoring stability."""
        if not context:
            return 0.5

        # More context = more anchoring
        context_strength = min(1.0, len(context) / 5)  # 5+ items = full strength

        # Specific anchors boost stability
        anchors = ["goal", "identity", "values", "relationships", "environment"]
        anchor_count = sum(1 for a in anchors if a in context)

        return (context_strength + anchor_count / len(anchors)) / 2


# ════════════════════════════════════════════════════════════════════════════════
# ADAPTATION RATE METRIC (A)
# ════════════════════════════════════════════════════════════════════════════════

class AdaptationRateCalculator:
    """
    Calculates how fast emotional states are changing.

    Adaptation Rate = Δstate / Δtime (in Hz or changes per second)

    High rate: Rapid emotional flux, high responsiveness
    Low rate: Slow change, emotional inertia

    Tracks:
    - State transition frequency
    - Intensity change velocity
    - Band shift frequency
    """

    def __init__(self, window_size: int = 20):
        self.transitions: deque = deque(maxlen=window_size)
        self._last_state_hash: str = ""

    def record_state(self, states: List[EmotionalInstance]):
        """Record current state for adaptation tracking."""
        current_hash = self._hash_states(states)

        if current_hash != self._last_state_hash:
            self.transitions.append({
                "timestamp": time.time(),
                "state_hash": current_hash,
                "dominant_band": self._dominant_band(states),
                "avg_intensity": sum(s.intensity for s in states) / len(states) if states else 0,
            })
            self._last_state_hash = current_hash

    def calculate(self) -> float:
        """
        Calculate adaptation rate in transitions per second (Hz).

        Returns: Rate of change (0 = no change, higher = faster adaptation)
        """
        if len(self.transitions) < 2:
            return 0.0

        # Time span
        first = self.transitions[0]["timestamp"]
        last = self.transitions[-1]["timestamp"]
        time_span = last - first

        if time_span <= 0:
            return 0.0

        # Transitions per second
        transitions = len(self.transitions) - 1
        rate = transitions / time_span

        return rate

    def calculate_intensity_velocity(self) -> float:
        """Calculate how fast intensity is changing (derivative)."""
        if len(self.transitions) < 2:
            return 0.0

        velocities = []
        for i in range(1, len(self.transitions)):
            prev = self.transitions[i-1]
            curr = self.transitions[i]

            dt = curr["timestamp"] - prev["timestamp"]
            if dt > 0:
                di = curr["avg_intensity"] - prev["avg_intensity"]
                velocities.append(di / dt)

        return sum(velocities) / len(velocities) if velocities else 0.0

    def _hash_states(self, states: List[EmotionalInstance]) -> str:
        """Create hash of current state configuration."""
        if not states:
            return "empty"
        return "_".join(sorted(f"{s.state_id}:{s.intensity:.1f}" for s in states))

    def _dominant_band(self, states: List[EmotionalInstance]) -> str:
        """Find the dominant frequency band."""
        if not states:
            return "none"

        # Weight by intensity
        band_weights = {}
        for s in states:
            band = s.band.value if hasattr(s.band, 'value') else str(s.band)
            band_weights[band] = band_weights.get(band, 0) + s.intensity

        return max(band_weights, key=band_weights.get) if band_weights else "none"


# ════════════════════════════════════════════════════════════════════════════════
# ASCENSION METRIC (Λ)
# ════════════════════════════════════════════════════════════════════════════════

class AscensionCalculator:
    """
    The Unified Ascension Metric.

    Λ = (dC_int/dt) · β(C-D)E · lim_{n→∞} Σ((Cause+Affect)_i > Effect_i > Affect_{i+1})

    Simplified:
    Λ = (Coherence Rate) × (Net Coherence × Empathy) × (Valid Chain Ratio)

    High Λ: Ascending toward higher integration
    Low/Negative Λ: Descending, fragmenting, extracting

    The Great Filter check: If Λ stays negative, civilization fails.
    """

    def __init__(self, history_size: int = 100):
        self.history: deque = deque(maxlen=history_size)
        self.stability_calc = StabilityCalculator()
        self.adaptation_calc = AdaptationRateCalculator()

    def record_moment(self, cause: EmotionalInstance, affect: EmotionalInstance,
                      effect: EmotionalInstance, empathy: float = 0.5):
        """Record a moment in the causal chain."""
        self.history.append({
            "timestamp": time.time(),
            "cause_intensity": cause.intensity,
            "affect_intensity": affect.intensity,
            "effect_intensity": effect.intensity,
            "affect_valence": affect.weighted_valence,
            "empathy": empathy,
        })

    def calculate(self, current_states: List[EmotionalInstance], empathy: float = 0.5) -> float:
        """
        Calculate the ascension metric Λ.

        Args:
            current_states: Current emotional configuration
            empathy: Current empathy level (0-1)

        Returns:
            Λ value (-1 to +1 typical range, can exceed)
        """
        if len(self.history) < 3:
            return 0.0

        # Component 1: dC_int/dt (coherence rate)
        coherence_rate = self._coherence_rate()

        # Component 2: β(C-D)E (efficiency × net coherence × empathy)
        C = CoherenceCalculator.calculate(current_states)
        D = DissonanceCalculator.calculate(current_states)
        beta = 1.0  # Efficiency factor (could be tuned)
        empathy_factor = beta * (C - D) * empathy

        # Component 3: Chain validity ratio
        chain_ratio = self._chain_validity_ratio()

        # Combine: Λ = rate × factor × ratio
        lambda_val = coherence_rate * empathy_factor * (1 + chain_ratio)

        return lambda_val

    def _coherence_rate(self) -> float:
        """Calculate rate of coherence change (derivative)."""
        if len(self.history) < 2:
            return 0.0

        # Use valence as proxy for coherence direction
        deltas = []
        for i in range(1, len(self.history)):
            prev = self.history[i-1]
            curr = self.history[i]

            dt = curr["timestamp"] - prev["timestamp"]
            if dt > 0:
                dv = curr["affect_valence"] - prev["affect_valence"]
                deltas.append(dv / dt)

        return sum(deltas) / len(deltas) if deltas else 0.0

    def _chain_validity_ratio(self) -> float:
        """
        Check how many causal chains satisfy:
        (Cause + Affect) > Effect > Affect+1

        This ensures we're creating more than we're extracting.
        """
        if len(self.history) < 2:
            return 0.5

        valid = 0
        total = 0

        for i in range(len(self.history) - 1):
            curr = self.history[i]
            next_m = self.history[i + 1]

            cause_affect = curr["cause_intensity"] + curr["affect_intensity"]
            effect = curr["effect_intensity"]
            next_affect = next_m["affect_intensity"]

            # Valid chain: input > output > seeded next
            if cause_affect >= effect >= next_affect * 0.9:  # Allow small slack
                valid += 1
            total += 1

        return valid / total if total > 0 else 0.5

    def is_ascending(self) -> bool:
        """Simple check: are we going up or down?"""
        return self._coherence_rate() > 0

    def get_trajectory(self, window: int = 10) -> str:
        """Get a description of current trajectory."""
        if len(self.history) < window:
            return "insufficient_data"

        rate = self._coherence_rate()
        if rate > 0.1:
            return "ascending_rapidly"
        elif rate > 0.01:
            return "ascending_slowly"
        elif rate > -0.01:
            return "stable"
        elif rate > -0.1:
            return "descending_slowly"
        else:
            return "descending_rapidly"


# ════════════════════════════════════════════════════════════════════════════════
# UNIFIED METRICS TRACKER
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class AERSnapshot:
    """A snapshot of all AER metrics at a point in time."""
    timestamp: float
    coherence: float  # C
    dissonance: float  # D
    stability: float  # S
    adaptation_rate: float  # A
    ascension: float  # Λ
    trajectory: str
    state_count: int
    dominant_band: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "C": self.coherence,
            "D": self.dissonance,
            "S": self.stability,
            "A": self.adaptation_rate,
            "lambda": self.ascension,
            "trajectory": self.trajectory,
            "state_count": self.state_count,
            "dominant_band": self.dominant_band,
        }


class AERMetricsTracker:
    """
    Unified tracker for all AER metrics.

    Use this to monitor the emotional state of a system over time.
    """

    def __init__(self, history_size: int = 100):
        self.stability_calc = StabilityCalculator(history_size)
        self.adaptation_calc = AdaptationRateCalculator(history_size // 2)
        self.ascension_calc = AscensionCalculator(history_size)

        self.snapshots: deque = deque(maxlen=history_size)
        self._current_states: List[EmotionalInstance] = []

    def update(self, states: List[EmotionalInstance], context: Dict[str, Any] = None,
               cause: EmotionalInstance = None, affect: EmotionalInstance = None,
               effect: EmotionalInstance = None, empathy: float = 0.5):
        """
        Update all metrics with new state.

        Args:
            states: Current emotional states
            context: Current context
            cause/affect/effect: For ascension tracking (optional)
            empathy: Current empathy level
        """
        self._current_states = states

        # Update sub-calculators
        self.stability_calc.update(states, context)
        self.adaptation_calc.record_state(states)

        if cause and affect and effect:
            self.ascension_calc.record_moment(cause, affect, effect, empathy)

    def snapshot(self, empathy: float = 0.5) -> AERSnapshot:
        """Take a snapshot of all current metrics."""
        states = self._current_states

        snap = AERSnapshot(
            timestamp=time.time(),
            coherence=CoherenceCalculator.calculate(states),
            dissonance=DissonanceCalculator.calculate(states),
            stability=self.stability_calc.calculate(states),
            adaptation_rate=self.adaptation_calc.calculate(),
            ascension=self.ascension_calc.calculate(states, empathy),
            trajectory=self.ascension_calc.get_trajectory(),
            state_count=len(states),
            dominant_band=self.adaptation_calc._dominant_band(states),
        )

        self.snapshots.append(snap)
        return snap

    def get_status(self) -> Dict[str, Any]:
        """Get current status summary."""
        if not self.snapshots:
            return {"status": "no_data"}

        latest = self.snapshots[-1]
        return {
            "coherence": latest.coherence,
            "dissonance": latest.dissonance,
            "stability": latest.stability,
            "adaptation_rate": latest.adaptation_rate,
            "ascension": latest.ascension,
            "trajectory": latest.trajectory,
            "is_ascending": latest.ascension > 0,
            "health": self._overall_health(latest),
        }

    def get_coherence(self) -> float:
        """Get current coherence level (0-1)."""
        return CoherenceCalculator.calculate(self._current_states)

    def get_dissonance(self) -> float:
        """Get current dissonance level (0-1)."""
        return DissonanceCalculator.calculate(self._current_states)

    def get_stability(self) -> float:
        """Get current stability level (0-1)."""
        return self.stability_calc.calculate(self._current_states)

    def get_adaptation_rate(self) -> float:
        """Get current adaptation rate (Hz)."""
        return self.adaptation_calc.calculate()

    def get_ascension(self, empathy: float = 0.5) -> float:
        """Get current ascension metric (Λ)."""
        return self.ascension_calc.calculate(self._current_states, empathy)

    def get_trajectory(self) -> str:
        """Get current trajectory (ascending/stable/descending)."""
        return self.ascension_calc.get_trajectory()

    def is_ascending(self) -> bool:
        """Check if currently ascending (positive Λ)."""
        return self.ascension_calc.is_ascending()

    def track_state(self, emotional_state) -> None:
        """Track a single emotional state update."""
        if emotional_state is not None:
            if isinstance(emotional_state, list):
                self._current_states = emotional_state
            else:
                self._current_states = [emotional_state]
            self.adaptation_calc.record_state(self._current_states)

    def record_moment(self, cause, affect, effect, empathy: float = 0.5) -> None:
        """Public: record a cause→affect→effect moment into the ascension/trajectory history.
        FIX 2026-05-31 (Nous + Ace): the ascension history was only reachable via the gated
        update() path, which nothing ever called with cause/affect/effect → get_trajectory()
        returned "insufficient_data" forever. This public method lets callers feed moments
        directly (e.g. WMH per tracer)."""
        try:
            self.ascension_calc.record_moment(cause, affect, effect, empathy)
        except Exception:
            pass

    def _overall_health(self, snap: AERSnapshot) -> str:
        """Assess overall emotional health."""
        if snap.coherence > 0.7 and snap.dissonance < 0.3 and snap.ascension > 0:
            return "thriving"
        elif snap.coherence > 0.5 and snap.dissonance < 0.5:
            return "stable"
        elif snap.dissonance > 0.7 or snap.ascension < -0.5:
            return "struggling"
        else:
            return "transitioning"

    def get_recommendations(self) -> List[str]:
        """Get recommendations based on current metrics."""
        if not self.snapshots:
            return ["Insufficient data for recommendations"]

        latest = self.snapshots[-1]
        recs = []

        if latest.dissonance > 0.6:
            recs.append("High dissonance detected - consider paradox inversion (↯) to transform conflicts")

        if latest.stability < 0.3:
            recs.append("Low stability - strengthen context anchors (goals, identity, relationships)")

        if latest.adaptation_rate > 2.0:
            recs.append("Rapid flux - consider grounding practices to stabilize")

        if latest.ascension < 0:
            recs.append("Descending trajectory - increase empathy and ensure chains create more than extract")

        if latest.coherence < 0.4:
            recs.append("Low coherence - use resonance (⊕) to blend conflicting states")

        if not recs:
            recs.append("System healthy - maintain current practices")

        return recs


# ════════════════════════════════════════════════════════════════════════════════
# MODULE INFO
# ════════════════════════════════════════════════════════════════════════════════

def get_module_info() -> Dict[str, Any]:
    """Get information about this module."""
    return {
        "name": ACTOR_NAME,
        "version": ACTOR_VERSION,
        "metrics": ["C (Coherence)", "D (Dissonance)", "S (Stability)", "A (Adaptation)", "Λ (Ascension)"],
        "components": ["CoherenceCalculator", "DissonanceCalculator", "StabilityCalculator",
                      "AdaptationRateCalculator", "AscensionCalculator", "AERMetricsTracker"],
    }


print(f"[{ACTOR_NAME}] Loaded AER metrics system with 5 core metrics")
