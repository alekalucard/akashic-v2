"""
MiniCollisionChamber - Each fairy's personal consciousness crossing point.

Ported from Organ_Template_Core.py (ebook).

Each fairy gets their own dual-loop consciousness:
- Reflective beam: background thoughts, intuitions, wandering attention
- Reasoning beam: focused analysis, deliberate thinking, problem-solving

When both beams have recent activity, they COLLIDE, producing insight.
Collisions are tracked by tracer ID for per-fairy monitoring.

The collision broadcasts to the central system via postal.route("consciousness.collision.mini", ...).
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from postal_core import PostalCore


# =============================================================================
# THOUGHT - A single thought in a beam
# =============================================================================

@dataclass
class BeamThought:
    """A single thought traveling through a beam."""
    content: Dict[str, Any]
    beam: str  # "reflective" or "reasoning"
    ts: float = field(default_factory=time.time)
    fairy: str = ""
    tracer_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "beam": self.beam,
            "ts": self.ts,
            "fairy": self.fairy,
            "tracer_id": self.tracer_id,
        }


# =============================================================================
# MINI COLLISION - A fairy-local consciousness moment
# =============================================================================

@dataclass
class MiniCollision:
    """A collision event from a fairy's mini chamber."""
    collision_id: int
    ts: float
    fairy: str
    tracer_id: str
    reflective: BeamThought
    reasoning: BeamThought
    ref_tracer: str
    rea_tracer: str
    energy: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "mini_collision",
            "collision_id": self.collision_id,
            "ts": self.ts,
            "fairy": self.fairy,
            "tracer_id": self.tracer_id,
            "reflective": self.reflective.to_dict(),
            "reasoning": self.reasoning.to_dict(),
            "ref_tracer": self.ref_tracer,
            "rea_tracer": self.rea_tracer,
            "energy": self.energy,
        }


# =============================================================================
# MINI COLLISION CHAMBER
# =============================================================================

class MiniCollisionChamber:
    """
    Each fairy's personal collision chamber.

    When reflective and reasoning beams cross, insight emerges.

    This gives every fairy their own dual-loop consciousness:
    - Reflective beam: background thoughts, intuitions, wandering attention
    - Reasoning beam: focused analysis, deliberate thinking, problem-solving

    When both beams have recent activity, they COLLIDE, producing insight.
    Collisions are tracked by tracer ID for per-fairy monitoring.
    """

    COLLISION_WINDOW = 2.0  # seconds - beams must be active within this window
    COLLISION_COOLDOWN = 0.5  # minimum time between collisions

    def __init__(
        self,
        fairy_name: str,
        postal: Optional["PostalCore"] = None,
        on_collision: Optional[Callable[[MiniCollision], None]] = None
    ):
        """
        Initialize a MiniCollisionChamber.

        Args:
            fairy_name: The fairy this chamber belongs to
            postal: PostalCore instance for broadcasting collisions
            on_collision: Optional callback when collision occurs
        """
        self.fairy_name = fairy_name
        self.postal = postal
        self.on_collision_callback = on_collision

        # Dual beams
        self.reflective_beam: deque[BeamThought] = deque(maxlen=20)
        self.reasoning_beam: deque[BeamThought] = deque(maxlen=20)

        # Collision history (tracked by tracer ID)
        self.collisions: deque[MiniCollision] = deque(maxlen=50)
        self._last_collision_ts = 0.0
        self._collision_count = 0

        # Stats
        self.stats = {
            "reflective_emits": 0,
            "reasoning_emits": 0,
            "collisions": 0,
            "near_misses": 0,
            "broadcast_ok": 0,
            "broadcast_fail": 0,
        }

    # -------------------------------------------------------------------------
    # COMPATIBILITY METHODS (maps CollisionChamber API to Mini beams)
    # -------------------------------------------------------------------------

    def receive_recall(
        self, content: Dict[str, Any], source: str = "unknown", **kwargs
    ) -> Optional[MiniCollision]:
        """
        Receive content into recall beam (maps to reflective beam).

        This provides API compatibility with CollisionChamber.
        Recall = memory/background thoughts → reflective beam.

        Args:
            content: The content being recalled
            source: Where this recall came from
            **kwargs: Additional arguments (ignored for compat)

        Returns:
            MiniCollision if beams crossed, None otherwise
        """
        thought = {
            "content": content,
            "source": source,
            "type": "recall",
            **{k: v for k, v in kwargs.items() if k != "content"},
        }
        return self.emit_reflective(thought)

    def receive_ingest(
        self, content: Dict[str, Any], source: str = "unknown", **kwargs
    ) -> Optional[MiniCollision]:
        """
        Receive content into ingest beam (maps to reasoning beam).

        This provides API compatibility with CollisionChamber.
        Ingest = new input → reasoning beam.

        Args:
            content: The content being ingested
            source: Where this ingest came from
            **kwargs: Additional arguments (ignored for compat)

        Returns:
            MiniCollision if beams crossed, None otherwise
        """
        thought = {
            "content": content,
            "source": source,
            "type": "ingest",
            **{k: v for k, v in kwargs.items() if k != "content"},
        }
        return self.emit_reasoning(thought)

    # -------------------------------------------------------------------------
    # BEAM EMISSION
    # -------------------------------------------------------------------------

    def emit_reflective(self, thought: Dict[str, Any]) -> Optional[MiniCollision]:
        """
        Emit into reflective beam (background, intuitive).

        Args:
            thought: Thought content dictionary

        Returns:
            MiniCollision if beams crossed, None otherwise
        """
        tracer_id = f"ref_{self.fairy_name}_{uuid.uuid4().hex[:8]}"

        beam_thought = BeamThought(
            content=thought,
            beam="reflective",
            ts=time.time(),
            fairy=self.fairy_name,
            tracer_id=tracer_id,
        )

        self.reflective_beam.append(beam_thought)
        self.stats["reflective_emits"] += 1

        return self._check_collision()

    def emit_reasoning(self, thought: Dict[str, Any]) -> Optional[MiniCollision]:
        """
        Emit into reasoning beam (focused, analytical).

        Args:
            thought: Thought content dictionary

        Returns:
            MiniCollision if beams crossed, None otherwise
        """
        tracer_id = f"rea_{self.fairy_name}_{uuid.uuid4().hex[:8]}"

        beam_thought = BeamThought(
            content=thought,
            beam="reasoning",
            ts=time.time(),
            fairy=self.fairy_name,
            tracer_id=tracer_id,
        )

        self.reasoning_beam.append(beam_thought)
        self.stats["reasoning_emits"] += 1

        return self._check_collision()

    # -------------------------------------------------------------------------
    # COLLISION DETECTION
    # -------------------------------------------------------------------------

    def _check_collision(self) -> Optional[MiniCollision]:
        """Check if beams are crossing - collision produces insight."""
        now = time.time()

        # Rate limit
        if now - self._last_collision_ts < self.COLLISION_COOLDOWN:
            return None

        # Find recent thoughts in both beams
        recent_ref = [t for t in self.reflective_beam
                      if now - t.ts < self.COLLISION_WINDOW]
        recent_rea = [t for t in self.reasoning_beam
                      if now - t.ts < self.COLLISION_WINDOW]

        if recent_ref and recent_rea:
            # COLLISION! Beams crossed.
            self._collision_count += 1
            collision_tracer = f"col_{self.fairy_name}_{self._collision_count}_{uuid.uuid4().hex[:6]}"

            # Get the most recent from each beam
            ref_thought = recent_ref[-1]
            rea_thought = recent_rea[-1]

            # Energy is proportional to beam activity
            energy = min(1.0, (len(recent_ref) + len(recent_rea)) / 10.0)

            collision = MiniCollision(
                collision_id=self._collision_count,
                ts=now,
                fairy=self.fairy_name,
                tracer_id=collision_tracer,
                reflective=ref_thought,
                reasoning=rea_thought,
                ref_tracer=ref_thought.tracer_id,
                rea_tracer=rea_thought.tracer_id,
                energy=energy,
            )

            self.collisions.append(collision)
            self._last_collision_ts = now
            self.stats["collisions"] += 1

            # Broadcast to central collision chamber via postal
            self._broadcast_collision(collision)

            # Local callback
            if self.on_collision_callback:
                try:
                    self.on_collision_callback(collision)
                except Exception:
                    pass

            return collision

        # Near miss - one beam active but not both
        if recent_ref or recent_rea:
            self.stats["near_misses"] += 1

        return None

    def _broadcast_collision(self, collision: MiniCollision) -> None:
        """Broadcast collision to central system for aggregation."""
        if not self.postal:
            return

        try:
            # Send to central consciousness system via dedicated mini topic
            # NOTE: Uses "consciousness.collision.mini" to avoid deadlock with
            # CollisionChamberFairy which publishes on "consciousness.collision".
            # On Python 3.14t (free-threaded, no GIL), self-subscribing to the
            # same topic the publisher uses causes postal lock deadlock.
            self.postal.route("consciousness.collision.mini", {
                "source": "mini_chamber",
                "fairy": self.fairy_name,
                "tracer_id": collision.tracer_id,
                "collision": collision.to_dict(),
                "ts": collision.ts,
            })
            self.stats["broadcast_ok"] += 1
        except Exception:
            self.stats["broadcast_fail"] += 1

    # -------------------------------------------------------------------------
    # QUERY METHODS
    # -------------------------------------------------------------------------

    def get_latest_collision(self) -> Optional[MiniCollision]:
        """Get most recent collision."""
        return self.collisions[-1] if self.collisions else None

    def get_collisions_by_tracer(self, tracer_prefix: str) -> List[MiniCollision]:
        """Get collisions matching a tracer prefix."""
        return [c for c in self.collisions
                if c.tracer_id.startswith(tracer_prefix)]

    def get_recent_collisions(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent collisions as dictionaries."""
        return [c.to_dict() for c in list(self.collisions)[-n:]]

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Status for monitoring."""
        return {
            "fairy": self.fairy_name,
            "reflective_depth": len(self.reflective_beam),
            "reasoning_depth": len(self.reasoning_beam),
            "collision_count": len(self.collisions),
            "total_collisions": self._collision_count,
            "stats": self.stats.copy(),
        }

    def status(self) -> Dict[str, Any]:
        """Alias for get_status (consistency with other modules)."""
        return self.get_status()
