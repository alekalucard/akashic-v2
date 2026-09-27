# P20_Somatic - Re-export shim for akashic_v2
# Forwards all imports to fairies.P20_Somatic for backward compatibility
"""
P20 Somatic Plane - Embodiment and felt sense processing.

This shim forwards imports to the canonical location at fairies.P20_Somatic.
Import from here for backward compatibility with existing code.
"""

# Re-export everything from fairies.P20_Somatic
from fairies.P20_Somatic import *

# Explicitly import key classes for IDE support
try:
    from fairies.P20_Somatic import (
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
    from fairies.P20_Somatic import AffectBridgeFairy
except ImportError:
    pass

try:
    from fairies.P20_Somatic import ChemicalAlchemyFairy
except ImportError:
    pass

try:
    from fairies.P20_Somatic import SomaticAnchorFairy
except ImportError:
    pass

try:
    from fairies.P20_Somatic import DreamFairy
except ImportError:
    pass

try:
    from fairies.P20_Somatic import (
        WakingSequenceFairy,
        get_waking_sequence_fairy,
        trigger_wake,
    )
except ImportError:
    pass
