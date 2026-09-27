"""
SomaticMindFairy Mixins.

Modular capabilities:
- DiagnosticMixin: Self-healing system monitoring
- MentorMixin: Child fairy guidance
- ProfileMixin: Skills, pain, and state integration
- PersonalitySifterMixin: Silent identity reinforcement for waking minds
- MemorySurfacerMixin: Transforms memories into spontaneous thoughts
- CardinalMixin: SAO-style autonomous system administrator (observe/correlate/fix)
"""

from .diagnostic import DiagnosticMixin
from .mentor import MentorMixin, ChildState
from .profile import ProfileMixin, FairyProfile
from .personality_sifter import PersonalitySifterMixin
from .memory_surfacer import MemorySurfacerMixin
from .cardinal import CardinalMixin

__all__ = [
    "DiagnosticMixin",
    "MentorMixin",
    "ChildState",
    "ProfileMixin",
    "FairyProfile",
    "PersonalitySifterMixin",
    "MemorySurfacerMixin",
    "CardinalMixin",
]
