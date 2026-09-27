"""
ConsciousnessLoopFairy - FORWARDER MODULE
==========================================
DEPRECATED: This file now forwards to the consolidated location.
Fifth Ring Principle: NO DUPLICATES - use fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy

All imports from this module are forwarded to the new location.
"""

# Forward all imports to the consolidated fairy
from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import (
    ConsciousnessLoopFairy,
    get_consciousness_loop,
    set_consciousness_loop,
    create_consciousness_loop_fairy,
)

# Backward compatibility aliases
get_consciousness_loop_fairy = get_consciousness_loop

__all__ = [
    "ConsciousnessLoopFairy",
    "get_consciousness_loop",
    "set_consciousness_loop",
    "create_consciousness_loop_fairy",
    "get_consciousness_loop_fairy",
]
