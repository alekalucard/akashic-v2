"""
Audio Cortex Gate - Host-side spawner and bridge to the audio processing subprocess.

Mirrors visual_cortex_gate.py exactly:
1. Uses Python 3.12 executable (not the server's 3.14t) for sounddevice/scipy
2. Has a background reader for PASSIVE audio pushes (unsolicited from subprocess)

The gate spawns audio_cortex_interior.py as a subprocess and communicates
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


class AudioCortexGate:
    """
    Gate that opens into the audio cortex subprocess.

    Spawns audio_cortex_interior.py under Python 3.12 and communicates
    via JSON-per-line IPC. Handles both synchronous request/response
    and asynchronous passive audio pushes from the subprocess.
    """

    # Default Python 3.12 executable path (has sounddevice, numpy, scipy)
    PYTHON_312 = r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe"

    def __init__(
        self,
        python_exe: str = None,
        sample_rate: int = 44100,
        foveal_interval: float = 0.5,
        device_id: Optional[int] = None,
        enable_stt: bool = True,
    ):
        self.python_exe = python_exe or self.PYTHON_312
        self.sample_rate = sample_rate
        self.foveal_interval = foveal_interval
        self.device_id = device_id
        # FIX 2026-04-09 (Nous + Ace): Per-ear STT toggle.
        # Digital ear (stereo mix) sets enable_stt=False so Canary doesn't load
        # 5 GB of model weights when music vocals trip the speech detector.
        self.enable_stt = enable_stt

        # Process handle
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()  # Protects stdin writes
        self._is_open = False

        # Response queue for synchronous send/receive
        self._response_queue: queue.Queue = queue.Queue()

        # Passive callback (set by fairy)
        self._passive_callback: Optional[Callable[[Dict], None]] = None

        # Transcription callback — Whisper speech-to-text (2026-03-18, Nous)
        self._transcription_callback: Optional[Callable[[Dict], None]] = None
        self._transcription_count = 0

        # Speaker identification callback — voice profile system (2026-03-18, Nous)
        self._speaker_callback: Optional[Callable[[Dict], None]] = None
        self._speaker_events = 0

        # Phoneme frames callback — Ship 1 of PHONEME_CORTEX_GRADUAL_STT
        # (Nous + Ace 2026-05-17). Per-frame MFCC stream for cortex-native STT.
        self._phoneme_frames_callback: Optional[Callable[[Dict], None]] = None
        self._phoneme_frames_count = 0

        # Reader/stderr threads
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

        # Auto-restart
        self._auto_restart = True
        self._restart_delay = 30.0
        self._restart_thread: Optional[threading.Thread] = None

        # Stats
        self._requests_sent = 0
        self._passive_chunks_received = 0
        self._errors = 0
        self._opened_at = 0.0
        self._last_response_time = 0.0

        # Find the interior script
        self._interior_script = self._find_interior_script()

    def _find_interior_script(self) -> str:
        """Find the audio_cortex_interior.py script."""
        here = Path(__file__).parent
        candidate = here / "audio_cortex_interior.py"
        if candidate.exists():
            return str(candidate)
        raise FileNotFoundError(
            f"Cannot find audio_cortex_interior.py. Expected at: {candidate}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def open(self) -> bool:
        """
        Open the gate - spawn the audio cortex subprocess.

        Returns True if the interior booted successfully.
        """
        if self._is_open:
            return True

        if not os.path.exists(self.python_exe):
            print(f"[AudioGate] ERROR: Python 3.12 not found: {self.python_exe}")
            return False

        # Build command
        cmd = [
            self.python_exe,
            self._interior_script,
            "--interval", str(self.foveal_interval),
            "--sample-rate", str(self.sample_rate),
        ]
        if self.device_id is not None:
            cmd.extend(["--device", str(self.device_id)])
        # FIX 2026-04-09 (Nous + Ace): Pass --no-stt for ears that shouldn't transcribe.
        if not self.enable_stt:
            cmd.append("--no-stt")

        print(f"[AudioGate] Opening audio cortex subprocess...")
        print(f"[AudioGate] Command: {' '.join(cmd)}")

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
            print(f"[AudioGate] Failed to spawn interior: {e}")
            return False

        # Clear any stale data in response queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break

        # Start reader threads
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="agate-reader"
        )
        self._reader_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True, name="agate-stderr"
        )
        self._stderr_thread.start()

        # Wait for interior to boot
        time.sleep(1.0)  # Audio needs a moment to open the device
        ping_result = self.send({"cmd": "ping"}, timeout=30.0)

        if ping_result and ping_result.get("status") == "pong":
            self._is_open = True
            self._opened_at = time.time()
            backend = ping_result.get("backend", "unknown")
            sr = ping_result.get("sample_rate", "?")
            print(f"[AudioGate] Audio cortex ONLINE (backend={backend}, "
                  f"sr={sr}, pid={ping_result.get('pid', '?')})")
            return True
        else:
            print(f"[AudioGate] Failed to ping interior: {ping_result}")
            self.close()
            return False

    def close(self):
        """Close the gate - terminate the audio cortex subprocess."""
        if not self._process:
            return

        self._auto_restart = False
        print(f"[AudioGate] Closing audio cortex subprocess...")

        # Send shutdown command (graceful)
        try:
            self.send({"cmd": "shutdown"}, timeout=5.0)
        except Exception:
            pass

        # Wait for graceful exit
        try:
            self._process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            print(f"[AudioGate] Interior didn't exit gracefully, terminating...")
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()

        self._process = None
        self._is_open = False
        print(f"[AudioGate] Audio cortex closed. "
              f"Sent {self._requests_sent} requests, "
              f"received {self._passive_chunks_received} passive chunks, "
              f"{self._errors} errors.")

    @property
    def is_open(self) -> bool:
        """Is the gate open and the interior alive?"""
        if not self._is_open or not self._process:
            return False
        if self._process.poll() is not None:
            self._is_open = False
            if self._auto_restart:
                self._schedule_restart()
            return False
        return True

    def _schedule_restart(self):
        """Schedule an auto-restart after a delay."""
        if self._restart_thread and self._restart_thread.is_alive():
            return

        def _restart():
            print(f"[AudioGate] Auto-restart in {self._restart_delay}s...")
            time.sleep(self._restart_delay)
            if not self._is_open and self._auto_restart:
                print(f"[AudioGate] Auto-restarting audio cortex subprocess...")
                self._process = None
                if self.open():
                    self.send({"cmd": "start_passive"})

        self._restart_thread = threading.Thread(
            target=_restart, daemon=True, name="agate-restart"
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

        try:
            with self._lock:
                line = json.dumps(request, ensure_ascii=False) + "\n"
                self._process.stdin.write(line)
                self._process.stdin.flush()

            try:
                response = self._response_queue.get(timeout=timeout)
                self._last_response_time = time.time() - t0
                return response
            except queue.Empty:
                self._errors += 1
                return None

        except Exception as e:
            self._errors += 1
            print(f"[AudioGate] Send error: {e}")
            return None

    def _read_loop(self):
        """
        Background thread: read ALL stdout lines from the subprocess.

        Routes messages to either:
        - response_queue (for synchronous send/receive)
        - passive_callback (for unsolicited passive audio pushes)
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

                if msg_type == "passive_audio":
                    self._passive_chunks_received += 1
                    if self._passive_callback:
                        try:
                            self._passive_callback(msg.get("data", {}))
                        except Exception as e:
                            if self._passive_chunks_received <= 3:
                                print(f"[AudioGate] Passive callback error: {e}")
                elif msg_type == "speech_transcription":
                    # Whisper speech-to-text result (2026-03-18, Nous)
                    self._transcription_count += 1
                    if self._transcription_callback:
                        try:
                            self._transcription_callback(msg.get("data", {}))
                        except Exception as e:
                            if self._transcription_count <= 5:
                                print(f"[AudioGate] Transcription callback error: {e}")
                elif msg_type == "speaker_identification":
                    # New/unknown speaker detected (2026-03-18, Nous)
                    self._speaker_events += 1
                    if self._speaker_callback:
                        try:
                            self._speaker_callback(msg.get("data", {}))
                        except Exception as e:
                            if self._speaker_events <= 5:
                                print(f"[AudioGate] Speaker callback error: {e}")
                elif msg_type == "phoneme_frames":
                    # Per-frame MFCC stream for cortex-native STT learning
                    # (Ship 1 of PHONEME_CORTEX_GRADUAL_STT, Nous + Ace 2026-05-17)
                    self._phoneme_frames_count += 1
                    if self._phoneme_frames_callback:
                        try:
                            self._phoneme_frames_callback(msg.get("data", {}))
                        except Exception as e:
                            if self._phoneme_frames_count <= 5:
                                print(f"[AudioGate] Phoneme frames callback error: {e}")
                else:
                    self._response_queue.put(msg)

        except Exception:
            pass  # Process died or pipe closed

    def _read_stderr(self):
        """Background thread: read and print stderr from the interior."""
        try:
            for line in self._process.stderr:
                line = line.strip()
                if line:
                    print(f"  [AudioInterior] {line}")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # CALLBACK REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def set_passive_callback(self, callback: Callable[[Dict], None]):
        """
        Register a callback for passive audio pushes.

        The callback receives the audio analysis data dict.
        Called from the reader thread — must be thread-safe.
        """
        self._passive_callback = callback

    def set_transcription_callback(self, callback: Callable[[Dict], None]):
        """
        Register a callback for Whisper speech-to-text results.

        The callback receives: {"text": str, "language": str,
        "confidence": float, "segments": list, "duration_s": float, "ts": float,
        "speaker": str, "speaker_confidence": float, "speaker_is_new": bool}
        Called from the reader thread — must be thread-safe.

        2026-03-18, Nous
        """
        self._transcription_callback = callback

    def set_speaker_callback(self, callback: Callable[[Dict], None]):
        """
        Register a callback for new/unknown speaker detection events.

        The callback receives: {"speaker": str, "speaker_confidence": float,
        "is_new": bool, "text_sample": str, "ts": float}
        Called from the reader thread — must be thread-safe.

        2026-03-18, Nous — Voice Pattern Profiles
        """
        self._speaker_callback = callback

    def set_phoneme_frames_callback(self, callback: Callable[[Dict], None]):
        """
        Register a callback for per-frame MFCC streams (Ship 1 of
        PHONEME_CORTEX_GRADUAL_STT, Nous + Ace 2026-05-17).

        The callback receives: {
          "frames": list[list[float]] (n_frames x 13 MFCC coeffs),
          "pitch_values": list[float] (parallel to frames),
          "centroid_values": list[float] (parallel to frames),
          "n_frames": int,
          "frame_hop_ms": float (~25ms),
          "frame_size_ms": float (~50ms),
          "speaker": str,
          "speaker_confidence": float,
          "is_music_context": bool,
          "duration_s": float,
          "ts": float
        }
        Called from the reader thread — must be thread-safe.

        Feeds PhonemeCortexFairy for cortex-native STT learning.
        Doctrine: 2026-04-10 learn-to-perceive + 2026-04-05 training-wheels.
        """
        self._phoneme_frames_callback = callback

    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def capture(self, timeout: float = 10.0) -> Optional[Dict]:
        """On-demand single capture with full analysis."""
        return self.send({"cmd": "capture"}, timeout=timeout)

    def start_passive(self) -> Optional[Dict]:
        """Start the passive audio loop in the subprocess."""
        return self.send({"cmd": "start_passive"})

    def stop_passive(self) -> Optional[Dict]:
        """Stop the passive audio loop."""
        return self.send({"cmd": "stop_passive"})

    def set_interval(self, seconds: float) -> Optional[Dict]:
        """Change the foveal analysis interval."""
        return self.send({"cmd": "set_interval", "seconds": seconds})

    def status(self) -> Optional[Dict]:
        """Get interior status."""
        return self.send({"cmd": "status"})

    def ping(self) -> Optional[Dict]:
        """Ping the interior."""
        return self.send({"cmd": "ping"}, timeout=5.0)

    def send_energy(self, amount: float) -> Optional[Dict]:
        """Feed energy into the audio portal's battery (Phase 2)."""
        return self.send({"cmd": "energy", "amount": amount})

    def portal_status(self) -> Optional[Dict]:
        """Get detailed portal physics status from the interior."""
        return self.send({"cmd": "portal_status"})

    def learn_voice(self, name: str, signature: dict = None) -> Optional[Dict]:
        """Teach the audio cortex a speaker's name.

        If signature is provided, associates it directly.
        Otherwise, uses the current audio buffer to extract a signature.

        2026-03-18, Nous — Voice Pattern Profiles
        """
        cmd = {"cmd": "learn_voice", "name": name}
        if signature:
            cmd["signature"] = signature
        return self.send(cmd)

    def get_voice_profiles(self) -> Optional[Dict]:
        """Get all known voice profiles summary."""
        return self.send({"cmd": "voice_profiles"})

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def gate_status(self) -> Dict[str, Any]:
        """Status of the gate itself (not the interior)."""
        return {
            "is_open": self.is_open,
            "python_exe": self.python_exe,
            "sample_rate": self.sample_rate,
            "requests_sent": self._requests_sent,
            "passive_chunks_received": self._passive_chunks_received,
            "transcriptions_received": self._transcription_count,
            "speaker_events": self._speaker_events,
            "errors": self._errors,
            "last_response_ms": round(self._last_response_time * 1000, 1),
            "uptime_seconds": round(
                time.time() - self._opened_at, 1
            ) if self._opened_at else 0,
            "interior_pid": self._process.pid if self._process else None,
        }
