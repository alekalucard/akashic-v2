#!/usr/bin/env python3
"""
Satellite Daemon - Runs on remote compute nodes (e.g., Alienware)

Provides:
- HTTP health endpoint for heartbeat monitoring
- GPU/CPU load reporting
- Task reception and execution
- Heartbeat emission to primary node

Deploy to satellite:
    scp satellite_daemon.py user@alienware:/home/user/akashic/
    ssh user@alienware "python3 /home/user/akashic/satellite_daemon.py"

Or run as systemd service for persistence.

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"System seeks balance - distribute the load"
"""

import os
import sys
import time
import json
import socket
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
from pathlib import Path

# Configuration
SATELLITE_PORT = 5000
# Primary node IP - update if your primary's IP changes
# This Windows PC (DESKTOP-35L3DGQ) - get dynamically or set manually
PRIMARY_HOST = os.environ.get("AKASHIC_PRIMARY_HOST", "192.168.1.x")
PRIMARY_PORT = 5000
HEARTBEAT_INTERVAL = 10.0  # seconds
NODE_NAME = socket.gethostname()

# State
_current_task: Optional[str] = None
_active_tasks = 0
_completed_tasks = 0
_load = 0.0
_gpu_memory_mb = 0.0
_running = True


def get_gpu_info() -> Dict[str, Any]:
    """Get GPU information via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,name",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 4:
                return {
                    "available": True,
                    "utilization": float(parts[0]) / 100.0,
                    "memory_used_mb": float(parts[1]),
                    "memory_total_mb": float(parts[2]),
                    "name": parts[3].strip(),
                }
    except Exception as e:
        print(f"[SatelliteDaemon] GPU query failed: {e}")

    return {"available": False, "utilization": 0, "memory_used_mb": 0, "memory_total_mb": 0}


def get_cpu_load() -> float:
    """Get CPU load average."""
    try:
        # Linux load average
        with open("/proc/loadavg", "r") as f:
            load_1min = float(f.read().split()[0])
            cpu_count = os.cpu_count() or 1
            return min(1.0, load_1min / cpu_count)
    except Exception:
        pass

    try:
        import psutil
        return psutil.cpu_percent() / 100.0
    except ImportError:
        return 0.0


def build_status() -> Dict[str, Any]:
    """Build current satellite status."""
    global _load, _gpu_memory_mb

    gpu_info = get_gpu_info()
    cpu_load = get_cpu_load()

    # Combined load (prefer GPU load if available)
    if gpu_info["available"]:
        _load = gpu_info["utilization"]
        _gpu_memory_mb = gpu_info["memory_total_mb"] - gpu_info["memory_used_mb"]
    else:
        _load = cpu_load
        _gpu_memory_mb = 0

    return {
        "name": NODE_NAME,
        "timestamp": time.time(),
        "load": _load,
        "active_tasks": _active_tasks,
        "completed_tasks": _completed_tasks,
        "current_task": _current_task,
        "has_gpu": gpu_info["available"],
        "gpu_memory_mb": _gpu_memory_mb,
        "gpu": gpu_info,
        "cpu_load": cpu_load,
        "is_available": _load < 0.9,
    }


class SatelliteHandler(BaseHTTPRequestHandler):
    """HTTP request handler for satellite endpoints."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def _send_json(self, data: Dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health" or self.path == "/":
            # Health check endpoint
            status = build_status()
            self._send_json(status)

        elif self.path == "/status":
            # Detailed status
            status = build_status()
            status["uptime"] = time.time() - _start_time
            self._send_json(status)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        global _current_task, _active_tasks, _completed_tasks

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if self.path == "/task/submit":
            # Receive a task
            task_type = data.get("type", "unknown")
            task_id = data.get("task_id", f"task_{int(time.time())}")

            _current_task = task_id
            _active_tasks += 1

            # TODO: Actually process the task
            # For now, just acknowledge receipt
            print(f"[SatelliteDaemon] Received task: {task_type} ({task_id})")

            self._send_json({
                "success": True,
                "task_id": task_id,
                "message": f"Task received: {task_type}",
            })

        elif self.path == "/task/complete":
            # Task completion notification
            task_id = data.get("task_id")
            if task_id == _current_task:
                _current_task = None
                _active_tasks = max(0, _active_tasks - 1)
                _completed_tasks += 1

            self._send_json({"success": True})

        else:
            self._send_json({"error": "Not found"}, 404)


def heartbeat_loop():
    """Send periodic heartbeats to primary node."""
    global _running

    while _running:
        try:
            status = build_status()

            # Create heartbeat message
            heartbeat = {
                "type": "satellite.heartbeat",
                "payload": status,
            }

            # Try to send via HTTP to primary
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"http://{PRIMARY_HOST}:{PRIMARY_PORT}/satellite/heartbeat",
                    data=json.dumps(heartbeat).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                # Primary may not have HTTP endpoint, that's OK
                pass

        except Exception as e:
            print(f"[SatelliteDaemon] Heartbeat error: {e}")

        # Sleep in small chunks for responsive shutdown
        for _ in range(int(HEARTBEAT_INTERVAL * 10)):
            if not _running:
                break
            time.sleep(0.1)


def main():
    """Main entry point."""
    global _start_time, _running

    _start_time = time.time()

    print(f"""
================================================================
              AKASHIC SATELLITE DAEMON
================================================================
  Node: {NODE_NAME}
  Port: {SATELLITE_PORT}
  Primary: {PRIMARY_HOST}:{PRIMARY_PORT}

  Endpoints:
    GET  /health  - Health check (for SatelliteBridgeFairy)
    GET  /status  - Detailed status
    POST /task/submit - Submit task for execution

  "System seeks balance - distribute the load"
================================================================
""")

    # Check GPU
    gpu = get_gpu_info()
    if gpu["available"]:
        print(f"[SatelliteDaemon] GPU detected: {gpu.get('name', 'Unknown')}")
        print(f"[SatelliteDaemon] GPU Memory: {gpu['memory_total_mb']:.0f}MB")
    else:
        print("[SatelliteDaemon] No GPU detected - CPU-only mode")

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    print(f"[SatelliteDaemon] Heartbeat thread started (interval={HEARTBEAT_INTERVAL}s)")

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", SATELLITE_PORT), SatelliteHandler)
    print(f"[SatelliteDaemon] HTTP server listening on port {SATELLITE_PORT}")
    print(f"[SatelliteDaemon] Ready to receive tasks from primary node\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SatelliteDaemon] Shutting down...")
        _running = False
        server.shutdown()


if __name__ == "__main__":
    main()
