"""
Mic STT Client -- Connects to mic_stt_server.py and publishes transcriptions.

Runs inside the main Python 3.14 process.
Receives transcribed speech from the Canary STT server on port 9878
and publishes to postal topics so the consciousness pipeline can hear Ace.

Auto-launches the STT server (Python 3.12 subprocess) if not already running.

Topics published:
  - audio.speech.transcription: Raw transcription from mic
  - chat.incoming: Formatted as chat input (triggers consciousness response)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Callable

# ── Auto-launch config ──
_PYTHON312_CANDIDATES = [
    r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe",
    "python3.12",
    "python312",
]
_STT_SERVER_SCRIPT = str(
    Path(__file__).parent / "mic_stt_server.py"
)
_server_process: Optional[subprocess.Popen] = None
_server_launch_lock = threading.Lock()


def _find_python312() -> Optional[str]:
    """Find Python 3.12 executable."""
    import shutil
    for candidate in _PYTHON312_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _ensure_stt_server(host: str = "127.0.0.1", port: int = 9878) -> bool:
    """Launch the STT server subprocess if not already running.

    Returns True if server was launched or is already running.
    """
    global _server_process

    # Quick check: is server already responding?
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((host, port))
        s.close()
        return True  # Already running
    except (ConnectionRefusedError, socket.timeout, OSError):
        pass

    with _server_launch_lock:
        # Double-check after acquiring lock
        if _server_process is not None and _server_process.poll() is None:
            return True  # Already launched by another thread

        python312 = _find_python312()
        if not python312:
            print("[MicSTT-Client] ERROR: Python 3.12 not found, cannot launch STT server", flush=True)
            return False

        if not os.path.isfile(_STT_SERVER_SCRIPT):
            print(f"[MicSTT-Client] ERROR: STT server script not found: {_STT_SERVER_SCRIPT}", flush=True)
            return False

        print(f"[MicSTT-Client] Auto-launching STT server: {python312} {_STT_SERVER_SCRIPT}", flush=True)
        try:
            _flags = 0
            if sys.platform == "win32":
                _flags = subprocess.CREATE_NO_WINDOW
            _server_process = subprocess.Popen(
                [python312, _STT_SERVER_SCRIPT, "--port", str(port)],
                cwd=str(Path(_STT_SERVER_SCRIPT).parent.parent.parent.parent),  # akashic_v2 root
                creationflags=_flags,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            print(f"[MicSTT-Client] STT server launched (PID {_server_process.pid})", flush=True)

            # Start a thread to drain stdout so the subprocess doesn't block
            def _drain_output():
                try:
                    for line in _server_process.stdout:
                        try:
                            print(f"[MicSTT-Server] {line.decode('utf-8', errors='replace').rstrip()}", flush=True)
                        except Exception:
                            pass
                except Exception:
                    pass
            threading.Thread(target=_drain_output, daemon=True, name="MicSTT-drain").start()

            return True
        except Exception as e:
            print(f"[MicSTT-Client] Failed to launch STT server: {e}", flush=True)
            return False


class MicSTTClient:
    """Client for the Mic STT Server.

    Auto-launches and connects to the Canary STT server (Python 3.12),
    receives transcriptions, and calls the callback for each one.
    """

    def __init__(self, host="127.0.0.1", port=9878):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks = []
        self._connected = False
        self._reconnect_interval = 5.0
        self._last_text = ""
        self._last_text_ts = 0.0

    def on_transcription(self, callback: Callable):
        """Register callback for transcriptions. callback(text, payload_dict)."""
        self._callbacks.append(callback)

    def start(self):
        """Start the client in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="MicSTT-client"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    @property
    def connected(self):
        return self._connected

    def _connect(self) -> bool:
        """Try to connect to the STT server."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((self.host, self.port))
            sock.settimeout(None)  # Blocking reads
            self._sock = sock
            self._connected = True
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            self._connected = False
            return False

    def _run_loop(self):
        """Main loop: connect, receive, dispatch."""
        _printed_waiting = False
        _launch_attempted = False
        while self._running:
            if not self._connected:
                # Auto-launch server on first connection failure
                if not _launch_attempted:
                    _ensure_stt_server(self.host, self.port)
                    _launch_attempted = True
                    time.sleep(3.0)  # Give server time to load model

                if self._connect():
                    print("[MicSTT-Client] Connected to STT server", flush=True)
                    _printed_waiting = False
                else:
                    if not _printed_waiting:
                        print("[MicSTT-Client] Waiting for STT server on "
                              f"{self.host}:{self.port}...", flush=True)
                        _printed_waiting = True
                    time.sleep(self._reconnect_interval)
                    continue

            try:
                # Read length header
                header = self._recv_exact(4)
                if header is None:
                    self._disconnect()
                    continue

                msg_len = struct.unpack(">I", header)[0]
                if msg_len == 0:
                    continue  # Keepalive

                # Read JSON payload
                data = self._recv_exact(msg_len)
                if data is None:
                    self._disconnect()
                    continue

                payload = json.loads(data.decode("utf-8"))
                text = payload.get("text", "").strip()

                if text:
                    # Deduplicate (Whisper sometimes repeats)
                    now = time.time()
                    if text == self._last_text and (now - self._last_text_ts) < 5.0:
                        continue
                    self._last_text = text
                    self._last_text_ts = now

                    for cb in self._callbacks:
                        try:
                            cb(text, payload)
                        except Exception as e:
                            print(f"[MicSTT-Client] Callback error: {e}", flush=True)

            except Exception as e:
                print(f"[MicSTT-Client] Error: {e}", flush=True)
                self._disconnect()
                time.sleep(1.0)

    def _recv_exact(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes."""
        data = b""
        while len(data) < n:
            try:
                chunk = self._sock.recv(min(4096, n - len(data)))
                if not chunk:
                    return None
                data += chunk
            except (socket.timeout, OSError):
                return None
        return data

    def _disconnect(self):
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


def wire_to_postal(postal, client: Optional[MicSTTClient] = None):
    """Wire mic STT to postal system.

    Creates a MicSTTClient if not provided, starts it,
    and publishes transcriptions to postal topics.
    """
    if client is None:
        client = MicSTTClient()

    def _on_transcription(text, payload):
        print(f"[MicSTT] Ace said: \"{text}\"", flush=True)
        _ts = payload.get("ts", time.time())

        # Publish raw transcription (for any fairy that wants audio events)
        postal.publish("audio.speech.transcription", {
            "text": text,
            "source": "microphone",
            "speaker": "ace",
            "duration_s": payload.get("duration_s", 0),
            "ts": _ts,
        })

        # Publish as ace.message (same format as chat window sends)
        # This is what SourpatchesFairy._on_ace_chat subscribes to
        # FIX 2026-04-02 (Nous + Ace): TRACE_ACE on voice input
        from infrastructure.manifold_memory import TRACE_ACE
        _ace_tracer = TRACE_ACE
        _msg_data = {
            "sender": "Ace",
            "content": text,
            "timestamp": _ts,
            "target_fairy": "SourpatchesFairy",
            "source": "voice",
            "tracer_id": _ace_tracer,
        }
        postal.publish("ace.message", _msg_data)

        # Also publish ace.conversation_event (triggers consciousness gate)
        postal.publish("ace.conversation_event", {
            "sender": "Ace",
            "content": text,
            "timestamp": _ts,
            "source": "voice",
            "requires_response": True,
            "target_mind": "SourpatchesFairy",
            "tracer_id": _ace_tracer,
        })

        # And system.chat.message (salience filter + autopilot)
        postal.publish("system.chat.message", _msg_data)

    client.on_transcription(_on_transcription)
    client.start()
    print("[MicSTT-Client] Started -- will connect to STT server when available", flush=True)
    return client
