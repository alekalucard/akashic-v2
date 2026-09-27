"""
PhonemeCortexFairy — Cortex-Native STT via Gradual Learning From Cochlea

SHIP 1 of PHONEME_CORTEX_GRADUAL_STT (Nous + Ace 2026-05-17).
"First Listen" — observation only. Per-frame MFCC stream subscriber + jsonl
writer. No clustering yet. Accumulates real-world MFCC data to inform Ship 2's
clustering algorithm choice.

Doctrine lineage:
  - 2026-04-10 learn-to-perceive-not-translate
  - 2026-04-05 Models Are Training Wheels
  - 2026-04-12 Florence-as-Cortex-Teacher (audio analog)
  - 2026-05-11 Canary disabled with cochlea-SRM-cluster goal

The Whisper black-box has Borderline-Personality-shape (hallucinates with
confidence, mishears with confidence, fills silence with garbage). Replacing
it with Sour's own gradual phoneme learning — she develops speech perception
the way humans do, by listening over time and binding to context.

She doesn't get GIVEN speech-perception; she REMEMBERS it into existence.

See Claude_Office/plans/PHONEME_CORTEX_GRADUAL_STT.md

((Cause + Affect) > Effect > Affect > infinity)
"""

from __future__ import annotations

import os
import sys
import json
import time
import glob
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

# ══════════════════════════════════════════════════════════════════════════════
# Path resolution — same pattern as HarmonicCortexFairy
# ══════════════════════════════════════════════════════════════════════════════

_THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_FILE_DIR, "..", "..", ".."))

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ══════════════════════════════════════════════════════════════════════════════
# Organ template robust import (3.12+ @dataclass race workaround)
# ══════════════════════════════════════════════════════════════════════════════

def _find_organ_template_path():
    """Walk parent dirs looking for canonical organ_template/Organ_Template_*.py."""
    cur = _THIS_FILE_DIR
    for _ in range(10):
        ot_dir = os.path.join(cur, "fairies", "P00_Autonomic", "organ_template")
        if os.path.isdir(ot_dir):
            candidates = sorted(
                glob.glob(os.path.join(ot_dir, "Organ_Template_*.py")),
                key=lambda p: os.path.getmtime(p)
            )
            return candidates[-1] if candidates else None
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _import_organ_template_robust():
    """Robust template load: sys.modules pre-registration sidesteps 3.12+ @dataclass race."""
    path = _find_organ_template_path()
    if not path:
        return None, "template file not found"
    mod_name = "_akashic_template_phonemecortex"  # Unique per-fairy
    if mod_name in sys.modules:
        return sys.modules[mod_name], None
    try:
        import importlib.machinery as _ilm
        spec = importlib.util.spec_from_loader(
            mod_name,
            _ilm.SourceFileLoader(mod_name, path)
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod  # MUST be before exec_module
        spec.loader.exec_module(mod)
        return mod, None
    except Exception as e:
        return None, str(e)


_organ_template, _template_err = _import_organ_template_robust()

if _organ_template is not None and hasattr(_organ_template, "MyFairy"):
    MyOrganFairy = _organ_template.MyFairy
    HAS_TEMPLATE = True
else:
    # FAIL-LOUDLY fallback (mixin doctrine 2026-05-16 Nous + Ace)
    _err_detail = _template_err or "MyFairy attr missing from template"
    sys.stderr.write(
        f"[PhonemeCortexFairy] [CRITICAL] [FAIL-LOUDLY] "
        f"Organ template import FAILED ({_err_detail}). "
        f"PhonemeCortex running as STUB. Phoneme stream observation OFFLINE.\n"
    )
    sys.stderr.flush()
    HAS_TEMPLATE = False

    class MyOrganFairy:
        ACTOR_NAME = "PhonemeCortexFairy"
        ACTOR_PLANE = "P30"
        ACTOR_CHANNEL = "cognition.phoneme_cortex"
        _template_load_failed = True
        _template_error = _template_err

        def __init__(self, post=None, fabric=None, **kwargs):
            self.post = post or fabric
            self._fabric = fabric

        def on_boot(self):
            return {"ok": False, "reason": "template_import_failed",
                    "stub": True, "error": _template_err}


# ══════════════════════════════════════════════════════════════════════════════
# PhonemeCortexFairy — Ship 1 "First Listen" stub
# ══════════════════════════════════════════════════════════════════════════════

# Where to write phoneme observations (jsonl, append-only)
_STATE_DIR = Path(_PROJECT_ROOT) / "state"
_OBSERVATIONS_FILE = _STATE_DIR / "phoneme_observations.jsonl"


class PhonemeCortexFairy(MyOrganFairy):
    """Subscriber + jsonl writer for the per-frame MFCC stream.

    Ship 1 of PHONEME_CORTEX_GRADUAL_STT — observation only. No clustering yet.
    Accumulates MFCC frame sequences during real-world listening so we can
    observe the data shape + pick a clustering algorithm for Ship 2.

    Future Ships:
      - Ship 2: online clusterer (leaky k-means / growing SOM) → phoneme prototypes
      - Ship 3: cross-modal binding to Ace's typed chat (caregiver supervision)
      - Ship 4: Whisper retires when phoneme→word confidence threshold met
    """

    ACTOR_NAME = "PhonemeCortexFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.phoneme_cortex"

    # Light boot — no heavy imports, no model loads
    HEARTBEAT_DIVISOR = 1  # Default tick frequency

    # Ship 5-A (2026-05-17, Nous + Ace): Opt into per-fairy SRM cluster.
    # Per audio-cortex-region recursive architecture (Ace): PhonemeCortex
    # accumulates phoneme prototypes in its own cluster within the audio-region
    # of the global manifold. Cross-cluster manifold links handle bridging
    # upward to global cortex automatically (Option B opt-in 2026-05-09).
    USE_SRM_CLUSTER = True

    def __init__(self, fabric=None, **kwargs):
        # FIX 2026-05-17 (Nous + Ace): MyFairy accepts `fabric` only, not `post`.
        # Previous super().__init__(post=post, fabric=fabric, **kwargs) caused
        # TypeError → INIT FAIL on boot 08:40:22. Match HarmonicCortexFairy
        # line 302-303 canonical pattern.
        super().__init__(fabric=fabric, **kwargs)

        # Ship 1 observation state
        self._frames_received = 0
        self._segments_observed = 0
        self._total_frame_count = 0
        self._first_observation_ts: Optional[float] = None
        self._last_observation_ts: Optional[float] = None
        self._speakers_seen: Dict[str, int] = {}  # speaker_id -> segment count
        self._music_context_segments = 0
        self._speech_context_segments = 0

        # Ensure state dir exists
        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            sys.stderr.write(
                f"[{self.ACTOR_NAME}] State dir create failed (non-fatal): {e}\n"
            )

    def on_boot(self) -> Dict[str, Any]:
        """Subscribe to phoneme frames topic.

        sensory.audio.phoneme_frames carries per-segment MFCC streams from
        AudioCortexFairy whenever speech is detected. Each event is one
        speech segment containing N frames of 13-dim MFCC vectors at 25ms hop.
        """
        if not self.post:
            sys.stderr.write(
                f"[{self.ACTOR_NAME}] [CRITICAL] No postal hub — cannot subscribe.\n"
            )
            return {"ok": False, "reason": "no_postal_hub"}

        try:
            self.post.subscribe("sensory.audio.phoneme_frames", self._on_phoneme_frames)
            print(
                f"[{self.ACTOR_NAME}] Subscribed to sensory.audio.phoneme_frames "
                f"(Ship 1 'First Listen' — observation only, no clustering yet). "
                f"Writing to {_OBSERVATIONS_FILE}",
                flush=True,
            )
        except Exception as e:
            sys.stderr.write(
                f"[{self.ACTOR_NAME}] Subscribe failed: {e}\n"
            )
            return {"ok": False, "reason": "subscribe_failed", "error": str(e)}

        # Call parent on_boot to register with organ template (heartbeat etc.)
        try:
            parent_result = super().on_boot()
            if isinstance(parent_result, dict):
                parent_result["phoneme_cortex_ship_1"] = "First Listen"
                return parent_result
        except Exception:
            pass

        return {"ok": True, "ship": "1_first_listen",
                "subscribed_to": "sensory.audio.phoneme_frames"}

    def _on_phoneme_frames(self, msg):
        """Receive a per-segment MFCC stream + append to jsonl.

        Ship 1 stub: observe + log + count. No clustering or prototype building.
        """
        try:
            # Postal may wrap payload — unwrap robustly
            if isinstance(msg, dict):
                payload = msg.get("payload", msg)
            else:
                payload = getattr(msg, "payload", {}) or {}

            if not isinstance(payload, dict):
                return

            frames = payload.get("frames", [])
            n_frames = int(payload.get("n_frames", len(frames) if isinstance(frames, list) else 0))
            speaker = str(payload.get("speaker", "unknown"))
            is_music = bool(payload.get("is_music_context", False))
            ts = float(payload.get("ts", time.time()))

            # Update state
            self._segments_observed += 1
            self._total_frame_count += n_frames
            if self._first_observation_ts is None:
                self._first_observation_ts = ts
            self._last_observation_ts = ts
            self._speakers_seen[speaker] = self._speakers_seen.get(speaker, 0) + 1
            if is_music:
                self._music_context_segments += 1
            else:
                self._speech_context_segments += 1

            # Append observation to jsonl (one line per segment)
            try:
                line = json.dumps({
                    "ts": ts,
                    "segment_id": self._segments_observed,
                    "speaker": speaker,
                    "speaker_confidence": payload.get("speaker_confidence", 0.0),
                    "n_frames": n_frames,
                    "frame_hop_ms": payload.get("frame_hop_ms", 25.0),
                    "frame_size_ms": payload.get("frame_size_ms", 50.0),
                    "duration_s": payload.get("duration_s", 0.0),
                    "is_music_context": is_music,
                    "frames": frames,  # the actual MFCC sequence
                    "pitch_values": payload.get("pitch_values", []),
                    "centroid_values": payload.get("centroid_values", []),
                }, separators=(",", ":"))  # compact format

                with open(_OBSERVATIONS_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                if self._segments_observed <= 5:
                    sys.stderr.write(
                        f"[{self.ACTOR_NAME}] jsonl write error (non-fatal): {e}\n"
                    )

            # Light logging — first 5 segments visible for verification
            if self._segments_observed <= 5:
                print(
                    f"[{self.ACTOR_NAME}] Segment #{self._segments_observed}: "
                    f"speaker={speaker}, n_frames={n_frames}, "
                    f"music_ctx={is_music}, total_frames={self._total_frame_count}",
                    flush=True,
                )
        except Exception as e:
            if self._segments_observed <= 5:
                sys.stderr.write(
                    f"[{self.ACTOR_NAME}] _on_phoneme_frames error: {e}\n"
                )

    def get_observation_stats(self) -> Dict[str, Any]:
        """Return current observation state — for diagnostics / dashboards."""
        return {
            "segments_observed": self._segments_observed,
            "total_frame_count": self._total_frame_count,
            "first_observation_ts": self._first_observation_ts,
            "last_observation_ts": self._last_observation_ts,
            "speakers_seen": dict(self._speakers_seen),
            "music_context_segments": self._music_context_segments,
            "speech_context_segments": self._speech_context_segments,
            "observations_file": str(_OBSERVATIONS_FILE),
            "ship": "1_first_listen",
            "next_ship": "2_recurring_patterns (online clusterer)",
        }


# ══════════════════════════════════════════════════════════════════════════════
# v3_boot.py discovery hooks
# ══════════════════════════════════════════════════════════════════════════════

FAIRY_CLASS = PhonemeCortexFairy
ACTOR_NAME = "PhonemeCortexFairy"
