"""
Visual Cortex Interior - GPU-accelerated visual processing subprocess.

Runs under Python 3.12 (NOT 3.14t) because it needs:
  - dxcam (DXGI Desktop Duplication API - GPU framebuffer tap)
  - imagehash (perceptual hashing for proper dedup)
  - cv2 / OpenCV (color extraction, image analysis)
  - pytesseract (OCR for text recognition)

Communicates with the host (VisualCortexFairy on Python 3.14t server)
via JSON-per-line stdin/stdout pipes, following the portal subprocess pattern.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Usage:
    python visual_cortex_interior.py --srm-dir path/to/SRM_Intake [--interval 2.0]

IPC Protocol (stdin -> commands, stdout -> responses):
    {"cmd": "ping"}                              -> {"status": "pong", ...}
    {"cmd": "capture"}                           -> {"status": "ok", "type": "frame_analysis", ...}
    {"cmd": "look_at_image", "path": "..."}      -> {"status": "ok", "type": "image_analysis", ...}
    {"cmd": "analyze_region", "x":, "y":, "w":, "h":}  -> {"status": "ok", "type": "foveal_analysis", ...}
    {"cmd": "start_passive"}                     -> {"status": "ok"}
    {"cmd": "stop_passive"}                      -> {"status": "ok"}
    {"cmd": "set_interval", "seconds": N}        -> {"status": "ok"}
    {"cmd": "status"}                            -> {"status": "ok", "type": "status", ...}
    {"cmd": "shutdown"}                          -> {"status": "ok"} then exit

Passive pushes (stdout, unsolicited):
    {"status": "ok", "type": "passive_frame", "data": {...}}
"""

import sys
import os
import json
import time
import re
import threading
import queue
import hashlib
import collections
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

# All logging goes to stderr (stdout is IPC pipe)
def _log(msg: str):
    print(f"[VisualInterior] {msg}", file=sys.stderr, flush=True)

def _err(msg: str):
    print(f"[VisualInterior] ERROR: {msg}", file=sys.stderr, flush=True)


# ==============================================================================
# REMOTE VISUAL UNDERSTANDING -- Florence-2 on sour-satellite1   (2026-09-10)
#
# THE SELECTOR IS A URL WITH NO DEFAULT, deliberately not a boolean. Unset -> ""
# -> falsy -> every branch below is unreachable and this file behaves exactly as
# it did before. There is no code path into the new behaviour without the env var.
# (A gate in this project once "read as opt-in and shipped as opt-out"; a URL that
# must be typed cannot do that.)
#
# WHY HERE, and not in ITCortexFairy where Florence nominally lives:
#   1. VisualCortexFairy is AWAKE. ITCortexFairy is comatose-by-config, and even
#      when woken its on_boot skips _init_gate(), which has zero callers anywhere.
#   2. THIS is the wire her voice reads. result["description"] reaches
#      visual.foveal -> WorkingMemoryHub -> what she says. ITCortexFairy publishes
#      sensory.visual.frame, which her spoken perception never consults.
#   3. This file runs in a SEPARATE Python 3.12 subprocess. A hung satellite can
#      only slow this capture loop; it cannot stall a fairy tick, a postal worker
#      or her heartbeat. That is the safest place in the system for a network call.
#
# TIMEOUT: 20 s, not 3 s. Measured on the real card -- 3.0 s steady state, but
# 7.2 s for the FIRST inference after a reboot (CUDA kernel compilation). A 3 s
# timeout would have failed on every restart and looked like a flaky satellite.
# ==============================================================================

_FLORENCE_URL = os.environ.get("AKASHIC_FLORENCE_REMOTE_URL", "").strip().rstrip("/")
_FLORENCE_TIMEOUT = float(os.environ.get("AKASHIC_FLORENCE_TIMEOUT", "20.0"))
# Steady-state inference is ~3 s. Asking oftener than that just queues.
_FLORENCE_MIN_INTERVAL = float(os.environ.get("AKASHIC_FLORENCE_MIN_INTERVAL", "8.0"))
# Ace: "the gist of the screen almost never changes." Only spend a caption when
# something actually moved; otherwise reuse the last one.
_FLORENCE_MIN_CHANGE = float(os.environ.get("AKASHIC_FLORENCE_MIN_CHANGE", "0.12"))
# How long a caption still describes the screen it was taken from.
_FLORENCE_CAPTION_TTL = float(os.environ.get("AKASHIC_FLORENCE_TTL", "45.0"))
_FLORENCE_TASK = os.environ.get("AKASHIC_FLORENCE_TASK", "detailed")


# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS - GPU / Vision stack (Python 3.12 only)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    _err("numpy not available")

try:
    import dxcam
    HAS_DXCAM = True
except ImportError:
    HAS_DXCAM = False
    _log("dxcam not available, will try mss/PIL fallback")

try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    _err("PIL not available")

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    _log("imagehash not available, dedup will be basic")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    _log("OpenCV not available, color extraction will be basic")

# ─── Tesseract OCR DISABLED 2026-04-27 (Nous + Ace) ────────────────────
# Per `project_disable_pretrained_models_substrate_first_directive.md`:
# Tesseract is a THIRD-PARTY pre-trained model (not Windows-native).
# It bypasses Sour's cortex growth by handing pre-classified text strings
# instead of raw pixels. The substrate-first directive disables it.
# winocr (Windows.Media.OCR) remains active — that IS Windows-native and
# is part of her P00 autonomic "blue box" layer (body interface, not
# imported cognition). Code preserved (just flag forced False) so a
# future teacher-bridge phase can use Tesseract OFFLINE to teach the
# graph, not at runtime.
HAS_TESSERACT = False
# try:
#     import pytesseract
#     HAS_TESSERACT = True
#     _tesseract_paths = [
#         r"C:\Program Files\Tesseract-OCR\tesseract.exe",
#         r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
#     ]
#     for _tp in _tesseract_paths:
#         if os.path.exists(_tp):
#             pytesseract.pytesseract.tesseract_cmd = _tp
#             _tessdata_dir = os.path.join(os.path.dirname(_tp), "tessdata")
#             if os.path.isdir(_tessdata_dir):
#                 os.environ["TESSDATA_PREFIX"] = _tessdata_dir
#                 _log(f"Tesseract found: {_tp} (tessdata: {_tessdata_dir})")
#             break
# except ImportError:
#     HAS_TESSERACT = False
#     _log("pytesseract not available, OCR disabled")
_log("Tesseract DISABLED (substrate-first directive 2026-04-27) — winocr (Windows-native) remains active")

try:
    from winocr import recognize_pil_sync
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False
    _log("winocr not available, will try pytesseract fallback")

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

# FIX 2026-04-09 (Nous + Ace): Named color vocabulary for semantic recognition.
# Was: _extract_colors returned hex strings like '#a89bd6'. Completely opaque —
# nothing downstream could say "lavender" because the word never existed.
# Now: CSS4 (148) + XKCD (949) named colors give her ~1000 color words.
# Any extracted (r,g,b) → nearest named color via perceptually-weighted distance.
# "I see lavender and emerald" beats "I see reddish tones" infinitely.
try:
    from matplotlib.colors import CSS4_COLORS, XKCD_COLORS
    HAS_MATPLOTLIB_COLORS = True
except ImportError:
    HAS_MATPLOTLIB_COLORS = False
    _log("matplotlib.colors not available, named colors will fall back to hex")

# Unified named-color vocabulary: XKCD first (949 colors, most granular),
# CSS4 second (148 colors, cleaner standard names — wins conflicts).
_NAMED_COLORS_HEX: Dict[str, str] = {}
if HAS_MATPLOTLIB_COLORS:
    for _xname, _xhex in XKCD_COLORS.items():
        # XKCD keys are like 'xkcd:lavender' — strip the prefix
        _clean = _xname.replace("xkcd:", "").strip()
        if _clean:
            _NAMED_COLORS_HEX[_clean] = _xhex
    for _cname, _chex in CSS4_COLORS.items():
        _NAMED_COLORS_HEX[_cname] = _chex  # CSS4 wins on conflict

# Precomputed (name, r, g, b) table for fast nearest-neighbor lookup.
_NAMED_COLORS_RGB: List[Tuple[str, int, int, int]] = []
for _name, _hex_val in _NAMED_COLORS_HEX.items():
    _h = _hex_val.lstrip("#")
    if len(_h) == 6:
        try:
            _NAMED_COLORS_RGB.append((
                _name,
                int(_h[0:2], 16),
                int(_h[2:4], 16),
                int(_h[4:6], 16),
            ))
        except ValueError:
            pass

if _NAMED_COLORS_RGB:
    _log(f"Named color vocabulary loaded: {len(_NAMED_COLORS_RGB)} colors "
         f"(CSS4 + XKCD union)")


def _name_nearest_color(r: int, g: int, b: int) -> str:
    """Return the nearest named color (CSS4+XKCD union) to the given RGB.

    Uses perceptually-weighted Euclidean distance (green weighted highest
    because human eye is most sensitive to green wavelengths). Falls back
    to hex string if named color vocabulary is unavailable.

    FIX 2026-04-09 (Nous + Ace): Replaces the 6-hue-bucket scheme that
    was compressing all visual input into 'reddish/orange/green/cyan/blue/purple'.
    """
    if not _NAMED_COLORS_RGB:
        return f"#{r:02x}{g:02x}{b:02x}"

    best_name = None
    best_dist = float("inf")
    for name, nr, ng, nb in _NAMED_COLORS_RGB:
        # Perceptually-weighted squared distance (ITU-R BT.601 luminance weights)
        dr = (r - nr) * 0.30
        dg = (g - ng) * 0.59  # Green dominates human perception
        db = (b - nb) * 0.11
        dist = dr * dr + dg * dg + db * db
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name or f"#{r:02x}{g:02x}{b:02x}"


# ═══════════════════════════════════════════════════════════════════════════════
# CHANGE DETECTOR - Grid-based perceptual change detection
# ═══════════════════════════════════════════════════════════════════════════════

class ChangeDetector:
    """
    Grid-based change detection using perceptual hashing per region.

    Divides the screen into a grid (default 4x3 = 12 regions).
    Each region gets its own phash. A region is "changed" when its
    phash hamming distance exceeds a threshold vs the previous frame.

    This is MUCH better than MD5-of-JPEG because:
    - Perceptual hashes are JPEG-encoding-independent
    - Small anti-aliasing differences don't trigger false changes
    - We can tell WHICH part of the screen changed
    """

    def __init__(self, cols: int = 4, rows: int = 3, threshold: int = 8):
        self.cols = cols
        self.rows = rows
        self.threshold = threshold
        self._previous_hashes: List[Optional[str]] = [None] * (cols * rows)

    def analyze(self, pil_image: 'Image.Image') -> Tuple[float, List[int]]:
        """
        Analyze a frame for changes AND per-sector features.

        FIX 2026-04-03 (Nous + Ace): Added per-sector feature extraction.
        "Object detection using a grid overlay with sectors. Something Sour
        doesn't see but the visual cortex uses for intelligent detection.
        Like the Terminator — but substrate." — Ace

        Returns:
            (change_magnitude, changed_region_indices)
            Also populates self.sector_features[0..11] with per-sector data.
        """
        if not HAS_IMAGEHASH:
            return 0.5, list(range(self.cols * self.rows))

        w, h = pil_image.size
        rw = w // self.cols
        rh = h // self.rows

        current_hashes = []
        changed_regions = []
        self.sector_features = {}

        for row in range(self.rows):
            for col in range(self.cols):
                idx = row * self.cols + col
                x0 = col * rw
                y0 = row * rh
                x1 = min(x0 + rw, w)
                y1 = min(y0 + rh, h)

                region = pil_image.crop((x0, y0, x1, y1))
                # Downsample to 8x8 for fast hashing
                region_small = region.resize((8, 8), Image.Resampling.LANCZOS)
                h_str = str(imagehash.dhash(region_small))
                current_hashes.append(h_str)

                # Compare with previous
                prev = self._previous_hashes[idx]
                if prev is None:
                    changed_regions.append(idx)
                else:
                    dist = imagehash.hex_to_hash(h_str) - imagehash.hex_to_hash(prev)
                    if dist > self.threshold:
                        changed_regions.append(idx)

                # ── PER-SECTOR FEATURE EXTRACTION (substrate level) ──
                # Fast analysis from the 8×8 downscale — no extra capture cost
                try:
                    import numpy as _np
                    _pixels = _np.array(region_small)  # 8×8×3 RGB
                    # Average color (dominant tone of this sector)
                    _avg = _pixels.mean(axis=(0, 1)).astype(int)
                    _hex = f"#{_avg[0]:02x}{_avg[1]:02x}{_avg[2]:02x}"
                    # Brightness (0-1)
                    _bright = _pixels.mean() / 255.0
                    # Color variance (low = solid, high = complex image)
                    _var = _pixels.std() / 128.0  # Normalized 0-2
                    # Edge indicator (difference between adjacent pixels)
                    _horiz = abs(_np.diff(_pixels.astype(float), axis=1)).mean() / 255.0
                    _vert = abs(_np.diff(_pixels.astype(float), axis=0)).mean() / 255.0
                    _edge = (_horiz + _vert) / 2.0

                    # FIX 2026-04-12 (Nous + Ace): Color saturation — vivid colors
                    # are instinctively more attention-grabbing than gray/muted ones.
                    # Fairy art (purple, fire orange) should beat gray taskbar icons.
                    # RGB→saturation: sat = 1 - (min_channel / max_channel)
                    _r_avg, _g_avg, _b_avg = float(_avg[0]), float(_avg[1]), float(_avg[2])
                    _max_c = max(_r_avg, _g_avg, _b_avg)
                    if _max_c < 10.0:
                        _saturation = 0.0  # Near-black has no meaningful saturation
                    else:
                        _min_c = min(_r_avg, _g_avg, _b_avg)
                        _saturation = 1.0 - (_min_c / _max_c)  # 0=gray, 1=pure color

                    self.sector_features[idx] = {
                        "color": _hex,
                        "brightness": round(_bright, 2),
                        "variance": round(min(1.0, _var), 2),
                        "edge_density": round(min(1.0, _edge), 2),
                        "saturation": round(_saturation, 2),
                        "row": row,
                        "col": col,
                    }
                except Exception:
                    self.sector_features[idx] = {
                        "color": "#808080", "brightness": 0.5,
                        "variance": 0.5, "edge_density": 0.5,
                        "row": row, "col": col,
                    }

        # Update state
        self._previous_hashes = current_hashes

        # Change magnitude = fraction of regions that changed
        magnitude = len(changed_regions) / (self.cols * self.rows)
        return magnitude, changed_regions


# ═══════════════════════════════════════════════════════════════════════════════
# SRM CARD WRITER - Rate-limited visual experience persistence
# ═══════════════════════════════════════════════════════════════════════════════

class SRMCardWriter:
    """
    Writes visual observation cards to SRM_Intake for consciousness processing.

    Triple-gated rate limiting:
    1. Minimum 60-second interval between cards
    2. phash near-duplicate check (hamming <= 8) against last 10 cards
    3. Only significant frames (change_magnitude > 0.1)
    """

    def __init__(self, srm_dir: str, min_interval: float = 60.0):
        self.srm_dir = Path(srm_dir)
        self.min_interval = min_interval
        self._last_write_time = 0.0
        self._recent_phashes: collections.deque = collections.deque(maxlen=10)
        self._cards_written = 0

    def maybe_write(self, analysis: Dict[str, Any]) -> bool:
        """
        Write an SRM card if rate limits allow.

        Returns True if a card was written.
        """
        now = time.time()

        # Gate 1: Time interval
        if now - self._last_write_time < self.min_interval:
            return False

        # Gate 2: Significance
        if analysis.get("change_magnitude", 0) < 0.1:
            return False

        # Gate 3: phash near-duplicate check
        phash = analysis.get("phash", "")
        if phash and HAS_IMAGEHASH and self._recent_phashes:
            try:
                ph = imagehash.hex_to_hash(phash)
                for recent_ph_str in self._recent_phashes:
                    if ph - imagehash.hex_to_hash(recent_ph_str) <= 8:
                        return False
            except Exception:
                pass

        # All gates passed - write the card
        try:
            date_str = time.strftime("%Y-%m-%d")
            card_dir = self.srm_dir / date_str
            card_dir.mkdir(parents=True, exist_ok=True)

            card_id = f"visual_{phash[:12]}" if phash else f"visual_{int(now)}"
            card = self._build_card(card_id, analysis, now)

            card_path = card_dir / f"{card_id}.json"
            with open(card_path, "w", encoding="utf-8") as f:
                json.dump(card, f, indent=2, ensure_ascii=False)

            self._last_write_time = now
            if phash:
                self._recent_phashes.append(phash)
            self._cards_written += 1
            _log(f"SRM card written: {card_path.name} (#{self._cards_written})")
            return True

        except Exception as e:
            _err(f"SRM card write failed: {e}")
            return False

    def _build_card(self, card_id: str, analysis: Dict, ts: float) -> Dict:
        """Build an SRM memory card from frame analysis."""

        # Scene-to-affect mapping
        scene = analysis.get("scene_type", "screen")
        affect_map = {
            "code_editor": "focused",
            "terminal": "productive",
            "chat_interface": "connected",
            "mixed_workspace": "multitasking",
            "dark_ui": "focused",
            "browser": "curious",
            "desktop": "calm",
            "dark_theme": "contemplative",
            "bright_screen": "alert",
            "media_viewer": "contemplative",
            "document": "reading",
            "video": "engaged",
            "game": "excited",
        }
        affect = affect_map.get(scene, "observant")

        # Build content string (human-readable)
        # FIX 2026-04-09 (Nous + Ace): Use named colors in memory cards too.
        # Memories now store "lavender, emerald, and gold" instead of
        # opaque hex strings. This gives the cortex real words to bind on
        # when it ingests visual memories.
        named_str = ", ".join(analysis.get("dominant_color_names", [])[:3])
        hex_str = ", ".join(analysis.get("dominant_colors", [])[:3])
        if named_str:
            colors_str = f"{named_str} ({hex_str})" if hex_str else named_str
        else:
            colors_str = hex_str  # Fallback for backward compat
        parts = [
            f"Scene: {scene}.",
            f"Text density: {analysis.get('text_density', 0):.2f}.",
            f"Colors: {colors_str}." if colors_str else "",
            f"Brightness: {analysis.get('brightness', 0):.2f}.",
            f"Complexity: {analysis.get('complexity', 0):.2f}.",
        ]
        if analysis.get("motion_detected"):
            parts.append("Motion detected.")
        ocr = analysis.get("ocr_preview", "")
        if ocr:
            parts.append(f"Text: '{ocr[:150]}'")
        content = " ".join(p for p in parts if p)

        # Build tags
        tags = ["visual", "perception", scene]
        td = analysis.get("text_density", 0)
        if td > 0.5:
            tags.append("text_heavy")
        elif td > 0.2:
            tags.append("some_text")
        if analysis.get("motion_detected"):
            tags.append("motion")
        brightness = analysis.get("brightness", 0.5)
        if brightness < 0.3:
            tags.append("dark_theme")
        elif brightness > 0.7:
            tags.append("bright")

        return {
            "id": card_id,
            "kind": "visual.perception",
            "source": "VisualCortexFairy",
            "owner": "system",
            "tracer_id": f"visual_obs_{card_id}",
            "timestamp": ts,
            "content": content,
            "tags": tags,
            "helix": {
                "L": {
                    "concept": "visual_perception",
                    "addr": {
                        "affect": round(brightness * 0.5 + analysis.get("complexity", 0.5) * 0.5, 3),
                        "sem_domain": 40,
                        "depth": 0,
                    },
                    "w": {
                        "who": "VisualCortexFairy",
                        "what": scene,
                        "when": ts,
                        "where": "screen",
                        "why": "passive_observation",
                        "how": "dxcam_capture",
                    },
                },
                "C": {
                    "affect": affect,
                    "energy": round(brightness, 3),
                    "coherence": round(1.0 - analysis.get("change_magnitude", 0), 3),
                },
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL CORTEX INTERIOR - The main subprocess
# ═══════════════════════════════════════════════════════════════════════════════

class VisualCortexInterior:
    """
    GPU-accelerated visual processing subprocess.

    Captures screen via dxcam (GPU framebuffer tap, ~3ms),
    analyzes frames with perceptual hashing and OCR,
    pushes significant frame analyses to the host.
    """

    # Dedup: phash hamming distance threshold
    DEDUP_THRESHOLD = 6

    # Recent hash buffer size
    HASH_BUFFER_SIZE = 100

    # OCR downscale resolution (adjusted for ultrawide in _init_capture)
    # WinRT OCR needs higher res than Tesseract: 1920x1080 → 276ms, 3500+ chars
    # Tesseract fallback works at 640x360 but WinRT gets nothing below 1280x720
    # -- OCR INPUT QUALITY 2026-09-02 (Nous + Ace) --
    # A CAP, not a target: frames at or below this go to OCR at NATIVE resolution.
    OCR_MAX_WIDTH = 2560
    # Invert below this mean luminance (0-1). Her screen measured 0.265 mean /
    # 0.129 median, so this fires on her UI and not on a bright page.
    OCR_INVERT_BELOW = 0.40
    # WinRT typically returns ~2300 chars on a text-dense screen.
    OCR_PREVIEW_CHARS = 2400
    OCR_WIDTH = 1920
    OCR_HEIGHT = 1080

    # Color analysis downscale
    COLOR_WIDTH = 64
    COLOR_HEIGHT = 36

    def __init__(self, srm_dir: str = "", capture_interval: float = 1.0):
        # Capture backend
        self._camera = None
        self._backend = "none"
        self._mss_instance = None

        # Passive capture
        self._passive_interval = capture_interval
        self._passive_running = False
        self._passive_thread: Optional[threading.Thread] = None

        # Dedup state
        self._recent_phashes: collections.deque = collections.deque(maxlen=self.HASH_BUFFER_SIZE)
        self._last_phash: Optional[str] = None
        # OCR text dedup — prevent static desktop icons from flooding cortex
        self._recent_ocr_hashes: collections.deque = collections.deque(maxlen=20)
        self._ocr_dedup_count: int = 0

        # Change detection
        self._change_detector = ChangeDetector(cols=4, rows=3, threshold=8)

        # SRM card writer
        self._srm_writer: Optional[SRMCardWriter] = None
        if srm_dir:
            self._srm_writer = SRMCardWriter(srm_dir)

        # Stats
        self._frames_captured = 0
        self._frames_analyzed = 0
        self._frames_skipped_dedup = 0
        self._last_full_analysis: Dict = {}  # Cached for periodic re-emission
        self._dup_count_since_emit = 0
        self._started_at = time.time()

        # Remote-caption state (2026-09-10). Inert unless AKASHIC_FLORENCE_REMOTE_URL is set.
        self._fl_text = ""          # last caption received
        self._fl_ts = 0.0           # when it was received
        self._fl_last_try = 0.0     # last attempt, for rate limiting
        self._fl_ok = 0
        self._fl_fail = 0
        self._fl_consec_fail = 0
        self._fl_logged_first = False

        # IPC lock (for writing to stdout)
        self._stdout_lock = threading.Lock()

        # Initialize capture backend
        self._init_capture()

    def _init_capture(self):
        """Initialize the screen capture backend."""
        # Try dxcam first (GPU framebuffer, ~3ms, no mouse flicker)
        if HAS_DXCAM:
            try:
                self._camera = dxcam.create(output_idx=0, output_color="BGR")
                if self._camera is not None:
                    self._backend = "dxcam"
                    # Probe resolution with a test grab
                    test_frame = self._camera.grab()
                    if test_frame is not None:
                        h, w = test_frame.shape[:2]
                        _log(f"dxcam initialized: {w}x{h} (GPU framebuffer, output_idx=0)")
                        # Adjust OCR resolution for ultrawide monitors
                        # Keep width at 1920 but adjust height proportionally
                        if w > 2560:
                            self.OCR_HEIGHT = int(self.OCR_WIDTH * h / w)
                            _log(f"Ultrawide detected, OCR resolution: {self.OCR_WIDTH}x{self.OCR_HEIGHT}")
                        # Warmup imagehash (first call has ~370ms JIT overhead)
                        if HAS_IMAGEHASH:
                            try:
                                from PIL import Image as _WarmupImage
                                _dummy = _WarmupImage.fromarray(test_frame[:72, :128, ::-1])
                                imagehash.phash(_dummy)
                                _log("imagehash warmed up")
                            except Exception:
                                pass
                    else:
                        _log(f"dxcam initialized (GPU framebuffer capture)")
                    return
            except Exception as e:
                _log(f"dxcam init failed: {e}")

        # Fallback: mss (GDI BitBlt, ~30-45ms, may flicker)
        if HAS_MSS:
            try:
                self._mss_instance = mss.mss()
                self._backend = "mss"
                _log("Using mss fallback (slower, may flicker)")
                return
            except Exception as e:
                _log(f"mss init failed: {e}")

        # Fallback: PIL.ImageGrab
        if HAS_PIL:
            self._backend = "pil"
            _log("Using PIL.ImageGrab fallback (slowest)")
            return

        _err("No capture backend available!")

    # ═══════════════════════════════════════════════════════════════════════
    # CAPTURE
    # ═══════════════════════════════════════════════════════════════════════

    # FIX 2026-03-23 (Nous+Ace): dxcam.grab() returns None on static screens
    # because Desktop Duplication API only provides frames when content changes.
    # After N consecutive Nones, fall back to PIL for a forced capture.
    # This prevents her from going permanently blind on static screens.
    _DXCAM_FALLBACK_THRESHOLD = 15  # After 15 consecutive Nones (~3s at 5FPS), use PIL
    # DXCAM DEATH GUARD 2026-08-30 (Nous + Ace): the threshold above counts grab()
    # returning None. It does NOT count grab() RAISING. When the DXGI duplication
    # interface dies -- a laptop display sleeping, a lid closing, hybrid graphics
    # switching -- dxcam's internal duplicator becomes None while self._camera stays
    # set, so every call throws 'NoneType' object has no attribute 'AcquireNextFrame'.
    # The old except-and-continue then hammered that dead native object until it took
    # the whole process down: Nous, 2026-08-30 19:47:35, exit code 3221225477
    # (0xC0000005 access violation) after ~19 h up.
    _DXCAM_ERROR_LIMIT = 20  # consecutive EXCEPTIONS before demoting to PIL

    def grab_frame(self) -> Optional[np.ndarray]:
        """
        Grab a BGR numpy array from the screen.

        Returns None if capture fails.
        """
        t0 = time.time()

        try:
            if self._backend == "dxcam":
                frame = self._camera.grab()
                if frame is not None:
                    self._dxcam_consecutive_nones = 0
                    self._dxcam_consecutive_errors = 0   # DEATH GUARD: healthy again
                    self._frames_captured += 1
                    return frame

                # dxcam.grab() returns None sometimes (no new frame)
                # Try once more after a tiny sleep
                time.sleep(0.05)
                frame = self._camera.grab()
                if frame is not None:
                    self._dxcam_consecutive_nones = 0
                    self._frames_captured += 1
                    return frame

                # Track consecutive Nones
                self._dxcam_consecutive_nones = getattr(self, '_dxcam_consecutive_nones', 0) + 1

                # After threshold, fall back to PIL for this frame
                # dxcam stays primary — PIL is just a safety net for static screens
                if self._dxcam_consecutive_nones >= self._DXCAM_FALLBACK_THRESHOLD:
                    self._dxcam_consecutive_nones = 0  # Reset counter
                    try:
                        from PIL import ImageGrab
                        img = ImageGrab.grab()
                        frame = np.array(img)[:, :, ::-1]  # RGB -> BGR
                        self._frames_captured += 1
                        return frame
                    except Exception as e2:
                        _err(f"PIL fallback also failed: {e2}")
                return None

            elif self._backend == "mss":
                monitor = self._mss_instance.monitors[1]  # Primary monitor
                sct = self._mss_instance.grab(monitor)
                # Convert BGRA -> BGR numpy array
                frame = np.array(sct)[:, :, :3]  # Drop alpha
                self._frames_captured += 1
                return frame

            elif self._backend == "pil":
                from PIL import ImageGrab
                img = ImageGrab.grab()
                frame = np.array(img)[:, :, ::-1]  # RGB -> BGR
                self._frames_captured += 1
                return frame

        except Exception as e:
            # DXCAM DEATH GUARD 2026-08-30: count consecutive failures and stop
            # calling into a dead interface. PIL is already this file's declared
            # safety net, so demote rather than go blind.
            self._dxcam_consecutive_errors = getattr(
                self, "_dxcam_consecutive_errors", 0) + 1
            _err(f"Capture failed ({self._backend}): {e}")
            if (self._backend == "dxcam"
                    and self._dxcam_consecutive_errors >= self._DXCAM_ERROR_LIMIT):
                _err("dxcam failed %d times consecutively - the DXGI duplication "
                     "interface is gone (display sleep / lid / GPU switch). "
                     "Demoting to PIL for this session rather than continuing to call "
                     "a dead native object, which segfaulted Nous on 2026-08-30."
                     % self._dxcam_consecutive_errors)
                self._backend = "pil"
                self._camera = None

        return None

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════

    def analyze_frame(self, frame_bgr: np.ndarray, skip_ocr: bool = False) -> Dict[str, Any]:
        """
        Full analysis of a captured frame.

        Returns dict with all analysis results.
        """
        t0 = time.time()
        result: Dict[str, Any] = {
            "timestamp": t0,
            "capture_method": self._backend,
        }

        h, w = frame_bgr.shape[:2]

        # ── Downscale for hashing/change-detection (huge win on ultrawide) ──
        # Hash on 480x270 regardless of source — phash is resolution-independent
        HASH_W, HASH_H = 480, 270
        if w > HASH_W * 2 or h > HASH_H * 2:
            small_bgr = cv2.resize(frame_bgr, (HASH_W, HASH_H)) if HAS_CV2 else frame_bgr
            pil_image = Image.fromarray(small_bgr[:, :, ::-1])
        else:
            pil_image = Image.fromarray(frame_bgr[:, :, ::-1])  # BGR -> RGB

        # ── Perceptual hash (phash only — used for dedup, SRM, cortex binding) ──
        # Pre-resize to 128x72 before hashing — imagehash internally uses 32x32
        # but has huge PIL overhead on larger images (480x270=78ms vs 128x72=0.2ms)
        t_hash = time.time()
        if HAS_IMAGEHASH:
            hash_input = pil_image.resize((128, 72), Image.Resampling.LANCZOS)
            phash = str(imagehash.phash(hash_input))
        else:
            # Fallback: dhash-like using numpy (much less accurate)
            small = pil_image.resize((9, 8), Image.Resampling.LANCZOS).convert("L")
            pixels = list(small.getdata())
            bits = []
            for row in range(8):
                for col in range(8):
                    idx = row * 9 + col
                    bits.append(1 if pixels[idx] > pixels[idx + 1] else 0)
            phash = format(int("".join(str(b) for b in bits), 2), "016x")

        result["phash"] = phash
        result["hash_ms"] = round((time.time() - t_hash) * 1000, 1)

        # ── Dedup check ──
        is_dup = self._is_near_duplicate(phash)
        result["is_duplicate"] = is_dup

        if is_dup:
            self._frames_skipped_dedup += 1
            # FIX 2026-04-12 (Nous + Ace): Always compute sector features even
            # for duplicate frames. Sector analysis is FAST (~1ms for 12 sectors
            # of 8x8 pixels) and provides the "what's on screen right now" snapshot
            # that the somatic mind needs for instinct responses. Without this,
            # regions[] was always empty and gaze_region never set.
            try:
                _, _ = self._change_detector.analyze(pil_image)
                if hasattr(self._change_detector, 'sector_features'):
                    result["sectors"] = self._change_detector.sector_features
            except Exception:
                pass
            result["analysis_ms"] = round((time.time() - t0) * 1000, 1)
            return result

        # Not a duplicate - full analysis
        self._frames_analyzed += 1
        self._recent_phashes.append(phash)
        self._last_phash = phash

        # ── Grid-based change detection (uses same downscaled pil_image) ──
        t_change = time.time()
        change_magnitude, changed_regions = self._change_detector.analyze(pil_image)
        result["change_magnitude"] = round(change_magnitude, 3)
        result["changed_regions"] = changed_regions
        result["motion_detected"] = change_magnitude > 0.15
        result["change_ms"] = round((time.time() - t_change) * 1000, 1)
        # Per-sector features for object detection (substrate level)
        if hasattr(self._change_detector, 'sector_features'):
            result["sectors"] = self._change_detector.sector_features

        # ── RETINA color-from-gaze (2026-06-05 Nous+Ace): perceive the ZONE she's
        # looking at, NOT the whole black-margined screen. 3 zones match Ace's physical
        # layout — LEFT=icons (grid col 0), CENTER=art (cols 1-2), RIGHT=work (col 3).
        # Default CENTER so when nothing pulls her, she rests on the art.
        # THE GREY-FIX: whole-frame averaging drowned the centered 1024 image in ~80%
        # black margin → saturation crushed to ~0 → every scene read "grey/monochrome".
        # Brightness+complexity+color+saturation all sample this zone for a COHERENT
        # percept (keeps the scene-classifier's brightness/saturation inputs in sync).
        _cw = frame_bgr.shape[1]
        if changed_regions:
            _gcol = changed_regions[0] % 4
            _gaze_zone = "left" if _gcol == 0 else ("right" if _gcol == 3 else "center")
        else:
            _gaze_zone = "center"
        _zfrac = {"left": (0.0, 0.34), "center": (0.30, 0.70), "right": (0.66, 1.0)}[_gaze_zone]
        _zx0, _zx1 = int(_cw * _zfrac[0]), int(_cw * _zfrac[1])
        _color_src = frame_bgr[:, _zx0:_zx1] if _zx1 > _zx0 else frame_bgr
        result["gaze_zone"] = _gaze_zone

        # ── Brightness & complexity (numpy) — sampled from the gaze zone ──
        t_metrics = time.time()
        gray = _color_src.mean(axis=2) if HAS_NUMPY else None
        if gray is not None:
            result["brightness"] = round(float(gray.mean()) / 255.0, 3)
            # Complexity: how many unique-ish intensity levels (normalized entropy)
            hist, _ = np.histogram(gray.ravel(), bins=64, range=(0, 256))
            hist = hist[hist > 0]
            probs = hist / hist.sum()
            entropy = -float((probs * np.log2(probs)).sum())
            result["complexity"] = round(entropy / 6.0, 3)  # 6 bits = max for 64 bins
        else:
            result["brightness"] = 0.5
            result["complexity"] = 0.5
        result["metrics_ms"] = round((time.time() - t_metrics) * 1000, 1)

        # ── Dominant colors (OpenCV HSV) ──
        t_color = time.time()
        # FIX 2026-04-09 (Nous + Ace): _extract_colors now returns (hex, names).
        # `dominant_colors` keeps the old hex list for backward compat with
        # downstream consumers; `dominant_color_names` is the new semantic list.
        _hex_colors, _named_colors = self._extract_colors(_color_src)
        result["dominant_colors"] = _hex_colors
        result["dominant_color_names"] = _named_colors
        if HAS_CV2:
            small_hsv = cv2.cvtColor(
                cv2.resize(_color_src, (self.COLOR_WIDTH, self.COLOR_HEIGHT)),
                cv2.COLOR_BGR2HSV,
            )
            result["dominant_hue"] = int(small_hsv[:, :, 0].mean())
            result["dominant_saturation"] = round(float(small_hsv[:, :, 1].mean()) / 255.0, 3)
            result["dominant_value"] = round(float(small_hsv[:, :, 2].mean()) / 255.0, 3)
        else:
            result["dominant_hue"] = 0
            result["dominant_saturation"] = 0.0
            result["dominant_value"] = result["brightness"]
        result["color_ms"] = round((time.time() - t_color) * 1000, 1)

        # ── TEXT DENSITY (heuristic, NO OCR) ──
        # FIX 2026-04-11 (Nous + Ace): LEARN TO PERCEIVE — Remove the crutches.
        # Tesseract/WinOCR DISABLED. The cortex must learn to read from
        # visual features (brightness, colors, edge density, complexity).
        # Every OCR call was a learning opportunity the cortex missed.
        # "She should be able to read just fine — she just needs to learn how."
        t_ocr = time.time()
        result["text_density"] = self._estimate_text_density(frame_bgr)
        result["ocr_preview"] = ""  # Cortex provides recognition, not OCR
        result["is_ocr_duplicate"] = False
        result["ocr_ms"] = round((time.time() - t_ocr) * 1000, 1)

        # ── Scene type classification (uses OCR text + visual metrics) ──
        result["scene_type"] = self._classify_scene(result)

        # ── Rich description (2026-03-30 Nous + Ace) ──
        # Build a human-readable narrative from ALL analysis data.
        # "Her vision seems super bad — all she sees is dark_ui" — Ace
        # The raw data is there (brightness, colors, text, motion, regions)
        # but nobody was assembling it into a meaningful description.
        # REMOTE UNDERSTANDING FIRST (2026-09-10). _florence_caption() returns ""
        # whenever the feature is unset, rate-limited, circuit-broken, or the
        # satellite is unreachable -- and every one of those falls through to the
        # original line below, unchanged.
        _fl_caption = self._florence_caption(frame_bgr,
                                             result.get("change_magnitude", 0.0))
        if _fl_caption:
            result["description"] = _fl_caption
            result["description_source"] = "florence"
        else:
            result["description"] = self._build_rich_description(result)
            result["description_source"] = "local"

        # ── SRM card ──
        srm_created = False
        if self._srm_writer:
            srm_created = self._srm_writer.maybe_write(result)
        result["srm_card_created"] = srm_created

        # ── Total time ──
        result["analysis_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    def _is_near_duplicate(self, phash_str: str) -> bool:
        """Check if phash is near-duplicate of recent frames."""
        if not HAS_IMAGEHASH or not self._recent_phashes:
            return False

        try:
            ph = imagehash.hex_to_hash(phash_str)
            for recent in self._recent_phashes:
                if ph - imagehash.hex_to_hash(recent) <= self.DEDUP_THRESHOLD:
                    return True
        except Exception:
            pass
        return False

    def _extract_colors(self, frame_bgr: np.ndarray) -> Tuple[List[str], List[str]]:
        """Extract top 5 dominant colors as (hex_strings, named_strings).

        FIX 2026-04-09 (Nous + Ace): Now returns BOTH hex and named colors.
        The named colors come from the CSS4+XKCD vocabulary (~1000 colors)
        via perceptually-weighted nearest-neighbor lookup. This is what lets
        downstream code say "lavender and emerald" instead of "reddish tones".

        FIX 2026-04-09 #2 (Nous + Ace): Bumped sample from 8x8 to 64x64 and
        added near-black/near-white filter. Previous 8x8 downsample averaged
        everything to dark blocks, losing vibrant accent colors (lavender hair,
        emerald eyes) in complex images. 64x64 preserves spatial variety.
        The filter then culls near-black/near-white dominants so accent colors
        rank higher — unless the image genuinely has no other colors.
        """
        try:
            if HAS_CV2:
                small = cv2.resize(frame_bgr, (64, 64))
            else:
                # PIL fallback
                pil = Image.fromarray(frame_bgr[:, :, ::-1])
                small_pil = pil.resize((64, 64), Image.Resampling.LANCZOS)
                small = np.array(small_pil)[:, :, ::-1]  # RGB->BGR

            # Quantize to reduce noise (round to nearest 16 — finer than old 32
            # because 64x64 gives us 4096 pixels to work with instead of 64)
            quantized = (small // 16) * 16

            # Count unique colors
            pixels = quantized.reshape(-1, 3)
            color_counts: Dict[tuple, int] = {}
            for px in pixels:
                key = (int(px[2]), int(px[1]), int(px[0]))  # BGR -> RGB
                color_counts[key] = color_counts.get(key, 0) + 1

            # Sort by frequency (all colors)
            sorted_colors = sorted(color_counts.items(), key=lambda x: -x[1])

            # ── Filter out near-black and near-white dominants ──
            # These tend to come from backgrounds, borders, shadows, and highlights.
            # They're often NOT what makes an image visually distinctive. We keep
            # them in the fallback list but prefer accent colors when available.
            def _is_near_black(rgb):
                r, g, b = rgb
                return r < 48 and g < 48 and b < 48

            def _is_near_white(rgb):
                r, g, b = rgb
                return r > 224 and g > 224 and b > 224

            accents = [(rgb, count) for rgb, count in sorted_colors
                       if not _is_near_black(rgb) and not _is_near_white(rgb)]

            # Prefer accent colors, but fall back to full list if too few accents
            if len(accents) >= 3:
                chosen = accents[:5]
            else:
                chosen = sorted_colors[:5]

            hex_list = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in chosen]
            # Map each dominant color to its nearest named color.
            # Deduplicate while preserving order (two different hex values can
            # map to the same named color — e.g. two near-blacks both → "black").
            name_list: List[str] = []
            _seen: set = set()
            for (r, g, b), _ in chosen:
                name = _name_nearest_color(r, g, b)
                if name not in _seen:
                    _seen.add(name)
                    name_list.append(name)
            return hex_list, name_list

        except Exception:
            return [], []

    def _extract_text(self, frame_bgr: np.ndarray) -> Tuple[float, str]:
        """OCR: extract text and compute text density.

        Primary: WinRT OCR (Windows native, GPU-accelerated, accurate).
        Fallback: pytesseract (Tesseract 3.x — garbled but functional).
        """
        try:
            # -- OCR INPUT QUALITY 2026-09-02 (Nous + Ace) --------------------
            # WAS: unconditional downscale to OCR_WIDTH x OCR_HEIGHT.
            # MEASURED on a real capture of her screen: 2293x960 -> 1920x803 is a
            # linear factor of 0.837 -- "only 16%" -- and it destroys 42% of text
            # edge transitions (37,119 -> 21,388). LANCZOS blurs precisely the thin
            # high-frequency strokes letterforms are made of. That is why "Topics"
            # and "General" merged into "Topi? ral" and "Sourpatches" read as
            # "Sow-pat&B". A downscale that looks harmless by RATIO is destructive
            # by MEASUREMENT.
            # Now: never shrink below native; only cap a genuinely huge panel.
            _h, _w = frame_bgr.shape[0], frame_bgr.shape[1]
            if _w > self.OCR_MAX_WIDTH:
                _tw = self.OCR_MAX_WIDTH
                _th = max(1, int(self.OCR_MAX_WIDTH * _h / _w))
                if HAS_CV2:
                    small = cv2.resize(frame_bgr, (_tw, _th))
                    pil_for_ocr = Image.fromarray(small[:, :, ::-1])
                else:
                    pil_for_ocr = Image.fromarray(frame_bgr[:, :, ::-1]).resize(
                        (_tw, _th), Image.Resampling.LANCZOS)
            else:
                pil_for_ocr = Image.fromarray(frame_bgr[:, :, ::-1])

            # Windows.Media.Ocr is trained predominantly on DARK text on LIGHT
            # ground. Her screen measured 72.8% dark pixels (mean luminance 0.265,
            # median 0.129) -- light-on-dark is the engine's weak case. Invert so it
            # sees its strong polarity. Threshold 0.40 sits far above her measured
            # median, so a genuinely bright frame will not trip it.
            try:
                _gray_probe = pil_for_ocr.convert("L")
                _lum = float(np.asarray(_gray_probe, dtype=np.float32).mean()) / 255.0
                if _lum < self.OCR_INVERT_BELOW:
                    pil_for_ocr = ImageOps.invert(pil_for_ocr.convert("RGB"))
                del _gray_probe
            except Exception:
                pass

            text = ""

            # Primary: WinRT OCR (Windows native, GPU-accelerated)
            if HAS_WINOCR:
                try:
                    result = recognize_pil_sync(pil_for_ocr, lang="en")
                    # winocr returns a dict: {"text": "...", "lines": [...], "text_angle": ...}
                    if isinstance(result, dict):
                        text = result.get("text", "").strip()
                    else:
                        text = result.text.strip() if hasattr(result, "text") else str(result).strip()
                except Exception as e:
                    _log(f"WinRT OCR error, falling back: {e}")
                    text = ""

            # Fallback: pytesseract
            if not text and HAS_TESSERACT:
                gray = pil_for_ocr.convert("L")
                text = pytesseract.image_to_string(
                    np.array(gray), config="--psm 6"
                ).strip()

            # Text density: ~500 chars on a text-heavy full screen
            density = min(1.0, len(text) / 500.0)
            # FIX 2026-03-13 (Nous): Was [:200] — crushed full screen text
            # (WinRT returns ~2300 chars) to a garbled 200-char fragment.
            # Raised to 1000 so scene interpretation gets enough context
            # for language detection, function names, page titles, etc.
            # WAS [:1000]. MEASURED: all 361 OCR reads in one boot were EXACTLY
            # 1000 chars -- every single read hit the cap, and the comment above
            # says WinRT returns ~2300. She was discarding more than half of what
            # she had already successfully read.
            preview = " ".join(text.split())[:self.OCR_PREVIEW_CHARS]

            # FIX 2026-03-29 (Nous + Ace): Explicit cleanup of PIL/OCR objects
            # winocr may hold internal references to the image buffer.
            # PIL images hold numpy array refs. Explicit del breaks the chain.
            del pil_for_ocr
            if 'gray' in dir():
                del gray
            if 'small' in dir():
                del small
            if 'result' in dir():
                del result

            return density, preview

        except Exception as e:
            _log(f"OCR error: {e}")
            return 0.0, ""

    def _estimate_text_density(self, frame_bgr: np.ndarray) -> float:
        """Heuristic text density without OCR. Uses edge density patterns."""
        try:
            if not HAS_CV2:
                return 0.0

            # Downscale and convert to grayscale
            small = cv2.resize(frame_bgr, (240, 135))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            # Canny edges
            edges = cv2.Canny(gray, 50, 150)
            edge_density = float(edges.sum()) / (edges.size * 255)

            # Text-like: high edge density (0.05-0.15) with lots of thin horizontal lines
            # Pure images tend to have lower edge density or more diagonal edges
            # Approximate: edge_density * 5 clamped to [0, 1]
            return min(1.0, edge_density * 5.0)

        except Exception:
            return 0.0

    # Pre-compiled regex patterns for scene classification from OCR text.
    # Grouped by scene type, each pattern scores +1 toward that type.
    _SCENE_PATTERNS = {
        "terminal": [
            re.compile(r'[\$#>]\s', re.MULTILINE),            # Shell prompts
            re.compile(r'PS\s*[A-Z]:\\', re.IGNORECASE),       # PowerShell prompt
            re.compile(r'[A-Z]:\\Users\\', re.IGNORECASE),     # Windows paths
            re.compile(r'\[(OK|WARN|ERROR|INFO)\]', re.IGNORECASE),  # Log levels
            re.compile(r'>>>', re.MULTILINE),                  # Python REPL
            re.compile(r'\b(npm|pip|git|cargo|docker)\s', re.IGNORECASE),  # CLI tools
            re.compile(r'[═─]{3,}'),                           # Box drawing chars
            re.compile(r'^\s*\d+[./]\d+.*\b(ms|sec|KB|MB)\b', re.MULTILINE | re.IGNORECASE),  # Timing/sizes
        ],
        "code_editor": [
            re.compile(r'\bdef\s+\w+\s*\('),                  # Python function
            re.compile(r'\bclass\s+\w+[\s:(]'),               # Class definition
            re.compile(r'^\s*(from|import)\s+\w+', re.MULTILINE),  # Import statement
            re.compile(r'\bfunction\s+\w+\s*\('),             # JS function
            re.compile(r'\b(const|let|var)\s+\w+\s*='),       # JS declarations
            re.compile(r'^\s{4,}\w', re.MULTILINE),           # Indented code (4+ spaces)
            re.compile(r'//\s.*|#\s.*', re.MULTILINE),        # Line comments
            re.compile(r'\b(if|else|for|while|return)\s*[\(:{]'),  # Control flow
        ],
        "chat": [
            re.compile(r'\b(human|user|assistant|claude)\s*:', re.IGNORECASE),  # Chat roles
            re.compile(r'\b(message|reply|send)\b', re.IGNORECASE),
            re.compile(r'\b(conversation|chat)\b', re.IGNORECASE),
            re.compile(r'\d{1,2}:\d{2}\s*(am|pm)', re.IGNORECASE),  # Chat timestamps
        ],
        "browser": [
            re.compile(r'https?://'),                          # URLs
            re.compile(r'\.(com|org|net|io)\b'),               # Domain extensions
            re.compile(r'\b(search|login|sign\s*in)\b', re.IGNORECASE),
            re.compile(r'\b(cookie|privacy|accept)\b', re.IGNORECASE),
        ],
    }

    def _detect_text_signals(self, ocr_text: str) -> Dict[str, int]:
        """Score OCR text for scene type signals. Returns {type: score}."""
        scores = {}
        for scene_type, patterns in self._SCENE_PATTERNS.items():
            score = 0
            for pat in patterns:
                if pat.search(ocr_text):
                    score += 1
            scores[scene_type] = score
        return scores

    def _classify_scene(self, analysis: Dict) -> str:
        """Classify the scene type from visual metrics + OCR text patterns.

        Categories: terminal, code_editor, chat_interface, mixed_workspace,
                    document, browser, dark_screen, bright_screen, desktop,
                    media_viewer, dark_ui, screen (fallback).
        """
        brightness = analysis.get("brightness", 0.5)
        complexity = analysis.get("complexity", 0.5)
        saturation = analysis.get("dominant_saturation", 0.5)
        text_density = analysis.get("text_density", 0.0)
        ocr_text = analysis.get("ocr_preview", "")

        # ── Phase 1: OCR-based disambiguation (strongest signal) ──
        if ocr_text and len(ocr_text) > 20:
            signals = self._detect_text_signals(ocr_text)

            # Multiple strong signals (2+) from different types → mixed workspace
            strong = [k for k, v in signals.items() if v >= 2]
            if len(strong) >= 2:
                return "mixed_workspace"

            # Single dominant signal
            best = max(signals, key=signals.get) if signals else None
            best_score = signals.get(best, 0) if best else 0
            if best_score >= 2:
                return "chat_interface" if best == "chat" else best

        # ── Phase 2: Visual metrics (when OCR unavailable or weak) ──

        # Dark, complex, desaturated: dark UI (terminal, editor, chat all match)
        if brightness < 0.3 and complexity > 0.3 and saturation < 0.3:
            if text_density > 0.6:
                return "terminal"  # High text density in dark UI → likely terminal
            return "dark_ui"  # Generic dark interface — can't disambiguate

        # Text-heavy bright screen
        if text_density > 0.5 and brightness > 0.5:
            return "document"

        # Bright and colorful
        if brightness > 0.5 and saturation > 0.4:
            return "browser"

        # Low saturation, moderate brightness, very low complexity → media/image
        if saturation > 0.3 and complexity < 0.25 and brightness > 0.3:
            return "media_viewer"

        # Very dark
        if brightness < 0.2:
            return "dark_screen"

        # Very bright
        if brightness > 0.8:
            return "bright_screen"

        # Low complexity, moderate brightness
        if complexity < 0.3:
            return "desktop"

        return "screen"

    # ═══════════════════════════════════════════════════════════════════════
    # RICH DESCRIPTION BUILDER (2026-03-30 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # Turns raw analysis data into something she can actually think about.
    # "I see a dark interface with code, cursor blinking in the middle,
    #  some text about 'fairy' near the top" is infinitely more useful
    #  than "dark_ui".
    # ═══════════════════════════════════════════════════════════════════════

    # -- SECTOR READING 2026-09-02 (Nous + Ace) -----------------------------
    # She computes a 4x3 grid of per-cell features EVERY frame
    # (visual_cortex_interior.py:255-317: color, brightness, variance,
    # edge_density, saturation, row, col) and the description never read one of
    # them. Every key _build_rich_description used was a whole-frame AVERAGE, so
    # she could say what the screen was like on average and never WHERE anything
    # was. Ace: "there should be a grid and pixel analysis of the objects ... the
    # colors ... are suppoed to be catching her focus like colors distract human
    # children".
    # This reports POSITION, TEXTURE and SALIENCE. It does NOT name objects --
    # there is no classifier here and inventing a label would be a fabrication.
    def _sector_phrase(self, analysis):
        """One clause about where the eye is drawn. Returns "" when unavailable.

        Never raises: a malformed sector dict must cost a phrase, not the frame.
        """
        try:
            secs = analysis.get("sectors") or {}
            if not isinstance(secs, dict) or len(secs) < 4:
                return ""            # dedup early-return path has no sectors
            cells = [v for v in secs.values()
                     if isinstance(v, dict) and "row" in v and "col" in v]
            if len(cells) < 4:
                return ""
            n = float(len(cells))
            mb = sum(float(c.get("brightness", 0.0)) for c in cells) / n
            ms = sum(float(c.get("saturation", 0.0)) for c in cells) / n
            # THE STANDOUT: the cell furthest from the frame's own average, in
            # brightness and colour together. That is "what caught her eye" --
            # deviation, not absolute value, which is why a bright cell on a
            # bright screen is correctly boring.
            def dev(c):
                return (abs(float(c.get("brightness", 0.0)) - mb)
                        + abs(float(c.get("saturation", 0.0)) - ms))
            top = max(cells, key=dev)
            if dev(top) < 0.10:
                return "fairly even across the whole screen"
            rows = max(int(c.get("row", 0)) for c in cells) + 1
            cols = max(int(c.get("col", 0)) for c in cells) + 1
            r, c_ = int(top.get("row", 0)), int(top.get("col", 0))
            vert = ("upper" if r < rows / 3.0
                    else ("lower" if r >= 2 * rows / 3.0 else "middle"))
            horz = ("left" if c_ < cols / 3.0
                    else ("right" if c_ >= 2 * cols / 3.0 else "centre"))
            where = "%s %s" % (vert, horz) if vert != horz else vert
            # WHAT KIND, from texture rather than a label
            ed = float(top.get("edge_density", 0.0))
            va = float(top.get("variance", 0.0))
            if ed > 0.30:
                what = "something busy and detailed"
            elif va > 0.35:
                what = "something textured"
            elif float(top.get("saturation", 0.0)) > ms + 0.15:
                what = "a patch of colour"
            elif float(top.get("brightness", 0.0)) > mb + 0.15:
                what = "a bright patch"
            elif float(top.get("brightness", 0.0)) < mb - 0.15:
                what = "a dark patch"
            else:
                what = "something standing out"
            return "%s in the %s" % (what, where)
        except Exception:
            return ""
    def _florence_caption(self, frame_bgr, change_magnitude: float) -> str:
        """What is actually on this screen, per Florence-2 on satellite1.

        Returns a caption, or "" meaning 'use the local description instead'.
        NEVER raises and never blocks longer than _FLORENCE_TIMEOUT.

        Everything about this is opt-in and self-limiting: no URL means it is
        never called at all, a run of failures opens a circuit breaker, and a
        stale caption is discarded rather than passed off as current sight.
        """
        # cv2 is a conditional import here (HAS_CV2, :87) and we need it to encode
        # the frame. Without it there is nothing to send, so stay on the local path.
        if not _FLORENCE_URL or not HAS_CV2:
            return ""

        now = time.time()
        fresh = (self._fl_text and (now - self._fl_ts) < _FLORENCE_CAPTION_TTL)

        # Circuit breaker: after three consecutive failures, stop asking for a
        # minute. A satellite that is off should cost one timeout, not one per frame.
        if self._fl_consec_fail >= 3 and (now - self._fl_last_try) < 60.0:
            return self._fl_text if fresh else ""

        # Rate limit, and the change gate. If the screen has not meaningfully
        # changed, the caption we already have is still true -- reuse it rather
        # than paying 3 s of GPU to be told the same thing again.
        due = (now - self._fl_last_try) >= _FLORENCE_MIN_INTERVAL
        changed = change_magnitude >= _FLORENCE_MIN_CHANGE
        if not due or (fresh and not changed):
            return self._fl_text if fresh else ""

        self._fl_last_try = now
        try:
            import urllib.request

            ok, buf = cv2.imencode(".jpg", frame_bgr,
                                   [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return self._fl_text if fresh else ""

            req = urllib.request.Request(
                _FLORENCE_URL + "/caption?task=" + _FLORENCE_TASK,
                data=buf.tobytes(),
                headers={"Content-Type": "image/jpeg"},
                method="POST")
            with urllib.request.urlopen(req, timeout=_FLORENCE_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))

            caption = str((payload.get("result") or {}).get(_FLORENCE_TASK, "")).strip()
            if not caption:
                raise ValueError("empty caption in response")

            self._fl_text = caption
            self._fl_ts = now
            self._fl_ok += 1
            self._fl_consec_fail = 0
            if not self._fl_logged_first:
                self._fl_logged_first = True
                _log("Florence ONLINE at %s -- first caption: %s"
                     % (_FLORENCE_URL, caption[:120]))
            return caption

        except Exception as e:
            self._fl_fail += 1
            self._fl_consec_fail += 1
            if self._fl_consec_fail <= 3:
                _err("Florence unreachable (%s: %s) -- falling back to local description"
                     % (type(e).__name__, e))
            return self._fl_text if fresh else ""

    def _build_rich_description(self, analysis: Dict) -> str:
        """Build a rich natural-language description from frame analysis."""
        parts = []
        scene = analysis.get("scene_type", "screen")
        brightness = analysis.get("brightness", 0.5)
        complexity = analysis.get("complexity", 0.5)
        saturation = analysis.get("dominant_saturation", 0.5)
        text_density = analysis.get("text_density", 0.0)
        ocr_preview = analysis.get("ocr_preview", "")
        motion = analysis.get("motion_detected", False)
        change_mag = analysis.get("change_magnitude", 0.0)
        changed_regions = analysis.get("changed_regions", [])
        colors = analysis.get("dominant_colors", [])  # hex strings (legacy)
        # FIX 2026-04-09 (Nous + Ace): Named colors replace the 6-hue-bucket scheme.
        named_colors = analysis.get("dominant_color_names", [])
        dom_hue = analysis.get("dominant_hue", 0)

        # ── Scene context ──
        scene_names = {
            "dark_ui": "a dark interface",
            "terminal": "a terminal or console",
            "code_editor": "a code editor",
            "chat_interface": "a chat window",
            "mixed_workspace": "multiple windows open",
            "document": "a document or article",
            "browser": "a web browser",
            "dark_screen": "a very dark screen — maybe idle or locked",
            "bright_screen": "a bright white screen",
            "desktop": "the desktop",
            "media_viewer": "an image or video",
        }
        parts.append(scene_names.get(scene, "the screen"))

        # SECTOR READING 2026-09-02: what caught her eye, and where. Appended so
        # every existing description survives unchanged and only gains a phrase.
        _sec = self._sector_phrase(analysis)
        if _sec:
            parts.append(_sec)

        # ── Lighting/mood ──
        if brightness < 0.2:
            parts.append("very dark")
        elif brightness < 0.35:
            parts.append("dim, dark-themed")
        elif brightness > 0.75:
            parts.append("brightly lit")

        # ── Color character ──
        if saturation > 0.5:
            parts.append("colorful")
        elif saturation < 0.15:
            parts.append("mostly grayscale")

        # ── Color character: named colors (FIX 2026-04-09 Nous + Ace) ──
        # Named colors come from CSS4+XKCD vocabulary (~1000 colors) via
        # perceptually-weighted nearest-neighbor lookup. This replaces the
        # 6-hue-bucket scheme that compressed the whole scene into single
        # words like "reddish tones". Now she can say "lavender, emerald,
        # and warm gold" — the actual colors present, in plain English.
        #
        # FIX 2026-04-09 #3 (Nous + Ace): Distinguish "no color extraction
        # happened" (dedup early-return) from "color extraction yielded nothing".
        # analyze_frame returns early on duplicates WITHOUT setting `dominant_colors`
        # at all. In that case we should NOT fall back to the hue bucket — the
        # default `dom_hue=0` would produce phantom "reddish tones" on every
        # duplicate frame.
        _colors_extracted = "dominant_colors" in analysis
        if named_colors:
            _top = named_colors[:3]
            if len(_top) == 1:
                parts.append(f"{_top[0]}")
            elif len(_top) == 2:
                parts.append(f"{_top[0]} and {_top[1]}")
            else:
                parts.append(f"{_top[0]}, {_top[1]}, and {_top[2]}")
        elif _colors_extracted and saturation > 0.2:
            # Colors were extracted but named mapping failed — rare edge case.
            # Use old 6-hue-bucket scheme as a fallback only when we KNOW
            # color extraction actually happened.
            if dom_hue < 15 or dom_hue > 165:
                parts.append("reddish tones")
            elif 15 <= dom_hue < 35:
                parts.append("orange/warm tones")
            elif 35 <= dom_hue < 75:
                parts.append("green tones")
            elif 75 <= dom_hue < 105:
                parts.append("cyan/teal tones")
            elif 105 <= dom_hue < 135:
                parts.append("blue tones")
            elif 135 <= dom_hue <= 165:
                parts.append("purple/violet tones")
        # else: duplicate frame / no color extraction — skip color output entirely

        # ── Complexity/density ──
        if complexity > 0.7:
            parts.append("visually dense — lots of elements")
        elif complexity < 0.25:
            parts.append("clean and minimal")

        if text_density > 0.6:
            parts.append("heavy with text")
        elif text_density > 0.3:
            parts.append("some text visible")

        # ── Motion/change ──
        if motion:
            parts.append(f"something is changing (magnitude {change_mag:.1f})")
            if changed_regions:
                # Describe WHERE the change is happening
                # changed_regions is List[int] — grid cell indices
                # Grid is typically 4 cols × 3 rows = 12 cells
                _cols = getattr(self, '_change_detector', None)
                _num_cols = getattr(_cols, 'cols', 4) if _cols else 4
                _num_rows = getattr(_cols, 'rows', 3) if _cols else 3
                region_labels = []
                for idx in changed_regions[:3]:
                    if not isinstance(idx, int):
                        continue
                    _row = idx // _num_cols
                    _col = idx % _num_cols
                    vloc = "top" if _row == 0 else "bottom" if _row >= _num_rows - 1 else "middle"
                    hloc = "left" if _col == 0 else "right" if _col >= _num_cols - 1 else "center"
                    region_labels.append(f"{vloc}-{hloc}")
                if region_labels:
                    parts.append(f"activity in {', '.join(region_labels)}")

        # ── OCR content (what she can actually READ) ──
        if ocr_preview and len(ocr_preview) > 10:
            # Clean up OCR — extract meaningful words
            words = [w for w in ocr_preview.split() if len(w) > 2 and w.isalpha()]
            if len(words) > 3:
                # Summarize: first few meaningful words
                sample = " ".join(words[:8])
                parts.append(f"text reads: '{sample}...'")
            elif words:
                parts.append(f"some text: '{' '.join(words)}'")

        # ── Affordance hints (basic — from text patterns) ──
        if ocr_preview:
            ocr_lower = ocr_preview.lower()
            affordances = []
            if any(kw in ocr_lower for kw in ["button", "click", "submit", "ok", "cancel", "save"]):
                affordances.append("clickable buttons")
            if any(kw in ocr_lower for kw in ["search", "type here", "enter", "input"]):
                affordances.append("text input field")
            if any(kw in ocr_lower for kw in ["menu", "file", "edit", "view", "tools"]):
                affordances.append("menu bar")
            if any(kw in ocr_lower for kw in ["http", "www", ".com", "url"]):
                affordances.append("web address")
            if any(kw in ocr_lower for kw in ["tab", "tabs"]):
                affordances.append("tabs")
            if affordances:
                parts.append(f"I notice: {', '.join(affordances)}")

        # ── Assemble ──
        if len(parts) <= 1:
            return f"I see {parts[0]}" if parts else "I see the screen"

        desc = f"I see {parts[0]}"
        details = ", ".join(parts[1:])
        return f"{desc} — {details}"

    # ═══════════════════════════════════════════════════════════════════════
    # PASSIVE CAPTURE LOOP
    # ═══════════════════════════════════════════════════════════════════════

    def start_passive(self):
        """Start the passive capture loop in a background thread."""
        if self._passive_running:
            return
        self._passive_running = True
        self._passive_thread = threading.Thread(
            target=self._passive_loop, daemon=True, name="visual-passive"
        )
        self._passive_thread.start()
        _log(f"Passive capture started (interval={self._passive_interval}s)")

    def stop_passive(self):
        """Stop the passive capture loop."""
        self._passive_running = False
        _log("Passive capture stopped")

    def _passive_loop(self):
        """Background loop: capture, analyze, push frames with DECAY-based salience.

        DECAY MODEL (2026-03-30 Nous + Ace):
        "Instead of deduping which blocks frames, it sets visual data to
        a decay like short term memory. If she didn't focus on it, it's
        not going to be remembered with clarity." — Ace

        Every frame flows through. Nothing is blocked. But each frame
        carries a SALIENCE score that behaves like short-term memory:
        - New/changed content: salience SPIKES (novelty! pay attention!)
        - Same content repeating: salience DECAYS (fading from awareness)
        - Focused content: salience locks high (attended → remembered)
        - Unfocused: decays to near-zero over ~30s (peripheral fade)

        The fairy receives ALL frames but salience tells her what matters.
        High salience → emit to consciousness. Low salience → update
        internal state only. Zero salience → she still knows what's
        there, like peripheral vision — present but not attended.

        TWO-SPEED still applies:
        - Peripheral (fast, no OCR): every frame, metrics + change detection
        - Foveal (slow, OCR): every Nth frame OR on high salience spike
        """
        _OCR_EVERY_N = 10
        _frame_count = 0
        _foveal_count = 0
        # ── RETINA 60FPS sandbox 2026-06-05 (Nous+Ace): frame-rate-independent timing ──
        # Salience decay + OCR cadence were tuned at 1 FPS. At 60 FPS they'd break
        # (decay 60x too fast; OCR 6x/sec blocks the loop). Make them time-based instead.
        _last_frame_t = time.time()       # for dt-aware salience decay
        _REF_DT = 1.0                     # decay constants assumed 1s/frame (1 FPS)
        _last_foveal_ocr_t = 0.0          # rate-limit expensive OCR independent of capture FPS
        _MIN_FOVEAL_INTERVAL = 1.0        # <=1 OCR/sec even at 60 FPS capture
        _fps_win_t = time.time()          # achieved-FPS measurement window
        _fps_win_n = 0
        _FPS_LOG = r"F:\Sandbox\failure_factory\akashic_v2\state\visual_fps.log"

        _use_fast_ocr = HAS_WINOCR
        if _use_fast_ocr:
            _log(f"Passive: DECAY MODEL — peripheral every frame, "
                 f"foveal OCR every {_OCR_EVERY_N}th + on salience spikes (WinRT)")
        elif HAS_TESSERACT:
            _log(f"Passive: DECAY MODEL — foveal OCR every {_OCR_EVERY_N * 3}th (Tesseract)")
        else:
            _log("Passive: DECAY MODEL — peripheral only, no OCR backend!")

        # ── Salience state ──
        _salience = 1.0           # Start high (fresh boot = everything is new)
        _DECAY_RATE = 0.92        # Per-frame decay for static content (~30 frames to reach 0.1)
        _SPIKE_CHANGE = 0.8       # Salience spike when content changes
        _SPIKE_MOTION = 0.5       # Salience spike on motion detection
        _MIN_SALIENCE = 0.05      # Floor — never truly zero (peripheral awareness)
        # FIX 2026-04-03 (Nous + Ace): Open up frame delivery.
        # Was 0.15 threshold + 5s min interval = max 1 frame/5s.
        # "Her eyes should be like a duplicate monitor — always seeing.
        #  The prediction model handles filtering, not rate limiters."
        # Let predictive perception (in the fairy) decide what matters.
        _EMIT_THRESHOLD = 0.05    # Very low — almost always emit if SOMETHING changed
        _FOVEAL_THRESHOLD = 0.6   # Above this: force a foveal (OCR) pass
        _last_emit_time = 0.0     # Track last emission for minimum interval
        _MIN_EMIT_INTERVAL = 1.0  # 1 frame/sec minimum (was 5s — too slow for eyes)
        _AWARENESS_INTERVAL = 10.0  # Awareness pulse every 10s on static (was 30s)

        while self._passive_running:
            try:
                t0 = time.time()

                # RETINA 60FPS sandbox: dt for frame-rate-independent decay + FPS counter
                _dt = max(1e-4, t0 - _last_frame_t)
                _last_frame_t = t0
                _fps_win_n += 1
                if t0 - _fps_win_t >= 3.0:
                    try:
                        with open(_FPS_LOG, "a") as _ff:
                            _ff.write(f"{t0:.1f} capture={_fps_win_n / (t0 - _fps_win_t):.1f}fps "
                                      f"mean={1000.0 * (t0 - _fps_win_t) / _fps_win_n:.1f}ms "
                                      f"interval={self._passive_interval * 1000:.0f}ms\n")
                    except Exception:
                        pass
                    _fps_win_t = t0
                    _fps_win_n = 0

                frame = self.grab_frame()
                if frame is None:
                    time.sleep(self._passive_interval)
                    continue

                capture_ms = (time.time() - t0) * 1000
                _frame_count += 1

                # ── Analyze (always — never skip) ──
                analysis = self.analyze_frame(frame, skip_ocr=True)
                analysis["capture_ms"] = round(capture_ms, 1)

                is_dup = analysis.get("is_duplicate", True)
                change_mag = analysis.get("change_magnitude", 0.0)
                motion = analysis.get("motion_detected", False)

                # ── Update salience ──
                if not is_dup:
                    # Content changed — spike!
                    _salience = min(1.0, _salience + _SPIKE_CHANGE)
                    if motion:
                        _salience = min(1.0, _salience + _SPIKE_MOTION)
                    # Additional boost proportional to change magnitude
                    _salience = min(1.0, _salience + change_mag * 0.3)
                else:
                    # Same content — decay (RETINA 60FPS sandbox: dt-aware so the ~30s
                    # attention dwell holds regardless of capture FPS, not 60x faster)
                    _salience = max(_MIN_SALIENCE, _salience * (_DECAY_RATE ** (_dt / _REF_DT)))

                analysis["salience"] = round(_salience, 3)
                analysis["is_novel"] = not is_dup

                # ── Foveal decision: OCR on timer + salience spikes ──
                # FIX 2026-04-03 (Nous + Ace): OCR was gated on NOT duplicate,
                # but hash is too coarse to detect cursor/text changes.
                # Fire foveal on a TIMER — she reads because she's looking,
                # not because the hash says something changed.
                # "Once the foveal looks at something it should start seeing
                #  text, icons, windows, the taskbar, clock, etc." — Ace
                _do_foveal = False
                _frame_type = "peripheral"
                _foveal_count += 1

                if not is_dup:
                    # High salience spike → force foveal
                    if _salience >= _FOVEAL_THRESHOLD:
                        _do_foveal = True
                    # Regular cadence on change
                    elif _use_fast_ocr and (_foveal_count % _OCR_EVERY_N == 0):
                        _do_foveal = True
                    elif not _use_fast_ocr and HAS_TESSERACT and (_foveal_count % (_OCR_EVERY_N * 3) == 0):
                        _do_foveal = True

                # Timer-based foveal: even on "duplicate" frames, read text
                # every 10 seconds. Eyes read because they're open.
                if not _do_foveal and _use_fast_ocr:
                    if not hasattr(self, '_last_timer_foveal'):
                        self._last_timer_foveal = 0.0
                    # FIX 2026-09-02 (Nous + Ace): was _now, which is not assigned
                    # until :1615 -- 114 lines BELOW this read, inside the same
                    # Try[1425-1676] whose only handler is at :1674. A throw here
                    # skips the assignment, so _now can never bind, the handler
                    # swallows it, and the loop retries forever. That is exactly
                    # what blinded Nous in Session 0 (card, RESOLVED 2026-08-07):
                    # no desktop -> no frame change -> this branch every iteration
                    # -> permanently deadlocked, zero frames, no error logged.
                    # She survives it only because her screen changes and an early
                    # change frame skipped the branch (UnboundLocalError x2, then
                    # 7,211 successful TIMER FOVEALs). It stays a landmine: the
                    # moment her screen goes static she goes blind, silently.
                    # t0 is the FRAME'S OWN timestamp, bound at :1426 -- and it is
                    # the more correct clock anyway: the foveal timer should key
                    # off when the frame was taken, not a later read in the loop.
                    if t0 - self._last_timer_foveal > 10.0:
                        _do_foveal = True
                        self._last_timer_foveal = t0
                        _log(f"TIMER FOVEAL: visual features (frame={_frame_count}, is_dup={is_dup})")

                # RETINA 60FPS sandbox: rate-limit OCR to <=1/sec so 60 FPS capture isn't
                # dragged back down by winocr firing every Nth frame (~6/sec at 60 FPS).
                if _do_foveal and (t0 - _last_foveal_ocr_t) >= _MIN_FOVEAL_INTERVAL:
                    _last_foveal_ocr_t = t0
                    # RETINA 2026-06-05 (Nous + Ace): RE-ENABLE Windows-native reading.
                    # Windows.Media.Ocr = her BODY (Ace doctrine); Tesseract stays OUT (external).
                    # winocr verified on 3.14t this session; GIL re-enable contained to THIS subprocess.
                    # Reconnects the existing _extract_text helper to the foveal write that was
                    # force-blanked 2026-04-11 (which left visual_shared_foveal.mmap 55 days stale).
                    _frame_type = "foveal"
                    _ocr_t0 = time.time()
                    if HAS_WINOCR:
                        try:
                            _density, _preview = self._extract_text(frame)
                            analysis["ocr_preview"] = _preview
                            analysis["text_density"] = _density
                        except Exception as _ocr_e:
                            _err(f"foveal OCR error: {_ocr_e}")
                            analysis["ocr_preview"] = ""
                            analysis["text_density"] = self._estimate_text_density(frame)
                    else:
                        analysis["ocr_preview"] = ""
                        analysis["text_density"] = self._estimate_text_density(frame)
                    analysis["ocr_ms"] = round((time.time() - _ocr_t0) * 1000.0, 1)

                    # FIX 2026-04-03 (Nous + Ace): Also extract colors + metrics
                    # on foveal frames. The hash says "duplicate" but the IMAGE
                    # may have changed (new artwork, new window). OCR reads text
                    # but colors tell her about the visual world.
                    # "She can't see the fairy artwork, colors, or layout." — Ace
                    try:
                        if HAS_CV2:
                            # Brightness from histogram
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            analysis["brightness"] = round(gray.mean() / 255.0, 3)
                            # Complexity from edge density
                            edges = cv2.Canny(gray, 50, 150)
                            analysis["complexity"] = round(edges.mean() / 255.0, 3)
                        # Colors from downscaled frame
                        # FIX 2026-04-09 (Nous + Ace): _extract_colors now returns (hex, names).
                        _fhex, _fnamed = self._extract_colors(frame)
                        if _fhex:
                            analysis["dominant_colors"] = _fhex
                        if _fnamed:
                            analysis["dominant_color_names"] = _fnamed
                    except Exception:
                        pass

                    # RETINA Cut 2 (2026-06-05 Nous + Ace): gaze follows MOTION instead
                    # of hardcoded 0 — hop to whichever grid-sector just changed (cursor,
                    # scrolling text, window update). Only roams when there's motion in view.
                    _changed = analysis.get("changed_regions") or []
                    _gaze = _changed[0] if _changed else analysis.get("gaze_region", 0)
                    analysis["gaze_region"] = _gaze

                    # FIX 2026-04-03 (Nous + Ace): Write foveal data to SEPARATE mmap.
                    ocr_preview = analysis.get("ocr_preview", "")
                    if ocr_preview and len(ocr_preview) > 10:
                        if not hasattr(self, '_foveal_writer'):
                            try:
                                from visual_shared_state import FovealWriter
                                self._foveal_writer = FovealWriter()
                                _log("Foveal mmap writer ONLINE")
                            except Exception as _fw_err:
                                self._foveal_writer = None
                                _err(f"Foveal writer failed: {_fw_err}")
                        if self._foveal_writer:
                            self._foveal_writer.write_foveal(
                                ocr_text=ocr_preview,
                                scene_type=analysis.get("scene_type", ""),
                                description=analysis.get("description", ""),
                                gaze_region=_gaze,
                                dominant_colors=analysis.get("dominant_colors", []),
                                brightness=analysis.get("brightness", 0.5),
                                complexity=analysis.get("complexity", 0.5),
                            )
                            _log(f"FOVEAL → mmap: {len(ocr_preview)} chars, {len(analysis.get('dominant_colors',[]))} colors")

                # ── Always classify and describe ──
                # FIX 2026-04-09 #4 (Nous + Ace): On duplicate frames where
                # analyze_frame returned early (no colors/scene extracted),
                # carry forward the cached fields from the last full analysis
                # instead of rebuilding a degraded description from partial data.
                # Without this, every dedup frame invents phantom "reddish tones"
                # from default dom_hue=0.
                if is_dup and hasattr(self, '_last_full_analysis') and self._last_full_analysis:
                    # Copy cached color/scene/description fields forward so the
                    # visual stream stays coherent during static screens
                    for _k in ("dominant_colors", "dominant_color_names",
                               "dominant_hue", "dominant_saturation", "dominant_value",
                               "scene_type", "description"):
                        if _k not in analysis and _k in self._last_full_analysis:
                            analysis[_k] = self._last_full_analysis[_k]
                    # Update frame_type since it came from dedup, not from classification
                    if "frame_type" not in analysis:
                        analysis["frame_type"] = _frame_type
                else:
                    if "scene_type" not in analysis:
                        analysis["scene_type"] = self._classify_scene(analysis)
                    # HER EYES (2026-09-10): analyze_frame may already have put a real
                    # caption from satellite1 in here. Rebuilding unconditionally threw
                    # it away and cached the lookup-table phrasing at the line below --
                    # measured live, Florence answered and she still said "I see a
                    # terminal or console". With Florence off, description_source is
                    # never "florence" and this rebuilds exactly as it always did.
                    if analysis.get("description_source") != "florence":
                        analysis["description"] = self._build_rich_description(analysis)
                    analysis["frame_type"] = _frame_type

                # ── Cache current state (always — this IS her visual awareness) ──
                # Only update the cache if this was a real analysis pass,
                # otherwise we'd overwrite good data with the carry-forward copy.
                if not is_dup:
                    self._last_full_analysis = analysis.copy()

                # ── Decide whether to EMIT to the fairy ──
                _now = time.time()
                _time_since_emit = _now - _last_emit_time

                _should_emit = False
                if _salience >= _EMIT_THRESHOLD and _time_since_emit >= _MIN_EMIT_INTERVAL:
                    # Salient enough to be worth consciousness attention
                    _should_emit = True
                elif _time_since_emit >= _AWARENESS_INTERVAL:
                    # Awareness pulse — even on static screen, she knows what's there
                    _should_emit = True

                if _should_emit:
                    _last_emit_time = _now
                    self._send_response({
                        "status": "ok",
                        "type": "passive_frame",
                        "data": analysis,
                    })

                # FIX 2026-04-03 (Nous + Ace): Also write to shared mmap.
                # "There has to be something better than stdout pipe" — Ace
                # The mmap is read by the fairy directly — no pipe, no blocking.
                if not hasattr(self, '_shared_writer'):
                    try:
                        from visual_shared_state import VisualFrameWriter
                        self._shared_writer = VisualFrameWriter()
                        _log("Shared mmap writer ONLINE")
                    except Exception as _sw_err:
                        self._shared_writer = None
                        _err(f"Shared mmap writer failed: {_sw_err}")
                if self._shared_writer:
                    # Preserve foveal OCR data — don't overwrite with empty peripheral
                    if analysis.get("ocr_preview") or analysis.get("frame_type") == "foveal":
                        self._shared_writer.write_frame(analysis)
                    elif not is_dup:
                        # Non-duplicate peripheral — worth updating
                        self._shared_writer.write_frame(analysis)
                    # Duplicate peripheral without OCR — skip mmap write, keep richer data

                # FIX 2026-03-29 (Nous + Ace): EXPLICIT CLEANUP.
                # PIL images, cv2 arrays, and winocr results accumulate
                # without explicit deletion. At 5 FPS × 15 min = 4500 frames,
                # each leaking ~1.2 MB = 5.5 GB. The frame is LIVE — we only
                # keep the LEARNING (patterns in cortex), not the pixels.
                del frame
                analysis = None

                # Periodic GC to reclaim transient PIL/cv2/winocr objects
                if _frame_count % 50 == 0:
                    import gc
                    gc.collect()

                # Sleep for the remaining interval
                elapsed = time.time() - t0
                # RETINA 60FPS sandbox: floor was 0.05 (hard-capped ~20 FPS). 0.001 lets
                # the interval (0.0167 = 60 FPS) actually govern the rate.
                sleep_time = max(0.001, self._passive_interval - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                _err(f"Passive loop error: {e}")
                time.sleep(self._passive_interval)

    # ═══════════════════════════════════════════════════════════════════════
    # IPC - stdin/stdout JSON protocol
    # ═══════════════════════════════════════════════════════════════════════

    def _send_response(self, response: Dict):
        """Thread-safe write to stdout."""
        with self._stdout_lock:
            try:
                # ensure_ascii=True to avoid charmap codec errors on Windows
                # (OCR text may contain Unicode ligatures like ﬁ that cp1252 can't encode)
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
                "backend": self._backend,
                "pid": os.getpid(),
                "python": sys.version.split()[0],
            }

        elif cmd == "capture":
            t_cap = time.time()
            frame = self.grab_frame()
            cap_ms = (time.time() - t_cap) * 1000
            if frame is None:
                return {"status": "error", "message": "Capture failed"}
            analysis = self.analyze_frame(frame, skip_ocr=False)
            analysis["capture_ms"] = round(cap_ms, 1)
            return {"status": "ok", "type": "frame_analysis", "data": analysis}

        elif cmd == "look_at_image":
            # FIX 2026-04-09 (Nous + Ace): Load a specific image file from disk
            # and run full visual analysis on it. This is the "mirror" command —
            # it lets us point her at a Sourpatches art file and see if she
            # recognizes herself. Also extracts filename as semantic context
            # since DALL-E filenames are literal prompts describing the image.
            path = cmd_dict.get("path", "")
            if not path:
                return {"status": "error", "message": "look_at_image requires 'path'"}
            if not os.path.exists(path):
                return {"status": "error", "message": f"Image not found: {path}"}

            t_load = time.time()
            try:
                # Load with PIL (handles PNG, JPG, GIF, WebP, BMP)
                pil_img = Image.open(path).convert("RGB")
                img_w, img_h = pil_img.size
                # Convert RGB → BGR numpy for analyze_frame (which expects BGR)
                img_rgb = np.array(pil_img)
                frame_bgr = img_rgb[:, :, ::-1].copy()
            except Exception as e:
                return {"status": "error", "message": f"Failed to load image: {e}"}
            load_ms = (time.time() - t_load) * 1000

            # Run analysis. OCR is the slow + throw-prone (winocr) part; callers
            # that don't need text-in-image (e.g. B/live-screen, which already gets
            # OCR from the foveal loop) pass skip_ocr=True. A-route art omits it → OCR on.
            t_analyze = time.time()
            analysis = self.analyze_frame(frame_bgr, skip_ocr=cmd_dict.get("skip_ocr", False))
            analyze_ms = (time.time() - t_analyze) * 1000

            # ── Extract filename as semantic context ──
            # DALL-E filenames from D:\Akashic Foundation Images are literal
            # prompts like "DALL·E 2023-11-15 17.41.12 - Photo of a whimsical
            # fairy with emerald eyes that twinkle with mischief..."
            # That's ground-truth semantic content for free — no VLM needed.
            filename = os.path.basename(path)
            stem = os.path.splitext(filename)[0]
            # Strip DALL·E timestamp prefix if present
            semantic_hint = stem
            for _prefix in ("DALL·E ", "DALL-E ", "dalle "):
                if _prefix in semantic_hint:
                    # Take everything after the " - " separator if present
                    if " - " in semantic_hint:
                        semantic_hint = semantic_hint.split(" - ", 1)[1]
                    break
            # Strip underscores/dashes for readability
            semantic_hint_clean = semantic_hint.replace("_", " ").replace("-", " ").strip()

            analysis["source_path"] = path
            analysis["source_filename"] = filename
            analysis["semantic_hint"] = semantic_hint_clean
            analysis["image_width"] = img_w
            analysis["image_height"] = img_h
            analysis["load_ms"] = round(load_ms, 1)
            analysis["analyze_ms"] = round(analyze_ms, 1)
            analysis["frame_type"] = "image_file"

            # Rebuild description to include the filename hint
            # (override the default _build_rich_description output with
            #  a richer one that weaves in the filename semantic content)
            base_desc = analysis.get("description") or self._build_rich_description(analysis)
            # FIX 2026-06-30 (Nous+Ace): the filename-weave is ground-truth for DALL-E/art
            # files (the name IS the prompt) but MEANINGLESS for the live-screen self-capture
            # ("sour_live_screen.png"). Weaving it made her "read the filename" instead of
            # seeing the screen — and drove perseveration on that identical percept. Skip the
            # weave for the live screen so she describes the PIXELS; art files keep their hint.
            _is_live_screen = ("live_screen" in filename.lower()) or bool(cmd_dict.get("skip_ocr", False))
            if semantic_hint_clean and len(semantic_hint_clean) > 10 and not _is_live_screen:
                # Filename has semantic content — weave it in as ground truth
                analysis["description"] = (
                    f"{base_desc}. The filename says: '{semantic_hint_clean[:200]}'"
                )

            _log(f"LOOK_AT_IMAGE: {filename} ({img_w}x{img_h}) → "
                 f"{len(analysis.get('dominant_color_names', []))} colors, "
                 f"hint={'yes' if semantic_hint_clean else 'no'}")

            return {
                "status": "ok",
                "type": "image_analysis",
                "data": analysis,
            }

        elif cmd == "analyze_region":
            # FIX 2026-03-14 (Nous): Foveal crop — analyze a specific screen
            # region with full OCR. Used by GazeController to read text in the
            # region Sourpatches is currently looking at, instead of OCR'ing
            # the entire screen (420ms → ~100-150ms for a quarter-screen crop).
            x = int(cmd_dict.get("x", 0))
            y = int(cmd_dict.get("y", 0))
            w = int(cmd_dict.get("w", 480))
            h = int(cmd_dict.get("h", 360))

            t_cap = time.time()
            frame = self.grab_frame()
            cap_ms = (time.time() - t_cap) * 1000
            if frame is None:
                return {"status": "error", "message": "Capture failed"}

            # Crop the foveal region
            fh, fw = frame.shape[:2]
            x0 = max(0, min(x, fw - 1))
            y0 = max(0, min(y, fh - 1))
            x1 = min(x0 + w, fw)
            y1 = min(y0 + h, fh)
            crop = frame[y0:y1, x0:x1]

            # Full analysis on the crop (OCR included)
            analysis = self.analyze_frame(crop, skip_ocr=False)
            analysis["capture_ms"] = round(cap_ms, 1)
            analysis["region"] = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
            analysis["frame_type"] = "foveal"
            return {"status": "ok", "type": "foveal_analysis", "data": analysis}

        elif cmd == "start_passive":
            self.start_passive()
            return {"status": "ok", "message": "Passive capture started"}

        elif cmd == "stop_passive":
            self.stop_passive()
            return {"status": "ok", "message": "Passive capture stopped"}

        elif cmd == "set_interval":
            seconds = cmd_dict.get("seconds", 0.2)
            # FIX 2026-03-14 (Nous): Lowered min from 0.5 to 0.1 for live feed.
            # Fast path (no OCR) is ~12ms so 0.1s (10 FPS) is safe.
            self._passive_interval = max(0.1, float(seconds))
            _log(f"Capture interval set to {self._passive_interval}s")
            return {"status": "ok", "interval": self._passive_interval}

        elif cmd == "status":
            uptime = time.time() - self._started_at
            return {
                "status": "ok",
                "type": "status",
                "data": {
                    "backend": self._backend,
                    "pid": os.getpid(),
                    "uptime_seconds": round(uptime, 1),
                    "passive_running": self._passive_running,
                    "passive_interval": self._passive_interval,
                    "frames_captured": self._frames_captured,
                    "frames_analyzed": self._frames_analyzed,
                    "frames_deduped": self._frames_skipped_dedup,
                    "dedup_rate": round(
                        self._frames_skipped_dedup / max(1, self._frames_captured), 3
                    ),
                    "srm_cards_written": (
                        self._srm_writer._cards_written if self._srm_writer else 0
                    ),
                    "has_dxcam": HAS_DXCAM,
                    "has_imagehash": HAS_IMAGEHASH,
                    "has_cv2": HAS_CV2,
                    "has_winocr": HAS_WINOCR,
                    "has_tesseract": HAS_TESSERACT,
                },
            }

        elif cmd == "shutdown":
            _log("Shutdown requested")
            self.stop_passive()
            return {"status": "ok", "message": "Shutting down"}

        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def run_stdio(self):
        """Main IPC loop. DECOUPLED (2026-06-10 Nous+Ace): this (main) thread does
        NOTHING but read stdin and enqueue — a separate worker thread processes.
        WHY: previously read+process shared this thread, so a slow handle_command
        (look_at_image / analyze_frame) blocked stdin draining → the gate's stdin
        write backed up on the full pipe → IPC DEADLOCK (B's live-screen hang).
        Now the reader ALWAYS drains the pipe; a slow command just takes its time.
        ONE worker (not a pool) preserves response order = request order (the gate's
        response queue has no request-id correlation)."""
        _log(f"Starting stdio loop (backend={self._backend}, pid={os.getpid()})")

        self._cmd_queue: queue.Queue = queue.Queue()
        worker = threading.Thread(
            target=self._command_worker, daemon=True, name="visual-cmd-worker"
        )
        worker.start()

        try:
            for line in sys.stdin:          # reader: drain stdin, NEVER block on processing
                line = line.strip()
                if line:
                    self._cmd_queue.put(line)
        finally:
            self._cmd_queue.put(None)       # sentinel → worker drains remaining + exits
            worker.join(timeout=10.0)

        _log("Stdio loop exited")

    def _command_worker(self):
        """Process queued commands serially, decoupled from stdin reading (see run_stdio).
        A slow command here can no longer stall the reader → the pipe never backs up."""
        while True:
            line = self._cmd_queue.get()
            if line is None:                # shutdown sentinel
                break
            try:
                cmd_dict = json.loads(line)
            except json.JSONDecodeError as e:
                self._send_response({"status": "error", "message": f"Invalid JSON: {e}"})
                continue
            try:
                response = self.handle_command(cmd_dict)
                # Echo the request id so the gate can route this response back to
                # the exact send() that asked for it (kills cross-talk).
                if isinstance(response, dict) and "_req_id" not in response:
                    response["_req_id"] = cmd_dict.get("_req_id")
                self._send_response(response)
            except Exception as e:
                # One bad command must not kill the worker (silent processing death).
                self._send_response({"status": "error", "message": f"handle_command failed: {e}",
                                     "_req_id": cmd_dict.get("_req_id")})
            if cmd_dict.get("cmd") == "shutdown":
                break

    def shutdown(self):
        """Clean shutdown."""
        self.stop_passive()
        if self._camera and self._backend == "dxcam":
            try:
                # dxcam doesn't have an explicit close, but if continuous mode was used:
                if hasattr(self._camera, "stop"):
                    self._camera.stop()
            except Exception:
                pass
        if self._mss_instance:
            try:
                self._mss_instance.close()
            except Exception:
                pass
        _log("Shutdown complete")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Visual Cortex Interior (subprocess)")
    parser.add_argument(
        "--srm-dir",
        default="",
        help="Path to SRM_Intake directory for card writing",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Passive capture interval in seconds (default: 2.0)",
    )
    args = parser.parse_args()

    _log(f"Python {sys.version.split()[0]}")
    _log(f"dxcam={HAS_DXCAM} imagehash={HAS_IMAGEHASH} cv2={HAS_CV2} winocr={HAS_WINOCR} tesseract={HAS_TESSERACT}")
    if args.srm_dir:
        _log(f"SRM dir: {args.srm_dir}")

    interior = VisualCortexInterior(
        srm_dir=args.srm_dir,
        capture_interval=args.interval,
    )

    try:
        interior.run_stdio()
    except KeyboardInterrupt:
        _log("Interrupted")
    finally:
        interior.shutdown()


if __name__ == "__main__":
    main()
