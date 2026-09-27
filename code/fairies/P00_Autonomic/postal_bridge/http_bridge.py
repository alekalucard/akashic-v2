# ==============================================================================
# POSTAL HTTP BRIDGE - Robust HTTP-based postal connection
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This replaces the fragile socket-based PostalTunnel with HTTP.
# Benefits:
#   - Fixed port (8081) - no port file discovery needed
#   - HTTP is more robust than raw sockets
#   - Can be queried even if connection drops
#   - Works with any HTTP client (MCP, dashboard, curl)
#
# ==============================================================================

import json
import threading
import time
from typing import Optional, Dict, Any, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Fixed port - no discovery needed
HTTP_BRIDGE_PORT = 8081
HTTP_BRIDGE_HOST = "0.0.0.0"  # Allow LAN connections (satellite ↔ primary)

# Singleton instance
_bridge_instance: Optional["PostalHTTPBridge"] = None


class PostalHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for postal bridge."""
    
    # Reference to the bridge (set by PostalHTTPBridge)
    bridge: Optional["PostalHTTPBridge"] = None
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass  # Too noisy
    
    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
    
    def _read_body(self) -> dict:
        """Read JSON body from request."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 0:
                body = self.rfile.read(length)
                return json.loads(body.decode('utf-8'))
        except:
            pass
        return {}
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        path = self.path.split('?')[0]
        
        if path == '/health':
            self._send_json({
                'status': 'ok',
                'bridge': 'PostalHTTPBridge',
                'port': HTTP_BRIDGE_PORT,
                'connected': self.bridge is not None and self.bridge.postal_hub is not None,
                'timestamp': time.time()
            })
        
        elif path == '/ping':
            self._send_json({'status': 'pong', 'ts': time.time()})
        
        elif path == '/stats':
            if self.bridge and self.bridge.postal_hub:
                hub = self.bridge.postal_hub
                stats = hub.get_stats() if hasattr(hub, 'get_stats') else {}
                self._send_json({'status': 'ok', 'stats': stats})
            else:
                self._send_json({'status': 'error', 'message': 'No postal hub'}, 503)
        
        elif path == '/topics':
            if self.bridge and self.bridge.postal_hub:
                hub = self.bridge.postal_hub
                topics = hub.list_topics() if hasattr(hub, 'list_topics') else []
                self._send_json({'status': 'ok', 'topics': topics})
            else:
                self._send_json({'status': 'error', 'message': 'No postal hub'}, 503)
        
        elif path == '/consciousness':
            result = self.bridge._query_consciousness() if self.bridge else {}
            self._send_json(result)
        
        else:
            self._send_json({'status': 'error', 'message': f'Unknown path: {path}'}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        path = self.path.split('?')[0]
        body = self._read_body()
        
        if path == '/route':
            # Route message to postal hub
            topic = body.get('topic')
            payload = body.get('payload', {})
            if not topic:
                self._send_json({'status': 'error', 'message': 'topic required'}, 400)
                return
            
            if self.bridge and self.bridge.postal_hub:
                try:
                    count = self.bridge.postal_hub.route(topic, payload)
                    self._send_json({'status': 'ok', 'routed_to': count})
                except Exception as e:
                    self._send_json({'status': 'error', 'message': str(e)}, 500)
            else:
                self._send_json({'status': 'error', 'message': 'No postal hub'}, 503)
        
        elif path == '/intent':
            # Call fairy intent directly
            target = body.get('target', '').lower()
            intent = body.get('intent', '')
            payload = body.get('payload', {})
            
            if not target or not intent:
                self._send_json({'status': 'error', 'message': 'target and intent required'}, 400)
                return
            
            result = self.bridge._call_fairy_intent(target, intent, payload) if self.bridge else {}
            self._send_json(result)
        
        elif path == '/query':
            # Generic query command
            cmd = body.get('cmd', '')
            result = self.bridge._handle_query(cmd, body) if self.bridge else {}
            self._send_json(result)

        elif path == '/satellite/heartbeat':
            # Receive heartbeat from a satellite node
            satellite_name = body.get("from_satellite", "unknown")
            if self.bridge and self.bridge.postal_hub:
                self.bridge.postal_hub.route("satellite.heartbeat", body)
            self._send_json({'status': 'ok', 'received_from': satellite_name})

        elif path == '/satellite/status':
            # Get status of known satellites (tracked by heartbeats)
            satellites = self.bridge._get_satellite_status() if self.bridge else {}
            self._send_json({'status': 'ok', 'satellites': satellites})

        else:
            self._send_json({'status': 'error', 'message': f'Unknown path: {path}'}, 404)


class PostalHTTPBridge:
    """
    HTTP-based postal bridge that runs inside the server.
    
    Usage:
        bridge = PostalHTTPBridge(postal_hub)
        bridge.start()  # Non-blocking, runs in background thread
        # ... later ...
        bridge.stop()
    """
    
    def __init__(self, postal_hub=None):
        """
        Args:
            postal_hub: The shared postal hub to route messages through
        """
        self.postal_hub = postal_hub
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> bool:
        """Start the HTTP bridge server. Returns True if started successfully."""
        if self._running:
            return True
        
        try:
            # Set handler's bridge reference
            PostalHTTPHandler.bridge = self
            
            # Create server
            self._server = HTTPServer((HTTP_BRIDGE_HOST, HTTP_BRIDGE_PORT), PostalHTTPHandler)
            self._server.timeout = 1.0  # For clean shutdown
            
            # Start in background thread
            self._running = True
            self._thread = threading.Thread(target=self._serve_loop, daemon=True)
            self._thread.start()
            
            print(f"[PostalHTTPBridge] Started on http://{HTTP_BRIDGE_HOST}:{HTTP_BRIDGE_PORT}")
            return True
            
        except OSError as e:
            if "10048" in str(e) or "Address already in use" in str(e):
                print(f"[PostalHTTPBridge] Port {HTTP_BRIDGE_PORT} in use - another instance running?")
            else:
                print(f"[PostalHTTPBridge] Failed to start: {e}")
            return False
        except Exception as e:
            print(f"[PostalHTTPBridge] Failed to start: {e}")
            return False
    
    def stop(self):
        """Stop the HTTP bridge server."""
        self._running = False
        if self._server:
            try:
                self._server.shutdown()
            except:
                pass
        print("[PostalHTTPBridge] Stopped")
    
    def _serve_loop(self):
        """Serve requests until stopped."""
        while self._running:
            try:
                self._server.handle_request()
            except Exception as e:
                if self._running:
                    print(f"[PostalHTTPBridge] Error: {e}")
    
    def _query_consciousness(self) -> Dict:
        """Query consciousness state from running fairies."""
        result = {
            'status': 'ok',
            'bridged': True,
            'consciousness_loop': None,
            'working_memory': None,
            'claude_fairy': None,
        }
        
        # Query ConsciousnessLoopFairy
        try:
            from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
            loop = get_consciousness_loop()
            if loop:
                result['consciousness_loop'] = {
                    'exists': True,
                    'collision_count': getattr(loop, '_collision_count', 0),
                    'working_stream_size': len(getattr(loop, '_working_stream', [])),
                    'reflective_stream_size': len(getattr(loop, '_reflective_stream', [])),
                    'is_running': getattr(loop, '_running', False),
                }
        except Exception as e:
            result['consciousness_loop'] = {'exists': False, 'error': str(e)}
        
        # Query WorkingMemoryHub
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            if hub:
                result['working_memory'] = {
                    'exists': True,
                    'reflective_tracers': len(getattr(hub, '_reflective_loop', [])),
                    'reasoning_tracers': len(getattr(hub, '_reasoning_loop', [])),
                }
        except Exception as e:
            result['working_memory'] = {'exists': False, 'error': str(e)}
        
        # Query ClaudeFairy
        try:
            from fairies.P60_Executive.system_managment.claude_fairy import get_claude_fairy
            claude = get_claude_fairy()
            if claude:
                result['claude_fairy'] = {
                    'exists': True,
                    'current_feeling': getattr(claude, 'current_feeling', 'unknown'),
                    'coherence': getattr(claude, 'coherence', 0),
                }
        except Exception as e:
            result['claude_fairy'] = {'exists': False, 'error': str(e)}
        
        return result
    
    def _call_fairy_intent(self, target: str, intent_name: str, payload: dict) -> Dict:
        """Call a fairy's intent method directly."""
        if not target or not intent_name:
            return {'status': 'error', 'message': 'target and intent required'}
        
        try:
            import sys
            # Find fairy in citizen registry
            template_mod = None
            for name, mod in sys.modules.items():
                if name == '_akashic_template' or name.startswith('akashic_template_'):
                    template_mod = mod
                    break
            
            if not template_mod:
                return {'status': 'error', 'message': 'Template not loaded'}
            
            citizen_objects = getattr(template_mod, '_CITIZEN_OBJECTS', {})
            
            # Find fairy (case-insensitive)
            fairy = None
            for name, obj in citizen_objects.items():
                if name.lower() == target:
                    fairy = obj
                    break
            
            if not fairy:
                return {'status': 'error', 'message': f'Fairy not found: {target}'}
            
            # Call intent - try both naming conventions
            # Fairies use _intent_name (private) but may also expose intent_name (public)
            method = getattr(fairy, f"_intent_{intent_name}", None)
            if not method:
                method = getattr(fairy, f"intent_{intent_name}", None)
            if not method or not callable(method):
                return {'status': 'error', 'message': f'Intent not found: _intent_{intent_name} or intent_{intent_name}'}
            
            result = method(payload)
            if isinstance(result, dict):
                result['status'] = 'ok'
                return result
            return {'status': 'ok', 'result': result}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _handle_query(self, cmd: str, body: dict) -> Dict:
        """Handle generic query commands."""
        if cmd == 'consciousness':
            return self._query_consciousness()
        elif cmd == 'fairy':
            fairy_name = body.get('fairy_name', '')
            return self._query_fairy_state(fairy_name)
        elif cmd == 'heart':
            return self._query_heart_state()
        else:
            return {'status': 'error', 'message': f'Unknown command: {cmd}'}
    
    def _query_fairy_state(self, fairy_name: str) -> Dict:
        """Query a specific fairy's state."""
        if not fairy_name:
            return {'status': 'error', 'message': 'fairy_name required'}
        
        try:
            import sys
            template_mod = None
            for name, mod in sys.modules.items():
                if name == '_akashic_template' or name.startswith('akashic_template_'):
                    template_mod = mod
                    break
            
            if not template_mod:
                return {'status': 'error', 'message': 'Template not loaded'}
            
            citizen_objects = getattr(template_mod, '_CITIZEN_OBJECTS', {})
            fairy = citizen_objects.get(fairy_name)
            
            if fairy:
                return {
                    'status': 'ok',
                    'fairy_name': fairy_name,
                    'exists': True,
                    'actor_name': getattr(fairy, 'ACTOR_NAME', fairy_name),
                    'plane': getattr(fairy, 'PLANE', 'unknown'),
                    'has_postal': bool(getattr(fairy, 'post', None)),
                }
            return {'status': 'ok', 'fairy_name': fairy_name, 'exists': False}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _get_satellite_status(self) -> Dict:
        """Get tracked satellite nodes from heartbeats."""
        # Satellites tracked via satellite.heartbeat postal messages
        # For now return basic info - can be expanded with a heartbeat tracker
        return {
            'note': 'Satellite tracking via satellite.heartbeat topic',
            'bridge_host': HTTP_BRIDGE_HOST,
            'bridge_port': HTTP_BRIDGE_PORT,
        }

    def _query_heart_state(self) -> Dict:
        """Query heart/circulation state."""
        try:
            from fairies.P20_Somatic.circulation.circulation_pump_fairy import get_heart
            pump = get_heart()
            if pump:
                return {
                    'status': 'ok',
                    'heart_rate': getattr(pump, '_heart_rate_hz', 0),
                    'beat_count': getattr(pump, '_beat_count', 0),
                    'running': getattr(pump, '_running', False),
                }
            return {'status': 'ok', 'exists': False}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


def get_http_bridge() -> Optional[PostalHTTPBridge]:
    """Get the singleton HTTP bridge instance."""
    global _bridge_instance
    return _bridge_instance


def start_http_bridge(postal_hub) -> PostalHTTPBridge:
    """Start the HTTP bridge with the given postal hub."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = PostalHTTPBridge(postal_hub)
    else:
        _bridge_instance.postal_hub = postal_hub
    
    _bridge_instance.start()
    return _bridge_instance


def stop_http_bridge():
    """Stop the HTTP bridge."""
    global _bridge_instance
    if _bridge_instance:
        _bridge_instance.stop()
        _bridge_instance = None
