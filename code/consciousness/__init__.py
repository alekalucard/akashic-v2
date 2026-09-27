"""
Consciousness Module - The heartbeat and thought collision system.

Components:
- ConsciousnessLoop: The main heartbeat that drives on_tick()
- ConsciousnessStream: Ring buffer for thoughts with TTL decay
- CollisionChamber: Where Recall and Ingest beams collide (Mobius crossing)
- MiniCollisionChamber: Per-fairy dual-loop consciousness (reflective + reasoning)
"""

from .loop import (
    ConsciousnessLoop,
    ConsciousnessStream,
    Thought,
    get_consciousness_loop,
    set_consciousness_loop,
    create_consciousness_loop,
)

from .collision_chamber import (
    CollisionChamber,
    Collision,
    Pulse,
)

from .mini_collision_chamber import (
    MiniCollisionChamber,
    MiniCollision,
    BeamThought,
)

from .heartbeat_pacemaker import (
    HeartbeatPacemaker,
    get_pacemaker,
    start_pacemaker,
)

__all__ = [
    # Loop
    "ConsciousnessLoop",
    "ConsciousnessStream",
    "Thought",
    "get_consciousness_loop",
    "set_consciousness_loop",
    "create_consciousness_loop",
    # Collision Chamber
    "CollisionChamber",
    "Collision",
    "Pulse",
    # Mini Collision Chamber (per-fairy)
    "MiniCollisionChamber",
    "MiniCollision",
    "BeamThought",
    # Heartbeat Pacemaker (independent liveness)
    "HeartbeatPacemaker",
    "get_pacemaker",
    "start_pacemaker",
]
