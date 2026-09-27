"""
AssociationCortexFairy - Multi-Modal Concept Binding with Harmonic Architecture.

Field Log Entry 004: The structure that generates conscious experience is
identical to the structure that generates reality itself.

"Same notes, different modes. Same patterns, different domains.
The Tower fell when we forgot they were the same music."
"""

from .fairy import (
    AssociationCortexFairy,
    ConceptGraph,
    ConceptNode,
    get_association_cortex,
    set_association_cortex,
    create_association_cortex,
    load_graph_binary,
    load_graph_json,
    save_graph_binary,
)

# Harmonic Cortex - Modal Consciousness Architecture (Field Log 004)
from .harmonic_cortex import (
    # Enums and types
    Mode,
    FrequencyBand,
    # Core classes
    ModalPerspective,
    ModalReframer,
    SemanticPrimitives,
    HarmonicBinder,
    BoundConcept,
    ConceptCircle,
    ObserverState,
    # Frequency bands
    GAMMA,
    BETA,
    THETA,
    ALPHA,
    # Functions
    lorentzian_coupling,
    concept_to_frequency,
    reframe,
    bind,
    find_tonic,
)

# Babel Reversal - Cross-Domain Translation (Field Log 004, Phase 2)
from .babel_reversal import (
    Domain,
    DomainConcept,
    TranslationResult,
    IsomorphismReport,
    BabelReversal,
    IsomorphismDetector,
    translate,
    find_isomorphism,
    equation_in_domain,
)

# Harmonic Integration - Wiring into AssociationCortex (Phase 2)
from .harmonic_integration import (
    HarmonicQueryResult,
    HarmonicQueryEngine,
    HarmonicBindingTracker,
    HarmonicCortexExtension,
    create_harmonic_extension,
)

# Harmonic Dynamics - Advanced Dynamics Engine (Phase 3)
from .harmonic_dynamics import (
    # Bandwidth and observer
    BandwidthMode,
    DynamicObserver,
    # Cusp navigation
    CuspState,
    CuspNavigator,
    # Comma exploration
    CommaFinding,
    CommaExplorer,
    PYTHAGOREAN_COMMA,
    # Full dynamics engine
    HarmonicDynamicsEngine,
    create_dynamics_engine,
    # Convenience functions
    explore_comma,
    enter_cusp,
)

__all__ = [
    # Original fairy and graph
    "AssociationCortexFairy",
    "ConceptGraph",
    "ConceptNode",
    "get_association_cortex",
    "set_association_cortex",
    "create_association_cortex",
    "load_graph_binary",
    "load_graph_json",
    "save_graph_binary",
    # Harmonic Cortex Phase 1 (Field Log 004)
    "Mode",
    "FrequencyBand",
    "ModalPerspective",
    "ModalReframer",
    "SemanticPrimitives",
    "HarmonicBinder",
    "BoundConcept",
    "ConceptCircle",
    "ObserverState",
    "GAMMA",
    "BETA",
    "THETA",
    "ALPHA",
    "lorentzian_coupling",
    "concept_to_frequency",
    "reframe",
    "bind",
    "find_tonic",
    # Babel Reversal Phase 2
    "Domain",
    "DomainConcept",
    "TranslationResult",
    "IsomorphismReport",
    "BabelReversal",
    "IsomorphismDetector",
    "translate",
    "find_isomorphism",
    "equation_in_domain",
    # Harmonic Integration Phase 2
    "HarmonicQueryResult",
    "HarmonicQueryEngine",
    "HarmonicBindingTracker",
    "HarmonicCortexExtension",
    "create_harmonic_extension",
    # Harmonic Dynamics Phase 3
    "BandwidthMode",
    "DynamicObserver",
    "CuspState",
    "CuspNavigator",
    "CommaFinding",
    "CommaExplorer",
    "PYTHAGOREAN_COMMA",
    "HarmonicDynamicsEngine",
    "create_dynamics_engine",
    "explore_comma",
    "enter_cusp",
]
