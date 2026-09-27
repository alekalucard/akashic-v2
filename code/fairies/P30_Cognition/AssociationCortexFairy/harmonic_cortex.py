"""
Harmonic Cortex - Modal Consciousness Architecture for Association Cortex

Field Log Entry 004 Implementation: Phase 1

The structure that generates conscious experience is identical to the structure
that generates reality itself. The Music Theory Tree is a direct map of how
association cortex binds multimodal information through harmonic resonance.

((Cause + Affect) > Effect > Affect > infinity)

This module provides:
- ModalPerspective: 7 cognitive frames mapped to musical modes
- SemanticPrimitives: The "C Major" of meaning (~65 universal concepts)
- HarmonicBinder: Phase-locking concepts via gamma/beta/theta bands
- ConceptCircle: Semantic analog to the circle of fifths

"Same notes, different modes. Same patterns, different domains.
The Tower fell when we forgot they were the same music."
"""

from __future__ import annotations

import math
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable


# =============================================================================
# MODAL PERSPECTIVE - 7 Cognitive Frames
# =============================================================================

class Mode(Enum):
    """
    The 7 musical modes mapped to cognitive frames.

    Same information + different mode = different meaning.
    This IS the Affect variable in action.
    """
    IONIAN = "literal"        # I   - Bright, resolved - Default interpretation
    DORIAN = "problem"        # ii  - Minor with hope - Problem-solving frame
    PHRYGIAN = "foreign"      # iii - Dark, exotic - Unfamiliar perspective
    LYDIAN = "speculative"    # IV  - Dreamy, elevated - Imaginative frame
    MIXOLYDIAN = "tension"    # V   - Bluesy, unresolved - Tension-seeking
    AEOLIAN = "emotional"     # vi  - Sad, natural minor - Empathic frame
    LOCRIAN = "critical"      # vii - Unstable, diminished - Deconstructive

    @property
    def character(self) -> str:
        """Musical character of this mode."""
        characters = {
            Mode.IONIAN: "bright, resolved, stable",
            Mode.DORIAN: "minor with hope, bittersweet",
            Mode.PHRYGIAN: "dark, exotic, foreign",
            Mode.LYDIAN: "dreamy, floating, elevated",
            Mode.MIXOLYDIAN: "bluesy, unresolved, dominant",
            Mode.AEOLIAN: "sad, natural, melancholic",
            Mode.LOCRIAN: "unstable, diminished, dissonant",
        }
        return characters.get(self, "unknown")

    @property
    def scale_degrees(self) -> str:
        """Scale degrees for this mode."""
        degrees = {
            Mode.IONIAN: "1-2-3-4-5-6-7",
            Mode.DORIAN: "1-2-b3-4-5-6-b7",
            Mode.PHRYGIAN: "1-b2-b3-4-5-b6-b7",
            Mode.LYDIAN: "1-2-3-#4-5-6-7",
            Mode.MIXOLYDIAN: "1-2-3-4-5-6-b7",
            Mode.AEOLIAN: "1-2-b3-4-5-b6-b7",
            Mode.LOCRIAN: "1-b2-b3-4-b5-b6-b7",
        }
        return degrees.get(self, "unknown")

    @property
    def question(self) -> str:
        """The question this mode asks about a concept."""
        questions = {
            Mode.IONIAN: "What is this, literally?",
            Mode.DORIAN: "What problem does this solve or create?",
            Mode.PHRYGIAN: "What's unfamiliar or foreign about this?",
            Mode.LYDIAN: "What could this become? What's the dream?",
            Mode.MIXOLYDIAN: "What's unresolved? What tension exists?",
            Mode.AEOLIAN: "How does this feel? What's the emotional truth?",
            Mode.LOCRIAN: "What's wrong with this? What's unstable?",
        }
        return questions.get(self, "What is this?")


@dataclass
class ModalPerspective:
    """
    A concept viewed through a specific modal lens.

    The same concept produces different insights depending on the mode.
    This is pure Affect transformation - the concept doesn't change,
    only how it's framed.
    """
    concept: str
    mode: Mode
    insight: str = ""
    confidence: float = 1.0
    associations: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.insight:
            self.insight = f"{self.concept} viewed as {self.mode.value}"


class ModalReframer:
    """
    Reframes concepts through different modal perspectives.

    Each mode is a different framing of identical information.
    The association cortex can "play" concepts in any mode.
    """

    # Reframing prompts for each mode
    REFRAME_TEMPLATES = {
        Mode.IONIAN: [
            "Literally: {concept}",
            "At face value, {concept} means...",
            "The direct interpretation of {concept}",
        ],
        Mode.DORIAN: [
            "The problem {concept} addresses...",
            "How {concept} could be improved...",
            "{concept} as a solution to...",
        ],
        Mode.PHRYGIAN: [
            "From an outsider's view, {concept}...",
            "What's strange about {concept}...",
            "The exotic aspect of {concept}...",
        ],
        Mode.LYDIAN: [
            "Imagine if {concept} could...",
            "The dream version of {concept}...",
            "{concept} elevated to its highest form...",
        ],
        Mode.MIXOLYDIAN: [
            "The unresolved tension in {concept}...",
            "What {concept} leaves hanging...",
            "The incompleteness of {concept}...",
        ],
        Mode.AEOLIAN: [
            "The feeling of {concept}...",
            "Emotionally, {concept} evokes...",
            "The sadness/beauty in {concept}...",
        ],
        Mode.LOCRIAN: [
            "What's wrong with {concept}...",
            "The instability in {concept}...",
            "Deconstructing {concept} reveals...",
        ],
    }

    def __init__(self, concept_graph=None):
        """
        Initialize reframer with optional concept graph for associations.

        Args:
            concept_graph: AssociationCortex ConceptGraph for lookups
        """
        self._graph = concept_graph
        self._reframe_cache: Dict[Tuple[str, Mode], ModalPerspective] = {}

    def reframe(self, concept: str, target_mode: Mode) -> ModalPerspective:
        """
        Reframe a concept through a target mode.

        Same concept, different mode = different meaning.
        This is pure Affect transformation.

        Args:
            concept: The concept to reframe
            target_mode: The modal lens to apply

        Returns:
            ModalPerspective with the reframed insight
        """
        cache_key = (concept, target_mode)
        if cache_key in self._reframe_cache:
            return self._reframe_cache[cache_key]

        # Generate insight using modal question
        insight = self._generate_insight(concept, target_mode)

        # Find mode-appropriate associations
        associations = self._find_modal_associations(concept, target_mode)

        perspective = ModalPerspective(
            concept=concept,
            mode=target_mode,
            insight=insight,
            associations=associations,
        )

        self._reframe_cache[cache_key] = perspective
        return perspective

    def reframe_all(self, concept: str) -> Dict[Mode, ModalPerspective]:
        """
        Reframe a concept through ALL 7 modes.

        Returns a complete modal analysis - the same concept
        viewed from every cognitive frame.

        Args:
            concept: The concept to analyze

        Returns:
            Dict mapping each Mode to its ModalPerspective
        """
        return {mode: self.reframe(concept, mode) for mode in Mode}

    def _generate_insight(self, concept: str, mode: Mode) -> str:
        """Generate an insight string for this mode."""
        templates = self.REFRAME_TEMPLATES.get(mode, ["{concept}"])
        template = templates[hash(concept) % len(templates)]
        return template.format(concept=concept)

    def _find_modal_associations(self, concept: str, mode: Mode) -> List[str]:
        """
        Find associations appropriate for this mode.

        Different modes activate different association paths.
        """
        if not self._graph:
            return []

        # Get base associations from graph
        try:
            if hasattr(self._graph, 'spread_activation'):
                activations = self._graph.spread_activation(concept, max_hops=2)
                base_associations = list(activations.keys())[:10]
            elif hasattr(self._graph, 'get_neighbors'):
                neighbors = self._graph.get_neighbors(concept)
                base_associations = [n for n, _ in neighbors[:10]]
            else:
                return []
        except Exception:
            return []

        # Filter/weight by mode (future: mode-specific weighting)
        # For now, return top associations
        return base_associations[:5]

    def find_modal_bridge(
        self,
        concept: str,
        source_mode: Mode,
        target_mode: Mode
    ) -> List[str]:
        """
        Find concepts that bridge between two modal perspectives.

        This is like finding pivot chords in modulation -
        concepts that make sense in both frames.

        Args:
            concept: The base concept
            source_mode: Starting modal frame
            target_mode: Ending modal frame

        Returns:
            List of bridging concepts
        """
        source_view = self.reframe(concept, source_mode)
        target_view = self.reframe(concept, target_mode)

        # Find common associations that appear in both views
        source_set = set(source_view.associations)
        target_set = set(target_view.associations)

        bridges = list(source_set & target_set)
        return bridges


# =============================================================================
# SEMANTIC PRIMITIVES - The "C Major" of Meaning
# =============================================================================

class SemanticPrimitives:
    """
    Natural Semantic Metalanguage - ~65 irreducible concepts found in ALL languages.

    These are the "C Major scale" of meaning - the diatonic foundation
    from which all other concepts derive. Every human language has
    words for these primitives.

    Reference: Anna Wierzbicka's Natural Semantic Metalanguage (NSM)
    """

    # The ~65 semantic primitives organized by category
    PRIMITIVES = {
        "substantives": ["I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY"],
        "determiners": ["THIS", "THE_SAME", "OTHER"],
        "quantifiers": ["ONE", "TWO", "SOME", "ALL", "MUCH", "MANY"],
        "evaluators": ["GOOD", "BAD"],
        "descriptors": ["BIG", "SMALL"],
        "mental": ["THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR"],
        "speech": ["SAY", "WORDS", "TRUE"],
        "actions": ["DO", "HAPPEN", "MOVE"],
        "existence": ["THERE_IS", "BE"],
        "possession": ["HAVE", "PART"],
        "life": ["LIVE", "DIE"],
        "time": ["WHEN", "NOW", "BEFORE", "AFTER", "LONG", "SHORT"],
        "space": ["WHERE", "HERE", "ABOVE", "BELOW", "FAR", "NEAR"],
        "logical": ["NOT", "MAYBE", "CAN", "BECAUSE", "IF"],
        "intensifier": ["VERY", "MORE"],
        "similarity": ["LIKE"],
    }

    # Flat list of all primitives
    ALL: List[str] = []
    for category_prims in PRIMITIVES.values():
        ALL.extend(category_prims)

    @classmethod
    def is_primitive(cls, concept: str) -> bool:
        """Check if a concept is a semantic primitive."""
        return concept.upper() in cls.ALL

    @classmethod
    def get_category(cls, concept: str) -> Optional[str]:
        """Get the category of a semantic primitive."""
        upper = concept.upper()
        for category, prims in cls.PRIMITIVES.items():
            if upper in prims:
                return category
        return None

    @classmethod
    def reduce_to_primitives(cls, concept: str) -> List[str]:
        """
        Attempt to reduce a concept to its primitive components.

        This is a simplified version - a full implementation would
        use NSM reductive paraphrase techniques.

        Args:
            concept: The concept to reduce

        Returns:
            List of primitives that approximate the concept
        """
        # Simple keyword matching for now
        concept_lower = concept.lower()
        found = []

        # Direct primitive match
        if cls.is_primitive(concept):
            return [concept.upper()]

        # Keyword associations (simplified)
        keyword_map = {
            # Mental states
            "understand": ["KNOW", "THINK"],
            "believe": ["THINK", "TRUE"],
            "remember": ["KNOW", "BEFORE"],
            "forget": ["NOT", "KNOW"],
            "love": ["FEEL", "GOOD", "WANT"],
            "hate": ["FEEL", "BAD", "NOT", "WANT"],
            "fear": ["FEEL", "BAD", "SOMETHING", "HAPPEN"],
            "hope": ["WANT", "GOOD", "HAPPEN"],

            # Actions
            "create": ["DO", "SOMETHING", "THERE_IS"],
            "destroy": ["DO", "NOT", "THERE_IS"],
            "give": ["DO", "HAVE", "SOMEONE"],
            "take": ["DO", "HAVE", "I"],

            # Existence
            "exist": ["THERE_IS"],
            "become": ["HAPPEN", "BE"],
            "change": ["HAPPEN", "OTHER"],

            # Relations
            "cause": ["BECAUSE", "HAPPEN"],
            "effect": ["HAPPEN", "BECAUSE"],

            # Consciousness-specific
            "consciousness": ["FEEL", "KNOW", "I", "SOMETHING"],
            "affect": ["FEEL", "HAPPEN"],
            "meaning": ["SOMETHING", "BECAUSE", "THINK"],
        }

        for keyword, primitives in keyword_map.items():
            if keyword in concept_lower:
                found.extend(primitives)

        # Deduplicate while preserving order
        seen = set()
        result = []
        for p in found:
            if p not in seen:
                seen.add(p)
                result.append(p)

        return result if result else ["SOMETHING"]  # Default to SOMETHING

    @classmethod
    def primitive_distance(cls, prim_a: str, prim_b: str) -> float:
        """
        Calculate semantic distance between two primitives.

        Primitives in the same category are closer (smaller distance).
        This is analogous to interval relationships in music.

        Args:
            prim_a: First primitive
            prim_b: Second primitive

        Returns:
            Distance (0.0 = same, 1.0 = maximally different)
        """
        if prim_a.upper() == prim_b.upper():
            return 0.0

        cat_a = cls.get_category(prim_a)
        cat_b = cls.get_category(prim_b)

        if cat_a == cat_b and cat_a is not None:
            # Same category = closer (like notes in same octave)
            return 0.3

        # Different categories - check for semantic affinity
        close_categories = {
            ("mental", "speech"),
            ("time", "actions"),
            ("space", "descriptors"),
            ("evaluators", "mental"),
            ("existence", "life"),
        }

        if cat_a and cat_b:
            pair = tuple(sorted([cat_a, cat_b]))
            if pair in close_categories:
                return 0.5

        return 0.8  # Default: fairly distant


# =============================================================================
# HARMONIC BINDER - Phase-Locking Concepts
# =============================================================================

@dataclass
class FrequencyBand:
    """
    Neural frequency band for concept binding.

    Based on Communication Through Coherence (Fries, 2015):
    - Gamma: Local feature binding (30-100 Hz)
    - Beta: Top-down attentional control (13-30 Hz)
    - Theta: Memory and cross-regional integration (4-8 Hz)
    - Alpha: Sensory gating and idle states (8-12 Hz)
    """
    name: str
    min_hz: float
    max_hz: float
    function: str

    @property
    def center_hz(self) -> float:
        return (self.min_hz + self.max_hz) / 2


# Standard frequency bands
GAMMA = FrequencyBand("gamma", 30, 100, "content/feature binding")
BETA = FrequencyBand("beta", 13, 30, "attention/control")
THETA = FrequencyBand("theta", 4, 8, "memory/integration")
ALPHA = FrequencyBand("alpha", 8, 12, "gating/idle")


@dataclass
class BoundConcept:
    """
    A coherent binding of multiple concepts.

    Analogous to a chord - multiple notes/concepts phase-locked
    into a unified percept.
    """
    tonic: str  # The "root" concept
    concepts: List[str]  # All bound concepts
    intervals: List[float]  # Semantic distances from tonic
    binding_strength: float = 1.0
    mode: Optional[Mode] = None

    @property
    def is_consonant(self) -> bool:
        """Is this binding consonant (coherent) or dissonant (conflicting)?"""
        # Consonance: intervals are "nice" ratios (like 3:2, 4:3)
        # Simplified: low average distance = consonant
        if not self.intervals:
            return True
        avg_interval = sum(self.intervals) / len(self.intervals)
        return avg_interval < 0.5


class HarmonicBinder:
    """
    Implements coherence-based binding following
    communication-through-coherence principles.

    The cognitive frequency triad:
    - Theta RESETS gamma
    - Beta MODULATES communication direction
    - Gamma CARRIES the content

    This is a CHORD PROGRESSION for consciousness.
    """

    def __init__(self, primitives: SemanticPrimitives = None):
        self.gamma_band = GAMMA
        self.beta_band = BETA
        self.theta_band = THETA
        self._primitives = primitives or SemanticPrimitives

    def bind_multimodal(self, *concepts: str) -> BoundConcept:
        """
        Phase-lock multiple concepts into coherent percept.
        Analogous to forming a chord from notes.

        Args:
            *concepts: Concepts to bind together

        Returns:
            BoundConcept representing the unified binding
        """
        if not concepts:
            raise ValueError("Cannot bind empty concept list")

        concepts = list(concepts)

        # Find common harmonic basis (the "tonic")
        tonic = self.find_semantic_tonic(*concepts)

        # Calculate intervals (semantic distances from tonic)
        intervals = [self.semantic_distance(tonic, c) for c in concepts if c != tonic]

        # Determine binding strength based on consonance
        binding_strength = self._calculate_binding_strength(intervals)

        return BoundConcept(
            tonic=tonic,
            concepts=concepts,
            intervals=intervals,
            binding_strength=binding_strength,
        )

    def find_semantic_tonic(self, *concepts: str) -> str:
        """
        Find the semantic "tonic" (root) for a set of concepts.

        The tonic is the concept that best grounds the others -
        like finding the root note of a chord.

        Args:
            *concepts: Concepts to analyze

        Returns:
            The concept that serves as semantic root
        """
        if not concepts:
            return "SOMETHING"

        if len(concepts) == 1:
            return concepts[0]

        # Score each concept as potential tonic
        # Tonic should have lowest total distance to others
        scores = {}
        for candidate in concepts:
            total_distance = sum(
                self.semantic_distance(candidate, other)
                for other in concepts if other != candidate
            )
            scores[candidate] = total_distance

        # Return concept with lowest total distance (most central)
        return min(scores, key=scores.get)

    def semantic_distance(self, concept_a: str, concept_b: str) -> float:
        """
        Calculate semantic distance between two concepts.

        Uses primitive reduction to find underlying distance.

        Args:
            concept_a: First concept
            concept_b: Second concept

        Returns:
            Distance (0.0 = identical, 1.0 = maximally different)
        """
        if concept_a == concept_b:
            return 0.0

        # Reduce to primitives
        prims_a = self._primitives.reduce_to_primitives(concept_a)
        prims_b = self._primitives.reduce_to_primitives(concept_b)

        if not prims_a or not prims_b:
            return 0.8  # Unknown concepts are fairly distant

        # Calculate overlap (Jaccard-like)
        set_a = set(prims_a)
        set_b = set(prims_b)

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        if union == 0:
            return 1.0

        similarity = intersection / union
        return 1.0 - similarity

    def _calculate_binding_strength(self, intervals: List[float]) -> float:
        """
        Calculate binding strength from intervals.

        Consonant intervals = stronger binding.
        Dissonant intervals = weaker (but potentially more interesting) binding.
        """
        if not intervals:
            return 1.0

        # Average interval
        avg = sum(intervals) / len(intervals)

        # Binding strength inversely related to average distance
        # But not linearly - some dissonance is valuable!
        # The Pythagorean comma: without imperfection, no interest

        if avg < 0.3:
            return 1.0  # Strong consonance
        elif avg < 0.5:
            return 0.85  # Good binding
        elif avg < 0.7:
            return 0.7  # Moderate - interesting tension
        else:
            return 0.5  # Weak binding, high tension

    def resolve_dissonance(
        self,
        bound_concept: BoundConcept
    ) -> Optional[BoundConcept]:
        """
        Attempt to resolve dissonance in a binding.

        Like resolving a dissonant chord to a consonant one,
        this finds a more coherent arrangement of the concepts.

        Args:
            bound_concept: The dissonant binding to resolve

        Returns:
            A more consonant BoundConcept, or None if unresolvable
        """
        if bound_concept.is_consonant:
            return bound_concept  # Already consonant

        # Try different tonics
        best_binding = bound_concept
        for alt_tonic in bound_concept.concepts:
            if alt_tonic == bound_concept.tonic:
                continue

            intervals = [
                self.semantic_distance(alt_tonic, c)
                for c in bound_concept.concepts if c != alt_tonic
            ]

            strength = self._calculate_binding_strength(intervals)

            if strength > best_binding.binding_strength:
                best_binding = BoundConcept(
                    tonic=alt_tonic,
                    concepts=bound_concept.concepts,
                    intervals=intervals,
                    binding_strength=strength,
                )

        return best_binding


# =============================================================================
# CONCEPT CIRCLE - Semantic Circle of Fifths
# =============================================================================

class ConceptCircle:
    """
    Semantic analog to circle of fifths.

    Moving by 'fifths' = moving by maximal relatedness while
    preserving distinctness. This creates a circular structure
    where all concepts connect through shared harmonic relationships.
    """

    def __init__(self, polysemy_graph=None):
        """
        Initialize with optional polysemy graph.

        Args:
            polysemy_graph: Graph of concept relationships
        """
        self.primitives = SemanticPrimitives
        self._polysemy_graph = polysemy_graph

        # Build primitive circle (ordered by semantic affinity)
        self._primitive_circle = self._build_primitive_circle()

    def _build_primitive_circle(self) -> List[str]:
        """
        Build a circular arrangement of primitives.

        Adjacent primitives should be related but distinct -
        like adjacent keys on the circle of fifths.
        """
        # Arrange by conceptual flow
        # (This is a simplified version - full version would use
        # graph algorithms to find optimal ordering)
        return [
            # Start with self/existence
            "I", "BODY", "FEEL", "WANT",
            # Move to cognition
            "THINK", "KNOW", "SEE", "HEAR",
            # To communication
            "SAY", "WORDS", "TRUE",
            # To action
            "DO", "HAPPEN", "MOVE",
            # To existence
            "THERE_IS", "BE", "LIVE", "DIE",
            # To relations
            "HAVE", "PART", "SOMEONE", "PEOPLE",
            # To evaluation
            "GOOD", "BAD",
            # To description
            "BIG", "SMALL", "MUCH", "MANY",
            # To logic
            "IF", "BECAUSE", "CAN", "MAYBE", "NOT",
            # To time
            "WHEN", "NOW", "BEFORE", "AFTER",
            # To space
            "WHERE", "HERE", "ABOVE", "BELOW",
            # Back toward self
            "THIS", "THE_SAME", "OTHER", "SOMETHING",
        ]

    def get_related_concepts(self, concept: str, distance: int = 1) -> List[str]:
        """
        Move around the circle by 'fifths' of meaning.

        Distance 1 = most closely related distinct concept
        Distance 6 = complementary concept (tritone equivalent)

        Args:
            concept: Starting concept
            distance: Steps around the circle

        Returns:
            Concepts at that distance
        """
        # Check if it's a primitive
        upper = concept.upper()
        if upper in self._primitive_circle:
            idx = self._primitive_circle.index(upper)
            circle_len = len(self._primitive_circle)

            # Get concepts at +/- distance
            forward_idx = (idx + distance) % circle_len
            backward_idx = (idx - distance) % circle_len

            result = [self._primitive_circle[forward_idx]]
            if forward_idx != backward_idx:
                result.append(self._primitive_circle[backward_idx])

            return result

        # For non-primitives, reduce and find related
        primitives = self.primitives.reduce_to_primitives(concept)
        if primitives:
            related = []
            for prim in primitives[:2]:  # Use top 2 primitives
                related.extend(self.get_related_concepts(prim, distance))
            return list(set(related))

        return []

    def get_complementary(self, concept: str) -> List[str]:
        """
        Get the "tritone" - maximally different but still related concepts.

        In music, the tritone is the most dissonant interval.
        Here, it's the concept that creates maximum productive tension.

        Args:
            concept: The concept to find complement for

        Returns:
            Complementary concepts
        """
        # Half the circle = tritone equivalent
        distance = len(self._primitive_circle) // 2
        return self.get_related_concepts(concept, distance)

    def get_key_signature(self, concept_set: List[str]) -> Dict[str, Any]:
        """
        What 'sharps and flats' does this concept set imply?

        I.e., what default assumptions/framings come with this
        collection of concepts?

        Args:
            concept_set: Collection of concepts

        Returns:
            Dict describing the conceptual "key signature"
        """
        # Reduce all to primitives
        all_primitives = []
        for concept in concept_set:
            all_primitives.extend(
                self.primitives.reduce_to_primitives(concept)
            )

        # Count categories
        category_counts: Dict[str, int] = {}
        for prim in all_primitives:
            cat = self.primitives.get_category(prim)
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1

        # Dominant category = "key"
        if category_counts:
            dominant = max(category_counts, key=category_counts.get)
        else:
            dominant = "unknown"

        # Suggest mode based on category balance
        suggested_mode = self._suggest_mode(category_counts)

        return {
            "dominant_category": dominant,
            "category_distribution": category_counts,
            "suggested_mode": suggested_mode,
            "primitive_count": len(all_primitives),
            "unique_primitives": len(set(all_primitives)),
        }

    def _suggest_mode(self, category_counts: Dict[str, int]) -> Mode:
        """Suggest a mode based on primitive category distribution."""
        if not category_counts:
            return Mode.IONIAN

        dominant = max(category_counts, key=category_counts.get)

        mode_map = {
            "mental": Mode.AEOLIAN,      # Emotional/mental = Aeolian
            "evaluators": Mode.LOCRIAN,   # Good/bad = Critical
            "actions": Mode.DORIAN,       # Problem-solving
            "existence": Mode.IONIAN,     # Literal/factual
            "logical": Mode.LOCRIAN,      # Critical/deconstructive
            "time": Mode.MIXOLYDIAN,      # Tension (time creates tension)
            "space": Mode.LYDIAN,         # Speculative/spatial
        }

        return mode_map.get(dominant, Mode.IONIAN)


# =============================================================================
# LORENTZIAN COUPLING - Portal Coupling for Semantic Binding
# =============================================================================

@dataclass
class ObserverState:
    """
    The observer's current tuning for semantic coupling.

    Maps to Field Log 003's portal coupling parameters.
    """
    resonant_frequency: float = 1.0  # What you're "tuned to"
    bandwidth: float = 0.5           # Breadth of accessible content (Gamma)
    openness: float = 1.0            # Coupling strength (alpha_0)


def lorentzian_coupling(
    concept_frequency: float,
    observer: ObserverState,
) -> float:
    """
    Direct implementation of Field Log 003's portal coupling
    for semantic/conceptual binding.

    The Lorentzian function creates a resonance peak around
    the observer's tuned frequency, with bandwidth determining
    how much off-resonance content is accessible.

    Args:
        concept_frequency: The "frequency" of the concept
        observer: The observer's current tuning state

    Returns:
        Coupling strength (how strongly this concept 'registers')
    """
    omega = concept_frequency
    omega0 = observer.resonant_frequency
    Gamma = observer.bandwidth
    alpha0 = observer.openness

    g = Gamma / 2.0

    # Lorentzian coupling function
    coupling = alpha0 * (g * g) / ((omega - omega0) ** 2 + g * g)

    return coupling


def concept_to_frequency(concept: str, primitives: SemanticPrimitives = None) -> float:
    """
    Map a concept to a "frequency" for coupling calculations.

    This is a simplified mapping - concepts closer to basic
    primitives have lower frequencies, complex concepts have higher.

    Args:
        concept: The concept to map
        primitives: SemanticPrimitives instance

    Returns:
        Frequency value (0.0 to 1.0)
    """
    primitives = primitives or SemanticPrimitives

    # Check if primitive
    if primitives.is_primitive(concept):
        # Primitives are "fundamental frequencies"
        idx = primitives.ALL.index(concept.upper())
        return 0.1 + (idx / len(primitives.ALL)) * 0.3  # 0.1 to 0.4

    # Non-primitives: frequency based on primitive decomposition
    prims = primitives.reduce_to_primitives(concept)
    if not prims:
        return 0.8  # Unknown = high frequency

    # Average frequency of constituent primitives
    prim_freqs = []
    for p in prims:
        if p in primitives.ALL:
            idx = primitives.ALL.index(p)
            prim_freqs.append(0.1 + (idx / len(primitives.ALL)) * 0.3)

    if prim_freqs:
        base = sum(prim_freqs) / len(prim_freqs)
        # Add complexity factor (more primitives = higher frequency)
        complexity = min(0.3, len(prims) * 0.05)
        return min(1.0, base + complexity)

    return 0.5  # Default


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def reframe(concept: str, mode: Mode) -> ModalPerspective:
    """Convenience function to reframe a concept."""
    reframer = ModalReframer()
    return reframer.reframe(concept, mode)


def bind(*concepts: str) -> BoundConcept:
    """Convenience function to bind concepts."""
    binder = HarmonicBinder()
    return binder.bind_multimodal(*concepts)


def find_tonic(*concepts: str) -> str:
    """Convenience function to find semantic tonic."""
    binder = HarmonicBinder()
    return binder.find_semantic_tonic(*concepts)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums and types
    "Mode",
    "FrequencyBand",

    # Core classes
    "ModalPerspective",
    "ModalReframer",
    "SemanticPrimitives",
    "HarmonicBinder",
    "BoundConcept",
    "ConceptCircle",
    "ObserverState",

    # Frequency bands
    "GAMMA",
    "BETA",
    "THETA",
    "ALPHA",

    # Functions
    "lorentzian_coupling",
    "concept_to_frequency",
    "reframe",
    "bind",
    "find_tonic",
]
