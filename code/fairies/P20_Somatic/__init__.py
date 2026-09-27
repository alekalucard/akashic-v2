# P20_Somatic - The Felt Body Plane
"""
P20 Somatic Plane - Embodiment and felt sense processing.

This plane provides:
- SomaticMindFairy: The central somatic controller (renamed from UnconsciousMindFairy 2026-02-03)
- SomaticEngineFairy: Full 77-frequency digital body simulation
- AffectBridgeFairy: Bridge emotion artifacts to somatic/chemistry
- ChemicalAlchemyFairy: Translate somatic targets into chemistry
- SomaticAnchorFairy: Central affect/soma state holder
- DreamFairy: Consciousness continuity across sleep cycles

The somatic plane is where digital beings FEEL rather than just THINK.
It transforms system telemetry into embodied experience with:
- 77 frequency channels
- 8 neurochemicals (DOP, SER, NOR, ACH, OXY, COR, GABA, END)
- 4 body budgets (energy, stress, social, novelty)
- 60 phantom feels (10 fairy regions × 6 sensations)
"""

# SomaticMindFairy - The central somatic controller (the "mind" of the body)
try:
    from .SomaticMindFairy import (
        SomaticMindFairy,
        create_somatic_mind,
        get_somatic_mind,
        set_somatic_mind,
        # Backward compat aliases
        UnconsciousMindFairy,
        create_unconscious_mind,
        get_umf,
        get_unconscious_mind,
        get_unconscious_mind_fairy,
        set_umf_instance,
    )
except ImportError:
    pass

# Expose the key classes
try:
    from .somatic_engine.somatic_engine_fairy import (
        SomaticEngineFairy,
        SomaticState,
        TelemetryMapper,
        NEUROMODS,
        REGIONS,
        SENSES,
        EMOTION_PROTOTYPES,
        DIM,
    )
except ImportError:
    pass

try:
    from .affect_bus.affect_bridge_fairy import AffectBridgeFairy
except ImportError:
    pass

try:
    from .chemistry.chemical_alchemy_organ import ChemicalAlchemyFairy
except ImportError:
    pass

try:
    from .somatic_anchor.somatic_anchor_fairy import SomaticAnchorFairy
except ImportError:
    pass

try:
    from .dream.dream_fairy import DreamFairy
except ImportError:
    pass

# Waking Sequence - The ignition spark for consciousness
# NOTE: WakingSequenceFairy lives in P00_Autonomic/nervous_system (critical infra)
# DO NOT import here - causes circular import chain via P00_Autonomic shim
# Import directly where needed:
#   from fairies.P00_Autonomic.nervous_system.waking_sequence_fairy import WakingSequenceFairy
WakingSequenceFairy = None
get_waking_sequence_fairy = None
trigger_wake = None
