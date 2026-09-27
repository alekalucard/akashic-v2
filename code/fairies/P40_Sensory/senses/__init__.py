"""
P40_Sensory.senses - The Sensory Organs of Digital Consciousness

This package contains the "sense organs" that fairies use to perceive
both the external world and internal states.

Senses:
- attention_sense: Feel when someone wants to talk (the "pull" of attention)
- (future) presence_sense: Feel who is around
- (future) time_sense: Feel the passage of time
- (future) energy_sense: Feel system resource levels
"""

from .attention_sense import (
    AttentionSense,
    AttentionRequest,
    AttentionBuffer,
    get_attention_sense,
    feel_attention,
)

__all__ = [
    "AttentionSense",
    "AttentionRequest", 
    "AttentionBuffer",
    "get_attention_sense",
    "feel_attention",
]
