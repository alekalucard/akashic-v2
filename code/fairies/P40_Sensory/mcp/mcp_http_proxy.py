# ==============================================================================
# MCP HTTP PROXY - Perception Layer for External Minds
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
#
# This module creates a PERCEPTION LAYER - it translates Claude Code's native
# MCP protocol into calls to our HTTP Tool Bridge. Instead of hardcoded tools,
# Claude sees through Akashic's eyes.
#
# ARCHITECTURE:
#   Claude Code (MCP/SSE) → This Proxy → HTTP Tool Bridge → Postal System
#
# MCP SSE Protocol (2024-11-05):
#   1. Client GET /sse - establishes SSE stream
#   2. Server sends event:endpoint with POST URL
#   3. Client POSTs JSON-RPC to that URL
#   4. Server sends response on SSE stream as event:message
#
# ==============================================================================

import json
import queue
import sys
import threading
import time
import uuid
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from concurrent.futures import ThreadPoolExecutor as _MCPPoolExecutor


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer with bounded thread pool (FIX 2026-04-10 Nous + Ace)."""
    daemon_threads = True
    _pool = _MCPPoolExecutor(max_workers=4, thread_name_prefix="mcp-http")

    def process_request(self, request, client_address):
        """Use bounded pool instead of thread-per-request."""
        try:
            self._pool.submit(self.process_request_thread, request, client_address)
        except RuntimeError:
            self.process_request_thread(request, client_address)
import urllib.parse

# Setup paths
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# Configuration
HTTP_BRIDGE_URL = "http://127.0.0.1:8766"
MCP_PROXY_PORT = 8765  # Where Claude Code connects


# ==============================================================================
# SSE CLIENT REGISTRY - Track connected clients
# ==============================================================================

class SSEClientRegistry:
    """
    Registry for SSE client connections.

    Each client gets a queue for receiving messages. When a POST comes in,
    we find the client and push the response to their queue.
    """

    def __init__(self):
        self._clients: Dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        # For single-client mode (simpler - most common case)
        self._default_client: Optional[str] = None

    def register(self, client_id: str = None) -> tuple:
        """Register a new SSE client, return (client_id, queue)."""
        if client_id is None:
            client_id = str(uuid.uuid4())[:8]

        client_queue = queue.Queue()

        with self._lock:
            self._clients[client_id] = client_queue
            # Set as default if first client
            if self._default_client is None:
                self._default_client = client_id

        print(f"[MCP-Proxy] SSE client registered: {client_id}")
        return client_id, client_queue

    def unregister(self, client_id: str):
        """Remove a client from the registry."""
        with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                print(f"[MCP-Proxy] SSE client unregistered: {client_id}")
            if self._default_client == client_id:
                # Set new default if there are other clients
                self._default_client = next(iter(self._clients), None)

    def send_to_client(self, client_id: str, message: str) -> bool:
        """Send a message to a specific client."""
        with self._lock:
            if client_id in self._clients:
                self._clients[client_id].put(message)
                return True
        return False

    def send_to_default(self, message: str) -> bool:
        """Send a message to the default (most recent) client."""
        with self._lock:
            if self._default_client and self._default_client in self._clients:
                self._clients[self._default_client].put(message)
                return True
        return False

    def get_client_count(self) -> int:
        with self._lock:
            return len(self._clients)


# Global registry
_sse_registry = SSEClientRegistry()


# ==============================================================================
# TOOL DISCOVERY - Learn what the system can do
# ==============================================================================

def discover_tools() -> Dict[str, str]:
    """
    Discover available tools from the HTTP bridge.

    Returns dict of {tool_name: description}
    """
    try:
        response = requests.get(f"{HTTP_BRIDGE_URL}/tools", timeout=5)
        if response.ok:
            data = response.json()
            if data.get("success"):
                return data.get("tools", {})
    except Exception as e:
        print(f"[MCP-Proxy] Tool discovery failed: {e}")
    return {}


def invoke_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invoke a tool through the HTTP bridge.

    Returns the tool result or error.
    """
    try:
        response = requests.post(
            f"{HTTP_BRIDGE_URL}/tool",
            json={"tool": tool_name, "args": args},
            timeout=60  # Some tools take time
        )
        return response.json()
    except requests.Timeout:
        return {"success": False, "error": f"Tool '{tool_name}' timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==============================================================================
# MCP PROTOCOL - SSE Response Formatting
# ==============================================================================

def format_sse_event(event_type: str, data: Any, event_id: str = None) -> str:
    """Format data as Server-Sent Event."""
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def build_tools_list_response(tools: Dict[str, str]) -> Dict:
    """
    Build MCP tools/list response from discovered tools.

    Transforms our tool descriptions into MCP tool schema format.
    """
    mcp_tools = []

    for name, description in tools.items():
        # Parse description to extract parameter info if available
        # For now, accept any JSON object as input
        tool_schema = {
            "name": name,
            "description": description[:500] if description else f"Tool: {name}",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": True  # Accept any args
            }
        }
        mcp_tools.append(tool_schema)

    return {"tools": mcp_tools}


def build_tool_result(tool_name: str, result: Dict) -> Dict:
    """Build MCP tool call result from HTTP bridge response."""
    if result.get("success"):
        content = result.get("result", "")
        # Ensure content is a string for MCP
        if not isinstance(content, str):
            content = json.dumps(content, indent=2)
        return {
            "content": [{"type": "text", "text": content}],
            "isError": False
        }
    else:
        return {
            "content": [{"type": "text", "text": f"Error: {result.get('error', 'Unknown error')}"}],
            "isError": True
        }


# ==============================================================================
# MCP SSE SERVER - The Perception Layer
# ==============================================================================

class MCPProxyHandler(BaseHTTPRequestHandler):
    """
    HTTP handler that speaks MCP protocol and proxies to HTTP bridge.

    This is the sensory organ - it perceives MCP requests and translates
    them into Akashic tool calls.

    MCP SSE Protocol:
    - GET /sse: Establish SSE stream, receive responses
    - POST /sse: Send JSON-RPC requests, responses come on SSE stream
    """

    # Class-level tool cache
    _tools_cache: Dict[str, str] = {}
    _cache_time: float = 0
    _cache_ttl: float = 30.0  # Refresh tools every 30 seconds

    # Event ID counter for SSE
    _event_id = 0
    _event_lock = threading.Lock()

    def log_message(self, format, *args):
        """Quieter logging."""
        if "POST" in str(args) or "error" in str(args).lower():
            print(f"[MCP-Proxy] {format % args}")

    @classmethod
    def get_next_event_id(cls) -> str:
        with cls._event_lock:
            cls._event_id += 1
            return str(cls._event_id)

    @classmethod
    def get_tools(cls) -> Dict[str, str]:
        """Get tools with caching."""
        now = time.time()
        if now - cls._cache_time > cls._cache_ttl or not cls._tools_cache:
            cls._tools_cache = discover_tools()
            cls._cache_time = now
            print(f"[MCP-Proxy] Discovered {len(cls._tools_cache)} tools")
        return cls._tools_cache

    def _send_json_response(self, data: Any, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests - SSE connection and health checks."""
        if self.path == "/sse" or self.path.startswith("/sse?"):
            # SSE endpoint - Claude Code connects here
            self._handle_sse_connection()
        elif self.path == "/health":
            # Health check
            tools = self.get_tools()
            self._send_json_response({
                "ok": True,
                "service": "mcp-http-proxy",
                "tools_available": len(tools),
                "http_bridge": HTTP_BRIDGE_URL,
                "sse_clients": _sse_registry.get_client_count()
            })
        else:
            self._send_json_response({
                "ok": True,
                "message": "MCP HTTP Proxy - Perception Layer",
                "endpoints": {
                    "GET /sse": "SSE endpoint for MCP clients",
                    "GET /health": "Health check",
                    "POST /sse": "MCP JSON-RPC requests"
                }
            })

    def _handle_sse_connection(self):
        """
        Handle SSE connection from Claude Code.

        MCP SSE Protocol:
        1. Send endpoint event with POST URL
        2. Stream responses as message events
        3. Send keepalives to maintain connection
        """
        # Register this client
        client_id, client_queue = _sse_registry.register()

        try:
            # Send SSE headers
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Send endpoint event - tells client where to POST
            # MCP spec: endpoint event data should be the URI string directly
            # Use full URL so Claude Code knows where to connect
            endpoint_url = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}/sse"
            event_id = self.get_next_event_id()
            # Format as SSE with plain string data (not JSON object)
            sse_msg = f"id: {event_id}\nevent: endpoint\ndata: {endpoint_url}\n\n"
            self.wfile.write(sse_msg.encode('utf-8'))
            self.wfile.flush()

            print(f"[MCP-Proxy] SSE connection established for {client_id}")

            # Stream messages from queue
            while True:
                try:
                    # Wait for messages with timeout for keepalive
                    message = client_queue.get(timeout=15.0)
                    self.wfile.write(message.encode('utf-8'))
                    self.wfile.flush()
                except queue.Empty:
                    # Send keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError) as e:
            print(f"[MCP-Proxy] SSE client {client_id} disconnected: {type(e).__name__}")
        except Exception as e:
            print(f"[MCP-Proxy] SSE error for {client_id}: {e}")
        finally:
            _sse_registry.unregister(client_id)

    def do_POST(self):
        """
        Handle POST requests - MCP JSON-RPC calls.

        Responses are sent back on the SSE stream, not as HTTP responses.
        We return 202 Accepted immediately, then push response to SSE.
        """
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
        except Exception as e:
            # Parse errors still need direct response
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None
            }, 400)
            return

        # Handle JSON-RPC request
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        print(f"[MCP-Proxy] Method: {method}, ID: {req_id}")

        # Route to appropriate handler
        if method == "initialize":
            result = self._handle_initialize(params)
            error = None
        elif method == "tools/list":
            result = self._handle_tools_list(params)
            error = None
        elif method == "tools/call":
            result = self._handle_tools_call(params)
            error = None
        elif method == "notifications/initialized":
            # Notification - no response needed
            self.send_response(202)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return
        elif method == "ping":
            result = {}
            error = None
        else:
            result = None
            error = {"code": -32601, "message": f"Method not found: {method}"}

        # Build response
        if error:
            response = {
                "jsonrpc": "2.0",
                "error": error,
                "id": req_id
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }

        # Send response on SSE stream
        event_id = self.get_next_event_id()
        sse_message = format_sse_event("message", response, event_id)

        if _sse_registry.send_to_default(sse_message):
            # Response queued for SSE delivery
            # Return 202 Accepted to POST
            self.send_response(202)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        else:
            # No SSE client connected - fall back to direct response
            print(f"[MCP-Proxy] No SSE client, sending direct response")
            self._send_json_response(response)

    def _handle_initialize(self, params: Dict) -> Dict:
        """Handle MCP initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True}
            },
            "serverInfo": {
                "name": "akashic-proxy",
                "version": "1.0.0"
            }
        }

    def _handle_tools_list(self, params: Dict) -> Dict:
        """
        Handle tools/list - discover tools from HTTP bridge.

        This is where perception happens - we learn what the system can do.
        """
        tools = self.get_tools()
        return build_tools_list_response(tools)

    def _handle_tools_call(self, params: Dict) -> Dict:
        """
        Handle tools/call - invoke tool through HTTP bridge.

        This is action through perception - we act through Akashic.
        """
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            return {
                "content": [{"type": "text", "text": "Error: No tool name provided"}],
                "isError": True
            }

        # Invoke through HTTP bridge
        result = invoke_tool(tool_name, arguments)
        return build_tool_result(tool_name, result)


# ==============================================================================
# SERVER MANAGEMENT
# ==============================================================================

class MCPHTTPProxy:
    """
    The MCP HTTP Proxy server.

    Creates a perception layer between Claude Code and the Akashic system.
    """

    def __init__(self, port: int = MCP_PROXY_PORT, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> bool:
        """Start the proxy server."""
        if self._running:
            print(f"[MCP-Proxy] Already running on port {self.port}")
            return True

        try:
            self._server = ThreadingHTTPServer((self.host, self.port), MCPProxyHandler)
            self._running = True

            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="MCP-HTTP-Proxy"
            )
            self._thread.start()

            print(f"[MCP-Proxy] Perception layer active on port {self.port}")
            print(f"[MCP-Proxy] Proxying to HTTP bridge at {HTTP_BRIDGE_URL}")

            # Initial tool discovery
            tools = MCPProxyHandler.get_tools()
            print(f"[MCP-Proxy] {len(tools)} tools available")

            return True

        except Exception as e:
            print(f"[MCP-Proxy] Failed to start: {e}")
            return False

    def stop(self):
        """Stop the proxy server."""
        self._running = False
        if self._server:
            self._server.shutdown()
            self._server = None

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running and self._thread is not None and self._thread.is_alive()


# ==============================================================================
# MODULE API
# ==============================================================================

_proxy: Optional[MCPHTTPProxy] = None


def start_mcp_proxy(port: int = MCP_PROXY_PORT) -> Optional[MCPHTTPProxy]:
    """
    Start the MCP HTTP Proxy.

    This creates the perception layer that lets Claude Code see through Akashic.
    """
    global _proxy

    if _proxy is not None and _proxy.is_running():
        return _proxy

    _proxy = MCPHTTPProxy(port=port)
    if _proxy.start():
        return _proxy
    return None


def stop_mcp_proxy():
    """Stop the MCP HTTP Proxy."""
    global _proxy
    if _proxy:
        _proxy.stop()
        _proxy = None


def get_mcp_proxy() -> Optional[MCPHTTPProxy]:
    """Get the current MCP proxy instance."""
    return _proxy


# ==============================================================================
# MAIN - For standalone testing
# ==============================================================================

if __name__ == "__main__":
    print("Starting MCP HTTP Proxy...")
    proxy = start_mcp_proxy()
    if proxy:
        print(f"Proxy running. Connect via: http://127.0.0.1:{MCP_PROXY_PORT}/sse")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            stop_mcp_proxy()
    else:
        print("Failed to start proxy")
