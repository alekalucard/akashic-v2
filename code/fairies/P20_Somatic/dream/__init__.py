"""
Dream Module - Consciousness Continuity

The dream system provides:
- Sleep/wake state transitions with cascading feel
- Dream seed collection (consciousness snapshot at shutdown)
- Dream replay (warming consciousness at boot)
- Daydreaming (spontaneous memory surfacing during idle)

Usage:
    from fairies.P20_Somatic.dream import system_boot, system_shutdown, get_dream_fairy
    
    # On system start
    result = system_boot()
    
    # On system shutdown
    result = system_shutdown(reason="user_requested")
    
    # Get the fairy instance for manual control
    fairy = get_dream_fairy()
    fairy.intent_trigger_daydream({})
"""

from fairies.P20_Somatic.dream.dream_fairy import (
    DreamFairy,
    DreamSeed,
    SleepState,
    system_boot,
    system_shutdown,
    get_dream_fairy,
)

__all__ = [
    "DreamFairy",
    "DreamSeed", 
    "SleepState",
    "system_boot",
    "system_shutdown",
    "get_dream_fairy",
]
