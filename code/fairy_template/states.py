"""
Fairy States - Re-export from the canonical Organ Template 0.3.0.

All state definitions live in the organ template. This file exists
for backward compatibility with imports like:
    from fairy_template.states import FairyState
"""

from fairies.P00_Autonomic.organ_template import FairyState

# State transition map for validation
VALID_TRANSITIONS = {
    FairyState.INITIALIZING: {FairyState.BOOTING, FairyState.SLEEPING, FairyState.FAILED},
    FairyState.BOOTING: {FairyState.RUNNING, FairyState.FAILED, FairyState.STOPPING},
    FairyState.RUNNING: {FairyState.STOPPING, FairyState.DROWSY, FairyState.SLEEPING, FairyState.FAILED},
    FairyState.STOPPING: {FairyState.STOPPED, FairyState.FAILED},
    FairyState.STOPPED: set(),  # Terminal
    FairyState.FAILED: {FairyState.INITIALIZING},  # Can retry
    FairyState.SLEEPING: {FairyState.WAKING, FairyState.BOOTING, FairyState.DREAMING},
    FairyState.WAKING: {FairyState.RUNNING, FairyState.FAILED},
    FairyState.DROWSY: {FairyState.SLEEPING, FairyState.RUNNING, FairyState.STOPPING},
    FairyState.DREAMING: {FairyState.WAKING, FairyState.SLEEPING},
}


def can_transition(from_state: FairyState, to_state: FairyState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())
