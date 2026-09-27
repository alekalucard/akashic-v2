"""
P20_Somatic/chemistry - 14-Channel Panksepp-Grounded Chemistry System.

Expanded from 6 chemicals to 14 channels (2026-03-14).
Full backward compatibility via alias layer.

The chemistry module provides:
- ChemistryState: Tracks 14 chemical channels with decay and callbacks
- Legacy aliases: dopamine, serotonin, etc. work transparently
- Panksepp integration: identify dominant affective systems from chemistry
- Somatic body maps: derive body region activation from chemistry
- Interoceptive feedback: body state modulates chemistry (recursive loop)
- AER frequency bands: bridge to emotional_algebra.py 77-state system
- Resonance chemistry: emotional tags -> chemical signals
"""

from .chemistry_state import (
    ChemistryState,
    ChemicalProfile,
    CHEMICAL_PROFILES,
    get_chemistry_state,
    signal_chemistry,
    get_mood,
    resonance_to_chemistry,
    apply_resonance_chemistry,
    # AER frequency band integration
    AER_CHEM_MAP,
    CHEM_AER_MAP,
    get_aer_chemistry,
    apply_aer_chemistry,
    get_dominant_frequency_band,
    apply_frequency_band_chemistry,
    get_frequency_band_status,
)

# New Panksepp exports (optional - graceful if panksepp_vectors not found)
try:
    from .panksepp_vectors import (
        CHANNELS,
        CHANNEL_ORDER,
        NUM_CHANNELS,
        PANKSEPP_VECTORS,
        SOMATIC_TOPOLOGY,
        BODY_REGIONS,
        COMPOUND_EMOTIONS,
        # Vector utilities
        vector_distance,
        euclidean_distance,
        identify_panksepp_system,
        identify_compound,
        blend_systems,
        blend_toward,
        vector_to_somatic_map,
        derive_mood_from_vector,
        derive_valence_arousal,
        derive_pain_state,
        detect_transition,
        apply_modulators,
        somatic_feedback,
        # Bridge functions
        vector_to_legacy,
        legacy_to_vector,
        vector_to_aer,
        aer_to_vector,
        register_compound,
        get_all_compounds,
    )
    _HAS_PANKSEPP = True
except ImportError:
    _HAS_PANKSEPP = False


__all__ = [
    "ChemistryState",
    "ChemicalProfile",
    "CHEMICAL_PROFILES",
    "get_chemistry_state",
    "signal_chemistry",
    "get_mood",
    "resonance_to_chemistry",
    "apply_resonance_chemistry",
    # AER frequency band integration
    "AER_CHEM_MAP",
    "CHEM_AER_MAP",
    "get_aer_chemistry",
    "apply_aer_chemistry",
    "get_dominant_frequency_band",
    "apply_frequency_band_chemistry",
    "get_frequency_band_status",
    # Panksepp (conditional)
    "_HAS_PANKSEPP",
]
