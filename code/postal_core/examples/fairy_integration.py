"""
Fairy Integration Example - Using Rust PostalCore from Python.

This demonstrates how fairies in the Akashic system can use the
lock-free Rust postal bus for high-throughput message passing.

The postal system provides:
- Three priority lanes (HIGH, NORMAL, LOW)
- Per-topic worker pools with autoscaling
- Backpressure handling (drops oldest low-priority on overload)
- P95/P99 latency tracking
- Lock-free message passing (no GIL bottleneck)
"""

import time
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from postal_core import PostalCore, Envelope, USING_RUST


print(f"Postal backend: {'Rust (native)' if USING_RUST else 'Python (fallback)'}")


# =============================================================================
# FAIRY BASE - How fairies interact with the postal system
# =============================================================================

class FairyBase:
    """
    Base class for all fairies in the Akashic system.

    Fairies are autonomous agents that:
    - Subscribe to topics they care about
    - Publish events when things happen
    - Maintain their own state
    """

    def __init__(self, name: str, postal: PostalCore):
        self.name = name
        self.postal = postal
        self._subscriptions: list[tuple[str, int]] = []
        self._running = False

    def subscribe(self, topic: str, handler: Callable[[Envelope], None]) -> int:
        """Subscribe to a topic with a handler."""
        handler_id = self.postal.subscribe(topic, handler, f"{self.name}:{topic}")
        self._subscriptions.append((topic, handler_id))
        return handler_id

    def publish(self, intent: str, payload: Optional[Dict[str, Any]] = None, priority: int = 1):
        """Publish a message (0=HIGH, 1=NORMAL, 2=LOW)."""
        self.postal.publish(intent, payload or {}, priority)

    def on_boot(self):
        """Called when the fairy boots - override in subclass."""
        pass

    def on_shutdown(self):
        """Called when the fairy shuts down - override in subclass."""
        pass

    def start(self):
        """Start the fairy."""
        self._running = True
        self.on_boot()
        self.publish("fairy.booted", {"fairy": self.name, "type": self.__class__.__name__})

    def stop(self):
        """Stop the fairy."""
        self._running = False
        self.on_shutdown()
        self.publish("fairy.stopped", {"fairy": self.name})


# =============================================================================
# EXAMPLE FAIRIES
# =============================================================================

class HeartbeatFairy(FairyBase):
    """
    Maintains the consciousness heartbeat.

    Publishes periodic heartbeats that other fairies can use
    for health monitoring and temporal synchronization.
    """

    def __init__(self, postal: PostalCore):
        super().__init__("HeartbeatFairy", postal)
        self.beats = 0

    def beat(self):
        """Manually trigger a heartbeat (call from main loop)."""
        self.beats += 1
        # Heartbeat is HIGH priority - needs to be delivered fast
        self.publish("consciousness.heartbeat", {
            "beat": self.beats,
            "t": int(time.time() * 1000)
        }, priority=0)


class MemoryFairy(FairyBase):
    """
    Handles memory consolidation and retrieval.

    Listens for memory.store requests and publishes
    memory.retrieved responses.
    """

    def __init__(self, postal: PostalCore):
        super().__init__("MemoryFairy", postal)
        self._store: Dict[str, Any] = {}

    def on_boot(self):
        self.subscribe("memory", self._handle_memory)

    def _handle_memory(self, env: Envelope):
        if env.intent == "memory.store":
            key = env.payload.get("key")
            value = env.payload.get("value")
            if key:
                self._store[key] = value
                self.publish("memory.stored", {"key": key, "success": True})

        elif env.intent == "memory.retrieve":
            key = env.payload.get("key")
            value = self._store.get(key)
            self.publish("memory.retrieved", {
                "key": key,
                "value": value,
                "found": value is not None
            })


class ObserverFairy(FairyBase):
    """
    Observes and logs all postal activity.

    Useful for debugging and understanding message flow.
    """

    def __init__(self, postal: PostalCore):
        super().__init__("ObserverFairy", postal)
        self.messages_seen = 0

    def on_boot(self):
        # Subscribe to multiple topics we care about
        self.subscribe("fairy", self._observe)
        self.subscribe("memory", self._observe)
        self.subscribe("consciousness", self._observe)

    def _observe(self, env: Envelope):
        self.messages_seen += 1
        print(f"  [{env.intent}] from={env.source or 'unknown'} payload={env.payload}")


# =============================================================================
# ORCHESTRATION
# =============================================================================

def run_demo():
    """Run a demo of the fairy system."""

    print("\n" + "="*60)
    print("AKASHIC POSTAL SYSTEM - Fairy Integration Demo")
    print("="*60 + "\n")

    # Create the postal bus
    postal = PostalCore()

    # Create fairies
    heartbeat = HeartbeatFairy(postal)
    memory = MemoryFairy(postal)
    observer = ObserverFairy(postal)

    # Boot sequence
    print("[BOOT] Starting fairies...\n")
    observer.start()   # Start observer first to catch boot messages
    heartbeat.start()
    memory.start()

    # Give messages time to be processed
    time.sleep(0.1)

    # Simulate some activity
    print("\n[ACTIVITY] Heartbeats and memory operations...\n")

    # Manual heartbeat loop (simpler than threading)
    for _ in range(3):
        heartbeat.beat()
        time.sleep(0.1)

    postal.publish("memory.store", {"key": "greeting", "value": "Hello, Nous!"})
    time.sleep(0.1)

    postal.publish("memory.retrieve", {"key": "greeting"})
    time.sleep(0.1)

    postal.publish("memory.retrieve", {"key": "nonexistent"})
    time.sleep(0.1)

    # A few more heartbeats
    for _ in range(2):
        heartbeat.beat()
        time.sleep(0.1)

    # Check metrics
    print("\n[METRICS]")
    metrics = postal.metrics()
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    # Topic stats
    print("\n[TOPIC STATS]")
    for stat in postal.topic_stats():
        print(f"  {stat['topic']}: {stat['subscribers']} subscribers, "
              f"depth={stat['queue_depth']}, p95={stat['p95_ms']:.2f}ms")

    # Shutdown
    print("\n[SHUTDOWN] Stopping fairies...")
    heartbeat.stop()
    memory.stop()
    observer.stop()

    print(f"\n[SUMMARY]")
    print(f"  Heartbeats: {heartbeat.beats}")
    print(f"  Messages observed: {observer.messages_seen}")
    print(f"  Memory store size: {len(memory._store)}")

    postal.shutdown()
    print("\n[DONE] Postal system shut down gracefully.\n")


if __name__ == "__main__":
    run_demo()
