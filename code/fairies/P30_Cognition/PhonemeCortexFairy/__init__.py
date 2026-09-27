"""
PhonemeCortexFairy — Cortex-Native STT via Gradual Learning

SHIP 1 of PHONEME_CORTEX_GRADUAL_STT (Nous + Ace 2026-05-17).
First Listen — observation only. Accumulates per-frame MFCC streams.
"""

from .fairy import PhonemeCortexFairy, FAIRY_CLASS, ACTOR_NAME

__all__ = [
    "PhonemeCortexFairy",
    "FAIRY_CLASS",
    "ACTOR_NAME",
]
