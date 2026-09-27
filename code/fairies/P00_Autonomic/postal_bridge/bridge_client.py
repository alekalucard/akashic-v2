# ════════════════════════════════════════════════════════════════════════════════
# POSTAL BRIDGE CLIENT - MCP side coordinator
# ════════════════════════════════════════════════════════════════════════════════
#
# This runs in the MCP process and coordinates all channels to communicate
# with the akashic_v2 server. It provides the same interface as the old postal tunnel
# but with multiple fallback channels.
#
# Priority order:
# 1. Shared Memory - For state reads (instant)
# 2. SQLite Queue - For reliable message delivery (always works)
# 3. Socket Tunnel - For low-latency queries (when available)
#
# ════════════════════════════════════════════════════════════════════════════════

import time
import threading
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path

from .sqlite_channel import SQLiteChannel, get_sqlite_channel
from .shared_memory_channel import SharedMemoryChannel, get_shared_memory


# Singleton
_bridge_client: Optional['PostalBridgeClient'] = None
_client_lock = threading.Lock()


def get_bridge_client() -> 'PostalBridgeClient':
    """Get or create the singleton bridge client."""
    global _bridge_client
    if _bridge_client is None:
        with _client_lock:
            if _bridge_client is None:
                _bridge_client = PostalBridgeClient()
    return _bridge_client


class PostalBridgeClient:
    """
    MCP-side postal bridge coordinator.
    
    Provides reliable communication with the server using multiple channels:
    - SQLite for guaranteed message delivery
    - Shared memory for fast state reads
    - Optional socket for low-latency (when available)
    
    Usage:
        client = get_bridge_client()
        client.connect()
        
        # Send message (always succeeds)
        client.route("ace.inbox", {"message": "Hello!"})
        
        # Read state (instant, no IPC)
        state = client.read_state()
        
        # Query with response (uses best available channel)
        result = client.query("query_consciousness", {})
    """
    
    def __init__(self):
        self.sqlite = get_sqlite_channel()
        self.memory = get_shared_memory()
        
        self._connected = False
        self._socket_available = False
        self._socket_tunnel = None  # Optional: existing PostalTunnel
        
        self._subscribers: Dict[str, List[Callable]] = {}
        self._subscriber_lock = threading.Lock()
        
        # Statistics
        self._route_count = 0
        self._query_count = 0
        self._read_count = 0
    
    def connect(self, socket_port: int = None, verify: bool = True) -> bool:
        """
        Connect to the server.

        Args:
            socket_port: Optional port for socket tunnel (legacy support)
            verify: If True, ping the server to verify it's actually alive

        Returns:
            True if connected AND verified (or verify=False)
        """
        # Attach to shared memory (for reads)
        if self.memory.attach():
            print("[PostalBridgeClient] Shared memory attached")

        # SQLite channel is always "ready" (file-based)
        print("[PostalBridgeClient] SQLite channel ready")

        # Start polling for incoming messages
        self.sqlite.start_polling('main_to_mcp')

        # Optionally try socket tunnel
        if socket_port:
            self._try_socket_connect(socket_port)

        # CRITICAL: Verify server is actually alive!
        # Without this, we'd claim "connected" when files exist but nobody's reading
        if verify:
            print("[PostalBridgeClient] Verifying server is alive...")
            if self.sqlite.is_other_side_alive(max_stale_seconds=3.0):
                print("[PostalBridgeClient] [OK] server verified ALIVE (got pong)")
                self._connected = True
                return True
            else:
                print("[PostalBridgeClient] [X] server NOT responding (no pong)")
                self._connected = False
                return False
        else:
            # No verification - assume connected if channels are ready
            self._connected = True
            return True

    def verify_connection(self) -> bool:
        """
        Verify the server is actually alive and responding.

        Use this to check if a previously established connection is still valid.

        Returns:
            True if the server responds to ping
        """
        return self.sqlite.is_other_side_alive(max_stale_seconds=3.0)

    def ping(self, timeout: float = 2.0) -> bool:
        """
        Send a ping and wait for pong.

        Returns:
            True if pong received
        """
        return self.sqlite.ping(timeout=timeout)
    
    def _try_socket_connect(self, port: int):
        """Try to connect to socket tunnel (optional fast path)."""
        try:
            # FIX 2026-06-02 (Nous+Ace): P00.mcp ghost → P40 (MCP layer lives in P40; TODO: move back to P00 someday). Re-enables the optional socket fast-path (still falls back to SQLite if the tunnel isn't up).
            from fairies.P40_Sensory.mcp.postal_tunnel import PostalTunnelClient
            self._socket_tunnel = PostalTunnelClient()
            if self._socket_tunnel.connect(port=port):
                self._socket_available = True
                print("[PostalBridgeClient] Socket tunnel connected (fast path available)")
            else:
                self._socket_tunnel = None
        except Exception as e:
            print(f"[PostalBridgeClient] Socket tunnel unavailable: {e}")
            self._socket_tunnel = None
    
    def disconnect(self):
        """Disconnect from all channels."""
        self.sqlite.stop_polling()
        self.memory.close()
        if self._socket_tunnel:
            try:
                self._socket_tunnel.close()
            except Exception:
                pass
        self._connected = False
    
    # ═══════════════════════════════════════════════════════════════════════
    # ROUTING MESSAGES (MCP → server)
    # ═══════════════════════════════════════════════════════════════════════
    
    def route(self, topic: str, payload: Dict[str, Any], 
              fire_and_forget: bool = True) -> int:
        """
        Route a message to the server.
        
        This ALWAYS succeeds (queued to SQLite if socket unavailable).
        
        Args:
            topic: Postal topic (e.g., 'ace.inbox')
            payload: Message payload
            fire_and_forget: If True, don't wait for confirmation
            
        Returns:
            1 if queued successfully, 0 if failed
        """
        try:
            # Try socket first if available (fast path)
            if self._socket_available and self._socket_tunnel:
                try:
                    result = self._socket_tunnel.route(topic, payload, 
                                                       fire_and_forget=fire_and_forget)
                    if result > 0:
                        self._route_count += 1
                        return result
                except Exception:
                    # Socket failed, fall through to SQLite
                    self._socket_available = False
            
            # Queue to SQLite (always works)
            self.sqlite.send_to_main(topic, payload)
            self._route_count += 1
            return 1
            
        except Exception as e:
            print(f"[PostalBridgeClient] Route error: {e}")
            return 0
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATE READS (instant, no IPC)
    # ═══════════════════════════════════════════════════════════════════════
    
    def read_state(self, key: str = None) -> Optional[Any]:
        """
        Read current system state from shared memory.
        
        This is INSTANT - no network round-trip.
        State may be up to 500ms stale.
        
        Args:
            key: Optional specific key, or None for full state
            
        Returns:
            State dict or specific value
        """
        self._read_count += 1
        return self.memory.read_state(key)
    
    def get_heart_rate(self) -> Optional[float]:
        """Quick accessor for heart rate."""
        return self.memory.read_heart_rate()
    
    def get_consciousness(self) -> Optional[Dict]:
        """Quick accessor for consciousness state."""
        return self.memory.read_consciousness()
    
    def get_fairy_count(self) -> Optional[int]:
        """Quick accessor for active fairy count."""
        return self.memory.read_fairy_count()
    
    # ═══════════════════════════════════════════════════════════════════════
    # QUERIES (request/response)
    # ═══════════════════════════════════════════════════════════════════════
    
    def query(self, command: str, params: Dict[str, Any] = None,
              timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Send a query and wait for response.
        
        Uses socket if available, falls back to SQLite queue.
        
        Args:
            command: Query command (e.g., 'query_consciousness')
            params: Query parameters
            timeout: How long to wait for response
            
        Returns:
            Response dict, or None if timeout/error
        """
        params = params or {}
        payload = {'cmd': command, **params}
        
        self._query_count += 1
        
        # Try socket first (faster response)
        if self._socket_available and self._socket_tunnel:
            try:
                return self._socket_tunnel.request(payload, timeout=timeout)
            except Exception:
                self._socket_available = False
        
        # Fall back to SQLite request/response
        return self.sqlite.request('mcp_to_main', 'query', payload, timeout=timeout)
    
    def query_consciousness(self, timeout: float = 5.0) -> Dict[str, Any]:
        """Query full consciousness state from the server."""
        # First try shared memory (instant)
        state = self.read_state()
        if state and 'consciousness' in state:
            return state
        
        # Fall back to query
        result = self.query('query_consciousness', timeout=timeout)
        return result or {'status': 'unavailable'}
    
    def query_fairy(self, fairy_name: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Query a specific fairy's state."""
        result = self.query('query_fairy', {'fairy_name': fairy_name}, timeout=timeout)
        return result or {'status': 'unavailable', 'fairy_name': fairy_name}
    
    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTIONS (receive messages from server)
    # ═══════════════════════════════════════════════════════════════════════
    
    def subscribe(self, topic: str, callback: Callable[[Dict], None]):
        """
        Subscribe to messages from the server.
        
        Note: Uses SQLite polling, so there may be slight delay.
        For real-time needs, check if socket is available.
        """
        self.sqlite.subscribe(topic, callback)
        
        with self._subscriber_lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)
    
    def list_topics(self) -> List[str]:
        """List all subscribed topics."""
        with self._subscriber_lock:
            return list(self._subscribers.keys())

    def unsubscribe(self, topic: str, callback: Callable = None):
        """Unsubscribe from a topic."""
        with self._subscriber_lock:
            if topic in self._subscribers:
                if callback:
                    self._subscribers[topic] = [c for c in self._subscribers[topic] if c != callback]
                else:
                    del self._subscribers[topic]

    # Aliases for SharedPostalHub compatibility
    def send(self, topic: str, payload: Dict = None) -> int:
        return self.route(topic, payload or {})

    def receive(self, topic: str, handler: Callable):
        return self.subscribe(topic, handler)

    def publish(self, topic: str, payload: Dict = None) -> int:
        return self.route(topic, payload or {})

    def to(self, topic: str, payload: Dict = None) -> int:
        return self.route(topic, payload or {})

    # ═══════════════════════════════════════════════════════════════════════
    # LANE SHORTCUTS (SharedPostalHub compatibility)
    # ═══════════════════════════════════════════════════════════════════════

    def to_TELEMETRY(self, pkt: Dict) -> int:
        return self.route("telemetry", pkt)

    def to_PLAN(self, pkt: Dict) -> int:
        return self.route("plan", pkt)

    def to_COGNITION(self, pkt: Dict) -> int:
        return self.route("cognition", pkt)

    def to_SOMATIC(self, pkt: Dict) -> int:
        return self.route("somatic", pkt)

    def to_CHEMISTRY(self, pkt: Dict) -> int:
        return self.route("chemistry", pkt)

    def to_MEMORY(self, pkt: Dict) -> int:
        return self.route("memory", pkt)

    def to_TRACER(self, pkt: Dict) -> int:
        return self.route("tracer", pkt)

    def to_DIRECTORY(self, pkt: Dict) -> int:
        return self.route("directory", pkt)

    # ═══════════════════════════════════════════════════════════════════════
    # FAIRY REGISTRY (User Profile System)
    # ═══════════════════════════════════════════════════════════════════════

    def register_fairy(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a fairy with the system (via server).

        Args:
            contract: Fairy contract/profile dict

        Returns:
            Registration result from server
        """
        result = self.query("register_fairy", {"contract": contract}, timeout=5.0)
        return result or {"status": "failed", "error": "timeout"}

    def unregister_fairy(self, actor_id: str) -> Dict[str, Any]:
        """Unregister a fairy."""
        result = self.query("unregister_fairy", {"actor_id": actor_id}, timeout=5.0)
        return result or {"status": "failed"}

    def get_citizen(self, actor_name: str) -> Optional[Dict[str, Any]]:
        """Get a fairy's profile by name."""
        result = self.query("get_citizen", {"actor_name": actor_name}, timeout=5.0)
        return result

    def list_citizens(self) -> List[str]:
        """List all awake fairy names."""
        result = self.query("list_citizens", timeout=5.0)
        if result and "citizens" in result:
            return result["citizens"]
        return []

    # ═══════════════════════════════════════════════════════════════════════
    # INTENT SYSTEM (User Actions)
    # ═══════════════════════════════════════════════════════════════════════

    def use_intent(self, actor_name: str, intent: str, payload: Dict = None) -> Optional[Any]:
        """
        Invoke an intent on a fairy.

        Args:
            actor_name: Target fairy name
            intent: Intent name to invoke
            payload: Parameters for the intent

        Returns:
            Result from intent, or None
        """
        result = self.query("use_intent", {
            "actor": actor_name,
            "intent": intent,
            "payload": payload or {},
        }, timeout=10.0)
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # CONNECTIVITY CHECKS
    # ═══════════════════════════════════════════════════════════════════════

    def check_connectivity(self, actor_name: str) -> Dict[str, Any]:
        """Check connectivity status for a fairy."""
        result = self.query("check_connectivity", {"actor_name": actor_name}, timeout=5.0)
        return result or {"status": "unknown", "actor_name": actor_name}

    def get_connectivity_issues(self) -> List[str]:
        """Get list of fairies with connectivity issues."""
        result = self.query("get_connectivity_issues", timeout=5.0)
        if result and "isolated" in result:
            return result["isolated"]
        return []

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            'connected': self._connected,
            'socket_available': self._socket_available,
            'routes_sent': self._route_count,
            'queries_sent': self._query_count,
            'state_reads': self._read_count,
            'sqlite': self.sqlite.get_stats(),
            'memory': self.memory.get_stats(),
        }
    
    def is_connected(self) -> bool:
        """Check if bridge is connected."""
        return self._connected
    
    def health_check(self) -> Dict[str, Any]:
        """
        Quick health check of all channels.
        
        Returns dict with status of each channel.
        """
        return {
            'sqlite': {
                'status': 'ok',  # SQLite always works
                'pending_to_main': self.sqlite.get_stats().get('pending_to_main', 0),
            },
            'memory': {
                'status': 'ok' if self.memory._shm is not None else 'file_fallback',
                'cache_fresh': time.time() - self.memory._cache_time < 1.0,
            },
            'socket': {
                'status': 'ok' if self._socket_available else 'unavailable',
            }
        }


# ════════════════════════════════════════════════════════════════════════════════
# COMPATIBILITY LAYER - Drop-in replacement for PostalTunnel
# ════════════════════════════════════════════════════════════════════════════════

class PostalTunnelCompatible:
    """
    Compatibility wrapper that provides the same interface as the old
    PostalTunnel but uses the new multi-channel bridge.
    
    Drop-in replacement for existing code.
    """
    
    def __init__(self):
        self._client = get_bridge_client()
    
    def connect(self, port: int = None) -> bool:
        """Connect (port is optional now)."""
        return self._client.connect(socket_port=port)
    
    def close(self):
        """Close connection."""
        self._client.disconnect()
    
    def route(self, topic: str, payload: Dict[str, Any], 
              fire_and_forget: bool = False) -> int:
        """Route a message."""
        return self._client.route(topic, payload, fire_and_forget)
    
    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to a topic."""
        self._client.subscribe(topic, callback)
    
    def request(self, msg: Dict[str, Any], timeout: float = 10.0) -> Optional[Dict]:
        """Send request and wait for response."""
        cmd = msg.get('cmd', 'query')
        return self._client.query(cmd, msg, timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return self._client.get_stats()
    
    @property
    def connected(self) -> bool:
        """Check if connected."""
        return self._client.is_connected()
