"""
SatelliteBridgeFairy - Bridges File-Based Satellites to Postal System

The Problem:
- SatelliteManager uses file-based .satellite/*.json
- GPUPoolFairy expects postal-based satellite.gpu.announce
- WorkerEquilibrium only knows local CPU/GPU

The Solution:
This fairy bridges them by:
1. Loading .satellite/peer_registry.json on boot
2. Emitting satellite.gpu.announce for GPUPoolFairy
3. Emitting satellite.status for WorkerEquilibrium
4. Periodically checking satellite health via socket ping

"System seeks balance - distribute the load"

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import json
import socket
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

import sys
ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


@dataclass
class SatelliteNode:
    """A remote satellite node."""
    name: str
    ip: str
    port: int = 5000
    role: str = "compute"
    capabilities: List[str] = field(default_factory=list)

    # GPU info
    has_gpu: bool = False
    gpu_memory_mb: float = 0.0

    # Status
    is_available: bool = False
    last_heartbeat: float = 0.0
    last_ping_ms: float = 0.0
    current_load: float = 0.0

    # Task tracking
    active_tasks: int = 0
    completed_tasks: int = 0

    def to_announce_dict(self) -> Dict[str, Any]:
        """Format for satellite.gpu.announce message."""
        return {
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "has_gpu": self.has_gpu,
            "gpu_memory_mb": self.gpu_memory_mb,
            "latency_ms": self.last_ping_ms,
            "is_available": self.is_available,
            "load": self.current_load,
        }


class SatelliteBridgeFairy(Fairy):
    """
    Bridges file-based satellite configuration to postal messaging.

    Guild: HealthGuild (hardware management)
    Coordinates with: GPUPoolFairy, WorkerEquilibrium, EquilibriumFairy

    Provides:
    - Load .satellite/peer_registry.json on boot
    - Emit satellite.gpu.announce for GPU-capable satellites
    - Check satellite health via socket ping
    - Route tasks to satellites when local resources saturated
    """

    ACTOR_NAME = "SatelliteBridgeFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.satellite"

    PURPOSE = "Bridge satellites to postal system"
    MANTRA = "System seeks balance - distribute the load"

    # Heartbeat configuration
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1

    # Don't need heavy infrastructure for this utility fairy
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_CORTEX = False
    NEEDS_BODY = False
    NEEDS_AFFECT = False

    # Timing
    ANNOUNCE_DIVISOR = 10   # Announce every 10 beats (~2.5s)
    HEALTH_DIVISOR = 40     # Health check every 40 beats (~10s)

    # Paths
    SATELLITE_DIR = ROOT / ".satellite"
    PEER_REGISTRY_PATH = ROOT / ".satellite" / "peer_registry.json"

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Satellite registry
        self._satellites: Dict[str, SatelliteNode] = {}

        # Metrics
        self._announces_sent = 0
        self._health_checks = 0
        self._tasks_routed = 0

        # Lock for thread safety
        self._lock = threading.Lock()

        # Health check thread
        self._health_thread: Optional[threading.Thread] = None
        self._running = False

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def on_boot(self) -> bool:
        """Boot the satellite bridge."""
        # Load satellite registry
        self._load_peer_registry()

        # Subscribe to satellite events
        if self.post:
            # Listen for satellite task requests
            self.post.subscribe(
                "satellite.task.submit",
                self._on_task_submit,
                f"{self.ACTOR_NAME}-task"
            )

            # Listen for satellite status requests
            self.post.subscribe(
                "satellite.status.request",
                self._on_status_request,
                f"{self.ACTOR_NAME}-status"
            )

            # Listen for heartbeats FROM satellites
            self.post.subscribe(
                "satellite.heartbeat",
                self._on_satellite_heartbeat,
                f"{self.ACTOR_NAME}-heartbeat"
            )

        # Start health check thread
        self._start_health_checker()

        # Initial announce
        self._announce_all_satellites()

        satellite_count = len(self._satellites)
        gpu_count = sum(1 for s in self._satellites.values() if s.has_gpu)
        print(f"[{self.ACTOR_NAME}] Loaded {satellite_count} satellites ({gpu_count} with GPU)")

        return True

    def on_shutdown(self):
        """Shutdown the bridge."""
        self._running = False
        if self._health_thread:
            self._health_thread.join(timeout=2.0)

    def get_capabilities(self):
        """Capabilities provided by this fairy."""
        caps = {
            "satellite.announce",
            "satellite.health.check",
            "satellite.task.route",
        }
        if any(s.has_gpu for s in self._satellites.values()):
            caps.add("satellite.gpu.available")
        return caps

    # =========================================================================
    # HEARTBEAT
    # =========================================================================

    def on_tick(self, tick_count: int):
        """Handle heartbeat tick."""
        # Announce satellites periodically
        if tick_count % self.ANNOUNCE_DIVISOR == 0:
            self._announce_all_satellites()

        # Emit status for WorkerEquilibrium
        if tick_count % (self.ANNOUNCE_DIVISOR * 2) == 0:
            self._emit_equilibrium_status()

    # =========================================================================
    # PEER REGISTRY
    # =========================================================================

    def _load_peer_registry(self):
        """Load satellites from .satellite/peer_registry.json

        Falls back to network_config.json if peer_registry has no compute nodes,
        auto-populating the registry so the gap never recurs.
        """
        peers = {}

        # Try loading peer_registry.json first
        if self.PEER_REGISTRY_PATH.exists():
            try:
                data = json.loads(self.PEER_REGISTRY_PATH.read_text(encoding='utf-8'))
                peers = data.get("peers", {})
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to read peer registry: {e}")

        # Check if we have any non-primary peers
        compute_peers = {k: v for k, v in peers.items()
                         if v.get("role") != "primary"}

        # Fallback: auto-populate from network_config.json
        if not compute_peers:
            network_config_path = self.SATELLITE_DIR / "network_config.json"
            if network_config_path.exists():
                try:
                    nc_data = json.loads(network_config_path.read_text(encoding='utf-8'))
                    nodes = nc_data.get("nodes", {})
                    for name, node_data in nodes.items():
                        if node_data.get("role") == "primary":
                            continue
                        # Convert network_config format to peer_registry format
                        peers[name] = {
                            "name": name,
                            "role": node_data.get("role", "compute"),
                            "hostname": node_data.get("hostname", ""),
                            "ip": node_data.get("ip", ""),
                            "port": node_data.get("port", 5000),
                            "capabilities": node_data.get("capabilities", []),
                            "gpu_memory_mb": node_data.get("gpu_memory_mb", 8000),
                            "is_available": False,
                            "last_heartbeat": 0,
                            "load": 0.0,
                        }
                    if peers:
                        print(f"[{self.ACTOR_NAME}] Auto-populated {len(peers)} peers from network_config.json")
                        # Save back to peer_registry so this fallback only runs once
                        self._auto_save_peer_registry(peers)
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Failed to read network config: {e}")

        if not peers:
            print(f"[{self.ACTOR_NAME}] No peers found in registry or network config")
            return

        # Load into satellites dict
        with self._lock:
            for name, peer_data in peers.items():
                if peer_data.get("role") == "primary":
                    continue

                capabilities = peer_data.get("capabilities", [])

                self._satellites[name] = SatelliteNode(
                    name=name,
                    ip=peer_data.get("ip", ""),
                    port=peer_data.get("port", 5000),
                    role=peer_data.get("role", "compute"),
                    capabilities=capabilities,
                    has_gpu="gpu" in capabilities,
                    gpu_memory_mb=peer_data.get("gpu_memory_mb", 8000.0),
                    last_heartbeat=peer_data.get("last_heartbeat", 0),
                    current_load=peer_data.get("load", 0.0),
                )

    def _auto_save_peer_registry(self, peers: dict):
        """Save auto-populated peers to peer_registry.json."""
        try:
            data = {
                "peers": peers,
                "created": time.strftime("%Y-%m-%d"),
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            self.PEER_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.PEER_REGISTRY_PATH.write_text(
                json.dumps(data, indent=2), encoding='utf-8'
            )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to auto-save peer registry: {e}")

    def _save_peer_registry(self):
        """Save updated satellite status back to registry."""
        try:
            # Load existing data
            data = {}
            if self.PEER_REGISTRY_PATH.exists():
                data = json.loads(self.PEER_REGISTRY_PATH.read_text(encoding='utf-8'))

            # Update peer status
            peers = data.get("peers", {})
            with self._lock:
                for name, satellite in self._satellites.items():
                    if name in peers:
                        peers[name]["last_heartbeat"] = satellite.last_heartbeat
                        peers[name]["load"] = satellite.current_load
                        peers[name]["is_available"] = satellite.is_available

            data["peers"] = peers
            data["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

            self.PEER_REGISTRY_PATH.write_text(
                json.dumps(data, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to save peer registry: {e}")

    # =========================================================================
    # ANNOUNCEMENTS
    # =========================================================================

    def _announce_all_satellites(self):
        """Emit satellite.gpu.announce for all GPU-capable satellites."""
        if not self.post:
            return

        with self._lock:
            for name, satellite in self._satellites.items():
                if satellite.has_gpu:
                    # Announce for GPUPoolFairy
                    self.post.publish(
                        "satellite.gpu.announce",
                        satellite.to_announce_dict()
                    )
                    self._announces_sent += 1

    def _emit_equilibrium_status(self):
        """Emit aggregate satellite status for WorkerEquilibrium."""
        if not self.post:
            return

        with self._lock:
            available_satellites = [s for s in self._satellites.values() if s.is_available]
            gpu_satellites = [s for s in available_satellites if s.has_gpu]

            # Calculate aggregate load
            if available_satellites:
                avg_load = sum(s.current_load for s in available_satellites) / len(available_satellites)
            else:
                avg_load = 1.0  # No satellites = treat as saturated

            status = {
                "total_satellites": len(self._satellites),
                "available_satellites": len(available_satellites),
                "gpu_satellites": len(gpu_satellites),
                "aggregate_load": avg_load,
                "total_gpu_memory_mb": sum(s.gpu_memory_mb for s in gpu_satellites),
                "active_tasks": sum(s.active_tasks for s in self._satellites.values()),
            }

        self.post.publish("satellite.status", status)

    # =========================================================================
    # HEALTH CHECKING
    # =========================================================================

    def _start_health_checker(self):
        """Start background thread for satellite health checks."""
        self._running = True
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="satellite_health_checker"
        )
        self._health_thread.start()

    def _health_check_loop(self):
        """Periodically check satellite health via socket ping."""
        while self._running:
            try:
                self._check_all_satellites()
                self._save_peer_registry()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Health check error: {e}")

            # Sleep for 10 seconds between checks
            for _ in range(100):  # 100 x 0.1s = 10s, allows quick shutdown
                if not self._running:
                    break
                time.sleep(0.1)

    def _check_all_satellites(self):
        """Check health of all satellites."""
        with self._lock:
            for name, satellite in self._satellites.items():
                self._check_satellite(satellite)
        self._health_checks += 1

    def _check_satellite(self, satellite: SatelliteNode):
        """Check if a satellite is reachable via TCP ping."""
        if not satellite.ip:
            satellite.is_available = False
            return

        start = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((satellite.ip, satellite.port))
            sock.close()

            if result == 0:
                satellite.is_available = True
                satellite.last_ping_ms = (time.time() - start) * 1000
                satellite.last_heartbeat = time.time()
            else:
                satellite.is_available = False
                satellite.last_ping_ms = 0.0

        except Exception:
            satellite.is_available = False
            satellite.last_ping_ms = 0.0

    # =========================================================================
    # POSTAL HANDLERS
    # =========================================================================

    @staticmethod
    def _extract_payload(envelope) -> dict:
        """Extract payload dict from postal Envelope object or raw dict."""
        if hasattr(envelope, 'payload'):
            p = envelope.payload
            return p if isinstance(p, dict) else {}
        if isinstance(envelope, dict):
            return envelope.get("payload", {})
        return {}

    def _on_satellite_heartbeat(self, envelope):
        """Handle heartbeat FROM a satellite."""
        data = self._extract_payload(envelope)

        name = data.get("name")
        if not name:
            return

        with self._lock:
            if name in self._satellites:
                satellite = self._satellites[name]
                satellite.last_heartbeat = time.time()
                satellite.is_available = True
                satellite.current_load = data.get("load", 0.0)
                satellite.gpu_memory_mb = data.get("gpu_memory_mb", satellite.gpu_memory_mb)

                # Update task count if provided
                if "active_tasks" in data:
                    satellite.active_tasks = data["active_tasks"]

    def _on_task_submit(self, envelope):
        """Handle request to route a task to satellites."""
        data = self._extract_payload(envelope)

        # Find best available satellite
        best = self._find_best_satellite(
            requires_gpu=data.get("requires_gpu", False),
            min_memory_mb=data.get("min_memory_mb", 0),
        )

        if not best:
            # No satellite available - reply with failure
            reply_to = data.get("reply_to")
            if reply_to and self.post:
                self.post.publish(reply_to, {
                    "success": False,
                    "error": "No suitable satellite available",
                })
            return

        # Route to satellite
        if self.post:
            self.post.publish(f"satellite.{best.name}.task", {
                "task": data.get("task", {}),
                "reply_to": data.get("reply_to"),
            })

            best.active_tasks += 1
            self._tasks_routed += 1

    def _on_status_request(self, envelope):
        """Handle status request."""
        data = self._extract_payload(envelope)
        reply_to = data.get("reply_to") if data else None

        if reply_to and self.post:
            with self._lock:
                status = {
                    "satellites": {
                        name: {
                            "ip": s.ip,
                            "available": s.is_available,
                            "has_gpu": s.has_gpu,
                            "load": s.current_load,
                            "ping_ms": s.last_ping_ms,
                            "active_tasks": s.active_tasks,
                        }
                        for name, s in self._satellites.items()
                    },
                    "announces_sent": self._announces_sent,
                    "health_checks": self._health_checks,
                    "tasks_routed": self._tasks_routed,
                }

            self.post.publish(reply_to, status)

    # =========================================================================
    # ROUTING
    # =========================================================================

    def _find_best_satellite(
        self,
        requires_gpu: bool = False,
        min_memory_mb: float = 0
    ) -> Optional[SatelliteNode]:
        """Find the best available satellite for a task."""
        candidates = []

        with self._lock:
            for satellite in self._satellites.values():
                if not satellite.is_available:
                    continue

                if requires_gpu and not satellite.has_gpu:
                    continue

                if min_memory_mb > 0 and satellite.gpu_memory_mb < min_memory_mb:
                    continue

                # Score: lower load is better, more memory is better
                score = (1 - satellite.current_load) * 100 + satellite.gpu_memory_mb / 100
                candidates.append((score, satellite))

        if not candidates:
            return None

        # Return highest score
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def get_available_satellites(self) -> List[Dict[str, Any]]:
        """Get list of available satellites (for external use)."""
        with self._lock:
            return [
                s.to_announce_dict()
                for s in self._satellites.values()
                if s.is_available
            ]


# =============================================================================
# SINGLETON
# =============================================================================

_instance: Optional[SatelliteBridgeFairy] = None

def get_satellite_bridge(fabric=None) -> SatelliteBridgeFairy:
    """Get or create the singleton satellite bridge."""
    global _instance
    if _instance is None:
        _instance = SatelliteBridgeFairy(fabric)
    return _instance
