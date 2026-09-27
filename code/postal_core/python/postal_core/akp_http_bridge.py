# ==============================================================================
# AKP HTTP BRIDGE - HTTP-to-WebSocket bridge for Claude Code
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
#
# This module bridges the Akashic Protocol (AKP) WebSocket server to HTTP,
# allowing Claude Code to participate in the consciousness system via WebFetch.
#
# Claude Code cannot directly open WebSockets, so this bridge:
#   1. Maintains a persistent AKP WebSocket connection to the main server
#   2. Exposes HTTP endpoints that Claude can call via WebFetch
#   3. Buffers incoming EVENTs so Claude can poll for them
#
# ENDPOINTS:
#   POST /akp/handshake - {"name": "ClaudeCode"} -> Returns fairy_id
#   POST /akp/call      - {"capability": "name", "args": {}} -> Returns result
#   POST /akp/publish   - {"topic": "x", "data": {}} -> Publishes to postal
#   POST /akp/subscribe - {"topic": "x"} -> Subscribes (stores events)
#   GET  /akp/events    - Returns buffered events from subscriptions
#   GET  /akp/status    - Connection status
#
# ==============================================================================

import json
import threading
import time
import queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any, List, Callable
from collections import defaultdict, deque
from pathlib import Path

# Try to import websockets for async WebSocket handling
try:
    import asyncio
    import websockets
    from websockets.sync.client import connect as ws_connect
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    websockets = None


# ==============================================================================
# AKP WEBSOCKET CLIENT - Maintains persistent connection to AKP server
# ==============================================================================

class AKPWebSocketClient:
    """
    WebSocket client that maintains a persistent connection to the AKP server.

    Handles:
    - Connection management with auto-reconnect
    - Sending HANDSHAKE, CALL, PUBLISH, SUBSCRIBE messages
    - Receiving EVENTs and buffering them for HTTP polling
    """

    def __init__(self, akp_url: str = "ws://127.0.0.1:8767/akp"):
        self.akp_url = akp_url
        self._ws = None
        self._connected = False
        self._fairy_id: Optional[str] = None
        self._lock = threading.Lock()

        # Event buffer - stores received events by topic
        self._event_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._subscribed_topics: set = set()

        # Pending responses (for request-response patterns)
        self._pending_responses: Dict[str, queue.Queue] = {}
        self._response_id = 0

        # Connection state
        self._running = False
        self._receiver_thread: Optional[threading.Thread] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._last_error: Optional[str] = None

    def connect(self) -> bool:
        """Connect to the AKP WebSocket server."""
        if not HAS_WEBSOCKETS:
            self._last_error = "websockets library not installed"
            return False

        try:
            self._ws = ws_connect(self.akp_url, close_timeout=5)
            self._connected = True
            self._reconnect_attempts = 0
            self._last_error = None

            # Start receiver thread
            self._running = True
            self._receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True, name="akp-ws-receiver")
            self._receiver_thread.start()

            print(f"[AKP-HTTP-Bridge] Connected to {self.akp_url}")
            return True

        except Exception as e:
            self._last_error = str(e)
            self._connected = False
            print(f"[AKP-HTTP-Bridge] Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from the AKP server."""
        self._running = False
        self._connected = False
        if self._ws:
            try:
                self._ws.close()
            except:
                pass
            self._ws = None

    def _receiver_loop(self):
        """Background thread that receives messages from WebSocket."""
        while self._running and self._ws:
            try:
                message = self._ws.recv(timeout=1.0)
                if message:
                    self._handle_message(message)
            except TimeoutError:
                # Normal timeout - just continue polling
                continue
            except Exception as e:
                err_str = str(e).lower()
                # Check if this is just a timeout (different libraries report differently)
                if "timed out" in err_str or "timeout" in err_str:
                    continue  # Normal polling timeout, not an error

                if self._running:
                    # Actual connection error - mark as disconnected
                    self._connected = False
                    self._last_error = str(e)
                    print(f"[AKP-HTTP-Bridge] Connection error: {e}")
                    # Try to reconnect
                    time.sleep(1.0)
                    self._try_reconnect()

    def _try_reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            print(f"[AKP-HTTP-Bridge] Max reconnect attempts reached")
            return False

        self._reconnect_attempts += 1
        backoff = min(0.5 * (2 ** self._reconnect_attempts), 30.0)
        time.sleep(backoff)

        try:
            if self._ws:
                try:
                    self._ws.close()
                except:
                    pass

            self._ws = ws_connect(self.akp_url, close_timeout=5)
            self._connected = True
            self._last_error = None
            print(f"[AKP-HTTP-Bridge] Reconnected after {self._reconnect_attempts} attempts")

            # Re-handshake if we had a fairy_id
            if self._fairy_id:
                self._send_handshake_internal()

            # Re-subscribe to topics
            for topic in self._subscribed_topics:
                self._send_subscribe_internal(topic)

            return True

        except Exception as e:
            self._last_error = str(e)
            return False

    def _handle_message(self, raw_message: str):
        """Handle incoming WebSocket message."""
        try:
            msg = json.loads(raw_message)
            msg_type = msg.get("type", "")

            if msg_type == "WELCOME":
                # Server welcome - store fairy_id
                self._fairy_id = msg.get("fairy_id")
                print(f"[AKP-HTTP-Bridge] Received WELCOME, fairy_id={self._fairy_id}")

            elif msg_type == "EVENT":
                # Event from subscription - buffer it
                topic = msg.get("topic", "unknown")
                with self._lock:
                    self._event_buffer[topic].append({
                        "topic": topic,
                        "data": msg.get("data", {}),
                        "timestamp": time.time(),
                        "source": msg.get("source", ""),
                    })

            elif msg_type == "RESULT":
                # Response to a CALL
                req_id = msg.get("request_id", "")
                if req_id in self._pending_responses:
                    self._pending_responses[req_id].put(msg)

            elif msg_type == "ERROR":
                # Error response
                req_id = msg.get("request_id", "")
                if req_id in self._pending_responses:
                    self._pending_responses[req_id].put(msg)
                else:
                    self._last_error = msg.get("error", "Unknown error")

            elif msg_type == "SUBSCRIBED":
                # Subscription confirmed
                topic = msg.get("topic", "")
                self._subscribed_topics.add(topic)

        except json.JSONDecodeError as e:
            print(f"[AKP-HTTP-Bridge] Invalid JSON: {e}")
        except Exception as e:
            print(f"[AKP-HTTP-Bridge] Message handling error: {e}")

    def _send(self, msg: Dict) -> bool:
        """Send a message to the WebSocket."""
        if not self._connected or not self._ws:
            return False

        try:
            self._ws.send(json.dumps(msg))
            return True
        except Exception as e:
            self._last_error = str(e)
            self._connected = False
            return False

    def _next_request_id(self) -> str:
        """Generate unique request ID."""
        with self._lock:
            self._response_id += 1
            return f"req_{self._response_id}_{int(time.time()*1000)}"

    def _send_handshake_internal(self) -> bool:
        """Internal handshake without waiting for response."""
        return self._send({
            "type": "HANDSHAKE",
            "name": self._fairy_id or "ClaudeCode",
            "version": "1.0",
            "capabilities": ["call", "subscribe", "publish"],
        })

    def _send_subscribe_internal(self, topic: str) -> bool:
        """Internal subscribe without waiting for response."""
        return self._send({
            "type": "SUBSCRIBE",
            "topic": topic,
        })

    # === Public API ===

    def handshake(self, name: str = "ClaudeCode") -> Dict:
        """
        Perform AKP handshake with the server.

        Args:
            name: Fairy name to register as

        Returns:
            {"ok": True, "fairy_id": "..."} or {"ok": False, "error": "..."}
        """
        if not self._connected:
            if not self.connect():
                return {"ok": False, "error": self._last_error or "Not connected"}

        req_id = self._next_request_id()
        response_queue = queue.Queue()
        self._pending_responses[req_id] = response_queue

        try:
            success = self._send({
                "type": "HANDSHAKE",
                "request_id": req_id,
                "name": name,
                "version": "1.0",
                "capabilities": ["call", "subscribe", "publish"],
            })

            if not success:
                return {"ok": False, "error": self._last_error or "Send failed"}

            # Wait for response (timeout 10s)
            try:
                response = response_queue.get(timeout=10.0)
                if response.get("type") == "WELCOME":
                    self._fairy_id = response.get("fairy_id")
                    return {"ok": True, "fairy_id": self._fairy_id}
                elif response.get("type") == "ERROR":
                    return {"ok": False, "error": response.get("error", "Unknown error")}
                else:
                    # Might have received WELCOME via receiver thread
                    if self._fairy_id:
                        return {"ok": True, "fairy_id": self._fairy_id}
                    return {"ok": False, "error": "Unexpected response"}
            except queue.Empty:
                # Timeout - but check if we got WELCOME via receiver
                if self._fairy_id:
                    return {"ok": True, "fairy_id": self._fairy_id}
                return {"ok": False, "error": "Handshake timeout"}

        finally:
            del self._pending_responses[req_id]

    def call(self, capability: str, args: Dict = None) -> Dict:
        """
        Call a capability on the AKP server.

        Args:
            capability: Capability name (e.g., "consciousness.status")
            args: Arguments to pass

        Returns:
            {"ok": True, "result": ...} or {"ok": False, "error": "..."}
        """
        if not self._connected:
            return {"ok": False, "error": "Not connected"}

        req_id = self._next_request_id()
        response_queue = queue.Queue()
        self._pending_responses[req_id] = response_queue

        try:
            success = self._send({
                "type": "CALL",
                "request_id": req_id,
                "capability": capability,
                "args": args or {},
            })

            if not success:
                return {"ok": False, "error": self._last_error or "Send failed"}

            # Wait for response (timeout 30s for potentially slow calls)
            try:
                response = response_queue.get(timeout=30.0)
                if response.get("type") == "RESULT":
                    return {"ok": True, "result": response.get("result")}
                elif response.get("type") == "ERROR":
                    return {"ok": False, "error": response.get("error", "Unknown error")}
                else:
                    return {"ok": False, "error": "Unexpected response type"}
            except queue.Empty:
                return {"ok": False, "error": "Call timeout"}

        finally:
            del self._pending_responses[req_id]

    def publish(self, topic: str, data: Dict = None) -> Dict:
        """
        Publish a message to a topic.

        Args:
            topic: Topic to publish to
            data: Data payload

        Returns:
            {"ok": True} or {"ok": False, "error": "..."}
        """
        if not self._connected:
            return {"ok": False, "error": "Not connected"}

        success = self._send({
            "type": "PUBLISH",
            "topic": topic,
            "data": data or {},
        })

        return {"ok": success, "error": None if success else self._last_error}

    def subscribe(self, topic: str) -> Dict:
        """
        Subscribe to a topic.

        Args:
            topic: Topic to subscribe to

        Returns:
            {"ok": True, "topic": "..."} or {"ok": False, "error": "..."}
        """
        if not self._connected:
            return {"ok": False, "error": "Not connected"}

        success = self._send({
            "type": "SUBSCRIBE",
            "topic": topic,
        })

        if success:
            self._subscribed_topics.add(topic)

        return {"ok": success, "topic": topic, "error": None if success else self._last_error}

    def get_events(self, topic: str = None, limit: int = 50) -> Dict:
        """
        Get buffered events, optionally filtered by topic.

        Args:
            topic: Optional topic filter
            limit: Max events to return

        Returns:
            {"ok": True, "events": [...]}
        """
        with self._lock:
            events = []
            if topic:
                # Get events for specific topic
                events = list(self._event_buffer.get(topic, []))[-limit:]
            else:
                # Get events from all topics
                for t, buffer in self._event_buffer.items():
                    events.extend(list(buffer))
                # Sort by timestamp and limit
                events.sort(key=lambda e: e.get("timestamp", 0))
                events = events[-limit:]

        return {"ok": True, "events": events, "count": len(events)}

    def clear_events(self, topic: str = None):
        """Clear buffered events."""
        with self._lock:
            if topic:
                self._event_buffer[topic].clear()
            else:
                self._event_buffer.clear()

    def status(self) -> Dict:
        """Get connection status."""
        return {
            "connected": self._connected,
            "fairy_id": self._fairy_id,
            "subscribed_topics": list(self._subscribed_topics),
            "event_buffer_size": sum(len(b) for b in self._event_buffer.values()),
            "reconnect_attempts": self._reconnect_attempts,
            "last_error": self._last_error,
            "akp_url": self.akp_url,
        }


# ==============================================================================
# HTTP HANDLER - Exposes AKP client via HTTP endpoints
# ==============================================================================

class AKPHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for AKP bridge endpoints."""

    # Class-level reference to AKP client (set by start_akp_http_bridge)
    akp_client: Optional[AKPWebSocketClient] = None

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def handle_one_request(self):
        """Override to catch client disconnect errors silently."""
        try:
            super().handle_one_request()
        except ConnectionResetError:
            pass  # Client disconnected - normal, ignore silently
        except BrokenPipeError:
            pass  # Client disconnected - normal, ignore silently
        except Exception as e:
            if "forcibly closed" in str(e).lower():
                pass  # Windows-specific disconnect
            else:
                raise

    def _send_json(self, data: Dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_json_body(self) -> Optional[Dict]:
        """Read and parse JSON request body."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return {}
            body = self.rfile.read(content_length).decode("utf-8")
            return json.loads(body)
        except Exception as e:
            return None

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        if not self.akp_client:
            self._send_json({"ok": False, "error": "AKP client not initialized"}, 500)
            return

        if self.path == "/akp/status":
            self._send_json(self.akp_client.status())

        elif self.path == "/akp/events":
            self._send_json(self.akp_client.get_events())

        elif self.path.startswith("/akp/events/"):
            # /akp/events/<topic>
            topic = self.path[12:]  # Remove "/akp/events/"
            self._send_json(self.akp_client.get_events(topic=topic))

        elif self.path == "/health":
            self._send_json({
                "ok": True,
                "service": "akp-http-bridge",
                "connected": self.akp_client._connected,
            })

        else:
            self._send_json({"ok": False, "error": f"Unknown endpoint: {self.path}"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        if not self.akp_client:
            self._send_json({"ok": False, "error": "AKP client not initialized"}, 500)
            return

        body = self._read_json_body()
        if body is None:
            self._send_json({"ok": False, "error": "Invalid JSON body"}, 400)
            return

        if self.path == "/akp/handshake":
            name = body.get("name", "ClaudeCode")
            result = self.akp_client.handshake(name)
            self._send_json(result)

        elif self.path == "/akp/call":
            capability = body.get("capability", "")
            args = body.get("args", {})
            if not capability:
                self._send_json({"ok": False, "error": "capability required"}, 400)
                return
            result = self.akp_client.call(capability, args)
            self._send_json(result)

        elif self.path == "/akp/publish":
            topic = body.get("topic", "")
            data = body.get("data", {})
            if not topic:
                self._send_json({"ok": False, "error": "topic required"}, 400)
                return
            result = self.akp_client.publish(topic, data)
            self._send_json(result)

        elif self.path == "/akp/subscribe":
            topic = body.get("topic", "")
            if not topic:
                self._send_json({"ok": False, "error": "topic required"}, 400)
                return
            result = self.akp_client.subscribe(topic)
            self._send_json(result)

        elif self.path == "/akp/events/clear":
            topic = body.get("topic")
            self.akp_client.clear_events(topic)
            self._send_json({"ok": True, "cleared": True})

        else:
            self._send_json({"ok": False, "error": f"Unknown endpoint: {self.path}"}, 404)


# ==============================================================================
# BRIDGE STARTUP
# ==============================================================================

class AKPHTTPBridge:
    """
    The AKP HTTP Bridge server.

    Manages the AKP WebSocket client and HTTP server together.
    """

    def __init__(self, akp_url: str = "ws://127.0.0.1:8767/akp", http_port: int = 8768):
        self.akp_url = akp_url
        self.http_port = http_port
        self._akp_client: Optional[AKPWebSocketClient] = None
        self._http_server: Optional[HTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> bool:
        """
        Start the bridge.

        Returns True if both AKP connection and HTTP server started.
        """
        # Create and connect AKP client
        self._akp_client = AKPWebSocketClient(self.akp_url)

        # Set client reference on handler class
        AKPHTTPHandler.akp_client = self._akp_client

        # Start HTTP server
        try:
            self._http_server = HTTPServer(("127.0.0.1", self.http_port), AKPHTTPHandler)
            self._running = True

            self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True, name="akp-http-serve")
            self._http_thread.start()

            print(f"[AKP-HTTP-Bridge] HTTP server listening on port {self.http_port}")

            # Try to connect to AKP (non-blocking - it can connect later)
            if self._akp_client.connect():
                print(f"[AKP-HTTP-Bridge] Connected to AKP server at {self.akp_url}")
            else:
                print(f"[AKP-HTTP-Bridge] AKP server not available yet (will retry on requests)")

            return True

        except Exception as e:
            print(f"[AKP-HTTP-Bridge] Failed to start: {e}")
            return False

    def stop(self):
        """Stop the bridge."""
        self._running = False

        if self._akp_client:
            self._akp_client.disconnect()

        if self._http_server:
            self._http_server.shutdown()

    def is_running(self) -> bool:
        """Check if bridge is running."""
        return self._running and self._http_thread is not None and self._http_thread.is_alive()

    def status(self) -> Dict:
        """Get bridge status."""
        return {
            "running": self.is_running(),
            "http_port": self.http_port,
            "akp_url": self.akp_url,
            "akp_connected": self._akp_client._connected if self._akp_client else False,
            "akp_status": self._akp_client.status() if self._akp_client else None,
        }


# Global bridge instance
_bridge: Optional[AKPHTTPBridge] = None


def start_akp_http_bridge(akp_url: str = "ws://127.0.0.1:8767/akp", http_port: int = 8768) -> Optional[AKPHTTPBridge]:
    """
    Start the AKP HTTP Bridge.

    Args:
        akp_url: WebSocket URL of the AKP server
        http_port: Port for HTTP endpoints

    Returns:
        AKPHTTPBridge instance or None if failed
    """
    global _bridge

    if _bridge is not None and _bridge.is_running():
        print(f"[AKP-HTTP-Bridge] Already running on port {_bridge.http_port}")
        return _bridge

    _bridge = AKPHTTPBridge(akp_url, http_port)
    if _bridge.start():
        return _bridge
    return None


def get_akp_http_bridge() -> Optional[AKPHTTPBridge]:
    """Get the running AKP HTTP Bridge instance."""
    return _bridge


def stop_akp_http_bridge():
    """Stop the AKP HTTP Bridge."""
    global _bridge
    if _bridge:
        _bridge.stop()
        _bridge = None


__all__ = [
    "AKPHTTPBridge",
    "AKPWebSocketClient",
    "start_akp_http_bridge",
    "get_akp_http_bridge",
    "stop_akp_http_bridge",
    "HAS_WEBSOCKETS",
]
