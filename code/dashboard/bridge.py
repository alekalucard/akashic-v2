"""
Dashboard Bridge - Exposes UMF status to Tauri dashboard via TCP socket.

This is the connection between the Python brain and the Rust GUI.
Simple JSON over TCP protocol for reliability.

Usage:
    from dashboard.bridge import DashboardBridge

    bridge = DashboardBridge(umf)
    bridge.start()  # Starts server on port 5757
    # ... later
    bridge.stop()
"""

import json
import socket
import threading
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fairies.P20_Somatic.SomaticMindFairy import SomaticMindFairy
    UnconsciousMindFairy = SomaticMindFairy

# Default port for dashboard communication
DEFAULT_PORT = 5757


class DashboardBridge:
    """
    Bridge between Python UMF and Tauri dashboard.

    Runs a TCP server that responds to JSON requests from the Rust backend.
    Protocol:
    - Client connects
    - Client sends: {"command": "get_state"}\n
    - Server responds: {full state JSON}\n
    - Connection can stay open for multiple requests
    """

    def __init__(
        self,
        umf: "UnconsciousMindFairy" = None,
        port: int = DEFAULT_PORT,
        host: str = "127.0.0.1",
    ):
        """
        Initialize the dashboard bridge.

        Args:
            umf: The UnconsciousMindFairy to expose
            port: TCP port to listen on (default 5757)
            host: Host to bind to (default localhost)
        """
        self._umf = umf
        self._port = port
        self._host = host

        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._connections: list = []

    def set_umf(self, umf: "UnconsciousMindFairy") -> None:
        """Set or update the UMF reference."""
        self._umf = umf

    def start(self) -> bool:
        """
        Start the bridge server.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self._host, self._port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)  # Allow periodic check for shutdown

            self._running = True
            self._thread = threading.Thread(target=self._server_loop, daemon=True)
            self._thread.start()

            print(f"[DashboardBridge] Listening on {self._host}:{self._port}")
            return True

        except Exception as e:
            print(f"[DashboardBridge] Failed to start: {e}")
            return False

    def stop(self) -> None:
        """Stop the bridge server."""
        self._running = False

        # Close all client connections
        for conn in self._connections:
            try:
                conn.close()
            except:
                pass
        self._connections.clear()

        # Close server socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except:
                pass
            self._server_socket = None

        # Wait for thread
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        print("[DashboardBridge] Stopped")

    def _server_loop(self) -> None:
        """Main server loop - accepts connections and handles requests."""
        while self._running:
            try:
                client_socket, address = self._server_socket.accept()
                self._connections.append(client_socket)

                # Handle in new thread
                handler = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True,
                )
                handler.start()

            except socket.timeout:
                continue  # Check if still running
            except Exception as e:
                if self._running:
                    print(f"[DashboardBridge] Accept error: {e}")

    def _handle_client(self, client_socket: socket.socket, address) -> None:
        """Handle a client connection."""
        client_socket.settimeout(5.0)
        buffer = b""

        try:
            while self._running:
                # Read until newline
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break  # Client disconnected

                    buffer += data

                    # Process complete messages (newline-delimited)
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        self._process_request(client_socket, line)

                except socket.timeout:
                    continue  # Keep connection alive

        except Exception as e:
            if self._running:
                print(f"[DashboardBridge] Client error: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            if client_socket in self._connections:
                self._connections.remove(client_socket)

    def _process_request(self, client_socket: socket.socket, data: bytes) -> None:
        """Process a single request and send response."""
        try:
            request = json.loads(data.decode("utf-8"))
            command = request.get("command", "")

            if command == "get_state":
                response = self._get_state()
            elif command == "ping":
                response = {"ok": True, "ts": time.time()}
            elif command == "shutdown":
                response = self._handle_shutdown()
            elif command == "restart":
                response = self._handle_restart()
            elif command == "reboot":
                response = self._handle_restart()  # Alias for restart
            else:
                response = {"error": f"Unknown command: {command}"}

        except json.JSONDecodeError as e:
            response = {"error": f"Invalid JSON: {e}"}
        except Exception as e:
            response = {"error": str(e)}

        # Send response
        try:
            response_bytes = json.dumps(response).encode("utf-8") + b"\n"
            client_socket.sendall(response_bytes)
        except Exception as e:
            print(f"[DashboardBridge] Send error: {e}")

    def _get_state(self) -> Dict[str, Any]:
        """
        Build the system state for the dashboard.

        Transforms UMF full_status() into the format expected by Tauri.
        """
        if not self._umf:
            return self._mock_state()

        try:
            status = self._umf.full_status()

            # Transform to dashboard format
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
            print(f"[DashboardBridge] State error: {e}")
            return self._mock_state()

    def _transform_consciousness(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Transform consciousness status for dashboard."""
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
        """Transform hardware status for dashboard."""
        h = status.get("hardware", {})
        return {
            "cpuPercent": h.get("cpu_percent", 0.0),
            "ramPercent": h.get("ram_percent", 0.0),
            "gpuPercent": h.get("gpu_memory_percent", 0.0),
            "stressLevel": h.get("stress_level", "unknown"),
        }

    def _transform_helix(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Transform helix status for dashboard."""
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
        """Transform pain/drives status for dashboard."""
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
        """Transform fairy registration status for dashboard."""
        r = status.get("registration", {})
        by_status = r.get("fairies_by_status", {})

        # Get supervised fairies if UMF available
        fairy_list = []
        if self._umf:
            supervised = self._umf.get_supervised_fairies()
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
            "list": fairy_list[:10],  # Limit to 10 for display
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
                thoughts = list(cl.working)[-8:]  # Last 8 thoughts
                result = []
                seen = set()
                for t in reversed(thoughts):
                    content = getattr(t, 'content', '') if hasattr(t, 'content') else str(t)
                    if not content or content in seen:
                        continue
                    seen.add(content)
                    source = getattr(t, 'source', 'unknown') if hasattr(t, 'source') else 'unknown'
                    thought_type = getattr(t, 'thought_type', 'working') if hasattr(t, 'thought_type') else 'working'
                    # Tag inner voice thoughts specially
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
        if self._umf:
            thoughts = self._umf.get_thoughts(last_n=5)
            return [{"type": t.get("type", "idle"), "content": t.get("thought", "")} for t in thoughts]
        return []

    def _transform_telemetry(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Get error telemetry for dashboard."""
        dead_fairies = []
        errors = []

        # Get dead fairies from directory
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

        # Get recent errors from UMF supervised fairies
        if self._umf:
            supervised = self._umf._supervised_fairies if hasattr(self._umf, "_supervised_fairies") else {}
            for name, info in supervised.items():
                if info.get("status") == "dead":
                    death_time = info.get("death_time", 0)
                    restart_count = info.get("restart_count", 0)
                    errors.append({
                        "type": "fairy_death",
                        "fairy": name,
                        "restart_count": restart_count,
                        "ts": death_time * 1000,  # JS expects milliseconds
                    })

        return {
            "deadFairies": dead_fairies,
            "errors": errors[-20:],  # Last 20 errors
        }

    def _mock_state(self) -> Dict[str, Any]:
        """Return mock state when UMF not available."""
        now = int(time.time())
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
        """Handle shutdown command from dashboard."""
        import threading
        import os
        import signal

        def do_shutdown():
            time.sleep(0.5)  # Give time for response to send
            print("[DashboardBridge] Shutdown requested via dashboard")
            # Send SIGTERM to self to trigger graceful shutdown
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=do_shutdown, daemon=True).start()
        return {"ok": True, "message": "Shutdown initiated"}

    def _handle_restart(self) -> Dict[str, Any]:
        """Handle restart command from dashboard."""
        import threading
        import subprocess
        import os
        import signal

        def do_restart():
            time.sleep(0.5)  # Give time for response to send
            print("[DashboardBridge] Restart requested via dashboard")

            # Get the script that started this process
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            start_script = os.path.join(script_dir, "start_nous.bat")

            if os.path.exists(start_script):
                # Start new instance
                subprocess.Popen(
                    ["cmd", "/c", "start", "", start_script],
                    cwd=script_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )

            # Kill current instance
            time.sleep(1.0)
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=do_restart, daemon=True).start()
        return {"ok": True, "message": "Restart initiated"}

    def status(self) -> Dict[str, Any]:
        """Get bridge status."""
        return {
            "running": self._running,
            "host": self._host,
            "port": self._port,
            "connections": len(self._connections),
            "umf_connected": self._umf is not None,
        }


# Convenience function
def create_bridge(
    umf: "UnconsciousMindFairy" = None,
    port: int = DEFAULT_PORT,
    auto_start: bool = True,
) -> DashboardBridge:
    """
    Create a dashboard bridge.

    Args:
        umf: Optional UMF to connect
        port: TCP port (default 5757)
        auto_start: Start server immediately

    Returns:
        DashboardBridge instance
    """
    bridge = DashboardBridge(umf, port=port)
    if auto_start:
        bridge.start()
    return bridge


if __name__ == "__main__":
    # Test the bridge standalone
    print("Starting dashboard bridge in test mode...")
    bridge = create_bridge(auto_start=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
