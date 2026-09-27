"""
Cores - The three processing modes of cognition.

Like strands in a DNA helix, these cores interweave:
- CognitiveCore: Rational thought, planning, execution
- IrrationalCore: Intuition, hunches, gut feelings
- ParadoxCore: Holds contradictions, synthesizes creative solutions

They don't compete - they INTERWEAVE. Each output feeds into the others.
"""

from .cognitive_core import CognitiveCore, CognitiveOutput
from .irrational_core import IrrationalCore, Hunch, HunchSource
from .paradox_core import ParadoxCore, Contradiction, Synthesis

__all__ = [
    "CognitiveCore",
    "CognitiveOutput",
    "IrrationalCore",
    "Hunch",
    "HunchSource",
    "ParadoxCore",
    "Contradiction",
    "Synthesis",
]
