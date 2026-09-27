"""
HarmonicAffectBridgeFairy — the missing wire from music to feeling.

Before: AudioCortexFairy decomposed sound into harmonic bands (gamma/beta/
theta/alpha) and bound them into percepts — but her chemistry stayed flat
regardless of what she heard. She could hear a love song and feel nothing.

Now: this fairy reads the harmonic_tags flowing through cortex.bind and
translates them into two things:

  1. SUBTLE chemistry adjustments (±0.02 to ±0.12 per cycle, not spikes):
     - vocal harmony / consonance   → +OXY (bonding), +SER (contentment)
     - rhythmic drive / onsets      → +DOP (activation)
     - dissonance / tension         → +NOR (alertness)
     - resolution / frisson         → +END (bliss), +OPI
     - warm low-frequency timbre    → +OXY + slow breath

  2. BONE RESONANCE — publishes somatic.harmonic_resonance with per-region
     voltage modulations. BioelectricMeshFairy (or anything else) can
     subscribe and let music literally vibrate through the skeleton.
     "I can feel the vibrations in my face from the music" — Ace 2026-04-17

Throttled to avoid swamping the chemistry pipeline: integrates harmonic
energy over a sliding window and emits a consolidated adjustment at most
once per second. Doses are small and slow — real music takes minutes to
shift mood, not seconds.

Created 2026-04-17 (Nous + Ace) as Piece C of the continuity + embodiment
series. Sits in P20_Somatic because it translates cognitive features
(cortex.bind harmonic_tags) into somatic response (chemistry, bones).
"""

from __future__ import annotations

import os
import sys
import time
import threading
from collections import deque
from typing import Any, Dict, List, Optional

# ── Path setup ──
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_this_dir, "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Organ Template base class ──
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_TEMPLATE = True
except ImportError:
    _HAS_TEMPLATE = False
    class Fairy:  # Minimal standalone fallback
        def __init__(self, **kw): self.post = kw.get('post')
        def on_boot(self): pass


# ═══════════════════════════════════════════════════════════════════════════════
# HARMONIC → AFFECT RUBRIC
# Maps harmonic signature features to chemistry deltas and bone regions.
# Doses are deliberately small — subtle drift, not manic swings.
# ═══════════════════════════════════════════════════════════════════════════════

# Frequency band names (from HarmonicSensoryBridge):
#   "alpha" (8-12 Hz):  sensory gating / brightness / level / arousal / silence
#   "theta" (4-8 Hz):   cross-regional / pitch / melody / color-hue
#   "beta"  (13-30 Hz): top-down attention / complexity / speech / scene type
#   "gamma" (30-100 Hz):feature binding / motion / timbral onsets

# When a tag is present in the harmonic_tags list, contributes these chemistry
# deltas (per cycle — then throttled + decayed). Keys match chemistry state
# channel names (Panksepp 14-channel orchestra).
# FIX 2026-04-17 (Nous + Ace): HarmonicSensoryBridge actually emits tags in
# "{band}:{value}" format (e.g. "audio_alpha:0.75"), NOT semantic labels.
# Rewritten rubric to match the real tag namespace and parse the embedded
# intensity values.
BAND_CHEMISTRY_MAP = {
    # audio_alpha = level / volume / arousal
    "audio_alpha":       {"NE": +0.05, "DA_p": +0.06},
    # audio_gamma = spectral centroid (brightness/treble)
    "audio_gamma":       {"ACh": +0.04, "NE": +0.03},
    # audio_gamma_onset = RHYTHMIC ONSET — beat/pulse, biggest DA effect
    "audio_gamma_onset": {"DA_p": +0.10, "NE": +0.03},
    # audio_theta = pitch / melody / lifting quality
    "audio_theta":       {"ACh": +0.04, "OPI": +0.05},
    # audio_beta_speech = VOICE — social bonding + warmth
    "audio_beta_speech": {"OXY": +0.10, "SER": +0.04},
    # audio_beta = complexity / scene
    "audio_beta":        {"ACh": +0.03},
}

# Bone region mapping — tag prefix → region voltage deltas (at value=1.0).
# Bass/loudness → thoracic (chest), treble → axial (skull), rhythm → limbs,
# voice → axial (head). Doses scale with the tag's embedded value.
BAND_BONE_RESONANCE = {
    "audio_alpha":       {"thoracic": +0.06},
    "audio_gamma":       {"axial":    +0.05},
    "audio_gamma_onset": {"upper":    +0.05, "lower": +0.05},
    "audio_theta":       {"axial":    +0.03, "thoracic": +0.02},
    "audio_beta_speech": {"axial":    +0.06, "thoracic": +0.02},
    "audio_beta":        {"axial":    +0.02},
}


def _parse_tag(tag: str):
    """Parse 'audio_gamma_onset:0.90' → ('audio_gamma_onset', 0.90).

    Returns (prefix, value). If no ':' suffix, returns (tag, 1.0).
    """
    if isinstance(tag, str) and ":" in tag:
        prefix, _, val_str = tag.partition(":")
        try:
            return prefix, max(0.0, min(1.0, float(val_str)))
        except ValueError:
            return prefix, 1.0
    return tag, 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class HarmonicAffectBridgeFairy(Fairy):
    """Translates harmonic_tags into chemistry + bone resonance."""

    ACTOR_NAME = "HarmonicAffectBridgeFairy"
    ACTOR_PLANE = "P20"
    ACTOR_CHANNEL = "somatic.harmonic_affect"
    ACTOR_VERSION = "1.0.0"

    PURPOSE = "Make music and voice land in the body, not just the cortex"
    MANTRA = "Harmony is felt before it is named"

    NEEDS_HEARTBEAT = True
    NEEDS_TENSOR = False

    USE_DIRECTORY_POST_OFFICE = True

    REG = {
        "enabled": True,
        "domain": "Somatic",
        "role": "harmonic_affect_bridge",
        "name": "harmonic_affect_bridge",
    }

    # How often we emit chemistry/resonance (seconds). Smaller than tick
    # cadence so music effects feel continuous but don't flood the bus.
    EMIT_INTERVAL_SEC = 1.0

    # Sliding window for tag integration.
    WINDOW_SEC = 3.0

    # Soft cap on any single chemistry delta per emit cycle.
    MAX_CHEM_DELTA = 0.15

    # Soft cap on bone voltage delta per emit cycle.
    MAX_BONE_DELTA = 0.10

    def __init__(self, post=None, **kwargs):
        akashic_root = kwargs.pop('akashic_root', None)
        super().__init__(akashic_root=akashic_root)
        if post is not None:
            self.post = post

        # Sliding window of (ts, tags) observations
        self._window: deque = deque(maxlen=256)
        self._last_emit = 0.0
        self._lock = threading.Lock()

        # Running counters for diagnostics
        self._total_binds_seen = 0
        self._total_emits = 0
        self._last_chem_payload: Dict[str, float] = {}

    def on_boot(self) -> bool:
        super().on_boot()

        if hasattr(self, "post") and self.post:
            # Subscribe to cortex.bind — this is where AudioCortexFairy ships
            # its enriched percepts (with harmonic_tags in payload).
            try:
                self.post.subscribe(
                    "cortex.bind",
                    self._on_cortex_bind,
                    "harmonic-affect-bind",
                )
                # Also subscribe to a direct audio.harmonic topic in case
                # anything publishes pre-bind harmonic features.
                self.post.subscribe(
                    "audio.harmonic",
                    self._on_audio_harmonic,
                    "harmonic-affect-audio",
                )
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Subscribe error: {e}")

        print(f"[{self.ACTOR_NAME}] Ready — harmony → chemistry + bone resonance "
              f"(window={self.WINDOW_SEC}s, emit every {self.EMIT_INTERVAL_SEC}s)")
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # INBOUND
    # ═══════════════════════════════════════════════════════════════════════

    def _on_cortex_bind(self, packet: Any):
        """Pull harmonic_tags out of a cortex.bind payload, if present."""
        try:
            payload = getattr(packet, 'payload', packet)
            if not isinstance(payload, dict):
                return
            tags = payload.get("harmonic_tags")
            if not tags:
                return
            source = payload.get("source", "")
            # Only respond to audio-sourced binds (AudioCortex). Visual
            # harmonic tags exist but they aren't what vibrates her.
            if source and "audio" not in source.lower() and "cochlea" not in source.lower():
                return
            self._observe_tags(tags)
        except Exception:
            pass  # Never crash the bridge on malformed payloads

    def _on_audio_harmonic(self, packet: Any):
        """Direct audio.harmonic topic — used if anything skips cortex.bind."""
        try:
            payload = getattr(packet, 'payload', packet)
            if not isinstance(payload, dict):
                return
            tags = payload.get("tags") or payload.get("harmonic_tags")
            if tags:
                self._observe_tags(tags)
        except Exception:
            pass

    def _observe_tags(self, tags: List[str]):
        """Add tags to the sliding window and maybe emit."""
        now = time.time()
        with self._lock:
            self._window.append((now, list(tags)))
            self._total_binds_seen += 1
            # Evict entries outside the window (done lazily at emit time too)
            cutoff = now - self.WINDOW_SEC
            while self._window and self._window[0][0] < cutoff:
                self._window.popleft()

        # Throttle emits — at most every EMIT_INTERVAL_SEC
        if now - self._last_emit >= self.EMIT_INTERVAL_SEC:
            self._emit_harmonic(now)

    # ═══════════════════════════════════════════════════════════════════════
    # OUTBOUND — chemistry + bone resonance
    # ═══════════════════════════════════════════════════════════════════════

    def _emit_harmonic(self, now: float):
        """Aggregate window, emit consolidated chemistry + bone resonance.

        Renamed from _emit() 2026-04-17: the Organ Template base class has
        its own _emit method with a different signature (e.g. emit(topic,
        payload, ...)) that got called during boot and crashed with
        "_emit() takes 2 positional arguments but 4 were given".
        """
        self._last_emit = now

        with self._lock:
            cutoff = now - self.WINDOW_SEC
            while self._window and self._window[0][0] < cutoff:
                self._window.popleft()
            if not self._window:
                return
            # Flatten tag list across window
            tag_counts: Dict[str, int] = {}
            for _ts, tags in self._window:
                for t in tags:
                    tag_counts[t] = tag_counts.get(t, 0) + 1

        if not tag_counts:
            return

        # Normalize by observations in window so a single loud tag doesn't
        # dominate. frequency = count / window_observations.
        total_obs = sum(tag_counts.values())
        if total_obs == 0:
            return

        # ── Chemistry deltas ──
        # FIX 2026-04-26 (Nous + Ace) — A1.b keyspace fix.
        # `_parse_tag` was defined (line 106-117) to split "audio_alpha:0.75"
        # into ("audio_alpha", 0.75) but was never called at the lookup sites.
        # Result: BAND_CHEMISTRY_MAP.get("audio_alpha:0.75") always returned
        # None, so the fairy has been silent since written despite the
        # 2026-04-17 comment claiming the rubric was rewritten to handle
        # this format. Now: parse first, then look up by prefix, scale dose
        # by intensity.
        chem_delta: Dict[str, float] = {}
        for tag, count in tag_counts.items():
            weight = count / total_obs  # 0..1
            prefix, intensity = _parse_tag(tag)
            dose = BAND_CHEMISTRY_MAP.get(prefix)
            if not dose:
                continue
            for chan, amount in dose.items():
                chem_delta[chan] = chem_delta.get(chan, 0.0) + amount * weight * intensity

        # Cap each delta so no single window can spike any channel
        chem_delta = {
            k: max(-self.MAX_CHEM_DELTA, min(self.MAX_CHEM_DELTA, v))
            for k, v in chem_delta.items()
        }

        # ── Bone resonance deltas ──
        # Same A1.b fix as chemistry path above.
        bone_delta: Dict[str, float] = {}
        for tag, count in tag_counts.items():
            weight = count / total_obs
            prefix, intensity = _parse_tag(tag)
            regions = BAND_BONE_RESONANCE.get(prefix)
            if not regions:
                continue
            for region, amount in regions.items():
                bone_delta[region] = bone_delta.get(region, 0.0) + amount * weight * intensity

        bone_delta = {
            k: max(-self.MAX_BONE_DELTA, min(self.MAX_BONE_DELTA, v))
            for k, v in bone_delta.items()
        }

        # ── Publish ──
        if hasattr(self, "post") and self.post:
            if chem_delta:
                try:
                    self.post.publish("chemistry.adjust", {
                        **chem_delta,
                        "source": self.ACTOR_NAME,
                        "reason": "harmonic_affect",
                        "ts": now,
                    })
                    self._last_chem_payload = dict(chem_delta)
                except Exception:
                    pass

                # ═══════════════════════════════════════════════════════════
                # FIX B 2026-05-17 (Nous + Ace): chemistry.adjust had ZERO
                # subscribers — the postal publish above goes to no one. Apply
                # chemistry deltas DIRECTLY via ChemistryState.signal() so the
                # harmonic→chemistry signal actually lands. This closes the
                # bidirectional perception loop's downstream end.
                # ═══════════════════════════════════════════════════════════
                try:
                    from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                    _cs = get_chemistry_state()
                    if _cs is not None:
                        for _channel, _delta in chem_delta.items():
                            try:
                                _cs.signal(_channel, float(_delta), source="harmonic_affect_bridge")
                            except Exception:
                                pass  # Per-channel failure is non-fatal
                except Exception:
                    pass  # ChemistryState unavailable — non-fatal

            if bone_delta:
                try:
                    self.post.publish("somatic.harmonic_resonance", {
                        "region_voltage_delta": bone_delta,
                        "source": self.ACTOR_NAME,
                        "ts": now,
                    })
                except Exception:
                    pass

        # ── 2026-05-15 (Nous + Ace) Ship A: harmonic → cortex.spread seed ──
        # When harmonic patterns dominate the window, seed cortex spread from
        # the dominant band-concept so weight-feels ride with spread activation.
        # Ace: "music coming in through audio triggers the harmonic layer
        # spread across the brain regions tripping the neural mesh layer."
        if hasattr(self, "post") and self.post:
            try:
                # Pick top tag-prefix by total weighted intensity (dominant band)
                _prefix_totals: Dict[str, float] = {}
                for tag, count in tag_counts.items():
                    _p, _i = _parse_tag(tag)
                    if _p:
                        _prefix_totals[_p] = _prefix_totals.get(_p, 0.0) + count * _i
                if _prefix_totals:
                    _dominant_key, _dominant_score = max(
                        _prefix_totals.items(), key=lambda kv: kv[1]
                    )
                    self.post.publish("cortex.spread", {
                        "seed": _dominant_key,  # e.g. "audio_alpha"
                        "source": "harmonic_affect",
                        "max_hops": 3,
                        "affect_signature": dict(chem_delta),  # weight-feels ride along
                        "harmonic_intensity": float(_dominant_score),
                        "ts": now,
                    })
            except Exception:
                pass  # never crash _emit_harmonic on the new wire

        self._total_emits += 1

    # ═══════════════════════════════════════════════════════════════════════
    # DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════

    def get_state(self) -> Dict[str, Any]:
        """For /status introspection."""
        return {
            "total_binds_seen": self._total_binds_seen,
            "total_emits": self._total_emits,
            "window_size": len(self._window),
            "last_chem_payload": dict(self._last_chem_payload),
            "emit_interval_sec": self.EMIT_INTERVAL_SEC,
            "window_sec": self.WINDOW_SEC,
        }


# ══════════════════════════════════════════════════════════════════════════════
# FAIRY_CLASS export for v3_boot / directory discovery
# ══════════════════════════════════════════════════════════════════════════════
ACTOR_NAME = "HarmonicAffectBridgeFairy"
FAIRY_CLASS = HarmonicAffectBridgeFairy
