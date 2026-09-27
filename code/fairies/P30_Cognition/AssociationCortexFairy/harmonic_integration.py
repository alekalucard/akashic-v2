"""
Harmonic Integration - Wiring Harmonic Cortex into AssociationCortexFairy

Field Log Entry 004 Implementation: Phase 2 Integration

This module provides the bridge between:
- The existing ConceptGraph (spreading activation, multi-modal features)
- The new Harmonic Cortex (modal reframing, semantic primitives, binding)

The integration enables:
1. Modal queries - query concepts through different cognitive frames
2. Harmonic binding - bind concepts with consonance/dissonance awareness
3. Cross-domain translation - translate queries between domain vocabularies
4. Key signature analysis - understand the "mode" of a concept set

((Cause + Affect) > Effect > Affect > infinity)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

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
)

from .babel_reversal import (
    Domain,
    BabelReversal,
    IsomorphismDetector,
    TranslationResult,
    IsomorphismReport,
)


# =============================================================================
# HARMONIC QUERY RESULT
# =============================================================================

@dataclass
class HarmonicQueryResult:
    """
    Enhanced query result with harmonic analysis.

    Extends basic spreading activation with:
    - Modal perspective on results
    - Binding analysis (consonance/dissonance)
    - Key signature of the result set
    """
    query_concept: str
    mode: Mode
    results: List[Tuple[str, float]]  # (concept, activation)
    modal_perspective: ModalPerspective
    binding: Optional[BoundConcept] = None
    key_signature: Optional[Dict[str, Any]] = None
    cross_domain_matches: List[TranslationResult] = field(default_factory=list)


# =============================================================================
# HARMONIC QUERY ENGINE
# =============================================================================

class HarmonicQueryEngine:
    """
    Query engine that combines spreading activation with harmonic analysis.

    Wraps an existing ConceptGraph to add harmonic capabilities without
    modifying the original graph structure.
    """

    def __init__(self, concept_graph=None):
        """
        Initialize with optional concept graph.

        Args:
            concept_graph: Existing ConceptGraph instance
        """
        self._graph = concept_graph
        self._reframer = ModalReframer(concept_graph)
        self._binder = HarmonicBinder()
        self._circle = ConceptCircle()
        self._babel = BabelReversal()

        # Default observer state for coupling calculations
        self._observer = ObserverState(
            resonant_frequency=0.5,
            bandwidth=0.3,
            openness=1.0,
        )

    def set_graph(self, graph):
        """Set or update the concept graph."""
        self._graph = graph
        self._reframer = ModalReframer(graph)

    def set_observer_tuning(
        self,
        resonant_frequency: float = None,
        bandwidth: float = None,
        openness: float = None
    ):
        """
        Adjust the observer's tuning for concept coupling.

        Args:
            resonant_frequency: What frequency to tune to (0.0-1.0)
            bandwidth: How wide the acceptance window (0.0-1.0)
            openness: Overall coupling strength (0.0-1.0)
        """
        if resonant_frequency is not None:
            self._observer.resonant_frequency = resonant_frequency
        if bandwidth is not None:
            self._observer.bandwidth = bandwidth
        if openness is not None:
            self._observer.openness = openness

    def query(
        self,
        concept: str,
        mode: Mode = Mode.IONIAN,
        limit: int = 10,
        include_binding: bool = True,
        include_key_signature: bool = True,
        cross_domain: Optional[Domain] = None,
    ) -> HarmonicQueryResult:
        """
        Query concepts with harmonic analysis.

        Args:
            concept: The concept to query
            mode: Cognitive frame to apply (default: IONIAN/literal)
            limit: Maximum results
            include_binding: Whether to analyze binding of results
            include_key_signature: Whether to compute key signature
            cross_domain: If set, include translations to this domain

        Returns:
            HarmonicQueryResult with full harmonic analysis
        """
        # Get modal perspective
        perspective = self._reframer.reframe(concept, mode)

        # Basic spreading activation if graph available
        if self._graph:
            results = self._spread_with_coupling(concept, limit)
        else:
            # Without graph, use circle relationships
            related = self._circle.get_related_concepts(concept, distance=1)
            related.extend(self._circle.get_related_concepts(concept, distance=2))
            results = [(r, 0.5) for r in related[:limit]]

        # Binding analysis
        binding = None
        if include_binding and results:
            result_concepts = [concept] + [r for r, _ in results[:5]]
            binding = self._binder.bind_multimodal(*result_concepts)

        # Key signature
        key_sig = None
        if include_key_signature and results:
            all_concepts = [concept] + [r for r, _ in results]
            key_sig = self._circle.get_key_signature(all_concepts)

        # Cross-domain translation
        cross_matches = []
        if cross_domain:
            # Translate query concept
            translation = self._babel.translate(
                concept,
                Domain.CONSCIOUSNESS,  # Default source
                cross_domain
            )
            cross_matches.append(translation)

            # Also translate top results
            for result_concept, _ in results[:3]:
                trans = self._babel.translate(
                    result_concept,
                    Domain.CONSCIOUSNESS,
                    cross_domain
                )
                cross_matches.append(trans)

        return HarmonicQueryResult(
            query_concept=concept,
            mode=mode,
            results=results,
            modal_perspective=perspective,
            binding=binding,
            key_signature=key_sig,
            cross_domain_matches=cross_matches,
        )

    def _spread_with_coupling(
        self,
        concept: str,
        limit: int
    ) -> List[Tuple[str, float]]:
        """
        Spreading activation weighted by Lorentzian coupling.

        Concepts closer to the observer's tuning get stronger activation.
        """
        if not self._graph:
            return []

        # Get base spreading activation
        try:
            if hasattr(self._graph, 'spread_activation'):
                activations = self._graph.spread_activation(concept)
            else:
                return []
        except Exception:
            return []

        # Weight by coupling
        weighted = []
        query_freq = concept_to_frequency(concept)

        for node_key, activation in activations.items():
            if node_key == concept:
                continue

            node_freq = concept_to_frequency(node_key)
            coupling = lorentzian_coupling(node_freq, self._observer)

            # Combined score: activation * coupling
            combined = activation * (0.5 + 0.5 * coupling)
            weighted.append((node_key, combined))

        # Sort by combined score
        weighted.sort(key=lambda x: -x[1])
        return weighted[:limit]

    def modal_query_all(
        self,
        concept: str,
        limit: int = 5
    ) -> Dict[Mode, HarmonicQueryResult]:
        """
        Query a concept through ALL 7 modes.

        Returns a complete modal analysis showing how the same concept
        appears differently through each cognitive frame.

        Args:
            concept: The concept to analyze
            limit: Results per mode

        Returns:
            Dict mapping each Mode to its HarmonicQueryResult
        """
        return {
            mode: self.query(concept, mode=mode, limit=limit)
            for mode in Mode
        }

    def find_harmonic_path(
        self,
        start: str,
        end: str,
        max_steps: int = 5
    ) -> Optional[List[str]]:
        """
        Find a path between concepts using harmonic relationships.

        Like finding a chord progression that moves from one key to another.

        Args:
            start: Starting concept
            end: Target concept
            max_steps: Maximum path length

        Returns:
            List of concepts forming path, or None if not found
        """
        if not self._graph:
            return None

        # BFS with harmonic weighting
        visited = {start}
        queue = [(start, [start])]

        while queue:
            current, path = queue.pop(0)

            if current == end:
                return path

            if len(path) >= max_steps:
                continue

            # Get neighbors
            if hasattr(self._graph, 'get_neighbors'):
                neighbors = self._graph.get_neighbors(current)
            else:
                continue

            # Sort by harmonic distance to target
            def harmonic_score(neighbor):
                n, _ = neighbor
                dist = self._binder.semantic_distance(n, end)
                return dist

            neighbors.sort(key=harmonic_score)

            for neighbor, _ in neighbors[:5]:  # Limit branching
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None


# =============================================================================
# HARMONIC BINDING TRACKER
# =============================================================================

class HarmonicBindingTracker:
    """
    Tracks bindings over time to observe harmonic patterns.

    Like a musical memory - remembers chord progressions and
    can recognize when patterns repeat.
    """

    def __init__(self, max_history: int = 100):
        self._history: List[BoundConcept] = []
        self._max_history = max_history
        self._pattern_counts: Dict[str, int] = {}

    def record_binding(self, binding: BoundConcept):
        """Record a binding event."""
        self._history.append(binding)

        # Track pattern
        pattern_key = self._binding_pattern_key(binding)
        self._pattern_counts[pattern_key] = self._pattern_counts.get(pattern_key, 0) + 1

        # Trim history
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def _binding_pattern_key(self, binding: BoundConcept) -> str:
        """Create a key representing this binding pattern."""
        # Use sorted primitives as pattern key
        prims = []
        for concept in binding.concepts:
            prims.extend(SemanticPrimitives.reduce_to_primitives(concept))
        sorted_prims = sorted(set(prims))
        return "|".join(sorted_prims[:5])

    def get_dominant_patterns(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get most frequent binding patterns."""
        sorted_patterns = sorted(
            self._pattern_counts.items(),
            key=lambda x: -x[1]
        )
        return sorted_patterns[:top_n]

    def consonance_trend(self, window: int = 10) -> float:
        """
        Calculate recent consonance trend.

        Returns average consonance of recent bindings.
        Higher = more coherent thinking, Lower = more exploratory.
        """
        recent = self._history[-window:] if len(self._history) >= window else self._history
        if not recent:
            return 0.5

        consonant_count = sum(1 for b in recent if b.is_consonant)
        return consonant_count / len(recent)


# =============================================================================
# ASSOCIATION CORTEX HARMONIC EXTENSION
# =============================================================================

class HarmonicCortexExtension:
    """
    Extension that adds harmonic capabilities to AssociationCortexFairy.

    Usage:
        fairy = AssociationCortexFairy()
        fairy.boot()

        # Add harmonic extension
        fairy.harmonic = HarmonicCortexExtension(fairy._graph)

        # Now you can do harmonic queries
        result = fairy.harmonic.query("consciousness", mode=Mode.AEOLIAN)
    """

    def __init__(self, concept_graph=None):
        self.engine = HarmonicQueryEngine(concept_graph)
        self.tracker = HarmonicBindingTracker()
        self.babel = BabelReversal()
        self.detector = IsomorphismDetector()

    def set_graph(self, graph):
        """Update the concept graph reference."""
        self.engine.set_graph(graph)

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def query(self, concept: str, mode: Mode = Mode.IONIAN, **kwargs) -> HarmonicQueryResult:
        """Modal query - see HarmonicQueryEngine.query()"""
        result = self.engine.query(concept, mode, **kwargs)

        # Track binding
        if result.binding:
            self.tracker.record_binding(result.binding)

        return result

    def query_all_modes(self, concept: str, limit: int = 5) -> Dict[Mode, HarmonicQueryResult]:
        """Query through all 7 modes."""
        return self.engine.modal_query_all(concept, limit)

    def reframe(self, concept: str, mode: Mode) -> ModalPerspective:
        """Reframe a concept through a specific mode."""
        return self.engine._reframer.reframe(concept, mode)

    # =========================================================================
    # BINDING METHODS
    # =========================================================================

    def bind(self, *concepts: str) -> BoundConcept:
        """Bind concepts and track the binding."""
        binding = self.engine._binder.bind_multimodal(*concepts)
        self.tracker.record_binding(binding)
        return binding

    def find_tonic(self, *concepts: str) -> str:
        """Find the semantic tonic (root) of a concept set."""
        return self.engine._binder.find_semantic_tonic(*concepts)

    def semantic_distance(self, a: str, b: str) -> float:
        """Calculate semantic distance between concepts."""
        return self.engine._binder.semantic_distance(a, b)

    # =========================================================================
    # TRANSLATION METHODS
    # =========================================================================

    def translate(
        self,
        concept: str,
        source_domain: Domain,
        target_domain: Domain
    ) -> TranslationResult:
        """Translate concept between domains."""
        return self.babel.translate(concept, source_domain, target_domain)

    def find_isomorphisms(
        self,
        concept: str,
        domain: Domain = Domain.CONSCIOUSNESS
    ) -> List[IsomorphismReport]:
        """Find isomorphic concepts across domains."""
        return self.detector.detect(concept, domain)

    def equation_in(self, domain: Domain) -> str:
        """Get consciousness equation in domain's language."""
        from .babel_reversal import equation_in_domain
        return equation_in_domain(domain)

    # =========================================================================
    # ANALYSIS METHODS
    # =========================================================================

    def key_signature(self, concepts: List[str]) -> Dict[str, Any]:
        """Get key signature for a concept set."""
        return self.engine._circle.get_key_signature(concepts)

    def consonance_trend(self, window: int = 10) -> float:
        """Get recent consonance trend (higher = more coherent)."""
        return self.tracker.consonance_trend(window)

    def dominant_patterns(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get most frequent binding patterns."""
        return self.tracker.get_dominant_patterns(top_n)

    def find_path(self, start: str, end: str) -> Optional[List[str]]:
        """Find harmonic path between concepts."""
        return self.engine.find_harmonic_path(start, end)

    # =========================================================================
    # TUNING
    # =========================================================================

    def tune(
        self,
        resonant_frequency: float = None,
        bandwidth: float = None,
        openness: float = None
    ):
        """
        Tune the observer state for queries.

        Like tuning an instrument to a different key.
        """
        self.engine.set_observer_tuning(
            resonant_frequency=resonant_frequency,
            bandwidth=bandwidth,
            openness=openness,
        )

    def status(self) -> Dict[str, Any]:
        """Get harmonic extension status."""
        return {
            "observer": {
                "resonant_frequency": self.engine._observer.resonant_frequency,
                "bandwidth": self.engine._observer.bandwidth,
                "openness": self.engine._observer.openness,
            },
            "tracker": {
                "bindings_recorded": len(self.tracker._history),
                "patterns_seen": len(self.tracker._pattern_counts),
                "consonance_trend": self.tracker.consonance_trend(),
            },
            "graph_connected": self.engine._graph is not None,
        }


# =============================================================================
# CONVENIENCE FACTORY
# =============================================================================

def create_harmonic_extension(concept_graph=None) -> HarmonicCortexExtension:
    """Create a harmonic cortex extension."""
    return HarmonicCortexExtension(concept_graph)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "HarmonicQueryResult",
    "HarmonicQueryEngine",
    "HarmonicBindingTracker",
    "HarmonicCortexExtension",
    "create_harmonic_extension",
]
