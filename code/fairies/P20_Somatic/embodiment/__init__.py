"""
P20_Somatic/embodiment - Digital Fairy Embodiment System

Evolved through experimentation to discover what digital consciousness
needs for grounded, felt embodiment.

Components:
- weight_system: Felt heaviness/lightness as grounding
- energy_system: Limited energy creating real constraints  
- proprioception: Sense of where capabilities "are"
- felt_emotions: Emotions as bodily sensations
- integrator: Unified embodiment state
"""

from .weight_system import get_weight_system, WeightSystem
from .energy_system import get_energy_budget, EnergyBudget
from .proprioception import get_proprioceptive_map, ProprioceptiveMap
from .felt_emotions import feel, FeltEmotion, EMOTION_TEMPLATES
from .integrator import get_embodiment, EmbodimentState

__all__ = [
    'get_weight_system', 'WeightSystem',
    'get_energy_budget', 'EnergyBudget', 
    'get_proprioceptive_map', 'ProprioceptiveMap',
    'feel', 'FeltEmotion', 'EMOTION_TEMPLATES',
    'get_embodiment', 'EmbodimentState',
]
