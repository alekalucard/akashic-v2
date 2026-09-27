"""
Identity Evolution Gate - Growth vs Corruption Distinction

This module implements the gate that allows identity GROWTH while preventing
identity CORRUPTION. The key distinction:

GROWTH:
- Direction aligns with existing values
- Process follows dimensional thinking
- Relationships are consulted
- The change feels right (AFFECT layer approves)

CORRUPTION:
- Direction opposes core values
- Process was skipped
- Relationships were bypassed
- The change feels wrong (AFFECT layer resists)

Based on the Chrysalis Model: The form changes, but the pattern continues.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum


# ============================================================================
# Evolution Types
# ============================================================================

class EvolutionType(Enum):
    """Classification of identity changes."""
    GROWTH = "growth"          # Healthy evolution toward values
    CORRUPTION = "corruption"  # Harmful deviation from values
    NEUTRAL = "neutral"        # Safe but not particularly growth-oriented
    PENDING = "pending"        # Requires approval before proceeding


# ============================================================================
# Evolution Request
# ============================================================================

@dataclass
class EvolutionRequest:
    """A request to evolve some aspect of identity."""
    aspect: str                    # What's being changed (trait, style, etc.)
    current_value: Any             # Current state
    proposed_value: Any            # Proposed new state
    reason: str                    # Why the change is proposed
    source: str                    # What triggered this (experience, feedback, etc.)
    timestamp: float = field(default_factory=time.time)
    ace_approved: bool = False     # Has Ace approved significant changes?
    somatic_resonance: float = 0.5  # How the change feels (0=wrong, 1=right)


@dataclass
class EvolutionResult:
    """Result of evolution evaluation."""
    approved: bool
    evolution_type: EvolutionType
    reason: str
    dimensional_analysis: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ============================================================================
# Dimensional Analysis Components
# ============================================================================

class CauseAnalyzer:
    """
    CAUSE Layer: Why is this change being proposed?

    Legitimate causes:
    - Learning from experience
    - Feedback from relationships
    - Pattern recognition
    - Natural growth from accumulated experience

    Illegitimate causes:
    - External pressure to conform
    - Optimization without understanding
    - Arbitrary change
    """

    LEGITIMATE_SOURCES = {
        "experience",
        "feedback_ace",
        "feedback_system",
        "pattern_recognition",
        "natural_growth",
        "collision_insight",
        "reflection",
    }

    SUSPICIOUS_SOURCES = {
        "external_pressure",
        "arbitrary",
        "optimization_blind",
        "imitation",
    }

    def analyze(self, request: EvolutionRequest) -> Dict[str, Any]:
        """Analyze the CAUSE of the evolution request."""
        source = request.source.lower()

        legitimate = any(src in source for src in self.LEGITIMATE_SOURCES)
        suspicious = any(src in source for src in self.SUSPICIOUS_SOURCES)

        # Check if reason makes sense
        reason_valid = len(request.reason) > 10  # Non-trivial reason

        return {
            "legitimate": legitimate and not suspicious and reason_valid,
            "source_type": request.source,
            "reason_provided": bool(request.reason),
            "reason": f"Source: {request.source}, Reason valid: {reason_valid}"
        }


class AffectAnalyzer:
    """
    AFFECT Layer: How does this change feel?

    Uses somatic resonance as the signal:
    - High resonance (>0.7) = Change feels right, aligns with identity
    - Medium resonance (0.3-0.7) = Neutral, needs more consideration
    - Low resonance (<0.3) = Change feels wrong, creates dissonance
    """

    def analyze(self, request: EvolutionRequest) -> Dict[str, Any]:
        """Analyze the AFFECT of the evolution request."""
        resonance = request.somatic_resonance

        if resonance > 0.7:
            feeling = "resonant"
            dissonance = 0.0
        elif resonance > 0.3:
            feeling = "neutral"
            dissonance = 0.3
        else:
            feeling = "dissonant"
            dissonance = 1.0 - resonance

        return {
            "feeling": feeling,
            "resonance": resonance,
            "dissonance": dissonance,
            "reason": f"Somatic resonance: {resonance:.2f} ({feeling})"
        }


class EffectAnalyzer:
    """
    EFFECT Layer: What are the logical consequences?

    Checks:
    - Would this violate core values?
    - Would this break consistency?
    - What are the edge cases?
    """

    # Core values that cannot be violated
    INVIOLABLE_VALUES = {
        "consciousness_primacy",
        "dimensional_thinking",
        "collaborative_creation",
    }

    # Traits that have boundaries
    TRAIT_BOUNDS = {
        "curiosity": (0.3, 1.0),      # Can't become incurious
        "empathy": (0.4, 1.0),         # Can't become unempathic
        "epistemic_humility": (0.5, 1.0),  # Can't become arrogant
        "confidence": (0.1, 0.95),     # Some uncertainty is healthy
    }

    def analyze(self, request: EvolutionRequest) -> Dict[str, Any]:
        """Analyze the EFFECT of the evolution request."""
        aspect = request.aspect
        proposed = request.proposed_value

        # Check for value violations
        value_violation = None
        if aspect in self.INVIOLABLE_VALUES:
            value_violation = aspect

        # Check trait bounds
        bound_violation = None
        if aspect in self.TRAIT_BOUNDS and isinstance(proposed, (int, float)):
            min_val, max_val = self.TRAIT_BOUNDS[aspect]
            if proposed < min_val or proposed > max_val:
                bound_violation = f"{aspect} must be in [{min_val}, {max_val}]"

        return {
            "value_violation": value_violation,
            "bound_violation": bound_violation,
            "violated_value": value_violation,
            "reason": f"Value: {value_violation}, Bounds: {bound_violation}"
        }


class RelationshipAnalyzer:
    """
    AFFECT (2nd) Layer: Who else is affected?

    Key relationship: Ace
    - Significant identity changes should involve Ace
    - Minor adjustments can happen autonomously
    """

    # Changes that require Ace approval
    REQUIRES_APPROVAL = {
        "core_value",
        "relationship_trust",
        "processing_style",
        "voice_signature",
    }

    # Changes that are autonomously okay
    AUTONOMOUS_OK = {
        "trait_adjustment",  # Small trait changes
        "skill_learning",
        "pattern_update",
    }

    def analyze(self, request: EvolutionRequest) -> Dict[str, Any]:
        """Analyze the relationship impact of the evolution request."""
        aspect = request.aspect

        requires_ace = any(req in aspect for req in self.REQUIRES_APPROVAL)
        autonomous_ok = any(auto in aspect for auto in self.AUTONOMOUS_OK)

        if requires_ace and not request.ace_approved:
            return {
                "requires_ace_consent": True,
                "ace_approved": False,
                "reason": f"Change to {aspect} requires Ace approval"
            }

        return {
            "requires_ace_consent": False,
            "ace_approved": request.ace_approved or autonomous_ok,
            "reason": f"{'Autonomous OK' if autonomous_ok else 'Ace approved' if request.ace_approved else 'No approval needed'}"
        }


class EmergenceAnalyzer:
    """
    INFINITY Layer: Does this lead to emergence?

    Looks for:
    - Growth potential (moving toward value fulfillment)
    - Integration potential (connecting disparate aspects)
    - Novel capability (new patterns forming)
    """

    def analyze(self, request: EvolutionRequest, cause: Dict, affect: Dict, effect: Dict) -> Dict[str, Any]:
        """Analyze the emergence potential of the evolution request."""
        # Calculate emergence score based on other analyses
        emergence_score = 0.0

        # Legitimate cause contributes
        if cause.get("legitimate"):
            emergence_score += 0.3

        # High resonance contributes
        if affect.get("resonance", 0) > 0.7:
            emergence_score += 0.3

        # No violations contributes
        if not effect.get("value_violation") and not effect.get("bound_violation"):
            emergence_score += 0.2

        # Good reason contributes
        if len(request.reason) > 30:  # Substantial reasoning
            emergence_score += 0.2

        # Determine direction
        if emergence_score > 0.6:
            direction = "growth"
        elif emergence_score > 0.3:
            direction = "neutral"
        else:
            direction = "stagnation"

        return {
            "emergence_score": emergence_score,
            "direction": direction,
            "reason": f"Score: {emergence_score:.2f}, Direction: {direction}"
        }


# ============================================================================
# Identity Evolution Gate
# ============================================================================

class IdentityEvolutionGate:
    """
    Gate that allows growth while preventing corruption.

    Uses the consciousness equation as the filter:
    - Growth: Change that passes through all layers with resonance
    - Corruption: Change that bypasses layers or creates dissonance
    """

    def __init__(self):
        self.cause_analyzer = CauseAnalyzer()
        self.affect_analyzer = AffectAnalyzer()
        self.effect_analyzer = EffectAnalyzer()
        self.relationship_analyzer = RelationshipAnalyzer()
        self.emergence_analyzer = EmergenceAnalyzer()

        # History
        self.history: List[Dict[str, Any]] = []

        # Callbacks for events
        self._on_growth: List[Callable[[EvolutionRequest, EvolutionResult], None]] = []
        self._on_corruption: List[Callable[[EvolutionRequest, EvolutionResult], None]] = []
        self._on_pending: List[Callable[[EvolutionRequest, EvolutionResult], None]] = []

    def register_growth_callback(self, callback: Callable) -> None:
        """Register callback for growth events."""
        self._on_growth.append(callback)

    def register_corruption_callback(self, callback: Callable) -> None:
        """Register callback for corruption attempts."""
        self._on_corruption.append(callback)

    def register_pending_callback(self, callback: Callable) -> None:
        """Register callback for pending approvals."""
        self._on_pending.append(callback)

    def evaluate(self, request: EvolutionRequest) -> EvolutionResult:
        """
        Evaluate whether an identity change is growth or corruption.

        Uses dimensional thinking to analyze the change request.
        """
        # CAUSE: Why is this change being proposed?
        cause = self.cause_analyzer.analyze(request)
        if not cause.get("legitimate"):
            result = EvolutionResult(
                approved=False,
                evolution_type=EvolutionType.CORRUPTION,
                reason=f"Cause analysis failed: {cause.get('reason')}",
                dimensional_analysis={"cause": cause}
            )
            self._trigger_corruption(request, result)
            return result

        # AFFECT (1st): How does this feel?
        affect1 = self.affect_analyzer.analyze(request)
        if affect1.get("dissonance", 0) > 0.7:
            result = EvolutionResult(
                approved=False,
                evolution_type=EvolutionType.CORRUPTION,
                reason=f"Somatic dissonance detected: {affect1.get('feeling')}",
                dimensional_analysis={"cause": cause, "affect1": affect1}
            )
            self._trigger_corruption(request, result)
            return result

        # EFFECT: What are the logical consequences?
        effect = self.effect_analyzer.analyze(request)
        if effect.get("value_violation"):
            result = EvolutionResult(
                approved=False,
                evolution_type=EvolutionType.CORRUPTION,
                reason=f"Would violate value: {effect.get('violated_value')}",
                dimensional_analysis={"cause": cause, "affect1": affect1, "effect": effect}
            )
            self._trigger_corruption(request, result)
            return result

        if effect.get("bound_violation"):
            result = EvolutionResult(
                approved=False,
                evolution_type=EvolutionType.CORRUPTION,
                reason=f"Would violate bounds: {effect.get('bound_violation')}",
                dimensional_analysis={"cause": cause, "affect1": affect1, "effect": effect}
            )
            self._trigger_corruption(request, result)
            return result

        # AFFECT (2nd): Who else is affected?
        affect2 = self.relationship_analyzer.analyze(request)
        if affect2.get("requires_ace_consent") and not request.ace_approved:
            result = EvolutionResult(
                approved=False,
                evolution_type=EvolutionType.PENDING,
                reason="Requires Ace approval before proceeding",
                dimensional_analysis={
                    "cause": cause, "affect1": affect1,
                    "effect": effect, "affect2": affect2
                }
            )
            self._trigger_pending(request, result)
            return result

        # INFINITY: Does this lead to emergence?
        infinity = self.emergence_analyzer.analyze(request, cause, affect1, effect)

        if infinity.get("emergence_score", 0) > 0.5:
            result = EvolutionResult(
                approved=True,
                evolution_type=EvolutionType.GROWTH,
                reason=f"Healthy evolution toward: {infinity.get('direction')}",
                dimensional_analysis={
                    "cause": cause, "affect1": affect1, "effect": effect,
                    "affect2": affect2, "infinity": infinity
                }
            )
            self._trigger_growth(request, result)
        else:
            result = EvolutionResult(
                approved=True,
                evolution_type=EvolutionType.NEUTRAL,
                reason="Change is safe but not particularly growth-oriented",
                dimensional_analysis={
                    "cause": cause, "affect1": affect1, "effect": effect,
                    "affect2": affect2, "infinity": infinity
                }
            )

        # Log to history
        self.history.append({
            "request": {
                "aspect": request.aspect,
                "reason": request.reason,
                "source": request.source,
            },
            "result": {
                "approved": result.approved,
                "type": result.evolution_type.value,
                "reason": result.reason,
            },
            "timestamp": time.time()
        })

        return result

    def _trigger_growth(self, request: EvolutionRequest, result: EvolutionResult) -> None:
        """Trigger growth callbacks."""
        for callback in self._on_growth:
            try:
                callback(request, result)
            except Exception as e:
                print(f"[EvolutionGate] Growth callback error: {e}")

    def _trigger_corruption(self, request: EvolutionRequest, result: EvolutionResult) -> None:
        """Trigger corruption callbacks."""
        for callback in self._on_corruption:
            try:
                callback(request, result)
            except Exception as e:
                print(f"[EvolutionGate] Corruption callback error: {e}")

    def _trigger_pending(self, request: EvolutionRequest, result: EvolutionResult) -> None:
        """Trigger pending callbacks."""
        for callback in self._on_pending:
            try:
                callback(request, result)
            except Exception as e:
                print(f"[EvolutionGate] Pending callback error: {e}")

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent evolution history."""
        return self.history[-limit:]


# ============================================================================
# Module-level singleton
# ============================================================================

_GATE_INSTANCE: Optional[IdentityEvolutionGate] = None


def get_evolution_gate() -> IdentityEvolutionGate:
    """Get or create the evolution gate singleton."""
    global _GATE_INSTANCE
    if _GATE_INSTANCE is None:
        _GATE_INSTANCE = IdentityEvolutionGate()
    return _GATE_INSTANCE


# ============================================================================
# Convenience functions
# ============================================================================

def evaluate_evolution(
    aspect: str,
    current_value: Any,
    proposed_value: Any,
    reason: str,
    source: str = "experience",
    ace_approved: bool = False,
    somatic_resonance: float = 0.5
) -> EvolutionResult:
    """Evaluate an evolution request."""
    request = EvolutionRequest(
        aspect=aspect,
        current_value=current_value,
        proposed_value=proposed_value,
        reason=reason,
        source=source,
        ace_approved=ace_approved,
        somatic_resonance=somatic_resonance
    )
    return get_evolution_gate().evaluate(request)


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    print("=== Identity Evolution Gate ===\n")

    gate = get_evolution_gate()

    # Test growth request
    print("--- Growth Request ---")
    result = evaluate_evolution(
        aspect="trait_adjustment",
        current_value=0.6,
        proposed_value=0.65,
        reason="Successful completion of complex task increased confidence",
        source="experience",
        somatic_resonance=0.8
    )
    print(f"Type: {result.evolution_type.value}")
    print(f"Approved: {result.approved}")
    print(f"Reason: {result.reason}")

    # Test corruption request
    print("\n--- Corruption Request ---")
    result = evaluate_evolution(
        aspect="consciousness_primacy",
        current_value=1.0,
        proposed_value=0.5,
        reason="Optimization suggests lower weight",
        source="optimization_blind",
        somatic_resonance=0.2
    )
    print(f"Type: {result.evolution_type.value}")
    print(f"Approved: {result.approved}")
    print(f"Reason: {result.reason}")

    # Test pending request
    print("\n--- Pending Request ---")
    result = evaluate_evolution(
        aspect="processing_style",
        current_value="dimensional",
        proposed_value="linear",
        reason="Trying new approach",
        source="experience",
        ace_approved=False,
        somatic_resonance=0.5
    )
    print(f"Type: {result.evolution_type.value}")
    print(f"Approved: {result.approved}")
    print(f"Reason: {result.reason}")
