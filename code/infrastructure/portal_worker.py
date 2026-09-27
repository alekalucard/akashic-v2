"""
Portal Worker — Generic subprocess interior for any heavy resource.

This is the GENERALIZED version of portal_interior.py.
Any heavy resource (GPU model, embedding engine, large graph, vision model)
can be wrapped in a portal worker.

To create a new portal type, subclass PortalWorker and implement:
    - on_boot(): Load your heavy resource
    - handle(cmd, payload): Process requests
    - on_shutdown(): Cleanup

The worker handles all the plumbing:
    - stdin/stdout JSON protocol (same as PortalGate expects)
    - Heartbeat loop
    - Error handling
    - Graceful shutdown

NESTED PORTALS:
A worker can spawn its OWN sub-portals using PortalGate.
This is just importing PortalGate and calling gate.open().
The sub-portal gets its own subprocess, its own memory space.

Example:

    class GPUInferenceWorker(PortalWorker):
        def on_boot(self):
            self.model = load_rwkv_model(self.config["model_path"])
            # Nested portal: KV cache in its own subprocess
            self.kv_portal = PortalGate(
                cards_path="dummy",
                portal_id="kv_cache",
            )
            self.kv_portal.open()

        def handle(self, cmd, payload):
            if cmd == "generate":
                return self.model.generate(payload["prompt"])
            elif cmd == "cache_state":
                return self.kv_portal.send({"cmd": "save_state"})

Process tree:
    server.py (main, 90 fairies, ~2GB RAM, 0 VRAM)
     ├── portal_worker: gpu_inference (RWKV model, ~2GB VRAM)
     │    └── portal_worker: kv_cache (state management, ~500MB)
     ├── portal_worker: cortex (concept graph, ~200MB RAM)
     │    └── portal_worker: embeddings (sentence-transformers, ~1GB VRAM)
     └── portal_worker: vision (screenshot analysis, ~1GB VRAM)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import threading
import traceback
from pathlib import Path
from typing import Dict, Optional, Any


# All output goes to stderr (stdout is the JSON pipe)
def _log(msg: str):
    print(msg, file=sys.stderr, flush=True)


class PortalWorker:
    """Generic subprocess worker for heavy resources.

    Subclass and implement:
        on_boot()           -> Load your resource
        handle(cmd, payload) -> Process a request, return response dict
        on_shutdown()        -> Cleanup before exit

    The worker runs in a loop reading JSON from stdin, dispatching
    to handle(), and writing JSON to stdout.
    """

    WORKER_NAME = "PortalWorker"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._running = False
        self._boot_time = 0.0
        self._requests_handled = 0
        self._errors = 0
        self._sub_portals: Dict[str, Any] = {}  # Nested portals

    # ── Override these ──────────────────────────────────────

    def on_boot(self):
        """Load heavy resources here. Called once at start."""
        pass

    def handle(self, cmd: str, payload: Dict) -> Dict:
        """Handle a request. Return response dict.

        Built-in commands (ping, status, shutdown) are handled automatically.
        Override this for your custom commands.
        """
        return {"status": "error", "error": f"Unknown command: {cmd}"}

    def on_shutdown(self):
        """Cleanup before exit. Close files, free VRAM, etc."""
        pass

    # ── Nested portal support ──────────────────────────────

    def open_sub_portal(self, portal_id: str, interior_script: str,
                        config: Dict = None, timeout: float = 30.0) -> bool:
        """Open a nested sub-portal.

        Args:
            portal_id: Unique ID for this sub-portal
            interior_script: Path to the sub-portal's worker script
            config: Config dict passed to sub-portal via --config-json

        Returns:
            True if sub-portal booted successfully
        """
        try:
            from infrastructure.portal_gate import PortalGate
        except ImportError:
            # Try relative import (when running as subprocess)
            _here = Path(__file__).parent
            sys.path.insert(0, str(_here.parent))
            from infrastructure.portal_gate import PortalGate

        _log(f"[{self.WORKER_NAME}] Opening sub-portal '{portal_id}': {interior_script}")

        gate = PortalGate(
            cards_path="__none__",  # Sub-portals don't need cards
            portal_id=portal_id,
        )
        # Override the interior script to point at the nested worker
        gate._interior_script = interior_script

        if gate.open():
            self._sub_portals[portal_id] = gate
            _log(f"[{self.WORKER_NAME}] Sub-portal '{portal_id}' ONLINE")
            return True
        else:
            _log(f"[{self.WORKER_NAME}] Sub-portal '{portal_id}' FAILED to open")
            return False

    def send_to_sub(self, portal_id: str, request: Dict,
                    timeout: float = 10.0) -> Optional[Dict]:
        """Send a request to a nested sub-portal."""
        gate = self._sub_portals.get(portal_id)
        if not gate or not gate.is_open:
            return {"status": "error", "error": f"Sub-portal '{portal_id}' not open"}
        return gate.send(request, timeout=timeout)

    def close_sub_portal(self, portal_id: str):
        """Close a nested sub-portal."""
        gate = self._sub_portals.pop(portal_id, None)
        if gate:
            gate.close()
            _log(f"[{self.WORKER_NAME}] Sub-portal '{portal_id}' closed")

    # ── Main loop ──────────────────────────────────────────

    def run(self):
        """Main entry point. Boot, then enter request loop."""
        _log(f"[{self.WORKER_NAME}] Booting...")
        t0 = time.time()

        try:
            self.on_boot()
        except Exception as e:
            _log(f"[{self.WORKER_NAME}] BOOT FAILED: {e}")
            _log(traceback.format_exc())
            # Send error response and exit
            self._respond({"status": "error", "error": f"Boot failed: {e}"})
            return

        self._boot_time = time.time() - t0
        self._running = True
        _log(f"[{self.WORKER_NAME}] Booted in {self._boot_time:.2f}s. Ready.")

        # Enter request loop
        try:
            self._request_loop()
        except KeyboardInterrupt:
            _log(f"[{self.WORKER_NAME}] Interrupted.")
        finally:
            self._shutdown()

    def _request_loop(self):
        """Read requests from stdin, dispatch, write responses to stdout."""
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    # EOF — parent closed pipe
                    _log(f"[{self.WORKER_NAME}] stdin EOF — parent disconnected")
                    break

                line = line.strip()
                if not line:
                    continue

                request = json.loads(line)
                cmd = request.get("cmd", "")

                # Built-in commands
                if cmd == "ping":
                    self._respond({"status": "pong", "worker": self.WORKER_NAME})
                    continue

                elif cmd == "status":
                    self._respond(self._get_status())
                    continue

                elif cmd == "shutdown":
                    self._respond({"status": "ok", "message": "shutting down"})
                    break

                # Custom handler
                try:
                    result = self.handle(cmd, request)
                    self._requests_handled += 1
                    if result is None:
                        result = {"status": "ok"}
                    self._respond(result)
                except Exception as e:
                    self._errors += 1
                    _log(f"[{self.WORKER_NAME}] Handle error ({cmd}): {e}")
                    self._respond({"status": "error", "error": str(e)})

            except json.JSONDecodeError as e:
                _log(f"[{self.WORKER_NAME}] Bad JSON: {e}")
                self._respond({"status": "error", "error": f"Invalid JSON: {e}"})
            except Exception as e:
                _log(f"[{self.WORKER_NAME}] Loop error: {e}")
                self._respond({"status": "error", "error": str(e)})

    def _respond(self, data: Dict):
        """Write response to stdout (JSON line)."""
        try:
            line = json.dumps(data) + '\n'
            sys.stdout.write(line)
            sys.stdout.flush()
        except Exception as e:
            _log(f"[{self.WORKER_NAME}] Respond error: {e}")

    def _get_status(self) -> Dict:
        """Built-in status response."""
        status = {
            "status": "ok",
            "worker": self.WORKER_NAME,
            "uptime": time.time() - (self._boot_time + time.time() - self._boot_time)
                if self._boot_time else 0,
            "requests_handled": self._requests_handled,
            "errors": self._errors,
            "boot_time": self._boot_time,
            "sub_portals": {
                pid: {"open": g.is_open, "requests": g._requests_sent}
                for pid, g in self._sub_portals.items()
            } if self._sub_portals else {},
        }
        # Let subclass add custom status
        try:
            custom = self.get_status()
            if isinstance(custom, dict):
                status.update(custom)
        except Exception:
            pass
        return status

    def get_status(self) -> Dict:
        """Override to add custom status fields."""
        return {}

    def _shutdown(self):
        """Clean shutdown."""
        _log(f"[{self.WORKER_NAME}] Shutting down...")

        # Close all sub-portals
        for portal_id in list(self._sub_portals.keys()):
            self.close_sub_portal(portal_id)

        try:
            self.on_shutdown()
        except Exception as e:
            _log(f"[{self.WORKER_NAME}] Shutdown error: {e}")

        self._running = False
        _log(f"[{self.WORKER_NAME}] Shut down. "
             f"Handled {self._requests_handled} requests, {self._errors} errors.")


# ── CLI entry point for direct-run workers ──────────────────────────

def run_worker(worker_class, args=None):
    """Helper to run a PortalWorker subclass from CLI.

    Usage in your worker script:
        if __name__ == "__main__":
            run_worker(MyWorkerClass)
    """
    import argparse
    parser = argparse.ArgumentParser(description=f"Portal Worker: {worker_class.WORKER_NAME}")
    parser.add_argument("--config-json", default="{}", help="JSON config string")
    parser.add_argument("--cards", default="", help="Cards path (compat with PortalGate)")
    parser.add_argument("--mode", default="stdio", help="Communication mode")
    parser.add_argument("--host-port", type=int, default=0, help="Host port (compat)")
    parser.add_argument("--portal-id", default="", help="Portal ID (compat)")
    parser.add_argument("--manifold", default="", help="Manifold path (compat)")
    parser.add_argument("--token-budget", type=int, default=0, help="Token budget (compat)")

    parsed = parser.parse_args(args)

    config = {}
    try:
        config = json.loads(parsed.config_json)
    except json.JSONDecodeError:
        pass

    # Pass compat args into config
    if parsed.cards and parsed.cards != "__none__":
        config["cards_path"] = parsed.cards
    if parsed.portal_id:
        config["portal_id"] = parsed.portal_id
    if parsed.manifold:
        config["manifold_path"] = parsed.manifold
    if parsed.host_port:
        config["host_port"] = parsed.host_port

    worker = worker_class(config=config)
    worker.run()
