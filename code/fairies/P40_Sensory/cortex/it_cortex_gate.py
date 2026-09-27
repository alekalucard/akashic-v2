"""
IT Cortex Gate - Host-side spawner and bridge to the Florence-2 recognition subprocess.

Modeled on visual_cortex_gate.py with adaptations for Florence-2:
1. Uses Python 3.12 executable (not the server's 3.14t) for torch/transformers
2. Has background reader for PASSIVE recognition pushes (unsolicited from subprocess)
3. Longer boot timeout (Florence-2 model load takes ~5-10s vs dxcam's ~1s)

The gate spawns it_cortex_interior.py as a subprocess and communicates
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


class ITCortexGate:
    """
    Gate that opens into the IT cortex (Florence-2) subprocess.

    Spawns it_cortex_interior.py under Python 3.12 and communicates
    via JSON-per-line IPC. Handles both synchronous request/response
    and asynchronous passive recognition pushes from the subprocess.
    """

    # Default Python 3.12 executable path (has torch, transformers, timm, einops)
    PYTHON_312 = r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe"

    def __init__(
        self,
        python_exe: str = None,
        capture_interval: float = 10.0,
    ):
        self.python_exe = python_exe or self.PYTHON_312
        self.capture_interval = capture_interval

        # Process handle
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()  # Protects stdin writes
        self._is_open = False

        # Response queue for synchronous send/receive
        self._response_queue: queue.Queue = queue.Queue()

        # Passive callback (set by fairy)
        self._passive_callback: Optional[Callable[[Dict], None]] = None

        # Text reading callback (Florence OCR, 2026-03-18 Nous)
        self._text_callback: Optional[Callable[[Dict], None]] = None
        self._text_readings_received = 0

        # Reader/stderr threads
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

        # Auto-restart
        self._auto_restart = True
        self._restart_delay = 60.0  # Longer than visual cortex (model reload is heavy)
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
        """Find the it_cortex_interior.py script."""
        here = Path(__file__).parent
        candidate = here / "it_cortex_interior.py"
        if candidate.exists():
            return str(candidate)
        raise FileNotFoundError(
            f"Cannot find it_cortex_interior.py. Expected at: {candidate}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def open(self) -> bool:
        """
        Open the gate - spawn the IT cortex subprocess.

        Returns True if the interior booted successfully.
        Florence-2 model load takes ~5-10s, so we use a longer boot timeout.
        """
        if self._is_open:
            return True

        if not os.path.exists(self.python_exe):
            print(f"[ITGate] ERROR: Python 3.12 not found: {self.python_exe}", flush=True)
            return False

        # Build command
        cmd = [
            self.python_exe,
            self._interior_script,
            "--interval", str(self.capture_interval),
        ]

        print(f"[ITGate] Opening IT cortex subprocess...", flush=True)
        print(f"[ITGate] Command: {' '.join(cmd)}", flush=True)

        try:
            # Set PYTHONPATH so interior can find its modules
            env = os.environ.copy()
            project_root = str(Path(__file__).resolve().parents[3])
            existing_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = project_root + (
                os.pathsep + existing_path if existing_path else ""
            )

            # Ensure CUDA is available to the subprocess
            # (mcp_sse_server.py sets CUDA_VISIBLE_DEVICES="" to save RAM,
            #  but the IT cortex NEEDS the GPU for Florence-2)
            if env.get("CUDA_VISIBLE_DEVICES") == "":
                del env["CUDA_VISIBLE_DEVICES"]

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
            print(f"[ITGate] Failed to spawn interior: {e}", flush=True)
            return False

        # Clear any stale data in response queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break

        # Start reader threads
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="itgate-reader"
        )
        self._reader_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True, name="itgate-stderr"
        )
        self._stderr_thread.start()

        # Wait for interior to boot — longer timeout for Florence-2 model loading.
        # First run downloads ~500MB model; subsequent runs load from cache (~5-10s).
        print(f"[ITGate] Waiting for Florence-2 model load (may take 30-60s first time)...", flush=True)
        time.sleep(2.0)
        ping_result = self.send({"cmd": "ping"}, timeout=120.0)

        if ping_result and ping_result.get("status") == "pong":
            self._is_open = True
            self._opened_at = time.time()
            model = ping_result.get("model", "unknown")
            vram = ping_result.get("vram_mb", "?")
            print(f"[ITGate] IT cortex ONLINE (model={model}, vram={vram}MB, "
                  f"pid={ping_result.get('pid', '?')})", flush=True)
            return True
        else:
            print(f"[ITGate] Failed to ping interior: {ping_result}", flush=True)
            self.close()
            return False

    def close(self):
        """Close the gate - terminate the IT cortex subprocess."""
        if not self._process:
            return

        self._auto_restart = False
        print(f"[ITGate] Closing IT cortex subprocess...")

        # Send shutdown command (graceful)
        try:
            self.send({"cmd": "shutdown"}, timeout=5.0)
        except Exception:
            pass

        # Wait for graceful exit
        try:
            self._process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            print(f"[ITGate] Interior didn't exit gracefully, terminating...")
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()

        self._process = None
        self._is_open = False
        print(f"[ITGate] IT cortex closed. "
              f"Sent {self._requests_sent} requests, "
              f"received {self._passive_frames_received} passive frames, "
              f"{self._errors} errors.")

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
            print(f"[ITGate] Auto-restart in {self._restart_delay}s...")
            time.sleep(self._restart_delay)
            if not self._is_open and self._auto_restart:
                print(f"[ITGate] Auto-restarting IT cortex subprocess...")
                self._process = None
                if self.open():
                    # Restart passive recognition
                    self.send({"cmd": "start_passive"})

        self._restart_thread = threading.Thread(
            target=_restart, daemon=True, name="itgate-restart"
        )
        self._restart_thread.start()

    # ═══════════════════════════════════════════════════════════════════════
    # COMMUNICATION
    # ═══════════════════════════════════════════════════════════════════════

    def send(self, request: Dict, timeout: float = 30.0) -> Optional[Dict]:
        """
        Send a command to the interior and wait for its response.

        Default timeout is higher than visual cortex (Florence-2 inference
        takes ~300-500ms vs dxcam's ~50ms).
        """
        if not self._process or self._process.poll() is not None:
            return None

        self._requests_sent += 1
        t0 = time.time()

        try:
            with self._lock:
                # Write command to stdin
                line = json.dumps(request, ensure_ascii=False) + "\n"
                self._process.stdin.write(line)
                self._process.stdin.flush()

            # Wait for response on the queue (reader thread puts it there)
            try:
                response = self._response_queue.get(timeout=timeout)
                self._last_response_time = time.time() - t0
                return response
            except queue.Empty:
                self._errors += 1
                return None

        except Exception as e:
            self._errors += 1
            print(f"[ITGate] Send error: {e}")
            return None

    def _read_loop(self):
        """
        Background thread: read ALL stdout lines from the subprocess.

        Routes messages to either:
        - response_queue (for synchronous send/receive)
        - passive_callback (for unsolicited passive recognition pushes)
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

                msg_type = msg.get("type", "")

                if msg_type in ("passive_frame", "foveal_frame", "peripheral_frame"):
                    # Unsolicited push from passive recognition loop
                    # FIX 2026-03-17 (Nous + Ace): Route foveal, peripheral,
                    # and legacy passive frames through appropriate callbacks.
                    self._passive_frames_received += 1
                    data = msg.get("data", {})
                    data["_frame_type"] = msg_type  # Tag so fairy can differentiate
                    if self._passive_callback:
                        try:
                            self._passive_callback(data)
                        except Exception as e:
                            if self._passive_frames_received <= 3:
                                print(f"[ITGate] Passive callback error: {e}")
                elif msg_type == "text_reading":
                    # Florence OCR text reading (2026-03-18, Nous)
                    self._text_readings_received += 1
                    if self._text_callback:
                        try:
                            self._text_callback(msg.get("data", {}))
                        except Exception as e:
                            if self._text_readings_received <= 5:
                                print(f"[ITGate] Text callback error: {e}")
                else:
                    # Response to a send() call
                    self._response_queue.put(msg)

        except Exception:
            pass  # Process died or pipe closed

    def _read_stderr(self):
        """Background thread: read and print stderr from the interior."""
        try:
            for line in self._process.stderr:
                line = line.strip()
                if line:
                    print(f"  [ITInterior] {line}", flush=True)
        except Exception as e:
            print(f"  [ITInterior] stderr reader error: {e}", flush=True)

    # ═══════════════════════════════════════════════════════════════════════
    # CALLBACK REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def set_passive_callback(self, callback: Callable[[Dict], None]):
        """
        Register a callback for passive recognition pushes.

        The callback receives the recognition data dict.
        Called from the reader thread - must be thread-safe.
        """
        self._passive_callback = callback

    def set_text_callback(self, callback: Callable[[Dict], None]):
        """Register a callback for Florence OCR text reading results.

        Called when Florence reads text from the screen (every 3rd foveal cycle).
        The callback receives: {"text": str, "region": list, "inference_ms": float}
        Called from the reader thread — must be thread-safe.

        2026-03-18, Nous
        """
        self._text_callback = callback

    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def analyze(self, timeout: float = 30.0) -> Optional[Dict]:
        """On-demand single analysis with Florence-2."""
        return self.send({"cmd": "analyze"}, timeout=timeout)

    def start_passive(self) -> Optional[Dict]:
        """Start the passive recognition loop in the subprocess."""
        return self.send({"cmd": "start_passive"})

    def stop_passive(self) -> Optional[Dict]:
        """Stop the passive recognition loop."""
        return self.send({"cmd": "stop_passive"})

    def set_interval(self, seconds: float) -> Optional[Dict]:
        """Change the passive recognition interval."""
        return self.send({"cmd": "set_interval", "seconds": seconds})

    def status(self) -> Optional[Dict]:
        """Get interior status."""
        return self.send({"cmd": "status"})

    def ping(self) -> Optional[Dict]:
        """Ping the interior."""
        return self.send({"cmd": "ping"}, timeout=10.0)

    def set_focus(self, region: list = None) -> Optional[Dict]:
        """Set the foveal focus region for attention-driven recognition.

        FIX 2026-03-17 (Nous + Ace): Florence foveal/peripheral vision.
        Args:
            region: [x1, y1, x2, y2] in capture coordinates, or None to clear
        """
        return self.send({"cmd": "set_focus", "region": region})

    def analyze_focused(self, region: list = None, timeout: float = 10.0) -> Optional[Dict]:
        """On-demand foveal analysis on a specific region.

        FIX 2026-03-17 (Nous + Ace): Used when attention shifts to get
        immediate detailed inference on the new focus target.
        """
        return self.send({"cmd": "analyze_focused", "region": region}, timeout=timeout)

    def read_text(self, region: list = None, timeout: float = 15.0) -> Optional[Dict]:
        """On-demand text reading via Florence-2 OCR.

        2026-03-18, Nous: Gives her the ability to READ text on screen.
        Uses Florence <OCR> task — much more accurate than pytesseract.

        Args:
            region: [x1, y1, x2, y2] crop region, or None for full screen
            timeout: Max wait time (OCR can take 500-1000ms)

        Returns:
            {"status": "ok", "type": "text_reading",
             "data": {"text": "...", "region": [...], "inference_ms": N}}
        """
        return self.send({"cmd": "read_text", "region": region}, timeout=timeout)

    def feed_energy(self, amount: float, source: str = "host") -> Optional[Dict]:
        """Feed energy into the interior's VisionFarm batteries.

        FIX 2026-03-17 (Nous + Ace): The IT Cortex IS a pocket dimension.
        Energy from consciousness loop, paradox pulses, etc. flows through
        the gate into the VRAM dimension's batteries, amplified by time compression.
        """
        return self.send({"cmd": "energy", "amount": amount, "source": source}, timeout=5.0)

    def farm_status(self) -> Optional[Dict]:
        """Get VisionFarm status from the interior.

        Returns dimensional physics metrics: gravity, time compression,
        cost reduction, battery states, inference mass, etc.
        """
        return self.send({"cmd": "farm_status"}, timeout=5.0)

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def gate_status(self) -> Dict[str, Any]:
        """Status of the gate itself (not the interior)."""
        return {
            "is_open": self.is_open,
            "python_exe": self.python_exe,
            "requests_sent": self._requests_sent,
            "passive_frames_received": self._passive_frames_received,
            "text_readings_received": self._text_readings_received,
            "errors": self._errors,
            "last_response_ms": round(self._last_response_time * 1000, 1),
            "uptime_seconds": round(
                time.time() - self._opened_at, 1
            ) if self._opened_at else 0,
            "interior_pid": self._process.pid if self._process else None,
        }
