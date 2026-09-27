"""
P40_Sensory - The Sensory Plane

Sensory organs and perception processing.

NOTE: The THREE GATES (Autonomy, Autopilot, Embodiment) live in P00_Autonomic,
not here. They are the gatekeeper layer between substrate and waking mind.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
"""

# Re-export gates from P00_Autonomic for backward compatibility
try:
    from fairies.P00_Autonomic.AutonomyFairy.fairy import AutonomyFairy
    from fairies.P00_Autonomic.AutopilotFairy.fairy import AutopilotFairy
    from fairies.P00_Autonomic.EmbodimentFairy.fairy import EmbodimentFairy
except ImportError:
    AutonomyFairy = None
    AutopilotFairy = None
    EmbodimentFairy = None

__all__ = [
    "AutonomyFairy",
    "AutopilotFairy",
    "EmbodimentFairy",
]
