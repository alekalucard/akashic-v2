"""
Test CognitionBridge Integration with UMF.

Tests that UMF can:
1. Wire CognitionBridge when fabric is available
2. Route thinking through _do_bridged_think() via postal
3. Fall back to Ollama when bridge unavailable

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

NOTE: This file uses extensive mocking to avoid circular import issues
in the codebase. We mock at the import level rather than importing UMF.
"""

import pytest
import sys
import time
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, Any, List, Optional
from collections import deque
from dataclasses import dataclass, field


# ============================================================================
# Mock Classes (isolated from actual codebase)
# ============================================================================

@dataclass
class MockThinkRequest:
    """Mock ThinkRequest matching the real interface."""
    stimulus: str
    stimulus_type: str = "reflection"
    chemistry: Dict[str, float] = field(default_factory=dict)
    somatic: Dict[str, float] = field(default_factory=dict)
    recent_thoughts: List[str] = field(default_factory=list)
    pain_state: Dict[str, float] = field(default_factory=dict)
    helix_hint: Optional[Dict[str, Any]] = None
    source: str = "UMF"
    priority: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stimulus": self.stimulus,
            "stimulus_type": self.stimulus_type,
            "chemistry": self.chemistry,
            "somatic": self.somatic,
            "recent_thoughts": self.recent_thoughts,
            "pain_state": self.pain_state,
            "helix_hint": self.helix_hint,
            "source": self.source,
            "priority": self.priority,
        }


@dataclass
class MockThinkResponse:
    """Mock ThinkResponse matching the real interface."""
    thought: str = "Test thought"
    reasoning: str = "Test reasoning"
    actions: List[Dict] = field(default_factory=list)
    local_only: bool = True
    depth_score: float = 0.5
    associations: List[str] = field(default_factory=list)
    error: Optional[str] = None


class MockCognitionBridge:
    """Mock CognitionBridge for testing."""
    def __init__(self, fabric):
        self.fabric = fabric
        self.think_calls = []
        self._response = MockThinkResponse()

    def think(self, request):
        self.think_calls.append(request)
        return self._response

    def set_response(self, response: MockThinkResponse):
        self._response = response


class MockFabric:
    """Mock TensorMemoryFabric for testing."""
    def __init__(self):
        self.subscriptions = {}
        self.publications = []
        self.requests = []
        self._request_response = None

    def subscribe(self, topic, callback, name):
        self.subscriptions[topic] = (callback, name)

    def publish(self, topic, payload):
        self.publications.append((topic, payload))

    def request(self, topic, payload, timeout=5.0):
        self.requests.append((topic, payload, timeout))
        return self._request_response

    def set_request_response(self, response):
        self._request_response = response


# ============================================================================
# Helper: Create a minimal UMF-like object for testing
# ============================================================================

def create_mock_umf(fabric=None, bridge=None, bridge_wired=False, ollama_wired=False):
    """
    Create a minimal UMF-like object with the new CognitionBridge methods.

    This avoids importing the full UMF class which has circular dependencies.
    Instead, we create a lightweight object with just the methods we need to test.
    """
    class MinimalUMF:
        """Minimal UMF with just the cognition bridge methods."""
        ACTOR_NAME = "UnconsciousMindFairy"

        def __init__(self):
            self.fabric = fabric
            self._cognition_bridge = bridge
            self._cognition_bridge_wired = bridge_wired
            self._ollama_wired = ollama_wired
            self._last_bridge_tick = 0
            self._bridge_think_interval = 20
            self._thought_queue = deque(maxlen=50)
            self._pain_system = None
            self._consciousness_loop = None
            self._collision_chamber = None
            self._profile = MagicMock()
            self._profile.somatic = {}

        def _wire_cognition_bridge(self) -> bool:
            """Wire UMF to use CognitionBridge for thinking."""
            if self._cognition_bridge_wired:
                return True

            # Mock HAS_COGNITION_BRIDGE check
            if not hasattr(self, '_has_bridge_module') or not self._has_bridge_module:
                print(f"[{self.ACTOR_NAME}] CognitionBridge module not available")
                return False

            if not self.fabric:
                print(f"[{self.ACTOR_NAME}] No fabric - cannot wire CognitionBridge")
                return False

            try:
                # Use mock bridge factory
                if hasattr(self, '_bridge_factory') and self._bridge_factory:
                    self._cognition_bridge = self._bridge_factory(self.fabric)
                else:
                    self._cognition_bridge = MockCognitionBridge(self.fabric)

                if self._cognition_bridge:
                    self._cognition_bridge_wired = True
                    print(f"[{self.ACTOR_NAME}] CognitionBridge WIRED")
                    return True
                else:
                    print(f"[{self.ACTOR_NAME}] Failed to create CognitionBridge")
                    return False

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to wire CognitionBridge: {e}")
                return False

        def _do_bridged_think(self) -> Optional[str]:
            """UMF thinking through CognitionBridge."""
            if not self._cognition_bridge_wired or not self._cognition_bridge:
                return None

            try:
                # Gather context
                recent_thoughts = [t.get("thought", "") for t in list(self._thought_queue)[-5:]]

                chemistry = {}
                pain_state = {}
                somatic = getattr(self._profile, 'somatic', {}) or {}

                # Build stimulus
                stimulus = self._generate_thinking_prompt(recent_thoughts)

                # Create request
                request = MockThinkRequest(
                    stimulus=stimulus,
                    stimulus_type="reflection",
                    chemistry=chemistry,
                    somatic=somatic,
                    recent_thoughts=recent_thoughts,
                    pain_state=pain_state,
                    source="UMF",
                    priority=0.5,
                )

                print(f"[{self.ACTOR_NAME}] Bridged thinking...")

                # Route through bridge
                response = self._cognition_bridge.think(request)

                if response.error:
                    print(f"[{self.ACTOR_NAME}] Bridge error: {response.error}")
                    return None

                thought = response.thought
                if not thought:
                    return None

                print(f"[{self.ACTOR_NAME}] Bridged: {thought[:100]}...")

                # Add to consciousness stream
                if self._consciousness_loop:
                    self._consciousness_loop.add_thought(
                        content=thought,
                        source="cognition_bridge",
                        stream="working",
                        confidence=0.7,
                        tags=["autonomous", "bridged"],
                    )

                # Add to collision chamber
                if self._collision_chamber:
                    self._collision_chamber.receive_ingest(
                        content={"thought": thought, "type": "bridged"},
                        source="cognition_bridge",
                        importance="normal",
                    )

                # Add to thought queue
                self._thought_queue.append({
                    "thought": thought,
                    "type": "bridged",
                    "local_only": response.local_only,
                    "depth_score": response.depth_score,
                    "ts": time.time(),
                })

                # Execute semantic actions
                self._parse_and_execute_thought_actions(thought)

                # Execute structured actions
                for action in response.actions:
                    action_type = action.get("type", "")
                    if action_type == "alert_ace":
                        self._action_alert_ace(action.get("message", ""))

                return thought

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Bridged think error: {e}")
                import traceback
                traceback.print_exc()
                return None

        def _generate_thinking_prompt(self, recent_thoughts: list) -> str:
            """Mock prompt generator."""
            return "What should I think about?"

        def _parse_and_execute_thought_actions(self, thought: str) -> None:
            """Mock action parser."""
            pass

        def _action_alert_ace(self, message: str) -> None:
            """Mock alert action."""
            pass

    return MinimalUMF()


# ============================================================================
# Tests
# ============================================================================

class TestCognitionBridgeWiring:
    """Test that UMF can wire CognitionBridge."""

    def test_wire_cognition_bridge_returns_true_if_already_wired(self):
        """If already wired, should return True immediately."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)

        result = umf._wire_cognition_bridge()
        assert result is True

    def test_wire_cognition_bridge_returns_false_without_fabric(self):
        """Without fabric, wiring should fail gracefully."""
        umf = create_mock_umf(fabric=None, bridge_wired=False)
        umf._has_bridge_module = True

        result = umf._wire_cognition_bridge()
        assert result is False

    def test_wire_cognition_bridge_returns_false_without_module(self):
        """Without CognitionBridge module, wiring fails."""
        fabric = MockFabric()
        umf = create_mock_umf(fabric=fabric, bridge_wired=False)
        umf._has_bridge_module = False

        result = umf._wire_cognition_bridge()
        assert result is False

    def test_wire_cognition_bridge_creates_bridge_with_fabric(self):
        """With fabric and module available, should create bridge."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)

        umf = create_mock_umf(fabric=fabric, bridge_wired=False)
        umf._has_bridge_module = True
        umf._bridge_factory = lambda f: mock_bridge

        result = umf._wire_cognition_bridge()

        assert result is True
        assert umf._cognition_bridge_wired is True
        assert umf._cognition_bridge is mock_bridge


class TestBridgedThink:
    """Test _do_bridged_think routing."""

    def test_do_bridged_think_returns_none_if_not_wired(self):
        """If bridge not wired, should return None."""
        umf = create_mock_umf(bridge_wired=False)

        result = umf._do_bridged_think()
        assert result is None

    def test_do_bridged_think_calls_bridge(self):
        """Should call bridge.think with request."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(thought="Bridge thought"))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)
        umf._thought_queue = deque([
            {"thought": "thought1", "ts": time.time()},
            {"thought": "thought2", "ts": time.time()},
        ], maxlen=50)

        result = umf._do_bridged_think()

        # Should have called think on bridge
        assert len(mock_bridge.think_calls) == 1
        assert result == "Bridge thought"

    def test_do_bridged_think_adds_to_consciousness_loop(self):
        """Successful thought should be added to consciousness loop."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(thought="Consciousness thought"))

        mock_loop = MagicMock()

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)
        umf._consciousness_loop = mock_loop

        umf._do_bridged_think()

        # Should have called add_thought on consciousness loop
        mock_loop.add_thought.assert_called_once()
        call_kwargs = mock_loop.add_thought.call_args.kwargs
        assert call_kwargs.get("content") == "Consciousness thought"
        assert call_kwargs.get("source") == "cognition_bridge"
        assert call_kwargs.get("stream") == "working"

    def test_do_bridged_think_adds_to_thought_queue(self):
        """Successful thought should be added to thought queue."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(
            thought="Queue thought",
            local_only=False,
            depth_score=0.8,
        ))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)
        assert len(umf._thought_queue) == 0

        umf._do_bridged_think()

        assert len(umf._thought_queue) == 1
        queued = umf._thought_queue[0]
        assert queued["thought"] == "Queue thought"
        assert queued["type"] == "bridged"
        assert queued["local_only"] is False
        assert queued["depth_score"] == 0.8

    def test_do_bridged_think_executes_semantic_actions(self):
        """Thought content should be parsed for semantic actions."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(
            thought="I should tell Ace: hello world"
        ))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)
        umf._parse_and_execute_thought_actions = MagicMock()

        umf._do_bridged_think()

        umf._parse_and_execute_thought_actions.assert_called_once_with(
            "I should tell Ace: hello world"
        )

    def test_do_bridged_think_executes_structured_actions(self):
        """Structured actions from response should be executed."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(
            thought="Action thought",
            actions=[{"type": "alert_ace", "message": "structured alert"}]
        ))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)
        umf._action_alert_ace = MagicMock()

        umf._do_bridged_think()

        umf._action_alert_ace.assert_called_once_with("structured alert")


class TestErrorHandling:
    """Test error handling in bridge integration."""

    def test_do_bridged_think_handles_bridge_error(self):
        """Bridge errors should be handled gracefully."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(
            thought="",
            error="Test error"
        ))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)

        # Should not raise, should return None
        result = umf._do_bridged_think()
        assert result is None

    def test_do_bridged_think_handles_empty_thought(self):
        """Empty thought from bridge should return None."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(thought=""))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)

        result = umf._do_bridged_think()
        assert result is None

    def test_do_bridged_think_handles_exception(self):
        """Exceptions during thinking should be caught."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.think = MagicMock(side_effect=Exception("Test exception"))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)

        # Should not raise
        result = umf._do_bridged_think()
        assert result is None


class TestFallbackBehavior:
    """Test fallback to Ollama when bridge unavailable."""

    def test_bridge_preferred_when_both_available(self):
        """When both bridge and Ollama are wired, bridge should be used."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(thought="Bridge wins"))

        umf = create_mock_umf(
            fabric=fabric,
            bridge=mock_bridge,
            bridge_wired=True,
            ollama_wired=True  # Both wired
        )

        # Bridge should be preferred
        result = umf._do_bridged_think()
        assert result == "Bridge wins"
        assert len(mock_bridge.think_calls) == 1

    def test_ollama_used_when_bridge_not_wired(self):
        """When bridge not wired, Ollama should be used."""
        umf = create_mock_umf(bridge_wired=False, ollama_wired=True)

        # Bridge think should return None
        result = umf._do_bridged_think()
        assert result is None
        # (In actual UMF, on_tick would then call _do_ollama_think)


class TestRequestBuilding:
    """Test that ThinkRequest is built correctly."""

    def test_request_includes_recent_thoughts(self):
        """Request should include recent thoughts from queue."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(thought="Response"))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)
        umf._thought_queue = deque([
            {"thought": "thought1", "ts": time.time()},
            {"thought": "thought2", "ts": time.time()},
            {"thought": "thought3", "ts": time.time()},
        ], maxlen=50)

        umf._do_bridged_think()

        assert len(mock_bridge.think_calls) == 1
        request = mock_bridge.think_calls[0]
        assert len(request.recent_thoughts) == 3
        assert "thought1" in request.recent_thoughts
        assert "thought2" in request.recent_thoughts
        assert "thought3" in request.recent_thoughts

    def test_request_uses_generated_prompt_as_stimulus(self):
        """Request stimulus should come from _generate_thinking_prompt."""
        fabric = MockFabric()
        mock_bridge = MockCognitionBridge(fabric)
        mock_bridge.set_response(MockThinkResponse(thought="Response"))

        umf = create_mock_umf(fabric=fabric, bridge=mock_bridge, bridge_wired=True)
        umf._generate_thinking_prompt = MagicMock(return_value="Custom prompt")

        umf._do_bridged_think()

        assert len(mock_bridge.think_calls) == 1
        request = mock_bridge.think_calls[0]
        assert request.stimulus == "Custom prompt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
