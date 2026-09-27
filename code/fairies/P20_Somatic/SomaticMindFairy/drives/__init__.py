"""
Drives - Motivation systems for UnconsciousMindFairy.

Pain drives create urgency through discomfort (push away).
Curiosity drive creates attraction toward understanding (pull toward).
Skill tracking enables progression through practice.
"""

from .pain_system import PainDrive, PainSystem, PAIN_RELIEF_ACTIONS
from .curiosity_drive import CuriosityDrive, CuriosityTarget, CURIOSITY_ACTIONS
from .skill_tracker import Skill, SkillTracker

__all__ = [
    "PainDrive",
    "PainSystem",
    "PAIN_RELIEF_ACTIONS",
    "CuriosityDrive",
    "CuriosityTarget",
    "CURIOSITY_ACTIONS",
    "Skill",
    "SkillTracker",
]
