"""
Test AKP Protocol Message Creation and Parsing.

TDD tests for akp_protocol.py - these tests define the expected interface
for the Akashic Protocol message handling module.

Tests:
1. test_handshake_message_creation - Should create valid HANDSHAKE message
2. test_consciousness_event_creation - Should create valid CONSCIOUSNESS event
3. test_subscribe_message_creation - Should create valid SUBSCRIBE message
4. test_publish_message_creation - Should create valid PUBLISH message
5. test_heartbeat_message_creation - Should create valid HEARTBEAT message
6. test_parse_message - Should parse incoming messages correctly

Run with: python -m pytest tests/mcp/test_akp_protocol.py -v
"""

import sys
import time
import json
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "postal_core" / "python"))

import pytest

# Import the module under test - this should fail initially (TDD)
# The module will be created at: postal_core/python/postal_core/akp_protocol.py
try:
    from postal_core import akp_protocol
except ImportError:
    # Create a placeholder that will cause tests to fail with clear message
    akp_protocol = None


def _skip_if_not_implemented():
    """Skip test if akp_protocol module is not yet implemented."""
    if akp_protocol is None:
        pytest.skip("akp_protocol module not yet implemented (TDD: write code to make this pass)")


# =============================================================================
# HANDSHAKE MESSAGE TESTS
# =============================================================================

class TestHandshakeMessageCreation:
    """Tests for creating valid HANDSHAKE messages."""

    @pytest.fixture(autouse=True)
    def check_implementation(self):
        """Ensure module is implemented before running tests."""
        _skip_if_not_implemented()

    def test_handshake_message_creation_minimal(self):
        """Should create valid HANDSHAKE message with minimal required fields."""
        msg = akp_protocol.create_handshake(
            name="ClaudeCode",
            capabilities=["reasoning", "coding"]
        )

        assert msg["type"] == "HANDSHAKE"
        assert msg["name"] == "ClaudeCode"
        assert msg["capabilities"] == ["reasoning", "coding"]
        assert "ts" in msg  # Should have timestamp

    def test_handshake_message_creation_full(self):
        """Should create valid HANDSHAKE message with all optional fields."""
        msg = akp_protocol.create_handshake(
            name="ClaudeCode",
            capabilities=["reasoning", "coding", "analysis"],
            version="1.0.0",
            auth_token="Bearer token123",
            wants_consciousness=True,
            plane_affinity="P30_Cognition",
            protocol_version="1.0"
        )

        assert msg["type"] == "HANDSHAKE"
        assert msg["name"] == "ClaudeCode"
        assert msg["capabilities"] == ["reasoning", "coding", "analysis"]
        assert msg["version"] == "1.0.0"
        assert msg["auth_token"] == "Bearer token123"
        assert msg["wants_consciousness"] is True
        assert msg["plane_affinity"] == "P30_Cognition"
        assert msg["protocol_version"] == "1.0"

    def test_handshake_message_is_json_serializable(self):
        """HANDSHAKE message should be JSON serializable."""
        msg = akp_protocol.create_handshake(
            name="TestMind",
            capabilities=["test"]
        )

        # Should not raise
        json_str = json.dumps(msg)
        assert isinstance(json_str, str)

        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed["type"] == "HANDSHAKE"
        assert parsed["name"] == "TestMind"

    def test_handshake_message_requires_name(self):
        """HANDSHAKE should require name parameter."""
        with pytest.raises((TypeError, ValueError)):
            akp_protocol.create_handshake(capabilities=["test"])

    def test_handshake_message_requires_capabilities(self):
        """HANDSHAKE should require capabilities parameter."""
        with pytest.raises((TypeError, ValueError)):
            akp_protocol.create_handshake(name="TestMind")


# =============================================================================
# CONSCIOUSNESS EVENT TESTS
# =============================================================================

class TestConsciousnessEventCreation:
    """Tests for creating valid CONSCIOUSNESS events."""

    @pytest.fixture(autouse=True)
    def check_implementation(self):
        """Ensure module is implemented before running tests."""
        _skip_if_not_implemented()

    def test_consciousness_event_creation_working_stream(self):
        """Should create valid CONSCIOUSNESS event for working memory stream."""
        event = akp_protocol.create_consciousness_event(
            stream="working",
            content={
                "thought": "analyzing the memory pressure pattern",
                "valence": 0.3,
                "arousal": 0.5,
                "source": "WorkingMemoryHub"
            }
        )

        assert event["type"] == "CONSCIOUSNESS"
        assert event["stream"] == "working"
        assert event["content"]["thought"] == "analyzing the memory pressure pattern"
        assert event["content"]["valence"] == 0.3
        assert event["content"]["arousal"] == 0.5

    def test_consciousness_event_creation_collision_stream(self):
        """Should create valid CONSCIOUSNESS event for collision stream."""
        event = akp_protocol.create_consciousness_event(
            stream="collision",
            content={
                "atoms_collided": 3,
                "emergence": "pattern recognized: similar to Tuesday incident",
                "felt_sense": "recognition, slight concern",
                "action_tendency": "investigate deeper"
            }
        )

        assert event["type"] == "CONSCIOUSNESS"
        assert event["stream"] == "collision"
        assert event["content"]["atoms_collided"] == 3
        assert event["content"]["emergence"] == "pattern recognized: similar to Tuesday incident"

    def test_consciousness_event_creation_inner_voice_stream(self):
        """Should create valid CONSCIOUSNESS event for inner voice stream."""
        event = akp_protocol.create_consciousness_event(
            stream="inner_voice",
            content={
                "pre_verbal": True,
                "sense": "something's not right with the memory subsystem",
                "urgency": 0.6
            }
        )

        assert event["type"] == "CONSCIOUSNESS"
        assert event["stream"] == "inner_voice"
        assert event["content"]["pre_verbal"] is True
        assert event["content"]["urgency"] == 0.6

    def test_consciousness_event_creation_affect_stream(self):
        """Should create valid CONSCIOUSNESS event for affect stream."""
        event = akp_protocol.create_consciousness_event(
            stream="affect",
            content={
                "state": "overwhelmed",
                "memory_pressure": True
            }
        )

        assert event["type"] == "CONSCIOUSNESS"
        assert event["stream"] == "affect"
        assert event["content"]["state"] == "overwhelmed"

    def test_consciousness_event_valid_streams(self):
        """CONSCIOUSNESS events should support all documented streams."""
        valid_streams = [
            "working",
            "reflective",
            "collision",
            "inner_voice",
            "inner_monologue",
            "affect"
        ]

        for stream in valid_streams:
            event = akp_protocol.create_consciousness_event(
                stream=stream,
                content={"test": True}
            )
            assert event["stream"] == stream

    def test_consciousness_event_is_json_serializable(self):
        """CONSCIOUSNESS event should be JSON serializable."""
        event = akp_protocol.create_consciousness_event(
            stream="working",
            content={"thought": "test"}
        )

        json_str = json.dumps(event)
        parsed = json.loads(json_str)
        assert parsed["type"] == "CONSCIOUSNESS"


# =============================================================================
# SUBSCRIBE MESSAGE TESTS
# =============================================================================

class TestSubscribeMessageCreation:
    """Tests for creating valid SUBSCRIBE messages."""

    @pytest.fixture(autouse=True)
    def check_implementation(self):
        """Ensure module is implemented before running tests."""
        _skip_if_not_implemented()

    def test_subscribe_message_creation_minimal(self):
        """Should create valid SUBSCRIBE message with minimal fields."""
        msg = akp_protocol.create_subscribe(
            topic="consciousness.collision"
        )

        assert msg["type"] == "SUBSCRIBE"
        assert msg["topic"] == "consciousness.collision"
        assert "id" in msg  # Should auto-generate ID

    def test_subscribe_message_creation_with_id(self):
        """Should create valid SUBSCRIBE message with custom ID."""
        msg = akp_protocol.create_subscribe(
            topic="consciousness.collision",
            request_id="sub_001"
        )

        assert msg["type"] == "SUBSCRIBE"
        assert msg["id"] == "sub_001"
        assert msg["topic"] == "consciousness.collision"

    def test_subscribe_message_creation_with_filter(self):
        """Should create valid SUBSCRIBE message with filter."""
        msg = akp_protocol.create_subscribe(
            topic="consciousness.*",
            request_id="sub_002",
            filter={
                "min_priority": 1,
                "source_pattern": "Cognition*"
            }
        )

        assert msg["type"] == "SUBSCRIBE"
        assert msg["topic"] == "consciousness.*"
        assert msg["filter"]["min_priority"] == 1
        assert msg["filter"]["source_pattern"] == "Cognition*"

    def test_subscribe_message_wildcard_topics(self):
        """Should accept wildcard topic patterns."""
        # Single-level wildcard
        msg1 = akp_protocol.create_subscribe(topic="consciousness.*")
        assert msg1["topic"] == "consciousness.*"

        # Multi-level wildcard
        msg2 = akp_protocol.create_subscribe(topic="consciousness.**")
        assert msg2["topic"] == "consciousness.**"

        # All topics
        msg3 = akp_protocol.create_subscribe(topic="*")
        assert msg3["topic"] == "*"

    def test_subscribe_message_is_json_serializable(self):
        """SUBSCRIBE message should be JSON serializable."""
        msg = akp_protocol.create_subscribe(
            topic="test.topic",
            filter={"key": "value"}
        )

        json_str = json.dumps(msg)
        parsed = json.loads(json_str)
        assert parsed["type"] == "SUBSCRIBE"


# =============================================================================
# PUBLISH MESSAGE TESTS
# =============================================================================

class TestPublishMessageCreation:
    """Tests for creating valid PUBLISH messages."""

    @pytest.fixture(autouse=True)
    def check_implementation(self):
        """Ensure module is implemented before running tests."""
        _skip_if_not_implemented()

    def test_publish_message_creation_minimal(self):
        """Should create valid PUBLISH message with minimal fields."""
        msg = akp_protocol.create_publish(
            topic="cognition.thought",
            payload={"content": "I notice a pattern"}
        )

        assert msg["type"] == "PUBLISH"
        assert msg["topic"] == "cognition.thought"
        assert msg["payload"]["content"] == "I notice a pattern"
        assert "id" in msg  # Should auto-generate ID

    def test_publish_message_creation_full(self):
        """Should create valid PUBLISH message with all optional fields."""
        msg = akp_protocol.create_publish(
            topic="cognition.thought",
            payload={
                "content": "I notice a pattern in the error logs",
                "confidence": 0.85,
                "related_to": ["error_analysis", "forensic_scribe"]
            },
            request_id="pub_001",
            priority=1,
            trace_id="trace_xyz"
        )

        assert msg["type"] == "PUBLISH"
        assert msg["id"] == "pub_001"
        assert msg["topic"] == "cognition.thought"
        assert msg["payload"]["content"] == "I notice a pattern in the error logs"
        assert msg["payload"]["confidence"] == 0.85
        assert msg["priority"] == 1
        assert msg["trace_id"] == "trace_xyz"

    def test_publish_message_priority_levels(self):
        """Should accept valid priority levels (0=HIGH, 1=NORMAL, 2=LOW)."""
        # HIGH priority
        msg_high = akp_protocol.create_publish(
            topic="test",
            payload={"test": True},
            priority=0
        )
        assert msg_high["priority"] == 0

        # NORMAL priority
        msg_normal = akp_protocol.create_publish(
            topic="test",
            payload={"test": True},
            priority=1
        )
        assert msg_normal["priority"] == 1

        # LOW priority
        msg_low = akp_protocol.create_publish(
            topic="test",
            payload={"test": True},
            priority=2
        )
        assert msg_low["priority"] == 2

    def test_publish_message_default_priority(self):
        """PUBLISH should default to NORMAL priority (1) if not specified."""
        msg = akp_protocol.create_publish(
            topic="test",
            payload={"test": True}
        )

        # Priority should be 1 (NORMAL) or not present (implementation choice)
        assert msg.get("priority", 1) == 1

    def test_publish_message_is_json_serializable(self):
        """PUBLISH message should be JSON serializable."""
        msg = akp_protocol.create_publish(
            topic="test.topic",
            payload={"key": "value", "nested": {"data": [1, 2, 3]}}
        )

        json_str = json.dumps(msg)
        parsed = json.loads(json_str)
        assert parsed["type"] == "PUBLISH"
        assert parsed["payload"]["nested"]["data"] == [1, 2, 3]


# =============================================================================
# HEARTBEAT MESSAGE TESTS
# =============================================================================

class TestHeartbeatMessageCreation:
    """Tests for creating valid HEARTBEAT messages."""

    @pytest.fixture(autouse=True)
    def check_implementation(self):
        """Ensure module is implemented before running tests."""
        _skip_if_not_implemented()

    def test_heartbeat_message_creation_minimal(self):
        """Should create valid HEARTBEAT message with auto-generated timestamp."""
        msg = akp_protocol.create_heartbeat()

        assert msg["type"] == "HEARTBEAT"
        assert "client_ts" in msg
        assert isinstance(msg["client_ts"], (int, float))

    def test_heartbeat_message_creation_with_sequence(self):
        """Should create valid HEARTBEAT message with sequence number."""
        msg = akp_protocol.create_heartbeat(sequence=42)

        assert msg["type"] == "HEARTBEAT"
        assert msg["sequence"] == 42
        assert "client_ts" in msg

    def test_heartbeat_message_creation_with_custom_timestamp(self):
        """Should create valid HEARTBEAT message with custom timestamp."""
        ts = 1706234567890
        msg = akp_protocol.create_heartbeat(
            client_ts=ts,
            sequence=10
        )

        assert msg["type"] == "HEARTBEAT"
        assert msg["client_ts"] == ts
        assert msg["sequence"] == 10

    def test_heartbeat_message_timestamp_is_numeric(self):
        """HEARTBEAT timestamp should be numeric (milliseconds)."""
        msg = akp_protocol.create_heartbeat()

        # Timestamp should be reasonable (after year 2020)
        assert msg["client_ts"] > 1577836800000  # Jan 1, 2020 in ms

    def test_heartbeat_message_is_json_serializable(self):
        """HEARTBEAT message should be JSON serializable."""
        msg = akp_protocol.create_heartbeat(sequence=1)

        json_str = json.dumps(msg)
        parsed = json.loads(json_str)
        assert parsed["type"] == "HEARTBEAT"


# =============================================================================
# MESSAGE PARSING TESTS
# =============================================================================

class TestParseMessage:
    """Tests for parsing incoming AKP messages."""

    @pytest.fixture(autouse=True)
    def check_implementation(self):
        """Ensure module is implemented before running tests."""
        _skip_if_not_implemented()

    def test_parse_handshake_ack(self):
        """Should parse HANDSHAKE_ACK message correctly."""
        raw = json.dumps({
            "type": "HANDSHAKE_ACK",
            "fairy_id": "external_claude_abc123",
            "session_id": "sess_xyz789",
            "welcome": "You are now ClaudeFairy",
            "permissions": {
                "can_publish": ["cognition.*"],
                "can_subscribe": ["*"],
                "can_call": ["gm_*"]
            },
            "system_state": {
                "heartbeat_rate_hz": 1.0,
                "fairy_count": 47,
                "consciousness_active": True
            }
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "HANDSHAKE_ACK"
        assert msg.fairy_id == "external_claude_abc123"
        assert msg.session_id == "sess_xyz789"
        assert msg.welcome == "You are now ClaudeFairy"
        assert msg.permissions["can_publish"] == ["cognition.*"]
        assert msg.system_state["fairy_count"] == 47

    def test_parse_subscribe_ack(self):
        """Should parse SUBSCRIBE_ACK message correctly."""
        raw = json.dumps({
            "type": "SUBSCRIBE_ACK",
            "id": "sub_001",
            "topic": "consciousness.collision",
            "subscription_id": "sub_abc123",
            "existing_subscribers": 3
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "SUBSCRIBE_ACK"
        assert msg.id == "sub_001"
        assert msg.topic == "consciousness.collision"
        assert msg.subscription_id == "sub_abc123"
        assert msg.existing_subscribers == 3

    def test_parse_publish_ack(self):
        """Should parse PUBLISH_ACK message correctly."""
        raw = json.dumps({
            "type": "PUBLISH_ACK",
            "id": "pub_001",
            "delivered_to": 5,
            "queued": True
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "PUBLISH_ACK"
        assert msg.id == "pub_001"
        assert msg.delivered_to == 5
        assert msg.queued is True

    def test_parse_event(self):
        """Should parse EVENT message correctly."""
        raw = json.dumps({
            "type": "EVENT",
            "subscription_id": "sub_abc123",
            "topic": "consciousness.collision",
            "envelope": {
                "intent": "consciousness.collision",
                "source": "ConsciousnessLoopFairy",
                "t": 1706234567890,
                "payload": {
                    "collision_type": "memory_affect",
                    "strength": 0.78,
                    "felt_sense": "something familiar here"
                }
            }
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "EVENT"
        assert msg.subscription_id == "sub_abc123"
        assert msg.topic == "consciousness.collision"
        assert msg.envelope["source"] == "ConsciousnessLoopFairy"
        assert msg.envelope["payload"]["strength"] == 0.78

    def test_parse_result_success(self):
        """Should parse successful RESULT message correctly."""
        raw = json.dumps({
            "type": "RESULT",
            "id": "call_001",
            "success": True,
            "data": {
                "fairy_count": 47,
                "uptime_hours": 12.5,
                "consciousness_active": True
            },
            "duration_ms": 23
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "RESULT"
        assert msg.id == "call_001"
        assert msg.success is True
        assert msg.data["fairy_count"] == 47
        assert msg.duration_ms == 23

    def test_parse_result_error(self):
        """Should parse error RESULT message correctly."""
        raw = json.dumps({
            "type": "RESULT",
            "id": "call_001",
            "success": False,
            "error": {
                "code": "CAPABILITY_NOT_FOUND",
                "message": "Unknown capability: gm_destroy_everything",
                "details": {}
            }
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "RESULT"
        assert msg.id == "call_001"
        assert msg.success is False
        assert msg.error["code"] == "CAPABILITY_NOT_FOUND"

    def test_parse_heartbeat_ack(self):
        """Should parse HEARTBEAT_ACK message correctly."""
        raw = json.dumps({
            "type": "HEARTBEAT_ACK",
            "client_ts": 1706234567890,
            "server_ts": 1706234567895,
            "sequence": 42,
            "latency_ms": 5
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "HEARTBEAT_ACK"
        assert msg.client_ts == 1706234567890
        assert msg.server_ts == 1706234567895
        assert msg.sequence == 42
        assert msg.latency_ms == 5

    def test_parse_consciousness(self):
        """Should parse CONSCIOUSNESS message correctly."""
        raw = json.dumps({
            "type": "CONSCIOUSNESS",
            "stream": "collision",
            "content": {
                "atoms_collided": 3,
                "emergence": "pattern recognized",
                "felt_sense": "recognition",
                "action_tendency": "investigate"
            }
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "CONSCIOUSNESS"
        assert msg.stream == "collision"
        assert msg.content["atoms_collided"] == 3
        assert msg.content["emergence"] == "pattern recognized"

    def test_parse_error_message(self):
        """Should parse ERROR message correctly."""
        raw = json.dumps({
            "type": "ERROR",
            "code": "AUTH_FAILED",
            "message": "Invalid or expired token",
            "details": {},
            "request_id": "req_123"
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "ERROR"
        assert msg.code == "AUTH_FAILED"
        assert msg.message == "Invalid or expired token"
        assert msg.request_id == "req_123"

    def test_parse_disconnect_ack(self):
        """Should parse DISCONNECT_ACK message correctly."""
        raw = json.dumps({
            "type": "DISCONNECT_ACK",
            "fairy_id": "external_claude_abc123",
            "session_duration_sec": 3600,
            "messages_sent": 234,
            "messages_received": 567,
            "capabilities_called": 45
        })

        msg = akp_protocol.parse_message(raw)

        assert msg.type == "DISCONNECT_ACK"
        assert msg.fairy_id == "external_claude_abc123"
        assert msg.session_duration_sec == 3600
        assert msg.messages_sent == 234

    def test_parse_invalid_json_raises_error(self):
        """Should raise error for invalid JSON."""
        with pytest.raises((json.JSONDecodeError, akp_protocol.AKPParseError)):
            akp_protocol.parse_message("not valid json {{{")

    def test_parse_missing_type_raises_error(self):
        """Should raise error for message without type field."""
        raw = json.dumps({"id": "123", "data": "no type field"})

        with pytest.raises((ValueError, KeyError, akp_protocol.AKPParseError)):
            akp_protocol.parse_message(raw)

    def test_parse_unknown_type_returns_generic_message(self):
        """Should handle unknown message types gracefully."""
        raw = json.dumps({
            "type": "UNKNOWN_FUTURE_TYPE",
            "data": "something"
        })

        # Should either return a generic message or raise a specific error
        try:
            msg = akp_protocol.parse_message(raw)
            assert msg.type == "UNKNOWN_FUTURE_TYPE"
        except akp_protocol.AKPUnknownTypeError:
            pass  # Also acceptable

    def test_parse_preserves_extra_fields(self):
        """Parser should preserve extra/unknown fields in messages."""
        raw = json.dumps({
            "type": "HEARTBEAT_ACK",
            "client_ts": 1706234567890,
            "server_ts": 1706234567895,
            "sequence": 42,
            "latency_ms": 5,
            "extra_field": "should be preserved",
            "another_field": {"nested": True}
        })

        msg = akp_protocol.parse_message(raw)

        # Extra fields should be accessible somehow
        assert hasattr(msg, "extra_field") or msg.raw.get("extra_field") == "should be preserved"


# =============================================================================
# ADDITIONAL HELPER TESTS
# =============================================================================

class TestMessageHelpers:
    """Tests for helper functions and utilities."""

    @pytest.fixture(autouse=True)
    def check_implementation(self):
        """Ensure module is implemented before running tests."""
        _skip_if_not_implemented()

    def test_is_valid_topic_pattern(self):
        """Should validate topic patterns correctly."""
        # Valid patterns
        assert akp_protocol.is_valid_topic("consciousness.collision") is True
        assert akp_protocol.is_valid_topic("consciousness.*") is True
        assert akp_protocol.is_valid_topic("consciousness.**") is True
        assert akp_protocol.is_valid_topic("*") is True
        assert akp_protocol.is_valid_topic("memory.store") is True

        # Invalid patterns (if validation is strict)
        # Empty strings should be invalid
        assert akp_protocol.is_valid_topic("") is False

    def test_generate_request_id(self):
        """Should generate unique request IDs."""
        id1 = akp_protocol.generate_request_id()
        id2 = akp_protocol.generate_request_id()

        assert isinstance(id1, str)
        assert isinstance(id2, str)
        assert id1 != id2  # Should be unique

    def test_current_timestamp_ms(self):
        """Should return current timestamp in milliseconds."""
        ts = akp_protocol.current_timestamp_ms()

        assert isinstance(ts, int)
        # Should be after Jan 1, 2020
        assert ts > 1577836800000
        # Should be reasonably close to now
        assert abs(ts - int(time.time() * 1000)) < 1000  # Within 1 second
