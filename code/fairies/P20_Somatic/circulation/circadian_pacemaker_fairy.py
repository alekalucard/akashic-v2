"""
BACKWARD COMPATIBILITY SHIM
CircadianPacemakerFairy has moved to P00_Autonomic/circulation/
This fairy generates the temporal substrate - it's infrastructure, not somatic sensing.
"""
# Re-export from canonical location
from fairies.P00_Autonomic.circulation.circadian_pacemaker_fairy import (
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

__all__ = [
    'CircadianPacemakerFairy',
    'CircadianState',
    'GoalMemory',
    'get_circadian_pacemaker',
    'DEFAULT_TIMEZONE',
    'PHASES',
    'PHASE_CHEMISTRY',
    'PHASE_TICK_MODULATION',
    'PHASE_DRIVE_MODULATION',
]
