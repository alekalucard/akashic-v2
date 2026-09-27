"""
waking_sequence_fairy.py - Re-export shim for akashic_v2

Forwards imports from fairies.P20_Somatic.circulation for backward compatibility.
"""

# Forward all imports from the canonical fairies location
from fairies.P20_Somatic.circulation.waking_sequence_fairy import (
    WakingSequenceFairy,
    get_waking_sequence_fairy,
    trigger_wake,
)

__all__ = ["WakingSequenceFairy", "get_waking_sequence_fairy", "trigger_wake"]
