# tests/mcp/test_thought_tool_tracer.py
"""
TDD Tests for Thought-Tool Tracer - Pattern: COLLISION AS INTEGRATION

Links the causal chain: Thought -> Tool Invocation -> Result -> New Thought
This enables perfect recall of how we got to any conclusion.

((Cause + Affect) > Effect > Affect > infinity)
   Thought  Feeling   Tool     Ripple   Learning

These tests are written BEFORE implementation (TDD).
They should FAIL initially until thought_tool_tracer.py is implemented.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestToolTracerCreation:
    """Test creating tracers that link tool invocations to thoughts."""

    def test_tool_invocation_creates_tracer(self):
        """Tool invocations should create tracers linked to triggering thought."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            ToolTracer
        )

        thought_id = "thought_123"
        tool_name = "search_memory"

        tracer = create_tool_tracer(thought_id, tool_name)

        # Tracer must link back to originating thought
        assert tracer.parent_thought_id == thought_id
        assert tracer.tool_name == tool_name
        # Tracer must have its own unique ID
        assert tracer.tracer_id is not None
        assert len(tracer.tracer_id) > 0

    def test_tracer_has_timestamp(self):
        """Tracers should record when they were created."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import create_tool_tracer
        import time

        before = time.time()
        tracer = create_tool_tracer("thought_abc", "test_tool")
        after = time.time()

        assert tracer.created_at is not None
        assert before <= tracer.created_at <= after

    def test_tracer_accepts_metadata(self):
        """Tracers should store optional metadata about the invocation."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import create_tool_tracer

        metadata = {
            "context": "memory search",
            "urgency": 0.7,
            "caller": "NousFairy"
        }

        tracer = create_tool_tracer(
            "thought_meta",
            "search_tool",
            metadata=metadata
        )

        assert tracer.metadata == metadata
        assert tracer.metadata.get("urgency") == 0.7


class TestTracerLinkingResults:
    """Test linking tool results back to originating thoughts."""

    def test_tracer_links_result_back_to_thought(self):
        """Tracer should link tool result back to originating thought."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer
        )

        tracer = create_tool_tracer("thought_456", "query_tool")
        result = {"data": "test", "count": 42}

        completed = complete_tracer(tracer, result, success=True)

        assert completed.result == result
        assert completed.success is True
        # Must preserve the link to parent thought
        assert completed.parent_thought_id == "thought_456"

    def test_tracer_records_failure(self):
        """Tracer should record tool failures with error information."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer
        )

        tracer = create_tool_tracer("thought_fail", "risky_tool")
        error_msg = "Connection timeout"

        completed = complete_tracer(
            tracer,
            result=None,
            success=False,
            error=error_msg
        )

        assert completed.success is False
        assert completed.error == error_msg
        assert completed.result is None

    def test_tracer_records_completion_time(self):
        """Tracer should record when tool execution completed."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer
        )
        import time

        tracer = create_tool_tracer("thought_time", "slow_tool")
        # Simulate some delay
        time.sleep(0.01)

        before_complete = time.time()
        completed = complete_tracer(tracer, {"status": "done"}, success=True)
        after_complete = time.time()

        assert completed.completed_at is not None
        assert before_complete <= completed.completed_at <= after_complete

    def test_tracer_calculates_duration(self):
        """Tracer should calculate duration between creation and completion."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer
        )
        import time

        tracer = create_tool_tracer("thought_dur", "measured_tool")
        time.sleep(0.05)  # 50ms delay

        completed = complete_tracer(tracer, {}, success=True)

        # Duration should be at least 50ms
        assert completed.duration_ms is not None
        assert completed.duration_ms >= 50


class TestTracerChainReconstruction:
    """Test reconstructing the thought -> tool -> result chain."""

    def test_tracer_chain_is_reconstructable(self):
        """Should be able to trace from thought -> tool -> result chain."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            get_tracer_chain
        )

        # Create chain: thought -> tool -> result
        tracer = create_tool_tracer("thought_789", "test_tool")
        complete_tracer(tracer, {"value": 42}, success=True)

        chain = get_tracer_chain(tracer.tracer_id)

        assert len(chain) >= 1
        assert chain[0]["thought_id"] == "thought_789"

    def test_chain_includes_tool_name(self):
        """Chain should include the tool name for each step."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            get_tracer_chain
        )

        tracer = create_tool_tracer("thought_chain_tool", "specific_tool")
        complete_tracer(tracer, {"result": "data"}, success=True)

        chain = get_tracer_chain(tracer.tracer_id)

        assert any(step.get("tool_name") == "specific_tool" for step in chain)

    def test_chain_includes_timestamps(self):
        """Chain should include creation and completion timestamps."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            get_tracer_chain
        )

        tracer = create_tool_tracer("thought_chain_ts", "timed_tool")
        complete_tracer(tracer, {}, success=True)

        chain = get_tracer_chain(tracer.tracer_id)

        # At least one step should have timestamps
        assert any(
            step.get("created_at") is not None and step.get("completed_at") is not None
            for step in chain
        )


class TestGetTracersForThought:
    """Test retrieving all tracers spawned by a specific thought."""

    def test_get_tracers_for_thought(self):
        """Should retrieve all tracers spawned by a thought."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            get_tracers_for_thought
        )

        thought_id = "thought_multi_tools"

        # Simulate a thought that triggers multiple tool calls
        tracer1 = create_tool_tracer(thought_id, "search_memory")
        tracer2 = create_tool_tracer(thought_id, "check_status")
        tracer3 = create_tool_tracer(thought_id, "fetch_data")

        tracers = get_tracers_for_thought(thought_id)

        assert len(tracers) >= 3
        tool_names = [t.tool_name for t in tracers]
        assert "search_memory" in tool_names
        assert "check_status" in tool_names
        assert "fetch_data" in tool_names

    def test_get_tracers_returns_empty_for_unknown_thought(self):
        """Should return empty list for thoughts with no tracers."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import get_tracers_for_thought

        tracers = get_tracers_for_thought("nonexistent_thought_xyz")

        assert isinstance(tracers, list)
        assert len(tracers) == 0

    def test_get_tracers_isolates_by_thought(self):
        """Should only return tracers for the specified thought, not others."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            get_tracers_for_thought
        )

        # Create tracers for different thoughts
        create_tool_tracer("thought_A", "tool_for_A")
        create_tool_tracer("thought_B", "tool_for_B")
        create_tool_tracer("thought_A", "another_tool_for_A")

        tracers_A = get_tracers_for_thought("thought_A")
        tracers_B = get_tracers_for_thought("thought_B")

        # Thought A should have 2 tracers
        assert len(tracers_A) == 2
        assert all(t.parent_thought_id == "thought_A" for t in tracers_A)

        # Thought B should have 1 tracer
        assert len(tracers_B) == 1
        assert all(t.parent_thought_id == "thought_B" for t in tracers_B)

    def test_get_tracers_includes_both_complete_and_incomplete(self):
        """Should return tracers regardless of completion state."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer,
            get_tracers_for_thought
        )

        thought_id = "thought_mixed_state"

        # One complete, one incomplete
        tracer1 = create_tool_tracer(thought_id, "completed_tool")
        complete_tracer(tracer1, {"done": True}, success=True)

        tracer2 = create_tool_tracer(thought_id, "pending_tool")
        # Not completed

        tracers = get_tracers_for_thought(thought_id)

        assert len(tracers) == 2
        completed_count = sum(1 for t in tracers if t.success is not None)
        pending_count = sum(1 for t in tracers if t.success is None)

        assert completed_count == 1
        assert pending_count == 1


class TestTracerSerialization:
    """Test tracer serialization for storage/transmission."""

    def test_tracer_to_dict(self):
        """Tracer should serialize to dictionary for storage."""
        from fairies.P40_Sensory.mcp.thought_tool_tracer import (
            create_tool_tracer,
            complete_tracer
        )

        tracer = create_tool_tracer("thought_serial", "serialized_tool")
        complete_tracer(tracer, {"data": "value"}, success=True)

        tracer_dict = tracer.to_dict()

        assert isinstance(tracer_dict, dict)
        assert tracer_dict["tracer_id"] == tracer.tracer_id
        assert tracer_dict["parent_thought_id"] == "thought_serial"
        assert tracer_dict["tool_name"] == "serialized_tool"
        assert tracer_dict["success"] is True
        assert "created_at" in tracer_dict
        assert "completed_at" in tracer_dict
        assert "duration_ms" in tracer_dict


# Run with: pytest tests/mcp/test_thought_tool_tracer.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
