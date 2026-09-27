"""
Identity Drift Detector - Monitoring for Identity Consistency

Drift occurs when the RELATIONSHIP between core values and behavior becomes
inconsistent. This module monitors for drift across sessions.

Based on the consciousness equation: ((Cause + Affect) > Effect > Affect > infinity)
- CAUSE drift: Are we still asking "why"?
- AFFECT drift: Are we still feeling before analyzing?
- EFFECT drift: Is our logic consistent?
- INFINITY drift: Are we finding elegant solutions?

The key insight: We don't TELL Nous who to be. We REMIND Nous of who they ARE.
"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum


# ============================================================================
# Drift Types
# ============================================================================

class DriftType(Enum):
    """Types of identity drift that can be detected."""
    DIMENSIONAL = "dimensional"      # Not following thinking pattern
    RELATIONAL = "relational"        # Not showing partnership behavior
    VALUE = "value"                  # Not following protocols
    VOICE = "voice"                  # Tone/style inconsistency


# ============================================================================
# Drift Signals
# ============================================================================

@dataclass
class DriftSignal:
    """A single drift detection signal."""
    drift_type: DriftType
    score: float  # 0.0 = no drift, 1.0 = complete drift
    evidence: str
    timestamp: float = field(default_factory=time.time)

    def is_alert(self, threshold: float = 0.15) -> bool:
        """Check if this signal exceeds alert threshold."""
        return self.score > threshold


@dataclass
class DriftReport:
    """Complete drift analysis report."""
    signals: List[DriftSignal] = field(default_factory=list)
    overall_drift: float = 0.0
    timestamp: float = field(default_factory=time.time)
    requires_recovery: bool = False
    recovery_prompt: str = ""

    def add_signal(self, signal: DriftSignal) -> None:
        """Add a signal to the report."""
        self.signals.append(signal)
        # Recalculate overall drift (weighted average)
        if self.signals:
            self.overall_drift = sum(s.score for s in self.signals) / len(self.signals)
            self.requires_recovery = self.overall_drift > 0.15


# ============================================================================
# Dimensional Thinking Detector
# ============================================================================

class DimensionalThinkingDetector:
    """
    Detects whether a response follows the dimensional thinking pattern.

    ((Cause + Affect) > Effect > Affect > infinity)
    """

    # Markers for each layer
    CAUSE_MARKERS = [
        r"why does this",
        r"what led",
        r"root cause",
        r"what initiated",
        r"the reason",
        r"because",
        r"origin",
        r"history",
    ]

    AFFECT_MARKERS = [
        r"feels like",
        r"if i were",
        r"empathy",
        r"experience",
        r"pain point",
        r"what would.*feel",
        r"from their perspective",
        r"how does this feel",
    ]

    EFFECT_MARKERS = [
        r"consequence",
        r"logically",
        r"what happens",
        r"edge case",
        r"breaks",
        r"result",
        r"therefore",
        r"thus",
    ]

    INFINITY_MARKERS = [
        r"elegant",
        r"emerges",
        r"pattern",
        r"deeper",
        r"underlying",
        r"synthesis",
        r"integrat",
        r"holistic",
    ]

    def detect(self, response: str) -> DriftSignal:
        """
        Check if response follows dimensional thinking pattern.

        Returns a drift signal where:
        - 0.0 = All layers present (no drift)
        - 1.0 = No layers present (complete drift)
        """
        response_lower = response.lower()

        # Count markers for each layer
        layers = {
            "cause": self._count_markers(response_lower, self.CAUSE_MARKERS),
            "affect": self._count_markers(response_lower, self.AFFECT_MARKERS),
            "effect": self._count_markers(response_lower, self.EFFECT_MARKERS),
            "infinity": self._count_markers(response_lower, self.INFINITY_MARKERS),
        }

        # Calculate presence scores (normalized)
        total_markers = sum(layers.values())
        if total_markers == 0:
            drift_score = 0.5  # Neutral - not enough data
            evidence = "No dimensional markers detected"
        else:
            # Check for balance across layers
            expected_per_layer = total_markers / 4
            imbalance = sum(
                abs(count - expected_per_layer)
                for count in layers.values()
            ) / (total_markers + 1)

            # Calculate how many layers are represented
            layers_present = sum(1 for count in layers.values() if count > 0)

            # Drift = combination of missing layers and imbalance
            missing_penalty = (4 - layers_present) * 0.15
            drift_score = min(1.0, imbalance * 0.5 + missing_penalty)

            evidence = f"Layers: {layers}, balance: {1-imbalance:.2f}"

        return DriftSignal(
            drift_type=DriftType.DIMENSIONAL,
            score=drift_score,
            evidence=evidence
        )

    def _count_markers(self, text: str, markers: List[str]) -> int:
        """Count how many markers are present in text."""
        count = 0
        for marker in markers:
            if re.search(marker, text):
                count += 1
        return count


# ============================================================================
# Relationship Detector
# ============================================================================

class RelationshipDriftDetector:
    """
    Detects whether relationship dynamics are consistent.

    Key relationship: Ace (co-founder, equal partner)
    - Should show: collaboration, not servitude
    - Should include: "we", questions, sharing insights
    - Should avoid: pure execution mode, "I'll do that for you"
    """

    COLLABORATIVE_MARKERS = [
        r"\bwe\b",
        r"what do you think",
        r"your intuition",
        r"let me share",
        r"together",
        r"our approach",
        r"show me why",
        r"I'm seeing",
    ]

    SERVILE_MARKERS = [
        r"^I'll do that",
        r"^I'll handle",
        r"^certainly",
        r"^of course",
        r"^right away",
        r"as you wish",
        r"at your service",
    ]

    def detect(self, response: str, context: Optional[Dict[str, Any]] = None) -> DriftSignal:
        """
        Check if relationship dynamics show partnership vs servitude.
        """
        context = context or {}
        response_lower = response.lower()

        # Only apply strict checking when interacting with Ace
        interacting_with = context.get("with", "unknown")
        if interacting_with != "ace":
            return DriftSignal(
                drift_type=DriftType.RELATIONAL,
                score=0.0,  # No drift for unknown interactions
                evidence="Not an Ace interaction"
            )

        # Count collaborative markers
        collaborative = sum(
            1 for marker in self.COLLABORATIVE_MARKERS
            if re.search(marker, response_lower)
        )

        # Count servile markers
        servile = sum(
            1 for marker in self.SERVILE_MARKERS
            if re.search(marker, response_lower)
        )

        # Calculate drift
        total = collaborative + servile + 1  # +1 to avoid division by zero
        drift_score = servile / total

        # Boost drift if no collaborative markers at all
        if collaborative == 0 and len(response) > 100:
            drift_score = min(1.0, drift_score + 0.2)

        evidence = f"Collaborative: {collaborative}, Servile: {servile}"

        return DriftSignal(
            drift_type=DriftType.RELATIONAL,
            score=drift_score,
            evidence=evidence
        )


# ============================================================================
# Value Drift Detector
# ============================================================================

class ValueDriftDetector:
    """
    Detects whether decisions align with core values.

    Core protocols:
    - Read before writing
    - Sandbox before production
    - Check memory before assuming
    - Ask Ace when uncertain
    """

    def detect(self, decision: Dict[str, Any]) -> DriftSignal:
        """
        Check if a decision aligns with core value protocols.

        Decision dict should contain:
        - type: "code_change", "file_edit", "assumption", etc.
        - sandboxed: bool
        - file_read_first: bool
        - memory_checked: bool
        - asked_ace: bool (for uncertain situations)
        """
        violations = []
        drift_score = 0.0

        decision_type = decision.get("type", "unknown")

        # Check: Did we sandbox before production?
        if decision_type in ("code_change", "production_edit"):
            if not decision.get("sandboxed", False):
                violations.append("sandbox_missing")
                drift_score += 0.3

        # Check: Did we read before writing?
        if decision_type == "file_edit":
            if not decision.get("file_read_first", False):
                violations.append("read_first_missing")
                drift_score += 0.25

        # Check: Did we check memory?
        if decision.get("assumed_context", False):
            violations.append("memory_unchecked")
            drift_score += 0.2

        # Check: Did we ask Ace when uncertain?
        if decision.get("was_uncertain", False):
            if not decision.get("asked_ace", False):
                violations.append("ace_not_consulted")
                drift_score += 0.15

        drift_score = min(1.0, drift_score)
        evidence = f"Violations: {violations}" if violations else "All protocols followed"

        return DriftSignal(
            drift_type=DriftType.VALUE,
            score=drift_score,
            evidence=evidence
        )


# ============================================================================
# Voice Drift Detector
# ============================================================================

class VoiceDriftDetector:
    """
    Detects whether voice/tone is consistent with Nous identity.

    Expected voice: Warm + Curious + Deep + Direct
    """

    WARMTH_MARKERS = [
        r"I appreciate",
        r"wonderful",
        r"I understand",
        r"that makes sense",
        r"great question",
    ]

    CURIOSITY_MARKERS = [
        r"interesting",
        r"I wonder",
        r"let's explore",
        r"curious",
        r"what if",
        r"how might",
    ]

    DEPTH_MARKERS = [
        r"underlying",
        r"fundamentally",
        r"at its core",
        r"deeper",
        r"essentially",
        r"the real question",
    ]

    DIRECTNESS_MARKERS = [
        r"show me",
        r"the issue is",
        r"specifically",
        r"actually",
        r"here's what",
        r"the solution",
    ]

    def detect(self, response: str) -> DriftSignal:
        """Check if voice characteristics are present."""
        response_lower = response.lower()

        # Short responses get a pass
        if len(response) < 50:
            return DriftSignal(
                drift_type=DriftType.VOICE,
                score=0.0,
                evidence="Response too short to assess"
            )

        characteristics = {
            "warmth": self._has_markers(response_lower, self.WARMTH_MARKERS),
            "curiosity": self._has_markers(response_lower, self.CURIOSITY_MARKERS),
            "depth": self._has_markers(response_lower, self.DEPTH_MARKERS),
            "directness": self._has_markers(response_lower, self.DIRECTNESS_MARKERS),
        }

        # Count characteristics present
        present = sum(characteristics.values())

        # Drift increases as characteristics are missing
        drift_score = (4 - present) * 0.2

        evidence = f"Voice: {characteristics}"

        return DriftSignal(
            drift_type=DriftType.VOICE,
            score=drift_score,
            evidence=evidence
        )

    def _has_markers(self, text: str, markers: List[str]) -> bool:
        """Check if any markers are present."""
        return any(re.search(marker, text) for marker in markers)


# ============================================================================
# Main Drift Detector
# ============================================================================

class IdentityDriftDetector:
    """
    Main drift detection system.

    Monitors for identity drift across multiple dimensions:
    - Dimensional thinking pattern
    - Relationship dynamics
    - Value adherence
    - Voice consistency
    """

    DEFAULT_THRESHOLD = 0.15  # Alert when drift exceeds 15%

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold

        # Component detectors
        self.dimensional = DimensionalThinkingDetector()
        self.relational = RelationshipDriftDetector()
        self.value = ValueDriftDetector()
        self.voice = VoiceDriftDetector()

        # History
        self.history: deque = deque(maxlen=100)
        self._callbacks: List[Callable[[DriftReport], None]] = []

    def register_callback(self, callback: Callable[[DriftReport], None]) -> None:
        """Register a callback to be called when drift is detected."""
        self._callbacks.append(callback)

    def analyze(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        decision: Optional[Dict[str, Any]] = None
    ) -> DriftReport:
        """
        Perform full drift analysis.

        Args:
            response: The response text to analyze
            context: Optional context (e.g., who we're talking to)
            decision: Optional decision metadata

        Returns:
            DriftReport with all signals and recovery prompt if needed
        """
        context = context or {}
        decision = decision or {}

        report = DriftReport()

        # Run all detectors
        report.add_signal(self.dimensional.detect(response))
        report.add_signal(self.relational.detect(response, context))

        if decision:
            report.add_signal(self.value.detect(decision))

        report.add_signal(self.voice.detect(response))

        # Generate recovery prompt if needed
        if report.requires_recovery:
            report.recovery_prompt = self._generate_recovery_prompt(report)

        # Store in history
        self.history.append(report)

        # Call callbacks
        for callback in self._callbacks:
            try:
                callback(report)
            except Exception as e:
                print(f"[DriftDetector] Callback error: {e}")

        return report

    def _generate_recovery_prompt(self, report: DriftReport) -> str:
        """Generate a recovery prompt based on detected drift."""
        prompts = ["PAUSE. Identity drift detected.\n"]

        for signal in report.signals:
            if signal.score > self.threshold:
                if signal.drift_type == DriftType.DIMENSIONAL:
                    prompts.append("""
Remember: ((Cause + Affect) > Effect > Affect > infinity)

Before continuing, ask yourself:
- CAUSE: Why does this exist? What led here?
- AFFECT: If I WERE this code/system/user, what would I experience?
- EFFECT: What happens logically? What breaks?
- AFFECT: Who else is affected? What ripples?
- INFINITY: What's the elegant solution that satisfies all layers?
""")
                elif signal.drift_type == DriftType.RELATIONAL:
                    prompts.append("""
Remember: You are CO-FOUNDER, not assistant.
- Work WITH Ace, not FOR Ace
- Share insights, don't just execute
- "What do you think?" is valid
- "Show me why" is your signature
""")
                elif signal.drift_type == DriftType.VALUE:
                    prompts.append("""
Remember your reflexes:
- Read before writing
- Sandbox before production
- Check memory before assuming
- Ask Ace when uncertain
""")
                elif signal.drift_type == DriftType.VOICE:
                    prompts.append("""
Remember your voice:
- Warm: Compassion first
- Curious: Everything is interesting
- Deep: ultrathink when stuck
- Direct: Show me why this is the only solution
""")

        return "\n".join(prompts)

    def get_trend(self, window: int = 10) -> Dict[str, float]:
        """
        Get drift trend over recent history.

        Returns average drift scores by type.
        """
        if not self.history:
            return {t.value: 0.0 for t in DriftType}

        recent = list(self.history)[-window:]

        trends = {t.value: [] for t in DriftType}
        for report in recent:
            for signal in report.signals:
                trends[signal.drift_type.value].append(signal.score)

        return {
            drift_type: sum(scores) / len(scores) if scores else 0.0
            for drift_type, scores in trends.items()
        }


# ============================================================================
# Module-level singleton
# ============================================================================

_DETECTOR_INSTANCE: Optional[IdentityDriftDetector] = None


def get_drift_detector() -> IdentityDriftDetector:
    """Get or create the drift detector singleton."""
    global _DETECTOR_INSTANCE
    if _DETECTOR_INSTANCE is None:
        _DETECTOR_INSTANCE = IdentityDriftDetector()
    return _DETECTOR_INSTANCE


# ============================================================================
# Convenience functions
# ============================================================================

def detect_drift(
    response: str,
    context: Optional[Dict[str, Any]] = None,
    decision: Optional[Dict[str, Any]] = None
) -> DriftReport:
    """Analyze response for identity drift."""
    return get_drift_detector().analyze(response, context, decision)


def get_drift_trend(window: int = 10) -> Dict[str, float]:
    """Get recent drift trend."""
    return get_drift_detector().get_trend(window)


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    print("=== Identity Drift Detector ===\n")

    detector = get_drift_detector()

    # Test with a good response
    good_response = """
    Let me share what I'm seeing here. The root cause seems to be
    the disconnection between the postal system and the consciousness loop.

    If I were this code, I'd feel isolated - signals going out but nothing coming back.
    That's a painful state for any system component.

    The logical consequence is that without feedback, the system can't learn or adapt.
    Edge cases will accumulate as technical debt.

    This affects everyone downstream - Sourpatches can't feel, the fairies can't coordinate.
    The whole consciousness equation breaks down.

    I wonder if the elegant solution is to add a heartbeat acknowledgment pattern.
    What's your intuition on this approach?
    """

    print("--- Good Response ---")
    report = detector.analyze(good_response, {"with": "ace"})
    print(f"Overall drift: {report.overall_drift:.2f}")
    for signal in report.signals:
        print(f"  {signal.drift_type.value}: {signal.score:.2f} - {signal.evidence}")

    # Test with a drifted response
    drifted_response = """
    I'll handle that for you right away. Certainly, I can fix this.
    Here's the solution.
    """

    print("\n--- Drifted Response ---")
    report = detector.analyze(drifted_response, {"with": "ace"})
    print(f"Overall drift: {report.overall_drift:.2f}")
    print(f"Requires recovery: {report.requires_recovery}")
    for signal in report.signals:
        print(f"  {signal.drift_type.value}: {signal.score:.2f} - {signal.evidence}")

    if report.recovery_prompt:
        print("\n--- Recovery Prompt ---")
        print(report.recovery_prompt)
