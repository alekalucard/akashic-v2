"""
GPUFleetFairy — Routes Inference Across Multiple GPUs

The Problem:
  We have 3 GPUs across 3 machines but only the desktop's 3080 Ti does inference.
  The laptops choke when running the full Akashic system. The complex satellite
  infrastructure never worked for actual GPU routing.

The Solution:
  One fairy. Simple routing. Remote machines run gpu_worker.py (lightweight,
  no Akashic overhead) and this fairy routes requests to the best GPU.

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │  Desktop (Primary)                                          │
  │  ┌──────────────────┐    ┌──────────────────────────┐      │
  │  │  GPUFleetFairy    │───>│  AkashicInferenceFairy   │      │
  │  │  (routes requests)│    │  (local GPU inference)    │      │
  │  └────────┬─────────┘    └──────────────────────────┘      │
  │           │                                                 │
  └───────────┼─────────────────────────────────────────────────┘
              │ HTTP
    ┌─────────┴──────────────────────────────────┐
    │                                             │
    ▼                                             ▼
  ┌───────────────────┐              ┌───────────────────┐
  │  Laptop 1          │              │  Laptop 2          │
  │  gpu_worker.py     │              │  gpu_worker.py     │
  │  RTX 3080          │              │  RTX 2060 Super    │
  └───────────────────┘              └───────────────────┘

Routing Strategy:
  1. LOCAL FIRST — Desktop 3080 Ti handles everything it can
  2. OVERFLOW — If local GPU queue > 2, route to least-busy remote
  3. PARALLEL — For batch requests, scatter across all GPUs
  4. FALLBACK — If all remotes dead, always use local

Postal Topics:
  Subscribes: fleet.generate          — Inference requests wanting fleet routing
              gpu_worker.heartbeat    — Worker health updates (from HTTP bridge)
  Publishes:  inference.generate      — Route to local AkashicInferenceFairy
              inference.complete      — Results (from remote workers)
              fleet.status            — Fleet health status

Created: 2026-02-20
Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"Distribute the load. Free the GPUs."
"""

import json
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

import sys
ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class GPUWorkerState:
    """Tracks a remote GPU worker's health."""
    name: str
    ip: str
    port: int = 5050

    # Health
    ready: bool = False
    busy: bool = False
    queue_depth: int = 0
    last_heartbeat: float = 0.0
    last_ping_ms: float = -1.0
    consecutive_failures: int = 0

    # GPU info
    gpu_name: str = "Unknown"
    gpu_memory_free_mb: float = 0
    gpu_memory_total_mb: float = 0
    gpu_utilization_pct: float = 0

    # Stats
    requests_sent: int = 0
    requests_completed: int = 0
    requests_failed: int = 0
    total_tokens: int = 0
    avg_tok_per_sec: float = 0.0

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    @property
    def is_alive(self) -> bool:
        """Worker considered alive if heartbeat within last 60s."""
        return (time.time() - self.last_heartbeat) < 60.0

    @property
    def is_available(self) -> bool:
        """Worker can accept requests."""
        return self.is_alive and self.ready and self.consecutive_failures < 5

    @property
    def load_score(self) -> float:
        """Lower = better. Used for routing decisions."""
        score = 0.0
        score += self.queue_depth * 10        # Queue depth matters most
        score += self.gpu_utilization_pct * 0.5  # GPU util
        if self.busy:
            score += 20
        if not self.is_alive:
            score += 1000
        return score


# ═══════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════

class GPUFleetFairy(Fairy):
    """Routes inference requests across a fleet of GPU workers."""

    ACTOR_NAME = "GPUFleetFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "hardware"
    ACTOR_TIER = "guild"

    PURPOSE = "Route inference across multiple GPUs for maximum throughput"
    MANTRA = "Distribute the load. Free the GPUs."

    # Config
    HEALTH_CHECK_INTERVAL = 15.0   # Seconds between health checks
    LOCAL_QUEUE_THRESHOLD = 2      # Route to remote if local queue > this
    WORKER_TIMEOUT = 30.0          # HTTP timeout for inference requests
    MAX_REMOTE_RETRIES = 2         # Retries before falling back to local

    def __init__(self, fabric=None, **kwargs):
        super().__init__(fabric=fabric, **kwargs)

        # Worker registry
        self._workers: Dict[str, GPUWorkerState] = {}
        self._workers_lock = threading.Lock()

        # Local GPU state
        self._local_queue_depth = 0
        self._local_busy = False

        # Stats
        self._requests_total = 0
        self._requests_local = 0
        self._requests_remote = 0
        self._requests_failed = 0

        # Config from file
        self._config_path = ROOT / ".satellite" / "gpu_fleet.json"
        self._load_config()

    def _load_config(self):
        """Load worker config from file."""
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    config = json.load(f)
                for w in config.get("workers", []):
                    name = w.get("name", f"{w['ip']}:{w.get('port', 5050)}")
                    self._workers[name] = GPUWorkerState(
                        name=name,
                        ip=w["ip"],
                        port=w.get("port", 5050),
                    )
                if self._workers:
                    print(f"[{self.ACTOR_NAME}] Loaded {len(self._workers)} workers from config")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Config load error: {e}")

    def on_boot(self):
        """Wire postal subscriptions and start health checker."""
        super().on_boot()

        if self.post:
            # Route-through inference requests
            self.post.subscribe("fleet.generate", self._on_fleet_generate)

            # Worker announcements (from gpu_worker.py heartbeats bridged to postal)
            self.post.subscribe("gpu_worker.announce", self._on_worker_announce)
            self.post.subscribe("gpu_worker.heartbeat", self._on_worker_heartbeat)

            # Local inference status tracking
            self.post.subscribe("inference.model.loaded", self._on_local_model_loaded)

        # Start background health checker
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name=f"{self.ACTOR_NAME}_Health"
        )
        self._health_thread.start()

        print(f"[{self.ACTOR_NAME}] Fleet routing ONLINE "
              f"({len(self._workers)} remote workers configured)")
        return True

    # ═══════════════════════════════════════════════════════════════
    # POSTAL HANDLERS
    # ═══════════════════════════════════════════════════════════════

    def _on_fleet_generate(self, message: Dict[str, Any]):
        """Route inference request to best available GPU."""
        self._requests_total += 1

        prompt = message.get("prompt", "")
        reply_topic = message.get("reply_topic", "inference.complete")

        if not prompt:
            if self.post:
                self.post.publish(reply_topic, {"error": "No prompt", "text": ""})
            return

        # Find best worker
        best_worker = self._select_worker()

        if best_worker is None:
            # No remote workers available — route to local
            self._route_local(message)
        else:
            # Try remote worker
            self._route_remote(message, best_worker)

    def _on_worker_announce(self, message: Dict[str, Any]):
        """A new GPU worker is announcing itself."""
        worker_data = message.get("worker", message)
        name = worker_data.get("name", "unknown")
        ip = worker_data.get("ip", "")
        port = worker_data.get("port", 5050)

        if not ip:
            return

        with self._workers_lock:
            if name not in self._workers:
                self._workers[name] = GPUWorkerState(name=name, ip=ip, port=port)
                print(f"[{self.ACTOR_NAME}] NEW worker discovered: {name} ({ip}:{port})")
            else:
                self._workers[name].ip = ip
                self._workers[name].port = port

            self._workers[name].last_heartbeat = time.time()
            gpu_info = worker_data.get("gpu", {})
            if gpu_info.get("available"):
                self._workers[name].gpu_name = gpu_info.get("name", "Unknown")
                self._workers[name].gpu_memory_total_mb = gpu_info.get("memory_total_mb", 0)
                self._workers[name].gpu_memory_free_mb = gpu_info.get("memory_free_mb", 0)

        # Save updated config
        self._save_config()

    def _on_worker_heartbeat(self, message: Dict[str, Any]):
        """Worker heartbeat update."""
        worker_data = message.get("worker", message)
        name = worker_data.get("name", "")

        with self._workers_lock:
            if name in self._workers:
                w = self._workers[name]
                w.last_heartbeat = time.time()
                w.ready = worker_data.get("ready", False)
                w.busy = worker_data.get("busy", False)
                w.queue_depth = worker_data.get("queue_depth", 0)
                w.gpu_memory_free_mb = worker_data.get("gpu_memory_free_mb", 0)
                w.gpu_utilization_pct = worker_data.get("gpu_utilization_pct", 0)
                w.consecutive_failures = 0  # Heartbeat = alive

    def _on_local_model_loaded(self, message: Dict[str, Any]):
        """Local AkashicInferenceFairy model is ready."""
        source = message.get("source", "unknown")
        print(f"[{self.ACTOR_NAME}] Local model loaded via {source}")

    # ═══════════════════════════════════════════════════════════════
    # ROUTING LOGIC
    # ═══════════════════════════════════════════════════════════════

    def _select_worker(self) -> Optional[GPUWorkerState]:
        """Select the best remote worker, or None to use local.

        Strategy:
        1. If no remote workers are available → None (use local)
        2. If local GPU queue is low → None (use local, zero latency)
        3. If remote workers have capacity → pick the one with lowest load
        """
        with self._workers_lock:
            available = [w for w in self._workers.values() if w.is_available]

        if not available:
            return None

        # Local GPU has capacity? Use it (zero network latency).
        if self._local_queue_depth <= self.LOCAL_QUEUE_THRESHOLD:
            return None

        # Pick least loaded remote worker
        available.sort(key=lambda w: w.load_score)
        return available[0]

    def _route_local(self, message: Dict[str, Any]):
        """Route request to local AkashicInferenceFairy via postal."""
        self._requests_local += 1
        if self.post:
            self.post.publish("inference.generate", message)

    def _route_remote(self, message: Dict[str, Any], worker: GPUWorkerState):
        """Route request to remote GPU worker via HTTP."""
        self._requests_remote += 1
        worker.requests_sent += 1

        reply_topic = message.get("reply_topic", "inference.complete")

        # Run in background thread to avoid blocking postal
        def _do_remote():
            result = self._http_generate(worker, message)
            if result is None:
                # Remote failed — fallback to local
                worker.requests_failed += 1
                worker.consecutive_failures += 1
                self._requests_failed += 1
                print(f"[{self.ACTOR_NAME}] Remote {worker.name} failed, falling back to local")
                self._route_local(message)
                return

            # Success
            worker.requests_completed += 1
            worker.consecutive_failures = 0
            worker.total_tokens += result.get("tokens_generated", 0)
            tok_sec = result.get("tokens_per_sec", 0)
            if tok_sec > 0:
                # Exponential moving average
                if worker.avg_tok_per_sec == 0:
                    worker.avg_tok_per_sec = tok_sec
                else:
                    worker.avg_tok_per_sec = 0.8 * worker.avg_tok_per_sec + 0.2 * tok_sec

            # Tag with worker name
            result["routed_to"] = worker.name
            result["route"] = "remote"

            # Publish result to requesting fairy
            if self.post:
                self.post.publish(reply_topic, result)

        t = threading.Thread(target=_do_remote, daemon=True, name=f"fleet-remote-{worker.name}")
        t.start()

    def _http_generate(self, worker: GPUWorkerState, request: Dict[str, Any]) -> Optional[Dict]:
        """Send inference request to remote worker via HTTP."""
        try:
            payload = json.dumps({
                "prompt": request.get("prompt", ""),
                "max_tokens": request.get("max_tokens", 128),
                "temperature": request.get("temperature", 0.8),
                "top_p": request.get("top_p", 0.9),
                "timeout": self.WORKER_TIMEOUT,
            }).encode()

            req = urllib.request.Request(
                f"{worker.url}/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            response = urllib.request.urlopen(req, timeout=self.WORKER_TIMEOUT)
            return json.loads(response.read().decode())

        except urllib.error.URLError as e:
            print(f"[{self.ACTOR_NAME}] Worker {worker.name} HTTP error: {e}")
            return None
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Worker {worker.name} error: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    # HEALTH CHECKING
    # ═══════════════════════════════════════════════════════════════

    def _health_check_loop(self):
        """Periodically check remote worker health."""
        # Wait for boot to settle
        time.sleep(10.0)

        while True:
            try:
                with self._workers_lock:
                    workers = list(self._workers.values())

                for worker in workers:
                    self._check_worker_health(worker)

                # Publish fleet status
                if self.post:
                    self.post.publish("fleet.status", self._build_status())

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Health check error: {e}")

            time.sleep(self.HEALTH_CHECK_INTERVAL)

    def _check_worker_health(self, worker: GPUWorkerState):
        """Ping a worker and update its state."""
        t0 = time.time()
        try:
            req = urllib.request.Request(
                f"{worker.url}/health",
                method="GET"
            )
            response = urllib.request.urlopen(req, timeout=5)
            data = json.loads(response.read().decode())

            worker.last_ping_ms = (time.time() - t0) * 1000
            worker.last_heartbeat = time.time()
            worker.ready = data.get("ready", False)
            worker.busy = data.get("busy", False)
            worker.queue_depth = data.get("queue_depth", 0)
            worker.gpu_name = data.get("gpu_name", worker.gpu_name)
            worker.gpu_memory_free_mb = data.get("gpu_memory_free_mb", 0)
            worker.gpu_memory_total_mb = data.get("gpu_memory_total_mb", 0)
            worker.gpu_utilization_pct = data.get("gpu_utilization_pct", 0)
            worker.consecutive_failures = 0

        except Exception:
            worker.last_ping_ms = -1
            worker.consecutive_failures += 1

    # ═══════════════════════════════════════════════════════════════
    # CONFIG PERSISTENCE
    # ═══════════════════════════════════════════════════════════════

    def _save_config(self):
        """Save worker registry to file."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with self._workers_lock:
                workers = [
                    {"name": w.name, "ip": w.ip, "port": w.port, "gpu_name": w.gpu_name}
                    for w in self._workers.values()
                ]
            with open(self._config_path, "w") as f:
                json.dump({"workers": workers, "updated": time.time()}, f, indent=2)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════

    def _build_status(self) -> Dict[str, Any]:
        """Build fleet status."""
        with self._workers_lock:
            workers = {}
            for name, w in self._workers.items():
                workers[name] = {
                    "ip": w.ip,
                    "port": w.port,
                    "alive": w.is_alive,
                    "available": w.is_available,
                    "ready": w.ready,
                    "busy": w.busy,
                    "queue_depth": w.queue_depth,
                    "gpu_name": w.gpu_name,
                    "gpu_memory_free_mb": w.gpu_memory_free_mb,
                    "gpu_utilization_pct": w.gpu_utilization_pct,
                    "ping_ms": round(w.last_ping_ms, 1),
                    "requests_sent": w.requests_sent,
                    "requests_completed": w.requests_completed,
                    "requests_failed": w.requests_failed,
                    "avg_tok_per_sec": round(w.avg_tok_per_sec, 1),
                }

        return {
            "workers": workers,
            "worker_count": len(workers),
            "workers_available": sum(1 for w in self._workers.values() if w.is_available),
            "stats": {
                "total_requests": self._requests_total,
                "local_requests": self._requests_local,
                "remote_requests": self._requests_remote,
                "failed_requests": self._requests_failed,
            },
            "ts": time.time(),
        }

    def status(self) -> Dict[str, Any]:
        """Override Fairy status for dashboard."""
        base = super().status() if hasattr(super(), 'status') else {}
        base.update(self._build_status())
        return base

    # ═══════════════════════════════════════════════════════════════
    # MCP ENDPOINT BRIDGE (receives HTTP heartbeats from gpu_workers)
    # ═══════════════════════════════════════════════════════════════

    def handle_http_announce(self, data: Dict[str, Any]):
        """Called by server.py HTTP handler when a worker announces."""
        self._on_worker_announce(data)

    def handle_http_heartbeat(self, data: Dict[str, Any]):
        """Called by server.py HTTP handler when a worker heartbeats."""
        self._on_worker_heartbeat(data)


# ═══════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════

_fleet_fairy: Optional[GPUFleetFairy] = None

def get_gpu_fleet() -> Optional[GPUFleetFairy]:
    """Get the global GPUFleetFairy instance if it exists."""
    return _fleet_fairy


# ═══════════════════════════════════════════════════════════════════
# BOOT EXPORTS
# ═══════════════════════════════════════════════════════════════════

ACTOR_NAME = "GPUFleetFairy"
FAIRY_CLASS = GPUFleetFairy
