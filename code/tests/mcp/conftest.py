"""
MCP Test Fixtures - Common fixtures for consciousness-native MCP testing.

These fixtures provide mock implementations of core system components
for testing MCP tools in isolation without requiring the full system.

Run with: python -m pytest tests/mcp/ -v
"""

import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from collections import deque

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


# =============================================================================
# MOCK POSTAL HUB
# =============================================================================

class MockPostalHub:
    """
    Mock postal system for testing MCP tools.

    Tracks all messages routed and subscriptions made without
    requiring the actual postal infrastructure.

    Mirrors the UnifiedPostalHub interface from fairies/P00_Autonomic/postal.py
    """

    def __init__(self):
        # Message tracking
        self.messages: List[Dict[str, Any]] = []
        self.subscriptions: Dict[str, List[Callable]] = {}

        # Fairy registry tracking
        self.registered_fairies: Dict[str, Dict[str, Any]] = {}

        # Intent tracking
        self.intent_calls: List[Dict[str, Any]] = []

        # Stats
        self.stats = {
            "messages_routed": 0,
            "subscriptions": 0,
            "intents_invoked": 0,
        }

    def route(self, topic: str, payload: Dict[str, Any], sender_id: str = None) -> int:
        """Route a message and track it."""
        self.messages.append({
            "topic": topic,
            "payload": payload,
            "sender_id": sender_id,
            "ts": time.time(),
        })
        self.stats["messages_routed"] += 1

        # Deliver to subscribers
        delivered = 0
        if topic in self.subscriptions:
            for callback in self.subscriptions[topic]:
                try:
                    callback(payload)
                    delivered += 1
                except Exception:
                    pass

        return delivered

    def subscribe(self, topic: str, callback: Callable, subscriber_id: str = None):
        """Subscribe to a topic."""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append(callback)
        self.stats["subscriptions"] += 1

    def receive(self, topic: str, callback: Callable, subscriber_id: str = None):
        """Alias for subscribe."""
        return self.subscribe(topic, callback, subscriber_id)

    def register_fairy(self, fairy_or_contract) -> Dict[str, Any]:
        """Mock fairy registration."""
        if isinstance(fairy_or_contract, dict):
            profile = fairy_or_contract
        else:
            profile = {
                "actor_name": getattr(fairy_or_contract, "actor_name", "TestFairy"),
                "actor_id": getattr(fairy_or_contract, "actor_id", "test-fairy-001"),
                "plane": getattr(fairy_or_contract, "plane", "P99_Test"),
            }

        actor_id = profile.get("actor_id", f"test-{len(self.registered_fairies)}")
        self.registered_fairies[actor_id] = profile

        # Route wake event
        self.route("fairy.wake", profile)

        return profile

    def unregister_fairy(self, actor_id: str) -> Optional[Dict[str, Any]]:
        """Mock fairy unregistration."""
        return self.registered_fairies.pop(actor_id, None)

    def get_citizen(self, actor_name: str) -> Optional[Dict[str, Any]]:
        """Get fairy profile by name."""
        for profile in self.registered_fairies.values():
            if profile.get("actor_name") == actor_name:
                return profile
        return None

    def list_citizens(self) -> List[str]:
        """List all registered fairy names."""
        return [p.get("actor_name") for p in self.registered_fairies.values()]

    def use_intent(self, target_actor: str, intent: str, payload: Dict = None,
                   caller_id: str = None) -> Optional[Any]:
        """Track intent invocations."""
        self.intent_calls.append({
            "target": target_actor,
            "intent": intent,
            "payload": payload or {},
            "caller": caller_id,
            "ts": time.time(),
        })
        self.stats["intents_invoked"] += 1
        return None  # Mock returns None by default

    # Lane shortcuts
    def to_TELEMETRY(self, pkt: Dict) -> int:
        return self.route("telemetry", pkt)

    def to_COGNITION(self, pkt: Dict) -> int:
        return self.route("cognition", pkt)

    def to_SOMATIC(self, pkt: Dict) -> int:
        return self.route("somatic", pkt)

    def to_CHEMISTRY(self, pkt: Dict) -> int:
        return self.route("chemistry", pkt)

    def to_MEMORY(self, pkt: Dict) -> int:
        return self.route("memory", pkt)

    def get_stats(self) -> Dict[str, Any]:
        """Return tracking stats."""
        return {
            **self.stats,
            "total_messages": len(self.messages),
            "active_subscriptions": sum(len(v) for v in self.subscriptions.values()),
            "registered_fairies": len(self.registered_fairies),
        }

    def list_topics(self) -> List[str]:
        """List all topics that have been used."""
        topics = set(self.subscriptions.keys())
        topics.update(m["topic"] for m in self.messages)
        return sorted(topics)

    # Test helper methods
    def get_messages_for_topic(self, topic: str) -> List[Dict[str, Any]]:
        """Get all messages routed to a specific topic."""
        return [m for m in self.messages if m["topic"] == topic]

    def clear(self):
        """Clear all tracking state."""
        self.messages.clear()
        self.subscriptions.clear()
        self.registered_fairies.clear()
        self.intent_calls.clear()
        self.stats = {
            "messages_routed": 0,
            "subscriptions": 0,
            "intents_invoked": 0,
        }


# =============================================================================
# MOCK CHEMISTRY STATE
# =============================================================================

@dataclass
class MockChemicalLevel:
    """A single chemical level with tracking."""
    name: str
    level: float = 0.5
    baseline: float = 0.5
    signals_received: int = 0


class MockChemistryState:
    """
    Mock chemistry state for testing affect-aware MCP tools.

    Tracks chemical signals and mood without real decay.
    Mirrors the ChemistryState interface from fairies/P20_Somatic/chemistry/chemistry_state.py
    """

    DEFAULT_CHEMICALS = ["dopamine", "serotonin", "cortisol", "adrenaline", "oxytocin", "norepinephrine"]

    def __init__(self):
        self._levels: Dict[str, MockChemicalLevel] = {}
        self._callbacks: List[Callable] = []
        self._signal_history: List[Dict[str, Any]] = []

        # Initialize default chemicals
        for chem in self.DEFAULT_CHEMICALS:
            baseline = 0.5 if chem != "cortisol" else 0.3
            baseline = 0.1 if chem == "adrenaline" else baseline
            self._levels[chem] = MockChemicalLevel(name=chem, level=baseline, baseline=baseline)

    def signal(self, chemical: str, delta: float, source: str = "test") -> float:
        """Apply a chemical signal."""
        if chemical not in self._levels:
            self._levels[chemical] = MockChemicalLevel(name=chemical)

        level = self._levels[chemical]
        old_value = level.level
        level.level = max(0.0, min(1.0, level.level + delta))
        level.signals_received += 1

        # Track signal
        self._signal_history.append({
            "chemical": chemical,
            "delta": delta,
            "source": source,
            "old": old_value,
            "new": level.level,
            "ts": time.time(),
        })

        # Notify callbacks
        for cb in self._callbacks:
            try:
                cb(chemical, level.level, delta)
            except Exception:
                pass

        return level.level

    def get_level(self, chemical: str) -> float:
        """Get current level (no decay in mock)."""
        if chemical not in self._levels:
            return 0.0
        return self._levels[chemical].level

    def get_all_levels(self) -> Dict[str, float]:
        """Get all chemical levels."""
        return {name: level.level for name, level in self._levels.items()}

    def get_mood_vector(self) -> Dict[str, Any]:
        """Compute simplified mood vector."""
        levels = self.get_all_levels()

        # Simplified valence/arousal calculation
        valence = (levels.get("dopamine", 0.5) - 0.5) * 0.5 + (levels.get("serotonin", 0.5) - 0.5) * 0.5
        arousal = levels.get("adrenaline", 0.1) * 0.4 + levels.get("norepinephrine", 0.4) * 0.3

        # Derive mood
        if valence > 0.2:
            mood = "excited" if arousal > 0.5 else "calm"
        elif valence < -0.2:
            mood = "stressed" if arousal > 0.5 else "melancholic"
        else:
            mood = "focused" if arousal > 0.5 else "neutral"

        return {
            "valence": round(valence, 3),
            "arousal": round(arousal, 3),
            "mood": mood,
            "levels": {k: round(v, 3) for k, v in levels.items()},
        }

    def add_callback(self, callback: Callable):
        """Add callback for chemical changes."""
        self._callbacks.append(callback)

    # Test helper methods
    def set_level(self, chemical: str, level: float):
        """Directly set a level for testing."""
        if chemical not in self._levels:
            self._levels[chemical] = MockChemicalLevel(name=chemical)
        self._levels[chemical].level = max(0.0, min(1.0, level))

    def set_mood(self, mood: str):
        """Set chemicals to produce a specific mood."""
        mood_presets = {
            "excited": {"dopamine": 0.8, "serotonin": 0.6, "adrenaline": 0.5},
            "calm": {"dopamine": 0.6, "serotonin": 0.7, "cortisol": 0.2},
            "stressed": {"dopamine": 0.3, "cortisol": 0.8, "adrenaline": 0.6},
            "focused": {"norepinephrine": 0.7, "dopamine": 0.5},
            "neutral": {},  # Keep defaults
        }

        if mood in mood_presets:
            for chem, level in mood_presets[mood].items():
                self.set_level(chem, level)

    def get_signal_history(self) -> List[Dict[str, Any]]:
        """Get history of all signals received."""
        return self._signal_history.copy()

    def clear(self):
        """Reset to baseline levels."""
        for level in self._levels.values():
            level.level = level.baseline
            level.signals_received = 0
        self._signal_history.clear()


# =============================================================================
# MOCK COLLISION CHAMBER
# =============================================================================

@dataclass
class MockPulse:
    """Mock pulse for collision testing."""
    id: str
    beam: str
    content: Dict[str, Any]
    source: str
    energy: float = 0.7
    entered_at: float = field(default_factory=time.time)


@dataclass
class MockCollision:
    """Mock collision event."""
    id: int
    ts: float
    recall_pulse: MockPulse
    ingest_pulse: MockPulse
    energy: float
    resonance: float
    products: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "consciousness_collision",
            "collision_id": self.id,
            "ts": self.ts,
            "energy": self.energy,
            "resonance": self.resonance,
            "products": self.products,
        }


class MockCollisionChamber:
    """
    Mock collision chamber for testing consciousness-aware MCP tools.

    Allows controlled collision simulation without real beam dynamics.
    Mirrors the CollisionChamber interface from consciousness/collision_chamber.py
    """

    def __init__(self):
        self.recall_beam: deque[MockPulse] = deque(maxlen=100)
        self.ingest_beam: deque[MockPulse] = deque(maxlen=100)

        self._collision_count = 0
        self._recent_collisions: deque[MockCollision] = deque(maxlen=50)
        self._on_collision: Optional[Callable] = None

        self.stats = {
            "recall_received": 0,
            "ingest_received": 0,
            "collisions": 0,
            "decayed": 0,
        }

        self.stats_mobius = {
            "crossings_attempted": 0,
            "crossings_completed": 0,
            "crossings_blocked": 0,
        }

    @property
    def on_collision(self) -> Optional[Callable]:
        return self._on_collision

    @on_collision.setter
    def on_collision(self, callback: Callable):
        self._on_collision = callback

    def receive_recall(self, content: Dict[str, Any], source: str = "test", **kwargs) -> Optional[MockCollision]:
        """Receive a recall pulse."""
        self.stats["recall_received"] += 1

        pulse = MockPulse(
            id=f"recall-{self.stats['recall_received']}",
            beam="recall",
            content=content,
            source=source,
            energy=kwargs.get("energy", 0.7),
        )
        self.recall_beam.append(pulse)

        # Auto-collide if ingest beam has pulses
        return self._try_collision()

    def receive_ingest(self, content: Dict[str, Any], source: str = "test", **kwargs) -> Optional[MockCollision]:
        """Receive an ingest pulse."""
        self.stats["ingest_received"] += 1

        pulse = MockPulse(
            id=f"ingest-{self.stats['ingest_received']}",
            beam="ingest",
            content=content,
            source=source,
            energy=kwargs.get("energy", 0.7),
        )
        self.ingest_beam.append(pulse)

        # Auto-collide if recall beam has pulses
        return self._try_collision()

    def _try_collision(self) -> Optional[MockCollision]:
        """Try to produce a collision if both beams have pulses."""
        if not self.recall_beam or not self.ingest_beam:
            return None

        recall_pulse = self.recall_beam.popleft()
        ingest_pulse = self.ingest_beam.popleft()

        self._collision_count += 1
        self.stats["collisions"] += 1

        collision = MockCollision(
            id=self._collision_count,
            ts=time.time(),
            recall_pulse=recall_pulse,
            ingest_pulse=ingest_pulse,
            energy=(recall_pulse.energy * ingest_pulse.energy) ** 0.5,
            resonance=0.8,  # Fixed resonance for testing
            products={
                "to_ingest": recall_pulse.content,
                "to_recall": ingest_pulse.content,
            },
        )

        self._recent_collisions.append(collision)

        if self._on_collision:
            try:
                self._on_collision(collision)
            except Exception:
                pass

        return collision

    def tick(self) -> Optional[MockCollision]:
        """Tick the chamber (no-op in mock, collisions happen on receive)."""
        return None

    def status(self) -> Dict[str, Any]:
        """Get chamber status."""
        return {
            "recall_beam_size": len(self.recall_beam),
            "ingest_beam_size": len(self.ingest_beam),
            "collision_count": self._collision_count,
            "recent_collisions": len(self._recent_collisions),
            "stats": self.stats.copy(),
            "mobius": {
                "enabled": True,
                "stats": self.stats_mobius.copy(),
            },
        }

    def get_status(self) -> Dict[str, Any]:
        """Alias for status()."""
        return self.status()

    def recent_collisions(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent collisions."""
        return [c.to_dict() for c in list(self._recent_collisions)[-n:]]

    # Test helper methods
    def force_collision(self, recall_content: Dict, ingest_content: Dict) -> MockCollision:
        """Force a collision between specific content."""
        self.receive_recall(recall_content)
        # Clear the auto-collision, then manually create
        if self._recent_collisions:
            self._recent_collisions.pop()
            self._collision_count -= 1
            self.stats["collisions"] -= 1

        self.receive_ingest(ingest_content)
        return self._recent_collisions[-1] if self._recent_collisions else None

    def inject_collision(self, energy: float = 0.8, resonance: float = 0.9) -> MockCollision:
        """Inject a pre-made collision for testing."""
        self._collision_count += 1

        recall_pulse = MockPulse(
            id=f"injected-recall-{self._collision_count}",
            beam="recall",
            content={"injected": True, "type": "recall"},
            source="test_injection",
        )
        ingest_pulse = MockPulse(
            id=f"injected-ingest-{self._collision_count}",
            beam="ingest",
            content={"injected": True, "type": "ingest"},
            source="test_injection",
        )

        collision = MockCollision(
            id=self._collision_count,
            ts=time.time(),
            recall_pulse=recall_pulse,
            ingest_pulse=ingest_pulse,
            energy=energy,
            resonance=resonance,
            products={
                "to_ingest": recall_pulse.content,
                "to_recall": ingest_pulse.content,
            },
        )

        self._recent_collisions.append(collision)
        self.stats["collisions"] += 1

        return collision

    def clear(self):
        """Clear all state."""
        self.recall_beam.clear()
        self.ingest_beam.clear()
        self._recent_collisions.clear()
        self._collision_count = 0
        self.stats = {
            "recall_received": 0,
            "ingest_received": 0,
            "collisions": 0,
            "decayed": 0,
        }


# =============================================================================
# SAMPLE TOOL RESULT
# =============================================================================

@dataclass
class SampleToolResult:
    """
    Sample MCP tool result for testing tool response handling.

    Provides various pre-made tool results representing different scenarios.
    """
    success: bool
    data: Any
    error: Optional[str] = None
    affect_signals: Optional[Dict[str, float]] = None
    collision_products: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "data": self.data,
        }
        if self.error:
            result["error"] = self.error
        if self.affect_signals:
            result["affect_signals"] = self.affect_signals
        if self.collision_products:
            result["collision_products"] = self.collision_products
        return result

    @classmethod
    def success_result(cls, data: Any = None) -> "SampleToolResult":
        """Create a successful tool result."""
        return cls(success=True, data=data or {"status": "ok"})

    @classmethod
    def error_result(cls, error: str) -> "SampleToolResult":
        """Create an error tool result."""
        return cls(success=False, data=None, error=error)

    @classmethod
    def with_affect(cls, data: Any, signals: Dict[str, float]) -> "SampleToolResult":
        """Create a result with affect signals."""
        return cls(success=True, data=data, affect_signals=signals)

    @classmethod
    def with_collision(cls, data: Any, products: Dict[str, Any]) -> "SampleToolResult":
        """Create a result with collision products."""
        return cls(success=True, data=data, collision_products=products)


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_postal() -> MockPostalHub:
    """
    Provide a mock postal hub for testing.

    Usage:
        def test_something(mock_postal):
            mock_postal.route("topic", {"data": "value"})
            assert len(mock_postal.messages) == 1
    """
    return MockPostalHub()


@pytest.fixture
def mock_chemistry() -> MockChemistryState:
    """
    Provide a mock chemistry state for testing.

    Usage:
        def test_affect(mock_chemistry):
            mock_chemistry.signal("dopamine", 0.2)
            assert mock_chemistry.get_level("dopamine") == 0.7
    """
    return MockChemistryState()


@pytest.fixture
def mock_collision() -> MockCollisionChamber:
    """
    Provide a mock collision chamber for testing.

    Usage:
        def test_consciousness(mock_collision):
            collision = mock_collision.inject_collision(energy=0.9)
            assert collision.energy == 0.9
    """
    return MockCollisionChamber()


@pytest.fixture
def sample_tool_result() -> SampleToolResult:
    """
    Provide a sample successful tool result.

    For other result types, use the class methods:
        result = SampleToolResult.error_result("Something went wrong")
        result = SampleToolResult.with_affect(data, {"dopamine": 0.1})
    """
    return SampleToolResult.success_result({"example": "data"})


# =============================================================================
# COMBINED FIXTURES
# =============================================================================

@pytest.fixture
def consciousness_mocks(mock_postal, mock_chemistry, mock_collision):
    """
    Provide all consciousness-related mocks together.

    Usage:
        def test_full_system(consciousness_mocks):
            postal, chemistry, collision = consciousness_mocks
            # ... use all three
    """
    return mock_postal, mock_chemistry, mock_collision


@pytest.fixture
def affect_aware_context(mock_postal, mock_chemistry):
    """
    Provide a context for testing affect-aware tools.

    Returns a dict with configured mocks and helper methods.
    """
    return {
        "postal": mock_postal,
        "chemistry": mock_chemistry,
        "signal_affect": lambda chem, delta: mock_chemistry.signal(chem, delta, "test"),
        "route_message": lambda topic, data: mock_postal.route(topic, data),
    }
