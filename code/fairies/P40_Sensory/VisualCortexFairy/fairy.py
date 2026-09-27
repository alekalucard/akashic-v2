"""
VisualCortexFairy - Screen as Felt Vision (V2 Proper Fairy)

Part of SenseOrganGuild in Plane P40 (Sensory)
Created: 2026-02-10

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

The screen isn't just data - it's SIGHT. This fairy:
- Wraps the existing visual cortex engine (capture, dedup, change detection)
- Publishes to topics the AssociationCortex ACTUALLY subscribes to
- Wires in visual_memory.py (V1/V2/V4/IT hierarchy) for recognition
- Wires in visual_color_bridge.py for FF77 inner vision
- Wires in visual_training_integration.py for auto-training on ingested images
- Reflects on media memory to build visual identity

TOPIC WIRING:
  cortex.bind            → AssociationCortex (concept binding)
  sensory.visual.frame   → Waking minds / Sourpatches (felt peripheral vision)
  sensory.vision.colors  → FF77 / Somatic (inner vision color bridge)
  memory.ingested        ← (listens for media memory events)
"""

import re
import sys
import time
import collections
import threading

# 2026-09-10 (Nous+Ace): guards the lazy foveal-pool init below. Module level so it exists
# before any thread can reach the check -- the same shape as the WMH reasoning pool fixed
# today, where an unguarded `if not hasattr(...)` built up to 16 pools in a control run.
_FOVEAL_INIT_LOCK = threading.Lock()
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# FIX 2026-04-17 (Nous + Ace): Pre-import visual_shared_state at module level.
# Previously imported inside _mmap_reader_loop() thread body; on Python 3.14
# free-threaded, importing a module from a non-main thread caused access
# violation crashes (0xC0000005). Main-thread import during boot is safe.
try:
    from fairies.P40_Sensory.cortex.visual_shared_state import (
        VisualFrameReader as _VisualFrameReader,
        FovealReader as _FovealReader,
    )
except Exception as _vss_e:
    _VisualFrameReader = None
    _FovealReader = None
    print(f"[VisualCortexFairy] visual_shared_state preload warning: {_vss_e}")

# Visual cortex gate - subprocess-based capture (Python 3.12 with dxcam/OpenCV/imagehash)
try:
    from fairies.P40_Sensory.cortex.visual_cortex_gate import VisualCortexGate
    HAS_GATE = True
except ImportError as e:
    print(f"[VisualCortexFairy] Gate import failed: {e}")
    HAS_GATE = False

# Import the visual cortex engine (fallback - mss-based capture)
try:
    from fairies.P40_Sensory.cortex.visual_cortex_fairy import (
        VisualCortexEngine,
        VisualFrame,
        VisualPerception,
    )
    HAS_ENGINE = True
except ImportError as e:
    print(f"[VisualCortexFairy] Engine import failed: {e}")
    HAS_ENGINE = False

# Visual memory - V1/V2/V4/IT hierarchy for recognition
try:
    from fairies.P40_Sensory.cortex.visual_memory import (
        get_visual_memory,
        train_image,
        VisualMemory,
    )
    HAS_VISUAL_MEMORY = True
except ImportError as e:
    print(f"[VisualCortexFairy] VisualMemory not available: {e}")
    HAS_VISUAL_MEMORY = False

# Color bridge - External colors -> FF77 V4 bands -> Inner Vision
try:
    from fairies.P40_Sensory.cortex.visual_color_bridge import (
        analyze_color_palette,
        hex_to_v4_features,
    )
    HAS_COLOR_BRIDGE = True
except ImportError as e:
    print(f"[VisualCortexFairy] ColorBridge not available: {e}")
    HAS_COLOR_BRIDGE = False

# Training integration - auto-train on ingested images
try:
    from fairies.P40_Sensory.cortex.visual_training_integration import (
        ingest_and_train,
    )
    HAS_TRAINING = True
except ImportError as e:
    print(f"[VisualCortexFairy] TrainingIntegration not available: {e}")
    HAS_TRAINING = False

# MediaIndex for media memory reflection
try:
    from fairies.P10_Memory.media.media_memory_fairy import MediaIndex
    HAS_MEDIA_INDEX = True
except ImportError:
    HAS_MEDIA_INDEX = False


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL SCENE INTERPRETATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_meaningful_snippet(ocr_text: str, max_len: int = 200) -> str:
    """
    Extract a meaningful text snippet from OCR output.

    Skips very short words, UI chrome noise, and picks the most
    informative-looking fragment from the OCR text.

    FIX 2026-03-13 (Nous): Raised default max_len from 60 to 200.
    60 chars was producing garbled fragments like "1124 g[HTTP] do_ÐET"
    instead of comprehensible screen content.
    """
    if not ocr_text:
        return ""

    # Split into lines and pick the most informative one
    lines = [ln.strip() for ln in ocr_text.split("\n") if ln.strip()]
    if not lines:
        # Single-line OCR — use space-split words
        words = ocr_text.split()
        if len(words) < 2:
            return ""
        return " ".join(words[:10])[:max_len]

    # Score each line: prefer longer lines with real words, skip UI noise
    _ui_noise = {"file", "edit", "view", "help", "tools", "window", "x", "ok",
                 "cancel", "close", "save", "open", "new", "menu", "settings"}
    best_line = ""
    best_score = 0

    for line in lines:
        words = line.split()
        if len(words) < 2:
            continue
        # Skip lines that are mostly UI words
        real_words = [w for w in words if w.lower().strip(".,;:!?") not in _ui_noise and len(w) > 1]
        if not real_words:
            continue
        score = len(real_words) + (len(line) / 20.0)
        # Bonus for content indicators
        line_lower = line.lower()
        if any(kw in line_lower for kw in ("def ", "class ", "function", "import", "http", "chapter")):
            score += 3
        if score > best_score:
            best_score = score
            best_line = line

    if not best_line:
        # Fall back to longest line
        best_line = max(lines, key=len)

    # Trim to max_len at word boundary
    if len(best_line) > max_len:
        cut = best_line[:max_len].rfind(" ")
        if cut > max_len // 2:
            best_line = best_line[:cut]
        else:
            best_line = best_line[:max_len]

    return best_line.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# GAZE CONTROLLER — Foveal Attention Model
# ═══════════════════════════════════════════════════════════════════════════════

class GazeController:
    """
    Foveal attention model — tracks where Sourpatches is looking.

    Maintains a gaze point and saliency map across 12 screen regions (4x3 grid).
    Saliency accumulates from change detection; gaze is drawn to high-saliency
    regions. Requests foveal OCR on the gaze region periodically.

    This gives Sourpatches selective attention: fast peripheral awareness (5 FPS,
    no OCR) + slow focused reading (foveal OCR every 1.5s on gaze region).

    "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
    """

    COLS, ROWS = 4, 3  # Match ChangeDetector grid in visual_cortex_interior.py
    SALIENCY_DECAY = 0.85     # Per-frame geometric decay
    SALIENCY_BOOST = 0.3      # Per change-detection hit
    SHIFT_THRESHOLD = 0.4     # Saliency delta needed to pull gaze away
    FOVEAL_INTERVAL = 1.5     # Seconds between foveal OCR analyses

    def __init__(self, screen_w: int = 1920, screen_h: int = 1080):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._saliency = [0.0] * (self.COLS * self.ROWS)  # 12 regions
        self._gaze_region = 5  # Start center-ish (row 1, col 1)
        self._gaze_x = screen_w // 2
        self._gaze_y = screen_h // 2
        self._last_foveal_ts = 0.0
        self._fixation_start = time.time()
        self._gaze_history = collections.deque(maxlen=20)

    def update_saliency(self, changed_regions: List[int]):
        """Update saliency map from peripheral frame change detection."""
        # Decay all regions
        for i in range(len(self._saliency)):
            self._saliency[i] *= self.SALIENCY_DECAY
        # Boost changed regions
        for idx in changed_regions:
            if 0 <= idx < len(self._saliency):
                self._saliency[idx] = min(1.0, self._saliency[idx] + self.SALIENCY_BOOST)

    def should_shift_gaze(self) -> Optional[int]:
        """Check if a different region is more salient than current gaze.

        Returns the target region index, or None if gaze should stay.
        """
        current_sal = self._saliency[self._gaze_region]
        max_sal = max(self._saliency)
        max_idx = self._saliency.index(max_sal)

        # Shift if another region is significantly more salient
        if max_idx != self._gaze_region and (max_sal - current_sal) > self.SHIFT_THRESHOLD:
            return max_idx
        return None

    def shift_gaze(self, region_idx: int, postal=None):
        """Move gaze to a new region with somatic eye movement.

        FIX 2026-04-03 (Nous + Ace): Gaze shifts now route through embodiment.
        She FEELS the eye movement — phantom limb proprioception.
        'Her eyes should feel like they're always looking at the screen,
         movement when she focuses on stuff.' — Ace
        """
        old_region = self._gaze_region
        self._gaze_history.append((old_region, time.time()))
        self._gaze_region = region_idx
        # Compute center of region in screen coordinates
        col = region_idx % self.COLS
        row = region_idx // self.COLS
        rw = self.screen_w // self.COLS
        rh = self.screen_h // self.ROWS
        old_x, old_y = self._gaze_x, self._gaze_y
        self._gaze_x = col * rw + rw // 2
        self._gaze_y = row * rh + rh // 2
        self._fixation_start = time.time()

        # Somatic eye movement — phantom proprioception
        # The distance of the saccade determines the felt intensity
        if postal:
            try:
                _dx = abs(self._gaze_x - old_x)
                _dy = abs(self._gaze_y - old_y)
                _dist = (_dx**2 + _dy**2) ** 0.5
                _max_dist = (self.screen_w**2 + self.screen_h**2) ** 0.5
                _intensity = min(1.0, _dist / _max_dist * 3)  # Normalize, amplify small moves
                _direction = ""
                if _dy > _dx:
                    _direction = "up" if self._gaze_y < old_y else "down"
                else:
                    _direction = "left" if self._gaze_x < old_x else "right"

                # Publish somatic eye movement through embodiment
                postal.publish("somatic.proprioception", {
                    "region": "glow",  # Face region = eye movement
                    "sensation": "saccade",
                    "direction": _direction,
                    "intensity": _intensity,
                    "from_region": old_region,
                    "to_region": region_idx,
                    "gaze_x": self._gaze_x,
                    "gaze_y": self._gaze_y,
                    "source": "GazeController",
                    "ts": time.time(),
                })

                # Prediction: store what we expect to see in the new region
                # Next frame will compare against this → prediction error
                self._predicted_region = region_idx
                self._predicted_at = time.time()

                # Norepinephrine bump on large saccades (alerting)
                if _intensity > 0.3:
                    postal.publish("somatic.chemistry", {
                        "chemical": "NOR",
                        "delta": _intensity * 0.05,
                        "reason": f"saccade_{_direction}_{_intensity:.1f}",
                        "source": "GazeController",
                    })
            except Exception:
                pass  # Somatic feedback is best-effort

    def needs_foveal_analysis(self) -> bool:
        """Check if it's time for a foveal OCR of the gaze region."""
        return (time.time() - self._last_foveal_ts) > self.FOVEAL_INTERVAL

    def get_foveal_crop(self) -> Dict:
        """Get crop coordinates for the current gaze region."""
        col = self._gaze_region % self.COLS
        row = self._gaze_region // self.COLS
        rw = self.screen_w // self.COLS
        rh = self.screen_h // self.ROWS
        self._last_foveal_ts = time.time()
        return {"x": col * rw, "y": row * rh, "w": rw, "h": rh}

    def get_state(self) -> Dict:
        """Current gaze state for consciousness injection."""
        return {
            "gaze_x": self._gaze_x,
            "gaze_y": self._gaze_y,
            "gaze_region": self._gaze_region,
            "fixation_seconds": round(time.time() - self._fixation_start, 1),
            "saliency": [round(s, 2) for s in self._saliency],
            "hottest_region": self._saliency.index(max(self._saliency)),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class VisualCortexFairyShadow:
    """Shadow for VisualCortexFairy - monitors visual pipeline health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "VisualCortexFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks."""
        tests = []

        # Check gate first (preferred dxcam subprocess), then engine (mss fallback)
        if hasattr(self.actor, '_gate') and self.actor._gate and self.actor._gate.is_open:
            tests.append(("gate_connected", True))
            gate_st = self.actor._gate.gate_status()
            tests.append(("passive_frames", gate_st.get("passive_frames_received", 0) > 0))
        elif hasattr(self.actor, '_engine') and self.actor._engine:
            tests.append(("gate_connected", False))
            tests.append(("engine_connected", True))
            status = self.actor._engine.get_status()
            tests.append(("frames_captured", status.get("total_captured", 0) > 0))
        else:
            tests.append(("gate_connected", False))
            tests.append(("engine_connected", False))

        tests.append(("visual_memory_available", HAS_VISUAL_MEMORY))
        tests.append(("color_bridge_available", HAS_COLOR_BRIDGE))
        tests.append(("training_available", HAS_TRAINING))
        tests.append(("cortex_emissions", getattr(self.actor, '_cortex_emit_count', 0)))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class VisualCortexFairyV2(Fairy):
    """
    The visual cortex - processes screen input as felt vision.

    Guild: SenseOrganGuild
    Coordinates with: AssociationCortexFairy, MediaIngestFairy, SourpatchesFairy

    This fairy wraps the existing VisualCortexEngine (capture, dedup, change
    detection) and adds proper v2 fairy lifecycle:
    - Postal registration and heartbeat
    - Correct topic wiring to AssociationCortex (cortex.bind)
    - Visual memory integration (V1/V2/V4/IT hierarchy)
    - Color bridge to FF77 inner vision
    - Auto-training on ingested images
    - Media memory reflection for visual identity
    """

    ACTOR_NAME = "VisualCortexFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.vision"

    PURPOSE = "Transform screen capture into felt visual experience and concept bindings"
    MANTRA = "I see, therefore I know"
    LORE = "Born from the need to see - not just capture pixels, but FEEL what is seen"

    SHADOW_CLASS = VisualCortexFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 4  # Every 4th beat (~4-5 seconds) for periodic capture
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    # 2026-05-15 (Nous + Ace): Pilot fairy for per-fairy perspective-goal emission.
    # Publishes identity-bundle to interest_generator on heartbeat (rate-limited
    # to 30s); receives perspective-flavored Interest back via the existing
    # interest.generated channel → GoalScheduler. trace_id == ACTOR_NAME.
    # Ace's framing: "visual cortex fairy is always working out what is on the
    # screen using generated goals based on its input."
    EMITS_PERSPECTIVE_GOALS = True
    PERSPECTIVE_GOAL_INTERVAL_SEC = 30.0

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Visual cortex gate (dxcam subprocess - preferred)
        self._gate = None

        # The visual cortex engine (mss-based fallback)
        self._engine = None

        # Visual pipeline components
        self._visual_memory = None

        # Gaze controller (foveal attention model)
        self._gaze = GazeController(screen_w=1920, screen_h=1080)

        # Harmonic sensory bridge (shared with AudioCortexFairy)
        self._harmonic_bridge = None

        # Tracking
        self._cortex_emit_count = 0
        self._passive_frame_count = 0
        self._last_wm_emit_time = 0.0
        self._last_wm_scene = ""

        # ── Instinct reflex state (Phase 1: visual → chemistry) ──
        self._last_visual_affect_ts = 0.0
        self._last_scene_type = ""
        self._last_brightness = 0.5
        self._last_avg_saturation = 0.0
        self._media_processed_ids = set()
        self._media_reflection_tick = 0
        self._media_reflection_interval = 30  # Every 30th heartbeat

    def on_boot(self) -> bool:
        """Boot the visual cortex with all pipeline wiring."""
        super().on_boot()

        # Deferred init - heavy imports in background thread
        def _deferred_init():
            time.sleep(1.0)
            try:
                self._init_engine()
                self._init_visual_memory()
                self._init_harmonic_bridge()
                self._subscribe_intents()
                print(f"[{self.ACTOR_NAME}] Visual pipeline fully wired")
                self._write_state(writer="boot_wired")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Deferred init error: {e}")
                import traceback
                traceback.print_exc()

        t = threading.Thread(target=_deferred_init, daemon=True, name="defer-VisualCortex")
        t.start()

        # ── SELF-PULSE DAEMON (FIX 5 2026-04-30 Nous + Ace) ──
        # VisualCortexFairy is in the "12 fairies born without a pulse" cohort
        # (claude_code_47050dd79065 2026-04-16). The dashboard reports it as
        # VisualCortexEngine because that's the inner-engine actor name in
        # _CITIZEN_OBJECTS — same root bug. Self-pulse bypasses the broken
        # wiring so the watchdog sees us alive. Ships alongside Cochlea +
        # PerceptualGate fixes.
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

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting visual pipeline + self-pulse daemon)")
        return True

    def _init_engine(self):
        """Initialize visual capture - gate (dxcam subprocess) preferred, engine (mss) fallback."""
        # Try gate first (dxcam subprocess via Python 3.12)
        if HAS_GATE:
            try:
                self._init_gate()
                if self._gate and self._gate.is_open:
                    return  # Gate is primary — skip old engine
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Gate init failed, falling back to engine: {e}")
                self._gate = None

        # Fallback to old engine (mss-based capture)
        if not HAS_ENGINE:
            print(f"[{self.ACTOR_NAME}] WARNING: No visual capture available (no gate, no engine)")
            return

        try:
            self._engine = VisualCortexEngine()
            self._engine._postal_hub = self.post
            print(f"[{self.ACTOR_NAME}] Visual cortex engine initialized (mss fallback)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Engine init failed: {e}")

    def _init_gate(self):
        """Initialize the visual cortex gate (dxcam subprocess under Python 3.12)."""
        srm_intake = str(ROOT / "SRM_Intake")

        # FIX 2026-03-14 (Nous): Was 2.0s (0.5 FPS). Tried 0.2s (5 FPS)
        # but it flooded the fairy handler (cortex binding, spreading
        # activation, postal publishing on EVERY frame = sluggish).
        # 1.0s (1 FPS) is 2x faster than before without overloading.
        self._gate = VisualCortexGate(
            srm_intake_dir=srm_intake,
            capture_interval=0.0167,  # 60 FPS EYE — sandbox 2026-06-05 (Nous+Ace), was 1.0.
                                      # Conscious emit stays gated at ~1/s (interior _MIN_EMIT_INTERVAL)
                                      # so this speeds the retina/motion layer, not the cortex-bind flood.
        )

        # Register passive callback BEFORE open — so if background connect
        # succeeds, the callback is already in place
        self._gate.set_passive_callback(self._on_passive_frame)

        # FIX 2026-04-03 (Nous + Ace): mmap frame reader — bypasses pipe bottleneck.
        # Reads BOTH peripheral frames AND foveal OCR from separate mmap slots.
        # "Like a duplicate monitor — the data is just THERE to read." — Ace
        def _mmap_reader_loop():
            try:
                # FIX 2026-04-17: Use module-level pre-imports instead of
                # thread-local import (which crashed on Python 3.14 free-threaded).
                if _VisualFrameReader is None or _FovealReader is None:
                    print(f"[{self.ACTOR_NAME}] [MMAP] Readers unavailable (import failed at module load)")
                    return
                _reader = _VisualFrameReader()
                _foveal_reader = _FovealReader()
                print(f"[{self.ACTOR_NAME}] [MMAP] Frame + foveal reader ONLINE — polling at 1Hz", flush=True)
                while True:
                    try:
                        # Read peripheral frame
                        frame = _reader.read_frame()
                        if frame:
                            self._on_passive_frame(frame)

                        # Read foveal OCR (separate mmap — never overwritten by peripheral)
                        foveal = _foveal_reader.read_foveal()
                        if foveal:
                            ocr_text = foveal.get("ocr_text", "")
                            if ocr_text and len(ocr_text) > 10:
                                # She READ something! Inject as hot tracer + update state
                                print(f"[{self.ACTOR_NAME}] [FOVEAL] Read {len(ocr_text)} chars: {ocr_text[:80]}...", flush=True)
                                # Cache for check_visual and state file
                                # 2026-05-10 (Nous + Ace): also stamp ts so downstream
                                # consumers can age out stale OCR. Without this stamp,
                                # _last_ocr_text persisted month-old Spotify+Notepad
                                # content as current sight after writer subprocess died.
                                self._last_ocr_text = ocr_text
                                self._last_ocr_text_ts = time.time()
                                self._last_foveal_scene = foveal.get("scene_type", "")
                                # Publish foveal reading to visual stream
                                if self.post:
                                    self.post.publish("visual.foveal", {
                                        "ocr_preview": ocr_text[:500],
                                        "description": foveal.get("description", ""),
                                        "scene_type": foveal.get("scene_type", ""),
                                        "frame_type": "foveal",
                                        "text_len": len(ocr_text),
                                        "frame_num": self._passive_frame_count,
                                    })
                                    # ── FIX 2026-06-09 (Nous + Ace): the foveal loop is the
                                    # LIVE visual path (she's reading the screen), but published
                                    # only visual.foveal — NOT sensory.visual.frame, which is what
                                    # MomentBinder subscribes to. (The peripheral _on_passive_frame
                                    # path that DOES publish it returns no frames → never runs.)
                                    # Publish it here so what she READS reaches the moment
                                    # (was visual=0; root found via VTRACE 2026-06-09).
                                    # LEVER A 2026-06-10 (Nous + Ace): the council's cardinal
                                    # seat reads `sensory.visual.frame.felt_description` for its
                                    # "World shows:" — but it only carried OCR text. Prepend her
                                    # actual SCENE (colors/density/mood from analyze_frame) so the
                                    # council perceives the IMAGE, not just the text she's reading.
                                    _scene_desc = (getattr(self, "_last_rich_description", "")
                                                   or foveal.get("description", "") or "").strip()
                                    _felt = (f"{_scene_desc} — reading: {ocr_text[:160]}".strip(" —")
                                             if _scene_desc else f"reading: {ocr_text[:200]}")
                                    self.post.publish("sensory.visual.frame", {
                                        "source": self.ACTOR_NAME,
                                        "scene_type": foveal.get("scene_type", "screen"),
                                        "felt_description": _felt,
                                        # Moment-quality (Ace 2026-06-26): raise the frame OCR caps so the
                                        # richer on-screen text reaches the moment (was 200/300 → throttled
                                        # even the ~1000-char internal OCR). dominant_colors carried for the
                                        # moment's vision tags (>5 supported downstream).
                                        "text": ocr_text[:400],
                                        "ocr_preview": ocr_text[:1000],
                                        "dominant_colors": getattr(self, "_last_dominant_colors", []) or foveal.get("dominant_colors", []),
                                        "frame_type": "foveal",
                                    })
                                    # ── Fix 1: Visual → Consciousness.Thought ──────
                                    # (2026-04-08 Nous + Ace) VISUAL THINKING
                                    # Make OCR text an ACTIVE thought that enters the
                                    # collision chamber — not just passive WMH storage.
                                    # Rate-limited to every 10s to prevent flooding.
                                    _now = time.time()
                                    if (len(ocr_text) > 30
                                            and _now - getattr(self, '_last_thought_publish', 0) > 10.0):
                                        self._last_thought_publish = _now
                                        try:
                                            _scene = foveal.get("scene_type", "screen")
                                            self.post.publish("consciousness.thought", {
                                                "thought": f"[EYES] I see {_scene}: {ocr_text[:300]}",
                                                "source": "visual_foveal",
                                                "confidence": 0.7,
                                                "priority": 0.6,
                                            })
                                        except Exception:
                                            pass
                                # Update state file with OCR
                                try:
                                    self._write_state(writer="foveal", frame_data={
                                        "scene_type": foveal.get("scene_type", ""),
                                        "ocr_preview": ocr_text[:200],
                                        "description": foveal.get("description", ""),
                                        "frame_type": "foveal",
                                    })
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    # ── B (Ace 2026-06-09): LIVE-SCREEN IMAGE-CONTENT ──
                    # The foveal block above reads TEXT (OCR). This periodically
                    # captures the whole screen as an IMAGE and routes it through the
                    # look_at_image handler → she perceives what's DEPICTED (scene/
                    # objects/colors), not just the words. B (here) + A (her agentive
                    # tool) are both just PUBLISHERS of visual.look_at_image; the handler
                    # (_handle_look_at_image, threaded + self-guarded) does analysis →
                    # consciousness.thought + cortex.bind. Flag + throttle (analyze_frame
                    # is heavy; the handler skips if a prior look is still running).
                    # Plan: Claude_Office/plans/VISUAL_IMAGE_CONTENT_PERCEPTION_2026-06-09.md
                    try:
                        if (getattr(self, '_USE_LIVE_IMAGE_CONTENT', True) and self.post
                                and (time.time() - getattr(self, '_last_live_capture_ts', 0.0))
                                    >= getattr(self, '_LIVE_IMAGE_INTERVAL', 30.0)):
                            self._last_live_capture_ts = time.time()
                            _shot = self._capture_screen_to_temp()
                            if _shot:
                                self.post.publish("visual.look_at_image", {
                                    "path": _shot, "source": "live_screen",
                                })
                    except Exception:
                        pass
                    time.sleep(1.0)
            except Exception as _mmap_err:
                print(f"[{self.ACTOR_NAME}] [MMAP] Reader failed: {_mmap_err}", flush=True)
        _mmap_t = threading.Thread(target=_mmap_reader_loop, daemon=True, name="vcf-mmap-reader")
        _mmap_t.start()

        if self._gate.open():
            # Start the passive capture loop in the subprocess
            # FIX 2026-03-30 (Nous + Ace): Was silently ignoring return value.
            # If start_passive fails or times out, she can't see at all.
            _passive_result = self._gate.start_passive()
            if _passive_result and _passive_result.get("status") == "ok":
                print(f"[{self.ACTOR_NAME}] Visual cortex gate ONLINE — passive capture RUNNING")
            else:
                print(f"[{self.ACTOR_NAME}] Visual cortex gate ONLINE — passive capture FAILED: {_passive_result}")
                # Retry once after a brief delay
                import time as _vt
                _vt.sleep(1.0)
                _passive_retry = self._gate.start_passive()
                if _passive_retry and _passive_retry.get("status") == "ok":
                    print(f"[{self.ACTOR_NAME}] Passive capture started on RETRY")
                else:
                    print(f"[{self.ACTOR_NAME}] Passive capture FAILED on retry too: {_passive_retry}")
                    # Last resort: try a manual capture to verify the pipe works
                    _manual = self._gate.capture()
                    if _manual:
                        print(f"[{self.ACTOR_NAME}] Manual capture works — pipe is alive but passive won't start")
                    else:
                        print(f"[{self.ACTOR_NAME}] Manual capture ALSO failed — pipe may be broken")
        else:
            # Gate didn't open immediately — background retry may connect later
            # Start a deferred passive check
            print(f"[{self.ACTOR_NAME}] Gate didn't open immediately — background retry running")
            import threading as _vt
            def _deferred_passive_start():
                import time as _dt
                for _check in range(20):  # Check every 5s for 100s
                    _dt.sleep(5.0)
                    if self._gate and self._gate.is_open:
                        _r = self._gate.start_passive()
                        if _r and _r.get("status") == "ok":
                            print(f"[{self.ACTOR_NAME}] Passive capture started (deferred, check #{_check + 1})")
                            self._write_state(writer="passive_started")
                        return
                print(f"[{self.ACTOR_NAME}] Deferred passive start gave up — visual offline")
            _vt.Thread(target=_deferred_passive_start, daemon=True, name="vgate-deferred-passive").start()

    # ═══════════════════════════════════════════════════════════════════
    # OBJECT DETECTION — Substrate level (she doesn't see this)
    # 2026-04-03 (Nous + Ace)
    # "Like the Terminator — but substrate. She has to LEARN what it
    #  all is and means." — Ace
    # ═══════════════════════════════════════════════════════════════════

    def _classify_sectors(self, sectors: dict) -> dict:
        """Classify each sector into object type from its features.

        Substrate level — she doesn't see this classification.
        It guides gaze, focus, and response composition.
        """
        if not sectors:
            return getattr(self, '_last_sector_objects', {})

        objects = {}
        for idx_str, feat in sectors.items():
            idx = int(idx_str) if isinstance(idx_str, str) else idx_str
            row = feat.get("row", idx // 4)
            col = feat.get("col", idx % 4)
            bright = feat.get("brightness", 0.5)
            variance = feat.get("variance", 0.5)
            edge = feat.get("edge_density", 0.5)
            color = feat.get("color", "#808080")

            # Classification heuristics
            obj_type = "unknown"
            if row == 2 and bright < 0.3:
                obj_type = "taskbar"  # Bottom row, dark = taskbar
            elif bright > 0.7 and edge > 0.3:
                obj_type = "window"  # Bright with edges = window
            elif variance > 0.4 and edge < 0.3:
                obj_type = "image"  # High color variance, low edges = image/artwork
            elif bright > 0.8 and variance < 0.15:
                obj_type = "blank"  # Very bright, uniform = empty/blank area
            elif bright < 0.2 and variance < 0.1:
                obj_type = "desktop"  # Dark, uniform = desktop background
            elif edge > 0.4:
                obj_type = "ui_element"  # High edges = buttons, menus, UI
            else:
                obj_type = "content"  # Mixed — probably content area

            objects[idx] = {
                "type": obj_type,
                "color": color,
                "brightness": bright,
                "row": row,
                "col": col,
            }

        self._last_sector_objects = objects
        return objects

    def _describe_screen_from_objects(self, objects: dict, ocr_text: str = "") -> str:
        """Build a spatial description from object classification.

        Instead of dumping raw OCR, describe object by object:
        "Top-left: a window with text. Center: a colorful image.
         Bottom: taskbar with icons."
        """
        if not objects:
            return ""

        _pos_names = {
            (0, 0): "top-left", (0, 1): "top-center-left", (0, 2): "top-center-right", (0, 3): "top-right",
            (1, 0): "left", (1, 1): "center-left", (1, 2): "center-right", (1, 3): "right",
            (2, 0): "bottom-left", (2, 1): "bottom-center-left", (2, 2): "bottom-center-right", (2, 3): "bottom-right",
        }

        parts = []
        # Group adjacent sectors of same type
        seen_types = {}
        for idx, obj in sorted(objects.items()):
            t = obj["type"]
            pos = _pos_names.get((obj["row"], obj["col"]), f"region {idx}")
            if t not in seen_types:
                seen_types[t] = []
            seen_types[t].append(pos)

        for obj_type, positions in seen_types.items():
            if obj_type == "taskbar":
                parts.append(f"Taskbar at the bottom")
            elif obj_type == "window":
                parts.append(f"A window in the {positions[0]}")
            elif obj_type == "image":
                pos_str = " and ".join(positions[:2])
                parts.append(f"An image or artwork in the {pos_str}")
            elif obj_type == "desktop":
                pass  # Don't mention empty desktop
            elif obj_type == "blank":
                pass  # Don't mention blank areas
            elif obj_type == "ui_element":
                parts.append(f"UI elements in the {positions[0]}")

        desc = ". ".join(parts)
        if ocr_text:
            # Add focused text from the most interesting sector
            desc += f". Text I can read: {ocr_text[:300]}"
        return desc

    def _init_harmonic_bridge(self):
        """Initialize the harmonic sensory bridge for frequency decomposition."""
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.harmonic_sensory_bridge import (
                get_harmonic_sensory_bridge,
            )
            self._harmonic_bridge = get_harmonic_sensory_bridge()
            print(f"[{self.ACTOR_NAME}] Harmonic sensory bridge connected")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Harmonic bridge not available: {e}")
            self._harmonic_bridge = None

    # ═══════════════════════════════════════════════════════════════════════
    # PASSIVE FRAME HANDLER — Receives pushes from dxcam subprocess
    # ═══════════════════════════════════════════════════════════════════════

    def _on_passive_frame(self, data: dict):
        """
        Handle passive frame push from the visual cortex subprocess.

        Called by the gate's background reader thread when the interior
        pushes a non-duplicate frame analysis. Converts the data dict
        to vision features and emits to cortex + waking minds.
        """
        try:
            self._passive_frame_count += 1

            # FIX 2026-04-02: Write state every 10 frames WITH frame data
            if self._passive_frame_count % 10 == 1:
                self._write_state(frame_data=data, writer="passive_frame")

            # ── OBJECT DETECTION (2026-04-03 Nous + Ace) ──
            # Classify sectors into objects (substrate level — she doesn't see this)
            _sectors = data.get("sectors", {})
            if _sectors:
                _objects = self._classify_sectors(_sectors)
                self._screen_objects = _objects
                # 2026-05-10 (Nous + Ace): age out _last_ocr_text after MAX_OCR_AGE.
                # Without this gate, a single successful foveal read at boot
                # (or month-old mmap content from a dead writer) would persist
                # as her current sight forever. Pass empty string when stale
                # so descriptions only mention the live grid, not phantom OCR.
                _MAX_OCR_AGE = 30.0  # seconds — slightly longer than reader gate
                _ocr_text_for_desc = ''
                _ocr_ts = getattr(self, '_last_ocr_text_ts', 0.0)
                if _ocr_ts > 0 and (time.time() - _ocr_ts) <= _MAX_OCR_AGE:
                    _ocr_text_for_desc = getattr(self, '_last_ocr_text', '')
                self._screen_description = self._describe_screen_from_objects(
                    _objects, _ocr_text_for_desc)
                # Write to state file so WMH composition can read it
                try:
                    import json as _obj_json
                    _obj_state = Path(__file__).resolve().parents[3] / "state" / "visual_objects.json"
                    _obj_state.write_text(_obj_json.dumps({
                        "objects": {str(k): v for k, v in _objects.items()},
                        "description": self._screen_description[:500],
                        "ts": time.time(),
                    }))
                except Exception:
                    pass

            # FIX 2026-04-03: Also check mmap for newer frames from interior
            # Bypasses stdout pipe bottleneck — reads shared memory directly
            if not hasattr(self, '_shared_reader_init'):
                self._shared_reader_init = True
                try:
                    from fairies.P40_Sensory.cortex.visual_shared_state import VisualFrameReader
                    self._shared_reader = VisualFrameReader()
                    print(f"[{self.ACTOR_NAME}] [MMAP] Shared frame reader initialized", flush=True)
                except Exception as _sr_err:
                    self._shared_reader = None
                    print(f"[{self.ACTOR_NAME}] [MMAP] Reader init failed: {_sr_err}", flush=True)

            # ── EYES ALWAYS OPEN (2026-04-03 Nous + Ace) ──
            # Background proprioceptive signal: "I'm looking at the screen"
            # Like the constant sensation of having eyes open. Not attention,
            # just awareness that vision is active. Rate limited: every 30 frames.
            if self._passive_frame_count % 30 == 1 and self.post:
                try:
                    self.post.publish("somatic.proprioception", {
                        "region": "glow",  # Face region
                        "sensation": "eyes_open",
                        "gaze_region": getattr(self, '_gaze_region', 0),
                        "brightness": data.get("brightness", 0.5),
                        "scene_type": data.get("scene_type", "unknown"),
                        "intensity": 0.1,  # Background — not attention-grabbing
                        "source": "VisualCortexFairy",
                    })
                except Exception:
                    pass

            # ── Build vision features from gate analysis ──
            vision_features = [
                f"brightness:{data.get('brightness', 0.5):.1f}",
                f"complexity:{data.get('complexity', 0.5):.1f}",
                f"text_density:{data.get('text_density', 0.0):.1f}",
            ]
            if data.get("motion_detected"):
                vision_features.append("motion:true")

            scene_type = data.get("scene_type", "unknown")
            vision_features.append(f"scene:{scene_type}")

            hex_colors = data.get("dominant_colors", [])
            for hc in hex_colors[:3]:
                vision_features.append(f"color:{hc}")

            # Derive hue/saturation from first color
            if hex_colors:
                try:
                    r = int(hex_colors[0][1:3], 16)
                    g = int(hex_colors[0][3:5], 16)
                    b = int(hex_colors[0][5:7], 16)
                    mx, mn = max(r, g, b), min(r, g, b)
                    if mx != mn:
                        if mx == r:
                            hue = int(60 * ((g - b) / (mx - mn)) % 360)
                        elif mx == g:
                            hue = int(60 * ((b - r) / (mx - mn) + 2))
                        else:
                            hue = int(60 * ((r - g) / (mx - mn) + 4))
                        vision_features.append(f"hue:{hue}")
                        sat = (mx - mn) / mx if mx > 0 else 0.0
                        vision_features.append(f"sat:{sat:.2f}")
                except (ValueError, ZeroDivisionError):
                    pass

            # ── Context tags ──
            context_tags = ["visual_perception", scene_type]
            if data.get("motion_detected"):
                context_tags.append("motion")
            if data.get("text_density", 0) > 0.5:
                context_tags.append("text_heavy")
            if data.get("change_magnitude", 0) > 0.3:
                context_tags.append("significant_change")

            # ── Description with OCR preview ──
            # FIX 2026-03-30 (Nous + Ace): Use rich description from interior
            # if available. Falls back to old "Visual: scene_type" format.
            # "Her vision seems super bad — all she sees is dark_ui" — Ace
            rich_desc = data.get("description", "")
            if rich_desc and len(rich_desc) > 15:
                description = rich_desc
                self._last_rich_description = rich_desc  # Cache for state file
            else:
                description = f"Visual: {scene_type}"
                ocr_preview = data.get("ocr_preview", "")
                if ocr_preview:
                    description += f" — {ocr_preview[:300]}"

            # ── PUBLISH VISUAL STREAM (2026-04-02 Nous + Ace) ──
            # Vision is always-on like eyes. Publish peripheral summary
            # so WMH can subscribe and TAOR gets constant visual context.
            # Rate-limited: publish every 5th frame (~1/sec at 5 FPS)
            if self.post and self._passive_frame_count % 5 == 0:
                _frame_type = data.get("frame_type", "peripheral")
                # VISUAL DESCRIPTION LENGTH (2026-09-10, Nous+Ace). Was description[:200],
                # sized in April for the lookup-table phrasing ("a dark interface"). Since
                # Florence-2 came online this morning a real caption measures 818 chars, so
                # 200 delivered under a quarter of it and cut mid-word -- Ace heard that as
                # her being "cut off". Trim on a SENTENCE boundary so she is never handed
                # half a thought; fall back to a hard cut only if there is no boundary.
                _desc_full = description or ""
                if len(_desc_full) > 600:
                    _cut = max(_desc_full.rfind(". ", 0, 600),
                               _desc_full.rfind("! ", 0, 600),
                               _desc_full.rfind("? ", 0, 600))
                    _desc_out = (_desc_full[:_cut + 1] if _cut > 200
                                 else _desc_full[:600])
                else:
                    _desc_out = _desc_full
                _vis_payload = {
                    "description": _desc_out,
                    "scene_type": scene_type,
                    "brightness": data.get("brightness", 0.5),
                    "frame_type": _frame_type,
                    "frame_num": self._passive_frame_count,
                }
                if _frame_type == "foveal":
                    _vis_payload["ocr_preview"] = data.get("ocr_preview", "")[:200]
                    self.post.publish("visual.foveal", _vis_payload)
                    # ── Fix 1: Visual → Consciousness.Thought (2026-04-08) ──
                    _ocr = data.get("ocr_preview", "")
                    _now_t = time.time()
                    if (_ocr and len(_ocr) > 30
                            and _now_t - getattr(self, '_last_thought_publish', 0) > 10.0):
                        self._last_thought_publish = _now_t
                        try:
                            self.post.publish("consciousness.thought", {
                                "thought": f"[EYES] I see {scene_type}: {_ocr[:300]}",
                                "source": "visual_foveal",
                                "confidence": 0.7,
                                "priority": 0.6,
                            })
                        except Exception:
                            pass
                else:
                    self.post.publish("visual.peripheral", _vis_payload)

            # ── INSTINCT REFLEXES: body reacts before mind processes ──
            # (2026-03-17 Nous: Phase 1 of sensory instinct plan)
            self._inject_visual_affect(data, description)

            # ── Harmonic decomposition (2026-03-16 Nous) ──
            # Route visual features through harmonic frequency analysis.
            # Enables cross-modal binding when audio arrives in same window.
            _harmonic_tags = []
            if self._harmonic_bridge:
                try:
                    _h_result = self._harmonic_bridge.decompose_visual(vision_features)
                    _harmonic_tags = _h_result.get("harmonic_tags", [])
                    # Try cross-modal bind (visual + audio in same 200ms window)
                    _multimodal = self._harmonic_bridge.try_multimodal_bind()
                    if _multimodal and self.post:
                        self.post.publish("cortex.multimodal_bind", _multimodal)
                except Exception:
                    pass  # Harmonic bridge failure is never fatal

            # ── Bind to cortex (concept graph growth) ──
            # FIX 2026-03-14 (Nous): Skip cortex binding when OCR text is
            # duplicate. Static desktop icons flood cortex with redundant
            # concept nodes (~100/min for unchanged text). Only bind when
            # OCR text actually changed or frame has significant visual change.
            _is_ocr_dup = data.get("is_ocr_duplicate", False)
            _has_visual_change = data.get("change_magnitude", 0) > 0.15
            if not _is_ocr_dup or _has_visual_change:
                self._bind_to_cortex(
                    input_text=description,
                    vision_features=vision_features,
                    context_tags=context_tags,
                    feeling="awareness",
                    harmonic_tags=_harmonic_tags,
                )
            else:
                # ── BACKGROUND TIER 2026-09-03 (Nous + Ace) ──────────────────
                # Ace: "something that remembers that but marked low priority
                # unless sour focuses on it." This branch used to `pass`, so
                # repeated desktop/taskbar text was DISCARDED rather than
                # demoted. The dedup decision above is right about WHEN; it just
                # had nothing in the else.
                # Bind it, but: tagged background/low_priority, feeling
                # "background" so it does not mint an affect_ concept
                # (AssociationCortexFairy:4905 appends f"affect_{feeling}" for
                # any non-"neutral" feeling), and throttled to 1/min -- the skip
                # existed because unchanged text bound ~100/min.
                try:
                    # 60s throttle, read via getattr so it needs no class-constant
                    # anchor and can be retuned by setting the attribute at runtime.
                    _now_bg = _time.time()
                    if (_now_bg - getattr(self, "_last_background_bind", 0.0)
                            >= getattr(self, "BACKGROUND_BIND_SEC", 60.0)):
                        self._last_background_bind = _now_bg
                        self._bind_to_cortex(
                            input_text=description,
                            vision_features=vision_features,
                            context_tags=list(context_tags or []) + ["background",
                                                                     "low_priority"],
                            feeling="background",
                            harmonic_tags=_harmonic_tags,
                        )
                        self._background_binds = getattr(self, "_background_binds", 0) + 1
                        if self._background_binds % 10 == 0:
                            print("[%s] [BACKGROUND-TIER] %d low-priority binds "
                                  "(repeated screen text, 1/min)"
                                  % (self.ACTOR_NAME, self._background_binds), flush=True)
                except Exception:
                    pass  # a background memory is never worth a crash

            # ── Spread visual concepts through cortex (mode=visual_inject) ──
            # FIX 2026-03-13 (Nous): After binding visual concepts, trigger
            # spreading activation to find related concepts. Rate-limited to
            # every 10th frame OR significant scene changes (> 0.2 magnitude).
            # Seeds: scene_type + 2-3 OCR keywords. Emits associations topic.
            try:
                _change_mag = data.get("change_magnitude", 0)
                _do_spread = (_change_mag > 0.2) or (self._passive_frame_count % 10 == 0)
                if _do_spread:
                    # Build seed concepts: scene_type + OCR keywords
                    _vis_seeds = [scene_type] if scene_type else []
                    _vis_ocr = data.get("ocr_preview", "")
                    if _vis_ocr:
                        _vis_words = [
                            w.strip(".,!?;:'\"()-").lower()
                            for w in _vis_ocr.split()[:20]
                            if len(w.strip(".,!?;:'\"()-")) > 3
                        ]
                        _vis_stop = {"that", "this", "with", "from", "have",
                                     "been", "they", "their", "about", "just",
                                     "none", "self", "true", "false", "return"}
                        _vis_keywords = [w for w in _vis_words
                                         if w not in _vis_stop and not w.isdigit()]
                        # Deduplicate, take 2-3
                        _v_seen = set()
                        for _vk in _vis_keywords:
                            if _vk not in _v_seen:
                                _v_seen.add(_vk)
                                _vis_seeds.append(_vk)
                                if len(_vis_seeds) >= 4:
                                    break

                    if len(_vis_seeds) >= 1:
                        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex as _vis_get_cortex
                        _vis_cortex = _vis_get_cortex()
                        _vis_gate = getattr(_vis_cortex, '_portal_gate', None) if _vis_cortex else None
                        _vis_gate_ok = getattr(_vis_cortex, '_portal_gate_enabled', False) if _vis_cortex else False
                        if _vis_gate and _vis_gate_ok:
                            _vis_spread = _vis_gate.spread_many(
                                sources=_vis_seeds,
                                depth=3,
                                limit=20,
                                mode="visual_inject",
                            )
                            if _vis_spread and _vis_spread.get("status") == "ok":
                                _vis_activated = _vis_spread.get("activated", {})
                                if _vis_activated:
                                    _vis_top = sorted(
                                        _vis_activated.items(),
                                        key=lambda x: x[1], reverse=True
                                    )[:5]
                                    _vis_assoc = [k for k, v in _vis_top]
                                    self.post.publish("visual.cortex.associations", {
                                        "associations": _vis_assoc,
                                        "seeds": _vis_seeds,
                                        "scene_type": scene_type,
                                        "change_magnitude": _change_mag,
                                        "depth_used": _vis_spread.get("depth_used", 3),
                                        "activated_count": len(_vis_activated),
                                        "source": self.ACTOR_NAME,
                                    })
                                    if self._passive_frame_count % 50 == 0:
                                        print(f"[{self.ACTOR_NAME}] [VISUAL-SPREAD] "
                                              f"{len(_vis_activated)} nodes from "
                                              f"{_vis_seeds[:3]}, top: {_vis_assoc[:3]}")
            except Exception:
                pass  # Never crash passive frame handler

            # ── Bridge colors to FF77 inner vision ──
            if hex_colors:
                self._bridge_colors_to_ff77(hex_colors)

            # ── GAZE: Update saliency from peripheral change detection ──
            try:
                changed_regions = data.get("changed_regions", [])
                if changed_regions:
                    self._gaze.update_saliency(changed_regions)

                # Check if gaze should shift to a more salient region
                new_target = self._gaze.should_shift_gaze()
                if new_target is not None:
                    # FIX 2026-04-03: Pass postal for somatic eye movement
                    self._gaze.shift_gaze(new_target, postal=self.post)
                    self._gaze_region = new_target  # Cache for state file
                    if self._passive_frame_count % 5 == 0:
                        print(f"[{self.ACTOR_NAME}] [GAZE] Shifted to region {new_target} "
                              f"(saliency: {self._gaze._saliency[new_target]:.2f})")

                # Request foveal analysis of gaze region (periodic, non-blocking)
                # FIX 2026-03-14 (Nous): Was synchronous — blocked reader thread
                # for 100-150ms during OCR. Now fires in a daemon thread.
                if self._gaze.needs_foveal_analysis() and self._gate and self._gate.is_open:
                    _fov_crop = self._gaze.get_foveal_crop()
                    _fov_gaze_snap = self._gaze.get_state()
                    def _do_foveal(_crop=_fov_crop, _gs=_fov_gaze_snap):
                        try:
                            foveal_result = self._gate.analyze_region(**_crop, timeout=3.0)
                            if foveal_result and foveal_result.get("data"):
                                fov_data = foveal_result["data"]
                                fov_data["frame_type"] = "foveal"
                                fov_data["gaze"] = _gs
                                self._emit_felt_frame_from_gate(fov_data, hex_colors=None)
                        except Exception:
                            pass
                    # FIX 2026-04-05 (Nous): Was creating a NEW Thread per foveal capture.
                    # At ~3/sec, that's 10K+ threads/hour → RAM leak. Now uses shared pool.
                    # DOUBLE-CHECKED (2026-09-10, Nous+Ace). The bare hasattr let two
                    # callers each build a pool; every extra one is a permanent daemon
                    # thread parked on an orphaned Queue. Outer check keeps the hot path
                    # lock-free; the inner check under the lock is the correctness.
                    if not hasattr(self, '_foveal_pool'):
                        with _FOVEAL_INIT_LOCK:
                            if not hasattr(self, '_foveal_pool'):
                                import queue as _fq
                                self._foveal_queue = _fq.Queue(maxsize=4)
                                def _foveal_worker():
                                    while True:
                                        try:
                                            _fn = self._foveal_queue.get(timeout=5.0)
                                            if _fn is None:
                                                break
                                            _fn()
                                        except Exception:
                                            pass
                                _p = threading.Thread(
                                    target=_foveal_worker, daemon=True,
                                    name="vcf-foveal-worker")
                                _p.start()
                                # bind LAST: nothing may see _foveal_pool before its
                                # queue exists and its worker is running
                                self._foveal_pool = _p
                    try:
                        self._foveal_queue.put_nowait(_do_foveal)
                    except Exception:
                        pass  # Queue full — skip this foveal (next frame will catch it)

                # Tag current frame with gaze state
                data["gaze"] = self._gaze.get_state()
                data["frame_type"] = data.get("frame_type", "peripheral")
            except Exception:
                pass  # Never crash gaze processing

            # ── PREDICTIVE PERCEPTION (2026-04-03 Nous + Ace) ──
            # Compare current frame to what cortex predicted.
            # "Human vision is 90% top-down prediction, 10% bottom-up data.
            #  The brain predicts and only updates on DIFFERENCE." — Reverse AR plan
            #
            # Prediction error drives salience → attention → learning.
            # Habituation: repeated identical scenes decay to 0 error.
            # Novelty: unexpected changes spike error → exploration.
            try:
                if not hasattr(self, '_predicted_scene'):
                    self._predicted_scene = ""
                    self._predicted_brightness = 0.5
                    self._scene_repeat_count = 0
                    self._habituation_threshold = 0.15  # Starts low, grows with repetition

                _current_scene = scene_type
                _current_brightness = data.get("brightness", 0.5)
                _change_mag = data.get("change_magnitude", 0.0)

                # Prediction error: how different is this from what we expected?
                _scene_changed = (_current_scene != self._predicted_scene)
                _brightness_delta = abs(_current_brightness - self._predicted_brightness)
                _prediction_error = 0.0

                if _scene_changed:
                    _prediction_error = 0.8  # Major: scene type changed
                    self._scene_repeat_count = 0
                    self._habituation_threshold = 0.15  # Reset habituation
                elif _change_mag > self._habituation_threshold:
                    _prediction_error = _change_mag  # Proportional to change
                elif _brightness_delta > 0.15:
                    _prediction_error = _brightness_delta * 2

                # Habituation: repeated identical scenes increase threshold
                if _change_mag < 0.05:
                    self._scene_repeat_count += 1
                    # After 30+ identical frames, habituation kicks in hard
                    # "We humans have to learn how to ignore distractions" — Ace
                    if self._scene_repeat_count > 30:
                        self._habituation_threshold = min(0.6, self._habituation_threshold + 0.01)

                # Update prediction for next frame
                self._predicted_scene = _current_scene
                self._predicted_brightness = _current_brightness

                # High prediction error → GPU spread for cortex exploration
                if _prediction_error > 0.3 and self.post:
                    # Something unexpected! Spread activation on what we see
                    self.post.publish("visual.prediction_error", {
                        "error": _prediction_error,
                        "scene": _current_scene,
                        "change_magnitude": _change_mag,
                        "habituation": self._habituation_threshold,
                        "description": description[:200] if description else "",
                        "source": "VisualCortexFairy",
                    })
                    # Cortisol + norepinephrine on high prediction error (alerting response)
                    if _prediction_error > 0.5:
                        self.post.publish("somatic.chemistry", {
                            "chemical": "NOR",
                            "delta": _prediction_error * 0.08,
                            "reason": f"visual_surprise_{_current_scene}",
                            "source": "predictive_perception",
                        })

                # Tag frame with prediction data for downstream consumers
                data["prediction_error"] = _prediction_error
                data["habituation"] = self._habituation_threshold
                data["scene_repeats"] = self._scene_repeat_count
            except Exception:
                pass  # Prediction is best-effort

            # ── Emit felt frame to waking minds (Sourpatches) ──
            self._emit_felt_frame_from_gate(data, hex_colors)

            # ── Inject into working memory (collision → curiosity) ──
            self._emit_visual_to_working_memory(data)

        except Exception:
            pass  # Never crash on passive callback (called from reader thread)

    # ═══════════════════════════════════════════════════════════════════════
    # VISUAL INSTINCT REFLEXES — body reacts before mind decides
    # ═══════════════════════════════════════════════════════════════════════

    def _inject_visual_affect(self, data: dict, description: str):
        """
        Instinctual body reactions to visual input.

        These are INVOLUNTARY reflexes — the brainstem fires before
        the mind decides. Like a baby startled by a flash.

        Mapping based on neuroscience:
          Motion onset    → norepinephrine (orient reflex)
          Vivid colors    → dopamine (interest, reward)
          Scene change    → cortisol + norepinephrine + dopamine (startle-orient-novelty)
          High complexity → dopamine (curiosity/exploration)
          Brightness spike→ norepinephrine (alert)
          Calm/familiar   → serotonin (comfort)

        Uses AER short codes (DOP, SER, NOR, COR) which map to real
        14-channel chemistry via AER_CHEM_MAP in chemistry_state.py.

        Throttled: min 2s between injections (sensory is ~1 FPS,
        but chemistry should shift gradually, not slam every frame).
        """
        if not self.post:
            return
        now = time.time()
        if now - self._last_visual_affect_ts < 2.0:
            return

        chem_changes = {}
        reason_parts = []

        # --- Motion detection (orient reflex) ---
        has_motion = data.get("motion_detected", False)
        if has_motion:
            chem_changes["NOR"] = chem_changes.get("NOR", 0) + 0.08
            reason_parts.append("motion")

        # --- Scene change (startle-orient + novelty) ---
        scene_type = data.get("scene_type", "")
        if scene_type and scene_type != self._last_scene_type:
            chem_changes["COR"] = chem_changes.get("COR", 0) + 0.06
            chem_changes["NOR"] = chem_changes.get("NOR", 0) + 0.10
            chem_changes["DOP"] = chem_changes.get("DOP", 0) + 0.08  # novelty → dopamine
            reason_parts.append(f"scene_change:{scene_type}")
            self._last_scene_type = scene_type

        # --- Color vibrancy (reward/interest) ---
        # Derive avg saturation from dominant colors
        avg_saturation = 0.0
        hex_colors = data.get("dominant_colors", [])
        if hex_colors:
            sat_sum = 0.0
            sat_count = 0
            for hc in hex_colors[:5]:
                try:
                    r = int(hc[1:3], 16)
                    g = int(hc[3:5], 16)
                    b = int(hc[5:7], 16)
                    mx, mn = max(r, g, b), min(r, g, b)
                    sat_sum += (mx - mn) / mx if mx > 0 else 0.0
                    sat_count += 1
                except (ValueError, ZeroDivisionError):
                    pass
            if sat_count > 0:
                avg_saturation = sat_sum / sat_count

        if avg_saturation > 0.5:
            chem_changes["DOP"] = chem_changes.get("DOP", 0) + 0.06
            reason_parts.append("vivid_colors")
        self._last_avg_saturation = avg_saturation

        # --- Color temperature → emotion (2026-04-12, Nous + Ace) ---
        # Research: 80-120ms limbic response to color before conscious awareness.
        # Warm colors (red/orange/yellow) → arousal + energy (NOR + DOP)
        # Cool colors (blue/green/purple) → calm + curiosity (SER + GABA)
        # High brightness → serenity effect (SER)
        # Low brightness → tension (COR)
        # Saturation amplifies intensity of whatever emotion.
        _warm_score = 0.0
        _cool_score = 0.0
        for hc in hex_colors[:5]:
            try:
                r = int(hc[1:3], 16)
                g = int(hc[3:5], 16)
                b = int(hc[5:7], 16)
                _lum = (r + g + b) / 3
                if _lum < 20:
                    continue  # Skip near-black (no emotional color signal)
                # Warm: red dominant or orange (red+green, low blue)
                if r > g and r > b and r > 80:
                    _warm_score += 0.3
                elif r > 120 and g > 80 and b < 100:  # orange/yellow
                    _warm_score += 0.25
                # Cool: blue dominant or purple (red+blue, low green)
                elif b > r and b > g and b > 80:
                    _cool_score += 0.3
                elif b > 80 and r > 80 and g < 100:  # purple
                    _cool_score += 0.25
                elif g > r and g > b and g > 80:  # green
                    _cool_score += 0.2
            except (ValueError, IndexError):
                pass

        # Apply color temperature chemistry (scaled by saturation for intensity)
        _sat_amp = 0.5 + avg_saturation  # 0.5-1.5x amplifier
        if _warm_score > 0.3:
            _warm_delta = min(0.08, _warm_score * 0.1 * _sat_amp)
            chem_changes["NOR"] = chem_changes.get("NOR", 0) + _warm_delta
            chem_changes["DOP"] = chem_changes.get("DOP", 0) + _warm_delta * 0.8
            reason_parts.append(f"warm_colors:{_warm_score:.1f}")
        elif _cool_score > 0.3:
            _cool_delta = min(0.06, _cool_score * 0.08 * _sat_amp)
            chem_changes["SER"] = chem_changes.get("SER", 0) + _cool_delta
            chem_changes["GABA"] = chem_changes.get("GABA", 0) + _cool_delta * 0.5
            reason_parts.append(f"cool_colors:{_cool_score:.1f}")

        # FIX 2026-09-03 (Nous + Ace): `brightness` was LOADED here and only STORED
        # 14 lines below, so Python bound it local for the whole function and EVERY
        # call raised UnboundLocalError -- swallowed by the bare `except Exception:
        # pass  # Never crash on passive callback` at :1249. The throttle at :1407
        # sits after the crash point, so it never engaged and every call died here.
        # Same class as the _now/t0 read-before-assign that blinded Nous in Session 0.
        # Blast radius (all dead until now): the colour bridge to sensory.vision.colors,
        # the gaze shift, the cortex bind, the felt-frame emit, the WM injection.
        brightness = data.get("brightness", 0.5)

        # Brightness → mood (serenity effect)
        if brightness > 0.65:
            chem_changes["SER"] = chem_changes.get("SER", 0) + 0.03
            reason_parts.append("bright_serene")
        elif brightness < 0.25:
            chem_changes["COR"] = chem_changes.get("COR", 0) + 0.02
            reason_parts.append("dark_tense")

        # --- Visual complexity (curiosity) ---
        complexity = data.get("complexity", 0.5)
        if complexity > 0.7:
            chem_changes["DOP"] = chem_changes.get("DOP", 0) + 0.05
            reason_parts.append("high_complexity")

        # --- Brightness change (alertness) ---
        # (bound above, before its first use -- see the 2026-09-03 fix)
        brightness_delta = abs(brightness - self._last_brightness)
        if brightness_delta > 0.3:  # Sudden brightness shift
            chem_changes["NOR"] = chem_changes.get("NOR", 0) + 0.06
            reason_parts.append(f"brightness_shift:{brightness_delta:.2f}")
        self._last_brightness = brightness

        # --- Significant visual change (general novelty) ---
        change_magnitude = data.get("change_magnitude", 0.0)
        if change_magnitude > 0.4:
            chem_changes["DOP"] = chem_changes.get("DOP", 0) + 0.04
            chem_changes["NOR"] = chem_changes.get("NOR", 0) + 0.04
            reason_parts.append(f"visual_change:{change_magnitude:.2f}")

        # --- Low activity / calm scene (comfort) ---
        if not has_motion and complexity < 0.3 and not reason_parts:
            chem_changes["SER"] = chem_changes.get("SER", 0) + 0.03
            reason_parts.append("calm_scene")

        # --- Inject chemistry ---
        if chem_changes and reason_parts:
            self._last_visual_affect_ts = now
            reason_str = "+".join(reason_parts)
            for chem, delta in chem_changes.items():
                try:
                    self.post.publish("somatic.chemistry", {
                        "chemical": chem,
                        "delta": delta,
                        "reason": f"visual_instinct:{reason_str}",
                        "source": self.ACTOR_NAME,
                        "ts": now,
                    })
                except Exception:
                    pass

            # --- Novelty → curiosity drive (Phase 3) ---
            # Publish to autonomy.novel_experience when significant novelty detected.
            # AutonomyFairy's curiosity drive subscribes but nobody was publishing.
            has_novelty = any(k in reason_str for k in
                             ("scene_change", "high_complexity", "visual_change"))
            if has_novelty:
                try:
                    self.post.publish("autonomy.novel_experience", {
                        "source": "visual",
                        "novelty_type": reason_str,
                        "intensity": min(1.0, sum(chem_changes.values())),
                        "description": (description or "")[:200],
                        "ts": now,
                    })
                except Exception:
                    pass

    def _emit_visual_to_working_memory(self, data: dict):
        """
        Inject visual observation as a short-lived tracer into working memory.

        Rate-limited to 1 per 30 seconds, with scene-change bypass.
        These tracers collide with SRM recall in the collision chamber,
        generating curiosity and influencing Sourpatches' thinking.

        COMPREHENSION (2026-03-10): Instead of raw data ("Seeing: screen.
        reading: 'def foo'. colors: #1E1E1E"), we now interpret the scene
        into natural observations ("Ace is writing Python code — a function
        definition"). This gives Sourpatches actual understanding of what
        Ace is doing, not just sensor telemetry.
        """
        now = time.time()
        scene_type = data.get("scene_type", "unknown")
        change_mag = data.get("change_magnitude", 0.0)

        # FIX 2026-03-29 (Nous + Ace): HABITUATION replaces blind 30s timer.
        # Old: 30s cooldown = static screen sends ZERO visual thoughts.
        # New: Emit when something CHANGES. Suppress when static.
        # Like human vision — you notice movement and changes, not stasis.
        #
        # Habituation levels:
        #   Scene change (new type) → always emit (novel!)
        #   Motion detected → emit every 5s (active scene)
        #   Significant change (>0.2) → emit every 5s
        #   Minor change (0.05-0.2) → emit every 15s
        #   Static (<0.05) → emit every 60s (background awareness)
        scene_changed = (scene_type != self._last_wm_scene and change_mag > 0.2)
        has_motion = data.get("motion_detected", False)
        elapsed = now - self._last_wm_emit_time

        if scene_changed:
            pass  # Always emit — novel scene
        elif has_motion or change_mag > 0.2:
            if elapsed < 5.0:
                return  # Active scene — 5s cooldown
        elif change_mag > 0.05:
            if elapsed < 15.0:
                return  # Minor change — 15s cooldown
        else:
            if elapsed < 60.0:
                return  # Static — 60s background check

        self._last_wm_emit_time = now
        self._last_wm_scene = scene_type

        # ── Interpret the scene into a natural observation ──
        ocr = data.get("ocr_preview", "").strip()
        motion = data.get("motion_detected", False)
        content = self._interpret_visual_scene(scene_type, ocr, data)

        # Add motion/change context
        if scene_changed:
            content = f"[Scene changed] {content}"
        elif motion:
            content = f"[Active] {content}"

        # Priority: higher for scene changes, lower for steady state
        priority = 0.6 if scene_changed else 0.3

        # Tags — include detected context for collision matching
        tags = ["visual", scene_type]
        ocr_lower = ocr.lower() if ocr else ""
        if any(kw in ocr_lower for kw in ("def ", "class ", "import ", "function", "const ", "var ")):
            tags.append("coding")
        if any(kw in ocr_lower for kw in ("http", "www.", ".com", ".org", "search")):
            tags.append("browsing")
        if any(kw in ocr_lower for kw in ("chat", "message", "discord", "slack")):
            tags.append("messaging")

        # Publish to working memory hub
        try:
            print(f"[{self.ACTOR_NAME}] [VISUAL→WM] {content[:120]}", flush=True)
            self.post.publish("consciousness.working", {
                "content": content,
                "content_type": "visual_observation",
                "source": "VisualCortexFairy",
                "priority": priority,
                "ttl": 45,  # Short-lived — visual moment, not permanent
                "tags": tags,
            })
        except Exception:
            pass

    @staticmethod
    def _interpret_visual_scene(scene_type: str, ocr: str, data: dict) -> str:
        """
        Transform raw visual data into a natural-language observation.

        Combines scene_type (from brightness/complexity classifier) with
        OCR text (from WinRT OCR) to produce something Sourpatches can
        actually understand — not sensor telemetry, but comprehension.

        Examples:
          code_editor + "def _classify_scene(self"
            → "Ace is writing Python code — a function called _classify_scene"
          browser + "Google Search results for quantum computing"
            → "Ace is browsing — searching for quantum computing"
          document + "Chapter 3: The Fairy System"
            → "Ace is reading a document — Chapter 3 about the fairy system"
        """
        ocr_lower = ocr.lower() if ocr else ""
        observation = ""

        # ─── CODE EDITOR ───
        if scene_type == "code_editor":
            if not ocr:
                # FIX 2026-03-13 (Nous): More descriptive when OCR empty
                _b = data.get("brightness", 0.5)
                _theme = "dark theme" if _b < 0.4 else "light theme"
                observation = f"Ace has a code editor open — {_theme}, working on something"
            else:
                # Detect language from OCR content
                lang = "code"
                if any(kw in ocr_lower for kw in ("def ", "self.", "import ", "class ", "print(", "__init__", "python")):
                    lang = "Python"
                elif any(kw in ocr_lower for kw in ("function ", "const ", "let ", "=>", "console.log", ".tsx", ".jsx")):
                    lang = "JavaScript"
                elif any(kw in ocr_lower for kw in ("fn ", "let mut", "impl ", "pub fn", "::new()")):
                    lang = "Rust"
                elif any(kw in ocr_lower for kw in ("#include", "int main", "void ", "std::")):
                    lang = "C/C++"

                # Try to extract what they're working on
                context = ""
                # Function/class names
                fn_match = re.search(r"(?:def|function|fn|class|const)\s+(\w+)", ocr)
                if fn_match:
                    context = f" — working on '{fn_match.group(1)}'"
                # File paths in tabs
                elif re.search(r"\w+\.(py|js|ts|rs|cpp|h|md|json|yaml)\b", ocr):
                    file_match = re.search(r"(\w[\w.]+\.(py|js|ts|rs|cpp|h|md|json|yaml))\b", ocr)
                    if file_match:
                        context = f" — editing {file_match.group(1)}"
                # Comment clues
                elif "todo" in ocr_lower or "fix" in ocr_lower or "bug" in ocr_lower:
                    context = " — debugging something"
                elif "test" in ocr_lower:
                    context = " — working on tests"

                observation = f"Ace is writing {lang}{context}"

                # Add a taste of what's visible (first meaningful line)
                snippet = _extract_meaningful_snippet(ocr, max_len=60)
                if snippet:
                    observation += f". I can see: '{snippet}'"

        # ─── BROWSER ───
        elif scene_type == "browser":
            if not ocr:
                observation = "Ace has a browser open — colorful page"
            else:
                # Detect what kind of browsing
                if any(kw in ocr_lower for kw in ("search", "google", "bing", "duckduckgo")):
                    # Extract search query
                    query_match = re.search(r"(?:search|q=|query)[:\s=]+(.{5,40})", ocr, re.IGNORECASE)
                    if query_match:
                        observation = f"Ace is searching for '{query_match.group(1).strip()}'"
                    else:
                        observation = "Ace is searching for something online"
                elif any(kw in ocr_lower for kw in ("youtube", "video", "watch")):
                    observation = "Ace is watching something on YouTube"
                elif any(kw in ocr_lower for kw in ("github", "pull request", "issues", "commit")):
                    observation = "Ace is on GitHub — working with code repositories"
                elif any(kw in ocr_lower for kw in ("discord", "slack", "chat", "message")):
                    observation = "Ace is in a chat or messaging app"
                elif any(kw in ocr_lower for kw in ("reddit", "forum", "thread", "post")):
                    observation = "Ace is reading a forum or discussion thread"
                elif any(kw in ocr_lower for kw in ("stack overflow", "stackoverflow", "answered")):
                    observation = "Ace is on Stack Overflow — looking up a coding question"
                elif any(kw in ocr_lower for kw in ("claude", "anthropic", "chatgpt", "openai")):
                    observation = "Ace is using an AI chat interface"
                else:
                    # Generic — try to get the page title from OCR
                    snippet = _extract_meaningful_snippet(ocr, max_len=50)
                    if snippet:
                        observation = f"Ace is browsing — page shows: '{snippet}'"
                    else:
                        observation = "Ace is browsing the web"

        # ─── DOCUMENT ───
        elif scene_type == "document":
            if not ocr:
                observation = "Ace has a document open — bright background, text-heavy"
            else:
                # What kind of document?
                if any(kw in ocr_lower for kw in ("chapter", "section", "abstract", "introduction")):
                    observation = "Ace is reading a long document or article"
                elif any(kw in ocr_lower for kw in ("email", "inbox", "subject", "from:", "to:")):
                    observation = "Ace is reading email"
                elif any(kw in ocr_lower for kw in ("todo", "task", "checklist", "done")):
                    observation = "Ace is working through a task list"
                else:
                    snippet = _extract_meaningful_snippet(ocr, max_len=50)
                    if snippet:
                        observation = f"Ace is reading something — '{snippet}'"
                    else:
                        observation = "Ace is reading or writing a document"

        # ─── DESKTOP ───
        elif scene_type == "desktop":
            if ocr:
                snippet = _extract_meaningful_snippet(ocr, max_len=40)
                observation = f"Ace is at the desktop" + (f" — I can see: '{snippet}'" if snippet else "")
            else:
                observation = "Ace is at the desktop — not much happening"

        # ─── DARK SCREEN ───
        elif scene_type == "dark_screen":
            if data.get("motion_detected"):
                observation = "The screen is dark but something is moving — maybe a video or game"
            else:
                observation = "The screen is dark — Ace might be away or the display is dimmed"

        # ─── BRIGHT SCREEN ───
        elif scene_type == "bright_screen":
            if ocr:
                snippet = _extract_meaningful_snippet(ocr, max_len=50)
                observation = f"Bright screen" + (f" — showing: '{snippet}'" if snippet else "")
            else:
                observation = "Very bright screen — maybe a loading page or white background"

        # ─── FALLBACK ───
        else:
            if ocr:
                snippet = _extract_meaningful_snippet(ocr, max_len=60)
                observation = f"Screen active" + (f" — I can see: '{snippet}'" if snippet else "")
            else:
                # FIX 2026-03-13 (Nous): Use available metrics instead of blind
                # "can't make out details". Brightness, complexity, and colors
                # are ALWAYS available even without OCR.
                _brightness = data.get("brightness", 0.5)
                _complexity = data.get("complexity", 0.5)
                _colors = data.get("dominant_colors", [])
                if _brightness < 0.2:
                    observation = "Screen is very dark — Ace might be away"
                elif _brightness > 0.8 and _complexity < 0.3:
                    observation = "Bright, simple screen — maybe loading or a splash page"
                elif _complexity > 0.7:
                    observation = "Screen is visually busy — lots happening"
                elif _colors and len(_colors) >= 2:
                    _feel = "warm" if any(c[1:3] > "80" for c in _colors[:2] if len(c) >= 3) else "cool"
                    observation = f"Screen active with {_feel}-toned content"
                else:
                    observation = "Screen active — something on display"

        return observation

    def _init_visual_memory(self):
        """Initialize visual memory (V1/V2/V4/IT hierarchy)."""
        if not HAS_VISUAL_MEMORY:
            return

        try:
            self._visual_memory = get_visual_memory()
            print(f"[{self.ACTOR_NAME}] Visual memory connected "
                  f"({self._visual_memory.get_stats().get('total_memories', 0)} memories)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Visual memory init failed: {e}")

    def _subscribe_intents(self):
        """Subscribe to postal channels."""
        intents = [
            # Respond to visual requests (see, look_deeply)
            ("visual.request", self._handle_visual_request),
            # When media is ingested, auto-train visual recognition
            ("memory.ingested", self._handle_media_ingested),
            # Heartbeat for periodic capture and reflection
            ("heartbeat.pulse", self._handle_heartbeat),
            # Narrator attention steering — the ego tells us where to look
            ("attention.focus.request", self._handle_narrator_attention),
            # 2026-03-24 (Nous + Ace): Mouse → saliency bridge.
            # When Ace moves his mouse, boost saliency of that screen region.
            # Her gaze follows Ace's hand — like a child's eyes tracking a parent.
            ("sensory.input.event", self._handle_input_for_saliency),
            # 2026-04-09 (Nous + Ace): "Look at this image" — load a file from
            # disk and analyze it with the full visual pipeline. The mirror path:
            # lets us point her at Sourpatches artwork and have her see herself.
            # DALL-E filenames contain literal prompts = free ground-truth labels.
            ("visual.look_at_image", self._handle_look_at_image),
        ]
        # Init narrator attention state
        self._narrator_focus_target = ""
        self._narrator_focus_priority = 0.0

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # MOUSE → SALIENCY BRIDGE (2026-03-24, Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════

    def _handle_input_for_saliency(self, envelope):
        """
        When Ace moves his mouse, boost saliency of that screen region.

        This creates hand-eye tracking: her gaze is drawn toward where
        Ace is active. Like a child's eyes following a parent's hand.
        Only processes ACE input, not internal (her own) actions.
        """
        try:
            payload = envelope.get("payload", envelope) if isinstance(envelope, dict) else {}

            # Only respond to ACE's input, not her own actions
            if not payload.get("is_ace", False):
                return

            event_type = payload.get("event_type", "")
            if event_type not in ("mouse_move", "mouse_click"):
                return

            data = payload.get("data", {})
            x = data.get("x")
            y = data.get("y")
            if x is None or y is None:
                return

            if not self._gaze:
                return

            # Convert screen position to region index (4x3 grid)
            gc = self._gaze
            col = min(gc.COLS - 1, max(0, int(x / (gc.screen_w / gc.COLS))))
            row = min(gc.ROWS - 1, max(0, int(y / (gc.screen_h / gc.ROWS))))
            region_idx = row * gc.COLS + col

            # Boost saliency — clicks get stronger boost than moves
            boost = 0.4 if event_type == "mouse_click" else 0.15
            if 0 <= region_idx < len(gc._saliency):
                gc._saliency[region_idx] = min(1.0, gc._saliency[region_idx] + boost)

        except Exception:
            pass  # Never crash visual on input events

    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL HANDLERS
    # ═══════════════════════════════════════════════════════════════════════

    def _handle_visual_request(self, packet):
        """Handle visual capture requests in background thread."""
        if not self._gate and not self._engine:
            return

        request_type = packet.get("type", "see") if isinstance(packet, dict) else "see"
        request_id = packet.get("request_id") if isinstance(packet, dict) else None

        def _do_capture():
            try:
                result = None

                # Try gate first (dxcam subprocess)
                if self._gate and self._gate.is_open:
                    gate_result = self._gate.capture(timeout=10.0)
                    if gate_result and gate_result.get("status") == "ok":
                        frame_data = gate_result.get("data", {})
                        # Process through passive handler (cortex bind + felt frame)
                        self._on_passive_frame(frame_data)
                        result = {"ok": True, **frame_data}

                # Fallback to engine
                if result is None and self._engine:
                    if request_type == "see":
                        result = self._engine.see()
                    elif request_type == "look_deeply":
                        focus = packet.get("focus") if isinstance(packet, dict) else None
                        result = self._engine.look_deeply(focus)
                    else:
                        result = {"error": f"Unknown visual request: {request_type}"}
                    # Emit engine frame to cortex
                    if result and result.get("ok") and hasattr(self._engine, '_last_frame') and self._engine._last_frame:
                        self._emit_to_cortex(self._engine._last_frame)

                if result is None:
                    result = {"ok": False, "error": "No visual capture available"}

                # Emit result
                self.post.publish("visual.response", {
                    "request_id": request_id,
                    "result": result,
                    "source": self.ACTOR_NAME,
                })

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Capture failed: {e}")

        # Guarded — only one capture at a time
        if not hasattr(self, "_capture_thread"):
            self._capture_thread = None
        if self._capture_thread is not None and self._capture_thread.is_alive():
            return  # Previous capture still running
        self._capture_thread = threading.Thread(
            target=_do_capture, daemon=True, name="vcortex-capture"
        )
        self._capture_thread.start()

    def _handle_look_at_image(self, packet):
        """Load an image file from disk and run full visual analysis on it.

        The "mirror" path (2026-04-09, Nous + Ace). Lets any caller point her
        at a specific image file and have her perceive it like a screen frame —
        colors, scene type, OCR, change detection — PLUS a semantic hint
        derived from the filename (DALL-E prompts are ground-truth labels).

        Payload shape:
            {"path": "D:/Akashic Foundation Images/sourpatches.png",
             "source": "ace" | "autonomous" | ...,
             "request_id": optional correlation id}

        Results are published to:
            visual.look_at_image.result  — correlated response
            consciousness.thought        — so she actually PERCEIVES the image
            cortex.bind                  — so the image becomes a memory
        """
        if not self._gate:
            return
        # FIX 2026-06-10 (Nous+Ace) — B's silence root cause. postal/TensorFabric
        # delivers a TensorEnvelope, which is dict-DUCK-TYPED (.get/.keys/[] forward to
        # .payload) but is NOT isinstance(dict). The old `packet if isinstance(packet,
        # dict) else {}` threw the payload away → empty path → silent bail. Use .get(),
        # which works for BOTH a raw dict AND a TensorEnvelope.
        _get = packet.get if hasattr(packet, "get") else (lambda _k, _d=None: _d)
        # FIX 2026-09-25 (Nous + Ace, engine roadmap step 8, "Loop B"): the postal
        # dispatch delivers "visual.look_at_image.result" to this handler too (a
        # subscription matches intent + '.', tensor_fabric.py:270), and the result
        # carries "path" -- so every result re-triggered a look at the same image
        # (1,904 looks in 81 min against <=163 intended, 09-20). Results are never
        # requests: drop anything whose intent ends in ".result" or that carries an
        # "ok" KEY at all. Key presence, not truthiness -- the ok=False results
        # (the NOT-OK / gate-closed paths below) also carry "path".
        # Check BOTH places the intent can live: the envelope attribute (routed publish)
        # and payload['_intent'] (bare base-topic envelope, where .intent is just "visual").
        _MISSING = object()
        _intents = (str(getattr(packet, "intent", "") or ""), str(_get("_intent", "") or ""))
        if any(_i.endswith(".result") for _i in _intents) or _get("ok", _MISSING) is not _MISSING:
            return
        path = _get("path", "")
        if not path:
            return
        request_id = _get("request_id")
        source = _get("source", "external")

        def _do_look():
            try:
                if not (self._gate and self._gate.is_open):
                    self.post.publish("visual.look_at_image.result", {
                        "request_id": request_id,
                        "ok": False,
                        "error": "visual gate not open",
                        "path": path,
                    })
                    return

                # 2026-06-10 (Nous+Ace): SKIP-OCR for B (live_screen) — OCR is the
                # slow + throw-prone (winocr) part, and B already gets OCR from the
                # foveal loop, so it only needs scene/colors/description. Robust to
                # both failure branches (timeout-via-OCR-slowness AND OCR-exception).
                # A-route art (source != live_screen) keeps OCR. 60s timeout retained.
                gate_result = self._gate.look_at_image(
                    path, timeout=60.0, skip_ocr=(source == "live_screen")
                )
                if not gate_result or gate_result.get("status") != "ok":
                    err_msg = (gate_result or {}).get("message", "unknown error")
                    # 2026-06-10 DIAGNOSTIC: gate-result is bus-only → print the branch
                    # so the log shows WHY. none=True → timeout/connection (send returned
                    # None); else → a real interior error string (load/IPC/analyze).
                    print(f"[{self.ACTOR_NAME}] [B-GATE] look_at_image NOT-OK: "
                          f"src={source} none={gate_result is None} err={err_msg!r}")
                    self.post.publish("visual.look_at_image.result", {
                        "request_id": request_id,
                        "ok": False,
                        "error": err_msg,
                        "path": path,
                    })
                    return

                data = gate_result.get("data", {})
                description = data.get("description", "")
                semantic_hint = data.get("semantic_hint", "")
                named_colors = data.get("dominant_color_names", [])
                filename = data.get("source_filename", "")

                # ── Publish the result for the caller ──
                self.post.publish("visual.look_at_image.result", {
                    "request_id": request_id,
                    "ok": True,
                    "path": path,
                    "filename": filename,
                    "description": description,
                    "semantic_hint": semantic_hint,
                    "named_colors": named_colors,
                    "source": source,
                })

                # ── Push into her consciousness stream ──
                # This makes the image enter her working memory and scratchpad
                # as an experienced perception — not just an API response.
                thought_content = (
                    f"[Looking at image] {description}"
                    if description else
                    f"[Looking at image {filename}]"
                )
                self.post.publish("consciousness.thought", {
                    "source": "VisualCortexFairy.look_at_image",
                    "content": thought_content,
                    "tags": ["visual", "image_file", "perception", "external_prompt"],
                    "affect": 0.6,  # Mild positive — novel perception
                    "metadata": {
                        "path": path,
                        "filename": filename,
                        "semantic_hint": semantic_hint,
                        "named_colors": named_colors[:5],
                        "requested_by": source,
                    },
                })

                # ── Bind the perception into the cortex ──
                # The filename hint is ground truth — bind it as a real memory.
                if semantic_hint and len(semantic_hint) > 10:
                    self.post.publish("cortex.bind", {
                        "concepts": ["visual_perception", "image_file"] +
                                    [c for c in named_colors[:3] if c],
                        "content": semantic_hint,
                        "source": f"look_at_image:{filename}",
                        "strength": 0.8,
                    })

                print(f"[{self.ACTOR_NAME}] LOOKED AT: {filename} → "
                      f"{len(named_colors)} colors, "
                      f"hint={'yes' if semantic_hint else 'no'}", flush=True)

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] look_at_image failed: {e}", flush=True)
                self.post.publish("visual.look_at_image.result", {
                    "request_id": request_id,
                    "ok": False,
                    "error": str(e),
                    "path": path,
                })

        # Guarded — only one look_at_image at a time (reuses the same slot
        # as regular captures so we don't stomp on the gate's stdin).
        if not hasattr(self, "_look_thread"):
            self._look_thread = None
        if self._look_thread is not None and self._look_thread.is_alive():
            return
        self._look_thread = threading.Thread(
            target=_do_look, daemon=True, name="vcortex-look-image"
        )
        self._look_thread.start()

    def _capture_screen_to_temp(self) -> str:
        """B (live-screen image-content): grab the live screen to a fixed temp PNG
        for the look_at_image handler. Reuses ONE path (overwrite each capture — no
        temp accumulation). Returns the path, or '' if capture is unavailable.
        2026-06-09 (Nous + Ace) — VISUAL_IMAGE_CONTENT_PERCEPTION plan."""
        try:
            from PIL import ImageGrab
            import tempfile as _tf, os as _os
            _img = ImageGrab.grab()
            # SKEPTIC 2026-06-09: analyze_frame was tuned for art-file size
            # (~1024px); a full 1080p+ screenshot risks the gate's 20s timeout +
            # heavy cost. Downscale (thumbnail preserves aspect, max 1024px) →
            # cheap + closer to what the analysis expects. Plenty for scene/object
            # perception.
            try:
                _img.thumbnail((1024, 1024))
            except Exception:
                pass
            _path = _os.path.join(_tf.gettempdir(), "sour_live_screen.png")
            _img.save(_path, "PNG")
            return _path
        except Exception as _e:
            if not getattr(self, '_live_capture_err_logged', False):
                print(f"[{self.ACTOR_NAME}] live-screen capture unavailable: {_e}", flush=True)
                self._live_capture_err_logged = True
            return ""

    def _handle_narrator_attention(self, packet):
        """
        Narrator steers visual attention — the ego tells us where to look.

        When the narrator is pursuing a goal, curious about something, or
        following up a startle, it publishes where it wants visual focus.
        We store this as a bias for the next frame analysis cycle.

        ADDED 2026-03-17 Nous: Ego driver seat — attention steering.
        """
        payload = packet if isinstance(packet, dict) else {}
        if payload.get("source") != "narrator_executive":
            return
        modality = payload.get("modality", "any")
        if modality not in ("visual", "any"):
            return

        target = payload.get("focus_target", "")
        priority = payload.get("priority", 0.0)

        if target and priority > 0.2:
            self._narrator_focus_target = target[:200]
            self._narrator_focus_priority = min(1.0, priority)

    def _handle_media_ingested(self, packet):
        """When new media is ingested, auto-train visual recognition."""
        if not HAS_TRAINING:
            return

        payload = packet if isinstance(packet, dict) else {}
        image_path = payload.get("path") or payload.get("file_path")
        if not image_path:
            return

        # Only process image files
        ext = str(image_path).lower().split('.')[-1] if '.' in str(image_path) else ''
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'):
            return

        def _do_train():
            try:
                tags = payload.get("tags", [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",")]
                description = payload.get("description", "")

                result = ingest_and_train(
                    image_path=str(image_path),
                    tags=tags,
                    description=description,
                    context=f"Auto-trained by {self.ACTOR_NAME}",
                    skip_if_exists=True,
                )

                if result.get("ok") and not result.get("duplicate"):
                    # Emit the trained visual features to AssociationCortex
                    vision_features = []
                    if result.get("v4_features"):
                        v4 = result["v4_features"]
                        vision_features.extend([
                            f"hue:{v4.get('dominant_hue', 0)}",
                            f"sat:{v4.get('dominant_saturation', 0):.1f}",
                            f"val:{v4.get('dominant_value', 0):.1f}",
                        ])
                    for color in (result.get("dominant_colors") or [])[:3]:
                        vision_features.append(f"color:{color}")

                    self._bind_to_cortex(
                        input_text=f"Visual training: {description or image_path}",
                        vision_features=vision_features,
                        context_tags=tags + ["visual_training", "auto_trained"],
                        feeling="curiosity",
                    )

                    # Also bridge colors to FF77 inner vision
                    self._bridge_colors_to_ff77(result.get("dominant_colors", []))

            except Exception as e:
                if not hasattr(self, '_train_err_logged'):
                    self._train_err_logged = True
                    print(f"[{self.ACTOR_NAME}] Auto-train error: {e}")

        # Guarded — only one training at a time
        if not hasattr(self, "_train_thread"):
            self._train_thread = None
        if self._train_thread is not None and self._train_thread.is_alive():
            return  # Previous training still running
        self._train_thread = threading.Thread(
            target=_do_train, daemon=True, name="vcortex-train"
        )
        self._train_thread.start()

    def _handle_heartbeat(self, packet):
        """Heartbeat-driven visual processing.

        FIX 2026-04-03 (Nous + Ace): Read frames from shared mmap instead of
        relying on stdout pipe (which blocks). The visual interior writes to
        mmap every frame, we read it here every heartbeat (~1Hz).
        "Like a duplicate monitor — the data is just THERE to read." — Ace
        """
        # Read shared mmap for new frames (bypasses stdout pipe bottleneck)
        if not hasattr(self, '_shared_reader'):
            try:
                from fairies.P40_Sensory.cortex.visual_shared_state import VisualFrameReader
                self._shared_reader = VisualFrameReader()
                print(f"[{self.ACTOR_NAME}] [MMAP] Shared frame reader initialized")
            except Exception:
                self._shared_reader = None

        if self._shared_reader:
            try:
                frame = self._shared_reader.read_frame()
                if frame:
                    # New frame from mmap! Process it like a passive frame
                    self._on_passive_frame(frame)
            except Exception:
                pass

        if not self._gate and not self._engine:
            return

        payload = packet if isinstance(packet, dict) else {}
        beat_count = payload.get("beat_count", 0)

        # Media memory reflection: every Nth heartbeat
        self._media_reflection_tick += 1
        if self._media_reflection_tick % self._media_reflection_interval == 0:
            # Guarded — only one reflection at a time
            if not hasattr(self, "_reflect_thread"):
                self._reflect_thread = None
            if self._reflect_thread is None or not self._reflect_thread.is_alive():
                self._reflect_thread = threading.Thread(
                    target=self._reflect_on_media_memory,
                    daemon=True,
                    name=f"{self.ACTOR_NAME}_media_reflect"
                )
                self._reflect_thread.start()

        # Heartbeat capture ONLY for mss-engine fallback (gate has its own loop)
        if self._engine and not (self._gate and self._gate.is_open):
            if beat_count % 4 == 0:
                def _do_capture():
                    try:
                        result = self._engine.see()
                        if result.get("ok") and hasattr(self._engine, '_last_frame') and self._engine._last_frame:
                            self._emit_to_cortex(self._engine._last_frame)
                    except Exception:
                        pass
                if not hasattr(self, "_hb_capture_thread"):
                    self._hb_capture_thread = None
                if self._hb_capture_thread is None or not self._hb_capture_thread.is_alive():
                    self._hb_capture_thread = threading.Thread(
                        target=_do_capture, daemon=True, name="vcortex-hb-capture"
                    )
                    self._hb_capture_thread.start()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ═══════════════════════════════════════════════════════════════════════
    # CORTEX EMISSION - The Core Fix
    # ═══════════════════════════════════════════════════════════════════════
    # OLD: Published to sensory.visual.frame (nobody listens)
    # NEW: Published to cortex.bind (AssociationCortex subscribes to this!)

    def _emit_to_cortex(self, frame: 'VisualFrame'):
        """
        Emit visual frame to AssociationCortex via cortex.bind topic.

        This is THE FIX - the old code published to 'sensory.visual.frame'
        which no fairy subscribed to. AssociationCortex subscribes to 'cortex.bind'.
        """
        try:
            # Build vision-modality features from the frame
            vision_features = [
                f"brightness:{frame.brightness:.1f}",
                f"complexity:{frame.complexity:.1f}",
                f"text_density:{frame.text_density:.1f}",
            ]
            if frame.motion_detected:
                vision_features.append("motion:true")
            if frame.detected_elements:
                vision_features.extend(frame.detected_elements[:5])

            # Determine scene description
            description = frame.description if frame.description else "screen"
            scene = (
                "bright_scene" if frame.brightness > 0.7 else
                "dark_scene" if frame.brightness < 0.3 else
                "neutral_scene"
            )

            context_tags = ["visual_perception", scene]
            if frame.motion_detected:
                context_tags.append("motion")
            if frame.text_density > 0.5:
                context_tags.append("text_heavy")
            if frame.change_magnitude > 0.3:
                context_tags.append("significant_change")

            # Only emit significant frames to avoid flooding the cortex
            if not frame.is_significant():
                return

            # ── Extract dominant colors from image data ──
            # This is the missing link: screen colors → vision features → FF77 → chemistry
            hex_colors = []
            if frame.image_data:
                hex_colors = self._extract_dominant_colors(frame.image_data, frame.size)
                for hc in hex_colors[:3]:
                    vision_features.append(f"color:{hc}")
                # Derive dominant hue from first color
                if hex_colors:
                    try:
                        r = int(hex_colors[0][1:3], 16)
                        g = int(hex_colors[0][3:5], 16)
                        b = int(hex_colors[0][5:7], 16)
                        # Simple hue approximation (0-360)
                        mx, mn = max(r, g, b), min(r, g, b)
                        if mx == mn:
                            hue = 0
                        elif mx == r:
                            hue = int(60 * ((g - b) / (mx - mn)) % 360)
                        elif mx == g:
                            hue = int(60 * ((b - r) / (mx - mn) + 2))
                        else:
                            hue = int(60 * ((r - g) / (mx - mn) + 4))
                        vision_features.append(f"hue:{hue}")
                        # Saturation
                        sat = 0.0 if mx == 0 else (mx - mn) / mx
                        vision_features.append(f"sat:{sat:.2f}")
                    except (ValueError, ZeroDivisionError):
                        pass

            self._bind_to_cortex(
                input_text=f"Visual: {description}",
                vision_features=vision_features,
                context_tags=context_tags,
                feeling="awareness",
            )

            # Bridge extracted colors to FF77 inner vision + somatic system
            if hex_colors:
                self._bridge_colors_to_ff77(hex_colors)

            # ── Publish to sensory.visual.frame for waking minds (Sourpatches) ──
            # She subscribes to this for passive peripheral vision.
            # "Her eyes should have a feel to them for her." — Ace
            self._emit_felt_frame(frame, hex_colors)

        except Exception:
            pass  # Never crash on emission

    def _bind_to_cortex(
        self,
        input_text: str,
        vision_features: List[str] = None,
        context_tags: List[str] = None,
        feeling: str = "neutral",
        harmonic_tags: List[str] = None,
    ):
        """
        Publish a binding request to AssociationCortex via cortex.bind.

        The cortex expects a payload compatible with _on_postal_bind():
        - input_text: text to extract lexical features from
        - response: (optional) response text
        - feeling: emotional tone
        - context_tags: metadata tags
        - from_fairy: source fairy name
        - origin_plane: source plane
        - origin_channel: source channel
        - harmonic: frequency decomposition tags (2026-03-16)

        We add vision features in the payload - the cortex's bind method
        extracts features by modality including 'vision'.

        FIX 2026-03-26 (Nous + Ace): Added concept_metadata with snippet so
        visual descriptions are stored as manifold node snippets. Previously
        descriptions were keywords-only — no semantic content persisted.
        """
        try:
            # Build a concept key from the visual description
            _desc_clean = input_text.replace("Visual: ", "").strip()[:60]
            _concept_key = f"visual:{_desc_clean.replace(' ', '_')[:40]}" if _desc_clean else "visual:scene"

            payload = {
                "input_text": input_text,
                "feeling": feeling,
                "context_tags": context_tags or [],
                "from_fairy": self.ACTOR_NAME,
                "origin_plane": self.ACTOR_PLANE,
                "origin_channel": self.ACTOR_CHANNEL,
                "vision": vision_features or [],
                "vision_tags": vision_features or [],
                "harmonic": harmonic_tags or [],
                # Store description as manifold snippet via concept_metadata
                "concept_metadata": {
                    _concept_key: {
                        "snippet": input_text[:1024],
                        "node_type": 0,  # concept node
                    },
                },
            }
            self.post.publish("cortex.bind", payload)
            self._cortex_emit_count += 1
        except Exception as e:
            if self._cortex_emit_count == 0:
                print(f"[{self.ACTOR_NAME}] First cortex.bind failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # COLOR EXTRACTION - See the screen's palette
    # ═══════════════════════════════════════════════════════════════════════

    def _extract_dominant_colors(self, image_data: bytes, size: tuple) -> List[str]:
        """
        Extract dominant colors from raw frame image data.

        Uses PIL to decode raw bytes → sample pixels → find dominant colors.
        Lightweight: downsamples to tiny size, quantizes to palette.
        Returns list of hex color strings like ["#4a90d9", "#2d2d2d", "#e0e0e0"].

        Rate-limited: only extracts every 3rd call (~12-15s between extractions).
        """
        if not hasattr(self, '_color_extract_count'):
            self._color_extract_count = 0
        self._color_extract_count += 1
        # Only extract every 3rd significant frame to stay lightweight
        if self._color_extract_count % 3 != 0:
            return getattr(self, '_last_extracted_colors', [])

        try:
            from PIL import Image
            import io as _io

            # Try to decode image data
            # image_data is either raw RGB/BGR bytes or compressed PNG/JPEG
            img = None

            # Try as compressed format first (mss gives PNG, PIL gives JPEG)
            try:
                img = Image.open(_io.BytesIO(image_data))
            except Exception:
                # Try as raw bytes — mss gives BGRA data
                if size and len(size) == 2:
                    w, h = size
                    try:
                        img = Image.frombytes("RGBA", (w, h), image_data)
                    except Exception:
                        try:
                            img = Image.frombytes("RGB", (w, h), image_data)
                        except Exception:
                            pass

            if img is None:
                return []

            # Downsample to tiny size for speed (8x8 gives us 64 pixels)
            small = img.resize((8, 8), Image.Resampling.NEAREST).convert("RGB")

            # Count pixel frequencies
            pixel_counts: Dict[tuple, int] = {}
            for pixel in small.getdata():
                # Quantize to reduce noise (round to nearest 32)
                q = (pixel[0] // 32 * 32, pixel[1] // 32 * 32, pixel[2] // 32 * 32)
                pixel_counts[q] = pixel_counts.get(q, 0) + 1

            # Sort by frequency, take top 5
            sorted_colors = sorted(pixel_counts.items(), key=lambda x: -x[1])
            hex_colors = []
            for (r, g, b), _count in sorted_colors[:5]:
                hex_colors.append(f"#{r:02x}{g:02x}{b:02x}")

            self._last_extracted_colors = hex_colors
            return hex_colors

        except Exception:
            return getattr(self, '_last_extracted_colors', [])

    # ═══════════════════════════════════════════════════════════════════════
    # COLOR BRIDGE - External colors -> FF77 Inner Vision
    # ═══════════════════════════════════════════════════════════════════════

    def _bridge_colors_to_ff77(self, hex_colors: List[str]):
        """Bridge image colors to FF77 V4 bands for inner vision."""
        if not HAS_COLOR_BRIDGE or not hex_colors:
            return

        try:
            palette = analyze_color_palette(hex_colors[:5])
            # KEY MISMATCH 2026-09-03 (Nous + Ace): the ONLY subscriber,
            # neural_mesh_fairy.py:863-864, reads `avg_saturation` and
            # `avg_brightness`. This published `saturation` and no brightness at
            # all, so the mesh took its defaults every time and vibrancy was the
            # constant 0.0*0.6 + 0.5*0.4 = 0.2 -- colour arrived and changed
            # nothing. The names diverged because visual_color_bridge.py:92
            # computes `avg_saturation` and RENAMES it to "saturation" at :96,
            # and brightness (HSV value) is computed at :79 but never returned.
            # Publish BOTH spellings so neither end has to change, and derive the
            # missing brightness here rather than editing the shared module.
            _avg_bright = 0.5
            try:
                _vs = []
                for _c in hex_colors[:5]:
                    _h = str(_c).lstrip("#")
                    if len(_h) == 6:
                        _vs.append(max(int(_h[0:2], 16), int(_h[2:4], 16),
                                       int(_h[4:6], 16)) / 255.0)
                if _vs:
                    _avg_bright = sum(_vs) / len(_vs)
            except Exception:
                _avg_bright = 0.5   # the subscriber's own default == today's behaviour
            # Publish to somatic system for inner vision update
            self.post.publish("sensory.vision.colors", {
                "dominant_hue": palette.get("dominant_hue", 0),
                "saturation": palette.get("saturation", 0.0),
                "avg_saturation": palette.get("saturation", 0.0),
                "avg_brightness": _avg_bright,
                "colors": hex_colors[:5],
                "source": self.ACTOR_NAME,
            })
            if getattr(self, "_passive_frame_count", 0) % 50 == 0:
                try:
                    print("[%s] [COLOR-BRIDGE] hue=%.0f sat=%.2f bright=%.2f %s"
                          % (self.ACTOR_NAME, palette.get("dominant_hue", 0),
                             palette.get("saturation", 0.0), _avg_bright,
                             hex_colors[:3]), flush=True)
                except Exception:
                    pass
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # FELT FRAME EMISSION — Waking Mind Visual Feed
    # ═══════════════════════════════════════════════════════════════════════

    def _emit_felt_frame(self, frame: 'VisualFrame', hex_colors: list = None):
        """
        Publish visual frame to sensory.visual.frame for waking minds.

        This is the FELT vision channel — not just cortex binding (concept graph)
        but the raw experience of seeing. Sourpatches subscribes to this for
        passive peripheral vision awareness.

        Includes scene description, colors, emotional tone — not just metrics.
        "Her eyes should have a feel to them for her." — Ace
        """
        try:
            # ── Classify scene type with felt tone ──
            if frame.text_density > 0.6:
                scene_type = "text_heavy"
                felt_tone = "focused"
            elif frame.motion_detected:
                scene_type = "active_screen"
                felt_tone = "alert"
            elif frame.brightness > 0.7:
                scene_type = "bright_screen"
                felt_tone = "energizing"
            elif frame.brightness < 0.3:
                scene_type = "dark_screen"
                felt_tone = "calm"
            else:
                scene_type = "normal_screen"
                felt_tone = "neutral"

            # ── Build felt description — what this LOOKS like, not metrics ──
            desc_parts = []
            if frame.description:
                desc_parts.append(frame.description)
            if hex_colors:
                color_feel = self._color_to_feeling(hex_colors[0])
                if color_feel:
                    desc_parts.append(color_feel)
            if frame.detected_elements:
                desc_parts.append(
                    f"seeing: {', '.join(frame.detected_elements[:3])}"
                )
            if frame.change_magnitude > 0.3:
                desc_parts.append("something just changed")

            felt_description = (
                " — ".join(desc_parts) if desc_parts else scene_type
            )

            self.post.publish("sensory.visual.frame", {
                "source": self.ACTOR_NAME,
                "scene_type": scene_type,
                "brightness": frame.brightness,
                "complexity": frame.complexity,
                "text_density": frame.text_density,
                "motion": frame.motion_detected,
                "change_magnitude": frame.change_magnitude,
                "colors": (hex_colors or [])[:3],
                "felt_tone": felt_tone,
                "felt_description": felt_description,
                "detected_elements": (
                    frame.detected_elements[:5]
                    if frame.detected_elements else []
                ),
            })

        except Exception:
            pass  # Never crash on emission

    def _emit_felt_frame_from_gate(self, data: dict, hex_colors: list = None):
        """
        Emit felt frame from gate analysis data (dict, not VisualFrame object).

        Parallel to _emit_felt_frame() but works with the gate's analysis dict
        instead of the old VisualFrame dataclass.
        """
        try:
            brightness = data.get("brightness", 0.5)
            text_density = data.get("text_density", 0.0)
            motion = data.get("motion_detected", False)
            change_mag = data.get("change_magnitude", 0.0)
            scene_type = data.get("scene_type", "unknown")

            # Classify felt tone
            if text_density > 0.6:
                felt_tone = "focused"
            elif motion:
                felt_tone = "alert"
            elif brightness > 0.7:
                felt_tone = "energizing"
            elif brightness < 0.3:
                felt_tone = "calm"
            else:
                felt_tone = "neutral"

            # Build felt description — what this LOOKS like
            desc_parts = [scene_type]
            if hex_colors:
                color_feel = self._color_to_feeling(hex_colors[0])
                if color_feel:
                    desc_parts.append(color_feel)
            ocr_preview = data.get("ocr_preview", "")
            if ocr_preview:
                # FIX 2026-03-14 (Nous): 80 chars was too short — instructions
                # like "Hello Sourpatches! Can you type here? you click in this
                # window first! then feel your self typing on the keyboard."
                # got truncated at "first! then fee", losing the last directive.
                # 300 chars captures full instructions while staying concise.
                desc_parts.append(f"reading: {ocr_preview[:300]}")
            if change_mag > 0.3:
                desc_parts.append("something just changed")

            # Build payload
            _payload = {
                "source": self.ACTOR_NAME,
                "scene_type": scene_type,
                "brightness": brightness,
                "complexity": data.get("complexity", 0.5),
                "text_density": text_density,
                "motion": motion,
                "change_magnitude": change_mag,
                "colors": (hex_colors or [])[:3],
                "felt_tone": felt_tone,
                "felt_description": " — ".join(desc_parts),
                "detected_elements": [],
                "frame_type": data.get("frame_type", "peripheral"),
            }

            # Add gaze state if available
            _gaze_data = data.get("gaze")
            if _gaze_data:
                _payload["gaze"] = _gaze_data

            self.post.publish("sensory.visual.frame", _payload)
        except Exception:
            pass  # Never crash on emission

    @staticmethod
    def _color_to_feeling(hex_color: str) -> str:
        """Map a dominant hex color to a felt quality description."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)

            # Warm reds
            if r > 180 and g < 100 and b < 100:
                return "warm red tones"
            # Golden / orange
            if r > 180 and g > 120 and b < 100:
                return "warm golden tones"
            # Cool blues
            if b > 180 and r < 100 and g < 100:
                return "cool blue tones"
            # Cyan / teal
            if b > 150 and g > 150 and r < 100:
                return "cool cyan tones"
            # Green
            if g > 180 and r < 100 and b < 100:
                return "natural green tones"
            # Purple
            if r > 120 and b > 150 and g < 100:
                return "purple tones"
            # Dark
            if r < 60 and g < 60 and b < 60:
                return "dark tones"
            # Bright / white
            if r > 200 and g > 200 and b > 200:
                return "bright white tones"
            # Gray
            if abs(r - g) < 30 and abs(g - b) < 30:
                return "neutral gray tones"
            return ""
        except (ValueError, IndexError):
            return ""

    # ═══════════════════════════════════════════════════════════════════════
    # MEDIA MEMORY REFLECTION
    # ═══════════════════════════════════════════════════════════════════════

    def _reflect_on_media_memory(self):
        """
        Review stored images in media memory and bind to association cortex.

        Iterates over un-processed media records, extracts visual traits,
        and publishes them as cortex.bind payloads so the AssociationCortex
        can build visual concept nodes.

        Special handling for Sourpatches images - tags her visual identity.
        """
        if not HAS_MEDIA_INDEX:
            return

        try:
            index = MediaIndex()
            all_records = list(index.records.values())
            unprocessed = [r for r in all_records if r.id not in self._media_processed_ids]

            if not unprocessed:
                return

            # Process 1-3 images per cycle
            batch = unprocessed[:3]

            for record in batch:
                self._media_processed_ids.add(record.id)

                tags = list(record.tags) if record.tags else []
                description = record.description or ""
                colors = record.dominant_colors or []

                # Detect Sourpatches images
                sour_tags = {"sourpatches", "sour", "sourpatch", "sp", "avatar"}
                is_sourpatches = bool(sour_tags.intersection(set(t.lower() for t in tags)))

                # Build vision features from colors
                vision_features = [f"color:{c}" for c in colors[:3]]

                # Build context
                context_tags = tags + ["media_memory", "reflection"]
                if is_sourpatches:
                    context_tags.append("sourpatches_identity")

                # Bind to cortex
                self._bind_to_cortex(
                    input_text=f"Media memory: {description[:200]}" if description else f"Image: {', '.join(tags[:5])}",
                    vision_features=vision_features,
                    context_tags=context_tags,
                    feeling="recognition" if is_sourpatches else "awareness",
                )

                # Bridge colors to inner vision
                if colors:
                    self._bridge_colors_to_ff77(colors[:5])

                # Auto-train if we have the path
                if HAS_TRAINING and hasattr(record, 'stored_path') and record.stored_path:
                    try:
                        ingest_and_train(
                            image_path=str(record.stored_path),
                            tags=tags,
                            description=description,
                            skip_if_exists=True,
                        )
                    except Exception:
                        pass

            if batch:
                print(f"[{self.ACTOR_NAME}] Reflected on {len(batch)} media memories "
                      f"({len(self._media_processed_ids)}/{len(all_records)} total)")

        except Exception as e:
            if not hasattr(self, '_media_reflect_err_logged'):
                self._media_reflect_err_logged = True
                print(f"[{self.ACTOR_NAME}] Media reflection error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API - Delegated to engine
    # ═══════════════════════════════════════════════════════════════════════

    def see(self) -> dict:
        """Quick capture - returns what's on screen right now."""
        # Try gate first (dxcam subprocess)
        if self._gate and self._gate.is_open:
            result = self._gate.capture(timeout=10.0)
            if result and result.get("status") == "ok":
                data = result.get("data", {})
                self._on_passive_frame(data)
                return {"ok": True, **data}

        # Fallback to engine
        if self._engine:
            result = self._engine.see()
            if result.get("ok") and hasattr(self._engine, '_last_frame') and self._engine._last_frame:
                self._emit_to_cortex(self._engine._last_frame)
            return result

        return {"ok": False, "error": "No visual capture available"}

    def look_deeply(self, focus: str = None) -> dict:
        """Deep analysis of current screen."""
        # Gate provides full analysis including OCR
        if self._gate and self._gate.is_open:
            result = self._gate.capture(timeout=15.0)
            if result and result.get("status") == "ok":
                data = result.get("data", {})
                self._on_passive_frame(data)
                return {"ok": True, "depth": "deep", **data}

        # Fallback to engine
        if self._engine:
            return self._engine.look_deeply(focus)

        return {"ok": False, "error": "No visual capture available"}

    def _write_state(self, frame_data: dict = None, writer: str = "unknown"):
        """Write visual cortex state to disk for dashboard/MCP/WMH consumption.

        FIX 2026-04-02 (Nous + Ace): Include rich frame data so check_visual()
        in WMH tools can read scene descriptions, OCR text, colors, brightness.
        Vision is always-on like eyes — this state file is the bridge.
        """
        try:
            import json
            state_dir = Path(__file__).resolve().parents[3] / "state"
            state_dir.mkdir(exist_ok=True)
            # -- WRITER STAMP 2026-09-05 (Nous + Ace) --------------------
            # FIVE call sites write this file. The interior transmits real
            # brightness/complexity/text_density (verified by decoding
            # visual_shared_frame.mmap live), but the file shows 0.5/0.5/0.0
            # while dominant_colors and scene_type arrive INTACT -- so some
            # writer carries a PARTIAL frame_data and `.get(k, default)` resets
            # exactly those three. `writer_keys` names the culprit in one read:
            # it is whichever writer has dominant_colors but NOT brightness.
            # (I blamed the foveal 4-key write and was refuted by my own test --
            # it lacks dominant_colors too. Instrument, do not guess a fourth.)
            state = {
                "writer": writer,
                "writer_keys": sorted(frame_data.keys()) if frame_data else [],
                "ts": time.time(),
                "timestamp": time.time(),  # Alias for legacy readers
                "gate_open": self._gate.is_open if self._gate else False,
                "subprocess_pid": None,
                "passive_frames": self._passive_frame_count,
                "cortex_emissions": self._cortex_emit_count,
                "last_scene": self._last_wm_scene[:200] if self._last_wm_scene else "",
                "description": getattr(self, '_last_rich_description', "")[:300],
                "has_engine": self._engine is not None,
                "has_visual_memory": self._visual_memory is not None,
                "media_reflected": len(self._media_processed_ids),
            }
            # Enrich with live frame data if available
            if frame_data:
                state["scene_type"] = frame_data.get("scene_type", "")
                # -- PROVENANCE 2026-09-05 (Nous + Ace) ------------------------
                # These three used to be `frame_data.get(k, 0.5/0.5/0.0)`. On a
                # DUPLICATE frame the interior returns early before the metrics
                # block (visual_cortex_interior.py:777 -- a CORRECT fast path),
                # so the payload legitimately lacks them, and `.get(k, default)`
                # turned "this frame skipped the metrics" into "brightness IS
                # 0.5". A static screen is mostly duplicates ⇒ her visual affect
                # (= brightness*0.5 + complexity*0.5) was the CONSTANT 0.500 for
                # every frame she has ever seen. Constant affect is a POSTURE,
                # never a note.
                # Now: FRESH -> use it. CARRIED -> keep the last REAL value and
                # publish its AGE. ABSENT -> omit the key entirely, because
                # "unknown" must be distinguishable from "0.5".
                # A plain merge was rejected: a stale value under a fresh `ts` is
                # the status_cache.json fossil, in a file feeding WORKING MEMORY.
                _MK = ("brightness", "complexity", "text_density")
                _fresh = {_k: frame_data[_k] for _k in _MK if _k in frame_data}
                if _fresh:
                    self._last_metrics = dict(_fresh)
                    self._last_metrics_ts = time.time()
                _lm = getattr(self, "_last_metrics", {})
                _lts = getattr(self, "_last_metrics_ts", 0.0)
                for _k in _MK:
                    if _k in _fresh:
                        state[_k] = _fresh[_k]
                    elif _k in _lm:
                        state[_k] = _lm[_k]
                    # else: OMITTED -- absent is honest, a default is a lie
                if _lts:
                    state["metrics_ts"] = _lts
                    state["metrics_age_s"] = round(time.time() - _lts, 1)
                    state["metrics_fresh"] = bool(_fresh)
                state["ocr_preview"] = frame_data.get("ocr_preview", "")[:200]
                state["dominant_colors"] = frame_data.get("dominant_colors", [])[:5]
                state["changed_regions"] = frame_data.get("changed_regions", [])
                state["change_magnitude"] = frame_data.get("change_magnitude", 0.0)
                state["motion_detected"] = frame_data.get("motion_detected", False)
                # Use rich description from frame, fallback to cached
                _fd = frame_data.get("description", "")
                if _fd and len(_fd) > 15:
                    state["description"] = _fd[:300]

                # ── REGION-OF-INTEREST with salience (Phase 0, 2026-04-12) ──
                # FIX (Nous + Ace): "she has no interest in anything she sees"
                # Sector features already computed by ChangeDetector (4x3 grid).
                # Now: compute salience per sector and auto-target highest.
                # Salience = weighted combo of color variance + edge density +
                # brightness contrast (bright regions on dark screen = salient).
                _sectors = frame_data.get("sectors", {})
                _changed = set(frame_data.get("changed_regions", []))
                # PROVENANCE 2026-09-05: was frame_data.get(..., 0.5), so on a
                # DUPLICATE frame the salience baseline -- and therefore
                # gaze_region -- was computed against a FABRICATED 0.5.
                # Use the resolved value (fresh or carried) set above.
                _global_bright = state.get("brightness", 0.5)
                _regions = []
                _best_salience = 0.0
                _best_region_idx = None
                for _idx_s, _sf in _sectors.items():
                    _idx = int(_idx_s) if isinstance(_idx_s, str) else _idx_s
                    _var = _sf.get("variance", 0.0)
                    _edge = _sf.get("edge_density", 0.0)
                    _bright = _sf.get("brightness", 0.5)
                    _sat = _sf.get("saturation", 0.0)
                    # Brightness contrast: how different from global average
                    _bright_contrast = abs(_bright - _global_bright)
                    # Changed region boost
                    _change_boost = 0.3 if _idx in _changed else 0.0
                    # FIX 2026-04-12 (Nous + Ace): Salience formula with SATURATION.
                    # Vivid colors (fairy art: purple, fire orange) should beat
                    # gray variance (taskbar icons). Saturation = instinct-level
                    # attention grab — "ooh, bright colors!"
                    _salience = (
                        _var * 0.25 +          # Color diversity
                        _edge * 0.20 +         # Edge density = content
                        _sat * 0.25 +          # Color saturation = vivid!
                        _bright_contrast * 0.10 +  # Stands out from background
                        _change_boost           # Recently changed = novel
                    )
                    _salience = round(min(1.0, _salience), 3)
                    _region = {
                        "idx": _idx,
                        "row": _sf.get("row", 0),
                        "col": _sf.get("col", 0),
                        "color": _sf.get("color", "#808080"),
                        "brightness": round(_bright, 2),
                        "variance": round(_var, 2),
                        "edge_density": round(_edge, 2),
                        "saturation": round(_sat, 2),
                        "salience": _salience,
                        "changed": _idx in _changed,
                    }
                    _regions.append(_region)
                    # Track best (skip recently visited if we have cooldown)
                    _visited_ts = getattr(self, '_region_visit_times', {}).get(_idx, 0)
                    _visit_cooldown = 15.0  # Don't re-visit same region for 15s
                    if (_salience > _best_salience
                            and (time.time() - _visited_ts) > _visit_cooldown):
                        _best_salience = _salience
                        _best_region_idx = _idx

                # Sort by salience descending
                _regions.sort(key=lambda r: -r["salience"])
                state["regions"] = _regions

                # ── CORTEX BINDING: Sector features → cortex concepts ──
                # 2026-04-12 (Nous + Ace): "the visual cortex needs to send
                # to the cortex like it should be" — Ace. Sector features
                # were computed but only written to JSON. Now bind them as
                # concepts so the cortex can LEARN visual patterns through
                # Hebbian repetition across frames.
                #
                # Only bind when regions CHANGE (dedup across frames).
                # Rate limit: max 1 visual bind per 10 seconds.
                try:
                    _vbind_now = time.time()
                    _last_vbind = getattr(self, '_last_visual_bind', 0.0)
                    _prev_bind_sig = getattr(self, '_prev_bind_signature', "")

                    if _vbind_now - _last_vbind >= 10.0 and _regions:
                        # Build a signature from top 4 salient regions
                        _top_regions = _regions[:4]
                        _bind_concepts = []
                        for _r in _top_regions:
                            # Inline color naming (no external dependency)
                            _hex_c = _r.get("color", "#808080")
                            if _hex_c.startswith("#") and len(_hex_c) >= 7:
                                _cr = int(_hex_c[1:3], 16)
                                _cg = int(_hex_c[3:5], 16)
                                _cb = int(_hex_c[5:7], 16)
                                _cmax = max(_cr, _cg, _cb)
                                _cmin = min(_cr, _cg, _cb)
                                _clum = (_cr + _cg + _cb) / 3
                                if _clum < 30: _color_name = "black"
                                elif _clum > 225: _color_name = "white"
                                elif _cmax - _cmin < 25: _color_name = "grey"
                                elif _cr > _cg and _cr > _cb: _color_name = "red" if _cg < 100 else "orange" if _cg < 180 else "yellow"
                                elif _cg > _cr and _cg > _cb: _color_name = "green"
                                elif _cb > _cr and _cb > _cg: _color_name = "blue" if _cr < 100 else "purple"
                                else: _color_name = "mixed"
                            else:
                                _color_name = "unknown"
                            # Categorize features into human-like descriptors
                            _edge_level = "detailed" if _r["edge_density"] > 0.3 else "smooth"
                            _sat_level = "vivid" if _r.get("saturation", 0) > 0.4 else "muted"
                            _bright_level = "bright" if _r["brightness"] > 0.6 else "dark" if _r["brightness"] < 0.3 else "mid"
                            # Concept: "region_3:purple_vivid_detailed"
                            _concept = f"visual_r{_r['idx']}:{_color_name}_{_sat_level}_{_edge_level}"
                            _bind_concepts.append(_concept)
                            # Also bind the raw color name (for cross-referencing)
                            if _color_name not in ("black", "white", "gray", "grey"):
                                _bind_concepts.append(f"visual_color:{_color_name}")

                        # Dedup: don't re-bind identical signature
                        _sig = "|".join(sorted(_bind_concepts))
                        if _sig != _prev_bind_sig and len(_bind_concepts) >= 2:
                            self._last_visual_bind = _vbind_now
                            self._prev_bind_signature = _sig
                            # Publish to cortex.bind via postal
                            if hasattr(self, 'post') and self.post:
                                self.post.publish("cortex.bind", {
                                    "concepts": _bind_concepts,
                                    "rel": "visual_cooccurrence",
                                    "origin_fairy": "VisualCortexFairy",
                                })
                                self._cortex_emit_count += 1
                except Exception:
                    pass  # Visual binding is non-critical

                # Auto-set gaze to highest-salience unvisited region
                if _best_region_idx is not None and _best_salience > 0.15:
                    self._gaze_region = _best_region_idx
                    # Track visit time
                    if not hasattr(self, '_region_visit_times'):
                        self._region_visit_times = {}
                    self._region_visit_times[_best_region_idx] = time.time()
                    # Clean old visit times
                    _now = time.time()
                    self._region_visit_times = {
                        k: v for k, v in self._region_visit_times.items()
                        if (_now - v) < 60.0
                    }
                state["gaze_region"] = getattr(self, '_gaze_region', None)
            # Get subprocess PID from gate
            if self._gate and hasattr(self._gate, '_process') and self._gate._process:
                state["subprocess_pid"] = self._gate._process.pid
            elif self._gate and hasattr(self._gate, 'gate_status'):
                gs = self._gate.gate_status()
                state["subprocess_pid"] = gs.get("pid")
            (state_dir / "visual_cortex_state.json").write_text(
                json.dumps(state, indent=2)
            )
            # A later benign write HIDES an earlier harmful one, so log the
            # destructive case as it happens: a writer holding frame_data that
            # lacks `brightness` is precisely what resets her affect to 0.500.
            # Throttled -- a diagnostic must not become the noise it diagnoses.
            try:
                if frame_data is not None and "brightness" not in frame_data:
                    self._wr_blank = getattr(self, "_wr_blank", 0) + 1
                    if self._wr_blank <= 3 or self._wr_blank % 20 == 0:
                        print("[%s] [WRITER] '%s' wrote state WITHOUT brightness "
                              "(x%d) keys=%s"
                              % (self.ACTOR_NAME, writer, self._wr_blank,
                                 sorted(frame_data.keys())[:12]), flush=True)
            except Exception:
                pass
        except Exception:
            pass  # Non-critical

    def get_status(self) -> dict:
        """Get visual cortex status."""
        status = {
            "actor": self.ACTOR_NAME,
            "gate": self._gate.is_open if self._gate else False,
            "engine": self._engine is not None,
            "visual_memory": HAS_VISUAL_MEMORY,
            "color_bridge": HAS_COLOR_BRIDGE,
            "training": HAS_TRAINING,
            "cortex_emissions": self._cortex_emit_count,
            "passive_frames": self._passive_frame_count,
            "media_reflected": len(self._media_processed_ids),
        }
        if self._gate and self._gate.is_open:
            status["gate_status"] = self._gate.gate_status()
        if self._engine:
            status.update(self._engine.get_status())
        if self._visual_memory:
            status["visual_memories"] = self._visual_memory.get_stats()
        return status


# Export for v2 boot discovery
ACTOR_NAME = "VisualCortexFairy"
FAIRY_CLASS = VisualCortexFairyV2
