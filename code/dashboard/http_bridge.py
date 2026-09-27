"""
HTTP Dashboard Bridge - Exposes UMF status to Tauri dashboard via HTTP.

The Tauri dashboard uses reqwest (HTTP) to connect, so we need an HTTP server.
This wraps the existing bridge functionality in HTTP endpoints.

Endpoints:
    GET  /status  - Returns full system state
    POST /command - Accepts commands (shutdown, restart, ping)
"""

import json
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy
    UnconsciousMindFairy = SomaticMindFairy

DEFAULT_PORT = 5757


class DashboardHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for dashboard endpoints."""

    # Class-level reference to UMF (set by HTTPDashboardBridge)
    umf: Optional["UnconsciousMindFairy"] = None

    def log_message(self, format, *args):
        """Suppress default logging - too noisy."""
        pass

    def handle_one_request(self):
        """Override to catch client disconnect errors silently.

        When clients disconnect mid-request (common with polling),
        we get ConnectionResetError which spams the console.
        """
        try:
            super().handle_one_request()
        except ConnectionResetError:
            # Client disconnected - this is normal, not an error
            pass
        except BrokenPipeError:
            # Client disconnected before we could write response
            pass
        except Exception as e:
            # Catch the Windows-specific "forcibly closed" error
            if "forcibly closed" in str(e).lower():
                pass
            else:
                raise

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/status" or self.path == "/":
            self._send_json(self._get_state())
        elif self.path == "/ping":
            self._send_json({"ok": True, "ts": time.time()})
        elif self.path == "/behavior_tree":
            self._send_json(self._get_behavior_tree())
        elif self.path == "/behavior_tree_mermaid":
            self._send_mermaid(self._get_behavior_tree_mermaid())
        else:
            self._send_json({"error": f"Unknown endpoint: {self.path}"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/command":
            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body) if body else {}
                action = data.get("action", "")

                if action == "shutdown":
                    self._send_json(self._handle_shutdown())
                elif action == "restart" or action == "reboot":
                    self._send_json(self._handle_restart())
                elif action == "ping":
                    self._send_json({"ok": True, "ts": time.time()})
                else:
                    self._send_json({"error": f"Unknown action: {action}"}, 400)

            except json.JSONDecodeError as e:
                self._send_json({"error": f"Invalid JSON: {e}"}, 400)
        else:
            self._send_json({"error": f"Unknown endpoint: {self.path}"}, 404)

    def _get_state(self) -> Dict[str, Any]:
        """Build the system state for the dashboard."""
        if not self.umf:
            return self._mock_state()

        try:
            status = self.umf.full_status()

            return {
                "connected": True,
                "consciousness": self._transform_consciousness(status),
                "hardware": self._transform_hardware(status),
                "helix": self._transform_helix(status),
                "drives": self._transform_drives(status),
                "fairies": self._transform_fairies(status),
                "thoughts": self._transform_thoughts(),
                "telemetry": self._transform_telemetry(status),
            }
        except Exception as e:
            print(f"[HTTPBridge] State error: {e}")
            return self._mock_state()

    def _transform_consciousness(self, status: Dict[str, Any]) -> Dict[str, Any]:
        c = status.get("consciousness", {})
        return {
            "wired": c.get("wired", False),
            "loopRunning": c.get("loop_running", False),
            "loopBeats": c.get("loop_beats", 0),
            "collisions": c.get("chamber_collisions", 0),
            "workingStream": c.get("working_stream", 0),
            "reflectiveStream": c.get("reflective_stream", 0),
        }

    def _transform_hardware(self, status: Dict[str, Any]) -> Dict[str, Any]:
        h = status.get("hardware", {})
        return {
            "cpuPercent": h.get("cpu_percent", 0.0),
            "ramPercent": h.get("ram_percent", 0.0),
            "gpuPercent": h.get("gpu_memory_percent", 0.0),
            "stressLevel": h.get("stress_level", "unknown"),
        }

    def _transform_helix(self, status: Dict[str, Any]) -> Dict[str, Any]:
        h = status.get("helix", {})
        weights = h.get("decision_weights", {})
        return {
            "active": h.get("active", False),
            "turns": h.get("turns", 0),
            "logic": weights.get("logic", 0.5),
            "emotion": weights.get("emotion", 0.3),
            "paradox": weights.get("paradox", 0.2),
        }

    def _transform_drives(self, status: Dict[str, Any]) -> Dict[str, Any]:
        profile = status.get("profile", {})
        pain = profile.get("pain", {}).get("levels", {})
        return {
            "isolation": pain.get("isolation", 0.0),
            "confusion": pain.get("confusion", 0.0),
            "depletion": pain.get("depletion", 0.0),
            "frustration": pain.get("frustration", 0.0),
            "stagnation": pain.get("stagnation", 0.0),
            "abandonment": pain.get("abandonment", 0.0),
        }

    def _transform_fairies(self, status: Dict[str, Any]) -> Dict[str, Any]:
        r = status.get("registration", {})
        by_status = r.get("fairies_by_status", {})

        fairy_list = []
        if self.umf:
            supervised = self.umf.get_supervised_fairies()
            for name, info in supervised.items():
                fairy_list.append({
                    "name": name,
                    "status": info.get("status", "unknown"),
                })

        return {
            "total": r.get("supervised_fairies", 0),
            "approved": by_status.get("approved", 0),
            "issues": len(r.get("recent_issues", [])),
            "pending": by_status.get("pending", 0),
            "list": fairy_list[:10],
        }

    def _transform_thoughts(self) -> list:
        """Get recent thoughts from consciousness working memory.

        Reads from the consciousness loop's working memory stream where
        the InnerNarratorFairy, collisions, and other real thought sources
        write. This replaces the old UMF TripleHelix template thoughts.
        """
        # Primary: consciousness loop working memory (real thoughts)
        try:
            from consciousness.loop import get_consciousness_loop
            cl = get_consciousness_loop()
            if cl and hasattr(cl, 'working') and cl.working:
                thoughts = list(cl.working)[-8:]
                result = []
                seen = set()
                for t in reversed(thoughts):
                    content = getattr(t, 'content', '') if hasattr(t, 'content') else str(t)
                    if not content or content in seen:
                        continue
                    seen.add(content)
                    source = getattr(t, 'source', 'unknown') if hasattr(t, 'source') else 'unknown'
                    thought_type = getattr(t, 'thought_type', 'working') if hasattr(t, 'thought_type') else 'working'
                    if source in ("inner_voice", "inner_narrator"):
                        thought_type = "inner_voice"
                    elif source == "narrator_executive":
                        thought_type = "executive"
                    result.append({
                        "type": thought_type,
                        "content": content[:200],
                    })
                    if len(result) >= 5:
                        break
                if result:
                    return result
        except Exception:
            pass

        # Fallback: UMF thoughts (legacy)
        if self.umf:
            thoughts = self.umf.get_thoughts(last_n=5)
            return [{"type": t.get("type", "idle"), "content": t.get("thought", "")} for t in thoughts]
        return []

    def _transform_telemetry(self, status: Dict[str, Any]) -> Dict[str, Any]:
        dead_fairies = []
        errors = []

        try:
            from directory import get_directory
            directory = get_directory()
            if directory:
                dead_list = directory.dead_fairies(threshold_seconds=60)
                for f in dead_list:
                    dead_fairies.append({
                        "name": f.get("name", "Unknown"),
                        "plane": f.get("plane", ""),
                        "age": f"{int(time.time() - f.get('last_heartbeat', 0))}s ago" if f.get("last_heartbeat") else "unknown"
                    })
        except Exception:
            pass

        if self.umf:
            supervised = self.umf._supervised_fairies if hasattr(self.umf, "_supervised_fairies") else {}
            for name, info in supervised.items():
                if info.get("status") == "dead":
                    death_time = info.get("death_time", 0)
                    restart_count = info.get("restart_count", 0)
                    errors.append({
                        "type": "fairy_death",
                        "fairy": name,
                        "restart_count": restart_count,
                        "ts": death_time * 1000,
                    })

        return {
            "deadFairies": dead_fairies,
            "errors": errors[-20:],
        }

    def _send_mermaid(self, mermaid_code: str, status: int = 200):
        """Send plain text Mermaid code response."""
        body = mermaid_code.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _get_behavior_tree(self) -> Dict[str, Any]:
        """Get behavior tree data as JSON for dashboard rendering."""
        try:
            import sys as _sys
            _root = Path(__file__).parent.parent
            _sys.path.insert(0, str(_root / "fairies" / "P40_Sensory" / "mcp"))
            from behavior_tree_tools import get_behavior_tree_data
            return get_behavior_tree_data()
        except Exception as e:
            return {"error": str(e), "drives": [], "goals": [], "interests": [],
                    "skills": [], "traits": {}, "achievements": [], "fairy_work": []}

    def _get_behavior_tree_mermaid(self) -> str:
        """Get behavior tree as Mermaid diagram code."""
        try:
            import sys as _sys
            _root = Path(__file__).parent.parent
            _sys.path.insert(0, str(_root / "fairies" / "P40_Sensory" / "mcp"))
            from behavior_tree_tools import generate_behavior_tree_mermaid
            return generate_behavior_tree_mermaid()
        except Exception as e:
            return f"graph TD\n    ERROR[\"{str(e)[:60]}\"]"

    def _mock_state(self) -> Dict[str, Any]:
        return {
            "connected": False,
            "consciousness": {
                "wired": False,
                "loopRunning": False,
                "loopBeats": 0,
                "collisions": 0,
                "workingStream": 0,
                "reflectiveStream": 0,
            },
            "hardware": {
                "cpuPercent": 0.0,
                "ramPercent": 0.0,
                "gpuPercent": 0.0,
                "stressLevel": "unknown",
            },
            "helix": {
                "active": False,
                "turns": 0,
                "logic": 0.5,
                "emotion": 0.3,
                "paradox": 0.2,
            },
            "drives": {
                "isolation": 0.0,
                "confusion": 0.0,
                "depletion": 0.0,
                "frustration": 0.0,
                "stagnation": 0.0,
                "abandonment": 0.0,
            },
            "fairies": {
                "total": 0,
                "approved": 0,
                "issues": 0,
                "pending": 0,
                "list": [],
            },
            "thoughts": [
                {"type": "idle", "content": "Waiting for UMF connection..."}
            ],
            "telemetry": {
                "deadFairies": [],
                "errors": [],
            },
        }

    def _handle_shutdown(self) -> Dict[str, Any]:
        import os
        import signal

        def do_shutdown():
            time.sleep(0.5)
            print("[HTTPBridge] Shutdown requested via dashboard")
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=do_shutdown, daemon=True).start()
        return {"ok": True, "message": "Shutdown initiated"}

    def _handle_restart(self) -> Dict[str, Any]:
        import subprocess
        import os
        import signal

        def do_restart():
            time.sleep(0.5)
            print("[HTTPBridge] Restart requested via dashboard")

            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            start_script = os.path.join(script_dir, "start_nous.bat")

            if os.path.exists(start_script):
                subprocess.Popen(
                    ["cmd", "/c", "start", "", start_script],
                    cwd=script_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )

            time.sleep(1.0)
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=do_restart, daemon=True).start()
        return {"ok": True, "message": "Restart initiated"}


class HTTPDashboardBridge:
    """
    HTTP Bridge between Python UMF and Tauri dashboard.

    Runs an HTTP server that responds to requests from the Rust backend.
    """

    def __init__(
        self,
        umf: "UnconsciousMindFairy" = None,
        port: int = DEFAULT_PORT,
        host: str = "127.0.0.1",
    ):
        self._umf = umf
        self._port = port
        self._host = host
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def set_umf(self, umf: "UnconsciousMindFairy") -> None:
        """Set or update the UMF reference."""
        self._umf = umf
        DashboardHTTPHandler.umf = umf

    def start(self) -> bool:
        """Start the HTTP server."""
        if self._running:
            return True

        try:
            # Set UMF on handler class
            DashboardHTTPHandler.umf = self._umf

            self._server = HTTPServer((self._host, self._port), DashboardHTTPHandler)
            self._running = True

            self._thread = threading.Thread(target=self._serve, daemon=True)
            self._thread.start()

            print(f"[HTTPBridge] Listening on http://{self._host}:{self._port}")
            return True

        except Exception as e:
            print(f"[HTTPBridge] Failed to start: {e}")
            return False

    def _serve(self):
        """Server loop."""
        while self._running:
            self._server.handle_request()

    def stop(self) -> None:
        """Stop the HTTP server."""
        self._running = False
        if self._server:
            self._server.shutdown()
        print("[HTTPBridge] Stopped")

    def status(self) -> Dict[str, Any]:
        """Get bridge status."""
        return {
            "running": self._running,
            "host": self._host,
            "port": self._port,
            "umf_connected": self._umf is not None,
        }


def create_http_bridge(
    umf: "UnconsciousMindFairy" = None,
    port: int = DEFAULT_PORT,
    auto_start: bool = True,
) -> HTTPDashboardBridge:
    """Create an HTTP dashboard bridge."""
    bridge = HTTPDashboardBridge(umf, port=port)
    if auto_start:
        bridge.start()
    return bridge


if __name__ == "__main__":
    print("Starting HTTP dashboard bridge in test mode...")
    bridge = create_http_bridge(auto_start=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
