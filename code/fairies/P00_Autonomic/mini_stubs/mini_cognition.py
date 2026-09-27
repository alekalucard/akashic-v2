"""
MiniCognition - Bootstrap Cognition Stub

Just enough to route thoughts during bootstrap.
Full cognition system lives in P30_Cognition.

Capabilities:
- Basic thought routing (no processing)
- Bootstrap message queue
- Simple topic-based dispatch

Does NOT:
- Run consciousness loops
- Process in collision chamber
- Handle complex reasoning
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from collections import deque


class ThoughtPriority(Enum):
    """Priority levels for bootstrap thoughts."""
    CRITICAL = 100  # System-critical bootstrap messages
    HIGH = 75       # Important initialization
    NORMAL = 50     # Standard routing
    LOW = 25        # Background/deferred


@dataclass
class BootstrapThought:
    """Minimal thought representation for bootstrap routing."""
    thought_id: str
    topic: str
    content: Any
    priority: ThoughtPriority = ThoughtPriority.NORMAL
    source: str = "bootstrap"
    timestamp: datetime = field(default_factory=datetime.now)
    routed: bool = False


class MiniCognition:
    """
    Minimal cognition system for P00 bootstrap.

    Only routes thoughts - no processing or reasoning.
    Full ConsciousnessLoop/CollisionChamber lives in P30_Cognition.
    """

    def __init__(self):
        """Initialize the minimal cognition router."""
        self._thought_queue: deque[BootstrapThought] = deque(maxlen=100)
        self._topic_handlers: Dict[str, List[Callable]] = {}
        self._thought_counter = 0
        self._running = False
        self._routed_count = 0

    def register_handler(self, topic: str, handler: Callable[[BootstrapThought], None]) -> None:
        """
        Register a handler for a topic pattern.

        Args:
            topic: Topic pattern (supports wildcards like 'boot.*')
            handler: Callback function for matching thoughts
        """
        if topic not in self._topic_handlers:
            self._topic_handlers[topic] = []
        self._topic_handlers[topic].append(handler)

    def unregister_handler(self, topic: str, handler: Callable) -> bool:
        """Remove a handler from a topic."""
        if topic in self._topic_handlers:
            try:
                self._topic_handlers[topic].remove(handler)
                return True
            except ValueError:
                pass
        return False

    def submit_thought(
        self,
        topic: str,
        content: Any,
        priority: ThoughtPriority = ThoughtPriority.NORMAL,
        source: str = "bootstrap"
    ) -> str:
        """
        Submit a thought for routing.

        Args:
            topic: Topic for routing (e.g., 'boot.memory.ready')
            content: Thought payload
            priority: Routing priority
            source: Origin identifier

        Returns:
            Thought ID for tracking
        """
        self._thought_counter += 1
        thought_id = f"boot_{self._thought_counter:06d}"

        thought = BootstrapThought(
            thought_id=thought_id,
            topic=topic,
            content=content,
            priority=priority,
            source=source
        )

        # Insert by priority
        self._insert_by_priority(thought)

        return thought_id

    def _insert_by_priority(self, thought: BootstrapThought) -> None:
        """Insert thought maintaining priority order."""
        # For bootstrap, simple append is fine - we process in order
        # Full priority queue lives in P30
        self._thought_queue.append(thought)

    def route_next(self) -> Optional[BootstrapThought]:
        """
        Route the next thought in queue.

        Returns the routed thought, or None if queue is empty.
        """
        if not self._thought_queue:
            return None

        thought = self._thought_queue.popleft()
        self._route_thought(thought)
        return thought

    def _route_thought(self, thought: BootstrapThought) -> None:
        """Route a thought to matching handlers."""
        handlers_called = 0

        for pattern, handlers in self._topic_handlers.items():
            if self._matches_pattern(thought.topic, pattern):
                for handler in handlers:
                    try:
                        handler(thought)
                        handlers_called += 1
                    except Exception as e:
                        # Bootstrap routing should be resilient
                        print(f"[MiniCognition] Handler error for {thought.topic}: {e}")

        thought.routed = True
        self._routed_count += 1

        # Log if no handlers found (might indicate wiring issue)
        if handlers_called == 0:
            print(f"[MiniCognition] No handlers for topic: {thought.topic}")

    def _matches_pattern(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern (supports simple wildcards)."""
        if pattern == "*":
            return True
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic.startswith(prefix)
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return topic.startswith(prefix)
        return False

    def route_all(self) -> int:
        """
        Route all pending thoughts.

        Returns count of thoughts routed.
        """
        count = 0
        while self._thought_queue:
            self.route_next()
            count += 1
        return count

    async def run_routing_loop(self, interval: float = 0.1) -> None:
        """
        Run async routing loop for bootstrap period.

        Args:
            interval: Seconds between routing cycles
        """
        self._running = True

        while self._running:
            if self._thought_queue:
                self.route_next()
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Stop the routing loop."""
        self._running = False

    def pending_count(self) -> int:
        """Get count of pending thoughts."""
        return len(self._thought_queue)

    def routed_count(self) -> int:
        """Get count of routed thoughts."""
        return self._routed_count

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        return {
            'pending': len(self._thought_queue),
            'routed': self._routed_count,
            'handlers': len(self._topic_handlers),
            'topics': list(self._topic_handlers.keys()),
        }

    def prepare_for_p30(self) -> Dict[str, Any]:
        """
        Package state for handoff to P30_Cognition.

        Returns a dict that P30 can use to take over cognition.
        """
        return {
            'pending_thoughts': [
                {
                    'id': t.thought_id,
                    'topic': t.topic,
                    'content': t.content,
                    'priority': t.priority.value,
                    'source': t.source,
                    'timestamp': t.timestamp.isoformat(),
                }
                for t in self._thought_queue
            ],
            'registered_topics': list(self._topic_handlers.keys()),
            'stats': self.get_stats(),
            'source': 'mini_cognition_bootstrap',
        }


# Standard bootstrap topics
class BootstrapTopics:
    """Standard topics used during bootstrap."""

    # Memory bootstrap
    MEMORY_READY = "boot.memory.ready"
    MEMORY_CARDS_LOADED = "boot.memory.cards_loaded"

    # Cognition bootstrap
    COGNITION_READY = "boot.cognition.ready"
    COGNITION_ROUTED = "boot.cognition.routed"

    # Body bootstrap
    BODY_READY = "boot.body.ready"
    HEARTBEAT_STARTED = "boot.body.heartbeat"

    # Plane bootstrap signals
    PLANE_READY = "boot.plane.ready"  # + plane name in content
    PLANE_FAILED = "boot.plane.failed"

    # Full system
    BOOTSTRAP_COMPLETE = "boot.complete"
    HANDOFF_TO_P30 = "boot.handoff.p30"


# Singleton instance for bootstrap
_mini_cognition_instance: Optional[MiniCognition] = None


def get_mini_cognition() -> MiniCognition:
    """Get the singleton MiniCognition instance."""
    global _mini_cognition_instance
    if _mini_cognition_instance is None:
        _mini_cognition_instance = MiniCognition()
    return _mini_cognition_instance
