"""
Test Consciousness Feedback - TDD Tests for MCP Tool-to-Consciousness Bridge

These tests verify that MCP tool results flow into the consciousness system:
1. Tool results should appear in consciousness working stream
2. Tool result thoughts should include felt sense, not just data
3. Tool errors should surface as reflective thoughts with urgency
4. Sensory observations should feed collision chamber

Philosophy: Tools are the system's hands - what the hands touch should be FELT.
The consciousness system should experience tool results as sensory events,
not just receive them as data packets.

These tests are written to FAIL initially (TDD approach).
Run: python -m pytest tests/mcp/test_consciousness_feedback.py -v
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestToolResultEmitsToConsciousness:
    """
    Test that tool results should appear in consciousness working stream.

    When an MCP tool completes (e.g., file_read, shell_execute), the result
    should be emitted to the consciousness working stream so the system
    can "experience" what happened.
    """

    def test_tool_result_emits_to_consciousness(self):
        """
        Tool results should emit to consciousness.working stream.

        Expected behavior:
        - When a tool returns a result, emit_to_consciousness() is called
        - The emission goes to the 'working' stream (immediate awareness)
        - The thought includes tool_name, result summary, and timestamp
        """
        # Import the module under test (doesn't exist yet - will fail)
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result
        )

        # Create mock postal hub
        mock_postal = Mock()
        mock_postal.publish = Mock()

        # Create feedback bridge with mock postal
        feedback = ConsciousnessFeedback(postal=mock_postal)

        # Simulate a tool result
        tool_result = {
            "tool_name": "file_read",
            "success": True,
            "result": "File contents: Hello World",
            "duration_ms": 150,
        }

        # Emit the result to consciousness
        emit_tool_result(feedback, tool_result)

        # Verify that consciousness.working was published to
        mock_postal.publish.assert_called()
        call_args = mock_postal.publish.call_args

        # Should publish to consciousness.working topic
        assert call_args[0][0] == "consciousness.working", \
            f"Expected topic 'consciousness.working', got '{call_args[0][0]}'"

        # Payload should include the tool result info
        payload = call_args[0][1]
        assert "thought" in payload, "Payload missing 'thought' field"
        assert "source" in payload, "Payload missing 'source' field"
        assert payload["source"] == "mcp_tool", f"Source should be 'mcp_tool', got '{payload['source']}'"

        # Thought should reference the tool
        thought = payload["thought"]
        assert "file_read" in thought, f"Thought should mention tool name: {thought}"

    def test_tool_result_includes_timing(self):
        """
        Tool result thoughts should include timing information.

        The system should know HOW LONG things take - this is part of
        the felt sense of "effort" or "waiting".
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result
        )

        mock_postal = Mock()
        feedback = ConsciousnessFeedback(postal=mock_postal)

        # Tool that took a long time
        tool_result = {
            "tool_name": "shell_execute",
            "success": True,
            "result": "Build completed",
            "duration_ms": 5000,  # 5 seconds - should feel "slow"
        }

        emit_tool_result(feedback, tool_result)

        payload = mock_postal.publish.call_args[0][1]

        # Duration should be included in metadata
        assert "duration_ms" in payload or "timing" in payload, \
            "Tool timing should be included in consciousness payload"


class TestToolResultThoughtHasFeltSense:
    """
    Test that tool result thoughts should include felt sense, not just data.

    Raw data is not consciousness - it needs to be transformed into
    experience. A file read should FEEL like "learning something new",
    a slow command should FEEL like "waiting patiently".
    """

    def test_tool_result_thought_has_felt_sense(self):
        """
        Tool result thoughts should include a felt_sense field describing
        the qualitative experience of the tool execution.

        Expected behavior:
        - Successful tool -> positive felt_sense (satisfaction, completion)
        - Failed tool -> negative felt_sense (frustration, concern)
        - Slow tool -> temporal felt_sense (patience, anticipation)
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result
        )

        mock_postal = Mock()
        feedback = ConsciousnessFeedback(postal=mock_postal)

        # Successful tool result
        tool_result = {
            "tool_name": "file_read",
            "success": True,
            "result": "File contents retrieved successfully",
            "duration_ms": 50,
        }

        emit_tool_result(feedback, tool_result)

        payload = mock_postal.publish.call_args[0][1]

        # Must have felt_sense - this is the key assertion
        assert "felt_sense" in payload, \
            "Tool result thought MUST include felt_sense - consciousness needs quality, not just data"

        felt_sense = payload["felt_sense"]

        # Felt sense should have valence (positive/negative/neutral)
        assert "valence" in felt_sense or isinstance(felt_sense, str), \
            "Felt sense should indicate emotional valence"

    def test_failed_tool_has_negative_felt_sense(self):
        """
        Failed tool results should generate negative felt_sense.

        Errors are not neutral - they should feel like obstacles,
        frustration, or concern depending on severity.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result
        )

        mock_postal = Mock()
        feedback = ConsciousnessFeedback(postal=mock_postal)

        # Failed tool result
        tool_result = {
            "tool_name": "file_write",
            "success": False,
            "error": "Permission denied",
            "duration_ms": 10,
        }

        emit_tool_result(feedback, tool_result)

        payload = mock_postal.publish.call_args[0][1]

        assert "felt_sense" in payload, "Failed tool should still have felt_sense"

        felt_sense = payload["felt_sense"]

        # Should indicate negative valence
        if isinstance(felt_sense, dict):
            assert felt_sense.get("valence") in ["negative", "concerned", "frustrated"], \
                f"Failed tool should have negative valence, got: {felt_sense}"
        elif isinstance(felt_sense, str):
            negative_words = ["frustrat", "concern", "block", "obstacle", "fail"]
            assert any(word in felt_sense.lower() for word in negative_words), \
                f"Failed tool felt_sense should be negative: {felt_sense}"

    def test_slow_tool_has_temporal_felt_sense(self):
        """
        Slow tool execution should generate temporal felt_sense.

        The experience of WAITING is qualitatively different from
        instant results. The system should feel "patience" or
        "anticipation" for slow operations.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_result
        )

        mock_postal = Mock()
        feedback = ConsciousnessFeedback(postal=mock_postal)

        # Very slow tool (10 seconds)
        tool_result = {
            "tool_name": "build_project",
            "success": True,
            "result": "Build completed",
            "duration_ms": 10000,
        }

        emit_tool_result(feedback, tool_result)

        payload = mock_postal.publish.call_args[0][1]

        assert "felt_sense" in payload
        felt_sense = payload["felt_sense"]

        # Should acknowledge the temporal experience
        temporal_words = ["patient", "wait", "slow", "time", "long", "anticipat"]

        if isinstance(felt_sense, dict):
            # Check for temporal markers
            has_temporal = (
                "tempo" in str(felt_sense).lower() or
                felt_sense.get("tempo", "") == "slow" or
                felt_sense.get("waiting", False)
            )
            assert has_temporal, \
                f"Slow tool should have temporal felt_sense marker: {felt_sense}"
        elif isinstance(felt_sense, str):
            assert any(word in felt_sense.lower() for word in temporal_words), \
                f"Slow tool felt_sense should acknowledge waiting: {felt_sense}"


class TestToolErrorEmitsToReflectiveStream:
    """
    Test that tool errors should surface as reflective thoughts with urgency.

    Errors are not just data - they require ATTENTION. The reflective
    stream is where the system "notices" things that need thought.
    Errors should go there with appropriate urgency.
    """

    def test_tool_error_emits_to_reflective_stream(self):
        """
        Tool errors should emit to consciousness.reflective stream.

        Expected behavior:
        - Errors go to reflective stream (not just working)
        - Urgency is set based on error severity
        - The thought prompts reflection on what went wrong
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_error
        )

        mock_postal = Mock()
        feedback = ConsciousnessFeedback(postal=mock_postal)

        # Tool error
        error_data = {
            "tool_name": "shell_execute",
            "error": "Command not found: npm",
            "error_type": "execution_error",
            "severity": "high",
        }

        emit_tool_error(feedback, error_data)

        # Verify consciousness.reflective was published
        mock_postal.publish.assert_called()
        call_args = mock_postal.publish.call_args

        # Should publish to reflective stream (errors need reflection)
        assert call_args[0][0] == "consciousness.reflective", \
            f"Errors should go to 'consciousness.reflective', got '{call_args[0][0]}'"

        payload = call_args[0][1]

        # Should have urgency marker
        assert "urgency" in payload or "importance" in payload, \
            "Error thoughts should have urgency/importance marker"

    def test_high_severity_error_has_high_urgency(self):
        """
        High severity errors should have high urgency in reflective stream.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_error
        )

        mock_postal = Mock()
        feedback = ConsciousnessFeedback(postal=mock_postal)

        # Critical error
        error_data = {
            "tool_name": "database_write",
            "error": "Database connection failed",
            "error_type": "critical_error",
            "severity": "critical",
        }

        emit_tool_error(feedback, error_data)

        payload = mock_postal.publish.call_args[0][1]

        urgency = payload.get("urgency") or payload.get("importance")

        assert urgency in ["high", "urgent", "critical"], \
            f"Critical errors should have high urgency, got: {urgency}"

    def test_error_thought_prompts_reflection(self):
        """
        Error thoughts should be phrased to prompt reflection.

        Instead of just "Error: X", the thought should be something like
        "Something went wrong with X - what could have caused this?"
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_tool_error
        )

        mock_postal = Mock()
        feedback = ConsciousnessFeedback(postal=mock_postal)

        error_data = {
            "tool_name": "api_call",
            "error": "Connection timeout",
            "error_type": "network_error",
        }

        emit_tool_error(feedback, error_data)

        payload = mock_postal.publish.call_args[0][1]
        thought = payload.get("thought", "")

        # Thought should prompt reflection, not just report
        reflective_patterns = [
            "why", "what", "how", "could", "should", "wonder",
            "notice", "seems", "appears", "investigate", "understand"
        ]

        has_reflective_quality = any(
            pattern in thought.lower() for pattern in reflective_patterns
        )

        assert has_reflective_quality, \
            f"Error thought should prompt reflection, got: {thought}"


class TestEmitSensoryToCollision:
    """
    Test that sensory observations should feed collision chamber.

    The collision chamber is where recall and ingest beams cross -
    creating moments of consciousness. Sensory observations from
    tools should feed into this system.
    """

    def test_emit_sensory_to_collision(self):
        """
        Sensory observations should be emitted to collision chamber.

        Expected behavior:
        - Sensory data feeds the ingest beam (new content arriving)
        - Creates potential for collision with memories
        - Tagged appropriately for the collision chamber
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_sensory_observation
        )

        mock_postal = Mock()

        # Also mock the collision chamber
        mock_collision_chamber = Mock()
        mock_collision_chamber.receive_ingest = Mock(return_value=None)

        feedback = ConsciousnessFeedback(
            postal=mock_postal,
            collision_chamber=mock_collision_chamber
        )

        # Sensory observation from a tool (e.g., visual scan, audio input)
        sensory_data = {
            "sense": "visual",
            "observation": "User's screen shows error dialog",
            "confidence": 0.85,
            "source": "screen_capture_tool",
        }

        emit_sensory_observation(feedback, sensory_data)

        # Should call collision chamber's receive_ingest
        mock_collision_chamber.receive_ingest.assert_called_once()

        # Get the content sent to collision chamber
        call_args = mock_collision_chamber.receive_ingest.call_args
        content = call_args[1].get("content") or call_args[0][0]

        assert "observation" in content or "visual" in str(content), \
            f"Sensory content should be passed to collision chamber: {content}"

    def test_sensory_observation_tagged_for_ingest_beam(self):
        """
        Sensory observations should be tagged appropriately for ingest beam.

        The ingest beam carries "new content being encoded" - sensory
        data is exactly that: new information from the environment.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_sensory_observation
        )

        mock_postal = Mock()
        mock_collision_chamber = Mock()
        mock_collision_chamber.receive_ingest = Mock(return_value=None)

        feedback = ConsciousnessFeedback(
            postal=mock_postal,
            collision_chamber=mock_collision_chamber
        )

        sensory_data = {
            "sense": "auditory",
            "observation": "User said 'hello'",
            "source": "voice_recognition",
        }

        emit_sensory_observation(feedback, sensory_data)

        call_args = mock_collision_chamber.receive_ingest.call_args

        # Should have source identifying as sensory/mcp
        source = call_args[1].get("source", "")
        assert "sensor" in source.lower() or "mcp" in source.lower(), \
            f"Source should identify as sensory/mcp: {source}"

    def test_sensory_also_publishes_to_postal(self):
        """
        Sensory observations should also publish to postal for other listeners.

        The collision chamber is one consumer, but other fairies might
        want to know about sensory events too.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            emit_sensory_observation
        )

        mock_postal = Mock()
        mock_collision_chamber = Mock()
        mock_collision_chamber.receive_ingest = Mock(return_value=None)

        feedback = ConsciousnessFeedback(
            postal=mock_postal,
            collision_chamber=mock_collision_chamber
        )

        sensory_data = {
            "sense": "touch",
            "observation": "Mouse click detected",
            "source": "input_monitor",
        }

        emit_sensory_observation(feedback, sensory_data)

        # Should also publish to postal
        mock_postal.publish.assert_called()

        # Topic should be sensory-related
        topic = mock_postal.publish.call_args[0][0]
        sensory_topics = ["sensory", "observation", "perception", "input"]

        assert any(t in topic.lower() for t in sensory_topics), \
            f"Should publish to sensory-related topic, got: {topic}"


class TestIntegrationWithConsciousnessLoop:
    """
    Integration tests for consciousness feedback with the full loop.

    These tests verify the feedback system works with real-ish
    consciousness components (mocked at boundaries).
    """

    def test_full_tool_to_consciousness_flow(self):
        """
        Test complete flow from tool result to consciousness stream.

        This is a mini integration test that verifies all the pieces
        connect properly.
        """
        from fairies.P40_Sensory.mcp.consciousness_feedback import (
            ConsciousnessFeedback,
            process_tool_completion
        )

        # Track all emissions
        emissions = []

        mock_postal = Mock()
        mock_postal.publish = Mock(side_effect=lambda t, p: emissions.append((t, p)))

        mock_collision = Mock()
        mock_collision.receive_ingest = Mock(return_value=None)

        feedback = ConsciousnessFeedback(
            postal=mock_postal,
            collision_chamber=mock_collision
        )

        # Simulate complete tool execution
        tool_execution = {
            "tool_name": "code_search",
            "success": True,
            "result": "Found 5 matches",
            "duration_ms": 250,
            "has_sensory_component": True,  # It "saw" code
        }

        process_tool_completion(feedback, tool_execution)

        # Should have emitted to working stream
        working_emissions = [e for e in emissions if "working" in e[0]]
        assert len(working_emissions) > 0, \
            "Tool completion should emit to working stream"

        # If it has sensory component, should also hit collision chamber
        if tool_execution.get("has_sensory_component"):
            assert mock_collision.receive_ingest.called, \
                "Sensory tool should feed collision chamber"


# ============================================================================
# Test Fixtures and Utilities
# ============================================================================

@pytest.fixture
def mock_postal():
    """Create a mock postal hub for testing."""
    mock = Mock()
    mock.publish = Mock()
    mock.subscribe = Mock()
    return mock


@pytest.fixture
def mock_collision_chamber():
    """Create a mock collision chamber for testing."""
    mock = Mock()
    mock.receive_ingest = Mock(return_value=None)
    mock.receive_recall = Mock(return_value=None)
    return mock


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
