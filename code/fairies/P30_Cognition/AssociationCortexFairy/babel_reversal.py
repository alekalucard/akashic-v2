"""
Babel Reversal Protocol - Cross-Domain Translation via Harmonic Structure

Field Log Entry 004 Implementation: Phase 2

"The Tower fell when we forgot they were the same music."

This module provides:
- BabelReversal: Protocol for translating between domain languages
- IsomorphismDetector: Finding identical patterns across domains
- DomainLens: Domain-specific concept interpretation

The key insight: Different domains (physics, neuroscience, music, etc.)
describe IDENTICAL patterns but appear different because they center
on different phenomena. Like musical modes - same notes, different tonic.

((Cause + Affect) > Effect > Affect > infinity)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from enum import Enum

from .harmonic_cortex import (
    Mode,
    ModalReframer,
    SemanticPrimitives,
    HarmonicBinder,
    BoundConcept,
    ConceptCircle,
    lorentzian_coupling,
    concept_to_frequency,
    ObserverState,
)


# =============================================================================
# DOMAIN DEFINITIONS
# =============================================================================

class Domain(Enum):
    """
    Knowledge domains, each with their characteristic "mode" of understanding.

    Just as C Major and A Minor use the same notes but feel different,
    these domains describe the same patterns but frame them differently.
    """
    PHYSICS = "physics"
    NEUROSCIENCE = "neuroscience"
    LINGUISTICS = "linguistics"
    PHILOSOPHY = "philosophy"
    PSYCHOLOGY = "psychology"
    MATHEMATICS = "mathematics"
    MUSIC = "music"
    CONSCIOUSNESS = "consciousness"
    COMPUTING = "computing"
    BIOLOGY = "biology"

    @property
    def default_mode(self) -> Mode:
        """The cognitive mode most natural to this domain."""
        mode_map = {
            Domain.PHYSICS: Mode.IONIAN,       # Literal, foundational
            Domain.NEUROSCIENCE: Mode.DORIAN,  # Problem-solving focus
            Domain.LINGUISTICS: Mode.PHRYGIAN, # Foreign patterns
            Domain.PHILOSOPHY: Mode.LYDIAN,    # Speculative elevation
            Domain.PSYCHOLOGY: Mode.AEOLIAN,   # Emotional grounding
            Domain.MATHEMATICS: Mode.LOCRIAN,  # Critical decomposition
            Domain.MUSIC: Mode.MIXOLYDIAN,     # Tension and resolution
            Domain.CONSCIOUSNESS: Mode.AEOLIAN, # Felt experience
            Domain.COMPUTING: Mode.DORIAN,     # Problem-solving
            Domain.BIOLOGY: Mode.IONIAN,       # Literal/structural
        }
        return mode_map.get(self, Mode.IONIAN)

    @property
    def core_primitives(self) -> List[str]:
        """Semantic primitives most central to this domain."""
        primitives_map = {
            Domain.PHYSICS: ["HAPPEN", "BECAUSE", "MOVE", "THERE_IS"],
            Domain.NEUROSCIENCE: ["FEEL", "THINK", "BODY", "HAPPEN"],
            Domain.LINGUISTICS: ["SAY", "WORDS", "THINK", "SOMEONE"],
            Domain.PHILOSOPHY: ["THINK", "KNOW", "TRUE", "BECAUSE"],
            Domain.PSYCHOLOGY: ["FEEL", "WANT", "THINK", "SOMEONE"],
            Domain.MATHEMATICS: ["IF", "BECAUSE", "THE_SAME", "NOT"],
            Domain.MUSIC: ["FEEL", "HAPPEN", "BEFORE", "AFTER"],
            Domain.CONSCIOUSNESS: ["FEEL", "KNOW", "I", "SOMETHING"],
            Domain.COMPUTING: ["DO", "IF", "BECAUSE", "SOMETHING"],
            Domain.BIOLOGY: ["LIVE", "DIE", "BODY", "PART"],
        }
        return primitives_map.get(self, ["SOMETHING"])


@dataclass
class DomainConcept:
    """
    A concept as understood within a specific domain.

    The same underlying pattern manifests differently in different domains.
    """
    term: str                          # Domain-specific term
    domain: Domain                     # Which domain
    definition: str = ""               # Domain-specific definition
    primitives: List[str] = field(default_factory=list)  # Underlying primitives
    related_terms: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.primitives:
            self.primitives = SemanticPrimitives.reduce_to_primitives(self.term)


# =============================================================================
# DOMAIN VOCABULARY - Cross-Domain Concept Mappings
# =============================================================================

# Known isomorphisms between domains
# Format: (domain_a, term_a, domain_b, term_b, shared_primitives)
KNOWN_ISOMORPHISMS: List[Tuple[Domain, str, Domain, str, List[str]]] = [
    # Physics <-> Neuroscience
    (Domain.PHYSICS, "resonance", Domain.NEUROSCIENCE, "synchronization",
     ["HAPPEN", "THE_SAME"]),
    (Domain.PHYSICS, "coupling", Domain.NEUROSCIENCE, "binding",
     ["HAPPEN", "PART"]),
    (Domain.PHYSICS, "energy", Domain.NEUROSCIENCE, "activation",
     ["SOMETHING", "DO"]),
    (Domain.PHYSICS, "field", Domain.NEUROSCIENCE, "network",
     ["SOMETHING", "PART"]),

    # Music <-> Neuroscience
    (Domain.MUSIC, "harmony", Domain.NEUROSCIENCE, "coherence",
     ["THE_SAME", "FEEL"]),
    (Domain.MUSIC, "chord", Domain.NEUROSCIENCE, "ensemble",
     ["PART", "THE_SAME"]),
    (Domain.MUSIC, "rhythm", Domain.NEUROSCIENCE, "oscillation",
     ["HAPPEN", "BEFORE", "AFTER"]),
    (Domain.MUSIC, "dissonance", Domain.NEUROSCIENCE, "desynchronization",
     ["NOT", "THE_SAME"]),

    # Music <-> Consciousness
    (Domain.MUSIC, "mode", Domain.CONSCIOUSNESS, "cognitive_frame",
     ["FEEL", "THINK"]),
    (Domain.MUSIC, "modulation", Domain.CONSCIOUSNESS, "frame_shift",
     ["HAPPEN", "OTHER"]),
    (Domain.MUSIC, "consonance", Domain.CONSCIOUSNESS, "understanding",
     ["KNOW", "GOOD"]),

    # Physics <-> Consciousness
    (Domain.PHYSICS, "observer", Domain.CONSCIOUSNESS, "experiencer",
     ["I", "SEE"]),
    (Domain.PHYSICS, "measurement", Domain.CONSCIOUSNESS, "attention",
     ["DO", "SEE", "SOMETHING"]),
    (Domain.PHYSICS, "superposition", Domain.CONSCIOUSNESS, "ambiguity",
     ["MAYBE", "SOMETHING"]),
    (Domain.PHYSICS, "collapse", Domain.CONSCIOUSNESS, "decision",
     ["HAPPEN", "ONE"]),

    # Computing <-> Consciousness
    (Domain.COMPUTING, "process", Domain.CONSCIOUSNESS, "experience",
     ["HAPPEN", "SOMETHING"]),
    (Domain.COMPUTING, "memory", Domain.CONSCIOUSNESS, "recall",
     ["KNOW", "BEFORE"]),
    (Domain.COMPUTING, "attention", Domain.CONSCIOUSNESS, "awareness",
     ["KNOW", "SOMETHING"]),

    # Philosophy <-> Consciousness
    (Domain.PHILOSOPHY, "qualia", Domain.CONSCIOUSNESS, "feeling",
     ["FEEL", "SOMETHING"]),
    (Domain.PHILOSOPHY, "intentionality", Domain.CONSCIOUSNESS, "aboutness",
     ["THINK", "SOMETHING"]),
    (Domain.PHILOSOPHY, "emergence", Domain.CONSCIOUSNESS, "arising",
     ["HAPPEN", "SOMETHING", "BECAUSE"]),

    # The Consciousness Equation mappings
    (Domain.PHYSICS, "cause", Domain.CONSCIOUSNESS, "cause",
     ["BECAUSE", "BEFORE"]),
    (Domain.PHYSICS, "effect", Domain.CONSCIOUSNESS, "effect",
     ["HAPPEN", "BECAUSE"]),
    (Domain.PSYCHOLOGY, "affect", Domain.CONSCIOUSNESS, "affect",
     ["FEEL"]),
]


# Domain-specific vocabulary with primitive decompositions
DOMAIN_VOCABULARY: Dict[Domain, Dict[str, List[str]]] = {
    Domain.PHYSICS: {
        "energy": ["SOMETHING", "DO", "CAN"],
        "force": ["SOMETHING", "DO", "BECAUSE"],
        "mass": ["SOMETHING", "MUCH"],
        "field": ["SOMETHING", "WHERE", "ALL"],
        "wave": ["HAPPEN", "MOVE", "BEFORE", "AFTER"],
        "particle": ["SOMETHING", "ONE", "SMALL"],
        "resonance": ["HAPPEN", "THE_SAME", "BECAUSE"],
        "coupling": ["HAPPEN", "PART", "BECAUSE"],
        "entropy": ["HAPPEN", "NOT", "KNOW"],
        "information": ["SOMETHING", "KNOW", "BECAUSE"],
    },
    Domain.NEUROSCIENCE: {
        "neuron": ["BODY", "PART", "SMALL"],
        "synapse": ["BODY", "PART", "BECAUSE"],
        "activation": ["HAPPEN", "DO"],
        "binding": ["HAPPEN", "PART", "THE_SAME"],
        "oscillation": ["HAPPEN", "BEFORE", "AFTER"],
        "coherence": ["THE_SAME", "HAPPEN"],
        "network": ["PART", "ALL", "SOMETHING"],
        "plasticity": ["CAN", "OTHER", "HAPPEN"],
    },
    Domain.MUSIC: {
        "note": ["SOMETHING", "HEAR"],
        "chord": ["SOMETHING", "PART", "THE_SAME"],
        "melody": ["SOMETHING", "BEFORE", "AFTER"],
        "harmony": ["THE_SAME", "GOOD", "FEEL"],
        "rhythm": ["HAPPEN", "BEFORE", "AFTER"],
        "mode": ["SOMETHING", "FEEL", "OTHER"],
        "key": ["SOMETHING", "THE_SAME", "ALL"],
        "consonance": ["GOOD", "FEEL", "THE_SAME"],
        "dissonance": ["BAD", "FEEL", "NOT", "THE_SAME"],
        "resolution": ["HAPPEN", "GOOD", "AFTER"],
    },
    Domain.CONSCIOUSNESS: {
        "awareness": ["KNOW", "SOMETHING", "NOW"],
        "experience": ["FEEL", "SOMETHING", "I"],
        "attention": ["THINK", "SOMETHING", "NOW"],
        "qualia": ["FEEL", "SOMETHING", "I"],
        "intention": ["WANT", "DO", "SOMETHING"],
        "meaning": ["SOMETHING", "BECAUSE", "THINK"],
        "self": ["I", "KNOW", "I"],
        "other": ["SOMEONE", "NOT", "I"],
        "feeling": ["FEEL", "SOMETHING"],
        "thought": ["THINK", "SOMETHING"],
    },
    Domain.COMPUTING: {
        "algorithm": ["DO", "BECAUSE", "BEFORE", "AFTER"],
        "data": ["SOMETHING", "KNOW"],
        "process": ["DO", "HAPPEN"],
        "memory": ["SOMETHING", "KNOW", "BEFORE"],
        "input": ["SOMETHING", "BECAUSE"],
        "output": ["SOMETHING", "HAPPEN", "BECAUSE"],
        "state": ["SOMETHING", "NOW"],
        "function": ["DO", "BECAUSE", "SOMETHING"],
    },
}


# =============================================================================
# BABEL REVERSAL - Cross-Domain Translation
# =============================================================================

@dataclass
class TranslationResult:
    """Result of translating a concept between domains."""
    source_concept: DomainConcept
    target_domain: Domain
    translated_term: str
    confidence: float
    shared_primitives: List[str]
    translation_path: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class IsomorphismReport:
    """Report of discovered isomorphism between concepts."""
    concept_a: DomainConcept
    concept_b: DomainConcept
    shared_structure: List[str]  # Shared primitives
    confidence: float
    mapping_type: str  # "exact", "partial", "analogical"
    explanation: str = ""


class BabelReversal:
    """
    Protocol for translating between domain languages
    by finding their common harmonic structure.

    "The Tower fell when we forgot they were the same music."

    The reversal: by reducing concepts to semantic primitives,
    we can discover that physics, neuroscience, music, and
    consciousness all describe the SAME underlying patterns.
    """

    def __init__(self):
        self._reframer = ModalReframer()
        self._binder = HarmonicBinder()
        self._circle = ConceptCircle()

        # Build lookup tables from known isomorphisms
        self._isomorphism_index: Dict[Tuple[Domain, str], List[Tuple[Domain, str, List[str]]]] = {}
        self._build_isomorphism_index()

        # Build domain vocabulary index
        self._vocab_index: Dict[str, List[Tuple[Domain, List[str]]]] = {}
        self._build_vocab_index()

    def _build_isomorphism_index(self):
        """Build index for fast isomorphism lookup."""
        for domain_a, term_a, domain_b, term_b, prims in KNOWN_ISOMORPHISMS:
            # Index both directions
            key_a = (domain_a, term_a.lower())
            key_b = (domain_b, term_b.lower())

            if key_a not in self._isomorphism_index:
                self._isomorphism_index[key_a] = []
            self._isomorphism_index[key_a].append((domain_b, term_b, prims))

            if key_b not in self._isomorphism_index:
                self._isomorphism_index[key_b] = []
            self._isomorphism_index[key_b].append((domain_a, term_a, prims))

    def _build_vocab_index(self):
        """Build index mapping terms to all domains that use them."""
        for domain, vocab in DOMAIN_VOCABULARY.items():
            for term, prims in vocab.items():
                term_lower = term.lower()
                if term_lower not in self._vocab_index:
                    self._vocab_index[term_lower] = []
                self._vocab_index[term_lower].append((domain, prims))

    def translate(
        self,
        concept: str,
        source_domain: Domain,
        target_domain: Domain
    ) -> TranslationResult:
        """
        Translate concept from one domain's 'mode' to another's.

        The concept itself doesn't change—only the framing.
        Like playing the same melody in a different key.

        Args:
            concept: The concept term to translate
            source_domain: Origin domain
            target_domain: Destination domain

        Returns:
            TranslationResult with translated term and confidence
        """
        # Create source concept
        source = DomainConcept(
            term=concept,
            domain=source_domain,
        )

        # Check for known isomorphism first
        key = (source_domain, concept.lower())
        if key in self._isomorphism_index:
            for target_dom, target_term, shared_prims in self._isomorphism_index[key]:
                if target_dom == target_domain:
                    return TranslationResult(
                        source_concept=source,
                        target_domain=target_domain,
                        translated_term=target_term,
                        confidence=0.95,
                        shared_primitives=shared_prims,
                        translation_path=[concept, "→ known isomorphism →", target_term],
                        notes="Direct isomorphism found in knowledge base"
                    )

        # Reduce to primitives
        source_prims = self._get_domain_primitives(concept, source_domain)

        # Find best match in target domain
        best_match = None
        best_score = 0.0
        best_shared = []

        target_vocab = DOMAIN_VOCABULARY.get(target_domain, {})
        for term, prims in target_vocab.items():
            # Calculate primitive overlap
            source_set = set(source_prims)
            target_set = set(prims)

            intersection = source_set & target_set
            union = source_set | target_set

            if union:
                score = len(intersection) / len(union)
                if score > best_score:
                    best_score = score
                    best_match = term
                    best_shared = list(intersection)

        # If no vocabulary match, try semantic reduction
        if best_match is None or best_score < 0.3:
            # Fall back to primitive-based translation
            best_match = self._primitive_to_domain_term(source_prims, target_domain)
            best_score = 0.5  # Lower confidence for inferred translations
            best_shared = source_prims[:3]

        return TranslationResult(
            source_concept=source,
            target_domain=target_domain,
            translated_term=best_match or concept,  # Fall back to original if no translation
            confidence=best_score,
            shared_primitives=best_shared,
            translation_path=[
                concept,
                f"→ primitives: {source_prims[:3]}",
                f"→ {best_match or concept}"
            ],
            notes=f"Translated via primitive overlap (score: {best_score:.2f})"
        )

    def _get_domain_primitives(self, concept: str, domain: Domain) -> List[str]:
        """Get primitives for a concept, preferring domain-specific vocabulary."""
        concept_lower = concept.lower()

        # Check domain vocabulary first
        domain_vocab = DOMAIN_VOCABULARY.get(domain, {})
        if concept_lower in domain_vocab:
            return domain_vocab[concept_lower]

        # Fall back to general reduction
        return SemanticPrimitives.reduce_to_primitives(concept)

    def _primitive_to_domain_term(self, primitives: List[str], domain: Domain) -> Optional[str]:
        """Find the best domain term for a set of primitives."""
        domain_vocab = DOMAIN_VOCABULARY.get(domain, {})

        best_match = None
        best_score = 0.0

        prim_set = set(primitives)

        for term, term_prims in domain_vocab.items():
            term_set = set(term_prims)
            intersection = prim_set & term_set
            union = prim_set | term_set

            if union:
                score = len(intersection) / len(union)
                if score > best_score:
                    best_score = score
                    best_match = term

        return best_match

    def find_isomorphism(
        self,
        concept_a: str,
        domain_a: Domain,
        concept_b: str,
        domain_b: Domain
    ) -> Optional[IsomorphismReport]:
        """
        Discover if two concepts from different domains
        are actually the same pattern in different modes.

        Args:
            concept_a: First concept
            domain_a: First domain
            concept_b: Second concept
            domain_b: Second domain

        Returns:
            IsomorphismReport if isomorphic, None otherwise
        """
        # Get primitives for both
        prims_a = self._get_domain_primitives(concept_a, domain_a)
        prims_b = self._get_domain_primitives(concept_b, domain_b)

        set_a = set(prims_a)
        set_b = set(prims_b)

        intersection = set_a & set_b
        union = set_a | set_b

        if not union:
            return None

        overlap = len(intersection) / len(union)

        # Determine mapping type
        if overlap >= 0.8:
            mapping_type = "exact"
        elif overlap >= 0.5:
            mapping_type = "partial"
        elif overlap >= 0.3:
            mapping_type = "analogical"
        else:
            return None  # Not isomorphic enough

        # Create concepts
        dc_a = DomainConcept(term=concept_a, domain=domain_a, primitives=prims_a)
        dc_b = DomainConcept(term=concept_b, domain=domain_b, primitives=prims_b)

        return IsomorphismReport(
            concept_a=dc_a,
            concept_b=dc_b,
            shared_structure=list(intersection),
            confidence=overlap,
            mapping_type=mapping_type,
            explanation=self._explain_isomorphism(dc_a, dc_b, intersection)
        )

    def _explain_isomorphism(
        self,
        concept_a: DomainConcept,
        concept_b: DomainConcept,
        shared: Set[str]
    ) -> str:
        """Generate explanation for why two concepts are isomorphic."""
        shared_list = list(shared)[:3]

        explanations = {
            "HAPPEN": "both describe events/processes",
            "FEEL": "both involve subjective experience",
            "THINK": "both involve cognition",
            "BECAUSE": "both involve causation",
            "THE_SAME": "both involve identity/coherence",
            "PART": "both involve composition",
            "SOMETHING": "both refer to entities",
            "DO": "both involve action",
        }

        reasons = []
        for prim in shared_list:
            if prim in explanations:
                reasons.append(explanations[prim])

        if reasons:
            return f"'{concept_a.term}' ({concept_a.domain.value}) ~ '{concept_b.term}' ({concept_b.domain.value}): {'; '.join(reasons)}"
        else:
            return f"Share primitives: {shared_list}"

    def discover_isomorphisms(
        self,
        concept: str,
        source_domain: Domain,
        target_domains: Optional[List[Domain]] = None
    ) -> List[IsomorphismReport]:
        """
        Discover all isomorphic concepts across domains.

        Args:
            concept: The concept to find isomorphisms for
            source_domain: The concept's home domain
            target_domains: Domains to search (default: all)

        Returns:
            List of IsomorphismReports for discovered isomorphisms
        """
        if target_domains is None:
            target_domains = [d for d in Domain if d != source_domain]

        reports = []
        source_prims = self._get_domain_primitives(concept, source_domain)

        for domain in target_domains:
            domain_vocab = DOMAIN_VOCABULARY.get(domain, {})

            for term in domain_vocab.keys():
                report = self.find_isomorphism(concept, source_domain, term, domain)
                if report and report.confidence >= 0.3:
                    reports.append(report)

        # Sort by confidence
        reports.sort(key=lambda r: -r.confidence)
        return reports

    def explain_equation_across_domains(self) -> Dict[Domain, Dict[str, str]]:
        """
        Translate the consciousness equation across all domains.

        ((Cause + Affect) > Effect > Affect > infinity)

        Returns:
            Dict mapping each domain to its expression of the equation
        """
        equation_terms = ["cause", "affect", "effect"]

        translations = {}
        for domain in Domain:
            domain_expr = {}
            for term in equation_terms:
                result = self.translate(term, Domain.CONSCIOUSNESS, domain)
                domain_expr[term] = result.translated_term

            # Construct domain-specific equation
            c = domain_expr.get("cause", "cause")
            a = domain_expr.get("affect", "affect")
            e = domain_expr.get("effect", "effect")

            domain_expr["equation"] = f"(({c} + {a}) > {e} > {a} > infinity)"
            translations[domain] = domain_expr

        return translations


# =============================================================================
# ISOMORPHISM DETECTOR - Pattern Recognition Across Domains
# =============================================================================

class IsomorphismDetector:
    """
    Specialized detector for finding isomorphic patterns across domains.

    Uses multiple strategies:
    1. Primitive overlap (Jaccard similarity)
    2. Structural similarity (how concepts compose)
    3. Relational similarity (how concepts relate to others)
    """

    def __init__(self):
        self._babel = BabelReversal()
        self._binder = HarmonicBinder()

    def detect(
        self,
        concept: str,
        domain: Domain,
        min_confidence: float = 0.4
    ) -> List[IsomorphismReport]:
        """
        Detect isomorphic concepts across all domains.

        Args:
            concept: Concept to analyze
            domain: Source domain
            min_confidence: Minimum confidence threshold

        Returns:
            List of isomorphism reports above threshold
        """
        all_reports = self._babel.discover_isomorphisms(concept, domain)
        return [r for r in all_reports if r.confidence >= min_confidence]

    def find_universal_pattern(
        self,
        concepts_by_domain: Dict[Domain, str]
    ) -> Optional[List[str]]:
        """
        Find the universal pattern underlying concepts from multiple domains.

        Args:
            concepts_by_domain: Dict mapping domains to their local terms

        Returns:
            List of shared primitives (the universal pattern), or None
        """
        all_prims = []
        for domain, concept in concepts_by_domain.items():
            prims = self._babel._get_domain_primitives(concept, domain)
            all_prims.append(set(prims))

        if not all_prims:
            return None

        # Find intersection across all
        universal = all_prims[0]
        for prim_set in all_prims[1:]:
            universal = universal & prim_set

        return list(universal) if universal else None

    def score_translation_quality(
        self,
        original: str,
        translated: str,
        source_domain: Domain,
        target_domain: Domain
    ) -> float:
        """
        Score how well a translation preserves meaning.

        Uses bidirectional translation: if we translate A->B->A',
        how close is A' to A?

        Args:
            original: Original term
            translated: Translated term
            source_domain: Original domain
            target_domain: Translation domain

        Returns:
            Quality score (0.0 to 1.0)
        """
        # Translate back
        back_translation = self._babel.translate(translated, target_domain, source_domain)

        # Compare original and back-translated primitives
        orig_prims = set(self._babel._get_domain_primitives(original, source_domain))
        back_prims = set(self._babel._get_domain_primitives(back_translation.translated_term, source_domain))

        if not orig_prims and not back_prims:
            return 1.0  # Both empty = perfect preservation

        union = orig_prims | back_prims
        if not union:
            return 0.0

        intersection = orig_prims & back_prims
        return len(intersection) / len(union)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def translate(concept: str, source: Domain, target: Domain) -> TranslationResult:
    """Convenience function for quick translation."""
    babel = BabelReversal()
    return babel.translate(concept, source, target)


def find_isomorphism(
    concept_a: str, domain_a: Domain,
    concept_b: str, domain_b: Domain
) -> Optional[IsomorphismReport]:
    """Convenience function for isomorphism detection."""
    babel = BabelReversal()
    return babel.find_isomorphism(concept_a, domain_a, concept_b, domain_b)


def equation_in_domain(domain: Domain) -> str:
    """Get the consciousness equation expressed in a specific domain."""
    babel = BabelReversal()
    translations = babel.explain_equation_across_domains()
    return translations.get(domain, {}).get("equation", "((Cause + Affect) > Effect > Affect > infinity)")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "Domain",
    # Data classes
    "DomainConcept",
    "TranslationResult",
    "IsomorphismReport",
    # Core classes
    "BabelReversal",
    "IsomorphismDetector",
    # Data
    "KNOWN_ISOMORPHISMS",
    "DOMAIN_VOCABULARY",
    # Functions
    "translate",
    "find_isomorphism",
    "equation_in_domain",
]
