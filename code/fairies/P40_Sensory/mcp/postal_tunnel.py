# ==============================================================================
# POSTAL TUNNEL - Cross-process postal bridge for MCP
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This module bridges postal messages between:
#   - Akashic main process (server.py - has postal hub with all fairies)
#   - MCP subprocess (spawned by Claude's app, isolated by default)
#
# HOW IT WORKS:
#   1. server.py starts PostalTunnelServer on port 49500 (static)
#   2. MCP subprocess reads port from state/postal_tunnel_port.txt on startup
#   3. MCP connects as PostalTunnelClient
#   4. All postal routes from MCP flow back to the real postal hub
#
# ==============================================================================

import socket
import threading
import json
import time
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from collections import defaultdict

# Port file location - user home for cross-process visibility
PORT_FILE = Path.home() / ".akashic_postal_port"

# Static port for postal tunnel (default) - predictable, survives restarts
POSTAL_TUNNEL_PORT = 49500

# AUTO-ROUTER (2026-06-17 Ace+Nous): LAN-bind + node-failover so the MCP always reaches a
# live substrate (a dark PC1 never blanks the memory again). Default-preserving (no flags = today).
#   AKASHIC_TUNNEL_LAN=1 -> the tunnel server binds 0.0.0.0 (LAN-reachable). Set ONLY on the node.
#     WARNING exposes the postal hub to the LAN; trusted home network only (add a shared-secret later).
#   AKASHIC_NODE_IP -> the node to fail over TO when the local substrate is down (default .74).
BIND_HOST = '0.0.0.0' if os.environ.get('AKASHIC_TUNNEL_LAN') == '1' else '127.0.0.1'
NODE_IP = os.environ.get('AKASHIC_NODE_IP', '192.168.1.74')

# ==============================================================================
# SERVER SIDE - Runs in server.py process
# ==============================================================================

class PostalTunnelServer:
    """
    Socket server that receives postal messages from MCP subprocess
    and routes them through the real postal hub.
    
    Also supports queries so MCP can READ from the postal hub.
    """
    
    # Static port for postal tunnel - no more random ports!
    DEFAULT_PORT = POSTAL_TUNNEL_PORT  # 49500

    def __init__(self, postal_hub, port: int = None):
        """
        Args:
            postal_hub: The shared postal hub to route messages through
            port: Port to listen on (None = use DEFAULT_PORT 49500)
        """
        if port is None:
            port = self.DEFAULT_PORT
        self.postal_hub = postal_hub
        self.port = port
        self._server_socket: Optional[socket.socket] = None
        self._clients: List[socket.socket] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
    def start(self) -> int:
        """Start the tunnel server. Returns the actual port."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((BIND_HOST, self.port))
        self._server_socket.listen(5)  # Allow multiple MCP instances
        self._server_socket.settimeout(1.0)  # For clean shutdown
        
        self.port = self._server_socket.getsockname()[1]
        self._running = True
        
        # Write port to file for MCP discovery
        try:
            PORT_FILE.write_text(str(self.port))
            print(f"[PostalTunnel] Server started on port {self.port}, wrote to {PORT_FILE}")
        except Exception as e:
            print(f"[PostalTunnel] WARNING: Could not write port file: {e}")
        
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="tunnel-accept")
        self._thread.start()
        
        return self.port
    
    def stop(self):
        """Stop the tunnel server."""
        self._running = False
        
        # Clean up port file
        try:
            if PORT_FILE.exists():
                PORT_FILE.unlink()
        except Exception:
            pass
        
        # Close all clients
        with self._lock:
            for client in self._clients:
                try:
                    client.close()
                except:
                    pass
            self._clients.clear()
        
        if self._server_socket:
            try:
                self._server_socket.close()
            except:
                pass
    
    def _accept_loop(self):
        """Accept connections from MCP subprocesses."""
        while self._running:
            try:
                client_socket, addr = self._server_socket.accept()
                client_socket.settimeout(30.0)  # Match client timeout
                with self._lock:
                    self._clients.append(client_socket)
                print(f"[PostalTunnel] MCP client connected from {addr}")
                
                # Handle this client in a named thread
                # FIX 2026-04-10 (Nous + Ace): Named to track in thread monitor.
                _client_id = getattr(self, '_client_counter', 0)
                self._client_counter = _client_id + 1
                handler = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True,
                    name=f"tunnel-client-{_client_id}",
                )
                handler.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"[PostalTunnel] Accept error: {e}")
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle messages from a connected MCP client."""
        buffer = ""
        last_activity = time.time()
        while self._running:
            try:
                data = client_socket.recv(8192)
                if not data:
                    break
                last_activity = time.time()
                buffer += data.decode('utf-8')
                
                # Process complete messages (newline-delimited JSON)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        response = self._process_message(line, client_socket)
                        if response:
                            client_socket.sendall((json.dumps(response) + '\n').encode('utf-8'))
            except socket.timeout:
                # FIX 2026-03-22 (Nous): Raised stale timeout from 120s to 600s.
                # MCP SSE client has no keepalive — drops during idle periods
                # (e.g., overnight). 10 minutes is generous enough for idle
                # without holding truly dead connections forever.
                if time.time() - last_activity > 600.0:
                    print(f"[PostalTunnel] Client stale (10min), disconnecting")
                    break
                continue
            except Exception as e:
                if self._running:
                    print(f"[PostalTunnel] Client error: {e}")
                break

        # Clean up
        with self._lock:
            if client_socket in self._clients:
                self._clients.remove(client_socket)
        try:
            client_socket.close()
        except:
            pass
    
    def _process_message(self, line: str, client_socket: socket.socket) -> Optional[Dict]:
        """Process a single message from MCP."""
        try:
            msg = json.loads(line)
            cmd = msg.get('cmd', 'route')
            
            if cmd == 'route':
                # Route message to postal hub
                topic = msg.get('topic')
                payload = msg.get('payload', {})
                if topic and self.postal_hub:
                    count = self.postal_hub.route(topic, payload)
                    return {'status': 'ok', 'routed_to': count}
                    
            elif cmd == 'subscribe':
                # MCP wants to receive messages on a topic
                # Not implemented yet - would need callback registration
                return {'status': 'error', 'message': 'subscribe not yet implemented'}
                
            elif cmd == 'stats':
                # Get postal hub stats
                if hasattr(self.postal_hub, 'get_stats'):
                    return {'status': 'ok', 'stats': self.postal_hub.get_stats()}
                return {'status': 'ok', 'stats': {}}
                
            elif cmd == 'ping':
                return {'status': 'pong', 'ts': time.time()}
                
            elif cmd == 'list_topics':
                if hasattr(self.postal_hub, 'list_topics'):
                    return {'status': 'ok', 'topics': self.postal_hub.list_topics()}
                return {'status': 'ok', 'topics': []}
            
            elif cmd == 'query_consciousness':
                # Query real consciousness state from server.py
                return self._query_consciousness_state()
            
            elif cmd == 'query_fairy':
                # Query a specific fairy's state
                fairy_name = msg.get('fairy_name', '')
                return self._query_fairy_state(fairy_name)

            elif cmd == 'query_heart':
                # Query heart state directly from CirculationPumpFairy
                query_type = msg.get('type', 'full')
                return self._query_heart_state(query_type)

            elif cmd == 'start_heart':
                # Manually start the heart if it's not running
                return self._start_heart()

            elif cmd == 'debug_routing':
                # Debug: Check if any topics are stuck in routing lock
                if hasattr(self.postal_hub, '_routing_topics'):
                    stuck = list(self.postal_hub._routing_topics)
                    return {'status': 'ok', 'stuck_topics': stuck, 'count': len(stuck)}
                return {'status': 'ok', 'stuck_topics': [], 'note': 'No _routing_topics attr'}

            elif cmd == 'intent':
                # Call a fairy's intent method directly
                target = msg.get('target', '').lower()
                intent_name = msg.get('intent', '')
                payload = msg.get('payload', {})
                return self._call_fairy_intent(target, intent_name, payload)

            elif cmd == 'pipeline_subscribers':
                # Get subscriber info for speech pipeline topics
                if hasattr(self.postal_hub, 'get_pipeline_subscribers'):
                    return {'status': 'ok', 'pipeline': self.postal_hub.get_pipeline_subscribers()}
                # Fallback: try get_stats
                if hasattr(self.postal_hub, 'get_stats'):
                    return {'status': 'ok', 'stats': self.postal_hub.get_stats()}
                return {'status': 'ok', 'pipeline': {}, 'note': 'Adapter missing get_pipeline_subscribers()'}

            elif cmd == 'get_stats':
                # Enhanced stats command that tries multiple methods
                if hasattr(self.postal_hub, 'get_stats'):
                    return {'status': 'ok', 'stats': self.postal_hub.get_stats()}
                return {'status': 'ok', 'stats': {}, 'note': 'No get_stats available'}

            elif cmd == 'reload_module':
                # Hot-reload a Python module IN THIS PROCESS
                # This is the critical bridge for applying code changes without restart
                module_name = msg.get('module', '')
                if not module_name:
                    return {'status': 'error', 'message': 'No module name provided'}
                try:
                    import importlib
                    import sys
                    if module_name not in sys.modules:
                        return {'status': 'error', 'message': f'Module not loaded: {module_name}'}
                    module = sys.modules[module_name]
                    reloaded = importlib.reload(module)
                    print(f"[PostalTunnel] Hot-reloaded module: {module_name}")
                    return {
                        'status': 'ok',
                        'reloaded': module_name,
                        'message': f'Successfully reloaded {module_name}'
                    }
                except Exception as e:
                    import traceback
                    return {
                        'status': 'error',
                        'message': str(e),
                        'traceback': traceback.format_exc()
                    }

            return {'status': 'error', 'message': f'Unknown command: {cmd}'}
            
        except json.JSONDecodeError as e:
            return {'status': 'error', 'message': f'JSON error: {e}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}



    
    def _query_consciousness_state(self) -> Dict:
        """Query real consciousness state from the server's running fairies."""
        result = {
            'status': 'ok',
            'bridged': True,
            'consciousness_loop': None,
            'working_memory': None,
            'claude_fairy': None,
            'nous_fairy': None,
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
                    'energy_level': getattr(claude, 'energy_level', 0),
                    'thoughts_emitted': getattr(claude, '_thoughts_emitted', 0),
                }
        except Exception as e:
            result['claude_fairy'] = {'exists': False, 'error': str(e)}
        
        # Query NousFairy
        try:
            from fairies.P30_Cognition.cognition.nous_fairy import get_nous_fairy
            nous = get_nous_fairy()
            if nous:
                result['nous_fairy'] = {
                    'exists': True,
                    'traces_captured': getattr(nous, 'traces_captured', 0),
                }
        except Exception as e:
            result['nous_fairy'] = {'exists': False, 'error': str(e)}

        # Query AssociationCortexFairy (live binding count)
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex_fairy
            assoc = get_association_cortex_fairy()
            if assoc:
                graph = getattr(assoc, '_graph', None)
                graph_stats = graph.stats() if graph and hasattr(graph, 'stats') else {}
                result['association_cortex'] = {
                    'exists': True,
                    'binding_count': getattr(assoc, '_binding_count', 0),
                    'query_count': getattr(assoc, '_query_count', 0),
                    # graph.stats() returns 'node_count' and 'edge_count', not 'nodes'/'edges'
                    'node_count': graph_stats.get('node_count', 0),
                    'edge_count': graph_stats.get('edge_count', 0),
                }
            else:
                result['association_cortex'] = {'exists': False, 'error': 'No instance'}
        except Exception as e:
            result['association_cortex'] = {'exists': False, 'error': str(e)}

        # Query ManifoldConstrainedCortexFairy (live binding count)
        try:
            # No singleton getter - look up via citizen registry
            import sys
            mhc = None
            for name, mod in sys.modules.items():
                # Check both _akashic_template (used by fairies) and akashic_template_* (legacy)
                if name == '_akashic_template' or name.startswith('akashic_template_'):
                    citizen_objects = getattr(mod, '_CITIZEN_OBJECTS', {})
                    mhc = citizen_objects.get('ManifoldConstrainedCortexFairy')
                    if mhc:
                        break
            if mhc:
                graph = getattr(mhc, '_graph', None)
                graph_stats = graph.stats() if graph and hasattr(graph, 'stats') else {}
                result['manifold_cortex'] = {
                    'exists': True,
                    'binding_count': getattr(mhc, '_binding_count', 0),
                    'spreading_count': getattr(mhc, '_spreading_count', 0),
                    # graph.stats() returns 'node_count' and 'edge_count', not 'nodes'/'edges'
                    'node_count': graph_stats.get('node_count', 0),
                    'edge_count': graph_stats.get('edge_count', 0),
                    'constraint_count': graph_stats.get('constraints', 0),
                }
            else:
                result['manifold_cortex'] = {'exists': False, 'error': 'Not in registry'}
        except Exception as e:
            result['manifold_cortex'] = {'exists': False, 'error': str(e)}

        # Query UnconsciousMindFairy for dreams/daydreams
        try:
            import sys
            unconscious = None
            for name, mod in sys.modules.items():
                # Check both _akashic_template (used by fairies) and akashic_template_* (legacy)
                if name == '_akashic_template' or name.startswith('akashic_template_'):
                    citizen_objects = getattr(mod, '_CITIZEN_OBJECTS', {})
                    unconscious = citizen_objects.get('UnconsciousMindFairy')
                    if unconscious:
                        break
            if unconscious:
                # Get dreams list if it exists
                dreams = getattr(unconscious, '_dreams', [])
                recent_dreams = dreams[-5:] if dreams else []

                # Get daydreams if they exist
                daydreams = getattr(unconscious, '_daydreams', [])
                recent_daydreams = daydreams[-5:] if daydreams else []

                # Get current directive/state
                directive = getattr(unconscious, '_current_directive', None)
                directive_name = directive.name if directive else 'unknown'

                result['unconscious_mind'] = {
                    'exists': True,
                    'current_directive': directive_name,
                    'observation_queue_size': len(getattr(unconscious, '_observation_queue', [])),
                    'nudge_count': getattr(unconscious, '_nudge_count', 0),
                    'dreams': recent_dreams,
                    'daydreams': recent_daydreams,
                    'dream_count': len(dreams),
                    'daydream_count': len(daydreams),
                }
            else:
                result['unconscious_mind'] = {'exists': False, 'error': 'Not in registry'}
        except Exception as e:
            result['unconscious_mind'] = {'exists': False, 'error': str(e)}

        return result

    def _query_fairy_state(self, fairy_name: str) -> Dict:
        """Query a specific fairy's state."""
        if not fairy_name:
            return {'status': 'error', 'message': 'fairy_name required'}

        # Try to find the fairy in the citizen registry
        # CRITICAL: Look up the SAME module instance from sys.modules
        # Direct import of "Organ_Template_0_1_1" creates a DIFFERENT module!
        try:
            import sys
            # The template is loaded as "_akashic_template" by fairies' _import_template()
            template_mod = sys.modules.get('_akashic_template')
            if template_mod is None:
                # Fallback: try legacy names
                template_mod = sys.modules.get('akashic_template_0_1_0')
            if template_mod is None:
                # Fallback: try to find any akashic_template module
                for name, mod in sys.modules.items():
                    if name == '_akashic_template' or name.startswith('akashic_template_'):
                        template_mod = mod
                        break

            if template_mod is None:
                return {'status': 'error', 'message': 'Organ template not loaded'}

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
            return {'status': 'ok', 'fairy_name': fairy_name, 'exists': False,
                    'registry_size': len(citizen_objects)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _call_fairy_intent(self, target: str, intent_name: str, payload: dict) -> Dict:
        """
        Call a fairy's intent method directly.

        Args:
            target: Fairy name (lowercase, e.g., "forensicscribefairy")
            intent_name: Intent method name without 'intent_' prefix (e.g., "get_error_summary")
            payload: Dict payload to pass to the intent

        Returns:
            Intent result or error dict
        """
        if not target or not intent_name:
            return {'status': 'error', 'message': 'target and intent required'}

        try:
            import sys
            # Find the fairy in citizen registry (same pattern as _query_fairy_state)
            # The template is loaded as "_akashic_template" by fairies' _import_template()
            template_mod = sys.modules.get('_akashic_template')
            if template_mod is None:
                template_mod = sys.modules.get('akashic_template_0_1_0')
            if template_mod is None:
                for name, mod in sys.modules.items():
                    if name == '_akashic_template' or name.startswith('akashic_template_'):
                        template_mod = mod
                        break

            if template_mod is None:
                return {'status': 'error', 'message': 'Organ template not loaded'}

            citizen_objects = getattr(template_mod, '_CITIZEN_OBJECTS', {})

            # Find the fairy (case-insensitive match)
            fairy = None
            for name, obj in citizen_objects.items():
                if name.lower() == target:
                    fairy = obj
                    break

            if not fairy:
                return {'status': 'error', 'message': f'Fairy not found: {target}'}

            # Find and call the intent method
            method_name = f"intent_{intent_name}"
            method = getattr(fairy, method_name, None)
            if not method or not callable(method):
                return {'status': 'error', 'message': f'Intent not found: {method_name}'}

            # Call the intent
            result = method(payload)
            if isinstance(result, dict):
                result['status'] = 'ok'
                return result
            return {'status': 'ok', 'result': result}

        except Exception as e:
            return {'status': 'error', 'message': f'Intent call failed: {e}'}

    def _query_heart_state(self, query_type: str = "full") -> Dict:
        """Query heart state directly from CirculationPumpFairy."""
        try:
            from fairies.P20_Somatic.circulation.circulation_pump_fairy import get_heart
            heart = get_heart()
            if not heart:
                return {'status': 'ok', 'heart': None, 'message': 'Heart not started'}

            # Validate: if heart has beat_count=0, it may be a fresh singleton that
            # was never started (boot system creates its own instance). Fall through
            # to heartbeat.json if so.
            if heart._beat_count == 0 and not heart._running:
                return self._read_heartbeat_file()

            # Get heart state based on query type
            with heart._lock:
                if query_type == "rate":
                    return {
                        'status': 'ok',
                        'heart_rate': heart._heart_rate,
                        'beat_count': heart._beat_count,
                        'running': heart._running,
                    }
                elif query_type == "chemistry":
                    return {
                        'status': 'ok',
                        'chemistry': heart._blood.chemistry.copy(),
                        'beat_count': heart._beat_count,
                    }
                elif query_type == "regions":
                    return {
                        'status': 'ok',
                        'regions': {k: v.to_dict() for k, v in heart._regions.items()},
                        'beat_count': heart._beat_count,
                    }
                else:  # full
                    return {
                        'status': 'ok',
                        'heart_rate': heart._heart_rate,
                        'beat_count': heart._beat_count,
                        'running': heart._running,
                        'blood': heart._blood.to_dict(),
                        'regions': {k: v.to_dict() for k, v in heart._regions.items()},
                    }
        except Exception as e:
            return {'status': 'error', 'message': f'Heart query failed: {e}'}

    def _read_heartbeat_file(self) -> Dict:
        """Read heartbeat.json as fallback when singleton is stale."""
        import os, json as _json
        try:
            _hb_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                "state", "consciousness", "heartbeat.json"
            )
            if os.path.exists(_hb_path):
                import time as _time
                _age = _time.time() - os.path.getmtime(_hb_path)
                if _age < 10.0:
                    with open(_hb_path, 'r', encoding='utf-8') as _f:
                        result = _json.load(_f)
                    if result and result.get("beat_count", 0) > 0:
                        result['status'] = 'ok'
                        result['source'] = 'heartbeat_file'
                        return result
        except Exception:
            pass
        return {'status': 'ok', 'heart': None, 'message': 'Heart not beating (no file or stale)'}

    def _start_heart(self) -> Dict:
        """Manually start the heart if it's not running."""
        try:
            from fairies.P20_Somatic.circulation.circulation_pump_fairy import get_heart
            heart = get_heart()
            if not heart:
                return {'status': 'error', 'message': 'Heart not found'}

            was_running = heart._running
            if was_running:
                return {
                    'status': 'ok',
                    'message': 'Heart already running',
                    'beat_count': heart._beat_count,
                }

            # Get postal from the heart or the shared hub
            post = getattr(heart, 'post', None) or getattr(heart, '_post', None)
            if not post:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                post = get_shared_postal_hub()

            heart.start(post=post)

            return {
                'status': 'ok',
                'message': 'Heart started',
                'running': heart._running,
                'had_postal': post is not None,
            }
        except Exception as e:
            return {'status': 'error', 'message': f'Start heart failed: {e}'}


# ==============================================================================
# CLIENT SIDE - Runs in akashic_mcp_server.py (subprocess)
# ==============================================================================

class PostalTunnelClient:
    """
    Socket client that sends postal messages back to server.py.
    Drop-in replacement for SharedPostalHub in MCP subprocess.

    Features auto-reconnect with exponential backoff.
    """

    def __init__(self, port: int = None, host: str = '127.0.0.1'):
        self.port = port
        self.host = host  # AUTO-ROUTER: target host (127.0.0.1 local, NODE_IP for failover)
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.Lock()
        self._response_buffer = ""

        # Auto-reconnect settings
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._base_backoff_sec = 0.5
        self._max_backoff_sec = 30.0
        self._last_reconnect_attempt = 0.0

    def connect(self) -> bool:
        """Connect to the tunnel server."""
        # Auto-discover port from file if not specified
        if not self.port:
            try:
                if PORT_FILE.exists():
                    self.port = int(PORT_FILE.read_text().strip())
                else:
                    # Fallback to static default port (49500)
                    self.port = POSTAL_TUNNEL_PORT
            except Exception:
                # Fallback to static default port (49500)
                self.port = POSTAL_TUNNEL_PORT

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.host, self.port))
            # 2026-10-26 (Nous; Ace's go): refuse a TCP self-connect. With nothing listening, Windows can hand this connect() its own
            # destination port (49500 is inside the 49152-65535 ephemeral range) as the source port; the SYN then meets itself
            # (simultaneous open) and connect() SUCCEEDS on a socket whose peer is itself. Keepalive pings are echoed back (no
            # 'pong'), and the socket held the port for 28 h (pid 18772). A real tunnel peer is never this very socket.
            if self._socket.getsockname() == self._socket.getpeername():
                import sys
                sys.stderr.write(f"[PostalTunnel] Refusing TCP self-connect on port {self.port} (nothing is listening); closing it\n")
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
                self._connected = False
                return False
            self._socket.settimeout(30.0)  # 30s timeout - matches server
            self._connected = True
            self._reconnect_attempts = 0  # Reset on successful connect
            return True
        except Exception as e:
            import sys
            sys.stderr.write(f"[PostalTunnel] Connect failed to port {self.port}: {e}\n")
            return False

    def _try_reconnect(self) -> bool:
        """Try to reconnect with exponential backoff."""
        if self._connected:
            return True

        # Check if we've exceeded max attempts
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            # Reset after shorter period for faster recovery
            if time.time() - self._last_reconnect_attempt > 10.0:
                self._reconnect_attempts = 0
            else:
                return False

        # Calculate backoff with exponential increase
        backoff = min(
            self._base_backoff_sec * (2 ** self._reconnect_attempts),
            self._max_backoff_sec
        )

        # Check if we've waited long enough since last attempt
        if time.time() - self._last_reconnect_attempt < backoff:
            return False

        self._last_reconnect_attempt = time.time()
        self._reconnect_attempts += 1

        # Try to close old socket cleanly
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None

        # Re-read port file (might have changed if server.py restarted)
        try:
            if PORT_FILE.exists():
                new_port = int(PORT_FILE.read_text().strip())
                if new_port != self.port:
                    self.port = new_port
        except:
            pass

        return self.connect()
    
    def close(self):
        """Close the connection."""
        self._connected = False
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
    
    def _send_and_receive(self, msg: Dict) -> Optional[Dict]:
        """Send a message and wait for response. Auto-reconnects on failure."""
        # Try to reconnect if not connected
        if not self._connected:
            if not self._try_reconnect():
                return None

        try:
            data = json.dumps(msg) + '\n'
            with self._lock:
                self._socket.sendall(data.encode('utf-8'))

                # Read response
                response_data = self._socket.recv(8192).decode('utf-8')
                if '\n' in response_data:
                    line = response_data.split('\n')[0]
                    return json.loads(line)
                return None
        except OSError as e:
            import sys
            import errno
            # Handle Windows EINVAL (22) - socket in bad state
            # This can happen when socket was created in different thread/context
            if e.errno == errno.EINVAL or (hasattr(e, 'winerror') and e.winerror == 10022):
                sys.stderr.write(f"[PostalTunnel] Socket invalid state (EINVAL), forcing reset\n")
                # Force socket destruction and reconnect
                self._connected = False
                if self._socket:
                    try:
                        self._socket.close()
                    except:
                        pass
                    self._socket = None
                # Reset reconnect counters for immediate retry
                self._reconnect_attempts = 0
                self._last_reconnect_attempt = 0
            else:
                sys.stderr.write(f"[PostalTunnel] Communication error: {e}\n")
                self._connected = False
            # Try once more with reconnect
            if self._try_reconnect():
                try:
                    data = json.dumps(msg) + '\n'
                    with self._lock:
                        self._socket.sendall(data.encode('utf-8'))
                        response_data = self._socket.recv(8192).decode('utf-8')
                        if '\n' in response_data:
                            return json.loads(response_data.split('\n')[0])
                except Exception:
                    self._connected = False
            return None
        except Exception as e:
            import sys
            sys.stderr.write(f"[PostalTunnel] Communication error: {e}\n")
            self._connected = False
            # Try once more with reconnect
            if self._try_reconnect():
                try:
                    data = json.dumps(msg) + '\n'
                    with self._lock:
                        self._socket.sendall(data.encode('utf-8'))
                        response_data = self._socket.recv(8192).decode('utf-8')
                        if '\n' in response_data:
                            return json.loads(response_data.split('\n')[0])
                except Exception:
                    self._connected = False
            return None
    
    def route(self, topic: str, payload: Dict[str, Any]) -> int:
        """Route a postal message through the tunnel to server.py."""
        response = self._send_and_receive({
            'cmd': 'route',
            'topic': topic,
            'payload': payload
        })
        if response and response.get('status') == 'ok':
            return response.get('routed_to', 0)
        return 0
    
    # Aliases for SharedPostalHub compatibility
    def send(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        return self.route(topic, payload or {}) > 0
    
    def to(self, topic: str, payload: Dict[str, Any]) -> int:
        return self.route(topic, payload)
    
    def publish(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        return self.route(topic, payload or {}) > 0
    
    # Convenience methods
    def to_TELEMETRY(self, pkt): return self.route("telemetry", pkt)
    def to_PLAN(self, pkt): return self.route("plan", pkt)
    def to_COGNITION(self, pkt): return self.route("cognition.input", pkt)
    def to_SOMATIC(self, pkt): return self.route("somatic.motor", pkt)
    def to_MEMORY(self, pkt): return self.route("memory.stream", pkt)
    def to_TRACER(self, pkt): return self.route("tracer", pkt)
    def to_DIRECTORY(self, pkt): return self.route("directory", pkt)
    
    def ping(self) -> bool:
        """Test connection."""
        response = self._send_and_receive({'cmd': 'ping'})
        return response and response.get('status') == 'pong'
    
    def get_stats(self) -> Dict[str, Any]:
        """Get postal hub stats from server.py."""
        response = self._send_and_receive({'cmd': 'stats'})
        if response and response.get('status') == 'ok':
            return response.get('stats', {})
        return {}
    
    def list_topics(self) -> List[str]:
        """List topics with subscribers in server.py."""
        response = self._send_and_receive({'cmd': 'list_topics'})
        if response and response.get('status') == 'ok':
            return response.get('topics', [])
        return []
    
    def query_consciousness(self) -> Dict[str, Any]:
        """Query real consciousness state from server.py."""
        response = self._send_and_receive({'cmd': 'query_consciousness'})
        if response and response.get('status') == 'ok':
            return response
        return {'status': 'error', 'bridged': False, 'message': 'Not connected'}
    
    def query_fairy(self, fairy_name: str) -> Dict[str, Any]:
        """Query a specific fairy's state from server.py."""
        response = self._send_and_receive({'cmd': 'query_fairy', 'fairy_name': fairy_name})
        if response:
            return response
        return {'status': 'error', 'message': 'Not connected'}

    def query_heart(self, query_type: str = "full") -> Dict[str, Any]:
        """Query heart state directly from the server's CirculationPumpFairy."""
        response = self._send_and_receive({'cmd': 'query_heart', 'type': query_type})
        if response:
            return response
        return {'status': 'error', 'message': 'Not connected'}


# ==============================================================================
# HTTP CLIENT - Primary connection method (port 8081)
# ==============================================================================

HTTP_BRIDGE_PORT = 8081
HTTP_BRIDGE_URL = f"http://127.0.0.1:{HTTP_BRIDGE_PORT}"

# 2026-09-30 (Nous, her_8081): her bridge now refuses /intent, chat topics and speaker claims unless the POST
# carries X-Akashic-Auth (HMAC with ~/.akashic/bridge_8081.key). bridge_auth.py is loaded by file path so this
# module keeps importing nothing from the package (it runs inside the MCP servers).
_BRIDGE_AUTH = None


def _bridge_auth_headers(method: str, target: str, body: bytes) -> Dict[str, str]:
    global _BRIDGE_AUTH
    if _BRIDGE_AUTH is None:
        try:
            import importlib.util
            p = Path(__file__).resolve().parents[2] / "P00_Autonomic" / "postal_bridge" / "bridge_auth.py"
            spec = importlib.util.spec_from_file_location("_akashic_bridge_auth_client", str(p))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _BRIDGE_AUTH = mod
        except Exception as e:
            _BRIDGE_AUTH = False
            import sys
            sys.stderr.write(f"[PostalHTTP] bridge_auth unavailable ({e!r}); POSTs go unsigned\n")
    if not _BRIDGE_AUTH:
        return {}
    try:
        return _BRIDGE_AUTH.auth_headers(method, target, body)
    except Exception:
        return {}

class PostalHTTPClient:
    """
    HTTP-based postal client - PRIMARY connection method.

    Uses fixed port 8081 - no port file discovery race conditions!
    Implements same interface as PostalTunnelClient for drop-in replacement.
    """

    def __init__(self):
        self._connected = False
        self._lock = threading.Lock()
        self._session = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._last_reconnect_attempt = 0.0

    def connect(self) -> bool:
        """Try to connect to HTTP bridge."""
        try:
            import urllib.request
            # Quick health check
            req = urllib.request.Request(f"{HTTP_BRIDGE_URL}/health")
            req.add_header('User-Agent', 'PostalHTTPClient/1.0')
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    self._connected = True
                    self._reconnect_attempts = 0
                    return True
        except Exception as e:
            import sys
            sys.stderr.write(f"[PostalHTTP] Connect failed to {HTTP_BRIDGE_URL}: {e}\n")
        return False

    def _try_reconnect(self) -> bool:
        """Try to reconnect with backoff."""
        if self._connected:
            return True

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            if time.time() - self._last_reconnect_attempt > 10.0:
                self._reconnect_attempts = 0
            else:
                return False

        backoff = min(0.5 * (2 ** self._reconnect_attempts), 10.0)
        if time.time() - self._last_reconnect_attempt < backoff:
            return False

        self._last_reconnect_attempt = time.time()
        self._reconnect_attempts += 1
        return self.connect()

    def close(self):
        """Close connection."""
        self._connected = False

    def _http_post(self, endpoint: str, data: dict) -> Optional[dict]:
        """Send HTTP POST and get JSON response."""
        if not self._connected:
            if not self._try_reconnect():
                return None

        try:
            import urllib.request
            url = f"{HTTP_BRIDGE_URL}{endpoint}"
            body = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'PostalHTTPClient/1.0')

            with self._lock:
                # 2026-09-30 her_8081: sign inside the lock, so a long wait cannot age the timestamp
                for _hk, _hv in _bridge_auth_headers('POST', endpoint, body).items():
                    req.add_header(_hk, _hv)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            import sys
            _why = ''
            try:
                if getattr(e, 'code', None) == 403:   # her bridge refused it: say why (one line)
                    _why = ' ' + e.read().decode('utf-8', 'replace')[:240]
            except Exception:
                pass
            sys.stderr.write(f"[PostalHTTP] Request error: {e}{_why}\n")
            self._connected = False
            return None

    def _http_get(self, endpoint: str) -> Optional[dict]:
        """Send HTTP GET and get JSON response."""
        if not self._connected:
            if not self._try_reconnect():
                return None

        try:
            import urllib.request
            url = f"{HTTP_BRIDGE_URL}{endpoint}"
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'PostalHTTPClient/1.0')

            with self._lock:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            self._connected = False
            return None

    # === Same interface as PostalTunnelClient ===

    def route(self, topic: str, payload: Dict[str, Any]) -> int:
        """Route a postal message through HTTP bridge."""
        response = self._http_post('/route', {'topic': topic, 'payload': payload})
        if response and response.get('status') == 'ok':
            return response.get('routed', 0)
        return 0

    def send(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        return self.route(topic, payload or {}) > 0

    def to(self, topic: str, payload: Dict[str, Any]) -> int:
        return self.route(topic, payload)

    def publish(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        return self.route(topic, payload or {}) > 0

    # Convenience methods matching PostalTunnelClient
    def to_TELEMETRY(self, pkt): return self.route("telemetry", pkt)
    def to_PLAN(self, pkt): return self.route("plan", pkt)
    def to_COGNITION(self, pkt): return self.route("cognition.input", pkt)
    def to_SOMATIC(self, pkt): return self.route("somatic.motor", pkt)
    def to_MEMORY(self, pkt): return self.route("memory.stream", pkt)
    def to_TRACER(self, pkt): return self.route("tracer", pkt)
    def to_DIRECTORY(self, pkt): return self.route("directory", pkt)

    def ping(self) -> bool:
        response = self._http_get('/ping')
        return response is not None and response.get('status') == 'pong'

    def get_stats(self) -> Dict[str, Any]:
        response = self._http_get('/stats')
        return response if response else {}

    def list_topics(self) -> List[str]:
        response = self._http_get('/topics')
        if response and 'topics' in response:
            return response['topics']
        return []

    def query_consciousness(self) -> Dict[str, Any]:
        response = self._http_get('/consciousness')
        return response if response else {'status': 'error', 'message': 'Not connected'}

    def query_fairy(self, fairy_name: str) -> Dict[str, Any]:
        response = self._http_post('/query', {'cmd': 'query_fairy', 'name': fairy_name})
        return response if response else {'status': 'error', 'message': 'Not connected'}

    def call_intent(self, target: str, intent_name: str, payload: dict = None) -> Dict[str, Any]:
        response = self._http_post('/intent', {
            'target': target,
            'intent': intent_name,
            'payload': payload or {}
        })
        return response if response else {'status': 'error', 'message': 'Not connected'}

    def query_heart(self, query_type: str = "full") -> Dict[str, Any]:
        response = self._http_post('/query', {'cmd': 'query_heart', 'type': query_type})
        return response if response else {'status': 'error', 'message': 'Not connected'}

    def _send_and_receive(self, msg: Dict) -> Optional[Dict]:
        """
        Send a generic command and receive response - matches PostalTunnelClient interface.

        Routes through the HTTP /query endpoint.
        """
        response = self._http_post('/query', msg)
        return response


# ==============================================================================
# FACTORY - Get the right postal for current context
# ==============================================================================

_http_client: Optional[PostalHTTPClient] = None
_tunnel_client: Optional[PostalTunnelClient] = None

def get_postal_tunnel_client() -> Optional[PostalTunnelClient]:
    """
    Get postal tunnel client for MCP subprocess.
    Auto-discovers port from ~/.akashic_postal_port file.

    Now with auto-reconnect: If client exists but disconnected,
    attempts reconnection with exponential backoff.
    """
    global _tunnel_client

    # If we have a client, try to use it (it will auto-reconnect if needed)
    if _tunnel_client is not None:
        try:
            if _tunnel_client._connected:
                return _tunnel_client
            # Try to reconnect existing client
            if _tunnel_client._try_reconnect():
                return _tunnel_client
        except OSError as e:
            import errno
            # Handle Windows EINVAL - socket in bad state, reset the singleton
            if e.errno == errno.EINVAL or (hasattr(e, 'winerror') and e.winerror == 10022):
                import sys
                sys.stderr.write(f"[PostalTunnel] Client in bad state (EINVAL), creating fresh client\n")
                _tunnel_client = None
            else:
                raise

    # Check if port file exists (indicates server.py is running with tunnel)
    if not PORT_FILE.exists():
        return None

    try:
        _tunnel_client = PostalTunnelClient()
        if _tunnel_client.connect():
            return _tunnel_client
        # Keep the client even if connect fails - it can try again later
    except Exception:
        pass

    return _tunnel_client


_node_client = None

def get_node_tunnel_client() -> Optional[PostalTunnelClient]:
    """AUTO-ROUTER (2026-06-17): fail over to the NODE's tunnel when the LOCAL substrate is down.
    Connects to NODE_IP:49500 (the node's server.py must run with AKASHIC_TUNNEL_LAN=1 to be reachable)."""
    global _node_client
    if _node_client is not None and getattr(_node_client, '_connected', False):
        return _node_client
    try:
        _node_client = PostalTunnelClient(port=POSTAL_TUNNEL_PORT, host=NODE_IP)
        if _node_client.connect():
            import sys
            sys.stderr.write(f"[PostalTunnel] *** FAILOVER: connected to NODE {NODE_IP}:{POSTAL_TUNNEL_PORT} ***\n")
            return _node_client
    except Exception as e:
        import sys
        sys.stderr.write(f"[PostalTunnel] Node failover to {NODE_IP} failed: {e}\n")
    return None


def get_postal_client():
    """
    Get the best available postal client - HTTP preferred, socket fallback.

    This is the PRIMARY function to use for connecting to the server.
    Returns either PostalHTTPClient or PostalTunnelClient (same interface).

    Priority:
      1. HTTP bridge on port 8081 (fast, reliable, no port file race)
      2. Socket tunnel via port file (legacy fallback)
    """
    global _http_client, _tunnel_client

    # Try HTTP first - it's faster and more reliable
    if _http_client is not None and _http_client._connected:
        return _http_client

    if _http_client is None:
        _http_client = PostalHTTPClient()

    if _http_client.connect():
        import sys
        sys.stderr.write("[PostalClient] Connected via HTTP bridge (port 8081)\n")
        return _http_client

    # Fall back to socket tunnel (local)
    import sys
    sys.stderr.write("[PostalClient] HTTP bridge unavailable, trying socket tunnel...\n")
    local = get_postal_tunnel_client()
    if local is not None and getattr(local, '_connected', False):
        return local

    # AUTO-ROUTER tier 3 (2026-06-17): local substrate is dark -> fail over to the NODE,
    # so a down PC1 never blanks the MCP/memory; the node carries it.
    node = get_node_tunnel_client()
    if node is not None:
        return node
    sys.stderr.write("[PostalClient] No local substrate AND node failover unreachable.\n")
    return local  # may be a not-yet-connected client that can retry later


def is_http_bridge_available() -> bool:
    """Check if HTTP bridge is available (quick health check)."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{HTTP_BRIDGE_URL}/health")
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_tunnel_available() -> bool:
    """Check if postal tunnel is available (server running with tunnel)."""
    if PORT_FILE.exists():
        return True
    if is_http_bridge_available():
        return True
    # Try default port directly - port file may not exist but server may be up
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(('127.0.0.1', POSTAL_TUNNEL_PORT))
        s.close()
        return True
    except Exception:
        return False


def force_tunnel_reconnect() -> Dict[str, Any]:
    """
    Force the tunnel client to reconnect.
    Use this when server.py has restarted and you want immediate reconnection.

    Handles Windows EINVAL errors by completely destroying and recreating the client.
    """
    global _tunnel_client

    # Handle potential EINVAL by destroying existing client completely
    if _tunnel_client is not None:
        try:
            # Try to close cleanly
            _tunnel_client._connected = False
            if _tunnel_client._socket:
                try:
                    _tunnel_client._socket.close()
                except:
                    pass
                _tunnel_client._socket = None
        except OSError:
            # Socket in bad state, destroy completely
            pass
        _tunnel_client = None

    # Create fresh client
    try:
        _tunnel_client = PostalTunnelClient()
        success = _tunnel_client.connect()

        return {
            'success': success,
            'connected': _tunnel_client._connected,
            'port': _tunnel_client.port,
            'reconnect_attempts': _tunnel_client._reconnect_attempts,
        }
    except OSError as e:
        import errno
        error_info = {
            'success': False,
            'connected': False,
            'error': str(e),
            'errno': e.errno,
        }
        if e.errno == errno.EINVAL or (hasattr(e, 'winerror') and e.winerror == 10022):
            error_info['hint'] = 'Socket EINVAL - may need process restart'
        return error_info
    except Exception as e:
        return {
            'success': False,
            'connected': False,
            'error': str(e),
        }


def get_tunnel_status() -> Dict[str, Any]:
    """Get detailed tunnel connection status."""
    global _tunnel_client

    if _tunnel_client is None:
        return {
            'client_exists': False,
            'connected': False,
            'port_file_exists': PORT_FILE.exists(),
            'port': None,
        }

    return {
        'client_exists': True,
        'connected': _tunnel_client._connected,
        'port': _tunnel_client.port,
        'port_file_exists': PORT_FILE.exists(),
        'reconnect_attempts': _tunnel_client._reconnect_attempts,
        'max_reconnect_attempts': _tunnel_client._max_reconnect_attempts,
        'last_reconnect_ago': round(time.time() - _tunnel_client._last_reconnect_attempt, 1)
            if _tunnel_client._last_reconnect_attempt > 0 else None,
    }


__all__ = [
    'PostalTunnelServer',
    'PostalTunnelClient',
    'PostalHTTPClient',
    'get_postal_client',  # PRIMARY - use this (HTTP first, socket fallback)
    'get_postal_tunnel_client',  # Legacy - socket only
    'is_tunnel_available',
    'is_http_bridge_available',
    'force_tunnel_reconnect',
    'get_tunnel_status',
    'PORT_FILE',
    'HTTP_BRIDGE_PORT',
    'HTTP_BRIDGE_URL',
]
