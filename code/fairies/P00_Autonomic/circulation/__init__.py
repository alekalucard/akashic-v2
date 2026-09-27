"""
P00_Autonomic Circulation - Autonomic Timing Infrastructure

This module contains the core timing and rhythm infrastructure that
all planes depend on. These are substrate-level components:

- CircadianPacemakerFairy: The SCN - generates temporal dimension
- TemporalDispatcherFairy: Fans heartbeat to plane-specific frequencies
- temporal_core: Base frequencies and coupling math

The heart (CirculationPumpFairy) remains in P20_Somatic as the somatic
beat generator, but these infrastructure components live here because
they are system-wide primitives that must boot before consciousness.

Philosophy: ((Cause + Affect) > Effect > Affect > infinity)
- Time is not external metadata, it's the substrate of felt experience
- P00 generates time; P20 feels it; P30 thinks in it

ARCHITECTURAL LAYERING:
- temporal_core (P00): Pure timing math - frequencies, bands, coupling
- temporal_stratification (P20): Adds somatic modulation (arousal, circadian)

This separation allows P30 fairies to import timing from P00 without
creating upward dependencies to P20.
"""

from .temporal_core import (
    # Enums and Constants
    TemporalBand,
    PLANE_FREQUENCIES,
    FAIRY_FREQUENCIES,
    DEFAULT_COUPLINGS,

    # Dataclasses
    TemporalCoupling,
    FairyTiming,

    # Core Engine
    TemporalEngine,

    # Singleton & Functions
    get_temporal_engine,
    get_tick_interval,
    tempo_aware_sleep,
    register_fairy_timing,
    get_plane_frequency,
    get_fairy_frequency,
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

from .temporal_dispatcher_fairy import (
    TemporalDispatcherFairy,
    TemporalDispatcherFairyShadow,
)

from .time_sense_fairy import (
    TimeSenseFairy,
    TimeSenseFairyShadow,
)

from .habit_consultant_fairy import (
    HabitConsultantFairy,
    HabitConsultantFairyShadow,
)

__all__ = [
    # temporal_core - Enums and Constants
    'TemporalBand',
    'PLANE_FREQUENCIES',
    'FAIRY_FREQUENCIES',
    'DEFAULT_COUPLINGS',

    # temporal_core - Dataclasses
    'TemporalCoupling',
    'FairyTiming',

    # temporal_core - Core Engine
    'TemporalEngine',

    # temporal_core - Singleton & Functions
    'get_temporal_engine',
    'get_tick_interval',
    'tempo_aware_sleep',
    'register_fairy_timing',
    'get_plane_frequency',
    'get_fairy_frequency',

    # CircadianPacemakerFairy
    'CircadianPacemakerFairy',
    'CircadianState',
    'GoalMemory',
    'get_circadian_pacemaker',
    'DEFAULT_TIMEZONE',
    'PHASES',
    'PHASE_CHEMISTRY',
    'PHASE_TICK_MODULATION',
    'PHASE_DRIVE_MODULATION',

    # TemporalDispatcherFairy
    'TemporalDispatcherFairy',
    'TemporalDispatcherFairyShadow',

    # TimeSenseFairy
    'TimeSenseFairy',
    'TimeSenseFairyShadow',

    # HabitConsultantFairy (Phase 4)
    'HabitConsultantFairy',
    'HabitConsultantFairyShadow',
]
