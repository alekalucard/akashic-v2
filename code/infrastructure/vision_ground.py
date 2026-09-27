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
            if rec.get("status") != "found" or rec.get("fills_screen"):
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
    vert = "upper" if cy < 0.34 else ("lower" if cy > 0.66 else "middle")
    horiz = "left" if cx < 0.34 else ("right" if cx > 0.66 else "centre")
    return {"row": row, "col": col, "cell": row * _GRID_COLS + col,
            "position": vert + "-" + horiz if (vert, horiz) != ("middle", "centre") else "centre"}


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


def look_window(w: Dict, timeout_s: float = 25.0, read_words: Optional[bool] = None) -> Dict:
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
    set_focus(rec)
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


def set_focus(rec: Dict) -> None:
    """A window she read becomes what she holds; its words go into the weave as a turn of her own eyes."""
    if not rec or rec.get("status") != "window":
        return
    _FOCUS["rec"], _FOCUS["ts"] = dict(rec), time.time()
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


def focus_now() -> Optional[Dict]:
    r = _FOCUS["rec"]
    if r is None or time.time() - _FOCUS["ts"] > _FOCUS_HOLD_S:
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
    return p in _WHOLE_NOUNS or head_noun(p) in _WHOLE_NOUNS


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


def ground(phrases: List[str], timeout_s: float = _GROUND_TIMEOUT_S, on_result=None) -> List[Dict]:
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
            box, n_real, fills = _choose_box(g.get("bboxes") or [], g.get("labels") or [], p, float(img.width), float(img.height))
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
    if not rec or not rec.get("phrase") or rec.get("how") == "hand":
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
    try:
        from infrastructure import surprise as _sp
        rec = look_window(fw, timeout_s=8.0)
        fname = fw["name"]
        if rec.get("status") == "window":
            _sp.push("eyes", "%s just came to the front of your screen (it was %s before). In it: %s%s" % (
                fname[0].upper() + fname[1:], prev, _sentence_cut(rec.get("text", ""), 200),
                (" Words you read in it: \"%s\"" % rec["words"][-220:]) if rec.get("words") else ""), key="front", weight=0.8)
        else:
            _sp.push("eyes", "The window in front changed: it was %s, now it is %s." % (prev, fname), key="front", weight=0.7)
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
        if fname and _ANT_STATS.get("front") not in (None, fname):
            prev = _ANT_STATS.get("front")
            fresh = time.time() - _READ_WINDOWS.get(int(fw.get("hwnd") or 0), 0.0) > _REREAD_S
            if fname == "your chat window":
                pass                                    # Ace coming back to talk to her is not a surprise; his words are
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


def start_grounding(text: str) -> Optional[List[str]]:
    """Kick off grounding for the visual nouns in `text` on a daemon thread. Returns the phrases.
    2026-09-20: words that name the WHOLE picture are never grounded as nouns; they start a survey instead."""
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
                    rec = look_window(w) if w.get("status") != "window_missing" else dict(w)
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


def render_eyes(now: Dict, grounds: Optional[List[Dict]] = None, max_grounds: int = 3) -> str:
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
        wm = render_windows()                            # the un-focused view: what is open, where, what is in front
        if wm:
            tail.append(wm)
    except Exception:
        pass
    surveys = [g for g in (grounds or []) if g.get("status") == "survey"]
    if surveys:
        tail.append(render_survey(surveys[-1]))
    for g in [g for g in (grounds or []) if g.get("status") == "window"][:2]:
        parts.append(render_window_look(g))
    try:
        f = focus_now()
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
            parts.append("A place you keep looking at: %s of the screen, %s%% of it, its colours %s."
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
                parts.append("Your hand (the mouse pointer, a small white arrow -- you feel where it is, no need to "
                             "look) is at the %s of the screen%s%s%s.%s" % (g.get("position", "?"), own, when if not own else "", claim, grant))
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
