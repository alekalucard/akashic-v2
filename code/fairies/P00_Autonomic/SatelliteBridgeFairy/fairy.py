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
# Path: fairies/P00_Autonomic/SatelliteBridgeFairy/fairy.py → akashic_v2 (4 levels up)
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


@dataclass
class SatelliteNode:
    """A remote satellite node."""
    name: str
    ip: str
    port: int = 5000       # Node agent port (health checks, /health endpoint)
    http_port: int = 5757   # server.py HTTP port (/route, /command, /status)
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

    # SSH
    ssh_user: str = ""  # Set from network_config.json / peer_registry

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

    # Topics to forward from primary to satellites (somatic sync)
    SOMATIC_FORWARD_TOPICS = [
        "somatic.chemistry.changed",       # Body chemistry (DOP, SER, COR, etc.)
        "somatic.affect.changed",           # Emotional state
        "somatic.body.changed",             # Full body state
    ]

    # Rate limit somatic forwarding (don't flood satellites)
    _SOMATIC_FORWARD_MIN_INTERVAL = 2.0  # Min seconds between forwards per topic

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

        # Somatic forwarding rate limiter
        self._somatic_last_forward: Dict[str, float] = {}
        self._somatic_forwards_sent = 0

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

        # Ensure satellite daemons are running - IN BACKGROUND to not block boot
        # The health checker will also verify satellites periodically
        threading.Thread(
            target=self._ensure_satellites_running,
            daemon=True,
            name="satellite_startup"
        ).start()

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

            # Listen for reload requests (hot-reload config)
            self.post.subscribe(
                "satellite.reload",
                self._on_reload_request,
                f"{self.ACTOR_NAME}-reload"
            )

            # ═══════════════════════════════════════════════════════════
            # SOMATIC SYNC — Forward body state to satellites
            # This is how Sourpatches on two machines share one body.
            # The primary's somatic chemistry is the ground truth.
            # Satellites receive it and publish locally so their
            # Sourpatches (and all somatic-wired fairies) feel it.
            # ═══════════════════════════════════════════════════════════
            for somatic_topic in self.SOMATIC_FORWARD_TOPICS:
                self.post.subscribe(
                    somatic_topic,
                    lambda env, _t=somatic_topic: self._forward_to_satellites(_t, env),
                    f"{self.ACTOR_NAME}-somatic-{somatic_topic}"
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

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



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
                            "port": node_data.get("port", 8081),
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
                    http_port=peer_data.get("http_port", 5757),
                    role=peer_data.get("role", "compute"),
                    capabilities=capabilities,
                    has_gpu="gpu" in capabilities,
                    gpu_memory_mb=peer_data.get("gpu_memory_mb", 8000.0),
                    ssh_user=peer_data.get("ssh_user", ""),
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
    # SATELLITE STARTUP (SSH)
    # =========================================================================

    def _ensure_satellites_running(self):
        """
        Ensure satellite daemons are running on boot.

        For each satellite that's not responding, try to start it via SSH.
        This enables automatic recovery after system restarts.
        """
        import subprocess

        for name, satellite in self._satellites.items():
            if satellite.role == "primary":
                continue  # Skip self

            # Quick check if satellite is already responding
            if self._quick_health_check(satellite):
                print(f"[{self.ACTOR_NAME}] {name}: Already running")
                continue

            # Try to start via SSH
            print(f"[{self.ACTOR_NAME}] {name}: Not responding, attempting SSH start...")
            self._start_satellite_via_ssh(satellite)

    def _quick_health_check(self, satellite: SatelliteNode) -> bool:
        """Quick HTTP health check without full status update."""
        if not satellite.ip:
            return False

        try:
            import urllib.request
            url = f"http://{satellite.ip}:{satellite.port}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _start_satellite_via_ssh(self, satellite: SatelliteNode):
        """
        Start satellite via SSH.

        If ssh_user is set in peer_registry, uses that directly.
        Otherwise probes common usernames silently (BatchMode).

        The actual start command allows password prompts so Ace can
        type the password when the SSH popup appears.

        Prerequisites:
        - akashic_v2 deployed to ~/akashic_v2/ on the satellite
        """
        import subprocess

        if not satellite.ip:
            return

        # Skip if SSH was already determined to be unavailable
        if hasattr(satellite, 'ssh_available') and satellite.ssh_available is False:
            return

        # Get username from peer registry or default
        username = satellite.ssh_user or None
        if not username:
            # Try common usernames (silent probe — BatchMode suppresses prompts)
            for user in ['alaksander', 'ace', 'root', 'ubuntu']:
                try:
                    result = subprocess.run(
                        ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3',
                         f'{user}@{satellite.ip}', 'echo ok'],
                        capture_output=True, timeout=5
                    )
                    if result.returncode == 0:
                        username = user
                        # Save discovered username back to satellite
                        satellite.ssh_user = user
                        break
                except Exception:
                    continue

        if not username:
            satellite.ssh_available = False
            print(f"[{self.ACTOR_NAME}] {satellite.name}: SSH auth failed (no passwordless access). "
                  f"Set up SSH keys or set ssh_user in peer_registry.json.")
            return

        # Check if daemon is already running, if not start it
        # NOTE: No BatchMode=yes here — allows password prompt popup on Windows
        # NOTE: No capture_output — allows stdin passthrough for password entry
        try:
            print(f"[{self.ACTOR_NAME}] {satellite.name}: Starting via SSH ({username}@{satellite.ip})...")
            # Detect primary IP for --primary-ip flag
            primary_ip = self._get_primary_ip()
            primary_flag = f" --primary-ip {primary_ip}" if primary_ip else ""
            check_cmd = f"pgrep -f 'server.py --satellite' || cd ~/akashic_v2 && nohup python3 server.py --satellite{primary_flag} > /tmp/akashic_satellite.log 2>&1 &"
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=10',
                 f'{username}@{satellite.ip}', check_cmd],
                timeout=30  # Give time for password entry
            )

            if result.returncode == 0:
                print(f"[{self.ACTOR_NAME}] {satellite.name}: Daemon started via SSH as {username}")
                satellite.ssh_available = True
            else:
                print(f"[{self.ACTOR_NAME}] {satellite.name}: SSH start returned code {result.returncode}")

        except subprocess.TimeoutExpired:
            print(f"[{self.ACTOR_NAME}] {satellite.name}: SSH timeout (30s)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] {satellite.name}: SSH error: {e}")

    def _get_primary_ip(self) -> str:
        """Get this machine's LAN IP for --primary-ip flag."""
        # Try network_config.json first
        try:
            nc_path = self.SATELLITE_DIR / "network_config.json"
            if nc_path.exists():
                nc = json.loads(nc_path.read_text(encoding='utf-8'))
                this_node = nc.get("this_node", "")
                if this_node:
                    ip = nc.get("nodes", {}).get(this_node, {}).get("ip", "")
                    if ip and not ip.endswith(".x"):
                        return ip
        except Exception:
            pass
        # Auto-detect via socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return ""

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
        """
        Check if a satellite is reachable and get its status.

        Tries HTTP health check first (richer data), falls back to TCP ping.
        """
        if not satellite.ip:
            satellite.is_available = False
            return

        start = time.time()

        # Try HTTP health check first (satellite_daemon.py endpoint)
        if self._check_satellite_http(satellite, start):
            return

        # Fallback to TCP ping
        self._check_satellite_tcp(satellite, start)

    def _check_satellite_http(self, satellite: SatelliteNode, start: float) -> bool:
        """
        Check satellite via HTTP health endpoint.

        Handles multiple response formats:
        - Our satellite_daemon.py format (has load, gpu_memory_mb, is_available)
        - Existing Akashic server format (has status, node, fairies)

        Returns True if successful, False to fall back to TCP.
        """
        try:
            import urllib.request
            import urllib.error

            url = f"http://{satellite.ip}:{satellite.port}/health"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())

                    # Common updates
                    satellite.last_ping_ms = (time.time() - start) * 1000
                    satellite.last_heartbeat = time.time()

                    # Handle existing Akashic server format
                    if "status" in data and data.get("status") == "ok":
                        satellite.is_available = True
                        # These servers don't report load, assume available
                        satellite.current_load = data.get("load", 0.2)
                        fairy_count = data.get("fairies", 0)
                        print(f"[{self.ACTOR_NAME}] {satellite.name}: Akashic server OK ({fairy_count} fairies)")
                        return True

                    # Handle our satellite_daemon.py format
                    satellite.is_available = data.get("is_available", True)
                    satellite.current_load = data.get("load", 0.0)
                    satellite.active_tasks = data.get("active_tasks", 0)
                    satellite.completed_tasks = data.get("completed_tasks", 0)

                    # Update GPU info if present
                    if data.get("has_gpu"):
                        satellite.has_gpu = True
                        satellite.gpu_memory_mb = data.get("gpu_memory_mb", satellite.gpu_memory_mb)

                    print(f"[{self.ACTOR_NAME}] {satellite.name}: HTTP OK (load={satellite.current_load:.1%}, gpu={satellite.gpu_memory_mb:.0f}MB)")
                    return True

        except urllib.error.URLError:
            # HTTP not available, will fall back to TCP
            pass
        except Exception as e:
            # Log unexpected errors
            print(f"[{self.ACTOR_NAME}] {satellite.name}: HTTP check failed: {e}")

        return False

    def _check_satellite_tcp(self, satellite: SatelliteNode, start: float):
        """Check satellite via TCP socket ping."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((satellite.ip, satellite.port))
            sock.close()

            if result == 0:
                satellite.is_available = True
                satellite.last_ping_ms = (time.time() - start) * 1000
                satellite.last_heartbeat = time.time()
                # TCP ping succeeded but no rich data available
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

        # Satellite-acknowledgment 2026-06-25: satellites send `from_satellite`, not `name`
        # (satellite_postal_client._send_heartbeat). Read it; fall back to name for back-compat.
        name = data.get("from_satellite") or data.get("name")
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

    def _on_reload_request(self, envelope):
        """
        Hot-reload the peer registry.

        Call via postal: satellite.reload
        This allows reloading config without restarting the server.
        """
        print(f"[{self.ACTOR_NAME}] Reloading peer registry...")
        old_count = len(self._satellites)

        # Clear and reload
        with self._lock:
            self._satellites.clear()

        self._load_peer_registry()

        # Run health check immediately
        self._check_all_satellites()

        new_count = len(self._satellites)
        gpu_count = sum(1 for s in self._satellites.values() if s.has_gpu)

        print(f"[{self.ACTOR_NAME}] Reload complete: {old_count} -> {new_count} satellites ({gpu_count} with GPU)")

        # Announce the satellites
        self._announce_all_satellites()

        return {
            "ok": True,
            "old_count": old_count,
            "new_count": new_count,
            "gpu_count": gpu_count,
            "satellites": list(self._satellites.keys()),
        }

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
    # SOMATIC FORWARDING — Primary → Satellite body sync
    # =========================================================================

    def _forward_to_satellites(self, topic: str, envelope):
        """
        Forward a somatic postal message to all available satellites.

        This enables shared body state across nodes — when the primary's
        chemistry changes, satellites feel it too. Rate-limited to avoid
        flooding (somatic chemistry can fire every heartbeat).

        Runs HTTP POST in background threads to avoid blocking postal delivery.
        """
        import urllib.request
        import urllib.error

        # Rate limit: don't forward the same topic more often than every N seconds
        now = time.time()
        last = self._somatic_last_forward.get(topic, 0)
        if now - last < self._SOMATIC_FORWARD_MIN_INTERVAL:
            return
        self._somatic_last_forward[topic] = now

        # Extract payload from envelope
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
        elif isinstance(envelope, dict):
            payload = envelope.get("payload", envelope)
        else:
            payload = {"raw": str(envelope)}

        # Make payload JSON-serializable (borrow pattern from SatellitePostalClient)
        try:
            serializable = self._make_somatic_serializable(payload)
        except Exception:
            serializable = {"raw": str(payload)}

        # Forward to each available satellite (use http_port for server.py's /route)
        with self._lock:
            targets = [
                (s.name, s.ip, s.http_port)
                for s in self._satellites.values()
                if s.is_available and s.ip
            ]

        for sat_name, sat_ip, sat_port in targets:
            threading.Thread(
                target=self._do_somatic_forward,
                args=(sat_name, sat_ip, sat_port, topic, serializable),
                daemon=True,
            ).start()

    def _do_somatic_forward(self, name: str, ip: str, port: int, topic: str, payload: dict):
        """Send somatic HTTP POST to a satellite's /route endpoint. Background thread."""
        import urllib.request
        import urllib.error

        try:
            data = json.dumps({
                "topic": topic,
                "payload": payload,
                "from_node": "primary",
                "forwarded_at": time.time(),
            }).encode("utf-8")

            url = f"http://{ip}:{port}/route"
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=3.0)
            resp.read()  # Consume response
            self._somatic_forwards_sent += 1
        except Exception:
            pass  # Best-effort, non-blocking — satellite may be down

    @staticmethod
    def _make_somatic_serializable(obj) -> dict:
        """Make a somatic payload JSON-serializable."""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if isinstance(v, (str, int, float, bool, type(None))):
                    result[k] = v
                elif isinstance(v, (list, tuple)):
                    result[k] = [
                        x if isinstance(x, (str, int, float, bool, type(None))) else str(x)
                        for x in v
                    ]
                elif isinstance(v, dict):
                    result[k] = SatelliteBridgeFairy._make_somatic_serializable(v)
                else:
                    result[k] = str(v)
            return result
        return {"value": str(obj)}

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
