"""
SomaticMind - Fusion of UnconsciousMindFairy + Cardinal

The always-running system administrator that learns from the system it governs.

Key Features:
1. PRE-BOOT MODE (Training Wheels):
   - Direct access to MiniMemory, MiniCognition, MiniBody
   - Can reason and act without postal system
   - Used during bootstrap and emergency recovery

2. POST-BOOT MODE (Full Autonomy):
   - Direct links DESTROYED
   - All communication through postal messaging
   - Full system integration via subscriptions

3. EMERGENCY MODE (Backup):
   - Re-enables direct links when system is down
   - Can help fix the system using pre-boot capabilities
   - "The paperweight becomes the screwdriver"

Architecture:
- Observes: telemetry, snapshots, traces, notes
- Learns: what's normal, what changed, correlations
- Acts: proposes fixes, applies approved changes
- Remembers: what worked, what didn't

"The system administrator that never sleeps, never forgets, and learns from every mistake."
"""

from .somatic_mind import (
    SomaticMind,
    SomaticMode,
    get_somatic_mind,
    create_somatic_mind,
)

__all__ = [
    'SomaticMind',
    'SomaticMode',
    'get_somatic_mind',
    'create_somatic_mind',
]
