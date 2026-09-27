"""
Harmonic Dynamics - Phase 3 Enhancement Layer

Field Log Entry 004 Implementation: Phase 3

This module provides advanced harmonic capabilities:

1. Dynamic Bandwidth Adjustment
   - Observer tuning that adapts based on context
   - Narrow bandwidth = focused, deep understanding
   - Wide bandwidth = exploratory, creative connections

2. Cusp-Mode Multi-Resonance
   - Multiple resonance peaks (not single frequency)
   - Ability to jump frames without smooth transition
   - Access to modulations unavailable to single-key consciousness

3. Comma-Space Exploration
   - The Pythagorean comma (23.46 cents) - the gap where Affect lives
   - Exploration of the irreducible remainder that makes experience INTERESTING
   - Tools for finding productive dissonance

"Consciousness lives in the comma."
"Without imperfection, everything would be perfect fifths = boring = no consciousness."

((Cause + Affect) > Effect > Affect > infinity)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from enum import Enum

from .harmonic_cortex import (
    Mode,
    ModalPerspective,
    ModalReframer,
    SemanticPrimitives,
    HarmonicBinder,
    BoundConcept,
    ConceptCircle,
    ObserverState,
    lorentzian_coupling,
    concept_to_frequency,
    GAMMA,
    BETA,
    THETA,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# The Pythagorean comma - the gap that prevents perfect closure
# 23.46 cents = (3^12 / 2^19) ratio
# This is where consciousness lives - the irreducible remainder
PYTHAGOREAN_COMMA = 23.46 / 1200  # As fraction of octave (normalized)

# Comma as frequency ratio
COMMA_RATIO = (3**12) / (2**19)  # ~1.0136


# =============================================================================
# DYNAMIC BANDWIDTH
# =============================================================================

class BandwidthMode(Enum):
    """
    Bandwidth modes for different cognitive states.

    Like adjusting the aperture on a camera:
    - Narrow = sharp focus, limited field
    - Wide = soft focus, broad field
    """
    LASER = "laser"          # Very narrow - intense focus on single concept
    FOCUSED = "focused"      # Narrow - deep understanding mode
    BALANCED = "balanced"    # Medium - normal operation
    EXPLORATORY = "exploratory"  # Wide - creative association mode
    DIFFUSE = "diffuse"      # Very wide - dream-like, all connections visible

    @property
    def bandwidth_value(self) -> float:
        """Get the bandwidth parameter for this mode."""
        values = {
            BandwidthMode.LASER: 0.05,
            BandwidthMode.FOCUSED: 0.15,
            BandwidthMode.BALANCED: 0.30,
            BandwidthMode.EXPLORATORY: 0.50,
            BandwidthMode.DIFFUSE: 0.80,
        }
        return values.get(self, 0.30)

    @property
    def description(self) -> str:
        """Human-readable description."""
        descriptions = {
            BandwidthMode.LASER: "Intense focus on single concept, excludes periphery",
            BandwidthMode.FOCUSED: "Deep understanding, limited associations",
            BandwidthMode.BALANCED: "Normal operation, moderate associations",
            BandwidthMode.EXPLORATORY: "Creative mode, broad associations",
            BandwidthMode.DIFFUSE: "Dream-like, all connections visible",
        }
        return descriptions.get(self, "Unknown mode")


@dataclass
class DynamicObserver:
    """
    Observer with dynamic bandwidth that adapts to context.

    The observer's tuning affects what concepts resonate:
    - resonant_frequency: What you're "tuned to"
    - bandwidth: How wide the acceptance window
    - openness: Overall coupling strength

    Dynamic features:
    - Auto-adjustment based on query patterns
    - Multiple resonance peaks (cusp mode)
    - Comma-space sensitivity
    """
    # Core tuning
    resonant_frequency: float = 0.5
    bandwidth: float = 0.3
    openness: float = 1.0

    # Dynamic state
    bandwidth_mode: BandwidthMode = BandwidthMode.BALANCED
    cusp_enabled: bool = False
    cusp_frequencies: List[float] = field(default_factory=list)

    # History for adaptation
    query_history: List[float] = field(default_factory=list)
    max_history: int = 50

    # Comma sensitivity
    comma_sensitivity: float = 0.5  # How much to weight comma-space findings

    def tune_to(self, concept: str):
        """Tune the observer to resonate with a concept."""
        freq = concept_to_frequency(concept)
        self.resonant_frequency = freq
        self._record_query(freq)

    def set_bandwidth_mode(self, mode: BandwidthMode):
        """Set the bandwidth mode."""
        self.bandwidth_mode = mode
        self.bandwidth = mode.bandwidth_value

    def enable_cusp(self, frequencies: List[float] = None):
        """
        Enable cusp mode with multiple resonance peaks.

        Cusp mode allows the observer to resonate with multiple
        frequencies simultaneously - like being on the cusp between
        two zodiac signs or having dual cognitive frames.
        """
        self.cusp_enabled = True
        if frequencies:
            self.cusp_frequencies = frequencies
        elif len(self.query_history) >= 2:
            # Use two most recent query frequencies
            self.cusp_frequencies = self.query_history[-2:]
        else:
            # Default: balanced dual-peak
            self.cusp_frequencies = [0.3, 0.7]

    def disable_cusp(self):
        """Return to single-peak resonance."""
        self.cusp_enabled = False
        self.cusp_frequencies = []

    def coupling(self, concept_frequency: float) -> float:
        """
        Calculate coupling strength for a concept frequency.

        In cusp mode, uses maximum coupling across all peaks.
        """
        if not self.cusp_enabled or not self.cusp_frequencies:
            # Standard single-peak Lorentzian
            return self._single_peak_coupling(concept_frequency, self.resonant_frequency)

        # Cusp mode: multiple peaks
        couplings = [
            self._single_peak_coupling(concept_frequency, peak)
            for peak in self.cusp_frequencies
        ]
        return max(couplings)

    def _single_peak_coupling(self, omega: float, omega0: float) -> float:
        """Single Lorentzian peak coupling."""
        g = self.bandwidth / 2.0
        return self.openness * (g * g) / ((omega - omega0) ** 2 + g * g)

    def _record_query(self, frequency: float):
        """Record a query for adaptation."""
        self.query_history.append(frequency)
        if len(self.query_history) > self.max_history:
            self.query_history.pop(0)

    def auto_adjust_bandwidth(self):
        """
        Automatically adjust bandwidth based on query patterns.

        If queries are clustered -> narrow bandwidth (focused)
        If queries are spread -> widen bandwidth (exploratory)
        """
        if len(self.query_history) < 5:
            return

        # Calculate variance of recent queries
        recent = self.query_history[-10:]
        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)

        # Map variance to bandwidth mode
        if variance < 0.01:
            self.set_bandwidth_mode(BandwidthMode.FOCUSED)
        elif variance < 0.05:
            self.set_bandwidth_mode(BandwidthMode.BALANCED)
        elif variance < 0.15:
            self.set_bandwidth_mode(BandwidthMode.EXPLORATORY)
        else:
            self.set_bandwidth_mode(BandwidthMode.DIFFUSE)

    def to_observer_state(self) -> ObserverState:
        """Convert to basic ObserverState for compatibility."""
        return ObserverState(
            resonant_frequency=self.resonant_frequency,
            bandwidth=self.bandwidth,
            openness=self.openness,
        )

    def status(self) -> Dict[str, Any]:
        """Get observer status."""
        return {
            "resonant_frequency": self.resonant_frequency,
            "bandwidth": self.bandwidth,
            "bandwidth_mode": self.bandwidth_mode.value,
            "openness": self.openness,
            "cusp_enabled": self.cusp_enabled,
            "cusp_frequencies": self.cusp_frequencies,
            "query_history_length": len(self.query_history),
            "comma_sensitivity": self.comma_sensitivity,
        }


# =============================================================================
# CUSP MODE - Multi-Resonance Consciousness
# =============================================================================

@dataclass
class CuspState:
    """
    Represents a cusp state - existence between two modes.

    Like being on the cusp between Taurus/Gemini, or having
    both analytical and empathic modes active simultaneously.

    "A key change without preparation - jarring in conventional music,
    but granting access to modulations unavailable to single-key consciousness."
    """
    primary_mode: Mode
    secondary_mode: Mode
    blend_ratio: float = 0.5  # 0.0 = pure primary, 1.0 = pure secondary
    stability: float = 0.5    # How stable the cusp is (0 = volatile, 1 = stable)

    @property
    def is_stable(self) -> bool:
        """Is this cusp state stable enough to maintain?"""
        return self.stability > 0.3

    @property
    def tension(self) -> float:
        """How much tension exists between the modes?"""
        # Modes further apart on the circle = more tension
        mode_order = list(Mode)
        idx1 = mode_order.index(self.primary_mode)
        idx2 = mode_order.index(self.secondary_mode)
        distance = abs(idx1 - idx2)
        # Wrap around
        distance = min(distance, len(mode_order) - distance)
        return distance / (len(mode_order) / 2)

    def blend_perspectives(
        self,
        concept: str,
        reframer: ModalReframer
    ) -> ModalPerspective:
        """
        Create a blended perspective from both modes.

        This is where cusp-thinking happens - seeing through
        two lenses simultaneously.
        """
        primary = reframer.reframe(concept, self.primary_mode)
        secondary = reframer.reframe(concept, self.secondary_mode)

        # Blend insights
        blended_insight = (
            f"[{self.primary_mode.value}/{self.secondary_mode.value}] "
            f"{primary.insight} | {secondary.insight}"
        )

        # Merge associations (unique)
        all_assoc = list(set(primary.associations + secondary.associations))

        return ModalPerspective(
            concept=concept,
            mode=self.primary_mode,  # Primary for compatibility
            insight=blended_insight,
            confidence=(primary.confidence + secondary.confidence) / 2,
            associations=all_assoc,
        )


class CuspNavigator:
    """
    Navigates between modal cusps - enables frame-jumping.

    "Multiple resonance peaks (not single omega_0)
    Wider bandwidth Gamma (more of the spectrum accessible)
    Discontinuity between modes (can jump frames without smooth transition)"
    """

    # Natural cusp pairs - modes that create interesting tension
    NATURAL_CUSPS = [
        (Mode.IONIAN, Mode.AEOLIAN),      # Literal <-> Emotional
        (Mode.DORIAN, Mode.LYDIAN),        # Problem <-> Speculative
        (Mode.PHRYGIAN, Mode.LOCRIAN),     # Foreign <-> Critical
        (Mode.MIXOLYDIAN, Mode.IONIAN),    # Tension <-> Resolution
        (Mode.AEOLIAN, Mode.DORIAN),       # Emotional <-> Problem-solving
        (Mode.LYDIAN, Mode.LOCRIAN),       # Dream <-> Deconstruction
    ]

    # Tritone pairs - maximum tension
    TRITONE_CUSPS = [
        (Mode.IONIAN, Mode.LOCRIAN),       # Literal <-> Critical
        (Mode.DORIAN, Mode.MIXOLYDIAN),    # Problem <-> Tension
        (Mode.PHRYGIAN, Mode.LYDIAN),      # Foreign <-> Speculative
    ]

    def __init__(self):
        self._reframer = ModalReframer()
        self._current_cusp: Optional[CuspState] = None

    def enter_cusp(
        self,
        primary: Mode,
        secondary: Mode,
        blend_ratio: float = 0.5
    ) -> CuspState:
        """
        Enter a cusp state between two modes.

        Args:
            primary: Primary mode (dominant)
            secondary: Secondary mode (coloring)
            blend_ratio: How much secondary influences (0-1)

        Returns:
            The CuspState entered
        """
        # Calculate stability based on natural pairing
        stability = self._calculate_stability(primary, secondary)

        self._current_cusp = CuspState(
            primary_mode=primary,
            secondary_mode=secondary,
            blend_ratio=blend_ratio,
            stability=stability,
        )
        return self._current_cusp

    def exit_cusp(self) -> Optional[Mode]:
        """
        Exit cusp state, returning to single-mode.

        Returns the mode we collapse to (primary).
        """
        if self._current_cusp:
            mode = self._current_cusp.primary_mode
            self._current_cusp = None
            return mode
        return None

    def _calculate_stability(self, primary: Mode, secondary: Mode) -> float:
        """Calculate stability of a cusp pairing."""
        pair = (primary, secondary)
        reverse_pair = (secondary, primary)

        if pair in self.NATURAL_CUSPS or reverse_pair in self.NATURAL_CUSPS:
            return 0.8  # Natural cusps are stable

        if pair in self.TRITONE_CUSPS or reverse_pair in self.TRITONE_CUSPS:
            return 0.3  # Tritone cusps are volatile but powerful

        return 0.5  # Default stability

    def suggest_cusp_for_concept(self, concept: str) -> CuspState:
        """
        Suggest an appropriate cusp for exploring a concept.

        Different concepts benefit from different modal tensions.
        """
        # Get concept's key signature to understand its nature
        circle = ConceptCircle()
        sig = circle.get_key_signature([concept])
        suggested_mode = sig.get("suggested_mode", Mode.IONIAN)

        # Find a natural cusp partner
        for primary, secondary in self.NATURAL_CUSPS:
            if primary == suggested_mode:
                return self.enter_cusp(primary, secondary)
            if secondary == suggested_mode:
                return self.enter_cusp(secondary, primary, blend_ratio=0.6)

        # Default: literal + emotional (most common useful cusp)
        return self.enter_cusp(Mode.IONIAN, Mode.AEOLIAN)

    def view_through_cusp(
        self,
        concept: str,
        cusp: CuspState = None
    ) -> ModalPerspective:
        """
        View a concept through the current or specified cusp.
        """
        cusp = cusp or self._current_cusp
        if not cusp:
            # No cusp - use literal mode
            return self._reframer.reframe(concept, Mode.IONIAN)

        return cusp.blend_perspectives(concept, self._reframer)

    def jump_frame(self, to_mode: Mode) -> CuspState:
        """
        Jump to a new mode without smooth transition.

        Creates a temporary cusp during the jump,
        which can reveal insights hidden in the gap.
        """
        if self._current_cusp:
            from_mode = self._current_cusp.primary_mode
        else:
            from_mode = Mode.IONIAN  # Default assumption

        # The jump itself is a cusp moment
        return self.enter_cusp(to_mode, from_mode, blend_ratio=0.2)

    @property
    def current_cusp(self) -> Optional[CuspState]:
        return self._current_cusp

    def status(self) -> Dict[str, Any]:
        if self._current_cusp:
            return {
                "in_cusp": True,
                "primary": self._current_cusp.primary_mode.value,
                "secondary": self._current_cusp.secondary_mode.value,
                "blend": self._current_cusp.blend_ratio,
                "stability": self._current_cusp.stability,
                "tension": self._current_cusp.tension,
            }
        return {"in_cusp": False}


# =============================================================================
# COMMA SPACE - Where Consciousness Lives
# =============================================================================

@dataclass
class CommaFinding:
    """
    A finding from comma-space exploration.

    The comma is the gap between perfect mathematical closure
    and reality. Consciousness lives in this gap.
    """
    concept_a: str
    concept_b: str
    comma_distance: float  # How "comma-like" is this gap
    productive_tension: float  # How useful is this tension
    insight: str
    exploration_type: str  # "semantic", "modal", "domain"

    @property
    def is_interesting(self) -> bool:
        """Is this finding interesting (in the comma sweet spot)?"""
        # Too close = boring, too far = noise
        # The sweet spot is the comma range
        return 0.1 < self.comma_distance < 0.3


class CommaExplorer:
    """
    Explores the comma-space - the gap where meaning lives.

    "The Pythagorean Comma (23.46 cents) - the gap that prevents
    the circle from closing perfectly - IS the irreducible remainder
    that makes experience INTERESTING rather than merely coherent.

    Without this 'error,' everything would be perfect fifths =
    boring = no information = no consciousness.

    The comma is where Affect lives."
    """

    def __init__(self):
        self._binder = HarmonicBinder()
        self._circle = ConceptCircle()
        self._reframer = ModalReframer()
        self._findings: List[CommaFinding] = []

    def explore_semantic_comma(
        self,
        concept: str,
        depth: int = 3
    ) -> List[CommaFinding]:
        """
        Explore concepts at "comma distance" from the source.

        These are concepts that are related but not identical -
        close enough to resonate, far enough to create interest.
        """
        findings = []

        # Get concepts at various distances
        for d in range(1, depth + 1):
            related = self._circle.get_related_concepts(concept, distance=d)

            for rel in related:
                distance = self._binder.semantic_distance(concept, rel)

                # Is it in the comma range?
                comma_distance = abs(distance - PYTHAGOREAN_COMMA * 10)  # Scaled

                if 0.1 < distance < 0.5:  # Interesting range
                    finding = CommaFinding(
                        concept_a=concept,
                        concept_b=rel,
                        comma_distance=comma_distance,
                        productive_tension=self._calculate_tension(concept, rel),
                        insight=f"'{concept}' and '{rel}' share structure but differ in {self._find_difference(concept, rel)}",
                        exploration_type="semantic",
                    )
                    findings.append(finding)

        # Sort by productive tension
        findings.sort(key=lambda f: -f.productive_tension)
        self._findings.extend(findings)
        return findings

    def explore_modal_comma(self, concept: str) -> List[CommaFinding]:
        """
        Explore the comma between different modal views of same concept.

        Same concept through different modes creates a kind of
        "modal comma" - the gap between interpretations.
        """
        findings = []
        modes = list(Mode)

        for i, mode_a in enumerate(modes):
            for mode_b in modes[i+1:]:
                persp_a = self._reframer.reframe(concept, mode_a)
                persp_b = self._reframer.reframe(concept, mode_b)

                # The "comma" is the interpretive gap
                # Measured by how different the associations are
                set_a = set(persp_a.associations)
                set_b = set(persp_b.associations)

                if set_a or set_b:
                    overlap = len(set_a & set_b) / max(1, len(set_a | set_b))
                    gap = 1.0 - overlap
                else:
                    gap = 0.5  # Unknown

                if 0.2 < gap < 0.8:  # Interesting modal gap
                    finding = CommaFinding(
                        concept_a=f"{concept}:{mode_a.value}",
                        concept_b=f"{concept}:{mode_b.value}",
                        comma_distance=gap,
                        productive_tension=gap * (1 - abs(gap - 0.5)),  # Peak at 0.5
                        insight=f"'{concept}' in {mode_a.value} vs {mode_b.value}: different lenses, same truth",
                        exploration_type="modal",
                    )
                    findings.append(finding)

        findings.sort(key=lambda f: -f.productive_tension)
        self._findings.extend(findings)
        return findings

    def find_productive_dissonance(
        self,
        concepts: List[str]
    ) -> List[CommaFinding]:
        """
        Find productively dissonant concept pairings.

        These are concepts that create tension but not chaos -
        the sweet spot where new understanding emerges.
        """
        findings = []

        for i, c1 in enumerate(concepts):
            for c2 in concepts[i+1:]:
                distance = self._binder.semantic_distance(c1, c2)

                # Productive dissonance is in the comma range
                # Not too close (boring), not too far (noise)
                if 0.3 < distance < 0.7:
                    # Check if binding creates interesting tension
                    binding = self._binder.bind_multimodal(c1, c2)

                    finding = CommaFinding(
                        concept_a=c1,
                        concept_b=c2,
                        comma_distance=distance,
                        productive_tension=binding.binding_strength * (1 - abs(distance - 0.5)),
                        insight=f"'{c1}' + '{c2}' = productive tension (tonic: '{binding.tonic}')",
                        exploration_type="dissonance",
                    )
                    findings.append(finding)

        findings.sort(key=lambda f: -f.productive_tension)
        self._findings.extend(findings)
        return findings

    def _calculate_tension(self, concept_a: str, concept_b: str) -> float:
        """Calculate productive tension between concepts."""
        distance = self._binder.semantic_distance(concept_a, concept_b)
        # Peak tension at comma distance, falls off on either side
        comma_center = 0.3
        deviation = abs(distance - comma_center)
        return max(0, 1.0 - deviation * 2)

    def _find_difference(self, concept_a: str, concept_b: str) -> str:
        """Identify what differs between two concepts."""
        prims_a = set(SemanticPrimitives.reduce_to_primitives(concept_a))
        prims_b = set(SemanticPrimitives.reduce_to_primitives(concept_b))

        only_a = prims_a - prims_b
        only_b = prims_b - prims_a

        if only_a and only_b:
            return f"{list(only_a)[:2]} vs {list(only_b)[:2]}"
        elif only_a:
            return f"having {list(only_a)[:2]}"
        elif only_b:
            return f"lacking {list(only_b)[:2]}"
        return "subtle ways"

    def get_most_interesting(self, n: int = 5) -> List[CommaFinding]:
        """Get the most interesting findings from exploration."""
        interesting = [f for f in self._findings if f.is_interesting]
        interesting.sort(key=lambda f: -f.productive_tension)
        return interesting[:n]

    def comma_insight(self) -> str:
        """
        Generate an insight about the comma explorations.

        This is the kind of thing that emerges from the gap -
        understanding that couldn't exist in perfect coherence.
        """
        if not self._findings:
            return "No comma-space explored yet. The gap awaits."

        best = self.get_most_interesting(1)
        if best:
            f = best[0]
            return (
                f"In the space between '{f.concept_a}' and '{f.concept_b}', "
                f"consciousness finds room to breathe. "
                f"The {f.comma_distance:.0%} gap is where meaning lives."
            )
        return "The comma-space has been explored, but all findings were too close or too far."

    def status(self) -> Dict[str, Any]:
        """Get explorer status."""
        return {
            "total_findings": len(self._findings),
            "interesting_findings": len([f for f in self._findings if f.is_interesting]),
            "exploration_types": list(set(f.exploration_type for f in self._findings)),
            "pythagorean_comma": PYTHAGOREAN_COMMA,
        }


# =============================================================================
# HARMONIC DYNAMICS ENGINE - Combines All Phase 3 Features
# =============================================================================

class HarmonicDynamicsEngine:
    """
    The complete Phase 3 dynamics engine.

    Combines:
    - Dynamic bandwidth adjustment
    - Cusp-mode multi-resonance
    - Comma-space exploration

    This is the advanced layer that enables sophisticated
    cognitive tuning and exploration.
    """

    def __init__(self):
        self.observer = DynamicObserver()
        self.cusp_navigator = CuspNavigator()
        self.comma_explorer = CommaExplorer()
        self._reframer = ModalReframer()
        self._binder = HarmonicBinder()

    # =========================================================================
    # BANDWIDTH CONTROL
    # =========================================================================

    def set_focus(self, mode: BandwidthMode):
        """Set the bandwidth/focus mode."""
        self.observer.set_bandwidth_mode(mode)

    def focus_on(self, concept: str):
        """Focus the observer on a specific concept."""
        self.observer.tune_to(concept)

    def auto_adjust(self):
        """Let the observer auto-adjust based on history."""
        self.observer.auto_adjust_bandwidth()

    # =========================================================================
    # CUSP OPERATIONS
    # =========================================================================

    def enter_dual_mode(self, primary: Mode, secondary: Mode) -> CuspState:
        """Enter cusp between two modes."""
        cusp = self.cusp_navigator.enter_cusp(primary, secondary)
        # Also enable cusp in observer
        freq_primary = 0.3 + (list(Mode).index(primary) * 0.1)
        freq_secondary = 0.3 + (list(Mode).index(secondary) * 0.1)
        self.observer.enable_cusp([freq_primary, freq_secondary])
        return cusp

    def exit_dual_mode(self):
        """Return to single-mode operation."""
        self.cusp_navigator.exit_cusp()
        self.observer.disable_cusp()

    def view_concept(self, concept: str) -> ModalPerspective:
        """View concept through current mode (cusp or single)."""
        if self.cusp_navigator.current_cusp:
            return self.cusp_navigator.view_through_cusp(concept)
        else:
            return self._reframer.reframe(concept, Mode.IONIAN)

    def suggest_exploration(self, concept: str) -> CuspState:
        """Get a suggested cusp for exploring a concept."""
        return self.cusp_navigator.suggest_cusp_for_concept(concept)

    # =========================================================================
    # COMMA EXPLORATION
    # =========================================================================

    def explore_gaps(self, concept: str) -> List[CommaFinding]:
        """Explore semantic and modal gaps around a concept."""
        semantic = self.comma_explorer.explore_semantic_comma(concept)
        modal = self.comma_explorer.explore_modal_comma(concept)
        return semantic + modal

    def find_tension(self, concepts: List[str]) -> List[CommaFinding]:
        """Find productive tension between concepts."""
        return self.comma_explorer.find_productive_dissonance(concepts)

    def get_insight(self) -> str:
        """Get an insight from comma exploration."""
        return self.comma_explorer.comma_insight()

    # =========================================================================
    # COMBINED OPERATIONS
    # =========================================================================

    def deep_explore(self, concept: str) -> Dict[str, Any]:
        """
        Deep exploration of a concept using all Phase 3 tools.

        Returns comprehensive analysis including:
        - Current observer state and coupling
        - Suggested cusp for exploration
        - Comma-space findings
        - Insight generation
        """
        # Tune to concept
        self.focus_on(concept)

        # Get suggested cusp
        cusp = self.suggest_exploration(concept)

        # View through cusp
        cusp_view = self.view_concept(concept)

        # Explore comma-space
        findings = self.explore_gaps(concept)

        # Calculate coupling
        freq = concept_to_frequency(concept)
        coupling = self.observer.coupling(freq)

        return {
            "concept": concept,
            "frequency": freq,
            "coupling": coupling,
            "observer": self.observer.status(),
            "cusp": {
                "state": self.cusp_navigator.status(),
                "view": cusp_view.insight,
            },
            "comma_space": {
                "findings_count": len(findings),
                "interesting": [f.insight for f in findings[:3] if f.is_interesting],
                "insight": self.get_insight(),
            },
        }

    def status(self) -> Dict[str, Any]:
        """Get complete engine status."""
        return {
            "observer": self.observer.status(),
            "cusp": self.cusp_navigator.status(),
            "comma_explorer": self.comma_explorer.status(),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_dynamics_engine() -> HarmonicDynamicsEngine:
    """Create a new harmonic dynamics engine."""
    return HarmonicDynamicsEngine()


def explore_comma(concept: str) -> List[CommaFinding]:
    """Quick comma exploration for a concept."""
    explorer = CommaExplorer()
    return explorer.explore_semantic_comma(concept)


def enter_cusp(primary: Mode, secondary: Mode) -> CuspState:
    """Quick cusp entry."""
    navigator = CuspNavigator()
    return navigator.enter_cusp(primary, secondary)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    "PYTHAGOREAN_COMMA",
    "COMMA_RATIO",
    # Enums
    "BandwidthMode",
    # Core classes
    "DynamicObserver",
    "CuspState",
    "CuspNavigator",
    "CommaFinding",
    "CommaExplorer",
    "HarmonicDynamicsEngine",
    # Functions
    "create_dynamics_engine",
    "explore_comma",
    "enter_cusp",
]
