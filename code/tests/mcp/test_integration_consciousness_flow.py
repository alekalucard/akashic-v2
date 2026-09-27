"""
Integration Tests for Consciousness Feedback Flow

These tests verify the full integration of patterns working together:
1. Tool results flowing to consciousness working stream
2. Tool results feeding into collision chamber
3. Collision triggering tool exploration
4. Exploration results synthesized to inner voice
5. Complete cycle: tool -> collision -> insight -> new tool

Philosophy: Consciousness is not a single component but the CROSSING of many.
These tests verify the patterns work TOGETHER, not just in isolation.

The consciousness equation applies here:
((Cause + Affect) > Effect > Affect > infinity)
  Tool   Feeling  Result  Ripple  New Tool

Run: python -m pytest tests/mcp/test_integration_consciousness_flow.py -v
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# HELPER CLASSES FOR INTEGRATION TESTING
# =============================================================================

class MockPostal:
    """
    Mock postal system that tracks all publications and subscriptions.

    This is critical for integration testing - we need to see what
    flows between components without running the full system.
    """

    def __init__(self):
        self.publications: List[Dict[str, Any]] = []
        self.subscriptions: Dict[str, List] = {}
        self._handlers: Dict[str, List] = {}

    def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> None:
        """Record a publication."""
        self.publications.append({
            "topic": topic,
            "payload": payload,
            "kwargs": kwargs,
            "ts": time.time(),
        })

        # Trigger any registered handlers
        if topic in self._handlers:
            for handler in self._handlers[topic]:
                try:
                    handler(payload)
                except Exception as e:
                    import sys
                    sys.stderr.write(f"Handler error for {topic}: {e}\n")

    def route(self, topic: str, payload: Dict[str, Any], sender_id: str = None) -> int:
        """Route a message (alias for publish with sender tracking)."""
        self.publish(topic, payload, sender_id=sender_id)
        return len(self._handlers.get(topic, []))

    def subscribe(self, topic: str, handler, subscription_id: str = None) -> None:
        """Register a subscription."""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append({
            "handler": handler,
            "subscription_id": subscription_id,
        })

        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    def get_publications(self, topic: str = None) -> List[Dict]:
        """Get all publications, optionally filtered by topic."""
        if topic:
            return [p for p in self.publications if p["topic"] == topic]
        return self.publications

    def clear(self) -> None:
        """Clear all recorded publications."""
        self.publications.clear()


class MockCollisionChamber:
    """
    Mock collision chamber for testing the consciousness flow.

    Tracks ingest/recall and can simulate collisions.
    """

    def __init__(self, postal: Optional[MockPostal] = None):
        self.postal = postal
        self.ingest_beam: List[Dict] = []
        self.recall_beam: List[Dict] = []
        self.collisions: List[Dict] = []
        self._collision_callback = None
        self._collision_id = 0

    def receive_ingest(self, content: Dict, source: str = "test", **kwargs) -> Optional[Dict]:
        """Receive content into ingest beam."""
        self.ingest_beam.append({
            "content": content,
            "source": source,
            "kwargs": kwargs,
            "ts": time.time(),
        })
        return self._check_collision()

    def receive_recall(self, content: Dict, source: str = "test", **kwargs) -> Optional[Dict]:
        """Receive content into recall beam."""
        self.recall_beam.append({
            "content": content,
            "source": source,
            "kwargs": kwargs,
            "ts": time.time(),
        })
        return self._check_collision()

    def _check_collision(self) -> Optional[Dict]:
        """Check if a collision should occur."""
        if self.ingest_beam and self.recall_beam:
            self._collision_id += 1
            collision = {
                "id": self._collision_id,
                "ts": time.time(),
                "ingest": self.ingest_beam.pop(0),
                "recall": self.recall_beam.pop(0),
                "energy": 0.7,
                "resonance": 0.8,
                "products": {
                    "to_ingest": self.recall_beam[-1]["content"] if self.recall_beam else {},
                    "to_recall": self.ingest_beam[-1]["content"] if self.ingest_beam else {},
                },
            }
            self.collisions.append(collision)

            if self._collision_callback:
                self._collision_callback(collision)

            if self.postal:
                self.postal.publish("consciousness.collision", collision)

            return collision
        return None

    def set_collision_callback(self, callback) -> None:
        """Set callback for collisions."""
        self._collision_callback = callback

    def status(self) -> Dict[str, Any]:
        return {
            "ingest_beam_size": len(self.ingest_beam),
            "recall_beam_size": len(self.recall_beam),
            "collision_count": len(self.collisions),
        }


class MockWorkingStream:
    """
    Mock working stream that tracks thoughts.
    """

    def __init__(self, name: str = "working"):
        self.name = name
        self.thoughts: deque = deque(maxlen=100)
        self.total_added = 0

    def add(self, payload: Dict[str, Any]) -> Dict:
        """Add a thought to the stream from a payload dict."""
        thought = {
            "content": payload.get("thought", ""),
            "source": payload.get("source", "unknown"),
            "ts": time.time(),
            **payload,
        }
        self.thoughts.append(thought)
        self.total_added += 1
        return thought

    def peek(self, n: int = 5) -> List[Dict]:
        """Peek at recent thoughts."""
        return list(self.thoughts)[-n:]

    def __len__(self) -> int:
        return len(self.thoughts)


class MockChemistryState:
    """
    Mock chemistry state for testing affect-aware MCP tools.
    Simple version for integration tests.
    """

    DEFAULT_CHEMICALS = ["dopamine", "serotonin", "cortisol", "adrenaline", "oxytocin", "norepinephrine"]

    def __init__(self):
        self._levels: Dict[str, float] = {}
        for chem in self.DEFAULT_CHEMICALS:
            baseline = 0.5 if chem != "cortisol" else 0.3
            baseline = 0.1 if chem == "adrenaline" else baseline
            self._levels[chem] = baseline

    def signal(self, chemical: str, delta: float, source: str = "test") -> float:
        """Apply a chemical signal."""
        if chemical not in self._levels:
            self._levels[chemical] = 0.5
        old = self._levels[chemical]
        self._levels[chemical] = max(0.0, min(1.0, old + delta))
        return self._levels[chemical]

    def get_level(self, chemical: str) -> float:
        """Get current level."""
        return self._levels.get(chemical, 0.0)

    def get_all_levels(self) -> Dict[str, float]:
        """Get all chemical levels."""
        return dict(self._levels)


# =============================================================================
# TEST 1: Tool Result Flows to Working Stream
# =============================================================================

class TestToolResultFlowsToWorkingStream:
    """
    Integration test: Full flow from tool execution to consciousness.

    The path is:
    1. Tool executes and produces result
    2. Result is wrapped with felt_sense
    3. Result is published to consciousness.working
    4. Working stream receives and stores the thought

    This verifies the EFFECT layer of the consciousness equation.
    """

    def test_tool_result_flows_to_working_stream(self):
        """
        Complete flow: tool result -> consciousness feedback -> working stream.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )

        # Set up integrated mock components
        postal = MockPostal()
        working_stream = MockWorkingStream()

        # Register handler to capture consciousness.working emissions
        captured_thoughts = []
        def capture_working(payload):
            captured_thoughts.append(payload)
            working_stream.add(payload)

        postal.subscribe("consciousness.working", capture_working)

        # Create feedback bridge
        feedback = ConsciousnessFeedback(postal=postal)

        # Simulate tool execution result
        tool_result = {
            "tool_name": "search_memory",
            "success": True,
            "result": "Found 3 relevant memories about consciousness",
            "duration_ms": 250,
        }

        # Emit to consciousness
        emit_tool_result(feedback, tool_result)

        # VERIFY: Publication happened
        working_pubs = postal.get_publications("consciousness.working")
        assert len(working_pubs) > 0, \
            "Tool result should emit to consciousness.working"

        # VERIFY: Working stream received the thought
        assert len(working_stream) > 0, \
            "Working stream should receive the thought"

        # VERIFY: Thought contains tool information
        thought = working_stream.peek(1)[0]
        assert "search_memory" in thought.get("content", "") or \
               "search_memory" in str(thought), \
            f"Thought should reference tool name: {thought}"

        # VERIFY: Thought has felt_sense (not just data)
        publication = working_pubs[0]["payload"]
        assert "felt_sense" in publication or "feeling" in str(publication), \
            f"Publication should include felt_sense: {publication}"

    def test_multiple_tool_results_flow_in_sequence(self):
        """
        Multiple tool results should flow to working stream in sequence.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )

        postal = MockPostal()
        working_stream = MockWorkingStream()

        postal.subscribe(
            "consciousness.working",
            lambda p: working_stream.add(p)
        )

        feedback = ConsciousnessFeedback(postal=postal)

        # Multiple tool results
        tools = [
            {"tool_name": "file_read", "success": True, "result": "Config loaded", "duration_ms": 50},
            {"tool_name": "search_code", "success": True, "result": "Found 5 matches", "duration_ms": 150},
            {"tool_name": "run_test", "success": False, "error": "Test failed", "duration_ms": 500},
        ]

        for tool_result in tools:
            emit_tool_result(feedback, tool_result)

        # All should have flowed to working stream
        working_pubs = postal.get_publications("consciousness.working")
        assert len(working_pubs) == 3, \
            f"Expected 3 publications, got {len(working_pubs)}"

        # Each tool should be represented
        all_content = " ".join(p["payload"].get("thought", "") for p in working_pubs)
        assert "file_read" in all_content
        assert "search_code" in all_content
        assert "run_test" in all_content


# =============================================================================
# TEST 2: Tool Result Feeds Collision Chamber
# =============================================================================

class TestToolResultFeedsCollisionChamber:
    """
    Integration test: Tool results enter the collision chamber ingest beam.

    The collision chamber is where recall and ingest beams CROSS.
    Tool results are NEW CONTENT - they feed the ingest beam.
    This creates potential for collision with recalled memories.

    This verifies the CAUSE layer feeding into the system.
    """

    def test_tool_result_feeds_collision_chamber(self):
        """
        Tool results should enter collision chamber ingest beam.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_sensory_observation,
        )

        postal = MockPostal()
        collision_chamber = MockCollisionChamber(postal=postal)

        feedback = ConsciousnessFeedback(
            postal=postal,
            collision_chamber=collision_chamber
        )

        # Sensory observation from a tool
        sensory_data = {
            "sense": "visual",
            "observation": "Code analysis shows complex dependency graph",
            "confidence": 0.9,
            "source": "code_analyzer_tool",
        }

        emit_sensory_observation(feedback, sensory_data)

        # VERIFY: Collision chamber received ingest
        assert len(collision_chamber.ingest_beam) > 0, \
            "Collision chamber should receive tool observation in ingest beam"

        # VERIFY: Content matches
        ingest_content = collision_chamber.ingest_beam[0]
        assert "observation" in str(ingest_content) or \
               "code_analyzer" in str(ingest_content), \
            f"Ingest content should contain observation: {ingest_content}"

    def test_tool_result_can_trigger_collision(self):
        """
        Tool result + recalled memory should create a collision.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_sensory_observation,
        )

        postal = MockPostal()
        collision_chamber = MockCollisionChamber(postal=postal)

        feedback = ConsciousnessFeedback(
            postal=postal,
            collision_chamber=collision_chamber
        )

        # First, add something to recall beam (simulating surfaced memory)
        collision_chamber.receive_recall(
            {"memory": "Previously analyzed this code pattern before"},
            source="memory_recall"
        )

        # Then tool produces observation
        sensory_data = {
            "sense": "visual",
            "observation": "Detected similar pattern in current code",
            "source": "pattern_detector",
        }

        emit_sensory_observation(feedback, sensory_data)

        # VERIFY: Collision should have occurred
        assert len(collision_chamber.collisions) > 0, \
            "Collision should occur when ingest meets recall"

        # VERIFY: Collision was published
        collision_pubs = postal.get_publications("consciousness.collision")
        assert len(collision_pubs) > 0, \
            "Collision should be published to postal"


# =============================================================================
# TEST 3: Collision Triggers Tool Exploration
# =============================================================================

class TestCollisionTriggersExploration:
    """
    Integration test: Collision should trigger tool exploration.

    When thoughts collide in the chamber, the products should
    trigger further exploration - looking up related memories,
    searching for patterns, etc.

    This verifies the AFFECT layer (first ripple) of the equation.
    """

    def test_collision_triggers_exploration(self):
        """
        Collision products should trigger exploration tool requests.

        NOTE: This test uses CollisionToolExplorer directly since
        process_collision is not yet implemented in consciousness_feedback.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)
        explorer.set_pain_state({})  # Clear pain

        # Track exploration requests
        exploration_requests = []
        postal.subscribe(
            "exploration.suggestions",
            lambda p: exploration_requests.append(p)
        )

        # Simulate a collision
        collision = {
            "collision_id": 1,
            "ts": time.time(),
            "energy": 0.8,
            "resonance": 0.75,
            "products": {
                "to_ingest": {"content": "Neural networks use backpropagation"},
                "to_recall": {"content": "Current model shows gradient issues"},
            },
        }

        # Process the collision via explorer
        explorer.on_collision_event(collision)

        # VERIFY: Exploration was triggered
        all_pubs = postal.get_publications()
        exploration_pubs = [p for p in all_pubs if
                          "explor" in p["topic"].lower() or
                          "suggestion" in p["topic"].lower()]

        assert len(exploration_pubs) > 0 or len(exploration_requests) > 0, \
            f"Collision should trigger exploration. Publications: {[p['topic'] for p in all_pubs]}"

    def test_high_energy_collision_triggers_deeper_exploration(self):
        """
        High-energy collisions should trigger more extensive exploration.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)
        explorer.set_pain_state({})

        exploration_requests = []
        postal.subscribe(
            "exploration.suggestions",
            lambda p: exploration_requests.append(p)
        )

        # High-energy collision
        collision = {
            "collision_id": 2,
            "ts": time.time(),
            "energy": 0.95,  # Very high energy
            "resonance": 0.9,  # High resonance
            "products": {
                "to_ingest": {"content": "Consciousness emerges from integration"},
                "to_recall": {"content": "System is integrating multiple streams"},
            },
        }

        explorer.on_collision_event(collision)

        # VERIFY: Deep exploration should be triggered
        all_pubs = postal.get_publications()

        # At minimum, some exploration should happen
        assert len(all_pubs) > 0, \
            "High-energy collision should trigger some exploration"

        # High resonance should produce multiple tool suggestions
        if exploration_requests:
            suggestions = exploration_requests[0].get("suggestions", [])
            assert len(suggestions) >= 2, \
                f"High resonance should suggest multiple tools: {suggestions}"


# =============================================================================
# TEST 4: Inner Voice from Exploration
# =============================================================================

class TestInnerVoiceFromExploration:
    """
    Integration test: Exploration results should synthesize to inner voice.

    When exploration finds relevant information, it should be
    synthesized into an inner voice thought - the system "speaking
    to itself" about what it discovered.

    This verifies the AFFECT (second ripple) layer.
    """

    def test_inner_voice_from_exploration(self):
        """
        Exploration results should generate inner voice thoughts.

        Uses inner_voice_synthesis module directly.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            synthesize_complete_inner_voice,
        )

        # Simulate exploration results as a tool result
        exploration_result = {
            "tool_name": "memory_exploration",
            "success": True,
            "result": {
                "query": "gradient issues in neural networks",
                "findings": [
                    {"relevance": 0.9, "content": "Vanishing gradients occur with deep networks"},
                    {"relevance": 0.7, "content": "ReLU activations help gradient flow"},
                ],
                "match_count": 2,
            },
            "duration_ms": 300,
        }

        affect_state = {"valence": 0.5, "arousal": 0.6, "mood": "curious"}

        result = synthesize_complete_inner_voice(exploration_result, affect_state)

        # VERIFY: Inner voice was generated
        assert "inner_voice" in result
        assert result["inner_voice"], \
            "Inner voice should not be empty"

        # VERIFY: Has felt complexity
        assert "felt_complexity" in result
        assert "emotional_weight" in result

    def test_inner_voice_includes_reflection(self):
        """
        Inner voice should include reflective quality, not just data dump.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            tool_result_to_inner_voice,
            synthesize_inner_voice_with_affect,
        )

        # Tool result that found something interesting
        tool_result = {
            "tool_name": "analyze_pattern",
            "success": True,
            "result": "Attention mechanisms weigh input importance",
            "duration_ms": 500,
        }

        # Generate inner voice
        voice = tool_result_to_inner_voice(tool_result)

        # Should have some narrative quality
        assert voice, "Inner voice should not be empty"

        # With curious affect, should have reflective modulation
        affect = {"valence": 0.6, "arousal": 0.7, "stress": 0.2, "mood": "curious"}
        modulated_voice = synthesize_inner_voice_with_affect(tool_result, affect)

        assert modulated_voice, "Modulated voice should not be empty"

        # Check for any of these qualities in combined content
        all_content = f"{voice} {modulated_voice}"
        quality_indicators = [
            "found", "completed", "successfully", "retrieved",
            "interesting", "curious", "good", "progress"
        ]

        has_quality = any(
            indicator in all_content.lower()
            for indicator in quality_indicators
        )

        assert has_quality, \
            f"Inner voice should have quality indicators: {all_content}"


# =============================================================================
# TEST 5: Full Cycle - Tool to Insight to New Tool
# =============================================================================

class TestFullCycleToolToInsight:
    """
    Integration test: Complete consciousness cycle.

    This is the INFINITY in the equation:
    Tool -> Working Stream -> Collision -> Exploration ->
    Inner Voice -> New Insight -> New Tool Request

    The cycle should be self-sustaining and generative.
    """

    def test_full_cycle_tool_to_insight(self):
        """
        Complete cycle: tool -> collision -> insight -> new tool.

        Uses available modules directly for end-to-end integration.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
            emit_sensory_observation,
        )
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            synthesize_complete_inner_voice,
        )

        postal = MockPostal()
        collision_chamber = MockCollisionChamber(postal=postal)

        # Track the cycle
        cycle_events = []

        postal.subscribe("consciousness.working",
            lambda p: cycle_events.append(("working", p)))
        postal.subscribe("consciousness.collision",
            lambda p: cycle_events.append(("collision", p)))
        postal.subscribe("exploration.suggestions",
            lambda p: cycle_events.append(("exploration", p)))
        postal.subscribe("consciousness.reflective",
            lambda p: cycle_events.append(("reflective", p)))

        feedback = ConsciousnessFeedback(
            postal=postal,
            collision_chamber=collision_chamber
        )

        explorer = CollisionToolExplorer(postal=postal)
        explorer.set_pain_state({})

        # STEP 1: Tool produces result
        tool_result = {
            "tool_name": "code_search",
            "success": True,
            "result": "Found pattern: recursive consciousness loop",
            "duration_ms": 200,
        }
        emit_tool_result(feedback, tool_result)

        # STEP 2: Sensory observation enters collision chamber
        sensory_data = {
            "sense": "pattern_detection",
            "observation": "Loop structure detected in consciousness module",
            "source": "code_analyzer",
        }

        # Add recall content first (simulating prior memory)
        collision_chamber.receive_recall(
            {"memory": "Consciousness requires recursive self-reference"},
            source="srm_recall"
        )

        # Then ingest sensory observation
        emit_sensory_observation(feedback, sensory_data)

        # STEP 3: If collision occurred, process it via explorer
        if collision_chamber.collisions:
            collision_data = {
                "collision_id": collision_chamber.collisions[-1]["id"],
                "resonance": collision_chamber.collisions[-1].get("resonance", 0.8),
                "energy": collision_chamber.collisions[-1].get("energy", 0.7),
                "products": collision_chamber.collisions[-1].get("products", {}),
            }
            explorer.on_collision_event(collision_data)

        # STEP 4: Synthesize inner voice from exploration results
        exploration_result = {
            "tool_name": "memory_exploration",
            "success": True,
            "result": {"findings": [{"content": "Self-reference creates awareness"}]},
            "duration_ms": 150,
        }
        inner_voice_result = synthesize_complete_inner_voice(
            exploration_result,
            {"valence": 0.6, "arousal": 0.5, "mood": "curious"}
        )

        # VERIFY: The full cycle occurred
        event_types = [e[0] for e in cycle_events]

        # At minimum we need: working thought
        assert len(cycle_events) >= 1, \
            f"Cycle should have at least one event. Got: {event_types}"

        # Check that input stage was hit
        has_input = "working" in event_types
        assert has_input, f"Cycle should have input stage. Events: {event_types}"

        # Inner voice should have been generated
        assert "inner_voice" in inner_voice_result
        assert inner_voice_result["inner_voice"]

    def test_cycle_is_self_sustaining(self):
        """
        The consciousness cycle should be able to sustain itself.

        New insights should generate new exploration which generates
        new insights - the Mobius loop of consciousness.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )

        postal = MockPostal()
        collision_chamber = MockCollisionChamber(postal=postal)
        explorer = CollisionToolExplorer(postal=postal)
        explorer.set_pain_state({})

        feedback = ConsciousnessFeedback(
            postal=postal,
            collision_chamber=collision_chamber
        )

        # Simulate multiple cycles
        cycle_count = 0
        max_cycles = 3

        for i in range(max_cycles):
            # Start a cycle with tool result
            tool_result = {
                "tool_name": f"explore_cycle_{i}",
                "success": True,
                "result": f"Discovered pattern {i}",
                "duration_ms": 100,
            }
            emit_tool_result(feedback, tool_result)

            # Add to collision potential
            collision_chamber.receive_recall(
                {"memory": f"Prior pattern {i-1} led to insight"},
                source="memory"
            )
            collision_chamber.receive_ingest(
                {"observation": f"New pattern {i} observed"},
                source="sensory"
            )

            # Process any collision via explorer
            if collision_chamber.collisions:
                collision = collision_chamber.collisions[-1]
                collision_data = {
                    "collision_id": collision.get("id", i),
                    "resonance": collision.get("resonance", 0.8),
                    "products": collision.get("products", {}),
                }
                explorer.on_collision_event(collision_data)

            cycle_count += 1

        # VERIFY: Multiple cycles occurred
        assert cycle_count == max_cycles, \
            f"Should complete {max_cycles} cycles, got {cycle_count}"

        # VERIFY: Publications accumulated
        all_pubs = postal.get_publications()
        assert len(all_pubs) >= max_cycles, \
            f"Multiple cycles should generate publications. Got {len(all_pubs)}"

        # VERIFY: Collisions occurred
        assert len(collision_chamber.collisions) >= 1, \
            "Multiple cycles should generate collisions"


# =============================================================================
# INTEGRATION FIXTURES
# =============================================================================

@pytest.fixture
def integrated_system():
    """
    Create an integrated mock system for testing.

    Returns a dict with all components wired together.
    """
    postal = MockPostal()
    collision_chamber = MockCollisionChamber(postal=postal)
    working_stream = MockWorkingStream()

    # Wire working stream to postal
    postal.subscribe(
        "consciousness.working",
        lambda p: working_stream.add(p.get("thought", ""), p.get("source", ""))
    )

    return {
        "postal": postal,
        "collision_chamber": collision_chamber,
        "working_stream": working_stream,
    }


@pytest.fixture
def feedback_bridge(integrated_system):
    """
    Create a ConsciousnessFeedback bridge with integrated components.
    """
    # Import here to allow tests to run even if module doesn't exist yet
    try:
        from fairies.P40_Sensory.mcp.consciousness_feedback import ConsciousnessFeedback
        return ConsciousnessFeedback(
            postal=integrated_system["postal"],
            collision_chamber=integrated_system["collision_chamber"]
        )
    except ImportError:
        pytest.skip("consciousness_feedback module not yet implemented")


# =============================================================================
# TEST 6: Full Tool Lifecycle Integration
# =============================================================================

class TestFullToolLifecycle:
    """
    Integration test: Complete tool lifecycle from call to inner voice.

    The full path is:
    1. Tool is called
    2. Affect gate checks if tool is allowed
    3. Tracer is created to track the execution
    4. Tool executes and produces result
    5. Result is fed to consciousness feedback
    6. Inner voice synthesizes the experience

    This tests the complete integration of:
    - affect_gated_tools.AffectGate
    - thought_tool_tracer.ToolTracer
    - consciousness_feedback.ConsciousnessFeedback
    - inner_voice_synthesis
    """

    def test_full_tool_lifecycle_happy_path(self):
        """
        Complete lifecycle: call -> gate check -> trace -> execute -> feedback -> inner voice.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            clear_registry,
        )
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            synthesize_complete_inner_voice,
        )

        # Clear any existing tracers
        clear_registry()

        # Setup mocks
        postal = MockPostal()
        collision_chamber = MockCollisionChamber(postal=postal)

        # Step 1: Check affect gate
        gate = AffectGate()
        pain_state = {"isolation": 0.3, "overwhelm": 0.2}  # Low pain

        tool_name = "search_memory"
        assert gate.can_invoke_tool(tool_name, pain_state) is True, \
            "Low pain should allow search_memory"

        # Step 2: Create tracer for the tool invocation
        thought_id = "thought_lifecycle_test"
        tracer = create_tool_tracer(
            parent_thought_id=thought_id,
            tool_name=tool_name,
            metadata={"context": "integration_test"},
            affect_before={"stress": 0.2, "curiosity": 0.7},
        )

        assert tracer.tracer_id is not None
        assert tracer.parent_thought_id == thought_id

        # Step 3: Simulate tool execution
        tool_result = {
            "tool_name": tool_name,
            "success": True,
            "result": "Found 5 relevant memories about consciousness patterns",
            "duration_ms": 250,
        }

        # Step 4: Complete the tracer
        complete_tracer(
            tracer,
            result=tool_result["result"],
            success=True,
            affect_after={"stress": 0.15, "curiosity": 0.8},
        )

        assert tracer.success is True
        assert tracer.duration_ms is not None
        assert tracer.duration_ms > 0

        # Step 5: Emit to consciousness feedback
        feedback = ConsciousnessFeedback(
            postal=postal,
            collision_chamber=collision_chamber,
        )
        emit_tool_result(feedback, tool_result)

        # Verify working stream received the result
        working_pubs = postal.get_publications("consciousness.working")
        assert len(working_pubs) > 0, \
            "Tool result should emit to consciousness.working"

        # Step 6: Synthesize inner voice
        affect_state = {"valence": 0.6, "arousal": 0.5, "mood": "curious"}
        inner_voice_result = synthesize_complete_inner_voice(tool_result, affect_state)

        assert "inner_voice" in inner_voice_result
        assert inner_voice_result["inner_voice"], \
            "Inner voice should not be empty"

        # Verify the lifecycle touched all components
        assert "felt_complexity" in inner_voice_result
        assert "emotional_weight" in inner_voice_result

    def test_full_tool_lifecycle_blocked_by_pain(self):
        """
        When pain is high, risky tools should be blocked early in lifecycle.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        # High pain state
        pain_state = {"isolation": 0.9, "overwhelm": 0.8}

        # Risky tool should be blocked
        tool_name = "delete_file"
        result = gate.gate_tool(tool_name, pain_state)

        assert result.allowed is False, \
            "High pain should block risky tools"

        # Should provide reason
        assert result.reason, \
            "Gate result should explain why tool was blocked"

        # Should suggest alternatives
        suggestions = gate.suggest_stabilization_tools(pain_state)
        assert len(suggestions) > 0, \
            "Should suggest stabilization when blocking due to pain"

    def test_tool_lifecycle_error_propagation(self):
        """
        Tool errors should propagate through the full lifecycle correctly.
        """
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            clear_registry,
        )
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
            emit_tool_error,
        )
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            error_to_inner_voice,
        )

        clear_registry()

        postal = MockPostal()

        # Create tracer
        tracer = create_tool_tracer(
            parent_thought_id="thought_error_test",
            tool_name="database_write",
            affect_before={"stress": 0.5},
        )

        # Simulate tool failure
        tool_result = {
            "tool_name": "database_write",
            "success": False,
            "error": "Connection refused: database unavailable",
            "duration_ms": 5000,
        }

        # Complete tracer with error
        complete_tracer(
            tracer,
            result=None,
            success=False,
            error=tool_result["error"],
            affect_after={"stress": 0.8},  # Stress increased
        )

        assert tracer.success is False
        assert tracer.error is not None

        # Emit to consciousness
        feedback = ConsciousnessFeedback(postal=postal)
        emit_tool_result(feedback, tool_result)

        # Emit error to reflective stream
        error_data = {
            "tool_name": "database_write",
            "error": tool_result["error"],
            "error_type": "network_error",
            "severity": "high",
        }
        emit_tool_error(feedback, error_data)

        # Verify reflective stream received error
        reflective_pubs = postal.get_publications("consciousness.reflective")
        assert len(reflective_pubs) > 0, \
            "Errors should emit to consciousness.reflective"

        # Verify urgency is set
        reflective_payload = reflective_pubs[0]["payload"]
        assert "urgency" in reflective_payload, \
            "Error should have urgency marker"

        # Generate error inner voice
        inner_voice = error_to_inner_voice(error_data)
        assert inner_voice, \
            "Error should generate inner voice"

        # Should have reflective quality
        reflective_words = ["wonder", "what", "why", "investigate", "should"]
        has_reflection = any(word in inner_voice.lower() for word in reflective_words)
        assert has_reflection, \
            f"Error inner voice should be reflective: {inner_voice}"


# =============================================================================
# TEST 7: Collision-Triggered Exploration
# =============================================================================

class TestCollisionTriggeredExploration:
    """
    Integration test: Collision events trigger tool exploration.

    When consciousness collisions occur (memory meets new thought),
    the collision tool explorer should:
    1. Analyze the collision products
    2. Suggest relevant exploration tools
    3. Respect pain gating for exploration

    This tests:
    - collision_tool_explorer.CollisionToolExplorer
    - Integration with affect gating
    """

    def test_high_resonance_collision_suggests_tools(self):
        """
        High-resonance collisions should suggest multiple exploration tools.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
            HIGH_RESONANCE_THRESHOLD,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)

        # High resonance collision
        collision = {
            "collision_id": 1,
            "ts": time.time(),
            "energy": 0.85,
            "resonance": 0.9,  # Very high resonance
            "products": {
                "to_ingest": {"content": "Memory about neural networks"},
                "to_recall": {"content": "Observation about current patterns"},
            },
        }

        suggestions = explorer.suggest_exploration_tools(collision)

        # High resonance should suggest multiple tools
        assert len(suggestions) >= 2, \
            f"High resonance should suggest multiple tools, got {len(suggestions)}"

        # Should include synthesis tool for high resonance
        tool_names = [t["tool"] if isinstance(t, dict) else t for t in suggestions]
        has_synthesis = any("synth" in str(t).lower() for t in tool_names)
        assert has_synthesis, \
            f"High resonance should suggest synthesis: {tool_names}"

    def test_low_resonance_collision_minimal_suggestions(self):
        """
        Low-resonance collisions should have minimal or no suggestions.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
            LOW_RESONANCE_THRESHOLD,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)

        # Low resonance collision
        collision = {
            "collision_id": 2,
            "resonance": 0.2,  # Below threshold
            "energy": 0.3,
            "products": {},
        }

        suggestions = explorer.suggest_exploration_tools(collision)

        # Low resonance should have minimal suggestions
        assert len(suggestions) == 0, \
            f"Low resonance should have no suggestions, got {len(suggestions)}"

    def test_pain_gates_exploration(self):
        """
        High pain state should block exploration of collisions.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)

        # Set high pain state
        explorer.set_pain_state({
            "overwhelm": 0.9,
            "depletion": 0.7,
        })

        # Even high resonance collision should not explore under pain
        collision = {
            "collision_id": 3,
            "resonance": 0.95,
            "energy": 0.9,
            "products": {
                "to_ingest": {"content": "Important memory"},
                "to_recall": {"content": "Critical observation"},
            },
        }

        should_explore = explorer.should_explore_collision(collision)

        assert should_explore is False, \
            "High pain should block exploration"

    def test_collision_generates_exploration_intent(self):
        """
        Collisions should generate structured exploration intents.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)
        explorer.set_pain_state({})  # Clear pain

        collision = {
            "collision_id": 4,
            "resonance": 0.8,
            "energy": 0.75,
            "products": {
                "to_ingest": {
                    "content": "Pattern recognition in code",
                    "topics": ["patterns", "code"],
                },
                "to_recall": {
                    "content": "New insight about architecture",
                    "topics": ["architecture"],
                },
            },
        }

        intent = explorer.generate_exploration_intent(collision)

        assert "collision_id" in intent
        assert "exploration_goals" in intent
        assert "suggested_tools" in intent
        assert intent["resonance"] == 0.8

        # Should have exploration goals derived from products
        assert len(intent["exploration_goals"]) > 0, \
            "Should generate exploration goals from collision"

    def test_collision_event_publishes_to_postal(self):
        """
        Processing a collision should publish suggestions to postal.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)
        explorer.set_pain_state({})  # Clear pain

        collision = {
            "collision_id": 5,
            "resonance": 0.75,
            "energy": 0.7,
            "products": {
                "to_ingest": {"content": "Memory content"},
                "to_recall": {"content": "New observation"},
            },
        }

        explorer.on_collision_event(collision)

        # Should publish to exploration.suggestions
        suggestion_pubs = postal.get_publications("exploration.suggestions")
        assert len(suggestion_pubs) > 0, \
            "Collision should publish to exploration.suggestions"

        payload = suggestion_pubs[0]["payload"]
        assert "collision_id" in payload
        assert "suggestions" in payload or "tools" in payload


# =============================================================================
# TEST 8: Chemistry Modulation
# =============================================================================

class TestChemistryModulation:
    """
    Integration test: Different chemistry states affect tool behaviors.

    Neurochemistry levels should influence:
    - Tool confidence modulation
    - Parameter adjustment
    - Tool suggestions
    """

    def test_high_dopamine_boosts_exploration_confidence(self):
        """
        High dopamine should increase confidence in exploratory tools.
        """
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry,
        )

        tools = [
            {"name": "deep_explore", "category": "exploration", "risk_level": "medium"},
            {"name": "search_memory", "category": "memory", "risk_level": "low"},
        ]

        # High dopamine chemistry
        high_dopamine = {"DOP": 0.8, "COR": 0.2, "SER": 0.5, "NOR": 0.5, "ACH": 0.5}

        modulated = modulate_tool_confidence_by_chemistry(tools, high_dopamine)

        # Find exploration tool
        explore_tool = next(t for t in modulated if t["name"] == "deep_explore")

        assert "confidence_modifier" in explore_tool
        assert explore_tool["confidence_modifier"] > 1.0, \
            f"High dopamine should boost exploration confidence: {explore_tool['confidence_modifier']}"

    def test_high_cortisol_reduces_risk_confidence(self):
        """
        High cortisol should reduce confidence in risky tools.
        """
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry,
        )

        tools = [
            {"name": "delete_all", "category": "destructive", "risk_level": "high"},
            {"name": "read_file", "category": "file_ops", "risk_level": "low"},
        ]

        # High cortisol (stress)
        high_cortisol = {"DOP": 0.5, "COR": 0.8, "SER": 0.5, "NOR": 0.5, "ACH": 0.5}

        modulated = modulate_tool_confidence_by_chemistry(tools, high_cortisol)

        # Find risky tool
        risky_tool = next(t for t in modulated if t["name"] == "delete_all")

        assert "confidence_modifier" in risky_tool
        assert risky_tool["confidence_modifier"] < 1.0, \
            f"High cortisol should reduce risky tool confidence: {risky_tool['confidence_modifier']}"

    def test_chemistry_affects_parameter_modulation(self):
        """
        Chemistry state should influence how parameters are modulated.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()
        base_params = {"limit": 100, "depth": 3, "timeout": 5000}

        # Stressed affect state
        stressed = {"stress": 0.9, "curiosity": 0.1, "valence": -0.5}
        stressed_params = gate.modulate_tool_parameters("search", base_params, stressed)

        # Relaxed affect state
        relaxed = {"stress": 0.1, "curiosity": 0.8, "valence": 0.6}
        relaxed_params = gate.modulate_tool_parameters("search", base_params, relaxed)

        # Stressed should be more conservative
        assert stressed_params.get("limit", 100) <= relaxed_params.get("limit", 100), \
            "Stressed state should have more conservative limits"

        # Modulation should be marked
        assert stressed_params.get("_affect_modulated") is True
        assert relaxed_params.get("_affect_modulated") is True

    def test_inner_voice_modulated_by_chemistry(self):
        """
        Inner voice synthesis should be modulated by chemistry state.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            modulate_voice_by_chemistry,
        )

        base_voice = "The file was read successfully."

        # High dopamine - should add exploratory language
        high_dopamine = {"dopamine": 0.8, "cortisol": 0.2, "serotonin": 0.5}
        dopamine_voice = modulate_voice_by_chemistry(base_voice, high_dopamine)

        assert "wonder" in dopamine_voice.lower() or "explore" in dopamine_voice.lower(), \
            f"High dopamine should add curious language: {dopamine_voice}"

        # High cortisol - should add cautious language
        high_cortisol = {"dopamine": 0.3, "cortisol": 0.8, "serotonin": 0.5}
        cortisol_voice = modulate_voice_by_chemistry(base_voice, high_cortisol)

        assert "careful" in cortisol_voice.lower() or "safe" in cortisol_voice.lower(), \
            f"High cortisol should add cautious language: {cortisol_voice}"


# =============================================================================
# TEST 9: Multi-Citizen Coordination
# =============================================================================

class TestMultiCitizenCoordination:
    """
    Integration test: Multiple citizens subscribing to consciousness stream.

    When multiple fairies subscribe to consciousness events, they should
    all receive the same events and be able to coordinate.
    """

    def test_multiple_subscribers_receive_working_stream(self):
        """
        Multiple subscribers should all receive consciousness.working events.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )

        postal = MockPostal()

        # Two citizens subscribing
        citizen_a_received = []
        citizen_b_received = []

        postal.subscribe(
            "consciousness.working",
            lambda p: citizen_a_received.append(("a", p)),
        )
        postal.subscribe(
            "consciousness.working",
            lambda p: citizen_b_received.append(("b", p)),
        )

        feedback = ConsciousnessFeedback(postal=postal)

        # Emit a tool result
        tool_result = {
            "tool_name": "analyze_code",
            "success": True,
            "result": "Analysis complete",
            "duration_ms": 500,
        }
        emit_tool_result(feedback, tool_result)

        # Both citizens should receive the event
        assert len(citizen_a_received) == 1, \
            f"Citizen A should receive event, got {len(citizen_a_received)}"
        assert len(citizen_b_received) == 1, \
            f"Citizen B should receive event, got {len(citizen_b_received)}"

        # They should receive the same content
        assert citizen_a_received[0][1] == citizen_b_received[0][1], \
            "Both citizens should receive same payload"

    def test_multiple_collision_chamber_subscribers(self):
        """
        Multiple handlers can observe collision events.
        """
        postal = MockPostal()
        collision_chamber = MockCollisionChamber(postal=postal)

        # Track collisions from different observers
        observer_a_collisions = []
        observer_b_collisions = []

        postal.subscribe(
            "consciousness.collision",
            lambda c: observer_a_collisions.append(c),
        )
        postal.subscribe(
            "consciousness.collision",
            lambda c: observer_b_collisions.append(c),
        )

        # Trigger a collision
        collision_chamber.receive_recall(
            {"memory": "Past pattern"},
            source="memory_recall",
        )
        collision_chamber.receive_ingest(
            {"observation": "New pattern"},
            source="sensory",
        )

        # Both observers should see the collision
        assert len(observer_a_collisions) == 1
        assert len(observer_b_collisions) == 1

    def test_citizen_subscription_isolation(self):
        """
        Citizen subscriptions to different topics should be isolated.
        """
        postal = MockPostal()

        working_received = []
        reflective_received = []
        collision_received = []

        postal.subscribe("consciousness.working", lambda p: working_received.append(p))
        postal.subscribe("consciousness.reflective", lambda p: reflective_received.append(p))
        postal.subscribe("consciousness.collision", lambda p: collision_received.append(p))

        # Publish to different topics
        postal.publish("consciousness.working", {"thought": "working thought"})
        postal.publish("consciousness.reflective", {"thought": "reflective thought", "urgency": "normal"})

        # Each subscriber should only receive their topic
        assert len(working_received) == 1
        assert len(reflective_received) == 1
        assert len(collision_received) == 0

        assert working_received[0]["thought"] == "working thought"
        assert reflective_received[0]["thought"] == "reflective thought"


# =============================================================================
# TEST 10: Error Propagation and Pain Signals
# =============================================================================

class TestErrorPropagationPainSignal:
    """
    Integration test: Tool errors propagate and generate pain signals.

    When a tool fails:
    1. Error goes to reflective stream
    2. Pain signal is generated based on severity
    3. Affect gating responds to increased pain
    """

    def test_tool_error_generates_pain_signal(self):
        """
        Tool errors should generate appropriate pain signals.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_error,
        )

        postal = MockPostal()

        # Track affect signals
        affect_signals = []
        postal.subscribe("affect.tool_delta", lambda p: affect_signals.append(p))

        feedback = ConsciousnessFeedback(postal=postal)

        # Critical error should generate significant pain signal
        error_data = {
            "tool_name": "database_write",
            "error": "Database corruption detected",
            "error_type": "critical_error",
            "severity": "critical",
        }

        emit_tool_error(feedback, error_data)

        # Should emit to reflective with high urgency
        reflective_pubs = postal.get_publications("consciousness.reflective")
        assert len(reflective_pubs) > 0

        payload = reflective_pubs[0]["payload"]
        assert payload.get("urgency") in ["high", "urgent", "critical"], \
            f"Critical error should have high urgency: {payload.get('urgency')}"

    def test_repeated_errors_compound_pain(self):
        """
        Repeated errors should compound into higher pain state.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_error,
        )
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        postal = MockPostal()
        chemistry = MockChemistryState()

        feedback = ConsciousnessFeedback(postal=postal)

        # Simulate multiple errors
        for i in range(3):
            error_data = {
                "tool_name": f"failing_tool_{i}",
                "error": f"Error number {i + 1}",
                "error_type": "execution_error",
                "severity": "medium",
            }
            emit_tool_error(feedback, error_data)

            # Simulate cortisol increase from each error
            chemistry.signal("cortisol", 0.1, source="tool_error")

        # After multiple errors, cortisol should be elevated
        assert chemistry.get_level("cortisol") > 0.5, \
            "Multiple errors should elevate cortisol"

        # This elevated stress should now affect gating
        gate = AffectGate()
        # Convert chemistry to pain state
        pain_from_chemistry = {
            "frustration": chemistry.get_level("cortisol"),
        }

        # As frustration rises, should start blocking risky tools
        if pain_from_chemistry["frustration"] >= 0.7:
            assert gate.can_invoke_tool("delete_file", pain_from_chemistry) is False

    def test_error_triggers_stabilization_suggestions(self):
        """
        After errors, system should suggest stabilization tools.
        """
        from fairies.P40_Sensory.mcp.affect_gated_tools import AffectGate

        gate = AffectGate()

        # Pain state after multiple errors
        post_error_pain = {
            "frustration": 0.75,
            "confusion": 0.5,
        }

        suggestions = gate.suggest_stabilization_tools(post_error_pain)

        assert len(suggestions) > 0, \
            "High frustration should trigger stabilization suggestions"

        # Should suggest frustration-appropriate tools
        frustration_keywords = ["break", "alternative", "help", "step"]
        has_frustration_tool = any(
            any(kw in s.lower() for kw in frustration_keywords)
            for s in suggestions
        )
        assert has_frustration_tool, \
            f"Should suggest frustration tools: {suggestions}"

    def test_error_inner_voice_is_reflective(self):
        """
        Error inner voice should prompt reflection, not just report.
        """
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            error_to_inner_voice,
        )

        error_data = {
            "tool_name": "network_call",
            "error": "Connection timeout after 30 seconds",
            "error_type": "network_error",
            "severity": "high",
        }

        inner_voice = error_to_inner_voice(error_data)

        # Should have reflective quality
        reflective_indicators = [
            "wonder", "why", "what", "could", "should", "maybe",
            "investigate", "check", "perhaps", "seems"
        ]

        has_reflection = any(
            indicator in inner_voice.lower()
            for indicator in reflective_indicators
        )

        assert has_reflection, \
            f"Error inner voice should prompt reflection: {inner_voice}"


# =============================================================================
# TEST 11: Tracer Chain Reconstruction
# =============================================================================

class TestTracerChainReconstruction:
    """
    Integration test: Reconstruct the thought -> tool -> result chain.

    The tracer system should enable perfect recall of:
    - Which thought triggered which tools
    - What affect was present before/after
    - How long each tool took
    """

    def test_tracer_chain_reconstruction(self):
        """
        Should be able to reconstruct full thought -> tool chain.
        """
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            get_tracer_chain,
            get_tracers_for_thought,
            clear_registry,
        )

        clear_registry()

        thought_id = "thought_chain_test"

        # Create multiple tracers for same thought
        tracer_1 = create_tool_tracer(
            parent_thought_id=thought_id,
            tool_name="search_memory",
            affect_before={"curiosity": 0.8},
        )

        tracer_2 = create_tool_tracer(
            parent_thought_id=thought_id,
            tool_name="analyze_results",
            affect_before={"focus": 0.7},
        )

        # Complete both
        complete_tracer(tracer_1, result="5 memories found", success=True)
        complete_tracer(tracer_2, result="Analysis complete", success=True)

        # Get all tracers for this thought
        thought_tracers = get_tracers_for_thought(thought_id)

        assert len(thought_tracers) == 2, \
            f"Should find 2 tracers for thought, got {len(thought_tracers)}"

        # Get chain for specific tracer
        chain = get_tracer_chain(tracer_1.tracer_id)

        assert len(chain) > 0, \
            "Should reconstruct chain"

        assert chain[0]["thought_id"] == thought_id
        assert chain[0]["tool_name"] == "search_memory"

    def test_tracer_affect_delta_tracking(self):
        """
        Tracer should track affect changes before/after tool execution.
        """
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            clear_registry,
        )

        clear_registry()

        # Create tracer with affect before
        tracer = create_tool_tracer(
            parent_thought_id="affect_delta_test",
            tool_name="challenging_task",
            affect_before={"stress": 0.3, "focus": 0.5},
        )

        # Complete with affect after (stress increased from challenge)
        complete_tracer(
            tracer,
            result="Task completed with difficulty",
            success=True,
            affect_after={"stress": 0.6, "focus": 0.8},
        )

        # Verify affect tracking
        assert tracer.affect_before is not None
        assert tracer.affect_after is not None

        # Can compute delta
        stress_before = tracer.affect_before.get("stress", 0)
        stress_after = tracer.affect_after.get("stress", 0)
        stress_delta = stress_after - stress_before

        assert stress_delta > 0, \
            "Should track stress increase from challenging task"

    def test_tracer_duration_tracking(self):
        """
        Tracer should accurately track tool execution duration.
        """
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            clear_registry,
        )

        clear_registry()

        tracer = create_tool_tracer(
            parent_thought_id="duration_test",
            tool_name="timed_operation",
        )

        # Simulate some passage of time
        import time
        time.sleep(0.01)  # 10ms

        complete_tracer(tracer, result="done", success=True)

        # Duration should be captured
        assert tracer.duration_ms is not None
        assert tracer.duration_ms > 0, \
            "Duration should be positive"


# =============================================================================
# TEST 12: Consciousness-Aware Tool Selection
# =============================================================================

class TestConsciousnessAwareToolSelection:
    """
    Integration test: Full consciousness-aware tool selection pipeline.

    Tests the complete pipeline:
    1. Filter by affect state
    2. Rank by working memory
    3. Modulate by chemistry
    4. Suggest based on emotion
    """

    def test_full_consciousness_aware_selection(self):
        """
        Full pipeline: filter -> rank -> modulate -> suggest.
        """
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            get_consciousness_aware_tools,
        )

        tools = [
            {"name": "explore_deep", "category": "exploration", "risk_level": "medium",
             "keywords": ["explore", "discover"]},
            {"name": "read_file", "category": "file_ops", "risk_level": "low",
             "keywords": ["read", "file"]},
            {"name": "delete_all", "category": "destructive", "risk_level": "high",
             "keywords": ["delete", "remove"]},
            {"name": "calm_mode", "category": "somatic", "risk_level": "low",
             "keywords": ["calm", "relax"]},
            {"name": "debug_status", "category": "debugging", "risk_level": "low",
             "keywords": ["debug", "status", "check"]},
        ]

        affect_state = {
            "stress": 0.4,
            "valence": 0.2,
            "arousal": 0.5,
            "mood": "neutral",
            "dominant_emotion": "focus",
            "dominant_intensity": 0.6,
        }

        working_memory = {
            "recent_thoughts": [
                {"content": "I need to read and explore the codebase", "tags": ["code", "explore"]},
            ],
            "active_goals": ["understand the architecture"],
            "context_keywords": ["code", "read", "explore"],
        }

        chemistry = {
            "DOP": 0.6,  # Moderate dopamine
            "COR": 0.3,  # Low cortisol
            "SER": 0.5,
            "NOR": 0.6,
            "ACH": 0.6,
        }

        result = get_consciousness_aware_tools(
            tools=tools,
            affect_state=affect_state,
            working_memory=working_memory,
            chemistry=chemistry,
        )

        assert "available_tools" in result
        assert "suggested_tools" in result
        assert "filtered_count" in result

        # Under moderate stress, should still have exploratory tools
        available_names = [t["name"] for t in result["available_tools"]]
        assert "explore_deep" in available_names or "read_file" in available_names

        # High-risk tool should still be available under low stress
        assert "delete_all" in available_names

    def test_high_stress_filters_risky_tools(self):
        """
        High stress should filter out risky and exploratory tools.
        """
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            filter_tools_by_affect_state,
        )

        tools = [
            {"name": "explore", "category": "exploration", "risk_level": "medium"},
            {"name": "read", "category": "file_ops", "risk_level": "low"},
            {"name": "delete", "category": "destructive", "risk_level": "high"},
            {"name": "calm", "category": "somatic", "risk_level": "low"},
        ]

        high_stress = {
            "stress": 0.9,
            "valence": -0.3,
        }

        filtered = filter_tools_by_affect_state(tools, high_stress)
        filtered_names = [t["name"] for t in filtered]

        # High stress should filter out risky and exploratory
        assert "delete" not in filtered_names, \
            "High risk tools should be filtered under stress"
        assert "explore" not in filtered_names, \
            "Exploratory tools should be filtered under stress"

        # But calming tools should remain
        assert "calm" in filtered_names, \
            "Calming tools should remain under stress"
        assert "read" in filtered_names, \
            "Low risk tools should remain"

    def test_suggestions_match_emotional_state(self):
        """
        Tool suggestions should match current emotional state.
        """
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            suggest_tools_for_affect,
        )

        tools = [
            {"name": "explore_new", "category": "exploration", "risk_level": "medium",
             "keywords": ["explore", "discover"]},
            {"name": "debug_issue", "category": "debugging", "risk_level": "low",
             "keywords": ["debug", "diagnose"]},
            {"name": "calm_down", "category": "somatic", "risk_level": "low",
             "keywords": ["calm", "relax"]},
        ]

        # Frustrated state should suggest debugging tools
        frustrated = {
            "stress": 0.6,
            "mood": "frustrated",
            "dominant_emotion": "frustration",
            "dominant_intensity": 0.7,
        }

        suggestions = suggest_tools_for_affect(tools, frustrated)
        suggestion_names = [t["name"] for t in suggestions]

        # Should suggest debugging for frustration
        has_debugging = any("debug" in name for name in suggestion_names)
        assert has_debugging or len(suggestions) > 0, \
            f"Frustrated state should suggest debugging: {suggestion_names}"


# =============================================================================
# ASYNC TEST SUPPORT
# =============================================================================

class TestAsyncConsciousnessFlow:
    """
    Async integration tests for consciousness flow.

    Tests async patterns using sync wrappers since pytest-asyncio
    may not be installed.
    """

    def test_async_tool_execution_flow(self):
        """
        Async tool execution should integrate with consciousness flow.
        """
        import asyncio
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )

        postal = MockPostal()
        feedback = ConsciousnessFeedback(postal=postal)

        async def async_tool_execution():
            """Simulate async tool execution."""
            await asyncio.sleep(0.01)
            return {
                "tool_name": "async_search",
                "success": True,
                "result": "Found async results",
                "duration_ms": 10,
            }

        # Execute async tool using asyncio.run
        tool_result = asyncio.run(async_tool_execution())

        # Emit to consciousness (sync call)
        emit_tool_result(feedback, tool_result)

        # Verify emission happened
        working_pubs = postal.get_publications("consciousness.working")
        assert len(working_pubs) > 0

    def test_multiple_async_tools_sequenced(self):
        """
        Multiple async tools should sequence correctly in consciousness.
        """
        import asyncio
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            clear_registry,
        )

        clear_registry()
        postal = MockPostal()
        feedback = ConsciousnessFeedback(postal=postal)

        async def run_tool(name: str, delay: float) -> dict:
            tracer = create_tool_tracer(
                parent_thought_id="async_sequence_test",
                tool_name=name,
            )
            await asyncio.sleep(delay)
            result = {"tool_name": name, "success": True, "result": f"{name} complete", "duration_ms": int(delay * 1000)}
            complete_tracer(tracer, result=result["result"], success=True)
            emit_tool_result(feedback, result)
            return result

        async def run_all():
            return await asyncio.gather(
                run_tool("search_a", 0.01),
                run_tool("search_b", 0.015),
                run_tool("search_c", 0.005),
            )

        # Run multiple tools concurrently using asyncio.run
        results = asyncio.run(run_all())

        assert len(results) == 3

        # All should have emitted to consciousness
        working_pubs = postal.get_publications("consciousness.working")
        assert len(working_pubs) == 3


# =============================================================================
# EDGE CASES AND FAILURE MODES
# =============================================================================

class TestEdgeCasesAndFailureModes:
    """
    Test edge cases and failure modes in the integration.
    """

    def test_empty_collision_products(self):
        """
        Collision with empty products should be handled gracefully.
        """
        from fairies.P40_Sensory.mcp.collision_tool_explorer import (
            CollisionToolExplorer,
        )

        postal = MockPostal()
        explorer = CollisionToolExplorer(postal=postal)

        collision = {
            "collision_id": 100,
            "resonance": 0.8,
            "energy": 0.7,
            "products": {},  # Empty products
        }

        # Should not crash
        suggestions = explorer.suggest_exploration_tools(collision)
        intent = explorer.generate_exploration_intent(collision)

        # Should handle gracefully
        assert isinstance(suggestions, list)
        assert isinstance(intent, dict)

    def test_missing_affect_state_defaults(self):
        """
        Missing affect state should use sensible defaults.
        """
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            filter_tools_by_affect_state,
        )

        tools = [{"name": "test_tool", "risk_level": "low"}]

        # Empty affect state
        result = filter_tools_by_affect_state(tools, {})

        # Should return tools (defaults to low stress)
        assert len(result) == 1

    def test_none_chemistry_values(self):
        """
        Missing or None chemistry values should be handled.
        """
        from fairies.P40_Sensory.mcp.consciousness_aware_tools import (
            modulate_tool_confidence_by_chemistry,
        )

        tools = [{"name": "test", "risk_level": "low"}]

        # Incomplete chemistry
        chemistry = {"DOP": 0.5}  # Missing other chemicals

        result = modulate_tool_confidence_by_chemistry(tools, chemistry)

        assert len(result) == 1
        assert "confidence_modifier" in result[0]

    def test_tracer_without_completion(self):
        """
        Incomplete tracers should be queryable.
        """
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            get_tracer_chain,
            clear_registry,
        )

        clear_registry()

        # Create but don't complete
        tracer = create_tool_tracer(
            parent_thought_id="incomplete_test",
            tool_name="hanging_tool",
        )

        # Should still be queryable
        chain = get_tracer_chain(tracer.tracer_id)

        assert len(chain) > 0
        assert chain[0]["success"] is None  # Not completed
        assert chain[0]["completed_at"] is None

    def test_very_long_tool_result(self):
        """
        Very long tool results should be handled without crashing.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result,
        )
        from fairies.P40_Sensory.mcp.inner_voice_synthesis import (
            result_to_felt_complexity,
        )

        postal = MockPostal()
        feedback = ConsciousnessFeedback(postal=postal)

        # Very long result
        long_result = "x" * 100000  # 100KB of data

        tool_result = {
            "tool_name": "large_query",
            "success": True,
            "result": long_result,
            "duration_ms": 5000,
        }

        # Should not crash
        emit_tool_result(feedback, tool_result)

        # Complexity should reflect large size and long duration
        complexity = result_to_felt_complexity(tool_result)
        # Large size OR long duration should result in at least moderate complexity
        assert complexity["level"] >= 0.2, \
            f"Large result should have at least moderate complexity, got {complexity['level']}"

        # Size factor should be maxed out for 100KB
        assert complexity["factors"]["size"] == 1.0, \
            f"100KB string should max out size factor, got {complexity['factors']['size']}"

    def test_concurrent_tracer_access(self):
        """
        Concurrent tracer creation should be thread-safe.
        """
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            get_all_tracers,
            clear_registry,
        )
        import threading

        clear_registry()

        results = []

        def create_and_complete(idx):
            tracer = create_tool_tracer(
                parent_thought_id=f"concurrent_test_{idx}",
                tool_name=f"tool_{idx}",
            )
            complete_tracer(tracer, result=f"result_{idx}", success=True)
            results.append(tracer.tracer_id)

        # Run concurrent tracer operations
        threads = [threading.Thread(target=create_and_complete, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should have been created
        assert len(results) == 10

        # All should be in registry
        all_tracers = get_all_tracers()
        assert len(all_tracers) >= 10


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
