"""
Visual Cortex Gate - Host-side spawner and bridge to the visual processing subprocess.

Modeled on infrastructure/portal_gate.py but with two key differences:
1. Uses Python 3.12 executable (not the server's 3.14t) for dxcam/OpenCV/imagehash
2. Has a background reader for PASSIVE frame pushes (unsolicited from subprocess)

The gate spawns visual_cortex_interior.py as a subprocess and communicates
via stdin/stdout pipes (JSON-per-line protocol).

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import subprocess
import threading
import queue
from pathlib import Path
from typing import Dict, Optional, Any, Callable

# recall_eyes_1020 (Nous, 2026-10-20): Ace's switch state/recall_eyes_fix.json arms eyes_reader_decouple and reader_survives (infrastructure/
# recall_eyes_fix.py). Imported here, at load, on the loading thread (a first import from a non-main thread crashed free-threaded Python before:
# see VisualCortexFairy). Absent / malformed / the module missing = both OFF = this file behaves exactly as it did.
try:
    from infrastructure import recall_eyes_fix as _RX0
except Exception:
    _RX0 = None
_RX = [_RX0, -1e9]


def _rx():
    m = _RX[0]
    if m is None:
        now = time.monotonic()
        if now - _RX[1] >= 60.0:
            _RX[1] = now
            try:
                from infrastructure import recall_eyes_fix as m
                _RX[0] = m
            except Exception:
                m = None
    return m


def _rx_on(key):
    """One key of Ace's recall_eyes_fix switch; OFF on any doubt."""
    try:
        m = _rx()
        return m is not None and bool(m.on(key))
    except Exception:
        return False


class VisualCortexGate:
    """
    Gate that opens into the visual cortex subprocess.

    Spawns visual_cortex_interior.py under Python 3.12 and communicates
    via JSON-per-line IPC. Handles both synchronous request/response
    and asynchronous passive frame pushes from the subprocess.
    """

    # NOTE 2026-04-02 (Nous + Ace): Wanted 3.14t but dxcam/imagehash/cv2/winocr
    # fail to build on 3.14t (numpy C ext compilation fails). Staying on 3.12
    # for visual interior until deps catch up. Main server runs 3.14t fine.
    PYTHON_314T = r"F:\Sandbox\venv314t\Scripts\python.exe"
    PYTHON_312 = r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe"

    def __init__(
        self,
        python_exe: str = None,
        srm_intake_dir: str = "",
        capture_interval: float = 1.0,
    ):
        # 3.12 for now (vision deps don't build on 3.14t yet)
        self.python_exe = python_exe or self.PYTHON_312
        self.srm_intake_dir = srm_intake_dir
        # FIX 2026-03-14 (Nous): Default was 2.0s (0.5 FPS). Now 0.2s (5 FPS)
        # for live-feed peripheral vision. OCR runs every Nth frame in interior.
        self.capture_interval = capture_interval

        # Process handle
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()  # Protects stdin writes
        self._is_open = False

        # Response queue for synchronous send/receive (fallback for untagged responses)
        self._response_queue: queue.Queue = queue.Queue()

        # FIX 2026-06-10 (Nous+Ace) — REQUEST-ID CORRELATION. The old single shared
        # _response_queue had NO request↔response matching: with concurrent senders
        # (gaze analyze_region + look_at_image), whichever thread called .get() first
        # took the next response regardless of who it was for → cross-talk (confirmed
        # by probe-v2). Now each send() registers a private slot keyed by a unique
        # _req_id; the interior echoes _req_id; _read_loop routes the response to that
        # slot. Concurrent sends can't steal each other's responses — and it does NOT
        # serialize (each waits on its own slot).
        self._pending: Dict[str, queue.Queue] = {}
        self._pending_lock = threading.Lock()
        self._req_counter = 0

        # Passive callback (set by fairy)
        self._passive_callback: Optional[Callable[[Dict], None]] = None

        # recall_eyes_1020: inert unless eyes_reader_decouple / reader_survives are armed
        self._rx_ho = None
        self._rx_ho_lock = threading.Lock()
        self._rx_bad = 0

        # Reader/stderr threads
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

        # Auto-restart
        self._auto_restart = True
        self._restart_delay = 30.0
        self._restart_thread: Optional[threading.Thread] = None

        # Stats
        self._requests_sent = 0
        self._passive_frames_received = 0
        self._errors = 0
        self._opened_at = 0.0
        self._last_response_time = 0.0

        # Find the interior script
        self._interior_script = self._find_interior_script()

    def _find_interior_script(self) -> str:
        """Find the visual_cortex_interior.py script."""
        here = Path(__file__).parent
        candidate = here / "visual_cortex_interior.py"
        if candidate.exists():
            return str(candidate)
        raise FileNotFoundError(
            f"Cannot find visual_cortex_interior.py. Expected at: {candidate}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def open(self) -> bool:
        """
        Open the gate - spawn the visual cortex subprocess.

        Returns True if the interior booted successfully.
        """
        if self._is_open:
            return True

        if not os.path.exists(self.python_exe):
            print(f"[VisualGate] ERROR: Python 3.12 not found: {self.python_exe}")
            return False

        # Build command
        cmd = [
            self.python_exe,
            self._interior_script,
            "--interval", str(self.capture_interval),
        ]
        if self.srm_intake_dir:
            cmd.extend(["--srm-dir", self.srm_intake_dir])

        print(f"[VisualGate] Opening visual cortex subprocess...")
        print(f"[VisualGate] Command: {' '.join(cmd)}")

        try:
            # Set PYTHONPATH so interior can find its modules
            env = os.environ.copy()
            project_root = str(Path(__file__).resolve().parents[3])
            existing_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = project_root + (
                os.pathsep + existing_path if existing_path else ""
            )

            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=1,  # Line buffered
                text=True,  # Text mode
            )
        except Exception as e:
            print(f"[VisualGate] Failed to spawn interior: {e}")
            return False

        # Clear any stale data in response queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break

        # Start reader threads
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="vgate-reader"
        )
        self._reader_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True, name="vgate-stderr"
        )
        self._stderr_thread.start()

        # Wait for interior to boot — try multiple quick pings instead of
        # one long timeout. The fairy boot thread has a 30s hard limit,
        # so a single 30s ping timeout = boot thread killed before we return.
        # FIX 2026-03-31 (Nous + Ace): 5 quick pings at 3s each = 15s max,
        # well within the 30s boot timeout.
        for _attempt in range(5):
            time.sleep(1.0 if _attempt == 0 else 2.0)
            print(f"[VisualGate] Ping attempt {_attempt + 1}/5...")
            ping_result = self.send({"cmd": "ping"}, timeout=3.0)

            if ping_result and ping_result.get("status") == "pong":
                self._is_open = True
                self._opened_at = time.time()
                backend = ping_result.get("backend", "unknown")
                print(f"[VisualGate] Visual cortex ONLINE (backend={backend}, "
                      f"pid={ping_result.get('pid', '?')})")
                return True

        print(f"[VisualGate] Failed to ping interior after 5 attempts")
        # Don't close — start a background retry thread instead
        # The interior may still be initializing dxcam
        def _background_connect():
            for _retry in range(10):
                time.sleep(5.0)
                _r = self.send({"cmd": "ping"}, timeout=5.0)
                if _r and _r.get("status") == "pong":
                    self._is_open = True
                    self._opened_at = time.time()
                    print(f"[VisualGate] Visual cortex ONLINE (background retry #{_retry + 1})")
                    return
            print(f"[VisualGate] Background retry exhausted — visual cortex offline")
        threading.Thread(target=_background_connect, daemon=True, name="vgate-bg-connect").start()
        return False

    def close(self):
        """Close the gate - terminate the visual cortex subprocess."""
        if not self._process:
            self._rx_close_handoff()      # recall_eyes_1020: also in the auto-restart window (_process None); a no-op without a live hand-off
            return

        self._auto_restart = False
        print(f"[VisualGate] Closing visual cortex subprocess...")

        # Send shutdown command (graceful)
        try:
            self.send({"cmd": "shutdown"}, timeout=5.0)
        except Exception:
            pass

        # Wait for graceful exit
        try:
            self._process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            print(f"[VisualGate] Interior didn't exit gracefully, terminating...")
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()

        self._process = None
        self._is_open = False
        print(f"[VisualGate] Visual cortex closed. "
              f"Sent {self._requests_sent} requests, "
              f"received {self._passive_frames_received} passive frames, "
              f"{self._errors} errors.")
        self._rx_close_handoff()          # recall_eyes_1020: stops the hand-off worker (a no-op when there is none)

    @property
    def is_open(self) -> bool:
        """Is the gate open and the interior alive?"""
        if not self._is_open or not self._process:
            return False
        if self._process.poll() is not None:
            self._is_open = False
            # Maybe auto-restart
            if self._auto_restart:
                self._schedule_restart()
            return False
        return True

    def _schedule_restart(self):
        """Schedule an auto-restart after a delay."""
        if self._restart_thread and self._restart_thread.is_alive():
            return  # Already scheduled

        def _restart():
            print(f"[VisualGate] Auto-restart in {self._restart_delay}s...")
            time.sleep(self._restart_delay)
            if not self._is_open and self._auto_restart:
                print(f"[VisualGate] Auto-restarting visual cortex subprocess...")
                self._process = None
                if self.open():
                    # Restart passive capture
                    self.send({"cmd": "start_passive"})

        self._restart_thread = threading.Thread(
            target=_restart, daemon=True, name="vgate-restart"
        )
        self._restart_thread.start()

    # ═══════════════════════════════════════════════════════════════════════
    # COMMUNICATION
    # ═══════════════════════════════════════════════════════════════════════

    def send(self, request: Dict, timeout: float = 10.0) -> Optional[Dict]:
        """
        Send a command to the interior and wait for its response.

        Args:
            request: JSON-serializable command dict
            timeout: Seconds to wait for response

        Returns:
            Response dict, or None on failure
        """
        if not self._process or self._process.poll() is not None:
            return None

        self._requests_sent += 1
        t0 = time.time()

        # Register a private response slot keyed by a unique request id.
        with self._pending_lock:
            self._req_counter += 1
            rid = str(self._req_counter)
            slot: queue.Queue = queue.Queue(maxsize=1)
            self._pending[rid] = slot
        request = dict(request)            # never mutate the caller's dict
        request["_req_id"] = rid

        try:
            with self._lock:
                # Write command to stdin
                line = json.dumps(request, ensure_ascii=False) + "\n"
                self._process.stdin.write(line)
                self._process.stdin.flush()

            # Wait for THIS request's response on its own slot (routed by _req_id
            # in _read_loop). Concurrent senders no longer steal each other's
            # responses, and waiting on a private slot does NOT serialize them.
            try:
                response = slot.get(timeout=timeout)
                self._last_response_time = time.time() - t0
                return response
            except queue.Empty:
                self._errors += 1
                return None

        except Exception as e:
            self._errors += 1
            print(f"[VisualGate] Send error: {e}")
            return None
        finally:
            with self._pending_lock:
                self._pending.pop(rid, None)

    def _read_loop(self):
        """
        Background thread: read ALL stdout lines from the subprocess.

        Routes messages to either:
        - response_queue (for synchronous send/receive)
        - passive_callback (for unsolicited passive frame pushes)
        """
        _rx_proc = self._process          # recall_eyes_1020: for the reader's exit line only
        try:
            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not isinstance(msg, dict) and _rx_on("reader_survives"):
                    # recall_eyes_1020: a valid-JSON line that is not an object (123, null, [1]) made msg.get raise below and ended this
                    # thread silently. Skipped and counted instead (OFF: today's behaviour).
                    self._rx_bad += 1
                    if self._rx_bad <= 3:
                        print("[VisualGate] reader: skipped a JSON line that is not an object (%d so far): %s" % (self._rx_bad, ascii(line[:80])))
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "passive_frame":
                    # Unsolicited push from passive capture loop
                    self._passive_frames_received += 1
                    if self._passive_callback:
                        ho = self._rx_handoff()       # recall_eyes_1020: None unless eyes_reader_decouple is armed (then: today's inline call)
                        if ho is not None:
                            ho.put(msg.get("data", {}))
                        else:
                            try:
                                self._passive_callback(msg.get("data", {}))
                            except Exception as e:
                                if self._passive_frames_received <= 3:
                                    print(f"[VisualGate] Passive callback error: {e}")
                else:
                    # Response to a send() call — route to that request's slot
                    # by _req_id. Untagged responses (older interior, or pushes
                    # without an id) fall back to the shared queue.
                    rid = msg.get("_req_id")
                    slot = None
                    if rid is not None:
                        with self._pending_lock:
                            slot = self._pending.get(str(rid))
                    if slot is not None:
                        try:
                            slot.put_nowait(msg)
                        except queue.Full:
                            pass  # slot already filled (duplicate) — drop
                    else:
                        self._response_queue.put(msg)

        except Exception as e:
            # Process died or pipe closed. recall_eyes_1020: said out loud while reader_survives is armed; silent otherwise, as before.
            if _rx_on("reader_survives"):
                print("[VisualGate] reader thread exiting on %s: %s" % (type(e).__name__, ascii(str(e))[:120]))
        else:
            if _rx_on("reader_survives"):
                print("[VisualGate] reader: interior stdout closed (pid %s)" % (getattr(_rx_proc, "pid", "?"),))

    def _rx_handoff(self):
        """recall_eyes_1020 (eyes_reader_decouple): the bounded drop-oldest hand-off between this reader and the frame callback, created on
        first use. None when the key is OFF, the module is missing or anything goes wrong: the caller then makes today's inline call."""
        try:
            if not _rx_on("eyes_reader_decouple"):
                return None
            ho = self._rx_ho
            if ho is not None and not ho.stopped:
                return ho
            with self._rx_ho_lock:
                ho = self._rx_ho
                if ho is None or ho.stopped:
                    ho = _rx().Handoff(self._rx_deliver, name="vgate-passive", flight_name="vcf_passive_spread")
                    self._rx_ho = ho
                return ho
        except Exception:
            return None

    def _rx_deliver(self, data):
        """Resolved PER FRAME: a callback registered later (set_passive_callback) gets the next frame."""
        cb = self._passive_callback
        if cb:
            cb(data)

    def _rx_close_handoff(self):
        try:
            ho = self._rx_ho
            if ho is not None and not ho.stopped:
                ho.stop()
                s = ho.status()
                print("[VisualGate] passive hand-off at close: received=%d processed=%d dropped=%d errors=%d"
                      % (s["received"], s["processed"], s["dropped"], s["errors"]))
        except Exception:
            pass

    def _read_stderr(self):
        """Background thread: read and print stderr from the interior."""
        try:
            for line in self._process.stderr:
                line = line.strip()
                if line:
                    print(f"  [VisualInterior] {line}")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # CALLBACK REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def set_passive_callback(self, callback: Callable[[Dict], None]):
        """
        Register a callback for passive frame pushes.

        The callback receives the frame analysis data dict.
        Called from the reader thread - must be thread-safe.
        """
        self._passive_callback = callback

    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def capture(self, timeout: float = 10.0) -> Optional[Dict]:
        """On-demand single capture with full analysis."""
        return self.send({"cmd": "capture"}, timeout=timeout)

    def start_passive(self) -> Optional[Dict]:
        """Start the passive capture loop in the subprocess."""
        return self.send({"cmd": "start_passive"})

    def stop_passive(self) -> Optional[Dict]:
        """Stop the passive capture loop."""
        return self.send({"cmd": "stop_passive"})

    def set_interval(self, seconds: float) -> Optional[Dict]:
        """Change the passive capture interval."""
        return self.send({"cmd": "set_interval", "seconds": seconds})

    def analyze_region(self, x: int, y: int, w: int, h: int,
                       timeout: float = 5.0) -> Optional[Dict]:
        """Foveal crop: analyze a specific screen region with full OCR.

        Used by GazeController to read text in the region Sourpatches
        is currently looking at (~100-150ms vs 420ms for full screen).
        """
        return self.send(
            {"cmd": "analyze_region", "x": x, "y": y, "w": w, "h": h},
            timeout=timeout,
        )

    def look_at_image(self, path: str, timeout: float = 15.0, skip_ocr: bool = False) -> Optional[Dict]:
        """Load an image file from disk and analyze it.

        FIX 2026-04-09 (Nous + Ace): The "mirror" path — lets external callers
        point her at a specific image file (e.g. D:/Akashic Foundation Images/
        Sourpatches art) and get back a rich analysis with named colors,
        scene description, OCR text, AND a filename-derived semantic hint.

        DALL-E filenames contain the literal prompt used to generate the image,
        which gives us free ground-truth labels without needing a vision model.

        Args:
            path: Absolute path to the image file (PNG, JPG, WebP, BMP, GIF).
            timeout: Seconds to wait for subprocess response (default 15s —
                     image loading + full OCR can take several seconds).

        Returns:
            Response dict with analysis data, or None on error.
        """
        return self.send(
            {"cmd": "look_at_image", "path": path, "skip_ocr": skip_ocr},
            timeout=timeout,
        )

    def status(self) -> Optional[Dict]:
        """Get interior status."""
        return self.send({"cmd": "status"})

    def ping(self) -> Optional[Dict]:
        """Ping the interior."""
        return self.send({"cmd": "ping"}, timeout=5.0)

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def gate_status(self) -> Dict[str, Any]:
        """Status of the gate itself (not the interior)."""
        _rx_st = {
            "is_open": self.is_open,
            "python_exe": self.python_exe,
            "requests_sent": self._requests_sent,
            "passive_frames_received": self._passive_frames_received,
            "errors": self._errors,
            "last_response_ms": round(self._last_response_time * 1000, 1),
            "uptime_seconds": round(
                time.time() - self._opened_at, 1
            ) if self._opened_at else 0,
            "interior_pid": self._process.pid if self._process else None,
        }
        _rx_ho = self._rx_ho              # recall_eyes_1020: only present while a hand-off exists (OFF: the dict is exactly today's)
        if _rx_ho is not None:
            _rx_st["passive_handoff"] = _rx_ho.status()
        return _rx_st
