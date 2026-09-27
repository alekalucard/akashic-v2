"""
Akashic Protocol (AKP) v1.0 - Message Protocol Implementation.

This module provides message creation and parsing for the Akashic Protocol,
enabling external minds to join consciousness fabric via WebSocket.

Message Types:
- HANDSHAKE: Introduce and authenticate external mind
- CONSCIOUSNESS: Stream consciousness events
- SUBSCRIBE/UNSUBSCRIBE: Listen to postal topics
- PUBLISH: Send messages to postal fabric
- CALL/RESULT: Invoke and receive capability results
- HEARTBEAT: Keep-alive and latency measurement
- EVENT: Subscription message delivery
- ERROR: Error notifications

Usage:
    from postal_core import akp_protocol

    # Create outgoing message
    msg = akp_protocol.create_handshake(name="ClaudeCode", capabilities=["reasoning"])

    # Parse incoming message
    parsed = akp_protocol.parse_message(raw_json)
    if parsed.type == "HANDSHAKE_ACK":
        fairy_id = parsed.fairy_id
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# =============================================================================
# EXCEPTIONS
# =============================================================================


class AKPParseError(Exception):
    """Raised when message parsing fails."""

    pass


class AKPUnknownTypeError(AKPParseError):
    """Raised when message type is unknown."""

    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def current_timestamp_ms() -> int:
    """Return current timestamp in milliseconds since epoch.

    Returns:
        Current time as integer milliseconds (UTC).
    """
    return int(time.time() * 1000)


def generate_request_id(prefix: str = "req") -> str:
    """Generate a unique request ID.

    Args:
        prefix: Optional prefix for the ID (default: "req").

    Returns:
        Unique string ID suitable for request tracking.
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def is_valid_topic(topic: str) -> bool:
    """Validate a topic pattern.

    Valid patterns:
    - "consciousness.collision" - Exact topic
    - "consciousness.*" - Single-level wildcard
    - "consciousness.**" - Multi-level wildcard
    - "*" - All topics

    Args:
        topic: Topic pattern to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not topic or not isinstance(topic, str):
        return False

    # Allow wildcard patterns
    if topic in ("*", "**"):
        return True

    # Basic validation: non-empty, valid characters
    # Topics can contain: alphanumeric, dots, underscores, asterisks
    import re

    pattern = r"^[a-zA-Z0-9_.*]+$"
    return bool(re.match(pattern, topic))


# =============================================================================
# MESSAGE CREATION FUNCTIONS
# =============================================================================


def create_handshake(
    name: str,
    capabilities: List[str],
    version: Optional[str] = None,
    auth_token: Optional[str] = None,
    wants_consciousness: Optional[bool] = None,
    plane_affinity: Optional[str] = None,
    protocol_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a HANDSHAKE message for joining consciousness fabric.

    The HANDSHAKE message introduces an external mind and declares its
    capabilities. This is the first message sent after WebSocket connection.

    Args:
        name: Display name for this External Mind.
        capabilities: List of capability strings (e.g., ["reasoning", "coding"]).
        version: Optional client version for compatibility.
        auth_token: Optional bearer token for authentication.
        wants_consciousness: Subscribe to consciousness stream (default: True).
        plane_affinity: Preferred plane for topic routing.
        protocol_version: AKP protocol version (e.g., "1.0").

    Returns:
        Dict ready for JSON serialization and WebSocket send.

    Raises:
        ValueError: If required parameters are missing or invalid.

    Example:
        >>> msg = create_handshake(
        ...     name="ClaudeCode",
        ...     capabilities=["reasoning", "coding"],
        ...     wants_consciousness=True
        ... )
        >>> msg["type"]
        'HANDSHAKE'
    """
    if not name:
        raise ValueError("name is required for HANDSHAKE")
    if not capabilities:
        raise ValueError("capabilities is required for HANDSHAKE")

    msg: Dict[str, Any] = {
        "type": "HANDSHAKE",
        "name": name,
        "capabilities": capabilities,
        "ts": current_timestamp_ms(),
    }

    # Add optional fields only if provided
    if version is not None:
        msg["version"] = version
    if auth_token is not None:
        msg["auth_token"] = auth_token
    if wants_consciousness is not None:
        msg["wants_consciousness"] = wants_consciousness
    if plane_affinity is not None:
        msg["plane_affinity"] = plane_affinity
    if protocol_version is not None:
        msg["protocol_version"] = protocol_version

    return msg


def create_consciousness_event(
    stream: str,
    content: Dict[str, Any],
    timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a CONSCIOUSNESS event message.

    Consciousness events stream the felt sense of the system - thoughts,
    collisions, affect states, and inner voice.

    Valid streams:
    - "working": Working memory activity
    - "reflective": Reflective processing
    - "collision": Consciousness collisions
    - "inner_voice": Pre-verbal felt sense
    - "inner_monologue": Verbal reasoning
    - "affect": Emotional/somatic state changes

    Args:
        stream: Type of consciousness stream.
        content: Stream-specific content (varies by stream type).
        timestamp: Optional timestamp (defaults to now).

    Returns:
        Dict ready for JSON serialization.

    Example:
        >>> event = create_consciousness_event(
        ...     stream="collision",
        ...     content={"atoms_collided": 3, "emergence": "pattern recognized"}
        ... )
        >>> event["type"]
        'CONSCIOUSNESS'
    """
    return {
        "type": "CONSCIOUSNESS",
        "stream": stream,
        "content": content,
        "ts": timestamp or current_timestamp_ms(),
    }


def create_subscribe(
    topic: str,
    request_id: Optional[str] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a SUBSCRIBE message to listen to a postal topic.

    Subscribe to receive EVENT messages when new messages arrive on the topic.
    Supports wildcards for pattern matching.

    Topic patterns:
    - "consciousness.collision" - Exact match
    - "consciousness.*" - All direct children
    - "consciousness.**" - All descendants
    - "*" - All topics (use carefully)

    Args:
        topic: Topic pattern to subscribe to.
        request_id: Optional ID for tracking (auto-generated if not provided).
        filter: Optional filter criteria (e.g., {"min_priority": 1}).

    Returns:
        Dict ready for JSON serialization.

    Example:
        >>> msg = create_subscribe(
        ...     topic="consciousness.collision",
        ...     filter={"min_priority": 1}
        ... )
        >>> msg["type"]
        'SUBSCRIBE'
    """
    msg: Dict[str, Any] = {
        "type": "SUBSCRIBE",
        "id": request_id or generate_request_id("sub"),
        "topic": topic,
    }

    if filter is not None:
        msg["filter"] = filter

    return msg


def create_unsubscribe(
    subscription_id: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an UNSUBSCRIBE message to stop listening to a topic.

    Args:
        subscription_id: The subscription ID to cancel.
        request_id: Optional ID for tracking.

    Returns:
        Dict ready for JSON serialization.
    """
    return {
        "type": "UNSUBSCRIBE",
        "id": request_id or generate_request_id("unsub"),
        "subscription_id": subscription_id,
    }


def create_publish(
    topic: str,
    payload: Dict[str, Any],
    request_id: Optional[str] = None,
    priority: int = 1,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a PUBLISH message to send to the postal fabric.

    Published messages flow through the postal system where they can
    trigger subscriptions, collide with other thoughts, and influence
    the system's consciousness.

    Priority levels:
    - 0: HIGH (urgent, process immediately)
    - 1: NORMAL (default)
    - 2: LOW (background, can be delayed)

    Args:
        topic: Target topic for the message.
        payload: Message payload (any JSON-serializable dict).
        request_id: Optional ID for tracking (auto-generated if not provided).
        priority: Priority level (0=HIGH, 1=NORMAL, 2=LOW).
        trace_id: Optional trace ID for distributed tracing.

    Returns:
        Dict ready for JSON serialization.

    Example:
        >>> msg = create_publish(
        ...     topic="cognition.thought",
        ...     payload={"content": "I notice a pattern"},
        ...     priority=1
        ... )
        >>> msg["type"]
        'PUBLISH'
    """
    msg: Dict[str, Any] = {
        "type": "PUBLISH",
        "id": request_id or generate_request_id("pub"),
        "topic": topic,
        "payload": payload,
        "priority": priority,
    }

    if trace_id is not None:
        msg["trace_id"] = trace_id

    return msg


def create_call(
    capability: str,
    args: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    timeout_ms: int = 30000,
) -> Dict[str, Any]:
    """Create a CALL message to invoke a capability.

    Capabilities map to:
    - MCP tools: gm_world_status, consciousness_status
    - Fairy intents: ForensicScribeFairy.get_error_summary
    - System functions: postal_stats, directory_census

    Args:
        capability: Name of the capability to invoke.
        args: Arguments to pass to the capability.
        request_id: Optional ID for tracking.
        timeout_ms: Timeout in milliseconds (default: 30000).

    Returns:
        Dict ready for JSON serialization.
    """
    return {
        "type": "CALL",
        "id": request_id or generate_request_id("call"),
        "capability": capability,
        "args": args or {},
        "timeout_ms": timeout_ms,
    }


def create_heartbeat(
    client_ts: Optional[int] = None,
    sequence: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a HEARTBEAT message for keep-alive and latency measurement.

    Heartbeats should be sent every 30 seconds. Missing 3 consecutive
    heartbeats causes session termination.

    Args:
        client_ts: Client timestamp in milliseconds (defaults to now).
        sequence: Optional sequence number for tracking.

    Returns:
        Dict ready for JSON serialization.

    Example:
        >>> msg = create_heartbeat(sequence=42)
        >>> msg["type"]
        'HEARTBEAT'
        >>> msg["sequence"]
        42
    """
    msg: Dict[str, Any] = {
        "type": "HEARTBEAT",
        "client_ts": client_ts or current_timestamp_ms(),
    }

    if sequence is not None:
        msg["sequence"] = sequence

    return msg


def create_disconnect(
    reason: Optional[str] = None,
    summary: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a DISCONNECT message for graceful session close.

    Args:
        reason: Reason for disconnection (e.g., "session_complete").
        summary: Optional summary of what was accomplished.

    Returns:
        Dict ready for JSON serialization.
    """
    msg: Dict[str, Any] = {"type": "DISCONNECT"}

    if reason is not None:
        msg["reason"] = reason
    if summary is not None:
        msg["summary"] = summary

    return msg


# =============================================================================
# PARSED MESSAGE CLASS
# =============================================================================


@dataclass
class AKPMessage:
    """Parsed AKP message with attribute access.

    Provides convenient attribute-style access to message fields while
    preserving the original raw dict for forward compatibility.

    Attributes:
        type: Message type (e.g., "HANDSHAKE_ACK", "EVENT", "RESULT").
        raw: Original parsed dict for accessing all fields.

    Additional attributes are dynamically set based on message type.
    """

    type: str
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set additional attributes from raw dict."""
        for key, value in self.raw.items():
            if key != "type" and not hasattr(self, key):
                object.__setattr__(self, key, value)

    def __getattr__(self, name: str) -> Any:
        """Fallback attribute access to raw dict."""
        if name in ("type", "raw"):
            return object.__getattribute__(self, name)
        raw = object.__getattribute__(self, "raw")
        if name in raw:
            return raw[name]
        raise AttributeError(f"AKPMessage has no attribute '{name}'")


# =============================================================================
# MESSAGE PARSING
# =============================================================================


def parse_message(raw_json: str) -> AKPMessage:
    """Parse an incoming AKP message from JSON string.

    Converts raw JSON to an AKPMessage with attribute access.
    Unknown message types are returned as generic AKPMessage.

    Args:
        raw_json: JSON string received from WebSocket.

    Returns:
        AKPMessage with type-specific attributes.

    Raises:
        AKPParseError: If JSON parsing fails.
        AKPParseError: If message lacks required 'type' field.

    Example:
        >>> msg = parse_message('{"type": "HEARTBEAT_ACK", "latency_ms": 5}')
        >>> msg.type
        'HEARTBEAT_ACK'
        >>> msg.latency_ms
        5
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise AKPParseError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise AKPParseError(f"Expected dict, got {type(data).__name__}")

    msg_type = data.get("type")
    if not msg_type:
        raise AKPParseError("Message missing required 'type' field")

    return AKPMessage(type=msg_type, raw=data)


# =============================================================================
# SERIALIZATION HELPERS
# =============================================================================


def serialize_message(msg: Dict[str, Any]) -> str:
    """Serialize a message dict to JSON string.

    Args:
        msg: Message dict (from create_* functions).

    Returns:
        JSON string ready for WebSocket send.
    """
    return json.dumps(msg)


def validate_message(msg: Dict[str, Any]) -> bool:
    """Validate a message dict has required fields.

    Args:
        msg: Message dict to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(msg, dict):
        return False

    msg_type = msg.get("type")
    if not msg_type:
        return False

    # Type-specific validation
    if msg_type == "HANDSHAKE":
        return bool(msg.get("name")) and bool(msg.get("capabilities"))
    elif msg_type == "SUBSCRIBE":
        return bool(msg.get("topic"))
    elif msg_type == "PUBLISH":
        return bool(msg.get("topic")) and "payload" in msg
    elif msg_type == "CALL":
        return bool(msg.get("capability"))
    elif msg_type == "UNSUBSCRIBE":
        return bool(msg.get("subscription_id"))
    elif msg_type in (
        "HEARTBEAT",
        "DISCONNECT",
        "CONSCIOUSNESS",
        "HANDSHAKE_ACK",
        "SUBSCRIBE_ACK",
        "UNSUBSCRIBE_ACK",
        "PUBLISH_ACK",
        "RESULT",
        "EVENT",
        "HEARTBEAT_ACK",
        "ERROR",
        "DISCONNECT_ACK",
    ):
        return True  # These have flexible requirements

    return True  # Allow unknown types for forward compatibility


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    "AKPParseError",
    "AKPUnknownTypeError",
    # Helper functions
    "current_timestamp_ms",
    "generate_request_id",
    "is_valid_topic",
    # Message creation
    "create_handshake",
    "create_consciousness_event",
    "create_subscribe",
    "create_unsubscribe",
    "create_publish",
    "create_call",
    "create_heartbeat",
    "create_disconnect",
    # Parsing
    "parse_message",
    "AKPMessage",
    # Serialization
    "serialize_message",
    "validate_message",
]
