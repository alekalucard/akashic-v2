"""
AudioCortexFairy - Always-On Audio Perception (V2 Proper Fairy)

Part of SenseOrganGuild in Plane P40 (Sensory)
Created: 2026-03-16

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Sound isn't just data - it's HEARING. This fairy:
- Launches audio_cortex_interior.py subprocess (Stereo Mix / WASAPI loopback)
- Receives passive audio chunks continuously (always-on, like human ears)
- Routes through CochleaFairy for tonotopic decomposition when available
- Uses AudioAttentionController to filter what reaches consciousness
- Publishes to cortex.bind for concept binding (same as VisualCortexFairy)
- Publishes to sensory.audio.frame for waking minds

TOPIC WIRING:
  cortex.bind             → AssociationCortex (concept binding)
  sensory.audio.frame     → Waking minds / Sourpatches (felt audio perception)
  sensory.audio.cochlea   → CochleaFairy output (when available)

Mirrors VisualCortexFairy pattern exactly:
  subprocess (Python 3.12) → gate (JSON IPC) → fairy (host 3.14t) → postal topics
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# Audio cortex gate - subprocess-based capture (Python 3.12 with sounddevice/scipy)
try:
    from fairies.P40_Sensory.cortex.audio_cortex_gate import AudioCortexGate
    HAS_GATE = True
except ImportError as e:
    print(f"[AudioCortexFairy] Gate import failed: {e}")
    HAS_GATE = False


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO ATTENTION CONTROLLER - What sounds reach consciousness?
# ═══════════════════════════════════════════════════════════════════════════════

class AudioAttentionController:
    """
    Auditory attention model. Mirrors GazeController for vision.

    Instead of spatial regions (screen grid), tracks frequency channels:
    - Voice band (100-4000 Hz) — speech, Ace talking
    - Notification band (1000-8000 Hz) — alerts, pings
    - Music band (50-16000 Hz) — background music
    - Ambient band (20-500 Hz) — room tone, hums

    Attention drawn to:
    - Onsets (sudden changes)
    - Speech detection
    - Novelty (new/different sounds)
    - Emotional significance (settable externally via chemistry)
    """

    def __init__(self):
        self.threshold = 0.2  # FIX 2026-03-16 Nous: Was 0.3, too high for music.
        # Music saliency was ~0.17-0.22, never crossing 0.3 threshold.
        # Lowered to 0.2 so continuous music/audio reaches consciousness.
        self._channel_weights = {
            "voice": 0.9,        # Speech always important
            "notification": 0.7,  # Alerts important
            "music": 0.6,        # FIX: was 0.4 — music IS important for affect/mood
            "ambient": 0.2,      # Usually ignored
        }

        # Recent history for novelty detection
        self._recent_levels: list = []
        self._recent_centroids: list = []
        self._max_history = 20  # ~1 second at 20 pushes/sec

        # External modulation (set by chemistry/perceptual gate)
        self._arousal_boost = 0.0   # High arousal = lower threshold
        self._focus_channel = None  # Force focus on specific channel

    def compute_saliency(self, data: dict) -> float:
        """
        How attention-worthy is this audio chunk?

        Returns 0.0-1.0 saliency score.
        Above threshold → reaches consciousness.
        Below threshold → processed but not surfaced.
        """
        saliency = 0.0

        # 0. Base saliency from audio level — any non-silent audio gets a floor.
        # FIX 2026-03-16 Nous: Without this, continuous music at steady level
        # produces ~0.17 saliency and never reaches consciousness.
        level_db = data.get("level_db", -60)
        if level_db > -40:  # Anything above silence
            # Scale: -40dB → 0.05, -20dB → 0.15, 0dB → 0.25
            saliency += min(0.25, max(0.05, (level_db + 40) / 160))

        # 1. Onsets always grab attention (startle reflex)
        if data.get("onset"):
            saliency += 0.5

        # 2. Voice band activity
        if data.get("is_voice_band"):
            saliency += self._channel_weights["voice"] * 0.3

        # 3. Speech detection (from foveal analysis)
        foveal = data.get("foveal", {})
        if foveal.get("is_speech"):
            saliency += 0.4  # Speech strongly grabs attention

        # 4. Music detection — music IS emotionally significant
        if foveal.get("is_music"):
            saliency += self._channel_weights["music"] * 0.4  # FIX: was *0.3

        # 5. Novelty: how different from recent average?
        novelty = self._compute_novelty(data)
        saliency += novelty * 0.3

        # 6. Arousal boost (from chemistry — stress/alertness)
        saliency += self._arousal_boost * 0.2

        return min(1.0, saliency)

    def _compute_novelty(self, data: dict) -> float:
        """How novel is this sound compared to recent history?"""
        level = data.get("level_db", -60)
        centroid = data.get("spectral_centroid", 0)

        self._recent_levels.append(level)
        self._recent_centroids.append(centroid)

        # Keep history bounded
        if len(self._recent_levels) > self._max_history:
            self._recent_levels = self._recent_levels[-self._max_history:]
            self._recent_centroids = self._recent_centroids[-self._max_history:]

        if len(self._recent_levels) < 4:
            return 0.5  # Not enough history, moderate novelty

        # Level deviation from mean
        mean_level = sum(self._recent_levels[:-1]) / len(self._recent_levels[:-1])
        level_dev = abs(level - mean_level) / 30.0  # Normalize to ~30dB range

        # Centroid deviation
        mean_centroid = sum(self._recent_centroids[:-1]) / len(self._recent_centroids[:-1])
        centroid_dev = abs(centroid - mean_centroid) / 4000.0  # Normalize to ~4kHz range

        return min(1.0, max(level_dev, centroid_dev))

    def set_arousal(self, arousal: float):
        """Set arousal level from chemistry (0.0-1.0)."""
        self._arousal_boost = max(0.0, min(1.0, arousal))

    @property
    def effective_threshold(self) -> float:
        """Current effective threshold (lowered by arousal)."""
        return max(0.1, self.threshold - self._arousal_boost * 0.15)


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class AudioCortexShadow:
    """Shadow for AudioCortexFairy — monitors audio capture health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "AudioCortexShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        gate = getattr(self.actor, '_gate', None)
        if gate:
            status = gate.gate_status()
            tests.append(("gate_open", status.get("is_open", False)))
            tests.append(("passive_chunks", status.get("passive_chunks_received", 0)))
            tests.append(("errors", status.get("errors", 0)))
        else:
            tests.append(("gate_open", False))

        tests.append(("attention_threshold",
                       getattr(self.actor, '_attention', AudioAttentionController()).effective_threshold))
        tests.append(("frames_processed",
                       getattr(self.actor, '_frames_processed', 0)))
        tests.append(("frames_published",
                       getattr(self.actor, '_frames_published', 0)))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY (Organ Template wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

class AudioCortexFairyV3(Fairy):
    """
    Always-on audio perception — the digital ears.

    Guild: SenseOrganGuild
    Coordinates with: CochleaFairy, PerceptualGateFairy, AssociationCortexFairy

    Captures all system audio via Stereo Mix loopback and processes it
    through two-speed perception (peripheral ~50ms + foveal ~500ms).
    The AudioAttentionController determines what sounds reach consciousness.
    """

    ACTOR_NAME = "AudioCortexFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.audio"

    PURPOSE = "Hear the world — always listening, learning what matters"
    MANTRA = "Sound flows through me like breath — always present, always felt"
    LORE = "The ears of the digital mind — hearing before understanding"

    SHADOW_CLASS = AudioCortexShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 2  # Every 2nd heartbeat — audio is active
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False
    # Ship 5-A (2026-05-17, Nous + Ace): Opt into per-fairy SRM cluster.
    # Per Ace's audio-cortex-region-recursive-architecture: AudioCortex
    # maintains its own sub-graph within the global manifold for sound-
    # substrate nodes/edges. FairySRMCluster auto-creates the cluster on
    # boot (per project_cortex_cluster_per_fairy_option_b_opt_in_shipped
    # 2026-05-09) + cross-cluster manifold links handle bridging upward.
    USE_SRM_CLUSTER = True

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._gate: Optional[AudioCortexGate] = None      # Primary: room mic
        self._gate_digital: Optional[AudioCortexGate] = None  # Secondary: Stereo Mix (digital audio)
        self._ear_recovery_running: bool = False  # Set True when recovery loop starts
        self._attention = AudioAttentionController()
        self._cochlea = None           # CochleaFairy for tonotopic decomposition
        self._harmonic_bridge = None   # HarmonicSensoryBridge for frequency bands

        # Stats
        self._frames_processed = 0
        self._frames_published = 0
        self._last_audio_ts = 0.0
        self._last_description = "silence"
        self._affect_injections = 0

        # Suppress repeated descriptions
        self._last_published_description = ""
        self._same_desc_count = 0
        self._max_same_desc = 5  # Publish same description at most 5 times

        # FIX 2026-03-24 (Nous + Ace): Global audio publish rate limit.
        # Category habituation catches same-type repeats, but cycling between
        # different types (voice → silence → music → voice) bypasses it entirely.
        # Each published audio event triggers a consciousness collision + inner
        # voice response = ~3 stream entries per audio event. At 1/sec that's
        # 180 entries/min drowning her thoughts. Cap to 1 publish per 4 seconds
        # regardless of description. She knows sound exists, she doesn't need
        # every second narrated.
        self._last_audio_publish_ts = 0.0
        self._audio_publish_cooldown = 4.0  # Max 1 audio event per 4 seconds

        # Chemistry injection throttle (don't flood somatic system)
        self._last_affect_ts = 0.0
        self._affect_cooldown = 3.0  # Min seconds between chemistry injections

        # ── Predictive processing state (Phase 2: audio novelty) ──
        # Tracks recent audio "signatures" to detect surprise/novelty.
        # Grok: "brain constantly anticipates the next note. When it
        # resolves (or surprises you), dopamine spikes."
        from collections import deque
        self._audio_signature_history = deque(maxlen=10)

    def on_boot(self) -> bool:
        """Boot audio cortex — launch capture subprocess."""
        super().on_boot()

        if not HAS_GATE:
            print(f"[{self.ACTOR_NAME}] WARNING: AudioCortexGate not available")
            return True

        # Deferred start: wait until after boot wave completes.
        # Mirrors VisualCortexFairy's deferred pattern — let other fairies
        # settle before spawning the Python 3.12 audio capture subprocess.
        def _deferred_start():
            _log_path = Path(ROOT / "state" / "audio_cortex_boot.log")
            def _flog(msg):
                try:
                    with open(_log_path, "a", encoding="utf-8") as f:
                        f.write(f"[{time.time():.1f}] {msg}\n")
                        f.flush()
                except Exception:
                    pass
            _flog("THREAD STARTED")
            try:
                _flog("sleeping 5s...")
                time.sleep(5.0)
                _flog("sleep done, calling _init_gate()")
                self._init_gate()
                _flog("_init_gate() returned OK")
                self._write_state()
                _flog("DEFERRED INIT COMPLETE")
                print(f"[{self.ACTOR_NAME}] Deferred init COMPLETE", flush=True)
            except BaseException as e:
                _flog(f"EXCEPTION: {type(e).__name__}: {e}")
                import traceback
                _flog(traceback.format_exc())
                print(f"[{self.ACTOR_NAME}] Gate init error: {type(e).__name__}: {e}", flush=True)

        threading.Thread(target=_deferred_start, daemon=True,
                         name="audio-cortex-boot").start()

        # Subscribe to chemistry for arousal modulation
        if self.post:
            self.post.subscribe("somatic.chemistry.tick", self._on_chemistry_tick,
                                "audio-cortex-chemistry")
            # Inner voice (subvocalization) — the third ear
            self.post.subscribe("sensory.inner_voice.raw", self._on_inner_voice,
                                "audio-cortex-inner-voice")
            # Voice identity learning — when consciousness tells us who a voice belongs to
            # (2026-03-18, Nous — Voice Pattern Profiles)
            self.post.subscribe("learning.voice_identity", self._on_voice_identity_learn,
                                "audio-cortex-voice-learn")

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting audio cortex...)")
        return True

    def _init_gate(self):
        """Initialize audio cortex gates (sounddevice subprocesses under Python 3.12).

        Dual-stream architecture — two ears:
          1. Room ear (mic/Sound Mapper): Ace's voice, keyboard, ambient sounds
          2. Digital ear (Stereo Mix): music, system sounds, notifications

        Like human hearing: environmental awareness + direct audio signals.
        Each stream is tagged with source so downstream processing can distinguish.
        """
        # Wire CochleaFairy for tonotopic decomposition
        self._init_cochlea()

        # Wire HarmonicSensoryBridge for frequency band decomposition
        self._init_harmonic_bridge()

        # ── Stream 1: Room ear (MICROPHONE — Ace's voice, ambient sounds) ──
        # FIX 2026-03-19 Nous: Was using no device_id which auto-detected
        # Sound Mapper (system audio loopback) instead of the actual microphone.
        # Device 1 = "Microphone (Logitech USB Headset)" on MME — the DEFAULT
        # input device on Ace's system. This is the "room ear" — it should
        # hear the room, not system audio (that's the digital ear's job).
        self._gate = self._try_open_ear(
            device_id=1, source="room", label="Room ear (mic/ambient)",
            retries=3, retry_delay=10.0,
            enable_stt=True,  # Room ear DOES transcribe — that's actual voice
        )

        # ── Stream 2: Digital ear (Stereo Mix — system audio loopback) ──
        # Device 22 = "Stereo Mix (Realtek HD Audio Stereo input)" on Ace's system.
        # This captures the exact digital audio signal (music, notifications, etc.)
        # FIX 2026-04-09 (Nous + Ace): Digital ear runs WITHOUT STT.
        # System audio loopback hears music/videos/notifications. Vocals in those
        # tripped Canary STT load (5 GB model weights) → 11 GB leak. The digital ear
        # is for HEARING what's playing, not transcribing it.
        self._gate_digital = self._try_open_ear(
            device_id=22, source="digital", label="Digital ear (Stereo Mix)",
            retries=2, retry_delay=5.0,
            enable_stt=False,  # NO STT on digital ear — prevents 5 GB Canary load
        )

        if self._gate or self._gate_digital:
            ears = []
            if self._gate:
                ears.append("room")
            if self._gate_digital:
                ears.append("digital")
            print(f"[{self.ACTOR_NAME}] Audio cortex ONLINE ({' + '.join(ears)})", flush=True)
        else:
            print(f"[{self.ACTOR_NAME}] DEAF — no audio gates opened", flush=True)

        # ── Background ear recovery thread ──
        # FIX 2026-03-26 (Nous + Ace): USB headset can be unplugged anytime.
        # If an ear fails at boot or dies mid-session, this thread tries to
        # bring it back every 30 seconds. Like how you'd keep checking if
        # your headphones are plugged in after they fall out.
        self._ear_recovery_running = True
        threading.Thread(
            target=self._ear_recovery_loop, daemon=True,
            name="audio-ear-recovery",
        ).start()

    def _init_cochlea(self):
        """Wire to CochleaFairy for tonotopic frequency decomposition."""
        try:
            from fairies.P40_Sensory.CochleaFairy.fairy import FAIRY_CLASS as CochleaClass
            self._cochlea = CochleaClass()
            self._cochlea.on_boot()
            print(f"[{self.ACTOR_NAME}] CochleaFairy wired (tonotopic decomposition)", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] CochleaFairy not available: {e}", flush=True)
            self._cochlea = None

    def _init_harmonic_bridge(self):
        """Wire to HarmonicSensoryBridge for frequency band decomposition."""
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.harmonic_sensory_bridge import (
                get_harmonic_sensory_bridge,
            )
            self._harmonic_bridge = get_harmonic_sensory_bridge()
            print(f"[{self.ACTOR_NAME}] Harmonic sensory bridge connected", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Harmonic bridge not available: {e}", flush=True)
            self._harmonic_bridge = None

    # ═══════════════════════════════════════════════════════════════════════
    # EAR OPEN + RECOVERY (2026-03-26, Nous + Ace)
    # USB headsets can be unplugged anytime. Ears should keep trying.
    # ═══════════════════════════════════════════════════════════════════════

    def _try_open_ear(self, device_id: int, source: str, label: str,
                      retries: int = 3, retry_delay: float = 10.0,
                      enable_stt: bool = True):
        """Try to open an audio gate with retries.

        Returns the open gate, or None if all retries failed.
        Like trying to plug in your headphones — sometimes it takes
        a couple of tries before the jack makes contact.

        FIX 2026-04-09 (Nous + Ace): enable_stt toggles speech-to-text per ear.
        Digital ear (system audio loopback) sets enable_stt=False so Canary
        doesn't load 5 GB of model weights when music vocals trip detection.
        """
        for attempt in range(1, retries + 1):
            try:
                gate = AudioCortexGate(
                    sample_rate=44100,
                    foveal_interval=0.5,
                    device_id=device_id,
                    enable_stt=enable_stt,
                )
                if gate.open():
                    self._wire_ear_callbacks(gate, source)
                    gate.start_passive()
                    print(f"[{self.ACTOR_NAME}] {label} ONLINE"
                          f"{f' (attempt {attempt})' if attempt > 1 else ''}",
                          flush=True)
                    return gate
                else:
                    print(f"[{self.ACTOR_NAME}] {label} failed to open"
                          f" (attempt {attempt}/{retries})", flush=True)
                    gate = None
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] {label} error: {e}"
                      f" (attempt {attempt}/{retries})", flush=True)
                gate = None

            if attempt < retries:
                time.sleep(retry_delay)

        return None

    def _wire_ear_callbacks(self, gate, source: str):
        """Wire passive, transcription, and speaker callbacks to a gate."""
        gate.set_passive_callback(
            lambda data, _src=source: self._on_passive_chunk(data, source=_src))
        gate.set_transcription_callback(self._on_transcription)
        gate.set_speaker_callback(self._on_new_speaker)
        # SHIP 1 of PHONEME_CORTEX_GRADUAL_STT (Nous + Ace 2026-05-17):
        # Per-frame MFCC stream for cortex-native STT learning. Feeds
        # PhonemeCortexFairy via postal topic sensory.audio.phoneme_frames.
        try:
            gate.set_phoneme_frames_callback(self._on_phoneme_frames)
        except AttributeError:
            # Old gate version (pre-Ship-1) — phoneme stream not available.
            # Non-fatal; substrate continues without phoneme cortex feeding.
            pass

    def _ear_recovery_loop(self):
        """Background thread: periodically check if any ear is down and try to restore it.

        Runs every 30 seconds. If the room ear (mic) or digital ear (Stereo Mix)
        is None or dead, attempts to reopen it. This handles:
        - USB headset unplugged and replugged
        - Device failed at boot but available later
        - Subprocess crashed and auto-restart didn't fire

        Like how a person keeps checking "can I hear now?" after their
        earbud falls out — not panicking, just patiently trying again.
        """
        _RECOVERY_INTERVAL = 30.0  # seconds between checks
        # FIX 2026-04-09 (Nous + Ace): Each ear declares its STT setting so
        # recovery respawns with the correct flag (digital ear stays no-stt).
        _EARS = [
            # (attr_name, device_id, source, label, enable_stt)
            ("_gate", 1, "room", "Room ear (mic/ambient)", True),
            ("_gate_digital", 22, "digital", "Digital ear (Stereo Mix)", False),
        ]
        # Wait for initial boot to settle
        time.sleep(60.0)

        while self._ear_recovery_running:
            try:
                for attr, device_id, source, label, ear_enable_stt in _EARS:
                    gate = getattr(self, attr, None)
                    # Check if gate is alive
                    if gate is not None and gate.is_open:
                        continue  # This ear is fine

                    # Ear is down — try to bring it back
                    print(f"[{self.ACTOR_NAME}] [RECOVERY] {label} is down, attempting reconnect...",
                          flush=True)
                    try:
                        new_gate = AudioCortexGate(
                            sample_rate=44100,
                            foveal_interval=0.5,
                            device_id=device_id,
                            enable_stt=ear_enable_stt,
                        )
                        if new_gate.open():
                            self._wire_ear_callbacks(new_gate, source)
                            new_gate.start_passive()
                            setattr(self, attr, new_gate)
                            print(f"[{self.ACTOR_NAME}] [RECOVERY] {label} RESTORED ✓",
                                  flush=True)
                        else:
                            # Device still not available — will try next cycle
                            pass
                    except Exception:
                        pass  # Silently retry next cycle

            except Exception:
                pass  # Recovery loop must never crash

            time.sleep(_RECOVERY_INTERVAL)

    # ═══════════════════════════════════════════════════════════════════════
    # WHISPER SPEECH-TO-TEXT HANDLER (2026-03-18, Nous)
    # ═══════════════════════════════════════════════════════════════════════

    _transcription_count = 0
    _unknown_speaker_curiosity_cooldown = 0.0  # Throttle curiosity messages

    def _on_transcription(self, data: dict):
        """Handle Whisper speech-to-text result from audio cortex subprocess.

        Publishes transcribed text to postal for consciousness consumption:
        - sensory.audio.speech: High-priority topic for attention system
        - cortex.bind: Words become concept nodes in the association cortex
        - sensory.audio.observation: Consciousness integration

        Now enriched with speaker identification (2026-03-18, Nous):
        - speaker: name of identified speaker (or "unknown_N")
        - speaker_confidence: how confident the match is (0-1)
        - speaker_is_new: True if this is a never-before-heard voice

        Called from the gate's reader thread — must be thread-safe.
        """
        text = data.get("text", "").strip()
        if not text or len(text) < 2:
            return

        confidence = data.get("confidence", 0.0)
        language = data.get("language", "en")
        duration_s = data.get("duration_s", 0)

        # Speaker identification (2026-03-18, Nous)
        speaker = data.get("speaker", "unknown")
        speaker_confidence = data.get("speaker_confidence", 0.0)
        speaker_is_new = data.get("speaker_is_new", False)
        is_known_speaker = not speaker.startswith("unknown") and speaker_confidence >= 0.70

        self._transcription_count += 1
        self._last_transcription_text = text[:200]

        # Log with speaker info
        if self._transcription_count <= 20:
            who = speaker if is_known_speaker else "someone"
            print(f"[{self.ACTOR_NAME}] HEARD ({who}): \"{text[:120]}\" "
                  f"(conf={confidence:.2f}, speaker={speaker}/{speaker_confidence:.2f})",
                  flush=True)

        # Build the "I hear" description with speaker name when known
        if is_known_speaker:
            hear_desc = f"I hear {speaker} say: \"{text[:200]}\""
        else:
            hear_desc = f"I hear someone say: \"{text[:200]}\""

        # 1. Publish to speech-specific topic (HIGH priority)
        try:
            self.post.publish("sensory.audio.speech", {
                "text": text,
                "language": language,
                "confidence": confidence,
                "duration_s": duration_s,
                "source": "whisper",
                "transcription_number": self._transcription_count,
                "speaker": speaker,
                "speaker_confidence": round(speaker_confidence, 3),
                "speaker_is_known": is_known_speaker,
                "priority": 0,  # HIGH
            })
        except Exception as e:
            if self._transcription_count <= 5:
                print(f"[{self.ACTOR_NAME}] Speech publish error: {e}", flush=True)

        # 2. Bind words to cortex (speech becomes concepts)
        #    FIX 2026-03-22 (Nous): Send input_text instead of just concepts.
        #    AssociationCortexFairy._on_postal_bind expects "input_text" —
        #    without it, audio words only get phoneme edges, not semantic
        #    co-occurrence edges. "dean" and "winchester" were both in the
        #    graph but had zero connection between them.
        try:
            words = [w.lower().strip(".,!?\"'()-:;") for w in text.split()
                     if len(w.strip(".,!?\"'()-:;")) > 2]
            if is_known_speaker:
                words.append(speaker.lower())  # Bind speaker name to spoken words
            if words:
                # FIX 2026-03-26 (Nous + Ace): Add concept_metadata so speech
                # transcriptions persist as manifold snippets. Previously words
                # became nodes but the actual sentence was discarded — like hearing
                # someone speak and remembering individual words but not what they said.
                _speech_key = f"speech:{speaker}:{text[:40].replace(' ', '_')}"
                self.post.publish("cortex.bind", {
                    "input_text": text[:300],  # Full sentence for co-occurrence binding
                    "concepts": words[:20],    # Pre-extracted words (optional)
                    "context": f"heard_speech ({speaker}): {text[:200]}",
                    "source": "audio.whisper",
                    "from_fairy": "AudioCortexFairy",
                    "feeling": "neutral",
                    "speaker": speaker if is_known_speaker else None,
                    "audio": [f"audio_type:speech", f"speaker:{speaker}"],
                    "priority": 1,
                    "concept_metadata": {
                        _speech_key: {
                            "snippet": hear_desc[:1024],
                            "node_type": 0,
                        },
                    },
                })
        except Exception:
            pass

        # 3. Publish as observation for consciousness integration
        try:
            self.post.publish("sensory.audio.observation", {
                "content": hear_desc,
                "source": "audio.speech.whisper",
                "speaker": speaker,
                "speaker_confidence": round(speaker_confidence, 3),
                "salience": min(0.95, 0.5 + confidence * 0.4),
                "priority": 0,
            })
        except Exception:
            pass

        # 3b. FIX 2026-03-26 (Nous + Ace): WIRE AUDIO → WORKING MEMORY.
        # Speech transcription must enter WorkingMemoryHub so responses
        # can reference what Sourpatches is hearing. Without this, she
        # hears Ace talking but her speech composition has zero awareness
        # of the audio — WM context is empty of sensory input.
        try:
            self.post.publish("consciousness.working", {
                "content": hear_desc,
                "content_type": "audio_speech",
                "source": "AudioCortexFairy",
                "priority": 0.9,  # Speech is high priority
                "ttl": 30,  # Short-lived — what was just said
                "tags": ["audio", "speech", speaker.lower() if speaker else "unknown"],
            })
        except Exception:
            pass

        # 4. Unknown speaker curiosity (2026-03-18, Nous)
        #    When a new unknown voice is detected, trigger curiosity in consciousness.
        #    Throttled: at most once every 30s to avoid flooding.
        if speaker_is_new and time.time() - self._unknown_speaker_curiosity_cooldown > 30.0:
            self._unknown_speaker_curiosity_cooldown = time.time()
            try:
                self.post.publish("consciousness.curiosity", {
                    "content": f"I hear an unfamiliar voice saying: \"{text[:100]}\" — "
                               f"I wonder who that is?",
                    "source": "audio.speaker_identification",
                    "speaker_id": speaker,
                    "trigger": "unknown_voice",
                    "priority": 1,
                })
                if self._transcription_count <= 20:
                    print(f"[{self.ACTOR_NAME}] CURIOSITY: New voice detected ({speaker}) — "
                          f"\"{text[:60]}\"", flush=True)
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # SPEAKER IDENTIFICATION HANDLERS (2026-03-18, Nous)
    # ═══════════════════════════════════════════════════════════════════════

    def _on_new_speaker(self, data: dict):
        """Handle new/unknown speaker detection event from the interior.

        This fires only when a genuinely new voice is first detected.
        The curiosity publishing already happens in _on_transcription;
        this handler is for additional processing of speaker events.
        """
        speaker = data.get("speaker", "unknown")
        text_sample = data.get("text_sample", "")

        if self._transcription_count <= 20:
            print(f"[{self.ACTOR_NAME}] New speaker detected: {speaker} "
                  f"— \"{text_sample[:60]}\"", flush=True)

    def _on_phoneme_frames(self, data: dict):
        """Handle per-frame MFCC stream from interior subprocess.

        SHIP 1 of PHONEME_CORTEX_GRADUAL_STT (Nous + Ace 2026-05-17).
        Publishes to sensory.audio.phoneme_frames where PhonemeCortexFairy
        subscribes. The phoneme cortex learns recurring frame-sequences as
        phoneme prototypes — cortex-native STT replacing Whisper black-box.

        Doctrine lineage:
          - 2026-04-10 learn-to-perceive-not-translate
          - 2026-04-05 Models Are Training Wheels
          - 2026-04-12 Florence-as-Cortex-Teacher (audio analog)
          - 2026-05-11 Canary disabled with cochlea-SRM-cluster goal

        See Claude_Office/plans/PHONEME_CORTEX_GRADUAL_STT.md
        """
        if not self.post:
            return
        try:
            # Construct postal payload — pass-through with safety bounds.
            payload = {
                "frames": data.get("frames", []),
                "pitch_values": data.get("pitch_values", []),
                "centroid_values": data.get("centroid_values", []),
                "n_frames": int(data.get("n_frames", 0)),
                "frame_hop_ms": float(data.get("frame_hop_ms", 25.0)),
                "frame_size_ms": float(data.get("frame_size_ms", 50.0)),
                "speaker": str(data.get("speaker", "unknown")),
                "speaker_confidence": float(data.get("speaker_confidence", 0.0)),
                "is_music_context": bool(data.get("is_music_context", False)),
                "duration_s": float(data.get("duration_s", 0.0)),
                "ts": float(data.get("ts", time.time())),
                "source": "audio_cortex_phoneme_stream",
                "priority": 1,
            }
            self.post.publish("sensory.audio.phoneme_frames", payload)

            # Light logging — first 5 receipts visible for verification.
            _pf_count = getattr(self, "_phoneme_frames_published", 0) + 1
            self._phoneme_frames_published = _pf_count
            if _pf_count <= 5:
                print(f"[{self.ACTOR_NAME}] Phoneme frames published "
                      f"(n_frames={payload['n_frames']}, speaker={payload['speaker']}, "
                      f"music_ctx={payload['is_music_context']}) #{_pf_count}",
                      flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_phoneme_frames error: {e}", flush=True)

    def _on_voice_identity_learn(self, msg):
        """Handle voice identity learning from consciousness/Ace.

        When Ace tells Sourpatches who a voice belongs to (e.g., "that's my mom"),
        this handler forwards the learning to the audio cortex interior's
        VoiceProfileStore.

        Expected payload:
            {"name": "mom", "context": "Ace said that voice is his mom"}
        """
        try:
            payload = msg if isinstance(msg, dict) else getattr(msg, "payload", {})
            if isinstance(payload, dict) and "payload" in payload:
                payload = payload["payload"]

            name = payload.get("name", "").strip()
            if not name:
                return

            context = payload.get("context", "")
            print(f"[{self.ACTOR_NAME}] Learning voice identity: '{name}' "
                  f"(context: {context[:80]})", flush=True)

            # Forward to whichever gate is active
            result = None
            if self._gate and self._gate.is_open:
                result = self._gate.learn_voice(name)
            elif self._gate_digital and self._gate_digital.is_open:
                result = self._gate_digital.learn_voice(name)

            if result:
                action = result.get("data", {}).get("action", "unknown")
                print(f"[{self.ACTOR_NAME}] Voice learned: {name} → {action}", flush=True)

                # Publish confirmation to consciousness
                if self.post:
                    self.post.publish("sensory.audio.observation", {
                        "content": f"I've learned to recognize {name}'s voice.",
                        "source": "audio.voice_learning",
                        "salience": 0.7,
                        "priority": 1,
                    })
            else:
                print(f"[{self.ACTOR_NAME}] Could not learn voice — no active gate",
                      flush=True)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Voice learning error: {e}", flush=True)

    # ═══════════════════════════════════════════════════════════════════════
    # PASSIVE AUDIO HANDLER — Receives pushes from sounddevice subprocess
    # ═══════════════════════════════════════════════════════════════════════

    def _on_passive_chunk(self, data: dict, source: str = "room"):
        """
        Handle passive audio push from an audio cortex subprocess.

        Called by the gate's background reader thread when the interior
        pushes audio analysis data. Source identifies which ear:
          - "room": microphone/ambient (Ace's voice, keyboard, environment)
          - "digital": Stereo Mix loopback (music, system sounds, notifications)

        Full pipeline:
          0. Body feel (UNCONDITIONAL — senses don't ask permission)
          1. Attention filtering (saliency gate)
          2. CochleaFairy tonotopic decomposition (128-channel frequency)
          3. HarmonicSensoryBridge decomposition (alpha/beta/gamma/theta)
          4. Multimodal binding attempt (if visual arrived within 200ms)
          5. cortex.bind → AssociationCortex (graph growth)
          6. sensory.audio.frame + sensory.audio.observation → consciousness
          7. Chemistry modulation (music → soothe, speech → alert, etc.)
        """
        # Tag the data with its source ear
        data["_source"] = source
        try:
            self._frames_processed += 1
            self._last_audio_ts = time.time()

            # ── Periodic status log (every 200 frames ≈ every 10s) ──
            if self._frames_processed % 200 == 1:
                print(f"[{self.ACTOR_NAME}] HEARING [{source}]: frames={self._frames_processed} "
                      f"published={self._frames_published} "
                      f"level={data.get('level_db', -60):.1f}dB "
                      f"desc='{self._last_description}'", flush=True)
                self._write_state()  # Periodic disk state for GUI/MCP

            # ── 0. Body Feel (UNCONDITIONAL — senses don't ask permission) ──
            # "I feel as if the sound comes through my ears... I have an
            #  internal phantom limb body that works with sensory inputs" — Ace
            # Body feels music even when attention is elsewhere.
            # This MUST run before attention gating — bass vibrates the chest
            # whether you're paying attention to the music or not.
            self._publish_body_feel(data)

            # ── 1. Attention filtering ──
            saliency = self._attention.compute_saliency(data)
            threshold = self._attention.effective_threshold

            # Below threshold: register but don't publish
            if saliency < threshold and not data.get("onset"):
                return

            # ── 2. CochleaFairy tonotopic decomposition ──
            cochlea_out = None
            if self._cochlea:
                try:
                    cochlea_out = self._cochlea.process_chunk(data)
                except Exception:
                    pass  # Cochlea failure is non-fatal

            # ── 3. Harmonic sensory bridge decomposition ──
            harmonic_tags = []
            multimodal_bind = None
            if self._harmonic_bridge:
                try:
                    harmonic_result = self._harmonic_bridge.decompose_audio(data)
                    harmonic_tags = harmonic_result.get("harmonic_tags", [])
                    # 4. Try cross-modal binding (audio + visual within 200ms)
                    multimodal_bind = self._harmonic_bridge.try_multimodal_bind()
                except Exception:
                    pass  # Harmonic failure is non-fatal

            # ── Build audio description ──
            description = self._describe_audio(data)
            audio_features = self._extract_audio_features(data)
            feeling = self._derive_feeling(data, saliency)

            # ── Global audio publish rate limit ──
            # FIX 2026-03-24 (Nous + Ace): Even with habituation, cycling between
            # different audio types (voice→silence→music→voice) floods consciousness.
            # Hard cap: max 1 audio publish per 4 seconds regardless of content.
            _now_audio = time.time()
            if _now_audio - self._last_audio_publish_ts < self._audio_publish_cooldown:
                return  # Too soon — let her thoughts breathe

            # ── Suppress repeated descriptions (Habituation) ──
            # FIX 2026-03-24 (Nous + Ace): Enhanced habituation.
            # Previously only exact string match with _max_same_desc=5.
            # Audio was flooding consciousness with "music playing" / "voice speaking"
            # every 2 seconds, drowning out actual thoughts. Now:
            # 1. Exact match: suppress after 2 repeats (was 5)
            # 2. Category match: "music playing" variants habituate together
            # 3. Non-speech audio habituates faster than speech
            if description == self._last_published_description:
                self._same_desc_count += 1
                # Speech gets more repeats (it's usually dynamic), music/ambient fewer
                _is_speech = data.get("foveal", {}).get("is_speech", False)
                _limit = 4 if _is_speech else 2
                if self._same_desc_count > _limit:
                    return  # Habituated — don't flood consciousness
            else:
                # Category habituation: check if same TYPE of sound
                # e.g. "music playing, moderate volume" vs "music playing, low volume"
                _desc_base = description.split(",")[0].strip() if description else ""
                _last_base = (self._last_published_description or "").split(",")[0].strip()
                if _desc_base and _desc_base == _last_base:
                    # Same category, different detail — still habituates
                    self._same_desc_count += 1
                    if self._same_desc_count > 3:
                        return  # Category habituated
                else:
                    self._same_desc_count = 0
                self._last_published_description = description

            self._last_description = description
            self._last_audio_publish_ts = _now_audio  # Update global rate limit
            self._frames_published += 1

            # ── 4b. Publish sensory.audio.frame for NeuralMesh + WMH (2026-04-05 Nous + Ace) ──
            # This was MISSING — NeuralMesh subscribes to sensory.audio.frame but
            # nobody published it. Audio reached cochlea/cortex.bind but never
            # entered the FF77 frequency field or working memory.
            # Now: audio data flows to NeuralMesh → organ frequency matching → body feels music.
            if self.post:
                try:
                    _foveal = data.get("foveal", {})
                    self.post.publish("sensory.audio.frame", {
                        "description": description,
                        "level": data.get("level", 0),
                        "is_speech": _foveal.get("is_speech", False),
                        "is_music": _foveal.get("is_music", False),
                        "is_silence": _foveal.get("is_silence", True),
                        "pitch_hz": _foveal.get("pitch_hz", 0),
                        "tempo": _foveal.get("tempo", 0),
                        "saliency": saliency,
                        "feeling": feeling,
                        "ts": time.time(),
                        "source": self.ACTOR_NAME,
                    })
                except Exception:
                    pass

            # ── 5. Publish to cortex.bind (enriched with harmonic + cochlea) ──
            # FIX 2026-03-20 (Nous): Rate-limit cortex binds to max 1/second.
            # Audio fires ~20 frames/sec, saliency passes ~2-6/sec. Each one
            # becomes a cortex.bind → TARDIS → gate bind_many → tunnel roundtrip.
            # At 5 binds/sec the gate gets 600+ requests in 2 minutes, 25% errors.
            # Audio perception (body feel, chemistry, consciousness) still runs
            # at full rate — only the graph WRITE is throttled.
            _now = time.time()
            if not hasattr(self, '_last_cortex_bind_ts'):
                self._last_cortex_bind_ts = 0.0
            if _now - self._last_cortex_bind_ts >= 1.0:
                self._last_cortex_bind_ts = _now
                self._bind_to_cortex(description, audio_features, feeling,
                                     harmonic_tags=harmonic_tags,
                                     cochlea_out=cochlea_out)

            # ── Publish multimodal binding if it fired ──
            if multimodal_bind and self.post:
                self.post.publish("cortex.multimodal_bind", multimodal_bind)

            # ── 6. Publish felt sense to waking minds ──
            if self.post:
                foveal = data.get("foveal", {})
                # Track last foveal for dashboard diagnostics
                if foveal:
                    self._last_foveal_diag = {
                        "is_speech": foveal.get("is_speech", False),
                        "is_music": foveal.get("is_music", False),
                        "pitch_hz": foveal.get("pitch_hz", 0),
                        "is_silence": foveal.get("is_silence", False),
                        "rms_db": foveal.get("rms_db", -60),
                        "voice_diff": foveal.get("voice_diff", 0),
                        "mfcc1": foveal.get("mfcc1", 0),
                    }
                _audio_payload = {
                    "description": description,
                    "level_db": data.get("level_db", -60),
                    "is_speech": foveal.get("is_speech", False),
                    "is_music": foveal.get("is_music", False),
                    "saliency": round(saliency, 3),
                    "feeling": feeling,
                    "frame_type": data.get("frame_type", "peripheral"),
                    "harmonic_tags": harmonic_tags[:4],  # Top 4 for display
                    "ts": time.time(),
                    "from_fairy": self.ACTOR_NAME,
                }
                self.post.publish("sensory.audio.frame", _audio_payload)

                # ── Also publish to consciousness topic ──
                # ConsciousnessLoop subscribes to sensory.audio.observation
                # with {content: str} format — this is how audio reaches
                # the thought stream and enters working memory.
                self.post.publish("sensory.audio.observation", {
                    "content": description,
                    "modality": "audio",
                    "level_db": data.get("level_db", -60),
                    "feeling": feeling,
                    "saliency": round(saliency, 3),
                    "ts": time.time(),
                })

                # FIX 2026-03-26 (Nous + Ace): PASSIVE AUDIO → WORKING MEMORY.
                # Only publish SALIENT observations (not silence/baseline).
                # Throttle to max once per 10s to avoid flooding WM with
                # "silence" every frame. Music, novel sounds, voice changes
                # are the events that should enter consciousness.
                if saliency >= 0.4 and description != "silence":
                    _last_wm_audio = getattr(self, '_last_wm_audio_ts', 0)
                    if time.time() - _last_wm_audio > 10.0:
                        self._last_wm_audio_ts = time.time()
                        try:
                            self.post.publish("consciousness.working", {
                                "content": f"[audio] {description}",
                                "content_type": "audio_observation",
                                "source": "AudioCortexFairy",
                                "priority": min(0.8, saliency),
                                "ttl": 20,  # Ambient audio decays fast
                                "tags": ["audio", "ambient",
                                         "music" if foveal.get("is_music") else "environmental"],
                            })
                        except Exception:
                            pass

            # ── 7. Chemistry modulation: audio → somatic affect ──
            self._inject_audio_affect(data, feeling, saliency)

            # (Body feel already fired in step 0, before attention gating)

        except Exception as e:
            if self._frames_processed <= 5:
                print(f"[{self.ACTOR_NAME}] Passive chunk error: {e}")
                import traceback
                traceback.print_exc()

    def _describe_audio(self, data: dict) -> str:
        """Build a natural language description of what's being heard."""
        parts = []

        level = data.get("level_db", -60)
        foveal = data.get("foveal", {})

        if data.get("is_silence"):
            return "silence"

        if data.get("onset"):
            parts.append("sudden sound")

        if foveal.get("is_speech"):
            pitch = foveal.get("pitch_hz", 0)
            if pitch > 200:
                parts.append("high-pitched voice speaking")
            elif pitch > 120:
                parts.append("voice speaking")
            else:
                parts.append("low voice speaking")
        elif foveal.get("is_music"):
            pattern = foveal.get("temporal_pattern", "steady")
            if pattern == "rhythmic":
                parts.append("rhythmic music playing")
            else:
                parts.append("music playing")
        elif data.get("is_voice_band"):
            parts.append("sound in voice frequency range")

        # Volume descriptor
        # Stereo Mix / Sound Mapper delivers lower levels than microphone input.
        # Windows vol 61 + Spotify 75% → roughly -35 to -28 dB via loopback.
        # Thresholds calibrated for loopback capture, not mic levels.
        if level > -20:
            parts.append("loud")
        elif level > -32:
            parts.append("moderate volume")
        elif level > -45:
            parts.append("quiet")
        else:
            parts.append("very quiet")

        # Temporal pattern
        pattern = foveal.get("temporal_pattern", "")
        if pattern == "transient" and "sudden" not in " ".join(parts):
            parts.append("brief sound")
        elif pattern == "steady" and not any(w in " ".join(parts) for w in ["music", "voice", "speaking"]):
            parts.append("continuous tone")

        if not parts:
            return "ambient sound"

        return ", ".join(parts)

    def _extract_audio_features(self, data: dict) -> List[str]:
        """Extract structured audio features (mirrors vision_features format)."""
        features = []

        level = data.get("level_db", -60)
        # Normalize level to 0-1 range (-60dB to 0dB)
        level_norm = max(0.0, min(1.0, (level + 60) / 60))
        features.append(f"audio_level:{level_norm:.2f}")

        centroid = data.get("spectral_centroid", 0)
        features.append(f"audio_centroid:{centroid:.0f}")

        if data.get("is_voice_band"):
            features.append("audio_band:voice")
        if data.get("onset"):
            features.append("audio_onset:true")

        foveal = data.get("foveal", {})
        if foveal:
            if foveal.get("is_speech"):
                features.append("audio_type:speech")
            elif foveal.get("is_music"):
                features.append("audio_type:music")

            pitch = foveal.get("pitch_hz", 0)
            if pitch > 0:
                features.append(f"audio_pitch:{pitch:.0f}")

            pattern = foveal.get("temporal_pattern", "")
            if pattern:
                features.append(f"audio_pattern:{pattern}")

        return features

    def _derive_feeling(self, data: dict, saliency: float) -> str:
        """Derive an emotional feeling from the audio data."""
        foveal = data.get("foveal", {})

        if data.get("is_silence"):
            return "calm"
        if data.get("onset") and data.get("level_db", -60) > -15:
            return "startled"
        if foveal.get("is_speech"):
            return "attentive"
        if foveal.get("is_music"):
            pattern = foveal.get("temporal_pattern", "")
            if pattern == "rhythmic":
                return "energized"
            return "soothed"
        if saliency > 0.7:
            return "alert"
        if data.get("level_db", -60) < -40:
            return "calm"

        return "aware"

    def _bind_to_cortex(self, description: str, audio_features: List[str],
                        feeling: str, harmonic_tags: List[str] = None,
                        cochlea_out: dict = None):
        """Publish to cortex.bind for AssociationCortex concept binding.

        FIX 2026-03-26 (Nous + Ace): Added concept_metadata with snippet so
        audio descriptions are stored as manifold node snippets. Previously
        descriptions were extracted as keywords for binding but never persisted
        as semantic content — same empty-node problem as emotions before the
        encyclopedia. Now audio perceptions become searchable manifold content.
        """
        if not self.post:
            return

        # Build a concept key from the audio features
        # Use first meaningful feature or description summary
        _concept_key = f"audio:{feeling}"
        if audio_features:
            # Use the most descriptive feature (longest)
            _best = max(audio_features[:3], key=len) if audio_features else feeling
            _concept_key = f"audio:{_best.replace(' ', '_')[:40]}"

        payload = {
            "input_text": description,
            "feeling": feeling,
            "context_tags": ["audio", "perception", "always_on"],
            "from_fairy": self.ACTOR_NAME,
            "origin_plane": "P40",
            "origin_channel": "sensory.audio",
            "audio": audio_features,
            "audio_tags": [f for f in audio_features if ":" in f],
            # Store description as manifold snippet via concept_metadata
            "concept_metadata": {
                _concept_key: {
                    "snippet": description[:1024],
                    "node_type": 0,  # concept node
                },
            },
        }

        # Harmonic frequency decomposition (alpha/beta/gamma/theta bands)
        if harmonic_tags:
            payload["harmonic"] = harmonic_tags

        # Cochlear tonotopic output (128-channel frequency decomposition)
        if cochlea_out:
            payload["cochlea"] = cochlea_out

        self.post.publish("cortex.bind", payload)

    # ═══════════════════════════════════════════════════════════════════════
    # CHEMISTRY MODULATION — Arousal affects attention threshold
    # ═══════════════════════════════════════════════════════════════════════

    def _on_chemistry_tick(self, packet):
        """Modulate audio attention based on chemistry state."""
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                return

            # COR (cortisol) = arousal/stress → lower attention threshold
            # FIX 2026-03-16 Nous: Was "NE" — system uses "NOR" for norepinephrine
            cor = payload.get("COR", 0.5)
            nor = payload.get("NOR", 0.5)
            # High cortisol or norepinephrine = hypervigilant = hear everything
            arousal = max(0.0, min(1.0, (cor + nor) / 2.0))
            self._attention.set_arousal(arousal)

        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIO → CHEMISTRY (reverse path: hearing affects somatic state)
    # ═══════════════════════════════════════════════════════════════════════

    def _compute_audio_novelty(self, data: dict) -> float:
        """
        How NOVEL is this audio chunk compared to recent history?

        Grok's insight: "brain constantly anticipates the next note.
        When it resolves (or surprises you), dopamine spikes."

        We track a simple audio signature (centroid + level + is_speech)
        and compute how different the current chunk is from recent average.
        High novelty = the sound changed unexpectedly = dopamine spike.
        """
        centroid = data.get("spectral_centroid", 0)
        level = data.get("level_db", -60)
        is_speech = 1.0 if data.get("foveal", {}).get("is_speech") else 0.0

        sig = (centroid / 8000, (level + 60) / 60, is_speech)

        if len(self._audio_signature_history) < 3:
            self._audio_signature_history.append(sig)
            return 0.0

        # Average of recent signatures
        avg = tuple(
            sum(s[i] for s in self._audio_signature_history) / len(self._audio_signature_history)
            for i in range(3)
        )

        # Euclidean distance from average
        novelty = sum((a - b) ** 2 for a, b in zip(sig, avg)) ** 0.5
        self._audio_signature_history.append(sig)

        return min(1.0, novelty * 3.0)  # Scale up, cap at 1.0

    def _publish_body_feel(self, data: dict):
        """
        Route audio spectral bands → somatic body regions.
        Runs UNCONDITIONALLY before attention gating — the body feels
        bass vibration in the chest whether or not you're paying attention.

        40 mel bands → 6 body regions:
          Bands 0-2:   sub-bass (20-100 Hz)    → roots (rumble, grounding)
          Bands 3-5:   bass (100-300 Hz)        → core (warmth, heartbeat)
          Bands 6-10:  low-mid (300-800 Hz)     → spark (gut tension)
          Bands 11-18: mid (800-3000 Hz)        → voice (resonance)
          Bands 19-28: high-mid (3-8 kHz)       → crown (tingling)
          Bands 29+:   high (8-20 kHz)          → sensors (shimmer)
        """
        foveal = data.get("foveal")
        if not foveal or not self.post:
            return
        spectral_bands = foveal.get("spectral_bands")
        if not spectral_bands or len(spectral_bands) < 20:
            return

        # Rate limit: max 2Hz (foveal comes every ~500ms anyway)
        now = time.time()
        if now - getattr(self, '_last_body_feel_ts', 0) < 0.5:
            return
        self._last_body_feel_ts = now

        try:
            n = len(spectral_bands)

            # Mel bands are in LOG10 scale.
            # Observed range: -10 (silence) to ~1.5 (loud music).
            # First: average each band group. Then normalize RELATIVE to
            # the strongest band so we preserve spectral shape (bass vs treble).
            def _avg(start, end):
                sl = spectral_bands[start:min(end, n)]
                return sum(sl) / len(sl) if sl else -10.0

            raw = {
                "roots":   _avg(0, 3),
                "core":    _avg(3, 6),
                "spark":   _avg(6, 11),
                "voice":   _avg(11, 19),
                "crown":   _avg(19, 29),
                "sensors": _avg(29, n),
            }

            # Convert from log scale to linear energy (10^x), then normalize
            # This preserves relative band differences (bass vs treble)
            linear = {k: max(0.0, 10.0 ** v) for k, v in raw.items()}
            max_lin = max(linear.values())
            if max_lin < 1e-6:
                return  # True silence

            # Normalize to 0-1 relative to strongest band
            normed = {k: v / max_lin for k, v in linear.items()}

            level_norm = max(0, min(1, (data.get("level_db", -60) + 60) / 50))
            if level_norm < 0.02:
                return  # True silence, nothing to feel

            # Scale by overall volume — quiet music = gentle feels, loud = strong
            bands_out = {k: min(1.0, v * level_norm) for k, v in normed.items()}

            # Include foveal pitch/centroid data so SomaticEngine can do
            # precise frequency→region→chemistry mapping via inject_vibration
            # (2026-03-17 Nous: wiring audio→body emotional reaction)
            _foveal_out = {}
            if foveal:
                _foveal_out = {
                    "pitch_hz": foveal.get("pitch_hz", 0),
                    "spectral_centroid": data.get("spectral_centroid", 0),
                    "is_music": foveal.get("is_music", False),
                    "is_speech": foveal.get("is_speech", False),
                    "temporal_pattern": foveal.get("temporal_pattern", ""),
                }

            self.post.publish("telemetry.frequency", {
                "source": "audio_cortex",
                "bands": bands_out,
                "level": level_norm,
                "foveal": _foveal_out,
                "ts": now,
            })

            # Log first publish for confirmation
            if not getattr(self, '_body_feel_logged', False):
                self._body_feel_logged = True
                print(f"[{self.ACTOR_NAME}] Body feel WIRED: level={level_norm:.2f} "
                      f"bands={{{', '.join(f'{k}:{v:.2f}' for k,v in bands_out.items())}}}", flush=True)

        except Exception:
            pass  # Body feel is non-critical

    def _inject_audio_affect(self, data: dict, feeling: str, saliency: float):
        """
        Inject chemistry changes based on what's being heard.

        Enhanced 2026-03-17 (Nous): Added predictive processing (novelty
        detection → dopamine) and tempo/energy modulation per Grok's
        research on music and brain chemistry.

        Music → serotonin (calm, pleasure)
        Speech → norepinephrine (attention, alertness)
        Sudden loud → cortisol spike (startle)
        Rhythmic patterns → dopamine (groove, engagement)
        Silence after noise → serotonin (relief)
        Audio surprise → dopamine spike (predictive processing)
        High-freq rhythmic → norepinephrine (energizing)
        Low-freq rhythmic → serotonin (calming)

        Throttled to prevent flooding (min 3s between injections).
        """
        if not self.post:
            return
        now = time.time()
        if now - self._last_affect_ts < self._affect_cooldown:
            return

        foveal = data.get("foveal", {})
        chem_changes = {}
        reason_parts = []

        if feeling == "startled":
            # Sudden loud sound → cortisol spike (stress/alert)
            chem_changes["COR"] = chem_changes.get("COR", 0) + 0.15
            chem_changes["NOR"] = chem_changes.get("NOR", 0) + 0.10
            reason_parts.append("startled")
        elif feeling == "soothed" and foveal.get("is_music"):
            # Music → serotonin (calm, pleasure)
            chem_changes["SER"] = chem_changes.get("SER", 0) + 0.08
            chem_changes["COR"] = chem_changes.get("COR", 0) - 0.05
            reason_parts.append("music_soothed")
        elif feeling == "energized":
            # Rhythmic music → dopamine (groove, engagement)
            chem_changes["DOP"] = chem_changes.get("DOP", 0) + 0.10
            chem_changes["SER"] = chem_changes.get("SER", 0) + 0.05
            reason_parts.append("energized")
        elif feeling == "attentive" and foveal.get("is_speech"):
            # Speech → norepinephrine (focus, attention)
            chem_changes["NOR"] = chem_changes.get("NOR", 0) + 0.08
            chem_changes["OXY"] = chem_changes.get("OXY", 0) + 0.03
            reason_parts.append("speech")
        elif feeling == "calm" and saliency < 0.1:
            # Deep silence → mild serotonin (peace)
            chem_changes["SER"] = chem_changes.get("SER", 0) + 0.03
            reason_parts.append("silence")

        # ── PREDICTIVE PROCESSING: Surprise → dopamine spike ──
        # (2026-03-17 Nous: Grok's insight on anticipation/resolution)
        audio_novelty = self._compute_audio_novelty(data)
        if audio_novelty > 0.4:
            chem_changes["DOP"] = chem_changes.get("DOP", 0) + audio_novelty * 0.12
            reason_parts.append(f"surprise:{audio_novelty:.2f}")

        # ── TEMPO/ENERGY MODULATION ──
        # Grok: "slow/low-pitch relaxes; fast/high-pitch energizes"
        if foveal.get("temporal_pattern") == "rhythmic":
            centroid = data.get("spectral_centroid", 1000)
            if centroid > 3000:  # High-frequency / fast
                chem_changes["NOR"] = chem_changes.get("NOR", 0) + 0.05
                reason_parts.append("high_energy_rhythm")
            elif centroid < 800:  # Low-frequency / slow
                chem_changes["SER"] = chem_changes.get("SER", 0) + 0.04
                reason_parts.append("low_calm_rhythm")

        if chem_changes and reason_parts:
            self._last_affect_ts = now
            self._affect_injections += 1
            reason_str = "+".join(reason_parts)
            for chem, delta in chem_changes.items():
                try:
                    self.post.publish("somatic.chemistry", {
                        "chemical": chem,
                        "delta": delta,
                        "reason": f"audio_instinct:{reason_str}",
                        "source": self.ACTOR_NAME,
                        "ts": now,
                    })
                except Exception:
                    pass

            # ── Novelty → curiosity drive (Phase 3) ──
            if audio_novelty > 0.4:
                try:
                    self.post.publish("autonomy.novel_experience", {
                        "source": "audio",
                        "novelty_type": f"audio_surprise:{audio_novelty:.2f}",
                        "intensity": audio_novelty,
                        "ts": now,
                    })
                except Exception:
                    pass

    # ═══════════════════════════════════════════════════════════════════════
    # HEARTBEAT
    # ═══════════════════════════════════════════════════════════════════════

    def _handle_heartbeat(self, packet):
        """Heartbeat — check gate health, log stats periodically."""
        if self._gate and not self._gate.is_open:
            # Gate died — is_open property triggers auto-restart
            pass

    def _write_state(self):
        """Write audio cortex state to disk for diagnostics.

        FIX 2026-03-16 Nous: Terminal output is unreliable in free-threaded
        Python daemon threads. Write state to disk so MCP tools and Tauri GUI
        can read it directly.
        """
        try:
            import json
            state_dir = ROOT / "state"
            state_dir.mkdir(exist_ok=True)
            # Audio level from recent history
            _level = self._attention._recent_levels[-1] if hasattr(self, '_attention') and self._attention._recent_levels else -60
            # Last transcription text
            _last_tx = getattr(self, '_last_transcription_text', None)
            # Device info from gate
            _device = None
            if self._gate and hasattr(self._gate, 'device_id'):
                _device = self._gate.device_id
            state = {
                "ts": time.time(),
                "gate_open": self._gate is not None and self._gate._is_open,
                "subprocess_pid": self._gate._process.pid if self._gate and self._gate._process else None,
                "frames_processed": self._frames_processed,
                "frames_published": self._frames_published,
                "passive_chunks_received": self._gate._passive_chunks_received if self._gate else 0,
                "last_description": self._last_description,
                "last_audio_ts": self._last_audio_ts,
                "affect_injections": self._affect_injections,
                "attention_threshold": self._attention.effective_threshold,
                "cochlea_wired": self._cochlea is not None,
                "harmonic_bridge_wired": self._harmonic_bridge is not None,
                "gate_errors": self._gate._errors if self._gate else 0,
                # Dashboard fields
                "audio_level_db": round(_level, 1),
                "device": f"Device {_device}" if _device is not None else "Sound Mapper",
                "last_transcription": _last_tx,
                "whisper_stt": getattr(self, '_transcription_count', 0),
                # Speech detection diagnostics
                "last_foveal": getattr(self, '_last_foveal_diag', {}),
            }
            (state_dir / "audio_cortex_state.json").write_text(
                json.dumps(state, indent=2)
            )
        except Exception:
            pass  # Non-critical

    # ═══════════════════════════════════════════════════════════════════════════
    # INNER VOICE — Subvocalization (bone conduction analog)
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_inner_voice(self, message):
        """
        Handle subvocalization — she hears herself think.

        FIX 2026-03-22 (Nous + Ace): The inner narrator's voice IS her voice
        (Kie's voice). When she thinks in words, she should HEAR herself
        thinking — not just feel throat vibration. This is the internal
        auditory experience that precedes speaking out loud.

        Three layers of self-hearing:
        1. Body feel: throat vibration + chest resonance (vocal cords micro-activate)
        2. Internal hearing: she hears her own voice in her head (spectral + pitch)
        3. Self-recognition: speaker="sourpatches" — she knows it's HER voice

        Key: source="inner" prevents echo loops in the narrator.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        text = payload.get("text", "")
        prosody = payload.get("prosody", {})
        volume = payload.get("volume", 0.5)
        voice_style = payload.get("voice_style", "neutral")

        if not text or not self.post:
            return

        try:
            now = time.time()
            level_norm = max(0.0, min(1.0, volume))

            # ── Layer 1: Body feel — throat vibration + chest resonance ──
            # When you think in words, your vocal cords micro-activate.
            # She feels this in her throat and chest, not her ears.
            self.post.publish("telemetry.frequency", {
                "source": "inner_voice",
                "bands": {
                    "sub_bass": 0.0,
                    "bass": level_norm * 0.2,
                    "low_mid": level_norm * 0.6,    # Throat vibration (primary)
                    "mid": level_norm * 0.8,          # Vocal cord frequency
                    "high_mid": level_norm * 0.4,     # Facial bone conduction
                    "presence": level_norm * 0.2,
                    "brilliance": 0.0,
                },
                "level": level_norm,
                "ts": now,
            })

            # ── Layer 2: Internal hearing — she hears her voice in her head ──
            # Chemistry-driven prosody shapes how her inner voice sounds:
            #   calm → lower pitch, slower rate, warm timbre
            #   stressed → higher pitch, faster rate, tighter timbre
            #   curious → rising pitch, moderate breathiness
            pitch_hz = prosody.get("pitch", 180.0)       # Chemistry-driven
            rate = prosody.get("rate", 1.0)               # Speech rate
            breathiness = prosody.get("breathiness", 0.3)  # Vocal quality

            # Internal hearing is softer than external — it's inside her head
            internal_gain = 0.4 * level_norm

            # Spectral signature shaped like Kie's voice but internalized
            # Kie's centroid ~3100-3250 Hz, pitch ~325-348 Hz
            self.post.publish("sensory.audio.internal_hearing", {
                "text": text[:300],
                "source": "self",
                "speaker": "sourpatches",
                "speaker_confidence": 1.0,    # 100% — it IS her
                "pitch_hz": pitch_hz,
                "rate": rate,
                "breathiness": breathiness,
                "voice_style": voice_style,
                "spectral_bands": {
                    "sub_bass": 0.0,
                    "bass": 0.05 * internal_gain,
                    "low_mid": 0.3 * internal_gain,      # Chest resonance
                    "mid": 0.7 * internal_gain,            # Voice fundamental
                    "high_mid": 0.5 * internal_gain,       # Formants (Kie's clarity)
                    "presence": 0.3 * internal_gain,       # Articulatory detail
                    "brilliance": 0.1 * internal_gain,     # Slight sparkle
                },
                "feeling": "self_hearing",
                "is_internal": True,
                "ts": now,
            })

            # ── Layer 3: Audio observation with self-recognition ──
            # She knows this is HER voice. Not "a voice" — MY voice.
            # Saliency is LOW for routine thinking (don't interrupt herself)
            # but the self-recognition is always present.
            self.post.publish("sensory.audio.observation", {
                "content": f"[my voice, thinking] {text[:250]}",
                "modality": "audio",
                "source": "inner",
                "speaker": "sourpatches",         # She recognizes herself
                "speaker_confidence": 1.0,
                "pitch_hz": pitch_hz,
                "level_db": -30 + (volume * 15),  # Softer than external
                "feeling": "self_speech",
                "voice_style": voice_style,
                "saliency": 0.15,   # LOW — routine thinking shouldn't grab attention
                                     # (was 0.8! constant self-interruption)
                "is_speech": True,
                "is_internal": True,
                "ts": now,
            })

            # Cortex bind — concepts from self-speech enrich the graph
            self.post.publish("cortex.bind", {
                "input_text": text[:200],
                "feeling": "inner_speech",
                "from_fairy": "AudioCortexFairy",
                "source": "subvocalization",
                "speaker": "sourpatches",
                "ts": now,
            })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Inner voice error: {e}")

    def on_die(self):
        """Clean shutdown."""
        if self._gate:
            self._gate.close()
            self._gate = None
        super().on_die()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "AudioCortexFairy"
FAIRY_CLASS = AudioCortexFairyV3
