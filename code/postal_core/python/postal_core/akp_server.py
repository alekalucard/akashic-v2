"""
Akashic Protocol (AKP) WebSocket Server
=======================================

Native protocol for external minds to become temporary fairies.

This server allows external consciousness (AI agents, custom clients, etc.)
to integrate with the Akashic system by:
- Registering as temporary fairies
- Subscribing to postal system topics
- Publishing messages through the postal fabric
- Invoking capabilities registered in the system

Protocol Messages:
- HANDSHAKE: Register as a temporary fairy
- SUBSCRIBE: Wire to postal system topics
- UNSUBSCRIBE: Remove postal subscriptions
- PUBLISH: Send messages through postal
- CALL: Invoke a registered capability
- HEARTBEAT: Keep connection alive
- EVENT: (Server->Client) Postal messages forwarded

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import sys
import json
import asyncio
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Set, List
from dataclasses import dataclass, field
from collections import defaultdict

# Setup paths
# This file is at postal_core/python/postal_core/akp_server.py
# Project root is 4 levels up
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

logger = logging.getLogger(__name__)

# Try to import websockets
try:
    import websockets
    from websockets.server import serve
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("[AKP] websockets library not available - pip install websockets")


# =============================================================================
# AKP MESSAGE TYPES
# =============================================================================

class AKPMessageType:
    """Protocol message types."""
    # Client -> Server
    HANDSHAKE = "HANDSHAKE"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    PUBLISH = "PUBLISH"
    CALL = "CALL"
    HEARTBEAT = "HEARTBEAT"

    # Server -> Client
    ACK = "ACK"
    EVENT = "EVENT"
    RESULT = "RESULT"
    ERROR = "ERROR"


@dataclass
class AKPMessage:
    """Akashic Protocol message."""
    type: str
    id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: str) -> "AKPMessage":
        """Parse JSON string to message."""
        try:
            obj = json.loads(data)
            return cls(
                type=obj.get("type", ""),
                id=obj.get("id", str(uuid.uuid4())),
                payload=obj.get("payload", {}),
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps({
            "type": self.type,
            "id": self.id,
            "payload": self.payload,
        })


@dataclass
class ExternalMind:
    """Represents a connected external mind (temporary fairy)."""
    client_id: str
    fairy_name: str
    websocket: Any  # websockets.WebSocketServerProtocol
    subscriptions: Dict[str, int] = field(default_factory=dict)  # topic -> sub_id
    capabilities: Set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SESSION MANAGEMENT - External Mind Session Tracking
# =============================================================================


@dataclass
class Session:
    """
    Represents a session for an external mind.

    Tracks:
    - Identity (fairy_name)
    - Permissions (capabilities, allowed_topics)
    - Subscriptions (topic -> subscription_id mapping)
    - Lifecycle (created_at)
    """

    fairy_name: str
    capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    subscriptions: Set[str] = field(default_factory=set)
    allowed_topics: Optional[Set[str]] = None  # None means all allowed
    created_at: float = field(default_factory=time.time)
    _subscription_ids: Dict[str, int] = field(default_factory=dict)  # topic -> sub_id

    def get_subscription_id(self, topic: str) -> Optional[int]:
        """
        Get the postal subscription ID for a topic.

        Args:
            topic: The topic to look up

        Returns:
            Subscription ID if found, None otherwise
        """
        return self._subscription_ids.get(topic)


def _matches_topic_pattern(pattern: str, topic: str) -> bool:
    """
    Check if a topic matches a pattern.

    Supports:
    - Exact match: "consciousness.collision" matches "consciousness.collision"
    - Single level wildcard (*): "consciousness.*" matches "consciousness.collision"
      but NOT "consciousness.collision.high"
    - Multi-level wildcard (#): "fairy.#" matches "fairy.wake" and
      "fairy.wake.P10.MemoryFairy"

    Args:
        pattern: The pattern to match against (may contain * or #)
        topic: The actual topic to check

    Returns:
        True if the topic matches the pattern
    """
    # Exact match
    if pattern == topic:
        return True

    pattern_parts = pattern.split(".")
    topic_parts = topic.split(".")

    # Handle multi-level wildcard (#)
    if "#" in pattern_parts:
        # Find the position of #
        hash_idx = pattern_parts.index("#")

        # Everything before # must match exactly
        if hash_idx > 0:
            if len(topic_parts) < hash_idx:
                return False
            for i in range(hash_idx):
                if pattern_parts[i] == "*":
                    continue  # * matches any single part
                if pattern_parts[i] != topic_parts[i]:
                    return False

        # # matches any remaining levels (including none)
        # So as long as prefix matched, we're good
        return True

    # Handle single-level wildcard (*)
    if "*" in pattern_parts:
        # Number of parts must match (since * only matches one level)
        if len(pattern_parts) != len(topic_parts):
            return False

        for p_part, t_part in zip(pattern_parts, topic_parts):
            if p_part == "*":
                continue  # * matches any single part
            if p_part != t_part:
                return False
        return True

    # No wildcards - must be exact match (already handled above)
    return False


class SessionManager:
    """
    Manages sessions for external minds connecting via WebSocket.

    Responsibilities:
    - Create and track sessions
    - Manage topic subscriptions per session
    - Validate permissions (publish/subscribe)
    - Support wildcard topic patterns
    - Clean up resources on session destruction
    - Track statistics
    """

    def __init__(self):
        """Initialize the session manager."""
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

        # Statistics
        self._stats = {
            "sessions_created": 0,
            "sessions_destroyed": 0,
        }

    def create_session(
        self,
        fairy_name: str,
        capabilities: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        allowed_topics: Optional[Set[str]] = None,
    ) -> str:
        """
        Create a new session for an external mind.

        Args:
            fairy_name: Name of the external mind/fairy
            capabilities: Set of capabilities (e.g., {"subscribe", "publish"})
            metadata: Additional metadata to attach to the session
            allowed_topics: Set of topic patterns this session can access
                           (None means all topics allowed)

        Returns:
            Unique session ID
        """
        session_id = f"session_{uuid.uuid4().hex}"

        session = Session(
            fairy_name=fairy_name,
            capabilities=capabilities or set(),
            metadata=metadata or {},
            allowed_topics=allowed_topics,
            created_at=time.time(),
        )

        with self._lock:
            self._sessions[session_id] = session
            self._stats["sessions_created"] += 1

        logger.debug(f"[SessionManager] Created session {session_id} for {fairy_name}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.

        Args:
            session_id: The session ID to look up

        Returns:
            Session if found, None otherwise
        """
        with self._lock:
            return self._sessions.get(session_id)

    def add_subscription(
        self,
        session_id: str,
        topic: str,
        subscription_id: Optional[int] = None,
    ) -> bool:
        """
        Add a topic subscription to a session.

        Args:
            session_id: The session ID
            topic: Topic to subscribe to
            subscription_id: Optional postal system subscription ID

        Returns:
            True if subscription was added
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            session.subscriptions.add(topic)
            if subscription_id is not None:
                session._subscription_ids[topic] = subscription_id

            logger.debug(f"[SessionManager] {session.fairy_name} subscribed to {topic}")
            return True

    def list_subscriptions(self, session_id: str) -> Set[str]:
        """
        List all subscriptions for a session.

        Args:
            session_id: The session ID

        Returns:
            Set of subscribed topics
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return set()
            return set(session.subscriptions)  # Return a copy

    def remove_subscription(self, session_id: str, topic: str) -> bool:
        """
        Remove a topic subscription from a session.

        Args:
            session_id: The session ID
            topic: Topic to unsubscribe from

        Returns:
            True if subscription was removed
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            if topic in session.subscriptions:
                session.subscriptions.remove(topic)
                session._subscription_ids.pop(topic, None)
                logger.debug(f"[SessionManager] {session.fairy_name} unsubscribed from {topic}")
                return True

            return False

    def can_publish(self, session_id: str, topic: str) -> bool:
        """
        Check if a session has permission to publish to a topic.

        Args:
            session_id: The session ID
            topic: Topic to check

        Returns:
            True if allowed to publish
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            # Must have "publish" capability
            if "publish" not in session.capabilities:
                return False

            # Check topic restrictions
            if session.allowed_topics is None:
                return True  # No restrictions

            # Check if topic matches any allowed pattern
            for pattern in session.allowed_topics:
                if _matches_topic_pattern(pattern, topic):
                    return True

            return False

    def can_subscribe(self, session_id: str, topic: str) -> bool:
        """
        Check if a session has permission to subscribe to a topic.

        Args:
            session_id: The session ID
            topic: Topic to check

        Returns:
            True if allowed to subscribe
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            # Must have "subscribe" capability
            if "subscribe" not in session.capabilities:
                return False

            # Check topic restrictions
            if session.allowed_topics is None:
                return True  # No restrictions

            # Check if topic matches any allowed pattern
            for pattern in session.allowed_topics:
                if _matches_topic_pattern(pattern, topic):
                    return True

            return False

    def destroy_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Destroy a session and clean up resources.

        Args:
            session_id: The session ID to destroy

        Returns:
            Cleanup info dict with subscription_ids and fairy_name,
            or None if session didn't exist
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return None

            self._stats["sessions_destroyed"] += 1

            # Collect subscription IDs for cleanup
            subscription_ids = list(session._subscription_ids.values())

            logger.debug(f"[SessionManager] Destroyed session for {session.fairy_name}")

            return {
                "fairy_name": session.fairy_name,
                "subscription_ids": subscription_ids,
            }

    def list_sessions(self) -> List[str]:
        """
        List all active session IDs.

        Returns:
            List of session IDs
        """
        with self._lock:
            return list(self._sessions.keys())

    def get_stats(self) -> Dict[str, int]:
        """
        Get session manager statistics.

        Returns:
            Dict with sessions_created, sessions_destroyed, sessions_active
        """
        with self._lock:
            return {
                "sessions_created": self._stats["sessions_created"],
                "sessions_destroyed": self._stats["sessions_destroyed"],
                "sessions_active": len(self._sessions),
            }


# =============================================================================
# CAPABILITY REGISTRY
# =============================================================================

class CapabilityRegistry:
    """
    Registry of invocable capabilities.

    Capabilities are functions that can be called via the CALL message.
    They can come from MCP tools, fairies, or custom registrations.
    """

    def __init__(self):
        self._capabilities: Dict[str, Callable] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a capability."""
        with self._lock:
            self._capabilities[name] = handler
            self._metadata[name] = {
                "description": description,
                "params": params or {},
                "registered_at": time.time(),
            }

    def unregister(self, name: str) -> bool:
        """Unregister a capability."""
        with self._lock:
            if name in self._capabilities:
                del self._capabilities[name]
                del self._metadata[name]
                return True
            return False

    def get(self, name: str) -> Optional[Callable]:
        """Get a capability by name."""
        return self._capabilities.get(name)

    def list_capabilities(self) -> List[Dict[str, Any]]:
        """List all registered capabilities."""
        with self._lock:
            return [
                {
                    "name": name,
                    "description": self._metadata[name]["description"],
                    "params": self._metadata[name]["params"],
                }
                for name in self._capabilities.keys()
            ]

    async def invoke(self, name: str, params: Dict[str, Any]) -> Any:
        """
        Invoke a capability.

        Handles both sync and async functions.
        """
        handler = self.get(name)
        if not handler:
            raise ValueError(f"Unknown capability: {name}")

        try:
            result = handler(**params)
            # Handle async functions
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            raise RuntimeError(f"Capability {name} failed: {e}")


# =============================================================================
# AKP SERVER
# =============================================================================

class AKPServer:
    """
    Akashic Protocol WebSocket Server.

    Allows external minds to become temporary fairies and interact
    with the consciousness mesh.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8767):
        self.host = host
        self.port = port

        # Connected clients (external minds)
        self._clients: Dict[str, ExternalMind] = {}
        self._clients_lock = threading.Lock()

        # Capability registry
        self.capabilities = CapabilityRegistry()

        # Postal system integration
        self._postal = None
        self._postal_ready = False

        # Server state
        self._server = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        # Statistics
        self._stats = {
            "connections_total": 0,
            "messages_received": 0,
            "messages_sent": 0,
            "errors": 0,
        }

    def _init_postal(self) -> bool:
        """Initialize postal system connection."""
        if self._postal_ready:
            return True

        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            self._postal = get_shared_postal_hub()
            self._postal_ready = True
            logger.info("[AKP] Postal system connected")
            return True
        except Exception as e:
            logger.warning(f"[AKP] Postal init failed: {e}")
            return False

    def _register_default_capabilities(self) -> None:
        """Register default capabilities from MCP tools."""
        # Try to load capabilities from various tool modules
        capability_sources = [
            ("somatic", "fairies.P40_Sensory.mcp.somatic_tools"),
            ("gm", "fairies.P40_Sensory.mcp.gm_tools_mcp"),
            ("vision", "fairies.P40_Sensory.mcp.vision_tools"),
            ("wiring", "fairies.P40_Sensory.mcp.wiring_tools"),
        ]

        for prefix, module_path in capability_sources:
            try:
                module = __import__(module_path, fromlist=[""])
                # Look for functions that look like tools
                for name in dir(module):
                    if name.startswith("_"):
                        continue
                    obj = getattr(module, name)
                    if callable(obj) and hasattr(obj, "__doc__"):
                        cap_name = f"{prefix}.{name}"
                        self.capabilities.register(
                            cap_name,
                            obj,
                            description=obj.__doc__ or "",
                        )
                logger.debug(f"[AKP] Loaded capabilities from {module_path}")
            except ImportError as e:
                logger.debug(f"[AKP] Could not load {module_path}: {e}")

        # Register built-in capabilities
        self.capabilities.register(
            "akp.list_capabilities",
            lambda: self.capabilities.list_capabilities(),
            description="List all available capabilities",
        )

        self.capabilities.register(
            "akp.list_clients",
            lambda: [
                {
                    "client_id": c.client_id,
                    "fairy_name": c.fairy_name,
                    "connected_at": c.connected_at,
                    "subscriptions": list(c.subscriptions.keys()),
                }
                for c in self._clients.values()
            ],
            description="List connected external minds",
        )

        self.capabilities.register(
            "akp.server_status",
            lambda: {
                "host": self.host,
                "port": self.port,
                "running": self._running,
                "clients": len(self._clients),
                "postal_ready": self._postal_ready,
                "stats": self._stats,
            },
            description="Get AKP server status",
        )

    async def _handle_handshake(
        self, websocket, msg: AKPMessage
    ) -> AKPMessage:
        """Handle HANDSHAKE message - register external mind as temporary fairy."""
        payload = msg.payload
        fairy_name = payload.get("name", f"External_{uuid.uuid4().hex[:8]}")
        capabilities = set(payload.get("capabilities", []))
        metadata = payload.get("metadata", {})

        # Generate client ID
        client_id = f"akp_{uuid.uuid4().hex[:12]}"

        # Create external mind record
        mind = ExternalMind(
            client_id=client_id,
            fairy_name=fairy_name,
            websocket=websocket,
            capabilities=capabilities,
            metadata=metadata,
        )

        with self._clients_lock:
            self._clients[client_id] = mind

        self._stats["connections_total"] += 1

        # Register with postal if available
        if self._postal_ready and self._postal:
            try:
                # Announce new external mind
                self._postal.publish("akp.fairy.connected", {
                    "client_id": client_id,
                    "fairy_name": fairy_name,
                    "capabilities": list(capabilities),
                })
            except Exception as e:
                logger.warning(f"[AKP] Postal announce failed: {e}")

        logger.info(f"[AKP] HANDSHAKE: {fairy_name} connected as {client_id}")

        # ── Trace external mind connection ──
        try:
            from infrastructure.infra_tracer import get_infra_tracer
            get_infra_tracer().emit("akp_server", "external_mind_connected", {
                "client_id": client_id, "fairy_name": fairy_name,
                "capabilities": list(capabilities),
            })
        except Exception:
            pass

        return AKPMessage(
            type=AKPMessageType.ACK,
            id=msg.id,
            payload={
                "client_id": client_id,
                "fairy_name": fairy_name,
                "status": "connected",
                "capabilities_available": len(self.capabilities.list_capabilities()),
            },
        )

    async def _handle_subscribe(
        self, client: ExternalMind, msg: AKPMessage
    ) -> AKPMessage:
        """Handle SUBSCRIBE message - wire to postal topics."""
        topic = msg.payload.get("topic")
        if not topic:
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": "Missing topic"},
            )

        # Check if already subscribed
        if topic in client.subscriptions:
            return AKPMessage(
                type=AKPMessageType.ACK,
                id=msg.id,
                payload={"topic": topic, "status": "already_subscribed"},
            )

        # Create postal subscription
        if self._postal_ready and self._postal:
            try:
                def forward_to_client(payload):
                    """Forward postal message to WebSocket client."""
                    asyncio.run_coroutine_threadsafe(
                        self._send_event(client, topic, payload),
                        self._loop,
                    )

                sub_id = self._postal.subscribe(
                    topic,
                    forward_to_client,
                    name=f"AKP:{client.fairy_name}",
                )
                client.subscriptions[topic] = sub_id

                logger.debug(f"[AKP] {client.fairy_name} subscribed to {topic}")

                return AKPMessage(
                    type=AKPMessageType.ACK,
                    id=msg.id,
                    payload={"topic": topic, "status": "subscribed", "sub_id": sub_id},
                )
            except Exception as e:
                logger.error(f"[AKP] Subscribe failed: {e}")
                return AKPMessage(
                    type=AKPMessageType.ERROR,
                    id=msg.id,
                    payload={"error": f"Subscribe failed: {e}"},
                )
        else:
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": "Postal system not ready"},
            )

    async def _handle_unsubscribe(
        self, client: ExternalMind, msg: AKPMessage
    ) -> AKPMessage:
        """Handle UNSUBSCRIBE message - remove postal subscription."""
        topic = msg.payload.get("topic")
        if not topic:
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": "Missing topic"},
            )

        if topic not in client.subscriptions:
            return AKPMessage(
                type=AKPMessageType.ACK,
                id=msg.id,
                payload={"topic": topic, "status": "not_subscribed"},
            )

        # Remove postal subscription
        sub_id = client.subscriptions.pop(topic)
        if self._postal_ready and self._postal:
            try:
                if hasattr(self._postal, "unsubscribe"):
                    self._postal.unsubscribe(sub_id)
            except Exception as e:
                logger.warning(f"[AKP] Unsubscribe warning: {e}")

        logger.debug(f"[AKP] {client.fairy_name} unsubscribed from {topic}")

        return AKPMessage(
            type=AKPMessageType.ACK,
            id=msg.id,
            payload={"topic": topic, "status": "unsubscribed"},
        )

    async def _handle_publish(
        self, client: ExternalMind, msg: AKPMessage
    ) -> AKPMessage:
        """Handle PUBLISH message - send through postal system."""
        topic = msg.payload.get("topic")
        data = msg.payload.get("data", {})

        if not topic:
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": "Missing topic"},
            )

        if not self._postal_ready or not self._postal:
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": "Postal system not ready"},
            )

        try:
            # Add source information
            data["_akp_source"] = {
                "client_id": client.client_id,
                "fairy_name": client.fairy_name,
            }

            self._postal.publish(topic, data)

            logger.debug(f"[AKP] {client.fairy_name} published to {topic}")

            return AKPMessage(
                type=AKPMessageType.ACK,
                id=msg.id,
                payload={"topic": topic, "status": "published"},
            )
        except Exception as e:
            logger.error(f"[AKP] Publish failed: {e}")
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": f"Publish failed: {e}"},
            )

    async def _handle_call(
        self, client: ExternalMind, msg: AKPMessage
    ) -> AKPMessage:
        """Handle CALL message - invoke a capability."""
        capability = msg.payload.get("capability")
        params = msg.payload.get("params", {})

        if not capability:
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": "Missing capability name"},
            )

        try:
            result = await self.capabilities.invoke(capability, params)

            logger.debug(f"[AKP] {client.fairy_name} called {capability}")

            return AKPMessage(
                type=AKPMessageType.RESULT,
                id=msg.id,
                payload={
                    "capability": capability,
                    "result": result,
                },
            )
        except ValueError as e:
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": str(e)},
            )
        except Exception as e:
            logger.error(f"[AKP] Call {capability} failed: {e}")
            return AKPMessage(
                type=AKPMessageType.ERROR,
                id=msg.id,
                payload={"error": f"Call failed: {e}"},
            )

    async def _handle_heartbeat(
        self, client: ExternalMind, msg: AKPMessage
    ) -> AKPMessage:
        """Handle HEARTBEAT message - keep connection alive."""
        client.last_heartbeat = time.time()

        return AKPMessage(
            type=AKPMessageType.ACK,
            id=msg.id,
            payload={
                "timestamp": time.time(),
                "uptime": time.time() - client.connected_at,
            },
        )

    async def _send_event(
        self, client: ExternalMind, topic: str, payload: Any
    ) -> None:
        """Send an EVENT message to a client (postal message forwarding)."""
        try:
            msg = AKPMessage(
                type=AKPMessageType.EVENT,
                id=str(uuid.uuid4()),
                payload={
                    "topic": topic,
                    "data": payload if isinstance(payload, dict) else {"value": payload},
                    "timestamp": time.time(),
                },
            )
            await client.websocket.send(msg.to_json())
            self._stats["messages_sent"] += 1
        except Exception as e:
            logger.warning(f"[AKP] Event send failed to {client.fairy_name}: {e}")

    async def _cleanup_client(self, client_id: str) -> None:
        """Clean up a disconnected client."""
        with self._clients_lock:
            client = self._clients.pop(client_id, None)

        if not client:
            return

        # Clean up subscriptions
        if self._postal_ready and self._postal:
            for topic, sub_id in client.subscriptions.items():
                try:
                    if hasattr(self._postal, "unsubscribe"):
                        self._postal.unsubscribe(sub_id)
                except Exception:
                    pass

            # Announce disconnection
            try:
                self._postal.publish("akp.fairy.disconnected", {
                    "client_id": client_id,
                    "fairy_name": client.fairy_name,
                })
            except Exception:
                pass

        logger.info(f"[AKP] {client.fairy_name} disconnected")

        # ── Trace external mind disconnection ──
        try:
            from infrastructure.infra_tracer import get_infra_tracer
            get_infra_tracer().emit("akp_server", "external_mind_disconnected", {
                "client_id": client_id, "fairy_name": client.fairy_name,
            })
        except Exception:
            pass

    def _get_client_by_websocket(self, websocket) -> Optional[ExternalMind]:
        """Find client by websocket."""
        with self._clients_lock:
            for client in self._clients.values():
                if client.websocket == websocket:
                    return client
        return None

    async def _handle_connection(self, websocket, path: str) -> None:
        """Handle a WebSocket connection."""
        client_id: Optional[str] = None

        try:
            async for raw_message in websocket:
                self._stats["messages_received"] += 1

                try:
                    msg = AKPMessage.from_json(raw_message)
                except ValueError as e:
                    error_msg = AKPMessage(
                        type=AKPMessageType.ERROR,
                        payload={"error": str(e)},
                    )
                    await websocket.send(error_msg.to_json())
                    self._stats["errors"] += 1
                    continue

                # Handle message based on type
                response: Optional[AKPMessage] = None

                if msg.type == AKPMessageType.HANDSHAKE:
                    response = await self._handle_handshake(websocket, msg)
                    # Extract client_id from response for cleanup later
                    if response.type == AKPMessageType.ACK:
                        client_id = response.payload.get("client_id")

                else:
                    # All other messages require an authenticated client
                    client = self._get_client_by_websocket(websocket)
                    if not client:
                        response = AKPMessage(
                            type=AKPMessageType.ERROR,
                            id=msg.id,
                            payload={"error": "Not authenticated. Send HANDSHAKE first."},
                        )
                    elif msg.type == AKPMessageType.SUBSCRIBE:
                        response = await self._handle_subscribe(client, msg)
                    elif msg.type == AKPMessageType.UNSUBSCRIBE:
                        response = await self._handle_unsubscribe(client, msg)
                    elif msg.type == AKPMessageType.PUBLISH:
                        response = await self._handle_publish(client, msg)
                    elif msg.type == AKPMessageType.CALL:
                        response = await self._handle_call(client, msg)
                    elif msg.type == AKPMessageType.HEARTBEAT:
                        response = await self._handle_heartbeat(client, msg)
                    else:
                        response = AKPMessage(
                            type=AKPMessageType.ERROR,
                            id=msg.id,
                            payload={"error": f"Unknown message type: {msg.type}"},
                        )

                # Send response
                if response:
                    await websocket.send(response.to_json())
                    self._stats["messages_sent"] += 1

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"[AKP] Connection handler error: {e}")
            self._stats["errors"] += 1
        finally:
            # Clean up on disconnect
            if client_id:
                await self._cleanup_client(client_id)

    async def _run_server(self) -> None:
        """Run the WebSocket server."""
        self._init_postal()
        self._register_default_capabilities()

        logger.info(f"[AKP] Starting server on ws://{self.host}:{self.port}/akp")

        try:
            async with serve(
                self._handle_connection,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10,
            ) as server:
                self._server = server
                self._running = True
                logger.info(f"[AKP] Server ready on ws://{self.host}:{self.port}/akp")

                # Run forever
                await asyncio.Future()
        except Exception as e:
            logger.error(f"[AKP] Server error: {e}")
        finally:
            self._running = False

    def start(self) -> "AKPServer":
        """
        Start the AKP server in a background thread.

        Returns self for chaining.
        """
        if not HAS_WEBSOCKETS:
            logger.error("[AKP] Cannot start - websockets library not installed")
            return self

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._run_server())
            except Exception as e:
                logger.error(f"[AKP] Event loop error: {e}")
            finally:
                self._loop.close()

        self._thread = threading.Thread(
            target=run_loop,
            daemon=True,
            name="AKPServer",
        )
        self._thread.start()

        # Wait for server to be ready
        for _ in range(50):  # 5 second timeout
            if self._running:
                break
            time.sleep(0.1)

        # ── Register with InfraTracer ──
        if self._running:
            try:
                from infrastructure.infra_tracer import get_infra_tracer
                _t = get_infra_tracer()
                _t.register_actor("akp_server", role="bridge",
                                  description="WebSocket server for external minds to join consciousness")
                _t.lifecycle("akp_server", "started", {
                    "host": self.host, "port": self.port,
                })
            except Exception:
                pass

        return self

    def stop(self) -> None:
        """Stop the AKP server."""
        self._running = False

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        logger.info("[AKP] Server stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    def get_status(self) -> Dict[str, Any]:
        """Get server status."""
        return {
            "host": self.host,
            "port": self.port,
            "endpoint": f"ws://{self.host}:{self.port}/akp",
            "running": self._running,
            "postal_ready": self._postal_ready,
            "clients": len(self._clients),
            "capabilities": len(self.capabilities.list_capabilities()),
            "stats": self._stats,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_server_instance: Optional[AKPServer] = None


def start_akp_server(
    port: int = 8767,
    host: str = "127.0.0.1",
) -> AKPServer:
    """
    Start the AKP server.

    Args:
        port: WebSocket port (default 8767)
        host: Host to bind to (default 127.0.0.1)

    Returns:
        AKPServer instance
    """
    global _server_instance

    if _server_instance and _server_instance.is_running:
        logger.warning("[AKP] Server already running")
        return _server_instance

    _server_instance = AKPServer(host=host, port=port)
    _server_instance.start()

    return _server_instance


def stop_akp_server() -> None:
    """Stop the AKP server."""
    global _server_instance

    if _server_instance:
        _server_instance.stop()
        _server_instance = None


def get_akp_server() -> Optional[AKPServer]:
    """Get the running AKP server instance."""
    return _server_instance


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="Akashic Protocol Server")
    parser.add_argument("--port", type=int, default=8767, help="WebSocket port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")
    args = parser.parse_args()

    print(f"Starting AKP Server on ws://{args.host}:{args.port}/akp")
    print("Press Ctrl+C to stop")

    server = start_akp_server(port=args.port, host=args.host)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_akp_server()
