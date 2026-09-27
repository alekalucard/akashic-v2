"""
Mic STT Server -- Persistent NVIDIA Canary speech-to-text from microphone.
Runs under Python 3.12 (has sounddevice, torch, NeMo).

Captures mic audio, detects speech via WebRTC VAD,
runs Canary-1b-flash on speech segments, streams transcriptions to clients.

Protocol (TCP localhost:9878):
  Server -> Client: LENGTH(4 bytes big-endian) + JSON(utf-8)
  JSON: {"text": "...", "confidence": 0.95, "language": "en",
         "duration_s": 2.3, "ts": 1234567890.0}

  Client -> Server: LENGTH=0 (4 zero bytes) = keepalive/ping
  Server -> Client: LENGTH=0 = no new transcription (pong)

Start: python312 mic_stt_server.py
       python312 mic_stt_server.py --device 3  (specific mic device ID)
       python312 mic_stt_server.py --list-devices  (show available devices)

Phase 4: Replaced Whisper with NVIDIA Canary-1b-flash (5.85% WER, zero hallucination loops).
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import argparse
import collections
import json
import os
import struct
import sys
import socket
import tempfile
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

PORT = 9878
HOST = "127.0.0.1"


def _log(msg):
    try:
        print(f"[MicSTT] {msg}", flush=True)
    except Exception:
        pass


def list_input_devices():
    """Print all input devices and exit."""
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    print("\n=== Input Devices ===")
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        api = hostapis[d["hostapi"]]["name"] if d["hostapi"] < len(hostapis) else "?"
        star = " <-- DEFAULT" if i == sd.default.device[0] else ""
        print(f"  [{i}] {d['name']}  ({api}, {d['default_samplerate']}Hz, "
              f"{d['max_input_channels']}ch){star}")
    print()


def find_mic_device():
    """Find the best microphone (NOT Stereo Mix/loopback).

    Priority:
    1. USB microphone (Logitech, Blue, HyperX, etc.)
    2. Default input device (if not Stereo Mix)
    3. Any input device that isn't Stereo Mix/loopback
    """
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    candidates = []

    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        name_lower = d["name"].lower()
        api = hostapis[d["hostapi"]]["name"].lower() if d["hostapi"] < len(hostapis) else ""

        # Skip loopback/stereo mix — those are for system audio, not mic
        if "stereo mix" in name_lower or "loopback" in name_lower:
            continue
        # Skip WASAPI (often buggy for mic capture on Windows)
        if "wasapi" in api:
            continue

        priority = 100
        # USB mics get highest priority
        if any(kw in name_lower for kw in ("usb", "logitech", "blue", "hyperx",
                                            "rode", "samson", "at2020", "yeti",
                                            "snowball", "fifine", "tonor")):
            priority = 1
        # "Microphone" in name
        elif "microphone" in name_lower or "mic" in name_lower:
            priority = 5
        # MME/DirectSound preferred over WDM
        elif "mme" in api or "directsound" in api:
            priority = 10
        # Default input device
        if i == sd.default.device[0]:
            priority = min(priority, 3)

        candidates.append({
            "id": i,
            "name": d["name"],
            "api": hostapis[d["hostapi"]]["name"] if d["hostapi"] < len(hostapis) else "?",
            "sr": int(d["default_samplerate"]),
            "channels": d["max_input_channels"],
            "priority": priority,
        })

    candidates.sort(key=lambda c: c["priority"])
    return candidates


class MicCapture:
    """Captures audio from the microphone using sounddevice.

    Includes auto-gain compensation for quiet USB mics (Logitech headsets
    deliver -40 to -50 dB even with Windows volume maxed).
    """

    def __init__(self, device_id=None, sample_rate=16000):
        self.sample_rate = sample_rate
        self._device_id = device_id
        self._stream = None
        self._running = False
        self._lock = threading.Lock()
        # Ring buffer: last 30 seconds of audio
        self._buffer = np.zeros(sample_rate * 30, dtype=np.float32)
        self._write_pos = 0
        self._total_samples = 0
        # Chunk queue for VAD
        self._chunk_queue = collections.deque(maxlen=100)
        # Auto-gain: boost quiet mic input to usable levels
        self._auto_gain = 8.0  # Start with 8x boost
        self._gain_target_rms = 0.10  # Target ~-20 dB
        self._gain_max = 30.0  # Max 30x
        self._gain_min = 1.0  # Never reduce below 1x
        self._gain_smoothing = 0.95  # Slow adaptation
        self._chunk_count = 0

    def _callback(self, indata, frames, time_info, status):
        """Audio callback — runs in audio thread, must be fast."""
        if status:
            pass  # Overflow/underflow — ignore
        # Convert to mono float32
        audio = indata[:, 0].copy() if indata.ndim > 1 else indata.flatten().copy()

        # Track auto-gain for Whisper (applied AFTER VAD, not to VAD input)
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms > 1e-6:
            desired_gain = self._gain_target_rms / rms
            desired_gain = max(self._gain_min, min(desired_gain, self._gain_max))
            self._auto_gain = (self._gain_smoothing * self._auto_gain +
                               (1 - self._gain_smoothing) * desired_gain)

        self._chunk_count += 1
        if self._chunk_count % 100 == 0:
            _log(f"MIC: raw_rms={rms:.5f}, gain={self._auto_gain:.1f}x")

        with self._lock:
            n = len(audio)
            end = self._write_pos + n
            if end <= len(self._buffer):
                self._buffer[self._write_pos:end] = audio
            else:
                # Wrap around
                first = len(self._buffer) - self._write_pos
                self._buffer[self._write_pos:] = audio[:first]
                self._buffer[:n - first] = audio[first:]
            self._write_pos = end % len(self._buffer)
            self._total_samples += n
        self._chunk_queue.append(audio)

    def start(self, device_id=None):
        """Start capturing from mic."""
        dev = device_id or self._device_id
        try:
            # Try 16kHz mono (Whisper's native rate)
            self._stream = sd.InputStream(
                device=dev,
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                blocksize=int(self.sample_rate * 0.1),  # 100ms chunks
                callback=self._callback,
            )
            self._stream.start()
            self._running = True
            return True
        except Exception as e:
            _log(f"Failed to open device {dev} at {self.sample_rate}Hz: {e}")
            # Try device's native sample rate
            try:
                dev_info = sd.query_devices(dev)
                native_sr = int(dev_info["default_samplerate"])
                if native_sr != self.sample_rate:
                    _log(f"Retrying at native rate {native_sr}Hz...")
                    self.sample_rate = native_sr
                    self._buffer = np.zeros(native_sr * 30, dtype=np.float32)
                    self._stream = sd.InputStream(
                        device=dev,
                        samplerate=native_sr,
                        channels=1,
                        dtype='float32',
                        blocksize=int(native_sr * 0.1),
                        callback=self._callback,
                    )
                    self._stream.start()
                    self._running = True
                    return True
            except Exception as e2:
                _log(f"Native rate also failed: {e2}")
            return False

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
        self._running = False

    def get_chunk(self, timeout=0.5):
        """Get next audio chunk from queue. Returns None on timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                return self._chunk_queue.popleft()
            except IndexError:
                time.sleep(0.01)
        return None

    def get_recent_audio(self, seconds: float) -> np.ndarray:
        """Get the last N seconds of audio from ring buffer."""
        n_samples = int(seconds * self.sample_rate)
        with self._lock:
            if self._total_samples < n_samples:
                n_samples = self._total_samples
            if n_samples == 0:
                return np.zeros(0, dtype=np.float32)
            start = (self._write_pos - n_samples) % len(self._buffer)
            if start + n_samples <= len(self._buffer):
                return self._buffer[start:start + n_samples].copy()
            else:
                first = len(self._buffer) - start
                return np.concatenate([
                    self._buffer[start:],
                    self._buffer[:n_samples - first]
                ])


class WebRTCVAD:
    """Voice Activity Detection using Google's WebRTC VAD.

    WebRTC VAD is purpose-built for speech detection and works reliably
    at any input level — it uses spectral analysis, not just energy.
    This solves the quiet USB mic problem that plagued energy-based VAD.

    The VAD processes 30ms frames of 16kHz int16 audio.
    We accumulate speech frames and return complete utterances.
    """

    def __init__(self, sample_rate=16000, aggressiveness=2):
        """
        Args:
            sample_rate: Must be 8000, 16000, 32000 or 48000
            aggressiveness: 0-3 (0=least aggressive, 3=most aggressive filtering)
                           2 is good balance — catches speech but not all noise
        """
        import webrtcvad
        self.sample_rate = sample_rate
        self._vad = webrtcvad.Vad(aggressiveness)
        self._frame_duration_ms = 30  # WebRTC VAD needs 10, 20, or 30ms frames
        self._frame_size = int(sample_rate * self._frame_duration_ms / 1000)  # 480 samples @ 16kHz

        self._speech_active = False
        self._speech_start = 0.0
        self._silence_start = 0.0
        self._min_speech_duration = 0.8  # Min 0.8s to transcribe
        self._max_speech_duration = 15.0  # Max 15s per utterance
        self._silence_timeout = 1.2  # 1.2s silence ends utterance
        self._speech_buffer = []
        self._pre_buffer = collections.deque(maxlen=5)  # Keep 500ms before trigger

        # Debounce: need N consecutive VAD-speech frames to start
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._speech_start_threshold = 8  # 8 frames = 240ms of speech to trigger
        self._speech_end_threshold = 40  # 40 frames = 1.2s of silence to end

        self._chunk_count = 0
        self._leftover = np.zeros(0, dtype=np.float32)  # Leftover from previous chunk

    def process_chunk(self, chunk):
        """Process a 100ms audio chunk. Returns complete utterance or None.

        The chunk is split into 30ms frames for WebRTC VAD.
        """
        now = time.monotonic()
        self._chunk_count += 1

        # Prepend any leftover from previous chunk
        if len(self._leftover) > 0:
            audio = np.concatenate([self._leftover, chunk])
        else:
            audio = chunk

        # Process in 30ms frames
        n_frames = len(audio) // self._frame_size
        self._leftover = audio[n_frames * self._frame_size:]

        any_speech = False
        for i in range(n_frames):
            frame = audio[i * self._frame_size:(i + 1) * self._frame_size]
            # WebRTC VAD needs int16 bytes
            frame_int16 = (frame * 32767).astype(np.int16).tobytes()
            is_speech = self._vad.is_speech(frame_int16, self.sample_rate)

            if is_speech:
                any_speech = True
                self._consecutive_speech += 1
                self._consecutive_silence = 0
            else:
                self._consecutive_silence += 1
                self._consecutive_speech = 0

        # Log every 100 chunks (~10s)
        if self._chunk_count % 100 == 0:
            _log(f"VAD: speech_active={self._speech_active}, "
                 f"consec_speech={self._consecutive_speech}, "
                 f"consec_silence={self._consecutive_silence}, "
                 f"rms={float(np.sqrt(np.mean(chunk**2))):.4f}")

        if not self._speech_active:
            self._pre_buffer.append(chunk)
            if self._consecutive_speech >= self._speech_start_threshold:
                self._speech_active = True
                self._speech_start = now
                self._silence_start = 0.0
                # Include pre-buffer
                self._speech_buffer = list(self._pre_buffer)
                _log(f"Speech START (after {self._consecutive_speech} speech frames)")
        else:
            self._speech_buffer.append(chunk)
            speech_duration = now - self._speech_start

            if not any_speech:
                if self._silence_start == 0.0:
                    self._silence_start = now
            else:
                self._silence_start = 0.0

            # End conditions
            should_end = False
            if self._silence_start > 0 and (now - self._silence_start) >= self._silence_timeout:
                should_end = True
            if speech_duration >= self._max_speech_duration:
                should_end = True

            if should_end:
                self._speech_active = False
                self._consecutive_speech = 0
                self._consecutive_silence = 0
                if speech_duration >= self._min_speech_duration and self._speech_buffer:
                    result = np.concatenate(self._speech_buffer)
                    self._speech_buffer = []
                    _log(f"Speech END ({speech_duration:.1f}s)")
                    return result
                self._speech_buffer = []

        return None


def main():
    parser = argparse.ArgumentParser(description="Mic STT Server (Canary-1b-flash)")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--device", type=int, default=None, help="Audio device ID")
    parser.add_argument("--list-devices", action="store_true", help="List input devices")
    parser.add_argument("--model", default="nvidia/canary-1b-flash", help="NeMo ASR model name")
    parser.add_argument("--gpu", action="store_true", default=True, help="Use GPU")
    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
        return

    # ── Find mic device ──
    if args.device is not None:
        dev_info = sd.query_devices(args.device)
        _log(f"Using specified device [{args.device}]: {dev_info['name']}")
        selected_device = args.device
    else:
        candidates = find_mic_device()
        if not candidates:
            _log("ERROR: No microphone found!")
            sys.exit(1)
        selected_device = candidates[0]["id"]
        _log(f"Auto-selected mic: [{selected_device}] {candidates[0]['name']} "
             f"({candidates[0]['api']})")
        if len(candidates) > 1:
            _log(f"  Other candidates: {[(c['id'], c['name']) for c in candidates[1:3]]}")

    # ── Start mic capture ──
    mic = MicCapture(sample_rate=16000)
    if not mic.start(selected_device):
        _log("ERROR: Failed to start mic capture!")
        sys.exit(1)
    _log(f"Mic capture started at {mic.sample_rate}Hz")

    # ── Load Canary-1b-flash ──
    # Priority: 1) Audio manifold (portal_canary_engine) 2) from_pretrained() fallback
    t0 = time.perf_counter()

    import torch
    # Suppress verbose NeMo/Lightning warnings for inference-only use
    import logging
    for _logger_name in ('nemo', 'pytorch_lightning', 'lightning', 'nemo.utils'):
        logging.getLogger(_logger_name).setLevel(logging.ERROR)

    device = "cuda" if args.gpu and torch.cuda.is_available() else "cpu"
    canary_model = None
    _using_portal_engine = False
    _portal_engine = None

    # ── Try audio.manifold loading first (direct read, adds mass to gravity) ──
    _manifold_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "state", "akashic", "audio.manifold")
    )
    if os.path.exists(_manifold_path):
        try:
            # Import portal engine from cortex directory
            _cortex_dir = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..",
                             "fairies", "P40_Sensory", "cortex")
            )
            if _cortex_dir not in sys.path:
                sys.path.insert(0, _cortex_dir)
            from portal_canary_engine import PortalCanaryEngine

            _log(f"Loading Canary from audio manifold: {_manifold_path}")
            _portal_engine = PortalCanaryEngine(_manifold_path, model_prefix="canary")
            if _portal_engine.boot():
                if _portal_engine.ensure_loaded(device=device):
                    canary_model = _portal_engine._model
                    _using_portal_engine = True
                    load_time = time.perf_counter() - t0
                    _log(f"Canary loaded from AUDIO MANIFOLD in {load_time:.1f}s "
                         f"(mass={_portal_engine.mass:.1f}MB)")
                else:
                    _log("Portal engine ensure_loaded() failed — falling back to from_pretrained()")
            else:
                _log("Portal engine boot() failed — falling back to from_pretrained()")
        except Exception as e:
            _log(f"Manifold loading failed: {e} — falling back to from_pretrained()")

    # ── Fallback: load from HuggingFace (standard path) ──
    if canary_model is None:
        _log(f"Loading Canary model '{args.model}' via from_pretrained()...")
        from nemo.collections.asr.models import EncDecMultiTaskModel

        canary_model = EncDecMultiTaskModel.from_pretrained(args.model)
        if device == "cuda":
            canary_model = canary_model.cuda()
        canary_model.eval()

        # Set greedy decoding (beam_size=1) for speed
        decode_cfg = canary_model.cfg.decoding
        decode_cfg.beam.beam_size = 1
        canary_model.change_decoding_strategy(decode_cfg)

    # Temp directory for audio files (Canary needs file paths, not numpy arrays)
    _temp_dir = tempfile.mkdtemp(prefix="canary_stt_")
    _temp_wav = os.path.join(_temp_dir, "utterance.wav")

    load_time = time.perf_counter() - t0
    _load_source = "audio_manifold" if _using_portal_engine else "from_pretrained"
    _log(f"Canary loaded on {device} in {load_time:.1f}s (source: {_load_source})")

    # ── VAD (WebRTC — works at any input level) ──
    vad = WebRTCVAD(sample_rate=mic.sample_rate, aggressiveness=2)

    # ── Connected clients ──
    clients = []
    clients_lock = threading.Lock()

    def broadcast(payload_dict):
        """Send transcription to all connected clients."""
        data = json.dumps(payload_dict).encode("utf-8")
        msg = struct.pack(">I", len(data)) + data
        with clients_lock:
            dead = []
            for c in clients:
                try:
                    c.sendall(msg)
                except Exception:
                    dead.append(c)
            for c in dead:
                clients.remove(c)
                try:
                    c.close()
                except Exception:
                    pass

    # ── TCP server for clients ──
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, args.port))
    srv.listen(4)
    _log(f"Listening on {HOST}:{args.port}")

    def accept_clients():
        while True:
            try:
                conn, addr = srv.accept()
                conn.settimeout(5.0)
                with clients_lock:
                    clients.append(conn)
                _log(f"Client connected from {addr}")
            except Exception:
                break

    accept_thread = threading.Thread(target=accept_clients, daemon=True)
    accept_thread.start()

    # ── Write PID file ──
    pid_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "state", "mic_stt_server.pid")
    )
    try:
        with open(pid_path, "w") as f:
            f.write(f"{os.getpid()}\n{args.port}\n")
    except Exception:
        pass

    # ── Transcribe function ──
    def transcribe(audio_np):
        """Run Canary-1b-flash on audio. Returns text or empty string."""
        try:
            # Resample if needed (Canary wants 16kHz)
            if mic.sample_rate != 16000:
                import scipy.signal
                audio_16k = scipy.signal.resample(
                    audio_np, int(len(audio_np) * 16000 / mic.sample_rate)
                ).astype(np.float32)
            else:
                audio_16k = audio_np

            # Normalize audio
            peak = np.abs(audio_16k).max()
            if peak > 0:
                audio_16k = audio_16k / peak * 0.9

            # Write to temp wav (Canary requires file paths)
            sf.write(_temp_wav, audio_16k, 16000)

            # Transcribe with Canary
            with torch.no_grad():
                output = canary_model.transcribe(
                    [_temp_wav],
                    batch_size=1,
                    pnc='yes',       # Punctuation and capitalization
                    source_lang='en',
                    target_lang='en',
                )

            if output and len(output) > 0:
                text = output[0].text if hasattr(output[0], 'text') else str(output[0])
                return text.strip()
            return ""
        except Exception as e:
            _log(f"Transcription error: {e}")
            return ""

    # ── Main loop: capture -> VAD -> transcribe -> broadcast ──
    _log("Listening for speech...")
    transcription_count = 0

    try:
        while True:
            chunk = mic.get_chunk(timeout=0.5)
            if chunk is None:
                continue

            utterance = vad.process_chunk(chunk)
            if utterance is not None:
                duration = len(utterance) / mic.sample_rate
                _log(f"Speech detected ({duration:.1f}s) -- transcribing...")

                t1 = time.perf_counter()
                text = transcribe(utterance)
                elapsed = time.perf_counter() - t1

                if text and len(text) > 1:
                    # Canary has built-in hallucination resistance, but keep minimal safety net
                    _clean = text.lower().strip(".!?, ")
                    _word_count = len(text.split())
                    _is_hallucination = (
                        _word_count <= 1 and duration > 8.0  # 1 word from 8s+ audio = suspicious
                    )
                    if not _is_hallucination:
                        transcription_count += 1
                        _log(f"[#{transcription_count}] ({elapsed:.1f}s) \"{text}\"")
                        broadcast({
                            "text": text,
                            "duration_s": round(duration, 2),
                            "transcribe_time_s": round(elapsed, 2),
                            "ts": time.time(),
                            "n": transcription_count,
                        })
                    else:
                        _log(f"Filtered hallucination: \"{text}\"")
                else:
                    _log(f"Empty transcription ({elapsed:.1f}s, {duration:.1f}s audio)")

    except KeyboardInterrupt:
        _log("Shutting down...")
    finally:
        mic.stop()
        srv.close()
        try:
            os.unlink(pid_path)
        except Exception:
            pass
        # Clean up temp directory
        try:
            import shutil
            shutil.rmtree(_temp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
