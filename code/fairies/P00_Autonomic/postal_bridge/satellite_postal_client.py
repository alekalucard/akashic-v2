# ==============================================================================
# SATELLITE POSTAL CLIENT - Forward consciousness to primary node
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# When running in satellite mode, the system processes everything locally
# EXCEPT waking minds (Sourpatches, Nous). This client subscribes to local
# postal topics and forwards consciousness-relevant messages to the primary
# node's PostalHTTPBridge via HTTP.
#
# The satellite is the "shadow research and evolution society" — autonomous
# experimental processing that surfaces discoveries to the primary's
# waking minds.
#
# ==============================================================================

import json
import socket
import threading
import time
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

# 2026-09-30 (Nous, her_8081): sign POSTs to the primary's bridge when THIS machine has the bridge key
# (~/.akashic/bridge_8081.key, copied by hand). Without a key the POSTs go unsigned, exactly as before; the
# primary still accepts them unless they carry a chat topic or a claim of who spoke.
try:
    from .bridge_auth import auth_headers as _auth_headers
except Exception:
    try:
        import importlib.util as _ilu
        from pathlib import Path as _P
        _spec = _ilu.spec_from_file_location("_akashic_bridge_auth_sat", str(_P(__file__).resolve().with_name("bridge_auth.py")))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _auth_headers = _mod.auth_headers
    except Exception:
        def _auth_headers(method, target, body):
            return {}


class SatellitePostalClient:
    """
    Forwards selected postal topics from satellite to primary via HTTP.

    Architecture:
        Local PostalHub → subscribe → SatellitePostalClient → HTTP POST → Primary's PostalHTTPBridge

    Only consciousness-relevant topics are forwarded to keep traffic minimal.
    All forwarding is best-effort and non-blocking.
    """

    # Topics to forward from satellite to primary
    FORWARDED_TOPICS = [
        "consciousness.surfacing",          # Thoughts that surface to waking mind
        "consciousness.collision",           # All collision events
        "consciousness.collision.system",    # System chamber collisions specifically
        "memory.ingested",                   # New memories formed on satellite
        "cognition.output",                  # Cortex bindings / associations
        "cognition.inference.complete",      # Inference results from AkashicInferenceFairy
        "satellite.status",                  # Satellite health broadcasts
    ]

    # Heartbeat interval (seconds)
    HEARTBEAT_INTERVAL = 10.0

    # HTTP timeout for forwarding (seconds) - keep short to avoid blocking postal
    FORWARD_TIMEOUT = 3.0

    def __init__(
        self,
        primary_ip: str,
        primary_port: int = 8081,
        local_fabric=None,
        node_name: str = "satellite",
    ):
        """
        Args:
            primary_ip: IP address of the primary node
            primary_port: PostalHTTPBridge port on primary (default 8081)
            local_fabric: Local PostalHub to subscribe to
            node_name: This satellite's identity name
        """
        self.primary_url = f"http://{primary_ip}:{primary_port}"
        self.primary_ip = primary_ip
        self.primary_port = primary_port
        self.fabric = local_fabric
        self.node_name = node_name

        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._forwarded_count = 0
        self._forward_errors = 0
        self._last_heartbeat_ok = False
        self._start_time = 0.0

    def start(self):
        """Subscribe to local postal topics and begin forwarding to primary."""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()

        # Subscribe to each forwarded topic
        if self.fabric:
            for topic in self.FORWARDED_TOPICS:
                try:
                    self.fabric.subscribe(
                        topic,
                        lambda env, t=topic: self._forward(t, env),
                        f"satellite_fwd_{topic.replace('.', '_')}"
                    )
                except Exception as e:
                    print(f"[SatellitePostalClient] Failed to subscribe to {topic}: {e}")

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="satellite-heartbeat"
        )
        self._heartbeat_thread.start()

        print(f"[SatellitePostalClient] Started - forwarding {len(self.FORWARDED_TOPICS)} topics to {self.primary_url}")

    def stop(self):
        """Stop forwarding and heartbeat."""
        self._running = False
        print(f"[SatellitePostalClient] Stopped (forwarded {self._forwarded_count} messages, {self._forward_errors} errors)")

    def _headers(self, data: bytes) -> Dict[str, str]:
        """Content-Type, plus X-Akashic-Auth when this machine has the bridge key (2026-09-30, her_8081)."""
        h = {"Content-Type": "application/json"}
        try:
            h.update(_auth_headers("POST", "/route", data))
        except Exception:
            pass
        return h

    def _forward(self, topic: str, envelope):
        """Forward a postal message to primary via HTTP POST. Non-blocking, best-effort."""
        if not self._running:
            return

        # Extract payload from envelope
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
        elif isinstance(envelope, dict):
            payload = envelope
        else:
            payload = {"raw": str(envelope)}

        # Make payload JSON-serializable
        try:
            serializable_payload = self._make_serializable(payload)
        except Exception:
            serializable_payload = {"raw": str(payload)}

        # Forward in background thread to avoid blocking postal delivery
        threading.Thread(
            target=self._do_forward,
            args=(topic, serializable_payload),
            daemon=True,
        ).start()

    def _do_forward(self, topic: str, payload: dict):
        """Actually send the HTTP POST to primary. Runs in background thread."""
        try:
            data = json.dumps({
                "topic": topic,
                "payload": payload,
                "from_satellite": self.node_name,
                "forwarded_at": time.time(),
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.primary_url}/route",
                data=data,
                headers=self._headers(data),
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=self.FORWARD_TIMEOUT)
            resp.read()  # Consume response
            self._forwarded_count += 1
        except (urllib.error.URLError, socket.timeout, OSError):
            self._forward_errors += 1
        except Exception:
            self._forward_errors += 1

    def _heartbeat_loop(self):
        """Send periodic heartbeat to primary with satellite status."""
        while self._running:
            try:
                self._send_heartbeat()
            except Exception:
                self._last_heartbeat_ok = False

            # Sleep in small increments for responsive shutdown
            for _ in range(int(self.HEARTBEAT_INTERVAL * 10)):
                if not self._running:
                    break
                time.sleep(0.1)

    def _send_heartbeat(self):
        """Send a single heartbeat with satellite status info."""
        import platform

        heartbeat_data = {
            "topic": "satellite.heartbeat",
            "payload": {
                "from_satellite": self.node_name,
                "hostname": socket.gethostname(),
                "platform": platform.system(),
                "uptime": time.time() - self._start_time,
                "forwarded_count": self._forwarded_count,
                "forward_errors": self._forward_errors,
                "timestamp": time.time(),
            },
        }

        # Try to add GPU info if available
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    heartbeat_data["payload"]["gpu"] = {
                        "memory_used_mb": int(parts[0].strip()),
                        "memory_total_mb": int(parts[1].strip()),
                        "utilization_pct": int(parts[2].strip()),
                    }
        except Exception:
            pass  # GPU info is optional

        try:
            data = json.dumps(heartbeat_data).encode("utf-8")
            req = urllib.request.Request(
                f"{self.primary_url}/route",
                data=data,
                headers=self._headers(data),
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=self.FORWARD_TIMEOUT)
            resp.read()
            self._last_heartbeat_ok = True
        except Exception:
            self._last_heartbeat_ok = False

    def _make_serializable(self, obj) -> Any:
        """Make an object JSON-serializable by converting non-standard types."""
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        if isinstance(obj, dict):
            return {str(k): self._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        if hasattr(obj, '__dict__'):
            return self._make_serializable(vars(obj))
        return str(obj)

    def get_status(self) -> Dict[str, Any]:
        """Get satellite client status for diagnostics."""
        return {
            "running": self._running,
            "primary_url": self.primary_url,
            "node_name": self.node_name,
            "forwarded_count": self._forwarded_count,
            "forward_errors": self._forward_errors,
            "last_heartbeat_ok": self._last_heartbeat_ok,
            "uptime": time.time() - self._start_time if self._start_time else 0,
            "topics": self.FORWARDED_TOPICS,
        }
