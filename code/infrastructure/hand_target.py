"""hand_target -- where her hand should go for the thing she NAMED, and whether it is there after the move. 2026-09-29 (Nous,
thought_hand_r2; Ace: "Window targeting: YES, same round").

Measured (state/intentions.jsonl row ts 1790723010.25, Boot C 16:03:30): "move: mouse to Valheim window title bar" went through
Florence phrase grounding to (673, 534), middle-left of a 3440x1440 screen, and was booked "arrived" (reach_match 1.0,
landing_err 0 px): the reach landed where the eyes pointed, and nothing checked that the thing under the cursor was the thing
she named. She then said "My hand found the Valheim window title bar on its first try" (log L145093). "Valheim dedicated" was
not an OS window: the Claude app's OS title is "Claude" (state/user_presence.json foreground_window, written by her own
intention.write_presence from vision_ground.front_window()), the window maps name only "your chat window" and "Nous's window
(Claude)", and her eyes read "Valheim dedicated" as TEXT inside Nous's window (L106073: 'The window is titled "Valheim
dedicated"'; the foveal OCR "g Valheimdedicated D o x Recy:le Bin ..." from L2644 on).

Targeting by kind (intention.execute calls plan() before its grounding and check_landing() after the move):
  (a) WINDOW: the object names an OS top-level window -- vision_ground.window_mentions() on the object with its echo prefix
      stripped ('mouse to ...'), 'Nous' / 'Claude' as Nous's window, or a window whose title holds every name word of the object.
      Aim at its caption strip: top + CAPTION_DY px, left of centre, clear of the app icon and of min / max / close -- the first
      such point whose root window IS that window (a point another window covers is skipped). When EVERY point belongs to another
      window (fully covered, or minimised / cloaked after the window-map cache filled) plan() returns {'covered': True, 'under': ...}
      and intention.execute makes no move: a not-found-class outcome (her words say what it is behind, a try at her goal, the
      door's backoff, no chord). (Fable, round-2 verifier L2/L3.)
  (b) TEXT: the object names on-screen text -- a quoted phrase, or a capitalised name that the eyes' last full-screen read also
      holds (never the eyes' read alone: her own chat window shows every name she speaks). Florence OCR-with-regions over
      full-resolution tiles of the screen; aim at the box whose words match, never a box in her own chat window.
  (c) otherwise, or when (b) finds nothing: today's Florence phrase grounding in intention.execute, unchanged.
Landing check, for an (a)- or (b)-kind object whichever route placed the hand: (a) the root window under the landed cursor
(WindowFromPoint -> GetAncestor(GA_ROOT)) must be the target window; (b) a small full-resolution crop around the cursor, read
by Florence OCR, must hold the name words, and the hand must not be on her own chat window. Either can fail: a MISS goes through
the existing miss path (ok False, the chord, a try at her goal, her words next turn). When the eyes cannot look the verdict is
'unverified' -- never 'arrived'. A 'visual' object (no window, no text evidence) gets no check: today's path, unchanged.
Every OS / satellite call sits behind one module function (_screen, _eyes_text, _root_at, _find_text_boxes, _read_text_at;
the window map is vision_ground.windows_now) so the tests script the world. Nothing here moves or clicks.
UNVERIFIED LIVE: the satellite's OCR-with-regions task name (OCR_REGION_TASK) -- no satellite server code is on this PC; if the
satellite does not serve it, (b) finds nothing and every text object goes to (c) + the landing check (task=ocr, which
vision_ground.look_window already uses).
Set 1c (2026-10-09, Ace approved "her eyes learning the toy names"): (p) PLAYROOM TOY -- the object names a toy of her VERIFIED
Playroom exactly (vision_ground.playroom_item, from touch_os.eyes_playroom: the same source her finger aims with). Checked
BEFORE (a): vision_ground.window_mentions' title-head match made "red ball in Sour's Playroom" the Playroom WINDOW and the hand
went to its caption bar. Aim at the toy's centre; landing: the root under the hand must be the Playroom and the hand inside the
toy's current rect. Only while Ace's eyes switch (state/eyes_fix.json) carries 'toy_names' (fold 10-09: its own key,
independent of touch); otherwise nothing here changes. Fold 10-09 (DIAGNOSIS 5.2): a landing with no toy record (the key went
off, the Playroom is no longer verified or shown, DPI changed) is 'unverified', never 'arrived'.
eyes_fix_1009 F4 'hand_honest' (Ace's eyes switch state/eyes_fix.json; DIAGNOSIS C3): (i) "X in <window>" with a noun in X
is X looked for INSIDE that window (kind 'in_window'), never the window's title bar; (ii) a 'visual' object gets a landing
READ (what window is under the hand) -- 'unverified', never 'arrived'; (iii) told_move() says what the hand was aimed at
("the title bar of Sour's Playroom") and what is under it. Key off: classify / plan / check_landing are today's.
eyes_fix2_1012 'window_names' (Ace's SECOND eyes switch state/eyes_fix2.json; Boot K L50607): after the toy name and 'X in
<window>', an object that is EXACTLY the name of one window on her screen (vision_ground.named_window -- the matcher her look
uses) is aimed INSIDE that window's client area, never its title bar (kind 'window', aim 'inside'; the same landing check);
told as "the inside of the Sour's Playroom window". Key off: plan() is today's.
e1b_1013 vision_hand 'hand_rest' (same second switch; Boot L: 48 of 65 moves were "it is already there", nothing said where):
rest_part(xy) names the window PART under a point of her screen -- its title bar (above its client area), inside it, its edge --
or the desktop / taskbar; vision_ground.hand_rest_line and intention's no-op telling ask it. Read-only; nothing here moves.
Revert: delete this file -- intention's thought_hand_r2 hooks then run today's path.
"""
from __future__ import annotations

import difflib
import io
import json
import re
import sys
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

CAPTION_DY = 12                # px below the window's top edge: inside the caption strip
CAPTION_X_FRACS = (0.35, 0.2, 0.5, 0.65)   # left of centre first
CAPTION_LEFT_KEEP = 48         # clear of the app icon at the far left
CAPTION_RIGHT_KEEP = 160       # clear of min / max / close at the far right
OCR_REGION_TASK = "ocr_region"             # Florence <OCR_WITH_REGION> on the satellite (UNVERIFIED live, see above)
OCR_TASK = "ocr"                           # known live: vision_ground.look_window asks task=detailed,ocr
TILE_COLS, TILE_ROWS = 3, 2
SCAN_DEADLINE_S = 10.0
EYES_ACQUIRE_S = 2.0           # per satellite call: the eyes are one-at-a-time (vision_ground._INFLIGHT)
CALL_TIMEOUT_S = 8.0
CROP_W, CROP_H = 420, 90       # logical px around the landed cursor, for the text check
FUZZY = 0.8                    # a name word of >= 5 letters may be read with one slip ('Recy:le Bin')

_STRUCT = {"the", "a", "an", "my", "your", "his", "her", "its", "this", "that", "these", "those", "to", "of", "on", "in", "at",
           "for", "with", "and", "or", "over", "into", "onto", "near", "by", "from", "window", "windows", "title", "titled",
           "bar", "caption", "tab", "tabs", "screen", "desktop", "top", "bottom", "left", "right", "middle", "corner", "edge",
           "side", "area", "part", "icon", "button", "thing", "app", "application", "program", "page", "console", "terminal",
           "browser", "chat", "notepad", "log", "ui", "interface", "little", "big", "small", "upper", "lower", "centre",
           "center", "header", "heading", "label", "text", "word", "words", "name", "named", "called", "says", "which",
           "where", "there", "here", "it", "one", "open", "new", "main", "front", "back", "mouse", "cursor", "pointer", "hand",
           "hands", "should", "would", "could", "is", "was", "be", "again", "now", "just", "real", "actual", "field", "box"}
_ECHO_RE = re.compile(r"^\s*(?:(?:the|my|your|her)\s+)?(?:mouse|cursor|pointer|hands?)(?:\s+pointer)?\s+"
                      r"(?:(?:back|over|up|down|across|right)\s+)?(?:to|towards?|onto|into|over|at|on|near)\s+", re.I)
_QUOTED_RE = re.compile(r"[\"'‘’“”]([^\"'‘’“”]{2,80})[\"'‘’“”]")
_NOUS_RE = re.compile(r"^(?:(?:the|to)\s+)?(?:nous|claude)(?:'?s?\s+(?:window|ui|screen|side|interface))?$", re.I)


# ── the seams (the tests script these; production reads the OS and the satellite) ─────────────────────────────────────
def _vg():
    vg = sys.modules.get("infrastructure.vision_ground")
    if vg is None:
        try:
            from infrastructure import vision_ground as vg
        except Exception:
            return None
    return vg


def _ef(key: str) -> bool:
    """eyes_fix_1009: one key of Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py); OFF on any doubt (the
    module absent, the file absent or malformed) -- then every line marked eyes_fix runs today's path."""
    try:
        from infrastructure import eyes_fix as _efm
        return _efm.on(key)
    except Exception:
        return False


def _ef2(key: str) -> bool:
    """eyes_fix2_1012: one key of Ace's SECOND eyes switch (state/eyes_fix2.json, infrastructure/eyes_fix2.py); OFF on any
    doubt -- then every line marked eyes_fix2 runs today's path."""
    try:
        from infrastructure import eyes_fix2 as _ef2m
        return _ef2m.on(key)
    except Exception:
        return False


_U32C = {"dll": None}


def _client_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """eyes_fix2: the window's CLIENT area (below its title bar and inside its frame) in screen px, the space GetWindowRect
    answers in; None when the OS cannot say. Read-only user32 calls on a PRIVATE handle (no other caller's argtypes change)."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        u = _U32C["dll"]
        if u is None:
            u = ctypes.WinDLL("user32", use_last_error=True)
            u.GetClientRect.argtypes = (wt.HWND, ctypes.POINTER(wt.RECT))
            u.GetClientRect.restype = wt.BOOL
            u.ClientToScreen.argtypes = (wt.HWND, ctypes.POINTER(wt.POINT))
            u.ClientToScreen.restype = wt.BOOL
            _U32C["dll"] = u
        if not hwnd:
            return None
        r = wt.RECT()
        if not u.GetClientRect(wt.HWND(int(hwnd)), ctypes.byref(r)):
            return None
        p = wt.POINT(0, 0)
        if not u.ClientToScreen(wt.HWND(int(hwnd)), ctypes.byref(p)):
            return None
        return int(p.x), int(p.y), int(p.x + r.right), int(p.y + r.bottom)
    except Exception:
        return None


def _screen() -> Tuple[int, int]:
    try:
        import ctypes
        u = ctypes.windll.user32
        return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
    except Exception:
        return 0, 0


def _eyes_text() -> str:
    """The eyes' last full-screen read (VisualInterior ocr_preview in state/visual_shared_frame.mmap), '' when dark."""
    try:
        vg = _vg()
        d = vg.eyes_now() if vg is not None else {}
        return str((d or {}).get("ocr_preview") or "")
    except Exception:
        return ""


_U32 = {"dll": None}


def _root_at(x: int, y: int) -> Optional[Tuple[int, str]]:
    """(hwnd, title) of the top-level window under a screen point, or None when the OS cannot say. A PRIVATE user32 handle:
    the argtypes set here touch no other caller's ctypes.windll.user32 function objects."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        u = _U32["dll"]
        if u is None:
            u = ctypes.WinDLL("user32", use_last_error=True)
            u.WindowFromPoint.argtypes = (wt.POINT,)
            u.WindowFromPoint.restype = wt.HWND
            u.GetAncestor.argtypes = (wt.HWND, wt.UINT)
            u.GetAncestor.restype = wt.HWND
            u.GetWindowTextLengthW.argtypes = (wt.HWND,)
            u.GetWindowTextW.argtypes = (wt.HWND, wt.LPWSTR, ctypes.c_int)
            _U32["dll"] = u
        h = u.WindowFromPoint(wt.POINT(int(x), int(y)))
        if not h:
            return None
        root = u.GetAncestor(h, 2) or h                 # GA_ROOT
        n = int(u.GetWindowTextLengthW(root) or 0)
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(root, buf, n + 1)
        return int(root), buf.value
    except Exception:
        return None


def _satellite(task: str, png: bytes) -> Optional[Dict]:
    """One Florence call under the eyes' one-at-a-time guard; the result dict, or None when the eyes could not look."""
    vg = _vg()
    url = vg.florence_url() if vg is not None else ""
    if not url:
        return None
    sem = getattr(vg, "_INFLIGHT", None)
    if sem is not None and not sem.acquire(timeout=EYES_ACQUIRE_S):
        return None
    try:
        req = urllib.request.Request(url + "/caption?task=" + task, data=png, headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=CALL_TIMEOUT_S) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return (d or {}).get("result") or None
    except Exception:
        return None
    finally:
        if sem is not None:
            sem.release()


def _grab_full():
    """(full-resolution screen image, sx, sy) with the hand strip painted out, or (None, 1, 1)."""
    try:
        from PIL import ImageGrab
        sw, sh = _screen()
        full = ImageGrab.grab()
        try:
            _vg()._paint_out_strip(full)
        except Exception:
            pass
        return full, full.width / float(sw or full.width), full.height / float(sh or full.height)
    except Exception:
        return None, 1.0, 1.0


def _png(im) -> bytes:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "PNG", compress_level=1)
    return buf.getvalue()


def parse_ocr_region(res: Optional[Dict]) -> List[Tuple[str, List[float]]]:
    """Florence <OCR_WITH_REGION> as the satellite may return it: {'quad_boxes': [[x1,y1,...,x4,y4]], 'labels': ['</s>text']} (or
    'bboxes' of 4 numbers) under the task's key. [(label, [x1, y1, x2, y2])]; [] for anything else."""
    if not isinstance(res, dict):
        return []
    g = None
    for k in (OCR_REGION_TASK, "ocr_with_region", "<OCR_WITH_REGION>", "ocr_region"):
        if isinstance(res.get(k), dict):
            g = res[k]
            break
    if g is None:
        return []
    labels = list(g.get("labels") or [])
    quads = list(g.get("quad_boxes") or g.get("bboxes") or [])
    out = []
    for lab, q in zip(labels, quads):
        try:
            q = [float(v) for v in q]
            xs, ys = (q[0::2], q[1::2]) if len(q) >= 8 else ([q[0], q[2]], [q[1], q[3]])
            out.append((re.sub(r"</?s>", "", str(lab)).strip(), [min(xs), min(ys), max(xs), max(ys)]))
        except Exception:
            continue
    return out


def _ace_first() -> bool:
    """Ace's message is queued / his reply pending, or his own grounding is in flight: the eyes are his (hand_door's reads)."""
    try:
        door = sys.modules.get("infrastructure.hand_door")
        return bool(door is not None and (door.ace_waiting_live() or door.ace_grounding_pending()))
    except Exception:
        return False


def _find_text_boxes(words: List[str]) -> Dict:
    """Production (b): Florence OCR-with-regions over TILE_COLS x TILE_ROWS full-resolution tiles, until a box matches.
    {'boxes': [{'label', 'rect' (logical px)}], 'looked': bool (a tile was read), 'busy': bool (stopped for Ace)}."""
    out = {"boxes": [], "looked": False, "busy": False}
    full, sx, sy = _grab_full()
    if full is None:
        return out
    t0 = time.time()
    tw, th = full.width // TILE_COLS, full.height // TILE_ROWS
    for row in range(TILE_ROWS):
        for col in range(TILE_COLS):
            if time.time() - t0 > SCAN_DEADLINE_S:
                return out
            if _ace_first():
                out["busy"] = True
                return out
            box = (col * tw, row * th, full.width if col == TILE_COLS - 1 else (col + 1) * tw,
                   full.height if row == TILE_ROWS - 1 else (row + 1) * th)
            res = _satellite(OCR_REGION_TASK, _png(full.crop(box)))
            if res is None:
                continue
            out["looked"] = True
            for lab, (x1, y1, x2, y2) in parse_ocr_region(res):
                out["boxes"].append({"label": lab, "rect": ((x1 + box[0]) / sx, (y1 + box[1]) / sy, (x2 + box[0]) / sx, (y2 + box[1]) / sy)})
            if any(_all_in(words, b["label"]) for b in out["boxes"]):
                return out
    return out


def _read_text_at(rect: Tuple[float, float, float, float]) -> Optional[str]:
    """Production landing read: the words Florence OCR finds in a full-resolution crop of `rect` (logical px); None when the eyes
    could not look."""
    full, sx, sy = _grab_full()
    if full is None:
        return None
    l, t, r, b = rect
    box = (max(0, int(l * sx)), max(0, int(t * sy)), min(full.width, int(r * sx)), min(full.height, int(b * sy)))
    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
        return None
    im = full.crop(box)
    if im.height < 96:
        from PIL import Image
        k = 2 if im.height >= 48 else 3
        im = im.resize((im.width * k, im.height * k), Image.Resampling.LANCZOS)
    res = _satellite(OCR_TASK, _png(im))
    if res is None:
        return None
    o = res.get("ocr")
    if isinstance(o, dict):
        o = o.get("ocr") or o.get("text") or ""
    if isinstance(o, list):
        o = " ".join(str(x) for x in o)
    return re.sub(r"</?s>", " ", str(o or ""))


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def strip_echo(obj: str) -> str:
    """'mouse to Valheim window title bar' -> 'Valheim window title bar' (the ask's farm writes the effector into the object)."""
    s = " ".join(str(obj or "").split()).strip(" .,:;!?")
    for _ in range(2):
        s2 = _ECHO_RE.sub("", s)
        if s2 == s:
            break
        s = s2
    return s


_VOCAB = {"set": None}


def _vocab() -> set:
    if _VOCAB["set"] is None:
        v = set(_STRUCT)
        try:
            vr = sys.modules.get("infrastructure.volition_read")
            if vr is None:
                from infrastructure import volition_read as vr
            v |= set(vr._TARGET_HEADS) | set(vr._PERSON_WORDS) | set(vr._VAGUE_WORDS) | set(vr._PRONOUNS) | set(vr._VERBISH)
        except Exception:
            pass
        try:
            vg = _vg()
            for name in ("_NOUNS", "_ADJ", "_CHROMATIC", "_NAME_ORDER", "_WIN_WORDS", "_STOPISH", "_BANDS"):
                v |= {str(x).lower() for x in (getattr(vg, name, None) or ())}
        except Exception:
            pass
        _VOCAB["set"] = v
    return _VOCAB["set"]


def name_words(obj: str) -> List[str]:
    """The words of the object that NAME something (not a kind of window / thing, a colour, a place or a function word)."""
    out = []
    for tok in re.findall(r"[A-Za-z][A-Za-z'\-]*", strip_echo(obj)):
        for p in tok.split("-"):
            w = p.lower().strip("'")
            if w.endswith("'s"):
                w = w[:-2]
            if len(w) >= 3 and w not in _vocab() and w not in out:
                out.append(w)
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def fuzzy_in(word: str, text: str) -> bool:
    w, t = _norm(word), _norm(text)
    if not w or not t:
        return False
    if w in t:
        return True
    if len(w) < 5 or len(t) < len(w):
        return False
    n = len(w)
    return any(difflib.SequenceMatcher(None, w, t[i:i + n]).ratio() >= FUZZY for i in range(0, len(t) - n + 1))


def _all_in(words: List[str], text: str) -> bool:
    return bool(words) and all(fuzzy_in(w, text) for w in words)


def _capitalised(obj: str, words: List[str]) -> bool:
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]*", " ".join(str(obj or "").split()))

    def base(t):
        t = t.lower().strip("'")
        return t[:-2] if t.endswith("'s") else t
    return any(i > 0 and t[:1].isupper() and base(t) in words for i, t in enumerate(toks))


# ── (a) windows ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _windows() -> List[Dict]:
    try:
        vg = _vg()
        return [w for w in (vg.windows_now() if vg is not None else []) or [] if w.get("hwnd")]
    except Exception:
        return []


def match_window(obj: str) -> Optional[Dict]:
    """The OS window the object names, front-most first: window_mentions (vision_ground's own matcher, on the stripped object;
    'Nous' / 'Claude' as Nous's window), else a window whose title holds every name word."""
    s = strip_echo(obj)
    wins = _windows()
    if not wins:
        return None
    vg = _vg()
    ms = []
    try:
        q = "nous's window" if _NOUS_RE.match(s) else s
        ms = [m for m in (vg.window_mentions(q) if vg is not None else []) if m.get("hwnd")]
    except Exception:
        ms = []
    if ms:
        return ms[0]
    nw = name_words(obj)
    if nw and sum(len(w) for w in nw) >= 4:
        for w in wins:
            if _all_in(nw, str(w.get("title") or "")):
                return w
    return None


def caption_points(w: Dict) -> List[Tuple[int, int]]:
    sw, sh = _screen()
    l, t, r, b = [int(v) for v in w["rect"]]
    L, T = max(0, l), max(0, t)
    R, B = (min(sw, r) if sw else r), (min(sh, b) if sh else b)
    lo, hi = L + CAPTION_LEFT_KEEP, R - CAPTION_RIGHT_KEEP
    y = min(T + CAPTION_DY, B - 1)
    pts = []
    for f in CAPTION_X_FRACS:
        x = int(L + (R - L) * f)
        if hi > lo:
            x = min(max(x, lo), hi)
        if (x, y) not in pts:
            pts.append((x, y))
    return pts


def _position(x: float, y: float) -> str:
    sw, sh = _screen()
    try:
        return _vg()._place(x / float(sw), y / float(sh))["position"]
    except Exception:
        return "?"


def _rec(x: int, y: int, how: str) -> Dict:
    """A grounding-shaped record for intention.execute: the frame IS the screen, the box is the point (its centre is exact)."""
    sw, sh = _screen()
    return {"status": "found", "bbox": [x, y, x, y], "frame_w": sw or 1, "frame_h": sh or 1, "position": _position(x, y),
            "synthetic": True, "how": how}


def _window_name(root: Optional[Tuple[int, str]]) -> str:
    if not root:
        return "something your eyes could not name"
    for w in _windows():
        if int(w.get("hwnd") or 0) == int(root[0]):
            return str(w.get("name") or w.get("title") or "another window")
    try:
        return _vg()._win_name(root[1], "")
    except Exception:
        return "a window called '%s'" % str(root[1])[:40]


# ── the plan and the check ───────────────────────────────────────────────────────────────────────────────────────────
def _playroom_toy(obj: str) -> Optional[Dict]:
    """set1c: the verified Playroom's toy the object names exactly (vision_ground.playroom_item), or None."""
    try:
        vg = _vg()
        f = getattr(vg, "playroom_item", None) if vg is not None else None
        return f(strip_echo(obj)) if f is not None else None
    except Exception:
        return None


_IN_WIN_RE = re.compile(r"^(?P<item>.+?)\s+(?:in|on|inside|within)\s+(?P<win>.+)$", re.I)
_NOT_ITEM = {"the", "a", "an", "my", "your", "her", "his", "its", "this", "that", "top", "bottom", "left", "right", "upper",
             "lower", "middle", "centre", "center", "corner", "edge", "side", "part", "area", "title", "bar", "caption",
             "window", "windows", "front", "back", "somewhere", "something", "anything", "place", "spot"}


def _in_window(obj: str) -> Optional[Dict]:
    """eyes_fix F4: 'red ball in Sour's Playroom' -> {'kind': 'in_window', 'item': 'red ball', 'window': <the Playroom row>}
    when the part before 'in' names a THING and the rest names an open window; None otherwise (today's routes)."""
    s = strip_echo(obj)
    m = _IN_WIN_RE.match(s)
    if not m:
        return None
    item, win = m.group("item").strip(" .,:;"), m.group("win").strip(" .,:;")
    toks = [t.strip("'") for t in re.findall(r"[a-z][a-z'\-]*", item.lower())]
    if not [t for t in toks if t and t not in _NOT_ITEM]:
        return None
    w = match_window(win)
    if w is None or not w.get("frac") or not w.get("hwnd"):
        return None
    return {"kind": "in_window", "window": w, "item": item, "words": name_words(item), "name": s}


def classify(obj: str) -> Dict:
    toy = _playroom_toy(obj)                           # set1c: a toy of her verified Playroom BEFORE the window match
    if toy is not None:
        return {"kind": "playroom", "toy": toy, "words": name_words(obj), "name": strip_echo(obj)}
    if _ef("hand_honest"):                             # eyes_fix F4: 'X in <window>' is X, inside that window -- not its title bar
        iw = _in_window(obj)
        if iw is not None:
            return iw
    w = match_window(obj)
    nw = name_words(obj)
    if w is not None:
        return {"kind": "window", "window": w, "words": nw, "name": strip_echo(obj)}
    if nw:
        # Text only with evidence that the words are WRITTEN on the screen: quoted, or a capitalised name the eyes' last read
        # also holds. Not the eyes' read alone: her own chat window shows every name she speaks ('zombie portrait'), and a
        # picture she names would become a text object whose landing check then fails -- a false miss with a chord.
        quoted = any(_all_in(nw, q) for q in _QUOTED_RE.findall(str(obj or "")))
        if quoted or (_capitalised(obj, nw) and _all_in(nw, _eyes_text())):
            return {"kind": "text", "words": nw, "name": strip_echo(obj)}
    return {"kind": "visual", "words": nw, "name": strip_echo(obj)}


# ── eyes_fix2 'window_names': a BARE window name -> INSIDE that window (its client area), not its title bar ─────────────────
INSIDE_FRACS = ((0.5, 0.5), (0.5, 0.3), (0.3, 0.5), (0.7, 0.5), (0.5, 0.7))   # of the client area: its middle first
INSIDE_TOP_DY = 32             # px: a caption strip, when the OS gives no client rect (then the window rect minus it)
INSIDE_EDGE = 8                # px: the frame, likewise


def inside_points(w: Dict) -> List[Tuple[int, int]]:
    """Candidate aim points INSIDE the window's client area, clamped to her screen; [] when it has no usable inside."""
    sw, sh = _screen()
    l, t, r, b = [int(v) for v in w["rect"]]
    cr = _client_rect(int(w.get("hwnd") or 0))
    if cr is None or cr[2] - cr[0] < 8 or cr[3] - cr[1] < 8:
        cr = (l + INSIDE_EDGE, t + INSIDE_TOP_DY, r - INSIDE_EDGE, b - INSIDE_EDGE)
    L, T, R, B = [int(v) for v in cr]
    if sw:
        L, R = max(0, L), min(sw - 1, R)
    if sh:
        T, B = max(0, T), min(sh - 1, B)
    if R - L < 4 or B - T < 4:
        return []
    pts: List[Tuple[int, int]] = []
    for fx, fy in INSIDE_FRACS:
        p = (int(L + (R - L) * fx), int(T + (B - T) * fy))
        if p not in pts:
            pts.append(p)
    return pts


def _bare_window(obj: str) -> Optional[Dict]:
    """eyes_fix2 (window_names): the object is EXACTLY the name of one window on her screen (vision_ground.named_window, the
    matcher her look uses, so eye and hand agree) -> aim INSIDE its client area, at the first point whose root window IS that
    window; every point another window's -> {'covered': True} (no move, as today's window route). None: key off, no exact
    name, no usable inside (today's routes run)."""
    if not _ef2("window_names"):
        return None
    try:
        vg = _vg()
        f = getattr(vg, "named_window", None) if vg is not None else None
        hit = f(strip_echo(obj)) if f is not None else None
    except Exception:
        hit = None
    if not hit or not (hit.get("window") or {}).get("hwnd"):
        return None
    w = hit["window"]
    pts = inside_points(w)
    if not pts:
        return None
    base = {"kind": "window", "route": "window", "aim": "inside", "hwnd": int(w["hwnd"]), "title": w.get("title"),
            "name": w.get("name"), "label": hit.get("label"), "n": int(hit.get("n") or 1), "words": name_words(obj)}
    roots = [(p, _root_at(*p)) for p in pts]
    pick = next((p for p, r in roots if r is not None and int(r[0]) == int(w["hwnd"])), None)
    if pick is None:
        over = next((r for _p, r in roots if r is not None), None)
        if over is not None:
            return dict(base, covered=True, under=_root_words(over), rec=None)   # e1b (verify F3): Ace's window is never named
        pick = pts[0]
    return dict(base, xy=pick, rec=_rec(pick[0], pick[1], "window inside"))


# ── e1b_1013 vision_hand 'hand_rest': what is under a point of her screen (where the cursor rests) ─────────────────────────
REST_SHELL = {"Progman": ("desktop", "on the desktop"), "WorkerW": ("desktop", "on the desktop"),
              "Shell_TrayWnd": ("taskbar", "on the taskbar"), "Shell_SecondaryTrayWnd": ("taskbar", "on the taskbar")}
REST_AT = {"inside": "inside %s", "title bar": "on the title bar of %s", "edge": "on the edge of %s"}
REST_SKIP = frozenset({"TkTopLevel"})   # verify F5: her hand strip / fingertip marker (Tk wrappers, skipped by her map too): never named
ACE_WINDOW = "a window from Ace's screen"
_U32K = {"dll": None}


def _root_class(hwnd: int) -> str:
    """The class of a top-level window ('' when the OS cannot say). Read-only; a PRIVATE user32 handle."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        u = _U32K["dll"]
        if u is None:
            u = ctypes.WinDLL("user32", use_last_error=True)
            u.GetClassNameW.argtypes = (wt.HWND, wt.LPWSTR, ctypes.c_int)
            u.GetClassNameW.restype = ctypes.c_int
            _U32K["dll"] = u
        buf = ctypes.create_unicode_buffer(256)
        n = int(u.GetClassNameW(wt.HWND(int(hwnd)), buf, 256) or 0)
        return buf.value if n > 0 else ""
    except Exception:
        return ""


def _root_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """GetWindowRect of a top-level window (None when the OS cannot say). Read-only; a PRIVATE user32 handle."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        u = _U32K.get("rect")
        if u is None:
            u = ctypes.WinDLL("user32", use_last_error=True)
            u.GetWindowRect.argtypes = (wt.HWND, ctypes.POINTER(wt.RECT))
            u.GetWindowRect.restype = wt.BOOL
            _U32K["rect"] = u
        r = wt.RECT()
        if not hwnd or not u.GetWindowRect(wt.HWND(int(hwnd)), ctypes.byref(r)):
            return None
        return int(r.left), int(r.top), int(r.right), int(r.bottom)
    except Exception:
        return None


def _root_words(root: Optional[Tuple[int, str]]) -> str:
    """e1b vision_hand (verify F3): a root window inside a sentence, by her map's rule -- the map's own name for a window in her
    map; else its title ONLY when its centre is on her screen (vision_ground._on_her_screen); a window whose centre is on Ace's
    monitor is ACE_WINDOW, never its title; 'something your eyes could not name' when the OS cannot say. Shared by rest_part and
    _bare_window's covered path. Read-only, never raises."""
    try:
        if not root:
            return _window_name(None)
        if any(int(w.get("hwnd") or 0) == int(root[0]) for w in _windows()):
            return _window_name(root)
        rr, vg0 = _root_rect(int(root[0])), _vg()
        if rr is None or vg0 is None:
            return _window_name(None)
        if not vg0._on_her_screen(rr):              # her monitor only: Ace's window is never named
            return ACE_WINDOW
        return _window_name(root)
    except Exception:
        return _window_name(None)


def _map_row_at(x: int, y: int) -> Optional[Dict]:
    """The front-most window of her map whose rect holds the point (the map comes front to back); None."""
    for w in _windows():
        r = w.get("rect")
        try:
            if r and int(r[0]) <= x < int(r[2]) and int(r[1]) <= y < int(r[3]):
                return w
        except Exception:
            continue
    return None


def rest_part(xy) -> Optional[Dict]:
    """e1b vision_hand: {'part', 'at', 'hwnd', 'name'} for a point of HER screen -- the root window the OS names there and, for a
    window in her map, the part: 'title bar' (above its client area), 'inside' (its client area), 'edge' (its frame); the desktop
    or the taskbar by class; another root by its name ONLY when its centre is on her screen (vision_ground._on_her_screen, the map's
    own rule) -- a window of Ace's that overhangs her screen by its frame is never named. Her own hand strip (a Tk wrapper her map
    skips, REST_SKIP) is never named: what lies under it in her map is told instead, or only the place on the screen (None). None:
    off her screen, or the OS cannot say. Read-only, never raises."""
    try:
        sw, sh = _screen()
        x, y = int(xy[0]), int(xy[1])
        if sw <= 0 or sh <= 0 or not (0 <= x < sw and 0 <= y < sh):
            return None
        root = _root_at(x, y)
        if root is None:
            return None
        w = next((w for w in _windows() if int(w.get("hwnd") or 0) == int(root[0])), None)
        if w is None or not w.get("rect"):
            cls = _root_class(int(root[0]))
            shell = REST_SHELL.get(cls)
            if shell is not None:
                return {"part": shell[0], "at": shell[1], "hwnd": int(root[0]), "name": None}
            if cls in REST_SKIP:                         # verify F5: her hand strip is not a window of her world
                w = _map_row_at(x, y)
                if w is None or not w.get("rect"):
                    return None                          # nothing of her map under it: the line says only where on the screen
            else:
                words = _root_words(root)
                if words == ACE_WINDOW:
                    return {"part": "other", "at": "on the edge of %s" % ACE_WINDOW, "hwnd": int(root[0]), "name": None}
                return {"part": "window", "at": "on %s" % words, "hwnd": int(root[0]), "name": None}
        vg = _vg()
        ww = vg.win_words(w) if (vg is not None and hasattr(vg, "win_words")) else str(w.get("title") or w.get("name") or "a window")
        l, t, r, b = [int(v) for v in w["rect"]]
        cr = _client_rect(int(w["hwnd"]))
        if cr is not None and cr[2] - cr[0] >= 8 and cr[3] - cr[1] >= 8:
            if cr[0] <= x < cr[2] and cr[1] <= y < cr[3]:
                part = "inside"
            elif y < cr[1] and cr[0] <= x < cr[2]:
                part = "title bar"
            else:
                part = "edge"
        else:                                           # the OS gave no client rect: the caption strip is the top INSIDE_TOP_DY px
            part = "title bar" if y < t + INSIDE_TOP_DY else "inside"
        return {"part": part, "at": REST_AT[part] % ww, "hwnd": int(w["hwnd"]), "name": w.get("name")}
    except Exception:
        return None


def _own_chat(root: Optional[Tuple[int, str]]) -> bool:
    """The window under a point is her OWN chat window: its text is her own words (every name she speaks), not the named thing."""
    return bool(root) and any(int(w.get("hwnd") or 0) == int(root[0]) and w.get("name") == "your chat window" for w in _windows())


def plan(obj: str) -> Optional[Dict]:
    """None: route (c), no landing check (today's path). Else {'kind', 'route', 'rec' (None -> ground as today), 'words', ...};
    {'busy': True} when the eyes are Ace's."""
    c = classify(obj)
    if c["kind"] == "in_window":                        # eyes_fix F4: ground the item inside the window's rect; no title bar
        w = c["window"]
        return {"kind": "in_window", "route": "ground_in", "hwnd": int(w["hwnd"]), "title": w.get("title"), "name": w.get("name"),
                "item": c["item"], "words": c["words"], "within": tuple(float(v) for v in w["frac"]), "rec": None}
    if c["kind"] == "playroom":                         # set1c: the toy's centre, unless another window covers it
        t = c["toy"]
        x, y = int(t["point"][0]), int(t["point"][1])
        hwnd = int(t["playroom"]["hwnd"])
        if not t.get("visible"):
            return {"kind": "playroom", "route": "playroom", "covered": True, "hwnd": hwnd, "name": t["name"], "words": c["words"],
                    "under": _window_name(_root_at(x, y)), "rec": None}
        return {"kind": "playroom", "route": "playroom", "hwnd": hwnd, "name": t["name"], "words": c["words"], "xy": (x, y),
                "rec": _rec(x, y, "playroom toy")}
    _bw = _bare_window(obj)                             # eyes_fix2 (window_names): toy names and 'X in <window>' above; then a
    if _bw is not None:                                 # BARE window name -> inside it; then today's routes
        return _bw
    if c["kind"] == "window":
        w = c["window"]
        pts = caption_points(w)
        if not pts:
            return None
        roots = [(p, _root_at(*p)) for p in pts]
        pick = next((p for p, r in roots if r is not None and int(r[0]) == int(w["hwnd"])), None)
        if pick is None:
            # 2026-09-29 (Fable, round-2 verifier L2/L3): every caption point the OS could name belongs to ANOTHER window -- the
            # window she named is fully covered, or was minimised / cloaked after the 2 s window-map cache filled. Before this
            # the hand went to pts[0] anyway and the landing check booked a MISS with the frustration chord, a goal failure and
            # a x2 tempo backoff, for a place she could never reach. Now: no move; intention treats it like a not-found (her
            # words say what it is behind, a try at her goal, the door's backoff, no chord). Only when the OS named NOTHING at
            # any point (root None everywhere) does the first point stay the aim, and the landing check decides.
            over = next((r for _p, r in roots if r is not None), None)
            if over is not None:
                return {"kind": "window", "route": "window", "covered": True, "hwnd": int(w["hwnd"]), "title": w.get("title"),
                        "name": w.get("name"), "words": c["words"], "under": _window_name(over), "rec": None}
            pick = pts[0]
        return {"kind": "window", "route": "window", "hwnd": int(w["hwnd"]), "title": w.get("title"), "name": w.get("name"),
                "words": c["words"], "xy": pick, "rec": _rec(pick[0], pick[1], "window caption")}
    if c["kind"] == "text":
        found = _find_text_boxes(c["words"]) or {}
        if found.get("busy"):
            return {"busy": True, "kind": "text", "words": c["words"]}
        hits = [b for b in found.get("boxes") or [] if _all_in(c["words"], b["label"])
                and not _own_chat(_root_at(int((b["rect"][0] + b["rect"][2]) / 2.0), int((b["rect"][1] + b["rect"][3]) / 2.0)))]
        if hits:
            b = min(hits, key=lambda h: len(_norm(h["label"])))      # the tightest label that holds every name word
            x, y = int((b["rect"][0] + b["rect"][2]) / 2.0), int((b["rect"][1] + b["rect"][3]) / 2.0)
            return {"kind": "text", "route": "text", "words": c["words"], "label": b["label"], "xy": (x, y), "rec": _rec(x, y, "text")}
        return {"kind": "text", "route": "ground", "words": c["words"], "rec": None, "looked": bool(found.get("looked"))}
    if _ef("hand_honest"):                             # eyes_fix F4: a visual move gets a landing READ, never 'arrived'
        return {"kind": "visual", "route": "ground", "words": c["words"], "name": c["name"], "rec": None}
    return None


def check_landing(p: Optional[Dict], xy) -> Optional[Dict]:
    """{'verdict': 'arrived' | 'miss' | 'unverified', 'under', 'why'} for a window / text object; None for anything else."""
    if not p or p.get("kind") not in ("window", "text", "playroom", "in_window", "visual"):   # eyes_fix F4: + in_window, visual
        return None
    if xy is None:
        return {"verdict": "unverified", "under": None, "why": "the hand's landing was not read"}
    x, y = int(xy[0]), int(xy[1])
    if p["kind"] in ("in_window", "visual"):            # eyes_fix F4: a READ of what is under the hand -- never 'arrived'
        root = _root_at(x, y)
        if p["kind"] == "in_window" and root is not None and int(root[0]) != int(p["hwnd"]):
            return {"verdict": "miss", "under": _window_name(root), "why": "the window under the hand is not the one she named"}
        return {"verdict": "unverified", "under": (_window_name(root) if root is not None else None),
                "why": "her eyes could not check that the hand is on \"%s\"" % (p.get("item") or p.get("name") or "it")}
    if p["kind"] == "playroom":                         # set1c: the Playroom under the hand, and the hand on the toy NOW
        root = _root_at(x, y)
        if root is None:
            return {"verdict": "unverified", "under": None, "why": "the OS did not say which window is under the hand"}
        if int(root[0]) != int(p["hwnd"]):
            return {"verdict": "miss", "under": _window_name(root), "why": "the window under the hand is not her Playroom"}
        t = _playroom_toy(p.get("name") or "")
        if t is None:                                   # fold 10-09 (DIAGNOSIS 5.2): no toy record now = unknown, never 'arrived'
            return {"verdict": "unverified", "under": "your Playroom",
                    "why": "her eyes could not say where the %s is now" % p.get("name")}
        if not (t["rect"][0] <= x < t["rect"][2] and t["rect"][1] <= y < t["rect"][3]):
            return {"verdict": "miss", "under": "your Playroom", "why": "the hand is in her Playroom but not on the %s" % p.get("name")}
        return {"verdict": "arrived", "under": p.get("name"), "why": "the toy she named is under the hand"}
    if p["kind"] == "window":
        root = _root_at(x, y)
        if root is None:
            return {"verdict": "unverified", "under": None, "why": "the OS did not say which window is under the hand"}
        if int(root[0]) == int(p["hwnd"]):
            return {"verdict": "arrived", "under": p.get("name"), "why": "the window under the hand is the one she named"}
        return {"verdict": "miss", "under": _window_name(root), "why": "the window under the hand is not the one she named"}
    root = _root_at(x, y)
    if _own_chat(root):
        return {"verdict": "miss", "under": _window_name(root), "why": "the hand is on her own chat window (her own words), not the text she named"}
    txt = _read_text_at((x - CROP_W / 2.0, y - CROP_H / 2.0, x + CROP_W / 2.0, y + CROP_H / 2.0))
    if txt is None:
        return {"verdict": "unverified", "under": None, "why": "her eyes could not read what is under the hand"}
    if _all_in(p.get("words") or [], txt):
        return {"verdict": "arrived", "under": p.get("label") or " ".join(p.get("words") or []), "why": "the words under the hand match"}
    return {"verdict": "miss", "under": _window_name(root), "read": txt[:80], "why": "the words under the hand are not the ones she named"}


# ── eyes_fix F4 'hand_honest': the move told as it was (DIAGNOSIS C3 / section 2 rows 1 and 4) ───────────────────────────
def aimed_words(p: Optional[Dict], obj: str) -> str:
    """What the hand was AIMED at, in her words: 'the title bar of a window called 'Sour's Playroom'', never only the words
    she said (intention.py:1369-1371 named the object; the aim was the caption strip)."""
    k = (p or {}).get("kind")
    if k == "window":
        if p.get("aim") == "inside":                    # eyes_fix2 (window_names): a bare window name -- inside it, not its title bar
            return "the inside of %s" % (p.get("label") or p.get("title") or p.get("name") or "that window")
        return "the title bar of %s" % (p.get("title") or p.get("name") or "that window")
    if k == "playroom":
        return "the %s in your Playroom" % (p.get("name") or "toy")
    if k == "text":
        return "the words '%s' on the screen" % (p.get("label") or " ".join(p.get("words") or []) or strip_echo(obj))
    if k == "in_window":
        return "where your eyes put \"%s\" in %s" % (p.get("item") or strip_echo(obj), p.get("title") or p.get("name") or "that window")
    return "where your eyes put \"%s\"" % strip_echo(obj)


def told_move(obj: str, p: Optional[Dict], rec: Optional[Dict], reached: bool, land: Optional[Dict], where_after: str = "") -> str:
    """The move's summary: what the hand was aimed at, where that is, and what is under the hand now -- 'arrived' only from a
    landing check that can fail; a READ (visual, in_window) is told as what is under the hand and that her eyes could not
    check it."""
    head = "you moved your hand to %s (%s of the screen)" % (aimed_words(p, obj), (rec or {}).get("position", "?"))
    if not reached:
        return head + " but it did not arrive" + (where_after or "")
    v, under = (land or {}).get("verdict"), (land or {}).get("under")
    if v == "arrived":
        return head + " and it is resting there now"
    if v == "miss":
        return head + " but it landed on %s, not on it" % (under or "something else")
    s = head + "; your eyes could not check it is on it"
    if under and not ((p or {}).get("kind") == "in_window" and under == (p or {}).get("name")):
        s += " -- it is over %s" % under
    return s
