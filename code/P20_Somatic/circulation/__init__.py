# P20_Somatic.circulation - Re-export shim for akashic_v2
# Forwards all imports to fairies.P20_Somatic.circulation for backward compatibility
"""
Circulation System - Heart, Circadian Rhythm, and Temporal Stratification.

This shim forwards imports to the canonical location at fairies.P20_Somatic.circulation.
"""

# Re-export everything from fairies.P20_Somatic.circulation
from fairies.P20_Somatic.circulation import *

# Explicitly import for IDE support
try:
    from fairies.P20_Somatic.circulation import (
        # Circulation
        CirculationPumpFairy,
        BloodState,
        RegionState,
        PulseEvent,
        NEUROCHEMICALS,
        BODY_REGIONS,
        # Circadian
        CircadianPacemakerFairy,
        CircadianState,
        GoalMemory,
        get_circadian_pacemaker,
        DEFAULT_TIMEZONE,
        PHASES,
        PHASE_CHEMISTRY,
        PHASE_TICK_MODULATION,
        PHASE_DRIVE_MODULATION,
        # Temporal Stratification
        TemporalEngine,
        TemporalBand,
        TemporalCoupling,
        FairyTiming,
        PLANE_FREQUENCIES,
        FAIRY_FREQUENCIES,
        get_temporal_engine,
        get_tick_interval,
        tempo_aware_sleep,
        register_fairy_timing,
        # Waking Sequence
        WakingSequenceFairy,
        get_waking_sequence_fairy,
        trigger_wake,
    )
except ImportError:
    pass
