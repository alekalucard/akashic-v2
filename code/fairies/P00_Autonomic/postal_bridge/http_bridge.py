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
# 2026-09-30 (Nous, security fix her_8081): this port accepted ANY message from ANY host, including one
# that made her believe Ace spoke. Now a request that calls /intent, routes a chat-class topic, claims who
# spoke, or comes from a browser must carry a valid X-Akashic-Auth header (HMAC with the key in
# ~/.akashic/bridge_8081.key -- see bridge_auth.py). No CORS any more. Every refusal prints one line;
# the first request of each (ip, path, topic, signed?) prints one census line.
#
# ==============================================================================

import json
import threading
import time
from typing import Optional, Dict, Any, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# 2026-09-30 (Nous, her_8081): the shared-secret rule lives in bridge_auth.py beside this file.
try:
    from . import bridge_auth as _auth
except Exception:                      # loaded outside the package (tests, tools): load the file beside us
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_akashic_bridge_auth", str(Path(__file__).resolve().with_name("bridge_auth.py")))
    _auth = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_auth)

# Fixed port - no discovery needed
HTTP_BRIDGE_PORT = 8081
HTTP_BRIDGE_HOST = "0.0.0.0"  # Allow LAN connections (satellite ↔ primary)

# Singleton instance
_bridge_instance: Optional["PostalHTTPBridge"] = None

# 2026-09-30 her_8081: auth state
_VERIFIER = _auth.Verifier()
_POST_PATHS = ('/route', '/intent', '/query', '/satellite/heartbeat', '/satellite/status')
_LOG_LOCK = threading.Lock()
_REFUSAL_LOG = {}       # (ip, path, reason class) -> [last print time, suppressed count]
_CENSUS = set()         # (ip, path, topic, signed) already announced
_CENSUS_MAX = 256


def _ascii(s, n=80):
    """ASCII only, bounded: a diagnostic must never be the failure (her console is cp1252)."""
    s = str(s)
    return ''.join(c if 32 <= ord(c) < 127 else '?' for c in s[:n]) + ('...' if len(s) > n else '')


def _topic_of(path, body):
    if not isinstance(body, dict):
        return ''
    if path == '/route':
        return _ascii(body.get('topic', ''))
    if path == '/intent':
        return _ascii('%s.%s' % (body.get('target', ''), body.get('intent', '')))
    return ''


def _refused(ip, path, body, reasons):
    """One line per refusal, at most one per (ip, path, reason class) every 10 s; never the payload."""
    now = time.time()
    key = (ip, path, str(reasons[0]).split(' (')[0][:40])
    with _LOG_LOCK:
        rec = _REFUSAL_LOG.get(key)
        if rec is not None and now - rec[0] < 10.0:
            rec[1] += 1
            return
        suppressed = rec[1] if rec is not None else 0
        if len(_REFUSAL_LOG) > 512:
            _REFUSAL_LOG.clear()
        _REFUSAL_LOG[key] = [now, 0]
    try:
        print("[PostalHTTPBridge] REFUSED POST %s from %s topic=%r: %s%s" % (
            path, _ascii(ip, 45), _topic_of(path, body), _ascii('; '.join(str(r) for r in reasons), 240),
            (" [+%d more like this]" % suppressed) if suppressed else ""), flush=True)
    except Exception:
        pass


def _census(ip, path, body, signed):
    """The census the design asked for: the first request of each (ip, path, topic, signed) prints once."""
    key = (ip, path, _topic_of(path, body), bool(signed))
    with _LOG_LOCK:
        if key in _CENSUS or len(_CENSUS) >= _CENSUS_MAX:
            return
        _CENSUS.add(key)
        full = len(_CENSUS) >= _CENSUS_MAX
    try:
        print("[PostalHTTPBridge] census: first %s POST %s topic=%r from %s%s" % (
            'SIGNED' if signed else 'open', path, key[2], _ascii(ip, 45),
            ' (census table full; no more census lines)' if full else ''), flush=True)
    except Exception:
        pass


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
        self.end_headers()                      # 2026-09-30 her_8081: no CORS header any more
        self.wfile.write(body)
    
    def _read_raw(self) -> bytes:
        """The request body exactly as sent (the signature covers these bytes)."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 0:
                return self.rfile.read(length)
        except Exception:
            pass
        return b''
    
    @staticmethod
    def _decode(raw: bytes) -> dict:
        """JSON object -> dict; anything else -> {} (as before, a bad body becomes {})."""
        try:
            if raw:
                obj = json.loads(raw.decode('utf-8'))
                if isinstance(obj, dict):
                    return obj
        except Exception:
            pass
        return {}
    
    def _read_body(self) -> dict:
        """Read JSON body from request."""
        return self._decode(self._read_raw())
    
    def _client_ip(self) -> str:
        try:
            return str(self.client_address[0])
        except Exception:
            return '?'
    
    def _authorize(self, path: str, raw: bytes, body: dict) -> bool:
        """True = go ahead. False = a 403 was sent. A request with a valid X-Akashic-Auth is trusted; an
        unsigned one only when bridge_auth.privileged_reasons() finds nothing (no /intent, no chat topic,
        no claim of who spoke, no browser headers). A present but invalid header is always refused."""
        values = self.headers.get_all(_auth.HEADER) or []
        signed = False
        if values:
            if len(values) != 1:
                ok, why = False, 'more than one auth header'
            else:
                ok, why = _VERIFIER.verify(values[0], 'POST', self.path, raw)
            if not ok:
                _refused(self._client_ip(), path, body, ['bad auth: ' + why])
                self._send_json({'status': 'error', 'message': 'forbidden: bad auth (%s)' % why}, 403)
                return False
            signed = True
        else:
            # 2026-10-06 senses_hub: the door scopes the 8 open topics to the satellite's address
            reasons = _auth.privileged_reasons('POST', path, self.headers, body, client_ip=self._client_ip())
            if reasons:
                _refused(self._client_ip(), path, body, reasons)
                self._send_json({'status': 'error', 'message': 'forbidden: %s' % '; '.join(reasons[:3]),
                                 'auth': '%s %s required' % (_auth.HEADER, _auth.VERSION)}, 403)
                return False
        _census(self._client_ip(), path, body, signed)
        return True
    
    def do_OPTIONS(self):
        """2026-09-30 her_8081: no CORS. No browser page is a legitimate sender, so preflights are refused."""
        self._send_json({'status': 'error', 'message': 'CORS is not offered on this port'}, 403)
    
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
        """Handle POST requests. 2026-09-30 her_8081: checked by _authorize() before anything is routed."""
        path = self.path.split('?')[0]
        raw = self._read_raw()
        body = self._decode(raw)
        if path not in _POST_PATHS:
            self._send_json({'status': 'error', 'message': f'Unknown path: {path}'}, 404)
            return
        if not self._authorize(path, raw, body):
            return
        
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
            if _VERIFIER.key_present():
                print(f"[PostalHTTPBridge] auth: key present -- /intent, chat topics, speaker claims and browser "
                      f"requests need {_auth.HEADER} {_auth.VERSION}")
            else:
                print(f"[PostalHTTPBridge] auth: NO KEY at {_ascii(_auth.KEY_FILE, 120)} -- those requests are ALL "
                      f"REFUSED (open topics still work). Run apply_her_8081.py to create it.")
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
