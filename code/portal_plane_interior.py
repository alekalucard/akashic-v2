"""
Portal Plane Interior -- A subprocess that hosts an entire plane of fairies.

Part of the Russian Doll architecture:
  P00 (host) -> Portal -> P10 -> Portal -> P20 -> ... -> P60

Each plane portal is a subprocess with its own PostalHub. A PostalBridge
forwards publish/subscribe traffic across the stdin/stdout JSON pipe.

Protocol (same as portal_compute_interior.py):
  - stdin:  JSON-per-line requests from host
  - stdout: JSON-per-line responses/publishes to host
  - stderr: logging (human-readable)

Commands:
  {"cmd": "ping"}                    -> {"status": "pong", ...}
  {"cmd": "status"}                  -> {"status": "ok", "fairies": [...], ...}
  {"cmd": "postal", "topic": "...", "payload": {...}}  -> delivers to interior PostalHub
  {"cmd": "shutdown"}                -> graceful shutdown

Outbound (interior -> host):
  {"cmd": "postal_out", "topic": "...", "payload": {...}}  -> host re-publishes

Usage:
  python portal_plane_interior.py --plane P60_Executive

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import threading
import importlib
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════════
# Logging -- all logging goes to stderr. stdout is SACRED (JSON pipe only).
# ═══════════════════════════════════════════════════════════════════════════════

def _log(msg: str):
    """Log to stderr (never stdout -- that's the JSON pipe)."""
    print(msg, file=sys.stderr, flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# InteriorPostalHub -- PostalHub with outbound bridge
# ═══════════════════════════════════════════════════════════════════════════════

class InteriorPostalHub:
    """PostalHub that lives inside a plane portal subprocess.

    Same API as the real PostalHub (publish, subscribe, route) but with
    a twist: ALL publishes are ALSO forwarded to the host via stdout JSON.
    This is the bridge that lets interior fairies talk to the outside world.
    """

    def __init__(self, portal_id: str, outbound_fn=None):
        self._subscriptions: Dict[str, List] = defaultdict(list)
        self._lock = threading.RLock()
        self._message_count = 0
        self._portal_id = portal_id
        self._outbound_fn = outbound_fn  # Callable that sends JSON to host
        self._bridged_topics: set = set()  # Topics that came FROM host (don't echo back)

    def subscribe(self, topic: str, callback, name: str = None) -> bool:
        """Subscribe to a topic."""
        with self._lock:
            if callback not in self._subscriptions[topic.lower()]:
                self._subscriptions[topic.lower()].append(callback)
        return True

    def unsubscribe(self, topic: str, callback) -> bool:
        """Unsubscribe from a topic."""
        with self._lock:
            try:
                self._subscriptions[topic.lower()].remove(callback)
                return True
            except ValueError:
                return False

    def route(self, topic: str, payload: Dict[str, Any]) -> int:
        """Route a message to all local subscribers."""
        with self._lock:
            listeners = list(self._subscriptions.get(topic.lower(), []))
            self._message_count += 1

        delivered = 0
        for cb in listeners:
            try:
                cb(payload)
                delivered += 1
            except Exception as e:
                _log(f"[InteriorPostal] Error delivering to {topic}: {e}")
        return delivered

    def publish(self, topic: str, payload: Dict[str, Any]) -> int:
        """Publish locally AND bridge to host (if not already from host)."""
        # Deliver locally first
        delivered = self.route(topic, payload)

        # Bridge to host -- but ONLY if this publish originated inside the portal
        # (not if it came from the host via the bridge, which would cause infinite loops)
        _thread_id = threading.current_thread().ident
        if self._outbound_fn and not getattr(threading.current_thread(), '_from_host', False):
            try:
                self._outbound_fn({
                    "cmd": "postal_out",
                    "topic": topic,
                    "payload": self._make_serializable(payload),
                    "source_portal": self._portal_id,
                })
            except Exception as e:
                _log(f"[InteriorPostal] Outbound bridge error for {topic}: {e}")

        return delivered

    def to(self, topic: str, payload: Dict[str, Any]) -> int:
        """Alias for route (local only, no bridge)."""
        return self.route(topic, payload)

    # Convenience aliases matching real PostalHub
    def to_DIRECTORY(self, payload): return self.publish("directory", payload)
    def to_TELEMETRY(self, payload): return self.publish("telemetry", payload)
    def to_MEMORY(self, payload): return self.publish("memory.stream", payload)
    def to_TRACER(self, payload): return self.publish("tracer", payload)
    def to_COGNITION(self, payload): return self.publish("cognition.input", payload)
    def to_SOMATIC(self, payload): return self.publish("somatic.motor", payload)

    def get_subscribers(self, topic: str) -> list:
        with self._lock:
            return list(self._subscriptions.get(topic.lower(), []))

    @staticmethod
    def _make_serializable(obj):
        """Make a payload JSON-serializable (strip callables, convert sets, etc.)."""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                try:
                    json.dumps(v)
                    result[k] = v
                except (TypeError, ValueError):
                    if isinstance(v, set):
                        result[k] = list(v)
                    elif isinstance(v, (int, float, str, bool, type(None))):
                        result[k] = v
                    else:
                        result[k] = str(v)
            return result
        return obj

    def stats(self) -> Dict:
        with self._lock:
            return {
                "message_count": self._message_count,
                "topic_count": len(self._subscriptions),
                "topics": {t: len(cbs) for t, cbs in self._subscriptions.items() if cbs},
            }


# ═══════════════════════════════════════════════════════════════════════════════
# PlanePortalInterior -- The subprocess that hosts a plane
# ═══════════════════════════════════════════════════════════════════════════════

class PlanePortalInterior:
    """The interior of a plane portal -- boots fairies, bridges postal.

    This runs inside a subprocess. It creates its own PostalHub,
    boots all fairies from the specified plane, and bridges postal
    traffic to/from the host via stdin/stdout JSON pipes.
    """

    def __init__(self, plane: str, project_root: str,
                 sub_portal_specs: List = None, exclude_patterns: List = None):
        self.plane = plane
        self.project_root = Path(project_root)
        self._running = False
        self._stdout_lock = threading.Lock()  # Protect stdout writes
        self._booted_fairies: List[str] = []
        self._fairy_instances: Dict[str, Any] = {}
        self._boot_errors: List[str] = []
        self._boot_time = 0.0
        self._portal_id = f"plane_{plane.split('_')[0].lower()}"

        # CRITICAL: Save real stdin/stdout BEFORE fairy imports can hijack them.
        # SpeechCenterFairy imports the MCP server which may redirect sys.stdout.
        # We need the raw OS pipes for the JSON protocol to work.
        self._real_stdin = sys.stdin
        self._real_stdout = sys.stdout

        # Sub-portal support (Russian Doll nesting)
        # Each spec is (plane_full, plane_code) e.g. ("P60_Executive", "P60")
        self.sub_portal_specs: List = sub_portal_specs or []
        self._sub_portals: Dict[str, Any] = {}  # plane_code -> PlanePortalGate

        # Exclude patterns -- fairy dirs matching these are skipped
        # Used when a fairy must stay in the main process (e.g., Sourpatches)
        self.exclude_patterns: List[str] = exclude_patterns or []

        # Create our PostalHub with outbound bridge
        self.postal = InteriorPostalHub(
            portal_id=self._portal_id,
            outbound_fn=self._send_to_host,
        )

        # Portal battery (energy economy)
        self._energy = 1.0  # Start fully charged
        self._tick_count = 0

    def _send_to_host(self, message: Dict):
        """Send a JSON message to the host via stdout (the REAL pipe, not redirected)."""
        with self._stdout_lock:
            try:
                self._real_stdout.write(json.dumps(message) + '\n')
                self._real_stdout.flush()
            except Exception as e:
                _log(f"[PlaneInterior] stdout write error: {e}")

    # ─── Boot ────────────────────────────────────────────────────────────────

    def boot(self) -> bool:
        """Boot all fairies from this plane.

        Scans fairies/{plane}/ for fairy.py files, imports them,
        instantiates, wires PostalHub, and calls on_boot().
        """
        start = time.time()
        plane_dir = self.project_root / "fairies" / self.plane

        if not plane_dir.exists():
            _log(f"[PlaneInterior] ERROR: Plane dir not found: {plane_dir}")
            return False

        _log(f"[PlaneInterior] Booting plane {self.plane} from {plane_dir}")

        # Discover fairy directories
        fairy_dirs = []
        for item in sorted(plane_dir.iterdir()):
            if item.is_dir() and not item.name.startswith(('_', '.')):
                fairy_py = item / "fairy.py"
                if fairy_py.exists():
                    fairy_dirs.append(item)
                else:
                    # Check subdirectories (e.g., Waking Minds/Sourpatches/)
                    for sub in item.iterdir():
                        if sub.is_dir() and not sub.name.startswith(('_', '.')):
                            sub_fairy = sub / "fairy.py"
                            if sub_fairy.exists():
                                fairy_dirs.append(sub)

        _log(f"[PlaneInterior] Found {len(fairy_dirs)} fairy directories")

        # Filter out excluded dirs
        if self.exclude_patterns:
            original_count = len(fairy_dirs)
            filtered = []
            for fd in fairy_dirs:
                # Check against exclude patterns (match directory name or any parent dir name)
                excluded = False
                for pattern in self.exclude_patterns:
                    # Match fairy dir name or any ancestor relative to plane dir
                    rel_path = str(fd.relative_to(self.project_root / "fairies" / self.plane))
                    if pattern in rel_path or pattern == fd.name:
                        _log(f"[PlaneInterior]   EXCLUDED {fd.name} (matches '{pattern}')")
                        excluded = True
                        break
                if not excluded:
                    filtered.append(fd)
            fairy_dirs = filtered
            if original_count != len(fairy_dirs):
                _log(f"[PlaneInterior] After exclusions: {len(fairy_dirs)} fairy directories "
                     f"({original_count - len(fairy_dirs)} excluded)")

        # Boot each fairy
        for fairy_dir in fairy_dirs:
            fairy_name = fairy_dir.name
            try:
                self._boot_one_fairy(fairy_dir, fairy_name)
            except Exception as e:
                err = f"{fairy_name}: {e}"
                self._boot_errors.append(err)
                _log(f"[PlaneInterior] FAILED to boot {fairy_name}: {e}")
                _log(traceback.format_exc())

        self._boot_time = time.time() - start
        _log(f"[PlaneInterior] Plane {self.plane} booted: "
             f"{len(self._booted_fairies)} fairies in {self._boot_time:.1f}s "
             f"({len(self._boot_errors)} errors)")

        # Open sub-portals (Russian Doll nesting)
        if self.sub_portal_specs:
            _log(f"[PlaneInterior] Opening {len(self.sub_portal_specs)} sub-portal(s)...")
            for sp_plane_full, sp_plane_code in self.sub_portal_specs:
                try:
                    gate = PlanePortalGate(
                        plane=sp_plane_full,
                        project_root=str(self.project_root),
                        boot_timeout=30.0,
                    )
                    if gate.open(host_postal=self.postal):
                        self._sub_portals[sp_plane_code] = gate
                        _log(f"[PlaneInterior] Sub-portal opened: {sp_plane_code} "
                             f"({len(gate._booted_fairies)} fairies)")
                    else:
                        _log(f"[PlaneInterior] Sub-portal FAILED: {sp_plane_code}")
                        self._boot_errors.append(f"sub-portal {sp_plane_code} failed to open")
                except Exception as e:
                    _log(f"[PlaneInterior] Sub-portal error ({sp_plane_code}): {e}")
                    self._boot_errors.append(f"sub-portal {sp_plane_code}: {e}")

        return True

    def _boot_one_fairy(self, fairy_dir: Path, fairy_name: str):
        """Import, instantiate, wire, and boot a single fairy."""
        fairy_py = fairy_dir / "fairy.py"
        _log(f"[PlaneInterior]   Booting {fairy_name}...")

        # Add project root and fairy parent to sys.path
        _root_str = str(self.project_root)
        if _root_str not in sys.path:
            sys.path.insert(0, _root_str)

        _parent_str = str(fairy_dir.parent)
        if _parent_str not in sys.path:
            sys.path.insert(0, _parent_str)

        # Import the fairy module
        spec = importlib.util.spec_from_file_location(
            f"portal_fairy.{fairy_name}.fairy",
            str(fairy_py),
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod  # Must be before exec for @dataclass
        spec.loader.exec_module(mod)

        # Find the fairy class
        cls = getattr(mod, 'FAIRY_CLASS', None)
        if cls is None:
            cls = getattr(mod, fairy_name, None)
        if cls is None:
            # Search for any class with ACTOR_NAME
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if isinstance(obj, type) and hasattr(obj, 'ACTOR_NAME'):
                    cls = obj
                    break

        if cls is None:
            raise ValueError(f"No fairy class found in {fairy_py}")

        # Instantiate
        try:
            instance = cls()
        except TypeError:
            # Some fairies need arguments
            instance = cls.__new__(cls)

        # Wire PostalHub
        if hasattr(instance, 'post'):
            instance.post = self.postal
        if hasattr(instance, '_post'):
            instance._post = self.postal

        # Call on_boot
        if hasattr(instance, 'on_boot'):
            try:
                boot_result = instance.on_boot()
                # Handle async on_boot
                if hasattr(boot_result, '__await__'):
                    import asyncio
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(boot_result)
                    loop.close()
            except Exception as e:
                _log(f"[PlaneInterior]   {fairy_name}.on_boot() error: {e}")

        self._fairy_instances[fairy_name] = instance
        self._booted_fairies.append(fairy_name)
        _log(f"[PlaneInterior]   [OK] {fairy_name} booted")

    # ─── Request Processing ──────────────────────────────────────────────────

    def process_request(self, request: Dict) -> Dict:
        """Process a request from the host."""
        cmd = request.get("cmd", "")

        if cmd == "ping":
            return {"status": "pong", "portal_id": self._portal_id, "plane": self.plane}

        elif cmd == "status":
            result = {
                "status": "ok",
                "portal_id": self._portal_id,
                "plane": self.plane,
                "fairies": self._booted_fairies,
                "fairy_count": len(self._booted_fairies),
                "errors": self._boot_errors,
                "boot_time": self._boot_time,
                "energy": self._energy,
                "ticks": self._tick_count,
                "postal": self.postal.stats(),
                "pid": os.getpid(),
            }
            # Include sub-portal status
            if self._sub_portals:
                sub_status = {}
                for pc, gate in self._sub_portals.items():
                    try:
                        sub_status[pc] = gate.send({"cmd": "status"}, timeout=5.0) or {"status": "timeout"}
                    except Exception:
                        sub_status[pc] = {"status": "error"}
                result["sub_portals"] = sub_status
            return result

        elif cmd == "postal":
            # Deliver a postal message from host into interior
            topic = request.get("topic", "")
            payload = request.get("payload", {})
            if topic:
                # Mark this thread as "from host" so the bridge doesn't echo it back
                threading.current_thread()._from_host = True
                try:
                    delivered = self.postal.route(topic, payload)
                finally:
                    threading.current_thread()._from_host = False
                return {"status": "ok", "delivered": delivered, "topic": topic}
            return {"status": "error", "message": "Missing topic"}

        elif cmd == "energy":
            amount = request.get("amount", 0.1)
            self._energy = min(1.0, self._energy + amount)
            return {"status": "ok", "energy": self._energy}

        elif cmd == "tick":
            self._tick_count += 1
            self._energy = max(0.0, self._energy - 0.001)  # Slow drain
            return {"status": "ok", "tick": self._tick_count, "energy": self._energy}

        elif cmd == "shutdown":
            _log(f"[PlaneInterior] Shutdown requested")
            self._running = False
            return {"status": "ok", "message": "shutting_down"}

        elif cmd == "fairy_status":
            # Get status of a specific fairy
            name = request.get("name", "")
            inst = self._fairy_instances.get(name)
            if inst and hasattr(inst, 'get_status'):
                try:
                    return {"status": "ok", "fairy_status": inst.get_status()}
                except Exception as e:
                    return {"status": "error", "message": str(e)}
            return {"status": "error", "message": f"Unknown fairy: {name}"}

        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    # ─── Main Loop ───────────────────────────────────────────────────────────

    def run_stdio(self):
        """Run the plane interior reading from real stdin, writing to real stdout.

        Uses _real_stdin/_real_stdout saved at init to survive stdout hijacking
        by imported modules (e.g., MCP server captures sys.stdout).
        """
        self._running = True
        _log(f"[PlaneInterior] Entering stdio loop (pid={os.getpid()}, plane={self.plane})")

        # Background tick thread
        tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        tick_thread.start()

        for line in self._real_stdin:
            if not self._running:
                break
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.process_request(request)
                # Send response via REAL stdout (not redirected sys.stdout)
                with self._stdout_lock:
                    self._real_stdout.write(json.dumps(response) + '\n')
                    self._real_stdout.flush()
                if not self._running:
                    break
            except json.JSONDecodeError as e:
                with self._stdout_lock:
                    self._real_stdout.write(json.dumps({"status": "error", "message": f"JSON parse: {e}"}) + '\n')
                    self._real_stdout.flush()
            except Exception as e:
                _log(f"[PlaneInterior] Request error: {e}")
                with self._stdout_lock:
                    self._real_stdout.write(json.dumps({"status": "error", "message": str(e)}) + '\n')
                    self._real_stdout.flush()

        _log(f"[PlaneInterior] Stdio loop ended")
        self.shutdown()

    def _tick_loop(self):
        """Background heartbeat."""
        while self._running:
            try:
                time.sleep(1.0)
                self._tick_count += 1
                self._energy = max(0.0, self._energy - 0.0005)  # Very slow drain
            except Exception:
                pass

    def shutdown(self):
        """Graceful shutdown -- close sub-portals first, then stop local fairies."""
        _log(f"[PlaneInterior] Shutting down plane {self.plane}...")
        self._running = False

        # Close sub-portals FIRST (innermost shuts down before outer)
        if self._sub_portals:
            _log(f"[PlaneInterior] Closing {len(self._sub_portals)} sub-portal(s)...")
            for pc, gate in list(self._sub_portals.items()):
                try:
                    gate.close()
                    _log(f"[PlaneInterior] Sub-portal {pc} closed")
                except Exception as e:
                    _log(f"[PlaneInterior] Error closing sub-portal {pc}: {e}")
            self._sub_portals.clear()

        # Call shutdown on each local fairy
        for name, inst in self._fairy_instances.items():
            try:
                if hasattr(inst, 'shutdown'):
                    inst.shutdown()
                elif hasattr(inst, 'on_shutdown'):
                    inst.on_shutdown()
            except Exception as e:
                _log(f"[PlaneInterior] Error shutting down {name}: {e}")

        _log(f"[PlaneInterior] Plane {self.plane} shutdown complete")


# ═══════════════════════════════════════════════════════════════════════════════
# PlanePortalGate -- The host-side gate that spawns and bridges to a plane portal
# ═══════════════════════════════════════════════════════════════════════════════

class PlanePortalGate:
    """Host-side gate for a plane portal subprocess.

    Spawns portal_plane_interior.py as a subprocess, bridges postal
    traffic bidirectionally, and monitors the portal's health.

    Usage (in server.py):
        gate = PlanePortalGate(
            plane="P60_Executive",
            project_root="F:/Sandbox/failure_factory/akashic_v2",
        )
        gate.open(host_postal=PostalHub())
        # P60 fairies are now running inside the portal subprocess
        # All postal traffic is automatically bridged
    """

    def __init__(
        self,
        plane: str,
        project_root: str = "",
        python_exe: str = None,
        boot_timeout: float = 60.0,
        sub_portals: List = None,
        exclude: List = None,
    ):
        self.plane = plane
        self.plane_code = plane.split("_")[0]  # "P60"
        self.project_root = project_root or str(Path(__file__).parent)
        self.python_exe = python_exe or sys.executable
        self.boot_timeout = boot_timeout

        # Sub-portals this gate should tell the interior to open
        # Each is (plane_full, plane_code) e.g. ("P60_Executive", "P60")
        self.sub_portals: List = sub_portals or []

        # Fairy dir patterns to exclude from boot in the interior
        self.exclude: List[str] = exclude or []

        self._process: Optional[subprocess.Popen] = None
        self._is_open = False
        self._lock = threading.Lock()
        self._stdout_lock = threading.Lock()
        self._host_postal = None

        # Booted fairies list (populated after open() succeeds)
        self._booted_fairies: List[str] = []

        # Stats
        self._opened_at = 0.0
        self._requests_sent = 0
        self._postal_in = 0   # Messages bridged host -> interior
        self._postal_out = 0  # Messages bridged interior -> host

        # Response queue for synchronous send()
        self._response_queue = None

        # Track what topics the interior subscribes to (for future optimization)
        self._interior_fairies: List[str] = []

    def open(self, host_postal=None) -> bool:
        """Open the gate -- spawn the plane portal subprocess.

        Args:
            host_postal: The host's PostalHub to bridge traffic to/from.

        Returns True if the portal booted and responded to ping.
        """
        if self._is_open:
            return True

        self._host_postal = host_postal
        import subprocess as _sp

        # Build command
        script = str(Path(__file__))
        cmd = [
            self.python_exe,
            "-u",  # Unbuffered stdout -- critical for pipe protocol
            script,
            "--plane", self.plane,
            "--project-root", self.project_root,
        ]

        # Pass sub-portal specs to interior (Russian Doll nesting)
        if self.sub_portals:
            # Format: "P60_Executive:P60,P70_Whatever:P70"
            sp_str = ",".join(f"{pf}:{pc}" for pf, pc in self.sub_portals)
            cmd += ["--sub-portals", sp_str]

        # Pass exclude patterns to interior
        if self.exclude:
            cmd += ["--exclude", ",".join(self.exclude)]

        print(f"[PlaneGate:{self.plane_code}] Opening portal for {self.plane}...")
        print(f"[PlaneGate:{self.plane_code}] Spawning: {' '.join(cmd[:4])}...")

        try:
            env = os.environ.copy()
            # Inherit AKASHIC_SKIP_TORCH and other env vars
            existing_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = self.project_root + (os.pathsep + existing_path if existing_path else "")

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = 0x08000000  # CREATE_NO_WINDOW

            self._process = _sp.Popen(
                cmd,
                stdin=_sp.PIPE,
                stdout=_sp.PIPE,
                stderr=_sp.PIPE,
                env=env,
                bufsize=1,
                text=True,
                creationflags=creation_flags,
            )
        except Exception as e:
            print(f"[PlaneGate:{self.plane_code}] Failed to spawn: {e}")
            return False

        # Start stderr reader
        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True,
            name=f"PlaneGate-{self.plane_code}-stderr"
        )
        self._stderr_thread.start()

        # Start stdout reader (handles both responses and postal_out messages)
        import queue
        self._response_queue = queue.Queue()
        self._stdout_thread = threading.Thread(
            target=self._read_stdout, daemon=True,
            name=f"PlaneGate-{self.plane_code}-stdout"
        )
        self._stdout_thread.start()

        # Wait for boot + ping
        print(f"[PlaneGate:{self.plane_code}] Waiting for portal boot (timeout={self.boot_timeout}s)...")
        time.sleep(1.0)  # Give subprocess time to import and boot

        ping_result = self.send({"cmd": "ping"}, timeout=self.boot_timeout)
        if ping_result and ping_result.get("status") == "pong":
            self._is_open = True
            self._opened_at = time.time()

            # Get status to know which fairies booted
            status = self.send({"cmd": "status"}, timeout=10.0)
            if status:
                self._interior_fairies = status.get("fairies", [])
                self._booted_fairies = list(self._interior_fairies)
                boot_time = status.get("boot_time", 0)
                errors = status.get("errors", [])
                # Include sub-portal fairies in the count
                sub_status = status.get("sub_portals", {})
                sub_fairy_count = 0
                for sp_code, sp_info in sub_status.items():
                    if isinstance(sp_info, dict):
                        sp_fairies = sp_info.get("fairies", [])
                        sub_fairy_count += len(sp_fairies)
                        self._booted_fairies.extend(sp_fairies)
                total_str = f"{len(self._interior_fairies)} local"
                if sub_fairy_count:
                    total_str += f" + {sub_fairy_count} in sub-portals"
                print(f"[PlaneGate:{self.plane_code}] Portal ONLINE -- "
                      f"{total_str} fairies in {boot_time:.1f}s")
                if errors:
                    for err in errors:
                        print(f"[PlaneGate:{self.plane_code}]   [WARN] {err}")

            # Wire postal bridge (host -> interior)
            if self._host_postal:
                self._wire_postal_bridge()

            return True
        else:
            print(f"[PlaneGate:{self.plane_code}] Portal failed to respond: {ping_result}")
            self.close()
            return False

    def _wire_postal_bridge(self):
        """Wire the host PostalHub to forward relevant messages into the portal.

        Strategy: Subscribe to ALL topics on the host PostalHub with a wildcard-like
        approach. When a message is published on the host, forward it into the portal.

        We use a monkey-patch on the host's publish() to intercept ALL publishes.
        This is cleaner than subscribing to every individual topic.
        """
        if not self._host_postal:
            return

        original_publish = self._host_postal.publish
        gate_ref = self  # Closure reference

        def bridged_publish(topic, payload):
            """Publish locally AND forward into the portal."""
            # First, publish on host as normal
            result = original_publish(topic, payload)

            # Then forward to interior (if portal is open and message isn't FROM interior)
            if (gate_ref._is_open
                    and (not isinstance(payload, dict)
                         or payload.get("_from_portal") != gate_ref.plane_code)):
                try:
                    # Don't bridge if this came from the portal (prevent loops)
                    source = payload.get("source_portal", "") if isinstance(payload, dict) else ""
                    if source != gate_ref._portal_id:
                        gate_ref._send_postal_to_interior(topic, payload)
                except Exception:
                    pass

            return result

        self._host_postal.publish = bridged_publish
        self._original_publish = original_publish  # Save for cleanup
        self._portal_id = f"plane_{self.plane_code.lower()}"

        print(f"[PlaneGate:{self.plane_code}] Postal bridge wired (host -> interior)")

    def _send_postal_to_interior(self, topic: str, payload):
        """Send a postal message from host into the portal interior."""
        if not self._is_open or not self._process:
            return
        try:
            safe_payload = self._make_serializable(payload)
            msg = json.dumps({
                "cmd": "postal",
                "topic": topic,
                "payload": safe_payload,
            })
            with self._stdout_lock:
                self._process.stdin.write(msg + '\n')
                self._process.stdin.flush()
            self._postal_in += 1
        except (TypeError, ValueError) as e:
            # Non-serializable payload -- log but don't crash bridge
            print(f"[PlaneGate:{self.plane_code}] Serialization warning on '{topic}': {e}",
                  file=sys.stderr)
        except Exception as e:
            print(f"[PlaneGate:{self.plane_code}] Bridge write error: {e}", file=sys.stderr)

    def _read_stdout(self):
        """Read stdout from the portal subprocess.

        Handles two types of messages:
        1. Responses to our send() calls -> put in response_queue
        2. postal_out messages -> re-publish on host PostalHub
        """
        try:
            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if msg.get("cmd") == "postal_out":
                    # Bridge: interior -> host
                    topic = msg.get("topic", "")
                    payload = msg.get("payload", {})
                    if topic and self._host_postal:
                        # Mark as from portal to prevent echo loops
                        if isinstance(payload, dict):
                            payload["_from_portal"] = self.plane_code
                        try:
                            # Use the ORIGINAL publish (not the bridged one)
                            if hasattr(self, '_original_publish'):
                                self._original_publish(topic, payload)
                            elif self._host_postal:
                                self._host_postal.route(topic, payload)
                        except Exception as e:
                            print(f"[PlaneGate:{self.plane_code}] postal_out error: {e}",
                                  file=sys.stderr)
                        self._postal_out += 1
                else:
                    # Response to a send() call
                    if self._response_queue:
                        self._response_queue.put(msg)
        except Exception as e:
            if self._is_open:
                print(f"[PlaneGate:{self.plane_code}] stdout reader error: {e}", file=sys.stderr)

    def _read_stderr(self):
        """Read and forward stderr from portal subprocess."""
        prefix = f"[Portal:{self.plane_code}]"
        try:
            for line in self._process.stderr:
                line = line.rstrip('\n\r')
                if line:
                    print(f"{prefix} {line}", flush=True)
        except Exception:
            pass

    def send(self, request: Dict, timeout: float = 10.0) -> Optional[Dict]:
        """Send a request to the portal and wait for response."""
        if not self._process or self._process.poll() is not None:
            return None

        try:
            msg = json.dumps(request) + '\n'
            with self._stdout_lock:
                self._process.stdin.write(msg)
                self._process.stdin.flush()
            self._requests_sent += 1
        except Exception as e:
            print(f"[PlaneGate:{self.plane_code}] send error: {e}")
            return None

        # Wait for response
        try:
            response = self._response_queue.get(timeout=timeout)
            return response
        except Exception:
            return None

    def close(self):
        """Close the gate -- terminate the portal subprocess."""
        if not self._process:
            return

        print(f"[PlaneGate:{self.plane_code}] Closing portal...")
        self._is_open = False

        # Restore original publish if we monkey-patched
        if hasattr(self, '_original_publish') and self._host_postal:
            self._host_postal.publish = self._original_publish

        # Send shutdown
        try:
            self.send({"cmd": "shutdown"}, timeout=5.0)
        except Exception:
            pass

        # Terminate
        try:
            self._process.terminate()
            self._process.wait(timeout=10)
        except Exception:
            try:
                self._process.kill()
            except Exception:
                pass

        self._process = None
        print(f"[PlaneGate:{self.plane_code}] Portal closed")

    def is_open(self) -> bool:
        if not self._is_open or not self._process:
            return False
        return self._process.poll() is None

    def gate_status(self) -> Dict:
        return {
            "plane": self.plane,
            "plane_code": self.plane_code,
            "is_open": self.is_open(),
            "pid": self._process.pid if self._process else None,
            "fairies": self._interior_fairies,
            "fairy_count": len(self._interior_fairies),
            "requests_sent": self._requests_sent,
            "postal_in": self._postal_in,
            "postal_out": self._postal_out,
            "uptime": time.time() - self._opened_at if self._opened_at else 0,
        }

    @staticmethod
    def _make_serializable(obj):
        """Make a payload JSON-serializable."""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                try:
                    json.dumps(v)
                    result[k] = v
                except (TypeError, ValueError):
                    if isinstance(v, set):
                        result[k] = list(v)
                    elif isinstance(v, (int, float, str, bool, type(None))):
                        result[k] = v
                    else:
                        result[k] = str(v)
            return result
        return obj


# ═══════════════════════════════════════════════════════════════════════════════
# Main -- Subprocess entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Portal Plane Interior")
    parser.add_argument("--plane", required=True, help="Plane directory name (e.g., P60_Executive)")
    parser.add_argument("--project-root", default="", help="Project root path")
    parser.add_argument("--mode", default="stdio", help="Communication mode (stdio)")
    parser.add_argument("--sub-portals", default="",
        help="Comma-sep sub-portal specs: PlaneDir:Code (e.g., P60_Executive:P60)")
    parser.add_argument("--exclude", default="",
        help="Comma-sep fairy dirs to skip (e.g., 'Waking Minds')")
    args = parser.parse_args()

    project_root = args.project_root or str(Path(__file__).parent)

    # Parse sub-portal specs
    sub_portal_specs = []
    if args.sub_portals:
        for spec in args.sub_portals.split(","):
            spec = spec.strip()
            if ":" in spec:
                plane_full, plane_code = spec.split(":", 1)
                sub_portal_specs.append((plane_full.strip(), plane_code.strip()))
            else:
                _log(f"[PlaneInterior] WARNING: Invalid sub-portal spec '{spec}' (expected PlaneDir:Code)")

    # Parse exclude patterns
    exclude_patterns = []
    if args.exclude:
        exclude_patterns = [p.strip() for p in args.exclude.split(",") if p.strip()]

    _log(f"[PlaneInterior] Starting: plane={args.plane}, root={project_root}, pid={os.getpid()}")
    if sub_portal_specs:
        _log(f"[PlaneInterior] Sub-portals: {sub_portal_specs}")
    if exclude_patterns:
        _log(f"[PlaneInterior] Exclude: {exclude_patterns}")

    interior = PlanePortalInterior(
        plane=args.plane,
        project_root=project_root,
        sub_portal_specs=sub_portal_specs,
        exclude_patterns=exclude_patterns,
    )

    # Boot the plane (includes sub-portal opening)
    ok = interior.boot()
    if not ok:
        _log(f"[PlaneInterior] Boot failed for {args.plane}")
        # Still enter stdio loop so host gets error responses

    # Enter stdio loop
    interior.run_stdio()


if __name__ == "__main__":
    main()
