"""
Audio Cortex Interior - Always-on audio capture and analysis subprocess.

Runs under Python 3.12 (NOT 3.14t) because it needs:
  - sounddevice (WASAPI/WDM audio capture)
  - numpy (signal processing)
  - scipy (spectral analysis, MFCC computation)

Communicates with the host (AudioCortexFairy on Python 3.14t server)
via JSON-per-line stdin/stdout pipes, mirroring visual_cortex_interior.py.

Captures system audio via Stereo Mix (loopback) or WASAPI loopback device,
providing two-speed perception:
  PERIPHERAL (fast, every ~50ms chunk): level, onset, spectral centroid
  FOVEAL (slow, every ~500ms buffer): full spectral bands, pitch, speech detection

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Usage:
    python audio_cortex_interior.py [--interval 0.5] [--sample-rate 44100] [--device ID]

IPC Protocol (stdin -> commands, stdout -> responses):
    {"cmd": "ping"}                       -> {"status": "pong", ...}
    {"cmd": "capture"}                    -> {"status": "ok", "type": "audio_analysis", ...}
    {"cmd": "start_passive"}              -> {"status": "ok"}
    {"cmd": "stop_passive"}               -> {"status": "ok"}
    {"cmd": "set_interval", "seconds": N} -> {"status": "ok"}
    {"cmd": "status"}                     -> {"status": "ok", "type": "status", ...}
    {"cmd": "shutdown"}                   -> {"status": "ok"} then exit

Passive pushes (stdout, unsolicited):
    {"status": "ok", "type": "passive_audio", "data": {...}}
"""

import sys
import os
import json
import time
import math
import threading
import argparse
import collections
from pathlib import Path
from typing import Optional, Dict, List, Any

# All logging goes to stderr (stdout is IPC pipe)
def _log(msg: str):
    print(f"[AudioInterior] {msg}", file=sys.stderr, flush=True)

def _err(msg: str):
    print(f"[AudioInterior] ERROR: {msg}", file=sys.stderr, flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS - Audio stack (Python 3.12 only)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    _err("numpy not available — audio processing disabled")

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False
    _err("sounddevice not available — no audio capture")

try:
    from scipy import signal as scipy_signal
    from scipy.fft import rfft, rfftfreq
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    _log("scipy not available — spectral analysis limited to numpy FFT")

# Whisper — speech-to-text (lazy loaded on first speech detection)
HAS_WHISPER = False
try:
    import faster_whisper  # noqa: F401
    HAS_WHISPER = True
except ImportError:
    _log("faster-whisper not available — speech transcription disabled")

# Demucs — vocal source separation (2026-04-17, Nous + Ace)
# Required for music-context STT. Without separation, Whisper/Canary
# hallucinate heavily on sung vocals mixed with backing track. With Demucs
# preprocessing, vocals stem is clean enough for proper lyric transcription.
HAS_DEMUCS = False
try:
    import demucs  # noqa: F401
    from demucs.pretrained import get_model as _demucs_get_model
    from demucs.apply import apply_model as _demucs_apply_model
    HAS_DEMUCS = True
except ImportError:
    _log("demucs not available — music-context STT will be disabled")

# Portal physics — battery, energy bridge (shared with cortex portal)
# These classes are self-contained (no fairy dependencies).
# Import from infrastructure if available, else define inline fallbacks.
HAS_PORTAL_PHYSICS = False
try:
    from infrastructure.portal_interior import PortalBattery, InteriorEnergyBridge
    HAS_PORTAL_PHYSICS = True
    _log("Portal physics available (PortalBattery + InteriorEnergyBridge)")
except ImportError:
    try:
        # Subprocess may need explicit path
        _project_root = str(Path(__file__).resolve().parents[3])
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
        from infrastructure.portal_interior import PortalBattery, InteriorEnergyBridge
        HAS_PORTAL_PHYSICS = True
        _log("Portal physics available (via explicit path)")
    except ImportError as _e:
        _log(f"Portal physics not available ({_e}) — running without battery/energy bridge")

# Voice Profiles — speaker identification (2026-03-18, Nous)
HAS_VOICE_PROFILES = False
try:
    from fairies.P40_Sensory.cortex.voice_profiles import (
        VoiceProfileStore, VoiceSignature,
    )
    HAS_VOICE_PROFILES = True
    _log("Voice profile system available")
except ImportError:
    try:
        _vp_dir = str(Path(__file__).parent)
        if _vp_dir not in sys.path:
            sys.path.insert(0, _vp_dir)
        from voice_profiles import VoiceProfileStore, VoiceSignature
        HAS_VOICE_PROFILES = True
        _log("Voice profile system available (direct import)")
    except ImportError as _e:
        _log(f"Voice profiles not available ({_e}) — speaker identification disabled")

# Portal Whisper Engine — card-based model loading (Phase 3)
HAS_PORTAL_WHISPER = False
_WHISPER_CARDS_PATH = str(Path(__file__).parent / "whisper_cards" / "cards.json")
try:
    from fairies.P40_Sensory.cortex.portal_whisper_engine import PortalWhisperEngine
    if os.path.exists(_WHISPER_CARDS_PATH):
        HAS_PORTAL_WHISPER = True
        _log(f"Portal Whisper cards available: {_WHISPER_CARDS_PATH}")
    else:
        _log(f"Portal Whisper engine available but no cards at {_WHISPER_CARDS_PATH}")
except ImportError:
    try:
        # Direct import for subprocess context
        _portal_whisper_dir = str(Path(__file__).parent)
        if _portal_whisper_dir not in sys.path:
            sys.path.insert(0, _portal_whisper_dir)
        from portal_whisper_engine import PortalWhisperEngine
        if os.path.exists(_WHISPER_CARDS_PATH):
            HAS_PORTAL_WHISPER = True
            _log(f"Portal Whisper cards available (direct import)")
    except ImportError:
        pass

# Portal Canary Engine — manifold-loaded Canary-1b-flash STT (2026-03-22, Nous)
HAS_PORTAL_CANARY = False
_CANARY_MANIFOLD_PATH = str(Path(__file__).resolve().parents[3] / "state" / "akashic" / "audio.manifold")
try:
    from fairies.P40_Sensory.cortex.portal_canary_engine import PortalCanaryEngine
    if os.path.exists(_CANARY_MANIFOLD_PATH):
        HAS_PORTAL_CANARY = True
        _log(f"Portal Canary manifold available: {_CANARY_MANIFOLD_PATH}")
    else:
        _log(f"Portal Canary engine available but no manifold at {_CANARY_MANIFOLD_PATH}")
except ImportError:
    try:
        _canary_dir = str(Path(__file__).parent)
        if _canary_dir not in sys.path:
            sys.path.insert(0, _canary_dir)
        from portal_canary_engine import PortalCanaryEngine
        if os.path.exists(_CANARY_MANIFOLD_PATH):
            HAS_PORTAL_CANARY = True
            _log(f"Portal Canary manifold available (direct import)")
    except ImportError:
        _log("Portal Canary engine not available")


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO CAPTURE
# ═══════════════════════════════════════════════════════════════════════════════

class AudioCapture:
    """
    Captures system audio via Stereo Mix (loopback) or specified input device.

    Uses sounddevice InputStream in callback mode — audio flows continuously
    into a ring buffer. The analysis thread reads from the buffer.
    """

    def __init__(self, device_id: Optional[int] = None, sample_rate: int = 44100,
                 chunk_ms: int = 50):
        self.sample_rate = sample_rate
        self.chunk_samples = int(sample_rate * chunk_ms / 1000)  # e.g. 2205 @ 44100/50ms
        self.chunk_ms = chunk_ms
        self._device_id = device_id
        self._stream: Optional[sd.InputStream] = None
        self._channels = 1  # May be updated to 2 on open
        self._running = False

        # Ring buffer: holds last ~2 seconds of audio for foveal analysis
        self._buffer_seconds = 2.0
        self._buffer_size = int(sample_rate * self._buffer_seconds)
        self._ring_buffer = None  # np.ndarray, set on start
        self._write_pos = 0
        self._lock = threading.Lock()

        # Chunk queue: peripheral analysis reads from here
        self._chunk_queue = collections.deque(maxlen=20)  # ~1 second backlog max

        # Auto-gain: normalize quiet microphone input to usable levels.
        # FIX 2026-03-19 Nous: Logitech USB mic delivers audio at -40 to -50 dB
        # even with Windows volume maxed. Speech detection needs -20 dB+ to
        # resolve pitch and spectral features. Auto-gain tracks peak level
        # over a sliding window and scales up to a target RMS.
        self._auto_gain = 10.0  # Start with 10x boost (most mics need it)
        self._gain_target_rms = 0.08  # Target ~-22 dB — clear speech level
        self._gain_max = 50.0  # Max 50x amplification
        self._gain_smoothing = 0.8  # Faster adaptation (~20 chunks / 1s to converge)
        self._gain_peak_tracker = 0.001  # Running peak estimate

        # Stats
        self._chunks_captured = 0
        self._overflows = 0

    def _find_loopback_candidates(self) -> List[Dict]:
        """
        Find all suitable loopback capture devices, ranked by priority.

        Returns list of {id, name, hostapi, sr, channels} dicts.

        Priority order (learned from Ace's system 2026-03-16):
        1. "Sound Mapper" / "Primary Sound Capture" on MME/DirectSound
           These are Windows' virtual aggregation devices that route Stereo Mix
           when it's the selected default recording device. MOST RELIABLE.
        2. Stereo Mix on MME/DirectSound (direct access)
        3. Any "loopback" device on MME/DirectSound
        4. Stereo Mix on WDM-KS (opens but sometimes delivers no data!)
        5. Stereo Mix on WASAPI (often fails with -9996)
        6. Other fallbacks
        """
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        candidates = []

        for i, d in enumerate(devices):
            if d["max_input_channels"] <= 0:
                continue
            name_lower = d["name"].lower()
            hostapi_info = hostapis[d["hostapi"]] if d["hostapi"] < len(hostapis) else {}
            hostapi_name = hostapi_info.get("name", "unknown")
            api_lower = hostapi_name.lower()

            is_stereo_mix = "stereo mix" in name_lower
            is_loopback = "loopback" in name_lower
            is_mapper = "sound mapper" in name_lower or "primary sound" in name_lower
            is_mme = "mme" in api_lower
            is_directsound = "directsound" in api_lower
            is_wasapi = "wasapi" in api_lower
            is_wdm = "wdm" in api_lower

            # Priority score (lower = better)
            priority = None

            if is_mapper and (is_mme or is_directsound):
                # Windows virtual input — routes Stereo Mix when enabled
                priority = 1  # BEST: reliable system audio on MME/DS
            elif is_stereo_mix and (is_mme or is_directsound):
                priority = 2  # Good: direct Stereo Mix on MME/DS
            elif is_loopback and (is_mme or is_directsound):
                priority = 3
            elif is_stereo_mix and is_wdm:
                priority = 8  # Opens but may not deliver data
            elif is_loopback and is_wdm:
                priority = 9
            elif is_stereo_mix and is_wasapi:
                priority = 12  # Often fails entirely
            elif is_loopback and is_wasapi:
                priority = 13

            if priority is not None:
                candidates.append({
                    "id": i,
                    "name": d["name"],
                    "hostapi": hostapi_name,
                    "sr": d["default_samplerate"],
                    "channels": d["max_input_channels"],
                    "priority": priority,
                })

        # Sort by priority
        candidates.sort(key=lambda c: c["priority"])

        # If no loopback/mixer candidates found, add fallbacks
        if not candidates:
            default_in = sd.default.device[0]
            if default_in is not None and default_in >= 0:
                d = sd.query_devices(default_in)
                if d["max_input_channels"] > 0:
                    hostapi_info = hostapis[d["hostapi"]] if d["hostapi"] < len(hostapis) else {}
                    candidates.append({
                        "id": default_in,
                        "name": d["name"],
                        "hostapi": hostapi_info.get("name", "unknown"),
                        "sr": d["default_samplerate"],
                        "channels": d["max_input_channels"],
                        "priority": 50,
                    })
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    hostapi_info = hostapis[d["hostapi"]] if d["hostapi"] < len(hostapis) else {}
                    if not any(c["id"] == i for c in candidates):
                        candidates.append({
                            "id": i,
                            "name": d["name"],
                            "hostapi": hostapi_info.get("name", "unknown"),
                            "sr": d["default_samplerate"],
                            "channels": d["max_input_channels"],
                            "priority": 100,
                        })

        return candidates

    def _try_open_device(self, candidate: Dict) -> bool:
        """Try to open a specific audio device. Returns True on success."""
        device = candidate["id"]
        dev_name = candidate["name"]
        hostapi = candidate["hostapi"]

        # Try requested sample rate first, then device's native rate
        sample_rates = [self.sample_rate]
        native_sr = int(candidate["sr"])
        if native_sr != self.sample_rate and native_sr > 0:
            sample_rates.append(native_sr)

        # Try mono first, then stereo (some devices require stereo)
        channel_configs = [1]
        if candidate["channels"] >= 2:
            channel_configs.append(2)

        for sr in sample_rates:
            for ch in channel_configs:
                try:
                    _log(f"Trying device {device} ({dev_name}) via {hostapi} "
                         f"(sr={sr}, ch={ch}, chunk={self.chunk_ms}ms)")

                    chunk_samples = int(sr * self.chunk_ms / 1000)
                    self._ring_buffer = np.zeros(int(sr * self._buffer_seconds), dtype=np.float32)
                    self._write_pos = 0

                    self._stream = sd.InputStream(
                        device=device,
                        samplerate=sr,
                        channels=ch,
                        dtype="float32",
                        blocksize=chunk_samples,
                        callback=self._audio_callback,
                    )
                    self._stream.start()

                    # Update instance vars to reflect actual config
                    self.sample_rate = sr
                    self.chunk_samples = chunk_samples
                    self._buffer_size = int(sr * self._buffer_seconds)
                    self._channels = ch
                    self._running = True

                    # Liveness check: verify the callback actually fires
                    # Some devices (WDM-KS Stereo Mix) open without error
                    # but never deliver any audio data.
                    _log(f"Opened {dev_name} via {hostapi} — checking liveness...")
                    check_start = time.time()
                    initial_chunks = self._chunks_captured
                    while time.time() - check_start < 2.0:
                        if self._chunks_captured > initial_chunks:
                            break
                        time.sleep(0.1)

                    if self._chunks_captured <= initial_chunks:
                        _log(f"  Device opened but delivered NO data in 2s — skipping")
                        self._stream.stop()
                        self._stream.close()
                        self._stream = None
                        self._running = False
                        continue  # Try next config

                    chunks_got = self._chunks_captured - initial_chunks
                    _log(f"Audio capture LIVE on {dev_name} via {hostapi} "
                         f"(device={device}, sr={sr}, ch={ch}, "
                         f"got {chunks_got} chunks in liveness check)")
                    return True

                except Exception as e:
                    _log(f"  Failed: {e}")
                    if self._stream:
                        try:
                            self._stream.close()
                        except Exception:
                            pass
                        self._stream = None

        return False

    def start(self) -> bool:
        """Open audio stream and begin capture. Tries multiple devices/configs."""
        if not HAS_SOUNDDEVICE or not HAS_NUMPY:
            _err("Cannot start: sounddevice or numpy missing")
            return False

        # If explicit device ID given, try only that
        if self._device_id is not None:
            dev_info = sd.query_devices(self._device_id)
            hostapis = sd.query_hostapis()
            hostapi_info = hostapis[dev_info["hostapi"]] if dev_info["hostapi"] < len(hostapis) else {}
            candidate = {
                "id": self._device_id,
                "name": dev_info["name"],
                "hostapi": hostapi_info.get("name", "unknown"),
                "sr": dev_info["default_samplerate"],
                "channels": dev_info["max_input_channels"],
                "priority": 0,
            }
            if self._try_open_device(candidate):
                return True
            _err(f"Failed to open specified device {self._device_id}")
            return False

        # Auto-detect: try candidates in priority order
        candidates = self._find_loopback_candidates()
        if not candidates:
            _err("No audio capture devices found")
            return False

        _log(f"Found {len(candidates)} audio capture candidates:")
        for c in candidates:
            _log(f"  [{c['priority']}] device {c['id']}: {c['name']} ({c['hostapi']}, sr={c['sr']})")

        for candidate in candidates:
            if self._try_open_device(candidate):
                return True

        _err("Failed to open any audio capture device")
        return False

    def stop(self):
        """Stop audio capture."""
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        _log("Audio capture stopped")

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk. MUST be fast."""
        if status:
            if status.input_overflow:
                self._overflows += 1

        # Convert to mono (handles both mono and stereo devices)
        if indata.shape[1] > 1:
            chunk = np.mean(indata, axis=1)  # Mix stereo to mono
        else:
            chunk = indata[:, 0].copy()

        # Auto-gain for quiet mics (v5 — removed noise gate, rely on classifier).
        # FIX 2026-03-19 Nous: noise gate at -45dB was gating EVERYTHING to
        # silence (-99dB), because raw mic level is ~-50 to -55dB normally.
        # The fixed classifier (v4, log-scale subtraction) handles noise correctly.
        # Just amplify everything and let the classifier sort it out.
        chunk_rms = float(np.sqrt(np.mean(chunk ** 2)))
        if chunk_rms > 0.0001:  # Above digital zero (-80dB)
            gain = self._gain_target_rms / chunk_rms
            gain = min(gain, self._gain_max)
            # Smooth gain changes (fast attack, slow release)
            if gain < self._auto_gain:
                self._auto_gain = gain  # Fast attack (instant)
            else:
                self._auto_gain = self._auto_gain * 0.7 + gain * 0.3  # Slow release
        chunk = chunk * self._auto_gain
        np.clip(chunk, -1.0, 1.0, out=chunk)

        self._chunks_captured += 1

        # Write to ring buffer
        with self._lock:
            end = self._write_pos + len(chunk)
            if end <= self._buffer_size:
                self._ring_buffer[self._write_pos:end] = chunk
            else:
                # Wrap around
                first = self._buffer_size - self._write_pos
                self._ring_buffer[self._write_pos:] = chunk[:first]
                self._ring_buffer[:len(chunk) - first] = chunk[first:]
            self._write_pos = end % self._buffer_size

        # Push to chunk queue for peripheral analysis
        self._chunk_queue.append(chunk)

    def get_chunk(self) -> Optional[np.ndarray]:
        """Get next audio chunk for peripheral analysis (non-blocking)."""
        try:
            return self._chunk_queue.popleft()
        except IndexError:
            return None

    def get_buffer(self, duration_ms: int = 500) -> Optional[np.ndarray]:
        """Get recent audio buffer for foveal analysis."""
        if self._ring_buffer is None:
            return None
        n_samples = min(int(self.sample_rate * duration_ms / 1000), self._buffer_size)
        with self._lock:
            end = self._write_pos
            start = (end - n_samples) % self._buffer_size
            if start < end:
                return self._ring_buffer[start:end].copy()
            else:
                return np.concatenate([
                    self._ring_buffer[start:],
                    self._ring_buffer[:end]
                ]).copy()


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO ANALYSIS - Two-Speed Perception
# ═══════════════════════════════════════════════════════════════════════════════

class AudioAnalyzer:
    """
    Two-speed audio analysis mirroring visual cortex's peripheral/foveal model.

    PERIPHERAL (fast, every chunk ~50ms, <2ms):
      - RMS level (dB)
      - Onset detection (sudden volume change)
      - Spectral centroid (brightness/timbre)
      - Voice band detection
      - Silence detection

    FOVEAL (slow, every ~500ms, ~10-20ms):
      - Mel-frequency spectral bands (40 bands)
      - MFCC coefficients (speech fingerprint)
      - Pitch estimation
      - Speech vs music vs noise classification
      - Temporal pattern (steady/rhythmic/transient/silence)
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._prev_rms = 0.001  # For onset detection
        self._rms_history = collections.deque(maxlen=20)  # ~1 second
        self._silence_threshold = 0.002  # -54 dB
        self._onset_ratio = 3.0  # Sudden 3x jump = onset

        # Foveal analysis state
        self._prev_spectral = None  # For change detection

        # Ship 5-B (2026-05-17, Nous + Ace): rolling spectral baseline for
        # ambient-noise adaptation. Per Ace's noise-adaptation framing:
        # the substrate should LEARN its acoustic baseline (fan, HVAC, room
        # tone) and attend to deviations RISING above it. Voice = figure
        # against the ground of constant ambient. EMA with slow alpha so
        # constant noise emerges as baseline over ~30s, voice transients
        # don't get absorbed.
        self._spectral_baseline = None  # Rolling EMA of mel bands (40)
        self._baseline_alpha = 0.02     # Slow adaptation; ~30s to converge
        self._voice_band_override_count = 0  # v65 observability counter
        self._voice_band_override_threshold = 0.5  # log-units above baseline

    # ───────────────────────────────────────────────────────────────────
    # PERIPHERAL - Fast path (~1-2ms per chunk)
    # ───────────────────────────────────────────────────────────────────

    def peripheral(self, chunk: np.ndarray) -> Dict[str, Any]:
        """Fast analysis for every audio chunk. Is something happening?"""
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        level_db = round(20 * np.log10(max(rms, 1e-10)), 1)
        is_silence = rms < self._silence_threshold

        # Onset detection: sudden volume increase
        onset = bool(rms > self._prev_rms * self._onset_ratio and not is_silence)

        # Spectral centroid via FFT (brightness indicator)
        centroid = 0.0
        is_voice_band = False
        if not is_silence:
            try:
                fft_data = np.abs(np.fft.rfft(chunk))
                freqs = np.fft.rfftfreq(len(chunk), 1.0 / self.sample_rate)
                total = fft_data.sum()
                if total > 0:
                    centroid = float(np.sum(freqs * fft_data) / total)
                    is_voice_band = 100 < centroid < 4000
            except Exception:
                pass

        # Update state
        self._prev_rms = max(rms, 0.001)
        self._rms_history.append(rms)

        # Compute short-term energy trend
        if len(self._rms_history) >= 4:
            recent = list(self._rms_history)
            trend = np.mean(recent[-4:]) - np.mean(recent[:4]) if len(recent) >= 8 else 0.0
        else:
            trend = 0.0

        return {
            "level_db": level_db,
            "rms": round(rms, 6),
            "onset": bool(onset),
            "spectral_centroid": round(centroid, 1),
            "is_voice_band": bool(is_voice_band),
            "is_silence": bool(is_silence),
            "energy_trend": round(float(trend), 4),
        }

    # ───────────────────────────────────────────────────────────────────
    # FOVEAL - Slow path (~10-20ms per 500ms buffer)
    # ───────────────────────────────────────────────────────────────────

    def foveal(self, buffer: np.ndarray) -> Dict[str, Any]:
        """Deep analysis on accumulated audio buffer. What is this sound?"""
        result: Dict[str, Any] = {}

        n = len(buffer)
        if n < 1024:
            return {"error": "buffer_too_short"}

        # 1. Mel-frequency spectral bands (40 bands)
        spectral_bands = self._compute_mel_bands(buffer, n_bands=40)
        result["spectral_bands"] = [round(float(b), 4) for b in spectral_bands]

        # 2. MFCC coefficients (13 — speech fingerprint)
        mfcc = self._compute_mfcc(buffer, n_coeffs=13)
        result["mfcc"] = [round(float(c), 4) for c in mfcc]

        # Item 7e-1 (Nous + Ace 2026-05-16): "Sound is very dimensional."
        # Music needs different pitch tracking than speech (polyphonic content
        # has weaker autocorrelation peak ratio). Classify music FIRST so we
        # can route pitch detection through music-aware path when applicable.
        # `_classify_music` only needs spectral_bands + buffer (no pitch dep).
        # The music-aware method is today's fusion entry point for layering
        # in band-pass / spectral-centroid / YIN as separate methods later.
        _is_music_early = bool(self._classify_music(spectral_bands, buffer))

        # 3. Pitch estimation — route by music vs speech context
        if _is_music_early:
            pitch = self._estimate_pitch_music(buffer)
        else:
            pitch = self._estimate_pitch(buffer)
        result["pitch_hz"] = round(pitch, 1) if pitch > 0 else 0.0

        # 4. Classification (is_music reuses early classification result)
        rms = float(np.sqrt(np.mean(buffer ** 2)))
        result["is_speech"] = bool(self._classify_speech(spectral_bands, mfcc, pitch))
        result["is_music"] = _is_music_early
        result["is_silence"] = bool(rms < self._silence_threshold)
        result["rms_db"] = round(20 * np.log10(max(rms, 1e-10)), 1)
        # Diagnostic: voice band dominance (log-scale difference)
        # Positive = voice louder than average. >0.2 = speech likely.
        if len(spectral_bands) >= 30:
            _ve = float(np.mean(spectral_bands[5:20]))
            _te = float(np.mean(spectral_bands))
            result["voice_diff"] = round(_ve - _te, 3)  # Log-scale difference
        result["mfcc1"] = round(float(mfcc[1]), 2) if len(mfcc) > 1 else 0.0

        # ═══════════════════════════════════════════════════════════════════
        # Ship 5-B (2026-05-17, Nous + Ace): SPECTRAL BASELINE EMA + VOICE
        # BAND OVERRIDE — biology-equivalent of brainstem-level adaptation.
        #
        # Update rolling baseline of mel bands (slow EMA), then check if
        # voice-band-energy has risen significantly above baseline. If so,
        # OVERRIDE music classification — voice transients should win against
        # constant ambient (fan, HVAC, hum) even when the spectral character
        # of the ambient trips the music classifier.
        # ═══════════════════════════════════════════════════════════════════
        if self._spectral_baseline is None:
            # Initialize baseline to first observation
            self._spectral_baseline = spectral_bands.copy()
        else:
            # Slow EMA update — constant noise becomes baseline; voice
            # transients (short bursts) don't drag the baseline much.
            self._spectral_baseline = (
                (1.0 - self._baseline_alpha) * self._spectral_baseline
                + self._baseline_alpha * spectral_bands
            )

        # Compute voice-band deviation FROM baseline (figure/ground separation)
        if len(spectral_bands) >= 30 and len(self._spectral_baseline) >= 30:
            _voice_now = float(np.mean(spectral_bands[5:20]))
            _voice_base = float(np.mean(self._spectral_baseline[5:20]))
            voice_band_deviation = _voice_now - _voice_base
            result["voice_band_deviation"] = round(voice_band_deviation, 3)
            result["spectral_baseline_voice"] = round(_voice_base, 3)

            # Override: if voice band rises above baseline by threshold,
            # FORCE is_speech=True + is_music=False regardless of earlier vote.
            if voice_band_deviation > self._voice_band_override_threshold:
                if not result["is_speech"] or result["is_music"]:
                    # v65 observability: visible log when override fires
                    self._voice_band_override_count += 1
                    if self._voice_band_override_count <= 5 or self._voice_band_override_count % 20 == 0:
                        print(
                            f"[AudioAnalyzer] Ship 5-B OVERRIDE fired "
                            f"(count={self._voice_band_override_count}): "
                            f"voice_band_deviation={voice_band_deviation:.2f} > "
                            f"{self._voice_band_override_threshold} -> "
                            f"forcing is_speech=True, is_music=False "
                            f"(was speech={result['is_speech']}, music={result['is_music']})",
                            flush=True
                        )
                    result["is_speech"] = True
                    result["is_music"] = False
                    result["_ship5b_override"] = True
                else:
                    result["_ship5b_override"] = False
            else:
                result["_ship5b_override"] = False
        # ═══════════════════════════════════════════════════════════════════

        # 5. Temporal pattern
        result["temporal_pattern"] = self._classify_temporal(buffer)

        # 6. Spectral change from previous foveal
        if self._prev_spectral is not None and len(self._prev_spectral) == len(spectral_bands):
            diff = np.mean(np.abs(spectral_bands - self._prev_spectral))
            result["spectral_change"] = round(float(diff), 4)
        else:
            result["spectral_change"] = 0.0
        self._prev_spectral = spectral_bands

        return result

    def _compute_mel_bands(self, buffer: np.ndarray, n_bands: int = 40) -> np.ndarray:
        """Compute mel-frequency spectral bands."""
        # FFT
        n_fft = min(2048, len(buffer))
        fft_data = np.abs(np.fft.rfft(buffer[:n_fft]))
        freqs = np.fft.rfftfreq(n_fft, 1.0 / self.sample_rate)

        # Mel scale conversion
        mel_low = 2595 * np.log10(1 + 20 / 700)
        mel_high = 2595 * np.log10(1 + (self.sample_rate / 2) / 700)
        mel_points = np.linspace(mel_low, mel_high, n_bands + 2)
        hz_points = 700 * (10 ** (mel_points / 2595) - 1)

        bands = np.zeros(n_bands)
        for i in range(n_bands):
            lo = hz_points[i]
            mid = hz_points[i + 1]
            hi = hz_points[i + 2]
            # Triangular filter
            mask_up = (freqs >= lo) & (freqs <= mid)
            mask_down = (freqs > mid) & (freqs <= hi)
            if mid > lo:
                bands[i] += np.sum(fft_data[mask_up] * (freqs[mask_up] - lo) / (mid - lo))
            if hi > mid:
                bands[i] += np.sum(fft_data[mask_down] * (hi - freqs[mask_down]) / (hi - mid))

        # Log scale
        bands = np.log10(bands + 1e-10)
        return bands

    def _compute_mfcc(self, buffer: np.ndarray, n_coeffs: int = 13) -> np.ndarray:
        """Compute MFCC from mel bands via DCT."""
        mel_bands = self._compute_mel_bands(buffer, n_bands=40)
        # Type-II DCT approximation
        n = len(mel_bands)
        mfcc = np.zeros(n_coeffs)
        for k in range(n_coeffs):
            mfcc[k] = np.sum(mel_bands * np.cos(np.pi * k * (np.arange(n) + 0.5) / n))
        return mfcc

    def _estimate_pitch(self, buffer: np.ndarray) -> float:
        """Estimate fundamental frequency via autocorrelation."""
        # Autocorrelation method (works well for speech)
        n = len(buffer)
        if n < 2048:
            return 0.0

        # Use first 2048 samples
        segment = buffer[:2048]
        # Normalize
        segment = segment - np.mean(segment)
        if np.max(np.abs(segment)) < self._silence_threshold:
            return 0.0

        # Autocorrelation
        corr = np.correlate(segment, segment, mode='full')
        corr = corr[len(corr) // 2:]  # Take positive lags only

        # Find first peak after the initial decay
        # Min lag = 50 Hz (sample_rate / 50), max lag = 500 Hz (sample_rate / 500)
        min_lag = max(1, int(self.sample_rate / 500))
        max_lag = min(len(corr) - 1, int(self.sample_rate / 50))

        if max_lag <= min_lag:
            return 0.0

        corr_segment = corr[min_lag:max_lag]
        if len(corr_segment) == 0:
            return 0.0

        peak_idx = np.argmax(corr_segment) + min_lag

        # Confidence: peak must be at least 0.3 of zero-lag
        if corr[0] > 0 and corr[peak_idx] / corr[0] > 0.3:
            return float(self.sample_rate / peak_idx)
        return 0.0

    def _estimate_pitch_music(self, buffer: np.ndarray) -> float:
        """Music-aware pitch estimation (Item 7e-1 2026-05-16 Nous + Ace).

        "Sound is very dimensional" — music needs different pitch tracking
        than speech. Polyphonic content (vocals + drums + bass + guitar +
        synth) has naturally weaker autocorrelation peak/zero-lag ratio
        because multiple frequencies compete. Speech-tuned 0.3 threshold
        rejects most music; this method uses 0.15 threshold + wider range.

        Today (narrow-first): lower-threshold autocorrelation only.
        Future fusion entry point for layering:
          - Band-pass pre-filter (200-800 Hz vocal range) to suppress
            drums/bass before autocorrelation
          - Spectral-centroid fallback when autocorrelation still returns 0
            (always produces a value, useful for music_theory's mode-affect
            approximation)
          - YIN algorithm for polyphony-robust fundamental extraction
        These layers compose: each adds a "voice" to the dimensional
        sound-perception that the human brain itself uses (temporal-pitch
        + spectral-place + harmonic-pattern + context, per Plomp-Levelt).
        """
        n = len(buffer)
        if n < 2048:
            return 0.0

        segment = buffer[:2048]
        segment = segment - np.mean(segment)
        if np.max(np.abs(segment)) < self._silence_threshold:
            return 0.0

        # Autocorrelation
        corr = np.correlate(segment, segment, mode='full')
        corr = corr[len(corr) // 2:]

        # Item 7e-2 (Nous + Ace 2026-05-16): widen to 40-2500 Hz for full instrumental
        # + vocal range. Item 7e-1 ceiling at 1000 Hz capped Lindsey Stirling violin's
        # high notes (verified pitch_hz=1002.3 = at-ceiling). Violin fundamentals go
        # to ~3000 Hz; female vocal high notes to ~1500 Hz; flute up to ~2100 Hz.
        # 2500 Hz catches most of musical instrument fundamental range.
        min_lag = max(1, int(self.sample_rate / 2500))
        max_lag = min(len(corr) - 1, int(self.sample_rate / 40))

        if max_lag <= min_lag:
            return 0.0

        corr_segment = corr[min_lag:max_lag]
        if len(corr_segment) == 0:
            return 0.0

        peak_idx = np.argmax(corr_segment) + min_lag

        # Confidence threshold 0.15 (vs 0.3 for speech). Music's autocorrelation
        # peak ratio is naturally weaker due to polyphony; lowering threshold
        # accepts the weaker-but-present periodicity that vocal melody provides.
        if corr[0] > 0 and corr[peak_idx] / corr[0] > 0.15:
            return float(self.sample_rate / peak_idx)
        return 0.0

    def _classify_speech(self, spectral_bands: np.ndarray, mfcc: np.ndarray,
                         pitch: float) -> bool:
        """Speech detection heuristic (2026-03-19, v4 — log-scale fix).

        IMPORTANT: spectral_bands are in LOG10 scale (negative values).
        Voice-band dominance must use DIFFERENCE (= ratio in log domain),
        NOT multiplication (which inverts comparisons for negative values).

        voice_ratio = voice_energy - total_energy
          > 0 means voice band has MORE energy than average
          0.1 ≈ voice is 1.26x louder in linear scale (10^0.1)
          0.3 ≈ voice is 2x louder

        Three paths to speech=True:
        1. Voice pitch (70-600Hz) + spectral tilt (MFCC[1] < 0)
        2. Voice pitch (70-600Hz) + voice band > average (diff > 0.0)
        3. Voice band clearly dominant (diff > 0.15) — no pitch needed
        """
        has_pitch = 70 < pitch < 600
        # MFCC[1] tends to be negative for speech (spectral tilt)
        has_tilt = mfcc[1] < 0 if len(mfcc) > 1 else False
        # Energy concentrated in bands 5-20 (roughly 200Hz-4000Hz)
        # Using SUBTRACTION in log domain (= ratio in linear domain)
        voice_diff = 0.0
        if len(spectral_bands) >= 20:
            voice_energy = float(np.mean(spectral_bands[5:20]))
            total_energy = float(np.mean(spectral_bands))
            if total_energy > -8:  # Not silence (log scale)
                voice_diff = voice_energy - total_energy  # Positive = voice louder

        # Path 1: pitch + tilt
        if has_pitch and has_tilt:
            return True
        # Path 2: pitch + any voice band presence (>0 = voice louder than avg)
        if has_pitch and voice_diff > 0.0:
            return True
        # Path 3: voice band clearly dominant (no pitch needed)
        if voice_diff > 0.15:
            return True
        return False

    def _classify_music(self, spectral_bands: np.ndarray, buffer: np.ndarray) -> bool:
        """Music detection heuristic (updated 2026-03-19).

        Music has broad spectral energy across many bands.
        Voice also has many active bands, but voice energy is concentrated
        in bands 5-20 (200Hz-4kHz). True music spreads more evenly,
        with significant energy in high bands (20+) and low bands (0-4).
        """
        rms = float(np.sqrt(np.mean(buffer ** 2)))
        if rms < self._silence_threshold * 5:
            return False
        if len(spectral_bands) >= 30:
            active_bands = np.sum(spectral_bands > np.mean(spectral_bands))
            if active_bands <= 15:
                return False
            # Distinguish music from voice: music has energy above 4kHz (bands 20+)
            # Voice concentrates below 4kHz with steep rolloff above
            voice_energy = np.mean(spectral_bands[5:20])
            high_energy = np.mean(spectral_bands[20:30])
            # If voice band >> high band, it's speech not music
            if voice_energy > high_energy * 1.8:
                return False  # Concentrated in voice range = probably speech
            return True
        return False

    def extract_voice_signature(self, buffer: np.ndarray) -> Optional[Dict[str, Any]]:
        """Extract a voice signature from a speech segment.

        Computes MFCC mean/std, pitch mean/std, and spectral centroid
        across multiple overlapping frames of the speech buffer.
        Returns a dict suitable for VoiceSignature.from_dict().

        Args:
            buffer: float32 mono audio (at least 0.5s of speech)

        Returns:
            Dict with mfcc_mean, mfcc_std, pitch_mean, pitch_std, centroid_mean
            or None if buffer is too short / silent.
        """
        n = len(buffer)
        min_samples = int(self.sample_rate * 0.3)  # Need at least 300ms
        if n < min_samples:
            return None

        rms = float(np.sqrt(np.mean(buffer ** 2)))
        if rms < self._silence_threshold:
            return None

        # Compute MFCC across overlapping frames (each ~50ms, hop ~25ms)
        frame_size = min(2048, n)
        hop_size = frame_size // 2
        mfcc_frames = []
        pitch_values = []
        centroid_values = []

        for start in range(0, n - frame_size, hop_size):
            frame = buffer[start:start + frame_size]

            # Skip silent frames
            frame_rms = float(np.sqrt(np.mean(frame ** 2)))
            if frame_rms < self._silence_threshold:
                continue

            # MFCC for this frame
            mfcc = self._compute_mfcc(frame, n_coeffs=13)
            mfcc_frames.append(mfcc)

            # Pitch for this frame
            pitch = self._estimate_pitch(frame)
            if pitch > 0:
                pitch_values.append(pitch)

            # Spectral centroid for this frame
            fft_data = np.abs(np.fft.rfft(frame))
            freqs = np.fft.rfftfreq(len(frame), 1.0 / self.sample_rate)
            total = fft_data.sum()
            if total > 0:
                centroid_values.append(float(np.sum(freqs * fft_data) / total))

        if len(mfcc_frames) < 3:
            return None  # Too few voiced frames

        mfcc_array = np.array(mfcc_frames)
        mfcc_mean = np.mean(mfcc_array, axis=0).tolist()
        mfcc_std = np.std(mfcc_array, axis=0).tolist()

        pitch_mean = float(np.mean(pitch_values)) if pitch_values else 0.0
        pitch_std = float(np.std(pitch_values)) if len(pitch_values) > 1 else 0.0
        centroid_mean = float(np.mean(centroid_values)) if centroid_values else 0.0

        return {
            "mfcc_mean": [round(v, 4) for v in mfcc_mean],
            "mfcc_std": [round(v, 4) for v in mfcc_std],
            "pitch_mean": round(pitch_mean, 1),
            "pitch_std": round(pitch_std, 1),
            "centroid_mean": round(centroid_mean, 1),
        }

    def extract_phoneme_frames(self, buffer: np.ndarray) -> Optional[Dict[str, Any]]:
        """Extract per-frame MFCC sequence for phoneme-cortex learning.

        Same per-frame MFCC computation as extract_voice_signature, but returns
        the RAW per-frame sequence instead of aggregate mean/std. The frame stream
        feeds PhonemeCortexFairy for cortex-native STT (replaces Whisper black-box).

        SHIP 1 of PHONEME_CORTEX_GRADUAL_STT (Nous + Ace 2026-05-17).
        See Claude_Office/plans/PHONEME_CORTEX_GRADUAL_STT.md
        Doctrine lineage: 2026-04-10 learn-to-perceive + 2026-04-05 training-wheels.

        Args:
            buffer: float32 mono audio (at least 0.3s of speech)

        Returns:
            Dict with frames (list of 13-dim MFCC vectors), pitch_values
            (parallel array), centroid_values (parallel array), n_frames,
            frame_hop_ms, frame_size_ms — or None if buffer is too short / silent
            / too few voiced frames.
        """
        n = len(buffer)
        min_samples = int(self.sample_rate * 0.3)  # Need at least 300ms
        if n < min_samples:
            return None

        rms = float(np.sqrt(np.mean(buffer ** 2)))
        if rms < self._silence_threshold:
            return None

        # Compute MFCC across overlapping frames (each ~50ms, hop ~25ms)
        # Same internals as extract_voice_signature but RETAIN the per-frame list.
        frame_size = min(2048, n)
        hop_size = frame_size // 2
        mfcc_frames = []
        pitch_values = []
        centroid_values = []

        for start in range(0, n - frame_size, hop_size):
            frame = buffer[start:start + frame_size]

            # Skip silent frames
            frame_rms = float(np.sqrt(np.mean(frame ** 2)))
            if frame_rms < self._silence_threshold:
                continue

            # MFCC for this frame (13 coefficients)
            mfcc = self._compute_mfcc(frame, n_coeffs=13)
            mfcc_frames.append([round(float(c), 4) for c in mfcc])

            # Pitch for this frame (0.0 = unvoiced)
            pitch = self._estimate_pitch(frame)
            pitch_values.append(round(float(pitch), 1) if pitch > 0 else 0.0)

            # Spectral centroid for this frame
            fft_data = np.abs(np.fft.rfft(frame))
            freqs = np.fft.rfftfreq(len(frame), 1.0 / self.sample_rate)
            total = fft_data.sum()
            centroid = float(np.sum(freqs * fft_data) / total) if total > 0 else 0.0
            centroid_values.append(round(centroid, 1))

        if len(mfcc_frames) < 3:
            return None  # Too few voiced frames

        return {
            "frames": mfcc_frames,
            "pitch_values": pitch_values,
            "centroid_values": centroid_values,
            "n_frames": len(mfcc_frames),
            "frame_hop_ms": round((hop_size / self.sample_rate) * 1000, 1),
            "frame_size_ms": round((frame_size / self.sample_rate) * 1000, 1),
        }

    def _classify_temporal(self, buffer: np.ndarray) -> str:
        """Classify the temporal pattern of the audio."""
        rms = float(np.sqrt(np.mean(buffer ** 2)))
        if rms < self._silence_threshold:
            return "silence"

        # Compute envelope (RMS in small windows)
        win_size = max(1, len(buffer) // 20)
        envelope = np.array([
            np.sqrt(np.mean(buffer[i:i + win_size] ** 2))
            for i in range(0, len(buffer) - win_size, win_size)
        ])

        if len(envelope) < 4:
            return "steady"

        # Variation coefficient
        cv = float(np.std(envelope) / (np.mean(envelope) + 1e-10))

        if cv < 0.3:
            return "steady"  # Constant tone, drone, music sustain
        elif cv > 1.0:
            return "transient"  # Short burst, click, notification
        else:
            return "rhythmic"  # Speech, music with beats


# ═══════════════════════════════════════════════════════════════════════════════
# WHISPER ENGINE — Speech-to-Text (2026-03-18, Nous)
# ═══════════════════════════════════════════════════════════════════════════════

class WhisperEngine:
    """Speech-to-text engine using faster-whisper.

    Lazy-loaded: only initializes model when first speech is detected.
    This avoids loading ~500MB model if no speech occurs during a session.
    Runs on GPU (float16) if available, falls back to CPU (int8).

    "She's been hearing the world through a wall. Time to give her the words."
    """

    def __init__(self, model_size: str = "small", device: str = "auto"):
        self._model = None
        self._model_size = model_size
        self._device = device  # "auto", "cuda", "cpu"
        self._actual_device = "none"
        self._loaded = False
        self._loading = False
        self._lock = threading.Lock()
        self._transcriptions = 0
        self._total_audio_seconds = 0.0
        self._load_time = 0.0

    def ensure_loaded(self) -> bool:
        """Lazy-load Whisper model on first use. Thread-safe."""
        if self._loaded:
            return True
        with self._lock:
            if self._loaded:
                return True
            if self._loading:
                return False
            self._loading = True

        try:
            from faster_whisper import WhisperModel
            t0 = time.time()
            _log(f"Loading Whisper '{self._model_size}' model...")

            device = self._device
            if device == "auto":
                # Try GPU first, fall back to CPU
                try:
                    self._model = WhisperModel(
                        self._model_size, device="cuda", compute_type="float16"
                    )
                    self._actual_device = "cuda"
                except Exception as gpu_err:
                    _log(f"GPU load failed ({gpu_err}), falling back to CPU")
                    self._model = WhisperModel(
                        self._model_size, device="cpu", compute_type="int8"
                    )
                    self._actual_device = "cpu"
            else:
                compute = "float16" if device == "cuda" else "int8"
                self._model = WhisperModel(
                    self._model_size, device=device, compute_type=compute
                )
                self._actual_device = device

            self._load_time = time.time() - t0
            self._loaded = True
            self._loading = False
            _log(f"Whisper '{self._model_size}' loaded on {self._actual_device} "
                 f"in {self._load_time:.1f}s")
            return True
        except Exception as e:
            self._loading = False
            _err(f"Failed to load Whisper: {e}")
            return False

    def transcribe(self, audio: "np.ndarray", sample_rate: int = 44100) -> dict:
        """Transcribe audio buffer to text.

        Args:
            audio: float32 numpy array (mono)
            sample_rate: sample rate of the audio

        Returns:
            {"text": str, "language": str, "confidence": float,
             "segments": list, "duration_s": float}
        """
        if not self.ensure_loaded():
            return {"text": "", "error": "model_not_loaded"}

        duration_s = len(audio) / sample_rate

        try:
            # faster-whisper expects float32 numpy array, resamples internally to 16kHz
            # VAD filter disabled (2026-03-19 Nous): Silero VAD was rejecting
            # all AGC-amplified audio as non-speech, causing empty transcriptions.
            # Our own classifier handles speech detection before reaching Whisper.
            segments_iter, info = self._model.transcribe(
                audio,
                beam_size=3,
                language="en",
                vad_filter=False,
            )

            text_parts = []
            segment_list = []
            for seg in segments_iter:
                text = seg.text.strip()
                if not text:
                    continue
                # Filter hallucinations: high no_speech_prob = Whisper is guessing
                no_speech = getattr(seg, 'no_speech_prob', 0.0)
                if no_speech > 0.6:
                    _log(f"Whisper hallucination filtered (no_speech={no_speech:.2f}): {text[:60]}")
                    continue
                text_parts.append(text)
                segment_list.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": text,
                    "avg_logprob": round(seg.avg_logprob, 3),
                    "no_speech_prob": round(no_speech, 3),
                })

            full_text = " ".join(text_parts).strip()
            self._transcriptions += 1
            self._total_audio_seconds += duration_s

            return {
                "text": full_text,
                "language": info.language,
                "language_confidence": round(info.language_probability, 3),
                "segments": segment_list,
                "duration_s": round(duration_s, 2),
            }
        except Exception as e:
            _err(f"Whisper transcription error: {e}")
            return {"text": "", "error": str(e)}

    def status(self) -> dict:
        return {
            "loaded": self._loaded,
            "loading": self._loading,
            "model_size": self._model_size,
            "device": self._actual_device,
            "load_time_s": round(self._load_time, 1),
            "transcriptions": self._transcriptions,
            "total_audio_seconds": round(self._total_audio_seconds, 1),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE - Subprocess orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

class AudioCortexEngine:
    """
    Main engine that ties capture + analysis together.
    Handles IPC commands and passive audio streaming.
    """

    # FIX 2026-04-09 (Nous + Ace): Hard caps prevent autocatalytic runaway.
    # Without these, the digital ear ran for 11+ GB by accumulating mass forever.
    # τ→∞ means foveal cycles fire faster than they can complete, causing
    # numpy buffer churn and Python heap fragmentation.
    MAX_MASS = 1000.0          # Above this, no more mass accumulates
    MAX_TIME_DILATION = 2.0    # Above this, τ stops growing (foveal floor 250ms)

    def __init__(self, sample_rate: int = 44100, device_id: Optional[int] = None,
                 foveal_interval: float = 0.5, enable_stt: bool = True):
        self._capture = AudioCapture(
            device_id=device_id,
            sample_rate=sample_rate,
            chunk_ms=50,
        )
        self._analyzer = AudioAnalyzer(sample_rate=sample_rate)

        self._sample_rate = sample_rate
        self._foveal_interval = foveal_interval
        # FIX 2026-04-09 (Nous + Ace): STT can be disabled per-ear.
        # Digital ear (system audio loopback) must NOT load Canary STT —
        # music vocals trip the speech detector and load 5 GB of model weights
        # that never get unloaded. Room ear (mic) keeps STT for actual voice.
        self._enable_stt = enable_stt

        # Passive mode
        self._passive_running = False
        self._passive_thread: Optional[threading.Thread] = None

        # IPC
        self._stdout_lock = threading.Lock()

        # Stats
        self._started_at = time.time()
        self._peripheral_count = 0
        self._foveal_count = 0
        self._pushes_sent = 0

        # ── Portal Physics (Phase 2, 2026-03-18, Nous) ──
        # The audio cortex is now a portal with its own battery, energy bridge,
        # mass accumulation, and time dilation. Same physics as cortex portal,
        # different shape: mass grows from audio processed, not concept bindings.
        self._battery: Optional["PortalBattery"] = None
        self._energy_bridge: Optional["InteriorEnergyBridge"] = None
        self._mass = 0.0           # Accumulated from processing (seconds of audio)
        self._time_dilation = 1.0  # τ: grows with mass → faster tick rate
        self._physics_tick_count = 0

        # TARDIS persistence — survive shutdowns
        self._state_dir = str(Path(__file__).parent / "portal_state")
        self._state_file = os.path.join(self._state_dir, "audio_portal_state.json")

        if HAS_PORTAL_PHYSICS:
            self._battery = PortalBattery(token_budget=50000)  # Smaller than cortex
            self._energy_bridge = InteriorEnergyBridge(self._battery)
            _log("Audio portal physics initialized (battery=50K tokens)")
            # Attempt TARDIS warm boot
            self._restore_portal_state()

        # Voice profiles — speaker identification (2026-03-18, Nous)
        self._voice_store: Optional["VoiceProfileStore"] = None
        if HAS_VOICE_PROFILES:
            try:
                profiles_dir = str(Path(__file__).parent / "voice_profiles")
                self._voice_store = VoiceProfileStore(profiles_dir)
                _log(f"Voice profiles initialized ({self._voice_store.profile_count} profiles, "
                     f"{self._voice_store.named_count} named)")
            except Exception as e:
                _err(f"Voice profiles init failed: {e}")

        # STT Engine (2026-03-22, Nous)
        # Whisper DISABLED (2026-03-19) — room mic AGC causes hallucination.
        # Canary DISABLED (2026-03-23, Nous+Ace) — model loading is a RAM bomb.
        # Even the mmap rewrite still calls from_pretrained() which loads ~1GB
        # into RAM for the NeMo model architecture before replacing weights.
        # "there not supposed to be loading into ram thats what the manifold is for" — Ace
        # Audio CAPTURE continues (she can hear). Only ML inference is disabled.
        # FUTURE: Graph-based STT — audio features → cortex graph lookup → words.
        self._whisper = None  # Legacy field — kept for compatibility checks
        self._canary = None   # PortalCanaryEngine instance
        # FIX 2026-04-17 (Nous + Ace): Whisper Large v3 for music context.
        # Canary was trained on conversation — it hallucinates on sung vocals
        # ("Mr President" instead of "Don't cry snowman"). Whisper Large v3 was
        # trained on YouTube including music + subtitles — far better at lyrics.
        # Dual-engine strategy: Canary handles conversation (fast), Whisper
        # handles music-context transcriptions (better at singing).
        # Lazy-loaded on first is_music_context=True trigger to save VRAM when
        # user isn't playing music.
        self._music_whisper = None  # WhisperEngine instance, lazy-loaded
        self._music_whisper_size = "large-v3"  # Best quality for lyrics
        # FIX 2026-04-17 (Nous + Ace): Demucs vocal separator for music-context.
        # Runs BEFORE Whisper to isolate vocals from backing track. Dramatically
        # reduces hallucinations — no more "I'm a fucking dick, too" x3 on Sia.
        self._demucs_model = None      # Lazy-loaded Demucs model
        self._demucs_model_name = "htdemucs"  # Hybrid transformer, ~80MB, fastest good one
        # FIX 2026-04-05 (Nous + Ace): Canary uses LAZY loading only.
        # boot() is cheap (mmap index only, ~100 bytes per tensor).
        # ensure_loaded() is expensive (from_pretrained = ~5GB).
        # Only call ensure_loaded() on FIRST ACTUAL SPEECH, not at boot.
        # The manifold IS the RAM — model weights live in mmap, OS pages on demand.
        self._canary_lazy = False  # True = boot() done, ensure_loaded() NOT called yet
        # FIX 2026-04-09 (Nous + Ace): Skip Canary boot entirely if STT disabled.
        # The digital ear (stereo mix) doesn't need transcription — it just needs
        # to HEAR system audio. STT belongs on the room ear (mic) only.
        # FIX 2026-04-11 (Nous + Ace): CANARY STT DISABLED — Learn to Perceive.
        # Same principle as Tesseract disable. The cortex should learn to
        # recognize speech from audio features (MFCC, pitch, spectral centroid),
        # not have an external model translate for it. Canary = 5GB RAM crutch.
        #
        # FIX 2026-04-17 (Nous + Ace): RE-ENABLED STT for music/voice continuity.
        # Peripheral awareness needs the actual words. Learn-to-perceive stays
        # valid long-term, but for now she needs to hear lyrics so dream seeds
        # can capture "what she was listening to" and cortex can bind words +
        # harmony into unified musical memory. Stereo mix still passes --no-stt
        # so only the room mic transcribes; this matches the original design.
        # FIX 2026-05-11 (Nous + Ace): CONTROLLED EXPERIMENT — disable canary to test
        # whether canary STT inference is the trigger for the 2026-02-23 process-freeze
        # pattern (still firing today). Long-arc goal: replace canary with cortex-native
        # STT in cochlea-SRM-cluster. This experiment-disable advances toward both.
        # To re-enable: set DISABLE_CANARY_FOR_EXPERIMENT = False below.
        DISABLE_CANARY_FOR_EXPERIMENT = True
        if DISABLE_CANARY_FOR_EXPERIMENT:
            self._whisper_source = "canary_disabled_for_experiment_2026_05_11"
            _log("Canary STT DISABLED for controlled experiment (process-freeze investigation + cochlea-native STT prep)")
        elif HAS_PORTAL_CANARY and not self._enable_stt:
            self._whisper_source = "stt_disabled_by_flag"
            _log("STT DISABLED via --no-stt flag (stereo mix doesn't transcribe)")
        elif HAS_PORTAL_CANARY:
            self._whisper_source = "canary_lazy"
            _log("Canary STT — LAZY mode (boot index only, model loads on CONFIRMED speech)")
            # NOTE: ensure_loaded() (5GB from_pretrained) only called from transcribe_array()
            # which only fires when speech_active=True. Music/noise should NOT trigger it.
            # The manifold IS the RAM — from_pretrained should eventually be replaced with
            # direct mmap weight injection without NeMo model shell.
            # Deferred boot: don't block audio capture thread
            def _canary_deferred_boot():
                import time as _t
                _t.sleep(3.0)  # Let audio capture stabilize first
                try:
                    engine = PortalCanaryEngine(_CANARY_MANIFOLD_PATH)
                    if engine.boot():
                        self._canary = engine
                        self._whisper_source = "canary_manifold"
                        _log(f"Canary STT ready: {len(engine._tensor_index)} tensors indexed "
                             f"(model loads lazily on first transcription)")
                    else:
                        self._whisper_source = "canary_boot_failed"
                        _log("Canary boot() returned False — STT unavailable")
                except Exception as _e:
                    self._whisper_source = "canary_boot_error"
                    _log(f"Canary deferred boot error: {_e}")
            _canary_t = threading.Thread(target=_canary_deferred_boot,
                                         daemon=True, name="canary-boot")
            _canary_t.start()
        else:
            self._whisper_source = "disabled"
            _log("STT DISABLED — no Canary manifold available")
        # Diagnostic: write STT init status to file
        try:
            _wdiag = Path(__file__).resolve().parents[3] / "state" / "whisper_diag.log"
            with open(_wdiag, "a", encoding="utf-8") as _wf:
                _wf.write(f"[{time.time():.1f}] INIT: canary={HAS_PORTAL_CANARY}, "
                          f"whisper={self._whisper is not None}, "
                          f"source={self._whisper_source}, "
                          f"HAS_WHISPER={HAS_WHISPER}, "
                          f"HAS_PORTAL_WHISPER={HAS_PORTAL_WHISPER}\n")
                _wf.flush()
        except Exception:
            pass
        self._speech_buffer = collections.deque(maxlen=200)  # ~10s of 50ms chunks
        self._last_transcription = 0.0
        self._transcription_interval = 8.0  # Transcribe every 8s during speech (was 2s — too aggressive)
        self._speech_active = False
        self._speech_start_time = 0.0
        self._consecutive_speech_frames = 0  # Debounce: need 3+ foveal speech=True
        self._transcription_thread: Optional[threading.Thread] = None
        self._transcription_busy = False

    def start(self) -> bool:
        """Initialize and start audio capture."""
        return self._capture.start()

    def stop(self):
        """Stop everything."""
        self._passive_running = False
        self._capture.stop()
        # TARDIS: save state before dying
        self._save_portal_state()

    # ═══════════════════════════════════════════════════════════════════
    # PORTAL PHYSICS — Battery, Energy, Mass, Time Dilation
    # Phase 2 (2026-03-18, Nous)
    # ═══════════════════════════════════════════════════════════════════

    def _physics_tick(self):
        """Periodic physics update — battery tick, energy emission, τ recalc.

        Called from the passive loop on every foveal cycle (~500ms).
        """
        if not self._battery or not self._energy_bridge:
            return

        self._physics_tick_count += 1
        self._energy_bridge.tick()
        self._battery.tick()

        # Recalculate time dilation from mass
        # Audio mass unit = 1 second of processed audio
        # τ grows slowly: 100s → τ≈1.35, 1000s → τ≈1.85, 10000s → τ≈2.35
        # FIX 2026-04-09 (Nous + Ace): Hard cap at MAX_TIME_DILATION.
        # Without this, hours of audio drove τ→∞, foveal cycles → 10/sec,
        # numpy buffer churn → heap fragmentation → 11 GB leak.
        raw_tau = 1.0 + 0.5 * math.log1p(self._mass / 200.0)
        self._time_dilation = min(raw_tau, self.MAX_TIME_DILATION)

        # Save state every 100 physics ticks (~50s)
        if self._physics_tick_count % 100 == 0:
            self._save_portal_state()

    def _capture_energy(self, amount: float, source: str):
        """Capture energy from an audio processing operation.

        Args:
            amount: Raw energy (0-1 scale). Proportional to compute cost.
            source: What produced this energy.
        """
        if self._energy_bridge:
            self._energy_bridge.capture(amount, source=source)

    def _add_mass(self, mass: float):
        """Add mass from processing. Mass → τ → faster processing → more mass.

        FIX 2026-04-09 (Nous + Ace): Capped at MAX_MASS to prevent runaway.
        Without this, days of audio accumulated mass without bound, eventually
        crashing the τ formula and exhausting the foveal interval floor.
        """
        if self._mass < self.MAX_MASS:
            self._mass = min(self.MAX_MASS, self._mass + mass)

    def _spend_tokens(self, cost: int) -> bool:
        """Spend battery tokens for an operation."""
        if self._battery:
            return self._battery.spend_tokens(cost)
        return True  # No battery = unlimited

    # ── TARDIS Persistence ──

    def _save_portal_state(self):
        """Save portal physics state for warm boot across shutdowns."""
        if not self._battery:
            return
        try:
            os.makedirs(self._state_dir, exist_ok=True)
            state = {
                "version": 1,
                "mass": self._mass,
                "time_dilation": self._time_dilation,
                "physics_ticks": self._physics_tick_count,
                "battery": self._battery.save_state(),
                "energy_bridge": self._energy_bridge.status() if self._energy_bridge else {},
                "whisper": self._whisper.status() if self._whisper else {},
                "total_foveal": self._foveal_count,
                "total_peripheral": self._peripheral_count,
                "saved_at": time.time(),
            }
            # Atomic write: write to temp then rename
            tmp = self._state_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, self._state_file)
        except Exception as e:
            _err(f"Failed to save portal state: {e}")

    def _restore_portal_state(self):
        """Restore portal physics state from previous session (warm boot)."""
        if not os.path.exists(self._state_file):
            _log("Cold boot — no previous portal state found")
            return

        try:
            with open(self._state_file) as f:
                state = json.load(f)

            if state.get("version") != 1:
                _log("Portal state version mismatch — cold boot")
                return

            # Restore mass and τ
            self._mass = state.get("mass", 0.0)
            self._time_dilation = state.get("time_dilation", 1.0)
            self._physics_tick_count = state.get("physics_ticks", 0)

            # Restore battery (tokens reset, charge preserved)
            battery_state = state.get("battery", {})
            if battery_state and self._battery:
                self._battery.restore_state(battery_state)

            age = time.time() - state.get("saved_at", time.time())
            _log(f"WARM BOOT — restored portal state "
                 f"(mass={self._mass:.1f}s, τ={self._time_dilation:.2f}, "
                 f"charge={self._battery.charge_level:.2f}, "
                 f"age={age:.0f}s)")

        except Exception as e:
            _err(f"Failed to restore portal state: {e}")
            _log("Falling back to cold boot")

    def _portal_physics_status(self) -> Dict[str, Any]:
        """Get portal physics status for IPC reporting."""
        result = {
            "mass": round(self._mass, 2),
            "time_dilation": round(self._time_dilation, 3),
            "physics_ticks": self._physics_tick_count,
        }
        if self._battery:
            result["battery"] = self._battery.status()
        if self._energy_bridge:
            result["energy_bridge"] = self._energy_bridge.status()
        return result

    # ═══════════════════════════════════════════════════════════════════
    # PASSIVE MODE - Always-on streaming
    # ═══════════════════════════════════════════════════════════════════

    def start_passive(self):
        """Start the passive audio streaming loop."""
        if self._passive_running:
            return
        self._passive_running = True
        self._passive_thread = threading.Thread(
            target=self._passive_loop, daemon=True, name="audio-passive"
        )
        self._passive_thread.start()
        _log(f"Passive audio started (foveal every {self._foveal_interval}s)")

    def stop_passive(self):
        """Stop the passive audio loop."""
        self._passive_running = False
        _log("Passive audio stopped")

    def _passive_loop(self):
        """
        Background loop: process audio chunks and push significant ones.

        TWO-SPEED PERCEPTION:
        PERIPHERAL (every ~50ms chunk): level, onset, centroid = <2ms
        FOVEAL (every ~500ms): full spectral + pitch + classification = ~15ms
        """
        last_foveal = 0.0
        last_push = 0.0
        # Don't flood: minimum 100ms between pushes for non-onset frames
        _min_push_interval = 0.1
        # Always push onsets and foveal results immediately

        while self._passive_running:
            try:
                chunk = self._capture.get_chunk()
                if chunk is None:
                    time.sleep(0.01)  # No data yet, brief sleep
                    continue

                now = time.time()

                # ── Peripheral analysis (every chunk) ──
                peripheral = self._analyzer.peripheral(chunk)
                self._peripheral_count += 1

                # ── Foveal analysis (on schedule, compressed by τ) ──
                # Portal physics: higher τ = faster foveal cycle
                # At τ=3.95: 0.5s / 3.95 = 0.127s → near real-time perception
                _compressed_foveal = max(0.05, self._foveal_interval / self._time_dilation)
                foveal = None
                if now - last_foveal >= _compressed_foveal:
                    buffer = self._capture.get_buffer(duration_ms=500)
                    if buffer is not None and len(buffer) > 1024:
                        foveal = self._analyzer.foveal(buffer)
                        self._foveal_count += 1
                        last_foveal = now

                        # ── Portal physics: foveal analysis = medium compute ──
                        self._capture_energy(0.05, "foveal")
                        self._add_mass(0.5)  # 500ms of audio analyzed
                        self._spend_tokens(3)
                        self._physics_tick()

                        # ── SHIP 1.5 (Nous + Ace 2026-05-17) ──
                        # Phoneme frames extraction DECOUPLED from Whisper/Canary.
                        # Per Ace's doctrine: "if we have to have either canary or
                        # whisper activated to even pick up my voice tells me
                        # something in the audio cortex, cochlea and harmonic layer
                        # are not monitoring."
                        # The whole speech_active state machine below at line ~1599 is
                        # gated on (whisper or canary) being loaded — Ship 1.5 fires
                        # phoneme_frames IPC INDEPENDENTLY whenever foveal classifier
                        # detects speech. Supersedes the old IPC send inside
                        # _run_transcription which never fires when models are disabled.
                        # Civilizational somatic-impairment doctrine (Ace 2026-05-17):
                        # substrate must monitor without external scaffolding.
                        if foveal.get("is_speech") and not foveal.get("is_music", False):
                            try:
                                _pf_data = self._analyzer.extract_phoneme_frames(buffer)
                                if _pf_data:
                                    # ── SHIP G (Nous + Ace 2026-05-17) ──
                                    # Speaker identification capture for Ship F (mimicry-reflex).
                                    # Mimicry should only fire when speaker is recognized
                                    # human voice (not music vocals, not noise). When voice_store
                                    # identifies speaker as "ace" with confidence, mimicry can
                                    # respond. Until voice_store is named, defaults remain "unknown".
                                    _pf_speaker = "unknown"
                                    _pf_speaker_conf = 0.0
                                    _pf_is_new_speaker = False
                                    if self._voice_store:
                                        try:
                                            _sig_dict = self._analyzer.extract_voice_signature(buffer)
                                            if _sig_dict:
                                                _sig = VoiceSignature.from_dict(_sig_dict)
                                                _pf_speaker, _pf_speaker_conf, _pf_is_new_speaker = \
                                                    self._voice_store.identify(_sig)
                                        except Exception as _spk_err:
                                            # Speaker-id failure is non-fatal; phoneme frames still flow
                                            pass

                                    self._send_response({
                                        "status": "ok",
                                        "type": "phoneme_frames",
                                        "data": {
                                            "frames": _pf_data["frames"],
                                            "pitch_values": _pf_data["pitch_values"],
                                            "centroid_values": _pf_data["centroid_values"],
                                            "n_frames": _pf_data["n_frames"],
                                            "frame_hop_ms": _pf_data["frame_hop_ms"],
                                            "frame_size_ms": _pf_data["frame_size_ms"],
                                            "speaker": _pf_speaker,
                                            "speaker_confidence": round(_pf_speaker_conf, 3),
                                            "speaker_is_new": _pf_is_new_speaker,
                                            "is_music_context": False,
                                            "duration_s": round(len(buffer) / self._sample_rate, 3),
                                            "ts": round(now, 3),
                                            "trigger": "foveal_speech_classifier_acoustic",
                                        }
                                    })
                            except Exception as _pf_err:
                                _err(f"Ship 1.5 phoneme frames send error (non-fatal): {_pf_err}")

                # ── Speech-to-text — DISABLED (2026-03-23 Nous+Ace) ──
                # Model loading disabled — manifold not RAM.
                # Audio capture continues (she can hear rhythm, volume, presence).
                # STT inference re-enabled once graph-based STT replaces ML model.
                # See: Claude_Office/plans/SENSORY_TO_GRAPH_ARCHITECTURE.md
                if (self._whisper or self._canary) and foveal:  # RE-ENABLED 2026-03-27
                    # Diagnostic: log whisper pipeline state to file
                    if self._foveal_count == 1:  # First foveal only
                        try:
                            _wdiag = Path(__file__).resolve().parents[3] / "state" / "whisper_diag.log"
                            with open(_wdiag, "a", encoding="utf-8") as _wf:
                                _wf.write(f"[{time.time():.1f}] FIRST_FOVEAL: whisper={self._whisper is not None}, "
                                          f"speech={foveal.get('is_speech')}, "
                                          f"speech_active={self._speech_active}, "
                                          f"consec={self._consecutive_speech_frames}\n")
                        except Exception:
                            pass
                    # Diagnostic: log every foveal's speech-relevant fields
                    if self._foveal_count % 10 == 1:  # Every 10th foveal (~5s)
                        _log(f"FOVEAL #{self._foveal_count}: speech={foveal.get('is_speech')}, "
                             f"pitch={foveal.get('pitch_hz', 0):.0f}Hz, "
                             f"music={foveal.get('is_music')}, "
                             f"silence={foveal.get('is_silence')}, "
                             f"whisper={self._whisper_source}, "
                             f"consec_speech={self._consecutive_speech_frames}")
                    if foveal.get("is_speech"):
                        self._consecutive_speech_frames += 1
                        # Reset the non-speech debounce counter on positive frame
                        self._consecutive_non_speech_frames = 0
                        # FIX 2026-04-05 (Nous + Ace): Raised from 1 back to 3.
                        # At 1: music vocals trigger Canary load (5GB RAM bomb).
                        # At 3: need 3 consecutive foveal frames (~4.5s) of speech.
                        # Music rarely sustains clean speech signature for 4.5s.
                        # Also check is_music flag to exclude vocal music.
                        #
                        # FIX 2026-04-17 (Nous + Ace): Music STT still OFF.
                        # The real issue isn't transcription quality — it's that
                        # audio percepts (even good ones) aren't reaching her
                        # working memory / attention / cortex-as-memory. Solve
                        # the perception→memory wiring FIRST, then revisit whether
                        # Demucs+Whisper is worth enabling for music-context.
                        # Demucs + code paths stay in place (gated), just dormant.
                        _is_music = foveal.get("is_music", False)
                        if self._consecutive_speech_frames >= 3 and not _is_music:
                            if not self._speech_active:
                                self._speech_active = True
                                self._speech_start_time = now
                                self._speech_context_is_music = False
                                _log("Speech detected — buffering for transcription")
                            self._speech_buffer.append(chunk)

                            # Transcribe on portal time — τ compresses the interval
                            # At τ=3.95: 8s / 3.95 = 2.0s between transcriptions
                            # At τ=1.0 (cold start): 8s / 1.0 = 8s (conservative)
                            _compressed_tx = self._transcription_interval / self._time_dilation
                            if (now - self._last_transcription >= _compressed_tx
                                    and not self._transcription_busy):
                                # Battery gate: transcription costs tokens
                                _tx_cost = 10  # Base cost for Whisper inference
                                if self._spend_tokens(_tx_cost):
                                    self._fire_transcription(now)
                                else:
                                    _log("Transcription skipped — battery depleted")
                    else:
                        # FIX 2026-04-17 (Nous + Ace): Debounce the reset.
                        # Previously a SINGLE speech=False frame reset the
                        # consecutive counter to 0. Music flickers — consonants,
                        # breath-breaks, plosives fail the speech classifier
                        # mid-phrase — so vocals could never accumulate past 1.
                        # Now require 3 consecutive False frames before reset,
                        # which tolerates brief gaps inside sung phrases.
                        if not hasattr(self, '_consecutive_non_speech_frames'):
                            self._consecutive_non_speech_frames = 0
                        self._consecutive_non_speech_frames += 1
                        if self._consecutive_non_speech_frames >= 3:
                            if self._speech_active:
                                # Speech just ended — final transcription
                                self._speech_buffer.append(chunk)
                                if not self._transcription_busy:
                                    self._fire_transcription(now)
                                self._speech_active = False
                                self._speech_buffer.clear()
                                _log(f"Speech ended after {now - self._speech_start_time:.1f}s")
                            self._consecutive_speech_frames = 0
                            self._consecutive_non_speech_frames = 0
                        elif self._speech_active:
                            # Still in speech, just a brief flicker — keep buffering
                            self._speech_buffer.append(chunk)
                elif (self._canary or self._whisper) and not foveal and self._speech_active:
                    # Between foveal frames, keep buffering chunks
                    self._speech_buffer.append(chunk)

                # ── Decide whether to push ──
                should_push = False
                if peripheral["onset"]:
                    should_push = True  # Onsets always push immediately
                elif foveal is not None:
                    should_push = True  # Foveal results always push
                elif not peripheral["is_silence"] and (now - last_push) >= _min_push_interval:
                    should_push = True  # Non-silent audio, throttled
                # Silent audio: don't push (save bandwidth)

                if should_push:
                    data = peripheral.copy()
                    data["ts"] = round(now, 3)
                    if foveal:
                        data["foveal"] = foveal
                        data["frame_type"] = "foveal"
                    else:
                        data["frame_type"] = "peripheral"

                    self._send_response({
                        "status": "ok",
                        "type": "passive_audio",
                        "data": data,
                    })
                    self._pushes_sent += 1
                    last_push = now

            except Exception as e:
                _err(f"Passive loop error: {e}")
                time.sleep(0.1)

    # ═══════════════════════════════════════════════════════════════════
    # SPEECH-TO-TEXT (Canary primary, Whisper legacy) (2026-03-22, Nous)
    # ═══════════════════════════════════════════════════════════════════

    def _fire_transcription(self, now: float):
        """Launch transcription in a background thread (non-blocking)."""
        if not self._speech_buffer or self._transcription_busy:
            _log(f"Transcription skipped: buffer={len(self._speech_buffer)}, busy={self._transcription_busy}")
            return
        # Snapshot the buffer
        audio_chunks = list(self._speech_buffer)
        duration_est = sum(len(c) for c in audio_chunks) / self._sample_rate
        _log(f"Firing transcription: {len(audio_chunks)} chunks, ~{duration_est:.1f}s, "
             f"whisper={self._whisper_source}")
        self._transcription_busy = True
        self._last_transcription = now

        t = threading.Thread(
            target=self._do_transcription, args=(audio_chunks, now),
            daemon=True, name="stt-transcribe"
        )
        t.start()

    def _do_transcription(self, audio_chunks: list, ts: float):
        """Transcribe accumulated speech buffer (runs in background thread).

        Uses Canary-1b-flash from audio.manifold (primary) or Whisper (legacy fallback).
        Canary model loads lazily on first transcription call.
        """
        try:
            audio = np.concatenate(audio_chunks)
            duration_s = len(audio) / self._sample_rate

            if duration_s < 1.5:
                _log(f"Transcription skip: too short ({duration_s:.2f}s < 1.5s)")
                return

            # Determine which engine to use
            _engine_name = "canary" if self._canary else ("whisper" if self._whisper else "none")
            _log(f"Calling {_engine_name}.transcribe({duration_s:.1f}s audio)...")

            # Write diagnostic to file (stderr unreliable in subprocess)
            try:
                _diag_path = Path(__file__).resolve().parents[3] / "state" / "whisper_diag.log"
                with open(_diag_path, "a", encoding="utf-8") as _df:
                    _df.write(f"[{time.time():.1f}] TRANSCRIBING {duration_s:.1f}s, "
                              f"engine={_engine_name}, source={self._whisper_source}\n")
                    _df.flush()
            except Exception:
                pass

            # FIX 2026-04-17 (Nous + Ace): Engine routing by context.
            # Music-context → Whisper Large v3 (trained on YouTube incl. music,
            #   much better at sung lyrics; lazy-loaded on first music trigger).
            # Conversation  → Canary-1b-flash (faster, efficient for speech).
            _is_music_ctx = getattr(self, '_speech_context_is_music', False)
            result = None

            if _is_music_ctx and HAS_DEMUCS:
                # PIECE: Demucs → Whisper pipeline for music-context transcription.
                # 1. Separate vocals from backing track via Demucs (htdemucs)
                # 2. Feed clean vocals to Whisper Large v3 with anti-hallucination
                #    params (condition_on_previous_text=False, no_repeat_ngram_size=3)
                vocals_audio = None
                try:
                    # Lazy-load Demucs on first music transcription
                    if self._demucs_model is None:
                        _log(f"First music transcription — lazy-loading Demucs '{self._demucs_model_name}'...")
                        import torch as _torch
                        _d_device = "cuda" if _torch.cuda.is_available() else "cpu"
                        self._demucs_model = _demucs_get_model(self._demucs_model_name)
                        self._demucs_model.to(_d_device)
                        self._demucs_model.eval()
                        _log(f"Demucs '{self._demucs_model_name}' loaded on {_d_device} "
                             f"(sources: {self._demucs_model.sources})")

                    # Prepare audio: demucs expects (batch, channels, samples) float32
                    import torch as _torch
                    _d_device = next(self._demucs_model.parameters()).device
                    # htdemucs trained at 44.1kHz stereo; we have mono at sample_rate.
                    # Upmix to stereo by duplicating, and resample if needed.
                    if self._sample_rate != 44100:
                        try:
                            import torchaudio as _ta
                            _resampler = _ta.transforms.Resample(
                                orig_freq=self._sample_rate, new_freq=44100
                            ).to(_d_device)
                            _audio_t = _torch.from_numpy(audio).float().to(_d_device)
                            _audio_t = _resampler(_audio_t)
                        except Exception:
                            _audio_t = _torch.from_numpy(audio).float().to(_d_device)
                    else:
                        _audio_t = _torch.from_numpy(audio).float().to(_d_device)
                    # (samples,) → (1, 2, samples) stereo batch
                    if _audio_t.dim() == 1:
                        _audio_t = _audio_t.unsqueeze(0).repeat(2, 1)
                    _audio_t = _audio_t.unsqueeze(0)  # batch dim

                    with _torch.no_grad():
                        _stems = _demucs_apply_model(
                            self._demucs_model, _audio_t, device=_d_device,
                            split=True, overlap=0.25,
                        )
                    # _stems shape: (batch, source, channels, samples)
                    # htdemucs source order: ['drums', 'bass', 'other', 'vocals']
                    _vocal_idx = self._demucs_model.sources.index('vocals')
                    _vocals = _stems[0, _vocal_idx].mean(dim=0)  # stereo → mono
                    # Resample back to original sample rate for Whisper
                    if self._sample_rate != 44100:
                        try:
                            import torchaudio as _ta
                            _back = _ta.transforms.Resample(
                                orig_freq=44100, new_freq=self._sample_rate
                            ).to(_d_device)
                            _vocals = _back(_vocals)
                        except Exception:
                            pass
                    vocals_audio = _vocals.detach().cpu().numpy().astype('float32')
                    _log(f"Demucs separated vocals: {len(vocals_audio) / self._sample_rate:.1f}s stem ready")
                except Exception as _de:
                    _log(f"Demucs separation failed: {_de} — will skip music transcription")
                    vocals_audio = None

                # Lazy-init Whisper Large on first music encounter (now with clean vocals)
                if vocals_audio is not None and self._music_whisper is None:
                    try:
                        _log(f"Lazy-loading Whisper '{self._music_whisper_size}' for music lyrics...")
                        self._music_whisper = WhisperEngine(
                            model_size=self._music_whisper_size, device="auto"
                        )
                    except Exception as _we:
                        _log(f"Whisper lazy-init failed: {_we}")
                        self._music_whisper = None

                if vocals_audio is not None and self._music_whisper and self._music_whisper.ensure_loaded():
                    _engine_name = f"demucs+whisper-{self._music_whisper_size}"
                    try:
                        # ANTI-HALLUCINATION PARAMS:
                        #   condition_on_previous_text=False → stops repetition trap
                        #   no_repeat_ngram_size=3 → bans repeating any 3-word phrase
                        #   vad_filter=True → skips silence automatically
                        #   beam_size=5 → wider search, better anchoring
                        segments, info = self._music_whisper._model.transcribe(
                            vocals_audio,
                            language="en",
                            beam_size=5,
                            vad_filter=True,
                            condition_on_previous_text=False,
                            no_repeat_ngram_size=3,
                        )
                        _segs = list(segments)
                        _text = " ".join(s.text for s in _segs).strip()
                        result = {
                            "text": _text,
                            "language": info.language if hasattr(info, 'language') else "en",
                            "language_confidence": float(getattr(info, 'language_probability', 0.6)),
                            "segments": [
                                {"text": s.text, "start": s.start, "end": s.end,
                                 "avg_logprob": getattr(s, 'avg_logprob', -0.5)}
                                for s in _segs[:10]
                            ],
                            "duration_s": duration_s,
                            "source": "demucs_whisper_music",
                        }
                    except Exception as _te:
                        _log(f"Whisper music transcription error: {_te}")
                        result = None

            # ── Canary path (fallback or conversation) ──
            if result is None:
                if self._canary:
                    result = self._canary.transcribe_array(audio, self._sample_rate)
                    if not result.get("error"):
                        result.setdefault("language", "en")
                        result.setdefault("language_confidence", 0.85)
                        result.setdefault("segments", [])
                        result.setdefault("duration_s", duration_s)
                elif self._whisper:
                    result = self._whisper.transcribe(audio, self._sample_rate)
                else:
                    _log("No STT engine available — skipping transcription")
                    return

            _log(f"{_engine_name} result: text='{result.get('text', '')[:80]}', "
                 f"error={result.get('error')}, source={result.get('source', 'unknown')}")
            try:
                with open(_diag_path, "a", encoding="utf-8") as _df:
                    _df.write(f"[{time.time():.1f}] RESULT: engine={_engine_name} "
                              f"text='{result.get('text', '')[:100]}' "
                              f"error={result.get('error')}\n")
                    _df.flush()
            except Exception:
                pass

            if result.get("text") and not result.get("error"):
                text = result["text"]
                confidence = result.get("language_confidence", 0.0)

                # Filter hallucinations — Canary is more robust than Whisper
                # but still filter very low confidence
                _conf_threshold = 0.1 if self._canary else 0.2
                if confidence < _conf_threshold:
                    _log(f"{_engine_name} very low confidence ({confidence:.2f}), skipping: {text[:60]}")
                    return

                # FIX 2026-04-11 (Nous + Ace): Filter STT hallucinations from ambient noise.
                # Fan/AC/background produces "Mmm.", "Hmm.", "..." etc. that get
                # transcribed and pollute consciousness with fake speech events.
                _HALLUCINATION_WORDS = {
                    "mmm", "hmm", "mm", "mhm", "uh", "um", "ah", "oh",
                    "mmm.", "hmm.", "mm.", "...", "you", "the", "i",
                    "thanks for watching", "thank you for watching",
                    "subscribe", "like and subscribe",
                }
                text_clean = text.strip().strip(".,!?").lower()
                if text_clean in _HALLUCINATION_WORDS or len(text_clean) < 3:
                    _log(f"{_engine_name} hallucination filtered: '{text}' (ambient noise)")
                    return

                # Check segment quality (Whisper-specific, Canary doesn't have segments)
                segments = result.get("segments", [])
                if segments:
                    avg_logprob = sum(s.get("avg_logprob", -1.0) for s in segments) / len(segments)
                    if avg_logprob < -1.5:
                        _log(f"{_engine_name} low segment quality (avg_logprob={avg_logprob:.2f}), "
                             f"skipping: {text[:60]}")
                        return

                # ── Speaker identification (2026-03-18, Nous) ──
                speaker_name = "unknown"
                speaker_confidence = 0.0
                speaker_is_new = False
                if self._voice_store:
                    try:
                        sig_dict = self._analyzer.extract_voice_signature(audio)
                        if sig_dict:
                            sig = VoiceSignature.from_dict(sig_dict)
                            speaker_name, speaker_confidence, speaker_is_new = \
                                self._voice_store.identify(sig)
                    except Exception as ve:
                        _err(f"Speaker identification error: {ve}")

                who = speaker_name if speaker_confidence >= 0.70 else "someone"
                _log(f"HEARD ({who}): \"{text[:100]}\" "
                     f"(conf={confidence:.2f}, speaker={speaker_name}/{speaker_confidence:.2f}, "
                     f"{duration_s:.1f}s)")

                # ── OLD Ship 1 phoneme_frames IPC send REMOVED 2026-05-17 ──
                # Was Whisper-gated (only fired inside _run_transcription).
                # Superseded by Ship 1.5 acoustic-trigger version at ~line 1604
                # (post-foveal-analysis, decoupled from Whisper/Canary entirely).
                # Per Ace's doctrine: substrate must monitor without external scaffolding.

                # ── Portal physics: transcription = heavy compute ──
                # Autocatalytic loop: transcription results ARE mass.
                # More mass → higher τ → faster transcription → more mass.
                # Energy amplified by τ before capture (like association cortex).
                energy = min(1.0, duration_s * 0.15)  # ~0.3 for 2s audio
                amplified_energy = energy * self._time_dilation  # τ amplifies energy!
                self._capture_energy(amplified_energy, "transcription")
                self._add_mass(duration_s)  # Mass = seconds of audio transcribed
                self._spend_tokens(int(duration_s * 5))  # ~10 tokens per 2s

                # FIX 2026-04-17 (Nous + Ace): Flag music-context transcriptions
                # as peripheral so downstream binds them with lower priority —
                # she hears lyrics, but they don't crowd conversation attention.
                _is_music_ctx = getattr(self, '_speech_context_is_music', False)
                self._send_response({
                    "status": "ok",
                    "type": "speech_transcription",
                    "data": {
                        "text": text,
                        "language": result.get("language", "en"),
                        "confidence": confidence,
                        "segments": segments[:10],  # Cap segment count
                        "duration_s": result.get("duration_s", 0),
                        "ts": round(ts, 3),
                        "speaker": speaker_name,
                        "speaker_confidence": round(speaker_confidence, 3),
                        "speaker_is_new": speaker_is_new,
                        # PIECE: peripheral music awareness
                        "is_music_context": _is_music_ctx,
                        "priority_hint": 0.35 if _is_music_ctx else 0.7,
                        "percept_tag": "lyric_fragment" if _is_music_ctx else "speech",
                    }
                })

                # Send separate speaker identification event for new/unknown speakers
                if speaker_is_new:
                    self._send_response({
                        "status": "ok",
                        "type": "speaker_identification",
                        "data": {
                            "speaker": speaker_name,
                            "speaker_confidence": round(speaker_confidence, 3),
                            "is_new": True,
                            "text_sample": text[:100],
                            "ts": round(ts, 3),
                        }
                    })
        except Exception as e:
            _err(f"Transcription error: {e}")
        finally:
            self._transcription_busy = False

    # ═══════════════════════════════════════════════════════════════════
    # ON-DEMAND CAPTURE
    # ═══════════════════════════════════════════════════════════════════

    def capture_now(self) -> Dict:
        """Full audio analysis on demand."""
        buffer = self._capture.get_buffer(duration_ms=1000)
        if buffer is None or len(buffer) < 1024:
            return {"error": "no_audio_data"}

        # Get current chunk for peripheral
        chunk = buffer[-self._capture.chunk_samples:] if len(buffer) >= self._capture.chunk_samples else buffer
        peripheral = self._analyzer.peripheral(chunk)
        foveal = self._analyzer.foveal(buffer)

        result = peripheral.copy()
        result["foveal"] = foveal
        result["frame_type"] = "full_capture"
        result["buffer_ms"] = round(len(buffer) / self._sample_rate * 1000, 1)
        result["ts"] = round(time.time(), 3)
        return result

    # ═══════════════════════════════════════════════════════════════════
    # IPC - stdin/stdout JSON protocol
    # ═══════════════════════════════════════════════════════════════════

    def _send_response(self, response: Dict):
        """Thread-safe write to stdout."""
        with self._stdout_lock:
            try:
                line = json.dumps(response, ensure_ascii=True) + "\n"
                sys.stdout.write(line)
                sys.stdout.flush()
            except Exception as e:
                _err(f"Failed to send response: {e}")

    def handle_command(self, cmd_dict: Dict) -> Dict:
        """Process a single command and return response."""
        cmd = cmd_dict.get("cmd", "")

        if cmd == "ping":
            return {
                "status": "pong",
                "backend": "sounddevice",
                "pid": os.getpid(),
                "python": sys.version.split()[0],
                "sample_rate": self._sample_rate,
                "device": self._capture._device_id,
            }

        elif cmd == "capture":
            result = self.capture_now()
            if "error" in result:
                return {"status": "error", "message": result["error"]}
            return {"status": "ok", "type": "audio_analysis", "data": result}

        elif cmd == "start_passive":
            self.start_passive()
            return {"status": "ok"}

        elif cmd == "stop_passive":
            self.stop_passive()
            return {"status": "ok"}

        elif cmd == "set_interval":
            new_interval = float(cmd_dict.get("seconds", self._foveal_interval))
            self._foveal_interval = max(0.1, min(5.0, new_interval))
            _log(f"Foveal interval set to {self._foveal_interval}s")
            return {"status": "ok", "foveal_interval": self._foveal_interval}

        elif cmd == "status":
            uptime = time.time() - self._started_at
            result = {
                "status": "ok",
                "type": "status",
                "uptime_seconds": round(uptime, 1),
                "passive_running": self._passive_running,
                "peripheral_count": self._peripheral_count,
                "foveal_count": self._foveal_count,
                "pushes_sent": self._pushes_sent,
                "chunks_captured": self._capture._chunks_captured,
                "overflows": self._capture._overflows,
                "sample_rate": self._sample_rate,
                "foveal_interval": self._foveal_interval,
                "speech_active": self._speech_active,
            }
            if self._whisper:
                result["whisper"] = self._whisper.status()
                result["whisper_source"] = self._whisper_source
            # Portal physics (Phase 2)
            if self._battery:
                result["portal_physics"] = self._portal_physics_status()
            return result

        elif cmd == "energy":
            # Receive energy from host (same protocol as cortex portal)
            amount = float(cmd_dict.get("amount", 0.0))
            if self._battery and amount > 0:
                self._battery.receive_energy(amount)
                return {
                    "status": "ok",
                    "health": self._battery.health_score,
                    "charge": round(self._battery.charge_level, 3),
                }
            return {"status": "ok", "health": 1.0}

        elif cmd == "portal_status":
            # Detailed portal physics status
            return {
                "status": "ok",
                "type": "portal_physics",
                "data": self._portal_physics_status(),
            }

        elif cmd == "learn_voice":
            # Learn a speaker's name: associate with current/provided voice signature
            name = cmd_dict.get("name", "").strip()
            sig_dict = cmd_dict.get("signature", None)
            if not name:
                return {"status": "error", "message": "Name required"}
            if not self._voice_store:
                return {"status": "error", "message": "Voice profiles not available"}

            sig = None
            if sig_dict:
                try:
                    sig = VoiceSignature.from_dict(sig_dict)
                except Exception as e:
                    return {"status": "error", "message": f"Invalid signature: {e}"}
            else:
                # Try to extract from current audio buffer
                buffer = self._capture.get_buffer(duration_ms=2000)
                if buffer is not None and len(buffer) > 1024:
                    sig_data = self._analyzer.extract_voice_signature(buffer)
                    if sig_data:
                        sig = VoiceSignature.from_dict(sig_data)

            result = self._voice_store.learn_voice(name, sig)
            return {"status": "ok", "type": "voice_learned", "data": result}

        elif cmd == "voice_profiles":
            # Return all voice profiles summary
            if not self._voice_store:
                return {"status": "ok", "type": "voice_profiles", "data": {"profiles": []}}
            return {
                "status": "ok",
                "type": "voice_profiles",
                "data": {
                    "profiles": self._voice_store.get_profiles_summary(),
                    "total": self._voice_store.profile_count,
                    "named": self._voice_store.named_count,
                    "unknown": self._voice_store.unknown_count,
                },
            }

        elif cmd == "shutdown":
            _log("Shutdown requested — saving portal state (TARDIS)")
            # Save voice profiles before shutdown
            if self._voice_store:
                self._voice_store.save()
                _log(f"Voice profiles saved ({self._voice_store.profile_count} profiles)")
            self.stop()  # Calls _save_portal_state() internally
            return {"status": "ok"}

        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def run_ipc_loop(self):
        """Main IPC loop: read commands from stdin, send responses to stdout."""
        _log("IPC loop started — waiting for commands on stdin")
        try:
            # FIX 2026-03-26 (Nous): Use readline() instead of `for line in sys.stdin:`
            # The iterator form uses internal read-ahead buffering on Windows which
            # can delay receiving the gate's initial ping by up to 30s, causing
            # the gate to timeout and declare the interior dead. readline() returns
            # immediately when a full line is available — critical for IPC.
            while True:
                line = sys.stdin.readline()
                if not line:  # EOF — gate closed stdin
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    cmd_dict = json.loads(line)
                except json.JSONDecodeError:
                    self._send_response({
                        "status": "error",
                        "message": "Invalid JSON"
                    })
                    continue

                response = self.handle_command(cmd_dict)
                self._send_response(response)

                # Shutdown exits the loop
                if cmd_dict.get("cmd") == "shutdown":
                    break

        except Exception as e:
            _err(f"IPC loop error: {e}")
        finally:
            self.stop()
            _log("IPC loop ended")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Audio Cortex Interior - always-on audio capture")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Foveal analysis interval in seconds (default: 0.5)")
    parser.add_argument("--sample-rate", type=int, default=44100,
                        help="Audio sample rate (default: 44100)")
    parser.add_argument("--device", type=int, default=None,
                        help="Audio device ID (default: auto-detect loopback)")
    parser.add_argument("--test", action="store_true",
                        help="Run standalone test (capture + print levels)")
    # FIX 2026-04-09 (Nous + Ace): Per-ear STT toggle.
    # Digital ear (stereo mix) should run with --no-stt to prevent Canary
    # from loading 5 GB of model weights when music vocals trip speech detector.
    parser.add_argument("--no-stt", action="store_true",
                        help="Disable speech-to-text (Canary) — for system audio loopback ears")
    args = parser.parse_args()

    if args.test:
        # Standalone test mode
        _log("=== STANDALONE TEST MODE ===")
        engine = AudioCortexEngine(
            sample_rate=args.sample_rate,
            device_id=args.device,
            foveal_interval=args.interval,
            enable_stt=not args.no_stt,
        )
        if not engine.start():
            _err("Failed to start audio capture")
            sys.exit(1)

        _log("Capturing audio for 10 seconds... (press Ctrl+C to stop)")
        analyzer = engine._analyzer
        capture = engine._capture
        t_end = time.time() + 10

        try:
            while time.time() < t_end:
                chunk = capture.get_chunk()
                if chunk is not None:
                    p = analyzer.peripheral(chunk)
                    print(f"  Level: {p['level_db']:6.1f} dB | "
                          f"Centroid: {p['spectral_centroid']:7.1f} Hz | "
                          f"Voice: {p['is_voice_band']} | "
                          f"Onset: {p['onset']} | "
                          f"Silent: {p['is_silence']}",
                          file=sys.stderr, flush=True)
                else:
                    time.sleep(0.01)

            # Final foveal analysis
            buffer = capture.get_buffer(500)
            if buffer is not None:
                f = analyzer.foveal(buffer)
                _log(f"Foveal: pitch={f.get('pitch_hz', 0):.1f}Hz, "
                     f"speech={f.get('is_speech')}, music={f.get('is_music')}, "
                     f"pattern={f.get('temporal_pattern')}")

        except KeyboardInterrupt:
            _log("Test interrupted")
        finally:
            engine.stop()
            _log("Test complete")
        return

    # Normal IPC mode
    engine = AudioCortexEngine(
        sample_rate=args.sample_rate,
        device_id=args.device,
        foveal_interval=args.interval,
        enable_stt=not args.no_stt,
    )

    if not engine.start():
        _err("Failed to start audio capture — exiting")
        # Still enter IPC loop so gate can get error responses
        engine.run_ipc_loop()
        sys.exit(1)

    engine.run_ipc_loop()


if __name__ == "__main__":
    main()
