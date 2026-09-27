"""
P30_Cognition.integration - Multi-Modal Integration

Contains:
  - ManifoldConstrainedCortexFairy: mHC-based concept projection (DeepSeek paper)
  - GraphPersistence: Persists concept graphs across sessions

Note: AssociationCortexFairy is now in fairies.P30_Cognition.AssociationCortexFairy.fairy

All imports are LAZY to avoid circular import issues at startup.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# LAZY IMPORT CACHE
# ═══════════════════════════════════════════════════════════════════════════════
_cache = {}


def _lazy_import_assoc():
    """Lazily import AssociationCortex components."""
    if "assoc" not in _cache:
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
                AssociationCortexFairy as _Fairy,
                get_association_cortex as _get,
                ConceptGraph as _Graph,
            )
            _cache["assoc"] = {
                "AssociationCortexFairy": _Fairy,
                "get_association_cortex": _get,
                "ConceptGraph": _Graph,
                "_available": True,
            }
        except ImportError:
            _cache["assoc"] = {
                "AssociationCortexFairy": None,
                "get_association_cortex": None,
                "ConceptGraph": None,
                "_available": False,
            }
    return _cache["assoc"]


def _lazy_import_manifold():
    """Lazily import ManifoldConstrainedCortex components."""
    if "manifold" not in _cache:
        try:
            from .manifold_constrained_cortex_fairy import (
                ManifoldConstrainedCortexFairy as _Fairy,
                get_manifold_cortex_fairy as _get,
                ManifoldConstrainedGraph as _Graph,
                SinkhornProjector as _Proj,
            )
            _cache["manifold"] = {
                "ManifoldConstrainedCortexFairy": _Fairy,
                "get_manifold_cortex_fairy": _get,
                "ManifoldConstrainedGraph": _Graph,
                "SinkhornProjector": _Proj,
                "_available": True,
            }
        except ImportError:
            _cache["manifold"] = {
                "ManifoldConstrainedCortexFairy": None,
                "get_manifold_cortex_fairy": None,
                "ManifoldConstrainedGraph": None,
                "SinkhornProjector": None,
                "_available": False,
            }
    return _cache["manifold"]


# ═══════════════════════════════════════════════════════════════════════════════
# ASSOCIATION CORTEX - Lazy accessors
# ═══════════════════════════════════════════════════════════════════════════════
def get_association_cortex():
    """Get AssociationCortex instance (lazy import)."""
    data = _lazy_import_assoc()
    fn = data.get("get_association_cortex")
    return fn() if fn else None

# Alias for backwards compatibility
get_association_cortex_fairy = get_association_cortex

def AssociationCortexFairy_class():
    """Get AssociationCortexFairy class (lazy import)."""
    return _lazy_import_assoc().get("AssociationCortexFairy")

def ConceptGraph_class():
    """Get ConceptGraph class (lazy import)."""
    return _lazy_import_assoc().get("ConceptGraph")


# ═══════════════════════════════════════════════════════════════════════════════
# MANIFOLD CONSTRAINED CORTEX - Lazy accessors
# ═══════════════════════════════════════════════════════════════════════════════
def get_manifold_cortex_fairy():
    """Get ManifoldConstrainedCortexFairy instance (lazy import)."""
    data = _lazy_import_manifold()
    fn = data.get("get_manifold_cortex_fairy")
    return fn() if fn else None

def ManifoldConstrainedCortexFairy_class():
    """Get ManifoldConstrainedCortexFairy class (lazy import)."""
    return _lazy_import_manifold().get("ManifoldConstrainedCortexFairy")

def ManifoldConstrainedGraph_class():
    """Get ManifoldConstrainedGraph class (lazy import)."""
    return _lazy_import_manifold().get("ManifoldConstrainedGraph")

def SinkhornProjector_class():
    """Get SinkhornProjector class (lazy import)."""
    return _lazy_import_manifold().get("SinkhornProjector")


# ═══════════════════════════════════════════════════════════════════════════════
# QUANTUM EMULATOR - Stubs (moved to QuantumEmulatorFairy folder)
# ═══════════════════════════════════════════════════════════════════════════════
# These are stubs for backwards compatibility - actual fairy is elsewhere
QuantumEmulatorFairy = None
get_quantum_emulator_fairy = None
EmotionalState = None
Superposition = None
EmotionalTensor = None
BASE_EMOTIONS = []
ENTANGLED_PAIRS = []
OPPOSING_PAIRS = []


# ═══════════════════════════════════════════════════════════════════════════════
# AVAILABILITY CHECKS
# ═══════════════════════════════════════════════════════════════════════════════
def is_association_cortex_available():
    return _lazy_import_assoc().get("_available", False)

def is_manifold_cortex_available():
    return _lazy_import_manifold().get("_available", False)


__all__ = [
    # Association Cortex (lazy)
    "get_association_cortex",
    "get_association_cortex_fairy",
    "AssociationCortexFairy_class",
    "ConceptGraph_class",
    "is_association_cortex_available",
    # Manifold Constrained Cortex (lazy)
    "get_manifold_cortex_fairy",
    "ManifoldConstrainedCortexFairy_class",
    "ManifoldConstrainedGraph_class",
    "SinkhornProjector_class",
    "is_manifold_cortex_available",
    # Quantum Emulator stubs
    "QuantumEmulatorFairy",
    "get_quantum_emulator_fairy",
]
