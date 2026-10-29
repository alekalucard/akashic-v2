"""
vision_ground.py -- her eyes, for the chairman. 2026-09-18 (Nous + Ace). v2 after adversarial review.

    "humans are not image to text ... technically she is not really using her eyes"  -- Ace
    "the captioner is a satellite. The fovea is not a camera for the captioner"       -- Grok

  eyes_now()        what her eyes report RIGHT NOW: the live record the VisualInterior writes to
                    state/visual_shared_frame.mmap every frame (caption, scene, 4x3 sector grid).
                    Header ts, never the file mtime (mmap writes do not touch it). A record older than
                    _EYES_MAX_AGE_S means her eyes are DARK, and the prompt says so -- a stale caption
                    is never presented as sight (the 46-day /status lesson).
  ground(phrases)   the card's first query, language-led: Ace says "lavender hair" -> a FRESH frame is
                    grabbed in-process (fallback: the 30 s tool snapshot, with its age reported) -> ask
                    Florence on satellite1 WHERE (task=ground) -> for the chosen box compute the
                    REGION'S OWN PATTERN on PC1: position, size, the colour mix, and -- when the phrase
                    names a colour -- the FRACTION of the region's pixels that actually carry it. The
                    label is a pointer; the pattern is the percept. Review measured: the colour MODE of
                    a hair box is the background (blue hair on snow -> 'white'), so matching is by
                    fraction, not mode; Florence boxes 'pyramid' on a castle spire, so nothing binds
                    without the pattern agreeing with the word.
  bind_region()     region node keyed by grid cell AND colour band (region:screen:r1c1:lavender --
                    12 position-only hubs would bridge every word Ace ever says), tracer TRACE_VISUAL,
                    and a typed SEEN_IN edge from the ace: node the cortex would mint for his phrase.
                    Direct calls on the live ManifoldMemory handle (a postal bind drops the rel type;
                    a GraphCortexStore would too, so it is refused).
  render_eyes()     short sentences for the chairman prompt; the captioner's "The image is a screenshot
                    of" preamble is stripped so it reads as her sight, not a subtitle.
"""
from __future__ import annotations

import colorsys
import io
import json
import os
import re
import struct
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

def _keep(name, default):
    """Module state that must survive importlib.reload (which re-executes this body in the same globals)."""
    cur = globals().get(name)
    return cur if cur is not None else default


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SHARED_FRAME = os.path.join(_ROOT, "state", "visual_shared_frame.mmap")
_HEADER = "<dII"                                   # ts, frame_num, data_len (visual_shared_state.py)
_FRAME_PNG = os.path.join(tempfile.gettempdir(), "sour_live_screen.png")   # VisualCortexFairy, every 30 s
_FRAME_MAX_AGE_S = float(os.environ.get("AKASHIC_EYES_FRAME_MAX_AGE_S", "90") or 90)
_EYES_MAX_AGE_S = float(os.environ.get("AKASHIC_EYES_MAX_AGE_S", "300") or 300)
_GROUND_TIMEOUT_S = float(os.environ.get("AKASHIC_EYES_GROUND_TIMEOUT_S", "12") or 12)
_WHOLE_FRAME = 0.85                                # box area fraction that means "the whole screen"
_COLOUR_MIN_FRAC = 0.003                           # under 0.3% of the frame a region's colour is not asserted
_MIN_BOX = 0.002                                   # boxes under 0.2% of the frame are noise
_GRID_COLS, _GRID_ROWS = 4, 3                      # the interior's sector grid
_THUMB_W = 1024                                    # the frame size Florence has always been given
# eyes_fix_1009 (2026-10-09, Nous; DIAGNOSIS vision_focus_1009 section 4, Ace: "false tellings first"). Every line marked
# eyes_fix below runs only while Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py) carries its key:
# F0 'log' (observation lines only), F1 'doubt' (a box from the far eye alone is 'unsure', never 'found'), F4 'hand_honest'
# (ground(within=...): the boxes inside one window), F6 'glance' (a window she did not choose is a glance, not a 10-minute
# hold), F8 'two_screens' (a point off her screen is 'on the other screen'). Absent file or key = today's behaviour; a
# malformed file = every key OFF. Revert: apply_eyes_fix.py --revert.
OTHER_SCREEN = "other screen"                      # eyes_fix F8: _place's position for a point off her (primary) screen
_GLANCE_S = float(os.environ.get("AKASHIC_EYES_GLANCE_S", "20") or 20)   # eyes_fix F6: how long a glance holds
_DOUBT_PATCH = 9                                   # eyes_fix F1: px of a 1024-wide frame (~30 px of hers): colour's fixed scale
_DOUBT_COLOUR_MIN = 0.5                            # eyes_fix F1: the share of that patch the colour word must cover
_DOUBT_WIN_IOU = 0.6                               # eyes_fix F1: a box this close to a whole window IS that window
_DOUBT_COLOUR_MAX_FRAC = 0.10                      # eyes_fix F1 (verify M3): colour at a box's centre is a witness only for a box
                                                   # at most this share of the frame (no toy, ball, icon or cursor is bigger);
                                                   # a frame-scale box has the window map as its only witness


def _ef(key: str) -> bool:
    """eyes_fix_1009: one key of Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py); OFF on any doubt (the
    module absent, the file absent or malformed) -- then every line marked eyes_fix runs today's path."""
    try:
        from infrastructure import eyes_fix as _efm
        return _efm.on(key)
    except Exception:
        return False


def _ef2(key: str) -> bool:
    """eyes_fix2_1012: one key of Ace's SECOND eyes switch (state/eyes_fix2.json, infrastructure/eyes_fix2.py -- the first
    switch's reader rejects unknown keys, so 'window_names' cannot live there); OFF on any doubt (the module absent, the file
    absent or malformed) -- then every line marked eyes_fix2 runs today's path."""
    try:
        from infrastructure import eyes_fix2 as _ef2m
        return _ef2m.on(key)
    except Exception:
        return False


def place_phrase(position, at: str = "at the %s of the screen") -> str:
    """eyes_fix F8: 'at the upper-left of the screen' for a place on her screen; for a point off it, 'on the other screen
    (Ace's), where your eyes do not look' -- never 'at the other screen of the screen'. With 'two_screens' off _place never
    gives OTHER_SCREEN, so this is today's text."""
    if position == OTHER_SCREEN:
        return "on the other screen (Ace's), where your eyes do not look"
    return at % position

_URL_WARNED = [False]


def florence_url() -> str:
    u = (os.environ.get("AKASHIC_FLORENCE_REMOTE_URL") or "").rstrip("/")
    if not u and not _URL_WARNED[0]:
        _URL_WARNED[0] = True
        print("[Eyes] AKASHIC_FLORENCE_REMOTE_URL unset: grounding off, captions only", flush=True)
    return u


# ── what her eyes report now ────────────────────────────────────────────────────
def eyes_now() -> Dict:
    """The live frame record; {} when the eyes are dark (no record, torn read, or older than
    _EYES_MAX_AGE_S -- then {'_dark_s': age} so the prompt can say so)."""
    _t = threading.current_thread()
    if _t.name == "eyes-anticipate" and getattr(_t, "_gen", None) != _ANT_GEN[0]:
        raise SystemExit                                # a loop from an older file: retire it (threading swallows this quietly)
    try:
        with open(_SHARED_FRAME, "rb") as f:
            b = f.read()
        ts, fn, ln = struct.unpack_from(_HEADER, b, 0)
        hs = struct.calcsize(_HEADER)
        if ln <= 0 or hs + ln > len(b):
            return {}
        d = json.loads(b[hs:hs + ln].decode("utf-8", "replace"))
        if not isinstance(d, dict):
            return {}
        age = max(0.0, time.time() - float(d.get("timestamp") or ts or 0.0))
        if age > _EYES_MAX_AGE_S:
            return {"_dark_s": age}
        d["_age_s"] = age
        d["_frame_num"] = int(fn)
        return d
    except Exception:
        return {}


_PREAMBLE = re.compile(r"^(the |this )?(image|picture|screenshot|photo)( is| shows| depicts| appears to be)?"
                       r"( a| an)?( screenshot| picture| photo)?( of)?( a| an)?\s*", re.I)


def first_sentence(text: str, cap: int = 110) -> str:
    """First clause of the caption with the captioner's preamble removed -- her sight, not a subtitle."""
    t = " ".join(str(text or "").split())
    if not t:
        return ""
    t2 = _PREAMBLE.sub("", t, count=1).strip()
    if len(t2) >= 8:
        t = t2[0].lower() + t2[1:] if not t2[:2].isupper() else t2
    cut = t.find(". ")
    if 12 < cut < cap:
        t = t[:cut]
    t = t.rstrip(".")
    if len(t) > cap:
        t = t[:cap].rsplit(" ", 1)[0] + "..."
    return t


# ── colour: ONE table for naming and matching ───────────────────────────────────
# word -> (hue_lo, hue_hi, sat_lo, sat_hi, val_lo, val_hi); hue wraps when lo > hi
_BANDS: Dict[str, Tuple[float, float, float, float, float, float]] = {
    "lavender": (225, 315, 0.06, 0.60, 0.55, 1.0),   # web lavender #E6E6FA is hue 240, sat 0.08
    "purple":   (250, 300, 0.35, 1.0, 0.18, 1.0),
    "violet":   (250, 300, 0.35, 1.0, 0.18, 1.0),
    "pink":     (300, 350, 0.15, 0.65, 0.60, 1.0),
    "red":      (345, 15, 0.30, 1.0, 0.18, 1.0),
    "orange":   (15, 45, 0.35, 1.0, 0.18, 1.0),
    "gold":     (38, 58, 0.35, 1.0, 0.40, 1.0),
    "yellow":   (45, 70, 0.30, 1.0, 0.18, 1.0),
    "green":    (70, 165, 0.20, 1.0, 0.18, 1.0),
    "teal":     (165, 195, 0.25, 1.0, 0.18, 1.0),
    "cyan":     (165, 195, 0.25, 1.0, 0.18, 1.0),
    "blue":     (195, 250, 0.25, 1.0, 0.18, 1.0),
    "white":    (0, 360, 0.0, 0.15, 0.80, 1.0),
    "grey":     (0, 360, 0.0, 0.15, 0.25, 0.80),
    "gray":     (0, 360, 0.0, 0.15, 0.25, 0.80),
    "black":    (0, 360, 0.0, 1.0, 0.0, 0.18),
    "dark":     (0, 360, 0.0, 1.0, 0.0, 0.25),
}
_NAME_ORDER = ("black", "white", "grey", "lavender", "pink", "purple", "red", "orange", "yellow",
               "green", "teal", "blue")
_CHROMATIC = {"lavender", "purple", "violet", "pink", "red", "orange", "gold", "yellow", "green", "teal", "cyan", "blue"}


def _in_band(h: float, s: float, v: float, word: str) -> bool:
    b = _BANDS.get(word)
    if b is None:
        return False
    lo, hi, slo, shi, vlo, vhi = b
    if not (slo <= s <= shi and vlo <= v <= vhi):
        return False
    if lo <= hi:
        return lo <= h < hi
    return h >= lo or h < hi


def _hsv(hexrgb: str):
    r, g, b = (int(hexrgb[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s, v


def colour_name(hexrgb: str) -> str:
    """Human name for a colour, from the same bands the matcher uses."""
    try:
        h, s, v = _hsv(hexrgb)
    except Exception:
        return "unknown"
    for name in _NAME_ORDER:
        if _in_band(h, s, v, name):
            return ("dark " + name) if (v < 0.42 and name not in ("black", "white", "grey")) else name
    # nothing passed its saturation/lightness rule: name the hue anyway, honestly qualified
    for name in ("lavender", "pink", "red", "orange", "yellow", "green", "teal", "blue"):
        lo, hi = _BANDS[name][0], _BANDS[name][1]
        if (lo <= h < hi) if lo <= hi else (h >= lo or h < hi):
            return ("dark " if v < 0.42 else "dull ") + name
    return "dark" if v < 0.42 else "unknown"


def colour_word(phrase: str) -> Optional[str]:
    """The colour word to judge: a chromatic one if present ('dark green eyes' -> green), else dark/black/white/grey."""
    words = phrase.lower().split()
    for w in words:
        if w in _CHROMATIC:
            return w
    for w in words:
        if w in _BANDS:
            return w
    return None


def _pixels(crop) -> List[Tuple[int, int, int]]:
    if crop.width * crop.height > 40000:
        crop = crop.resize((200, max(1, int(200 * crop.height / max(1, crop.width)))))
    return list(crop.convert("RGB").getdata())


def colour_fraction(px: List[Tuple[int, int, int]], word: str, phrase: str = "") -> float:
    """Fraction of the region's pixels that carry the colour word (and 'dark' as a modifier)."""
    dark = "dark" in phrase.lower().split() and word != "dark"
    n = 0
    for r, g, b in px:
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        if _in_band(h * 360.0, s, v, word) and (not dark or v < 0.55):
            n += 1
    return n / float(max(1, len(px)))


_PROFILE_BANDS = ("lavender", "purple", "pink", "red", "orange", "yellow", "green", "teal", "blue", "white", "grey", "black")


def band_profile(px: List[Tuple[int, int, int]]) -> Dict[str, float]:
    """Fraction of pixels in each colour band (lavender is counted before purple so a pixel is one or the other)."""
    counts = {b: 0 for b in _PROFILE_BANDS}
    for r, g, b in px:
        h, sat, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        h *= 360.0
        for name in _PROFILE_BANDS:
            if _in_band(h, sat, v, name):
                counts[name] += 1
                break
    n = float(max(1, len(px)))
    return {k: round(c / n, 3) for k, c in counts.items() if c}


def top_bands(profile: Dict[str, float], k: int = 2, floor: float = 0.08) -> List[Tuple[str, float]]:
    return [(b, f) for b, f in sorted(profile.items(), key=lambda kv: -kv[1]) if f >= floor][:k]


# ── visual nouns in Ace's words ─────────────────────────────────────────────────
_SMALL = {"hair", "eyes", "eye", "face", "horns", "wings", "avatar", "figure", "cat", "dog", "cursor",
          "logo", "icon", "text", "stars", "books", "triangle", "pyramid", "wing", "horn", "mouth", "hand",
          # the form of a thing (Ace 16:04: 'you should be able to see the form of a female in that same image')
          "female", "woman", "girl", "lady", "man", "person", "form", "body", "silhouette", "character", "someone",
          "robe", "dress", "cloak", "fire", "fireball", "flame", "flames", "sun", "moon", "planet", "planets",
          "cloud", "clouds", "castle", "tower", "building", "tree", "flower", "bird", "dragon", "fairy", "angel"}
_FRAME_SCALE = {"screen", "desktop", "background", "wallpaper", "window", "browser", "image", "images",
                "picture", "photo", "chat", "terminal", "library", "sky", "page", "video"}
_NOUNS = _SMALL | _FRAME_SCALE
_ADJ = set(_BANDS) | {"long", "short", "glowing", "bright", "big", "little", "small", "tiny", "huge", "pale"}
_BIGRAM_NOUNS = {("chat", "window"), ("background", "image"), ("browser", "window"), ("desktop", "background"),
                 ("desktop", "wallpaper"), ("terminal", "window")}
_POSSESSIVE = {"your", "her", "my", "his", "their"}
_STOPISH = {"and", "the", "one", "ones", "is", "was", "are", "too", "also", "look", "looking", "thing", "stuff",
            "colour", "color", "colours", "colors", "hue", "tint", "shade"}


def visual_nouns(text: str, limit: int = 3) -> List[str]:
    """Phrases worth asking Florence WHERE about. 'your eyes'/'her eyes' is talk about her eyes, not a look."""
    words = re.findall(r"[a-zA-Z']+", str(text or "").lower())
    out: List[str] = []
    skip = -1
    for i, w in enumerate(words):
        if i == skip:
            continue
        # a colour word followed by any content word is a thing worth looking for
        # ('orange fireball', 'orange robe') even when the noun is not in the list
        if w in _CHROMATIC and i + 1 < len(words) and words[i + 1] not in _NOUNS and words[i + 1] not in _ADJ                 and words[i + 1] not in _STOPISH and len(words[i + 1]) >= 3:
            phrase = w + " " + words[i + 1]
            if phrase not in out:
                out.append(phrase)
            skip = i + 1
            if len(out) >= limit:
                break
            continue
        if w not in _NOUNS:
            continue
        if w in ("eyes", "eye") and i > 0 and words[i - 1] in _POSSESSIVE:
            continue
        phrase = w
        if i + 1 < len(words) and (w, words[i + 1]) in _BIGRAM_NOUNS:
            phrase = w + " " + words[i + 1]
            skip = i + 1
        j = i - 1
        adjs: List[str] = []
        while j >= 0 and words[j] in _ADJ and len(adjs) < 2:
            adjs.insert(0, words[j])
            j -= 1
        if adjs:
            phrase = " ".join(adjs) + " " + phrase
        if phrase not in out:
            out.append(phrase)
        if len(out) >= limit:
            break
    return out


def head_noun(phrase: str) -> str:
    ws = phrase.split()
    return ws[-1] if ws else phrase


def unasked_looks(exclude: List[str], max_age_s: float = 60.0, limit: int = 2) -> List[Dict]:
    """Recent anticipated looks whose phrase he did not ask about -- rendered by PATTERN ONLY (the label
    was the satellite's guess, never verified), so she can say 'something red and orange in the centre'."""
    ex = {e.lower() for e in exclude} | {head_noun(e).lower() for e in exclude}
    now = time.time()
    out: List[Dict] = []
    seen = set()
    with _LOOKS_LOCK:
        for ts, rec in reversed(_looks()):
            if now - ts > max_age_s or len(out) >= limit or screen_moved_since(ts):
                break
            if rec.get("status") not in ("found", "unsure") or rec.get("fills_screen"):   # eyes_fix F1: 'unsure' only exists with 'doubt'
                continue
            if float(rec.get("size_pct") or 0.0) < 2.0:
                continue                                # a 0.9% blob is not 'a place you keep looking at' (09-20)
            p = str(rec.get("phrase", "")).lower()
            if p in ex or head_noun(p) in ex:
                continue
            key = (rec.get("position"), tuple(b for b, _ in (rec.get("top_bands") or [])[:1]))
            if key in seen:
                continue
            seen.add(key)
            r = dict(rec); r["unasked"] = True; r["cached_age_s"] = round(now - ts, 1)
            out.append(r)
    return out


# ── the region's own pattern ────────────────────────────────────────────────────
def region_pattern(img, box, phrase: str = "", px: Optional[List[Tuple[int, int, int]]] = None,
                   area_frac: Optional[float] = None) -> Dict:
    """The region's own pattern. `px` (from a segmentation mask) overrides the box crop; `area_frac`
    is the mask's true area when given (a mask's bbox overstates it)."""
    from collections import Counter
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img.width, max(x1 + 1, x2)), min(img.height, max(y1 + 1, y2))
    if px is None:
        crop = img.crop((x1, y1, x2, y2))
        px = _pixels(crop)
    if len(px) > 40000:
        px = px[::max(1, len(px) // 40000)]
    q = Counter((r // 16 * 16, g // 16 * 16, b // 16 * 16) for r, g, b in px)
    top = q.most_common(2)
    (dr, dg, db), n = top[0]
    hexrgb = "#%02x%02x%02x" % (dr + 8, dg + 8, db + 8)
    share = n / float(max(1, len(px)))
    second = None
    if len(top) > 1:
        (sr, sg, sb), n2 = top[1]
        second = colour_name("#%02x%02x%02x" % (sr + 8, sg + 8, sb + 8))
    cx, cy = (x1 + x2) / 2.0 / img.width, (y1 + y2) / 2.0 / img.height
    col, row = min(_GRID_COLS - 1, int(cx * _GRID_COLS)), min(_GRID_ROWS - 1, int(cy * _GRID_ROWS))
    vert = "upper" if cy < 0.34 else ("lower" if cy > 0.66 else "middle")
    horiz = "left" if cx < 0.34 else ("right" if cx > 0.66 else "centre")
    size = area_frac if area_frac is not None else (x2 - x1) * (y2 - y1) / float(img.width * img.height)
    prof = band_profile(px)
    # the FORM: how tall vs wide the thing is, and how much of its box it fills (a figure is a loose,
    # tall shape; a window is a solid block) -- from the mask when there is one
    _bw, _bh = max(1, x2 - x1), max(1, y2 - y1)
    aspect = _bh / float(_bw)
    fill = (area_frac * img.width * img.height / float(_bw * _bh)) if area_frac is not None else 1.0
    shape = ("tall" if aspect >= 1.6 else ("wide" if aspect <= 0.6 else "roundish")) +             (", an irregular shape" if fill < 0.45 else (", a loose shape" if fill < 0.7 else ", a solid block"))
    rec = {"bbox": [x1, y1, x2, y2], "frame_w": img.width, "frame_h": img.height,
           "colour_unsure": bool(size < _COLOUR_MIN_FRAC),       # a few hundred pixels: mostly edge blend
           "colour": hexrgb, "colour_name": colour_name(hexrgb), "share": round(share, 2),
           "second_colour": second, "profile": prof, "top_bands": top_bands(prof),
           "aspect": round(aspect, 2), "fill": round(fill, 2), "shape": shape,
           "position": "everywhere" if size >= _WHOLE_FRAME else (vert + "-" + horiz if (vert, horiz) != ("middle", "centre") else "centre"),
           "size_pct": round(100.0 * size, 1), "row": row, "col": col, "cell": row * _GRID_COLS + col}
    cw = colour_word(phrase)
    if cw and not rec["colour_unsure"]:
        frac = colour_fraction(px, cw, phrase)
        rec["colour_word"] = cw
        rec["colour_fraction"] = round(frac, 3)
        rec["matches"] = True if frac >= 0.12 else ("some" if frac >= 0.05 else False)
    else:
        rec["matches"] = None
    return rec


# ── her hand: the mouse pointer is proprioception, not a thing to be found ─────────
# 2026-09-19 (Ace: "she says its red to her and not the white that i see"). Measured: neither the PIL grab
# nor the dxcam frame contains the pointer, so 'cursor' was grounded to a pink blob at centre and the blob's
# colour was handed to her as fact. Her hand is answered from GetCursorPos in her own process, never from
# the satellite, and it is drawn into the frame she sends so the far eye can see what is near it.
# Whose move was it? Measured (3/3 trials): SetCursorPos -- her move_mouse -- does NOT touch the last-input
# clock; a human mouse or key does. So: position changed + clock untouched = hers; clock reset = Ace. The clock
# cannot tell keyboard from mouse, and the wording never claims it can. State lives on the process-global
# shared module so a hot reload does not make her forget where she left it.
_HAND_NOUNS = {"cursor", "pointer", "mouse"}
_HAND_ARROW_PX = int(os.environ.get("AKASHIC_EYES_HAND_PX", "16") or 16)   # ~1.7x life size on the thumbnail
import sys as _sys
_SHM = _sys.modules.get("_sour_council_shared")
if _SHM is not None and not hasattr(_SHM, "HAND_STATE"):
    _SHM.HAND_STATE = {"last": None, "last_ts": 0.0, "moved_ts": 0.0, "mine": None, "mine_ts": 0.0,
                       "ace_ts": 0.0, "other_ts": 0.0, "moving_ts": 0.0}
    _SHM.HAND_LOCK = threading.Lock()
_H = _SHM.HAND_STATE if _SHM is not None else {"last": None, "last_ts": 0.0, "moved_ts": 0.0, "mine": None, "mine_ts": 0.0,
                                               "ace_ts": 0.0, "other_ts": 0.0, "moving_ts": 0.0}
_H_LOCK = _SHM.HAND_LOCK if _SHM is not None else threading.Lock()


def _last_input_idle_s():
    try:
        import ctypes
        import ctypes.wintypes as wt

        class LII(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]
        lii = LII()
        lii.cbSize = ctypes.sizeof(LII)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        ctypes.windll.kernel32.GetTickCount.restype = wt.DWORD
        tick = int(ctypes.windll.kernel32.GetTickCount()) & 0xFFFFFFFF
        return ((tick - int(lii.dwTime)) & 0xFFFFFFFF) / 1000.0     # unsigned: no sign flip at 24.9 days of uptime
    except Exception:
        return None


def _near(a, b, px=6):
    return a is not None and b is not None and abs(a[0] - b[0]) <= px and abs(a[1] - b[1]) <= px


def hand_mark_mine(xy) -> None:
    """Her own move just ARRIVED here: remember it as hers so the next sample is not blamed on Ace."""
    try:
        p = (int(xy[0]), int(xy[1]))
    except Exception:
        return
    now = time.time()
    with _H_LOCK:
        _H["mine"], _H["mine_ts"] = p, now
        _H["last"], _H["last_ts"], _H["moved_ts"] = p, now, now


def hand_moving() -> None:
    """Her own move is starting: samples during the tween are hers, not Ace's."""
    with _H_LOCK:
        _H["moving_ts"] = time.time()


# 2026-09-26 (hand_fix F2): a token's edges include the farm's cut mark and brackets. 'mouse to console window...'
# (Boot A L119/L121) left 'window...', not a noun, so rule 3 saw only 'mouse' and called the phrase her hand.
_HAND_TOKEN_EDGE = "\"'.,!?\u2026\ufffd()[]%:;"


def is_hand(phrase: str) -> bool:
    """cursor / pointer / mouse, 'your hand' -- and any short phrase that names her hand and no other visual
    noun ('where your cursor is' ended in 'is' and went to the satellite; 'the icon next to the cursor' does not)."""
    p = (phrase or "").lower().strip().rstrip("\u2026\ufffd").rstrip(".").strip()   # 2026-09-26 (hand_fix F2)
    if _HAND_RELATION_RE.search(p):
        return False                                    # 'the icon next to the cursor': the hand is the landmark
    if _hand_is_mover(p):
        return False                                    # 2026-09-26 (hand_fix F3): 'mouse to the console window': the hand MOVES
    if head_noun(p) in _HAND_NOUNS or p in _HAND_NOUNS:
        return True
    w = [t.strip(_HAND_TOKEN_EDGE) for t in p.split()]
    if len(w) == 2 and w[1] == "hand" and w[0] in _POSSESSIVE | {"the"}:
        return True
    if len(w) <= 6 and any(t in _HAND_NOUNS for t in w) and not any(t in (_NOUNS - _HAND_NOUNS) for t in w):
        return True                                     # 'where your cursor is' -- not 'the icon next to the cursor'
    return False


_HAND_RELATION_RE = re.compile(r"\b(?:next to|near|beside|by|under|above|below|around|behind|left of|right of|close to)\b")
# 2026-09-26 (hand_fix F3, revised): '<hand noun> [back|over|up|down|across] to|toward|towards|onto|into|away from <X>'
# is the hand as the thing MOVED -- but only when X names a THING the eyes can find: a visual noun, a colour, or a
# screen part. The ask prompt itself says 'move your hand (the mouse) to', and 12 of 31 move objects copy that shape;
# 7 fell through to rule 3 as 'your hand' (L29-L33 on 09-19, L119/L121 Boot A). Without a thing after the preposition
# it stays her hand, as before: 'my cursor to show Ace', 'the pointer to say hi', 'mouse to where it was' -- the eyes
# cannot see the pointer (the 09-19 red-cursor bug). 'at' and a bare 'over' are left out ('the cursor at the top').
_HAND_MOVER_RE = re.compile(r"\b(?:mouse|cursor|pointer)\s+(?:(?:back|over|up|down|across)\s+)?"
                            r"(?:to|toward|towards|onto|into|away\s+from)\s+(\S.*)$")
_HAND_TARGET_WORDS = ((_NOUNS - _HAND_NOUNS - {"hand"}) | ((set(_BANDS) | _CHROMATIC) - {"dark"})
                      | {"button", "block", "box", "bar", "corner", "clock", "patch", "area", "field", "tab", "menu",
                         "panel", "link", "input", "scrollbar", "square", "circle", "shape", "title", "label", "frame",
                         "card", "folder", "file", "console", "app", "document", "photo", "portrait", "illustration"})


def _hand_is_mover(p: str) -> bool:
    m = _HAND_MOVER_RE.search(p)
    return bool(m) and any(t in _HAND_TARGET_WORDS for t in re.findall(r"[a-z]+", m.group(1)))


def hand_now() -> Optional[Dict]:
    """Where her hand is, as fractions of the logical screen, and whose hand last moved it. Same-process
    GetCursorPos and GetSystemMetrics agree on DPI, so the fraction is exact whatever the frame size."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        pt = wt.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return None
        sw, sh = int(ctypes.windll.user32.GetSystemMetrics(0)), int(ctypes.windll.user32.GetSystemMetrics(1))
        if sw <= 0 or sh <= 0:
            return None
    except Exception:
        return None
    x, y, now = int(pt.x), int(pt.y), time.time()
    idle = _last_input_idle_s()
    input_ts = (now - idle) if idle is not None else None      # when a human last touched keyboard or mouse
    with _H_LOCK:
        last, last_ts, moved_ts = _H["last"], _H["last_ts"], _H["moved_ts"]
        if last is not None and abs(last[0] - x) + abs(last[1] - y) >= 4:
            moved_ts = now
            hers = (now - _H["moving_ts"] < 3.0) or (_H["mine"] is not None and now - _H["mine_ts"] < 3.0 and _near(_H["mine"], (x, y)))
            if not hers:
                if input_ts is not None and input_ts >= last_ts - 1.0:
                    _H["ace_ts"] = input_ts                 # human input since the last sample: Ace, at the input time
                else:
                    _H["other_ts"] = now                    # moved, but no human input: some other mover
        _H["last"], _H["last_ts"], _H["moved_ts"] = (x, y), now, moved_ts
        mine, mine_ts, ace_ts, other_ts = _H["mine"], _H["mine_ts"], _H["ace_ts"], _H["other_ts"]
    where_left = mine is not None and _near(mine, (x, y))
    return {"x": x, "y": y, "screen_w": sw, "screen_h": sh, "cx": x / float(sw), "cy": y / float(sh),
            "still_s": (round(now - moved_ts, 1) if moved_ts else None), "ts": now,
            "ace_input_s": (round(idle, 1) if idle is not None else None),
            "mine_s": (round(now - mine_ts, 1) if mine is not None else None),
            "where_you_left_it": (where_left if mine is not None else None),
            "ace_moved_s": (round(now - ace_ts, 1) if ace_ts else None),
            "other_moved_s": (round(now - other_ts, 1) if other_ts else None)}


def _ago(s) -> str:
    s = float(s or 0)
    return "%.0f s" % s if s < 90 else ("%.0f min" % (s / 60.0) if s < 5400 else "over an hour")


def hand_owner_note(h: Dict) -> str:
    """One clause on whose hand it was -- only what the measured signals prove. The input clock knows that a
    human touched the keyboard or mouse, never which; the wording says so."""
    if not h:
        return ""
    mine_s, left, ace_in = h.get("mine_s"), h.get("where_you_left_it"), h.get("ace_input_s")
    ace_mv, other_mv = h.get("ace_moved_s"), h.get("other_moved_s")
    if mine_s is not None:
        if left:
            if ace_in is None:
                return "exactly where you left it %s ago" % _ago(mine_s)
            if ace_in > mine_s:
                return "exactly where you left it %s ago, and Ace has not touched the keyboard or mouse since" % _ago(mine_s)
            return "exactly where you left it %s ago; Ace has used the keyboard or mouse since but it has not moved" % _ago(mine_s)
        if ace_mv is not None and ace_mv <= mine_s + 1:
            return "not where you left it %s ago -- Ace moved it %s ago" % (_ago(mine_s), _ago(ace_mv))
        if other_mv is not None and other_mv <= mine_s + 1:
            return "not where you left it %s ago -- it was moved, but not by Ace's hand" % _ago(mine_s)
        return "not where you left it %s ago" % _ago(mine_s)
    if ace_in is not None and ace_in < 10:
        return "Ace's hand was on the keyboard or mouse %s ago" % _ago(ace_in)
    if ace_mv is not None and ace_mv < 120:
        return "Ace moved it %s ago" % _ago(ace_mv)
    return ""


def _place(cx: float, cy: float) -> Dict:
    col, row = min(_GRID_COLS - 1, int(cx * _GRID_COLS)), min(_GRID_ROWS - 1, int(cy * _GRID_ROWS))
    if not (0.0 <= cx < 1.0 and 0.0 <= cy < 1.0) and _ef("two_screens"):   # eyes_fix F8: off her (primary) screen --
        return {"row": row, "col": col, "cell": row * _GRID_COLS + col, "position": OTHER_SCREEN}   # never 'left' (C9)
    vert = "upper" if cy < 0.34 else ("lower" if cy > 0.66 else "middle")
    horiz = "left" if cx < 0.34 else ("right" if cx > 0.66 else "centre")
    return {"row": row, "col": col, "cell": row * _GRID_COLS + col,
            "position": vert + "-" + horiz if (vert, horiz) != ("middle", "centre") else "centre"}


_HAND_PLACE_SAID = _keep("_HAND_PLACE_SAID", [None, 0.0])


def _log_hand_place(h: Dict, position) -> None:
    """eyes_fix F0 'log' (DIAGNOSIS C9): the raw cursor beside the place word it became -- 'middle-left' fits her chat
    window and Ace's monitor 2 alike. One line per (x, y, place) per 30 s. ASCII."""
    try:
        k = (int(h["x"]), int(h["y"]), str(position))
        now = time.time()
        if _HAND_PLACE_SAID[0] == k and now - float(_HAND_PLACE_SAID[1]) < 30.0:
            return
        _HAND_PLACE_SAID[0], _HAND_PLACE_SAID[1] = k, now
        print("[Eyes] HAND PLACE: raw cursor (%d, %d) on her screen %dx%d -> '%s'" % (
            k[0], k[1], int(h.get("screen_w") or 0), int(h.get("screen_h") or 0), k[2]), flush=True)
    except Exception:
        pass


def hand_record(phrase: str, img=None) -> Dict:
    """A look record for her hand, in the vocabulary of every other look -- but felt, not seen."""
    h = hand_now()
    if h is None:
        return {"phrase": phrase, "status": "could_not_look", "why": "hand", "how": "hand"}
    fw = int(getattr(img, "width", 0) or _THUMB_W)
    fh = int(getattr(img, "height", 0) or int(_THUMB_W * 9 / 21.5))
    fx, fy = int(h["cx"] * fw), int(h["cy"] * fh)
    a = _HAND_ARROW_PX
    rec = {"phrase": phrase, "status": "found", "how": "hand", "felt": True,
           "bbox": [fx, fy, min(fw, fx + a), min(fh, fy + a)], "frame_w": fw, "frame_h": fh,
           "colour": "#ffffff", "colour_name": "white", "share": 1.0, "second_colour": None,
           "profile": {"white": 1.0}, "top_bands": [("white", 1.0)], "aspect": 1.5, "fill": 0.4,
           "shape": "a small white arrow pointing up and left",
           "size_pct": round(100.0 * (a * a) / float(fw * fh), 2), "fills_screen": False, "n_boxes": 1,
           "screen_xy": [h["x"], h["y"]], "still_s": h["still_s"], "frame_age_s": 0.0, "frame_src": "hand", "ms": 0}
    rec.update(_place(h["cx"], h["cy"]))
    if _ef("log"):                                     # eyes_fix F0: the raw cursor beside its place word
        _log_hand_place(h, rec.get("position"))
    rec["owner_note"] = hand_owner_note(h)
    try:
        from infrastructure import intention as _it       # lazy: no import cycle; the grant lives there
        _g = _it.grant_left_s()
        if _g > 0:
            rec["grant_s"] = int(_g)
    except Exception:
        pass
    cw = colour_word(phrase)
    if cw:
        rec["colour_word"] = cw
        rec["colour_fraction"] = 1.0 if cw == "white" else 0.0
        rec["matches"] = True if cw == "white" else False
    else:
        rec["matches"] = None
    return rec


def draw_hand(img) -> None:
    """Draw her hand (the pointer) onto a frame, in place: white arrow, dark outline, at the true position."""
    try:
        from PIL import ImageDraw
        h = hand_now()
        if h is None:
            return
        fx, fy = h["cx"] * img.width, h["cy"] * img.height
        k = _HAND_ARROW_PX / 16.0
        pts = [(0, 0), (0, 15), (4, 11.5), (6.5, 16), (9, 15), (6.5, 10.5), (11, 10.5)]
        poly = [(fx + px * k, fy + py * k) for px, py in pts]
        d = ImageDraw.Draw(img)
        d.polygon(poly, fill=(255, 255, 255), outline=(20, 20, 20))
    except Exception:
        pass


_STRIP_STATE = os.path.join(_ROOT, "state", "hand_overlay.json")
_STRIP_FRAC = 0.05                                  # the strip sits in the top 5% of the screen


def _paint_out_strip(img) -> None:
    """While the hand strip is on Ace's screen, cover its band in her frame with the rows just below it, so
    third-person text about herself never reaches her far eye."""
    try:
        with open(_STRIP_STATE, encoding="utf-8") as f:
            d = json.load(f)
        if not d.get("text") or time.time() > float(d.get("until") or 0):
            return
        band = max(2, int(img.height * _STRIP_FRAC))
        x0, x1 = int(img.width * 0.2), int(img.width * 0.8)
        patch = img.crop((x0, band, x1, 2 * band))
        img.paste(patch, (x0, 0))
    except Exception:
        pass


# ── a fresh frame ───────────────────────────────────────────────────────────────
def fresh_frame() -> Tuple[Optional[bytes], Optional[object], float, str]:
    """(png_bytes, PIL image, age_s, source). Grab the screen in-process (~50 ms, same 1024-wide thumbnail
    Florence has always been given); fall back to the 30 s tool snapshot with its real age."""
    try:
        from PIL import Image, ImageGrab
        im = ImageGrab.grab()
        if im.width > _THUMB_W:
            im = im.resize((_THUMB_W, max(1, int(im.height * _THUMB_W / im.width))), Image.Resampling.LANCZOS)
        im = im.convert("RGB")
        _paint_out_strip(im)                           # the hand strip is for Ace, not for her eyes
        draw_hand(im)                                  # the grab has no pointer in it; her hand goes in here
        buf = io.BytesIO()
        im.save(buf, "PNG", compress_level=1)
        return buf.getvalue(), im, 0.0, "grab"
    except Exception:
        pass
    try:
        from PIL import Image
        age = time.time() - os.path.getmtime(_FRAME_PNG)
        if age > _FRAME_MAX_AGE_S:
            return None, None, age, "stale"
        with open(_FRAME_PNG, "rb") as f:
            png = f.read()
        im = Image.open(io.BytesIO(png))
        im.load()
        return png, im.convert("RGB"), age, "snapshot"
    except Exception:
        return None, None, -1.0, "none"


# ── WINDOWS: the coarse map the OS already knows (Ace 2026-09-20: "unfocus ... move her focus") ─────────
_WIN_CACHE = _keep('_WIN_CACHE', [0.0, []])  #  ts, list: the map is cheap but not free of ctypes calls
_WIN_MIN_S = 2.0
_WIN_LOOK_CACHE = _keep('_WIN_LOOK_CACHE', {})  #  title -> (ts, rec): one look per window per 20 s
_WIN_LOOK_MIN_S = 20.0
_WIN_SKIP_CLASSES = {"TkTopLevel", "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
_WIN_WORDS = {"window", "windows", "browser", "chat", "console", "terminal", "log", "ui", "screen"}
_MENU_RE = re.compile(r"\b(?:File|Edit|View|Format|Help|Window|Tools|Search|Terminal|Run|Debug|Selection|Go)\b(?:\s+\b(?:File|Edit|View|Format|Help|Window|Tools|Search|Terminal|Run|Debug|Selection|Go)\b)+")
_WIN_TEXTY = re.compile(r"chat|browser|chrome|firefox|edge|notepad|log|console|terminal|code|editor|word|doc", re.I)
_WIN_MENTION_RE = re.compile(
    r"\b(?:(?:your|her|my) (?:own )?chat(?: window)?|chat window|(?:nous'?s?|nous'? own|claude'?s?) (?:window|ui|screen|side)|\bclaude\b|"
    r"(?:the |his |ace'?s? )?(?:browser|web ?page)(?: window)?|(?:the )?(?:log|console|terminal) window|"
    r"(?:the |his )?(?:window|windows) in front|(?:the |his |a )?front window|what(?:'s| is) in front|which window)\b", re.I)


def _win_name(title: str, cls: str) -> str:
    """Her words for a window: what is on his screen, never a mechanism name."""
    t = str(title or "")
    tl = t.lower()
    if "sourpatches" in tl and ("chat" in tl or cls.startswith("Qt")):
        return "your chat window"
    if tl == "claude" or tl.startswith("claude"):
        return "Nous's window (Claude)"
    if "google chrome" in tl or "mozilla firefox" in tl or "microsoft edge" in tl or "brave" in tl:
        page = re.sub(r"\s*[-\u2014\u2013]\s*(google chrome|mozilla firefox|microsoft edge|brave)\s*$", "", t, flags=re.I).strip()
        return "a browser, on '%s'" % page[:50] if page else "a browser"
    if cls == "ConsoleWindowClass" or "powershell" in tl or "python" in tl or tl.endswith(".exe") or "daemon" in tl:
        return "a console window"
    if cls in ("Notepad", "Notepad++") or "notepad" in tl:
        return "a text window, '%s'" % t[:40]
    return "a window called '%s'" % t[:40]


_WIN_LOCK = _keep("_WIN_LOCK", threading.RLock())
_WIN_ENUM = _keep("_WIN_ENUM", {"cb": None, "rows": [], "ctx": {}})   # ONE ctypes thunk for the process, made once


def _win_cb_impl(h, _l):
    """EnumWindows callback body (looked up by name, so a reload updates it without a new thunk)."""
    try:
        ctx = _WIN_ENUM["ctx"]; u = ctx["u"]; wt = ctx["wt"]; ctypes = ctx["ctypes"]; dwm = ctx["dwm"]
        sw, sh, fg = ctx["sw"], ctx["sh"], ctx["fg"]
        if not u.IsWindowVisible(h) or u.IsIconic(h):
            return True
        n = u.GetWindowTextLengthW(h)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, buf, n + 1)
        cl = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, cl, 256)
        if cl.value in _WIN_SKIP_CLASSES:
            return True
        if dwm is not None:
            ck = ctypes.c_int(0)
            if dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(ck), 4) == 0 and ck.value:
                return True                             # cloaked: a UWP shell window that is not on the screen
        r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        l, t, rr, b = max(0, r.left), max(0, r.top), min(int(sw), r.right), min(int(sh), r.bottom)
        if rr - l <= 0 or b - t <= 0:
            return True
        area = (rr - l) * (b - t) / (sw * sh)
        if area < 0.005:
            return True
        pl = _place((l + rr) / 2.0 / sw, (t + b) / 2.0 / sh)
        _WIN_ENUM["rows"].append({"hwnd": int(h), "title": buf.value, "cls": cl.value, "name": _win_name(buf.value, cl.value),
                                  "frac": (l / sw, t / sh, rr / sw, b / sh), "rect": (r.left, r.top, r.right, r.bottom),
                                  "size_pct": round(100 * area, 1), "position": pl["position"], "front": h == fg,
                                  "half": ("left half" if rr / sw <= 0.55 else ("right half" if l / sw >= 0.45 else
                                           ("most of the screen" if area >= 0.6 else pl["position"])))})
    except Exception:
        pass
    return True


def windows_now(max_n: int = 8) -> List[Dict]:
    """Visible top-level windows on the primary screen, front to back, as fractions of the screen (the rects come
    in the process's DPI space; the fractions do not care). [] on any error -- then the prompt says nothing.
    One ctypes thunk for the whole process, one lock around the enumeration (3.14t)."""
    now = time.time()
    if now - _WIN_CACHE[0] < _WIN_MIN_S:
        return _WIN_CACHE[1]
    try:
        import ctypes, ctypes.wintypes as wt
        u = ctypes.windll.user32
        try:
            dwm = ctypes.windll.dwmapi
        except Exception:
            dwm = None
        sw, sh = float(u.GetSystemMetrics(0)), float(u.GetSystemMetrics(1))
        if sw <= 0 or sh <= 0:
            return []
        with _WIN_LOCK:
            if now - _WIN_CACHE[0] < _WIN_MIN_S:
                return _WIN_CACHE[1]
            if _WIN_ENUM["cb"] is None:
                _WIN_ENUM["cb"] = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(lambda h, l: _win_cb_impl(h, l))
            _WIN_ENUM["ctx"] = {"u": u, "wt": wt, "ctypes": ctypes, "dwm": dwm, "sw": sw, "sh": sh, "fg": u.GetForegroundWindow()}
            _WIN_ENUM["rows"] = []
            u.EnumWindows(_WIN_ENUM["cb"], 0)
            rows = list(_WIN_ENUM["rows"])
            for i, w in enumerate(rows):
                cov = 0.0
                l1, t1, r1, b1 = w["frac"]
                for f in rows[:i]:
                    l2, t2, r2, b2 = f["frac"]
                    ov = max(0.0, min(r1, r2) - max(l1, l2)) * max(0.0, min(b1, b2) - max(t1, t2))
                    cov = max(cov, ov / max(1e-6, (r1 - l1) * (b1 - t1)))
                w["covered"] = round(cov, 2)
            rows = rows[:max_n]
            _note_departures(_WIN_CACHE[1], rows, now)   # 2026-10-06 (council_set1 item 5): which windows just left (never raises)
            _WIN_CACHE[0], _WIN_CACHE[1] = now, rows
            return rows
    except Exception as e:
        print("[Eyes] windows: %s" % str(e)[:80], flush=True)
        return _WIN_CACHE[1]


def render_windows(wins: Optional[List[Dict]] = None) -> str:
    wins = windows_now() if wins is None else wins
    if not wins:
        return ""
    bits = []
    for w in wins:
        tag = ""
        if w.get("front"):
            tag = ", in front"
        elif w.get("covered", 0) >= 0.7:
            tag = ", behind"
        elif w.get("covered", 0) >= 0.3:
            tag = ", partly covered"
        bits.append("%s (%s, %s%% of the screen%s)" % (w["name"], w["half"], w["size_pct"], tag))
    return "Open on your screen, front to back: " + "; ".join(bits) + "."


def front_window() -> Optional[Dict]:
    for w in windows_now():
        if w.get("front"):
            return w
    return None


def window_mentions(text: str) -> List[Dict]:
    """The windows his words point at, in order, without duplicates -- matched against the live map."""
    t = str(text or "")
    if not t:
        return []
    wins = windows_now()
    if not wins:
        return []
    out: List[Dict] = []
    seen = set()

    def _add(w, phrase, kind=""):
        if w is None:
            if kind and not any(o.get("status") == "window_missing" and o.get("name") == kind for o in out):
                out.append({"status": "window_missing", "name": kind, "asked_as": phrase, "phrase": phrase})
            return
        if w["hwnd"] not in seen:
            seen.add(w["hwnd"]); r = dict(w); r["asked_as"] = phrase; out.append(r)
    for m in _WIN_MENTION_RE.finditer(t):
        ph = m.group(0).lower()
        if "chat" in ph and "window" in ph or ph.strip() in ("your chat", "her chat", "my chat", "the chat"):
            _add(next((w for w in wins if w["name"] == "your chat window"), None), ph, "your chat window")
        elif "nous" in ph or "claude" in ph:
            _add(next((w for w in wins if "Claude" in w["name"]), None), ph, "Nous's window")
        elif "browser" in ph or "chrome" in ph or "page" in ph:
            _add(next((w for w in wins if w["name"].startswith("a browser")), None), ph, "a browser window")
        elif "log" in ph or "console" in ph or "terminal" in ph:
            _add(next((w for w in wins if w["name"] == "a console window"), None), ph, "a console window")
        elif "front" in ph or "open" in ph or "which window" in ph:
            _add(next((w for w in wins if w.get("front")), None), ph)
    tl = t.lower()
    for w in wins:                                   # a title he quotes ('constellations', 'Steam')
        title = str(w.get("title", "")).lower()
        head = re.split(r"\s*[-\u2014\u2013]\s*", title)[0].strip()
        if len(head) >= 4 and head in tl and w["hwnd"] not in seen:
            _add(w, head)
    return out


def look_window(w: Dict, timeout_s: float = 25.0, read_words: Optional[bool] = None, origin: Optional[str] = None) -> Dict:   # eyes_fix F6: + origin
    """Focus on ONE window: crop the live screen to it (physical pixels, whatever the DPI), caption the crop, and
    read its words when it is a text-bearing window. Cached per window for 20 s."""
    title = str(w.get("title", ""))
    now = time.time()
    c = _WIN_LOOK_CACHE.get(title)
    if c and now - c[0] < _WIN_LOOK_MIN_S:
        r = dict(c[1]); r["cached_age_s"] = round(now - c[0], 1); return r
    rec = {"phrase": w.get("asked_as") or w["name"], "status": "window", "name": w["name"], "half": w["half"], "title": title,
           "hwnd": w.get("hwnd"), "size_pct": w["size_pct"], "front": bool(w.get("front")), "covered": w.get("covered", 0.0), "text": "", "words": ""}
    url = florence_url()
    if not url:
        rec["status"] = "could_not_look"; rec["why"] = "network"; return rec
    try:
        import ctypes
        from PIL import Image, ImageGrab
        u = ctypes.windll.user32
        full = ImageGrab.grab()
        sx, sy = full.width / float(u.GetSystemMetrics(0)), full.height / float(u.GetSystemMetrics(1))
        l, t, r, b = w["rect"]
        box = (max(0, int(l * sx)), max(0, int(t * sy)), min(full.width, int(r * sx)), min(full.height, int(b * sy)))
        if box[2] - box[0] < 16 or box[3] - box[1] < 16:
            rec["status"] = "could_not_look"; rec["why"] = "frame"; return rec
        _paint_out_strip(full)                        # the hand strip is for Ace, not for her eyes (any window under it)
        im = full.crop(box).convert("RGB")
        if im.width > _THUMB_W:
            im = im.resize((_THUMB_W, max(1, int(im.height * _THUMB_W / im.width))), Image.Resampling.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG", compress_level=1); png = buf.getvalue()
    except Exception as e:
        rec["status"] = "could_not_look"; rec["why"] = "frame"; rec["err"] = str(e)[:80]; return rec
    texty = bool(_WIN_TEXTY.search(w["name"] + " " + title)) if read_words is None else bool(read_words)
    task = "detailed,ocr" if texty else "detailed"
    sem = _INFLIGHT
    if not sem.acquire(timeout=timeout_s):
        rec["status"] = "could_not_look"; rec["why"] = "timeout"
        print("[Eyes] WINDOW %s: could not look (the far eye was busy for %.0f s)" % (w["name"], timeout_s), flush=True); return rec
    try:
        req = urllib.request.Request(url + "/caption?task=" + task, data=png, headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            d = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as e:
        rec["status"] = "could_not_look"; rec["why"] = "network"; rec["err"] = str(e)[:80]
        print("[Eyes] WINDOW %s: could not look (%s)" % (w["name"], str(e)[:80]), flush=True); return rec
    finally:
        sem.release()                                  # the SAME semaphore object we acquired, whatever a reload rebinds
    res = d.get("result") or {}
    text = _PREAMBLE.sub("", str(res.get("detailed") or ""), count=1).strip()
    rec["text"] = (text[0].upper() + text[1:]) if text else ""
    ocr = res.get("ocr")
    if isinstance(ocr, dict):
        ocr = ocr.get("ocr") or ocr.get("text") or ""
    words = " ".join(str(ocr or "").split())
    words = _MENU_RE.sub(" ", words)                             # window chrome is not what he wrote
    words = " ".join(t for t in words.split() if len(t) > 2 or t.lower() in ("i", "a", "no", "ok", "hi", "to", "of", "in", "on", "is", "it", "me", "my", "we", "do", "so", "be", "up", "if", "or", "an", "at", "by", "as", "am", "us", "go") or t[:1].isdigit() or t in (":D", ":P", ":)", "<3"))
    rec["words"] = words[-360:] if len(words) > 360 else words   # the LAST lines of a chat / log are the newest
    _WIN_LOOK_CACHE[title] = (now, dict(rec))
    print("[Eyes] WINDOW %s: %s | words: %s" % (w["name"], rec["text"][:100], rec["words"][:80]), flush=True)
    set_focus(rec, origin=origin)                     # eyes_fix F6: origin 'front' / 'ace' = a glance (with the key)
    return rec


def render_window_look(g: Dict) -> str:
    where = "%s, %s%% of the screen%s" % (g.get("half", "?"), g.get("size_pct", "?"),
                                          ", in front" if g.get("front") else (", partly behind another" if float(g.get("covered") or 0) >= 0.3 else ""))
    fa = float(g.get("cached_age_s") or 0.0)
    old = (" (from your look %.0f s ago)" % fa) if fa > 15 else ""
    parts = ["You moved your focus to %s%s (%s): %s" % (g.get("name", "a window"), old, where, _sentence_cut(g.get("text", ""), 300) or "nothing your far eye could put into words")]
    if g.get("words"):
        parts.append("Words you can read in it (the newest at the end): \"%s\"" % g["words"][-300:])
    return " ".join(parts)


# ── FOCUS: what she is holding (Ace 2026-09-20: "her vision snapped back ... and she lost it") ──────────
_FOCUS = _keep('_FOCUS', {"rec": None, "ts": 0.0})
_FOCUS_HOLD_S = float(os.environ.get("AKASHIC_EYES_FOCUS_HOLD_S", "600") or 600)
_READ_WINDOWS = _keep('_READ_WINDOWS', {})  #  hwnd -> ts of her last read of it (no re-read inside _REREAD_S)
_REREAD_S = 300.0
# 2026-10-06 (Nous, council_set1 item 5 -- Ace's Monday list: after the player closed, "American Dad" kept coming back).
# A held window is the main carrier (Boot G: the closed Media Player's caption, "Family Guy" in it, reached two Ace prompts after
# the close, G137092 / G138398). Live switch state/council_set1.json {"stale_topic": true}; absent / unreadable / not exactly true
# = every function below the lines marked council_set1 behaves as today, byte for byte. ON:
#   * focus_now: a held window that has LEFT the window map is classified at read time -- closed (IsWindow false), put away
#     (minimised / hidden) or out of view (another screen, cloaked, 9th+ in z-order, tiny). Closed -> the hold ends and ONE
#     notice line, no caption, no words, is told to her next reply to Ace and ONE to her next other prompt (skeptic F6: a
#     surprise or goal-author prompt reading it first no longer takes it from his reply). Put away / out of view -> the hold stays (a restore re-holds it)
#     but its caption and words are not rendered while she cannot see into it. An open window keeps today's 600 s hold.
#   * start_grounding: Ace's "I closed it" / "it's closed" / "I turned it off" ends the hold (the window he means: a named
#     window, else the held one if it left the map, else the latest departure <= 10 min, else the held one when his words
#     point at it). Words never OPEN a hold here; only her eyes do, and only on a window present in the map.
#   * front_item_closed: the driver drops a front-window surprise whose window has closed before she would speak of it.
# Bound: the map refreshes every _WIN_MIN_S (2 s); the first prompt rendered after that carries no caption of a closed window.
_FOCUS_LOCK = _keep('_FOCUS_LOCK', threading.Lock())
_FOCUS_END = _keep('_FOCUS_END', {"note": None})          # the one closing notice still to be told
_DEPARTED = _keep('_DEPARTED', [])                         # windows that just left the map: hwnd, title, name, ts (<= 10 min, 16)
_FRONT_TOLD = _keep('_FRONT_TOLD', [None])                 # the window of the last front-window surprise (hwnd, name, ts)
_CS1_SWITCH = os.path.join(_ROOT, "state", "council_set1.json")
_CS1_TTL_S = 1.0
_CS1_CACHE = _keep('_CS1_CACHE', [(0.0, None)])
_DEPART_KEEP_S = 600.0


def _glance_keep(now: float):
    """eyes_fix F6: what the focus goes back to when a glance ends -- her own hold if it is still inside its own time (or the
    one an earlier glance was keeping). Called under _FOCUS_LOCK."""
    if _FOCUS.get("glance"):
        return _FOCUS.get("back")
    r = _FOCUS.get("rec")
    if r is not None and now - float(_FOCUS.get("ts") or 0.0) <= float(_FOCUS.get("hold_s") or _FOCUS_HOLD_S):
        return {"rec": r, "ts": float(_FOCUS.get("ts") or 0.0), "hold_s": float(_FOCUS.get("hold_s") or _FOCUS_HOLD_S)}
    return None


def _glance_over(now: float) -> None:
    """eyes_fix F6 'glance' (the 10-06 rule: notice, glance, come back; DIAGNOSIS C6). A window she did not choose -- it came
    to the front, or Ace named it -- holds for _GLANCE_S, then the focus goes back to what she held before, or to nothing.
    Only a hold a glance made carries 'glance', so with the key off this never acts."""
    with _FOCUS_LOCK:
        if not _FOCUS.get("glance") or now - float(_FOCUS.get("ts") or 0.0) <= float(_FOCUS.get("hold_s") or _GLANCE_S):
            return
        name = str((_FOCUS.get("rec") or {}).get("name") or "a window")
        back = _FOCUS.get("back")
        for _k in ("glance", "back", "hold_s"):
            _FOCUS.pop(_k, None)
        if back and back.get("rec") is not None and now - float(back.get("ts") or 0.0) <= float(back.get("hold_s") or _FOCUS_HOLD_S):
            _FOCUS["rec"], _FOCUS["ts"], _FOCUS["hold_s"] = back["rec"], float(back["ts"]), float(back.get("hold_s") or _FOCUS_HOLD_S)
            told = "your focus is back on %s" % str(back["rec"].get("name") or "a window")
        else:
            _FOCUS["rec"] = None
            told = "nothing is held now"
    print("[Eyes] GLANCE over: %s (a window you did not choose) after %.0f s; %s" % (name, _GLANCE_S, told), flush=True)


def set_focus(rec: Dict, origin: Optional[str] = None) -> None:   # eyes_fix F6: + origin ('front' / 'ace' = not hers)
    """A window she read becomes what she holds; its words go into the weave as a turn of her own eyes."""
    if not rec or rec.get("status") != "window":
        return
    _gl = origin in ("front", "ace") and _ef("glance")  # eyes_fix F6: a window she did not choose is a glance, not a hold
    with _FOCUS_LOCK:                                  # 2026-10-06 (council_set1 item 5): one writer of the hold at a time
        _back = _glance_keep(time.time()) if _gl else None
        _FOCUS["rec"], _FOCUS["ts"] = dict(rec), time.time()
        if _gl:
            _FOCUS["glance"], _FOCUS["hold_s"], _FOCUS["back"] = origin, _GLANCE_S, _back
        else:
            for _k in ("glance", "hold_s", "back"):
                _FOCUS.pop(_k, None)
    if rec.get("hwnd"):
        _READ_WINDOWS[int(rec["hwnd"])] = time.time()
        for k in [k for k, ts in _READ_WINDOWS.items() if time.time() - ts > 3600]:
            _READ_WINDOWS.pop(k, None)
    try:
        words = str(rec.get("words") or "").strip()
        if len(words) >= 8 and rec.get("name") != "your chat window":     # her own chat's words are Ace's and hers, already woven
            from infrastructure import sequence_weave as _w
            _w.drop("%s: %s" % (rec.get("name", "a window"), words[-240:]), "eyes", 1, source="eyes")
    except Exception:
        pass


def focus_now(lane: Optional[str] = None) -> Optional[Dict]:   # 2026-10-06 (council_set1 item 5): + lane (skeptic F6); OFF: ignored
    if _st_on():                                       # 2026-10-06 (council_set1 item 5); OFF: the lines below, unchanged
        return _focus_now_cs1(lane)
    _glance_over(time.time())                          # eyes_fix F6: a glance that ran out gives the focus back
    r = _FOCUS["rec"]
    if r is None or time.time() - _FOCUS["ts"] > float(_FOCUS.get("hold_s") or _FOCUS_HOLD_S):   # eyes_fix F6: + hold_s
        return None
    out = dict(r); out["held_s"] = time.time() - _FOCUS["ts"]
    wins = windows_now()
    w = next((x for x in wins if r.get("hwnd") and x.get("hwnd") == r.get("hwnd")), None) \
        or next((x for x in wins if x.get("title") == r.get("title")), None)
    out["still_open"] = w is not None
    if w is not None:
        out["front_now"] = bool(w.get("front")); out["half"] = w["half"]; out["covered_now"] = float(w.get("covered") or 0)
        fw = next((x for x in wins if x.get("front")), None)
        out["behind"] = fw["name"] if (fw is not None and not w.get("front")) else ""
    return out


def render_focus(f: Optional[Dict]) -> str:
    if not f:
        return ""
    if f.get("cs1"):                                  # 2026-10-06 (council_set1 item 5): only the ON path marks a record
        return _render_focus_cs1(f)
    ago = f.get("held_s", 0.0)
    when = "just now" if ago < 20 else ("%.0f s ago" % ago if ago < 120 else "%.0f min ago" % (ago / 60))
    if not f.get("still_open"):
        where = "it has since been closed"
    elif f.get("front_now"):
        where = "still in front"
    else:
        where = "still open, %s now" % (("behind %s" % f["behind"]) if f.get("behind") else "behind another window")
    parts = ["What you are holding in focus (read %s): %s, %s. %s" % (when, f.get("name", "a window"), where, _sentence_cut(f.get("text", ""), 240) or "")]
    if f.get("words"):
        parts.append("Words you read in it: \"%s\"" % f["words"][-300:])
    return " ".join(parts).replace(". .", ".")


# -- council_set1 item 5 (2026-10-06): a closed window's topic stops being fed --------------------------------------
def _cs1() -> Dict:
    """state/council_set1.json ({} when absent, unreadable, torn or not an object). 1 s cache. Never raises."""
    now = time.time()
    c = _CS1_CACHE[0]
    if c[1] is not None and 0.0 <= now - c[0] < _CS1_TTL_S:
        return c[1]
    d: Dict = {}
    try:
        with open(_CS1_SWITCH, "rb") as f:
            v = json.loads(f.read().decode("utf-8-sig"))
        d = v if isinstance(v, dict) else {}
    except Exception:
        d = {}
    _CS1_CACHE[0] = (now, d)
    return d


def _st_on() -> bool:
    try:
        return _cs1().get("stale_topic") is True
    except Exception:
        return False


def _win_state(hwnd) -> str:
    """Why a window is not in the map: 'closed' (no such window any more), 'put_away' (minimised or hidden), 'out_of_view'
    (it exists and shows: another screen, cloaked, past the 8-window cap, tiny), or 'unknown'. Never raises."""
    try:
        h = int(hwnd or 0)
        if h <= 0:
            return "unknown"
        import ctypes
        import ctypes.wintypes as wt
        u = ctypes.windll.user32
        if not u.IsWindow(wt.HWND(h)):
            return "closed"
        if u.IsIconic(wt.HWND(h)) or not u.IsWindowVisible(wt.HWND(h)):
            return "put_away"
        return "out_of_view"
    except Exception:
        return "unknown"


def _note_departures(old: List[Dict], new: List[Dict], now: float) -> None:
    """Called inside windows_now (under _WIN_LOCK) at each map refresh: remember which windows just left. Never raises."""
    try:
        cur = {int(w.get("hwnd") or 0) for w in (new or [])}
        for w in (old or []):
            h = int(w.get("hwnd") or 0)
            if h and h not in cur and not any(d.get("hwnd") == h for d in _DEPARTED):
                _DEPARTED.append({"hwnd": h, "title": str(w.get("title") or ""), "name": str(w.get("name") or "a window"), "ts": now})
        keep = [d for d in _DEPARTED if d.get("hwnd") not in cur and now - float(d.get("ts") or 0.0) <= _DEPART_KEEP_S][-16:]
        _DEPARTED[:] = keep
    except Exception:
        pass


def departed(max_age_s: float = _DEPART_KEEP_S) -> List[Dict]:
    """Windows that left the map in the last max_age_s, newest first (copies)."""
    now = time.time()
    with _WIN_LOCK:
        return [dict(d) for d in reversed(_DEPARTED) if now - float(d.get("ts") or 0.0) <= max_age_s]


def _end_focus(rec: Optional[Dict], why: str) -> bool:
    """End the hold on `rec` (only if it is still the one held) and leave ONE notice for the next prompt."""
    with _FOCUS_LOCK:
        cur = _FOCUS["rec"]
        if rec is not None and cur is not rec:
            return False
        r = cur if rec is None else rec
        if r is None:
            return False
        _FOCUS["rec"] = None
        _FOCUS_END["note"] = {"why": why, "name": str(r.get("name") or "a window"), "hwnd": r.get("hwnd"),
                              "read_ts": float(_FOCUS["ts"] or 0.0), "ts": time.time(), "told_to": []}
    return True


def _take_end_note(now: float, lane: Optional[str] = None) -> Optional[Dict]:
    """The closing notice: told ONCE to a prompt that answers Ace (lane 'ace') and ONCE to her other prompts (anything
    else: a surprise, a voluntary line, the goal author). Skeptic F6: whichever reads it first no longer takes it from the other."""
    k = "ace" if lane == "ace" else "side"
    with _FOCUS_LOCK:
        n = _FOCUS_END.get("note")
        if not n or now - float(n.get("ts") or 0.0) > _FOCUS_HOLD_S:
            return None
        told = n.setdefault("told_to", [])
        if k in told:
            return None
        told.append(k)
        return {"cs1": True, "gone": n["why"], "name": n["name"], "held_s": now - float(n.get("read_ts") or now),
                "still_open": False, "text": "", "words": ""}


def _focus_now_cs1(lane: Optional[str] = None) -> Optional[Dict]:
    now = time.time()
    _glance_over(now)                                  # eyes_fix F6
    with _FOCUS_LOCK:
        r = _FOCUS["rec"]
        ts = float(_FOCUS["ts"] or 0.0)
        _hold = float(_FOCUS.get("hold_s") or _FOCUS_HOLD_S)   # eyes_fix F6
        n = _FOCUS_END.get("note")
        if r is not None and n is not None and float(n.get("ts") or 0.0) < ts:
            _FOCUS_END["note"] = None          # a newer hold superseded the notice
    if r is None or now - ts > _hold:                   # eyes_fix F6: was _FOCUS_HOLD_S (the same unless a glance holds)
        return _take_end_note(now, lane)
    out = dict(r); out["held_s"] = now - ts
    wins = windows_now()
    w = next((x for x in wins if r.get("hwnd") and x.get("hwnd") == r.get("hwnd")), None) \
        or next((x for x in wins if x.get("title") == r.get("title")), None)
    out["still_open"] = w is not None
    if w is not None:
        out["front_now"] = bool(w.get("front")); out["half"] = w["half"]; out["covered_now"] = float(w.get("covered") or 0)
        fw = next((x for x in wins if x.get("front")), None)
        out["behind"] = fw["name"] if (fw is not None and not w.get("front")) else ""
        return out
    st = _win_state(r.get("hwnd"))
    if st == "closed":
        if _end_focus(r, "closed"):
            print("[Eyes] FOCUS ended: %s is closed" % r.get("name", "a window"), flush=True)
        return _take_end_note(now, lane)
    out["cs1"] = True; out["gone"] = st; out["text"] = ""; out["words"] = ""
    return out


def _render_focus_cs1(f: Dict) -> str:
    name = f.get("name", "a window")
    gone = f.get("gone")
    if gone == "closed":
        return "The window you were holding in focus, %s, is closed now." % name
    if gone == "ace_closed":
        return "Ace closed %s; it is not on the screen any more." % name
    if gone == "ace_closed_inside":
        return "Ace says he closed what was in %s; what you read in it before is over." % name
    ago = float(f.get("held_s") or 0.0)
    when = "just now" if ago < 20 else ("%.0f s ago" % ago if ago < 120 else "%.0f min ago" % (ago / 60))
    if gone == "put_away":
        return "What you are holding in focus (read %s): %s, put away now (minimised), so you cannot see into it." % (when, name)
    return "What you are holding in focus (read %s): %s, out of your view now (behind other windows or off this screen)." % (when, name)


# skeptic F2 (2026-10-06): 'stopped' / 'quit' / 'exited' / 'shut' need an object ('I stopped and thought' is not a close);
# 'that's off' and 'its gone' are gone; 'it's off' needs 'now' / 'already'; a non-screen object (eyes, door, blinds, lights ...)
# or a past time (last night, years ago ...) in the clause vetoes it. Corpus re-run: the same 2 real closes, nothing else.
_CLOSE_OBJ = r"(?:it|that|this|the\s+[\w']+|my\s+[\w']+|our\s+[\w']+)"
_CLOSE_RE = re.compile(
    r"\b(?:i|we)(?:'ve| have)?\s+(?:just\s+|already\s+)?"
    r"(?:closed|turned\s+(?:it|that|this|\w+)?\s*off|turned\s+off"
    r"|shut\s+(?:down|off)\b|shut\s+" + _CLOSE_OBJ + r"(?:\s+(?:down|off))?"
    r"|(?:exited|quit|stopped)\s+(?:out\s+of\s+)?" + _CLOSE_OBJ + r")\b"
    r"|\b(?:it'?s|its|it\s+is)\s+(?:(?:now|already)\s+)?(?:closed|shut(?:\s+down)?)\b"
    r"|\b(?:it'?s|its|it\s+is)\s+(?:(?:now|already)\s+off|off\s+(?:now|already))\b", re.I)
_CLOSE_NEG = re.compile(r"\b(?:not|never|didn'?t|haven'?t|don'?t|won'?t|can'?t|isn'?t|wasn'?t|aren'?t)\b", re.I)
_CLOSE_REF = re.compile(r"\b(?:it|that|this|video|show|episode|movie|film|player|game|music|song|stream|tab|window)\b", re.I)
_CLOSE_NOT = re.compile(r"\b(?:my|the|our|your|his|her|a)\s+(?:eyes?|mouth|doors?|blinds|curtains?|fridge|gate|lid|lights?|lamp|oven|"
                        r"stove|heater|fan|alarm|car|engine|water|tap|book|store|shop)\b", re.I)
_CLOSE_PAST = re.compile(r"\b(?:yesterday|last\s+(?:night|week|month|year|time)|(?:days?|weeks?|months?|years?)\s+ago|"
                         r"earlier\s+today|this\s+morning)\b", re.I)
_CLOSE_BOUND = re.compile(r"[,.;:!?]|\b(?:and|but|so|then|because|cause|while)\b", re.I)


def _close_clause(t: str, m) -> str:
    """The close match plus what follows it up to the clause boundary (<= 30 chars): where its object and refs may be."""
    tail = t[m.end():m.end() + 30]
    b = _CLOSE_BOUND.search(tail)
    return t[m.start():m.end()] + (tail[:b.start()] if b else tail)


def _close_match(text: str):
    """The first close Ace states (a regex match), or None. Pure."""
    t = str(text or "")
    for m in _CLOSE_RE.finditer(t):
        pre = t[max(0, m.start() - 20):m.start()]
        if _CLOSE_NEG.search(pre) or _CLOSE_NEG.search(m.group(0)):
            continue
        c = _close_clause(t, m)
        if _CLOSE_NOT.search(c) or _CLOSE_PAST.search(c):
            continue
        return m
    return None


def close_said(text: str) -> bool:
    """Ace says something is closed (corpus 2026-10-06: his chat history, nous_builds/council_set1/tests). Pure."""
    return _close_match(text) is not None


def _title_head(title: str) -> str:
    return re.split(r"\s*[-\u2014\u2013]\s*", str(title or "").lower())[0].strip()


def _close_heard(text: str) -> Optional[str]:
    """Ace said he closed something: end the hold he means. Returns what was closed, or None. Idempotent."""
    cm = _close_match(text)
    if cm is None:
        return None
    now = time.time()
    tl = str(text or "").lower()
    tc = _close_clause(tl, cm)                       # skeptic F2: rule 4 looks only inside the clause of the close
    with _FOCUS_LOCK:
        r = _FOCUS["rec"] if (_FOCUS["rec"] is not None and now - float(_FOCUS["ts"] or 0.0) <= float(_FOCUS.get("hold_s") or _FOCUS_HOLD_S)) else None   # eyes_fix F6
    wins = windows_now()
    in_map = (lambda rec: rec is not None and any((rec.get("hwnd") and x.get("hwnd") == rec.get("hwnd")) or x.get("title") == rec.get("title") for x in wins))
    dep = departed()
    target, why = None, None
    for d0 in dep:                                                     # 1. a window he names that just left
        h0 = _title_head(d0.get("title"))
        if len(h0) >= 4 and h0 in tl:
            target = d0
            break
    if target is None and r is not None:
        h1 = _title_head(r.get("title"))
        if len(h1) >= 4 and h1 in tl:
            target = r
    if target is None and r is not None and not in_map(r):             # 2. 'it': the held window, gone from the map
        target = r
    if target is None and dep:                                         # 3. the latest departure
        target = dep[0]
    if target is None and r is not None and _CLOSE_REF.search(tc):     # 4. the held window, still open: its content is over
        target = r
    if target is None:
        print("[Eyes] CLOSE heard (%r) -- nothing held, nothing just left" % str(text)[:60], flush=True)
        return None
    with _WIN_LOCK:                                  # verify_tests F8: the map-refresh thread rewrites _DEPARTED under this lock (an RLock)
        for d0 in _DEPARTED:
            if target.get("hwnd") and d0.get("hwnd") == target.get("hwnd"):
                d0["ace_closed"] = True
    is_focus = r is not None and (target is r or (target.get("hwnd") and target.get("hwnd") == r.get("hwnd")))
    if is_focus:
        _end_focus(r, "ace_closed" if not in_map(r) else "ace_closed_inside")
    name = str(target.get("name") or "a window")
    print("[Eyes] CLOSED (Ace said so): %s%s" % (name, " -- the hold on it ended" if is_focus else ""), flush=True)
    return name


def front_item_closed(item: Optional[Dict]) -> bool:
    """True when `item` is the front-window surprise about a window that has closed (or that Ace said he closed)."""
    try:
        if not _st_on() or not item:
            return False
        if str(item.get("kind")) != "eyes" or str(item.get("key")) != "front":
            return False
        ft = _FRONT_TOLD[0]
        if not ft or abs(float(item.get("ts") or 0.0) - float(ft.get("ts") or 0.0)) > 10.0:
            return False
        h = int(ft.get("hwnd") or 0)
        if not h or any(w.get("hwnd") == h for w in windows_now()):
            return False
        return _win_state(h) == "closed" or any(d.get("hwnd") == h and d.get("ace_closed") for d in departed())
    except Exception:
        return False


# ── the SURVEY: look the whole picture over (Ace 2026-09-20) ───────────────────────
_WHOLE_RE = re.compile(r"\b(?:image|images|picture|pictures|wallpaper|photo|photos|screenshot|artwork|drawing|illustration|"
                       r"look (?:it|this|that|the (?:image|picture|screen)) over|take it in|taking it in|look over|what do you see|"
                       r"describe (?:what|the|your)|whole (?:image|picture|screen))\b", re.I)
_SURVEY_SLOT = _keep('_SURVEY_SLOT', [None])
_WINDOW_SLOT = _keep('_WINDOW_SLOT', [None])
_WHOLE_NOUNS = {"image", "images", "picture", "pictures", "wallpaper", "photo", "photos", "screenshot", "artwork", "art",
                "drawing", "illustration", "screen", "desktop", "everything", "whole screen", "whole image", "whole picture"}
_SURVEY_CACHE = _keep('_SURVEY_CACHE', [0.0, None])  #  ts, dict: one survey per 20 s is plenty
_SURVEY_MIN_S = 20.0


def wants_survey(text: str) -> bool:
    return bool(_WHOLE_RE.search(str(text or "")))


def is_whole(phrase: str) -> bool:
    p = " ".join(str(phrase or "").lower().replace("the ", " ").replace("my ", " ").replace("your ", " ").split())
    if not (p in _WHOLE_NOUNS or head_noun(p) in _WHOLE_NOUNS):
        return False
    # fold 10-09 (DIAGNOSIS 5.3): 'pictures' is also a toy of her Playroom. A toy her eyes can see by its name (playroom_record:
    # Ace's eyes switch 'toy_names', the VERIFIED Playroom, the toy uncovered) is that toy, not the whole screen; otherwise
    # (no key, not verified, covered) the word stays a survey, as before.
    return playroom_record(phrase) is None


def survey(timeout_s: float = 25.0, max_regions: int = 5) -> Optional[Dict]:
    """One call to the far eye (detailed + dense): what the whole screen shows, and where things are."""
    now = time.time()
    if _SURVEY_CACHE[1] is not None and now - _SURVEY_CACHE[0] < _SURVEY_MIN_S:
        return _SURVEY_CACHE[1]
    url = florence_url()
    if not url:
        return None
    png, img, age, src = fresh_frame()
    if img is None:
        return None
    sem = _INFLIGHT if "_INFLIGHT" in globals() else None
    if sem is not None and not sem.acquire(timeout=timeout_s):
        return None
    try:
        req = urllib.request.Request(url + "/caption?task=detailed,dense", data=png, headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("[Eyes] survey: %s" % str(e)[:80], flush=True)
        return None
    finally:
        if sem is not None:
            sem.release()
    res = d.get("result") or {}
    text = str(res.get("detailed") or "")
    text = _PREAMBLE.sub("", text, count=1).strip()
    if text:
        text = text[0].upper() + text[1:]
    dense = res.get("dense") or {}
    regions = []
    W, H = float(img.width), float(img.height)
    for box, label in zip(dense.get("bboxes") or [], dense.get("labels") or []):
        try:
            x1, y1, x2, y2 = [float(b) for b in box]
        except Exception:
            continue
        size = (x2 - x1) * (y2 - y1) / (W * H)
        if size <= 0 or size >= _WHOLE_FRAME:
            continue
        pl = _place((x1 + x2) / 2.0 / W, (y1 + y2) / 2.0 / H)
        regions.append({"label": str(label)[:60], "position": pl["position"], "size_pct": round(100 * size, 1)})
    regions.sort(key=lambda r: -r["size_pct"])
    out = {"phrase": "the whole picture", "status": "survey", "text": text, "regions": regions[:max_regions], "ts": now, "frame_src": src}
    _SURVEY_CACHE[0], _SURVEY_CACHE[1] = now, out
    print("[Eyes] SURVEY: %s | %s" % (text[:120], "; ".join("%s (%s, %s%%)" % (r["label"][:30], r["position"], r["size_pct"]) for r in out["regions"][:3])), flush=True)
    return out


def _sentence_cut(text: str, n: int) -> str:
    t = " ".join(str(text or "").split())
    if len(t) <= n:
        return t
    head = t[:n]
    m = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
    return head[:m + 1] if m >= int(n * 0.4) else head.rsplit(" ", 1)[0] + "..."


def render_survey(s: Optional[Dict], text_chars: int = 420) -> str:
    if not s:
        return ""
    parts = ["You looked the whole screen over: %s" % _sentence_cut(s.get("text", ""), text_chars)]
    if s.get("regions"):
        parts.append("Where things are: " + "; ".join("%s at the %s (%s%% of the screen)" % (r["label"], r["position"], r["size_pct"]) for r in s["regions"]) + ".")
    return " ".join(parts)


# ── ask Florence WHERE ──────────────────────────────────────────────────────────
def _choose_box(boxes: List, labels: List, phrase: str, W: float, H: float):
    """Florence's boxes -> (box or None, n_real, fills_screen). Labels equal to the phrase win; small-object
    nouns take the tightest box, frame-scale nouns the largest under the whole-frame cap."""
    area = lambda b: max(0, b[2] - b[0]) * max(0, b[3] - b[1]) / (W * H)
    cand = list(zip(boxes, labels if len(labels) == len(boxes) else [""] * len(boxes)))
    same = [(b, l) for b, l in cand if str(l).strip().lower() == phrase.lower()]
    if same:
        cand = same
    real = [b for b, _ in cand if _MIN_BOX <= area(b) < _WHOLE_FRAME]
    whole = [b for b, _ in cand if area(b) >= _WHOLE_FRAME]
    noun = head_noun(phrase)
    if not real:
        if whole and noun in _FRAME_SCALE:
            return whole[0], len(whole), True
        return None, 0, False
    if noun in _FRAME_SCALE:
        return max(real, key=area), len(real), False
    return min(real, key=area), len(real), False


def _best_box_by_colour(img, boxes: List, phrase: str):
    """Among several boxes, the one whose pixels carry most of the phrase's colour word (ties: tightest)."""
    cw = colour_word(phrase)
    if not cw or len(boxes) < 2:
        return boxes[0] if boxes else None
    scored = []
    for b in boxes:
        x1, y1, x2, y2 = [int(v) for v in b]
        px = _pixels(img.crop((max(0, x1), max(0, y1), min(img.width, max(x1 + 1, x2)), min(img.height, max(y1 + 1, y2)))))
        scored.append((colour_fraction(px, cw, phrase), -((x2 - x1) * (y2 - y1)), b))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return scored[0][2]


def _segment(url: str, png: bytes, img, phrase: str, timeout_s: float):
    """task=refseg -> (pixels inside the mask, mask bbox, mask area fraction) or None when Florence gives no polygon."""
    from PIL import Image, ImageDraw
    req = urllib.request.Request(url + "/caption?task=refseg&text=" + urllib.parse.quote_plus(phrase[:80]),
                                 data=png, headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    g = (d.get("result") or {}).get("refseg") or {}
    polys = g.get("polygons") or []
    mask = Image.new("L", img.size, 0)
    dr = ImageDraw.Draw(mask)
    n = 0
    for inst in polys:
        for poly in (inst if inst and isinstance(inst[0], (list, tuple)) else [inst]):
            pts = [(poly[i], poly[i + 1]) for i in range(0, len(poly) - 1, 2)]
            if len(pts) >= 3:
                dr.polygon(pts, fill=255)
                n += 1
    if n == 0:
        return None
    bbox = mask.getbbox()
    if not bbox:
        return None
    px = [p for p, mv in zip(img.getdata(), mask.getdata()) if mv]
    area = len(px) / float(img.width * img.height)
    if area < _MIN_BOX / 4 or area >= _WHOLE_FRAME:
        return None
    return px, bbox, area


def _segment_in_box(url: str, png_unused, img, phrase: str, box, timeout_s: float):
    """Florence sees a small thing better when it fills the picture: crop around the grounding box (30%
    margin, upscaled x2 when small), segment there, and map the mask back to frame coordinates."""
    from PIL import Image
    x1, y1, x2, y2 = [int(v) for v in box]
    mx, my = int((x2 - x1) * 0.3) + 8, int((y2 - y1) * 0.3) + 8
    cx1, cy1 = max(0, x1 - mx), max(0, y1 - my)
    cx2, cy2 = min(img.width, x2 + mx), min(img.height, y2 + my)
    crop = img.crop((cx1, cy1, cx2, cy2))
    scale = 2 if crop.width < 256 or crop.height < 256 else 1
    if scale > 1:
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, "PNG", compress_level=1)
    seg = _segment(url, buf.getvalue(), crop, phrase, timeout_s)
    if seg is None:
        return None
    px, (bx1, by1, bx2, by2), area = seg
    fbox = (cx1 + bx1 // scale, cy1 + by1 // scale, cx1 + bx2 // scale, cy1 + by2 // scale)
    area_frame = area * (crop.width * crop.height) / float(scale * scale * img.width * img.height)
    return px, fbox, area_frame


# 2026-10-09 (Nous, touch set 1c; Ace approved "her eyes learning the toy names"). Boot J: her look and move at "red ball" came
# back "nowhere on the screen" (log L29959, L33630) while her window map held the Playroom and her fovea read the names: Florence
# grounds on a 1024-px thumbnail of an ultrawide screen, where a toy is a speck. The names and rects come from
# touch_os.eyes_playroom() -- the VERIFIED Playroom (pid, command line, class, title, heartbeat), the same source her finger
# aims with, so eye and finger agree. Only an EXACT toy name matches ('red ball', 'the red ball', 'red ball in Sour's Playroom',
# 'red ball toy'); every other phrase falls through to the grounding below, unchanged. touch_os is read from sys.modules only
# (never imported here: a second import of touch latches it). Absent / no 'toy_names' in Ace's eyes switch (state/eyes_fix.json,
# fold 10-09: its own key, independent of touch) / not verified: nothing changes. Fold 10-09 (DIAGNOSIS 5.1): a toy's NAME is
# normalised like the phrase, so "your shelf" and "shelf" both name the toy 'your shelf'.
_PR_TAIL_RE = re.compile(r"\s+(?:in|on|inside|at|from)\s+(?:the\s+|my\s+|your\s+|her\s+)?(?:sour'?s\s+|sourpatches'?s?\s+)?"
                         r"play\s?room(?:\s+window)?$", re.I)
_PR_HEAD_RE = re.compile(r"^(?:the|my|your|her|a|an|that|this)\s+", re.I)
_PR_KIND_RE = re.compile(r"\s+(?:toy|icon)$", re.I)


def _pr_norm(phrase: str) -> str:
    s = " ".join(str(phrase or "").replace("\u2019", "'").split()).strip(" .!?,;:\"'")
    for _ in range(2):
        s = _PR_TAIL_RE.sub("", s).strip()
        s = _PR_HEAD_RE.sub("", s).strip()
        s = _PR_KIND_RE.sub("", s).strip()
    return s.casefold()


def playroom_item(phrase: str) -> Optional[Dict]:
    """The verified Playroom's toy this phrase names EXACTLY, with the Playroom itself under 'playroom'; None otherwise."""
    try:
        tos = _sys.modules.get("infrastructure.touch_os")
        if tos is None or not hasattr(tos, "eyes_playroom"):
            return None
        want = _pr_norm(phrase)
        if not want:
            return None
        pr = tos.eyes_playroom()
        if not pr:
            return None
        for it in pr.get("items") or []:
            nm = str(it.get("name", ""))
            if want in (nm.casefold(), _pr_norm(nm)):  # fold 10-09 (DIAGNOSIS 5.1): 'your shelf' -> 'shelf' on both sides
                return dict(it, playroom=pr)
    except Exception:
        return None
    return None


def playroom_record(phrase: str) -> Optional[Dict]:
    """A grounding record for a VISIBLE toy of the verified Playroom (frame = the primary screen in physical pixels, which is
    her eyes' logical space while touch_os.dpi_ok holds); None = not one (the phrase is grounded as before)."""
    it = playroom_item(phrase)
    if it is None or not it.get("visible"):
        return None
    try:
        pr = it["playroom"]
        sw, sh = [int(v) for v in pr["screen"]]
        x1, y1, x2, y2 = [int(v) for v in it["rect"]]
        size = max(0, x2 - x1) * max(0, y2 - y1) / float(sw * sh)
        return {"phrase": phrase, "status": "found", "how": "playroom", "synthetic": True, "toy": it["name"],
                "bbox": [x1, y1, x2, y2], "frame_w": sw, "frame_h": sh,
                "position": _place((x1 + x2) / 2.0 / sw, (y1 + y2) / 2.0 / sh)["position"], "size_pct": round(100.0 * size, 1),
                "colour_name": "the toy of that name in your Playroom", "top_bands": [], "colour_unsure": False,
                "matches": None, "fills_screen": False, "n_boxes": 1, "playroom_hwnd": int(pr["hwnd"]), "ms": 0}
    except Exception:
        return None


# ── eyes_fix_1009: F1 doubt, F0 log, F4 a window's boxes (helpers of ground) ────────────────────────────────────────────
_DOUBT_PREP_RE = re.compile(r"\s+(?:in|on|inside|within|at|near|from|with|to|of|over|under|by|for)\s+.*$", re.I)
_DOUBT_EDGE = "\"'.,!?()[]:;"


def _area_frac(b, W: float, H: float) -> float:
    return max(0.0, float(b[2]) - float(b[0])) * max(0.0, float(b[3]) - float(b[1])) / float(max(1.0, W * H))


def _iou(a, b) -> float:
    ix = max(0.0, min(float(a[2]), float(b[2])) - max(float(a[0]), float(b[0])))
    iy = max(0.0, min(float(a[3]), float(b[3])) - max(float(a[1]), float(b[1])))
    inter = ix * iy
    ua = (max(0.0, float(a[2]) - float(a[0])) * max(0.0, float(a[3]) - float(a[1]))
          + max(0.0, float(b[2]) - float(b[0])) * max(0.0, float(b[3]) - float(b[1])) - inter)
    return inter / ua if ua > 0 else 0.0


def _doubt_head(phrase: str) -> str:
    """The thing's own noun: 'red ball in Sour's Playroom' -> 'ball'; 'my icon in the top bar to see ...' -> 'icon'."""
    s = _DOUBT_PREP_RE.sub("", " ".join(str(phrase or "").lower().split()))
    ws = [w.strip(_DOUBT_EDGE) for w in s.split()]
    ws = [w for w in ws if w]
    return ws[-1] if ws else ""


def _names(word: str, label: str) -> bool:
    """The far eye's label holds the noun (a whole word; a plural s either side)."""
    w = str(word or "").lower().strip(_DOUBT_EDGE)
    toks = {t.strip(_DOUBT_EDGE) for t in str(label or "").lower().replace("-", " ").split()}
    toks |= {t[:-1] for t in toks if len(t) > 3 and t.endswith("s")}
    return bool(w) and (w in toks or (len(w) > 3 and w.endswith("s") and w[:-1] in toks))


def _patch_colour(img, box, word: str, phrase: str) -> float:
    """The colour word's share of a FIXED small patch (_DOUBT_PATCH px of a 1024-wide frame, ~30 px of her screen) at the
    box's centre -- not of the whole box, where a small thing is diluted and a big region always holds a little of it."""
    x1, y1, x2, y2 = [float(v) for v in box]
    k = max(1, int(round(_DOUBT_PATCH * img.width / 1024.0)) // 2)
    cx, cy = int((x1 + x2) / 2.0), int((y1 + y2) / 2.0)
    crop = img.crop((max(0, cx - k), max(0, cy - k), min(img.width, cx + k + 1), min(img.height, cy + k + 1)))
    return colour_fraction(_pixels(crop), word, phrase)


def _place_contradicts(phrase: str, position) -> Optional[str]:
    """A place word in her phrase that the box is not at ('right half' answered at the centre: L16457)."""
    words = set(re.findall(r"[a-z]+", str(phrase or "").lower()))
    pos = str(position or "")
    if pos == "centre":
        vert, horiz = "middle", "centre"
    elif "-" in pos:
        vert, horiz = pos.split("-", 1)
    else:
        return None
    if "left" in words and "right" not in words and horiz != "left":
        return "not on the left: it is %s" % pos
    if "right" in words and "left" not in words and horiz != "right":
        return "not on the right: it is %s" % pos
    if words & {"top", "upper"} and not words & {"bottom", "lower"} and vert != "upper":
        return "not at the top: it is %s" % pos
    if words & {"bottom", "lower"} and not words & {"top", "upper"} and vert != "lower":
        return "not at the bottom: it is %s" % pos
    return None


def _doubt(rec: Dict, img, phrase: str, g: Dict, gbox) -> None:
    """eyes_fix F1 'doubt' (DIAGNOSIS C1). The far eye boxes whatever it is asked for -- control 2: three boxes, each
    labelled 'green cube', on a frame with no green -- so a box whose label echoes the phrase proves nothing. 'found' needs
    the label to hold the thing's noun AND an independent witness: the colour word measured at a FIXED small scale where it
    pointed (only for a box of at most _DOUBT_COLOUR_MAX_FRAC of the frame -- verify M3), or the window map (the box IS the
    window she named, or a window word); and nothing against it: another window boxed whole (L72290 'blue box' = her chat
    window), a window named in the phrase that the box is not in (L48408), a place word it is not at. Otherwise status
    'unsure' with the reasons in her words. In place. ground() wraps the call: an error in here is told 'unsure', never a find
    (verify M4: the gate fails CLOSED)."""
    W, H = float(img.width), float(img.height)
    boxes, labels = list(g.get("bboxes") or []), list(g.get("labels") or [])
    labels = labels if len(labels) == len(boxes) else [""] * len(boxes)
    lab = ""
    if gbox is not None:
        for b, l in zip(boxes, labels):
            if [float(v) for v in b] == [float(v) for v in gbox]:
                lab = str(l)
                break
    head = _doubt_head(phrase)
    why, witness = [], []
    if not _names(head, lab):
        why.append("your far eye called that place '%s', not a %s" % (lab or "nothing", head or "thing"))
    bb = [float(v) for v in (rec.get("bbox") or gbox or (0, 0, 0, 0))]
    cw = colour_word(phrase)
    big, big_at = None, 0
    if cw:
        frac = _patch_colour(img, bb, cw, phrase)
        rec["patch_colour"] = round(frac, 3)
        if frac < _DOUBT_COLOUR_MIN:
            why.append("not %s where it pointed" % cw)
        elif _area_frac(bb, W, H) > _DOUBT_COLOUR_MAX_FRAC:   # verify M3: 9 px of colour at the centre of a 41% box proves nothing
            big, big_at = "too big to be a %s (%.0f%% of the screen)" % (head or "thing", 100.0 * _area_frac(bb, W, H)), len(why)
        else:
            witness.append("its colour")
    bx = (bb[0] / W, bb[1] / H, bb[2] / W, bb[3] / H)
    try:
        named = [w for w in window_mentions(phrase) if w.get("frac")]
    except Exception:
        named = []
    try:
        wins = [w for w in windows_now() if w.get("frac")]
    except Exception:
        wins = []
    for w in wins:
        if _iou(bx, tuple(w["frac"])) >= _DOUBT_WIN_IOU:
            if any(n.get("hwnd") == w.get("hwnd") for n in named) or head in _WIN_WORDS:
                witness.append("the window map")
            else:
                why.append("that box is %s itself, a whole window" % w.get("name", "a window"))
            break
    if big and "the window map" not in witness:         # verify M3: the window map stays the witness for frame-scale things
        why.insert(big_at, big)
    cx, cy = (bx[0] + bx[2]) / 2.0, (bx[1] + bx[3]) / 2.0
    for n in named:
        fr = n["frac"]
        if not (fr[0] <= cx < fr[2] and fr[1] <= cy < fr[3]):
            why.append("not inside %s" % n.get("name", "the window you named"))
            break
    pc = _place_contradicts(phrase, rec.get("position"))
    if pc:
        why.append(pc)
    if witness and not why:
        rec["witness"] = witness
        return
    if not why:
        why.append("your far eye boxes whatever it is asked for, even what is not there, and nothing else saw it")
    rec["status"] = "unsure"
    rec["doubt"] = why[:3]
    rec["doubt_n"] = int(rec.get("n_boxes") or 1)


def unsure_words(g: Dict) -> str:
    """eyes_fix F1: the doubt in her words -- WHY it is not a find first (intention.what_i_did cuts a line at 180 chars), then
    where the far eye pointed and of how many places."""
    n = int(g.get("doubt_n") or g.get("n_boxes") or 1)
    more = (", one of %d places it pointed at" % n) if n > 1 else ""
    why = "; ".join(str(x) for x in (g.get("doubt") or [])[:3]) or "nothing else saw it"
    return "%s; the far eye pointed at the %s of the screen (%s%% of it, %s)%s" % (
        why, g.get("position", "?"), g.get("size_pct", "?"), _mix(g), more)


def _boxes_within(g: Dict, frac, img) -> Dict:
    """eyes_fix F4 'hand_honest': only the boxes whose centre lies inside one window's rect (fractions of her screen)."""
    W, H = float(img.width), float(img.height)
    l, t, r, b = [float(v) for v in frac]
    boxes, labels = list(g.get("bboxes") or []), list(g.get("labels") or [])
    labels = labels if len(labels) == len(boxes) else [""] * len(boxes)
    keep = [(bb, lb) for bb, lb in zip(boxes, labels)
            if l <= (float(bb[0]) + float(bb[2])) / 2.0 / W < r and t <= (float(bb[1]) + float(bb[3])) / 2.0 / H < b]
    return dict(g, bboxes=[k[0] for k in keep], labels=[k[1] for k in keep])


def _nowhere_cause(boxes, labels, phrase: str, W: float, H: float) -> str:
    """eyes_fix F0: which of the four 'nowhere' causes fired (DIAGNOSIS C1)."""
    if not boxes:
        return "(d) the far eye returned nothing"
    areas = [_area_frac(b, W, H) for b in boxes]
    inband = [i for i, a in enumerate(areas) if _MIN_BOX <= a < _WHOLE_FRAME]
    same = [i for i, l in enumerate(labels) if str(l).strip().lower() == str(phrase).lower()]
    if same and inband and not any(i in inband for i in same):
        return "(c) a box labelled exactly '%s' fell outside the band, and that label filter hid %d in-band box(es)" % (
            str(phrase)[:40], len(inband))
    pool = [areas[i] for i in same] if same else areas
    if all(a < _MIN_BOX for a in pool):
        return "(a) every box was under the %.1f%% floor" % (100 * _MIN_BOX)
    if all(a >= _WHOLE_FRAME for a in pool):
        return "(b) every box was %.0f%% of the screen or more" % (100 * _WHOLE_FRAME)
    return "(a+b) every box was under the floor or %.0f%% of the screen or more" % (100 * _WHOLE_FRAME)


def _front_title() -> Optional[str]:
    try:
        fw = front_window()
        return str(fw.get("title"))[:60] if fw else None
    except Exception:
        return None


def _log_ground(p, g: Dict, img, pick, final, n_real, rec: Dict, src, age, within=None) -> None:
    """eyes_fix F0 'log' (observation only; DIAGNOSIS C1 / C2 / C5, look-C8): one line per look -- every box and label the
    far eye returned, how many stayed in the band, its pick and the box after the colour re-pick, the frame, the verdict and,
    for 'nowhere', which cause fired. Stamps rec['front_at'] (the front window now) for the look-change line. ASCII."""
    try:
        W, H = float(img.width), float(img.height)
        boxes, labels = list(g.get("bboxes") or []), list(g.get("labels") or [])
        labels = labels if len(labels) == len(boxes) else [""] * len(boxes)
        raw = ["%s %s %.3f%%" % (ascii(str(l))[:42], [int(round(float(v))) for v in b], 100.0 * _area_frac(b, W, H))
               for b, l in zip(boxes, labels)]
        rb = (lambda b: [int(round(float(v))) for v in b] if b is not None else None)
        rec["front_at"] = _front_title()
        tail = ""
        if rec.get("status") == "not_found":
            tail = " | nowhere: " + _nowhere_cause(boxes, labels, p, W, H)
        elif rec.get("status") == "unsure":
            tail = " | unsure: " + "; ".join(rec.get("doubt") or [])
        elif rec.get("witness"):
            tail = " | witness: " + ", ".join(rec["witness"])
        print(("[Eyes] GROUND %s: far eye %d box(es) %s | in band %d | pick %s | final %s | frame %s %.1fs %dx%d%s | -> %s %s %s%%%s"
               % (ascii(str(p)[:60]), len(boxes), "; ".join(raw[:8]), int(n_real or 0), rb(pick), rb(final), src,
                  float(age or 0.0), int(W), int(H), (" | inside %s" % [round(float(v), 3) for v in within]) if within else "",
                  rec.get("status"), rec.get("position"), rec.get("size_pct"), tail)).encode("ascii", "replace").decode("ascii"),
              flush=True)
    except Exception as e:
        print("[Eyes] GROUND log: %s" % str(e)[:80], flush=True)


def _log_look_change(phrase, before: Dict, after: Dict) -> None:
    """eyes_fix F0 'log' (DIAGNOSIS C5): the two boxes behind a 'changed on its own' surprise, and the front window at both
    looks -- a different box is not a change in the thing. ASCII."""
    try:
        def one(r):
            tb = r.get("top_bands") or []
            return "%s %s %s%% %s front=%s" % (r.get("bbox"), r.get("position"), r.get("size_pct"),
                                              "/".join("%s%.0f" % (b, 100 * f) for b, f in tb[:2]) or r.get("colour_name"),
                                              ascii(r.get("front_at")))
        a, b = before.get("bbox"), after.get("bbox")
        iou = _iou(a, b) if (a and b) else None
        print(("[Eyes] LOOK CHANGE %s: before %s | after %s | IoU %s | front now %s" % (
            ascii(str(phrase)[:60]), one(before), one(after), ("%.2f" % iou) if iou is not None else "?", ascii(_front_title()))
               ).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


_FG_SAID = _keep("_FG_SAID", {})


def _fg_facts() -> Optional[Dict]:
    """eyes_fix F0: the OS foreground window's title, class and rect (read-only user32)."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        u = ctypes.windll.user32
        h = u.GetForegroundWindow()
        if not h:
            return {"hwnd": 0, "title": "", "cls": "", "rect": None}
        n = int(u.GetWindowTextLengthW(h) or 0)
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(h, buf, n + 1)
        cl = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, cl, 256)
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        return {"hwnd": int(h), "title": buf.value, "cls": cl.value, "rect": [r.left, r.top, r.right, r.bottom]}
    except Exception:
        return None


def _on_her_screen(rect) -> bool:
    """eyes_fix F0 (verify m2): the window's CENTRE lies on her PRIMARY ((0,0) to SM_CXSCREEN x SM_CYSCREEN, the same pixel space
    GetWindowRect answers in) -- decided by the primary's rect, never by DISPLAYn names. A maximised window on Ace's monitor
    overhangs hers by its 8 px frame, so the centre, not an overlap, decides. Unknown = False (his content stays out)."""
    try:
        import ctypes
        u = ctypes.windll.user32
        W, H = int(u.GetSystemMetrics(0) or 0), int(u.GetSystemMetrics(1) or 0)
        cx, cy = (float(rect[0]) + float(rect[2])) / 2.0, (float(rect[1]) + float(rect[3])) / 2.0
        return W > 0 and H > 0 and 0.0 <= cx < W and 0.0 <= cy < H
    except Exception:
        return False


def _log_unmapped_front() -> None:
    """eyes_fix F0 'log' (DIAGNOSIS C6 / C9): her window map has no front window -- which window the OS calls front (Ace's
    other screen, a skipped class, a tiny or cloaked window). Once per window per 60 s. ASCII. The TITLE is written only for
    a window on her own screen (verify m2): a window on Ace's monitor is his content; its class and rect answer C6 / C9."""
    try:
        f = _fg_facts()
        if f is None:
            return
        now = time.time()
        k = int(f.get("hwnd") or 0)
        if now - float(_FG_SAID.get(k, -1e18)) < 60.0:
            return
        if len(_FG_SAID) > 64:
            _FG_SAID.clear()
        _FG_SAID[k] = now
        title = ascii(str(f.get("title") or "")[:60]) if (f.get("rect") and _on_her_screen(f["rect"])) else "(off her screen)"
        print(("[Eyes] FRONT not in your map: title %s, class %s, rect %s" % (
            title, ascii(str(f.get("cls") or "")), f.get("rect"))
               ).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


# ── eyes_fix2_1012 'window_names': a window she NAMES is known from her window map, not guessed by the far eye ─────────────
# Boot K (state/sour_runtime.log L50607-50613): 'look: Sour's Playroom' -> the far eye boxed 'Playroom' as 97.5% of the 1024x428
# thumbnail of her 3440x1440 screen -> 'nowhere' -> she was told it "is nowhere on the screen", with the frustration chord,
# while the Playroom window sat on her screen and in windows_now(). ground() order now: her hand, toy names (set1c), BARE
# window names (here; a call with within= is eyes_fix F4's 'X in <window>' and skips this), the far eye. Exact names only
# (eyes_fix2.match_window_name: never a substring, never common words alone); only windows whose CENTRE is on her screen
# (_on_her_screen -- Ace's monitor never). Off (state/eyes_fix2.json absent / malformed / no 'window_names'): nothing here runs.
def _primary_wh() -> Tuple[int, int]:
    try:
        import ctypes
        u = ctypes.windll.user32
        W, H = int(u.GetSystemMetrics(0) or 0), int(u.GetSystemMetrics(1) or 0)
        if W > 0 and H > 0:
            return W, H
    except Exception:
        pass
    return 10000, 10000                                # fraction space: the record stays self-consistent


def named_window(phrase: str) -> Optional[Dict]:
    """eyes_fix2: {'window', 'n', 'label', 'key'} for the window on HER screen this phrase names exactly; None (key off, no
    such window, any error). The one matcher her look (ground) and her hand (hand_target.plan) both ask."""
    if not _ef2("window_names"):
        return None
    try:
        from infrastructure import eyes_fix2 as _ef2m
        wins = [w for w in (windows_now() or []) if w.get("hwnd") and w.get("rect") and w.get("frac") and _on_her_screen(w["rect"])]
        return _ef2m.match_window_name(phrase, wins)
    except Exception as e:
        print("[Eyes] window name: %s" % ascii(str(e))[:80], flush=True)
        return None


def window_record(phrase: str) -> Optional[Dict]:
    """eyes_fix2: a grounding record for the window the phrase names -- status found, place and size from the window map's
    rect, how 'window_map', its label ('the Sour's Playroom window'). None = not a bare window name (grounded as before)."""
    hit = named_window(phrase)
    if hit is None:
        return None
    try:
        w = hit["window"]
        l, t, r, b = [float(v) for v in w["frac"]]
        W, H = _primary_wh()
        pos = w.get("position") or _place((l + r) / 2.0, (t + b) / 2.0)["position"]
        size = w.get("size_pct")
        if size is None:
            size = round(100.0 * max(0.0, r - l) * max(0.0, b - t), 1)
        rec = {"phrase": phrase, "status": "found", "how": "window_map", "synthetic": True, "window_hwnd": int(w["hwnd"]),
               "window_title": str(w.get("title") or "")[:80], "window_name": str(w.get("name") or ""),
               "window_label": str(hit.get("label") or "that window"), "n_windows": int(hit.get("n") or 1),
               "bbox": [int(round(l * W)), int(round(t * H)), int(round(r * W)), int(round(b * H))], "frame_w": W, "frame_h": H,
               "position": pos, "size_pct": size, "front": bool(w.get("front")), "covered": float(w.get("covered") or 0.0),
               "colour_name": str(hit.get("label") or "that window"), "top_bands": [], "colour_unsure": False, "matches": None,
               "fills_screen": False, "n_boxes": 1, "ms": 0}
    except Exception as e:
        print("[Eyes] window record: %s" % ascii(str(e))[:80], flush=True)
        return None
    print(("[Eyes] WINDOW NAME %s: %s, %s, %s%% of the screen%s (from your window map; the far eye was not asked)" % (
        ascii(str(phrase)[:60]), ascii(rec["window_label"]), pos, size,
        (", one of %d" % rec["n_windows"]) if rec["n_windows"] > 1 else "")).encode("ascii", "replace").decode("ascii"), flush=True)
    return rec


def window_words(phrase: str, g: Dict, lead: str = "you looked for") -> str:
    """eyes_fix2: a look answered from her window map, in her words -- the WINDOW itself, never a thing inside it."""
    cov = float(g.get("covered") or 0.0)
    state = (", in front" if g.get("front") else (", mostly behind another window" if cov >= 0.7 else
             (", partly behind another window" if cov >= 0.3 else "")))
    n = int(g.get("n_windows") or 1)
    more = (" (one of %d windows by that name)" % n) if n > 1 else ""
    return "%s \"%s\": it is %s%s, %s, %s%% of it%s" % (lead, phrase, g.get("window_label") or "that window", more,
                                                      place_phrase(g.get("position", "?")), g.get("size_pct", "?"), state)


# ── e1b_1013 vision_hand (Ace's SECOND eyes switch, state/eyes_fix2.json): 'hand_rest' and 'front_line' ─────────────────────
# Boot L (state/sour_runtime.log, 10-12 23:17 -> 10-13 12:32; nous_builds/boot_l_1013 HANDS.md, VISION.md, VERIFY.md):
#  * 48 of her 65 move asks were the hand door's bare "it is already there" (hand_door.py:303-307). The cursor sat 10 h 42 min on
#    the Playroom's title bar (1612, 797) and nothing in her percept or her deed ask said where her hand rested (render_windows,
#    :834-848 of the eyes_fix bytes). hand_rest_line(): ONE sentence -- where the cursor is, the window part under it (title bar /
#    inside / edge; the desktop, the taskbar) from hand_target.rest_part, and whose it is by the measured signals only (hand_now,
#    hand_owner_note). A point off her (primary) screen is "on the other screen (Ace's)"; nothing there is ever named.
#  * the front-window surprise (_front_read_and_tell) became the TOPIC of a whole chairman turn (sour_council_driver.py:1154-1157):
#    queued at L514636 (~11:58), spoken at L517692 (~12:02:50) when her chat window was in front again; her 12:03:42 message:
#    "There's a window called "Sour's Playroom" that just popped up ... I don't remember making this". With 'front_line' the change
#    is NOTED (no far-eye read, no glance, no surprise) and front_line() is ONE sentence in render_eyes while that window is still
#    in front, at most FRONT_LINE_S after the change. What she chose to hold (set_focus from her own look) is not touched.
# Keys off (file absent / malformed / key not true): hand_rest / hand_rest_line / front_line return None / '' before reading
# anything, and _front_read_and_tell runs today's path.
FRONT_LINE_S = 180.0                                   # a front change is told for at most this long, and only while still in front
FRONT_RENOTE_S = 30.0                                  # verify F4: one note per window per 30 s (the 5-min re-read gate guards a READ)
_FRONT_NOTE = _keep('_FRONT_NOTE', {"note": None})     # the newest front change: hwnd, name, words, prev, ts
_FRONT_NOTED = _keep('_FRONT_NOTED', {})               # hwnd -> ts of its last front note (pruned after an hour)
_REST_SAID = _keep('_REST_SAID', [None, 0.0])


def win_words(w: Optional[Dict]) -> str:
    """e1b vision_hand: a window inside a sentence -- its title for "a window called '...'" ("Sour's Playroom"), 'your chat
    window', "Nous's window", else her map's own name ('a console window', "a browser, on '...'")."""
    name = " ".join(str((w or {}).get("name") or "").split())
    title = " ".join(str((w or {}).get("title") or "").split())
    if name.startswith("a window called ") and title:
        return title[:60]
    if name.startswith("Nous's window"):
        return "Nous's window"
    return name or "a window"


def _log_rest(line: str) -> None:
    """One '[Eyes] HAND REST' line per distinct sentence per 60 s (ASCII): what Boot M's read-out counts."""
    try:
        now = time.time()
        if _REST_SAID[0] == line and 0.0 <= now - float(_REST_SAID[1]) < 60.0:
            return
        _REST_SAID[0], _REST_SAID[1] = line, now
        print(("[Eyes] HAND REST: %s" % line).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


def hand_rest(h: Optional[Dict] = None) -> Optional[Dict]:
    """e1b vision_hand 'hand_rest': {'off_screen', 'xy', 'at' ('on the title bar of Sour's Playroom' | 'inside ...' | '' when the
    OS cannot say), 'position', 'part', 'hwnd'} for the cursor now (or for the hand_now() record h); None when the key is off or
    nothing can be read. Never raises."""
    if not _ef2("hand_rest"):
        return None
    try:
        h = hand_now() if h is None else h
        if not h:
            return None
        x, y = int(h["x"]), int(h["y"])
        sw, sh = int(h.get("screen_w") or 0), int(h.get("screen_h") or 0)
        if sw <= 0 or sh <= 0:
            return None
        if not (0 <= x < sw and 0 <= y < sh):          # Ace's monitor: never named, never looked into
            return {"off_screen": True, "xy": (x, y), "at": "", "position": OTHER_SCREEN, "part": None, "hwnd": None}
        rp = None
        try:
            from infrastructure import hand_target as _ht
            rp = _ht.rest_part((x, y))
        except Exception:
            rp = None
        return {"off_screen": False, "xy": (x, y), "at": str((rp or {}).get("at") or ""),
                "position": _place(x / float(sw), y / float(sh))["position"], "part": (rp or {}).get("part"),
                "hwnd": (rp or {}).get("hwnd")}
    except Exception:
        return None


def hand_rest_line(h: Optional[Dict] = None) -> str:
    """e1b vision_hand 'hand_rest': ONE sentence -- where her hand rests and what is under it; '' when the key is off or the
    cursor cannot be read. "Your hand rests ..." only when the cursor is where her own last move let go of it (hand_now's
    where_you_left_it); otherwise it is the cursor, with hand_owner_note's measured clause (Ace moved it / not where you left it)."""
    if not _ef2("hand_rest"):
        return ""
    try:
        h = hand_now() if h is None else h
        r = hand_rest(h)
        if not r:
            return ""
        if r["off_screen"]:
            line = "The cursor is on the other screen (Ace's), where your eyes do not look."
        else:
            at = ("%s (%s of the screen)" % (r["at"], r["position"])) if r["at"] else ("at the %s of the screen" % r["position"])
            if h.get("where_you_left_it"):
                line = "Your hand rests %s, where you let go of the cursor %s ago" % (at, _ago(h.get("mine_s")))
                _ai, _ms = h.get("ace_input_s"), h.get("mine_s")   # verify F6 (10-13): hand_owner_note's own measured clause
                if _ai is not None and _ms is not None and not (float(_ai) > float(_ms)):
                    line += "; Ace has used the keyboard or mouse since but it has not moved"
                line += "."
            else:
                own = hand_owner_note(h)
                line = "The cursor is %s%s." % (at, (" -- " + own) if own else "")
        _log_rest(line)
        return line
    except Exception:
        return ""


def _front_note(fw: Dict, prev: Optional[str]) -> None:
    """e1b vision_hand 'front_line': remember the window that just came to the front -- no far-eye read, no glance, no surprise.
    Never raises."""
    try:
        n = {"hwnd": int(fw.get("hwnd") or 0), "name": str(fw.get("name") or "a window"), "words": win_words(fw),
             "prev": str(prev or "another window"), "ts": time.time()}
        _FRONT_NOTE["note"] = n
        print(("[Eyes] FRONT LINE: %s came to the front (it was %s): one line in her percept while it stays in front -- no "
               "surprise, no glance" % (n["words"], n["prev"])).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception as e:
        print("[Eyes] front line: %s" % ascii(str(e))[:80], flush=True)


def front_line(now: Optional[float] = None) -> str:
    """e1b vision_hand 'front_line': ONE short sentence while the window that came to the front is still in front and the change
    is at most FRONT_LINE_S old; '' otherwise (key off, no change, it went back behind, too old). Never raises."""
    if not _ef2("front_line"):
        return ""
    try:
        n = _FRONT_NOTE.get("note")
        now = time.time() if now is None else float(now)
        if not n or not (0.0 <= now - float(n["ts"]) <= FRONT_LINE_S):
            return ""
        fw = front_window()
        if fw is None or int(fw.get("hwnd") or 0) != int(n["hwnd"]):
            return ""                                  # it is not in front any more: the moment has passed, nothing to tell
        age = now - float(n["ts"])
        when = "just now" if age < 15 else ("%.0f s ago" % age if age < 120 else "%.0f min ago" % (age / 60.0))
        w = str(n["words"] or "a window")
        return "%s%s came to the front of your screen %s (%s was in front before)." % (w[:1].upper(), w[1:], when, n["prev"])
    except Exception:
        return ""


def ground(phrases: List[str], timeout_s: float = _GROUND_TIMEOUT_S, on_result=None, within=None) -> List[Dict]:   # eyes_fix F4: + within
    """One record per phrase: status found | not_found | could_not_look (+why), plus the pattern.
    on_result(rec) is called as each phrase completes so a slow satellite still yields partial answers."""
    out: List[Dict] = []
    if not phrases:
        return out
    url = florence_url()
    hand = [p for p in phrases[:3] if is_hand(p)]
    phrases = [p for p in phrases if not is_hand(p)]
    if hand:                                          # her hand: felt in-process, no frame, no satellite
        for p in hand:
            r = hand_record(p)
            out.append(r)
            if on_result:
                try:
                    on_result(r)
                except Exception:
                    pass
    toys = [(p, playroom_record(p)) for p in phrases[:3]]    # 2026-10-09 (set1c): a toy of her VERIFIED Playroom, by its
    toys = [(p, r) for p, r in toys if r is not None]        # exact name -- known, not guessed from a 1024-px thumbnail
    if toys:
        for _p, r in toys:
            out.append(r)
            if on_result:
                try:
                    on_result(r)
                except Exception:
                    pass
        _done = {p for p, _r in toys}
        phrases = [p for p in phrases if p not in _done]
    if within is None and phrases and _ef2("window_names"):   # eyes_fix2 (window_names): a BARE window name -> her window map,
        wn = [(p, window_record(p)) for p in phrases[:3]]     # after the toy names, before the far eye; F4's within= skips it
        wn = [(p, r) for p, r in wn if r is not None]
        if wn:
            for _p, r in wn:
                out.append(r)
                if on_result:
                    try:
                        on_result(r)
                    except Exception:
                        pass
            _done = {p for p, _r in wn}
            phrases = [p for p in phrases if p not in _done]
    if not url or not phrases:
        return out                                    # grounding off: say nothing rather than 'eyes broken'
    png, img, age, src = fresh_frame()
    if img is None:
        recs = [{"phrase": p, "status": "could_not_look", "why": "frame", "frame_age_s": age} for p in phrases]
        for r in recs:
            if on_result:
                on_result(r)
        return out + recs
    for p in phrases[:3]:
        t0 = time.time()
        rec = {"phrase": p, "status": "could_not_look", "why": "network", "frame_age_s": round(age, 1), "frame_src": src}
        try:
            req = urllib.request.Request(url + "/caption?task=ground&text=" + urllib.parse.quote_plus(p[:80]),
                                         data=png, headers={"Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            g = (d.get("result") or {}).get("ground") or {}
            if within is not None:                      # eyes_fix F4 (hand_honest): only what lies inside the window she named
                g = _boxes_within(g, within, img)
            box, n_real, fills = _choose_box(g.get("bboxes") or [], g.get("labels") or [], p, float(img.width), float(img.height))
            _pick = box                                 # eyes_fix F0: the far eye's pick, before the colour re-pick
            seg = None
            if box is not None and not fills and head_noun(p) in _SMALL:
                try:
                    seg = _segment(url, png, img, p, timeout_s)     # the thing itself, not a box around it
                except Exception:
                    seg = None
                if seg is None:
                    try:
                        seg = _segment_in_box(url, png, img, p, box, timeout_s)   # closer look inside the box
                        if seg is not None:
                            rec["how_note"] = "crop"
                    except Exception:
                        seg = None
            rec["ms"] = int((time.time() - t0) * 1000)
            if box is None:
                rec["status"] = "not_found"
                rec.pop("why", None)
            elif seg is not None:
                px, mbox, area = seg
                rec.update(region_pattern(img, mbox, p, px=px, area_frac=area))
                rec["n_boxes"] = n_real
                rec["fills_screen"] = False
                rec["how"] = "mask"
                rec["status"] = "found"
                rec.pop("why", None)
            else:
                if n_real > 1 and not fills:
                    W, H = float(img.width), float(img.height)
                    real = [b for b in (g.get("bboxes") or []) if _MIN_BOX <= (max(0, b[2]-b[0]) * max(0, b[3]-b[1])) / (W * H) < _WHOLE_FRAME]
                    box = _best_box_by_colour(img, real, p) or box
                rec.update(region_pattern(img, box, p))
                rec["n_boxes"] = n_real
                rec["fills_screen"] = fills
                rec["how"] = "box"
                rec["status"] = "found"
                rec.pop("why", None)
            if rec.get("status") == "found" and not rec.get("fills_screen") and _ef("doubt"):   # eyes_fix F1: a witness, or 'unsure'
                try:
                    _doubt(rec, img, p, g, box)
                except Exception as _de:                # eyes_fix F1 (verify M4): the gate fails CLOSED -- its own error is never a find
                    rec["status"] = "unsure"
                    rec["doubt"] = ["your eyes' own check of that place failed"]
                    rec["doubt_n"] = int(rec.get("n_boxes") or 1)
                    print("[Eyes] doubt check failed (%s: %s): told as not sure" % (type(_de).__name__, ascii(str(_de))[:80]), flush=True)
            if _ef("log"):                              # eyes_fix F0: what the far eye returned and what was made of it
                _log_ground(p, g, img, _pick, box, n_real, rec, src, age, within)
        except Exception as e:
            rec["why"] = "timeout" if "timed out" in str(e).lower() else "network"
            rec["err"] = "%s: %s" % (type(e).__name__, str(e)[:80])
        out.append(rec)
        if on_result:
            try:
                on_result(rec)
            except Exception:
                pass
    return out


# ── anticipation: the looks that happen before anyone asks ──────────────────────
# Ace 2026-09-18: "the council including Florence should be about 30 moments ahead of the chairman".
_LOOKS: "deque" = None                              # (ts, rec) of the last 30 looks, any source
_LOOKS_MAX = 30
_LOOKS_LOCK = _keep('_LOOKS_LOCK', threading.Lock())
_STANDING = _keep('_STANDING', {})  #  phrase -> expiry ts (0 = permanent)
# 2026-09-20: no permanent standing phrases -- 'hair,wings' were the Saiyan image and kept her fovea on 1% blobs
# for hours after it was gone. The windows map is always known; what he names is watched for _PROMOTE_S.
_STANDING_DEFAULT = [p.strip() for p in (os.environ.get("AKASHIC_EYES_STANDING") or "").split(",") if p.strip()]
_MISSES = _keep('_MISSES', {})  #  phrase -> consecutive not_found looks
_PROMOTE_S = float(os.environ.get("AKASHIC_EYES_PROMOTE_S", "900") or 900)     # his words stay watched this long
_CACHE_FRESH_S = float(os.environ.get("AKASHIC_EYES_CACHE_S", "90") or 90)     # a look this recent answers for the satellite
_ANTICIPATE_EVERY_S = float(os.environ.get("AKASHIC_EYES_ANTICIPATE_S", "20") or 20)
_ANTICIPATE_ON = os.environ.get("AKASHIC_EYES_ANTICIPATE", "1") != "0"
_ANT_STARTED = _keep('_ANT_STARTED', [False])
_ANT_STATS = _keep('_ANT_STATS', {"cycles": 0, "looks": 0, "skipped_static": 0, "last_frame": -1, "last_ts": 0.0})
_LAST_MOVE_TS = _keep('_LAST_MOVE_TS', [0.0])  #  when the screen last moved (per the interior's record): looks older than this are stale


def screen_moved_since(ts: float) -> bool:
    return _LAST_MOVE_TS[0] > ts


def _looks():
    global _LOOKS
    if _LOOKS is None:
        from collections import deque
        _LOOKS = deque(maxlen=_LOOKS_MAX)
    return _LOOKS


def remember_look(rec: Dict) -> None:
    if not rec or not rec.get("phrase") or rec.get("how") in ("hand", "playroom", "window_map"):   # set1c: a toy known by name is not a look; eyes_fix2: nor a window
        return                                          # her hand is felt, not seen: never a 'place you keep looking at'
    prev = None
    try:
        _p = str(rec.get("phrase", ""))
        _floor = 0.5 if head_noun(_p) in _SMALL else 2.0           # 2% of 3440x1440 is a 315 px block: not a cursor's size
        if rec.get("status") == "not_found" or (rec.get("status") == "found" and float(rec.get("size_pct") or 0.0) < _floor):
            _MISSES[_p] = _MISSES.get(_p, 0) + 1     # a 1% blob for 'fairy' (his figure of speech) is a miss, not a find
        elif rec.get("status") == "found":
            _MISSES.pop(_p, None)
    except Exception:
        pass
    with _LOOKS_LOCK:
        if rec.get("status") == "found":
            p = str(rec.get("phrase", "")).lower()
            for _ts, r in reversed(_looks()):
                if str(r.get("phrase", "")).lower() == p and r.get("status") == "found":
                    prev = r
                    break
        _looks().append((time.time(), rec))
    if prev is not None:                                # 2026-09-20: the same look, different answer = a surprise she captured
        if _ef("log"):                                  # eyes_fix F0: the two boxes behind the surprise (DIAGNOSIS C5)
            _log_look_change(rec.get("phrase"), prev, rec)
        try:
            from infrastructure import surprise as _sp
            _sp.from_look_change(str(rec.get("phrase")), prev, rec)
        except Exception:
            pass


def cached_look(phrase: str, max_age_s: float = _CACHE_FRESH_S) -> Optional[Dict]:
    """The freshest look for this phrase (or its head noun) within max_age_s, stamped with its age."""
    if is_hand(phrase):
        return None                                   # her hand is always live, never a memory of a look
    want = {phrase.lower(), head_noun(phrase).lower()}
    now = time.time()
    with _LOOKS_LOCK:
        for ts, rec in reversed(_looks()):
            if now - ts > max_age_s or screen_moved_since(ts):
                break                                   # older looks were of a different screen
            p = str(rec.get("phrase", "")).lower()
            if p in want or head_noun(p) in want:
                r = dict(rec)
                r["cached_age_s"] = round(now - ts, 1)
                r["looked_as"] = p
                r["phrase"] = phrase                 # answer under the words he used ...
                cw = colour_word(phrase)               # ... and judge HIS colour word on the region's profile
                prof = r.get("profile") or {}
                if cw and r.get("status") == "found" and prof:
                    frac = float(prof.get(cw, 0.0))
                    if cw == "dark":
                        frac = float(prof.get("black", 0.0))
                    r["colour_word"] = cw
                    r["colour_fraction"] = round(frac, 3)
                    r["matches"] = True if frac >= 0.12 else ("some" if frac >= 0.05 else False)
                return r
    return None


def promote(phrases: List[str]) -> None:
    """What Ace asks about, she keeps watching for a while -- the learned anticipatory habit."""
    now = time.time()
    for p in phrases or []:
        if p:
            _STANDING[p] = now + _PROMOTE_S


def standing_phrases() -> List[str]:
    now = time.time()
    for k in [k for k, exp in _STANDING.items() if exp and exp < now]:
        _STANDING.pop(k, None)
    for k in [k for k in _STANDING if _MISSES.get(k, 0) >= 2]:
        _STANDING.pop(k, None); _MISSES.pop(k, None)   # looked twice, nothing there twice: it has left the screen
    out = [p for p in _STANDING if p]
    for p in _STANDING_DEFAULT:
        if p not in out:
            out.append(p)
    return out


def recent_region_tags(max_age_s: float = 60.0, limit: int = 6) -> List[str]:
    """Region tags for the MomentBinder: region:<phrase>:<position>:<band><pct> -- regions, not captions."""
    now = time.time()
    tags: List[str] = []
    with _LOOKS_LOCK:
        for ts, rec in reversed(_looks()):
            if now - ts > max_age_s or len(tags) >= limit or screen_moved_since(ts):
                break
            if rec.get("status") != "found":
                continue
            tb = rec.get("top_bands") or []
            band = ("%s%d" % (tb[0][0], int(100 * tb[0][1]))) if tb else str(rec.get("colour_name", "?"))
            tags.append("region:%s:%s:%s" % (re.sub(r"\s+", "_", str(rec.get("phrase", "?"))), rec.get("position", "?"), band))
    return tags


_ANT_GEN = _keep("_ANT_GEN", [0])


def _front_read_and_tell(fw: Dict, prev: Optional[str]) -> None:
    """Off the loop thread: read the window that just came to the front (8 s patience) and say so with its words."""
    if _ef2("front_line"):                             # e1b vision_hand: one line in her percept -- no surprise (no whole turn),
        _front_note(fw, prev)                          # no far-eye read, no glance; what she holds stays held
        return
    try:
        from infrastructure import surprise as _sp
        rec = look_window(fw, timeout_s=8.0, origin="front")   # eyes_fix F6: she did not choose it
        fname = fw["name"]
        if rec.get("status") == "window":
            _ft_ok = _sp.push("eyes", "%s just came to the front of your screen (it was %s before). In it: %s%s" % (   # 2026-10-06 (council_set1 item 5)
                fname[0].upper() + fname[1:], prev, _sentence_cut(rec.get("text", ""), 200),
                (" Words you read in it: \"%s\"" % rec["words"][-220:]) if rec.get("words") else ""), key="front", weight=0.8)
        else:
            _ft_ok = _sp.push("eyes", "The window in front changed: it was %s, now it is %s." % (prev, fname), key="front", weight=0.7)   # 2026-10-06 (council_set1 item 5)
        if _ft_ok:                                     # 2026-10-06 (council_set1 item 5, verify_tests F6): only a surprise that was queued names its window
            _FRONT_TOLD[0] = {"hwnd": int(fw.get("hwnd") or 0), "name": fname, "ts": time.time()}
    except Exception as e:
        print("[Eyes] front read: %s" % e, flush=True)


def _anticipate_once(st: Dict) -> None:
    """One cycle. Called by name from the loop thread, so a reload changes what a cycle does."""
    if not florence_url():
        return
    now = eyes_now()
    fn = int(now.get("_frame_num", -1)) if now else -1
    moved = (fn != _ANT_STATS["last_frame"]) and (not now.get("is_duplicate") or float(now.get("salience") or 0) >= 0.5)
    if moved:
        _LAST_MOVE_TS[0] = time.time()                  # everything looked at before this is a different screen
    stale = (time.time() - _ANT_STATS["last_ts"]) > 6 * _ANTICIPATE_EVERY_S
    if not (moved or stale):
        _ANT_STATS["skipped_static"] += 1
        return
    try:                                                # which window is in front: a change is an event she saw
        fw = front_window()
        fname = fw["name"] if fw else None
        if fw is None and _ef("log"):                   # eyes_fix F0: the OS front window her map does not hold
            _log_unmapped_front()
        if fname and _ANT_STATS.get("front") not in (None, fname):
            prev = _ANT_STATS.get("front")
            fresh = time.time() - _READ_WINDOWS.get(int(fw.get("hwnd") or 0), 0.0) > _REREAD_S
            if fname == "your chat window":
                pass                                    # Ace coming back to talk to her is not a surprise; his words are
            elif _ef2("front_line"):                    # e1b vision_hand (verify F4): nothing is READ, so the 5-min re-read gate is
                _fh = int(fw.get("hwnd") or 0)          # not this path's limiter -- every fronting is noted, one per window per
                if time.time() - _FRONT_NOTED.get(_fh, 0.0) > FRONT_RENOTE_S:   # FRONT_RENOTE_S; _READ_WINDOWS is not stamped
                    _FRONT_NOTED[_fh] = time.time()
                    for _k in [k for k, ts in _FRONT_NOTED.items() if time.time() - ts > 3600]:
                        _FRONT_NOTED.pop(_k, None)
                    threading.Thread(target=_front_read_and_tell, args=(dict(fw), prev), daemon=True, name="eyes-front").start()
            elif fresh:                                 # something new in front: read it (own thread), hold it, say so
                _READ_WINDOWS[int(fw.get("hwnd") or 0)] = time.time()
                threading.Thread(target=_front_read_and_tell, args=(dict(fw), prev), daemon=True, name="eyes-front").start()
        if fname:
            _ANT_STATS["front"] = fname
    except Exception as _fe:
        print("[Eyes] front: %s" % _fe, flush=True)
    phrases = standing_phrases()
    if not phrases:
        _ANT_STATS["last_frame"], _ANT_STATS["last_ts"] = fn, time.time()
        return
    rr = st.get("rr", 0)
    batch = [phrases[(rr + i) % len(phrases)] for i in range(min(2, len(phrases)))]
    st["rr"] = rr + len(batch)
    sem = _INFLIGHT
    if not sem.acquire(timeout=0.1):
        return                                          # an asked-for look is running; keep the satellite for it
    try:
        recs = ground(batch, on_result=remember_look)
    finally:
        sem.release()
    _ANT_STATS["cycles"] += 1
    _ANT_STATS["looks"] += len(recs)
    _ANT_STATS["last_frame"], _ANT_STATS["last_ts"] = fn, time.time()
    found = [(r.get("phrase"), r.get("position"), (r.get("top_bands") or [("?", 0)])[0][0]) for r in recs if r.get("status") == "found"]
    if found:
        print("[Eyes] anticipated: %s" % found, flush=True)


def _anticipate_loop(gen: int = 0, first_sleep: float = 0.0):
    """Look ahead: when the screen has moved since the last cycle, segment the standing phrases (round-robin,
    two per cycle) and remember the looks. The body lives in _anticipate_once so a reload takes effect; a loop
    of an older generation is retired in eyes_now()."""
    st: Dict = {"rr": 0}
    if first_sleep > 0:
        time.sleep(first_sleep)
    while True:
        try:
            time.sleep(_ANTICIPATE_EVERY_S)
            if gen != _ANT_GEN[0]:
                print("[Eyes] anticipation gen %d retired" % gen, flush=True)
                return
            _anticipate_once(st)
        except SystemExit:
            return
        except Exception as e:
            print("[Eyes] anticipate err: %s" % e, flush=True)
            time.sleep(5)


def _retire_stale_anticipation() -> None:
    """A loop thread started from an older file (inline bytecode) does not see reloaded code. Its cycle calls
    eyes_now(), which raises SystemExit for a thread of a stale generation; a fresh loop is started."""
    alive = [t for t in threading.enumerate() if t.name == "eyes-anticipate" and t.is_alive()]
    stale = [t for t in alive if getattr(t, "_gen", None) != _ANT_GEN[0]]
    if stale:
        _ANT_GEN[0] += 1
        nt = threading.Thread(target=_anticipate_loop, args=(_ANT_GEN[0], 25.0), daemon=True, name="eyes-anticipate")
        nt._gen = _ANT_GEN[0]
        nt.start()
        print("[Eyes] anticipation: stale loop found (from an older file); gen %d started, the old one retires within a cycle" % _ANT_GEN[0], flush=True)
    elif not alive and _ANT_STARTED[0]:
        # the old loop already left (it met the new eyes_now before this ran): keep her eyes running
        nt = threading.Thread(target=_anticipate_loop, args=(_ANT_GEN[0], 5.0), daemon=True, name="eyes-anticipate")
        nt._gen = _ANT_GEN[0]
        nt.start()
        print("[Eyes] anticipation: no loop alive after reload; gen %d restarted" % _ANT_GEN[0], flush=True)


def start_anticipation() -> bool:
    if not _ANTICIPATE_ON:
        return False
    if any(t.name == "eyes-anticipate" and t.is_alive() and getattr(t, "_gen", None) == _ANT_GEN[0] for t in threading.enumerate()):
        return False
    _ANT_STARTED[0] = True
    t = threading.Thread(target=_anticipate_loop, args=(_ANT_GEN[0], 0.0), daemon=True, name="eyes-anticipate")
    t._gen = _ANT_GEN[0]
    t.start()
    print("[Eyes] anticipation on: standing %s, every %.0fs when the screen moves" % (standing_phrases(), _ANTICIPATE_EVERY_S), flush=True)
    return True


# ── non-blocking start / bounded collect (the council loop pattern) ────────────
_PENDING = _keep('_PENDING', {})
_PENDING_LOCK = _keep('_PENDING_LOCK', threading.Lock())
_INFLIGHT = _keep('_INFLIGHT', threading.Semaphore(1))  #  one grounding run at a time: the satellite is single-threaded


def start_grounding(text: str, origin: Optional[str] = None) -> Optional[List[str]]:   # 2026-10-06 (council_set1 item 5): + origin (skeptic F10)
    """Kick off grounding for the visual nouns in `text` on a daemon thread. Returns the phrases.
    2026-09-20: words that name the WHOLE picture are never grounded as nouns; they start a survey instead."""
    if _st_on() and origin != "wm_store":             # 2026-10-06 (council_set1 item 5): "I closed it" ends what she holds;
        try:                                           # a late working-memory copy of his words ends nothing (skeptic F10)
            _close_heard(text)
        except Exception as _ce:
            print("[Eyes] close heard: %s" % _ce, flush=True)
    phrases = [p for p in visual_nouns(text) if not is_whole(p) and not _WIN_MENTION_RE.fullmatch(p.strip())]
    want_survey = wants_survey(text)
    try:                                                # 2026-09-20: a window he names is a FOCUS, not a noun to segment
        wins = window_mentions(text) if florence_url() else []
    except Exception:
        wins = []
    if wins:
        phrases = [p for p in phrases if head_noun(p) not in _WIN_WORDS]
        slotw = {"done": threading.Event(), "partial": [], "phrases": [w.get("name", "that window") for w in wins[:2] if w.get("status") != "window_missing"], "t0": time.time()}

        def _wl():
            try:
                for w in wins[:2]:
                    rec = look_window(w, origin="ace") if w.get("status") != "window_missing" else dict(w)   # eyes_fix F6
                    with _PENDING_LOCK:
                        slotw["partial"].append(rec)
            finally:
                slotw["done"].set()
        threading.Thread(target=_wl, daemon=True, name="eyes-window").start()
        _WINDOW_SLOT[0] = slotw
    if want_survey and florence_url():
        slot0 = {"done": threading.Event(), "partial": [], "phrases": phrases, "t0": time.time()}

        def _sv():
            try:
                s = survey()
                if s:
                    with _PENDING_LOCK:
                        slot0["partial"].append(dict(s))
            finally:
                slot0["done"].set()                     # always: the collector waits on this too
        if not phrases:
            if _WINDOW_SLOT[0] is not None:
                slot0["window_from"] = _WINDOW_SLOT[0]; _WINDOW_SLOT[0] = None
            with _PENDING_LOCK:
                _PENDING[text[:400]] = slot0
            threading.Thread(target=_sv, daemon=True, name="eyes-survey").start()
            return ["the whole picture"]
        threading.Thread(target=_sv, daemon=True, name="eyes-survey").start()
        _SURVEY_SLOT[0] = slot0
    if not phrases and _WINDOW_SLOT[0] is not None:     # only a window was named
        slotw = _WINDOW_SLOT[0]; _WINDOW_SLOT[0] = None
        with _PENDING_LOCK:
            _PENDING[text[:400]] = slotw
        return [w.get("name", "?") for w in wins[:2]]
    if not phrases or not florence_url():
        return None
    promote(phrases)
    cached = [c for c in (cached_look(p) for p in phrases) if c is not None]
    fresh = [p for p in phrases if cached_look(p) is None]
    slot = {"done": threading.Event(), "partial": cached, "phrases": phrases, "t0": time.time()}
    if want_survey and _SURVEY_SLOT[0] is not None:
        slot["survey_from"] = _SURVEY_SLOT[0]; _SURVEY_SLOT[0] = None
    if _WINDOW_SLOT[0] is not None:
        slot["window_from"] = _WINDOW_SLOT[0]; _WINDOW_SLOT[0] = None
    if not fresh:                                   # everything he named was already looked at
        slot["done"].set()
        with _PENDING_LOCK:
            _PENDING[text[:400]] = slot
        return phrases
    phrases = fresh
    with _PENDING_LOCK:
        for k in [k for k, s in _PENDING.items() if time.time() - s["t0"] > 120]:
            _PENDING.pop(k, None)
        _PENDING[text[:400]] = slot

    def _on(rec):
        with _PENDING_LOCK:
            slot["partial"].append(rec)
        remember_look(rec)

    def _run():
        with _INFLIGHT:
            try:
                ground(phrases, on_result=_on)
            except Exception as e:
                _on({"phrase": phrases[0], "status": "could_not_look", "why": "network", "err": str(e)[:80]})
            finally:
                slot["done"].set()
    threading.Thread(target=_run, daemon=True, name="eyes-ground").start()
    return phrases


def collect_grounding(texts: List[str], wait_s: float = 5.0) -> List[Dict]:
    """Results for `texts` (the messages being answered); waits at most wait_s in total; phrases still
    in flight come back as could_not_look/timeout so 'still looking' is said, not invented."""
    deadline = time.time() + wait_s
    out: List[Dict] = []
    for t in texts:
        with _PENDING_LOCK:
            slot = _PENDING.pop(str(t)[:400], None)
        if slot is None:
            continue
        slot["done"].wait(max(0.0, deadline - time.time()))
        sv = slot.get("survey_from")
        if sv is not None:
            sv["done"].wait(max(0.0, deadline - time.time()))
        wv = slot.get("window_from")
        if wv is not None:
            wv["done"].wait(max(0.0, deadline - time.time()))
        with _PENDING_LOCK:
            got = list(slot["partial"])
            if sv is not None:
                got = list(sv["partial"]) + got
            if wv is not None:
                got = list(wv["partial"]) + got
        done_phrases = {r.get("phrase") for r in got}
        out.extend(got)
        out.extend({"phrase": p, "status": "could_not_look", "why": "timeout"} for p in slot["phrases"] if p not in done_phrases)
    return out


# ── prompt rendering ────────────────────────────────────────────────────────────
def _mix(g: Dict) -> str:
    if g.get("colour_unsure"):
        return "too small to be sure of its colour"
    tb = g.get("top_bands") or []
    if tb:
        if len(tb) == 1 or tb[0][1] >= 0.6:
            return "%s %.0f%%" % (tb[0][0], 100 * tb[0][1])
        return "%s %.0f%% and %s %.0f%%" % (tb[0][0], 100 * tb[0][1], tb[1][0], 100 * tb[1][1])
    name, share, second = g.get("colour_name", "?"), float(g.get("share") or 0.0), g.get("second_colour")
    if share >= 0.5:
        return "mostly %s" % name
    return "mixed colours, the largest patch %s%s" % (name, (" and " + second) if second and second != name else "")


def render_eyes(now: Dict, grounds: Optional[List[Dict]] = None, max_grounds: int = 3, lane: Optional[str] = None) -> str:   # 2026-10-06 (council_set1 item 5): + lane (skeptic F6)
    parts: List[str] = []
    now = now or {}
    if now.get("_dark_s"):
        parts.append("Your eyes have been dark for %.0f min." % (now["_dark_s"] / 60.0))
    else:
        cap = first_sentence(now.get("description", ""))
        if cap:
            age = now.get("_age_s", 0.0)
            when = "just now" if age < 15 else ("%.0f s ago" % age if age < 120 else "a while ago")
            parts.append("Your eyes (%s): %s." % (when, cap))       # no classifier label: 'dark screen' was her dark theme
        else:
            parts.append("Your eyes report nothing current.")
    tail: List[str] = []                                 # the map and the survey come AFTER what he asked for
    try:
        _fl = front_line()                               # e1b vision_hand 'front_line': one line, just before the map ('' = off)
        if _fl:
            tail.append(_fl)
    except Exception:
        pass
    try:
        wm = render_windows()                            # the un-focused view: what is open, where, what is in front
        if wm:
            tail.append(wm)
    except Exception:
        pass
    try:                                                 # e1b vision_hand 'hand_rest': where her hand rests, after the map ('' = off;
        if not any(g.get("how") == "hand" for g in (grounds or [])):   # a look at the cursor this turn already says it)
            _hr = hand_rest_line()
            if _hr:
                tail.append(_hr)
    except Exception:
        pass
    surveys = [g for g in (grounds or []) if g.get("status") == "survey"]
    if surveys:
        tail.append(render_survey(surveys[-1]))
    for g in [g for g in (grounds or []) if g.get("status") == "window"][:2]:
        parts.append(render_window_look(g))
    try:
        f = focus_now(lane)                              # 2026-10-06 (council_set1 item 5, skeptic F6): whose prompt; OFF: ignored
        if f and not any(g.get("status") == "window" and g.get("title") == f.get("title") for g in (grounds or [])):
            parts.append(render_focus(f))
    except Exception:
        pass
    for g in [g for g in (grounds or []) if g.get("status") == "window_missing"][:2]:
        parts.append("You looked for %s: none is open on the screen right now." % g.get("name", "that window"))
    for g in [g for g in (grounds or []) if g.get("status") not in ("survey", "window", "window_missing")][:max_grounds]:
        p = g.get("phrase", "that")
        st = g.get("status")
        if g.get("unasked"):
            parts.append(("A place your eyes keep pointing at (they are not sure what it is): %s of the screen, %s%% of it, its colours %s."
                          if st == "unsure" else "A place you keep looking at: %s of the screen, %s%% of it, its colours %s.")   # eyes_fix F1
                         % (g.get("position", "?"), g.get("size_pct", "?"), _mix(g)))
            continue
        if st == "found":
            if g.get("how") == "hand":
                still = g.get("still_s")
                when = ("; it just moved" if still is not None and still < 5 else
                        ("; it has rested there for %.0f s" % still if still is not None and still < 600 else ""))
                cw, m = g.get("colour_word"), g.get("matches")
                claim = ("" if not cw else (" (the pointer is the white arrow)" if m is True else " (the pointer is the white arrow, not %s)" % cw))
                own = g.get("owner_note") or ""
                own = (", " + own) if own else ""
                grant = (" Ace has handed you the mouse for the next %d s." % int(g["grant_s"])) if g.get("grant_s") else ""
                # 2026-10-01 (Nous, cursor_object b): the pointer is the CURSOR -- an object her hand reaches for and takes, which
                # Ace also moves -- not her hand. Was: "Your hand (the mouse pointer, ...) is at". Seen live in Boot E's EYES prompt.
                parts.append("The cursor (the mouse pointer, a small white arrow -- you feel where it is, no need to "
                             "look) is %s%s%s%s.%s" % (place_phrase(g.get("position", "?")), own, when if not own else "", claim, grant))   # eyes_fix F8
                continue
            if g.get("how") == "playroom":            # 2026-10-09 (set1c): a toy of her verified Playroom, known by its name
                parts.append("You looked for \"%s\": it is the toy named '%s' in your Playroom, %s of the screen."
                             % (p, g.get("toy", p), g.get("position", "?")))
                continue
            if g.get("how") == "window_map":          # eyes_fix2 (window_names): the WINDOW she named, from her window map
                parts.append(window_words(p, g, lead="You looked for") + ".")
                continue
            if g.get("fills_screen"):
                parts.append("You looked for \"%s\": it fills the screen, %s." % (p, _mix(g)))
                continue
            cw = g.get("colour_word")
            m = g.get("matches")
            if cw is None:
                verdict = " (its colour was not checked against a word)"
            elif m is True:
                verdict = " -- about %.0f%% of it really is %s" % (100 * float(g.get("colour_fraction", 0)), cw)
            elif m == "some":
                verdict = " -- only a little of it (%.0f%%) is %s" % (100 * float(g.get("colour_fraction", 0)), cw)
            else:
                verdict = " -- not %s at all" % cw
            if g.get("colour_unsure"):
                where = "%s of the screen, %s%% of it -- too small to be sure of its colour" % (g.get("position", "?"), g.get("size_pct", "?"))
                verdict = ""
            else:
                where = "%s of the screen, %s%% of it, its colours %s" % (g.get("position", "?"), g.get("size_pct", "?"), _mix(g))
            if g.get("how") == "mask" and g.get("shape"):
                where += ", its form %s" % g["shape"]
            elif g.get("how") == "box" and head_noun(p) in _SMALL:
                where += " (a rough box around it, not the thing itself)"
            n = int(g.get("n_boxes") or 1)
            more = (" (one of %d places it pointed at)" % n) if n > 1 else ""
            fa = float(g.get("cached_age_s") or g.get("frame_age_s") or 0.0)
            old = (" (from your look %.0f s ago)" % fa) if fa > 15 else ""
            parts.append("You looked for \"%s\"%s: something is there, %s%s%s." % (p, old, where, verdict, more))
        elif st == "unsure":                            # eyes_fix F1 (doubt): a place to check, never 'something is there'
            parts.append("You looked for \"%s\": your eyes are not sure -- %s." % (p, unsure_words(g)))
        elif st == "not_found":
            parts.append("You looked for \"%s\": nowhere on the screen right now." % p)
        else:
            why = g.get("why")
            if why == "frame":
                parts.append("You tried to look for \"%s\" but your eyes were dark." % p)
            elif why == "timeout":
                parts.append("You were still looking for \"%s\" when you had to speak." % p)
            else:
                parts.append("You tried to look for \"%s\" but the far eye did not answer." % p)
    return " ".join(parts + tail)


# ── the manifold: region node + typed edge from Ace's word ─────────────────────
_STOP = {"the", "a", "an", "my", "your", "her", "his", "long", "short", "big", "little", "small", "tiny", "huge", "some"}


def _cortex_handle():
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        am = getattr(acf, "_akashic_cortex_region", None) if acf is not None else None
        if am is None:
            return None
        if type(am).__name__ != "ManifoldMemory" and not hasattr(am, "_REL_NAME_TO_INT"):
            return None                               # a GraphCortexStore would silently drop the rel type
        if hasattr(am, "upsert_node") and hasattr(am, "link") and hasattr(am, "get_node"):
            return am
    except Exception:
        pass
    return None


def phrase_keys(phrase: str) -> List[str]:
    """The ace: keys the cortex mints for his words, most specific first: ace:<adj>_<noun>, ace:<noun>."""
    ws = [w for w in re.findall(r"[a-z0-9]+", phrase.lower()) if w not in _STOP]
    keys: List[str] = []
    if len(ws) >= 2:
        keys.append("ace:" + ws[-2] + "_" + ws[-1])
    if ws:
        keys.append("ace:" + ws[-1])
    return [k[:60] for k in keys]


def region_key(rec: Dict) -> str:
    band = re.sub(r"[^a-z]+", "_", str(rec.get("colour_name", "unknown")).lower()).strip("_") or "unknown"
    return "region:screen:r%dc%d:%s" % (int(rec.get("row", 0)), int(rec.get("col", 0)), band)


def bind_region(phrase: str, rec: Dict, am=None) -> Optional[str]:
    """Region node (cell + colour band, TRACE_VISUAL) and a SEEN_IN edge from Ace's phrase node -- ONLY when
    the region's pixels carry the colour his word names (matches is True). A bare noun is never bound:
    nothing independent verified it. Returns the region key only if the edge was actually written."""
    if not rec or rec.get("status") != "found" or rec.get("matches") is not True or rec.get("fills_screen") or rec.get("how") == "hand":
        return None
    am = am or _cortex_handle()
    if am is None:
        return None
    try:
        from infrastructure.manifold_memory import (NTYPE_ENTITY, REGION_SEMANTIC, TRACE_VISUAL, TRACE_ACE,
                                                    REL_SEEN_IN)
        rkey = region_key(rec)
        snippet = ("screen region %s, %s, cell %d" % (rec.get("position", "?"), rec.get("colour_name", "?"),
                                                       int(rec.get("cell", 0))))[:120]
        rs = am.upsert_node(rkey, activation=0.5, count=1, degree=0, coord_str="040.000.%03d" % int(rec.get("cell", 0)),
                            snippet=snippet, node_type=NTYPE_ENTITY, region=REGION_SEMANTIC, tracer_id=TRACE_VISUAL, parent_slot=0)
        if rs is not None and rs < 0:
            return None
        pkey = None
        for k in phrase_keys(phrase):
            if am.get_node(k):
                pkey = k
                break
        if pkey is None:
            keys = phrase_keys(phrase)
            if not keys:
                return None
            pkey = keys[0]
            ps = am.upsert_node(pkey, activation=0.5, count=1, degree=0, coord_str="", snippet=phrase[:120],
                                node_type=NTYPE_ENTITY, region=REGION_SEMANTIC, tracer_id=TRACE_VISUAL, parent_slot=0)
            if ps is not None and ps < 0:
                return None
        if not am.link(pkey, rkey, weight=0.4, rel_type=REL_SEEN_IN, tracer_id=TRACE_ACE):
            return None
        return rkey
    except Exception as e:
        print("[Eyes] bind failed: %s" % e, flush=True)
        return None


# ── on (re)load: retire an anticipation loop that still runs the file it was born from ─────────────────────
try:
    _retire_stale_anticipation()
except Exception as _re_err:
    print("[Eyes] retire: %s" % _re_err, flush=True)
