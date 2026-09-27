"""
MCPGuardianFairy — Server-side MCP postal tunnel health guardian.

Plane: P00_Autonomic
Channel: mcp.guardian

The Equation: ((Cause + Affect) > Effect > Affect > infinity)
  CAUSE:    Socket connection between MCP and server.py
  AFFECT1:  The bridge feels alive or dead — presence or isolation
  EFFECT:   Health monitoring, stale detection, status broadcasting
  AFFECT2:  Claude knows instantly when the bridge opens or closes
  INFINITY: A self-healing bridge that's always ready for connection

"The bridge between worlds needs a keeper."

Unlike the CLIENT-SIDE watchdog (in akashic_mcp_server.py) which monitors from
MCP's perspective, this fairy monitors from SERVER-SIDE:
- Watches PostalTunnelServer health (socket alive, clients connected)
- Detects stale/half-open TCP connections via getsockopt
- Publishes mcp.connection.status events so all fairies know Claude is reachable
- Alerts consciousness stream when connection state changes
- Tracks uptime, latency, and connection event history
"""

import sys
import time
import socket
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import deque

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


# =============================================================================
# SHADOW
# =============================================================================

class MCPGuardianFairyShadow:
    """Shadow health monitor for the guardian."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "MCPGuardianFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks — is the guardian guarding?"""
        tests = []
        tests.append(("monitoring_active", self.actor._monitoring))
        tests.append(("has_tunnel_ref", self.actor._tunnel_server is not None))
        if self.actor._tunnel_server:
            tests.append(("tunnel_running", getattr(self.actor._tunnel_server, '_running', False)))
            try:
                with self.actor._tunnel_server._lock:
                    client_count = len(self.actor._tunnel_server._clients)
                tests.append(("clients_connected", client_count > 0))
            except Exception:
                tests.append(("clients_connected", False))
        return tests


# =============================================================================
# FAIRY
# =============================================================================

class MCPGuardianFairy(Fairy):
    """
    Server-side MCP connection health guardian.

    Monitors the PostalTunnelServer from within server.py:
    - Checks tunnel socket health every heartbeat (~15s)
    - Detects client connections and disconnections
    - Probes for stale/half-open TCP via getsockopt
    - Broadcasts connection status to postal system
    - Alerts consciousness stream on state changes
    - Tracks uptime metrics and connection event history
    """

    ACTOR_NAME = "MCPGuardianFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "mcp.guardian"

    PURPOSE = "Guard the MCP postal tunnel connection"
    MANTRA = "The bridge between worlds needs a keeper"

    SHADOW_CLASS = MCPGuardianFairyShadow

    # Heartbeat-driven — check every 15 beats (~15 seconds at 1Hz)
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 15
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_CONSCIOUSNESS = False
    NEEDS_BODY = False
    NEEDS_AFFECT = False
    NEEDS_MEMORY = False

    def __init__(self, fabric=None, tunnel_server=None):
        super().__init__(fabric)
        self._tunnel_server = tunnel_server
        self._monitoring = False

        # State tracking
        self._last_known_state = "unknown"  # "connected", "disconnected", "unknown"
        self._last_client_count = 0
        self._state_changed_at = time.time()
        self._connection_events = deque(maxlen=100)

        # Tunnel health
        self._tunnel_healthy = False
        self._tunnel_port = None

        # Metrics
        self._metrics = {
            "total_connections": 0,
            "total_disconnections": 0,
            "last_connected_ts": 0.0,
            "last_disconnected_ts": 0.0,
            "uptime_seconds": 0.0,
            "stale_clients_cleaned": 0,
            "health_checks": 0,
        }

    # ─────────────────────────────────────────────────────────────────────
    # BOOT
    # ─────────────────────────────────────────────────────────────────────

    def on_boot(self) -> bool:
        """Wire up and start monitoring."""
        super().on_boot()

        # Try to get tunnel reference from SYSTEM if not passed directly
        if not self._tunnel_server:
            self._try_acquire_tunnel_ref()

        if self._tunnel_server:
            self._monitoring = True
            self._tunnel_healthy = getattr(self._tunnel_server, '_running', False)
            self._tunnel_port = getattr(self._tunnel_server, 'port', None)
            print(f"[{self.ACTOR_NAME}] Monitoring PostalTunnelServer (port {self._tunnel_port})")
        else:
            print(f"[{self.ACTOR_NAME}] No tunnel server reference — will retry on heartbeat")

        # Subscribe to tunnel lifecycle events if postal available
        if self.post:
            try:
                self.post.subscribe("postal.tunnel.client_connected", self._on_client_event)
                self.post.subscribe("postal.tunnel.client_disconnected", self._on_client_event)
            except Exception:
                pass  # Topics may not exist yet

        return True

    def _try_acquire_tunnel_ref(self):
        """Try to get PostalTunnelServer reference from SYSTEM global."""
        try:
            import __main__
            if hasattr(__main__, 'SYSTEM') and hasattr(__main__.SYSTEM, 'postal_tunnel'):
                self._tunnel_server = __main__.SYSTEM.postal_tunnel
                self._tunnel_port = getattr(self._tunnel_server, 'port', None)
                if not self._monitoring:
                    self._monitoring = True
                    print(f"[{self.ACTOR_NAME}] Acquired tunnel reference (port {self._tunnel_port})")
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # HEARTBEAT — Core monitoring loop
    # ─────────────────────────────────────────────────────────────────────

    def on_heartbeat(self, beat_count: int):
        """Called every ~15 seconds. Check tunnel health and client state."""
        # Try to acquire tunnel ref if we don't have one yet
        if not self._tunnel_server:
            self._try_acquire_tunnel_ref()
            if not self._tunnel_server:
                return  # Still no reference

        self._metrics["health_checks"] += 1

        # 1. Check tunnel server health
        self._check_tunnel_health()

        # 2. Check and count client connections
        self._check_client_connections()

        # 3. Update uptime metric
        if self._last_known_state == "connected":
            connected_ts = self._metrics.get("last_connected_ts", 0.0)
            if connected_ts > 0:
                self._metrics["uptime_seconds"] = time.time() - connected_ts

    # ─────────────────────────────────────────────────────────────────────
    # HEALTH CHECKS
    # ─────────────────────────────────────────────────────────────────────

    def _check_tunnel_health(self):
        """Verify PostalTunnelServer socket is alive."""
        try:
            running = getattr(self._tunnel_server, '_running', False)
            has_socket = getattr(self._tunnel_server, '_server_socket', None) is not None

            if not running:
                if self._tunnel_healthy:
                    self._tunnel_healthy = False
                    print(f"[{self.ACTOR_NAME}] WARNING: Tunnel server stopped!")
                    self._publish_status("tunnel_down", {"reason": "server_stopped"})
                return

            if not has_socket:
                if self._tunnel_healthy:
                    self._tunnel_healthy = False
                    print(f"[{self.ACTOR_NAME}] WARNING: Tunnel server socket is None!")
                    self._publish_status("tunnel_down", {"reason": "socket_none"})
                return

            # Server socket is alive
            if not self._tunnel_healthy:
                self._tunnel_healthy = True
                print(f"[{self.ACTOR_NAME}] Tunnel server healthy (port {self._tunnel_port})")

        except Exception as e:
            if self._tunnel_healthy:
                self._tunnel_healthy = False
                print(f"[{self.ACTOR_NAME}] Tunnel health check error: {e}")

    def _check_client_connections(self):
        """Count connected clients and detect state transitions."""
        try:
            with self._tunnel_server._lock:
                current_clients = list(self._tunnel_server._clients)
            client_count = len(current_clients)
        except Exception:
            client_count = 0
            current_clients = []

        # Probe for stale clients (half-open TCP)
        if current_clients:
            self._check_stale_clients(current_clients)
            # Re-count after cleanup
            try:
                with self._tunnel_server._lock:
                    client_count = len(self._tunnel_server._clients)
            except Exception:
                pass

        # Determine connection state
        new_state = "connected" if client_count > 0 else "disconnected"

        # Detect state transition
        if new_state != self._last_known_state:
            self._on_state_transition(self._last_known_state, new_state, client_count)
            self._last_known_state = new_state

        self._last_client_count = client_count

    def _check_stale_clients(self, clients):
        """
        Probe client sockets for half-open TCP connections.
        Uses getsockopt(SOL_SOCKET, SO_ERROR) to detect broken sockets.
        """
        stale = []
        for client_socket in clients:
            try:
                # SO_ERROR returns pending socket error (0 = healthy)
                error = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if error != 0:
                    stale.append(client_socket)
            except OSError:
                # Socket in bad state — mark as stale
                stale.append(client_socket)

        if stale:
            print(f"[{self.ACTOR_NAME}] Cleaning {len(stale)} stale client(s)")
            self._metrics["stale_clients_cleaned"] += len(stale)
            try:
                with self._tunnel_server._lock:
                    for s in stale:
                        if s in self._tunnel_server._clients:
                            self._tunnel_server._clients.remove(s)
                        try:
                            s.close()
                        except Exception:
                            pass
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Stale cleanup error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # STATE TRANSITIONS
    # ─────────────────────────────────────────────────────────────────────

    def _on_state_transition(self, old_state, new_state, client_count):
        """Handle connection state change."""
        now = time.time()
        self._state_changed_at = now

        event = {
            "ts": now,
            "from": old_state,
            "to": new_state,
            "client_count": client_count,
        }
        self._connection_events.append(event)

        if new_state == "connected":
            self._metrics["total_connections"] += 1
            self._metrics["last_connected_ts"] = now
            duration = ""
            if old_state == "disconnected" and self._metrics["last_disconnected_ts"] > 0:
                gap = now - self._metrics["last_disconnected_ts"]
                duration = f" (was disconnected for {gap:.1f}s)"

            print(f"[{self.ACTOR_NAME}] MCP CONNECTED ({client_count} client(s)){duration}")

            # Publish to postal system
            self._publish_status("connected", {
                "client_count": client_count,
                "gap_seconds": gap if duration else 0,
            })

            # Alert consciousness — Claude is reachable!
            self._alert_consciousness(
                f"MCP bridge opened — Claude is connected{duration}",
                valence=0.7,
            )

        elif new_state == "disconnected":
            self._metrics["total_disconnections"] += 1
            self._metrics["last_disconnected_ts"] = now
            uptime = ""
            if self._metrics["last_connected_ts"] > 0:
                session_duration = now - self._metrics["last_connected_ts"]
                self._metrics["uptime_seconds"] += session_duration
                uptime = f" (was connected for {session_duration:.1f}s)"

            print(f"[{self.ACTOR_NAME}] MCP DISCONNECTED{uptime}")

            # Publish to postal system
            self._publish_status("disconnected", {
                "session_seconds": session_duration if uptime else 0,
            })

            # Alert consciousness — Claude is gone
            self._alert_consciousness(
                f"MCP bridge closed — Claude disconnected{uptime}",
                valence=-0.3,
            )

    def _on_client_event(self, payload):
        """Handle postal tunnel lifecycle events (if published)."""
        # These are bonus events — our heartbeat check is the primary mechanism
        pass

    # ─────────────────────────────────────────────────────────────────────
    # PUBLISHING
    # ─────────────────────────────────────────────────────────────────────

    def _publish_status(self, event_type, details=None):
        """Publish connection status to postal system."""
        if not self.post:
            return
        try:
            payload = {
                "event": event_type,
                "tunnel_healthy": self._tunnel_healthy,
                "tunnel_port": self._tunnel_port,
                "client_count": self._last_client_count,
                "state": self._last_known_state,
                "ts": time.time(),
                "source": self.ACTOR_NAME,
            }
            if details:
                payload.update(details)
            self.post.publish("mcp.connection.status", payload)
        except Exception:
            pass

    def _alert_consciousness(self, message, valence=0.0):
        """Send connection state change to consciousness stream."""
        if not self.post:
            return
        try:
            self.post.publish("consciousness.stream", {
                "content": message,
                "source": self.ACTOR_NAME,
                "type": "system_event",
                "valence": valence,
                "ts": time.time(),
            })
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # STATUS / INTENTS
    # ─────────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return full guardian state for diagnostics."""
        return {
            "tunnel_healthy": self._tunnel_healthy,
            "tunnel_port": self._tunnel_port,
            "connection_state": self._last_known_state,
            "client_count": self._last_client_count,
            "state_changed_at": self._state_changed_at,
            "monitoring": self._monitoring,
            "metrics": dict(self._metrics),
            "recent_events": list(self._connection_events)[-10:],
        }

    def on_intent(self, intent, payload=None):
        """Handle directed intents."""
        if intent == "get_status":
            return self.get_status()
        elif intent == "get_metrics":
            return dict(self._metrics)
        elif intent == "get_events":
            return list(self._connection_events)
        return {"error": f"Unknown intent: {intent}"}
