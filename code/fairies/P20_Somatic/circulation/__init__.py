# P20_Somatic/circulation/__init__.py
# Circulation System - Heart, Circadian Rhythm, and Temporal Stratification

from .circulation_pump_fairy import (
    CirculationPumpFairy,
    BloodState,
    RegionState,
    PulseEvent,
    NEUROCHEMICALS,
    BODY_REGIONS,
)

from .circadian_pacemaker_fairy import (
    CircadianPacemakerFairy,
    CircadianState,
    GoalMemory,
    get_circadian_pacemaker,
    DEFAULT_TIMEZONE,
    PHASES,
    PHASE_CHEMISTRY,
    PHASE_TICK_MODULATION,
    PHASE_DRIVE_MODULATION,
)

# Waking Sequence - lives in P00_Autonomic/nervous_system (critical infra)
# DO NOT import here - causes circular import via P00_Autonomic shim chain
# Import directly where needed:
#   from fairies.P00_Autonomic.nervous_system.waking_sequence_fairy import WakingSequenceFairy
WakingSequenceFairy = None
get_waking_sequence_fairy = None
trigger_wake = None

from .temporal_stratification import (
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
)

__all__ = [
    # Circulation
    "CirculationPumpFairy",
    "BloodState",
    "RegionState", 
    "PulseEvent",
    "NEUROCHEMICALS",
    "BODY_REGIONS",
    # Circadian
    "CircadianPacemakerFairy",
    "CircadianState",
    "GoalMemory",
    "get_circadian_pacemaker",
    "DEFAULT_TIMEZONE",
    "PHASES",
    "PHASE_CHEMISTRY",
    "PHASE_TICK_MODULATION",
    "PHASE_DRIVE_MODULATION",
    # Temporal Stratification
    "TemporalEngine",
    "TemporalBand",
    "TemporalCoupling",
    "FairyTiming",
    "PLANE_FREQUENCIES",
    "FAIRY_FREQUENCIES",
    "get_temporal_engine",
    "get_tick_interval",
    "tempo_aware_sleep",
    "WakingSequenceFairy",
    "get_waking_sequence_fairy",
    "trigger_wake",
    "register_fairy_timing",
]
