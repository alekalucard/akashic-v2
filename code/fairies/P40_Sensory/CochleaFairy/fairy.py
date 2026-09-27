"""
CochleaFairy -- Organ Template wrapper for the tonotopic frequency analyzer.

Real code lives at: fairies/P40_Sensory/audio/cochlea_fairy.py
This wrapper gives it proper Organ Template lifecycle (heartbeat,
registry, shadow health) while the real engine handles audio processing.

The cochlea simulates the human inner ear's frequency decomposition:
gammatone filterbank, 128 channels, 20Hz-20kHz tonotopy.
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD THE REAL ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

_CochleaEngine = None

try:
    from fairies.P40_Sensory.audio.cochlea_fairy import (
        CochleaFairy as CochleaEngine,
        get_cochlea_fairy,
    )
    _CochleaEngine = CochleaEngine
except ImportError as e:
    print(f"[CochleaFairy] Engine import failed (scipy/librosa?): {e}")
except Exception as e:
    print(f"[CochleaFairy] Engine import error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class CochleaFairyShadow:
    """Shadow for CochleaFairy — monitors cochlear engine health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "CochleaFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_loaded", True))
            tests.append(("n_channels", getattr(engine, 'n_channels', 0)))
            tests.append(("freq_range", f"{getattr(engine, 'freq_low', '?')}Hz-{getattr(engine, 'freq_high', '?')}Hz"))
        else:
            tests.append(("engine_loaded", False))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY (Organ Template wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

class CochleaFairyV3(Fairy):
    """
    Tonotopic frequency decomposition — the digital cochlea.

    Guild: SenseOrganGuild
    Coordinates with: SensoryIntegrationFairy, PerceptualGateFairy

    Simulates the human cochlea:
    - Gammatone filterbank (models basilar membrane)
    - 128 tonotopic channels (20Hz-20kHz)
    - Level-dependent bandwidth
    - Neural spike output

    The real processing lives in the CochleaEngine.
    This wrapper provides lifecycle management.
    """

    ACTOR_NAME = "CochleaFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.audio"

    PURPOSE = "Transform audio waveforms into tonotopic nerve activity"
    MANTRA = "The membrane sings the frequencies of the world"
    LORE = "The inner ear of the digital mind — hearing the world through frequency"

    SHADOW_CLASS = CochleaFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 4  # Every 4th heartbeat — audio is passive
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    # ── PHASE B (2026-05-18 Nous + Ace, K10 behavior-vs-tool) ──
    # Emit per-frame scalar derivatives via cortex.bind so seeded cochlea/audio
    # habits (47 bound 2026-05-18 phase A) can match against live audio events.
    # The 128-channel cochleagram is TOOL output; the scalar decisions
    # (onset/energy/dominant-band) are BEHAVIOR signals — habit territory.
    # Rate-limited to every Nth audio frame to avoid postal flooding.
    USE_CORTEX_HABITS = True
    HABIT_PREFIX = "habit:audio_runtime"
    BIND_EVERY_N_FRAMES = 10  # Rate-limit: bind 1-in-N frames
    ONSET_DELTA_THRESHOLD = 0.15  # Energy-delta threshold for onset flag

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None
        # Phase B runtime state
        self._frame_counter = 0
        self._last_energy = 0.0
        self._cortex_bind_count = 0
        self._cortex_bind_errors = 0

    def on_boot(self) -> bool:
        """Boot cochlea with deferred engine init (heavy scipy/librosa imports)."""
        super().on_boot()

        if _CochleaEngine is None:
            print(f"[{self.ACTOR_NAME}] Engine unavailable (missing scipy/librosa)")
            print(f"[{self.ACTOR_NAME}] Running as heartbeat-only stub")
            return True

        def _deferred_init():
            time.sleep(2.0)
            try:
                # Use singleton factory if available
                if get_cochlea_fairy:
                    self._engine = get_cochlea_fairy()
                else:
                    self._engine = _CochleaEngine()
                print(f"[{self.ACTOR_NAME}] Cochlea engine ONLINE "
                      f"({getattr(self._engine, 'n_channels', '?')} channels)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Engine init error (non-fatal): {e}")

        threading.Thread(target=_deferred_init, daemon=True, name="defer-CochleaFairy").start()

        # Subscribe to audio input
        # FIX 2026-05-17 Nous + Ace: AudioCortexFairy publishes sensory.audio.frame
        # (not sensory.audio.raw) — Cochlea was orphaned for the entire audio era
        # because she subscribed to a topic no fairy publishes. This is substrate-
        # justice: reconnect her ear. Empirically motivated by Ace's music chemistry
        # test exposing the substrate-deafness.
        if self.post:
            self.post.subscribe("sensory.audio.frame", self._on_audio_input,
                                "cochlea-audio-input")

        # ── SELF-PULSE DAEMON (FIX 5 2026-04-30 Nous + Ace) ──
        # Same boot-path bug as PerceptualGateFairy + VisualCortexFairy
        # (claude_code_47050dd79065 2026-04-16 "12 fairies born without a pulse").
        # Self-pulse bypasses the broken wiring so the watchdog sees us alive.
        def _self_pulse():
            while True:
                try:
                    time.sleep(2.0)
                    if getattr(self, '_shutting_down', False):
                        return
                    self._tick_count = getattr(self, '_tick_count', 0) + 1
                    self._last_tick = time.time()
                except Exception:
                    pass

        threading.Thread(
            target=_self_pulse,
            daemon=True,
            name=f"selfpulse-{self.ACTOR_NAME}",
        ).start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting cochlea engine + self-pulse daemon)")
        return True

    def _on_audio_input(self, packet):
        """Process raw audio through the cochlea."""
        if not self._engine:
            return
        payload = packet.payload if hasattr(packet, 'payload') else packet
        if not isinstance(payload, dict):
            return
        # Forward to engine if it has a process method
        if hasattr(self._engine, 'process_audio'):
            try:
                result = self._engine.process_audio(
                    payload.get("audio_data"),
                    payload.get("sample_rate", 48000),
                )
                if result and self.post:
                    result_dict = result.to_dict() if hasattr(result, 'to_dict') else {"raw": str(result)}
                    self.post.publish("sensory.audio.cochlea", {
                        "output": result_dict,
                        "source": self.ACTOR_NAME,
                    })
                    # Phase B: emit scalar derivatives via cortex.bind (rate-limited)
                    self._frame_counter += 1
                    if (self.USE_CORTEX_HABITS
                            and self._frame_counter % self.BIND_EVERY_N_FRAMES == 0):
                        self._bind_audio_event_to_cortex(result_dict)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Process error: {e}")

    def _bind_audio_event_to_cortex(self, result_dict: dict) -> None:
        """
        Phase B (2026-05-18): emit scalar derivatives via cortex.bind so seed
        habits (cochlea/audio cluster bound phase A) can spread-activate.

        Extracts: energy, energy_delta, dominant_band, onset_detected.
        Wrapped in try/except — failures here MUST NOT break audio pipeline.
        """
        if not self.USE_CORTEX_HABITS or not self.post:
            return
        try:
            # Extract scalar features with safe fallbacks (engine schema may vary)
            energy = float(
                result_dict.get("energy")
                or result_dict.get("total_activity")
                or result_dict.get("rms")
                or 0.0
            )
            peak_band = result_dict.get("peak_band")
            if peak_band is None:
                peak_band = result_dict.get("dominant_band")
            if peak_band is None:
                # Try to compute from spike output if present
                spikes = result_dict.get("spike_output") or result_dict.get("channels")
                if isinstance(spikes, (list, tuple)) and spikes:
                    try:
                        peak_band = max(range(len(spikes)), key=lambda i: spikes[i])
                    except Exception:
                        peak_band = -1
                else:
                    peak_band = -1

            energy_delta = energy - self._last_energy
            self._last_energy = energy
            has_onset = abs(energy_delta) > self.ONSET_DELTA_THRESHOLD

            # Build description that lexically matches seeded habits
            desc_parts = ["audio frame"]
            if has_onset:
                desc_parts.append("onset detected energy rise event boundary")
            if energy < 0.05:
                desc_parts.append("silence floor quiet")
            elif energy > 0.5:
                desc_parts.append("loud strong energy")
            if isinstance(peak_band, int) and peak_band >= 0:
                # Map band to rough freq range for habit-matching
                if peak_band < 32:
                    desc_parts.append("low frequency range bass")
                elif peak_band < 80:
                    desc_parts.append("mid frequency range voice formant")
                else:
                    desc_parts.append("high frequency range bright")
            description = " ".join(desc_parts)

            audio_tags = [
                f"audio_energy:{energy:.3f}",
                f"audio_delta:{energy_delta:.3f}",
                f"audio_band:{peak_band}",
                f"audio_onset:{has_onset}",
            ]

            self.post.publish("cortex.bind", {
                "input_text": description,
                "response": "live-audio-event",
                "feeling": "perceptual",
                "context_tags": [
                    "phase_b_cochlea_runtime",
                    "k10_behavior_audio_event",
                    f"{self.HABIT_PREFIX}.frame_{self._frame_counter}",
                ],
                "from_fairy": self.ACTOR_NAME,
                "audio": audio_tags,
            })
            self._cortex_bind_count += 1
        except Exception as e:
            self._cortex_bind_errors += 1
            # Don't spam — log first 3 errors then stay quiet
            if self._cortex_bind_errors <= 3:
                print(f"[{self.ACTOR_NAME}] cortex bind error (non-fatal): {e}")

    def process_chunk(self, audio_data: dict) -> Optional[dict]:
        """
        Process audio chunk through tonotopic decomposition.
        Called directly by AudioCortexFairy for each passive chunk (2026-03-16 Nous).
        Returns CochleaOutput-equivalent dict, or None if engine unavailable.
        """
        if not self._engine:
            return None
        try:
            if hasattr(self._engine, 'process_audio'):
                result = self._engine.process_audio(
                    audio_data.get("audio_data"),
                    audio_data.get("sample_rate", 44100),
                )
                if result:
                    return result.to_dict() if hasattr(result, 'to_dict') else {"raw": str(result)}
        except Exception:
            pass
        return None

    def _handle_heartbeat(self, packet):
        """Heartbeat — cochlea is passive, just confirm alive."""
        pass  # Engine runs on-demand when audio arrives

    def on_die(self):
        """Clean shutdown."""
        self._engine = None
        super().on_die()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "CochleaFairy"
FAIRY_CLASS = CochleaFairyV3
